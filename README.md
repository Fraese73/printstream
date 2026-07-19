# PrintStream

PrintStream ist ein Streaming-Server für 3D-Drucker. Er läuft auf einem Raspberry Pi 5, liest Druckdaten aus OctoPrint und sendet das Kamerabild mit FFmpeg zu YouTube Live.

## MVP
- Webcam-Stream von OctoPrint lesen
- Stream per RTMPS zu YouTube senden
- Stream per Weboberfläche starten und stoppen
- FFmpeg-Status und Fehlerlog anzeigen
- OctoPrint-Daten abrufen
- Overlay mit Fortschritt, Temperaturen und Restzeit

## Zielsystem
- Raspberry Pi 5, Debian 13, aarch64
- Python 3.11+
- FFmpeg (mit libfreetype / drawtext)
- Fonts: `fonts-dejavu-core` für das Overlay
- OctoPrint im lokalen Netzwerk

## Schnellstart
```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv python3-pip git fonts-dejavu-core
cp .env.example .env
nano .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload
```
Dann: `http://IP-DES-PI5:8088`

Tests: `pytest`

Wichtig: Streamschlüssel und API-Key niemals committen.
