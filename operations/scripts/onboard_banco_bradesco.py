"""
onboard_banco_bradesco.py
────────────────────────────
Onboards Banco Bradesco S.A. (BANK010) as a Real Earth bank, from
sample datasets/PAK.csv, per the mapping in
operations/scripts/onboarding_maps/BANK010_banco_bradesco.json.

CORRECTED IDENTITY: this dataset was originally onboarded under the name
"Bank of Punjab" (India) - wrong. PAK.csv is the PAKDD 2010 Credit Scoring
competition dataset: real Brazilian state/city names, a NACIONALITY field,
and demographics/income figures that don't remotely fit an Indian
applicant population once validated against the platform's INR-scale
checks. Re-onboarded here as a real Brazilian bank (country_code='BRA'),
which is what the source data actually is.

TRAINING-ONLY, per the confirmed scope decision: PAK.csv has no loan-
amount/exposure field at all - it's applicant/outcome data, not a loan
book. This script creates:
  1. One `banks` row for BANK010 (Banco Bradesco S.A.), world='real',
     country_code='BRA'.
  2. `bank_loan_metrics` rows (all 50,000 PAK.csv rows) for PD model
     training only.

No `customers`/`customer_kyc`/`loans`/`accounts`/`credit_risk_metrics`
rows are created - no operational loan book, no regulatory/financial/
performance reporting from this pass, only a trainable bank-specific
model.

Currency: monetary figures (PERSONAL_MONTHLY_INCOME) are assumed BRL
(Brazil's real currency, matching the source data's actual origin) and
converted to USD using country_macro.BRA's fx_rate_per_usd - the
platform's existing FX reference field, populated for Brazil for exactly
this purpose. Real Earth monetary values are canonically USD-denominated
(not each bank's native currency, and not INR like Utopian Earth) per
the explicit instruction this conversion approach was built under.

No imputation: any canonical feature genuinely absent from PAK.csv (the 4
core ratios, cibil_score, all delta/trend features, exposure_class, etc.)
is left NULL, never filled - ml_models/trainer.py's blank-column-exclusion
logic (run_training(bank_ids=['BANK010'], exposure_class='GENERIC'))
handles this correctly at training time.

Categorical encodings (education_enc/residence_type_enc/employment_type_enc)
are risk-ordered by this bank's OWN observed default rate - self-consistent
within BANK010 only, never comparable to the other 9 (Utopian Earth)
banks' encodings, which are anchored to real ref_lookup labels. This is
exactly why BANK010 must never be pooled into combined/cross-bank training.

Idempotent - clears BANK010's existing bank_loan_metrics rows before
reinserting.

Run: python operations/scripts/onboard_banco_bradesco.py
"""

import os
import sqlite3
import pandas as pd

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
PAK_CSV = os.path.join(_ROOT, 'sample datasets', 'PAK.csv')

BANK_ID = 'BANK010'
BANK_NAME = 'Banco Bradesco S.A.'
COUNTRY_CODE = 'BRA'

# Genuinely absent from PAK.csv - left NULL, never fabricated. See
# unmapped_required_fields_no_source_at_all in the mapping file.
GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'foir', 'city_tier_enc', 'loan_purpose_enc', 'cibil_score',
    'previous_default_flag', 'months_as_customer', 'num_late_payments_past_12m',
    'existing_loans_count', 'is_rural', 'delta_de_ratio', 'delta_cibil',
    'months_since_origination', 'exposure_class', 'ecs_bounce_count',
    'other_lender_emi_ratio', 'income_disruption_flag', 'sector_stress_index',
    'ltv_trend_pct', 'pd_observed',
]


