"""Telemetry schemas: request logs and usage aggregates (read-only)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import BucketType, DimensionType


class RequestLogQueryAo(BaseModel):
    client_key_id: str | None = None
    model: str | None = None
    status: int | None = None
    start: str | None = None
    end: str | None = None
    page_num: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class RequestLogVo(BaseModel):
    id: str
    ts: str
    client_key_id: str | None = None
    client_key_name: str | None = None
    upstream_key_id: str | None = None
    upstream_key_label: str | None = None
    method: str
    path: str
    model: str | None = None
    status: int
    latency_ms: int
    stream: bool
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class UsageQueryAo(BaseModel):
    dimension_type: DimensionType = DimensionType.key
    bucket_type: BucketType = BucketType.day
    start: str | None = None
    end: str | None = None


class UsageVo(BaseModel):
    bucket: str
    bucket_type: str
    dimension_type: str
    dimension_value: str
    requests: int
    errors: int
    rate_limited: int
    prompt_tokens: int
    completion_tokens: int
