# 基础版 · 晨间 STATUS 报告

> 给早上醒来的老板。今晚把「跑管线的工具」升级成了「有登录、有项目概念的可演示/可交付产品壳」,并做完了整套烟雾测试(如实记录,见文末测试摘要)。
> 范围严格只做 `docs/feature-tiers-v2.md`「基础版 ¥8k」那一档,没有顺手做完整版/护城河版的东西。
> 日期:2026-06-07(凌晨)。分支:`feat/basic-version`(未 push)。

---

## 一、今晚建了什么(一句话)

在原有 CLI 管线 + Flask 操作台之上,新增了**轻量数据层 + 极简登录 + 项目管理 + 关键词库/用量统计**,
让客户能「登录 → 建自己的项目 → 在项目里生成 SEO 网页 → 输出按项目隔离、跑完留记录」。
原有的 CLI 三种跑法、`/run` SSE 双屏剧场、`/demo` 零 key 重放**全部未破坏**,质检锁定文件 `lib/quality.py` **一行未改**。

新增/改动的核心文件:
- `models.py` —— 轻量数据层(`sqlite3` 标准库,零 ORM)。users / projects / generations / keywords 四张表,自动建表,参数化 SQL 防注入。
- `auth.py` —— 极简登录(邮箱 + 密码)。密码走 PBKDF2-HMAC-SHA256 + 随机 salt(绝不存明文),Flask session 登录态,`login_required` 装饰器。
- `app.py` —— 从「跑管线工具」接上登录与项目:`/`(操作台,需登录)、`/login` `/register` `/logout`、`/projects`(列表+新建)、`/projects/<id>`、`/run`(项目上下文里跑、输出隔离、跑完记账)、`/api/keywords`(项目关键词库)。`/demo` `/demo_stream` 保持公开。
- `templates/login.html`、`templates/projects.html` —— 登录卡片、项目列表+新建(豆包风)。
- `templates/index.html` —— 操作台加了账户/项目条、用量计量(免费版 100k token/月)、关键词库 tab。

---

## 二、基础版每个功能的状态

> 图例:✅ 可用 · 🟡 部分/有限制 · 🔴 未做

| 功能 | 状态 | 说明 |
|---|---|---|
| 登录系统 | ✅ | 邮箱+密码,PBKDF2 哈希,session 登录态,未登录拦截 + `?next=` 回跳。烟雾测试全过。 |
| 项目管理 | ✅ | 建项目(选行业配置或填种子词)、列表、进操作台。按 `user_id` 隔离,越权访问他人项目 → 404。 |
| AI 关键词生成 | ✅ | 走「接地真抓词」:抓 Google/Bing 真实搜索补全、按买家意图确定性聚簇(零 LLM、有出处)。实测 `PU leather` 抓到 210 个真实词 → 聚成 5 页计划。 |
| 关键词管理 | ✅ | 接地抓到的词入库(词 + 意图 + 覆盖页数 + 来源),操作台「关键词库」tab 展示;`/api/keywords` 受保护、越权 404。 |
| SEO 文章/FAQ/产品页/分类页生成 | ✅ | DeepSeek v4-pro 写正文,支持 pillar/comparison/application/faq/product/guide 多页型。CLI dry-run 实测产出真实 40KB 页面。 |
| Meta Title / Description | ✅ | 页面 schema 强制产出 `title` + `meta_description`,质检对其评分。 |
| CTA 生成 | ✅ | 由 writer 在正文/模板内产出(制造商语气)。 |
| 行业模板(套用) | ✅ | `industries/*.yaml`,`pu-leather.yaml` 是高质 8 页范例;建项目时下拉可选。 |
| 内容审核流(基础) | ✅ | 每页过 `lib/quality.score_page` 确定性质检,低于阈值(70)标记/跳过;实测命中后触发定向润色。 |
| AI 自检/润色(基础) | ✅ | 质检导向润色环:78→84 分定向修复(deepseek-v4-flash),keep-better 诚实复评。 |
| 结构化数据(基础 schema) | ✅ | `lib/schema` 产 JSON-LD(Organization / Article 等)。 |
| 内链(简单推荐) | ✅ | writer 产出页内 `<a href>` 互链;质检会提示缺 pillar/sibling 链接。 |
| Token 统计 | ✅ | 每次跑读本次 `total_tokens`,写进 `generations.tokens_used` + 累加 `projects.token_used`;操作台显示「本次消耗 / 累计 / 剩余」。免费版上限 100k/月,超额开跑前友好拦截(`TokenLimitError`)。 |
| 自动配图(基础) | 🟡 | 代码已接 `lib/images`(Pexels),但 **PEXELS key 未配** → 返回 None、页面不带配图(不影响生成与质检)。配 key 即生效。 |
| 失败重试 | 🟡 | LLM 调用层有瞬时错误(限流/超载/抖动)自动重试(`lib/retry` + `_is_transient_llm_error`)。**发布到 WP 的失败重试今晚未端到端联调**(因今晚不真发布)。 |
| 发布日志(简单) | 🟡 | 每次跑落一条 `generations` 记录(状态/页数/通过数/token/结果 JSON),`models.list_generations` 可读。**操作台暂未做「日志列表」专门页面**,数据已经在库里,补个只读页即可。 |
| WordPress 单站点绑定 | 🟡 | 发布代码 `lib/wp_publish` 在,`WP_*` 已配;**但今晚遵铁律没真发布**(对外不可逆),只验证了 dry-run/本地预览。项目层面「绑定站点」目前是全局 `WP_*` 环境变量,未做「每项目独立站点」录入 UI。 |
| 自动发布 WordPress | 🟡 | 同上 —— 代码路径在(`/run?mode=publish` → `generate_site(dry_run=False)`),**待老板做一次真发布联调**才能标 ✅。 |

