"""Telemetry service: request logs, usage aggregation, dashboard, config view."""

from __future__ import annotations

from app.core.config import Config
from app.repositories.base import Repository
from app.schemas.common import AuthMode, ConfigVo, DashboardVo, PageVo, TodayCounts
from app.schemas.telemetry import (
    RequestLogQueryAo,
    RequestLogVo,
    UsageQueryAo,
    UsageVo,
)


class TelemetryService:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    async def record(self, row: dict) -> None:
        await self._repo.insert_request_log(row)

    async def query_logs(self, ao: RequestLogQueryAo) -> PageVo[RequestLogVo]:
        rows, total = await self._repo.query_request_logs(
            client_key_id=ao.client_key_id,
            model=ao.model,
            status=ao.status,
            start=ao.start,
            end=ao.end,
            page_num=ao.page_num,
            page_size=ao.page_size,
        )
        client_names = {r["id"]: r["name"] for r in await self._repo.list_client_keys()}
        upstream_labels = {r["id"]: r["label"] for r in await self._repo.list_upstream_keys()}
        records = [
            RequestLogVo(
                id=r["id"],
                ts=r["ts"],
                client_key_id=r.get("client_key_id"),
                client_key_name=client_names.get(r.get("client_key_id")),
                upstream_key_id=r.get("upstream_key_id"),
                upstream_key_label=upstream_labels.get(r.get("upstream_key_id")),
                method=r["method"],
                path=r["path"],
                model=r.get("model"),
                status=r["status"],
                latency_ms=r["latency_ms"],
                stream=bool(r["stream"]),
                prompt_tokens=r.get("prompt_tokens"),
                completion_tokens=r.get("completion_tokens"),
            )
            for r in rows
        ]
        return PageVo(records=records, total=total, page_num=ao.page_num, page_size=ao.page_size)

    async def query_usage(self, ao: UsageQueryAo) -> list[UsageVo]:
        rows = await self._repo.query_usage(
            ao.dimension_type.value, ao.bucket_type.value, ao.start, ao.end
        )
        return [UsageVo(**r) for r in rows]

    async def dashboard(self, config: Config, auth_mode: AuthMode) -> DashboardVo:
        counts = await self._repo.count_keys()
        today = await self._repo.today_counts()
        return DashboardVo(
            status="ok",
            upstream=config.upstream,
            auth_mode=auth_mode,
            upstream_key_count=counts["upstream"],
            client_key_count=counts["client"],
            today=TodayCounts(**today),
        )

    def config_view(self, config: Config, auth_mode: AuthMode, backend: str) -> ConfigVo:
        return ConfigVo(
            upstream=config.upstream,
            connect_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
            auth_mode=auth_mode,
            port=config.port,
            db_backend=backend,
        )

    async def purge(self, days: int) -> int:
        return await self._repo.purge_old_logs(days)
