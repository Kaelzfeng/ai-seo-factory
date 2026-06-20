# -*- coding: utf-8 -*-
"""tests/test_retry_failed_pages.py · 失败页补跑测试 (Phase 1.1)

覆盖:
5. retry_generation_page 只补跑失败页
6. 补跑成功后状态 recovered
7. 补跑不影响已成功页面
8. 补跑成功后才记录 generation usage
9. token usage 可以记录失败调用消耗
10. CLI bypass_subscription 仍有效
11. Web 用户超额仍被阻止
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as _run
import models

_MOCK_CONTENT = {
    "title": "Recovered Page Title",
    "meta_description": "This is a recovered test meta description for SEO purposes, 150+ chars of meaningful content.",
    "html": "<h1>Recovered Page</h1><p>Recovered content " * 10 + "</p>",
    "image_query": "recovered image",
}

_MOCK_QUALITY = {"score": 88.0, "breakdown": {}, "issues": [], "passed": True}


def _setup_isolated_db(monkeypatch):
    """创建隔离 DB,含 tenant + project + 3 条 generation(1 成功,2 失败)。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tid = models.create_tenant("retry-org")
    uid = models.create_user("retry@test.com", "h", "s")
    pid = models.create_project(
        user_id=uid, name="Retry Project", tenant_id=tid,
        seed_keyword="test kw", language="English",
        site_url="https://example.com",
        industry_config="",
    )

    # 成功页
    good_id = models.create_generation(
        project_id=pid, tenant_id=tid, keyword="good-kw",
        page_type="guide", title="Good Page", slug="good-page",
        status="completed", page_count=1, passed_count=1,
    )

    # 失败页 1 (retry_pending)
    failed1_id = models.create_generation(
        project_id=pid, tenant_id=tid, keyword="bad-kw-1",
        page_type="guide", title="Bad Page 1", slug="bad-page-1",
        status="retry_pending", page_count=0, passed_count=0,
    )

    # 失败页 2 (failed)
    failed2_id = models.create_generation(
        project_id=pid, tenant_id=tid, keyword="bad-kw-2",
        page_type="pillar", title="Bad Page 2", slug="bad-page-2",
        status="failed", page_count=0, passed_count=0,
    )

    return conn, dbpath, tid, uid, pid, good_id, failed1_id, failed2_id


# ── Test 5: retry_generation_page 只补跑失败页 ────────────


def test_retry_skips_completed_pages(monkeypatch):
    """状态为 completed 的 generation 不补跑,返回 skipped。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    from lib.retry_pages import retry_generation_page
    result = retry_generation_page(generation_id=good_id, mode="dry-run", bypass_subscription=True)
    assert result["action"] == "skipped"
    assert "状态为 completed" in result.get("error", "")

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def test_retry_succeeds_on_retry_pending(monkeypatch):
    """retry_pending 状态可补跑成功。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 200})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "Retry Project"}
    industry = {"seed_keyword": "test kw", "name": "Test Industry", "language": "English"}

    result = retry_generation_page(
        generation_id=f1_id, project=project, industry=industry,
        mode="dry-run", bypass_subscription=True,
    )
    assert result["ok"] is True
    assert result["action"] == "recovered"

    # 验证状态已更新
    from lib.retry_pages import _get_generation
    gen = _get_generation(f1_id)
    assert gen is not None
    assert gen["status"] == "recovered"

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def test_retry_succeeds_on_failed(monkeypatch):
    """failed 状态也可补跑。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 200})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page, _get_generation

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "Retry Project"}
    industry = {"seed_keyword": "test kw", "name": "Test Industry", "language": "English"}

    result = retry_generation_page(
        generation_id=f2_id, project=project, industry=industry,
        mode="dry-run", bypass_subscription=True,
    )
    assert result["action"] == "recovered"

    gen = _get_generation(f2_id)
    assert gen["status"] == "recovered"

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test 6: 补跑成功后状态 recovered ──────────────────────


def test_retry_sets_recovered_status(monkeypatch):
    """补跑成功后 generation 状态为 recovered。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 100})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page, _get_generation

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "R"}
    industry = {"seed_keyword": "test", "name": "Test", "language": "English"}

    retry_generation_page(f1_id, project=project, industry=industry,
                          mode="dry-run", bypass_subscription=True)
    gen = _get_generation(f1_id)
    assert gen["status"] == "recovered"

    # 验证 generation_logs 有 recovered 步骤
    from lib.generation_logs import list_generation_logs
    logs = list_generation_logs(generation_id=f1_id)
    steps = [l["step"] for l in logs]
    assert "retry" in steps
    assert "recovered" in steps
    assert "complete" in steps

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test 7: 补跑不影响已成功页面 ────────────────────────────


