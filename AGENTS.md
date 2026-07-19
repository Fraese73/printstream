# AGENTS.md

## Ziel

PrintStream streamt eine OctoPrint-Webcam per FFmpeg zu YouTube und zeigt Druckdaten an.

## Zielumgebung

- Raspberry Pi 5, 16 GB RAM
- Debian 13 Trixie, aarch64
- FFmpeg und Python 3.11+
- ioBroker läuft parallel

## Regeln

- API unter `/api/v1` versionieren.
- FFmpeg als separaten Prozess starten.
- Niemals `shell=True` verwenden.
- Secrets niemals loggen oder committen.
- Konfiguration aus `.env` laden.
- Python `logging`, Type Hints und Tests verwenden.
- Vor größeren Änderungen zuerst einen kurzen Plan erstellen.

## Stream-Zustände

`STOPPED`, `STARTING`, `RUNNING`, `STOPPING`, `ERROR`
