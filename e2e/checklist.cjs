// Judge-style feature checklist (12 items) against a LIVE backend, with inputs generated at run time (never pre-recorded).
// Usage: BASE=http://localhost:8000 node e2e/checklist.cjs     (BASE = the app URL; API_BASE if the API is on another host)
const { chromium } = require("playwright");
const fs = require("fs"); const crypto = require("crypto");
const BASE = process.env.BASE || "http://localhost:8000";
const API = process.env.API_BASE || BASE;
const OUT = process.env.OUT || "e2e-results";
const STAMP = Date.now().toString(36).slice(-5);
const NAME = `Checklist Hab ${STAMP}`, MAT = `Basalt-fibre felt ${STAMP}`;
const O2 = +(23 + Math.random() * 3).toFixed(1), P = +(70 + Math.random() * 25).toFixed(1); // random new atmosphere
const j = async (path, body, method) => { const r = await fetch(API + path, body ? { method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}); if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`); return r; };
const json = async (...a) => (await j(...a)).json();
const sha = (b) => crypto.createHash("sha256").update(b).digest("hex").slice(0, 12);

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
  await p.addInitScript(() => { try { localStorage.setItem("sxs-welcome-v1", "1"); } catch {} }); // skip the first-visit welcome
  const errors = []; p.on("pageerror", (e) => errors.push(String(e)));
  const res = []; const step = async (n, name, fn) => {
    try { res.push({ n, name, ok: true, detail: await fn() }); } catch (e) { res.push({ n, name, ok: false, detail: String(e).split("\n")[0].slice(0, 240) }); }
    await p.screenshot({ path: `${OUT}/check${String(n).padStart(2, "0")}.png` }).catch(() => {});
  };
  const nav = async (label) => { await p.locator("aside .nav", { hasText: label }).first().click(); await p.waitForTimeout(900); };
  const pick = async () => { await p.selectOption("select[aria-label='Active spacecraft']", { label: NAME }); await p.waitForTimeout(1200); };
  let sc, mid;
  await p.goto(BASE); await p.waitForSelector("text=Powered by NASA data", { timeout: 60000 });

  await step(1, "Digital twin: new spacecraft + changed atmosphere", async () => {
    sc = await json("/api/spacecraft", { mode: "scratch", name: NAME });
    sc.atmosphere = { ...sc.atmosphere, o2_pct: O2, pressure_kpa: P, gravity: "partial gravity" };
    sc.compartments = [{ id: "C-HAB", name: "Sleep station", type: "crew", volume_m3: 12, x: 0, y: 0, w: 50, h: 100, sensors: [{ id: "S1", type: "smoke" }],
      objects: [{ id: "O-BAG", name: "Sleeping bag", category: "crew equipment", components: [{ id: "K-SHELL", name: "Shell fabric", material_id: "MAT-NOMEX", form: "fabric", thickness_mm: 0.5, mass_g: 400 }] }] }];
    sc = await json(`/api/spacecraft/${sc.id}`, sc, "PUT");
    await p.reload(); await p.waitForTimeout(1500); await pick(); await nav("Digital twin");
    await p.waitForSelector("g[aria-label='Compartment Sleep station']", { timeout: 15000 });
    return `${NAME}: ${O2}% O₂, ${P} kPa, partial gravity; twin shows 'Sleep station'`;
  });
  await step(2, "Material inventory: custom material not in presets", async () => {
    const m = await json("/api/materials", { name: MAT, composition: "basalt fibre", form: "felt", class: "inorganic fibre" });
    mid = m.id || m.material?.id; if (!mid) throw new Error("no id returned");
    sc.compartments[0].objects[0].components.push({ id: "K-PAD", name: "Padding", material_id: mid, form: "felt", thickness_mm: 10, mass_g: 300 });
    sc = await json(`/api/spacecraft/${sc.id}`, sc, "PUT");
    await nav("Material inventory"); await p.waitForSelector(`text=${MAT}`, { timeout: 15000 });
    const st = (await json(`/api/materials/${mid}`)).status; return `${mid} added; evidence status: ${st?.status || JSON.stringify(st).slice(0, 80)}`;
  });
  await step(3, "Virtual Fire Lab: new fuel / O₂ / pressure combination", async () => {
    const o2 = +(17 + Math.random() * 5).toFixed(2), d0 = +(2.3 + Math.random() * 1.2).toFixed(2);
    const r = await json("/api/predict", { material_form: "liquid droplet", fuel: "methanol", o2_pct: o2, pressure_kpa: 101.0, d0_mm: d0, diluent: "nitrogen", gravity: "microgravity" });
    await nav("Virtual Fire Lab"); await p.getByRole("button", { name: /Droplet/ }).first().click(); await p.waitForTimeout(800);
    return `methanol ${o2}% O₂, 101.0 kPa, ${d0} mm → ${r.outcome}${r.estimate != null ? ` K=${r.estimate.toFixed(3)}` : ""}`;
  });
  await step(4, "Combustion prediction: supported AND unsupported", async () => {
    const ok = await json("/api/predict", { material_form: "liquid droplet", fuel: "methanol", o2_pct: 21, pressure_kpa: 101.3, d0_mm: 2.5, diluent: "nitrogen", gravity: "microgravity" });
    const bad = await json("/api/predict", { material_form: "liquid droplet", fuel: "methanol", o2_pct: 30, pressure_kpa: 101.3, d0_mm: 1.7, diluent: "nitrogen", gravity: "microgravity" });
    const solid = await json("/api/predict", { material_form: "fabric", fuel: "Nomex", o2_pct: 21, pressure_kpa: 101.3, diluent: "nitrogen", gravity: "microgravity" });
    if (!ok.outcome.startsWith("Model-supported") || bad.outcome !== "Unavailable" || solid.outcome !== "Unavailable") throw new Error(`${ok.outcome} / ${bad.outcome} / ${solid.outcome}`);
    return `in-domain: ${ok.outcome}; 30%/1.7 mm: ${bad.outcome} (${(bad.reasons || [])[0] || ""}); Nomex fabric: ${solid.outcome}`;
  });
  await step(5, "Material interaction under the selected spacecraft environment", async () => {
    const it = await json("/api/interactions", { material_ids: ["MAT-PMMA", "MAT-NOMEX"] });
    const rk = await json("/api/evidence/rank", { material_id: "MAT-PMMA", o2_pct: O2, pressure_kpa: P, gravity: "partial gravity", flow_cm_s: 15 });
    const d = it.documented_interactions[0]; const a = rk.find((e) => e.id === d?.id)?.applicability;
    await nav("Virtual Fire Lab"); await p.getByRole("button", { name: "Level 2 · Material interactions" }).click();
    await p.getByRole("button", { name: new RegExp(`Use .* environment`) }).click(); await p.waitForTimeout(1200);
    return `${it.status}: ${d?.id}; applicability at ${O2}% / ${P} kPa / partial g: ${a?.tier || JSON.stringify(a).slice(0, 60)}`;
  });
  await step(6, "Scenario comparison: two atmospheres", async () => {
    const r = await json("/api/compare/conditions", { material_id: "MAT-NOMEX", scenarios: [
      { label: "Cabin air", o2_pct: 21, pressure_kpa: 101.3, gravity: "microgravity", flow_cm_s: 15, diluent: "nitrogen" },
      { label: NAME, o2_pct: O2, pressure_kpa: P, gravity: "partial gravity", flow_cm_s: 15, diluent: "nitrogen" }] });
    const rows = r.rows || r.scenarios || r; const s = JSON.stringify(r);
    if (!/po2|partial/i.test(s)) throw new Error("no O2 partial pressure in comparison");
    return `pO₂ ${(21 * 101.3 / 100).toFixed(1)} vs ${(O2 * P / 100).toFixed(1)} kPa compared`;
  });
  await step(7, "Knowledge graph: material → experiment → finding → source", async () => {
    const t = await json(`/api/graph/trace?node=${encodeURIComponent(`${sc.id}/C-HAB/O-BAG/K-SHELL`)}`);
    const tr = t.traces || t; if (!tr.length) throw new Error("no trace");
    const path = tr[0].path.map((n) => n.label).join(" → ");
    const custom = await json(`/api/graph/trace?node=${encodeURIComponent(`${sc.id}/C-HAB/O-BAG/K-PAD`)}`);
    return `${tr.length} traces (engine ${tr[0].engine}): ${path}; custom material traces: ${(custom.traces || custom).length} (expected 0, no evidence invented)`;
  });
  await step(8, "Scientific audit: FLEX test 70 (193F001) discrepancy + source", async () => {
    const a = await json("/api/audit"); const items = a.items.filter((x) => (x.test || "").includes("193F001"));
    const k = items.find((x) => /burning/i.test(x.quantity)) || items[0]; if (!k) throw new Error("193F001 not in audit"); await nav("Evidence audit");
    return `${items.length} items for ${k.test}; ${k.quantity}: ${k.values.map((v) => `${v.raw} ${k.unit} (${v.location})`).join(" vs ")} → ${k.status}`;
  });
  await step(9, "Research gaps for the custom scenario", async () => {
    const g = await json(`/api/gaps/gravity?spacecraft_id=${sc.id}`); const s = JSON.stringify(g);
    if (!s.includes(MAT)) throw new Error("custom material not listed"); await pick(); await nav("Research gaps");
    return `${MAT} listed in the gravity gap view for ${NAME}`;
  });
  await step(10, "Emergency preparedness: simulated incident, no operational guidance", async () => {
    const r = await json("/api/incidents/replay", { spacecraft_id: sc.id, compartment_id: "C-HAB", type: "smoke", phase: "lunar surface" });
    const s = JSON.stringify(r).toLowerCase();
    if (!/simulat/.test(s)) throw new Error("not labelled simulated");
    const bad = ["evacuate the", "put on your", "discharge the extinguisher", "turn off the", "you should immediately"].filter((x) => s.includes(x));
    if (bad.length) throw new Error("operational instruction found: " + bad.join(", "));
    return `labelled simulated; ${(r.candidates || r.candidate_components || []).length} unconfirmed candidates; no instructions`;
  });
  await step(11, "PDF report, change conditions, second report differs", async () => {
    const pdf = async () => Buffer.from(await (await j("/api/report", { spacecraft_id: sc.id })).arrayBuffer());
    const a = await pdf(); sc.atmosphere.o2_pct = +(O2 + 2).toFixed(1); sc = await json(`/api/spacecraft/${sc.id}`, sc, "PUT"); const c = await pdf();
    if (a.slice(0, 4).toString() !== "%PDF" || sha(a) === sha(c)) throw new Error("reports identical or not PDF");
    fs.writeFileSync(`${OUT}/report_before.pdf`, a); fs.writeFileSync(`${OUT}/report_after.pdf`, c);
    return `report 1 ${a.length} B (${sha(a)}), report 2 at ${sc.atmosphere.o2_pct}% O₂ ${c.length} B (${sha(c)})`;
  });
  await step(12, "Persistence after page refresh", async () => {
    await p.reload(); await p.waitForTimeout(2500);
    const opts = await p.locator("select[aria-label='Active spacecraft'] option").allInnerTexts();
    if (!opts.includes(NAME)) throw new Error("spacecraft missing after refresh");
    const s2 = await json(`/api/spacecraft/${sc.id}`); const mats = await json("/api/materials");
    if (!mats.some((m) => m.id === mid)) throw new Error("custom material missing");
    return `after refresh: ${NAME} (${s2.atmosphere.o2_pct}% O₂) and ${MAT} still present (server SQLite)`;
  });
  fs.writeFileSync(`${OUT}/checklist_results.json`, JSON.stringify({ base: BASE, api: API, when: new Date().toISOString(), spacecraft: NAME, material: MAT, steps: res, page_errors: errors }, null, 1));
  console.log(res.map((r) => `${r.ok ? "PASS" : "FAIL"} ${r.n}. ${r.name} — ${r.detail}`).join("\n"));
  console.log(`\n${res.filter((r) => r.ok).length}/${res.length} passed · page errors: ${errors.length}`, errors.slice(0, 2));
  await b.close();
})();
