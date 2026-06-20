# -*- coding: utf-8 -*-
"""tests/test_generation_logs.py · 生成步骤日志测试

覆盖:
3. generation_logs 能记录步骤
4. 页面失败时写入 failed log
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models


# ── Fixture ─────────────────────────────────────────


@pytest.fixture()
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    yield conn
    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def _setup(conn, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    tid = models.create_tenant("test-org")
    uid = models.create_user("test@example.com", "hash", "salt")
    pid = models.create_project(
        user_id=uid, name="test-project",
        tenant_id=tid, seed_keyword="test",
    )
    gen_id = models.create_generation(
        project_id=pid, tenant_id=tid, keyword="test-kw",
        page_type="guide", title="Test", slug="test-page", status="running",
    )
    return tid, uid, pid, gen_id


# ── Test: 能记录步骤 ────────────────────────────────


def test_log_generation_step(db, monkeypatch):
    tid, uid, pid, gen_id = _setup(db, monkeypatch)

    from lib.generation_logs import log_generation_step
    log_id = log_generation_step(
        tenant_id=tid, project_id=pid,
        generation_id=gen_id, step="llm_generate",
        status="success", message="LLM 生成完成",
        meta={"tokens": 500},
    )
    assert log_id is not None
    assert log_id > 0

    # 验证记录
    logs = models.list_generation_logs(generation_id=gen_id)
    assert len(logs) >= 1
    log = logs[0]
    assert log["step"] == "llm_generate"
    assert log["status"] == "success"
    assert log["message"] == "LLM 生成完成"
    assert "tokens" in log["meta_json"]


# ── Test: 能记录多个步骤 ─────────────────────────────


def test_log_multiple_steps(db, monkeypatch):
    tid, uid, pid, gen_id = _setup(db, monkeypatch)

    from lib.generation_logs import log_generation_step

    log_generation_step(tenant_id=tid, project_id=pid,
                        generation_id=gen_id, step="llm_generate",
                        status="success", message="step 1")
    log_generation_step(tenant_id=tid, project_id=pid,
                        generation_id=gen_id, step="quality_score",
                        status="success", message="step 2")
    log_generation_step(tenant_id=tid, project_id=pid,
                        generation_id=gen_id, step="polish",
                        status="success", message="step 3")

    from lib.generation_logs import list_generation_logs
    logs = list_generation_logs(generation_id=gen_id)
    assert len(logs) == 3
    steps = [l["step"] for l in logs]
    assert steps == ["llm_generate", "quality_score", "polish"]


# ── Test: 页面失败时写入 failed log ──────────────────


def test_mark_generation_failed(db, monkeypatch):
    tid, uid, pid, gen_id = _setup(db, monkeypatch)

    from lib.generation_logs import mark_generation_failed

    mark_generation_failed(
        generation_id=gen_id,
        step="llm_generate",
        reason="LLM 返回空响应",
        meta={"attempt": 3},
    )

    logs = models.list_generation_logs(generation_id=gen_id)
    assert len(logs) >= 1
    failed_log = [l for l in logs if l["status"] == "failed"]
    assert len(failed_log) >= 1
    assert failed_log[0]["step"] == "llm_generate"
    assert "LLM 返回空响应" in failed_log[0]["message"]


# ── Test: mark_generation_failed 更新 generations 状态 ──


def test_mark_generation_failed_updates_status(db, monkeypatch):
    tid, uid, pid, gen_id = _setup(db, monkeypatch)
    # 确认初始状态
    gen = models.list_generations(project_id=pid)[0]
    assert gen["status"] == "running"

    from lib.generation_logs import mark_generation_failed
    mark_generation_failed(gen_id, step="render", reason="渲染失败")

    gen = models.list_generations(project_id=pid)[0]
    assert gen["status"] == "failed"


# ── Test: mark_generation_success ────────────────────


def test_mark_generation_success(db, monkeypatch):
    tid, uid, pid, gen_id = _setup(db, monkeypatch)

    from lib.generation_logs import mark_generation_success
    mark_generation_success(gen_id, meta={"final_score": 85})

    logs = models.list_generation_logs(generation_id=gen_id)
    assert len(logs) >= 1
    success_logs = [l for l in logs if l["step"] == "complete" and l["status"] == "success"]
    assert len(success_logs) >= 1

    gen = models.list_generations(project_id=pid)[0]
    assert gen["status"] == "completed"


# ── Test: generation_id=None 不抛异常 ────────────────


def test_log_with_none_generation_id(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    from lib.generation_logs import mark_generation_failed, mark_generation_success, log_generation_step

    # 这些调用不应抛异常
    mark_generation_failed(None, step="test", reason="test")
    mark_generation_success(None)
    log_id = log_generation_step(generation_id=None, step="orphan", status="success")
    # log_generation_step 仍然创建了记录(generation_id 可以为 NULL)
    assert log_id > 0
