"""Anthropic Messages API endpoint (Claude Code compatibility).

Translates Anthropic <-> OpenAI so Anthropic-format clients can use the NIM relay.
Registered before the /v1/* passthrough catch-all so /v1/messages is handled here.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import get_config, get_http, get_repo, get_telemetry
from app.core.config import Config
from app.core.http_client import HttpClient
from app.repositories.base import Repository
from app.services.anthropic import AnthropicService
from app.services.telemetry import TelemetryService

log = logging.getLogger("nim-proxy")

router = APIRouter()


@router.post("/v1/messages")
async def messages(
    request: Request,
    config: Config = Depends(get_config),
    repo: Repository = Depends(get_repo),
    http: HttpClient = Depends(get_http),
    telemetry: TelemetryService = Depends(get_telemetry),
) -> object:
    body = await request.json()
    headers = {k: v for k, v in request.headers.items()}
    service = AnthropicService(repo, http, config)
    result, row = await service.messages(body, headers)

    if hasattr(result, "__aiter__"):
        async def stream():
            async for ev in result:
                yield ev
            try:
                await telemetry.record(row)
            except Exception:  # noqa: BLE001
                log.exception("telemetry record failed")

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"x-accel-buffering": "no", "cache-control": "no-cache"},
        )

    try:
        await telemetry.record(row)
    except Exception:  # noqa: BLE001
        log.exception("telemetry record failed")
    status = row.get("status", 200)
    return JSONResponse(result, status_code=status if status >= 400 else 200)


@router.post("/v1/messages/count_tokens")
async def count_tokens(request: Request) -> JSONResponse:
    body = await request.json()
    chars = len(json.dumps(body.get("messages", []))) + len(json.dumps(body.get("system", "")))
    return JSONResponse({"input_tokens": max(1, chars // 4)})
