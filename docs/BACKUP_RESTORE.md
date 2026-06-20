# Backup & Restore

## Backup
```bash
python scripts/backup_sqlite.py
python scripts/backup_sqlite.py --db instance/app.db --out backups/
python scripts/backup_sqlite.py --dry-run  # preview only
```

Output: `backups/backup-YYYYMMDD-HHMMSS-app.db`

## Restore
```bash
python scripts/restore_sqlite.py --backup backups/backup-xxx-app.db
python scripts/restore_sqlite.py --backup backups/backup-xxx-app.db --db instance/app.db
python scripts/restore_sqlite.py --backup backups/backup-xxx-app.db --dry-run
```

Restore automatically creates a pre-restore backup of the current DB before overwriting.

## Important
- Never commit `*.db` files to git
- Keep `backups/` in `.gitignore`
- Backups are plain SQLite copies — ensure file permissions are restricted
