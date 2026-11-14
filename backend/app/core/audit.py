"""Scientific Evidence Audit: automated cross-source comparison of the original NASA tables.

Classification:
- Confirmed discrepancy: two primary NASA sources give different values for the same quantity of the same test.
- Potential discrepancy: values differ in a way that may be formatting, units or rounding; needs a third source.
- Missing information: a value is blank or non-numeric in one source.
Nothing is corrected automatically; affected records are excluded from models where stated.
"""
from __future__ import annotations
import json, os, re
from functools import lru_cache
from . import data

TP_COLS = [("fuel", "Fuel", None), ("pressure_mmHg", "Ambient pressure", "mmHg"), ("o2", "O2 mole fraction", None),
           ("n2", "N2 mole fraction", None), ("co2", "CO2 mole fraction", None), ("he", "He mole fraction", None),
           ("d0_mm", "Initial droplet diameter", "mm"), ("ext_d_mm", "Visible flame extinction diameter", "mm"),
           ("k_mm2_s", "Burning-rate constant", "mm^2/s"), ("burn_time_s", "Burn time", "s"), ("end", "Test end", None)]


def _num(x):
    m = re.search(r"(\d*\.?\d+)", x or "")
    return float(m.group(1)) if m else None


def _mm(x, unit=None):
    """Parse a thickness string to mm, returning (value_mm, note)."""
    x = (x or "").strip()
    if not x or not re.search(r"\d", x):
        return None, "no numeric value"
    v = _num(x)
    if re.match(r"^0\d", x):
        return None, f"'{x}' lacks a decimal point (most likely 0.{x[1:].split()[0]} mm; formatting)"
    if "cm" in x or unit == "cm":
        return round(v * 10, 3), f"'{x}' {'with column unit cm ' if unit == 'cm' and 'cm' not in x else ''}= {round(v * 10, 3):g} mm"
    return v, ""


