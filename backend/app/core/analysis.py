"""Applicability assessment, material screening, Virtual Fire Lab, research gaps, scenario comparison and Fire Safety Insights.

Applicability is reported per factor (match / partial / mismatch / not reported) and summarised into a tier. Not-reported
factors are never scored as matches, and no tier is a safety verdict.
"""
from __future__ import annotations
from . import data, graph, models, store

TIERS = ["Directly applicable", "Partially applicable", "Contextual only", "Not applicable"]
FACTOR_W = {"material": 3, "form": 1, "gravity": 2, "o2": 1, "pressure": 1, "flow": 1}


def _range_factor(val, rng, tol):
    if val is None:
        return "not specified"
    if not rng:
        return "not reported"
    lo, hi = rng
    if lo - 1e-9 <= val <= hi + 1e-9:
        return "match"
    if lo - tol <= val <= hi + tol:
        return "partial"
    return "mismatch"


def applicability(e: dict, sc: dict) -> dict:
    """sc: scenario dict with material_id, form, gravity, o2_pct, pressure_kpa, flow_cm_s"""
    al = data.material_aliases()
    ev_mats = {al.get(m.lower()) for m in e["materials"]} - {None}
    mats = data.materials()
    f = {}
    if sc.get("material_id") is None:
        f["material"] = "not specified"
    elif sc["material_id"] in ev_mats:
        f["material"] = "match"
    elif ev_mats and mats[sc["material_id"]]["class"] in {mats[m]["class"] for m in ev_mats}:
        f["material"] = "partial"
    elif not ev_mats:
        f["material"] = "not reported"
    else:
        f["material"] = "mismatch"
    if not sc.get("form") or not e.get("form"):
        f["form"] = "not reported" if sc.get("form") else "not specified"
    else:
        a, b = sc["form"].lower(), e["form"].lower()
        f["form"] = "match" if a == b else ("partial" if (set(a.split()) & set(b.split())) else "mismatch")
    if not e.get("gravity"):
        f["gravity"] = "not reported"
    else:
        f["gravity"] = "match" if sc.get("gravity") == e["gravity"] else "mismatch"
    f["o2"] = _range_factor(sc.get("o2_pct"), e.get("o2_pct"), 3)
    f["pressure"] = _range_factor(sc.get("pressure_kpa"), e.get("pressure_kpa"), 10)
    f["flow"] = _range_factor(sc.get("flow_cm_s"), e.get("flow_cm_s"), 5)
    val = {"match": 1.0, "partial": 0.5, "mismatch": 0.0}
    scored = {k: v for k, v in f.items() if v in val}
    w = sum(FACTOR_W[k] for k in scored)
    score = sum(FACTOR_W[k] * val[v] for k, v in scored.items()) / w if w else 0.0
    coverage = len(scored) / len(f)
    hist = e["category"] == "Historical incident"
    if f["material"] == "mismatch" or f["gravity"] == "mismatch" and f["material"] != "match":
        tier = "Not applicable" if f["material"] == "mismatch" else "Contextual only"
    elif hist:
        tier = "Contextual only"
    elif f["material"] == "match" and f["gravity"] in ("match", "not reported") and score >= 0.75:
        tier = "Directly applicable"
    elif f["material"] in ("match", "partial") or score >= 0.5:
        tier = "Partially applicable"
    else:
        tier = "Contextual only"
    if e["category"] == "Conflicting evidence" and tier == "Directly applicable":
        tier = "Partially applicable"  # an unresolved source conflict caps applicability
    return {"tier": tier, "score": round(score, 3), "factor_coverage": round(coverage, 2), "factors": f,
            "explanation": "; ".join(f"{k}: {v}" for k, v in f.items())}


def ranked_evidence(sc: dict, ids: list[str] | None = None):
    out = []
    for e in data.evidence():
        if ids and e["id"] not in ids:
            continue
        a = applicability(e, sc)
        out.append({**e, "applicability": a})
    order = {t: i for i, t in enumerate(TIERS)}
    return sorted(out, key=lambda x: (order[x["applicability"]["tier"]], -x["applicability"]["score"]))


