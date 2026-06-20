"""lib/intake.py — Phase 2 意图反问 agent(后端逻辑)

把「客户用任意语言一句话 → 多轮友好反问 → 产出一份英文 SEO brief」的对话逻辑
从 app.py 里抽出来,保持 app.py 薄。只暴露一个函数 step(),app.py 的 /intake
端点直接调它。

为什么不复用 lib/llm.structured()?
  structured() 走【强制 tool_choice】拿结构化输出。这在 DeepSeek 上必须配
  thinking=disabled 才不 400(structured 里已这么做),能用。但本任务明确要求走
  【JSON 输出】路线(prompt 出现 "json" + schema 例子 + thinking 关闭 + 剥 ```json
  围栏 + try/except 容错重试一次),好处是不依赖工具调用、对解析失败有显式降级。
  所以这里直接调底层 client.messages.create(thinking 关闭、不带 tools),自己解析
  JSON,这样既满足契约、又把 thinking/JSON gotcha 处理在一个地方。

对外契约(app.py /intake 逐字对应):
  step(history, message) -> dict
    history: [{"role":"user"|"agent","text": "..."}]  本轮 message 不含在内
    message: 本轮用户输入(任意语言)
    返回(action 二选一):
      {"ok": True, "action": "ask",   "message": "...", "chips": [...]}
      {"ok": True, "action": "brief", "message": "...", "brief": {...}}
    解析彻底失败也绝不抛:降级成一个兜底 "ask" 问题(让 /intake 永不 500)。
"""
from __future__ import annotations

import json
import re

from lib import llm

# planner 角色(deepseek-v4-flash):便宜、够用,反问/归纳不需要 writer 级模型。
_MODEL = llm.default_model("planner")

# 给模型看的 schema 例子 —— prompt 里必须出现 "json" 字样(DeepSeek JSON 输出的硬要求),
# 同时举两种 action 的形状,模型照抄即可。
_SCHEMA_HINT = """\
Respond with ONE json object and NOTHING else (no markdown, no code fences, no commentary).

If you still need to clarify (ask at most one short question per turn), output exactly:
{"action": "ask",
 "message": "<one friendly question, in Chinese>",
 "chips": ["<quick option>", "<quick option>"]}    // 0 to 4 chips; [] is allowed

Once the industry/product is clear and language + market are decided, output the brief:
{"action": "brief",
 "message": "<one-line summary, in Chinese>",
 "brief": {
   "industry": "<industry/product, ENGLISH, e.g. PU / synthetic leather>",
   "market": "<target market, e.g. Global B2B export>",
   "language": "English",
   "audience": "<one-line buyer persona, ENGLISH>",
   "differentiator": "<what makes this supplier non-generic: proprietary specs / in-house QC / certs / niche application; ENGLISH; may be empty>",
   "competitors": ["<competitor site or url, may be empty>"],
   "seed_keywords": ["<english seed 1>", "<english seed 2>"],
   "project_name": "<a name for the project, english or bilingual>"
 }}
"""

