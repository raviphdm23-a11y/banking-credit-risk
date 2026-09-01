"""
rm_case_store.py
────────────────
The Relationship-Management case ledger — the M/H/O + provenance backbone.

Three constructs are kept strictly separate (the keystone correction from the
architecture review):
    M — Machine recommendation   (decision_orchestrator output)
    H — Human judgment            (RM proposals, four-eyes, escalations)
    O — Organisational decision   (the final, governed outcome)

Storage (sqlite, in bank.db):
    rm_cases        — current projection / queue row per case
    rm_case_events  — append-only, hash-chained provenance (every M and H and O)
    rm_outcomes     — post-decision performance, to close the learning loop

Every state change is an event; the case is the fold of its events. Events are
hash-chained (each carries prev_hash + hash) so the audit trail is tamper-evident
and the decision provenance graph can be reconstructed exactly.

This module owns the workflow + Delegation-of-Authority enforcement:
escalation-instead-of-override above thresholds, four-eyes for borderline/large
exposures, and mandatory rationale on any deviation from the machine line.
"""

import json
import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone, date, timedelta

MIN_RATIONALE_CHARS = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS rm_cases (
    case_id TEXT PRIMARY KEY,
    created_at TEXT, updated_at TEXT,
    rm_id TEXT, customer_name TEXT, customer_id TEXT,
    product TEXT, requested_amount REAL, exposure REAL,
    risk_grade TEXT, machine_reco TEXT, confidence_class TEXT,
    required_control TEXT, state TEXT,
    proposed_reco TEXT, proposed_by TEXT, proposed_rationale TEXT,
    final_decision TEXT, final_by TEXT, deviation INTEGER DEFAULT 0,
    machine_json TEXT
);
CREATE TABLE IF NOT EXISTS rm_case_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT, seq INTEGER, ts TEXT,
    actor_id TEXT, actor_role TEXT, event_type TEXT, action TEXT,
    rationale_code TEXT, rationale_text TEXT, payload TEXT,
    prev_hash TEXT, hash TEXT
);
CREATE TABLE IF NOT EXISTS rm_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT, booked INTEGER, performance_status TEXT,
    dpd INTEGER, default_flag INTEGER, observation_date TEXT,
    recorded_at TEXT, notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_rmcase_state ON rm_cases(state);
