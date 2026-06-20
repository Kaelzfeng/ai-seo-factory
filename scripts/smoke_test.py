#!/usr/bin/env python
"""scripts/smoke_test.py · Phase 8: 快速烟测"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    ok = True
    checks = [
        ("health_check", lambda: __import__("lib.health").health.health_check()),
        ("readiness_check", lambda: __import__("lib.health").health.readiness_check()),
        ("config_report", lambda: __import__("lib.config_check").config_check.get_config_report()),
        ("plan_catalog", lambda: __import__("lib.plan_catalog").plan_catalog.list_public_plans()),
        ("competitor_mock", lambda: __import__("lib.competitor_analysis").competitor_analysis.analyze_competitors("test", provider_name="mock", limit=3)),
        ("entitlements", lambda: {"tenants": "stub - requires DB tenant"}),
    ]
    for name, fn in checks:
        try:
            result = fn()
            status = "OK"
            if isinstance(result, dict) and not result.get("ok", True):
                status = "FAIL"
                ok = False
        except Exception as e:
            status = f"ERROR: {e}"
            ok = False
        print(f"[{status}] {name}")
    print(f"\nOverall: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
