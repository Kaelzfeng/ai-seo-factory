# 关键词侦察 v2 · 真实问题层(Question Layer)设计

**Goal:** 给 `lib/keyword_scout.py` 加一层「真实问题」采集与暴露 —— 把买家**真在搜索框里问**的问题(从搜索自动补全的前缀位采到),作为确定性、有出处、零 API key 的信号,喂进页面规划与透明视图。

**红线(继承自项目):** 真实数据不注水。任何问题都必须来自真实补全/SERP;抓不到就如实标注 `unavailable`,绝不用 LLM 或规则**杜撰**问题。不改 `lib/quality.py`(锁定镜像模块)。

---

## 背景与动机

现状 `harvest()` 用 `DEFAULT_MODIFIERS = ["", "for", "vs", "best", "wholesale", "supplier", "how to", "what is", "is", "price"]`,且**总是**拼成 `seed + " " + mod`(后缀位)。于是:

- `"what is"` → 查询 `"PU leather what is"`(别扭,几乎不出问题);
- 真正出问题的是**前缀位** `"what is PU leather"` → `is pu leather durable / real leather / waterproof / toxic`、`why does pu leather peel`、`difference between pure leather and pu leather`。

实测(2026-06-06,沙箱内 live):前缀问题轮可靠返回 7-10 条真问题/探针,零反爬、零 key。**这是「关键词 agent」线里唯一现在就能真做又能真验的增强。**

## 非目标(YAGNI)

- ❌ LLM 润色 / DeepSeek provider 分支 —— 需 key,本期不做。
- ❌ Google Trends 趋势排序 —— pytrends 限流不稳、无法可靠验证,本期不做。
- ❌ 百度/中文适配器 —— 沙箱地域受限、当前样本全英文外贸,本期不做。
- ❌ 改 `run.py` 的 plan 形状(`grounded_plan` 已透传 plan;问题层是**叠加**不是替换)。

---

## 架构

三个确定性纯函数 + 一个最小集成,全部零 key:

### 1. 问题轮采集 `harvest_questions(seed, …)`

**职责:** 用一组问题前缀 + 介词/比较模式,在**前缀位**查 Google 自动补全,返回真问题池。

- 前缀集(确定性、可解释):
  - W/H 疑问词:`what / what is / why / how / how to / when / where / which / who`
  - 是非/能否:`is / are / does / do / can / will / should`
  - 比较/介词:`<seed> vs`、`<seed> for`、`<seed> with`、`<seed> without`、`difference between <seed> and`
- 每条探针:`google_autocomplete(probe)`,复用现有磁盘缓存(`recon/.cache`)与 `polite` 限速。
- 输出:`{question: {"sources": [...], "probes": [...], "intent": str}}`;`question` 经 `_norm` 规范化(小写、压空白、去重),长度 < 8 字直接丢。
- `collect_log=True` 时附 `(pool, log)`,log 记每条探针打到哪、返回什么 —— 供透明视图「问题怎么来的」。

### 2. 池合并 `merge_questions(base_pool, q_pool)`

**职责:** 把问题池并进 `harvest()` 的主词池,**不破坏**既有 `support` 语义。

- 已存在的词:补 `is_question=True`、并 `probes` 进 `queries`、`sources` 取并集。
- 新增的词:以 `support = len(probes)` 落入主池,带 `is_question=True`、`intent=classify_intent(kw)`。
- 返回合并后的 pool(形状与 `harvest()` 输出兼容:`{kw: {sources, intent, support, queries, is_question?}}`)。

### 3. FAQ 桶偏好真问题(改 `cluster_plan`)

**职责:** informational/faq 桶选页时,**真问题优先**;FAQ 页 evidence 列真实问题。

- 现有 informational 排序在「good 正则(durable|waterproof|clean…)」基础上,**再加一档**:`is_question` 为真的排最前(`key = (0 if is_question else 1, 0 if good else 1, -support, len)`)。
- pillar 与其他桶逻辑不变(避免回归)。
- 被选中的 informational 页:`evidence` 优先填该词关联的真问题(`queries` 里 `?`/疑问词开头者),不足再退回原 `queries[:4]`。

