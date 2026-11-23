"""Application factory and server composition root.

create_app() is platform-agnostic; the server lifespan wires SQLite + httpx.
The Workers composition root (workers/entry.py) injects D1 + workers.fetch via
per-request dependencies instead of app.state.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.adapters.httpx_client import HttpxAdapter
from app.api import admin, relay, setup
from app.api.errors import register_exception_handlers
from app.core.config import build_config, server_env
from app.repositories.sqlite import SqliteRepository, open_database

log = logging.getLogger("nim-proxy")


class SPAStaticFiles(StaticFiles):
    """Static files with SPA fallback: unknown paths serve index.html so that
    client-side routes (e.g. /admin/client-keys) survive refresh / deep links."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def create_app(platform: str = "server") -> FastAPI:
    config = build_config(server_env())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if platform == "server":
            conn = open_database(config.db_path)
            repo = SqliteRepository(conn)
            await repo.migrate()
            await repo.seed_keys(config.nvidia_api_keys, config.proxy_api_keys)
            app.state.repo = repo
            app.state.http = HttpxAdapter(config.connect_timeout, config.read_timeout)
            log.info("server ready: upstream=%s db=%s", config.upstream, config.db_path)
        try:
            yield
        finally:
            repo = getattr(app.state, "repo", None)
            if repo is not None:
                await repo.aclose()

    app = FastAPI(title="nim-proxy", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.platform = platform
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(relay.router)
    app.include_router(setup.router)
    app.include_router(admin.router)

    # Serve the built admin SPA when present (server target).
    dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if dist.is_dir():
        app.mount("/admin", SPAStaticFiles(directory=str(dist), html=True), name="admin")

    return app


app = create_app()
