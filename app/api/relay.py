"""Relay (passthrough) and health endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask

from app.api.deps import get_config, get_relay, get_telemetry
from app.core.config import Config
from app.core.security import bearer_token
from app.services.relay import RelayService
from app.services.telemetry import TelemetryService

log = logging.getLogger("nim-proxy")

router = APIRouter()


@router.get("/health")
async def health(config: Config = Depends(get_config)) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "upstream": config.upstream,
            "upstream_keys": len(config.nvidia_api_keys),
            "proxy_auth": bool(config.proxy_api_keys),
        }
    )


@router.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def relay(
    request: Request,
    path: str,
    service: RelayService = Depends(get_relay),
    telemetry: TelemetryService = Depends(get_telemetry),
) -> object:
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    response, row = await service.relay(
        method=request.method,
        path=f"v1/{path}",
        query=request.url.query,
        headers=headers,
        body=body,
        bearer=bearer_token(request),
    )

    async def record():
        try:
            await telemetry.record(row)
        except Exception:  # noqa: BLE001 - telemetry must not break the relay
            log.exception("failed to record request telemetry")

    if row.pop("_deferred_telemetry", False):
        # Lazy SSE stream: status/usage are only known once it finishes, so
        # record after the response body is fully sent.
        response.background = BackgroundTask(record)
    else:
        await record()
    return response
