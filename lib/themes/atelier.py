"""lib/themes/atelier.py · "Atelier Dark" 主题

把已批准的 b-atelier-dark mockup 移植成参数化、可复用于任意行业的主题模块。
所有文字/品牌/导航/正文都来自传入的 ctx 字典 —— 没有任何皮革/MERIDIAN 等硬编码内容。
CSS 逐字复用 mockup 的 <style>（独立常量，禁止 .format()/% 误伤 { }）。
"""
from lib.themes._base import esc

NAME = "atelier-dark"
LABEL = "Atelier Dark"

# Google Fonts <link>（连同 preconnect 一起从 mockup 搬来）
_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;1,9..144,300;1,9..144,400&family=Hanken+Grotesk:wght@400;500;600&family=Spline+Sans+Mono:wght@400;500&display=swap" rel="stylesheet">'
)

# ============ mockup 的整段 <style>，逐字复用 ============
# 注意：作为独立常量字符串拼接，绝不能用 .format()/% —— 否则 CSS 里的 { } 会被误吞。
# 额外补一条裸 <table> 在窄屏可横向滚动的规则（mockup 原本依赖 .table-scroll 外层 wrapper，
# 但正文可能给的是裸 <table>，所以追加 .article table{display:block;overflow-x:auto}）。
_CSS = """
  :root{
    --bg:#121013;          /* warm charcoal */
    --panel:#1A1715;
    --panel-2:#15120F;
    --ink:#ECE6DC;         /* warm white */
    --accent:#C9A36B;      /* aged copper */
    --accent-soft:#A88A5C;
    --muted:#9A9187;
    --line:rgba(236,230,220,.12);
    --line-strong:rgba(201,163,107,.34);
    --serif:"Fraunces", Georgia, serif;
    --sans:"Hanken Grotesk", system-ui, sans-serif;
    --mono:"Spline Sans Mono", ui-monospace, monospace;
  }

  *{box-sizing:border-box;}
  html{scroll-behavior:smooth;}
  body{
    margin:0;
    background:var(--bg);
    color:var(--ink);
    font-family:var(--sans);
    font-weight:400;
    line-height:1.8;
    font-size:17px;
    -webkit-font-smoothing:antialiased;
    text-rendering:optimizeLegibility;
    position:relative;
    overflow-x:hidden;
  }

  /* very faint film grain overlay */
  body::after{
    content:"";
    position:fixed;
    inset:0;
    pointer-events:none;
    z-index:9999;
    opacity:.04;
    mix-blend-mode:overlay;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  ::selection{background:rgba(201,163,107,.28);color:var(--ink);}

  a{color:var(--accent);text-decoration:none;}

  .wrap{max-width:1180px;margin:0 auto;padding:0 40px;}

  /* ============ STICKY TOP BAR ============ */
  header.top{
    position:sticky;top:0;z-index:100;
    background:rgba(18,16,19,.72);
    backdrop-filter:blur(14px) saturate(140%);
    -webkit-backdrop-filter:blur(14px) saturate(140%);
    border-bottom:1px solid var(--line);
  }
  .top-inner{
    display:flex;align-items:center;justify-content:space-between;
    gap:24px;height:74px;
  }
  .brand{display:flex;align-items:baseline;gap:14px;white-space:nowrap;}
  .brand .mark{
    font-family:var(--serif);
    font-weight:500;
    font-size:21px;
    letter-spacing:.14em;
    text-transform:uppercase;
    color:var(--ink);
  }
  .brand .mark b{color:var(--accent);font-weight:500;}
  .brand .est{
    font-family:var(--mono);
    font-size:10.5px;
    letter-spacing:.16em;
    text-transform:uppercase;
    color:var(--muted);
  }
  nav.main{display:flex;gap:0;align-items:center;flex-wrap:nowrap;}
  nav.main a{
    font-size:12.5px;
    letter-spacing:.04em;
    color:var(--muted);
    padding:8px 13px;
    position:relative;
    transition:color .25s ease;
    white-space:nowrap;
  }
  nav.main a:hover{color:var(--ink);}
  nav.main a.active{color:var(--ink);}
  nav.main a.active::after{
    content:"";
    position:absolute;left:13px;right:13px;bottom:0;
    height:1px;background:var(--accent);
  }

  /* ============ BREADCRUMB ============ */
  .breadcrumb{
    border-bottom:1px solid var(--line);
  }
  .breadcrumb .wrap{
    padding-top:16px;padding-bottom:16px;
    font-family:var(--mono);
    font-size:11px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--muted);
  }
  .breadcrumb a{color:var(--muted);}
  .breadcrumb a:hover{color:var(--accent);}
  .breadcrumb .sep{color:var(--accent-soft);margin:0 8px;opacity:.6;}
  .breadcrumb .here{color:var(--ink);}

  /* ============ HERO ============ */
  .hero{
    position:relative;
    padding:96px 0 84px;
    border-bottom:1px solid var(--line);
    background:
      radial-gradient(120% 80% at 88% -10%, rgba(201,163,107,.10), transparent 55%),
      linear-gradient(180deg, var(--panel-2) 0%, var(--bg) 100%);
    overflow:hidden;
  }
  /* faint vertical grid lines */
  .hero::before{
    content:"";
    position:absolute;inset:0;
    background-image:linear-gradient(90deg,var(--line) 1px,transparent 1px);
    background-size:calc((100% - 0px)/6) 100%;
    opacity:.5;
    pointer-events:none;
    mask-image:linear-gradient(180deg,transparent,#000 18%,#000 82%,transparent);
    -webkit-mask-image:linear-gradient(180deg,transparent,#000 18%,#000 82%,transparent);
  }
  .hero .wrap{position:relative;z-index:1;}

  .hero-grid{
    display:grid;
    grid-template-columns:1fr auto;
    gap:48px;
    align-items:end;
  }

  .kicker{
    display:inline-flex;align-items:center;gap:12px;
    font-family:var(--mono);
    font-size:11px;letter-spacing:.22em;text-transform:uppercase;
    color:var(--accent);
    margin-bottom:34px;
  }
  .kicker .num{
    color:var(--muted);
    border:1px solid var(--line-strong);
    border-radius:2px;
    padding:3px 8px;
    font-size:10px;
    letter-spacing:.1em;
  }
  .kicker .dash{width:46px;height:1px;background:var(--accent-soft);opacity:.7;}

  .hero h2.display{
    font-family:var(--serif);
    font-weight:300;
    font-optical-sizing:auto;
    font-size:clamp(2.7rem, 6.4vw, 5.5rem);
    line-height:1.02;
    letter-spacing:-.01em;
    margin:0 0 30px;
    color:var(--ink);
    max-width:14ch;
  }
  .hero h2.display em{
    font-style:italic;
    font-weight:400;
    color:var(--accent);
  }
  .hero .lede{
    font-size:clamp(1rem, 1.5vw, 1.18rem);
    line-height:1.7;
    color:var(--muted);
    max-width:54ch;
    margin:0 0 40px;
    font-weight:400;
  }

  .chips{display:flex;flex-wrap:wrap;gap:10px;}
  .chip{
    font-family:var(--mono);
    font-size:11.5px;letter-spacing:.06em;
    color:var(--ink);
    padding:7px 14px;
    border:1px solid var(--line-strong);
    border-radius:100px;
    background:rgba(201,163,107,.05);
    white-space:nowrap;
  }
  .chip b{color:var(--accent);font-weight:500;}

  /* right rail meta block */
  .hero-meta{
    border-left:1px solid var(--line);
    padding-left:30px;
    min-width:200px;
    text-align:left;
  }
  .hero-meta .row{margin-bottom:24px;}
  .hero-meta .row:last-child{margin-bottom:0;}
  .hero-meta .k{
    font-family:var(--mono);
    font-size:10px;letter-spacing:.18em;text-transform:uppercase;
    color:var(--muted);
    display:block;margin-bottom:6px;
  }
  .hero-meta .v{
    font-family:var(--serif);
    font-size:1.35rem;
    font-weight:400;
    color:var(--ink);
    line-height:1.2;
  }
  .hero-meta .v small{
    font-family:var(--sans);
    font-size:.7rem;color:var(--muted);
    letter-spacing:.04em;display:block;margin-top:3px;
  }

  /* hero load animation */
  .anim{opacity:0;transform:translateY(16px);animation:rise .9s cubic-bezier(.2,.7,.2,1) forwards;}
  .d1{animation-delay:.05s;} .d2{animation-delay:.16s;} .d3{animation-delay:.28s;}
  .d4{animation-delay:.40s;} .d5{animation-delay:.52s;} .d6{animation-delay:.62s;}
  @keyframes rise{to{opacity:1;transform:translateY(0);}}
  @media (prefers-reduced-motion:reduce){
    .anim{animation:none;opacity:1;transform:none;}
  }

  /* ============ ARTICLE ============ */
  .article-shell{
    background:linear-gradient(180deg, var(--bg), var(--panel-2) 140%);
    padding:84px 0 40px;
  }
  article{
    max-width:760px;
    margin:0 auto;
  }

  article h1{
    font-family:var(--serif);
    font-weight:300;
    font-size:clamp(2rem,3.6vw,2.9rem);
    line-height:1.1;
    letter-spacing:-.01em;
    color:var(--ink);
    margin:0 0 36px;
    padding-bottom:30px;
    border-bottom:1px solid var(--line);
  }

  article h2{
    font-family:var(--serif);
    font-weight:400;
    font-size:clamp(1.5rem,2.6vw,2rem);
    line-height:1.18;
    letter-spacing:-.005em;
    color:var(--ink);
    margin:72px 0 22px;
    position:relative;
    padding-top:26px;
    counter-increment:sec;
  }
  article h2::before{
    content:"0" counter(sec);
    position:absolute;top:0;left:0;
    font-family:var(--mono);
    font-size:11px;letter-spacing:.16em;
    color:var(--accent);
    font-weight:400;
  }
  article{counter-reset:sec;}

  article h3{
    font-family:var(--serif);
    font-weight:500;
    font-size:1.3rem;
    color:var(--ink);
    margin:40px 0 14px;
  }

  article p{
    margin:0 0 24px;
    color:#D9D2C7;
    font-size:17px;
    line-height:1.82;
  }

  /* drop-cap on first paragraph */
  article > p:first-of-type::first-letter{
    font-family:var(--serif);
    font-weight:300;
    float:left;
    font-size:4.6rem;
    line-height:.78;
    padding:8px 14px 0 0;
    color:var(--accent);
  }

  article a{
    color:var(--accent);
    border-bottom:1px solid var(--line-strong);
    padding-bottom:1px;
    transition:color .2s ease, border-color .2s ease;
  }
  article a:hover{color:var(--ink);border-bottom-color:var(--accent);}

  article ul{
    list-style:none;
    margin:0 0 30px;
    padding:0;
  }
  article ul li{
    position:relative;
    padding:14px 0 14px 34px;
    border-bottom:1px solid var(--line);
    color:#D9D2C7;
    line-height:1.65;
  }
  article ul li:first-child{border-top:1px solid var(--line);}
  article ul li::before{
    content:"";
    position:absolute;left:6px;top:24px;
    width:7px;height:7px;
    border:1px solid var(--accent);
    transform:rotate(45deg);
  }

  /* ============ DATASHEET TABLE ============ */
  .table-scroll{
    overflow-x:auto;
    margin:36px 0 40px;
    border:1px solid var(--line);
    border-radius:4px;
    background:var(--panel);
    -webkit-overflow-scrolling:touch;
  }
  /* 裸 <table>（正文无外层 .table-scroll wrapper）也要能在窄屏横向滚动 */
  article table{
    display:block;
    overflow-x:auto;
    -webkit-overflow-scrolling:touch;
    width:100%;
    border-collapse:collapse;
    min-width:560px;
    font-size:14.5px;
  }
  .table-scroll table{min-width:560px;}
  article thead th{
    font-family:var(--mono);
    font-weight:500;
    font-size:10.5px;
    letter-spacing:.13em;
    text-transform:uppercase;
    color:var(--accent);
    text-align:left;
    padding:18px 20px;
    background:var(--panel-2);
    border-bottom:1px solid var(--line-strong);
    white-space:nowrap;
  }
  article tbody td{
    padding:15px 20px;
    border-bottom:1px solid var(--line);
    color:#D9D2C7;
    vertical-align:top;
    line-height:1.5;
  }
  article tbody tr:last-child td{border-bottom:none;}
  article tbody tr:hover td{background:rgba(201,163,107,.045);}
  /* first col = property name, serif; second col = numeric, mono */
  article tbody td:first-child{
    font-family:var(--serif);
    font-weight:500;
    color:var(--ink);
    font-size:15px;
    white-space:nowrap;
  }
  article tbody td:nth-child(2){
    font-family:var(--mono);
    font-size:13px;
    color:var(--accent);
    white-space:nowrap;
  }
  article tbody td:nth-child(3){
    font-family:var(--mono);
    font-size:12px;
    color:var(--muted);
    letter-spacing:.02em;
    white-space:nowrap;
  }

  article blockquote{
    margin:36px 0;
    padding:6px 0 6px 28px;
    border-left:2px solid var(--accent);
    font-family:var(--serif);
    font-style:italic;
    font-weight:300;
    font-size:1.3rem;
    line-height:1.5;
    color:var(--ink);
  }

  /* ============ FOOTER ============ */
  footer.site{
    border-top:1px solid var(--line);
    background:var(--panel-2);
    padding:54px 0 60px;
  }
  footer.site .wrap{
    display:flex;align-items:flex-start;justify-content:space-between;
    gap:40px;flex-wrap:wrap;
  }
  footer .f-brand .mark{
    font-family:var(--serif);
    font-weight:500;
    font-size:18px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--ink);
  }
  footer .f-brand .mark b{color:var(--accent);font-weight:500;}
  footer .f-brand .est{
    font-family:var(--mono);
    font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--muted);margin-top:8px;
  }
  footer .f-meta{
    font-family:var(--mono);
    font-size:11px;letter-spacing:.06em;
    color:var(--muted);
    line-height:2;
    text-align:right;
  }
  footer .f-meta .sep{color:var(--accent-soft);opacity:.5;margin:0 6px;}

  /* ============ INDEX GROUPS ============ */
  .idx-group{margin:0 0 8px;}
  .idx-item{
    position:relative;
    padding:14px 0 14px 34px;
    border-bottom:1px solid var(--line);
    line-height:1.65;
  }
  .idx-item:first-child{border-top:1px solid var(--line);}
  .idx-item::before{
    content:"";
    position:absolute;left:6px;top:24px;
    width:7px;height:7px;
    border:1px solid var(--accent);
    transform:rotate(45deg);
  }
  .idx-title{
    font-family:var(--serif);font-weight:500;font-size:1.18rem;
    color:var(--ink);border-bottom:none;display:inline-block;margin-bottom:6px;
  }
  a.idx-title:hover{color:var(--accent);border-bottom:none;}
  .idx-kind{
    display:block;font-family:var(--mono);font-size:10px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--accent);margin-bottom:8px;
  }
  .idx-teaser{
    display:block;color:var(--muted);font-size:15px;line-height:1.6;
  }
  .idx-skip{
    font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--muted);border:1px solid var(--line);border-radius:2px;
    padding:2px 7px;margin-left:10px;vertical-align:middle;
  }

  /* ============ RESPONSIVE ============ */
  @media (max-width:1040px){
    nav.main a{padding:8px 9px;font-size:12px;}
  }
  @media (max-width:880px){
    .hero-grid{grid-template-columns:1fr;gap:40px;}
    .hero-meta{
      border-left:none;border-top:1px solid var(--line);
      padding-left:0;padding-top:26px;
      display:flex;gap:40px;flex-wrap:wrap;
    }
    .hero-meta .row{margin-bottom:0;}
  }
  @media (max-width:720px){
    .wrap{padding:0 22px;}
    .top-inner{height:auto;padding:16px 0;flex-direction:column;align-items:flex-start;gap:14px;}
    .brand{order:0;}
    nav.main{
      order:1;width:100%;
      overflow-x:auto;
      gap:0;
      -webkit-overflow-scrolling:touch;
      scrollbar-width:none;
      padding-bottom:2px;
    }
    nav.main::-webkit-scrollbar{display:none;}
    nav.main a{padding:6px 12px 6px 0;font-size:12px;}
    nav.main a.active::after{left:0;right:12px;}
    .hero{padding:60px 0 56px;}
    .article-shell{padding:56px 0 30px;}
    article > p:first-of-type::first-letter{font-size:3.6rem;}
    .hero-meta{gap:28px;}
  }
"""


