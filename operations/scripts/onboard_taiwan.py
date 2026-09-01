"""
onboard_taiwan.py
──────────────────
Onboards BANK011 ("Taiwan Composite Bank" - explicit generic placeholder
identity, confirmed by the business; the source dataset does not name a
real institution) as a Real Earth bank, from
sample datasets/Taiwan_UCI_Credit_Card.csv, per the mapping in
operations/scripts/onboarding_maps/BANK011_taiwan_credit_card.json.

SCOPE (confirmed): TRAINING-ONLY, same pattern as BANK010 (Bradesco). This
script creates:
  1. `countries` + `country_macro` rows for Taiwan (TWN) - not yet seeded
     anywhere else on the platform, needed for the macro-feature join and
     the TWD->USD conversion.
  2. One `banks` row for BANK011, world='real', country_code='TWN'.
  3. `bank_loan_metrics` rows (all 30,000 rows) for PD model training only.
No `customers`/`customer_kyc`/`loans`/`accounts`/`credit_risk_metrics` rows
are created - no operational loan book, no regulatory/financial/performance
reporting from this pass.

Currency: LIMIT_BAL/BILL_AMT*/PAY_AMT* are NT$ (New Taiwan Dollar),
converted to USD via country_macro.TWN.fx_rate_per_usd - same mechanism as
Bradesco's BRL conversion, not a new one.

No imputation: any canonical feature genuinely absent from this dataset
(the 4 core ratios, cibil_score, occupation/geography fields, all
delta/trend features, etc.) is left NULL, never filled - matches
BANK010's policy exactly. See the mapping file's
unmapped_required_fields_no_source_at_all for the full list.

LEAKAGE FIX vs BANK010: BANK010's risk-ordered categorical encoding was
computed on the full 50,000-row file's target BEFORE any train/test split,
which mildly leaks test-set outcomes into the encoding (flagged after the
fact). This script uses 5-fold OUT-OF-FOLD encoding instead: each row's
risk-order code is computed using only the OTHER 4 folds' target values,
so no row's own outcome ever informs its own encoding, regardless of
whatever train/test split ml_models/trainer.py later performs.

Compliance: SEX -> gender_enc is populated (per "don't lose information
upfront") but is a protected characteristic in most jurisdictions.
MARRIAGE -> marital_status_enc is a softer version of the same concern.
Neither is added to ml_models/trainer.py's FEATURE_COLS by this script -
that requires a separate, explicit decision.

New generic columns used (added by add_taiwan_columns.py, already run):
  credit_limit, repay_status_m1..m6, bill_amt_m1..m6, payment_amt_m1..m6,
  marital_status_enc, gender_enc, credit_utilization_ratio,
  payment_coverage_ratio

Idempotent - clears BANK011's existing bank_loan_metrics rows before
reinserting.

Run: python operations/scripts/onboard_taiwan.py
"""

import os
import sqlite3
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
TAIWAN_CSV = os.path.join(_ROOT, 'sample datasets', 'Taiwan_UCI_Credit_Card.csv')

BANK_ID = 'BANK011'
BANK_NAME = 'Taiwan Composite Bank'
COUNTRY_CODE = 'TWN'
RANDOM_STATE = 42

# Genuinely absent from this dataset - left NULL, never fabricated. See
# unmapped_required_fields_no_source_at_all in the mapping file.
GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'annual_income', 'years_employed', 'num_dependents', 'employment_type_enc',
    'residence_type_enc', 'city_tier_enc', 'loan_purpose_enc', 'cibil_score',
    'months_as_customer', 'existing_loans_count', 'is_rural', 'num_existing_products',
    'months_in_residence', 'foir',
    'delta_de_ratio', 'delta_cibil', 'months_since_origination',
    'ecs_bounce_count', 'other_lender_emi_ratio', 'income_disruption_flag',
    'sector_stress_index', 'ltv_trend_pct', 'exposure_class',
]


