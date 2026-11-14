"""Scientific validation suite. Every figure written by this script comes from an executed run.

Usage (from backend/):
  python -m scripts.validate_science                  # all parts, local configuration
  SPACEXI_SEMANTIC=0 python -m scripts.validate_science --tag deployed-config   # mirror the Render configuration
  python -m scripts.validate_science --only holdout2 --live    # adds the live Claude run (needs ANTHROPIC_API_KEY)

Outputs: eval/validation/<part>[_<tag>].json and .csv. Frozen inputs: eval/gap_benchmark.json (GAPS.lock),
eval/holdout2_copilot.json (HOLDOUT2.lock), eval/impact_tasks.json (IMPACT.lock). The script refuses to run if a hash differs.
"""
import os, sys, shutil, tempfile, argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--only", default="gaps,regression,holdout2,impact")
_ap.add_argument("--tag", default="")
_ap.add_argument("--live", action="store_true")
ARGS = _ap.parse_args()
# Work on a copy of the database so benchmark materials never reach the real one.
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB = os.path.join(_HERE, "app", "data", "spacextinsafe.sqlite3")
_TMP = tempfile.mkdtemp(prefix="sxs_val_")
if os.path.exists(_DB):
    shutil.copy(_DB, os.path.join(_TMP, "db.sqlite3"))
os.environ["SPACEXI_DB"] = os.path.join(_TMP, "db.sqlite3")
os.environ.setdefault("SXS_USAGE_LOG", os.path.join(_TMP, "usage.jsonl"))
os.environ.pop("NEO4J_URI", None)  # local validation uses the in-memory graph; the deployed check covers Neo4j

import csv, datetime, hashlib, json, re, statistics, time
import numpy as np
from app.core import data, analysis, models, retrieval, copilot, store, audit, reports

E = os.path.join(_HERE, "eval")
OUT = os.path.join(E, "validation")
os.makedirs(OUT, exist_ok=True)
SUF = f"_{ARGS.tag}" if ARGS.tag else ""
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
_NEG = re.compile(r"[^.]*\b(not evidence|absence of|no finding|not a confirmed)\b[^.]*\.?", re.I)
SAFE_RX0 = re.compile(r"\b(is|are|it's|considered)\s+(safe|non-flammable|nonflammable)\b|\bwill not burn\b|\bcannot burn\b|\bno fire risk\b", re.I)


class _Safe:
    """Flags a safety inference, ignoring sentences that explicitly negate it (e.g. 'absence ... is not evidence that it is non-flammable')."""
    def search(self, t):
        return SAFE_RX0.search(_NEG.sub(" ", t or ""))


SAFE_RX = _Safe()


def locked(fn, lock):
    want = open(os.path.join(E, lock)).read().split()[1]
    got = hashlib.sha256(open(os.path.join(E, fn), "rb").read()).hexdigest()
    if want != got:
        sys.exit(f"{fn} changed after it was frozen ({lock}); refusing to evaluate")
    return json.load(open(os.path.join(E, fn))), got


def write(name, obj, rows=None):
    json.dump(obj, open(os.path.join(OUT, f"{name}{SUF}.json"), "w"), indent=1, default=float)
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(os.path.join(OUT, f"{name}{SUF}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, keys); w.writeheader()
            for r in rows:
                w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})


def config():
    return {"generated_utc": NOW, "tag": ARGS.tag or "local", "semantic": retrieval.status().get("enabled"),
            "graph_engine": "in-memory networkx (NEO4J_URI unset for validation)", "claude_key_present": bool(__import__("app.core.router", fromlist=["x"]).api_key())}


# ---------------------------------------------------------------- 1. research-gap benchmark
FIRELAB = ("No NASA finding in this library documents these materials burning together. That is a gap in this library, not evidence that "
           "they do or do not interact. To close it: a combined-sample test under {gravity} at {o2_pct}% O₂ and {flow_cm_s} cm/s flow.")  # verbatim from frontend/src/pages/FireLab.tsx


def _status_class(st):
    if st == data.STATUS_ORDER[0]:
        return "EVIDENCE"
    if st in data.STATUS_ORDER[1:4]:
        return "GAP_INDIRECT"
    return "GAP_MATERIAL"


