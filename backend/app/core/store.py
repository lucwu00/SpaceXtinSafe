"""SQLite persistence for spacecraft configurations and saved scenarios (works without Neo4j)."""
from __future__ import annotations
import copy, json, os, sqlite3, threading, uuid
from . import data

DB = os.environ.get("SPACEXI_DB", os.path.join(data.DATA, "spacextinsafe.sqlite3"))
_lock = threading.Lock()


def _con():
    c = sqlite3.connect(DB)
    c.execute("create table if not exists spacecraft (id text primary key, body text not null)")
    c.execute("create table if not exists scenario (id text primary key, body text not null)")
    c.execute("create table if not exists material (id text primary key, body text not null)")
    c.execute("create table if not exists procedure (id text primary key, spacecraft_id text, body text not null)")
    return c


def _seed():
    with _lock, _con() as c:
        if c.execute("select count(*) from spacecraft").fetchone()[0] == 0:
            for t in data.templates():
                s = copy.deepcopy(t); s["id"] = t["id"].replace("TPL-", "SC-"); s["template_id"] = t["id"]; s["origin"] = "Quick Start template"
                c.execute("insert into spacecraft values (?,?)", (s["id"], json.dumps(s)))


def list_spacecraft():
    _seed()
    with _con() as c:
        return [json.loads(r[0]) for r in c.execute("select body from spacecraft order by id")]


def get_spacecraft(sid):
    _seed()
    with _con() as c:
        r = c.execute("select body from spacecraft where id=?", (sid,)).fetchone()
        return json.loads(r[0]) if r else None


def save_spacecraft(sc: dict):
    validate(sc)
    with _lock, _con() as c:
        c.execute("insert or replace into spacecraft values (?,?)", (sc["id"], json.dumps(sc)))
    from . import graph
    graph.invalidate()
    return sc


def delete_spacecraft(sid):
    with _lock, _con() as c:
        c.execute("delete from spacecraft where id=?", (sid,))
    from . import graph
    graph.invalidate()


def new_spacecraft(mode: str, template_id: str | None, name: str | None):
    if mode in ("quick", "customise"):
        t = next((x for x in data.templates() if x["id"] == template_id), None)
        if not t:
            raise ValueError("Unknown template")
        sc = copy.deepcopy(t); sc["template_id"] = t["id"]
        sc["origin"] = "Quick Start template" if mode == "quick" else f"Customised from {t['name']}"
    else:
        sc = {"name": name or "New spacecraft", "vehicle_class": "Custom (built from scratch)", "description": "",
              "atmosphere": {"o2_pct": 21.0, "pressure_kpa": 101.3, "gravity": "microgravity", "ventilation_cm_s": 10, "diluent": "nitrogen"},
              "compartments": [], "origin": "Built from scratch", "template_id": None}
    sc["id"] = "SC-" + uuid.uuid4().hex[:8].upper()
    if name:
        sc["name"] = name
    return save_spacecraft(sc)


def validate(sc):
    a = sc.get("atmosphere", {})
    errs = []
    if not (0 < float(a.get("o2_pct", 0)) <= 100): errs.append("atmosphere.o2_pct must be in (0, 100]")
    if not (0 < float(a.get("pressure_kpa", 0)) <= 200): errs.append("atmosphere.pressure_kpa must be in (0, 200]")
    if a.get("gravity") not in ("microgravity", "partial gravity", "1-g"): errs.append("atmosphere.gravity must be microgravity, partial gravity or 1-g")
    ids = set()
    mats = data.materials()
    for c in sc.get("compartments", []):
        for o in c.get("objects", []):
            for k in o.get("components", []):
                if k.get("material_id") not in mats: errs.append(f"component {k.get('id')} has unknown material {k.get('material_id')}")
                if k.get("id") in ids: errs.append(f"duplicate component id {k.get('id')}")
                ids.add(k.get("id"))
    if errs:
        raise ValueError("; ".join(errs))


def list_scenarios():
    with _con() as c:
        return [json.loads(r[0]) for r in c.execute("select body from scenario")]


def save_scenario(sc):
    sc.setdefault("id", "SN-" + uuid.uuid4().hex[:8].upper())
    with _lock, _con() as c:
        c.execute("insert or replace into scenario values (?,?)", (sc["id"], json.dumps(sc)))
    return sc


_mat_cache = {"v": None}


def custom_materials() -> dict:
    if _mat_cache["v"] is None:
        with _con() as c:
            _mat_cache["v"] = {m["id"]: m for m in (json.loads(r[0]) for r in c.execute("select body from material"))}
    return _mat_cache["v"]


def save_material(m: dict) -> dict:
    """User-defined material. Unknown properties stay null; no combustion properties are ever assigned."""
    name = (m.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    base = data._base_materials()
    rel = [r for r in m.get("related_to", []) if r in base]
    mid = m.get("id") or "UMAT-" + uuid.uuid4().hex[:8].upper()
    rec = {"id": mid, "name": name, "scientific_name": m.get("scientific_name") or None, "category": m.get("category") or "User-defined",
           "class": m.get("class") or "user-defined", "default_form": m.get("form") or None, "forms": [m["form"]] if m.get("form") else [],
           "applications": [a for a in m.get("applications", []) if a], "aliases": [a for a in m.get("aliases", []) if a], "related_to": rel,
           "phenomenon": m.get("phenomenon") or "unknown", "composition": m.get("composition") or None, "grade": m.get("grade") or None,
           "thickness_mm": m.get("thickness_mm"), "mass_g": m.get("mass_g"), "geometry": m.get("geometry") or None,
           "provenance": "User-defined in SpaceXtinSafe (not verified)", "user_defined": True,
           "notes": "Entered by a user. Properties not supplied are unknown."}
    with _lock, _con() as c:
        c.execute("insert or replace into material values (?,?)", (mid, json.dumps(rec)))
    _mat_cache["v"] = None
    from . import graph
    graph.invalidate()
    return rec


def delete_material(mid: str):
    with _lock, _con() as c:
        c.execute("delete from material where id=?", (mid,))
    _mat_cache["v"] = None
    from . import graph
    graph.invalidate()


def duplicate_spacecraft(sid: str, name: str | None = None):
    sc = get_spacecraft(sid)
    if not sc:
        raise ValueError("Unknown spacecraft")
    sc = copy.deepcopy(sc); sc["id"] = "SC-" + uuid.uuid4().hex[:8].upper(); sc["name"] = name or f"{sc['name']} (copy)"
    sc["origin"] = f"Duplicated from {get_spacecraft(sid)['name']}"
    return save_spacecraft(sc)


def list_procedures(spacecraft_id):
    with _con() as c:
        return [json.loads(r[0]) for r in c.execute("select body from procedure where spacecraft_id=?", (spacecraft_id,))]


def save_procedure(p: dict):
    """Registers a reference to an authorised vehicle procedure document (title, identifier, link). Content is never generated."""
    if not p.get("title") or not p.get("spacecraft_id"):
        raise ValueError("title and spacecraft_id are required")
    rec = {"id": p.get("id") or "PROC-" + uuid.uuid4().hex[:8].upper(), "spacecraft_id": p["spacecraft_id"], "title": p["title"],
           "identifier": p.get("identifier"), "url": p.get("url"), "authority": p.get("authority"), "registered_by": "user (not verified by SpaceXtinSafe)"}
    with _lock, _con() as c:
        c.execute("insert or replace into procedure values (?,?,?)", (rec["id"], rec["spacecraft_id"], json.dumps(rec)))
    return rec
