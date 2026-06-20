# 超级管理员后台(Admin Console)高保真 Demo 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development(或 executing-plans)逐任务实现。步骤用 `- [ ]` 勾选。
> **本计划在 feat 统一基线上执行(post baseline-merge)**——文件路径假设 `static/console.css`、`templates/index.html` 等 feat 资产已在。依据 spec:`docs/superpowers/specs/2026-06-07-admin-console-design.md`。

**Goal:** 给「AI SEO 内容工厂」加一个高保真、可点击的超级管理员后台 Demo(假数据 + 竞品模块灌真数据),用于客户演示/收定金。

**Architecture:** 独立 Flask Blueprint `admin/`(`url_prefix=/admin`)+ `templates/admin/*` + `admin/fixtures.py` 假数据层;`app.py` 仅加一行注册;复用 `static/console.css` 的 Gemini 设计系统,新增 `static/admin.css` 只定义 `--admin-rail-*` 扩展变量与 admin 专属布局(**不改 console.css**)。视觉=深色侧栏 + Gemini 蓝主动作。

**Tech Stack:** Python/Flask、Jinja2、原生 HTML/CSS/JS(无新依赖)、pytest。

---

## ⚠️ 协同护栏(每个任务/每个 ultracode agent 都必须遵守)

- **绝不修改**:`templates/index.html`、`static/console.css`、`templates/projects.html`、`templates/login.html`、`lib/intake.py`、`skills/seo-content/**`、`app.py` 里 `/` 与 `/intake` 路由及 auth 注册。
- `app.py` **只允许新增一行** blueprint 注册(见 Task 1)。
- `models.py` 本期 **不动**(全用 `fixtures.py` 假数据)。
- admin 一切 HTML/CSS **只用 `console.css` 已有 token/组件**;新样式进 `static/admin.css`,**只引用** `var(--…)`,不重定义 console.css 的变量(只新增 `--admin-rail-*`)。
- 竞品模块**只读** `research/competitor-dossiers.json`,不写。

---

## 文件结构(本计划新建/修改)

| 文件 | 职责 |
|---|---|
| `admin/__init__.py`(新) | 定义 `admin_bp` Blueprint,导入 routes |
| `admin/routes.py`(新) | 各 `/admin/*` 路由处理器,取 fixtures → render |
| `admin/fixtures.py`(新) | 假数据(租户/项目/成员/可行性/关键词/透明档案/模块清单)+ `load_competitors()` 读真 json |
| `static/admin.css`(新) | `--admin-rail-*` 扩展变量 + 深色侧栏/顶栏/数据范围卡/占位空状态布局(引用 console.css 变量) |
| `templates/admin/_shell.html`(新) | 共享壳:深色侧栏(11 模块+子项)+ 顶栏(租户/项目/成员选择器+搜索+角色+通知)+ 数据范围卡 + `{% block main %}` |
| `templates/admin/feasibility.html`(新) | 深做①:SEO 可行性报告+可解释评分(主视图) |
| `templates/admin/competitors.html`(新) | 深做②:竞品拆解(真数据)+ Gap 矩阵 |
| `templates/admin/keyword_map.html`(新) | 深做③:关键词地图(意图分层) |
| `templates/admin/transparency.html`(新) | 深做④:透明化生成档案(只读快照) |
| `templates/admin/_stub.html`(新) | 浅壳模板(占位空状态),7-8 模块复用 |
| `tests/test_admin.py`(新) | 路由冒烟测试 + 关键内容断言 |
| `app.py`(改:+1 行) | `from admin import admin_bp; app.register_blueprint(admin_bp)` |

---

## Phase 0 — 脚手架(串行,必须最先)

### Task 1: Blueprint + 注册 + 冒烟测试

**Files:** Create `admin/__init__.py`、`admin/routes.py`、`tests/test_admin.py`;Modify `app.py`(+1 注册行)

- [ ] **Step 1: 写失败测试** — `tests/test_admin.py`
```python
import app as appmod

def _client():
    appmod.app.config.update(TESTING=True)
    return appmod.app.test_client()

def test_admin_index_200():
    r = _client().get("/admin/")
    assert r.status_code == 200
    assert "超级管理员".encode() in r.data  # 顶栏角色徽标
```
- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_admin.py::test_admin_index_200 -v` → FAIL(404,蓝图未注册)
- [ ] **Step 3: 建 Blueprint** — `admin/__init__.py`
```python
from flask import Blueprint

admin_bp = Blueprint(
    "admin", __name__,
    url_prefix="/admin",
    # 模板用 app 级 templates/admin/,无需 template_folder
)
from admin import routes  # noqa: E402,F401  (注册路由)
```
- [ ] **Step 4: 占位 index 路由** — `admin/routes.py`
```python
from flask import render_template
from admin import admin_bp
from admin import fixtures as fx  # Task 2 提供;先建空占位避免 import 错

