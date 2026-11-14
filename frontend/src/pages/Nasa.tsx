import { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import { useAsync, Loading, Empty } from "../ui";

const arr = (v: any): string[] => (Array.isArray(v) ? v : v ? [String(v)] : []);
const ST: Record<string, string> = {
  "Fully integrated original dataset": "ok", "Partially integrated original dataset": "acc", "Curated scientific findings available": "model",
  "Scientific reference only": "", "Dataset acquired but not yet analysed": "warn", "Source unavailable": "bad", "Pending verification": "",
};
const FEATURES = ["Droplet burning-rate prediction", "Evidence audit", "Flame spread & interactions", "Extinction & flammability boundaries", "Smoke detection research", "Ignition & extinction research", "Partial-gravity limitations", "Knowledge graph", "Incident analogues"];

/** Investigation → feature map built only from what the backend reports as integrated for each investigation. */
function FeatureMap({ invs }: { invs: any[] }) {
  const rows = invs.filter((i) => arr(i.features).length);
  const feats = [...new Set(rows.flatMap((i) => i.features))] as string[];
  const order = [...FEATURES.filter((f) => feats.includes(f)), ...feats.filter((f) => !FEATURES.includes(f))];
  const H = Math.max(rows.length, order.length) * 30 + 20, W = 760;
  const y1 = (i: number) => 20 + i * ((H - 30) / Math.max(1, rows.length - 1 || 1));
  const y2 = (i: number) => 20 + i * ((H - 30) / Math.max(1, order.length - 1 || 1));
  return (
    <div style={{ overflowX: "auto" }}><svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", minWidth: 560 }} role="img" aria-label="Investigation to feature map">
      {rows.map((r, i) => r.features.map((f: string) => { const j = order.indexOf(f); return <path key={r.acronym + f} d={`M200 ${y1(i)} C 380 ${y1(i)}, 380 ${y2(j)}, 560 ${y2(j)}`} fill="none" stroke="var(--acc)" strokeOpacity={0.35} strokeWidth={1.5} />; }))}
      {rows.map((r, i) => <g key={r.acronym}><circle cx={200} cy={y1(i)} r={4} fill="var(--fire)" /><text x={190} y={y1(i) + 4} textAnchor="end" fontSize={12} fill="var(--ink)">{r.acronym}</text></g>)}
      {order.map((f, j) => <g key={f}><circle cx={560} cy={y2(j)} r={4} fill="var(--acc2)" /><text x={570} y={y2(j) + 4} fontSize={12} fill="var(--ink)">{f}</text></g>)}
    </svg></div>
  );
}

export function NasaCoverage() {
  const invs = useAsync(() => api.investigations(), []);
  const ds = useAsync(() => api.datasets(), []);
  const use = useAsync(() => api.nasaUsage(), []);
  const { go, patch } = useApp();
  const [sel, setSel] = useState<any>(null);
  const [st, setSt] = useState("");
  if (invs.loading) return <Loading />;
  const list = (invs.data || []).filter((i: any) => !st || i.status === st);
  const counts: Record<string, number> = {};
  (invs.data || []).forEach((i: any) => { counts[i.status] = (counts[i.status] || 0) + 1; });
  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <button className={`btn sm ${!st ? "pri" : ""}`} onClick={() => setSt("")}>All ({invs.data?.length})</button>
        {Object.entries(counts).map(([k, n]) => <button key={k} className={`btn sm ${st === k ? "pri" : ""}`} onClick={() => setSt(k)}>{k} ({n})</button>)}
      </div>
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
        {list.map((i: any) => (
          <button key={i.acronym} className="card tight" style={{ textAlign: "left", color: "inherit", cursor: "pointer", borderColor: sel?.acronym === i.acronym ? "var(--acc)" : undefined }} onClick={() => setSel(i)}>
            <div className="row between"><b style={{ fontSize: 15 }}>{i.acronym}</b>{i.accession && <span className="mono faint">{i.accession}</span>}</div>
            <div className="small muted" style={{ minHeight: 36 }}>{i.official_name}</div>
            <span className={`pill ${ST[i.status] || ""}`}>{i.status}</span>
            <div className="row small" style={{ marginTop: 6, gap: 12 }}><span><b>{i.curated_findings}</b> findings</span><span><b>{i.integrated_measurements ?? 0}</b> records used</span><span><b>{i.models?.length || 0}</b> models</span></div>
          </button>))}
      </div>
      {sel && <div className="card" style={{ marginTop: 14 }}>
        <div className="row between"><div><h2>{sel.official_name} ({sel.acronym})</h2><div className="small muted">{sel.platform}{sel.hardware ? ` · ${sel.hardware}` : ""}{sel.dates?.[0] ? ` · ${sel.dates.filter(Boolean).join(" to ")}` : ""}</div></div>
          <span className={`pill ${ST[sel.status] || ""}`}>{sel.status}</span></div>
        <div className="grid g2" style={{ marginTop: 10 }}>
          <div><h3>Scientific objective</h3><p className="small">{sel.objective || "Not curated."}</p><div className="small faint">Text source: {sel.text_source}</div>
            <h3 style={{ marginTop: 10 }}>Materials and conditions</h3><p className="small">{sel.materials?.join(", ") || "—"}</p><p className="small muted">{sel.conditions?.join(" · ") || ""}</p></div>
          <div><h3>Integration in SpaceXtinsafe</h3>
            <ul className="small">
              <li>Original PSI files acquired: {sel.psi_files_acquired ?? 0}</li>
              <li>Records used in analysis: {sel.integrated_measurements ?? 0}</li>
              <li>Experimental-test nodes in the knowledge graph: {sel.graph_test_nodes ?? 0}</li>
              <li>Curated findings: {sel.curated_findings} {sel.finding_ids?.length ? <span className="mono faint">({sel.finding_ids.join(", ")})</span> : null}</li>
              <li>Predictive models: {sel.models?.length ? sel.models.join(", ") : "none"}</li>
              <li>Audit items: {sel.audit_items ?? 0}</li>
              <li>Supports: {sel.features?.join(", ") || "reference only"}</li></ul>
            <h3>Limitations</h3><ul className="small">{arr(sel.limitations).map((l: string) => <li key={l}>{l}</li>)}</ul>
            <div className="row">{sel.record_url && <a className="btn sm" href={sel.record_url} target="_blank" rel="noreferrer">NASA PSI record</a>}{sel.doi && <a className="btn sm" href={`https://doi.org/${sel.doi}`} target="_blank" rel="noreferrer">DOI {sel.doi}</a>}
              {(sel.sources || []).map((s: any) => <a key={s.id} className="btn sm" href={s.url} target="_blank" rel="noreferrer">{s.identifier}</a>)}
              {sel.finding_ids?.length > 0 && <button className="btn sm pri" onClick={() => { patch({ question: `What did ${sel.acronym} find?` }); go("library"); }}>Open its findings</button>}</div></div>
        </div></div>}
      <div className="card" style={{ marginTop: 14 }}><h2>How NASA investigations power SpaceXtinsafe</h2><p className="small muted">Lines are drawn only where the backend reports integrated data or verified findings for that feature.</p>
        {invs.data && <FeatureMap invs={invs.data} />}</div>
      <div className="card"><h2>Original NASA datasets and provenance</h2>
        {ds.loading ? <Loading /> : !ds.data?.length ? <Empty>No datasets.</Empty> : <div className="scroll"><table><thead><tr><th>Dataset</th><th>Investigation</th><th>Original file</th><th>Integrity</th><th>Rows used / in file</th><th>Used for</th><th>Transformations</th><th>Limitations</th></tr></thead>
          <tbody>{ds.data.map((d: any) => <tr key={d.accession}><td><a href={d.record_url} target="_blank" rel="noreferrer">{d.accession}</a><div className="mono faint">DOI {d.doi || "—"}</div></td><td>{d.investigation}</td>
            <td className="small">{d.filename}<div className="mono faint" title={d.sha256}>sha256 {d.sha256?.slice(0, 12)}… · {d.acquired}</div></td>
            <td><span className={`pill ${d.integrity?.startsWith("SHA-256 matches") ? "ok" : "warn"}`}>{d.integrity}</span></td><td>{d.records_used} / {d.rows_in_file}</td>
            <td className="small"><span className={`pill ${/not yet/i.test(d.usage_status || "") ? "warn" : "ok"}`}>{d.usage_status}</span><div className="muted">{arr(d.features).join(", ")}</div></td><td className="small muted">{arr(d.transformations).join("; ")}</td><td className="small muted">{arr(d.limitations).join("; ")}</td></tr>)}</tbody></table></div>}</div>
      {use.data && <div className="card"><h2>NASA data usage statement</h2>
        <div className="grid g2 small">
          <div><b>Datasets used:</b> {use.data.datasets_used.join(", ")}<br /><b>Acquired, not yet analysed:</b> {use.data.datasets_acquired_not_used.join(", ") || "none"}
            <h3 style={{ marginTop: 10 }}>Analyses performed</h3><ul>{use.data.analyses.map((a: string) => <li key={a}>{a}</li>)}</ul></div>
          <div><h3>Models trained</h3><ul>{use.data.models.map((m: any) => <li key={m.id}>{m.id}: {m.status} (n={m.n})</li>)}</ul>
            <p>{use.data.findings} curated findings from {use.data.sources} sources.</p>
            <h3>Conceptual or exploratory only</h3><ul>{use.data.conceptual.map((a: string) => <li key={a}>{a}</li>)}</ul></div></div></div>}
    </div>
  );
}
