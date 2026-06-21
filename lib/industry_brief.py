# -*- coding: utf-8 -*-
"""Deterministic product and industry context for B2B content generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class IndustryBrief:
    industry: str
    product: str
    buyer_type: str
    market: str
    language: str
    spec_dimensions: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    quality_checks: list[str] = field(default_factory=list)
    buyer_pain_points: list[str] = field(default_factory=list)
    purchase_factors: list[str] = field(default_factory=list)
    export_factors: list[str] = field(default_factory=list)
    customization_options: list[str] = field(default_factory=list)
    packaging_factors: list[str] = field(default_factory=list)
    faq_topics: list[str] = field(default_factory=list)
    content_angles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "IndustryBrief":
        values = {name: data.get(name) for name in cls.__dataclass_fields__}
        return cls(**values)

    def all_terms(self) -> list[str]:
        """Return stable, unique terms that can be checked against page copy."""
        values = [self.product, self.industry]
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, list):
                values.extend(value)
        seen = set()
        terms = []
        for value in values:
            term = str(value or "").strip()
            key = term.casefold()
            if term and key not in seen:
                seen.add(key)
                terms.append(term)
        return terms


_CLASSIFIERS = (
    ("metal_pipe", (
        "铁管", "钢管", "不锈钢管", "铝型材", "金属管", "steel pipe",
        "stainless pipe", "carbon steel pipe", "metal tube", "aluminum profile",
    )),
    ("hardware_tools", (
        "铁锤", "锤子", "扳手", "螺丝刀", "五金工具", "hammer", "wrench",
        "screwdriver", "hardware tool",
    )),
    ("ceramic_homeware", (
        "陶瓷杯", "餐具", "马克杯", "玻璃杯", "ceramic mug", "tableware",
        "mug", "glass cup", "homeware",
    )),
    ("hydraulic_parts", (
        "液压接头", "软管接头", "阀门", "法兰", "hydraulic fitting",
        "hose fitting", "hydraulic valve", "flange",
    )),
    ("industrial_belt", (
        "工业皮带", "输送带", "传动带", "industrial belt", "conveyor belt",
        "transmission belt", "v-belt",
    )),
    ("textile_apparel", (
        "t恤", "运动服", "帽子", "布料", "t-shirt", "sportswear", "cap",
        "fabric", "apparel", "textile",
    )),
    ("packaging_display", (
        "纸盒", "亚克力展示架", "包装袋", "paper box", "acrylic display",
        "display stand", "packaging bag", "packaging box",
    )),
    ("pet_products", (
        "宠物梳", "宠物玩具", "宠物碗", "宠物用品", "pet grooming brush",
        "pet brush", "pet toy", "pet bowl", "pet product",
    )),
)


_LIBRARIES = {
    "metal_pipe": {
        "industry": "Metal / Pipe / Steel Products",
        "spec_dimensions": ["outer diameter", "wall thickness", "length", "tolerance"],
        "materials": ["galvanized steel", "stainless steel", "carbon steel"],
        "applications": ["construction", "scaffolding", "greenhouse", "furniture frame"],
        "standards": ["ASTM", "JIS", "EN", "GB"],
        "quality_checks": ["dimensional inspection", "coating thickness", "MTC verification"],
        "buyer_pain_points": ["tolerance mismatch", "corrosion risk", "container damage"],
        "purchase_factors": ["grade selection", "mill capacity", "MOQ", "lead time"],
        "export_factors": ["container loading", "MTC", "third-party inspection", "export documents"],
        "customization_options": ["cut length", "surface finish", "galvanized coating", "end treatment"],
        "packaging_factors": ["steel bundle", "waterproof wrapping", "container bracing"],
        "faq_topics": ["outer diameter tolerance", "MOQ", "MTC", "loading quantity", "cut length"],
        "content_angles": ["specification-led sourcing", "application and grade matching"],
    },
    "hardware_tools": {
        "industry": "Hardware Tools",
        "spec_dimensions": ["handle length", "head weight", "hardness", "grip profile"],
        "materials": ["forged carbon steel", "fiberglass handle", "wood handle", "TPR grip"],
        "applications": ["DIY", "construction", "industrial maintenance", "retail tool kits"],
        "standards": ["Rockwell hardness", "drop test protocol", "retail labeling requirements"],
        "quality_checks": ["head retention test", "hardness test", "grip pull test"],
        "buyer_pain_points": ["loose tool heads", "inconsistent hardness", "damaged retail packs"],
        "purchase_factors": ["tool range", "private label MOQ", "wholesale price tier", "lead time"],
        "export_factors": ["country-of-origin marking", "carton drop test", "export documents"],
        "customization_options": ["private label", "handle color", "laser logo", "tool set configuration"],
        "packaging_factors": ["bulk carton", "retail blister pack", "color box", "master carton"],
        "faq_topics": ["head material", "handle material", "hardness", "private label MOQ", "packing"],
        "content_angles": ["durability evidence", "retail and wholesale assortment planning"],
    },
    "ceramic_homeware": {
        "industry": "Ceramic / Homeware",
        "spec_dimensions": ["capacity", "rim diameter", "height", "shape"],
        "materials": ["ceramic", "stoneware", "porcelain", "lead-free glaze"],
        "applications": ["supermarket retail", "gift buyers", "cafe service", "promotional merchandise"],
        "standards": ["food contact safety", "lead and cadmium migration limits"],
        "quality_checks": ["drop test", "glaze inspection", "thermal shock test"],
        "buyer_pain_points": ["glaze variation", "breakage in transit", "food safety documentation"],
        "purchase_factors": ["capacity range", "decoration cost", "MOQ", "retail margin"],
        "export_factors": ["food contact report", "drop-test record", "export documents"],
        "customization_options": ["logo customization", "decal printing", "glaze color", "custom shape"],
        "packaging_factors": ["gift box", "retail packaging", "divider carton", "protective insert"],
        "faq_topics": ["capacity", "glaze", "food contact safety", "MOQ", "logo customization", "gift box"],
        "content_angles": ["shelf-ready collections", "food-safe customization"],
    },
    "hydraulic_parts": {
        "industry": "Hydraulic / Industrial Parts",
        "spec_dimensions": ["thread standard", "pressure rating", "sealing type", "connection size"],
        "materials": ["carbon steel", "stainless steel", "brass", "zinc-nickel plating"],
        "applications": ["industrial equipment", "hydraulic system", "mobile machinery", "fluid power assembly"],
        "standards": ["BSP", "NPT", "JIC", "DIN"],
        "quality_checks": ["leakage test", "pressure proof test", "thread gauge inspection"],
        "buyer_pain_points": ["leakage risk", "thread mismatch", "seal failure"],
        "purchase_factors": ["pressure class", "material grade", "sample confirmation", "MOQ"],
        "export_factors": ["inspection certificate", "material traceability", "export documents", "Europe compliance review"],
        "customization_options": ["custom thread", "seal material", "surface plating", "assembly kit"],
        "packaging_factors": ["thread protection cap", "sealed bag", "labeled carton"],
        "faq_topics": ["thread standard", "working pressure", "sealing type", "sample confirmation", "MOQ"],
        "content_angles": ["leak prevention", "interface compatibility"],
    },
    "industrial_belt": {
        "industry": "Industrial Belts / Power Transmission",
        "spec_dimensions": ["belt width", "belt length", "tensile strength", "ply count"],
        "materials": ["rubber grade", "polyester carcass", "PVC", "polyurethane"],
        "applications": ["conveyor", "material handling", "power transmission", "factory automation"],
        "standards": ["DIN abrasion", "ISO belt specification", "antistatic requirement"],
        "quality_checks": ["abrasion resistance", "adhesion test", "tensile test"],
        "buyer_pain_points": ["premature wear", "belt tracking", "splice failure"],
        "purchase_factors": ["load profile", "operating temperature", "MOQ", "service life"],
        "export_factors": ["roll dimensions", "batch test report", "export documents"],
        "customization_options": ["cover pattern", "cleat profile", "endless splice", "custom width"],
        "packaging_factors": ["roll packaging", "pallet protection", "splice kit"],
        "faq_topics": ["belt width", "ply count", "abrasion resistance", "splice method", "MOQ"],
        "content_angles": ["downtime reduction", "load and environment matching"],
    },
    "textile_apparel": {
        "industry": "Textile / Apparel",
        "spec_dimensions": ["fabric composition", "GSM", "size range", "size chart"],
        "materials": ["cotton", "polyester", "spandex", "blended fabric"],
        "applications": ["retail collection", "sports team", "brand merchandise", "uniform program"],
        "standards": ["color fastness", "shrinkage tolerance", "restricted substances"],
        "quality_checks": ["stitching inspection", "color fastness test", "measurement check"],
        "buyer_pain_points": ["size inconsistency", "color variation", "late seasonal delivery"],
        "purchase_factors": ["GSM", "size ratio", "MOQ", "production lead time"],
        "export_factors": ["fiber content label", "packing list", "export documents"],
        "customization_options": ["logo printing", "embroidery", "custom color", "private label"],
        "packaging_factors": ["individual polybag", "size sticker", "retail carton"],
        "faq_topics": ["fabric composition", "GSM", "size chart", "logo method", "MOQ"],
        "content_angles": ["fit consistency", "brand-ready production"],
    },
    "packaging_display": {
        "industry": "Packaging / Display Products",
        "spec_dimensions": ["material thickness", "structure", "load capacity", "finished size"],
        "materials": ["corrugated board", "kraft paper", "acrylic", "laminated film"],
        "applications": ["retail display", "retail shelf", "counter display", "e-commerce packaging", "gift presentation"],
        "standards": ["print color tolerance", "carton compression requirement", "retail compliance"],
        "quality_checks": ["load test", "print registration", "dieline fit check"],
        "buyer_pain_points": ["structure collapse", "color mismatch", "assembly complexity"],
        "purchase_factors": ["printing method", "MOQ", "tooling cost", "flat-pack efficiency"],
        "export_factors": ["pallet utilization", "carton marks", "export documents"],
        "customization_options": ["custom mold", "dieline", "offset printing", "screen printing"],
        "packaging_factors": ["flat packing", "protective film", "master packaging"],
        "faq_topics": ["material thickness", "dieline", "printing method", "MOQ", "sample approval"],
        "content_angles": ["retail conversion", "shipping-volume efficiency"],
    },
    "pet_products": {
        "industry": "Pet Products",
        "spec_dimensions": ["pet size", "product dimensions", "bristle spacing", "handle size"],
        "materials": ["material safety", "BPA-free plastic", "stainless steel", "soft TPR"],
        "applications": ["home grooming", "pet shop", "Amazon retail", "professional groomer"],
        "standards": ["material safety declaration", "retail labeling", "small-parts assessment"],
        "quality_checks": ["durability test", "bite resistance", "handle pull test"],
        "buyer_pain_points": ["sharp edges", "weak bristles", "difficult cleaning"],
        "purchase_factors": ["pet size range", "cleaning method", "MOQ", "retail price point"],
        "export_factors": ["material declaration", "retail barcode", "export documents"],
        "customization_options": ["logo printing", "color matching", "private label", "set configuration"],
        "packaging_factors": ["retail packaging", "hanging card", "Amazon-ready carton"],
        "faq_topics": ["pet size", "material safety", "cleaning method", "durability", "MOQ", "custom logo"],
        "content_angles": ["pet-safe design", "retail-ready assortment"],
    },
}


def _safe(value, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text and text.casefold() != "none" else fallback


def _classify(product: str, industry: str) -> str:
    haystack = f"{product} {industry}".casefold()
    for key, terms in _CLASSIFIERS:
        if any(term.casefold() in haystack for term in terms):
            return key
    return "generic"


def _generic_library(product: str) -> dict:
    return {
        "industry": f"{product} Product Discovery",
        "spec_dimensions": [f"{product} dimensions", f"{product} performance specification", f"{product} tolerance"],
        "materials": [f"{product} material options", f"{product} finish options"],
        "applications": [f"{product} buyer use case", f"{product} operating environment"],
        "standards": [f"{product} applicable standards", f"{product} buyer compliance requirements"],
        "quality_checks": [f"{product} sample inspection", f"{product} functional test"],
        "buyer_pain_points": [f"unclear {product} specification", f"unverified {product} quality"],
        "purchase_factors": [f"{product} specification questions", f"{product} MOQ", f"{product} lead time"],
        "export_factors": [f"{product} export documents", f"{product} shipment planning"],
        "customization_options": [f"{product} customization options", f"{product} private label"],
        "packaging_factors": [f"{product} packaging", f"{product} transport protection"],
        "faq_topics": [f"{product} material options", f"{product} MOQ", f"{product} packaging", f"{product} export documents"],
        "content_angles": [f"define {product} before quotation", f"match {product} to buyer use case"],
    }


def build_industry_brief(intent: dict | None) -> IndustryBrief:
    """Infer a non-empty product brief without external calls or secrets.

    Phase 9.4.1: Uses product_localized for brief.product when available,
    falling back to the cleaned original product name.
    Classification is always done against the ORIGINAL product so that
    localized names (e.g. 鉄管) still match their classifier (e.g. 铁管).
    """
    from lib.localization import clean_product_display_name, normalize_language, normalize_market

    intent = intent or {}

    # Original product for classification (never localized, always the
    # extracted/cleaned product phrase in its source language).
    product_original = clean_product_display_name(
        intent.get("product") or intent.get("product_phrase") or intent.get("industry"),
        language=intent.get("language"), market=intent.get("market"),
    )
    product_original = _safe(product_original, "B2B product")

    # Phase 9.4.1: Prefer product_localized for page content generation
    product_localized = intent.get("product_localized")
    if product_localized and str(product_localized).strip() and str(product_localized).lower() != "none":
        product = str(product_localized).strip()
    else:
        product = product_original

    raw_industry = _safe(intent.get("industry"), product_original)
    # Classify using the ORIGINAL product (localized names won't match classifiers)
    key = _classify(product_original, raw_industry)
    library = dict(_LIBRARIES.get(key) or _generic_library(product))
    return IndustryBrief(
        industry=library.pop("industry"),
        product=product,
        buyer_type=_safe(intent.get("audience") or intent.get("buyer_type"), "B2B buyers and distributors"),
        market=normalize_market(intent.get("market")) or "global export markets",
        language=normalize_language(intent.get("language")),
        **library,
    )
