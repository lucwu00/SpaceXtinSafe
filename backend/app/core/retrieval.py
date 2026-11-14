"""Evidence retrieval: keyword (BM25), semantic (sentence-transformers), hybrid (reciprocal rank fusion) and
hybrid + graph (adds findings reached by traversing the spacecraft graph from entities named in the question).

Semantic search is ON by default (SPACEXI_SEMANTIC=1). If the model weights cannot be loaded, the status says so and
semantic / hybrid modes are reported as unavailable rather than silently falling back.
"""
from __future__ import annotations
import math, os, re, time
from collections import Counter
from functools import lru_cache
import numpy as np
from . import data, graph, store

MODEL_NAME = os.environ.get("SPACEXI_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
SEM = {"enabled": os.environ.get("SPACEXI_SEMANTIC", "1") != "0", "loaded": False, "error": None, "dim": None, "model": MODEL_NAME, "embedding_check": None}
STOP = set("a an the of in on for to and or with by at from is are was were be what which how does do did that this these those it its as into about than under over our my".split())


def tok(s):
    return [w for w in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)?", s.lower()) if w not in STOP]


def doc_text(e):
    return " ".join([e["statement"], e["quote"], e["investigation"], " ".join(e["materials"]), " ".join(e.get("keywords", [])), " ".join(e.get("concerns", []))])


@lru_cache
def corpus():
    ev = data.evidence()
    return ev, [tok(doc_text(e)) for e in ev]


def bm25(q, k1=1.5, b=0.75):
    ev, docs = corpus()
    N = len(docs); avg = sum(map(len, docs)) / N
    df = Counter(w for d in docs for w in set(d))
    qt = tok(q); scores = []
    for d in docs:
        tf = Counter(d); s = 0.0
        for w in qt:
            if w in tf:
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avg))
        scores.append(s)
    order = np.argsort(scores)[::-1]
    return [(ev[i]["id"], float(scores[i])) for i in order if scores[i] > 0]


_model = {"m": None, "emb": None}


def _load():
    if not SEM["enabled"]:
        SEM["error"] = "Disabled by SPACEXI_SEMANTIC=0"; return None
    if _model["m"] is None and SEM["error"] is None:
        try:
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer(MODEL_NAME)
            ev, _ = corpus()
            emb = m.encode([doc_text(e) for e in ev], normalize_embeddings=True, show_progress_bar=False)
            a = m.encode(["methanol droplet burning rate"], normalize_embeddings=True)[0]
            b = m.encode(["alcohol droplet combustion speed"], normalize_embeddings=True)[0]
            c = m.encode(["lunar habitat airlock"], normalize_embeddings=True)[0]
            SEM.update(loaded=True, dim=int(emb.shape[1]), embedding_check={
                "corpus_embeddings": list(emb.shape), "norm_mean": float(np.linalg.norm(emb, axis=1).mean()),
                "cos(related paraphrase)": float(a @ b), "cos(unrelated)": float(a @ c),
                "passed": bool(a @ b > a @ c and np.isfinite(emb).all() and emb.std() > 0)})
            _model.update(m=m, emb=emb)
        except Exception as ex:
            SEM["error"] = f"{type(ex).__name__}: {str(ex)[:220]}"
    return _model["m"]


def semantic(q):
    m = _load()
    if m is None:
        return None
    ev, _ = corpus()
    qv = m.encode([q], normalize_embeddings=True)[0]
    s = _model["emb"] @ qv
    order = np.argsort(s)[::-1]
    return [(ev[i]["id"], float(s[i])) for i in order]


def rrf(*lists, k=60):
    sc = Counter()
    for lst in lists:
        for r, (i, _) in enumerate(lst):
            sc[i] += 1 / (k + r + 1)
    return sorted(sc.items(), key=lambda x: -x[1])


def entities(q, spacecraft_id=None):
    """Find spacecraft elements and materials named in the question (spacecraft names, compartment, object, component, material)."""
    ql = q.lower(); hits = []
    scs = store.list_spacecraft()
    if spacecraft_id:
        scs = [s for s in scs if s["id"] == spacecraft_id] + [s for s in scs if s["id"] != spacecraft_id]
    named_sc = [s for s in scs if s["name"].lower() in ql]
    # Bug fix (found during evaluation run 1): previously only the first spacecraft was searched when none was named.
    pool = named_sc or scs
    for sc in pool:
        if sc["name"].lower() in ql:
            hits.append(sc["id"])
        for c in sc["compartments"]:
            cid = f"{sc['id']}/{c['id']}"
            if c["name"].lower() in ql:
                hits.append(cid)
            for o in c["objects"]:
                oid = f"{cid}/{o['id']}"
                if o["name"].lower() in ql:
                    hits.append(oid)
                for k in o["components"]:
                    if k["name"].lower() in ql:
                        hits.append(f"{oid}/{k['id']}")
    for alias, mid in data.material_aliases().items():
        if re.search(r"\b" + re.escape(alias) + r"\b", ql):
            hits.append(mid)
    # most specific first: drop a spacecraft hit if a compartment/object inside it was named
    specific = [h for h in hits if not any(o != h and o.startswith(h + "/") for o in hits)]
    return specific


LAST_GRAPH_ENGINE = {"engine": None}


def graph_candidates(q, spacecraft_id=None):
    """Entity linking, then graph expansion. Runs in Neo4j when connected (parameterised Cypher); otherwise networkx."""
    ents = entities(q, spacecraft_id)
    neo = graph.neo4j_findings(ents) if ents else None
    LAST_GRAPH_ENGINE["engine"] = "neo4j" if neo is not None else "networkx"
    out, seen = [], set()
    for e in ents:
        fs = neo.get(e, []) if neo is not None else [f for mid in graph.materials_for(e) for f in graph.findings_for_material(mid)]
        for f in fs:
            if f not in seen:
                seen.add(f); out.append((f, 1.0))
    return out, ents


def search(q, mode="hybrid+graph", k=8, spacecraft_id=None):
    t0 = time.perf_counter()
    kw = bm25(q)
    note = None; ents = []
    if mode == "auto":
        mode = "hybrid+graph" if _load() is not None else "keyword+graph"
        if mode == "keyword+graph":
            note = f"Semantic model unavailable ({SEM['error']}); using keyword + graph."
    if mode == "keyword":
        ranked = kw
    elif mode == "keyword+graph":
        gc, ents = graph_candidates(q, spacecraft_id)
        ranked = rrf(kw, gc) if gc else kw
    elif mode == "semantic":
        s = semantic(q)
        if s is None:
            return {"mode": mode, "available": False, "reason": SEM["error"], "results": []}
        ranked = s
    else:
        s = semantic(q)
        if s is None:
            return {"mode": mode, "available": False, "reason": f"Hybrid needs semantic embeddings: {SEM['error']}", "results": []}
        ranked = rrf(kw, s[:30])
        if mode == "hybrid+graph":
            gc, ents = graph_candidates(q, spacecraft_id)
            if gc:
                ranked = rrf(kw, s[:30], gc)
            else:
                note = "No spacecraft element or material recognised; graph added nothing."
    evm = {e["id"]: e for e in data.evidence()}
    res = [{"rank": r + 1, "score": round(sc, 5), **evm[i]} for r, (i, sc) in enumerate(ranked[:k])]
    return {"mode": mode, "available": True, "results": res, "entities": ents, "note": note, "latency_ms": (time.perf_counter() - t0) * 1000,
            "graph_engine": LAST_GRAPH_ENGINE["engine"] if "graph" in mode else None}


def status():
    _load()
    return SEM