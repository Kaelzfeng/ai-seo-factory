# -*- coding: utf-8 -*-
"""轻量数据层(sqlite3 标准库,零 ORM)。

users / projects / generations / keywords / tenants / plans / subscriptions / usage_logs
+ Phase 1: sites / generation_logs / cms_logs
+ Phase 2: batch_runs / jobs / job_steps

参数化 SQL 防注入。
"""

import os
import sqlite3
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "app.db"

_local = threading.local()


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_db() -> sqlite3.Connection:
    """获得当前线程的数据库连接。自动建表。"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        _ensure_data_dir()
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        _create_tables(conn)
        _migrate_tables(conn)
        _seed_plans(conn)
    return conn


def init_db(db_path: str = None):
    """用指定路径初始化数据库（测试环境用）。返回连接。"""
    path = db_path or str(DB_PATH)
    if db_path:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    _migrate_tables(conn)
    _seed_plans(conn)
    return conn


def close_db():
    """关闭当前线程的数据库连接。"""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def _create_tables(conn):
    conn.executescript(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS tenant_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL DEFAULT 'owner',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER DEFAULT NULL REFERENCES tenants(id) ON DELETE SET NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        industry_config TEXT,
        industry TEXT DEFAULT '',
        language TEXT DEFAULT 'English',
        seed_keyword TEXT,
        site_url TEXT DEFAULT '',
        wp_url TEXT DEFAULT '',
        wp_username TEXT DEFAULT '',
        wp_app_password TEXT DEFAULT '',
        token_used INTEGER NOT NULL DEFAULT 0,
        token_limit INTEGER NOT NULL DEFAULT 100000,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER DEFAULT NULL REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        keyword TEXT DEFAULT '',
        page_type TEXT DEFAULT 'guide',
        status TEXT NOT NULL DEFAULT 'pending',
        title TEXT DEFAULT '',
        slug TEXT DEFAULT '',
        output_path TEXT DEFAULT '',
        quality_score REAL DEFAULT 0.0,
        token_count INTEGER NOT NULL DEFAULT 0,
        page_count INTEGER NOT NULL DEFAULT 0,
        passed_count INTEGER NOT NULL DEFAULT 0,
        tokens_used INTEGER NOT NULL DEFAULT 0,
        result_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER DEFAULT NULL REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        keyword TEXT DEFAULT '',
        intent TEXT NOT NULL DEFAULT 'other',
        priority INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT 'seed',
        support INTEGER NOT NULL DEFAULT 0,
        is_question INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        monthly_generation_limit INTEGER NOT NULL DEFAULT 3,
        monthly_token_limit INTEGER NOT NULL DEFAULT 100000,
        max_projects INTEGER NOT NULL DEFAULT 1,
        max_sites INTEGER NOT NULL DEFAULT 1,
        competitor_analysis_limit INTEGER NOT NULL DEFAULT 1,
        price_cents INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        plan_code TEXT NOT NULL DEFAULT 'free',
        status TEXT NOT NULL DEFAULT 'active',
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        expire_at TEXT DEFAULT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        user_id INTEGER DEFAULT NULL REFERENCES users(id) ON DELETE SET NULL,
        project_id INTEGER DEFAULT NULL REFERENCES projects(id) ON DELETE SET NULL,
        kind TEXT NOT NULL DEFAULT 'generation',
        amount INTEGER NOT NULL DEFAULT 1,
        meta_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
    CREATE INDEX IF NOT EXISTS idx_projects_tenant ON projects(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_generations_project ON generations(project_id);
    CREATE INDEX IF NOT EXISTS idx_generations_tenant ON generations(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_keywords_project ON keywords(project_id);
    CREATE INDEX IF NOT EXISTS idx_keywords_intent ON keywords(intent);
    CREATE INDEX IF NOT EXISTS idx_keywords_tenant ON keywords(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_tenant_members_user ON tenant_members(user_id);
    CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant ON tenant_members(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_usage_logs_tenant ON usage_logs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_usage_logs_created ON usage_logs(created_at);

    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        cms_type TEXT NOT NULL DEFAULT 'wordpress',
        site_url TEXT DEFAULT '',
        wp_url TEXT DEFAULT '',
        wp_username TEXT DEFAULT '',
        wp_app_password TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS generation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        generation_id INTEGER REFERENCES generations(id) ON DELETE CASCADE,
        step TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        message TEXT DEFAULT '',
        meta_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS cms_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        generation_id INTEGER REFERENCES generations(id) ON DELETE CASCADE,
        site_id INTEGER REFERENCES sites(id) ON DELETE SET NULL,
        cms_type TEXT NOT NULL DEFAULT 'wordpress',
        action TEXT NOT NULL DEFAULT 'publish',
        status TEXT NOT NULL DEFAULT 'pending',
        remote_id TEXT DEFAULT '',
        remote_url TEXT DEFAULT '',
        error TEXT DEFAULT '',
        meta_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_sites_tenant ON sites(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_sites_project ON sites(project_id);
    CREATE INDEX IF NOT EXISTS idx_generation_logs_gen ON generation_logs(generation_id);
    CREATE INDEX IF NOT EXISTS idx_generation_logs_tenant ON generation_logs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_cms_logs_gen ON cms_logs(generation_id);
    CREATE INDEX IF NOT EXISTS idx_cms_logs_site ON cms_logs(site_id);
    CREATE INDEX IF NOT EXISTS idx_cms_logs_tenant ON cms_logs(tenant_id);

    CREATE TABLE IF NOT EXISTS batch_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        source TEXT DEFAULT '',
        mode TEXT NOT NULL DEFAULT 'dry-run',
        status TEXT NOT NULL DEFAULT 'created',
        total_jobs INTEGER NOT NULL DEFAULT 0,
        success_jobs INTEGER NOT NULL DEFAULT 0,
        failed_jobs INTEGER NOT NULL DEFAULT 0,
        partial_jobs INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        started_at TEXT DEFAULT NULL,
        finished_at TEXT DEFAULT NULL,
        meta_json TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        batch_run_id INTEGER NOT NULL REFERENCES batch_runs(id) ON DELETE CASCADE,
        keyword TEXT NOT NULL DEFAULT '',
        industry_path TEXT DEFAULT '',
        mode TEXT NOT NULL DEFAULT 'dry-run',
        status TEXT NOT NULL DEFAULT 'pending',
        pages_total INTEGER NOT NULL DEFAULT 0,
        pages_success INTEGER NOT NULL DEFAULT 0,
        pages_failed INTEGER NOT NULL DEFAULT 0,
        generation_id INTEGER DEFAULT NULL,
        retryable INTEGER NOT NULL DEFAULT 0,
        error TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        started_at TEXT DEFAULT NULL,
        finished_at TEXT DEFAULT NULL,
        meta_json TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS job_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        step TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'started',
        message TEXT DEFAULT '',
        meta_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_batch_runs_tenant ON batch_runs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_batch_runs_status ON batch_runs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_jobs_batch ON jobs(batch_run_id);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_job_steps_job ON job_steps(job_id);
    CREATE INDEX IF NOT EXISTS idx_job_steps_tenant ON job_steps(tenant_id);

    CREATE TABLE IF NOT EXISTS business_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        profile_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS site_blueprints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        blueprint_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_bp_tenant ON business_profiles(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_bp_project ON business_profiles(project_id);
    CREATE INDEX IF NOT EXISTS idx_sbp_tenant ON site_blueprints(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_sbp_project ON site_blueprints(project_id);

    CREATE TABLE IF NOT EXISTS page_contents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        blueprint_id INTEGER REFERENCES site_blueprints(id) ON DELETE SET NULL,
        generation_id INTEGER REFERENCES generations(id) ON DELETE SET NULL,
        slug TEXT NOT NULL DEFAULT '',
        page_type TEXT NOT NULL DEFAULT 'article',
        title TEXT NOT NULL DEFAULT '',
        primary_keyword TEXT NOT NULL DEFAULT '',
        content_json TEXT DEFAULT '{}',
        gutenberg_html TEXT DEFAULT '',
        quality_score REAL DEFAULT 0.0,
        review_status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_pc_tenant ON page_contents(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_pc_project ON page_contents(project_id);
    CREATE INDEX IF NOT EXISTS idx_pc_blueprint ON page_contents(blueprint_id);
    CREATE INDEX IF NOT EXISTS idx_pc_slug ON page_contents(slug);
    """
    )


