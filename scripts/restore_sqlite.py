#!/usr/bin/env python
"""scripts/restore_sqlite.py · Phase 9: SQLite 恢复"""
import argparse, os, shutil, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backup", required=True)
    p.add_argument("--db", default="data/app.db")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    backup_path = Path(args.backup)
    db_path = Path(args.db)
    if not backup_path.exists():
        print(f"ERROR: Backup not found: {backup_path}"); sys.exit(1)
    if args.dry_run:
        print(f"[DRY-RUN] Would restore: {backup_path} -> {db_path}")
        return
    # Pre-restore backup of current DB
    if db_path.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        pre_bak = db_path.parent / f"pre-restore-{stamp}-{db_path.name}"
        shutil.copy2(db_path, pre_bak)
        print(f"[OK] Pre-restore backup: {pre_bak}")
    shutil.copy2(backup_path, db_path)
    print(f"[OK] Restored: {backup_path} -> {db_path}")

if __name__ == "__main__": main()
