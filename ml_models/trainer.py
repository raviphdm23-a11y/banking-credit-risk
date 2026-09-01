"""
ML Training Engine for PD (Probability of Default) Model
Orchestrates data ingestion, validation, training, evaluation, and model promotion.
"""

import os
import json
import shutil
import sqlite3
import time
import traceback
import io
import base64
import glob
import threading
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.cm as cm

from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, GroupShuffleSplit, StratifiedKFold, GroupKFold
from sklearn.metrics import (
    roc_auc_score, accuracy_score, precision_score,
    recall_score, f1_score, confusion_matrix, brier_score_loss,
    precision_recall_curve, roc_curve, average_precision_score
)
import joblib

import sys as _sys
_ROOT_FOR_IMPORT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_FOR_IMPORT not in _sys.path:
    _sys.path.insert(0, _ROOT_FOR_IMPORT)
from backend.feature_schema import FEATURE_COLS, REQUIRED_COLUMNS, validate_no_nulls

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAINING_DIR  = os.path.join(_ROOT, 'data', 'training')
ARCHIVE_DIR   = os.path.join(_ROOT, 'data', 'archive')
RUNS_DIR      = os.path.join(_ROOT, 'data', 'runs')
ML_DIR        = os.path.join(_ROOT, 'ml_models')

# Path to bank.db (override with BANK_DB_PATH env var)
BANK_DB_PATH  = os.environ.get('BANK_DB_PATH', os.path.join(_ROOT, 'bank.db'))

MODEL_PATH       = os.path.join(ML_DIR, 'pd_model.pkl')
BACKUP_PATH      = os.path.join(ML_DIR, 'pd_model_backup.pkl')


def bank_key(bank_ids):
    """Stable directory-safe key for a bank selection. None/empty => 'ALL'."""
    if not bank_ids:
        return 'ALL'
    return '_'.join(sorted(bank_ids))
META_PATH        = os.path.join(ML_DIR, 'pd_model_metadata.json')
HISTORY_PATH     = os.path.join(ML_DIR, 'run_history.json')
HPARAM_PATH      = os.path.join(ML_DIR, 'hyperparameters.json')
BENCHMARKS_PATH  = os.path.join(ML_DIR, 'peer_benchmarks.json')

# REQUIRED_COLUMNS / FEATURE_COLS now come from backend.feature_schema — the
# single canonical definition shared with sync_bank_loan_metrics.py's
# validation gate, instead of three independently hand-typed copies (see
# feature_schema.py's docstring for why that divergence was a real bug).
#
# Transaction-derived behavioral features (emi_miss_ratio, n_transactions,
# avg_balance, etc.) are DELIBERATELY EXCLUDED from training (see
# conversation this was decided in): they're only fully known after a loan
# has already concluded, and are close to tautologically tied to the
# Closed/Written-Off label itself. They remain computed and stored in
# bank_loan_metrics for other analysis, just not part of FEATURE_COLS.
TARGET_COL    = 'default_flag'

# ── Bank-scoped auto-discovery (Phase: Taiwan onboarding) ────────────────────
# A bank-scoped training run (bank_ids set, not the shared 'ALL' pool) may
# have real columns in bank_loan_metrics beyond the fixed 37-feature
# canonical FEATURE_COLS list - e.g. BANK011's repay_status_m1..m6,
# bill_amt_m1..m6, credit_limit, etc. These are auto-discovered and added to
# that run's feature set (see run_training()) instead of sitting populated
# but permanently unused. Identity/metadata columns are never features;
# COMPLIANCE_EXCLUDED_COLS are populated in bank_loan_metrics (per "don't
# lose information upfront") but require an explicit, separate compliance
# decision before ever being used as a model input - auto-discovery must
# never silently pull these in just because a bank happens to have the data.
NON_FEATURE_COLS = {
    'id', 'bank_id', 'bank_name', 'loan_id', TARGET_COL, 'pd_observed',
    'observation_date', 'loaded_at', 'country_code', 'exposure_class', 'group_id',
} | (REQUIRED_COLUMNS - set(FEATURE_COLS))
# The REQUIRED_COLUMNS - FEATURE_COLS difference includes previous_default_flag
# (deliberately excluded from FEATURE_COLS as a documented leakage risk - see
# backend/feature_schema.py's docstring) and is_rural. Auto-discovery must
# respect the SAME exclusion the canonical schema already made, not just the
# 37-column list itself - a bank-scoped run finding previous_default_flag
# populated is not license to reintroduce a known leakage risk.
COMPLIANCE_EXCLUDED_COLS = {
    'gender_enc',           # protected characteristic under fair-lending law in most jurisdictions
    'marital_status_enc',   # same category of concern, softer - excluded pending explicit review
    'foreign_worker_flag',  # national-origin-adjacent; confirmed correlated with target in BANK012's
                             # source sample (30.7% vs 10.8% default rate) - exactly the kind of
                             # correlation fair-lending law exists to keep out of underwriting models
}

# Sovereign rating → ordinal (1 = AAA best; higher number = worse credit)
# Lock to prevent concurrent training runs
_training_lock = threading.Lock()
_training_running = False


# ── Database source helpers ───────────────────────────────────────────────────

def scan_db_source():
    """Return info dict for the bank_loan_metrics table, or None if unavailable."""
    if not os.path.exists(BANK_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(BANK_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bank_loan_metrics'")
        if not c.fetchone():
            conn.close()
            return None
        c.execute("SELECT COUNT(*) FROM bank_loan_metrics")
        row_count = c.fetchone()[0]
        c.execute("SELECT MAX(loaded_at) FROM bank_loan_metrics")
        last_loaded = c.fetchone()[0] or 'unknown'
        conn.close()
        stat = os.stat(BANK_DB_PATH)
        return {
            'filename':  'bank_loan_metrics (bank.db)',
            'filepath':  BANK_DB_PATH,
            'size_kb':   round(stat.st_size / 1024, 1),
            'modified':  last_loaded[:16] if last_loaded and last_loaded != 'unknown' else 'unknown',
            'row_count': row_count,
            'source':    'database',
        }
    except Exception:
        return None


def load_from_db(bank_ids=None, exposure_class=None):
    """Load all rows from bank_loan_metrics, optionally restricted to bank_ids
    and/or a single exposure_class (CORPORATE/SME/RETAIL_MORTGAGES/RETAIL_OTHER).

    Macro features (gdp_growth_pct, inflation_cpi_pct, policy_rate_pct,
    unemployment_pct) are stored directly in bank_loan_metrics and backfilled
    from country_macro by sync_bank_loan_metrics.py / seed scripts.
    """
    if not os.path.exists(BANK_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(BANK_DB_PATH)
        # SELECT * (not an explicit column list) - deliberately, after this
        # exact list was found stale THREE separate times (missed Taiwan's
        # columns, then German's, then heloc's/credit_risk's) each time a new
        # Real Earth bank's onboarding script added generic columns that
        # never got added here, silently making that bank's model auto
        # discovery blind to its own real features (heloc's CV AUC came back
        # 0.5 - a coin flip - because every one of its 23 real bureau columns
        # was invisible to this query). SELECT * means a future bank's new
        # columns are visible automatically; nothing downstream assumes a
        # fixed column set - NON_FEATURE_COLS/FEATURE_COLS/auto-discovery all
        # already handle "whatever columns are present" dynamically.
        query = "SELECT * FROM bank_loan_metrics"
        clauses, params = [], []
        if bank_ids:
            placeholders = ','.join('?' * len(bank_ids))
            clauses.append(f"bank_id IN ({placeholders})")
            params.extend(bank_ids)
        if exposure_class:
            clauses.append("exposure_class = ?")
            params.append(exposure_class)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        df = pd.read_sql_query(query, conn, params=params or None)
        conn.close()
        if len(df) == 0:
            return None
        # Fill any missing feature values with column medians. Loans with no
        # transaction history (behavioral columns NULL) get the population
        # median for the miss-ratio/volatility features - a neutral "unknown,
        # assume typical" value rather than 0, which would look artificially
        # clean/risk-free next to loans that do have observed history.
        fill_cols = ('gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
                     'delta_de_ratio', 'delta_cibil', 'months_since_origination',
                     'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct',
                     'delta_unemployment_pct', 'macro_regime_score',
                     'emi_miss_ratio', 'income_miss_ratio', 'income_cv',
                     'income_to_declared_ratio', 'balance_cv', 'max_gap_days',
                     'n_transactions', 'avg_balance',
                     'ecs_bounce_count', 'other_lender_emi_ratio', 'income_disruption_flag',
                     'sector_stress_index', 'ltv_trend_pct')
        for col in fill_cols:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].median())

        # Loudly flag any canonical feature column that's fully NULL (median-fill
        # is a no-op on those, so they'd otherwise train with zero variance and
        # get exactly 0.000000 feature_importances_ with no error anywhere — the
        # exact failure mode that hit macro_regime_score for months undetected).
        full_null_cols = [col for col in FEATURE_COLS
                           if col in df.columns and df[col].isna().all()]
        if full_null_cols:
            print(f'[WARN] bank_loan_metrics: these feature columns are 100% NULL '
                  f'and will contribute zero signal to training: {full_null_cols}')
        return df
    except Exception as e:
        print('[WARN] Could not load from bank.db: {}'.format(e))
        return None


def _validate_dataframe(df, name='data', bank_scoped=False):
    """
    Run the same validation checks as validate_file() on an already-loaded DataFrame.
    Returns (ok: bool, error_message: str | None).

    bank_scoped=True (training on a specific single/multiple bank(s), not
    the shared cross-bank 'ALL' pool): XGBoost natively handles missing
    values in its own tree-split logic - at every node it learns whichever
    default direction (left/right) reduces loss more, and routes NaN rows
    that way at both train and predict time. No imputation, no row-drop
    needed for a feature just being unknown. So for bank_scoped runs, only
    identity/target columns are required non-null; feature-column NaNs
    survive into training instead of silently discarding real rows (this
    was costing Banco Bradesco 65% of its rows - 50,000 down to 17,427 -
    for columns XGBoost could have handled directly).

    Non-bank-scoped (Utopian Earth's combined pool) keeps the original
    strict behavior: a column that's ENTIRELY null is excluded from the
    row-filter (nothing to offer as a per-row signal), but a column with
    only SOME nulls still causes those specific rows to be dropped - the
    combined pool's data is expected to be complete, so a partial null
    there is more likely a genuine data-quality issue than a structural
    onboarding gap.
    """
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return False, 'Missing columns: {}'.format(sorted(missing))

    if bank_scoped:
        strict_required = [c for c in ('bank_id', 'loan_id', 'default_flag', 'observation_date')
                            if c in df.columns]
        df.dropna(subset=strict_required, inplace=True)
    else:
        feature_cols_present = [c for c in list(REQUIRED_COLUMNS)
                                 if c in df.columns and not df[c].isna().all()]
        df.dropna(subset=feature_cols_present, inplace=True)

    if not df['default_flag'].isin([0, 1]).all():
        return False, 'default_flag must be 0 or 1 only'
    for col, lo, hi in [
        ('de_ratio',                    0.0,       10.0),
        ('interest_coverage',           0.0,       20.0),
        ('profitability',             -50.0,      100.0),
        ('liquidity_ratio',             0.1,        5.0),
        ('age',                        18.0,      100.0),
        # employment_type_enc/city_tier_enc/education_enc/residence_type_enc/
        # loan_purpose_enc bounds below were sized to Utopian Earth's fixed
        # taxonomies (7 employment types, 3 city tiers, etc.). Real Earth
        # banks get risk-ordered encodings derived from THEIR OWN category
        # cardinality (see onboard_banco_bradesco.py's _risk_ordered_encoding)
        # which is unpredictable in advance - e.g. Banco Bradesco's
        # RESIDENCE_TYPE has 6 real categories, not Utopian Earth's 4.
        # Widened to a generous, currency/taxonomy-agnostic ceiling.
        ('employment_type_enc',         1.0,       20.0),
        ('years_employed',              0.0,       60.0),
        # Was 100,000-99,999,999 - an INR-only assumption (Utopian Earth's 9
        # banks). Real Earth banks are USD-denominated (see
        # onboard_banco_bradesco.py's currency conversion) - a legitimate,
        # much lower-income population's annual income can genuinely be a
        # few hundred to a few thousand USD. Widened to a currency-agnostic
        # sanity floor (just above zero) rather than an INR-specific band.
        ('annual_income',               1.0, 99999999.0),
        ('foir',                        0.0,        0.9),
        ('num_dependents',              0.0,       20.0),
        ('months_in_residence',         0.0,      900.0),
        ('city_tier_enc',               1.0,       20.0),
        ('education_enc',               1.0,       20.0),
        ('residence_type_enc',          1.0,       20.0),
        ('loan_purpose_enc',            1.0,       20.0),
        ('cibil_score',               300.0,      900.0),
        ('previous_default_flag',       0.0,        1.0),
        ('months_as_customer',          0.0,      600.0),
        ('num_late_payments_past_12m',  0.0,       12.0),
        ('existing_loans_count',        0.0,       10.0),
        ('num_existing_products',       0.0,       20.0),
        ('is_rural',                    0.0,        1.0),
        ('ecs_bounce_count',            0.0,       12.0),
        ('other_lender_emi_ratio',      0.0,        3.0),
        ('income_disruption_flag',      0.0,        1.0),
        ('sector_stress_index',         0.0,      100.0),
        ('ltv_trend_pct',             -50.0,       50.0),
    ]:
        if col not in df.columns:
            return False, 'Missing column: {}'.format(col)
        # A column that's entirely NULL was already excluded from the dropna
        # subset above (bank-scoped onboarding gap, not corrupt data) - a
        # range check against all-NaN values would always evaluate False
        # (NaN comparisons are never True) and reject the whole dataset for
        # a column run_training() is about to legitimately drop anyway.
        if df[col].isna().all():
            continue
        # Range-check only the non-null values. Not bank_scoped: dropna
        # above already removed every row with a null in a partially-
        # populated column, so this is a no-op there (nothing to skip).
        # bank_scoped: NaNs are deliberately still present (XGBoost handles
        # them natively) - a NaN entry isn't a range violation, it's an
        # honest "unknown", and comparing NaN >= lo is always False, which
        # would otherwise fail the whole column for one unknown value.
        non_null = df[col].dropna()
        if not ((non_null >= lo) & (non_null <= hi)).all():
            return False, '{} has values outside valid range [{}, {}]'.format(col, lo, hi)
    if len(df) < 50:
        return False, 'Too few rows ({}); minimum 50 required'.format(len(df))
    return True, None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_hyperparameters():
    with open(HPARAM_PATH, 'r') as f:
        return json.load(f)


def _load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, 'r') as f:
        return json.load(f)


