# -*- coding: utf-8 -*-
"""Phase 9.4.0 industry-aware content contracts."""

from __future__ import annotations

import hashlib
import importlib.util
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            try:
                digest.update(item.read_bytes())
            except PermissionError:
                digest.update(str(item.stat().st_size).encode("ascii"))
    return digest.hexdigest()


def _brief(intent):
    assert importlib.util.find_spec("lib.industry_brief") is not None
    from lib.industry_brief import build_industry_brief
    return build_industry_brief(intent)


def _writer(page_type, brief):
    assert importlib.util.find_spec("lib.page_content_writer") is not None
    from lib.page_content_writer import write_page_content
    return write_page_content({"type": page_type, "page_type": page_type}, brief)


def _all_text(brief) -> str:
    return " ".join(str(value) for value in brief.to_dict().values()).lower()


def test_pipe_industry_brief_has_pipe_specific_terms():
    brief = _brief({"product": "铁管", "language": "Japanese", "market": "Japan"})
    text = _all_text(brief)
    for term in ("outer diameter", "wall thickness", "tolerance", "astm", "mtc", "container loading"):
        assert term in text


def test_ceramic_mug_brief_has_homeware_specific_terms():
    brief = _brief({"product": "陶瓷杯", "language": "Spanish", "audience": "supermarket buyers"})
    text = _all_text(brief)
    for term in ("capacity", "glaze", "food contact safety", "drop test", "gift box"):
        assert term in text


def test_hydraulic_fitting_brief_has_hydraulic_specific_terms():
    brief = _brief({"product": "液压接头", "language": "English", "market": "Europe"})
    text = _all_text(brief)
    for term in ("thread standard", "pressure rating", "sealing type", "bsp", "npt", "jic", "din", "leakage risk"):
        assert term in text


def test_industrial_belt_brief_has_industrial_specific_terms():
    brief = _brief({"product": "industrial belt", "language": "English", "audience": "factory buyers"})
    text = _all_text(brief)
    for term in ("belt width", "tensile strength", "ply count", "abrasion resistance", "conveyor"):
        assert term in text


def test_pet_product_brief_has_pet_specific_terms():
    brief = _brief({"product": "宠物梳", "language": "German", "audience": "pet shop buyers"})
    text = _all_text(brief)
    for term in ("material safety", "pet size", "durability", "cleaning method", "retail packaging"):
        assert term in text


def test_generic_fallback_brief_uses_product_phrase():
    brief = _brief({"product": "solar orchard monitor", "language": "English"})
    assert brief.product == "solar orchard monitor"
    text = _all_text(brief)
    assert "solar orchard monitor" in text
    assert all((brief.spec_dimensions, brief.purchase_factors, brief.export_factors, brief.faq_topics))


def test_pipe_and_ceramic_content_are_not_same_template():
    pipe = _writer("supplier_guide", _brief({"product": "steel pipe", "language": "English"}))["html"]
    ceramic = _writer("supplier_guide", _brief({"product": "ceramic mug", "language": "English"}))["html"]
    assert SequenceMatcher(None, pipe, ceramic).ratio() < 0.72


def test_hydraulic_and_pet_content_are_not_same_template():
    hydraulic = _writer("specifications", _brief({"product": "hydraulic fitting", "language": "English"}))["html"]
    pet = _writer("specifications", _brief({"product": "pet grooming brush", "language": "English"}))["html"]
    assert SequenceMatcher(None, hydraulic, pet).ratio() < 0.72


def test_generated_page_contains_product_name():
    brief = _brief({"product": "ceramic mug", "language": "English"})
    assert brief.product.lower() in _writer("manufacturer", brief)["html"].lower()


def test_generated_page_contains_industry_terms():
    brief = _brief({"product": "hydraulic fitting", "language": "English"})
    html = _writer("export", brief)["html"].lower()
    assert sum(term.lower() in html for term in brief.all_terms()) >= 5


def test_generated_page_does_not_contain_none():
    brief = _brief({"product": "paper box", "language": "English", "market": None})
    for page_type in ("supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq"):
        page = _writer(page_type, brief)
        assert "none" not in (page["title"] + page["meta_description"] + page["html"] + page["cta"]).lower()


