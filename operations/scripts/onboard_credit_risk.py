"""
onboard_credit_risk.py
─────────────────────────
Onboards BANK014 ("US Personal Loan Reference Bank" - generic placeholder
identity, the widely-used Kaggle "Credit Risk Dataset" is not tied to a
named real institution) as a Real Earth bank, from
sample datasets/credit_risk_cleaned.csv.

SCOPE: TRAINING-ONLY (same default, not re-confirmed per-bank) - even
though loan_amnt exists (a real facility-size field), the established
default this session has been training-only unless explicitly decided
otherwise.

Currency: US-based, already USD - no conversion needed (same as BANK013).

KNOWN AMBIGUITY, documented not silently resolved: this file has BOTH a
`loan_status` and a `target` column, and they DISAGREE (crosstab confirms
they are not the same signal - e.g. loan_status=0 & target=1 happens 3,573
times). `target` is used here for default_flag, consistent with every
other bank onboarded this session (all of which use a column literally
named `target`) - loan_status is left unmapped, not silently discarded
without a reason.

Data-quality fixes (same clipping precedent as BANK010's AGE column):
  - person_age: 5 rows > 100 (max 144, clear data-entry defects) -> clipped
    to [18, 85], not dropped.
  - person_emp_length: 2 rows > 60 (max 123) -> clipped to [0, 50].
  - person_income: capped at the file's own P99 to control a small number
    of extreme outliers (max recorded value $6,000,000/yr) - same
    "cap at P99, don't drop" approach used for BANK010's annual_income.

Mappings onto EXISTING canonical fields (this file aligns well with the
canonical schema - a leaner mapping than BANK013's pure-new-fields case):
  loan_intent           -> loan_purpose_enc   (already integer-coded 0-5;
                            +1 shift to the platform's 1-indexed convention)
  person_home_ownership -> residence_type_enc (already integer-coded 0-3;
                            +1 shift, same convention)
  loan_amnt              -> requested_loan_amount (REUSED from BANK012 -
                            same generic column, not a new one)

Category labels for loan_intent/person_home_ownership/loan_grade (used only
for the UI dropdown display in backend/bank_field_meta.py) are INFERRED from
this dataset's well-known public origin (standard alphabetical LabelEncoder
convention: home_ownership={MORTGAGE,OTHER,OWN,RENT}, loan_intent=
{DEBTCONSOLIDATION,EDUCATION,HOMEIMPROVEMENT,MEDICAL,PERSONAL,VENTURE},
loan_grade=A..G) - moderate confidence, not verified against the original
preprocessing code. The actual stored values are the source integers
either way, so a wrong label guess would only affect a dropdown caption,
never the data itself.

Run: python operations/scripts/onboard_credit_risk.py
"""

import os
import sqlite3
import pandas as pd

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
CSV = os.path.join(_ROOT, 'sample datasets', 'credit_risk_cleaned.csv')

BANK_ID = 'BANK014'
BANK_NAME = 'US Personal Loan Reference Bank'
COUNTRY_CODE = 'USA'

GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'employment_type_enc', 'foir', 'num_dependents', 'city_tier_enc',
    'education_enc', 'months_in_residence', 'cibil_score',
    'months_as_customer', 'num_late_payments_past_12m', 'existing_loans_count',
    'is_rural', 'num_existing_products', 'previous_default_flag', 'exposure_class',
    'delta_de_ratio', 'delta_cibil', 'months_since_origination',
    'ecs_bounce_count', 'other_lender_emi_ratio', 'income_disruption_flag',
    'sector_stress_index', 'ltv_trend_pct',
]


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
            (BANK_NAME, 'USPL', 'United States', 'Austin', 'Texas', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}'.")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'USPL', 'United States', 'Austin', 'Texas', None, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=USA. "
          f"year_established left NULL - generic placeholder identity.")


def build_dataframe():
    df = pd.read_csv(CSV, low_memory=False)
    print(f"[2] Loaded {len(df)} rows from credit_risk_cleaned.csv")

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct, "
        "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
        "macro_regime_score FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
        (COUNTRY_CODE,)
    ).fetchone()
    conn.close()
    (gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp, mrs) = row
    print(f"[3] Using USA macro (already seeded)")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    out['default_flag'] = df['target'].astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    # ── Data-quality clipping (documented in module docstring) ─────────────
    out['age'] = df['person_age'].clip(lower=18, upper=85)
    out['years_employed'] = df['person_emp_length'].clip(lower=0, upper=50)
    income_p99 = df['person_income'].quantile(0.99)
    out['annual_income'] = df['person_income'].clip(upper=income_p99)

    # ── Direct maps onto EXISTING canonical fields (+1 shift to 1-indexed) ─
    out['loan_purpose_enc'] = df['loan_intent'] + 1
    out['residence_type_enc'] = df['person_home_ownership'] + 1

    # ── requested_loan_amount REUSED from BANK012 (German) - same generic
    # column, both banks' loan-amount data lands in the same place. ────────
    out['requested_loan_amount'] = df['loan_amnt']

    # ── New fields ───────────────────────────────────────────────────────
    out['loan_grade_enc'] = df['loan_grade'] + 1
    out['loan_interest_rate_pct'] = df['loan_int_rate']
    out['loan_to_income_ratio'] = df['loan_percent_income']
    out['credit_history_length_years'] = df['cb_person_cred_hist_length']

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
    cur.executemany(f"INSERT INTO bank_loan_metrics ({','.join(cols)}) VALUES ({placeholders})", rows)
    conn.commit()
    print(f"[5] Inserted {len(rows)} bank_loan_metrics rows for {BANK_ID}.")

    total = conn.execute("SELECT COUNT(*) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
    print(f"\n[6] Column coverage for {BANK_ID} ({total} rows):")
    for col in ['age', 'annual_income', 'years_employed', 'loan_purpose_enc', 'residence_type_enc',
                'requested_loan_amount', 'loan_grade_enc', 'loan_interest_rate_pct',
                'loan_to_income_ratio', 'credit_history_length_years', 'default_flag']:
        n = conn.execute(f"SELECT COUNT({col}) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
        print(f"    {col:32s} {n:6d}/{total} ({n / total * 100:5.1f}%)")

    stats = conn.execute(
        "SELECT AVG(default_flag), MIN(requested_loan_amount), AVG(requested_loan_amount), MAX(requested_loan_amount) "
        "FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()
    print(f"\n[7] Default rate: {stats[0] * 100:.2f}%")
    print(f"[8] requested_loan_amount (USD): min={stats[1]:.0f} avg={stats[2]:.0f} max={stats[3]:.0f}")
    conn.close()


if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    _ensure_bank(conn)
    conn.close()

    df_out = build_dataframe()
    load(df_out)

    print(f"\nDone. {BANK_ID} ({BANK_NAME}) onboarded as a Real Earth, training-only bank.")
