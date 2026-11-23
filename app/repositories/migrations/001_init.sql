-- 001_init.sql — NIM Proxy 管理台与遥测（服务器 SQLite 与 Workers D1 共用）
-- 主键 TEXT(32) uuid4().hex；时间 ISO 8601 UTC 文本。

CREATE TABLE IF NOT EXISTS np_upstream_key (
    id                   TEXT PRIMARY KEY,
    label                TEXT NOT NULL,
    secret               TEXT NOT NULL,
    enabled              INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    last_used_at         TEXT,
    last_error_status    INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS np_client_key (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    secret       TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at   TEXT
);

CREATE TABLE IF NOT EXISTS np_request_log (
    id                TEXT PRIMARY KEY,
    ts                TEXT NOT NULL,
    client_key_id     TEXT,
    upstream_key_id   TEXT,
    method            TEXT NOT NULL,
    path              TEXT NOT NULL,
    model             TEXT,
    status            INTEGER NOT NULL,
    latency_ms        INTEGER NOT NULL,
    stream            INTEGER NOT NULL DEFAULT 0,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER
);

CREATE INDEX IF NOT EXISTS idx_request_log_ts ON np_request_log (ts);
CREATE INDEX IF NOT EXISTS idx_request_log_status ON np_request_log (status);
CREATE INDEX IF NOT EXISTS idx_request_log_client ON np_request_log (client_key_id);

CREATE TABLE IF NOT EXISTS schema_migrations (
    name       TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
