#!/usr/bin/env bash
# Depuis un poste de dev : compile le frontend, copie le dépôt utile dans le CT
# et lance l'installation idempotente.
#   NAOMOX_HOST=root@10.185.10.230 deploy/push.sh
set -euo pipefail
HOST="${NAOMOX_HOST:-root@10.185.10.230}"
KEY="${NAOMOX_KEY:-$HOME/.ssh/naomox_ed25519}"
cd "$(dirname "$0")/.."

if [ "${SKIP_BUILD:-0}" != 1 ]; then
  (cd frontend && { [ -d node_modules ] || npm ci; } && npm run build)
fi

tar --owner=0 --group=0 \
    --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='*.egg-info' \
    -cf - backend/pyproject.toml backend/README.md backend/src frontend/dist deploy homebrew |
  ssh -i "$KEY" "$HOST" 'rm -rf /root/naomox-src && mkdir -p /root/naomox-src && tar --no-same-owner -xf - -C /root/naomox-src && bash /root/naomox-src/deploy/install.sh'
