"""Dual knowledge graphs.

Spacecraft domain: Spacecraft -HAS_COMPARTMENT-> Compartment -CONTAINS-> Object -HAS_COMPONENT-> Component -MADE_OF-> Material,
                   Component -IN_FORM-> MaterialForm, Spacecraft -OPERATES_IN-> MissionCondition
Science domain:    Investigation -HAS_TEST-> ExperimentalTest -RECORDED_IN-> Dataset, Finding -REPORTED_IN-> Source,
                   Finding -FROM_INVESTIGATION-> Investigation, Finding -INVOLVES-> Material, Finding -UNDER-> Condition,
                   Finding -CONCERNS-> Concern, Dataset -RECORDS-> Investigation, DataConflict -FLAGS-> Investigation,
                   Model -FITTED_ON-> Dataset, Model -PREDICTS_FOR-> Material, ResearchGap -ABOUT-> Material
Bridges: shared Material nodes; MissionCondition -MATCHES-> Condition (same gravity regime); Material -RELATED_TO-> Material.

The graph is held in memory (networkx) and mirrored to Neo4j AuraDB when NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD are set.
The status endpoint reports the real Neo4j connection result; it never claims a live connection that was not verified.
"""
from __future__ import annotations
import os, time
from functools import lru_cache
import networkx as nx
from . import data, store

_cache = {"g": None}
NEO = {"configured": bool(os.environ.get("NEO4J_URI")), "connected": False, "last_sync": None, "error": None, "nodes_synced": 0}


def invalidate():
    _cache["g"] = None
    if NEO.get("connected"):  # keep Neo4j in step with configuration edits (background, debounced)
        import threading
        if _cache.get("timer"):
            _cache["timer"].cancel()
        _cache["timer"] = threading.Timer(2.0, neo4j_sync); _cache["timer"].daemon = True; _cache["timer"].start()


def _add(g, nid, label, **p):
    g.add_node(nid, label=label, **p)


