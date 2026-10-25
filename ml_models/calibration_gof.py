"""calibration_gof.py - goodness-of-fit for calibration, valid under clustering.

WHY THIS EXISTS
---------------
The governing calibration test (METHODOLOGY v3 s7 / CRE36.122) is the per-grade
realised-vs-expected backtest, with a Hosmer-Lemeshow cross-check. Both assume
INDEPENDENT observations. On panel / discrete-time-hazard data (panel_adapter
hazard framing) each entity contributes many correlated rows, so the effective
sample is the number of ENTITIES, not rows. Treating the rows as independent
makes the per-grade Wilson intervals ~sqrt(design-effect) too tight and the HL
statistic too large, so both tests OVER-REJECT on economically trivial
deviations - a false alarm driven by row count, not miscalibration.

That is a methodology gap, not a governance one: the fix belongs here (make the
test valid for the data structure), NOT at the gate (which must never be taught
to forgive a failing test). When a `groups` vector is supplied the per-grade CI
is formed by a CLUSTER bootstrap (resample whole entities, not rows) and the HL
p-value is reported with a design-effect correction. With `groups=None` the
behaviour is the classical i.i.d. test, unchanged - so every cross-sectional run
is identical to before. The switch is automatic on the presence of groups.

ASCII-only in emitted strings (Windows cp1252 console).
"""
import numpy as np
import pandas as pd

Z95 = 1.959963985


# ---------------------------------------------------------------------------
# i.i.d. per-grade interval (Wilson) - unchanged classical path
# ---------------------------------------------------------------------------
def wilson_ci(k, n, z=Z95):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    hw = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - hw), min(1.0, c + hw))


# ---------------------------------------------------------------------------
# Cluster bootstrap per-grade realised-rate CI (resample ENTITIES, not rows)
# ---------------------------------------------------------------------------
def cluster_bootstrap_grade_ci(y, grade_idx, group_idx, n_grades, n_groups,
                               n_boot=1000, random_state=42, alpha=0.05):
    """Percentile CI of each grade's realised default rate, resampling whole
    entities with replacement. Vectorised via per-(entity,grade) count/event
    matrices so cost is O(n_boot * n_groups * n_grades), not O(n_boot * n_rows).

    y          : 0/1 outcome per row.
    grade_idx  : grade index per row in [0, n_grades).
    group_idx  : entity index per row in [0, n_groups).
    Returns {g: (lo, hi)} over grade indices with any population.
    """
    y = np.asarray(y, dtype=float)
    N = np.zeros((n_groups, n_grades), dtype=np.float64)   # rows per (entity,grade)
    K = np.zeros((n_groups, n_grades), dtype=np.float64)   # events per (entity,grade)
    np.add.at(N, (group_idx, grade_idx), 1.0)
    np.add.at(K, (group_idx, grade_idx), y)

    rng = np.random.RandomState(random_state)
    lo = np.full(n_grades, np.nan)
    hi = np.full(n_grades, np.nan)
    boots = np.full((n_boot, n_grades), np.nan)
    for b in range(n_boot):
        idx = rng.randint(0, n_groups, n_groups)     # resample entities w/ replacement
        Nb = N[idx].sum(axis=0)
        Kb = K[idx].sum(axis=0)
        with np.errstate(invalid='ignore', divide='ignore'):
            boots[b] = np.where(Nb > 0, Kb / Nb, np.nan)
    for g in range(n_grades):
        col = boots[:, g]
        col = col[~np.isnan(col)]
        if len(col):
            lo[g] = np.percentile(col, 100 * alpha / 2)
            hi[g] = np.percentile(col, 100 * (1 - alpha / 2))
    return {g: (lo[g], hi[g]) for g in range(n_grades) if np.isfinite(lo[g])}


