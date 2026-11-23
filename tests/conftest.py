"""Shared test fixtures: fresh app with temp SQLite + fake outbound HTTP."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN = "test-admin"
AUTH = {"Authorization": f"Bearer {ADMIN}"}


class FakeStreaming:
    def __init__(self, status: int, headers: dict, content: bytes) -> None:
        self.status = status
        self.headers = headers
        self._content = content
        self.closed = False

    async def aiter_bytes(self):
        yield self._content

    async def aclose(self) -> None:
        self.closed = True


class FakeHttp:
    """Programmable outbound client; records calls for assertions."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.responses: list[FakeStreaming] = []
        self.default = FakeStreaming(200, {"content-type": "application/json"}, b'{"ok":true}')

    def queue(self, status: int, headers: dict, content: bytes) -> None:
        self.responses.append(FakeStreaming(status, headers, content))

    async def request(self, method, url, *, headers, content):
        from app.core.http_client import HttpClientResponse

        self.calls.append({"method": method, "url": url, "headers": headers})
        resp = self.responses.pop(0) if self.responses else self.default
        return HttpClientResponse(resp.status, resp.headers, resp._content)

    async def stream(self, method, url, *, headers, content):
        self.calls.append({"method": method, "url": url, "headers": headers})
        return self.responses.pop(0) if self.responses else self.default


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    def _make(nvidia: str = "", proxy: str = "", admin: str = ADMIN):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setenv("ADMIN_TOKEN", admin)
        monkeypatch.setenv("NVIDIA_API_KEYS", nvidia)
        monkeypatch.setenv("PROXY_API_KEYS", proxy)
        from app.main import create_app

        return create_app("server")

    return _make


@pytest.fixture
def client(make_app):
    app = make_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def relay_client(make_app):
    app = make_app(nvidia="nvapi-key1,nvapi-key2", proxy="sk-client")
    with TestClient(app) as c:
        fake = FakeHttp()
        app.state.http = fake  # set after lifespan wired the real adapter
        c.fake = fake  # type: ignore[attr-defined]
        yield c
