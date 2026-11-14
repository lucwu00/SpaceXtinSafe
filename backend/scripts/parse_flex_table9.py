"""Parse NASA/TP-2015-216046 Table IX (pdftotext -layout) into data/derived/flex_tp_table9.json.
Run with the path to the TP PDF. Rows that do not match the expected column pattern are reported, not guessed."""
import re, json, subprocess, sys, os
pdf = sys.argv[1]; out = os.path.join(os.path.dirname(__file__), '..', 'app', 'data', 'derived', 'flex_tp_table9.json')
num = r'(~?-?\d*\.?\d+|–|-)'
row = re.compile(r'^\s*FLEX[–-](\d+)\s+(\S+)\s+(\d+/\d+/\d+)\s+(\S+)\s+(Methanol|Heptane)\s+' + r'\s+'.join([num] * 9) + r'\s+(\w[\w ]*?)\s*$')
rows, unparsed = [], []
for p in range(26, 40):
    t = subprocess.run(['pdftotext', '-layout', '-f', str(p), '-l', str(p), pdf, '-'], capture_output=True, text=True).stdout
    for line in t.splitlines():
        if not re.match(r'^\s*FLEX[–-]\d+', line): continue
        m = row.match(line)
        if not m: unparsed.append({'page': p, 'line': line.strip()}); continue
        g = list(m.groups()); f = lambda v: None if v in ('–', '-') else float(v.lstrip('~'))
        rows.append({'test': int(g[0]), 'identifier': g[1], 'date': g[2], 'gmt': g[3], 'fuel': g[4], 'pressure_mmHg': f(g[5]), 'o2': f(g[6]), 'n2': f(g[7]), 'co2': f(g[8]), 'he': f(g[9]), 'd0_mm': f(g[10]), 'ext_d_mm': f(g[11]), 'k_mm2_s': f(g[12]), 'burn_time_s': f(g[13]), 'end': g[14].strip(), 'pdf_page': p})
json.dump({'source': 'NASA/TP-2015-216046 Table IX', 'rows': rows, 'unparsed_lines': unparsed}, open(out, 'w'), indent=1)
print(len(rows), 'rows parsed;', len(unparsed), 'lines not parsed')
