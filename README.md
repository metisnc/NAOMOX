# NAOMOX

Netbooter web pour cartes **Sega Naomi, Naomi 2, Chihiro et Triforce** équipées d'une NetDIMM.
On choisit un jeu sur son téléphone ou sa tablette, NAOMOX envoie la ROM à la borne par le
réseau et affiche la progression en direct.

Portage de [WiPiNetbooter](https://github.com/chunksin/WiPiNetbooter) hors Raspberry Pi, pour
un conteneur LXC Proxmox. Le protocole NetDIMM est celui de la bibliothèque `netdimm` de
DragonMinded (domaine public).

- Lancement de jeux avec file d'attente par borne, annulation, relance et vérification de l'envoi.
- Plusieurs bornes, plan d'adressage libre, recherche automatique sur le réseau.
- Time hack (sans PIC zero-key), mode serveur, démarrage automatique.
- Infos NetDIMM, mise à jour du firmware (4.01 à 4.03), diagnostic Naomi.
- Liste des jeux compatible `romsinfo.csv` de WiPi, envoi de fichiers depuis l'interface.

| Doc | Contenu |
|---|---|
| [docs/DEPLOY.md](docs/DEPLOY.md) | installation sur Proxmox (LXC), dépannage |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | architecture et décisions |
| [docs/TESTING.md](docs/TESTING.md) | tests automatisés et checklist sur borne |
| [docs/AUDIT.md](docs/AUDIT.md) | audit de WiPiNetbooter 6.1.4 |

## Installation sur Proxmox en une commande

Dans le **shell de l'hôte Proxmox** (Datacenter → nœud → Shell), en root :

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/metisnc/NAOMOX/main/deploy/proxmox-install.sh)"
```

Un **assistant** s'ouvre alors :

- **Installation rapide** : valeurs par défaut (ID libre, IP en DHCP, 8 Go système + 64 Go de
  données), un récapitulatif, et c'est parti ;
- **Installation personnalisée** : il demande l'ID, le nom, le mot de passe root, l'accès SSH/SFTP,
  le réseau (DHCP ou IP fixe, bridge, VLAN), le stockage, la taille des disques, les vCPU et la RAM.

À la fin, l'adresse de l'interface s'affiche : **http://naomox.local**. Login console du conteneur :
`root` / `naomox` ; SSH/SFTP (copie des ROMs) : `naomox` / `naomox` (changer avec `passwd`).
Tout est rappelé dans l'onglet **Notes** du conteneur.

### Installation automatisée (script, IA)

Sans aucune question, avec `NAOMOX_YES=1` et les variables voulues :

```sh
NAOMOX_YES=1 IP=192.168.1.50/24 GW=192.168.1.1 DATA_GB=128   bash -c "$(curl -fsSL https://raw.githubusercontent.com/metisnc/NAOMOX/main/deploy/proxmox-install.sh)"
```

`NAOMOX_DRY_RUN=1` affiche ce qui serait fait, sans rien créer.

| Variable | Défaut | Rôle |
|---|---|---|
| `CTID` | prochain ID libre | numéro du conteneur |
| `HOSTNAME_CT` | `naomox` | nom du conteneur (→ `http://<nom>.local`) |
| `IP` / `GW` / `DNS` | `dhcp` | IP fixe `192.168.1.50/24` avec sa passerelle |
| `BRIDGE` / `VLAN` | `vmbr0` / — | réseau des bornes |
| `STORAGE` | premier stockage CT actif | stockage des disques |
| `ROOTFS_GB` / `DATA_GB` | `8` / `64` | tailles des disques (ROMs dans les données) |
| `ROOT_PASSWORD` | `naomox` | mot de passe root du conteneur |
| `SSH_PASSWORD` | = `ROOT_PASSWORD` | mot de passe SSH/SFTP du compte `naomox` (vide = pas d'accès SSH) |
| `NAOMOX_VERSION` | `latest` | version publiée à installer (`v0.1.0`…) |
| `CONTENT` | — | pack de contenu à importer (voir plus bas) |
| `NAOMOX_YES` | — | `1` = aucune question (automatisation) |
| `NAOMOX_DRY_RUN` | — | `1` = simulation, rien n'est créé |

> Le conteneur a besoin d'un accès Internet pendant l'installation (paquets Debian et Python).

Ensuite : déposer les ROMs dans `/srv/naomox/roms` (ou Réglages → Fichiers), Réglages → Jeux →
**Scanner**, puis Bornes → **Rechercher**.

## Réutiliser ses ROMs et vidéos : le pack de contenu

Pour installer un nouveau NAOMOX avec les ROMs, jaquettes, vidéos, logos, firmwares et la liste
des jeux (favoris, jeux désactivés) d'une installation existante — sans backup/restore du
conteneur :

```sh
# 1. Sur l'hôte Proxmox : créer le pack depuis un NAOMOX existant (ici le CT 120), vers un NAS monté
pct exec 120 -- naomox-content export - > /mnt/pve/mon-nas/naomox-content.tar

# 2. Nouvelle installation avec ce pack (ou réponse à la question « Contenu » de l'assistant)
CONTENT=/mnt/pve/mon-nas/naomox-content.tar bash -c "$(curl -fsSL https://raw.githubusercontent.com/metisnc/NAOMOX/main/deploy/proxmox-install.sh)"

# Ou dans un NAOMOX déjà installé
pct exec 121 -- naomox-content import - < /mnt/pve/mon-nas/naomox-content.tar
```

`CONTENT` accepte un fichier `.tar`, un dossier (contenant `roms/`, `media/`, `firmware/`) ou une URL
`http(s)`. L'import ajoute sans écraser, remet les droits et relance la détection des jeux ; le disque
de données est agrandi automatiquement si le pack est plus gros. Les bornes ne sont pas dans le pack.

> ⚠ Les ROMs, vidéos et firmwares Sega sont protégés par le droit d'auteur : gardez le pack sur
> votre propre stockage (NAS, partage privé), ne le publiez jamais.

## Développement

Démarrage rapide depuis un poste de dev, avec un CT Debian déjà créé :

```sh
NAOMOX_HOST=root@<ip-du-ct> deploy/push.sh
```

Aucune ROM, aucun firmware Sega ni aucun média de jeu n'est fourni dans ce dépôt.

## Crédits des logos de systèmes (non inclus dans ce dépôt)

Les logos de systèmes sont des marques de leurs détenteurs (Sega, Sammy, Namco, Nintendo). Ils
ne sont pas distribués avec NAOMOX : on les dépose dans `/srv/naomox/media/systems/` (Réglages →
Fichiers → Logos systèmes). L'installation de référence utilise :

| Fichier | Source | Licence |
|---|---|---|
| `Sega Naomi.png` | [Wikimedia Commons — Sega NAOMI logo.png](https://commons.wikimedia.org/wiki/File:Sega_NAOMI_logo.png) | domaine public |
| `Sega Chihiro.svg` | [Wikimedia Commons — Sega Chihiro.svg](https://commons.wikimedia.org/wiki/File:Sega_Chihiro.svg), par Hipnosis183 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `Sega Triforce.svg` | [Wikimedia Commons — Triforce arcade.svg](https://commons.wikimedia.org/wiki/File:Triforce_arcade.svg) | domaine public |
| `Sega Naomi2.png`, `Sammy Atomiswave.png` | pack WiPiNetbooter 6.1 | — |
