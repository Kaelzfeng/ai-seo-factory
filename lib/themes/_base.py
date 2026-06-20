"""lib/themes/_base.py · 主题系统的共享基座

设计目标（"几个模板 + 以后可拓展"）：
- lib/preview.py 负责【逻辑】：站内链接改写、JSON-LD 注入点、质检横幅、slug 映射、写文件；
  它把一份【与主题无关的 ctx 字典】交给当前主题渲染。
- 每个主题（lib/themes/<name>.py）负责【表现】：返回完整 HTML 文档字符串。
- 新增一套模板 = 新增一个 lib/themes/<name>.py 并在 __init__.py 注册，不动 preview.py。

主题模块必须导出：
    NAME: str                     # 机器名（与文件名一致），如 "datasheet-editorial"
    LABEL: str                    # 人读名，如 "Datasheet Editorial"
    def render_page(ctx: dict) -> str   # 返回单页完整 <!doctype html> 文档
    def render_index(ctx: dict) -> str  # 返回站点首页完整文档

约定（两个 render 都要遵守）：
- 全页恰好一个 <h1>。当 ctx["body_has_h1"] 为 True 时，正文已含 <h1>，
  hero 大标题必须用非 h1 元素（如 role="heading" aria-level="1"）；为 False 时由 hero 提供 h1。
- 必须把 ctx["jsonld"]（可能为空串）原样放进 <head>。
- 必须把 ctx["warn_html"]（质检未过横幅，可能为空串）渲染在 <article> 之前。
- 导航用 ctx["nav"]，对 active==True 的项加该主题的高亮态。
- 不外链图片；字体用 Google Fonts <link>（联网可用）。

----- 单页 render_page 的 ctx 键 -----
  lang, site, org, title, meta_desc,
  body_html (已改写内链、含正文那唯一 <h1>),
  body_has_h1 (bool), ptype, type_label,
  nav   : [ {label, href, active(bool)} ]   有序，pillar 在前
  crumbs: [ {label, href|None} ]            href 为 None 表示当前页（不可点）
  chips : [str]                             hero 规格小标签，可能为空
  jsonld: str   warn_html: str   updated: str(ISO 日期)   year: int   robots: str

----- 首页 render_index 的 ctx 键 -----
  lang, site, org, year, site_name, sub, robots,
  nav   : [ {label, href, active(bool)} ]
  stats : {total, n_pass, n_skip}
  groups: [ {type, label, items:[ {title, href|None, teaser, type_label, passed(bool)} ]} ]
"""
import html as _html


def esc(s) -> str:
    """HTML 转义（属性/文本通用）。"""
    return _html.escape("" if s is None else str(s), quote=True)
