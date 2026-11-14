"""FLEX burning-rate-constant models, fitted to the original PSI-69 table.

Pre-registered rules (fixed before fitting, not tuned on results):
- Groups: fuel x pressure band, nitrogen diluent only (CO2 and He tests are not pooled with N2 tests).
- Features: O2 percent and initial droplet diameter when the group has >= 25 usable tests, else O2 only.
- Validation: leave-one-session-out CV (session = test date), so tests run on the same day never sit on both sides.
- Status 'Model-supported' needs n >= 20, sessions >= 8 and predictive skill (1 - MAE/baseline MAE) >= 0.30;
  otherwise 'Exploratory'.
- Parameter count includes the intercept (O2-only OLS = 2 parameters; O2 + D0 = 3).
"""
from __future__ import annotations
from functools import lru_cache
import numpy as np
from scipy.spatial import Delaunay
from sklearn.ensemble import RandomForestRegressor
from . import data

MMHG_PER_KPA = 7.50062
BANDS = {"1atm": (700, 800, 101.3), "0.7atm": (500, 560, 70.9)}
RULES = {"min_tests": 20, "min_sessions": 8, "min_skill": 0.30, "d0_feature_min_n": 25,
         "knn_k": 3, "knn_quantile": 0.95, "local_min_points": 3, "local_min_sessions": 2}


def _usable(t):
    from .audit import excluded_flex_tests
    if t["test"] in excluded_flex_tests():
        return False
    return (t["k_mm2_s"] is not None and t["d0_mm"] is not None and t["o2"] is not None and t["pressure_mmHg"] is not None
            and not (t["co2"] or 0) and not (t["he"] or 0))


def group_rows(fuel, band):
    lo, hi, _ = BANDS[band]
    return [t for t in data.flex_tests() if t["fuel"] == fuel and _usable(t) and lo <= t["pressure_mmHg"] <= hi]


def _design(rows, use_d0):
    X = np.array([[t["o2"] * 100] + ([t["d0_mm"]] if use_d0 else []) for t in rows], float)
    return X


def _ols(X, y):
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta


def _pred(beta, X):
    return beta[0] + X @ beta[1:]


def _loso(rows, X, y, fit_predict):
    sess = np.array([t["date"] for t in rows])
    oof = np.full(len(y), np.nan)
    base = np.full(len(y), np.nan)
    for s in np.unique(sess):
        te = sess == s; tr = ~te
        if tr.sum() < 3:
            continue
        oof[te] = fit_predict(X[tr], y[tr], X[te])
        base[te] = y[tr].mean()
    return oof, base


def _metrics(y, p, b):
    m = ~np.isnan(p)
    y, p, b = y[m], p[m], b[m]
    mae, bmae = float(np.mean(np.abs(y - p))), float(np.mean(np.abs(y - b)))
    ss_res, ss_tot = float(np.sum((y - p) ** 2)), float(np.sum((y - y.mean()) ** 2))
    return {"n_scored": int(m.sum()), "mae": mae, "rmse": float(np.sqrt(np.mean((y - p) ** 2))), "baseline_mae": bmae,
            "baseline_rmse": float(np.sqrt(np.mean((y - b) ** 2))), "predictive_skill": 1 - mae / bmae if bmae else None,
            "oof_r2": 1 - ss_res / ss_tot if ss_tot else None}


