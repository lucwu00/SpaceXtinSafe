import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp, matName } from "../state";
import { Page, useAsync, Loading, Err, Empty } from "../ui";

const uid = (p: string) => p + "-" + Math.random().toString(36).slice(2, 7).toUpperCase();
const FORMS = ["thin sheet", "thin fabric sheet", "fabric", "foam", "bulk", "powder", "foil", "shavings", "laminate", "board", "film", "liquid", "liquid droplet", "wire", "wire insulation", "cell", "canister", "rod", "sphere", "slab", "blanket", "moulded part", "adhesive layer", "coating", "assembly", "mixed"];

export function MaterialSelect({ value, onChange, id }: { value: string; onChange: (v: string) => void; id?: string }) {
  const { materials } = useApp();
  const cats = [...new Set(materials.map((m) => m.category || "Other"))].sort();
  return <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>{cats.map((c) => <optgroup key={c} label={c}>
    {materials.filter((m) => (m.category || "Other") === c).map((m) => <option key={m.id} value={m.id}>{m.name}{m.user_defined ? " (user)" : ""}</option>)}</optgroup>)}</select>;
}

export function CustomMaterialForm({ onCreated }: { onCreated?: (r: any) => void }) {
  const { materials, reload } = useApp();
  const [f, setF] = useState<any>({ name: "", composition: "", grade: "", form: "", thickness_mm: "", mass_g: "", geometry: "", applications: "", related_to: "" });
  const [res, setRes] = useState<any>(null); const [err, setErr] = useState<string | null>(null);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: any) => {
    e.preventDefault(); setErr(null);
    try {
      const r = await api.newMaterial({ ...f, thickness_mm: f.thickness_mm === "" ? null : +f.thickness_mm, mass_g: f.mass_g === "" ? null : +f.mass_g,
        applications: f.applications ? [f.applications] : [], related_to: f.related_to ? [f.related_to] : [] });
      setRes(r); await reload(); onCreated?.(r);
    } catch (x: any) { setErr(x.message); }
  };
  return (
    <form className="card" onSubmit={submit}>
      <h3>Add a material that is not in the catalogue</h3>
      <p className="small muted">Leave anything you don't know blank: unknown properties stay unknown. No combustion properties are assigned.</p>
      <div className="grid g4">
        <label className="label">Name *<input id="cm-name" required value={f.name} onChange={set("name")} placeholder="e.g. Magnesium alloy AZ31" /></label>
        <label className="label">Composition<input id="cm-comp" value={f.composition} onChange={set("composition")} placeholder="e.g. Mg-3Al-1Zn" /></label>
        <label className="label">Grade<input id="cm-grade" value={f.grade} onChange={set("grade")} /></label>
        <label className="label">Physical form<input id="cm-form" value={f.form} onChange={set("form")} placeholder="e.g. bulk, powder, foil" /></label>
        <label className="label">Thickness mm<input id="cm-th" type="number" step="any" value={f.thickness_mm} onChange={set("thickness_mm")} /></label>
        <label className="label">Mass g<input id="cm-mass" type="number" step="any" value={f.mass_g} onChange={set("mass_g")} /></label>
        <label className="label">Geometry<input id="cm-geo" value={f.geometry} onChange={set("geometry")} /></label>
        <label className="label">Application<input id="cm-app" value={f.applications} onChange={set("applications")} /></label>
        <label className="label">Closest catalogue material (optional)<select id="cm-rel" value={f.related_to} onChange={set("related_to")}><option value="">none</option>
          {materials.filter((m) => !m.user_defined).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      </div>
      <div className="row" style={{ marginTop: 8 }}><button className="btn pri">Add material and search evidence</button></div>
      {err && <div className="banner">{err}</div>}
      {res && <div style={{ marginTop: 10 }}>
        <div className="row"><span className="pill acc">{res.material.name}</span><span className="pill">{res.status.status}</span>{res.gap_created && <span className="pill fire">Research gap recorded</span>}</div>
        <p className="small muted">{res.status.note}</p>
        {res.status.related_findings.length > 0 && <p className="small">Related (indirect) findings via {res.status.related_materials.join(", ")}: {res.status.related_findings.join(", ")}</p>}
        <p className="small"><b>Library search</b> ({res.library_search_note}): {res.library_search.map((e: any) => e.id).join(", ") || "nothing retrieved"}</p>
      </div>}
    </form>
  );
}

