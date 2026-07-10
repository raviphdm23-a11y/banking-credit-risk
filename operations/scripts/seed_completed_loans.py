"""
seed_completed_loans.py
────────────────────────
Adds new customers whose loan lifecycle is *already resolved* (Closed or
Written-Off) rather than Active - this is the population sync_bank_loan_metrics.py
now trains on exclusively (see its own docstring), and there are currently
only 154 such loans in the whole ledger, split 4 ways by exposure_class and
9 ways by bank. That's too thin to train a model with real discriminative
power (a full customer-level run currently comes out AUC=0.5).

Design (see conversation for the reasoning this was checked against):
  - Purely additive: new customers/accounts/loans/transactions only, never
    touches an existing row.
  - disbursed/tenure/maturity are chosen so the loan's full lifecycle -
    disbursement through its last EMI - already sits in the past relative
    to simulation_clock.json's sim_date, with a multi-month buffer, so nothing
    needs a separate lifecycle-resolution pass afterward.
  - Closed loans get a full, uninterrupted EMI/income transaction trail for
    their entire tenure and outstanding=0 (zero footprint on today's
    advances_net/CD-ratio/LCR/NSFR - see bank_liquidity_report()).
  - Written-Off loans get a genuinely interrupted trail (EMIs stop partway
    through, paid ratio in the 30-60% band - a real default signal, not a
    seeding-window artifact) and a nonzero outstanding, matching how every
    Written-Off loan already in this ledger behaves (so this DOES add a
    small amount to advances_net - it's not zero-impact like Closed loans).
  - Follows each bank's existing ID conventions exactly ({PREFIX}-LN-{SEG}-#####
    for loans, {PREFIX}-{SEG}-#### for customers, ACC-{PREFIX}-##### for
    accounts) and the current (not legacy) transaction-type conventions
    (type='EMI Payment' / type='Deposit', matching what
    build_behavioral_features.py and the rest of the pipeline expect).

Run:
    python operations/scripts/seed_completed_loans.py [--per-bank N] [--dry-run]
    Then:
    python operations/scripts/sync_bank_loan_metrics.py
    python operations/scripts/build_behavioral_features.py
"""

import argparse
import json
import os
import random
import re
import sqlite3
from datetime import date, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

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

CLOSED_SHARE = 0.90
TENURE_CHOICES = [24, 36, 48]

WRITTEN_OFF_PAID_RATIO = (0.30, 0.60)   # genuinely delinquent - stops well below the 85% "closed" threshold
CLOSED_PAID_RATIO      = 1.0            # full tenure paid


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


def _next_seq(cur, table, id_col, prefix, sep):
    row = cur.execute(
        f"SELECT MAX(CAST(SUBSTR({id_col}, ?) AS INTEGER)) FROM {table} WHERE {id_col} LIKE ?",
        (len(prefix) + len(sep) + 1, prefix + sep + '%')
    ).fetchone()
    return (row[0] or 0) + 1


def _next_acc_seq(cur, bank_id, prefix):
    rows = cur.execute("SELECT id FROM accounts WHERE bank_id=?", (bank_id,)).fetchall()
    best = 0
    for (aid,) in rows:
        m = re.match(r'ACC-[A-Z]+-(\d+)', aid)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


def _principal_rate_range(cur, bank_id, exposure_class):
    row = cur.execute(
        "SELECT AVG(principal), MIN(principal), MAX(principal), AVG(rate), MIN(rate), MAX(rate) "
        "FROM loans WHERE bank_id=? AND exposure_class=?",
        (bank_id, exposure_class)
    ).fetchone()
    if row and row[0]:
        return row
    # Fallback: segment-wide range if this bank has no existing loans in this segment
    row = cur.execute(
        "SELECT AVG(principal), MIN(principal), MAX(principal), AVG(rate), MIN(rate), MAX(rate) "
        "FROM loans WHERE exposure_class=?", (exposure_class,)
    ).fetchone()
    return row


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


