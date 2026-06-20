# 全屏生成现场 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 点「看着生成 / 运行管线」后,整窗变成沉浸式全屏双屏生成现场(左=给搜索引擎/数据,右=给人/生成展示),布局可收起、完成后留在现场逐页下钻看成品 + 关键词落位明细。

**Architecture:** 方案 1「原页全屏覆盖层」——现有 `templates/index.html` 的 `.theater` 升格为 `position:fixed; inset:0` 的现场态,**复用全部现有 SSE / `interpret` / `materialize` / 预热 wiring**。后端只做透传:把现成的 `quality.breakdown` 经 `app.py` 透出来,并由一个单测过的纯函数 `_keyword_landing()` 从 `keyword_usage.notes` **派生**关键词落位(不碰锁定的 `lib/quality.py`)。

**Tech Stack:** Flask(`app.py`)+ 原生 HTML/CSS/JS(`templates/index.html`,零框架、零 webfont)+ patchright-stealth 浏览器实测 + Python 直跑校验。

参照 spec:`docs/superpowers/specs/2026-06-06-fullscreen-generation-theater-design.md`

---

## 文件结构

- **`render_samples.py`**(改):`render_all` 的 `results` 每项带上 `breakdown` 与 `target_keyword`(透传现成数据)。
- **`app.py`**(改):新增纯函数 `_keyword_landing(kw_bd)`;`_slim_results` 与 `/demo_stream` done summary 的每页带上 `breakdown` / `landing` / `target_keyword`。
- **`templates/index.html`**(改):CSS 加全屏壳 `.theater.fs` / 顶条 / `.rail-collapsed` / 竖条 / 下钻明细;DOM 加顶条 stamp+✕、左栏竖条、中缝 `‹` 钮、`#kwPanel`;JS 加 `enterFs/exitFs/toggleRail/renderLanding`,扩展 `activateTab` 与 `finalizeStage`。
- **`run.py`**(改 1 行):`generate_site` 的结果 dict 带上 `target_keyword`(供 `/run` 下钻显示目标词)。

约定的数据形状(贯穿全计划,务必一致):
- `_keyword_landing(kw_bd)` → `{"present": bool, "title": bool, "meta": bool, "heading_intro": bool, "body_count": int}`
- 透传后每页 summary item 含:`title, type, slug, score, passed, link, warnings, breakdown, landing, target_keyword`
- 前端 `stage.rows[slug]` 新增:`row.breakdown`、`row.landing`、`row.kw`

---

## Task 1: 后端透传 breakdown + target_keyword(render_samples)

**Files:**
- Modify: `render_samples.py`(`render_all` 内 `results.append(...)`,约 219-220 行)

- [ ] **Step 1: 改 render_all 的 results,带上 breakdown 与 target_keyword**

把 `render_samples.py` 中这段:

```python
        _emit(f" {'✅' if q['passed'] else '⛔'} [{origin}] {q['score']:>5}/100  {p['slug']}.html")
        results.append({"slug": p["slug"], "score": q["score"],
                        "passed": q["passed"], "origin": origin})
```

改为:

```python
        _emit(f" {'✅' if q['passed'] else '⛔'} [{origin}] {q['score']:>5}/100  {p['slug']}.html")
        results.append({"slug": p["slug"], "score": q["score"],
                        "passed": q["passed"], "origin": origin,
                        "breakdown": q.get("breakdown", {}),
                        "target_keyword": p.get("target_keyword", "")})
```

- [ ] **Step 2: 跑校验,确认 results 带上了真实 breakdown**

Run:
```bash
python -X utf8 -c "import render_samples as R; s=R.render_all(); r=s['results'][0]; print('keys:', sorted(r)); ku=r['breakdown']['keyword_usage']; print('keyword_usage:', ku); print('target_keyword:', r['target_keyword'])"
```
Expected: `keys` 含 `breakdown`、`target_keyword`;`keyword_usage` 形如 `{'score': 15.0, 'max': 15.0, 'notes': 'body count=...'}`;`target_keyword` 非空。

- [ ] **Step 3: Commit**

```bash
git add render_samples.py
git commit -m "feat(quality-透传): render_all 结果带上 breakdown 与 target_keyword"
```

---

