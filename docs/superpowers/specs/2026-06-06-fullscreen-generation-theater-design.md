# 全屏生成现场 · 设计 spec

日期:2026-06-06
状态:设计已确认(待用户审阅 → 转实现计划)
范围:`templates/index.html` 前端为主 + 一处后端**透传**(把现成的 `quality.breakdown` 透出来给完成下钻的关键词落位明细用,非管线改动)

## 1. 问题 / 动机

现在操作台(`templates/index.html`)点「看着生成 / 运行管线」后,双屏剧场(左=给搜索引擎·数据,
右=给人·生成展示)是**嵌在操作台页面里的一小块**,不够大、不够沉浸。客户要的是 Gemini Canvas /
Manus 那种「进入生成模式」——点开始后整窗被双屏占满,沉浸地看页面被生成。

## 2. 已拍板的决策

- **接管范围 = 全屏接管**:点开始 → 整个浏览器窗口被双屏现场占满,操作台/抬头/表单被盖住(不删)。
- **布局 = C · 数据栏可收起**:左=给搜索引擎(数据),右=给人(生成展示);默认展开**偏右 40/60**
  (右屏就是舞台主角),中缝有 `‹` 收起钮,点了左栏缩成竖条、右屏全幅;再点 `›` 展开。
- **完成行为 = 留在现场可下钻**:跑完留在全屏现场,可逐页下钻看成品 + 该页关键词落位/得分;
  `✕` 才退回操作台。
- **实现路子 = 方案 1 · 原页全屏覆盖层**:现有 `.theater` 升格为 `position:fixed; inset:0` 的现场态,
  **复用全部现有 SSE / 解析 / 逐字 / 预热 wiring**;后端**仅一处透传**(`quality.breakdown` 给下钻明细),
  无管线、无路由改动。

## 3. 设计细节

### 3.1 进入 / 退场
- 触发:`#form` submit(运行管线)与 `#demoBtn`(看着生成)两个入口,在 `beginStream()` 里给
  `.theater` 加 `.fs` 类,并给 `<body>` 加 `overflow:hidden` 锁背景滚动。
- 视觉:`.theater.fs { position:fixed; inset:0; z-index:1000; }`;进入用 ~250ms 展开过渡
  (transform/clip 从触发按钮附近撑开到全屏),不突兀。
- 退场:顶条 `✕` 或 `Esc` → 移除 `.fs` + 解锁 body 滚动 → 回操作台。**操作台 DOM 与表单选择不丢**。
- 取消:生成中(`status==运行中/渲染中`)点 `✕`/`Esc` 先二次确认「正在生成,确定退出?」→ 确认则
  `es.close()` 关流 + 退场。

### 3.2 顶部状态条(全宽)
`SE 印章 · 生成现场 · [LIVE] · [进度条 #progFill] · #progNum · 计时 #elapsed · [✕]`。
复用现有 `#dot / #status / #progFill / #progNum / #elapsed`,只是重新摆位到全屏顶条。
完成态顶条把 `生成现场 · LIVE` 换成 `✓ 完成 · N 页 · 通过 P/N`(由 done summary 填,真实数字)。

### 3.3 左栏「给搜索引擎」+ 收起
- 默认展开:`.split` 在 `.fs` 下用 `grid-template-columns: 0.66fr 18px 1fr`(≈40/60,右为主)。
- 内容:行式打印机日志 `#log` + 页面账本 `#ledger`(沿用现有元素)。
- 收起:中缝 `.gutter` 顶部加 `‹` 钮(`#railToggle`)。点击 → `.split` 加 `.rail-collapsed`:
  左栏 `.scr-data` 收成 ~30px 竖条(只剩竖排「给搜索引擎」+ `›` 展开钮 + `i/N`),
  `grid-template-columns: 30px 1fr`。过渡 200ms。再点 `›` 移除 `.rail-collapsed` 还原。
- 键盘 `[` 可选地切换收起/展开。

### 3.4 右舞台「给人 · 生成展示」
**零逻辑改动**,原样复用:预热靶心(`#pressWarm`)→ 逐字写作(`#writer`)→ 成品页(`#proof/#prevFrame`)。
全屏下容器变大:`fitProof()` 的缩放基准改为读 `.press` 实际宽高重算(现已按 `press.clientWidth` 算,
天然适配);成品页看得更清。底部页面标签条 `#pageTabs` 保留。