def _save_history(history):
    with open(HISTORY_PATH, 'w') as f:
        json.dump(history, f, indent=2, default=str)


def _fig_to_base64(fig):
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64


def is_training_running():
    return _training_running


# ── Step 1: Scan ──────────────────────────────────────────────────────────────

def scan_training_folder():
    """
    Return list of data source info dicts for the training UI.
    Includes the bank_loan_metrics DB table (primary) plus any CSV files
    in data/training/ (supplementary drop-folder).
    """
    sources = []

    # DB source — always checked first
    db_info = scan_db_source()
    if db_info:
        sources.append(db_info)

    # CSV files in the training drop-folder
    os.makedirs(TRAINING_DIR, exist_ok=True)
    for path in glob.glob(os.path.join(TRAINING_DIR, '*.csv')):
        stat = os.stat(path)
        try:
            row_count = sum(1 for _ in open(path)) - 1
        except Exception:
            row_count = -1
        sources.append({
            'filename':  os.path.basename(path),
            'filepath':  path,
            'size_kb':   round(stat.st_size / 1024, 1),
            'modified':  datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            'row_count': row_count,
            'source':    'csv',
        })

    return sorted(sources, key=lambda x: x['filename'])


# ── Step 2: Validate ──────────────────────────────────────────────────────────

