# -*- coding: utf-8 -*-
"""Shared multilingual presentation rules for industry-aware content.

IndustryBrief owns *what* should be said.  This module owns *how* the same
fields are expressed in the requested language.  It deliberately contains no
industry classifier and performs no network or model calls.
"""

from __future__ import annotations

from html import unescape
import re


PAGE_TYPES = ("supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq")
SECTION_KEYS = (
    "definition", "specs", "applications", "production", "materials", "quality",
    "orders", "packaging", "market", "documents", "selection", "inquiry", "faq",
)


def _pack(titles, sections, site, cta, intro, business, section_intro, faq_answer, faq_summary, coverage):
    return {
        "titles": dict(zip(PAGE_TYPES, titles)),
        "sections": dict(zip(SECTION_KEYS, sections)),
        "site": site,
        "cta": cta,
        "sentences": {
            "intro": intro,
            "business_context": business,
            "section_intro": section_intro,
            "faq_answer": faq_answer,
            "faq_summary": faq_summary,
            "meta": "{title} — {market}. {summary}",
            "site_sub": business,
        },
        "coverage": coverage,
    }


_PACKS = {
    "English": _pack(
        ("{product} Supplier and Sourcing Guide", "{product} Manufacturer Capabilities", "{product} Wholesale and Bulk Ordering", "{product} Export Distributor Program", "{product} Specifications Buying Guide", "{product} B2B Buyer FAQ"),
        ("Product Definition and Buyer Fit", "Key Specifications", "Applications and Pre-purchase Checks", "Production Capability", "Materials, Process and Customization", "Quality Control and Lead Time", "MOQ, Quotation and Payment", "Bulk Packaging and Shipping", "Target Market and Distributor Cooperation", "Export Documents and Compliance", "Specification and Material Selection", "Inspection and Inquiry Fields", "Buyer Questions"),
        "{product} B2B Export Site", "Send the {product} specifications, quantity and target market to request a documented quotation.",
        "This guide helps {buyer} evaluate {product} for {market} using application requirements and documented evidence.",
        "Buyers can compare specifications, packaging, export terms, quality, wholesale quantities and quotation details before ordering.",
        "For {label}, confirm the following product-specific fields with the supplier.",
        "Confirm {topic} against the sample, quotation and purchase specification before bulk production.",
        "State quantity, packaging, lead time, certification and customization requirements in one inquiry.",
        ("buyers", "specifications", "packaging", "export", "quotation", "quality"),
    ),
    "Japanese": _pack(
        ("{product} サプライヤー選定ガイド", "{product} メーカー・生産能力", "{product} 卸売・大量注文ガイド", "{product} 輸出・販売代理店ガイド", "{product} 仕様・購買ガイド", "{product} B2B よくある質問"),
        ("製品定義とバイヤー適合", "主要仕様", "用途と発注前確認", "生産能力", "材料・工程・カスタマイズ", "品質確認と納期", "MOQ・見積・支払条件", "梱包と輸送", "対象市場と販売協力", "輸出書類と適合性", "仕様・材質の選定", "検査基準と引合項目", "バイヤーの質問"),
        "{product} B2B 輸出サイト", "{product} の仕様、数量、用途、納入市場を共有し、MOQ と輸出書類を含む見積をご依頼ください。",
        "このガイドは、{buyer} が {market} 向けの {product} を用途、仕様、品質確認資料に基づいて調達するための情報です。",
        "バイヤーは、仕様、梱包、輸出条件、見積、納期、品質確認を比較してから卸売発注を判断できます。",
        "{label} について、次の製品固有項目をサプライヤーと確認してください。",
        "量産前に、{topic} をサンプル、見積、購買仕様書で確認してください。",
        "数量、梱包、納期、認証、カスタマイズ条件を一つの調達依頼に記載してください。",
        ("仕様", "梱包", "輸出", "見積", "バイヤー", "調達", "納期", "品質確認"),
    ),
    "Korean": _pack(
        ("{product} 공급업체 선정 가이드", "{product} 제조 역량", "{product} 도매 및 대량 주문", "{product} 수출 유통 프로그램", "{product} 사양 구매 가이드", "{product} B2B 구매자 FAQ"),
        ("제품 정의와 구매자 적합성", "핵심 사양", "용도와 주문 전 확인", "생산 능력", "소재·공정·맞춤화", "품질 관리와 납기", "MOQ·견적·결제", "포장과 운송", "목표 시장과 유통 협력", "수출 서류와 규정", "사양 및 소재 선택", "검사와 문의 항목", "구매자 질문"),
        "{product} B2B 수출 사이트", "{product} 사양, 수량, 목표 시장을 보내 문서화된 견적을 요청하세요.",
        "이 가이드는 {buyer}가 {market}용 {product}를 사양과 품질 자료로 평가하도록 돕습니다.",
        "구매자는 사양, 포장, 수출 조건, 견적, 납기와 품질을 비교한 뒤 도매 주문을 결정할 수 있습니다.",
        "{label}에 대해 다음 제품별 항목을 공급업체와 확인하세요.",
        "대량 생산 전에 샘플, 견적서와 구매 사양서로 {topic}을 확인하세요.",
        "수량, 포장, 납기, 인증과 맞춤 조건을 한 번의 문의에 기재하세요.",
        ("구매자", "사양", "포장", "수출", "견적", "품질"),
    ),
    "German": _pack(
        ("Lieferantenleitfaden für {product}", "Herstellerkapazitäten für {product}", "Großhandel und Mengenbestellung für {product}", "Export und Vertrieb von {product}", "Spezifikationsleitfaden für {product}", "B2B-Fragen zu {product}"),
        ("Produktdefinition und Käuferprofil", "Technische Spezifikationen", "Anwendungen und Auftragsprüfung", "Produktionskapazität", "Material, Verfahren und Anpassung", "Qualität und Lieferzeit", "MOQ, Angebot und Zahlung", "Verpackung und Versand", "Zielmarkt und Vertriebspartner", "Exportdokumente und Konformität", "Spezifikations- und Materialauswahl", "Prüfung und Anfragedaten", "Fragen der Käufer"),
        "{product} B2B-Exportseite", "Senden Sie Spezifikationen, Menge und Zielmarkt für {product}, um mit einer dokumentierten Anfrage ein Angebot anzufordern.",
        "Dieser Leitfaden hilft {buyer}, {product} für {market} anhand von Einsatz, Spezifikationen und Qualitätsnachweisen zu bewerten.",
        "Käufer vergleichen Spezifikationen, Verpackung, Exportbedingungen, Lieferzeit, Großhandel, Angebot und Qualität vor der Bestellung.",
        "Für {label} sind die folgenden produktspezifischen Angaben mit dem Lieferanten zu bestätigen.",
        "Prüfen Sie {topic} vor der Serienfertigung anhand von Muster, Angebot und Einkaufsspezifikation.",
        "Geben Sie Menge, Verpackung, Lieferzeit, Zertifizierung und Anpassung in einer Anfrage an.",
        ("Käufer", "Spezifikationen", "Verpackung", "Lieferzeit", "Großhandel", "Angebot", "Qualität"),
    ),
    "French": _pack(
        ("Guide fournisseur de {product}", "Capacités du fabricant de {product}", "Commande en gros de {product}", "Exportation et distribution de {product}", "Spécifications d’achat de {product}", "FAQ B2B sur {product}"),
        ("Définition du produit et profil acheteur", "Spécifications clés", "Applications et contrôles avant commande", "Capacité de production", "Matériaux, procédé et personnalisation", "Qualité et délai", "MOQ, devis et paiement", "Emballage et expédition", "Marché cible et distributeurs", "Documents export et conformité", "Choix des spécifications et matériaux", "Inspection et données de demande", "Questions des acheteurs"),
        "Site d’export B2B de {product}", "Envoyez les spécifications, la quantité et le marché de {product} pour demander un devis documenté.",
        "Ce guide aide les {buyer} à évaluer {product} pour {market} selon les usages, les spécifications et les preuves qualité.",
        "Les acheteurs comparent spécifications, emballage, distribution, devis, commande en gros, délai et qualité avant l’achat.",
        "Pour {label}, confirmez avec le fournisseur les données propres au produit ci-dessous.",
        "Avant la production en série, vérifiez {topic} avec l’échantillon, le devis et le cahier des charges.",
        "Indiquez quantité, emballage, délai, certification et personnalisation dans une seule demande.",
        ("acheteurs", "spécifications", "emballage", "distribution", "devis", "commande en gros", "qualité"),
    ),
    "Spanish": _pack(
        ("Guía de proveedores de {product}", "Capacidad del fabricante de {product}", "Pedidos al por mayor de {product}", "Exportación y distribución de {product}", "Especificaciones de compra de {product}", "Preguntas B2B sobre {product}"),
        ("Definición del producto y comprador", "Especificaciones clave", "Aplicaciones y revisión previa", "Capacidad de producción", "Materiales, proceso y personalización", "Calidad y plazo de entrega", "MOQ, cotización y pago", "Embalaje y transporte", "Mercado objetivo y distribuidores", "Documentos de exportación y cumplimiento", "Selección de especificaciones y materiales", "Inspección y datos de consulta", "Preguntas de compradores"),
        "Sitio B2B de exportación de {product}", "Envíe las especificaciones, cantidad y mercado de {product} para solicitar una cotización documentada.",
        "Esta guía permite a los {buyer} evaluar {product} para {market} según su aplicación, especificaciones y evidencia de calidad.",
        "Los compradores comparan proveedores, especificaciones, embalaje, distribución, cotización, pedidos al por mayor y calidad antes de comprar.",
        "Para {label}, confirme con el proveedor los siguientes datos específicos del producto.",
        "Antes de la producción en serie, confirme {topic} mediante la muestra, la cotización y la especificación de compra.",
        "Indique cantidad, embalaje, plazo, certificación y personalización en una sola consulta.",
        ("proveedores", "compradores", "especificaciones", "embalaje", "distribución", "cotización", "pedidos al por mayor"),
    ),
    "Portuguese": _pack(
        ("Guia de fornecedores de {product}", "Capacidade do fabricante de {product}", "Atacado e pedidos em volume de {product}", "Exportação e distribuição de {product}", "Especificações de compra de {product}", "Perguntas B2B sobre {product}"),
        ("Definição do produto e perfil do comprador", "Especificações principais", "Aplicações e revisão antes do pedido", "Capacidade de produção", "Materiais, processo e personalização", "Qualidade e prazo", "MOQ, cotação e pagamento", "Embalagem e transporte", "Mercado-alvo e distribuidores", "Documentos de exportação e conformidade", "Seleção de especificações e materiais", "Inspeção e dados da consulta", "Perguntas dos compradores"),
        "Site B2B de exportação de {product}", "Envie especificações, quantidade e mercado de {product} para solicitar uma cotação documentada.",
        "Este guia ajuda os {buyer} a avaliar {product} para {market} segundo aplicação, especificações e evidências de qualidade.",
        "Os compradores comparam especificações, embalagem, distribuição, cotação, atacado, prazo e qualidade antes do pedido.",
        "Para {label}, confirme com o fornecedor os seguintes dados específicos do produto.",
        "Antes da produção em volume, confirme {topic} com a amostra, a cotação e a especificação de compra.",
        "Informe quantidade, embalagem, prazo, certificação e personalização em uma única consulta.",
        ("compradores", "especificações", "embalagem", "distribuição", "cotação", "atacado", "qualidade"),
    ),
    "Italian": _pack(
        ("Guida ai fornitori di {product}", "Capacità del produttore di {product}", "Ingrosso e ordini di {product}", "Esportazione e distribuzione di {product}", "Specifiche di acquisto di {product}", "FAQ B2B su {product}"),
        ("Definizione del prodotto e acquirenti", "Specifiche principali", "Applicazioni e verifica preordine", "Capacità produttiva", "Materiali, processo e personalizzazione", "Qualità e tempi di consegna", "MOQ, preventivo e pagamento", "Imballaggio e spedizione", "Mercato e distributori", "Documenti export e conformità", "Scelta di specifiche e materiali", "Ispezione e dati richiesta", "Domande degli acquirenti"),
        "Sito export B2B di {product}", "Invia specifiche, quantità e mercato di {product} per richiedere un preventivo documentato.",
        "Questa guida aiuta gli {buyer} a valutare {product} per {market} tramite applicazioni, specifiche e prove di qualità.",
        "Gli acquirenti confrontano specifiche, imballaggio, esportazione, preventivo, ingrosso, consegna e qualità.",
        "Per {label}, conferma con il fornitore i seguenti dati specifici del prodotto.",
        "Prima della produzione, verifica {topic} con campione, preventivo e specifica di acquisto.",
        "Indica quantità, imballaggio, consegna, certificazione e personalizzazione in una richiesta.",
        ("acquirenti", "specifiche", "imballaggio", "esportazione", "preventivo", "qualità"),
    ),
    "Russian": _pack(
        ("Руководство по поставщикам {product}", "Возможности производителя {product}", "Оптовые заказы {product}", "Экспорт и дистрибуция {product}", "Спецификации для закупки {product}", "B2B вопросы о {product}"),
        ("Описание продукта и покупателя", "Основные спецификации", "Применение и проверка заказа", "Производственные возможности", "Материалы и персонализация", "Качество и срок поставки", "MOQ, предложение и оплата", "Упаковка и доставка", "Целевой рынок и дистрибьюторы", "Экспортные документы", "Выбор спецификации и материала", "Проверка и данные запроса", "Вопросы покупателей"),
        "B2B экспорт {product}", "Отправьте спецификации, количество и рынок {product}, чтобы запросить документированное предложение.",
        "Руководство помогает покупателям оценить {product} для {market} по применению, спецификациям и данным качества.",
        "Покупатели сравнивают спецификации, упаковку, экспорт, предложение, оптовые условия, сроки и качество.",
        "Для раздела «{label}» подтвердите у поставщика следующие данные продукта.",
        "До серийного производства проверьте {topic} по образцу, предложению и закупочной спецификации.",
        "Укажите количество, упаковку, сроки, сертификацию и персонализацию в одном запросе.",
        ("покупатели", "спецификации", "упаковка", "экспорт", "предложение", "качество"),
    ),
    "Arabic": _pack(
        ("دليل موردي {product}", "قدرات مصنّعي {product}", "طلبات الجملة من {product}", "تصدير وتوزيع {product}", "دليل مواصفات شراء {product}", "أسئلة مشتري {product}"),
        ("تعريف المنتج وملاءمة المشترين", "المواصفات الرئيسية", "الاستخدامات وفحص الطلب", "القدرة الإنتاجية", "المواد والتخصيص", "الجودة ووقت التسليم", "MOQ وعرض السعر والدفع", "التغليف والشحن", "السوق والموزعين", "وثائق التصدير والامتثال", "اختيار المواصفات والمواد", "الفحص وبيانات الاستفسار", "أسئلة المشترين"),
        "موقع تصدير B2B لمنتج {product}", "أرسل مواصفات {product} والكمية والسوق لطلب عرض سعر موثق.",
        "يساعد هذا الدليل {buyer} على تقييم {product} لسوق {market} وفق الاستخدام والمواصفات وأدلة الجودة.",
        "يقارن المشترين بين المواصفات والتغليف والتصدير والموزعين وعرض سعر وطلبات الجملة والجودة قبل الشراء.",
        "بالنسبة إلى {label}، أكد بيانات المنتج التالية مع المورد.",
        "قبل الإنتاج الكمي، تحقق من {topic} باستخدام العينة وعرض السعر ومواصفات الشراء.",
        "حدد الكمية والتغليف ووقت التسليم والشهادات والتخصيص في استفسار واحد.",
        ("المواصفات", "التغليف", "التصدير", "المشترين", "الموزعين", "عرض سعر", "الجودة"),
    ),
    "Vietnamese": _pack(
        ("Hướng dẫn nhà cung cấp {product}", "Năng lực nhà sản xuất {product}", "Đơn hàng bán buôn {product}", "Xuất khẩu và phân phối {product}", "Hướng dẫn thông số {product}", "Câu hỏi B2B về {product}"),
        ("Định nghĩa sản phẩm và người mua", "Thông số chính", "Ứng dụng và kiểm tra trước đơn hàng", "Năng lực sản xuất", "Chất liệu và tùy chỉnh", "Chất lượng và thời gian giao", "MOQ, báo giá và thanh toán", "Đóng gói và vận chuyển", "Thị trường và nhà phân phối", "Chứng từ xuất khẩu", "Chọn thông số và chất liệu", "Kiểm tra và dữ liệu yêu cầu", "Câu hỏi của người mua"),
        "Trang xuất khẩu B2B {product}", "Gửi thông số, số lượng và thị trường của {product} để yêu cầu báo giá có tài liệu.",
        "Hướng dẫn này giúp người mua đánh giá {product} cho {market} theo ứng dụng, thông số và bằng chứng chất lượng.",
        "Người mua so sánh thông số, chất liệu, đóng gói, xuất khẩu, báo giá, thời gian giao và chất lượng trước khi đặt hàng.",
        "Với {label}, hãy xác nhận các dữ liệu riêng của sản phẩm sau với nhà cung cấp.",
        "Trước khi sản xuất số lượng lớn, xác nhận {topic} bằng mẫu, báo giá và thông số mua hàng.",
        "Nêu số lượng, đóng gói, thời gian giao, chứng nhận và tùy chỉnh trong một yêu cầu.",
        ("thông số", "đóng gói", "xuất khẩu", "người mua", "báo giá", "chất lượng"),
    ),
    "Thai": _pack(
        ("คู่มือซัพพลายเออร์ {product}", "ความสามารถผู้ผลิต {product}", "การสั่งซื้อส่ง {product}", "การส่งออกและจัดจำหน่าย {product}", "คู่มือข้อมูลจำเพาะ {product}", "คำถาม B2B เกี่ยวกับ {product}"),
        ("คำจำกัดความสินค้าและผู้ซื้อ", "ข้อมูลจำเพาะหลัก", "การใช้งานและตรวจสอบก่อนสั่ง", "กำลังการผลิต", "วัสดุและการปรับแต่ง", "คุณภาพและระยะเวลาส่งมอบ", "MOQ ใบเสนอราคาและการชำระเงิน", "บรรจุภัณฑ์และขนส่ง", "ตลาดและผู้จัดจำหน่าย", "เอกสารส่งออก", "การเลือกข้อมูลจำเพาะและวัสดุ", "การตรวจสอบและข้อมูลสอบถาม", "คำถามของผู้ซื้อ"),
        "เว็บไซต์ส่งออก B2B {product}", "ส่งข้อมูลจำเพาะ จำนวน และตลาดของ {product} เพื่อขอใบเสนอราคาพร้อมเอกสาร",
        "คู่มือนี้ช่วยผู้ซื้อประเมิน {product} สำหรับ {market} จากการใช้งาน ข้อมูลจำเพาะ และหลักฐานคุณภาพ",
        "ผู้ซื้อเปรียบเทียบข้อมูลจำเพาะ บรรจุภัณฑ์ ส่งออก ใบเสนอราคา ค้าส่ง ระยะเวลาส่งมอบ และคุณภาพก่อนสั่งซื้อ",
        "สำหรับ {label} โปรดยืนยันข้อมูลเฉพาะสินค้าต่อไปนี้กับซัพพลายเออร์",
        "ก่อนผลิตจำนวนมาก ให้ตรวจสอบ {topic} จากตัวอย่าง ใบเสนอราคา และข้อกำหนดการซื้อ",
        "ระบุจำนวน บรรจุภัณฑ์ ระยะเวลาส่งมอบ การรับรอง และการปรับแต่งในคำขอเดียว",
        ("ข้อมูลจำเพาะ", "บรรจุภัณฑ์", "ส่งออก", "ผู้ซื้อ", "ใบเสนอราคา", "คุณภาพ"),
    ),
    "Indonesian": _pack(
        ("Panduan pemasok {product}", "Kemampuan produsen {product}", "Pesanan grosir {product}", "Ekspor dan distribusi {product}", "Panduan spesifikasi {product}", "FAQ B2B {product}"),
        ("Definisi produk dan pembeli", "Spesifikasi utama", "Aplikasi dan pemeriksaan pesanan", "Kapasitas produksi", "Bahan dan kustomisasi", "Kualitas dan waktu pengiriman", "MOQ, penawaran dan pembayaran", "Kemasan dan pengiriman", "Pasar dan distributor", "Dokumen ekspor", "Pemilihan spesifikasi dan bahan", "Inspeksi dan data permintaan", "Pertanyaan pembeli"),
        "Situs ekspor B2B {product}", "Kirim spesifikasi, jumlah, dan pasar {product} untuk meminta penawaran terdokumentasi.",
        "Panduan ini membantu pembeli menilai {product} untuk {market} berdasarkan aplikasi, spesifikasi, dan bukti kualitas.",
        "Pembeli membandingkan spesifikasi, kemasan, ekspor, penawaran, grosir, waktu pengiriman, dan kualitas sebelum memesan.",
        "Untuk {label}, konfirmasikan data khusus produk berikut dengan pemasok.",
        "Sebelum produksi massal, periksa {topic} melalui sampel, penawaran, dan spesifikasi pembelian.",
        "Cantumkan jumlah, kemasan, waktu pengiriman, sertifikasi, dan kustomisasi dalam satu permintaan.",
        ("spesifikasi", "kemasan", "ekspor", "pembeli", "penawaran", "kualitas"),
    ),
    "Malay": _pack(
        ("Panduan pembekal {product}", "Keupayaan pengilang {product}", "Pesanan borong {product}", "Eksport dan pengedaran {product}", "Panduan spesifikasi {product}", "Soalan B2B {product}"),
        ("Definisi produk dan pembeli", "Spesifikasi utama", "Aplikasi dan semakan pesanan", "Kapasiti pengeluaran", "Bahan dan penyesuaian", "Kualiti dan masa penghantaran", "MOQ, sebut harga dan bayaran", "Pembungkusan dan penghantaran", "Pasaran dan pengedar", "Dokumen eksport", "Pemilihan spesifikasi dan bahan", "Pemeriksaan dan data pertanyaan", "Soalan pembeli"),
        "Laman eksport B2B {product}", "Hantar spesifikasi, kuantiti dan pasaran {product} untuk meminta sebut harga berdokumen.",
        "Panduan ini membantu pembeli menilai {product} untuk {market} berdasarkan aplikasi, spesifikasi dan bukti kualiti.",
        "Pembeli membandingkan spesifikasi, pembungkusan, eksport, sebut harga, borong, penghantaran dan kualiti.",
        "Bagi {label}, sahkan data khusus produk berikut dengan pembekal.",
        "Sebelum pengeluaran pukal, semak {topic} melalui sampel, sebut harga dan spesifikasi pembelian.",
        "Nyatakan kuantiti, pembungkusan, penghantaran, pensijilan dan penyesuaian dalam satu pertanyaan.",
        ("pembeli", "spesifikasi", "pembungkusan", "eksport", "sebut harga", "kualiti"),
    ),
    "Dutch": _pack(
        ("Leveranciersgids voor {product}", "Productiecapaciteit voor {product}", "Groothandel in {product}", "Export en distributie van {product}", "Specificatiegids voor {product}", "B2B-vragen over {product}"),
        ("Productdefinitie en koper", "Belangrijkste specificaties", "Toepassingen en ordercontrole", "Productiecapaciteit", "Materialen en maatwerk", "Kwaliteit en levertijd", "MOQ, offerte en betaling", "Verpakking en verzending", "Markt en distributeurs", "Exportdocumenten", "Keuze van specificaties en materiaal", "Inspectie en aanvraaggegevens", "Vragen van kopers"),
        "B2B-exportsite voor {product}", "Stuur specificaties, hoeveelheid en markt van {product} voor een gedocumenteerde offerte.",
        "Deze gids helpt kopers {product} voor {market} te beoordelen op toepassing, specificaties en kwaliteitsbewijs.",
        "Kopers vergelijken specificaties, verpakking, export, offerte, groothandel, levertijd en kwaliteit.",
        "Bevestig voor {label} de volgende productspecifieke gegevens met de leverancier.",
        "Controleer {topic} vóór bulkproductie met monster, offerte en inkoopspecificatie.",
        "Vermeld hoeveelheid, verpakking, levertijd, certificering en maatwerk in één aanvraag.",
        ("kopers", "specificaties", "verpakking", "export", "offerte", "kwaliteit"),
    ),
    "Turkish": _pack(
        ("{product} tedarikçi rehberi", "{product} üretici kapasitesi", "{product} toptan sipariş", "{product} ihracat ve dağıtım", "{product} teknik özellik rehberi", "{product} B2B soruları"),
        ("Ürün tanımı ve alıcı", "Temel teknik özellikler", "Uygulama ve sipariş kontrolü", "Üretim kapasitesi", "Malzeme ve özelleştirme", "Kalite ve teslim süresi", "MOQ, teklif ve ödeme", "Ambalaj ve sevkiyat", "Pazar ve distribütörler", "İhracat belgeleri", "Özellik ve malzeme seçimi", "Muayene ve talep verileri", "Alıcı soruları"),
        "{product} B2B ihracat sitesi", "Belgeli teklif için {product} özelliklerini, miktarı ve pazarı gönderin.",
        "Bu rehber, alıcıların {product} ürününü {market} için kullanım, teknik özellik ve kalite kanıtıyla değerlendirmesine yardımcı olur.",
        "Alıcılar siparişten önce özellik, ambalaj, ihracat, teklif, toptan koşullar, teslim ve kaliteyi karşılaştırır.",
        "{label} için aşağıdaki ürüne özel verileri tedarikçiyle doğrulayın.",
        "Seri üretimden önce {topic} bilgisini numune, teklif ve satın alma şartnamesiyle doğrulayın.",
        "Miktar, ambalaj, teslim, sertifika ve özelleştirmeyi tek talepte belirtin.",
        ("alıcılar", "teknik özellik", "ambalaj", "ihracat", "teklif", "kalite"),
    ),
    "Polish": _pack(
        ("Przewodnik dostawców {product}", "Możliwości producenta {product}", "Zamówienia hurtowe {product}", "Eksport i dystrybucja {product}", "Specyfikacje zakupowe {product}", "Pytania B2B o {product}"),
        ("Definicja produktu i nabywca", "Kluczowe specyfikacje", "Zastosowanie i kontrola zamówienia", "Możliwości produkcyjne", "Materiały i personalizacja", "Jakość i termin dostawy", "MOQ, wycena i płatność", "Opakowanie i wysyłka", "Rynek i dystrybutorzy", "Dokumenty eksportowe", "Wybór specyfikacji i materiału", "Kontrola i dane zapytania", "Pytania nabywców"),
        "Strona eksportowa B2B {product}", "Prześlij specyfikacje, ilość i rynek {product}, aby otrzymać udokumentowaną wycenę.",
        "Przewodnik pomaga nabywcom ocenić {product} dla {market} według zastosowania, specyfikacji i dowodów jakości.",
        "Nabywcy porównują specyfikacje, opakowanie, eksport, wycenę, hurt, dostawę i jakość.",
        "Dla {label} potwierdź z dostawcą następujące dane produktu.",
        "Przed produkcją seryjną sprawdź {topic} według próbki, wyceny i specyfikacji zakupu.",
        "Podaj ilość, opakowanie, termin, certyfikację i personalizację w jednym zapytaniu.",
        ("nabywcy", "specyfikacje", "opakowanie", "eksport", "wycena", "jakość"),
    ),
    "Chinese Simplified": _pack(
        ("{product}供应商与采购指南", "{product}制造商能力", "{product}批发与大宗订购", "{product}出口与分销", "{product}规格采购指南", "{product}B2B买家问答"),
        ("产品定义与买家匹配", "关键规格", "应用与下单前检查", "生产能力", "材料、工艺与定制", "质量与交期", "MOQ、报价与付款", "包装与运输", "目标市场与经销合作", "出口文件与合规", "规格和材料选择", "检验与询盘字段", "买家问题"),
        "{product}B2B出口站", "发送{product}规格、数量和目标市场，获取附带文件的报价。",
        "本指南帮助{buyer}根据应用、规格和质量证明评估面向{market}的{product}。",
        "买家可在下单前比较规格、包装、出口条件、报价、批发数量、交期和质量。",
        "关于{label}，请与供应商确认以下产品专属字段。",
        "批量生产前，请通过样品、报价和采购规格确认{topic}。",
        "请在一次询盘中说明数量、包装、交期、认证和定制要求。",
        ("规格", "包装", "出口", "买家", "报价", "质量"),
    ),
    "Chinese Traditional": _pack(
        ("{product}供應商與採購指南", "{product}製造商能力", "{product}批發與大宗訂購", "{product}出口與分銷", "{product}規格採購指南", "{product}B2B買家問答"),
        ("產品定義與買家匹配", "關鍵規格", "應用與下單前檢查", "生產能力", "材料、工藝與客製化", "品質與交期", "MOQ、報價與付款", "包裝與運輸", "目標市場與經銷合作", "出口文件與合規", "規格和材料選擇", "檢驗與詢盤欄位", "買家問題"),
        "{product}B2B出口站", "發送{product}規格、數量和目標市場，取得附帶文件的報價。",
        "本指南協助{buyer}根據應用、規格和品質證明評估面向{market}的{product}。",
        "買家可在下單前比較規格、包裝、出口條件、報價、批發數量、交期和品質。",
        "關於{label}，請與供應商確認以下產品專屬欄位。",
        "批量生產前，請透過樣品、報價和採購規格確認{topic}。",
        "請在一次詢盤中說明數量、包裝、交期、認證和客製化要求。",
        ("規格", "包裝", "出口", "買家", "報價", "品質"),
    ),
}