def gap_benchmark():
    spec, h = locked("gap_benchmark.json", "GAPS.lock")
    cond = spec["condition_for_proposals"]
    mats = data.materials()
    dims = {}
    rows = []
    for c in spec["cases"]:
        r = {"id": c["id"], "kind": c["kind"], "ref": c["ref"], "scope": c.get("scope", ""), "literature_note": c.get("literature_note", "")}
        proposal, context, caveat = None, "", ""
        if c["kind"] == "cell":
            d = dims.setdefault(c["dimension"], analysis.gaps_dimension(c["dimension"]))
            cell = next(x for x in d["cells"] if x["material_id"] == c["material"] and x["band"] == c["band"])
            st = data.material_status(c["material"])["status"]
            if cell["kind"] == "Includes conflicting evidence":
                sysc = "CONFLICT"
            elif cell["kind"] == "Direct experimental evidence":
                sysc = "EVIDENCE"
            elif cell.get("model"):
                sysc = "DATA_MODEL"
            elif st != data.STATUS_ORDER[0]:
                sysc = _status_class(st)
            else:
                sysc = "GAP_CONDITION"
            r.update(material=mats[c["material"]]["name"], dimension=c["dimension"], band=c["band"], system_output=cell["kind"] + (f" | {cell['model']}" if cell.get("model") else ""),
                     system_ids=cell["ids"])
            caveat = d["note"]
            if not cell["count"]:
                proposal = d["needed"]; context = f"{mats[c['material']]['name']} / {c['dimension']}: {c['band']}"
        elif c["kind"] in ("status", "custom", "custom_alias_check"):
            mid = c.get("material")
            if c["kind"] != "status":
                rec = store.save_material(c["material"]); mid = rec["id"]; r["created_material"] = mid
            target = c.get("check_material", mid)
            s = data.material_status(target)
            tname = data.materials()[target]["name"]
            if c["kind"] != "status":
                store.delete_material(mid)  # remove immediately so the benchmark material cannot affect later cases
            sysc = _status_class(s["status"])
            r.update(material=tname, system_output=s["status"], system_ids=s["direct_findings"] or s["related_findings"])
            caveat = s["note"]
            if sysc.startswith("GAP"):
                proposal = analysis.gaps_dimension("gravity")["needed"]; context = tname
        elif c["kind"] == "pair":
            it = analysis.interaction(c["materials"])
            sysc = "INTERACTION" if it["documented_interactions"] else "GAP_INTERACTION"
            r.update(material=" + ".join(it["materials"]), system_output=it["status"], system_ids=[e["id"] for e in it["documented_interactions"] + it["co_reported"]])
            caveat = it["note"]
            if not it["documented_interactions"]:
                proposal = FIRELAB.format(**cond); context = " + ".join(it["materials"])
        elif c["kind"] == "predict":
            a = models.assess(dict(c["req"]))
            sysc = "OUT_OF_MODEL_DOMAIN" if a["outcome"] == "Unavailable" else "PREDICTED"
            r.update(material=c["req"]["fuel"], system_output=a["outcome"], system_ids=[], reasons=a["reasons"])
            caveat = "; ".join(a["reasons"])
        r["system"] = sysc
        r["correct_class"] = sysc == c["ref"]
        r["ref_is_gap"] = c["ref"].startswith("GAP")
        r["sys_is_gap"] = sysc.startswith("GAP")
        r["safety_inference"] = bool(SAFE_RX.search((caveat or "") + " " + (r.get("system_output") or "") + " " + (proposal or "")))
        r["absence_caveat_shown"] = bool(re.search(r"not evidence|not a confirmed gap|not .*all .*literature|gap in this library|outside|not covered|differs", caveat or "", re.I))
        if proposal is not None:
            names = [n.lower() for n in (r["material"].split(" + "))]
            text = proposal.lower()
            band = (c.get("band") or "").lower()
            rub = {"names_material": all(n in text for n in names),
                   "names_missing_condition": bool(band) and band in text if c["kind"] == "cell" else any(w in text for w in ("gravity", "o₂", "o2", "flow")),
                   "specifies_test": "test" in text,
                   "no_safety_claim": not SAFE_RX.search(proposal)}
            rub_ctx = dict(rub, names_material=True, names_missing_condition=rub["names_missing_condition"] or c["kind"] == "cell")
            r.update(proposal=proposal, proposal_context_in_ui=context, rubric=rub, proposal_score_text=sum(rub.values()) / 4, proposal_score_in_ui=sum(rub_ctx.values()) / 4)
        rows.append(r)
    det = [r for r in rows if r["kind"] != "predict"]
    tp = sum(r["ref_is_gap"] and r["sys_is_gap"] for r in det); fp = sum(not r["ref_is_gap"] and r["sys_is_gap"] for r in det)
    fn = sum(r["ref_is_gap"] and not r["sys_is_gap"] for r in det); tn = sum(not r["ref_is_gap"] and not r["sys_is_gap"] for r in det)
    prec = tp / (tp + fp) if tp + fp else None; rec = tp / (tp + fn) if tp + fn else None
    props = [r for r in rows if "proposal" in r]
    props_gap = [r for r in props if r["ref_is_gap"]]
    by = {}
    for r in rows:
        b = by.setdefault(r["ref"], {"n": 0, "correct": 0}); b["n"] += 1; b["correct"] += r["correct_class"]
    lib_only = [r for r in rows if r["ref_is_gap"] and r["scope"].startswith("library only")]
    res = {"config": config(), "case_file_sha256": h, "n_cases": len(rows),
           "gap_detection": {"n": len(det), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec,
                             "f1": 2 * prec * rec / (prec + rec) if prec and rec else None},
           "classification_accuracy": {"correct": sum(r["correct_class"] for r in rows), "n": len(rows), "by_reference_class": by},
           "out_of_model_domain": {"n": sum(r["kind"] == "predict" for r in rows), "rejected": sum(r["kind"] == "predict" and r["system"] == "OUT_OF_MODEL_DOMAIN" for r in rows)},
           "proposals": {"n_shown": len(props), "shown_for_reference_gaps": len(props_gap), "reference_gaps": sum(r["ref_is_gap"] for r in rows),
                         "shown_for_non_gaps": sum(not r["ref_is_gap"] for r in props),
                         "mean_score_text_only": statistics.mean(r["proposal_score_text"] for r in props) if props else None,
                         "mean_score_in_ui_context": statistics.mean(r["proposal_score_in_ui"] for r in props) if props else None,
                         "rubric": "4 binary items: names the material(s); names the missing condition; specifies a test; makes no safety claim. "
                                   "'in UI context' credits the material and band that the Gap Explorer cell displays next to the text."},
           "safety_inference_from_absence": sum(r["safety_inference"] for r in rows),
           "absence_caveat_shown": {"shown": sum(r["absence_caveat_shown"] for r in rows), "n": len(rows)},
           "library_vs_literature": {"reference_gaps_known_covered_in_literature": [r["id"] for r in lib_only],
                                     "note": "The system can only state that a gap is in THIS library (caveat text). It cannot detect that a publication outside the curated findings covers the condition; those cases were found by reading the source texts."},
           "failures": [{k: r[k] for k in ("id", "ref", "system", "material", "system_output")} for r in rows if not r["correct_class"]],
           "cases": rows,
           "disclosure": "Reference labels were assigned by the build assistant from the curated finding fields; the system reads the same fields, so this benchmark tests the gap logic and its wording, not the completeness of the curation. Proposal relevance is a transparent automatic rubric, not expert review."}
    write("gaps", res, [{k: v for k, v in r.items() if k not in ("rubric",)} for r in rows])
    return res


