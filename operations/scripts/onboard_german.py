"""
onboard_german.py
───────────────────
Onboards BANK012 ("German Composite Bank" - explicit generic placeholder
identity; the Statlog German Credit dataset is an academic benchmark, not
tied to a named real institution) as a Real Earth bank, from
sample datasets/german_credit_record.csv, per the mapping in
operations/scripts/onboarding_maps/BANK012_german_credit.json.

SCOPE (same default as BANK011, not re-confirmed per-bank): TRAINING-ONLY.
Creates:
  1. `countries` + `country_macro` rows for Germany (DEU) - not yet seeded.
  2. One `banks` row for BANK012, world='real', country_code='DEU'.
  3. `bank_loan_metrics` rows (all 1,000 rows) for PD model training only.
No `customers`/`customer_kyc`/`loans`/`accounts`/`credit_risk_metrics` rows.

Currency: credit_amount is DM (Deutsche Mark, pre-Euro). Converted DM->EUR
via the official fixed ECB conversion rate (1 EUR = 1.95583 DM - an exact
historical fact, not an estimate), then EUR->USD via
country_macro.DEU.fx_rate_per_usd (disclosed estimate).

No imputation: any canonical feature genuinely absent is left NULL. See
unmapped_required_fields_no_source_at_all in the mapping file.

Leakage-safe: all risk-ordered categorical encodings use 5-fold
out-of-fold encoding (same method as onboard_taiwan.py) - no row's own
outcome informs its own encoding.

Compliance: personal_status_sex is parsed into gender_enc + marital_status_enc
(both REUSED from BANK011's schema, not new columns). foreign_worker ->
foreign_worker_flag is a NEW field added to
ml_models.trainer.COMPLIANCE_EXCLUDED_COLS by this onboarding (confirmed
correlated with target in this dataset - see mapping file). None of these
three are added to FEATURE_COLS or eligible for auto-discovery by default.

Idempotent - clears BANK012's existing bank_loan_metrics rows before
reinserting.

Run: python operations/scripts/onboard_german.py
"""

import os
import sqlite3
import pandas as pd
from sklearn.model_selection import KFold

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
GERMAN_CSV = os.path.join(_ROOT, 'sample datasets', 'german_credit_record.csv')

BANK_ID = 'BANK012'
BANK_NAME = 'German Composite Bank'
COUNTRY_CODE = 'DEU'
RANDOM_STATE = 42
DM_PER_EUR = 1.95583  # official fixed ECB conversion rate, exact

GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'annual_income', 'foir', 'cibil_score', 'months_as_customer',
    'num_late_payments_past_12m', 'city_tier_enc', 'education_enc', 'is_rural',
    'num_existing_products', 'exposure_class',
    'delta_de_ratio', 'delta_cibil', 'months_since_origination',
    'ecs_bounce_count', 'other_lender_emi_ratio', 'income_disruption_flag',
    'sector_stress_index', 'ltv_trend_pct',
]

EMPLOYMENT_SINCE_MIDPOINT = {
    '< 1 year': 0.5,
    '1 ≤ ... < 4 years': 2.5,
    '4 ≤ ... < 7 years': 5.5,
    '≥ 7 years': 10.0,
    'unemployed': 0.0,
}


