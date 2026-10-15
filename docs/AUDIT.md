# Audit — WiPiNetbooter 6.1.4 (image) vs WiPiNetbooter-NG (fork)

Sources :

- **Image d'origine** : `WiPi6-1-4.img` (31,9 Go), extraite sous Windows en `WiPi6-1-4/0`
  (`/boot`, FAT) et `WiPi6-1-4/1` (rootfs ext4). Base **DietPi** (Debian 10 Buster, armhf).
- **Fork** : `metisnc/WiPiNetbooter-NG`, branche `master` au commit `23412c0`.
  L'arbre correspond à WiPi **6.1-92**, plus le launcher 3.5".

> **Limite de l'audit.** L'extraction Windows a transformé les 936 liens symboliques en
> fichiers vides. Plusieurs dossiers sont donc vides : `bin`, `usr/bin`, `opt`,
> `sbin/piforce/dm_netboot`, `card_emulator`, `lcd-piforcetools` et `var/www/html/csv`.
> Les unités `lcd-piforce` et les configs `dnsmasq`/`hostapd` manquent aussi.
> Le code applicatif manquant est présent dans le fork. Les éléments système encore absents
> concernent tous des fonctions abandonnées (§6). Un montage `losetup -P -r` sur un hôte Linux
> (le Proxmox) permettra de compléter cet audit. Ce n'est pas bloquant.

---

## 1. Inventaire des composants

### 1.1 Frontend web

| Élément | Image 6.1.4 | Fork |
|---|---|---|
| Serveur | lighttpd + PHP 7.3 en FastCGI (`/etc/lighttpd/lighttpd.conf`), utilisateur `www-data`, port 80 | idem (non versionné) |
| Racine du site | `/var/www/html`, environ 70 pages PHP | environ 90 pages PHP + `launcher/` |
| Bibliothèques | jQuery, Bootstrap, Swiper (dans `package/`) | idem |
| Nouveau frontend | — | `var/www/html/launcher/` : JS natif sans build, API PHP JSON (`api/games, dimms, launch, status, cancel`), conçu pour l'écran tactile 3.5" en kiosque Chromium |
| Kiosque | autologin `dietpi` sur tty1 → `startx` → openbox → Chromium `http://127.0.0.1/index.html` | `launcher/install.sh` remplace l'URL par `/launcher/?kiosk=1`, ajoute une extension « home-button », un écran de veille et `screen-rotate.sh` |

### 1.2 Scripts Python (`/sbin/piforce`)

| Script | Rôle | Python | À conserver ? |
|---|---|---|---|
| `wipiloader.py` | orchestrateur de lancement (voir §2) | 3 | **logique reprise** dans le backend |
| `singleboot.py` | au démarrage, envoie le `defaultgame` de chaque DIMM dès qu'elle répond sur le port 10703, ou lance le menu | 3 | **oui** (autoboot) |
| `timehack.py` | boucle `set_time_hack(10)` toutes les 300 s | 3 | **oui** |
| `wipiloaderfw.py` | envoi du firmware NetDIMM | 3 | **oui** |
| `menulauncher.py` | lance `netdimm_menu` (OSM) ; relance si 3 boutons maintenus sur `/dev/input/event0` | 3 | menu **oui**, déclencheur evdev **non** |
| `auditnames.py`, `renamecsv.py`, `importcsv.py`, `updatecsv.py` | audit et renommage des ROMs, import/export du CSV des jeux | **2** | **logique reprise** |
| `check.py`, `wipimonitor.py` | orchestration au démarrage (NFC, OpenJVS, `/boot/wifi.txt`, extinction auto…) | 3 | **non** (Pi) |
| `configuration.py`, `devicelist.py`, `device*.py`, `mappingfiles.py` | OpenJVS, manettes evdev | 2 | **non** |
| `wifi*.py`, `hotspot*.py`, `homewifi.py`, `setstatic.py`, `setdhcp.py` | Wi-Fi, point d'accès, IP fixe | 2 | **non** (réseau géré par Proxmox) |
| `bluetooth*.py` | appairage Bluetooth | 2 | **non** |
| `rotary*.py`, `switchmode.py` (partie LCD) | GPIO, LCD | 2/3 | **non** |
| `nfcloader.py`, `writenfc.py`, `card_emulator/*` | NFC, émulation de lecteurs de cartes | 3 | **non** |
| `reboot.py`, `shutdown.py`, `ziplogs.py`, `delete.py` | système | 2/3 | à remplacer (journald, API) |

