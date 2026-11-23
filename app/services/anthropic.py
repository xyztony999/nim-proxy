"""Anthropic Messages API <-> OpenAI Chat Completions translation.

Lets Anthropic-format clients (e.g. Claude Code via cc-switch) use the NIM relay:
Anthropic request in -> OpenAI request to NIM -> OpenAI response -> Anthropic out.
Supports text, images, tools/tool_use/tool_result, and streaming SSE.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from app.core.config import Config
from app.core.errors import Unauthorized, UpstreamUnavailable
from app.core.http_client import HttpClient
from app.repositories.base import Repository
from app.services.sse import iter_chat_chunks, iter_keepalive, one_shot, retry_on_timeout

log = logging.getLogger("nim-proxy")

RETRY_STATUS = {401, 403, 429}
_STOP_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}


def map_model(model: str | None, default_model: str) -> str:
    # NIM model ids contain "/"; Anthropic model names (claude-*) map to the default.
    if model and "/" in model:
        return model
    return default_model


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def to_openai_request(body: dict, default_model: str) -> dict:
    messages: list[dict] = []
    system = body.get("system")
    if system:
        messages.append({"role": "system", "content": _text_of(system)})

    for m in body.get("messages", []):
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            continue

        if role == "assistant":
            texts, tool_calls = [], []
            for b in content:
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    tool_calls.append({
                        "id": b.get("id"),
                        "type": "function",
                        "function": {
                            "name": b.get("name"),
                            "arguments": json.dumps(b.get("input", {})),
                        },
                    })
            am: dict = {"role": "assistant", "content": "\n".join(texts) or None}
            if tool_calls:
                am["tool_calls"] = tool_calls
            messages.append(am)
        else:  # user
            parts = []
            for b in content:
                bt = b.get("type")
                if bt == "tool_result":
                    tc = b.get("content")
                    text = _text_of(tc) if isinstance(tc, list) else str(tc or "")
                    messages.append(
                        {"role": "tool", "tool_call_id": b.get("tool_use_id"), "content": text}
                    )
                elif bt == "text":
                    parts.append({"type": "text", "text": b.get("text", "")})
                elif bt == "image":
                    src = b.get("source", {})
                    url = src.get("url") or (
                        f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"
                    )
                    parts.append({"type": "image_url", "image_url": {"url": url}})
            if parts:
                if all(p["type"] == "text" for p in parts):
                    messages.append(
                        {"role": "user", "content": "\n".join(p["text"] for p in parts)}
                    )
                else:
                    messages.append({"role": "user", "content": parts})

    oai: dict = {
        "model": map_model(body.get("model"), default_model),
        "messages": messages,
        "max_tokens": body.get("max_tokens", 1024),
        "stream": bool(body.get("stream", False)),
    }
    for k in ("temperature", "top_p"):
        if k in body:
            oai[k] = body[k]
    if body.get("stop_sequences"):
        oai["stop"] = body["stop_sequences"]
    if body.get("tools"):
        oai["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in body["tools"]
        ]
    tc = body.get("tool_choice")
    if isinstance(tc, dict):
        if tc.get("type") == "auto":
            oai["tool_choice"] = "auto"
        elif tc.get("type") == "any":
            oai["tool_choice"] = "required"
        elif tc.get("type") == "tool":
            oai["tool_choice"] = {"type": "function", "function": {"name": tc.get("name")}}
    return oai


def to_anthropic_message(oai: dict, model: str) -> dict:
    choice = (oai.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    content = []
    if msg.get("content"):
        content.append({"type": "text", "text": msg["content"]})
    for tc in msg.get("tool_calls") or []:
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except ValueError:
            args = {}
        content.append({
            "type": "tool_use", "id": tc.get("id"),
            "name": tc["function"].get("name"), "input": args,
        })
    usage = oai.get("usage") or {}
    return {
        "id": oai.get("id") or f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": _STOP_MAP.get(choice.get("finish_reason"), "end_turn"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _message_start(msgid: str, model: str, input_tokens: int) -> str:
    return _sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msgid, "type": "message", "role": "assistant", "model": model,
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": 0},
        },
    })


class AnthropicStream:
    """Stateful OpenAI SSE chunk -> Anthropic SSE event translator."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._started = False
        self._next_index = 0
        self._text_index: int | None = None
        self._tool_blocks: dict[int, int] = {}
        self._open_index: int | None = None
        self._finish: str | None = None
        self._input_tokens = 0
        self._output_tokens = 0
        self._msgid = f"msg_{uuid.uuid4().hex}"

    def start(self) -> list[str]:
        """Initial events, emitted before the upstream fetch to flush headers."""
        out: list[str] = []
        if not self._started:
            self._started = True
            out.append(_message_start(self._msgid, self._model, self._input_tokens))
            out.append(_sse("ping", {"type": "ping"}))
        return out

    def fail(self, message: str) -> str:
        return _sse("error", {
            "type": "error", "error": {"type": "api_error", "message": message},
        })

    def ping(self) -> str:
        # Real Anthropic ping event as keepalive (clients ignore SSE comments
        # for idle-timeout purposes; ping is a standard Anthropic event).
        return _sse("ping", {"type": "ping"})

    @property
    def usage(self) -> dict:
        return {"input_tokens": self._input_tokens, "output_tokens": self._output_tokens}

    def _close_block(self, out: list[str]) -> None:
        if self._open_index is not None:
            out.append(_sse(
                "content_block_stop", {"type": "content_block_stop", "index": self._open_index}
            ))
            self._open_index = None

    def _open_block(self, out: list[str], block: dict) -> int:
        self._close_block(out)
        index = self._next_index
        self._next_index += 1
        self._open_index = index
        out.append(_sse(
            "content_block_start",
            {"type": "content_block_start", "index": index, "content_block": block},
        ))
        return index

    def feed(self, chunk: dict) -> list[str]:
        out: list[str] = []
        usage = chunk.get("usage")
        if usage:
            self._input_tokens = usage.get("prompt_tokens", self._input_tokens)
            self._output_tokens = usage.get("completion_tokens", self._output_tokens)
        if not self._started:
            self._started = True
            out.append(_message_start(self._msgid, self._model, self._input_tokens))
            out.append(_sse("ping", {"type": "ping"}))
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                if self._text_index is None:
                    self._text_index = self._open_block(out, {"type": "text", "text": ""})
                out.append(_sse("content_block_delta", {
                    "type": "content_block_delta", "index": self._text_index,
                    "delta": {"type": "text_delta", "text": delta["content"]},
                }))
            for tc in delta.get("tool_calls") or []:
                tindex = tc.get("index", 0)
                fn = tc.get("function") or {}
                if tindex not in self._tool_blocks:
                    self._text_index = None
                    block = {
                        "type": "tool_use",
                        "id": tc.get("id") or f"toolu_{uuid.uuid4().hex}",
                        "name": fn.get("name") or "",
                        "input": {},
                    }
                    self._tool_blocks[tindex] = self._open_block(out, block)
                args = fn.get("arguments")
                if args:
                    out.append(_sse("content_block_delta", {
                        "type": "content_block_delta", "index": self._tool_blocks[tindex],
                        "delta": {"type": "input_json_delta", "partial_json": args},
                    }))
            if choice.get("finish_reason"):
                self._finish = choice["finish_reason"]
        return out

    def finish(self) -> list[str]:
        out: list[str] = []
        if not self._started:
            out.append(_message_start(self._msgid, self._model, self._input_tokens))
        self._close_block(out)
        out.append(_sse("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": _STOP_MAP.get(self._finish, "end_turn"), "stop_sequence": None,
            },
            "usage": {"output_tokens": self._output_tokens},
        }))
        out.append(_sse("message_stop", {"type": "message_stop"}))
        return out


