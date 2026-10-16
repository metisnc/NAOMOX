#!/usr/bin/env bash
# Pack de contenu NAOMOX : ROMs, médias (jaquettes, vidéos, logos de systèmes), firmwares
# et liste des jeux (favoris, jeux désactivés). Les bornes ne sont pas incluses.
#
# À lancer dans le conteneur, en root (installé comme /usr/local/bin/naomox-content) :
#   naomox-content export <fichier.tar | ->        crée le pack (« - » = sortie standard)
#   naomox-content import <fichier.tar | dossier | URL | ->
#
# Depuis l'hôte Proxmox :
#   pct exec <CTID> -- naomox-content export - > /mnt/pve/nas/naomox-content.tar
#   pct exec <CTID> -- naomox-content import - < /mnt/pve/nas/naomox-content.tar
#
# L'import ajoute les fichiers absents sans écraser ceux déjà présents, remet les droits du
# compte naomox et relance la détection des ROMs.
# ⚠ Les ROMs, vidéos et firmwares Sega sont protégés : gardez ce pack sur votre propre
#   stockage, ne le publiez pas.
set -euo pipefail

DATA_DIR="${NAOMOX_DATA:-/srv/naomox}"
USER_NAME=naomox
PARTS=(roms media firmware)

die() { printf 'Erreur : %s\n' "$*" >&2; exit 1; }
log() { printf '==> %s\n' "$*" >&2; }

[ "$(id -u)" -eq 0 ] || die "à lancer en root"
[ -d "$DATA_DIR" ] || die "$DATA_DIR introuvable"

export_pack() {
  local dest="${1:--}" items=()
  for p in "${PARTS[@]}"; do [ -d "$DATA_DIR/$p" ] && items+=("$p"); done
  [ -f "$DATA_DIR/state/games.csv" ] && items+=("state/games.csv")
  [ ${#items[@]} -gt 0 ] || die "rien à exporter dans $DATA_DIR"
  log "Export de : ${items[*]}"
  # Les ROMs sont déjà compressées : archive tar simple (rapide, pas de recompression).
  if [ "$dest" = - ]; then
    tar -C "$DATA_DIR" --exclude='.upload-*' --exclude='*.tmp' -cf - "${items[@]}"
  else
    tar -C "$DATA_DIR" --exclude='.upload-*' --exclude='*.tmp' -cf "$dest" "${items[@]}"
    log "Pack créé : $dest ($(du -h "$dest" | cut -f1))"
  fi
}

# Archive tar sur l'entrée standard → $DATA_DIR, sans écraser l'existant. La liste des jeux du
# pack est mise de côté (state/.games-import.csv) pour être fusionnée par l'API.
untar() {
  rm -f "$DATA_DIR/state/.games-import.csv"
  tar -C "$DATA_DIR" --no-same-owner --skip-old-files \
    --transform 's|^state/games\.csv$|state/.games-import.csv|' \
    --transform 's|^\./state/games\.csv$|state/.games-import.csv|' -xf -
}

wait_api() {
  for _ in $(seq 1 30); do curl -fs -m 2 http://127.0.0.1/api/v1/health >/dev/null 2>&1 && return 0; sleep 1; done
  return 1
}

import_pack() {
  local src="${1:-}" before after
  [ -n "$src" ] || die "source manquante (fichier .tar, dossier, URL ou -)"
  mkdir -p "$DATA_DIR/state"
  before="$(find "$DATA_DIR/roms" -type f 2>/dev/null | wc -l)"
  case "$src" in
    -) log "Import depuis l'entrée standard"; untar ;;
    http://*|https://*) log "Téléchargement de $src"; curl -fsSL "$src" | untar ;;
    *)
      if [ -d "$src" ]; then log "Import du dossier $src"; tar -C "$src" -cf - . | untar
      elif [ -f "$src" ]; then log "Import de $src"; untar < "$src"
      else die "source introuvable : $src"; fi ;;
  esac
  chown -R "$USER_NAME:$USER_NAME" "$DATA_DIR"
  after="$(find "$DATA_DIR/roms" -type f 2>/dev/null | wc -l)"
  log "ROMs : $before → $after"

  if systemctl is-active -q naomox 2>/dev/null && wait_api; then
    if [ -f "$DATA_DIR/state/.games-import.csv" ]; then
      if curl -fs -X POST -H 'X-Requested-With: naomox' -F "file=@$DATA_DIR/state/.games-import.csv" \
        "http://127.0.0.1/api/v1/games/import?replace=false" >/dev/null; then
        log "Liste des jeux fusionnée (favoris, jeux désactivés…)"
      fi
    fi
    if curl -fs -X POST -H 'X-Requested-With: naomox' http://127.0.0.1/api/v1/games/scan >/dev/null; then
      log "Nouvelles ROMs détectées"
    else
      log "Pensez à Réglages → Jeux → Scanner"
    fi
  else
    log "Service arrêté : la liste des jeux sera à fusionner via Réglages → Jeux → Importer"
  fi
  rm -f "$DATA_DIR/state/.games-import.csv"
}

case "${1:-}" in
  export) export_pack "${2:--}" ;;
  import) import_pack "${2:-}" ;;
  *) sed -n '2,17p' "$0" >&2; exit 1 ;;
esac
