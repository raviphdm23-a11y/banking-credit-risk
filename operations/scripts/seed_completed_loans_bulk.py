"""
seed_completed_loans_bulk.py
─────────────────────────────
Large-scale generator of completed loans (Closed/Written-Off) per Basel
segment, sized to push EPV (events-per-variable) toward the "acceptable"
floor of 10 while keeping this batch's own Written-Off rate realistic
(~10-15%) - see the conversation this was sized from.

v2 (this version) replaces v1's deterministic "decide the outcome, then pick
matching feature ranges" approach with a probabilistic one, for two reasons
raised in review:
  1. Deterministic disjoint good/bad ranges made CIBIL alone (and the full
     model) hit AUC ~0.95-1.0 - unrealistically clean separability that no
     real credit portfolio has.
  2. Five new "other circumstances" attributes were added (ECS/NACH bounce
     count, other-lender exposure, an income-disruption shock flag, an
     industry-sector stress index, and collateral LTV drift for mortgages)
     so the model isn't purely CIBIL-driven.

Generation model (a latent risk score + idiosyncratic shock, the same
structure real structural default models use):
  1. Every loan's profile (CIBIL, D/E, ICR, profitability, liquidity, FOIR,
     late payments, previous default, ECS bounces, other-lender exposure,
     income disruption, sector stress, LTV trend) is drawn from a SINGLE
     population distribution - not two disjoint good/bad distributions.
  2. A continuous risk_z score is computed as a weighted combination of
     those features (standardized), PLUS a Gaussian idiosyncratic shock -
     this shock term *is* the residual "unknown factor" that no dataset can
     capture, injected at the point where the outcome is generated rather
     than bolted onto the model afterward.
  3. risk_z is passed through a logistic function (intercept calibrated at
     runtime via calibrate_intercept() to hit the target average default
     rate) to get a per-loan default probability, and the actual outcome is
     a Bernoulli draw from that probability - not a deterministic threshold.

This means a low-CIBIL borrower sometimes survives (Closed) and a
high-CIBIL borrower sometimes doesn't (Written-Off) - genuine overlap, by
construction, rather than a clean split.

Since the outcome is now probabilistic rather than pre-assigned, loans are
generated one at a time per (bank, segment) until that pair's Written-Off
quota is met (rather than a fixed pre-computed total), so realized totals
vary slightly from the target math - this is expected and reported at the
end.

Run:
    python operations/scripts/seed_completed_loans_bulk.py [--wo-rate 0.125] [--target-epv 10] [--dry-run]
    Then:
    python operations/scripts/sync_bank_loan_metrics.py
    python operations/scripts/build_behavioral_features.py
"""

import argparse
import json
import math
import os
import random
import sqlite3
from datetime import date, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')
N_FEATURES = 36  # ml_models/trainer.py FEATURE_COLS length (behavioral features excluded from training)

SEGMENTS = ['CORPORATE', 'SME', 'RETAIL_MORTGAGES', 'RETAIL_OTHER']
SEG_CODE = {
    'CORPORATE':         'CORP',
    'SME':                'SME',
    'RETAIL_MORTGAGES':  'RETA',
    'RETAIL_OTHER':      'RETA',
}
LOAN_TYPE_CHOICES = {
    'CORPORATE':         [('Business Loan', 'BUSINESS')],
    'SME':                [('Business Loan', 'BUSINESS')],
    'RETAIL_MORTGAGES':  [('Home Loan', 'HOME_PURCHASE')],
    'RETAIL_OTHER':      [('Education Loan', 'EDUCATION'),
                            ('Personal Loan', 'PERSONAL'),
                            ('Vehicle Loan', 'VEHICLE')],
}
EMPLOYMENT_TYPES = ['SALARIED', 'SELF_EMPLOYED', 'BUSINESS', 'PROFESSIONAL', 'GOVT']
EDUCATION_LEVELS = ['HIGH_SCHOOL', 'DIPLOMA', 'GRADUATE', 'POST_GRADUATE', 'PROFESSIONAL', 'PHD']
RESIDENCE_TYPES  = ['OWNED', 'RENTED', 'FAMILY', 'EMPLOYER']
CITY_TIERS       = ['TIER1', 'TIER2', 'TIER3']
FIRST_NAMES = ['Aarav', 'Vivaan', 'Aditya', 'Ishaan', 'Kabir', 'Ananya', 'Diya',
               'Saanvi', 'Meera', 'Rohan', 'Karan', 'Nisha', 'Priya', 'Arjun',
               'Sanya', 'Rahul', 'Neha', 'Vikram', 'Pooja', 'Amit']
