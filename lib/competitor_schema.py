# -*- coding: utf-8 -*-
"""lib/competitor_schema.py · Phase 5: 竞品分析数据契约

全英文字段名, dataclasses, to_dict/from_dict。
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import time


@dataclass
class SERPResult:
    rank: int = 0
    title: str = ""
    url: str = ""
    domain: str = ""
    snippet: str = ""
    source: str = "mock"
    fetched_at: str = ""

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OnPageSignals:
    url: str = ""
    title: str = ""
    meta_description: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    h3: list[str] = field(default_factory=list)
    word_count: int = 0
    language: str = "en"
    canonical: str = ""
    schema_types: list[str] = field(default_factory=list)
    faq_count: int = 0
    images_count: int = 0
    internal_links_count: int = 0
    external_links_count: int = 0

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CompetitorProfile:
    domain: str = ""
    url: str = ""
    rank: int = 0
    title: str = ""
    meta_description: str = ""
    headings: list[str] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    faq_items: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    content_depth_score: float = 0.0
    structure_score: float = 0.0
    authority_signals: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    raw_signals: OnPageSignals | None = None
    error: str = ""

    def to_dict(self):
        d = asdict(self)
        if self.raw_signals:
            d["raw_signals"] = self.raw_signals.to_dict()
        return d

    @classmethod
    def from_dict(cls, d):
        rs = d.get("raw_signals")
        return cls(
            **{k: v for k, v in d.items()
               if k in cls.__dataclass_fields__ and k != "raw_signals"},
            raw_signals=OnPageSignals.from_dict(rs) if rs else None,
        )


@dataclass
class GapMatrix:
    keyword_gaps: list[str] = field(default_factory=list)
    topic_gaps: list[str] = field(default_factory=list)
    schema_gaps: list[str] = field(default_factory=list)
    faq_gaps: list[str] = field(default_factory=list)
    content_depth_gaps: list[str] = field(default_factory=list)
    internal_link_gaps: list[str] = field(default_factory=list)
    page_type_gaps: list[str] = field(default_factory=list)
    priority_items: list[dict] = field(default_factory=list)

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SurpassStrategy:
    target_keyword: str = ""
    recommended_pages: list[str] = field(default_factory=list)
    recommended_sections: list[str] = field(default_factory=list)
    recommended_faq: list[str] = field(default_factory=list)
    recommended_schema: list[str] = field(default_factory=list)
    recommended_internal_links: list[str] = field(default_factory=list)
    content_angle: str = ""
    differentiation_points: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    rationale: str = ""

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CompetitorReport:
    id: int = 0
    tenant_id: int | None = None
    project_id: int | None = None
    query: str = ""
    market: str = "global"
    language: str = "English"
    serp_results: list[SERPResult] = field(default_factory=list)
    competitors: list[CompetitorProfile] = field(default_factory=list)
    gap_matrix: GapMatrix | None = None
    surpass_strategy: SurpassStrategy | None = None
    status: str = "pending"
    errors: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "tenant_id": self.tenant_id, "project_id": self.project_id,
            "query": self.query, "market": self.market, "language": self.language,
            "serp_results": [s.to_dict() for s in self.serp_results],
            "competitors": [c.to_dict() for c in self.competitors],
            "gap_matrix": self.gap_matrix.to_dict() if self.gap_matrix else None,
            "surpass_strategy": self.surpass_strategy.to_dict() if self.surpass_strategy else None,
            "status": self.status, "errors": self.errors, "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CompetitorReport":
        return cls(
            id=d.get("id", 0),
            tenant_id=d.get("tenant_id"),
            project_id=d.get("project_id"),
            query=d.get("query", ""),
            market=d.get("market", "global"),
            language=d.get("language", "English"),
            serp_results=[SERPResult.from_dict(s) for s in d.get("serp_results", [])],
            competitors=[CompetitorProfile.from_dict(c) for c in d.get("competitors", [])],
            gap_matrix=GapMatrix.from_dict(gm) if (gm := d.get("gap_matrix")) else None,
            surpass_strategy=SurpassStrategy.from_dict(ss) if (ss := d.get("surpass_strategy")) else None,
            status=d.get("status", "pending"),
            errors=d.get("errors", []),
            created_at=d.get("created_at", ""),
        )
