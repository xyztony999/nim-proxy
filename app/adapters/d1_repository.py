"""D1 repository (Workers target). Native async; shares SQL semantics with SQLite."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

# Schema is managed by wrangler d1 migrations (workers/migrations/*.sql).


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _to_py(value):
    convert = getattr(value, "to_py", None)
    return convert() if callable(convert) else value


class D1Repository:
    def __init__(self, db) -> None:
        self._db = db
        self._ready = False

    async def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = _to_py(await stmt.all())
        return list(result.get("results", []))

    async def _first(self, sql: str, params: tuple = ()) -> dict | None:
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        row = _to_py(await stmt.first())
        return dict(row) if row else None

    async def _run(self, sql: str, params: tuple = ()) -> None:
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        await stmt.run()

    async def migrate(self) -> None:
        # Schema is managed by `wrangler d1 migrations apply` (CI runs it before
        # deploy). D1 .exec() splits on newlines and cannot run multi-line DDL,
        # so runtime migration is intentionally a no-op here.
        self._ready = True

    async def seed_keys(self, nvidia_keys: list[str], proxy_keys: list[str]) -> None:
        await self.migrate()
        if not await self._first("SELECT 1 AS x FROM np_upstream_key LIMIT 1"):
            for i, secret in enumerate(nvidia_keys):
                ts = _now()
                await self._run(
                    "INSERT INTO np_upstream_key (id,label,secret,enabled,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (_new_id(), f"upstream-{i + 1}", secret, 1, ts, ts),
                )
        if not await self._first("SELECT 1 AS x FROM np_client_key LIMIT 1"):
            for i, secret in enumerate(proxy_keys):
                ts = _now()
                await self._run(
                    "INSERT INTO np_client_key (id,name,secret,enabled,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (_new_id(), f"client-{i + 1}", secret, 1, ts, ts),
                )

    # upstream
    async def list_upstream_keys(self) -> list[dict]:
        await self.migrate()
        return await self._all("SELECT * FROM np_upstream_key ORDER BY created_at")

    async def get_upstream_key(self, kid: str) -> dict | None:
        return await self._first("SELECT * FROM np_upstream_key WHERE id=?", (kid,))

    async def create_upstream_key(self, label: str, secret: str) -> dict:
        kid, ts = _new_id(), _now()
        await self._run(
            "INSERT INTO np_upstream_key (id,label,secret,enabled,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (kid, label, secret, 1, ts, ts),
        )
        return await self.get_upstream_key(kid)  # type: ignore[return-value]

    async def delete_upstream_key(self, kid: str) -> bool:
        if not await self.get_upstream_key(kid):
            return False
        await self._run("DELETE FROM np_upstream_key WHERE id=?", (kid,))
        return True

    async def set_upstream_enabled(self, kid: str, enabled: bool) -> dict | None:
        if not await self.get_upstream_key(kid):
            return None
        await self._run(
            "UPDATE np_upstream_key SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, _now(), kid),
        )
        return await self.get_upstream_key(kid)

    async def list_enabled_upstream_keys(self) -> list[dict]:
        await self.migrate()
        return await self._all("SELECT * FROM np_upstream_key WHERE enabled=1 ORDER BY created_at")

    async def record_upstream_result(self, kid: str, status: int) -> None:
        row = await self.get_upstream_key(kid)
        if not row:
            return
        failures = 0 if status < 400 else row["consecutive_failures"] + 1
        await self._run(
            "UPDATE np_upstream_key SET last_used_at=?, last_error_status=?, "
            "consecutive_failures=?, updated_at=? WHERE id=?",
            (_now(), status if status >= 400 else None, failures, _now(), kid),
        )

    # client
    async def list_client_keys(self) -> list[dict]:
        await self.migrate()
        return await self._all("SELECT * FROM np_client_key ORDER BY created_at")

    async def get_client_key(self, kid: str) -> dict | None:
        return await self._first("SELECT * FROM np_client_key WHERE id=?", (kid,))

    async def create_client_key(self, name: str, secret: str) -> dict:
        kid, ts = _new_id(), _now()
        await self._run(
            "INSERT INTO np_client_key (id,name,secret,enabled,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (kid, name, secret, 1, ts, ts),
        )
        return await self.get_client_key(kid)  # type: ignore[return-value]

    async def revoke_client_key(self, kid: str) -> bool:
        row = await self.get_client_key(kid)
        if not row or row["revoked_at"]:
            return False
        await self._run(
            "UPDATE np_client_key SET revoked_at=?, enabled=0, updated_at=? WHERE id=?",
            (_now(), _now(), kid),
        )
        return True

    async def set_client_enabled(self, kid: str, enabled: bool) -> dict | None:
        row = await self.get_client_key(kid)
        if not row or row["revoked_at"]:
            return None
        await self._run(
            "UPDATE np_client_key SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, _now(), kid),
        )
        return await self.get_client_key(kid)

    async def find_client_key_by_secret(self, secret: str) -> dict | None:
        await self.migrate()
        return await self._first(
            "SELECT * FROM np_client_key WHERE secret=? AND enabled=1 AND revoked_at IS NULL",
            (secret,),
        )

    async def record_client_used(self, kid: str) -> None:
        await self._run("UPDATE np_client_key SET last_used_at=? WHERE id=?", (_now(), kid))

    # telemetry
    async def insert_request_log(self, row: dict) -> None:
        await self.migrate()
        await self._run(
            "INSERT INTO np_request_log (id,ts,client_key_id,upstream_key_id,method,path,"
            "model,status,latency_ms,stream,prompt_tokens,completion_tokens) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                row.get("id") or _new_id(), row.get("ts") or _now(), row.get("client_key_id"),
                row.get("upstream_key_id"), row["method"], row["path"], row.get("model"),
                row["status"], row["latency_ms"], 1 if row.get("stream") else 0,
                row.get("prompt_tokens"), row.get("completion_tokens"),
            ),
        )

    async def query_request_logs(self, **kw) -> tuple[list[dict], int]:
        await self.migrate()
        where, params = [], []
        for field, key in (("client_key_id", "client_key_id"), ("status", "status")):
            if kw.get(key) is not None:
                where.append(f"{field}=?")
                params.append(kw[key])
        if kw.get("model"):
            where.append("model LIKE ?")
            params.append(f"%{kw['model']}%")
        if kw.get("start"):
            where.append("ts>=?")
            params.append(kw["start"])
        if kw.get("end"):
            where.append("ts<=?")
            params.append(kw["end"])
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total_row = await self._first(
            f"SELECT COUNT(*) AS n FROM np_request_log{clause}", tuple(params)
        )
        total = int(total_row["n"])  # type: ignore[index]
        offset = (kw["page_num"] - 1) * kw["page_size"]
        rows = await self._all(
            f"SELECT * FROM np_request_log{clause} ORDER BY ts DESC LIMIT ? OFFSET ?",
            tuple(params) + (kw["page_size"], offset),
        )
        return rows, total

    async def query_usage(self, dimension_type, bucket_type, start, end) -> list[dict]:
        await self.migrate()
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
        return await self._all(
            f"SELECT {bucket_expr} AS bucket, '{bucket_type}' AS bucket_type, "
            f"'{dimension_type}' AS dimension_type, {dim_expr} AS dimension_value, "
            "COUNT(*) AS requests, SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END) AS errors, "
            "SUM(CASE WHEN status=429 THEN 1 ELSE 0 END) AS rate_limited, "
            "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens),0) AS completion_tokens "
            f"FROM np_request_log{clause} GROUP BY bucket, dimension_value ORDER BY bucket",
            tuple(params),
        )

    async def today_counts(self) -> dict:
        await self.migrate()
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
        row = await self._first(
            "SELECT COUNT(*) AS requests, "
            "SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END) AS errors, "
            "SUM(CASE WHEN status=429 THEN 1 ELSE 0 END) AS rate_limited "
            "FROM np_request_log WHERE ts>=?",
            (start,),
        )
        return {k: int(row[k] or 0) for k in ("requests", "errors", "rate_limited")}  # type: ignore[index]

    async def purge_old_logs(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await self._all("SELECT id FROM np_request_log WHERE ts<?", (cutoff,))
        await self._run("DELETE FROM np_request_log WHERE ts<?", (cutoff,))
        return len(rows)

    async def count_keys(self) -> dict:
        await self.migrate()
        up = await self._first("SELECT COUNT(*) AS n FROM np_upstream_key")
        cl = await self._first("SELECT COUNT(*) AS n FROM np_client_key WHERE revoked_at IS NULL")
        return {"upstream": int(up["n"]), "client": int(cl["n"])}  # type: ignore[index]

    async def get_admin_credential(self) -> dict | None:
        await self.migrate()
        return await self._first("SELECT * FROM np_admin_credential LIMIT 1")

    async def create_admin_credential(self, password_hash: str) -> dict:
        kid, ts = _new_id(), _now()
        await self._run(
            "INSERT INTO np_admin_credential (id,password_hash,created_at,updated_at) "
            "VALUES (?,?,?,?)",
            (kid, password_hash, ts, ts),
        )
        return await self.get_admin_credential()  # type: ignore[return-value]

    async def create_session(self, token_hash: str, expires_at: str) -> None:
        await self._run(
            "INSERT INTO np_admin_session (token_hash,expires_at,created_at) VALUES (?,?,?)",
            (token_hash, expires_at, _now()),
        )

    async def get_session(self, token_hash: str) -> dict | None:
        await self.migrate()
        return await self._first("SELECT * FROM np_admin_session WHERE token_hash=?", (token_hash,))

    async def aclose(self) -> None:
        return None
