"""测试 harness:复用 run.py 真实路径,调 DeepSeek 生成一页 + 确定性打分,dump 供人评审。
用法: python tools/_llm_test.py [slug]   默认 pu-leather-vs-genuine-leather
"""
import sys, json, pathlib, os, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import yaml
from dotenv import load_dotenv
load_dotenv()
from lib import llm, quality

PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "meta_description": {"type": "string"},
        "html": {"type": "string"},
        "image_query": {"type": "string"},
    },
    "required": ["title", "meta_description", "html", "image_query"],
}

CFG = yaml.safe_load(pathlib.Path('industries/pu-leather.yaml').read_text(encoding='utf-8'))
site = os.getenv('WP_SITE') or 'https://demoleather.com'
pages = [dict(p) for p in CFG['pages']]
for p in pages:
    p['url'] = f"{site}/{p['slug']}/"
pillar_url = next((p['url'] for p in pages if p.get('type') == 'pillar'), None)
for p in pages:
    p['pillar_url'] = pillar_url

target = sys.argv[1] if len(sys.argv) > 1 else 'pu-leather-vs-genuine-leather'
page = next(p for p in pages if p['slug'] == target)
related = [{'title': q['title'], 'url': q['url'], 'type': q['type']}
           for q in pages if q['slug'] != page['slug']]
page['related'] = related

writer_sys = llm.load_skill('seo-content')
profile = (f"Industry: {CFG.get('name','')}\nTone: {CFG.get('tone','')}\n"
           f"Audience: {CFG.get('audience','')}\nTerminology: {CFG.get('terminology','')}\n"
           f"E-E-A-T: {CFG.get('eeat','')}\nLanguage: {CFG.get('language','English')}")
writer_user = (f"CURRENT DATE: 2026-06-06 — use this exact date for any "
               f"'Data last updated' line and date ranges; do not invent a date.\n\n"
               f"PAGE TO WRITE:\n{page}\n\nINDUSTRY PROFILE:\n{profile}\n\n"
               f"RELATED PAGES (link to the pillar and 2-3 of these naturally, "
               f"using their exact url):\n{related}\n\n"
               f"Write a complete, original SEO page as WordPress HTML.")

model = os.getenv('WRITER_MODEL') or llm.default_model('writer')
print(f"provider={llm._provider()}  writer_model={model}  page={target}  type={page['type']}")
print("calling DeepSeek …")
content = llm.structured(model, writer_sys, writer_user, PAGE_SCHEMA, max_tokens=8000)

def wc(html):
    return len(re.sub('<[^>]+>', ' ', html).split())

q = quality.score_page(page, content, CFG)
print("\n===== DEEPSEEK OUTPUT (元数据) =====")
print(f"title  ({len(content['title'])} chars): {content['title']}")
print(f"meta   ({len(content['meta_description'])} chars): {content['meta_description']}")
print(f"body word count: {wc(content['html'])}")
print(f"image_query: {content['image_query']}")
print("\n===== QUALITY (确定性 quality.py) =====")
print(f"score: {q.get('score')}/100   passed: {q.get('passed')}   (阈值 {quality.PASS_THRESHOLD})")
for iss in q.get('issues', []):
    print("  -", iss)
bd = q.get('breakdown') or {}
print("breakdown:", json.dumps(bd, ensure_ascii=False)[:800])

out = pathlib.Path('output/_llm_test')
out.mkdir(parents=True, exist_ok=True)
(out / f'{target}.json').write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding='utf-8')
(out / f'{target}.html').write_text(content['html'], encoding='utf-8')
print(f"\nwrote {out / (target + '.html')}  和  {target}.json")