CREATE INDEX IF NOT EXISTS idx_rmevents_case ON rm_case_events(case_id, seq);
"""

# Terminal / actionable states
OPEN_STATES = ("INTERIM_ASSESSED", "UNDER_RM_REVIEW", "PENDING_APPROVAL",
               "INFO_REQUESTED", "DEFERRED", "ESCALATED")


def init_schema(conn):
    conn.executescript(SCHEMA)
    _migrate_schema(conn)
    conn.commit()


def _migrate_schema(conn):
    """Idempotent ALTER TABLEs for columns added after the original CREATE
    TABLE IF NOT EXISTS shipped (that clause only creates the table once;
    it never adds columns to an already-existing rm_cases table)."""
    for col, ddl in (
        ("bank_id", "TEXT"),
        ("booked_loan_id", "TEXT"),
        ("booked_customer_id", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE rm_cases ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise


# ── event helpers ────────────────────────────────────────────────────────────
def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_event(conn, case_id, event_type, actor_id="system", actor_role="system",
                 action=None, rationale_code=None, rationale_text=None, payload=None):
    row = conn.execute(
        "SELECT seq, hash FROM rm_case_events WHERE case_id=? ORDER BY seq DESC LIMIT 1",
        (case_id,)).fetchone()
    seq = (row[0] + 1) if row else 1
    prev_hash = row[1] if row else "GENESIS"
    ts = _now()
    core = {"case_id": case_id, "seq": seq, "ts": ts, "actor_id": actor_id,
            "actor_role": actor_role, "event_type": event_type, "action": action,
            "rationale_code": rationale_code, "rationale_text": rationale_text,
            "payload": payload}
    h = hashlib.sha256((prev_hash + json.dumps(core, sort_keys=True, default=str)).encode()).hexdigest()
    conn.execute(
        "INSERT INTO rm_case_events (case_id, seq, ts, actor_id, actor_role, event_type, "
        "action, rationale_code, rationale_text, payload, prev_hash, hash) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (case_id, seq, ts, actor_id, actor_role, event_type, action, rationale_code,
         rationale_text, json.dumps(payload, default=str) if payload is not None else None,
         prev_hash, h))
    return h


# ── create ───────────────────────────────────────────────────────────────────
def create_case(conn, M, rm_id="RM-DEMO"):
    app_ = M["application"]
    case_id = "RMC-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
    ts = _now()
    conn.execute(
        "INSERT INTO rm_cases (case_id, created_at, updated_at, rm_id, customer_name, "
        "customer_id, product, requested_amount, exposure, risk_grade, machine_reco, "
        "confidence_class, required_control, state, machine_json, bank_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (case_id, ts, ts, rm_id,
         app_.get("customer_name", "New Applicant"), app_.get("customer_id"),
         app_.get("product", "Personal Loan"),
         float(app_.get("requested_amount") or app_.get("exposure") or 0),
         M["routing"]["exposure_assessed"], M["composed"]["risk_grade"],
         M["composed"]["recommendation"], M["confidence"]["class"],
         M["routing"]["required_control"], "INTERIM_ASSESSED",
         json.dumps(M, default=str), app_.get("bank_id")))
    append_event(conn, case_id, "CASE_CREATED", rm_id, "relationship_manager",
                 payload={"product": app_.get("product"), "customer": app_.get("customer_name")})
    append_event(conn, case_id, "MACHINE_RECOMMENDATION", "decision_engine", "machine",
                 action=M["composed"]["recommendation"],
                 payload={"recommendation": M["composed"], "confidence": M["confidence"],
                          "routing": M["routing"], "policy_decision": M["policy"]["decision"],
                          "model_content_hash": M["model_content_hash"],
                          "content_hash": M["content_hash"]})
    conn.commit()

    # Phase 4 — prediction_store (backend/prediction_store.py): structured,
    # queryable columns for this assessment's outputs, alongside (not
    # replacing) the machine_json blob already stored above.
    try:
        from backend.model_registry import get_active_model_id
        from backend.prediction_store import record_prediction
        # Only look up the bank-scoped registry entry if a bank-specific
        # model actually scored this case (M['model_scope'], set by
        # app.py's _resolve_segment_engine) - not just whatever the RM
        # requested, so a fallback-to-shared case still gets the correct
        # (shared) model_id instead of a bank-specific one that wasn't used.
        lookup_bank_id = app_.get('bank_id') if (M.get('model_scope') or '').startswith('bank_specific') else None
        model_id = get_active_model_id(conn, app_.get('exposure_class'), bank_id=lookup_bank_id)
        record_prediction(conn, M, case_id=case_id, model_id=model_id)
    except Exception as e:
        print(f"[rm_case_store] prediction_store write failed for {case_id} (non-fatal): {e}")

    return case_id


# ── read ─────────────────────────────────────────────────────────────────────
def _case_row(conn, case_id):
    r = conn.execute("SELECT * FROM rm_cases WHERE case_id=?", (case_id,)).fetchone()
    return dict(r) if r else None


def get_case(conn, case_id):
    c = _case_row(conn, case_id)
    if not c:
        return None
    if c.get("machine_json"):
        try:
            c["machine"] = json.loads(c["machine_json"])
        except Exception:
            c["machine"] = None
    c.pop("machine_json", None)
    events = []
    for e in conn.execute("SELECT * FROM rm_case_events WHERE case_id=? ORDER BY seq", (case_id,)).fetchall():
        ev = dict(e)
        if ev.get("payload"):
            try:
                ev["payload"] = json.loads(ev["payload"])
            except Exception:
                pass
        events.append(ev)
    c["provenance"] = events
    o = conn.execute("SELECT * FROM rm_outcomes WHERE case_id=? ORDER BY id DESC LIMIT 1",
                     (case_id,)).fetchone()
    c["outcome"] = dict(o) if o else None
    return c


def list_cases(conn, state=None, control=None):
    q = "SELECT case_id, created_at, updated_at, rm_id, customer_name, product, requested_amount, " \
        "exposure, risk_grade, machine_reco, confidence_class, required_control, state, " \
        "proposed_reco, final_decision, deviation FROM rm_cases"
    clauses, params = [], []
    if state:
        clauses.append("state=?"); params.append(state)
    if control:
        clauses.append("required_control=?"); params.append(control)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(q, params).fetchall()]


# ── workflow / authority ─────────────────────────────────────────────────────
def _update(conn, case_id, **fields):
    fields["updated_at"] = _now()
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE rm_cases SET {sets} WHERE case_id=?",
                 list(fields.values()) + [case_id])


def rm_action(conn, case_id, action, actor_id="RM-DEMO",
              rationale_code=None, rationale_text=None, modified_recommendation=None,
              extra=None):
    """RM acts on the interim assessment. The relationship manager is the final
    authority: there are exactly two actions — **accept** or **reject** — and
    each one immediately finalises the organisational decision (no four-eyes /
    committee / escalation routing). A rejection deviates from the machine line,
    so a rationale is required and recorded on the provenance ledger."""
    c = _case_row(conn, case_id)
    if not c:
        return {"error": "Case not found"}, 404
    M = json.loads(c["machine_json"])
    machine_reco = M["composed"]["recommendation"]
    action = (action or "").lower()

    if action == "accept":
        final = machine_reco
    elif action == "reject":
        final = "DECLINE"
        if not rationale_text or len(rationale_text.strip()) < MIN_RATIONALE_CHARS:
            return {"error": f"A rejection requires a rationale of at least {MIN_RATIONALE_CHARS} characters."}, 400
    else:
        return {"error": f"Unknown action '{action}' — only 'accept' or 'reject' are permitted."}, 400

    deviation = final != machine_reco
    append_event(conn, case_id, "RM_PROPOSAL", actor_id, "relationship_manager",
                 action=action, rationale_code=rationale_code, rationale_text=rationale_text,
                 payload={"proposed": final, "machine_reco": machine_reco,
                          "deviation": deviation})
    return _finalise(conn, case_id, final, actor_id, "relationship_manager",
                     machine_reco, rationale_text, single_control=True)


def four_eyes(conn, case_id, decision, actor_id="CO-DEMO", rationale_text=None):
    """Credit officer / committee approves or returns an RM proposal."""
    c = _case_row(conn, case_id)
    if not c:
        return {"error": "Case not found"}, 404
    if c["state"] not in ("PENDING_APPROVAL", "ESCALATED"):
        return {"error": f"Case is not awaiting approval (state={c['state']})."}, 409
    M = json.loads(c["machine_json"])
    machine_reco = M["composed"]["recommendation"]
    role = "risk_committee" if c["required_control"] == "COMMITTEE" else "credit_officer"
    decision = (decision or "").lower()

    if decision == "return":
        _update(conn, case_id, state="UNDER_RM_REVIEW")
        append_event(conn, case_id, "FOUR_EYES_RETURNED", actor_id, role,
                     action="return", rationale_text=rationale_text)
        conn.commit(); return {"state": "UNDER_RM_REVIEW"}, 200

    if decision == "approve":
        proposed = c["proposed_reco"] or machine_reco
        return _finalise(conn, case_id, proposed, actor_id, role, machine_reco,
                         rationale_text, single_control=False)

    return {"error": "decision must be 'approve' or 'return'"}, 400


def _finalise(conn, case_id, final_decision, actor_id, actor_role, machine_reco,
              rationale_text, single_control):
    deviation = 1 if final_decision != machine_reco else 0
    _update(conn, case_id, state="DECISION_FINAL", final_decision=final_decision,
            final_by=actor_id, deviation=deviation,
            proposed_reco=final_decision)
    append_event(conn, case_id, "DECISION_FINAL", actor_id, actor_role,
                 action=final_decision, rationale_text=rationale_text,
                 payload={"organizational_decision": final_decision,
                          "machine_recommendation": machine_reco,
                          "deviation": bool(deviation),
                          "control": "RM_SINGLE" if single_control else "FOUR_EYES"})
    conn.commit()

    result = {"state": "DECISION_FINAL", "final_decision": final_decision,
              "deviation": bool(deviation)}

    # Only an APPROVE actually books a loan against the originating bank's
    # ledger - see backend/loan_booking.py for why nothing booked loans
    # before this (accept/reject only ever flipped case state).
    if final_decision == "APPROVE":
        from backend.loan_booking import book_loan
        try:
            booking = book_loan(conn, _case_row(conn, case_id))
        except Exception as e:
            booking = None
            # book_loan() writes customers/accounts/loans/credit_risk_metrics/
            # bank_loan_metrics/collateral_register/ALM funding in one
            # transaction, committing only at its very end - if it raises
            # partway through, those inserts are still pending on this shared
            # connection. Without an explicit rollback here, a later unrelated
            # conn.commit() elsewhere in the request would silently persist a
            # half-booked loan (e.g. a loan row with no ALM funding behind it).
            conn.rollback()
            print(f"[rm_case_store] Loan booking failed for {case_id}, rolled back: {e}")
        if booking:
            _update(conn, case_id, booked_loan_id=booking["loan_id"],
                    booked_customer_id=booking["customer_id"])
            append_event(conn, case_id, "LOAN_BOOKED", "system", "system",
                         payload=booking)
            conn.commit()
            result["booking"] = booking

    return result, 200


# ── outcome (learning loop) ──────────────────────────────────────────────────
def record_outcome(conn, case_id, performance_status, booked=True, dpd=0,
                   default_flag=0, observation_date=None, notes=None):
    c = _case_row(conn, case_id)
    if not c:
        return {"error": "Case not found"}, 404
    observation_date = observation_date or date.today().isoformat()
    conn.execute(
        "INSERT INTO rm_outcomes (case_id, booked, performance_status, dpd, default_flag, "
        "observation_date, recorded_at, notes) VALUES (?,?,?,?,?,?,?,?)",
        (case_id, 1 if booked else 0, performance_status, dpd, default_flag,
         observation_date, _now(), notes))
    append_event(conn, case_id, "OUTCOME_RECORDED", "monitoring", "system",
                 action=performance_status,
                 payload={"performance_status": performance_status, "dpd": dpd,
                          "default_flag": default_flag, "observation_date": observation_date})
    conn.commit()
    return {"recorded": True, "performance_status": performance_status}, 200


# ── insights (HITL learning / monitoring aggregates) ─────────────────────────
def insights(conn):
    by_state = {r[0]: r[1] for r in
                conn.execute("SELECT state, COUNT(*) FROM rm_cases GROUP BY state").fetchall()}
    by_control = {r[0]: r[1] for r in
                  conn.execute("SELECT required_control, COUNT(*) FROM rm_cases GROUP BY required_control").fetchall()}
    finals = conn.execute(
        "SELECT machine_reco, final_decision, deviation FROM rm_cases WHERE state='DECISION_FINAL'"
    ).fetchall()
    n_final = len(finals)
    n_dev = sum(1 for f in finals if f[2])
    # override outcome tracking (don't assume overrides are correct)
    joined = conn.execute(
        "SELECT c.deviation, o.default_flag FROM rm_cases c "
        "JOIN rm_outcomes o ON o.case_id=c.case_id WHERE c.state='DECISION_FINAL'"
    ).fetchall()
    ov = [j for j in joined if j[0]]
    ov_default = sum(1 for j in ov if j[1])
    nonov = [j for j in joined if not j[0]]
    nonov_default = sum(1 for j in nonov if j[1])

    return {
        "by_state": by_state,
        "by_control": by_control,
        "decisions_final": n_final,
        "deviations": n_dev,
        "override_rate_pct": round(n_dev / n_final * 100, 1) if n_final else 0.0,
        "agreement_rate_pct": round((n_final - n_dev) / n_final * 100, 1) if n_final else 0.0,
        "outcomes_tracked": len(joined),
        "override_default_rate_pct": round(ov_default / len(ov) * 100, 1) if ov else None,
        "aligned_default_rate_pct": round(nonov_default / len(nonov) * 100, 1) if nonov else None,
        "note": "Override hit-rate compares default rates of human-overridden vs model-aligned "
                "decisions once outcomes mature — overrides are not assumed correct.",
    }
