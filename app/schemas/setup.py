"""First-run setup and admin login schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SetupStatusVo(BaseModel):
    configured: bool
    upstream_key_count: int


class SetupInitAo(BaseModel):
    nvidia_key: str = Field(min_length=20, max_length=512)
    admin_password: str = Field(min_length=8, max_length=256)
    client_key_name: str | None = Field(default=None, max_length=128)

    @field_validator("nvidia_key")
    @classmethod
    def _nvapi_prefix(cls, v: str) -> str:
        if not v.startswith("nvapi-"):
            raise ValueError("nvidia_key must start with 'nvapi-'")
        return v


class SetupInitVo(BaseModel):
    ok: bool
    client_secret: str | None = None


class LoginAo(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class LoginVo(BaseModel):
    token: str
