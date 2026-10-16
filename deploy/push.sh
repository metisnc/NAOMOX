#!/usr/bin/env bash
# Depuis un poste de dev : compile le frontend, copie le dépôt utile dans le CT
# et lance l'installation idempotente.
#   NAOMOX_HOST=root@naomox.local deploy/push.sh
set -euo pipefail
HOST="${NAOMOX_HOST:-root@naomox.local}"
KEY="${NAOMOX_KEY:-$HOME/.ssh/naomox_ed25519}"
cd "$(dirname "$0")/.."

if [ "${SKIP_BUILD:-0}" != 1 ]; then
  (cd frontend && { [ -d node_modules ] || npm ci; } && npm run build)
fi

# Mot de passe SSH/SFTP du compte naomox à (ré)appliquer : développé ici, côté poste.
remote_env=""
if [ -n "${NAOMOX_SSH_PASSWORD:-}" ]; then remote_env="NAOMOX_SSH_PASSWORD=$(printf %q "$NAOMOX_SSH_PASSWORD") "; fi

tar --owner=0 --group=0 \
    --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='*.egg-info' \
    -cf - backend/pyproject.toml backend/README.md backend/src frontend/dist deploy homebrew |
  ssh -i "$KEY" "$HOST" "rm -rf /root/naomox-src && mkdir -p /root/naomox-src && tar --no-same-owner -xf - -C /root/naomox-src && ${remote_env}bash /root/naomox-src/deploy/install.sh"
