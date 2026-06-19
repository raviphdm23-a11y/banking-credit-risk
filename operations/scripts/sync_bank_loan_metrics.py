"""
sync_bank_loan_metrics.py
─────────────────────────
End-of-day job: derives bank_loan_metrics from actual customer loan data
stored across customers / loans / accounts / transactions /
credit_risk_metrics / customer_kyc / ref_lookup.

Default rule (RBI 90-day NPA aligned):
  A loan is flagged default_flag = 1 if ANY of the following:
    1. loans.loan_classification is 'NPA', 'Doubtful', or 'Loss'
    2. credit_risk_metrics.npa_flag = 1
    3. The last 3 consecutive expected EMI months have no EMI transaction
       recorded in the transactions table for that customer's account.

KYC features (risk-ordered integer encoding via ref_lookup.risk_order):
  employment_type_enc, city_tier_enc, education_enc, residence_type_enc

Run:
    python sync_bank_loan_metrics.py
"""

import os
import sqlite3
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')


# ─────────────────────────────────────────────────────────────────────────────
# EMI default detection
# ─────────────────────────────────────────────────────────────────────────────

def expected_emi_months(disbursed_str, tenure):
    """
    Return a list of (year, month) tuples for every month an EMI was due,
    from the month after disbursement up to today.
    """
    disbursed = datetime.strptime(disbursed_str, '%Y-%m-%d').date()
    today     = date.today()

    y, m = disbursed.year, disbursed.month
    m += 1
    if m > 12:
        m, y = 1, y + 1

    months = []
    for _ in range(tenure):
        if date(y, m, 1) > today:
            break
        months.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    return months


def paid_emi_months(loan_id, cursor):
    """
    Return a set of (year, month) in which an EMI payment transaction exists
    for the customer who holds this loan.
    """
    cursor.execute("""
        SELECT DISTINCT
            CAST(strftime('%Y', t.date) AS INTEGER) AS yr,
            CAST(strftime('%m', t.date) AS INTEGER) AS mo
        FROM transactions t
        JOIN accounts   a ON a.id  = t.aid
        JOIN loans      l ON l.cid = a.cid AND l.id = ?
        WHERE t.desc LIKE '%EMI Payment%'
    """, (loan_id,))
    return {(row[0], row[1]) for row in cursor.fetchall()}


def compute_default_flag(loan_id, disbursed, tenure, classification,
                          npa_flag, cursor):
    """
    Apply the three-tier default rule. Returns (flag: int, reason: str).
    """
    # Rule 1: explicit adverse loan classification
    if classification in ('NPA', 'Doubtful', 'Loss'):
        return 1, 'loan_classification = {}'.format(classification)

    # Rule 2: NPA flag set in credit risk metrics
    if npa_flag:
        return 1, 'npa_flag = 1 in credit_risk_metrics'

    # Rule 3: 3 consecutive missed EMIs (RBI 90-day rule)
    expected = expected_emi_months(disbursed, tenure)

    if len(expected) < 3:
        # Loan too new — fewer than 3 EMIs have fallen due yet
        return 0, 'loan too recent (only {} EMI months elapsed)'.format(len(expected))

    paid    = paid_emi_months(loan_id, cursor)
    last_3  = expected[-3:]
    missed  = [m for m in last_3 if m not in paid]

    if len(missed) == 3:
        labels = ['{}-{:02d}'.format(y, m) for y, m in last_3]
        return 1, '3 consecutive missed EMIs: {}'.format(', '.join(labels))

    paid_count = 3 - len(missed)
    return 0, 'performing — {}/3 recent EMIs paid'.format(paid_count)


# ─────────────────────────────────────────────────────────────────────────────
# Main sync
# ─────────────────────────────────────────────────────────────────────────────

def sync(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today_str  = date.today().isoformat()
    loaded_at  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("=" * 70)
    print("bank_loan_metrics sync — {}".format(today_str))
    print("=" * 70)

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

            -- Country
            b.country_code

        FROM loans l
        JOIN banks                  b       ON b.bank_id      = l.bank_id
        JOIN customers              c       ON c.id           = l.cid
        LEFT JOIN credit_risk_metrics crm   ON crm.lid        = l.id
        LEFT JOIN customer_kyc      kyc     ON kyc.cid        = l.cid
                                           AND kyc.bank_id    = l.bank_id
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

        # Compute default flag using the 3-rule hierarchy
        default_flag, reason = compute_default_flag(
            lid,
            loan['disbursed'],
            loan['tenure'],
            loan['loan_classification'],
            loan['npa_flag'],
            cursor
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
                 country_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            loan['country_code'],
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
