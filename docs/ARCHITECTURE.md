# Architecture cible — WiPiNetbooter-NG sur Proxmox

Ce document se lit avec [AUDIT.md](AUDIT.md). Les décisions marquées **[à valider]** attendent ton accord.

## 1. Vue d'ensemble

```
 Téléphone / tablette (LAN)                       Réseau des bornes (isolé)
          │ HTTP(S) :80                                     │ TCP 10703
          ▼                                                 ▼
┌──────────────────────── LXC Debian 12 « wipi » ─────────────────────────┐
│ eth0 (vmbr0, LAN, DHCP ou IP fixe)      eth1 (vmbr1, 10.0.0.1/24, sans GW)│
│                                                                          │
│  wipinetbooter-api (systemd, utilisateur « wipi », aucun sudo)           │
│   ├─ FastAPI : REST /api/v1/* + SSE /api/v1/events + frontend statique   │
│   ├─ Gestionnaire de bornes : un worker asyncio par NetDIMM              │
│   │    file de jobs (send, firmware, diag, info), verrou TCP par DIMM    │
│   │    superviseurs : time hack, mode serveur (ensure), menu OSM,        │
│   │    autoboot                                                          │
│   ├─ Sous-processus de transfert (python -m wipi.transfer) :             │
│   │    lib netdimm (dm_netboot), progression en JSON lines sur stdout    │
│   └─ Stockage : /etc/wipi/config.yaml + /srv/wipi/{roms,media,firmware,  │
│                 homebrew,state}                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2. LXC ou VM

| Critère | LXC non privilégié | VM |
|---|---|---|
| Matériel nécessaire | aucun : tout passe par le réseau (TCP 10703) | aucun |
| Empreinte | environ 100 Mo de RAM, démarrage en 2 s | 512 Mo et plus, noyau séparé |
| Réseau | 2 interfaces virtuelles sur deux bridges, sans difficulté | idem |
| Isolation | bonne (namespaces utilisateur) | meilleure |
| Sauvegarde | `vzdump` / snapshots | idem |

**Décision : LXC Debian 12 non privilégié.** Les fonctions USB et série sont abandonnées,
donc aucun passthrough n'est requis et le mode privilégié devient inutile. `deploy/install.sh`
fonctionne aussi dans une VM Debian 12 si tu préfères (option documentée dans DEPLOY.md).

Dimensionnement : 1 vCPU, 512 Mo de RAM, rootfs de 8 Go, plus un **point de montage `mp0`
de 64 Go** pour `/srv/wipi`. Il contient les ROMs (24 Go aujourd'hui) et les médias (1,6 Go).
Le volume est séparé pour qu'on puisse reconstruire le conteneur sans recopier les ROMs.
Les ROMs restent **dans le conteneur**, comme demandé. `mp0` reste un volume Proxmox
(par exemple `local-lvm` ou `local-zfs`), pas un dossier de l'hôte.

## 3. Réseau

### 3.1 Topologie

- **`vmbr0` (LAN)** : accès à l'interface web depuis le téléphone ou la tablette. `eth0` du conteneur.
- **`vmbr1` (bornes)** : bridge dédié, relié **soit** à une carte réseau physique branchée sur le
  switch des bornes, **soit** à un VLAN (`vmbr0` VLAN-aware, tag configurable). `eth1` du conteneur
  en `10.0.0.1/24`, **sans passerelle**.
- **Aucun serveur DHCP** n'est lancé, nulle part. Les NetDIMM sont en IP fixe (réglée dans le
  menu de test de la borne), comme sur l'image d'origine. On évite ainsi tout DHCP sauvage sur le LAN.
- Pas de routage entre le LAN et le réseau des bornes. Seul le conteneur voit les deux.

### 3.2 Plan d'adressage (modifiable)

| Élément | Défaut (repris de l'image) | Où le modifier |
|---|---|---|
| Sous-réseau des bornes | `10.0.0.0/24` | `config.yaml` → `network.cabinet_subnet` (utilisé par la découverte) ; IP de `eth1` via `pct set` (documenté) |
| IP du netbooter côté bornes | `10.0.0.1` | `pct set <id> -net1 …` |
| NetDIMM | `10.0.0.2`, `.3`, … | interface web → Bornes (stockées dans `state/cabinets.yaml`) |
| Port NetDIMM | `10703` | `config.yaml` → `netdimm.port` (utile pour le mock) |

L'interface propose aussi une **découverte** : un balayage asynchrone du port 10703 sur le
sous-réseau, qui remplace `nmap`. On ajoute ensuite la borne en un clic.

## 4. Stockage et configuration

| Chemin | Contenu | Écrit par |
|---|---|---|
| `/etc/wipi/config.yaml` | configuration statique : chemins, ports, authentification, sous-réseau, délais d'expiration | administrateur |
| `/srv/wipi/roms/` | `*.bin.gz` (ou `.bin`) | upload web, scp ou rsync |
| `/srv/wipi/media/{images,videos}/` | jaquettes et vidéos | upload web, scp |
| `/srv/wipi/firmware/` | `FW_Netdimm_40x.bin.gz` (Sega, **jamais dans git**) | scp |
| `/srv/wipi/homebrew/` | netbootmenu, naomidiag (domaine public, copiés depuis le dépôt à l'installation) | install.sh |
| `/srv/wipi/state/cabinets.yaml` | bornes : nom, IP, type, jeu par défaut, time hack, mode serveur, options OSM | API (écriture atomique) |
| `/srv/wipi/state/games.csv` | métadonnées des jeux, **même format que `romsinfo.csv`** (import et export compatibles) | API |
| `/srv/wipi/state/history.jsonl` | historique des lancements | API |

Choix des fichiers plutôt que d'une base de données : les fichiers restent lisibles, éditables
à la main, faciles à sauvegarder, et compatibles avec le CSV existant. Le volume est faible
(quelques centaines de jeux, une poignée de bornes). Écriture atomique (fichier temporaire puis
`rename`) sous verrou. Au premier démarrage, `games.csv` est initialisé depuis
`romsinfo.csv` (fourni dans le dépôt, métadonnées seulement).

Exemple de `config.yaml` :

```yaml
paths:
  data: /srv/wipi