def validate_file(filepath):
    """
    Validate a single CSV file.
    Returns (ok: bool, error_message: str | None, row_count: int).
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return False, f"Cannot read CSV: {e}", 0

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return False, f"Missing columns: {sorted(missing)}", 0

    if df.isnull().any().any():
        null_cols = df.columns[df.isnull().any()].tolist()
        return False, f"Null values in columns: {null_cols}", len(df)

    if not df['default_flag'].isin([0, 1]).all():
        return False, "default_flag must be 0 or 1 only", len(df)

    for col, lo, hi in [
        ('de_ratio',                    0.0,       10.0),
        ('interest_coverage',           0.0,       20.0),
        ('profitability',             -50.0,      100.0),
        ('liquidity_ratio',             0.1,        5.0),
        ('age',                        18.0,      100.0),
        # employment_type_enc/city_tier_enc/education_enc/residence_type_enc/
        # loan_purpose_enc bounds below were sized to Utopian Earth's fixed
        # taxonomies (7 employment types, 3 city tiers, etc.). Real Earth
        # banks get risk-ordered encodings derived from THEIR OWN category
        # cardinality (see onboard_banco_bradesco.py's _risk_ordered_encoding)
        # which is unpredictable in advance - e.g. Banco Bradesco's
        # RESIDENCE_TYPE has 6 real categories, not Utopian Earth's 4.
        # Widened to a generous, currency/taxonomy-agnostic ceiling.
        ('employment_type_enc',         1.0,       20.0),
        ('years_employed',              0.0,       60.0),
        # Was 100,000-99,999,999 - an INR-only assumption (Utopian Earth's 9
        # banks). Real Earth banks are USD-denominated (see
        # onboard_banco_bradesco.py's currency conversion) - a legitimate,
        # much lower-income population's annual income can genuinely be a
        # few hundred to a few thousand USD. Widened to a currency-agnostic
        # sanity floor (just above zero) rather than an INR-specific band.
        ('annual_income',               1.0, 99999999.0),
        ('foir',                        0.0,        0.9),
        ('num_dependents',              0.0,       20.0),
        ('months_in_residence',         0.0,      900.0),
        ('city_tier_enc',               1.0,       20.0),
        ('education_enc',               1.0,       20.0),
        ('residence_type_enc',          1.0,       20.0),
        ('loan_purpose_enc',            1.0,       20.0),
        ('cibil_score',               300.0,      900.0),
        ('previous_default_flag',       0.0,        1.0),
        ('months_as_customer',          0.0,      600.0),
        ('num_late_payments_past_12m',  0.0,       12.0),
        ('existing_loans_count',        0.0,       10.0),
        ('num_existing_products',       0.0,       20.0),
        ('is_rural',                    0.0,        1.0),
        ('ecs_bounce_count',            0.0,       12.0),
        ('other_lender_emi_ratio',      0.0,        3.0),
        ('income_disruption_flag',      0.0,        1.0),
        ('sector_stress_index',         0.0,      100.0),
        ('ltv_trend_pct',             -50.0,       50.0),
    ]:
        if col not in df.columns:
            return False, f"Missing column: {col}", len(df)
        if not ((df[col] >= lo) & (df[col] <= hi)).all():
            return False, f"{col} has values outside valid range [{lo}, {hi}]", len(df)

    if len(df) < 50:
        return False, f"Too few rows ({len(df)}); minimum 50 required", len(df)

    return True, None, len(df)


# ── Step 3: Load & merge ──────────────────────────────────────────────────────

def load_from_enriched_transactions(bank_ids=None, exposure_class=None, include_active=False):
    """
    Load transaction-level enriched data from transactions table, optionally
    restricted to bank_ids and/or a single exposure_class.
    Only rows belonging to loans with a completed lifecycle (status =
    'Closed' or 'Written-Off') are included by default - an 'Active' loan's
    outcome hasn't resolved yet, so promoting a model trained against it
    would train against a status that can still change rather than the
    loan's real outcome. include_active=True lifts that restriction - for
    read-only research sampling (e.g. Model Lab's SHAP tooling) where
    nothing gets promoted, not for anything that calls train_model().
    Returns DataFrame with all enriched ML features.
    """
    conn = sqlite3.connect(BANK_DB_PATH)

    query = """
        SELECT
            t.id as loan_id, t.bank_id,
            t.loan_id_ref as group_id,
            t.cust_age as age, t.cust_annual_income as annual_income,
            t.cust_cibil_score as cibil_score, t.cust_is_rural as is_rural,
            t.cust_years_employed as years_employed, t.cust_foir_declared as foir,
            t.cust_num_dependents as num_dependents,
            COALESCE(k.months_as_customer, 0) as months_as_customer,
            COALESCE(k.num_late_payments_past_12m, 0) as num_late_payments_past_12m,
            COALESCE(k.num_existing_products, 1) as num_existing_products,
            t.loan_de_ratio as de_ratio, t.loan_interest_coverage as interest_coverage,
            t.loan_profitability as profitability, t.loan_liquidity_ratio as liquidity_ratio,
            t.loan_pd_score, t.loan_classification,
            t.macro_gdp_growth_pct as gdp_growth_pct, t.macro_inflation_cpi_pct as inflation_cpi_pct,
            t.macro_policy_rate_pct as policy_rate_pct,
            t.macro_unemployment_pct as unemployment_pct,
            t.delta_de_ratio, t.delta_cibil, t.delta_gdp_pct, t.macro_regime_score,
            t.months_since_origination,
            t.employment_type_enc, t.city_tier_enc, t.education_enc, t.residence_type_enc,
            t.loan_purpose_enc, t.loan_classification_enc,
            t.default_flag,
            t.date as observation_date,
            t.delta_cpi_pct, t.delta_policy_rate_pct, t.delta_unemployment_pct,
            0 as previous_default_flag,
            1 as existing_loans_count,
            blm.emi_miss_ratio, blm.income_miss_ratio, blm.income_cv,
            blm.income_to_declared_ratio, blm.balance_cv, blm.max_gap_days,
            blm.n_transactions, blm.avg_balance, blm.exposure_class
        FROM transactions t
        LEFT JOIN accounts a ON t.aid = a.id
        LEFT JOIN customer_kyc k ON a.cid = k.cid
        LEFT JOIN bank_loan_metrics blm ON t.loan_id_ref = blm.loan_id
        JOIN loans lo ON lo.id = t.loan_id_ref
        WHERE t.default_flag IS NOT NULL
            AND t.cust_age IS NOT NULL
            AND t.cust_annual_income IS NOT NULL
            AND t.loan_de_ratio IS NOT NULL
            AND t.loan_interest_coverage IS NOT NULL
            AND t.loan_classification IS NOT NULL
    """
    if not include_active:
        query += " AND lo.status IN ('Closed', 'Written-Off')"

    params = []
    if bank_ids:
        placeholders = ','.join('?' * len(bank_ids))
        query += f" AND t.bank_id IN ({placeholders})"
        params.extend(bank_ids)
    if exposure_class:
        query += " AND blm.exposure_class = ?"
        params.append(exposure_class)
    params = params or None

    df = pd.read_sql(query, con=conn, params=params)
    conn.close()

    if df is not None and len(df) > 0:
        # Loans without a matching bank_loan_metrics row (no transaction
        # history at seed time, or joined loan_id mismatch) get the
        # population median for behavioral features - neutral "unknown,
        # assume typical" rather than 0 (which would look risk-free).
        behavioral_cols = ('emi_miss_ratio', 'income_miss_ratio', 'income_cv',
                            'income_to_declared_ratio', 'balance_cv', 'max_gap_days',
                            'n_transactions', 'avg_balance')
        for col in behavioral_cols:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].median())
        print(f"[TRAIN] Loaded {len(df)} enriched transactions from database")
        return df
    else:
        print("[TRAIN] No enriched transactions found in database")
        return None


def load_and_merge(use_transaction_level=False, bank_ids=None, exposure_class=None):
    """
    Load training data from available sources, optionally restricted to a
    subset of banks (bank_ids: list of bank_id strings, e.g. ['BANK001']) and/or
    a single exposure_class (CORPORATE/SME/RETAIL_MORTGAGES/RETAIL_OTHER).
    If use_transaction_level=True: Load from enriched transactions table (84K rows)
    If use_transaction_level=False: Load from bank_loan_metrics (customer-level, 1.1K rows)

    Returns (DataFrame, files_used, files_skipped, dupes).
    """
    frames     = []
    files_used = []
    files_skip = []
    bank_label = f" [banks: {', '.join(bank_ids)}]" if bank_ids else ""
    seg_label  = f" [segment: {exposure_class}]" if exposure_class else ""

    # --- PRIMARY DATA SOURCE (MUTUALLY EXCLUSIVE) ---
    if use_transaction_level:
        print(f"[TRAIN] Using TRANSACTION-LEVEL data source (56K+ enriched transactions){bank_label}{seg_label}")
        txn_df = load_from_enriched_transactions(bank_ids=bank_ids, exposure_class=exposure_class)
        if txn_df is None or len(txn_df) == 0:
            print("[TRAIN] ERROR: load_from_enriched_transactions() returned EMPTY!")
            raise ValueError('[TRAIN] CRITICAL: No enriched transactions loaded for the selected bank(s)/segment! Check database or SQL.')
        print(f"[TRAIN] SUCCESS: Loaded {len(txn_df):,} enriched transactions")
        frames.append(txn_df)
        files_used.append({
            'filename': f'enriched_transactions (bank.db - TRANSACTION LEVEL){bank_label}{seg_label}',
            'rows': len(txn_df)
        })
    else:
        print(f"[TRAIN] Using CUSTOMER-LEVEL data source (bank_loan_metrics){bank_label}{seg_label}")
        db_df = load_from_db(bank_ids=bank_ids, exposure_class=exposure_class)
        if db_df is not None:
            # bank_scoped=True (single/multiple specific banks, not the
            # shared cross-bank pool): XGBoost natively handles missing
            # values via its own tree-split logic, so don't drop rows just
            # because a feature column is unknown for them - see
            # _validate_dataframe's docstring.
            ok, err = _validate_dataframe(db_df, 'bank_loan_metrics', bank_scoped=bool(bank_ids))
            if ok:
                frames.append(db_df)
                files_used.append({'filename': f'bank_loan_metrics (bank.db - CUSTOMER LEVEL){bank_label}{seg_label}', 'rows': len(db_df)})
            else:
                files_skip.append({'filename': 'bank_loan_metrics (bank.db)', 'reason': err})

    # --- Supplementary source: CSV files in data/training/ ---
    # Only merge CSVs with customer-level data (not transaction-level)
    # Transaction-level data is now realistic at the source (seed scripts + migration)
    # Skipped entirely when a bank or segment filter is active - CSV drop-files
    # aren't scoped to a specific bank/segment selection, so mixing them in
    # would silently reintroduce data outside the requested subset.
    if not use_transaction_level and not bank_ids and not exposure_class:
        csv_sources = [s for s in scan_training_folder() if s.get('source') == 'csv']
        for f in csv_sources:
            ok, err, rows = validate_file(f['filepath'])
            if ok:
                df = pd.read_csv(f['filepath'])
                frames.append(df)
                files_used.append({'filename': f['filename'], 'rows': rows})
            else:
                files_skip.append({'filename': f['filename'], 'reason': err})

    if not frames:
        raise ValueError(
            'No valid training data found. '
            'Check enriched_transactions or bank_loan_metrics table, '
            'and ensure data/training/ contains CSV files if needed.'
        )

    merged = pd.concat(frames, ignore_index=True)

    # Deduplicate ONLY for customer-level data (bank_loan_metrics)
    # Transaction-level data should NOT be deduplicated - each transaction is a separate sample
    dupes = 0
    if not use_transaction_level:
        before = len(merged)
        merged = merged.drop_duplicates(subset='loan_id', keep='first')
        dupes  = before - len(merged)

    if len(merged) < 50:
        raise ValueError('Only {} rows after deduplication; minimum 50 required'.format(len(merged)))

    return merged, files_used, files_skip, dupes


# ── Step 4: Train ─────────────────────────────────────────────────────────────

def _build_xgboost(X_train, y_train, hp):
    """Build XGBoost classifier."""
    model_hp = hp.get('models', {}).get('xgboost', hp.get('model', {}))

    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    auto_spw = round(n_neg / n_pos, 2) if n_pos > 0 else 1.0

    model = XGBClassifier(
        n_estimators      = int(model_hp.get('n_estimators', 200)),
        max_depth         = int(model_hp.get('max_depth', 4)),
        learning_rate     = float(model_hp.get('learning_rate', 0.05)),
        subsample         = float(model_hp.get('subsample', 0.8)),
        colsample_bytree  = float(model_hp.get('colsample_bytree', 0.8)),
        min_child_weight  = int(model_hp.get('min_child_weight', 5)),
        gamma             = float(model_hp.get('gamma', 0.1)),
        reg_alpha         = float(model_hp.get('reg_alpha', 0.1)),
        reg_lambda        = float(model_hp.get('reg_lambda', 1.0)),
        scale_pos_weight  = auto_spw,
        random_state      = int(model_hp.get('random_state', 42)),
        eval_metric       = 'logloss',
        verbosity         = 0,
        n_jobs            = -1,
    )
    model.fit(X_train, y_train)
    return model


def _build_logistic_regression(X_train, y_train, hp):
    """Build Logistic Regression classifier (with scaling).

    Adds a median-imputer step ahead of scaling - LogisticRegression can't
    accept NaN natively (confirmed via a real training failure on a
    bank-scoped Real Earth bank, not anticipated in advance: this was
    already broken for every Real Earth bank before this fix, same
    technical requirement as the tree-ensemble builders below)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    lr_hp = hp.get('models', {}).get('logistic_regression', {})
    pipe = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=float(lr_hp.get('C', 1.0)),
            penalty=lr_hp.get('penalty', 'l2'),
            solver=lr_hp.get('solver', 'lbfgs'),
            max_iter=int(lr_hp.get('max_iter', 1000)),
            class_weight=lr_hp.get('class_weight', 'balanced'),
            random_state=int(lr_hp.get('random_state', 42)),
        )),
    ])
    pipe.fit(X_train, y_train)
    return pipe


# ── Tree-ensemble comparison models (bagging + a second boosting
# implementation, genuinely different architectures from XGBoost) ───────────
#
# IMPORTANT: unlike XGBoost, none of sklearn's RandomForestClassifier,
# ExtraTreesClassifier, or GradientBoostingClassifier can handle NaN inputs
# natively - they raise on fit/predict if given one. This platform's
# bank-scoped Real Earth training relies on XGBoost's native missing-value
# routing specifically so genuinely-unfilled fields never need a fabricated
# default (see allow_missing_features_ / model_feature_frame()). These three
# model types wrap a SimpleImputer(strategy='median') as the first Pipeline
# step - a technical requirement of the algorithm, not a policy reversal:
# the imputer learns its median from the TRAINING data only (fit once,
# reused identically at predict/live-inference time via the same saved
# Pipeline object), so it's an honest, consistent, non-fabricated fallback -
# just a different mechanism than XGBoost's tree-routing one. XGBoost
# remains the only model type that sees genuine NaN as NaN.
def _build_random_forest(X_train, y_train, hp):
    """Bagging ensemble - each tree trained independently on a bootstrap
    resample and averaged, not sequentially error-correcting like boosting.
    Genuinely different bias/variance behavior from XGBoost, useful as a
    real architectural comparison point."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    rf_hp = hp.get('models', {}).get('random_forest', {})
    pipe = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', RandomForestClassifier(
            n_estimators=int(rf_hp.get('n_estimators', 300)),
            max_depth=rf_hp.get('max_depth', 8),
            min_samples_leaf=int(rf_hp.get('min_samples_leaf', 5)),
            max_features=rf_hp.get('max_features', 'sqrt'),
            class_weight=rf_hp.get('class_weight', 'balanced'),
            random_state=int(rf_hp.get('random_state', 42)),
            n_jobs=-1,
        )),
    ])
    pipe.fit(X_train, y_train)
    return pipe


def _build_extra_trees(X_train, y_train, hp):
    """Extremely Randomized Trees - another bagging ensemble like Random
    Forest, but split thresholds are chosen randomly rather than optimally
    at each node. Faster to train and often more robust to overfitting on
    noisy tabular data than Random Forest."""
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    et_hp = hp.get('models', {}).get('extra_trees', {})
    pipe = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', ExtraTreesClassifier(
            n_estimators=int(et_hp.get('n_estimators', 300)),
            max_depth=et_hp.get('max_depth', 8),
            min_samples_leaf=int(et_hp.get('min_samples_leaf', 5)),
            max_features=et_hp.get('max_features', 'sqrt'),
            class_weight=et_hp.get('class_weight', 'balanced'),
            random_state=int(et_hp.get('random_state', 42)),
            n_jobs=-1,
        )),
    ])
    pipe.fit(X_train, y_train)
    return pipe


def _build_gradient_boosting(X_train, y_train, hp):
    """sklearn's own boosting implementation - a genuinely different
    algorithm from XGBoost's (no native missing-value routing, no XGBoost-
    style regularization terms), useful as a boosting-vs-boosting comparison
    point specifically, not just boosting-vs-bagging.

    GradientBoostingClassifier has no class_weight parameter (unlike
    RandomForest/ExtraTrees/LogisticRegression) - approximated via
    per-sample weights instead, computed the same 'balanced' way."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.utils.class_weight import compute_sample_weight

    gb_hp = hp.get('models', {}).get('gradient_boosting', {})
    pipe = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', GradientBoostingClassifier(
            n_estimators=int(gb_hp.get('n_estimators', 200)),
            max_depth=int(gb_hp.get('max_depth', 3)),
            learning_rate=float(gb_hp.get('learning_rate', 0.05)),
            subsample=float(gb_hp.get('subsample', 0.8)),
            min_samples_leaf=int(gb_hp.get('min_samples_leaf', 5)),
            random_state=int(gb_hp.get('random_state', 42)),
        )),
    ])
    # GradientBoostingClassifier has no class_weight param - pass balanced
    # sample_weight through to the 'clf' step via Pipeline's standard
    # stepname__paramname fit-param routing, so Pipeline.fit() still runs
    # normally end-to-end (feature_names_in_ etc. set correctly, same as
    # every other pipeline here) rather than hand-assembling pre-fit steps.
    sample_weight = compute_sample_weight(class_weight='balanced', y=y_train)
    pipe.fit(X_train, y_train, clf__sample_weight=sample_weight)
    return pipe


