#!/usr/bin/env python
"""scripts/dev_bootstrap.py · Phase 8: 本地初始化"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    print("=== AI SEO Content Factory Dev Bootstrap ===\n")
    done = []
    # 1. DB init
    try:
        from models import init_db, _get_db, create_tenant, create_user, add_tenant_member, create_subscription, create_project
        db = _get_db()
        print("[OK] Database initialized")
        done.append("database")
    except Exception as e:
        print(f"[FAIL] Database: {e}"); return

    # 2. Seed plans
    try:
        from lib.plan_catalog import seed_default_plans
        seed_default_plans()
        print("[OK] Plans seeded")
    except Exception as e:
        print(f"[WARN] Plans: {e}")

    # 3. Demo tenant (if none exist)
    try:
        rows = db.execute("SELECT COUNT(*) as n FROM tenants").fetchone()
        if rows["n"] == 0:
            tid = create_tenant("demo-org")
            uid = create_user("demo@example.com", "pbkdf2:sha256:demo", "demo")
            add_tenant_member(tid, uid, "owner")
            create_subscription(tid, "free", "active")
            create_project(user_id=uid, name="Demo Project", tenant_id=tid, seed_keyword="PU leather", language="English")
            print(f"[OK] Demo tenant created (id={tid})")
        else:
            print(f"[OK] {rows['n']} tenants exist, skip demo creation")
    except Exception as e:
        print(f"[WARN] Demo tenant: {e}")

    print("\n=== Next Steps ===")
    print("python run.py industries/pu-leather.yaml --dry-run")
    print("python -m pytest tests/ -v")
    print("python app.py")

if __name__ == "__main__": main()
