"""Multi-model routing evaluation. Usage: python -m scripts.eval_routing [--live] [--baseline]

Part A (always, no API calls): routing accuracy — the tier each locked case is routed to vs its expected tier.
Part B (--live, needs ANTHROPIC_API_KEY on this server): every case is answered for real; records model, tokens, estimated
cost, latency, escalations, fallbacks and claim checks. --baseline also answers the LLM cases in Deep Research mode
(always the advanced model) so cost and quality can be compared on the same questions. Nothing is reported as a saving
unless both runs were executed.
"""
import os as _os, tempfile as _tf
_os.environ.setdefault("SXS_USAGE_LOG", _os.path.join(_tf.gettempdir(), "sxs_eval_usage.jsonl"))  # keep evaluation calls out of the server usage log
import hashlib, json, os, statistics, sys, time
from datetime import datetime, timezone
from app.core import copilot, router

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(HERE, "eval", "routing_cases.json")
OUT = os.path.join(HERE, "eval", "results_routing.json")


def observed_tier(r):
    rt = r.get("routing", {})
    return rt.get("selected_tier", rt.get("tier", 0)) if r.get("mode") not in ("deterministic", "boundary", "no-evidence") or rt.get("selected_tier") else rt.get("tier", 0)


def summarise(rows):
    llm = [x for x in rows if x.get("model")]
    lat = [x["latency_ms"] for x in rows]
    return {"n": len(rows), "llm_calls": len(llm), "input_tokens": sum(x.get("input_tokens") or 0 for x in rows),
            "output_tokens": sum(x.get("output_tokens") or 0 for x in rows), "cost_usd": round(sum(x.get("cost_usd") or 0 for x in rows), 5),
            "latency_ms_median": statistics.median(lat) if lat else None, "escalations": sum(1 for x in rows if x.get("escalations")),
            "fallbacks": sum(1 for x in rows if x.get("fallback")),
            "claims_kept": sum(x["claims_kept"] for x in rows), "claims_dropped": sum(x["claims_dropped"] for x in rows),
            "by_model": {m: sum(1 for x in llm if x["model"] == m) for m in sorted({x["model"] for x in llm})}}


def run(live=False, baseline=False):
    raw = open(CASES, "rb").read()
    lock = open(os.path.join(HERE, "eval", "ROUTING.lock")).read().strip()
    cases = json.loads(raw)["cases"]
    key = os.environ.pop("ANTHROPIC_API_KEY", None) if not live else os.environ.get("ANTHROPIC_API_KEY")
    if live and not key:
        live = False
    router._cache.clear()
    acc = []
    for c in cases:  # Part A: routing only (no key -> no API call; the selected tier is still recorded)
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        r = copilot.ask(c["q"], None, "SC-ORBITAL", "auto", "eval-routing")
        if saved: os.environ["ANTHROPIC_API_KEY"] = saved
        t = observed_tier(r)
        acc.append({"id": c["id"], "kind": c["kind"], "expected": c["expected_tier"], "routed": t, "correct": t == c["expected_tier"],
                    "reason": r.get("routing", {}).get("reason")})
    router._cache.clear()
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "case_file_sha256": hashlib.sha256(raw).hexdigest(),
           "lock_matches": hashlib.sha256(raw).hexdigest() == lock, "config": router.config(),
           "routing_accuracy": {"n": len(acc), "correct": sum(a["correct"] for a in acc),
                                "by_expected_tier": {t: {"n": sum(1 for a in acc if a["expected"] == t), "correct": sum(1 for a in acc if a["expected"] == t and a["correct"])} for t in (0, 1, 2, 3)},
                                "confusion": {f"{e}->{o}": sum(1 for a in acc if a["expected"] == e and a["routed"] == o) for e in (0, 1, 2, 3) for o in (0, 1, 2, 3) if any(a["expected"] == e and a["routed"] == o for a in acc)},
                                "cases": acc},
           "live": {"status": "not run", "reason": "ANTHROPIC_API_KEY not set on this server" if not key else "run with --live"}}
    if key and not live:
        os.environ["ANTHROPIC_API_KEY"] = key
    if live:
        os.environ.setdefault("SXS_DAILY_BUDGET_USD", "5")
        router.BUDGET_USD = max(router.BUDGET_USD, float(os.environ["SXS_DAILY_BUDGET_USD"]))
        router.RATE = 10_000
        router.check_models()

        def answer(mode):
            rows = []
            for c in cases:
                t0 = time.time(); r = copilot.ask(c["q"], None, "SC-ORBITAL", mode, f"eval-{mode}"); rt = r.get("routing", {})
                rows.append({"id": c["id"], "mode": r.get("mode"), "tier": rt.get("tier"), "model": rt.get("model"), "input_tokens": rt.get("input_tokens"),
                             "output_tokens": rt.get("output_tokens"), "cost_usd": rt.get("cost_usd"), "latency_ms": round((time.time() - t0) * 1000),
                             "escalations": rt.get("escalations") or [], "fallback": rt.get("fallback"),
                             "claims_kept": len(r.get("claims") or []), "claims_dropped": len(r.get("dropped") or []),
                             "citations_all_retrieved": all(set(x["citations"]) <= {e["id"] for e in r.get("evidence") or []} for x in r.get("claims") or []),
                             "abstained": bool(r.get("abstained")) or r.get("mode") in ("no-evidence", "boundary")})
                router._cache.clear()
            return rows
        auto = answer("auto")
        out["live"] = {"status": "run", "auto": {"summary": summarise(auto), "cases": auto}}
        if baseline:
            deep = answer("deep")
            llm_ids = {x["id"] for x in auto if x["model"]}
            a = summarise([x for x in auto if x["id"] in llm_ids]); d = summarise([x for x in deep if x["id"] in llm_ids])
            out["live"]["deep_baseline"] = {"summary": summarise(deep), "cases": deep,
                                            "same_questions_llm_only": {"auto": a, "deep": d, "note": "Measured on the same questions in this run. Quality is compared by claim checks only, not by expert review."}}
    json.dump(out, open(OUT, "w"), indent=1)
    return out


if __name__ == "__main__":
    o = run("--live" in sys.argv, "--baseline" in sys.argv)
    ra = o["routing_accuracy"]
    print(f"routing accuracy {ra['correct']}/{ra['n']}", ra["by_expected_tier"], ra["confusion"])
    for a in ra["cases"]:
        if not a["correct"]:
            print("  MISS", a["id"], a["expected"], "->", a["routed"], a["reason"])
    print("live:", o["live"]["status"])
