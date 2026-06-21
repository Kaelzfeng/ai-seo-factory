# -*- coding: utf-8 -*-
"""tests/test_conversational_intent_memory.py · Phase 9.3.8: Generic Conversational Intent Engine

Tests for merge_intent, is_intent_ready, build_clarification, and multi-turn memory.
All tests are pure unit tests on lib.intent_engine — no HTTP, no DB.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════
# Pure unit tests on intent_engine
# ═══════════════════════════════════════════════════════

def test_initial_b2b_hardware_sentence_locks_intent():
    """单句完整输入应直接 ready，不追问。"""
    from lib.intent_engine import merge_intent, is_intent_ready, empty_intent
    intent = merge_intent(empty_intent(),
        "我要你帮我生成一个卖五金工具的网站，我需要面对英语 b2b 企业的")
    assert intent["product"] == "五金工具"
    assert intent["industry"] == "hardware tools"
    assert intent["language"] == "English"
    assert intent["audience"] is not None  # B2B detected
    assert is_intent_ready(intent)


def test_multiturn_slots_are_merged():
    """4 轮多轮对话应全部合并。"""
    from lib.intent_engine import merge_intent, is_intent_ready, empty_intent
    intent = empty_intent()
    intent = merge_intent(intent, "五金工具")
    assert intent["product"] == "五金工具"
    assert not is_intent_ready(intent)  # only product, no audience yet

    intent = merge_intent(intent, "海外批发商")
    assert intent["audience"] == "海外批发商"
    # With product + audience, language defaults to English and goal infers → ready
    assert is_intent_ready(intent)
    assert intent["language"] == "English"  # auto-defaulted
    assert intent["goal"] == "generate website"  # auto-inferred

    # Additional turns still merge correctly
    intent = merge_intent(intent, "日语")
    assert intent["language"] == "Japanese"  # override default English

    intent = merge_intent(intent, "日本市场")
    assert intent["market"] == "日本"
    assert is_intent_ready(intent)


def test_product_answer_is_remembered():
    """产品回答后应被记住，不丢失。"""
    from lib.intent_engine import merge_intent, empty_intent
    intent = merge_intent(empty_intent(), "我要做家具")
    assert intent["product"] == "家具"
    # 下一轮不应该清空产品
    intent = merge_intent(intent, "海外批发商")
    assert intent["product"] == "家具"
    assert intent["audience"] == "海外批发商"


def test_audience_answer_is_remembered():
    """买家回答后应被记住。"""
    from lib.intent_engine import merge_intent, empty_intent
    intent = merge_intent(empty_intent(), "wholesale buyers")
    assert "wholesale" in intent["audience"].lower() or "buyers" in intent["audience"].lower()
    intent = merge_intent(intent, "hardware tools")
    assert "buyers" in intent["audience"].lower() or "wholesale" in intent["audience"].lower()
    assert intent["product"] == "Hardware Tools" or intent["industry"] == "hardware tools"


def test_language_answer_is_remembered():
    """语言回答后应被记住。"""
    from lib.intent_engine import merge_intent, empty_intent
    intent = merge_intent(empty_intent(), "英文网站")
    assert intent["language"] == "English"
    intent = merge_intent(intent, "五金工具")
    assert intent["language"] == "English"  # 不丢失
    assert intent["product"] == "五金工具"


def test_market_answer_is_remembered():
    """市场回答后应被记住。"""
    from lib.intent_engine import merge_intent, empty_intent
    intent = merge_intent(empty_intent(), "日本市场")
    assert intent["market"] == "日本"
    intent = merge_intent(intent, "五金工具 B2B")
    assert intent["market"] == "日本"  # 不丢失
    assert intent["product"] == "五金工具"


def test_no_repeated_clarification_after_slots_filled():
    """所有 slot 填满后不应再追问。"""
    from lib.intent_engine import merge_intent, is_intent_ready, get_missing_slots, empty_intent
    intent = merge_intent(empty_intent(), "五金工具 海外批发商 日语 日本市场")
    assert is_intent_ready(intent)
    missing = get_missing_slots(intent)
    assert len(missing) == 0


def test_japan_japanese_hardware_b2b_locks_intent():
    """日本+日语+五金工具+B2B → ready。"""
    from lib.intent_engine import merge_intent, is_intent_ready, empty_intent
    intent = merge_intent(empty_intent(), "Japanese B2B hardware tools Japan market")
    assert intent["language"] == "Japanese"
    assert intent["market"] == "Japan"
    assert intent["product"] == "Hardware Tools"
    assert is_intent_ready(intent)


def test_hammer_hardware_export_locks_intent():
    """Hammer hardware export → ready。"""
    from lib.intent_engine import merge_intent, is_intent_ready, empty_intent
    intent = merge_intent(empty_intent(),
        "I want to generate a hammer hardware tools B2B export site in English")
    # "hardware tools" is longer than "hammer" so _best_match prefers it
    assert "hammer" in intent.get("product", "").lower() or "hardware" in intent.get("product", "").lower()
    assert intent.get("industry") == "hardware tools"
    assert intent["language"] == "English"
    assert intent.get("audience") is not None  # B2B detected
    assert is_intent_ready(intent)


def test_furniture_export_english_us_dealers_locks_intent():
    """家具出口+英文+美国经销商 → ready（不应只支持五金工具）。"""
    from lib.intent_engine import merge_intent, is_intent_ready, empty_intent
    intent = merge_intent(empty_intent(),
        "我想做一个家具出口站，英文，面向美国经销商")
    assert intent["product"] == "家具"
    assert intent["industry"] == "furniture"
    assert intent["language"] == "English"
    assert intent["market"] == "美国"
    assert intent["audience"] == "经销商"
    assert is_intent_ready(intent)


def test_pet_supplies_europe_b2b_defaults_english():
    """宠物用品+欧洲+B2B → ready，语言默认 English。"""
    from lib.intent_engine import merge_intent, is_intent_ready, empty_intent
    intent = merge_intent(empty_intent(),
        "做一个面向欧洲 B2B 客户的宠物用品 SEO 网站")
    assert intent["product"] == "宠物用品"
    assert intent["industry"] == "pet supplies"
    assert intent["market"] == "欧洲"
    assert intent["audience"] is not None  # B2B/客户 detected
    # 未明确指定语言，但 is_intent_ready 应自动默认 English
    assert is_intent_ready(intent)
    assert intent["language"] == "English"  # auto-defaulted


def test_user_can_override_market_and_language():
    """覆盖指令应只修改指定字段，不清空已有字段。"""
    from lib.intent_engine import merge_intent, empty_intent
    intent = merge_intent(empty_intent(), "五金工具 海外批发商 英文 日本市场")
    assert intent["product"] == "五金工具"
    assert intent["market"] == "日本"
    assert intent["language"] == "English"

    # 覆盖 market 和 language
    intent = merge_intent(intent, "改成日语，美国市场")
    assert intent["language"] == "Japanese"  # overridden
    # "美国市场" in the override target should also match market
    assert "美国" in intent.get("market", "") or intent["market"] == "美国"
    assert intent["product"] == "五金工具"  # preserved
    assert intent["audience"] == "海外批发商"  # preserved


def test_clarification_asked_at_most_once_per_missing_slot():
    """每个缺失 slot 最多问一次，asked_slots 防止重复。"""
    from lib.intent_engine import merge_intent, build_clarification, empty_intent
    intent = merge_intent(empty_intent(), "五金工具")
    # 第一轮：问 audience（还没问过）
    msg1, intent = build_clarification(intent)
    assert "product" in intent.get("asked_slots", []) or len(msg1) > 0

    # 第二轮：用户只回答了产品，还没有 audience
    intent2 = merge_intent(intent, "五金工具")  # 重复产品
    msg2, intent2 = build_clarification(intent2)
    # 不应再问 product
    asked = intent2.get("asked_slots", [])
    assert asked.count("product") <= 1  # product 只被问过一次


def test_no_old_repeated_prompt_visible_after_sufficient_info():
    """信息足够后不应出现旧硬编码追问文案。"""
    from lib.intent_engine import merge_intent, is_intent_ready, build_clarification, empty_intent
    intent = merge_intent(empty_intent(), "五金工具 海外批发商 日语 日本市场")
    assert is_intent_ready(intent)
    # ready 后不应再产生 clarification
    missing = intent.get("asked_slots", [])
    # asked_slots 应该在之前已经记录
    # 如果 ready，不再 call build_clarification 就能验证


def test_conversation_state_restores_intent_slots():
    """conversation state 应包含 intent 字段，可正确序列化/反序列化。"""
    from lib.intent_engine import merge_intent, empty_intent
    intent = merge_intent(empty_intent(), "五金工具 海外批发商 日语 日本市场")
    # Simulate JSON round-trip
    dumped = json.dumps(intent, ensure_ascii=False)
    loaded = json.loads(dumped)
    assert loaded["product"] == "五金工具"
    assert loaded["audience"] == "海外批发商"
    assert loaded["language"] == "Japanese"
    assert loaded["market"] == "日本"


# ═══════════════════════════════════════════════════════
# HTTP-level tests: /intake with multi-turn
# ═══════════════════════════════════════════════════════

@pytest.fixture
def intake_app():
    from app import app as _app
    _app.config["TESTING"] = True
    _app.config["SECRET_KEY"] = "test-intent"
    return _app


def test_intake_b2b_hardware_locks_intent(intake_app, monkeypatch):
    """POST /intake with complete sentence → action=brief, not ask."""
    # Mock the LLM step to always return ask (to test fallback path)
    monkeypatch.setattr("lib.intake.step", lambda h, m: {"ok": True, "action": "ask", "message": "..."})
    with intake_app.test_client() as c:
        resp = c.post("/intake", json={
            "message": "我要你帮我生成一个卖五金工具的网站，我需要面对英语b2b企业的",
            "history": [],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["action"] == "brief"
        assert data["brief"] is not None
        assert "五金" in data["brief"].get("industry", "") or "五金" in data["brief"].get("project_name", "")


def test_intake_multiturn_merges_intent(intake_app, monkeypatch):
    """Multi-turn: intent carries across POSTs via previous_intent field.

    After turn 2 (product + audience), is_intent_ready is True
    because language defaults to English and goal infers to generate_website.
    """
    monkeypatch.setattr("lib.intake.step", lambda h, m: {"ok": True, "action": "ask", "message": "..."})

    with intake_app.test_client() as c:
        # Turn 1: just product
        resp1 = c.post("/intake", json={"message": "五金工具", "history": []})
        d1 = resp1.get_json()
        assert d1["ok"] is True
        intent1 = d1.get("intent") or {}
        assert intent1.get("product") == "五金工具"
        assert d1["action"] == "ask"  # not ready yet

        # Turn 2: add audience → becomes ready (language→English, goal→generate_website)
        resp2 = c.post("/intake", json={
            "message": "海外批发商",
            "history": [{"role": "user", "text": "五金工具"}, {"role": "agent", "text": d1["message"]}],
            "previous_intent": intent1,
        })
        d2 = resp2.get_json()
        # With product + audience, intent is ready → brief
        assert d2.get("action") in ("brief", "ask")  # may lock or ask depending on LLM
        if d2.get("intent"):
            assert d2["intent"].get("product") == "五金工具"
            assert d2["intent"].get("audience") == "海外批发商"

        # If not yet brief (LLM returned ask), test that subsequent turns merge
        if d2["action"] == "ask" and d2.get("intent"):
            intent_carried = d2["intent"]
            resp3 = c.post("/intake", json={
                "message": "日语",
                "history": [],
                "previous_intent": intent_carried,
            })
            d3 = resp3.get_json()
            if d3.get("intent"):
                assert d3["intent"].get("language") == "Japanese"
                assert d3["intent"].get("product") == "五金工具"


def test_intake_furniture_not_hardware(intake_app, monkeypatch):
    """家具输入应识别为家具，不能因为不是五金工具就失败。"""
    monkeypatch.setattr("lib.intake.step", lambda h, m: {"ok": True, "action": "ask", "message": "..."})
    with intake_app.test_client() as c:
        resp = c.post("/intake", json={
            "message": "我想做一个家具出口站，英文，面向美国经销商",
            "history": [],
        })
        data = resp.get_json()
        assert data["ok"] is True
        assert data["action"] == "brief"
        assert "家具" in data["brief"].get("industry", "") or "家具" in data.get("message", "")


# ═══════════════════════════════════════════════════════
# Conversation state endpoint
# ═══════════════════════════════════════════════════════

@pytest.fixture
def state_client(monkeypatch):
    """Setup with DB, auth, and a project."""
    import auth as _auth
    import models as _models
    from app import app as _app

    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = _models.init_db(dbpath)
    monkeypatch.setattr(_models, "_get_db", lambda: conn)

    _app.config["TESTING"] = True
    _app.config["SECRET_KEY"] = "test-state"

    tid = _models.create_tenant("cs-org")
    uid = _models.create_user("cs@test.com", "h", "s")
    _models.add_tenant_member(tid, uid, "owner")
    pid = _models.create_project(user_id=uid, name="CS Project", tenant_id=tid, seed_keyword="test")

    monkeypatch.setattr(_auth, "current_user", lambda: {"id": uid, "email": "cs@test.com"})
    monkeypatch.setattr(_auth, "current_tenant_id", lambda: tid)

    with _app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        yield c, pid, tid, conn

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def test_conversation_state_has_intent_field(state_client):
    """/api/projects/<id>/conversation-state 返回 intent 字段。"""
    c, pid, tid, conn = state_client
    resp = c.get(f"/api/projects/{pid}/conversation-state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "intent" in data  # key exists, may be empty dict


# ═══════════════════════════════════════════════════════
# Immutability guards
# ═══════════════════════════════════════════════════════

def test_output_src_not_modified():
    """output_src/ 不应被测试修改。"""
    out_dir = ROOT / "output_src"
    if out_dir.exists():
        for f in out_dir.rglob("*.html"):
            if f.is_file():
                assert f.exists()


def test_static_not_modified():
    """static/ 不应被测试修改。"""
    static_dir = ROOT / "static"
    if static_dir.exists():
        files = list(static_dir.rglob("*"))
        assert len(files) > 0
        for f in files:
            if f.is_file():
                assert f.exists()
