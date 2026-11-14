"""SpaceXtinsafe API."""
from __future__ import annotations
import json, os
from fastapi import FastAPI, HTTPException, Body, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from .core import data, models, audit, graph, retrieval, analysis, copilot, incidents, reports, store, coverage, router

app = FastAPI(title="SpaceXtinsafe API", version="1.1.0",
              description="NASA microgravity combustion evidence intelligence. Research prototype, not NASA-endorsed.")
origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _warm():
    """Load the semantic model and build the graph in the background so the first user request is not slow."""
    import threading
    def go():
        try:
            retrieval.status(); graph.build(); models.registry()  # warm the FLEX models so the first prediction is instant
            if os.environ.get("NEO4J_URI"):
                graph.neo4j_sync()  # verified connection status comes only from a real sync
            if router.api_key():
                router.check_models()  # verify configured model IDs exist for this key
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()
EVAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval", "results.json")


def _404(x, what="item"):
    if x is None:
        raise HTTPException(404, f"Unknown {what}")
    return x


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/version")
def version():
    return {"app": app.version, "evidence": len(data.evidence()), "models": [m["model_id"] for m in models.registry()]}


@app.get("/api/status")
def status():
    """Honest service status: what is actually active right now."""
    return {"semantic": {k: v for k, v in retrieval.SEM.items()}, "copilot": copilot.status(), "graph": graph.neo4j_status(),
            "data": {"evidence": len(data.evidence()), "sources": len(data.sources()), "flex_tests": len(data.flex_tests()),
                     "raw_files": data.provenance()}}


@app.post("/api/status/semantic/check")
def semantic_check():
    return retrieval.status()


@app.post("/api/status/neo4j/verify")
def neo4j_verify():
    """Proves retrieval runs in Neo4j: the GraphRAG expansion is computed by Cypher and compared with the in-memory graph."""
    return graph.neo4j_verify()


@app.post("/api/status/neo4j/sync")
def neo4j_sync():
    return graph.neo4j_sync()


# ---- library ----
@app.get("/api/materials")
def materials():
    return [{**m, "evidence_count": len(data.evidence_for_material(mid)), "evidence_status": data.material_status(mid)["status"]} for mid, m in data.materials().items()]


@app.post("/api/materials")
def material_new(body: dict = Body(...)):
    """User-defined material. Returns the record plus evidence found for it (library search and related materials)."""
    try:
        m = store.save_material(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    q = " ".join(x for x in [m["name"], m.get("scientific_name"), m.get("composition"), m.get("category")] if x)
    found = retrieval.search(q, "auto", k=5)
    return {"material": m, "status": data.material_status(m["id"]), "library_search": found["results"], "library_search_note":
            "Retrieved by text similarity only; these findings are about other materials unless they name this one. Applicability is not established.",
            "gap_created": data.material_status(m["id"])["status"] != data.STATUS_ORDER[0]}


@app.delete("/api/materials/{mid}")
def material_del(mid: str):
    if mid not in store.custom_materials():
        raise HTTPException(400, "Only user-defined materials can be deleted")
    store.delete_material(mid); return {"deleted": mid}


@app.get("/api/literature")
def literature(q: str):
    """Live NTRS search for additional references. Results are NOT curated or verified."""
    import urllib.request, urllib.parse
    try:
        url = "https://ntrs.nasa.gov/api/citations/search?" + urllib.parse.urlencode({"q": q, "page.size": 6})
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=15) as r:
            d = json.load(r)
        res = [{"id": x["id"], "title": x["title"], "type": x.get("stiType"), "url": f"https://ntrs.nasa.gov/citations/{x['id']}"} for x in d.get("results", [])]
        return {"available": True, "results": res, "label": "Discovered via live NTRS search: not verified, not curated, not used in any analysis."}
    except Exception as ex:
        return {"available": False, "results": [], "reason": f"NTRS search unavailable: {type(ex).__name__}"}


@app.get("/api/investigations")
def investigations():
    return coverage.investigations()


@app.get("/api/datasets")
def datasets():
    return coverage.datasets()


@app.get("/api/nasa-usage")
def nasa_usage():
    return coverage.nasa_usage()


