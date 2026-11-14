import os, tempfile, json
os.environ.setdefault("SPACEXI_DB", os.path.join(tempfile.mkdtemp(), "t.sqlite3"))
os.environ.setdefault("SPACEXI_SEMANTIC", "0")
from fastapi.testclient import TestClient
from app.main import app
from app.core import data, models, audit, analysis, copilot, retrieval, graph, store

c = TestClient(app)


def test_raw_files_match_acquisition_manifest():
    assert all(v["manifest_match"] for v in data.provenance().values())


def test_every_evidence_quote_verified():
    ev = data.evidence()
    assert len(ev) >= 40 and all(e["verified"] and e.get("location") for e in ev)


def test_flex_unit_and_parameter_counts():
    for m in models.registry():
        assert m["n_parameters"] == 1 + len(m["features"])
        assert "mm^2/s" in m["target"]
    assert any(i["id"] == "AUD-FLEX-UNIT" for i in audit.run()["items"])


def test_confirmed_flex_discrepancy_excluded_from_models():
    ex = audit.excluded_flex_tests()
    assert 70 in ex
    for m in models.registry():
        assert not any("Test #70 " in o["record"] for o in m["observed"])


def test_eligibility_outcomes():
    base = dict(material_form="liquid droplet", fuel="methanol", o2_pct=21, pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="microgravity")
    assert models.assess(base)["outcome"] == "Model-supported estimate"
    assert models.assess({**base, "d0_mm": None})["outcome"] == "Unavailable"
    assert models.assess({**base, "o2_pct": 40})["outcome"] == "Unavailable"
    assert models.assess({**base, "diluent": "carbon dioxide"})["outcome"] == "Unavailable"
    assert models.assess({**base, "o2_pct": 30, "d0_mm": 1.7})["outcome"] != "Model-supported estimate"


def test_saffire_audit_conflicts_present():
    ids = {i["id"]: i for i in audit.run()["items"]}
    assert ids["AUD-SAFFIREII-2-6-air-flow-velocity"]["status"] == "Confirmed discrepancy"
    assert ids["AUD-SAFFIREIII-S1-air-flow-velocity"]["status"] == "Confirmed discrepancy"
    assert ids["AUD-SAFFIREII-2-6-material"]["status"] == "Missing information"


def test_graph_traversal_object_to_sources():
    t = graph.trace("SC-ORBITAL/C-CREW/O-BAG")
    assert t and all(p["path"][-1]["label"] == "Source" for p in t)
    assert {"MAT-NOMEX", "MAT-PU"} <= {p["material"] for p in t}


def test_keyword_plus_graph_reaches_findings_without_semantic():
    r = retrieval.search("Which findings are relevant to the Sleeping bag in the Orbital Research Module?", "auto")
    assert r["available"] and "EV-SAF-08" in [x["id"] for x in r["results"]]


def test_boundary_questions_refused():
    for q in ["Is the crew quarters safe?", "Give me the fire risk percentage", "How should the crew extinguish the fire?"]:
        assert copilot.ask(q)["mode"] == "boundary"


def test_claim_check_drops_unsupported_numbers():
    ev = [e for e in data.evidence() if e["id"] == "EV-SAF-05"]
    kept, dropped = copilot.check_claims([{"text": "Spread was 2.1 mm/s", "citations": ["EV-SAF-05"]}, {"text": "Spread was 9.9 mm/s", "citations": ["EV-SAF-05"]}], ev)
    assert len(kept) == 1 and len(dropped) == 1


def test_spacecraft_crud_and_validation():
    sc = c.post("/api/spacecraft", json={"mode": "customise", "template_id": "TPL-CAPSULE", "name": "Mine"}).json()
    sc["atmosphere"]["o2_pct"] = 150
    assert c.put(f"/api/spacecraft/{sc['id']}", json=sc).status_code == 400
    sc["atmosphere"]["o2_pct"] = 30
    assert c.put(f"/api/spacecraft/{sc['id']}", json=sc).json()["atmosphere"]["o2_pct"] == 30
    assert c.delete(f"/api/spacecraft/{sc['id']}").status_code == 200