def screen(spacecraft_id: str, compartment_id: str | None = None):
    """Material screening across a configured spacecraft. Shows evidence status, never a safety verdict."""
    sc = store.get_spacecraft(spacecraft_id)
    if not sc:
        raise KeyError(spacecraft_id)
    atm = sc["atmosphere"]; mats = data.materials(); rows = []
    for c in sc["compartments"]:
        if compartment_id and c["id"] != compartment_id:
            continue
        for o in c["objects"]:
            for k in o["components"]:
                scen = {"material_id": k["material_id"], "form": k.get("form"), "gravity": atm["gravity"], "o2_pct": atm["o2_pct"],
                        "pressure_kpa": atm["pressure_kpa"], "flow_cm_s": atm.get("ventilation_cm_s")}
                ev = [x for x in ranked_evidence(scen) if x["applicability"]["tier"] != "Not applicable" and k["material_id"] in {data.material_aliases().get(m.lower()) for m in x["materials"]}]
                tiers = [x["applicability"]["tier"] for x in ev]
                ms = data.material_status(k["material_id"])
                status = ("Applicable evidence identified" if "Directly applicable" in tiers else
                          "Partially applicable evidence" if "Partially applicable" in tiers else
                          "Contextual evidence only" if tiers else
                          "Related (indirect) evidence only" if ms["related_findings"] else "No NASA evidence in library (research gap)")
                pred = None
                if k["material_id"] in ("MAT-METHANOL", "MAT-HEPTANE"):
                    pred = models.assess({"material_form": k.get("form"), "fuel": "methanol" if k["material_id"] == "MAT-METHANOL" else "n-heptane",
                                          "o2_pct": atm["o2_pct"], "pressure_kpa": atm["pressure_kpa"], "d0_mm": None, "diluent": atm.get("diluent"), "gravity": atm["gravity"]})["outcome"]
                rows.append({"compartment": c["name"], "compartment_id": c["id"], "object": o["name"], "object_id": o["id"], "component": k["name"],
                             "component_id": k["id"], "material_id": k["material_id"], "material": mats[k["material_id"]]["name"], "form": k.get("form"),
                             "status": status, "evidence_ids": [x["id"] for x in ev], "investigations": sorted({x["investigation"] for x in ev}),
                             "top_tier": tiers[0] if tiers else None, "prediction": pred or "No model for this material",
                             "material_status": ms["status"], "related_findings": ms["related_findings"], "phenomenon": mats[k["material_id"]].get("phenomenon"),
                             "user_defined": mats[k["material_id"]].get("user_defined", False)})
    return {"spacecraft": sc["name"], "atmosphere": atm, "rows": rows,
            "boundary": "Evidence status describes what NASA research covers. It is not a flammability rating, qualification or safety verdict."}


def material_profile(mid: str, scen: dict | None = None):
    m = data.materials()[mid]
    ev = data.evidence_for_material(mid)
    scen = {**(scen or {}), "material_id": mid}
    ranked = ranked_evidence(scen, [e["id"] for e in ev]) if ev else []
    measured = [e for e in ev if e["category"] in ("Experimentally observed", "Conflicting evidence")]
    gaps = []
    if not ev:
        gaps.append("No NASA combustion evidence for this material in the library.")
    if not any(e.get("gravity") == "partial gravity" for e in ev):
        gaps.append("No partial-gravity (Moon/Mars) evidence.")
    if not any((e.get("o2_pct") or [0, 0])[1] > 23 for e in ev):
        gaps.append("No evidence at elevated oxygen (>23%).")
    if not any((e.get("pressure_kpa") or [999, 999])[0] < 90 for e in ev):
        gaps.append("No evidence at reduced pressure (<90 kPa).")
    inters = [e for e in ev if e["category"] == "Documented material interaction"]
    users = []
    for sc in store.list_spacecraft():
        for c in sc["compartments"]:
            for o in c["objects"]:
                for k in o["components"]:
                    if k["material_id"] == mid:
                        users.append({"spacecraft": sc["name"], "compartment": c["name"], "object": o["name"], "component": k["name"]})
    return {"material": m, "status": data.material_status(mid), "evidence": ranked, "measured_count": len(measured), "interactions": inters, "gaps": gaps, "used_in": users,
            "models": [models.public(x) for x in models.registry() if (mid == "MAT-METHANOL" and x["fuel"] == "methanol") or (mid == "MAT-HEPTANE" and x["fuel"] == "n-heptane")]}


def interaction(mids: list[str]):
    al = data.material_aliases(); out = []
    for e in data.evidence():
        em = {al.get(x.lower()) for x in e["materials"]}
        if len(set(mids) & em) >= 2:
            out.append(e)
    documented = [e for e in out if e["category"] == "Documented material interaction"]
    co = [e for e in out if e not in documented]
    names = [data.materials()[m]["name"] for m in mids]
    return {"materials": names, "documented_interactions": documented, "co_reported": co,
            "status": "Documented interaction" if documented else ("Co-reported in the same finding, no interaction documented" if co else "No documented interaction (research gap)"),
            "note": "Absence of a documented interaction is not evidence that materials do not interact."}


