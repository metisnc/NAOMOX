#!/usr/bin/env bash
# Rapatrie backend/src et backend/tests depuis le CT de dev (après `ruff format` / `ruff --fix`).
set -euo pipefail
HOST="${NAOMOX_HOST:-root@naomox.local}"
KEY="${NAOMOX_KEY:-$HOME/.ssh/naomox_ed25519}"
cd "$(dirname "$0")/.."
ssh -i "$KEY" "$HOST" "cd /opt/naomox-dev && tar --exclude='__pycache__' -cf - backend/src backend/tests" | tar --no-same-owner -xf -
