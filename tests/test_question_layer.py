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


def test_cluster_plan_prefers_real_questions():
    # 同 informational 桶:一个真问题(is_question)、一个 support 更高的泛词。
    # 两者都不命中既有 good 关键词正则,故只有 is_question 排序键能区分二者——
    # 这样测试真正校验「真问题优先」,而非被 good 词巧合带过。
    pool = {
        "pu leather": {"sources": ["google"], "intent": "other", "support": 9,
                       "queries": ["pu leather"]},
        "is pu leather good": {"sources": ["google"], "intent": "informational",
                               "support": 2, "queries": ["is pu leather"],
                               "is_question": True},
        "pu leather meaning explained": {"sources": ["google"],
                                         "intent": "informational",
                                         "support": 5,
                                         "queries": ["pu leather meaning"]},
    }
    plan = ks.cluster_plan("PU leather", pool, max_pages=7)
    faq = [p for p in plan if p["intent"] == "informational"]
    assert faq, "应至少有一个 informational 页"
    # 真问题胜过 support 更高的泛词
    assert faq[0]["target_keyword"] == "is pu leather good"


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


def test_faq_evidence_leads_with_real_question():
    # 真问题 FAQ 页的 evidence 应以买家真问题领头,而非别扭探针(spec 组件3·evidence 半)
    pool = {
        "pu leather": {"sources": ["google"], "intent": "other", "support": 9,
                       "queries": ["pu leather"]},
        "is pu leather good": {"sources": ["google"], "intent": "informational",
                               "support": 2,
                               "queries": ["how to pu leather", "is pu leather"],
                               "is_question": True},
    }
    plan = ks.cluster_plan("PU leather", pool, max_pages=7)
    faq = [p for p in plan if p["intent"] == "informational"][0]
    # evidence 第一条就是真问题本身(target),不是别扭探针 "how to pu leather"
    assert faq["evidence"][0] == "is pu leather good"


def test_merge_questions_support_does_not_shrink():
    # base.support 高于并集大小(且 queries 稀疏)时,support 不被静默缩小
    base = {"is pu leather durable": {"sources": ["google"],
                                      "intent": "informational",
                                      "support": 5, "queries": ["pu leather is"]}}
    q = {"is pu leather durable": {"sources": ["google"],
                                   "intent": "informational",
                                   "support": 1, "probes": ["is pu leather"]}}
    merged = ks.merge_questions(base, q)
    # 并集 {"pu leather is","is pu leather"} 大小=2,但既有 support=5 → 取大不缩水
    assert merged["is pu leather durable"]["support"] == 5


def test_cluster_plan_normalizes_seed_whitespace():
    # seed 含双空格:pillar support 应命中规范化池键(而非落空成 0),
    # 且规范化后的 seed 词不泄漏成重复支撑页
    pool = {
        "pu leather": {"sources": ["google"], "intent": "other", "support": 7,
                       "queries": ["pu leather"]},
        "pu leather wholesale": {"sources": ["google"], "intent": "commercial",
                                 "support": 4, "queries": ["pu leather wholesale"]},
    }
    plan = ks.cluster_plan("PU  leather", pool, max_pages=7)  # 双空格
    assert plan[0]["type"] == "pillar"
    assert plan[0]["support"] == 7  # 命中规范化池键,非 0
    assert all(p["target_keyword"] != "pu leather" for p in plan[1:])  # 不泄漏
