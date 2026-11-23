#!/usr/bin/env bash
# Probe Pyodide wheel mirrors from inside WSL.
set -u
U="pyodide/v314.0.7/full/httpx-0.28.1-py3-none-any.whl"
for h in cdn.jsdelivr.net fastly.jsdelivr.net gcore.jsdelivr.net testingcf.jsdelivr.net; do
  printf '%-24s ' "$h"
  curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' --max-time 12 -L "https://$h/$U" || echo FAIL
done
printf '%-24s ' index.pyodide.org
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' --max-time 12 https://index.pyodide.org/314.0.7/httpx/
printf '%-24s ' npmmirror-pyodide
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' --max-time 12 'https://registry.npmmirror.com/-/binary/pyodide/v314.0.7/full/httpx-0.28.1-py3-none-any.whl'
