"""Multi-model routing for the Scientific Copilot.

Tier 0  Deterministic Python (no LLM): navigation, O2 partial pressure, inventory, dataset statistics, eligibility-checked
        predictions, boundaries and evidence-based abstention.
Tier 1  Lightweight model (SXS_MODEL_FAST, default claude-haiku-5-5): app enquiries, terminology, simple summaries.
Tier 2  Scientific model (SXS_MODEL_STANDARD, default ANTHROPIC_MODEL or claude-sonnet-5-5): evidence-grounded science.
Tier 3  Advanced model (SXS_MODEL_DEEP, default claude-opus-5-5): conflicts, multi-investigation synthesis, interacting
        materials and conditions.

Routing is rule-based (no model is called to choose a model). Every tier goes through the same claim checks. Missing
evidence abstains; it never escalates. Usage (model, reason, tokens, estimated cost, latency, evidence, escalations,
fallbacks) is appended to a JSONL log next to the database.
"""
from __future__ import annotations
import collections, hashlib, json, os, re, threading, time
from datetime import datetime, timezone

E = os.environ.get
TIERS = {
    1: {"name": "Lightweight", "env": "SXS_MODEL_FAST", "default": "claude-haiku-5-5", "max_tokens": int(E("SXS_MAXTOK_FAST", "500"))},
    2: {"name": "Scientific", "env": "SXS_MODEL_STANDARD", "default": E("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": int(E("SXS_MAXTOK_STANDARD", "900"))},
    3: {"name": "Advanced scientific", "env": "SXS_MODEL_DEEP", "default": "claude-opus-5-5", "max_tokens": int(E("SXS_MAXTOK_DEEP", "1400"))},
}
# USD per million tokens (input, output). Defaults: Anthropic pricing page, standard tier, checked 2026-11-14
# (Haiku 5.5 prompts <= 100k tokens). Override with SXS_PRICE_<FAST|STANDARD|DEEP>="in,out" if prices change.
PRICE_DEFAULT = {1: (0.10, 0.50), 2: (2.0, 10.0), 3: (4.0, 20.0)}
_PK = {1: "FAST", 2: "STANDARD", 3: "DEEP"}


def model_for(t):
    return E(TIERS[t]["env"]) or TIERS[t]["default"]


def price(t):
    v = E(f"SXS_PRICE_{_PK[t]}")
    try:
        return tuple(float(x) for x in v.split(",")) if v else PRICE_DEFAULT[t]
    except ValueError:
        return PRICE_DEFAULT[t]


def cost(t, tin, tout):
    pi, po = price(t)
    return round((tin * pi + tout * po) / 1e6, 6)


# ---------------- model availability (verified against the API, not assumed) ----------------
AVAIL = {"checked": None, "models": {}, "error": None}


def api_key():
    """The key with stray whitespace/quotes removed (common when copied into .env or a dashboard)."""
    return (E("ANTHROPIC_API_KEY") or "").strip().strip('"').strip("'").strip() or None


def client(timeout=40):
    """Anthropic client authenticated ONLY by ANTHROPIC_API_KEY (x-api-key header).
    A blank ANTHROPIC_AUTH_TOKEN in the environment makes the SDK send 'Authorization: Bearer  ', which httpx rejects
    as an illegal header (APIConnectionError). Blank auth tokens are removed; a real one is ignored in favour of the key."""
    import anthropic
    if not (E("ANTHROPIC_AUTH_TOKEN") or "").strip():
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    return anthropic.Anthropic(api_key=api_key(), auth_token=None, timeout=timeout,
                               base_url=(E("ANTHROPIC_BASE_URL") or "").strip() or None)


def check_models():
    key = api_key()
    if not key:
        AVAIL.update(checked=_now(), models={}, error="no ANTHROPIC_API_KEY"); return AVAIL
    try:
        ids = {m.id for m in client(20).models.list(limit=100).data}
        AVAIL.update(checked=_now(), error=None, models={model_for(t): (model_for(t) in ids) for t in TIERS})
    except Exception as ex:
        AVAIL.update(checked=_now(), error=f"{type(ex).__name__}: {str(ex)[:160]}")
    return AVAIL


def usable(t):
    """Unknown availability (not yet checked) counts as usable; a failed call then records a fallback."""
    return AVAIL["models"].get(model_for(t), True)


# ---------------- safeguards: rate limit, daily budget, cache ----------------
RATE = int(E("SXS_RATE_PER_MIN", "20"))           # LLM calls per client per minute
BUDGET_USD = float(E("SXS_DAILY_BUDGET_USD", "2.0"))  # estimated spend per UTC day; beyond it -> evidence mode
BUDGET_TOK = int(E("SXS_DAILY_TOKEN_BUDGET", "400000"))
CACHE_TTL = int(E("SXS_CACHE_TTL_S", "3600"))
_lock = threading.Lock()
_calls = collections.defaultdict(collections.deque)
_cache: "collections.OrderedDict[str, tuple[float, dict]]" = collections.OrderedDict()
_day = {"date": None, "usd": 0.0, "tokens": 0}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rate_ok(client):
    with _lock:
        q, now = _calls[client or "anon"], time.time()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE:
            return False
        q.append(now); return True


def budget_ok():
    d = datetime.now(timezone.utc).date().isoformat()
    with _lock:
        if _day["date"] != d:
            _day.update(date=d, usd=0.0, tokens=0)
        return _day["usd"] < BUDGET_USD and _day["tokens"] < BUDGET_TOK


def spend(usd, tokens):
    with _lock:
        _day["usd"] += usd; _day["tokens"] += tokens


def cache_key(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def cache_get(k):
    with _lock:
        v = _cache.get(k)
        if v and time.time() - v[0] < CACHE_TTL:
            _cache.move_to_end(k); return json.loads(json.dumps(v[1]))
        _cache.pop(k, None)


def cache_put(k, resp):
    with _lock:
        _cache[k] = (time.time(), resp)
        while len(_cache) > 300:
            _cache.popitem(last=False)


# ---------------- monitoring ----------------
def _log_path():
    from . import store
    return E("SXS_USAGE_LOG") or os.path.join(os.path.dirname(store.DB), "copilot_usage.jsonl")


def record(entry):
    try:
        with open(_log_path(), "a") as f:
            f.write(json.dumps({"at": _now(), **entry}) + "\n")
    except OSError:
        pass


def usage(limit=200):
    try:
        rows = [json.loads(x) for x in open(_log_path())][-2000:]
    except OSError:
        rows = []
    by = collections.defaultdict(lambda: {"n": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "latency_ms": []})
    for r in rows:
        b = by[r.get("engine", "?")]
        b["n"] += 1; b["input_tokens"] += r.get("input_tokens") or 0; b["output_tokens"] += r.get("output_tokens") or 0
        b["cost_usd"] += r.get("cost_usd") or 0.0; b["latency_ms"].append(r.get("latency_ms") or 0)
    summ = {k: {**{x: v[x] for x in ("n", "input_tokens", "output_tokens")}, "cost_usd": round(v["cost_usd"], 5),
                "latency_ms_median": sorted(v["latency_ms"])[len(v["latency_ms"]) // 2] if v["latency_ms"] else None} for k, v in by.items()}
    return {"requests": len(rows), "by_engine": summ, "escalations": sum(1 for r in rows if r.get("escalations")),
            "fallbacks": sum(1 for r in rows if r.get("fallback")), "cache_hits": sum(1 for r in rows if r.get("cached")),
            "today": dict(_day), "limits": {"rate_per_min": RATE, "daily_budget_usd": BUDGET_USD, "daily_token_budget": BUDGET_TOK, "cache_ttl_s": CACHE_TTL},
            "recent": rows[-limit:][::-1]}


def config():
    return {"tiers": {t: {"name": TIERS[t]["name"], "model": model_for(t), "env": TIERS[t]["env"], "max_tokens": TIERS[t]["max_tokens"],
                          "price_usd_per_mtok": price(t), "available": AVAIL["models"].get(model_for(t))} for t in TIERS},
            "availability_checked": AVAIL["checked"], "availability_error": AVAIL["error"],
            "price_source": "Anthropic pricing page, standard tier, checked 2026-11-14; override with SXS_PRICE_*"}


# ---------------- routing rules (deterministic) ----------------
NAV = {"twin": r"digital twin|cutaway", "studio": r"design studio|edit (my|the) spacecraft|add (a )?(compartment|object|component|material)|new spacecraft",
       "graph": r"knowledge graph|graph explorer|trace", "workspace": r"mission workspace", "library": r"evidence library|nasa investigations? (coverage|dashboard)",
       "firelab": r"fire lab|droplet model|material interaction", "gaps": r"research gaps?|gap (map|heatmap)", "compare": r"compare (scenario|configuration|atmosphere)s?",
       "audit": r"audit|discrepanc(y|ies) (page|table)", "incidents": r"incident (replay|intelligence)", "evaluation": r"evaluation (cent(re|er)|results)",
       "reports": r"(pdf|mission) report|export (a )?report"}
NAV_Q = re.compile(r"\b(where (can|do|is)|how (do|can) i (open|find|get to|use|export|add|edit|create|generate)|which (page|tab|module)|take me to|go to|open the)\b", re.I)
APP_Q = re.compile(r"\b(what (can|could|do|does) (you|this|the) ?(app|tool|platform|copilot|assistant)? ?(do|offer|help with)?|who are you|what are you|how does (this|the) (app|tool|copilot|routing|eligibility check|applicability|ranking) work|what is spacextinsafe|help me|^help)\b", re.I)
GREET_Q = re.compile(r"^\s*(hey+|hi+|hello+|hiya|yo|howdy|good (morning|afternoon|evening|day)|greetings|thanks?( you)?( so much)?|thank you|ok(ay)?|cool|great|bye|goodbye)( there| copilot| claude)?\s*[!.?]*\s*$", re.I)
HOWTO_Q = re.compile(r"\bhow (do|can|should) (i|we|you)\b|\bhow to\b|\bwhere do i\b|\bsteps? to\b", re.I)
HOWTO = [  # (pattern, page, steps) — application guidance only, never operational fire-safety procedure
    (r"(add|create|make|new|build).*(spacecraft|vehicle|module|ship)|(spacecraft|vehicle).*(add|create|new)", "studio",
     ["Open Design Studio (sidebar, or '+ New / edit' in the header).", "Choose a Quick Start template, or 'Start from scratch'.",
      "Name it, set the atmosphere (O₂ %, pressure, gravity, ventilation) and press Save.", "Add compartments, objects and components; pick a material for each component."]),
    (r"(add|create|define|custom|new).*material", "studio",
     ["Open Design Studio → 'Add a custom material'.", "Enter its name, composition, form and class, then save.",
      "Select it for any component. It starts with no NASA evidence; nothing is inferred for it."]),
    (r"(add|create).*(compartment|object|component)", "studio",
     ["Open Design Studio and select the spacecraft.", "Use 'Add compartment', then 'Add object' inside it, then 'Add component'.", "Pick a material and form for each component, then Save."]),
    (r"(change|edit|set|modify).*(oxygen|o2|pressure|gravity|atmosphere|ventilation|condition)", "workspace",
     ["Open Mission Workspace.", "Change O₂ %, pressure, gravity, flow or diluent in the scenario panel; every module uses the new values.",
      "To change the vehicle's own atmosphere, edit it in Design Studio and Save."]),
    (r"(predict|estimate|burning rate|model)", "firelab",
     ["Open Virtual Fire Lab → 'Droplet models'.", "Choose methanol or n-heptane and set O₂, pressure and droplet diameter.",
      "The eligibility checks return Model-supported, Exploratory or Unavailable with reasons."]),
    (r"(report|pdf|export)", "reports", ["Open Mission reports.", "Press 'Generate PDF'. It uses the current spacecraft, scenario, prediction, interaction, comparison and incident."]),
    (r"compare", "compare", ["Open Compare scenarios.", "Pick 2–3 configurations, or one material under two atmospheres (O₂ partial pressure is shown)."]),
    (r"(gap|missing evidence)", "gaps", ["Open Research gaps.", "Choose a dimension (gravity, oxygen, pressure, airflow, form, material, compartment)."]),
    (r"(incident|replay|emergency)", "incidents", ["Open Incident intelligence.", "Choose a mission phase, compartment and type, then press Replay. Replays are simulated and give no instructions."]),
    (r"(graph|trace|neo4j)", "graph", ["Open Knowledge graphs.", "Select a spacecraft element to see its multi-hop trace to NASA findings, investigations and sources."]),
    (r"(audit|discrepanc|flex test)", "audit", ["Open Evidence audit.", "Filter by status to see each FLEX or Saffire value next to the NASA report value."]),
    (r"(demo|tour|start)", "overview", ["Press '▶ Guided demo' in the header for an 18-step tour that drives the real app."]),
]
PO2_Q = re.compile(r"(o2|oxygen) partial pressure|partial pressure of (o2|oxygen)|\bpo2\b|\bpo₂\b", re.I)
INV_Q = re.compile(r"\b(list|show|what('s| is| are)?) (all )?(the )?(objects|components|materials|items|inventory)\b.*\b(in|inside|aboard|on)\b|\binventory\b", re.I)
STAT_Q = re.compile(r"\bhow many (flex |saffire |bass )?(tests|findings|datasets|investigations|materials|sources|spacecraft|compartments|discrepancies)\b", re.I)
TERM_Q = re.compile(r"^\s*(what (is|are|does) (a |an |the )?[\w\- ]{2,40}( mean)?\??|define [\w\- ]+\??|meaning of [\w\- ]+\??)\s*$", re.I)
SUMM_Q = re.compile(r"\b(summari[sz]e|summary of|in simple terms|briefly|tl;?dr|eli5)\b", re.I)
CONFLICT_Q = re.compile(r"\b(conflict\w*|discrepan\w*|disagree\w*|inconsisten\w*|contradict\w*)\b", re.I)
SYNTH_Q = re.compile(r"\b(synthes\w*|across (all |the )?(investigations|experiments|studies)|compare (the )?(findings|results) (of|from|across)|overall|taken together|reconcile)\b", re.I)
COND = {"oxygen": r"\b(o2|oxygen)\b", "pressure": r"\b(pressure|kpa|atm)\b", "gravity": r"\b(gravity|microgravity|lunar|martian|partial[- ]g)\b",
        "flow": r"\b(flow|ventilation|airflow|cm/s)\b", "diluent": r"\b(nitrogen|helium|diluent)\b", "form": r"\b(thickness|thin|thick|droplet|fabric|foam|sheet)\b"}


def _num_near(q, pat):
    m = re.search(rf"(\d+(?:\.\d+)?)\s*{pat}", q, re.I)
    return float(m.group(1)) if m else None


def deterministic(question, scenario, spacecraft_id):
    """Tier 0 answers. Returns a response dict or None."""
    from . import data, store, analysis, models, retrieval, audit
    q = question.strip()
    if PO2_Q.search(q):
        o2 = _num_near(q, r"\s*%") or (scenario or {}).get("o2_pct")
        p = _num_near(q, r"\s*kpa") or ((_num_near(q, r"\s*atm") or 0) * 101.325 or None) or (scenario or {}).get("pressure_kpa")
        if o2 and p:
            v = round(o2 / 100 * p, 2)
            return {"mode": "deterministic", "answer": f"O₂ partial pressure = {o2}% × {p} kPa = {v} kPa.",
                    "claims": [], "limitations": "Arithmetic only (mole fraction × total pressure). Equal O₂ partial pressures do not imply equal flammability: total pressure, diluent and flow also matter.",
                    "tool": "o2_partial_pressure", "result": {"o2_pct": o2, "pressure_kpa": p, "po2_kpa": v}}
    m_fuel = re.search(r"\b(methanol|n-?heptane|heptane)\b", q, re.I)
    if re.search(r"\b(predict|estimate|burning[- ]rate constant|what (is|would be) the burning rate)\b", q, re.I) and m_fuel:
        o2, d0 = _num_near(q, r"\s*%"), _num_near(q, r"\s*mm")
        if o2 is not None and d0 is not None:
            p = _num_near(q, r"\s*kpa") or ((_num_near(q, r"\s*atm") or 0) * 101.325 or None) or 101.3
            fuel = "methanol" if m_fuel.group(1).lower() == "methanol" else "n-heptane"
            req = {"material_form": "liquid droplet", "fuel": fuel, "o2_pct": o2, "pressure_kpa": p, "d0_mm": d0, "diluent": "nitrogen", "gravity": "microgravity"}
            a = models.assess(req)
            if a.get("estimate") is not None and a["outcome"] != "Unavailable":
                lo, hi = a.get("interval_90") or (None, None)
                txt = f"{a['outcome']}: K ≈ {a['estimate']:.3f} {a.get('unit', 'mm²/s')}" + (f" (90% band {lo:.3f}–{hi:.3f})" if lo is not None else "") + "."
            else:
                txt = f"{a['outcome']}. Reasons: " + "; ".join(a.get("reasons", []))
            return {"mode": "deterministic", "answer": txt, "claims": [], "tool": "flex_model_prediction", "result": a, "request": req,
                    "limitations": "Assumed nitrogen diluent and microgravity" + ("" if _num_near(q, r"\s*kpa") or _num_near(q, r"\s*atm") else " and 101.3 kPa")
                    + ". Estimates come only from eligibility-checked FLEX regression models."}
    if STAT_Q.search(q):
        ev = data.evidence()
        facts = {"findings": len(ev), "sources": len(data.sources()), "materials": len(data.materials()),
                 "spacecraft": len(store.list_spacecraft()), "investigations with findings": len({e["investigation"] for e in ev})}
        word = STAT_Q.search(q).group(2).lower()
        if word == "tests":
            facts["FLEX droplet tests (PSI-69)"] = len(data.flex_tests())
        if word == "discrepancies":
            facts.update(audit.run()["counts"])
        return {"mode": "deterministic", "answer": "Library statistics: " + "; ".join(f"{k} {v}" for k, v in facts.items()) + ".",
                "claims": [], "tool": "dataset_statistics", "result": facts}
    if INV_Q.search(q) and spacecraft_id:
        sc = store.get_spacecraft(spacecraft_id)
        if sc:
            ql = q.lower()
            comps = [c for c in sc["compartments"] if c["name"].lower() in ql] or sc["compartments"]
            rows = [r for r in analysis.screen(spacecraft_id)["rows"] if r["compartment_id"] in {c["id"] for c in comps}]
            lines = [f"{r['compartment']} › {r['object']} › {r['component']}: {r['material']} ({r['form']}) — {r['status']}" for r in rows]
            return {"mode": "deterministic", "answer": f"{sc['name']}: {len(rows)} components.", "items": lines, "claims": [],
                    "tool": "spacecraft_inventory", "limitations": "Evidence status describes research coverage, not a safety rating."}
    if GREET_Q.match(q):
        thanks = re.search(r"thank", q, re.I); bye = re.search(r"bye", q, re.I)
        txt = ("You're welcome." if thanks else "Goodbye." if bye else "Hi! I'm the SpaceXtinsafe Scientific Copilot.") + \
            ("" if thanks or bye else " Ask me what NASA microgravity combustion experiments found about a material or condition, about your spacecraft, or how to use the app.")
        return {"mode": "deterministic", "answer": txt, "claims": [], "tool": "greeting",
                "suggestions": ["What did FLEX investigate?", "What NASA evidence applies to the Crew quarters?", "How do I add a spacecraft?"]}
    if HOWTO_Q.search(q):
        for pat, page, steps in HOWTO:
            if re.search(pat, q, re.I):
                return {"mode": "deterministic", "answer": "Here's how in SpaceXtinsafe:", "items": steps, "navigate": page, "claims": [], "tool": "app_guidance"}
    if NAV_Q.search(q):
        for page, pat in NAV.items():
            if re.search(pat, q, re.I):
                return {"mode": "deterministic", "answer": f"Open “{page}” from the sidebar.", "navigate": page, "claims": [], "tool": "navigation"}
    return None


def complexity(question, ev, named_materials):
    """Features and score used to choose tier 2 vs 3. Returned so the reason can be shown and logged."""
    from . import data
    invs = {e["investigation"] for e in ev[:6]}
    conds = [k for k, p in COND.items() if re.search(p, question, re.I)]
    conflict = bool(CONFLICT_Q.search(question))
    from . import audit
    flagged = {i["investigation"] for i in audit.run()["items"] if i["status"] in ("Confirmed discrepancy", "Potential discrepancy")}
    conflict_ev = sorted({e["investigation"] for e in ev[:6] if e["investigation"] in flagged})
    f = {"investigations_in_top_evidence": len(invs), "conditions_mentioned": conds, "materials_named": len(set(named_materials)),
         "conflict_question": conflict, "synthesis_question": bool(SYNTH_Q.search(question)), "investigations_with_source_discrepancies": conflict_ev,
         "evidence_sources": len({e.get("source_id") for e in ev[:6]})}
    score = (2 if conflict else 0) + (1 if conflict_ev else 0) + (2 if f["synthesis_question"] else 0) + (1 if len(invs) >= 4 else 0) \
        + (1 if len(conds) >= 3 else 0) + (1 if f["materials_named"] >= 2 else 0)
    return score, f


def choose(question, mode, kind, score, feats):
    """kind: 'app' | 'term' | 'science'. Returns (tier, reason)."""
    if kind in ("app", "term", "summary"):
        t, why = 1, {"app": "general application enquiry", "term": "terminology explanation", "summary": "simple summary"}[kind]
        if mode == "deep" and kind != "app":
            t, why = 2, why + " (Deep Research: scientific model)"
        return t, why
    if mode == "fast":
        return 1, "Fast mode: lightweight model for an evidence-grounded answer (same claim checks)"
    if mode == "deep":
        return 3, "Deep Research mode: advanced model"
    if score >= 3:
        bits = [k for k in ("conflict_question", "synthesis_question") if feats[k]] + (["source discrepancies in " + ", ".join(feats["investigations_with_source_discrepancies"])] if feats["investigations_with_source_discrepancies"] else []) \
            + ([f"{feats['investigations_in_top_evidence']} investigations"] if feats["investigations_in_top_evidence"] >= 4 else []) \
            + ([f"{len(feats['conditions_mentioned'])} interacting conditions"] if len(feats["conditions_mentioned"]) >= 3 else []) \
            + ([f"{feats['materials_named']} materials"] if feats["materials_named"] >= 2 else [])
        return 3, f"complexity score {score} ≥ 3: " + ", ".join(b.replace("_", " ") for b in bits)
    return 2, f"evidence-grounded scientific question (complexity score {score} < 3)"


def kind_of(question):
    if APP_Q.search(question):
        return "app"
    if SUMM_Q.search(question):
        return "summary"
    if TERM_Q.match(question) and len(question.split()) <= 8:
        return "term"
    return "science"