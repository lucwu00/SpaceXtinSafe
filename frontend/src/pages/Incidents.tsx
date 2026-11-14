import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import { Page, Loading, EvidenceCard, Empty, Err } from "../ui";

const PHASES = ["pre-launch", "ascent", "orbital operations", "deep-space transit", "lunar surface", "martian surface", "descent and landing"];
const TYPES: [string, string][] = [["smoke", "Smoke detected"], ["electrical", "Electrical overheating"], ["oxygen", "Oxygen system anomaly"], ["propulsion", "Propulsion event (not cabin fire)"], ["external_heating", "External/entry heating (not cabin fire)"]];

function Procedures({ sid }: { sid: string }) {
  const [list, setList] = useState<any[]>([]);
  const [f, setF] = useState({ title: "", identifier: "", url: "", authority: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.procedures(sid).then(setList).catch(() => setList([])); }, [sid]);
  const add = async () => { setErr(null); try { await api.addProcedure({ ...f, spacecraft_id: sid }); setList(await api.procedures(sid)); setF({ title: "", identifier: "", url: "", authority: "" }); } catch (e: any) { setErr(e.message); } };
  return (
    <div className="card"><h3>Registered vehicle procedure documents</h3>
      <p className="small muted">Register references to authorised, vehicle-specific procedures so they can be found for human review. SpaceXtinSafe never writes or summarises procedure content.</p>
      {list.length ? <ul className="small">{list.map((p) => <li key={p.id}><b>{p.title}</b> {p.identifier && <span className="mono">({p.identifier})</span>} {p.authority && `· ${p.authority}`} {p.url && <a href={p.url} target="_blank" rel="noreferrer">open</a>} <span className="faint">· {p.registered_by}</span></li>)}</ul> : <div className="small faint">None registered for this spacecraft.</div>}
      <Err e={err} />
      <div className="grid g4" style={{ marginTop: 6 }}>{(["title", "identifier", "authority", "url"] as const).map((k) => <input key={k} placeholder={k} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} aria-label={`Procedure ${k}`} />)}</div>
      <button className="btn sm" style={{ marginTop: 6 }} onClick={add} disabled={!f.title}>Register document reference</button>
    </div>
  );
}

