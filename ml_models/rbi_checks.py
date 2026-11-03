"""
rbi_checks.py - reporting-only validation diagnostics asked for by the Indian (RBI) regime pack.

These are the evidence functions behind checklist rows R18 and R19 (RBI Draft paras 16, 31, 42, 54, 55). Like the
missingness scan and the out-of-time test they REPORT and DECIDE NOTHING: no pass/fail threshold is invented here. Where
a threshold is needed it is read from the app's existing governance block in hyperparameters.json (psi_major,
psi_watch, auc_drop_pct, fairness_gap) or is the four-fifths ratio already used for the adverse-impact test.

Every function is pure (arrays and frames in, a dict or frame out) so it can be unit-tested on a synthetic panel.

ASCII-only strings (Windows cp1252 console).
"""
import json
import os

import numpy as np
import pandas as pd

_HP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hyperparameters.json')
_DEFAULTS = {'psi_major': 0.25, 'psi_watch': 0.10, 'auc_drop_pct': 5.0, 'fairness_gap': 0.05}
FOUR_FIFTHS = 0.80   # the adverse-impact bar already used by the framework (EEOC four-fifths rule)


def thresholds():
    """The material-change thresholds the application already uses (hyperparameters.json['governance'])."""
    out = dict(_DEFAULTS)
    try:
        g = json.load(open(_HP, encoding='utf-8')).get('governance', {})
        for k in out:
            if k in g:
                out[k] = float(g[k])
    except (OSError, ValueError):
        pass
    return out


