#!/usr/bin/env bash
# NAOMOX — installation complète sur Proxmox VE en une commande (sur l'hôte, en root) :
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/metisnc/NAOMOX/main/deploy/proxmox-install.sh)"
#
# Crée un conteneur LXC Debian non privilégié (ID libre, DHCP par défaut), y installe la
# dernière version publiée de NAOMOX et affiche l'adresse de l'interface. Ne modifie rien
# d'autre sur l'hôte que : le nouveau conteneur et, si besoin, le téléchargement d'un
# template Debian standard.
#
# Variables facultatives (à placer devant la commande) :
#   CTID=…            ID du conteneur (défaut : prochain ID libre)
#   HOSTNAME_CT=…     nom du conteneur (défaut : naomox → http://naomox.local)
#   IP=dhcp | 192.168.1.50/24   GW=192.168.1.1   DNS=…   BRIDGE=vmbr0   VLAN=…
#   STORAGE=…         stockage des disques (défaut : premier stockage acceptant les CT)
#   ROOTFS_GB=8  DATA_GB=64  CORES=2  MEMORY=1024
#   ROOT_PASSWORD=naomox                   mot de passe root du conteneur
#   NAOMOX_VERSION=latest | v0.2.0         version à installer
#   GITHUB_TOKEN=…    jeton GitHub (lecture) tant que le dépôt est privé
#   NAOMOX_YES=1      ne pas demander de confirmation
set -euo pipefail

REPO="${NAOMOX_REPO:-metisnc/NAOMOX}"
VERSION="${NAOMOX_VERSION:-latest}"

