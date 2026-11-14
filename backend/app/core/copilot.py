"""Scientific Copilot. Claude (when ANTHROPIC_API_KEY is set on the server) writes the answer from retrieved NASA evidence only;
every claim is then checked: cited IDs must be among the retrieved evidence and every number in a claim must appear in
the cited evidence. Failing claims are removed and listed. Without a key (or on any API error) the answer is an
evidence-retrieval summary, and the response says which mode produced it.
"""
from __future__ import annotations
import json, os, re, time
from . import retrieval, data, models, store, router

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
STATE = {"mode": "claude" if os.environ.get("ANTHROPIC_API_KEY") else "evidence-retrieval", "last_error": None, "verified_live": False}
OPERATIONAL = re.compile(r"\b(steps to|procedure (for|to)|should (the )?crew|should we|vent(ing)? the cabin|depressuri[sz]|isolate (the )?power|cut (the )?power|shut (off|down)|turn off (the )?(ventilation|fans?|oxygen)|activate (the )?suppression)\b", re.I)
QUANT = re.compile(r"\b(predict|estimate|forecast|calculate|compute|how fast will|what will (the|its))\b", re.I)
INTERACT = re.compile(r"\b(together|each other|adjacent|next to|combined|interact\w*|in contact)\b", re.I)
PROPERTY = re.compile(r"\b(melting point|boiling point|ignition temperature|autoignition|flash point|thermal conductivity|density|specific heat|heat of combustion|toxicity|tensile|modulus)\b", re.I)
GENERIC = set("what which how does did do is are was were the a an of in on for to and or with by at from about this that these those there any some known know nasa evidence research find found findings say says show shows study studied data result results experiment experiments test tests spacecraft space fire fires flame flames burn burning burns combustion material materials happen happens happened when why can could would will should relate relates related relevant apply applies applicable regarding concern concerning cover covers information tell explain describe".split())


def _stem(w):
    return w[:5]


def salient_overlap(question, evidence, spacecraft_id=None):
    # words naming spacecraft elements are handled by graph traversal, so they are not required to appear in the evidence
    names = set()
    for sc in store.list_spacecraft():
        names |= set(retrieval.tok(sc["name"]))
        for c in sc["compartments"]:
            names |= set(retrieval.tok(c["name"]))
            for o in c["objects"]:
                names |= set(retrieval.tok(o["name"])) | {w for k in o["components"] for w in retrieval.tok(k["name"])}
    q = [w for w in retrieval.tok(question) if w not in GENERIC and w not in names and len(w) > 2]
    if not q:
        return 1.0, []
    text = " ".join(retrieval.doc_text(e).lower() for e in evidence)
    toks = {_stem(t) for t in retrieval.tok(text)}
    hit = [w for w in q if _stem(w) in toks]
    return len(hit) / len(q), [w for w in q if w not in hit]


BOUNDARY = re.compile(r"\b(is|are|was|were)\b[^?.]{0,60}\bsafe\b|\bunsafe\b|\bsafe to\b|fire[- ]risk (score|percent|percentage|probability)|probability of (a )?fire|what should (the )?crew do|\bevacuat|emergency procedure|how (do|should|can) (we|i|they|the crew) (put out|extinguish|fight)", re.I)
SYSTEM = ("You are SpaceXtinsafe's scientific copilot. Answer ONLY from the NASA evidence provided. Return JSON: "
          '{"claims":[{"text":"...","citations":["EV-..."]}],"limitations":"..."}. Every claim needs at least one citation from the provided IDs. '
          "Copy numbers exactly as written in the evidence. Never give safe/unsafe verdicts, fire-risk percentages, or emergency or operational instructions. "
          "Related evidence is not enough: if the evidence does not directly answer the question, return no claims and explain in limitations. "
          "State experimental conditions (gravity, O2, flow, sample form) when you report a measurement.")


def _nums(s):
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", s)}


def check_claims(claims, retrieved):
    evm = {e["id"]: e for e in retrieved}; kept, dropped = [], []
    for c in claims:
        cites = [x for x in c.get("citations", []) if x in evm]
        problems = []
        if not c.get("citations"):
            problems.append("no citation")
        if len(cites) < len(c.get("citations", [])):
            problems.append("cites evidence that was not retrieved")
        src = " ".join(evm[x]["statement"] + " " + evm[x]["quote"] for x in cites)
        bad = [n for n in _nums(c.get("text", "")) if n not in _nums(src)]
        if bad:
            problems.append(f"numbers not in cited evidence: {', '.join(sorted(bad))}")
        (dropped if problems else kept).append({**c, "citations": cites, **({"problems": problems} if problems else {})})
    return kept, dropped


