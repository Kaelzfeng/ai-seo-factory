#!/usr/bin/env python
"""scripts/backup_sqlite.py · Phase 9: SQLite 备份"""
import argparse, os, shutil, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/app.db")
    p.add_argument("--out", default="backups")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_name = f"backup-{stamp}-{db_path.name}"
    out_path = Path(args.out) / out_name
    if args.dry_run:
        print(f"[DRY-RUN] Would backup: {db_path} -> {out_path}")
        return
    os.makedirs(args.out, exist_ok=True)
    shutil.copy2(db_path, out_path)
    print(f"[OK] Backup created: {out_path} ({db_path.stat().st_size} bytes)")

if __name__ == "__main__": main()
