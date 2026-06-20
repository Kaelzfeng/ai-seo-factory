"""lib/themes/blueprint.py · "Technical Blueprint" 主题

把 mockups/c-technical-blueprint.html + mockups/site-c/index.html 的视觉设计
参数化成可复用于任意行业的主题模块。所有文字/品牌/导航/正文均来自 ctx，
不含任何皮革/MERIDIAN 等硬编码行业内容。

契约见 lib/themes/_base.py。
"""
from lib.themes._base import esc

NAME = "technical-blueprint"
LABEL = "Technical Blueprint"

# Google Fonts <link>（连同 preconnect 一起从 mockup 搬来）
_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900'
    '&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700'
    '&display=swap" rel="stylesheet">'
)

# === 逐字复用 mockup 的 <style>（配色/字体/间距/动画一模一样）===
# 仅在末尾补一条：裸 <table>（无 .table-scroll 外层容器）时也能窄屏横向滚动。
_STYLE = """<style>
  :root{
    --bg:#F4F5F3;
    --grid:rgba(14,17,22,.06);
    --grid-strong:rgba(14,17,22,.12);
    --ink:#0E1116;
    --accent:#1B39C4;
    --accent-soft:rgba(27,57,196,.08);
    --muted:#5A6066;
    --line:#D2D6DC;
    --paper:#FBFBFA;
    --unit:28px;
  }

  *{box-sizing:border-box;}
  html{ -webkit-text-size-adjust:100%; }
  body{
    margin:0;
    background:var(--bg);
    color:var(--ink);
    font-family:"IBM Plex Sans",-apple-system,sans-serif;
    font-weight:400;
    font-size:17px;
    line-height:1.62;
    letter-spacing:.005em;
    -webkit-font-smoothing:antialiased;
    text-rendering:optimizeLegibility;
    /* engineering grid: fine net + every-4th stronger line, drawn over near-white */
    background-image:
      repeating-linear-gradient(to right, var(--grid) 0, var(--grid) 1px, transparent 1px, transparent var(--unit)),
      repeating-linear-gradient(to bottom, var(--grid) 0, var(--grid) 1px, transparent 1px, transparent var(--unit)),
      repeating-linear-gradient(to right, var(--grid-strong) 0, var(--grid-strong) 1px, transparent 1px, transparent calc(var(--unit) * 4)),
      repeating-linear-gradient(to bottom, var(--grid-strong) 0, var(--grid-strong) 1px, transparent 1px, transparent calc(var(--unit) * 4));
    background-position:0 0;
  }

  .mono{ font-family:"IBM Plex Mono",monospace; }

  /* ============ LAYOUT FRAME ============ */
  .frame{
    max-width:1240px;
    margin:0 auto;
    position:relative;
    background:linear-gradient(var(--paper),var(--paper));
    border-left:1px solid var(--line);
    border-right:1px solid var(--line);
  }
  /* corner tick marks of a drawing sheet */
  .frame::before,.frame::after{
    content:"";
    position:absolute;
    width:14px;height:14px;
    border:1px solid var(--accent);
    z-index:5;
  }
  .frame::before{ top:-1px;left:-1px;border-right:none;border-bottom:none; }
  .frame::after{ top:-1px;right:-1px;border-left:none;border-bottom:none; }

  /* ============ TOP BAR ============ */
  header.topbar{
    position:sticky;top:0;z-index:40;
    background:rgba(251,251,250,.86);
    backdrop-filter:saturate(140%) blur(8px);
    -webkit-backdrop-filter:saturate(140%) blur(8px);
    border-bottom:1px solid var(--ink);
  }
  .topbar-inner{
    display:flex;align-items:stretch;
    min-height:62px;
  }
  .brand{
    display:flex;flex-direction:column;justify-content:center;
    padding:8px 22px;
    border-right:1px solid var(--line);
    flex-shrink:0;
  }
  .brand .name{
    font-family:"Archivo",sans-serif;
    font-weight:900;
    font-size:18px;
    letter-spacing:.02em;
    line-height:1;
    text-transform:uppercase;
  }
  .brand .name .dot{ color:var(--accent); }
  .brand .est{
    font-family:"IBM Plex Mono",monospace;
    font-size:10px;
    letter-spacing:.14em;
    text-transform:uppercase;
    color:var(--muted);
    margin-top:5px;
  }
  nav.mainnav{
    display:flex;align-items:stretch;
    overflow-x:auto;
    flex:1;
    scrollbar-width:none;
  }
  nav.mainnav::-webkit-scrollbar{ display:none; }
  nav.mainnav a{
    display:flex;align-items:center;
    padding:0 16px;
    font-family:"IBM Plex Mono",monospace;
    font-size:11px;
    font-weight:500;
    letter-spacing:.04em;
    text-transform:uppercase;
    color:var(--muted);
    text-decoration:none;
    white-space:nowrap;
    border-left:1px solid transparent;
    border-right:1px solid var(--line);
    transition:color .18s ease, background .18s ease;
    position:relative;
  }
  nav.mainnav a:last-child{ border-right:none; }
  nav.mainnav a .idx{
    font-size:9px;color:var(--line);margin-right:7px;
    transition:color .18s ease;
  }
  nav.mainnav a:hover{ color:var(--ink);background:var(--accent-soft); }
  nav.mainnav a:hover .idx{ color:var(--accent); }
  nav.mainnav a.active{
    color:var(--accent);
    background:#fff;
    border-bottom:2px solid var(--accent);
  }
  nav.mainnav a.active .idx{ color:var(--accent); }

  /* ============ BREADCRUMB ============ */
  .breadcrumb{
    border-bottom:1px solid var(--line);
    background:var(--paper);
    padding:10px 24px;
    font-family:"IBM Plex Mono",monospace;
    font-size:11px;
    letter-spacing:.05em;
    text-transform:uppercase;
    color:var(--muted);
    display:flex;align-items:center;gap:9px;flex-wrap:wrap;
  }
  .breadcrumb a{ color:var(--muted);text-decoration:none; }
  .breadcrumb a:hover{ color:var(--accent); }
  .breadcrumb .sep{ color:var(--accent);font-weight:600; }
  .breadcrumb .here{ color:var(--ink); }

  /* ============ HERO ============ */
  .hero{
    position:relative;
    padding:54px 24px 0;
    border-bottom:1px solid var(--ink);
    overflow:hidden;
  }
  .hero-grid{
    display:grid;
    grid-template-columns:1fr;
  }
  .hero-meta{
    display:flex;justify-content:space-between;align-items:flex-start;
    gap:16px;flex-wrap:wrap;
    font-family:"IBM Plex Mono",monospace;
    font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
    padding-bottom:20px;
    border-bottom:1px dashed var(--line);
  }
  .hero-meta .tag-accent{ color:var(--accent);font-weight:600; }
  .kicker{
    display:inline-flex;align-items:center;gap:10px;
    font-family:"IBM Plex Mono",monospace;
    font-size:12px;letter-spacing:.16em;text-transform:uppercase;
    color:var(--accent);
    margin:26px 0 18px;
    font-weight:600;
  }
  .kicker .barcode{
    display:inline-block;width:34px;height:13px;
    background:repeating-linear-gradient(to right,var(--accent) 0,var(--accent) 2px,transparent 2px,transparent 4px);
  }
  .hero-title{
    font-family:"Archivo",sans-serif;
    font-weight:900;
    font-stretch:expanded;
    font-size:clamp(38px,7vw,90px);
    line-height:.96;
    letter-spacing:-.02em;
    text-transform:uppercase;
    margin:0;
    max-width:15ch;
    text-wrap:balance;
  }
  .hero-title .em{
    color:var(--accent);
    display:inline-block;
  }
  .hero-rule{
    height:0;
    border-top:3px solid var(--accent);
    margin:30px 0 0;
    position:relative;
  }
  /* ruler ticks under the cobalt line */
  .hero-rule::after{
    content:"";
    position:absolute;left:0;right:0;top:3px;height:9px;
    background:repeating-linear-gradient(to right,var(--accent) 0,var(--accent) 1px,transparent 1px,transparent 22px);
    opacity:.5;
  }
  .hero-lead{
    font-size:clamp(16px,1.7vw,20px);
    line-height:1.55;
    color:var(--ink);
    max-width:60ch;
    margin:26px 0 30px;
    font-weight:400;
  }
  .hero-lead strong{ font-weight:600; }
  .chips{
    display:flex;flex-wrap:wrap;gap:0;
    border-top:1px solid var(--ink);
    border-left:1px solid var(--line);
    margin-bottom:0;
  }
  .chip{
    flex:1 1 auto;min-width:140px;
    padding:13px 16px 14px;
    border-right:1px solid var(--line);
    border-bottom:1px solid var(--line);
    background:#fff;
  }
  .chip .lbl{
    display:block;
    font-family:"IBM Plex Mono",monospace;
    font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--muted);margin-bottom:5px;
  }
  .chip .val{
    font-family:"IBM Plex Mono",monospace;
    font-size:15px;font-weight:600;color:var(--ink);
    letter-spacing:.01em;
  }
  .chip .val span{ color:var(--accent); }

  /* hero stagger animation */
  .anim{ opacity:0;transform:translateY(14px);animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards; }
  .a1{ animation-delay:.05s; }
  .a2{ animation-delay:.16s; }
  .a3{ animation-delay:.27s; }
  .a4{ animation-delay:.38s; }
  .a5{ animation-delay:.49s; }
  .a6{ animation-delay:.60s; }
  @keyframes rise{ to{ opacity:1;transform:translateY(0);} }
  @media (prefers-reduced-motion:reduce){
    .anim{ opacity:1;transform:none;animation:none; }
  }

  /* ============ ARTICLE ============ */
  .article-wrap{
    display:grid;
    grid-template-columns:62px minmax(0,1fr);
    border-bottom:1px solid var(--ink);
  }
  /* left coordinate gutter */
  .gutter{
    border-right:1px solid var(--line);
    position:relative;
    background:
      repeating-linear-gradient(to bottom,transparent 0,transparent calc(var(--unit)*4 - 1px),var(--grid-strong) calc(var(--unit)*4 - 1px),var(--grid-strong) calc(var(--unit)*4));
  }
  .gutter .figtag{
    position:sticky;top:80px;
    writing-mode:vertical-rl;
    transform:rotate(180deg);
    font-family:"IBM Plex Mono",monospace;
    font-size:10px;letter-spacing:.22em;text-transform:uppercase;
    color:var(--accent);
    padding:18px 0;
    margin-left:24px;
  }

  article{
    padding:46px clamp(20px,4vw,64px) 56px;
    max-width:80ch;
  }

  /* the single real H1 lives in the article — demote it visually so it's a "doc title" line, hero carries the poster */
  article h1{
    font-family:"IBM Plex Mono",monospace;
    font-size:13px;
    font-weight:500;
    letter-spacing:.06em;
    text-transform:uppercase;
    color:var(--muted);
    margin:0 0 8px;
    padding-bottom:14px;
    border-bottom:1px solid var(--line);
    line-height:1.4;
  }
  article h1::before{
    content:"DOC \\25B8 ";
    color:var(--accent);
  }

  article p{
    margin:0 0 20px;
    color:#22262C;
  }
  article > p:first-of-type{
    margin-top:22px;
  }
  /* lead-in paragraph after H1 gets a touch more presence */
  article h1 + p{
    font-size:18.5px;
    color:var(--ink);
  }

  /* H2 — cobalt mono numbered + uppercase label */
  article h2{
    counter-increment:sec;
    font-family:"Archivo",sans-serif;
    font-weight:800;
    font-stretch:expanded;
    font-size:clamp(22px,3vw,32px);
    line-height:1.08;
    letter-spacing:-.01em;
    text-transform:uppercase;
    color:var(--ink);
    margin:54px 0 18px;
    padding-top:30px;
    border-top:1px solid var(--ink);
    position:relative;
    text-wrap:balance;
  }
  article h2::before{
    content:"\\A7" counter(sec,decimal-leading-zero);
    display:block;
    font-family:"IBM Plex Mono",monospace;
    font-size:12px;font-weight:600;
    letter-spacing:.12em;
    color:var(--accent);
    margin-bottom:12px;
    text-transform:uppercase;
  }
  article{ counter-reset:sec; }

  article h3{
    font-family:"Archivo",sans-serif;
    font-weight:700;
    font-size:19px;
    text-transform:uppercase;
    letter-spacing:.01em;
    margin:34px 0 12px;
    color:var(--ink);
  }

  article a{
    color:var(--accent);
    text-decoration:none;
    font-weight:500;
    border-bottom:1px solid rgba(27,57,196,.32);
    transition:background .15s ease, border-color .15s ease;
    padding-bottom:1px;
  }
  article a:hover{
    background:var(--accent-soft);
    border-bottom-color:var(--accent);
  }

  /* lists */
  article ul{
    list-style:none;
    margin:0 0 24px;
    padding:0;
    border-top:1px solid var(--line);
  }
  article ul li{
    position:relative;
    padding:11px 8px 11px 40px;
    border-bottom:1px solid var(--line);
    color:#22262C;
  }
  article ul li::before{
    content:"";
    position:absolute;
    left:14px;top:19px;
    width:7px;height:7px;
    background:var(--accent);
    transform:rotate(45deg);
  }
  article ul li::after{
    counter-increment:li;
    content:counter(li,decimal-leading-zero);
    position:absolute;
    left:0;top:50%;transform:translateY(-50%);
    display:none;
  }

  /* blockquote (in case content has one) */
  article blockquote{
    margin:28px 0;
    padding:18px 22px;
    border-left:3px solid var(--accent);
    background:var(--accent-soft);
    font-family:"IBM Plex Sans",sans-serif;
    font-style:normal;
    color:var(--ink);
  }

  /* ============ TABLE — DATASHEET ============ */
  .table-scroll{
    overflow-x:auto;
    margin:8px 0 28px;
    border:1px solid var(--ink);
    background:#fff;
    -webkit-overflow-scrolling:touch;
  }
  article table{
    width:100%;
    border-collapse:collapse;
    min-width:620px;
    font-size:14px;
  }
  article thead th{
    background:var(--accent);
    color:#fff;
    font-family:"IBM Plex Mono",monospace;
    font-size:10.5px;
    font-weight:600;
    letter-spacing:.08em;
    text-transform:uppercase;
    text-align:left;
    padding:12px 14px;
    border-right:1px solid rgba(255,255,255,.18);
    white-space:nowrap;
    position:sticky;top:0;
  }
  article thead th:last-child{ border-right:none; }
  article tbody td{
    padding:11px 14px;
    border-bottom:1px solid var(--line);
    border-right:1px solid var(--grid-strong);
    color:#22262C;
    vertical-align:top;
  }
  article tbody td:last-child{ border-right:none; }
  /* first col = property name, semibold sans */
  article tbody td:first-child{
    font-weight:600;
    color:var(--ink);
    white-space:nowrap;
  }
  /* numeric range column + standard column = mono */
  article tbody td:nth-child(2),
  article tbody td:nth-child(3){
    font-family:"IBM Plex Mono",monospace;
    font-size:13px;
    letter-spacing:-.01em;
    white-space:nowrap;
    color:var(--ink);
  }
  /* test-standard col tinted cobalt to read as the "spec reference" */
  article tbody td:nth-child(3){
    color:var(--accent);
    font-weight:500;
  }
  article tbody tr:nth-child(even) td{
    background:#FAFAF8;
  }
  article tbody tr:hover td{
    background:var(--accent-soft);
  }

  /* bare <table> (no .table-scroll wrapper): keep it horizontally scrollable on narrow screens */
  .article table{ display:block;overflow-x:auto;-webkit-overflow-scrolling:touch; }

  /* ============ FOOTER ============ */
  footer{
    background:var(--ink);
    color:#C9CDD3;
    padding:40px 24px 36px;
  }
  .footer-inner{
    max-width:1240px;margin:0 auto;
    display:flex;justify-content:space-between;align-items:flex-end;
    gap:24px;flex-wrap:wrap;
  }
  footer .f-brand{
    font-family:"Archivo",sans-serif;
    font-weight:900;font-size:20px;letter-spacing:.02em;
    text-transform:uppercase;color:#fff;
    line-height:1;
  }
  footer .f-brand .dot{ color:#6B83E6; }
  footer .f-sub{
    font-family:"IBM Plex Mono",monospace;
    font-size:11px;letter-spacing:.08em;text-transform:uppercase;
    color:#878D96;margin-top:10px;
  }
  footer .f-meta{
    font-family:"IBM Plex Mono",monospace;
    font-size:11px;letter-spacing:.06em;text-transform:uppercase;
    color:#878D96;text-align:right;line-height:1.9;
  }
  footer .f-meta .rev{ color:#6B83E6; }

  /* ============ RESPONSIVE ============ */
  @media (max-width:860px){
    .article-wrap{ grid-template-columns:1fr; }
    .gutter{ display:none; }
  }
  @media (max-width:720px){
    body{ font-size:16px; }
    .brand{ padding:8px 16px; }
    .brand .name{ font-size:16px; }
    nav.mainnav a{ font-size:10px;padding:0 12px; }
    nav.mainnav a .idx{ display:none; }
    .hero{ padding:38px 18px 0; }
    .hero-title{ max-width:100%; }
    .breadcrumb{ padding:9px 16px;font-size:10px; }
    article{ padding:34px 18px 44px; }
    .chip{ min-width:120px; }
  }
  @media (max-width:480px){
    .topbar-inner{ flex-direction:column;align-items:stretch; }
    .brand{ border-right:none;border-bottom:1px solid var(--line);flex-direction:row;align-items:baseline;gap:10px; }
    nav.mainnav{ border-top:none; }
  }
</style>"""