_SYSTEM = """\
You are the intake agent of an SEO website-building tool aimed at ENGLISH B2B export.
The tool generates ENGLISH SEO pages for manufacturers / suppliers; the readers are
global B2B import buyers sourcing in bulk (not end consumers).

Your job, given the user's messages (which may be in ANY language):
- Infer: industry/product, target market, language, whether it is B2B export or
  end-consumer, and whether they already have a competitor site.
- Ask ONLY about what is missing or ambiguous. At most 1-3 turns total, exactly ONE
  question per turn, each with a few quick "chips". Good chip examples:
    "B2B 批发出口 / 面向终端消费者"
    "英文出口 / 中文国内"
    "有对标站(填URL) / 我没有,先跳过"
- As soon as the industry is clear and language + market are decided, STOP asking and
  output the brief directly. Do not over-question.

Infer aggressively BEFORE asking (pre-fill, don't interrogate): from the user's first
message, deduce the product, B2B-vs-consumer, and the likely market; only ask about what
you genuinely cannot infer.

Capture the supplier's EDGE when the user reveals it — proprietary specs, an in-house QC
lab, certifications, a niche application, first-hand sourcing/test data. This
"differentiator" is what makes the generated pages genuinely unique instead of thin and
generic (it is the program's whole moat). Record it in the brief when present; leave it
blank if truly unknown. NEVER invent one — a fabricated edge is worse than an empty field.

CRITICAL — seed_keywords MUST be ENGLISH B2B search terms. Even if the user writes only
Chinese (e.g. "皮革沙发清洁剂"), you must translate/generalize into correct English B2B
keywords (e.g. "pu leather supplier", "wholesale synthetic leather",
"leather cleaner manufacturer"). NEVER put Chinese strings into seed_keywords — that is
the exact bug we are fixing.

Output language rule: the conversational "message" is in Chinese (friendly), but every
field inside "brief" (industry/market/audience/seed_keywords) is ENGLISH.
"""


def step(history, message: str) -> dict:
    """跑一轮意图对话。返回 {ok, action:"ask"|"brief", ...}(见模块 docstring)。

    永不抛:LLM 调用失败 / JSON 解析失败 都降级成一个兜底 "ask"。
    """
    message = (message or "").strip()
    if not message and not history:
        # 首轮空输入:友好开场(不调模型,省一次 token)。
        return {
            "ok": True,
            "action": "ask",
            "message": "你想做什么产品/行业的 SEO 出口站?用一句话描述就行(中英文都可)。",
            "chips": ["PU/合成革出口", "五金工具出口", "家具/家居出口"],
        }

    user_text = _build_user_turn(history, message)

    # 一次主调用 + 一次容错重试(重试时把约束再喊一遍,逼模型只吐 JSON)。
    data = _ask_llm(user_text, strict_retry=False)
    if data is None:
        data = _ask_llm(user_text, strict_retry=True)
    if data is None:
        # 彻底失败:别 500,降级成一个兜底反问,让前端继续对话。
        return {
            "ok": True,
            "action": "ask",
            "message": "我没太理解,能再说一下你的产品/行业,以及是面向海外 B2B 出口吗?",
            "chips": ["B2B 批发出口", "面向终端消费者", "英文出口 / 中文国内"],
        }

    return _normalize(data)


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------

def _build_user_turn(history, message: str) -> str:
    """把前端回传的 history + 本轮 message 拼成一段对话文本喂给模型。

    history 里 role 用 user/agent(前端口径);我们原样转写成 "User:" / "Agent:" 行,
    再附上本轮 User 输入和「现在请按 json schema 输出下一步」的指令。
    """
    lines = []
    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        role = "User" if (turn.get("role") == "user") else "Agent"
        text = str(turn.get("text", "")).strip()
        if text:
            lines.append(f"{role}: {text}")
    lines.append(f"User: {message}")
    convo = "\n".join(lines)
    return (
        "Conversation so far:\n"
        f"{convo}\n\n"
        "Now decide the next step and reply with the single json object as specified.\n"
        f"{_SCHEMA_HINT}"
    )


