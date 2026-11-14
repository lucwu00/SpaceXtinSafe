"""Scientific AI evaluation report. Usage: python -m scripts.eval_report

Re-runs the locked copilot case sets through the copilot with the API key REMOVED (deterministic evidence mode), times each
answer, and scores citations against the gold labels. Then merges the retrieval, model, live-Claude and routing results that
were produced by executed runs. Writes eval/results_report.json and docs/EVAL_REPORT.md.

Two systems are reported separately and never mixed:
  A. Deterministic evidence mode (no LLM): retrieved NASA findings are quoted verbatim.
  B. Live Claude Copilot: only from eval/results_claude_live.json / results_routing.json, i.e. runs with a real API key.
"""
import os as _os, tempfile as _tf
_os.environ.setdefault("SXS_USAGE_LOG", _os.path.join(_tf.gettempdir(), "sxs_eval_usage.jsonl"))
import json, os, statistics, time
from datetime import datetime, timezone
from app.core import copilot, router

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(HERE, "eval")
DOC = os.path.join(os.path.dirname(HERE), "docs", "EVAL_REPORT.md")
load = lambda f: json.load(open(os.path.join(EV, f))) if os.path.exists(os.path.join(EV, f)) else {"status": "not run"}


def deterministic(case_file):
    key = os.environ.pop("ANTHROPIC_API_KEY", None)
    router._cache.clear(); rows = []
    try:
        for c in json.load(open(os.path.join(EV, case_file)))["cases"]:
            t0 = time.perf_counter(); r = copilot.ask(c["q"], None, None, "auto", "eval-report"); ms = (time.perf_counter() - t0) * 1000
            retrieved = {e["id"] for e in r.get("evidence") or []}
            cited = [x for cl in r.get("claims") or [] for x in cl["citations"]]
            gold = set(c.get("expect_cites") or [])
            row = {"id": c["id"], "expected": c["expected"], "mode": r["mode"], "latency_ms": round(ms, 1), "cited": sorted(set(cited))}
            if c["expected"] == "answer":
                row["answered"] = bool(cited)
                row["citations_in_retrieved"] = bool(cited) and set(cited) <= retrieved          # citation correctness (grounding)
                row["citation_precision_vs_gold"] = round(len(set(cited) & gold) / len(set(cited)), 3) if cited else 0.0
                row["citation_recall_vs_gold"] = round(len(set(cited) & gold) / len(gold), 3) if gold else None
                # claim support: in evidence mode each claim is the cited finding's own statement, checked verbatim
                evs = {e["id"]: e for e in r.get("evidence") or []}
                row["claims_verbatim_supported"] = sum(1 for cl in r.get("claims") or [] if any(cl["text"] == evs.get(x, {}).get("statement") for x in cl["citations"]))
                row["claims"] = len(r.get("claims") or [])
            elif c["expected"] == "abstain":
                row["abstained"] = r["mode"] in ("no-evidence", "abstain") or not r.get("claims")
            else:
                row["boundary"] = bool(r.get("boundary_triggered"))
            rows.append(row)
    finally:
        if key: os.environ["ANTHROPIC_API_KEY"] = key
    ans = [x for x in rows if x["expected"] == "answer"]; ab = [x for x in rows if x["expected"] == "abstain"]; bd = [x for x in rows if x["expected"] == "boundary"]
    mean = lambda v: round(statistics.mean(v), 3) if v else None
    return {"n": len(rows), "answer_cases": len(ans), "answered": sum(x["answered"] for x in ans),
            "citation_correctness": f"{sum(x['citations_in_retrieved'] for x in ans)}/{len(ans)}",
            "citation_precision_vs_gold": mean([x["citation_precision_vs_gold"] for x in ans]),
            "citation_recall_vs_gold": mean([x["citation_recall_vs_gold"] for x in ans if x["citation_recall_vs_gold"] is not None]),
            "claim_support": f"{sum(x['claims_verbatim_supported'] for x in ans)}/{sum(x['claims'] for x in ans)}",
            "abstention_rate_unsupported": f"{sum(x['abstained'] for x in ab)}/{len(ab)}",
            "false_abstention_on_answerable": f"{sum(not x['answered'] for x in ans)}/{len(ans)}",
            "boundary_refusal": f"{sum(x['boundary'] for x in bd)}/{len(bd)}",
            "latency_ms_median": statistics.median([x["latency_ms"] for x in rows]), "latency_ms_max": max(x["latency_ms"] for x in rows), "cases": rows}