@admin_bp.route("/")
def index():
    return render_template("admin/feasibility.html", **fx.context("feasibility"))
```
> 注:Task 2 未完成前,临时把 Step 4 的 body 改成 `return "超级管理员 OK"` 让测试先过;Task 2 完成后改回 render_template。
- [ ] **Step 5: app.py 注册(唯一允许的改动)** — 在 `auth.init_app(app)` 之后加:
```python
from admin import admin_bp
app.register_blueprint(admin_bp)
```
- [ ] **Step 6: 跑测试确认通过** — `pytest tests/test_admin.py -v` → PASS
- [ ] **Step 7: 提交** — `git add admin/ tests/test_admin.py app.py && git commit -m "feat(admin): blueprint 脚手架 + 注册 + 冒烟测试"`

### Task 2: 假数据层 `admin/fixtures.py`

**Files:** Create `admin/fixtures.py`;Test: 追加 `tests/test_admin.py`

- [ ] **Step 1: 写失败测试**
```python
from admin import fixtures as fx

def test_fixtures_shapes():
    assert fx.TENANTS and fx.TENANTS[0]["name"] == "FlowPilot Inc."
    f = fx.FEASIBILITY
    assert f["score"] == 82 and f["verdict"] == "Go"
    assert len(f["factors"]) >= 6 and {"name","score","weight","evidence","confidence","status"} <= f["factors"][0].keys()
    assert len(fx.MODULES) == 11
    comps = fx.load_competitors()
    assert len(comps) >= 6 and "competitor" in comps[0]

def test_context_has_shell_keys():
    ctx = fx.context("feasibility")
    assert ctx["active"] == "feasibility" and ctx["tenant"]["name"] and ctx["modules"]
```
- [ ] **Step 2: 跑确认失败** — `pytest tests/test_admin.py::test_fixtures_shapes -v` → FAIL(ImportError/AttributeError)
- [ ] **Step 3: 实现 fixtures**(完整数据契约;数值取自原型图)— `admin/fixtures.py`
```python
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_DOSSIERS = ROOT / "research" / "competitor-dossiers.json"

# 11 个一级模块(字母徽标 + Material Symbols 图标名 + 子项)。deep=有内容;其余浅壳。
MODULES = [
    {"key":"platform","letter":"P","icon":"apartment","label":"平台管理","sub":"租户·订阅·运维"},
    {"key":"projects","letter":"J","icon":"folder_managed","label":"项目中台","sub":"项目·创建·目标"},
    {"key":"cms","letter":"C","icon":"hub","label":"CMS 中台","sub":"连接·映射·变更"},
    {"key":"seo","letter":"S","icon":"insights","label":"SEO 策略","sub":"策略工作台","deep":True,
     "children":[
        {"key":"feasibility","label":"策略工作台"},{"key":"nogo","label":"No-go 建议"},
        {"key":"competitors","label":"竞品拆解","deep":True},{"key":"serp","label":"SERP 快照"},
        {"key":"keyword_map","label":"关键词地图","deep":True},{"key":"intent","label":"意图治理"},
        {"key":"architecture","label":"网站架构"},{"key":"blueprint","label":"行业 Blueprint"}]},
    {"key":"content","letter":"N","icon":"edit_document","label":"内容生产","sub":"计划·编辑·审核"},
    {"key":"publish","letter":"F","icon":"cloud_upload","label":"发布中台","sub":"队列·校验·回流"},
    {"key":"monitor","letter":"M","icon":"monitoring","label":"监控优化","sub":"排名·收录·实验"},
    {"key":"agent","letter":"A","icon":"smart_toy","label":"Agent 与 Skill","sub":"编排·Skill·运行"},
    {"key":"data","letter":"D","icon":"database","label":"数据与系统","sub":"数据·凭证·模型"},
    {"key":"rbac","letter":"R","icon":"shield_person","label":"权限与安全","sub":"RBAC·数据权限·审计"},
    {"key":"settings","letter":"T","icon":"settings","label":"设置","sub":"项目策略"},
]
# transparency 作为 SEO 策略下的"生成档案"深做屏,额外可达:
DEEP_KEYS = {"feasibility","competitors","keyword_map","transparency"}

TENANTS = [
    {"id":"flowpilot","name":"FlowPilot Inc.","plan":"Enterprise","status":"正常"},
    {"id":"herz","name":"萌翻天 Inc.","plan":"Growth","status":"正常"},
]
PROJECTS = {
    "flowpilot":[{"id":"fp1","name":"FlowPilot AI","cms":"WordPress","locale":"US / English","domain":"flowpilot.ai"}],
    "herz":[{"id":"hz1","name":"PU Leather Hub","cms":"WordPress","locale":"US / English","domain":"puleather.example"}],
}
MEMBERS = [{"id":"mia","name":"Mia Chen","role":"超级管理员","scope":"全部租户 / 全部项目 / 全部员工"}]