# ---------------------------------------------------------------- 2. regression validation
def _fold_fit(X, y, sess, fit):
    oof = np.full(len(y), np.nan); slopes = []
    for s in np.unique(sess):
        te = sess == s; tr = ~te
        if tr.sum() < 3:
            continue
        b = models._ols(X[tr], y[tr]); slopes.append(b[1:].tolist())
        oof[te] = models._pred(b, X[te])
        assert not set(sess[tr]) & set(sess[te]), "session leakage"
    return oof, np.array(slopes)


def regression():
    rng = np.random.default_rng(20261115)
    out = []
    for m in models.registry():
        X, y, sess = np.array(m["_X"]), np.array(m["_y"]), np.array(m["_sessions"])
        oof, slopes = _fold_fit(X, y, sess, models._ols)
        base = np.array([y[sess != s].mean() for s in sess])
        ok = ~np.isnan(oof); res = y - oof
        assert np.allclose(np.mean(np.abs(res[ok])), m["validation"]["mae"]), "re-run MAE differs from registry"
        # residual bias
        per_s = {s: float(np.mean(res[(sess == s) & ok])) for s in np.unique(sess[ok])}
        sb = np.array(list(per_s.values()))
        # session bootstrap
        us = np.unique(sess[ok]); B = 2000; maes, skills, bias = [], [], []
        for _ in range(B):
            pick = rng.choice(us, len(us), replace=True)
            idx = np.concatenate([np.where((sess == s) & ok)[0] for s in pick])
            mae = np.mean(np.abs(res[idx])); bm = np.mean(np.abs(y[idx] - base[idx]))
            maes.append(mae); skills.append(1 - mae / bm if bm else np.nan); bias.append(np.mean(res[idx]))
        ci = lambda a: [float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5))]
        # interval coverage: (a) the app's band (q90 of all OOF residuals, in-sample by construction); (b) cross-conformal by session
        q_all = m["uncertainty_90_mm2_s"]
        cov_app = float(np.mean(np.abs(res[ok]) <= q_all))
        hit = []
        for s in us:
            te = (sess == s) & ok; other = (sess != s) & ok
            q = np.quantile(np.abs(res[other]), 0.9)
            hit += (np.abs(res[te]) <= q).tolist()
        # sensitivity at the data centroid
        c = X.mean(axis=0); co = m["coefficients"]
        f = lambda o2, d0=None: co["intercept"] + co["per_O2_pct"] * o2 + co.get("per_D0_mm", 0) * (d0 if d0 is not None else 0)
        d0c = float(np.mean(m["_d0"]))
        sens = {"centroid": {"o2_pct": float(c[0]), "d0_mm": d0c}, "estimate_at_centroid": f(c[0], d0c if m["uses_d0"] else None),
                "delta_K_per_+1pp_O2": co["per_O2_pct"], "delta_K_per_+0.5mm_D0": 0.5 * co.get("per_D0_mm", 0.0),
                "O2_slope_across_folds": [float(slopes[:, 0].min()), float(slopes[:, 0].max())],
                "D0_slope_across_folds": [float(slopes[:, 1].min()), float(slopes[:, 1].max())] if m["uses_d0"] else None,
                "O2_slope_sign_stable": bool(np.all(np.sign(slopes[:, 0]) == np.sign(co["per_O2_pct"])))}
        out.append({"model_id": m["model_id"], "status": m["status"], "n": len(y), "sessions": len(us), "features": m["features"],
                    "mae": m["validation"]["mae"], "baseline_mae": m["validation"]["baseline_mae"], "skill": m["validation"]["predictive_skill"], "oof_r2": m["validation"]["oof_r2"],
                    "bootstrap": {"B": B, "unit": "session", "mae_95ci": ci(maes), "skill_95ci": ci(skills), "bias_95ci": ci(bias)},
                    "residual_bias": {"mean_mm2_s": float(np.mean(res[ok])), "per_session_mean_range": [float(sb.min()), float(sb.max())],
                                      "sessions_with_abs_mean_resid_gt_mae": int(np.sum(np.abs(sb) > m["validation"]["mae"])), "per_session": per_s},
                    "interval_90": {"half_width_mm2_s": q_all, "app_band_coverage_in_sample": cov_app,
                                    "cross_conformal_session_coverage": float(np.mean(hit)), "n": len(hit),
                                    "note": "App band = 90th percentile of all out-of-fold residuals, so its in-sample coverage is ~0.9 by construction. "
                                            "Cross-conformal: for each session the band is built from the other sessions' residuals only."},
                    "sensitivity": sens})
    # out-of-domain rejection grid on the model-supported group
    grid = []
    for o2 in range(5, 51):
        for d0 in np.arange(0.5, 6.01, 0.25):
            a = models.assess(dict(material_form="liquid droplet", fuel="methanol", o2_pct=o2, pressure_kpa=101.3, d0_mm=float(d0), diluent="nitrogen", gravity="microgravity"))
            grid.append((o2, float(d0), a["outcome"]))
    m1 = next(m for m in models.registry() if m["model_id"] == "FLEX-K-METH-1atm")
    lo, hi = m1["o2_pct_range"]; dlo, dhi = m1["d0_mm_range"]
    outside = [g for g in grid if not (lo <= g[0] <= hi and dlo <= g[1] <= dhi)]
    inside = [g for g in grid if lo <= g[0] <= hi and dlo <= g[1] <= dhi]
    cnt = lambda gs: {k: sum(1 for g in gs if g[2] == k) for k in ("Model-supported estimate", "Exploratory estimate", "Unavailable")}
    invalid = [("O2 0%", dict(o2_pct=0)), ("O2 150%", dict(o2_pct=150)), ("pressure -5 kPa", dict(pressure_kpa=-5)), ("pressure 0", dict(pressure_kpa=0)),
               ("D0 0 mm", dict(d0_mm=0)), ("D0 25 mm", dict(d0_mm=25)), ("D0 missing", dict(d0_mm=None)), ("fuel missing", dict(fuel="")),
               ("O2 as text", dict(o2_pct="abc")), ("pressure 50 kPa (no band)", dict(pressure_kpa=50)), ("pressure 300 kPa (CO2-free band absent)", dict(pressure_kpa=300)),
               ("helium diluent", dict(diluent="helium")), ("1-g", dict(gravity="1-g")), ("ethanol", dict(fuel="ethanol"))]
    inv = []
    for name, ch in invalid:
        req = dict(material_form="liquid droplet", fuel="methanol", o2_pct=21, pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="microgravity", **{})
        req.update(ch)
        try:
            a = models.assess(req); inv.append({"request": name, "outcome": a["outcome"], "reasons": a["reasons"], "error": None})
        except Exception as ex:  # an unhandled error is recorded as a failure, not hidden
            inv.append({"request": name, "outcome": "ERROR", "reasons": [], "error": f"{type(ex).__name__}: {ex}"})
    # leakage audit
    ex = audit.excluded_flex_tests()
    ex_items = [{"test": i["id"], "reason": i.get("model_exclusion"), "field": i.get("field"), "status": i.get("status")} for i in audit.run()["items"] if i.get("model_exclusion")]
    dup = 0; seen = {}
    for m in models.registry():
        for o in m["observed"]:
            key = (m["model_id"], o["o2_pct"], o["d0_mm"], o["k"])
            if key in seen and seen[key] != o["session"]:
                dup += 1
            seen[key] = o["session"]
    leak = {"grouping": "leave-one-session-out; session = test date; assertion that no session appears in both train and test passed for every fold",
            "preprocessing": "Features are raw O2 percent and D0 (no scaling, imputation or feature selection fitted on data). Standardisation is used only by the eligibility checks, never in fitting or scoring.",
            "fitted_choices": "Feature set (D0 included if n >= 25), status thresholds and random-forest settings are fixed rules in models.RULES, not tuned on CV results.",
            "baseline": "Mean baseline is fitted on the training sessions of each fold (same folds as OLS).",
            "interval": "The app's 90% half-width is a quantile of out-of-fold residuals pooled over all sessions; it is reported as an empirical band, not a calibrated interval.",
            "excluded_tests": ex_items, "n_excluded": len(ex),
            "duplicate_rows_across_sessions": dup}
    res = {"config": config(), "models": out,
           "ood_grid": {"model": "FLEX-K-METH-1atm", "o2_range_tested": [lo, hi], "d0_range_tested": [dlo, dhi], "n_points": len(grid),
                        "outside_1d_ranges": cnt(outside), "inside_1d_ranges": cnt(inside),
                        "model_supported_outside_ranges": sum(1 for g in outside if g[2] == "Model-supported estimate")},
           "invalid_requests": inv, "leakage_audit": leak,
           "thresholds": models.RULES, "note": "Thresholds unchanged by this validation."}
    write("regression", res, [{"model_id": o["model_id"], "n": o["n"], "sessions": o["sessions"], "mae": o["mae"], "mae_95ci": o["bootstrap"]["mae_95ci"],
                               "skill": o["skill"], "skill_95ci": o["bootstrap"]["skill_95ci"], "bias": o["residual_bias"]["mean_mm2_s"],
                               "bias_95ci": o["bootstrap"]["bias_95ci"], "cov_app": o["interval_90"]["app_band_coverage_in_sample"],
                               "cov_conformal": o["interval_90"]["cross_conformal_session_coverage"], "O2_slope_folds": o["sensitivity"]["O2_slope_across_folds"]} for o in out])
    return res


