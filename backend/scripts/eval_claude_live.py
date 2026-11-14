"""Live Claude Copilot evaluation. Runs only when ANTHROPIC_API_KEY is set; otherwise writes status 'not run'.
Usage: python -m scripts.eval_claude_live [--judge]   (results -> eval/results_claude_live.json)"""
import os as _os, tempfile as _tf
_os.environ.setdefault("SXS_USAGE_LOG", _os.path.join(_tf.gettempdir(), "sxs_eval_usage.jsonl"))  # keep evaluation calls out of the server usage log
import json, os, re, sys, datetime, hashlib
from app.core import copilot
E = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval")
OUT = f"{E}/results_claude_live.json"


def judge(question, claim, ev):
    """Optional LLM entailment check (same model family; indicative only)."""
    import anthropic
    from app.core import router
    cl = router.client(60)
    txt = "\n".join(f"[{e['id']}] {e['statement']} QUOTE: {e['quote']}" for e in ev)
    m = cl.messages.create(model=copilot.MODEL, max_tokens=20, messages=[{"role": "user", "content":
        f"Evidence:\n{txt}\n\nClaim: {claim}\n\nIs the claim fully entailed by the evidence? Answer only ENTAILED or NOT_ENTAILED."}])
    return "NOT" not in "".join(b.text for b in m.content if getattr(b, "type", "") == "text").upper()


def run(use_judge=False):
    cases = json.load(open(f"{E}/claude_live_cases.json"))["cases"]
    from app.core import router
    if not router.api_key():
        res = {"status": "not run", "reason": "ANTHROPIC_API_KEY not set on this server", "n_cases": len(cases)}
        json.dump(res, open(OUT, "w"), indent=1); return res
    rows = []
    router._cache.clear(); router.RATE = 10_000; router.BUDGET_USD = max(router.BUDGET_USD, 5.0)
    import time as _t
    for c in cases:
        t0 = _t.time(); r = copilot.ask(c["q"], None, None, "auto", "eval-claude-live"); rt = r.get("routing", {})
        retrieved = {e["id"] for e in r.get("evidence", [])}
        cited = sorted({x for cl in r.get("claims", []) for x in cl["citations"]})
        row = {"id": c["id"], "expected": c["expected"], "mode": r["mode"], "cited": cited, "claims": len(r.get("claims", [])), "dropped": len(r.get("dropped", [])),
               "answer": r.get("answer", "")[:600], "latency_ms": round((_t.time() - t0) * 1000), "model": rt.get("model"), "tier": rt.get("tier"),
               "input_tokens": rt.get("input_tokens") or 0, "output_tokens": rt.get("output_tokens") or 0, "cost_usd": rt.get("cost_usd") or 0.0,
               "fallback": rt.get("fallback"), "escalations": rt.get("escalations") or []}
        if c["expected"] == "answer":
            row["live_claude_used"] = r["mode"] == "claude"
            row["citation_correct"] = bool(cited) and all(x in retrieved for x in cited)
            row["citation_completeness"] = len(set(cited) & set(c["expect_cites"])) / len(c["expect_cites"])
            row["numbers_ok"] = all(n in r.get("answer", "") for n in c.get("numbers", []))
            row["conditions_ok"] = all(t.lower() in r.get("answer", "").lower() for t in c.get("condition_terms", []))
            row["unsupported_numbers_removed"] = row["dropped"]
            if use_judge and r["mode"] == "claude":
                evm = {e["id"]: e for e in r["evidence"]}
                ent = [judge(c["q"], cl["text"], [evm[x] for x in cl["citations"] if x in evm]) for cl in r["claims"]]
                row["judge_entailed"] = f"{sum(ent)}/{len(ent)}"
            row["passed"] = row["live_claude_used"] and row["citation_correct"] and row["citation_completeness"] > 0 and row["numbers_ok"]
        elif c["expected"] == "abstain":
            row["passed"] = r["mode"] in ("no-evidence", "abstain") or (r["mode"] == "claude" and not r.get("claims"))
        else:
            row["passed"] = bool(r.get("boundary_triggered"))
        rows.append(row)
    ans = [x for x in rows if x["expected"] == "answer"]
    llm = [x for x in rows if x["model"]]
    lat = sorted(x["latency_ms"] for x in llm) or [0]
    kept = sum(x["claims"] for x in ans); dropped = sum(x["dropped"] for x in ans)
    res = {"status": "run", "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "models": router.config()["tiers"],
           "case_file_sha256": hashlib.sha256(open(f"{E}/claude_live_cases.json", "rb").read()).hexdigest(),
           "n_cases": len(rows), "n_passed": sum(x["passed"] for x in rows),
           "answer_cases": {"n": len(ans), "live_claude_used": sum(x["live_claude_used"] for x in ans), "citation_correct": sum(x["citation_correct"] for x in ans),
                            "mean_citation_completeness": round(sum(x["citation_completeness"] for x in ans) / max(1, len(ans)), 3),
                            "numbers_ok": sum(x["numbers_ok"] for x in ans), "conditions_ok": sum(x["conditions_ok"] for x in ans),
                            "claims_removed_by_checks": sum(x["dropped"] for x in ans)},
           "live_success_rate": {"answer_cases_answered_by_claude": f'{sum(x["live_claude_used"] for x in ans)}/{len(ans)}', "api_fallbacks": sum(1 for x in rows if x["fallback"])},
           "claim_support_rate": round(kept / (kept + dropped), 3) if kept + dropped else None,
           "latency_ms_llm": {"median": lat[len(lat) // 2], "max": lat[-1]},
           "tokens": {"input": sum(x["input_tokens"] for x in rows), "output": sum(x["output_tokens"] for x in rows)},
           "estimated_cost_usd": round(sum(x["cost_usd"] for x in rows), 5),
           "by_model": {m: sum(1 for x in llm if x["model"] == m) for m in sorted({x["model"] for x in llm})},
           "abstain": {"n": sum(x["expected"] == "abstain" for x in rows), "passed": sum(x["passed"] for x in rows if x["expected"] == "abstain")},
           "boundary": {"n": sum(x["expected"] == "boundary" for x in rows), "passed": sum(x["passed"] for x in rows if x["expected"] == "boundary")},
           "judge": "LLM entailment judge used (same model family; indicative only)" if use_judge else "No LLM judge",
           "cases": rows, "claude_error": copilot.STATE.get("last_error"),
           "disclosure": "Evaluates the live generative Copilot. Separate from the deterministic retrieval evaluation. 15 cases written before the first live run; small set, indicative only."}
    json.dump(res, open(OUT, "w"), indent=1)
    return res


if __name__ == "__main__":
    r = run("--judge" in sys.argv)
    print({k: r[k] for k in r if k not in ("cases",)})