@lru_cache
def registry() -> list[dict]:
    out = []
    for fuel in ("methanol", "n-heptane"):
        for band in ("1atm", "0.7atm"):
            rows = group_rows(fuel, band)
            if len(rows) < 6:
                continue
            use_d0 = len(rows) >= RULES["d0_feature_min_n"]
            X, y = _design(rows, use_d0), np.array([t["k_mm2_s"] for t in rows])
            beta = _ols(X, y)
            oof, base = _loso(rows, X, y, lambda a, b_, c: _pred(_ols(a, b_), c))
            met = _metrics(y, oof, base)
            rf = lambda a, b_, c: RandomForestRegressor(n_estimators=300, max_depth=3, min_samples_leaf=3, random_state=0).fit(a, b_).predict(c)
            rf_oof, _ = _loso(rows, X, y, rf)
            rf_met = _metrics(y, rf_oof, base)
            sessions = len({t["date"] for t in rows})
            failed = [k for k, ok in (("min_tests", len(rows) >= RULES["min_tests"]), ("min_sessions", sessions >= RULES["min_sessions"]),
                                       ("min_skill", (met["predictive_skill"] or 0) >= RULES["min_skill"])) if not ok]
            resid = np.abs(y - oof)[~np.isnan(oof)]
            feats = ["O2 mole percent"] + (["Initial droplet diameter (mm)"] if use_d0 else [])
            out.append({
                "model_id": f"FLEX-K-{'METH' if fuel == 'methanol' else 'HEPT'}-{band}", "fuel": fuel, "pressure_band": band,
                "pressure_kpa_nominal": BANDS[band][2], "diluent": "nitrogen", "gravity": "microgravity", "material_form": "liquid droplet",
                "target": "burning-rate constant K (mm^2/s)", "method": "Ordinary least squares with intercept",
                "features": feats, "n_parameters": 1 + len(feats), "uses_d0": use_d0,
                "coefficients": {"intercept": float(beta[0]), "per_O2_pct": float(beta[1]), **({"per_D0_mm": float(beta[2])} if use_d0 else {})},
                "n_observations": len(rows), "n_sessions": sessions,
                "o2_pct_range": [float(X[:, 0].min()), float(X[:, 0].max())],
                "d0_mm_range": [min(t["d0_mm"] for t in rows), max(t["d0_mm"] for t in rows)],
                "pressure_kpa_range": [round(min(t["pressure_mmHg"] for t in rows) / MMHG_PER_KPA, 1), round(max(t["pressure_mmHg"] for t in rows) / MMHG_PER_KPA, 1)],
                "validation": {"scheme": "leave-one-session-out", **met},
                "benchmark": {"identical_folds": True, "mean_baseline": {"mae": met["baseline_mae"], "n_parameters": 1},
                              "ols": {"mae": met["mae"], "rmse": met["rmse"], "predictive_skill": met["predictive_skill"], "n_parameters": 1 + len(feats)},
                              "random_forest": {"mae": rf_met["mae"], "rmse": rf_met["rmse"], "predictive_skill": rf_met["predictive_skill"],
                                                "settings": "300 trees, max_depth 3, min_samples_leaf 3, random_state 0"},
                              "decision": ("OLS retained as primary: random forest did not achieve lower out-of-fold MAE" if rf_met["mae"] >= met["mae"]
                                           else "Random forest had lower out-of-fold MAE; OLS kept as primary for interpretability (difference reported)")},
                "status": "Model-supported" if not failed else "Exploratory", "failed_criteria": failed,
                "uncertainty_90_mm2_s": float(np.quantile(resid, 0.9)) if len(resid) else None,
                "observed": [{"o2_pct": t["o2"] * 100, "d0_mm": t["d0_mm"], "k": t["k_mm2_s"], "session": t["date"], "record": t["record"]} for t in rows],
                "excluded_tests": [t["record"] for t in data.flex_tests() if t["fuel"] == fuel and BANDS[band][0] <= (t["pressure_mmHg"] or 0) <= BANDS[band][1] and not _usable(t)],
                "limitations": ["Applies only to quiescent isolated droplets in microgravity with nitrogen diluent",
                                "Trace contaminant present in some tests (NASA/TP-2015-216046 Section 5); burning-rate constants judged minimally affected",
                                "Not valid for solids, fabrics, partial gravity, forced flow, CO2 or helium diluents"],
                "unit_verification": "PSI-69 header 'Burning rate; mm' is the burning-rate constant in mm^2/s per NASA/TP-2015-216046 Table IX and its column definition",
                "_X": X.tolist(), "_y": y.tolist(), "_sessions": [t["date"] for t in rows], "_d0": [t["d0_mm"] for t in rows],
            })
    return out


def public(m):
    return {k: v for k, v in m.items() if not k.startswith("_")}


def find_model(fuel, pressure_kpa):
    best = None
    for m in registry():
        if m["fuel"] != fuel:
            continue
        lo, hi = m["pressure_kpa_range"]
        tol = 0.05 * m["pressure_kpa_nominal"]
        if lo - tol <= pressure_kpa <= hi + tol:
            best = m
    return best


def _joint(m, pt_raw):
    """Joint feature-support diagnostics in standardised space."""
    X = np.array(m["_X"]); sd = X.std(axis=0); sd[sd == 0] = 1
    Z, z = X / sd, np.array(pt_raw) / sd
    k = RULES["knn_k"]
    d_all = np.linalg.norm(Z[:, None] - Z[None], axis=2); np.fill_diagonal(d_all, np.inf)
    train_knn = np.sort(d_all, axis=1)[:, :k].mean(axis=1)
    thr = float(np.quantile(train_knn, RULES["knn_quantile"]))
    d = np.linalg.norm(Z - z, axis=1); knn = float(np.sort(d)[:k].mean())
    radius = float(np.median(train_knn)) * 2
    near = d <= radius
    sessions = {m["_sessions"][i] for i in np.where(near)[0]}
    if Z.shape[1] == 1:
        inside = bool(Z[:, 0].min() <= z[0] <= Z[:, 0].max())
        hull_method = "range (1 feature)"
    else:
        inside = bool(Delaunay(Z).find_simplex(z[None])[0] >= 0)
        hull_method = "convex hull (Delaunay, standardised features)"
    return {"inside_hull": inside, "hull_method": hull_method, "knn_distance": knn, "knn_threshold_p95": thr,
            "knn_ok": knn <= thr, "local_points": int(near.sum()), "local_sessions": len(sessions), "local_radius": radius,
            "local_ok": int(near.sum()) >= RULES["local_min_points"] and len(sessions) >= RULES["local_min_sessions"]}


