"""
seed_global_customers.py
────────────────────────
Ground the four foreign group banks (BANK003 USA, BANK004 UK, BANK005 Singapore,
BANK006 UAE) in a **real ledger**, exactly like the two India banks — so their
balance sheet, P&L, CAR, LCR and GNPA roll up from actual customers/loans/accounts
instead of hardcoded anchors.

For each foreign bank this generates the full record set the platform expects
(mirrors operations/scripts/add_new_customers.py):
    branches · customers · customer_kyc · accounts (+ one opening-deposit
    transaction so the ledger stays reconciled) · loans · credit_risk_metrics ·
    bank_loan_metrics (the 21-feature + target row the PD trainer consumes).

Design notes
------------
* Monetary amounts stay in the **group reporting currency (₹)** — consistent with
  the rest of bank.db and the global-reporting design; the country/currency/FX
  context lives in the `countries` / `country_macro` tables.
* Bank sizing preserves the regional hierarchy (USA largest → UAE smallest) via
  per-bank customer counts + loan/deposit ranges, so group/region/country totals
  stay meaningful and land near the original anchors.
* Country-appropriate name/city pools per bank for realism.
* PD (`pd_observed`/`pd_score`) is generated from the risk drivers so the model
  has genuine signal; ~1-in-6 customers are NPA.
* **Idempotent**: a bank that already has customers is skipped.

After this runs, re-run seed_bank_balance_sheet.py + seed_bank_profit_loss.py so
the foreign banks' sheets become live-anchored (they auto-include any bank that
now has loans/accounts).

Run:  python operations/scripts/seed_global_customers.py
"""

import os
import sqlite3
import random
from datetime import date, datetime
import numpy as np

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

# Import shared risk formula (consistent with seed_real_bank.py and add_new_customers.py)
import sys
sys.path.insert(0, _REPO_ROOT)
from ml_models.risk_formula import true_pd_nonlinear, sample_correlated_features, add_measurement_noise