_LANGUAGE_ALIASES = {
    "Chinese Simplified": ("中文", "Chinese", "简体中文", "簡體中文", "zh", "zh-CN", "zh-Hans"),
    "Chinese Traditional": ("繁体中文", "繁體中文", "Traditional Chinese", "zh-TW", "zh-Hant"),
}


_MARKET_ALIASES = {
    "Japan": ("日本市场", "日本市場", "Japan market", "market in Japan", "日本"),
    "US": ("美国市场", "美國市場", "US market", "U.S. market", "United States", "America", "USA", "美国", "美國", "US"),
    "Germany": ("德国市场", "德國市場", "Germany market", "German market", "Germany", "德国", "德國"),
    "France": ("法国市场", "法國市場", "France market", "French market", "France", "法国", "法國"),
    "Spain": ("西班牙市场", "西班牙市場", "Spain market", "Spanish market", "Spain", "西班牙"),
    "Brazil": ("巴西市场", "巴西市場", "Brazil market", "Brazil", "巴西"),
    "Europe": ("欧洲市场", "歐洲市場", "Europe market", "European market", "Europe", "欧洲", "歐洲"),
    "Middle East": ("中东市场", "中東市場", "Middle East market", "Middle East", "中东", "中東"),
    "Southeast Asia": ("东南亚市场", "東南亞市場", "Southeast Asia market", "Southeast Asian", "Southeast Asia", "东南亚", "東南亞"),
}


