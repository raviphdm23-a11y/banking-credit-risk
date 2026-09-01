"""
add_german_columns.py
───────────────────────
Schema-only migration: adds new generic, reusable columns to
bank_loan_metrics needed to onboard a Real Earth bank from
sample datasets/german_credit_record.csv (the Statlog German Credit
dataset). Same naming philosophy as add_taiwan_columns.py - generic names,
not Germany-prefixed, so a future installment-loan-shaped bank reuses these
columns instead of spawning near-duplicates.

gender_enc and marital_status_enc are NOT added here - they already exist
(added by add_taiwan_columns.py) and are reused directly for this bank's
personal_status_sex field.

Does NOT insert any data. Idempotent - safe to re-run.

Run:
    python operations/scripts/add_german_columns.py
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

NEW_COLUMNS = [
    ('checking_account_status_enc', 'INTEGER'),
    ('credit_history_enc', 'INTEGER'),
    ('requested_loan_amount', 'REAL'),         # distinct concept from credit_limit (revolving line) - a specific installment loan amount
    ('savings_status_enc', 'INTEGER'),
    ('installment_rate_band', 'INTEGER'),      # ordinal 1-4 band, not a literal percentage
    ('other_debtors_enc', 'INTEGER'),
    ('property_type_enc', 'INTEGER'),
    ('other_installment_plans_enc', 'INTEGER'),
    ('has_registered_phone', 'INTEGER'),
    ('loan_duration_months', 'REAL'),
    ('foreign_worker_flag', 'INTEGER'),        # COMPLIANCE FLAG - see mapping file + trainer.py COMPLIANCE_EXCLUDED_COLS
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
    print(f"Added {len(added)} new column(s): {added}")
    if skipped:
        print(f"Already present, skipped: {skipped}")

    total_cols = len(cur.execute("PRAGMA table_info(bank_loan_metrics)").fetchall())
    print(f"\nbank_loan_metrics now has {total_cols} columns total.")
    conn.close()


if __name__ == '__main__':
    main()
