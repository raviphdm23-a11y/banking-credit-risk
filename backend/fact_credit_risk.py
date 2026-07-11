"""
fact_credit_risk.py
─────────────────────
Phase 5 of the data-layer restructuring: the L4 gold-layer table.

One row per loan per reporting period, denormalized across every layer
built in Phases 1-4:
    - loans                (contract terms, rwa_approach, seniority)
    - customers             (identity)
    - credit_risk_metrics   (current live ratios/PD)
    - bank_loan_metrics     (feature-store snapshot: macro deltas, regime score)
    - collateral_register   (Phase 2 - collateral, if any)
    - prediction_store      (Phase 4 - the assessment that led to this loan, if any)
    - reg_client_exposures  (Phase 3-aware: AIRB or SA RWA/capital/provision,
                             already correctly branched by rwa_approach)

Before this table existed, every report generator (regulatory batch,
financial reports, underwriter PDF, RM insights) independently re-joined
these tables with its own hand-written SQL - meaning the same "what is
this loan's RWA/PD/collateral position" question could get answered
slightly differently in different places (e.g. one report reading
reg_client_exposures, another re-deriving RWA from loans + a stale
LGD_BY_TYPE lookup that predates Phase 3's AIRB branch).

This is a rebuilt-not-incrementally-maintained table (DELETE+INSERT per
bank per report_date), refreshed as part of the regulatory batch
(operations/scripts/run_regulatory_batch.py), since it depends on that
batch's reg_client_exposures output already existing for the same
report_date. Consumers should read the latest report_date per bank/loan,
not assume there's only ever one row per loan.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_credit_risk (
    loan_id             TEXT NOT NULL,
    report_date         TEXT NOT NULL,
    bank_id             TEXT,
    bank_name           TEXT,
    cid                 TEXT,
    customer_name       TEXT,
    country_code        TEXT,
    product             TEXT,
    exposure_class      TEXT,
    rwa_approach        TEXT,
    seniority           TEXT,
    loan_status         TEXT,
    loan_classification TEXT,
    principal           REAL,
    outstanding         REAL,
    rate                REAL,
    tenure_months       INTEGER,
    disbursed           TEXT,
    maturity            TEXT,
    ltv_ratio           REAL,
    collateral_type     TEXT,
    collateral_value    REAL,
    effective_collateral_value REAL,
    de_ratio            REAL,
    interest_coverage   REAL,
    profitability       REAL,
    liquidity_ratio     REAL,
    cibil_score         INTEGER,
    macro_regime_score  REAL,
    delta_gdp_pct       REAL,
    delta_unemployment_pct REAL,
    pd_current          REAL,            -- live pd_score from credit_risk_metrics
    pd_at_origination   REAL,            -- prediction_store.pd_point, if this loan has one
    rating_grade        TEXT,
    lgd                 REAL,
    ead                 REAL,
    risk_weight         REAL,
    rwa                 REAL,
    capital_charge      REAL,
    expected_loss       REAL,
    provision           REAL,
    model_id            TEXT,
    calculation_methodology TEXT,
    is_npa              INTEGER,
    generated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (loan_id, report_date)
);
CREATE INDEX IF NOT EXISTS idx_fact_bank_date ON fact_credit_risk(bank_id, report_date);
CREATE INDEX IF NOT EXISTS idx_fact_cid ON fact_credit_risk(cid);
"""


