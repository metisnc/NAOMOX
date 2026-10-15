#!/usr/bin/env bash
# Installation / mise à jour idempotente de NAOMOX sur Debian 12 ou 13 (LXC ou VM).
#
#   sudo ./deploy/install.sh                 # depuis une copie du dépôt (frontend/dist compilé)
#   sudo ./deploy/install.sh --no-start      # installe sans (re)démarrer le service
#   sudo ./deploy/install.sh --uninstall     # retire service, code et config (garde /srv/naomox)
#
# Ne touche jamais aux données (/srv/naomox) ni à une config existante (/etc/naomox/config.yaml).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/naomox
CONF_DIR=/etc/naomox
DATA_DIR=/srv/naomox
USER_NAME=naomox
UNIT=/etc/systemd/system/naomox.service
START=1

log() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mErreur :\033[0m %s\n' "$*" >&2; exit 1; }

for arg in "$@"; do
  case "$arg" in
    --no-start) START=0 ;;
    --uninstall)
      [ "$(id -u)" -eq 0 ] || die "à lancer en root"
      systemctl disable --now naomox 2>/dev/null || true
      rm -f "$UNIT" && systemctl daemon-reload
      rm -rf "$APP_DIR" "$CONF_DIR"
      log "NAOMOX désinstallé ; données conservées dans $DATA_DIR"
      exit 0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) die "option inconnue : $arg" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "à lancer en root"
. /etc/os-release
[ "${ID:-}" = debian ] || die "Debian requis (trouvé : ${ID:-?})"
case "${VERSION_ID:-}" in 12|13) ;; *) die "Debian 12 ou 13 requis (trouvé : ${VERSION_ID:-?})" ;; esac
[ -f "$REPO/backend/pyproject.toml" ] || die "dépôt introuvable : $REPO"
[ -f "$REPO/frontend/dist/index.html" ] || die "frontend non compilé : lancer 'npm ci && npm run build' dans frontend/"

log "Paquets système"
need=()
for p in python3 python3-venv ca-certificates curl; do
  dpkg -s "$p" >/dev/null 2>&1 || need+=("$p")
done
if [ ${#need[@]} -gt 0 ]; then
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${need[@]}"
fi

log "Utilisateur système $USER_NAME"
id "$USER_NAME" >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --no-create-home --shell /usr/sbin/nologin "$USER_NAME"

log "Répertoires"
install -d -m 0755 "$APP_DIR" "$CONF_DIR"
install -d -m 0750 -o "$USER_NAME" -g "$USER_NAME" "$DATA_DIR"
for d in roms media media/images media/videos firmware homebrew state tmp; do
  install -d -m 0750 -o "$USER_NAME" -g "$USER_NAME" "$DATA_DIR/$d"
done

log "Code de l'application → $APP_DIR"
rm -rf "$APP_DIR/app.new" "$APP_DIR/frontend.new"
mkdir -p "$APP_DIR/app.new"
cp -a "$REPO/backend/pyproject.toml" "$REPO/backend/README.md" "$REPO/backend/src" "$APP_DIR/app.new/"
find "$APP_DIR/app.new" -name '__pycache__' -prune -exec rm -rf {} +
cp -a "$REPO/frontend/dist" "$APP_DIR/frontend.new"
rm -rf "$APP_DIR/app" "$APP_DIR/frontend"
mv "$APP_DIR/app.new" "$APP_DIR/app"
mv "$APP_DIR/frontend.new" "$APP_DIR/frontend"

log "Environnement Python ($APP_DIR/venv)"
[ -x "$APP_DIR/venv/bin/python" ] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q --upgrade "$APP_DIR/app"
chmod -R a+rX "$APP_DIR"

log "Configuration"
if [ ! -f "$CONF_DIR/config.yaml" ]; then
  install -m 0640 -g "$USER_NAME" "$REPO/deploy/config.example.yaml" "$CONF_DIR/config.yaml"
  log "  $CONF_DIR/config.yaml créé (à adapter)"
else
  log "  $CONF_DIR/config.yaml existant conservé"
fi

log "Homebrew (domaine public)"
HB="$REPO/homebrew"
if [ -d "$HB" ]; then
  for f in naomidiag.bin.gz netbootmenu.bin netbootmenu.bin.dark netbootmenu.bin.light; do
    if [ -f "$HB/$f" ] && [ ! -f "$DATA_DIR/homebrew/$(basename "$f")" ]; then
      install -m 0640 -o "$USER_NAME" -g "$USER_NAME" "$HB/$f" "$DATA_DIR/homebrew/"
    fi
  done
fi

log "Service systemd"
changed=0
if ! cmp -s "$REPO/deploy/naomox.service" "$UNIT" 2>/dev/null; then
  install -m 0644 "$REPO/deploy/naomox.service" "$UNIT"
  changed=1
fi
systemctl daemon-reload
systemctl enable -q naomox

if [ "$START" -eq 1 ]; then
  systemctl restart naomox
  log "Vérification"
  for _ in $(seq 1 30); do
    if curl -fsS -m 2 http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
      ip=$(hostname -I | awk '{print $1}')
      log "NAOMOX opérationnel : http://${ip}/"
      exit 0
    fi
    sleep 1
  done
  journalctl -u naomox -n 40 --no-pager >&2 || true
  die "le service ne répond pas (voir journalctl -u naomox)"
fi
if [ "$changed" -eq 1 ]; then log "Unité systemd mise à jour"; fi
log "Installé (service non démarré : --no-start)"
