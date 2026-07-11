"""
feature_schema.py
──────────────────
Phase 1 of the data-layer restructuring: a single canonical definition of
the model's training feature columns, the ones `bank_loan_metrics` (the
training table, aka the informal "feature store") must populate for every
loan row.

Before this module existed, the same column list was hand-typed
independently in three places — `ml_models/trainer.py`'s SELECT,
`operations/scripts/sync_bank_loan_metrics.py`'s SELECT/INSERT, and
`backend/feature_meta.py`'s live-inference defaults — with no mechanism
forcing them to agree. That's exactly how `macro_regime_score` and its 4
delta columns went 100% NULL for 15,349 training rows for months, with
zero indication other than XGBoost training silently reporting
0.000000 feature_importances_ for those columns (see
operations/scripts/backfill_macro_deltas.py for the fix).

`FEATURE_COLS` here is the actual model input vector (mirrors
`ml_models/trainer.py`'s FEATURE_COLS exactly — that remains the
source of truth for training; this module exists so other consumers can
import it instead of re-typing it, and so a shared NULL-check can run
against it). `REQUIRED_COLUMNS` adds the columns needed to load/validate a
row (ids, target, observation date, plus previous_default_flag which is
deliberately excluded from FEATURE_COLS as a leakage risk but still
required to be present/non-null in the source data).
"""

FEATURE_COLS = [
    # Financial ratios (4)
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    # KYC — character & capacity (9)
    'age', 'employment_type_enc', 'years_employed', 'annual_income',
    'foir', 'num_dependents', 'city_tier_enc', 'education_enc', 'residence_type_enc',
    # KYC — context (6)
    'loan_purpose_enc', 'cibil_score',
    'months_as_customer', 'num_late_payments_past_12m',
    'existing_loans_count', 'num_existing_products',
    # Country macro levels (4)
    'gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
    # Trend features (3)
    'delta_de_ratio', 'delta_cibil', 'months_since_origination',
    # Macro regime delta features (5)
    'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct',
    'delta_unemployment_pct', 'macro_regime_score',
    # "Other circumstances" features (5)
    'ecs_bounce_count', 'other_lender_emi_ratio', 'income_disruption_flag',
    'sector_stress_index', 'ltv_trend_pct',
]

REQUIRED_COLUMNS = set(FEATURE_COLS) | {
    'bank_id', 'loan_id', 'default_flag', 'observation_date',
    'previous_default_flag', 'is_rural',
}


def null_report(conn, table='bank_loan_metrics', columns=None):
    """Return {col: (null_count, total_rows)} for each canonical column present in `table`."""
    columns = columns if columns is not None else FEATURE_COLS
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    total = cur.fetchone()[0]
    report = {}
    for col in columns:
        if col not in existing:
            report[col] = (None, total)  # column missing entirely
            continue
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
        report[col] = (cur.fetchone()[0], total)
    return report


def validate_no_nulls(conn, table='bank_loan_metrics', columns=None, raise_on_fail=True):
    """Fail loudly if any canonical feature column is missing or has NULLs.

    A feature that's NULL across the board trains with zero variance and
    gets exactly 0.000000 XGBoost feature_importances_ — silently. This
    check is meant to catch that at sync/train time instead of by accident
    months later. Returns the list of (col, null_count, total) offenders.
    """
    report = null_report(conn, table, columns)
    bad = [(col, n, t) for col, (n, t) in report.items() if n is None or n > 0]
    if bad and raise_on_fail:
        lines = []
        for col, n, t in bad:
            if n is None:
                lines.append(f'  - {col}: MISSING from {table} entirely')
            else:
                lines.append(f'  - {col}: {n}/{t} rows NULL')
        raise ValueError(
            f"[feature_schema] {table} has unpopulated canonical feature columns "
            f"— any model trained on these will silently see zero variance:\n" + '\n'.join(lines)
        )
    return bad
