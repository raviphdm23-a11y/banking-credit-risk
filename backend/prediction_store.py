"""
prediction_store.py
─────────────────────
Phase 4 of the data-layer restructuring: L3 calculation-layer record of
one assessment's outputs, as structured/queryable columns instead of only
existing inside `rm_cases.machine_json` (a JSON blob you can't SELECT
against - e.g. "how many AIRB-methodology assessments ran last month" or
"what was the PD trend for this customer across re-assessments" both
require parsing every row's JSON today).

One row per assessment (backend/decision_orchestrator.py's `M`), written
by rm_case_store.create_case() at the same time as the rm_cases row.
`loan_id` starts NULL and is back-filled once/if the case is actually
booked (backend/loan_booking.py) - most assessments never become a loan,
so this correctly distinguishes "assessed" from "booked" instead of
conflating them.
"""

import json
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS prediction_store (
    prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id       TEXT UNIQUE NOT NULL,
    case_id         TEXT,
    loan_id         TEXT,                 -- NULL until/unless booked
    bank_id         TEXT,
    customer_id     TEXT,
    customer_name   TEXT,
    exposure_class  TEXT,
    model_id        TEXT,                 -- FK -> model_registry.model_id (nullable: pre-Phase-4 model versions)
    model_version    TEXT,
    calculation_methodology TEXT,         -- AIRB | STANDARDIZED | BOTH, from the application
    pd_point        REAL,
    pd_low          REAL,
    pd_high         REAL,
    rating_grade    TEXT,
    lgd             REAL,
    ead             REAL,
    rwa             REAL,
    risk_weight     REAL,
    expected_loss   REAL,
    capital_charge  REAL,
    recommendation  TEXT,
    macro_regime_score REAL,
    content_hash    TEXT,
    as_of_date      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prediction_loan ON prediction_store(loan_id);
CREATE INDEX IF NOT EXISTS idx_prediction_case ON prediction_store(case_id);
CREATE INDEX IF NOT EXISTS idx_prediction_customer ON prediction_store(customer_id);
"""


def _ensure_schema(conn):
    conn.executescript(SCHEMA)


def record_prediction(conn, M, case_id=None, model_id=None):
    """Insert one prediction_store row from a decision_orchestrator `M` dict.
    No-op (returns None) if a row for this report_id already exists
    (idempotent — a case create is not expected to be replayed, but this
    guards against it rather than raising a UNIQUE-constraint error).
    """
    _ensure_schema(conn)
    app_ = M.get('application', {})
    report_id = M.get('report_id')
    if not report_id:
        return None
    existing = conn.execute(
        "SELECT prediction_id FROM prediction_store WHERE report_id=?", (report_id,)
    ).fetchone()
    if existing:
        return existing[0]

    pd_block = M.get('pd', {})
    rwa_block = M.get('rwa', {})
    lgd_block = M.get('lgd', {})
    el_block = M.get('el', {})
    methodology = (app_.get('calculation_methodology') or 'standardized').upper()
    # Basel capital-charge (CAR minimum x RWA) isn't a field decision_orchestrator's
    # M carries today - approximated here rather than left silently at 0, using
    # the same RBI CAR minimum backend/regulatory_engine.py uses elsewhere.
    rwa_amount = rwa_block.get('rwa')
    capital_charge = round(rwa_amount * 0.115, 2) if rwa_amount is not None else None

    created_at = M.get('created_at') or ''
    as_of_date = created_at[:10] if len(created_at) >= 10 else date.today().isoformat()

    cur = conn.execute(
        """INSERT INTO prediction_store
           (report_id, case_id, bank_id, customer_id, customer_name, exposure_class,
            model_id, model_version, calculation_methodology,
            pd_point, pd_low, pd_high, rating_grade, lgd, ead, rwa, risk_weight,
            expected_loss, capital_charge, recommendation, macro_regime_score,
            content_hash, as_of_date)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (report_id, case_id, app_.get('bank_id'), app_.get('customer_id'),
         app_.get('customer_name'), app_.get('exposure_class'),
         model_id, M.get('model_version'), methodology,
         pd_block.get('point'), pd_block.get('low'), pd_block.get('high'),
         (M.get('rating') or {}).get('grade'),
         lgd_block.get('lgd'), M.get('ead'), rwa_amount, rwa_block.get('risk_weight'),
         (el_block or {}).get('amount_inr'), capital_charge,
         (M.get('composed') or {}).get('recommendation'),
         (M.get('macro_regime') or {}).get('score'),
         M.get('content_hash'), as_of_date)
    )
    conn.commit()
    return cur.lastrowid


def link_to_loan(conn, report_id, loan_id):
    """Called by loan_booking.book_loan() once a case is actually booked."""
    _ensure_schema(conn)
    conn.execute(
        "UPDATE prediction_store SET loan_id=? WHERE report_id=?", (loan_id, report_id)
    )


def get_prediction(conn, report_id):
    _ensure_schema(conn)
    row = conn.execute(
        "SELECT * FROM prediction_store WHERE report_id=?", (report_id,)
    ).fetchone()
    if row is None:
        return None
    cols = [d[0] for d in conn.execute("SELECT * FROM prediction_store LIMIT 0").description]
    return dict(zip(cols, row))
