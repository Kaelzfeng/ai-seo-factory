"""LLM 封装：加载 skill 文件 + 强制结构化输出。

支持的 provider:
- anthropic（默认）：官方 Anthropic API,读 ANTHROPIC_API_KEY。
- deepseek：走 DeepSeek Anthropic 兼容端点 https://api.deepseek.com/anthropic,
  读 DEEPSEEK_API_KEY。接口同形,structured()/structured_stream() 复用。
- openai：OpenAI Chat Completions API,读 OPENAI_API_KEY,
  使用 response_format json_object + prompt-level schema 实现结构化输出。
- mock：返回 mock 结构化数据,用于测试(无需 API key)。

provider 选择(`_provider()`,每次动态读环境):
  显式 LLM_PROVIDER 优先；否则有 DEEPSEEK_API_KEY → deepseek；
  有 OPENAI_API_KEY → openai；再否则 anthropic。
"""
import json
import os
import pathlib
import threading
from anthropic import Anthropic

SKILLS_DIR = pathlib.Path(__file__).resolve().parent.parent / "skills"

# ---------------------------------------------------------------------------
# Token 用量计数器(线程本地累加,向后兼容)
# ---------------------------------------------------------------------------
# structured()/structured_stream() 每次调用都把本次响应的 usage(input/output tokens)
# 累加进【当前线程】的计数器。调用方(run.generate_site / app.py /run)可:
#   reset_usage()  开跑前清零(只清当前线程,不串户)
#   last_usage()   读 {"input_tokens", "output_tokens", "total_tokens", "calls"}
# 用线程本地是因为 app.py 每次 /run 在独立后台线程里跑管线,多个并发请求互不污染。
# 关键:这套计数完全旁路,不改变 structured()/structured_stream() 的返回值结构,
#       现有 run.py 调用方一行不用动。
_usage_local = threading.local()


def _usage_state() -> dict:
    """取当前线程的 usage 累加器(首次访问惰性初始化)。"""
    state = getattr(_usage_local, "usage", None)
    if state is None:
        state = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
        _usage_local.usage = state
    return state


def reset_usage() -> None:
    """清零当前线程的 token 计数器(开跑前调一次)。只影响当前线程。"""
    _usage_local.usage = {"input_tokens": 0, "output_tokens": 0,
                          "total_tokens": 0, "calls": 0}


def last_usage() -> dict:
    """读当前线程累计的 token 用量。返回
    {"input_tokens", "output_tokens", "total_tokens", "calls"} 的拷贝。
    """
    return dict(_usage_state())


def _record_usage(usage) -> None:
    """把一次 API 响应的 usage(anthropic/deepseek 同形:.input_tokens/.output_tokens)
    累加进当前线程计数器。usage 缺失或字段缺失都安全降级为 0,绝不抛(计数失败
    不能影响生成本身)。"""
    if usage is None:
        return
    try:
        it = getattr(usage, "input_tokens", None)
        ot = getattr(usage, "output_tokens", None)
        # 兼容 dict 形态的 usage(极少数 SDK/网关变体)。
        if it is None and isinstance(usage, dict):
            it = usage.get("input_tokens")
        if ot is None and isinstance(usage, dict):
            ot = usage.get("output_tokens")
        it = int(it or 0)
        ot = int(ot or 0)
    except (TypeError, ValueError):
        return
    state = _usage_state()
    state["input_tokens"] += it
    state["output_tokens"] += ot
    state["total_tokens"] += it + ot
    state["calls"] += 1

# DeepSeek 的 Anthropic 兼容网关(同 Messages API 形状,tool-use/流式可复用)
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"

