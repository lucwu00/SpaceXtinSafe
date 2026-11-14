"""Vehicle-aware SIMULATED incident replay for training and research discussion.
All sensor values are synthetic and labelled SIMULATED. The tool identifies the configured compartment and the objects and
materials in it, retrieves related NASA evidence and historical analogues, and points to the vehicle's authorised
procedures. It never generates emergency instructions.
"""
from __future__ import annotations
from . import data, store, retrieval, analysis

PHASES = {"pre-launch": ("1-g", "On the pad: Earth gravity; ground support available."),
          "ascent": ("variable (launch loads)", "High and changing acceleration; NASA microgravity findings apply poorly."),
          "orbital operations": ("microgravity", "Matches most NASA ISS/Cygnus combustion experiments."),
          "deep-space transit": ("microgravity", "Microgravity, but longer isolation from ground support."),
          "lunar surface": ("partial gravity", "Partial gravity: only LUCI/FM2 context applies; most findings are microgravity."),
          "martian surface": ("partial gravity", "Partial gravity (Mars): no direct findings in this library."),
          "descent and landing": ("variable (landing loads)", "Changing loads; NASA microgravity findings apply poorly.")}

PROC = "Refer to the vehicle's authorised emergency procedures and flight controllers. SpaceXtinSafe does not generate emergency instructions."
NON_CABIN = {
    "propulsion": "Propulsion combustion event (outside the pressurised cabin). Cabin-material combustion research does not describe this; SpaceXtinSafe has no propulsion evidence.",
    "external_heating": "External aerodynamic or entry heating (thermal protection). This is not internal cabin combustion; SpaceXtinSafe has no TPS evidence.",
}
TYPES = {
    "smoke": {"title": "Smoke detected (simulated)", "classes": {"fabric", "polymer", "polymer foam", "elastomer", "energy storage", "assembly", "fluoropolymer"},
              "query": "smoke detection particles carbon monoxide fabric burning", "analogues": ["EV-MIR-01", "EV-SAF6-03"],
              "steps": [("T+0 s", "Particulate sensor reading rises above baseline", {"particulate_rel": 3.2}),
                        ("T+40 s", "Carbon monoxide reading rises", {"co_ppm": 18}),
                        ("T+90 s", "Second sensor in the same compartment confirms", {"particulate_rel": 4.1, "co_ppm": 26})]},
    "electrical": {"title": "Electrical overheating odour (simulated)", "classes": {"assembly", "fluoropolymer", "energy storage"},
                   "query": "electrical arc wiring insulation ignition source oxygen", "analogues": ["EV-AP1-02", "EV-AP13-01"],
                   "steps": [("T+0 s", "Crew reports burning odour near equipment", {}), ("T+30 s", "Circuit current anomaly logged", {"current_dev_pct": 35}),
                             ("T+60 s", "Localised temperature rise on panel", {"panel_temp_c": 58})]},
    "oxygen": {"title": "Oxygen system anomaly (simulated)", "classes": {"oxygen system"}, "query": "solid-fuel oxygen generator canister fire contamination",
               "analogues": ["EV-MIR-01", "EV-MIR-02"],
               "steps": [("T+0 s", "Oxygen generator activation", {}), ("T+15 s", "Unexpected canister temperature rise", {"canister_temp_c": 140}),
                         ("T+45 s", "Smoke reported in compartment", {"particulate_rel": 5.0})]},
}


def scenarios(spacecraft_id):
    sc = store.get_spacecraft(spacecraft_id)
    return [{"type": t, "title": v["title"], "compartments": [c["id"] for c in sc["compartments"]]} for t, v in TYPES.items()]


def replay(spacecraft_id: str, compartment_id: str, itype: str, phase: str = "orbital operations"):
    sc = store.get_spacecraft(spacecraft_id)
    if phase not in PHASES:
        raise KeyError(phase)
    if itype in NON_CABIN:
        return {"spacecraft": sc["name"], "type": itype, "phase": phase, "title": itype.replace("_", " ").title() + " (simulated)", "classification": "Not internal cabin combustion",
                "message": NON_CABIN[itype], "timeline": [], "candidates": [], "evidence": [], "analogues": [], "procedures": store.list_procedures(spacecraft_id),
                "disclaimer": "Simulated. SpaceXtinSafe does not model propulsion or entry heating and gives no operational commands."}
    spec = TYPES[itype]
    comp = next(c for c in sc["compartments"] if c["id"] == compartment_id)
    mats = data.materials(); evm = {e["id"]: e for e in data.evidence()}
    cands = []
    for o in comp["objects"]:
        for k in o["components"]:
            m = mats[k["material_id"]]
            if m["class"] in spec["classes"] or m.get("user_defined"):  # user-defined materials cannot be excluded
                ev = data.evidence_for_material(k["material_id"])
                cands.append({"object": o["name"], "component": k["name"], "material": m["name"], "material_id": k["material_id"],
                              "evidence_ids": [e["id"] for e in ev], "evidence_status": "NASA evidence available" if ev else "No NASA evidence (gap)"})
    r = retrieval.search(spec["query"] + " " + " ".join(c["material"] for c in cands), "auto", k=5, spacecraft_id=spacecraft_id)
    grav, phase_note = PHASES[phase]
    steps = []
    for i, (t, obs, vals) in enumerate(spec["steps"]):
        steps.append({"t": t, "observation": obs, "simulated_values": vals, "label": "SIMULATED",
                      "source": "crew report" if "reports" in obs.lower() or "odour" in obs.lower() else "simulated sensor",
                      "confirmed": i == len(spec["steps"]) - 1 and len(vals) > 1,
                      "system": (f"Location resolved to {comp['name']} ({sc['name']})." if i == 0 else
                                 f"{len(cands)} candidate components in {comp['name']} match this signature." if i == 1 else
                                 "Related NASA evidence and historical analogues retrieved."),
                      "procedure_reference": PROC})
    scen = {**sc["atmosphere"], "gravity": grav if grav in ("microgravity", "partial gravity", "1-g") else None}
    ev = r["results"]
    lim = []
    for e in ev:
        a = analysis.applicability(e, {"o2_pct": scen["o2_pct"], "pressure_kpa": scen["pressure_kpa"], "gravity": scen["gravity"], "flow_cm_s": sc["atmosphere"].get("ventilation_cm_s")})
        e["applicability"] = a
        if a["factors"]["gravity"] == "mismatch":
            lim.append(f"{e['id']}: obtained in {e.get('gravity')}, phase is {grav}")
    procs = store.list_procedures(spacecraft_id)
    summary = (f"SIMULATED {spec['title'].replace(' (simulated)', '').lower()} during {phase} in {comp['name']} of {sc['name']}. "
               f"{len(cands)} configured components could be involved (unconfirmed). {len([c for c in cands if c['evidence_ids']])} have NASA evidence in the library. "
               f"{len(lim)} retrieved findings come from a different gravity regime. "
               + (f"{len(procs)} registered procedure document(s) available for authorised human review." if procs else "No vehicle procedure documents are registered."))
    return {"spacecraft": sc["name"], "compartment": comp["name"], "type": itype, "title": spec["title"], "atmosphere": sc["atmosphere"],
            "phase": phase, "phase_gravity": grav, "phase_note": phase_note, "classification": "Internal cabin combustion scenario",
            "applicability_limitations": lim, "procedures": procs, "human_review_summary": summary,
            "timeline": steps, "candidates": cands, "evidence": ev, "analogues": [evm[a] for a in spec["analogues"]],
            "disclaimer": "Simulated training scenario. Values are synthetic. Candidate components are possibilities from the configuration, not a diagnosis."}