## Task 2: 关键词落位派生函数 `_keyword_landing`(app.py,单测)

`lib/quality.py` 是锁定的镜像模块,不改。它的 `keyword_usage.notes` 用固定文案编码命中:
缺标题→`"not in title"`、缺 meta→`"not in meta"`、缺 H2/前150→`"not in heading/intro"`、始终含 `"body count=N"`;
`target_keyword` 为空时 notes 退化为 `"ok"`。据此**派生**每处是否命中(命中 = 对应 miss 文案不在 notes 里)。

**Files:**
- Modify: `app.py`(在「辅助函数」区,`_slim_results` 之前加 `_keyword_landing`)
- Test: `tests/test_keyword_landing.py`(新建)

- [ ] **Step 1: 写失败测试**

Create `tests/test_keyword_landing.py`:

```python
# -*- coding: utf-8 -*-
import importlib
import app  # noqa


def test_all_hit():
    bd = {"score": 15.0, "max": 15.0, "notes": "body count=3"}
    r = app._keyword_landing(bd)
    assert r == {"present": True, "title": True, "meta": True,
                 "heading_intro": True, "body_count": 3}


def test_title_and_meta_miss():
    bd = {"score": 4.0, "max": 15.0, "notes": "not in title; not in meta; body count=2"}
    r = app._keyword_landing(bd)
    assert r["present"] and r["title"] is False and r["meta"] is False
    assert r["heading_intro"] is True and r["body_count"] == 2


def test_no_keyword():
    bd = {"score": 0.0, "max": 15.0, "notes": "ok"}
    r = app._keyword_landing(bd)
    assert r["present"] is False


def test_against_real_quality():
    # 用真实 quality.score_page 的输出反向校验派生与真实命中一致
    from lib import quality
    page = {"target_keyword": "pu leather", "type": "guide", "url": "u", "pillar_url": None, "related": []}
    content = {"title": "PU Leather Guide", "meta_description": "pu leather facts " * 8,
               "html": "<h1>PU Leather</h1><h2>What is pu leather?</h2><p>pu leather " + ("x " * 200) + "</p>"}
    bd = quality.score_page(page, content, {})["breakdown"]["keyword_usage"]
    r = app._keyword_landing(bd)
    assert r["present"] is True and r["title"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_keyword_landing.py -q`
Expected: FAIL —— `AttributeError: module 'app' has no attribute '_keyword_landing'`

- [ ] **Step 3: 在 app.py 实现 `_keyword_landing`**

在 `app.py` 的 `# 辅助函数` 区、`def _resolve_config_path` 之前加:

```python
import re as _re


def _keyword_landing(kw_breakdown):
    """从 quality 的 keyword_usage breakdown 派生关键词「落位」(命中在哪几处)。

    quality.py 锁定不改;它的 notes 用固定文案编码缺失:
      缺标题→'not in title' / 缺 meta→'not in meta' / 缺 H2 或前150词→'not in heading/intro';
      并始终含 'body count=N';target_keyword 为空时 notes='ok'。
    命中 = 对应缺失文案不在 notes 里。纯函数、可单测、不调模型。
    """
    notes = str((kw_breakdown or {}).get("notes", "") or "")
    m = _re.search(r"body count=(\d+)", notes)
    present = m is not None  # 有 body count 才说明这页有 target_keyword 在打分
    return {
        "present": present,
        "title": present and ("not in title" not in notes),
        "meta": present and ("not in meta" not in notes),
        "heading_intro": present and ("not in heading/intro" not in notes),
        "body_count": int(m.group(1)) if m else 0,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_keyword_landing.py -q`
Expected: PASS(4 passed)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_keyword_landing.py
git commit -m "feat(下钻): _keyword_landing 从 quality.notes 派生关键词落位(单测)"
```

---

## Task 3: 透传 breakdown / landing / target_keyword 到 /run 与 /demo_stream

**Files:**
- Modify: `run.py`(`generate_site` 两处 `results.append`,约 279-284 与 296-301 行,各加 `target_keyword`)
- Modify: `app.py`(`_slim_results` 带 breakdown/landing/target_keyword;`/demo_stream` done summary 同样)

- [ ] **Step 1: run.py 两处结果 dict 各加 target_keyword**

低质分支(约 279 行)`results.append({...})` 内、`"warnings": warnings,` 之后加一行:
```python
                "target_keyword": page.get("target_keyword", ""),
