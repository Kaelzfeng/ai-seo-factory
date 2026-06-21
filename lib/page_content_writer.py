# -*- coding: utf-8 -*-
"""Brief-driven deterministic page copy and weak-content reinforcement."""

from __future__ import annotations

from html import escape

from lib.industry_brief import IndustryBrief
from lib.localization import (
    language_coverage_score,
    localize_cta,
    localize_page_title,
    localize_section_label,
    localize_sentence,
    localize_term,
    normalize_language,
)


GENERIC_BOILERPLATE = (
    "review manufacturing controls",
    "confirm commercial terms",
    "supplier and manufacturing scope",
    "wholesale and export requirements",
    "this b2b export guide helps buyers evaluate suppliers",
)


_COPY = {
    "English": {
        "titles": {
            "supplier_guide": "{product} Supplier and Sourcing Guide",
            "manufacturer": "{product} Manufacturer Capabilities",
            "wholesale": "{product} Wholesale and Bulk Ordering",
            "export": "{product} Export Distributor Program",
            "specifications": "{product} Specifications Buying Guide",
            "faq": "{product} B2B Buyer FAQ",
        },
        "sections": {
            "definition": "Product Definition and Buyer Fit", "specs": "Key Specifications",
            "applications": "Applications and Pre-purchase Checks", "production": "Production Capability",
            "materials": "Materials, Process and Customization", "quality": "Quality Control and Lead Time",
            "orders": "MOQ, Quotation and Payment", "packaging": "Bulk Packaging and Shipping",
            "market": "Target Market and Distributor Cooperation", "documents": "Export Documents and Compliance",
            "selection": "Specification and Material Selection", "inquiry": "Inspection and Inquiry Fields",
            "faq": "Buyer Questions",
        },
        "cta": "Send your {product} specification, target quantity and market to request a documented quotation.",
    },
    "Japanese": {
        "titles": {
            "supplier_guide": "{product} サプライヤー選定ガイド", "manufacturer": "{product} メーカー・生産能力",
            "wholesale": "{product} 卸売・大量注文ガイド", "export": "{product} 輸出・販売代理店ガイド",
            "specifications": "{product} 仕様・購買ガイド", "faq": "{product} B2B よくある質問",
        },
        "sections": {
            "definition": "製品定義と買い手", "specs": "主要仕様", "applications": "用途と発注前確認",
            "production": "生産能力", "materials": "材料・工程・カスタマイズ", "quality": "品質管理と納期",
            "orders": "MOQ・見積・支払条件", "packaging": "梱包と輸送", "market": "対象市場と代理店協力",
            "documents": "輸出書類・検査・適合性", "selection": "仕様・材質の選定",
            "inquiry": "検査基準と引合項目", "faq": "バイヤーの質問",
        },
        "cta": "{product} の仕様、数量、用途、納入市場を共有し、MOQ と輸出書類を含む見積をご依頼ください。",
    },
    "Spanish": {
        "titles": {
            "supplier_guide": "Guía de proveedores de {product}", "manufacturer": "Fabricante y capacidad de {product}",
            "wholesale": "Compra mayorista de {product}", "export": "Distribución y exportación de {product}",
            "specifications": "Especificaciones de compra de {product}", "faq": "Preguntas B2B sobre {product}",
        },
        "sections": {
            "definition": "Definición del producto y comprador", "specs": "Especificaciones clave",
            "applications": "Aplicaciones y confirmación previa", "production": "Capacidad de producción",
            "materials": "Materiales, proceso y personalización", "quality": "Control de calidad y plazo",
            "orders": "MOQ, cotización y pago", "packaging": "Embalaje y transporte mayorista",
            "market": "Mercado objetivo y distribuidores", "documents": "Documentos de exportación y cumplimiento",
            "selection": "Selección de especificaciones y materiales", "inquiry": "Inspección y datos de consulta",
            "faq": "Preguntas del comprador",
        },
        "cta": "Envíe la especificación, cantidad y mercado de {product} para solicitar una cotización documentada.",
    },
    "German": {
        "titles": {
            "supplier_guide": "Lieferantenleitfaden für {product}", "manufacturer": "Herstellerkapazitäten für {product}",
            "wholesale": "Großhandel und Mengenbestellung für {product}", "export": "Export und Vertrieb von {product}",
            "specifications": "Spezifikationsleitfaden für {product}", "faq": "B2B-Fragen zu {product}",
        },
        "sections": {
            "definition": "Produktdefinition und Käuferprofil", "specs": "Technische Spezifikationen",
            "applications": "Anwendungen und Auftragsprüfung", "production": "Produktionskapazität",
            "materials": "Material, Verfahren und Anpassung", "quality": "Qualitätskontrolle und Lieferzeit",
            "orders": "MOQ, Angebot und Zahlung", "packaging": "Verpackung und Versand",
            "market": "Zielmarkt und Vertriebspartner", "documents": "Exportdokumente und Konformität",
            "selection": "Spezifikations- und Materialauswahl", "inquiry": "Prüfung und Anfragedaten",
            "faq": "Fragen der Käufer",
        },
        "cta": "Senden Sie Spezifikation, Menge und Zielmarkt für {product}, um eine dokumentierte Anfrage zu starten.",
    },
    "French": {
        "titles": {
            "supplier_guide": "Guide fournisseur de {product}", "manufacturer": "Capacités du fabricant de {product}",
            "wholesale": "Commande en gros de {product}", "export": "Exportation et distribution de {product}",
            "specifications": "Spécifications d’achat de {product}", "faq": "FAQ B2B sur {product}",
        },
        "sections": {
            "definition": "Définition du produit et profil acheteur", "specs": "Spécifications clés",
            "applications": "Applications et contrôles avant commande", "production": "Capacité de production",
            "materials": "Choix du matériau, procédé et personnalisation", "quality": "Contrôle qualité et délai",
            "orders": "MOQ, devis et paiement", "packaging": "Emballage et expédition en gros",
            "market": "Marché cible et partenaires distributeurs", "documents": "Documents export et conformité",
            "selection": "Sélection des spécifications et du matériau", "inquiry": "Inspection et champs de demande",
            "faq": "Questions des acheteurs",
        },
        "cta": "Envoyez la spécification, la quantité et le marché de {product} pour demander un devis documenté.",
    },
}


