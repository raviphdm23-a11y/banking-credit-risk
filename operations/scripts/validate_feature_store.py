"""
validate_feature_store.py
──────────────────────────
Phase 1 data-layer health check: confirms every canonical model feature
column (backend/feature_schema.py) is actually populated in
bank_loan_metrics — the informal "feature store" both trainer.py and
sync_bank_loan_metrics.py depend on.

This is the check that would have caught the macro_regime_score bug the
day it happened (15,349/15,349 rows NULL across 5 columns) instead of
months later via a support ticket. Run it after every
sync_bank_loan_metrics.py run and before every retrain.

Exit code 0 = clean. Exit code 1 = at least one canonical column has NULLs
(reported per-column, with counts) — investigate before training on it.

Run: python operations/scripts/validate_feature_store.py
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from backend.feature_schema import FEATURE_COLS, null_report

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')


def run(db_path=DB, table='bank_loan_metrics'):
    conn = sqlite3.connect(db_path)
    report = null_report(conn, table=table, columns=FEATURE_COLS)
    conn.close()

    total = next(iter(report.values()))[1] if report else 0
    print("=" * 70)
    print(f"feature_store validation — {table} ({total} rows)")
    print("=" * 70)

    bad = []
    for col in FEATURE_COLS:
        n, t = report[col]
        if n is None:
            print(f"  MISSING  {col:<28} - column does not exist in {table}")
            bad.append(col)
        elif n > 0:
            pct = 100.0 * n / t if t else 0.0
            flag = "FULL-NULL" if n == t else "PARTIAL  "
            print(f"  {flag}  {col:<28} - {n}/{t} NULL ({pct:.1f}%)")
            bad.append(col)
        else:
            print(f"  OK       {col:<28} - 0 NULL")

    print("=" * 70)
    if bad:
        print(f"FAIL: {len(bad)}/{len(FEATURE_COLS)} canonical feature columns have NULLs or are missing.")
        print("Any model trained on this table will see zero variance in these columns")
        print("(exactly 0.000000 feature_importances_) with no other warning.")
        return 1
    print(f"PASS: all {len(FEATURE_COLS)} canonical feature columns fully populated.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
