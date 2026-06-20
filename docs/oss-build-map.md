# 开源选型 · 买-造地图(OSS Build/Buy Map)

> 实现铁律:**能用成熟开源就用,核心差异化才自研。** 许可证硬红线:只接受 **MIT / Apache-2.0 / BSD**;**GPL / AGPL / SSPL 一律不可打进 SaaS 代码**(调它的 HTTP/REST API 不算污染,把它的源码 link 进我们代码才算)。
> 产品终局要整体转 **Java**,故优先 Java/JVM 生态或语言无关(独立服务,API 集成)的方案。
> 调研日期:2026-06-06。许可证均逐个核实。

---

## 1. 核心大脑 —— 必须自研(护城河,开源给不了)

| 层 | 自研件 | 说明 / 现有资产 |
|---|---|---|
| 抓词 | suggest + question-wheel 抓取 | `lib/keyword_scout.py`。同类开源全是无许可个人脚本,我们已做得更好,留着 |
| 抓词 | **搜索意图分类(规则引擎)** | `keyword_scout._INTENT_RULES`。无对口开源;规则可解释,正好喂"透明化 SaaS"卖点 |
| 对标 | **竞品页 → 反推命中词** | 开源(open-seo-crawler 等)只做 on-page 技术审计,**不反推词**;反推=核心 IP。抽取层可借 extruct |
| 两轴 | 横向生意画像 + 纵向全量词→意图分组→站点架构 | 产品价值本体,无库可拿(programmatic-SEO 开源全是 GPL 的 WP 插件或玩具仓) |
| 渲染 | 页面 schema(Pydantic 契约)+ 渲染管线 | schema→模板→HTML 这条管线是对抗审/内外链/行业匹配的落点,语言无关才撑得住转 Java |
| 渲染 | **Gutenberg 块 emitter** | 关键事实:Gutenberg 块 = 普通 HTML + `<!-- wp:* -->` 注释定界符,是**纯文本序列化格式**。模板直接 emit 字符串,经 WP REST `content` 字段 POST 即原生块。**不需要库,也无 GPL 风险** |
| 渲染 | **JSON-LD emitter(薄层)** | FAQPage/Product/Article/BreadcrumbList 本质是 dict→json.dumps;自研保证"结构化数据与可见内容同源" |
| 质检 | 内链策略判定、关键词落位/密度、反 slop + 规格/认证信号打分 | `lib/quality.py`(**锁定文件,只扩不改**)。通用 SEO linter 不懂"manufacturer 语气 + ISO/REACH/Martindale" |
| 对抗审 | 上帝视角领域事实核查(标准/单位/量纲) | agent 层(不确定);quality.py 和 prompt 都抓不到错误标准引用 |
| 壳 | **多租户隔离薄层** | Spring Boot + Hibernate 原生多租户(schema-per-tenant),租户 ID 从 JWT claim 取。社区 starter 全是负债,自己写更干净 |

## 2. 拿来即用(全 MIT/Apache/BSD)

