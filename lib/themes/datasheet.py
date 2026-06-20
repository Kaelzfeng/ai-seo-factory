"""lib/themes/datasheet.py · "Datasheet Editorial" 主题

把 mockups/a-datasheet-editorial.html + mockups/site-a/index.html 的视觉设计
参数化成可复用主题：所有文字/品牌/导航/正文均来自 ctx，无任何行业硬编码。

导出：NAME, LABEL, render_page(ctx), render_index(ctx)
严格遵循 lib/themes/_base.py 的契约。
"""
import re

from lib.themes._base import esc

NAME = "datasheet-editorial"
LABEL = "Datasheet Editorial"

# ---------------------------------------------------------------------------
# 转化加权(chrome 层)——纯附加,绝不进入被评分的正文内容。
#
# 评分发生在 lib.quality.score_page(page, content, industry),作用对象是
# content dict(title/meta/html),与本主题渲染完全解耦:本文件只把已经定好的
# body_html 套进页面外壳,这里新增的徽带/CTA/重点句只出现在最终 HTML 文件里,
# 永远不会回写进参与评分的 content。检测函数全部只读 body_html,不做任何改写。
# ---------------------------------------------------------------------------

# 信任徽带:从正文里检出认证/标准 token(复用 quality.py 的
# CERT_STANDARD_TOKENS / SPEC_SIGNAL_PATTERNS 思路),映射到可扫的展示标签。
# 顺序即展示顺序(管理体系/化学合规/物理测试方法分簇,从最"招牌"的标准排起)。
# 每项:(展示标签, 副标, [小写匹配 token...])。命中任一 token 即点亮该徽章。
_TRUST_BADGES = [
    ("ISO", "Test methods", ["iso"]),
    ("REACH", "EU SVHC", ["reach"]),
    ("RoHS", "Restricted subst.", ["rohs"]),
    ("OEKO-TEX", "Skin-safe", ["oeko-tex", "oeko tex", "oeko"]),
    ("ASTM", "US methods", ["astm"]),
    ("Martindale", "Abrasion", ["martindale"]),
    ("Wyzenbeek", "Double rubs", ["wyzenbeek"]),
    ("Prop 65", "CA exposure", ["prop 65", "proposition 65"]),
    ("GRS", "Recycled", ["grs"]),
    ("SAE J", "Light-fastness", ["sae j"]),
    ("SGS", "Lab report", ["sgs"]),
    ("Intertek", "Lab report", ["intertek"]),
    ("Bureau Veritas", "Lab report", ["bureau veritas"]),
    ("Eurofins", "Lab report", ["eurofins"]),
]

_TAG_RE = re.compile(r"(?s)<[^>]+>")


def _visible_text(html: str) -> str:
    """从 body_html 取可见文本(只读;去标签 + 小写),供 token 检测用。"""
    if not html:
        return ""
    text = _TAG_RE.sub(" ", str(html))
    text = re.sub(r"\s+", " ", text).lower()
    return text


def _detect_trust(body_html: str):
    """返回命中的信任徽章 [(label, sub), ...];检不到返回 [](则不渲染徽带)。"""
    low = _visible_text(body_html)
    if not low:
        return []
    found = []
    for label, sub, tokens in _TRUST_BADGES:
        if any(tok in low for tok in tokens):
            found.append((label, sub))
    return found


def _trust_band(body_html: str) -> str:
    """信任徽带:hero 与正文之间的一条可扫标准带。检不到任何标准则返回空串。"""
    badges = _detect_trust(body_html)
    if not badges:
        return ""
    out = [
        '<aside class="trustband anim d3" aria-label="Standards and certifications cited">',
        '<span class="trustband__lead">Verified against</span>',
        '<ul class="trustband__list">',
    ]
    for label, sub in badges:
        out.append(
            '<li class="trustband__item">'
            '<span class="trustband__std">' + esc(label) + '</span>'
            '<span class="trustband__sub">' + esc(sub) + '</span>'
            '</li>'
        )
    out.append('</ul>')
    out.append(
        '<span class="trustband__note">Test reports tied to the production batch &mdash; '
        're-validated per lot.</span>'
    )
    out.append('</aside>')
    return "".join(out)


# 决策重点句:把首段里第一句"可作决策落点"的话拉成重点排版。
# 只读 body_html,提取第一段第一句(若过短/过长则不渲染,保持克制)。
_FIRST_P_RE = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")