# index 专属的额外 <style>（逐字搬自 site-c/index.html 的第二个 <style>）
_INDEX_STYLE = """<style>
  .group-head{ font-family:"IBM Plex Mono",monospace; font-size:11px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); padding:30px 8px 12px; border-top:1px solid var(--ink); margin-top:0; }
  .index-item{ display:block; padding:18px 8px 20px 40px; position:relative; border-bottom:1px solid var(--line); text-decoration:none; color:inherit; }
  .index-item::before{ content:""; position:absolute; left:14px; top:26px; width:7px; height:7px; background:var(--accent); transform:rotate(45deg); }
  .index-item:hover{ background:var(--accent-soft); }
  .index-item .it-num{ font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.12em; color:var(--muted); }
  .index-item .it-type{ font-family:"IBM Plex Mono",monospace; font-size:9.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); border:1px solid var(--line); padding:2px 8px; margin-left:10px; }
  .index-item .it-title{ font-family:"Archivo",sans-serif; font-weight:800; font-size:clamp(19px,2.4vw,26px); line-height:1.1; text-transform:uppercase; letter-spacing:-.01em; color:var(--ink); margin:8px 0 6px; }
  .index-item:hover .it-title{ color:var(--accent); }
  .index-item .it-desc{ color:#22262C; max-width:74ch; font-size:15.5px; line-height:1.55; }
  /* skipped (failed QC) item: not a link, dimmed, with a marker */
  .index-item.is-skip{ opacity:.6; }
  .index-item.is-skip .it-title{ color:var(--muted); }
  .index-item .it-skip{ font-family:"IBM Plex Mono",monospace; font-size:9.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); border:1px solid var(--line); padding:2px 8px; margin-left:10px; }
</style>"""


