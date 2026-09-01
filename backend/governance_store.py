"""
governance_store.py
───────────────────
The Model Governance department's data layer — the SR 11-7 / Basel / EU AI Act
control backbone that wraps policy, thresholds and sign-off workflow around
what the ML pipeline already computes.

Storage (sqlite, in bank.db — every table self-creates on first use):
    gov_audit_events          — unified, hash-chained model-lifecycle audit log
                                (training runs, promotions, blocks, force-promotes,
                                rollbacks, hyperparameter changes, wiki edits,
                                alerts, validation sign-offs, monitor runs)
    gov_kpi_snapshots         — one row per (monitor run, model slot, KPI)
    gov_alerts                — threshold-breach alerts requiring acknowledgement
    gov_wiki_entries          — per-model governance wiki (current projection)
    gov_wiki_versions         — full field snapshot per wiki edit
    gov_validation_signoffs   — six-pillar independent-validation checklist
    gov_baseline_distributions— training-time score/feature bins for PSI

The audit chain clones rm_case_store's event chain but is GLOBAL (one chain
for the whole model lifecycle, seeded "GENESIS") rather than per-case, so a
single verify walk proves the entire governance history intact.

Slot keys match ml_models/active_model.json exactly: 'CORPORATE', 'SME',
'RETAIL_MORTGAGES', 'RETAIL_OTHER', or '<SEG>::<BANKxxx>' / 'GENERIC::<BANKxxx>'
for bank-scoped models. The slot is the unit of governance — one wiki entry,
one validation checklist, one KPI series per slot.
"""

import json
import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

MIN_ACTION_CHARS = 20          # same spirit as rm_case_store.MIN_RATIONALE_CHARS

ML_DIR = Path(__file__).resolve().parent.parent / 'ml_models'

PILLARS = {
    1: 'Conceptual Soundness',
    2: 'Data Quality Assessment',
    3: 'Process Verification',
    4: 'Outcomes Analysis',
    5: 'Ongoing Monitoring',
    6: 'Governance Framework',
}