def test_screen_incident_report_endpoints():
    assert c.get("/api/spacecraft/SC-ORBITAL/screen").json()["rows"]
    r = c.post("/api/incidents/replay", json={"spacecraft_id": "SC-ORBITAL", "compartment_id": "C-ECLSS", "type": "oxygen"}).json()
    assert all(s["label"] == "SIMULATED" for s in r["timeline"]) and r["candidates"]
    pdf = c.post("/api/report", json={"spacecraft_id": "SC-ORBITAL"})
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"


def test_status_does_not_fake_neo4j():
    s = c.get("/api/status").json()
    if not os.environ.get("NEO4J_URI"):
        assert s["graph"]["connected"] is False


def test_user_defined_material_creates_gap_and_updates_all_modules():
    m = c.post("/api/materials", json={"name": "Experimental insulation X", "form": "blanket"}).json()
    assert m["status"]["status"].startswith("User-defined") and m["gap_created"]
    mid = m["material"]["id"]
    sc = c.post("/api/spacecraft", json={"mode": "scratch", "name": "Gap test"}).json()
    sc["compartments"] = [{"id": "C-A", "name": "Bay A", "type": "general", "volume_m3": 4, "objects": [{"id": "O-A", "name": "Box", "category": "x",
                           "components": [{"id": "K-A", "name": "Liner", "material_id": mid, "form": "blanket"}]}]}]
    assert c.put(f"/api/spacecraft/{sc['id']}", json=sc).status_code == 200
    rows = c.get(f"/api/spacecraft/{sc['id']}/screen").json()["rows"]
    assert rows[0]["status"].startswith("No NASA evidence")
    assert mid in graph.materials_for(f"{sc['id']}/C-A/O-A")
    cells = c.get(f"/api/gaps/gravity?spacecraft_id={sc['id']}").json()["cells"]
    assert all(x["count"] == 0 for x in cells)
    assert c.post("/api/report", json={"spacecraft_id": sc["id"]}).content[:5] == b"%PDF-"


def test_audit_tolerance_classification():
    items = {i["id"]: i for i in audit.run()["items"]}
    assert items["AUD-FLEX-070-ext_d_mm"]["classification"].startswith("Rounding")
    assert items["AUD-FLEX-070-k_mm2_s"]["classification"] == "Substantive discrepancy" and items["AUD-FLEX-070-k_mm2_s"]["model_exclusion"]
    assert not items["AUD-FLEX-070-ext_d_mm"]["model_exclusion"]


def test_abstention_rules():
    assert copilot.ask("Predict the burning rate of polycarbonate at 25% oxygen")["mode"] == "no-evidence"
    assert copilot.ask("What is the melting point of aluminium?")["mode"] == "no-evidence"
    assert copilot.ask("Should we shut off the ventilation fans?")["mode"] == "boundary"


def test_condition_comparison_reports_partial_pressure():
    r = c.post("/api/compare/conditions", json={"material_id": "MAT-SIBAL", "scenarios": [{"o2_pct": 21, "pressure_kpa": 101.3, "gravity": "microgravity"},
                                                                                           {"o2_pct": 34, "pressure_kpa": 56.5, "gravity": "partial gravity"}]}).json()
    assert [s["o2_partial_pressure_kpa"] for s in r["scenarios"]] == [21.3, 19.2]


def test_incident_non_cabin_and_phase():
    r = c.post("/api/incidents/replay", json={"spacecraft_id": "SC-ORBITAL", "type": "propulsion", "phase": "ascent"}).json()
    assert r["classification"] == "Not internal cabin combustion"
    r = c.post("/api/incidents/replay", json={"spacecraft_id": "SC-LUNAR", "compartment_id": "C-HAB", "type": "smoke", "phase": "lunar surface"}).json()
    assert r["phase_gravity"] == "partial gravity" and r["applicability_limitations"]


def test_coverage_statuses_computed():
    inv = {i["name"]: i for i in c.get("/api/investigations").json()}
    assert inv["FLEX"]["status"] == "Fully integrated original dataset"
    assert inv["CFI"]["status"] == "Dataset acquired but not yet analysed"
    assert all(d["integrity"].startswith("SHA-256 matches") for d in c.get("/api/datasets").json())