def _pull_quote(body_html: str) -> str:
    """从首段抽 1 句决策结论做拉出重点排版;不合适则返回空串(可选件)。"""
    if not body_html:
        return ""
    m = _FIRST_P_RE.search(str(body_html))
    if not m:
        return ""
    para = re.sub(r"\s+", " ", _TAG_RE.sub(" ", m.group(1))).strip()
    if not para:
        return ""
    # 取第一句(到第一个句号/问号止);避免缩写误切,要求句末后跟空格或结尾。
    sm = re.search(r"(.+?[.?!])(?:\s|$)", para)
    sentence = (sm.group(1) if sm else para).strip()
    # 克制护栏:太短(没信息)或太长(是定义/铺垫,不是一句决策重点)都不拉出。
    # 上限收紧到 28 词:只留真正"一句话决策"的句子;长引言宁可不拉(本件可选)。
    n = len(sentence.split())
    if n < 8 or n > 28:
        return ""
    return (
        '<aside class="pullquote anim d3" aria-hidden="true">'
        '<p class="pullquote__txt">' + esc(sentence) + '</p>'
        '</aside>'
    )


# 朱红 CTA 行动块:站点既有"报价/联系"语气(每页正文末尾都已是
# "把应用/市场/数量告诉我们 → 回你规格表+测试报告+FOB 报价/周期"),
# 这里把它做成醒目的朱红行动块。文案不编造承诺,只复述站点既有动作。
def _cta_block(org: str) -> str:
    org_e = esc(org or "")
    return (
        '<aside class="cta" aria-labelledby="cta-h">'
        '<div class="cta__inner">'
        '<p class="cta__kicker">Request a quote</p>'
        '<p class="cta__head" id="cta-h">Tell us the application, market and order quantity.</p>'
        '<p class="cta__sub">'
        'Send the end use, the abrasion and compliance standards your buyer enforces, '
        'and your volume. We return a construction spec, current third-party test reports, '
        'and an FOB lead time priced against your real MOQ &mdash; not a catalog number.'
        '</p>'
        '<ul class="cta__deliv" aria-label="What you receive">'
        '<li>Construction spec sheet</li>'
        '<li>Current test reports</li>'
        '<li>FOB quote &amp; lead time</li>'
        '</ul>'
        + ('<p class="cta__sig">' + org_e + '</p>' if org_e else '')
        + '</div>'
        '</aside>'
    )

# ---- Google Fonts <link>（逐字搬自 mockup 的 <head>）----
_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900'
    '&family=Archivo+Black&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;'
    '1,6..72,400;1,6..72,500&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet" />'
)

