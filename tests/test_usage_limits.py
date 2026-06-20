# -*- coding: utf-8 -*-
"""tests/test_usage_limits.py · 用量记录与额度边界测试"""

import os
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models
from lib.usage import record_usage, get_monthly_usage, get_usage_summary


import pytest


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(path)
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    yield
    conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


def test_record_generation_usage():
    """记录一次生成用量后在 monthly 中可见。"""
    tid = models.create_tenant("usage-co")
    record_usage(tid, kind="generation", amount=1)
    monthly = get_monthly_usage(tid)
    assert monthly.get("generation") == 1


def test_record_token_usage():
    """记录 token 用量。"""
    tid = models.create_tenant("token-co")
    record_usage(tid, kind="token", amount=15000)
    monthly = get_monthly_usage(tid)
    assert monthly.get("token") == 15000


def test_multiple_usage_aggregates():
    """多次记录同类用量会累加。"""
    tid = models.create_tenant("agg-co")
    record_usage(tid, kind="generation", amount=1)
    record_usage(tid, kind="generation", amount=2)
    monthly = get_monthly_usage(tid)
    assert monthly.get("generation") == 3


def test_record_usage_with_meta():
    """meta 信息能正确存储为 JSON。"""
    tid = models.create_tenant("meta-co")
    meta = {"page_slugs": ["page-a", "page-b"], "model": "deepseek-v4-pro"}
    log_id = record_usage(tid, kind="generation", amount=2, meta=meta)
    assert log_id > 0
    # 验证数据库中的 meta_json
    db = models._get_db()
    row = db.execute("SELECT * FROM usage_logs WHERE id = ?", (log_id,)).fetchone()
    parsed = json.loads(row["meta_json"])
    assert parsed["page_slugs"] == ["page-a", "page-b"]


def test_record_usage_with_project():
    """关联 project 的用量能正确存储。"""
    tid = models.create_tenant("proj-co")
    uid = models.create_user("test@example.com", "hash", "salt")
    pid = models.create_project(uid, "test project", tenant_id=tid)
    log_id = record_usage(tid, user_id=uid, project_id=pid, kind="generation", amount=1)
    row = models._get_db().execute("SELECT * FROM usage_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["project_id"] == pid
    assert row["user_id"] == uid


def test_get_usage_summary():
    """get_usage_summary 返回正确的汇总结构。"""
    tid = models.create_tenant("summary-co")
    record_usage(tid, kind="generation", amount=2)
    record_usage(tid, kind="token", amount=35000)
    summary = get_usage_summary(tid)
    assert summary["generations"] == 2
    assert summary["tokens"] == 35000
    assert summary["total_logs"] >= 2


def test_monthly_usage_isolation():
    """不同租户的用量互不污染。"""
    t1 = models.create_tenant("co-a")
    t2 = models.create_tenant("co-b")
    record_usage(t1, kind="generation", amount=3)
    record_usage(t2, kind="generation", amount=1)
    assert get_monthly_usage(t1).get("generation") == 3
    assert get_monthly_usage(t2).get("generation") == 1


def test_usage_logs_created_at_present():
    """每条 usage log 都有 created_at 时间戳。"""
    tid = models.create_tenant("ts-co")
    log_id = record_usage(tid, kind="generation", amount=1)
    row = models._get_db().execute("SELECT * FROM usage_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["created_at"] is not None
    assert len(row["created_at"]) >= 10  # 至少包含日期