def build() -> nx.MultiDiGraph:
    if _cache["g"] is not None:
        return _cache["g"]
    g = nx.MultiDiGraph()
    al = data.material_aliases()
    for mid, m in data.materials().items():
        _add(g, mid, "Material", name=m["name"], domain="bridge", cls=m["class"], user_defined=m.get("user_defined", False))
    for mid, m in data.materials().items():
        for r in m.get("related_to", []):
            if r in g:
                g.add_edge(mid, r, key="RELATED_TO", rel="RELATED_TO")
    for sc in store.list_spacecraft():
        _add(g, sc["id"], "Spacecraft", name=sc["name"], domain="spacecraft")
        a = sc["atmosphere"]
        mc = f"MC:{a['gravity']}|{a['o2_pct']}|{a['pressure_kpa']}"
        _add(g, mc, "MissionCondition", name=f"{a['o2_pct']}% O2, {a['pressure_kpa']} kPa, {a['gravity']}", domain="spacecraft", gravity=a["gravity"])
        g.add_edge(sc["id"], mc, key="OPERATES_IN", rel="OPERATES_IN")
        for c in sc.get("compartments", []):
            cid = f"{sc['id']}/{c['id']}"
            _add(g, cid, "Compartment", name=c["name"], domain="spacecraft", spacecraft=sc["id"])
            g.add_edge(sc["id"], cid, key="HAS_COMPARTMENT", rel="HAS_COMPARTMENT")
            for o in c.get("objects", []):
                oid = f"{cid}/{o['id']}"
                _add(g, oid, "Object", name=o["name"], domain="spacecraft", spacecraft=sc["id"], category=o.get("category"))
                g.add_edge(cid, oid, key="CONTAINS", rel="CONTAINS")
                for k in o.get("components", []):
                    kid = f"{oid}/{k['id']}"
                    _add(g, kid, "Component", name=k["name"], domain="spacecraft", spacecraft=sc["id"], form=k.get("form"))
                    g.add_edge(oid, kid, key="HAS_COMPONENT", rel="HAS_COMPONENT")
                    if k["material_id"] in g:
                        g.add_edge(kid, k["material_id"], key="MADE_OF", rel="MADE_OF")
                    if k.get("form"):
                        fid = "FORM:" + k["form"]; _add(g, fid, "MaterialForm", name=k["form"], domain="spacecraft")
                        g.add_edge(kid, fid, key="IN_FORM", rel="IN_FORM")
    for sid, s in data.sources().items():
        _add(g, sid, "Source", name=s["title"], domain="science", identifier=s["identifier"])
    invs = set()
    for e in data.evidence():
        inv = "INV:" + e["investigation"]; invs.add(inv)
        _add(g, inv, "Investigation", name=e["investigation"], domain="science")
        _add(g, e["id"], "Finding", name=e["statement"][:90], domain="science", category=e["category"])
        g.add_edge(e["id"], e["source_id"], key="REPORTED_IN", rel="REPORTED_IN")
        g.add_edge(e["id"], inv, key="FROM_INVESTIGATION", rel="FROM_INVESTIGATION")
        for mname in e["materials"]:
            mid = al.get(mname.lower())
            if mid:
                g.add_edge(e["id"], mid, key="INVOLVES", rel="INVOLVES")
        if e.get("gravity"):
            cn = "COND:gravity=" + e["gravity"]; _add(g, cn, "Condition", name=e["gravity"], domain="science")
            g.add_edge(e["id"], cn, key="UNDER", rel="UNDER")
        for cc in e.get("concerns", []):
            cn = "CONCERN:" + cc; _add(g, cn, "Concern", name=cc, domain="science")
            g.add_edge(e["id"], cn, key="CONCERNS", rel="CONCERNS")
    for ds, inv in (("SRC-PSI69", "FLEX"), ("SRC-PSI98", "Saffire-I"), ("SRC-PSI99", "Saffire-II"), ("SRC-PSI100", "Saffire-III"), ("SRC-PSI25", "BASS-II"), ("SRC-PSI26", "BASS")):
        n = "INV:" + inv
        if n not in g:
            _add(g, n, "Investigation", name=inv, domain="science")
        g.add_edge(ds, n, key="RECORDS", rel="RECORDS")
    # experimental tests from the original PSI tables
    for t in data.flex_tests():
        tid = f"TEST:FLEX:{t['identifier']}:{t['date']}"
        _add(g, tid, "ExperimentalTest", name=f"FLEX {t['identifier']} ({t['fuel']})", domain="science")
        g.add_edge("INV:FLEX", tid, key="HAS_TEST", rel="HAS_TEST"); g.add_edge(tid, "SRC-PSI69", key="RECORDED_IN", rel="RECORDED_IN")
        m = "MAT-METHANOL" if t["fuel"] == "methanol" else "MAT-HEPTANE"
        g.add_edge(tid, m, key="TESTED_MATERIAL", rel="TESTED_MATERIAL")
    for sm in data.saffire_samples():
        tid = f"TEST:{sm['investigation']}:{sm['sample']}"
        inv = "INV:" + sm["investigation"]
        if inv not in g:
            _add(g, inv, "Investigation", name=sm["investigation"], domain="science")
        _add(g, tid, "ExperimentalTest", name=f"{sm['investigation']} sample {sm['sample']}", domain="science")
        g.add_edge(inv, tid, key="HAS_TEST", rel="HAS_TEST"); g.add_edge(tid, sm["source_id"], key="RECORDED_IN", rel="RECORDED_IN")
    from .coverage import _bass_mat
    for t in data.bass2_tests():
        mid = _bass_mat(t)
        if not mid or not t.get("test"):
            continue
        tid = f"TEST:BASS-II:{t['test']}"
        if "INV:BASS-II" not in g:
            _add(g, "INV:BASS-II", "Investigation", name="BASS-II", domain="science")
        _add(g, tid, "ExperimentalTest", name=f"BASS-II {t['test']} ({t['material_raw'][:30]})", domain="science")
        g.add_edge("INV:BASS-II", tid, key="HAS_TEST", rel="HAS_TEST"); g.add_edge(tid, "SRC-PSI25", key="RECORDED_IN", rel="RECORDED_IN")
        g.add_edge(tid, mid, key="TESTED_MATERIAL", rel="TESTED_MATERIAL")
    for e in data.evidence():
        if e.get("gravity"):
            for mcn, d in list(g.nodes(data=True)):
                if d["label"] == "MissionCondition" and d.get("gravity") == e["gravity"]:
                    g.add_edge(mcn, "COND:gravity=" + e["gravity"], key="MATCHES", rel="MATCHES")
    for mid in data.materials():
        if not data.evidence_for_material(mid):
            gid = "GAP:" + mid; _add(g, gid, "ResearchGap", name=f"No library evidence: {data.materials()[mid]['name']}", domain="science")
            g.add_edge(gid, mid, key="ABOUT", rel="ABOUT")
    from . import audit, models
    for it in audit.run()["items"]:
        if it["status"] != "Missing information" or it["id"].startswith("AUD-SAFF"):
            _add(g, it["id"], "DataConflict", name=f"{it['quantity']}: {it['status']}", domain="science", status=it["status"])
            inv = "INV:" + it["investigation"]
            if inv in g:
                g.add_edge(it["id"], inv, key="FLAGS", rel="FLAGS")
    for m in models.registry():
        _add(g, m["model_id"], "Model", name=m["model_id"], domain="science", status=m["status"])
        g.add_edge(m["model_id"], "SRC-PSI69", key="FITTED_ON", rel="FITTED_ON")
        g.add_edge(m["model_id"], "MAT-METHANOL" if m["fuel"] == "methanol" else "MAT-HEPTANE", key="PREDICTS_FOR", rel="PREDICTS_FOR")
    _cache["g"] = g
    return g