```
通过分支(约 296 行起)`results.append({...})` 内同样加:
```python
                "target_keyword": page.get("target_keyword", ""),
```

- [ ] **Step 2: app.py `_slim_results` 带上 breakdown / landing / target_keyword**

把 `_slim_results` 里的 `slim.append({...})` 改为(在原有字段后追加三项):

```python
        q = r.get("quality") or {}
        bd = q.get("breakdown") or {}
        slim.append({
            "title": r.get("title", ""),
            "type": r.get("type", ""),
            "slug": r.get("slug", ""),
            "score": q.get("score"),
            "passed": q.get("passed"),
            "published": bool(r.get("published")),
            "skipped": bool(r.get("skipped")),
            "link": r.get("link"),
            "warnings": r.get("warnings") or [],
            "breakdown": bd,
            "landing": _keyword_landing(bd.get("keyword_usage") or {}),
            "target_keyword": r.get("target_keyword", ""),
        })
```

- [ ] **Step 3: app.py `/demo_stream` done summary 每页带 breakdown / landing / target_keyword**

把 `/demo_stream` 里构造 `out` 的循环改为:

```python
        out = []
        for p in pages:
            r = rmap[p["slug"]]
            bd = r.get("breakdown") or {}
            out.append({
                "title": p.get("title", p["slug"]), "type": p.get("type", ""),
                "slug": p["slug"], "score": r["score"], "passed": r["passed"],
                "published": False, "skipped": not r["passed"],
                "link": f"./{p['slug']}.html", "warnings": [],
                "breakdown": bd,
                "landing": _keyword_landing(bd.get("keyword_usage") or {}),
                "target_keyword": r.get("target_keyword", ""),
            })
```

- [ ] **Step 4: 校验 /demo_stream 的 done summary 带上了 landing**

先重启服务(改了 app.py):
```bash
python app.py
```
另开一条命令校验(零 key、demo 路径):
```bash
python -X utf8 -c "import requests,json; lines=[l for l in requests.get('http://127.0.0.1:5000/demo_stream',stream=True,timeout=60).iter_lines(decode_unicode=True)]; ev=[l for l in lines if l.startswith('data: {') and 'results' in l][-1][6:]; d=json.loads(ev); r=d['results'][0]; print('keys:',sorted(r)); print('landing:',r['landing']); print('target_keyword:',r['target_keyword'])"
```
Expected: `keys` 含 `breakdown`/`landing`/`target_keyword`;`landing` 形如 `{'present': True, 'title': True, ...,'body_count': N}`。

- [ ] **Step 5: Commit**

```bash
git add run.py app.py
git commit -m "feat(下钻): /run 与 /demo_stream 透传 breakdown/landing/target_keyword"
```

---

## Task 4: 全屏壳 —— 进入 / 退出(.theater.fs + 顶条 + ✕/Esc)

**Files:**
- Modify: `templates/index.html`(CSS `<style>`;`.stage-bar` DOM 加 stamp+✕;JS `beginStream`/退场)

- [ ] **Step 1: CSS —— 全屏壳 + 顶条**

在 `<style>` 里 `.theater{...}` 之后加:

```css
  /* ===== 全屏生成现场 ===== */
  body.gen-lock{overflow:hidden}
  .theater.fs{position:fixed; inset:0; z-index:1000; margin:0; border:0; display:flex; flex-direction:column;
    animation:fsIn .25s ease-out}
  @keyframes fsIn{from{opacity:.4; transform:scale(.985)}to{opacity:1; transform:none}}
  .theater.fs .split{flex:1; min-height:0}
  .theater.fs .scr{min-height:0}
  /* 顶条:复用 .stage-bar,全屏下两端加 stamp / ✕ */
  .fs-stamp{flex:none; width:24px; height:24px; background:var(--red); color:#fff; display:none;
    place-items:center; font-family:var(--mono); font-weight:600; font-size:10px; box-shadow:2px 2px 0 var(--ink)}
  .theater.fs .fs-stamp{display:grid}
  .fs-close{flex:none; display:none; width:26px; height:26px; border:1px solid var(--ink); background:var(--paper);
    color:var(--ink); cursor:pointer; font-family:var(--mono); font-size:13px; line-height:1; align-items:center; justify-content:center}
  .theater.fs .fs-close{display:inline-flex}
  .fs-close:hover{background:var(--red); color:#fff; border-color:var(--red)}
  .theater.fs .stage-bar{padding:9px 14px}
```

- [ ] **Step 2: DOM —— 给 `.stage-bar` 两端加 stamp 与 ✕**

把现有 `.stage-bar`(`<div class="stage-bar">…</div>`)改成首尾各加一个元素:开头加 stamp,结尾加 ✕。即:

```html
      <div class="stage-bar">
        <span class="fs-stamp">SE</span>
        <span class="live"><span id="dot" class="dot"></span><span id="status">就绪</span></span>
        <span class="prog-wrap">
          <span class="progress"><span class="pfill" id="progFill"></span></span>
          <span class="prog-num" id="progNum">0 / 0</span>
        </span>
        <span class="elapsed" id="elapsed"></span>
        <button class="fs-close" id="fsClose" type="button" title="退出（Esc）">✕</button>
      </div>
```

- [ ] **Step 3: JS —— 进入/退出全屏 + ✕/Esc(生成中确认)**

在 IIFE 内、`startTheater()` 定义之后加:

```javascript
  function enterFs() { theater.classList.add("fs"); document.body.classList.add("gen-lock"); }
  function exitFs() {
    const running = dot.className.indexOf("live") !== -1;
    if (running && !confirm("正在生成，确定退出？将中断本次生成。")) return;
    if (es) { es.close(); es = null; }
    clearInterval(timer); hideWarm();
    theater.classList.remove("fs", "show"); document.body.classList.remove("gen-lock");
    runBtn.disabled = false; document.getElementById("demoBtn").disabled = false;
  }
  document.getElementById("fsClose").addEventListener("click", exitFs);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && theater.classList.contains("fs")) exitFs();
  });
