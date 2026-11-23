"""Streaming reliability: headers sent before the upstream fetch, keepalive
comments while NIM is slow, and in-band error events instead of a reset.

These drive the service generators directly with stub repo/http so they are
independent of the database and the test client's event loop.
"""

import asyncio
import time

from app.services.anthropic import AnthropicService
from app.services.relay import RelayService
from app.services.responses import ResponsesService
from app.services.sse import KEEPALIVE, iter_keepalive
from tests.conftest import FakeHttp


class _StubRepo:
    async def record_upstream_result(self, *a, **k):
        pass


class _StubConfig:
    upstream = "https://nim.example"
    anthropic_model = "m"


_SSE = (
    b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
    b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    b'data: [DONE]\n\n'
)


def test_iter_keepalive_emits_comments_while_waiting():
    async def slow():
        await asyncio.sleep(0.05)
        yield 1
        await asyncio.sleep(0.05)
        yield 2

    async def run():
        return [x async for x in iter_keepalive(slow(), interval=0.01)]

    out = asyncio.run(run())
    assert KEEPALIVE in out
    assert 1 in out and 2 in out


def test_responses_stream_headers_before_upstream():
    fake = FakeHttp()
    fake.queue(200, {"content-type": "text/event-stream"}, _SSE)
    svc = ResponsesService(_StubRepo(), fake, _StubConfig())
    telemetry = {"status": 200, "upstream_key_id": None}

    async def run():
        gen = svc._stream({"model": "m", "stream": True}, "https://x/v1/chat/completions",
                          b"{}", [], telemetry)
        it = gen.__aiter__()
        first = await it.__anext__()
        assert "response.created" in first
        assert fake.calls == []  # upstream not contacted yet -> headers already flowing
        rest = [ev async for ev in it]
        assert any("response.completed" in e for e in rest)
        assert len(fake.calls) == 1
        assert telemetry["status"] == 200

    asyncio.run(run())


def test_responses_stream_upstream_error_is_in_band():
    fake = FakeHttp()
    fake.queue(500, {"content-type": "application/json"}, b'{"error":"boom"}')
    svc = ResponsesService(_StubRepo(), fake, _StubConfig())
    telemetry = {"status": 200, "upstream_key_id": None}

    async def run():
        gen = svc._stream({"model": "m", "stream": True}, "https://x/v1/chat/completions",
                          b"{}", [], telemetry)
        blob = "".join([ev async for ev in gen])
        assert "response.created" in blob
        assert "response.failed" in blob
        assert "boom" in blob
        assert telemetry["status"] == 500

    asyncio.run(run())


def test_anthropic_stream_headers_before_upstream():
    fake = FakeHttp()
    fake.queue(200, {"content-type": "text/event-stream"}, _SSE)
    svc = AnthropicService(_StubRepo(), fake, _StubConfig())
    telemetry = {"status": 200, "upstream_key_id": None}

    async def run():
        gen = svc._stream({"model": "m", "stream": True}, "https://x/v1/chat/completions",
                          b"{}", [], telemetry)
        it = gen.__aiter__()
        first = await it.__anext__()
        assert "message_start" in first
        assert fake.calls == []
        rest = [ev async for ev in it]
        assert any("message_stop" in e for e in rest)
        assert len(fake.calls) == 1

    asyncio.run(run())


def test_relay_lazy_stream_pings_first_and_defers_telemetry():
    fake = FakeHttp()
    fake.queue(200, {"content-type": "text/event-stream"}, _SSE)
    svc = RelayService(_StubRepo(), fake, _StubConfig())
    response, telemetry = svc._lazy_stream(
        "POST", "https://x/v1/chat/completions", {}, b'{"model":"m","stream":true}',
        [], None, "v1/chat/completions", time.perf_counter(),
    )
    assert telemetry["_deferred_telemetry"] is True

    async def run():
        it = response.body_iterator.__aiter__()
        first = await it.__anext__()
        assert first == b": ping\n\n"
        assert fake.calls == []  # headers flushed before upstream fetch
        rest = [chunk async for chunk in it]
        assert b"data: [DONE]" in b"".join(rest)
        assert len(fake.calls) == 1
        assert telemetry["status"] == 200

    asyncio.run(run())