def stats():
    g = build()
    by = {}
    for _, d in g.nodes(data=True):
        by[d["label"]] = by.get(d["label"], 0) + 1
    rels = {}
    for *_, d in g.edges(data=True):
        rels[d["rel"]] = rels.get(d["rel"], 0) + 1
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "by_label": by, "by_relationship": rels, "neo4j": neo4j_status()}


def subgraph(center: str, depth: int = 2, domain: str | None = None, limit: int = 220):
    g = build()
    if center not in g:
        return {"nodes": [], "edges": []}
    u = g.to_undirected(as_view=True)
    seen = {center: 0}; frontier = [center]
    for d in range(depth):
        nxt = []
        for n in frontier:
            for m in u.neighbors(n):
                if m not in seen and (domain is None or g.nodes[m]["domain"] in (domain, "bridge")):
                    seen[m] = d + 1; nxt.append(m)
        frontier = nxt
    nodes = list(seen)[:limit]; ns = set(nodes)
    return {"nodes": [{"id": n, **g.nodes[n], "hop": seen[n]} for n in nodes],
            "edges": [{"source": a, "target": b, "rel": d["rel"]} for a, b, d in g.edges(data=True) if a in ns and b in ns]}


def materials_for(node: str) -> list[str]:
    """Traverse down from a spacecraft, compartment, object or component to the materials it is made of."""
    g = build()
    if node not in g:
        return []
    if g.nodes[node]["label"] == "Material":
        return [node]
    keep = {"HAS_COMPARTMENT", "CONTAINS", "HAS_COMPONENT", "MADE_OF"}  # containment only; RELATED_TO is not followed
    seen, stack, out = {node}, [node], set()
    while stack:
        n = stack.pop()
        for _, b, d in g.out_edges(n, data=True):
            if d["rel"] in keep and b not in seen:
                seen.add(b); stack.append(b)
                if g.nodes[b]["label"] == "Material":
                    out.add(b)
    return sorted(out)


def findings_for_material(mid: str) -> list[str]:
    g = build()
    return sorted(a for a, b, d in g.in_edges(mid, data=True) if d["rel"] == "INVOLVES")


def trace(node: str) -> list[dict]:
    """Explain the multi-hop path from a spacecraft element to NASA findings and sources (Neo4j when connected)."""
    t = neo4j_trace(node)
    if t is not None:
        return t
    g = build(); out = []
    for mid in materials_for(node):
        try:
            path = nx.shortest_path(g, node, mid) if node != mid else [mid]
        except nx.NetworkXNoPath:
            path = [node, mid]
        for f in findings_for_material(mid):
            src = next(b for _, b, d in g.out_edges(f, data=True) if d["rel"] == "REPORTED_IN")
            inv = next(b for _, b, d in g.out_edges(f, data=True) if d["rel"] == "FROM_INVESTIGATION")
            out.append({"path": [{"id": p, "label": g.nodes[p]["label"], "name": g.nodes[p]["name"]} for p in path] +
                        [{"id": f, "label": "Finding", "name": g.nodes[f]["name"]}, {"id": inv, "label": "Investigation", "name": g.nodes[inv]["name"]},
                         {"id": src, "label": "Source", "name": g.nodes[src]["name"]}], "material": mid, "finding": f, "engine": "networkx"})
    return out


