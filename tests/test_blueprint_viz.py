# -*- coding: utf-8 -*-
"""tests/test_blueprint_viz.py · Blueprint 可视化测试

14. blueprint_to_graph_data 输出 nodes / edges
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.schemas import BusinessProfile, PagePlan, SiteBlueprint
from lib.seo_engine.blueprint_viz import (
    blueprint_to_graph_data, blueprint_to_dot,
)


def _sample_blueprint():
    profile = BusinessProfile(industry="Test")
    pages = [
        PagePlan(slug="guide", title="Guide", page_type="guide", primary_keyword="guide"),
        PagePlan(slug="vs", title="VS", page_type="comparison", primary_keyword="vs"),
        PagePlan(slug="faq", title="FAQ", page_type="faq", primary_keyword="faq"),
    ]
    link_graph = {
        "guide": ["vs", "faq"],
        "vs": ["guide"],
        "faq": ["guide"],
    }
    return SiteBlueprint(project_id=1, business_profile=profile, pages=pages, link_graph=link_graph)


def test_graph_data_has_nodes_and_edges():
    bp = _sample_blueprint()
    gd = blueprint_to_graph_data(bp)
    assert "nodes" in gd
    assert "edges" in gd
    assert len(gd["nodes"]) == 3
    assert len(gd["edges"]) >= 2

    node_ids = [n["id"] for n in gd["nodes"]]
    assert "guide" in node_ids
    assert "vs" in node_ids


def test_graph_data_nodes_have_type():
    bp = _sample_blueprint()
    gd = blueprint_to_graph_data(bp)
    for node in gd["nodes"]:
        assert "type" in node
        assert "label" in node


def test_dot_output_is_valid():
    bp = _sample_blueprint()
    dot = blueprint_to_dot(bp)
    assert dot.startswith("digraph")
    assert "guide" in dot
    assert "}" in dot
    assert "->" in dot
