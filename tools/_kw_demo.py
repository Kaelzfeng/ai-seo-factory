import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from lib import keyword_scout as k

seed = 'PU leather'
print('== seed ==', seed)
gp = k.grounded_plan(seed, max_pages=7)
print('== grounded_plan keys ==', list(gp.keys()))
print('== pool size (抓到多少真实搜索词) ==', gp.get('pool_size'))

print('\n== 规划出的页(按意图把真实词聚成主题簇) ==')
for p in gp.get('plan', []):
    print(f"  [{p.get('type')}] {p.get('target_keyword')}  ->  {p.get('title')}")

q = gp.get('questions')
print('\n== 买家真问题(问题前缀轮抓的) 样本 ==')
if isinstance(q, dict):
    for kk, vv in list(q.items())[:10]:
        s = vv if isinstance(vv, (str, int, float)) else json.dumps(vv, ensure_ascii=False)
        print('  -', kk, ':', str(s)[:140])
elif isinstance(q, list):
    for item in q[:14]:
        print('  -', item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)[:140])

hl = gp.get('harvest_log')
if hl:
    print('\n== 抓取来源样本(每条查询打到哪、返回了啥) ==')
    items = hl if isinstance(hl, list) else list(hl.items())
    for it in items[:6]:
        print('  ', json.dumps(it, ensure_ascii=False)[:180])

intents = gp.get('intents')
if intents:
    print('\n== 意图分布 ==', json.dumps(intents, ensure_ascii=False)[:300])
