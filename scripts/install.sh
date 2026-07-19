#!/usr/bin/env bash
set -euo pipefail
APP_DIR=/opt/printstream
APP_USER=${SUDO_USER:-pi}
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv python3-pip
sudo mkdir -p "$APP_DIR"
sudo cp -R . "$APP_DIR"
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
cd "$APP_DIR"
sudo -u "$APP_USER" python3 -m venv .venv
sudo -u "$APP_USER" .venv/bin/pip install -r requirements.txt
[ -f .env ] || sudo -u "$APP_USER" cp .env.example .env
sudo cp systemd/printstream.service /etc/systemd/system/printstream.service
sudo systemctl daemon-reload
echo "Installation abgeschlossen. Bearbeite /opt/printstream/.env und starte anschließend den Dienst."
