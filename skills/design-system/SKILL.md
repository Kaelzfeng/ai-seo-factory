# Design System — 生成站模板库 & 操作台视觉规范

这是设计系统的**人读权威规范**，与代码一一对应、**必须保持同步**：

- 主题契约（ctx 键、render 接口、单一 h1 等约定）↔ `lib/themes/_base.py`
- 主题注册表（机器名 → 模块、别名、默认）↔ `lib/themes/__init__.py`
- 三套内置主题实现 ↔ `lib/themes/datasheet.py` / `atelier.py` / `blueprint.py`
- ctx 构造 / 站内链接改写 / 质检横幅 / 委托渲染 ↔ `lib/preview.py`
- 操作台模板 ↔ `templates/index.html`

> 一句话定位：**生成站用「几套」可插拔模板（主题库，可继续拓展）；操作台用「一套」固定模板（技术仪表盘）。**
> 改了这里的字体/配色/契约/某套主题的"标志动作"，就要同步改对应代码文件（同一个 commit）。

设计目标：让生成出来的站**绝不像 AI 套模板**——有明确美学主张、有记忆点、对 B2B 工业采购买家可信。
灵感取自 Awwwards / Godly 高分获奖项目的共同打法，而非通用 UI 套件。

---

## 0. 反"AI 套路"红线（任何模板都不许碰）

源自 frontend-design 原则 + 我们对高分项目的复盘。**新增/修改模板前先过这张表：**

- ❌ 禁止 **Inter / Roboto / Arial / 系统字体 / Space Grotesk** 当主字体。用有性格的显示字 + 精致正文字。
- ❌ 禁止 **白底紫蓝渐变 + 圆角卡片网格** 这套被滥用的"AI 配色 + 布局"。
- ❌ 禁止 **居中 hero + 三张卡片** 的模板感构图。
- ✅ 配色要有**单一主张**：一个主导底色 + 克制中性 + **一个**信号强调色（不要五彩平均分布）。
- ✅ 构图要有**编辑/海报式主张**：不对称、超大字、网格线、序号、hairline、技术标注等，任选契合该方向的手法。
- ✅ 要有**氛围与质感**：纸纹/噪点/网格/细线/细阴影/首字下沉等，而不是纯色平铺。
- ✅ 一处**克制的载入动画**（hero staggered fade-up），高光时刻一次到位，不要满屏微交互。

共通骨架（三套主题都遵守，靠它们保证"同一产品的不同皮肤"而非各做各的）：
`sticky 顶栏(品牌+导航) → 面包屑 → 编辑式 hero(kicker + 大标题 + 导语 + 规格 chips) → <article>正文 → 页脚`。
正文里的**规格表**一律做成"**数据手册 / datasheet**"质感（数字列等宽、行底 hairline、表头有性格）——这是本产品内容（满是 ISO/Martindale/N·MOQ）的天然形态，也是最强的可信度信号。

---

## 1. 三套内置主题（生成站模板库）

切换：行业 config（`industries/*.yaml`）里写 `theme: <机器名>`；缺省走 `lib.themes.DEFAULT`。
机器名 / 别名见 `lib/themes/__init__.py`。

### A · `datasheet-editorial` — Datasheet Editorial（**默认**）
- **气质**：暖纸上的材料白皮书 / 工程文档，编辑杂志的呼吸感。**B2B 最可信、长文最好读** → 设为默认。
- **字体**：显示 `Archivo`(800–900) / `Archivo Black`；正文 `Newsreader`(衬线 400/500)；数据/序号/标签 `IBM Plex Mono`。
- **配色**：`--paper:#F2EEE3` / `--ink:#15110B` / `--accent:#E2402A`(朱红) / `--muted:#6B6357` / `--line:#D8D1C2`。
- **标志动作**：超大紧字距 hero 大标题；H2 前朱红等宽序号 `01 —`；区块间 1px hairline；极淡 SVG 纸纹噪点；数字列等宽的 datasheet 表。
- **适用**：默认首选；外贸工业材料、零部件、化工、机械等"按规格成交"的品类。

