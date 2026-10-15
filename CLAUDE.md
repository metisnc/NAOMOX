# CLAUDE.md — NAOMOX (ex-WiPiNetbooter-NG, cible Proxmox)

Netbooter pour cartes Sega Naomi / Naomi 2 / Chihiro / Triforce équipées d'une NetDIMM.
Fork de [chunksin/WiPiNetbooter](https://github.com/chunksin/WiPiNetbooter) (Raspberry Pi),
dépôt `metisnc/NAOMOX`, en cours de portage vers un **conteneur LXC Debian 13 sur Proxmox**,
piloté depuis une interface web (téléphone / tablette).

## Environnement de déploiement

- Proxmox **de production** `10.185.10.200` (PVE 9.2, nœud `pve`). **Seul le CT 10230 nous
  appartient** : ne jamais créer, modifier, arrêter ni télécharger quoi que ce soit d'autre
  (pas de template, pas de stockage, pas de bridge).
- CT **10230** `naomox` : LXC non privilégié, Debian 13 (Python 3.13), `eth0` sur `vmbr0` en
  `10.185.10.230/24` (passerelle et DNS `10.185.10.254`). rootfs de 8 Go et `mp0` de 64 Go
  montés sur `/srv/naomox` (`local-zfs`).
- Accès : `ssh -i ~/.ssh/naomox_ed25519 root@10.185.10.230`. Aucun identifiant n'est stocké
  dans le dépôt.
- Git Bash sous Windows : exporter `MSYS_NO_PATHCONV=1` avant tout appel à l'API Proxmox
  contenant un chemin `/…`, sinon le chemin est réécrit en `C:/Program Files/Git/…`.

## État du dépôt

- **Code hérité Pi** (référence, sera retiré une fois le nouveau backend fonctionnel) :
  - `var/www/html/` : interface PHP d'origine + `launcher/` (frontend 3.5" du fork).
  - `sbin/piforce/` : scripts Python (`wipiloader.py`, …) et `*mode.txt` (options globales).
  - `sbin/piforce/dm_netboot/` : bibliothèque **netdimm** de DragonMinded (domaine public),
    Python 3, implémente le protocole NetDIMM (TCP 10703). **C'est le cœur réutilisé.**
  - `boot/`, `etc/`, `root/`, `usr/` : fichiers système de l'image Pi (DietPi).
- **Nouveau code** :
  - `backend/` — paquet Python `naomox` (FastAPI) + `src/netdimm` vendorisé (3 patchs NAOMOX
    commentés : port configurable, timeout socket, firmware 4.03 ; fichier de progression WiPi retiré).
    Modules : `transfer` (sous-processus d'envoi), `jobs` (file par borne), `supervisor` (présence,
    time hack, mode serveur, autoboot), `api` (REST + SSE), `storage`, `mock` (fausse NetDIMM).
  - `frontend/` — Vite + Svelte 5 + TS, routage par hash, état dans `src/lib/state.svelte.ts`.
  - `deploy/` — `install.sh` (idempotent), `naomox.service`, `push.sh`, `pct-create.sh`, Docker optionnel.
  - `tools/dev-sync.sh` / `dev-pull.sh` — exécution des tests dans le CT (pas de Python sur le poste Windows).

## Documentation

- `docs/AUDIT.md` — audit de l'image WiPi 6.1.4 et du fork (flux de lancement, dépendances Pi).
- `docs/ARCHITECTURE.md` — architecture cible et décisions.
- `docs/DEPLOY.md` — déploiement Proxmox pas à pas + dépannage.
- `docs/TESTING.md` — tests automatisés, e2e et checklist de test réel sur borne.

## Décisions prises (validées par l'utilisateur)

1. Cible **Proxmox uniquement**. Pas de compatibilité Pi à maintenir.
2. Seules les fonctions **NetDIMM / réseau** sont conservées : netboot, mode serveur
   (ensure), time hack (zero-key), mise à jour firmware NetDIMM, infos DIMM, menu OSM
   (netbootmenu), gestion des bornes et des jeux. Tout le matériel Pi est abandonné
   (écran, LCD, GPIO/relais, rotary, Wi-Fi AP, Bluetooth, NFC, card emulators, OpenJVS/FFB,
   cycraft). Voir `docs/AUDIT.md` §6.
3. Interface **entièrement réécrite**, mobile-first, servie par le backend. Plus de PHP, plus de sudo.
4. Toutes les cartes supportées ; **plan d'adressage modifiable**. Les bornes sont sur le
   **LAN principal** (`10.185.10.0/24`), comme l'interface web : pas de bridge dédié, et
   **jamais de serveur DHCP**.
4bis. Frontend Vite + Svelte (TS), compilé à l'avance ; données en YAML et CSV ;
   authentification optionnelle, désactivée par défaut. Nom technique : `naomox` (service,
   utilisateur, `/etc/naomox`, `/srv/naomox`, `/opt/naomox`).
5. ROMs, firmwares et médias stockés **dans le conteneur** (`/srv/naomox`, configurable).
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

```sh
tools/dev-sync.sh 'ruff check . && ruff format --check . && pytest -q'   # tests backend dans le CT
tools/dev-sync.sh 'ruff check --fix . ; ruff format .' && tools/dev-pull.sh  # formater puis rapatrier
(cd frontend && npm run check && npm run build)                         # frontend
(cd frontend && NAOMOX_E2E_URL=http://10.185.10.230:8081 npm run e2e)   # e2e UI (instance jetable, cf. TESTING.md)
deploy/push.sh                                                          # build + déploiement sur le CT 10230
ssh -i ~/.ssh/naomox_ed25519 root@10.185.10.230 journalctl -u naomox -f
```

## Conventions

- Code et commentaires en français côté `naomox`, anglais dans les patchs du code vendorisé.
- Toute modification de `backend/src/netdimm` : commentaire `# NAOMOX:` + commit `vendor(netdimm): …` dédié.
- Lint : ruff (`backend/pyproject.toml`), svelte-check `--fail-on-warnings`.
- Le mock traite une connexion à la fois (comme une vraie NetDIMM) — ne pas paralléliser.
- Non porté : menu OSM (`netdimm_menu`) — signalé dans TESTING.md.