MODEL_BUILDERS = {
    'xgboost': _build_xgboost,
    'logistic_regression': _build_logistic_regression,
    'random_forest': _build_random_forest,
    'extra_trees': _build_extra_trees,
    'gradient_boosting': _build_gradient_boosting,
}


def train_model(X_train, y_train, hp, model_type='xgboost'):
    """Dispatcher to build model by type."""
    builder = MODEL_BUILDERS.get(model_type)
    if builder is None:
        raise ValueError(f"Unknown model_type: {model_type}. Must be one of: {list(MODEL_BUILDERS.keys())}")
    return builder(X_train, y_train, hp)


# ── Step 5: Evaluate ──────────────────────────────────────────────────────────

def evaluate_model(model, X_test, y_test, df_test, threshold):
    """
    Compute classification metrics.
    y_test IS default_flag (binary). Model outputs predict_proba → probability of default.
    """
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_true_bin   = y_test.values          # already binary (0/1)
    y_pred_bin   = (y_pred_proba >= threshold).astype(int)

    auc    = float(roc_auc_score(y_true_bin, y_pred_proba)) if len(np.unique(y_true_bin)) > 1 else 0.5
    # ROC-AUC is insensitive to class balance and can look deceptively strong
    # with only a handful of positives (ranking the few defaulters above the
    # bulk of non-defaulters is "easy" even for an overfit model). PR-AUC
    # (average precision) is far more sensitive to whether the model is
    # actually separating classes vs. just getting lucky on a tiny positive
    # count - a large gap between the two is itself a red flag.
    pr_auc = float(average_precision_score(y_true_bin, y_pred_proba)) if len(np.unique(y_true_bin)) > 1 else None
    acc    = float(accuracy_score(y_true_bin, y_pred_bin))
    prec   = float(precision_score(y_true_bin, y_pred_bin, zero_division=0))
    rec    = float(recall_score(y_true_bin, y_pred_bin, zero_division=0))
    f1     = float(f1_score(y_true_bin, y_pred_bin, zero_division=0))
    brier  = float(brier_score_loss(y_true_bin, y_pred_proba))
    cm     = confusion_matrix(y_true_bin, y_pred_bin, labels=[0, 1]).tolist()

    metrics = {
        'auc_roc':   round(auc, 4),
        'pr_auc':    round(pr_auc, 4) if pr_auc is not None else None,
        'accuracy':  round(acc, 4),
        'precision': round(prec, 4),
        'recall':    round(rec, 4),
        'f1':        round(f1, 4),
        'brier_score': round(brier, 6),
        'n_test':    int(len(y_true_bin)),
        'n_defaults': int(y_true_bin.sum()),
        'default_rate': round(float(y_true_bin.mean()), 4),
    }
    return metrics, cm, y_pred_proba


def cross_validate_model(X, y, hp, model_type, groups=None, n_splits=5):
    """
    Honest generalization estimate via stratified (or grouped) k-fold CV.

    A single train/test split is not trustworthy on a dataset with very few
    positive examples (e.g. ~15-20 defaults): whichever handful of defaults
    happens to land in the test fold dominates the reported AUC, so the same
    model can show anywhere from ~0.45 to ~1.0 depending only on the random
    seed. Averaging over multiple folds is the only way to see whether a
    training run's headline single-split number is representative or just
    lucky/unlucky - this is what the admin dashboard's "Rows Trained" /
    "AUC-ROC" card was missing.

    If groups is provided (transaction-level training), use GroupKFold so an
    entire loan's rows stay on one side of every fold - the same leakage
    concern that GroupShuffleSplit addresses for the primary train/test split
    applies here too, per-fold.

    n_splits is capped to the positive-class count (need >=1 positive example
    per fold) so this degrades gracefully instead of erroring on tiny samples.
    """
    n_pos = int(y.sum())
    n_splits_eff = max(2, min(n_splits, n_pos)) if n_pos >= 2 else None
    if n_splits_eff is None:
        return {
            'n_splits': 0, 'fold_aucs': [], 'mean_auc': None, 'std_auc': None,
            'note': f'Too few positive examples ({n_pos}) for cross-validation',
        }

    if groups is not None:
        gkf = GroupKFold(n_splits=n_splits_eff)
        splitter = gkf.split(X, y, groups=groups)
    else:
        skf = StratifiedKFold(n_splits=n_splits_eff, shuffle=True, random_state=42)
        splitter = skf.split(X, y)

    fold_aucs = []
    for train_idx, test_idx in splitter:
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        if len(np.unique(y_te)) < 2:
            continue  # fold has only one class present - AUC undefined, skip
        fold_model = train_model(X.iloc[train_idx], y_tr, hp, model_type=model_type)
        proba = fold_model.predict_proba(X.iloc[test_idx])[:, 1]
        fold_aucs.append(float(roc_auc_score(y_te, proba)))

    if not fold_aucs:
        return {
            'n_splits': n_splits_eff, 'fold_aucs': [], 'mean_auc': None, 'std_auc': None,
            'note': 'No fold had both classes present',
        }

    return {
        'n_splits': n_splits_eff,
        'fold_aucs': [round(a, 4) for a in fold_aucs],
        'mean_auc': round(float(np.mean(fold_aucs)), 4),
        'std_auc': round(float(np.std(fold_aucs)), 4),
        'note': None,
    }


# ── Trustworthiness diagnostics ────────────────────────────────────────────────
# Small-sample warning signs that a headline AUC alone won't surface - see the
# conversation this was built from: with a handful of positive examples, an
# XGBoost model with dozens of features can rank the few known defaulters
# above everyone else (a high AUC) purely by fitting to their specific
# fingerprint, not by learning a generalizable pattern.

MIN_EPV_ACCEPTABLE = 10   # Peduzzi et al. rule of thumb floor
MIN_EPV_COMFORTABLE = 20


def compute_epv(n_events, n_features):
    """
    Events-per-variable: minority-class training examples / feature count.
    Standard statistical guidance for stable model estimation is EPV >= 10
    (>= 20 preferred) - below that, the model has more degrees of freedom
    than the data can responsibly support, so it substantially risks fitting
    the specific training examples rather than a generalizable pattern.
    """
    if n_features <= 0:
        return None
    epv = round(n_events / n_features, 2)
    if epv < MIN_EPV_ACCEPTABLE:
        risk = 'high'
    elif epv < MIN_EPV_COMFORTABLE:
        risk = 'moderate'
    else:
        risk = 'low'
    return {'epv': epv, 'n_events': n_events, 'n_features': n_features,
            'overfitting_risk': risk,
            'note': f'Rule of thumb: EPV >= {MIN_EPV_ACCEPTABLE} acceptable, '
                    f'>= {MIN_EPV_COMFORTABLE} comfortable (Peduzzi et al.).'}


def baseline_cibil_predictions(X_train, y_train, X_test):
    """
    Trains a trivial single-feature (CIBIL score only) logistic regression on
    the same split as the real model, and returns its predicted probabilities
    on the test set (aligned index-for-index with X_test) - the raw material
    both baseline_cibil_auc() and bootstrap_auc_lift() need. Returns None if
    CIBIL isn't in the feature set.
    """
    if 'cibil_score' not in X_train.columns:
        return None
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(class_weight='balanced', max_iter=1000)
    clf.fit(X_train[['cibil_score']], y_train)
    return clf.predict_proba(X_test[['cibil_score']])[:, 1]


def baseline_cibil_auc(X_train, y_train, X_test, y_test):
    """
    AUC of the CIBIL-only baseline against real test-set outcomes. If the
    full model's AUC isn't meaningfully better than this, the other 38
    features aren't contributing real signal - the model is just adding
    capacity to overfit, not accuracy. Returns None if CIBIL isn't in the
    feature set or the test split has only one class present (AUC undefined).
    """
    proba = baseline_cibil_predictions(X_train, y_train, X_test)
    if proba is None or len(np.unique(y_test)) < 2:
        return None
    return float(roc_auc_score(y_test, proba))