### 1.3 Bibliothèque `dm_netboot` (DragonMinded, domaine public / Unlicense)

`sbin/piforce/dm_netboot/` est une copie de `DragonMinded/netboot` :

- `netdimm/netdimm.py` : la classe `NetDimm` implémente le protocole sur le port TCP **10703**.
  - Méthodes publiques : `info()`, `send(data, key, progress_callback)`, `receive()`,
    `reboot()`, `set_time_limit()`, `set_time_hack()`, `peek()`/`poke()`.
  - Paquets internes : 0x07 (host mode), 0x08 (DIMM mode), 0x7F (key code),
    0x04 (upload, flags 0x80/0x81), désactivation du CRC, restart.
- `scripts/` : `netdimm_send`, `netdimm_ensure`, `netdimm_info`, `netdimm_firmware`,
  `netdimm_menu`, `netdimm_peekpoke`, `netdimm_receive`, plus les outils de ROM
  (`attach_settings`, `binary_patch`, `rominfo`, `eeprominfo`…).
- `naomi/` (en-têtes ROM, EEPROM, réglages), `netboot/` (serveur Flask d'origine, non utilisé),
  `homebrew/` (`netbootmenu.bin[.dark|.light]`, `naomidiag.bin.gz`, `settingstrojan.bin`,
  `sramdump.bin`).
- **Patch WiPi local** : `NetDimm.__upload_file()` écrit en dur `/var/log/progress_<ip>`
  (de 0 à 100, puis `COMPLETE`). Ce code est en plus du `progress_callback` prévu en amont.
  Il faudra le **supprimer** et passer par le callback.
- Dépendances (`requirements.txt`) : pycryptodome, pyyaml, arcadeutils, dragoncurses, pillow,
  flask. Le netboot seul n'a besoin que de pycryptodome, arcadeutils et pyyaml.

> `triforcetools.py` (Python 2, l'ancien outil de netboot) **n'existe plus** : il a été remplacé
> par `netdimm` en amont dès WiPi 6.x et supprimé du fork au commit `6607ade`. Le portage
> Python 3 du protocole est donc déjà fait. Le travail consiste à **réutiliser** `netdimm`
> et à le **tester** contre un faux serveur NetDIMM.

### 1.4 Services et démarrage automatique

| Mécanisme | Contenu |
|---|---|
| systemd (personnalisés) | `openjvs.service`, `openjvs@.service`, `openffb.service` (root, `Restart=always`). `lcd-piforce.service` activé, mais son fichier d'unité est perdu dans l'extraction |
| systemd (activés) | `dnsmasq`, `hostapd`, `hciuart`, `netfilter-persistent`, `ssh`, `networking`, `dietpi-*` |
| Connexion | `getty@tty1` avec autologin `dietpi`, puis `~/.bashrc` lance `startx -- -nocursor` |
| rc.local / cron | aucun (`cron.d/php` seulement). Le manuel cite `rc.local → check.py` : probablement lancé par `lcd-piforce` |
| `dm_netboot/services/*.service` | exemples DragonMinded, non utilisés |

### 1.5 Réseau

| Élément | Valeur |
|---|---|
| `eth0` (côté bornes) | statique `10.0.0.1/24`, sans passerelle (`10.0.0.254` est en commentaire) |
| NetDIMM par défaut | **`10.0.0.2`** (`network.php` : « Netdimm … should be configured to run on 10.0.0.2 ») |
| Port NetDIMM | **TCP 10703** (`singleboot.py` `port_check`, `dimmscanner.php` : `nmap -p10703`) |
| `wlan0` (point d'accès) | `192.168.42.1/24`, SSID « naomi », hostapd + dnsmasq (DHCP sur le Wi-Fi uniquement) |
| `wlan0` (mode maison) | DHCP + wpa_supplicant |
| Variantes | `/etc/network/interfaces{,.home,.hotspot,.restore}`, réécrites ligne par ligne par `setstatic.py` et `hotspotupdate.py` |
| Divers | `activedimm.txt` = `192.168.1.2` (valeur résiduelle) |

### 1.6 ROMs et configuration des jeux

| Donnée | Emplacement | Format |
|---|---|---|
| ROMs | `/boot/roms/` (FAT), 205 fichiers `.bin.gz`, **24 Go** | `<system>-<nom>_<id>.bin.gz` |
| Métadonnées des jeux | `/var/www/html/csv/romsinfo.csv` (copie dans `/boot/config/romsinfo.csv`) | CSV : `system,romname,image,video,description,lcd_description,manufacturer,year,genre,rating,orientation,controls,enabled,favourite,openjvs,openffb,game_id,audit_name` |
| Bornes | `/var/www/html/csv/dimms.csv` | CSV : `name,ipaddress,type,opentarget,defaultgame,openjvs,openffb` |
| Options globales | `/sbin/piforce/*mode.txt` (une valeur par fichier) | `zeromode=hackon|hackoff`, `servermode=serveron|serveroff`, `bootfile=single|multi`, `osm*`, `relaymode`, … |
| Médias | `/boot/config/images` (220 fichiers), `/boot/config/videos` (156 mp4), **1,6 Go** | |
| Firmwares NetDIMM | `/boot/config/firmware/FW_Netdimm_40{1,2,3}.bin.gz` | Binaires **Sega** |

---

## 2. Flux « clic sur un jeu → netboot »

### 2.1 Interface d'origine

```
gamelist.php                         (liste lue depuis romsinfo.csv)
  └─ lien loadcheck.php?rom=<f>&name=&system=&mapping=<openjvs>&ffb=<openffb>
loadcheck.php                        (www-data)
  ├─ lit csv/dimms.csv, filtre les DIMM compatibles avec <system>
  ├─ exec("fping -c1 -t500 $address") pour chaque DIMM
  ├─ 1 seule DIMM en ligne → redirection vers load.php (Chrome) ou loadnochrome.php
  └─ sinon                 → page de choix de la DIMM
load.php:54-60
  $relaymode = file_get_contents('/sbin/piforce/relaymode.txt');
  $zeromode  = file_get_contents('/sbin/piforce/zeromode.txt');
  $command = escapeshellcmd('sudo python3 /sbin/piforce/wipiloader.py '
             .$rom.' '.$dimm.' '.$relaymode.' '.$zeromode.' '.$mapping.' '.$ffb);
  shell_exec($command . '> /dev/null 2>/dev/null &');
  boucle : popen('sudo tail -n 1 /var/log/progress_'.$dimm) → barre de progression jusqu'à 100
```

### 2.2 Launcher du fork

```
launch.js  →  POST api/launch.php {rom, dimm?}   (en-tête obligatoire : X-Launcher: 1)
  find_game()       : jeu présent dans romsinfo.csv, activé, ROM présente dans /boot/roms
  candidate_dimms() : DIMM compatibles qui répondent à fping (règles copiées de loadcheck.php)
  api/launch_lib.php :
    $args = [$rom, $ip, read_mode('relaymode'), read_mode('zeromode'), $mapping, $ffb];
    exec('sudo python3 /sbin/piforce/wipiloader.py '
         . implode(' ', array_map('escapeshellarg', $args)) . ' > /dev/null 2>&1 &');
  état     : GET api/status.php  → pgrep wipiloader|netdimm_send + lecture de /var/log/progress_<ip>
  annuler  : POST api/cancel.php → sudo pkill -f '[w]ipiloader\.py|[d]m_netboot/netdimm_send'
  persistance : launcher/data/launch.json et history.json (le /var/log en RAM de DietPi est vidé chaque heure)
```

### 2.3 `wipiloader.py <rom> <ip> <relaymode> <zeromode> <mapping> <ffb>`, lancé en root via sudo

1. Lit `openmode`, `ffbmode`, `emumode`, `hatserial` et `servermode` (`*.txt`).
2. Si OpenJVS/OpenFFB sont actifs : `sudo openjvs <mapping>`, `sudo openffb -h=0 -gp=<ffb>`. **(Pi)**
3. Écrit `/var/log/activerom/<rom>` et `/var/www/logs/log.txt` (`"<rom> <ip>"`).
4. Démarre, selon le nom de la ROM, les émulateurs de cartes (Initial D, F-Zero, MKGP, WMMT),
   `/usr/lib/cycraft` et `mjpg_streamer`. **(Pi / matériel)**
5. Envoie la ROM :
   ```python
   romfile = '/boot/roms/' + argv[1]
   if srvmode == 'serveron':
       cmd = 'sudo python3 /sbin/piforce/dm_netboot/netdimm_ensure ' + ip + ' ' + romfile
   else:
       cmd = 'sudo python3 /sbin/piforce/dm_netboot/netdimm_send ' + ip + ' ' + romfile + ' --disable-crc'
   os.system(cmd)
   if argv[4] == 'hackon':
       os.system('sudo python3 /sbin/piforce/timehack.py ' + ip + ' &')
   ```
6. `netdimm_send` décompresse via `pigz -cd`, applique les éventuels patches et réglages,
   puis appelle `NetDimm.send()` et `reboot()`.

### 2.4 Droits

- `/etc/sudoers.d/web` : `www-data ALL = (root) NOPASSWD: ALL`, c'est-à-dire **root total depuis le web**.
- `/etc/sudoers.d/dietpi` : `dietpi ALL=NOPASSWD: ALL`.
- Ces règles ne sont **pas versionnées** dans le fork.

### 2.5 Autres appels PHP → shell liés à la NetDIMM

| Page | Commande |
|---|---|
| `fwupdatesend.php` | `sudo python3 wipiloaderfw.py <fwfile> <ip>`, qui lance `netdimm_send` sur `FW_Netdimm_40x.bin.gz` |
| `naomidiag.php` | `sudo python3 dm_netboot/netdimm_send <ip> homebrew/naomidiag/naomidiag.bin.gz` |
| `dimmscanner.php` | `nmap --open -oG /sbin/piforce/nmap.txt -p10703 <plage>` (découverte des NetDIMM) |
| `dimms.php`, `updatedimms.php`, `deletedimm.php` | ping des DIMM, modification de `dimms.csv`, envoi du jeu par défaut |
| `romaudit.php`, `saveaudit.php` | `sudo python3 auditnames.py <path>` (identification des ROMs par hash et en-tête), `renamecsv.py` |
| `importcsv.php`, `dumpcsv.php`, `editgamelist.php`, `updatecsv*.php` | gestion de `romsinfo.csv` |
| `options.php` → `switchmode.php` | bascules : Single Boot, Server Mode, Time Hack, OSM (on/off, thème, replay/once), menu simple ou avancé |

---

## 3. Python et dépendances

- **Chemin du netboot : 100 % Python 3** (3.7 sur Buster). Les `.pyc` de `__pycache__` sont en cpython-37.
- Scripts annexes en **Python 2** : wifi, bluetooth, configuration, devicelist, audit et CSV
  (`#!/usr/bin/python -u` ou appel par `sudo python`).
- Paquets Python 2 (`/usr/local/lib/python2.7/dist-packages`) : Adafruit_CharLCD, Adafruit_GPIO,
  pycrypto, pyserial, pyscard, rfidiot, ndeflib, evdev, psutil, wifi, requests.
- Paquets Python 3 : psutil, RPi.GPIO (importé dans `wipiloader.py` mais **jamais utilisé**),
  evdev, filehash, plus les dépendances de `dm_netboot`.
- Binaires système : `fping`, `nmap`, `pigz`, `openjvs`, `openffb`, `mjpg_streamer`, `cycraft` (ARM).

**Pour la cible**, il suffit de Python 3.11 (Debian 12) avec pycryptodome, arcadeutils et pyyaml,
plus le backend. `fping`, `nmap` et `pigz` sont remplacés par du Python (socket et gzip).

---

## 4. Écarts entre l'image 6.1.4 et le fork

| Sujet | Image 6.1.4 | Fork (6.1-92 + launcher) |
|---|---|---|
| Netboot | `dm_netboot` (perdu à l'extraction) | `dm_netboot` présent et complet |
| `triforcetools.py`, `webforce*.py` | absents | supprimés (`6607ade`) |
| Firmware | `.bin` | `.bin.gz` |
| Frontend | PHP seul | PHP + `launcher/` (21 commits, kiosque 3.5") |
| Appel de `wipiloader` | sans échappement (injection possible) | `escapeshellarg`, POST + en-tête `X-Launcher` |
| Persistance de l'état | aucune | `launcher/data/*.json` |
| Mode simulation | — | `launcher/config.php` `simulate=false` (scénarios de test `?sim=`) |
| Déploiement | image SD | `tools/deploy.sh` (tar via ssh, launcher uniquement) |

**Manques et défauts du fork** :

- `servermode.txt` absent ;
- `sudoers` et unités systemd non versionnés ;
- `relaymode` transmis mais ignoré ;
- aucun test, aucun lint, aucun `.gitignore` à la racine ;
- binaires commités : firmwares Sega, `cycraft`, `tft35a.dtbo`, 1,2 Go de vidéos et 19 Mo
  d'images (`.git` fait 1,3 Go), plus les `.pyc`.

---

## 5. Sécurité (constats)

1. `www-data` est root sans mot de passe : toute faille PHP donne la prise de contrôle complète.
2. `load.php`, `loadcheck.php` et `updatedimms.php` injectent des paramètres GET dans le shell.
   `escapeshellcmd` n'empêche pas d'ajouter des arguments.
3. Aucune authentification sur l'interface.
4. SSH root avec mot de passe `raspberry` (documenté dans l'aide).

La cible les supprime tous : service non-root, aucun shell, authentification optionnelle (voir ARCHITECTURE).

---

## 6. Dépendances au matériel Pi : décision

Décision utilisateur : seules les fonctions **réseau / NetDIMM** sont conservées.

| Fonction | Fichiers concernés | Décision |
|---|---|---|
| Écran 3.5" tactile tft35a, kiosque Chromium, calibration, veille | `boot/config.txt.lcd35`, `etc/xdg/openbox/autostart`, `launcher/kiosk/` | **Abandon**. L'interface web la remplace |
| LCD 16x2 I2C + boutons (`lcd-piforce`) | `switchmode.py`, `lcdmode.txt` | **Abandon** |
| Rotary sur le HAT (GPIO BCM 18–21) | `rotary*.py` | **Abandon** |
| Relais de redémarrage GPIO26 | `relaymode.txt` (déjà inutilisé) | **Abandon** |
| Point d'accès Wi-Fi, `/boot/wifi.txt`, `reset.txt` | `hotspot*.py`, `homewifi.py` | **Abandon** (réseau Proxmox) |
| Bluetooth | `bluetooth*.py` | **Abandon** |
| `/boot` en FAT | partout | **Remplacé** par `/srv/wipi` (configurable) |
| Émulation de lecteurs de cartes (série ttyUSB) | `card_emulator/*`, `launchcard.php` | **Abandon** |
| NFC ACR122U | `nfc*.py` | **Abandon** |
| OpenJVS (HAT ou RS485 USB), OpenFFB | `openjvs*.service`, `hatupdate.sh`, `mastermapping.csv` | **Abandon**. Les colonnes `openjvs`/`openffb` sont ignorées mais conservées dans le CSV |
| `cycraft`, `mjpg_streamer` | `/usr/lib/cycraft` (ARM) | **Abandon** |
| Déclencheur du menu OSM par manette (evdev `/dev/input/event0`) | `menulauncher.py` | **Remplacé** par un bouton « relancer le menu » dans l'interface |
| Mise à jour APT `wipi`, reboot/shutdown du Pi | `update.php`, `reboot.php` | **Remplacé** par `deploy/install.sh` et `pct` |

### Fonctions NetDIMM conservées

| Fonction | Origine |
|---|---|
| Lancement d'un jeu sur une borne (choix de la DIMM compatible, progression, annulation) | `load*.php`, `wipiloader.py`, `netdimm_send` |
| Mode serveur : renvoi automatique si la borne redémarre | `netdimm_ensure` |
| Time hack (zero-key) par borne | `timehack.py` |
| Démarrage automatique (`defaultgame` par borne, ou menu) | `singleboot.py` |
| Menu OSM (netbootmenu, thème clair/sombre, replay/once) | `netdimm_menu`, `menulauncher.py` |
| Informations DIMM (firmware, mémoire, état) | `netdimm_info` |
| Mise à jour du firmware NetDIMM 4.01/4.02/4.03 | `fwupdate*.php`, `netdimm_firmware` |
| Diagnostic Naomi (homebrew `naomidiag`) | `naomidiag.php` |
| Découverte des NetDIMM sur le sous-réseau (port 10703) | `dimmscanner.php` |
| Gestion des bornes (CRUD, type, jeu par défaut) | `dimms.php`, `updatedimms.php`, `deletedimm.php` |
| Gestion des jeux (activer, favoris, édition, import/export CSV, audit et renommage des ROMs) | `editgamelist.php`, `updatecsv*.php`, `importcsv.php`, `dumpcsv.php`, `romaudit.php` |
| Gestion des fichiers ROM et médias (upload, suppression) | `filemanager/` |