def _clean(value, fallback="") -> str:
    text = str(value or "").strip()
    return fallback if not text or text.casefold() == "none" else text


def _page_type(page: dict) -> str:
    value = _clean(page.get("type") or page.get("page_type"), "supplier_guide").lower()
    aliases = {"supplier": "supplier_guide", "guide": "supplier_guide", "bulk": "wholesale", "specs": "specifications"}
    return aliases.get(value, value) if value in set(aliases) | {
        "supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq"
    } else "supplier_guide"


def _list(items, language="English") -> str:
    values = [localize_term(_clean(item), language) for item in items if _clean(item)]
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _paragraph(template_key: str, brief: IndustryBrief, **variables) -> str:
    values = {
        "product": brief.product,
        "buyer": brief.buyer_type,
        "market": brief.market,
        **variables,
    }
    return f"<p>{escape(localize_sentence(template_key, brief.language, values))}</p>"


def localized_page_title(brief: IndustryBrief, page_type: str) -> str:
    """Return a safe page title in the requested language."""
    normalized_type = _page_type({"type": page_type})
    return localize_page_title(
        normalized_type, brief.product, brief.language,
        market=brief.market, audience=brief.buyer_type,
    )


def _section(key: str, brief: IndustryBrief, items) -> str:
    label = localize_section_label(key, brief.language)
    return f"<h2>{escape(label)}</h2>" + _paragraph("section_intro", brief, label=label) + _list(items, brief.language)


