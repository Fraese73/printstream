# Zu PrintStream beitragen

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ruff check .
black --check .
mypy app
pytest
```

Keine Secrets committen und keine Subprozesse mit `shell=True` starten.