> 没有任何「完整版/护城河版」功能被顺手做掉:竞品拆解、去重 unique 引擎、多租户、计费仪表盘、技能市场、agent 编排 —— 一律未碰。

---

## 三、怎么本地跑起来

```
# 1. 装依赖(若还没装)
pip install -r requirements.txt

# 2. 启动产品壳
python app.py
#   → 监听 http://127.0.0.1:5000

# 3. 浏览器打开 http://127.0.0.1:5000
#   未登录会跳到 /login
#   点「注册」建一个账号(邮箱+密码)→ 自动登录
#   进「我的项目」(/projects)→ 新建项目:
#       · 选行业配置(如 pu-leather.yaml,稳妥好看的预设)
#       · 或填一个种子关键词(如 "pu leather wholesale",现场真抓词聚簇)
#   → 自动进操作台(带项目上下文)
#   点「生成 · 预览(不发布)」→ 看双屏实时剧场:
#       左屏:站点结构/账本逐行落位;右屏:正文逐字 materialize
#   跑完:质检得分 + 关键词落位明细 + 「关键词库」tab + 本次/剩余 token

# 想给同行/客户当场看效果(零 key、不花钱):
#   直接访问 /demo 或操作台的「离线样板演示」—— 用已存的真实内容重放,不调模型
```

CLI 仍可用(三种跑法都在):
```
python run.py industries/pu-leather.yaml --dry-run     # 本地预览,不发布(今晚验证用这个)
python run.py                                          # 默认 pu-leather.yaml,发布到 WordPress
python run.py industries/your-config.yaml              # 用别的行业 config 发布
```

数据库:`data/app.db`(sqlite,首次运行自动建表)。Flask 密钥:`data/secret_key`(首次自动生成)。
两者都在 `.gitignore`,**绝不入库**。`.env`(含 DEEPSEEK / WP 机密)也在 `.gitignore`,从未读取/打印/提交。

---

## 四、还需老板做的

1. **真发布到 WordPress 的联调(最关键)**:今晚遵守「对外不可逆操作今晚不做」的铁律,只跑了 dry-run。
   需要老板挑一个安全时间,用 `python run.py industries/pu-leather.yaml`(或操作台 `/run?mode=publish`)做一次真发布,
   确认 WP REST/SSH 隧道发布、配图、内链、SEO 描述在真站点上都对。这是把上面三个 🟡(WP 绑定/自动发布/发布失败重试)转 ✅ 的唯一缺口。
