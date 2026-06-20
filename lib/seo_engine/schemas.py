# -*- coding: utf-8 -*-
"""lib/seo_engine/schemas.py · Phase 3 dataclass schemas

使用 stdlib dataclasses,零外部依赖。
每个类提供 to_dict() / from_dict() 用于 JSON 序列化。
字段名全英文,便于未来 Java 迁移。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


def _list_from_dicts(items: list, cls):
    """Helper: convert list of dicts to list of dataclass instances."""
    if not items:
        return []
    return [cls.from_dict(i) if isinstance(i, dict) else i for i in items]


def _list_to_dicts(items: list) -> list:
    """Helper: convert list of dataclass instances to list of dicts."""
    if not items:
        return []
    return [i.to_dict() if hasattr(i, "to_dict") else i for i in items]


# ── QualityReport (placeholder) ──────────────────────


@dataclass
class QualityReport:
    """占位结构,供未来 Stage 4 使用。"""
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "QualityReport":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── BusinessProfile ──────────────────────────────────


@dataclass
class BusinessProfile:
    industry: str = ""
    business_type: str = ""
    target_markets: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    buyer_personas: list[str] = field(default_factory=list)
    value_propositions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    tone: str = "Professional, factual"
    terminology: list[str] = field(default_factory=list)
    source_input: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BusinessProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Keyword ──────────────────────────────────────────


@dataclass
class Keyword:
    keyword: str = ""
    intent: str = "informational"
    priority: int = 0
    language: str = "English"
    market: str = ""
    volume_hint: int = 0
    difficulty_hint: int = 0
    source: str = ""
    cluster_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Keyword":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Topic ────────────────────────────────────────────


@dataclass
class Topic:
    id: str = ""
    name: str = ""
    intent: str = "informational"
    keywords: list[str] = field(default_factory=list)
    priority: int = 0
    page_type: str = "article"
    pillar_keyword: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Topic":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── PagePlan ─────────────────────────────────────────


@dataclass
class PagePlan:
    slug: str = ""
    title: str = ""
    page_type: str = "article"
    primary_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    intent: str = "informational"
    language: str = "English"
    market: str = ""
    cluster_id: str = ""
    parent_slug: str = ""
    suggested_sections: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    # Phase 5.1: competitor gap hints
    competitor_gap_hints: list[str] = field(default_factory=list)
    recommended_faq: list[str] = field(default_factory=list)
    recommended_schema: list[str] = field(default_factory=list)
    content_angle: str = ""
    differentiation_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PagePlan":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── SiteBlueprint ────────────────────────────────────


@dataclass
class SiteBlueprint:
    project_id: int = 0
    business_profile: BusinessProfile | None = None
    keywords: list[Keyword] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    pages: list[PagePlan] = field(default_factory=list)
    link_graph: dict = field(default_factory=dict)
    created_at: str = ""
    review_status: str = "pending_review"
    # Phase 5.1: competitor integration
    competitor_hints: dict | None = None
    source_competitor_report_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "business_profile": self.business_profile.to_dict() if self.business_profile else None,
            "keywords": _list_to_dicts(self.keywords),
            "topics": _list_to_dicts(self.topics),
            "pages": _list_to_dicts(self.pages),
            "link_graph": self.link_graph,
            "created_at": self.created_at,
            "review_status": self.review_status,
            "competitor_hints": self.competitor_hints,
            "source_competitor_report_id": self.source_competitor_report_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SiteBlueprint":
        bp = d.get("business_profile")
        return cls(
            project_id=d.get("project_id", 0),
            business_profile=BusinessProfile.from_dict(bp) if bp else None,
            keywords=_list_from_dicts(d.get("keywords", []), Keyword),
            topics=_list_from_dicts(d.get("topics", []), Topic),
            pages=_list_from_dicts(d.get("pages", []), PagePlan),
            link_graph=d.get("link_graph", {}),
            created_at=d.get("created_at", ""),
            review_status=d.get("review_status", "pending_review"),
            competitor_hints=d.get("competitor_hints"),
            source_competitor_report_id=d.get("source_competitor_report_id"),
        )


# ── PageContent (Phase 4) ────────────────────────────


@dataclass
class PageContent:
    slug: str = ""
    title: str = ""
    page_type: str = "article"
    primary_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    meta_title: str = ""
    meta_description: str = ""
    body_html: str = ""
    faq: list[dict] = field(default_factory=list)
    cta: str = ""
    schema_json: str = ""
    internal_links: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    review_status: str = "pending"
    source_page_plan: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PageContent":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