_MARKET_LABELS = {
    "Japanese": {"Japan": "日本市場", "US": "米国市場", "Germany": "ドイツ市場", "France": "フランス市場", "Spain": "スペイン市場", "Europe": "欧州市場", "Brazil": "ブラジル市場", "Middle East": "中東市場", "Southeast Asia": "東南アジア市場"},
    "Spanish": {"Japan": "el mercado japonés", "US": "el mercado estadounidense", "Germany": "el mercado alemán", "France": "el mercado francés", "Spain": "el mercado español", "Europe": "el mercado europeo", "Brazil": "el mercado brasileño", "Middle East": "Oriente Medio", "Southeast Asia": "el Sudeste Asiático"},
    "German": {"Japan": "den japanischen Markt", "US": "den US-Markt", "Germany": "den deutschen Markt", "France": "den französischen Markt", "Spain": "den spanischen Markt", "Europe": "den europäischen Markt", "Brazil": "den brasilianischen Markt", "Middle East": "den Nahen Osten", "Southeast Asia": "Südostasien"},
    "French": {"Japan": "le marché japonais", "US": "le marché américain", "Germany": "le marché allemand", "France": "le marché français", "Spain": "le marché espagnol", "Europe": "le marché européen", "Brazil": "le marché brésilien", "Middle East": "le Moyen-Orient", "Southeast Asia": "l’Asie du Sud-Est"},
    "Portuguese": {"Japan": "o mercado japonês", "US": "o mercado dos EUA", "Germany": "o mercado alemão", "France": "o mercado francês", "Spain": "o mercado espanhol", "Europe": "o mercado europeu", "Brazil": "o mercado brasileiro", "Middle East": "o Oriente Médio", "Southeast Asia": "o Sudeste Asiático"},
    "Chinese Simplified": {"Japan": "日本市场", "US": "美国市场", "Germany": "德国市场", "France": "法国市场", "Spain": "西班牙市场", "Europe": "欧洲市场", "Brazil": "巴西市场", "Middle East": "中东市场", "Southeast Asia": "东南亚市场"},
    "Chinese Traditional": {"Japan": "日本市場", "US": "美國市場", "Germany": "德國市場", "France": "法國市場", "Spain": "西班牙市場", "Europe": "歐洲市場", "Brazil": "巴西市場", "Middle East": "中東市場", "Southeast Asia": "東南亞市場"},
}


