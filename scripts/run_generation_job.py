#!/usr/bin/env python
"""scripts/run_generation_job.py · Phase 9.2: Job Mode CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--create", action="store_true")
    p.add_argument("--job-id", type=int)
    p.add_argument("--run", action="store_true")
    p.add_argument("--run-background", action="store_true")
    p.add_argument("--project-id", type=int, default=1)
    p.add_argument("--input", default="I want an English B2B export site for PU leather")
    p.add_argument("--dry-run", action="store_true", default=True)
    args = p.parse_args()

    from lib.generation_job_mode import (
        create_generation_job, run_generation_job, run_generation_job_background,
        get_generation_job_status,
    )

    if args.create:
        r = create_generation_job(1, project_id=args.project_id, user_input=args.input, mode="dry-run" if args.dry_run else "publish")
        print(f"Created job_id={r['job_id']} status={r['status']}")
        print(f"Next: python scripts/run_generation_job.py --job-id {r['job_id']} --run")
    elif args.job_id and args.run:
        r = run_generation_job(args.job_id, tenant_id=1)
        s = get_generation_job_status(args.job_id)
        print(f"job_id={args.job_id} status={s['status']} pages={s.get('pages_success',0)}/{s.get('pages_total',0)}")
    elif args.job_id and args.run_background:
        r = run_generation_job_background(args.job_id, tenant_id=1)
        print(f"job_id={args.job_id} status={r['status']} (background)")
    else:
        p.print_help()

if __name__ == "__main__": main()