def test_generated_page_not_generic_boilerplate_only():
    brief = _brief({"product": "ceramic mug", "language": "English"})
    html = _writer("supplier_guide", brief)["html"]
    banned = (
        "Review manufacturing controls", "Confirm commercial terms",
        "Supplier and Manufacturing Scope", "Wholesale and Export Requirements",
        "This B2B export guide helps buyers evaluate suppliers",
    )
    assert not any(phrase.lower() in html.lower() for phrase in banned)


def test_each_page_uses_industry_brief_terms():
    brief = _brief({"product": "steel pipe", "language": "English"})
    for page_type in ("supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq"):
        html = _writer(page_type, brief)["html"].lower()
        assert sum(term.lower() in html for term in brief.all_terms()) >= 5, page_type


def test_supplier_page_uses_specific_specs():
    brief = _brief({"product": "steel pipe", "language": "English"})
    html = _writer("supplier_guide", brief)["html"].lower()
    assert "outer diameter" in html and "wall thickness" in html and "construction" in html


def test_manufacturer_page_uses_material_and_quality():
    brief = _brief({"product": "ceramic mug", "language": "English"})
    html = _writer("manufacturer", brief)["html"].lower()
    assert "ceramic" in html and "glaze" in html and "drop test" in html


def test_wholesale_page_uses_packaging_and_moq():
    brief = _brief({"product": "paper box", "language": "English"})
    html = _writer("wholesale", brief)["html"].lower()
    assert "moq" in html and "packaging" in html and "dieline" in html


def test_export_page_uses_export_factors():
    brief = _brief({"product": "hydraulic fitting", "language": "English", "market": "Europe"})
    html = _writer("export", brief)["html"].lower()
    assert "europe" in html and "export documents" in html and "inspection" in html


def test_specs_page_uses_spec_dimensions():
    brief = _brief({"product": "industrial belt", "language": "English"})
    html = _writer("specifications", brief)["html"].lower()
    assert "belt width" in html and "tensile strength" in html and "ply count" in html


def test_faq_page_uses_faq_topics():
    brief = _brief({"product": "pet grooming brush", "language": "English"})
    html = _writer("faq", brief)["html"].lower()
    assert "moq" in html and "cleaning" in html and "custom" in html


def test_japanese_pipe_content_contains_japanese_industry_terms():
    brief = _brief({"product": "铁管", "language": "Japanese", "market": "Japan"})
    html = " ".join(_writer(page_type, brief)["html"] for page_type in (
        "supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq"
    ))
    for term in ("外径", "肉厚", "長さ", "亜鉛メッキ", "建築用途", "梱包", "MOQ", "輸出書類"):
        assert term in html


def test_spanish_ceramic_content_uses_localized_labels():
    brief = _brief({"product": "陶瓷杯", "language": "Spanish", "audience": "retail buyers"})
    html = _writer("supplier_guide", brief)["html"]
    for term in ("Capacidad", "Esmalte", "seguridad alimentaria", "personalización de logotipo", "caja de regalo"):
        assert term.lower() in html.lower()


def test_german_pet_content_uses_localized_labels():
    brief = _brief({"product": "宠物梳", "language": "German", "audience": "pet shop buyers"})
    page = _writer("wholesale", brief)
    assert "Verpackung" in page["html"] and "Angebot" in page["html"] and "Anfrage" in page["cta"]


def test_french_hydraulic_content_uses_localized_labels():
    brief = _brief({"product": "raccord hydraulique", "language": "French", "market": "Europe"})
    page = _writer("specifications", brief)
    assert "Spécifications" in page["title"] and "matériau" in page["html"].lower()


def test_weak_llm_content_is_reinforced_from_brief():
    assert importlib.util.find_spec("lib.page_content_writer") is not None
    from lib.page_content_writer import reinforce_page_content
    brief = _brief({"product": "hydraulic fitting", "language": "English"})
    generic = {
        "title": "Supplier and Manufacturing Scope",
        "meta_description": "A generic page.",
        "html": "<h1>Supplier and Manufacturing Scope</h1><p>Review manufacturing controls. Confirm commercial terms.</p>",
    }
    result = reinforce_page_content(generic, {"type": "supplier_guide"}, brief)
    assert "pressure rating" in result["html"].lower()
    assert "review manufacturing controls" not in result["html"].lower()