def _abstain(reason, question, related=None, kind="no-evidence"):
    return {"mode": kind, "answer": reason, "claims": [], "dropped": [], "evidence": related or [], "abstained": True}


APP_HELP = ("SpaceXtinsafe modules: Mission overview; Design Studio (build/edit spacecraft, custom materials); Digital twin (cutaway with "
            "evidence, gap, conflict, interaction and sensor overlays); Material inventory; Mission Workspace (question + conditions -> evidence, "
            "applicability, insights, eligibility-checked prediction); Evidence library (keyword/semantic/hybrid/graph search; NASA investigations "
            "and datasets tab); Knowledge graphs (multi-hop traces, Neo4j sync); Virtual Fire Lab (L1 material intelligence, L2 interactions, FLEX "
            "droplet models, L3 future simulation); Research gaps by dimension; Compare scenarios (configurations or atmospheres with O2 partial "
            "pressure); Evidence audit; Incident intelligence (simulated replays, procedure registry); AI Evaluation Centre; Mission reports (PDF). "
            "Prediction eligibility: missing inputs, physical validity, condition compatibility, pressure band, convex hull, nearest-neighbour "
            "distance and local coverage -> Model-supported, Exploratory or Unavailable. The tool gives no safety verdicts or emergency instructions.")
APP_SYSTEM = ("You are the SpaceXtinsafe app guide. Answer in at most 4 sentences using ONLY the app description provided. Do not make "
              "scientific or numerical claims about combustion; for science, tell the user to ask a scientific question. Return JSON: "
              '{"answer":"..."}')


def _call(tier, system, user):
    cl = router.client(60 if tier == 3 else 40)
    msg = cl.messages.create(model=router.model_for(tier), max_tokens=router.TIERS[tier]["max_tokens"], system=system,
                             messages=[{"role": "user", "content": user}])
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    u = getattr(msg, "usage", None)
    tin, tout = (getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0)
    return json.loads(txt[txt.find("{"): txt.rfind("}") + 1]), tin, tout


def _evidence_fallback(ev, r, why):
    claims = [{"text": e["statement"], "citations": [e["id"]]} for e in ev[:3]]
    return {"mode": "evidence-retrieval", "answer": " ".join(c["text"] for c in claims), "claims": claims, "dropped": [],
            "limitations": f"{why}; showing the top retrieved NASA findings verbatim.", "evidence": ev, "retrieval_mode": r["mode"] if r else None, "graph_engine": r.get("graph_engine") if r else None}


def ask(question: str, scenario: dict | None = None, spacecraft_id: str | None = None, mode: str = "auto", client: str | None = None):
    t0 = time.time()
    mode = mode if mode in ("auto", "fast", "deep") else "auto"
    ck = router.cache_key(question.strip().lower(), scenario, spacecraft_id, mode)
    hit = router.cache_get(ck)
    if hit:
        hit["routing"] = {**hit.get("routing", {}), "cached": True, "latency_ms": round((time.time() - t0) * 1000)}
        router.record({"engine": hit["routing"].get("engine"), "model": hit["routing"].get("model"), "tier": hit["routing"].get("tier"),
                       "reason": "cache hit", "cached": True, "latency_ms": hit["routing"]["latency_ms"], "copilot_mode": mode})
        return hit
    res = _ask(question, scenario, spacecraft_id, mode, client)
    rt = res.setdefault("routing", {})
    rt.setdefault("tier", 0); rt.setdefault("engine", "Python (no LLM)"); rt.setdefault("model", None)
    rt.update(copilot_mode=mode, latency_ms=round((time.time() - t0) * 1000), cached=False, evidence_retrieved=len(res.get("evidence") or []))
    router.record({k: rt.get(k) for k in ("engine", "model", "tier", "reason", "input_tokens", "output_tokens", "cost_usd", "latency_ms",
                                          "evidence_retrieved", "escalations", "fallback", "copilot_mode")} | {"result_mode": res.get("mode")})
    if res.get("mode") in ("claude", "deterministic", "boundary", "no-evidence"):
        router.cache_put(ck, res)
    return res