def _ensure_schema(conn):
    conn.executescript(SCHEMA)
    # These source tables predate fact_credit_risk and were never indexed on
    # their loan-id join columns - the build query below joins against all
    # three per loan, and without an index that's an effective O(n^2) table
    # scan across ~19K loans (confirmed: hung for minutes before this fix).
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crm_lid ON credit_risk_metrics(lid, metric_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collateral_loan_id ON collateral_register(loan_id, collateral_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blm_loan_id ON bank_loan_metrics(loan_id)")


def build_fact_credit_risk(conn, bank_id, report_date):
    """(Re)build fact_credit_risk rows for one bank + report_date from
    reg_client_exposures (already generated for this report_date by
    run_regulatory_batch.py) joined against every earlier-phase table.
    Idempotent - deletes then reinserts this bank+date's rows.
    """
    _ensure_schema(conn)
    # collateral_register and prediction_store (Phases 2/4) self-create lazily
    # on first write - a bank.db that's never booked a loan through the new
    # paths yet won't have them at all, so the LEFT JOINs below would 500.
    from backend.collateral_store import _ensure_schema as _ensure_collateral
    from backend.prediction_store import _ensure_schema as _ensure_prediction
    from backend.loan_booking import _ensure_loan_columns
    _ensure_collateral(conn)
    _ensure_prediction(conn)
    _ensure_loan_columns(conn)   # loans.rwa_approach/seniority (Phase 3)

    cur = conn.cursor()
    cur.execute("DELETE FROM fact_credit_risk WHERE bank_id=? AND report_date=?", (bank_id, report_date))

    cur.execute(
        """
        SELECT
            e.loan_id, e.cid, e.customer_name,
            l.bank_id, b.bank_name, b.country_code,
            l.type, l.exposure_class, l.rwa_approach, l.seniority,
            l.status, l.loan_classification, l.principal, l.outstanding, l.rate,
            l.tenure, l.disbursed, l.maturity, l.ltv_ratio,
            cr.collateral_type, cr.collateral_value, cr.effective_value,
            crm.de, crm.intcov, crm.profit, crm.liq,
            blm.cibil_score, blm.macro_regime_score, blm.delta_gdp_pct, blm.delta_unemployment_pct,
            crm.pd_score,
            ps.pd_point, ps.rating_grade, ps.model_id, ps.calculation_methodology,
            e.classification, e.ead, e.pd, e.lgd, e.risk_weight, e.rwa,
            e.capital_charge, e.expected_loss, e.provision
        FROM reg_client_exposures e
        JOIN loans l ON l.id = e.loan_id
        JOIN banks b ON b.bank_id = l.bank_id
        LEFT JOIN credit_risk_metrics crm ON crm.metric_id = (
            SELECT MAX(metric_id) FROM credit_risk_metrics WHERE lid = l.id)
        LEFT JOIN bank_loan_metrics blm ON blm.loan_id = l.id
        LEFT JOIN collateral_register cr ON cr.collateral_id = (
            SELECT MAX(collateral_id) FROM collateral_register WHERE loan_id = l.id)
        LEFT JOIN prediction_store ps ON ps.loan_id = l.id
        WHERE e.bank_id = ? AND e.report_date = ?
        """,
        (bank_id, report_date)
    )
    rows = cur.fetchall()

    for r in rows:
        (loan_id, cid, customer_name, lbank_id, bank_name, country_code,
         product, exposure_class, rwa_approach, seniority,
         status, classification, principal, outstanding, rate,
         tenure, disbursed, maturity, ltv_ratio,
         collateral_type, collateral_value, effective_value,
         de, intcov, profit, liq,
         cibil_score, macro_regime_score, delta_gdp_pct, delta_unemployment_pct,
         pd_current,
         pd_at_origination, rating_grade, model_id, calculation_methodology,
         exp_classification, ead, pd_exp, lgd, risk_weight, rwa,
         capital_charge, expected_loss, provision) = r

        is_npa = 1 if (classification or 'Standard') not in ('Standard', 'Performing') else 0

        cur.execute(
            """INSERT INTO fact_credit_risk
               (loan_id, report_date, bank_id, bank_name, cid, customer_name, country_code,
                product, exposure_class, rwa_approach, seniority, loan_status, loan_classification,
                principal, outstanding, rate, tenure_months, disbursed, maturity, ltv_ratio,
                collateral_type, collateral_value, effective_collateral_value,
                de_ratio, interest_coverage, profitability, liquidity_ratio,
                cibil_score, macro_regime_score, delta_gdp_pct, delta_unemployment_pct,
                pd_current, pd_at_origination, rating_grade, lgd, ead, risk_weight, rwa,
                capital_charge, expected_loss, provision, model_id, calculation_methodology, is_npa)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (loan_id, report_date, lbank_id, bank_name, cid, customer_name, country_code,
             product, exposure_class, rwa_approach, seniority, status, classification,
             principal, outstanding, rate, tenure, disbursed, maturity, ltv_ratio,
             collateral_type, collateral_value, effective_value,
             de, intcov, profit, liq,
             cibil_score, macro_regime_score, delta_gdp_pct, delta_unemployment_pct,
             pd_current, pd_at_origination, rating_grade, lgd, ead, risk_weight, rwa,
             capital_charge, expected_loss, provision, model_id, calculation_methodology, is_npa)
        )

    conn.commit()
    return len(rows)


def get_fact_credit_risk(conn, bank_id=None, report_date=None, cid=None):
    """Read helper: latest fact_credit_risk rows, optionally filtered.
    If report_date is omitted, returns each loan's most recent row."""
    _ensure_schema(conn)
    where, params = [], []
    if bank_id:
        where.append("bank_id = ?"); params.append(bank_id)
    if cid:
        where.append("cid = ?"); params.append(cid)
    if report_date:
        where.append("report_date = ?"); params.append(report_date)
        sql = "SELECT * FROM fact_credit_risk"
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur = conn.execute(sql, params)
    else:
        sql = (
            "SELECT f.* FROM fact_credit_risk f "
            "JOIN (SELECT loan_id, MAX(report_date) AS max_date FROM fact_credit_risk "
            "      GROUP BY loan_id) latest "
            "  ON latest.loan_id = f.loan_id AND latest.max_date = f.report_date"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
