"""Shared SSE parsing: buffer bytes across chunks and yield complete chat chunks.

Upstream byte chunks do not align to SSE line boundaries; parsing each chunk
independently drops lines split across chunks. This buffers across chunks.

Also provides keepalive iteration: NIM's first byte can take >100s, which
trips Cloudflare's origin timeout (524) if nothing is sent to the client.
Streaming endpoints therefore send headers + initial events immediately and
emit SSE comments while waiting on the upstream.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

KEEPALIVE = ": keepalive\n\n"


async def one_shot(coro) -> AsyncIterator:
    """Wrap a single awaitable as a one-item async iterator."""
    yield await coro


async def retry_on_timeout(http, stream, *, method, url, headers, content):
    """NIM's own edge can return 524 when a free-tier instance is slow to first
    byte. One fresh attempt often lands on a faster instance; keepalives keep
    the client connection alive meanwhile. Bounded to a single retry.
    """
    if stream is not None and stream.status == 524:
        await stream.aclose()
        stream = await http.stream(method, url, headers=headers, content=content)
    return stream


async def iter_keepalive(aiter, interval: float = 15.0) -> AsyncIterator:
    """Yield items from aiter; yield KEEPALIVE whenever a wait exceeds interval.

    Keeps the client connection alive while the upstream is slow. Pending
    work is cancelled if the consumer closes the iterator (client disconnect).
    """
    it = aiter.__aiter__()
    task = None
    try:
        while True:
            task = asyncio.ensure_future(it.__anext__())
            while True:
                done, _ = await asyncio.wait({task}, timeout=interval)
                if done:
                    break
                yield KEEPALIVE
            try:
                item = task.result()
            except StopAsyncIteration:
                return
            yield item
    finally:
        if task is not None and not task.done():
            task.cancel()


async def iter_chat_chunks(stream) -> AsyncIterator[dict]:
    buffer = ""

    def parse(line: str) -> dict | None:
        line = line.strip()
        if not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data or data == "[DONE]":
            return None
        try:
            return json.loads(data)
        except ValueError:
            return None

    async for raw in stream.aiter_bytes():
        buffer += raw.decode("utf-8", "replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            chunk = parse(line)
            if chunk is not None:
                yield chunk
    leftover = parse(buffer)
    if leftover is not None:
        yield leftover