@app.get("/api/materials/{mid}")
def material(mid: str, o2_pct: float | None = None, pressure_kpa: float | None = None, gravity: str | None = None, flow_cm_s: float | None = None, form: str | None = None):
    _404(data.materials().get(mid), "material")
    return analysis.material_profile(mid, {"o2_pct": o2_pct, "pressure_kpa": pressure_kpa, "gravity": gravity, "flow_cm_s": flow_cm_s, "form": form})


@app.post("/api/interactions")
def interactions(body: dict = Body(...)):
    return analysis.interaction(body["material_ids"])


@app.get("/api/evidence")
def evidence():
    return data.evidence()


@app.get("/api/sources")
def sources():
    return list(data.sources().values())


@app.post("/api/evidence/rank")
def rank(scen: dict = Body(...)):
    return analysis.ranked_evidence(scen)


@app.get("/api/search")
def search(q: str, mode: str = "auto", k: int = 8, spacecraft_id: str | None = None):
    if mode not in ("auto", "keyword", "semantic", "hybrid", "hybrid+graph", "keyword+graph"):
        raise HTTPException(400, "bad mode")
    return retrieval.search(q, mode, k, spacecraft_id)


# ---- spacecraft ----
@app.get("/api/templates")
def templates():
    return data.templates()


@app.get("/api/spacecraft")
def spacecraft_list():
    return store.list_spacecraft()


@app.post("/api/spacecraft")
def spacecraft_new(body: dict = Body(...)):
    try:
        return store.new_spacecraft(body.get("mode", "quick"), body.get("template_id"), body.get("name"))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/spacecraft/{sid}")
def spacecraft_get(sid: str):
    return _404(store.get_spacecraft(sid), "spacecraft")


