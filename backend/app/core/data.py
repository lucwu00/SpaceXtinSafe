"""Loads the curated library and parses the original NASA PSI experimental tables (no values are edited)."""
from __future__ import annotations
import csv, json, os, re
from functools import lru_cache

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW = os.path.join(DATA, "raw")


def _j(*p):
    with open(os.path.join(DATA, *p), encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def sources() -> dict:
    return {s["id"]: s for s in _j("curated", "sources.json")}


@lru_cache
def evidence() -> list[dict]:
    ev = _j("curated", "evidence.json")
    src = sources()
    for e in ev:
        s = src[e["source_id"]]
        e["source_title"], e["source_url"], e["source_identifier"] = s["title"], s["url"], s["identifier"]
    return ev


@lru_cache
def _base_materials() -> dict:
    return {m["id"]: m for m in _j("curated", "materials.json")}


def materials() -> dict:
    """Catalogue materials plus user-defined materials (SQLite)."""
    from . import store
    return {**_base_materials(), **store.custom_materials()}


EV_CATS_DIRECT = {"Experimentally observed", "Documented material interaction", "Conflicting evidence", "Research summary", "Definition", "Data-quality caveat"}
STATUS_ORDER = ["Verified NASA combustion evidence", "Related but indirect evidence", "Supplementary evidence (historical incident context)",
                "Insufficient evidence (context statements only)", "User-defined material, no evidence found", "Catalogue entry, no evidence in library"]


def material_status(mid: str) -> dict:
    """Evidence status computed from the verified findings (never assigned by hand)."""
    m = materials()[mid]
    ev = evidence_for_material(mid)
    cats = {e["category"] for e in ev}
    related = [r for r in m.get("related_to", []) if r in materials() and evidence_for_material(r)]
    if cats & EV_CATS_DIRECT:
        st = STATUS_ORDER[0]
    elif related:
        st = STATUS_ORDER[1]
    elif "Historical incident" in cats:
        st = STATUS_ORDER[2]
    elif ev:
        st = STATUS_ORDER[3]
    elif m.get("user_defined"):
        st = STATUS_ORDER[4]
    else:
        st = STATUS_ORDER[5]
    return {"status": st, "direct_findings": [e["id"] for e in ev], "related_materials": related,
            "related_findings": sorted({e["id"] for r in related for e in evidence_for_material(r)}),
            "note": "Absence of evidence in this library is not evidence that a material is non-flammable, and is not a confirmed gap in all literature."}


@lru_cache
def templates() -> list[dict]:
    return _j("curated", "spacecraft_templates.json")


@lru_cache
def provenance() -> dict:
    return _j("raw", "provenance.json")


def _open(fn):
    """PSI tables mix UTF-8 (with BOM) and Windows-1252; decode without altering content."""
    b = open(os.path.join(RAW, fn), "rb").read()
    try:
        t = b.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = b.decode("cp1252")
    import io
    return io.StringIO(t)


def _num(v):
    if v is None:
        return None
    v = str(v).strip()
    if v in ("", "n/a", "-", "–"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


@lru_cache
def flex_tests() -> list[dict]:
    """PSI-69 rows, one per FLEX test. Column 'Burning rate; mm' is the burning-rate constant in mm^2/s
    (unit verified against NASA/TP-2015-216046 Table IX; see audit AUD-FLEX-UNIT)."""
    out = []
    with _open("PSI-69_Experimental table_FLEX.csv") as f:
        for r in csv.DictReader(f):
            out.append({
                "test": int(r["FLEX Test #"]), "identifier": r["FLEX Identifier"].strip(), "date": r["Test Date"].strip(),
                "fuel": r["Fuel"].strip().lower().replace("heptane", "n-heptane") if r["Fuel"].strip() else None,
                "pressure_mmHg": _num(r["Ambient pressure; mmHg"]), "o2": _num(r["O initial ambient composition; mole fraction"]),
                "n2": _num(r["N initial ambient composition; mole fraction"]), "co2": _num(r["CO initial ambient composition; mole fraction"]),
                "he": _num(r["He initial ambient composition; mole fraction"]), "d0_mm": _num(r["Droplet initial diameter; mm"]),
                "ext_d_mm": _num(r["Visible flame extinction diameter; mm"]), "k_mm2_s": _num(r["Burning rate; mm"]),
                "burn_time_s": _num(r["Burn time; s"]), "end": r["Test end"].strip(),
                "record": f"PSI-69 experimental table, FLEX Test #{r['FLEX Test #']} ({r['FLEX Identifier'].strip()})",
            })
    return out


def _split_val(v):
    v = (v or "").strip()
    m = re.search(r"(-?\d*\.?\d+)", v)
    return (float(m.group(1)) if m else None), v


@lru_cache
def saffire_samples() -> list[dict]:
    """Saffire-I/II/III PSI table rows with raw strings kept next to parsed numbers."""
    out = []
    files = [("Saffire-I", "PSI-98_Experimental table_SAFFIRE-1.csv", "SRC-PSI98"),
             ("Saffire-II", "PSI-99_Experimental table_SAFFIRE-2.csv", "SRC-PSI99"),
             ("Saffire-III", "PSI-100_Experimental table_SAFFIRE-3.csv", "SRC-PSI100")]
    for inv, fn, sid in files:
        with _open(fn) as f:
            rows = list(csv.reader(f))
        hdr = [h.strip() for h in rows[0]]
        for r in rows[1:]:
            if not r or not r[0].strip() or r[0].strip().startswith("F") or r[0].lower().startswith("note"):
                continue
            d = {hdr[i]: (r[i].strip() if i < len(r) else "") for i in range(len(hdr))}
            if not d.get("Material") and not d.get("Air Flow (cm/s)") and not d.get("Air Flow"):
                continue
            flow_raw = d.get("Air Flow (cm/s)") or d.get("Air Flow") or ""
            out.append({"investigation": inv, "source_id": sid, "sample": d.get("Sample Number"), "material_raw": d.get("Material"),
                        "thickness_raw": d.get("Sample Thickness (cm)") or d.get("Samle Thickness") or d.get("Sample Thickness"),
                        "length_raw": d.get("Sample Length (cm)") or d.get("Sample Length"), "width_raw": d.get("Sample Width (cm)") or d.get("Sample Width"),
                        "flow_cm_s": _split_val(flow_raw)[0], "flow_raw": flow_raw,
                        "o2_raw": d.get("Percent O2") or d.get("Percent O2 (Note 1)"), "direction": (d.get("Flow Direction") or d.get("Direction") or "").strip(),
                        "spread_raw": d.get("?-g Spread Length"), "burn_length_raw": d.get("?-g Burn Length"), "raw": d})
    return out


@lru_cache
def bass2_tests() -> list[dict]:
    out = []
    with _open("PSI-25_Experimental table_BASS-II.csv") as f:
        for r in csv.DictReader(f):
            r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
            out.append({"test": r.get("Test #"), "pi": r.get("PI"), "material_raw": r.get("Fuel Sample Material"),
                        "o2_initial": _num(r.get("Calibrated  initial O2 % by vol")), "o2_final": _num(r.get("Calibrated final O2 % by vol")),
                        "fan_raw": r.get("Fan display"), "record": f"PSI-25 experimental table, test {r.get('Test #')}"})
    return out


def material_aliases() -> dict[str, str]:  # noqa: D401
    """lower-case evidence material name -> material id"""
    m = {}
    for mid, mat in materials().items():
        for a in [mat["name"], *mat["aliases"]]:
            m[a.lower()] = mid
    return m


def evidence_for_material(mid: str) -> list[dict]:
    al = material_aliases()
    return [e for e in evidence() if any(al.get(x.lower()) == mid for x in e["materials"])]