FEASIBILITY = {
    "score":82, "verdict":"Go", "verdict_note":"进入完整 SEO 链路",
    "confidence":"高", "ai_infer":"31%", "eta":"8-12 周", "eta_note":"首批页面发布后",
    "sources":5, "sources_note":"可追溯", "risks":3, "risks_note":"需运营确认",
    "opportunities":["高意图长尾词存在明显缺口","对比页与替代品页商业意图强","竞品内容深度不均衡"],
    "risks_list":["头部词品牌垄断较高","部分 SERP 由目录站占位","需要持续补充产品事实"],
    "data_sources":[
        {"name":"Google SERP","note":"已纳入报告,报告输出会标注来源"},
        {"name":"GSC","note":"已纳入报告,报告输出会标注来源"},
        {"name":"DataForSEO","note":"已纳入报告,报告输出会标注来源"},
        {"name":"竞品页面抓取","note":"已纳入报告,报告输出会标注来源"},
        {"name":"产品官网","note":"已纳入报告,报告输出会标注来源"}],
    "factors":[
        {"name":"搜索需求","score":86,"weight":"20%","evidence":"核心商业词 1.9K/月,长尾集群 18K/月","confidence":"高","status":"通过"},
        {"name":"商业意图","score":91,"weight":"18%","evidence":"best / alternative / software / pricing 查询占比高","confidence":"高","status":"通过"},
        {"name":"SERP 可突破性","score":73,"weight":"16%","evidence":"Top10 存在内容薄弱目录页和论坛页","confidence":"中","status":"通过"},
        {"name":"内容成本","score":68,"weight":"12%","evidence":"对比页和安全页需要事实库与人工审核","confidence":"中","status":"需确认"},
        {"name":"链接门槛","score":64,"weight":"10%","evidence":"头部词需要品牌引用,长尾词可先切入","confidence":"中","status":"需确认"},
        {"name":"AI 可见性","score":70,"weight":"12%","evidence":"对比/替代品页易被 ChatGPT/Perplexity 引用","confidence":"中","status":"需确认"}],
}

INTENTS = ["pillar","comparison","commercial","application","informational"]  # 对齐 console.css .kchip 变体
KEYWORDS = {
    "intents":INTENTS,
    "clusters":[
        {"name":"PU 革总览","intent":"pillar","pages":1,"keywords":["what is pu leather","pu leather guide","pu leather meaning"]},
        {"name":"对比类","intent":"comparison","pages":3,"keywords":["pu leather vs genuine leather","pu leather vs pvc","pu vs faux leather"]},
        {"name":"应用场景","intent":"application","pages":5,"keywords":["pu leather for furniture","pu leather for automotive","pu leather for bags"]},
        {"name":"采购/商业","intent":"commercial","pages":4,"keywords":["pu leather supplier","pu leather manufacturer","bulk pu leather"]},
        {"name":"知识问答","intent":"informational","pages":5,"keywords":["is pu leather durable","is pu leather waterproof","how to clean pu leather"]}],
}

TRANSPARENCY = {
    "page":"pu-leather-for-automotive.html", "title":"PU Leather for Automotive", "score":84, "passed":True,
    "breakdown":[
        {"dim":"keyword_usage","score":10,"max":15,"note":"automotive 关键词未进标题 −5(真实扣分,不掩饰)"},
        {"dim":"structure","score":20,"max":20,"note":"H1/H2/H3 层级完整"},
        {"dim":"depth_wordcount","score":18,"max":20,"note":"1480 词,达标"},
        {"dim":"internal_links","score":18,"max":20,"note":"4 条簇内链,缺 1 条回 pillar"},
        {"dim":"specificity_antislop","score":13,"max":15,"note":"含 1 项独有数据表(信息增益)"},
        {"dim":"meta_title_quality","score":5,"max":10,"note":"meta 略长 −5"}],
    "placements":[
        {"kw":"pu leather for automotive","where":"H1 / 正文×3","hit":True},
        {"kw":"automotive upholstery","where":"H2 / 正文×2","hit":True},
        {"kw":"abrasion resistance","where":"数据表","hit":True}],
}

def load_competitors():
    """只读真竞品档案;文件缺失时返回 [](demo 不崩)。"""
    try:
        data = json.loads(_DOSSIERS.read_text(encoding="utf-8"))
        return data.get("competitors", [])
    except Exception:
        return []

