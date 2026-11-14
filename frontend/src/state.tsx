import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

export type Scenario = {
  compartment_id?: string; object_id?: string; component_id?: string; material_id?: string; form?: string;
  o2_pct?: number; pressure_kpa?: number; gravity?: string; flow_cm_s?: number; diluent?: string; d0_mm?: number; question?: string;
};
type Ctx = {
  page: string; go: (p: string) => void;
  list: any[]; scId: string; setScId: (id: string) => void; sc: any | null; reload: () => Promise<void>;
  scenario: Scenario; setScenario: (s: Scenario) => void; patch: (s: Partial<Scenario>) => void;
  materials: any[]; status: any | null; refreshStatus: () => void;
  prediction: any | null; setPrediction: (p: any) => void;
  copilotOpen: boolean; setCopilotOpen: (b: boolean) => void; copilotSeed: string; askCopilot: (q: string) => void;
  simple: boolean; setSimple: (b: boolean) => void;
  ctx: { interaction_ids?: string[]; compare_ids?: string[]; incident?: any; fireTab?: string }; setCtx: (p: Partial<{ interaction_ids: string[]; compare_ids: string[]; incident: any; fireTab: string }>) => void;
  demo: number | null; setDemo: (n: number | null) => void;
};
const C = createContext<Ctx>(null as any);
export const useApp = () => useContext(C);

export function AppProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState(() => location.hash.slice(1) || "overview");
  const [list, setList] = useState<any[]>([]);
  const [scId, setScIdRaw] = useState<string>(() => { try { return localStorage.getItem("sxs.sc") || "SC-ORBITAL"; } catch { return "SC-ORBITAL"; } });
  const [scenario, setScenario] = useState<Scenario>({});
  const [materials, setMaterials] = useState<any[]>([]);
  const [status, setStatus] = useState<any | null>(null);
  const [prediction, setPrediction] = useState<any | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotSeed, setSeed] = useState("");
  const [simple, setSimple] = useState(false);
  const [ctx, setCtxRaw] = useState<any>({});
  const setCtx = (p: any) => setCtxRaw((c: any) => ({ ...c, ...p }));
  const [demo, setDemo] = useState<number | null>(null);
  const go = (p: string) => { setPage(p); location.hash = p; window.scrollTo(0, 0); };
  useEffect(() => { const f = () => setPage(location.hash.slice(1) || "overview"); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  const reload = useCallback(async () => { setList(await api.spacecraft()); api.materials().then(setMaterials); }, []);
  const refreshStatus = useCallback(() => { api.status().then(setStatus).catch(() => setStatus(null)); }, []);
  useEffect(() => { reload(); refreshStatus(); }, [reload, refreshStatus]);
  const sc = list.find((s) => s.id === scId) || list[0] || null;
  // Keep the scenario's atmosphere in step with the selected spacecraft.
  useEffect(() => {
    if (!sc) return;
    const a = sc.atmosphere;
    setScenario((s) => ({ ...s, o2_pct: a.o2_pct, pressure_kpa: a.pressure_kpa, gravity: a.gravity, flow_cm_s: a.ventilation_cm_s, diluent: a.diluent }));
  }, [sc?.id, sc?.atmosphere?.o2_pct, sc?.atmosphere?.pressure_kpa, sc?.atmosphere?.gravity]);
  const setScId = (id: string) => { setScIdRaw(id); try { localStorage.setItem("sxs.sc", id); } catch { /* ignore */ } setScenario({}); setPrediction(null); };
  const patch = (p: Partial<Scenario>) => setScenario((s) => ({ ...s, ...p }));
  const askCopilot = (q: string) => { setSeed(q + "​".repeat(Math.random() * 5 | 0)); setCopilotOpen(true); };
  return <C.Provider value={{ page, go, list, scId: sc?.id || scId, setScId, sc, reload, scenario, setScenario, patch, materials, status, refreshStatus,
    prediction, setPrediction, copilotOpen, setCopilotOpen, copilotSeed: copilotSeed, askCopilot, simple, setSimple, ctx, setCtx, demo, setDemo }}>{children}</C.Provider>;
}

export const matName = (materials: any[], id?: string) => materials.find((m) => m.id === id)?.name || id || "—";
