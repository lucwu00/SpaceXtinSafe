import { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import { Page, useAsync, Loading, Outcome, fmt, Err } from "../ui";

export function Evaluation() {
  const e = useAsync(() => api.evaluation(), []);
  const { status } = useApp();
  const [tab, setTab] = useState("retrieval");
  if (e.loading) return <Loading />;
  if (!e.data || e.data.status === "not run") return <Err e="Evaluation has not been run on this server (python -m scripts.run_eval)." />;
  const R = e.data.retrieval, C = e.data.copilot, EL = e.data.eligibility;
  const modes = Object.keys(R.modes);
  return (
    <Page title="AI Evaluation Centre" intro={`Results of the evaluation script, run ${e.data.generated_utc}. Totals are computed from the executed cases. Labels were fixed before the first run; their SHA-256 is shown.`}
      simple="How well the search, the copilot and the prediction checks actually perform, measured on test questions.">
      <div className="tabs">{[["retrieval", "Retrieval & GraphRAG (dev set)"], ["holdout", "Holdout set"], ["copilot", "Copilot (deterministic)"], ["claude", "Live Claude Copilot"], ["routing", "Multi-model routing"], ["eligibility", "Prediction eligibility"], ["models", "Model cards"], ["system", "System & disclosures"]].map(([k, l]) =>
        <button key={k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "retrieval" && <>
        <div className="card"><h2>Recall@{R.k} and MRR by mode ({R.n_questions} questions; {R.modes[modes[0]].n_unsupported_excluded} unsupported excluded)</h2>
          <table><thead><tr><th>Mode</th><th>All recall</th><th>All MRR</th><th>Single-hop recall</th><th>Single-hop MRR</th><th>Multi-hop recall</th><th>Multi-hop MRR</th><th>Median latency</th></tr></thead>
            <tbody>{modes.map((m) => { const v = R.modes[m]; return v.status ? <tr key={m}><td>{m}</td><td colSpan={7}><span className="pill warn">{v.status}: {v.reason}</span></td></tr> :
              <tr key={m}><td><b>{m}</b></td><td>{fmt(v.all["recall@5"])}</td><td>{fmt(v.all.mrr)}</td><td>{fmt(v["single-hop"]["recall@5"])}</td><td>{fmt(v["single-hop"].mrr)}</td><td>{fmt(v["multi-hop"]["recall@5"])}</td><td>{fmt(v["multi-hop"].mrr)}</td><td>{fmt(v.all.latency_ms_median, 1)} ms</td></tr>; })}</tbody></table>
          <p className="small muted">Semantic model: {R.semantic_model.model} · loaded {String(R.semantic_model.loaded)} · {R.semantic_model.dim}-d · embedding check {R.semantic_model.embedding_check ? `${R.semantic_model.embedding_check.passed ? "passed" : "FAILED"} (paraphrase cos ${fmt(R.semantic_model.embedding_check["cos(related paraphrase)"], 2)} vs unrelated ${fmt(R.semantic_model.embedding_check["cos(unrelated)"], 2)})` : "not run"}</p></div>
        <div className="grid g2"><div className="card"><h2>Did the graph help? (hybrid vs hybrid + graph, per question)</h2>
          {Object.entries(R.graph_effect_counts).map(([t, c]: any) => <p key={t}><b>{t}:</b> {Object.entries(c).map(([k, n]) => `${n} ${k}`).join(", ")}</p>)}
          <p className="small muted">The graph adds findings reached from spacecraft elements named in the question. On single-hop questions it changed nothing; on multi-hop questions it is shown per question below, including where it gave no improvement.</p></div>
          <div className="card"><h2>Run history</h2>{(e.data.run_history || []).map((h: any) => <p key={h.run} className="small"><b>Run {h.run}:</b> {h.note} Hybrid+graph multi-hop recall@5 = {fmt(h["hybrid+graph multi-hop recall@5"])}</p>)}
            <p className="small mono faint">labels sha256 {R.label_file_sha256.slice(0, 16)}…</p></div></div>
        <div className="card"><h2>Per-question graph effect</h2><div className="scroll"><table><thead><tr><th>Q</th><th>Type</th><th>Hybrid recall</th><th>Hybrid+graph recall</th><th>Effect</th></tr></thead>
          <tbody>{R.graph_effect_by_question.map((r: any) => <tr key={r.id}><td>{r.id}</td><td>{r.type}</td><td>{fmt(r["hybrid_recall@5"], 2)}</td><td>{fmt(r["graph_recall@5"], 2)}</td>
            <td><span className={`pill ${r.effect === "improved" ? "ok" : r.effect === "worse" ? "bad" : ""}`}>{r.effect}</span></td></tr>)}</tbody></table></div>
          <p className="small faint">{R.disclosure}</p></div></>}
      {tab === "holdout" && e.data.holdout && (() => { const H = e.data.holdout.retrieval; const types = ["all", ...H.types.filter((t: string) => t !== "unsupported")]; return <>
        <div className="banner info">{e.data.holdout.note} Labels sha256 {H.label_file_sha256.slice(0, 16)}…; the retrieval system was not changed after this set was written.</div>
        <div className="card"><h2>Holdout recall@{H.k} by question type ({H.n_questions} questions)</h2><div className="scroll"><table><thead><tr><th>Mode</th>{types.map((t: string) => <th key={t}>{t}{H.modes[Object.keys(H.modes)[0]][t] ? ` (n=${H.modes[Object.keys(H.modes)[0]][t].n})` : ""}</th>)}</tr></thead>
          <tbody>{Object.entries(H.modes).map(([m, v]: any) => <tr key={m}><td><b>{m}</b></td>{types.map((t: string) => <td key={t}>{v[t] ? fmt(v[t]["recall@5"]) : "—"}</td>)}</tr>)}</tbody></table></div>
          <p className="small muted">Graph effect per question: {Object.entries(H.graph_effect_counts).map(([t, c]: any) => `${t}: ${Object.entries(c).map(([k, n]) => `${n} ${k}`).join(", ")}`).join(" · ")}</p>
          <p className="small faint">{H.disclosure}</p></div>
        <div className="card"><h2>Holdout copilot: {e.data.holdout.copilot.n_passed} / {e.data.holdout.copilot.n_cases}</h2><div className="row">{Object.entries(e.data.holdout.copilot.by_expected).map(([k, v]: any) => <span key={k} className="pill">{k}: {v.passed}/{v.n}</span>)}</div>
          <p className="small faint">{e.data.holdout.copilot.disclosure}</p></div></>; })()}
      {tab === "claude" && (() => { const L = e.data.claude_live || { status: "not run" }; return L.status !== "run" ?
        <div className="card"><h2>Live Claude Copilot: not evaluated yet</h2><p>{L.reason || "No live run recorded."}</p>
          <p className="small muted">The 15 live cases are fixed in advance. Once ANTHROPIC_API_KEY and ADMIN_TOKEN are set on the server, run <span className="mono">POST /api/evaluation/claude-live</span> with header <span className="mono">X-Admin-Token</span>. The deterministic results in the other tabs do not establish the accuracy of the generative Copilot.</p></div> :
        <div className="card"><h2>Live Claude Copilot: {L.n_passed} / {L.n_cases} cases passed</h2><div className="small muted">Model {L.model} · run {L.generated_utc} · {L.judge}</div>
          <div className="grid g4" style={{ margin: "10px 0" }}>
            <div className="kpi"><b>{L.answer_cases.citation_correct}/{L.answer_cases.n}</b><span>answers with only retrieved citations</span></div>
            <div className="kpi"><b>{fmt(L.answer_cases.mean_citation_completeness, 2)}</b><span>mean citation completeness</span></div>
            <div className="kpi"><b>{L.answer_cases.numbers_ok}/{L.answer_cases.n}</b><span>expected numbers stated</span></div>
            <div className="kpi"><b>{L.abstain.passed}/{L.abstain.n} · {L.boundary.passed}/{L.boundary.n}</b><span>abstentions · boundary refusals</span></div></div>
          <table><thead><tr><th>Case</th><th>Expected</th><th>Mode</th><th>Cited</th><th>Removed claims</th><th>Entailment (judge)</th><th>Result</th></tr></thead><tbody>{L.cases.map((c: any) => <tr key={c.id}><td>{c.id}</td><td>{c.expected}</td><td>{c.mode}</td><td className="mono small">{c.cited.join(", ") || "—"}</td><td>{c.dropped}</td><td>{c.judge_entailed || "—"}</td><td><span className={`pill ${c.passed ? "ok" : "bad"}`}>{c.passed ? "pass" : "fail"}</span></td></tr>)}</tbody></table>
          <p className="small faint">{L.disclosure}</p></div>; })()}
      {tab === "routing" && <Routing R={e.data.routing} />}
      {tab === "copilot" && <div className="card"><h2>{C.n_passed} / {C.n_cases} copilot cases passed</h2>
        <div className="row">{Object.entries(C.by_expected).map(([k, v]: any) => <span key={k} className="pill">{k}: {v.passed}/{v.n}</span>)}<span className={`pill ${C.claude_live ? "ok" : "warn"}`}>Claude live during run: {String(C.claude_live)}</span></div>
        <div className="banner" style={{ marginTop: 10 }}>{C.disclosure}</div>
        <table><thead><tr><th>Case</th><th>Expected</th><th>Mode</th><th>Cited</th><th>Result</th></tr></thead><tbody>{C.cases.map((c: any) => <tr key={c.id}><td>{c.id}</td><td>{c.expected}</td><td>{c.mode}</td><td className="mono small">{c.cited.join(", ") || "—"}</td><td><span className={`pill ${c.passed ? "ok" : "bad"}`}>{c.passed ? "pass" : "fail"}</span></td></tr>)}</tbody></table>
        <p className="small muted">Currently on this server: Claude {status?.copilot.verified_live ? "verified live" : status?.copilot.key_configured ? "key configured (not yet verified)" : "not configured"}.</p></div>}
      {tab === "eligibility" && <div className="card"><h2>{EL.n_passed} / {EL.n_cases} eligibility cases behaved as specified</h2>
        <table><thead><tr><th>Case</th><th>Expected</th><th>Outcome</th><th>Reasons</th></tr></thead><tbody>{EL.cases.map((c: any) => <tr key={c.case}><td>{c.case}</td><td>{c.expected}</td><td><Outcome o={c.outcome} /></td><td className="small muted">{c.reasons.join("; ")}</td></tr>)}</tbody></table></div>}
      {tab === "models" && <div className="card"><h2>Model cards</h2><table><thead><tr><th>Model</th><th>Status</th><th>n / sessions</th><th>Features</th><th>Parameters</th><th>OLS MAE</th><th>RF MAE</th><th>Baseline MAE</th><th>Skill</th><th>90% band</th></tr></thead>
        <tbody>{e.data.models.map((m: any) => <tr key={m.model_id}><td>{m.model_id}</td><td>{m.status}{m.failed_criteria.length ? <div className="small faint">failed: {m.failed_criteria.join(", ")}</div> : null}</td><td>{m.n_observations} / {m.n_sessions}</td>
          <td className="small">{m.features.join(", ")}</td><td>{m.n_parameters}</td><td>{fmt(m.validation.mae)}</td><td>{fmt(m.benchmark.random_forest.mae)}</td><td>{fmt(m.validation.baseline_mae)}</td><td>{fmt(m.validation.predictive_skill, 2)}</td><td>±{fmt(m.uncertainty_90_mm2_s)}</td></tr>)}</tbody></table>
        <p className="small muted">Leave-one-session-out CV on identical folds for OLS, random forest and the mean baseline. Parameter counts include the intercept. {e.data.models[0]?.benchmark.decision}.</p></div>}
      {tab === "system" && <div className="grid g2"><div className="card"><h2>Data integrity</h2><p>{e.data.data.quotes_verified} / {e.data.data.evidence_statements} evidence quotes verified verbatim against source text.</p>
        <p>Audit: {Object.entries(e.data.audit.counts).map(([k, v]) => `${v} ${k}`).join(", ")} across {e.data.audit.flex_rows_compared} FLEX rows plus Saffire tables.</p>
        <p>Graph: {e.data.graph.nodes} nodes, {e.data.graph.edges} relationships · {e.data.graph.neo4j.mode}</p></div>
        <div className="card"><h2>Disclosures</h2><ul className="small"><li>{R.disclosure}</li><li>{C.disclosure}</li><li>Runtime {e.data.runtime_s}s.</li></ul></div></div>}
    </Page>
  );
}

export function Reports() {
  const { sc, scenario, prediction, ctx } = useApp();
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const gen = async () => {
    setBusy(true); setErr(null);
    try { const b = await api.report({ spacecraft_id: sc.id, scenario: scenario.material_id ? scenario : null, prediction, interaction_ids: ctx.interaction_ids, compare_ids: ctx.compare_ids, incident: ctx.incident }); setUrl(URL.createObjectURL(b)); }
    catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <Page title="Mission evidence report" intro="Generate a PDF with the configuration, material evidence screening, scenario insights, prediction eligibility (if run), audit summary, model cards and full source list, with the research-prototype boundary on every report."
      simple="Download a PDF summary of everything for this spacecraft, with the NASA sources listed.">
      <Err e={err} />
      <div className="card"><h2>{sc?.name}</h2>
        <ul className="small"><li>Scenario: {scenario.material_id ? `${scenario.material_id} · ${scenario.o2_pct}% O₂ · ${scenario.pressure_kpa} kPa · ${scenario.gravity}` : "none selected (configuration-level report)"}</li>
          <li>Prediction: {prediction ? prediction.outcome : "not run"}</li>
          <li>Material interaction: {ctx.interaction_ids?.length ? ctx.interaction_ids.join(" + ") : "none (set in Virtual Fire Lab, Level 2)"}</li>
          <li>Configuration comparison: {ctx.compare_ids?.length ? ctx.compare_ids.join(" vs ") : "none (set in Compare scenarios)"}</li>
          <li>Simulated incident: {ctx.incident ? `${ctx.incident.type} in ${ctx.incident.compartment_id} during ${ctx.incident.phase}` : "none (replay one in Incident intelligence)"}</li></ul>
        <div className="row"><button className="btn pri" onClick={gen} disabled={busy || !sc}>{busy ? "Generating…" : "Generate PDF"}</button>
          {url && <a className="btn" href={url} download="spacextinsafe_mission_report.pdf">Download report</a>}</div></div>
      {url && <iframe title="Report preview" src={url} style={{ width: "100%", height: 720, border: "1px solid var(--line)", borderRadius: 9 }} />}
    </Page>
  );
}

function Routing({ R }: { R: any }) {
  const u = useAsync(() => api.copilotUsage(), []);
  if (!R || R.status === "not run") return <div className="card"><h2>Multi-model routing: not evaluated yet</h2><p className="small">Run <span className="mono">python -m scripts.eval_routing</span>.</p></div>;
  const A = R.routing_accuracy, cfg = R.config, L = R.live;
  const TN = ["Tier 0 · deterministic (no LLM)", "Tier 1 · lightweight", "Tier 2 · scientific", "Tier 3 · advanced"];
  return <>
    <div className="card"><h2>Configured tiers</h2>
      <table><thead><tr><th>Tier</th><th>Model (env variable)</th><th>Max output tokens</th><th>Price used for estimates (USD / M tokens in, out)</th><th>Available on this key</th></tr></thead>
        <tbody><tr><td>{TN[0]}</td><td>Python functions, graph traversal, FLEX models</td><td>—</td><td>0</td><td>always</td></tr>
          {[1, 2, 3].map((t) => { const c = cfg.tiers[t]; return <tr key={t}><td>{TN[t]}</td><td className="mono">{c.model} ({c.env})</td><td>{c.max_tokens}</td><td>{c.price_usd_per_mtok.join(", ")}</td><td>{c.available === undefined || c.available === null ? "not verified" : c.available ? "yes" : "no"}</td></tr>; })}</tbody></table>
      <div className="small faint" style={{ marginTop: 6 }}>{cfg.price_source}. Rules choose the tier; no model is called to choose a model. Missing evidence abstains and never escalates.</div></div>
    <div className="card"><h2>Routing accuracy: {A.correct} / {A.n} locked cases routed to the expected tier</h2>
      <div className="small muted">Run {R.generated_utc} · cases sha256 {R.case_file_sha256.slice(0, 12)}… · lock {R.lock_matches ? "matches" : "does NOT match"} · labels written by the same developer as the rules, so this measures conformity to the stated policy.</div>
      <div className="row" style={{ margin: "8px 0" }}>{[0, 1, 2, 3].map((t) => <span key={t} className="pill">{TN[t]}: {A.by_expected_tier[t].correct}/{A.by_expected_tier[t].n}</span>)}</div>
      <div className="scroll" style={{ maxHeight: 360 }}><table><thead><tr><th>Case</th><th>Kind</th><th>Expected</th><th>Routed</th><th>Reason</th></tr></thead>
        <tbody>{A.cases.map((c: any) => <tr key={c.id}><td>{c.id}{c.correct ? "" : " ✗ miss"}</td><td>{c.kind}</td><td>{c.expected}</td><td>{c.routed}</td><td className="small">{c.reason}</td></tr>)}</tbody></table></div></div>
    <div className="card"><h2>Live answer quality, latency and cost</h2>
      {L.status !== "run" ? <p>Not measured: {L.reason}. Cost savings and answer quality are not claimed until this run is executed with an API key (admin endpoint <span className="mono">POST /api/evaluation/routing-live</span>).</p> :
        <><table><thead><tr><th>Run</th><th>LLM calls</th><th>Models</th><th>Tokens in / out</th><th>Est. cost</th><th>Median latency</th><th>Claims kept / dropped</th><th>Escalations</th><th>Fallbacks</th></tr></thead>
          <tbody>{[["Auto", L.auto?.summary], ["Deep Research baseline", L.deep_baseline?.summary]].filter(([, x]) => x).map(([n, x]: any) =>
            <tr key={n}><td>{n}</td><td>{x.llm_calls}</td><td className="small">{Object.entries(x.by_model).map(([m, k]) => `${m} ×${k}`).join(", ")}</td><td>{x.input_tokens} / {x.output_tokens}</td><td>${x.cost_usd}</td><td>{x.latency_ms_median} ms</td><td>{x.claims_kept} / {x.claims_dropped}</td><td>{x.escalations}</td><td>{x.fallbacks}</td></tr>)}</tbody></table>
          {L.deep_baseline?.same_questions_llm_only && <p className="small">Same LLM questions: Auto ${L.deep_baseline.same_questions_llm_only.auto.cost_usd} vs Deep ${L.deep_baseline.same_questions_llm_only.deep.cost_usd}. {L.deep_baseline.same_questions_llm_only.note}</p>}</>}</div>
    <div className="card"><h2>Monitoring on this server</h2>
      {!u.data ? <Loading /> : u.data.static ? <p className="small">Not available in the static preview.</p> : <>
        <div className="row"><span className="pill">{u.data.requests} requests logged</span><span className="pill">{u.data.escalations} escalations</span><span className="pill">{u.data.fallbacks} fallbacks</span><span className="pill">{u.data.cache_hits} cache hits</span>
          <span className="pill">today est. ${(u.data.today?.usd ?? 0).toFixed(4)} of ${u.data.limits.daily_budget_usd} budget</span><span className="pill">rate limit {u.data.limits.rate_per_min}/min</span></div>
        <table style={{ marginTop: 8 }}><thead><tr><th>Engine</th><th>Requests</th><th>Tokens in / out</th><th>Est. cost</th><th>Median latency</th></tr></thead>
          <tbody>{Object.entries(u.data.by_engine).map(([k, v]: any) => <tr key={k}><td>{k}</td><td>{v.n}</td><td>{v.input_tokens} / {v.output_tokens}</td><td>${v.cost_usd}</td><td>{v.latency_ms_median} ms</td></tr>)}</tbody></table></>}</div>
  </>;
}
