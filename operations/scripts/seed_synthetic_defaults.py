"""
seed_synthetic_defaults.py
────────────────────────────
Adds synthetic loans (+ backing customers/accounts/transactions) targeting
under-represented exposure-class segments so each of CORPORATE, SME,
RETAIL_MORTGAGES, RETAIL_OTHER has enough defaulting loans to train/validate
a segment-specific PD model. Before this script: CORPORATE 1/422,
SME 2/218, RETAIL_MORTGAGES 5/332, RETAIL_OTHER 11/378 (defaults/total) -
too sparse for any per-segment model or honest cross-validation.

Root-cause fix: unlike seed_real_bank.py/add_new_customers.py's
simple_default_rate_model(), which conditions default probability only on
income/age/macro (never exposure_class), this script feeds
risk_formula.segment_pd_multiplier(exposure_class) into that function's
macro_regime_score parameter so each segment gets an appropriately elevated,
segment-specific default rate instead of the same flat ~2.5% baseline.

Also generates up to 12 months of realistic transaction history per new
loan (monthly income deposit + EMI payment) so build_behavioral_features.py
computes REAL emi_miss_ratio/income_cv/etc. for these rows instead of
leaving them NULL -> median-filled. Defaulting loans get a meaningfully
higher missed-payment rate baked into their transaction history so the
behavioral features carry genuine signal for the newly-augmented segments.

Run:  python operations/scripts/seed_synthetic_defaults.py
Then: python operations/scripts/build_behavioral_features.py
"""
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ml_models.risk_formula import (
    add_measurement_noise,
    sample_correlated_features,
    segment_pd_multiplier,
    simple_default_rate_model,
)

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

SEGMENT_LOAN_TYPE = {
    'CORPORATE':        [('Business Loan', 2)],
    'SME':              [('Business Loan', 2)],
    'RETAIL_MORTGAGES': [('Home Loan', 5)],
    'RETAIL_OTHER':      [('Vehicle Loan', 3), ('Personal Loan', 1), ('Education Loan', 4)],
}
SEGMENT_EMPLOYMENT = {
    'CORPORATE':        ['GOVT', 'SALARIED'],
    'SME':              ['BUSINESS', 'SELF_EMPLOYED'],
    'RETAIL_MORTGAGES': ['SALARIED', 'GOVT', 'SELF_EMPLOYED'],
    'RETAIL_OTHER':     ['SALARIED', 'FREELANCE', 'RETIRED', 'STUDENT'],
}
EMP_LABELS = ['GOVT', 'SALARIED', 'RETIRED', 'SELF_EMPLOYED', 'BUSINESS', 'FREELANCE', 'STUDENT']
FIRST = ['Aarav', 'Diya', 'Kabir', 'Anaya', 'Vivaan', 'Saanvi', 'Reyansh', 'Myra', 'Aditya', 'Ira',
         'Krishna', 'Aadhya', 'Arjun', 'Kiara', 'Ishaan', 'Riya', 'Rohan', 'Neha', 'Sanjay', 'Pooja']
LAST = ['Malhotra', 'Kapoor', 'Bhat', 'Menon', 'Chauhan', 'Pillai', 'Saxena', 'Bose', 'Nayak', 'Gill',
        'Iyer', 'Reddy', 'Verma', 'Joshi', 'Shetty']
CITIES = [('Mumbai', 'Maharashtra', 1), ('Pune', 'Maharashtra', 2), ('Indore', 'Madhya Pradesh', 2),
          ('Kochi', 'Kerala', 2), ('Patna', 'Bihar', 3), ('Bengaluru', 'Karnataka', 1)]

TARGET_DEFAULTS = 55
BASE_BATCH = {'CORPORATE': 400, 'SME': 400, 'RETAIL_MORTGAGES': 500, 'RETAIL_OTHER': 350}
TOPUP_BATCH = 150
MAX_ITERS = 6


def emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def gen_loan(cur, idx, segment, bank_id, bank_name, country_code, branch_id, ifsc, rng):
    cid = f"SYNC{idx}"
    first, last = random.choice(FIRST), random.choice(LAST)
    city, state, tier = random.choice(CITIES)
    emp_label = random.choice(SEGMENT_EMPLOYMENT[segment])
    emp_enc = EMP_LABELS.index(emp_label) + 1
    edu_enc = random.randint(1, 6)
    res_enc = random.randint(1, 4)
    ltype, purpose_enc = random.choice(SEGMENT_LOAN_TYPE[segment])
    is_rural = 1 if tier == 3 and random.random() < 0.5 else 0
    age = random.randint(26, 62)
    years_emp = round(random.uniform(1, min(age - 22, 30)), 1)
    deps = random.randint(0, 4)
    months_cust = random.randint(6, 200)
    ex_loans = random.randint(0, 4)
    ex_products = random.randint(1, 6)

    good = random.random() < 0.5
    if good:
        de_true = float(np.clip(rng.exponential(scale=0.7), 0.1, 2.5))
        ic_true = float(np.clip(rng.gamma(shape=3.0, scale=2.5), 3.5, 15.0))
        profit_true = float(np.clip(rng.normal(loc=15.0, scale=8.0), 5.0, 60.0))
        liq_true = float(np.clip(rng.gamma(shape=4.0, scale=0.5), 1.3, 4.0))
        income = random.randint(5000000, 40000000) if segment == 'CORPORATE' else random.randint(900000, 4500000)
        late = 0
        prev_def = 0
    else:
        de_true = float(np.clip(rng.exponential(scale=1.5), 2.0, 8.0))
        ic_true = float(np.clip(rng.gamma(shape=2.0, scale=1.0), 1.0, 3.5))
        profit_true = float(np.clip(rng.normal(loc=-1.0, scale=10.0), -50.0, 10.0))
        liq_true = float(np.clip(rng.gamma(shape=2.0, scale=0.3), 0.5, 2.0))
        income = random.randint(2000000, 15000000) if segment == 'CORPORATE' else random.randint(300000, 1500000)
        late = random.randint(1, 6)
        prev_def = 1 if random.random() < 0.4 else 0

    foir_true = float(np.clip(rng.beta(2.2, 3.5), 0.05, 0.75))
    noisy = add_measurement_noise(rng, de_true, ic_true, profit_true, liq_true, income, years_emp, foir_true)
    de = round(noisy['de_ratio'], 2)
    ic = round(noisy['int_coverage'], 2)
    profit = round(noisy['profitability'], 1)
    liq = round(noisy['liquidity_ratio'], 2)
    foir = round(noisy['foir'], 2)
    corr = sample_correlated_features(rng, income, years_emp, profit)
    cibil = corr['cibil_score']

    # Segment-aware default probability - the actual root-cause fix.
    macro_stress = segment_pd_multiplier(segment)
    pd_obs = simple_default_rate_model(income, age, macro_stress, rng)
    default_flag = int(rng.binomial(1, p=pd_obs))
    pd_obs = round(pd_obs, 4)

    principal = random.randint(3, 80) * 100000
    outstanding = round(principal * random.uniform(0.55, 0.98), 2)
    rate = round(random.uniform(8.5, 15.5), 2)
    tenure = random.choice([36, 48, 60, 84, 120, 180])
    loan_emi = emi(principal, rate, tenure)
    classification = 'NPA' if (default_flag and random.random() < 0.6) else 'Standard'
    disb_date = date.today() - timedelta(days=random.randint(400, 1200))
    mat_year = disb_date.year + tenure // 12
    mat = date(mat_year, min(disb_date.month, 12), 28).isoformat()
    lid = f"SYN-{segment[:4]}-{idx:05d}"
    aid = f"SYNACC-{idx:05d}"
    balance = round(random.uniform(50000, 1500000), 2)
    obs = date.today().isoformat()
    now = datetime.now().isoformat(timespec='seconds')

    cur.execute("INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, bank_id, first, last, f"{date.today().year - age}-06-15", random.choice(['Male', 'Female']),
                 f"{first.lower()}.{last.lower()}{idx}@example.com", f"9{random.randint(100000000, 999999999)}",
                 f"{random.randint(1, 99)} MG Road", city, state, str(random.randint(100000, 999999)),
                 date.today().isoformat(), 'Active'))

    cur.execute("INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (aid, bank_id, cid, 'Savings', balance, disb_date.isoformat(), branch_id, ifsc, 'Active'))

    # ── Up to 12 months of transaction history: monthly income + EMI ──────
    # Defaulting loans get a materially higher missed-EMI/income rate so
    # emi_miss_ratio/income_miss_ratio carry genuine signal for this segment
    # instead of relying on population-median fill.
    running_balance = balance
    monthly_income = income / 12.0
    # Continuous, overlapping miss-probability draws rather than a fixed
    # constant per default_flag value - a hardcoded 0.45-vs-0.03 split would
    # make emi_miss_ratio a near-perfect discriminator on its own (the same
    # disjoint-bucket separability problem this project already fixed once
    # for financial ratios). Beta draws give each loan its own probability
    # with real overlap between defaulters and non-defaulters.
    miss_emi_prob = float(np.clip(rng.beta(2.5, 4.0) if default_flag else rng.beta(1.0, 12.0), 0.0, 0.85))
    miss_income_prob = float(np.clip(rng.beta(1.5, 6.0) if default_flag else rng.beta(1.0, 20.0), 0.0, 0.7))
    tx_rows = []
    for m in range(12):
        tx_date = disb_date + timedelta(days=30 * m + random.randint(0, 4))
        if tx_date > date.today():
            break
        if random.random() > miss_income_prob:
            amt = round(monthly_income * random.uniform(0.9, 1.1), 2)
            running_balance = round(running_balance + amt, 2)
            tx_rows.append((f"SYNTX-{idx}-{m}-IN", bank_id, aid, tx_date.isoformat(), '09:00:00',
                             'Deposit', amt, running_balance, '[INCOME] Monthly salary/business income'))
        if random.random() > miss_emi_prob:
            running_balance = round(running_balance - loan_emi, 2)
            tx_rows.append((f"SYNTX-{idx}-{m}-EMI", bank_id, aid, tx_date.isoformat(), '10:00:00',
                             'EMI Payment', loan_emi, running_balance, f'EMI payment for {lid}'))
    cur.executemany("INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", tx_rows)

    cur.execute("INSERT INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,maturity,outstanding,status,branch_id,loan_classification,exposure_class) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lid, bank_id, cid, ltype, principal, rate, tenure, loan_emi, disb_date.isoformat(), mat, outstanding,
                 'Active', branch_id, classification, segment))

    cur.execute("INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,age,gender,"
                "marital_status,education_level,num_dependents,employment_type,employer_name,industry_sector,"
                "years_employed,annual_income,other_income,foir_declared,residence_type,years_at_address,city_tier,"
                "is_pep,risk_category,created_at,updated_at,months_as_customer,num_existing_products,existing_loans_count,"
                "loan_purpose,previous_default_flag,cibil_score,num_late_payments_past_12m,state,is_rural) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, bank_id, 1, 1, 'VERIFIED', disb_date.isoformat(), age, 'Male', 'MARRIED',
                 ['PHD', 'PROFESSIONAL', 'POST_GRADUATE', 'GRADUATE', 'DIPLOMA', 'HIGH_SCHOOL'][edu_enc - 1],
                 deps, emp_label, 'Employer Pvt Ltd', 'Services', years_emp, income, 0, foir,
                 ['OWNED', 'RENTED', 'FAMILY', 'EMPLOYER'][res_enc - 1], round(random.uniform(1, 15), 1),
                 f"TIER{tier}", 0, 'HIGH' if not good else 'LOW', now, now, months_cust, ex_products, ex_loans,
                 {'Home Loan': 'HOME_PURCHASE', 'Vehicle Loan': 'VEHICLE', 'Personal Loan': 'PERSONAL',
                  'Education Loan': 'EDUCATION', 'Business Loan': 'BUSINESS'}.get(ltype, 'PERSONAL'),
                 prev_def, cibil, late, state, is_rural))

    prior_de = round(random.uniform(0.5, 1.8), 4)
    prior_cibil = random.randint(710, 820)

    cur.execute("INSERT INTO credit_risk_metrics (bank_id,lid,de,intcov,profit,liq,df,pd_score,npa_flag,period,obs,prior_de,prior_cibil) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bank_id, lid, de, ic, profit, liq, default_flag, pd_obs,
                 1 if classification == 'NPA' else 0, '2024-Q2', obs, prior_de, prior_cibil))

    macro = cur.execute("""
        SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct
        FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1
    """, (country_code,)).fetchone() or (6.7, 4.5, 6.25, 7.6)

    months_orig = round(((date.today() - disb_date).days) / 30.44, 1)

    cur.execute("INSERT INTO bank_loan_metrics (bank_id,bank_name,loan_id,de_ratio,interest_coverage,profitability,"
                "liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,age,employment_type_enc,"
                "years_employed,annual_income,foir,num_dependents,city_tier_enc,education_enc,residence_type_enc,"
                "loan_purpose_enc,cibil_score,previous_default_flag,months_as_customer,num_late_payments_past_12m,"
                "existing_loans_count,num_existing_products,is_rural,country_code,exposure_class,"
                "gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct,"
                "delta_de_ratio,delta_cibil,months_since_origination) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bank_id, bank_name, lid, de, ic, profit, liq, default_flag, pd_obs, obs, now,
                 age, emp_enc, years_emp, income, foir, deps, tier, edu_enc, res_enc, purpose_enc,
                 cibil, prev_def, months_cust, late, ex_loans, ex_products, is_rural, country_code, segment,
                 macro[0], macro[1], macro[2], macro[3],
                 round(de - prior_de, 4), round(float(cibil - prior_cibil), 1), months_orig))

    return default_flag


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    banks = cur.execute("SELECT bank_id, bank_name, country_code FROM banks").fetchall()
    branch_by_bank = {}
    for bid, _, _ in banks:
        row = cur.execute("SELECT branch_id, ifsc_code FROM branches WHERE bank_id=? LIMIT 1", (bid,)).fetchone()
        branch_by_bank[bid] = row or (f"BR-{bid}-001", f"{bid}0000001")

    idx = (cur.execute(
        "SELECT MAX(CAST(SUBSTR(id,5) AS INTEGER)) FROM customers WHERE id LIKE 'SYNC%'"
    ).fetchone()[0] or 0) + 1
    rng = np.random.default_rng(seed=2027)

    print("Before:")
    totals = {}
    for seg in BASE_BATCH:
        n, d = cur.execute(
            "SELECT COUNT(*), SUM(default_flag) FROM bank_loan_metrics WHERE exposure_class=?", (seg,)
        ).fetchone()
        totals[seg] = d or 0
        print(f"  {seg:<20}{d or 0}/{n or 0}")

    for seg, batch in BASE_BATCH.items():
        iters = 0
        current_batch = batch
        while totals[seg] < TARGET_DEFAULTS and iters < MAX_ITERS:
            new_defaults = 0
            for _ in range(current_batch):
                bid, bname, cc = random.choice(banks)
                branch_id, ifsc = branch_by_bank[bid]
                new_defaults += gen_loan(cur, idx, seg, bid, bname, cc, branch_id, ifsc, rng)
                idx += 1
            totals[seg] += new_defaults
            conn.commit()
            print(f"  [{seg}] +{current_batch} loans, +{new_defaults} defaults -> running total {totals[seg]}")
            iters += 1
            current_batch = TOPUP_BATCH

    print("\nFinal counts:")
    for seg in BASE_BATCH:
        n, d = cur.execute(
            "SELECT COUNT(*), SUM(default_flag) FROM bank_loan_metrics WHERE exposure_class=?", (seg,)
        ).fetchone()
        print(f"  {seg}: {d}/{n} defaults")

    conn.close()


if __name__ == '__main__':
    main()
