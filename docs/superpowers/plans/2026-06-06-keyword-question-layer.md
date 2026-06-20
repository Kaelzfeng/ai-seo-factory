# 关键词侦察 v2 · 真实问题层 实现计划

> **For agentic workers:** 本计划由 Workflow 编排执行。按任务顺序做,每个 Step 是 2-5 分钟的单一动作,TDD,频繁提交。

**Goal:** 给 `lib/keyword_scout.py` 加真实问题层(前缀问题轮采集 + 合并 + FAQ 偏好 + 记录暴露),零 key、零反爬、mock 网络可单测。

**Architecture:** 三个新纯函数(`_norm` / `harvest_questions` / `merge_questions`)+ 改 `cluster_plan` / `grounded_plan` / `write_record` / `main`。问题层是**叠加**,不动既有 `plan/intents/harvest_log` 字段。

**Tech Stack:** Python 3,`requests`(已有),`pytest`(mock `google_autocomplete`,不打真网络)。

**红线:** 不改 `lib/quality.py`。任何问题必须来自真实补全;抓不到如实标注,绝不杜撰。

---

## Task 1: `_norm` 提取 + `harvest_questions` 问题轮采集

**Files:**
- Modify: `lib/keyword_scout.py`(在 `harvest` 后、`classify_intent` 附近加)
- Test: `tests/test_question_layer.py`(新建)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_question_layer.py
# -*- coding: utf-8 -*-
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import keyword_scout as ks


# --- 用假补全替换真网络:按 probe 前缀返回固定真问题样本 ---
_FAKE = {
    "what is pu leather": ["what is pu leather", "what is pu leather made from",
                           "what is pu leather material"],
    "is pu leather": ["is pu leather durable", "is pu leather real leather",
                      "is pu leather waterproof", "is pu leather toxic"],
    "why pu leather": ["why does pu leather peel"],
    "how to pu leather": ["how to clean pu leather", "how to clean pu leather bag"],
    "difference between pu leather and": [
        "difference between pu leather and genuine leather"],
}


def _fake_autocomplete(q, hl="en", gl="us"):
    return _FAKE.get(q.strip().lower(), [])


def test_harvest_questions_surfaces_real_questions(monkeypatch):
    monkeypatch.setattr(ks, "google_autocomplete", _fake_autocomplete)
    pool = ks.harvest_questions("PU leather", polite=0)
    # 真问题进池、带出处 probes、长度足够
    assert "is pu leather durable" in pool
    assert "is pu leather toxic" in pool
    assert pool["is pu leather durable"]["support"] >= 1
    assert pool["is pu leather durable"]["probes"]  # 有出处
    # 过短噪声被滤(< 8 字符)
    assert all(len(k) >= 8 for k in pool)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_question_layer.py::test_harvest_questions_surfaces_real_questions -v`
Expected: FAIL —`AttributeError: module ... has no attribute 'harvest_questions'`

- [ ] **Step 3: 最小实现**

在 `lib/keyword_scout.py` 中,`classify_intent` 之后加:

```python
# 问题前缀(确定性、可解释):W/H 疑问 + 是非/能否。放 seed 前缀位采真问题。
QUESTION_PREFIXES = [
    "what", "what is", "why", "how", "how to", "when", "where", "which", "who",
    "is", "are", "does", "do", "can", "will", "should",
]


def _norm(kw):
    """统一规范化:小写、压空白、去首尾空格。"""
    return re.sub(r"\s+", " ", (kw or "").strip().lower())


def harvest_questions(seed, hl="en", gl="us", polite=0.35, collect_log=False):
    """问题轮:问题前缀 × seed(前缀位)查 Google 补全,返回真问题池:
    {question: {"sources":[...], "intent":str, "support":int, "probes":[...]}}。
    support = 有多少条探针surface出它。collect_log=True 额外返回 (pool, log)。"""
    seed_l = _norm(seed)
    pool = {}
    log = []
    probes = [(p + " " + seed_l) for p in QUESTION_PREFIXES]
    probes.append("difference between " + seed_l + " and")

    def _add(q, probe):
        q = _norm(q)
        if not q or len(q) < 8:
            return
        rec = pool.setdefault(q, {"sources": set(), "probes": set(),
                                  "intent": classify_intent(q)})
        rec["sources"].add("google")
        rec["probes"].add(probe)

    for probe in probes:
        try:
            sugg = google_autocomplete(probe, hl, gl)
            for kw in sugg:
                _add(kw, probe)
            log.append({"probe": probe, "source": "google", "suggestions": sugg})
        except Exception as e:
            sys.stderr.write("q fail %r: %s\n" % (probe, e))
            log.append({"probe": probe, "source": "google", "error": str(e)})
        if polite:
            time.sleep(polite)

    out = {}
    for q, rec in pool.items():
        out[q] = {
            "sources": sorted(rec["sources"]),
            "intent": rec["intent"],
            "support": len(rec["probes"]),
            "probes": sorted(rec["probes"]),
        }
    return (out, log) if collect_log else out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_question_layer.py::test_harvest_questions_surfaces_real_questions -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/keyword_scout.py tests/test_question_layer.py