# ---------- Neo4j mirror ----------
class _Shared:
    """One long-lived driver (Neo4j drivers are designed to be reused); close() is a no-op so callers stay simple."""
    drv = None

    def __init__(self, d): self.d = d
    def __getattr__(self, k): return getattr(self.d, k)
    def close(self): pass


def _driver():
    from neo4j import GraphDatabase
    if _Shared.drv is None:
        _Shared.drv = GraphDatabase.driver(os.environ["NEO4J_URI"].strip(), auth=(os.environ.get("NEO4J_USERNAME", "neo4j").strip(), os.environ["NEO4J_PASSWORD"].strip()),
                                           connection_timeout=10)
    return _Shared(_Shared.drv)


def _db():
    return os.environ.get("NEO4J_DATABASE", "neo4j")


def neo4j_status():
    return {**NEO, **NEO_STATS, "engine": "neo4j" if NEO["connected"] else "networkx",
            "mode": "Neo4j AuraDB (verified)" if NEO["connected"] else ("Neo4j configured but not connected: using in-memory graph + SQLite" if NEO["configured"] else "In-memory graph + SQLite fallback (Neo4j not configured)")}


def neo4j_sync():
    """Idempotent sync with parameterised Cypher: MERGE every node and relationship by stable id, then delete nodes and
    relationships that no longer exist in the current configuration. Running it twice leaves the same graph."""
    NEO["configured"] = bool(os.environ.get("NEO4J_URI"))
    if not NEO["configured"]:
        NEO["error"] = "NEO4J_URI not set"
        return neo4j_status()
    try:
        drv = _driver(); drv.verify_connectivity()
        g = build(); stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        nodes = [{"id": n, "label": d["label"], "name": str(d.get("name", "")), "domain": d.get("domain", "")} for n, d in g.nodes(data=True)]
        edges = [{"a": a, "b": b, "rel": d["rel"]} for a, b, d in g.edges(data=True)]
        with drv.session(database=_db()) as s:
            s.run("CREATE CONSTRAINT sxs_id IF NOT EXISTS FOR (n:SXS) REQUIRE n.id IS UNIQUE")
            for i in range(0, len(nodes), 500):
                s.run("UNWIND $rows AS r MERGE (n:SXS {id:r.id}) SET n.label=r.label, n.name=r.name, n.domain=r.domain, n.sync=$stamp",
                      rows=nodes[i:i + 500], stamp=stamp)
            for i in range(0, len(edges), 500):
                s.run("UNWIND $rows AS r MATCH (a:SXS {id:r.a}), (b:SXS {id:r.b}) MERGE (a)-[e:REL {type:r.rel}]->(b) SET e.sync=$stamp",
                      rows=edges[i:i + 500], stamp=stamp)
            s.run("MATCH (:SXS)-[e:REL]->(:SXS) WHERE e.sync <> $stamp DELETE e", stamp=stamp)
            s.run("MATCH (n:SXS) WHERE n.sync <> $stamp DETACH DELETE n", stamp=stamp)
            nc = s.run("MATCH (n:SXS) RETURN count(n) AS c").single()["c"]
            ec = s.run("MATCH (:SXS)-[e:REL]->(:SXS) RETURN count(e) AS c").single()["c"]
        drv.close()
        NEO.update(connected=True, last_sync=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), error=None, nodes_synced=nc, edges_synced=ec,
                   matches_local=(nc == g.number_of_nodes() and ec == g.number_of_edges()))
    except Exception as ex:  # report, never fake
        NEO.update(connected=False, error=f"{type(ex).__name__}: {str(ex)[:200]}")
    return neo4j_status()


