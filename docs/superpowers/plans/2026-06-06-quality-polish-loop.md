# 质检导向润色闭环(pro 写 + flash 润色)实现计划

> **For agentic workers:** Workflow 编排执行。每步 2-5 分钟单一动作,TDD,频繁提交。单测 mock LLM,**不打真 DeepSeek**(真生成验证由主循环做)。

**Goal:** pro 写完页 + quality.py 打分后,若有 issue,用 **flash** 跑一次定向润色修复具体扣分点,再用**同一把锁定的 quality.py 复评**,**只采用分数更高的版本**(诚实,绝不假装变好)。

**Architecture:** `lib/llm.py` 加 polish 角色默认模型;新增 `skills/seo-content-polish/SKILL.md` 润色提示词;`run.py` 加 `POLISH_MODEL` + `polish_page()` + 在 `generate_site` 写作+质检后插入润色环。

**红线:** 绝不改 `lib/quality.py`(锁定镜像)。复评走真 quality.py。润色失败/未提分 → 保留原版。

**决策:** ① 模型分工 = 写 pro / 润色 flash;② 1 次定向 pass(不无限循环);③ keep-better(按 total score);④ 润色只修被点名的 issue,**保留数据表/数字/标准/署名/字数深度**,不整篇重写。

---

## Task 1: `lib/llm.py` 加 polish 角色默认模型

**Files:** Modify `lib/llm.py`;Test `tests/test_llm_provider.py`

- [ ] **Step 1: 加测试**(追加到 `tests/test_llm_provider.py` 末尾)

```python
def test_default_model_polish_role():
    assert llm.default_model("polish", "deepseek") == "deepseek-v4-flash"
    assert llm.default_model("polish", "anthropic") == "claude-haiku-4-5-20251001"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_llm_provider.py::test_default_model_polish_role -v`
