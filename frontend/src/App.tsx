import { useEffect, useState } from "react";
import { AppProvider, useApp } from "./state";
import { api, STATIC, SNAP_META } from "./api";
import { EvidenceCard } from "./ui";
import { Overview } from "./pages/Overview";
import { Studio, Inventory } from "./pages/Studio";
import { Twin } from "./pages/Twin";
import { GraphPage } from "./pages/Graph";
import { Workspace, Library } from "./pages/Workspace";
import { FireLab } from "./pages/FireLab";
import { Gaps, Compare } from "./pages/Gaps";
import { Audit } from "./pages/Audit";
import { Incidents } from "./pages/Incidents";
import { Evaluation, Reports } from "./pages/Evaluation";
import { DemoBar } from "./Demo";

const NAV: [string, [string, string, string][]][] = [
  ["Mission", [["overview", "Mission overview", "◎"], ["studio", "Design Studio", "✦"], ["twin", "Digital twin", "▣"], ["inventory", "Material inventory", "≣"]]],
  ["Intelligence", [["workspace", "Mission Workspace", "⌕"], ["library", "Evidence library", "❏"], ["graph", "Knowledge graphs", "⋔"], ["firelab", "Virtual Fire Lab", "🜂"]]],
  ["Analysis", [["gaps", "Research gaps", "▦"], ["compare", "Compare scenarios", "⇄"], ["audit", "Evidence audit", "✓"], ["incidents", "Incident intelligence", "△"]]],
  ["Trust", [["evaluation", "AI Evaluation Centre", "◈"], ["reports", "Mission reports", "⎙"]]],
];
const PAGES: Record<string, () => JSX.Element> = { overview: Overview, studio: Studio, twin: Twin, inventory: Inventory, workspace: Workspace, library: Library,
  graph: GraphPage, firelab: FireLab, gaps: Gaps, compare: Compare, audit: Audit, incidents: Incidents, evaluation: Evaluation, reports: Reports };

function StatusPills() {
  const { status } = useApp();
  if (!status) return <span className="pill bad">API unreachable</span>;
  const s = status.semantic, c = status.copilot, g = status.graph;
  return <>
    <span className={`pill ${s.loaded ? "ok" : s.error ? "warn" : ""}`} title={s.error || s.model}>Semantic: {s.loaded ? "on" : s.error ? "unavailable" : "not loaded yet"}</span>
    <span className={`pill ${c.verified_live ? "ok" : c.key_configured ? "warn" : ""}`} title={c.last_error || ""}>Claude: {c.verified_live ? "live (verified)" : c.key_configured ? "key set, not yet verified" : "off (evidence mode)"}</span>
    <span className={`pill ${g.connected ? "ok" : ""}`} title={g.error || ""}>{g.connected ? "Neo4j: connected" : "Graph: in-memory + SQLite"}</span>
  </>;
}

function RoutingLine({ rt }: { rt: any }) {
  const engine = rt.engine || (rt.tier ? `Tier ${rt.tier}` : "Python (no LLM)");
  return <div className="small muted" style={{ marginBottom: 6 }}>
    <div><b>Engine:</b> {engine}{rt.model ? ` · ${rt.model}` : ""} · tier {rt.tier ?? 0}{rt.selected_tier && rt.selected_tier !== rt.tier ? (rt.escalations?.length && rt.tier > rt.selected_tier ? ` (started at tier ${rt.selected_tier}: ${rt.selected_model})` : ` (routed to tier ${rt.selected_tier}: ${rt.selected_model}, not used)`) : ""}{rt.cached ? " · cached" : ""}</div>
    <div><b>Why:</b> {rt.reason}</div>
    <div>{rt.latency_ms != null && `${rt.latency_ms} ms`}{rt.input_tokens != null && !rt.cached && ` · ${rt.input_tokens} in / ${rt.output_tokens} out tokens`}{rt.cost_usd != null && (rt.cached ? " · cached: no new API cost" : ` · est. $${rt.cost_usd.toFixed(5)}`)}{` · ${rt.evidence_retrieved ?? 0} evidence`}</div>
    {rt.escalations?.length > 0 && <div><b>Escalated:</b> {rt.escalations.map((e: any) => `${e.from}${e.to ? " → " + e.to : ""} (${e.why})`).join("; ")}</div>}
    {rt.fallback && <div><b>Fallback:</b> {rt.fallback}</div>}
  </div>;
}

