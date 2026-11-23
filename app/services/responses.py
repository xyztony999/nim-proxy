"""OpenAI Responses API <-> Chat Completions translation.

Lets Responses-wire clients (e.g. Codex via cc-switch, wire_api="responses") use
the NIM relay: Responses request in -> chat/completions to NIM -> Responses out.
Supports text, function calls, and streaming Responses SSE events.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from app.core.config import Config
from app.core.errors import Unauthorized, UpstreamUnavailable
from app.core.http_client import HttpClient
from app.repositories.base import Repository
from app.services.anthropic import RETRY_STATUS, client_token, map_model
from app.services.sse import iter_chat_chunks, iter_keepalive, one_shot, retry_on_timeout

log = logging.getLogger("nim-proxy")


def _hex() -> str:
    return uuid.uuid4().hex


def to_chat_request(body: dict, default_model: str) -> dict:
    messages: list[dict] = []
    if body.get("instructions"):
        messages.append({"role": "system", "content": body["instructions"]})

    pending: list[dict] = []

    def flush() -> None:
        if pending:
            messages.append({"role": "assistant", "content": None, "tool_calls": pending[:]})
            pending.clear()

    inp = body.get("input")
    if isinstance(inp, str):
        messages.append({"role": "user", "content": inp})
    elif isinstance(inp, list):
        for item in inp:
            t = item.get("type")
            if t == "message":
                flush()
                role = item.get("role", "user")
                if role == "developer":
                    role = "system"
                content = item.get("content")
                if isinstance(content, str):
                    messages.append({"role": role, "content": content})
                elif isinstance(content, list):
                    texts, parts = [], []
                    for p in content:
                        pt = p.get("type")
                        if pt in ("input_text", "output_text", "text"):
                            texts.append(p.get("text", ""))
                        elif pt == "input_image":
                            url = p.get("image_url", "")
                            parts.append({"type": "image_url", "image_url": {"url": url}})
                    if parts:
                        if texts:
                            parts.insert(0, {"type": "text", "text": "\n".join(texts)})
                        messages.append({"role": role, "content": parts})
                    else:
                        messages.append({"role": role, "content": "\n".join(texts)})
            elif t == "function_call":
                pending.append({
                    "id": item.get("call_id"),
                    "type": "function",
                    "function": {
                        "name": item.get("name"), "arguments": item.get("arguments", "{}"),
                    },
                })
            elif t == "function_call_output":
                flush()
                messages.append({
                    "role": "tool",
                    "tool_call_id": item.get("call_id"),
                    "content": item.get("output", ""),
                })
        flush()

    chat: dict = {
        "model": map_model(body.get("model"), default_model),
        "messages": messages,
        "stream": bool(body.get("stream", False)),
    }
    if body.get("max_output_tokens"):
        chat["max_tokens"] = body["max_output_tokens"]
    for k in ("temperature", "top_p"):
        if k in body:
            chat[k] = body[k]
    effort = (body.get("reasoning") or {}).get("effort")
    if effort:
        chat["reasoning_effort"] = effort
    fns = []
    for t in body.get("tools") or []:
        if t.get("type") == "function":
            fns.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {}),
                },
            })
    if fns:
        chat["tools"] = fns
    if body.get("tool_choice"):
        chat["tool_choice"] = body["tool_choice"]
    return chat


def _usage(chat: dict) -> dict:
    u = chat.get("usage") or {}
    pt, ct = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    return {"input_tokens": pt, "output_tokens": ct, "total_tokens": pt + ct}


def to_responses_object(chat: dict, model: str) -> dict:
    choice = (chat.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    output = []
    if msg.get("content"):
        output.append({
            "type": "message", "id": f"msg_{_hex()}", "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": msg["content"], "annotations": []}],
        })
    for tc in msg.get("tool_calls") or []:
        output.append({
            "type": "function_call", "id": f"fc_{_hex()}", "call_id": tc.get("id"),
            "name": tc["function"].get("name"),
            "arguments": tc["function"].get("arguments", "{}"), "status": "completed",
        })
    return {
        "id": chat.get("id") or f"resp_{_hex()}", "object": "response",
        "created_at": int(time.time()), "status": "completed", "model": model,
        "output": output, "usage": _usage(chat),
        "error": None, "incomplete_details": None, "metadata": {},
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ev(out: list[str], event: str, **fields) -> None:
    out.append(_sse(event, {"type": event, **fields}))


class ResponsesStream:
    """Stateful chat SSE chunk -> Responses SSE event translator."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._resp_id = f"resp_{_hex()}"
        self._started = False
        self._next_index = 0
        self._reasoning: dict | None = None
        self._reasoning_index = 0
        self._reasoning_text = ""
        self._msg: dict | None = None
        self._msg_index = 0
        self._msg_text = ""
        self._tools: dict[int, dict] = {}
        self._items: list[tuple[int, dict]] = []
        self._finish: str | None = None
        self._usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _skeleton(self, status: str) -> dict:
        return {
            "id": self._resp_id, "object": "response", "created_at": int(time.time()),
            "status": status, "model": self._model, "output": [], "usage": None,
            "error": None, "incomplete_details": None, "metadata": {},
        }

    def _start(self, out: list[str]) -> None:
        self._started = True
        _ev(out, "response.created", response=self._skeleton("in_progress"))
        _ev(out, "response.in_progress", response=self._skeleton("in_progress"))

    def start(self) -> list[str]:
        """Initial events, emitted before the upstream fetch to flush headers."""
        out: list[str] = []
        if not self._started:
            self._start(out)
        return out

    def fail(self, code: str, message: str) -> str:
        resp = self._skeleton("failed")
        resp["error"] = {"code": code, "message": message}
        return _sse("response.failed", {"type": "response.failed", "response": resp})

    def ping(self) -> str:
        # Keepalive as a REAL event, not an SSE comment: Codex's eventsource
        # parser skips comments, so only real events reset its stream idle
        # timeout. response.in_progress is parsed then safely ignored by Codex.
        return _sse("response.in_progress", {
            "type": "response.in_progress", "response": self._skeleton("in_progress"),
        })

    @property
    def usage(self) -> dict:
        return self._usage

    def feed(self, chunk: dict) -> list[str]:
        out: list[str] = []
        if chunk.get("usage"):
            self._usage = _usage(chunk)
        if not self._started:
            self._start(out)
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("reasoning_content"):
                self._feed_reasoning(out, delta["reasoning_content"])
            if delta.get("content"):
                self._feed_text(out, delta["content"])
            for tc in delta.get("tool_calls") or []:
                self._feed_tool(out, tc)
            if choice.get("finish_reason"):
                self._finish = choice["finish_reason"]
        return out

    def _feed_reasoning(self, out: list[str], text: str) -> None:
        # Reasoning models (minimax/nemotron/kimi) stream a long chain-of-thought
        # before any answer. Surface it as a Responses reasoning item so clients
        # (e.g. Codex) see activity during the thinking phase instead of timing
        # out on keepalive comments alone.
        if self._reasoning is None:
            self._reasoning_index = self._next_index
            self._next_index += 1
            self._reasoning = {
                "type": "reasoning", "id": f"rs_{_hex()}", "summary": [],
            }
            _ev(out, "response.output_item.added",
                output_index=self._reasoning_index, item=self._reasoning)
            _ev(out, "response.reasoning_summary_part.added", item_id=self._reasoning["id"],
                output_index=self._reasoning_index, summary_index=0,
                part={"type": "summary_text", "text": ""})
        self._reasoning_text += text
        _ev(out, "response.reasoning_summary_text.delta", item_id=self._reasoning["id"],
            output_index=self._reasoning_index, summary_index=0, delta=text)

    def _feed_text(self, out: list[str], text: str) -> None:
        if self._msg is None:
            self._msg_index = self._next_index
            self._next_index += 1
            self._msg = {
                "type": "message", "id": f"msg_{_hex()}", "role": "assistant",
                "status": "in_progress", "content": [],
            }
            _ev(out, "response.output_item.added", output_index=self._msg_index, item=self._msg)
            part = {"type": "output_text", "text": "", "annotations": []}
            _ev(out, "response.content_part.added", item_id=self._msg["id"],
                output_index=self._msg_index, content_index=0, part=part)
        self._msg_text += text
        _ev(out, "response.output_text.delta", item_id=self._msg["id"],
            output_index=self._msg_index, content_index=0, delta=text)

    def _feed_tool(self, out: list[str], tc: dict) -> None:
        tindex = tc.get("index", 0)
        fn = tc.get("function") or {}
        if tindex not in self._tools:
            idx = self._next_index
            self._next_index += 1
            item = {
                "type": "function_call", "id": f"fc_{_hex()}",
                "call_id": tc.get("id") or f"call_{_hex()}",
                "name": fn.get("name") or "", "arguments": "", "status": "in_progress",
            }
            self._tools[tindex] = {"item": item, "index": idx}
            _ev(out, "response.output_item.added", output_index=idx, item=item)
        if fn.get("arguments"):
            entry = self._tools[tindex]
            entry["item"]["arguments"] += fn["arguments"]
            _ev(out, "response.function_call_arguments.delta",
                item_id=entry["item"]["id"], output_index=entry["index"], delta=fn["arguments"])

    def finish(self) -> list[str]:
        out: list[str] = []
        if not self._started:
            self._start(out)
        if self._reasoning is not None:
            rid, ri = self._reasoning["id"], self._reasoning_index
            part = {"type": "summary_text", "text": self._reasoning_text}
            _ev(out, "response.reasoning_summary_text.done", item_id=rid,
                output_index=ri, summary_index=0, text=self._reasoning_text)
            _ev(out, "response.reasoning_summary_part.done", item_id=rid,
                output_index=ri, summary_index=0, part=part)
            self._reasoning["summary"] = [part]
            _ev(out, "response.output_item.done", output_index=ri, item=self._reasoning)
            self._items.append((ri, self._reasoning))
        if self._msg is not None:
            self._msg["content"] = [
                {"type": "output_text", "text": self._msg_text, "annotations": []}
            ]
            self._msg["status"] = "completed"
            mid, mi = self._msg["id"], self._msg_index
            _ev(out, "response.output_text.done", item_id=mid, output_index=mi,
                content_index=0, text=self._msg_text)
            _ev(out, "response.content_part.done", item_id=mid, output_index=mi,
                content_index=0, part=self._msg["content"][0])
            _ev(out, "response.output_item.done", output_index=mi, item=self._msg)
            self._items.append((mi, self._msg))
        for entry in self._tools.values():
            entry["item"]["status"] = "completed"
            tid, ti = entry["item"]["id"], entry["index"]
            _ev(out, "response.function_call_arguments.done", item_id=tid,
                output_index=ti, arguments=entry["item"]["arguments"])
            _ev(out, "response.output_item.done", output_index=ti, item=entry["item"])
            self._items.append((ti, entry["item"]))
        final = self._skeleton("completed")
        final["output"] = [item for _, item in sorted(self._items, key=lambda x: x[0])]
        final["usage"] = self._usage
        _ev(out, "response.completed", response=final)
        return out


