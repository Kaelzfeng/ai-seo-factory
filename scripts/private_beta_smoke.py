#!/usr/bin/env python
"""scripts/private_beta_smoke.py · Phase 9: Beta 烟测"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    ok = True
    checks = [
        ("health", lambda: __import__("lib.health", fromlist=["h"]).health_check()),
        ("ready", lambda: __import__("lib.health", fromlist=["h"]).readiness_check()),
        ("config", lambda: __import__("lib.config_check", fromlist=["c"]).get_config_report()),
        ("plans", lambda: __import__("lib.plan_catalog", fromlist=["p"]).list_public_plans()),
        ("competitor", lambda: __import__("lib.competitor_analysis", fromlist=["c"]).analyze_competitors("test","mock",limit=3)),
        ("routes", lambda: __import__("lib.api_contract", fromlist=["a"]).collect_routes(__import__("app", fromlist=["a"]).app)),
    ]
    for name, fn in checks:
        try:
            r = fn()
            if isinstance(r, dict) and r.get("ok") is False:
                print(f"[FAIL] {name}")
                ok = False
            else:
                print(f"[OK] {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            ok = False
    print(f"\nOverall: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
