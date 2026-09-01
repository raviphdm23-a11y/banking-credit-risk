"""
onboard_th02.py
──────────────────
Onboards BANK016 ("UK Consumer Credit Reference Bank" - generic placeholder
identity; this is the classic Lyn Thomas credit-scoring textbook dataset,
not tied to a named real institution) as a Real Earth bank, from
sample datasets/TH02.csv.

SCOPE: TRAINING-ONLY - no loan-amount/facility-size field exists in this
file at all (it's an application-scoring dataset, not attached to a
specific loan ask), same forcing reason as BANK010/BANK013.

Currency: GBP (UK). GBR is already seeded in countries/country_macro (from
BANK004 Barclays Bank PLC's Utopian setup) - reused directly, no new
seeding needed. Converted to USD via country_macro.GBR.fx_rate_per_usd.

*** TARGET POLARITY INVERTED - CONFIRMED BY EVIDENCE, NOT ASSUMED ***
Every other bank onboarded this session uses a `target` column where 1 =
default/bad. TH02.csv's `target` is the OPPOSITE convention (1 = good/
approved), verified empirically before onboarding, not assumed:
  - Raw target base rate is 73.6% "1" - implausibly HIGH for a default rate,
    but a very plausible "good" rate for an accepted-applicant population.
  - groupby('target')['DAINC'].mean(): target=1 rows average GBP 23,009
    income vs GBP 16,317 for target=0 - higher income correlating with
    target=1 is only consistent with target=1 meaning GOOD, not default.
  default_flag = 1 - target (inverted here, and ONLY here).

Mappings onto EXISTING canonical fields:
  NKID  -> num_dependents (direct)
  PHON  -> has_registered_phone (REUSED from BANK012)
  AES   -> employment_type_enc (risk-ordered, opaque single-letter codes)
  DAINC -> annual_income (GBP->USD converted)
  RES   -> residence_type_enc (risk-ordered, opaque single-letter codes)

New fields (mortgage_balance/home_value SHARED with BANK015/hmeq):
  YOB    -> year_of_birth_2digit (2-digit year, NOT converted to age - the
            reference year/century is not confirmed, so a computed age
            would be a fabrication, not a derivation)
  DEP    -> num_additional_dependents (distinct from NKID/num_dependents)
  SINC   -> spouse_income (GBP->USD converted)
  DHVAL  -> home_value (GBP->USD converted)
  DMORT  -> mortgage_balance (GBP->USD converted)
  DOUTM  -> outstanding_debt_mortgage_related (GBP->USD converted)
  DOUTL  -> outstanding_debt_other_loan (GBP->USD converted)
  DOUTHP -> outstanding_debt_hire_purchase (GBP->USD converted)
  DOUTCC -> outstanding_debt_credit_card (GBP->USD converted)

No imputation: 0 nulls in the source file, no fields need NULL-filling
beyond genuinely absent canonical fields.

Run: python operations/scripts/onboard_th02.py
"""

import os
import sqlite3
import pandas as pd
from sklearn.model_selection import KFold

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
CSV = os.path.join(_ROOT, 'sample datasets', 'TH02.csv')

BANK_ID = 'BANK016'
BANK_NAME = 'UK Consumer Credit Reference Bank'
COUNTRY_CODE = 'GBR'
RANDOM_STATE = 42

GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'age', 'foir', 'city_tier_enc', 'education_enc', 'months_in_residence',
    'loan_purpose_enc', 'cibil_score', 'previous_default_flag',
    'months_as_customer', 'num_late_payments_past_12m', 'existing_loans_count',
    'is_rural', 'num_existing_products', 'exposure_class',
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
            (BANK_NAME, 'UKCC', 'United Kingdom', 'Leeds', 'England', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}'.")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'UKCC', 'United Kingdom', 'Leeds', 'England', None, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=GBR. "
          f"year_established left NULL - generic placeholder identity.")


