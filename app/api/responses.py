"""OpenAI Responses API endpoint (Codex wire_api="responses" compatibility)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import get_config, get_http, get_repo, get_telemetry
from app.core.config import Config
from app.core.http_client import HttpClient
from app.repositories.base import Repository
from app.services.responses import ResponsesService
from app.services.telemetry import TelemetryService

log = logging.getLogger("nim-proxy")

router = APIRouter()


@router.post("/v1/responses")
async def responses(
    request: Request,
    config: Config = Depends(get_config),
    repo: Repository = Depends(get_repo),
    http: HttpClient = Depends(get_http),
    telemetry: TelemetryService = Depends(get_telemetry),
) -> object:
    body = await request.json()
    # TEMP DEBUG: capture request shape to np_debug (Workers only); remove after diagnosis.
    try:
        env = request.scope.get("env")
        if env is not None:
            import json as _json
            import uuid as _uuid
            from datetime import datetime, timezone
            inp = body.get("input")
            cap = _json.dumps({
                "tools": body.get("tools"),
                "tool_choice": body.get("tool_choice"),
                "input_types": [i.get("type") for i in inp if isinstance(i, dict)]
                if isinstance(inp, list) else "str",
                "reasoning": body.get("reasoning"),
            }, ensure_ascii=False)
            await env.DB.prepare("INSERT INTO np_debug(id,ts,body) VALUES(?,?,?)").bind(
                _uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), cap).run()
    except Exception:  # noqa: BLE001
        log.exception("debug capture failed")
    headers = {k: v for k, v in request.headers.items()}
    result, row = await ResponsesService(repo, http, config).create(body, headers)

    if hasattr(result, "__aiter__"):
        async def stream():
            async for ev in result:
                yield ev
            try:
                await telemetry.record(row)
            except Exception:  # noqa: BLE001
                log.exception("telemetry record failed")

        return StreamingResponse(
            stream(), media_type="text/event-stream",
            headers={"x-accel-buffering": "no", "cache-control": "no-cache"},
        )

    try:
        await telemetry.record(row)
    except Exception:  # noqa: BLE001
        log.exception("telemetry record failed")
    status = row.get("status", 200)
    return JSONResponse(result, status_code=status if status >= 400 else 200)
