# -*- coding: utf-8 -*-
"""lib/seo_engine/blueprint_viz.py · Blueprint 可视化

输出 JSON nodes/edges 或 DOT 格式。
不依赖 Graphviz,返回 DOT 字符串供外部渲染。
"""

from lib.seo_engine.schemas import SiteBlueprint


def blueprint_to_graph_data(bp: SiteBlueprint) -> dict:
    """将 SiteBlueprint 转为前端可视化用的 graph data。

    Returns:
        {"nodes": [{"id": str, "label": str, "type": str}, ...],
         "edges": [{"source": str, "target": str}, ...]}
    """
    nodes = []
    for page in bp.pages:
        nodes.append({
            "id": page.slug,
            "label": page.title or page.slug,
            "type": page.page_type,
            "primary_keyword": page.primary_keyword,
        })

    edges = []
    seen_edges = set()
    for src, targets in bp.link_graph.items():
        for tgt in targets:
            edge_key = f"{src}->{tgt}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({"source": src, "target": tgt})

    return {"nodes": nodes, "edges": edges}


def blueprint_to_dot(bp: SiteBlueprint) -> str:
    """将 SiteBlueprint 转为 Graphviz DOT 格式字符串。

    不依赖 graphviz 包,返回纯文本。
    """
    lines = ["digraph SiteBlueprint {",
             "  rankdir=LR;",
             "  node [shape=box, style=rounded, fontname=Arial];",
             ""]

    # 节点
    for page in bp.pages:
        color = _type_color(page.page_type)
        label = page.title or page.slug
        lines.append(f'  "{page.slug}" [label="{label}", fillcolor="{color}", style="filled,rounded"];')

    lines.append("")

    # 边
    seen_edges = set()
    for src, targets in bp.link_graph.items():
        for tgt in targets:
            edge_key = f"{src}->{tgt}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                lines.append(f'  "{src}" -> "{tgt}";')

    lines.append("}")
    return "\n".join(lines)


def blueprint_to_svg(bp: SiteBlueprint) -> str:
    """TODO: SVG 渲染。当前返回 DOT 字符串,需外部 graphviz 渲染。

    返回 DOT 格式字符串。
    """
    return blueprint_to_dot(bp)


def _type_color(page_type: str) -> str:
    """页型 → Graphviz 颜色映射。"""
    colors = {
        "guide": "#e8f5e9",
        "pillar": "#e8f5e9",
        "comparison": "#fff3e0",
        "faq": "#e3f2fd",
        "product": "#fce4ec",
        "category": "#f3e5f5",
        "article": "#ffffff",
        "landing": "#e0f2f1",
    }
    return colors.get(page_type, "#f5f5f5")
