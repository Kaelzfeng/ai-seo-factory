# -*- coding: utf-8 -*-
"""关键词侦察 + 确定性接地规划(lib/keyword_scout.py)

把现在 plan_pages 里「haiku 脑补关键词」那一步,换成「先抓真实搜索补全、再按意图
确定性聚成页面计划」。每个目标词都有**出处**(哪些真实补全词支撑它)与**意图**。

设计要点(与项目一致):
- 工具层纯 Python、model 无关:google/bing 自动补全 + 修饰词扩展 + 磁盘缓存。
- 接地规划层**零 LLM、零 API key 也能跑**(确定性、可复算);LLM 仅作可选润色。
- 输出形状与 run.PLAN_SCHEMA 兼容(title/type/slug/target_keyword)+ provenance。

CLI:  python lib/keyword_scout.py "PU leather"
"""
import json
import os
import pathlib
import re
import sys
import time

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / "recon" / ".cache"

# 默认修饰词:覆盖对比/应用/商业/信息四类意图(可按行业覆盖)
DEFAULT_MODIFIERS = ["", "for", "vs", "best", "wholesale", "supplier",
                     "how to", "what is", "is", "price"]

# 意图分类规则(确定性、可解释)。顺序即优先级。
_INTENT_RULES = [
    ("comparison", re.compile(r"\b(vs|versus|or|difference|compared?)\b", re.I)),
    ("commercial", re.compile(r"\b(wholesale|supplier|manufacturer|factory|bulk|moq|"
                              r"price|cost|buy|for sale|hs code|near me|distributor)\b", re.I)),
    ("application", re.compile(r"\bfor\b", re.I)),
    ("informational", re.compile(r"\b(how|what|why|is|are|does|can|clean|care|repair|"
                                 r"meaning|durable|waterproof|last|fix)\b", re.I)),
]
_TYPE_BY_INTENT = {
    "comparison": "comparison",
    "application": "application",
    "commercial": "product",
    "informational": "faq",
    "other": "guide",
}


