"""
loan_booking.py
────────────────
Books an APPROVED RM case as a real loan in the originating bank's ledger.

Before this module existed, "approving" a case (backend/rm_case_store.py's
_finalise) only flipped rm_cases.state/final_decision - no loans/accounts/
credit_risk_metrics/bank_loan_metrics row was ever created, and no bank's
balance sheet ever moved. book_loan() is called from _finalise() exactly
once, only when final_decision == "APPROVE".

Uses the model's own assessed PD (M["pd"]["point"]) as the loan's pd_score -
that's the actual point of having run the assessment, not a re-derived
risk-formula value. A freshly booked loan is always default_flag=0,
loan_classification='Standard' (it hasn't defaulted yet).

Reuses the row shapes from operations/scripts/add_new_customers.py (the
established pattern for inserting a full customer+loan set) but only
creates customer/kyc/account rows when the applicant doesn't already exist
at the originating bank - an existing customer's second loan only adds
loans + credit_risk_metrics + bank_loan_metrics.
"""
import json
import os
from datetime import date, datetime, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EMP_LABELS = ['GOVT', 'SALARIED', 'RETIRED', 'SELF_EMPLOYED', 'BUSINESS', 'FREELANCE', 'STUDENT']
EDU_LABELS = ['PHD', 'PROFESSIONAL', 'POST_GRADUATE', 'GRADUATE', 'DIPLOMA', 'HIGH_SCHOOL']
RES_LABELS = ['OWNED', 'RENTED', 'FAMILY', 'EMPLOYER']
PURPOSE_LABELS = {
    1: 'HOME_PURCHASE', 2: 'RENOVATION', 3: 'VEHICLE', 4: 'PERSONAL', 5: 'BUSINESS',
    6: 'EDUCATION', 7: 'MEDICAL', 8: 'DEBT_CONSOLIDATION', 9: 'WEDDING', 10: 'OTHER',
}


def _load_sim_clock():
    """Same frozen-simulation-clock convention as app.py's _load_sim_clock() -
    duplicated locally (rather than imported from app.py) to avoid a
    backend-module -> app.py circular import."""
    try:
        with open(os.path.join(_ROOT, 'simulation_clock.json')) as f:
            clk = json.load(f)
        return clk['sim_date'], clk.get('sim_period', 'FY2020')
    except Exception:
        return '2020-03-31', 'FY2020'


def emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0 or months <= 0:
        return round(principal / max(months, 1), 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def _next_id(conn, table, id_col, prefix):
    row = conn.execute(
        f"SELECT MAX(CAST(SUBSTR({id_col}, {len(prefix) + 1}) AS INTEGER)) "
        f"FROM {table} WHERE {id_col} LIKE ?", (prefix + '%',)
    ).fetchone()
    return (row[0] or 0) + 1


def _ensure_loan_columns(conn):
    """Phase 3 — self-migrating ALTER TABLE, same defensive pattern used
    elsewhere in this codebase (see sync_bank_loan_metrics.py). Adds the
    columns that let a booked loan durably record which RWA approach and
    seniority tier it was originated under - previously the RM's AIRB/
    Standardized choice on borrower-info.html and the seniority tier were
    both computed live for the assessment, then discarded at booking time
    (see this session's investigation into where 'calcMode' went)."""
    for col in ('rwa_approach TEXT', 'seniority TEXT'):
        try:
            conn.execute(f"ALTER TABLE loans ADD COLUMN {col}")
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                raise
    # months_in_residence (Phase 4 schema growth - Bank of Punjab onboarding
    # analysis) - defensive here too so book_loan() doesn't depend on
    # sync_bank_loan_metrics.py having run first on a given bank.db.
    try:
        conn.execute("ALTER TABLE bank_loan_metrics ADD COLUMN months_in_residence REAL")
    except Exception as e:
        if 'duplicate column' not in str(e).lower():
            raise


# borrower-info.html's calcMode radio -> a single definitive approach a
# booked loan is treated under going forward. 'both' was a same-screen
# AIRB-vs-SA comparison tool at assessment time (see this session's earlier
# investigation) with no representable "both" state once the loan is on
# the books - it resolves to the regulator-conservative default,
# Standardized, rather than silently picking AIRB.
_METHODOLOGY_MAP = {'airb': 'AIRB', 'standardized': 'STANDARDIZED', 'both': 'STANDARDIZED'}


def book_loan(conn, case_row):
    """
    Book the approved case's loan into its originating bank's ledger.

    Args:
        conn: sqlite3 connection (bank.db)
        case_row: the rm_cases row dict (must include machine_json)

    Returns:
        dict {loan_id, customer_id, bank_id, created_customer} on success,
        or None if there's no bank_id to book against (legacy/incomplete case -
        skipped, not an error, since older cases predate bank capture).
    """
    M = json.loads(case_row['machine_json'])
    app_ = M['application']
    bank_id = app_.get('bank_id')
    if not bank_id:
        print(f"[loan_booking] Skipping booking for {case_row['case_id']}: no bank_id on case.")
        return None

    sim_date, sim_period = _load_sim_clock()
    cur = conn.cursor()
    _ensure_loan_columns(conn)

    bank_row = cur.execute("SELECT bank_name, country_code FROM banks WHERE bank_id=?", (bank_id,)).fetchone()
    if not bank_row:
        print(f"[loan_booking] Skipping booking for {case_row['case_id']}: unknown bank_id '{bank_id}'.")
        return None
    bank_name, country_code = bank_row

    branch_row = cur.execute("SELECT branch_id, ifsc_code FROM branches WHERE bank_id=? LIMIT 1", (bank_id,)).fetchone()
    branch_id, ifsc = branch_row if branch_row else (f"BR-{bank_id}-001", f"{bank_id}0000001")

    customer_id = app_.get('customer_id')
    created_customer = False
    cid = None
    if customer_id:
        existing = cur.execute(
            "SELECT id FROM customers WHERE id=? AND bank_id=?", (customer_id, bank_id)
        ).fetchone()
        if existing:
            cid = existing[0]

    if cid is None:
        # Brand-new applicant (or customer_id belongs to a different bank) -
        # create a real, permanent customer relationship at this bank so the
        # loan has somewhere to live - this is the necessary consequence of
        # the loan actually existing on the bank's books.
        created_customer = True
        idx = _next_id(conn, 'customers', 'id', 'CUST')
        cid = f"CUST{idx}"
        first_last = (app_.get('customer_name') or 'New Applicant').split(' ', 1)
        first = first_last[0]
        last = first_last[1] if len(first_last) > 1 else ''
        age = int(app_.get('age') or app_.get('applicant_age') or 35)

        cur.execute(
            "INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, bank_id, first, last, f"{date.today().year - age}-01-01", 'Unspecified',
             f"{cid.lower()}@example.com", '9000000000', 'N/A', 'N/A', 'N/A', '000000',
             sim_date, 'Active'))

        aid = f"ACC-{cid}"
        opening_balance = round(float(app_.get('annual_income') or 0) / 12.0, 2) or 10000.0
        cur.execute(
            "INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (aid, bank_id, cid, 'Savings', opening_balance, sim_date, branch_id, ifsc, 'Active'))
        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (f"TX-{cid}-OPEN", bank_id, aid, sim_date, '10:00:00', 'Deposit',
             opening_balance, opening_balance, '[INCOME] Opening deposit - account funded'))

        emp_enc = int(app_.get('employment_type_enc') or 2)
        edu_enc = int(app_.get('education_enc') or 4)
        res_enc = int(app_.get('residence_type_enc') or 2)
        purpose_enc = int(app_.get('loan_purpose_enc') or 4)
        now = datetime.now().isoformat(timespec='seconds')
        cur.execute(
            "INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,age,gender,"
            "marital_status,education_level,num_dependents,employment_type,employer_name,industry_sector,"
            "years_employed,annual_income,other_income,foir_declared,residence_type,years_at_address,city_tier,"
            "is_pep,risk_category,created_at,updated_at,months_as_customer,num_existing_products,existing_loans_count,"
            "loan_purpose,previous_default_flag,cibil_score,num_late_payments_past_12m,state,is_rural) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, bank_id, 1, 1, app_.get('kyc_status', 'Verified'), sim_date,
             age, 'Unspecified', 'UNSPECIFIED',
             EDU_LABELS[edu_enc - 1] if 1 <= edu_enc <= len(EDU_LABELS) else 'GRADUATE',
             int(app_.get('num_dependents') or 0),
             EMP_LABELS[emp_enc - 1] if 1 <= emp_enc <= len(EMP_LABELS) else 'SALARIED',
             'N/A', 'N/A', float(app_.get('years_employed') or 0), float(app_.get('annual_income') or 0), 0,
             float(app_.get('foir') or 0),
             RES_LABELS[res_enc - 1] if 1 <= res_enc <= len(RES_LABELS) else 'RENTED',
             # years_at_address - was hardcoded 0 (never actually populated by
             # the live booking path, unlike the historical seeders which do
             # populate it with real varied values - see feature_meta.py's
             # months_in_residence default for why 82 months/~6.8yr, not 0).
             float(app_.get('months_in_residence') or 82.0) / 12.0,
             int(app_.get('city_tier_enc') or 2), 1 if app_.get('pep_flag') else 0,
             'HIGH' if float(M['pd']['point']) > 0.1 else 'LOW', now, now,
             int(app_.get('months_as_customer') or 0), int(app_.get('num_existing_products') or 1),
             int(app_.get('existing_loans_count') or 0),
             PURPOSE_LABELS.get(purpose_enc, 'PERSONAL'),
             int(app_.get('previous_default_flag') or 0), int(app_.get('cibil_score') or 700),
             int(app_.get('num_late_payments_past_12m') or 0), 'N/A', int(app_.get('is_rural') or 0)))

    # ── Loan facility ────────────────────────────────────────────────────────
    lid_idx = _next_id(conn, 'loans', 'id', 'RM-LN-')
    lid = f"RM-LN-{lid_idx:06d}"
    principal = float(app_.get('requested_amount') or app_.get('exposure') or 0)
    rate = float((M.get('pricing') or {}).get('indicative_rate_pct') or 12.0)
    tenure_months = max(1, int(round(float(app_.get('tenure_years') or 3) * 12)))
    loan_emi = emi(principal, rate, tenure_months)
    maturity = (date.fromisoformat(sim_date) + timedelta(days=tenure_months * 30.44)).isoformat()
    exposure_class = app_.get('exposure_class')
    product = app_.get('product', 'Personal Loan')
    ltv_ratio = app_.get('ltv_ratio')
    ltv_ratio = float(ltv_ratio) if ltv_ratio not in (None, '') else None
    rwa_approach = _METHODOLOGY_MAP.get(
        (app_.get('calculation_methodology') or 'standardized').lower(), 'STANDARDIZED')
    seniority = app_.get('seniority') or 'Senior Unsecured'

    cur.execute(
        "INSERT INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,maturity,outstanding,status,branch_id,loan_classification,exposure_class,ltv_ratio,rwa_approach,seniority) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (lid, bank_id, cid, product, principal, rate, tenure_months, loan_emi,
         sim_date, maturity, principal, 'Active', branch_id, 'Standard', exposure_class, ltv_ratio,
         rwa_approach, seniority))

    # ── Collateral (Phase 2 — collateral_register, see backend/collateral_store.py) ──
    # Previously discarded entirely: collateral_type/collateral_value were
    # captured on borrower-info.html and used for the live LGD calc at
    # assessment time, but book_loan() never wrote them anywhere (same
    # discard pattern the AIRB/SA methodology flag had). An unsecured loan
    # (no collateral_type/value on the application) correctly gets no row.
    from backend import collateral_store as _collateral
    _collateral.record_collateral(
        conn, lid, bank_id,
        collateral_type=app_.get('collateral_type'),
        collateral_value=app_.get('collateral_value'),
        valuation_date=sim_date,
        ltv_ratio=ltv_ratio,
        source='origination',
    )

    # Phase 4 — link this loan back to the prediction_store row that assessed
    # it (report_id lives on M, set when the case was created), so a booked
    # loan's PD/rating/RWA at origination stays queryable by loan_id.
    report_id = M.get('report_id')
    if report_id:
        from backend import prediction_store as _prediction
        _prediction.link_to_loan(conn, report_id, lid)

    # ── Risk metrics (this loan's own row) ──────────────────────────────────
    de = float(app_.get('de_ratio') or 0)
    ic = float(app_.get('interest_coverage') or 0)
    profit = float(app_.get('profitability') or 0)
    liq = float(app_.get('liquidity_ratio') or 0)
    cibil = int(app_.get('cibil_score') or 700)
    pd_score = float(M['pd']['point'])

    cur.execute(
        "INSERT INTO credit_risk_metrics (bank_id,lid,de,intcov,profit,liq,df,pd_score,npa_flag,period,obs,prior_de,prior_cibil) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (bank_id, lid, de, ic, profit, liq, 0, round(pd_score, 4), 0, sim_period, sim_date, de, cibil))

    # ── PD-training source row ───────────────────────────────────────────────
    macro = cur.execute(
        "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct "
        "FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1", (country_code,)
    ).fetchone() or (6.7, 4.5, 6.25, 7.6)

    cur.execute(
        "INSERT INTO bank_loan_metrics (bank_id,bank_name,loan_id,de_ratio,interest_coverage,profitability,"
        "liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,age,employment_type_enc,"
        "years_employed,annual_income,foir,num_dependents,months_in_residence,city_tier_enc,education_enc,residence_type_enc,"
        "loan_purpose_enc,cibil_score,previous_default_flag,months_as_customer,num_late_payments_past_12m,"
        "existing_loans_count,num_existing_products,is_rural,country_code,exposure_class,"
        "gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct,"
        "delta_de_ratio,delta_cibil,months_since_origination) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (bank_id, bank_name, lid, de, ic, profit, liq, 0, round(pd_score, 4), sim_date,
         datetime.now().isoformat(timespec='seconds'),
         int(app_.get('age') or app_.get('applicant_age') or 35),
         int(app_.get('employment_type_enc') or 2), float(app_.get('years_employed') or 0),
         float(app_.get('annual_income') or 0), float(app_.get('foir') or 0),
         int(app_.get('num_dependents') or 0), float(app_.get('months_in_residence') or 82.0),
         int(app_.get('city_tier_enc') or 2),
         int(app_.get('education_enc') or 4), int(app_.get('residence_type_enc') or 2),
         int(app_.get('loan_purpose_enc') or 4), cibil,
         int(app_.get('previous_default_flag') or 0), int(app_.get('months_as_customer') or 0),
         int(app_.get('num_late_payments_past_12m') or 0), int(app_.get('existing_loans_count') or 0),
         int(app_.get('num_existing_products') or 1), int(app_.get('is_rural') or 0), country_code, exposure_class,
         macro[0], macro[1], macro[2], macro[3], 0.0, 0.0, 0.0))

    # ── Balance sheet impact - the whole point of this feature ──────────────
    # advances_net is a stored snapshot (see plan investigation) that does NOT
    # auto-recompute from live `loans` the way RWA/capital ratios do, so it
    # must be incremented explicitly for the new loan to show up in the
    # bank's balance sheet / capital base / liquidity ratios. Where that
    # funding actually comes FROM (deposits / borrowings / drawing down
    # spare investments) is the ALCO function's job, not a silent asset-only
    # bump - see backend/alm_engine.decide_funding().
    from backend import alm_engine as _alm
    funding = _alm.decide_funding(conn, bank_id, sim_period, principal, loan_id=lid)

    conn.commit()
    return {'loan_id': lid, 'customer_id': cid, 'bank_id': bank_id, 'created_customer': created_customer,
            'funding_source': funding['source'], 'funding_reason': funding['reason']}
