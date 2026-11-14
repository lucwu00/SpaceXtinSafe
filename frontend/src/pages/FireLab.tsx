import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import { Page, useAsync, Loading, Empty, EvidenceCard, fmt, Tier, Err } from "../ui";
import { PredictionPanel } from "./Workspace";

const EVS: Record<string, string> = { "Verified NASA combustion evidence": "ok", "Related but indirect evidence": "acc", "Supplementary evidence (historical incident context)": "model", "User-defined material, no evidence found": "warn", "Catalogue entry, no evidence in library": "" };

function ModelChart({ m, d0, est }: { m: any; d0?: number; est?: any }) {
  const W = 540, H = 270, P = 40;
  const xs = m.observed.map((o: any) => o.o2_pct), ys = m.observed.map((o: any) => o.k);
  const x0 = Math.min(...xs) - 2, x1 = Math.max(...xs) + 2, y1 = Math.max(...ys, est?.estimate || 0) * 1.18;
  const X = (v: number) => P + ((v - x0) / (x1 - x0)) * (W - P - 12), Y = (v: number) => H - P - (v / y1) * (H - P - 30);
  const c = m.coefficients; const dd = m.uses_d0 ? d0 ?? (m.d0_mm_range[0] + m.d0_mm_range[1]) / 2 : 0;
  const line = (o: number) => c.intercept + c.per_O2_pct * o + (c.per_D0_mm || 0) * dd;
  const [lo, hi] = m.o2_pct_range, u = m.uncertainty_90_mm2_s || 0;
  const band = `M${X(lo)},${Y(line(lo) + u)} L${X(hi)},${Y(line(hi) + u)} L${X(hi)},${Y(Math.max(0, line(hi) - u))} L${X(lo)},${Y(Math.max(0, line(lo) - u))} Z`;
  const ticks = [0, y1 / 2, y1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%" }} role="img" aria-label={`${m.model_id}: observed tests, fitted line and 90% empirical band`}>
      {ticks.map((v) => <g key={v}><line x1={P} x2={W - 12} y1={Y(v)} y2={Y(v)} stroke="var(--line)" strokeDasharray="2 3" /><text x={P - 5} y={Y(v) + 3} fontSize={10} fill="var(--muted)" textAnchor="end">{v.toFixed(2)}</text></g>)}
      {[x0, (x0 + x1) / 2, x1].map((v) => <text key={v} x={X(v)} y={H - P + 15} fontSize={10} fill="var(--muted)" textAnchor="middle">{v.toFixed(0)}</text>)}
      <text x={W / 2} y={H - 6} fontSize={10} fill="var(--muted)" textAnchor="middle">Oxygen, % by volume</text><text x={P} y={11} fontSize={10} fill="var(--muted)">K, mm²/s</text>
      <path d={band} fill={m.status === "Model-supported" ? "var(--ok)" : "var(--model)"} opacity={0.12} />
      <line x1={X(lo)} y1={Y(line(lo))} x2={X(hi)} y2={Y(line(hi))} stroke={m.status === "Model-supported" ? "var(--ok)" : "var(--model)"} strokeWidth={2} strokeDasharray={m.status === "Model-supported" ? "" : "5 4"} />
      {m.observed.map((o: any, i: number) => <circle key={i} cx={X(o.o2_pct)} cy={Y(o.k)} r={3.2} fill="var(--fire)" opacity={0.85}><title>Observed · {o.record}: K={o.k} mm²/s, D0={o.d0_mm} mm, session {o.session}</title></circle>)}
      {est?.estimate != null && est.model?.model_id === m.model_id && <g><rect x={X(est.o2) - 5} y={Y(est.estimate) - 5} width={10} height={10} fill="none" stroke="var(--ink)" strokeWidth={2} transform={`rotate(45 ${X(est.o2)} ${Y(est.estimate)})`} /><text x={X(est.o2) + 9} y={Y(est.estimate) - 8} fontSize={10} fill="var(--ink)">your estimate</text></g>}
      <g fontSize={10} fill="var(--muted)"><circle cx={W - 190} cy={8} r={3} fill="var(--fire)" /><text x={W - 183} y={11}>observed test</text><rect x={W - 110} y={3} width={12} height={8} fill="var(--ok)" opacity={0.25} /><text x={W - 94} y={11}>90% band</text></g>
      {m.uses_d0 && <text x={W - 12} y={24} fontSize={10} fill="var(--muted)" textAnchor="end">line at D0 = {dd.toFixed(2)} mm</text>}
    </svg>
  );
}

function MaterialMeta({ m, status }: { m: any; status: string }) {
  return (
    <div className="card"><div className="row between"><h3>{m.name}</h3><span className={`pill ${EVS[status] || ""}`}>{status}</span></div>
      <table className="small"><tbody>
        {[["Scientific name", m.scientific_name], ["Category", m.category], ["Composition", m.composition || "Unknown"], ["Grade", m.grade || "Unknown"], ["Forms", (m.forms || []).join(", ")],
          ["Phenomenon", m.phenomenon], ["Typical applications", (m.applications || []).join(", ")], ["Provenance", m.provenance]].map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td>{v || "—"}</td></tr>)}
      </tbody></table>
      {m.notes && <p className="small faint">{m.notes}</p>}
    </div>
  );
}

const RELS = ["adjacent", "layered", "composite", "same object", "same compartment"];
const PRESETS = [
  { label: "Saffire-II combined PMMA + Nomex sample", ids: ["MAT-PMMA", "MAT-NOMEX"], rel: "adjacent", o2: 22.1, p: 101.3, g: "microgravity", flow: 20, ctx: "hot-wire igniter at the PMMA end" },
  { label: "Saffire VI cotton-fiberglass and PMMA", ids: ["MAT-SIBAL", "MAT-PMMA"], rel: "same compartment", o2: 21, p: 101.3, g: "microgravity", flow: 20, ctx: "separate samples in one flow duct" },
  { label: "Apollo 1 cabin: nylon + polyurethane in oxygen", ids: ["MAT-NYLON", "MAT-PU"], rel: "same compartment", o2: 100, p: 113.8, g: "1-g", flow: 0, ctx: "electrical arc (historical)" },
];

function Interactions() {
  const { materials, sc, scenario, setCtx } = useApp();
  const [ids, setIds] = useState<string[]>(["MAT-PMMA", "MAT-NOMEX"]);
  const [rel, setRel] = useState("adjacent");
  const fromSc = () => ({ o2_pct: sc?.atmosphere?.o2_pct ?? 21, pressure_kpa: sc?.atmosphere?.pressure_kpa ?? 101.3, gravity: sc?.atmosphere?.gravity ?? "microgravity", flow_cm_s: sc?.atmosphere?.ventilation_cm_s ?? 15 });
  const [cond, setCond] = useState({ ...fromSc(), sep_mm: "", thickness: "", ctx: "" });
  useEffect(() => { setCond((c) => ({ ...c, ...fromSc() })); }, [sc?.id]); // default to the selected spacecraft's environment
  const r = useAsync(() => (ids.length >= 2 ? api.interactions(ids) : Promise.resolve(null)), [ids.join()]);
  const rk = useAsync(() => api.rank({ ...scenario, material_id: ids[0], o2_pct: cond.o2_pct, pressure_kpa: cond.pressure_kpa, gravity: cond.gravity, flow_cm_s: cond.flow_cm_s }), [ids[0], JSON.stringify(cond)]);
  const matrix = useAsync(() => api.gapsDim("material", sc?.id), [sc?.id]);
  useEffect(() => { setCtx({ interaction_ids: ids }); }, [ids.join()]);
  const appl = (id: string) => rk.data?.find((e: any) => e.id === id)?.applicability;
  const docs = r.data?.documented_interactions || [], co = r.data?.co_reported || [];
  const cls = docs.length ? "Directly observed interaction" : co.length ? "Related but indirect evidence" : "Missing experimental evidence";
  return (
    <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1.3fr)" }}>
      <div className="card">
        <h2>Define the material combination</h2>
        <div className="row" style={{ marginBottom: 8 }}><button className="btn sm pri" onClick={() => setCond({ ...cond, ...fromSc(), ctx: "" })}>Use {sc?.name || "spacecraft"} environment</button><span className="small muted">Presets:</span>{PRESETS.map((p) => <button key={p.label} className="btn sm" onClick={() => { setIds(p.ids); setRel(p.rel); setCond({ ...cond, o2_pct: p.o2, pressure_kpa: p.p, gravity: p.g, flow_cm_s: p.flow, ctx: p.ctx }); }}>{p.label}</button>)}</div>
        {[0, 1, 2, 3].map((i) => <label key={i} className="label">Material {i + 1}{i < 2 ? "" : " (optional)"}
          <select value={ids[i] || ""} onChange={(e) => { const n = [...ids]; n[i] = e.target.value; setIds(n.filter(Boolean)); }}><option value="">—</option>{materials.map((m) => <option key={m.id} value={m.id}>{m.name}{m.user_defined ? " (user-defined)" : ""}</option>)}</select></label>)}
        <div className="grid g2" style={{ marginTop: 6 }}>
          <label className="label">Relationship<select value={rel} onChange={(e) => setRel(e.target.value)}>{RELS.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label className="label">Separation (mm)<input type="number" value={cond.sep_mm} onChange={(e) => setCond({ ...cond, sep_mm: e.target.value })} placeholder="unknown" /></label>
          <label className="label">Thickness (mm)<input type="number" value={cond.thickness} onChange={(e) => setCond({ ...cond, thickness: e.target.value })} placeholder="unknown" /></label>
          <label className="label">Oxygen %<input type="number" value={cond.o2_pct} onChange={(e) => setCond({ ...cond, o2_pct: +e.target.value })} /></label>
          <label className="label">Pressure kPa<input type="number" value={cond.pressure_kpa} onChange={(e) => setCond({ ...cond, pressure_kpa: +e.target.value })} /></label>
          <label className="label">Gravity<select value={cond.gravity} onChange={(e) => setCond({ ...cond, gravity: e.target.value })}>{["microgravity", "partial gravity", "1-g"].map((g) => <option key={g}>{g}</option>)}</select></label>
          <label className="label">Airflow cm/s<input type="number" value={cond.flow_cm_s} onChange={(e) => setCond({ ...cond, flow_cm_s: +e.target.value })} /></label>
          <label className="label">Ignition context<input value={cond.ctx} onChange={(e) => setCond({ ...cond, ctx: e.target.value })} placeholder="e.g. hot wire" /></label>
        </div>
        <p className="small faint">Unknown values stay unknown. SpaceXtinsafe does not infer how two materials burn together from their individual behaviour.</p>
      </div>
      <div>
        <div className="card">{r.loading ? <Loading /> : !r.data ? <Empty>Choose at least two materials.</Empty> : <>
          <div className="row between"><h2>{r.data.materials.join(" + ")}</h2><span className={`pill ${docs.length ? "ok" : co.length ? "acc" : "warn"}`}>{cls}</span></div>
          <div className="small muted">Relationship: {rel} · {cond.o2_pct}% O₂ · {cond.pressure_kpa} kPa · {cond.gravity} · {cond.flow_cm_s} cm/s{cond.ctx ? ` · ${cond.ctx}` : ""}</div>
          {docs.map((e: any) => <EvidenceCard key={e.id} e={{ ...e, applicability: appl(e.id) }} extra={<div className="small" style={{ marginTop: 4 }}>Observed relationship in the source: same composite sample. Your relationship: {rel}.</div>} />)}
          {co.map((e: any) => <EvidenceCard key={e.id} e={{ ...e, applicability: appl(e.id) }} extra={<div className="small faint">Both materials appear in this finding, but it does not document an interaction between them.</div>} />)}
          {!docs.length && <div className="banner">No NASA finding in this library documents these materials burning together. That is a gap in this library, not evidence that they do or do not interact. To close it: a combined-sample test under {cond.gravity} at {cond.o2_pct}% O₂ and {cond.flow_cm_s} cm/s flow.</div>}
          <p className="small faint">{r.data.note}</p></>}</div>
        <div className="card"><h3>Pairs on {sc?.name}</h3>{matrix.loading ? <Loading /> : <div className="scroll" style={{ maxHeight: 260 }}><table><tbody>
          {(matrix.data?.cells || []).filter((c: any) => c.status !== "No documented interaction (research gap)").slice(0, 30).map((c: any, i: number) =>
            <tr key={i}><td className="small">{c.a} + {c.b}</td><td><span className={`pill ${c.status.startsWith("Documented") ? "ok" : "acc"}`}>{c.status}</span></td><td className="mono faint">{c.ids.join(", ")}</td></tr>)}</tbody></table>
          <p className="small faint">{matrix.data?.pairs_checked} material pairs checked; pairs not listed have no NASA finding involving both.</p></div>}</div>
      </div>
    </div>
  );
}

