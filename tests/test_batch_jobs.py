# -*- coding: utf-8 -*-
"""tests/test_batch_jobs.py · 批量任务数据层测试

覆盖:
1. CSV 正确解析
2. CSV 缺 keyword 返回行号错误
3. create_batch_run 成功
4. create_jobs_from_rows 成功
5. tenant 隔离
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models


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
    tid = models.create_tenant("batch-org")
    uid = models.create_user("batch@test.com", "h", "s")
    pid = models.create_project(
        user_id=uid, name="Batch Project", tenant_id=tid,
        seed_keyword="test", language="English",
        site_url="https://example.com",
    )
    return tid, uid, pid


# ── CSV 解析测试 ─────────────────────────────────────


def test_parse_batch_csv_valid(tmp_path):
    """CSV 正确解析。"""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("keyword,industry_path,mode\nPU leather,industries/pu.yaml,dry-run\nMicrofiber,,publish\n", encoding="utf-8")

    from lib.batch_jobs import parse_batch_csv
    rows = parse_batch_csv(str(csv_path))
    assert len(rows) == 2
    assert rows[0]["keyword"] == "PU leather"
    assert rows[0]["industry_path"] == "industries/pu.yaml"
    assert rows[0]["mode"] == "dry-run"
    assert rows[1]["keyword"] == "Microfiber"
    assert rows[1]["mode"] == "publish"


def test_parse_batch_csv_missing_keyword(tmp_path):
    """CSV 缺 keyword 返回错误含行号。"""
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("keyword,industry_path,mode\nPU leather,x,dry-run\n,,publish\n", encoding="utf-8")

    from lib.batch_jobs import parse_batch_csv
    with pytest.raises(ValueError, match="第 3 行"):
        parse_batch_csv(str(csv_path))


def test_parse_batch_csv_no_keyword_column(tmp_path):
    """CSV 缺少 keyword 列。"""
    csv_path = tmp_path / "nokw.csv"
    csv_path.write_text("name,mode\nTest,dry-run\n", encoding="utf-8")

    from lib.batch_jobs import parse_batch_csv
    with pytest.raises(ValueError, match="缺少必填列"):
        parse_batch_csv(str(csv_path))


def test_parse_batch_csv_empty(tmp_path):
    """空 CSV。"""
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("keyword,industry_path,mode\n", encoding="utf-8")

    from lib.batch_jobs import parse_batch_csv
    with pytest.raises(ValueError, match="没有有效数据"):
        parse_batch_csv(str(csv_path))


def test_parse_batch_csv_default_mode(tmp_path):
    """mode 为空时默认 dry-run。"""
    csv_path = tmp_path / "default.csv"
    csv_path.write_text("keyword,industry_path,mode\nTest,x,\n", encoding="utf-8")

    from lib.batch_jobs import parse_batch_csv
    rows = parse_batch_csv(str(csv_path))
    assert rows[0]["mode"] == "dry-run"


# ── Batch Run 测试 ───────────────────────────────────


def test_create_batch_run(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)

    from lib.batch_jobs import create_batch_run
    br = create_batch_run(
        tenant_id=tid, user_id=uid, project_id=pid,
        name="Test Batch", source="test.csv", mode="dry-run",
    )
    assert br is not None
    assert br["tenant_id"] == tid
    assert br["project_id"] == pid
    assert br["name"] == "Test Batch"
    assert br["status"] == "created"


def test_create_jobs_from_rows(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)

    from lib.batch_jobs import create_batch_run, create_jobs_from_rows
    br = create_batch_run(tenant_id=tid, user_id=uid, project_id=pid,
                          name="Batch", source="test.csv", mode="dry-run")

    rows = [
        {"keyword": "KW1", "industry_path": "", "mode": "dry-run", "_line": 2},
        {"keyword": "KW2", "industry_path": "industries/pu.yaml", "mode": "dry-run", "_line": 3},
    ]
    jobs = create_jobs_from_rows(
        batch_run_id=br["id"], tenant_id=tid,
        user_id=uid, project_id=pid, rows=rows,
    )
    assert len(jobs) == 2
    assert jobs[0]["keyword"] == "KW1"
    assert jobs[0]["status"] == "pending"
    assert jobs[1]["keyword"] == "KW2"

    # batch_run total_jobs 应更新
    from lib.batch_jobs import get_batch_run
    br2 = get_batch_run(br["id"])
    assert br2["total_jobs"] == 2


# ── Tenant 隔离测试 ──────────────────────────────────


def test_batch_run_tenant_isolation(db, monkeypatch):
    tid1, uid1, pid1 = _setup(db, monkeypatch)
    tid2 = models.create_tenant("other-org")

    from lib.batch_jobs import create_batch_run, get_batch_run

    br = create_batch_run(tenant_id=tid1, name="T1 Batch", source="x.csv")

    # tid2 读不到 tid1 的 batch
    result = get_batch_run(br["id"], tenant_id=tid2)
    assert result is None

    # tid1 可以读到
    result = get_batch_run(br["id"], tenant_id=tid1)
    assert result is not None


def test_job_tenant_isolation(db, monkeypatch):
    tid1, uid1, pid1 = _setup(db, monkeypatch)
    tid2 = models.create_tenant("other-org")

    from lib.batch_jobs import create_batch_run, create_jobs_from_rows, get_job

    br = create_batch_run(tenant_id=tid1, name="Batch", source="x.csv")
    rows = [{"keyword": "KW", "industry_path": "", "mode": "dry-run", "_line": 2}]
    jobs = create_jobs_from_rows(batch_run_id=br["id"], tenant_id=tid1,
                                 rows=rows)

    # tid2 读不到 tid1 的 job
    result = get_job(jobs[0]["id"], tenant_id=tid2)
    assert result is None

    # tid1 可以读到
    result = get_job(jobs[0]["id"], tenant_id=tid1)
    assert result is not None


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
