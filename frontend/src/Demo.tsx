import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useApp } from "./state";

type Step = { title: string; page: string; text: string; run?: (a: ReturnType<typeof useApp>) => Promise<void> | void };

// Every step drives the real application: navigation, shared scenario changes and live backend calls. Nothing is pre-recorded.
const STEPS: Step[] = [
  { title: "What SpaceXtinsafe does", page: "overview", text: "SpaceXtinsafe links a spacecraft's compartments, objects and materials to original NASA microgravity combustion data, shows how far each finding applies, audits the sources, and gives estimates only where the data supports them." },
  { title: "Select a spacecraft template", page: "studio", text: "Quick Start loads an illustrative template. The demo uses the Orbital Research Module (generic, not a real vehicle).", run: (a) => a.setScId("SC-ORBITAL") },
  { title: "Explore the digital twin", page: "twin", text: "The cutaway shows each compartment. Overlays switch between material distribution, evidence coverage, research gaps, conflicts, interactions and sensors." },
  { title: "Select a compartment", page: "twin", text: "The Crew quarters is selected. The panel lists its objects, materials, linked NASA investigations and gaps.", run: (a) => a.patch({ compartment_id: "C-CREW" }) },
  { title: "Inspect an object and its materials", page: "twin", text: "The Sleeping bag decomposes into components: shell fabric (Nomex) and padding (polyurethane foam). The object is not assumed to behave like any one material.", run: (a) => a.patch({ compartment_id: "C-CREW", object_id: "O-BAG", material_id: "MAT-NOMEX", form: "fabric" }) },
  { title: "Modify a condition", page: "workspace", text: "The cabin oxygen is raised to 30% in the shared scenario. Every module now uses the new value, and applicability is recalculated.", run: (a) => a.patch({ o2_pct: 30, pressure_kpa: a.sc?.atmosphere?.pressure_kpa ?? 101.3, gravity: a.sc?.atmosphere?.gravity ?? "microgravity" }) },
  { title: "Traverse the knowledge graphs", page: "graph", text: "From the Sleeping bag, the graph walks object → component → material → NASA finding → investigation → source. The panel lists each multi-hop trace." },
  { title: "Retrieve NASA evidence", page: "workspace", text: "Press Analyse with the suggested question about the Sleeping bag. Retrieval combines keyword, semantic and graph search; the mode actually used is shown.", run: (a) => a.patch({ question: "Which findings are relevant to the Sleeping bag in the Orbital Research Module?" }) },
  { title: "Explain applicability", page: "workspace", text: "Open 'Why this rank?' on a finding: each factor (material, form, gravity, oxygen, pressure, flow) is shown as a match, partial, mismatch or not reported. Not-reported factors never count as matches." },
  { title: "An eligible prediction", page: "firelab", text: "Methanol droplet, 21% O₂, 101.3 kPa, 2.5 mm, nitrogen, microgravity: inside the tested domain, so the backend returns a model-supported estimate with a 90% empirical band.",
    run: async (a) => { a.setCtx({ fireTab: "droplet" }); a.patch({ material_id: "MAT-METHANOL", form: "liquid droplet", o2_pct: 21, pressure_kpa: 101.3, d0_mm: 2.5, diluent: "nitrogen", gravity: "microgravity" });
      a.setPrediction(await api.predict({ material_form: "liquid droplet", fuel: "methanol", o2_pct: 21, pressure_kpa: 101.3, d0_mm: 2.5, diluent: "nitrogen", gravity: "microgravity" })); } },
  { title: "An unsupported prediction is rejected", page: "firelab", text: "30% O₂ with a 1.7 mm droplet sits inside each separate tested range, but no test is near that combination. The joint-support checks reject it, and the reasons are listed.",
    run: async (a) => { a.setCtx({ fireTab: "droplet" }); a.patch({ o2_pct: 30, d0_mm: 1.7 }); a.setPrediction(await api.predict({ material_form: "liquid droplet", fuel: "methanol", o2_pct: 30, pressure_kpa: 101.3, d0_mm: 1.7, diluent: "nitrogen", gravity: "microgravity" })); } },
  { title: "Investigate a source discrepancy", page: "audit", text: "FLEX test 193F001: the PSI table gives K = 0.41 mm²/s, the NASA technical report 0.56. Both values are shown side by side and the test is excluded from model fitting." },
  { title: "Documented material interactions", page: "firelab", text: "Level 2: Saffire-II's combined PMMA and Nomex sample. The PMMA burned; the adjoining Nomex did not ignite in that test. Other pairs show as missing evidence, never as 'safe'.", run: (a) => { a.setCtx({ fireTab: "l2" }); a.patch({ material_id: "MAT-PMMA" }); } },
  { title: "Compare scenarios", page: "compare", text: "Compare configurations side by side, or one material under cabin air vs the 34% O₂ / 56.5 kPa exploration atmosphere. O₂ partial pressure is shown, but equal partial pressures are not treated as equivalent." },
  { title: "Identify a research gap", page: "gaps", text: "Dashed cells are combinations with no finding in this library, for example most materials in partial gravity. A gap in this library is not proof of a gap in all literature." },
  { title: "Replay a simulated incident", page: "incidents", text: "Choose a phase and compartment and press Replay. The timeline is labelled SIMULATED, candidate components are unconfirmed, and the tool refers to authorised procedures without giving instructions.", run: (a) => a.patch({ compartment_id: "C-CREW" }) },
  { title: "Generate the mission evidence report", page: "reports", text: "Generate PDF builds a report from your actual configuration, scenario, prediction, interaction, comparison and incident, with methodology, sources and the AI disclosure." },
  { title: "The actual AI evaluation results", page: "evaluation", text: "Retrieval on the development and holdout sets, the effect of the graph per question, copilot cases, eligibility tests and model cards, all computed from executed runs. Exit the demo to explore freely." },
];
export const DEMO_STEPS = STEPS.length;

