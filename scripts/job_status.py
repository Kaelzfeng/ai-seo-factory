#!/usr/bin/env python
"""scripts/job_status.py · Phase 9.2: Job 状态查询"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--job-id", type=int)
    p.add_argument("--project-id", type=int)
    args = p.parse_args()
    from lib.generation_job_mode import get_generation_job_status
    if args.job_id:
        s = get_generation_job_status(args.job_id)
        print(f"Job {args.job_id}: {s.get('status','?')} "
              f"pages={s.get('pages_success',0)}/{s.get('pages_total',0)} "
              f"step={s.get('last_step','?')}")
    elif args.project_id:
        print(f"Project {args.project_id} jobs: (use get_generation_job_status for per-job)")
    else:
        p.print_help()

if __name__ == "__main__": main()
