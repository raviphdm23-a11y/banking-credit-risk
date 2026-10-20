"""
binning.py - Stage 1 binning and IV machinery for METHODOLOGY.md v3 (section 4).

Three things v2 lacked:

1. **Monotonic WOE binning** (`woe_bin`) as the primary binning for
   ordinal/continuous columns, replacing v2's fixed 10 quantile bins. This is
   the credit-scoring standard form and makes the IV threshold far less
   arbitrary.

   Monotonicity is enforced only WHERE SUPPORTED. This matters: the project
   found genuinely U-shaped relationships (HMEQ `CLNO`, GMSC
   `NumberRealEstateLoansOrLines` - both real, both economically sensible), and
   blindly forcing monotone bins would destroy exactly the signal the
   methodology's Step 4 shape-diagnosis exists to detect. If enforcement would
   collapse the column below `min_bins_after_monotonic` bins, the
   size-constrained non-monotonic binning is kept instead and
   `monotonic_enforced=False` is reported.

2. **IV bin-count sensitivity** (`iv_sensitivity`) - IV rises with bin count,
   so a fixed-bin IV threshold is not scale-free (review item m2). Reports IV
   under WOE binning and 5/10/20 quantile bins, and flags the column when the
   `IV >= iv_min` verdict FLIPS across them, which routes it to the Stage-1
   model check instead of being decided on IV alone.

3. **Sentinel / shared-missingness indicator extraction**
   (`extract_sentinel_indicators`, `thin_file_indicator`) - METHODOLOGY v3
   section 3.5. Any value that cannot be a literal measurement (GMSC 96/98 in
   late-payment counts; HELOC -7/-8/-9) is recoded as an explicit indicator
   column so the information is attributable to a named Shapley player rather
   than leaking diffusely through many columns.

ASCII-only in emitted strings (Windows cp1252 console).
"""
import numpy as np
import pandas as pd

EPS = 1e-6
MISSING_LABEL = '__missing__'
OTHER_LABEL = '__other__'
IV_MIN_DEFAULT = 0.02


# ---------------------------------------------------------------------------
# WOE / IV primitives
# ---------------------------------------------------------------------------

def _bin_stats(bin_labels, y):
    """Per-bin good/bad counts and event rate, ordered as the labels are."""
    df = pd.DataFrame({'bin': np.asarray(bin_labels), 'y': np.asarray(y)})
    g = df.groupby('bin', observed=True)['y'].agg(['count', 'sum'])
    g.columns = ['n', 'bad']
    g['good'] = g['n'] - g['bad']
    g['event_rate'] = g['bad'] / g['n'].replace(0, np.nan)
    return g


def woe_iv_table(bin_labels, y):
    """WOE and IV contribution per bin, plus the total IV."""
    g = _bin_stats(bin_labels, y)
    total_good = g['good'].sum()
    total_bad = g['bad'].sum()
    if total_good == 0 or total_bad == 0:
        g['woe'] = 0.0
        g['iv_part'] = 0.0
        return g, 0.0
    dist_good = (g['good'] + EPS) / (total_good + EPS)
    dist_bad = (g['bad'] + EPS) / (total_bad + EPS)
    g['woe'] = np.log(dist_good / dist_bad)
    g['iv_part'] = (dist_good - dist_bad) * g['woe']
    return g, float(g['iv_part'].sum())


def iv_from_bins(bin_labels, y):
    """Total IV for a given bin assignment."""
    return woe_iv_table(bin_labels, y)[1]


# ---------------------------------------------------------------------------
# Monotonic WOE binning
# ---------------------------------------------------------------------------

def _merge_small_bins(edges, s, y, min_count):
    """Merge adjacent interval bins until every bin has >= min_count rows."""
    edges = list(edges)
    while len(edges) > 3:
        counts = pd.cut(s, bins=edges, include_lowest=True, duplicates='drop').value_counts(sort=False)
        if counts.min() >= min_count:
            break
        i = int(np.argmin(counts.values))
        # drop the interior edge that dissolves the smallest bin into a neighbour
        drop_at = i if i < len(edges) - 2 else len(edges) - 2
        drop_at = max(1, min(drop_at + 1, len(edges) - 2))
        edges.pop(drop_at)
    return edges


def _monotonic_violations(rates, direction):
    diffs = np.diff(rates)
    return int(np.sum(diffs > 0)) if direction < 0 else int(np.sum(diffs < 0))


