"""Key schemas (Ao = request input, Vo = response output)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class UpstreamKeySaveAo(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    secret: str = Field(min_length=20, max_length=512)

    @field_validator("secret")
    @classmethod
    def _nvapi_prefix(cls, v: str) -> str:
        if not v.startswith("nvapi-"):
            raise ValueError("secret must start with 'nvapi-'")
        return v


class UpstreamKeyVo(BaseModel):
    id: str
    label: str
    secret_masked: str
    enabled: bool
    created_at: str
    updated_at: str
    last_used_at: str | None = None
    last_error_status: int | None = None
    consecutive_failures: int = 0


class UpstreamKeyCreatedVo(UpstreamKeyVo):
    secret: str  # full value, returned only once at creation


class ClientKeySaveAo(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class ClientKeyVo(BaseModel):
    id: str
    name: str
    secret_masked: str
    enabled: bool
    created_at: str
    updated_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None


class ClientKeyCreatedVo(ClientKeyVo):
    secret: str  # full value, returned only once at creation