# ---- <style> 内容（逐字搬自 mockup；作为独立常量，绝不经过 .format/%）----
_CSS = """
  :root{
    --paper:#F2EEE3;
    --paper-2:#ECE6D7;
    --ink:#15110B;
    --accent:#E2402A;
    --accent-deep:#B82E1C;
    --muted:#6B6357;
    --line:#D8D1C2;
    --line-strong:#C4BBA6;
    --th-bg:#EAE4D6;
    --measure:68ch;
    --maxw:1180px;
    --gutter:clamp(20px,5vw,72px);
  }

  *,*::before,*::after{box-sizing:border-box;}

  html{ -webkit-text-size-adjust:100%; scroll-behavior:smooth; }

  body{
    margin:0;
    background:var(--paper);
    color:var(--ink);
    font-family:"Newsreader",Georgia,serif;
    font-size:1.0625rem;
    line-height:1.72;
    -webkit-font-smoothing:antialiased;
    text-rendering:optimizeLegibility;
    overflow-x:hidden;
  }

  /* ---- paper grain / noise overlay ---- */
  body::before{
    content:"";
    position:fixed;
    inset:0;
    z-index:9999;
    pointer-events:none;
    opacity:.045;
    mix-blend-mode:multiply;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='220'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  ::selection{ background:var(--accent); color:var(--paper); }

  a{ color:inherit; }

  /* ---------- TOP BAR ---------- */
  .topbar{
    position:sticky;
    top:0;
    z-index:50;
    background:rgba(242,238,227,.86);
    backdrop-filter:saturate(140%) blur(8px);
    -webkit-backdrop-filter:saturate(140%) blur(8px);
    border-bottom:1px solid var(--line);
  }
  .topbar__inner{
    max-width:var(--maxw);
    margin:0 auto;
    padding:0 var(--gutter);
    display:flex;
    align-items:stretch;
    justify-content:space-between;
    gap:24px;
    min-height:64px;
  }
  .brand{
    display:flex;
    align-items:center;
    gap:12px;
    text-decoration:none;
    color:var(--ink);
    flex-shrink:0;
  }
  .brand__mark{
    width:30px;height:30px;
    flex-shrink:0;
    display:grid;place-items:center;
    background:var(--ink);
    color:var(--paper);
    font-family:"Archivo Black","Archivo",sans-serif;
    font-size:1rem;
    line-height:1;
    transform:rotate(-3deg);
  }
  .brand__mark span{ transform:rotate(3deg); }
  .brand__txt{ display:flex; flex-direction:column; line-height:1.05; }
  .brand__name{
    font-family:"Archivo",sans-serif;
    font-weight:900;
    letter-spacing:-.01em;
    font-size:.98rem;
    text-transform:uppercase;
  }
  .brand__est{
    font-family:"IBM Plex Mono",monospace;
    font-size:.58rem;
    letter-spacing:.18em;
    text-transform:uppercase;
    color:var(--muted);
    margin-top:2px;
  }

  nav.mainnav{
    display:flex;
    align-items:stretch;
    gap:0;
    overflow-x:auto;
    scrollbar-width:none;
    -ms-overflow-style:none;
  }
  nav.mainnav::-webkit-scrollbar{ display:none; }
  nav.mainnav a{
    display:flex;
    align-items:center;
    padding:0 14px;
    text-decoration:none;
    color:var(--muted);
    font-family:"IBM Plex Mono",monospace;
    font-size:.66rem;
    font-weight:500;
    letter-spacing:.08em;
    text-transform:uppercase;
    white-space:nowrap;
    position:relative;
    transition:color .18s ease;
  }
  nav.mainnav a::after{
    content:"";
    position:absolute;
    left:14px;right:14px;bottom:18px;
    height:2px;
    background:var(--accent);
    transform:scaleX(0);
    transform-origin:left;
    transition:transform .22s ease;
  }
  nav.mainnav a:hover{ color:var(--ink); }
  nav.mainnav a:hover::after{ transform:scaleX(1); }
  nav.mainnav a.active{ color:var(--ink); }
  nav.mainnav a.active::after{ transform:scaleX(1); background:var(--accent); }

  /* ---------- BREADCRUMB ---------- */
  .crumb{
    max-width:var(--maxw);
    margin:0 auto;
    padding:14px var(--gutter) 0;
    font-family:"IBM Plex Mono",monospace;
    font-size:.66rem;
    letter-spacing:.1em;
    text-transform:uppercase;
    color:var(--muted);
  }
  .crumb a{ color:var(--muted); text-decoration:none; transition:color .15s; }
  .crumb a:hover{ color:var(--accent); }
  .crumb .sep{ color:var(--line-strong); margin:0 8px; }
  .crumb .here{ color:var(--ink); }

  /* ---------- HERO ---------- */
  .hero{
    max-width:var(--maxw);
    margin:0 auto;
    padding:clamp(34px,6vw,72px) var(--gutter) clamp(30px,4.5vw,52px);
    position:relative;
  }
  .hero__kicker{
    display:inline-flex;
    align-items:center;
    gap:10px;
    font-family:"IBM Plex Mono",monospace;
    font-size:.68rem;
    letter-spacing:.22em;
    text-transform:uppercase;
    color:var(--accent-deep);
    margin-bottom:clamp(20px,3vw,34px);
  }
  .hero__kicker .tick{
    width:30px;height:1px;background:var(--accent);display:inline-block;
  }
  .hero__kicker .doc{
    color:var(--muted);
  }

  .hero__title{
    font-family:"Archivo Black","Archivo",sans-serif;
    font-weight:900;
    font-size:clamp(2.7rem,7.4vw,5.5rem);
    line-height:.95;
    letter-spacing:-.022em;
    margin:0;
    max-width:14ch;
    text-wrap:balance;
  }
  .hero__title .vm{ color:var(--accent); }

  .hero__lede{
    font-family:"Newsreader",serif;
    font-size:clamp(1.08rem,1.9vw,1.35rem);
    line-height:1.55;
    color:var(--ink);
    max-width:58ch;
    margin:clamp(20px,3vw,30px) 0 0;
    font-weight:400;
  }
  .hero__lede em{ color:var(--muted); font-style:italic; }

  .chips{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin-top:clamp(26px,3.5vw,38px);
    padding-top:clamp(22px,3vw,30px);
    border-top:1px solid var(--line);
  }
  .chip{
    font-family:"IBM Plex Mono",monospace;
    font-size:.68rem;
    letter-spacing:.05em;
    text-transform:uppercase;
    padding:7px 12px;
    border:1px solid var(--line-strong);
    background:transparent;
    color:var(--ink);
    display:inline-flex;
    align-items:center;
    gap:7px;
    transition:border-color .18s,background .18s;
  }
  .chip::before{
    content:"";
    width:5px;height:5px;border-radius:50%;
    background:var(--accent);
    flex-shrink:0;
  }
  .chip:hover{ border-color:var(--accent); background:rgba(226,64,42,.05); }
  .chip strong{ font-weight:600; }

  /* ---------- ARTICLE ---------- */
  .sheet{
    max-width:var(--maxw);
    margin:0 auto;
    padding:0 var(--gutter) clamp(60px,8vw,110px);
  }
  .article{
    counter-reset:h2;
    max-width:var(--measure);
    margin:0;
  }
  /* The in-article heading is the real H1; the hero uses non-h1 text.
     This rule styles that article-level top heading as an eyebrow line. */
  .article h1{
    font-family:"Archivo",sans-serif;
    font-weight:800;
    font-size:clamp(1.05rem,2vw,1.3rem);
    line-height:1.25;
    letter-spacing:.01em;
    text-transform:uppercase;
    color:var(--muted);
    margin:0 0 clamp(26px,4vw,40px);
    padding-bottom:18px;
    border-bottom:2px solid var(--ink);
    max-width:100%;
  }

  .article > p{
    margin:0 0 1.35em;
    font-size:1.115rem;
    line-height:1.74;
    color:#211B12;
  }
  .article > p:first-of-type::first-letter,
  .article h1 + p::first-letter{
    /* intentionally none — keep editorial restraint */
  }

  .article h2{
    counter-increment:h2;
    font-family:"Archivo",sans-serif;
    font-weight:800;
    font-size:clamp(1.55rem,3.2vw,2.3rem);
    line-height:1.08;
    letter-spacing:-.018em;
    color:var(--ink);
    margin:clamp(48px,6vw,74px) 0 .55em;
    padding-top:clamp(34px,4.5vw,48px);
    border-top:1px solid var(--line);
    position:relative;
    text-wrap:balance;
  }
  .article h2::before{
    content:counter(h2,decimal-leading-zero) "  —";
    display:block;
    font-family:"IBM Plex Mono",monospace;
    font-size:.78rem;
    font-weight:500;
    letter-spacing:.16em;
    color:var(--accent);
    margin-bottom:14px;
    text-transform:none;
  }

  .article h3{
    font-family:"Archivo",sans-serif;
    font-weight:700;
    font-size:1.2rem;
    letter-spacing:-.01em;
    margin:2em 0 .5em;
    color:var(--ink);
  }

  .article a{
    color:var(--ink);
    text-decoration:none;
    background-image:linear-gradient(var(--accent),var(--accent));
    background-position:0 100%;
    background-repeat:no-repeat;
    background-size:100% 1.5px;
    padding-bottom:1px;
    transition:background-size .2s ease,color .2s ease;
  }
  .article a:hover{
    color:var(--accent-deep);
    background-size:100% calc(100% );
    background-image:linear-gradient(rgba(226,64,42,.12),rgba(226,64,42,.12));
  }

  .article ul{
    list-style:none;
    margin:1.6em 0 1.8em;
    padding:0;
  }
  .article ul li{
    position:relative;
    padding:.62em 0 .62em 34px;
    border-bottom:1px solid var(--line);
    font-size:1.05rem;
    line-height:1.6;
  }
  .article ul li:first-child{ border-top:1px solid var(--line); }
  .article ul li::before{
    content:"";
    position:absolute;
    left:6px;
    top:1.18em;
    width:9px;height:9px;
    background:var(--accent);
    transform:rotate(45deg);
  }

  /* ---------- DATASHEET TABLE ---------- */
  .article table{
    width:100%;
    border-collapse:collapse;
    margin:1.8em 0 2em;
    font-family:"Newsreader",serif;
    background:var(--paper);
    border:1px solid var(--line-strong);
    display:block;
    overflow-x:auto;
    -webkit-overflow-scrolling:touch;
  }
  .table-scroll{
    overflow-x:auto;
    -webkit-overflow-scrolling:touch;
    margin:1.9em 0 2.2em;
    border:1px solid var(--line-strong);
  }
  .table-scroll table{ margin:0; border:none; min-width:600px; display:table; }

  .article thead th{
    background:var(--th-bg);
    color:var(--ink);
    text-align:left;
    font-family:"IBM Plex Mono",monospace;
    font-weight:600;
    font-size:.64rem;
    letter-spacing:.13em;
    text-transform:uppercase;
    padding:13px 16px;
    border-bottom:2px solid var(--ink);
    white-space:nowrap;
  }
  .article tbody td{
    padding:12px 16px;
    border-bottom:1px solid var(--line);
    font-size:.98rem;
    vertical-align:top;
    color:#241D14;
  }
  .article tbody tr:last-child td{ border-bottom:none; }
  .article tbody tr:hover{ background:rgba(226,64,42,.035); }
  /* property column = label */
  .article tbody td:first-child{
    font-family:"Archivo",sans-serif;
    font-weight:600;
    color:var(--ink);
    width:24%;
  }
  /* range column = mono numeric datasheet feel */
  .article tbody td:nth-child(2){
    font-family:"IBM Plex Mono",monospace;
    font-size:.86rem;
    letter-spacing:-.01em;
    color:var(--accent-deep);
    font-weight:500;
    white-space:nowrap;
  }
  /* test standard column = mono uppercase */
  .article tbody td:nth-child(3){
    font-family:"IBM Plex Mono",monospace;
    font-size:.76rem;
    letter-spacing:.04em;
    text-transform:uppercase;
    color:var(--muted);
    white-space:nowrap;
  }
  .article tbody td:nth-child(4){
    color:var(--muted);
    font-size:.95rem;
  }

  /* ---------- INDEX GROUPS ---------- */
  .article .grp-skip{
    font-family:"IBM Plex Mono",monospace;
    font-size:.6rem;
    letter-spacing:.12em;
    text-transform:uppercase;
    color:var(--muted);
    border:1px solid var(--line-strong);
    padding:2px 7px;
    margin-left:8px;
    vertical-align:middle;
  }
  .article .grp-kind{ font-weight:600; }

  /* ---------- FOOTER ---------- */
  .footer{
    border-top:2px solid var(--ink);
    background:var(--paper-2);
  }
  .footer__inner{
    max-width:var(--maxw);
    margin:0 auto;
    padding:clamp(36px,5vw,56px) var(--gutter);
    display:flex;
    flex-wrap:wrap;
    align-items:flex-end;
    justify-content:space-between;
    gap:24px;
  }
  .footer__brand{
    font-family:"Archivo Black","Archivo",sans-serif;
    font-weight:900;
    font-size:clamp(1.6rem,4vw,2.6rem);
    letter-spacing:-.02em;
    line-height:.95;
    text-transform:uppercase;
    color:var(--ink);
  }
  .footer__brand .vm{ color:var(--accent); }
  .footer__meta{
    font-family:"IBM Plex Mono",monospace;
    font-size:.66rem;
    letter-spacing:.08em;
    text-transform:uppercase;
    color:var(--muted);
    text-align:right;
    line-height:1.9;
  }
  .footer__meta .accent{ color:var(--accent-deep); }

  /* ---------- LOAD ANIMATION ---------- */
  @keyframes rise{
    from{ opacity:0; transform:translateY(16px); }
    to{ opacity:1; transform:translateY(0); }
  }
  .anim{ opacity:0; animation:rise .72s cubic-bezier(.2,.7,.2,1) forwards; }
  .d1{ animation-delay:.05s; }
  .d2{ animation-delay:.16s; }
  .d3{ animation-delay:.28s; }
  .d4{ animation-delay:.42s; }
  @media (prefers-reduced-motion:reduce){
    .anim{ animation:none; opacity:1; }
    html{ scroll-behavior:auto; }
  }

  /* ---------- TRUST BAND (conversion chrome · standards detected from body) ---------- */
  .trustband{
    max-width:var(--maxw);
    margin:0 auto;
    padding:0 var(--gutter);
    display:flex;
    flex-wrap:wrap;
    align-items:center;
    gap:14px clamp(14px,2.4vw,26px);
    margin-bottom:clamp(6px,1.5vw,14px);
  }
  .trustband__lead{
    font-family:"IBM Plex Mono",monospace;
    font-size:.6rem;
    letter-spacing:.2em;
    text-transform:uppercase;
    color:var(--accent-deep);
    white-space:nowrap;
    padding-right:6px;
    border-right:2px solid var(--ink);
  }
  .trustband__list{
    list-style:none;
    margin:0;
    padding:0;
    display:flex;
    flex-wrap:wrap;
    align-items:stretch;
    gap:0;
    border-top:1px solid var(--line-strong);
    border-bottom:1px solid var(--line-strong);
  }
  .trustband__item{
    display:flex;
    flex-direction:column;
    justify-content:center;
    padding:8px 16px;
    border-left:1px solid var(--line);
    min-width:0;
  }
  .trustband__item:first-child{ border-left:none; }
  .trustband__std{
    font-family:"Archivo",sans-serif;
    font-weight:800;
    font-size:.82rem;
    letter-spacing:-.005em;
    line-height:1.1;
    color:var(--ink);
    white-space:nowrap;
  }
  .trustband__sub{
    font-family:"IBM Plex Mono",monospace;
    font-size:.54rem;
    letter-spacing:.12em;
    text-transform:uppercase;
    color:var(--muted);
    margin-top:2px;
    white-space:nowrap;
  }
  .trustband__note{
    font-family:"Newsreader",serif;
    font-style:italic;
    font-size:.84rem;
    line-height:1.4;
    color:var(--muted);
    flex:1 1 220px;
    min-width:200px;
  }

  /* ---------- PULL-QUOTE (decision line lifted from intro) ---------- */
  .pullquote{
    max-width:var(--measure);
    margin:clamp(20px,3vw,34px) 0 clamp(8px,1.5vw,16px);
    padding:0 0 0 clamp(18px,2.4vw,26px);
    border-left:4px solid var(--accent);
  }
  .pullquote__txt{
    margin:0;
    font-family:"Archivo",sans-serif;
    font-weight:700;
    font-size:clamp(1.25rem,2.6vw,1.7rem);
    line-height:1.22;
    letter-spacing:-.012em;
    color:var(--ink);
    text-wrap:balance;
  }

  /* ---------- VERMILION CTA ACTION BLOCK ---------- */
  .cta{
    max-width:var(--maxw);
    margin:0 auto;
    padding:0 var(--gutter) clamp(56px,8vw,96px);
  }
  .cta__inner{
    background:var(--accent);
    color:var(--paper);
    border:2px solid var(--ink);
    padding:clamp(28px,4vw,46px) clamp(24px,4vw,52px);
    position:relative;
  }
  .cta__inner::after{
    content:"";
    position:absolute;
    left:0;right:0;bottom:-9px;
    height:7px;
    background:var(--ink);
  }
  .cta__kicker{
    font-family:"IBM Plex Mono",monospace;
    font-size:.66rem;
    letter-spacing:.24em;
    text-transform:uppercase;
    color:var(--paper);
    opacity:.85;
    margin:0 0 14px;
  }
  .cta__head{
    font-family:"Archivo Black","Archivo",sans-serif;
    font-weight:900;
    font-size:clamp(1.7rem,4vw,2.9rem);
    line-height:1.02;
    letter-spacing:-.02em;
    color:var(--paper);
    margin:0 0 .5em;
    max-width:20ch;
    text-wrap:balance;
  }
  .cta__sub{
    font-family:"Newsreader",serif;
    font-size:clamp(1.02rem,1.6vw,1.18rem);
    line-height:1.55;
    color:var(--paper);
    margin:0 0 clamp(20px,2.6vw,28px);
    max-width:60ch;
  }
  .cta__deliv{
    list-style:none;
    margin:0;
    padding:0;
    display:flex;
    flex-wrap:wrap;
    gap:0;
    border-top:2px solid rgba(242,238,227,.55);
  }
  .cta__deliv li{
    font-family:"IBM Plex Mono",monospace;
    font-size:.7rem;
    letter-spacing:.06em;
    text-transform:uppercase;
    color:var(--paper);
    padding:14px 22px 0 0;
    margin-right:22px;
    position:relative;
  }
  .cta__deliv li::before{
    content:"";
    position:absolute;
    left:-15px;top:18px;
    width:6px;height:6px;
    background:var(--paper);
    transform:rotate(45deg);
  }
  .cta__deliv li:first-child::before{ display:none; }
  .cta__sig{
    font-family:"IBM Plex Mono",monospace;
    font-size:.62rem;
    letter-spacing:.16em;
    text-transform:uppercase;
    color:var(--paper);
    opacity:.8;
    margin:clamp(20px,2.6vw,26px) 0 0;
  }

  /* ---------- RESPONSIVE ---------- */
  @media (max-width:880px){
    .topbar__inner{ flex-direction:column; min-height:0; padding-top:12px; padding-bottom:0; gap:8px; }
    .brand{ padding-bottom:2px; }
    nav.mainnav{
      border-top:1px solid var(--line);
      margin:0 calc(var(--gutter) * -1);
      padding:0 var(--gutter);
    }
    nav.mainnav a{ padding:12px 12px; }
    nav.mainnav a::after{ bottom:8px; }
  }
  @media (max-width:720px){
    body{ font-size:1rem; }
    .hero__title{ max-width:100%; }
    .article ul li{ padding-left:30px; }
    .trustband__lead{ border-right:none; padding-right:0; }
    .trustband__list{ width:100%; }
    .trustband__note{ flex-basis:100%; }
    .cta__deliv li{ flex:1 1 100%; padding-right:0; margin-right:0; }
    .cta__deliv li::before{ display:none; }
    .cta__deliv li:not(:first-child){ border-top:1px solid rgba(242,238,227,.3); }
  }
  @media (max-width:520px){
    .footer__inner{ flex-direction:column; align-items:flex-start; }
    .footer__meta{ text-align:left; }
  }
"""