LAST_NAMES = ['Sharma', 'Verma', 'Gupta', 'Iyer', 'Nair', 'Reddy', 'Rao', 'Patel',
              'Mehta', 'Joshi', 'Das', 'Kapoor', 'Malhotra', 'Chatterjee', 'Ghosh']
CITIES = [('Mumbai', 'MH'), ('Bengaluru', 'KA'), ('Delhi', 'DL'), ('Chennai', 'TN'),
          ('Pune', 'MH'), ('Hyderabad', 'TG'), ('Kolkata', 'WB'), ('Ahmedabad', 'GJ')]
TENURE_CHOICES = [24, 36, 48]

PRINCIPAL_RANGES = {
    'CORPORATE':        (2_000_000, 20_000_000),
    'SME':               (300_000,   9_900_000),
    'RETAIL_MORTGAGES': (300_000,   8_800_000),
    'RETAIL_OTHER':     (200_000,   8_000_000),
}
RATE_RANGES = {
    'CORPORATE':        (8.0, 23.5),
    'SME':               (8.51, 15.5),
    'RETAIL_MORTGAGES': (7.62, 17.94),
    'RETAIL_OTHER':     (8.51, 22.42),
}
SECTOR_STRESS_BASE = {
    'IT': 25, 'Finance': 30, 'Healthcare': 25, 'Retail': 45,
    'Services': 45, 'Manufacturing': 50, 'Real Estate': 65, 'N/A': 40,
}
INDUSTRY_SECTORS = list(SECTOR_STRESS_BASE.keys())

# Risk-score weights - no single feature dominates; CIBIL is one signal
# among thirteen, not the whole story.
WEIGHTS = dict(cibil=1.0, de=0.7, ic=0.6, profit=0.5, liq=0.5, foir=0.6,
               late=0.6, prev_default=0.5, ecs=0.7, other_lender=0.6,
               disruption=0.6, sector=0.5, ltv=0.4)
SIGMA_SHOCK = 1.5     # idiosyncratic noise std - the "residual unknown factor"
WRITTEN_OFF_PAID_RATIO = (0.30, 0.60)
CLOSED_PAID_RATIO = 1.0


def _sim_date():
    try:
        with open(os.path.join(_REPO_ROOT, 'simulation_clock.json')) as f:
            return date.fromisoformat(json.load(f)['sim_date'])
    except Exception:
        return date.today()


def _bank_prefix(cur, bank_id):
    row = cur.execute(
        "SELECT id FROM customers WHERE bank_id=? AND id LIKE '%-DEP-%' LIMIT 1", (bank_id,)
    ).fetchone()
    if not row:
        raise RuntimeError(f"No existing DEP customer found for {bank_id} to infer prefix")
    return row[0].split('-DEP-')[0]


def _next_seq(cur, prefix, sep, table, id_col):
    row = cur.execute(
        f"SELECT MAX(CAST(SUBSTR({id_col}, ?) AS INTEGER)) FROM {table} WHERE {id_col} LIKE ?",
        (len(prefix) + len(sep) + 1, prefix + sep + '%')
    ).fetchone()
    return (row[0] or 0) + 1


def calc_emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def add_months(d, months):
    y, m = d.year, d.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, min(d.day, 28))


def sample_profile(rng, exposure_class):
    """Draw one borrower's full feature profile from a SINGLE population
    distribution (not conditioned on outcome) - the overlap between eventual
    Closed and Written-Off borrowers comes from here, not from post-hoc noise."""
    cibil = int(min(900, max(300, round(rng.gauss(700, 75)))))
    de = round(min(9.5, max(0.15, rng.lognormvariate(math.log(1.1), 0.55))), 2)
    ic = round(max(0.1, rng.gauss(4.3, 3.0)), 2)
    profit = round(rng.gauss(6.0, 9.0), 1)
    liq = round(max(0.15, rng.gauss(1.55, 0.55)), 2)
    foir = round(min(0.89, max(0.05, rng.gauss(0.40, 0.16))), 2)
    late = int(min(12, max(0, rng.expovariate(1 / 1.3))))
    prev_default = 1 if rng.random() < 0.07 else 0
    ecs = int(min(12, max(0, rng.expovariate(1 / 0.9))))
    other_lender = round(max(0.0, rng.gauss(0.30, 0.28)), 3)
    disruption = 1 if rng.random() < 0.12 else 0
    sector = rng.choice(INDUSTRY_SECTORS)
    sector_stress = round(min(100, max(0, rng.gauss(SECTOR_STRESS_BASE[sector], 13))), 1)
    ltv_trend = round(rng.gauss(0, 8), 2) if exposure_class == 'RETAIL_MORTGAGES' else 0.0
    return dict(cibil=cibil, de=de, ic=ic, profit=profit, liq=liq, foir=foir, late=late,
                prev_default=prev_default, ecs=ecs, other_lender=other_lender,
                disruption=disruption, sector=sector, sector_stress=sector_stress,
                ltv_trend=ltv_trend)


