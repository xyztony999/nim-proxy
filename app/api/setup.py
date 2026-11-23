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








@router.post("/api/v1/auth/login", response_model=LoginVo)
async def login(
    ao: LoginAo,
    config: Config = Depends(get_config),
    repo: Repository = Depends(get_repo),
) -> LoginVo:
    token = await AuthService(repo, config).login(ao.password)
    return LoginVo(token=token)
