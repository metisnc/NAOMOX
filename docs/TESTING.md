# Tests et vérification

## 1. Tests automatisés

### Backend (pytest + ruff)

Ces tests tournent dans le CT de dev ou sur n'importe quel Linux avec Python 3.11 ou plus.

```sh
tools/dev-sync.sh 'ruff check . && ruff format --check . && pytest -q'
# ou localement :
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && pytest -q
```

| Fichier | Couvre |
|---|---|
| `test_protocol.py` | la bibliothèque `netdimm` contre le **mock NetDIMM** : ordre et contenu des paquets (startup, host mode, zero-key, désactivation du CRC, upload par blocs 0x8000, set information, restart, time limit), lecture info/firmware, refus de connexion |
| `test_transfer.py` | le sous-processus de transfert : décompression gzip, événements JSON, vérification taille/CRC, ROM absente, borne injoignable, coupure en cours d'envoi |
| `test_jobs.py` | la file par borne : sérialisation, annulation (en cours et en attente), timeout global, timeout de la bibliothèque, relances automatique et manuelle |
| `test_supervisor.py` | la présence avec anti-rebond, le time hack, le démarrage automatique (une seule fois), le mode serveur (renvoi seulement si le CRC diffère après coupure), info et reboot |
| `test_storage.py` | les noms de fichiers sûrs (vrais noms de ROM, traversée refusée), le CSV romsinfo, le CRUD des bornes, le runtime, l'historique, la compatibilité |
| `test_api.py` | l'API HTTP : CSRF, CRUD, lancement (auto, choix, incompatible, ROM absente), scan, upload, médias, info, firmware, authentification |
| `test_e2e.py` | **bout en bout** avec un vrai serveur uvicorn, le mock et le flux SSE : lancement jusqu'à `done` |

Le mock sert aussi de **borne virtuelle** :

```sh
naomox mock --host 127.0.0.2 --port 10703 --firmware 4.03
```

### Frontend

```sh
cd frontend && npm ci
npm run check     # svelte-check : 0 erreur, 0 avertissement
npm run build     # → frontend/dist
```

### Interface de bout en bout (Playwright, navigateur installé)

Ce test pilote **l'interface** dans Edge (ou Chrome avec `NAOMOX_E2E_BROWSER=chrome`), en
viewport mobile. Il enchaîne :

1. recherche de la NetDIMM ;
2. ajout de la borne ;
3. lecture des infos (firmware) ;
4. scan des ROMs ;
5. lancement du jeu fictif ;
6. suivi en direct jusqu'à « Terminé ».

Il lui faut une instance **jetable**. Pour la préparer dans le CT, sans toucher à l'instance
principale :

```sh
ssh root@192.168.1.230 '
mkdir -p /tmp/naomox-e2e/data/roms
head -c 3000000 /dev/urandom | gzip -1 > /tmp/naomox-e2e/data/roms/n1-naomox_e2e_test.bin.gz
cat > /tmp/naomox-e2e/config.yaml <<EOF
paths: {data: /tmp/naomox-e2e/data, frontend: /opt/naomox/frontend}
http: {host: 0.0.0.0, port: 8081}
network: {cabinet_subnet: 127.0.0.0/29}
netdimm: {port: 10799, probe_interval: 1}
EOF
chown -R naomox:naomox /tmp/naomox-e2e
systemd-run --unit naomox-e2e-mock --uid naomox /opt/naomox/venv/bin/naomox mock --port 10799 --firmware 4.03
systemd-run --unit naomox-e2e --uid naomox -E NAOMOX_CONFIG=/tmp/naomox-e2e/config.yaml /opt/naomox/venv/bin/naomox serve'

cd frontend && NAOMOX_E2E_URL=http://naomox.local:8081 npm run e2e
# Captures : frontend/e2e/.results/screens/

ssh root@192.168.1.230 'systemctl stop naomox-e2e naomox-e2e-mock; rm -rf /tmp/naomox-e2e'
```

### Dernier résultat (2026-10-16)

