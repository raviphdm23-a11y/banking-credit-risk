"""
model_registry.py
───────────────────
Phase 4 of the data-layer restructuring: L1 reference record for which
model version produced a given prediction.

Before this module existed, "which model made this prediction" only lived
in `ml_models/run_history.json` (a flat file, not queryable from bank.db)
and `findings['model_version']` (a string embedded in each assessment's
JSON blob, not a foreign key to anything). `prediction_store.py` needs a
real model_id to point at so a prediction row is traceable to an actual
trained-and-promoted model, not just a version label.

One row per promotion event (ml_models/trainer.py calls register_promotion()
right after activate_model() succeeds). Self-creating, same pattern as
alm_engine.py/collateral_store.py.

Per-bank model hierarchy (added for the model-routing switch): `bank_scope`
distinguishes the shared cross-bank model ('ALL', the default and today's
only kind) from a model trained/promoted for exactly one bank ('BANK00X').
`exposure_class` can additionally be 'GENERIC' - a bank-wide model with no
Basel segmentation, for banks whose source data has no exposure_class
concept at all. get_active_model_id()'s 3-tier fallback (bank+segment ->
bank+GENERIC -> shared ALL+segment) is what a bank-aware inference request
resolves against.
"""

import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_registry (
    model_id        TEXT PRIMARY KEY,
    exposure_class  TEXT NOT NULL,   -- one of the 4 Basel segments, or 'GENERIC' (bank-wide, unsegmented)
    bank_scope      TEXT NOT NULL DEFAULT 'ALL',   -- 'ALL' (shared cross-bank) or a single bank_id
    model_type      TEXT NOT NULL,   -- 'xgboost', etc.
    run_id          TEXT,
    trained_at      TEXT NOT NULL,
    promoted_at     TEXT NOT NULL,
    n_train         INTEGER,
    auc_roc         REAL,
    metrics_json    TEXT,
    bank_ids_json   TEXT
);
"""


def _ensure_schema(conn):
    conn.execute(SCHEMA)
    try:
        conn.execute("ALTER TABLE model_registry ADD COLUMN bank_scope TEXT NOT NULL DEFAULT 'ALL'")
    except Exception:
        pass  # already exists (table created by an earlier version of this module)


def register_promotion(conn, exposure_class, model_type, run_id, trained_at,
                        promoted_at, metrics, n_train=None, bank_ids=None):
    """Insert one model_registry row for a just-promoted model. Returns model_id.

    bank_scope is derived from bank_ids: a single bank_id makes this a
    bank-scoped promotion; anything else (None, empty, or multiple banks)
    is the shared 'ALL' scope - "bank-specific model" means exactly one
    bank, by definition, for routing purposes.
    """
    _ensure_schema(conn)
    seg = exposure_class or 'ALL'
    bank_scope = bank_ids[0] if bank_ids and len(bank_ids) == 1 else 'ALL'
    model_id = f"{model_type}_{seg}_{bank_scope}_{run_id}"
    conn.execute(
        """INSERT OR REPLACE INTO model_registry
           (model_id, exposure_class, bank_scope, model_type, run_id, trained_at, promoted_at,
            n_train, auc_roc, metrics_json, bank_ids_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (model_id, seg, bank_scope, model_type, run_id, trained_at, promoted_at,
         n_train, (metrics or {}).get('auc_roc'),
         json.dumps(metrics or {}), json.dumps(bank_ids) if bank_ids else None)
    )
    conn.commit()
    return model_id


def get_active_model_id(conn, exposure_class, bank_id=None):
    """Most recently promoted model_id, resolved with the 3-tier fallback:
       1. bank_id + exposure_class exact match (bank-specific segment model)
       2. bank_id + 'GENERIC' (bank-wide, unsegmented model)
       3. shared 'ALL' scope + exposure_class (today's cross-bank model)

    Callers that don't pass bank_id (all pre-existing call sites) skip
    straight to tier 3 - identical behaviour to before bank_scope existed.
    """
    _ensure_schema(conn)
    seg = exposure_class or 'ALL'
    if bank_id:
        for scope, s in ((bank_id, seg), (bank_id, 'GENERIC')):
            row = conn.execute(
                "SELECT model_id FROM model_registry WHERE bank_scope=? AND exposure_class=? "
                "ORDER BY promoted_at DESC LIMIT 1",
                (scope, s)
            ).fetchone()
            if row:
                return row[0]
    row = conn.execute(
        "SELECT model_id FROM model_registry WHERE bank_scope='ALL' AND exposure_class=? "
        "ORDER BY promoted_at DESC LIMIT 1",
        (seg,)
    ).fetchone()
    return row[0] if row else None
