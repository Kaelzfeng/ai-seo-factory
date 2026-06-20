# -*- coding: utf-8 -*-
"""lib/seo_engine/stage5_links.py · Stage 5: 内部链接注入

根据 SiteBlueprint.link_graph 和 PagePlan.internal_links
给 PageContent 注入内部链接。
"""

import re

from lib.seo_engine.schemas import SiteBlueprint, PageContent


# 构造内部链接 HTML
_LINK_HTML = '<a href="{url}">{title}</a>'


def _build_link_html(slug: str, title_map: dict) -> str:
    """构建内部链接 <a> 标签。"""
    title = title_map.get(slug, slug.replace('-', ' ').title())
    return _LINK_HTML.format(url=f"./{slug}.html", title=title)


def attach_internal_links(page_content, blueprint) -> PageContent:
    """给 PageContent.body_html 注入内部链接。

    - pillar 页面链接到所有非 pillar 页面
    - 非 pillar 页面链接回 pillar
    - 同 cluster 互链
    - 不链接到不存在的 slug

    Args:
        page_content: PageContent
        blueprint: SiteBlueprint

    Returns:
        modified PageContent
    """
    if isinstance(blueprint, dict):
        blueprint = SiteBlueprint.from_dict(blueprint)

    # 构建标题映射
    title_map = {}
    for pp in blueprint.pages:
        title_map[pp.slug] = pp.title or pp.primary_keyword

    # 获取本页应链接的目标
    slug = ""
    page_type = ""
    if hasattr(page_content, 'slug'):
        slug = page_content.slug
        page_type = page_content.page_type
    elif isinstance(page_content, dict):
        slug = page_content.get('slug', '')
        page_type = page_content.get('page_type', '')

    link_graph = getattr(blueprint, 'link_graph', {})
    if isinstance(link_graph, str):
        import json
        link_graph = json.loads(link_graph)

    targets = link_graph.get(slug, [])

    # 构建链接 HTML
    links_html = ""
    for target_slug in targets[:5]:  # 最多 5 个
        if target_slug in title_map:
            links_html += f'<p>{_build_link_html(target_slug, title_map)}</p>\n'

    if not links_html:
        return page_content

    # 注入到 body_html 末尾
    body = ""
    if hasattr(page_content, 'body_html'):
        body = page_content.body_html
    elif isinstance(page_content, dict):
        body = page_content.get('body_html', '')

    body += f'\n<section class="internal-links"><h2>Related Pages</h2>\n{links_html}</section>'

    if hasattr(page_content, 'body_html'):
        page_content.body_html = body
        page_content.internal_links = targets
    elif isinstance(page_content, dict):
        page_content['body_html'] = body
        page_content['internal_links'] = targets

    return page_content


def attach_links_to_pages(page_contents: list, blueprint) -> list:
    """批量注入链接。"""
    return [attach_internal_links(pc, blueprint) for pc in page_contents]


def validate_internal_links(page_contents: list, blueprint) -> dict:
    """验证内部链接质量。

    Returns:
        {"ok": bool, "pages_without_links": [...], "bad_links": [...]}
    """
    if isinstance(blueprint, dict):
        blueprint = SiteBlueprint.from_dict(blueprint)

    valid_slugs = {pp.slug for pp in blueprint.pages}
    pages_without_links = []
    bad_links = []

    for pc in page_contents:
        slug = pc.slug if hasattr(pc, 'slug') else pc.get('slug', '')
        il = pc.internal_links if hasattr(pc, 'internal_links') else pc.get('internal_links', [])

        if not il:
            pages_without_links.append(slug)

        for link in il:
            if link not in valid_slugs:
                bad_links.append({"page": slug, "bad_link": link})

    ok = len(pages_without_links) == 0 and len(bad_links) == 0
    return {"ok": ok, "pages_without_links": pages_without_links, "bad_links": bad_links}