2. **(可选)配 PEXELS_API_KEY**:配上自动配图就生效;不配也能交付(页面不带图)。
3. **(可选,待定决策)发布日志页面**:数据已在 `generations` 表里,要不要在操作台加个「发布历史」只读列表页?基础版「发布日志(简单)」严格说差这一个 UI。
4. **(待定决策)每项目独立 WP 站点**:目前发布用全局 `WP_*`。若客户要在一个账号下管多个站点,需把站点凭据下放到项目级(基础版是「单站点绑定」,当前够用,看客户是否要多站)。

---

## 五、已知问题与坑

- **WP 真发布今晚零验证**:上面三个 WP 相关 🟡 全部因为「今晚不真发布」而无法端到端确认。代码路径在,但没在真站点上跑过 = 别当成已验证。
- **用量额度是软统计**:`projects.token_limit` 默认 100k,超了开跑前拦截;但这是按项目累计的简单计数,不是严格计费,也不防同一用户多项目绕过。基础版够用,转售档才需要真计费。
- **登录极简、无「记住我」**:`session.permanent=False`,关浏览器即掉登录态;无邮箱验证、无找回密码、无频率限制。客户明确要求「普通 CRUD 别搞高级」,这是有意为之,不是漏做。
- **接地抓词依赖外网可达**:`grounded_plan` 抓 Google/Bing 自动补全,有 `recon/.cache/` 缓存兜底;外网不可达且无缓存时会抓到空池。今晚实测可达(210 词)。
- **种子词模式临时落盘 yaml**:`/run` 的 seed 模式会在 `industries/` 下临时写一个 `seed_*.yaml`,跑完删除。正常路径没问题,但若进程被强杀可能残留一个临时文件(无害,可手删)。
- **生成耗时/费用**:8 页全量跑约几万 token(实测单页 ~12k token)。给客户演示建议用 `/demo` 零 key 重放,或先跑 1-2 页,别每次全量烧钱。

---

## 六、今晚测试摘要(如实记录)

1. **现有测试套件**:`python -m pytest tests/` → **20 passed**(质检/关键词落位/LLM provider/润色环/问题层)。
2. **CLI dry-run**(铁律③):`python run.py industries/<1页临时config> --dry-run` → **exit 0**。
   全链路:配置 → 预设规划 → DeepSeek v4-pro 写正文 → 质检 78 分 → 定向润色 78→84 → 质检 PASS 84/100 → 写本地预览 HTML(40KB)+ index(已落盘确认)。临时 config 跑完已删除。
3. **产品壳**(Flask test client,隔离临时 DB,不污染开发库):**15/15 通过**。覆盖:
   未登录 `/` 被拦(302→/login)、未登录 `/projects` 被拦、`/demo` 公开 200、注册自动登录、登出后再次被拦、
   重新登录、**错误密码被拒**、建项目跳操作台、**越权访问他人项目→404**、**越权读他人预览输出→404**、`/configs` 列出配置、**越权读他人关键词库→404**。
4. **闭环**(grounded 抓词 → LLM → 网页):
   - grounded 抓词:`keyword_scout.grounded_plan('PU leather')` → **210 个真实补全词、11 次查询、聚成 5 页计划**(零 key、有出处)。
   - LLM → 网页:CLI dry-run 已证明(见 2)。
   - 产品里可触发:`app.py /run` 通过 `on_keywords` 回调把接地词写进 `keywords` 表 →「关键词库」tab;无预设页时默认走接地规划。
   - 另有 Phase-1 已存证据:`output_src/*.json`(8 页真实生成正文)+ `design_round/transparency/keyword_record.json`(抓词出处留痕)。

**结论**:基础版作为「可演示、可交付的产品」整体跑通。唯一未端到端验证的是 **WordPress 真发布**(今晚遵铁律刻意不做),需老板做一次联调把那几个 🟡 收口。