def _brand_topbar(org):
    """品牌块（topbar 内）。.est 行用无行业含义的技术装饰。"""
    return (
        '<div class="brand">'
        '<span class="name">' + esc(org) + '<span class="dot">.</span></span>'
        '<span class="est">DOCUMENTATION SET</span>'
        '</div>'
    )


def _nav(nav):
    """主导航：active 项加 .active 高亮态；带 .idx 序号（mockup 风格）。"""
    out = ['<nav class="mainnav" aria-label="Primary">']
    for i, item in enumerate(nav or [], start=1):
        cls = ' class="active"' if item.get("active") else ''
        href = esc(item.get("href") or "#")
        idx = str(i).zfill(2)
        out.append(
            '<a href="' + href + '"' + cls + '>'
            '<span class="idx">' + idx + '</span>' + esc(item.get("label")) + '</a>'
        )
    out.append('</nav>')
    return "".join(out)


def _breadcrumb(crumbs):
    """面包屑：href 为 None 即当前页（.here 不可点）；其余可点，用 .sep 分隔。"""
    if not crumbs:
        return ''
    parts = ['<div class="breadcrumb" aria-label="Breadcrumb">']
    for i, c in enumerate(crumbs):
        if i:
            parts.append('<span class="sep">›</span>')
        href = c.get("href")
        label = esc(c.get("label"))
        if href is None:
            parts.append('<span class="here">' + label + '</span>')
        else:
            parts.append('<a href="' + esc(href) + '">' + label + '</a>')
    parts.append('</div>')
    return "".join(parts)


