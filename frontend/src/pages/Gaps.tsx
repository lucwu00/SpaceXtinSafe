import { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import { Page, useAsync, Loading, Outcome, fmt } from "../ui";

const KIND_BG: Record<string, string> = { "Direct experimental evidence": "rgba(78,161,255,.55)", "Includes conflicting evidence": "rgba(180,140,255,.55)", "No finding in this library": "transparent" };
const DIMS: [string, string][] = [["overview", "Material × condition"], ["gravity", "Gravity"], ["oxygen", "Oxygen"], ["pressure", "Pressure"], ["airflow", "Airflow"], ["form", "Material form"], ["material", "Material × material"], ["compartment", "Compartments"]];

function Legend() {
  return <div className="row small" style={{ marginTop: 8 }}>
    <span className="row"><span className="dot" style={{ background: KIND_BG["Direct experimental evidence"] }} />Direct experimental evidence</span>
    <span className="row"><span className="dot" style={{ background: KIND_BG["Includes conflicting evidence"] }} />Includes conflicting evidence</span>
    <span className="row"><span className="dot" style={{ border: "1px dashed var(--faint)" }} />No finding in this library</span>
    <span className="row"><b style={{ color: "var(--ok)" }}>M</b> model-supported estimate possible</span><span className="row"><b style={{ color: "var(--model)" }}>E</b> exploratory estimate only</span></div>;
}

export function Gaps() {
  const { sc, go, patch } = useApp();
  const [scope, setScope] = useState<"sc" | "all">("sc");
  const [dim, setDim] = useState("overview");
  const sid = scope === "sc" ? sc?.id : undefined;
  const g = useAsync(() => (dim === "overview" ? api.gaps(sid) : api.gapsDim(dim, dim === "compartment" ? sc?.id : sid)), [dim, scope, sc?.id]);
  const [cell, setCell] = useState<any>(null);
  const d = g.data;
  return (
    <Page title="Research gap explorer" intro="Where NASA evidence exists in this library and where it is missing, by gravity, oxygen, pressure, airflow, material form, material pairs and compartments. An empty cell is a gap in SpaceXtinSafe's curated library; it is not proof of a gap in the wider literature, and never evidence that a material is safe."
      simple="Empty squares show combinations NASA research in this tool has not covered yet."
      actions={<div className="row"><button className={`btn sm ${scope === "sc" ? "pri" : ""}`} onClick={() => setScope("sc")}>Materials on {sc?.name}</button><button className={`btn sm ${scope === "all" ? "pri" : ""}`} onClick={() => setScope("all")}>Whole catalogue</button></div>}>
      <div className="tabs">{DIMS.map(([k, l]) => <button key={k} className={`tab ${dim === k ? "on" : ""}`} onClick={() => { setDim(k); setCell(null); }}>{l}</button>)}</div>
      {g.loading || !d || (dim === "overview" ? !d.conditions : d.dimension !== dim) ? <Loading /> : <>
        {dim === "overview" && <div className="card"><div style={{ overflowX: "auto" }}><table className="heat"><thead><tr><th>Material</th>{d.conditions.map((c: string) => <th key={c} style={{ textAlign: "center" }}>{c}</th>)}</tr></thead>
          <tbody>{d.materials.map((m: string) => <tr key={m}><td style={{ textAlign: "left", fontFamily: "inherit" }}>{m}</td>{d.conditions.map((c: string) => { const x = d.cells.find((y: any) => y.material === m && y.condition === c);
            return <td key={c} onClick={() => setCell(x)} style={{ cursor: "pointer", background: x.count ? `rgba(78,161,255,${0.2 + 0.15 * Math.min(4, x.count)})` : "transparent", outline: x.count ? "" : "1px dashed var(--line)" }}>{x.count || ""}</td>; })}</tr>)}</tbody></table></div>
          {cell && <div className="banner info" style={{ marginTop: 10 }}><b>{cell.material} · {cell.condition}:</b> {cell.count ? `${cell.count} finding(s): ${cell.evidence_ids.join(", ")}` : "no finding in this library."}</div>}
          <p className="small faint">{d.note}</p>
          <h3 style={{ marginTop: 12 }}>FLEX droplet tests by O₂ and pressure (original PSI-69 rows)</h3>
          <div className="grid g2">{["methanol", "n-heptane"].map((fuel) => { const o2s = [...new Set(d.flex_coverage.map((c: any) => c.o2_pct))] as number[]; const mx = Math.max(...d.flex_coverage.map((c: any) => c.tests));
            return <div key={fuel}><div className="small muted">{fuel}</div><table className="heat"><thead><tr><th>O₂ %</th>{o2s.map((o) => <th key={o}>{o}</th>)}</tr></thead><tbody>{["101.3 kPa", "70.9 kPa"].map((p) => <tr key={p}><td style={{ fontFamily: "inherit" }}>{p}</td>
              {o2s.map((o) => { const x = d.flex_coverage.find((y: any) => y.fuel === fuel && y.o2_pct === o && y.pressure === p); return <td key={o} style={{ background: x.tests ? `rgba(255,138,61,${0.15 + 0.6 * x.tests / mx})` : "transparent", outline: x.tests ? "" : "1px dashed var(--line)" }}>{x.tests || ""}</td>; })}</tr>)}</tbody></table></div>; })}</div></div>}
        {["gravity", "oxygen", "pressure", "airflow"].includes(dim) && <div className="card"><div style={{ overflowX: "auto" }}><table className="heat"><thead><tr><th>Material</th>{d.bands.map((b: string) => <th key={b} style={{ textAlign: "center" }}>{b}</th>)}</tr></thead>
          <tbody>{d.materials.map((m: string) => <tr key={m}><td style={{ textAlign: "left", fontFamily: "inherit" }}>{m}</td>{d.bands.map((b: string) => { const x = d.cells.find((y: any) => y.material === m && y.band === b);
            return <td key={b} onClick={() => setCell(x)} style={{ cursor: "pointer", background: KIND_BG[x.kind], outline: x.count ? "" : "1px dashed var(--line)" }} title={x.kind}>
              {x.count || ""}{x.model && <b style={{ color: x.model.startsWith("Model") ? "var(--ok)" : "var(--model)", marginLeft: 3 }}>{x.model.startsWith("Model") ? "M" : "E"}</b>}</td>; })}</tr>)}</tbody></table></div>
          <Legend />
          {cell && <div className="banner info" style={{ marginTop: 10 }}><b>{cell.material} · {cell.band}:</b> {cell.kind}{cell.ids.length ? ` (${cell.ids.join(", ")})` : ""}.{cell.model ? ` ${cell.model} from the FLEX models (check eligibility in the Workspace).` : ""}
            {!cell.count && <> {d.needed} <button className="btn sm" onClick={() => { patch({ material_id: cell.material_id }); go("firelab"); }}>Open in Fire Lab</button></>}</div>}
          <p className="small faint">{d.note}</p></div>}
        {dim === "form" && <div className="card"><table><thead><tr><th>Material</th><th>Form tested</th><th>Outcome studied</th><th>Finding</th></tr></thead><tbody>
          {d.cells.map((c: any, i: number) => <tr key={i}><td>{c.material}</td><td>{c.form}</td><td className="small">{c.outcome}</td><td className="mono">{c.id}</td></tr>)}</tbody></table>
          <p className="small faint">Only forms that NASA actually tested appear. A material used in another form (for example a foam instead of a sheet) is not covered by these findings.</p></div>}
        {dim === "material" && <div className="card"><table><thead><tr><th>Pair</th><th>Status</th><th>Findings</th></tr></thead><tbody>
          {d.cells.map((c: any, i: number) => <tr key={i}><td>{c.a} + {c.b}</td><td><span className={`pill ${c.status.startsWith("Documented") ? "ok" : "acc"}`}>{c.status}</span></td><td className="mono">{c.ids.join(", ")}</td></tr>)}</tbody></table>
          <p className="small faint">{d.pairs_checked} pairs checked. {d.note}</p></div>}
        {dim === "compartment" && <div className="card">{d.rows.map((r: any) => <div key={r.id} style={{ marginBottom: 10 }}>
          <div className="row between small"><b>{r.compartment}</b><span className="muted">{r.components} components</span></div>
          <div style={{ display: "flex", height: 12, borderRadius: 4, overflow: "hidden", background: "var(--panel2)" }}>{d.statuses.map((s: string, i: number) => { const n = r.status_counts[s] || 0; return n ? <div key={s} title={`${s}: ${n}`} style={{ width: `${100 * n / r.components}%`, background: ["#4ea1ff", "#7c9cff", "#b48cff", "#64748b", "#334155", "#1e293b"][i] }} /> : null; })}</div></div>)}
          <div className="row small">{d.statuses.map((s: string, i: number) => <span key={s} className="row"><span className="dot" style={{ background: ["#4ea1ff", "#7c9cff", "#b48cff", "#64748b", "#334155", "#1e293b"][i] }} />{s}</span>)}</div></div>}
      </>}
    </Page>
  );
}

function ConditionCompare() {
  const { scenario, materials, setCtx } = useApp();
  const [mid, setMid] = useState(scenario.material_id || "MAT-SIBAL");
  const [form, setForm] = useState(scenario.form || "");
  const [d0, setD0] = useState<number | "">(scenario.d0_mm ?? 2.5);
  const [rows, setRows] = useState<any[]>([
    { label: "Orbital cabin air", o2_pct: 21, pressure_kpa: 101.3, gravity: "microgravity", flow_cm_s: 15, diluent: "nitrogen" },
    { label: "Exploration atmosphere, lunar", o2_pct: 34, pressure_kpa: 56.5, gravity: "partial gravity", flow_cm_s: 10, diluent: "nitrogen" }]);
  const [res, setRes] = useState<any>(null);
  const run = async () => setRes(await api.compareConditions({ material_id: mid, form: form || undefined, d0_mm: d0 === "" ? undefined : d0, scenarios: rows }));
  const up = (i: number, k: string, v: any) => setRows((r) => r.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <div>
      <div className="card"><div className="row">
        <label className="label">Material<select value={mid} onChange={(e) => setMid(e.target.value)}>{materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        <label className="label">Form<input value={form} onChange={(e) => setForm(e.target.value)} placeholder="e.g. liquid droplet" /></label>
        <label className="label">Droplet D0 mm (fuels)<input type="number" value={d0} onChange={(e) => setD0(e.target.value === "" ? "" : +e.target.value)} /></label>
        <button className="btn" onClick={() => setRows([...rows, { label: `Scenario ${rows.length + 1}`, o2_pct: 21, pressure_kpa: 101.3, gravity: "microgravity", flow_cm_s: 0, diluent: "nitrogen" }])} disabled={rows.length >= 4}>+ Scenario</button>
        <button className="btn pri" onClick={() => { run(); setCtx({}); }}>Compare</button></div>
        <div className="scroll" style={{ marginTop: 10 }}><table><thead><tr><th>Label</th><th>O₂ %</th><th>Pressure kPa</th><th>Gravity</th><th>Flow cm/s</th><th>Diluent</th><th /></tr></thead><tbody>{rows.map((r, i) => <tr key={i}>
          <td><input value={r.label} onChange={(e) => up(i, "label", e.target.value)} /></td><td><input type="number" style={{ width: 70 }} value={r.o2_pct} onChange={(e) => up(i, "o2_pct", +e.target.value)} /></td>
          <td><input type="number" style={{ width: 80 }} value={r.pressure_kpa} onChange={(e) => up(i, "pressure_kpa", +e.target.value)} /></td>
          <td><select value={r.gravity} onChange={(e) => up(i, "gravity", e.target.value)}>{["microgravity", "partial gravity", "1-g"].map((g) => <option key={g}>{g}</option>)}</select></td>
          <td><input type="number" style={{ width: 70 }} value={r.flow_cm_s} onChange={(e) => up(i, "flow_cm_s", +e.target.value)} /></td>
          <td><select value={r.diluent} onChange={(e) => up(i, "diluent", e.target.value)}>{["nitrogen", "carbon dioxide", "helium"].map((g) => <option key={g}>{g}</option>)}</select></td>
          <td><button className="btn sm" onClick={() => setRows(rows.filter((_, j) => j !== i))} disabled={rows.length <= 2}>✕</button></td></tr>)}</tbody></table></div></div>
      {res && <><div className={`grid g${Math.min(4, res.scenarios.length)}`}>{res.scenarios.map((s: any) => <div key={s.label} className="card">
        <h3>{s.label}</h3><div className="small muted">{s.conditions.o2_pct}% O₂ · {s.conditions.pressure_kpa} kPa · {s.conditions.gravity} · {s.conditions.flow_cm_s} cm/s</div>
        <div className="kpi" style={{ margin: "8px 0" }}><b>{fmt(s.o2_partial_pressure_kpa, 1)} kPa</b><span>O₂ partial pressure (reference only)</span></div>
        {Object.entries(s.tier_counts).map(([t, n]: any) => <div key={t} className="row between small"><span>{t}</span><b>{n}</b></div>)}
        {!Object.keys(s.tier_counts).length && <div className="small faint">No finding for this material applies.</div>}
        {s.prediction && <div style={{ marginTop: 6 }}><Outcome o={s.prediction.outcome} />{s.prediction.estimate != null && <b> {fmt(s.prediction.estimate)} mm²/s</b>}<div className="small muted">{s.prediction.reasons?.join("; ")}</div></div>}
        <ul className="small" style={{ paddingLeft: 16 }}>{s.top.map((t: any) => <li key={t.id}>{t.statement} <span className="mono faint">[{t.id}]</span></li>)}</ul></div>)}</div>
        <div className="banner info">{res.note}</div></>}
    </div>
  );
}

export function Compare() {
  const { list, sc, setCtx } = useApp();
  const [tab, setTab] = useState("configs");
  const [ids, setIds] = useState<string[]>(() => [sc?.id, list.find((s) => s.id !== sc?.id)?.id].filter(Boolean) as string[]);
  const r = useAsync(() => { setCtx({ compare_ids: ids }); return ids.length >= 2 ? api.compare(ids) : Promise.resolve(null); }, [ids.join()]);
  const statuses = ["Applicable evidence identified", "Partially applicable evidence", "Related (indirect) evidence only", "Contextual evidence only", "No NASA evidence in library (research gap)"];
  const col = ["#4ea1ff", "#7c9cff", "#b48cff", "#94a3b8", "transparent"];
  return (
    <Page title="Compare scenarios" intro="Compare spacecraft configurations (evidence coverage of their materials) or one material under different oxygen, pressure, gravity, airflow and diluent conditions. This compares research coverage and model eligibility, never safety."
      simple="Put two spacecraft, or two environments, side by side to see where NASA research applies.">
      <div className="tabs">{[["configs", "Spacecraft configurations"], ["conditions", "Conditions for one material"]].map(([k, l]) => <button key={k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "conditions" ? <ConditionCompare /> : <>
        <div className="card tight row">{[0, 1, 2].map((i) => <select key={i} value={ids[i] || ""} onChange={(e) => { const n = [...ids]; n[i] = e.target.value; setIds(n.filter(Boolean)); }} aria-label={`Configuration ${i + 1}`}>
          <option value="">{i < 2 ? "Select…" : "(optional third)"}</option>{list.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>)}</div>
        {r.loading ? <Loading /> : r.data && <div className={`grid g${r.data.configurations.length}`}>{r.data.configurations.map((c: any) => (
          <div key={c.id} className="card"><h2>{c.name}</h2>
            <div className="row"><span className="pill acc">{c.atmosphere.o2_pct}% O₂</span><span className="pill acc">{c.atmosphere.pressure_kpa} kPa</span><span className="pill">{c.atmosphere.gravity}</span><span className="pill">pO₂ {fmt(c.atmosphere.o2_pct / 100 * c.atmosphere.pressure_kpa, 1)} kPa</span></div>
            <div style={{ margin: "12px 0" }}>{statuses.map((s, i) => { const n = c.status_counts[s] || 0; return <div key={s} className="small" style={{ marginBottom: 6 }}>
              <div className="row between"><span>{s}</span><b>{n}</b></div><div style={{ height: 6, background: "var(--panel2)", borderRadius: 3, outline: i === 4 ? "1px dashed var(--line)" : "" }}><div style={{ width: `${(100 * n) / Math.max(1, c.components)}%`, height: 6, borderRadius: 3, background: i === 4 ? "repeating-linear-gradient(45deg,#64748b 0 3px,transparent 3px 6px)" : col[i] }} /></div></div>; })}</div>
            <div className="small"><b>{c.components}</b> components · {c.materials.length} materials</div>
            <div className="small muted" style={{ marginTop: 6 }}>Materials without NASA evidence here: {c.gap_materials.join(", ") || "none"}</div>
            {c.atmosphere.o2_pct > 23 && <div className="banner" style={{ marginTop: 8 }}>Elevated oxygen ({c.atmosphere.o2_pct}%): most findings were obtained near 21% O₂, so they apply only partially.</div>}
          </div>))}</div>}
        {r.data && <p className="small faint">{r.data.note}</p>}</>}
    </Page>
  );
}
