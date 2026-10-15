#!/usr/bin/env bash
# Création du conteneur LXC NAOMOX — à exécuter SUR L'HÔTE Proxmox (root).
# Valeurs par défaut = déploiement de référence (CT 10230, 10.185.10.230).
# Ne modifie rien d'autre que le conteneur créé ; échoue si l'ID existe déjà.
#
#   CTID=10230 IP=10.185.10.230/24 GW=10.185.10.254 ./pct-create.sh
set -euo pipefail

CTID="${CTID:-10230}"
HOSTNAME="${HOSTNAME_CT:-naomox}"
IP="${IP:-10.185.10.230/24}"
GW="${GW:-10.185.10.254}"
DNS="${DNS:-10.185.10.254}"
BRIDGE="${BRIDGE:-vmbr0}"
VLAN="${VLAN:-}"                       # ex. VLAN=30 si les bornes sont sur un VLAN
STORAGE="${STORAGE:-local-zfs}"
ROOTFS_GB="${ROOTFS_GB:-8}"
DATA_GB="${DATA_GB:-64}"               # volume /srv/naomox (ROMs, médias, état)
CORES="${CORES:-2}"
MEMORY="${MEMORY:-1024}"
TEMPLATE="${TEMPLATE:-local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst}"
SSH_KEY="${SSH_KEY:-}"                 # chemin d'une clé publique à autoriser pour root

pct status "$CTID" >/dev/null 2>&1 && { echo "Le CT $CTID existe déjà, abandon." >&2; exit 1; }
pveam list "${TEMPLATE%%:*}" | grep -q "${TEMPLATE#*:}" || {
  echo "Template absent : $TEMPLATE (pveam update && pveam download local <template>)" >&2; exit 1; }

net="name=eth0,bridge=${BRIDGE},ip=${IP},gw=${GW},firewall=0"
[ -n "$VLAN" ] && net="${net},tag=${VLAN}"

args=(
  --hostname "$HOSTNAME"
  --unprivileged 1 --features nesting=1
  --cores "$CORES" --memory "$MEMORY" --swap 512
  --rootfs "${STORAGE}:${ROOTFS_GB}"
  --mp0 "${STORAGE}:${DATA_GB},mp=/srv/naomox,backup=1"
  --net0 "$net" --nameserver "$DNS"
  --onboot 1 --tags naomox
  --description "NAOMOX - netbooter NetDIMM (Naomi/Chihiro/Triforce)"
)
[ -n "$SSH_KEY" ] && args+=(--ssh-public-keys "$SSH_KEY")

pct create "$CTID" "$TEMPLATE" "${args[@]}"
pct start "$CTID"
echo "CT $CTID créé et démarré. Étape suivante : copier le dépôt dans le CT puis lancer deploy/install.sh."