def context(active, tenant_id="flowpilot", project_id=None, member_id="mia"):
    """所有 admin 页共享的壳上下文 + 当前激活模块 key。"""
    tenant = next((t for t in TENANTS if t["id"]==tenant_id), TENANTS[0])
    projs = PROJECTS.get(tenant["id"], [])
    project = next((p for p in projs if p["id"]==project_id), projs[0] if projs else None)
    member = next((m for m in MEMBERS if m["id"]==member_id), MEMBERS[0])
    return {"active":active, "modules":MODULES, "tenants":TENANTS, "tenant":tenant,
            "projects":projs, "project":project, "members":MEMBERS, "member":member}
```
- [ ] **Step 4: 跑确认通过** — `pytest tests/test_admin.py -v` → PASS;并把 Task 1 Step 4 的 index 路由改回 `render_template("admin/feasibility.html", feasibility=fx.FEASIBILITY, **fx.context("feasibility"))`
- [ ] **Step 5: 提交** — `git add admin/fixtures.py tests/test_admin.py admin/routes.py && git commit -m "feat(admin): 假数据契约 fixtures + 真竞品加载"`

---

## Phase 1 — 共享壳(串行,在模块之前)

### Task 3: `static/admin.css`(扩展变量 + 深色侧栏/顶栏布局)

**Files:** Create `static/admin.css`(**不改 console.css**)

- [ ] **Step 1: 写扩展变量 + 布局**(完整;只引用 console.css 变量,新增 `--admin-rail-*`)
```css
/* admin.css —— 超管后台专属。依赖 static/console.css(先引 console.css 再引本文件)。
   只新增 --admin-rail-* 扩展变量 + admin 布局;绝不重定义 console.css 的 token。 */
:root{
  --admin-rail-bg:#1F1F1F;      /* 深色侧栏底(对齐 console.css --ink) */
  --admin-rail-ink:#E3E3E0;     /* 侧栏文字 */
  --admin-rail-faint:#9AA0A6;   /* 侧栏次级 */
  --admin-rail-on:#8AB4F8;      /* 选中态(Gemini 蓝在深色上的提亮版,仍是蓝系) */
  --admin-rail-on-bg:rgba(138,180,248,.16);
  --admin-rail-line:rgba(255,255,255,.10);
}
.admin{display:grid;grid-template-columns:248px minmax(0,1fr);grid-template-rows:minmax(0,1fr);height:100vh;overflow:hidden}
.admin.rail-min{grid-template-columns:64px minmax(0,1fr)}

/* 深色侧栏 */
.arail{background:var(--admin-rail-bg);color:var(--admin-rail-ink);display:flex;flex-direction:column;min-height:0;overflow:hidden}
.arail__top{display:flex;align-items:center;gap:10px;padding:16px 16px 12px}
.arail__brand b{font-size:14px;font-weight:700;line-height:1.1}
.arail__brand span{display:block;font-family:var(--mono);font-size:8.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--admin-rail-faint);margin-top:3px}
.arail__list{flex:1;min-height:0;overflow:auto;padding:6px 10px}
.anav{display:flex;align-items:center;gap:11px;padding:9px 11px;border-radius:10px;color:var(--admin-rail-ink);
  transition:background .16s var(--ease),color .16s var(--ease);cursor:pointer;text-decoration:none}
.anav:hover{background:rgba(255,255,255,.06);text-decoration:none;color:#fff}
.anav.on{background:var(--admin-rail-on-bg);color:var(--admin-rail-on)}
.anav__badge{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;flex:none;font-size:11px;font-weight:700;
  font-family:var(--mono);background:rgba(255,255,255,.08);color:var(--admin-rail-ink)}
.anav.on .anav__badge{background:var(--admin-rail-on);color:var(--admin-rail-bg)}
.anav__tx b{display:block;font-size:13.5px;font-weight:500;line-height:1.2}
.anav__tx span{display:block;font-size:10.5px;color:var(--admin-rail-faint);margin-top:1px}
.anav__sub{padding:2px 0 8px 30px;display:flex;flex-direction:column;gap:1px}
.asub{padding:6px 10px;border-radius:8px;font-size:12.5px;color:var(--admin-rail-faint);text-decoration:none;transition:background .16s,color .16s}
.asub:hover{background:rgba(255,255,255,.05);color:var(--admin-rail-ink);text-decoration:none}
.asub.on{color:var(--admin-rail-on);font-weight:600}

/* 主区 + 顶栏(复用 console.css .topbar/.projpill 思路,这里只补 admin 专属) */
.amain{min-width:0;display:flex;flex-direction:column;overflow:hidden;background:var(--bg)}
.atop{height:60px;display:flex;align-items:center;gap:12px;padding:0 22px;border-bottom:1px solid var(--line);flex:none}
.atop .grow{flex:1}
.arole{display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 12px;border-radius:9999px;background:var(--blue-wash);color:var(--blue);font-size:12.5px;font-weight:600}
.asearch{flex:1;max-width:420px;height:38px;border-radius:9999px;border:1px solid var(--line2);background:var(--surface);padding:0 14px;font-family:var(--sans)}

/* 数据范围卡条 */
.ascope{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:18px 22px}
.ascope .card{padding:14px 16px}
.ascope .lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--gray);margin-bottom:6px}
.ascope .val{font-size:15px;font-weight:600;color:var(--ink)}
.ascope .meta{font-size:12px;color:var(--faint);margin-top:2px}
.abody{flex:1;overflow:auto;padding:4px 22px 28px}

