# PROJECT_CONTEXT.md

## Aktueller Stand

- FastAPI-Grundgerüst
- `.env`-Konfiguration und Secrets in `.env.secrets`
- FFmpeg-Start, Stop und Status
- OctoPrint-Statusabfrage
- Jinja2-Weboberfläche
- systemd-Vorlage

## Umgebung

- OctoPrint: `http://192.168.2.59`
- Webcam: `http://192.168.2.59/webcam/?action=stream`
- YouTube bevorzugt per RTMPS

## Nächste Schritte

1. `.env` und `.env.secrets` einrichten.
2. lokalen Start testen.
3. YouTube-Teststream durchführen.
4. systemd-Dienst auf dem Pi aktivieren.
5. Logging und automatischen Neustart ergänzen.