http:
  host: 0.0.0.0
  port: 80
auth:
  enabled: false          # true → mot de passe unique, cookie de session
  password_hash: ""       # généré par `wipi set-password`
network:
  cabinet_subnet: 10.0.0.0/24
netdimm:
  port: 10703
  connect_timeout: 5
  send_timeout: 600
  retries: 2
timehack:
  interval_seconds: 300
  minutes: 10
```

## 5. Backend

### 5.1 Pile technique

- **Python 3.11** (version de Debian 12), **FastAPI**, uvicorn, pydantic, pyyaml.
- **`netdimm`** vient de `dm_netboot` (domaine public). Il est déplacé dans `backend/vendor/`,
  avec les modules `naomi` et `arcadeutils` strictement nécessaires.
  - Le **protocole n'est pas modifié**.
  - Seul le patch WiPi qui écrit `/var/log/progress_<ip>` est retiré. On utilise à la place le
    `progress_callback` d'origine.
- Outils : pytest, pytest-asyncio, httpx (client de test), ruff.

### 5.2 Modèle d'exécution

- **Un worker par borne**, avec une file FIFO. Un seul job à la fois par DIMM, parce que la
  NetDIMM n'accepte qu'une connexion de contrôle.
- **Types de jobs** : `launch`, `firmware`, `diag`, `info`.
- **Transfert dans un sous-processus** (`python -m wipi.transfer --ip … --file …`).
  - Il émet sa progression en JSON lines sur stdout : `{"phase":"upload","sent":…,"total":…}`.
  - Cela permet une **annulation fiable** (SIGTERM, puis SIGKILL), un délai d'expiration strict
    et l'isolation des plantages.
  - La décompression gzip se fait en Python, sans `pigz`.
- **États d'un job** : `queued → connecting → uploading → rebooting → done | error | cancelled | timeout`.
  Les erreurs sont typées : `unreachable`, `refused`, `timeout`, `protocol`, `rom_missing`,
  `firmware_mismatch`.
- **Relance** : `retries` tentatives automatiques sur `unreachable` / `timeout` à la connexion,
  jamais au milieu d'un upload. Un bouton « Relancer » est aussi proposé.
- **Superviseurs par borne** (tâches de fond, mises en pause pendant un job sur la même DIMM) :
  - **time hack** : `set_time_hack(minutes)` toutes les `interval_seconds` (comportement de `timehack.py`) ;
  - **mode serveur** : surveille la borne et renvoie le dernier jeu si elle a redémarré
    (logique de `netdimm_ensure`) ;
  - **menu OSM** : exécute `netdimm_menu` (sous-processus persistant) ; « relancer le menu »
    depuis le web remplace le déclencheur evdev ;
  - **autoboot** : au démarrage du service, envoie le `default_game` (ou le menu) dès que la
    borne répond sur le port 10703 (logique de `singleboot.py`).
- **Journaux** : `logging` vers stdout, donc journald (`journalctl -u wipinetbooter-api`).
  Les 200 dernières lignes de chaque job sont exposées par l'API.

### 5.3 API REST (`/api/v1`)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/games?system=&enabled=&fav=` | liste des jeux (métadonnées + présence de la ROM) |
| PATCH | `/games/{rom}` | activer, favori, champs éditables |
| POST | `/games/scan` | scan et audit des ROMs (identification par en-tête et hash) |
| GET / POST | `/games/export.csv`, `/games/import` | export et import au format `romsinfo.csv` |
| GET / POST / PATCH / DELETE | `/cabinets[/{id}]` | gestion des bornes |
| GET | `/cabinets/{id}/status` | en ligne, job en cours, superviseurs actifs |
| GET | `/cabinets/{id}/info` | `netdimm_info` (firmware, mémoire, état) |
| POST | `/cabinets/discover` | balayage du port 10703 sur le sous-réseau |
| POST | `/launch` `{rom, cabinet_id?}` | lancement ; sans `cabinet_id`, choix automatique de la seule borne compatible en ligne, sinon `409 {choices:[…]}` |
| GET | `/jobs?cabinet_id=` · `/jobs/{id}` | état et log d'un job |
| POST | `/jobs/{id}/cancel` · `/jobs/{id}/retry` | annuler, relancer |
| POST | `/cabinets/{id}/menu` · `/diag` · `/firmware` `{version}` | menu OSM, diagnostic, firmware (confirmation obligatoire) |
| PUT | `/cabinets/{id}/options` | time hack, mode serveur, jeu par défaut, thème et mode OSM |
| GET | `/events` | **SSE** : `job.progress`, `job.state`, `cabinet.online` |
| GET | `/media/{type}/{file}` | images et vidéos |
| GET | `/health` | supervision |

