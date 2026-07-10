"""
sync_bank_loan_metrics.py
─────────────────────────
End-of-day job: derives bank_loan_metrics from actual customer loan data
stored across customers / loans / accounts / transactions /
credit_risk_metrics / customer_kyc / ref_lookup.

Only loans with a completed lifecycle (status = 'Closed' or 'Written-Off')
are included. 'Active' loans are excluded because their outcome hasn't
actually resolved yet - the model would be trained against a status that
can still change, not the loan's real, final outcome. This is a stricter
(and much smaller) definitive-outcome sample than the RBI 90-day rule
alone would give.

Default rule (loan's own resolved status is authoritative):
  A loan is flagged default_flag = 1 if ANY of the following:
    1. loans.status = 'Written-Off', or loans.loan_classification is
       'NPA', 'Doubtful', or 'Loss'
    2. credit_risk_metrics.npa_flag = 1
  Otherwise (status = 'Closed', no adverse classification/flag) -> 0.

KYC features (risk-ordered integer encoding via ref_lookup.risk_order):
  employment_type_enc, city_tier_enc, education_enc, residence_type_enc

Run:
    python sync_bank_loan_metrics.py
"""

import os
import sqlite3
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seed_ref_lookup_domains import seed as seed_ref_lookup_domains

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')


# ─────────────────────────────────────────────────────────────────────────────
# Default detection
# ─────────────────────────────────────────────────────────────────────────────

def compute_default_flag(classification, npa_flag, status):
    """
    Apply the default rule. Returns (flag: int, reason: str).

    Only called for loans with a resolved lifecycle (status IN ('Closed',
    'Written-Off') — see the WHERE clause in sync()). For that population,
    status/loan_classification already hold the loan's real, final outcome
    (as established by resolve_loan_lifecycle.py from actual observed
    payment history), so they are authoritative and used directly:
      - Written-Off  -> default
      - Closed       -> not default (resolve_loan_lifecycle.py only closes
                        loans that paid >=85% of their EMIs over their own
                        observed window)
    The old "3 consecutive missed EMIs measured against real wall-clock
    today" heuristic is NOT applied here: for a loan whose transaction
    history was seeded only for a fixed window post-disbursement, that
    heuristic flags every resolved loan as having missed its final EMIs
    (the seed window ended, not the borrower) - it was previously drowned
    out by the much larger Active population, but became a 100%-false-
    default rate once training was scoped to completed loans only.
    """
    if status == 'Written-Off' or classification in ('NPA', 'Doubtful', 'Loss'):
        return 1, 'status/classification = {}/{}'.format(status, classification)

    if npa_flag:
        return 1, 'npa_flag = 1 in credit_risk_metrics'

    return 0, 'closed — fully repaid (status=Closed, no NPA/loss flag)'


# ─────────────────────────────────────────────────────────────────────────────
# Main sync
# ─────────────────────────────────────────────────────────────────────────────

