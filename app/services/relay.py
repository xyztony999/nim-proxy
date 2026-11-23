"""Relay service: client auth, upstream key rotation, passthrough, retry, telemetry.

Platform-agnostic: outbound calls go through the injected HttpClient.
"""

from __future__ import annotations

import json
import logging
import time

from starlette.background import BackgroundTask
from starlette.responses import Response, StreamingResponse

from app.core.config import Config
from app.core.errors import Unauthorized, UpstreamUnavailable
from app.core.http_client import HttpClient
from app.repositories.base import Repository
from app.schemas.common import AuthMode
from app.services.sse import iter_keepalive, one_shot

log = logging.getLogger("nim-proxy")

RETRY_STATUS = {401, 403, 429}
DROP_HEADERS = {
    "host", "content-length", "connection", "keep-alive", "transfer-encoding",
    "te", "trailers", "upgrade", "expect", "proxy-authorization", "proxy-authenticate",
}
_MAX_PARSE_BYTES = 1_000_000  # skip model/usage extraction for large bodies


class RelayService:
    def __init__(self, repo: Repository, http: HttpClient, config: Config) -> None:
        self._repo = repo
        self._http = http
        self._config = config

    async def auth_mode(self) -> AuthMode:
        counts = await self._repo.count_keys()
        return AuthMode.enforced if counts["client"] > 0 else AuthMode.relay_only

    async def relay(
        self,
        *,
        method: str,
        path: str,
        query: str,
        headers: dict[str, str],
        body: bytes,
        bearer: str | None,
    ) -> tuple[Response, dict]:
        t0 = time.perf_counter()

        # 1. client auth
        client_key_id = None
        mode = await self.auth_mode()
        if mode is AuthMode.enforced:
            if not bearer:
                raise Unauthorized("Invalid or missing API key")
            client = await self._repo.find_client_key_by_secret(bearer)
            if not client:
                raise Unauthorized("Invalid or missing API key")
            client_key_id = client["id"]
            await self._repo.record_client_used(client_key_id)

        # 2. upstream key pool
        keys = await self._repo.list_enabled_upstream_keys()
        url = self._config.upstream + "/" + path.lstrip("/")
        if query:
            url += "?" + query
        forward_headers = {k: v for k, v in headers.items() if k.lower() not in DROP_HEADERS}

        # 3. streaming requests: respond immediately, fetch upstream lazily so
        # headers beat Cloudflare's ~100s origin timeout when NIM is slow.
        if _is_stream_request(body):
            return self._lazy_stream(
                method, url, forward_headers, body, keys,
                client_key_id, path, t0,
            )

        # 4. forward with rotation/retry
        stream, used_key = await self._forward(method, url, forward_headers, body, keys)

        status = stream.status
        resp_headers = {
            k: v for k, v in stream.headers.items()
            if k.lower() not in ("content-length", "transfer-encoding", "connection")
        }
        ctype = stream.headers.get("content-type", "")
        is_sse = "text/event-stream" in ctype
        latency_ms = round((time.perf_counter() - t0) * 1000)

        if used_key:
            await self._repo.record_upstream_result(used_key["id"], status)

        model = _extract_model(body)
        prompt_tokens = completion_tokens = None

        if is_sse:
            resp_headers.setdefault("x-accel-buffering", "no")

            async def relay_iter():
                try:
                    async for chunk in stream.aiter_bytes():
                        yield chunk
                finally:
                    await stream.aclose()

            response: Response = StreamingResponse(
                relay_iter(),
                status_code=status,
                headers=resp_headers,
                media_type="text/event-stream",
                background=BackgroundTask(stream.aclose),
            )
        else:
            chunks = [chunk async for chunk in stream.aiter_bytes()]
            await stream.aclose()
            content = b"".join(chunks)
            prompt_tokens, completion_tokens = _extract_usage(content)
            response = Response(
                content=content, status_code=status, headers=resp_headers,
                media_type=ctype or None,
            )

        telemetry = {
            "client_key_id": client_key_id,
            "upstream_key_id": used_key["id"] if used_key else None,
            "method": method,
            "path": "/" + path.lstrip("/"),
            "model": model,
            "status": status,
            "latency_ms": latency_ms,
            "stream": is_sse,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        return response, telemetry

    async def _forward(self, method, url, forward_headers, body, keys):
        attempts = len(keys) if keys else 1
        used_key = None
        stream = None
        for i in range(attempts):
            req_headers = dict(forward_headers)
            if keys:
                used_key = keys[i]
                req_headers["authorization"] = f"Bearer {used_key['secret']}"
            stream = await self._http.stream(method, url, headers=req_headers, content=body)
            if stream.status in RETRY_STATUS and i < attempts - 1:
                await stream.aclose()
                log.warning("upstream %s, rotating key", stream.status)
                continue
            break
        if stream is None:
            raise UpstreamUnavailable("没有可用的上游密钥")
        return stream, used_key

    def _lazy_stream(
        self, method, url, forward_headers, body, keys,
        client_key_id, path, t0,
    ) -> tuple[Response, dict]:
        model = _extract_model(body)
        telemetry = {
            "client_key_id": client_key_id,
            "upstream_key_id": None,
            "method": method,
            "path": "/" + path.lstrip("/"),
            "model": model,
            "status": 200,
            "latency_ms": 0,
            "stream": True,
            "prompt_tokens": None,
            "completion_tokens": None,
            # recorded by the route after the stream finishes (BackgroundTask)
            "_deferred_telemetry": True,
        }

        async def gen():
            yield b": ping\n\n"  # flush headers before the upstream fetch
            stream = None
            used_key = None
            try:
                async for item in iter_keepalive(
                    one_shot(self._forward(method, url, forward_headers, body, keys))
                ):
                    if isinstance(item, str):
                        yield item.encode("utf-8")
                        continue
                    stream, used_key = item

                status = stream.status
                if used_key:
                    await self._repo.record_upstream_result(used_key["id"], status)
                telemetry["upstream_key_id"] = used_key["id"] if used_key else None
                telemetry["status"] = status
                telemetry["latency_ms"] = round((time.perf_counter() - t0) * 1000)

                ctype = stream.headers.get("content-type", "")
                if status >= 400 or "text/event-stream" not in ctype:
                    # Headers are already sent; surface the upstream body in-band.
                    content = b"".join([c async for c in stream.aiter_bytes()])
                    if status >= 400:
                        err = {"error": {
                            "message": content[:500].decode("utf-8", "replace"),
                            "type": "api_error", "code": status,
                        }}
                        yield f"data: {json.dumps(err)}\n\n".encode()
                        yield b"data: [DONE]\n\n"
                    else:
                        yield content
                    return

                async for item in iter_keepalive(stream.aiter_bytes()):
                    if isinstance(item, str):
                        yield item.encode("utf-8")
                    else:
                        yield item
            except UpstreamUnavailable as exc:
                telemetry["status"] = 503
                err = {"error": {"message": str(exc), "type": "api_error", "code": 503}}
                yield f"data: {json.dumps(err)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            finally:
                if stream is not None:
                    await stream.aclose()

        response = StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"x-accel-buffering": "no", "cache-control": "no-cache"},
        )
        return response, telemetry


def _is_stream_request(body: bytes) -> bool:
    if not body or len(body) > _MAX_PARSE_BYTES:
        return False
    try:
        return json.loads(body).get("stream") is True
    except (ValueError, AttributeError):
        return False


def _extract_model(body: bytes) -> str | None:
    if not body or len(body) > _MAX_PARSE_BYTES:
        return None
    try:
        data = json.loads(body)
        model = data.get("model")
        return model if isinstance(model, str) else None
    except (ValueError, AttributeError):
        return None


def _extract_usage(content: bytes) -> tuple[int | None, int | None]:
    if not content or len(content) > _MAX_PARSE_BYTES:
        return None, None
    try:
        usage = json.loads(content).get("usage") or {}
        return usage.get("prompt_tokens"), usage.get("completion_tokens")
    except (ValueError, AttributeError):
        return None, None
