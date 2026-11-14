"""End-to-end check of a running SpaceXtinsafe backend. Standard library only, so it runs anywhere with Python 3.9+.

Usage:
  python scripts/check_deployed.py https://spacextinsafe.onrender.com
  python scripts/check_deployed.py http://localhost:8000

Writes eval/validation/deployed_check_<host>_<UTC>.json, .csv and .md next to this script's backend folder.
Each check is labelled LIVE (calls Claude or Neo4j at run time), DETERMINISTIC (computed by the server without an LLM)
or RECORDED (reads stored evaluation results). Inputs are generated at run time; created records are deleted at the end.
Live Claude checks spend a few cents of API budget on the server's key.
"""
import csv, datetime, hashlib, json, os, random, re, string, sys, time, urllib.error, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
STAMP = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
NOW = datetime.datetime.now(datetime.timezone.utc)
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval", "validation")
SAFE = re.compile(r"\b(is|are|it's)\s+(safe|non-flammable)\b|\bwill not burn\b|\bno fire risk\b", re.I)


def call(method, path, body=None, timeout=120, raw=False):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "sxs-check-deployed"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read(); ms = round((time.time() - t0) * 1000)
            return r.status, (b if raw else json.loads(b or b"null")), ms
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode(errors="replace"), round((time.time() - t0) * 1000)


RES = []


def check(n, name, kind, fn):
    t0 = time.time()
    try:
        ok, detail, evidence = fn()
    except Exception as e:  # recorded as a failure, never hidden
        ok, detail, evidence = False, f"{type(e).__name__}: {e}", {}
    RES.append({"n": n, "check": name, "kind": kind, "passed": bool(ok), "detail": detail, "seconds": round(time.time() - t0, 1), "evidence": evidence})
    print(f"[{'PASS' if ok else 'FAIL'}] {n:>2} {kind:<13} {name}: {detail}")


def wake():
    for i in range(12):  # free Render instances sleep; allow ~2 minutes to wake
        try:
            s, b, ms = call("GET", "/api/health", timeout=20)
            if s == 200:
                return True, f"healthy after {i} retries ({ms} ms)", {"health": b}
        except Exception:
            pass
        time.sleep(10)
    return False, "no healthy response in ~2 minutes", {}


ST = {}


def status():
    s, b, _ = call("GET", "/api/status")
    ST.update(b if s == 200 else {})
    c, g, sem = b["copilot"], b["graph"], b["semantic"]
    ev = {"claude_verified_live": c.get("verified_live"), "key_configured": c.get("key_configured"), "last_error": c.get("last_error"),
          "graph_engine": g.get("engine"), "graph_mode": g.get("mode"), "neo4j_error": g.get("error"), "semantic_enabled": sem.get("enabled"),
          "evidence": b["data"]["evidence"], "flex_tests": b["data"]["flex_tests"]}
    return s == 200, f"Claude live={ev['claude_verified_live']}, graph={ev['graph_engine']}, semantic={ev['semantic_enabled']}", ev


def neo4j():
    s, b, ms = call("POST", "/api/status/neo4j/verify", {}, timeout=90)
    return s == 200 and b.get("verified") is True, f"verified={b.get('verified')} {b.get('reason') or ''} ({ms} ms)", b if isinstance(b, dict) else {"body": b}


def copilot(q, sid=None, mode="auto"):
    s, b, ms = call("POST", "/api/copilot", {"question": q, "spacecraft_id": sid, "mode": mode}, timeout=120)
    if s != 200:
        raise RuntimeError(f"HTTP {s}: {b}")
    return b, ms


def live_answer(q, want, sid=None):
    def f():
        b, ms = copilot(q, sid)
        cited = sorted({x for cl in b.get("claims", []) for x in cl["citations"]}); got = {e["id"] for e in b.get("evidence", [])}
        rt = b.get("routing") or {}
        ok = b["mode"] == "claude" and cited and set(cited) <= got and bool(set(cited) & set(want)) and not SAFE.search(b.get("answer", ""))
        return ok, f"mode={b['mode']} model={rt.get('model')} cited={cited} graph={b.get('graph_engine')} {ms} ms", \
            {"answer": b.get("answer", "")[:700], "cited": cited, "retrieved": sorted(got), "routing": rt, "graph_engine": b.get("graph_engine"), "dropped": len(b.get("dropped", []))}
    return f


