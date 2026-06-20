# -*- coding: utf-8 -*-
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import run


_BASE = {"title": "T", "meta_description": "M", "html": "<h1>x</h1>",
         "image_query": "pu leather"}


def test_polish_keeps_better(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather", "title": "T"}
    orig = dict(_BASE)
    polished = dict(_BASE, meta_description="better")
    q_orig = {"score": 80.0, "issues": ["meta description 200 chars"]}
    q_better = {"score": 92.0, "issues": []}
    monkeypatch.setattr(run.llm, "structured", lambda *a, **k: polished)
    # 复评:润色版给高分
    monkeypatch.setattr(run.quality, "score_page", lambda pg, c, cfg: q_better)
    out_content, out_q = run.polish_page(page, orig, q_orig, {}, "profile", lambda s: None)
    assert out_content is polished
    assert out_q["score"] == 92.0


def test_polish_keeps_original_when_not_better(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather", "title": "T"}
    orig = dict(_BASE)
    polished = dict(_BASE, meta_description="worse")
    q_orig = {"score": 88.0, "issues": ["Title 80 chars"]}
    monkeypatch.setattr(run.llm, "structured", lambda *a, **k: polished)
    # 复评:润色版分更低 → 保留原版
    monkeypatch.setattr(run.quality, "score_page", lambda pg, c, cfg: {"score": 70.0, "issues": []})
    out_content, out_q = run.polish_page(page, orig, q_orig, {}, "profile", lambda s: None)
    assert out_content is orig
    assert out_q["score"] == 88.0


def test_polish_noop_when_no_issues(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather"}
    orig = dict(_BASE)
    q = {"score": 100.0, "issues": []}
    called = {"n": 0}
    monkeypatch.setattr(run.llm, "structured", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or orig)
    out_content, out_q = run.polish_page(page, orig, q, {}, "profile", lambda s: None)
    assert out_content is orig and called["n"] == 0  # 无 issue 不调 LLM


def test_polish_keeps_original_on_llm_error(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather"}
    orig = dict(_BASE)
    q = {"score": 80.0, "issues": ["meta description 200 chars"]}
    def _boom(*a, **k):
        raise RuntimeError("deepseek down")
    monkeypatch.setattr(run.llm, "structured", _boom)
    out_content, out_q = run.polish_page(page, orig, q, {}, "profile", lambda s: None)
    assert out_content is orig and out_q is q  # 失败保留原版,不抛
