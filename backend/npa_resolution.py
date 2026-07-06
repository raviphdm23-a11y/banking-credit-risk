"""
npa_resolution.py
─────────────────
Actions a credit officer can take on an already-NPA-classified loan: recovery
(partial/full cash recovery), restructure, write-off. Unlike the existing
DPD-batch / classify-override (app.py's _run_npa_batch / ops_loan_classify,
which only ever change loan_classification), these actually move
outstanding/balance-sheet figures - the reverse-direction sibling of
backend/loan_booking.py's "make it real" pattern.

Provisions/GNPA%/PCR are computed LIVE from loans.outstanding +
loan_classification every regulatory batch run (backend/regulatory_engine.py) -
so these actions only need to correctly update loans/credit_risk_metrics/
bank_balance_sheet.advances_net; nothing here touches reg_capital_reports
directly, and nothing here touches bank_loan_metrics.default_flag - that's
the frozen training-label snapshot the segmented PD models were trained on,
and a cured/recovered loan doesn't retroactively "undefault" for modeling
purposes.

Note: app.py's _run_npa_batch/ops_loan_classify reference loans.days_past_due/
last_payment_date/override_default/override_reason/override_by/override_at,
but no migration in this repo ever added those columns to loans (confirmed
against the live bank.db) - added idempotently here since recovery/restructure
also need days_past_due/last_payment_date, which as a side effect fixes those
two previously-broken endpoints too.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_RATIONALE_CHARS = 20
VALID_ACTIONS = ('recovery', 'restructure', 'write_off')

SCHEMA = """
CREATE TABLE IF NOT EXISTS npa_resolution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id TEXT, bank_id TEXT, seq INTEGER, ts TEXT,
    action TEXT, amount REAL,
    prev_classification TEXT, new_classification TEXT,
    prev_outstanding REAL, new_outstanding REAL,
    actor_id TEXT, rationale TEXT,
    prev_hash TEXT, hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_npares_loan ON npa_resolution_events(loan_id, seq);
