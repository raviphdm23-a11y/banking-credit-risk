"""
seed_training_from_simulation.py
──────────────────────────────────
Builds a training-ready CSV from the Axis Bank simulation outcomes.

Two actions:
  1. Updates default_flag in existing bank_loan_metrics rows (3,800) to reflect
     actual NPA outcomes that materialised during the COVID simulation.
  2. Generates new feature-complete rows for loans disbursed during the
     simulation (APR–NOV 2020) — these carry real COVID-era default labels.

Output: data/training/axis_bank_covid_2020.csv
        (~4,000+ rows; combined updated existing + new simulation loans)

Feature synthesis for new loans:
  Financial ratios   — estimated from loan amount, rate, type
  Bureau features    — estimated from loan terms and NPA status
  Macro features     — from country_macro table (India FY2020/FY2021)
  default_flag       — directly from actual days_past_due / loan_classification

Run: python operations/scripts/seed_training_from_simulation.py
"""

import os, sys, csv, sqlite3, random
from datetime import date, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
OUT_DIR  = os.path.join(_REPO_ROOT, 'data', 'training')
OUT_FILE = os.path.join(OUT_DIR, 'axis_bank_covid_2020.csv')

BANK_ID   = 'BANK010'
OBS_DATE  = '2020-11-30'   # observation point = end of simulation

FEATURES = [
    'de_ratio','interest_coverage','profitability','liquidity_ratio',
    'age','employment_type_enc','years_employed','annual_income','foir',
    'num_dependents','city_tier_enc','education_enc','residence_type_enc',
    'loan_purpose_enc','cibil_score','previous_default_flag',
    'months_as_customer','num_late_payments_past_12m','existing_loans_count',
    'num_existing_products','gdp_growth_pct','inflation_cpi_pct',
    'policy_rate_pct','unemployment_pct','delta_de_ratio','delta_cibil',
    'months_since_origination',
    # Macro regime delta features (new)
    'delta_gdp_pct','delta_cpi_pct','delta_policy_rate_pct',
    'delta_unemployment_pct','macro_regime_score',
]
TARGET = 'default_flag'


# ── Macro lookup (India) ─────────────────────────────────────────────────────
MACRO_PRE = {
    'gdp_growth_pct':        6.5,
    'inflation_cpi_pct':     4.8,
    'policy_rate_pct':       6.5,
    'unemployment_pct':      7.8,
    'delta_gdp_pct':         0.0,
    'delta_cpi_pct':         0.0,
    'delta_policy_rate_pct': 0.0,
    'delta_unemployment_pct':0.0,
    'macro_regime_score':    0.0,
}
# COVID period: GDP -7.3%, deltas vs CY2019 baseline
# dGDP = -7.3 - 6.5 = -13.8pp, dUnemp = +3.6, dRate = -2.5, dCPI = +1.4
# MRS = min(1, 13.8/12)*40 + min(1, 3.6/6)*30 + min(1, 2.5/3)*15 + min(1, 1.4/4)*15
#      = 40 + 18 + 12.5 + 5.25 = 75.75
MACRO_COVID = {
    'gdp_growth_pct':        -7.3,
    'inflation_cpi_pct':      6.2,
    'policy_rate_pct':        4.0,
    'unemployment_pct':      11.4,
    'delta_gdp_pct':        -13.8,
    'delta_cpi_pct':          1.4,
    'delta_policy_rate_pct': -2.5,
    'delta_unemployment_pct': 3.6,
    'macro_regime_score':    75.8,
}


def _is_npa(row):
    return (row.get('days_past_due', 0) or 0) >= 90 or \
           (row.get('loan_classification','') or '') in \
           ('Sub-Standard','Doubtful-1','Doubtful-2','Loss')


def _months_between(d1_str, d2_str):
    try:
        d1 = date.fromisoformat(d1_str[:10])
        d2 = date.fromisoformat(d2_str[:10])
        return max(0, (d2.year - d1.year)*12 + (d2.month - d1.month))
    except Exception:
        return 12


