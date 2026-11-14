"""Build app/data/curated/evidence.json from evidence_draft.json.
Every quote must appear verbatim (whitespace-normalised) in the source text; the PDF page is located automatically.
Quotes that are not found are rejected (the script exits non-zero)."""
import json, re, subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, '..', 'app', 'data')
norm = lambda s: re.sub(r'\s+', ' ', s.replace('’', "'").replace('—', '-').replace('–', '-')).strip()
src = {s['id']: s for s in json.load(open(f'{D}/curated/sources.json'))}
layout = json.load(open(f'{D}/source_text/20180005168.layout.json')) if os.path.exists(f'{D}/source_text/20180005168.layout.json') else None
out, bad = [], []
for e in json.load(open(f'{D}/curated/evidence_draft.json')):
    s = src[e['source_id']]; pages = layout if e.get('layout_quote') else json.load(open(f"{D}/source_text/{s['text_file'] or 'mir.pages.json'}"))
    q = norm(e['quote']); page = next((i + 1 for i, p in enumerate(pages) if q in norm(p)), None)
    if page is None: bad.append(e['id']); continue
    e['location'] = f"{s['identifier']}, PDF p.{page}" if s['text_file'] else s['title']
    e['page'] = page if s['text_file'] else None; e['verified'] = 'quote found verbatim in source text'
    e.pop('layout_quote', None); out.append(e)
json.dump(out, open(f'{D}/curated/evidence.json', 'w'), indent=1)
print(f'{len(out)} verified, rejected: {bad}'); sys.exit(1 if bad else 0)