_TERM_TRANSLATIONS = {
    "Japanese": {
        "outer diameter": "外径", "wall thickness": "肉厚", "length": "長さ", "galvanized steel": "亜鉛メッキ鋼",
        "construction": "建築用途", "packaging": "梱包", "export documents": "輸出書類", "lead time": "納期", "quality": "品質確認",
    },
    "Spanish": {
        "pressure rating": "presión nominal", "working pressure": "presión de trabajo", "sealing type": "tipo de sellado",
        "thread standard": "norma de rosca", "capacity": "Capacidad", "glaze": "Esmalte",
        "food contact safety": "seguridad alimentaria", "logo customization": "personalización de logotipo",
        "gift box": "caja de regalo", "packaging": "embalaje", "quality": "calidad", "buyers": "compradores",
    },
    "German": {
        "abrasion resistance": "Verschleißfestigkeit", "tensile strength": "Zugfestigkeit", "material": "Material",
        "packaging": "Verpackung", "lead time": "Lieferzeit", "quality": "Qualität",
    },
    "French": {
        "capacity": "capacité", "glaze": "glaçure", "packaging": "emballage", "logo customization": "logo personnalisé",
        "food contact safety": "sécurité alimentaire", "buyers": "acheteurs", "quality": "qualité",
    },
    "Portuguese": {
        "material safety": "segurança do material", "pet size": "tamanho do animal", "durability": "durabilidade",
        "cleaning": "limpeza", "packaging": "embalagem", "buyers": "compradores", "quality": "qualidade",
    },
    "Vietnamese": {
        "fabric composition": "chất liệu vải", "size range": "kích cỡ", "size chart": "bảng kích cỡ",
        "logo printing": "in logo", "packaging": "đóng gói", "quality": "chất lượng",
    },
}