export function Studio() {
  const { sc, reload, setScId, materials } = useApp();
  const tpls = useAsync(() => api.templates(), []);
  const [tab, setTab] = useState<"quick" | "customise" | "scratch" | "edit">("edit");
  const [draft, setDraft] = useState<any>(null);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (sc) setDraft(JSON.parse(JSON.stringify(sc))); }, [sc?.id]);
  const create = async (mode: string, template_id?: string) => {
    setErr(null);
    try { const s = await api.newSpacecraft({ mode, template_id, name: name || undefined }); await reload(); setScId(s.id); setTab("edit"); setMsg(`Created ${s.name}`); }
    catch (e: any) { setErr(e.message); }
  };
  const save = async () => {
    setErr(null);
    try { await api.saveSpacecraft(draft); await reload(); setMsg("Saved. All modules now use this configuration."); } catch (e: any) { setErr(e.message); }
  };
  const del = async () => { if (!sc) return; await api.deleteSpacecraft(sc.id); await reload(); setScId("SC-ORBITAL"); };
  const up = (f: (d: any) => void) => setDraft((d: any) => { const n = JSON.parse(JSON.stringify(d)); f(n); return n; });
  return (
    <Page title="Spacecraft Design Studio" intro="Start from an illustrative template, customise one, or build a configuration from scratch. Every module (twin, graphs, workspace, incidents, reports) uses the configuration selected in the header."
      simple="Pick a ready-made spacecraft or make your own. Add rooms, the things in them, and what those things are made of.">
      <div className="tabs">{[["edit", "Edit current"], ["quick", "Quick Start"], ["customise", "Customise a template"], ["scratch", "Build from scratch"]].map(([k, l]) =>
        <button key={k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k as any)}>{l}</button>)}</div>
      <Err e={err} />{msg && <div className="banner info">{msg}</div>}
      {(tab === "quick" || tab === "customise") && (tpls.loading ? <Loading /> :
        <div className="grid g3">{tpls.data!.map((t: any) => (
          <div key={t.id} className="card"><h2>{t.name}</h2><div className="small muted">{t.vehicle_class}</div><p className="small">{t.description}</p>
            <div className="row"><span className="pill acc">{t.atmosphere.o2_pct}% O₂</span><span className="pill acc">{t.atmosphere.pressure_kpa} kPa</span><span className="pill">{t.atmosphere.gravity}</span></div>
            <div className="small muted" style={{ margin: "8px 0" }}>{t.compartments.length} compartments · {t.compartments.reduce((n: number, c: any) => n + c.objects.length, 0)} objects</div>
            {tab === "customise" && <input placeholder="Name for your copy" value={name} onChange={(e) => setName(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />}
            <button className="btn pri" onClick={() => create(tab === "quick" ? "quick" : "customise", t.id)}>{tab === "quick" ? "Use this template" : "Copy and customise"}</button>
          </div>))}</div>)}
      {tab === "scratch" && <div className="card"><h2>New empty configuration</h2>
        <div className="row"><input placeholder="Spacecraft name" value={name} onChange={(e) => setName(e.target.value)} /><button className="btn pri" onClick={() => create("scratch")}>Create</button></div>
        <p className="small muted">You will then add compartments, objects and components in the editor.</p></div>}
      {tab === "edit" && (!draft ? <Loading /> : <>
        <div className="card">
          <div className="row between"><h2>{draft.name}</h2><div className="row"><button className="btn" onClick={() => setDraft(JSON.parse(JSON.stringify(sc)))}>Revert</button>
            <button className="btn pri" onClick={save}>Save configuration</button>
            <button className="btn" onClick={async () => { const d = await api.duplicate(draft.id, `${draft.name} (copy)`); await reload(); setScId(d.id); setMsg(`Duplicated as ${d.name}`); }}>Duplicate</button>{!draft.id.startsWith("SC-ORBITAL") && !draft.id.startsWith("SC-CAPSULE") && !draft.id.startsWith("SC-LUNAR") && <button className="btn" onClick={del}>Delete</button>}</div></div>
          <div className="grid g4">
            <label className="label">Name<input value={draft.name} onChange={(e) => up((d) => (d.name = e.target.value))} /></label>
            <label className="label">Oxygen (% by volume)<input type="number" step="0.1" value={draft.atmosphere.o2_pct} onChange={(e) => up((d) => (d.atmosphere.o2_pct = +e.target.value))} /></label>
            <label className="label">Pressure (kPa)<input type="number" step="0.1" value={draft.atmosphere.pressure_kpa} onChange={(e) => up((d) => (d.atmosphere.pressure_kpa = +e.target.value))} /></label>
            <label className="label">Gravity<select value={draft.atmosphere.gravity} onChange={(e) => up((d) => (d.atmosphere.gravity = e.target.value))}>{["microgravity", "partial gravity", "1-g"].map((g) => <option key={g}>{g}</option>)}</select></label>
            <label className="label">Ventilation flow (cm/s)<input type="number" value={draft.atmosphere.ventilation_cm_s} onChange={(e) => up((d) => (d.atmosphere.ventilation_cm_s = +e.target.value))} /></label>
            <label className="label">Diluent<select value={draft.atmosphere.diluent} onChange={(e) => up((d) => (d.atmosphere.diluent = e.target.value))}>{["nitrogen", "carbon dioxide", "helium"].map((g) => <option key={g}>{g}</option>)}</select></label>
          </div>
        </div>
        {draft.compartments.map((c: any, ci: number) => (
          <div key={c.id} className="card">
            <div className="row between"><div className="row"><input value={c.name} onChange={(e) => up((d) => (d.compartments[ci].name = e.target.value))} style={{ fontWeight: 600 }} />
              <input value={c.type} onChange={(e) => up((d) => (d.compartments[ci].type = e.target.value))} placeholder="type" />
              <label className="row small muted">Volume m³<input type="number" style={{ width: 70 }} value={c.volume_m3} onChange={(e) => up((d) => (d.compartments[ci].volume_m3 = +e.target.value))} /></label></div>
              <div className="row"><button className="btn sm" onClick={() => up((d) => d.compartments[ci].objects.push({ id: uid("O"), name: "New object", category: "equipment", components: [] }))}>+ Object</button>
                <button className="btn sm" onClick={() => up((d) => d.compartments.splice(ci, 1))}>Remove compartment</button></div></div>
            {c.objects.length === 0 && <Empty>No objects yet.</Empty>}
            {c.objects.map((o: any, oi: number) => (
              <div key={o.id} className="ev">
                <div className="row between"><div className="row"><input value={o.name} onChange={(e) => up((d) => (d.compartments[ci].objects[oi].name = e.target.value))} />
                  <input value={o.category} onChange={(e) => up((d) => (d.compartments[ci].objects[oi].category = e.target.value))} placeholder="category" /></div>
                  <div className="row"><button className="btn sm" onClick={() => up((d) => d.compartments[ci].objects[oi].components.push({ id: uid("K"), name: "New component", material_id: "MAT-PMMA", form: "thin sheet", thickness_mm: null, mass_g: null }))}>+ Component</button>
                    <button className="btn sm" onClick={() => up((d) => d.compartments[ci].objects.splice(oi, 1))}>Remove</button></div></div>
                {o.components.length > 0 && <table style={{ marginTop: 6 }}><thead><tr><th>Component</th><th>Material</th><th>Form</th><th>Thickness mm</th><th>Mass g</th><th /></tr></thead><tbody>
                  {o.components.map((k: any, ki: number) => { const K = (f: (x: any) => void) => up((d) => f(d.compartments[ci].objects[oi].components[ki])); return (
                    <tr key={k.id}><td><input value={k.name} onChange={(e) => K((x) => (x.name = e.target.value))} /></td>
                      <td><MaterialSelect value={k.material_id} onChange={(v) => K((x) => (x.material_id = v))} /></td>
                      <td><select value={k.form || ""} onChange={(e) => K((x) => (x.form = e.target.value))}>{[...new Set([k.form, ...FORMS].filter(Boolean))].map((f) => <option key={f}>{f}</option>)}</select></td>
                      <td><input type="number" style={{ width: 80 }} value={k.thickness_mm ?? ""} onChange={(e) => K((x) => (x.thickness_mm = e.target.value === "" ? null : +e.target.value))} /></td>
                      <td><input type="number" style={{ width: 80 }} value={k.mass_g ?? ""} onChange={(e) => K((x) => (x.mass_g = e.target.value === "" ? null : +e.target.value))} /></td>
                      <td><button className="btn sm" onClick={() => up((d) => d.compartments[ci].objects[oi].components.splice(ki, 1))}>✕</button></td></tr>); })}</tbody></table>}
              </div>))}
          </div>))}
        <CustomMaterialForm />
        <button className="btn" onClick={() => up((d) => { const n = d.compartments.length; d.compartments.push({ id: uid("C"), name: "New compartment", type: "general", volume_m3: 10, x: (n % 3) * 34, y: Math.floor(n / 3) * 40, w: 32, h: 38, objects: [] }); })}>+ Compartment</button>
      </>)}
    </Page>
  );
}