export function Incidents() {
  const { sc, scenario, setCtx } = useApp();
  const [comp, setComp] = useState<string>(scenario.compartment_id || sc?.compartments[0]?.id || "");
  const [type, setType] = useState("smoke");
  const [phase, setPhase] = useState("orbital operations");
  const [r, setR] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [step, setStep] = useState(-1);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setComp(scenario.compartment_id && sc?.compartments.some((c: any) => c.id === scenario.compartment_id) ? scenario.compartment_id : sc?.compartments[0]?.id || ""); setR(null); }, [sc?.id]);
  useEffect(() => {
    if (!playing || !r?.timeline?.length) return;
    if (step >= r.timeline.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setStep((s) => s + 1), 1300); return () => clearTimeout(t);
  }, [playing, step, r]);
  const start = async () => {
    setErr(null);
    try { const x = await api.replay({ spacecraft_id: sc.id, compartment_id: comp, type, phase }); setR(x); setStep(0); setPlaying(true); setCtx({ incident: { compartment_id: comp, type, phase } }); }
    catch (e: any) { setErr(e.message); }
  };
  if (!sc) return <Loading />;
  return (
    <Page title="Incident intelligence (simulated)" intro="Replay a hypothetical incident against the active spacecraft's mission manifest. SpaceXtinSafe resolves the compartment, lists configured components that could be involved (unconfirmed), retrieves NASA evidence and historical analogues, flags where evidence comes from a different gravity regime, and points to registered vehicle procedures. It never generates emergency instructions or operational commands."
      simple="A practice scenario: pretend smoke appears in a room. The tool shows what's in that room and what NASA research and past incidents say, and leaves decisions to trained people.">
      <div className="banner">SIMULATED training scenario. Sensor values are synthetic. Real emergency response requires certified vehicle procedures, validated sensors, trained crews, mission-control coordination, certified onboard safety systems and human decision authority.</div>
      <div className="card tight row">
        <label className="row small muted">Mission phase<select value={phase} onChange={(e) => setPhase(e.target.value)}>{PHASES.map((p) => <option key={p}>{p}</option>)}</select></label>
        <label className="row small muted">Compartment<select value={comp} onChange={(e) => setComp(e.target.value)}>{sc.compartments.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label className="row small muted">Incident type<select value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <button className="btn pri" onClick={start} disabled={!comp}>Replay</button>{r?.timeline?.length > 0 && <button className="btn" onClick={() => { setStep(0); setPlaying(true); }}>Restart</button>}
      </div>
      <Err e={err} />
      {!r ? <Empty>Choose a phase, compartment and incident type, then press Replay.</Empty> : r.classification === "Not internal cabin combustion" ? <div className="card"><h2>{r.title}</h2><span className="pill warn">{r.classification}</span><p>{r.message}</p><p className="small faint">{r.disclaimer}</p></div> : <>
        <div className="card"><div className="row between"><h2>{r.title} · {r.compartment}</h2><div className="row"><span className="pill fire">SIMULATED</span><span className="pill">{r.phase} · {r.phase_gravity}</span><span className="pill acc">{r.classification}</span></div></div>
          <div className="small muted">{r.spacecraft} · {r.atmosphere.o2_pct}% O₂ · {r.atmosphere.pressure_kpa} kPa · {r.phase_note}</div>
          <div className="banner info" style={{ marginTop: 10 }}><b>Human-review summary.</b> {r.human_review_summary}</div></div>
        <div className="grid g2">
          <div className="card"><h3>Timeline</h3><div className="timeline">{r.timeline.map((s: any, i: number) => (
            <div key={i} className={`tl ${i <= step ? "on" : ""}`} style={{ opacity: i <= step ? 1 : 0.35 }}>
              <div className="row"><b className="mono">{s.t}</b><span className="pill fire">{s.label}</span><span className="pill">{s.source}</span><span className={`pill ${s.confirmed ? "ok" : "warn"}`}>{s.confirmed ? "confirmed" : "unconfirmed"}</span></div>
              <div>{s.observation}</div>{Object.keys(s.simulated_values || {}).length > 0 && <div className="mono small faint">{JSON.stringify(s.simulated_values)}</div>}
              {i <= step && <div className="small" style={{ color: "var(--acc2)" }}>SpaceXtinSafe: {s.system}</div>}</div>))}</div>
            <div className="banner info">{r.timeline[0]?.procedure_reference}</div>
            <h3>Possibly involved components (unconfirmed)</h3>
            {r.candidates.length ? <div className="scroll" style={{ maxHeight: 280 }}><table><thead><tr><th>Object</th><th>Component</th><th>Material</th><th>NASA evidence</th></tr></thead><tbody>
              {r.candidates.map((c: any, i: number) => <tr key={i}><td>{c.object}</td><td>{c.component}</td><td>{c.material}</td><td><span className={`pill ${c.evidence_ids.length ? "acc" : ""}`}>{c.evidence_status}</span></td></tr>)}</tbody></table></div>
              : <Empty>No configured component in this compartment matches this incident signature.</Empty>}
            {r.applicability_limitations?.length > 0 && <><h3 style={{ marginTop: 10 }}>Applicability limits</h3><ul className="small">{r.applicability_limitations.map((l: string) => <li key={l}>{l}</li>)}</ul></>}
            <p className="small faint">{r.disclaimer}</p></div>
          <div><div className="card"><h3>Historical analogues</h3>{r.analogues.map((e: any) => <EvidenceCard key={e.id} e={e} />)}</div>
            <div className="card"><h3>Related NASA evidence</h3>{step >= r.timeline.length - 1 ? r.evidence.map((e: any) => <EvidenceCard key={e.id} e={e} />) : <span className="small faint">Retrieved at the final replay step.</span>}</div></div>
        </div></>}
      <Procedures sid={sc.id} />
    </Page>
  );
}
