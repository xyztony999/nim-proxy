#!/usr/bin/env bash
# Build a local mirror of the Pyodide package index with wheel URLs rewritten
# from cdn.jsdelivr.net (blocked on this network) to fastly.jsdelivr.net.
# Layout: ~/pyodide-index-mirror/<ver>/<pkg>/index.html  (PEP 503 project pages)
set -euo pipefail

VER="314.0.7"
SRC="https://index.pyodide.org/$VER"
DST="$HOME/pyodide-index-mirror/$VER"
PKGS="annotated-types anyio certifi h11 httpcore httpx idna sniffio
      typing-extensions typing-inspection pydantic pydantic-core fastapi starlette"

mkdir -p "$DST"
for p in $PKGS; do
  mkdir -p "$DST/$p"
  curl -fsSL --max-time 30 "$SRC/$p/" \
    | sed 's#https://cdn\.jsdelivr\.net#https://fastly.jsdelivr.net#g' \
    > "$DST/$p/index.html"
  printf '%-20s %s hrefs, %s rewritten\n' "$p" \
    "$(grep -o 'href=' "$DST/$p/index.html" | wc -l)" \
    "$(grep -o 'fastly\.jsdelivr\.net' "$DST/$p/index.html" | wc -l)"
done
echo "mirror ready at $DST"
