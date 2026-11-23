#!/usr/bin/env bash
# Serve the rewritten Pyodide index locally, compile deps for the Pyodide target,
# install them into the pyodide venv, and package python_modules for wrangler.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

WORKER=/mnt/d/Project/nim-proxy/spikes/cf-workers/worker
MIRROR="$HOME/pyodide-index-mirror"
PORT=8132

echo "== probe files.pythonhosted.org =="
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' --max-time 15 \
  https://files.pythonhosted.org/packages/source/f/fastapi/ || echo FAIL

echo "== start local index server =="
if [ -f "$MIRROR/server.pid" ] && kill -0 "$(cat "$MIRROR/server.pid")" 2>/dev/null; then
  echo "already running (pid $(cat "$MIRROR/server.pid"))"
else
  cd "$MIRROR"
  nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  echo $! > "$MIRROR/server.pid"
  sleep 1
  kill -0 "$(cat "$MIRROR/server.pid")" && echo "server started (pid $(cat "$MIRROR/server.pid"), port $PORT)"
fi
curl -fsS --max-time 5 "http://127.0.0.1:$PORT/314.0.7/httpx/" >/dev/null && echo "index reachable"

cd "$WORKER"

echo "== compile pylock.toml for pyodide =="
printf 'workers-runtime-sdk\n' > /tmp/spike-extra-reqs.txt
uv pip compile pyproject.toml /tmp/spike-extra-reqs.txt \
  --python cpython-3.14.2-emscripten-wasm32-musl \
  --extra-index-url "http://127.0.0.1:$PORT/314.0.7" \
  --index-strategy unsafe-best-match \
  --no-header --no-build \
  -o pylock.toml
echo "pylock packages: $(grep -c '^\[\[package\]\]' pylock.toml || true)"

echo "== install into pyodide venv =="
VENV="$WORKER/.venv-workers/pyodide-venv"
VIRTUAL_ENV="$VENV" uv pip install --only-binary :all: \
  -r pylock.toml --preview-features pylock

echo "== package python_modules =="
rm -rf python_modules
SP="$VENV/lib/python3.14/site-packages"
cp -r "$SP" python_modules
touch python_modules/pyvenv.cfg
echo "python_modules: $(ls python_modules | wc -l) entries, $(du -sh python_modules | cut -f1)"
