"""Go/no-go spike: the NIM relay app running on Cloudflare Workers (Python Workers).

The same FastAPI app runs in two places:
- Workers: ``src/entry.py`` wraps it with ``workers.asgi.entrypoint``; secrets and
  bindings arrive on ``request.scope["env"]``.
- A plain server (uvicorn): configuration falls back to ``os.environ``; there is no D1.

Every ``/spike/*`` endpoint is guarded by ``X-Spike-Token`` so the deployed Worker
cannot be used as an open relay while the spike is live.
"""

import json
import logging
import os
import secrets
import sys
import time
from collections.abc import Mapping
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

UPSTREAM = "https://integrate.api.nvidia.com"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nim-spike")

app = FastAPI(docs_url=None, redoc_url=None)


# ---------- runtime abstraction: Workers bindings vs. server environment ----------


def get_env(request: Request):
    env = request.scope.get("env")
    return env if env is not None else os.environ


def to_py(value):
    """Convert a proxied JS result to a plain Python object; pass natives through."""
    convert = getattr(value, "to_py", None)
    return convert() if callable(convert) else value


def env_value(env, name: str, default=None):
    """Scalar variable or secret, from a Workers env object or a mapping (server)."""
    if isinstance(env, Mapping):
        return env.get(name, default)
    try:
        value = getattr(env, name)
    except AttributeError:
        return default
    if isinstance(value, (str, int, float, bool)) or value is None:
        return default if value is None else value
    converted = to_py(value)
    return default if converted is None else converted


def env_binding(env, name: str):
    """Object binding (D1, KV, ...), kept raw so its methods stay callable."""
    if isinstance(env, Mapping):
        return env.get(name)
    try:
        return getattr(env, name)
    except AttributeError:
        return None


def require_spike_token(request: Request) -> None:
    expected = env_value(get_env(request), "SPIKE_TOKEN") or ""
    presented = request.headers.get("x-spike-token", "")
    if not expected or not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="bad spike token")


def ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


# ---------- probes ----------


@app.get("/health")
async def health(request: Request):
    env = get_env(request)
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "runtime": "workers" if request.scope.get("env") is not None else "server",
        "has_nvidia_key": bool(env_value(env, "NVIDIA_API_KEY")),
        "has_db": env_binding(env, "DB") is not None,
    }


@app.get("/spike/upstream-models", dependencies=[Depends(require_spike_token)])
async def upstream_models(request: Request):
    """Egress probe: can this Worker reach NVIDIA NIM? Sends the key when present."""
    api_key = env_value(get_env(request), "NVIDIA_API_KEY") or ""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{UPSTREAM}/v1/models", headers=headers)
        content = await resp.aread()
    models = 0
    try:
        models = len(resp.json().get("data", []))
    except Exception:  # noqa: BLE001 - probe only
        pass
    return {
        "status": resp.status_code,
        "bytes": len(content),
        "models": models,
        "wall_ms": ms(t0),
        "key_sent": bool(api_key),
        "key_len": len(api_key),
    }


@app.post("/spike/peek", dependencies=[Depends(require_spike_token)])
async def peek(request: Request):
    """Body-parsing probe: show exactly what the app receives and whether JSON parses."""
    raw = await request.body()
    ctype = request.headers.get("content-type", "")
    parsed = None
    error = None
    try:
        import json

        parsed = json.loads(raw)
    except Exception as e:  # noqa: BLE001 - probe self-diagnostics
        error = repr(e)
    return {
        "bytes": len(raw),
        "content_type": ctype,
        "head": raw[:120].decode("utf-8", "replace"),
        "json_ok": parsed is not None,
        "json_error": error,
    }


class ChatIn(BaseModel):
    model: str = "minimaxai/minimax-m3.1-flash"
    prompt: str = "用一句话介绍你自己"
    max_tokens: int = Field(default=64, ge=1, le=8192)
    stream: bool = True


@app.post("/spike/chat", dependencies=[Depends(require_spike_token)])
async def chat(body: ChatIn, request: Request):
    """Core relay path: authenticated chat completion, streaming (SSE) or buffered."""
    try:
        return await _chat(body, request)
    except Exception as e:  # noqa: BLE001 - probe self-diagnostics
        import traceback

        log.exception("chat probe failed: %r", e)
        return JSONResponse(
            {"error": repr(e), "traceback": traceback.format_exc()[-1500:]},
            status_code=500,
        )


