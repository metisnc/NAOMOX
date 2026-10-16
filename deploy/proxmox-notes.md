# 🕹️ NAOMOX — netbooter NetDIMM

Lance les jeux **Sega Naomi / Naomi 2 / Atomiswave / Chihiro / Triforce** sur les bornes équipées d'une NetDIMM, depuis un téléphone ou une tablette.

## Accès
| | |
|---|---|
| **Interface web** | `http://<nom-du-conteneur>.local` ou `http://<IP-du-conteneur>` |
| **Login conteneur** (console Proxmox) | `root` / mot de passe défini à la création (`naomox` par défaut avec `pct-create.sh`) |
| **SSH / SFTP** | `naomox` / même mot de passe que root par défaut — on arrive dans `/srv/naomox` (ROMs dans `roms/`) ; administration : `su -` |
| Mot de passe de l'interface web | aucun par défaut (activable dans `/etc/naomox/config.yaml`) |

L'IP du conteneur : onglet **Réseau** de ce CT, ou `hostname -I` dans la console.
Le nom `.local` se change dans l'interface : **Réglages → Réseau → Nom réseau**.

## Conteneur
- LXC non privilégié Debian 12 ou 13, démarrage automatique
- **Disque racine** : système + application (`/opt/naomox`)
- **Point de montage 0** → `/srv/naomox` : toutes les données
  - `roms/` ROMs · `media/` jaquettes, vidéos, logos de systèmes · `firmware/` firmwares NetDIMM · `state/` bornes, jeux, historique
- Sauvegarde : `vzdump <ID>` inclut les deux disques ; la configuration seule tient dans `/srv/naomox/state/`

## Service
- `systemctl status naomox` · journaux : `journalctl -u naomox -f`
- Configuration : `/etc/naomox/config.yaml` · utilisateur système `naomox` (sans sudo)
- Port web **80** · NetDIMM en **TCP 10703** · nom réseau annoncé en mDNS (avahi)

## Pack de contenu (ROMs, vidéos, liste des jeux)
- Exporter depuis l'hôte : `pct exec <ID> -- naomox-content export - > /chemin/naomox-content.tar`
- Importer : `pct exec <ID> -- naomox-content import - < /chemin/naomox-content.tar`

## Premiers pas
1. Déposer les ROMs dans `/srv/naomox/roms` (ou Réglages → Fichiers), puis Réglages → Jeux → **Scanner**.
2. Sur la borne, menu de test → NETWORK SETTING : IP fixe hors plage DHCP, masque 255.255.255.0.
3. Interface → **Bornes → Rechercher** pour l'ajouter.

## Mise à jour
Depuis le poste de dev : `deploy/push.sh` (voir `docs/DEPLOY.md` du dépôt NAOMOX).