def _age(dob_str):
    try:
        dob = date.fromisoformat(dob_str[:10])
        obs = date.fromisoformat(OBS_DATE)
        return (obs - dob).days // 365
    except Exception:
        return 35


def _city_tier(city):
    tier1 = {'mumbai','delhi','bangalore','hyderabad','chennai','kolkata','pune','ahmedabad'}
    tier2 = {'jaipur','lucknow','surat','nagpur','patna','bhopal','chandigarh','coimbatore','indore'}
    c = (city or '').lower()
    if c in tier1: return 1
    if c in tier2: return 2
    return 3


def _loan_purpose_enc(ltype):
    mapping = {
        'Home Loan': 1, 'Vehicle Loan': 2, 'Business Loan': 3,
        'Personal Loan': 4, 'Education Loan': 5,
    }
    return mapping.get(ltype, 3)


def _employment_type(ltype):
    # 1=Salaried, 2=Self-Employed/Business; trainer valid range [1,7]
    return 2 if ltype == 'Business Loan' else 1


def _synthesise_features(loan, cust, is_npa, rng):
    """Generate all 27 features for a simulation loan row."""
    ltype     = loan.get('type', 'Business Loan')
    principal = loan.get('principal', 500_000) or 500_000
    rate      = loan.get('rate', 11.0) or 11.0
    tenure    = loan.get('tenure', 48) or 48
    disbursed = loan.get('disbursed', '2020-04-01') or '2020-04-01'
    otr       = loan.get('otr_restructured', 0) or 0
    morat_cat = loan.get('moratorium_category') or ''
    source    = loan.get('source', '') or ''

    months_orig = _months_between(disbursed, OBS_DATE)

    # ── Financial ratios (proxy from loan characteristics) ────────────────
    if is_npa:
        # Stressed borrower: high debt, low coverage, negative profitability
        de_ratio          = round(rng.uniform(3.5, 8.0), 2)
        interest_coverage = round(rng.uniform(0.5, 1.8), 2)
        profitability     = round(rng.uniform(-0.15, 0.02), 3)
        liquidity_ratio   = round(rng.uniform(0.4, 0.9), 2)
    elif otr:
        # OTR: restructured but still performing — moderate stress
        de_ratio          = round(rng.uniform(2.0, 4.5), 2)
        interest_coverage = round(rng.uniform(1.2, 2.5), 2)
        profitability     = round(rng.uniform(-0.03, 0.05), 3)
        liquidity_ratio   = round(rng.uniform(0.9, 1.4), 2)
    else:
        # Standard performing
        de_ratio          = round(rng.uniform(0.5, 2.5), 2)
        interest_coverage = round(rng.uniform(2.5, 6.0), 2)
        profitability     = round(rng.uniform(0.05, 0.20), 3)
        liquidity_ratio   = round(rng.uniform(1.2, 3.0), 2)

    # ── Bureau / borrower features ─────────────────────────────────────────
    age = _age(cust.get('dob', '1985-01-01'))

    emp_type = _employment_type(ltype)
    years_emp = rng.randint(2, 20) if not is_npa else rng.randint(1, 8)

    # Annual income: back-calculate from EMI capacity
    # EMI = principal * rate/12 / (1 - (1+r)^-n)
    r_m = rate / 100 / 12
    if r_m > 0:
        emi = principal * r_m * (1+r_m)**tenure / ((1+r_m)**tenure - 1)
    else:
        emi = principal / tenure
    foir = round(rng.uniform(0.30, 0.55) if not is_npa else rng.uniform(0.55, 0.75), 2)
    annual_income = round(emi * 12 / foir, 0)

    num_dependents = rng.randint(0, 4)
    city_tier      = _city_tier(cust.get('city', ''))
    education_enc  = rng.choices([1,2,3,4], weights=[10,20,40,30])[0]
    residence_type = rng.choices([1,2,3], weights=[40,45,15])[0]  # own/rent/parental
    loan_purpose   = _loan_purpose_enc(ltype)

    if is_npa:
        cibil_score = rng.randint(300, 620)
        prev_def    = rng.choices([0,1], weights=[50,50])[0]
        late_pay    = rng.randint(3, 12)
    elif otr:
        cibil_score = rng.randint(580, 700)
        prev_def    = rng.choices([0,1], weights=[70,30])[0]
        late_pay    = rng.randint(1, 5)
    elif morat_cat == 'R':
        cibil_score = rng.randint(550, 670)
        prev_def    = 0
        late_pay    = rng.randint(0, 3)
    else:
        cibil_score = rng.randint(680, 820)
        prev_def    = 0
        late_pay    = rng.randint(0, 2)

    # ECLGS loans had no prior credit issues (guaranteed)
    if 'ECLGS' in source:
        cibil_score = max(cibil_score, 650)
        late_pay    = min(late_pay, 2)

    months_as_cust   = _months_between(cust.get('joined','2018-01-01'), OBS_DATE)
    existing_loans   = rng.randint(0, 3) if not is_npa else rng.randint(1, 5)
    num_products     = rng.randint(1, 4)
    is_rural         = 1 if city_tier == 3 else 0

    # ── Macro regime (COVID vs pre-COVID) ─────────────────────────────────
    macro = MACRO_COVID if disbursed >= '2020-04-01' else MACRO_PRE

    # ── Trend features ─────────────────────────────────────────────────────
    delta_de    = round(rng.uniform( 0.1, 1.5) if is_npa else rng.uniform(-0.2, 0.3), 2)
    delta_cibil = round(rng.uniform(-60, -10)  if is_npa else rng.uniform(-15, 20),   1)

    return {
        'de_ratio':                  de_ratio,
        'interest_coverage':         interest_coverage,
        'profitability':             profitability,
        'liquidity_ratio':           liquidity_ratio,
        'age':                       age,
        'employment_type_enc':       emp_type,
        'years_employed':            years_emp,
        'annual_income':             annual_income,
        'foir':                      foir,
        'num_dependents':            num_dependents,
        'city_tier_enc':             city_tier,
        'education_enc':             education_enc,
        'residence_type_enc':        residence_type,
        'loan_purpose_enc':          loan_purpose,
        'cibil_score':               cibil_score,
        'previous_default_flag':     prev_def,
        'months_as_customer':        months_as_cust,
        'num_late_payments_past_12m':late_pay,
        'existing_loans_count':      existing_loans,
        'num_existing_products':     num_products,
        'gdp_growth_pct':            macro['gdp_growth_pct'],
        'inflation_cpi_pct':         macro['inflation_cpi_pct'],
        'policy_rate_pct':           macro['policy_rate_pct'],
        'unemployment_pct':          macro['unemployment_pct'],
        'delta_de_ratio':            delta_de,
        'delta_cibil':               delta_cibil,
        'months_since_origination':  months_orig,
        'delta_gdp_pct':             macro['delta_gdp_pct'],
        'delta_cpi_pct':             macro['delta_cpi_pct'],
        'delta_policy_rate_pct':     macro['delta_policy_rate_pct'],
        'delta_unemployment_pct':    macro['delta_unemployment_pct'],
        'macro_regime_score':        macro['macro_regime_score'],
    }