# ── per-bank config: customer count, branch code stem, name/city pools, sizes ──
# (loan principal & account balance ranges in raw ₹; tuned so advances/deposits
#  land near the original anchors with a healthy loan-to-deposit ratio)
BANKS = {
    'BANK003': {  # Atlas Bank N.A. — USA
        'name': 'Atlas Bank N.A.', 'stem': 'ATLS', 'short': 'ATLAS', 'n': 30, 'country_code': 'USA',
        'principal': (2_500_000, 6_000_000), 'balance': (1_500_000, 3_800_000),
        'first': ['James', 'Michael', 'Robert', 'John', 'David', 'William', 'Richard',
                  'Joseph', 'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Emily',
                  'Jessica', 'Sarah', 'Karen', 'Nancy', 'Daniel', 'Matthew'],
        'last': ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
                 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Taylor', 'Thomas'],
        'cities': [('New York', 'NY'), ('Los Angeles', 'CA'), ('Chicago', 'IL'),
                   ('Houston', 'TX'), ('San Francisco', 'CA'), ('Boston', 'MA'),
                   ('Seattle', 'WA'), ('Miami', 'FL'), ('Austin', 'TX')],
    },
    'BANK004': {  # Britannia Banking Group plc — UK
        'name': 'Britannia Banking Group plc', 'stem': 'BRIT', 'short': 'BRITANNIA', 'n': 24, 'country_code': 'GBR',
        'principal': (2_200_000, 5_500_000), 'balance': (1_400_000, 3_500_000),
        'first': ['Oliver', 'George', 'Harry', 'Jack', 'Charlie', 'Thomas', 'Henry',
                  'William', 'Amelia', 'Olivia', 'Emily', 'Isla', 'Sophie', 'Grace',
                  'Lily', 'Freya', 'Charlotte', 'Jessica', 'Daniel', 'Edward'],
        'last': ['Smith', 'Jones', 'Taylor', 'Brown', 'Williams', 'Wilson', 'Evans',
                 'Thomas', 'Roberts', 'Walker', 'Wright', 'Robinson', 'Thompson', 'White'],
        'cities': [('London', 'England'), ('Manchester', 'England'), ('Birmingham', 'England'),
                   ('Leeds', 'England'), ('Glasgow', 'Scotland'), ('Edinburgh', 'Scotland'),
                   ('Bristol', 'England'), ('Cardiff', 'Wales')],
    },
    'BANK005': {  # Lion City Bank Ltd — Singapore
        'name': 'Lion City Bank Ltd', 'stem': 'LION', 'short': 'LIONCITY', 'n': 18, 'country_code': 'SGP',
        'principal': (2_200_000, 5_200_000), 'balance': (1_600_000, 3_600_000),
        'first': ['Wei', 'Jun', 'Hui', 'Ming', 'Mei', 'Xin', 'Jia', 'Kai', 'Ling', 'Yan',
                  'Arjun', 'Priya', 'Ahmad', 'Nurul', 'Siti', 'Daniel', 'Rachel', 'Marcus'],
        'last': ['Tan', 'Lim', 'Lee', 'Ng', 'Wong', 'Chan', 'Goh', 'Koh', 'Teo', 'Ong',
                 'Kumar', 'Raman', 'Abdullah', 'Ismail'],
        'cities': [('Singapore', 'Central'), ('Jurong', 'West'), ('Tampines', 'East'),
                   ('Woodlands', 'North'), ('Bedok', 'East'), ('Punggol', 'North-East')],
    },
    'BANK006': {  # Gulf Union Bank PJSC — UAE
        'name': 'Gulf Union Bank PJSC', 'stem': 'GULF', 'short': 'GULFUNION', 'n': 14, 'country_code': 'ARE',
        'principal': (2_000_000, 5_000_000), 'balance': (1_500_000, 3_200_000),
        'first': ['Mohammed', 'Ahmed', 'Ali', 'Omar', 'Khalid', 'Hassan', 'Saeed', 'Rashid',
                  'Fatima', 'Aisha', 'Mariam', 'Layla', 'Noura', 'Hessa', 'Sara', 'Yousef'],
        'last': ['Al Maktoum', 'Al Nahyan', 'Al Qasimi', 'Al Falasi', 'Al Suwaidi', 'Khan',
                 'Hassan', 'Abdullah', 'Rahman', 'Sharma', 'Patel', 'Ahmed'],
        'cities': [('Dubai', 'Dubai'), ('Abu Dhabi', 'Abu Dhabi'), ('Sharjah', 'Sharjah'),
                   ('Ajman', 'Ajman'), ('Al Ain', 'Abu Dhabi')],
    },
}

# loan products (names match regulatory_engine RISK_WEIGHT_BY_TYPE keys), purpose_enc
LOAN_TYPES = [('Home Loan', 5), ('Vehicle Loan', 3), ('Personal Loan', 1),
              ('Education Loan', 4), ('Business Loan', 2)]
RISKY_LOANS = [('Personal Loan', 1), ('Business Loan', 2)]

# ref_lookup codes (must match ref_lookup table; index+1 = risk_order)
EMP_LABELS = ['GOVT', 'SALARIED', 'RETIRED', 'SELF_EMPLOYED', 'BUSINESS', 'FREELANCE', 'STUDENT']
EDU_LABELS = ['PHD', 'PROFESSIONAL', 'POST_GRADUATE', 'GRADUATE', 'DIPLOMA', 'HIGH_SCHOOL']
RES_LABELS = ['OWNED', 'RENTED', 'FAMILY', 'EMPLOYER']


_LTYPE_TO_PURPOSE = {
    'Home Loan': 'HOME_PURCHASE', 'Vehicle Loan': 'VEHICLE',
    'Personal Loan': 'PERSONAL', 'Education Loan': 'EDUCATION', 'Business Loan': 'BUSINESS',
}