Compatibilité des systèmes, reprise de `supported_systems()` :

| Type de DIMM | Jeux acceptés |
|---|---|
| Sega Naomi | Naomi, Atomiswave |
| Sega Naomi2 | Naomi, Naomi2, Atomiswave |
| Sega Chihiro | Chihiro |
| Sega Triforce | Triforce |

La table est surchargeable dans `config.yaml`.

## 6. Frontend **[à valider]**

- **Vite + Svelte (TypeScript)**, compilé en fichiers statiques servis par FastAPI.
  - Pas de Node.js en production : le build se fait en CI ou sur le poste de dev, et le dossier
    `dist/` est livré.
  - Alternative sans build : JS natif modulaire, comme le launcher actuel. C'est plus simple,
    mais moins maintenable pour une dizaine d'écrans.
- Mobile-first, avec un manifeste PWA pour l'ajout à l'écran d'accueil. Thème sombre par défaut.
- **Écrans** :
  - Jeux : grille avec jaquettes, filtres système, genre et favoris, recherche ;
  - Fiche jeu, puis Lancer ;
  - Suivi du lancement : progression en direct par SSE, annuler, relancer ;
  - Bornes : liste, état en ligne, job en cours, options ;
  - Découverte des bornes ;
  - Firmware et diagnostic ;
  - Gestion des jeux : édition, import/export, audit ;
  - Fichiers : upload de ROMs et de médias ;
  - Réglages ;
  - Historique.