### 3.5 完成态 + 下钻
- done 事件:顶条转 `✓ 完成 · N 页 · 通过 P/N`,`#progFill` 满。
- 下钻:点 `#pageTabs` 任一页 → 右屏 `#prevFrame` 切那页成品(已有 `activateTab`);**新增**:同时
  - 左栏对应 `#ledger` 行高亮(`.lr.sel`);
  - 行下方展开一小块「关键词落位」明细面板:标题/H2/meta/正文 命中处 + `keyword_usage` 维度分 +
    确定性总分。
- 数据来源:`quality.score_page` 返回的 `breakdown`(现成的确定性打分明细)。需把它透传到前端:
  - 真 `/run`:`app.py` 的 `_slim_results` 当前丢了 `quality`,扩它带上 `breakdown`。
  - demo:`render_samples.render_all` 现在的 `results` 只有 `{slug,score,passed,origin}`,丢了
    `breakdown`;扩它(及 `/demo_stream` 的 done summary)带上 `breakdown`。
  以上均为**透传已有数据**,不动打分 / 渲染逻辑。**诚实红线:只展示真实命中与真实扣分,绝不编。**

### 3.6 数据流 / 复用(前端为主 + 一处透传)
`interpret()`、`materialize()`、`revealPage()`、`finalizeStage()`、预热 `showWarm/hideWarm`、
SSE 端点本身——**逻辑全不动**。本次改动:
1. CSS:新增 `.theater.fs`、`.split`(fs 下的栅格)、`.rail-collapsed`、顶条、竖条等态。
2. DOM:在 `.theater` 内补一个全屏顶条容器 + 左栏竖条 + 中缝 `‹/›` 钮 + 完成下钻明细面板。
3. JS:`beginStream` 进 fs;`✕/Esc` 退场(含生成中确认);`#railToggle` 开合;`activateTab` 扩展
   联动左栏高亮 + 落位明细。
4. 后端透传(唯一后端改动):`_slim_results`、`render_samples.render_all`、`/demo_stream` done
   summary 各带上现成的 `breakdown`,供下钻明细用。

### 3.7 错误 / 边界
- 无 key 真 `/run`:现场照常进入,左栏 `#log` 打出干净的 authentication 错误行,顶条 `#dot` 转
  「出错」红点,右舞台停在预热之后给一行「未生成页面(缺 key)」占位(非假页面)。可 `✕` 退。
- 连接中断(`es.onerror`):顶条转「连接中断」,可退场。
- 移动端(`max-width:860px`):全屏现场内左右改**上下**——上=数据(可上滑收成顶条)、下=生成展示;
  中缝「权重」转横条。沿用现有 860px 断点思路。

### 3.8 视觉语言
全程拼版台:暖纸 `#F2EEE3` + 朱红 `#E2402A` + 近黑墨;套准角标在现场四角;得意黑 SVG 标签
(给搜索引擎/给人/权重,来自 `/assets/svg.json`);零 webfont;chrome 零 emoji(印刷符号 ▸ ‹ › ✕ ✓)。

## 4. 不在本次范围

- Tier B 真 token 流式仍需 key(已建好接线,本次不碰)。
- 关键词 agent 增强、Trends、DeepSeek provider。
- 真实 WordPress 连接。

## 5. 验收 / 测试(自验,浏览器实测)

1. 点「看着生成」→ 进入全屏现场(过渡顺)、左右 40/60、demo 全程逐字 + 完成。
2. `‹` 收起 → 左栏成竖条、右屏全幅;`›` 展开还原。
3. 完成后点页面标签 → 右屏切页 + 左栏行高亮 + 落位明细弹出,数字与 `quality.breakdown` 一致。
4. `✕` / `Esc` 退场 → 回操作台,表单选择仍在;生成中退场有二次确认。
5. 无 key 真 `/run` → 现场进入、打干净错误、可退,不崩。
6. 移动端(≤860px)→ 上下堆叠、可收起。
7. 0 console 报错。

## 6. 关联

- 现有实现:`templates/index.html`(双屏剧场 + 逐字 + 预热)、`app.py`(`/run` `/demo_stream`
  `/assets/svg.json`)、`render_samples.py`、`lib/quality.py`(breakdown)。
- 记忆:[[project-transparency-saas]]。
