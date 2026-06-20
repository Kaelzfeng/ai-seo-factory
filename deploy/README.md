# Deployment Assets

- `gunicorn.conf.py` — Gunicorn WSGI server config
- `systemd.service.example` — systemd unit file template
- `nginx.conf.example` — Nginx reverse proxy template
- `env.production.example` — production environment variables template

## Usage

```bash
# Copy and edit
cp deploy/env.production.example .env
# Edit .env with real values
vi .env

# Start with gunicorn
.venv/bin/gunicorn -c deploy/gunicorn.conf.py app:app

# Install systemd service
sudo cp deploy/systemd.service.example /etc/systemd/system/ai-seo-factory.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-seo-factory
```