def _body_for(page_type: str, brief: IndustryBrief) -> str:
    if page_type == "manufacturer":
        return (
            _section("production", brief, brief.purchase_factors + ["sample approval", "lead time", "batch capacity"])
            + _section("materials", brief, brief.materials + brief.customization_options)
            + _section("quality", brief, brief.quality_checks + brief.standards)
        )
    if page_type == "wholesale":
        return (
            _section("orders", brief, ["MOQ"] + brief.purchase_factors + ["payment terms", "lead time"])
            + _section("packaging", brief, brief.packaging_factors + brief.customization_options)
            + _section("documents", brief, brief.export_factors)
        )
    if page_type == "export":
        return (
            _section("market", brief, [brief.buyer_type, "territory planning", "replenishment"] + brief.applications)
            + _section("documents", brief, brief.export_factors + brief.standards + brief.quality_checks)
            + _section("quality", brief, brief.buyer_pain_points)
        )
    if page_type == "specifications":
        return (
            _section("selection", brief, brief.spec_dimensions + brief.materials + brief.applications)
            + _section("inquiry", brief, brief.standards + brief.quality_checks)
            + _section("orders", brief, brief.spec_dimensions + ["quantity", "target application", "delivery market"])
        )
    if page_type == "faq":
        questions = []
        for topic in brief.faq_topics:
            questions.append(
                f"<h3>{escape(brief.product)}: {escape(localize_term(topic, brief.language))}?</h3>"
                + _paragraph("faq_answer", brief, topic=localize_term(topic, brief.language))
            )
        questions.append(_paragraph("faq_summary", brief))
        return f"<h2>{escape(localize_section_label('faq', brief.language))}</h2>" + "".join(questions)
    return (
        _section("definition", brief, brief.content_angles)
        + _section("specs", brief, brief.spec_dimensions + brief.materials + brief.standards + brief.quality_checks)
        + _section(
            "applications", brief,
            brief.applications + brief.purchase_factors + brief.buyer_pain_points
            + brief.customization_options + brief.packaging_factors,
        )
    )


def write_page_content(page: dict, brief: IndustryBrief) -> dict:
    """Create one information-dense page directly from an IndustryBrief."""
    page_type = _page_type(page or {})
    language = normalize_language(brief.language)
    brief.language = language
    product = _clean(brief.product, "B2B product")
    title = localized_page_title(brief, page_type)
    cta = localize_cta(language, product)
    intro = _paragraph("intro", brief)
    business_context = _paragraph("business_context", brief)
    body = (
        f"<h1>{escape(title)}</h1>" + intro + business_context
        + _body_for(page_type, brief)
        + f"<blockquote>{escape(cta)}</blockquote>"
    )
    meta = localize_sentence("meta", language, {
        "title": title, "product": product, "market": brief.market,
        "summary": localize_sentence("business_context", language, {"product": product, "market": brief.market}),
    })
    return {
        "title": title,
        "meta_description": meta[:160],
        "html": body,
        "body_html": body,
        "cta": cta,
        "page_type": page_type,
    }


def industry_term_hits(content, brief: IndustryBrief) -> list[str]:
    text = _clean(content).casefold()
    return [term for term in brief.all_terms() if term.casefold() in text]


def contains_generic_boilerplate(content) -> bool:
    text = _clean(content).casefold()
    return any(phrase in text for phrase in GENERIC_BOILERPLATE)


def needs_industry_reinforcement(content: dict, brief: IndustryBrief, minimum_terms: int = 5) -> bool:
    html = _clean((content or {}).get("html") or (content or {}).get("body_html"))
    wrong_language = normalize_language(brief.language) != "English" and language_coverage_score(html, brief.language) < 0.45
    return contains_generic_boilerplate(html) or len(industry_term_hits(html, brief)) < minimum_terms or wrong_language


def reinforce_page_content(content: dict, page: dict, brief: IndustryBrief) -> dict:
    """Preserve strong copy; replace weak/generic copy with deterministic brief copy."""
    original = dict(content or {})
    if not needs_industry_reinforcement(original, brief):
        return original
    replacement = write_page_content(page or {}, brief)
    if "body_html" in original and "html" not in original:
        replacement["body_html"] = replacement["html"]
    return replacement