| 用途 | 选型 | 许可证 | 复用方式 |
|---|---|---|---|
| 自然结果 SERP(对标谁在排名) | googlesearch-python (Nv7-GitHub) | MIT | 直接封装,纯 requests+bs4 |
| schema/结构化数据抽取(抓对标) | extruct (scrapinghub) | BSD-3 | JSON-LD/Microdata/OG 抽取事实标准 |
| 免费趋势信号(#34 免费档) | **trendspyg** | MIT | pytrends 已归档→换它;相对热度非绝对量(量仍付费) |
| 大规模语义聚类(词池大了再上) | huggingface/text-clustering | Apache-2.0 | embed→UMAP→FAISS;引 torch 重依赖,转 Java 走 DJL 或微服务 |
| 视觉区块库 | HyperUI / Flowbite / Preline | MIT | Tailwind 区块当积木,拼 pillar/cluster/对比/FAQ 模板骨架 |
| 模板引擎(内部) | Jinja2 | BSD | 模板继承 + autoescape + SandboxedEnvironment |
| 模板引擎(客户自改沙箱) | python-liquid (jg-rp/liquid) | MIT | Liquid 非求值,天生为"客户可写但不能跑服务器代码"设计 |
| 认证 IdP | **Keycloak** | Apache-2.0 | 独立服务跑 OIDC/SAML;Java 同生态可深度二开 |
| 授权(简单期) | jCasbin | Apache-2.0 | 嵌库,Java 原生,多租户 RBAC(domain),零额外服务 |
| 授权(复杂期) | OpenFGA | Apache-2.0 | 独立服务 + Java SDK,CNCF Incubating,ReBAC |
| 计量/配额/计费 | **OpenMeter** | Apache-2.0 | 独立服务,内置 quota/usage-limit;**正好挂"全自动=付费解锁"** |
| 后台(业务) | React-Admin / Refine | MIT | 接 Java REST API 自动生成 CRUD |
| 后台(运维) | Spring Boot Admin | Apache-2.0 | 监控 JVM 健康,与业务后台不冲突 |
| 死链探活 | lychee | Apache-2.0 OR MIT | Rust 二进制,subprocess 调,语言无关;纯 I/O 不该进 quality.py |
| 可读性评分 | textstat | MIT | Flesch 等;quality.py **空白维度**,接 `lib/quality_ext.py` |
| 重复内容去重 | datasketch (MinHash+LSH) | MIT | 跨页防撞稿;quality.py **空白维度**,接 `quality_ext.py` |
| HTML 入库净化 | nh3(Python)/ OWASP Java HTML Sanitizer(Java) | MIT / Apache | 防 XSS 脏标签进 WP;**别用已弃用的 bleach** |
| 链接图全局视图 | NetworkX | BSD-3 | 跨页孤儿/断簇检测底座(quality.py 只能逐页);策略判定仍自研 |

## 3. 🔴 红线 —— 绝不打进代码

| 项目 | 问题 | 替代 |
|---|---|---|
| `schemaorg` PyPI 包 | **AGPLv3+** + 2021 停更(名字最诱人,最毒) | 自研 JSON-LD emitter |
| **Lago** 计费 | **AGPL-3.0** | OpenMeter (Apache) |
| 绝大多数 **WP 主题**(ThemeForest/WP.org) | **GPL**(打进 SaaS 代码即污染) | 调 WP API ✅;视觉用 HyperUI(MIT) |
| `sundios/people-also-ask`、各 suggest 脚本 | **无 LICENSE 文件**(不可商用) | 只抽思路;PAA 自研复用 question-wheel |
| `bleach` | 2023-01 **已弃用**(html5lib 失维) | nh3 |
| authentik **enterprise 目录** | source-available(非 MIT) | 只用其 MIT 核心,避开 enterprise 功能 |
| Oso 授权 | 开源版边缘化,主推付费 Cloud | jCasbin / OpenFGA |

## 4. 落地配方(零 GPL 全程合规)

**内容管线**:自研页面 schema(Pydantic)→ **Jinja2** 渲染骨架(嵌 **HyperUI** 区块)→ 同源数据 emit **JSON-LD**(自研薄层)→ 输出 **Gutenberg 块 HTML**(自研 emitter)→ 经 **WP REST API** 用现有 `wp_publish` 发布。客户自改模板叠 **python-liquid** 沙箱。

**质检管线**:`quality.py`(锁定,内链/落位/反 slop)+ 新 `quality_ext.py`(textstat 可读性 + datasketch 去重)+ 发布后 lychee 死链体检 + 入库前 nh3 净化 + NetworkX 全站链接图。

**SaaS 壳**:Keycloak(认证)+ jCasbin/OpenFGA(授权)+ OpenMeter(计量/配额,挂全自动=premium)+ React-Admin(后台)+ 自研 Hibernate 多租户路由。

**转 Java 影响**:纯 HTTP+解析逻辑(googlesearch/extruct/trendspyg)迁 Java 很轻(jsoup);难迁的只有 text-clustering 的 PyTorch 栈→DJL 或独立 Python 微服务。模板与 JSON-LD 逻辑抽象成语言无关 schema/数据契约,换语言只换渲染器。
