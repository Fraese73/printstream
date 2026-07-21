# Deployment

```bash
sudo ./scripts/install.sh
sudo nano /opt/printstream/.env
sudo nano /opt/printstream/.env.secrets
sudo chmod 600 /opt/printstream/.env.secrets
sudo systemctl enable --now printstream
```