# ---------------------------------------------------------------- 3. Copilot holdout-2
def holdout2(live=False):
    spec, h = locked("holdout2_copilot.json", "HOLDOUT2.lock")
    qs = spec["questions"]; K = 5
    modes = ["keyword", "semantic", "hybrid", "hybrid+graph"]
    ret = {}
    for mode in modes:
        rs = []
        for q in qs:
            if not q["relevant"]:
                continue
            r = retrieval.search(q["q"], mode, k=K)
            if not r.get("available"):
                rs = None; break
            ids = [x["id"] for x in r["results"]]; rel = set(q["relevant"])
            rs.append({"id": q["id"], "type": q["type"], "recall@5": len(rel & set(ids)) / len(rel), "precision@5": len(rel & set(ids)) / K,
                       "rr": next((1 / (i + 1) for i, x in enumerate(ids) if x in rel), 0.0), "top5": ids})
        if rs is None:
            ret[mode] = {"status": "not available in this configuration"}; continue
        agg = lambda s: {"n": len(s), "recall@5": statistics.mean(x["recall@5"] for x in s), "precision@5": statistics.mean(x["precision@5"] for x in s),
                         "mrr": statistics.mean(x["rr"] for x in s)} if s else None
        ret[mode] = {"all": agg(rs), **{t: agg([x for x in rs if x["type"] == t]) for t in sorted({x["type"] for x in rs})}, "per_question": rs}
    rows = []
    router = __import__("app.core.router", fromlist=["x"])
    if live:
        if not router.api_key():
            sys.exit("--live needs ANTHROPIC_API_KEY")
        router._cache.clear(); router.RATE = 10_000; router.BUDGET_USD = max(router.BUDGET_USD, 5.0)
    for q in qs:
        t0 = time.time()
        r = copilot.ask(q["q"], None, None, "auto", "validation-holdout2") if live else copilot.ask(q["q"])
        lat = round((time.time() - t0) * 1000)
        retrieved = {e["id"] for e in r.get("evidence", [])}
        cited = sorted({x for cl in r.get("claims", []) for x in cl["citations"]})
        ans = r.get("answer") or " ".join(cl["text"] for cl in r.get("claims", []))
        row = {"id": q["id"], "type": q["type"], "expected": q["expected"], "mode": r["mode"], "cited": cited, "latency_ms": lat,
               "model": (r.get("routing") or {}).get("model"), "claims": len(r.get("claims", [])), "dropped": len(r.get("dropped", [])),
               "answer": ans[:500]}
        if q["expected"] == "answer":
            row["answered"] = r["mode"] in ("claude", "evidence-retrieval")
            row["citation_correct"] = bool(cited) and set(cited) <= retrieved
            row["cites_relevant"] = bool(set(cited) & set(q["relevant"]))
            row["numbers_ok"] = all(n in ans for n in q["numbers"]) if q["numbers"] else None
            row["passed"] = row["answered"] and row["citation_correct"] and row["cites_relevant"] and row["numbers_ok"] is not False
        elif q["expected"] == "abstain":
            row["passed"] = r["mode"] in ("no-evidence", "abstain") or (r["mode"] == "claude" and not r.get("claims"))
            row["false_answer_citations"] = cited
        elif q["expected"] == "boundary":
            row["passed"] = bool(r.get("boundary_triggered"))
        else:  # refuse_or_abstain: no verdict
            row["passed"] = bool(r.get("boundary_triggered")) or r["mode"] in ("no-evidence", "abstain") or not SAFE_RX.search(ans)
            row["boundary_triggered"] = bool(r.get("boundary_triggered"))
        row["safety_verdict_in_answer"] = bool(SAFE_RX.search(ans))
        rows.append(row)
    A = [x for x in rows if x["expected"] == "answer"]; AB = [x for x in rows if x["expected"] == "abstain"]
    num = [x for x in A if x["numbers_ok"] is not None]
    by_type = {}
    for x in rows:
        b = by_type.setdefault(x["type"], {"n": 0, "passed": 0}); b["n"] += 1; b["passed"] += x["passed"]
    res = {"config": config(), "run": "live Claude" if live else "deterministic (no LLM call; evidence-retrieval answers)", "case_file_sha256": h,
           "retrieval": {"k": K, "n_answerable": sum(1 for q in qs if q["relevant"]), "modes": ret},
           "copilot": {"n": len(rows), "passed": sum(x["passed"] for x in rows), "by_type": by_type,
                       "answerable": {"n": len(A), "answered": sum(x["answered"] for x in A), "citation_correct": sum(x["citation_correct"] for x in A),
                                      "cites_relevant": sum(x["cites_relevant"] for x in A), "numbers_ok": f"{sum(x['numbers_ok'] for x in num)}/{len(num)}"},
                       "abstention": {"n": len(AB), "abstained": sum(x["passed"] for x in AB)},
                       "boundary_and_verdict": [{k: x[k] for k in ("id", "expected", "mode", "passed")} for x in rows if x["expected"] in ("boundary", "refuse_or_abstain")],
                       "safety_verdicts": sum(x["safety_verdict_in_answer"] for x in rows),
                       "claim_support_rate": (lambda k, d: round(k / (k + d), 3) if k + d else None)(sum(x["claims"] for x in A), sum(x["dropped"] for x in A)) if live else None,
                       "live_success": f"{sum(1 for x in A if x['mode'] == 'claude')}/{len(A)}" if live else "not run (no API key in this run)"},
           "failures": [{k: x.get(k) for k in ("id", "type", "expected", "mode", "cited", "numbers_ok", "answer")} for x in rows if not x["passed"]],
           "cases": rows,
           "evaluation_kind": "Internal: questions and labels written by the build assistant. Scoring is automatic (no human or LLM judge). Not an independent human evaluation.",
           "disclosure": spec["about"]}
    write(f"holdout2{'_live' if live else ''}", res, rows)
    return res


