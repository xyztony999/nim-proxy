#!/usr/bin/env bash
# Reports what the Cloudflare Python Workers toolchain can use inside WSL.
set -u
echo "user=$(whoami) home=$HOME kernel=$(uname -r)"
for t in python3 pip3 uv uvx node npm npx git curl; do
  p="$(command -v "$t" 2>/dev/null || true)"
  if [ -n "$p" ]; then
    printf '%-8s %s (%s)\n' "$t" "$p" "$("$t" --version 2>&1 | head -1)"
  else
    printf '%-8s NOT FOUND\n' "$t"
  fi
done
echo "--- proxy env ---"
env | grep -i -E '^(https?|all|no)_proxy=' | sed -E 's#//[^@/]*@#//***@#' || true
echo "--- reachability ---"
curl -s -o /dev/null -w 'pypi simple/fastapi     %{http_code} %{time_total}s\n' --max-time 20 https://pypi.org/simple/fastapi/
curl -s -o /dev/null -w 'astral.sh uv installer  %{http_code} %{time_total}s\n' --max-time 15 https://astral.sh/uv/install.sh
curl -s -o /dev/null -w 'github releases         %{http_code} %{time_total}s\n' --max-time 15 https://github.com/astral-sh/uv/releases
curl -s -o /dev/null -w 'nodejs.org index        %{http_code} %{time_total}s\n' --max-time 15 https://nodejs.org/dist/index.json
