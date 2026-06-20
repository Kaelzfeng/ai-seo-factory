# -*- coding: utf-8 -*-
"""lib/cms_field_mapper.py · Phase 6: PageContent → CMS 字段映射"""


def default_wordpress_mapping() -> dict:
    """默认 WordPress 字段映射规则。"""
    return {
        "title": {"source": "title", "required": True},
        "content": {"source": "gutenberg_html", "fallback": "body_html", "required": True},
        "excerpt": {"source": "meta_description", "required": False},
        "slug": {"source": "slug", "required": True},
        "status": {"default": "draft"},
        "meta_title": {"source": "meta_title", "fallback": "title", "required": False},
        "meta_description": {"source": "meta_description", "required": False},
        "schema_json": {"source": "schema_json", "required": False},
        "page_type": {"source": "page_type", "required": False},
        "primary_keyword": {"source": "primary_keyword", "required": False},
    }


def map_page_content_to_cms_fields(page_content, mapping: dict = None) -> dict:
    """把 PageContent 映射为 CMS 字段 dict。"""
    if mapping is None:
        mapping = default_wordpress_mapping()

    result = {}
    pc = page_content
    for cms_field, rule in mapping.items():
        if "default" in rule:
            result[cms_field] = rule["default"]
            continue

        source = rule.get("source", "")
        fallback = rule.get("fallback", "")
        val = ""

        # Try source
        if hasattr(pc, source):
            val = getattr(pc, source, "")
        elif isinstance(pc, dict) and source in pc:
            val = pc.get(source, "")

        # Try fallback
        if not val and fallback:
            if hasattr(pc, fallback):
                val = getattr(pc, fallback, "")
            elif isinstance(pc, dict) and fallback in pc:
                val = pc.get(fallback, "")

        result[cms_field] = val if val else ""

    return result


def validate_mapping(mapping: dict) -> dict:
    """验证 mapping 规则。"""
    issues = []
    for name, rule in mapping.items():
        if "source" not in rule and "default" not in rule:
            issues.append(f"Field '{name}' has no source or default")
    return {"ok": len(issues) == 0, "issues": issues}


def apply_mapping(page_content, mapping: dict = None) -> dict:
    """映射 + 验证的便捷函数。"""
    return map_page_content_to_cms_fields(page_content, mapping)
