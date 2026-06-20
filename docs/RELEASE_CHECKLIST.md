# Release Checklist

## Before Release

- [ ] `python -m pytest tests/ -v` — all pass
- [ ] `python run.py industries/pu-leather.yaml --dry-run` — 8/8
- [ ] `python scripts/analyze_competitor.py "test" --mock` — OK
- [ ] `python scripts/check_config.py` — OK
- [ ] `python scripts/smoke_test.py` — OK
- [ ] `python scripts/release_check.py` — OK
- [ ] `git diff -- templates static` — no changes
- [ ] `.gitignore` covers `.env`, `*.db`, `__pycache__`
- [ ] No API keys in repo

## After Release

- [ ] Tag release: `git tag v1.0.0 && git push --tags`
- [ ] Update deployment: `git pull && systemctl restart ai-seo-factory`
- [ ] Monitor health: `curl /api/health`
