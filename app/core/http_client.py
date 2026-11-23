"""Outbound HTTP client interface (platform-agnostic).

Server implementation uses httpx; Workers implementation uses workers.fetch
(ADR-010: httpx's jsfetch transport hangs on POST-with-body on some isolates).
Services depend on this interface, never on a concrete HTTP library.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class HttpClientResponse:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""

    def header(self, name: str, default: str = "") -> str:
        lowered = name.lower()
        for k, v in self.headers.items():
            if k.lower() == lowered:
                return v
        return default


class StreamingResponse(Protocol):
    """An opened streaming response: status/headers ready, body iterated lazily."""

    @property
    def status(self) -> int: ...

    @property
    def headers(self) -> dict[str, str]: ...

    def aiter_bytes(self) -> AsyncIterator[bytes]: ...

    async def aclose(self) -> None: ...


class HttpClient(Protocol):
    async def request(
        self, method: str, url: str, *, headers: dict[str, str], content: bytes | None
    ) -> HttpClientResponse:
        """Buffered request/response."""
        ...

    async def stream(
        self, method: str, url: str, *, headers: dict[str, str], content: bytes | None
    ) -> StreamingResponse:
        """Open a streaming response (status/headers available on return)."""
        ...