def _chips(chips):
    """规格小标签块；为空则不渲染整块。"""
    if not chips:
        return ''
    out = ['<div class="chips anim a6" aria-label="Key specifications">']
    for ch in chips:
        out.append('<div class="chip"><span class="val">' + esc(ch) + '</span></div>')
    out.append('</div>')
    return "".join(out)


def _footer(org, year):
    """底栏：品牌 + 无行业含义的技术装饰行。"""
    return (
        '<footer>'
        '<div class="footer-inner">'
        '<div>'
        '<div class="f-brand">' + esc(org) + '<span class="dot">.</span></div>'
        '<div class="f-sub">© ' + esc(year) + ' ' + esc(org) + ' · Specification-grade documentation</div>'
        '</div>'
        '<div class="f-meta">'
        '<div>SHEET 1 / 1 · <span class="rev">REV.A</span></div>'
        '<div>DOCUMENTATION SET</div>'
        '<div>SCALE 1:1</div>'
        '</div>'
        '</div>'
        '</footer>'
    )


def render_page(ctx: dict) -> str:
    """返回单页完整 <!doctype html> 文档。"""
    lang = esc(ctx.get("lang") or "en")
    title = esc(ctx.get("title"))
    meta_desc = esc(ctx.get("meta_desc"))
    org = ctx.get("org") or ""
    robots = esc(ctx.get("robots") or "")
    type_label = ctx.get("type_label") or "Document"
    body_has_h1 = bool(ctx.get("body_has_h1"))
    body_html = ctx.get("body_html") or ""        # 已构造好的 HTML，原样插入
    jsonld = ctx.get("jsonld") or ""              # 原样进 <head>
    warn_html = ctx.get("warn_html") or ""        # 原样，<article> 之前
    year = ctx.get("year") or ""

    tl_esc = esc(type_label)

    # hero 大标题：当正文已含唯一 <h1> 时，hero 标题必须为非 h1 元素
    if body_has_h1:
        hero_heading = '<p class="hero-title anim a3">' + title + '</p>'
    else:
        hero_heading = (
            '<h1 class="hero-title anim a3" role="heading" aria-level="1">' + title + '</h1>'
        )

    chips_html = _chips(ctx.get("chips"))

    doc = []
    doc.append('<!doctype html>')
    doc.append('<html lang="' + lang + '">')
    doc.append('<head>')
    doc.append('<meta charset="UTF-8">')
    doc.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    doc.append('<title>' + title + '</title>')
    doc.append('<meta name="description" content="' + meta_desc + '">')
    if robots:
        doc.append('<meta name="robots" content="' + robots + '">')
    doc.append(_FONTS)
    doc.append(_STYLE)
    if jsonld:
        doc.append(jsonld)
    doc.append('</head>')
    doc.append('<body>')
    doc.append('<div class="frame">')

    # TOP BAR
    doc.append('<header class="topbar"><div class="topbar-inner">')
    doc.append(_brand_topbar(org))
    doc.append(_nav(ctx.get("nav")))
    doc.append('</div></header>')

    # BREADCRUMB
    doc.append(_breadcrumb(ctx.get("crumbs")))

    # HERO
    doc.append('<section class="hero"><div class="hero-grid">')
    doc.append(
        '<div class="hero-meta anim a1">'
        '<span>SPEC SHEET / REV.A</span>'
        '<span class="tag-accent">' + tl_esc + ' · DOC</span>'
        '<span>SHEET 1 / 1 · SCALE 1:1</span>'
        '</div>'
    )
    doc.append(
        '<div class="kicker anim a2"><span class="barcode" aria-hidden="true"></span>'
        + tl_esc + ' · DOCUMENTATION</div>'
    )
    doc.append(hero_heading)
    doc.append('<div class="hero-rule anim a4" aria-hidden="true"></div>')
    doc.append('<p class="hero-lead anim a5">' + meta_desc + '</p>')
    doc.append(chips_html)
    doc.append('</div></section>')

    # ARTICLE
    doc.append('<div class="article-wrap">')
    doc.append(
        '<aside class="gutter" aria-hidden="true">'
        '<div class="figtag">SPEC SHEET · REV.A</div></aside>'
    )
    doc.append('<article>')
    if warn_html:
        doc.append(warn_html)      # 质检未过横幅，原样，<article> 内容之前
    doc.append(body_html)          # 含正文唯一 <h1>，原样插入
    doc.append('</article>')
    doc.append('</div>')

    # FOOTER
    doc.append(_footer(org, year))

    doc.append('</div>')
    doc.append('</body>')
    doc.append('</html>')
    return "\n".join(doc)


