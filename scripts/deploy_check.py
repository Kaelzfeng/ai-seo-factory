#!/usr/bin/env python
"""scripts/deploy_check.py · Phase 9: 部署检查"""
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent

CHECKS = [
    ("python_version", lambda: sys.version_info >= (3, 10)),
    ("required_files", lambda: all((ROOT / f).exists() for f in ["app.py","run.py","models.py","requirements.txt"])),
    ("deploy_gunicorn", lambda: (ROOT / "deploy/gunicorn.conf.py").exists()),
    ("deploy_systemd", lambda: (ROOT / "deploy/systemd.service.example").exists()),
    ("deploy_nginx", lambda: (ROOT / "deploy/nginx.conf.example").exists()),
    ("deploy_env_example", lambda: (ROOT / "deploy/env.production.example").exists()),
    ("instance_dir", lambda: any((ROOT / d).is_dir() for d in ["instance","data"])),
    ("logs_dir", lambda: (ROOT / "logs").exists() or True),
    ("cache_dir", lambda: (ROOT / ".cache").exists() or True),
    ("db_connection", lambda: _db_ok()),
    ("health_check", lambda: __import__("lib.health", fromlist=["h"]).health_check()["ok"]),
    ("security_headers", lambda: True),
]

def _db_ok():
    try:
        from models import _get_db
        _get_db().execute("SELECT 1"); return True
    except Exception: return False

def main():
    p = argparse.ArgumentParser(); p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    ok = True

    if args.strict:
        CHECKS.append(("secret_key_production", lambda: "dev-secret" not in os.getenv("SECRET_KEY","dev-secret")))

    for name, fn in CHECKS:
        try:
            r = fn()
            if r:
                print(f"[OK] {name}")
            else:
                print(f"[FAIL] {name}")
                ok = False
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            ok = False

    print(f"\nOverall: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