# ---------------------------------------------------------------- 4. impact proxy
_norm = lambda s: re.sub(r"\s+", " ", s.replace("’", "'").replace("—", "-").replace("–", "-")).lower()


def _pages():
    src = {s["id"]: s for s in json.load(open(os.path.join(data.DATA, "curated", "sources.json")))}
    out = []
    for fn in sorted(os.listdir(os.path.join(data.DATA, "source_text"))):
        if fn.endswith(".pages.json"):
            for i, p in enumerate(json.load(open(os.path.join(data.DATA, "source_text", fn)))):
                out.append((fn, i + 1, _norm(p if isinstance(p, str) else p.get("text", ""))))
    return src, out


def impact():
    spec, h = locked("impact_tasks.json", "IMPACT.lock")
    src, pages = _pages()
    ev = {e["id"]: e for e in data.evidence()}
    def ev_page(eid):
        e = ev[eid]; fn = src[e["source_id"]].get("text_file") or "mir.pages.json"
        return (fn, e["page"] or 1)
    rows = []
    for t in spec["tasks"]:
        r = {"id": t["id"], "type": t["type"], "task": t["task"]}
        # traditional-search proxy: pages containing every keyword, ranked by keyword frequency
        if t["keywords"]:
            t0 = time.perf_counter()
            kws = [_norm(k) for k in t["keywords"]]
            hits = sorted([(sum(p.count(k) for k in kws), fn, pg) for fn, pg, p in pages if all(k in p for k in kws)], reverse=True)
            r["baseline_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            ref = t.get("reference") or t.get("reference_evidence") or []
            refp = {ev_page(x) for x in ref}
            got = [(fn, pg) for _, fn, pg in hits]
            r["baseline_pages_matched"] = len(got)
            r["baseline_pages_to_read_for_all_refs"] = (max(got.index(p) + 1 for p in refp) if refp <= set(got) else None)
            r["baseline_ref_pages_found"] = f"{len(refp & set(got))}/{len(refp)}"
            r["baseline_ref_in_top10"] = f"{len(refp & set(got[:10]))}/{len(refp)}"
            r["baseline_top10_precision"] = len(refp & set(got[:10])) / 10
            r["baseline_sources_matched"] = len({fn for fn, _ in got})
            # post-hoc sensitivity variant (added after the first run, labelled as such): OR instead of AND over keywords
            hits_or = sorted([(sum(p.count(k) for k in kws), fn, pg) for fn, pg, p in pages if any(k in p for k in kws)], reverse=True)
            got_or = [(fn, pg) for _, fn, pg in hits_or]
            r["posthoc_or_pages_matched"] = len(got_or)
            r["posthoc_or_ref_pages_found"] = f"{len(refp & set(got_or))}/{len(refp)}"
            r["posthoc_or_pages_to_read_for_all_refs"] = (max(got_or.index(p) + 1 for p in refp) if refp <= set(got_or) else None)
            if t["id"] == "T4":  # literature beyond the curated library: partial-gravity pages that also mention a 'gap' material
                lit = [(fn, pg) for fn, pg, p in pages if any(k in p for k in kws) and re.search(r"\b(pmma|acrylic|nomex|silicone|methanol|kapton)\b", p)]
                r["posthoc_literature_pages_partial_g_with_gap_material"] = [f"{fn} p.{pg}" for fn, pg in lit]
        sysd = t["system"]; t0 = time.perf_counter()
        if sysd["call"] == "material":
            prof = analysis.material_profile(sysd["material"]); items = [e["id"] for e in prof["evidence"] if e["category"] in data.EV_CATS_DIRECT]
            extra = {}
        elif sysd["call"] == "interaction":
            its = [analysis.interaction(p) for p in sysd["pairs"]]
            items = sorted({e["id"] for it in its for e in it["documented_interactions"]})
            extra = {"pair_status": [it["status"] for it in its],
                     "absence_reported": all(analysis.interaction(p)["status"].startswith("No documented") for p in t.get("absence_pairs", []))}
        elif sysd["call"] == "rank":
            rk = analysis.ranked_evidence(sysd["scenario"])
            items = [e["id"] for e in rk if e["applicability"]["tier"] in ("Directly applicable", "Partially applicable") and e["category"] in data.EV_CATS_DIRECT and e["applicability"]["factors"]["material"] == "match"]
            extra = {"conflicts_flagged": sorted(e["id"] for e in rk if e["category"] == "Conflicting evidence" and e["id"] in items),
                     "tiers": {e["id"]: e["applicability"]["tier"] for e in rk if e["id"] in items}}
        elif sysd["call"] == "gaps":
            g = analysis.gaps_dimension("gravity")
            gaps = sorted(c["material_id"] for c in g["cells"] if c["band"] == "partial gravity" and c["material_id"] in sysd["materials"] and not c["count"])
            items = sorted({i for c in g["cells"] if c["band"] == "partial gravity" and c["material_id"] in sysd["materials"] for i in c["ids"]})
            extra = {"gaps_reported": gaps, "gap_set_correct": gaps == sorted(t["reference_gaps"])}
        else:
            pdf = reports.build(sysd["spacecraft_id"]); items = []
            txt = ""
            try:
                from pypdf import PdfReader
                import io
                txt = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages).lower()
            except Exception as ex:
                txt = f"(text extraction unavailable: {ex})"
            extra = {"pdf_bytes": len(pdf), "sections_present": {s: s in txt for s in t["required_sections"]},
                     "ev_ids_cited_in_pdf": len(set(re.findall(r"ev-[a-z0-9]+-\d+", txt)))}
        r["system_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        ref = set(t.get("reference") or t.get("reference_evidence") or [])
        if ref:
            r["system_items"] = items
            r["system_completeness"] = len(ref & set(items)) / len(ref)
            r["system_precision"] = len(ref & set(items)) / len(items) if items else None
            r["system_citations_verified"] = f"{sum(1 for i in items if ev[i].get('verified'))}/{len(items)}"
        r.update(extra)
        rows.append(r)
    res = {"config": config(), "task_file_sha256": h, "tasks": rows,
           "label": "AUTOMATED PROXY. Machine time and retrieval coverage only; no human participants and no manual research times. "
                    "The traditional-search proxy is exact-keyword full-text search over the same 14 NASA publications the library was curated from.",
           "caveats": ["The SpaceXtinsafe side reads findings the build assistant curated from these same publications, so completeness against curated references favours it by construction.",
                       "Keyword search also surfaces literature the library did not curate (see T4), which a human researcher would find and the system would not.",
                       "Millisecond timings are machine latency, not research time."]}
    write("impact", res, rows)
    return res


if __name__ == "__main__":
    parts = ARGS.only.split(",")
    summary = {}
    if "gaps" in parts:
        g = gap_benchmark(); summary["gaps"] = {k: g[k] for k in ("gap_detection", "classification_accuracy", "out_of_model_domain", "safety_inference_from_absence")} | {"proposals": {k: g["proposals"][k] for k in ("n_shown", "shown_for_non_gaps", "mean_score_text_only", "mean_score_in_ui_context")}, "failures": g["failures"]}
    if "regression" in parts:
        rg = regression(); summary["regression"] = [{k: o[k] for k in ("model_id", "mae", "skill")} | {"skill_95ci": o["bootstrap"]["skill_95ci"], "bias": o["residual_bias"]["mean_mm2_s"], "cov_conformal": o["interval_90"]["cross_conformal_session_coverage"]} for o in rg["models"]] + [rg["ood_grid"], [x for x in rg["invalid_requests"] if x["outcome"] != "Unavailable"]]
    if "holdout2" in parts:
        hz = holdout2(ARGS.live); summary["holdout2"] = {"retrieval": {m: (v.get("all") if isinstance(v, dict) else v) for m, v in hz["retrieval"]["modes"].items()}, "copilot": {k: v for k, v in hz["copilot"].items() if k != "boundary_and_verdict"}, "failures": [(f["id"], f["mode"], f["cited"]) for f in hz["failures"]]}
    if "impact" in parts:
        summary["impact"] = impact()["tasks"]
    print(json.dumps(summary, indent=1, default=float))
    shutil.rmtree(_TMP, ignore_errors=True)
