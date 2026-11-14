const BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";

/* ---- Static snapshot mode ----
   When the page carries window.__SXS_SNAPSHOT__ (single-file preview), API calls are answered from responses that were
   recorded from the real backend by backend/scripts/snapshot.py. Keys use the same normalisation as that script. */
const SNAP: Record<string, any> | undefined = (window as any).__SXS_SNAPSHOT__;
export const STATIC = !!SNAP;
export const SNAP_META = (window as any).__SXS_META__ || {};
const r1 = (v: any) => (v === undefined || v === null || v === "" ? null : Math.round(Number(v) * 10) / 10);
const stable = (o: any): string => (o === null || typeof o !== "object" ? JSON.stringify(o) : Array.isArray(o) ? `[${o.map(stable).join(",")}]`
  : `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${stable(o[k])}`).join(",")}}`);
function normBody(path: string, b: any) {
  b = b || {};
  if (path === "/api/evidence/rank" || path === "/api/insights") return { material_id: b.material_id || null, o2_pct: r1(b.o2_pct), pressure_kpa: r1(b.pressure_kpa), gravity: b.gravity || null };
  if (path === "/api/predict") { const o: any = {}; for (const k of ["material_form", "fuel", "o2_pct", "pressure_kpa", "d0_mm", "diluent", "gravity"]) o[k] = ["o2_pct", "pressure_kpa", "d0_mm"].includes(k) ? r1(b[k]) : b[k] || null; return o; }
  if (path === "/api/interactions") return { material_ids: [...(b.material_ids || [])].sort() };
  if (path === "/api/copilot") return { question: String(b.question || "").replace(/\u200b/g, "").trim() };
  if (path === "/api/incidents/replay") return { spacecraft_id: b.spacecraft_id, compartment_id: b.compartment_id, type: b.type, phase: b.phase || "orbital operations" };
  if (path === "/api/report") return { spacecraft_id: b.spacecraft_id };
  return b;
}
function staticKey(method: string, url: string, body?: any) {
  const [path, qs] = url.split("?");
  let p: [string, any][] = [...new URLSearchParams(qs || "").entries()].filter(([, v]) => v !== "" && v !== "undefined" && v !== "null");
  if (path.startsWith("/api/materials/")) p = p.filter(([k]) => ["o2_pct", "pressure_kpa", "gravity"].includes(k)).map(([k, v]) => [k, k === "gravity" ? v : r1(v)]);
  if (path === "/api/search") p = p.filter(([k]) => k === "q" || k === "mode");
  p.sort((a, b) => (a[0] < b[0] ? -1 : 1));
  let k = `${method} ${path}` + (p.length ? "?" + p.map(([a, b]) => `${a}=${b}`).join("&") : "");
  if (method === "POST") k += " " + stable(normBody(path, body));
  return k;
}
export class NotInSnapshot extends Error {}
function fromSnapshot(method: string, url: string, body?: any): any {
  const path = url.split("?")[0];
  if (method !== "GET" && method !== "POST") throw new NotInSnapshot("Static preview: creating, editing and deleting spacecraft needs the live backend (see README).");
  if (path === "/api/spacecraft" && method === "POST") throw new NotInSnapshot("Static preview: creating spacecraft needs the live backend (see README).");
  if (path === "/api/status/neo4j/sync") return { connected: false, error: "static preview: no backend", mode: "Static snapshot" };
  if (path === "/api/copilot/usage") return { requests: 0, by_engine: {}, recent: [], static: true, limits: {} };
  if (path === "/api/status/semantic/check") return SNAP!["GET /api/status"].semantic;
  const k = staticKey(method, url, body);
  if (k in SNAP!) {
    const v = SNAP![k];
    if (path === "/api/evidence/rank") { const ev: any[] = SNAP!["GET /api/evidence"]; return v.map((x: any) => ({ ...ev.find((e) => e.id === x.id), applicability: x.applicability })); }
    return JSON.parse(JSON.stringify(v));
  }
  if (path === "/api/predict") return { outcome: "Unavailable", estimate: null, checks: [{ check: "Static preview", result: false, detail: "This exact input was not pre-computed. The snapshot covers N2-diluted droplets at 70.9 and 101.3 kPa, O2 10-40%, D0 1.5-4.0 mm. Run the live backend for any input.", kind: "static" }], reasons: ["Not pre-computed in the static preview"], model: null };
  if (path === "/api/search") return { mode: "static", available: false, reason: "This query was not pre-recorded in the static preview. Try a suggested question, or run the live backend.", results: [] };
  if (path === "/api/copilot") return { mode: "static preview", answer: "This question was not pre-recorded. In the live app the Copilot answers any question from the NASA evidence. Try one of the suggested questions.", claims: [], dropped: [], evidence: [] };
  console.warn("[SXS static] not recorded:", k);
  throw new NotInSnapshot("This view needs the live backend for this exact input (not pre-recorded in the static preview).");
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  if (SNAP) return fromSnapshot(init?.method || "GET", path, init?.body ? JSON.parse(String(init.body)) : undefined);
  // Never spin forever: a free-tier backend can be asleep or restarting. 90 s covers a cold start.
  const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 90_000);
  let r: Response;
  try { r = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, signal: ctl.signal, ...init }); }
  catch (e: any) { throw new Error(e?.name === "AbortError" ? "The server took more than 90 s to answer (it may be waking up or restarting). Please try again." : `Cannot reach the API: ${e?.message || e}`); }
  finally { clearTimeout(timer); }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return r.json();
}
const post = <T,>(p: string, b: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(b) });

export const api = {
  status: () => req<any>("/api/status"),
  semanticCheck: () => post<any>("/api/status/semantic/check", {}),
  neo4jSync: () => post<any>("/api/status/neo4j/sync", {}),
  templates: () => req<any[]>("/api/templates"),
  spacecraft: () => req<any[]>("/api/spacecraft"),
  getSpacecraft: (id: string) => req<any>(`/api/spacecraft/${id}`),
  newSpacecraft: (b: { mode: string; template_id?: string; name?: string }) => post<any>("/api/spacecraft", b),
  saveSpacecraft: (sc: any) => req<any>(`/api/spacecraft/${sc.id}`, { method: "PUT", body: JSON.stringify(sc) }),
  deleteSpacecraft: (id: string) => req<any>(`/api/spacecraft/${id}`, { method: "DELETE" }),
  screen: (id: string, comp?: string) => req<any>(`/api/spacecraft/${id}/screen${comp ? `?compartment_id=${comp}` : ""}`),
  materials: () => req<any[]>("/api/materials"),
  material: (id: string, q: Record<string, any> = {}) =>
    req<any>(`/api/materials/${id}?` + new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)]))),
  interactions: (ids: string[]) => post<any>("/api/interactions", { material_ids: ids }),
  evidence: () => req<any[]>("/api/evidence"),
  sources: () => req<any[]>("/api/sources"),
  rank: (s: any) => post<any[]>("/api/evidence/rank", s),
  search: (q: string, mode = "auto", spacecraft_id?: string) =>
    req<any>(`/api/search?q=${encodeURIComponent(q)}&mode=${encodeURIComponent(mode)}&k=8${spacecraft_id ? `&spacecraft_id=${spacecraft_id}` : ""}`),
  graphStats: () => req<any>("/api/graph/stats"),
  subgraph: (center: string, depth = 2, domain?: string) =>
    req<any>(`/api/graph/subgraph?center=${encodeURIComponent(center)}&depth=${depth}${domain ? `&domain=${domain}` : ""}`),
  trace: (node: string) => req<any[]>(`/api/graph/trace?node=${encodeURIComponent(node)}`),
  models: () => req<any[]>("/api/models"),
  predict: (b: any) => post<any>("/api/predict", b),
  audit: () => req<any>("/api/audit"),
  auditCsvUrl: () => BASE + "/api/audit.csv",
  gaps: (sid?: string) => req<any>(`/api/gaps${sid ? `?spacecraft_id=${sid}` : ""}`),
  compare: (ids: string[]) => post<any>("/api/compare", { spacecraft_ids: ids }),
  insights: (s: any) => post<any>("/api/insights", s),
  copilot: (question: string, scenario?: any, spacecraft_id?: string, mode = "auto") => post<any>("/api/copilot", { question, scenario, spacecraft_id, mode }),
  copilotUsage: () => req<any>("/api/copilot/usage"),
  incidentTypes: (sid: string) => req<any[]>(`/api/incidents/${sid}`),
  replay: (b: any) => post<any>("/api/incidents/replay", b),
  evaluation: () => req<any>("/api/evaluation"),
  gapsDim: (dim: string, sid?: string) => req<any>(`/api/gaps/${dim}${sid ? `?spacecraft_id=${sid}` : ""}`),
  compareConditions: (b: any) => post<any>("/api/compare/conditions", b),
  investigations: () => req<any[]>("/api/investigations"),
  datasets: () => req<any[]>("/api/datasets"),
  nasaUsage: () => req<any>("/api/nasa-usage"),
  newMaterial: (b: any) => post<any>("/api/materials", b),
  deleteMaterial: (id: string) => req<any>(`/api/materials/${id}`, { method: "DELETE" }),
  literature: (q: string) => req<any>(`/api/literature?q=${encodeURIComponent(q)}`),
  duplicate: (id: string, name?: string) => post<any>(`/api/spacecraft/${id}/duplicate`, { name }),
  procedures: (sid: string) => req<any[]>(`/api/procedures/${sid}`),
  addProcedure: (b: any) => post<any>("/api/procedures", b),
  report: async (b: any) => {
    if (SNAP) {
      const v = fromSnapshot("POST", "/api/report", b);
      const bin = atob(v.__pdf_b64); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
      return new Blob([u], { type: "application/pdf" });
    }
    const r = await fetch(BASE + "/api/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
    if (!r.ok) throw new Error("Report failed");
    return r.blob();
  },
};