def _ensure_bank(conn):
    cur = conn.cursor()
    cur.execute("SELECT bank_id, world, bank_name FROM banks WHERE bank_id=?", (BANK_ID,))
    row = cur.fetchone()
    if row and row[2] == BANK_NAME:
        print(f"[1] {BANK_ID} already exists as '{BANK_NAME}' (world={row[1]}) - leaving as-is.")
        return
    if row:
        # Correcting a prior mis-identified onboarding (was 'Bank of Punjab'/IND).
        cur.execute(
            "UPDATE banks SET bank_name=?, bank_code=?, country=?, headquarters_city=?, "
            "headquarters_state=?, country_code=? WHERE bank_id=?",
            (BANK_NAME, 'BBDC', 'Brazil', 'Osasco', 'Sao Paulo', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}' (Brazil, world=real).")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'BBDC', 'Brazil', 'Osasco', 'Sao Paulo', 1943, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=BRA.")


def _risk_ordered_encoding(df, source_col):
    """Rank a categorical column's own observed categories by this bank's
    OWN default rate (ascending risk, 1=lowest) - the platform's
    ref_lookup.risk_order convention, applied self-consistently since no
    real data dictionary exists for these opaque codes. Rows with a NULL
    source value map to NULL, not the modal/median category."""
    valid = df[source_col].notna()
    rates = df.loc[valid].groupby(source_col)['target'].mean().sort_values()
    code_map = {cat: i + 1 for i, cat in enumerate(rates.index)}
    return df[source_col].map(code_map)


def build_dataframe():
    df = pd.read_csv(PAK_CSV, low_memory=False)
    print(f"[2] Loaded {len(df)} rows from PAK.csv")

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
        raise RuntimeError(f"No country_macro row for {COUNTRY_CODE} - seed it before onboarding.")
    (gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp,
     mrs, fx_rate_brl_per_usd) = row
    print(f"[3] Using BRA macro (FX rate: {fx_rate_brl_per_usd} BRL/USD)")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    out['default_flag'] = df['target'].astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    # ── Direct/derived mappings (see BANK010_banco_bradesco.json) ──────────
    out['age'] = df['AGE'].clip(lower=18, upper=85)
    out['num_dependents'] = df['QUANT_DEPENDANTS'].clip(upper=20)
    # BRL -> USD conversion (Real Earth's canonical monetary unit), THEN cap
    # at P99 (computed post-conversion) to control outliers, THEN annualize.
    income_usd_monthly = df['PERSONAL_MONTHLY_INCOME'] / fx_rate_brl_per_usd
    income_p99_usd = income_usd_monthly.quantile(0.99)
    out['annual_income'] = income_usd_monthly.clip(upper=income_p99_usd) * 12
    out['years_employed'] = df['MONTHS_IN_THE_JOB'] / 12.0
    out['months_in_residence'] = df['MONTHS_IN_RESIDENCE']
    card_cols = ['FLAG_VISA', 'FLAG_MASTERCARD', 'FLAG_DINERS', 'FLAG_AMERICAN_EXPRESS', 'FLAG_OTHER_CARDS']
    out['num_existing_products'] = df[card_cols].sum(axis=1)

    # ── Risk-ordered categorical encodings (this bank only) ────────────────
    out['education_enc'] = _risk_ordered_encoding(df, 'EDUCATION_LEVEL_2')
    out['residence_type_enc'] = _risk_ordered_encoding(df, 'RESIDENCE_TYPE')
    out['employment_type_enc'] = _risk_ordered_encoding(df, 'OCCUPATION_TYPE')

    # ── Country macro: real reference-data join (BRA, latest period) - same
    # mechanism every other bank uses, not fabrication. ─────────────────────
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
        tuple(None if pd.isna(v) else v for v in row)
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
    check_cols = ['age', 'num_dependents', 'annual_income', 'years_employed',
                  'months_in_residence', 'education_enc', 'residence_type_enc',
                  'employment_type_enc', 'num_existing_products',
                  'de_ratio', 'cibil_score', 'gdp_growth_pct', 'default_flag']
    for col in check_cols:
        n = conn.execute(
            f"SELECT COUNT({col}) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
        ).fetchone()[0]
        print(f"    {col:22s} {n:6d}/{total} ({n / total * 100:5.1f}%)")

    stats = conn.execute(
        "SELECT AVG(default_flag), MIN(annual_income), AVG(annual_income), MAX(annual_income) "
        "FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()
    print(f"\n[7] Default rate: {stats[0] * 100:.2f}%")
    print(f"[8] annual_income (USD): min={stats[1]:.0f} avg={stats[2]:.0f} max={stats[3]:.0f}")
    conn.close()


if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    _ensure_bank(conn)
    conn.close()

    df_out = build_dataframe()
    load(df_out)

    print(f"\nDone. {BANK_ID} ({BANK_NAME}) onboarded as a Real Earth, training-only bank.")
    print("Next: train its own model via")
    print("  ml_models.trainer.run_training(bank_ids=['BANK010'], exposure_class='GENERIC')")
