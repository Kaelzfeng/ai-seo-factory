# Security

## SECRET_KEY
- Must be changed from default in production
- Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- Never commit to git

## API Keys
- `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY` — stored in `.env` only
- Never logged or exposed in config report (masked)
- `.env` is in `.gitignore`

## Database
- SQLite file at `data/app.db` (or `instance/app.db`)
- Restrict file permissions: `chmod 600 data/app.db`
- WAL mode enabled for concurrent reads

## HTTPS
- Use Nginx + Let's Encrypt for production
- Set `proxy_set_header X-Forwarded-Proto https`

## Security Headers
Applied automatically:
- X-Content-Type-Options: nosniff
- X-Frame-Options: SAMEORIGIN
- Referrer-Policy: strict-origin-when-cross-origin

## WordPress
- Use Application Passwords, not main account passwords
- Never commit `wp_app_password` to git

## Webhooks
- Default dry-run mode — no real HTTP dispatch
- Configure `WEBHOOK_URL` only when ready