# ---------------------------------------------------------------------------
# Design effect + clustered Hosmer-Lemeshow
# ---------------------------------------------------------------------------
def intra_cluster_corr(y, group_idx, n_groups):
    """ANOVA (one-way) estimator of the intra-cluster correlation of a binary
    outcome, and the adjusted mean cluster size. Returns (rho, m_adj)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    sizes = np.bincount(group_idx, minlength=n_groups).astype(float)
    sizes = sizes[sizes > 0]
    k = len(sizes)
    grand = y.mean()
    # between/within mean squares
    gsum = np.bincount(group_idx, weights=y, minlength=n_groups).astype(float)
    gcnt = np.bincount(group_idx, minlength=n_groups).astype(float)
    nz = gcnt > 0
    gmean = np.zeros_like(gcnt)
    gmean[nz] = gsum[nz] / gcnt[nz]
    msb = (gcnt[nz] * (gmean[nz] - grand) ** 2).sum() / (k - 1) if k > 1 else 0.0
    ss_within = (y ** 2).sum() - (gsum[nz] ** 2 / gcnt[nz]).sum()
    msw = ss_within / (n - k) if n > k else 0.0
    m0 = (n - (sizes ** 2).sum() / n) / (k - 1) if k > 1 else np.mean(sizes)
    denom = msb + (m0 - 1) * msw
    rho = (msb - msw) / denom if denom > 0 else 0.0
    rho = float(max(0.0, rho))
    m_adj = float(sizes.mean())
    return rho, m_adj


def hosmer_lemeshow(y, p, g=10, group_idx=None, n_groups=None):
    """HL statistic over g equal-frequency bins. Returns dict with H, p_value,
    and (when groups given) a design-effect-corrected H_adj / p_adj where the
    statistic is deflated by DEFF = 1 + (m_adj - 1) * rho (Rao-Scott style).
    """
    from scipy.stats import chi2
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    yg, pg = y[order], p[order]
    H = 0.0
    for ix in np.array_split(np.arange(len(y)), g):
        n = len(ix); O = yg[ix].sum(); E = pg[ix].sum()
        rate = E / n
        d = E * (1 - rate)
        if d > 0:
            H += (O - E) ** 2 / d
    p_val = float(1 - chi2.cdf(H, g - 2))
    out = {'H': float(H), 'p_value': p_val, 'g': g, 'clustered': False}
    if group_idx is not None:
        rho, m_adj = intra_cluster_corr(y, group_idx, n_groups)
        deff = 1.0 + (m_adj - 1.0) * rho
        H_adj = H / deff if deff > 0 else H
        out.update({'clustered': True, 'rho': rho, 'm_adj': m_adj,
                    'design_effect': float(deff), 'H_adj': float(H_adj),
                    'p_adj': float(1 - chi2.cdf(H_adj, g - 2))})
    return out


# ---------------------------------------------------------------------------
# Public: the per-grade backtest, cluster-robust when groups are present
# ---------------------------------------------------------------------------
def per_grade_backtest(y, p, grades, grade_order, groups=None, n_boot=1000,
                       random_state=42, alpha=0.05):
    """Per-grade realised-vs-expected backtest.

    y           : 0/1 outcome per row.
    p           : predicted PD per row.
    grades      : rating grade label per row (strings).
    grade_order : the master-scale order (e.g. AAA..D); only populated grades
                  are reported.
    groups      : entity key per row. None -> classical Wilson interval
                  (i.i.d., unchanged). Given -> CLUSTER-bootstrap interval
                  (resample entities) + the result is marked method='cluster'.

    A grade PASSES when its expected mean PD lies inside the realised-rate CI.
    Returns (DataFrame, summary_dict).
    """
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    grades = np.asarray(grades)
    present = [g for g in grade_order if (grades == g).any()]
    gi_map = {g: i for i, g in enumerate(present)}
    grade_idx = np.array([gi_map[g] for g in grades])

    ci_boot = None
    method = 'wilson'
    if groups is not None:
        method = 'cluster'
        groups = np.asarray(groups)
        _, group_idx = np.unique(groups, return_inverse=True)
        ci_boot = cluster_bootstrap_grade_ci(
            y, grade_idx, group_idx, len(present), group_idx.max() + 1,
            n_boot=n_boot, random_state=random_state, alpha=alpha)

    rows = []
    npass = 0
    for gi, g in enumerate(present):
        m = grades == g
        n = int(m.sum()); k = int(y[m].sum())
        realised = k / n
        expected = float(p[m].mean())
        if method == 'cluster':
            lo, hi = ci_boot.get(gi, (np.nan, np.nan))
        else:
            lo, hi = wilson_ci(k, n)
        ok = bool(lo <= expected <= hi) if np.isfinite(lo) else False
        npass += int(ok)
        rows.append({'grade': g, 'n': n, 'defaults': k, 'realised': realised,
                     'expected': expected, 'ci_low': lo, 'ci_high': hi,
                     'pass': ok})
    df = pd.DataFrame(rows)
    summary = {'method': method, 'n_boot': (n_boot if method == 'cluster' else None),
               'grades_total': len(present), 'grades_passed': npass}
    return df, summary


# ---------------------------------------------------------------------------
# Deployment-relevant backtest: assess the CALIBRATED model, cluster-robust.
# ---------------------------------------------------------------------------
def _ece(y, p, n_bins=10):
    y = np.asarray(y, dtype=float); p = np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    e = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            e += (m.mean()) * abs(y[m].mean() - p[m].mean())
    return float(e)


def deployment_backtest(y, raw_pd, grade_fn, grade_order, groups=None,
                        test_size=0.2, random_state=42, n_boot=1000,
                        floor=0.0003, cap=0.999, hl_g=(10, 5)):
    """The goodness-of-fit the governance gates should actually read.

    Two things every prior gate-evidence script got wrong, fixed here and made
    the default:

    1. It tests the DEPLOYED model, i.e. the isotonically-calibrated PDs, not the
       raw learner OOF. (Raw WOE-logistic PDs can carry per-grade bias that the
       always-on isotonic step removes; testing the raw PDs fails a model nobody
       deploys.) Isotonic is fit on a calibration split and assessed on a
       held-out split, so the calibrator never sees the rows it is judged on.

    2. The split and the per-grade CI are CLUSTER-aware when `groups` is given
       (GroupShuffleSplit + cluster-bootstrap CI), so panel/hazard runs are not
       judged as if their rows were independent.

    `groups=None` -> stratified split + Wilson CI (classical, unchanged).
    Returns a dict with the calibrated per-grade table, pass count, ECE
    (raw vs calibrated), and HL (clustered when groups given).
    """
    from sklearn.isotonic import IsotonicRegression
    y = np.asarray(y, dtype=float)
    raw = np.clip(np.asarray(raw_pd, dtype=float), floor, cap)
    if groups is not None:
        from sklearn.model_selection import GroupShuffleSplit
        groups = np.asarray(groups)
        tr, te = next(GroupShuffleSplit(n_splits=1, test_size=test_size,
                                        random_state=random_state).split(raw, y, groups))
        g_te = groups[te]
        gi = np.unique(g_te, return_inverse=True)[1]; ng = gi.max() + 1
    else:
        from sklearn.model_selection import StratifiedShuffleSplit
        tr, te = next(StratifiedShuffleSplit(n_splits=1, test_size=test_size,
                                             random_state=random_state).split(raw, y))
        g_te = None; gi = None; ng = None

    iso = IsotonicRegression(out_of_bounds='clip').fit(raw[tr], y[tr])
    cal = np.clip(iso.predict(raw[te]), floor, cap)
    grades = np.array([grade_fn(float(x)) for x in cal])
    table, summ = per_grade_backtest(y[te], cal, grades, grade_order, groups=g_te,
                                     n_boot=n_boot, random_state=random_state)
    hls = {g: hosmer_lemeshow(y[te], cal, g=g, group_idx=gi, n_groups=ng) for g in hl_g}
    return {'n_test': int(len(te)), 'method': summ['method'],
            'grades_passed': summ['grades_passed'], 'grades_total': summ['grades_total'],
            'ece_raw': _ece(y[te], raw[te]), 'ece_cal': _ece(y[te], cal),
            'table': table, 'hl': hls, 'clustered': groups is not None}


def backtest_markdown(res):
    """Compact markdown for the deployment backtest result."""
    if not res:
        return ''
    L = ['## Calibration backtest (deployed/calibrated model%s)'
         % (', cluster-robust' if res.get('clustered') else ''), '']
    hl10 = res['hl'].get(10, {})
    hlp = hl10.get('p_adj', hl10.get('p_value'))
    L.append('Held-out n=%d; per-grade **%d/%d** inside the %s 95%% CI; ECE %.4f->%.4f (raw->calibrated); '
             'HL g=10 %s p=%.4f.'
             % (res['n_test'], res['grades_passed'], res['grades_total'],
                'cluster-bootstrap' if res['method'] == 'cluster' else 'Wilson',
                res['ece_raw'], res['ece_cal'],
                '(design-effect adj.)' if hl10.get('clustered') else '', (hlp if hlp is not None else float('nan'))))
    L.append('')
    t = res['table']
    L.append('| Grade | n | realised | expected | CI low | CI high | pass |')
    L.append('|---|--:|--:|--:|--:|--:|:--:|')
    for _, r in t.iterrows():
        L.append('| %s | %d | %.4f | %.4f | %.4f | %.4f | %s |'
                 % (r['grade'], r['n'], r['realised'], r['expected'],
                    r['ci_low'], r['ci_high'], 'PASS' if r['pass'] else 'FAIL'))
    L.append('')
    return '\n'.join(L)