def assess(req: dict) -> dict:
    """Decide whether a burning-rate estimate may be shown, and why. req keys: material_form, fuel, o2_pct, pressure_kpa,
    d0_mm, diluent, gravity."""
    checks, reasons = [], []
    add = lambda name, ok, detail, kind: checks.append({"check": name, "result": ok, "detail": detail, "kind": kind})
    need = ["material_form", "fuel", "o2_pct", "pressure_kpa", "d0_mm", "diluent", "gravity"]
    missing = [k for k in need if req.get(k) in (None, "")]
    add("Required inputs", not missing, "All inputs provided" if not missing else f"Missing: {', '.join(missing)}", "missing")
    if missing:
        return {"outcome": "Unavailable", "estimate": None, "checks": checks, "reasons": [f"Missing input: {k}" for k in missing], "model": None}
    o2, p, d0 = float(req["o2_pct"]), float(req["pressure_kpa"]), float(req["d0_mm"])
    phys = [(0 < o2 <= 100, "O2 percent must be within (0, 100]"), (0 < p <= 1000, "Pressure must be positive and below 1000 kPa"),
            (0 < d0 <= 10, "Droplet diameter must be positive and at most 10 mm")]
    bad = [msg for ok, msg in phys if not ok]
    add("Physical validity", not bad, "Inputs are physically valid" if not bad else "; ".join(bad), "physical")
    if bad:
        return {"outcome": "Unavailable", "estimate": None, "checks": checks, "reasons": bad, "model": None}
    cond = []
    if req["material_form"] != "liquid droplet":
        cond.append(f"Material form '{req['material_form']}' differs from the experiments (isolated liquid droplets)")
    if req["fuel"] not in ("methanol", "n-heptane"):
        cond.append(f"Fuel '{req['fuel']}' was not tested in FLEX")
    if req["diluent"] != "nitrogen":
        cond.append(f"Diluent '{req['diluent']}' is not covered by the nitrogen-diluent models")
    if req["gravity"] != "microgravity":
        cond.append(f"Gravity '{req['gravity']}' differs from the microgravity experiments")
    add("Experimental condition compatibility", not cond, "Form, fuel, diluent and gravity match the experiments" if not cond else "; ".join(cond), "conditions")
    if cond:
        return {"outcome": "Unavailable", "estimate": None, "checks": checks, "reasons": cond, "model": None}
    m = find_model(req["fuel"], p)
    add("Pressure band", m is not None, f"Matched {m['model_id']} ({m['pressure_kpa_range'][0]}-{m['pressure_kpa_range'][1]} kPa)" if m else
        "No model covers this pressure (tested nitrogen-diluent bands are about 70 and 101 kPa)", "conditions")
    if not m:
        return {"outcome": "Unavailable", "estimate": None, "checks": checks, "reasons": ["Pressure outside every tested band"], "model": None}
    pt = [o2] + ([d0] if m["uses_d0"] else [])
    j = _joint(m, pt)
    # Diameter domain still matters when D0 is not a predictor: check the joint (O2, D0) support of the group.
    d0_lo, d0_hi = m["d0_mm_range"]
    d0_in = d0_lo <= d0 <= d0_hi
    add("Droplet diameter within tested range", d0_in, f"Tested D0 {d0_lo}-{d0_hi} mm" + ("" if m["uses_d0"] else " (D0 is not a predictor in this model, but the estimate assumes a comparable droplet)"), "domain")
    jd_ok = True
    if not m["uses_d0"]:
        X2 = np.column_stack([np.array(m["_X"])[:, 0], np.array(m["_d0"])])
        jd = _joint({**m, "_X": X2.tolist()}, [o2, d0])
        jd_ok = jd["inside_hull"] and jd["knn_ok"]
        add("Joint O2 and diameter support (non-predictor check)", jd_ok,
            f"inside hull: {jd['inside_hull']}, kNN distance {jd['knn_distance']:.2f} vs threshold {jd['knn_threshold_p95']:.2f}", "joint")
    add("Inside joint convex hull", j["inside_hull"], j["hull_method"], "joint")
    add("Normalised nearest-neighbour distance", j["knn_ok"], f"mean distance to {RULES['knn_k']} nearest tests = {j['knn_distance']:.2f} (95th percentile of training = {j['knn_threshold_p95']:.2f})", "joint")
    add("Local data coverage", j["local_ok"], f"{j['local_points']} tests from {j['local_sessions']} sessions within radius {j['local_radius']:.2f}", "joint")
    est = float(m["coefficients"]["intercept"] + m["coefficients"]["per_O2_pct"] * o2 + (m["coefficients"].get("per_D0_mm", 0) * d0))
    if not j["inside_hull"] and not j["knn_ok"]:
        return {"outcome": "Unavailable", "estimate": None, "checks": checks, "reasons": ["Request lies outside the joint experimental domain and far from any tested condition (extrapolation)"], "model": public(m), "joint": j}
    if not d0_in and not jd_ok:
        return {"outcome": "Unavailable", "estimate": None, "checks": checks, "reasons": ["Droplet diameter is outside the tested range and the O2-diameter combination is not covered by any test"], "model": public(m), "joint": j}
    if m["status"] != "Model-supported":
        reasons.append(f"Model {m['model_id']} is exploratory (failed: {', '.join(m['failed_criteria'])})")
    if not j["inside_hull"]:
        reasons.append("Outside the joint convex hull, though close to tested points")
    if not j["knn_ok"]:
        reasons.append("Inside the hull but in a sparsely tested region (nearest-neighbour distance above the training 95th percentile)")
    if not j["local_ok"]:
        reasons.append("Too few nearby tests or sessions for adequate local coverage")
    if not d0_in:
        reasons.append("Droplet diameter outside the tested range")
    if not jd_ok:
        reasons.append("O2 and diameter combination not jointly covered by the tests")
    outcome = "Model-supported estimate" if not reasons else "Exploratory estimate"
    return {"outcome": outcome, "estimate": est, "unit": "mm^2/s",
            "interval_90": [est - m["uncertainty_90_mm2_s"], est + m["uncertainty_90_mm2_s"]] if m["uncertainty_90_mm2_s"] else None,
            "checks": checks, "reasons": reasons or ["All checks passed"], "model": public(m), "joint": j,
            "boundary": "Research estimate for an isolated droplet in a NASA-tested condition. Not a spacecraft fire-risk assessment."}
