"""
collateral_store.py
────────────────────
Phase 2 of the data-layer restructuring: collateral as a first-class L0
source interface.

Before this module existed there was no dedicated collateral table
anywhere in bank.db. Collateral type/value were captured on
borrower-info.html and flowed into the live assess-borrower-with-shap
call (backend/assessment_engine.py) purely as in-memory `inputs` dict
keys — real for the moment of assessment, then silently discarded at
booking time (backend/loan_booking.py never wrote them anywhere; `grep
collateral` returns zero matches there). Only `loans.ltv_ratio` survived
past booking, and only for RETAIL_MORTGAGES.

`collateral_register` is the durable L0 record: one row per loan with
collateral pledged, keyed by loan_id, self-creating (same pattern as
alm_engine.py's `alm_funding_events`). The haircut table is imported from
AIRBCalculations.COLLATERAL_HAIRCUTS (backend/calculations.py) rather than
redefined here, so LGD calc and this store can never independently drift
on what a given collateral_type's haircut is — the exact class of bug
Phase 1 fixed for training features.

Run standalone backfill: python operations/scripts/backfill_collateral_register.py
"""

from backend.calculations import AIRBCalculations

SCHEMA = """
CREATE TABLE IF NOT EXISTS collateral_register (
    collateral_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id         TEXT NOT NULL,
    bank_id         TEXT NOT NULL,
    collateral_type TEXT NOT NULL,
    collateral_value REAL NOT NULL,
    haircut_pct     REAL,             -- NULL for immovable property (Real Estate) —
                                       -- that risk is captured via loans.ltv_ratio's
                                       -- LTV-banded risk weight, not a haircut/coverage
                                       -- ratio; haircut_pct only applies to the 5
                                       -- financial-collateral types below.
    effective_value REAL NOT NULL,    -- collateral_value * (1 - haircut_pct), or
                                       -- collateral_value unchanged when haircut_pct IS NULL
    ltv_ratio       REAL,             -- mortgages only; mirrors loans.ltv_ratio at
                                       -- capture time for audit purposes
    valuation_date  TEXT NOT NULL,
    source          TEXT NOT NULL,    -- 'origination' | 'backfill_seed'
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _ensure_schema(conn):
    conn.execute(SCHEMA)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collateral_loan ON collateral_register(loan_id)")


def record_collateral(conn, loan_id, bank_id, collateral_type, collateral_value,
                       valuation_date, ltv_ratio=None, source='origination'):
    """Insert one collateral_register row for a loan. No-op (returns None) if
    collateral_type/collateral_value are falsy — an unsecured loan has no
    collateral row, which is the correct representation (not a zero-value row).
    """
    if not collateral_type or not collateral_value or collateral_value <= 0:
        return None
    _ensure_schema(conn)

    if collateral_type == 'Real Estate':
        haircut_pct = None
        effective_value = float(collateral_value)
    else:
        haircut_pct = AIRBCalculations.COLLATERAL_HAIRCUTS.get(
            collateral_type, AIRBCalculations.DEFAULT_HAIRCUT)
        effective_value = float(collateral_value) * (1 - haircut_pct)

    cur = conn.execute(
        """INSERT INTO collateral_register
           (loan_id, bank_id, collateral_type, collateral_value, haircut_pct,
            effective_value, ltv_ratio, valuation_date, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (loan_id, bank_id, collateral_type, float(collateral_value), haircut_pct,
         effective_value, ltv_ratio, valuation_date, source)
    )
    return cur.lastrowid


def get_collateral(conn, loan_id):
    """Return the most recent collateral_register row for a loan as a dict,
    or None if the loan is unsecured / has no recorded collateral.
    """
    _ensure_schema(conn)
    cur = conn.execute(
        """SELECT collateral_id, loan_id, bank_id, collateral_type, collateral_value,
                  haircut_pct, effective_value, ltv_ratio, valuation_date, source
           FROM collateral_register WHERE loan_id = ?
           ORDER BY collateral_id DESC LIMIT 1""",
        (loan_id,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    cols = ['collateral_id', 'loan_id', 'bank_id', 'collateral_type', 'collateral_value',
            'haircut_pct', 'effective_value', 'ltv_ratio', 'valuation_date', 'source']
    return dict(zip(cols, row))
