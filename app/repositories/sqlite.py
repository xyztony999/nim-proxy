"""SQLite repository (server target). Sync sqlite3 wrapped in a threadpool."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starlette.concurrency import run_in_threadpool

_MIGRATIONS = Path(__file__).parent / "migrations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def open_database(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class SqliteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    # ---- internals (sync, run under lock in threadpool) ----

    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _row(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            r = self._conn.execute(sql, params).fetchone()
            return dict(r) if r else None

    def _exec(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(sql, params)

    def _migrate(self) -> None:
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                r["name"] for r in self._conn.execute("SELECT name FROM schema_migrations")
            }
            for script in sorted(_MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
                if script.name in applied:
                    continue
                self._conn.executescript(script.read_text(encoding="utf-8"))
                self._conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (script.name, _now()),
                )
                self._conn.commit()

    def _seed_keys(self, nvidia_keys: list[str], proxy_keys: list[str]) -> None:
        with self._lock:
            with self._conn:
                if not self._conn.execute("SELECT 1 FROM np_upstream_key LIMIT 1").fetchone():
                    for i, secret in enumerate(nvidia_keys):
                        ts = _now()
                        self._conn.execute(
                            "INSERT INTO np_upstream_key "
                            "(id,label,secret,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                            (_new_id(), f"upstream-{i + 1}", secret, 1, ts, ts),
                        )
                if not self._conn.execute("SELECT 1 FROM np_client_key LIMIT 1").fetchone():
                    for i, secret in enumerate(proxy_keys):
                        ts = _now()
                        self._conn.execute(
                            "INSERT INTO np_client_key "
                            "(id,name,secret,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                            (_new_id(), f"client-{i + 1}", secret, 1, ts, ts),
                        )

    # ---- upstream keys ----

    def _list_upstream(self) -> list[dict]:
        return self._rows("SELECT * FROM np_upstream_key ORDER BY created_at")

    def _get_upstream(self, kid: str) -> dict | None:
        return self._row("SELECT * FROM np_upstream_key WHERE id=?", (kid,))

    def _create_upstream(self, label: str, secret: str) -> dict:
        kid, ts = _new_id(), _now()
        self._exec(
            "INSERT INTO np_upstream_key "
            "(id,label,secret,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (kid, label, secret, 1, ts, ts),
        )
        return self._get_upstream(kid)  # type: ignore[return-value]

    def _delete_upstream(self, kid: str) -> bool:
        with self._lock:
            with self._conn:
                cur = self._conn.execute("DELETE FROM np_upstream_key WHERE id=?", (kid,))
                return cur.rowcount > 0

    def _set_upstream_enabled(self, kid: str, enabled: bool) -> dict | None:
        if not self._get_upstream(kid):
            return None
        self._exec(
            "UPDATE np_upstream_key SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, _now(), kid),
        )
        return self._get_upstream(kid)

    def _list_enabled_upstream(self) -> list[dict]:
        return self._rows("SELECT * FROM np_upstream_key WHERE enabled=1 ORDER BY created_at")

    def _record_upstream_result(self, kid: str, status: int) -> None:
        row = self._get_upstream(kid)
        if not row:
            return
        failures = 0 if status < 400 else row["consecutive_failures"] + 1
        self._exec(
            "UPDATE np_upstream_key SET last_used_at=?, last_error_status=?, "
            "consecutive_failures=?, updated_at=? WHERE id=?",
            (_now(), status if status >= 400 else None, failures, _now(), kid),
        )

    # ---- client keys ----

    def _list_client(self) -> list[dict]:
        return self._rows("SELECT * FROM np_client_key ORDER BY created_at")

    def _get_client(self, kid: str) -> dict | None:
        return self._row("SELECT * FROM np_client_key WHERE id=?", (kid,))

    def _create_client(self, name: str, secret: str) -> dict:
        kid, ts = _new_id(), _now()
        self._exec(
            "INSERT INTO np_client_key "
            "(id,name,secret,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (kid, name, secret, 1, ts, ts),
        )
        return self._get_client(kid)  # type: ignore[return-value]

    def _revoke_client(self, kid: str) -> bool:
        row = self._get_client(kid)
        if not row or row["revoked_at"]:
            return False
        self._exec(
            "UPDATE np_client_key SET revoked_at=?, enabled=0, updated_at=? WHERE id=?",
            (_now(), _now(), kid),
        )
        return True

    def _set_client_enabled(self, kid: str, enabled: bool) -> dict | None:
        row = self._get_client(kid)
        if not row or row["revoked_at"]:
            return None
        self._exec(
            "UPDATE np_client_key SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, _now(), kid),
        )
        return self._get_client(kid)

    def _find_client_by_secret(self, secret: str) -> dict | None:
        return self._row(
            "SELECT * FROM np_client_key WHERE secret=? AND enabled=1 AND revoked_at IS NULL",
            (secret,),
        )

    def _record_client_used(self, kid: str) -> None:
        self._exec("UPDATE np_client_key SET last_used_at=? WHERE id=?", (_now(), kid))

    # ---- telemetry ----

    def _insert_log(self, row: dict) -> None:
        self._exec(
            "INSERT INTO np_request_log "
            "(id,ts,client_key_id,upstream_key_id,method,path,model,status,latency_ms,"
            "stream,prompt_tokens,completion_tokens) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                row.get("id") or _new_id(),
                row.get("ts") or _now(),
                row.get("client_key_id"),
                row.get("upstream_key_id"),
                row["method"],
                row["path"],
                row.get("model"),
                row["status"],
                row["latency_ms"],
                1 if row.get("stream") else 0,
                row.get("prompt_tokens"),
                row.get("completion_tokens"),
            ),
        )

    def _query_logs(
        self,
        client_key_id: str | None,
        model: str | None,
        status: int | None,
        start: str | None,
        end: str | None,
        page_num: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        where, params = [], []
        if client_key_id:
            where.append("client_key_id=?")
            params.append(client_key_id)
        if model:
            where.append("model LIKE ?")
            params.append(f"%{model}%")
        if status is not None:
            where.append("status=?")
            params.append(status)
        if start:
            where.append("ts>=?")
            params.append(start)
        if end:
            where.append("ts<=?")
            params.append(end)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._row(f"SELECT COUNT(*) AS n FROM np_request_log{clause}", tuple(params))["n"]  # type: ignore[index]
        offset = (page_num - 1) * page_size
        rows = self._rows(
            f"SELECT * FROM np_request_log{clause} ORDER BY ts DESC LIMIT ? OFFSET ?",
            tuple(params) + (page_size, offset),
        )
        return rows, int(total)

    def _query_usage(
        self, dimension_type: str, bucket_type: str, start: str | None, end: str | None
    ) -> list[dict]:
        bucket_expr = "substr(ts,1,13)" if bucket_type == "hour" else "substr(ts,1,10)"
        dim_expr = {
            "key": "COALESCE(client_key_id,'(none)')",
            "model": "COALESCE(model,'(unknown)')",
            "status": "CAST(status AS TEXT)",
        }[dimension_type]
        where, params = [], []
        if start:
            where.append("ts>=?")
            params.append(start)
        if end:
            where.append("ts<=?")
            params.append(end)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        return self._rows(
            f"SELECT {bucket_expr} AS bucket, '{bucket_type}' AS bucket_type, "
            f"'{dimension_type}' AS dimension_type, {dim_expr} AS dimension_value, "
            "COUNT(*) AS requests, SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END) AS errors, "
            "SUM(CASE WHEN status=429 THEN 1 ELSE 0 END) AS rate_limited, "
            "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens),0) AS completion_tokens "
            f"FROM np_request_log{clause} GROUP BY bucket, dimension_value ORDER BY bucket",
            tuple(params),
        )

    def _today_counts(self) -> dict:
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
        row = self._row(
            "SELECT COUNT(*) AS requests, SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END) AS errors, "
            "SUM(CASE WHEN status=429 THEN 1 ELSE 0 END) AS rate_limited "
            "FROM np_request_log WHERE ts>=?",
            (start,),
        )
        return {
            "requests": int(row["requests"] or 0),  # type: ignore[index]
            "errors": int(row["errors"] or 0),  # type: ignore[index]
            "rate_limited": int(row["rate_limited"] or 0),  # type: ignore[index]
        }

    def _purge(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock:
            with self._conn:
                cur = self._conn.execute("DELETE FROM np_request_log WHERE ts<?", (cutoff,))
                return cur.rowcount

    def _count_keys(self) -> dict:
        up = self._row("SELECT COUNT(*) AS n FROM np_upstream_key")["n"]  # type: ignore[index]
        cl = self._row("SELECT COUNT(*) AS n FROM np_client_key WHERE revoked_at IS NULL")["n"]  # type: ignore[index]
        return {"upstream": int(up), "client": int(cl)}

    # ---- async facade ----

    async def migrate(self) -> None:
        await run_in_threadpool(self._migrate)

    async def seed_keys(self, nvidia_keys: list[str], proxy_keys: list[str]) -> None:
        await run_in_threadpool(self._seed_keys, nvidia_keys, proxy_keys)

    async def list_upstream_keys(self) -> list[dict]:
        return await run_in_threadpool(self._list_upstream)

    async def get_upstream_key(self, kid: str) -> dict | None:
        return await run_in_threadpool(self._get_upstream, kid)

    async def create_upstream_key(self, label: str, secret: str) -> dict:
        return await run_in_threadpool(self._create_upstream, label, secret)

    async def delete_upstream_key(self, kid: str) -> bool:
        return await run_in_threadpool(self._delete_upstream, kid)

    async def set_upstream_enabled(self, kid: str, enabled: bool) -> dict | None:
        return await run_in_threadpool(self._set_upstream_enabled, kid, enabled)

    async def list_enabled_upstream_keys(self) -> list[dict]:
        return await run_in_threadpool(self._list_enabled_upstream)

    async def record_upstream_result(self, kid: str, status: int) -> None:
        await run_in_threadpool(self._record_upstream_result, kid, status)

    async def list_client_keys(self) -> list[dict]:
        return await run_in_threadpool(self._list_client)

    async def get_client_key(self, kid: str) -> dict | None:
        return await run_in_threadpool(self._get_client, kid)

    async def create_client_key(self, name: str, secret: str) -> dict:
        return await run_in_threadpool(self._create_client, name, secret)

    async def revoke_client_key(self, kid: str) -> bool:
        return await run_in_threadpool(self._revoke_client, kid)

    async def set_client_enabled(self, kid: str, enabled: bool) -> dict | None:
        return await run_in_threadpool(self._set_client_enabled, kid, enabled)

    async def find_client_key_by_secret(self, secret: str) -> dict | None:
        return await run_in_threadpool(self._find_client_by_secret, secret)

    async def record_client_used(self, kid: str) -> None:
        await run_in_threadpool(self._record_client_used, kid)

    async def insert_request_log(self, row: dict) -> None:
        await run_in_threadpool(self._insert_log, row)

    async def query_request_logs(self, **kw: object) -> tuple[list[dict], int]:
        return await run_in_threadpool(self._query_logs, **kw)  # type: ignore[arg-type]

    async def query_usage(
        self, dimension_type: str, bucket_type: str, start: str | None, end: str | None
    ) -> list[dict]:
        return await run_in_threadpool(self._query_usage, dimension_type, bucket_type, start, end)

    async def today_counts(self) -> dict:
        return await run_in_threadpool(self._today_counts)

    async def purge_old_logs(self, days: int) -> int:
        return await run_in_threadpool(self._purge, days)

    async def count_keys(self) -> dict:
        return await run_in_threadpool(self._count_keys)

    async def aclose(self) -> None:
        await run_in_threadpool(self._conn.close)