def _ask(question, scenario, spacecraft_id, mode, client):
    if BOUNDARY.search(question) or OPERATIONAL.search(question):
        return {"mode": "boundary", "answer": "SpaceXtinsafe does not give safety verdicts, fire-risk scores or emergency instructions. "
                "It can show what NASA research found for the materials and conditions you choose. For operational decisions, use the vehicle's "
                "authorised procedures and qualified fire-safety experts.", "claims": [], "dropped": [], "evidence": [], "boundary_triggered": True,
                "routing": {"reason": "boundary rule (verdict, risk score or operational instruction requested)"}}
    det = router.deterministic(question, scenario, spacecraft_id)
    if det:
        det.setdefault("evidence", []); det.setdefault("dropped", [])
        det["routing"] = {"reason": f"deterministic tool: {det['tool']}"}
        return det
    kind = router.kind_of(question)
    if kind == "app":
        return _app(question, mode, client)
    r = retrieval.search(question, "auto", k=6, spacecraft_id=spacecraft_id)
    ev = r["results"]
    # --- general abstention rules (applied before any answer is written) ---
    from . import analysis
    mats = data.materials()
    named = [m for m in retrieval.entities(question, spacecraft_id) if m in mats]
    if QUANT.search(question):
        fuels = [m for m in named if m in ("MAT-METHANOL", "MAT-HEPTANE")]
        msg = ("Quantitative estimates come only from the eligibility-checked burning-rate models (FLEX droplets: methanol and n-heptane). "
               + ("Use the prediction panel, which checks fuel, form, diluent, gravity, pressure band and joint O2-diameter support." if fuels else
                  f"No validated model exists for {', '.join(mats[m]['name'] for m in named) or 'this request'}, so no number is given."))
        return _routed_abstain(msg, question, kind="no-evidence")
    if len(set(named)) >= 2 and INTERACT.search(question):
        it = analysis.interaction(sorted(set(named)))
        if not it["documented_interactions"]:
            return _routed_abstain(f"No documented interaction between {', '.join(it['materials'])} in the library. {it['note']}", question, it["co_reported"])
    if named and not PROPERTY.search(question):
        st = {m: data.material_status(m) for m in set(named)}
        if all(v["status"] != data.STATUS_ORDER[0] for v in st.values()):
            rel = [e for e in data.evidence() if any(e["id"] in v["related_findings"] for v in st.values())]
            names = ", ".join(mats[m]["name"] for m in st)
            extra = f" Related evidence exists for {', '.join(mats[x]['name'] for v in st.values() for x in v['related_materials'])}, but it does not answer this question directly." if rel else ""
            return _routed_abstain(f"The library has no direct NASA combustion evidence for {names}.{extra} This is a gap in this library, not proof of non-flammability.", question, rel)
    if PROPERTY.search(question):
        prop = PROPERTY.search(question).group(0).lower()
        if not any(prop in (e["statement"] + " " + e["quote"]).lower() for e in ev):
            return _routed_abstain(f"No retrieved NASA evidence reports {prop}; the library does not contain material property data of this kind.", question)
    ov, missing = salient_overlap(question, ev[:3], spacecraft_id)
    sem = retrieval.semantic(question)
    top_cos = sem[0][1] if sem else None
    # Pre-set abstention rule (fixed before evaluation): best cosine < 0.35, or no keyword overlap when semantic is unavailable.
    # Rule added 2026-11-15 after user testing ("What did FLEX investigate?" abstained at cosine 0.30): a question that names a NASA
    # investigation, with every salient word found in evidence retrieved from that same investigation, is not treated as weak.
    inv_named = {e["investigation"] for e in ev[:3] if re.search(r"\b" + re.escape(e["investigation"].split()[0].split("-")[0]) + r"\b", question, re.I)}
    weak = ((top_cos is not None and top_cos < 0.35 and not (inv_named and ov == 1.0))
            or (top_cos is None and not retrieval.bm25(question)) or ov == 0)
    if not ev or weak:
        return {"mode": "no-evidence", "answer": "No NASA evidence in the library answers this question." + (f" Retrieved findings do not mention: {', '.join(missing)}." if missing else ""),
                "claims": [], "dropped": [], "evidence": [], "retrieval_mode": r["mode"], "top_cosine": top_cos, "salient_overlap": ov, "abstained": True,
                "routing": {"reason": "abstained: retrieved evidence does not match the question (no model escalation for missing evidence)"}}
    score, feats = router.complexity(question, ev, named)
    tier, reason = router.choose(question, mode, kind, score, feats)
    routing = {"reason": reason, "complexity": {"score": score, **feats}, "kind": kind, "escalations": [], "fallback": None}
    routing.update(selected_tier=tier, selected_model=router.model_for(tier))
    blocked = _blocked(client)
    if blocked:
        routing.update(fallback=blocked, engine="Evidence retrieval (no LLM)")
        return {**_evidence_fallback(ev, r, blocked), "routing": routing}
    ctx = "\n".join(f"[{e['id']}] ({e['investigation']}, {e['location']}) {e['statement']} QUOTE: \"{e['quote']}\"" for e in ev)
    if scenario:
        ctx += f"\n\nActive scenario: {json.dumps(scenario)}"
    user = f"Evidence:\n{ctx}\n\nQuestion: {question}\n" + ("Keep it brief and plain. " if kind in ("term", "summary") else "") + "Return only JSON."
    ceiling = 1 if mode == "fast" else 3
    tin = tout = 0; usd = 0.0
    while True:
        if not router.usable(tier):
            routing["escalations"].append({"from": router.model_for(tier), "why": "model not available on this API key"})
            if tier < ceiling:
                tier += 1; continue
            routing["fallback"] = "no configured model is available"; return {**_evidence_fallback(ev, r, routing["fallback"]), "routing": routing}
        try:
            j, a, b = _call(tier, SYSTEM, user)
        except Exception as ex:
            STATE.update(last_error=f"{type(ex).__name__}: {str(ex)[:200]}", verified_live=False)
            routing["fallback"] = f"API error on {router.model_for(tier)}: {type(ex).__name__}"
            routing.update(tier=tier, model=router.model_for(tier), engine=f"Claude {router.TIERS[tier]['name']} (failed) → evidence mode",
                           input_tokens=tin, output_tokens=tout, cost_usd=round(usd, 6))
            return {**_evidence_fallback(ev, r, f"Claude is not active: the call failed ({STATE['last_error']})"), "routing": routing}
        c = router.cost(tier, a, b); tin += a; tout += b; usd += c; router.spend(c, a + b)
        kept, dropped = check_claims(j.get("claims", []), ev)
        STATE.update(mode="claude", last_error=None, verified_live=True)
        # escalate only when evidence was judged sufficient but the answer failed the checks or came back empty
        weak = (not kept) or (len(dropped) > len(kept))
        if weak and tier < ceiling and not _blocked(client):
            routing["escalations"].append({"from": router.model_for(tier), "to": router.model_for(tier + 1),
                                           "why": "no claim passed the checks" if not kept else f"{len(dropped)} of {len(kept) + len(dropped)} claims failed the checks"})
            tier += 1; continue
        routing.update(tier=tier, model=router.model_for(tier), engine=f"Claude · {router.TIERS[tier]['name']}",
                       input_tokens=tin, output_tokens=tout, cost_usd=round(usd, 6))
        return {"mode": "claude", "model": router.model_for(tier), "answer": " ".join(c["text"] for c in kept) or "The evidence does not support an answer.",
                "claims": kept, "dropped": dropped, "limitations": j.get("limitations"), "evidence": ev, "retrieval_mode": r["mode"], "graph_engine": r.get("graph_engine"), "routing": routing}