@lru_cache
def run() -> dict:
    items = []
    D = data.DATA
    tp = json.load(open(os.path.join(D, "derived", "flex_tp_table9.json")))
    def _d(x):  # normalise dates like 3/5/2009 and 3/5/09
        mo, dd, yy = x.split("/")
        return f"{int(mo)}/{int(dd)}/{int(yy) % 100}"
    tpr = {(r["identifier"], _d(r["date"])): r for r in tp["rows"]}
    flex_mismatch, renumbered = 0, []
    matched = set()
    for t in data.flex_tests():
        r = tpr.get((t["identifier"], _d(t["date"])))
        if r:
            matched.add((r["identifier"], _d(r["date"])))
            if r["test"] != t["test"]:
                renumbered.append((t["test"], r["test"], t["identifier"]))
        if not r:
            items.append({"id": f"AUD-FLEX-{t['test']:03d}-MISSING", "status": "Missing information", "investigation": "FLEX", "test": t["record"],
                          "quantity": "whole row", "values": [{"source_id": "SRC-PSI69", "location": t["record"], "raw": "present"}, {"source_id": "SRC-FLEX-TP", "location": "Table IX", "raw": "no row with this identifier and date"}],
                          "affected": [], "modelling": "Used as in PSI-69 (single source)", "unresolved_question": "Why is this test absent from Table IX?"})
            continue
        for key, label, unit in TP_COLS:
            a, b = t.get(key), r.get(key)
            if key == "fuel":
                a, b = (a or "").replace("n-heptane", "heptane"), (b or "").lower()
            if key == "end":
                a, b = (a or "").lower(), (b or "").lower()
            if a == b or (isinstance(a, float) and isinstance(b, float) and abs(a - b) < 1e-9):
                continue
            flex_mismatch += 1
            status = "Missing information" if (a in (None, "") or b in (None, "")) else "Confirmed discrepancy"
            items.append({"id": f"AUD-FLEX-{t['test']:03d}-{key}", "status": status, "investigation": "FLEX", "test": f"FLEX test {t['test']} ({t['identifier']})",
                          "quantity": label, "unit": unit,
                          "values": [{"source_id": "SRC-PSI69", "location": f"PSI-69 experimental table, FLEX Test #{t['test']}", "raw": a},
                                     {"source_id": "SRC-FLEX-TP", "location": f"NASA/TP-2015-216046 Table IX, PDF p.{r['pdf_page']}", "raw": b}],
                          "affected": ["FLEX burning-rate models"] if key in ("o2", "d0_mm", "k_mm2_s", "pressure_mmHg") else [],
                          "modelling": "See model_exclusion (substantive differences in model variables exclude the test)",
                          "unresolved_question": "Which value matches the original downlinked data on the FLEX DVD addendum?"})
    for key, r in tpr.items():
        if key not in matched:
            items.append({"id": f"AUD-FLEX-TP{r['test']:03d}-MISSING", "status": "Missing information", "investigation": "FLEX", "test": f"TP FLEX-{r['test']:03d} ({r['identifier']})",
                          "quantity": "whole row", "values": [{"source_id": "SRC-FLEX-TP", "location": f"Table IX, PDF p.{r['pdf_page']}", "raw": "present"},
                          {"source_id": "SRC-PSI69", "location": "PSI-69 experimental table", "raw": "no row with this identifier and date"}],
                          "affected": [], "modelling": "Not in PSI-69, so not used", "unresolved_question": "Why is this test absent from the PSI table?"})
    if renumbered:
        items.append({"id": "AUD-FLEX-NUMBERING", "status": "Potential discrepancy", "investigation": "FLEX", "test": f"{len(renumbered)} tests",
                      "quantity": "Test number", "values": [{"source_id": "SRC-PSI69", "location": "PSI-69 'FLEX Test #'", "raw": f"e.g. #{renumbered[0][0]} for {renumbered[0][2]}"},
                      {"source_id": "SRC-FLEX-TP", "location": "Table IX 'FLEX test'", "raw": f"FLEX-{renumbered[0][1]:03d} for {renumbered[0][2]}"}],
                      "normalised": "Rows were matched on FLEX identifier and date instead of test number. Numbering differs, values do not.",
                      "affected": [], "modelling": "No impact (records matched by identifier and date)", "unresolved_question": None,
                      "detail": [{"psi_test": a, "tp_test": b, "identifier": c} for a, b, c in renumbered]})
    items.append({"id": "AUD-FLEX-UNIT", "status": "Confirmed discrepancy", "resolution": "Resolved by definition", "investigation": "FLEX",
                  "test": "All tests", "quantity": "Burning-rate constant unit label",
                  "values": [{"source_id": "SRC-PSI69", "location": "PSI-69 column header", "raw": "Burning rate; mm"},
                             {"source_id": "SRC-FLEX-TP", "location": "NASA/TP-2015-216046 Table IX header and Appendix A.1, PDF p.25-26", "raw": "Burning rate, mm2/s"}],
                  "normalised": "Values are burning-rate constants in mm^2/s; numbers are identical in both sources, only the unit label differs.",
                  "affected": ["FLEX burning-rate models", "EV-FLEX-02"], "modelling": "Models use mm^2/s", "unresolved_question": None})
    ntrs = json.load(open(os.path.join(D, "derived", "saffire_ntrs_table1.json")))["rows"]
    psi = {(s["investigation"], s["sample"]): s for s in data.saffire_samples()}
    for n in ntrs:
        s = psi.get((n["investigation"], n["psi_sample"]))
        if not s:
            continue
        loc_p = f"{ {'Saffire-I':'PSI-98','Saffire-II':'PSI-99','Saffire-III':'PSI-100'}[n['investigation']] } experimental table, sample {s['sample']}"
        loc_n = f"NTRS 20180005168 Table 1, PDF p.30, row {n['ntrs_sample']}"
        base = {"investigation": n["investigation"], "test": f"Sample {s['sample']} (NTRS {n['ntrs_sample']})"}
        def add(q, status, pv, nv, norm, affected, modelling, question):
            items.append({**base, "id": f"AUD-{n['investigation'].upper().replace('-', '')}-{s['sample']}-{re.sub(r'[^a-z]+', '-', q.lower()).strip('-')}", "status": status, "quantity": q,
                          "values": [{"source_id": s["source_id"], "location": loc_p, "raw": pv}, {"source_id": "SRC-SAF-2018", "location": loc_n, "raw": nv}],
                          "normalised": norm, "affected": affected, "modelling": modelling, "unresolved_question": question})
        if s["flow_cm_s"] is not None and s["flow_cm_s"] != n["flow_cm_s"]:
            add("Air flow velocity", "Confirmed discrepancy", s["flow_raw"], f"{n['flow_cm_s']} cm/s", f"{s['flow_cm_s']:g} vs {n['flow_cm_s']} cm/s (same unit)",
                [e["id"] for e in data.evidence() if n["ntrs_result_row"] in e["quote"] or n["ntrs_sample"] + " " in e["quote"]] + ["Fabric flame-spread comparisons"],
                "Excluded from flow-dependent comparisons", "Which flow setting was actually used? A third primary source (operations log or telemetry) is needed.")
        if not (s["material_raw"] or "").strip():
            add("Material", "Missing information", "(blank)", n["material"], f"NTRS gives {n['material']}", [], "Material taken from NTRS, flagged", "Confirm material from the PSI sample documentation")
        pt, note = _mm(s["thickness_raw"], "cm" if "(cm)" in " ".join(k for k in s["raw"] if "hick" in k) else None)
        nt, _ = _mm(n["thickness"])
        if pt is not None and nt is not None and abs(pt - nt) > 1e-6:
            status = "Potential discrepancy"
            add("Sample thickness", status, s["thickness_raw"], n["thickness"], f"{note}; PSI {pt:g} mm vs NTRS {nt:g} mm",
                [], "Thickness not used by models", "Is this a unit-label error (cm vs mm) or a real difference?")
        elif note and "decimal" in note:
            add("Sample thickness", "Potential discrepancy", s["thickness_raw"], n["thickness"], note, [], "No modelling impact", "Confirm the intended value with the PSI curators")
        lw = (s["length_raw"] or "").strip(); ww = (s["width_raw"] or "").strip()
        if n["investigation"] == "Saffire-I" and _num(lw) == _num(n["width"]) and _num(ww) == _num(n["length"]):
            add("Sample length and width", "Potential discrepancy", f"length {lw}, width {ww}", f"width {n['width']}, length {n['length']}",
                "Length and width appear swapped between sources", [], "No modelling impact", "Confirm sample orientation from drawings")
    for it in items:
        classify(it)
    counts, cls = {}, {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
        cls[it["classification"]] = cls.get(it["classification"], 0) + 1
    return {"generated_from": ["PSI-69 vs NASA/TP-2015-216046 Table IX (all 274 tests, 11 fields)", "PSI-98/99/100 vs NTRS 20180005168 Table 1 (13 samples)"],
            "flex_rows_compared": len(data.flex_tests()), "flex_field_mismatches": flex_mismatch, "counts": counts, "classification_counts": cls, "items": items,
            "tolerances": TOL_DOC,
            "method": __doc__.strip()}


TOL_DOC = ("Numeric FLEX fields: a difference no larger than half a unit of the coarser reported precision (e.g. 4.6 vs 4.58 mm) is a "
           "rounding/reporting-precision difference; beyond that, a relative difference <= 5% is a minor difference and > 5% is substantive. "
           "Only substantive differences in model inputs or outputs (O2, pressure, D0, K) exclude a test from fitting.")
MODEL_VARS = {"Ambient pressure", "O2 mole fraction", "Initial droplet diameter", "Burning-rate constant"}


def _dec(x):
    t = repr(float(x))
    return 0 if "e" in t else len(t.split(".")[1].rstrip("0"))


def classify(it):
    """Adds classification, explanation, significance, resolution and exclusion fields (does not change the source values)."""
    q = it["quantity"]; vals = [v.get("raw") for v in it["values"]]
    it["test_id"] = it.get("test")
    if it["status"] == "Missing information":
        c, why, sig = "Missing information", "A value is blank or absent in one source.", "Low unless the missing value is a model input"
    elif it["id"] == "AUD-FLEX-UNIT":
        c, why, sig = "Unit or label difference", "The column header unit differs; numbers are identical. The TP definition gives mm^2/s.", "High for interpretation, resolved"
    elif it["id"] == "AUD-FLEX-NUMBERING" or "length and width" in q.lower() or ("thickness" in q.lower() and "decimal" in (it.get("normalised") or "")):
        c, why, sig = "Potential transcription error", it.get("normalised") or "Formatting or ordering differs between sources.", "Low (no model uses these values)"
    elif "thickness" in q.lower():
        c, why, sig = "Unit or label difference", "Values differ by roughly a factor of ten, consistent with a cm/mm unit label error; not proven.", "Medium (sample description)"
    elif all(isinstance(v, (int, float)) for v in vals) and len(vals) == 2:
        a, b = vals; half = 0.5 * 10 ** -min(_dec(a), _dec(b)); d = abs(a - b); rel = d / max(abs(a), abs(b)) if max(abs(a), abs(b)) else 0
        if d <= half + 1e-12:
            c, why = "Rounding or reporting-precision difference", f"|{a} - {b}| = {d:.3g} is within half a unit ({half:g}) of the coarser reported precision."
        elif rel <= 0.05:
            c, why = "Minor difference beyond reporting precision", f"Differs by {d:.3g} ({rel:.1%}), more than rounding explains but small."
        else:
            c, why = "Substantive discrepancy", f"Differs by {d:.3g} ({rel:.1%}) for the same test and quantity in two primary NASA sources."
        sig = "High (model variable)" if q in MODEL_VARS else "Medium"
    else:
        c, why, sig = "Substantive discrepancy", it.get("normalised") or "Two primary sources report different values for the same test and quantity.", "High"
    it["classification"] = c; it["explanation"] = why; it["significance"] = sig
    it["resolution_status"] = it.get("resolution") or ("Explained (rounding)" if c.startswith("Rounding") else "Unresolved: needs a third primary source")
    it["model_exclusion"] = bool(it["id"].startswith("AUD-FLEX-") and it["id"].split("-")[2].isdigit() and c == "Substantive discrepancy" and q in MODEL_VARS)
    return it


def excluded_flex_tests() -> set[int]:
    return {int(i["id"].split("-")[2]) for i in run()["items"] if i.get("model_exclusion")}
