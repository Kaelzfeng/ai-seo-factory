# Deployment Guide

## Local Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # edit with your keys
python scripts/dev_bootstrap.py
python run.py industries/pu-leather.yaml --dry-run
python -m pytest tests/ -v
python app.py
```

## Environment Variables

See `docs/ENVIRONMENT.md` for full list.

## Database

SQLite by default at `data/app.db`. WAL mode enabled. No migration tool needed — tables auto-created on first access.

## Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## systemd

```ini
[Unit]
Description=AI SEO Content Factory
[Service]
User=app
WorkingDirectory=/opt/ai-seo-factory
ExecStart=/opt/ai-seo-factory/.venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always
[Install]
WantedBy=multi-user.target
```

## Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name factory.example.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Cloudflare / VPS Notes

- Enable HTTPS (Full/Strict)
- Set minimum TLS 1.2
- Enable Brotli compression
- Cache static assets at edge

## Security Checklist

- [ ] Change SECRET_KEY from default
- [ ] Set strong WordPress app passwords
- [ ] Enable HTTPS
- [ ] Review CSP headers for production
- [ ] Run `python scripts/release_check.py --strict`