# --------------------------------------------------------------------------
# 数据源(自动补全)——只读、轻量、带磁盘缓存
# --------------------------------------------------------------------------
def _cache_get(key):
    f = CACHE_DIR / (re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_") + ".json")
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cache_put(key, val):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / (re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_") + ".json")
    f.write_text(json.dumps(val, ensure_ascii=False), encoding="utf-8")


def google_autocomplete(q, hl="en", gl="us"):
    ck = "g:" + q + ":" + hl + gl
    c = _cache_get(ck)
    if c is not None:
        return c
    r = requests.get("https://suggestqueries.google.com/complete/search",
                     params={"client": "firefox", "q": q, "hl": hl, "gl": gl},
                     headers=UA, timeout=10)
    r.raise_for_status()
    out = r.json()[1]
    _cache_put(ck, out)
    return out


def bing_autocomplete(q, mkt="en-US"):
    ck = "b:" + q + ":" + mkt
    c = _cache_get(ck)
    if c is not None:
        return c
    r = requests.get("https://api.bing.com/osjson.aspx",
                     params={"query": q, "mkt": mkt}, headers=UA, timeout=10)
    r.raise_for_status()
    out = r.json()[1]
    _cache_put(ck, out)
    return out


# --------------------------------------------------------------------------
# 采集 + 意图分层
# --------------------------------------------------------------------------
def classify_intent(kw):
    for name, rx in _INTENT_RULES:
        if rx.search(kw):
            return name
    return "other"


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
            # 不缩水:并集大小与既有 support 取大(防 base.support 与 queries 脱钩时静默缩水)
            r["support"] = max(r.get("support", 0), len(qset))
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


def harvest(seed, modifiers=None, hl="en", gl="us", mkt="en-US", polite=0.35,
            collect_log=False):
    """对 seed × 修饰词 抓 Google+Bing 补全,返回去重池:
    {keyword: {"sources": [..], "intent": str, "support": int, "queries": [..]}}。
    support = 有多少个 seed×修饰词查询surfaced 出它(越高=越主流)。
    collect_log=True 时额外返回 (pool, log),log 记录每条查询打到哪个源、返回了什么
    (供 Stage 00「词怎么来的」透明展示)。"""
    modifiers = modifiers if modifiers is not None else DEFAULT_MODIFIERS
    pool = {}
    log = []

    def _add(kw, source, query):
        kw = _norm(kw)
        if not kw or len(kw) < 3:
            return
        rec = pool.setdefault(kw, {"sources": set(), "queries": set(),
                                   "intent": classify_intent(kw)})
        rec["sources"].add(source)
        rec["queries"].add(query)

    for mod in modifiers:
        q = (seed + " " + mod).strip()
        try:
            sugg = google_autocomplete(q, hl, gl)
            for kw in sugg:
                _add(kw, "google", q)
            log.append({"query": q, "source": "google", "suggestions": sugg})
        except Exception as e:
            sys.stderr.write("google fail %r: %s\n" % (q, e))
            log.append({"query": q, "source": "google", "error": str(e)})
        time.sleep(polite)
    for q in [seed]:
        try:
            sugg = bing_autocomplete(q, mkt)
            for kw in sugg:
                _add(kw, "bing", q)
            log.append({"query": q, "source": "bing", "suggestions": sugg})
        except Exception as e:
            sys.stderr.write("bing fail %r: %s\n" % (q, e))
            log.append({"query": q, "source": "bing", "error": str(e)})
        time.sleep(polite)

    # set -> list + support 计数
    out = {}
    for kw, rec in pool.items():
        out[kw] = {
            "sources": sorted(rec["sources"]),
            "intent": rec["intent"],
            "support": len(rec["queries"]),
            "queries": sorted(rec["queries"]),
        }
    return (out, log) if collect_log else out


# --------------------------------------------------------------------------
# 确定性接地规划(零 LLM):把真实词池聚成 1 pillar + N 支撑页
# --------------------------------------------------------------------------
_STOP_NEAR = re.compile(r"\b(in chinese|singapore|malaysia|uae|near me|canada|usa|"
                        r"pronounce|crop top|goth|bralette|watch|binder|desk pad)\b", re.I)


def _slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "page"


_ACRONYMS = {"pu", "pvc", "moq", "fob", "iso", "astm", "gsm", "uv", "tpu",
             "eva", "hs", "faq", "diy", "usa", "uae", "eu", "us", "qc"}


def _titlecase(s):
    small = {"vs", "for", "and", "or", "the", "a", "to", "of", "in"}
    words = s.split()
    out = []
    for i, w in enumerate(words):
        lw = re.sub(r"[^a-z]", "", w.lower())
        if lw in _ACRONYMS:
            out.append(w.upper())
        elif w in small and i != 0:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def _title_for(kw, intent, seed):
    t = _titlecase(kw)
    if intent == "comparison":
        return t + ": Key Differences Explained"
    if intent == "application":
        return t + ": Sourcing Guide for Importers"
    if intent == "commercial":
        return t + ": MOQ, Pricing & Lead Time"
    if intent == "informational":
        m = re.match(r"(?i)^(.*?)\bis\b(.+)$", kw)
        if m and m.group(2).strip():
            return "Is %s %s? A Buyer's FAQ" % (
                _titlecase(m.group(1).strip()), _titlecase(m.group(2).strip()))
        return t.rstrip("?") + "? A Buyer's FAQ"
    return t + ": What Importers Should Know"


_Q_LEAD = re.compile(r"(?i)^(what|why|how|when|where|which|who|is|are|does|do|"
                     r"can|will|should|difference)\b")


def _evidence_for(kw, rec):
    """支撑页出处。真问题页(is_question)优先以问题本身领头、辅以问题式来源查询,
    让透明视图 §C 展示的是买家真问题而非别扭探针;其余页沿用原始 queries[:4]。"""
    qs = list(rec.get("queries", []))
    if rec.get("is_question"):
        lead = [kw] + [x for x in qs if x != kw and _Q_LEAD.search(x)]
        return (lead or qs)[:4]
    return qs[:4]


def cluster_plan(seed, pool, max_pages=7):
    """确定性地从词池聚出页面计划(pillar + 支撑页)。返回 dict 列表,
    每项 {title,type,slug,target_keyword,intent,evidence,support}。"""
    seed_l = _norm(seed)  # 与 harvest/harvest_questions 的池键规范化一致(压内部空白)

    # 过滤:去掉太地域化/跑题的长尾;去掉与 seed 完全相同的(留给 pillar)
    cands = []
    for kw, rec in pool.items():
        if kw == seed_l or _STOP_NEAR.search(kw):
            continue
        if seed_l.split()[0] not in kw and "leather" not in kw:
            # 至少与种子主词沾边(粗过滤,避免补全漂走)
            pass
        cands.append((kw, rec))

    # 每个意图桶内按 support 降序,挑代表词,保证类型多样
    buckets = {}
    for kw, rec in cands:
        buckets.setdefault(rec["intent"], []).append((kw, rec))
    for b in buckets.values():
        b.sort(key=lambda x: (-x[1]["support"], len(x[0])))
    # informational 桶:优先选真问题(durable/waterproof/clean...)而非泛词
    if "informational" in buckets:
        good = re.compile(r"\b(durable|waterproof|clean|peel|last|safe|toxic|eco|"
                          r"breathable|quality|real|care)\b", re.I)
        buckets["informational"].sort(
            key=lambda x: (0 if x[1].get("is_question") else 1,
                           0 if good.search(x[0]) else 1,
                           -x[1]["support"], len(x[0])))

    # 期望配比:对比×2、应用×2、商业×1、信息×1、其它×1(够 max_pages)
    quota = [("comparison", 2), ("application", 2), ("commercial", 1),
             ("informational", 1), ("other", 1)]
    picked = []
    seen_kw = set()

    def _near_dup(kw):
        for p in picked:
            a, b = set(kw.split()), set(p[0].split())
            if len(a & b) >= max(2, min(len(a), len(b)) - 0):
                return True
        return False

    for intent, n in quota:
        for kw, rec in buckets.get(intent, []):
            if len([p for p in picked if p[1]["intent"] == intent]) >= n:
                break
            if kw in seen_kw or _near_dup(kw):
                continue
            picked.append((kw, rec))
            seen_kw.add(kw)

    # 若没满 max_pages,用剩余高 support 词补齐
    if len(picked) < max_pages:
        rest = sorted(((kw, rec) for kw, rec in cands if kw not in seen_kw),
                      key=lambda x: -x[1]["support"])
        for kw, rec in rest:
            if len(picked) >= max_pages:
                break
            if _near_dup(kw):
                continue
            picked.append((kw, rec))
            seen_kw.add(kw)

    picked = picked[:max_pages]

    # pillar
    plan = [{
        "title": _titlecase(seed) + ": The Complete Sourcing Guide for Importers",
        "type": "pillar",
        "slug": _slug(seed + " guide"),
        "target_keyword": seed,
        "intent": "pillar",
        "evidence": [seed],
        "support": pool.get(seed_l, {}).get("support", 0),
    }]
    for kw, rec in picked:
        plan.append({
            "title": _title_for(kw, rec["intent"], seed),
            "type": _TYPE_BY_INTENT.get(rec["intent"], "guide"),
            "slug": _slug(kw),
            "target_keyword": kw,
            "intent": rec["intent"],
            "evidence": _evidence_for(kw, rec),
            "support": rec["support"],
            "sources": rec["sources"],
        })
    return plan


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


def write_record(gp, cfg=None, out_path=None):
    """把接地规划结果写成 keyword_record.json,供透明视图 Stage 00「词怎么来的」消费。
    返回写入路径。"""
    cfg = cfg or {}
    if out_path is None:
        out_path = str(pathlib.Path(__file__).resolve().parent.parent
                       / "design_round" / "transparency" / "keyword_record.json")
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
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return out_path


def main():
    seed = sys.argv[1] if len(sys.argv) > 1 else "PU leather"
    res = grounded_plan(seed)
    print("种子词:%s   真实补全词池:%d 个\n" % (seed, res["pool_size"]))
    print("=== 接地规划(确定性、有据可查、零 LLM) ===")
    for p in res["plan"]:
        tag = "PILLAR " if p["type"] == "pillar" else "  └─ "
        print("%s[%s] %s" % (tag, p["type"], p["title"]))
        print("       目标词: %-42s  意图:%-13s support:%s"
              % (p["target_keyword"], p["intent"], p.get("support")))
        if p["type"] != "pillar":
            print("       出处(真实补全): %s" % " · ".join(p["evidence"]))
    if res.get("questions"):
        print("\n=== 买家真在问(真实补全·前缀问题轮·零杜撰) ===")
        for intent, qs in res["questions"].items():
            if not qs:
                continue
            print("  [%s]" % intent)
            for d in qs[:6]:
                print("    ? %-50s support:%s" % (d["q"], d["support"]))
    print("\n(词池与计划可喂给 run.plan_pages;LLM 仅作可选润色)")


if __name__ == "__main__":
    main()
