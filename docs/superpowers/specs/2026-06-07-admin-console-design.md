# 超级管理员后台(Admin Console)· 设计 spec

> 日期:2026-06-07 · 状态:**设计已定**(深色侧栏 + Gemini 蓝)· 待你最终确认 → 出实现计划
> 参考:用户提供的「AI SEO 内容工厂 · 完整交互原型」图(超级管理员视角 + 租户/项目/成员选择器 + 11 模块 + SEO 可行性报告主视图)
> 协同:与 `feat/gemini-console-redesign` 线并行,**先 merge 建共享基线再 build**(见 §10)。

---

## 1. 目标 / 非目标

**目标**:做一个**高保真、可点击的交互原型(Demo)**,用假数据,给客户演示、收定金。把那张图变成"能点、好看、把我们差异化讲清楚"的超管后台。

**这一期非目标(明确不做)**:
- ❌ 真多租户隔离 / 真 RBAC / 真计费(=规划里的"子系统②",Keycloak/jCasbin/OpenMeter,数月级,本期不碰)。
- ❌ 真数据持久化(除竞品模块可灌真研究数据外,其余全假数据)。
- ❌ 真权限校验、真审计落库、真 CMS 连接。

> 一句话:**演示态的"超管驾驶舱",不是能上线运营的后台。** 但代码长在真仓里、复用真设计系统、每个模块未来能把假数据换成真接口(渐进式)。

---

## 2. 现状与基线

- **C 端现状**:基础 Flask 应用(`app.py` 单文件 + `auth.py` 登录 + `models.py` sqlite 4 表 users/projects/generations/keywords)+ `feat/gemini-console-redesign` 上的 Gemini 风操作台(`templates/index.html` 生成台 + `static/console.css` 设计系统 + projects/login 改皮 + `lib/intake.py` 意图 agent)。
- **设计系统已定**:`static/console.css` = **Gemini 融合**(蓝 `#1A73E8`、Lexend、Roboto Mono、Material Symbols Rounded、全圆 pill、大圆角卡、Material 缓动 + Gemini keyframes)。现成组件:`.btn/.btn.pri/.iconbtn`、`.field`、`.card/.card-h/.card-b`、`.chip/.kchip`(含意图色:pillar/comparison/commercial/application/informational)、`.meter`、`.projpill`、`.rail`(图标导航)、`.topbar`、`.alert`、`.spark/.brandmark`、keyframes(animateGradient/gemShimmer/entry/morphBG/sweepBG)。
- **基线落点**:Admin 必须长在 **feat 统一基线**上(feat = main+6,纯 fast-forward)。**绝不能**长在 `worktree-research+competitive-teardown`(它 HEAD=旧 main `4198b78`,无 console.css / 无 Gemini index)。

---

## 3. 协同边界(防与 feat 线撞车)

| 维度 | 归属 | 约定 |
|---|---|---|
| `templates/index.html`(生成台)、`lib/intake.py`、`skills/seo-content`、`/`、`/intake` 路由 | **feat 线守** | Admin 不碰 |
| `static/console.css` | **feat 线守**(设计系统唯一真相) | Admin **只复用 token / 加扩展变量**,绝不 fork;新增 admin 专属样式放 `templates/admin/*` 的 `<style>` 或新 `static/admin.css`(只引用 console.css 的 `--var`) |
| 超管后台 = `admin.py`(独立 blueprint)+ `templates/admin/*` + `admin/fixtures.py` | **Admin 线守** | 不挤进 `app.py` |
| `app.py` | 共管 | Admin **只加一行** `app.register_blueprint(admin_bp)`,不动 feat 改过的路由 |
| `models.py` | 共管 | 本期 admin 用假数据**不动 models.py**;未来加 admin 表前,先与 feat 的 #47 `conversations` 表对列名 |
| 竞品数据 | Admin 已产出 | feat 的 P2 #32「上 Google 找对标」**直接消费**本线 `research/competitor-dossiers.json` + memory,不重复造 |

---

## 4. 架构

```
admin.py                      # Flask Blueprint(url_prefix="/admin"),只渲染模板 + 喂 fixtures
admin/fixtures.py             # 假数据层(租户/项目/成员/可行性报告/竞品[真]/关键词/…),纯 dict
templates/admin/
  _shell.html                 # 共享壳:左模块侧栏 + 顶栏(租户/项目/成员选择器) + {% block main %}
  feasibility.html            # 深做①:SEO 可行性报告 + 可解释评分(主视图,= 图)
  competitors.html            # 深做②:竞品拆解(灌真研究数据)
  keyword_map.html            # 深做③:关键词地图
  transparency.html           # 深做④:透明化生成档案
  _stub.html                  # 浅壳模板(导航可达 + 占位空状态),其余 7-8 模块复用
static/admin.css              # (可选)admin 专属布局,只引用 console.css 的 --var
```

