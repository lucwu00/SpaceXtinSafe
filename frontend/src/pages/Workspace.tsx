import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp, matName } from "../state";
import { NasaCoverage } from "./Nasa";
import { Page, useAsync, Loading, Empty, EvidenceCard, Outcome, fmt, Err } from "../ui";

const FORMS = ["", "thin sheet", "thin fabric sheet", "fabric", "foam", "bulk", "liquid droplet", "wire", "rod", "sphere"];

export function Conditions() {
  const { scenario: s, patch, materials } = useApp();
  return (
    <div className="grid g4">
      <label className="label">Material<select value={s.material_id || ""} onChange={(e) => patch({ material_id: e.target.value || undefined })}><option value="">(any)</option>
        {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      <label className="label">Form<select value={s.form || ""} onChange={(e) => patch({ form: e.target.value || undefined })}>{FORMS.map((f) => <option key={f} value={f}>{f || "(unspecified)"}</option>)}</select></label>
      <label className="label">Oxygen %<input type="number" step="0.5" value={s.o2_pct ?? ""} onChange={(e) => patch({ o2_pct: e.target.value === "" ? undefined : +e.target.value })} /></label>
      <label className="label">Pressure kPa<input type="number" step="0.5" value={s.pressure_kpa ?? ""} onChange={(e) => patch({ pressure_kpa: e.target.value === "" ? undefined : +e.target.value })} /></label>
      <label className="label">Gravity<select value={s.gravity || ""} onChange={(e) => patch({ gravity: e.target.value })}>{["microgravity", "partial gravity", "1-g"].map((g) => <option key={g}>{g}</option>)}</select></label>
      <label className="label">Flow cm/s<input type="number" value={s.flow_cm_s ?? ""} onChange={(e) => patch({ flow_cm_s: e.target.value === "" ? undefined : +e.target.value })} /></label>
      <label className="label">Diluent<select value={s.diluent || "nitrogen"} onChange={(e) => patch({ diluent: e.target.value })}>{["nitrogen", "carbon dioxide", "helium"].map((g) => <option key={g}>{g}</option>)}</select></label>
      <label className="label">Droplet diameter mm (liquids)<input type="number" step="0.1" value={s.d0_mm ?? ""} onChange={(e) => patch({ d0_mm: e.target.value === "" ? undefined : +e.target.value })} /></label>
    </div>
  );
}

export function PredictionPanel() {
  const { scenario: s, setPrediction, prediction } = useApp();
  const fuel = s.material_id === "MAT-METHANOL" ? "methanol" : s.material_id === "MAT-HEPTANE" ? "n-heptane" : s.material_id ? "other" : undefined;
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    setPrediction(await api.predict({ material_form: s.form, fuel, o2_pct: s.o2_pct, pressure_kpa: s.pressure_kpa, d0_mm: s.d0_mm, diluent: s.diluent, gravity: s.gravity }));
    setBusy(false);
  };
  return (
    <div className="card">
      <div className="row between"><h2>Predictive exploration: droplet burning-rate constant</h2><button className="btn pri" onClick={run} disabled={busy}>Check eligibility & estimate</button></div>
      <p className="small muted">Only FLEX droplet models exist. Eligibility checks inputs, physical validity, experimental conditions, pressure band, convex-hull membership, normalised nearest-neighbour distance and local data coverage. Being inside the hull alone is not enough.</p>
      {!prediction ? <Empty>Run the check to see whether an estimate is supported for the current scenario.</Empty> : <>
        <div className="row"><Outcome o={prediction.outcome} />{prediction.estimate != null && <b style={{ fontSize: 18 }}>{fmt(prediction.estimate)} mm²/s</b>}
          {prediction.interval_90 && <span className="small muted">90% empirical band {fmt(prediction.interval_90[0])}–{fmt(prediction.interval_90[1])}</span>}
          {prediction.model && <span className="pill">{prediction.model.model_id} · {prediction.model.status}</span>}</div>
        <div style={{ marginTop: 8 }}>{prediction.checks.map((c: any, i: number) => <div key={i} className="check"><span style={{ color: c.result ? "var(--ok)" : "var(--bad)" }}>{c.result ? "✓" : "✕"}</span><div><b className="small">{c.check}</b><div className="small muted">{c.detail}</div></div></div>)}</div>
        <div className="small" style={{ marginTop: 8 }}><b>Why:</b> {prediction.reasons.join("; ")}</div>
        {prediction.boundary && <div className="small faint">{prediction.boundary}</div>}</>}
    </div>
  );
}

