#!/usr/bin/env bash
# NAOMOX — installation complète sur Proxmox VE en une commande (sur l'hôte, en root) :
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/metisnc/NAOMOX/main/deploy/proxmox-install.sh)"
#
# Crée un conteneur LXC Debian non privilégié, y installe la dernière version publiée de
# NAOMOX et affiche l'adresse de l'interface. Ne modifie rien d'autre sur l'hôte que : le
# nouveau conteneur et, si besoin, le téléchargement d'un template Debian standard.
#
# Deux façons de l'utiliser :
#   - à la main : un assistant (fenêtres whiptail) propose « Installation rapide » (valeurs par
#     défaut) ou « Installation personnalisée » (ID, nom, mots de passe, réseau, stockage…) ;
#   - automatisée (script, IA) : NAOMOX_YES=1 + variables ci-dessous, aucune question.
#
# Variables (toutes facultatives ; elles servent aussi de valeurs proposées par l'assistant) :
#   CTID=…            ID du conteneur (défaut : prochain ID libre)
#   HOSTNAME_CT=…     nom du conteneur (défaut : naomox → http://naomox.local)
#   IP=dhcp | 192.168.1.50/24   GW=192.168.1.1   DNS=…   BRIDGE=vmbr0   VLAN=…
#   STORAGE=…         stockage des disques (défaut : premier stockage acceptant les CT)
#   ROOTFS_GB=8  DATA_GB=64  CORES=2  MEMORY=1024
#   ROOT_PASSWORD=naomox                   mot de passe root du conteneur
#   SSH_PASSWORD=…    mot de passe SSH/SFTP du compte naomox (défaut : celui de root ; vide = pas d'accès SSH)
#   NAOMOX_VERSION=latest | v0.2.0         version à installer
#   GITHUB_TOKEN=…    jeton GitHub (lecture), seulement pour un dépôt privé ou une fourche
#   NAOMOX_YES=1      aucune question (installation automatisée)
#   NAOMOX_DRY_RUN=1  affiche ce qui serait fait, sans rien créer
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
SSH_PASSWORD="${SSH_PASSWORD-$ROOT_PASSWORD}"
STORAGE="${STORAGE:-$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $3=="active" {print $1; exit}')}"

# --- Assistant interactif (whiptail) ------------------------------------------------------------
# Actif quand le script est lancé à la main (terminal) et que NAOMOX_YES n'est pas défini.
INTERACTIVE=0
if [ "${NAOMOX_YES:-0}" != 1 ] && [ -t 1 ] && [ -r /dev/tty ] && command -v whiptail >/dev/null; then
  INTERACTIVE=1
fi
TITLE="NAOMOX — installation sur Proxmox"

# wt <args…> : whiptail sur le terminal ; la réponse sort sur stdout.
wt() { whiptail --backtitle "$TITLE" "$@" 3>&1 1>&2 2>&3 </dev/tty; }
cancelled() { clear; die "installation annulée"; }

ask() { # ask <titre> <question> <défaut> → valeur
  wt --title "$1" --inputbox "$2" 11 72 "$3" || cancelled
}

ask_valid() { # ask_valid <titre> <question> <défaut> <regex> <message d'erreur>
  local v
  while true; do
    v="$(ask "$1" "$2" "$3")"
    if [[ "$v" =~ $4 ]]; then printf '%s' "$v"; return; fi
    wt --title "$1" --msgbox "$5" 9 64 || true
    set -- "$1" "$2" "$v" "$4" "$5"
  done
}

ask_password() { # ask_password <titre> <texte> → mot de passe confirmé (au moins 5 caractères)
  local p1 p2
  while true; do
    p1="$(wt --title "$1" --passwordbox "$2" 11 72)" || cancelled
    p2="$(wt --title "$1" --passwordbox "Confirmez le mot de passe :" 10 72)" || cancelled
    if [ "$p1" != "$p2" ]; then wt --title "$1" --msgbox "Les deux saisies sont différentes." 8 60 || true; continue; fi
    if [ "${#p1}" -lt 5 ]; then wt --title "$1" --msgbox "Au moins 5 caractères." 8 60 || true; continue; fi
    printf '%s' "$p1"; return
  done
}