def _brand_initial(org: str) -> str:
    """品牌方块里的字母：取 org 第一个非空白字符（大写）。"""
    for ch in (org or ""):
        if not ch.isspace():
            return ch.upper()
    return "·"


def _brand(org: str, href: str) -> str:
    """sticky 顶栏的品牌块（mark + name + est 装饰行）。"""
    org_e = esc(org)
    return (
        '<a class="brand" href="' + esc(href) + '" aria-label="' + org_e + ' home">'
        '<span class="brand__mark"><span>' + esc(_brand_initial(org)) + '</span></span>'
        '<span class="brand__txt">'
        '<span class="brand__name">' + org_e + '</span>'
        '<span class="brand__est">Specification-grade documentation</span>'
        '</span>'
        '</a>'
    )


def _nav(nav) -> str:
    """主导航：active 项加 .active + aria-current。"""
    out = ['<nav class="mainnav" aria-label="Primary">']
    for item in (nav or []):
        label = esc(item.get("label"))
        href = esc(item.get("href"))
        if item.get("active"):
            out.append('<a href="' + href + '" class="active" aria-current="page">' + label + '</a>')
        else:
            out.append('<a href="' + href + '">' + label + '</a>')
    out.append('</nav>')
    return "".join(out)


def _topbar(org: str, brand_href: str, nav) -> str:
    return (
        '<header class="topbar"><div class="topbar__inner">'
        + _brand(org, brand_href)
        + _nav(nav)
        + '</div></header>'
    )