# 各 provider 的角色默认模型(role: planner=规划/便宜, writer=写作/强)
_DEFAULT_MODELS = {
    "anthropic": {"planner": "claude-haiku-4-5-20251001", "writer": "claude-sonnet-4-6",
                  "polish": "claude-haiku-4-5-20251001"},
    "deepseek":  {"planner": "deepseek-v4-flash",          "writer": "deepseek-v4-pro",
                  "polish": "deepseek-v4-flash"},
    "openai":    {"planner": "gpt-4o-mini",                "writer": "gpt-4o",
                  "polish": "gpt-4o-mini"},
    "mock":      {"planner": "mock",                       "writer": "mock",
                  "polish": "mock"},
}


def _provider() -> str:
    """动态判定当前 provider：
    显式 LLM_PROVIDER > DEEPSEEK_API_KEY > OPENAI_API_KEY > anthropic。
    """
    p = os.getenv("LLM_PROVIDER", "").strip().lower()
    if p:
        return p
    if os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "anthropic"


def default_model(role: str, provider: str = None) -> str:
    """按 provider + 角色取默认模型 id。run.py 在未显式指定 *_MODEL 时用它。"""
    p = provider or _provider()
    table = _DEFAULT_MODELS.get(p, _DEFAULT_MODELS["anthropic"])
    return table.get(role, "")


_client = None
_client_provider = None
_openai_client = None


def _get_client():
    """返回 (anthropic_client, openai_client_or_none)。"""
    global _client, _client_provider, _openai_client
    p = _provider()
    if _client is None or _client_provider != p:
        if p == "deepseek":
            key = os.getenv("DEEPSEEK_API_KEY")
            if not key:
                raise RuntimeError("provider=deepseek 但未设置 DEEPSEEK_API_KEY")
            _client = Anthropic(base_url=_DEEPSEEK_BASE_URL, api_key=key)
            _openai_client = None
        elif p == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("provider=openai 但未设置 OPENAI_API_KEY")
            try:
                import openai as _openai_mod
                _openai_client = _openai_mod.OpenAI(api_key=key)
                _client = None
            except ImportError:
                raise RuntimeError("provider=openai 需要 pip install openai")
        elif p == "mock":
            _client = None
            _openai_client = None
        else:
            _client = Anthropic()  # ANTHROPIC_API_KEY
            _openai_client = None
        _client_provider = p
    return _client, _openai_client


def _structured_openai(model: str, system: str, user: str, schema: dict,
                       max_tokens: int = 4096) -> dict:
    """OpenAI structured output: JSON mode + parse。"""
    import openai as _oai
    client, _ = _get_client()  # returns (None, openai_client)
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialized")
    # 构建 JSON schema 描述
    schema_desc = json.dumps(schema, ensure_ascii=False)
    prompt = f"""{user}

IMPORTANT: You MUST return a valid JSON object matching this schema:
{schema_desc}

Return ONLY the JSON object, no markdown, no code fences."""
    try:
        resp = _openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        text = resp.choices[0].message.content
        # Parse JSON
        if text:
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
            return json.loads(text)
        raise RuntimeError("OpenAI 返回空响应")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OpenAI JSON 解析失败: {e}")
    except Exception as e:
        raise RuntimeError(f"OpenAI 调用异常: {e}")


import re


def load_skill(name: str) -> str:
    """读取 skills/<name>/SKILL.md 作为 system prompt。"""
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def structured(model: str, system: str, user: str, schema: dict,
               max_tokens: int = 4096, tool_name: str = "emit") -> dict:
    """用 tool use / json_mode 强制模型返回符合 schema 的 JSON。

    支持: anthropic/deepseek (tool_use), openai (json_object), mock (fake return)。
    """
    p = _provider()

    # Mock provider: return fake structured data
    if p == "mock":
        return _mock_structured(schema)

    # OpenAI provider: json_object mode
    if p == "openai":
        return _structured_openai(model, system, user, schema, max_tokens)

    # Anthropic / DeepSeek: tool_use mode
    client, _ = _get_client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "disabled"},
        tools=[{
            "name": tool_name,
            "description": "Return the structured result.",
            "input_schema": schema,
        }],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    )
    _record_usage(getattr(resp, "usage", None))
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("模型未返回结构化结果")