class ResponsesService:
    def __init__(self, repo: Repository, http: HttpClient, config: Config) -> None:
        self._repo = repo
        self._http = http
        self._config = config

    async def _auth(self, token: str | None) -> str | None:
        counts = await self._repo.count_keys()
        if counts["client"] == 0:
            return None
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

    async def create(self, body: dict, headers: dict) -> tuple[dict | AsyncIterator[str], dict]:
        client_key_id = await self._auth(client_token(headers))
        chat = to_chat_request(body, self._config.anthropic_model)
        model = chat["model"]
        payload = json.dumps(chat).encode("utf-8")
        keys = await self._repo.list_enabled_upstream_keys()
        url = f"{self._config.upstream}/v1/chat/completions"

        telemetry = {
            "client_key_id": client_key_id,
            "upstream_key_id": None,
            "method": "POST", "path": "/v1/responses", "model": model, "status": 200,
            "latency_ms": 0, "stream": bool(chat["stream"]),
            "prompt_tokens": None, "completion_tokens": None,
        }

        if chat["stream"]:
            # Return the iterator immediately; the upstream fetch happens inside
            # it so SSE headers reach the client before NIM's (possibly >100s)
            # first byte, avoiding Cloudflare's 524 origin timeout.
            return self._stream(chat, url, payload, keys, telemetry), telemetry

        stream, used_key = await self._open_upstream(url, payload, keys)
        status = stream.status
        if used_key:
            await self._repo.record_upstream_result(used_key["id"], status)
        telemetry["upstream_key_id"] = used_key["id"] if used_key else None
        telemetry["status"] = status

        if status >= 400:
            content = b"".join([c async for c in stream.aiter_bytes()])
            await stream.aclose()
            msg = content[:500].decode("utf-8", "replace")
            return {"error": {"message": msg, "type": "api_error", "code": status}}, telemetry

        content = b"".join([c async for c in stream.aiter_bytes()])
        await stream.aclose()
        try:
            chat_resp = json.loads(content)
        except ValueError:
            chat_resp = {}
        obj = to_responses_object(chat_resp, model)
        telemetry["prompt_tokens"] = obj["usage"]["input_tokens"]
        telemetry["completion_tokens"] = obj["usage"]["output_tokens"]
        return obj, telemetry

    async def _stream(
        self, chat: dict, url: str, payload: bytes, keys: list, telemetry: dict
    ) -> AsyncIterator[str]:
        translator = ResponsesStream(chat["model"])
        # Flush initial events (and thus response headers) right away.
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
                msg = content[:500].decode("utf-8", "replace")
                yield translator.fail(str(status), msg)
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
            yield translator.fail("upstream_unavailable", str(exc))
        except Exception as exc:  # noqa: BLE001 - surface mid-stream upstream failure in-band
            log.exception("responses stream failed mid-flight")
            telemetry["status"] = 502
            yield translator.fail("upstream_error", str(exc))
        finally:
            if stream is not None:
                await stream.aclose()
