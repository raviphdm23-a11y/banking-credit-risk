"""
onboard_hmeq.py
──────────────────
Onboards BANK015 ("US Home Equity Reference Bank" - generic placeholder
identity; the classic SAS "HMEQ" sample dataset is not tied to a named real
institution) as a Real Earth bank, from sample datasets/hmeq.csv.

SCOPE: TRAINING-ONLY (same established default) - LOAN is a genuine
facility-size field, but consistent with every other bank this session
unless explicitly decided otherwise.

Currency: US-based, already USD - no conversion needed.

Target polarity: target=1 already means default/bad (matches this
dataset's well-known public convention - target base rate 19.95% is the
documented rate for HMEQ) - NOT inverted, unlike BANK016/TH02.

Mappings onto EXISTING canonical fields:
  LOAN     -> requested_loan_amount (REUSED, same generic column as BANK012/014)
  REASON   -> loan_purpose_enc (risk-ordered: DebtCon/HomeImp)
  JOB      -> employment_type_enc (risk-ordered: Other/ProfExe/Office/Mgr/Self/Sales)
  YOJ      -> years_employed (direct)
  DEBTINC  -> foir (direct /100 - source is a 0-100ish percentage, foir is a
              0-1 fraction on this platform)

New fields (mortgage_balance/home_value SHARED with BANK016/TH02 - see
add_hmeq_and_th02_columns.py):
  MORTDUE -> mortgage_balance
  VALUE   -> home_value
  DEROG   -> num_derogatory_reports
  DELINQ  -> num_delinquent_lines
  CLAGE   -> oldest_credit_line_age_months
  NINQ    -> num_recent_inquiries
  CLNO    -> num_credit_lines

No imputation: this dataset has substantial genuine missingness (up to 21%
on DEBTINC) - left NULL exactly as found, not imputed. Out-of-fold
risk-ordered encoding used for REASON/JOB (same leakage-safe method as
every bank since BANK011).

Run: python operations/scripts/onboard_hmeq.py
"""

import os
import sqlite3
import pandas as pd
from sklearn.model_selection import KFold

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
CSV = os.path.join(_ROOT, 'sample datasets', 'hmeq.csv')

BANK_ID = 'BANK015'
BANK_NAME = 'US Home Equity Reference Bank'
COUNTRY_CODE = 'USA'
RANDOM_STATE = 42

GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'age', 'annual_income', 'num_dependents', 'city_tier_enc', 'education_enc',
    'residence_type_enc', 'months_in_residence', 'cibil_score',
    'previous_default_flag', 'months_as_customer', 'num_late_payments_past_12m',
    'existing_loans_count', 'is_rural', 'num_existing_products', 'exposure_class',
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
            (BANK_NAME, 'USHE', 'United States', 'Columbus', 'Ohio', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}'.")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'USHE', 'United States', 'Columbus', 'Ohio', None, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=USA. "
          f"year_established left NULL - generic placeholder identity.")


def _risk_ordered_encoding_oof(df, source_col, target_col='target', n_splits=5):
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
    print(f"[2] Loaded {len(df)} rows from hmeq.csv")

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct, "
        "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
        "macro_regime_score FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
        (COUNTRY_CODE,)
    ).fetchone()
    conn.close()
    (gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp, mrs) = row
    print("[3] Using USA macro (already seeded)")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    out['default_flag'] = df['target'].astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    out['requested_loan_amount'] = df['LOAN']
    out['years_employed'] = df['YOJ']
    # DEBTINC has genuine outliers up to 203% in the raw data - capped at the
    # platform's validated foir ceiling (0.9) rather than fabricating a
    # different number; same outlier-capping precedent as BANK010's
    # annual_income P99 cap. Uncapped, a single 2.03 value fails
    # _validate_dataframe's range check for the WHOLE dataset, not just that
    # row (discovered via a real training failure, not anticipated in advance).
    out['foir'] = (df['DEBTINC'] / 100.0).clip(upper=0.9)

    enc_df = pd.DataFrame({'target': out['default_flag'], 'REASON': df['REASON'], 'JOB': df['JOB']})
    out['loan_purpose_enc'] = _risk_ordered_encoding_oof(enc_df, 'REASON')
    out['employment_type_enc'] = _risk_ordered_encoding_oof(enc_df, 'JOB')

    out['mortgage_balance'] = df['MORTDUE']
    out['home_value'] = df['VALUE']
    out['num_derogatory_reports'] = df['DEROG']
    out['num_delinquent_lines'] = df['DELINQ']
    out['oldest_credit_line_age_months'] = df['CLAGE']
    out['num_recent_inquiries'] = df['NINQ']
    out['num_credit_lines'] = df['CLNO']

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
    for col in ['requested_loan_amount', 'years_employed', 'foir', 'loan_purpose_enc',
                'employment_type_enc', 'mortgage_balance', 'home_value',
                'num_derogatory_reports', 'num_delinquent_lines', 'default_flag']:
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