def _ensure_country_and_macro(conn):
    cur = conn.cursor()
    exists = cur.execute("SELECT 1 FROM countries WHERE country_code=?", (COUNTRY_CODE,)).fetchone()
    if exists:
        print(f"[0a] {COUNTRY_CODE} already in countries - leaving as-is.")
    else:
        cur.execute(
            "INSERT INTO countries (country_code, country_name, region, sub_region, "
            "currency_code, currency_symbol, central_bank, central_bank_abbr, capital_regulator, "
            "basel_framework, sovereign_rating, min_crar, min_cet1, min_tier1, min_lcr, min_nsfr, "
            "is_home, generated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (COUNTRY_CODE, 'Taiwan', 'Asia', 'East Asia', 'TWD', 'NT$',
             'Central Bank of the Republic of China (Taiwan)', 'CBC', 'FSC',
             'Basel III', 'AA-', 10.5, 7.0, 8.5, 100.0, 100.0, 0)
        )
        print(f"[0a] Created countries row for {COUNTRY_CODE} (Taiwan).")

    n_macro = cur.execute("SELECT COUNT(*) FROM country_macro WHERE country_code=?", (COUNTRY_CODE,)).fetchone()[0]
    if n_macro > 0:
        print(f"[0b] {COUNTRY_CODE} already has {n_macro} country_macro row(s) - leaving as-is.")
    else:
        # Disclosed estimates (CBC/DGBAS), same convention as every other
        # country_macro row on this platform - not audited real-time data.
        cur.execute(
            "INSERT INTO country_macro (country_code, period, gdp_usd_bn, gdp_growth_pct, "
            "inflation_cpi_pct, policy_rate_pct, unemployment_pct, public_debt_gdp_pct, "
            "current_account_gdp_pct, fx_rate_per_usd, population_mn, source, generated_at, "
            "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
            "macro_regime_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?,?,?,?,?)",
            (COUNTRY_CODE, '2023-Q2', 760.0, 1.4, 2.5, 1.875, 3.5, 28.0, 12.0, 31.0, 23.4,
             'CBC/DGBAS (disclosed estimate)', 0.0, 0.0, 0.0, 0.0, 0.0)
        )
        cur.execute(
            "INSERT INTO country_macro (country_code, period, gdp_usd_bn, gdp_growth_pct, "
            "inflation_cpi_pct, policy_rate_pct, unemployment_pct, public_debt_gdp_pct, "
            "current_account_gdp_pct, fx_rate_per_usd, population_mn, source, generated_at, "
            "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
            "macro_regime_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?,?,?,?,?)",
            (COUNTRY_CODE, '2024-Q2', 790.0, 3.9, 2.0, 2.0, 3.3, 28.0, 12.0, 32.0, 23.4,
             'CBC/DGBAS (disclosed estimate)', 2.5, -0.5, 0.125, -0.2, 8.4)
        )
        print(f"[0b] Created 2 country_macro rows for {COUNTRY_CODE} (2023-Q2 prior, 2024-Q2 current).")
    conn.commit()


def _ensure_bank(conn):
    cur = conn.cursor()
    row = cur.execute("SELECT bank_id, world, bank_name FROM banks WHERE bank_id=?", (BANK_ID,)).fetchone()
    if row and row[2] == BANK_NAME:
        print(f"[1] {BANK_ID} already exists as '{BANK_NAME}' (world={row[1]}) - leaving as-is.")
        return
    if row:
        cur.execute(
            "UPDATE banks SET bank_name=?, bank_code=?, country=?, headquarters_city=?, "
            "headquarters_state=?, country_code=? WHERE bank_id=?",
            (BANK_NAME, 'TWCB', 'Taiwan', 'Taipei', 'Taipei', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}'.")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'TWCB', 'Taiwan', 'Taipei', 'Taipei', None, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=TWN. "
          f"year_established left NULL - this is a generic placeholder identity, "
          f"not a real institution with a verifiable founding year.")