def test_strong_llm_content_is_preserved():
    assert importlib.util.find_spec("lib.page_content_writer") is not None
    from lib.page_content_writer import reinforce_page_content
    brief = _brief({"product": "hydraulic fitting", "language": "English"})
    strong = {
        "title": "Hydraulic Fitting Selection",
        "meta_description": "Hydraulic fitting guide for distributors.",
        "html": "<h1>Original expert copy</h1><p>Compare thread standard, pressure rating, sealing type, BSP, NPT, JIC, DIN, leakage risk and material grade.</p>",
    }
    result = reinforce_page_content(strong, {"type": "supplier_guide"}, brief)
    assert result["html"] == strong["html"]


def test_fallback_artifact_uses_industry_writer(tmp_path):
    from lib.generation_plan import build_generation_plan, render_fallback_artifacts
    intent = {
        "product": "陶瓷杯", "industry": "ceramic homeware", "language": "Spanish",
        "market": "Spain", "audience": "supermarket buyers",
    }
    pages = render_fallback_artifacts(tmp_path, intent, build_generation_plan(intent))
    assert len(pages) == 6
    combined = " ".join(page["html"] for page in pages)
    assert "Capacidad" in combined and "Esmalte" in combined and "caja de regalo" in combined
    assert "Supplier and Manufacturing Scope" not in combined
    assert all(("hero" in page["html"] and "article" in page["html"] and "footer" in page["html"]) for page in pages)


def test_normal_pipeline_reinforcement_uses_industry_brief():
    assert hasattr(__import__("run"), "_reinforce_page_contents_with_industry_brief")
    import run
    from lib.seo_engine.schemas import PageContent
    brief = _brief({"product": "hydraulic fitting", "language": "English", "market": "Europe"})
    page = PageContent(
        slug="hydraulic-fitting-supplier", page_type="supplier_guide",
        title="Supplier and Manufacturing Scope", meta_description="Generic supplier page.",
        body_html="<h1>Supplier and Manufacturing Scope</h1><p>Review manufacturing controls.</p>",
    )
    reinforced = run._reinforce_page_contents_with_industry_brief([page], brief)
    assert reinforced[0] is page
    assert "pressure rating" in page.body_html.lower()
    assert "review manufacturing controls" not in page.body_html.lower()


def test_generation_plan_titles_are_localized():
    from lib.generation_plan import build_generation_plan
    plan = build_generation_plan({"product": "铁管", "industry": "metal pipe", "language": "Japanese"})
    titles = " ".join(page["title"] for page in plan["pages"])
    assert "サプライヤー" in titles
    assert "メーカー" in titles
    assert "仕様" in titles
    assert "よくある質問" in titles


def test_complete_product_language_site_request_gets_b2b_content_default():
    from lib.intent_engine import empty_intent, is_intent_ready, merge_intent
    import lib.generation_plan as generation_plan
    intent = merge_intent(empty_intent(), "做一个宠物梳德语站")
    assert intent["product"] == "宠物梳"
    assert intent["language"] == "German"
    assert intent["audience"] is None
    assert hasattr(generation_plan, "apply_b2b_content_defaults")
    resolved = generation_plan.apply_b2b_content_defaults(intent)
    assert resolved["audience"] == "B2B buyers and distributors"
    assert is_intent_ready(resolved)


def test_output_src_not_modified():
    before = _tree_digest(ROOT / "output_src")
    brief = _brief({"product": "steel pipe", "language": "English"})
    for page_type in ("supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq"):
        _writer(page_type, brief)
    assert _tree_digest(ROOT / "output_src") == before


def test_static_not_modified():
    before = _tree_digest(ROOT / "static")
    brief = _brief({"product": "ceramic mug", "language": "Spanish"})
    _writer("supplier_guide", brief)
    assert _tree_digest(ROOT / "static") == before