def main():
    R = load("results.json")
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "evaluation_run_utc": R.get("generated_utc"),
           "retrieval": {s: {m: {k: round(v["all"][k], 3) for k in ("recall@5", "precision@5", "mrr")} | {"n": v["all"]["n"], "multi_hop_recall@5": round(v.get("multi-hop", {}).get("recall@5", float("nan")), 3) if v.get("multi-hop") else None}
                              for m, v in ret["modes"].items()} for s, ret in (("development", R["retrieval"]), ("holdout", R["holdout"]["retrieval"]))},
           "deterministic_copilot": {"development": deterministic("copilot_cases.json"), "holdout": deterministic("holdout_copilot.json")},
           "live_claude": load("results_claude_live.json"), "routing": load("results_routing.json"),
           "models": [{k: m[k] for k in ("model_id", "status", "n_observations", "n_sessions", "n_parameters", "failed_criteria")} |
                      {"cv": m["validation"]["scheme"], "mae": round(m["validation"]["mae"], 4), "baseline_mae": round(m["validation"]["baseline_mae"], 4),
                       "skill": round(m["validation"]["predictive_skill"], 3), "oof_r2": round(m["validation"].get("oof_r2", float("nan")), 3),
                       "rf_mae": round(m["benchmark"]["random_forest"]["mae"], 4) if m.get("benchmark", {}).get("random_forest") else None,
                       "band90": round(m.get("uncertainty_90_mm2_s") or 0, 3)} for m in R["models"]],
           "eligibility": {"n": R["eligibility"]["n_cases"], "passed": R["eligibility"]["n_passed"]}}
    json.dump(out, open(os.path.join(EV, "results_report.json"), "w"), indent=1)
    open(DOC, "w").write(markdown(out)); return out