def _risk_ordered_encoding_oof(df, source_col, target_col='target', n_splits=5):
    """
    Out-of-fold risk-ordered encoding: for each fold, the category->risk-rank
    mapping is learned from the OTHER folds only, then applied to the held-out
    fold. No row's own outcome ever informs its own encoding - fixes the
    leakage BANK010's onboarding had (full-file encoding computed pre-split).
    """
    codes = pd.Series(index=df.index, dtype='float64')
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    valid_mask = df[source_col].notna()
    valid_idx = df.index[valid_mask].to_numpy()

    for train_pos, holdout_pos in kf.split(valid_idx):
        train_idx = valid_idx[train_pos]
        holdout_idx = valid_idx[holdout_pos]
        rates = df.loc[train_idx].groupby(source_col)[target_col].mean().sort_values()
        code_map = {cat: i + 1 for i, cat in enumerate(rates.index)}
        # Categories seen only in the holdout fold (not in this fold's training
        # portion) fall back to the middle rank - genuinely unknown, not a guess
        # at extremes.
        fallback = (len(code_map) + 1) / 2.0
        codes.loc[holdout_idx] = df.loc[holdout_idx, source_col].map(code_map).fillna(fallback)

    return codes


def build_dataframe():
    df = pd.read_csv(TAIWAN_CSV, low_memory=False)
    print(f"[2] Loaded {len(df)} rows from Taiwan_UCI_Credit_Card.csv")

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct, "
        "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
        "macro_regime_score, fx_rate_per_usd "
        "FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
        (COUNTRY_CODE,)
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"No country_macro row for {COUNTRY_CODE} - _ensure_country_and_macro() should have run first.")
    (gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp,
     mrs, fx_rate_twd_per_usd) = row
    print(f"[3] Using TWN macro (FX rate: {fx_rate_twd_per_usd} TWD/USD)")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    out['default_flag'] = df['target'].astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    # ── Direct mappings ──────────────────────────────────────────────────
    out['age'] = df['AGE']

    # ── Currency-converted direct mappings (NT$ -> USD) ─────────────────
    out['credit_limit'] = df['LIMIT_BAL'] / fx_rate_twd_per_usd
    for m_target, m_source in zip(range(1, 7), ['BILL_AMT1', 'BILL_AMT2', 'BILL_AMT3', 'BILL_AMT4', 'BILL_AMT5', 'BILL_AMT6']):
        out[f'bill_amt_m{m_target}'] = df[m_source] / fx_rate_twd_per_usd
    for m_target, m_source in zip(range(1, 7), ['PAY_AMT1', 'PAY_AMT2', 'PAY_AMT3', 'PAY_AMT4', 'PAY_AMT5', 'PAY_AMT6']):
        out[f'payment_amt_m{m_target}'] = df[m_source] / fx_rate_twd_per_usd

    # ── Repayment status, re-numbered m1..m6 (no currency conversion - these
    # are status codes, not monetary amounts) ───────────────────────────────
    for m_target, m_source in zip(range(1, 7), ['PAY_0', 'PAY_2', 'PAY_3', 'PAY_4', 'PAY_5', 'PAY_6']):
        out[f'repay_status_m{m_target}'] = df[m_source]

    # ── Out-of-fold risk-ordered categorical encodings (this bank only) ────
    enc_df = pd.DataFrame({'target': out['default_flag'], 'EDUCATION': df['EDUCATION'], 'MARRIAGE': df['MARRIAGE']})
    out['education_enc'] = _risk_ordered_encoding_oof(enc_df, 'EDUCATION')
    out['marital_status_enc'] = _risk_ordered_encoding_oof(enc_df, 'MARRIAGE')

    # ── Flagged field - populated for completeness, excluded from training
    # (see module docstring compliance note) ────────────────────────────────
    out['gender_enc'] = df['SEX']

    # ── Derived fields, computed from real observed history ────────────────
    repay_cols = [f'repay_status_m{i}' for i in range(1, 7)]
    out['previous_default_flag'] = (out[repay_cols] > 0).any(axis=1).astype(int)
    out['num_late_payments_past_12m'] = (out[repay_cols] > 0).sum(axis=1)

    bill_cols = [f'bill_amt_m{i}' for i in range(1, 7)]
    pay_cols = [f'payment_amt_m{i}' for i in range(1, 7)]
    out['credit_utilization_ratio'] = np.where(
        out['credit_limit'] > 0, out['bill_amt_m1'] / out['credit_limit'], np.nan
    )
    with np.errstate(divide='ignore', invalid='ignore'):
        ratios = out[pay_cols].to_numpy() / np.where(out[bill_cols].to_numpy() > 0, out[bill_cols].to_numpy(), np.nan)
    out['payment_coverage_ratio'] = np.nanmean(ratios, axis=1)

    # ── Country macro: real reference-data join (TWN, latest period) ───────
    for col, val in zip(
        ['gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
         'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct', 'delta_unemployment_pct',
         'macro_regime_score'],
        [gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp, mrs]
    ):
        out[col] = val

    for col in GENUINELY_ABSENT_COLS:
        out[col] = None

    return out