- **路由**:`/admin/`(默认进可行性报告)、`/admin/feasibility`、`/admin/competitors`、`/admin/keywords`、`/admin/transparency`、`/admin/<module>`(浅壳)。全部 `@admin_bp.route`,本期可不挂 `login_required`(demo)或挂一个假 super-admin 守卫。
- **数据**:每个路由从 `fixtures.py` 取假数据 → `render_template`。竞品路由从 `research/competitor-dossiers.json` 读真数据(只读)。
- **零后端逻辑**:不调 run.py / 不写库 / 不发 WP。纯展示 + 前端交互(选择器切换、表格筛选、tab、modal)。

---

## 5. 信息架构(IA)—— 照图,但分深浅

**壳(所有页共享)**:
- **左侧栏**:11 个一级模块(平台管理 P / 项目中台 J / CMS 中台 C / **SEO 策略 S** / 内容生产 N / 发布中台 F / 监控优化 M / Agent 与 Skill A / 数据与系统 D / 权限与安全 R / 设置 T)。带模块字母徽标 + 文字标签 + 可展开子项(SEO 策略展开:策略工作台 / No-go 建议 / 竞品拆解 / SERP 快照 / 关键词地图 / 意图治理 / 网站架构 / 行业 Blueprint)。可折叠成图标列(复用 `.rail` 思路,做"宽标签版")。
- **顶栏**(`.topbar` + 3× `.projpill`):租户选择器(FlowPilot Inc.)· 项目选择器(FlowPilot AI)· 成员选择器(Mia Chen)· 全局搜索 · 角色徽标(超级管理员)· 通知。选择器**可点切换**(切换 = 换一套 fixtures,前端 JS 或后端 query 参数)。
- **数据范围条**:四张概览卡(租户 / 项目 / 当前成员 / 数据范围),如图。

**深做 4 模块**(SEO 策略下,= 我们差异化、竞品全没有的):见 §6。
**浅壳 7-8 模块**:平台管理 / 项目中台 / CMS 中台 / 内容生产 / 发布中台 / 监控优化 / Agent 与 Skill / 数据与系统 / 权限与安全 / 设置 —— 导航可达 + 一个像样的"占位空状态"(标题 + 该模块要做什么的一句话 + 一个禁用的主操作 + "demo 占位"标记)。**不显空白页,但也不假装做完**(诚实红线)。

---

## 6. 深做模块详设

### ① SEO 可行性报告 + 可解释评分(主视图 = 图)
- **顶部 6 张 KPI 卡**(`.card`):综合评分 82 / 结论 Go / 置信度 高(AI 推断 31%)/ 预期见效 8-12 周 / 数据源 5 / 风险数 3。
- **机会与风险**(两列 `.card` 列表)。
- **数据可信度**(右栏):Google SERP / GSC / DataForSEO / 竞品页面抓取 / 产品官网 —— 每条标"已纳入报告,输出会标注来源"。**这是我们对竞品"黑箱单分"的正面差异**。
- **可解释评分模型**(表):因子 / 分数(进度条)/ 权重 / 证据 / 置信度 / 状态(通过·需确认)/ 操作(查看证据·生成任务)。6 因子:搜索需求 86·20% / 商业意图 91·18% / SERP 可突破性 73·16% / 内容成本 68·12% / 链接门槛 64·10% / …
- 组件:`.card` + `.kchip` + `.meter`/自绘进度条 + 状态 `.chip`。数据:`fixtures.feasibility`。
- **卖点钩子**:把竞品研究里"竞品都是黑箱评分"写成一句话注解,凸显我们"可解释 + 可追溯"。

### ② 竞品拆解(灌真数据)
- **数据源 = 本线 `research/competitor-dossiers.json`(真!8 家)**。
- 视图:竞品卡列表(定位 / 软肋数 / 定价锚点)+ 点开详情(四维:定位/功能/UX/定价 + 软肋带 source url + 核验徽标 confirmed/refuted)。+ 一张"功能 Gap 矩阵"(去重/事实核查/可解释/透明/WP发布… 我们 vs 8 家)。
- **演示杀招**:这一屏"敢点真的"——客户点任一竞品,看到的是带真实引用的歼灭级拆解,直接坐实"我们懂竞品、且补了他们的洞"。

### ③ 关键词地图
- 视图:意图分层(pillar/comparison/commercial/application/informational,复用 `.kchip` 意图色)+ 簇→页型映射 + 配额。可用我们 PU-leather demo 的真抓词结构做假数据(210 词→5 簇→18 页那套)。
- 组件:树/簇布局 + `.kchip` + 简单 SVG 连线(pillar-cluster 拓扑)。