def bootstrap_auc_lift(y_test, proba_full, proba_baseline, n_bootstrap=1000, random_state=42):
    """
    Paired bootstrap test of whether the full model's AUC is *significantly*
    better than the CIBIL-only baseline's AUC on the same test set - not
    just numerically higher. Both models already produced fixed PD scores
    per test loan; this resamples which loans get counted (with
    replacement) many times and recomputes AUC_full - AUC_baseline each
    time, using the real observed default_flag as the ground truth both
    scores are judged against (agreement between the two models' scores is
    never compared - only each one's accuracy against what actually
    happened). If the resulting distribution's 95% interval excludes zero,
    the lift is distinguishable from noise given the available test-set
    size; if it straddles zero, the apparent lift could vanish on a
    different random draw of the same population and shouldn't be trusted.

    Returns None if CIBIL baseline unavailable or the test set has too few
    of either class to resample meaningfully.
    """
    if proba_baseline is None or len(np.unique(y_test)) < 2:
        return None

    y = np.asarray(y_test)
    n = len(y)
    rng = np.random.RandomState(random_state)

    diffs = []
    for _ in range(n_bootstrap):
        idx = rng.randint(0, n, size=n)
        y_bs = y[idx]
        if len(np.unique(y_bs)) < 2:
            continue  # can't score AUC on a resample with only one class present
        auc_full_bs = roc_auc_score(y_bs, proba_full[idx])
        auc_base_bs = roc_auc_score(y_bs, proba_baseline[idx])
        diffs.append(auc_full_bs - auc_base_bs)

    if len(diffs) < n_bootstrap * 0.5:
        return {'n_valid_resamples': len(diffs), 'n_bootstrap': n_bootstrap,
                'note': 'Too few resamples had both classes present - test set is too small/imbalanced for this check.',
                'significant': None, 'mean_lift': None, 'ci_95': None, 'p_value_two_sided': None}

    diffs = np.array(diffs)
    ci_low, ci_high = np.percentile(diffs, [2.5, 97.5])
    significant = bool(ci_low > 0 or ci_high < 0)   # 95% interval excludes zero
    # Two-sided bootstrap p-value: 2x the smaller tail proportion crossing zero.
    p_value = float(min(1.0, 2 * min((diffs <= 0).mean(), (diffs >= 0).mean())))

    return {
        'n_valid_resamples': int(len(diffs)), 'n_bootstrap': n_bootstrap,
        'mean_lift': round(float(diffs.mean()), 4),
        'ci_95': [round(float(ci_low), 4), round(float(ci_high), 4)],
        'significant': significant,
        'p_value_two_sided': round(p_value, 4),
        'note': None,
    }


# ── Step 6: Charts ────────────────────────────────────────────────────────────

def _get_feature_importance(model, n_features=None):
    """Extract feature importance from model (tree-based or linear)."""
    try:
        # Tree-based models (XGBoost, RandomForest, etc.)
        return model.feature_importances_
    except AttributeError:
        try:
            # Pipeline with a tree-ensemble model inside (RandomForest,
            # ExtraTrees, GradientBoosting - all wrapped with an imputer
            # step, see _build_random_forest/_build_extra_trees/
            # _build_gradient_boosting)
            return model.named_steps['clf'].feature_importances_
        except (AttributeError, KeyError):
            try:
                # Pipeline with Linear model inside
                return np.abs(model.named_steps['clf'].coef_[0])
            except (AttributeError, KeyError):
                try:
                    # Direct linear model (LogisticRegression, etc.)
                    return np.abs(model.coef_[0])
                except (AttributeError, IndexError):
                    # Fallback: equal importance for all features. n_features
                    # must match whatever was actually trained on (a bank-scoped
                    # run may use fewer than the full FEATURE_COLS) - not a
                    # hardcoded canonical-schema length, or the chart's bar
                    # count would mismatch its label count.
                    return np.ones(n_features if n_features is not None else len(FEATURE_COLS))