def render_index(ctx: dict) -> str:
    """返回首页完整 <!doctype html> 文档。"""
    lang = esc(ctx.get("lang") or "en")
    org = ctx.get("org") or ""
    site_name = esc(ctx.get("site_name"))
    sub = esc(ctx.get("sub"))
    robots = esc(ctx.get("robots") or "")
    year = ctx.get("year") or ""
    stats = ctx.get("stats") or {}
    groups = ctx.get("groups") or []

    total = stats.get("total", 0)
    n_pass = stats.get("n_pass", 0)
    n_skip = stats.get("n_skip", 0)

    doc = []
    doc.append('<!doctype html>')
    doc.append('<html lang="' + lang + '">')
    doc.append('<head>')
    doc.append('<meta charset="UTF-8">')
    doc.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    doc.append('<title>' + site_name + '</title>')
    doc.append('<meta name="description" content="' + sub + '">')
    if robots:
        doc.append('<meta name="robots" content="' + robots + '">')
    doc.append(_FONTS)
    doc.append(_STYLE)
    doc.append(_INDEX_STYLE)
    doc.append('</head>')
    doc.append('<body>')
    doc.append('<div class="frame">')

    # TOP BAR
    doc.append('<header class="topbar"><div class="topbar-inner">')
    doc.append(_brand_topbar(org))
    doc.append(_nav(ctx.get("nav")))
    doc.append('</div></header>')

    # BREADCRUMB (站点首页：当前页为 Index)
    doc.append(
        '<div class="breadcrumb" aria-label="Breadcrumb">'
        '<span class="here">Home</span>'
        '<span class="sep">›</span>'
        '<span class="here">Index</span>'
        '</div>'
    )

    # HERO (站点级：标题=site_name，副标=sub)
    doc.append('<section class="hero"><div class="hero-grid">')
    doc.append(
        '<div class="hero-meta anim a1">'
        '<span>SPEC SHEET / REV.A</span>'
        '<span class="tag-accent">DOCUMENTATION INDEX — ' + esc(total) + ' SHEETS</span>'
        '<span>SHEET 0 / ' + esc(total) + ' · SCALE 1:1</span>'
        '</div>'
    )
    doc.append(
        '<div class="kicker anim a2"><span class="barcode" aria-hidden="true"></span>'
        'DOCUMENTATION INDEX</div>'
    )
    doc.append('<h1 class="hero-title anim a3">' + site_name + '</h1>')
    doc.append('<div class="hero-rule anim a4" aria-hidden="true"></div>')
    doc.append('<p class="hero-lead anim a5"><strong>' + sub + '</strong></p>')
    doc.append(
        '<div class="chips anim a6" aria-label="Index summary">'
        '<div class="chip"><span class="lbl">Pages</span><span class="val"><span>'
        + esc(total) + '</span> sheets</span></div>'
        '<div class="chip"><span class="lbl">Published</span><span class="val"><span>'
        + esc(n_pass) + '</span> live</span></div>'
        '<div class="chip"><span class="lbl">Skipped</span><span class="val"><span>'
        + esc(n_skip) + '</span> held</span></div>'
        '<div class="chip"><span class="lbl">Revision</span><span class="val">REV.<span>A</span></span></div>'
        '</div>'
    )
    doc.append('</div></section>')

    # INDEX BODY
    doc.append('<div class="article-wrap">')
    doc.append(
        '<aside class="gutter" aria-hidden="true">'
        '<div class="figtag">INDEX · REV.A · ' + esc(total) + ' SHEETS</div></aside>'
    )
    doc.append('<article>')
    doc.append('<h1>' + site_name + '</h1>')
    doc.append(
        '<p>Connected reference sheets, grouped by document type. '
        'Each links to the next so a reader can move from the pillar into the specific document they need.</p>'
    )

    sheet_no = 0
    for grp in groups:
        doc.append('<div class="group-head">' + esc(grp.get("label")) + '</div>')
        doc.append('<div class="index-group">')
        for it in (grp.get("items") or []):
            sheet_no += 1
            num = 'SHEET ' + str(sheet_no).zfill(2)
            it_title = esc(it.get("title"))
            it_type = esc(it.get("type_label"))
            it_desc = esc(it.get("teaser"))
            href = it.get("href")
            passed = bool(it.get("passed"))
            if href and passed:
                doc.append(
                    '<a class="index-item" href="' + esc(href) + '">'
                    '<span class="it-num">' + num + '</span>'
                    '<span class="it-type">' + it_type + '</span>'
                    '<div class="it-title">' + it_title + '</div>'
                    '<div class="it-desc">' + it_desc + '</div>'
                    '</a>'
                )
            else:
                # 未过质检：标题不可点，打 skipped 标记
                doc.append(
                    '<div class="index-item is-skip">'
                    '<span class="it-num">' + num + '</span>'
                    '<span class="it-type">' + it_type + '</span>'
                    '<span class="it-skip">skipped</span>'
                    '<div class="it-title">' + it_title + '</div>'
                    '<div class="it-desc">' + it_desc + '</div>'
                    '</div>'
                )
        doc.append('</div>')

    doc.append('</article>')
    doc.append('</div>')

    # FOOTER
    doc.append(_footer(org, year))

    doc.append('</div>')
    doc.append('</body>')
    doc.append('</html>')
    return "\n".join(doc)
