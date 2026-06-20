#!/usr/bin/env python
"""scripts/create_demo_user.py · Phase 9: 创建 Demo 用户"""
import argparse, os, secrets, sys, string
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", default="demo@example.com")
    p.add_argument("--print-password", action="store_true")
    args = p.parse_args()

    import models, auth as _auth

    # Check if user exists
    existing = models.get_user_by_email(args.email)
    if existing:
        print(f"[SKIP] User already exists: {args.email} (id={existing['id']})")
        members = models._get_db().execute("SELECT tenant_id FROM tenant_members WHERE user_id=?", (existing["id"],)).fetchone()
        tid = members["tenant_id"] if members else None
        print(f"  tenant_id: {tid}")
        return

    # Generate password
    pwd = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(12)
    h, s = _auth.hash_password(pwd)
    uid = models.create_user(args.email, h, s)

    # Create tenant + subscription
    tid = models.create_tenant("demo-org")
    models.add_tenant_member(tid, uid, "owner")
    models.create_subscription(tid, plan_code="free", status="active")
    models.create_project(user_id=uid, name="Demo Project", tenant_id=tid, seed_keyword="PU leather", language="English", site_url="https://example.com")

    print(f"[OK] Demo user created")
    print(f"  email: {args.email}")
    print(f"  tenant_id: {tid}")
    if args.print_password:
        print(f"  password: {pwd}")
    else:
        print(f"  password: (hidden, set DEMO_PASSWORD or use --print-password)")
    print(f"\nNext:")
    print(f"  python scripts/usage_report.py --tenant-id {tid}")

if __name__ == "__main__": main()