@app.put("/api/spacecraft/{sid}")
def spacecraft_put(sid: str, body: dict = Body(...)):
    _404(store.get_spacecraft(sid), "spacecraft")
    body["id"] = sid
    try:
        return store.save_spacecraft(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/spacecraft/{sid}")
def spacecraft_del(sid: str):
    store.delete_spacecraft(sid); return {"deleted": sid}


@app.get("/api/spacecraft/{sid}/screen")
def screen(sid: str, compartment_id: str | None = None):
    _404(store.get_spacecraft(sid), "spacecraft")
    return analysis.screen(sid, compartment_id)


# ---- graph ----
@app.get("/api/graph/stats")
def graph_stats():
    return graph.stats()


@app.get("/api/graph/subgraph")
def graph_sub(center: str, depth: int = 2, domain: str | None = None):
    return graph.subgraph(center, min(depth, 4), domain)


@app.get("/api/graph/trace")
def graph_trace(node: str):
    return graph.trace(node)


# ---- science ----
@app.get("/api/models")
def model_list():
    return [models.public(m) for m in models.registry()]


@app.post("/api/predict")
def predict(req: dict = Body(...)):
    return models.assess(req)


@app.get("/api/audit")
def audit_all():
    return audit.run()


@app.get("/api/audit.csv")
def audit_csv():
    import csv, io
    b = io.StringIO(); w = csv.writer(b)
    w.writerow(["id", "status", "investigation", "test", "quantity", "source_a", "location_a", "value_a", "source_b", "location_b", "value_b", "normalised", "modelling", "unresolved_question"])
    for i in audit.run()["items"]:
        v = i["values"] + [{}] * (2 - len(i["values"]))
        w.writerow([i["id"], i["status"], i["investigation"], i["test"], i["quantity"], v[0].get("source_id"), v[0].get("location"), v[0].get("raw"),
                    v[1].get("source_id"), v[1].get("location"), v[1].get("raw"), i.get("normalised", ""), i.get("modelling", ""), i.get("unresolved_question") or ""])
    return Response(b.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=spacextinsafe_audit.csv"})


@app.get("/api/gaps")
def gaps(spacecraft_id: str | None = None):
    return analysis.gaps(spacecraft_id)


@app.post("/api/compare/conditions")
def compare_conditions(body: dict = Body(...)):
    return analysis.compare_conditions(body.get("material_id"), body.get("form"), body.get("scenarios", []), body.get("d0_mm"))


@app.get("/api/gaps/{dimension}")
def gaps_dim(dimension: str, spacecraft_id: str | None = None):
    if dimension not in ("gravity", "oxygen", "pressure", "airflow", "material", "form", "compartment"):
        raise HTTPException(400, "unknown dimension")
    return analysis.gaps_dimension(dimension, spacecraft_id)


@app.post("/api/spacecraft/{sid}/duplicate")
def spacecraft_dup(sid: str, body: dict = Body(default={})):
    try:
        return store.duplicate_spacecraft(sid, body.get("name"))
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/procedures/{sid}")
def procedures(sid: str):
    return store.list_procedures(sid)


@app.post("/api/procedures")
def procedure_add(body: dict = Body(...)):
    try:
        return store.save_procedure(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/compare")
def compare(body: dict = Body(...)):
    return analysis.compare(body["spacecraft_ids"])


@app.post("/api/insights")
def insights(scen: dict = Body(...)):
    return analysis.insights(scen)


@app.post("/api/copilot")
def ask(request: Request, body: dict = Body(...)):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "anon")).split(",")[0].strip()
    return copilot.ask(body["question"], body.get("scenario"), body.get("spacecraft_id"), body.get("mode", "auto"), ip)


@app.get("/api/copilot/usage")
def copilot_usage():
    return router.usage()


@app.post("/api/status/models/check")
def models_check():
    """Verifies the configured model IDs against the Anthropic models list (server-side key)."""
    router.check_models()
    return router.config()


@app.get("/api/incidents/{sid}")
def incident_list(sid: str):
    _404(store.get_spacecraft(sid), "spacecraft")
    return incidents.scenarios(sid)


@app.post("/api/incidents/replay")
def incident_replay(body: dict = Body(...)):
    try:
        return incidents.replay(body["spacecraft_id"], body.get("compartment_id"), body["type"], body.get("phase", "orbital operations"))
    except (StopIteration, KeyError):
        raise HTTPException(404, "Unknown spacecraft, compartment or incident type")


@app.post("/api/report")
def report(body: dict = Body(...)):
    if not store.get_spacecraft(body.get("spacecraft_id")):
        raise HTTPException(404, "Unknown spacecraft")
    pdf = reports.build(body["spacecraft_id"], body.get("scenario"), body.get("prediction"), body.get("interaction_ids"), body.get("compare_ids"), body.get("incident"))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=spacextinsafe_mission_report.pdf"})


@app.get("/api/evaluation")
def evaluation():
    if not os.path.exists(EVAL):
        return {"status": "not run", "message": "Run: python -m scripts.run_eval"}
    res = json.load(open(EVAL))
    live = os.path.join(os.path.dirname(EVAL), "results_claude_live.json")
    res["claude_live"] = json.load(open(live)) if os.path.exists(live) else {"status": "not run"}
    rout = os.path.join(os.path.dirname(EVAL), "results_routing.json")
    res["routing"] = json.load(open(rout)) if os.path.exists(rout) else {"status": "not run"}
    return res


@app.post("/api/evaluation/claude-live")
def evaluation_claude_live(x_admin_token: str | None = Header(default=None), judge: bool = False):
    """Runs the live Claude evaluation on the server (costs API credits). Requires the ADMIN_TOKEN environment variable."""
    tok = os.environ.get("ADMIN_TOKEN")
    if not tok or x_admin_token != tok:
        raise HTTPException(403, "Set ADMIN_TOKEN on the server and send it as the X-Admin-Token header")
    from scripts.eval_claude_live import run
    r = run(judge)
    return {k: v for k, v in r.items() if k != "cases"}


@app.post("/api/evaluation/routing-live")
def evaluation_routing_live(x_admin_token: str | None = Header(default=None), baseline: bool = False):
    """Runs the routing evaluation with real model calls (costs API credits; baseline=true also runs every case in Deep Research mode)."""
    tok = os.environ.get("ADMIN_TOKEN")
    if not tok or x_admin_token != tok:
        raise HTTPException(403, "Set ADMIN_TOKEN on the server and send it as the X-Admin-Token header")
    from scripts.eval_routing import run
    r = run(True, baseline)
    return {"routing_accuracy": {k: v for k, v in r["routing_accuracy"].items() if k != "cases"},
            "live": {k: (v.get("summary") if isinstance(v, dict) else v) for k, v in r["live"].items()}}


# Serve the built frontend when present (single-service deployment).
_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = os.path.join(_dist, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(_dist, "index.html"))