function Future() {
  const reqs = [["Computational fluid dynamics", "Flow fields around objects and through ventilation, resolved in 3-D"], ["Heat transfer", "Conduction, convection and radiation between flame, gas and surfaces"],
    ["Chemical kinetics", "Gas-phase reaction mechanisms for each fuel and its pyrolysis products"], ["Material decomposition", "Pyrolysis and charring models with measured parameters per material"],
    ["Smoke transport", "Particle formation, ageing and transport to detectors"], ["Radiation", "Soot and gas radiation, which dominates near-limit microgravity flames"],
    ["Ventilation modelling", "Cabin fans, ducts and their switching"], ["Gravity-dependent combustion", "Buoyancy from 0 g to 1 g, including partial gravity"],
    ["Geometry and mesh generation", "A detailed, validated cabin geometry"], ["Experimental validation", "Comparison against Saffire-scale and ground tests before any use"]];
  return (
    <div className="card"><h2>Level 3: whole-spacecraft fire simulation (future research capability)</h2>
      <div className="banner info">Not implemented. SpaceXtinsafe does not simulate fire growth in a spacecraft and shows no flame animations as results. A credible simulation would need all of the following.</div>
      <div className="grid g2">{reqs.map(([k, v]) => <div key={k} className="kpi"><b style={{ fontSize: 15 }}>{k}</b><span>{v}</span></div>)}</div>
      <p className="small muted" style={{ marginTop: 10 }}>What exists today in SpaceXtinsafe: verified NASA findings, an applicability assessment, and burning-rate estimates for isolated droplets only where the FLEX data supports them.</p></div>
  );
}