c_y=$'\033[1;33m'; c_g=$'\033[1;32m'; c_r=$'\033[1;31m'; c_0=$'\033[0m'
msg() { printf '%s==>%s %s\n' "$c_y" "$c_0" "$*"; }
ok() { printf '%s✓%s %s\n' "$c_g" "$c_0" "$*"; }
die() { printf '%sErreur :%s %s\n' "$c_r" "$c_0" "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "à lancer en root sur l'hôte Proxmox"
command -v pct >/dev/null && command -v pvesh >/dev/null || die "pct / pvesh introuvables : ce script s'exécute sur un hôte Proxmox VE"

CTID="${CTID:-$(pvesh get /cluster/nextid)}"
HOSTNAME_CT="${HOSTNAME_CT:-naomox}"
BRIDGE="${BRIDGE:-vmbr0}"
IP="${IP:-dhcp}"
GW="${GW:-}"
DNS="${DNS:-}"
VLAN="${VLAN:-}"
ROOTFS_GB="${ROOTFS_GB:-8}"
DATA_GB="${DATA_GB:-64}"
CORES="${CORES:-2}"
MEMORY="${MEMORY:-1024}"
ROOT_PASSWORD="${ROOT_PASSWORD:-naomox}"
STORAGE="${STORAGE:-$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $3=="active" {print $1; exit}')}"

pct status "$CTID" >/dev/null 2>&1 && die "le conteneur $CTID existe déjà (CTID=… pour en choisir un autre)"
[ -n "$STORAGE" ] || die "aucun stockage actif n'accepte les conteneurs (STORAGE=…)"
ip link show "$BRIDGE" >/dev/null 2>&1 || die "bridge $BRIDGE introuvable (BRIDGE=…)"
if [ "$IP" != dhcp ] && [ -z "$GW" ]; then die "IP fixe : préciser aussi GW=…"; fi

# --- Version à installer --------------------------------------------------------------------
auth=()
[ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
api="https://api.github.com/repos/$REPO/releases/$([ "$VERSION" = latest ] && echo latest || echo "tags/$VERSION")"
release="$(curl -fsSL "${auth[@]}" -H "Accept: application/vnd.github+json" "$api")" \
  || die "version $VERSION introuvable sur github.com/$REPO (dépôt privé ? définir GITHUB_TOKEN=…)"
read -r tag asset_api < <(python3 -c '
import json, sys
r = json.load(sys.stdin)
url = next((a["url"] for a in r.get("assets", []) if a["name"] == "naomox.tar.gz"), "")
print(r.get("tag_name", "?"), url)' <<<"$release")
[ -n "$asset_api" ] || die "archive naomox.tar.gz absente de la version $tag"

# --- Template Debian ---------------------------------------------------------------------------
TEMPLATE="${TEMPLATE:-$(pveam list local 2>/dev/null | awk '{print $1}' | grep -E 'debian-1[23]-standard' | sort -V | tail -1)}"
if [ -z "$TEMPLATE" ]; then
  msg "Téléchargement du template Debian standard"
  pveam update >/dev/null
  name="$(pveam available --section system | awk '{print $2}' | grep -E '^debian-13-standard' | sort -V | tail -1)"
  [ -n "$name" ] || name="$(pveam available --section system | awk '{print $2}' | grep -E '^debian-12-standard' | sort -V | tail -1)"
  [ -n "$name" ] || die "aucun template Debian 12/13 disponible"
  pveam download local "$name" >/dev/null
  TEMPLATE="local:vztmpl/$name"
fi

# --- Récapitulatif -----------------------------------------------------------------------------
cat <<EOF

  ${c_g}NAOMOX $tag${c_0} — netbooter NetDIMM
  Conteneur  : $CTID ($HOSTNAME_CT), $CORES vCPU, $MEMORY Mo
  Disques    : $STORAGE — système ${ROOTFS_GB} Go + données ${DATA_GB} Go (/srv/naomox)
  Réseau     : $BRIDGE${VLAN:+ (VLAN $VLAN)}, IP $IP${GW:+, passerelle $GW}
  Template   : $TEMPLATE

EOF
if [ "${NAOMOX_YES:-0}" != 1 ]; then
  read -r -p "Créer le conteneur et installer NAOMOX ? [O/n] " answer </dev/tty || answer=n
  case "${answer:-o}" in o|O|y|Y|oui|yes) ;; *) die "annulé" ;; esac
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

msg "Téléchargement de NAOMOX $tag"
curl -fsSL "${auth[@]}" -H "Accept: application/octet-stream" -o "$work/naomox.tar.gz" "$asset_api"
tar -xzf "$work/naomox.tar.gz" -C "$work" deploy/proxmox-notes.md 2>/dev/null || true

msg "Création du conteneur $CTID"
net="name=eth0,bridge=$BRIDGE,firewall=0"
if [ "$IP" = dhcp ]; then net="$net,ip=dhcp"; else net="$net,ip=$IP,gw=$GW"; fi
[ -n "$VLAN" ] && net="$net,tag=$VLAN"
args=(
  --hostname "$HOSTNAME_CT"
  --unprivileged 1 --features nesting=1
  --cores "$CORES" --memory "$MEMORY" --swap 512
  --rootfs "$STORAGE:$ROOTFS_GB"
  --mp0 "$STORAGE:$DATA_GB,mp=/srv/naomox,backup=1"
  --net0 "$net"
  --onboot 1 --tags naomox
  --password "$ROOT_PASSWORD"
)
[ -n "$DNS" ] && args+=(--nameserver "$DNS")
[ -f "$work/deploy/proxmox-notes.md" ] && args+=(--description "$(cat "$work/deploy/proxmox-notes.md")")
pct create "$CTID" "$TEMPLATE" "${args[@]}" >/dev/null
pct start "$CTID"

msg "Attente du réseau dans le conteneur"
for _ in $(seq 1 60); do
  if pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1; then break; fi
  sleep 2
done
pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1 || die "le conteneur n'a pas accès à Internet (DHCP, passerelle, DNS ?)"

msg "Installation de NAOMOX dans le conteneur (quelques minutes)"
pct push "$CTID" "$work/naomox.tar.gz" /root/naomox.tar.gz
pct exec "$CTID" -- bash -c '
  set -e
  export DEBIAN_FRONTEND=noninteractive
  rm -rf /root/naomox-src && mkdir -p /root/naomox-src
  tar -xzf /root/naomox.tar.gz -C /root/naomox-src && rm -f /root/naomox.tar.gz
  bash /root/naomox-src/deploy/install.sh
'

addr="$(pct exec "$CTID" -- hostname -I | awk '{print $1}')"
echo
ok "NAOMOX $tag installé dans le conteneur $CTID"
echo "   Interface : http://$HOSTNAME_CT.local  ou  http://$addr"
echo "   Console   : root / $ROOT_PASSWORD   (onglet Notes du conteneur pour le reste)"
echo "   Ensuite   : déposer les ROMs dans /srv/naomox/roms puis Réglages → Jeux → Scanner"