| Vérification | Résultat |
|---|---|
| pytest | **81 passed** (≈ 15 s) : protocole, transfert, jobs, supervision, API, firmware (garde-fous), logos recadrés, nom réseau mDNS, e2e |
| ruff | `check` et `format --check` propres |
| svelte-check | 0 erreur, 0 avertissement |
| Playwright | 1 passed (une borne : lancement direct) ; vérifié aussi à la main avec deux bornes virtuelles (choix proposé) |
| Déploiement | `install.sh` idempotent ; service `naomox` actif ; `http://naomox.local` résolu depuis Windows |
| Matériel réel | NetDIMM firmware 4.01 : info lue, **premier lancement de jeu réussi** (2026-10-16) ; checklist complète à dérouler |
| Installation Proxmox | commande unique testée : mode automatisé et assistant (installation par l'utilisateur), conteneurs de test supprimés |

---

## 2. Checklist de test réel sur borne

À faire par toi, sur le matériel. Cocher, et noter toute anomalie avec le **journal du job**
(Activité → Journal) et `journalctl -u naomox --since "10 min ago"`.

### Préparation

- [ ] La NetDIMM est réglée dans le menu de test (NETWORK SETTING) : IP fixe hors plage DHCP,
      masque `255.255.255.0`, `ETHER`, `REMOTE DISABLE`.
- [ ] Depuis le CT, `ping <ip>` répond.
- [ ] `timeout 2 bash -c '</dev/tcp/<ip>/10703' && echo ok` affiche `ok`.
- [ ] Bornes → **Rechercher** trouve l'IP. Ajouter la borne avec le **bon type**.
- [ ] La pastille passe au vert (« en ligne ») en moins de 10 s.
- [ ] Bornes → **Infos** affiche le bon firmware, la mémoire et un CRC.
      Firmware attendu : ____ ; firmware affiché : ____.

### Lancement (pour chaque type de carte disponible)

| # | Test | Naomi | Naomi 2 | Chihiro | Triforce |
|---|---|---|---|---|---|
| 1 | Lancer un petit jeu : « NOW LOADING » s'affiche sur la borne | ☐ | ☐ | ☐ | ☐ |
| 2 | La barre de progression avance dans l'interface pendant l'envoi | ☐ | ☐ | ☐ | ☐ |
| 3 | Les états **Vérification** puis **Redémarrage** passent, puis **Terminé** | ☐ | ☐ | ☐ | ☐ |
| 4 | Le jeu démarre sur la borne | ☐ | ☐ | ☐ | ☐ |
| 5 | Durée d'envoi notée (ROM la plus grosse) : ____ s | | | | |
| 6 | Lancer un 2e jeu pendant que le 1er tourne : il remplace le 1er | ☐ | ☐ | ☐ | ☐ |
| 7 | Deux lancements d'affilée : le 2e attend son tour (« En attente ») | ☐ | | | |
| 8 | **Annuler** pendant l'envoi : état « Annulé ». Relancer ensuite fonctionne | ☐ | | | |
| 9 | Débrancher le câble pendant l'envoi : erreur claire (timeout, déconnexion ou vérification), puis **Relancer** fonctionne | ☐ | | | |
| 10 | Borne éteinte : lancer donne « aucune borne compatible n'est en ligne » ; l'erreur `unreachable` arrive en moins de 20 s si la borne est choisie explicitement | ☐ | | | |
| 11 | Jeu Naomi 2 vers une borne Naomi : refusé (incompatible) | ☐ | | | |
| 12 | Jeu Atomiswave vers Naomi (avec AW-NET) | ☐ | | | |

> Si l'étape **Vérification** échoue alors que le jeu se lancerait normalement, noter le
> message exact (tailles et CRC), puis mettre `netdimm.verify_upload: false` dans
> `/etc/naomox/config.yaml` et redémarrer le service. C'est le seul ajout au déroulé WiPi
> d'origine : il réutilise la requête « information » standard. Ce point doit être confirmé
> sur matériel réel.

### Options par borne

- [ ] **Time hack** (borne **sans** PIC zero-key) : le jeu tourne plus de 15 min sans
      s'arrêter. L'interface n'affiche pas « time hack en échec ».
- [ ] **Time hack désactivé** sans PIC zero-key : le jeu s'arrête comme attendu (contre-test).
- [ ] **Au démarrage** = un jeu : `systemctl restart naomox`, puis allumer la borne. Le jeu est
      envoyé automatiquement, une seule fois.
- [ ] **Mode serveur** : lancer un jeu, puis couper et rallumer la borne. Le jeu est renvoyé
      automatiquement (source « mode serveur » dans l'Activité), et la NetDIMM affiche le
      contrôle CRC.
- [ ] **Mode serveur**, NAOMOX redémarré borne allumée : **pas** de renvoi, puisque le CRC est
      identique.
- [ ] **Redémarrer** (bouton) : la borne redémarre sur le jeu chargé.

### Maintenance

- [ ] **Diagnostic Naomi** : le homebrew naomidiag s'affiche.
- [ ] **Firmware** (facultatif, à tes risques) : version actuelle ____ → cible ____. Suivre
      les instructions à l'écran et vérifier la nouvelle version dans Infos. Depuis 3.x,
      passer d'abord en 4.01.

### Interface

- [ ] Téléphone et tablette : grille, recherche, filtres, favoris.
- [ ] Fiche d'un jeu : la vidéo se lit.
- [ ] Ajout à l'écran d'accueil (PWA).
- [ ] Deux appareils ouverts en même temps : la progression apparaît en direct sur les deux.
- [ ] Coupure Wi-Fi du téléphone puis retour : « en direct » revient, et l'état est resynchronisé.
- [ ] (Si activée) authentification : la connexion et la déconnexion fonctionnent.

### Non couvert dans cette version

- **Menu OSM** (netbootmenu : choix du jeu à la manette sur l'écran de la borne). Le homebrew
  est installé, mais `netdimm_menu` n'est pas encore porté. L'option « menu » au démarrage est
  ignorée, avec un avertissement dans le journal.
