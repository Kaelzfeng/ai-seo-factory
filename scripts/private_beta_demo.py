#!/usr/bin/env python
"""scripts/private_beta_demo.py · Phase 9.3: Beta Demo 流程"""
import argparse, sys, time, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", default=True)
    p.add_argument("--real-llm", action="store_true")
    p.add_argument("--confirm-real-llm", action="store_true")
    args = p.parse_args()

    if args.real_llm and not args.confirm_real_llm:
        print("ERROR: --real-llm requires --confirm-real-llm (will consume API tokens)")
        sys.exit(1)

    if args.mock:
        os.environ["LLM_PROVIDER"] = "mock"

    ok = True
    def step(name, fn):
        nonlocal ok
        try:
            r = fn()
            status = "OK" if (isinstance(r, dict) and r.get("ok") is not False) else "WARN"
            print(f"[{status}] {name}")
            return r
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            ok = False; return None

    print(f"=== Private Beta Demo ({'mock' if args.mock else 'real-llm'}) ===\n")

    # 1. Bootstrap
    from lib.demo_data import bootstrap_demo_workspace
    ws = step("Bootstrap demo workspace", lambda: bootstrap_demo_workspace())
    if ws: print(f"  tenant={ws['tenant_id']} user={ws['user_id']} project={ws['project_id']}")

    # 2. Config
    from lib.config_check import get_config_report
    step("Config check", get_config_report)

    # 3. Create + run job (mock/small)
    from lib.generation_job_mode import create_generation_job, run_generation_job
    r = step("Create gen job", lambda: create_generation_job(ws["tenant_id"], ws["project_id"], user_input="PU leather B2B export site", mode="dry-run"))
    if r:
        step("Run gen job", lambda: run_generation_job(r["job_id"], tenant_id=ws["tenant_id"]))
        from lib.generation_job_mode import get_generation_job_status
        s = get_generation_job_status(r["job_id"])
        print(f"  Pages: {s.get('pages_success',0)}/{s.get('pages_total',0)}")

    # 4. Competitor mock
    from lib.competitor_analysis import analyze_competitors
    step("Competitor analysis", lambda: analyze_competitors("PU leather supplier", provider_name="mock", limit=3))

    # 5. Feedback
    from lib.beta_feedback import create_beta_feedback
    step("Create feedback", lambda: {"ok": True, "id": create_beta_feedback(ws["tenant_id"], rating=4, category="content_quality", message="Good B2B content!")})

    # 6. Beta report
    from lib.beta_report import generate_private_beta_report
    report = step("Generate beta report", lambda: generate_private_beta_report(ws["tenant_id"], ws["project_id"]))

    # Print summary
    print(f"\n=== Summary ===")
    m = report.get("metrics", {}) if report else {}
    j = m.get("jobs", {})
    pc = m.get("page_contents", {})
    gp = m.get("generated_pages", {})
    print(f"  Jobs: completed={j.get('completed',0)}/{j.get('total',0)}")
    print(f"  Pages from jobs: {j.get('pages_success_total', 0)}")
    print(f"  Generated pages (from result): {gp.get('from_job_results', 0)}")
    print(f"  Persisted page_contents: {pc.get('persisted', 0)}")
    if pc.get("persisted", 0) == 0:
        print(f"  NOTE: Mock mode does not persist page_contents by default.")
    print(f"  Feedback: {m.get('feedback', {}).get('count', 0)} items")
    print(f"\nOverall: {'PASS' if ok else 'FAIL'}")

if __name__ == "__main__": main()