def run(db_path=DB_PATH, verbose=True):
    rng = random.Random(42)
    os.makedirs(OUT_DIR, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def p(msg):
        if verbose:
            print(msg)

    p('\n' + '='*60)
    p('  Building COVID simulation training dataset for BANK010')
    p('='*60)

    # ── Part A: Update existing bank_loan_metrics default_flags ──────────────
    p('\n[A] Updating default_flag in existing bank_loan_metrics rows...')

    npa_cids = {r[0] for r in conn.execute(
        "SELECT DISTINCT cid FROM loans WHERE bank_id=? AND ("
        "  days_past_due >= 90 OR "
        "  loan_classification IN ('Sub-Standard','Doubtful-1','Doubtful-2','Loss'))",
        (BANK_ID,)).fetchall()}

    cur = conn.cursor()
    cur.execute(
        "UPDATE bank_loan_metrics SET default_flag=1 WHERE bank_id=? AND loan_id IN "
        "(SELECT id FROM loans WHERE bank_id=? AND ("
        "  days_past_due >= 90 OR "
        "  loan_classification IN ('Sub-Standard','Doubtful-1','Doubtful-2','Loss')))",
        (BANK_ID, BANK_ID))
    updated = cur.rowcount
    conn.commit()
    p(f'    Updated {updated} rows to default_flag=1 (actual NPA)')
    p(f'    {len(npa_cids)} unique customers with NPA loans')

    # ── Part B: Export full bank_loan_metrics as base dataset ────────────────
    p('\n[B] Exporting bank_loan_metrics as base training rows...')
    base_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM bank_loan_metrics WHERE bank_id=?", (BANK_ID,)).fetchall()]
    p(f'    {len(base_rows)} base rows  |  '
      f'defaults: {sum(1 for r in base_rows if r["default_flag"])}')

    # ── Part C: Generate new rows for simulation loans (APR-NOV 2020) ────────
    p('\n[C] Generating feature rows for simulation loans...')

    # All loans created during simulation (identified by source field containing month codes)
    sim_sources = (
        'apr2020', 'may2020', 'jun2020', 'jul2020',
        'aug2020', 'sep2020', 'oct2020', 'nov2020',
    )
    source_filter = ' OR '.join([f"source LIKE '%{s}%'" for s in sim_sources])

    sim_loans = [dict(r) for r in conn.execute(
        f"SELECT l.*, c.dob, c.gender, c.city, c.state, c.joined, c.id as cust_id "
        f"FROM loans l JOIN customers c ON l.cid=c.id "
        f"WHERE l.bank_id=? AND ({source_filter})",
        (BANK_ID,)).fetchall()]

    p(f'    Found {len(sim_loans)} simulation-period loans')

    sim_rows = []
    npa_count = 0
    for loan in sim_loans:
        is_npa = _is_npa(loan)
        if is_npa:
            npa_count += 1
        cust = {'dob': loan['dob'], 'city': loan['city'],
                'joined': loan['joined'], 'gender': loan['gender']}
        feats = _synthesise_features(loan, cust, is_npa, rng)
        feats[TARGET] = 1 if is_npa else 0
        sim_rows.append(feats)

    p(f'    Generated {len(sim_rows)} rows  |  defaults: {npa_count} ({npa_count/max(len(sim_rows),1)*100:.1f}%)')

    # ── Part D: Write CSV (simulation-period loans only) ─────────────────────
    # The trainer reads bank_loan_metrics from the DB directly — do NOT duplicate
    # those 3800 rows in the CSV or the trainer deduplicator will eat the synthetic.
    # This CSV contributes only the new simulation loans (APR–NOV 2020 disbursals).
    p(f'\n[D] Writing simulation-period rows to {OUT_FILE}...')

    required_meta = ['bank_id', 'loan_id', 'observation_date', 'is_rural']
    fieldnames = required_meta + FEATURES + [TARGET]
    written = 0

    with open(OUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for i, row in enumerate(sim_rows):
            row['bank_id']          = BANK_ID
            row['loan_id']          = f'SIM-{i+1:04d}'
            row['observation_date'] = OBS_DATE
            row['is_rural'] = 1 if row.get('city_tier_enc', 3) == 3 else 0
            writer.writerow(row)
            written += 1

    p(f'    Wrote {written} simulation rows  |  {npa_count} defaults ({npa_count/max(written,1)*100:.1f}% default rate)')
    p(f'    (bank_loan_metrics base rows are read from DB by trainer — not duplicated here)')
    p(f'    Updated {updated} bank_loan_metrics rows with actual NPA outcomes')

    conn.close()

    p('\n' + '='*60)
    p('  Dataset ready. Run trainer next:')
    p('  POST http://localhost:5000/admin/api/train  (X-Admin-Password: 1234)')
    p('  or:  python ml_models/trainer.py')
    p('='*60)

    return OUT_FILE


if __name__ == '__main__':
    run()
