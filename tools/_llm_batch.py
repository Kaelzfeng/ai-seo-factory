"""批量测试:并发调 DeepSeek 生成多页型 + 确定性打分 + 程序后处理。dump 供 Workflow 对抗审。
用法: python tools/_llm_batch.py [slug ...]
"""
import sys, json, pathlib, os, re
import concurrent.futures as cf
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import yaml
from dotenv import load_dotenv
load_dotenv()
from lib import llm, quality

DATE = '2026-06-06'
PAGE_SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"}, "meta_description": {"type": "string"},
    "html": {"type": "string"}, "image_query": {"type": "string"}},
    "required": ["title", "meta_description", "html", "image_query"]}

CFG = yaml.safe_load(pathlib.Path('industries/pu-leather.yaml').read_text(encoding='utf-8'))
site = os.getenv('WP_SITE') or 'https://demoleather.com'
PAGES = [dict(p) for p in CFG['pages']]
for p in PAGES:
    p['url'] = f"{site}/{p['slug']}/"
PILLAR = next((p['url'] for p in PAGES if p.get('type') == 'pillar'), None)
for p in PAGES:
    p['pillar_url'] = PILLAR

writer_sys = llm.load_skill('seo-content')
profile = (f"Industry: {CFG.get('name','')}\nTone: {CFG.get('tone','')}\n"
           f"Audience: {CFG.get('audience','')}\nTerminology: {CFG.get('terminology','')}\n"
           f"E-E-A-T: {CFG.get('eeat','')}\nLanguage: {CFG.get('language','English')}")
model = os.getenv('WRITER_MODEL') or llm.default_model('writer')

def wc(html):
    return len(re.sub('<[^>]+>', ' ', html).split())

def postfix(content, page):
    c = dict(content)
    meta = c['meta_description']
    if len(meta) > 160:
        cut = meta[:160]
        sent = re.search(r'^.*[.!?](?=\s|$)', cut)
        meta = sent.group(0).strip() if (sent and len(sent.group(0)) >= 120) else cut[:cut.rfind(' ')].rstrip(' ,;:-—')
        c['meta_description'] = meta
    pillar = page['pillar_url'].rstrip('/')
    sib = {r['url'].rstrip('/') for r in page['related']}
    st = {'n': 0}
    def repl(m):
        href, text = m.group('href').rstrip('/'), m.group('text')
        if href == pillar:
            return m.group(0)
        if href in sib:
            st['n'] += 1
            return m.group(0) if st['n'] <= 3 else text
        return m.group(0)
    c['html'] = re.sub(r'<a\s+href="(?P<href>[^"]+)"[^>]*>(?P<text>.*?)</a>', repl, c['html'], flags=re.S)
    return c

def run_one(slug):
    page = next(p for p in PAGES if p['slug'] == slug)
    page = dict(page)
    page['related'] = [{'title': q['title'], 'url': q['url'], 'type': q['type']}
                       for q in PAGES if q['slug'] != slug]
    writer_user = (f"CURRENT DATE: {DATE} — use this exact date for any 'Data last updated' line.\n\n"
                   f"PAGE TO WRITE:\n{page}\n\nINDUSTRY PROFILE:\n{profile}\n\n"
                   f"RELATED PAGES (link to the pillar and 2-3 of these naturally, using their exact url):\n"
                   f"{page['related']}\n\nWrite a complete, original SEO page as WordPress HTML.")
    try:
        content = llm.structured(model, writer_sys, writer_user, PAGE_SCHEMA, max_tokens=8000)
    except Exception as e:
        return {'slug': slug, 'type': page['type'], 'error': str(e)[:200]}
    before = quality.score_page(page, content, CFG)
    fixed = postfix(content, page)
    after = quality.score_page(page, fixed, CFG)
    out = pathlib.Path('output/_llm_test')
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{slug}.batch.json').write_text(json.dumps(fixed, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'slug': slug, 'type': page['type'], 'title': fixed['title'],
            'meta_before': len(content['meta_description']), 'meta_after': len(fixed['meta_description']),
            'words': wc(fixed['html']),
            'score_before': before.get('score'), 'issues_before': before.get('issues'),
            'score_after': after.get('score'), 'issues_after': after.get('issues')}

SLUGS = sys.argv[1:] or ['pu-leather-guide', 'is-pu-leather-durable-waterproof',
                         'microfiber-pu-leather-bags', 'pu-leather-for-automotive']
print(f"provider={llm._provider()} model={model}  生成 {len(SLUGS)} 页(并发)…")
rows = []
with cf.ThreadPoolExecutor(max_workers=4) as ex:
    for r in ex.map(run_one, SLUGS):
        rows.append(r)
        if 'error' in r:
            print(f"  ✗ {r['slug']} ({r['type']}): {r['error']}")
        else:
            print(f"  ✓ {r['slug']:38s} [{r['type']:11s}] words={r['words']:5d}  "
                  f"score {r['score_before']}→{r['score_after']}  meta {r['meta_before']}→{r['meta_after']}")
            for iss in (r['issues_after'] or []):
                print(f"        ⚠ 残留: {iss}")

pathlib.Path('output/_llm_test/batch_summary.json').write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
print("\nwrote output/_llm_test/batch_summary.json")