def client_token(headers: dict) -> str | None:
    lowered = {k.lower(): v for k, v in headers.items()}
    if lowered.get("x-api-key"):
        return lowered["x-api-key"]
    auth = lowered.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


class AnthropicService:
    def __init__(self, repo: Repository, http: HttpClient, config: Config) -> None:
        self._repo = repo
        self._http = http
        self._config = config

    async def _auth(self, token: str | None) -> str | None:
        counts = await self._repo.count_keys()
        if counts["client"] == 0:
            return None  # relay-only mode
        if not token:
            raise Unauthorized("Invalid or missing API key")
        client = await self._repo.find_client_key_by_secret(token)
        if not client:
            raise Unauthorized("Invalid or missing API key")
        await self._repo.record_client_used(client["id"])
        return client["id"]

    async def _open_upstream(self, url: str, payload: bytes, keys: list):
        attempts = len(keys) if keys else 1
        used_key = None
        stream = None
        for i in range(attempts):
            req_headers = {"Content-Type": "application/json"}
            if keys:
                used_key = keys[i]
                req_headers["Authorization"] = f"Bearer {used_key['secret']}"
            stream = await self._http.stream("POST", url, headers=req_headers, content=payload)
            if stream.status in RETRY_STATUS and i < attempts - 1:
                await stream.aclose()
                continue
            break
        stream = await retry_on_timeout(
            self._http, stream, method="POST", url=url, headers=req_headers, content=payload
        )
        if stream is None:
            raise UpstreamUnavailable("没有可用的上游密钥")
        return stream, used_key

    async def messages(self, body: dict, headers: dict) -> tuple[dict | AsyncIterator[str], dict]:
        client_key_id = await self._auth(client_token(headers))
        oai = to_openai_request(body, self._config.anthropic_model)
        model = oai["model"]
        payload = json.dumps(oai).encode("utf-8")
        keys = await self._repo.list_enabled_upstream_keys()
        url = f"{self._config.upstream}/v1/chat/completions"

        telemetry = {
            "client_key_id": client_key_id,
            "upstream_key_id": None,
            "method": "POST",
            "path": "/v1/messages",
            "model": model,
            "status": 200,
            "latency_ms": 0,
            "stream": bool(oai["stream"]),
            "prompt_tokens": None,
            "completion_tokens": None,
        }

        if oai["stream"]:
            # Return the iterator immediately; the upstream fetch happens inside
            # it so SSE headers reach the client before NIM's (possibly >100s)
            # first byte, avoiding Cloudflare's 524 origin timeout.
            return self._stream(oai, url, payload, keys, telemetry), telemetry

        stream, used_key = await self._open_upstream(url, payload, keys)
        status = stream.status
        if used_key:
            await self._repo.record_upstream_result(used_key["id"], status)
        telemetry["upstream_key_id"] = used_key["id"] if used_key else None
        telemetry["status"] = status

        if status >= 400:
            content = b"".join([c async for c in stream.aiter_bytes()])
            await stream.aclose()
            err = {
                "type": "error",
                "error": {"type": "api_error", "message": content[:500].decode("utf-8", "replace")},
            }
            return err, telemetry

        content = b"".join([c async for c in stream.aiter_bytes()])
        await stream.aclose()
        try:
            oai_resp = json.loads(content)
        except ValueError:
            oai_resp = {}
        msg = to_anthropic_message(oai_resp, model)
        telemetry["prompt_tokens"] = msg["usage"]["input_tokens"]
        telemetry["completion_tokens"] = msg["usage"]["output_tokens"]
        return msg, telemetry

    async def _stream(
        self, oai: dict, url: str, payload: bytes, keys: list, telemetry: dict
    ) -> AsyncIterator[str]:
        translator = AnthropicStream(oai["model"])
        # Flush message_start/ping (and thus response headers) right away.
        for ev in translator.start():
            yield ev

        stream = None
        used_key = None
        try:
            async for item in iter_keepalive(one_shot(self._open_upstream(url, payload, keys))):
                if isinstance(item, str):
                    yield translator.ping()  # real event keeps client idle timer reset
                    continue
                stream, used_key = item

            status = stream.status
            if used_key:
                await self._repo.record_upstream_result(used_key["id"], status)
            telemetry["upstream_key_id"] = used_key["id"] if used_key else None
            telemetry["status"] = status

            if status >= 400:
                content = b"".join([c async for c in stream.aiter_bytes()])
                yield translator.fail(content[:500].decode("utf-8", "replace"))
                return

            async for item in iter_keepalive(iter_chat_chunks(stream)):
                if isinstance(item, str):
                    yield translator.ping()
                    continue
                for ev in translator.feed(item):
                    yield ev
            for ev in translator.finish():
                yield ev
            telemetry["prompt_tokens"] = translator.usage["input_tokens"]
            telemetry["completion_tokens"] = translator.usage["output_tokens"]
        except UpstreamUnavailable as exc:
            telemetry["status"] = 503
            yield translator.fail(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface mid-stream upstream failure in-band
            log.exception("anthropic stream failed mid-flight")
            telemetry["status"] = 502
            yield translator.fail(str(exc))
        finally:
            if stream is not None:
                await stream.aclose()