def risk_z(p, rng, sigma_shock=SIGMA_SHOCK):
    z = 0.0
    z += WEIGHTS['cibil']        * (700 - p['cibil']) / 80.0
    z += WEIGHTS['de']           * (p['de'] - 1.1) / 1.0
    z += WEIGHTS['ic']           * (4.3 - p['ic']) / 3.0
    z += WEIGHTS['profit']       * (6.0 - p['profit']) / 9.0
    z += WEIGHTS['liq']          * (1.55 - p['liq']) / 0.55
    z += WEIGHTS['foir']         * (p['foir'] - 0.40) / 0.16
    z += WEIGHTS['late']         * p['late'] / 1.5
    z += WEIGHTS['prev_default'] * p['prev_default']
    z += WEIGHTS['ecs']          * p['ecs'] / 1.2
    z += WEIGHTS['other_lender'] * p['other_lender'] / 0.30
    z += WEIGHTS['disruption']   * p['disruption']
    z += WEIGHTS['sector']       * (p['sector_stress'] - 45.0) / 20.0
    z += WEIGHTS['ltv']          * (-p['ltv_trend']) / 8.0
    z += rng.gauss(0, sigma_shock)
    return z


def calibrate_intercept(rng, exposure_class, target_rate, n_sim=8000):
    """Numerically find the logistic intercept that makes the average
    default probability across a simulated population equal target_rate,
    rather than hand-picking a magic constant."""
    zs = [risk_z(sample_profile(rng, exposure_class), rng) for _ in range(n_sim)]

    def mean_p(intercept):
        return sum(1.0 / (1.0 + math.exp(-(z + intercept))) for z in zs) / len(zs)

    lo, hi = -10.0, 10.0
    target_logit = math.log(target_rate / (1 - target_rate))
    # Since mean_p is monotonic in intercept, bisect directly.
    for _ in range(40):
        mid = (lo + hi) / 2
        if mean_p(mid) < target_rate:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def compute_targets(cur, wo_rate, target_epv, test_size=0.20):
    """Return {segment: {'target_total_defaults': int, 'current_defaults': int, 'wo_new': int}}."""
    target_total_defaults = math.ceil(target_epv * N_FEATURES / (1 - test_size))
    targets = {}
    for seg in SEGMENTS:
        row = cur.execute(
            "SELECT SUM(CASE WHEN status='Written-Off' THEN 1 ELSE 0 END) "
            "FROM loans WHERE exposure_class=? AND status IN ('Closed','Written-Off')",
            (seg,)
        ).fetchone()
        current_defaults = row[0] or 0
        additional_defaults = max(0, target_total_defaults - current_defaults)
        targets[seg] = {
            'target_total_defaults': target_total_defaults,
            'current_defaults': current_defaults,
            'wo_new': additional_defaults,
        }
    return targets


def _split_across_banks(n, n_banks):
    base, rem = divmod(n, n_banks)
    return [base + (1 if i < rem else 0) for i in range(n_banks)]


