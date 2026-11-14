// Dynamic end-to-end workflow through the real UI and live backend, using inputs that were never pre-recorded.
// Create spacecraft -> modify compartment -> add object -> add custom material -> graph -> evidence -> applicability ->
// eligible prediction -> discrepancy -> interaction -> compare -> gap -> incident -> report.
const { chromium } = require("playwright");
const fs = require("fs");
const BASE = process.env.BASE || "http://localhost:8000";
const OUT = process.env.OUT || "/tmp/claude-0/e2e";
const STAMP = Date.now().toString(36).slice(-5);
const NAME = `Judge Lab ${STAMP}`, MAT = `Ti-6Al-4V bracket stock ${STAMP}`;
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
  const errors = []; p.on("pageerror", (e) => errors.push(String(e)));
  const res = []; const step = async (n, name, fn) => {
    try { res.push({ n, name, ok: true, detail: await fn() }); } catch (e) { res.push({ n, name, ok: false, detail: String(e).split("\n")[0].slice(0, 240) }); }
    await p.screenshot({ path: `${OUT}/dyn${String(n).padStart(2, "0")}.png` });
  };
  const nav = async (label) => { await p.locator("aside .nav", { hasText: label }).first().click(); await p.waitForTimeout(700); };
  await p.goto(BASE); await p.waitForSelector("text=Powered by NASA data");
  await step(1, "Create spacecraft (from scratch)", async () => {
    await nav("Design Studio"); await p.getByRole("button", { name: "Build from scratch" }).click();
    await p.getByPlaceholder("Spacecraft name").fill(NAME); await p.getByRole("button", { name: "Create", exact: true }).click();
    await p.waitForSelector(`text=Created ${NAME}`); return NAME;
  });
  await step(2, "Modify compartment (add + rename + atmosphere)", async () => {
    await p.getByRole("button", { name: "+ Compartment" }).click();
    const nameInput = p.locator(".card input[value='New compartment']").first(); await nameInput.fill("Engineering bay");
    await p.locator("label:has-text('Oxygen') input").first().fill("26.5");
    return "Engineering bay added; O2 set to 26.5%";
  });
  await step(3, "Add object with component", async () => {
    await p.getByRole("button", { name: "+ Object" }).first().click(); await p.locator("input[value='New object']").first().fill("Tool locker");
    await p.getByRole("button", { name: "+ Component" }).first().click(); await p.locator("input[value='New component']").first().fill("Locker door");
    await p.getByRole("button", { name: "Save configuration" }).click(); await p.waitForSelector("text=Saved."); return "Tool locker / Locker door saved";
  });
  await step(4, "Add custom (unregistered) material and use it", async () => {
    await p.locator("#cm-name").first().fill(MAT); await p.locator("#cm-comp").first().fill("Ti-6Al-4V"); await p.locator("#cm-form").first().fill("shavings");
    await p.getByRole("button", { name: "Add material and search evidence" }).first().click(); await p.waitForSelector(`form.card .pill:has-text("${MAT}")`); // the hidden <option> can match plain text= first
    const st = await p.locator("form.card .pill").nth(1).innerText();
    const sel = p.locator("table select").first(); const opt = await sel.locator("option", { hasText: MAT }).getAttribute("value"); await sel.selectOption(opt);
    await p.getByRole("button", { name: "Save configuration" }).click(); await p.waitForSelector("text=Saved."); return `status: ${st}`;
  });
  await step(5, "Knowledge graph updated", async () => {
    const sc = (await (await fetch(BASE + "/api/spacecraft")).json()).find((s) => s.name === NAME);
    const c = sc.compartments.find((x) => x.name === "Engineering bay");
    const sub = await (await fetch(`${BASE}/api/graph/subgraph?center=${encodeURIComponent(sc.id + "/" + c.id)}&depth=3`)).json();
    const hasMat = sub.nodes.some((n) => n.label === "Material" && n.user_defined);
    if (!hasMat) throw new Error("custom material node missing"); await nav("Knowledge graphs"); await p.waitForTimeout(1500);
    return `${sub.nodes.length} nodes around Engineering bay incl. user-defined material`;
  });
  await step(6, "Retrieve NASA evidence (new free-text question)", async () => {
    await nav("Mission Workspace"); await p.locator("form input").first().fill(`Is there evidence about titanium shavings or metal fines near cotton clothing at ${STAMP.length + 24}% oxygen?`);
    await p.getByRole("button", { name: "Analyse", exact: true }).click(); await p.waitForSelector("text=Retrieved for your question", { timeout: 30000 });
    return await p.locator("text=/mode: /").first().innerText();
  });
  await step(7, "Assess applicability", async () => { await p.locator("button", { hasText: "Why this rank?" }).first().click(); return await p.locator(".factor").first().innerText(); });
  await step(8, "Eligible prediction with new inputs", async () => {
    await p.locator("label:has-text('Material') select").first().selectOption("MAT-METHANOL");
    await p.locator("label:has-text('Form') select").first().selectOption("liquid droplet");
    await p.locator("label:has-text('Oxygen') input").first().fill("19.3"); await p.locator("label:has-text('Pressure') input").first().fill("100.9");
    await p.locator("label:has-text('Gravity') select").first().selectOption("microgravity"); await p.locator("label:has-text('Diluent') select").first().selectOption("nitrogen");
    await p.locator("label:has-text('Droplet diameter') input").fill("2.83");
    await p.getByRole("button", { name: "Check eligibility & estimate" }).click(); await p.waitForSelector("#pred >> text=/mm²\\/s/", { timeout: 20000 });
    return (await p.locator("#pred .pill").first().innerText()) + " · " + (await p.locator("#pred b").first().innerText());
  });
  await step(9, "Investigate scientific discrepancy", async () => {
    await nav("Evidence audit"); await p.locator("tr", { hasText: "Burning-rate constant" }).first().click(); await p.waitForSelector("text=Modelling decision");
    return (await p.locator(".kpi .mono").allInnerTexts()).join(" vs ");
  });
  await step(10, "Explore material interaction", async () => {
    await nav("Virtual Fire Lab"); await p.getByRole("button", { name: "Level 2 · Material interactions" }).click();
    await p.getByRole("button", { name: "Saffire-II combined PMMA + Nomex sample" }).click(); await p.waitForTimeout(1500);
    return await p.locator(".card .pill").filter({ hasText: /interaction|evidence/i }).first().innerText();
  });
  await step(11, "Compare scenarios (new config vs template, then conditions)", async () => {
    await nav("Compare scenarios"); const s = p.locator(".card.tight select"); await s.nth(0).selectOption({ label: NAME }); await s.nth(1).selectOption({ label: "Lunar Surface Habitat" }); await p.waitForTimeout(1500);
    const h = (await p.locator(".card h2").allInnerTexts()).join(" vs ");
    await p.getByRole("button", { name: "Conditions for one material" }).click(); await p.getByRole("button", { name: "Compare", exact: true }).click(); await p.waitForSelector("text=O₂ partial pressure (reference only)");
    return h + " · condition comparison shown";
  });
  await step(12, "Identify research gap (for the new config)", async () => {
    await nav("Research gaps"); await p.getByRole("button", { name: "Gravity", exact: true }).click(); await p.waitForTimeout(1500);
    const has = await p.locator("table.heat td", { hasText: MAT }).count(); if (!has) throw new Error("custom material not in gap table"); return `${MAT} listed with gap cells`;
  });
  await step(13, "Replay simulated incident (new compartment, transit phase)", async () => {
    await nav("Incident intelligence"); await p.locator("label:has-text('Mission phase') select").selectOption("deep-space transit");
    await p.locator("label:has-text('Compartment') select").selectOption({ label: "Engineering bay" }); await p.getByRole("button", { name: "Replay" }).click();
    await p.waitForSelector("text=Human-review summary", { timeout: 20000 }); return (await p.locator(".banner.info").nth(0).innerText()).slice(0, 160);
  });
  await step(14, "Generate report from current inputs", async () => {
    await nav("Mission reports"); await p.getByRole("button", { name: "Generate PDF" }).click(); await p.waitForSelector("text=Download report", { timeout: 40000 });
    const sc = (await (await fetch(BASE + "/api/spacecraft")).json()).find((s) => s.name === NAME);
    const r = await fetch(BASE + "/api/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ spacecraft_id: sc.id }) });
    const buf = Buffer.from(await r.arrayBuffer()); return `PDF ${buf.length} bytes, starts ${buf.slice(0, 5)}`;
  });
  fs.writeFileSync(`${OUT}/dynamic_results.json`, JSON.stringify({ base: BASE, when: new Date().toISOString(), name: NAME, material: MAT, steps: res, page_errors: errors }, null, 1));
  console.log(res.map((r) => `${r.ok ? "PASS" : "FAIL"} ${r.n}. ${r.name} — ${r.detail}`).join("\n")); console.log("page errors:", errors.length, errors.slice(0, 2));
  await b.close();
})();
