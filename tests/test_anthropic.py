"""Anthropic <-> OpenAI translation and /v1/messages endpoint."""

import json

from app.services.anthropic import AnthropicStream, to_anthropic_message, to_openai_request
from tests.conftest import FakeHttp

OAI_RESP = {
    "id": "chatcmpl-1",
    "choices": [{"message": {"role": "assistant", "content": "你好"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


def test_request_translation():
    body = {
        "model": "claude-3-5-sonnet",
        "max_tokens": 100,
        "system": "你是助手",
        "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        "tools": [{"name": "get_weather", "description": "d", "input_schema": {"type": "object"}}],
        "tool_choice": {"type": "auto"},
    }
    oai = to_openai_request(body, "minimaxai/minimax-m3.1-flash")
    assert oai["model"] == "minimaxai/minimax-m3.1-flash"
    assert oai["messages"][0] == {"role": "system", "content": "你是助手"}
    assert oai["messages"][1] == {"role": "user", "content": "hi"}
    assert oai["tools"][0]["function"]["name"] == "get_weather"
    assert oai["tool_choice"] == "auto"


def test_request_tool_result_translation():
    body = {
        "model": "claude",
        "messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "f", "input": {"a": 1}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]},
        ],
    }
    oai = to_openai_request(body, "m")
    assert oai["messages"][0]["tool_calls"][0]["id"] == "t1"
    assert oai["messages"][1] == {"role": "tool", "tool_call_id": "t1", "content": "ok"}


def test_response_translation():
    msg = to_anthropic_message(OAI_RESP, "m")
    assert msg["type"] == "message"
    assert msg["content"][0] == {"type": "text", "text": "你好"}
    assert msg["stop_reason"] == "end_turn"
    assert msg["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_stream_translation():
    tr = AnthropicStream("m")
    events = []
    events += tr.feed({"choices": [{"delta": {"content": "你"}}]})
    events += tr.feed({"choices": [{"delta": {"content": "好"}, "finish_reason": "stop"}]})
    events += tr.finish()
    blob = "".join(events)
    assert "message_start" in blob
    assert "content_block_start" in blob
    assert "text_delta" in blob
    assert "message_stop" in blob
    assert '"stop_reason": "end_turn"' in blob


def test_endpoint_non_stream(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    with TestClient(app) as c:
        fake = FakeHttp()
        fake.queue(200, {"content-type": "application/json"}, json.dumps(OAI_RESP).encode())
        app.state.http = fake
        r = c.post(
            "/v1/messages",
            headers={"x-api-key": "sk-client", "anthropic-version": "2023-06-01"},
            json={"model": "claude-3-5-sonnet", "max_tokens": 100, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "message"
        assert data["content"][0]["text"] == "你好"
        assert data["usage"]["input_tokens"] == 10


def test_endpoint_stream(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    with TestClient(app) as c:
        fake = FakeHttp()
        sse = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        fake.queue(200, {"content-type": "text/event-stream"}, sse)
        app.state.http = fake
        r = c.post(
            "/v1/messages",
            headers={"x-api-key": "sk-client"},
            json={"model": "claude", "max_tokens": 50, "stream": True, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        assert "message_start" in r.text
        assert "message_stop" in r.text


def test_endpoint_requires_key(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    with TestClient(app) as c:
        app.state.http = FakeHttp()
        r = c.post("/v1/messages", json={"model": "claude", "max_tokens": 10, "messages": []})
        assert r.status_code == 401
