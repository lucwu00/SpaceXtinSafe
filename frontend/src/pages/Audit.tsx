import { useState } from "react";
import { api } from "../api";
import { Page, useAsync, Loading } from "../ui";

const ST: Record<string, string> = { "Confirmed discrepancy": "bad", "Potential discrepancy": "warn", "Missing information": "" };

export function Audit() {
  const a = useAsync(() => api.audit(), []);
  const src = useAsync(() => api.sources(), []);
  const [st, setSt] = useState(""); const [inv, setInv] = useState("");
  const [sel, setSel] = useState<any>(null);
  if (a.loading || !a.data) return <Loading />;
  const items = a.data.items.filter((i: any) => (!st || i.status === st) && (!inv || i.investigation === inv));
  const S = (id: string) => src.data?.find((s: any) => s.id === id);
  const dl = () => { const b = new Blob([JSON.stringify(a.data, null, 1)], { type: "application/json" }); const u = URL.createObjectURL(b); const l = document.createElement("a"); l.href = u; l.download = "spacextinsafe_audit.json"; l.click(); };
  return (
    <Page title="Scientific evidence audit" intro="Automated cross-checks of the original NASA files: all 274 PSI-69 FLEX rows against NASA/TP-2015-216046 Table IX (11 fields each), and the Saffire PSI tables against NTRS 20180005168 Table 1. Nothing is corrected silently. Confirmed discrepancies affecting model inputs are excluded from fitting."
      simple="We compared NASA's data tables with NASA's published reports. Where they disagree, we show both values and don't pick one."
      actions={<div className="row"><a className="btn" href={api.auditCsvUrl()}>Download CSV</a><button className="btn" onClick={dl}>Download JSON</button></div>}>
      <div className="grid g4">{["Confirmed discrepancy", "Potential discrepancy", "Missing information"].map((k) => (
        <button key={k} className={`kpi ${st === k ? "on" : ""}`} style={{ textAlign: "left", cursor: "pointer", color: "inherit", borderColor: st === k ? "var(--acc)" : undefined }} onClick={() => setSt(st === k ? "" : k)}>
          <b>{a.data.counts[k] || 0}</b><span>{k}</span></button>))}
        <div className="kpi"><b>{a.data.flex_rows_compared}</b><span>FLEX rows compared field by field</span></div></div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1.2fr)", marginTop: 14 }}>
        <div className="card"><div className="row between"><h2>Audit items ({items.length})</h2>
          <select value={inv} onChange={(e) => setInv(e.target.value)}><option value="">All</option>{[...new Set(a.data.items.map((i: any) => i.investigation))].map((i: any) => <option key={i}>{i}</option>)}</select></div>
          <div className="scroll"><table><tbody>{items.map((i: any) => (
            <tr key={i.id} className={`click ${sel?.id === i.id ? "sel" : ""}`} onClick={() => setSel(i)}><td><span className={`pill ${ST[i.status]}`}>{i.status}</span></td><td><b className="small">{i.quantity}</b><div className="small muted">{i.investigation} · {i.test}</div></td></tr>))}</tbody></table></div></div>
        <div className="card">{!sel ? <div className="empty">Select an item for the side-by-side comparison.</div> : <>
          <div className="row between"><h2>{sel.quantity}</h2><span className={`pill ${ST[sel.status]}`}>{sel.status}{sel.resolution ? ` · ${sel.resolution}` : ""}</span></div>
          <div className="mono faint">{sel.id}</div><div className="small muted">{sel.investigation} · {sel.test}</div>
          <div className="grid g2" style={{ marginTop: 10 }}>{sel.values.map((v: any, k: number) => (
            <div key={k} className="kpi"><span>{S(v.source_id)?.type || v.source_id}</span><b className="mono" style={{ fontSize: 20 }}>{String(v.raw ?? "(blank)")}{sel.unit ? <span className="small muted"> {sel.unit}</span> : null}</b>
              <div className="small">{v.location}</div>{S(v.source_id) && <a className="small" href={S(v.source_id).url} target="_blank" rel="noreferrer">{S(v.source_id).identifier}</a>}</div>))}</div>
          {sel.normalised && <p className="small"><b>Normalised:</b> {sel.normalised}</p>}
          <p className="small"><b>Affected findings / models:</b> {sel.affected?.length ? sel.affected.join(", ") : "none"}</p>
          <p className="small"><b>Modelling decision:</b> {sel.modelling || "—"}</p>
          <p className="small"><b>Unresolved question:</b> {sel.unresolved_question || "none"}</p>
          {sel.detail && <details><summary className="small muted">{sel.detail.length} renumbered tests</summary><div className="mono small">{sel.detail.map((d: any) => `${d.identifier}: PSI #${d.psi_test} = TP FLEX-${d.tp_test}`).join(" · ")}</div></details>}
        </>}</div>
      </div>
      <details className="card"><summary className="small muted">Method and classification rules</summary><pre className="small" style={{ whiteSpace: "pre-wrap" }}>{a.data.method}</pre></details>
    </Page>
  );
}