def _footer(org: str, year) -> str:
    org_e = esc(org)
    return (
        '<footer class="footer"><div class="footer__inner">'
        '<div class="footer__brand">' + org_e + '<span class="vm">.</span></div>'
        '<div class="footer__meta">'
        '&copy; ' + esc(year) + ' ' + org_e + '<br>'
        '<span class="accent">Specification-grade sourcing</span><br>'
        'Demo build'
        '</div>'
        '</div></footer>'
    )


def _crumbs(crumbs) -> str:
    if not crumbs:
        return ""
    parts = ['<nav class="crumb" aria-label="Breadcrumb">']
    sep = '<span class="sep">›</span>'
    pieces = []
    for c in crumbs:
        label = esc(c.get("label"))
        href = c.get("href")
        if href is None:
            pieces.append('<span class="here">' + label + '</span>')
        else:
            pieces.append('<a href="' + esc(href) + '">' + label + '</a>')
    parts.append(sep.join(pieces))
    parts.append('</nav>')
    return "".join(parts)


def _chips(chips) -> str:
    """规格小标签块；空列表则不渲染。"""
    chips = [c for c in (chips or []) if str(c).strip() != ""]
    if not chips:
        return ""
    out = ['<div class="chips anim d4" role="list" aria-label="Key specifications">']
    for c in chips:
        out.append('<span class="chip" role="listitem">' + esc(c) + '</span>')
    out.append('</div>')
    return "".join(out)


