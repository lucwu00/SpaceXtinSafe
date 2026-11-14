"""Dynamic behaviour with inputs that were never pre-recorded, shared-state propagation, and service-failure fallbacks."""
import os, tempfile, json
os.environ.setdefault("SPACEXI_DB", os.path.join(tempfile.mkdtemp(), "dyn.sqlite3"))
os.environ.setdefault("SPACEXI_SEMANTIC", "0")
from fastapi.testclient import TestClient
from app.main import app
from app.core import graph, copilot

c = TestClient(app)


def _new(name="Dyn Test"):
    return c.post("/api/spacecraft", json={"mode": "customise", "template_id": "TPL-ORBITAL", "name": name}).json()


def test_replacing_acrylic_with_titanium_propagates_everywhere():
    sc = _new("Titanium swap")
    lab = next(x for x in sc["compartments"] if x["id"] == "C-LAB")
    win = next(k for o in lab["objects"] for k in o["components"] if k["material_id"] == "MAT-PMMA")
    win["material_id"], win["form"] = "MAT-TI64", "bulk"
    sc2 = c.put(f"/api/spacecraft/{sc['id']}", json=sc).json()
    rows = c.get(f"/api/spacecraft/{sc['id']}/screen").json()["rows"]                 # twin + inventory source
    r = next(x for x in rows if x["component_id"] == win["id"])
    assert r["material_id"] == "MAT-TI64" and r["status"].startswith("No NASA")       # evidence recalculated
    sub = c.get("/api/graph/subgraph", params={"center": f"{sc['id']}/C-LAB", "depth": 3}).json()  # graph updated
    assert any(n["id"] == "MAT-TI64" for n in sub["nodes"])
    gaps = c.get(f"/api/gaps/gravity?spacecraft_id={sc['id']}").json()            # gaps updated
    assert any(x["material_id"] == "MAT-TI64" for x in gaps["cells"])
    cmp = c.post("/api/compare", json={"spacecraft_ids": [sc["id"], "SC-ORBITAL"]}).json()["configurations"]
    assert cmp[0]["materials"] != cmp[1]["materials"]                                # comparison uses new config
    inc = c.post("/api/incidents/replay", json={"spacecraft_id": sc["id"], "compartment_id": "C-LAB", "type": "smoke"}).json()
    assert inc["spacecraft"] == "Titanium swap"                                      # incident uses manifest
    pdf = c.post("/api/report", json={"spacecraft_id": sc["id"]})
    assert pdf.status_code == 200 and b"Titanium" in pdf.content or pdf.content[:5] == b"%PDF-"


def test_build_from_scratch_with_custom_material_and_new_prediction():
    sc = c.post("/api/spacecraft", json={"mode": "scratch", "name": "Scratch craft"}).json()
    m = c.post("/api/materials", json={"name": "Magnesium alloy AZ31B test plate", "composition": "Mg-3Al-1Zn", "grade": "AZ31B", "form": "sheet", "category": "Structural metals"}).json()
    assert m["material"]["user_defined"] and m["material"]["id"].startswith("UMAT-")
    assert m["status"]["status"] != "Verified NASA combustion evidence"                # no evidence invented
    sc["compartments"] = [{"id": "C-NEW", "name": "Workshop", "type": "engineering", "volume_m3": 9, "objects": [
        {"id": "O-NEW", "name": "Test fixture", "category": "equipment", "components": [
            {"id": "K-NEW", "name": "Plate", "material_id": m["material"]["id"], "form": "sheet", "thickness_mm": 2, "mass_g": 150}]}]}]
    sc["atmosphere"]["o2_pct"] = 26.5
    out = c.put(f"/api/spacecraft/{sc['id']}", json=sc)
    assert out.status_code == 200
    tr = c.get("/api/graph/trace", params={"node": f"{sc['id']}/C-NEW/O-NEW"}).json()
    assert tr == []                                                                   # no NASA path: a gap, not a fabricated link
    p = c.post("/api/predict", json={"material_form": "liquid droplet", "fuel": "methanol", "o2_pct": 19.3, "pressure_kpa": 100.9, "d0_mm": 2.83, "diluent": "nitrogen", "gravity": "microgravity"}).json()
    assert p["outcome"] in ("Model-supported estimate", "Exploratory estimate") and p["estimate"] is not None
    bad = c.post("/api/predict", json={"material_form": "sheet", "fuel": "other", "o2_pct": 26.5, "pressure_kpa": 101.3, "d0_mm": 2, "diluent": "nitrogen", "gravity": "microgravity"}).json()
    assert bad["outcome"] == "Unavailable" and bad["estimate"] is None


def test_arbitrary_question_and_interaction_and_condition_compare():
    r = c.post("/api/copilot", json={"question": "How did the cotton-fiberglass flame behave against the airflow in the large Saffire tests?"}).json()
    assert r["mode"] in ("evidence-retrieval", "claude") and r["claims"]
    a = c.post("/api/copilot", json={"question": "What is the ignition temperature of FR-4 circuit boards in lunar gravity?"}).json()
    assert a["mode"] in ("no-evidence", "abstain") or not a["claims"]
    it = c.post("/api/interactions", json={"material_ids": ["MAT-NOMEX", "MAT-PMMA"]}).json()
    assert it["status"] == "Documented interaction"
    cc = c.post("/api/compare/conditions", json={"material_id": "MAT-SIBAL", "scenarios": [{"o2_pct": 21, "pressure_kpa": 101.3, "gravity": "microgravity", "flow_cm_s": 20},
                                                                                       {"o2_pct": 34, "pressure_kpa": 56.5, "gravity": "partial gravity", "flow_cm_s": 10}]}).json()
    assert len(cc["scenarios"]) == 2 and cc["scenarios"][1]["o2_partial_pressure_kpa"] == 19.2


def test_neo4j_failure_is_reported_not_faked(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://does-not-exist.invalid")
    monkeypatch.setenv("NEO4J_PASSWORD", "x")
    graph.NEO["configured"] = True
    s = graph.neo4j_sync()
    assert s["connected"] is False and s["error"]
    assert "fallback" in s["mode"].lower() or "not connected" in s["mode"].lower()
    assert c.get("/api/graph/stats").json()["nodes"] > 0                             # in-memory graph still works
    graph.NEO["configured"] = False


def test_claude_failure_falls_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-invalid-test-key")
    r = c.post("/api/copilot", json={"question": "What did Saffire-II show about Nomex?"}).json()
    assert r["mode"] == "evidence-retrieval" and "not active" in (r.get("limitations") or "")
    assert copilot.STATE["verified_live"] is False
