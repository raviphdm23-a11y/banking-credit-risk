"""
add_taiwan_columns.py
──────────────────────
Schema-only migration: adds the new generic, reusable columns to
bank_loan_metrics needed to onboard a Real Earth bank from
sample datasets/Taiwan_UCI_Credit_Card.csv (or any future bank with the
same revolving-credit data shape - column names are deliberately NOT
Taiwan-prefixed, see naming rationale below).

Does NOT insert any data, does NOT create a `banks`/`countries` row, does
NOT onboard Taiwan itself - that's a separate onboarding script + a
still-open decision on bank identity/scope. This migration only makes the
columns exist, all NULL, on every existing row of every bank.

Naming rationale (agreed before writing this):
  - repay_status_m1..m6 / bill_amt_m1..m6 / payment_amt_m1..m6: generic,
    reusable names for a "6 months of billing/repayment history" shape -
    NOT Taiwan-specific, so a future card-issuer bank with the same data
    shape reuses these columns instead of spawning near-duplicates.
    m1 = most recent month, m6 = 6 months back (re-numbered cleanly out of
    the source CSV's own quirky PAY_0/PAY_2..PAY_6 naming - there is no
    "PAY_1" in the original UCI dataset, a known quirk of that file).
  - credit_limit: genuine borrower attribute (their credit line size),
    not the same concept as `exposure` (a live assessment-time input, not
    a training feature) - kept distinct on purpose.
  - marital_status_enc, gender_enc: brought in per "don't lose information
    upfront", but see compliance note below - gender in particular must
    NOT be added to ml_models/trainer.py's FEATURE_COLS without an
    explicit fair-lending compliance review. This migration only creates
    the column; it does not wire it into training.
  - credit_utilization_ratio, payment_coverage_ratio: derived fields
    (bill/limit and payment/bill ratios) - real, non-fabricated ratios
    computed from the raw monthly columns above at onboarding time.

Idempotent - safe to re-run; "duplicate column" errors are swallowed.

Run:
    python operations/scripts/add_taiwan_columns.py
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

NEW_COLUMNS = [
    # Genuine borrower attribute - NOT the same concept as `exposure`
    ('credit_limit', 'REAL'),

    # 6 months of repayment status, most-recent-first (re-numbered from the
    # source's PAY_0/PAY_2..PAY_6 quirk into a clean m1..m6 sequence)
    ('repay_status_m1', 'INTEGER'),
    ('repay_status_m2', 'INTEGER'),
    ('repay_status_m3', 'INTEGER'),
    ('repay_status_m4', 'INTEGER'),
    ('repay_status_m5', 'INTEGER'),
    ('repay_status_m6', 'INTEGER'),

    # 6 months of billing amounts
    ('bill_amt_m1', 'REAL'),
    ('bill_amt_m2', 'REAL'),
    ('bill_amt_m3', 'REAL'),
    ('bill_amt_m4', 'REAL'),
    ('bill_amt_m5', 'REAL'),
    ('bill_amt_m6', 'REAL'),

    # 6 months of actual payment amounts
    ('payment_amt_m1', 'REAL'),
    ('payment_amt_m2', 'REAL'),
    ('payment_amt_m3', 'REAL'),
    ('payment_amt_m4', 'REAL'),
    ('payment_amt_m5', 'REAL'),
    ('payment_amt_m6', 'REAL'),

    # Flagged fields - see compliance note in the module docstring. Column
    # exists so the raw source value isn't lost; NOT added to FEATURE_COLS
    # by this migration.
    ('marital_status_enc', 'INTEGER'),
    ('gender_enc', 'INTEGER'),

    # Derived fields (computed from the raw monthly columns above at
    # onboarding time - real ratios, not fabricated)
    ('credit_utilization_ratio', 'REAL'),
    ('payment_coverage_ratio', 'REAL'),
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
    print("All new columns are NULL on every existing row (no data touched) - "
          "verified schema-only change.")

    conn.close()


if __name__ == '__main__':
    main()
