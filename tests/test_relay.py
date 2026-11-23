"""Relay: passthrough, client auth, key rotation/retry, SSE streaming."""


from tests.conftest import AUTH, FakeHttp


def test_relay_only_mode(make_app):
    from fastapi.testclient import TestClient

    app = make_app(nvidia="nvapi-key1", proxy="")
    with TestClient(app) as c:
        fake = FakeHttp()
        app.state.http = fake
        resp = c.get("/v1/models")
        assert resp.status_code == 200
        assert fake.calls[0]["url"].endswith("/v1/models")


def test_enforced_auth(relay_client):
    assert relay_client.get("/v1/models").status_code == 401
    wrong = relay_client.get("/v1/models", headers={"Authorization": "Bearer wrong"})
    assert wrong.status_code == 401
    ok = relay_client.get("/v1/models", headers={"Authorization": "Bearer sk-client"})
    assert ok.status_code == 200


def test_retry_rotates_key(relay_client):
    relay_client.fake.queue(429, {"content-type": "application/json"}, b'{"error":"rate"}')
    relay_client.fake.queue(200, {"content-type": "application/json"}, b'{"ok":true}')
    resp = relay_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-client"},
        json={"model": "m1", "messages": []},
    )
    assert resp.status_code == 200
    assert len(relay_client.fake.calls) == 2
    keys = [c["headers"].get("authorization") for c in relay_client.fake.calls]
    assert keys[0] != keys[1]  # rotated to a different upstream key


def test_sse_streaming(relay_client):
    sse = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
    relay_client.fake.queue(200, {"content-type": "text/event-stream"}, sse)
    resp = relay_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-client"},
        json={"model": "m1", "messages": [], "stream": True},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert b"data: [DONE]" in resp.content


def test_telemetry_records_model(relay_client):
    relay_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-client"},
        json={"model": "minimaxai/minimax-m3.1-flash", "messages": []},
    )
    logs = relay_client.get("/api/v1/admin/request-logs", headers=AUTH).json()
    assert logs["total"] >= 1
    assert logs["records"][0]["model"] == "minimaxai/minimax-m3.1-flash"


def test_health_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