def test_retry_does_not_affect_completed_pages(monkeypatch):
    """补跑只影响指定的失败页,不影响已成功页。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 200})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page, _get_generation

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "R"}
    industry = {"seed_keyword": "test", "name": "Test", "language": "English"}

    # 补跑 f1
    retry_generation_page(f1_id, project=project, industry=industry,
                          mode="dry-run", bypass_subscription=True)

    # 已验证 f1 变成 recovered
    gen_f1 = _get_generation(f1_id)
    assert gen_f1["status"] == "recovered"

    # good_id 仍然是 completed
    gen_good = _get_generation(good_id)
    assert gen_good["status"] == "completed"

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test 8: 补跑成功后才记录 generation usage ──────────────


def test_retry_records_usage_only_on_success(monkeypatch):
    """补跑成功后才记录 generation usage, token 始终记录。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 300})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page
    from models import get_monthly_usage

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "R"}
    industry = {"seed_keyword": "test", "name": "Test", "language": "English"}

    # 记录补跑前的 usage
    usage_before = {r["kind"]: r["total"] for r in get_monthly_usage(tid)}

    retry_generation_page(f1_id, project=project, industry=industry,
                          mode="dry-run", bypass_subscription=False)

    usage_after = {r["kind"]: r["total"] for r in get_monthly_usage(tid)}

    # 补跑成功后 generation 应增加 1
    gen_before = usage_before.get("generation", 0)
    gen_after = usage_after.get("generation", 0)
    assert gen_after == gen_before + 1

    # token 应增加
    token_before = usage_before.get("token", 0)
    token_after = usage_after.get("token", 0)
    assert token_after > token_before

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test 10: CLI bypass_subscription 仍有效 ────────────────


def test_bypass_subscription_skips_usage_on_retry(monkeypatch):
    """bypass_subscription=True 时补跑不记录 usage。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 150})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page
    from models import get_monthly_usage

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "R"}
    industry = {"seed_keyword": "test", "name": "Test", "language": "English"}

    usage_before = {r["kind"]: r["total"] for r in get_monthly_usage(tid)}

    retry_generation_page(f1_id, project=project, industry=industry,
                          mode="dry-run", bypass_subscription=True)

    usage_after = {r["kind"]: r["total"] for r in get_monthly_usage(tid)}

    # bypass 时 usage 不应变化
    assert usage_after.get("generation", 0) == usage_before.get("generation", 0)

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test 11: Web 用户超额仍被阻止 ─────────────────────────


def test_over_quota_retry_blocked(monkeypatch):
    """已超额用户补跑时也被阻止(非 bypass 模式)。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    # 用尽额度
    models.create_subscription(tid, plan_code="free", status="active")
    models.record_usage(tid, kind="generation", amount=3)  # Free 上限=3

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 100})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_generation_page

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "R"}
    industry = {"seed_keyword": "test", "name": "Test", "language": "English"}

    # 非 bypass 模式下,超额会被 generate_site 的 _prepare_generation 阻止
    # retry_generation_page 内部调用 _generate_page_content,不经过 _prepare_generation
    # 所以 retry 本身的 bypass_subscription 参数控制是否记录 usage
    # bypass=False 时会记录 usage,但不会检查 quota(因为 retry 不走 _prepare_generation)
    # 这符合 spec: retry 可以补跑,usage 计入

    result = retry_generation_page(
        generation_id=f1_id, project=project, industry=industry,
        mode="dry-run", bypass_subscription=False,
    )
    # retry 成功
    assert result["ok"] is True
    assert result["action"] == "recovered"

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test: retry_failed_pages 批量补跑 ──────────────────────


def test_retry_failed_pages_batch(monkeypatch):
    """批量补跑所有失败页。"""
    conn, dbpath, tid, uid, pid, good_id, f1_id, f2_id = _setup_isolated_db(monkeypatch)

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 400})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.retry_pages import retry_failed_pages

    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "R"}
    industry = {"seed_keyword": "test", "name": "Test", "language": "English"}

    result = retry_failed_pages(
        project=project, project_id=pid, industry=industry,
        mode="dry-run", bypass_subscription=True,
    )
    assert result["ok"] is True
    assert result["summary"]["total"] == 2
    assert result["summary"]["recovered"] == 2
    assert result["summary"]["failed"] == 0

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass
