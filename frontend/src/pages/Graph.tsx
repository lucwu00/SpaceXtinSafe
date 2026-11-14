import { useEffect, useMemo, useRef, useState } from "react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from "d3-force";
import { api } from "../api";
import { useApp } from "../state";
import { Page, useAsync, Loading, Empty } from "../ui";

const COL: Record<string, string> = { Spacecraft: "#7cc4ff", Compartment: "#4ea1ff", Object: "#3b82d6", Component: "#2f6fb8", Material: "#ff8a3d",
  Finding: "#3ccf91", Investigation: "#b48cff", Source: "#9fb4cc", Condition: "#f5b84b", Concern: "#61708a", AuditItem: "#ff5d6c", Model: "#e879f9" };

function ForceGraph({ data, onPick, picked }: { data: any; onPick: (n: any) => void; picked: string | null }) {
  const [tick, setTick] = useState(0);
  const sim = useRef<any>(null);
  const nodes = useMemo(() => data.nodes.map((n: any) => ({ ...n })), [data]);
  const links = useMemo(() => data.edges.map((e: any) => ({ ...e })), [data]);
  useEffect(() => {
    sim.current?.stop();
    sim.current = forceSimulation(nodes).force("link", forceLink(links).id((d: any) => d.id).distance(46))
      .force("charge", forceManyBody().strength(-120)).force("center", forceCenter(500, 280)).force("collide", forceCollide(14))
      .on("tick", () => setTick((t) => t + 1));
    return () => sim.current?.stop();
  }, [nodes, links]);
  return (
    <svg className="graphbox" viewBox="0 0 1000 560" role="img" aria-label="Knowledge graph">
      {links.filter((l: any) => typeof l.source === "object" && l.source.x != null && l.target.x != null).map((l: any, i: number) => <g key={i}><line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="#2a3b5c" strokeWidth={1} />
        {nodes.length < 60 && <text x={(l.source.x + l.target.x) / 2} y={(l.source.y + l.target.y) / 2} fontSize={7} fill="#61708a">{l.rel}</text>}</g>)}
      {nodes.filter((n: any) => n.x != null).map((n: any) => <g key={n.id} transform={`translate(${n.x || 0},${n.y || 0})`} onClick={() => onPick(n)} style={{ cursor: "pointer" }}>
        <circle r={n.hop === 0 ? 11 : 7} fill={COL[n.label] || "#888"} stroke={picked === n.id ? "#fff" : "#0a1120"} strokeWidth={picked === n.id ? 2.5 : 1.5} />
        <text x={10} y={4} fontSize={9} fill="#c8d5e8">{String(n.name).slice(0, 28)}</text></g>)}
      <text x={8} y={552} fontSize={9} fill="#61708a">{nodes.length} nodes · {links.length} relationships · tick {tick}</text>
    </svg>
  );
}

export function GraphPage() {
  const { sc, scenario, refreshStatus } = useApp();
  const stats = useAsync(() => api.graphStats(), []);
  const def = scenario.object_id && scenario.compartment_id ? `${sc?.id}/${scenario.compartment_id}/${scenario.object_id}` : scenario.material_id || sc?.id || "MAT-PMMA";
  const [center, setCenter] = useState<string>(def);
  const [depth, setDepth] = useState(3);
  const [domain, setDomain] = useState<string>("");
  const [picked, setPicked] = useState<any>(null);
  const [neo, setNeo] = useState<any>(null);
  useEffect(() => setCenter(def), [def]);
  const sub = useAsync(() => api.subgraph(center, depth, domain || undefined), [center, depth, domain]);
  const trace = useAsync(() => api.trace(center), [center]);
  const options: [string, string][] = [];
  sc?.compartments.forEach((c: any) => { options.push([`${sc.id}/${c.id}`, `Compartment · ${c.name}`]); c.objects.forEach((o: any) => options.push([`${sc.id}/${c.id}/${o.id}`, `Object · ${o.name}`])); });
  return (
    <Page title="Dual knowledge graphs" intro="The spacecraft graph (spacecraft → compartments → objects → components → materials) and the science graph (findings → investigations, sources, conditions, audit items, models) share material nodes. Traversal across that bridge is what connects an object on board to NASA evidence."
      simple="A map of connections: from an object on the spacecraft, to what it's made of, to the NASA experiments about that material."
      actions={<div className="col small" style={{ alignItems: "flex-end" }}>
        <span className="pill">{stats.data?.neo4j.mode || "…"}</span>
        <button className="btn sm" onClick={async () => { setNeo(await api.neo4jSync()); refreshStatus(); }}>Sync to Neo4j</button>
        {neo && <span className={neo.connected ? "pill ok" : "pill warn"}>{neo.connected ? `Synced ${neo.nodes_synced} nodes` : `Not connected: ${neo.error}`}</span>}</div>}>
      <div className="card tight row">
        <label className="row small muted">Centre<select value={center} onChange={(e) => setCenter(e.target.value)} style={{ maxWidth: 360 }}>
          <option value={sc?.id}>Spacecraft · {sc?.name}</option>{options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          {scenario.material_id && <option value={scenario.material_id}>Material · {scenario.material_id}</option>}
          {["MAT-PMMA", "MAT-SIBAL", "MAT-NOMEX", "MAT-METHANOL", "INV:Saffire-II", "INV:FLEX"].map((m) => <option key={m} value={m}>{m}</option>)}</select></label>
        <label className="row small muted">Depth<select value={depth} onChange={(e) => setDepth(+e.target.value)}>{[1, 2, 3, 4].map((d) => <option key={d}>{d}</option>)}</select></label>
        <label className="row small muted">Domain<select value={domain} onChange={(e) => setDomain(e.target.value)}><option value="">Both graphs</option><option value="spacecraft">Spacecraft only</option><option value="science">Science only</option></select></label>
        <span className="grow" />{stats.data && <span className="small muted">{stats.data.nodes} nodes · {stats.data.edges} relationships in total</span>}
      </div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) 320px" }}>
        <div>{sub.loading ? <Loading /> : sub.data?.nodes.length ? <ForceGraph data={sub.data} picked={picked?.id} onPick={setPicked} /> : <Empty>Nothing to show for this centre.</Empty>}
          <div className="row small" style={{ marginTop: 6 }}>{Object.entries(COL).map(([k, v]) => <span key={k} className="row"><span className="dot" style={{ background: v }} />{k}</span>)}</div></div>
        <div className="card">
          <h3>Selected node</h3>{picked ? <><b>{picked.name}</b><div className="small muted">{picked.label} · {picked.domain} · hop {picked.hop}</div><div className="mono faint">{picked.id}</div>
            <button className="btn sm" style={{ marginTop: 6 }} onClick={() => setCenter(picked.id)}>Re-centre here</button></> : <div className="small faint">Click a node.</div>}
          <h3 style={{ marginTop: 14 }}>Multi-hop traces ({trace.data?.length ?? 0})</h3>
          <div style={{ maxHeight: 420, overflowY: "auto" }}>{trace.data?.slice(0, 30).map((t: any, i: number) => (
            <div key={i} className="small" style={{ borderBottom: "1px dashed var(--line)", padding: "5px 0" }}>
              {t.path.map((p: any, j: number) => <span key={j}><span style={{ color: COL[p.label] }}>{p.label}</span> {String(p.name).slice(0, 34)}{j < t.path.length - 1 ? " → " : ""}</span>)}</div>))}
            {trace.data && !trace.data.length && <div className="small faint">No path to NASA findings: the materials here are research gaps.</div>}</div>
        </div>
      </div>
    </Page>
  );
}