def generate_charts(model, X_test, y_test, y_pred, df_test, threshold):
    """Generate 6 evaluation charts, return dict of base64 PNG strings."""
    charts = {}
    y_true_bin = df_test['default_flag'].values
    for _style in ('seaborn-v0_8-whitegrid', 'seaborn-whitegrid', 'ggplot', 'default'):
        try:
            plt.style.use(_style)
            break
        except OSError:
            continue

    # 1. Feature Importance
    fig, ax = plt.subplots(figsize=(7, 4))
    importances = _get_feature_importance(model, n_features=len(X_test.columns))
    # X_test.columns, not the module-global FEATURE_COLS - a bank-scoped run
    # may have trained on a REDUCED feature set (see run_training()'s
    # active_feature_cols), and importances is positionally aligned to
    # whatever was actually in X_test, not the full canonical schema.
    # Using FEATURE_COLS here would silently mislabel every bar past the
    # first dropped column.
    feature_names_for_chart = list(X_test.columns)
    idx = np.argsort(importances)
    ax.barh([feature_names_for_chart[i] for i in idx], importances[idx], color='#2196F3')
    ax.set_title('Feature Importance', fontsize=13, fontweight='bold')
    ax.set_xlabel('Importance Score')
    ax.tick_params(axis='y', labelsize=10)
    charts['feature_importance'] = _fig_to_base64(fig)

    # 2. ROC Curve
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true_bin, y_pred)
    auc_val = roc_auc_score(y_true_bin, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, color='#2196F3', lw=2, label=f'AUC = {auc_val:.3f}')
    ax.plot([0, 1], [0, 1], 'k--', lw=1)
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title('ROC Curve', fontsize=13, fontweight='bold')
    ax.legend(loc='lower right')
    charts['roc_curve'] = _fig_to_base64(fig)

    # 3. Confusion Matrix
    # labels=[0, 1] forces a 2x2 matrix even when the test split happens to
    # contain only one class (e.g. a small/filtered bank subset with very
    # few defaults, where a group-aware split can push all positives to train).
    cm = confusion_matrix(y_true_bin, (y_pred >= threshold).astype(int), labels=[0, 1])
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.colorbar(im, ax=ax)
    labels = ['No Default', 'Default']
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel('Predicted'); ax.set_ylabel('Actual')
    ax.set_title(f'Confusion Matrix (threshold={threshold})', fontsize=12, fontweight='bold')
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                    color='white' if cm[i, j] > cm.max() / 2 else 'black', fontsize=14)
    charts['confusion_matrix'] = _fig_to_base64(fig)

    # 4. PD Score Distribution — split by actual default status
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(y_pred[y_true_bin == 0], bins=40, alpha=0.6, color='#2196F3', label='Non-Default')
    ax.hist(y_pred[y_true_bin == 1], bins=40, alpha=0.6, color='#FF5722', label='Default')
    ax.axvline(threshold, color='black', linestyle='--', lw=1.5, label=f'Threshold={threshold}')
    ax.set_xlabel('Predicted PD (probability)')
    ax.set_ylabel('Count')
    ax.set_title('PD Score Distribution by Actual Outcome', fontsize=13, fontweight='bold')
    ax.legend()
    charts['pd_distribution'] = _fig_to_base64(fig)

    # 5. Precision-Recall Curve
    prec_vals, rec_vals, _ = precision_recall_curve(y_true_bin, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(rec_vals, prec_vals, color='#E91E63', lw=2)
    ax.set_xlabel('Recall')
    ax.set_ylabel('Precision')
    ax.set_title('Precision-Recall Curve', fontsize=13, fontweight='bold')
    ax.set_xlim([0, 1]); ax.set_ylim([0, 1])
    charts['precision_recall'] = _fig_to_base64(fig)

    # 6. Calibration Curve (reliability diagram)
    from sklearn.calibration import calibration_curve
    fraction_pos, mean_pred = calibration_curve(y_true_bin, y_pred, n_bins=8, strategy='quantile')
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(mean_pred, fraction_pos, 's-', color='#4CAF50', lw=2, label='XGBoost')
    ax.plot([0, 1], [0, 1], 'k--', lw=1, label='Perfect calibration')
    ax.set_xlabel('Mean Predicted PD')
    ax.set_ylabel('Fraction of Actual Defaults')
    ax.set_title('Calibration Curve', fontsize=13, fontweight='bold')
    ax.legend()
    charts['calibration'] = _fig_to_base64(fig)

    return charts


# ── Step 7: Archive ───────────────────────────────────────────────────────────

def archive_training_files(files_used, run_id):
    """Move processed CSVs to data/archive/{run_id}/."""
    run_archive = os.path.join(ARCHIVE_DIR, run_id)
    os.makedirs(run_archive, exist_ok=True)
    for f in files_used:
        src = os.path.join(TRAINING_DIR, f['filename'])
        dst = os.path.join(run_archive, f['filename'])
        if os.path.exists(src):
            shutil.move(src, dst)


# ── Peer benchmark refresh ────────────────────────────────────────────────────

_BENCHMARK_COLS = ['de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio']
_BENCHMARK_LABELS = {
    'de_ratio':          'Debt-to-Equity',
    'interest_coverage': 'Interest Coverage',
    'profitability':     'Net Profit Margin (%)',
    'liquidity_ratio':   'Current Ratio',
}

_BENCHMARK_SEGMENT_KEYS = ('ALL', 'CORPORATE', 'SME', 'RETAIL_MORTGAGES', 'RETAIL_OTHER')


def _refresh_peer_benchmarks(df, exposure_class=None):
    """
    Recompute peer benchmarks (P25/median/P75/P10/P90) from approved borrowers
    (default_flag=0) in the given (already segment-filtered) training
    dataframe, and update that segment's entry in peer_benchmarks.json
    (keyed 'ALL' plus the 4 Basel segments) - so each exposure_class's peer
    comparison is scoped to its own population instead of one blended
    whole-portfolio benchmark. Called automatically after every successful
    model promotion.
    """
    seg = exposure_class or 'ALL'
    approved = df[df[TARGET_COL] == 0]
    n_approved = len(approved)
    n_total    = len(df)
    benchmarks = {}

    for col in _BENCHMARK_COLS:
        vals = approved[col].dropna().sort_values().tolist()
        if not vals:
            continue

        def pct(p):
            n   = len(vals)
            idx = (p / 100) * (n - 1)
            lo  = int(idx)
            hi  = min(lo + 1, n - 1)
            return vals[lo] + (idx - lo) * (vals[hi] - vals[lo])

        benchmarks[col] = {
            'label':  _BENCHMARK_LABELS.get(col, col),
            'median': round(pct(50), 4),
            'p25':    round(pct(25), 4),
            'p75':    round(pct(75), 4),
            'p10':    round(pct(10), 4),
            'p90':    round(pct(90), 4),
            'min':    round(vals[0],  4),
            'max':    round(vals[-1], 4),
            'n':      n_approved,
        }

    seg_out = {
        '_meta': {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'source':       f'bank_loan_metrics (default_flag=0, exposure_class={seg})',
            'n_approved':   n_approved,
            'n_total':      n_total,
            'default_rate': round(1 - n_approved / n_total, 4) if n_total else None,
        },
        **benchmarks,
    }

    # Read-merge-write: preserve other segments' already-computed benchmarks
    # rather than clobbering the whole file with just this run's segment.
    all_benchmarks = {}
    if os.path.exists(BENCHMARKS_PATH):
        try:
            with open(BENCHMARKS_PATH) as f:
                existing = json.load(f)
            # Migrate the old flat pre-segmentation shape into the 'ALL' key.
            if any(k in existing for k in _BENCHMARK_SEGMENT_KEYS):
                all_benchmarks = existing
            else:
                all_benchmarks = {'ALL': existing}
        except Exception:
            all_benchmarks = {}

    all_benchmarks[seg] = seg_out
    with open(BENCHMARKS_PATH, 'w') as f:
        json.dump(all_benchmarks, f, indent=2)


# ── Main training orchestrator ────────────────────────────────────────────────

def _gov_record(event_type, actor_id='system', object_type=None, object_id=None,
                payload=None, alert=None):
    """Write a governance audit event (and optionally an alert) to bank.db.
    Always non-fatal: training must never fail because of audit plumbing."""
    try:
        from backend import governance_store as _gov
        _conn = sqlite3.connect(BANK_DB_PATH)
        _gov.init_schema(_conn)
        _gov.append_audit_event(_conn, event_type, actor_id=actor_id,
                                actor_role='trainer', object_type=object_type,
                                object_id=object_id, payload=payload)
        if alert:
            _gov.create_alert(_conn, **alert)
            _conn.commit()
        _conn.close()
    except Exception as e:
        print(f'[GOV] audit write failed (non-fatal): {e}')


def _snapshot_story(slot_key):
    """Freeze the Model Trust Ledger's data for this slot's just-promoted model
    to disk, keyed by run_id, so past reports survive the next retrain.
    Non-fatal on any failure."""
    try:
        from backend import governance_store as _gov
        _conn = sqlite3.connect(BANK_DB_PATH)
        _gov.init_schema(_conn)
        snap = _gov.snapshot_story(_conn, slot_key)
        _conn.close()
        print(f'[GOV] story snapshot saved for {slot_key}: run_id={snap.get("run_id")}')
    except Exception as e:
        print(f'[GOV] story snapshot failed (non-fatal): {e}')


def _snapshot_baseline(run_id, slot_key, X_train, model):
    """Persist training-time score/feature distributions for later PSI
    monitoring (backend/drift_monitor.py). Non-fatal on any failure."""
    try:
        from backend import drift_monitor as _drift
        proba_train = model.predict_proba(X_train)[:, 1]
        _conn = sqlite3.connect(BANK_DB_PATH)
        n = _drift.snapshot_training_baseline(_conn, run_id, slot_key, X_train, proba_train)
        _conn.close()
        print(f'[GOV] PSI baselines snapshotted for {slot_key}: score + {n} features')
    except Exception as e:
        print(f'[GOV] baseline snapshot failed (non-fatal): {e}')


def run_training(triggered_by='manual', use_transaction_level=True, model_type='xgboost', bank_ids=None,
                  exposure_class=None, include_compliance_excluded=False):
    """
    Full training pipeline.

    Args:
        triggered_by (str): 'manual', 'scheduler', etc.
        use_transaction_level (bool): If True, use enriched transactions table (84K rows)
                                       If False, use bank_loan_metrics table (1.1K rows)
        model_type (str): 'xgboost', 'logistic_regression', etc.
        bank_ids (list[str] | None): If given, restrict training data to these
                                      bank_id values (e.g. ['BANK001', 'BANK002']).
                                      None/empty means all banks.
        exposure_class (str | None): If given, restrict training data to this
                                      single Basel segment (CORPORATE, SME,
                                      RETAIL_MORTGAGES, RETAIL_OTHER). None
                                      means the unsegmented/legacy 'ALL' slot.
        include_compliance_excluded (bool): Default False - bank-scoped
                                      auto-discovery skips COMPLIANCE_EXCLUDED_COLS
                                      (gender_enc, marital_status_enc) by design.
                                      Set True to deliberately include them anyway
                                      - e.g. to reproduce a published research
                                      benchmark that used all raw dataset columns.
                                      This is a per-run, explicit opt-in only; it
                                      does not change the default for any other
                                      call, and the resulting run record flags
                                      that this was used (see
                                      compliance_excluded_cols_included) so it's
                                      never silently invisible later. This model
                                      should not be treated as fit for a real
                                      lending decision without a separate,
                                      deliberate compliance sign-off - it exists
                                      for research/benchmark comparison.

    Returns a run record dict (same structure as stored in run_history.json).
    Raises RuntimeError if another run is already in progress.
    """
    global _training_running

    if not _training_lock.acquire(blocking=False):
        raise RuntimeError("A training run is already in progress.")

    _training_running = True
    run_id    = 'run_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    started   = time.time()
    timestamp = datetime.now().isoformat(timespec='seconds')
    bank_ids  = list(bank_ids) if bank_ids else None
    seg_key   = exposure_class or 'ALL'

    # Model-routing switch: exposure_class='GENERIC' trains a bank-wide,
    # unsegmented model - for a bank whose source data has no Basel
    # exposure_class concept at all. Only meaningful for exactly one bank
    # (a "generic model" is inherently bank-scoped; a cross-bank unsegmented
    # model is the old retired 'ALL' path and stays retired).
    if exposure_class == 'GENERIC' and (not bank_ids or len(bank_ids) != 1):
        _training_running = False
        _training_lock.release()
        raise ValueError(
            "exposure_class='GENERIC' (a bank-wide, unsegmented model) requires "
            "training on exactly one bank_id."
        )
    # 'GENERIC' isn't a real exposure_class value in bank_loan_metrics - it
    # means "don't filter by segment", same as exposure_class=None, for the
    # SQL query. seg_key/combo_key/registry still use the literal 'GENERIC'.
    sql_exposure_class = None if exposure_class == 'GENERIC' else exposure_class

    data_source = "enriched_transactions (TRANSACTION-LEVEL)" if use_transaction_level else "bank_loan_metrics (CUSTOMER-LEVEL)"

    record = {
        'run_id':        run_id,
        'timestamp':     timestamp,
        'triggered_by':  triggered_by,
        'data_source':   data_source,
        'use_transaction_level': use_transaction_level,
        'model_type':    model_type,
        'bank_ids':      bank_ids,
        'exposure_class': exposure_class,
        'compliance_excluded_cols_included': include_compliance_excluded,
        'status':        'failed',
        'files_used':    [],
        'files_skipped': [],
        'total_rows':    0,
        'train_rows':    0,
        'test_rows':     0,
        'metrics':       {},
        'confusion_matrix': [],
        'model_promoted':   False,
        'duration_seconds': 0,
        'error':         None,
    }

    try:
        hp        = _load_hyperparameters()
        threshold = float(hp['training'].get('pd_classification_threshold', 0.05))
        test_size = float(hp['training'].get('test_size', 0.20))
        min_rows_floor= int(hp['training'].get('min_rows_floor', 100))

        # Load data (now with transaction-level, bank, and exposure-class filters)
        merged, files_used, files_skip, dupes = load_and_merge(
            use_transaction_level=use_transaction_level, bank_ids=bank_ids, exposure_class=sql_exposure_class
        )
        record['files_used']    = files_used
        record['files_skipped'] = files_skip
        record['total_rows']    = len(merged)

        # Split
        # Check for missing columns
        missing_cols = [col for col in FEATURE_COLS if col not in merged.columns]
        if missing_cols:
            available_cols = list(merged.columns)
            raise ValueError(f'[TRAIN] Missing columns: {missing_cols}. Available: {available_cols[:10]}...')

        # Bank-scoped training (single or multiple specific banks): a column
        # that's ENTIRELY blank for the selected bank(s) - e.g. a newly
        # onboarded bank whose source data structurally never collected it -
        # is excluded from THIS run's feature set instead of being trained on
        # with zero variance (which _validate_dataframe's dropna would
        # otherwise turn into "zero rows left" for the whole dataset, not
        # just a useless column - see the fix there). The shared cross-bank
        # ('ALL') path keeps the full strict schema requirement unchanged - a
        # blank column there is a genuine anomaly worth failing loudly on,
        # not a routine per-bank onboarding gap.
        dropped_blank_cols = []
        auto_discovered_cols = []
        if bank_ids:
            dropped_blank_cols = [c for c in FEATURE_COLS if merged[c].isna().all()]

            # Auto-discovery: a bank-scoped run also picks up any real column
            # in bank_loan_metrics beyond the fixed 37-feature canonical list
            # that this bank actually populated - e.g. BANK011's
            # repay_status_m1..m6, bill_amt_m1..m6, credit_limit, the two
            # derived ratios. Identity/metadata columns are never eligible.
            # COMPLIANCE_EXCLUDED_COLS are excluded by default (see
            # run_training's docstring) unless this specific call explicitly
            # opts in via include_compliance_excluded=True - a deliberate,
            # per-run choice, not a change to the default for anyone else.
            excluded_cols = set(NON_FEATURE_COLS)
            if not include_compliance_excluded:
                excluded_cols |= COMPLIANCE_EXCLUDED_COLS
            elif COMPLIANCE_EXCLUDED_COLS & set(merged.columns):
                print(f"[TRAIN] include_compliance_excluded=True for this run - "
                      f"{sorted(COMPLIANCE_EXCLUDED_COLS)} are eligible for auto-discovery. "
                      f"This model is for research/benchmark comparison only, not a real "
                      f"lending decision, without a separate compliance sign-off.")
            candidate_extra_cols = [
                c for c in merged.columns
                if c not in FEATURE_COLS
                and c not in excluded_cols
            ]
            for c in candidate_extra_cols:
                if not pd.api.types.is_numeric_dtype(merged[c]):
                    continue
                if merged[c].isna().all():
                    continue
                auto_discovered_cols.append(c)
            if auto_discovered_cols:
                print(f"[TRAIN] Bank-scoped run for {bank_ids}: auto-discovered "
                      f"{len(auto_discovered_cols)} extra feature column(s) beyond the "
                      f"canonical 37: {auto_discovered_cols}")

        active_feature_cols = [c for c in FEATURE_COLS if c not in dropped_blank_cols] + auto_discovered_cols
        if dropped_blank_cols:
            print(f"[TRAIN] Bank-scoped run for {bank_ids}: excluding "
                  f"{len(dropped_blank_cols)} entirely-blank feature column(s): {dropped_blank_cols}")
        record['dropped_blank_features'] = dropped_blank_cols
        record['auto_discovered_features'] = auto_discovered_cols

        X = merged[active_feature_cols].copy()
        y = merged[TARGET_COL].copy()

        if y.nunique() < 2:
            filter_note = ''
            if bank_ids:
                filter_note += f" for the selected bank(s) {bank_ids}"
            if exposure_class:
                filter_note += f" for segment {exposure_class}"
            raise ValueError(
                f'[TRAIN] Only one class present in default_flag{filter_note} '
                f'({int(y.sum())} defaults out of {len(y)} rows) - cannot train or '
                'evaluate a classifier. Select more banks/segments or use the full dataset.'
            )

        # Convert all columns to numeric, drop non-numeric
        numeric_X = X.select_dtypes(include=['number'])
        if len(numeric_X.columns) < len(X.columns):
            dropped = set(X.columns) - set(numeric_X.columns)
            print(f"[TRAIN] Dropped non-numeric columns: {dropped}")
            X = numeric_X

        model_hp = hp.get('models', {}).get(model_type, hp.get('model', {}))
        random_state = int(model_hp.get('random_state', 42))

        # Transaction-level rows are NOT independent samples: every transaction
        # for a given loan shares (near-)identical static features (CIBIL,
        # income, DE ratio, ...), differing only in date/amount/macro trend.
        # A plain row-level train_test_split lets ~80% of each loan's rows
        # leak into train and ~20% into test, so the model just memorizes each
        # loan's feature fingerprint instead of generalizing - which is exactly
        # what was producing AUC=1.0 on transaction-level training. Split by
        # loan (group_id) instead, so an entire loan's rows land on one side
        # only, and report which split strategy was actually used.
        group_col = 'group_id' if 'group_id' in merged.columns else None
        if group_col is not None and merged[group_col].notna().any():
            groups = merged[group_col].fillna(merged.index.to_series().astype(str))
            gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
            train_idx, test_idx = next(gss.split(X, y, groups=groups))
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            record['split_strategy'] = 'grouped_by_loan'
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )
            record['split_strategy'] = 'row_level_random'
        df_test = merged.loc[X_test.index]
        record['train_rows'] = len(X_train)
        record['test_rows']  = len(X_test)

        # Train
        n_neg_train = int((y_train == 0).sum())
        n_pos_train = int((y_train == 1).sum())
        auto_spw = round(n_neg_train / n_pos_train, 2) if n_pos_train > 0 else 1.0
        model = train_model(X_train, y_train, hp, model_type=model_type)

        # Evaluate
        metrics, cm, y_pred = evaluate_model(model, X_test, y_test, df_test, threshold)
        record['metrics']          = metrics
        record['confusion_matrix'] = cm

        # Honest generalization estimate (see cross_validate_model docstring):
        # the single-split AUC above is not trustworthy when there are only a
        # handful of positive examples in the whole dataset - report the CV
        # mean/std alongside it so the admin dashboard isn't showing a number
        # that could swing from 0.45 to 1.0 on a different random seed.
        cv_groups = merged[group_col] if group_col is not None and merged[group_col].notna().any() else None
        cv_metrics = cross_validate_model(X, y, hp, model_type, groups=cv_groups, n_splits=5)
        record['cv_metrics'] = cv_metrics
        metrics['cv_auc_mean'] = cv_metrics.get('mean_auc')
        metrics['cv_auc_std']  = cv_metrics.get('std_auc')

        # Trustworthiness diagnostics (see conversation this was built from):
        # a single AUC number cannot be trusted at face value when the
        # minority class is this small - EPV flags whether there's enough
        # data to support the feature count at all, and the CIBIL-only
        # baseline flags whether the other 38 features are adding real
        # signal or just capacity to overfit.
        record['epv'] = compute_epv(n_pos_train, len(active_feature_cols))
        baseline_proba = baseline_cibil_predictions(X_train, y_train, X_test)
        baseline_auc = (float(roc_auc_score(y_test, baseline_proba))
                         if baseline_proba is not None and len(np.unique(y_test)) > 1 else None)
        record['baseline_cibil_only_auc'] = round(baseline_auc, 4) if baseline_auc is not None else None
        record['auc_lift_over_baseline'] = (
            round(metrics['auc_roc'] - baseline_auc, 4) if baseline_auc is not None else None
        )
        # Is that lift distinguishable from noise, or could it vanish on a
        # different random draw of the same test population? See
        # bootstrap_auc_lift()'s docstring - this judges each model's PD
        # scores against the real default outcome, never the two models
        # against each other.
        record['lift_significance'] = bootstrap_auc_lift(y_test, y_pred, baseline_proba)

        # Generate charts and save to data/runs/{run_id}/
        charts = generate_charts(model, X_test, y_test, y_pred, df_test, threshold)
        run_charts_dir = os.path.join(RUNS_DIR, run_id)
        os.makedirs(run_charts_dir, exist_ok=True)
        for name, b64 in charts.items():
            with open(os.path.join(run_charts_dir, f'{name}.b64'), 'w') as f:
                f.write(b64)

        # Save model to a (model_type, bank_combo, exposure_class) specific
        # directory - each unique combination keeps its own pickle + metadata
        # rather than overwriting one slot per model_type, so e.g. an
        # "all banks / CORPORATE" XGBoost and a "BANK001-only / SME" XGBoost
        # can both be kept and compared.
        combo_key = bank_key(bank_ids)
        model_type_dir = os.path.join(ML_DIR, 'models', model_type, combo_key, seg_key)
        os.makedirs(model_type_dir, exist_ok=True)
        type_model_path = os.path.join(model_type_dir, 'pd_model.pkl')
        type_meta_path = os.path.join(model_type_dir, 'pd_model_metadata.json')

        joblib.dump(model, type_model_path)

        # Build metadata for this model type
        MODEL_TYPE_LABELS = {
            'xgboost':             'XGBoost',
            'logistic_regression': 'Logistic Regression',
            'random_forest':       'Random Forest',
            'extra_trees':         'Extra Trees',
            'gradient_boosting':   'Gradient Boosting',
        }
        model_type_label = MODEL_TYPE_LABELS.get(model_type, model_type)
        new_meta = {
            'model_type':   model_type_label,
            'algorithm':    model_type,
            'version':      run_id,
            'date_trained': timestamp,
            'triggered_by': triggered_by,
            'features':     active_feature_cols,
            'n_features':   len(active_feature_cols),
            'dropped_blank_features': dropped_blank_cols,
            'target':       TARGET_COL,
            'metrics':      metrics,
            'hyperparameters': hp.get('models', {}).get(model_type, hp.get('model', {})),
            'n_train':            len(X_train),
            'rows_trained':       len(X_train),
            'total_rows':         len(merged),
            'test_rows':          len(X_test),
            'bank_ids':           bank_ids,
            'exposure_class':     exposure_class,
            'compliance_excluded_cols_included': include_compliance_excluded,
            'n_defaults_train':   n_pos_train,
            'scale_pos_weight':   auto_spw,
            'threshold':          threshold,
            'currency':           'INR',
            'epv':                        record['epv'],
            'baseline_cibil_only_auc':    record['baseline_cibil_only_auc'],
            'auc_lift_over_baseline':     record['auc_lift_over_baseline'],
            'lift_significance':          record['lift_significance'],
            'note':               f'{model_type_label} binary classifier; target=default_flag (RBI 90-day NPA rule)',
        }
        with open(type_meta_path, 'w') as f:
            json.dump(new_meta, f, indent=2)

        # Promotion: auto-activate if no active model exists yet, or if same
        # type being retrained — AND the governance challenger-vs-champion
        # gate passes (a retrain whose AUC regresses beyond tolerance vs the
        # currently promoted champion is saved but NOT activated).
        n_trained = len(X_train)
        rows_ok = n_trained >= min_rows_floor
        record['promotion_check'] = {
            'auc': metrics.get('auc_roc'),
            'n_trained': n_trained, 'min_rows_floor': min_rows_floor,
            'rows_ok': rows_ok,
        }

        if rows_ok:
            # Auto-activate if this is the first model for this segment, or
            # if retraining the exact (model_type, bank_combo) that's
            # currently active FOR THIS SEGMENT SPECIFICALLY - each segment
            # has its own independent active slot (see activate_model), so
            # training/promoting CORPORATE never disturbs SME/RETAIL_*/ALL.
            # Bank-scoped runs (combo_key != 'ALL') gate on their OWN
            # composite registry key (see activate_model), so a bank-specific
            # promotion is independent of - and never blocked by - whatever
            # is active in the shared cross-bank slot for this segment.
            reg_key = seg_key if combo_key == 'ALL' else f'{seg_key}::{combo_key}'
            registry = _load_active_model_registry()
            seg_active = registry.get(reg_key) or {}
            active_type = seg_active.get('model_type')
            active_combo = seg_active.get('bank_key')

            # Governance challenger-vs-champion gate: compare this run's
            # test AUC against the promoted champion for the same slot. Fails
            # open (gate_ok=True) when no champion is registered or the
            # registry is unreadable — the gate exists to stop silent
            # regressions, not to block first-time promotions.
            gov_cfg = hp.get('governance', {})
            gate_enabled = bool(gov_cfg.get('promotion_gate_enabled', True))
            gate_tol = float(gov_cfg.get('auc_regression_tolerance', 0.01))
            challenger_auc = metrics.get('auc_roc')
            champion_auc, champion_model_id = None, None
            try:
                _conn = sqlite3.connect(BANK_DB_PATH)
                _row = _conn.execute(
                    "SELECT model_id, auc_roc FROM model_registry "
                    "WHERE exposure_class=? AND bank_scope=? "
                    "ORDER BY promoted_at DESC LIMIT 1",
                    (seg_key, combo_key if combo_key != 'ALL' else 'ALL')).fetchone()
                _conn.close()
                if _row:
                    champion_model_id, champion_auc = _row[0], _row[1]
            except Exception as e:
                print(f'[GOV] champion lookup failed (gate passes open): {e}')

            gate_ok = (not gate_enabled or champion_auc is None
                       or challenger_auc is None
                       or challenger_auc >= champion_auc - gate_tol)
            record['promotion_check'].update({
                'gate_enabled': gate_enabled,
                'champion_model_id': champion_model_id,
                'champion_auc': champion_auc,
                'challenger_auc': challenger_auc,
                'tolerance': gate_tol,
                'gate_ok': gate_ok,
            })

            if (active_type is None or (active_type == model_type and active_combo == combo_key)) and gate_ok:
                activate_model(model_type, combo_key, exposure_class)
                record['model_promoted'] = True
                record['status_detail'] = 'promoted'
                _refresh_peer_benchmarks(merged, exposure_class)

                # Phase 4 — model_registry (backend/model_registry.py): a real,
                # queryable record of which model version this promotion was,
                # so prediction_store rows can point at an actual model_id
                # instead of just a free-text model_version string.
                promoted_model_id = None
                try:
                    from backend.model_registry import register_promotion
                    _conn = sqlite3.connect(BANK_DB_PATH)
                    promoted_model_id = register_promotion(
                        _conn, exposure_class, model_type, run_id=run_id,
                        trained_at=timestamp,
                        promoted_at=datetime.now().isoformat(timespec='seconds'),
                        metrics=metrics, n_train=n_trained, bank_ids=bank_ids,
                    )
                    _conn.close()
                except Exception as e:
                    print(f'[WARN] model_registry write failed (non-fatal): {e}')

                _gov_record('MODEL_PROMOTED', actor_id=triggered_by,
                            object_type='model',
                            object_id=promoted_model_id or f'{model_type}::{reg_key}',
                            payload={'run_id': run_id, 'slot': reg_key,
                                     'auc': challenger_auc,
                                     'champion_auc': champion_auc,
                                     'triggered_by': triggered_by})
                _snapshot_baseline(run_id, reg_key, X_train, model)
                _snapshot_story(reg_key)
            elif not gate_ok:
                # Challenger regressed beyond tolerance: keep the saved pkl +
                # metadata (already written above), but do NOT activate. A
                # force-promote (with audited rationale) is the only path in.
                record['model_promoted'] = False
                record['status_detail'] = 'trained_not_promoted'
                msg = (f'Promotion blocked for {reg_key}: challenger AUC '
                       f'{challenger_auc} < champion {champion_auc} - tolerance {gate_tol}')
                print(f'[GOV] {msg}')
                _gov_record('PROMOTION_BLOCKED', actor_id=triggered_by,
                            object_type='model', object_id=f'{model_type}::{reg_key}',
                            payload={'run_id': run_id, 'slot': reg_key,
                                     'challenger_auc': challenger_auc,
                                     'champion_auc': champion_auc,
                                     'champion_model_id': champion_model_id,
                                     'tolerance': gate_tol},
                            alert={'slot_key': reg_key,
                                   'alert_type': 'PROMOTION_BLOCKED',
                                   'kpi': 'auc_regression',
                                   'value': challenger_auc,
                                   'threshold': (champion_auc - gate_tol)
                                                if champion_auc is not None else None,
                                   'severity': 'BREACH', 'message': msg,
                                   'model_id': champion_model_id})

        # Archive used files
        archive_training_files(files_used, run_id)

        record['status'] = 'success'

    except Exception as e:
        record['error'] = traceback.format_exc()

    finally:
        record['duration_seconds'] = round(time.time() - started, 2)

        history = _load_history()
        history.insert(0, {k: v for k, v in record.items()})
        history = history[:50]  # keep last 50 runs
        _save_history(history)

        _training_running = False
        _training_lock.release()

        _gov_record('TRAINING_RUN', actor_id=triggered_by,
                    object_type='run', object_id=record.get('run_id'),
                    payload={'status': record.get('status'),
                             'status_detail': record.get('status_detail'),
                             'model_type': record.get('model_type'),
                             'exposure_class': record.get('exposure_class'),
                             'bank_ids': record.get('bank_ids'),
                             'total_rows': record.get('total_rows'),
                             'metrics': record.get('metrics'),
                             'model_promoted': record.get('model_promoted'),
                             'promotion_check': record.get('promotion_check'),
                             'error': (record.get('error') or '')[-300:] or None})

    return record