### ④ 透明化生成档案
- 复用 feat 线"生成档案/双屏"叙事的**只读快照版**:某页的关键词落位图 + 6 维确定性评分卡 + "为什么这页通过/某维扣分"。
- 诚实红线:展示真实扣分维度(如 automotive 关键词未进标题 −5),**不摆假失败页**。
- 组件:`.card` + 评分卡 + 落位高亮。

---

## 7. 设计语言(关键决策)

**基础 = 复用 `console.css` 的 Gemini 系统**(Lexend / Material Symbols Rounded / Roboto Mono / 蓝 `#1A73E8` / 全圆 pill / 大圆角卡 / Material 缓动)。**那张图当 IA/布局蓝本,不当像素级配色规范。**

**✅ 已定(2026-06-07)**:**深色侧栏 + Gemini 蓝主动作**。
- 超管后台用**深色侧栏 rail** 营造"后台/平台情境"(区别于 C 端生成台);
- 主动作 / 选中 / 链接仍用 Gemini 蓝 `--blue`,**不引入第二强调色(不要绿)**;
- 深色侧栏作为 `console.css` 的**扩展变量**(如 `--admin-rail-bg` / `--admin-rail-ink` / `--admin-rail-on` / `--admin-rail-line`),**不 fork** console.css;
- 其余(字体 Lexend / 卡片 / pill / 缓动 / Material Symbols / 组件)100% 复用 Gemini 系统,与生成台同源。

**需新增的组件(都用 console.css token 拼)**:宽标签版模块侧栏(可折叠 + 子项展开)、KPI 统计卡、可解释评分表(进度条 + 状态 + 行操作)、竞品对比矩阵、数据可信度列表。

---

## 8. 假数据层 `admin/fixtures.py`

- `TENANTS`(FlowPilot Inc. 等 2-3 个)、`PROJECTS`、`MEMBERS`、`feasibility`(图里那套评分/机会风险/数据可信度)、`keywords`(PU-leather 真抓词结构)、`transparency`(某页落位+评分)。
- `competitors` → 不写死,**运行时读 `research/competitor-dossiers.json`**(真)。
- 选择器切换 = 切 `fixtures` 里不同租户/项目的数据(让"切租户"看起来真的在换上下文)。

---

## 9. 交互范围(demo 要"能点")

- ✅ 左侧栏导航(深做页有内容,浅壳页有占位)、可折叠。
- ✅ 顶栏租户/项目/成员选择器**可切换**(切数据)。
- ✅ 可解释评分表"查看证据"→ modal;竞品卡点开 → 详情;关键词意图筛选;tab 切换。
- ✅ "重新分析 / 生成竞品拆解 / 生成关键词地图"按钮 → 触发一个**假进度动画**(用 Gemini shimmer/spark)后展示预置结果(演示"agent 在干活"的感觉)。
- ❌ 不接真后端、不写库、不发 WP、不真算分。

---

## 10. 与 feat 线的时序(就按"计划 → merge → ultracode")

1. **本 spec 复核**(你 + feat 线)。
2. **建共享基线**:feat `push` + `main` 快进到 feat(零冲突)。把本线的竞品产物(报告/dossiers/memory)+ 本 spec 也并上统一基线。
3. **ultracode build**(在统一基线上):见 §11。

## 11. ultracode 构建计划(实现期再跑)

并行可拆为:`fixtures.py`(1) → 壳 `_shell.html`(1)→ 4 个深做模块各 1 agent(并行)+ 浅壳批量 1 agent + `admin.py` 路由(1)→ 串验。每个 agent 强约束:**只用 console.css token、不碰 feat 守的文件、admin 全在 blueprint 内**。竞品模块 agent 额外读 `competitor-dossiers.json`。

## 12. 验收(demo 脚本)

进 `/admin` → 看到图那样的可行性报告(KPI+机会风险+数据可信度+可解释评分表)→ 切租户/项目(数据跟着换)→ 进竞品拆解(点开真竞品、看真引用+Gap 矩阵)→ 进关键词地图/透明化档案 → 点几个浅壳模块(占位得体)→ 整体视觉与 Gemini 生成台同源、"好看且敢点"。

## 13. 风险

- **基线门槛**:不先 merge 就 build = 白做(已用本 worktree=旧 main 实证)。→ build 前必须建基线。
- **设计分歧**(§7 绿/蓝、深/浅侧栏):需你拍板,否则 build 出来可能跑偏。
- **范围蔓延**:11 模块全做深会失控 → 严守"4 深 + 其余浅壳"。
- **诚实红线**:浅壳/透明档案不许假装做完、不许摆假失败页。
