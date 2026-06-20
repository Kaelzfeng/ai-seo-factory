# 开源 Skills 接入地图(2026-06-07)

> 调研:patchright + gh 实采 GitHub。红线:许可证只收 **MIT / Apache-2.0 / BSD / OFL / ISC**,
> **禁 GPL / AGPL**。产品跑 **DeepSeek(非 Claude)**,领域 `SKILL.md` **不能 drop-in 进生成管线**——
> 走「**提炼提示词**」进 `skills/seo-content`、`lib/intake.py`;dev 工作流 skill 才是「装进 `.claude/skills`」。
> 关联任务 #48。memory: [[project-console-sidebar-direction]] 同源的「开源优先」红线见 [[feedback-open-source-first]]。

---

## 0. 一句话结论

- **superpowers**(obra,MIT,★220k)= 14 个**开发工作流元技能**,**已全局装好、即用**,没有领域 skill。
- **领域 skill 的金矿 = `rampstackco/claude-skills`(MIT)** —— 一套**完整 SEO + 内容 + 建站生命周期**库,
  跟我们路线图(#8/#28/#30/#32/#33/#36)大面积重叠。**最高价值是把它的 `programmatic-seo` 等提炼进我们的产品管线。**
- **已装**:`anydesign`(MIT)→ `.claude/skills/anydesign/`,自动化我们「扒大厂设计→tokens」工作流。

---

## 1. superpowers(已全局装,MIT)—— 干活直接用

`obra/superpowers` v5.1.0(`~/.claude/plugins/.../superpowers`)。对我们最相关:

| skill | 用在哪 |
|---|---|
| `brainstorming` | 把毛想法问成设计(需求不清时先跑) |
| `writing-plans` / `executing-plans` | 多步实现前写计划、按计划执行 |
| `systematic-debugging` / `root-cause-tracing` | 查 bug 先定位根因 |
| `test-driven-development` | 写实现前先写测试 |
| `verification-before-completion` | 收工前真机/测试验证(我们一直在做) |
| `requesting/receiving-code-review` | 评审闭环 |
| `dispatching-parallel-agents` | 配合 Workflow 并行派子代理 |
| `using-git-worktrees` | 隔离并行改文件 |

> 注意 [[reference-workflow-auth-review-blocked]]:Workflow 里评审 auth 代码会被网络安全过滤误杀。

---

## 2. 领域 skills(已过许可证红线)

### 2a. 正中产品域 —— `rampstackco/claude-skills`(MIT,★310)
**「Brand Build」~100 个 skill**,`skills/<name>/SKILL.md + references/`。**完整 SEO 套件**:

| rampstackco skill | 对应我们 | 怎么用 |
|---|---|---|
| **`programmatic-seo`** | **产品核心**(规模化建站) | **提炼**进 `seo-content` + 质检理念(见 §4) |
| `seo-keyword` / `seo-keyword-gap-audit` | #8 关键词 agent | 提炼关键词意图/缺口逻辑 |
| `seo-competitor` / `competitor-experience-audit` | **#32 找对标** | 提炼竞品发现+审计流程 |
| `seo-backlink-audit` / `seo-offpage` / `seo-onpage` | #33 内外链 | 内链架构、锚文本纪律 |
| `pillar-content-architecture` | **#36 支柱+簇两轴** | 提炼 hub-and-spoke 拓扑 |
| `content-strategy` / `content-brief-authoring` / `content-and-copy` / `long-form-content-frameworks` | 内容生成 | 提炼 brief→长文框架 |
| `editorial-qa` | 质检(lib/quality.py 锁定,只扩) | 抽样质检纪律 |
| `seo-aeo-geo` | **新卖点** | AI 答案引擎优化=付费档差异化 |
| `vertical-site-conventions` | #30 各行业站视觉 | 行业站惯例库 |
| `seo-technical` / `seo-site-health-audit` / `seo-rank-tracking` / `seo-traffic-diagnosis` | 付费档诊断 | #34 加钱解锁的审计 |
| `design-system` / `design-standards` / `art-direction` / `frontend-component-build` | 模板/视觉 | #28 行业模板库 |

### 2b. SEO-first intake 范式 —— `BuildShipGrowRepeat/nextjs-sanity-blog-skill`(MIT)
`building-blog`:**40 问 intake → 一页计划 → 20 段 spec**(+ `blog-technical-requirements.md`、`blog-image-style-guide.md`)。
**几乎就是我们 `lib/intake.py` 的范式** → 借它的问题集/spec 结构充实我们的反问 agent。Next.js+Sanity 特定部分忽略。

### 2c. 抓取/调研(给 #32)
| skill | 许可 | 用途 |
|---|---|---|
| `michalparkola/tapestry-skills`(`article-extractor`/`youtube-transcript`) | MIT ★428 | 抓竞品文章正文+元数据 |
| `openweb-org/openweb` | MIT | agent 原生访问任意网站(自动解 auth) |
| `sanjay3290/ai-skills`(`deep-research`/`imagen`/`postgres`) | Apache-2.0 ★311 | 自主竞品调研(Gemini 实现,范式可移植) |

### 2d. 设计/视觉(给 #30 + 我们扒设计工作流)
| skill | 许可 | 用途 |
|---|---|---|
| **`uxKero/anydesign`** ✅已装 | MIT ★94 | 图/URL/Figma→`design.md`+tokens(自动化扒设计) |
| `wholiver/swiftui-design-skill` | MIT ★129 | 「反 AI Slop 六条铁律」设计规则(治生成站 AI 味,中英双语) |

### 2e. 元/工具
| skill | 许可 | 用途 |
|---|---|---|
| `yusufkaraaslan/Skill_Seekers` | MIT ★14k | 把文档站/仓库/PDF 转成 skill(DeepSeek 文档、SEO 指南→skill) |
| `anthropics/skills`(docx/pdf/xlsx) | ⚠️ 待核 SPDX | 以后「导出 SEO 报告为 docx/xlsx」 |

### 🚫 排除(红线)
- `NeoLabHQ/context-engineering-kit`(prompt-engineering / subagent-driven-development / software-architecture / kaizen)= **GPL-3.0**,禁用。

---

## 3. 已落地 / 待办

- ✅ **装 dev skill**:`anydesign` → `.claude/skills/anydesign/`(SKILL+references+scripts,去掉示例大图)。需 `pip install -r requirements.txt`(playwright 等)后用 `scripts/capture_site.py` 扒站。
- ⏳ **提炼进产品管线**(见 §4):`programmatic-seo` → `skills/seo-content`;`building-blog` 40 问 → `lib/intake.py`。
- ⏳ **可选再装**:`tapestry/article-extractor`(#32 抓竞品)、`Skill_Seekers`(转文档)、`swiftui-design-skill`(反 AI slop 规则)。

---

## 4. 提炼 spec:`programmatic-seo` + `building-blog` → 我们的管线

我们 `skills/seo-content/SKILL.md`(v2)**已吸收 pSEO 大半**(Information-Gain gate = 每页独特价值;禁模板变量替换/30–40% unique = 反薄页)。**增量(我们还没有的)**:

1. **AEO/GEO·首屏答案**:用户的具体问题在**前 200 词**就答清、结构化到能被 AI 答案引擎直接抽取引用(pSEO「above-the-fold answer」)。→ 加进 seo-content 结构要求。
2. **Schema 纪律**:每页带 JSON-LD 结构化数据(Product/FAQ/BreadcrumbList…),模板级渲染。→ seo-content 输出要求 + 后续 run.py 注入。
3. **内链密度**:每页 **5–15 条**内链(父类目/兄弟页/相关记录),锚文本带词。→ seo-content 已有 related pages,补密度下限。
4. **刷新纪律**:标注哪些字段易过期(价格/年份)需定期刷新。→ #34 付费档诊断 + content-refresh。
5. **数据源护城河自检**:开跑前问「这数据别人能不能复制?」不能=有 moat,能=纯 AI 改写=薄页风险。→ intake 反问加一问。
6. **building-blog 40 问 intake**:把它的结构化问题集(行业/受众/市场/竞品/语气/技术约束)对齐进 `intake.py`,让反问更全。

> 落点:`skills/seo-content/SKILL.md`(已做首轮:加 AEO 首屏 + schema + 内链密度)、`lib/intake.py`(待)、
> 质检概念(`lib/quality.py` **锁定只扩**,加抽样审计/schema 检查走新模块)。