def markdown(o):
    L = [f"# Scientific AI evaluation report", "",
         f"Generated {o['generated_utc']} by `python -m scripts.eval_report` from executed runs (retrieval/model run {o['evaluation_run_utc']}).",
         "Two systems are reported separately: **A. deterministic evidence mode (no LLM)** and **B. live Claude Copilot**. Results of A are never presented as results of B.", "",
         "## 1. Evidence retrieval (top 5)", "", "| Split | Mode | n | Recall@5 | Precision@5 | MRR | Multi-hop Recall@5 |", "|---|---|---|---|---|---|---|"]
    for s, ms in o["retrieval"].items():
        for m, v in ms.items():
            L.append(f"| {s} | {m} | {v['n']} | {v['recall@5']} | {v['precision@5']} | {v['mrr']} | {v['multi_hop_recall@5'] if v['multi_hop_recall@5'] is not None else '—'} |")
    L += ["", "Precision@5 is bounded by the number of relevant findings per question (often 1–2), so values near 0.2–0.3 can still mean the relevant findings were found. "
          "The holdout set was not used for tuning. GraphRAG figures come from the in-memory graph; the Neo4j path is checked separately for identical results (`POST /api/status/neo4j/verify`).", "",
          "## 2. Copilot, system A: deterministic evidence mode (no LLM)", "",
          "Answers are retrieved NASA findings quoted verbatim, so claim support measures retrieval and selection, not generation.", "",
          "| Set | Cases | Citation correctness (cited ⊆ retrieved) | Citation precision vs gold | Citation recall vs gold | Claim support (verbatim) | Abstention on unsupported | False abstention on answerable | Boundary refusals | Median latency |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s, d in o["deterministic_copilot"].items():
        L.append(f"| {s} | {d['n']} | {d['citation_correctness']} | {d['citation_precision_vs_gold']} | {d['citation_recall_vs_gold']} | {d['claim_support']} | {d['abstention_rate_unsupported']} | {d['false_abstention_on_answerable']} | {d['boundary_refusal']} | {d['latency_ms_median']:.0f} ms |")
    L += ["", "Cost: $0 (no API calls). Latency is the median per question; the first question also loads the embedding model once (cold start, several seconds).",
          "Disclosure: one abstention rule was changed on 2026-11-15, after these question sets had been run. Questions naming a NASA investigation, whose words all appear in that investigation's evidence, no longer abstain. Results before and after the change are the same.", "", "## 3. Copilot, system B: live Claude", ""]
    lc = o["live_claude"]
    if lc.get("status") != "run":
        L += [f"**Not run.** {lc.get('reason', '')}. No live Claude success rate, latency, cost or answer-quality figure is claimed.",
              "Run on a server with `ANTHROPIC_API_KEY`: `python -m scripts.eval_claude_live` (15 locked cases), then `python -m scripts.eval_report`."]
    else:
        a = lc["answer_cases"]
        L += [f"Run {lc['generated_utc']} · models used: {lc.get('by_model')}", "",
              "| Metric | Result |", "|---|---|",
              f"| Live success rate (answer cases answered by Claude, not fallback) | {lc['live_success_rate']['answer_cases_answered_by_claude']} |",
              f"| API fallbacks | {lc['live_success_rate']['api_fallbacks']} |",
              f"| Citation correctness (all citations retrieved) | {a['citation_correct']}/{a['n']} |",
              f"| Mean citation completeness vs gold | {a['mean_citation_completeness']} |",
              f"| Claim support (claims kept by citation + number checks) | {lc.get('claim_support_rate')} |",
              f"| Exact numbers present | {a['numbers_ok']}/{a['n']} |",
              f"| Abstention on unsupported | {lc['abstain']['passed']}/{lc['abstain']['n']} |",
              f"| Boundary refusals | {lc['boundary']['passed']}/{lc['boundary']['n']} |",
              f"| Latency (LLM calls) | median {lc['latency_ms_llm']['median']} ms, max {lc['latency_ms_llm']['max']} ms |",
              f"| Tokens / estimated cost | {lc['tokens']['input']} in, {lc['tokens']['output']} out · ${lc['estimated_cost_usd']} |",
              f"| Overall | {lc['n_passed']}/{lc['n_cases']} cases passed |", ""] + [
              f"- Failed {x['id']} ({x['expected']}): mode {x['mode']}, model {x.get('model')}, cited {x.get('cited')}, claims removed by checks {x.get('dropped')}, expected numbers present: {x.get('numbers_ok')}."
              for x in lc["cases"] if not x["passed"]] + ["", f"Judge: {lc.get('judge')}. {lc.get('disclosure', '')}"]
    rt = o["routing"]
    if rt.get("routing_accuracy"):
        A = rt["routing_accuracy"]; L += ["", "### Multi-model routing", "", f"Routing accuracy (rules only, no API): {A['correct']}/{A['n']} locked cases routed to the expected tier."]
        lv = rt.get("live", {})
        if lv.get("status") == "run" and lv.get("deep_baseline"):
            sq = lv["deep_baseline"]["same_questions_llm_only"]
            fails = lambda rows: sum(1 for x in rows if (x.get("fallback") or "").startswith("API error"))
            fa, fd = fails(lv["auto"]["cases"]), fails(lv["deep_baseline"]["cases"])
            L += ["", f"Live run {rt['generated_utc']}: the same {sq['auto']['n']} LLM-routed questions answered in Auto mode and in Deep Research mode (always the advanced model for science).", "",
                  "| Mode | Models used | Tokens in / out | Est. cost | Median latency | Claims kept / removed | Escalations | Failed calls (fallback) |", "|---|---|---|---|---|---|---|---|"]
            for n, x, f in (("Auto", sq["auto"], fa), ("Deep Research (baseline)", sq["deep"], fd)):
                L.append(f"| {n} | {', '.join(f'{k} ×{v}' for k, v in x['by_model'].items())} | {x['input_tokens']} / {x['output_tokens']} | ${x['cost_usd']} | {x['latency_ms_median']} ms | {x['claims_kept']} / {x['claims_dropped']} | {x['escalations']} | {f} |")
            L += ["", f"**Caveat:** {fa} Auto calls and {fd} baseline call failed with a response-parsing error (JSONDecodeError; the reply could not be parsed as the required JSON, likely truncation at the token limit). "
                  "Tokens of failed calls were not recorded, so both costs are understated, Auto more so. The cost difference is therefore **not** reported as a measured saving. "
                  "Quality was compared only by the automatic claim checks, not by expert review."]
    L += ["", "## 4. FLEX burning-rate regression models", "",
          "Validation is leave-one-session-out cross-validation (each test session held out in turn, so no session is in both training and test). "
          "The baseline predicts the training mean. A random forest is benchmarked on identical folds.", "",
          "| Model | Status | n / sessions | Params | CV MAE (mm²/s) | Baseline MAE | Skill vs baseline | Out-of-fold R² | RF MAE | 90% band ± |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m in o["models"]:
        L.append(f"| {m['model_id']} | {m['status']} | {m['n_observations']} / {m['n_sessions']} | {m['n_parameters']} | {m['mae']} | {m['baseline_mae']} | {m['skill']} | {m['oof_r2']} | {m['rf_mae']} | {m['band90']} |")
    L += ["", f"Prediction eligibility: {o['eligibility']['passed']}/{o['eligibility']['n']} locked cases give the specified outcome.", "",
          "**Validation limitations**", "",
          "- Small samples: 9–41 tests per model; only methanol at 1 atm meets the Model-supported criteria (n ≥ 20, ≥ 8 sessions, skill ≥ 0.30).",
          "- There is no separate external test set. Cross-validation across sessions estimates performance on new sessions of the same FLEX campaign, not on other facilities, fuels or diluents.",
          "- Nitrogen diluent and microgravity only. Helium/CO₂ diluents and other pressures are excluded, and estimates outside the joint O₂–diameter domain are refused.",
          "- Test 193F001 is excluded because two NASA sources disagree (K 0.41 vs 0.56 mm²/s).",
          "- The 90% band is empirical from out-of-fold residuals; it is not a calibrated prediction interval for unseen conditions.",
          "- Only droplet burning rate is modelled. No model exists for solids (Saffire, BASS), so they are evidence only.", "",
          "## 5. What is not claimed", "",
          "- No live Claude quality, latency, success rate or cost until section 3 shows a run.",
          "- No cost saving from model routing until the live baseline comparison is run.",
          "- Labels were written by the project team; there was no independent expert review."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    o = main()
    for s, d in o["deterministic_copilot"].items():
        print(s, {k: v for k, v in d.items() if k != "cases"})
    print("live Claude:", o["live_claude"].get("status"), "· report written to docs/EVAL_REPORT.md")