"""First-run wizard: ownership-gated init, permanent lock, password login + session."""

from tests.conftest import FakeHttp

INIT = {"nvidia_key": "nvapi-" + "x" * 30, "admin_password": "secret123", "client_key_name": "c1"}


def test_setup_full_flow(make_app):
    from fastapi.testclient import TestClient

    app = make_app(admin="")
    with TestClient(app) as c:
        app.state.http = FakeHttp()  # default 200 -> NVIDIA key validates

        assert c.get("/api/v1/setup/status").json()["configured"] is False

        init = c.post("/api/v1/setup/init", json=INIT)
        assert init.status_code == 200
        assert init.json()["client_secret"].startswith("sk-")

        assert c.get("/api/v1/setup/status").json()["configured"] is True
        # setup permanently locked
        assert c.post("/api/v1/setup/init", json=INIT).status_code == 409

        # password login issues a session token usable on admin endpoints
        login = c.post("/api/v1/auth/login", json={"password": "secret123"})
        assert login.status_code == 200
        token = login.json()["token"]
        keys = c.get("/api/v1/admin/upstream-keys", headers={"Authorization": f"Bearer {token}"})
        assert keys.status_code == 200
        assert len(keys.json()) == 1  # the NVIDIA key added by the wizard

        assert c.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 401


def test_setup_rejects_invalid_nvidia_key(make_app):
    from fastapi.testclient import TestClient

    app = make_app(admin="")
    with TestClient(app) as c:
        fake = FakeHttp()
        fake.queue(401, {"content-type": "application/json"}, b'{"error":"bad key"}')
        app.state.http = fake
        r = c.post("/api/v1/setup/init", json=INIT)
        assert r.status_code == 422
        assert c.get("/api/v1/setup/status").json()["configured"] is False


def test_setup_locked_when_env_token_set(make_app):
    from fastapi.testclient import TestClient

    app = make_app(admin="env-token")
    with TestClient(app) as c:
        assert c.get("/api/v1/setup/status").json()["configured"] is True
        assert c.post("/api/v1/setup/init", json=INIT).status_code == 409
