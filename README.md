# AI SEO 内容工厂 · DEMO（8k POC）

种子词 / 行业模板 → 主题簇(Topic Cluster) → 逐页生成 SEO 内容(含自动内链) → **质检内功(rubric)** → JSON-LD 结构化数据 → 配图 → **本地预览或一键发布到 WordPress**。

> 这是**可演示的最小闭环**：证明整条流水线真实跑通。现在已带**确定性质检 rubric（内功层）**、**容错重试**、**本地预览**与 **Flask 网页 UI**。

## 目录结构

```
seo/
├─ skills/
│  ├─ keyword-cluster/SKILL.md   # 种子词 → 主题簇规划（system prompt）
│  ├─ seo-content/SKILL.md       # 页面规格 → 文章+meta+配图词（system prompt）
│  ├─ quality-rubric/SKILL.md    # 内功：质检 rubric 的人读文档（与 lib/quality.py 同步）
│  ├─ design-system/SKILL.md     # 设计规范：生成站模板库 + 操作台（与 lib/themes/ 同步）
│  └─ wp-publish/SKILL.md        # 发布契约说明
├─ industries/
│  ├─ pu-leather.yaml            # 打磨好的行业模板（PU 合成革供应商，带预设 pages:）
│  └─ _template.yaml             # 现场版模板：填字段 + seed_keyword，结构现场生成（无 pages:）
├─ lib/
│  ├─ llm.py                     # Anthropic 封装（强制结构化输出）
│  ├─ quality.py                 # 内功：确定性质检评分（无 LLM，阈值 70 才发布）
│  ├─ schema.py                  # JSON-LD 结构化数据生成（Article/FAQ/Product + Breadcrumb）
│  ├─ preview.py                 # 主题驱动渲染：构造 ctx → 委托当前主题（站内链接改写/质检横幅）
│  ├─ themes/                    # 生成站可插拔模板库（datasheet-editorial / atelier-dark / technical-blueprint）
│  │  ├─ _base.py                #   主题契约（ctx 键 / render 接口 / 单一 h1 约定）
│  │  └─ __init__.py             #   注册表：机器名 → 模块、别名、DEFAULT
│  ├─ retry.py                   # 共享重试/退避助手（LLM 与 WP 调用都走它）
│  ├─ wp_publish.py              # WordPress REST 适配器（探测/重试/meta 回读校验）
│  └─ images.py                  # Pexels 配图（可选）
├─ templates/
│  └─ index.html                 # Flask UI 页面（表单 + 实时进度日志 SSE）
├─ output/                       # 预览模式产物（<slug>.html + index.html，自动生成）
├─ app.py                        # Flask 网页 UI（调用 run.generate_site，流式进度）
├─ run.py                        # 编排器（generate_site：质检 + schema + 预览/发布）
├─ requirements.txt
└─ .env.example
```

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env            # 然后填写 .env
```

## 准备 WordPress（演示站）

1. 用一个**干净的测试 WordPress**（本地 Docker 或测试域名），别用客户线上站。
2. **固定链接**：设置 → 固定链接 → 选「**文章名**」（这样每页 URL = `站点/<slug>/`，内链一次发布就生效）。
3. **应用程序密码**：用户 → 个人资料 → 应用程序密码，生成一串，填进 `.env` 的 `WP_APP_PASSWORD`。
4. （可选）装 Yoast 或 Rank Math，meta description 会自动写入；没装则回退到摘要。

## 运行（三种模式）

### 1) 本地预览 / Dry-run（推荐先跑，**不需要 WordPress**）

```bash
python run.py --dry-run                              # 打磨版：PU 合成革（演示兜底）
python run.py industries/_template.yaml --dry-run    # 现场版：客户行业 config
```

`--dry-run` 不发布任何东西，而是把每个**通过质检**的页面渲染成独立 HTML 写到
`output/<slug>.html`，再生成一个站点首页 `output/index.html`（带质检分数徽章、按页面类型分组、内链已改写为 `./<slug>.html` 可离线浏览）。跑完：

```
👉 打开 output/index.html
```

每页都内嵌 JSON-LD 结构化数据，未达阈值的页面会被标记为「below quality threshold」预览但不发布。这是现在**默认的演示路径**：零外部依赖、零风险。

### 2) 发布到 WordPress（需要 `.env` 配好 WP_*）

```bash
python run.py                              # 打磨版：PU 合成革（演示兜底）
python run.py industries/your-config.yaml  # 现场版：客户行业 config
```

控制台会实时显示：规划主题簇 → 逐页生成 → **质检打分** → 配图 → 发布。只有质检通过的页面才会发布；JSON-LD 会注入到文章正文。跑完打开站点前台刷新，整组页面已上线、互相内链、带配图、SEO 描述与结构化数据。

### 3) Flask 网页 UI

```bash
python app.py        # 启动后访问 http://127.0.0.1:5000
```

网页表单可选：用**行业 config**（下拉，来自 `industries/*.yaml`）或直接输入**种子词**（seed keyword + 几个画像字段）；选**仅预览（不发布）**或**发布到 WordPress**；点 Run 后下方实时滚动进度日志（SSE 流式）。预览模式跑完会给出 `output/index.html` 的链接，发布模式给出 WP 文章链接。UI 不含任何流水线逻辑，只调用 `run.generate_site`。

## 两种演示模式（内容来源）

- **打磨版（兜底）**：用 `industries/pu-leather.yaml` 里预设的 8 页结构，稳定好看，演示零风险。
- **现场版（客户词）**：复制 `industries/_template.yaml`，填好字段、改 `seed_keyword` 为客户的词（**不要加 `pages:` 段**），整站结构交给 `keyword-cluster` skill 现场生成 —— 代入感最强。

## 内功：质检 rubric（质量护城河）

发布前每页都过一道**确定性质检**（`lib/quality.py`，**无 LLM**，纯函数评分），人读版文档见 `skills/quality-rubric/SKILL.md`（两者保持同步）。六个维度合计 100 分，**阈值 70**：

| 维度 | 满分 | 看什么 |
|---|---|---|
| keyword_usage | 15 | 目标关键词在标题/meta/正文的分布，且不堆砌 |
| structure | 20 | 单一 `<h1>`、≥3 个 `<h2>`、层级不跳、有列表/表格、有问句式 H2 |
| depth_wordcount | 20 | 字数深度（pillar ≥1800，cluster ≥900） |
| internal_links | 20 | 内链闭环：cluster 上链 pillar、pillar 链全部 sibling；禁「click here」等空锚文本 |
| specificity_antislop | 15 | 具体规格+单位+标准（Martindale/ISO/g/m² 等）；扣 AI 套话黑名单 |
| meta_title_quality | 10 | 标题 50–60 字符、meta 140–160 字符、meta 不等于标题 |

**未达 70 的页面：预览但不发布**（dry-run 里会带「below quality threshold」横幅与可操作的 issue 列表）。这一层专门拦截 AI slop、保证 information gain 与内链闭环 —— 这就是“内功”。

## 诚实边界（写给自己）

- 已带**确定性质检 rubric（内功层）**与**容错重试**；仍**无搜索量校验**。
- 它证明"**高效、规范地把站铺出来 + 拦住 AI slop**"；**不承诺谷歌排名 / 收录 / 询盘**。
- 演示前**务必录屏兜底**，现场网络/模型抽风就放录屏；最稳的现场路径是 `--dry-run` 本地预览。

## 设计系统 / 模板（生成站「几套」+ 操作台「一套」）

刻意避开"AI 套模板"的观感（系统字 / 紫蓝渐变 / 卡片堆叠），灵感取自 Awwwards 高分获奖项目。
完整规范见 `skills/design-system/SKILL.md`（与 `lib/themes/` 同步）。

- **生成站 = 可插拔模板库**（`lib/themes/`，可继续拓展）：
  - `datasheet-editorial`（**默认**）暖纸 + 朱红，材料数据手册 / 编辑风，B2B 最可信、长文最好读。
  - `atelier-dark` 近黑 + 暖铜，高对比衬线、电影感，精品 / 高端定制调性。
  - `technical-blueprint` 近白工程网格 + 钴蓝，技术标注，最贴满页 ISO / 测试标准的内容。
  - **切换**：行业 config 里写 `theme: <机器名>`（缺省 `datasheet-editorial`）。
  - **新增一套**：写 `lib/themes/<x>.py`（实现 `_base.py` 契约）+ 在 `__init__.py` 注册一行 —— 不动 `preview.py`。详见 design-system skill。
- **操作台 = 一套固定模板**（`templates/index.html`）：暗色技术仪表盘（钴蓝 + 等宽 + 蓝图网格）。
  顶部「样板演示」可**下拉选生成站模板**（来自 `/themes` 路由）即时渲染对比。

并排预览三套主题（真实管线、无需 API key）：

```python
import render_samples as rs
for t in ("datasheet-editorial", "atelier-dark", "technical-blueprint"):
    rs.render_all(theme=t, outdir=f"output/_{t}")   # 然后浏览器打开各自的 index.html
```

> WordPress 落地（诚实边界）：模板目前活在本生成器的渲染层；打包成**原生 WP 主题 / 区块模板**是增量工作量，属"以后可拓展"，单独计。

## 升级到正式版（3.5–5 万）

这些 skill + config 的结构可直接接入 Claude Agent SDK，扩成：多行业模板引擎、内功质检(rubric + 黄金范例 + 案例站校准)、多人 RBAC 后台、任务/日志、以及 WordPress 之外的多 CMS 适配器。

## 合作伙伴快速上手（无需 API key）

克隆后想立刻看样板站：

```bash
pip install -r requirements.txt
python render_samples.py        # 用 output_src/*.json 的样例内容离线渲染
```

然后浏览器打开 `output/index.html` —— 整组互链的 PU 合成革样板站、带质检看板与 JSON-LD，**不需要 ANTHROPIC_API_KEY**。

更简单：直接起网页 UI，点按钮即可（同样零 key）：
```bash
python app.py        # 打开 http://127.0.0.1:5000
```
页面顶部绿色 **🎬 一键样板演示** 按钮 = 调用 `/demo` 路由，用 `output_src` 即时渲染并打开样板站，**不调用任何 LLM、不需要 key / WordPress**。下方表单的"运行"才是真实生成管线（需配 `.env`）。
要跑真实生成管线，配 `.env`（见 `.env.example`）后执行 `python run.py --dry-run`。

> 说明：`output/`（渲染后的 HTML）是生成产物，已 gitignore；样例内容源在 `output_src/*.json`（随仓库提交）。`docs/` 内含**内部报价与演示话术**，仅供项目协作方查看。