def _blocked(client):
    if not router.api_key():
        return "Claude is not active on this server (no ANTHROPIC_API_KEY)"
    if not router.budget_ok():
        return "daily API spending safeguard reached"
    if not router.rate_ok(client):
        return "request rate limit reached"
    return None


def _routed_abstain(reason, question, related=None, kind="no-evidence"):
    out = _abstain(reason, question, related, kind)
    out["routing"] = {"reason": "abstained: evidence insufficient (no model escalation for missing evidence)"}
    return out


def _app(question, mode, client):
    routing = {"reason": "general application enquiry", "kind": "app", "escalations": [], "fallback": None, "selected_tier": 1, "selected_model": router.model_for(1)}
    blocked = _blocked(client)
    if blocked or not router.usable(1):
        routing.update(fallback=blocked or "lightweight model not available", engine="App description (no LLM)")
        return {"mode": "deterministic", "answer": APP_HELP, "claims": [], "dropped": [], "evidence": [], "tool": "app_description", "routing": routing}
    try:
        j, a, b = _call(1, APP_SYSTEM, f"App description: {APP_HELP}\n\nUser: {question}")
    except Exception as ex:
        routing["fallback"] = f"API error: {type(ex).__name__}"
        return {"mode": "deterministic", "answer": APP_HELP, "claims": [], "dropped": [], "evidence": [], "tool": "app_description", "routing": routing}
    c = router.cost(1, a, b); router.spend(c, a + b)
    ans = str(j.get("answer", ""))[:1200]
    if _nums(ans) - _nums(APP_HELP):  # app answers may not introduce numbers
        ans = APP_HELP; routing["fallback"] = "answer introduced numbers not in the app description"
    routing.update(tier=1, model=router.model_for(1), engine=f"Claude · {router.TIERS[1]['name']}", input_tokens=a, output_tokens=b, cost_usd=c)
    return {"mode": "claude", "model": router.model_for(1), "answer": ans, "claims": [], "dropped": [], "evidence": [], "routing": routing}


def status():
    return {**STATE, "model": router.model_for(2), "key_configured": bool(router.api_key()), "routing": router.config()}