"""Record real backend responses into a static snapshot for the single-file preview.
Keys use the same normalisation as frontend/src/api.ts (staticKey). Usage: python -m scripts.snapshot <out.json>"""
import base64, json, os, sys, itertools, tempfile, shutil
from urllib.parse import urlencode
# record against a fresh copy of the seeded database so preview data = the three templates
os.environ["SPACEXI_DB"] = os.path.join(tempfile.mkdtemp(), "snap.sqlite3")
from fastapi.testclient import TestClient
from app.main import app
from app.core import data, retrieval

c = TestClient(app)
SNAP = {}


def r1(v):
    """Round to 0.1 and drop a trailing .0 so keys match JavaScript's number formatting."""
    if v in (None, ""):
        return None
    x = round(float(v), 1)
    return int(x) if x.is_integer() else x


def norm_body(path, b):
    b = b or {}
    if path in ("/api/evidence/rank", "/api/insights"):
        return {"material_id": b.get("material_id") or None, "o2_pct": r1(b.get("o2_pct")), "pressure_kpa": r1(b.get("pressure_kpa")), "gravity": b.get("gravity") or None}
    if path == "/api/predict":
        return {k: (r1(b.get(k)) if k in ("o2_pct", "pressure_kpa", "d0_mm") else (b.get(k) or None)) for k in ("material_form", "fuel", "o2_pct", "pressure_kpa", "d0_mm", "diluent", "gravity")}
    if path == "/api/interactions":
        return {"material_ids": sorted(b.get("material_ids", []))}
    if path == "/api/copilot":
        return {"question": (b.get("question") or "").replace("​", "").strip()}
    if path == "/api/incidents/replay":
        return {"spacecraft_id": b.get("spacecraft_id"), "compartment_id": b.get("compartment_id"), "type": b.get("type"), "phase": b.get("phase") or "orbital operations"}
    if path == "/api/report":
        return {"spacecraft_id": b.get("spacecraft_id")}
    return b


