# SEO 引擎设计 Spec(子系统 ① · 核)

> **范围声明**:本 spec 只覆盖**子系统 ① SEO 引擎**——也就是"2+1"的本体(横向+纵向两轴 + 按自然语言改页)。
> **子系统 ② SaaS 壳**(Keycloak 认证 / jCasbin 授权 / OpenMeter 计量计费 / 多租户)**另开一份 spec**,在 ① 单租户/CLI 跑通后再包。
> 选型依据见 [`docs/oss-build-map.md`](../../oss-build-map.md)。许可证红线:只用 MIT/Apache/BSD。
> 日期:2026-06-06。状态:**待用户审阅**。

---

## 1. 目标(一句话)

输入一句自然语言(+可选公司 URL/产品表),引擎自动:**懂这门生意 → 拉全行业的词并排出整站架构 → 生成每一页 → 上帝视角对抗审 → 发布到 WordPress**;并支持事后用自然语言增量改页。

## 2. 核心原则(贯穿全篇)

1. **确定的 → 传统程序;不确定的 → agent/LLM。** 能数、能算、能查表的(词数、内链拓扑、meta 长度、密度、死链、许可证)一律程序;懂行业、判意图、找内容缺口、写、判真伪、按 NL 改的交给 agent。
2. **开源优先,核心自研。** 管道层用成熟开源(已选型),两轴引擎/对抗审/反推词/质检大脑自己写。
3. **诚实不注水。** 免费阶段只用能真实抓到的信号(autocomplete/SERP/Trends 相对热度);**绝对搜索量是付费档**,不靠 LLM 瞎猜补。
4. **双档=商业模式。** 半自动(带 3 个人审节点)=默认;全自动(一路跑到发布)=付费解锁。**引擎本身两档都能跑**,计费门在子系统 ②。

## 3. 数据契约(语言无关,转 Java 只换渲染器)

所有阶段间用结构化对象传递,Python 阶段用 Pydantic,字段名即 Java 迁移契约。

```
BusinessProfile   # 横向轴产物
  industry, company, deliverables[], buyer_personas[], constraints, tone, terminology, language

Keyword           # 纵向轴原子
  text, intent(comparison|commercial|application|informational|other),
  support(int, 需求强度代理), source(suggest|paa|serp|competitor|seed), is_question(bool)

Topic             # 一簇语义相关词 = 一个页面候选
  label, intent, keywords[Keyword], head_keyword, support_sum, page_type, role(pillar|cluster|product|faq|...)

SiteBlueprint     # 纵向轴产物(站点蓝图)
  topics[Topic], pages[PagePlan], link_graph(edges[]), counts{pillar:n, cluster:n, product:n, ...}

PagePlan          # 一页的生成指令
  slug, url, page_type, role, target_keyword, supporting_keywords[], pillar_url, sibling_urls[], related[]

PageContent       # 生成产物
  title, meta_description, html, image_query, jsonld[]

QualityReport     # 质检产物
  score, issues[], dimensions{...}, blocking(bool)
```

---

## 4. 流水线(Stage 0–6)

```
S0 需求澄清  ──► S1 横向·生意画像 ──► S2 纵向·全量词→站点蓝图 ──► S3 逐页生成
                                                                      │
   发布 WP ◄── S6 发布前确定性闸 ◄── S5 内外链装配 ◄── S4 上帝视角对抗审 ◄┘
```

人审节点(半自动档插入,全自动档跳过):**① S1 后确认生意画像** · **② S2 后确认站点蓝图(最关键)** · **③ S4 后审内容再发布**。

### Stage 0 · 需求澄清(agent,不确定)

- 借 Superpowers brainstorming 的"一次一问"模式,**自研一个"需求澄清 agent"**(它是产品功能,不是开发期 skill)。
- 输入:一句 NL +(可选)公司 URL / 产品表。有 URL 则先用 `googlesearch-python`/`extruct` 抓现有站做底。
- 产出:把模糊需求收敛成可执行范围,喂给 S1。
- **确定性兜底**:澄清轮数上限、必填槽位(行业/语言/目标市场)缺失则强制追问——这部分程序卡。

### Stage 1 · 横向轴 · 生意画像(agent,不确定)

- agent 研究:行业 → 公司可交付 → 目标买家画像 → 拆需求。
- 产出 `BusinessProfile`,**约束后续一切**(语气、术语、E-E-A-T、语言),防跑偏。
- 注入到所有下游 prompt(已验证:行业 profile 注入润色 prompt 能保住制造商语气)。
- **【人审节点 ①】**:半自动档在此停,给人确认/改画像。

### Stage 2 · 纵向轴 · 全量词 → 站点蓝图(混合:程序为主 + agent 点睛)