def _ensure_country_and_macro(conn):
    cur = conn.cursor()
    if cur.execute("SELECT 1 FROM countries WHERE country_code=?", (COUNTRY_CODE,)).fetchone():
        print(f"[0a] {COUNTRY_CODE} already in countries - leaving as-is.")
    else:
        cur.execute(
            "INSERT INTO countries (country_code, country_name, region, sub_region, "
            "currency_code, currency_symbol, central_bank, central_bank_abbr, capital_regulator, "
            "basel_framework, sovereign_rating, min_crar, min_cet1, min_tier1, min_lcr, min_nsfr, "
            "is_home, generated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (COUNTRY_CODE, 'Germany', 'Europe', 'Western Europe', 'EUR', '€',
             'Deutsche Bundesbank', 'Bundesbank', 'BaFin',
             'Basel III', 'AAA', 10.5, 7.0, 8.5, 100.0, 100.0, 0)
        )
        print(f"[0a] Created countries row for {COUNTRY_CODE} (Germany).")

    n_macro = cur.execute("SELECT COUNT(*) FROM country_macro WHERE country_code=?", (COUNTRY_CODE,)).fetchone()[0]
    if n_macro > 0:
        print(f"[0b] {COUNTRY_CODE} already has {n_macro} country_macro row(s) - leaving as-is.")
    else:
        cur.execute(
            "INSERT INTO country_macro (country_code, period, gdp_usd_bn, gdp_growth_pct, "
            "inflation_cpi_pct, policy_rate_pct, unemployment_pct, public_debt_gdp_pct, "
            "current_account_gdp_pct, fx_rate_per_usd, population_mn, source, generated_at, "
            "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
            "macro_regime_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?,?,?,?,?)",
            (COUNTRY_CODE, '2023-Q2', 4120.0, -0.3, 6.0, 4.0, 5.7, 64.0, 6.0, 0.93, 84.4,
             'Bundesbank/Destatis/ECB (disclosed estimate)', 0.0, 0.0, 0.0, 0.0, 0.0)
        )
        cur.execute(
            "INSERT INTO country_macro (country_code, period, gdp_usd_bn, gdp_growth_pct, "
            "inflation_cpi_pct, policy_rate_pct, unemployment_pct, public_debt_gdp_pct, "
            "current_account_gdp_pct, fx_rate_per_usd, population_mn, source, generated_at, "
            "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
            "macro_regime_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?,?,?,?,?)",
            (COUNTRY_CODE, '2024-Q2', 4280.0, 0.2, 2.4, 4.25, 5.9, 63.0, 6.5, 0.92, 84.5,
             'Bundesbank/Destatis/ECB (disclosed estimate)', 0.5, -3.6, 0.25, 0.2, 9.9)
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
            (BANK_NAME, 'GECB', 'Germany', 'Frankfurt', 'Hesse', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}'.")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'GECB', 'Germany', 'Frankfurt', 'Hesse', None, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=DEU. "
          f"year_established left NULL - generic placeholder identity, not a real institution.")


def _risk_ordered_encoding_oof(df, source_col, target_col='target', n_splits=5):
    """Out-of-fold risk-ordered encoding - see onboard_taiwan.py for full rationale."""
    codes = pd.Series(index=df.index, dtype='float64')
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    valid_mask = df[source_col].notna()
    valid_idx = df.index[valid_mask].to_numpy()

    for train_pos, holdout_pos in kf.split(valid_idx):
        train_idx = valid_idx[train_pos]
        holdout_idx = valid_idx[holdout_pos]
        rates = df.loc[train_idx].groupby(source_col)[target_col].mean().sort_values()
        code_map = {cat: i + 1 for i, cat in enumerate(rates.index)}
        fallback = (len(code_map) + 1) / 2.0
        codes.loc[holdout_idx] = df.loc[holdout_idx, source_col].map(code_map).fillna(fallback)

    return codes


