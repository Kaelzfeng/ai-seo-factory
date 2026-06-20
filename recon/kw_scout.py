# -*- coding: utf-8 -*-
"""关键词侦察:实地打真实免费数据源(自动补全),看能拿到什么。只读、轻量、礼貌。
不是产品代码,是设计前的探路。运行:python recon/kw_scout.py"""
import sys, json, time, urllib.parse
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SEEDS = ["PU leather", "synthetic leather", "microfiber leather"]
PREFIXES = ["", "for", "vs", "best", "wholesale", "how to"]


def google_suggest(q, hl="en", gl="us"):
    url = "https://suggestqueries.google.com/complete/search"
    r = requests.get(url, params={"client": "firefox", "q": q, "hl": hl, "gl": gl},
                     headers=UA, timeout=10)
    r.raise_for_status()
    return r.json()[1]


def bing_suggest(q, mkt="en-US"):
    url = "https://api.bing.com/osjson.aspx"
    r = requests.get(url, params={"query": q, "mkt": mkt}, headers=UA, timeout=10)
    r.raise_for_status()
    return r.json()[1]


def google_related_paa(q, hl="en", gl="us"):
    """从 SERP HTML 里粗暴抓 People-Also-Ask / 相关搜索(探路用,看可行性)。"""
    url = "https://www.google.com/search"
    r = requests.get(url, params={"q": q, "hl": hl, "gl": gl, "num": "10"},
                     headers=UA, timeout=12)
    status = r.status_code
    text = r.text or ""
    # 极粗略信号:有没有 "People also ask" / "Related searches"
    has_paa = "People also ask" in text
    has_rel = "Related searches" in text or "Related searches" in text
    blocked = ("detected unusual traffic" in text.lower()
               or "/sorry/" in r.url or status == 429)
    return {"status": status, "bytes": len(text), "has_paa": has_paa,
            "has_related": has_rel, "looks_blocked": blocked}


def main():
    out = {"google_autocomplete": {}, "bing_autocomplete": {}, "google_serp_probe": {}}

    for seed in SEEDS:
        for pre in PREFIXES:
            q = (seed + " " + pre).strip() if pre else seed
            try:
                sug = google_suggest(q)
            except Exception as e:
                sug = ["<error: %s>" % e]
            out["google_autocomplete"][q] = sug
            time.sleep(0.4)

    for seed in SEEDS:
        try:
            out["bing_autocomplete"][seed] = bing_suggest(seed)
        except Exception as e:
            out["bing_autocomplete"][seed] = ["<error: %s>" % e]
        time.sleep(0.4)

    # 只探 1 个 SERP,判断 PAA/相关搜索可行性 + 是否被挡
    try:
        out["google_serp_probe"]["PU leather"] = google_related_paa("PU leather")
    except Exception as e:
        out["google_serp_probe"]["PU leather"] = {"error": str(e)}

    # 汇总:去重后的关键词池大小
    pool = set()
    for lst in out["google_autocomplete"].values():
        for k in lst:
            if not k.startswith("<error"):
                pool.add(k.lower())
    for lst in out["bing_autocomplete"].values():
        for k in lst:
            if not k.startswith("<error"):
                pool.add(k.lower())
    out["_summary"] = {"unique_keywords": len(pool),
                       "google_queries": len(out["google_autocomplete"]),
                       "bing_queries": len(out["bing_autocomplete"])}

    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
