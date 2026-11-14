import { useEffect, useState, type ReactNode } from "react";
import { useApp } from "./state";

export function useAsync<T>(fn: () => Promise<T>, deps: any[]): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true; setLoading(true); setError(null);
    fn().then((d) => live && setData(d)).catch((e) => live && setError(String(e.message || e))).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [...deps, n]);
  return { data, error, loading, reload: () => setN((x) => x + 1) };
}

export const Loading = ({ label = "Loading" }: { label?: string }) => <div className="row muted"><span className="spin" /> {label}…</div>;
export const Err = ({ e }: { e: string | null }) => (e ? <div className="banner">Error: {e}</div> : null);
export const Empty = ({ children }: { children: ReactNode }) => <div className="empty">{children}</div>;

export function Page({ title, intro, simple, children, actions }: { title: string; intro: string; simple?: string; children: ReactNode; actions?: ReactNode }) {
  const { simple: s } = useApp();
  return (
    <div>
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div><h1>{title}</h1><p className="intro">{s && simple ? simple : intro}</p></div>
        {actions}
      </div>
      {children}
    </div>
  );
}

export function Tier({ t }: { t: string }) {
  return <span className={`pill tier-${t.split(" ")[0]}`}>{t}</span>;
}

export function Factors({ f }: { f: Record<string, string> }) {
  return <span className="row" style={{ gap: 4 }}>{Object.entries(f).map(([k, v]) =>
    <span key={k} className={`factor f-${v.split(" ")[0]}`} title={`${k}: ${v}`}>{k}: {v}</span>)}</span>;
}

export function EvidenceCard({ e, extra }: { e: any; extra?: ReactNode }) {
  const { simple } = useApp();
  const [open, setOpen] = useState(false);
  return (
    <div className="ev">
      <div className="row between">
        <div className="row"><span className="pill acc">{e.investigation}</span><span className="pill">{e.category}</span>{e.applicability && <Tier t={e.applicability.tier} />}</div>
        <span className="mono faint">{e.id}</span>
      </div>
      <div style={{ marginTop: 6 }}>{e.statement}</div>
      {!simple && <div className="q">“{e.quote}”</div>}
      <div className="row small muted" style={{ marginTop: 4 }}>
        <span>{e.location}</span>·<a href={e.source_url} target="_blank" rel="noreferrer">{e.source_identifier}</a>
        {e.applicability && <button className="btn sm" onClick={() => setOpen(!open)}>{open ? "Hide" : "Why this rank?"}</button>}
      </div>
      {open && e.applicability && <div style={{ marginTop: 6 }}><Factors f={e.applicability.factors} /><div className="small faint" style={{ marginTop: 4 }}>Score {e.applicability.score} over {Math.round(e.applicability.factor_coverage * 100)}% of factors reported. Limitation: {e.limitations}</div></div>}
      {extra}
    </div>
  );
}

export function Outcome({ o }: { o: string }) {
  const cls = o.startsWith("Model-supported") ? "ok" : o.startsWith("Exploratory") ? "model" : "bad";
  return <span className={`pill ${cls}`}>{o}</span>;
}

export const fmt = (v: any, d = 3) => (v === null || v === undefined ? "—" : typeof v === "number" ? (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(d)) : String(v));
