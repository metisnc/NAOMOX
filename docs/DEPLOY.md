# Déploiement de NAOMOX sur Proxmox

Ce guide déploie NAOMOX dans un conteneur LXC Debian (12 ou 13), puis branche les bornes.

> **Le plus simple** : la commande unique du [README](../README.md#installation-sur-proxmox-en-une-commande)
> fait tout (conteneur + installation). Ce guide détaille les étapes et le dépannage.

Valeurs d'exemple utilisées ci-dessous : CT **120**, IP **192.168.1.230/24**, hôte Proxmox
`192.168.1.10`, LAN `192.168.1.0/24` (passerelle et DNS `192.168.1.1`).

## 1. Prérequis

| Élément | Détail |
|---|---|
| Proxmox VE | 8 ou 9, un template Debian 12 ou 13 (`pveam list local`) |
| Réseau | les NetDIMM et le CT sur le même LAN (ou routé), TCP **10703** joignable |
| Poste de dev | `git`, `ssh`, Node.js ≥ 20 (compilation du frontend) |
| NetDIMM | firmware **≥ 3.03** (4.01 / 4.02 / 4.03 recommandés) |

## 2. Créer le conteneur

Depuis l'hôte Proxmox, en root : copier `deploy/pct-create.sh`, puis le lancer.

```sh
CTID=120 IP=192.168.1.230/24 GW=192.168.1.1 DNS=192.168.1.1 \
STORAGE=local-zfs DATA_GB=64 SSH_KEY=/root/naomox.pub ./pct-create.sh
```

Le script renseigne aussi les **notes Proxmox** du CT (onglet Notes) à partir de
`deploy/proxmox-notes.md` : accès, disques, service, premiers pas. Mot de passe root :
`ROOT_PASSWORD=` (par défaut `naomox`, à changer sur un réseau partagé).

Le script exécute l'équivalent de :

```sh
pct create 120 local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst \
  --hostname naomox --unprivileged 1 --features nesting=1 \
  --cores 2 --memory 1024 --swap 512 \
  --rootfs local-zfs:8 \
  --mp0 local-zfs:64,mp=/srv/naomox,backup=1 \
  --net0 name=eth0,bridge=vmbr0,ip=192.168.1.230/24,gw=192.168.1.1,firewall=0 \
  --nameserver 192.168.1.1 --onboot 1 --tags naomox
pct start 120
```

À savoir :

- Le conteneur est **non privilégié**. NAOMOX n'utilise aucun périphérique de l'hôte : ni USB,
  ni série, ni GPIO.
- `nesting=1` est nécessaire au sandboxing systemd de Debian 13.
- `mp0` est un volume séparé pour les ROMs, médias et l'état. Il est inclus dans les
  sauvegardes `vzdump` (`backup=1`).
- Bornes sur un VLAN : ajouter `,tag=<vlan>` à `--net0` (variable `VLAN=` du script).
- Changer l'IP plus tard : `pct set 120 -net0 name=eth0,bridge=vmbr0,ip=<IP>/24,gw=<GW>`.

> **Git Bash sous Windows** : si vous pilotez l'API Proxmox (`curl`) depuis Git Bash, exportez
> `MSYS_NO_PATHCONV=1`. Sinon `mp=/srv/naomox` est réécrit en `C:/Program Files/Git/srv/naomox`.

## 3. Installer NAOMOX

### Depuis un poste de dev (recommandé)

```sh
git clone https://github.com/metisnc/NAOMOX.git && cd NAOMOX
NAOMOX_HOST=root@192.168.1.230 NAOMOX_KEY=~/.ssh/naomox_ed25519 deploy/push.sh
```

`push.sh` enchaîne trois étapes :

1. Il compile le frontend (`npm ci && npm run build`).
2. Il copie dans le CT le code utile : backend, `frontend/dist`, `deploy/` et les homebrew.
3. Il lance `deploy/install.sh`.

### Directement dans le CT

Il faut un `frontend/dist` compilé. Le CT n'a pas besoin de Node.js.

```sh
bash deploy/install.sh            # installe ou met à jour, puis (re)démarre le service
bash deploy/install.sh --no-start
bash deploy/install.sh --uninstall   # garde /srv/naomox
```

### Ce que fait `install.sh`

Le script est **idempotent** : on peut le relancer pour mettre à jour.

| Étape | Résultat |
|---|---|
| Paquets | `python3`, `python3-venv`, `ca-certificates`, `curl` |
| Utilisateur | `naomox` (système, sans shell, **sans sudo**) |
| Code | `/opt/naomox/app` ; venv `/opt/naomox/venv` (dépendances PyPI) ; frontend `/opt/naomox/frontend` |
| Configuration | `/etc/naomox/config.yaml`, créé depuis `deploy/config.example.yaml` **s'il n'existe pas** (jamais écrasé) |
| Données | `/srv/naomox/{roms,media/images,media/videos,firmware,homebrew,state,tmp}` (propriétaire `naomox`) |
| Homebrew | `naomidiag`, `netbootmenu` (domaine public) copiés dans `/srv/naomox/homebrew` |
| Service | `naomox.service` (port 80 par capacité, sandbox systemd), activé au démarrage |
| Vérification | `GET /api/v1/health` |

L'interface est alors disponible sur **http://192.168.1.230/** ou **http://naomox.local/**
(annonce mDNS / Bonjour par `avahi-daemon`, reconnue par iPhone, macOS, Windows 10/11 et Android récents ;
le nom vient du hostname du CT).

Pour que le nom court **http://naomox/** fonctionne sur tous les appareils, ajouter dans le DNS du
réseau (box, routeur UniFi, Pi-hole, Technitium…) un enregistrement **A** `naomox` → `192.168.1.230`. Sur téléphone, « Ajouter à
l'écran d'accueil » installe l'application (PWA).

## 4. Ajouter les ROMs, médias et firmwares

| Dossier (dans le CT) | Contenu |
|---|---|
| `/srv/naomox/roms/` | ROMs `.bin.gz` (ou `.bin`) |
| `/srv/naomox/media/images/`, `/srv/naomox/media/videos/` | jaquettes et vidéos référencées par la liste des jeux |
| `/srv/naomox/firmware/` | `FW_Netdimm_401.bin.gz`, `FW_Netdimm_402.bin.gz`, `FW_Netdimm_403.bin.gz` |

Trois façons de les déposer :

- **Interface** : Réglages → Fichiers → Ajouter des fichiers.
- **scp / rsync** depuis le poste :
  ```sh
  rsync -a --info=progress2 roms/ root@192.168.1.230:/srv/naomox/roms/
  ssh root@192.168.1.230 chown -R naomox:naomox /srv/naomox
  ```
- **Depuis une carte SD WiPi** : `/boot/roms` → `roms/`, `/boot/config/images|videos` →
  `media/`, `/boot/config/firmware` → `firmware/`.

Ensuite : Réglages → Jeux → **Scanner**.

**Depuis un autre NAOMOX** : utiliser le **pack de contenu** (`naomox-content export` / `import`,
voir le README) — un seul fichier `.tar` à garder sur un NAS, réimportable dans n'importe quelle
installation, ou passé directement à l'installateur (`CONTENT=…`). Les ROMs inconnues de la liste sont ajoutées, avec
le système deviné d'après leur préfixe (`n1-`, `n2-`, `aw-`, `ch-`, `tf-`).

La liste des jeux est initialisée avec le `romsinfo.csv` de WiPi 6.1. Elle s'exporte et
s'importe dans ce même format (Réglages → Jeux).

## 5. Configurer les bornes

### Sur la borne (menu test)

Entrer dans le menu de test → **NETWORK SETTING** (NetDIMM) :

| Réglage | Valeur |
|---|---|
| NETWORK TYPE | `ETHER` |
| REMOTE | `DISABLE` |
| IP ADDRESS | une IP fixe du LAN **hors plage DHCP**, par ex. `192.168.1.50` |
| SUBNET MASK | `255.255.255.0` |
| GATEWAY | `192.168.1.1` (facultatif) |

Selon la carte :

- **Triforce / Chihiro** : la carte doit être en mode satellite. Sur Triforce type 3, c'est
  SW1 sur ON ON. Sur les modèles VxWorks, ce sont les cavaliers JP1–JP3.
- **Sans PIC zero-key** : activer le **time hack** sur la borne dans NAOMOX. NAOMOX doit alors
  rester joignable pendant toute la partie.

### Dans NAOMOX

Aller dans **Bornes**, puis :

1. Cliquer sur **Rechercher**, ce qui balaye `network.cabinet_subnet` sur le port 10703.
2. Cliquer sur **Ajouter**, ou ajouter la borne à la main avec son nom, son IP et son type
   (Naomi, Naomi 2, Chihiro ou Triforce).

Options par borne :

| Option | Effet |
|---|---|
| Au démarrage | jeu envoyé automatiquement la première fois que la borne apparaît après le démarrage du service (ex-« Single Boot ») |
| Mode serveur | renvoie le dernier jeu à chaque mise sous tension, si la NetDIMM ne l'a plus en mémoire |
| Time hack | envoie périodiquement le paquet 0x17 (ex-`timehack.py`) |

Pour lancer un jeu, ouvrir l'onglet **Jeux**, choisir le jeu, puis **Lancer**.

- S'il n'y a qu'une borne compatible en ligne, elle est choisie automatiquement.
- Sinon, NAOMOX demande laquelle utiliser.
- La progression s'affiche en direct, et le transfert peut être annulé.

## 6. Options

### Authentification

```sh
ssh root@192.168.1.230
/opt/naomox/venv/bin/naomox hash-password        # saisir le mot de passe, copier le hash
nano /etc/naomox/config.yaml                     # auth.enabled: true, auth.password_hash: "scrypt$…"
systemctl restart naomox
```

### HTTPS

Placer NAOMOX derrière un reverse proxy existant (Caddy, nginx, Traefik).

Pour nginx, le flux SSE `/api/v1/events` exige `proxy_buffering off;`. L'en-tête
`X-Accel-Buffering: no` est déjà envoyé.

### Docker

Alternative non nécessaire avec le LXC :

```sh
docker compose -f deploy/docker-compose.yml up -d --build
```

Le conteneur utilise le réseau `host` et écoute sur le port 8080.

## 7. Exploitation

| Action | Commande |
|---|---|
| Journaux en direct | `journalctl -u naomox -f` |
| Statut | `systemctl status naomox` |
| Redémarrer | `systemctl restart naomox` |
| Mise à jour | relancer `deploy/push.sh` depuis le poste |
| Sauvegarde | `vzdump 120` (inclut `/srv/naomox`) ; l'état seul tient dans `/srv/naomox/state/` |
| Désinstaller | `bash deploy/install.sh --uninstall` (données conservées) |

Fichiers d'état, tous modifiables à la main service arrêté :

| Fichier | Contenu |
|---|---|
| `state/cabinets.yaml` | bornes |
| `state/games.csv` | jeux (format `romsinfo.csv`) |
| `state/settings.yaml` | réglages modifiés depuis l'interface |
| `state/runtime.json` | dernier jeu envoyé par borne |
| `state/history.jsonl` | historique |

## 8. Dépannage

### NetDIMM injoignable (`unreachable`, `refused`)

1. **La borne est-elle allumée**, et l'écran affiche-t-il l'attente réseau ou un jeu ? Si
   l'écran reste dans le menu de test, en sortir.
2. **Ping** depuis le CT : `ping 192.168.1.50`. Faire aussi un test de port :
   `timeout 2 bash -c '</dev/tcp/192.168.1.50/10703' && echo ouvert`.
3. **Câble et switch** : les LED du port NetDIMM doivent être allumées.
4. **`refused`** veut dire que l'IP répond mais que le port est fermé. Causes possibles : un
   autre appareil a cette IP (conflit), ou une Triforce/Chihiro n'est pas en mode satellite.
5. Firewall Proxmox : le CT est créé avec `firewall=0`. Si le firewall du datacenter est actif,
   autoriser la sortie vers TCP 10703.

### Mauvaise IP ou conflit d'adresse

- L'IP réglée dans le menu **NETWORK SETTING** doit correspondre exactement à celle de la fiche
  de la borne dans NAOMOX.
- Choisir une IP **hors plage DHCP** de la box ou du routeur, sinon un autre appareil peut la
  prendre. Pour vérifier : `ip neigh | grep 192.168.1.50`, l'adresse MAC doit être celle de
  la NetDIMM.
- **Rechercher** dans l'onglet Bornes liste toutes les IP qui répondent sur le port 10703.

### Timeout pendant le transfert (`timeout`, `disconnected`)

- Liaison instable : préférer un switch direct, éviter Wi-Fi et CPL entre le CT et la borne.
- `netdimm.socket_timeout` : 15 s pour Naomi, 40 s pour Chihiro/Triforce par défaut. Augmenter
  si la borne met longtemps à afficher « NOW LOADING ».
- `netdimm.send_timeout` (900 s) : délai maximal d'un lancement complet. Les grosses ROMs
  Chihiro de 512 Mo prennent plusieurs minutes.
- Le **journal du job** (Activité → Journal) contient la cause exacte.

### Firmware NetDIMM incompatible ou trop ancien

- NAOMOX demande un firmware **3.03 ou plus**. Bornes → Infos affiche la version.
- Pour mettre à jour : Bornes → Modifier → Maintenance → Firmware. Depuis 3.x, **passer
  d'abord en 4.01**, puis en 4.02 ou 4.03. Seules les NetDIMM **type 1** sont concernées.
- Pendant la mise à jour, suivre les instructions affichées par la borne et **ne pas couper le
  courant**.
- Erreur `protocol` ou réponses incohérentes : vérifier la version, et que l'appareil sur cette
  IP est bien une NetDIMM.

### Zero-key / PIC de sécurité

- **Avec un PIC zero-key** (recommandé), le jeu tourne indéfiniment après l'envoi, et NAOMOX
  peut être arrêté.
- **Sans PIC zero-key**, le jeu s'arrête au bout de quelques minutes. Activer le **time hack**
  sur la borne. NAOMOX renvoie alors le paquet « time limit » toutes les 30 s
  (`timehack.interval_seconds`) **tant que la borne est en ligne**. Le CT doit donc rester
  démarré pendant toute la partie.
- Une erreur « security PIC » ou « key chip » à l'écran se règle dans le matériel (PIC). Elle
  n'a pas de solution côté NAOMOX.

### Le service ne démarre pas

- `journalctl -u naomox -n 50`.
- **Port 80 déjà pris** : `ss -ltnp | grep :80`. Changer `http.port` dans la config.
- **Erreur de config** : la validation pydantic indique la clé en cause.
- **Sandbox systemd refusée** (CT sans `nesting=1`) : `pct set 120 -features nesting=1`, puis
  redémarrer le CT.

### Le jeu ne démarre pas alors que le transfert est « terminé »

- Le jeu n'est peut-être pas fait pour cette carte. Un Naomi 2 accepte les jeux Naomi et
  Atomiswave, mais un Naomi n'accepte pas les jeux Naomi 2.
- La ROM peut être corrompue. Pour le vérifier, activer le mode serveur sur la borne : la
  NetDIMM contrôle alors le CRC au démarrage (« CHECKING »), et l'état apparaît dans
  Bornes → Infos.
- Pour l'Atomiswave, il faut une cartouche de conversion AW-NET.