function Copilot() {
  const { copilotOpen, setCopilotOpen, copilotSeed, scenario, scId, sc, refreshStatus } = useApp();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [hist, setHist] = useState<any[]>([]);
  const [cmode, setCmode] = useState<"auto" | "fast" | "deep">("auto");
  const ask = async (question: string) => {
    if (!question.trim()) return;
    setBusy(true);
    try { const r = await api.copilot(question, scenario, scId, cmode); setHist((h) => [{ q: question, r }, ...h]); refreshStatus(); }
    catch (e: any) { setHist((h) => [{ q: question, r: { mode: "error", answer: e.message, claims: [], evidence: [] } }, ...h]); }
    setBusy(false); setQ("");
  };
  useEffect(() => { if (copilotSeed) { const s = copilotSeed.replace(/​/g, ""); setQ(s); ask(s); } }, [copilotSeed]);
  if (!copilotOpen) return <button className="btn pri fab" onClick={() => setCopilotOpen(true)}>Scientific Copilot</button>;
  return (
    <div className="drawer" role="dialog" aria-label="Scientific Copilot">
      <div className="row between" style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)" }}>
        <div><b>Scientific Copilot</b><div className="small muted">Answers only from NASA evidence · context: {sc?.name || "—"}</div></div>
        <button className="btn sm" onClick={() => setCopilotOpen(false)}>Close</button>
      </div>
      <div className="body">
        <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="col">
          <textarea rows={3} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about materials, experiments, conditions or this spacecraft…" />
          <div className="row" role="radiogroup" aria-label="Copilot mode">{([["auto", "Auto", "Selects the processing tier from the question"], ["fast", "Fast", "Lower cost: lightweight model, same evidence checks"], ["deep", "Deep Research", "Advanced model for scientific questions"]] as const).map(([k, l, t]) =>
            <button type="button" key={k} role="radio" aria-checked={cmode === k} title={t} className={`btn sm ${cmode === k ? "pri" : ""}`} onClick={() => setCmode(k)}>{l}</button>)}</div>
          <div className="row"><button className="btn pri" disabled={busy}>{busy ? "Thinking…" : "Ask"}</button>
            {["What NASA evidence applies to the Crew quarters?", "What does Saffire show about Nomex?", "Why is lunar gravity a concern?"].map((s) =>
              <button type="button" key={s} className="btn sm" onClick={() => ask(s)}>{s}</button>)}</div>
        </form>
        {hist.map((h, i) => (
          <div key={i} className="card tight" style={{ marginTop: 12 }}>
            <div className="small muted">You asked</div><div style={{ marginBottom: 8 }}>{h.q}</div>
            <div className="row" style={{ marginBottom: 6 }}><span className={`pill ${h.r.mode === "claude" ? "ok" : h.r.mode === "boundary" ? "fire" : ""}`}>
              {h.r.mode === "claude" ? `Claude (${h.r.model})` : h.r.mode === "evidence-retrieval" ? "Evidence retrieval (no LLM)" : h.r.mode === "deterministic" ? "Deterministic (no LLM)" : h.r.mode}</span>
              {h.r.retrieval_mode && <span className="pill">retrieval: {h.r.retrieval_mode}{h.r.graph_engine ? ` · graph: ${h.r.graph_engine === "neo4j" ? "Neo4j" : "in-memory"}` : ""}</span>}</div>
            {h.r.routing && <RoutingLine rt={h.r.routing} />}
            {h.r.claims?.length ? <ul style={{ paddingLeft: 18, margin: 0 }}>{h.r.claims.map((c: any, j: number) =>
              <li key={j}>{c.text} <span className="mono faint">[{c.citations.join(", ")}]</span></li>)}</ul> : <p>{h.r.answer}</p>}
            {h.r.items?.length > 0 && <ul className="small" style={{ paddingLeft: 18, marginTop: 6 }}>{h.r.items.map((x: string) => <li key={x}>{x}</li>)}</ul>}
            {h.r.dropped?.length > 0 && <div className="banner" style={{ marginTop: 8 }}>{h.r.dropped.length} claim(s) removed by the citation and number check: {h.r.dropped.map((d: any) => d.problems.join("; ")).join(" | ")}</div>}
            {h.r.limitations && <div className="small faint" style={{ marginTop: 6 }}>{h.r.limitations}</div>}
            {h.r.evidence?.length > 0 && <details style={{ marginTop: 8 }}><summary className="small muted">Evidence used ({h.r.evidence.length})</summary>
              {h.r.evidence.map((e: any) => <EvidenceCard key={e.id} e={e} />)}</details>}
          </div>))}
      </div>
    </div>
  );
}