def _brand_mark(org: str) -> str:
    """品牌标记：把 org 文本（已 esc）放进 .mark。
    mockup 把品牌拆成普通字 + 高亮 <b>；我们不知道品牌分词，故整体作为普通字，
    无行业含义；颜色仍沿用主题。"""
    return '<span class="mark">' + esc(org) + "</span>"


def _nav_html(nav) -> str:
    """导航：active 项加 mockup 的高亮态 class="active"。pillar 在前由调用方排序保证。"""
    out = []
    for item in (nav or []):
        label = esc(item.get("label"))
        href = esc(item.get("href"))
        cls = ' class="active"' if item.get("active") else ""
        out.append('<a href="' + href + '"' + cls + ">" + label + "</a>")
    return "".join(out)


def _crumbs_html(crumbs) -> str:
    """面包屑：href 为 None 即当前页不可点（.here），否则可点。用 mockup 的 .sep 分隔。"""
    parts = []
    for c in (crumbs or []):
        label = esc(c.get("label"))
        href = c.get("href")
        if href is None:
            parts.append('<span class="here">' + label + "</span>")
        else:
            parts.append('<a href="' + esc(href) + '">' + label + "</a>")
    return '<span class="sep">›</span>'.join(parts)


def _chips_html(chips) -> str:
    """规格小标签：字符串列表；空就返回空串（不渲染那块）。"""
    if not chips:
        return ""
    spans = []
    for c in chips:
        spans.append('<span class="chip">' + esc(c) + "</span>")
    return '<div class="chips anim d4">' + "".join(spans) + "</div>"


