#!/usr/bin/env bash
# Set NVIDIA_API_KEY from C:\Users\zhang\nvapi.txt into the spike Worker secret,
# then delete the file. Run via:
#   MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/d/Project/nim-proxy/spikes/cf-workers/scripts/set-nvidia-key.sh
set -euo pipefail

export CLOUDFLARE_API_TOKEN="$(cat ~/.cloudflare-token)"
export PATH="$HOME/.npm-global/bin:$PATH"
cd /mnt/d/Project/nim-proxy/spikes/cf-workers/worker

F=/mnt/c/Users/zhang/nvapi.txt
if [ ! -f "$F" ]; then
  echo "missing $F - run 'notepad ~/nvapi.txt' first, paste the key, save"
  exit 1
fi

K="$(cat "$F")"
K="${K//[[:space:]]/}"
if [ "${#K}" -lt 20 ]; then
  echo "ABORT: only ${#K} chars read from nvapi.txt"
  rm -f "$F"
  exit 1
fi

printf %s "$K" | wrangler secret put NVIDIA_API_KEY
echo "secret set OK (${#K} chars); nvapi.txt deleted"
rm -f "$F"
unset K