# ── Model Activation ─────────────────────────────────────────────────────────
# Segmented models need FOUR simultaneously-active models in production (one
# per exposure_class - a live system scores a CORPORATE loan with the
# CORPORATE model and a RETAIL_OTHER loan with the RETAIL_OTHER model at the
# same time), not one swappable slot like before segmentation. Each segment
# ('ALL' plus the 4 Basel classes) gets its own parallel active-model slot on
# disk and its own entry in active_model.json (now a dict keyed by segment
# instead of one flat object).

ACTIVE_MODEL_REGISTRY_PATH = os.path.join(ML_DIR, 'active_model.json')


def _segment_paths(exposure_class, bank_combo='ALL'):
    """(active_model, active_meta, backup_model, backup_meta) paths for a
    segment's active slot. 'ALL'/None reuses the original flat top-level
    filenames for backward compatibility with pre-segmentation deployments;
    the 4 Basel segments each get their own parallel slot.

    bank_combo (model-routing switch): when not 'ALL', resolves to a
    SEPARATE, bank-scoped active slot (pd_model_<seg>_<bank_combo>.pkl)
    instead of the shared cross-bank slot above - promoting a bank-specific
    model never touches the file every other bank's inference reads.
    exposure_class may also be 'GENERIC' (a bank-wide, unsegmented model,
    only meaningful together with a non-'ALL' bank_combo)."""
    seg = exposure_class or 'ALL'
    if bank_combo and bank_combo != 'ALL':
        suffix = f'{seg}_{bank_combo}'
        return (
            os.path.join(ML_DIR, f'pd_model_{suffix}.pkl'),
            os.path.join(ML_DIR, f'pd_model_metadata_{suffix}.json'),
            os.path.join(ML_DIR, f'pd_model_backup_{suffix}.pkl'),
            os.path.join(ML_DIR, f'pd_model_backup_metadata_{suffix}.json'),
        )
    if seg == 'ALL':
        return MODEL_PATH, META_PATH, BACKUP_PATH, os.path.join(ML_DIR, 'pd_model_backup_metadata.json')
    return (
        os.path.join(ML_DIR, f'pd_model_{seg}.pkl'),
        os.path.join(ML_DIR, f'pd_model_metadata_{seg}.json'),
        os.path.join(ML_DIR, f'pd_model_backup_{seg}.pkl'),
        os.path.join(ML_DIR, f'pd_model_backup_metadata_{seg}.json'),
    )