def _doc_head(lang, title, meta_desc, robots, jsonld) -> str:
    """构造 <head>：title/meta/robots/fonts/css/jsonld。"""
    return (
        "<!doctype html>\n"
        '<html lang="' + esc(lang) + '">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>" + esc(title) + "</title>\n"
        '<meta name="description" content="' + esc(meta_desc) + '">\n'
        '<meta name="robots" content="' + esc(robots) + '">\n'
        + _FONTS + "\n"
        "<style>" + _CSS + "</style>\n"
        + (jsonld or "")
        + "\n</head>\n"
    )


def render_page(ctx: dict) -> str:
    """返回单页完整 <!doctype html> 文档。"""
    org = ctx.get("org")
    title = ctx.get("title")
    meta_desc = ctx.get("meta_desc")
    type_label = ctx.get("type_label") or "Doc"
    body_html = ctx.get("body_html") or ""
    warn_html = ctx.get("warn_html") or ""
    jsonld = ctx.get("jsonld") or ""

    head = _doc_head(ctx.get("lang"), title, meta_desc, ctx.get("robots"), jsonld)

    # hero kicker：用 type_label 拼无行业含义的技术装饰（蓝图风 SPEC SHEET / REV.A 的等价）。
    kicker_label = esc(type_label) + " · DOC"

    # hero 大标题：当正文已含唯一 <h1>（body_has_h1==True，几乎总是），
    # 这里必须用非 h1（role="heading" aria-level="1"）。为 False 时 hero 提供 h1。
    if ctx.get("body_has_h1"):
        hero_heading = (
            '<div class="display anim d2" role="heading" aria-level="1">'
            + esc(title) + "</div>"
        )
    else:
        hero_heading = '<h1 class="display anim d2">' + esc(title) + "</h1>"

    chips_block = _chips_html(ctx.get("chips"))

    # 右栏 meta block：用 type_label + updated，无行业硬编码。
    updated = esc(ctx.get("updated"))
    hero_meta = (
        '<aside class="hero-meta anim d5">'
        '<div class="row"><span class="k">Type</span>'
        '<span class="v">' + esc(type_label) + "<small>document</small></span></div>"
        '<div class="row"><span class="k">Reference</span>'
        '<span class="v">SPEC SHEET<small>REV.A · FIG.01</small></span></div>'
        '<div class="row"><span class="k">Updated</span>'
        '<span class="v">' + (updated or "&mdash;") + "<small>last revision</small></span></div>"
        "</aside>"
    )

    body = (
        "<body>\n"
        '  <header class="top">\n'
        '    <div class="wrap top-inner">\n'
        '      <div class="brand">' + _brand_mark(org) + "</div>\n"
        '      <nav class="main">' + _nav_html(ctx.get("nav")) + "</nav>\n"
        "    </div>\n"
        "  </header>\n"
        '  <div class="breadcrumb"><div class="wrap">'
        + _crumbs_html(ctx.get("crumbs")) + "</div></div>\n"
        '  <section class="hero"><div class="wrap"><div class="hero-grid">\n'
        '    <div class="hero-main">\n'
        '      <div class="kicker anim d1"><span class="num">01</span>'
        "<span>" + kicker_label + '</span><span class="dash"></span></div>\n'
        "      " + hero_heading + "\n"
        '      <p class="lede anim d3">' + esc(meta_desc) + "</p>\n"
        "      " + chips_block + "\n"
        "    </div>\n"
        "    " + hero_meta + "\n"
        "  </div></div></section>\n"
        '  <div class="article-shell"><div class="wrap">\n'
        + warn_html + "\n"
        "    <article>\n" + body_html + "\n    </article>\n"
        "  </div></div>\n"
        '  <footer class="site"><div class="wrap">\n'
        '    <div class="f-brand"><div class="mark">' + esc(org) + "</div>"
        '<div class="est">' + esc(type_label) + " &middot; document</div></div>\n"
        '    <div class="f-meta">&copy; ' + esc(ctx.get("year")) + " " + esc(org)
        + '<span class="sep">&middot;</span>' + esc(type_label) + "</div>\n"
        "  </div></footer>\n"
        "</body>\n</html>"
    )
    return head + body


