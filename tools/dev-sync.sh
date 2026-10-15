#!/usr/bin/env bash
# Copie l'arbre de travail (backend, frontend/dist, deploy) vers le CT de dev et,
# optionnellement, y lance une commande dans /opt/naomox-dev/backend.
#   tools/dev-sync.sh                      # synchronise seulement
#   tools/dev-sync.sh 'pytest -q'          # synchronise puis lance les tests
set -euo pipefail
HOST="${NAOMOX_HOST:-root@10.185.10.230}"
KEY="${NAOMOX_KEY:-$HOME/.ssh/naomox_ed25519}"
DEST=/opt/naomox-dev
cd "$(dirname "$0")/.."

paths=(backend)
[ -d deploy ] && paths+=(deploy)
[ -d frontend/dist ] && paths+=(frontend/dist)
[ -f var/www/html/csv/romsinfo.csv ] && paths+=(var/www/html/csv/romsinfo.csv)

tar --owner=0 --group=0 --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
    --exclude='*.egg-info' -cf - "${paths[@]}" |
  ssh -i "$KEY" "$HOST" "rm -rf $DEST/backend/src $DEST/backend/tests && mkdir -p $DEST && tar --no-same-owner -xf - -C $DEST"

if [ $# -gt 0 ]; then
  ssh -i "$KEY" "$HOST" "cd $DEST/backend && \
    { [ -x .venv/bin/python ] || python3 -m venv .venv; } && . .venv/bin/activate && \
    { [ -f .venv/.deps-ok ] && cmp -s pyproject.toml .venv/.deps-ok || \
      { pip install -q -e '.[dev]' && cp pyproject.toml .venv/.deps-ok; }; } && $*"
fi
