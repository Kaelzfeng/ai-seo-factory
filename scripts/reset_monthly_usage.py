#!/usr/bin/env python
"""scripts/reset_monthly_usage.py · Phase 7: 月度重置 CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(); p.add_argument("--tenant-id", type=int); p.add_argument("--all", action="store_true"); p.add_argument("--dry-run", action="store_true", default=True)
    args = p.parse_args()
    from lib.monthly_reset import reset_monthly_usage, reset_all_tenants_monthly_usage
    if args.all:
        r = reset_all_tenants_monthly_usage(dry_run=args.dry_run)
    elif args.tenant_id:
        r = reset_monthly_usage(args.tenant_id, dry_run=args.dry_run)
    else:
        print("Need --tenant-id or --all"); sys.exit(1)
    print(f"ok={r['ok']} dry_run={r.get('dry_run')}")

if __name__ == "__main__": main()
