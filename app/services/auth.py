"""Admin authentication and first-run setup (platform-agnostic).

Admin credential lives in the database (password hash); a legacy env ADMIN_TOKEN
is still accepted. Login issues a session token stored hashed in the database.
Setup is gated by NVIDIA-key ownership proof and locks permanently once configured.
"""

from __future__ import annotations

import secrets as _secrets
from datetime import datetime, timedelta, timezone

from app.core.config import Config
from app.core.errors import Conflict, InvalidInput, Unauthorized
from app.core.http_client import HttpClient
from app.core.security import (
    hash_password,
    hash_token,
    new_session_token,
    secrets_equal,
    verify_password,
)
from app.repositories.base import Repository
from app.schemas.setup import SetupInitAo

_SESSION_TTL_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, repo: Repository, config: Config) -> None:
        self._repo = repo
        self._config = config

    async def is_configured(self) -> bool:
        if self._config.admin_token:
            return True
        return await self._repo.get_admin_credential() is not None

    async def login(self, password: str) -> str:
        cred = await self._repo.get_admin_credential()
        if cred:
            if not verify_password(password, cred["password_hash"]):
                raise Unauthorized("密码错误")
        elif self._config.admin_token:
            if not secrets_equal(password, self._config.admin_token):
                raise Unauthorized("令牌错误")
        else:
            raise Conflict("尚未初始化，请先完成首次设置")
        token = new_session_token()
        expires = (_now() + timedelta(days=_SESSION_TTL_DAYS)).isoformat()
        await self._repo.create_session(hash_token(token), expires)
        return token

    async def verify_bearer(self, bearer: str | None) -> bool:
        if not bearer:
            return False
        if self._config.admin_token and secrets_equal(bearer, self._config.admin_token):
            return True
        session = await self._repo.get_session(hash_token(bearer))
        return bool(session and session["expires_at"] > _now().isoformat())


class SetupService:
    def __init__(self, repo: Repository, http: HttpClient, config: Config) -> None:
        self._repo = repo
        self._http = http
        self._config = config

    async def init(self, ao: SetupInitAo) -> dict:
        if await AuthService(self._repo, self._config).is_configured():
            raise Conflict("已完成初始化，设置入口已锁定")

        # Ownership proof: the NVIDIA key must authenticate against NIM.
        resp = await self._http.request(
            "GET",
            f"{self._config.upstream}/v1/models",
            headers={"Authorization": f"Bearer {ao.nvidia_key}"},
            content=None,
        )
        if resp.status != 200:
            raise InvalidInput("NVIDIA 密钥验证失败（上游返回非 200）")

        await self._repo.create_upstream_key("default", ao.nvidia_key)
        await self._repo.create_admin_credential(hash_password(ao.admin_password))

        client_secret = None
        if ao.client_key_name:
            client_secret = "sk-" + _secrets.token_urlsafe(32)
            await self._repo.create_client_key(ao.client_key_name, client_secret)
        return {"ok": True, "client_secret": client_secret}