def _enforce_monotonic(edges, s, y, direction, min_bins):
    """Merge adjacent bins until the event rate is monotone in `direction`."""
    edges = list(edges)
    while len(edges) - 1 > min_bins:
        binned = pd.cut(s, bins=edges, include_lowest=True, duplicates='drop')
        g = _bin_stats(binned.astype(str), y)
        order = pd.cut(s, bins=edges, include_lowest=True, duplicates='drop').cat.categories.astype(str)
        rates = np.array([g.loc[o, 'event_rate'] if o in g.index else np.nan for o in order], dtype=float)
        if np.isnan(rates).any():
            break
        if _monotonic_violations(rates, direction) == 0:
            break
        diffs = np.diff(rates)
        bad = np.where(diffs > 0)[0] if direction < 0 else np.where(diffs < 0)[0]
        if len(bad) == 0:
            break
        # merge the violating adjacent pair with the smallest rate gap
        i = int(bad[np.argmin(np.abs(diffs[bad]))])
        edges.pop(i + 1)
    return edges


def woe_bin(series, y, min_bin_frac=0.05, max_bins=20, enforce_monotonic=True,
            min_bins_after_monotonic=3, cardinality_cap=50):
    """Bin one raw column for WOE/IV. Returns (bin_labels, info).

    Numeric columns: quantile pre-bins -> small-bin merge -> optional
    monotonicity merge. Missing values are ALWAYS kept as their own
    `__missing__` bin and never merged into a numeric interval, because
    missingness is frequently informative in credit data (and is treated as a
    first-class signal elsewhere in this methodology).

    Non-numeric columns: one bin per level, rare levels pooled into
    `__other__`; monotonicity is not a meaningful concept and is skipped.

    info keys: kind, n_bins, monotonic_enforced, direction, n_missing,
    merged_small, note.
    """
    s = pd.Series(series).reset_index(drop=True)
    y = pd.Series(np.asarray(y)).reset_index(drop=True)
    n = len(s)
    min_count = max(1, int(np.floor(min_bin_frac * n)))
    miss_mask = s.isna()

    if not pd.api.types.is_numeric_dtype(s):
        lab = s.astype('object').where(~miss_mask, MISSING_LABEL).astype(str)
        counts = lab.value_counts()
        if len(counts) > cardinality_cap:
            keep = set(counts.index[:cardinality_cap])
            lab = lab.where(lab.isin(keep), OTHER_LABEL)
        rare = lab.value_counts()
        rare_levels = set(rare.index[rare < min_count]) - {MISSING_LABEL}
        if rare_levels and len(rare) - len(rare_levels) >= 2:
            lab = lab.where(~lab.isin(rare_levels), OTHER_LABEL)
        return lab, {'kind': 'categorical', 'n_bins': int(lab.nunique()),
                     'monotonic_enforced': False, 'direction': 0,
                     'n_missing': int(miss_mask.sum()), 'merged_small': bool(rare_levels),
                     'edges': None, 'levels': sorted(set(lab.astype(str))),
                     'note': 'Categorical: one bin per level, rare levels pooled.'}

    obs = s[~miss_mask]
    if obs.nunique() <= 1:
        lab = pd.Series([MISSING_LABEL if m else 'constant' for m in miss_mask], index=s.index)
        return lab, {'kind': 'constant', 'n_bins': int(lab.nunique()),
                     'monotonic_enforced': False, 'direction': 0,
                     'n_missing': int(miss_mask.sum()), 'merged_small': False,
                     'edges': None, 'levels': sorted(set(lab.astype(str))),
                     'note': 'Near-constant column - no usable bins.'}

    # Count-like / discrete numerics are better left as their own levels than
    # forced into quantile intervals. v2 lost real signal both ways here: IV
    # collapsing to 0.0 on zero-inflated count columns (HMEQ DEROG/DELINQ/NINQ,
    # GMSC late-payment counts), and IV understated 6x on GMSC
    # NumberRealEstateLoansOrLines (0.012 quantile-binned vs 0.072 on raw
    # levels - the latter is where its genuine U-shape lives).
    #
    # Treated as discrete when the column is integer-valued with modest
    # cardinality, or when its mass is concentrated in a handful of levels
    # (the zero-inflated-count signature), in which case quantile cuts mostly
    # land inside a single repeated value and collapse.
    is_intlike = bool(np.all(np.isfinite(obs)) and np.allclose(obs, np.round(obs)))
    top_mass = float(obs.value_counts(normalize=True).head(5).sum())
    discrete = (obs.nunique() <= 12) or (is_intlike and obs.nunique() <= 30) or \
               (is_intlike and top_mass >= 0.80)
    if discrete:
        lab = s.astype('object').where(~miss_mask, MISSING_LABEL).astype(str)
        counts = lab.value_counts()
        rare = set(counts.index[counts < min_count]) - {MISSING_LABEL}
        # Pool rare levels so the chi-square reliability gate downstream is not
        # tripped purely by a thin tail of one-row levels.
        if rare and (len(counts) - len(rare)) >= 2:
            lab = lab.where(~lab.isin(rare), OTHER_LABEL)
        return lab, {'kind': 'numeric_discrete', 'n_bins': int(lab.nunique()),
                     'monotonic_enforced': False, 'direction': 0,
                     'n_missing': int(miss_mask.sum()), 'merged_small': bool(rare),
                     'edges': None, 'levels': sorted(set(lab.astype(str))),
                     'note': 'Discrete/count numeric: raw levels used as bins, rare '
                             'levels pooled (avoids the quantile-collapse artefact '
                             'seen in v2 both directions).'}

    try:
        qs = np.unique(np.nanquantile(obs, np.linspace(0, 1, max_bins + 1)))
    except (ValueError, IndexError):
        qs = np.unique(np.nanquantile(obs, [0, 0.25, 0.5, 0.75, 1.0]))
    if len(qs) < 3:
        lab = s.astype('object').where(~miss_mask, MISSING_LABEL).astype(str)
        return lab, {'kind': 'numeric_discrete', 'n_bins': int(lab.nunique()),
                     'monotonic_enforced': False, 'direction': 0,
                     'n_missing': int(miss_mask.sum()), 'merged_small': False,
                     'edges': None, 'levels': sorted(set(lab.astype(str))),
                     'note': 'Too few distinct quantiles for interval binning.'}
    edges = list(qs.astype(float))
    edges[0] = -np.inf
    edges[-1] = np.inf

    y_obs = y[~miss_mask]
    edges = _merge_small_bins(edges, obs, y_obs, min_count)
    n_bins_pre = len(edges) - 1

    monotonic_enforced = False
    direction = 0
    if enforce_monotonic:
        direction = int(np.sign(pd.Series(obs).corr(pd.Series(y_obs), method='spearman') or 0.0)) or 1
        mono_edges = _enforce_monotonic(edges, obs, y_obs, direction, min_bins_after_monotonic)
        if len(mono_edges) - 1 >= min_bins_after_monotonic:
            binned_try = pd.cut(obs, bins=mono_edges, include_lowest=True, duplicates='drop')
            g = _bin_stats(binned_try.astype(str), y_obs)
            order = binned_try.cat.categories.astype(str)
            rates = np.array([g.loc[o, 'event_rate'] if o in g.index else np.nan for o in order],
                             dtype=float)
            if not np.isnan(rates).any() and _monotonic_violations(rates, direction) == 0:
                edges = mono_edges
                monotonic_enforced = True

    binned = pd.cut(s, bins=edges, include_lowest=True, duplicates='drop').astype(str)
    lab = binned.where(~miss_mask, MISSING_LABEL)
    note = ('Monotonic WOE bins.' if monotonic_enforced else
            'Size-constrained bins; monotonicity NOT enforced (a monotone '
            'relationship was not supported - possible genuine non-monotonic '
            'shape, see METHODOLOGY v3 s4.4 Step 4 shape diagnosis).')
    return lab, {'kind': 'numeric_interval', 'n_bins': int(lab.nunique()),
                 'monotonic_enforced': monotonic_enforced, 'direction': direction,
                 'n_missing': int(miss_mask.sum()),
                 'merged_small': bool(n_bins_pre != max_bins),
                 'edges': [float(e) for e in edges], 'levels': None, 'note': note}