"""

_MIGRATIONS = [
    "ALTER TABLE loans ADD COLUMN days_past_due INTEGER DEFAULT 0",
    "ALTER TABLE loans ADD COLUMN last_payment_date TEXT",
    "ALTER TABLE loans ADD COLUMN override_default INTEGER DEFAULT 0",
    "ALTER TABLE loans ADD COLUMN override_reason TEXT",
    "ALTER TABLE loans ADD COLUMN override_by TEXT",
    "ALTER TABLE loans ADD COLUMN override_at TEXT",
]


def _load_sim_clock():
    """Same convention as backend/loan_booking.py - duplicated locally to
    avoid a backend-module -> app.py circular import."""
    try:
        with open(os.path.join(_ROOT, 'simulation_clock.json')) as f:
            clk = json.load(f)
        return clk['sim_date'], clk.get('sim_period', 'FY2020')
    except Exception:
        return '2020-03-31', 'FY2020'


def _ensure_schema(conn):
    conn.executescript(SCHEMA)
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists


def _append_event(conn, loan_id, bank_id, action, amount, prev_class, new_class,
                   prev_outstanding, new_outstanding, actor_id, rationale):
    row = conn.execute(
        "SELECT seq, hash FROM npa_resolution_events WHERE loan_id=? ORDER BY seq DESC LIMIT 1",
        (loan_id,)).fetchone()
    seq = (row[0] + 1) if row else 1
    prev_hash = row[1] if row else "GENESIS"
    ts = datetime.now().isoformat(timespec='seconds')
    core = {"loan_id": loan_id, "seq": seq, "ts": ts, "action": action, "amount": amount,
            "prev_classification": prev_class, "new_classification": new_class,
            "prev_outstanding": prev_outstanding, "new_outstanding": new_outstanding,
            "actor_id": actor_id, "rationale": rationale}
    h = hashlib.sha256((prev_hash + json.dumps(core, sort_keys=True, default=str)).encode()).hexdigest()
    conn.execute(
        "INSERT INTO npa_resolution_events (loan_id, bank_id, seq, ts, action, amount, "
        "prev_classification, new_classification, prev_outstanding, new_outstanding, "
        "actor_id, rationale, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (loan_id, bank_id, seq, ts, action, amount, prev_class, new_class,
         prev_outstanding, new_outstanding, actor_id, rationale, prev_hash, h))
    return h


def resolve_npa(conn, loan_id, action, amount=None, actor_id='OPS-DEMO', rationale=None):
    """Apply a recovery/restructure/write_off action to a loan.

    Returns a result dict on success, or None if the loan doesn't exist
    (caller maps that to 404). Raises ValueError on invalid input (caller
    maps that to 400).
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {VALID_ACTIONS}")
    if not rationale or len(rationale.strip()) < MIN_RATIONALE_CHARS:
        raise ValueError(f"rationale must be at least {MIN_RATIONALE_CHARS} characters")

    _ensure_schema(conn)
    sim_date, sim_period = _load_sim_clock()

    loan = conn.execute(
        "SELECT id, bank_id, outstanding, loan_classification, status FROM loans WHERE id=?",
        (loan_id,)).fetchone()
    if not loan:
        return None
    lid, bank_id, outstanding, prev_class, prev_status = loan
    outstanding = float(outstanding or 0)

    if action == 'recovery':
        if amount is None:
            raise ValueError("amount is required for recovery")
        amount = float(amount)
        if amount <= 0 or amount > outstanding:
            raise ValueError(f"amount must be > 0 and <= current outstanding ({outstanding:.2f})")
        new_outstanding = round(outstanding - amount, 2)
        if new_outstanding <= 0.01:
            new_outstanding = 0.0
            new_class, new_status, npa_flag = 'Standard', 'Closed', 0
        else:
            new_class, new_status = prev_class, prev_status
            npa_flag = 0 if prev_class == 'Standard' else 1
        conn.execute(
            "UPDATE loans SET outstanding=?, status=?, loan_classification=?, "
            "days_past_due=0, last_payment_date=? WHERE id=?",
            (new_outstanding, new_status, new_class, sim_date, lid))
        delta = -amount

    elif action == 'restructure':
        amount = None
        new_outstanding = outstanding
        new_class, new_status, npa_flag = 'Standard', 'Active', 0
        conn.execute(
            "UPDATE loans SET status='Active', loan_classification='Standard', "
            "days_past_due=0, last_payment_date=?, override_default=0 WHERE id=?",
            (sim_date, lid))
        delta = 0.0

    else:  # write_off
        amount = outstanding
        new_outstanding = 0.0
        new_class, new_status, npa_flag = 'Written-Off', 'Written-Off', 1
        conn.execute(
            "UPDATE loans SET outstanding=0, status='Written-Off', "
            "loan_classification='Written-Off' WHERE id=?", (lid,))
        delta = -outstanding

    conn.execute("UPDATE credit_risk_metrics SET npa_flag=? WHERE lid=?", (npa_flag, lid))

    if delta != 0.0:
        conn.execute(
            "UPDATE bank_balance_sheet SET advances_net = advances_net + ? "
            "WHERE bank_id=? AND period=?", (delta, bank_id, sim_period))

    event_hash = _append_event(conn, lid, bank_id, action, amount, prev_class, new_class,
                               outstanding, new_outstanding, actor_id, rationale.strip())
    conn.commit()

    return {
        'loan_id': lid, 'bank_id': bank_id, 'action': action,
        'previous_classification': prev_class, 'new_classification': new_class,
        'new_status': new_status,
        'previous_outstanding': outstanding, 'new_outstanding': new_outstanding,
        'balance_sheet_delta': delta, 'event_hash': event_hash,
    }


def resolution_history(conn, loan_id):
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT seq, ts, action, amount, prev_classification, new_classification, "
        "prev_outstanding, new_outstanding, actor_id, rationale, hash "
        "FROM npa_resolution_events WHERE loan_id=? ORDER BY seq", (loan_id,)).fetchall()
    cols = ['seq', 'ts', 'action', 'amount', 'prev_classification', 'new_classification',
            'prev_outstanding', 'new_outstanding', 'actor_id', 'rationale', 'hash']
    return [dict(zip(cols, r)) for r in rows]
