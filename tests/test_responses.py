"""OpenAI Responses <-> chat translation and /v1/responses endpoint."""

import json

from app.services.responses import ResponsesStream, to_chat_request, to_responses_object
from tests.conftest import FakeHttp

CHAT_RESP = {
    "id": "chatcmpl-1",
    "choices": [{"message": {"role": "assistant", "content": "Blue"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


def test_request_translation_string_input():
    body = {"model": "gpt-5", "instructions": "sys", "input": "hi", "max_output_tokens": 50}
    chat = to_chat_request(body, "minimaxai/minimax-m3.1-flash")
    assert chat["model"] == "minimaxai/minimax-m3.1-flash"
    assert chat["messages"][0] == {"role": "system", "content": "sys"}
    assert chat["messages"][1] == {"role": "user", "content": "hi"}
    assert chat["max_tokens"] == 50


def test_request_translation_items_and_tools():
    body = {
        "model": "gpt-5",
        "input": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
            {"type": "function_call", "call_id": "c1", "name": "f", "arguments": '{"a":1}'},
            {"type": "function_call_output", "call_id": "c1", "output": "ok"},
        ],
        "tools": [{"type": "function", "name": "f", "parameters": {"type": "object"}}],
    }
    chat = to_chat_request(body, "m")
    assert chat["messages"][0] == {"role": "user", "content": "hi"}
    assert chat["messages"][1]["tool_calls"][0]["id"] == "c1"
    assert chat["messages"][2] == {"role": "tool", "tool_call_id": "c1", "content": "ok"}
    assert chat["tools"][0]["function"]["name"] == "f"


def test_request_translation_null_fields_coerced():
    # NIM rejects null where a string is expected (tool content / arguments).
    body = {
        "model": "gpt-5",
        "input": [
            {"type": "message", "role": "user", "content": "hi"},
            {"type": "function_call", "call_id": "c1", "name": "f", "arguments": None},
            {"type": "function_call_output", "call_id": "c1", "output": None},
        ],
    }
    chat = to_chat_request(body, "m")
    asst = next(m for m in chat["messages"] if m.get("role") == "assistant")
    assert asst["content"] == ""  # not None
    assert asst["tool_calls"][0]["function"]["arguments"] == "{}"
    tool = next(m for m in chat["messages"] if m.get("role") == "tool")
    assert tool["content"] == ""  # not None


def test_request_translation_namespace_expanded():
    body = {
        "model": "gpt-5",
        "input": "hi",
        "tools": [
            {"type": "function", "name": "exec_command", "parameters": {"type": "object"}},
            {"type": "namespace", "name": "mcp__node_repl", "tools": [
                {"type": "function", "name": "js", "parameters": {"type": "object"}},
            ]},
        ],
    }
    chat = to_chat_request(body, "m")
    names = [t["function"]["name"] for t in chat["tools"]]
    assert "exec_command" in names
    assert "js" in names  # namespace member expanded


def test_request_translation_custom_tool_wrapped():
    body = {
        "model": "gpt-5", "input": "hi",
        "tools": [{"type": "custom", "name": "apply_patch", "description": "edit files",
                   "format": {"type": "grammar"}}],
    }
    chat = to_chat_request(body, "m")
    fn = chat["tools"][0]["function"]
    assert fn["name"] == "apply_patch"
    assert "input" in fn["parameters"]["properties"]


def test_stream_custom_tool_call_translation():
    tr = ResponsesStream("m", custom_names={"apply_patch"})
    events = []
    events += tr.feed({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "c1", "function": {"name": "apply_patch", "arguments": '{"input":'
                                              '"*** Begin Patch*** End Patch"}'}}]}}]})
    events += tr.finish()
    blob = "".join(events)
    assert '"type": "custom_tool_call"' in blob
    assert "response.custom_tool_call_input.delta" in blob
    assert "*** Begin Patch*** End Patch" in blob
    assert '"type": "function_call"' not in blob


def test_response_translation():
    obj = to_responses_object(CHAT_RESP, "m")
    assert obj["object"] == "response"
    assert obj["status"] == "completed"
    assert obj["output"][0]["content"][0]["text"] == "Blue"
    assert obj["usage"]["input_tokens"] == 10


def test_stream_translation():
    tr = ResponsesStream("m")
    events = []
    events += tr.feed({"choices": [{"delta": {"content": "Bl"}}]})
    events += tr.feed({"choices": [{"delta": {"content": "ue"}, "finish_reason": "stop"}]})
    events += tr.finish()
    blob = "".join(events)
    assert "response.created" in blob
    assert "response.output_text.delta" in blob
    assert "response.completed" in blob


def test_stream_reasoning_translation():
    tr = ResponsesStream("m")
    events = []
    events += tr.feed({"choices": [{"delta": {"reasoning_content": "thinking hard"}}]})
    events += tr.feed({"choices": [{"delta": {"content": "Answer"}, "finish_reason": "stop"}]})
    events += tr.finish()
    blob = "".join(events)
    assert "response.reasoning_summary_text.delta" in blob
    assert "response.reasoning_summary_text.done" in blob
    assert "response.output_text.delta" in blob
    assert "response.completed" in blob
    # reasoning item is emitted before the answer text
    assert blob.index("reasoning_summary_text.delta") < blob.index("output_text.delta")


def test_endpoint_non_stream(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    with TestClient(app) as c:
        fake = FakeHttp()
        fake.queue(200, {"content-type": "application/json"}, json.dumps(CHAT_RESP).encode())
        app.state.http = fake
        r = c.post("/v1/responses", headers={"Authorization": "Bearer sk-client"},
                   json={"model": "gpt-5", "input": "hi"})
        assert r.status_code == 200
        assert r.json()["object"] == "response"
        assert r.json()["output"][0]["content"][0]["text"] == "Blue"


def test_endpoint_stream(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    with TestClient(app) as c:
        fake = FakeHttp()
        sse = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        fake.queue(200, {"content-type": "text/event-stream"}, sse)
        app.state.http = fake
        r = c.post("/v1/responses", headers={"Authorization": "Bearer sk-client"},
                   json={"model": "gpt-5", "input": "hi", "stream": True})
        assert r.status_code == 200
        assert "response.completed" in r.text


class _SplitStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self.status = 200
        self.headers = {"content-type": "text/event-stream"}

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c

    async def aclose(self):
        pass


class _SplitHttp:
    def __init__(self, chunks):
        self._chunks = chunks

    async def stream(self, *a, **k):
        return _SplitStream(self._chunks)


def test_stream_split_chunk_boundaries(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    sse = (
        b'data: {"choices":[{"delta":{"content":"Blue"}}]}\n\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        b'data: [DONE]\n\n'
    )
    # split mid-line across chunks to exercise the line buffer
    chunks = [sse[:25], sse[25:60], sse[60:]]
    with TestClient(app) as c:
        app.state.http = _SplitHttp(chunks)
        r = c.post("/v1/responses", headers={"Authorization": "Bearer sk-client"},
                   json={"model": "gpt-5", "input": "hi", "stream": True})
        assert r.status_code == 200
        assert "response.output_text.delta" in r.text
        assert "Blue" in r.text


def test_endpoint_requires_key(make_app):
    from fastapi.testclient import TestClient

    app = make_app(proxy="sk-client")
    with TestClient(app) as c:
        app.state.http = FakeHttp()
        r = c.post("/v1/responses", json={"model": "gpt-5", "input": "hi"})
        assert r.status_code == 401