# --------------------------------------------------------------------------------------------- drift (Draft 54(7))
def psi(expected, actual, n_bins=10, eps=1e-4):
    """Population stability index of `actual` against `expected`. Numeric: quantile bins of `expected`;
    non-numeric: category shares. Missing values form their own bin."""
    e = pd.Series(expected).reset_index(drop=True)
    a = pd.Series(actual).reset_index(drop=True)
    if pd.api.types.is_numeric_dtype(e):
        ev = e.dropna().astype(float)
        if ev.nunique() < 2:
            return 0.0
        edges = np.unique(np.quantile(ev, np.linspace(0, 1, n_bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf

        def share(s):
            c = np.histogram(s.dropna().astype(float), bins=edges)[0].astype(float)
            c = np.append(c, float(s.isna().sum()))
            return c / max(1.0, c.sum())
    else:
        cats = sorted(set(e.dropna().astype(str)) | set(a.dropna().astype(str)))

        def share(s):
            vc = s.astype(object).where(s.notna(), '__missing__').astype(str).value_counts()
            c = np.array([float(vc.get(k, 0)) for k in cats] + [float(vc.get('__missing__', 0))])
            return c / max(1.0, c.sum())
    pe, pa = np.clip(share(e), eps, None), np.clip(share(a), eps, None)
    return float(np.sum((pa - pe) * np.log(pa / pe)))


def drift_status(value, th=None):
    th = th or thresholds()
    return 'major' if value > th['psi_major'] else ('watch' if value > th['psi_watch'] else 'stable')


def feature_drift(train, test, columns, n_bins=10):
    """PSI per feature, training period against test period, with the app's watch/major status."""
    th = thresholds()
    rows = []
    for c in columns:
        v = psi(train[c], test[c], n_bins)
        rows.append({'feature': c, 'psi': round(v, 4), 'status': drift_status(v, th)})
    t = pd.DataFrame(rows).sort_values('psi', ascending=False).reset_index(drop=True)
    return {'table': t, 'max_psi': float(t['psi'].max()) if len(t) else 0.0,
            'n_major': int((t['status'] == 'major').sum()), 'n_watch': int((t['status'] == 'watch').sum()),
            'thresholds': {k: th[k] for k in ('psi_watch', 'psi_major')}}


def score_drift(p_train, p_test, n_bins=10):
    v = psi(pd.Series(p_train), pd.Series(p_test), n_bins)
    return {'psi': round(v, 4), 'status': drift_status(v)}


# --------------------------------------------------------------------------- output stability (Draft 54(6))
def row_order_invariance(df, target, columns, build_scorer, *, groups=None, n_orders=4, seed=0, probe=200, **kw):
    """Fit the deployed scorer on `n_orders` row orderings of the SAME data and score one fixed probe set.
    `build_scorer(df, target, columns, groups=..., **kw)` must return (scorer, report) like
    missing_governance.build_scorer. Reports the largest PD difference over the probe rows."""
    rng = np.random.RandomState(seed)
    df = df.reset_index(drop=True)
    g = None if groups is None else np.asarray(groups)
    probe_idx = np.arange(min(probe, len(df)))
    pds = []
    for k in range(n_orders):
        perm = np.arange(len(df)) if k == 0 else rng.permutation(len(df))
        d = df.iloc[perm].reset_index(drop=True)
        gg = None if g is None else g[perm]
        sc, _ = build_scorer(d, target, columns, groups=gg, **kw)
        pds.append(np.asarray(sc.score(df.iloc[probe_idx][list(columns)])['probability'], dtype=float))
    arr = np.vstack(pds)
    spread = np.nanmax(arr, axis=0) - np.nanmin(arr, axis=0)
    return {'n_orders': int(n_orders), 'n_probe': int(len(probe_idx)),
            'max_abs_pd_diff': float(np.nanmax(spread)), 'mean_abs_pd_diff': float(np.nanmean(spread)),
            'invariant': bool(np.nanmax(spread) <= 1e-12)}


def selection_stability(select_fn, seeds):
    """`select_fn(seed) -> iterable of selected feature names`. Reports the size range and the pairwise Jaccard
    similarity of the selected sets across seeds (the run itself fixes seed 42; this is a reported diagnostic)."""
    sets = [frozenset(select_fn(s)) for s in seeds]
    jac = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            u = sets[i] | sets[j]
            jac.append(len(sets[i] & sets[j]) / len(u) if u else 1.0)
    core = frozenset.intersection(*sets) if sets else frozenset()
    return {'seeds': list(seeds), 'sizes': [len(s) for s in sets],
            'min_jaccard': float(min(jac)) if jac else 1.0, 'mean_jaccard': float(np.mean(jac)) if jac else 1.0,
            'n_in_every_set': len(core), 'stable': bool(jac and min(jac) >= 0.8) if jac else True}


# ------------------------------------------------------------------------------- fairness by group (Draft 54(3))
def segment_assessment(y, p, segments, cutoff=None, min_events=20):
    """Per-segment calibration and favourable-decision rate. `segments`: array of segment labels (for example the
    size band). The favourable decision is PD <= `cutoff`; with no institution cutoff the portfolio median predicted PD
    is used and the result is labelled INDICATIVE. `ratio` = lowest segment rate / highest segment rate."""
    from sklearn.metrics import roc_auc_score
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    s = np.asarray(segments).astype(str)
    ok = ~np.isnan(p)
    cut = float(np.median(p[ok])) if cutoff is None else float(cutoff)
    rows = []
    for g in sorted(set(s[ok])):
        m = ok & (s == g)
        ev = int(y[m].sum())
        auc = None
        if ev >= min_events and (m.sum() - ev) >= min_events:
            auc = float(roc_auc_score(y[m], p[m]))
        rows.append({'segment': g, 'n': int(m.sum()), 'events': ev, 'mean_pd': float(p[m].mean()),
                     'realised': float(y[m].mean()),
                     'realised_over_expected': float(y[m].mean() / p[m].mean()) if p[m].mean() > 0 else None,
                     'auc': auc, 'favourable_rate': float((p[m] <= cut).mean())})
    t = pd.DataFrame(rows)
    rates = t['favourable_rate'] if len(t) else pd.Series(dtype=float)
    ratio = float(rates.min() / rates.max()) if len(t) and rates.max() > 0 else None
    return {'table': t, 'cutoff': cut, 'cutoff_basis': 'portfolio median PD (indicative; no institution cutoff)'
            if cutoff is None else 'supplied cutoff', 'ratio': ratio,
            'passes_four_fifths': None if ratio is None else bool(ratio >= FOUR_FIFTHS),
            'thin_segments': [r['segment'] for r in rows if r['events'] < min_events]}


# -------------------------------------------------------------------- label and sample sensitivity (Draft 54(5))
def label_lag_sensitivity(y, p, days_to_event, lags=(0, 90, 180)):
    """Re-score discrimination after dropping positives whose event falls within `lag` days of the statement date
    (a proxy for statements that were not yet public). `days_to_event` is NaN for negatives."""
    from sklearn.metrics import roc_auc_score
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    d = np.asarray(days_to_event, dtype=float)
    rows = []
    for lag in lags:
        keep = ~((y == 1) & (d < lag))
        keep &= ~np.isnan(p)
        yy, pp = y[keep], p[keep]
        auc = float(roc_auc_score(yy, pp)) if len(np.unique(yy)) == 2 else None
        rows.append({'lag_days': int(lag), 'n_positives': int(yy.sum()), 'n_rows': int(keep.sum()),
                     'auc': auc, 'gini': None if auc is None else 2 * auc - 1})
    return pd.DataFrame(rows)


def coefficient_sign_audit(columns, coef, corr=None, rho=0.7):
    """The scorer models P(default = 1) on WOE inputs with WOE = ln(good/bad), so a higher WOE means LOWER risk and every
    fitted coefficient should be NEGATIVE. A positive coefficient has the unexpected sign. Lists those and, where a
    correlation matrix is supplied, the columns they are correlated with at |rho| >= rho (the usual cause is collinearity).
    Reporting only."""
    coef = np.asarray(coef, dtype=float)
    cols = list(columns)
    bad = [c for c, b in zip(cols, coef) if b > 0]
    out = {'n_columns': len(cols), 'n_unexpected': len(bad), 'unexpected': bad, 'expected_sign': 'negative', 'partners': {}}
    if corr is not None:
        for c in bad:
            if c in corr.columns:
                r = corr[c].drop(index=c, errors='ignore')
                out['partners'][c] = [k for k, v in r.items() if abs(v) >= rho and k in cols]
    return out


# ----------------------------------------------------------------------- stress and robustness (Draft 54, 55)
def perturbation_sensitivity(scorer, X, columns, grade_fn, scales=(0.01, 0.05, 0.10), seed=0, n_rows=2000):
    """Multiply every numeric input by (1 + e), e uniform in [-scale, +scale], re-score, and report the share of
    rows whose grade changes and the largest PD change."""
    rng = np.random.RandomState(seed)
    Xs = X[list(columns)].reset_index(drop=True)
    if len(Xs) > n_rows:
        Xs = Xs.iloc[rng.choice(len(Xs), n_rows, replace=False)].reset_index(drop=True)
    base = scorer.score(Xs)
    p0 = np.asarray(base['probability'], dtype=float)
    g0 = np.array([grade_fn(v) if v == v else None for v in p0], dtype=object)
    rows = []
    for sc in scales:
        Xp = Xs.copy()
        for c in Xp.columns:
            if pd.api.types.is_numeric_dtype(Xp[c]):
                Xp[c] = Xp[c] * (1.0 + rng.uniform(-sc, sc, len(Xp)))
        pp = np.asarray(scorer.score(Xp)['probability'], dtype=float)
        gp = np.array([grade_fn(v) if v == v else None for v in pp], dtype=object)
        valid = ~np.isnan(p0) & ~np.isnan(pp)
        rows.append({'scale': float(sc), 'share_grade_changed': float((g0[valid] != gp[valid]).mean()),
                     'max_abs_pd_change': float(np.max(np.abs(pp[valid] - p0[valid]))),
                     'mean_abs_pd_change': float(np.mean(np.abs(pp[valid] - p0[valid])))})
    return pd.DataFrame(rows)


def outlier_sensitivity(scorer, X, columns, q=0.01):
    """Clip every numeric input at its q and 1-q quantiles and re-score: how far do PDs move?"""
    Xs = X[list(columns)].reset_index(drop=True)
    Xc = Xs.copy()
    for c in Xc.columns:
        if pd.api.types.is_numeric_dtype(Xc[c]):
            lo, hi = Xc[c].quantile(q), Xc[c].quantile(1 - q)
            Xc[c] = Xc[c].clip(lo, hi)
    p0 = np.asarray(scorer.score(Xs)['probability'], dtype=float)
    p1 = np.asarray(scorer.score(Xc)['probability'], dtype=float)
    v = ~np.isnan(p0) & ~np.isnan(p1)
    return {'q': float(q), 'max_abs_pd_change': float(np.max(np.abs(p1[v] - p0[v]))),
            'mean_abs_pd_change': float(np.mean(np.abs(p1[v] - p0[v]))),
            'share_rows_changed_over_1pct_abs': float((np.abs(p1[v] - p0[v]) > 0.01).mean())}


# ------------------------------------------------------------------------------------ benchmarking (Draft 16)
def benchmark_models(X, y, small_columns, groups=None, n_splits=5, seed=42):
    """Out-of-fold AUC of (a) a plain logistic regression on a small named set of ratios and (b) a gradient-boosted
    tree on all columns of X, with grouped folds when `groups` is given. Reported next to the governed model; it
    selects nothing (the governed process keeps one learner)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    y = np.asarray(y).astype(int)
    folds = (StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y, groups=np.asarray(groups))
             if groups is not None else StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y))
    folds = list(folds)
    out = {}
    models = {
        'small_logistic': (list(small_columns), make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                                                              LogisticRegression(max_iter=1000))),
        'gradient_boosting': (list(X.columns), HistGradientBoostingClassifier(random_state=seed)),
    }
    for name, (cols, mdl) in models.items():
        oof = np.full(len(y), np.nan)
        for tr, te in folds:
            from sklearn.base import clone
            m = clone(mdl).fit(X.iloc[tr][cols], y[tr])
            oof[te] = m.predict_proba(X.iloc[te][cols])[:, 1]
        auc = float(roc_auc_score(y, oof))
        out[name] = {'n_features': len(cols), 'auc': auc, 'gini': 2 * auc - 1}
    return out


# ------------------------------------------------------------------------- material change (Draft 42)
def material_change(oot=None, drift=None, th=None):
    """Which of the application's material-change triggers does this run's OWN evidence breach? Triggers are the ones
    already in hyperparameters.json['governance']: score or feature PSI above psi_major, and a drop of more than
    auc_drop_pct in discrimination from in-time to out-of-time (the Gini change is used when no AUC is stored)."""
    th = th or thresholds()
    trig, seen = [], {}
    if drift is not None:
        seen['max_feature_psi'] = drift.get('max_psi')
        if drift.get('max_psi') is not None and drift['max_psi'] > th['psi_major']:
            trig.append('feature PSI %.3f > %.2f' % (drift['max_psi'], th['psi_major']))
    if oot and oot.get('ok') and oot.get('gini_drop_rel') is not None:
        seen['gini_drop_pct'] = round(100 * oot['gini_drop_rel'], 2)
        if 100 * oot['gini_drop_rel'] > th['auc_drop_pct']:
            trig.append('discrimination fell %.1f%% out of time > %.1f%%' % (100 * oot['gini_drop_rel'], th['auc_drop_pct']))
    return {'thresholds': th, 'observed': seen, 'triggered': trig, 'revalidation_required': bool(trig)}