def supported_languages() -> tuple[str, ...]:
    return tuple(_PACKS)


def normalize_language(value) -> str:
    """Return a writer language while preserving Simplified/Traditional Chinese."""
    raw = str(value or "").strip()
    folded = raw.casefold().replace("_", "-")
    for language in _PACKS:
        if folded == language.casefold():
            return language
    for language, aliases in _LANGUAGE_ALIASES.items():
        if any(folded == alias.casefold().replace("_", "-") for alias in aliases):
            return language
    from lib.language_normalizer import normalize
    result = normalize(raw)
    language = result.get("language", "English")
    if language == "Chinese":
        return "Chinese Traditional" if result.get("locale") == "zh-TW" or result.get("script") == "Hant" else "Chinese Simplified"
    return language if language in _PACKS else "English"


def normalize_market(value):
    """Return a canonical market without treating language names as markets."""
    raw = str(value or "").strip()
    if not raw or raw.casefold() == "none":
        return None
    folded = raw.casefold()
    language_only = ("西班牙语", "西語", "日语", "日語", "日本語", "德语", "德語", "法语", "法語", "spanish", "japanese", "german", "french")
    if folded in {item.casefold() for item in language_only}:
        return None
    # Explicit market phrases are safe inside a longer request.
    for market, aliases in _MARKET_ALIASES.items():
        for alias in aliases:
            af = alias.casefold()
            explicit = "市场" in alias or "市場" in alias or "market" in af or alias in ("United States", "America", "Southeast Asian", "Middle East")
            if explicit and af in folded:
                return market
    # Bare Latin country names are safe at word boundaries; bare CJK names are
    # accepted only when the entire field is already a market value.
    for market, aliases in _MARKET_ALIASES.items():
        for alias in aliases:
            af = alias.casefold()
            if re.fullmatch(r"[\w. -]+", alias, re.UNICODE):
                if re.search(r"(?<!\w)" + re.escape(af) + r"(?!\w)", folded):
                    return market
            elif folded == af:
                return market
    return raw


