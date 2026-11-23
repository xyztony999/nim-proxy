"""Shared SSE parsing: buffer bytes across chunks and yield complete chat chunks.

Upstream byte chunks do not align to SSE line boundaries; parsing each chunk
independently drops lines split across chunks. This buffers across chunks.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator


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
