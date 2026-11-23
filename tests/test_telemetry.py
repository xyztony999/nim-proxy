"""Telemetry: request logs, usage aggregation, dashboard."""

import asyncio
from datetime import datetime, timezone

from tests.conftest import AUTH


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_logs_and_usage(client):
    repo = client.app.state.repo

    async def seed():
        for status in (200, 429, 500):
            await repo.insert_request_log(
                {
                    "ts": _ts(), "method": "POST", "path": "/v1/chat/completions",
                    "model": "m1", "status": status, "latency_ms": 10, "stream": False,
                    "prompt_tokens": 5, "completion_tokens": 7,
                }
            )

    asyncio.run(seed())

    logs = client.get("/api/v1/admin/request-logs", headers=AUTH).json()
    assert logs["total"] == 3
    assert len(logs["records"]) == 3

    filtered = client.get("/api/v1/admin/request-logs?status=429", headers=AUTH).json()
    assert filtered["total"] == 1

    usage = client.get(
        "/api/v1/admin/usage?dimension_type=status&bucket_type=day", headers=AUTH
    ).json()
    assert sum(u["requests"] for u in usage) == 3
    assert sum(u["rate_limited"] for u in usage) == 1
    assert sum(u["errors"] for u in usage) == 2


def test_dashboard(client):
    dash = client.get("/api/v1/admin/dashboard", headers=AUTH).json()
    assert dash["status"] == "ok"
    assert dash["auth_mode"] == "relay_only"  # no client keys seeded
    assert "today" in dash


def test_config_view(client):
    cfg = client.get("/api/v1/admin/config", headers=AUTH).json()
    assert cfg["db_backend"] == "sqlite"
    assert cfg["upstream"].startswith("https://")