> 这是引擎价值最浓的一段,也是之前 brainstorm 没钉死的部分。下面是**具体算法**(请重点审这段)。

**2.1 全量抓词(程序,确定)** — `keyword_scout` grounded 模式
- seed(来自 S1 行业/产品)→ Google/Bing autocomplete + question-wheel + SERP/PAA + 竞品页反推。
- 每个词标注 `{intent, support, source, is_question}`。**grounded 模式不允许 LLM 瞎猜词**(只在零结果兜底时才 LLM,且标 source=guess 并默认关闭)。
- 趋势信号:`trendspyg`(MIT)给相对热度,填进 `support`(免费档);绝对量留付费档。

**2.2 意图归类(程序,确定)** — 规则引擎
- 用 `keyword_scout._INTENT_RULES` 把全量词按意图分桶(comparison/commercial/application/informational/other)。
- 规则可解释,正好喂"透明化 SaaS"卖点(UI 能展示"为什么这个词归这类")。

**2.3 主题聚类(确定打底 + 不确定升级)** — 一簇=一个页面候选
- 小词池:程序去重 + 近重复合并(已有 cluster_plan 思路)。
- 大词池:升级到 `huggingface/text-clustering`(Apache,embed→UMAP→FAISS)做语义聚类。
- 每簇取 `head_keyword`(support 最高者)与 `support_sum`。

**2.4 页型映射 + 角色分配(程序查表,确定)** — `_TYPE_BY_INTENT`
| 意图 | 页型 | 角色 |
|---|---|---|
| informational 宽头词(support 最高的主题) | pillar | 支柱页(每大主题 1 个) |
| comparison | comparison | cluster |
| application | application | cluster |
| commercial / transactional | product / category | product |
| informational 长尾问题 | faq / guide | cluster |

**2.5 页面系统配额(程序算,确定)**
- 每个 `support_sum ≥ 阈值` 的簇 → 1 页;阈值随档位/预算可调。
- 总页数 cap = 预算档(demo/付费档不同)。低于阈值的小簇并进最近 pillar 的 FAQ。
- 输出 `counts{pillar, cluster, product, faq}` —— 即"做多少分类页/产品页/支撑页"。

**2.6 站点架构 + 内链图(程序,确定)** — pillar-cluster 拓扑
- pillar 链向**本主题全部** cluster;cluster 回链 pillar 一次 + 2–3 个兄弟。
- 用 `NetworkX`(BSD)建有向图做**全站视图**:查孤儿页、断簇、pillar 可达性。
- 产出 `SiteBlueprint`。
- **【人审节点 ②·最关键】**:半自动档在此停,给人确认整站蓝图再生成。

### Stage 3 · 逐页生成(agent,不确定)

- 对每个 `PagePlan`,用 writer agent(DeepSeek `deepseek-v4-pro`)生成 `{title, meta_description, html, image_query}`。
- **必注入 `CURRENT DATE`**(否则模型用训练期旧年份——run.py 现缺,要补)。
- 注入 `BusinessProfile`(语气/术语)+ pillar_url + sibling_urls + related。
- 渲染管线(自研,零 GPL):页面 schema → **Jinja2** 骨架(嵌 HyperUI 区块)→ 同源数据 emit **JSON-LD** → 输出 **Gutenberg 块 HTML**(纯字符串 emitter)。
- 并发生成(已验证 ThreadPoolExecutor)。

### Stage 4 · 上帝视角对抗审(三层护栏,确定+不确定)

> 本 spec 最硬的质量保证。三层缺一不可(已实证)。

**层 A · 程序可数项(确定)** — `quality.py`(锁定,只扩不改)+ 新 `quality_ext.py`
- quality.py:关键词落位/密度(上下限)、title/meta 长度、禁词、占位符泄漏(`[Brand]`)、按页型内链规则、署名可见、关键词堆砌。
- quality_ext.py(新增维度,接 run 层加权,不动 quality.py):`textstat` 可读性、`datasketch` 跨页去重(防量产撞稿)。
- 入库前 `nh3` 净化(防脏标签进 WP)。

**层 B · agent 判不确定(模糊)**
- 捏造第三方统计("九大车企九家用 PU")、自然度、页型贴合、E-E-A-T、信息增益。
- 实证:prompt 自检 + 对抗 agent 能压住(0 捏造跨页型守住)。

**层 C · agent 领域事实核查(NEW,关键)**
- 标准/单位/量纲核查(实测抓到:Martindale 误标 ISO 5470-2[实为 Taber]、耐光 "Grade 6"[灰卡只到 5])。
- **这类错 quality.py 和 prompt 都抓不到,只有带领域知识的 agent 能抓。**
- 典型多 agent 对抗:每个发现派独立 skeptic 复核,多数否决才杀。

