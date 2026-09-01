"""
add_hmeq_and_th02_columns.py
───────────────────────────────
Schema-only migration for BANK015 (hmeq.csv) and BANK016 (TH02.csv).
Generic, reusable names - mortgage_balance and home_value are shared
concepts between both banks (a mortgage/home-equity applicant's existing
mortgage balance and property value), defined once and used by both, not
duplicated per bank.

Does NOT insert any data. Idempotent - safe to re-run.

Run:
    python operations/scripts/add_hmeq_and_th02_columns.py
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

NEW_COLUMNS = [
    # Shared between BANK015 (hmeq) and BANK016 (TH02)
    ('mortgage_balance', 'REAL'),
    ('home_value', 'REAL'),

    # BANK015 (hmeq) only
    ('num_derogatory_reports', 'REAL'),
    ('num_delinquent_lines', 'REAL'),
    ('oldest_credit_line_age_months', 'REAL'),
    ('num_recent_inquiries', 'REAL'),
    ('num_credit_lines', 'REAL'),

    # BANK016 (TH02) only
    ('year_of_birth_2digit', 'INTEGER'),
    ('num_additional_dependents', 'INTEGER'),
    ('spouse_income', 'REAL'),
    ('outstanding_debt_mortgage_related', 'REAL'),
    ('outstanding_debt_other_loan', 'REAL'),
    ('outstanding_debt_hire_purchase', 'REAL'),
    ('outstanding_debt_credit_card', 'REAL'),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    added, skipped = [], []
    for col_name, col_type in NEW_COLUMNS:
        try:
            cur.execute(f"ALTER TABLE bank_loan_metrics ADD COLUMN {col_name} {col_type}")
            added.append(col_name)
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                skipped.append(col_name)
            else:
                raise
    conn.commit()
    print(f"Added {len(added)}: {added}")
    if skipped:
        print(f"Already present, skipped: {skipped}")
    total_cols = len(cur.execute("PRAGMA table_info(bank_loan_metrics)").fetchall())
    print(f"\nbank_loan_metrics now has {total_cols} columns total.")
    conn.close()


if __name__ == '__main__':
    main()