```

在 `beginStream(url, statusText)` 里,`startTheater();` 之后加一行:
```javascript
    enterFs();
```

- [ ] **Step 4: 浏览器实测 —— 进入即全屏、✕/Esc 退场**

重启 `python app.py`。用浏览器(patchright)`http://127.0.0.1:5000`:
- evaluate 点 `#demoBtn` → 断言 `theater.classList.contains('fs')===true` 且 `getComputedStyle(theater).position==='fixed'`,截图确认铺满整窗。
- evaluate 调 `document.getElementById('fsClose').click()`(完成态无确认)→ 断言 `theater` 不含 `fs`/`show`、`body` 不含 `gen-lock`、操作台可见。
Expected: 进入全屏 ✓、退场回操作台 ✓、0 console 报错。

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat(全屏): 生成进入 position:fixed 全屏现场 + 顶条 stamp/✕ + Esc 退场"
```

---

## Task 5: 全屏双屏栅格 40/60(右为主)

**Files:**
- Modify: `templates/index.html`(CSS `.theater.fs .split`)

- [ ] **Step 1: CSS —— fs 下双屏 40/60**

在全屏壳 CSS 后加:

```css
  .theater.fs .split{grid-template-columns:minmax(0,0.66fr) 20px minmax(0,1fr)}
  .theater.fs .scr-data{font-size:14px}
  .theater.fs #log{height:auto; min-height:120px; max-height:30vh}
  .theater.fs .ledger{flex:1}
```

(说明:现有 `.split` 默认 `1fr 38px 1.08fr`;`.fs` 下收紧中缝到 20px、左 0.66 右 1 ≈ 40/60。)

- [ ] **Step 2: 浏览器实测 —— 比例与高度**

evaluate(在全屏生成态下):读 `getComputedStyle(document.querySelector('.theater.fs .split')).gridTemplateColumns`,断言三列、右列 > 左列(像素比 ≈ 1.5:1)。截图确认右屏明显更大、双屏铺满视口高度。
Expected: 右 > 左、铺满高度 ✓。

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat(全屏): 双屏 40/60 右为主 + 左栏高度自适应"
```

---

## Task 6: 左栏可收起 / 展开(‹ / ›)

