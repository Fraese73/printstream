# Arbeitsauftrag für Cursor

Du arbeitest am Projekt **PrintStream**.

## Umgebung
- Raspberry Pi 5, 16 GB RAM
- Debian 13 Trixie, aarch64
- ioBroker läuft parallel
- OctoPrint: `http://192.168.2.59`
- Webcam: `http://192.168.2.59/webcam/?action=stream`
- YouTube-Ausgabe über RTMPS Port 443

## Ziel
Einen stabilen Streaming-Server entwickeln, der den OctoPrint-Webcamstream mit FFmpeg zu YouTube sendet und Druckdaten anzeigt.

## Leitlinien
- Python 3.11+, FastAPI, FFmpeg
- Konfiguration nur über `.env`
- nie `shell=True`
- Streamschlüssel nie loggen
- API-Key nie ans Frontend senden
- geringe CPU-Last, ioBroker darf nicht beeinträchtigt werden
- Prozesse sauber starten und stoppen

## Nächste Aufgaben
1. Bestehende Dateien prüfen.
2. FFmpeg-Kommando robust machen.
3. Start, Stop, Status und Health-Endpunkt testen.
4. FFmpeg-Fehler im Webinterface anzeigen.
5. Tests für die Kommandoerzeugung schreiben.
6. Danach Overlay mit Fortschritt und Temperaturen ergänzen.
