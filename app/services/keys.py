"""Key governance service (platform-agnostic)."""

from __future__ import annotations

import secrets as _secrets

from app.core.errors import Conflict, InvalidInput, NotFound
from app.core.security import mask_secret
from app.repositories.base import Repository
from app.schemas.keys import (
    ClientKeyCreatedVo,
    ClientKeySaveAo,
    ClientKeyVo,
    UpstreamKeyCreatedVo,
    UpstreamKeySaveAo,
    UpstreamKeyVo,
)


def _upstream_vo(row: dict) -> UpstreamKeyVo:
    return UpstreamKeyVo(
        id=row["id"],
        label=row["label"],
        secret_masked=mask_secret(row["secret"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_used_at=row.get("last_used_at"),
        last_error_status=row.get("last_error_status"),
        consecutive_failures=row.get("consecutive_failures", 0),
    )


def _client_vo(row: dict) -> ClientKeyVo:
    return ClientKeyVo(
        id=row["id"],
        name=row["name"],
        secret_masked=mask_secret(row["secret"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_used_at=row.get("last_used_at"),
        revoked_at=row.get("revoked_at"),
    )


class KeyService:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    # upstream
    async def list_upstream(self) -> list[UpstreamKeyVo]:
        return [_upstream_vo(r) for r in await self._repo.list_upstream_keys()]

    async def create_upstream(self, ao: UpstreamKeySaveAo) -> UpstreamKeyCreatedVo:
        row = await self._repo.create_upstream_key(ao.label, ao.secret)
        vo = _upstream_vo(row)
        return UpstreamKeyCreatedVo(**vo.model_dump(), secret=row["secret"])

    async def get_upstream(self, kid: str) -> UpstreamKeyVo:
        row = await self._repo.get_upstream_key(kid)
        if not row:
            raise NotFound("上游密钥不存在")
        return _upstream_vo(row)

    async def delete_upstream(self, kid: str) -> None:
        if not await self._repo.delete_upstream_key(kid):
            raise NotFound("上游密钥不存在")

    async def set_upstream_enabled(self, kid: str, enabled: bool) -> UpstreamKeyVo:
        row = await self._repo.set_upstream_enabled(kid, enabled)
        if not row:
            raise NotFound("上游密钥不存在")
        return _upstream_vo(row)

    # client
    async def list_client(self) -> list[ClientKeyVo]:
        # Revoked keys are terminal and kept only for audit/log attribution; hide them here.
        rows = await self._repo.list_client_keys()
        return [_client_vo(r) for r in rows if not r.get("revoked_at")]

    async def create_client(self, ao: ClientKeySaveAo) -> ClientKeyCreatedVo:
        secret = "sk-" + _secrets.token_urlsafe(32)
        row = await self._repo.create_client_key(ao.name, secret)
        vo = _client_vo(row)
        return ClientKeyCreatedVo(**vo.model_dump(), secret=secret)

    async def get_client(self, kid: str) -> ClientKeyVo:
        row = await self._repo.get_client_key(kid)
        if not row:
            raise NotFound("客户端密钥不存在")
        return _client_vo(row)

    async def revoke_client(self, kid: str) -> None:
        row = await self._repo.get_client_key(kid)
        if not row:
            raise NotFound("客户端密钥不存在")
        if row.get("revoked_at"):
            raise Conflict("密钥已撤销")
        await self._repo.revoke_client_key(kid)

    async def set_client_enabled(self, kid: str, enabled: bool) -> ClientKeyVo:
        row = await self._repo.get_client_key(kid)
        if not row:
            raise NotFound("客户端密钥不存在")
        if row.get("revoked_at"):
            raise Conflict("已撤销的密钥不可启停")
        updated = await self._repo.set_client_enabled(kid, enabled)
        if not updated:
            raise InvalidInput("密钥状态更新失败")
        return _client_vo(updated)
