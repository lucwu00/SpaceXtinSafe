// End-to-end demonstration workflow (13 steps). Writes e2e/results.json and screenshots.
const { chromium } = require("playwright");
const fs = require("fs");
const BASE = process.env.BASE || "http://localhost:8000";
const OUT = process.env.OUT || "/tmp/claude-0/e2e";
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
  await p.addInitScript(() => { try { localStorage.setItem("sxs-welcome-v1", "1"); } catch {} }); // skip the first-visit welcome
  const errors = []; p.on("pageerror", (e) => errors.push(String(e))); p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  const res = []; const step = async (n, name, fn) => {
    try { const detail = await fn(); res.push({ n, name, ok: true, detail }); }
    catch (e) { res.push({ n, name, ok: false, detail: String(e).slice(0, 300) }); }
    await p.screenshot({ path: `${OUT}/step${String(n).padStart(2, "0")}.png` });
  };
  const nav = async (label) => { await p.getByRole("button", { name: label, exact: false }).first().click(); await p.waitForTimeout(600); };
  // remove configurations left by earlier E2E runs so names are unique
  const prev = await (await fetch(BASE + "/api/spacecraft")).json();
  for (const s of prev.filter((x) => x.name === "E2E Lab Module")) await fetch(BASE + "/api/spacecraft/" + s.id, { method: "DELETE" });
  await p.goto(BASE); await p.waitForSelector("text=Mission overview");
  await step(1, "Configure spacecraft (Customise template)", async () => {
    await nav("Design Studio"); await p.getByRole("button", { name: "Customise a template" }).click();
    await p.getByPlaceholder("Name for your copy").first().fill("E2E Lab Module");
    await p.getByRole("button", { name: "Copy and customise" }).first().click(); await p.waitForSelector("text=Created E2E Lab Module");
    const o2 = p.locator("label:has-text('Oxygen') input"); await o2.fill("24"); await p.getByRole("button", { name: "Save configuration" }).click();
    await p.waitForSelector("text=Saved."); return "Created and saved custom configuration at 24% O2";
  });
  await step(2, "Inspect compartment in digital twin", async () => {
    await nav("Digital twin"); await p.locator("g[aria-label='Compartment Crew quarters']").click(); await p.waitForSelector("h2:has-text('Crew quarters')"); return "Crew quarters selected";
  });
  await step(3, "Select object", async () => { await p.locator(".card button.nav", { hasText: "Sleeping bag" }).click(); await p.waitForSelector("h2:has-text('Sleeping bag')"); return "Sleeping bag selected"; });
  await step(4, "Identify component materials", async () => {
    const t = await p.locator(".ev").allInnerTexts(); if (!t.join(" ").includes("Nomex")) throw new Error("material not shown"); return t.map((x) => x.split("\n")[0]).join(" | ");
  });
  await step(5, "Traverse knowledge graphs", async () => {
    await p.locator(".ev", { hasText: "Shell fabric" }).getByRole("button", { name: "Trace in graph" }).click(); await p.waitForSelector("text=Multi-hop traces");
    await p.waitForFunction(() => /Multi-hop traces \((?!0\))\d+\)/.test(document.body.innerText), null, { timeout: 20000 });
    await p.waitForSelector("svg.graphbox", { timeout: 20000 }); await p.waitForTimeout(2500);
    return await p.locator("text=/Multi-hop traces \\(\\d+\\)/").innerText() + " · " + await p.locator("svg.graphbox > text").last().textContent();
  });
  await step(6, "Retrieve NASA evidence", async () => {
    await nav("Mission Workspace"); await p.locator("form input").first().fill("Which findings are relevant to the Sleeping bag in the E2E Lab Module?");
    await p.getByRole("button", { name: "Analyse", exact: true }).click({ timeout: 30000 }); await p.waitForSelector("text=Retrieved for your question", { timeout: 30000 });
    return (await p.locator("text=/mode: /").first().innerText()) + " · " + (await p.locator("text=/graph entities/").count() ? await p.locator("text=/graph entities/").first().innerText() : "no graph entities");
  });
  await step(7, "Assess applicability", async () => {
    await p.locator("button", { hasText: "Why this rank?" }).first().click(); const f = await p.locator(".factor").first().innerText(); return "Factor chips shown, e.g. " + f;
  });
  await step(8, "Generate eligible prediction", async () => {
    await p.locator("label:has-text('Material') select").first().selectOption("MAT-METHANOL");
    await p.locator("label:has-text('Form') select").first().selectOption("liquid droplet");
    await p.locator("label:has-text('Oxygen') input").first().fill("21"); await p.locator("label:has-text('Pressure') input").first().fill("101.3");
    await p.locator("label:has-text('Droplet diameter') input").fill("2.5");
    await p.getByRole("button", { name: "Check eligibility & estimate" }).click(); await p.waitForSelector("text=/mm²\\/s/");
    const o = await p.locator("#pred .pill").first().innerText(); if (!o.includes("Model-supported")) throw new Error("outcome " + o);
    await p.locator("label:has-text('Droplet diameter') input").fill("1.7"); await p.locator("label:has-text('Oxygen') input").first().fill("30");
    await p.getByRole("button", { name: "Check eligibility & estimate" }).click(); await p.waitForTimeout(800);
    return `21% O2, 2.5 mm: ${o}; 30% O2, 1.7 mm: ${await p.locator("#pred .pill").first().innerText()}`;
  });
  await step(9, "Investigate source discrepancies", async () => {
    await nav("Evidence audit"); await p.locator("tr", { hasText: "Air flow velocity" }).first().click(); await p.waitForSelector("text=Modelling decision");
    return await p.locator(".card h2").nth(1).innerText() + " · " + (await p.locator(".kpi .mono").allInnerTexts()).join(" vs ");
  });
  await step(10, "Compare scenarios", async () => {
    await nav("Compare scenarios"); const s = p.locator(".card.tight select"); await s.nth(0).selectOption({ label: "E2E Lab Module" }); await s.nth(1).selectOption({ label: "Lunar Surface Habitat" });
    await p.waitForTimeout(1200); return (await p.locator(".card h2").allInnerTexts()).join(" vs ");
  });
  await step(11, "Identify research gaps", async () => {
    await nav("Research gaps"); await p.waitForSelector("table.heat"); const z = await p.locator("table.heat td").evaluateAll((tds) => tds.filter((t) => t.textContent === "").length); return `${z} cells with no finding`;
  });
  await step(12, "Replay simulated incident", async () => {
    await nav("Incident intelligence"); await p.locator("label:has-text('Compartment') select").selectOption({ label: "Crew quarters" });
    await p.getByRole("button", { name: "Replay" }).click(); await p.waitForTimeout(4200); const c = await p.locator("table tbody tr").count();
    if (!(await p.locator("text=SIMULATED").count())) throw new Error("no simulated label"); return `${c} candidate components; timeline replayed`;
  });
  await step(13, "Generate mission evidence report", async () => {
    await nav("Mission reports"); await p.getByRole("button", { name: "Generate PDF" }).click(); await p.waitForSelector("text=Download report", { timeout: 30000 }); return "PDF generated and previewed";
  });
  await step(14, "Global Copilot (extra)", async () => {
    await p.getByRole("button", { name: "Scientific Copilot" }).click(); await p.locator(".drawer textarea").fill("What happened to Nomex in the Saffire experiments?");
    await p.locator(".drawer").getByRole("button", { name: "Ask", exact: true }).click(); await p.waitForSelector(".drawer .card", { timeout: 30000 });
    return await p.locator(".drawer .card .pill").first().innerText();
  });
  await step(15, "AI Evaluation Centre (extra)", async () => { await p.getByRole("button", { name: "Close" }).click(); await nav("AI Evaluation Centre"); await p.waitForSelector("text=Recall@5"); return "Loaded"; });
  fs.writeFileSync("e2e/results.json", JSON.stringify({ base: BASE, when: new Date().toISOString(), steps: res, console_errors: errors }, null, 1));
  console.log(res.map((r) => `${r.ok ? "PASS" : "FAIL"} ${r.n}. ${r.name} — ${r.detail}`).join("\n")); console.log("console errors:", errors.length, errors.slice(0, 3));
  await b.close();
})();
