#!/usr/bin/env python
"""scripts/sync_page_content.py · Phase 6: 发布同步 CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(description="同步 PageContent 到 CMS")
    p.add_argument("--page-content-id", type=int)
    p.add_argument("--project-id", type=int)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--mode", default="draft", choices=["draft","publish"])

    args = p.parse_args()
    from lib.publish_sync import sync_page_content, sync_project_pages

    if args.page_content_id:
        r = sync_page_content(args.page_content_id, 1, dry_run=args.dry_run, mode=args.mode)
    elif args.project_id:
        r = sync_project_pages(args.project_id, 1, dry_run=args.dry_run, mode=args.mode)
    else:
        print("Need --page-content-id or --project-id")
        sys.exit(1)

    print(f"ok={r['ok']}", f"status={r.get('status','?')}")
    if "results" in r:
        for i in r["results"]:
            print(f"  pc={i.get('page_content_id')} status={i.get('status')}")

if __name__ == "__main__":
    main()