### 4. 记录暴露(改 `grounded_plan` + `write_record`)

- `grounded_plan` 内部:`harvest(collect_log)` 后再 `harvest_questions(collect_log)`,`merge_questions` 合并,`cluster_plan` 照旧。返回 dict 增 `questions`(分组:`{intent: [{q, support, sources}]}`,按 support 降序、每组 ≤ 12)与 `question_log`。
- `write_record` 的 JSON 增顶层 `questions` 段 + `meta.question_count`;`note` 维持「确定性·真实搜索补全·零 LLM·有出处」。
- 既有 `plan` / `intents` / `harvest_log` 字段**保持不变**(透明视图旧消费不破)。

### 5.(stretch · 诚实降级)PAA `harvest_paa(seed)` —— **本期 descope,已实测不可达**

设计意图:用 patchright 隐身浏览器打 SERP 抓「People also ask」真问题,**任何**失败 →
`{"available": False, "reason": ...}`,**绝不**用别处数据冒充。

**2026-06-06 主循环 patchright 实测结论(诚实记录):**
- **Google SERP:被挡** —— `/search` 直接 302 到 `/sorry/index` 反爬验证页(数据中心 IP)。
- **Bing SERP:可开但内容被降级** —— body 仅 ~5.7KB,「People also ask」只抓到 1 条
  (`Is PU leather eco-friendly?`),相关搜索为空,不可靠。

→ **真 SERP PAA 在本环境拿不到稳定数据,本期不实现 `harvest_paa`**。可靠的真问题源就是
autocomplete 问题轮(§1-§4,已落地 + 真网络验证)。若将来换可出口 IP / 加代理 / 接
SerpAPI 类付费源,再按「成功写 `paa:{available:true}`、失败写 `paa:{available:false,reason}`、
绝不杜撰」补回。这条降级设计本身已被实测验证正确。

---

## 数据流

```
seed
 ├─ harvest()            → 主词池(后缀修饰词;support=查询数)        [现有,不动]
 ├─ harvest_questions()  → 问题池(前缀问题轮;真问题)               [新]
 │     └─ merge_questions() → 合并池(is_question 标记)              [新]
 ├─ cluster_plan(合并池) → pillar + 支撑页(FAQ 偏好真问题)         [改]
 └─ write_record()       → keyword_record.json{plan, intents,
                            harvest_log, questions}                  [改]
                                  ↓
              design_round/transparency 的 Stage 00「词/问题怎么来的」
```

## 错误处理

- 单条探针失败:`stderr` 记一行 + log 里记 `error`,继续(与现有 `harvest` 一致)。
- 全部探针失败(断网):`questions` 为空 dict,`grounded_plan` 仍出 plan(问题层是叠加,不阻断主流程)。
- PAA 任意失败:降级标注,不抛、不污染主结果。

## 测试策略(TDD,mock 网络)

纯函数全部可单测,**不打真网络**(mock `google_autocomplete`):

1. `harvest_questions` 用 mock 补全 → 断言问题池含预期真问题、带 `probes` 出处、短词被滤。
2. `merge_questions` → 断言既有词被打 `is_question` 且 `support` 不被破坏;新词正确落入。
3. `cluster_plan` 偏好:构造含真问题与泛词的池 → 断言 FAQ 页 target 是真问题。
4. `write_record` → 断言 JSON 含 `questions` 段 + `meta.question_count`,且 `plan/intents/harvest_log` 仍在。
5. `grounded_plan` 端到端(mock 两个 harvest)→ 断言 `questions` 键存在、形状正确。

真网络验证由主循环手动跑 `python lib/keyword_scout.py "PU leather"` 一次(非 CI)。

## 文件清单

- 改:`lib/keyword_scout.py`(加 `harvest_questions` / `merge_questions` / `_norm` / `QUESTION_PREFIXES`;改 `cluster_plan` / `grounded_plan` / `write_record` / `main` 打印)。
- 新:`tests/test_question_layer.py`(7 组单测,mock 网络:5 组核心 + evidence 领头 / merge 不缩水 / seed 规范化 3 组审查加固)。
- ~~(stretch)新 `harvest_paa`~~ —— 本期 descope(实测 SERP 不可达,见 §5)。
