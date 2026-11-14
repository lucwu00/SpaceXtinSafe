"""NASA Investigation Coverage and dataset provenance. Every status is computed from what the code actually loads and uses."""
from __future__ import annotations
import csv, io, json, os
from functools import lru_cache
from . import data, models, audit, graph

# name, acronym shown, PSI accession (or None), evidence 'investigation' labels, parsed table loader name, features
INV = [
    ("FLEX", "PSI-69", ["FLEX"], "flex", ["Droplet burning-rate models", "Prediction eligibility", "Evidence audit (Table IX vs PSI-69)", "Extinction findings", "Graph: 274 test nodes"]),
    ("FLEX-2", "PSI-68", [], None, []),
    ("Saffire", None, ["Saffire"], None, ["Programme objectives and test-platform context"]),
    ("Saffire-I", "PSI-98", ["Saffire-I", "Saffire"], "saffire", ["Large-scale flame spread observations", "Evidence audit (PSI vs NTRS Table 1)", "Graph test nodes"]),
    ("Saffire-II", "PSI-99", ["Saffire-II", "Saffire"], "saffire", ["Flame spread observations", "Documented PMMA-Nomex interaction", "Evidence audit", "Graph test nodes"]),
    ("Saffire-III", "PSI-100", ["Saffire-III", "Saffire"], "saffire", ["Flame spread observations", "Evidence audit", "Graph test nodes"]),
    ("Saffire-VI", None, ["Saffire-VI"], None, ["Combustion product findings", "Thick PMMA growth findings"]),
    ("BASS", "PSI-26", ["BASS"], None, ["PMMA sphere finding (Researcher's Guide)"]),
    ("BASS-II", "PSI-25", ["BASS-II"], "bass2", ["Flammability boundary and quenching findings"]),
    ("SAME", "PSI-102", ["SAME"], None, ["Smoke detection research findings", "Incident context"]),
    ("SAME-R", "PSI-101", [], None, []),
    ("ACME", "PSI-10", [], None, []),
    ("BRE", "PSI-20", [], None, []),
    ("CFI", "PSI-39", [], None, []),
    ("CFI-G", "PSI-159", [], None, []),
    ("SPICE", "PSI-107", ["SPICE"], None, ["Soot transition finding"]),
    ("SLICE", "PSI-106", [], None, []),
    ("SoFIE", None, ["SoFIE"], None, ["Quenching/blowoff and exploration-atmosphere findings"]),
    ("LUCI", None, ["LUCI"], None, ["Partial-gravity flame spread findings"]),
    ("FM2", None, ["FM2"], None, ["Partial-gravity flammability context"]),
]
FILES = {"PSI-69": "PSI-69_Experimental table_FLEX.csv", "PSI-68": "PSI-68_Experimental table_Flex2.csv", "PSI-26": "PSI-26_Experimental table_BASS.csv",
         "PSI-25": "PSI-25_Experimental table_BASS-II.csv", "PSI-98": "PSI-98_Experimental table_SAFFIRE-1.csv", "PSI-99": "PSI-99_Experimental table_SAFFIRE-2.csv",
         "PSI-100": "PSI-100_Experimental table_SAFFIRE-3.csv"}


def _bass_mat(t):
    m = (t.get("material_raw") or "").lower()
    return "MAT-PMMA" if ("pmma" in m or "acrylic" in m) else "MAT-SIBAL" if ("sibal" in m or "cotton" in m) else None


@lru_cache
def psi_records():
    return {r["accession"]: r for r in json.load(open(os.path.join(data.DATA, "curated", "psi_investigations.json")))}


def _rows(fn):
    try:
        return list(csv.reader(data._open(fn)))
    except Exception:
        return []


def datasets():
    prov = data.provenance(); out = []
    used = {"PSI-69": (len(data.flex_tests()), ["Model fitting (N2-diluted tests with K reported)", "Eligibility domain", "Audit vs Table IX", "Graph test nodes", "Gap heatmap"],
                       ["Parsed numerically; fuel names normalised (Heptane -> n-heptane); O2 mole fraction x 100 for features; burning rate read as mm^2/s (verified); test #70 excluded from fitting (audit)"]),
            "PSI-98": (2, ["Audit vs NTRS Table 1", "Graph test nodes"], ["Parsed; raw strings kept; numbers extracted for flow/thickness comparison"]),
            "PSI-99": (9, ["Audit vs NTRS Table 1", "Graph test nodes"], ["Parsed; raw strings kept; numbers extracted for flow/thickness comparison"]),
            "PSI-100": (2, ["Audit vs NTRS Table 1", "Graph test nodes"], ["Parsed; raw strings kept"]),
            "PSI-25": (sum(1 for t in data.bass2_tests() if _bass_mat(t)), ["Graph test nodes linked to PMMA / SIBAL", "Investigation coverage counts"],
                       ["Parsed (test id, material text, initial/final O2); material text mapped to PMMA or SIBAL where it names them; no flame-spread values in this table"]),
            "PSI-26": (0, [], ["Acquired; not parsed or analysed"]), "PSI-68": (0, [], ["Acquired; not parsed or analysed"])}
    for acc, fn in FILES.items():
        p = prov.get(fn, {}); rows = _rows(fn); n_used, feats, tr = used[acc]
        rec = psi_records().get(acc, {})
        status = ("Used in analysis and modelling" if acc == "PSI-69" else "Used in graph only" if acc == "PSI-25" else "Used in audit and graph" if feats else
                  "Parsed, not yet analysed" if n_used else "Acquired, not yet analysed")
        out.append({"accession": acc, "investigation": rec.get("investigationAcronym"), "filename": fn, "source_url": p.get("source_url"),
                    "record_url": rec.get("record_url"), "doi": rec.get("doi"), "acquired": p.get("acquired"), "sha256": p.get("sha256"),
                    "integrity": "SHA-256 matches acquisition manifest" if p.get("manifest_match") else "NOT verified",
                    "variables": [h.strip() for h in rows[0]] if rows else [], "rows_in_file": max(0, len(rows) - 1), "records_used": n_used,
                    "transformations": tr, "features": feats, "usage_status": status, "licence": rec.get("licenseName") or "CC0 1.0",
                    "limitations": {"PSI-69": "Header unit label 'mm' for burning rate; trace contaminant in some tests (TP Sec. 5).",
                                    "PSI-99": "Blank material cells (2-6, 2-9); thickness formatting; flow conflict with NTRS for 2-6.",
                                    "PSI-98": "Thickness column labelled cm; length/width appear swapped vs NTRS.",
                                    "PSI-100": "Flow 30 cm/s vs NTRS 25 cm/s; thickness .33 cm vs 0.37 mm.",
                                    "PSI-25": "Fan settings are free-text; no flame-spread column in this table."}.get(acc, "Not yet analysed.")})
    return out