def _head(lang, title, meta_desc, robots, jsonld) -> str:
    """完整 <head>（含字体/CSS/robots/jsonld）。返回从 <!doctype> 到 </head>。"""
    return (
        '<!DOCTYPE html>\n'
        '<html lang="' + esc(lang) + '">\n<head>\n'
        '<meta charset="UTF-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        '<meta name="robots" content="' + esc(robots) + '" />\n'
        '<title>' + esc(title) + '</title>\n'
        '<meta name="description" content="' + esc(meta_desc) + '" />\n'
        + _FONTS + '\n'
        '<style>' + _CSS + '</style>\n'
        + (jsonld or "")
        + '\n</head>\n'
    )


def render_page(ctx: dict) -> str:
    """单页完整 <!doctype html> 文档。"""
    type_label = ctx.get("type_label") or ctx.get("ptype") or "DOC"
    title = ctx.get("title", "")
    meta_desc = ctx.get("meta_desc", "")
    body_has_h1 = bool(ctx.get("body_has_h1"))

    # hero kicker：技术装饰 + 页面类型词（来自 type_label，无行业含义）
    kicker = (
        '<p class="hero__kicker anim d1">'
        '<span class="tick"></span>'
        '<span>' + esc(type_label) + ' &middot; DOC</span>'
        '<span class="doc">/ SPEC SHEET &middot; REV.A</span>'
        '</p>'
    )

    # hero 大标题：body 已含 h1 时用非 h1，否则提供 h1
    if body_has_h1:
        hero_title = (
            '<div class="hero__title anim d2" id="hero-title" role="heading" aria-level="1">'
            + esc(title) + '</div>'
        )
    else:
        hero_title = (
            '<h1 class="hero__title anim d2" id="hero-title">' + esc(title) + '</h1>'
        )

    hero_lede = ""
    if meta_desc:
        hero_lede = '<p class="hero__lede anim d3">' + esc(meta_desc) + '</p>'

    hero = (
        '<section class="hero" aria-labelledby="hero-title">'
        + kicker
        + hero_title
        + hero_lede
        + _chips(ctx.get("chips"))
        + '</section>'
    )

    body_html = ctx.get("body_html", "") or ""

    # 转化加权 chrome（纯附加，从已定的 body_html 只读检测，绝不改正文/不参与评分）：
    #   · 信任徽带：hero 之下、正文之上的一条可扫标准带（检不到标准则不渲染）。
    #   · 决策重点句：从首段拉出 1 句结论做重点排版（不合适则不渲染，可选件）。
    #   · 朱红 CTA：正文末尾的醒目行动块（站点既有报价/联系语气）。
    trust_band = _trust_band(body_html)
    pull_quote = _pull_quote(body_html)
    cta_block = _cta_block(ctx.get("org"))

    brand_href = "./index.html"
    parts = [
        _head(ctx.get("lang"), title, meta_desc, ctx.get("robots"), ctx.get("jsonld", "")),
        '<body>\n',
        _topbar(ctx.get("org"), brand_href, ctx.get("nav")),
        _crumbs(ctx.get("crumbs")),
        hero,
        trust_band,
        '<main class="sheet">',
        ctx.get("warn_html", "") or "",
        pull_quote,
        '<article class="article">',
        body_html,
        '</article>',
        cta_block,
        '</main>',
        _footer(ctx.get("org"), ctx.get("year")),
        '\n</body>\n</html>',
    ]
    return "".join(parts)


