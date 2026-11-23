"""Shared schemas: enums, pagination, dashboard, config."""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class AuthMode(StrEnum):
    enforced = "enforced"
    relay_only = "relay_only"


class KeyStatus(StrEnum):
    enabled = "enabled"
    disabled = "disabled"


class ClientKeyStatus(StrEnum):
    enabled = "enabled"
    disabled = "disabled"
    revoked = "revoked"


class StreamMode(StrEnum):
    stream = "stream"
    non_stream = "non_stream"


class BucketType(StrEnum):
    hour = "hour"
    day = "day"


class DimensionType(StrEnum):
    key = "key"
    model = "model"
    status = "status"


class PageVo(BaseModel, Generic[T]):
    records: list[T]
    total: int
    page_num: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class TodayCounts(BaseModel):
    requests: int
    errors: int
    rate_limited: int


class DashboardVo(BaseModel):
    status: str
    upstream: str
    auth_mode: AuthMode
    upstream_key_count: int
    client_key_count: int
    today: TodayCounts


class ConfigVo(BaseModel):
    upstream: str
    connect_timeout: float
    read_timeout: float
    auth_mode: AuthMode
    port: int
    db_backend: str