NEO_STATS = {"retrieval_queries": 0, "retrieval_errors": 0, "last_query_ms": None}


def neo4j_findings(node_ids: list[str]) -> dict[str, list[str]] | None:
    """GraphRAG expansion executed in Neo4j: for each linked entity, containment traversal to its materials, then the NASA
    findings that INVOLVE those materials. Returns {entity: [finding ids]} or None when Neo4j is not connected/fails."""
    if not NEO["connected"] or not node_ids:
        return None
    t0 = time.perf_counter()
    try:
        q = ("UNWIND $ids AS eid MATCH (s:SXS {id:eid}) "
             "OPTIONAL MATCH p=(s)-[:REL*0..4]->(m:SXS {label:'Material'}) "
             "WHERE all(r IN relationships(p) WHERE r.type IN ['HAS_COMPARTMENT','CONTAINS','HAS_COMPONENT','MADE_OF']) "
             "OPTIONAL MATCH (f:SXS {label:'Finding'})-[:REL {type:'INVOLVES'}]->(m) "
             "RETURN eid, collect(DISTINCT f.id) AS findings")
        with _driver().session(database=_db()) as s:
            out = {r["eid"]: sorted(x for x in r["findings"] if x) for r in s.run(q, ids=list(node_ids))}
        NEO_STATS.update(retrieval_queries=NEO_STATS["retrieval_queries"] + 1, last_query_ms=round((time.perf_counter() - t0) * 1000))
        return out
    except Exception as ex:
        NEO_STATS["retrieval_errors"] += 1
        NEO.update(connected=False, error=f"{type(ex).__name__}: {str(ex)[:200]}")
        return None


def neo4j_verify(sample: int = 40) -> dict:
    """Parity check: the same GraphRAG expansion computed in Neo4j and in the in-memory graph must give identical findings."""
    if not NEO["connected"]:
        return {"verified": False, "reason": NEO.get("error") or "Neo4j not connected"}
    g = build()
    ids = [n for n, d in g.nodes(data=True) if d["label"] in ("Spacecraft", "Compartment", "Object", "Component", "Material")][:sample]
    neo = neo4j_findings(ids)
    if neo is None:
        return {"verified": False, "reason": NEO.get("error")}
    local = {i: sorted({f for m in materials_for(i) for f in findings_for_material(m)}) for i in ids}
    diff = [i for i in ids if neo.get(i, []) != local[i]]
    return {"verified": not diff, "entities_checked": len(ids), "entities_with_findings": sum(1 for i in ids if local[i]),
            "mismatches": diff[:10], "neo4j_query_ms": NEO_STATS["last_query_ms"]}


def neo4j_trace(node: str) -> list[dict] | None:
    """Multi-hop traversal executed in Neo4j (parameterised): element -> materials -> findings -> investigation & source."""
    if not NEO["connected"]:
        return None
    try:
        drv = _driver()
        q = ("MATCH p=(s:SXS {id:$id})-[:REL*0..4]->(m:SXS {label:'Material'}) "
             "WHERE all(r IN relationships(p) WHERE r.type IN ['HAS_COMPARTMENT','CONTAINS','HAS_COMPONENT','MADE_OF']) "
             "MATCH (f:SXS {label:'Finding'})-[:REL {type:'INVOLVES'}]->(m) "
             "MATCH (f)-[:REL {type:'FROM_INVESTIGATION'}]->(i) MATCH (f)-[:REL {type:'REPORTED_IN'}]->(src) "
             "RETURN [n IN nodes(p) | {id:n.id, label:n.label, name:n.name}] AS path, m.id AS material, f.id AS finding, "
             "{id:f.id,label:'Finding',name:f.name} AS fn, {id:i.id,label:'Investigation',name:i.name} AS inv, {id:src.id,label:'Source',name:src.name} AS src")
        with drv.session(database=_db()) as s:
            rows = [r.data() for r in s.run(q, id=node)]
        drv.close()
        return [{"path": r["path"] + [r["fn"], r["inv"], r["src"]], "material": r["material"], "finding": r["finding"], "engine": "neo4j"} for r in rows]
    except Exception as ex:
        NEO.update(connected=False, error=f"{type(ex).__name__}: {str(ex)[:200]}")
        return None