const WELCOME_KEY = "sxs-welcome-v1";
function Welcome() {
  const { setDemo, go, setCopilotOpen } = useApp();
  const [open, setOpen] = useState(() => { try { return !localStorage.getItem(WELCOME_KEY); } catch { return true; } });
  const close = () => { try { localStorage.setItem(WELCOME_KEY, "1"); } catch { /* storage unavailable: show again next time */ } setOpen(false); };
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => { if (e.key === "Escape") close(); }; addEventListener("keydown", k); return () => removeEventListener("keydown", k); }, [open]);
  if (!open) return null;
  return (
    <div className="welcome-back" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
      <div className="welcome">
        <div className="small" style={{ color: "var(--acc2)", letterSpacing: 2, fontFamily: "var(--mono)" }}>WELCOME · NASA SPACE APPS 2026 · FLAME IN FREEFALL</div>
        <h1 id="welcome-title" style={{ fontSize: 26, margin: "8px 0 6px" }}>SpaceXtinsafe</h1>
        <p className="muted" style={{ marginTop: 0 }}>Links the things inside a spacecraft to what NASA microgravity fire experiments actually measured, shows how far each finding applies, and says clearly where the evidence stops.</p>
        <div className="grid g3" style={{ margin: "14px 0" }}>
          <div className="kpi"><b style={{ fontSize: 15 }}>1 · Take the tour</b><span>18 short steps drive the real app: digital twin, evidence, predictions, audit, gaps, reports. About 3 minutes.</span></div>
          <div className="kpi"><b style={{ fontSize: 15 }}>2 · Ask your own question</b><span>The Scientific Copilot answers only from NASA evidence, with citations, or says the evidence is missing.</span></div>
          <div className="kpi"><b style={{ fontSize: 15 }}>3 · Build a spacecraft</b><span>Design Studio: change compartments, materials and the cabin atmosphere; every module updates.</span></div>
        </div>
        <div className="row">
          <button autoFocus className="btn pri" onClick={() => { close(); setDemo(0); }}>▶ Start the guided tour (recommended for judges)</button>
          <button className="btn" onClick={() => { close(); setCopilotOpen(true); }}>Ask the Copilot</button>
          <button className="btn" onClick={() => { close(); go("studio"); }}>Open Design Studio</button>
          <button className="btn" onClick={close}>Explore on my own</button>
        </div>
        <p className="small faint" style={{ marginBottom: 0 }}>Independent research prototype, not NASA-endorsed. No safety verdicts or emergency instructions. Restart the tour any time with “▶ Guided demo” in the header.</p>
      </div>
    </div>
  );
}

function Shell() {
  const { page, go, list, scId, setScId, simple, setSimple, setDemo, demo } = useApp();
  const P = PAGES[page] || Overview;
  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><svg width="30" height="30" viewBox="0 0 32 32" aria-hidden><circle cx="16" cy="16" r="14" fill="none" stroke="#4ea1ff" strokeWidth="2" /><path d="M16 7c4 5 6 8 6 12a6 6 0 0 1-12 0c0-3 2-5 3-6 0 2 1 3 2 3 0-3 0-6 1-9z" fill="#ff8a3d" /></svg>
          <div><b>SpaceXtinsafe</b><small>From Research to Readiness</small></div></div>
        {NAV.map(([g, items]) => <div key={g}><div className="navgroup">{g}</div>
          {items.map(([id, label, ic]) => <button key={id} className={`nav ${page === id ? "on" : ""}`} onClick={() => go(id)}><span style={{ width: 16, textAlign: "center" }}>{ic}</span>{label}</button>)}</div>)}
        <div className="small faint" style={{ padding: "16px 10px" }}>Research prototype. Not NASA-endorsed. No safety verdicts or emergency instructions.</div>
      </aside>
      <div className="main">
        <div className="top">
          <label className="row small muted">Spacecraft
            <select value={scId} onChange={(e) => setScId(e.target.value)} aria-label="Active spacecraft">{list.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          <button className="btn sm" onClick={() => go("studio")}>+ New / edit</button>
          <button className="btn sm" onClick={() => setDemo(0)}>▶ Guided demo</button>
          <span className="grow" />
          {STATIC && <span className="pill fire">Static preview</span>}
          <StatusPills />
          <label className="row small muted" title="Plain-language explanations for non-specialists"><input type="checkbox" checked={simple} onChange={(e) => setSimple(e.target.checked)} /> Plain language</label>
        </div>
        <div className="content" style={{ paddingBottom: demo !== null ? 150 : undefined }}>
          {STATIC && <div className="banner info">Static preview of the SpaceXtinsafe app. Every response on this page was recorded from the real FastAPI backend{SNAP_META.recorded ? ` on ${SNAP_META.recorded}` : ""} ({SNAP_META.responses || "many"} responses). Navigation, the three template spacecraft, the graph, audit, evaluation, reports and the suggested questions all work. Editing spacecraft and arbitrary new queries need the live backend.</div>}
          <P /></div>
      </div>
      <Copilot />
      <DemoBar />
      <Welcome />
    </div>
  );
}

export default function App() { return <AppProvider><Shell /></AppProvider>; }