# ---------------------------------------------------------------------------
# IV with explicit binning choice, plus the mandatory sensitivity report
# ---------------------------------------------------------------------------

def _quantile_bins(series, y, bins):
    s = pd.Series(series).reset_index(drop=True)
    miss = s.isna()
    if pd.api.types.is_numeric_dtype(s):
        filled = s.fillna(s.median())
        try:
            lab = pd.qcut(filled, q=bins, duplicates='drop').astype(str)
        except ValueError:
            lab = filled.astype(str)
        return lab.where(~miss, MISSING_LABEL)
    return s.fillna(MISSING_LABEL).astype(str)


def compute_iv(series, y, binning='woe', bins=10, **woe_kwargs):
    """IV for one raw column under an explicit binning choice.

    binning='woe'      monotonic-where-supported WOE binning (v3 primary)
    binning='quantile' fixed `bins` quantile bins (v2 behaviour, kept for the
                       sensitivity report and backwards comparison)
    """
    if binning == 'woe':
        lab, _ = woe_bin(series, y, **woe_kwargs)
    elif binning == 'quantile':
        lab = _quantile_bins(series, y, bins)
    else:
        raise ValueError("binning must be 'woe' or 'quantile', got " + repr(binning))
    return iv_from_bins(lab, y)


def iv_sensitivity(series, y, iv_min=IV_MIN_DEFAULT, **woe_kwargs):
    """IV under WOE and 5/10/20 quantile bins, with a verdict-flip flag.

    `binning_sensitive=True` means the `IV >= iv_min` decision is not stable
    across binning choices, so the column must NOT be decided on IV alone -
    route it to the Stage-1 single-column model check (METHODOLOGY v3 s4.2).
    """
    lab_mono, info_mono = woe_bin(series, y, enforce_monotonic=True, **woe_kwargs)
    woe_iv = iv_from_bins(lab_mono, y)
    lab_free, _ = woe_bin(series, y, enforce_monotonic=False, **woe_kwargs)
    woe_iv_free = iv_from_bins(lab_free, y)

    q = {('q%d' % b): compute_iv(series, y, binning='quantile', bins=b) for b in (5, 10, 20)}
    all_iv = dict(q)
    all_iv['woe'] = woe_iv
    verdicts = {k: (v >= iv_min) for k, v in all_iv.items()}
    out = {k: float(v) for k, v in all_iv.items()}
    out['woe_nonmonotonic'] = float(woe_iv_free)
    out['iv_min'] = float(iv_min)
    out['binning_sensitive'] = bool(len(set(verdicts.values())) > 1)
    out['verdicts'] = verdicts
    out['primary_iv'] = float(woe_iv)
    out['primary_verdict'] = bool(verdicts['woe'])
    out['monotonic_enforced'] = bool(info_mono['monotonic_enforced'])
    out['n_bins'] = int(info_mono['n_bins'])

    # Non-monotonic shape detector. If freeing the monotonicity constraint
    # recovers materially more IV, the relationship is probably genuinely
    # non-monotonic - exactly the HMEQ CLNO / GMSC NumberRealEstateLoansOrLines
    # case (both real U-shapes, both economically sensible). Forcing monotone
    # bins would understate such a column, so flag it for the Step 4 shape
    # diagnosis rather than deciding on the monotone IV.
    rel_cost = ((woe_iv_free - woe_iv) / woe_iv_free) if woe_iv_free > EPS else 0.0
    out['monotonic_iv_cost_relative'] = float(rel_cost)
    out['shape_nonmonotonic'] = bool(info_mono['monotonic_enforced'] and rel_cost >= 0.20)
    # Either flag means "do not decide this column on IV alone".
    out['escalate_to_model_check'] = bool(out['binning_sensitive'] or out['shape_nonmonotonic'])
    return out


