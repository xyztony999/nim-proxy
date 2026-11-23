"""Configuration loaded from environment (server) or Workers bindings (per request)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field


def env_value(env: Any, name: str, default: str = "") -> str:
    """Read a scalar from a mapping (server) or a Workers env object."""
    if isinstance(env, Mapping):
        value = env.get(name, default)
        return default if value is None else str(value)
    try:
        value = getattr(env, name)
    except AttributeError:
        return default
    if value is None:
        return default
    if isinstance(value, str):
        return value
    convert = getattr(value, "to_py", None)
    converted = convert() if callable(convert) else value
    return default if converted is None else str(converted)


def _split_keys(raw: str) -> list[str]:
    return [k.strip() for k in raw.split(",") if k.strip()]


class Config(BaseModel):
    """Runtime configuration; immutable once loaded."""

    model_config = {"frozen": True}

    upstream: str = "https://integrate.api.nvidia.com"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    connect_timeout: float = Field(default=15, gt=0)
    read_timeout: float = Field(default=600, gt=0)
    db_path: str = "data/nim-proxy.db"
    admin_token: str = ""
    nvidia_api_keys: list[str] = Field(default_factory=list)
    proxy_api_keys: list[str] = Field(default_factory=list)
    log_retention_days: int = Field(default=30, ge=1)


def build_config(env: Any) -> Config:
    """Build Config from an env source (os.environ or Workers scope env)."""
    return Config(
        upstream=env_value(env, "NIM_UPSTREAM", "https://integrate.api.nvidia.com").rstrip("/"),
        host=env_value(env, "HOST", "0.0.0.0"),
        port=int(env_value(env, "PORT", "8000") or "8000"),
        connect_timeout=float(env_value(env, "CONNECT_TIMEOUT", "15") or "15"),
        read_timeout=float(env_value(env, "READ_TIMEOUT", "600") or "600"),
        db_path=env_value(env, "DB_PATH", "data/nim-proxy.db"),
        admin_token=env_value(env, "ADMIN_TOKEN", ""),
        nvidia_api_keys=_split_keys(
            env_value(env, "NVIDIA_API_KEYS", "") or env_value(env, "NVIDIA_API_KEY", "")
        ),
        proxy_api_keys=_split_keys(
            env_value(env, "PROXY_API_KEYS", "") or env_value(env, "PROXY_API_KEY", "")
        ),
        log_retention_days=int(env_value(env, "LOG_RETENTION_DAYS", "30") or "30"),
    )


def server_env() -> Mapping[str, str]:
    return os.environ