def generate_one_loan(bank_id, bank_name, branch_id, ifsc, exposure_class, prefix,
                       cust_seq, loan_seq, acc_seq, intercept, sim_date, rng):
    """Draw one loan's full profile + probabilistic outcome, and return
    (rows_dict, is_wo). Rows are single-element lists per table, concatenated
    by the caller."""
    seg_code = SEG_CODE[exposure_class]
    cid = f"{prefix}-{seg_code}-{cust_seq:04d}"
    lid = f"{prefix}-LN-{seg_code}-{loan_seq:05d}"
    aid = f"ACC-{prefix}-{acc_seq:05d}"

    profile = sample_profile(rng, exposure_class)
    z = risk_z(profile, rng)
    p_default = 1.0 / (1.0 + math.exp(-(z + intercept)))
    is_wo = rng.random() < p_default

    tenure = rng.choice(TENURE_CHOICES)
    months_since_maturity = rng.randint(3, 27)
    maturity_d = add_months(sim_date, -months_since_maturity)
    disbursed_d = add_months(maturity_d, -tenure)

    p_lo, p_hi = PRINCIPAL_RANGES[exposure_class]
    r_lo, r_hi = RATE_RANGES[exposure_class]
    principal = round(rng.uniform(p_lo, p_hi) / 10_000) * 10_000
    rate = round(rng.uniform(r_lo, r_hi), 2)
    emi = calc_emi(principal, rate, tenure)

    if is_wo:
        paid_ratio = rng.uniform(*WRITTEN_OFF_PAID_RATIO)
        outstanding = round(principal * rng.uniform(0.5, 0.75), 2)
        status, classification = 'Written-Off', 'Written-Off'
    else:
        paid_ratio = CLOSED_PAID_RATIO
        outstanding = 0.0
        status, classification = 'Closed', 'Standard'

    n_paid_months = max(1, round(tenure * paid_ratio))
    last_emi_d = add_months(disbursed_d, n_paid_months)

    loan_type, loan_purpose = rng.choice(LOAN_TYPE_CHOICES[exposure_class])
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    city, state = rng.choice(CITIES)
    age = rng.randint(28, 58)
    gender = rng.choice(['Male', 'Female'])
    dob = date(sim_date.year - age, rng.randint(1, 12), rng.randint(1, 28)).isoformat()
    emp_type = rng.choice(EMPLOYMENT_TYPES)
    edu = rng.choice(EDUCATION_LEVELS)
    residence = rng.choice(RESIDENCE_TYPES)
    city_tier = rng.choice(CITY_TIERS)
    annual_income = int(round(max(250_000, rng.gauss(1_800_000, 1_100_000))))
    years_employed = round(rng.uniform(2.0, min(age - 22, 25)), 1)
    months_as_customer = max(1, round((sim_date - disbursed_d).days / 30.44))
    prior_de = round(max(0.1, profile['de'] + rng.gauss(0, 0.3)), 4)
    prior_cibil = int(min(900, max(300, profile['cibil'] + rng.randint(-30, 30))))
    now_iso = datetime.now().isoformat(timespec='seconds')

    customer = (
        cid, bank_id, first, last, dob, gender,
        f"{first.lower()}.{last.lower()}{cust_seq}@example.com",
        f"+91{rng.randint(7000000000, 9999999999)}",
        f"{rng.randint(1, 999)} Main Road", city, state,
        str(rng.randint(100000, 999999)), disbursed_d.isoformat(), 'Active')

    kyc = (
        cid, bank_id, 1, 1, 'VERIFIED', disbursed_d.isoformat(), age, gender,
        rng.choice(['MARRIED', 'SINGLE']), edu, rng.randint(0, 3), emp_type,
        f'{bank_name.split()[0]} Corp', profile['sector'],
        years_employed, annual_income, 0.0, profile['foir'], residence,
        round(rng.uniform(1, 12), 1), city_tier, 0, 'HIGH' if is_wo else 'LOW',
        now_iso, now_iso, months_as_customer, rng.randint(1, 3), 0, loan_purpose,
        profile['prev_default'], profile['cibil'], profile['late'], state, 0,
        profile['ecs'], profile['other_lender'], profile['disruption'], profile['sector_stress'])

    balance = round(emi * rng.uniform(1.5, 3.0), 2)
    account = (aid, bank_id, cid, 'Savings', balance, disbursed_d.isoformat(),
               branch_id, ifsc, 'Active', None)

    txns = [(f"TX-{aid}-OPEN", bank_id, aid, disbursed_d.isoformat(), '09:00:00',
              'Deposit', balance, balance, '[INCOME] Opening balance - account funded')]

    loan = (
        lid, bank_id, cid, loan_type, principal, rate, tenure, emi,
        disbursed_d.isoformat(), maturity_d.isoformat(), outstanding, status, branch_id,
        classification, exposure_class,
        (sim_date - last_emi_d).days if is_wo else 0,
        last_emi_d.isoformat(), profile['ltv_trend'])

    # Both outcomes observe the SAME calendar window (the full tenure) -
    # only whether payments actually happened within it differs. Earlier
    # version stopped generating transactions entirely after n_paid_months
    # for Written-Off loans, which made n_transactions/avg_balance a
    # near-deterministic proxy for the outcome (Closed loans always had
    # ~2x more transaction rows purely from window length, not genuine
    # payment behavior) - a leakage artifact from the generation script
    # itself, not real signal. Post-default, income continues at reduced
    # frequency/amount (a struggling-but-not-inactive customer) and EMIs
    # simply stop, so emi_miss_ratio correctly captures the missed-payment
    # signal without n_transactions collapsing into a window-length tell.
    running_balance = balance
    for j in range(1, tenure + 1):
        if j <= n_paid_months:
            income_d = add_months(disbursed_d, j - 1)
            income_amt = round(emi * rng.uniform(1.6, 2.4), 2)
            running_balance = round(running_balance + income_amt, 2)
            txns.append((f"TX-{aid}-INC-{j:03d}", bank_id, aid, income_d.isoformat(), '09:00:00',
                         'Deposit', income_amt, running_balance, '[INCOME] Salary - Monthly salary credit'))
            emi_d = add_months(disbursed_d, j)
            running_balance = round(running_balance - emi, 2)
            txns.append((f"TX-{aid}-EMI-{j:03d}", bank_id, aid, emi_d.isoformat(), '05:00:00',
                         'EMI Payment', -emi, running_balance, '[LOAN] EMI Payment - Monthly loan instalment'))
        elif rng.random() < 0.4:
            # Post-default: reduced-probability, reduced-amount income only - no EMI.
            income_d = add_months(disbursed_d, j - 1)
            income_amt = round(emi * rng.uniform(0.4, 1.0), 2)
            running_balance = round(running_balance + income_amt, 2)
            txns.append((f"TX-{aid}-INC-{j:03d}", bank_id, aid, income_d.isoformat(), '09:00:00',
                         'Deposit', income_amt, running_balance, '[INCOME] Salary - Monthly salary credit'))

    crm = (
        bank_id, lid, profile['de'], profile['ic'], profile['profit'], profile['liq'],
        1 if is_wo else 0,
        round(min(0.95, max(0.005, (750 - profile['cibil']) / 900.0 + profile['de'] * 0.02)), 4),
        1 if is_wo else 0, '2025-Q4', last_emi_d.isoformat(), prior_de, prior_cibil)

    return {'customer': customer, 'kyc': kyc, 'account': account, 'txns': txns,
            'loan': loan, 'crm': crm}, is_wo


