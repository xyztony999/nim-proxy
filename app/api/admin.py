"""Admin console REST API (Owner-guarded)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import (
    get_config,
    get_key_service,
    get_relay,
    get_telemetry,
    require_admin,
)
from app.core.config import Config
from app.schemas.common import ConfigVo, DashboardVo
from app.schemas.keys import (
    ClientKeyCreatedVo,
    ClientKeySaveAo,
    ClientKeyVo,
    UpstreamKeyCreatedVo,
    UpstreamKeySaveAo,
    UpstreamKeyVo,
)
from app.schemas.telemetry import (
    RequestLogQueryAo,
    UsageQueryAo,
    UsageVo,
)
from app.services.keys import KeyService
from app.services.relay import RelayService
from app.services.telemetry import TelemetryService

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


# ---- dashboard / config ----


@router.get("/dashboard", response_model=DashboardVo)
async def dashboard(
    config: Config = Depends(get_config),
    telemetry: TelemetryService = Depends(get_telemetry),
    relay: RelayService = Depends(get_relay),
) -> DashboardVo:
    return await telemetry.dashboard(config, await relay.auth_mode())


@router.get("/config", response_model=ConfigVo)
async def config_view(
    request: Request,
    config: Config = Depends(get_config),
    telemetry: TelemetryService = Depends(get_telemetry),
    relay: RelayService = Depends(get_relay),
) -> ConfigVo:
    backend = "d1" if getattr(request.app.state, "platform", "server") == "workers" else "sqlite"
    return telemetry.config_view(config, await relay.auth_mode(), backend)


# ---- upstream keys ----


@router.get("/upstream-keys", response_model=list[UpstreamKeyVo])
async def list_upstream(keys: KeyService = Depends(get_key_service)) -> list[UpstreamKeyVo]:
    return await keys.list_upstream()


@router.post("/upstream-keys", response_model=UpstreamKeyCreatedVo, status_code=201)
async def create_upstream(
    ao: UpstreamKeySaveAo, keys: KeyService = Depends(get_key_service)
) -> UpstreamKeyCreatedVo:
    return await keys.create_upstream(ao)


@router.get("/upstream-keys/{kid}", response_model=UpstreamKeyVo)
async def get_upstream(kid: str, keys: KeyService = Depends(get_key_service)) -> UpstreamKeyVo:
    return await keys.get_upstream(kid)


@router.delete("/upstream-keys/{kid}", status_code=204)
async def delete_upstream(kid: str, keys: KeyService = Depends(get_key_service)) -> Response:
    await keys.delete_upstream(kid)
    return Response(status_code=204)


@router.post("/upstream-keys/{kid}/enable", response_model=UpstreamKeyVo)
async def enable_upstream(kid: str, keys: KeyService = Depends(get_key_service)) -> UpstreamKeyVo:
    return await keys.set_upstream_enabled(kid, True)


@router.post("/upstream-keys/{kid}/disable", response_model=UpstreamKeyVo)
async def disable_upstream(kid: str, keys: KeyService = Depends(get_key_service)) -> UpstreamKeyVo:
    return await keys.set_upstream_enabled(kid, False)


# ---- client keys ----


@router.get("/client-keys", response_model=list[ClientKeyVo])
async def list_client(keys: KeyService = Depends(get_key_service)) -> list[ClientKeyVo]:
    return await keys.list_client()


@router.post("/client-keys", response_model=ClientKeyCreatedVo, status_code=201)
async def create_client(
    ao: ClientKeySaveAo, keys: KeyService = Depends(get_key_service)
) -> ClientKeyCreatedVo:
    return await keys.create_client(ao)


@router.get("/client-keys/{kid}", response_model=ClientKeyVo)
async def get_client(kid: str, keys: KeyService = Depends(get_key_service)) -> ClientKeyVo:
    return await keys.get_client(kid)


@router.delete("/client-keys/{kid}", status_code=204)
async def revoke_client(kid: str, keys: KeyService = Depends(get_key_service)) -> Response:
    await keys.revoke_client(kid)
    return Response(status_code=204)


@router.post("/client-keys/{kid}/enable", response_model=ClientKeyVo)
async def enable_client(kid: str, keys: KeyService = Depends(get_key_service)) -> ClientKeyVo:
    return await keys.set_client_enabled(kid, True)


@router.post("/client-keys/{kid}/disable", response_model=ClientKeyVo)
async def disable_client(kid: str, keys: KeyService = Depends(get_key_service)) -> ClientKeyVo:
    return await keys.set_client_enabled(kid, False)


# ---- telemetry ----


@router.get("/usage", response_model=list[UsageVo])
async def usage(
    ao: UsageQueryAo = Depends(), telemetry: TelemetryService = Depends(get_telemetry)
) -> list[UsageVo]:
    return await telemetry.query_usage(ao)


@router.get("/request-logs")
async def request_logs(
    client_key_id: str | None = None,
    model: str | None = None,
    status: int | None = None,
    start: str | None = None,
    end: str | None = None,
    page_num: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    telemetry: TelemetryService = Depends(get_telemetry),
) -> dict:
    ao = RequestLogQueryAo(
        client_key_id=client_key_id, model=model, status=status, start=start, end=end,
        page_num=page_num, page_size=page_size,
    )
    page = await telemetry.query_logs(ao)
    return page.model_dump()
