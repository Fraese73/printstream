# Overlay-Logo

Lege hier deine Logo-Datei ab (**PNG mit echter Alpha-Transparenz**):

- Standardpfad: `assets/logo.png`
- In `.env`: `OVERLAY_LOGO_ENABLED=true` und `OVERLAY_LOGO_PATH=assets/logo.png`

Wichtig: Kein Schachbrett-Hintergrund in der Datei – der muss transparent sein (RGBA),
sonst erscheint das Karomuster im Stream.

Position oben rechts per FFmpeg-Ausdruck (`OVERLAY_LOGO_X=W-w-24`, `OVERLAY_LOGO_Y=24`).