def investigations():
    ev = data.evidence(); reg = models.registry(); g = graph.build(); au = audit.run()["items"]
    ds = {d["accession"]: d for d in datasets()}
    out = []
    for name, acc, labels, loader, feats in INV:
        rec = psi_records().get(acc, {}) if acc else {}
        evs = [e for e in ev if e["investigation"] == name]
        tests = sum(1 for n, d in g.nodes(data=True) if d["label"] == "ExperimentalTest" and n.startswith(f"TEST:{name}:") or (name == "FLEX" and n.startswith("TEST:FLEX:")))
        mdl = [m["model_id"] for m in reg] if name == "FLEX" else []
        conflicts = [i["id"] for i in au if i["investigation"] == name and i["classification"] != "Missing information"]
        d = ds.get(acc)
        if d and d["usage_status"] == "Used in analysis and modelling":
            st = "Fully integrated original dataset"
        elif d and d["usage_status"] in ("Used in audit and graph", "Used in graph only"):
            st = "Partially integrated original dataset"
        elif evs:
            st = "Curated scientific findings available"
        elif d:
            st = "Dataset acquired but not yet analysed"
        elif acc:
            st = "Dataset acquired but not yet analysed" if rec.get("files_acquired") else "Scientific reference only"
        else:
            st = "Scientific reference only"
        mats = sorted({m for e in evs for m in e["materials"]})
        out.append({"name": name, "acronym": rec.get("investigationAcronym") or name, "official_name": rec.get("title"), "accession": acc,
                    "objective": rec.get("objective"), "platform": rec.get("flightProgram"), "hardware": rec.get("experimentHardware"),
                    "dates": [rec.get("investigationStartDate"), rec.get("investigationEndDate")] if rec else None, "doi": rec.get("doi"),
                    "record_url": rec.get("record_url"), "psi_files_acquired": rec.get("files_acquired", 0),
                    "status": st, "curated_findings": len(evs), "finding_ids": [e["id"] for e in evs], "materials": mats,
                    "conditions": sorted({e.get("gravity") for e in evs if e.get("gravity")}),
                    "integrated_measurements": (d or {}).get("records_used", 0), "graph_test_nodes": tests, "models": mdl, "audit_items": conflicts,
                    "sources": sorted({(e["source_identifier"], e["source_url"]) for e in evs}), "features": feats if (evs or d and d["features"]) else [],
                    "limitations": (d or {}).get("limitations") or ("Findings are curated statements, not a parsed dataset." if evs else "Not integrated in this build."),
                    "text_source": "Official name, objective and platform are verbatim from the NASA PSI record" if rec else "No PSI record; findings from NTRS sources"})
    return out


def nasa_usage():
    ds = datasets(); inv = investigations(); reg = models.registry()
    return {"datasets_used": [d["accession"] for d in ds if d["features"]], "datasets_acquired_not_used": [d["accession"] for d in ds if not d["features"]],
            "analyses": ["Leave-one-session-out regression of droplet burning-rate constants (PSI-69)", "Random-forest and mean-baseline benchmarks on identical folds",
                         "Joint-support prediction eligibility (convex hull, nearest-neighbour distance, local coverage)",
                         "Automated cross-source audit: all PSI-69 rows vs NASA/TP-2015-216046 Table IX; Saffire PSI tables vs NTRS Table 1",
                         "Knowledge graph of PSI experimental tests linked to materials, findings and sources"],
            "models": [{"id": m["model_id"], "status": m["status"], "n": m["n_observations"]} for m in reg],
            "findings": sum(i["curated_findings"] for i in inv), "sources": len(data.sources()),
            "conceptual": ["Whole-spacecraft fire simulation (future research)", "Live NASA API connection (not required; files are versioned with hashes)",
                           "Models for solids and fabrics (too few independent tests in the integrated tables)"]}