- Le design (cartes et filtres) reprend les choix ergonomiques du launcher, sans le code
  propre au kiosque.

## 7. Sécurité

- Utilisateur système dédié `wipi`, **aucun sudo**, aucune commande shell construite à partir
  des entrées. Les sous-processus sont lancés avec une liste d'arguments, et les chemins de ROM
  sont résolus puis vérifiés sous `paths.data/roms`.
- Port 80 sans root grâce à `AmbientCapabilities=CAP_NET_BIND_SERVICE`.
- Durcissement systemd : `NoNewPrivileges`, `ProtectSystem=strict`, `ReadWritePaths=/srv/wipi`,
  `ProtectHome`, `PrivateTmp`, `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`.
- **Authentification optionnelle** : un mot de passe unique (haché en argon2 ou bcrypt), cookie
  de session HttpOnly et SameSite=Strict, CSRF via l'en-tête `X-Requested-With`. Désactivée par
  défaut sur un LAN de confiance, activable dans `config.yaml`.
- Firmware : confirmation explicite, plus vérification du type de DIMM et du firmware actuel
  (`info`) avant l'envoi.
- HTTPS en option derrière un reverse proxy existant (Caddy ou nginx). Non inclus par défaut.

## 8. Tests

- **Mock NetDIMM** (`backend/tests/mock_netdimm.py`) : serveur TCP asyncio qui implémente les
  paquets utilisés (host mode, DIMM mode, key code, upload par blocs, information, restart,
  time hack, peek/poke).
  - Il enregistre les échanges, ce qui permet de vérifier l'ordre et le contenu des paquets.
  - Il peut injecter des pannes : refus, coupure en plein upload, lenteur, réponse invalide.
- **Tests unitaires** :
  - netdimm contre le mock ;
  - compatibilité des systèmes ;
  - files d'attente et verrou par borne ;
  - annulation et délais d'expiration ;
  - lecture et écriture de `games.csv` et `cabinets.yaml` ;
  - validation des chemins (traversée de répertoire).
- **Test de bout en bout** : backend + mock sur un port local. On lance un jeu fictif
  (ROM générée de quelques Mo) via l'API et on vérifie l'événement SSE `done`.
  Un test Playwright pilote le frontend (optionnel).
- **Le mock sert aussi de « borne virtuelle »** en développement, via `wipi mock --port 10703`.

## 9. Arborescence prévue

```
backend/
  pyproject.toml          # deps, ruff, pytest
  wipi/                   # app FastAPI, workers, transfer, config, storage
  vendor/netdimm, naomi…  # copie de dm_netboot (Unlicense), sans le patch progress
  tests/
frontend/                 # Vite + Svelte
deploy/
  install.sh              # idempotent, Debian 12
  wipinetbooter-api.service
  pct-create.sh           # exemple documenté
  config.example.yaml
docs/  AUDIT.md  ARCHITECTURE.md  DEPLOY.md
legacy/ (ou suppression) # ancien code Pi, retiré dans une phase dédiée
```

## 10. Points à valider

1. Frontend : **Vite + Svelte** ou JS natif sans build (§6).
2. Stockage des données en fichiers (YAML et CSV) plutôt qu'en SQLite (§4).
3. Réseau des bornes : **carte réseau dédiée** ou **VLAN** (et lequel) (§3.1).
4. Authentification désactivée par défaut (§7).