**Files:**
- Modify: `templates/index.html`(CSS `.rail-collapsed` + 竖条;DOM 中缝 `‹` 钮 + 左栏竖条;JS `toggleRail`)

- [ ] **Step 1: CSS —— 收起态 + 竖条**

```css
  /* 左栏收起 */
  .theater.fs .split.rail-collapsed{grid-template-columns:34px 0px minmax(0,1fr)}
  .rail-collapsed .scr-data .scr-head,
  .rail-collapsed .scr-data #log,
  .rail-collapsed .scr-data .ledger,
  .rail-collapsed .scr-data #kwPanel{display:none}
  .rail-collapsed .gutter{display:none}
  .rail-strip{display:none}
  .rail-collapsed .scr-data .rail-strip{display:flex; flex-direction:column; align-items:center;
    justify-content:space-between; height:100%; padding:10px 0; background:var(--card)}
  .rail-strip .rx{font-family:var(--mono); font-size:13px; color:#fff; background:var(--red);
    width:22px; height:22px; display:grid; place-items:center; cursor:pointer; border:0}
  .rail-strip .vt{writing-mode:vertical-rl; font-size:11px; letter-spacing:.16em; color:var(--ink); font-weight:600}
  .rail-strip .vn{writing-mode:vertical-rl; font-family:var(--mono); font-size:9px; color:var(--muted)}
  /* 中缝收起钮 */
  .rail-toggle{writing-mode:horizontal-tb; width:18px; height:18px; display:grid; place-items:center;
    border:1px solid var(--ink); background:var(--paper); color:var(--ink); cursor:pointer; font-size:11px; padding:0}
  .rail-toggle:hover{background:var(--red); color:#fff; border-color:var(--red)}
```

- [ ] **Step 2: DOM —— 中缝加 `‹` 钮、左栏加竖条**

在 `.gutter`(`<div class="gutter" aria-hidden="true">…</div>`)的最前面加收起钮:
```html
        <div class="gutter" aria-hidden="true">
          <button class="rail-toggle" id="railToggle" type="button" title="收起数据栏">‹</button>
          <span class="arr">←</span>
          <span class="dx" data-dx="weight">权重</span>
          <span class="wlabel">two weightings</span>
          <span class="arr">→</span>
        </div>
```
在 `.scr.scr-data`(左栏)里,`.scr-head` 之前加竖条:
```html
        <div class="scr scr-data">
          <div class="rail-strip">
            <button class="rx" id="railExpand" type="button" title="展开数据栏">›</button>
            <span class="vt">给搜索引擎</span>
            <span class="vn" id="railCount">0/0</span>
          </div>
          <div class="scr-head">
```

- [ ] **Step 3: JS —— toggleRail + 计数同步**

在 IIFE 内加:
```javascript
  const splitEl = document.querySelector(".split");
  function setRail(collapsed) {
    splitEl.classList.toggle("rail-collapsed", collapsed);
    const c = document.getElementById("railCount");
    if (c) c.textContent = stage.done + "/" + (stage.total || countPlanned() || "?");
  }
  document.getElementById("railToggle").addEventListener("click", () => setRail(true));
  document.getElementById("railExpand").addEventListener("click", () => setRail(false));
  document.addEventListener("keydown", e => {
    if (e.key === "[" && theater.classList.contains("fs"))
      setRail(!splitEl.classList.contains("rail-collapsed"));
  });
```
并在 `setProg(done, total)` 末尾同步竖条计数,加一行:
```javascript
    const rc = document.getElementById("railCount"); if (rc) rc.textContent = done + " / " + (total || "?");
```

- [ ] **Step 4: 浏览器实测 —— 收起/展开**