# ---------------------------------------------------------------------------
# Sentinel / shared-missingness indicators (METHODOLOGY v3 s3.5)
# ---------------------------------------------------------------------------

def detect_sentinels(df, columns=None, candidates=(-9, -8, -7, 96, 97, 98, 99,
                                                   -999, 999, -99)):
    """Report which candidate sentinel values actually occur, and with what
    event-rate lift. Does not modify anything - this is the audit step.

    Returns {column: {value: {'n': int, 'frac': float}}}.
    """
    cols = columns or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    found = {}
    for c in cols:
        hits = {}
        for v in candidates:
            n = int((df[c] == v).sum())
            if n > 0:
                hits[v] = {'n': n, 'frac': float(n / len(df))}
        if hits:
            found[c] = hits
    return found


def sentinel_lift(df, target, sentinel_map):
    """Event rate inside vs outside each sentinel group - the leakage screen.

    An extreme lift (GMSC 96/98: 60.4% vs 6.6%) is a leakage CANDIDATE and
    must be resolved against a data dictionary before the rows or codes are
    retained (METHODOLOGY v3 s3.5 item 2).
    """
    out = {}
    base = float(df[target].mean())
    for c, values in sentinel_map.items():
        mask = df[c].isin(list(values))
        if mask.sum() == 0:
            continue
        inside = float(df.loc[mask, target].mean())
        outside = float(df.loc[~mask, target].mean())
        out[c] = {'n_sentinel': int(mask.sum()), 'event_rate_sentinel': inside,
                  'event_rate_other': outside, 'base_rate': base,
                  'lift_vs_base': (inside / base) if base > 0 else float('nan'),
                  'leakage_candidate': bool(base > 0 and inside / base >= 3.0)}
    return out