git commit -m "feat(关键词): 问题轮前缀采集 harvest_questions + _norm"
```

---

## Task 2: `merge_questions` 合并问题池进主词池

**Files:**
- Modify: `lib/keyword_scout.py`(`harvest_questions` 之后)
- Test: `tests/test_question_layer.py`

- [ ] **Step 1: 写失败测试**

```python
def test_merge_questions_marks_and_preserves(monkeypatch):
    base = {
        "pu leather": {"sources": ["google"], "intent": "other",
                       "support": 3, "queries": ["pu leather", "pu leather for"]},
        "is pu leather durable": {"sources": ["google"], "intent": "informational",
                                  "support": 1, "queries": ["pu leather is"]},
    }
    q = {
        "is pu leather durable": {"sources": ["google"], "intent": "informational",
                                  "support": 2, "probes": ["is pu leather",
                                                            "how to pu leather"]},
        "is pu leather toxic": {"sources": ["google"], "intent": "informational",
                                "support": 1, "probes": ["is pu leather"]},
    }
    merged = ks.merge_questions(base, q)
    # 既有词被打 is_question,support 不缩水,queries 取并集
    assert merged["is pu leather durable"]["is_question"] is True
    assert merged["is pu leather durable"]["support"] >= 1
    assert "is pu leather" in merged["is pu leather durable"]["queries"]
    # 新问题词正确落入
    assert merged["is pu leather toxic"]["is_question"] is True
    assert merged["is pu leather toxic"]["support"] == 1
    # 非问题词不被打标记
    assert "is_question" not in merged["pu leather"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_question_layer.py::test_merge_questions_marks_and_preserves -v`
Expected: FAIL — `has no attribute 'merge_questions'`

- [ ] **Step 3: 最小实现**

```python
def merge_questions(base_pool, q_pool):
    """把问题池并进主词池(不破坏既有 support 语义)。
    support = 该词「不同surfacing查询」并集大小。返回与 harvest() 兼容的 pool。"""
    merged = {kw: dict(rec) for kw, rec in base_pool.items()}
    for q, qrec in q_pool.items():
        probes = list(qrec.get("probes", []))
        if q in merged:
            r = merged[q]
            r["is_question"] = True
            qset = set(r.get("queries", [])) | set(probes)
            r["queries"] = sorted(qset)
            r["support"] = len(qset)
            r["sources"] = sorted(set(r.get("sources", []))
                                  | set(qrec.get("sources", [])))
        else:
            merged[q] = {
                "sources": list(qrec.get("sources", [])),
                "intent": qrec.get("intent", classify_intent(q)),
                "support": len(probes),
                "queries": probes,
                "is_question": True,
            }
    return merged
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_question_layer.py::test_merge_questions_marks_and_preserves -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/keyword_scout.py tests/test_question_layer.py
git commit -m "feat(关键词): merge_questions 合并问题池(并集 support·is_question 标记)"
```

---

## Task 3: `cluster_plan` 让 FAQ 桶偏好真问题

**Files:**
- Modify: `lib/keyword_scout.py`(`cluster_plan` 内 informational 排序处)
- Test: `tests/test_question_layer.py`

- [ ] **Step 1: 写失败测试**

```python
def test_cluster_plan_prefers_real_questions():
    # 同 informational 桶:一个真问题(is_question)、一个泛词。问题应被优先选为 FAQ 页
    pool = {
        "pu leather": {"sources": ["google"], "intent": "other", "support": 9,
                       "queries": ["pu leather"]},
        "is pu leather durable": {"sources": ["google"], "intent": "informational",
                                  "support": 2, "queries": ["is pu leather"],
                                  "is_question": True},
        "pu leather information": {"sources": ["google"], "intent": "informational",
                                   "support": 5, "queries": ["pu leather info"]},
    }
    plan = ks.cluster_plan("PU leather", pool, max_pages=7)
    faq = [p for p in plan if p["intent"] == "informational"]
    assert faq, "应至少有一个 informational 页"
    # 真问题胜过 support 更高的泛词
    assert faq[0]["target_keyword"] == "is pu leather durable"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_question_layer.py::test_cluster_plan_prefers_real_questions -v`
Expected: FAIL — 泛词 `pu leather information`(support 5)排在真问题前

- [ ] **Step 3: 最小实现**

在 `cluster_plan` 中,把现有 informational 排序块:

```python
    if "informational" in buckets:
        good = re.compile(r"\b(durable|waterproof|clean|peel|last|safe|toxic|eco|"
                          r"breathable|quality|real|care)\b", re.I)
        buckets["informational"].sort(
            key=lambda x: (0 if good.search(x[0]) else 1, -x[1]["support"], len(x[0])))
```

改为(新增 `is_question` 作首要排序键):

```python
    if "informational" in buckets:
        good = re.compile(r"\b(durable|waterproof|clean|peel|last|safe|toxic|eco|"
                          r"breathable|quality|real|care)\b", re.I)
        buckets["informational"].sort(
            key=lambda x: (0 if x[1].get("is_question") else 1,
                           0 if good.search(x[0]) else 1,
                           -x[1]["support"], len(x[0])))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_question_layer.py::test_cluster_plan_prefers_real_questions -v`
Expected: PASS

- [ ] **Step 5: 跑全量 scout 测试防回归**

Run: `python -m pytest tests/test_question_layer.py -v`
Expected: 3 passed

- [ ] **Step 6: 提交**

```bash
git add lib/keyword_scout.py tests/test_question_layer.py
git commit -m "feat(关键词): FAQ 桶优先真问题(is_question 排序优先)"
```

---

## Task 4: `grounded_plan` + `write_record` 暴露 questions 段

**Files:**
- Modify: `lib/keyword_scout.py`(`grounded_plan`、`write_record`)
- Test: `tests/test_question_layer.py`

- [ ] **Step 1: 写失败测试**

```python
def test_grounded_plan_and_record_expose_questions(monkeypatch, tmp_path):
    # mock 两个 harvest 的底层 google_autocomplete:主词 + 问题都走假数据
    def _fake(q, hl="en", gl="us"):
        ql = q.strip().lower()
        if ql.startswith(("what", "is ", "why", "how", "difference")):
            return _FAKE.get(ql, [])
        return ["pu leather wholesale", "pu leather supplier"]
    monkeypatch.setattr(ks, "google_autocomplete", _fake)
    monkeypatch.setattr(ks, "bing_autocomplete", lambda q, mkt="en-US": [])
    gp = ks.grounded_plan("PU leather", max_pages=7)
    # 顶层 questions 段存在且分组
    assert "questions" in gp and isinstance(gp["questions"], dict)
    # 既有字段保持(不破坏旧消费)
    for k in ("seed", "plan", "pool", "harvest_log", "intents"):
        assert k in gp
    # 写记录:JSON 含 questions + meta.question_count
    out = tmp_path / "rec.json"
    ks.write_record(gp, cfg={"org_name": "Acme"}, out_path=str(out))
    import json
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert "questions" in rec
    assert "question_count" in rec["meta"]
    # 旧字段仍在
    for k in ("plan", "intents", "harvest_log"):
        assert k in rec
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_question_layer.py::test_grounded_plan_and_record_expose_questions -v`
Expected: FAIL — `gp` 无 `questions` 键

- [ ] **Step 3: 改 `grounded_plan`**

把现有 `grounded_plan` 整体替换为:

```python
def grounded_plan(seed, modifiers=None, max_pages=7):
    """一站式:采集(主词池 + 问题轮)+ 合并 + 接地规划。
    返回 {seed, pool_size, plan, pool, harvest_log, intents, questions, question_log}。"""
    pool, log = harvest(seed, modifiers=modifiers, collect_log=True)
    q_pool, q_log = harvest_questions(seed, collect_log=True)
    pool = merge_questions(pool, q_pool)
    plan = cluster_plan(seed, pool, max_pages=max_pages)

    by_intent = {}
    for kw, rec in pool.items():
        by_intent.setdefault(rec["intent"], []).append(kw)
    intents = {k: {"count": len(v),
                   "samples": sorted(v, key=lambda x: -pool[x]["support"])[:10]}
               for k, v in by_intent.items()}

    # 真问题按意图分组(供透明视图「买家真在问」)
    questions = {}
    for q, rec in q_pool.items():
        questions.setdefault(rec["intent"], []).append(
            {"q": q, "support": rec["support"], "sources": rec["sources"]})
    for k in questions:
        questions[k].sort(key=lambda d: -d["support"])
        questions[k] = questions[k][:12]

    return {"seed": seed, "pool_size": len(pool), "plan": plan, "pool": pool,
            "harvest_log": log, "intents": intents,
            "questions": questions, "question_log": q_log}
```

- [ ] **Step 4: 改 `write_record`**

在 `write_record` 的 `rec` 字典里:`meta` 加 `"question_count"`,顶层加 `"questions"`。把:

```python
    rec = {
        "meta": {
            "seed": gp["seed"],
            "market": "English · Google + Bing autocomplete",
            "note": "确定性 · 真实搜索补全 · 零 LLM · 有出处",
            "org": cfg.get("org_name") or cfg.get("name") or "",
            "pool_size": gp["pool_size"],
            "queries_fired": [l["query"] for l in gp["harvest_log"]],
            "page_count": len(gp["plan"]),
        },
        "harvest_log": gp["harvest_log"],
        "intents": gp["intents"],
        "plan": gp["plan"],
    }
```

改为:

```python
    rec = {
        "meta": {
            "seed": gp["seed"],
            "market": "English · Google + Bing autocomplete",
            "note": "确定性 · 真实搜索补全 · 零 LLM · 有出处",
            "org": cfg.get("org_name") or cfg.get("name") or "",
            "pool_size": gp["pool_size"],
            "queries_fired": [l["query"] for l in gp["harvest_log"]],
            "page_count": len(gp["plan"]),
            "question_count": sum(len(v) for v in gp.get("questions", {}).values()),
        },
        "harvest_log": gp["harvest_log"],
        "intents": gp["intents"],
        "questions": gp.get("questions", {}),
        "plan": gp["plan"],
    }
```

- [ ] **Step 5: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/test_question_layer.py -v`
Expected: 4 passed

- [ ] **Step 6: 提交**

```bash
git add lib/keyword_scout.py tests/test_question_layer.py
git commit -m "feat(关键词): grounded_plan/write_record 暴露真实问题段 questions"
```

---

## Task 5: `main()` CLI 打印真实问题段

**Files:**
- Modify: `lib/keyword_scout.py`(`main`)

- [ ] **Step 1: 改 `main` 打印**

在 `main()` 的 plan 打印循环之后、最后一行 print 之前,插入问题段打印:

```python
    if res.get("questions"):
        print("\n=== 买家真在问(真实补全·前缀问题轮·零杜撰) ===")
        for intent, qs in res["questions"].items():
            if not qs:
                continue
            print("  [%s]" % intent)
            for d in qs[:6]:
                print("    ? %-50s support:%s" % (d["q"], d["support"]))
```

- [ ] **Step 2: 语法自检(不打真网络)**

Run: `python -c "import ast; ast.parse(open('lib/keyword_scout.py',encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add lib/keyword_scout.py
git commit -m "feat(关键词): CLI 打印买家真实问题段"
```

---

## 完成标准

- `python -m pytest tests/test_question_layer.py -v` → 全绿(4-5 个测试)。
- 既有 `tests/` 不回归:`python -m pytest tests/ -q`。
- `grounded_plan` 返回含 `questions`;`keyword_record.json` 含 `questions` + `meta.question_count`;旧字段 `plan/intents/harvest_log` 不变。
- 真网络验证(主循环手动跑,非 CI):`python lib/keyword_scout.py "PU leather"` 打印真实问题段。

## Stretch(主循环本人做,不在 workflow 内)

PAA `harvest_paa(seed)` via patchright:成功写 `paa:{available:true,...}`,任何失败写 `paa:{available:false,reason}`。绝不杜撰。
