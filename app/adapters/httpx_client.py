"""Server outbound HTTP adapter (httpx)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.http_client import HttpClientResponse


class _HttpxStreaming:
    def __init__(self, client: httpx.AsyncClient, resp: httpx.Response) -> None:
        self._client = client
        self._resp = resp

    @property
    def status(self) -> int:
        return self._resp.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._resp.headers)

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        async for chunk in self._resp.aiter_raw():
            yield chunk

    async def aclose(self) -> None:
        await self._resp.aclose()
        await self._client.aclose()


class HttpxAdapter:
    def __init__(self, connect_timeout: float = 15, read_timeout: float = 600) -> None:
        self._timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=60, pool=60)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, follow_redirects=False)

    async def request(
        self, method: str, url: str, *, headers: dict[str, str], content: bytes | None
    ) -> HttpClientResponse:
        async with self._client() as client:
            resp = await client.request(method, url, headers=headers, content=content)
            return HttpClientResponse(
                status=resp.status_code, headers=dict(resp.headers), content=resp.content
            )

    async def stream(
        self, method: str, url: str, *, headers: dict[str, str], content: bytes | None
    ) -> _HttpxStreaming:
        client = self._client()
        req = client.build_request(method, url, headers=headers, content=content)
        resp = await client.send(req, stream=True)
        return _HttpxStreaming(client, resp)
