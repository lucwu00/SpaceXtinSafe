"""Build single-file previews from dist/ + a backend snapshot.
python3 build_preview.py <snapshot.json> <artifact_out.html> <standalone_out.html>"""
import glob, json, re, sys, datetime
snap_path, art_out, std_out = sys.argv[1:4]
snap = json.load(open(snap_path))
html = open("dist/index.html").read()
css = "".join(open(f).read() for f in glob.glob("dist/assets/*.css"))
js = "".join(open(f).read() for f in glob.glob("dist/assets/*.js"))
meta = {"recorded": datetime.date.today().isoformat(), "responses": len(snap)}
esc = lambda s: s.replace("</", "<\\/")
fonts = re.findall(r'<link[^>]+fonts[^>]+>', html)
body = (f'<div id="root"></div>\n<script>window.__SXS_META__={json.dumps(meta)};window.__SXS_SNAPSHOT__={esc(json.dumps(snap, separators=(",", ":")))};</script>\n'
        f'<script type="module">{esc(js)}</script>')
head = f'<title>SpaceXtinsafe</title>\n{"".join(fonts)}\n<style>{css}</style>'
open(art_out, "w").write(head + "\n" + body)
open(std_out, "w").write(f'<!doctype html>\n<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">{head}</head><body>{body}</body></html>')
print("ok", len(open(art_out).read()) // 1024, "KB")