CONDS = [("Microgravity", lambda e: e.get("gravity") == "microgravity"), ("Partial gravity", lambda e: e.get("gravity") == "partial gravity"),
         ("1-g", lambda e: e.get("gravity") == "1-g"), ("Elevated O2 >23%", lambda e: (e.get("o2_pct") or [0, 0])[1] > 23),
         ("Reduced pressure <90 kPa", lambda e: (e.get("pressure_kpa") or [999, 999])[0] < 90),
         ("Forced flow reported", lambda e: (e.get("flow_cm_s") or [0, 0])[1] > 0), ("Quiescent", lambda e: e.get("flow_cm_s") == [0, 0])]


def gaps(spacecraft_id: str | None = None):
    mats = data.materials()
    mids = list(mats)
    if spacecraft_id:
        sc = store.get_spacecraft(spacecraft_id)
        mids = sorted({k["material_id"] for c in sc["compartments"] for o in c["objects"] for k in o["components"]})
    cells = []
    for mid in mids:
        ev = [e for e in data.evidence_for_material(mid) if e["category"] != "Historical incident"]
        for cname, fn in CONDS:
            n = sum(1 for e in ev if fn(e))
            cells.append({"material_id": mid, "material": mats[mid]["name"], "condition": cname, "count": n, "evidence_ids": [e["id"] for e in ev if fn(e)]})
    flex = []
    for fuel in ("methanol", "n-heptane"):
        for o2 in (12, 14, 16, 18, 21, 25, 30, 34, 40):
            for band, (lo, hi, kpa) in models.BANDS.items():
                n = sum(1 for t in data.flex_tests() if t["fuel"] == fuel and t["o2"] is not None and abs(t["o2"] * 100 - o2) < 1.0 and lo <= (t["pressure_mmHg"] or 0) <= hi
                        and not (t["co2"] or 0) and not (t["he"] or 0) and t["k_mm2_s"] is not None)
                flex.append({"fuel": fuel, "o2_pct": o2, "pressure": f"{kpa} kPa", "tests": n})
    return {"materials": [mats[m]["name"] for m in mids], "conditions": [c for c, _ in CONDS], "cells": cells, "flex_coverage": flex,
            "note": "Counts are curated findings in this library (not all NASA literature). Zero means no finding here, which is a candidate research gap."}


def compare(spacecraft_ids: list[str]):
    out = []
    for sid in spacecraft_ids:
        sc = store.get_spacecraft(sid); s = screen(sid)
        cnt = {}
        for r in s["rows"]:
            cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        out.append({"id": sid, "name": sc["name"], "atmosphere": sc["atmosphere"], "components": len(s["rows"]),
                    "materials": sorted({r["material"] for r in s["rows"]}), "status_counts": cnt,
                    "gap_materials": sorted({r["material"] for r in s["rows"] if r["status"].startswith("No NASA")})})
    return {"configurations": out, "note": "Comparison of evidence coverage, not of safety."}


def insights(scen: dict):
    ranked = ranked_evidence(scen)
    direct = [e for e in ranked if e["applicability"]["tier"] == "Directly applicable"]
    partial = [e for e in ranked if e["applicability"]["tier"] == "Partially applicable"]
    hist = [e for e in ranked if e["category"] == "Historical incident" and e["applicability"]["tier"] != "Not applicable"]
    conflicts = [e for e in ranked if e["category"] == "Conflicting evidence" and e["applicability"]["tier"] != "Not applicable"]
    mid = scen.get("material_id")
    pred = None
    if mid in ("MAT-METHANOL", "MAT-HEPTANE"):
        pred = models.assess({"material_form": scen.get("form"), "fuel": "methanol" if mid == "MAT-METHANOL" else "n-heptane", "o2_pct": scen.get("o2_pct"),
                              "pressure_kpa": scen.get("pressure_kpa"), "d0_mm": scen.get("d0_mm"), "diluent": scen.get("diluent", "nitrogen"), "gravity": scen.get("gravity")})
    prof = material_profile(mid, scen) if mid else None
    return {
        "observed": [{"text": e["statement"], "cite": e["id"], "tier": e["applicability"]["tier"]} for e in (direct or partial)[:5]],
        "suggests": [{"text": e["statement"], "cite": e["id"]} for e in partial[:4] if e not in direct],
        "model": pred or {"outcome": "Unavailable", "reasons": ["No validated model exists for this material; only FLEX droplet models are registered."]},
        "historical": [{"text": e["statement"], "cite": e["id"]} for e in hist[:3]],
        "uncertain": ([{"text": f"Source conflict: {e['statement']}", "cite": e["id"]} for e in conflicts] +
                      [{"text": g, "cite": None} for g in (prof["gaps"] if prof else [])]),
        "next": ([{"text": "Test this material in the specified atmosphere (no NASA finding in this library matches it directly)."}] if not direct else []) +
                [{"text": "Resolve open audit items affecting the cited findings before relying on their values."}] * bool(conflicts) +
                [{"text": "Ask a qualified fire-safety engineer to review any design decision."}],
        "boundary": "Research synthesis only. No fire-risk score, safe/unsafe verdict or emergency instruction is produced.",
    }