def run(wo_rate=0.125, target_epv=10.0, dry_run=False, seed_value=20260711):
    rng = random.Random(seed_value)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    sim_date = _sim_date()

    banks = cur.execute("SELECT bank_id, bank_name FROM banks ORDER BY bank_id").fetchall()
    n_banks = len(banks)

    targets = compute_targets(cur, wo_rate, target_epv)

    print("=" * 78)
    print(f"seed_completed_loans_bulk.py v2 (probabilistic) — sim_date={sim_date.isoformat()}, "
          f"target_epv={target_epv}, wo_rate~{wo_rate}{'  [DRY RUN]' if dry_run else ''}")
    print("=" * 78)
    for seg, t in targets.items():
        est_total = math.ceil(t['wo_new'] / wo_rate) if t['wo_new'] else 0
        print(f"  {seg:<18} current_defaults={t['current_defaults']:<5} "
              f"target_total_defaults={t['target_total_defaults']:<5} "
              f"-> +{t['wo_new']} written-off needed (~{est_total} total loans estimated)")
    print("=" * 78)

    if dry_run:
        conn.close()
        return targets

    # Calibrate one intercept per segment up front (shared across banks).
    intercepts = {seg: calibrate_intercept(rng, seg, wo_rate) for seg in SEGMENTS}
    print("Calibrated intercepts:", {k: round(v, 3) for k, v in intercepts.items()})
    print("=" * 78)

    realized = {seg: {'closed': 0, 'wo': 0} for seg in SEGMENTS}

    for bank_id, bank_name in banks:
        prefix = _bank_prefix(cur, bank_id)
        branch_id, ifsc = cur.execute(
            "SELECT branch_id, ifsc_code FROM branches WHERE bank_id=? LIMIT 1", (bank_id,)
        ).fetchone()

        bank_customers, bank_kycs, bank_accounts, bank_txns, bank_loans, bank_crms = [], [], [], [], [], []
        acc_seq = _next_seq(cur, f'ACC-{prefix}', '-', 'accounts', 'id')
        cust_seq_by_code, loan_seq_by_code = {}, {}

        bank_idx = [b for b, _ in banks].index(bank_id)

        for seg in SEGMENTS:
            wo_target_per_bank = _split_across_banks(targets[seg]['wo_new'], n_banks)[bank_idx]
            if wo_target_per_bank == 0:
                continue

            seg_code = SEG_CODE[seg]
            if seg_code not in cust_seq_by_code:
                cust_seq_by_code[seg_code] = _next_seq(cur, prefix, f'-{seg_code}-', 'customers', 'id')
                loan_seq_by_code[seg_code] = _next_seq(cur, f'{prefix}-LN', f'-{seg_code}-', 'loans', 'id')

            wo_count = 0
            # Safety valve: shouldn't be hit given wo_rate calibration, but
            # avoids a runaway loop if something's off.
            max_draws = int(wo_target_per_bank / wo_rate * 20) + 1000

            for _ in range(max_draws):
                if wo_count >= wo_target_per_bank:
                    break
                rows, is_wo = generate_one_loan(
                    bank_id, bank_name, branch_id, ifsc, seg, prefix,
                    cust_seq_by_code[seg_code], loan_seq_by_code[seg_code], acc_seq,
                    intercepts[seg], sim_date, rng)
                cust_seq_by_code[seg_code] += 1
                loan_seq_by_code[seg_code] += 1
                acc_seq += 1

                bank_customers.append(rows['customer'])
                bank_kycs.append(rows['kyc'])
                bank_accounts.append(rows['account'])
                bank_txns.extend(rows['txns'])
                bank_loans.append(rows['loan'])
                bank_crms.append(rows['crm'])

                if is_wo:
                    wo_count += 1
                    realized[seg]['wo'] += 1
                else:
                    realized[seg]['closed'] += 1

        cur.executemany(
            "INSERT INTO customers (id, bank_id, first, last, dob, gender, email, phone, "
            "address, city, state, pincode, joined, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            bank_customers)
        cur.executemany(
            "INSERT INTO customer_kyc (cid, bank_id, pan_verified, aadhaar_verified, "
            "kyc_status, kyc_date, age, gender, marital_status, education_level, "
            "num_dependents, employment_type, employer_name, industry_sector, "
            "years_employed, annual_income, other_income, foir_declared, "
            "residence_type, years_at_address, city_tier, is_pep, risk_category, "
            "created_at, updated_at, months_as_customer, num_existing_products, "
            "existing_loans_count, loan_purpose, previous_default_flag, cibil_score, "
            "num_late_payments_past_12m, state, is_rural, "
            "ecs_bounce_count, other_lender_emi_ratio, income_disruption_flag, sector_stress_index) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            bank_kycs)
        cur.executemany(
            "INSERT INTO accounts (id, bank_id, cid, type, balance, open_date, "
            "branch_id, ifsc_code, status, maturity_date) VALUES (?,?,?,?,?,?,?,?,?,?)",
            bank_accounts)
        cur.executemany(
            "INSERT INTO transactions (id, bank_id, aid, date, time, type, amount, balance_after, desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            bank_txns)
        cur.executemany(
            "INSERT INTO loans (id, bank_id, cid, type, principal, rate, tenure, emi, "
            "disbursed, maturity, outstanding, status, branch_id, loan_classification, "
            "exposure_class, days_past_due, last_payment_date, ltv_trend_pct) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            bank_loans)
        cur.executemany(
            "INSERT INTO credit_risk_metrics (bank_id, lid, de, intcov, profit, liq, df, "
            "pd_score, npa_flag, period, obs, prior_de, prior_cibil) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            bank_crms)

        conn.commit()
        print(f"  {bank_id}: +{len(bank_loans)} loans, +{len(bank_txns)} transactions — committed")

    conn.close()
    print("=" * 78)
    for seg in SEGMENTS:
        r = realized[seg]
        total = r['closed'] + r['wo']
        rate = r['wo'] / total if total else 0
        print(f"  {seg:<18} realized: +{r['closed']} closed, +{r['wo']} written-off "
              f"({total} total, {rate:.1%} written-off rate)")
    print("Done.")
    print("=" * 78)
    return realized


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--wo-rate', type=float, default=0.125)
    ap.add_argument('--target-epv', type=float, default=10.0)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    run(wo_rate=args.wo_rate, target_epv=args.target_epv, dry_run=args.dry_run)
