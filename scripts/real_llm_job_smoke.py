#!/usr/bin/env python
"""scripts/real_llm_job_smoke.py · Phase 9.2: Real LLM Job Smoke"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", default=True)
    p.add_argument("--real-llm", action="store_true")
    args = p.parse_args()

    import os
    if args.mock:
        os.environ["LLM_PROVIDER"] = "mock"

    from lib.generation_job_mode import create_generation_job, run_generation_job, get_generation_job_status

    print(f"Provider: {os.environ.get('LLM_PROVIDER', 'auto')}")
    t0 = time.time()

    r = create_generation_job(1, project_id=1, user_input="PU leather B2B export site", mode="dry-run")
    jid = r["job_id"]
    print(f"Created job_id={jid}")

    t1 = time.time()
    result = run_generation_job(jid, tenant_id=1)
    elapsed = time.time() - t1

    s = get_generation_job_status(jid)
    print(f"Status: {s['status']}")
    print(f"Pages: {s.get('pages_success',0)}/{s.get('pages_total',0)}")
    print(f"Elapsed: {elapsed:.0f}s")
    print(f"Overall: {'PASS' if s['status'] in ('completed','partial_success') else 'FAIL'}")

if __name__ == "__main__": main()