export function Workspace() {
  const { scenario, patch, sc, materials, askCopilot, go } = useApp();
  const [q, setQ] = useState(scenario.question || "");
  useEffect(() => { if (scenario.question) setQ(scenario.question); }, [scenario.question]);
  const [res, setRes] = useState<any>(null);
  const [ins, setIns] = useState<any>(null);
  const [ranked, setRanked] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true); setErr(null); patch({ question: q });
    try {
      const [r, i, rk] = await Promise.all([q.trim() ? api.search(q, "auto", sc?.id) : Promise.resolve(null), api.insights(scenario), api.rank(scenario)]);
      setRes(r); setIns(i); setRanked(rk);
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  useEffect(() => { if (scenario.material_id) run(); }, [scenario.material_id, scenario.o2_pct, scenario.pressure_kpa, scenario.gravity]);
  const rankedIds = new Set(res?.results?.map((x: any) => x.id));
  return (
    <Page title="Mission Workspace" intro="Ask any scientific question and set the conditions. Evidence is retrieved (keyword + semantic + graph), ranked by applicability factor by factor, and synthesised into Fire Safety Insights. Predictions appear only where eligible."
      simple="Ask a question about your spacecraft. You'll see the NASA findings that fit best, how closely they match your situation, and what is still unknown.">
      <div className="card">
        <form className="row" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <input style={{ flex: 1, minWidth: 260 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder={`e.g. What NASA evidence applies to the materials in the ${sc?.compartments[0]?.name || "cabin"}?`} />
          <button className="btn pri" disabled={busy}>{busy ? "Analysing…" : "Analyse"}</button>
          <button type="button" className="btn" onClick={() => askCopilot(q || `What does NASA research say about ${matName(materials, scenario.material_id)}?`)}>Ask Copilot</button>
        </form>
        <div className="row" style={{ marginTop: 8 }}><span className="small muted">Try:</span>
          {["What NASA evidence applies to the materials in the Crew quarters of the Orbital Research Module?", "Which findings are relevant to the Sleeping bag in the Orbital Research Module?", "Did Nomex ignite next to burning acrylic?", "Can materials that pass Earth flammability tests burn in lunar gravity?"].map((x) =>
            <button key={x} type="button" className="btn sm" onClick={() => setQ(x)}>{x}</button>)}</div>
        <div style={{ marginTop: 10 }}><Conditions /></div>
        <div className="small faint" style={{ marginTop: 6 }}>Shared scenario · spacecraft {sc?.name} · compartment {scenario.compartment_id || "—"} · object {scenario.object_id || "—"}</div>
      </div>
      <Err e={err} />
      {ins && <div className="grid g2">
        <div className="card"><h2>A · What NASA observed</h2>{ins.observed.length ? ins.observed.map((x: any) => <p key={x.cite} className="small">{x.text} <span className="mono faint">[{x.cite}]</span></p>) : <Empty>No directly or partially applicable finding.</Empty>}</div>
        <div className="card"><h2>B · What the model estimates</h2><Outcome o={ins.model.outcome} />{ins.model.estimate != null && <b> {fmt(ins.model.estimate)} mm²/s</b>}
          <p className="small muted">{ins.model.reasons?.join("; ")}</p><button className="btn sm" onClick={() => document.getElementById("pred")?.scrollIntoView({ behavior: "smooth" })}>Eligibility details</button></div>
        <div className="card"><h2>C · Historical analogues</h2>{ins.historical.length ? ins.historical.map((x: any) => <p key={x.cite} className="small">{x.text} <span className="mono faint">[{x.cite}]</span></p>) : <Empty>None linked.</Empty>}</div>
        <div className="card"><h2>D · What remains uncertain</h2>{ins.uncertain.map((x: any, i: number) => <p key={i} className="small">{x.text}{x.cite && <span className="mono faint"> [{x.cite}]</span>}</p>)}
          <h3>Recommended next steps</h3><ol className="small">{ins.next.map((x: any, i: number) => <li key={i}>{x.text}</li>)}</ol>
          <div className="small faint">{ins.boundary}</div></div>
      </div>}
      {res && <div className="card"><div className="row between"><h2>Retrieved for your question</h2><div className="row"><span className="pill acc">mode: {res.mode}</span>{res.graph_engine && <span className="pill">graph: {res.graph_engine === "neo4j" ? "Neo4j (Cypher)" : "in-memory"}</span>}
        {res.entities?.length > 0 && <span className="pill fire">graph entities: {res.entities.join(", ")}</span>}</div></div>
        {res.note && <div className="banner info">{res.note}</div>}
        {res.results.map((e: any) => <EvidenceCard key={e.id} e={{ ...e, applicability: ranked?.find((r) => r.id === e.id)?.applicability }} />)}</div>}
      {ranked && <div className="card"><h2>Applicability ranking for the scenario ({ranked.filter((r) => r.applicability.tier !== "Not applicable").length} relevant of {ranked.length})</h2>
        {ranked.filter((r) => r.applicability.tier !== "Not applicable" && !rankedIds.has(r.id)).slice(0, 8).map((e) => <EvidenceCard key={e.id} e={e} />)}
        <button className="btn sm" onClick={() => go("library")}>Open full evidence library</button></div>}
      <div id="pred"><PredictionPanel /></div>
      {!ins && !busy && <Empty>Select a component in the digital twin, or choose a material and press Analyse.</Empty>}
    </Page>
  );
}

export function Library() {
  const [tab, setTab] = useState(() => { const t = (window as any).__libTab === "nasa" ? "nasa" : "findings"; (window as any).__libTab = undefined; return t; });
  return (
    <Page title="Evidence library" intro="Every verified NASA finding, searchable with keyword, semantic, hybrid or hybrid + graph retrieval, plus the NASA investigation coverage dashboard with dataset provenance."
      simple="Search every NASA finding in the tool, and see which NASA experiments and datasets power it.">
      <div className="tabs">{[["findings", "Findings"], ["nasa", "NASA investigations & datasets"]].map(([k, l]) => <button key={k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "nasa" ? <NasaCoverage /> : <Findings />}
    </Page>
  );
}

function Findings() {
  const { sc, scenario } = useApp();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("auto");
  const [res, setRes] = useState<any>(null);
  const all = useAsync(() => api.rank(scenario), [JSON.stringify(scenario)]);
  const [inv, setInv] = useState(""); const [cat, setCat] = useState(""); const [grav, setGrav] = useState("");
  const list = (res?.results || all.data || []).filter((e: any) => (!inv || e.investigation === inv) && (!cat || e.category === cat) && (!grav || e.gravity === grav));
  const invs = [...new Set((all.data || []).map((e: any) => e.investigation))].sort() as string[];
  const cats = [...new Set((all.data || []).map((e: any) => e.category))].sort() as string[];
  return (
    <>
      <div className="card">
        <form className="row" onSubmit={async (e) => { e.preventDefault(); setRes(q ? await api.search(q, mode, sc?.id) : null); }}>
          <input style={{ flex: 1, minWidth: 240 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search findings…" />
          <select value={mode} onChange={(e) => setMode(e.target.value)}>{["auto", "keyword", "semantic", "hybrid", "hybrid+graph", "keyword+graph"].map((m) => <option key={m}>{m}</option>)}</select>
          <button className="btn pri">Search</button>{res && <button type="button" className="btn" onClick={() => setRes(null)}>Clear</button>}</form>
        <div className="row" style={{ marginTop: 8 }}>
          <select value={inv} onChange={(e) => setInv(e.target.value)}><option value="">All investigations</option>{invs.map((i) => <option key={i}>{i}</option>)}</select>
          <select value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{cats.map((i) => <option key={i}>{i}</option>)}</select>
          <select value={grav} onChange={(e) => setGrav(e.target.value)}><option value="">All gravity</option>{["microgravity", "partial gravity", "1-g"].map((i) => <option key={i}>{i}</option>)}</select>
          {res && !res.available && <span className="pill warn">{res.reason}</span>}{res?.available && <span className="pill acc">{res.mode}{res.graph_engine ? ` · graph: ${res.graph_engine === "neo4j" ? "Neo4j" : "in-memory"}` : ""} · {fmt(res.latency_ms, 1)} ms</span>}</div>
      </div>
      {all.loading ? <Loading /> : list.map((e: any) => <EvidenceCard key={e.id} e={{ ...e, applicability: e.applicability || all.data?.find((x: any) => x.id === e.id)?.applicability }} />)}
    </>
  );
}