def compare_conditions(material_id: str | None, form: str | None, scenarios: list[dict], d0_mm: float | None = None):
    """Same material under several condition sets. O2 partial pressure is reported, but equal partial pressures are not treated as equivalent."""
    out = []
    for i, c in enumerate(scenarios):
        sc = {"material_id": material_id, "form": form, "o2_pct": c.get("o2_pct"), "pressure_kpa": c.get("pressure_kpa"), "gravity": c.get("gravity"), "flow_cm_s": c.get("flow_cm_s")}
        rk = [e for e in ranked_evidence(sc) if e["applicability"]["tier"] != "Not applicable" and (not material_id or e["applicability"]["factors"]["material"] in ("match", "partial"))]
        tiers = {}
        for e in rk:
            tiers[e["applicability"]["tier"]] = tiers.get(e["applicability"]["tier"], 0) + 1
        pred = None
        if material_id in ("MAT-METHANOL", "MAT-HEPTANE"):
            pred = models.assess({"material_form": form, "fuel": "methanol" if material_id == "MAT-METHANOL" else "n-heptane", "o2_pct": c.get("o2_pct"),
                                  "pressure_kpa": c.get("pressure_kpa"), "d0_mm": d0_mm, "diluent": c.get("diluent", "nitrogen"), "gravity": c.get("gravity")})
            pred = {k: pred.get(k) for k in ("outcome", "estimate", "reasons")}
        ppo2 = round(c["o2_pct"] / 100 * c["pressure_kpa"], 1) if c.get("o2_pct") and c.get("pressure_kpa") else None
        out.append({"label": c.get("label") or f"Scenario {i+1}", "conditions": c, "o2_partial_pressure_kpa": ppo2, "tier_counts": tiers,
                    "top": [{"id": e["id"], "statement": e["statement"], "tier": e["applicability"]["tier"]} for e in rk[:4]], "prediction": pred})
    pp = [o["o2_partial_pressure_kpa"] for o in out if o["o2_partial_pressure_kpa"]]
    note = "O2 partial pressure is shown for reference. Equal partial pressures do not establish equal combustion behaviour (total pressure, diluent and gravity also matter)."
    if len(pp) > 1 and max(pp) - min(pp) < 1.5:
        note += " These scenarios have similar O2 partial pressures but differ in other conditions."
    return {"material": data.materials()[material_id]["name"] if material_id else None, "scenarios": out, "note": note}


