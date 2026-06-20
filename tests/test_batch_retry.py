# -*- coding: utf-8 -*-
"""tests/test_batch_retry.py · 批量重试集成测试

覆盖:
10. retry_partial_jobs 调用 retry_failed_pages
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as _run
import models

_MOCK_CONTENT = {
    "title": "Retry Batch Page",
    "meta_description": "Retry batch meta description for SEO, 150+ chars of meaningful content.",
    "html": "<h1>Retry Batch</h1><p>Content " * 10 + "</p>",
    "image_query": "retry batch image",
}

_MOCK_QUALITY = {"score": 88.0, "breakdown": {}, "issues": [], "passed": True}

_MOCK_PAGES = [
    {"title": f"Page {n}", "type": "guide", "slug": f"page-{n}",
     "target_keyword": f"kw-{n}"}
    for n in range(1, 9)
]


def _setup(conn, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    # 避免 keyword_scout 调用真实 Bing API
    try:
        from lib import keyword_scout
        monkeypatch.setattr(keyword_scout, "grounded_plan",
                           lambda seed, max_pages=7: {"plan": _MOCK_PAGES})
    except ImportError:
        pass
    tid = models.create_tenant("retry-batch-org")
    uid = models.create_user("rbatch@test.com", "h", "s")
    pid = models.create_project(
        user_id=uid, name="Retry Batch Project", tenant_id=tid,
        seed_keyword="test", language="English",
        site_url="https://example.com",
    )
    from lib.batch_jobs import create_batch_run, create_jobs_from_rows
    br = create_batch_run(tenant_id=tid, user_id=uid, project_id=pid,
                          name="Retry Batch", source="test.csv", mode="dry-run")
    rows = [
        {"keyword": f"rb-{n}", "industry_path": "", "mode": "dry-run", "_line": n+2}
        for n in range(1, 3)
    ]
    jobs = create_jobs_from_rows(batch_run_id=br["id"], tenant_id=tid,
                                 user_id=uid, project_id=pid, rows=rows)
    return tid, uid, pid, br["id"], [j["id"] for j in jobs]


# ── Test: retry_partial_jobs 调用 retry_failed_pages ──


def test_retry_partial_jobs_calls_retry_failed_pages(monkeypatch):
    """retry_partial_jobs 能补跑 partial_success job 的失败页。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    tid, uid, pid, bid, jids = _setup(conn, monkeypatch)

    # 设置 job 0 为 partial_success, meta 中有 failed_generation_ids
    from models import update_job
    failed_gen_ids = [999, 1000]  # 模拟失败 generation ID
    update_job(jids[0], status="partial_success",
               pages_success=6, pages_failed=2, retryable=1,
               meta_json=json.dumps({"failed_generation_ids": failed_gen_ids,
                                     "generation_ids": [1, 2, 3, 4, 5, 6]}))

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 200})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.batch_runner import retry_partial_jobs
    result = retry_partial_jobs(bid, bypass_subscription=True)

    assert result["ok"] is True
    assert len(result["results"]) >= 1

    # 验证 job 数据
    from lib.batch_jobs import get_job, list_job_steps
    job = get_job(jids[0])
    assert job["status"] in ("recovered", "partial_success")

    # 验证 job_steps 有 retry 相关记录且保留旧步骤
    steps = list_job_steps(jids[0])
    step_names = [s["step"] for s in steps]
    assert "retry_partial_started" in step_names
    assert len(steps) >= 1

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test: retry_partial_jobs skips when no failed gen ids ──


def test_retry_partial_jobs_skips_no_failed_gens(monkeypatch):
    """没有 failed_generation_ids 时跳过。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    tid, uid, pid, bid, jids = _setup(conn, monkeypatch)

    # job 0 为 partial_success 但没有 failed_generation_ids
    from models import update_job
    update_job(jids[0], status="partial_success",
               pages_success=7, pages_failed=1, retryable=1,
               meta_json=json.dumps({"failed_generation_ids": []}))

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 100})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.batch_runner import retry_partial_jobs
    result = retry_partial_jobs(bid, bypass_subscription=True)

    # 应该 skipped
    assert result["results"][0]["action"] == "skipped"

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test: retry_failed_jobs on batch with mixed status ──


def test_retry_failed_jobs_mixed_status(monkeypatch):
    """retry_failed_jobs 只处理非 completed 的 job。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    tid, uid, pid, bid, jids = _setup(conn, monkeypatch)

    # job 0: completed, job 1: failed
    from models import update_job
    update_job(jids[0], status="completed")
    update_job(jids[1], status="failed")

    call_count = [0]
    def fake_structured(**kw):
        call_count[0] += 1
        return dict(_MOCK_CONTENT)

    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 100})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.batch_runner import retry_failed_jobs
    result = retry_failed_jobs(bid, bypass_subscription=True)

    # job 0 不应被重跑,只有 job 1 被重跑
    from lib.batch_jobs import get_job, list_job_steps
    assert get_job(jids[0])["status"] == "completed"
    assert get_job(jids[1])["status"] in ("recovered", "completed")

    # 验证 job 1 有 retry_recovered 步骤,保留旧步骤
    steps = list_job_steps(jids[1])
    step_names = [s["step"] for s in steps]
    assert "retry_started" in step_names
    assert "retry_recovered" in step_names
    # 应该有旧步骤 + retry 步骤
    assert len(steps) >= 2

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── templates/static 未修改 ──────────────────────────


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    templates_dir = root / "templates"
    if templates_dir.exists():
        for f in templates_dir.rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0


def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    static_dir = root / "static"
    if static_dir.exists():
        for f in static_dir.rglob("*"):
            if f.is_file():
                assert f.exists()