### B · `atelier-dark` — Atelier Dark
- **气质**：近黑底高对比衬线、电影感大留白。把工业材料卖出**精品 / 高端定制**调性。
- **字体**：显示 `Fraunces`(高对比衬线 300/500，可 italic 点睛)；正文 `Hanken Grotesk`；标签/数据 `Spline Sans Mono` / Fraunces 小号大写。
- **配色**：`--bg:#121013`(暖炭黑) / `--ink:#ECE6DC` / `--accent:#C9A36B`(暖铜，贴皮革材质) / `--muted:#9A9187` / 细线 `rgba(236,230,220,.12)`。
- **标志动作**：右栏规格摘要（TYPE / REFERENCE / UPDATED）；铜色首字下沉；铜色 hairline；极淡颗粒；半透明 sticky 顶栏。铜色**只**用于细线/序号/链接/关键数字，绝不大面积铺——要"贵"不要"花"。
- **适用**：高端品牌、定制 / 小批量精品、想突出质感与溢价的客户。**注意**：暗色长文阅读更累，超长 pillar 慎用。

### C · `technical-blueprint` — Technical Blueprint
- **气质**：带坐标网格的工程规格图纸。冷静、系统、精密，和满页测试标准的内容最贴题。
- **字体**：显示 `Archivo`(宽体感 800)；正文 `IBM Plex Sans`；标签/坐标/数据 `IBM Plex Mono`。
- **配色**：`--bg:#F4F5F3`(近白) / `--ink:#0E1116` / `--accent:#1B39C4`(钴蓝/克莱因蓝) / `--muted:#5A6066` / `--line:#D2D6DC` / 网格 `rgba(14,17,22,.06)`。
- **标志动作**：极淡工程网格底；可见列网格 / 竖直 hairline；技术标注（`SPEC SHEET / REV.A`、`FIG.0x`、`SCALE 1:1`、角落 tick、条码、标尺线）；钴蓝等宽编号 H2；图纸式 datasheet 表；竖排侧栏标签。钴蓝用于网格强调线/序号/链接/关键规格。
- **适用**：技术属性极强、买家是采购工程师、规格即卖点的品类。

> 选型速记：**默认 A**；要"贵 / 精品"→ B；要"工程 / 硬核技术"→ C。

---

## 2. 主题契约（写新模板的硬约定）

权威定义在 `lib/themes/_base.py`，这里给要点。每个主题模块**必须且只**导出：

```python
from lib.themes._base import esc
NAME  = "<机器名>"          # 与文件名族一致
LABEL = "<人读名>"
def render_page(ctx: dict) -> str:    # 返回单页完整 <!doctype html> 文档
def render_index(ctx: dict) -> str:   # 返回站点首页完整文档
```

**职责边界**：`lib/preview.py` 管逻辑（站内链接改写、JSON-LD 注入、质检横幅、导航/面包屑/分组数据、写文件），
构造**与主题无关的 ctx** 交给主题；主题只管表现。**新增模板不动 preview.py。**

**必守约定**：
1. **全页恰好一个 `<h1>`**。`ctx["body_has_h1"]` 为 True（几乎总是）时，正文已含 `<h1>`，hero 大标题用非 h1（`role="heading" aria-level="1"` 或 `<p>`）；为 False 时由 hero 提供 h1。
2. `ctx["jsonld"]`（可能空串）原样放进 `<head>`。
3. `ctx["warn_html"]`（质检未过横幅，内联样式、主题无关，可能空串）原样渲染在 `<article>` **之前**。
4. 导航 `ctx["nav"]`（`{label,href,active}`，pillar 在前）对 active 项加本主题高亮态；面包屑 `ctx["crumbs"]`（`href` 为 None = 当前页不可点）。
5. 所有动态文本经 `esc()`；`body_html` / `jsonld` / `warn_html` 是已构造 HTML，**原样插入不转义**。
6. CSS 作为独立常量字符串拼接，**不要用 `.format()` / `%`**（会误伤 CSS 的 `{ }`）。
7. 字体用 Google Fonts `<link>`；**不外链图片**（要图用 CSS 渐变/SVG/色块）。
8. 正文可能是**裸 `<table>`**：用 CSS（`.article table{display:block;overflow-x:auto}` 或等价）保证窄屏可横向滚动，不依赖外层 wrapper。
9. 响应式：hero 字号 `clamp()`；≤640px 导航优雅收起。

ctx 完整键见 `lib/themes/_base.py` 顶部（单页 11 个、首页 8 个）。

---

## 3. 如何新增一套模板（"以后可拓展"的标准流程）

