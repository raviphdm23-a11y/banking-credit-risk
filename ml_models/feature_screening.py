"""
feature_screening.py - IV + Boruta dual-gate feature screening (Phase 1 of
the TAI paper's pipeline: "Feature Screening via IV-Composite Dual-Gate").

Operates on the RAW (pre-encoding) dataframe, before the train/test split,
matching the paper's stated procedure: IV and Boruta are computed on the
full imputed dataset, prior to splitting and prior to any resampling.

Two gates:
  1. Information Value (IV) per raw column, computed via WOE binning. A
     column with IV < iv_min is treated as indistinguishable from noise
     and dropped before Boruta ever sees it (standard credit-risk practice,
     Siddiqi 2005: <0.02 useless, 0.02-0.1 weak, 0.1-0.3 medium, >0.3 strong).
  2. Boruta shadow-feature test (Kursa & Rudnicki 2010) on the IV-surviving
     columns, using a Random Forest and one-hot-encoded/standardised copies
     of any categorical columns for importance estimation only - the
     original numeric/categorical values are what actually get modelled.

     Boruta itself operates on ENCODED columns (a categorical with 5 levels
     becomes 5 dummy columns). A raw column is reported CONFIRMED if at
     least one of its dummies is confirmed (numeric columns map 1:1, so
     this is unambiguous for them) - this is a documented methodological
     choice, not something the original paper's methodology section
     resolves explicitly, so the per-dummy detail is kept alongside the
     raw-column verdict for auditability.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

IV_MIN_DEFAULT = 0.02
BORUTA_PERC_DEFAULT = 90
EPS = 1e-6


def _woe_iv_for_bins(bin_labels, y):
    """WOE/IV given a bin assignment per row and the binary target."""
    df = pd.DataFrame({'bin': bin_labels, 'y': y})
    total_good = (df['y'] == 0).sum()
    total_bad = (df['y'] == 1).sum()
    if total_good == 0 or total_bad == 0:
        return 0.0
    iv = 0.0
    for _, g in df.groupby('bin', observed=True):
        n_good = (g['y'] == 0).sum()
        n_bad = (g['y'] == 1).sum()
        dist_good = (n_good + EPS) / (total_good + EPS)
        dist_bad = (n_bad + EPS) / (total_bad + EPS)
        woe = np.log(dist_good / dist_bad)
        iv += (dist_good - dist_bad) * woe
    return float(iv)


def compute_iv(series, y, max_bins=10):
    """IV for one raw column. Numeric columns are quantile-binned (up to
    max_bins, fewer if the data has ties); non-numeric columns use each
    category as its own bin."""
    s = series.copy()
    if pd.api.types.is_numeric_dtype(s):
        s_filled = s.fillna(s.median())
        try:
            bins = pd.qcut(s_filled, q=max_bins, duplicates='drop')
        except ValueError:
            bins = s_filled  # degenerate (near-constant) column -> single bin, IV ~= 0
        return _woe_iv_for_bins(bins.astype(str), y)
    bins = s.fillna('__missing__').astype(str)
    return _woe_iv_for_bins(bins, y)


def iv_table(df, target_col, max_bins=10):
    """{column: IV} for every non-target column."""
    y = df[target_col].values
    return {c: compute_iv(df[c], y, max_bins) for c in df.columns if c != target_col}


def iv_screen(df, target_col, iv_min=IV_MIN_DEFAULT, max_bins=10):
    ivs = iv_table(df, target_col, max_bins)
    keep = [c for c, v in ivs.items() if v >= iv_min]
    return keep, ivs


def _encode_for_importance(df, cols):
    """One-hot + median-impute + standardise, for Boruta/RF importance
    estimation ONLY - never for the features actually passed to a model."""
    sub = df[cols].copy()
    cat_cols = [c for c in sub.columns if not pd.api.types.is_numeric_dtype(sub[c])]
    num_cols = [c for c in sub.columns if c not in cat_cols]
    if num_cols:
        sub[num_cols] = SimpleImputer(strategy='median').fit_transform(sub[num_cols])
    for c in cat_cols:
        sub[c] = sub[c].fillna('__missing__').astype(str)
    enc = pd.get_dummies(sub, columns=cat_cols, dtype=float) if cat_cols else sub.astype(float)
    Xs = StandardScaler().fit_transform(enc.values)
    # map each encoded (dummy) column back to its raw source column
    raw_of = {}
    for col in enc.columns:
        raw_of[col] = col if col in num_cols else next(c for c in cat_cols if col.startswith(c + '_'))
    return Xs, list(enc.columns), raw_of


def boruta_screen(df, target_col, candidate_cols, perc=BORUTA_PERC_DEFAULT, random_state=42,
                  max_iter=100):
    """Boruta over `candidate_cols` (typically the IV survivors). Returns
    confirmed/tentative/rejected RAW column lists plus per-dummy detail."""
    from boruta import BorutaPy
    if not candidate_cols:
        return {'confirmed': [], 'tentative': [], 'rejected': [], 'dummy_detail': [],
                'perc': perc, 'n_candidate_raw': 0, 'n_encoded': 0}
    Xs, enc_cols, raw_of = _encode_for_importance(df, candidate_cols)
    y = df[target_col].values
    rf = RandomForestClassifier(n_jobs=-1, class_weight='balanced', max_depth=7, random_state=random_state)
    b = BorutaPy(rf, n_estimators='auto', perc=perc, random_state=random_state, verbose=0, max_iter=max_iter)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        b.fit(Xs, y)
    status = {}  # dummy col -> 'confirmed' | 'tentative' | 'rejected'
    for col, sup, tent in zip(enc_cols, b.support_, b.support_weak_):
        status[col] = 'confirmed' if sup else ('tentative' if tent else 'rejected')
    dummy_detail = [{'encoded_column': c, 'raw_column': raw_of[c], 'status': status[c]} for c in enc_cols]
    raw_status = {}
    for c in candidate_cols:
        dummies = [status[e] for e in enc_cols if raw_of[e] == c]
        if any(s == 'confirmed' for s in dummies):
            raw_status[c] = 'confirmed'
        elif any(s == 'tentative' for s in dummies):
            raw_status[c] = 'tentative'
        else:
            raw_status[c] = 'rejected'
    return {
        'confirmed': [c for c, s in raw_status.items() if s == 'confirmed'],
        'tentative': [c for c, s in raw_status.items() if s == 'tentative'],
        'rejected': [c for c, s in raw_status.items() if s == 'rejected'],
        'dummy_detail': dummy_detail,
        'perc': perc, 'n_candidate_raw': len(candidate_cols), 'n_encoded': len(enc_cols),
    }


def screen(df, target_col, iv_min=IV_MIN_DEFAULT, boruta_perc=BORUTA_PERC_DEFAULT,
          max_bins=10, random_state=42, include_tentative=True):
    """Full Phase-1 dual gate. Returns the retained raw column list plus a
    report explaining every drop, for the results log."""
    iv_keep, ivs = iv_screen(df, target_col, iv_min, max_bins)
    boruta = boruta_screen(df, target_col, iv_keep, boruta_perc, random_state)
    retained = boruta['confirmed'] + (boruta['tentative'] if include_tentative else [])
    return {
        'iv_min': iv_min, 'iv_dropped': sorted([c for c, v in ivs.items() if v < iv_min]),
        'iv_values': {c: round(v, 4) for c, v in sorted(ivs.items(), key=lambda kv: -kv[1])},
        'iv_survivor_count': len(iv_keep),
        'boruta': boruta,
        'include_tentative': include_tentative,
        'retained_columns': retained,
        'n_raw_total': len([c for c in df.columns if c != target_col]),
        'n_retained': len(retained),
    }
