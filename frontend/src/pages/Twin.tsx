import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import { Page, useAsync, Loading, Empty } from "../ui";

/* Evidence-status palette: deliberately NOT red/amber/green, so nothing reads as a certified risk class. */
export const EV_COL: Record<string, string> = {
  "Verified NASA combustion evidence": "#38bdf8", "Related but indirect evidence": "#a78bfa", "Supplementary evidence (historical incident context)": "#94a3b8",
  "Insufficient evidence (context statements only)": "#64748b", "User-defined material, no evidence found": "#f0abfc", "Catalogue entry, no evidence in library": "#334155",
};
const CAT_COL = ["#38bdf8", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#60a5fa", "#fb923c", "#c084fc", "#2dd4bf", "#e879f9", "#facc15", "#93c5fd", "#fca5a5", "#86efac"];
const OVERLAYS: [string, string][] = [["evidence", "Evidence coverage"], ["materials", "Material distribution"], ["gaps", "Research gaps"], ["conflicts", "Conflicting evidence"],
  ["interactions", "Documented interactions"], ["sensors", "Sensor locations"], ["incident", "Simulated incident"]];

function hull(shape: string, W: number, H: number) {
  // body outlines for the illustrative cutaways
  if (shape === "capsule") return `M ${W * 0.08} ${H * 0.82} L ${W * 0.3} ${H * 0.16} Q ${W * 0.5} ${H * 0.06} ${W * 0.7} ${H * 0.16} L ${W * 0.92} ${H * 0.82} Q ${W * 0.5} ${H * 0.95} ${W * 0.08} ${H * 0.82} Z`;
  if (shape === "habitat") return `M ${W * 0.04} ${H * 0.86} L ${W * 0.04} ${H * 0.5} Q ${W * 0.06} ${H * 0.08} ${W * 0.5} ${H * 0.08} Q ${W * 0.94} ${H * 0.08} ${W * 0.96} ${H * 0.5} L ${W * 0.96} ${H * 0.86} Z`;
  return `M ${W * 0.07} ${H * 0.24} L ${W * 0.93} ${H * 0.24} A ${W * 0.035} ${H * 0.3} 0 0 1 ${W * 0.93} ${H * 0.84} L ${W * 0.07} ${H * 0.84} A ${W * 0.035} ${H * 0.3} 0 0 1 ${W * 0.07} ${H * 0.24} Z`;
}

export function Cutaway({ sc, rows, overlay, selected, onSelect, onObject, incidentComp, interactions }: any) {
  const W = 1000, H = 440;
  const shape = sc.shape || (sc.template_id === "TPL-CAPSULE" ? "capsule" : sc.template_id === "TPL-LUNAR" ? "habitat" : sc.template_id === "TPL-ORBITAL" ? "module" : "module");
  const comps = sc.compartments;
  const total = comps.reduce((n: number, c: any) => n + (c.w ?? 30), 0) || 1;
  const cats = useMemo(() => [...new Set(rows.map((r: any) => r.material))] as string[], [rows]);
  let x = W * 0.08;
  const slices = comps.map((c: any) => { const w = ((c.w ?? 30) / total) * W * 0.84; const s = { c, x, w }; x += w; return s; });
  const top = shape === "habitat" ? H * 0.2 : shape === "capsule" ? H * 0.3 : H * 0.26, bot = shape === "habitat" ? H * 0.86 : H * 0.82;
  const fillFor = (cid: string) => {
    const r = rows.filter((x: any) => x.compartment_id === cid);
    if (!r.length) return "#16223a";
    if (overlay === "gaps") { const n = r.filter((x: any) => !x.investigations.length).length; return `rgba(240,171,252,${0.12 + 0.6 * n / r.length})`; }
    if (overlay === "conflicts") return r.some((x: any) => x.conflict) ? "rgba(167,139,250,.45)" : "#16223a";
    if (overlay === "incident") return incidentComp === cid ? "rgba(255,138,61,.35)" : "#16223a";
    const v = r.filter((x: any) => x.material_status?.startsWith("Verified")).length / r.length; return `rgba(56,189,248,${0.1 + 0.55 * v})`;
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", background: "radial-gradient(ellipse at 50% 40%, #12203a, #070d19)", borderRadius: 12 }} role="img" aria-label={`${sc.name} illustrative cutaway`}>
      <defs>
        <clipPath id="hullclip"><path d={hull(shape, W, H)} /></clipPath>
        <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#f0abfc" strokeWidth="2" opacity=".35" /></pattern>
        <linearGradient id="metal" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#334766" /><stop offset=".5" stopColor="#1b2840" /><stop offset="1" stopColor="#0f1829" /></linearGradient>
      </defs>
      {Array.from({ length: 60 }, (_, i) => <circle key={i} cx={(i * 137) % W} cy={(i * 71) % H} r={i % 7 === 0 ? 1.4 : 0.7} fill="#9fb4cc" opacity={0.35} />)}
      {shape === "module" && <>{[0.18, 0.62].map((f) => <g key={f}><rect x={W * f} y={H * 0.03} width={W * 0.2} height={H * 0.1} fill="#13305a" stroke="#4ea1ff" strokeWidth={1} />
        {Array.from({ length: 7 }, (_, i) => <line key={i} x1={W * f + (i + 1) * W * 0.025} y1={H * 0.03} x2={W * f + (i + 1) * W * 0.025} y2={H * 0.13} stroke="#4ea1ff" strokeOpacity={0.4} />)}
        <line x1={W * f} y1={H * 0.08} x2={W * (f + 0.2)} y2={H * 0.08} stroke="#4ea1ff" strokeOpacity={0.4} />
        <line x1={W * (f + 0.1)} y1={H * 0.13} x2={W * (f + 0.1)} y2={H * 0.24} stroke="#4ea1ff" /></g>)}
        <text x={W * 0.5} y={H * 0.09} fill="#61708a" fontSize={10} textAnchor="middle">solar arrays (illustrative)</text></>}
      {shape === "capsule" && <path d={`M ${W * 0.1} ${H * 0.86} Q ${W * 0.5} ${H * 0.99} ${W * 0.9} ${H * 0.86}`} stroke="#ff8a3d" strokeWidth={6} fill="none" opacity={0.7} />}
      {shape === "habitat" && <>{[0.12, 0.88].map((f) => <line key={f} x1={W * f} y1={H * 0.86} x2={W * (f + (f < 0.5 ? -0.06 : 0.06))} y2={H * 0.98} stroke="#6b7f9e" strokeWidth={4} />)}
        <rect x={0} y={H * 0.97} width={W} height={H * 0.03} fill="#2a3446" /></>}
      <path d={hull(shape, W, H)} fill="url(#metal)" stroke="#5b7bab" strokeWidth={2} />
      <g clipPath="url(#hullclip)">
        {slices.map(({ c, x, w }: any) => {
          const on = selected === c.id;
          return <g key={c.id} onClick={() => onSelect(c.id)} style={{ cursor: "pointer" }} tabIndex={0} role="button" aria-label={`Compartment ${c.name}`}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(c.id)}>
            <rect x={x + 2} y={top} width={w - 4} height={bot - top} fill={fillFor(c.id)} stroke={on ? "#e0f2fe" : "#2f4469"} strokeWidth={on ? 3 : 1} />
            {overlay === "gaps" && rows.some((r: any) => r.compartment_id === c.id && !r.investigations.length) && <rect x={x + 2} y={top} width={w - 4} height={bot - top} fill="url(#hatch)" />}
            <text x={x + 10} y={top + 26} fill="#e6edf7" fontSize={15} fontWeight={600}>{c.name}</text>
            <text x={x + 10} y={top + 43} fill="#93a3bd" fontSize={11}>{c.type} · {c.volume_m3} m³</text>
            {c.objects.map((o: any, i: number) => {
              const cols = w > 230 ? 2 : 1, bw = (w - 24 - (cols - 1) * 8) / cols, ox = x + 12 + (i % cols) * (bw + 8), oy = top + 56 + Math.floor(i / cols) * 34;
              const orows = rows.filter((r: any) => r.object_id === o.id && r.compartment_id === c.id);
              return <g key={o.id} onClick={(e) => { e.stopPropagation(); onSelect(c.id); onObject(o.id); }}>
                <rect x={ox} y={oy} width={bw} height={28} rx={6} fill="#0b1424" stroke="#2f4469" />
                {(() => { const dots = overlay === "materials" || overlay === "evidence" ? orows.length : overlay === "interactions" ? 2 : 0; const maxc = Math.max(4, Math.floor((bw - 16 - dots * 9) / 6.6));
                  return <text x={ox + 8} y={oy + 18} fill="#e6edf7" fontSize={11.5}><title>{o.name}</title>{o.name.length > maxc ? o.name.slice(0, maxc - 1) + "…" : o.name}</text>; })()}
                {(overlay === "materials" || overlay === "evidence") && orows.map((r: any, j: number) =>
                  <circle key={j} cx={ox + bw - 8 - j * 9} cy={oy + 14} r={3.6} fill={overlay === "materials" ? CAT_COL[cats.indexOf(r.material) % CAT_COL.length] : EV_COL[r.material_status] || "#334155"} stroke="#0b1424"><title>{r.component}: {r.material} ({r.material_status})</title></circle>)}
                {overlay === "interactions" && orows.some((r: any) => interactions.includes(r.material_id)) && <text x={ox + bw - 16} y={oy + 19} fill="#a78bfa" fontSize={13}>⇄</text>}
              </g>;
            })}
            {overlay === "sensors" && (c.sensors || []).map((s: any, i: number) => <g key={s.id}><circle cx={x + w - 18} cy={top + 20 + i * 22} r={7} fill="#0b1424" stroke="#38bdf8" />
              <text x={x + w - 30} y={top + 24 + i * 22} fill="#7cc4ff" fontSize={10} textAnchor="end">{s.type}</text></g>)}
            {overlay === "incident" && incidentComp === c.id && <text x={x + w / 2} y={bot - 14} fill="#ff8a3d" fontSize={12} textAnchor="middle">SIMULATED observation</text>}
          </g>;
        })}
      </g>
      <text x={12} y={H - 10} fill="#61708a" fontSize={11}>Illustrative, knowledge-driven cutaway of a generic configuration. Not a real or certified vehicle design, and not a physical simulation.</text>
    </svg>
  );
}

export function Twin() {
  const { sc, go, patch, scenario, materials } = useApp();
  const scr = useAsync(() => (sc ? api.screen(sc.id) : Promise.resolve(null)), [sc?.id, JSON.stringify(sc?.compartments)]);
  const audit = useAsync(() => api.audit(), []);
  const inter = useAsync(() => api.gapsDim("material", sc?.id), [sc?.id]);
  const [comp, setComp] = useState<string | null>(scenario.compartment_id || null);
  const [obj, setObj] = useState<string | null>(scenario.object_id || null);
  useEffect(() => { if (scenario.compartment_id) setComp(scenario.compartment_id); if (scenario.object_id !== undefined) setObj(scenario.object_id || null); }, [scenario.compartment_id, scenario.object_id]);
  const [overlay, setOverlay] = useState("evidence");
  if (!sc || scr.loading) return <Loading label="Loading spacecraft" />;
  const conflictIds = new Set((audit.data?.items || []).filter((i: any) => i.classification === "Substantive discrepancy").flatMap((i: any) => i.affected || []));
  const rows = (scr.data?.rows || []).map((r: any) => ({ ...r, conflict: r.evidence_ids.some((e: string) => conflictIds.has(e)) }));
  const interMats = (inter.data?.cells || []).filter((c: any) => c.status === "Documented interaction").flatMap((c: any) => [c.a, c.b])
    .map((n: string) => materials.find((m) => m.name === n)?.id).filter(Boolean);
  const C = sc.compartments.find((c: any) => c.id === comp) || null;
  const O = C?.objects.find((o: any) => o.id === obj) || null;
  const crow = rows.filter((r: any) => r.compartment_id === comp);
  const invs = [...new Set(crow.flatMap((r: any) => r.investigations))];
  const gaps = crow.filter((r: any) => !r.investigations.length);
  return (
    <Page title="Spacecraft digital twin" intro="A knowledge-driven digital twin: an illustrative cutaway of the active configuration, linked to NASA evidence, the knowledge graphs and every analysis module. Choose an overlay, select a compartment, then an object. It is a prototype, not a validated physical simulation."
      simple="Click a section of the spacecraft, then something inside it, to see what it's made of and what NASA research knows about those materials.">
      <div className="card tight row" role="radiogroup" aria-label="Overlay">
        <span className="small muted">Overlay</span>
        {OVERLAYS.map(([k, l]) => <button key={k} role="radio" aria-checked={overlay === k} className={`btn sm ${overlay === k ? "pri" : ""}`} onClick={() => setOverlay(k)}>{l}</button>)}
      </div>
      <div className="card" style={{ padding: 8 }}>
        {sc.compartments.length === 0 ? <Empty>No compartments yet. Add them in the Design Studio; the cutaway adapts to whatever you build.</Empty> :
          <Cutaway sc={sc} rows={rows} overlay={overlay} selected={comp} onSelect={(id: string) => { setComp(id); setObj(null); patch({ compartment_id: id, object_id: undefined }); }}
            onObject={(id: string) => { setObj(id); patch({ object_id: id }); }} incidentComp={scenario.compartment_id} interactions={interMats} />}
        <div className="row small" style={{ padding: "6px 6px 2px" }}>
          {overlay === "evidence" && Object.entries(EV_COL).map(([k, v]) => <span key={k} className="row"><span className="dot" style={{ background: v }} />{k}</span>)}
          {overlay === "gaps" && <span>Hatched and tinted sections contain components with no NASA finding in this library (a library gap, not a confirmed literature gap).</span>}
          {overlay === "conflicts" && <span>Violet sections contain materials whose findings are affected by a substantive source discrepancy (see Evidence audit).</span>}
          {overlay === "interactions" && <span>⇄ marks objects containing a material with a documented interaction finding (Saffire-II PMMA-Nomex sample).</span>}
          {overlay === "sensors" && <span>Illustrative sensor placements defined in the configuration. Not real instrumentation.</span>}
          {overlay === "incident" && <span>Highlights the compartment selected for the simulated incident replay.</span>}
          {overlay === "materials" && <span>Each dot is a component, coloured by material. Hover a dot for details.</span>}
        </div>
      </div>
      {C && <div className="grid g2">
        <div className="card">
          <div className="row between"><h2>{C.name}</h2><span className="small muted">{sc.atmosphere.o2_pct}% O₂ · {sc.atmosphere.pressure_kpa} kPa · {sc.atmosphere.gravity} · ventilation {sc.atmosphere.ventilation_cm_s} cm/s</span></div>
          <div className="grid g3" style={{ margin: "8px 0" }}>
            <div className="kpi"><b>{crow.length}</b><span>components</span></div>
            <div className="kpi"><b>{invs.length}</b><span>NASA investigations linked</span></div>
            <div className="kpi"><b>{gaps.length}</b><span>components with no library evidence</span></div></div>
          <div className="small"><b>Investigations:</b> {invs.join(", ") || "none"}</div>
          <div className="small"><b>Gaps:</b> {gaps.map((g: any) => g.material).filter((v: any, i: number, a: any[]) => a.indexOf(v) === i).join(", ") || "none"}</div>
          <div className="small"><b>Models:</b> {crow.some((r: any) => r.material_id === "MAT-METHANOL" || r.material_id === "MAT-HEPTANE") ? "FLEX droplet burning-rate models apply to liquid fuels here" : "no validated model for these materials"}</div>
          <div className="col" style={{ marginTop: 10 }}>{C.objects.map((o: any) => <button key={o.id} className={`nav ${obj === o.id ? "on" : ""}`} onClick={() => { setObj(o.id); patch({ object_id: o.id }); }}>{o.name} <span className="faint small">({o.category} · {o.components.length} components)</span></button>)}</div>
          <div className="row" style={{ marginTop: 8 }}><button className="btn sm" onClick={() => { patch({ compartment_id: C.id }); go("incidents"); }}>Simulate incident here</button>
            <button className="btn sm" onClick={() => go("gaps")}>Research gaps</button><button className="btn sm" onClick={() => go("compare")}>Compare</button></div>
        </div>
        <div className="card">{!O ? <Empty>Select an object to inspect its components. An object is not assumed to behave like any one of its materials.</Empty> : <>
          <h2>{O.name}</h2><div className="small muted" style={{ marginBottom: 8 }}>Decomposed into {O.components.length} components. Each component is assessed separately.</div>
          {O.components.map((k: any) => { const r = rows.find((x: any) => x.component_id === k.id && x.object_id === O.id);
            return <div key={k.id} className="ev"><div className="row between"><b>{k.name}</b><span className="pill" style={{ color: EV_COL[r?.material_status] || "#93a3bd", borderColor: "#23314d" }}>{r?.material_status || "…"}</span></div>
              <div className="small muted">{r?.material} · {k.form}{k.thickness_mm ? ` · ${k.thickness_mm} mm` : ""}{k.mass_g ? ` · ${k.mass_g} g` : ""}{r?.user_defined ? " · user-defined" : ""}</div>
              <div className="small faint">Phenomenon: {r?.phenomenon}</div>
              <div className="small">{r?.investigations.length ? `Investigations: ${r.investigations.join(", ")}` : r?.related_findings?.length ? `Only related (indirect) findings: ${r.related_findings.join(", ")}` : "No investigation in the library covers this material."}</div>
              <div className="row" style={{ marginTop: 6 }}>
                <button className="btn sm pri" onClick={() => { patch({ compartment_id: C.id, object_id: O.id, component_id: k.id, material_id: k.material_id, form: k.form }); go("workspace"); }}>Analyse</button>
                <button className="btn sm" onClick={() => { patch({ compartment_id: C.id, object_id: O.id, component_id: k.id, material_id: k.material_id }); go("graph"); }}>Trace in graph</button>
                <button className="btn sm" onClick={() => { patch({ material_id: k.material_id, form: k.form }); go("firelab"); }}>Fire Lab</button>
                <button className="btn sm" onClick={() => { patch({ material_id: k.material_id }); go("library"); }}>Evidence</button></div></div>; })}</>}
        </div></div>}
      {!C && <Empty>Select a compartment in the cutaway.</Empty>}
    </Page>
  );
}