evaluate(全屏生成态):点 `#railToggle` → 断言 `.split` 含 `rail-collapsed`、`gridTemplateColumns` 左列 ≈ 34px、`.rail-strip` 可见、右屏变宽;截图。再点 `#railExpand` → 断言移除 `rail-collapsed`、还原。
Expected: 收起成竖条 ✓、展开还原 ✓。

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat(全屏): 左数据栏可收起为竖条(‹/›/[ 切换),右屏全幅"
```

---

## Task 7: 完成下钻 —— 页面标签 → 行高亮 + 关键词落位明细

**Files:**
- Modify: `templates/index.html`(CSS `#kwPanel`/`.lrow.sel`;DOM `#kwPanel`;JS `finalizeStage` 存数据、`activateTab` 联动、`renderLanding`)

- [ ] **Step 1: CSS —— 选中行 + 落位明细面板**

```css
  .lrow.sel{background:var(--red); color:#fff}
  .lrow.sel .ltitle, .lrow.sel .ltype, .lrow.sel .lstate{color:#fff}
  .lrow.sel .lscore .pass, .lrow.sel .lscore .miss, .lrow.sel .lscore .muted{color:#fff}
  #kwPanel{display:none; margin:0 12px 12px; border:1px solid var(--red); background:#fff;
    font-family:var(--mono); font-size:12px; color:var(--ink2)}
  #kwPanel.show{display:block}
  #kwPanel .kh{display:flex; justify-content:space-between; padding:7px 10px; border-bottom:1px solid var(--line);
    background:var(--red-wash); color:var(--ink)}
  #kwPanel .kh b{color:var(--red)}
  #kwPanel .kbody{padding:8px 10px; line-height:1.85}
  #kwPanel .pos{display:flex; justify-content:space-between; border-bottom:1px dashed var(--line); padding:2px 0}
  #kwPanel .hit{color:var(--ok); font-weight:600}
  #kwPanel .miss{color:var(--red); font-weight:600}
  #kwPanel .dim{display:flex; justify-content:space-between; margin-top:5px; padding-top:5px; border-top:1px solid var(--line)}
  #kwPanel .dim b{color:var(--ink)}
```

- [ ] **Step 2: DOM —— 左栏 #ledger 之后加 #kwPanel**

在 `<div class="ledger" id="ledger"></div>` 之后加:
```html
          <div id="kwPanel"></div>
```

- [ ] **Step 3: JS —— finalizeStage 存 breakdown/landing/kw**

在 `finalizeStage(summary)` 的 `rows.forEach(r => {...})` 里,设置完 score 之后加:
```javascript
      row.breakdown = r.breakdown || null;
      row.landing = r.landing || null;
      row.kw = r.target_keyword || "";
```
(即该块变为:)
```javascript
    rows.forEach(r => {
      if (!r.slug) return;
      const row = ensureRow(r.slug, r.title || r.slug, r.type || "");
      if (r.score != null && row.score == null) setRowScore(row, r.score, r.passed !== false);
      row.breakdown = r.breakdown || null;
      row.landing = r.landing || null;
      row.kw = r.target_keyword || "";
      if (row.state !== "done") { setRowState(row, "done"); revealPage(r.slug, row.title); }
    });
```

- [ ] **Step 4: JS —— renderLanding + activateTab 联动**

加 `renderLanding`:
```javascript
  function renderLanding(slug) {
    const panel = document.getElementById("kwPanel");
    const row = stage.rows[slug];
    // 高亮选中行
    document.querySelectorAll("#ledger .lrow").forEach(el => el.classList.remove("sel"));
    if (row && row.el) row.el.classList.add("sel");
    if (!row || !row.landing || !row.landing.present) { panel.className = ""; panel.innerHTML = ""; return; }
    const L = row.landing, bd = row.breakdown || {};
    const ku = bd.keyword_usage || {};
    const yn = (ok, pts) => ok ? '<span class="hit">命中 ' + pts + '</span>' : '<span class="miss">未命中</span>';
    const bodyPts = L.body_count >= 1 && L.body_count <= 4 ? "+3"
                  : L.body_count > 6 ? "堆砌 −3" : (L.body_count === 0 ? "0" : "+0");
    panel.innerHTML =
      '<div class="kh"><span>关键词落位 · <b>' + escapeHtml(row.kw || "") + '</b></span>' +
      '<span>' + escapeHtml(row.title || slug) + '</span></div>' +
      '<div class="kbody">' +
      '<div class="pos"><span>标题 title</span>' + yn(L.title, "+5") + '</div>' +
      '<div class="pos"><span>H2 / 前 150 词</span>' + yn(L.heading_intro, "+4") + '</div>' +
      '<div class="pos"><span>meta 描述</span>' + yn(L.meta, "+3") + '</div>' +
      '<div class="pos"><span>正文出现 ×' + L.body_count + '</span><span class="' +
        (L.body_count >= 1 && L.body_count <= 4 ? "hit" : "miss") + '">' + bodyPts + '</span></div>' +
      '<div class="dim"><span>keyword_usage 维度</span><b>' + (ku.score != null ? ku.score : "—") +
        ' / ' + (ku.max != null ? ku.max : 15) + '</b></div>' +
      '<div class="dim"><span>确定性总分</span><b>' + (row.score != null ? row.score : "—") + ' / 100</b></div>' +
      '</div>';
    panel.className = "show";
  }
```
把现有 `activateTab(slug, title)` 末尾(`fitProof();` 之前或之后)加一行:
```javascript
    renderLanding(slug);
```

- [ ] **Step 5: 浏览器实测 —— 完成下钻**

跑完一次 demo(全屏、等完成 8/8)。evaluate:点 `#pageTabs .ptab:nth-child(2)` → 断言:
- 对应 `#ledger .lrow.sel` 出现且唯一;
- `#kwPanel.show` 出现,文本含目标词、含「命中 +5」或「未命中」、含 `keyword_usage` 维度分与总分;
- `#prevFrame.src` 指向该页 `/output/<slug>.html`。
并人工核:面板里的命中/分数与 `python -c "import render_samples as R;..."` 跑出的该页 `breakdown.keyword_usage` 一致(诚实)。
Expected: 行高亮 + 落位明细 + 右屏切页,数字与真实 breakdown 一致 ✓。

- [ ] **Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat(下钻): 完成后点页面标签 → 行高亮 + 关键词落位明细(真实 breakdown)"
```

---

## Task 8: 错误 / 移动端 / 整体收尾验证

**Files:**
- Modify: `templates/index.html`(CSS 移动端 fs 断点)

- [ ] **Step 1: CSS —— 移动端全屏现场上下堆叠**

在现有 `@media (max-width:860px)` 块内加:
```css
    .theater.fs .split{grid-template-columns:1fr}
    .theater.fs .split.rail-collapsed{grid-template-columns:1fr}
    .theater.fs .scr-data{max-height:42vh}
    .theater.fs .fs-stamp{display:none}
```

- [ ] **Step 2: 浏览器实测 —— 无 key /run 优雅 + 移动端 + 全程**

依次验(全部 patchright,0 console 报错):
1. 1280 桌面:`#demoBtn` → 全屏、预热 → 逐字 → 完成 8/8 → 收起/展开 → 点标签下钻;`✕` 退场。
2. 真 `/run` 无 key(选 config=pu-leather.yaml、preview):进入全屏、左栏 `#log` 打出 authentication 错误行、`#dot` 转 `err`、可 `✕` 退;不崩。
3. 390 移动:`#demoBtn` → 全屏现场左右改上下、可下钻。
Expected: 三项全过、0 console 报错。

- [ ] **Step 3: 截图留档**

桌面全屏生成中 / 收起态 / 完成下钻 / 移动端 各截一张(repo 根,`/*.png` 已 gitignore)。

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat(全屏): 移动端现场上下堆叠 + 整体收尾验证"
```

---

## 自审(写完对照 spec)

- **spec 覆盖**:全屏接管(T4)、布局C 40/60(T5)、可收起(T6)、完成留现场下钻(T7)、退场✕/Esc+生成中确认(T4)、无 key 优雅(T8)、移动端(T8)、breakdown 透传+诚实落位(T1/2/3/7)、零后端管线改动(只透传+派生)——均有对应任务。
- **占位扫描**:无 TBD/TODO;每个改动给了具体代码与校验命令。
- **类型一致**:`_keyword_landing` 返回键(present/title/meta/heading_intro/body_count)在 T2 定义、T3 透传、T7 消费,一致;前端 `row.breakdown/landing/kw` 在 T7 统一存取;CSS 类名 `.theater.fs`/`.rail-collapsed`/`.lrow.sel`/`#kwPanel`/`#railToggle`/`#railExpand`/`#fsClose` 跨任务一致。
- **诚实红线**:下钻明细全部来自真实 `breakdown` + 派生命中,T2 有「对真实 quality 输出」的单测,T7 验收要求与真实 breakdown 一致。
