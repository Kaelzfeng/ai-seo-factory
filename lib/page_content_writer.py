# -*- coding: utf-8 -*-
"""Brief-driven deterministic page copy and weak-content reinforcement."""

from __future__ import annotations

from html import escape

from lib.industry_brief import IndustryBrief


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


def _lang(brief: IndustryBrief) -> dict:
    return _COPY.get(brief.language) or _COPY["English"]


def _list(items) -> str:
    values = [_clean(item) for item in items if _clean(item)]
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _sentence(product: str, lead: str, items) -> str:
    values = ", ".join(_clean(item) for item in items if _clean(item))
    return f"<p>{escape(product)} — {escape(lead)}: {escape(values)}.</p>"


def _localized_terms(brief: IndustryBrief) -> str:
    industry = brief.industry.casefold()
    language = brief.language
    terms = []
    if language == "Japanese" and "pipe" in industry:
        terms = ["外径 (outer diameter)", "肉厚 (wall thickness)", "長さ (length)", "亜鉛メッキ (galvanized steel)",
                 "建築用途 (construction)", "梱包 (packaging)", "MOQ", "輸出書類 (export documents)"]
    elif language == "Spanish" and "ceramic" in industry:
        terms = ["Capacidad (capacity)", "Esmalte (glaze)", "seguridad alimentaria (food contact safety)",
                 "personalización de logotipo (logo customization)", "caja de regalo (gift box)", "compra minorista"]
    elif language == "German" and "pet" in industry:
        terms = ["Tiergröße (pet size)", "Materialsicherheit (material safety)", "Reinigung (cleaning method)",
                 "Haltbarkeit (durability)", "Verpackung für den Einzelhandel (retail packaging)"]
    elif language == "French" and "hydraulic" in industry:
        terms = ["norme de filetage (thread standard)", "pression nominale (pressure rating)",
                 "type d’étanchéité (sealing type)", "qualité du matériau (material grade)"]
    return _list(terms) if terms else ""


def localized_page_title(brief: IndustryBrief, page_type: str) -> str:
    """Return a safe page title in the requested language."""
    normalized_type = _page_type({"type": page_type})
    product = _clean(brief.product, "B2B product")
    return _lang(brief)["titles"][normalized_type].format(product=product)


def _body_for(page_type: str, brief: IndustryBrief, labels: dict) -> str:
    p = brief.product
    if page_type == "manufacturer":
        return (
            f"<h2>{labels['production']}</h2>"
            + _sentence(p, "production planning for buyer volume and lead time", brief.purchase_factors)
            + f"<h2>{labels['materials']}</h2>" + _list(brief.materials + brief.customization_options)
            + f"<h2>{labels['quality']}</h2>" + _list(brief.quality_checks + brief.standards)
            + _sentence(p, "capacity confirmation before production", ["sample approval", "lead time", "batch capacity"])
        )
    if page_type == "wholesale":
        return (
            f"<h2>{labels['orders']}</h2>"
            + _sentence(p, "wholesale quotation factors", ["MOQ"] + brief.purchase_factors + ["payment terms", "lead time"])
            + f"<h2>{labels['packaging']}</h2>" + _list(brief.packaging_factors + brief.customization_options)
            + _sentence(p, "shipment planning", brief.export_factors)
        )
    if page_type == "export":
        return (
            f"<h2>{labels['market']}</h2>"
            + _sentence(p, f"distributor cooperation for {brief.market}", [brief.buyer_type, "territory planning", "replenishment"])
            + f"<h2>{labels['documents']}</h2>" + _list(brief.export_factors + brief.standards + brief.quality_checks)
            + _sentence(p, "after-sales and replenishment controls", brief.buyer_pain_points)
        )
    if page_type == "specifications":
        return (
            f"<h2>{labels['selection']}</h2>" + _list(brief.spec_dimensions + brief.materials + brief.applications)
            + f"<h2>{labels['inquiry']}</h2>" + _list(brief.standards + brief.quality_checks)
            + _sentence(p, "inquiry fields", brief.spec_dimensions + ["quantity", "target application", "delivery market"])
        )
    if page_type == "faq":
        questions = []
        for topic in brief.faq_topics:
            questions.append(
                f"<h3>{escape(p)}: {escape(topic)}?</h3>"
                f"<p>Confirm {escape(topic)} with the sample, quotation and purchase specification before bulk production.</p>"
            )
        questions.append(
            f"<h3>MOQ, packaging, lead time, certification and custom options?</h3>"
            f"<p>State the {escape(p)} quantity, packaging format, required documents and customization scope in one inquiry.</p>"
        )
        return f"<h2>{labels['faq']}</h2>" + "".join(questions)
    return (
        f"<h2>{labels['definition']}</h2>"
        + _sentence(p, f"defined for {brief.buyer_type} in {brief.market}", brief.content_angles)
        + f"<h2>{labels['specs']}</h2>" + _list(brief.spec_dimensions + brief.materials + brief.standards)
        + f"<h2>{labels['applications']}</h2>" + _list(brief.applications + brief.purchase_factors + brief.buyer_pain_points)
    )


def write_page_content(page: dict, brief: IndustryBrief) -> dict:
    """Create one information-dense page directly from an IndustryBrief."""
    page_type = _page_type(page or {})
    localized = _lang(brief)
    product = _clean(brief.product, "B2B product")
    title = localized_page_title(brief, page_type)
    cta = localized["cta"].format(product=product)
    intro = (
        f"<p>{escape(product)} is evaluated by {escape(brief.buyer_type)} for "
        f"{escape(brief.market)} through product-specific specifications, application fit and documented quality evidence.</p>"
    )
    body = (
        f"<h1>{escape(title)}</h1>" + intro + _localized_terms(brief)
        + _body_for(page_type, brief, localized["sections"])
        + f"<blockquote>{escape(cta)}</blockquote>"
    )
    meta = f"{title}: {', '.join(brief.spec_dimensions[:3])}, {brief.market}, MOQ and documented B2B sourcing."
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
    return contains_generic_boilerplate(html) or len(industry_term_hits(html, brief)) < minimum_terms


def reinforce_page_content(content: dict, page: dict, brief: IndustryBrief) -> dict:
    """Preserve strong copy; replace weak/generic copy with deterministic brief copy."""
    original = dict(content or {})
    if not needs_industry_reinforcement(original, brief):
        return original
    replacement = write_page_content(page or {}, brief)
    if "body_html" in original and "html" not in original:
        replacement["body_html"] = replacement["html"]
    return replacement