1. **取灵感**：先去高分项目（Awwwards / Godly / Land-book）定一个**大胆的美学方向**，过第 0 节红线。
2. **建模块** `lib/themes/<x>.py`：实现第 2 节契约的 4 个符号；CSS/字体作为常量；驱动全部内容来自 ctx、零行业硬编码。
3. **注册** `lib/themes/__init__.py`：`_REGISTRY` 加一行 `"<机器名>": "lib.themes.<x>"`；可选加别名。
4. **自检**（契约级，必须打印 OK）：
   ```bash
   python -c "import sys; sys.path.insert(0,'.'); from lib.themes import <x> as t; \
   ctx={'lang':'en','site':'https://x.com','org':'Acme Co.','title':'T','meta_desc':'M',\
   'body_html':'<h1>T</h1><h2>S</h2><p>x</p><table><tr><td>a</td></tr></table>',\
   'body_has_h1':True,'ptype':'pillar','type_label':'Pillar',\
   'nav':[{'label':'G','href':'./g.html','active':True}],\
   'crumbs':[{'label':'Home','href':'./index.html'},{'label':'T','href':None}],\
   'chips':['0.6-1.8mm'],'jsonld':'','warn_html':'','updated':'2026-06-05','year':2026,'robots':'noindex'}; \
   h=t.render_page(ctx); assert h.count('<h1')==1; print('OK', t.NAME, len(h))"
   ```
5. **真实管线核验**：`python render_samples.py`（或 `render_samples.render_all(theme="<机器名>", outdir="output/_x")`），浏览器点开 `output/.../index.html` 实际点击导航 + 正文内链，确认对版、可点、一个 h1。
6. **可选**：在某行业 config 写 `theme: <机器名>` 设为该站默认；操作台「样板演示」下拉会自动出现该模板（来自 `/themes` 路由）。

---

## 4. 操作台模板（`templates/index.html` · 一套固定）

定位「**Technical Instrument** 技术仪表盘」：和生成站主题库**同语系**（mono / 网格 / 钴蓝），但是控制台，不是文章。

- **配色**：近黑底 `--bg:#0a0c10` + 蓝图细网格；钴蓝信号 `--accent:#5b7cff`；朱红 `--signal:#e2402a` 只给"运行管线"主动作键；状态色 ok/warn/bad。
- **字体**：显示 `Archivo`；UI/正文 `IBM Plex Sans`；标签/日志/读出 `IBM Plex Mono`。
- **结构**：顶栏(品牌 + `BUILD·LOCAL` / `3 SITE TEMPLATES` 标签) → 引导语(管线大字) → 主面板：`00 样板演示`(零依赖，含**生成站模板下拉** → `/demo?theme=`) / `01 内容来源` / `02 目标` / 运行键 → 读出区(状态灯 + 终端日志 + 结果表)。
- **不可破坏的 JS 契约**（改样式时务必保留）：元素 id `form/run/log/dot/status/elapsed/resultArea/configSelect/demoTheme/demoBtn`；`input[name=source]`(config/seed) + `.sub[data-for=...]`；`input[name=mode]`(preview/publish)；JS 注入用的类 `.openidx/.badge.ok/.badge.bad/.chip/.warns`。后端路由：`/configs`、`/themes`、`/run`(SSE)、`/demo`、`/output/<path>`。

---

## 5. WordPress 落地（诚实边界 + 拓展路径）

- **现状（可演示、真实）**：模板系统活在**本生成器**里——`lib/preview.py` + `lib/themes/*` 渲染的整页 HTML/CSS。
  发布到 WordPress 时，注入的是**文章正文 + JSON-LD**；页面外壳由 WP 当前主题决定。
- **拓展路径（未来功能，不要谎称已实现）**：把这三套设计打包成**原生 WP 主题 / 区块模板（block theme / theme.json + 模板 PHP）**，
  让发布出的站直接用我们这套外壳；或导出为可复用的 WP 全站编辑模板。这正是"以后可拓展更多功能"的落点之一。
- 报价/承诺时按 [诚实不注水] 原则：能演示的说能演示，WP 原生主题打包是**增量工作量**，单独计。

---

## 6. 任意模板的验收 checklist（PR 前自查）

- [ ] 过第 0 节反套路红线（字体不在黑名单、配色单一主张、非卡片堆叠模板感）。
- [ ] 全页**恰好一个 `<h1>`**（`body_has_h1` 两个分支都验过）。
- [ ] `jsonld` 在 `<head>`、`warn_html` 在 `<article>` 前、`robots/lang/title` 来自 ctx。
- [ ] 零行业硬编码：品牌/导航/面包屑/标题/正文/chips 全来自 ctx。
- [ ] 裸 `<table>` 窄屏可横向滚动；hero 字号 `clamp()`；≤640px 导航不溢出。
- [ ] 站内链接（导航 / 面包屑 Home / 正文内链）在真实管线产物里**可点、指向 `./<slug>.html`**。
- [ ] 契约自检脚本打印 OK；`render_samples` 真实管线 8/8 通过且浏览器对版。