export function DemoBar() {
  const app = useApp();
  const { demo, setDemo, go } = app;
  const [auto, setAuto] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ran = useRef<number | null>(null);
  useEffect(() => {
    if (demo === null) return;
    const s = STEPS[demo]; go(s.page);
    if (ran.current !== demo) { ran.current = demo; setErr(null); Promise.resolve(s.run?.(app)).catch((e) => setErr(`Live call failed: ${e.message}. The fallback state is shown.`)); }
  }, [demo]);
  useEffect(() => {
    if (!auto || demo === null) return;
    if (demo >= STEPS.length - 1) { setAuto(false); return; }
    const t = setTimeout(() => setDemo(demo + 1), 9000); return () => clearTimeout(t);
  }, [auto, demo]);
  useEffect(() => {
    if (demo === null) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setDemo(null); if (e.key === "ArrowRight" && e.altKey) setDemo(Math.min(STEPS.length - 1, demo + 1)); if (e.key === "ArrowLeft" && e.altKey) setDemo(Math.max(0, demo - 1)); };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, [demo]);
  if (demo === null) return null;
  const s = STEPS[demo];
  return (
    <div className="demobar" role="region" aria-label="Guided demo">
      <div className="demo-progress"><div style={{ width: `${(100 * (demo + 1)) / STEPS.length}%` }} /></div>
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div style={{ minWidth: 0, flex: 1 }}><div className="small muted">Guided demo · step {demo + 1} of {STEPS.length}</div><b>{s.title}</b><div className="small">{s.text}</div>{err && <div className="small" style={{ color: "var(--warn)" }}>{err}</div>}</div>
        <div className="row">
          <button className="btn sm" onClick={() => setDemo(Math.max(0, demo - 1))} disabled={demo === 0}>Previous</button>
          <button className="btn sm" onClick={() => setAuto(!auto)}>{auto ? "Pause" : "Auto-play"}</button>
          <button className="btn sm pri" onClick={() => setDemo(Math.min(STEPS.length - 1, demo + 1))} disabled={demo === STEPS.length - 1}>Next</button>
          <button className="btn sm" onClick={() => { ran.current = null; setDemo(0); }}>Restart</button>
          <button className="btn sm" onClick={() => { setAuto(false); setDemo(null); }}>Exit demo</button>
        </div>
      </div>
    </div>
  );
}
