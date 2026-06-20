# 操作台设计 Token —— 实地抠自大厂控制台(2026-06-07)

> 用 patchright 登进 4 个真·大厂 AI 控制台,`getComputedStyle` 直接读出它们的真实 token。
> 下表「实测值」是抠出来的原始值;「我们采用」是**开源/零授权风险**的等价方案(遵守 MIT/Apache/BSD/OFL/ISC 红线)。

## 1. 字体(typography)

| 控制台 | UI 无衬线 | 等宽 | 衬线 | 中文 |
|---|---|---|---|---|
| Claude Console | `anthropicSans`(自家) | `anthropicMono`(自家) | **`anthropicSerif`**(editorial 标题/logo) | — |
| OpenAI Platform | `OpenAI Sans`(自家) | — | — | — |
| Coze(字节) | Lark 系统栈 | — | — | **Noto Sans SC** |
| Dify | `ui-sans-serif/system-ui`(系统) | — | — | 系统 |

**共性**:全是干净 neo-grotesque 无衬线;大厂自家字买不到,系统栈/Noto 可平替。Claude 的**衬线 editorial 标题**是可偷的差异化。

**我们采用(全 OFL,零风险)**:
- UI 无衬线:**Inter**(OFL) → 拉丁;**Noto Sans SC**(OFL) → 中文。栈:`"Inter","Noto Sans SC","Microsoft YaHei",system-ui,sans-serif`
- 等宽(数字/slug/代码):**JetBrains Mono**(OFL),开 `tnum`/`zero`。
- 衬线点缀(品牌 wordmark / hero,Claude 式 editorial):**Source Serif 4** 或 **Newsreader**(均 OFL);中文点缀可用 **霞鹜文楷**(已在豆包系统里)。

## 2. 配色(color)—— 两营,强调色全员撞车

### 实测原始值

| 角色 | Claude(暖中性) | OpenAI(纯中性) | Dify(Tailwind/UntitledUI) | Coze(Lark) |
|---|---|---|---|---|
| 画布 bg | `#F8F8F6` | `#F3F3F3` | 白 | 白 |
| 面板 | `#F4F4F1` / `#E6E5E0` | `#F9F9F9` / 白 | 白 | `#F7F7FC` / `#F0F0F5` |
| 墨(主文字) | `#121212` | `#282828` | `#101828` | `#1F2329` |
| 次级文字 | `#373734` / `#52514E` | `#5D5D5D` / `#414141` | `#354052` / `#676F83` | `rgba(15,21,40,.82)` |
| 弱文字 | `#7B7974` / `#898781` | `#8F8F8F` | `rgba(16,24,40,.5)` | `rgba(55,67,106,.38)` |
| 深色面 | `#0B0B0B` | `#181818` | `#101828` | `#1A1B1E` |
| **强调** | **periwinkle `#9B87F5`** | **闷蓝 `#004F99`** + 黑 | **蓝 `#155AEF`/`#444CE7`** | **indigo `#5147FF`** |
| 链接 | `#256BC1` | `#004F99` | `#1863DC` | `#5147FF` |
| 边框 | `rgba(31,31,30,.1~.15)` | `rgba(40,40,40,.1~.12)` | `rgba(16,24,40,.08~.14)` | `rgba(82,100,154,.13)` |