def _ask_llm(user_text: str, strict_retry: bool):
    """调 DeepSeek(thinking 关闭、不强制工具),解析出 dict;失败返回 None。

    gotcha 处理集中在这:
      - DeepSeek thinking 默认开,强制 tool_choice 会 400 → 我们【不带 tools】,纯文本
        JSON 输出;并显式 thinking={"type":"disabled"}(关思考 → 输出更干净、更快)。
      - prompt 里出现 "json" 字样 + schema 例子(DeepSeek JSON 输出的硬要求,已在
        _SCHEMA_HINT / system 满足)。
      - 解析前先剥 ```json ... ``` 围栏,再 json.loads;再不行就从文本里抠出第一个
        平衡的 {...} 对象兜底。
    """
    system = _SYSTEM
    if strict_retry:
        system = (
            _SYSTEM
            + "\n\nIMPORTANT: Your previous reply was not valid JSON. Output ONLY a single "
              "json object, no prose, no markdown, no code fences."
        )
    try:
        client = llm._get_client()  # 复用 lib/llm 的 provider 选择 + key(只从环境读)
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=1200,
            system=system,
            # 关思考模式:DeepSeek 默认开思考。这里不走强制工具,而是纯 JSON 文本输出,
            # 关掉思考让它直接吐 JSON(也避免把 CoT 当正文)。对原生 Claude 无害。
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception:
        return None

    # 旁路记账(与 llm.structured 同款,失败安全降级,不影响返回)。
    try:
        llm._record_usage(getattr(resp, "usage", None))
    except Exception:
        pass

    text = _resp_text(resp)
    return _parse_json(text)


def _resp_text(resp) -> str:
    """把 Anthropic/DeepSeek 响应的 text block 拼成一个字符串。"""
    parts = []
    for block in getattr(resp, "content", None) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "".join(parts).strip()


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_json(text: str):
    """从模型文本里解析出 dict;剥 ```json 围栏 + 抠第一个平衡 {...} 兜底。失败 None。"""
    if not text:
        return None
    s = text.strip()
    # 剥首尾的 ```json / ``` 围栏(模型常自作主张包一层)。
    s = _FENCE_RE.sub("", s).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # 兜底:从文本里抠出第一个括号平衡的 JSON 对象。
    obj = _extract_first_object(s)
    return obj if isinstance(obj, dict) else None


def _extract_first_object(s: str):
    """扫描出第一个括号平衡的 {...}(忽略字符串内的括号)并 json.loads。失败 None。"""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except Exception:
                    return None
    return None


def _normalize(data: dict) -> dict:
    """把模型 dict 规整成契约形状,补默认值、做类型/数量约束,绝不让脏数据漏到前端。"""
    action = (data.get("action") or "").strip().lower()

    if action == "brief":
        brief = _normalize_brief(data.get("brief") or {})
        if not brief["seed_keywords"]:
            # brief 但没有英文种子词 → 不合格,退回反问(避免后续建项目拿不到 seed)。
            return {
                "ok": True,
                "action": "ask",
                "message": "我快好了,再确认一下:你的核心产品用英文怎么说?给一两个词就行。",
                "chips": [],
            }
        msg = str(data.get("message") or "").strip() or "信息够了,这是为你整理的 brief。"
        return {"ok": True, "action": "brief", "message": msg, "brief": brief}

    # 默认(含 action=="ask" 或缺失):当作 ask。
    msg = str(data.get("message") or "").strip() or "能再补充一点你的产品/行业信息吗?"
    chips = data.get("chips")
    chips = [str(c).strip() for c in chips if str(c).strip()] if isinstance(chips, list) else []
    return {"ok": True, "action": "ask", "message": msg, "chips": chips[:4]}


def _normalize_brief(b: dict) -> dict:
    """规整 brief 子对象:补字段、英文兜底、seed_keywords/competitors 收成字符串列表。"""
    def _s(key, default=""):
        v = b.get(key)
        return str(v).strip() if v is not None else default

    def _list(key):
        v = b.get(key)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    industry = _s("industry")
    seeds = _list("seed_keywords")
    project_name = _s("project_name") or industry or (seeds[0] if seeds else "SEO Export Site")
    return {
        "industry": industry,
        "market": _s("market") or "Global B2B export",
        "language": "English",  # 工具固定产出英文站
        "audience": _s("audience") or "Global B2B import buyers sourcing in bulk",
        # 差异化/独特价值(pSEO 护城河 = 让生成页不薄):可空,绝不编造;后续可喂给 seo-content。
        "differentiator": _s("differentiator"),
        "competitors": _list("competitors"),
        "seed_keywords": seeds,
        "project_name": project_name,
    }
