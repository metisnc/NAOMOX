# naomox (backend)

Service FastAPI qui pilote les NetDIMM : lancement de jeux, file d'attente par borne,
statut temps réel (SSE), time hack, mode serveur, démarrage automatique, firmware.

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest                 # tests (mock NetDIMM inclus)
ruff check .           # lint
naomox mock --port 10703 &                       # borne virtuelle
naomox serve --config ../deploy/config.example.yaml
```

`src/netdimm` est une copie de la bibliothèque de DragonMinded (domaine public) ; seules
modifications : port TCP configurable, suppression du fichier de progression WiPi.
