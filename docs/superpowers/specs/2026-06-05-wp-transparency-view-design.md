# 设计方案 · WordPress 页面制作透明视图(生成档案 v2)

> 日期:2026-06-05 ｜ 状态:已与客户口头对齐,待书面复核
> 落地目录:`design_round/transparency/` ｜ 视觉语言:已批准的「拼版台」

## 0. 一句话

做一个**能直接发给客户的网页**,用一套**真实样板数据**(PU 革,8 页),把
"页面怎么被生成、SEO 关键词怎么落位、质检凭什么给这个分、最后怎么上 WordPress"
**摊开给客户看**。对治客户对"AI 一键生成黑箱"的不信任。标语「生成不黑箱,每页看得见」。

## 1. 痛点与卖点

- **痛点**:买 SEO 的客户不信"AI 一键生成"——看不到页面怎么来、关键词有没有做对、质量凭什么。成交卡在不信任。
- **卖点 = 透明 = 信任**。两个"信任中心"都**忠于真实代码,不编假流程**(见 [[feedback-honest-no-inflation-pricing]]):
  1. **关键词落位图** ← `lib/quality.py` 的 `keyword_usage` 维度。
  2. **确定性质检评分卡** ← `score_page()` 返回的 `breakdown`(6 维,阈值 70,无 LLM、可复算)。

## 2. 两种"权重"(本方案的核心认知,缺一不可)

| | 给谁 | 目的 | 落在哪 |
|---|---|---|---|
| **关键词权重**(标题/H2/meta/正文密度) | 搜索引擎 | **排得上** | 内容(`seo-content` skill),由 `quality.py` 按位置打分 |
| **视觉权重**(去 AI 味的 CSS 层级) | 人 | **愿意下单** | 生成页主题 `datasheet-editorial` + 本透明视图自身 |

视觉层级的作用是把人眼引到决策点(关键规格/认证/CTA),人扫一眼抓到"凭什么买你"→ 下单更积极。
**透明视图的任务,就是把这两层权重同时摊开、并互为证据。**

## 3. 受众与形态(已定)

- **受众**:买我们 SEO 服务的客户(中小企业/外贸厂),让他放心成交。
- **数据**:**演示数据驱动**(不连真 WordPress;用真实样本 + 确定性管线产出的真数据)。
- **形态**:同一份数据**两种看法** —— ① **▶ 重演**(重放真实事件时间线,直播感)② **📄 档案**(静态可分享,客户自翻)。一个模式切换钮;档案=重演冻结在末态。
- **下钻**:**整站可下钻** —— 点任一主题簇页 → 展开它的关键词落位图 + 六维评分卡。

## 4. 真实数据(8 页 · 已实测 · 写死为事实)

种子词 `PU leather` → 1 支柱 + 7 簇页。`render_samples.py` 实测分数(确定性、无 API key):

| slug | 类型 | 总分 | 真实扣分点(诚实展示用) |
|---|---|---|---|
| pu-leather-guide | pillar | **100** | 满分 |
| pu-leather-vs-genuine-leather | comparison | **98** | 内链 18/20(兄弟链 4 个,超 2–3) |
| pu-leather-vs-pvc-leather | comparison | **98** | 内链 18/20(兄弟链 5 个) |
| types-of-synthetic-leather | guide | **96** | 内链 18/20;meta_title 8/10(标题 44 字符,短于 50–60) |
| pu-leather-for-furniture | application | **96** | 内链 18/20;标题 45 字符 |
| pu-leather-for-automotive | application | **93** | **关键词 10/15:目标词未进标题(−5)**;标题 45 字符 |
| is-pu-leather-durable-waterproof | faq | **98** | 内链 18/20(兄弟链 6 个) |
| microfiber-pu-leather-bags | product | **98** | 标题 48 字符 |

**全部 ≥70 通过。** 并且正文关键词密度 2–4 次(从不堆砌)、规格信号 11–13、违禁词 0 ——
即"关键词加权但给人看"可被真实数据证明。

### 4.1 诚实红线(不可违反)

