#!/usr/bin/env bash
# Création du conteneur LXC NAOMOX — à exécuter SUR L'HÔTE Proxmox (root).
# Préférer deploy/proxmox-install.sh (une commande). Ce script ne crée que le conteneur.
# Ne modifie rien d'autre que le conteneur créé ; échoue si l'ID existe déjà.
#
#   CTID=120 IP=192.168.1.230/24 GW=192.168.1.1 ./pct-create.sh      (défaut : ID libre, DHCP)
set -euo pipefail

CTID="${CTID:-$(pvesh get /cluster/nextid)}"
HOSTNAME="${HOSTNAME_CT:-naomox}"
IP="${IP:-dhcp}"
GW="${GW:-}"
DNS="${DNS:-}"
BRIDGE="${BRIDGE:-vmbr0}"
VLAN="${VLAN:-}"                       # ex. VLAN=30 si les bornes sont sur un VLAN
STORAGE="${STORAGE:-local-zfs}"
ROOTFS_GB="${ROOTFS_GB:-8}"
DATA_GB="${DATA_GB:-64}"               # volume /srv/naomox (ROMs, médias, état)
CORES="${CORES:-2}"
MEMORY="${MEMORY:-1024}"
TEMPLATE="${TEMPLATE:-local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst}"
SSH_KEY="${SSH_KEY:-}"                 # chemin d'une clé publique à autoriser pour root
ROOT_PASSWORD="${ROOT_PASSWORD:-naomox}" # mot de passe root du CT (console Proxmox)
NOTES="${NOTES:-$(dirname "$0")/proxmox-notes.md}"  # notes Proxmox du CT (onglet Notes)

pct status "$CTID" >/dev/null 2>&1 && { echo "Le CT $CTID existe déjà, abandon." >&2; exit 1; }
pveam list "${TEMPLATE%%:*}" | grep -q "${TEMPLATE#*:}" || {
  echo "Template absent : $TEMPLATE (pveam update && pveam download local <template>)" >&2; exit 1; }

if [ "$IP" = dhcp ]; then net="name=eth0,bridge=${BRIDGE},ip=dhcp,firewall=0"; else net="name=eth0,bridge=${BRIDGE},ip=${IP},gw=${GW},firewall=0"; fi
[ -n "$VLAN" ] && net="${net},tag=${VLAN}"

args=(
  --hostname "$HOSTNAME"
  --unprivileged 1 --features nesting=1
  --cores "$CORES" --memory "$MEMORY" --swap 512
  --rootfs "${STORAGE}:${ROOTFS_GB}"
  --mp0 "${STORAGE}:${DATA_GB},mp=/srv/naomox,backup=1"
  --net0 "$net"
  --onboot 1 --tags naomox
  --password "$ROOT_PASSWORD"
)
[ -n "$DNS" ] && args+=(--nameserver "$DNS")
[ -n "$SSH_KEY" ] && args+=(--ssh-public-keys "$SSH_KEY")
if [ -f "$NOTES" ]; then
  args+=(--description "$(cat "$NOTES")")
else
  args+=(--description "NAOMOX - netbooter NetDIMM (Naomi/Chihiro/Triforce)")
fi

pct create "$CTID" "$TEMPLATE" "${args[@]}"
pct start "$CTID"
echo "CT $CTID créé et démarré. Étape suivante : copier le dépôt dans le CT puis lancer deploy/install.sh."
