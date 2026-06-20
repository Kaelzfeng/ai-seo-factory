# -*- coding: utf-8 -*-
import importlib
import app  # noqa


def test_all_hit():
    bd = {"score": 15.0, "max": 15.0, "notes": "body count=3"}
    r = app._keyword_landing(bd)
    assert r == {"present": True, "title": True, "meta": True,
                 "heading_intro": True, "body_count": 3}


def test_title_and_meta_miss():
    bd = {"score": 4.0, "max": 15.0, "notes": "not in title; not in meta; body count=2"}
    r = app._keyword_landing(bd)
    assert r["present"] and r["title"] is False and r["meta"] is False
    assert r["heading_intro"] is True and r["body_count"] == 2


def test_no_keyword():
    bd = {"score": 0.0, "max": 15.0, "notes": "ok"}
    r = app._keyword_landing(bd)
    assert r["present"] is False


def test_against_real_quality():
    # 用真实 quality.score_page 的输出反向校验派生与真实命中一致
    from lib import quality
    page = {"target_keyword": "pu leather", "type": "guide", "url": "u", "pillar_url": None, "related": []}
    content = {"title": "PU Leather Guide", "meta_description": "pu leather facts " * 8,
               "html": "<h1>PU Leather</h1><h2>What is pu leather?</h2><p>pu leather " + ("x " * 200) + "</p>"}
    bd = quality.score_page(page, content, {})["breakdown"]["keyword_usage"]
    r = app._keyword_landing(bd)
    assert r["present"] is True and r["title"] is True