def _mock_structured(schema: dict) -> dict:
    """Mock provider: 从 schema 构造最小合法输出。"""
    result = {}
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        prop = props.get(key, {})
        ptype = prop.get("type", "string")
        if ptype == "string":
            result[key] = f"mock_{key}_value"
        elif ptype == "array":
            result[key] = []
        elif ptype == "object":
            result[key] = {}
        else:
            result[key] = f"mock_{key}"
    return result


def _partial_field(buf: str, key: str):
    """从一段【还在增长的】JSON 对象文本里，尽力抽出字符串字段 `key` 的当前值。

    Anthropic 流式 tool_use 的入参是 input_json_delta（一段段拼起来的不完整 JSON），
    想「看着 html 一个字一个字长出来」就得在 JSON 还没闭合时把 html 值解出来。
    实现：定位 "key" → 冒号 → 开引号，然后逐字反转义直到遇到未转义的结束引号或缓冲耗尽
    （耗尽=还在流，返回到目前为止的部分）。纯函数、无网络、可单测。
    """
    marker = '"%s"' % key
    i = buf.find(marker)
    if i < 0:
        return None
    j = buf.find(":", i + len(marker))
    if j < 0:
        return None
    k = j + 1
    while k < len(buf) and buf[k] in " \t\r\n":
        k += 1
    if k >= len(buf) or buf[k] != '"':
        return None  # 值还没开始（不是字符串或尚未到引号）
    k += 1
    esc = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\",
           "/": "/", "b": "\b", "f": "\f"}
    out = []
    while k < len(buf):
        c = buf[k]
        if c == "\\":
            if k + 1 >= len(buf):
                break  # 转义未传完，停在这（下一段会补上）
            nxt = buf[k + 1]
            if nxt == "u":
                if k + 6 <= len(buf):
                    try:
                        out.append(chr(int(buf[k + 2:k + 6], 16)))
                    except ValueError:
                        pass
                    k += 6
                    continue
                break  # \uXXXX 还没传全
            out.append(esc.get(nxt, nxt))
            k += 2
            continue
        if c == '"':
            break  # 字符串正常闭合
        out.append(c)
        k += 1
    return "".join(out)


def structured_stream(model: str, system: str, user: str, schema: dict,
                      on_delta=None, field: str = "html",
                      max_tokens: int = 4096, tool_name: str = "emit") -> dict:
    """structured() 的【流式】版本 —— Tier B 真·逐字生成。

    边流边把字段 `field`（默认 html，即页面正文）的当前内容回调给 on_delta(text)，
    让前端右屏「网页·给人」逐字 materialize。最终仍返回完整、已校验的结构化 dict
    （与 structured() 同形），所以 run.py 的后续质检/渲染逻辑完全不用改。

    需要 ANTHROPIC_API_KEY；没有 key 时 _get_client() 会抛 —— 调用方负责兜底报错。
    """
    acc = []
    last = ""
    with _get_client().messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        # 关思考模式:见 structured() 注释 —— 思考模式 + 强制 tool_choice 在 DeepSeek 会 400。
        thinking={"type": "disabled"},
        tools=[{
            "name": tool_name,
            "description": "Return the structured result.",
            "input_schema": schema,
        }],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for event in stream:
            if getattr(event, "type", None) != "content_block_delta":
                continue
            delta = getattr(event, "delta", None)
            if getattr(delta, "type", None) != "input_json_delta":
                continue
            acc.append(getattr(delta, "partial_json", "") or "")
            if on_delta:
                cur = _partial_field("".join(acc), field)
                if cur is not None and cur != last:
                    last = cur
                    on_delta(cur)
        final = stream.get_final_message()
    # 旁路记账:流式同样从最终消息读 usage 累加(get_final_message 带完整 usage)。
    _record_usage(getattr(final, "usage", None))
    for block in final.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("模型未返回结构化结果")