export function FireLab() {
  const { scenario, patch, materials, sc, setPrediction, prediction, ctx } = useApp();
  const [tab, setTab] = useState((ctx as any).fireTab || "l1");
  useEffect(() => { if ((ctx as any).fireTab) setTab((ctx as any).fireTab); }, [(ctx as any).fireTab]);
  const [src, setSrc] = useState<"material" | "component" | "question">("material");
  const [q, setQ] = useState("");
  const [qres, setQres] = useState<any>(null);
  const [lit, setLit] = useState<any>(null);
  const mid = scenario.material_id || "MAT-PMMA";
  const prof = useAsync(() => api.material(mid, { o2_pct: scenario.o2_pct, pressure_kpa: scenario.pressure_kpa, gravity: scenario.gravity, flow_cm_s: scenario.flow_cm_s, form: scenario.form }), [mid, scenario.o2_pct, scenario.pressure_kpa, scenario.gravity, materials.length]);
  const models = useAsync(() => api.models(), []);
  const comps: any[] = [];
  sc?.compartments.forEach((c: any) => c.objects.forEach((o: any) => o.components.forEach((k: any) => comps.push({ c, o, k }))));
  const est = prediction ? { ...prediction, o2: scenario.o2_pct } : null;
  return (
    <Page title="Virtual Fire Lab" intro="Investigate one material, component or question against NASA evidence (Level 1); combinations of materials under conditions you define (Level 2); and see what a whole-spacecraft simulation would require (Level 3). Droplet models show observed tests, the fitted line and the 90% empirical band."
      simple="Explore what NASA knows about a material, check whether two materials have been seen burning together, and see real experiment data next to model estimates.">
      <div className="tabs">{[["l1", "Level 1 · Material intelligence"], ["l2", "Level 2 · Material interactions"], ["droplet", "Droplet models (FLEX data)"], ["l3", "Level 3 · Future simulation"]].map(([k, l]) =>
        <button key={k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "l1" && <>
        <div className="card tight row">
          {(["material", "component", "question"] as const).map((s) => <button key={s} className={`btn sm ${src === s ? "pri" : ""}`} onClick={() => setSrc(s)}>{s === "material" ? "A material" : s === "component" ? `A component on ${sc?.name}` : "A question"}</button>)}
          {src === "material" && <select value={mid} onChange={(e) => patch({ material_id: e.target.value })} aria-label="Material">{materials.map((m) => <option key={m.id} value={m.id}>{m.name}{m.user_defined ? " (user-defined)" : ""} · {m.evidence_count}</option>)}</select>}
          {src === "component" && <select onChange={(e) => { const x = comps[+e.target.value]; if (x) patch({ compartment_id: x.c.id, object_id: x.o.id, component_id: x.k.id, material_id: x.k.material_id, form: x.k.form }); }} aria-label="Component">
            <option>Select…</option>{comps.map((x, i) => <option key={i} value={i}>{x.c.name} · {x.o.name} · {x.k.name}</option>)}</select>}
          {src === "question" && <form className="row" onSubmit={async (e) => { e.preventDefault(); setQres(await api.search(q, "auto", sc?.id)); }}><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Does thin PMMA blow off at high flow?" style={{ minWidth: 300 }} /><button className="btn pri">Search</button></form>}
          <span className="small muted">Conditions: {scenario.o2_pct}% O₂ · {scenario.pressure_kpa} kPa · {scenario.gravity}</span>
        </div>
        {src === "question" && qres && <div className="card">{qres.note && <div className="banner info">{qres.note}</div>}{qres.results.map((e: any) => <EvidenceCard key={e.id} e={e} />)}</div>}
        {src !== "question" && (prof.loading ? <Loading /> : prof.error ? <Err e={prof.error} /> : prof.data && <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.7fr) minmax(0,1fr)" }}>
          <div>{prof.data.evidence.length ? prof.data.evidence.map((e: any) => <EvidenceCard key={e.id} e={e} />) :
            <div className="banner">No NASA finding in this library involves {prof.data.material.name}. This is a research gap in SpaceXtinsafe's library; it may or may not be a gap in the wider literature, and it is not evidence that the material is non-flammable.</div>}
            <div className="card"><div className="row between"><h3>Discover more NASA literature (unverified)</h3><button className="btn sm" onClick={async () => setLit(await api.literature(prof.data.material.name).catch((e) => ({ available: false, label: e.message, results: [] })))}>Search NTRS</button></div>
              {lit && <><div className="small faint">{lit.label || lit.reason}</div>{lit.results?.length ? <ul className="small">{lit.results.map((x: any) => <li key={x.id}><a href={x.url} target="_blank" rel="noreferrer">{x.title}</a> <span className="faint">({x.year || "n.d."}, NTRS {x.id})</span></li>)}</ul> : <p className="small muted">No results returned.</p>}</>}</div></div>
          <div><MaterialMeta m={prof.data.material} status={typeof prof.data.status === "string" ? prof.data.status : prof.data.status?.status} />
            {prof.data.status?.note && <div className="small faint" style={{ margin: "-8px 0 12px" }}>{prof.data.status.note}</div>}
            <div className="card"><h3>Research gaps for this material</h3>{prof.data.gaps.map((g: string) => <p key={g} className="small">• {g}</p>)}</div>
            <div className="card"><h3>Where it is used</h3>{prof.data.used_in.length ? prof.data.used_in.map((u: any, i: number) => <p key={i} className="small">{u.spacecraft} · {u.compartment} · {u.object} · {u.component}</p>) : <span className="small faint">Not used in any configuration.</span>}</div>
            {prof.data.models.length > 0 && <div className="card"><h3>Applicable models</h3>{prof.data.models.map((m: any) => <p key={m.model_id} className="small">{m.model_id}: {m.status}</p>)}<button className="btn sm" onClick={() => setTab("droplet")}>Open droplet models</button></div>}</div>
        </div>)}
      </>}
      {tab === "l2" && <Interactions />}
      {tab === "l3" && <Future />}
      {tab === "droplet" && <>{models.loading ? <Loading /> : <div className="grid g2">{models.data!.map((m: any) => (
        <div key={m.model_id} className="card"><div className="row between"><h3>{m.model_id}</h3><span className={`pill ${m.status === "Model-supported" ? "ok" : "model"}`}>{m.status}</span></div>
          <div className="small muted">{m.fuel} · {m.pressure_kpa_range[0]}–{m.pressure_kpa_range[1]} kPa · N₂ diluent · n={m.n_observations}, {m.n_sessions} sessions · {m.n_parameters} parameters incl. intercept</div>
          <ModelChart m={m} d0={scenario.d0_mm} est={est} />
          <div className="small">Leave-one-session-out MAE {fmt(m.validation.mae)} vs mean baseline {fmt(m.validation.baseline_mae)} · skill {fmt(m.validation.predictive_skill, 2)} · R² {fmt(m.validation.oof_r2, 2)} · random forest MAE {fmt(m.benchmark.random_forest.mae)}</div>
          {m.failed_criteria.length > 0 && <div className="small" style={{ color: "var(--model)" }}>Exploratory because it failed: {m.failed_criteria.map((f: string) => f === "min_skill" ? `skill ≥ 0.30 (actual ${fmt(m.validation.predictive_skill, 2)})` : f === "min_tests" ? `≥ 20 tests (actual ${m.n_observations})` : f === "min_sessions" ? `≥ 8 sessions (actual ${m.n_sessions})` : f).join("; ")}</div>}</div>))}</div>}
        <PredictionPanel />{prediction && <button className="btn sm" onClick={() => setPrediction(null)}>Clear estimate marker</button>}</>}
      <span hidden><Tier t="Directly applicable" /></span>
    </Page>
  );
}