async def _chat(body: ChatIn, request: Request):
    api_key = env_value(get_env(request), "NVIDIA_API_KEY") or ""
    payload = {
        "model": body.model,
        "messages": [{"role": "user", "content": body.prompt}],
        "max_tokens": body.max_tokens,
        "stream": body.stream,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if body.stream else "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    t0 = time.perf_counter()
    # workers.fetch (pyfetch bridge) — httpx's jsfetch transport hangs on
    # POST-with-body on some isolates; the SDK's own fetch is the supported path.
    from workers import fetch as cf_fetch

    resp = await cf_fetch(
        f"{UPSTREAM}/v1/chat/completions",
        method="POST",
        headers=headers,
        body=json.dumps(payload).encode("utf-8"),
    )
    ttfb = ms(t0)
    status = int(resp.status)

    if status >= 400:
        content = await resp.bytes()
        log.info("upstream %s after %d ms: %s", status, ttfb, content[:300])
        return JSONResponse(
            {
                "upstream_status": status,
                "body": content[:500].decode("utf-8", "replace"),
                "ttfb_ms": ttfb,
            },
            status_code=502,
        )

    resp_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in ("content-length", "transfer-encoding", "connection")
    }
    resp_headers["X-Spike-TTFB-Ms"] = str(ttfb)
    ctype = resp_headers.get("content-type", "")

    if "text/event-stream" in ctype:
        reader = resp.body.getReader()
        stats = {"chunks": 0, "bytes": 0}

        async def relay():
            try:
                while True:
                    chunk = await reader.read()
                    if chunk.done:
                        break
                    data = chunk.value.to_bytes()
                    stats["chunks"] += 1
                    stats["bytes"] += len(data)
                    yield data
            finally:
                log.info(
                    "stream done: chunks=%d bytes=%d wall_ms=%d",
                    stats["chunks"],
                    stats["bytes"],
                    ms(t0),
                )

        resp_headers["x-accel-buffering"] = "no"
        return StreamingResponse(
            relay(),
            status_code=status,
            media_type="text/event-stream",
            headers=resp_headers,
        )

    content = await resp.bytes()
    return Response(content=content, status_code=status, media_type=ctype, headers=resp_headers)


@app.get("/spike/d1", dependencies=[Depends(require_spike_token)])
async def d1_probe(request: Request):
    """D1 from Python through the ASGI scope: create, insert, read back."""
    db = env_binding(get_env(request), "DB")
    if db is None:
        return JSONResponse({"error": "no DB binding"}, status_code=503)

    await db.prepare(
        "CREATE TABLE IF NOT EXISTS spike_hits (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL)"
    ).run()
    now = datetime.now(timezone.utc).isoformat()
    insert = await db.prepare("INSERT INTO spike_hits (at) VALUES (?)").bind(now).run()
    row = to_py(await db.prepare("SELECT COUNT(*) AS n FROM spike_hits").first())
    return {
        "rows": row.get("n") if isinstance(row, dict) else row,
        "insert_success": to_py(insert.success) if hasattr(insert, "success") else None,
        "binding_type": f"{type(db).__module__}.{type(db).__qualname__}",
    }


@app.post("/spike/echo", dependencies=[Depends(require_spike_token)])
async def echo(request: Request):
    """Body-size probe: the ASGI adapter buffers the whole body before the app runs."""
    body = await request.body()
    return {"bytes": len(body)}