def _safe(value, fallback="Product") -> str:
    text = str(value or "").strip()
    return fallback if not text or text.casefold() == "none" else text


def _page_type(value) -> str:
    normalized = str(value or "supplier_guide").strip().lower()
    aliases = {"supplier": "supplier_guide", "guide": "supplier_guide", "bulk": "wholesale", "specs": "specifications"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in PAGE_TYPES else "supplier_guide"


def _pack_for(language):
    return _PACKS[normalize_language(language)]


def clean_product_display_name(raw, language=None, market=None) -> str:
    """Remove request metadata while keeping only the product phrase."""
    text = _safe(raw, "Product").strip(" ,，。.;；:：")
    if text == "Product":
        return text

    # Extract the object after an English website command before removing
    # modifiers. This handles both "website for X" and "SEO pages for X".
    command = re.search(
        r"(?:create|build|make|generate)\s+(?:an?\s+)?(?:[\w-]+\s+){0,4}?(?:website|site|pages?)\s+(?:for|about)\s+(.+)$",
        text, re.IGNORECASE,
    )
    if command:
        text = command.group(1)

    text = re.sub(r"^(?:请)?(?:帮我|帮忙|我要|我想)?\s*(?:做|制作|生成|创建|建|搭建)\s*(?:一个|个)?\s*", "", text)
    text = re.split(r"[,，]\s*(?:面向|目标(?:是|为)?|target(?:ing)?)", text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.sub(r"\s+(?:target(?:ing)?\s+.+|for\s+(?:the\s+)?(?:Japan|US|USA|United States|Germany|France|Spain|Brazil|Europe|Middle East|Southeast Asia|Southeast Asian)\s+(?:market\s+)?(?:buyers?|distributors?|wholesalers?|retailers?|shops?)?)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+in\s+(?:English|Japanese|Korean|German|French|Spanish|Portuguese|Italian|Russian|Arabic|Vietnamese|Thai|Indonesian|Malay|Dutch|Turkish|Polish|Chinese)(?:\s+for.*)?$", "", text, flags=re.IGNORECASE)

    removable = [
        "西班牙市场", "西班牙市場", "日本市场", "日本市場", "德国市场", "德國市場", "法国市场", "法國市場",
        "美国市场", "美國市場", "巴西市场", "巴西市場", "欧洲市场", "歐洲市場", "中东市场", "中東市場",
        "东南亚市场", "東南亞市場", "西班牙语", "西班牙語", "葡萄牙语", "葡萄牙語", "阿拉伯语", "阿拉伯語",
        "印度尼西亚语", "印尼语", "越南语", "越南語", "意大利语", "意大利語", "土耳其语", "土耳其語",
        "英语", "英文", "日语", "日語", "日文", "德语", "德語", "德文", "法语", "法語", "法文", "韩语", "韩文", "俄语", "泰语",
        "马来语", "荷兰语", "波兰语", "中文", "简体中文", "繁体中文", "日本語",
    ]
    for token in sorted(removable, key=len, reverse=True):
        text = text.replace(token, "")

    english_meta = (
        "Traditional Chinese", "Simplified Chinese", "Bahasa Indonesia", "Bahasa Melayu", "Tiếng Việt",
        "Portuguese", "Indonesian", "Vietnamese", "Japanese", "Spanish", "English", "Korean", "German",
        "French", "Italian", "Russian", "Arabic", "Malay", "Dutch", "Turkish", "Polish", "Thai",
        "Germany market", "France market", "Spain market", "Japan market", "US market", "Brazil market",
        "Europe market", "Middle East market", "Southeast Asia market",
    )
    for token in sorted(english_meta, key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(token) + r"(?!\w)", " ", text, flags=re.IGNORECASE)

    text = re.sub(r"(?:B2B|SEO)?\s*(?:出口站|外贸站|外貿站|批发网站|批發網站|出口网站|外贸网站|官网|網站|网站|サイト|站|页面)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:B2B|SEO|export|wholesale|foreign\s+trade|official)\s*(?:website|site|pages?)?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:website|site|pages?)\b", " ", text, flags=re.IGNORECASE)
    text = text.replace("向け", "")
    text = re.sub(r"(?:面向)?(?:海外)?(?:礼品|工厂|品牌)?(?:批发商|经销商|采购商|买家|宠物店)$", "", text)
    text = re.sub(r"\b(?:for|in|target|buyers?|distributors?|wholesalers?|purchasers?|retailers?)\b.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ,，。.;；:：-/")
    return _safe(text, "Product")


def _market_label(market, language) -> str:
    canonical = normalize_market(market)
    if not canonical:
        defaults = {
            "Japanese": "世界の輸出市場", "Spanish": "mercados internacionales", "German": "internationale Exportmärkte",
            "French": "les marchés internationaux", "Portuguese": "mercados internacionais", "Arabic": "الأسواق الدولية",
            "Vietnamese": "thị trường quốc tế", "Thai": "ตลาดส่งออกทั่วโลก", "Indonesian": "pasar ekspor global",
            "Chinese Simplified": "全球出口市场", "Chinese Traditional": "全球出口市場",
        }
        return defaults.get(normalize_language(language), "global export markets")
    return _MARKET_LABELS.get(normalize_language(language), {}).get(canonical, canonical)


def localize_page_title(page_type, product, language, market=None, audience=None) -> str:
    del market, audience  # Market and audience belong in copy, never in the product title.
    clean = clean_product_display_name(product, language=language)
    return _pack_for(language)["titles"][_page_type(page_type)].format(product=clean)


def localize_site_title(product, language, market=None, site_type=None) -> str:
    del market, site_type
    return _pack_for(language)["site"].format(product=clean_product_display_name(product, language=language))


def localize_section_label(section_key, language) -> str:
    return _pack_for(language)["sections"].get(section_key, _pack_for(language)["sections"]["definition"])


def localize_cta(language, product="Product") -> str:
    return _pack_for(language)["cta"].format(product=clean_product_display_name(product, language=language))


class _SafeVariables(dict):
    def __missing__(self, key):
        return ""


def localize_sentence(template_key, language, variables=None) -> str:
    pack = _pack_for(language)
    template = pack["sentences"].get(template_key) or _PACKS["English"]["sentences"].get(template_key, "")
    values = _SafeVariables({key: _safe(value, "") for key, value in dict(variables or {}).items()})
    values["product"] = clean_product_display_name(values.get("product"), language=language)
    values["market"] = _market_label(values.get("market"), language)
    return template.format_map(values).strip()


def localize_term(term, language) -> str:
    """Translate known business/industry fields and retain the source term."""
    source = _safe(term, "")
    if not source:
        return ""
    translations = _TERM_TRANSLATIONS.get(normalize_language(language), {})
    folded = source.casefold()
    for needle, translated in sorted(translations.items(), key=lambda item: len(item[0]), reverse=True):
        if needle.casefold() in folded and translated.casefold() not in folded:
            return f"{translated} ({source})"
    return source


def language_coverage_score(text, language) -> float:
    """Score target-language business vocabulary, ignoring technical acronyms."""
    clean = unescape(re.sub(r"<[^>]+>", " ", str(text or ""))).casefold()
    tokens = _pack_for(language)["coverage"]
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token.casefold() in clean)
    return round(hits / len(tokens), 3)


# ═══════════════════════════════════════════════════════════════
# Phase 9.4.1: Product localization quality checks
# ═══════════════════════════════════════════════════════════════

# Technical acronyms allowed in any language — not flagged as untranslated
_TECH_ACRONYMS = {
    "MOQ", "OEM", "ODM", "ASTM", "JIS", "DIN", "EN", "BSP", "NPT", "JIC",
    "ISO", "FDA", "CE", "GSM", "TPR", "PVC", "PU", "BPA", "LED",
    "MTC", "B2B", "SEO", "ROI", "API", "SKU", "UPC", "EAN",
}


def product_localization_coverage(text, product_localized) -> float:
    """Score how well the localized product name appears in content.

    Returns 0.0 (absent) to 1.0 (well-represented).
    """
    if not text or not product_localized:
        return 0.0
    clean_text = unescape(re.sub(r"<[^>]+>", " ", str(text))).casefold()
    localized = str(product_localized).strip()
    if not localized:
        return 0.0
    count = clean_text.count(localized.casefold())
    if count >= 3:
        return 1.0
    elif count >= 1:
        return 0.5 + min(count - 1, 2) * 0.25
    return 0.0


def source_language_leak_score(text, product_original, target_language) -> float:
    """Score source-language leakage in target-language content.

    Returns 0.0 (no leak) to 1.0 (severe leak).
    Only checks for CJK characters in non-CJK target pages.
    Technical acronyms are excluded.
    """
    if not text or not product_original or not target_language:
        return 0.0

    clean_text = str(text)
    for acronym in _TECH_ACRONYMS:
        clean_text = re.sub(r'\b' + re.escape(acronym) + r'\b', '', clean_text, flags=re.IGNORECASE)

    cjk_target_langs = {"Chinese", "Chinese Simplified", "Chinese Traditional", "Japanese", "Korean"}
    if target_language in cjk_target_langs:
        return 0.0

    cjk_chars = re.findall(r'[一-鿿぀-ゟ゠-ヿ가-힯]', clean_text)
    if not cjk_chars:
        return 0.0

    total_chars = len(re.sub(r'\s', '', clean_text))
    if total_chars == 0:
        return 0.0

    ratio = len(cjk_chars) / total_chars
    return min(ratio * 3, 1.0)


def assert_no_none_terms(text) -> bool:
    """Verify no 'None' literal appears as a standalone word in content."""
    if not text:
        return True
    return not bool(re.search(r'\bNone\b', str(text)))