export function Inventory() {
  const { sc, materials, go, patch } = useApp();
  const scr = useAsync(() => (sc ? api.screen(sc.id) : Promise.resolve(null)), [sc?.id]);
  const [f, setF] = useState("");
  const [mf, setMf] = useState("");
  return (
    <Page title="Material and component inventory" intro="Every component in the active spacecraft with its material, form and NASA evidence status, plus the full material library. Edit components in the Design Studio."
      simple="A list of everything on board and what it's made of, with whether NASA has studied that material.">
      <div className="card"><div className="row between"><h2>{sc?.name} components</h2><input placeholder="Filter…" value={f} onChange={(e) => setF(e.target.value)} /></div>
        {scr.loading ? <Loading /> : <div className="scroll"><table><thead><tr><th>Compartment</th><th>Object</th><th>Component</th><th>Material</th><th>Form</th><th>Evidence</th><th>Investigations</th><th>Burning-rate model</th><th /></tr></thead>
          <tbody>{scr.data?.rows.filter((r: any) => JSON.stringify(r).toLowerCase().includes(f.toLowerCase())).map((r: any) => (
            <tr key={r.component_id + r.object_id}><td>{r.compartment}</td><td>{r.object}</td><td>{r.component}</td><td>{r.material}</td><td>{r.form}</td>
              <td><span className="pill">{r.status}</span><div className="small faint">{r.material_status}</div></td>
              <td className="small">{r.investigations.join(", ") || "—"}</td><td className="small muted">{r.prediction}</td>
              <td><button className="btn sm" onClick={() => { patch({ compartment_id: r.compartment_id, object_id: r.object_id, component_id: r.component_id, material_id: r.material_id, form: r.form }); go("workspace"); }}>Analyse</button></td></tr>))}</tbody></table></div>}
        <p className="small faint">{scr.data?.boundary}</p></div>
      <div className="card"><div className="row between"><h2>Material ontology ({materials.length})</h2><input placeholder="Filter materials…" value={mf} onChange={(e) => setMf(e.target.value)} /></div>
        <div className="row small" style={{ marginBottom: 8 }}>{Object.entries(materials.reduce((a: any, m: any) => ({ ...a, [m.evidence_status]: (a[m.evidence_status] || 0) + 1 }), {})).map(([k, v]: any) => <span key={k} className="pill">{k}: {v}</span>)}</div>
        <div className="scroll"><table><thead><tr><th>Material</th><th>Category</th><th>Composition / grade</th><th>Forms</th><th>Evidence status</th><th>Phenomenon</th><th>Typical applications</th><th /></tr></thead><tbody>
        {materials.filter((m) => JSON.stringify(m).toLowerCase().includes(mf.toLowerCase())).map((m) => <tr key={m.id}><td>{m.name}<div className="small faint">{m.scientific_name}</div></td><td>{m.category}</td>
          <td className="small">{[m.composition, m.grade].filter(Boolean).join(" · ") || "unknown"}</td><td className="small">{(m.forms || []).join(", ")}</td>
          <td><span className="pill">{m.evidence_status}</span> <span className="small faint">{m.evidence_count} findings</span></td><td className="small muted">{m.phenomenon}</td><td className="small muted">{(m.applications || []).join(", ")}</td>
          <td><button className="btn sm" onClick={() => { patch({ material_id: m.id, form: m.default_form }); go("firelab"); }}>Fire Lab</button></td></tr>)}</tbody></table></div>
        <p className="small faint">Catalogue entries describe materials only. Typical applications are illustrative, not claims of flight use. Evidence status is computed from the verified findings.</p></div>
      <CustomMaterialForm />
    </Page>
  );
}