def _migrate_tables(conn):
    """向既有表安全追加 Phase 0 新列(幂等 —— 列已存在则跳过)。"""
    migrations = [
        # users: 确保有 password_salt
        ("users", "password_salt", "TEXT NOT NULL DEFAULT ''"),
        # projects: 添加 SaaS / 站点字段
        ("projects", "tenant_id", "INTEGER DEFAULT NULL REFERENCES tenants(id) ON DELETE SET NULL"),
        ("projects", "industry", "TEXT DEFAULT ''"),
        ("projects", "language", "TEXT DEFAULT 'English'"),
        ("projects", "site_url", "TEXT DEFAULT ''"),
        ("projects", "wp_url", "TEXT DEFAULT ''"),
        ("projects", "wp_username", "TEXT DEFAULT ''"),
        ("projects", "wp_app_password", "TEXT DEFAULT ''"),
        # generations: 添加 SaaS + 内容字段
        ("generations", "tenant_id", "INTEGER DEFAULT NULL REFERENCES tenants(id) ON DELETE SET NULL"),
        ("generations", "keyword", "TEXT DEFAULT ''"),
        ("generations", "page_type", "TEXT DEFAULT 'guide'"),
        ("generations", "title", "TEXT DEFAULT ''"),
        ("generations", "slug", "TEXT DEFAULT ''"),
        ("generations", "output_path", "TEXT DEFAULT ''"),
        ("generations", "quality_score", "REAL DEFAULT 0.0"),
        ("generations", "token_count", "INTEGER NOT NULL DEFAULT 0"),
        # keywords: 添加 SaaS + search 字段
        ("keywords", "tenant_id", "INTEGER DEFAULT NULL REFERENCES tenants(id) ON DELETE SET NULL"),
        ("keywords", "keyword", "TEXT DEFAULT ''"),
        ("keywords", "priority", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for table, col, typedef in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass  # 列已存在


def _seed_plans(conn):
    """确保默认套餐已存在。"""
    defaults = [
        ("free", "Free", 3, 100000, 1, 1, 1, 0),
    ]
    for row in defaults:
        code, name, gen_lim, tok_lim, max_proj, max_sites, comp_lim, price = row
        conn.execute(
            """INSERT OR IGNORE INTO plans
               (code, name, monthly_generation_limit, monthly_token_limit,
                max_projects, max_sites, competitor_analysis_limit, price_cents)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, name, gen_lim, tok_lim, max_proj, max_sites, comp_lim, price),
        )
    conn.commit()


# ── 用户 ────────────────────────────────────────────


def create_user(email: str, password_hash: str, password_salt: str = "") -> int:
    db = _get_db()
    db.execute(
        "INSERT INTO users (email, password_hash, password_salt) VALUES (?, ?, ?)",
        (email, password_hash, password_salt),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_user_by_email(email: str) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ── Tenant ──────────────────────────────────────────


def create_tenant(name: str) -> int:
    db = _get_db()
    db.execute("INSERT INTO tenants (name) VALUES (?)", (name,))
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_tenant(tenant_id: int) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    return dict(row) if row else None


def add_tenant_member(tenant_id: int, user_id: int, role: str = "owner") -> int:
    db = _get_db()
    db.execute(
        "INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (?, ?, ?)",
        (tenant_id, user_id, role),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_tenant_member(tenant_id: int, user_id: int) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT * FROM tenant_members WHERE tenant_id = ? AND user_id = ?",
        (tenant_id, user_id),
    ).fetchone()
    return dict(row) if row else None


# ── 套餐 ────────────────────────────────────────────


def get_plan(plan_code: str) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM plans WHERE code = ?", (plan_code,)).fetchone()
    return dict(row) if row else None


def list_plans() -> list[dict]:
    db = _get_db()
    rows = db.execute("SELECT * FROM plans ORDER BY price_cents ASC").fetchall()
    return [dict(r) for r in rows]


# ── 订阅 ────────────────────────────────────────────


def create_subscription(tenant_id: int, plan_code: str = "free",
                        status: str = "active", expire_at: str = None) -> int:
    db = _get_db()
    db.execute(
        "INSERT INTO subscriptions (tenant_id, plan_code, status, expire_at) VALUES (?, ?, ?, ?)",
        (tenant_id, plan_code, status, expire_at),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_active_subscription(tenant_id: int) -> dict | None:
    db = _get_db()
    row = db.execute(
        """SELECT s.*, p.name as plan_name, p.monthly_generation_limit,
                  p.monthly_token_limit, p.max_projects, p.max_sites,
                  p.competitor_analysis_limit, p.price_cents
           FROM subscriptions s
           JOIN plans p ON p.code = s.plan_code
           WHERE s.tenant_id = ? AND s.status = 'active'
           ORDER BY s.created_at DESC LIMIT 1""",
        (tenant_id,),
    ).fetchone()
    return dict(row) if row else None


def is_subscription_active(tenant_id: int) -> bool:
    sub = get_active_subscription(tenant_id)
    if not sub:
        return False
    if sub.get("expire_at"):
        if sub["expire_at"] < time.strftime("%Y-%m-%dT%H:%M:%S"):
            return False
    return True


# ── 用量日志 ────────────────────────────────────────


def record_usage(tenant_id: int, user_id: int = None, project_id: int = None,
                 kind: str = "generation", amount: int = 1,
                 meta_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO usage_logs (tenant_id, user_id, project_id, kind, amount, meta_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tenant_id, user_id, project_id, kind, amount, meta_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_monthly_usage(tenant_id: int, year_month: str = None) -> list[dict]:
    """按自然月统计。year_month 格式 'YYYY-MM',缺省取当前月。"""
    if year_month is None:
        year_month = time.strftime("%Y-%m")
    db = _get_db()
    rows = db.execute(
        """SELECT kind, SUM(amount) as total
           FROM usage_logs
           WHERE tenant_id = ? AND strftime('%Y-%m', created_at) = ?
           GROUP BY kind""",
        (tenant_id, year_month),
    ).fetchall()
    return [dict(r) for r in rows]


def get_usage_summary(tenant_id: int) -> dict:
    """返回当前月的用量摘要。"""
    monthly = get_monthly_usage(tenant_id)
    summary = {"generations": 0, "tokens": 0}
    for row in monthly:
        if row["kind"] == "generation":
            summary["generations"] = row["total"]
        elif row["kind"] == "token":
            summary["tokens"] = row["total"]
    # 同时获取本月总条数
    db = _get_db()
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM usage_logs WHERE tenant_id = ? AND strftime('%Y-%m', created_at) = ?",
        (tenant_id, time.strftime("%Y-%m")),
    ).fetchone()
    summary["total_logs"] = row["cnt"] if row else 0
    return summary


# ── 项目 ────────────────────────────────────────────


def create_project(user_id: int, name: str,
                   industry_config: str = None,
                   seed_keyword: str = None,
                   token_limit: int = 100000,
                   tenant_id: int = None,
                   industry: str = "",
                   language: str = "English",
                   site_url: str = "",
                   wp_url: str = "",
                   wp_username: str = "",
                   wp_app_password: str = "") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO projects
           (user_id, name, industry_config, seed_keyword, token_limit,
            tenant_id, industry, language, site_url, wp_url, wp_username, wp_app_password)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, industry_config, seed_keyword, token_limit,
         tenant_id, industry, language, site_url, wp_url, wp_username, wp_app_password),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_project(project_id: int) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def list_projects(user_id: int = None, tenant_id: int = None) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM projects WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
    elif user_id is not None:
        rows = db.execute(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def add_project_tokens(project_id: int, tokens: int):
    db = _get_db()
    db.execute(
        "UPDATE projects SET token_used = token_used + ? WHERE id = ?",
        (tokens, project_id),
    )
    db.commit()


def get_project_token_used(project_id: int) -> int:
    db = _get_db()
    row = db.execute("SELECT token_used FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row["token_used"] if row else 0


# ── 生成记录 ────────────────────────────────────────


def create_generation(project_id: int, status: str = "pending",
                      page_count: int = 0, passed_count: int = 0,
                      tokens_used: int = 0, result_json: str = None,
                      tenant_id: int = None, keyword: str = "",
                      page_type: str = "guide", title: str = "",
                      slug: str = "", output_path: str = "",
                      quality_score: float = 0.0, token_count: int = 0) -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO generations
           (project_id, status, page_count, passed_count, tokens_used, result_json,
            tenant_id, keyword, page_type, title, slug, output_path, quality_score, token_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, status, page_count, passed_count, tokens_used, result_json,
         tenant_id, keyword, page_type, title, slug, output_path, quality_score, token_count),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_generation(gen_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [gen_id]
    db = _get_db()
    db.execute(f"UPDATE generations SET {sets} WHERE id = ?", vals)
    db.commit()


def list_generations(project_id: int = None, tenant_id: int = None) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM generations WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
    elif project_id is not None:
        rows = db.execute(
            "SELECT * FROM generations WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM generations ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── 关键词 ────────────────────────────────────────────


def add_keywords(project_id: int, keywords: list[dict], tenant_id: int = None):
    """批量写入关键词。每个 kw dict 含 text, intent, source, support, is_question 等。"""
    db = _get_db()
    rows = [
        (project_id, kw["text"], kw.get("intent", "other"),
         kw.get("source", "seed"), kw.get("support", 0),
         int(kw.get("is_question", False)),
         tenant_id,
         kw.get("keyword", kw.get("text", "")),
         kw.get("priority", 0))
        for kw in keywords
    ]
    db.executemany(
        """INSERT INTO keywords
           (project_id, text, intent, source, support, is_question, tenant_id, keyword, priority)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    db.commit()


def list_keywords(project_id: int = None, tenant_id: int = None) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM keywords WHERE tenant_id = ? ORDER BY support DESC, intent",
            (tenant_id,),
        ).fetchall()
    elif project_id is not None:
        rows = db.execute(
            "SELECT * FROM keywords WHERE project_id = ? ORDER BY support DESC, intent",
            (project_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM keywords ORDER BY support DESC, intent").fetchall()
    return [dict(r) for r in rows]


def count_keywords(project_id: int) -> int:
    db = _get_db()
    row = db.execute(
        "SELECT COUNT(*) as n FROM keywords WHERE project_id = ?", (project_id,)
    ).fetchone()
    return row["n"] if row else 0


# ── 站点 ──────────────────────────────────────────────


def create_site(tenant_id: int, project_id: int, name: str,
                cms_type: str = "wordpress", site_url: str = "",
                wp_url: str = "", wp_username: str = "",
                wp_app_password: str = "", status: str = "active") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO sites (tenant_id, project_id, name, cms_type, site_url,
           wp_url, wp_username, wp_app_password, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, project_id, name, cms_type, site_url,
         wp_url, wp_username, wp_app_password, status),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_site(site_id: int) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
    return dict(row) if row else None


def list_sites(tenant_id: int = None, project_id: int = None) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM sites WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
    elif project_id is not None:
        rows = db.execute(
            "SELECT * FROM sites WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM sites ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def update_site(site_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [site_id]
    db = _get_db()
    db.execute(f"UPDATE sites SET {sets} WHERE id = ?", vals)
    db.commit()


# ── 生成步骤日志 ──────────────────────────────────────


def create_generation_log(tenant_id: int = None, project_id: int = None,
                          generation_id: int = None, step: str = "",
                          status: str = "running", message: str = "",
                          meta_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO generation_logs (tenant_id, project_id, generation_id, step,
           status, message, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, project_id, generation_id, step, status, message, meta_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_generation_log(log_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [log_id]
    db = _get_db()
    db.execute(f"UPDATE generation_logs SET {sets} WHERE id = ?", vals)
    db.commit()


def list_generation_logs(generation_id: int = None, tenant_id: int = None) -> list[dict]:
    db = _get_db()
    if generation_id is not None:
        rows = db.execute(
            """SELECT * FROM generation_logs WHERE generation_id = ?
               ORDER BY created_at ASC""",
            (generation_id,),
        ).fetchall()
    elif tenant_id is not None:
        rows = db.execute(
            """SELECT * FROM generation_logs WHERE tenant_id = ?
               ORDER BY created_at DESC""",
            (tenant_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM generation_logs ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── CMS 操作日志 ──────────────────────────────────────


def create_cms_log(tenant_id: int = None, project_id: int = None,
                   generation_id: int = None, site_id: int = None,
                   cms_type: str = "wordpress", action: str = "publish",
                   status: str = "pending", remote_id: str = "",
                   remote_url: str = "", error: str = "",
                   meta_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO cms_logs (tenant_id, project_id, generation_id, site_id,
           cms_type, action, status, remote_id, remote_url, error, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, project_id, generation_id, site_id, cms_type, action,
         status, remote_id, remote_url, error, meta_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_cms_logs(tenant_id: int = None, project_id: int = None,
                  generation_id: int = None, site_id: int = None,
                  limit: int = 100) -> list[dict]:
    db = _get_db()
    sql = "SELECT * FROM cms_logs WHERE 1=1"
    params = []
    if tenant_id is not None:
        sql += " AND tenant_id = ?"
        params.append(tenant_id)
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)
    if generation_id is not None:
        sql += " AND generation_id = ?"
        params.append(generation_id)
    if site_id is not None:
        sql += " AND site_id = ?"
        params.append(site_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ── 批量运行 ──────────────────────────────────────────


def create_batch_run(tenant_id: int, user_id: int = None,
                     project_id: int = None, name: str = "",
                     source: str = "", mode: str = "dry-run",
                     total_jobs: int = 0, meta_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO batch_runs (tenant_id, user_id, project_id, name, source, mode,
           total_jobs, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, user_id, project_id, name, source, mode, total_jobs, meta_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_batch_run(batch_run_id: int) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM batch_runs WHERE id = ?", (batch_run_id,)).fetchone()
    return dict(row) if row else None


def list_batch_runs(tenant_id: int = None, limit: int = 50) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM batch_runs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM batch_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_batch_run(batch_run_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [batch_run_id]
    db = _get_db()
    db.execute(f"UPDATE batch_runs SET {sets} WHERE id = ?", vals)
    db.commit()


# ── 任务 ──────────────────────────────────────────────


def create_job(tenant_id: int, batch_run_id: int, keyword: str = "",
               user_id: int = None, project_id: int = None,
               industry_path: str = "", mode: str = "dry-run",
               meta_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO jobs (tenant_id, user_id, project_id, batch_run_id, keyword,
           industry_path, mode, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, user_id, project_id, batch_run_id, keyword,
         industry_path, mode, meta_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_job(job_id: int) -> dict | None:
    db = _get_db()
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(batch_run_id: int = None, tenant_id: int = None,
              status: str = None) -> list[dict]:
    db = _get_db()
    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if batch_run_id is not None:
        sql += " AND batch_run_id = ?"
        params.append(batch_run_id)
    if tenant_id is not None:
        sql += " AND tenant_id = ?"
        params.append(tenant_id)
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id ASC"
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_job(job_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    db = _get_db()
    db.execute(f"UPDATE jobs SET {sets} WHERE id = ?", vals)
    db.commit()


# ── 任务步骤日志 ──────────────────────────────────────


def create_job_step(job_id: int, step: str = "", status: str = "started",
                    message: str = "", tenant_id: int = None,
                    meta_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO job_steps (tenant_id, job_id, step, status, message, meta_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tenant_id, job_id, step, status, message, meta_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_job_steps(job_id: int) -> list[dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT * FROM job_steps WHERE job_id = ? ORDER BY created_at ASC",
        (job_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── 生意画像 (Phase 3) ───────────────────────────────


def create_business_profile(tenant_id: int = None, project_id: int = None,
                            status: str = "draft",
                            profile_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO business_profiles (tenant_id, project_id, status, profile_json)
           VALUES (?, ?, ?, ?)""",
        (tenant_id, project_id, status, profile_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_business_profile(profile_id: int) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT * FROM business_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    return dict(row) if row else None


def list_business_profiles(tenant_id: int = None,
                           project_id: int = None) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM business_profiles WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
    elif project_id is not None:
        rows = db.execute(
            "SELECT * FROM business_profiles WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM business_profiles ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_business_profile_status(profile_id: int, status: str,
                                   profile_json: str = None):
    db = _get_db()
    if profile_json:
        db.execute(
            "UPDATE business_profiles SET status = ?, profile_json = ?, updated_at = datetime('now') WHERE id = ?",
            (status, profile_json, profile_id),
        )
    else:
        db.execute(
            "UPDATE business_profiles SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, profile_id),
        )
    db.commit()


# ── 站点蓝图 (Phase 3) ───────────────────────────────


def create_site_blueprint(tenant_id: int = None, project_id: int = None,
                          status: str = "draft",
                          blueprint_json: str = "{}") -> int:
    db = _get_db()
    db.execute(
        """INSERT INTO site_blueprints (tenant_id, project_id, status, blueprint_json)
           VALUES (?, ?, ?, ?)""",
        (tenant_id, project_id, status, blueprint_json),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_site_blueprint(blueprint_id: int) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT * FROM site_blueprints WHERE id = ?", (blueprint_id,)
    ).fetchone()
    return dict(row) if row else None


def list_site_blueprints(tenant_id: int = None,
                         project_id: int = None) -> list[dict]:
    db = _get_db()
    if tenant_id is not None:
        rows = db.execute(
            "SELECT * FROM site_blueprints WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
    elif project_id is not None:
        rows = db.execute(
            "SELECT * FROM site_blueprints WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM site_blueprints ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_site_blueprint_status(blueprint_id: int, status: str,
                                 blueprint_json: str = None):
    db = _get_db()
    if blueprint_json:
        db.execute(
            "UPDATE site_blueprints SET status = ?, blueprint_json = ?, updated_at = datetime('now') WHERE id = ?",
            (status, blueprint_json, blueprint_id),
        )
    else:
        db.execute(
            "UPDATE site_blueprints SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, blueprint_id),
        )
    db.commit()


# ── 页面内容 (Phase 4) ───────────────────────────────


def create_page_content(tenant_id=None, project_id=None, blueprint_id=None,
                        generation_id=None, slug="", page_type="article",
                        title="", primary_keyword="", content_json="{}",
                        gutenberg_html="", quality_score=0.0, review_status="pending"):
    db = _get_db()
    db.execute(
        """INSERT INTO page_contents (tenant_id, project_id, blueprint_id,
           generation_id, slug, page_type, title, primary_keyword,
           content_json, gutenberg_html, quality_score, review_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, project_id, blueprint_id, generation_id,
         slug, page_type, title, primary_keyword,
         content_json, gutenberg_html, quality_score, review_status),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_page_content(pc_id):
    db = _get_db()
    row = db.execute("SELECT * FROM page_contents WHERE id = ?", (pc_id,)).fetchone()
    return dict(row) if row else None


def list_page_contents(tenant_id=None, project_id=None, blueprint_id=None):
    db = _get_db()
    sql = "SELECT * FROM page_contents WHERE 1=1"
    params = []
    if tenant_id is not None:
        sql += " AND tenant_id = ?"
        params.append(tenant_id)
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)
    if blueprint_id is not None:
        sql += " AND blueprint_id = ?"
        params.append(blueprint_id)
    sql += " ORDER BY id ASC"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def update_page_content(pc_id, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [pc_id]
    db = _get_db()
    db.execute(f"UPDATE page_contents SET {sets}, updated_at = datetime('now') WHERE id = ?", vals)
    db.commit()


def update_page_content_review_status(pc_id, review_status, quality_score=None):
    db = _get_db()
    if quality_score is not None:
        db.execute(
            "UPDATE page_contents SET review_status = ?, quality_score = ?, updated_at = datetime('now') WHERE id = ?",
            (review_status, quality_score, pc_id),
        )
    else:
        db.execute(
            "UPDATE page_contents SET review_status = ?, updated_at = datetime('now') WHERE id = ?",
            (review_status, pc_id),
        )
    db.commit()