def load(out):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,))
    print(f"[4] Cleared {cur.rowcount} existing {BANK_ID} rows.")

    cols = list(out.columns)
    placeholders = ','.join('?' * len(cols))
    rows = [
        tuple(None if (pd.isna(v) if not isinstance(v, str) else False) else v for v in row)
        for row in out[cols].itertuples(index=False)
    ]
    cur.executemany(
        f"INSERT INTO bank_loan_metrics ({','.join(cols)}) VALUES ({placeholders})", rows
    )
    conn.commit()
    print(f"[5] Inserted {len(rows)} bank_loan_metrics rows for {BANK_ID}.")

    total = conn.execute(
        "SELECT COUNT(*) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()[0]
    print(f"\n[6] Column coverage for {BANK_ID} ({total} rows):")
    check_cols = ['age', 'credit_limit', 'education_enc', 'marital_status_enc', 'gender_enc',
                  'repay_status_m1', 'bill_amt_m1', 'payment_amt_m1',
                  'previous_default_flag', 'num_late_payments_past_12m',
                  'credit_utilization_ratio', 'payment_coverage_ratio',
                  'gdp_growth_pct', 'default_flag']
    for col in check_cols:
        n = conn.execute(
            f"SELECT COUNT({col}) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
        ).fetchone()[0]
        print(f"    {col:28s} {n:6d}/{total} ({n / total * 100:5.1f}%)")

    stats = conn.execute(
        "SELECT AVG(default_flag), MIN(credit_limit), AVG(credit_limit), MAX(credit_limit) "
        "FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()
    print(f"\n[7] Default rate: {stats[0] * 100:.2f}%")
    print(f"[8] credit_limit (USD): min={stats[1]:.0f} avg={stats[2]:.0f} max={stats[3]:.0f}")
    conn.close()


if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    _ensure_country_and_macro(conn)
    _ensure_bank(conn)
    conn.close()

    df_out = build_dataframe()
    load(df_out)

    print(f"\nDone. {BANK_ID} ({BANK_NAME}) onboarded as a Real Earth, training-only bank.")
    print("Note: gender_enc/marital_status_enc are populated but NOT yet added to")
    print("ml_models/trainer.py's FEATURE_COLS - a deliberate compliance gate, not an oversight.")
    print("Note: credit_limit/repay_status_m*/bill_amt_m*/payment_amt_m*/credit_utilization_ratio/")
    print("payment_coverage_ratio are also NOT yet in FEATURE_COLS - trainer.py needs the")
    print("bank-scoped auto-discovery enhancement (discussed, not yet built) before a training")
    print("run for BANK011 will actually use anything beyond the fixed 37-feature canonical set.")
    print("Next: python -c \"from ml_models.trainer import run_training; "
          "run_training(bank_ids=['BANK011'], exposure_class='GENERIC')\"")