def build_dataframe():
    df = pd.read_csv(GERMAN_CSV, low_memory=False)
    print(f"[2] Loaded {len(df)} rows from german_credit_record.csv")

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
     mrs, fx_rate_eur_per_usd) = row
    print(f"[3] Using DEU macro (FX rate: {fx_rate_eur_per_usd} EUR/USD, DM->EUR fixed at {DM_PER_EUR})")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    out['default_flag'] = df['target'].astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    # ── Direct / derived mappings onto EXISTING canonical fields ───────────
    out['age'] = df['age']
    out['existing_loans_count'] = df['existing_credits']
    out['num_dependents'] = df['people_liable']
    out['months_in_residence'] = df['residence_since'] * 12
    out['years_employed'] = df['employment_since'].map(EMPLOYMENT_SINCE_MIDPOINT)

    enc_df = pd.DataFrame({
        'target': out['default_flag'],
        'purpose': df['purpose'], 'housing': df['housing'], 'job': df['job'],
        'checking_status': df['checking_status'], 'credit_history': df['credit_history'],
        'savings_status': df['savings_status'], 'other_debtors': df['other_debtors'],
        'property': df['property'], 'other_installment_plans': df['other_installment_plans'],
    })
    out['loan_purpose_enc'] = _risk_ordered_encoding_oof(enc_df, 'purpose')
    out['residence_type_enc'] = _risk_ordered_encoding_oof(enc_df, 'housing')
    out['employment_type_enc'] = _risk_ordered_encoding_oof(enc_df, 'job')

    # ── New generic fields ───────────────────────────────────────────────
    out['checking_account_status_enc'] = _risk_ordered_encoding_oof(enc_df, 'checking_status')
    out['credit_history_enc'] = _risk_ordered_encoding_oof(enc_df, 'credit_history')
    out['savings_status_enc'] = _risk_ordered_encoding_oof(enc_df, 'savings_status')
    out['other_debtors_enc'] = _risk_ordered_encoding_oof(enc_df, 'other_debtors')
    out['property_type_enc'] = _risk_ordered_encoding_oof(enc_df, 'property')
    out['other_installment_plans_enc'] = _risk_ordered_encoding_oof(enc_df, 'other_installment_plans')

    out['requested_loan_amount'] = (df['credit_amount'] / DM_PER_EUR) / fx_rate_eur_per_usd
    out['installment_rate_band'] = df['installment_rate']
    out['has_registered_phone'] = (df['telephone'] == 'yes, registered').astype(int)
    out['loan_duration_months'] = df['months_duration']

    # ── Derived field onto an EXISTING canonical field ──────────────────
    out['previous_default_flag'] = (df['credit_history'] == 'delay in past').astype(int)

    # ── Compliance-flagged fields ────────────────────────────────────────
    # personal_status_sex conflates sex and marital status, and only
    # distinguishes marital sub-status for men (a documented limitation of
    # this exact dataset, not an onboarding error - see mapping file).
    gender_map = {
        'male: single': 1, 'male: married/widowed': 1, 'male: divorced/separated': 1,
        'female: divorced/separated/married': 2,
    }
    marital_map = {
        'male: single': 1, 'male: married/widowed': 2, 'male: divorced/separated': 3,
        'female: divorced/separated/married': None,  # genuinely unknown for this bucket - not guessed
    }
    out['gender_enc'] = df['personal_status_sex'].map(gender_map)
    out['marital_status_enc'] = df['personal_status_sex'].map(marital_map)
    out['foreign_worker_flag'] = (df['foreign_worker'] == 'yes').astype(int)

    # ── Country macro: real reference-data join ─────────────────────────
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

    total = conn.execute("SELECT COUNT(*) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
    print(f"\n[6] Column coverage for {BANK_ID} ({total} rows):")
    check_cols = ['age', 'requested_loan_amount', 'loan_duration_months', 'loan_purpose_enc',
                  'residence_type_enc', 'employment_type_enc', 'checking_account_status_enc',
                  'credit_history_enc', 'previous_default_flag', 'gender_enc', 'marital_status_enc',
                  'foreign_worker_flag', 'gdp_growth_pct', 'default_flag']
    for col in check_cols:
        n = conn.execute(f"SELECT COUNT({col}) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
        print(f"    {col:28s} {n:6d}/{total} ({n / total * 100:5.1f}%)")

    stats = conn.execute(
        "SELECT AVG(default_flag), MIN(requested_loan_amount), AVG(requested_loan_amount), MAX(requested_loan_amount) "
        "FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()
    print(f"\n[7] Default rate: {stats[0] * 100:.2f}%")
    print(f"[8] requested_loan_amount (USD): min={stats[1]:.0f} avg={stats[2]:.0f} max={stats[3]:.0f}")
    conn.close()


if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    _ensure_country_and_macro(conn)
    _ensure_bank(conn)
    conn.close()

    df_out = build_dataframe()
    load(df_out)

    print(f"\nDone. {BANK_ID} ({BANK_NAME}) onboarded as a Real Earth, training-only bank.")
    print("gender_enc/marital_status_enc/foreign_worker_flag populated but excluded from")
    print("auto-discovery by default (ml_models.trainer.COMPLIANCE_EXCLUDED_COLS) - use")
    print("include_compliance_excluded=True to opt in for research/benchmark comparison.")
    print("Next: python -c \"from ml_models.trainer import run_training; "
          "run_training(bank_ids=['BANK012'], exposure_class='GENERIC')\"")