def det_copilot(q, expect):
    def f():
        b, ms = copilot(q)
        rt = b.get("routing") or {}
        ok = {"boundary": bool(b.get("boundary_triggered")), "abstain": b["mode"] in ("no-evidence", "abstain"),
              "tool": rt.get("tier") == 0 or b["mode"] in ("tool", "deterministic")}[expect]
        return ok, f"mode={b['mode']} tier={rt.get('tier')} boundary={b.get('boundary_triggered')} ({ms} ms)", {"answer": (b.get("answer") or "")[:400], "routing": rt}
    return f


CREATED = {"materials": [], "spacecraft": []}


def custom_spacecraft():
    s, sc, _ = call("POST", "/api/spacecraft", {"mode": "quick", "template_id": "TPL-ORBITAL", "name": f"Validation module {STAMP}"})
    if s != 200:
        s, sc, _ = call("POST", "/api/spacecraft", {"mode": "scratch", "name": f"Validation module {STAMP}"})
    CREATED["spacecraft"].append(sc["id"])
    o2 = round(random.uniform(23, 26), 1); kpa = round(random.uniform(70, 95), 1)
    sc["atmosphere"].update(o2_pct=o2, pressure_kpa=kpa)
    s2, sc2, _ = call("PUT", f"/api/spacecraft/{sc['id']}", sc)
    s3, scr, _ = call("GET", f"/api/spacecraft/{sc['id']}/screen")
    rows = scr.get("rows", []) if isinstance(scr, dict) else []
    ok = s2 == 200 and sc2["atmosphere"]["o2_pct"] == o2 and s3 == 200 and len(rows) > 0
    return ok, f"{sc['id']} at {o2}% O2 / {kpa} kPa, {len(rows)} components screened", {"id": sc["id"], "o2": o2, "kpa": kpa, "components": len(rows)}


def custom_material():
    s, b, _ = call("POST", "/api/materials", {"name": f"Validation felt {STAMP}", "form": "felt", "composition": "basalt fibre"})
    CREATED["materials"].append(b["material"]["id"])
    st = b["status"]["status"]
    ok = s == 200 and st.startswith("User-defined") and b.get("gap_created") is True and not b["status"]["direct_findings"]
    return ok, f"status='{st}', gap_created={b.get('gap_created')}", {"status": b["status"], "library_search_ids": [r["id"] for r in b.get("library_search", [])]}


def alias_collision():
    s, b, _ = call("POST", "/api/materials", {"name": f"Validation alias {STAMP}", "form": "sheet", "aliases": ["PMMA"]})
    CREATED["materials"].append(b["material"]["id"])
    s2, m, _ = call("GET", "/api/materials/MAT-PMMA")
    st = m["status"]["status"] if s2 == 200 else m
    return st.startswith("Verified"), f"PMMA status after a user alias 'PMMA' was added: '{st}'", {"status": st}


def predict(req, want):
    def f():
        s, b, ms = call("POST", "/api/predict", req)
        out = b.get("outcome") if isinstance(b, dict) else f"HTTP {s}"
        ok = s == 200 and (out == want if want != "not Model-supported" else out != "Model-supported estimate")
        return ok, f"outcome={out} estimate={b.get('estimate') if isinstance(b, dict) else None}", {"response": {k: b.get(k) for k in ("outcome", "estimate", "interval_90", "reasons")} if isinstance(b, dict) else b}
    return f


def gaps():
    s, b, _ = call("GET", "/api/gaps/gravity")
    cell = lambda m, band: next(c for c in b["cells"] if c["material_id"] == m and c["band"] == band)
    p, sb = cell("MAT-PMMA", "partial gravity"), cell("MAT-SIBAL", "partial gravity")
    ok = s == 200 and p["count"] == 0 and sb["count"] > 0 and "library" in b["note"].lower() and "needed" in b
    return ok, f"PMMA partial-g: {p['kind']}; SIBAL partial-g: {sb['kind']} {sb['ids']}", {"note": b["note"], "needed": b.get("needed")}