def _load_active_model_registry():
    """Load active_model.json as a dict keyed by segment ('ALL' plus the 4
    Basel classes). Migrates the old flat single-model shape (no segment
    keys, just {model_type, bank_key, activated_at}) by treating its
    contents as the 'ALL' segment's entry, so nothing already active breaks."""
    if not os.path.exists(ACTIVE_MODEL_REGISTRY_PATH):
        return {}
    try:
        with open(ACTIVE_MODEL_REGISTRY_PATH) as f:
            data = json.load(f)
    except Exception:
        return {}
    if 'model_type' in data:  # old flat shape
        return {'ALL': data}
    return data


def _save_active_model_registry(registry):
    with open(ACTIVE_MODEL_REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, indent=2)


def activate_model(model_type, bank_combo='ALL', exposure_class=None):
    """
    Activate a specific (model_type, bank_combo, exposure_class) model as the
    active model FOR THAT SEGMENT. Copies that combo's pkl and metadata to
    the segment's own active slot, backs up the previous model for that
    segment only, and updates that segment's entry in active_model.json -
    activating a CORPORATE model never touches SME/RETAIL_*/ALL's active slot.
    """
    seg = exposure_class or 'ALL'
    model_type_dir = os.path.join(ML_DIR, 'models', model_type, bank_combo, seg)
    type_model_path = os.path.join(model_type_dir, 'pd_model.pkl')
    type_meta_path = os.path.join(model_type_dir, 'pd_model_metadata.json')

    # Back-compat: pre-segmentation runs saved directly under
    # models/<model_type>/<bank_combo>/ with no exposure_class subdirectory.
    if not os.path.exists(type_model_path) and seg == 'ALL':
        legacy_dir = os.path.join(ML_DIR, 'models', model_type, bank_combo)
        legacy_model_path = os.path.join(legacy_dir, 'pd_model.pkl')
        legacy_meta_path = os.path.join(legacy_dir, 'pd_model_metadata.json')
        if os.path.exists(legacy_model_path):
            model_type_dir, type_model_path, type_meta_path = legacy_dir, legacy_model_path, legacy_meta_path

    # Deeper back-compat: pre-bank-combo runs saved directly under models/<model_type>/.
    if not os.path.exists(type_model_path) and bank_combo == 'ALL' and seg == 'ALL':
        legacy_dir = os.path.join(ML_DIR, 'models', model_type)
        legacy_model_path = os.path.join(legacy_dir, 'pd_model.pkl')
        legacy_meta_path = os.path.join(legacy_dir, 'pd_model_metadata.json')
        if os.path.exists(legacy_model_path):
            model_type_dir, type_model_path, type_meta_path = legacy_dir, legacy_model_path, legacy_meta_path

    if not os.path.exists(type_model_path):
        raise FileNotFoundError(
            f"No model found for type '{model_type}' / banks '{bank_combo}' / segment '{seg}' at {type_model_path}"
        )

    active_model_path, active_meta_path, backup_model_path, backup_meta_path = _segment_paths(seg, bank_combo)

    # Backup this segment's current active model
    if os.path.exists(active_model_path):
        shutil.copy2(active_model_path, backup_model_path)
    if os.path.exists(active_meta_path):
        shutil.copy2(active_meta_path, backup_meta_path)

    # Copy model type's files to this segment's active slots
    shutil.copy2(type_model_path, active_model_path)
    shutil.copy2(type_meta_path, active_meta_path)

    # Update this segment's entry in the active-model registry. Bank-scoped
    # promotions get their own composite key (seg::bank_combo) so they don't
    # collide with - or gate on - the shared cross-bank segment's entry.
    reg_key = seg if bank_combo == 'ALL' else f'{seg}::{bank_combo}'
    registry = _load_active_model_registry()
    registry[reg_key] = {
        'model_type': model_type,
        'bank_key': bank_combo,
        'exposure_class': seg,
        'activated_at': datetime.now().isoformat(timespec='seconds'),
    }
    _save_active_model_registry(registry)

    return {'status': 'activated', 'model_type': model_type, 'bank_key': bank_combo, 'exposure_class': seg}


# ── Rollback ──────────────────────────────────────────────────────────────────

def rollback_model(exposure_class=None):
    """Restore the given segment's backup as its active model. Only that
    segment's slot is affected - rolling back CORPORATE never touches
    SME/RETAIL_*/ALL."""
    seg = exposure_class or 'ALL'
    active_model_path, active_meta_path, backup_model_path, backup_meta_path = _segment_paths(seg)

    if not os.path.exists(backup_model_path):
        raise FileNotFoundError(f"No backup model found to roll back to for segment '{seg}'.")

    shutil.copy2(backup_model_path, active_model_path)
    if os.path.exists(backup_meta_path):
        shutil.copy2(backup_meta_path, active_meta_path)

    return {'status': 'rolled back', 'exposure_class': seg,
            'message': f"Previous {seg} model restored as active."}


# ── Force-promote (governance override of the challenger-vs-champion gate) ───

def force_promote(model_type, bank_combo='ALL', exposure_class=None,
                  actor_id=None, rationale=None):
    """Activate a saved-but-not-promoted model over the gate's objection.
    The override itself is a governed action: it requires an actor and a
    rationale (>= 20 chars) and lands on the hash-chained audit trail as
    FORCE_PROMOTE, so 'who promoted a regressing model, and why' is always
    answerable."""
    if not actor_id or not (rationale or '').strip() or len(rationale.strip()) < 20:
        raise ValueError('force_promote requires actor_id and a rationale of at least 20 characters')

    seg = exposure_class or 'ALL'
    result = activate_model(model_type, bank_combo, exposure_class)
    reg_key = seg if bank_combo == 'ALL' else f'{seg}::{bank_combo}'

    # Register the promotion from the saved type-dir metadata so model_registry
    # and prediction_store lineage stay correct even for a forced activation.
    meta_path = os.path.join(ML_DIR, 'models', model_type, bank_combo, seg,
                             'pd_model_metadata.json')
    model_id = None
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        from backend.model_registry import register_promotion
        _conn = sqlite3.connect(BANK_DB_PATH)
        model_id = register_promotion(
            _conn, exposure_class, model_type,
            run_id=meta.get('version'),
            trained_at=meta.get('date_trained'),
            promoted_at=datetime.now().isoformat(timespec='seconds'),
            metrics=meta.get('metrics') or {},
            n_train=meta.get('n_train'),
            bank_ids=meta.get('bank_ids'),
        )
        _conn.close()
    except Exception as e:
        print(f'[WARN] model_registry write failed on force-promote (non-fatal): {e}')

    _gov_record('FORCE_PROMOTE', actor_id=actor_id, object_type='model',
                object_id=model_id or f'{model_type}::{reg_key}',
                payload={'slot': reg_key, 'model_type': model_type,
                         'bank_combo': bank_combo, 'exposure_class': seg,
                         'rationale': rationale.strip()})

    # Re-snapshot PSI baselines from the promoted model's training data isn't
    # possible here (training frame is gone) — the next retrain refreshes them.
    _snapshot_story(reg_key)
    result['forced'] = True
    result['model_id'] = model_id
    return result


if __name__ == '__main__':
    print(run_training(triggered_by='cli'))
