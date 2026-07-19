# PrintStream

PrintStream ist eine modulare Open-Source-Plattform zum Livestreamen, Überwachen und Automatisieren von 3D-Druckern.

## Schnellstart

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv python3-pip git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload
```

Weboberfläche: `http://IP-DES-PI:8088`

Weitere Informationen: `PROJECT_CONTEXT.md`, `ROADMAP.md`, `AGENTS.md`.
