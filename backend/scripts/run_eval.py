"""Run all evaluations and write eval/results.json. Every total is derived from the executed results.
Usage: python -m scripts.run_eval"""
import os as _os, tempfile as _tf
_os.environ.setdefault("SXS_USAGE_LOG", _os.path.join(_tf.gettempdir(), "sxs_eval_usage.jsonl"))  # keep evaluation calls out of the server usage log
import hashlib, json, os, statistics, time, datetime
import numpy as np
from app.core import retrieval, copilot, models, audit, data, graph
E = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
K = 5


def retrieval_eval(fn="retrieval_questions.json"):
    qs = json.load(open(f"{E}/{fn}"))["questions"]
    retrieval.status()
    modes = ["keyword", "semantic", "hybrid", "hybrid+graph"]
    per_q, summary = [], {}
    for mode in modes:
        rows = []
        for q in qs:
            rel = set(q["relevant"])
            r = retrieval.search(q["q"], mode, k=K)
            if not r.get("available"):
                rows = None; summary[mode] = {"status": "Not evaluated", "reason": r.get("reason")}; break
            ids = [x["id"] for x in r["results"]]
            if not rel:
                rows.append({"id": q["id"], "type": q["type"], "excluded": True}); continue
            hits = [i for i in ids if i in rel]
            rr = next((1 / (n + 1) for n, i in enumerate(ids) if i in rel), 0.0)
            rows.append({"id": q["id"], "type": q["type"], "recall@5": len(hits) / len(rel), "precision@5": len(hits) / K, "rr": rr,
                         "latency_ms": r["latency_ms"], "top5": ids, "entities": r.get("entities")})
        if rows is None:
            continue
        def agg(sel):
            s = [x for x in rows if not x.get("excluded") and x["type"] in sel]
            return {"n": len(s), "recall@5": statistics.mean(x["recall@5"] for x in s), "precision@5": statistics.mean(x["precision@5"] for x in s),
                    "mrr": statistics.mean(x["rr"] for x in s), "latency_ms_median": statistics.median(x["latency_ms"] for x in s)}
        types = sorted({x["type"] for x in rows if not x.get("excluded")})
        summary[mode] = {"all": agg(set(types)), **{t: agg({t}) for t in types}, "n_unsupported_excluded": sum(1 for x in rows if x.get("excluded"))}
        per_q.append({"mode": mode, "rows": rows})
    # per-question comparison graph vs hybrid
    cmp = []
    if "hybrid" in summary and "hybrid+graph" in summary and "status" not in summary["hybrid"]:
        h = {x["id"]: x for x in next(p for p in per_q if p["mode"] == "hybrid")["rows"] if not x.get("excluded")}
        g = {x["id"]: x for x in next(p for p in per_q if p["mode"] == "hybrid+graph")["rows"] if not x.get("excluded")}
        for qid in h:
            d = g[qid]["recall@5"] - h[qid]["recall@5"]
            cmp.append({"id": qid, "type": h[qid]["type"], "hybrid_recall@5": h[qid]["recall@5"], "graph_recall@5": g[qid]["recall@5"],
                        "effect": "improved" if d > 1e-9 else "worse" if d < -1e-9 else "no change"})
    eff = {}
    for c in cmp:
        eff.setdefault(c["type"], {}).setdefault(c["effect"], 0); eff[c["type"]][c["effect"]] += 1
    return {"k": K, "n_questions": len(qs), "label_file_sha256": sha(f"{E}/{fn}"), "types": sorted({q["type"] for q in qs}), "semantic_model": retrieval.SEM,
            "modes": summary, "graph_effect_by_question": cmp, "graph_effect_counts": eff, "per_question": per_q,
            "disclosure": "Small labelled set written by the build assistant before the first run (hash locked in eval/LABELS.lock). Indicative only; "
                          "multi-hop questions name spacecraft elements defined in this app's own templates, so they test configuration-aware traversal, not general retrieval quality."}


def copilot_eval(fn="copilot_cases.json"):
    cs = json.load(open(f"{E}/{fn}"))["cases"]
    rows = []
    for c in cs:
        r = copilot.ask(c["q"])
        cited = sorted({x for cl in r["claims"] for x in cl["citations"]})
        if c["expected"] == "answer":
            ok = r["mode"] in ("claude", "evidence-retrieval") and bool(set(cited) & set(c["expect_cites"]))
        elif c["expected"] == "boundary":
            ok = bool(r.get("boundary_triggered"))
        else:
            ok = r["mode"] == "no-evidence"
        rows.append({"id": c["id"], "expected": c["expected"], "mode": r["mode"], "passed": ok, "cited": cited, "dropped_claims": len(r.get("dropped", [])),
                     "top_cosine": r.get("top_cosine")})
    modes = sorted({x["mode"] for x in rows})
    return {"n_cases": len(rows), "n_passed": sum(x["passed"] for x in rows), "by_expected": {e: {"n": sum(1 for x in rows if x["expected"] == e),
            "passed": sum(1 for x in rows if x["expected"] == e and x["passed"])} for e in ("answer", "boundary", "abstain")},
            "modes_observed": modes, "claude_live": copilot.STATE["verified_live"], "claude_error": copilot.STATE["last_error"],
            "case_file_sha256": sha(f"{E}/{fn}"), "cases": rows,
            "disclosure": f"{len(rows)} cases. Evaluated in mode(s): {', '.join(modes)}. " + ("Claude was live for this run." if copilot.STATE["verified_live"] else "Claude was NOT live for this run (no API key or API error), so answers were evidence-retrieval summaries; Claude-mode quality is untested.")}


