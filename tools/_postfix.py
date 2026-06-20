"""纯程序后处理(不调 LLM):把"可数的确定量"卡住——sibling 内链 cap 到 3、meta 截进 160。
作用在已生成内容上,重打分对比 before/after。印证「确定→程序」。
"""
import sys, json, pathlib, os, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import yaml
from dotenv import load_dotenv
load_dotenv()
from lib import quality

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
page['related'] = [{'title': q['title'], 'url': q['url'], 'type': q['type']}
                   for q in pages if q['slug'] != page['slug']]

src = pathlib.Path('output/_llm_test') / f'{target}.json'
content = json.loads(src.read_text(encoding='utf-8'))

def sib_count(html):
    sib = {r['url'].rstrip('/') for r in page['related']}
    return sum(1 for m in re.finditer(r'<a\s+href="([^"]+)"', html)
               if m.group(1).rstrip('/') in sib)

def report(tag, c):
    q = quality.score_page(page, c, CFG)
    print(f"[{tag}] meta={len(c['meta_description'])}c  siblings={sib_count(c['html'])}  "
          f"score={q.get('score')}  issues={q.get('issues')}")
    return q

print("=== BEFORE (DeepSeek 原样) ===")
report('before', content)

# --- 确定性修复 1:meta 截进 <=160(优先句末,否则词末)---
meta = content['meta_description']
if len(meta) > 160:
    cut = meta[:160]
    sent = re.search(r'^.*[.!?](?=\s|$)', cut)
    if sent and len(sent.group(0)) >= 120:
        meta = sent.group(0).strip()
    else:
        meta = cut[:cut.rfind(' ')].rstrip(' ,;:-—')
    content['meta_description'] = meta

# --- 确定性修复 2:sibling 内链 cap 到 3(多的拆掉 <a> 只留锚文本;pillar/外链不动)---
pillar = page['pillar_url'].rstrip('/')
sib_urls = {r['url'].rstrip('/') for r in page['related']}
state = {'sib': 0}
def repl(m):
    href, text = m.group('href').rstrip('/'), m.group('text')
    if href == pillar:
        return m.group(0)            # pillar 保留
    if href in sib_urls:
        state['sib'] += 1
        return m.group(0) if state['sib'] <= 3 else text   # 超过 3 的拆链
    return m.group(0)                # 外链保留
content['html'] = re.sub(r'<a\s+href="(?P<href>[^"]+)"[^>]*>(?P<text>.*?)</a>',
                         repl, content['html'], flags=re.S)

print("\n=== AFTER (程序后处理) ===")
report('after', content)

out = pathlib.Path('output/_llm_test') / f'{target}.fixed.json'
out.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding='utf-8')
print("\nwrote", out)
