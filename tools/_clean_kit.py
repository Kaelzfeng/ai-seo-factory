import json, pathlib

raw = pathlib.Path('svg-kit-lucide.json').read_text(encoding='utf-8')
val = json.loads(raw)
obj = json.loads(val) if isinstance(val, str) else val

clean = {}
for k, v in obj.items():
    s = v.strip()
    if s.startswith('<!--'):
        s = s.split('-->', 1)[1].strip()
    clean[k] = s

out = pathlib.Path('output/design_options/svg-kit.json')
out.write_text(json.dumps(clean, ensure_ascii=False, indent=0), encoding='utf-8')
print('wrote', len(clean), 'icons ->', out)
