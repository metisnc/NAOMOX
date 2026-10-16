# CLAUDE.md — NAOMOX

Netbooter web pour cartes Sega Naomi / Naomi 2 / Chihiro / Triforce équipées d'une NetDIMM,
déployé dans un **conteneur LXC Debian 13 sur Proxmox** et piloté depuis un téléphone ou une tablette.

- Dépôt de l'application : **`metisnc/NAOMOX`** (ce dépôt).
- Origine : portage de [WiPiNetbooter](https://github.com/chunksin/WiPiNetbooter) (Raspberry Pi).
  Le fork **`metisnc/WiPiNetbooter-NG`** reste la référence du code WiPi (PHP, scripts Pi,
  `dm_netboot`) : **ne jamais le renommer ni y pousser le travail NAOMOX** (il est utilisé par un
  autre workspace). L'historique NAOMOX en a été extrait (filter-branch) sans les binaires WiPi.

## Environnement de déploiement

Les informations propres à l'installation de l'auteur (hôte Proxmox, ID et IP du conteneur, accès)
sont dans **`CLAUDE.local.md`** (non versionné). Ne jamais les recopier dans le dépôt.

## Arborescence

- `backend/` — paquet Python `naomox` (FastAPI) + `src/netdimm` vendorisé (3 patchs NAOMOX
  commentés : port configurable, timeout socket, firmware 4.03 ; fichier de progression WiPi retiré).
  Modules : `transfer` (sous-processus d'envoi), `jobs` (file par borne), `supervisor` (présence,
  time hack, mode serveur, autoboot), `api` (REST + SSE), `storage`, `mock` (fausse NetDIMM).
- `frontend/` — Vite + Svelte 5 + TS, routage par hash, état dans `src/lib/state.svelte.ts`.
- `deploy/` — `install.sh` (idempotent), `naomox.service`, `push.sh`, `pct-create.sh`, Docker optionnel.
- `homebrew/` — naomidiag et netbootmenu (DragonMinded, domaine public), installés par `install.sh`.
- `tools/dev-sync.sh` / `dev-pull.sh` — exécution des tests dans le CT (pas de Python sur le poste Windows).

## Documentation

- `docs/AUDIT.md` — audit de l'image WiPi 6.1.4 et du fork `WiPiNetbooter-NG` (chemins `sbin/…`, `var/www/…` = ce fork) (flux de lancement, dépendances Pi).
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
   **même LAN** que l'interface web : pas de bridge dédié, et
   **jamais de serveur DHCP**.
4bis. Frontend Vite + Svelte (TS), compilé à l'avance ; données en YAML et CSV ;
   authentification optionnelle, désactivée par défaut. Nom technique : `naomox` (service,
   utilisateur, `/etc/naomox`, `/srv/naomox`, `/opt/naomox`).
5. ROMs, firmwares et médias stockés **dans le conteneur** (`/srv/naomox`, configurable).
6. Binaires déjà commités dans l'historique : retirés de l'arbre plus tard, **pas de
   réécriture d'historique** sans accord explicite.
7. Interface (phase graphique, oct. 2026) :
   - **Thème néon** repris du launcher WiPiNetbooter-NG (cyan / magenta), **noir par défaut**,
     blanc en option (`data-theme="light"`, choix mémorisé par appareil).
   - Couleurs système : Naomi ambre, Naomi 2 rouge, **Atomiswave vert**, **Chihiro blanc**
     (argent en thème clair), Triforce violet.
   - Tuiles = grands rectangles arrondis (logo + nom centré), zone de logo identique partout ;
     les logos de jeux sont **recadrés côté serveur** (`/media/logos/…`, Pillow, cache).
   - **Logos de systèmes** = marques, hors git, dans `/srv/naomox/media/systems/`
     (`Sega Naomi.png`, `Sega Chihiro.svg`…) ; crédits dans le README (Chihiro : CC BY-SA 4.0).
   - Lancement : un seul bouton LANCER ; le serveur choisit la borne s'il n'y en a qu'une en
     ligne, sinon l'interface propose le choix (réponse 409 `choose`).
   - **Firmware** : zone repliée + avertissement + version lue + cases + mot `FLASHER` ;
     le serveur refuse aussi : borne injoignable, même version, retour arrière, 3.x → autre que 4.01.
   - Pas de classification d'âge, pas de « même genre » dans la fiche.
8. Réseau : `http://naomox.local` (avahi-daemon). Le **nom réseau** est modifiable dans
   Réglages : NAOMOX l'annonce lui-même (`avahi-publish -a`, sans root). Le hostname du CT
   appartient à Proxmox (`pct set <CTID> -hostname …`) et n'est pas modifié par l'interface.

## Règles de travail

- Ne jamais modifier l'image d'origine (`../WiPi6-1-4*`). Lecture seule ; montage `.img`
  uniquement via `losetup -P -r` + `mount -o ro` (sur un hôte Linux).
- Ne jamais commiter de ROM, firmware Sega, média de jeu ou binaire propriétaire.
  Les homebrew DragonMinded (`homebrew/`) sont du domaine public et tolérés.
- Branche `main` ; une branche par évolution (`feat/…`). Petits commits atomiques, messages clairs.
- Signaler (ne pas supprimer silencieusement) toute fonction dépendant du matériel Pi.
- Ne pas modifier le protocole NetDIMM.

## Commandes

```sh
tools/dev-sync.sh 'ruff check . && ruff format --check . && pytest -q'   # tests backend dans le CT
tools/dev-sync.sh 'ruff check --fix . ; ruff format .' && tools/dev-pull.sh  # formater puis rapatrier
(cd frontend && npm run check && npm run build)                         # frontend
(cd frontend && NAOMOX_E2E_URL=http://<ct>:8081 npm run e2e)             # e2e UI (instance jetable, cf. TESTING.md)
NAOMOX_HOST=root@<ct> deploy/push.sh                                    # build + déploiement
ssh root@<ct> journalctl -u naomox -f
```

## Conventions

- Code et commentaires en français côté `naomox`, anglais dans les patchs du code vendorisé.
- Toute modification de `backend/src/netdimm` : commentaire `# NAOMOX:` + commit `vendor(netdimm): …` dédié.
- Lint : ruff (`backend/pyproject.toml`), svelte-check `--fail-on-warnings`.
- Le mock traite une connexion à la fois (comme une vraie NetDIMM) — ne pas paralléliser.
- Non porté : menu OSM (`netdimm_menu`) — signalé dans TESTING.md.
