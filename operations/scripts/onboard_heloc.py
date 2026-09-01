"""
onboard_heloc.py
──────────────────
Onboards BANK013 ("US HELOC Reference Bank" - explicit generic placeholder
identity; this is FICO's own published Explainable ML Challenge dataset,
not tied to a named real institution) as a Real Earth bank, from
sample datasets/heloc.csv.

SCOPE: TRAINING-ONLY (same default as BANK010/011/012, not re-confirmed
per-bank) - heloc.csv has no loan-amount/facility-size field at all, forcing
this the same way BANK010's PAK.csv did.

Currency: heloc.csv is US-based (Home Equity Line of Credit is US mortgage
terminology) and already USD-denominated - NO currency conversion needed,
the first onboarded bank where this is true.

Sentinel codes (FICO's own documented special values, NOT genuine numbers):
    -9 = No Bureau Record or No Investigation (whole-row: applicant has no
         credit history at all - every column is -9 together, 588 rows)
    -8 = No Usable/Valid Trades or Inquiries (column-specific)
    -7 = Condition not Met (e.g. MSinceMostRecentDelq=-7 means "never
         delinquent" - a real semantic, not literally unknown, but per this
         platform's no-imputation/no-fabrication policy, converted to NULL
         rather than guessing a numeric substitute for "never")
All three convert to NULL uniformly - no imputation, consistent with every
other onboarding this session.

No demographic fields exist in this dataset at all (pure bureau/trade-line
data) - age/income/employment/education are all genuinely absent, not
approximated from anything.

Run: python operations/scripts/onboard_heloc.py
"""

import os
import sqlite3
import numpy as np
import pandas as pd

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DB = os.path.join(_ROOT, 'bank.db')
HELOC_CSV = os.path.join(_ROOT, 'sample datasets', 'heloc.csv')

BANK_ID = 'BANK013'
BANK_NAME = 'US HELOC Reference Bank'
COUNTRY_CODE = 'USA'

SENTINEL_CODES = {-9, -8, -7}

GENUINELY_ABSENT_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'age', 'employment_type_enc', 'years_employed', 'annual_income', 'foir',
    'num_dependents', 'city_tier_enc', 'education_enc', 'residence_type_enc',
    'months_in_residence', 'loan_purpose_enc', 'cibil_score',
    'months_as_customer', 'existing_loans_count', 'is_rural',
    'num_existing_products', 'exposure_class',
    'delta_de_ratio', 'delta_cibil', 'months_since_origination',
    'ecs_bounce_count', 'other_lender_emi_ratio', 'income_disruption_flag',
    'sector_stress_index', 'ltv_trend_pct',
]
# Country macro fields (gdp_growth_pct, deltas, macro_regime_score) are NOT
# in the absent list - USA is already seeded (from BANK003 JPMorgan Chase's
# Utopian Earth setup) and joined below like every other bank's onboarding.

