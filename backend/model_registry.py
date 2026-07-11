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
"""

import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_registry (
    model_id        TEXT PRIMARY KEY,
    exposure_class  TEXT NOT NULL,   -- 'ALL' or one of the 4 Basel segments
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


def register_promotion(conn, exposure_class, model_type, run_id, trained_at,
                        promoted_at, metrics, n_train=None, bank_ids=None):
    """Insert one model_registry row for a just-promoted model. Returns model_id."""
    _ensure_schema(conn)
    seg = exposure_class or 'ALL'
    model_id = f"{model_type}_{seg}_{run_id}"
    conn.execute(
        """INSERT OR REPLACE INTO model_registry
           (model_id, exposure_class, model_type, run_id, trained_at, promoted_at,
            n_train, auc_roc, metrics_json, bank_ids_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (model_id, seg, model_type, run_id, trained_at, promoted_at,
         n_train, (metrics or {}).get('auc_roc'),
         json.dumps(metrics or {}), json.dumps(bank_ids) if bank_ids else None)
    )
    conn.commit()
    return model_id


def get_active_model_id(conn, exposure_class):
    """Most recently promoted model_id for a segment, or None."""
    _ensure_schema(conn)
    seg = exposure_class or 'ALL'
    row = conn.execute(
        "SELECT model_id FROM model_registry WHERE exposure_class=? "
        "ORDER BY promoted_at DESC LIMIT 1",
        (seg,)
    ).fetchone()
    return row[0] if row else None
