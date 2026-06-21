# -*- coding: utf-8 -*-
"""Regression tests for query-aware mock competitor analysis."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

import models
from lib.competitor_analysis import analyze_competitors
from lib.competitor_schema import CompetitorReport, SERPResult
from lib.gap_analyzer import build_gap_matrix
from lib.surpass_strategy import build_surpass_strategy


ROOT = Path(__file__).resolve().parent.parent
QUERY = "hardware tools supplier"
HARDWARE_TERMS = (
    "hardware tools", "hammer", "supplier", "manufacturer", "wholesale",
    "export", "b2b buyers", "bulk order", "specifications", "oem",
    "packaging", "export documentation",
)
LEATHER_TERMS = (
    "pu leather", "synthetic leather", "leather", "pvc leather",
    "pu-leather", "microfiber", "mock snippet for: pu leather",
    "example.com/pu-leather-guide",
)


def _mock_report(limit=10):
    return analyze_competitors(QUERY, provider_name="mock", limit=limit)


def _serialized(value):
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, ensure_ascii=False).lower()


def test_mock_competitor_analysis_uses_current_query():
    report = _mock_report(3)

    assert report.query == QUERY
    assert QUERY in _serialized(report)


def test_hardware_tools_mock_report_not_pu_leather():
    text = _serialized(_mock_report())

    assert not any(term in text for term in LEATHER_TERMS)


def test_hardware_tools_mock_serp_contains_hardware_terms():
    report = _mock_report()

    assert report.serp_results
    for result in report.serp_results:
        text = f"{result.title} {result.snippet}".lower()
        assert any(term in text for term in (
            "hardware tools", "hammer", "supplier", "manufacturer",
            "wholesale", "export",
        ))


def test_hardware_tools_mock_competitors_contains_supplier_export_terms():
    text = _serialized([profile.to_dict() for profile in _mock_report().competitors])

    for term in HARDWARE_TERMS:
        assert term in text


def test_hardware_tools_gap_matrix_not_leather():
    report = _mock_report()
    gap = build_gap_matrix(report.competitors)
    text = _serialized(gap)

    assert "leather" not in text
    assert "detailed hardware tools supplier comparison" in text
    assert "add faq: how to choose a hardware tools supplier?" in text
    assert "add faq: what export documents do wholesale hardware tools buyers need?" in text


def test_hardware_tools_surpass_strategy_not_leather():
    report = _mock_report()
    gap = build_gap_matrix(report.competitors)
    strategy = build_surpass_strategy(QUERY, gap, report.competitors)
    text = _serialized(strategy)

    assert "leather" not in text
    for term in ("supplier", "manufacturer", "wholesale", "export", "specifications"):
        assert any(term in page for page in strategy.recommended_pages)


@pytest.mark.parametrize(
    ("title", "url", "snippet"),
    [
        (
            "PU Leather Supplier Guide",
            "https://example.com/pu-leather-guide",
            "Synthetic leather sourcing",
        ),
        (
            "Ceramic Tile Distributor Guide",
            "https://surfaces.example/ceramic-tile-guide",
            "Porcelain flooring and tile distributor sourcing",
        ),
    ],
)
def test_analyze_competitor_rejects_topic_mismatch_before_save(
    monkeypatch, title, url, snippet,
):
    import lib.competitor_analysis as analysis_module
    import run

    poisoned = CompetitorReport(
        project_id=9,
        tenant_id=19,
        query=QUERY,
        serp_results=[SERPResult(
            rank=1,
            title=title,
            url=url,
            domain=url.split("/")[2],
            snippet=snippet,
        )],
    )
    saved = []
    monkeypatch.setattr(analysis_module, "analyze_competitors", lambda **kwargs: poisoned)
    monkeypatch.setattr(models, "create_competitor_report", lambda **kwargs: saved.append(kwargs))

    with pytest.raises(ValueError, match="topic mismatch"):
        run.analyze_competitor_seo(QUERY, project_id=9, tenant_id=19)

    assert saved == []


def test_competitor_report_saved_with_project_id_and_query(monkeypatch):
    import run

    saved = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return 321

    monkeypatch.setattr(models, "create_competitor_report", fake_save)
    report = run.analyze_competitor_seo(QUERY, project_id=9, tenant_id=19, limit=3)

    assert report["id"] == 321
    assert report["project_id"] == 9
    assert report["query"] == QUERY
    assert saved[0]["project_id"] == 9
    assert saved[0]["query"] == QUERY
    assert not any(term in saved[0]["report_json"].lower() for term in LEATHER_TERMS)


@pytest.fixture
def competitor_api_env(monkeypatch):
    from app import app

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(db_path)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tenant_id = models.create_tenant("query-filter-org")
    user_id = models.create_user("query-filter@test.local", "h", "s")
    models.add_tenant_member(tenant_id, user_id, role="owner")
    project_a = models.create_project(
        user_id=user_id,
        tenant_id=tenant_id,
        name="Hardware A",
        seed_keyword=QUERY,
    )
    project_b = models.create_project(
        user_id=user_id,
        tenant_id=tenant_id,
        name="Hardware B",
        seed_keyword=QUERY,
    )
    app.config.update(TESTING=True, SECRET_KEY="test")

    yield app, conn, tenant_id, user_id, project_a, project_b

    conn.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


def test_competitor_reports_api_filters_by_project_id_and_query(competitor_api_env):
    app, _conn, tenant_id, user_id, project_a, project_b = competitor_api_env
    wanted_id = models.create_competitor_report(
        tenant_id=tenant_id,
        project_id=project_a,
        query=QUERY,
        report_json='{"kind":"wanted"}',
    )
    models.create_competitor_report(
        tenant_id=tenant_id,
        project_id=project_a,
        query="industrial fasteners supplier",
    )
    models.create_competitor_report(
        tenant_id=tenant_id,
        project_id=project_b,
        query=QUERY,
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = user_id
        response = client.get(
            f"/api/competitor/reports?project_id={project_a}&query=hardware+tools+supplier"
        )

    assert response.status_code == 200
    reports = response.get_json()["reports"]
    assert [report["id"] for report in reports] == [wanted_id]


def test_static_not_modified():
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "static"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == ""


def test_templates_no_mojibake():
    mojibake_markers = ("\ufffd", "閿熸枻鎷", "閳光偓", "脙", "脗", "芒鈧")
    for path in (ROOT / "templates").rglob("*.html"):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        assert hashlib.sha256(raw).hexdigest()
        assert not any(marker in text for marker in mojibake_markers), path