# source_column -> canonical column (identity mapping, all new generic fields)
COLUMN_MAP = {
    'ExternalRiskEstimate': 'external_risk_score',
    'MSinceOldestTradeOpen': 'months_since_oldest_trade',
    'MSinceMostRecentTradeOpen': 'months_since_recent_trade',
    'AverageMInFile': 'avg_months_in_file',
    'NumSatisfactoryTrades': 'num_satisfactory_trades',
    'NumTrades60Ever2DerogPubRec': 'num_trades_60d_derog',
    'NumTrades90Ever2DerogPubRec': 'num_trades_90d_derog',
    'PercentTradesNeverDelq': 'pct_trades_never_delinquent',
    'MSinceMostRecentDelq': 'months_since_recent_delinquency',
    'MaxDelq2PublicRecLast12M': 'max_delinquency_12m',
    'MaxDelqEver': 'max_delinquency_ever',
    'NumTotalTrades': 'num_total_trades',
    'NumTradesOpeninLast12M': 'num_trades_opened_12m',
    'PercentInstallTrades': 'pct_installment_trades',
    'MSinceMostRecentInqexcl7days': 'months_since_recent_inquiry',
    'NumInqLast6M': 'num_inquiries_6m',
    'NumInqLast6Mexcl7days': 'num_inquiries_6m_excl7d',
    'NetFractionRevolvingBurden': 'net_fraction_revolving_burden',
    'NetFractionInstallBurden': 'net_fraction_installment_burden',
    'NumRevolvingTradesWBalance': 'num_revolving_trades_w_balance',
    'NumInstallTradesWBalance': 'num_installment_trades_w_balance',
    'NumBank2NatlTradesWHighUtilization': 'num_trades_high_utilization',
    'PercentTradesWBalance': 'pct_trades_w_balance',
}


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
            (BANK_NAME, 'USHB', 'United States', 'Chicago', 'Illinois', COUNTRY_CODE, BANK_ID)
        )
        conn.commit()
        print(f"[1] Corrected {BANK_ID} identity to '{BANK_NAME}'.")
        return
    cur.execute(
        "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
        "headquarters_state, year_established, status, country_code, world) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (BANK_ID, BANK_NAME, 'USHB', 'United States', 'Chicago', 'Illinois', None, 'Active', COUNTRY_CODE, 'real')
    )
    conn.commit()
    print(f"[1] Created {BANK_ID} ({BANK_NAME}), world='real', country=USA. "
          f"year_established left NULL - generic placeholder identity.")


def build_dataframe():
    df = pd.read_csv(HELOC_CSV, low_memory=False)
    print(f"[2] Loaded {len(df)} rows from heloc.csv")

    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct, "
        "delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct, "
        "macro_regime_score FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
        (COUNTRY_CODE,)
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"No country_macro row for {COUNTRY_CODE} - unexpected, USA should already be seeded.")
    (gdp_growth, cpi, policy_rate, unemp, d_gdp, d_cpi, d_rate, d_unemp, mrs) = row
    print(f"[3] Using USA macro (already seeded from BANK003 JPMorgan Chase's Utopian setup)")

    # Replace FICO's documented sentinel codes with genuine NaN across every
    # source column (not just the target/id columns) before anything else.
    source_cols = list(COLUMN_MAP.keys())
    df[source_cols] = df[source_cols].where(~df[source_cols].isin(SENTINEL_CODES), np.nan)
    n_sentinel_rows = df[source_cols].isna().all(axis=1).sum()
    print(f"[4] Sentinel-code rows (no bureau record at all): {n_sentinel_rows}")

    out = pd.DataFrame(index=df.index)
    out['bank_id'] = BANK_ID
    out['bank_name'] = BANK_NAME
    out['loan_id'] = [f'{BANK_ID}-{i:06d}' for i in range(len(df))]
    out['default_flag'] = df['target'].astype(int)
    out['observation_date'] = pd.Timestamp.today().date().isoformat()
    out['country_code'] = COUNTRY_CODE

    for source_col, target_col in COLUMN_MAP.items():
        out[target_col] = df[source_col]

    # Derived field onto an EXISTING canonical field, computed from real
    # observed history.
    out['previous_default_flag'] = (df['NumTrades90Ever2DerogPubRec'].fillna(0) > 0).astype(int)

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
    for col in ['external_risk_score', 'num_total_trades', 'pct_trades_never_delinquent',
                'previous_default_flag', 'default_flag']:
        n = conn.execute(f"SELECT COUNT({col}) FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
        print(f"    {col:32s} {n:6d}/{total} ({n / total * 100:5.1f}%)")

    stats = conn.execute(
        "SELECT AVG(default_flag), MIN(external_risk_score), AVG(external_risk_score), MAX(external_risk_score) "
        "FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)
    ).fetchone()
    print(f"\n[7] Default rate: {stats[0] * 100:.2f}%")
    print(f"[8] external_risk_score: min={stats[1]:.0f} avg={stats[2]:.0f} max={stats[3]:.0f}")
    conn.close()


if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    _ensure_bank(conn)
    conn.close()

    df_out = build_dataframe()
    load(df_out)

    print(f"\nDone. {BANK_ID} ({BANK_NAME}) onboarded as a Real Earth, training-only bank.")
