# Operations Manual

## Start / Stop / Restart
```bash
sudo systemctl start ai-seo-factory
sudo systemctl stop ai-seo-factory
sudo systemctl restart ai-seo-factory
```

## View Logs
```bash
tail -f logs/gunicorn-access.log
tail -f logs/gunicorn-error.log
journalctl -u ai-seo-factory -f
```

## Health Check
```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/ready
```

## Release Check
```bash
python scripts/release_check.py
python scripts/deploy_check.py --strict
```

## Backup
```bash
python scripts/backup_sqlite.py --db data/app.db --out backups/
```

## Restore
```bash
python scripts/restore_sqlite.py --backup backups/backup-xxx-app.db --db data/app.db
# Add --dry-run to preview
```

## Usage Report
```bash
python scripts/usage_report.py --tenant-id 1
```

## Sync Dry-Run
```bash
python scripts/sync_page_content.py --project-id 1 --dry-run
```

## Rollback Dry-Run
```bash
python scripts/rollback_publish.py --project-id 1 --dry-run
```