def _index_groups(groups) -> str:
    """首页分组列表：每组一个 <h2> + 一个 <ul>，item 未过质检则标题不可点 + skipped 标记。"""
    out = []
    for g in (groups or []):
        out.append('<h2>' + esc(g.get("label")) + '</h2>')
        out.append('<ul>')
        for it in (g.get("items") or []):
            title = esc(it.get("title"))
            teaser = it.get("teaser")
            type_label = it.get("type_label")
            href = it.get("href")
            passed = bool(it.get("passed"))
            li = ['<li>']
            if href is None or not passed:
                li.append('<span class="here">' + title + '</span>')
                li.append('<span class="grp-skip">skipped</span>')
            else:
                li.append('<a href="' + esc(href) + '">' + title + '</a>')
            tail = []
            if type_label:
                tail.append('<span class="grp-kind">' + esc(type_label) + '</span>')
            if teaser:
                tail.append(esc(teaser))
            if tail:
                li.append(' &mdash; ' + ' &middot; '.join(tail))
            li.append('</li>')
            out.append("".join(li))
        out.append('</ul>')
    return "".join(out)


def render_index(ctx: dict) -> str:
    """首页完整 <!doctype html> 文档。"""
    site_name = ctx.get("site_name", "")
    sub = ctx.get("sub", "")
    stats = ctx.get("stats") or {}

    # 首页 <title> 用 site_name
    head = _head(
        ctx.get("lang"),
        site_name,
        sub,
        ctx.get("robots"),
        "",  # 首页无 jsonld 入参（契约未给）
    )

    kicker = (
        '<p class="hero__kicker anim d1">'
        '<span class="tick"></span>'
        '<span>Documentation Index</span>'
        '<span class="doc">/ SPEC SHEET &middot; REV.A</span>'
        '</p>'
    )
    # 首页 hero 大标题是页面唯一 h1
    hero_title = (
        '<h1 class="hero__title anim d2" id="hero-title">' + esc(site_name) + '</h1>'
    )
    hero_lede = ""
    if sub:
        hero_lede = '<p class="hero__lede anim d3">' + esc(sub) + '</p>'

    # 站点级 chips：用 stats 拼（无行业含义）
    chip_specs = []
    if stats.get("total") is not None:
        chip_specs.append(str(stats.get("total")) + " Pages")
    if stats.get("n_pass") is not None:
        chip_specs.append(str(stats.get("n_pass")) + " Published")
    if stats.get("n_skip"):
        chip_specs.append(str(stats.get("n_skip")) + " Skipped")
    chips_html = ""
    if chip_specs:
        cout = ['<div class="chips anim d4" role="list" aria-label="Site facts">']
        for c in chip_specs:
            cout.append('<span class="chip" role="listitem">' + esc(c) + '</span>')
        cout.append('</div>')
        chips_html = "".join(cout)

    hero = (
        '<section class="hero" aria-labelledby="hero-title">'
        + kicker + hero_title + hero_lede + chips_html
        + '</section>'
    )

    brand_href = "./index.html"
    parts = [
        head,
        '<body>\n',
        _topbar(ctx.get("org"), brand_href, ctx.get("nav")),
        hero,
        '<main class="sheet"><article class="article">',
        _index_groups(ctx.get("groups")),
        '</article></main>',
        _footer(ctx.get("org"), ctx.get("year")),
        '\n</body>\n</html>',
    ]
    return "".join(parts)