wizard_custom() {
  local v free choices=() line name avail
  while true; do
    v="$(ask_valid "Conteneur" "Numéro (ID) du conteneur :" "$CTID" '^[0-9]{3,9}$' "Un nombre (100 ou plus).")"
    if pct status "$v" >/dev/null 2>&1; then
      wt --title "Conteneur" --msgbox "Le conteneur $v existe déjà, choisissez un autre numéro." 8 64 || true
      CTID="$(pvesh get /cluster/nextid)"; continue
    fi
    CTID="$v"; break
  done
  HOSTNAME_CT="$(ask_valid "Nom" "Nom du conteneur (l'interface sera sur http://<nom>.local) :" "$HOSTNAME_CT" \
    '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$' "Lettres minuscules, chiffres et tirets.")"

  if wt --title "Mot de passe root" --yesno "Mot de passe root du conteneur (console Proxmox) :\n\nGarder « naomox » ?" 10 64; then
    ROOT_PASSWORD=naomox
  else
    ROOT_PASSWORD="$(ask_password "Mot de passe root" "Nouveau mot de passe root du conteneur :")"
  fi
  if wt --title "Accès SSH / SFTP" --yesno "Ouvrir l'accès SSH/SFTP du compte « naomox » ?\n(pratique pour copier les ROMs avec WinSCP ou FileZilla ; même mot de passe que root)" 11 72; then
    SSH_PASSWORD="$ROOT_PASSWORD"
  else
    SSH_PASSWORD=""
  fi

  # Réseau
  # Bridges utilisables (les fwbr*/fwpr*/fwln* sont les bridges internes du pare-feu Proxmox).
  mapfile -t bridges < <(ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | sed 's/@.*//' \
    | grep -Ev '^(fwbr|fwpr|fwln|tap|veth)' | sort)
  if [ "${#bridges[@]}" -gt 1 ]; then
    choices=(); for b in "${bridges[@]}"; do choices+=("$b" ""); done
    BRIDGE="$(wt --title "Réseau" --default-item "$BRIDGE" --menu "Bridge réseau (le même que les bornes) :" 16 64 6 "${choices[@]}")" || cancelled
  fi
  if wt --title "Réseau" --yes-button "DHCP" --no-button "IP fixe" --yesno "Adresse IP du conteneur :\n\nDHCP (automatique) ou IP fixe ?" 10 64; then
    IP=dhcp; GW=""
  else
    IP="$(ask_valid "Réseau" "IP fixe avec masque (ex. 192.168.1.50/24) :" "$([ "$IP" = dhcp ] && echo "" || echo "$IP")" \
      '^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$' "Format attendu : 192.168.1.50/24")"
    GW="$(ask_valid "Réseau" "Passerelle (ex. 192.168.1.1) :" "$GW" '^([0-9]{1,3}\.){3}[0-9]{1,3}$' "Format attendu : 192.168.1.1")"
    DNS="$(ask_valid "Réseau" "Serveur DNS (vide = celui de l'hôte) :" "$DNS" '^(([0-9]{1,3}\.){3}[0-9]{1,3})?$' "Format attendu : 192.168.1.1 ou vide")"
  fi
  VLAN="$(ask_valid "Réseau" "VLAN (vide si aucun) :" "$VLAN" '^([0-9]{1,4})?$' "Un numéro de VLAN, ou vide.")"

  # Stockage : liste des stockages actifs acceptant les conteneurs, avec l'espace libre.
  choices=()
  while read -r line; do
    name="$(awk '{print $1}' <<<"$line")"; avail="$(awk '{printf "%.0f Go libres", $6/1048576}' <<<"$line")"
    choices+=("$name" "$avail")
  done < <(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $3=="active"')
  [ "${#choices[@]}" -gt 0 ] || die "aucun stockage actif n'accepte les conteneurs"
  STORAGE="$(wt --title "Stockage" --default-item "$STORAGE" --menu "Stockage des disques du conteneur :" 16 64 6 "${choices[@]}")" || cancelled
  ROOTFS_GB="$(ask_valid "Stockage" "Disque système (Go) :" "$ROOTFS_GB" '^[0-9]+$' "Un nombre de Go.")"
  free="$(pvesm status -storage "$STORAGE" 2>/dev/null | awk 'NR==2 {printf "%.0f", $6/1048576}')"
  DATA_GB="$(ask_valid "Stockage" "Disque des données en Go (ROMs, vidéos…, ${free:-?} Go libres) :" "$DATA_GB" '^[0-9]+$' "Un nombre de Go.")"

  CORES="$(ask_valid "Ressources" "Nombre de vCPU :" "$CORES" '^[1-9][0-9]?$' "Un nombre entre 1 et 99.")"
  MEMORY="$(ask_valid "Ressources" "Mémoire (Mo) :" "$MEMORY" '^[0-9]{3,6}$' "Un nombre de Mo (512 minimum conseillé).")"
}

if [ "$INTERACTIVE" = 1 ]; then
  mode="$(wt --title "$TITLE" --menu "Netbooter NetDIMM pour Naomi, Naomi 2, Atomiswave, Chihiro et Triforce.\n\nType d'installation :" 15 76 2 \
    "rapide" "Valeurs par défaut (DHCP, $CORES vCPU, $DATA_GB Go de données)" \
    "personnalisée" "Choisir ID, nom, mots de passe, réseau, stockage…")" || cancelled
  [ "$mode" = "personnalisée" ] && wizard_custom
  clear
fi

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
if [ -z "$TEMPLATE" ] && [ "${NAOMOX_DRY_RUN:-0}" = 1 ]; then
  TEMPLATE="(template Debian à télécharger)"
elif [ -z "$TEMPLATE" ]; then
  msg "Téléchargement du template Debian standard"
  pveam update >/dev/null
  name="$(pveam available --section system | awk '{print $2}' | grep -E '^debian-13-standard' | sort -V | tail -1)"
  [ -n "$name" ] || name="$(pveam available --section system | awk '{print $2}' | grep -E '^debian-12-standard' | sort -V | tail -1)"
  [ -n "$name" ] || die "aucun template Debian 12/13 disponible"
  pveam download local "$name" >/dev/null
  TEMPLATE="local:vztmpl/$name"
fi

# --- Récapitulatif -----------------------------------------------------------------------------
if [ -n "$SSH_PASSWORD" ]; then ssh_label="compte naomox ouvert"; else ssh_label="désactivé"; fi
cat <<EOF

  ${c_g}NAOMOX $tag${c_0} — netbooter NetDIMM
  Conteneur  : $CTID ($HOSTNAME_CT), $CORES vCPU, $MEMORY Mo
  Disques    : $STORAGE — système ${ROOTFS_GB} Go + données ${DATA_GB} Go (/srv/naomox)
  Réseau     : $BRIDGE${VLAN:+ (VLAN $VLAN)}, IP $IP${GW:+, passerelle $GW}
  SSH/SFTP   : $ssh_label
  Template   : $TEMPLATE

EOF
if [ "${NAOMOX_DRY_RUN:-0}" = 1 ]; then
  ok "simulation (NAOMOX_DRY_RUN=1) : rien n'a été créé"
  exit 0
fi
if [ "$INTERACTIVE" = 1 ]; then
  wt --title "Récapitulatif" --yes-button "Installer" --no-button "Annuler" --yesno "NAOMOX $tag

Conteneur : $CTID ($HOSTNAME_CT), $CORES vCPU, $MEMORY Mo
Disques   : $STORAGE — système $ROOTFS_GB Go + données $DATA_GB Go
Réseau    : $BRIDGE${VLAN:+ (VLAN $VLAN)}, IP $IP${GW:+, passerelle $GW}
SSH/SFTP  : $ssh_label

Créer le conteneur et installer NAOMOX ?" 17 74 || cancelled
  clear
elif [ "${NAOMOX_YES:-0}" != 1 ]; then
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
pct exec "$CTID" -- env NAOMOX_SSH_PASSWORD="$SSH_PASSWORD" bash -c '
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
if [ -n "$SSH_PASSWORD" ]; then echo "   SSH/SFTP  : ssh naomox@$addr  (mot de passe : $SSH_PASSWORD)"; fi
echo "   Ensuite   : déposer les ROMs dans /srv/naomox/roms puis Réglages → Jeux → Scanner"
