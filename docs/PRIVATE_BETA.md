# Private Beta Guide

## Objective
Validate the AI SEO Content Factory with 2-5 private beta users who need B2B content generation.

## Server Setup
```bash
bash scripts/server_bootstrap.sh
cp deploy/env.production.example .env  # edit with real values
bash scripts/start_gunicorn.sh
```

## Demo User
```bash
python scripts/create_demo_user.py --email user@company.com
```

## Minimum Demo Flow
1. `POST /api/seo/clarify` with industry input
2. `POST /api/seo/blueprint` — view page plan
3. `POST /api/seo/generate-from-input` — generate 8 pages
4. `GET /api/page-contents` — view results

## Beta Limits (Free Plan)
- 3 generations/month
- 100K tokens/month
- 1 competitor analysis
- 3 publish syncs
- 1 project, 1 site

## Feedback Collection
- Track errors via `/api/audit/logs`
- Monitor usage via `python scripts/usage_report.py --tenant-id N`

## Rollback
```bash
python scripts/restore_sqlite.py --backup backups/latest.db
```