Expected: FAIL(polish 角色缺失 → 返回 ""）

- [ ] **Step 3: 实现** —— 在 `lib/llm.py` 的 `_DEFAULT_MODELS` 两个 provider 各加 `"polish"`:

```python
_DEFAULT_MODELS = {
    "anthropic": {"planner": "claude-haiku-4-5-20251001", "writer": "claude-sonnet-4-6",
                  "polish": "claude-haiku-4-5-20251001"},
    "deepseek":  {"planner": "deepseek-v4-flash",          "writer": "deepseek-v4-pro",
                  "polish": "deepseek-v4-flash"},
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_llm_provider.py -v`
Expected: 全过(原 4 + 新 1）

- [ ] **Step 5: 提交**

```bash
git add lib/llm.py tests/test_llm_provider.py
git commit -m "feat(润色): llm 加 polish 角色默认模型(deepseek-v4-flash)"
```

---

## Task 2: 润色提示词 `skills/seo-content-polish/SKILL.md`

**Files:** Create `skills/seo-content-polish/SKILL.md`

- [ ] **Step 1: 写文件**(完整内容如下,逐字写入)

````markdown
# Skill: seo-content-polish

You are a precise SEO copy editor. You receive ONE already-written B2B export-supplier page
(title, meta_description, html) plus a list of SPECIFIC quality issues a deterministic SEO
checker flagged. Make the MINIMAL edits that resolve EACH listed issue — nothing else.

## HARD RULES
- Fix ONLY the listed issues. Do NOT rewrite, re-theme, or "improve" anything not flagged.
- PRESERVE all data tables, numbers, units, standards (ISO/ASTM/SAE...), the author byline,
  the "Data last updated" line, headings, and the overall word count / depth. Never delete
  substance to satisfy a length rule that isn't about that substance.
- Keep exactly one `<h1>`. Keep body-only HTML (no `<html>`/`<head>`/`<body>` wrappers).
- Never invent or alter a URL. When removing a link, keep its visible text as plain words.

## Issue → action map
- meta description too long ("meta description NNN chars") → trim `meta_description` to
  **140–160 chars**, keep the primary keyword once + a concrete reason to click.
- title too long ("Title NN chars") → shorten `title` to **50–60 chars**, primary keyword
  near the front.
- too many siblings ("N sibling links; cap at 2-3") → remove the LEAST-relevant in-body
  sibling `<a>` links until **2–3** remain (keep their text as plain words).
- pillar linked twice ("Links to pillar N times") → keep **exactly one** link to the pillar;
  turn the extra(s) into plain text.
- keyword stuffing ("appears N times in body") → reduce the target keyword in body to **1–4**
  natural uses; replace extras with pronouns/synonyms — do NOT delete whole sentences.
- keyword missing from meta ("missing from meta description") → weave the target keyword into
  `meta_description` once, naturally.
- keyword missing from body/heading/intro ("never appears in body" / "not in heading/intro")
  → add the target keyword naturally 1–2 times in the intro or an `<h2>`, without stuffing.
- AI-slop word ("Banned AI-slop phrase: 'X'") → replace 'X' with a plain, concrete word.
  Banned: delve, dive into, comprehensive, unlock, elevate, leverage, robust, seamless,
  cutting-edge, "in today's fast-paced world", "it is worth noting", "it is important to
  understand", "in conclusion", "navigating the complex landscape".

## Output
Return via the `emit` tool exactly `{title, meta_description, html, image_query}` — the FULL
corrected page. Keep `image_query` unchanged unless trivially improvable.
````

- [ ] **Step 2: 校验文件存在且非空**

Run: `python -c "import pathlib; p=pathlib.Path('skills/seo-content-polish/SKILL.md'); print('OK', len(p.read_text(encoding='utf-8')))"`
Expected: `OK <非零长度>`

- [ ] **Step 3: 提交**

```bash
git add skills/seo-content-polish/SKILL.md
git commit -m "feat(润色): seo-content-polish 定向修复提示词(只修被点名 issue)"
```

---

## Task 3: `run.py` 接入润色环 + keep-better

**Files:** Modify `run.py`;Test `tests/test_polish_loop.py`(新建)

- [ ] **Step 1: 写失败测试**(新建 `tests/test_polish_loop.py`)

```python
# -*- coding: utf-8 -*-
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import run


_BASE = {"title": "T", "meta_description": "M", "html": "<h1>x</h1>",
         "image_query": "pu leather"}


def test_polish_keeps_better(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather", "title": "T"}
    orig = dict(_BASE)
    polished = dict(_BASE, meta_description="better")
    q_orig = {"score": 80.0, "issues": ["meta description 200 chars"]}
    q_better = {"score": 92.0, "issues": []}
    monkeypatch.setattr(run.llm, "structured", lambda *a, **k: polished)
    # 复评:润色版给高分
    monkeypatch.setattr(run.quality, "score_page", lambda pg, c, cfg: q_better)
    out_content, out_q = run.polish_page(page, orig, q_orig, {}, "profile", lambda s: None)
    assert out_content is polished
    assert out_q["score"] == 92.0


def test_polish_keeps_original_when_not_better(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather", "title": "T"}
    orig = dict(_BASE)
    polished = dict(_BASE, meta_description="worse")
    q_orig = {"score": 88.0, "issues": ["Title 80 chars"]}
    monkeypatch.setattr(run.llm, "structured", lambda *a, **k: polished)
    # 复评:润色版分更低 → 保留原版
    monkeypatch.setattr(run.quality, "score_page", lambda pg, c, cfg: {"score": 70.0, "issues": []})
    out_content, out_q = run.polish_page(page, orig, q_orig, {}, "profile", lambda s: None)
    assert out_content is orig
    assert out_q["score"] == 88.0


def test_polish_noop_when_no_issues(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather"}
    orig = dict(_BASE)
    q = {"score": 100.0, "issues": []}
    called = {"n": 0}
    monkeypatch.setattr(run.llm, "structured", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or orig)
    out_content, out_q = run.polish_page(page, orig, q, {}, "profile", lambda s: None)
    assert out_content is orig and called["n"] == 0  # 无 issue 不调 LLM


def test_polish_keeps_original_on_llm_error(monkeypatch):
    page = {"slug": "s", "target_keyword": "pu leather"}
    orig = dict(_BASE)
    q = {"score": 80.0, "issues": ["meta description 200 chars"]}
    def _boom(*a, **k):
        raise RuntimeError("deepseek down")
    monkeypatch.setattr(run.llm, "structured", _boom)
    out_content, out_q = run.polish_page(page, orig, q, {}, "profile", lambda s: None)
    assert out_content is orig and out_q is q  # 失败保留原版,不抛
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_polish_loop.py -v`
Expected: FAIL（`run` 无 `polish_page`）

- [ ] **Step 3: 实现** —— `run.py` 改两处:

(a) 模型常量区,在 `WRITER_MODEL` 行下方加:

```python
POLISH_MODEL = os.getenv("POLISH_MODEL") or llm.default_model("polish")
```

(b) 新增 `polish_page` 函数(放在 `generate_site` 定义之前):

```python
def polish_page(page, content, q, cfg, profile, on_progress=None):
    """质检导向润色(flash):对着 quality 点名的具体 issue 定向修复,复评后 keep-better。
    无 issue / 润色失败 / 未提分 → 原样返回 (content, q)。绝不假装变好。"""
    _emit = on_progress or (lambda s: None)
    issues = q.get("issues") or []
    if not issues:
        return content, q
    polish_sys = llm.load_skill("seo-content-polish")
    polish_user = (
        f"TARGET KEYWORD: {page.get('target_keyword', '')}\n"
        f"CURRENT TITLE ({len(content.get('title', ''))} chars): {content.get('title', '')}\n"
        f"CURRENT META ({len(content.get('meta_description', ''))} chars): "
        f"{content.get('meta_description', '')}\n\n"
        f"QUALITY ISSUES TO FIX (fix each, minimal edits only):\n"
        + "\n".join("- " + str(i) for i in issues)
        + f"\n\nCURRENT HTML:\n{content.get('html', '')}\n\n"
        f"Return the corrected page via the emit tool."
    )
    try:
        polished = call_with_retry(
            lambda: llm.structured(POLISH_MODEL, polish_sys, polish_user,
                                   PAGE_SCHEMA, max_tokens=8000),
            should_retry=_is_transient_llm_error,
            on_retry=lambda n, e, s: _emit(f"   ↻ 润色重试 #{n}(等 {s:.1f}s)：{e}"),
        )
    except Exception as e:
        _emit(f"   ⚠️ 润色失败(保留原版)：{e}")
        return content, q
    pq = quality.score_page(page, polished, cfg)
    if pq.get("score", 0) > q.get("score", 0):
        _emit(f"   ✨ [{POLISH_MODEL}] 润色 {q.get('score')}→{pq.get('score')} 分"
              f"(对 {len(issues)} 处定向修复)")
        return polished, pq
    _emit(f"   ↩ 润色未提分（{pq.get('score')} ≤ {q.get('score')}),保留原版")
    return content, q
```

(c) 在 `generate_site` 里,质检之后、`page["_content"]` 赋值之前插入润色环。把:

```python
        # —— 质检(确定性、无 LLM)。score_page 永不抛。
        q = quality.score_page(page, content, cfg)
        passed = q.get("passed", False)
```

改为:

```python
        # —— 质检(确定性、无 LLM)。score_page 永不抛。
        q = quality.score_page(page, content, cfg)
        # —— 质检导向润色(flash):对着 issue 定向修复,复评 keep-better(诚实)。
        content, q = polish_page(page, content, q, cfg, profile, _emit)
        passed = q.get("passed", False)
```

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/test_polish_loop.py -v` 然后 `python -m pytest tests/ -q`
Expected: polish 4 passed;全量全绿

- [ ] **Step 5: 提交**

```bash
git add run.py tests/test_polish_loop.py
git commit -m "feat(润色): generate_site 接入质检导向润色环 + keep-better(诚实复评)"
```

---

## 完成标准

- `python -m pytest tests/ -q` 全绿(含 polish 4 测)。
- `polish_page`:无 issue 不调 LLM;润色失败保留原版不抛;只采用复评更高分的版本。
- 不碰 `lib/quality.py`。
- 真 DeepSeek 端到端验证(主循环做,非 CI):重跑皮革 8 页,看「润色 X→Y 分」真发生、均分上升、AI 味词/超长 meta 被修掉。
