-- D1 migration 002 (Workers target): first-run wizard admin credential + sessions.

CREATE TABLE IF NOT EXISTS np_admin_credential (
    id            TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS np_admin_session (
    token_hash TEXT PRIMARY KEY,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
