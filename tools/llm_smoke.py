# -*- coding: utf-8 -*-
"""DeepSeek(或 Anthropic)端到端冒烟:key 到位后跑这个确认 provider + 端点 + tool-use 通。

    python tools/llm_smoke.py            # 非流式 structured()
    python tools/llm_smoke.py --stream   # 流式 structured_stream()(验 Tier B「看着生成」)

只发一个极小请求,确认:① 选对了 provider ② key/端点能用 ③ tool-use 返回结构化 JSON。
不碰流水线、不写文件。失败会打印清楚的错误(缺 key / 端点不支持 tool 流式 等)。
"""
import sys
import pathlib

# Windows 控制台默认 cp1252,打印 emoji/中文会 UnicodeEncodeError —— 强制 utf-8。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()
from lib import llm  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "greeting": {"type": "string"},
        "language": {"type": "string"},
    },
    "required": ["greeting", "language"],
}


def main():
    stream = "--stream" in sys.argv[1:]
    provider = llm._provider()
    model = llm.default_model("writer")
    print(f"provider = {provider}   model = {model}   stream = {stream}")
    system = "You return only the requested structured fields. Be terse."
    user = "Greet a leather-goods importer in one short sentence. Set language to the language you used."

    if stream:
        chunks = []

        def on_delta(text):
            # 流式:打印 greeting 字段逐步增长(证明逐字 materialize 可用)
            chunks.append(text)
            sys.stdout.write("\r  …streaming greeting: " + text[:60])
            sys.stdout.flush()

        out = llm.structured_stream(model, system, user, SCHEMA,
                                    on_delta=on_delta, field="greeting",
                                    max_tokens=200)
        print()
    else:
        out = llm.structured(model, system, user, SCHEMA, max_tokens=200)

    print("RESULT:", out)
    print("OK ✅  provider/端点/tool-use 全通" if out.get("greeting") else "⚠️ 无 greeting 字段")


if __name__ == "__main__":
    main()