**两条铁律**:① **强调色 = 靛蓝/periwinkle**(无一例外,AI 产品标准色);② **主按钮 + 深色模式面 = 近黑**(#0B0B0B~#181818)。

### 我们采用(两选一,真渲染对比)

**P1 · 暖中性(Claude-grade · editorial)**
```
--bg:#F7F7F5; --panel:#FFFFFF; --panel2:#F4F3F0;
--ink:#1A1916; --ink2:#46443E; --faint:#827E76;
--line:#ECEAE4; --line2:#DFDCD4;
--acc:#6E72E8; --acc2:#4F53C9; --acc-wash:#EEEEFB;   /* periwinkle */
--ok:#2E8B6B; --warn:#A8791A;
--dark-bg:#0E0E0D; --dark-panel:#19180F;
```
**P2 · 冷中性(OpenAI/Dify-grade · 当前 mockup 用的就是这套)**
```
--bg:#F6F7F9; --panel:#FFFFFF; --panel2:#FBFBFC;
--ink:#14161A; --ink2:#52585F; --faint:#8A9099;
--line:#EBECEF; --line2:#E0E2E6;
--acc:#4E63E6; --acc2:#3C4FCB; --acc-wash:#EEF0FD;   /* indigo */
--ok:#1F9D6B; --warn:#B5820B;
--dark-bg:#0B0D10; --dark-panel:#15181D;
```
主按钮两套都用近黑(`--ink`)做最高层级 commit 动作,靛蓝留给选中/激活/链接。

## 3. 图标(icons)

| 控制台 | 图标方案 |
|---|---|
| Claude | 自家图标字 `Anthropicons`(20px 网格) |
| OpenAI | 自家 SVG 组件 |
| Coze | 自家图标集 `coz_*`(24px) |
| **Dify** | **Remix Icon**(开源 Apache-2.0) |

**我们采用**:**Lucide**(ISC ≈ MIT,零风险;shadcn 同款;仓库已有 `svg-kit-lucide.json`)。线性、24px 网格、stroke 1.75。统一替换 mockup 里手画的那批。备选 Remix Icon(Apache)。

## 4. 形状 / 深度

- 圆角:控件 6–8px、卡片 8–12px(Coze 8、Dify 偏小、Claude 偏软)。我们:控件 8–9px、卡片 12px ✓。
- 边框:**1px 低对比 alpha 边**(全员如此),非实色重边。
- 深度:柔影 + 1px 边,不纯平也不重投影(Linear/Stripe 同款)。

## 5. 数据可视化

- OpenAI 用 **Recharts**(MIT);折线/迷你条 + 时间范围 pill(24h/7d/30d/90d)。
- Claude:环形进度(credit/spend) + 柱状 token volume。
- 我们:KPI 卡(环形质检分 + 趋势 pill)已落;后续图表用 **Recharts / uPlot(MIT)** 或纯 SVG 自绘。

---
**落地默认(P1/P2 旧方案,已被下面的 Gemini 融合取代)**:Inter + Noto Sans SC + JetBrains Mono · Lucide 图标 · 靛蓝/periwinkle 强调 + 近黑主按钮。

---

# 6. ★ Gemini 融合方案(客户最终方向:与 Gemini 融为一体 + 生成模块 LLM 对话式)

> 实地登进 `gemini.google.com` 抠的真 token + 动画。原则:**视觉与 Gemini 融为一体,但用 Google 家的开源等价件(全 OFL/Apache),零授权风险,功能一个不丢。**

## 6.1 字体(Gemini 实测 → 我们开源替代)

| 角色 | Gemini 实测 | 我们采用(开源) |
|---|---|---|
| UI 无衬线 | `Google Sans` / `Google Sans Flex`(专有) | **Lexend**(Google 出品,**OFL**)——最接近 Google Sans 的圆润几何感 |
| 数字 / 代码 | `Google Sans Mono` / `Google Sans Code`(圆润友好) | **Roboto Mono**(Google,**OFL**)——替掉客户不喜欢的 JetBrains 硬技术感 |
| 中文 | — | **Noto Sans SC**(OFL) |
| 图标 | `Google Symbols`(Material Symbols) | **Material Symbols Rounded**(**Apache-2.0**)——Gemini 同款图标字,直接 Google Fonts 引 |

## 6.2 配色(Gemini 实测原始值)

```
--bg:#FDFCFC;            /* 近白·极微暖 */
--surface:#FFFFFF; --surface2:#F0F4F9;  /* 招牌浅蓝面 */ --surface3:#F8FAFD;
--ink:#1F1F1F; --ink2:#444746; --gray:#5F6368; --faint:#9AA0A6;
--line:#E3E3E0; --line2:#DADCE0;
--blue:#1A73E8;          /* 动作蓝 */ --blue-bright:#3C90FF; --blue-deep:#004A77; --blue-wash:#E8F0FE; --blue-surf:#C2E7FF;
--ok:#1E8E3E; --warn:#E37400;
/* 招牌 Gemini 渐变:蓝→紫→粉(完整 sweep 还有 红/橙/黄/绿) */
--gem:linear-gradient(90deg,#3C90FF,#AD72FF,#F96BD6);
```
**铁律**:动作=蓝(`#1A73E8`);AI/品牌时刻=蓝紫粉渐变;面=纯白/浅蓝;墨=`#1F1F1F`、灰=`#5F6368`。

## 6.3 形状 / 动效(Gemini 实测)

- **圆角**:输入框/按钮 = **全圆 `9999px` pill**;卡片 = 16–28px(Material 3 expressive,大圆角);头像/blob = 异形 morph。
- **缓动**:**`cubic-bezier(0.2, 0, 0, 1)`**(Material 标准,全站统一)· 时长 0.2–0.5s。
- **关键 @keyframes(实测,可原样复刻)**:
  - `animateGradient`:`0%{background-position:200% center}100%{0 center}` + 背景 `background-size:200%` + `--gem` → 流动渐变(sparkle/标题)。
  - `gem-shimmer-sweep`:`0%{bg-pos:100% 100%}70%,100%{0 0}` → 微光扫过("思考中"行)。
  - `morphBG/morphFG`:多帧 `border-radius` 异形变形(用 `--morph` 变量)→ 会"活"的蓝色光晕 blob。
  - `sweepBG`:`translate -200px→200px→-200px` → blob 漂移。
  - `temp-chat-entry`(opacity 0→1)/ `on-load-slide-in`(translateX -100%→0)→ 消息/侧栏入场。
- **首页光晕**=蓝色径向渐变 blob × `morphBG`(变形)× `sweepBG`(漂移),叠在 pill 输入框后。

## 6.4 生成模块 = LLM 对话式(功能映射,一个不丢)

把现有"表单 + 运行 + 双屏剧场"重构为**对话式 + Canvas**:
- **对话列(左)**:Gemini pill 输入("跟 agent 说要做的站 / 粘种子词 / 让它改某页")。`+` 附加 = **行业配置 / 现场种子词 / 目标(WP·预览)**(原表单项变成附加项)。模型选择器 = `deepseek-v4-flash ▾`。
- agent 回复里**内嵌富卡**:`✦ 接地抓到 210 词`→**关键词库**(原 03 模块)、`规划 5 簇 / 18 页`、`逐页生成 + 确定性质检`(原质检)。"思考中"用 shimmer。
- **Canvas(右)**= 原**双屏剧场**:右屏成品页 = Canvas 主体;左屏数据(关键词落位 + 规则打分)= Canvas 可收起的「给搜索引擎·数据」抽屉。页签 = 已生成各页。顶部 **发布到 WordPress** 动作保留。
- **"+1" 自然语言改页** = 直接在对话里说"把第 3 页的标题换成…",改的就是 Canvas 当前页。

→ 实现:Lexend + Noto Sans SC + Roboto Mono + Material Symbols Rounded · Gemini 蓝 + 蓝紫粉渐变 · 全圆 pill + 大圆角卡 · Material 缓动 + 上述 keyframes。功能 100% 保留,只换交互范式与皮肤。