def extract_sentinel_indicators(df, sentinel_map, drop_original_values=True,
                                suffix='_sentinel'):
    """Recode sentinel codes into explicit indicator columns.

    sentinel_map: {column: [values]}. For each column an indicator
    `<col><suffix>` is added (1 where the value is any of the sentinels), and
    if `drop_original_values` the sentinel positions in the original column are
    set to NaN so the numeric range is no longer polluted by non-measurements.

    Where several columns share the SAME sentinel rows (HELOC: the same ~588
    "no data available" rows appear in nearly every column), prefer a single
    shared indicator via `thin_file_indicator` instead of one per column.
    """
    out = df.copy()
    added = []
    for c, values in sentinel_map.items():
        if c not in out.columns:
            continue
        mask = out[c].isin(list(values))
        name = c + suffix
        out[name] = mask.astype(int)
        added.append(name)
        if drop_original_values:
            out.loc[mask, c] = np.nan
    return out, added


def thin_file_indicator(df, sentinel_value=-9, min_columns_frac=0.5, name='thin_file'):
    """One shared indicator for rows carrying the same sentinel across many columns.

    Addresses review item m5: when missingness is correlated across features,
    every subset in the Shapley computation shares a latent "no credit file"
    signal, so the information is not attributable to any one player. Making it
    an explicit column fixes that.

    A row is flagged when `sentinel_value` appears in at least
    `min_columns_frac` of the numeric columns that use that sentinel at all.
    """
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    using = [c for c in num_cols if (df[c] == sentinel_value).any()]
    if not using:
        return df.copy(), None, {'n_columns_using_sentinel': 0, 'n_rows_flagged': 0}
    hit_counts = (df[using] == sentinel_value).sum(axis=1)
    flag = (hit_counts >= max(1, int(np.ceil(min_columns_frac * len(using))))).astype(int)
    out = df.copy()
    out[name] = flag
    return out, name, {'n_columns_using_sentinel': len(using),
                       'columns_using_sentinel': using,
                       'n_rows_flagged': int(flag.sum())}

# ---------------------------------------------------------------------------
# Re-applying a fitted binning, and the leakage-safe WOE encoder used as the
# primary Shapley value-function learner (METHODOLOGY v3 s5.2)
# ---------------------------------------------------------------------------

def apply_bins(series, info):
    """Re-apply a binning fitted elsewhere (train fold) to new data (test fold).

    Interval kinds use the stored cut edges; level-based kinds map unseen levels
    to OTHER_LABEL. Missing stays MISSING_LABEL. This is what keeps the WOE
    transform leakage-free: bins and WOE values are learned on the training
    fold only and then applied unchanged to the held-out fold.
    """
    s = pd.Series(series).reset_index(drop=True)
    miss = s.isna()
    kind = info.get('kind')
    if kind == 'numeric_interval' and info.get('edges'):
        lab = pd.cut(s, bins=info['edges'], include_lowest=True, duplicates='drop').astype(str)
        return lab.where(~miss, MISSING_LABEL)
    lab = s.astype('object').where(~miss, MISSING_LABEL).astype(str)
    levels = info.get('levels')
    if levels:
        lab = lab.where(lab.isin(set(levels)), OTHER_LABEL)
    return lab