/* 浅壳空状态 */
.stub{max-width:520px;margin:8vh auto;text-align:center;color:var(--ink2)}
.stub .ic{width:64px;height:64px;border-radius:18px;background:var(--surface2);display:grid;place-items:center;margin:0 auto 18px}
.stub .ic .ms{font-size:30px;color:var(--gray)}
.stub h2{font-size:19px;margin:0 0 8px}
.stub p{color:var(--faint);font-size:13.5px;line-height:1.7;margin:0 0 18px}
.stub .demo-tag{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--warn);background:var(--warn-wash);padding:4px 10px;border-radius:9999px}

/* 折叠态 */
.admin.rail-min .arail__brand,.admin.rail-min .anav__tx,.admin.rail-min .anav__sub{display:none}
.admin.rail-min .anav{justify-content:center}
```
- [ ] **Step 2: 验证** — 无独立测试;由 Task 4 渲染时确认加载(`<link href=.../admin.css>` 200)。
- [ ] **Step 3: 提交** — `git add static/admin.css && git commit -m "feat(admin): 深色侧栏+顶栏布局 + --admin-rail-* 扩展变量(不改 console.css)"`

### Task 4: 共享壳 `templates/admin/_shell.html`

**Files:** Create `templates/admin/_shell.html`;Test: 追加 `tests/test_admin.py`

- [ ] **Step 1: 写失败测试**
```python
def test_shell_renders_all_modules():
    r = _client().get("/admin/")
    body = r.data.decode()
    for label in ["平台管理","SEO 策略","权限与安全","FlowPilot Inc.","Mia Chen"]:
        assert label in body
