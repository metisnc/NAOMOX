# CLAUDE.md — WiPiNetbooter-NG (cible Proxmox)

Netbooter pour cartes Sega Naomi / Naomi 2 / Chihiro / Triforce équipées d'une NetDIMM.
Fork de [chunksin/WiPiNetbooter](https://github.com/chunksin/WiPiNetbooter) (Raspberry Pi),
en cours de portage vers un **conteneur LXC Debian 12 sur Proxmox**, piloté depuis une
interface web (téléphone / tablette).

## État du dépôt

- **Code hérité Pi** (référence, sera retiré une fois le nouveau backend fonctionnel) :
  - `var/www/html/` : interface PHP d'origine + `launcher/` (frontend 3.5" du fork).
  - `sbin/piforce/` : scripts Python (`wipiloader.py`, …) et `*mode.txt` (options globales).
  - `sbin/piforce/dm_netboot/` : bibliothèque **netdimm** de DragonMinded (domaine public),
    Python 3, implémente le protocole NetDIMM (TCP 10703). **C'est le cœur réutilisé.**
  - `boot/`, `etc/`, `root/`, `usr/` : fichiers système de l'image Pi (DietPi).
- **Nouveau code** (à venir) : `backend/`, `frontend/`, `deploy/`, `docs/`.

## Documentation

- `docs/AUDIT.md` — audit de l'image WiPi 6.1.4 et du fork (flux de lancement, dépendances Pi).
- `docs/ARCHITECTURE.md` — architecture cible et décisions.
- `docs/DEPLOY.md` — (phase 4) déploiement Proxmox pas à pas.

## Décisions prises (validées par l'utilisateur)

1. Cible **Proxmox uniquement**. Pas de compatibilité Pi à maintenir.
2. Seules les fonctions **NetDIMM / réseau** sont conservées : netboot, mode serveur
   (ensure), time hack (zero-key), mise à jour firmware NetDIMM, infos DIMM, menu OSM
   (netbootmenu), gestion des bornes et des jeux. Tout le matériel Pi est abandonné
   (écran, LCD, GPIO/relais, rotary, Wi-Fi AP, Bluetooth, NFC, card emulators, OpenJVS/FFB,
   cycraft). Voir `docs/AUDIT.md` §6.
3. Interface **entièrement réécrite**, mobile-first, servie par le backend. Plus de PHP, plus de sudo.
4. Toutes les cartes supportées ; **plan d'adressage modifiable** (défaut `10.0.0.0/24`).
5. ROMs, firmwares et médias stockés **dans le conteneur** (`/srv/wipi`, configurable).
6. Binaires déjà commités dans l'historique : retirés de l'arbre plus tard, **pas de
   réécriture d'historique** sans accord explicite.

## Règles de travail

- Ne jamais modifier l'image d'origine (`../WiPi6-1-4*`). Lecture seule ; montage `.img`
  uniquement via `losetup -P -r` + `mount -o ro` (sur un hôte Linux).
- Ne jamais commiter de ROM, firmware Sega, média de jeu ou binaire propriétaire.
  Les homebrew DragonMinded (`dm_netboot/homebrew/`) sont du domaine public et tolérés.
- Une branche par phase : `feat/proxmox-<phase>`. Petits commits atomiques, messages clairs.
- Signaler (ne pas supprimer silencieusement) toute fonction dépendant du matériel Pi.
- Ne pas modifier le protocole NetDIMM.

## Commandes

_(à compléter en phase 3 : pytest, ruff, build frontend, lancement du mock NetDIMM)_
