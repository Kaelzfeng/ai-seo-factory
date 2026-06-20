#!/usr/bin/env python
"""scripts/change_plan.py · Phase 7: 变更套餐 CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(); p.add_argument("--tenant-id", type=int, required=True); p.add_argument("--plan", required=True, choices=["free","starter","pro","agency"])
    args = p.parse_args()
    from lib.admin_ops import change_tenant_plan
    r = change_tenant_plan(args.tenant_id, args.plan, mock_payment=True)
    print(f"ok={r['ok']} old={r.get('old_plan')} new={r.get('new_plan')} price={r.get('price_cents')}")

if __name__ == "__main__": main()