```
- [ ] **Step 2: 跑确认失败**(壳未建,模块标签缺失)
- [ ] **Step 3: 实现壳**(骨架完整;`{% block main %}` 给模块填充)— `templates/admin/_shell.html`
```html
<!doctype html><html lang="zh"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>超级管理员 · {% block title %}AI SEO 内容工厂{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700&family=Roboto+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..0" rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static', filename='console.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='admin.css') }}">
{% block head %}{% endblock %}
</head><body>
<div class="admin">
  <!-- 深色侧栏:11 模块 + SEO 策略子项 -->
  <aside class="arail">
    <div class="arail__top">
      <div class="spark" style="width:34px;height:34px"><span class="ms fill">network_intelligence</span></div>
      <div class="arail__brand"><b>AI SEO 内容工厂</b><span>Super Admin</span></div>
    </div>
    <nav class="arail__list">
      {% for m in modules %}
      <a class="anav {{ 'on' if active==m.key or (m.children and active in m.children|map(attribute='key')) }}"
         href="{{ url_for('admin.module', key=m.key) if not m.deep else url_for('admin.'+m.key) if m.key in ['feasibility'] else url_for('admin.module', key=m.key) }}">
        <span class="anav__badge">{{ m.letter }}</span>
        <span class="anav__tx"><b>{{ m.label }}</b><span>{{ m.sub }}</span></span>
      </a>
      {% if m.children and (active==m.key or active in m.children|map(attribute='key')) %}
      <div class="anav__sub">
        {% for c in m.children %}
        <a class="asub {{ 'on' if active==c.key }}"
           href="{{ url_for('admin.'+c.key) if c.key in ['feasibility','competitors','keyword_map'] else url_for('admin.module', key=c.key) }}">{{ c.label }}</a>
        {% endfor %}
        <a class="asub {{ 'on' if active=='transparency' }}" href="{{ url_for('admin.transparency') }}">生成档案(透明)</a>
      </div>
      {% endif %}
      {% endfor %}
    </nav>
  </aside>

  <main class="amain">
    <!-- 顶栏:租户/项目/成员选择器(.projpill 复用) + 搜索 + 角色 + 通知 -->
    <header class="atop">
      <a class="projpill" href="?tenant={{ tenant.id }}"><span class="dot"></span>{{ tenant.name }} · {{ project.locale if project }}<span class="ms">expand_more</span></a>
      <span class="chip">租户:{{ tenant.name }}</span>
      <span class="chip">项目:{{ project.name if project }}</span>
      <span class="chip">成员:{{ member.name }}</span>
      <span class="grow"></span>
      <input class="asearch" placeholder="搜索页面、关键词、任务、成员">
      <span class="arole"><span class="ms" style="font-size:16px">shield_person</span>{{ member.role }}</span>
      <button class="iconbtn"><span class="ms">notifications</span></button>
    </header>
    <!-- 数据范围四卡 -->
    <section class="ascope">
      <div class="card"><div class="lbl">租户</div><div class="val">{{ tenant.name }}</div><div class="meta">{{ tenant.plan }} · {{ tenant.status }}</div></div>
      <div class="card"><div class="lbl">项目</div><div class="val">{{ project.name if project }}</div><div class="meta">{{ project.domain if project }} · {{ project.cms if project }}</div></div>
      <div class="card"><div class="lbl">当前成员</div><div class="val">{{ member.name }}</div><div class="meta">{{ member.role }}</div></div>
      <div class="card"><div class="lbl">数据范围</div><div class="val">{{ member.scope }}</div><div class="meta">超级管理员可跨租户查看</div></div>
    </section>
    <div class="abody">{% block main %}{% endblock %}</div>
  </main>
</div>
</body></html>
```
> 注:`url_for` 分支按"深做 key 有独立路由、其余走 `admin.module`"。Task 5-9 落地路由后此处链接即生效。若某 `url_for` 在路由未建时报错,先用 `href="#"` 占位,模块任务完成后回填。
- [ ] **Step 4: 跑确认通过** — `pytest tests/test_admin.py -v` → PASS
- [ ] **Step 5: 提交** — `git add templates/admin/_shell.html tests/test_admin.py && git commit -m "feat(admin): 共享壳(深色侧栏11模块+顶栏选择器+数据范围卡)"`

---

## Phase 2 — 模块(★ 可并行:Task 5/6/7/8/9 互不依赖,各 1 个 ultracode agent)

> 公共规则(每个模块 agent):`{% extends "admin/_shell.html" %}` + `{% block main %}`;只用 console.css 组件(`.card/.card-h/.card-b/.kchip/.meter/.btn/.chip/.spark` + keyframes)与 admin.css;数据来自路由传入的 fixtures;每个模块加路由 + 测试断言关键内容存在。

### Task 5: 深做① 可行性报告 `feasibility.html`(= 原型图主视图)

**Files:** Create `templates/admin/feasibility.html`;`admin/routes.py` 已有 `index`,在其后无需新增(index 即 feasibility);Test 追加。

**Build 规格(agent 照此填 `{% block main %}`,数据 `feasibility`=fx.FEASIBILITY):**
1. **标题区**:`SEO 可行性报告` + 副标"判断产品是否值得做 Google 全球 SEO,并明确数据来源、置信度和 AI 推断比例" + 右上 `.btn.pri`「重新分析」、`.btn`「生成竞品拆解」「生成关键词地图」。
2. **6 张 KPI 卡**(`.card` 网格 6 列):综合评分 `{{f.score}}`/结论 `{{f.verdict}}`(+note)/置信度 `{{f.confidence}}`(+AI 推断 `{{f.ai_infer}}`)/预期见效 `{{f.eta}}`/数据源 `{{f.sources}}`/风险数 `{{f.risks}}`。
3. **机会与风险**(两列 `.card`):左列 `f.opportunities`、右列 `f.risks_list`,逐条行。
4. **数据可信度**(右栏 `.card` 列表):`f.data_sources` 每条 name + note。
5. **可解释评分模型**(`.card` 内表):列=因子/分数(进度条 width:score%)/权重/证据/置信度(`.kchip`)/状态(`.chip`,通过=ok 色、需确认=warn 色)/操作(查看证据·生成任务)。遍历 `f.factors`。
6. 进度条用纯 div:`<div style="height:6px;background:var(--line2);border-radius:5px"><i style="display:block;height:100%;width:{{fa.score}}%;background:var(--blue);border-radius:5px"></i></div>`。

- [ ] Step 1: 测试 `assert "可解释评分模型" in body and "搜索需求" in body and "82" in body`
- [ ] Step 2: 跑→失败
- [ ] Step 3: 写模板(照上规格)
- [ ] Step 4: 跑→PASS
- [ ] Step 5: `git commit -m "feat(admin): 可行性报告+可解释评分(主视图)"`

### Task 6: 深做② 竞品拆解 `competitors.html`(真数据)

**Files:** Create `templates/admin/competitors.html`;`admin/routes.py` +`competitors` 路由;Test 追加。

- [ ] **Step 1: 路由 + 测试**
```python
# admin/routes.py 追加
@admin_bp.route("/competitors")
def competitors():
    return render_template("admin/competitors.html", competitors=fx.load_competitors(), **fx.context("competitors"))
```
```python
# tests
def test_competitors_real_data():
    body = _client().get("/admin/competitors").data.decode()
    assert "Byword" in body and ("软肋" in body or "weakness" in body.lower())
```
- [ ] **Step 2: 跑→失败**
- [ ] **Step 3: 写模板** — 规格:① 顶部一句话注解"全场竞品都黑箱评分/无去重,我们可解释+去重 unique"(差异化钩子);② 竞品卡列表(遍历 `competitors`):每卡 `c.competitor` + `c.category` + 软肋数 `c.weaknesses|length` + 定价首档;点击展开详情(`<details>`):四维摘要 + `c.weaknesses` 每条 `weakness`+`evidence`+`sourceUrl`(链接)+ 核验 `c.verifications` 的 `verdict` 用 `.kchip`(confirmed=app 绿/refuted=warn/uncertain=info);③ 末尾「功能 Gap 矩阵」`.card` 内表:行=8 家 + 我们,列=去重/事实核查/可解释/透明/WP发布(✓/✗/弱),数据可硬编进模板(取自 spec §4)。
- [ ] **Step 4: 跑→PASS**
- [ ] **Step 5: `git commit -m "feat(admin): 竞品拆解(真档案数据)+ Gap 矩阵"`**

### Task 7: 深做③ 关键词地图 `keyword_map.html`

**Files:** Create `templates/admin/keyword_map.html`;`admin/routes.py` +`keyword_map` 路由;Test 追加。
- [ ] **Step 1: 路由**`@admin_bp.route("/keywords")` → `render_template("admin/keyword_map.html", kw=fx.KEYWORDS, **fx.context("keyword_map"))` + 测试 `assert "comparison" in body or "对比类" in body`
- [ ] **Step 2: 跑→失败**
- [ ] **Step 3: 写模板** — 规格:意图图例(5 个 `.kchip` 变体:pillar/comparison/commercial/application/informational);按 `kw.clusters` 渲染簇卡(`.card`):每卡簇名 + 意图 `.kchip` + 覆盖页数 `.chip` + 词 `.kchip`(用簇 intent 配色);可加一条简单 SVG/CSS 的 pillar→cluster 连线示意。
- [ ] **Step 4: 跑→PASS** / **Step 5: commit**

### Task 8: 深做④ 透明化生成档案 `transparency.html`

**Files:** Create `templates/admin/transparency.html`;`admin/routes.py` +`transparency` 路由;Test 追加。
- [ ] **Step 1: 路由**`@admin_bp.route("/transparency")` → `render_template("admin/transparency.html", t=fx.TRANSPARENCY, **fx.context("transparency"))` + 测试 `assert "automotive" in body and "−5" in body`(真实扣分可见)
- [ ] **Step 2: 跑→失败**
- [ ] **Step 3: 写模板** — 规格:标语"生成不黑箱,每页看得见";页名 `t.title` + 总分 `t.score`(`.spark` 或环形)+ passed 徽标;6 维评分卡(遍历 `t.breakdown`:dim/score/max + note,**如实显示扣分**,如 keyword_usage 10/15「automotive 关键词未进标题 −5」);关键词落位表(`t.placements`:kw/where/hit ✓)。诚实红线:不摆假失败页,只显真实扣分维度。
- [ ] **Step 4: 跑→PASS** / **Step 5: commit**

### Task 9: 浅壳模块(批量,1 agent)`_stub.html` + 通配路由

**Files:** Create `templates/admin/_stub.html`;`admin/routes.py` +`module` 通配路由;Test 追加。
- [ ] **Step 1: 路由 + 测试**
```python
# routes.py
@admin_bp.route("/m/<key>")
def module(key):
    m = next((x for x in fx.MODULES if x["key"]==key), None)
    if not m: abort(404)
    return render_template("admin/_stub.html", m=m, **fx.context(key))
```
```python
def test_stub_modules_reachable():
    c=_client()
    for key in ["platform","cms","content","publish","monitor","agent","data","rbac","settings"]:
        r=c.get(f"/admin/m/{key}")
        assert r.status_code==200 and "demo 占位".encode() in r.data
```
> 注:`from flask import abort` 加到 routes.py 顶部。`_shell.html` 里 `admin.module` 链接对应本路由(key 经 `/m/<key>`);回填 _shell 中 `url_for('admin.module', key=...)`。
- [ ] **Step 2: 跑→失败**
- [ ] **Step 3: 写 `_stub.html`**
```html
{% extends "admin/_shell.html" %}{% block title %}{{ m.label }}{% endblock %}
{% block main %}
<div class="stub">
  <div class="ic"><span class="ms">{{ m.icon }}</span></div>
  <h2>{{ m.label }}</h2>
  <p>本模块({{ m.sub }})将在正式版接入真实数据与操作。当前为高保真演示外壳,导航可达、结构就位。</p>
  <span class="demo-tag"><span class="ms" style="font-size:14px">construction</span>demo 占位 · 正式版接真</span>
</div>
{% endblock %}
```
- [ ] **Step 4: 跑→PASS** / **Step 5: `git commit -m "feat(admin): 7-8 浅壳模块(导航可达+得体占位)"`**

---

## Phase 3 — 集成与验收(串行,模块全完成后)

### Task 10: 导航/选择器联动 + 全路由冒烟 + 视觉验收

**Files:** Modify `admin/routes.py`(选择器切换)、`tests/test_admin.py`
- [ ] **Step 1: 选择器切换** — 各深做路由读 `request.args.get("tenant")` 传入 `fx.context(active, tenant_id=...)`,使顶栏切租户→数据范围卡跟着换。示例:
```python
from flask import request
@admin_bp.route("/")
def index():
    tid = request.args.get("tenant","flowpilot")
    return render_template("admin/feasibility.html", feasibility=fx.FEASIBILITY, **fx.context("feasibility", tenant_id=tid))
```
- [ ] **Step 2: 全路由冒烟测试**
```python
def test_all_admin_routes_200():
    c=_client()
    for path in ["/admin/","/admin/competitors","/admin/keywords","/admin/transparency"]:
        assert c.get(path).status_code==200
def test_switch_tenant():
    body=_client().get("/admin/?tenant=herz").data.decode()
    assert "萌翻天 Inc." in body
```
- [ ] **Step 3: 跑全部测试** — `pytest tests/test_admin.py -v` → 全 PASS
- [ ] **Step 4: 手动视觉验收**(运行 `python app.py` → `/admin/`):核对 §12 demo 脚本——可行性报告像原型图、切租户数据换、竞品拆解点开见真引用、关键词/透明档案、浅壳得体;整体深色侧栏+Gemini 蓝、与生成台同源。
- [ ] **Step 5: 提交** — `git add -A && git commit -m "feat(admin): 选择器联动 + 全路由冒烟 + 集成验收"`

---

## ultracode 编排映射(Workflow 多代理)

```
phase('scaffold')   # 串行
  Task1(blueprint+register+test) → Task2(fixtures)
phase('shell')      # 串行,依赖 scaffold
  Task3(admin.css) → Task4(_shell.html)
phase('modules')    # ★并行,依赖 shell —— parallel([T5,T6,T7,T8,T9])
  各 agent 强约束:extends _shell、只用 console.css+admin.css、数据来自 fixtures、不碰护栏文件
phase('integrate')  # 串行,依赖 modules
  Task10(选择器联动 + 全冒烟 + 验收)
```
每个并行 agent 输入:其 Task 的「Build 规格」+ `admin/fixtures.py` 字段 + `static/console.css` 组件清单 + 原型图。barrier 在 modules 后做集成。

---

## Self-Review

- **Spec 覆盖**:§1 目标✓(Demo) §3 护栏✓(护栏段+每任务约束) §4 架构✓(T1-2) §5 IA/壳✓(T4) §6 四深做✓(T5-8) §6 浅壳✓(T9) §7 视觉✓(T3 --admin-rail-*+蓝) §8 fixtures✓(T2) §9 交互✓(T10 切换) §11 ultracode✓(编排映射) §12 验收✓(T10 Step4)。
- **占位扫描**:无 TBD;模块体用"Build 规格"非含糊指令(给了组件/字段/断言);fixtures/壳/css/路由/测试均完整代码。
- **类型一致**:`fx.context()` 返回键(active/modules/tenants/tenant/projects/project/members/member)与 `_shell.html` 用到的变量一致;`FEASIBILITY` 字段与 T5 规格一致;`load_competitors()` 返回的 `competitor/weaknesses/verifications` 与 T6 一致;`MODULES[*].key` 与路由/`_shell` 链接一致。
- 已知取舍:模块体 HTML 由 ultracode agent 照规格 + 真 console.css 填充(非本计划逐行预写),因实际 build 在统一基线上才有 console.css;这是有意的右altitude,规格已足够无歧义。

---

## 风险

- **基线门槛**:本计划假设 feat 基线(console.css/index.html 已在)。必须 **post baseline-merge** 执行。
- **`url_for` 链接**:_shell 的 deep-key 路由名需与 routes 一致(feasibility=index 的 `admin.index` 还是 `admin.feasibility`?——本计划用 `admin.index` 作可行性报告;_shell 中"策略工作台"子项链 `admin.index`)。集成 Task10 统一校验所有 `url_for` 不报 BuildError。
- **测试中文断言**:用 `.encode()` 或 `.data.decode()` 比对,避免字节/字符串混比。