- **绝不摆假失败页。** 真实数据 8 页全过,就展示全过。
- **诚实通过"通过页里的真实扣分维度"体现**(如 automotive 关键词未进标题、多页超量内链),
  用 `breakdown` 的真实 `notes` / `issues`,**不得编造**。
- **关键词落位 / 评分卡 = 100% 真数据**;**上 WordPress 这一段标注为"演示数据下对真实发布动作的忠实重现(未连真站)"**。

## 5. 信息架构(封面 + 5 环节)

- **封面**:得意黑「生成不黑箱,每页看得见」+ 站点身份(Demo Leather Co., Ltd.)+「▶ 重演生成」+「确定性·可复算」印章。
- **① 主题簇**:种子词 → 8 页拆解树(类型 chip / 标题 / target_keyword / 内链角色 / 真实分数徽章)。**点任一节点 → 下钻**,下方 ②③④ 即该页细节。
- **② 关键词落位(权重轴)**:见 §6。
- **③ 质检评分**:6 维条形(真实 score/max + 真实 notes)+ 总分 + **70 分门槛线** + PASS 徽章 + 真实 issues;印章「确定性·无 LLM·可复算」。
- **④ 上 WordPress**:见 §7。
- **⑤ 结构化与出厂**:JSON-LD(Article/FAQPage/BreadcrumbList)+ 整站内链图 + 8 页 URL + **内嵌真实渲染的成品页**(§8,人侧证据)。

## 6. Stage ② 关键词落位 —— 以"权重"为主轴

把 `keyword_usage` 的真实打分摊成权重图(数值即权重):

| 槽位 | 权重 | 命中判据(`quality.py` 真实逻辑) |
|---|---|---|
| 标题 | **+5** | `_keyword_in(kw, title)` |
| H2 或正文前 150 词 | **+4** | `_keyword_in(kw, headings ∪ first150)` |
| meta 描述 | **+3** | `_keyword_in(kw, meta)` |
| 正文密度 | **+3** | `1 ≤ count ≤ 4`;`0` 缺失;`>6` 堆砌 −3 |

- 槽位**按权重排序**;每槽标分值;**命中标黄(真实文本里的 `<mark>`),未命中标灰**(automotive 标题槽=灰,真实)。
- 正文栏放**密度计**,明确画出「理想 1–4 ｜ **堆砌区 >6(给人看的护栏 · 越界扣分)**」。
- 关键词一律**嵌在真实句子里**展示(不孤立列词)——证明"嵌进能读的句子,不是塞的"。

## 7. Stage ④ 上 WordPress —— 真实 REST 动作的忠实重现

镜像 `lib/wp_publish.py` + `run.py` 发布顺序(演示数据,**明确标注未连真站**):

1. `🔐 verify_auth` → `GET /wp-json/wp/v2/users/me`
2. `get_or_create_category("PU Leather")`(幂等)
3. (逐页)`create_post` 真实载荷:`title / slug / status / excerpt(=meta) / categories / featured_media` + **JSON-LD 注入正文末尾**(展示真实 POST body 摘要)
4. `apply_seo_meta` → 按插件写 Yoast/RankMath 字段 + **回读校验**
5. 固定链接检查(pretty `/slug/`)→ 上线链接 + **如实告警**(本数据集:permalink OK、seo_meta applied)

要点:展示**真实会发出的请求与会做的检查**,让客户看到"SEO 关键词如何被格式化进 title/meta/focus keyword"。

## 8. 转化加权:生成页主题升级(`lib/themes/datasheet.py`,本次新增范围)

现状:`datasheet-editorial` **本身已去 AI 味**(暖纸+单一朱红零渐变、Archivo Black 巨标题 vs Newsreader 正文的狠层级、数据表朱红等宽数值、直角、颗粒纹理、零 emoji)。
**缺口**:做了编辑层级,**未做转化导向的内容加权**。本次**附加**(chrome 层,不动正文):

