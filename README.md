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
