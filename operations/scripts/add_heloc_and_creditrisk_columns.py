"""
add_heloc_and_creditrisk_columns.py
──────────────────────────────────────
Schema-only migration for BANK013 (heloc.csv, FICO HELOC-style bureau data)
and BANK014 (credit_risk_cleaned.csv, personal-loan data). Generic, reusable
names, not dataset-prefixed - a future bureau-report-shaped or
personal-loan-shaped bank reuses these columns.

requested_loan_amount already exists (added by add_german_columns.py) and is
reused directly for BANK014's loan_amnt - not redefined here.

Does NOT insert any data. Idempotent - safe to re-run.

Run:
    python operations/scripts/add_heloc_and_creditrisk_columns.py
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

# ── BANK013 (heloc.csv) - pure bureau/trade-line data, 23 new columns ──────
HELOC_COLUMNS = [
    ('external_risk_score', 'REAL'),
    ('months_since_oldest_trade', 'REAL'),
    ('months_since_recent_trade', 'REAL'),
    ('avg_months_in_file', 'REAL'),
    ('num_satisfactory_trades', 'REAL'),
    ('num_trades_60d_derog', 'REAL'),
    ('num_trades_90d_derog', 'REAL'),
    ('pct_trades_never_delinquent', 'REAL'),
    ('months_since_recent_delinquency', 'REAL'),
    ('max_delinquency_12m', 'REAL'),
    ('max_delinquency_ever', 'REAL'),
    ('num_total_trades', 'REAL'),
    ('num_trades_opened_12m', 'REAL'),
    ('pct_installment_trades', 'REAL'),
    ('months_since_recent_inquiry', 'REAL'),
    ('num_inquiries_6m', 'REAL'),
    ('num_inquiries_6m_excl7d', 'REAL'),
    ('net_fraction_revolving_burden', 'REAL'),
    ('net_fraction_installment_burden', 'REAL'),
    ('num_revolving_trades_w_balance', 'REAL'),
    ('num_installment_trades_w_balance', 'REAL'),
    ('num_trades_high_utilization', 'REAL'),
    ('pct_trades_w_balance', 'REAL'),
]

# ── BANK014 (credit_risk_cleaned.csv) - 4 genuinely new columns; loan_intent
# and person_home_ownership map onto EXISTING loan_purpose_enc/residence_type_enc,
# and loan_amnt reuses the already-added requested_loan_amount. ────────────
CREDIT_RISK_COLUMNS = [
    ('loan_grade_enc', 'INTEGER'),
    ('loan_interest_rate_pct', 'REAL'),
    ('loan_to_income_ratio', 'REAL'),
    ('credit_history_length_years', 'REAL'),
]


def _add_columns(cur, columns, label):
    added, skipped = [], []
    for col_name, col_type in columns:
        try:
            cur.execute(f"ALTER TABLE bank_loan_metrics ADD COLUMN {col_name} {col_type}")
            added.append(col_name)
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                skipped.append(col_name)
            else:
                raise
    print(f"[{label}] Added {len(added)}: {added}")
    if skipped:
        print(f"[{label}] Already present, skipped: {skipped}")


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    _add_columns(cur, HELOC_COLUMNS, 'BANK013/heloc')
    _add_columns(cur, CREDIT_RISK_COLUMNS, 'BANK014/credit_risk')
    conn.commit()

    total_cols = len(cur.execute("PRAGMA table_info(bank_loan_metrics)").fetchall())
    print(f"\nbank_loan_metrics now has {total_cols} columns total.")
    conn.close()


if __name__ == '__main__':
    main()