def _ltype_to_purpose(ltype):
    return _LTYPE_TO_PURPOSE.get(ltype, 'PERSONAL')

def determine_exposure_class(loan_type, employment_type):
    """Map loan type + employment to Basel III.1 exposure class."""
    if loan_type == 'Home Loan':
        return 'RETAIL_MORTGAGES'
    if loan_type in ('Vehicle Loan', 'Personal Loan', 'Education Loan'):
        return 'RETAIL_OTHER'
    if loan_type == 'Business Loan':
        return 'SME' if employment_type in ('BUSINESS', 'SELF_EMPLOYED') else 'CORPORATE'
    return 'CORPORATE'  # fallback

def _emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def _branches(cur, bank_id, cfg):
    """Create 3 branches for a bank (idempotent)."""
    stem, short = cfg['stem'], cfg['short']
    rows = []
    for i, (city, state) in enumerate(cfg['cities'][:3], start=1):
        bid = f"BR-{short}-{i:03d}"
        ifsc = f"{stem}000000{i}"
        rows.append((bid, bank_id, f"{city} Branch", ifsc, city, state,
                     str(random.randint(10000, 99999)), f"{city}", None, 'Active'))
    cur.executemany(
        "INSERT OR IGNORE INTO branches (branch_id,bank_id,branch_name,ifsc_code,city,"
        "state,pincode,address,contact_phone,status) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return [(r[0], r[3]) for r in rows]   # (branch_id, ifsc)


def _seed_bank(cur, bank_id, cfg, today):
    branches = _branches(cur, bank_id, cfg)
    n = cfg['n']
    p_lo, p_hi = cfg['principal']
    b_lo, b_hi = cfg['balance']
    added = 0
    npa = 0
    for k in range(n):
        idx = k + 1
        branch, ifsc = random.choice(branches)
        cid = f"{cfg['stem']}CUST{idx:03d}"
        lid = f"{cfg['short']}-LN-{idx:05d}"
        aid = f"ACC-{cfg['short']}-{idx:04d}"

        first = random.choice(cfg['first'])
        last = random.choice(cfg['last'])
        city, state = random.choice(cfg['cities'])
        tier = random.choice([1, 1, 2])

        # ── Realistic credit quality: continuous features + shared formula ────
        good = random.random() < 0.82          # ~18% distressed
        rng = np.random.default_rng(seed=random.randint(1, 1000000))

        if good:
            # Good customer: higher income, better ratios
            de_true     = float(rng.exponential(scale=0.7).clip(0.1, 2.5))
            ic_true     = float(rng.gamma(shape=3.0, scale=2.5).clip(3.5, 15.0))
            profit_true = float(rng.normal(loc=15.0, scale=8.0).clip(5.0, 60.0))
            liq_true    = float(rng.gamma(shape=4.0, scale=0.5).clip(1.3, 4.0))
            income      = random.randint(1_200_000, 6_000_000)
            late        = 0
            prev_def    = 0
        else:
            # At-risk customer: lower income, weaker ratios
            de_true     = float(rng.exponential(scale=1.5).clip(2.0, 8.0))
            ic_true     = float(rng.gamma(shape=2.0, scale=1.0).clip(1.0, 3.5))
            profit_true = float(rng.normal(loc=-1.0, scale=10.0).clip(-50.0, 10.0))
            liq_true    = float(rng.gamma(shape=2.0, scale=0.3).clip(0.5, 2.0))
            income      = random.randint(500_000, 2_000_000)
            late        = random.randint(2, 8)
            prev_def    = 1 if random.random() < 0.5 else 0

        # CIBIL correlated with income and tenure
        age = random.randint(25, 62)
        years_emp = round(random.uniform(1, min(age - 22, 30)), 1)
        cibil_base = 680 + (np.log(max(income, 100000)) - 12.5) * 30 + years_emp * 2
        cibil_true = int(cibil_base + rng.normal(0, 20).clip(300, 900))

        foir_true = float(rng.beta(2.2, 3.5).clip(0.05, 0.75))

        # Add measurement noise (observed ≠ true)
        noisy = add_measurement_noise(
            rng, de_true, ic_true, profit_true, liq_true,
            income, years_emp, foir_true
        )
        de      = round(noisy['de_ratio'], 2)
        ic      = round(noisy['int_coverage'], 2)
        profit  = round(noisy['profitability'], 1)
        liq     = round(noisy['liquidity_ratio'], 2)
        cibil   = int(noisy['cibil_score'] if noisy.get('cibil_score') else cibil_true)
        foir    = round(noisy['foir'], 2)

        # Employment and other attributes
        emp_enc = random.randint(1, 7); edu_enc = random.randint(3, 6); res_enc = random.randint(1, 4)
        ltype, purpose_enc = random.choice(RISKY_LOANS if not good else LOAN_TYPES)
        emp_label = EMP_LABELS[emp_enc - 1]
        exposure_class = determine_exposure_class(ltype, emp_label)
        deps = random.randint(0, 4); months_cust = random.randint(6, 200)
        ex_loans = random.randint(0, 4); ex_products = random.randint(1, 6)

        # Compute PD using shared formula (stable regime, no macro effects)
        pd_obs = round(true_pd_nonlinear(de, ic, profit, liq, cibil, foir, regime_multiplier=1.0), 4)
        default_flag = 1 if random.random() < pd_obs else 0

        principal = random.randint(p_lo // 100000, p_hi // 100000) * 100000
        outstanding = round(principal * random.uniform(0.55, 0.95), 2)
        rate = round(random.uniform(8.5, 15.5), 2)
        tenure = random.choice([36, 48, 60, 84, 120, 180, 240])
        loan_emi = _emi(principal, rate, tenure)
        classification = 'NPA' if (default_flag and random.random() < 0.6) else 'Standard'
        if classification == 'NPA':
            npa += 1
        disb = date(2022 + random.randint(0, 2), random.randint(1, 12), random.randint(1, 28)).isoformat()
        mat = date(2022 + tenure // 12, random.randint(1, 12), 28).isoformat()
        balance = round(random.uniform(b_lo, b_hi), 2)
        obs = today.isoformat()
        now = datetime.now().isoformat(timespec='seconds')
        dob = date(today.year - age, random.randint(1, 12), random.randint(1, 28)).isoformat()

        cur.execute("INSERT OR IGNORE INTO customers (id,bank_id,first,last,dob,gender,email,phone,"
                    "address,city,state,pincode,joined,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, bank_id, first, last, dob, random.choice(['Male', 'Female']),
                     f"{first.lower()}.{last.lower().replace(' ', '')}{idx}@example.com",
                     f"+{random.randint(1, 971)}{random.randint(1000000, 9999999)}",
                     f"{random.randint(1, 999)} High Street", city, state,
                     str(random.randint(10000, 99999)), '2022-01-10', 'Active'))

        cur.execute("INSERT OR IGNORE INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (aid, bank_id, cid, 'Savings', balance, '2022-01-10', branch, ifsc, 'Active'))
        cur.execute("INSERT OR IGNORE INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"TX-{cfg['short']}-{idx:04d}", bank_id, aid, '2022-01-10', '10:00:00', 'Deposit',
                     balance, balance, '[INCOME] Opening deposit - account funded'))

        cur.execute("INSERT OR IGNORE INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,"
                    "maturity,outstanding,status,branch_id,loan_classification,exposure_class) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (lid, bank_id, cid, ltype, principal, rate, tenure, loan_emi, disb, mat,
                     outstanding, 'Active', branch, classification, exposure_class))

        cur.execute("INSERT OR IGNORE INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,"
                    "kyc_date,age,gender,marital_status,education_level,num_dependents,employment_type,employer_name,"
                    "industry_sector,years_employed,annual_income,other_income,foir_declared,residence_type,"
                    "years_at_address,city_tier,is_pep,risk_category,created_at,updated_at,months_as_customer,"
                    "num_existing_products,existing_loans_count,loan_purpose,previous_default_flag,cibil_score,"
                    "num_late_payments_past_12m,state,is_rural) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, bank_id, 1, 1, 'VERIFIED', '2022-01-05', age, 'Male', 'MARRIED',
                     EDU_LABELS[edu_enc - 1], deps, EMP_LABELS[emp_enc - 1], 'Employer Ltd', 'Services',
                     years_emp, income, 0, foir, RES_LABELS[res_enc - 1], round(random.uniform(1, 15), 1),
                     f"TIER{tier}", 0, 'HIGH' if not good else 'LOW', now, now, months_cust, ex_products,
                     ex_loans, _ltype_to_purpose(ltype), prev_def, cibil, late, state, 0))

        # Prior values: uniform origination baseline (same distribution for all loans)
        prior_de    = round(random.uniform(0.5, 1.8), 4)
        prior_cibil = random.randint(710, 820)

        cur.execute("INSERT OR IGNORE INTO credit_risk_metrics (bank_id,lid,de,intcov,profit,liq,df,pd_score,"
                    "npa_flag,period,obs,prior_de,prior_cibil) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (bank_id, lid, de, ic, profit, liq, default_flag, pd_obs,
                     1 if classification == 'NPA' else 0, '2024-Q2', obs,
                     prior_de, prior_cibil))

        months_orig = round((today - date.fromisoformat(disb)).days / 30.44, 1)
        macro_row = cur.execute(
            "SELECT gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct "
            "FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
            (cfg.get('country_code', ''),)).fetchone() or (4.0, 4.5, 5.0, 6.0)

        cur.execute("INSERT OR IGNORE INTO bank_loan_metrics (bank_id,bank_name,loan_id,de_ratio,interest_coverage,"
                    "profitability,liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,age,"
                    "employment_type_enc,years_employed,annual_income,foir,num_dependents,city_tier_enc,education_enc,"
                    "residence_type_enc,loan_purpose_enc,cibil_score,previous_default_flag,months_as_customer,"
                    "num_late_payments_past_12m,existing_loans_count,num_existing_products,is_rural,country_code,"
                    "gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct,"
                    "delta_de_ratio,delta_cibil,months_since_origination) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (bank_id, cfg['name'], lid, de, ic, profit, liq, default_flag, pd_obs, obs, now,
                     age, emp_enc, years_emp, income, foir, deps, tier, edu_enc, res_enc, purpose_enc,
                     cibil, prev_def, months_cust, late, ex_loans, ex_products, 0,
                     cfg.get('country_code', ''),
                     macro_row[0], macro_row[1], macro_row[2], macro_row[3],
                     round(de - prior_de, 4), round(float(cibil - prior_cibil), 1), months_orig))
        added += 1
    return added, npa


def seed(db_path=DB_PATH, verbose=True):
    random.seed(2027)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    today = date.today()
    results = []
    for bank_id, cfg in BANKS.items():
        existing = cur.execute("SELECT COUNT(*) FROM customers WHERE bank_id=?", (bank_id,)).fetchone()[0]
        if existing:
            if verbose:
                print(f"{bank_id} {cfg['name']}: already has {existing} customers — skipped")
            continue
        added, npa = _seed_bank(cur, bank_id, cfg, today)
        results.append((bank_id, cfg['name'], added, npa))
    conn.commit()

    if verbose and results:
        for bank_id, name, added, npa in results:
            adv = cur.execute("SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?",
                              (bank_id,)).fetchone()[0]
            dep = cur.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE bank_id=?",
                              (bank_id,)).fetchone()[0]
            print(f"{bank_id} {name:32s} +{added} customers ({npa} NPA)  "
                  f"advances Rs {adv:,.0f}  deposits Rs {dep:,.0f}  LDR {adv / (dep or 1) * 100:,.0f}%")
    conn.close()
    return results


if __name__ == '__main__':
    seed()
