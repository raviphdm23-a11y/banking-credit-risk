"""
backfill_collateral_register.py
─────────────────────────────────
Phase 2 backfill: creates `collateral_register` rows (see
backend/collateral_store.py) for loans booked BEFORE that table existed.

Only RETAIL_MORTGAGES loans carry any collateral signal today
(loans.ltv_ratio, fabricated at seed time by seed_real_bank.py) - every
other exposure class was originated with no durable collateral record at
all (see this session's investigation: collateral_type/collateral_value
were captured on borrower-info.html but discarded before reaching
book_loan(), same pattern as the AIRB/SA methodology flag). Nothing can be
backfilled for those; only new bookings through the now-fixed
book_loan() will have real collateral rows.

collateral_value is back-derived from the loan's own principal and
ltv_ratio (collateral_value = principal / ltv_ratio) - an approximation
consistent with how ltv_ratio itself was originally fabricated as a
random draw at seed time (operations/scripts/seed_real_bank.py:504),
not an independently observed valuation.

Idempotent — skips loans that already have a collateral_register row.

Run: python operations/scripts/backfill_collateral_register.py
"""

import os
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from backend.collateral_store import record_collateral, get_collateral

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')


def run(db_path=DB):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, bank_id, principal, ltv_ratio, disbursed FROM loans "
        "WHERE exposure_class='RETAIL_MORTGAGES' AND ltv_ratio IS NOT NULL AND ltv_ratio > 0"
    )
    rows = cur.fetchall()
    print(f"[1] {len(rows)} RETAIL_MORTGAGES loans with an ltv_ratio to backfill from.")

    inserted, skipped = 0, 0
    for loan_id, bank_id, principal, ltv_ratio, disbursed in rows:
        if get_collateral(conn, loan_id) is not None:
            skipped += 1
            continue
        collateral_value = round(float(principal) / float(ltv_ratio), 2)
        record_collateral(
            conn, loan_id, bank_id,
            collateral_type='Real Estate',
            collateral_value=collateral_value,
            valuation_date=disbursed or date.today().isoformat(),
            ltv_ratio=ltv_ratio,
            source='backfill_seed',
        )
        inserted += 1

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM collateral_register")
    total = cur.fetchone()[0]
    conn.close()

    print(f"[2] Inserted {inserted} collateral_register rows, skipped {skipped} (already present).")
    print(f"[3] collateral_register now has {total} rows total.")


if __name__ == "__main__":
    run()