def gaps_dimension(dimension: str, spacecraft_id: str | None = None):
    mats = data.materials()
    mids = sorted({k["material_id"] for c in store.get_spacecraft(spacecraft_id)["compartments"] for o in c["objects"] for k in o["components"]}) if spacecraft_id else list(mats)
    bands = {
        "gravity": [("microgravity", lambda e: e.get("gravity") == "microgravity"), ("partial gravity", lambda e: e.get("gravity") == "partial gravity"), ("1-g", lambda e: e.get("gravity") == "1-g")],
        "oxygen": [("< 18%", lambda e: (e.get("o2_pct") or [99])[0] < 18), ("18-23%", lambda e: e.get("o2_pct") and e["o2_pct"][0] <= 23 and e["o2_pct"][1] >= 18),
                   ("23-30%", lambda e: e.get("o2_pct") and e["o2_pct"][1] > 23 and e["o2_pct"][0] <= 30), ("> 30%", lambda e: (e.get("o2_pct") or [0, 0])[1] > 30),
                   ("not reported", lambda e: not e.get("o2_pct"))],
        "pressure": [("< 70 kPa", lambda e: (e.get("pressure_kpa") or [999])[0] < 70), ("70-90 kPa", lambda e: e.get("pressure_kpa") and e["pressure_kpa"][0] <= 90 and e["pressure_kpa"][1] >= 70),
                     ("> 90 kPa", lambda e: (e.get("pressure_kpa") or [0, 0])[1] > 90), ("not reported", lambda e: not e.get("pressure_kpa"))],
        "airflow": [("quiescent", lambda e: e.get("flow_cm_s") == [0, 0]), ("1-10 cm/s", lambda e: e.get("flow_cm_s") and e["flow_cm_s"][1] > 0 and e["flow_cm_s"][0] <= 10),
                    ("10-30 cm/s", lambda e: e.get("flow_cm_s") and e["flow_cm_s"][1] > 10 and e["flow_cm_s"][0] <= 30), ("> 30 cm/s", lambda e: (e.get("flow_cm_s") or [0, 0])[1] > 30),
                    ("not reported", lambda e: not e.get("flow_cm_s"))],
    }
    if dimension == "compartment":
        sc = store.get_spacecraft(spacecraft_id or "SC-ORBITAL"); rows = []
        for c in sc["compartments"]:
            st = {}
            for o in c["objects"]:
                for k in o["components"]:
                    s = data.material_status(k["material_id"])["status"]; st[s] = st.get(s, 0) + 1
            rows.append({"compartment": c["name"], "id": c["id"], "status_counts": st, "components": sum(st.values())})
        return {"dimension": dimension, "rows": rows, "statuses": data.STATUS_ORDER}
    if dimension == "material":
        cells = []
        for a in mids:
            for b in mids:
                if a < b:
                    it = interaction([a, b])
                    if it["documented_interactions"] or it["co_reported"]:
                        cells.append({"a": mats[a]["name"], "b": mats[b]["name"], "status": it["status"], "ids": [e["id"] for e in it["documented_interactions"] + it["co_reported"]]})
        return {"dimension": dimension, "pairs_checked": len(mids) * (len(mids) - 1) // 2, "cells": cells,
                "note": "Only pairs that appear together in a finding are listed; every other pair has no documented interaction in this library."}
    if dimension == "form":
        cells = []
        for m in mids:
            for e in data.evidence_for_material(m):
                if e["category"] in data.EV_CATS_DIRECT:
                    cells.append({"material": mats[m]["name"], "form": e.get("form") or "not reported", "outcome": ", ".join(e.get("concerns", [])), "id": e["id"]})
        return {"dimension": dimension, "cells": cells}
    cols = bands[dimension]; cells = []
    for m in mids:
        ev = [e for e in data.evidence_for_material(m) if e["category"] in data.EV_CATS_DIRECT]
        for name, fn in cols:
            hit = [e for e in ev if fn(e)]
            cell = {"material_id": m, "material": mats[m]["name"], "band": name, "count": len(hit), "ids": [e["id"] for e in hit],
                    "kind": "Direct experimental evidence" if hit else "No finding in this library"}
            if any(e["category"] == "Conflicting evidence" for e in hit):
                cell["kind"] = "Includes conflicting evidence"
            if m in ("MAT-METHANOL", "MAT-HEPTANE") and dimension in ("oxygen", "pressure"):
                fuel = "methanol" if m == "MAT-METHANOL" else "n-heptane"
                st = {x["status"] for x in models.registry() if x["fuel"] == fuel and (
                    dimension == "pressure" and ((name == "> 90 kPa" and x["pressure_band"] == "1atm") or (name == "70-90 kPa" and x["pressure_band"] == "0.7atm")) or
                    dimension == "oxygen" and name in ("< 18%", "18-23%", "23-30%", "> 30%") and x["o2_pct_range"][0] <= {"< 18%": 17, "18-23%": 20, "23-30%": 26, "> 30%": 31}[name] <= x["o2_pct_range"][1])}
                if st:
                    cell["model"] = "Model-supported estimate possible" if "Model-supported" in st else "Exploratory estimate only"
            cells.append(cell)
    return {"dimension": dimension, "bands": [c for c, _ in cols], "materials": [mats[m]["name"] for m in mids], "cells": cells,
            "note": "A zero means no finding in THIS library, not a confirmed gap in all scientific literature. Model cells show where a FLEX droplet estimate can complement missing measurements.",
            "needed": "To close a gap: tests of the material in the stated form under the missing condition, with sample geometry, O2, pressure, flow and gravity reported."}