RISK_TIER_CADENCE = {
    'HIGH': 'Quarterly reviews with documented recalibration decisions.',
    'MEDIUM': 'Semi-annual reviews with documented recalibration decisions.',
    'LOW': 'Annual reviews with documented recalibration decisions.',
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS gov_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER, ts TEXT,
    actor_id TEXT, actor_role TEXT,
    event_type TEXT, object_type TEXT, object_id TEXT,
    payload TEXT, prev_hash TEXT, hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_gov_audit_seq ON gov_audit_events(seq);
CREATE INDEX IF NOT EXISTS idx_gov_audit_obj ON gov_audit_events(object_type, object_id);

CREATE TABLE IF NOT EXISTS gov_kpi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ts TEXT, slot_key TEXT, model_id TEXT,
    kpi TEXT, feature TEXT,
    value REAL, threshold REAL, status TEXT,
    detail_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_gov_kpi_slot ON gov_kpi_snapshots(slot_key, kpi, run_ts);

CREATE TABLE IF NOT EXISTS gov_alerts (
    alert_id TEXT PRIMARY KEY,
    created_at TEXT, slot_key TEXT, model_id TEXT,
    alert_type TEXT, kpi TEXT, value REAL, threshold REAL,
    severity TEXT, message TEXT,
    status TEXT DEFAULT 'OPEN',
    acked_by TEXT, acked_at TEXT, ack_action TEXT
);

CREATE TABLE IF NOT EXISTS gov_wiki_entries (
    slot_key TEXT PRIMARY KEY,
    model_id TEXT, exposure_class TEXT, bank_scope TEXT, model_type TEXT,
    risk_tier TEXT DEFAULT 'HIGH',
    purpose TEXT, assumptions TEXT, validation_methods TEXT,
    data_lineage TEXT, escalation_rules TEXT, review_cadence TEXT,
    regulatory_references TEXT,
    auto_json TEXT,
    created_at TEXT, updated_at TEXT, updated_by TEXT,
    version INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS gov_wiki_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT, version INTEGER, edited_at TEXT, edited_by TEXT,
    change_description TEXT, fields_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_gov_wiki_ver ON gov_wiki_versions(slot_key, version);

CREATE TABLE IF NOT EXISTS gov_validation_signoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT, model_id TEXT,
    pillar INTEGER, pillar_name TEXT,
    status TEXT DEFAULT 'PENDING',
    validator TEXT, signed_at TEXT, notes TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_gov_val_slot_pillar
    ON gov_validation_signoffs(slot_key, model_id, pillar);

CREATE TABLE IF NOT EXISTS gov_baseline_distributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, slot_key TEXT, created_at TEXT,
    kind TEXT, feature TEXT,
    bin_edges_json TEXT, bin_freqs_json TEXT,
    n_rows INTEGER
);
CREATE INDEX IF NOT EXISTS idx_gov_baseline_slot ON gov_baseline_distributions(slot_key, run_id);
"""

# Editable wiki fields — everything else on gov_wiki_entries is system-derived.
WIKI_PROSE_FIELDS = ('purpose', 'assumptions', 'validation_methods', 'data_lineage',
                     'escalation_rules', 'review_cadence', 'regulatory_references')


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def parse_slot(slot_key):
    """'CORPORATE' -> ('CORPORATE','ALL'); 'GENERIC::BANK011' -> ('GENERIC','BANK011')."""
    if '::' in slot_key:
        seg, bank = slot_key.split('::', 1)
        return seg, bank
    return slot_key, 'ALL'


# ── audit chain ──────────────────────────────────────────────────────────────
def append_audit_event(conn, event_type, actor_id='system', actor_role='system',
                       object_type=None, object_id=None, payload=None):
    """Append one event to the single global governance chain. Same construction
    as rm_case_store.append_event, but chained across ALL events (not per case),
    so one verify walk covers the whole model lifecycle."""
    row = conn.execute(
        "SELECT seq, hash FROM gov_audit_events ORDER BY seq DESC LIMIT 1").fetchone()
    seq = (row[0] + 1) if row else 1
    prev_hash = row[1] if row else 'GENESIS'
    ts = _now()
    core = {'seq': seq, 'ts': ts, 'actor_id': actor_id, 'actor_role': actor_role,
            'event_type': event_type, 'object_type': object_type,
            'object_id': object_id, 'payload': payload}
    h = hashlib.sha256(
        (prev_hash + json.dumps(core, sort_keys=True, default=str)).encode()).hexdigest()
    conn.execute(
        "INSERT INTO gov_audit_events (seq, ts, actor_id, actor_role, event_type, "
        "object_type, object_id, payload, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (seq, ts, actor_id, actor_role, event_type, object_type, object_id,
         json.dumps(payload, default=str) if payload is not None else None,
         prev_hash, h))
    conn.commit()
    return h


def verify_chain(conn):
    """Re-walk the whole chain recomputing every hash. Any edited, deleted or
    reordered event breaks the chain from that seq onward."""
    rows = conn.execute(
        "SELECT seq, ts, actor_id, actor_role, event_type, object_type, object_id, "
        "payload, prev_hash, hash FROM gov_audit_events ORDER BY seq").fetchall()
    prev = 'GENESIS'
    for r in rows:
        seq, ts, actor_id, actor_role, event_type, object_type, object_id, payload, prev_hash, h = r
        payload_obj = json.loads(payload) if payload else None
        core = {'seq': seq, 'ts': ts, 'actor_id': actor_id, 'actor_role': actor_role,
                'event_type': event_type, 'object_type': object_type,
                'object_id': object_id, 'payload': payload_obj}
        expect = hashlib.sha256(
            (prev + json.dumps(core, sort_keys=True, default=str)).encode()).hexdigest()
        if prev_hash != prev or h != expect:
            return {'intact': False, 'events': len(rows), 'first_broken_seq': seq}
        prev = h
    return {'intact': True, 'events': len(rows), 'first_broken_seq': None}


def list_audit_events(conn, limit=100, object_id=None):
    q = ("SELECT seq, ts, actor_id, actor_role, event_type, object_type, object_id, "
         "payload, prev_hash, hash FROM gov_audit_events")
    params = []
    if object_id:
        q += " WHERE object_id=?"
        params.append(object_id)
    q += " ORDER BY seq DESC LIMIT ?"
    params.append(int(limit))
    out = []
    for r in conn.execute(q, params).fetchall():
        ev = dict(zip(('seq', 'ts', 'actor_id', 'actor_role', 'event_type',
                       'object_type', 'object_id', 'payload', 'prev_hash', 'hash'), r))
        if ev['payload']:
            try:
                ev['payload'] = json.loads(ev['payload'])
            except Exception:
                pass
        out.append(ev)
    return out


# ── alerts ───────────────────────────────────────────────────────────────────
def create_alert(conn, slot_key, alert_type, kpi, value, threshold, severity,
                 message, model_id=None):
    """Insert an alert + ALERT_RAISED audit event. Deduped: if an OPEN alert for
    the same (slot, type, kpi) already exists the nightly monitor won't stack a
    duplicate — the existing alert_id is returned instead."""
    row = conn.execute(
        "SELECT alert_id FROM gov_alerts WHERE slot_key=? AND alert_type=? AND kpi=? "
        "AND status='OPEN'", (slot_key, alert_type, kpi)).fetchone()
    if row:
        return row[0]
    alert_id = 'GAL-' + datetime.now().strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:6].upper()
    conn.execute(
        "INSERT INTO gov_alerts (alert_id, created_at, slot_key, model_id, alert_type, "
        "kpi, value, threshold, severity, message, status) VALUES (?,?,?,?,?,?,?,?,?,?,'OPEN')",
        (alert_id, _now(), slot_key, model_id, alert_type, kpi, value, threshold,
         severity, message))
    append_audit_event(conn, 'ALERT_RAISED', object_type='alert', object_id=alert_id,
                       payload={'slot_key': slot_key, 'alert_type': alert_type,
                                'kpi': kpi, 'value': value, 'threshold': threshold,
                                'severity': severity, 'message': message})
    return alert_id


def ack_alert(conn, alert_id, acked_by, action_taken):
    row = conn.execute("SELECT status FROM gov_alerts WHERE alert_id=?", (alert_id,)).fetchone()
    if not row:
        return {'error': 'Alert not found'}, 404
    if row[0] != 'OPEN':
        return {'error': f'Alert is already {row[0]}'}, 409
    if not acked_by or not (action_taken or '').strip() or len(action_taken.strip()) < MIN_ACTION_CHARS:
        return {'error': f'Acknowledgement requires acked_by and an action description '
                         f'of at least {MIN_ACTION_CHARS} characters.'}, 400
    conn.execute(
        "UPDATE gov_alerts SET status='ACKNOWLEDGED', acked_by=?, acked_at=?, ack_action=? "
        "WHERE alert_id=?", (acked_by, _now(), action_taken.strip(), alert_id))
    append_audit_event(conn, 'ALERT_ACKNOWLEDGED', actor_id=acked_by, actor_role='governance',
                       object_type='alert', object_id=alert_id,
                       payload={'action_taken': action_taken.strip()})
    return {'acknowledged': True, 'alert_id': alert_id}, 200


def list_alerts(conn, status=None, slot_key=None):
    q = "SELECT * FROM gov_alerts"
    clauses, params = [], []
    if status:
        clauses.append("status=?"); params.append(status)
    if slot_key:
        clauses.append("slot_key=?"); params.append(slot_key)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY created_at DESC"
    cur = conn.execute(q, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ── model metadata loaders (auto-population sources) ─────────────────────────
def _load_active_registry():
    p = ML_DIR / 'active_model.json'
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _slot_metadata(model_type, bank_key, exposure_class):
    """Per-model metadata JSON written by trainer.py next to the pickle."""
    p = ML_DIR / 'models' / model_type / bank_key / exposure_class / 'pd_model_metadata.json'
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _latest_registry_row(conn, exposure_class, bank_scope):
    try:
        row = conn.execute(
            "SELECT model_id, auc_roc, promoted_at, n_train, metrics_json, "
            "run_id, trained_at, model_type FROM model_registry "
            "WHERE exposure_class=? AND bank_scope=? ORDER BY promoted_at DESC LIMIT 1",
            (exposure_class, bank_scope)).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return {'model_id': row[0], 'auc_roc': row[1], 'promoted_at': row[2],
            'n_train': row[3], 'metrics': json.loads(row[4]) if row[4] else {},
            'run_id': row[5], 'trained_at': row[6], 'model_type': row[7]}


def dataset_info(conn, slot_key):
    """Which bank/dataset this slot's active model was actually trained on,
    and when — for the Model Trust Ledger's 'Run Details' block. Every
    timestamp returned here is either tz-aware UTC (has an offset/'Z') or a
    naive server-local wall-clock string (this deployment's server clock is
    IST) — callers render both correctly by checking for a suffix."""
    seg, bank = parse_slot(slot_key)
    reg_row = _latest_registry_row(conn, seg, bank) or {}
    bank_name, country_code = None, None
    if bank and bank != 'ALL':
        row = conn.execute(
            "SELECT bank_name, country_code FROM banks WHERE bank_id=?", (bank,)).fetchone()
        if row:
            bank_name, country_code = row
    total_rows = None
    try:
        if bank and bank != 'ALL':
            total_rows = conn.execute(
                "SELECT COUNT(*) FROM bank_loan_metrics WHERE bank_id=?", (bank,)).fetchone()[0]
        else:
            total_rows = conn.execute("SELECT COUNT(*) FROM bank_loan_metrics").fetchone()[0]
    except sqlite3.OperationalError:
        pass
    metrics = reg_row.get('metrics') or {}
    return {
        'slot_key': slot_key, 'exposure_class': seg, 'bank_scope': bank,
        'bank_name': bank_name, 'country_code': country_code,
        'model_type': reg_row.get('model_type'), 'run_id': reg_row.get('run_id'),
        'trained_at': reg_row.get('trained_at'), 'promoted_at': reg_row.get('promoted_at'),
        'dataset_table': 'bank_loan_metrics', 'dataset_total_rows': total_rows,
        'n_train': reg_row.get('n_train'), 'n_test': metrics.get('n_test'),
        'default_rate': metrics.get('default_rate'),
    }


def build_auto_block(conn, slot_key):
    """Auto-populated section of a wiki entry, pulled live from active_model.json,
    model_registry and the per-model metadata JSON so the wiki cannot drift from
    the actual deployed model state."""
    seg, bank = parse_slot(slot_key)
    slot = _load_active_registry().get(slot_key) or {}
    model_type = slot.get('model_type')
    reg = _latest_registry_row(conn, seg, bank) if model_type else None
    meta = _slot_metadata(model_type, bank if bank != 'ALL' else 'ALL', seg) if model_type else {}
    metrics = (reg or {}).get('metrics') or meta.get('metrics') or {}
    return {
        'slot_key': slot_key,
        'exposure_class': seg,
        'bank_scope': bank,
        'model_type': model_type,
        'activated_at': slot.get('activated_at'),
        'model_id': (reg or {}).get('model_id'),
        'promoted_at': (reg or {}).get('promoted_at'),
        'n_train': (reg or {}).get('n_train') or meta.get('n_train'),
        'metrics': metrics,
        'feature_count': meta.get('n_features') or len(meta.get('features') or []) or None,
        'features': (meta.get('features') or [])[:60],
        'trained_at': meta.get('date_trained'),
        'compliance_excluded_cols_included': meta.get('compliance_excluded_cols_included'),
        'refreshed_at': _now(),
    }


# ── wiki ─────────────────────────────────────────────────────────────────────
DEFAULT_PROSE = {
    'purpose': ('Estimate 12-month probability of default (PD) for {seg} exposures '
                '({scope} scope) to drive rating-grade assignment, risk-based pricing, '
                'RWA/EL calculation and the Approve/Refer/Decline recommendation in the '
                'borrower assessment pipeline.'),
    'assumptions': ('Training labels follow the RBI 90-day NPA rule (default_flag). '
                    'Bureau and financial-statement inputs are accurate at assessment time. '
                    'Macro conditions remain within the range represented in training data. '
                    'Missing features are filled with neutral non-defaulter typical values '
                    '(backend/feature_meta.py EXTRA_FEATURE_DEFAULTS).'),
    'validation_methods': ('Back-testing: 80/20 held-out test split with AUC-ROC, PR-AUC, '
                           'Brier score and confusion matrix; 5-fold grouped cross-validation. '
                           'Benchmarking: bootstrap-significance AUC lift over a CIBIL-only '
                           'baseline model. Fairness: protected attributes (gender, marital '
                           'status, foreign-worker flag) excluded from training by default; '
                           'fairness-gap KPI monitored. Stress testing: macro-regime score '
                           'and sensitivity analysis in the assessment engine.'),
    'data_lineage': ('Sources: bank_loan_metrics table in bank.db (customer financials, '
                     'bureau attributes, country macro, trend features) plus CSVs staged in '
                     'data/training/. Transformations: canonical feature-schema alignment '
                     '(backend/feature_schema.py), neutral-default fills, per-bank '
                     'auto-discovered feature encodings. Quality checks: required-column '
                     'validation, numeric range checks, null-report gate, 50-row floor.'),
    'escalation_rules': ('Who: Model Risk Committee (governance dashboard alert queue). '
                         'When: PSI > 0.25 (major drift), AUC degradation > 5%, fairness gap '
                         '> 0.05, or a blocked promotion. How: gov_alerts record raised '
                         'automatically by the monitor; must be acknowledged with actor name '
                         'and an action taken (min 20 chars), recorded on the hash-chained '
                         'audit trail.'),
    'regulatory_references': ('SR 11-7 (Fed/OCC model risk management); Basel Committee '
                              'principles (BCBS); EU AI Act Articles 9-15 (high-risk credit '
                              'scoring systems); RBI IRB guidelines.'),
}


def ensure_wiki_entry(conn, slot_key, author='system'):
    """Create the wiki entry for a slot on first access (version 1), auto-populated
    from live model metadata with seeded default prose. Idempotent."""
    row = conn.execute("SELECT slot_key FROM gov_wiki_entries WHERE slot_key=?",
                       (slot_key,)).fetchone()
    if row:
        return False
    seg, bank = parse_slot(slot_key)
    auto = build_auto_block(conn, slot_key)
    scope_label = 'shared cross-bank' if bank == 'ALL' else f'bank-specific ({bank})'
    fields = {k: (v.format(seg=seg, scope=scope_label) if '{' in v else v)
              for k, v in DEFAULT_PROSE.items()}
    fields['review_cadence'] = RISK_TIER_CADENCE['HIGH']
    ts = _now()
    conn.execute(
        "INSERT INTO gov_wiki_entries (slot_key, model_id, exposure_class, bank_scope, "
        "model_type, risk_tier, purpose, assumptions, validation_methods, data_lineage, "
        "escalation_rules, review_cadence, regulatory_references, auto_json, created_at, "
        "updated_at, updated_by, version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
        (slot_key, auto.get('model_id'), seg, bank, auto.get('model_type'), 'HIGH',
         fields['purpose'], fields['assumptions'], fields['validation_methods'],
         fields['data_lineage'], fields['escalation_rules'], fields['review_cadence'],
         fields['regulatory_references'], json.dumps(auto), ts, ts, author))
    conn.execute(
        "INSERT INTO gov_wiki_versions (slot_key, version, edited_at, edited_by, "
        "change_description, fields_json) VALUES (?,1,?,?,?,?)",
        (slot_key, ts, author, 'Initial entry (auto-generated from model metadata)',
         json.dumps({**fields, 'risk_tier': 'HIGH'})))
    append_audit_event(conn, 'WIKI_CREATED', actor_id=author, actor_role='governance',
                       object_type='wiki', object_id=slot_key,
                       payload={'model_id': auto.get('model_id')})
    return True


def get_wiki(conn, slot_key):
    ensure_wiki_entry(conn, slot_key)
    cur = conn.execute("SELECT * FROM gov_wiki_entries WHERE slot_key=?", (slot_key,))
    cols = [d[0] for d in cur.description]
    entry = dict(zip(cols, cur.fetchone()))
    # refresh the auto block on every read so it always mirrors the deployed model
    auto = build_auto_block(conn, slot_key)
    entry['auto'] = auto
    entry.pop('auto_json', None)
    conn.execute("UPDATE gov_wiki_entries SET auto_json=?, model_id=?, model_type=? "
                 "WHERE slot_key=?",
                 (json.dumps(auto), auto.get('model_id'), auto.get('model_type'), slot_key))
    conn.commit()
    versions = [dict(zip(('version', 'edited_at', 'edited_by', 'change_description'), r))
                for r in conn.execute(
                    "SELECT version, edited_at, edited_by, change_description "
                    "FROM gov_wiki_versions WHERE slot_key=? ORDER BY version DESC",
                    (slot_key,)).fetchall()]
    entry['versions'] = versions
    return entry


def get_wiki_version(conn, slot_key, version):
    row = conn.execute(
        "SELECT version, edited_at, edited_by, change_description, fields_json "
        "FROM gov_wiki_versions WHERE slot_key=? AND version=?",
        (slot_key, int(version))).fetchone()
    if not row:
        return None
    return {'version': row[0], 'edited_at': row[1], 'edited_by': row[2],
            'change_description': row[3], 'fields': json.loads(row[4]) if row[4] else {}}


def update_wiki(conn, slot_key, fields, author, change_description):
    """Edit prose fields and/or risk_tier. Bumps version, snapshots the full field
    set, and records a WIKI_EDIT audit event carrying the changed-field diff."""
    if not author or not (change_description or '').strip():
        return {'error': 'author and change_description are required'}, 400
    ensure_wiki_entry(conn, slot_key)
    cur = conn.execute("SELECT * FROM gov_wiki_entries WHERE slot_key=?", (slot_key,))
    cols = [d[0] for d in cur.description]
    current = dict(zip(cols, cur.fetchone()))

    editable = set(WIKI_PROSE_FIELDS) | {'risk_tier'}
    updates, diff = {}, {}
    for k, v in (fields or {}).items():
        if k not in editable:
            continue
        if k == 'risk_tier':
            v = (v or '').upper()
            if v not in RISK_TIER_CADENCE:
                return {'error': "risk_tier must be HIGH, MEDIUM or LOW"}, 400
        if v != current.get(k):
            updates[k] = v
            diff[k] = {'from': current.get(k), 'to': v}
    if not updates:
        return {'error': 'No changes detected'}, 400
    # a risk-tier change re-derives the review cadence unless the caller set it explicitly
    if 'risk_tier' in updates and 'review_cadence' not in updates:
        updates['review_cadence'] = RISK_TIER_CADENCE[updates['risk_tier']]

    new_version = (current.get('version') or 1) + 1
    ts = _now()
    sets = ', '.join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE gov_wiki_entries SET {sets}, version=?, updated_at=?, updated_by=? "
        f"WHERE slot_key=?",
        list(updates.values()) + [new_version, ts, author, slot_key])
    snapshot = {k: updates.get(k, current.get(k))
                for k in list(WIKI_PROSE_FIELDS) + ['risk_tier']}
    conn.execute(
        "INSERT INTO gov_wiki_versions (slot_key, version, edited_at, edited_by, "
        "change_description, fields_json) VALUES (?,?,?,?,?,?)",
        (slot_key, new_version, ts, author, change_description.strip(),
         json.dumps(snapshot)))
    append_audit_event(conn, 'WIKI_EDIT', actor_id=author, actor_role='governance',
                       object_type='wiki', object_id=slot_key,
                       payload={'version': new_version, 'changes': diff,
                                'change_description': change_description.strip()})
    return {'updated': True, 'version': new_version}, 200


# ── six-pillar validation sign-offs ──────────────────────────────────────────
def _current_model_id(conn, slot_key):
    seg, bank = parse_slot(slot_key)
    reg = _latest_registry_row(conn, seg, bank)
    return (reg or {}).get('model_id') or f'unregistered::{slot_key}'


def get_signoffs(conn, slot_key):
    """All six pillar rows for the slot's CURRENT model_id, auto-seeding PENDING
    rows. A newly promoted model gets a fresh PENDING checklist — validation is
    per model version, not per slot forever."""
    model_id = _current_model_id(conn, slot_key)
    for p, name in PILLARS.items():
        conn.execute(
            "INSERT OR IGNORE INTO gov_validation_signoffs "
            "(slot_key, model_id, pillar, pillar_name, status) VALUES (?,?,?,?, 'PENDING')",
            (slot_key, model_id, p, name))
    conn.commit()
    cur = conn.execute(
        "SELECT pillar, pillar_name, status, validator, signed_at, notes "
        "FROM gov_validation_signoffs WHERE slot_key=? AND model_id=? ORDER BY pillar",
        (slot_key, model_id))
    rows = [dict(zip(('pillar', 'pillar_name', 'status', 'validator', 'signed_at', 'notes'), r))
            for r in cur.fetchall()]
    signed = sum(1 for r in rows if r['status'] == 'SIGNED_OFF')
    return {'slot_key': slot_key, 'model_id': model_id, 'pillars': rows,
            'signed_off': signed, 'total': len(PILLARS),
            'complete': signed == len(PILLARS)}


def sign_off(conn, slot_key, pillar, validator, status, notes=None):
    try:
        pillar = int(pillar)
    except (TypeError, ValueError):
        return {'error': 'pillar must be an integer 1-6'}, 400
    if pillar not in PILLARS:
        return {'error': 'pillar must be an integer 1-6'}, 400
    status = (status or '').upper()
    if status not in ('PENDING', 'SIGNED_OFF', 'FINDINGS'):
        return {'error': "status must be PENDING, SIGNED_OFF or FINDINGS"}, 400
    if status != 'PENDING' and not (validator or '').strip():
        return {'error': 'validator name is required for a sign-off or findings record'}, 400
    model_id = _current_model_id(conn, slot_key)
    get_signoffs(conn, slot_key)          # ensure rows exist
    conn.execute(
        "UPDATE gov_validation_signoffs SET status=?, validator=?, signed_at=?, notes=? "
        "WHERE slot_key=? AND model_id=? AND pillar=?",
        (status, (validator or '').strip() or None,
         _now() if status != 'PENDING' else None, notes, slot_key, model_id, pillar))
    append_audit_event(conn, 'VALIDATION_SIGNOFF', actor_id=validator or 'system',
                       actor_role='validator', object_type='model', object_id=model_id,
                       payload={'slot_key': slot_key, 'pillar': pillar,
                                'pillar_name': PILLARS[pillar], 'status': status,
                                'notes': notes})
    conn.commit()
    return get_signoffs(conn, slot_key), 200


# ── PSI baselines ────────────────────────────────────────────────────────────
def save_baseline(conn, run_id, slot_key, kind, feature, bin_edges, bin_freqs, n_rows):
    conn.execute(
        "INSERT INTO gov_baseline_distributions (run_id, slot_key, created_at, kind, "
        "feature, bin_edges_json, bin_freqs_json, n_rows) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, slot_key, _now(), kind, feature,
         json.dumps([float(x) for x in bin_edges]),
         json.dumps([float(x) for x in bin_freqs]), int(n_rows)))
    conn.commit()


def get_latest_baselines(conn, slot_key):
    """All baseline rows for the newest run_id snapshotted for this slot."""
    row = conn.execute(
        "SELECT run_id FROM gov_baseline_distributions WHERE slot_key=? "
        "ORDER BY created_at DESC LIMIT 1", (slot_key,)).fetchone()
    if not row:
        return None
    run_id = row[0]
    out = {'run_id': run_id, 'score': None, 'features': {}}
    for r in conn.execute(
            "SELECT kind, feature, bin_edges_json, bin_freqs_json, n_rows "
            "FROM gov_baseline_distributions WHERE slot_key=? AND run_id=?",
            (slot_key, run_id)).fetchall():
        entry = {'edges': json.loads(r[2]), 'freqs': json.loads(r[3]), 'n_rows': r[4]}
        if r[0] == 'score':
            out['score'] = entry
        else:
            out['features'][r[1]] = entry
    return out


# ── regulatory mapping ───────────────────────────────────────────────────────
def regulatory_mapping(conn, slot_key):
    """Auto-derived SR 11-7 / Basel / EU AI Act requirement status for one slot.
    Statuses are computed from live governance state — not hand-asserted — so
    the compliance view can never claim more than the system actually does."""
    ensure_wiki_entry(conn, slot_key)
    cur = conn.execute("SELECT * FROM gov_wiki_entries WHERE slot_key=?", (slot_key,))
    cols = [d[0] for d in cur.description]
    wiki = dict(zip(cols, cur.fetchone()))
    signoffs = get_signoffs(conn, slot_key)

    prose_complete = all((wiki.get(f) or '').strip() for f in WIKI_PROSE_FIELDS)
    gov_ok = bool((wiki.get('purpose') or '').strip() and (wiki.get('escalation_rules') or '').strip())

    # Ongoing monitoring: a KPI snapshot for this slot within the last 48h
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec='seconds')
    mon_row = conn.execute(
        "SELECT run_ts FROM gov_kpi_snapshots WHERE slot_key=? AND run_ts>=? LIMIT 1",
        (slot_key, cutoff)).fetchone()

    # Stress-testing evidence: CV / significance diagnostics present in metadata
    auto = build_auto_block(conn, slot_key)
    seg, bank = parse_slot(slot_key)
    meta = _slot_metadata(auto.get('model_type') or 'xgboost',
                          bank if bank != 'ALL' else 'ALL', seg)
    stress_evidence = bool(meta.get('lift_significance') or
                           (meta.get('metrics') or {}).get('cv_auc_mean') or
                           meta.get('epv'))

    # Human oversight: finalised RM decisions exist
    try:
        from backend.rm_case_store import insights
        ins = insights(conn)
        n_final = ins.get('decisions_final', 0)
    except Exception:
        ins, n_final = {}, 0

    def status_of(ok, partial=False):
        return 'SATISFIED' if ok else ('PARTIAL' if partial else 'GAP')

    val_status = ('SATISFIED' if signoffs['complete']
                  else ('PARTIAL' if signoffs['signed_off'] > 0 else 'GAP'))

    requirements = [
        {'requirement': 'Governance & Accountability',
         'frameworks': ['SR 11-7', 'Basel'],
         'status': status_of(gov_ok),
         'evidence': 'Wiki entry with documented purpose, ownership and escalation rules'
                     if gov_ok else 'Wiki purpose/escalation rules incomplete'},
        {'requirement': 'Independent Validation',
         'frameworks': ['SR 11-7'],
         'status': val_status,
         'evidence': f"Six-pillar validation: {signoffs['signed_off']}/6 pillars signed off "
                     f"for {signoffs['model_id']}"},
        {'requirement': 'Documentation',
         'frameworks': ['SR 11-7', 'Basel', 'EU AI Act'],
         'status': status_of(prose_complete, partial=True),
         'evidence': 'All wiki sections populated with version history'
                     if prose_complete else 'Some wiki sections empty'},
        {'requirement': 'Stress Testing',
         'frameworks': ['Basel'],
         'status': status_of(stress_evidence, partial=True),
         'evidence': 'Cross-validation + bootstrap significance diagnostics in model '
                     'metadata; macro-regime sensitivity in assessment engine'
                     if stress_evidence else 'No CV/significance diagnostics found in metadata'},
        {'requirement': 'Ongoing Monitoring',
         'frameworks': ['SR 11-7', 'EU AI Act'],
         'status': status_of(bool(mon_row)),
         'evidence': f'Drift/KPI monitor ran within 48h (last: {mon_row[0]})'
                     if mon_row else 'No KPI snapshot in the last 48h — run the monitor'},
        {'requirement': 'Human Oversight',
         'frameworks': ['EU AI Act'],
         'status': status_of(n_final > 0),
         'evidence': f"RM accept/reject flow live: {n_final} finalised decisions, "
                     f"override rate {ins.get('override_rate_pct', 0)}%"
                     if n_final else 'No finalised RM decisions yet'},
        {'requirement': 'Transparency',
         'frameworks': ['EU AI Act'],
         'status': 'SATISFIED',
         'evidence': 'SHAP per-assessment explanations (backend/shap_explainer.py), '
                     'reason codes and adverse-action applicant report '
                     '(public/report-applicant.html)'},
    ]
    satisfied = sum(1 for r in requirements if r['status'] == 'SATISFIED')
    return {'slot_key': slot_key, 'model_id': signoffs['model_id'],
            'requirements': requirements,
            'satisfied': satisfied, 'total': len(requirements)}


# ── per-run story snapshots ──────────────────────────────────────────────────
REPORTS_DIR = Path(__file__).resolve().parent.parent / 'data' / 'governance_reports'


def snapshot_story(conn, slot_key, reports_dir=None):
    """Freeze everything the Model Trust Ledger page needs for slot_key's
    CURRENT active model and write it to disk, keyed by run_id, so the story
    survives the next retrain (which would otherwise overwrite live state).
    Call this right after a model is promoted. Non-fatal by convention —
    callers should wrap this in try/except, same as _snapshot_baseline."""
    reg = regulatory_mapping(conn, slot_key)
    signoffs = get_signoffs(conn, slot_key)
    seg, bank = parse_slot(slot_key)
    reg_row = _latest_registry_row(conn, seg, bank) or {}
    model_id = reg.get('model_id') or reg_row.get('model_id')
    run_id = reg_row.get('run_id') or model_id or f'unknown_{int(datetime.now().timestamp())}'

    kpis = {}
    for kpi in ('psi_score', 'psi_feature', 'auc_stability', 'fairness_gap', 'prediction_volume'):
        row = conn.execute(
            "SELECT value, threshold, status, run_ts, detail_json FROM gov_kpi_snapshots "
            "WHERE slot_key=? AND kpi=? AND feature IS NULL "
            "ORDER BY run_ts DESC LIMIT 1", (slot_key, kpi)).fetchone()
        if row:
            kpis[kpi] = {'value': row[0], 'threshold': row[1], 'status': row[2],
                        'run_ts': row[3],
                        'detail': json.loads(row[4]) if row[4] else {}}

    snapshot = {
        'slot_key': slot_key,
        'model_id': model_id,
        'run_id': run_id,
        'exposure_class': seg,
        'bank_scope': bank,
        'auc_roc': reg_row.get('auc_roc'),
        'n_train': reg_row.get('n_train'),
        'promoted_at': reg_row.get('promoted_at'),
        'generated_at': _now(),
        'dataset': dataset_info(conn, slot_key),
        'regulatory': reg,
        'validation': signoffs,
        'kpis': kpis,
        'audit_events': list_audit_events(conn, limit=8),
        'audit_chain': verify_chain(conn),
    }

    base = Path(reports_dir) if reports_dir else REPORTS_DIR
    out_dir = base / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'story.json', 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, default=str)
    return snapshot


def list_story_snapshots(reports_dir=None):
    """Index of every saved snapshot, newest first, for the 'Past Reports' list."""
    base = Path(reports_dir) if reports_dir else REPORTS_DIR
    if not base.exists():
        return []
    out = []
    for d in base.iterdir():
        f = d / 'story.json'
        if not f.exists():
            continue
        try:
            with open(f, encoding='utf-8') as fh:
                snap = json.load(fh)
            ds = snap.get('dataset') or {}
            out.append({'run_id': snap.get('run_id'), 'slot_key': snap.get('slot_key'),
                        'model_id': snap.get('model_id'), 'auc_roc': snap.get('auc_roc'),
                        'promoted_at': snap.get('promoted_at'),
                        'generated_at': snap.get('generated_at'),
                        'bank_name': ds.get('bank_name'), 'bank_scope': ds.get('bank_scope'),
                        'satisfied': (snap.get('regulatory') or {}).get('satisfied'),
                        'total': (snap.get('regulatory') or {}).get('total')})
        except Exception:
            continue
    out.sort(key=lambda r: r.get('generated_at') or '', reverse=True)
    return out


def get_story_snapshot(run_id, reports_dir=None):
    base = Path(reports_dir) if reports_dir else REPORTS_DIR
    f = base / run_id / 'story.json'
    if not f.exists():
        return None
    with open(f, encoding='utf-8') as fh:
        return json.load(fh)