- **信任条**:从内容里检测认证/标准(复用 `quality.py` 的 `CERT_STANDARD_TOKENS`/`SPEC_SIGNAL_PATTERNS`),汇成一条可扫的 ISO·REACH·SGS 信任带。
- **朱红 CTA 行动块**:把结尾"告诉我们产品与市场,给你报价"做成醒目行动块。
- **关键结论重点句**:拉出 1 句决策结论加视觉重量。

**安全闸**:升级后重跑 `render_samples.py`,**8 页分数必须与 §4 完全一致**(chrome 不进入评分内容)。
不一致 = 改动泄漏到正文 → 回退。升级后**重新生成内嵌成品页**。

## 9. 反 AI 味验收清单(构建的硬闸,逐条核 + 真浏览器截图)

① 零紫/靛蓝渐变、零滥用渐变 ② 左对齐不对称编辑栅格(非全局居中) ③ 直角为主、阴影/圆角分层级(非统一 rounded+soft shadow) ④ 非三列等宽卡片(用账本/树/行式打印机版式) ⑤ 零 emoji(含把 `run.py` 进度行的 🚀✍️📊 在呈现层换成印刷符号) ⑥ 文案=真实数字/例子(零"赋能/无缝/一站式") ⑦ 得意黑 SVG 巨标题 + 狠层级 + 中/西文字距行距分调(中文字距≥0、等宽 tracking 不外溢) ⑧ 间距按编辑节奏非均匀 ⑨ 拿掉 logo 仍搬不走。
**命中任一条 → 打回重做。**

## 10. 技术形态与数据契约

- **`design_round/transparency/build_record.py`**:确定性、**无 API key、无网络**。读 `industries/pu-leather.yaml` + `output_src/*.json`,跑 `quality.score_page` + `schema.jsonld_for` + 复用 `quality.py` 辅助函数算关键词落位 + 拼 `wp_publish` 演示载荷与事件时间线 → 输出 **`record.json`**。
- **`record.json`** 顶层:`meta` / `cluster`(树)/ `pages{slug→{content,quality{breakdown,issues},keyword_placement{slots},schema_jsonld,wp_publish,rendered_preview_path}}` / `event_timeline`(驱动重演)/ `summary`。
- **`design_round/transparency/index.html`**:自包含(内联 CSS/JS),读 `record.json`,渲染封面+5 环节+下钻+双模式。得意黑走 SVG(`svg.json`,由 `gen_svg.py` 同法生成,零 webfont)。
- **内嵌成品页**:`../output/<slug>.html`(升级主题后重渲染)以 iframe/srcdoc 呈现。
- **可分享**:整目录可 `python -m http.server` 托管;Phase 6 另出单文件 `生成档案.html`(内联 record.json + 成品页)做"一个文件分享",尽力而为。

## 11. 构建计划(通宵 Workflow,无人值守)

1. **数据脊柱**:写 `build_record.py` 并运行,校验 8 页全字段。
2. **得意黑 SVG**:生成视图所需中文 display 文案,查无缺字。
3. **转化加权主题**:改 `datasheet.py` 附加件 + 重跑 `render_samples.py` 校验分数不变 + 重渲成品页。
4. **前端搭建**:建自包含 `index.html`(双模式/下钻/内嵌成品页/拼版台语言)。
5. **对抗式自检与打磨**:并行评审(诚实数据追溯 / 反 AI 味+真截图 / 双语排版 / 功能=8 页下钻·切换·重演·响应式),修复循环至干净。
6. **打包交付**:整理目录 + 写《交付说明》+ 终版截图(+ 尽力出单文件)。

完成后由**人(你)做最后审美拍板**:我先自检 + 摆真截图,不直接宣称"做好了"。

## 12. 不在本次范围(明确排除)

- 真实发布到 WordPress(需凭证)——本次演示数据。
- 关键词研究 agent(实时补全/Trends)、DeepSeek 接入、排名爬虫 —— 另立项,需在线协作做。
- 把拼版台落地回 `templates/index.html` 操作台 —— 下一步。

关联:[[project-transparency-saas]]、[[project-ai-seo-content-factory]]、[[feedback-design-reference-high-scorers]]、[[feedback-honest-no-inflation-pricing]]。