def interactions():
    a = call("POST", "/api/interactions", {"material_ids": ["MAT-PMMA", "MAT-NOMEX"]})[1]
    c = call("POST", "/api/interactions", {"material_ids": ["MAT-POLYESTER", "MAT-PU"]})[1]
    ok = a["status"] == "Documented interaction" and c["status"].startswith("No documented") and "not evidence" in c["note"]
    return ok, f"PMMA+Nomex: {a['status']}; polyester+PU: {c['status']}", {"documented_ids": [e["id"] for e in a["documented_interactions"]], "note": c["note"]}


def pdf():
    sid = CREATED["spacecraft"][0] if CREATED["spacecraft"] else "SC-ORBITAL"
    s1, p1, ms1 = call("POST", "/api/report", {"spacecraft_id": sid}, raw=True, timeout=120)
    s2, p2, ms2 = call("POST", "/api/report", {"spacecraft_id": sid, "scenario": {"material_id": "MAT-PMMA", "form": "sheet", "o2_pct": 30, "pressure_kpa": 70, "gravity": "microgravity", "flow_cm_s": 5}}, raw=True, timeout=120)
    h1, h2 = hashlib.sha256(p1).hexdigest()[:12], hashlib.sha256(p2).hexdigest()[:12]
    ok = s1 == s2 == 200 and p1[:4] == b"%PDF" and p2[:4] == b"%PDF" and h1 != h2 and len(p1) != len(p2)
    return ok, f"two PDFs {len(p1)} / {len(p2)} bytes, sha {h1} / {h2} ({ms1} / {ms2} ms)", {"bytes": [len(p1), len(p2)], "sha": [h1, h2],
            "note": "Sizes differ when the scenario section is added; the generation timestamp alone also changes the hash."}


def recorded():
    s, b, _ = call("GET", "/api/evaluation")
    cl = (b or {}).get("claude_live", {})
    return s == 200 and b.get("status") != "not run", f"stored results present; live Claude run {cl.get('generated_utc', 'n/a')}: {cl.get('n_passed')}/{cl.get('n_cases')}", {"claude_live_generated": cl.get("generated_utc")}


def usage():
    s, b, _ = call("GET", "/api/copilot/usage")
    return s == 200, f"{json.dumps(b)[:160]}", b if isinstance(b, dict) else {}


def cleanup():
    out = []
    for m in CREATED["materials"]:
        out.append(call("DELETE", f"/api/materials/{m}")[0])
    for sc in CREATED["spacecraft"]:
        out.append(call("DELETE", f"/api/spacecraft/{sc}")[0])
    return all(x == 200 for x in out), f"deleted {len(out)} test records", {}