def make_loan(conn, bank_id, bank_name, country_code, branch_id, ifsc, exposure_class,
              prefix, is_written_off, sim_date, rng, dry_run):
    cur = conn.cursor()

    seg_code = SEG_CODE[exposure_class]
    cust_seq = _next_seq(cur, 'customers', 'id', prefix, f'-{seg_code}-')
    loan_seq = _next_seq(cur, 'loans', 'id', f'{prefix}-LN', f'-{seg_code}-')
    acc_seq  = _next_acc_seq(cur, bank_id, prefix)

    cid = f"{prefix}-{seg_code}-{cust_seq:04d}"
    lid = f"{prefix}-LN-{seg_code}-{loan_seq:05d}"
    aid = f"ACC-{prefix}-{acc_seq:05d}"

    # ── Timing: maturity always 3-27 months before sim_date, tenure/disbursed
    # derived backward from that so the loan's full observed life is
    # unambiguously in the past. ────────────────────────────────────────────
    tenure = rng.choice(TENURE_CHOICES)
    months_since_maturity = rng.randint(3, 27)
    maturity_d = add_months(sim_date, -months_since_maturity)
    disbursed_d = add_months(maturity_d, -tenure)

    principal_avg, principal_min, principal_max, rate_avg, rate_min, rate_max = \
        _principal_rate_range(cur, bank_id, exposure_class)
    principal = round(rng.uniform(principal_min, principal_max) / 10_000) * 10_000
    rate = round(rng.uniform(rate_min, rate_max), 2)
    emi = calc_emi(principal, rate, tenure)

    if is_written_off:
        paid_ratio = rng.uniform(*WRITTEN_OFF_PAID_RATIO)
        outstanding = round(principal * rng.uniform(0.5, 0.75), 2)
        status, classification = 'Written-Off', 'Written-Off'
    else:
        paid_ratio = CLOSED_PAID_RATIO
        outstanding = 0.0
        status, classification = 'Closed', 'Standard'

    n_paid_months = max(1, round(tenure * paid_ratio))
    last_emi_d = add_months(disbursed_d, n_paid_months)

    # ── Customer profile ─────────────────────────────────────────────────────
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

    if is_written_off:
        cibil = rng.randint(540, 670)
        de = round(rng.uniform(3.0, 6.5), 2)
        ic = round(rng.uniform(0.8, 2.2), 2)
        profit = round(rng.uniform(-8.0, 4.0), 1)
        liq = round(rng.uniform(0.5, 1.1), 2)
        foir = round(rng.uniform(0.50, 0.85), 2)
        late = rng.randint(2, 7)
        prev_default = 1 if rng.random() < 0.4 else 0
        annual_income = rng.randint(300_000, 1_400_000)
    else:
        cibil = rng.randint(720, 830)
        de = round(rng.uniform(0.4, 1.8), 2)
        ic = round(rng.uniform(4.0, 12.0), 2)
        profit = round(rng.uniform(8.0, 20.0), 1)
        liq = round(rng.uniform(1.4, 2.6), 2)
        foir = round(rng.uniform(0.18, 0.40), 2)
        late = 0
        prev_default = 0
        annual_income = rng.randint(700_000, 4_500_000)

    years_employed = round(rng.uniform(2.0, min(age - 22, 25)), 1)
    months_as_customer = max(1, round((sim_date - disbursed_d).days / 30.44))
    prior_de = round(rng.uniform(0.5, 1.8), 4)
    prior_cibil = rng.randint(700, 820)
    now_iso = datetime.now().isoformat(timespec='seconds')

    if dry_run:
        return {
            'cid': cid, 'lid': lid, 'aid': aid, 'status': status,
            'principal': principal, 'outstanding': outstanding,
            'disbursed': disbursed_d.isoformat(), 'maturity': maturity_d.isoformat(),
            'last_emi': last_emi_d.isoformat(),
        }

    # ── Insert customer / kyc / account ──────────────────────────────────────
    cur.execute("""
        INSERT INTO customers (id, bank_id, first, last, dob, gender, email, phone,
            address, city, state, pincode, joined, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (cid, bank_id, first, last, dob, gender,
          f"{first.lower()}.{last.lower()}{cust_seq}@example.com",
          f"+91{rng.randint(7000000000, 9999999999)}",
          f"{rng.randint(1, 999)} Main Road", city, state,
          str(rng.randint(100000, 999999)), disbursed_d.isoformat(), 'Active'))

    cur.execute("""
        INSERT INTO customer_kyc (cid, bank_id, pan_verified, aadhaar_verified,
            kyc_status, kyc_date, age, gender, marital_status, education_level,
            num_dependents, employment_type, employer_name, industry_sector,
            years_employed, annual_income, other_income, foir_declared,
            residence_type, years_at_address, city_tier, is_pep, risk_category,
            created_at, updated_at, months_as_customer, num_existing_products,
            existing_loans_count, loan_purpose, previous_default_flag, cibil_score,
            num_late_payments_past_12m, state, is_rural)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (cid, bank_id, 1, 1, 'VERIFIED', disbursed_d.isoformat(), age, gender,
          rng.choice(['MARRIED', 'SINGLE']), edu, rng.randint(0, 3), emp_type,
          f'{bank_name.split()[0]} Corp', rng.choice(['IT', 'Manufacturing', 'Retail', 'Healthcare', 'Finance']),
          years_employed, annual_income, 0.0, foir, residence,
          round(rng.uniform(1, 12), 1), city_tier, 0, 'HIGH' if is_written_off else 'LOW',
          now_iso, now_iso, months_as_customer, rng.randint(1, 3), 0, loan_purpose,
          prev_default, cibil, late, state, 0))

    balance = round(emi * rng.uniform(1.5, 3.0), 2)
    cur.execute("""
        INSERT INTO accounts (id, bank_id, cid, type, balance, open_date,
            branch_id, ifsc_code, status, maturity_date)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (aid, bank_id, cid, 'Savings', balance, disbursed_d.isoformat(), branch_id, ifsc, 'Active', None))

    cur.execute("""
        INSERT INTO transactions (id, bank_id, aid, date, time, type, amount, balance_after, desc)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (f"TX-{aid}-OPEN", bank_id, aid, disbursed_d.isoformat(), '09:00:00',
          'Deposit', balance, balance, '[INCOME] Opening balance - account funded'))

    # ── Loan ──────────────────────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO loans (id, bank_id, cid, type, principal, rate, tenure, emi,
            disbursed, maturity, outstanding, status, branch_id, loan_classification,
            exposure_class, days_past_due, last_payment_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (lid, bank_id, cid, loan_type, principal, rate, tenure, emi,
          disbursed_d.isoformat(), maturity_d.isoformat(), outstanding, status, branch_id,
          classification, exposure_class,
          (sim_date - last_emi_d).days if is_written_off else 0,
          last_emi_d.isoformat()))

    # ── Monthly income + EMI transaction trail (stops at n_paid_months) ──────
    running_balance = balance
    for j in range(1, n_paid_months + 1):
        income_d = add_months(disbursed_d, j - 1)
        income_amt = round(emi * rng.uniform(1.6, 2.4), 2)
        running_balance = round(running_balance + income_amt, 2)
        cur.execute("""
            INSERT INTO transactions (id, bank_id, aid, date, time, type, amount, balance_after, desc)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (f"TX-{aid}-INC-{j:03d}", bank_id, aid, income_d.isoformat(), '09:00:00',
              'Deposit', income_amt, running_balance, '[INCOME] Salary - Monthly salary credit'))

        emi_d = add_months(disbursed_d, j)
        running_balance = round(running_balance - emi, 2)
        cur.execute("""
            INSERT INTO transactions (id, bank_id, aid, date, time, type, amount, balance_after, desc)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (f"TX-{aid}-EMI-{j:03d}", bank_id, aid, emi_d.isoformat(), '05:00:00',
              'EMI Payment', -emi, running_balance, '[LOAN] EMI Payment - Monthly loan instalment'))

    # ── credit_risk_metrics (single row - no duplication) ────────────────────
    cur.execute("""
        INSERT INTO credit_risk_metrics
            (bank_id, lid, de, intcov, profit, liq, df, pd_score, npa_flag, period, obs,
             prior_de, prior_cibil)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (bank_id, lid, de, ic, profit, liq, 1 if is_written_off else 0,
          round(min(0.95, max(0.005, (750 - cibil) / 900.0 + de * 0.02)), 4),
          1 if is_written_off else 0, '2025-Q4', last_emi_d.isoformat(),
          prior_de, prior_cibil))

    return {'cid': cid, 'lid': lid, 'aid': aid, 'status': status,
            'principal': principal, 'outstanding': outstanding}


def seed(per_bank=40, dry_run=False, db_path=DB_PATH, seed_value=20260709):
    rng = random.Random(seed_value)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    sim_date = _sim_date()

    banks = cur.execute(
        "SELECT bank_id, bank_name, country_code FROM banks ORDER BY bank_id"
    ).fetchall()

    per_segment = per_bank // len(SEGMENTS)
    n_written_off_per_segment = max(1, round(per_segment * (1 - CLOSED_SHARE)))

    print("=" * 70)
    print(f"seed_completed_loans.py — sim_date={sim_date.isoformat()}"
          f"{'  [DRY RUN]' if dry_run else ''}")
    print(f"Target: {per_bank}/bank x {len(banks)} banks = {per_bank * len(banks)} total, "
          f"{per_segment}/segment/bank ({n_written_off_per_segment} written-off of those)")
    print("=" * 70)

    totals = {'Closed': 0, 'Written-Off': 0}
    for bank_id, bank_name, country_code in banks:
        prefix = _bank_prefix(cur, bank_id)
        branch_row = cur.execute(
            "SELECT branch_id, ifsc_code FROM branches WHERE bank_id=? LIMIT 1", (bank_id,)
        ).fetchone()
        branch_id, ifsc = branch_row

        bank_added = {'Closed': 0, 'Written-Off': 0}
        for exposure_class in SEGMENTS:
            # Randomly spread which slot(s) in this segment/bank are the
            # written-off ones, rather than always the first N - avoids any
            # artificial clustering by generation order.
            slots = list(range(per_segment))
            rng.shuffle(slots)
            written_off_slots = set(slots[:n_written_off_per_segment])

            for slot in range(per_segment):
                is_wo = slot in written_off_slots
                result = make_loan(conn, bank_id, bank_name, country_code, branch_id, ifsc,
                                    exposure_class, prefix, is_wo, sim_date, rng, dry_run)
                bank_added[result['status']] += 1

        for k in totals:
            totals[k] += bank_added[k]
        print(f"  {bank_id}: +{bank_added['Closed']} Closed, +{bank_added['Written-Off']} Written-Off")

    if not dry_run:
        conn.commit()
    conn.close()

    print()
    print(f"Total: +{totals['Closed']} Closed, +{totals['Written-Off']} Written-Off "
          f"({sum(totals.values())} loans){' (dry run - no changes written)' if dry_run else ''}")
    print("=" * 70)
    return totals


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--per-bank', type=int, default=40)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    seed(per_bank=args.per_bank, dry_run=args.dry_run)
