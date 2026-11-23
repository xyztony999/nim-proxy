"""Workers outbound HTTP adapter (workers.fetch / pyfetch bridge, ADR-010)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.http_client import HttpClientResponse


def _to_py(value):
    convert = getattr(value, "to_py", None)
    return convert() if callable(convert) else value


class _WorkersStreaming:
    def __init__(self, resp) -> None:
        self._resp = resp
        self._reader = resp.body.getReader() if resp.body is not None else None

    @property
    def status(self) -> int:
        return int(self._resp.status)

    @property
    def headers(self) -> dict[str, str]:
        # JS fetch auto-decodes gzip/br; drop the stale content-encoding header.
        return {k: v for k, v in self._resp.headers.items() if k.lower() != "content-encoding"}

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        if self._reader is None:
            return
        while True:
            chunk = await self._reader.read()
            if chunk.done:
                break
            yield chunk.value.to_bytes()

    async def aclose(self) -> None:
        if self._reader is not None:
            try:
                self._reader.releaseLock()
            except Exception as e:  # noqa: BLE001 - lock may already be released
                import logging

                logging.getLogger("nim-proxy").debug("reader releaseLock: %r", e)


class WorkersFetchAdapter:
    async def request(
        self, method: str, url: str, *, headers: dict[str, str], content: bytes | None
    ) -> HttpClientResponse:
        from workers import fetch as cf_fetch

        # JS fetch rejects a body on GET/HEAD (even empty); pass None when empty.
        resp = await cf_fetch(url, method=method, headers=headers, body=content or None)
        data = await resp.bytes()
        return HttpClientResponse(
            status=int(resp.status),
            headers={k: v for k, v in resp.headers.items() if k.lower() != "content-encoding"},
            content=data,
        )

    async def stream(
        self, method: str, url: str, *, headers: dict[str, str], content: bytes | None
    ) -> _WorkersStreaming:
        from workers import fetch as cf_fetch

        resp = await cf_fetch(url, method=method, headers=headers, body=content or None)
        return _WorkersStreaming(resp)
