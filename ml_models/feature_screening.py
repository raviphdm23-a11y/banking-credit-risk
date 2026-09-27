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
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

IV_MIN_DEFAULT = 0.02
BORUTA_PERC_DEFAULT = 90
CARDINALITY_CAP_DEFAULT = 50
EPS = 1e-6
OTHER_LABEL = '__other__'


def cap_categories(series, max_categories=CARDINALITY_CAP_DEFAULT, other_label=OTHER_LABEL):
    """Collapse all but the `max_categories` most frequent values of a
    categorical series into a single bucket. Without this, a near-identifier
    column (e.g. PAK.csv's RESIDENCIAL_BOROUGH with 14,510 distinct values
    across 50,000 rows) either explodes a one-hot encoding into tens of
    thousands of dummy columns (multi-GB memory for a modest row count) or,
    for a model given native categorical support, wastes search effort and
    invites overfitting on categories that appear only once or twice.
    NaN is left untouched (handled by whatever missing-value strategy the
    caller already applies) - only present, non-null values are capped."""
    counts = series.value_counts()
    if len(counts) <= max_categories:
        return series
    keep = set(counts.index[:max_categories])
    return series.where(series.isna() | series.isin(keep), other_label)


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
        sub[c] = cap_categories(sub[c].fillna('__missing__').astype(str))
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


class MissingValueSafeImputer(BaseEstimator, TransformerMixin):
    """SMOTE and SMOTENC both require the continuous feature part to have no
    missing values at all - they compute real-valued nearest-neighbour
    distances, which are undefined for NaN. This isn't specific to any one
    dataset (GMSC's MonthlyIncome/NumberOfDependents, PAK.csv's numeric
    columns, and any future dataset with real missingness would all hit the
    same error), so it belongs directly in front of the sampler, not as a
    one-off fix. Median-imputes numeric columns and constant-fills
    categorical/'category' dtype columns, fit per call (i.e. per CV fold
    when used as a Pipeline step, so no test-fold statistic leaks into a
    training fold's imputation)."""

    def __init__(self, categorical_placeholder='__missing__'):
        self.categorical_placeholder = categorical_placeholder

    def fit(self, X, y=None):
        self.medians_ = {c: X[c].median() for c in X.columns if pd.api.types.is_numeric_dtype(X[c])}
        return self

    def transform(self, X):
        X = X.copy()
        for c in X.columns:
            if pd.api.types.is_numeric_dtype(X[c]):
                X[c] = X[c].fillna(self.medians_.get(c, 0))
            elif str(X[c].dtype) == 'category':
                if self.categorical_placeholder not in X[c].cat.categories:
                    X[c] = X[c].cat.add_categories([self.categorical_placeholder])
                X[c] = X[c].fillna(self.categorical_placeholder)
            else:
                X[c] = X[c].fillna(self.categorical_placeholder)
        return X


def make_smote_sampler(X, random_state=42, k_neighbors=5):
    """Plain SMOTE requires purely numeric input - it interpolates a synthetic
    point's feature values continuously between neighbours, which is undefined
    for a categorical value. dataset_lab.prepare_features' native-XGBoost path
    leaves categorical columns as pandas 'category' dtype rather than one-hot
    encoding them, so SMOTE would either error or silently corrupt those
    columns. SMOTENC handles mixed numeric/categorical data correctly (it
    copies a neighbour's actual categorical value rather than interpolating),
    so this picks SMOTENC whenever any 'category' dtype column is present,
    and falls back to plain SMOTE otherwise (the one-hot path, where every
    column is already numeric 0/1)."""
    from imblearn.over_sampling import SMOTE, SMOTENC
    cat_mask = [str(dt) == 'category' for dt in X.dtypes] if hasattr(X, 'dtypes') else []
    if any(cat_mask):
        return SMOTENC(categorical_features=cat_mask, random_state=random_state, k_neighbors=k_neighbors)
    return SMOTE(random_state=random_state, k_neighbors=k_neighbors)


def restore_categorical_dtypes(X_resampled, reference_X):
    """SMOTENC's internal encode/resample/decode round-trip can hand back a
    'category' dtype column as plain object/string. Re-cast any column that
    was 'category' dtype in `reference_X` back to it, so a native-categorical
    XGBoost model still sees the dtype it expects after resampling."""
    for c in reference_X.columns:
        if str(reference_X[c].dtype) == 'category' and c in X_resampled.columns:
            X_resampled[c] = X_resampled[c].astype('category')
    return X_resampled


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
