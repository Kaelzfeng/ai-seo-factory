#!/usr/bin/env python
"""scripts/release_check.py · Phase 8: 上线检查"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(); p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    from lib.release_checks import run_release_checks
    result = run_release_checks(args.strict)
    print(f"Overall: {'PASS' if result['ok'] else 'FAIL'}")
    for name, check in result["checks"].items():
        ck_ok = check if isinstance(check, bool) else check.get("ok", True)
        flag = "OK" if ck_ok else "FAIL"
        print(f"  [{flag}] {name}")
    sys.exit(0 if result["ok"] else 1)

if __name__ == "__main__": main()