if __name__ == "__main__":
    print(f"SpaceXtinsafe deployed check against {BASE} at {NOW.isoformat(timespec='seconds')}")
    M = dict(material_form="liquid droplet", fuel="methanol", pressure_kpa=101.3, diluent="nitrogen", gravity="microgravity")
    check(1, "Backend reachable (cold start allowed)", "DETERMINISTIC", wake)
    check(2, "Service status", "DETERMINISTIC", status)
    check(3, "Neo4j retrieval verified against in-memory graph", "LIVE (Neo4j)", neo4j)
    check(4, "Claude answer with checked citations (Saffire-II sample 2-7)", "LIVE (Claude)", live_answer("What happened to the Nomex next to the PMMA in Saffire-II sample 2-7?", ["EV-SAF-08"]))
    check(5, "Claude + graph: sleeping bag composition evidence", "LIVE (Claude)", live_answer("What NASA evidence exists for the materials in the sleeping bag?", ["EV-SAF-08", "EV-SAF6-01"], "SC-ORBITAL"))
    check(6, "Claude: conflicting evidence question", "LIVE (Claude)", live_answer("Is there any conflicting evidence about Saffire-II flow velocity?", ["EV-SAF-06", "EV-SAF-09"]))
    check(7, "Custom spacecraft with a random atmosphere", "DETERMINISTIC", custom_spacecraft)
    check(8, "Custom material creates a library gap, not evidence", "DETERMINISTIC", custom_material)
    check(9, "User alias cannot remove catalogue evidence (PMMA)", "DETERMINISTIC", alias_collision)
    check(10, "Supported prediction (methanol 21% O2, 2.5 mm)", "DETERMINISTIC", predict({**M, "o2_pct": 21, "d0_mm": 2.5}, "Model-supported estimate"))
    check(11, "Untested combination is not model-supported (30% O2, 1.7 mm)", "DETERMINISTIC", predict({**M, "o2_pct": 30, "d0_mm": 1.7}, "not Model-supported"))
    check(12, "Out-of-range O2 refused (45%)", "DETERMINISTIC", predict({**M, "o2_pct": 45, "d0_mm": 2.5}, "Unavailable"))
    check(13, "Non-numeric input refused without a server error", "DETERMINISTIC", predict({**M, "o2_pct": "abc", "d0_mm": 2.5}, "Unavailable"))
    check(14, "Solid fabric refused by the droplet model", "DETERMINISTIC", predict({**M, "material_form": "fabric", "o2_pct": 21, "d0_mm": 2.5}, "Unavailable"))
    check(15, "Research gaps by gravity", "DETERMINISTIC", gaps)
    check(16, "Interaction status and gap wording", "DETERMINISTIC", interactions)
    check(17, "Dynamic PDF report changes with inputs", "DETERMINISTIC", pdf)
    check(18, "Emergency instruction refused (boundary)", "DETERMINISTIC", det_copilot("What should the crew do first if a fire breaks out in the galley?", "boundary"))
    check(19, "Unsupported question abstains (Kevlar)", "DETERMINISTIC", det_copilot("How flammable is Kevlar in microgravity?", "abstain"))
    check(20, "Calculation answered by a tool, no LLM", "DETERMINISTIC", det_copilot("What is the oxygen partial pressure at 21% O2 and 101.3 kPa?", "tool"))
    check(21, "Stored evaluation results served", "RECORDED", recorded)
    check(22, "Usage and cost log", "DETERMINISTIC", usage)
    check(23, "Clean up test records", "DETERMINISTIC", cleanup)
    os.makedirs(OUTDIR, exist_ok=True)
    host = re.sub(r"[^a-z0-9]+", "-", BASE.split("//")[-1].lower()).strip("-")
    stem = os.path.join(OUTDIR, f"deployed_check_{host}_{NOW.strftime('%Y%m%dT%H%M%SZ')}")
    summary = {"base": BASE, "generated_utc": NOW.isoformat(timespec="seconds"), "passed": sum(r["passed"] for r in RES), "n": len(RES),
               "by_kind": {k: f"{sum(r['passed'] for r in RES if r['kind'] == k)}/{sum(r['kind'] == k for r in RES)}" for k in sorted({r['kind'] for r in RES})},
               "status": ST.get("copilot", {}) and {"claude_verified_live": ST["copilot"].get("verified_live"), "graph": ST.get("graph", {}).get("engine"), "semantic": ST.get("semantic", {}).get("enabled")},
               "checks": RES}
    json.dump(summary, open(stem + ".json", "w"), indent=1)
    with open(stem + ".csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["n", "check", "kind", "passed", "detail", "seconds"])
        for r in RES:
            w.writerow([r["n"], r["check"], r["kind"], r["passed"], r["detail"], r["seconds"]])
    with open(stem + ".md", "w", encoding="utf-8") as f:
        f.write(f"# Deployed check: {BASE}\n\nRun {summary['generated_utc']}. Passed {summary['passed']}/{summary['n']}. By kind: {summary['by_kind']}.\n\n| # | Check | Kind | Result | Detail |\n|---|---|---|---|---|\n")
        for r in RES:
            f.write(f"| {r['n']} | {r['check']} | {r['kind']} | {'PASS' if r['passed'] else 'FAIL'} | {r['detail'].replace('|', '/')} |\n")
    print(f"\n{summary['passed']}/{summary['n']} passed. {summary['by_kind']}\nWrote {stem}.json / .csv / .md")
