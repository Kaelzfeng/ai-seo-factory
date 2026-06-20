# -*- coding: utf-8 -*-
"""lib/demo_data.py · Phase 9.3: Demo 数据初始化 (幂等)"""
import secrets, os
from lib.plan_catalog import seed_default_plans

def ensure_demo_tenant(name="demo-org"):
    from models import _get_db, create_tenant
    db = _get_db()
    row = db.execute("SELECT id FROM tenants WHERE name=? LIMIT 1", (name,)).fetchone()
    if row: return row["id"]
    return create_tenant(name)

def ensure_demo_user(email="demo@example.com", password=None):
    from models import _get_db, get_user_by_email, create_user
    existing = get_user_by_email(email)
    if existing: return existing["id"]
    pwd = password or os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(12)
    import auth
    h, s = auth.hash_password(pwd)
    uid = create_user(email, h, s)
    return uid

def ensure_demo_project(tenant_id, user_id=None, name="PU Leather B2B Export Site"):
    from models import _get_db, create_project, list_projects
    projs = list_projects(tenant_id=tenant_id)
    if projs: return projs[0]["id"]
    return create_project(user_id=user_id or 1, name=name, tenant_id=tenant_id,
                          seed_keyword="PU leather", industry="PU Leather",
                          language="English", site_url="https://example.com",
                          industry_config="industries/pu-leather.yaml")

def ensure_demo_site(project_id, tenant_id):
    from models import list_sites, create_site
    sites = list_sites(tenant_id=tenant_id)
    if sites: return sites[0]["id"]
    return create_site(tenant_id=tenant_id, project_id=project_id, name="Demo WP",
                       cms_type="wordpress", site_url="https://demo.example.com",
                       wp_url="https://demo.example.com/wp-json",
                       wp_username="admin", wp_app_password="demo-pass",
                       status="active")

def ensure_demo_plan(tenant_id, plan_code="starter"):
    from lib.admin_ops import change_tenant_plan
    return change_tenant_plan(tenant_id, plan_code, mock_payment=True)

def bootstrap_demo_workspace(email="demo@example.com", plan_code="starter"):
    seed_default_plans()
    tid = ensure_demo_tenant()
    uid = ensure_demo_user(email)
    from models import add_tenant_member, get_tenant_member
    if not get_tenant_member(tid, uid):
        add_tenant_member(tid, uid, "owner")
    pid = ensure_demo_project(tid, uid)
    sid = ensure_demo_site(pid, tid)
    ensure_demo_plan(tid, plan_code)
    return {"tenant_id": tid, "user_id": uid, "project_id": pid, "site_id": sid}
