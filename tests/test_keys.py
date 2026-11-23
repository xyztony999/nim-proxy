"""Key governance: full CRUD chain + lifecycle + validation (GR-03)."""

from tests.conftest import AUTH


def test_upstream_full_chain(client):
    created = client.post(
        "/api/v1/admin/upstream-keys",
        json={"label": "k1", "secret": "nvapi-" + "x" * 30},
        headers=AUTH,
    )
    assert created.status_code == 201
    body = created.json()
    kid = body["id"]
    assert body["secret"].startswith("nvapi-")  # full value once
    assert body["secret_masked"].startswith("****")

    listed = client.get("/api/v1/admin/upstream-keys", headers=AUTH)
    assert listed.status_code == 200
    assert any(r["id"] == kid for r in listed.json())
    assert all("secret" not in r for r in listed.json())  # masked list

    detail = client.get(f"/api/v1/admin/upstream-keys/{kid}", headers=AUTH)
    assert detail.status_code == 200

    disabled = client.post(f"/api/v1/admin/upstream-keys/{kid}/disable", headers=AUTH)
    assert disabled.json()["enabled"] is False
    enabled = client.post(f"/api/v1/admin/upstream-keys/{kid}/enable", headers=AUTH)
    assert enabled.json()["enabled"] is True

    deleted = client.delete(f"/api/v1/admin/upstream-keys/{kid}", headers=AUTH)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/admin/upstream-keys/{kid}", headers=AUTH).status_code == 404


def test_upstream_validation(client):
    bad = client.post(
        "/api/v1/admin/upstream-keys",
        json={"label": "k", "secret": "not-nvapi"},
        headers=AUTH,
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


def test_client_full_chain(client):
    created = client.post("/api/v1/admin/client-keys", json={"name": "c1"}, headers=AUTH)
    assert created.status_code == 201
    kid = created.json()["id"]
    assert created.json()["secret"].startswith("sk-")

    disabled = client.post(f"/api/v1/admin/client-keys/{kid}/disable", headers=AUTH)
    assert disabled.json()["enabled"] is False
    enabled = client.post(f"/api/v1/admin/client-keys/{kid}/enable", headers=AUTH)
    assert enabled.json()["enabled"] is True

    assert client.delete(f"/api/v1/admin/client-keys/{kid}", headers=AUTH).status_code == 204
    # revoked is terminal: enable conflicts
    conflict = client.post(f"/api/v1/admin/client-keys/{kid}/enable", headers=AUTH)
    assert conflict.status_code == 409


def test_admin_requires_token(client):
    assert client.get("/api/v1/admin/upstream-keys").status_code == 401
    assert client.get(
        "/api/v1/admin/upstream-keys", headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_admin_disabled_without_token(make_app):
    from fastapi.testclient import TestClient

    app = make_app(admin="")
    with TestClient(app) as c:
        resp = c.get("/api/v1/admin/upstream-keys", headers=AUTH)
        assert resp.status_code == 403
