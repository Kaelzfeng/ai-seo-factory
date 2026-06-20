#!/usr/bin/env python
"""scripts/rollback_publish.py · Phase 6: 发布回滚 CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(description="回滚 CMS 发布")
    p.add_argument("--snapshot-id", type=int)
    p.add_argument("--project-id", type=int)
    p.add_argument("--dry-run", action="store_true", default=True)

    args = p.parse_args()
    from lib.publish_rollback import rollback_page_content, rollback_project

    if args.snapshot_id:
        r = rollback_page_content(args.snapshot_id, 1, dry_run=args.dry_run)
    elif args.project_id:
        r = rollback_project(args.project_id, 1, dry_run=args.dry_run)
    else:
        print("Need --snapshot-id or --project-id")
        sys.exit(1)

    print(f"ok={r['ok']}", f"status={r.get('status','?')}")
    if "results" in r:
        for i in r["results"]:
            print(f"  snap={i.get('snapshot_id')} status={i.get('status')}")

if __name__ == "__main__":
    main()
