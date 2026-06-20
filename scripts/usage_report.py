#!/usr/bin/env python
"""scripts/usage_report.py · Phase 7: 用量报告 CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(); p.add_argument("--tenant-id", type=int, default=1); p.add_argument("--month", default="")
    args = p.parse_args()
    from lib.entitlements import get_tenant_entitlements
    ent = get_tenant_entitlements(args.tenant_id)
    print(f"Plan: {ent['plan_name']} ({ent['plan_code']})")
    print(f"Subscription: {ent['subscription_status']}")
    print("Limits:")
    for k, v in ent["limits"].items():
        u = ent["usage"].get(k, 0)
        r = max(0, v - u)
        warn = " *** EXCEEDED" if u >= v else ""
        print(f"  {k}: {u}/{v} (remaining: {r}){warn}")

if __name__ == "__main__": main()
