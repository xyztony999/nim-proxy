"""FastAPI dependencies: config, repository, http client, services, admin guard."""

from __future__ import annotations

from fastapi import Depends, Request

from app.core.config import Config, build_config, server_env
from app.core.errors import Forbidden, Unauthorized
from app.core.http_client import HttpClient
from app.core.security import bearer_token, secrets_equal
from app.repositories.base import Repository
from app.services.keys import KeyService
from app.services.relay import RelayService
from app.services.telemetry import TelemetryService


def get_config(request: Request) -> Config:
    env = request.scope.get("env")
    return build_config(env if env is not None else server_env())


def get_repo(request: Request) -> Repository:
    repo = getattr(request.app.state, "repo", None)
    if repo is not None:
        return repo
    # Workers: build D1 repository from the per-request scope env.
    from app.adapters.d1_repository import D1Repository

    cached = getattr(request.state, "repo", None)
    if cached is None:
        cached = D1Repository(request.scope["env"].DB)
        request.state.repo = cached
    return cached


def get_http(request: Request) -> HttpClient:
    http = getattr(request.app.state, "http", None)
    if http is not None:
        return http
    from app.adapters.workers_http import WorkersFetchAdapter

    return WorkersFetchAdapter()


def get_key_service(repo: Repository = Depends(get_repo)) -> KeyService:
    return KeyService(repo)


def get_telemetry(repo: Repository = Depends(get_repo)) -> TelemetryService:
    return TelemetryService(repo)


def get_relay(
    request: Request,
    repo: Repository = Depends(get_repo),
    http: HttpClient = Depends(get_http),
    config: Config = Depends(get_config),
) -> RelayService:
    return RelayService(repo, http, config)


def require_admin(request: Request, config: Config = Depends(get_config)) -> None:
    if not config.admin_token:
        raise Forbidden("管理接口未启用（未配置 ADMIN_TOKEN）")
    token = bearer_token(request)
    if not token or not secrets_equal(token, config.admin_token):
        raise Unauthorized("无效的管理令牌")