def key(method, path, params=None, body=None):
    p = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    if path.startswith("/api/materials/"):
        p = {k: r1(v) if k != "gravity" else v for k, v in p.items() if k in ("o2_pct", "pressure_kpa", "gravity")}
    if path == "/api/search":
        p = {k: v for k, v in p.items() if k in ("q", "mode")}
    q = "&".join(f"{k}={p[k]}" for k in sorted(p))
    k = f"{method} {path}" + (f"?{q}" if q else "")
    if method == "POST":
        k += " " + json.dumps(norm_body(path, body), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return k


def get(path, params=None, store=True, transform=None):
    r = c.get(path, params=params or None)
    if r.status_code == 200 and store:
        v = r.json(); SNAP[key("GET", path, params)] = transform(v) if transform else v
        return v


def post(path, body, transform=None):
    r = c.post(path, json=body)
    if r.status_code == 200:
        v = r.json() if "json" in r.headers.get("content-type", "") else {"__pdf_b64": base64.b64encode(r.content).decode()}
        SNAP[key("POST", path, None, body)] = transform(v) if transform else v
        return v


def slim_pred(v):
    if v.get("model"):
        v["model"] = {k: v["model"][k] for k in ("model_id", "status", "failed_criteria", "n_observations", "n_sessions")}
    return v


retrieval.status()
for p in ["/api/status", "/api/templates", "/api/spacecraft", "/api/materials", "/api/evidence", "/api/sources", "/api/models", "/api/audit", "/api/gaps", "/api/graph/stats", "/api/evaluation",
          "/api/investigations", "/api/datasets", "/api/nasa-usage"]:
    get(p)
scs = c.get("/api/spacecraft").json()
mats = list(data.materials())
atms = [s["atmosphere"] for s in scs] + [{"o2_pct": 34, "pressure_kpa": 56.5, "gravity": "partial gravity"}]
centres = ["MAT-PMMA", "MAT-SIBAL", "MAT-NOMEX", "MAT-METHANOL", "INV:Saffire-II", "INV:FLEX"] + mats
for s in scs:
    get(f"/api/spacecraft/{s['id']}/screen"); get("/api/gaps", {"spacecraft_id": s["id"]}); get(f"/api/incidents/{s['id']}")
    centres.append(s["id"])
    for comp in s["compartments"]:
        get(f"/api/spacecraft/{s['id']}/screen", {"compartment_id": comp["id"]})
        centres.append(f"{s['id']}/{comp['id']}")
        for o in comp["objects"]:
            centres.append(f"{s['id']}/{comp['id']}/{o['id']}")
        for t in ("smoke", "electrical", "oxygen", "propulsion", "external_heating"):
            post("/api/incidents/replay", {"spacecraft_id": s["id"], "compartment_id": comp["id"], "type": t})
        for ph in ("pre-launch", "ascent", "deep-space transit", "lunar surface", "martian surface", "descent and landing"):
            post("/api/incidents/replay", {"spacecraft_id": s["id"], "compartment_id": comp["id"], "type": "smoke", "phase": ph})
    post("/api/report", {"spacecraft_id": s["id"]})
    get(f"/api/procedures/{s['id']}")
    for dim in ("gravity", "oxygen", "pressure", "airflow", "form", "material", "compartment"):
        get(f"/api/gaps/{dim}", {"spacecraft_id": s["id"]})
for ce in dict.fromkeys(centres):
    get("/api/graph/trace", {"node": ce})
    big = not ce.startswith("MAT-")  # keep the preview under the 16 MB artifact limit: materials get depths 1-3 only
    for d in ((1, 2, 3, 4) if big else (1, 2, 3)):
        get("/api/graph/subgraph", {"center": ce, "depth": d})
    for dom in (("spacecraft", "science") if big else ()):
        get("/api/graph/subgraph", {"center": ce, "depth": 3, "domain": dom})
for m in mats:
    get(f"/api/materials/{m}")
    for a in atms:
        get(f"/api/materials/{m}", {"o2_pct": a["o2_pct"], "pressure_kpa": a["pressure_kpa"], "gravity": a["gravity"]})
for m in [None] + mats:
    for a in atms:
        b = {"material_id": m, "o2_pct": a["o2_pct"], "pressure_kpa": a["pressure_kpa"], "gravity": a["gravity"]}
        post("/api/evidence/rank", b, lambda v: [{"id": e["id"], "applicability": e["applicability"]} for e in v]); post("/api/insights", b)
# conditions the guided demo passes through (cabin O2 raised to 30%, Saffire PMMA, methanol)
for m in (None, "MAT-NOMEX", "MAT-PU", "MAT-PMMA", "MAT-METHANOL"):
    for o2 in (21, 22.1, 30):
        bd = {"material_id": m, "o2_pct": o2, "pressure_kpa": 101.3, "gravity": "microgravity"}
        post("/api/evidence/rank", bd, lambda v: [{"id": e["id"], "applicability": e["applicability"]} for e in v]); post("/api/insights", bd)
        if m: get(f"/api/materials/{m}", {"o2_pct": o2, "pressure_kpa": 101.3, "gravity": "microgravity"})
for fuel in ("methanol", "n-heptane"):
    for o2 in [10] + list(range(12, 35)) + [40]:
        for p in (70.9, 101.3):
            for d0 in (1.5, 1.7, 2.0, 2.5, 3.0, 3.5, 4.0):
                post("/api/predict", {"material_form": "liquid droplet", "fuel": fuel, "o2_pct": o2, "pressure_kpa": p, "d0_mm": d0, "diluent": "nitrogen", "gravity": "microgravity"}, slim_pred)
for a in atms:  # default predictions the screens/insights would trigger for non-droplet materials
    for fuel, form in (("other", None), ("methanol", "liquid droplet"), ("n-heptane", "liquid droplet")):
        post("/api/predict", {"material_form": form, "fuel": fuel, "o2_pct": a["o2_pct"], "pressure_kpa": a["pressure_kpa"], "d0_mm": None, "diluent": "nitrogen", "gravity": a["gravity"]}, slim_pred)
for dim in ("gravity", "oxygen", "pressure", "airflow", "form", "material"):
    get(f"/api/gaps/{dim}")
CC_ROWS = [{"label": "Orbital cabin air", "o2_pct": 21, "pressure_kpa": 101.3, "gravity": "microgravity", "flow_cm_s": 15, "diluent": "nitrogen"},
           {"label": "Exploration atmosphere, lunar", "o2_pct": 34, "pressure_kpa": 56.5, "gravity": "partial gravity", "flow_cm_s": 10, "diluent": "nitrogen"}]
for m in mats:
    for extra in ({"d0_mm": 2.5}, {}):
        post("/api/compare/conditions", {"material_id": m, **extra, "scenarios": CC_ROWS})
for x, y in itertools.combinations(mats, 2):
    post("/api/interactions", {"material_ids": [x, y]})
ids = [s["id"] for s in scs]
for n in (2, 3):
    for combo in itertools.permutations(ids, n):
        post("/api/compare", {"spacecraft_ids": list(combo)})
qs = [q["q"] for q in json.load(open("eval/retrieval_questions.json"))["questions"]]
demo = ["What NASA evidence applies to the materials in the Crew quarters of the Orbital Research Module?", "methanol droplet burning rate", "Nomex ignition", "lunar gravity flammability", "smoke detection"]
for q in qs + demo:
    get("/api/search", {"q": q, "mode": "auto"})
for q in demo:
    for m in ("keyword", "semantic", "hybrid", "hybrid+graph", "keyword+graph"):
        get("/api/search", {"q": q, "mode": m})
cq = [x["q"] for x in json.load(open("eval/copilot_cases.json"))["cases"]] + ["What NASA evidence applies to the Crew quarters?", "What does Saffire show about Nomex?", "Why is lunar gravity a concern?"] + demo
for q in cq:
    post("/api/copilot", {"question": q})
json.dump(SNAP, open(sys.argv[1], "w"), separators=(",", ":"))
print(len(SNAP), "responses", os.path.getsize(sys.argv[1]) // 1024, "KB")