def _index_group_html(group) -> str:
    """渲染首页一个 group：<h2> 组标题 + 该组 items。"""
    label = esc(group.get("label"))
    out = ["<h2>" + label + "</h2>", '<div class="idx-group">']
    for it in (group.get("items") or []):
        title = esc(it.get("title"))
        href = it.get("href")
        type_label = esc(it.get("type_label"))
        teaser = esc(it.get("teaser"))
        passed = it.get("passed")
        out.append('<div class="idx-item">')
        if href is None or not passed:
            # 未过质检：标题不可点，打 skipped 标记
            out.append(
                '<span class="idx-title">' + title
                + '<span class="idx-skip">skipped</span></span>'
            )
        else:
            out.append('<a class="idx-title" href="' + esc(href) + '">' + title + "</a>")
        out.append('<span class="idx-kind">' + type_label + "</span>")
        out.append('<span class="idx-teaser">' + teaser + "</span>")
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def render_index(ctx: dict) -> str:
    """返回首页完整 <!doctype html> 文档。"""
    org = ctx.get("org")
    site_name = ctx.get("site_name")
    sub = ctx.get("sub")
    stats = ctx.get("stats") or {}

    # 首页 <title> 用 site_name。无 jsonld/meta_desc 约定项，meta 用 sub。
    head = _doc_head(ctx.get("lang"), site_name, sub, ctx.get("robots"), "")

    total = esc(stats.get("total"))
    n_pass = esc(stats.get("n_pass"))
    n_skip = esc(stats.get("n_skip"))

    hero_meta = (
        '<aside class="hero-meta anim d5">'
        '<div class="row"><span class="k">Pages</span>'
        '<span class="v">' + total + "<small>total</small></span></div>"
        '<div class="row"><span class="k">Published</span>'
        '<span class="v">' + n_pass + "<small>passed QA</small></span></div>"
        '<div class="row"><span class="k">Skipped</span>'
        '<span class="v">' + n_skip + "<small>not published</small></span></div>"
        "</aside>"
    )

    groups_html = "".join(_index_group_html(g) for g in (ctx.get("groups") or []))

    body = (
        "<body>\n"
        '  <header class="top">\n'
        '    <div class="wrap top-inner">\n'
        '      <div class="brand">' + _brand_mark(org) + "</div>\n"
        '      <nav class="main">' + _nav_html(ctx.get("nav")) + "</nav>\n"
        "    </div>\n"
        "  </header>\n"
        '  <div class="breadcrumb"><div class="wrap">'
        '<span class="here">' + esc(site_name) + "</span></div></div>\n"
        '  <section class="hero"><div class="wrap"><div class="hero-grid">\n'
        '    <div class="hero-main">\n'
        '      <div class="kicker anim d1"><span class="num">00</span>'
        "<span>INDEX · DOC</span><span class=\"dash\"></span></div>\n"
        '      <div class="display anim d2" role="heading" aria-level="1">'
        + esc(site_name) + "</div>\n"
        '      <p class="lede anim d3">' + esc(sub) + "</p>\n"
        "    </div>\n"
        "    " + hero_meta + "\n"
        "  </div></div></section>\n"
        '  <div class="article-shell"><div class="wrap">\n'
        "    <article>\n" + groups_html + "\n    </article>\n"
        "  </div></div>\n"
        '  <footer class="site"><div class="wrap">\n'
        '    <div class="f-brand"><div class="mark">' + esc(org) + "</div>"
        '<div class="est">' + esc(sub) + "</div></div>\n"
        '    <div class="f-meta">&copy; ' + esc(ctx.get("year")) + " " + esc(org)
        + '<span class="sep">&middot;</span>' + esc(site_name) + "</div>\n"
        "  </div></footer>\n"
        "</body>\n</html>"
    )
    return head + body
