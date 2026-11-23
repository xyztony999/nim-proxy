"""Public endpoints: first-run setup status/init and admin login."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_config, get_http, get_repo
from app.core.config import Config
from app.core.http_client import HttpClient
from app.repositories.base import Repository
from app.schemas.setup import LoginAo, LoginVo, SetupInitAo, SetupInitVo, SetupStatusVo
from app.services.auth import AuthService, SetupService

router = APIRouter()


@router.get("/api/v1/setup/status", response_model=SetupStatusVo)
async def setup_status(
    config: Config = Depends(get_config), repo: Repository = Depends(get_repo)
) -> SetupStatusVo:
    configured = await AuthService(repo, config).is_configured()
    counts = await repo.count_keys()
    return SetupStatusVo(configured=configured, upstream_key_count=counts["upstream"])




@router.post("/api/v1/setup/init", response_model=SetupInitVo)
async def setup_init(
    ao: SetupInitAo,
    config: Config = Depends(get_config),
    repo: Repository = Depends(get_repo),
    http: HttpClient = Depends(get_http),
) -> SetupInitVo:
    result = await SetupService(repo, http, config).init(ao)
    return SetupInitVo(**result)


@router.post("/api/v1/setup/debug-probe")
async def setup_debug_probe(
    ao: SetupInitAo,
    config: Config = Depends(get_config),
    http: HttpClient = Depends(get_http),
) -> dict:
    import json as _json

    from app.services.auth import _read_all

    out: dict = {}
    try:
        ms, mb = await _read_all(http, "GET", f"{config.upstream}/v1/models", {}, None)
        out["models_status"] = ms
        model_id = "minimaxai/minimax-m3.1-flash"
        try:
            data = _json.loads(mb)
            if data.get("data"):
                model_id = data["data"][0]["id"]
        except Exception:  # noqa: BLE001
            pass
        out["model_id"] = model_id
        probe = _json.dumps(
            {"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
        ).encode()
        ps, pb = await _read_all(
            http,
            "POST",
            f"{config.upstream}/v1/chat/completions",
            {"Authorization": f"Bearer {ao.nvidia_key}", "Content-Type": "application/json"},
            probe,
        )
        out["probe_status"] = ps
        out["probe_body"] = pb[:300].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)
    return out






@router.post("/api/v1/auth/login", response_model=LoginVo)
async def login(
    ao: LoginAo,
    config: Config = Depends(get_config),
    repo: Repository = Depends(get_repo),
) -> LoginVo:
    token = await AuthService(repo, config).login(ao.password)
    return LoginVo(token=token)