@app.get("/spike/bridge-matrix", dependencies=[Depends(require_spike_token)])
async def bridge_matrix(request: Request):
    """2x2 matrix: (GET|POST) x (plain client method | build_request+send(stream))."""
    import json as _json

    key = env_value(get_env(request), "NVIDIA_API_KEY") or ""
    auth = {"Authorization": f"Bearer {key}"} if key else {}
    out: dict[str, object] = {}
    timeout = httpx.Timeout(connect=20, read=30, write=20, pool=20)
    chat_url = f"{UPSTREAM}/v1/chat/completions"
    payload = {
        "model": "minimaxai/minimax-m3.1-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.get(f"{UPSTREAM}/v1/models", headers=auth)
            out["get_plain"] = r.status_code
        except Exception as e:  # noqa: BLE001
            out["get_plain"] = repr(e)[:90]
        try:
            req = client.build_request("GET", f"{UPSTREAM}/v1/models", headers=auth)
            r = await client.send(req, stream=True)
            await r.aread()
            await r.aclose()
            out["get_build_stream"] = r.status_code
        except Exception as e:  # noqa: BLE001
            out["get_build_stream"] = repr(e)[:90]
        try:
            r = await client.post(
                chat_url,
                headers={**auth, "Content-Type": "application/json"},
                json=payload,
            )
            out["post_plain"] = r.status_code
        except Exception as e:  # noqa: BLE001
            out["post_plain"] = repr(e)[:90]
        try:
            req = client.build_request(
                "POST",
                chat_url,
                headers={**auth, "Content-Type": "application/json"},
                content=_json.dumps(payload).encode(),
            )
            r = await client.send(req, stream=True)
            await r.aread()
            await r.aclose()
            out["post_build_stream"] = r.status_code
        except Exception as e:  # noqa: BLE001
            out["post_build_stream"] = repr(e)[:90]

        # bisect /spike/chat vs matrix: Accept header + timeout profile
        chat_timeout = httpx.Timeout(connect=15, read=600, write=60, pool=60)
        async with httpx.AsyncClient(timeout=chat_timeout) as c2:
            try:
                r = await c2.post(
                    chat_url,
                    headers={**auth, "Content-Type": "application/json"},
                    json=payload,
                )
                out["chat_timeouts_no_accept"] = r.status_code
            except Exception as e:  # noqa: BLE001
                out["chat_timeouts_no_accept"] = repr(e)[:90]
        async with httpx.AsyncClient(timeout=timeout) as c3:
            try:
                r = await c3.post(
                    chat_url,
                    headers={
                        **auth,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
                out["accept_header_matrix_timeouts"] = r.status_code
            except Exception as e:  # noqa: BLE001
                out["accept_header_matrix_timeouts"] = repr(e)[:90]

        # hypothesis: a fresh client's FIRST fetch hangs if it is a POST;
        # priming with a cheap GET fixes even the fully "cursed" config.
        async with httpx.AsyncClient(timeout=chat_timeout) as c4:
            try:
                prime = await c4.get(f"{UPSTREAM}/v1/models", headers=auth)
                r = await c4.post(
                    chat_url,
                    headers={
                        **auth,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
                out["primed_post_chat_style"] = {
                    "prime_status": prime.status_code,
                    "post_status": r.status_code,
                }
            except Exception as e:  # noqa: BLE001
                out["primed_post_chat_style"] = repr(e)[:90]
    return out


@app.get("/spike/fetch-latency", dependencies=[Depends(require_spike_token)])
async def fetch_latency(request: Request):
    """Decompose outbound POST latency: NIM queueing vs fetch bridging."""
    from workers import fetch as cf_fetch

    key = env_value(get_env(request), "NVIDIA_API_KEY") or ""
    chat_url = f"{UPSTREAM}/v1/chat/completions"
    out: dict[str, object] = {}

    async def timed_post(tag: str, auth_key: str, max_tokens: int):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_key}" if auth_key else "",
        }
        payload = json.dumps(
            {
                "model": "minimaxai/minimax-m3.1-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": max_tokens,
                "stream": False,
            }
        ).encode("utf-8")
        t = time.perf_counter()
        try:
            r = await cf_fetch(chat_url, method="POST", headers=headers, body=payload)
            out[tag] = {
                "status": int(r.status),
                "headers_ms": ms(t),
            }
        except Exception as e:  # noqa: BLE001
            out[tag] = {"error": repr(e)[:80], "elapsed_ms": ms(t)}

    await timed_post("bogus_key_post", "nvapi-bogus-key-for-auth-timing", 1)
    await timed_post("valid_key_post", key, 1)
    t = time.perf_counter()
    r = await cf_fetch(f"{UPSTREAM}/v1/models", headers={"Authorization": f"Bearer {key}"})
    out["valid_key_get"] = {"status": int(r.status), "headers_ms": ms(t)}
    return out


@app.get("/spike/cpu", dependencies=[Depends(require_spike_token)])
async def cpu_probe():
    """CPU probe: a fixed amount of Python work, to calibrate WASM speed."""
    try:
        t0 = time.perf_counter()
        total = sum(i * i for i in range(200_000))
        return {
            "loop_ms": round((time.perf_counter() - t0) * 1000, 2),
            "checksum": total,
        }
    except Exception as e:  # noqa: BLE001 - probe self-diagnostics
        import traceback

        return JSONResponse(
            {"error": repr(e), "traceback": traceback.format_exc()[-1500:]},
            status_code=500,
        )
