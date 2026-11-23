"""
NIM Proxy — NVIDIA NIM (integrate.api.nvidia.com) OpenAI-compatible API relay.

Features:
  * Generic passthrough: /v1/* -> upstream /v1/* (chat/completions, models,
    embeddings, ...). Streaming (SSE) and non-streaming both supported.
  * Upstream key pool: comma-separated keys, round-robin rotation,
    auto-retry with the next key on 401/403/429.
  * Proxy auth: clients authenticate with PROXY_API_KEYS; if unset, the
    client's own Authorization header is forwarded to upstream (pure relay).
  * CORS open for browser-based clients (LobeChat / NextChat / etc.).

All behavior is configured via environment variables, see .env.example.
"""

import itertools
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.responses import Response

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("nim-proxy")

UPSTREAM = os.getenv(
    "NIM_UPSTREAM", "https://integrate.api.nvidia.com"
).rstrip("/")

# Upstream NVIDIA keys ("nvapi-..."), comma-separated for rotation.
UPSTREAM_KEYS = [
    k.strip()
    for k in os.getenv("NVIDIA_API_KEYS", os.getenv("NVIDIA_API_KEY", "")).split(",")
    if k.strip()
]

# Keys clients must present as `Authorization: Bearer <key>`.
# Empty set => proxy auth disabled, client key is forwarded upstream as-is.
PROXY_KEYS = {
    k.strip()
    for k in os.getenv("PROXY_API_KEYS", os.getenv("PROXY_API_KEY", "")).split(",")
    if k.strip()
}

PORT = int(os.getenv("PORT", "8000"))

# Long read timeout: large max_tokens (e.g. 16384) can stream for minutes.
TIMEOUT = httpx.Timeout(
    connect=float(os.getenv("CONNECT_TIMEOUT", "15")),
    read=float(os.getenv("READ_TIMEOUT", "600")),
    write=60.0,
    pool=600.0,
)

# Status codes that are worth retrying with the next upstream key.
RETRY_STATUS = {401, 403, 429}

# Hop-by-hop / per-request headers we must not forward blindly.
DROP_HEADERS = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailers",
    "upgrade",
    "expect",
    "proxy-authorization",
    "proxy-authenticate",
}

_key_cycle = itertools.cycle(UPSTREAM_KEYS)


def next_key() -> str | None:
    if not UPSTREAM_KEYS:
        return None
    return next(_key_cycle)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(
        base_url=UPSTREAM, timeout=TIMEOUT, follow_redirects=False
    )
    if not UPSTREAM_KEYS:
        log.warning(
            "NVIDIA_API_KEYS is empty: running in pure-relay mode, "
            "the client's own Authorization header is passed upstream."
        )
    else:
        log.info("Loaded %d upstream key(s).", len(UPSTREAM_KEYS))
    log.info("Upstream: %s", UPSTREAM)
    yield
    await app.state.client.aclose()


app = FastAPI(title="nim-proxy", lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "upstream": UPSTREAM,
        "upstream_keys": len(UPSTREAM_KEYS),
        "proxy_auth": bool(PROXY_KEYS),
    }


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def relay(request: Request, path: str):
    # --- client auth ---
    auth = request.headers.get("authorization", "")
    if PROXY_KEYS:
        presented = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if presented not in PROXY_KEYS:
            return JSONResponse(
                {"error": {"message": "Invalid or missing API key", "type": "auth_error"}},
                status_code=401,
            )

    url = "/" + path
    if request.url.query:
        url += "?" + request.url.query
    body = await request.body()

    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in DROP_HEADERS
    }

    client: httpx.AsyncClient = request.app.state.client
    upstream_key = next_key()

    # Try each upstream key once on retryable failures.
    attempts = len(UPSTREAM_KEYS) if upstream_key else 1
    resp: httpx.Response | None = None
    for i in range(attempts):
        req_headers = dict(headers)
        if upstream_key:
            req_headers["authorization"] = f"Bearer {upstream_key}"
        req = client.build_request(
            request.method, url, headers=req_headers, content=body
        )
        resp = await client.send(req, stream=True)
        if resp.status_code in RETRY_STATUS and i < attempts - 1:
            await resp.aclose()
            log.warning(
                "Upstream %d for %s %s, rotating key.", resp.status_code,
                request.method, path,
            )
            upstream_key = next_key()
            continue
        break

    assert resp is not None
    if resp.status_code >= 400:
        log.info("Upstream %d for %s %s", resp.status_code, request.method, path)

    resp_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in ("content-length", "transfer-encoding", "connection")
    }

    ctype = resp.headers.get("content-type", "")
    is_sse = "text/event-stream" in ctype

    if is_sse:
        resp_headers.setdefault("x-accel-buffering", "no")  # keep nginx from buffering
        return StreamingResponse(
            resp.aiter_raw(),
            status_code=resp.status_code,
            headers=resp_headers,
            background=BackgroundTask(resp.aclose),
        )

    # Non-streaming: buffer and return untouched.
    content = await resp.aread()
    await resp.aclose()
    return Response(
        content=content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=ctype or None,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=PORT,
        workers=1,
        access_log=os.getenv("ACCESS_LOG", "1") == "1",
    )