def sync(db_path=DB_PATH):
    seed_ref_lookup_domains(db_path, verbose=False)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today_str  = date.today().isoformat()
    loaded_at  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("=" * 70)
    print("bank_loan_metrics sync — {}".format(today_str))
    print("=" * 70)

    # "Other circumstances" columns (see conversation this was added from) -
    # added here rather than as a separate enrichment pass like
    # add_macro_regime_score.py/build_behavioral_features.py, since these are
    # plain copies from customer_kyc/loans, not derived computations.
    for col in ('ecs_bounce_count INTEGER', 'other_lender_emi_ratio REAL',
                'income_disruption_flag INTEGER', 'sector_stress_index REAL',
                'ltv_trend_pct REAL'):
        try:
            cursor.execute(f"ALTER TABLE bank_loan_metrics ADD COLUMN {col}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' not in str(e).lower():
                raise

    # Step 1: Clear ALL existing rows (removes synthetic CSV data too)
    cursor.execute("DELETE FROM bank_loan_metrics")
    print("Cleared {} stale rows.".format(cursor.rowcount))

    # Step 2: Load every loan with credit risk metrics + KYC + ref encodings
    cursor.execute("""
        SELECT
            l.id                        AS loan_id,
            l.bank_id,
            b.bank_name,
            l.type                      AS loan_type,
            l.disbursed,
            l.tenure,
            l.emi,
            l.loan_classification,
            l.status,
            c.first || ' ' || c.last    AS customer_name,

            -- Financial ratios from credit_risk_metrics
            crm.de                      AS de_ratio,
            crm.intcov                  AS interest_coverage,
            crm.profit                  AS profitability,
            crm.liq                     AS liquidity_ratio,
            crm.npa_flag,
            crm.pd_score                AS pd_observed,

            -- KYC raw fields
            kyc.age,
            kyc.years_employed,
            kyc.annual_income,
            kyc.foir_declared,
            kyc.num_dependents,

            -- KYC categoricals → risk-ordered integers via ref_lookup
            emp_ref.risk_order          AS employment_type_enc,
            edu_ref.risk_order          AS education_enc,
            res_ref.risk_order          AS residence_type_enc,
            cty_ref.risk_order          AS city_tier_enc,
            lp_ref.risk_order           AS loan_purpose_enc,

            -- KYC context fields (direct)
            kyc.cibil_score,
            kyc.previous_default_flag,
            kyc.months_as_customer,
            kyc.num_late_payments_past_12m,
            kyc.existing_loans_count,
            kyc.num_existing_products,
            kyc.is_rural,

            -- "Other circumstances" features - signals of default risk
            -- beyond financial ratios/CIBIL (see conversation this was added from)
            kyc.ecs_bounce_count,
            kyc.other_lender_emi_ratio,
            kyc.income_disruption_flag,
            kyc.sector_stress_index,
            l.ltv_trend_pct,

            -- Country
            b.country_code,

            -- Country macro (latest period per country)
            cm.gdp_growth_pct,
            cm.inflation_cpi_pct,
            cm.policy_rate_pct,
            cm.unemployment_pct,

            -- Trend features (direction of travel since origination)
            ROUND(crm.de - crm.prior_de, 4)                                   AS delta_de_ratio,
            ROUND(CAST(kyc.cibil_score AS REAL) - CAST(crm.prior_cibil AS REAL), 1) AS delta_cibil,
            ROUND((julianday('now') - julianday(l.disbursed)) / 30.44, 1)     AS months_since_origination,

            -- Basel III.1 SA exposure class
            l.exposure_class

        FROM loans l
        JOIN banks                  b       ON b.bank_id      = l.bank_id
        JOIN customers              c       ON c.id           = l.cid
        LEFT JOIN credit_risk_metrics crm   ON crm.metric_id  = (
                                               SELECT MAX(metric_id) FROM credit_risk_metrics
                                               WHERE lid = l.id)
        LEFT JOIN customer_kyc      kyc     ON kyc.kyc_id     = (
                                               SELECT MAX(kyc_id) FROM customer_kyc
                                               WHERE cid = l.cid AND bank_id = l.bank_id)
        LEFT JOIN ref_lookup        emp_ref ON emp_ref.domain = 'employment_type'
                                           AND emp_ref.code   = kyc.employment_type
        LEFT JOIN ref_lookup        edu_ref ON edu_ref.domain = 'education_level'
                                           AND edu_ref.code   = kyc.education_level
        LEFT JOIN ref_lookup        res_ref ON res_ref.domain = 'residence_type'
                                           AND res_ref.code   = kyc.residence_type
        LEFT JOIN ref_lookup        cty_ref ON cty_ref.domain = 'city_tier'
                                           AND cty_ref.code   = kyc.city_tier
        LEFT JOIN ref_lookup        lp_ref  ON lp_ref.domain  = 'loan_purpose'
                                           AND lp_ref.code    = kyc.loan_purpose
        LEFT JOIN country_macro     cm      ON cm.country_code = b.country_code
                                           AND cm.period = (
                                               SELECT MAX(period) FROM country_macro
                                               WHERE country_code = b.country_code)
        WHERE l.status IN ('Closed', 'Written-Off')
        ORDER BY l.bank_id, l.id
    """)
    loans = cursor.fetchall()

    print("Loans found in database: {}".format(len(loans)))
    print()

    inserted = 0
    skipped  = 0

    for loan in loans:
        lid = loan['loan_id']

        # Skip loans with no credit risk metrics (can't compute ratios)
        if loan['de_ratio'] is None:
            print("  SKIP  {} ({}) — no credit_risk_metrics record".format(
                lid, loan['customer_name']))
            skipped += 1
            continue

        # Compute default flag from the loan's resolved status/classification
        default_flag, reason = compute_default_flag(
            loan['loan_classification'],
            loan['npa_flag'],
            loan['status'],
        )

        # FOIR = EMI / (annual_income / 12); fall back to kyc.foir_declared when income is zero
        # Capped at 0.89 (ref_numeric_constraints max)
        foir = None
        if loan['annual_income'] and loan['annual_income'] > 0 and loan['emi']:
            foir = round(min(float(loan['emi']) / (float(loan['annual_income']) / 12.0), 0.89), 4)
        elif loan['foir_declared']:
            foir = round(min(float(loan['foir_declared']), 0.89), 4)

        cursor.execute("""
            INSERT INTO bank_loan_metrics
                (bank_id, bank_name, loan_id,
                 de_ratio, interest_coverage, profitability, liquidity_ratio,
                 default_flag, pd_observed, observation_date, loaded_at,
                 age, employment_type_enc, years_employed, annual_income,
                 foir, num_dependents, city_tier_enc, education_enc,
                 residence_type_enc,
                 loan_purpose_enc, cibil_score, previous_default_flag,
                 months_as_customer, num_late_payments_past_12m,
                 existing_loans_count, num_existing_products, is_rural,
                 ecs_bounce_count, other_lender_emi_ratio, income_disruption_flag,
                 sector_stress_index, ltv_trend_pct,
                 country_code,
                 gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct,
                 delta_de_ratio, delta_cibil, months_since_origination,
                 exposure_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loan['bank_id'],
            loan['bank_name'],
            lid,
            round(float(loan['de_ratio']),         4),
            round(float(loan['interest_coverage']), 4),
            round(float(loan['profitability']),      4),
            round(float(loan['liquidity_ratio']),    4),
            default_flag,
            round(float(loan['pd_observed']),        6),
            today_str,
            loaded_at,
            loan['age'],
            loan['employment_type_enc'],
            loan['years_employed'],
            loan['annual_income'],
            foir,
            loan['num_dependents'],
            loan['city_tier_enc'],
            loan['education_enc'],
            loan['residence_type_enc'],
            loan['loan_purpose_enc'],
            loan['cibil_score'],
            loan['previous_default_flag'],
            loan['months_as_customer'],
            loan['num_late_payments_past_12m'],
            loan['existing_loans_count'],
            loan['num_existing_products'],
            loan['is_rural'],
            loan['ecs_bounce_count'],
            loan['other_lender_emi_ratio'],
            loan['income_disruption_flag'],
            loan['sector_stress_index'],
            loan['ltv_trend_pct'],
            loan['country_code'],
            loan['gdp_growth_pct'],
            loan['inflation_cpi_pct'],
            loan['policy_rate_pct'],
            loan['unemployment_pct'],
            loan['delta_de_ratio'],
            loan['delta_cibil'],
            loan['months_since_origination'],
            loan['exposure_class'],
        ))

        status = "DEFAULT" if default_flag else "OK    "
        print("  {}  {} | {} | {} | PD={:.4f} | {}".format(
            status, lid, loan['bank_id'],
            loan['customer_name'], loan['pd_observed'], reason
        ))
        inserted += 1

    conn.commit()

    # Step 3: Summary
    cursor.execute("""
        SELECT
            bank_id, bank_name,
            COUNT(*)           AS loans,
            SUM(default_flag)  AS defaults,
            ROUND(AVG(pd_observed), 4) AS avg_pd
        FROM bank_loan_metrics
        GROUP BY bank_id
    """)
    summary = cursor.fetchall()

    conn.close()

    print()
    print("=" * 70)
    print("Sync complete  |  Inserted: {}  |  Skipped (no metrics): {}".format(
        inserted, skipped))
    print()
    print("{:<10} {:<25} {:>6} {:>8} {:>8}".format(
        "bank_id", "bank_name", "loans", "defaults", "avg_pd"))
    print("-" * 65)
    for r in summary:
        print("{:<10} {:<25} {:>6} {:>8} {:>8}".format(
            r['bank_id'], r['bank_name'], r['loans'], r['defaults'], r['avg_pd']))
    print("=" * 70)


if __name__ == "__main__":
    sync()