def _risk_ordered_encoding_oof(df, source_col, target_col='default_flag', n_splits=5):
    codes = pd.Series(index=df.index, dtype='float64')
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    valid_idx = df.index[df[source_col].notna()].to_numpy()
    for train_pos, holdout_pos in kf.split(valid_idx):
        train_idx = valid_idx[train_pos]
        holdout_idx = valid_idx[holdout_pos]
        rates = df.loc[train_idx].groupby(source_col)[target_col].mean().sort_values()
        code_map = {cat: i + 1 for i, cat in enumerate(rates.index)}
        fallback = (len(code_map) + 1) / 2.0
        codes.loc[holdout_idx] = df.loc[holdout_idx, source_col].map(code_map).fillna(fallback)
    return codes


def build_dataframe():
    df = pd.read_csv(CSV, low_memory=False)
    print(f"[2] Loaded {len(df)} rows from TH02.csv")

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct, "
        "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
        "macro_regime_score, fx_rate_per_usd FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
        (COUNTRY_CODE,)
    ).fetchone()
    conn.close()
    (gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp, mrs, fx_rate_gbp_per_usd) = row
    print(f"[3] Using GBR macro (FX rate: {fx_rate_gbp_per_usd} GBP/USD)")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    # INVERTED - see module docstring for the empirical evidence.
    out['default_flag'] = (1 - df['target']).astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    out['num_dependents'] = df['NKID']
    out['has_registered_phone'] = df['PHON']
    # A handful of rows have genuine DAINC=0 (dependent spouse/unemployed
    # applicant) - floored to the platform's validated annual_income minimum
    # (1.0) rather than literal 0, which _validate_dataframe's range check
    # rejects outright for the whole dataset (same failure mode discovered
    # with BANK015's foir - fixed the same way, floor/cap, not fabricate).
    out['annual_income'] = (df['DAINC'] / fx_rate_gbp_per_usd).clip(lower=1.0)

    enc_df = pd.DataFrame({'default_flag': out['default_flag'], 'AES': df['AES'], 'RES': df['RES']})
    out['employment_type_enc'] = _risk_ordered_encoding_oof(enc_df, 'AES')
    out['residence_type_enc'] = _risk_ordered_encoding_oof(enc_df, 'RES')

    out['year_of_birth_2digit'] = df['YOB']
    out['num_additional_dependents'] = df['DEP']
    out['spouse_income'] = df['SINC'] / fx_rate_gbp_per_usd
    out['home_value'] = df['DHVAL'] / fx_rate_gbp_per_usd
    out['mortgage_balance'] = df['DMORT'] / fx_rate_gbp_per_usd
    out['outstanding_debt_mortgage_related'] = df['DOUTM'] / fx_rate_gbp_per_usd
    out['outstanding_debt_other_loan'] = df['DOUTL'] / fx_rate_gbp_per_usd
    out['outstanding_debt_hire_purchase'] = df['DOUTHP'] / fx_rate_gbp_per_usd
    out['outstanding_debt_credit_card'] = df['DOUTCC'] / fx_rate_gbp_per_usd

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
    for col in ['num_dependents', 'has_registered_phone', 'annual_income', 'employment_type_enc',
                'residence_type_enc', 'home_value', 'mortgage_balance', 'default_flag']:
        n = conn.execute(f"SELECT COUNT({col}) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
        print(f"    {col:32s} {n:6d}/{total} ({n / total * 100:5.1f}%)")

    stats = conn.execute(
        "SELECT AVG(default_flag), MIN(annual_income), AVG(annual_income), MAX(annual_income) "
        "FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()
    print(f"\n[7] Default rate (post-inversion): {stats[0] * 100:.2f}%")
    print(f"[8] annual_income (USD): min={stats[1]:.0f} avg={stats[2]:.0f} max={stats[3]:.0f}")
    conn.close()


if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    _ensure_bank(conn)
    conn.close()

    df_out = build_dataframe()
    load(df_out)

    print(f"\nDone. {BANK_ID} ({BANK_NAME}) onboarded as a Real Earth, training-only bank.")