class WOEEncoder:
    """Fit monotonic-WOE bins + WOE values per column; transform to WOE floats.

    Primary learner component for METHODOLOGY v3 s5.2: a penalised logistic
    regression on WOE-transformed inputs is the credit-scoring standard form,
    is near-insensitive to hyperparameters, and is deterministic - which removes
    the refit-noise objection that applies to using XGBoost as the Shapley
    value function (review item M9c).

    Fitted strictly on the data passed to `fit` (i.e. one training fold), so
    nothing from a held-out fold informs the bins or the WOE values. Unseen
    test levels map to OTHER_LABEL and, if that level was never seen in
    training, to WOE 0.0 (neutral) rather than an extrapolated value.
    """

    def __init__(self, min_bin_frac=0.05, max_bins=20, enforce_monotonic=True):
        self.min_bin_frac = min_bin_frac
        self.max_bins = max_bins
        self.enforce_monotonic = enforce_monotonic

    def fit(self, X, y):
        X = pd.DataFrame(X).reset_index(drop=True)
        y = pd.Series(np.asarray(y)).reset_index(drop=True)
        self.columns_ = list(X.columns)
        self.bin_info_ = {}
        self.woe_map_ = {}
        for c in self.columns_:
            lab, info = woe_bin(X[c], y, min_bin_frac=self.min_bin_frac,
                                max_bins=self.max_bins,
                                enforce_monotonic=self.enforce_monotonic)
            table, _ = woe_iv_table(lab, y)
            self.bin_info_[c] = info
            self.woe_map_[c] = {str(k): float(v) for k, v in table['woe'].items()}
        return self

    def transform(self, X):
        X = pd.DataFrame(X).reset_index(drop=True)
        out = {}
        for c in self.columns_:
            if c not in X.columns:
                out[c] = np.zeros(len(X))
                continue
            lab = apply_bins(X[c], self.bin_info_[c]).astype(str)
            m = self.woe_map_[c]
            out[c] = lab.map(m).fillna(0.0).to_numpy(dtype=float)
        return pd.DataFrame(out, index=X.index)

    def fit_transform(self, X, y):
        return self.fit(X, y).transform(X)


def adverse_missing_floor(encoder, columns=None):
    """Governance policy (METHODOLOGY v3 s9 — anti-omission): treat an UNKNOWN
    (missing) value as no safer than the worst observed bin, so that *omitting*
    a field can never lower predicted risk.

    For each named column the ``__missing__`` bin's WOE is set to the most-adverse
    (minimum) WOE among that column's non-missing bins, unless it is already at
    least that adverse. Convention here is WOE = ln(%good / %bad), so a LOWER WOE
    means higher risk. Mutates ``encoder.woe_map_`` in place and returns a change
    report.

    USAGE — apply at SCORING time, not before training. Fit the encoder and fit
    the model on the *true* (unfloored) WOE first, THEN call this and score with
    the floored encoder. Flooring *before* the model is fit corrupts the training
    representation: historical rows whose value was genuinely missing (and which
    may have defaulted less) get relabelled as the worst bin, which weakens the
    coefficient and shifts scores for fully-observed applicants too. Scoring-time
    flooring leaves honest/complete applicants unchanged and only removes the
    incentive to omit a field.

    Intended for columns whose missingness is applicant-influenceable (self-
    reported / omittable). Structural-MCAR columns (e.g. a field the lender always
    pulls) can be left out via ``columns``.
    """
    cols = list(columns) if columns is not None else list(encoder.columns_)
    report = {}
    for c in cols:
        m = encoder.woe_map_.get(c, {})
        if MISSING_LABEL not in m:
            continue
        others = [w for k, w in m.items() if k != MISSING_LABEL]
        if not others:
            continue
        worst = min(others)                 # most-adverse observed evidence
        old = m[MISSING_LABEL]
        new = min(old, worst)               # never make 'missing' more protective
        m[MISSING_LABEL] = new
        report[c] = {'old_missing_woe': old, 'worst_bin_woe': worst,
                     'new_missing_woe': new, 'changed': bool(new != old)}
    return report


def mandatory_missing_penalty(encoder, columns):
    """Governance policy for ESSENTIAL columns that were never blank in training
    (METHODOLOGY v3 s9 #10, companion to ``adverse_missing_floor``).

    Such a column has no learned ``__missing__`` bin, so at scoring a blank would
    otherwise map to WOE 0 (neutral) and escape penalty. For each named column this
    SETS/CREATES the ``__missing__`` entry to the column's most-adverse observed
    WOE, so omitting a mandatory field is scored as the worst observed case rather
    than as "no evidence". If a missing bin already exists it is floored (never made
    more protective). Mutates ``encoder.woe_map_`` in place; returns a report.

    This is a POLICY value, not a data estimate: training contains no missing rows
    for the column, so the risk of a blank cannot be learned. The recommended
    first-line control is an upstream validation gate that refuses to score an
    application missing an essential field; this function is the fallback for when
    a score must still be produced.
    """
    report = {}
    for c in columns:
        m = encoder.woe_map_.get(c)
        if not m:
            continue
        others = [w for k, w in m.items() if k != MISSING_LABEL]
        if not others:
            continue
        worst = min(others)
        had = MISSING_LABEL in m
        old = m.get(MISSING_LABEL)
        m[MISSING_LABEL] = worst if not had else min(old, worst)
        report[c] = {'had_missing_bin': bool(had),
                     'worst_bin_woe': float(worst),
                     'missing_woe_set': float(m[MISSING_LABEL])}
    return report