**确定性后处理(层 A 的修复手)** — `_postfix` 思路,**按页型**
- meta 截 ≤160、sibling 内链 cap(cluster ≤3;**pillar 不 cap**——pillar 须链全簇,一刀切会误伤)。
- 实证:确定性分 94→100、问题清零。

- **【人审节点 ③】**:半自动档在此停,人审对抗审结果 + 改稿再发布。

### Stage 5 · 内外链装配(程序为主,确定)

- **内链**:按 S2.6 link_graph 注入锚文本(锚文本黑名单走 quality.py)。
- **外链**:页内引用先做(引权威标准/来源);站外外链建设是后续独立模块。
- 发布后 `lychee`(Apache)跑死链体检(纯 I/O,不进 quality.py)。

### Stage 6 · 发布前确定性闸 + 发布(程序,确定)

- 闸:任一 blocking issue 未清 → 不发(staging 裸 IP→真实域名替换、CJK 未译、占位符泄漏)。
- 发布:经 WP REST API 用现有 `wp_publish` 发(Gutenberg 块 HTML 进 `content` 字段)。
- **硬约束**:WordPress 是客户死要求,不可静态替代;`WP_ALLOW_HTTP` 仅限回环(SSH 隧道发布)。

---

## 5. "+1" · 按自然语言改页(agent,不确定)

客户买的核心 agent 能力。独立于 S0–S6 的生成主线,作用在**已生成/已发布**的页上。

- 输入:目标页 + 一句 NL("把这页的语气更专业些 / 加一段关于耐磨测试的 FAQ / 把对比表换成 PVC")。
- agent:定位页 → 理解意图 → 局部改(只改被点名的部分,保留其余)→ **同样过 Stage 4 三层护栏** → 重发布。
- 复用已验证的"定向修复提示词(只修被点名 issue)"经验。
- 确定性边界:改动 diff 可见、可回滚;改完重打分,keep-better(诚实复评,不退步才采纳)。

---

## 6. 双档(半自动/全自动)如何落

- 引擎内部走同一条流水线;**档位 = 是否在人审节点 ①②③ 停。**
- 全自动:三个节点全自动通过(用对抗审的"通过即放行"结果)。
- 半自动:三个节点产出"待确认"事件,等人操作。
- demo 一律全自动(秀丝滑);计费门(全自动=付费)在子系统 ② 的 OpenMeter/RBAC 上,引擎不含计费逻辑。

## 7. 现有资产 vs 待建

| 已有(雏形) | 待建/待补 |
|---|---|
| `keyword_scout.py`(抓词+意图规则) | S0 需求澄清 agent |
| `lib/llm.py`(DeepSeek 接入) | S1 生意画像 agent |
| `industries/pu-leather.yaml`(预设页,**要关掉换 grounded**) | S2 全量词→蓝图(2.3–2.6 落地,#31) |
| `quality.py`(锁定,层 A) | `quality_ext.py`(textstat+datasketch) |
| `_postfix.py`(确定性后处理,**改成按页型**) | 渲染管线(Jinja2+Gutenberg/JSON-LD emitter) |
| `wp_publish`(S6 发布) | S4 层 C 领域事实核查 agent |
| skill `seo-content`(writer) | 竞品页反推词(#32)、按 NL 改页(#33) |
| | run.py 注入 `CURRENT DATE`(bug 补) |

## 8. 验收(引擎跑通的标准)

单租户/CLI:给一句"PU leather 出口"→ 自动产出 ≥8 页一套站(pillar+cluster+product+faq),内链图无孤儿、三层护栏全过、发布到 WP staging、死链 0、可读性达标、跨页去重无撞稿;再给一句 NL 改其中一页且不退步。

## 9. 明确不在本 spec(后续 spec)

- 子系统 ② SaaS 壳(Keycloak/jCasbin/OpenMeter/多租户/计费/登录界面)。
- 付费搜索量 API 接入(#34,DataForSEO/Ahrefs 等)。
- 站外外链建设独立模块。
- 整体转 Java(契约已按语言无关设计)。

## 10. 开放问题(请用户审这几点)

1. **S2.5 页面配额阈值**:用绝对 support 阈值,还是"取 top-N 簇"?demo 档 cap 多少页合适(8?12?)。
2. **S2.3 聚类升级触发点**:词池多大时从"程序去重"切到"text-clustering 语义聚类"?
3. **人审节点的"确认"粒度**:节点 ② 确认整站蓝图时,人是逐页勾选还是整体批准?
4. **"+1 改页"的范围红线**:允许改结构(增删整段/换组件)还是只允许改文案?改结构要不要重过蓝图审?
