import { api } from "../api";
import { useApp } from "../state";
import { Page, useAsync, Loading } from "../ui";
import { DEMO_STEPS } from "../Demo";

const CAPS: [string, string, string][] = [
  ["twin", "Digital twin", "Cutaway of the configured spacecraft with evidence, gap, conflict, interaction and sensor overlays."],
  ["graph", "Knowledge graphs", "Spacecraft and science graphs joined through materials: object → material → finding → source."],
  ["workspace", "Mission Workspace", "Any question or condition set, with retrieval, applicability ranking and Fire Safety Insights."],
  ["firelab", "Virtual Fire Lab", "Material intelligence, documented interactions and FLEX droplet models with uncertainty."],
  ["audit", "Evidence audit", "Every FLEX row checked against the NASA report; Saffire tables against NTRS. Conflicts shown, not hidden."],
  ["gaps", "Research gaps", "Where NASA evidence is missing by gravity, oxygen, pressure, airflow, form and material pairs."],
  ["incidents", "Incident intelligence", "Simulated, vehicle-aware replays across mission phases. No emergency instructions."],
  ["evaluation", "AI Evaluation Centre", "Retrieval, GraphRAG, copilot and eligibility results computed from executed runs."],
];

export function Overview() {
  const { sc, go, status, setDemo } = useApp();
  const use = useAsync(() => api.nasaUsage(), []);
  const audit = useAsync(() => api.audit(), []);
  const invs = useAsync(() => api.investigations(), []);
  const screen = useAsync(() => (sc ? api.screen(sc.id) : Promise.resolve(null)), [sc?.id, JSON.stringify(sc?.compartments)]);
  const rows = screen.data?.rows || [];
  const gapsN = rows.filter((r: any) => r.status.startsWith("No NASA")).length;
  return (
    <Page title="SpaceXtinSafe" intro="From Research to Readiness. A knowledge-driven spacecraft digital twin that turns NASA microgravity combustion research into vehicle-aware scientific intelligence for design investigations, material understanding, evidence-based prediction, research discovery and emergency preparedness."
      simple="See what NASA fire experiments in space say about the things inside a spacecraft, and where we still don't know."
      actions={<button className="btn pri" onClick={() => setDemo(0)}>▶ Start guided demo ({DEMO_STEPS} steps)</button>}>
      <div className="grid g2">
        <div className="card"><h2>Why spacecraft fire research matters</h2>
          <p className="small">In microgravity there is no buoyant flow: flames are shaped by ventilation and diffusion, so materials can burn, spread or self-extinguish differently from Earth. Ground screening tests run in 1 g, and NASA notes that designers have had to rely on 1-g understanding of flame spread, detection and suppression.</p>
          <p className="small">NASA's ISS and Cygnus experiments (FLEX, BASS, Saffire, SoFIE and others) produced the data to close that gap, but it is spread across datasets, reports and presentations. SpaceXtinSafe connects it to the objects aboard a specific spacecraft.</p>
          <div className="small faint">Source for the 1-g statement: Saffire VI, ICES-2024-365 (EV-SAF6-04).</div></div>
        <div className="card"><h2>Powered by NASA data</h2>
          {!use.data ? <Loading /> : <div className="grid g2">
            <div className="kpi"><b>{use.data.datasets_used.length}</b><span>original PSI datasets analysed ({use.data.datasets_used.join(", ")})</span></div>
            <div className="kpi"><b>{status?.data?.flex_tests ?? "—"}</b><span>FLEX droplet tests in the models and audit</span></div>
            <div className="kpi"><b>{use.data.findings}</b><span>curated findings, quotes verified against {use.data.sources} sources</span></div>
            <div className="kpi"><b>{invs.data?.length ?? "—"}</b><span>NASA investigations in the coverage dashboard</span></div></div>}
          <div className="row" style={{ marginTop: 8 }}><button className="btn sm" onClick={() => { (window as any).__libTab = "nasa"; go("library"); }}>Open NASA investigation coverage</button>
            {audit.data && <span className="pill">{audit.data.counts?.["Confirmed discrepancy"] ?? 0} confirmed source discrepancies</span>}</div></div>
      </div>
      <div className="card"><div className="row between"><h2>Active spacecraft: {sc?.name || "…"}</h2><div className="row"><button className="btn sm" onClick={() => go("twin")}>Open digital twin</button><button className="btn sm" onClick={() => go("studio")}>Edit configuration</button></div></div>
        {sc && <><div className="small muted">{sc.vehicle_class} · {sc.origin} · illustrative configuration, not a certified vehicle design</div>
          <div className="row" style={{ marginTop: 8 }}><span className="pill acc">{sc.atmosphere.o2_pct}% O₂</span><span className="pill acc">{sc.atmosphere.pressure_kpa} kPa</span><span className="pill acc">{sc.atmosphere.gravity}</span><span className="pill">ventilation {sc.atmosphere.ventilation_cm_s} cm/s</span></div>
          <div className="grid g4" style={{ marginTop: 10 }}>
            <div className="kpi"><b>{sc.compartments.length}</b><span>compartments</span></div><div className="kpi"><b>{sc.compartments.reduce((n: number, c: any) => n + c.objects.length, 0)}</b><span>objects</span></div>
            <div className="kpi"><b>{rows.length || "…"}</b><span>components</span></div><div className="kpi"><b>{screen.data ? gapsN : "…"}</b><span>components with no NASA evidence in the library</span></div></div></>}</div>
      <div className="card"><h2>Capabilities</h2><div className="grid g4">{CAPS.map(([p, t, d]) => <button key={p} className="kpi" style={{ textAlign: "left", cursor: "pointer", color: "inherit" }} onClick={() => go(p)}><b style={{ fontSize: 15 }}>{t}</b><span>{d}</span></button>)}</div></div>
      <div className="card"><h2>Scientific limits</h2>
        <div className="grid g4 small">
          <div><b>No verdicts.</b> Evidence status describes research coverage, never a flammability rating, qualification or "safe/unsafe" call.</div>
          <div><b>Estimates only in-domain.</b> Only FLEX droplet models exist; estimates need matching fuel, form, diluent, gravity, pressure band and joint O₂–diameter support.</div>
          <div><b>No emergency instructions.</b> Incident replays are simulated and point to authorised vehicle procedures.</div>
          <div><b>A prototype.</b> Independent research and education tool; not NASA-endorsed and not a physical fire simulation.</div></div></div>
    </Page>
  );
}