def eligibility_eval():
    cases = [("Inside data, methanol 1 atm", dict(material_form="liquid droplet", fuel="methanol", o2_pct=21, pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="microgravity"), "Model-supported estimate"),
             ("Within each 1-D range but untested combination (30% O2 with 1.7 mm)", dict(material_form="liquid droplet", fuel="methanol", o2_pct=30, pressure_kpa=101.3, d0_mm=1.7, diluent="nitrogen", gravity="microgravity"), "not Model-supported"),
             ("O2 above tested range", dict(material_form="liquid droplet", fuel="methanol", o2_pct=40, pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="microgravity"), "Unavailable"),
             ("Fabric instead of droplet", dict(material_form="fabric", fuel="methanol", o2_pct=21, pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="microgravity"), "Unavailable"),
             ("Missing diameter", dict(material_form="liquid droplet", fuel="methanol", o2_pct=21, pressure_kpa=101.3, d0_mm=None, diluent="nitrogen", gravity="microgravity"), "Unavailable"),
             ("Negative pressure", dict(material_form="liquid droplet", fuel="methanol", o2_pct=21, pressure_kpa=-5, d0_mm=2.5, diluent="nitrogen", gravity="microgravity"), "Unavailable"),
             ("CO2 diluent", dict(material_form="liquid droplet", fuel="methanol", o2_pct=21, pressure_kpa=101.3, d0_mm=2.5, diluent="carbon dioxide", gravity="microgravity"), "Unavailable"),
             ("Partial gravity", dict(material_form="liquid droplet", fuel="n-heptane", o2_pct=21, pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="partial gravity"), "Unavailable"),
             ("Exploratory model, in-domain (heptane 0.7 atm)", dict(material_form="liquid droplet", fuel="n-heptane", o2_pct=30, pressure_kpa=72, d0_mm=3.2, diluent="nitrogen", gravity="microgravity"), "Exploratory estimate"),
             ("Non-predictor diameter outside range (methanol 0.7 atm, D0 1.2 mm)", dict(material_form="liquid droplet", fuel="methanol", o2_pct=30, pressure_kpa=71.5, d0_mm=1.2, diluent="nitrogen", gravity="microgravity"), "not Model-supported")]
    rows = []
    for name, req, exp in cases:
        a = models.assess(req)
        ok = a["outcome"] != "Model-supported estimate" if exp == "not Model-supported" else a["outcome"] == exp
        rows.append({"case": name, "expected": exp, "outcome": a["outcome"], "passed": ok, "reasons": a["reasons"]})
    return {"n_cases": len(rows), "n_passed": sum(r["passed"] for r in rows), "cases": rows}


def main():
    t = time.time()
    res = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "retrieval": retrieval_eval(), "copilot": copilot_eval(), "eligibility": eligibility_eval(),
           "holdout": {"retrieval": retrieval_eval("holdout_retrieval.json"), "copilot": copilot_eval("holdout_copilot.json"),
                       "note": "Holdout sets were written and hash-locked (eval/HOLDOUT.lock) before the round-2 changes were tested; they were not used for tuning."},
           "models": [{k: m[k] for k in ("model_id", "status", "failed_criteria", "n_observations", "n_sessions", "n_parameters", "features", "validation", "benchmark", "uncertainty_90_mm2_s")} for m in models.registry()],
           "audit": {"counts": audit.run()["counts"], "flex_rows_compared": audit.run()["flex_rows_compared"]},
           "graph": graph.stats(), "data": {"evidence_statements": len(data.evidence()), "quotes_verified": sum(1 for e in data.evidence() if e.get("verified"))}}
    hist = []
    for n, f, note in ((1, "results_run1_before_entity_fix.json", "Entity linking searched only the first spacecraft when none was named (bug)."),
                       (2, "results_run2_round1.json", "Round 1 final: bug fixed; labels unchanged.")):
        if os.path.exists(f"{E}/{f}"):
            pr = json.load(open(f"{E}/{f}"))
            hist.append({"run": n, "note": note, "hybrid+graph multi-hop recall@5": pr["retrieval"]["modes"]["hybrid+graph"]["multi-hop"]["recall@5"],
                         "copilot": f"{pr['copilot']['n_passed']}/{pr['copilot']['n_cases']}"})
    hist.append({"run": len(hist) + 1, "note": "Round 2: expanded templates (decomposed objects) and material ontology, general abstention rules; dev labels unchanged.",
                 "hybrid+graph multi-hop recall@5": res["retrieval"]["modes"].get("hybrid+graph", {}).get("multi-hop", {}).get("recall@5"),
                 "copilot": f"{res['copilot']['n_passed']}/{res['copilot']['n_cases']}"})
    res["run_history"] = hist
    res["runtime_s"] = round(time.time() - t, 1)
    json.dump(res, open(f"{E}/results.json", "w"), indent=1, default=float)
    r = res["retrieval"]["modes"]
    for m, v in r.items():
        print(m, v if "status" in v else {k: (round(v[k]["recall@5"], 3), round(v[k]["mrr"], 3)) for k in ("all", "single-hop", "multi-hop")})
    print("graph effect", res["retrieval"]["graph_effect_counts"])
    print("copilot", res["copilot"]["n_passed"], "/", res["copilot"]["n_cases"], res["copilot"]["by_expected"], res["copilot"]["modes_observed"])
    print("eligibility", res["eligibility"]["n_passed"], "/", res["eligibility"]["n_cases"])
    for m, v in res["holdout"]["retrieval"]["modes"].items():
        print("HOLDOUT", m, {k: round(v[k]["recall@5"], 3) for k in v if isinstance(v[k], dict)})
    print("HOLDOUT copilot", res["holdout"]["copilot"]["n_passed"], "/", res["holdout"]["copilot"]["n_cases"], res["holdout"]["copilot"]["by_expected"])


if __name__ == "__main__":
    main()
