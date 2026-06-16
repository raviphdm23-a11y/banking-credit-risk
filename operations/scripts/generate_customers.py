"""
generate_customers.py
─────────────────────
Generates 48 new customers across BANK001 (HDFC) and BANK002 (ICICI),
each with: customer, account, loan, credit_risk_metrics, customer_kyc.
8 of 48 are marked default (NPA) to give a realistic ~16% default rate.
Run sync_bank_loan_metrics.py afterward to populate bank_loan_metrics.
"""

import os
import sqlite3
import random
import math
from datetime import date, timedelta

random.seed(42)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')
conn = sqlite3.connect(DB_PATH)
today = date.today()

# ── Reference data ─────────────────────────────────────────────────────────────

BANKS = [
    ("BANK001", [
        ("BR-HDFC-001", "HDFC0000001"),
        ("BR-HDFC-002", "HDFC0000002"),
        ("BR-HDFC-003", "HDFC0000003"),
    ]),
    ("BANK002", [
        ("BR-ICICI-001", "ICIC0000001"),
        ("BR-ICICI-002", "ICIC0000002"),
        ("BR-ICICI-003", "ICIC0000003"),
    ]),
]

MALE_NAMES   = ["Arjun","Kiran","Suresh","Ramesh","Vikram","Anil","Deepak","Sanjay",
                "Manish","Rohit","Amit","Rahul","Nitin","Rajiv","Vikas","Santosh",
                "Mahesh","Dinesh","Ashok","Ravi","Ganesh","Sunil","Pavan","Kartik","Naveen"]
FEMALE_NAMES = ["Sunita","Kavita","Pooja","Neha","Anjali","Deepa","Meera","Rekha",
                "Lalitha","Suman","Anita","Geeta","Savita","Usha","Lata","Vandana",
                "Nandini","Padma","Divya","Shweta","Aparna","Smita","Jyoti"]
LAST_NAMES   = ["Sharma","Kumar","Singh","Patel","Gupta","Verma","Rao","Joshi",
                "Nair","Reddy","Mehta","Shah","Iyer","Pillai","Desai","Bose",
                "Das","Agarwal","Mishra","Tiwari","Pandey","Srivastava","Yadav","Dubey"]

# (city, state, pincode_prefix, tier, is_rural)
CITIES = [
    ("Mumbai",       "Maharashtra",    "400", "TIER1", 0),
    ("New Delhi",    "Delhi",          "110", "TIER1", 0),
    ("Bangalore",    "Karnataka",      "560", "TIER1", 0),
    ("Chennai",      "Tamil Nadu",     "600", "TIER1", 0),
    ("Hyderabad",    "Telangana",      "500", "TIER1", 0),
    ("Pune",         "Maharashtra",    "411", "TIER1", 0),
    ("Kolkata",      "West Bengal",    "700", "TIER1", 0),
    ("Ahmedabad",    "Gujarat",        "380", "TIER1", 0),
    ("Jaipur",       "Rajasthan",      "302", "TIER2", 0),
    ("Lucknow",      "Uttar Pradesh",  "226", "TIER2", 0),
    ("Indore",       "Madhya Pradesh", "452", "TIER2", 0),
    ("Surat",        "Gujarat",        "395", "TIER2", 0),
    ("Kochi",        "Kerala",         "682", "TIER2", 0),
    ("Chandigarh",   "Punjab",         "160", "TIER2", 0),
    ("Nagpur",       "Maharashtra",    "440", "TIER2", 0),
    ("Varanasi",     "Uttar Pradesh",  "221", "TIER3", 0),
    ("Patna",        "Bihar",          "800", "TIER3", 0),
    ("Coimbatore",   "Tamil Nadu",     "641", "TIER3", 0),
    ("Agra",         "Uttar Pradesh",  "282", "TIER3", 0),
    ("Sikar",        "Rajasthan",      "332", "TIER3", 1),
    ("Nanded",       "Maharashtra",    "431", "TIER3", 1),
]

# (emp_type, income_lo, income_hi, yrs_lo, yrs_hi)
EMP_CONFIGS = {
    "GOVT":         (350000,  1800000, 2,  35),
    "SALARIED":     (250000,  4000000, 1,  25),
    "RETIRED":      (200000,   800000, 0,   5),
    "SELF_EMPLOYED":(300000,  3000000, 3,  20),
    "BUSINESS":     (500000,  8000000, 5,  30),
    "FREELANCE":    (200000,  2000000, 1,  10),
    "STUDENT":      (0,             0, 0,   0),
}

EMPLOYERS = {
    "GOVT":         ["Government of India","State Government","Municipal Corporation","PSU - ONGC","PSU - BHEL","Indian Railways"],
    "SALARIED":     ["Infosys","TCS","Wipro","HCL Technologies","Accenture","Deloitte","HDFC Bank","Axis Bank","Reliance Industries","Mahindra","Cognizant","IBM India"],
    "RETIRED":      ["Retired - Government","Retired - Private Sector"],
    "SELF_EMPLOYED":["Self Employed - Doctor","Self Employed - CA","Self Employed - Architect","Self Employed - Trader","Self Employed - Consultant"],
    "BUSINESS":     ["ABC Enterprises","Singh & Sons Pvt Ltd","Patel Trading Co","Kumar Constructions","Sharma Industries","Gupta Exports"],
    "FREELANCE":    ["Freelance IT Consultant","Freelance Designer","Freelance Content Writer"],
    "STUDENT":      ["Student"],
}

EMP_INDUSTRY = {
    "GOVT":         ["GOVT"],
    "SALARIED":     ["IT","BANKING","HEALTHCARE","MANUFACTURING","RETAIL","TELECOM","FMCG"],
    "RETIRED":      ["GOVT","MANUFACTURING"],
    "SELF_EMPLOYED":["RETAIL","HEALTHCARE","CONSTRUCTION"],
    "BUSINESS":     ["MANUFACTURING","RETAIL","CONSTRUCTION","AGRICULTURE"],
    "FREELANCE":    ["IT","EDUCATION"],
    "STUDENT":      ["EDUCATION"],
}

# (loan_name, loan_purpose, min_p, max_p, rate_lo, rate_hi, tenure_lo, tenure_hi, step)
LOAN_TYPES = [
    ("Home Loan",     "HOME_PURCHASE",      1500000, 10000000, 8.5,  9.5, 120, 240, 12),
    ("Personal Loan", "PERSONAL",            100000,   800000, 12.0, 18.0,  12,  60,  6),
    ("Vehicle Loan",  "VEHICLE",             300000,  1500000,  9.0, 12.0,  36,  84, 12),
    ("Education Loan","EDUCATION",           500000,  2500000, 10.0, 13.0,  60, 120, 12),
    ("Business Loan", "BUSINESS",            500000,  5000000, 12.0, 16.0,  36,  84, 12),
]
RISKY_LOAN_TYPES = [l for l in LOAN_TYPES if l[1] in ("PERSONAL","BUSINESS","DEBT_CONSOLIDATION")]


def emi_calc(principal, annual_rate_pct, tenure_months):
    r = annual_rate_pct / 12 / 100
    return principal * r * (1 + r)**tenure_months / ((1 + r)**tenure_months - 1)


def rand_date(y1, y2):
    s = date(y1, 1, 1)
    e = date(y2, 12, 28)
    return s + timedelta(days=random.randint(0, (e - s).days))


# Indices (0-47) that will be defaulters
DEFAULT_INDICES = {3, 7, 12, 18, 24, 31, 38, 44}

inserted = 0

for i in range(48):
    is_default = (i in DEFAULT_INDICES)

    bank_id, branches = BANKS[i % 2]
    branch_id, ifsc_code = random.choice(branches)
    bank_prefix = "HDFC" if bank_id == "BANK001" else "ICICI"

    cust_id = "CUST{:03d}".format(200 + i)
    loan_id = "{}-LN-{:05d}-G{:03d}".format(bank_prefix, 200 + i, 200 + i)
    acc_id  = "ACC-{}-{:04d}".format(bank_prefix, 200 + i)

    # Demographics
    gender = random.choice(["M", "M", "F"])
    first  = random.choice(MALE_NAMES if gender == "M" else FEMALE_NAMES)
    last   = random.choice(LAST_NAMES)

    city, state, pin_prefix, city_tier, is_rural = random.choice(CITIES)
    pincode = "{}{}".format(pin_prefix, random.randint(100, 999))

    age = random.randint(22, 30) if is_default and random.random() < 0.4 else (
          random.randint(55, 65) if is_default and random.random() < 0.4 else
          random.randint(28, 58))
    dob = date(today.year - age, random.randint(1, 12), random.randint(1, 28))

    # Employment
    if is_default:
        emp_type = random.choice(["SELF_EMPLOYED","BUSINESS","FREELANCE","SALARIED","STUDENT"])
    else:
        emp_type = random.choices(
            ["GOVT","SALARIED","RETIRED","SELF_EMPLOYED","BUSINESS","FREELANCE"],
            weights=[15, 45, 10, 15, 10, 5]
        )[0]

    inc_lo, inc_hi, yrs_lo, yrs_hi = EMP_CONFIGS[emp_type]
    if emp_type == "STUDENT":
        annual_income  = 0
        years_employed = 0
        employer_name  = "Student"
    else:
        annual_income  = random.randint(inc_lo // 1000, inc_hi // 1000) * 1000
        years_employed = round(random.uniform(yrs_lo, yrs_hi), 1)
        employer_name  = random.choice(EMPLOYERS[emp_type])

    industry_sector = random.choice(EMP_INDUSTRY[emp_type])

    # Education
    if emp_type == "STUDENT":
        education_level = random.choice(["GRADUATE", "POST_GRADUATE"])
    elif is_default:
        education_level = random.choice(["HIGH_SCHOOL","DIPLOMA","GRADUATE","POST_GRADUATE"])
    else:
        education_level = random.choices(
            ["PHD","PROFESSIONAL","POST_GRADUATE","GRADUATE","DIPLOMA","HIGH_SCHOOL"],
            weights=[5, 8, 30, 35, 12, 10]
        )[0]

    marital_status = random.choices(
        ["MARRIED","SINGLE","DIVORCED","WIDOWED"], weights=[55, 30, 10, 5]
    )[0]
    num_dependents = (random.randint(1, 4) if marital_status == "MARRIED" else
                      random.randint(0, 2) if marital_status in ("DIVORCED","WIDOWED") else 0)

    if emp_type == "STUDENT":
        residence_type = random.choice(["FAMILY","EMPLOYER"])
    else:
        residence_type = random.choices(
            ["OWNED","FAMILY","EMPLOYER","RENTED"], weights=[25, 20, 10, 45]
        )[0]

    years_at_address = round(random.uniform(0.5, 15), 1)

    # Bank relationship
    joined = rand_date(2017, 2025)
    months_as_customer = max(0, (today.year - joined.year) * 12 + (today.month - joined.month))

    # Context / bureau data
    if is_default:
        cibil_score            = random.randint(300, 570)
        previous_default_flag  = random.choice([0, 1, 1])
        num_late_payments      = random.randint(3, 12)
        existing_loans_count   = random.randint(2, 6)
    else:
        cibil_score            = random.randint(650, 900)
        previous_default_flag  = 0
        num_late_payments      = random.randint(0, 1)
        existing_loans_count   = random.randint(0, 3)

    num_existing_products = random.randint(1, 5)

    # Loan
    if emp_type == "STUDENT":
        lt = next(l for l in LOAN_TYPES if l[1] == "EDUCATION")
    elif is_default:
        lt = random.choice(RISKY_LOAN_TYPES)
    else:
        lt = random.choice(LOAN_TYPES)

    ln_name, ln_purpose, min_p, max_p, r_lo, r_hi, t_lo, t_hi, t_step = lt
    principal = random.randint(min_p // 1000, max_p // 1000) * 1000
    rate      = round(random.uniform(r_lo, r_hi), 2)
    tenure    = random.choice(range(t_lo, t_hi + 1, t_step))
    emi       = round(emi_calc(principal, rate, tenure), 2)

    disbursed = rand_date(2019, 2025)
    m_end     = disbursed.month + tenure - 1
    maturity  = date(disbursed.year + m_end // 12, m_end % 12 + 1, min(disbursed.day, 28))

    months_elapsed = max(0, (today.year - disbursed.year) * 12 + (today.month - disbursed.month))
    outstanding    = round(max(0, principal - emi * months_elapsed * 0.3), 2)

    foir = round(emi / (annual_income / 12), 4) if annual_income > 0 else 0.50
    foir = min(foir, 0.89)

    loan_classification = "NPA" if is_default else "Standard"

    # Credit risk metrics
    if is_default:
        de       = round(random.uniform(4.5, 9.0), 4)
        intcov   = round(random.uniform(0.4, 1.4), 4)
        profit   = round(random.uniform(-15.0, 4.0), 4)
        liq      = round(random.uniform(0.3, 0.9), 4)
        pd_score = round(random.uniform(0.35, 0.80), 6)
        npa_flag = 1
    else:
        de       = round(random.uniform(0.3, 3.8), 4)
        intcov   = round(random.uniform(2.0, 15.0), 4)
        profit   = round(random.uniform(5.0, 30.0), 4)
        liq      = round(random.uniform(1.1, 4.5), 4)
        pd_score = round(random.uniform(0.01, 0.14), 6)
        npa_flag = 0

    risk_cat = "HIGH" if is_default else ("MEDIUM" if cibil_score < 720 else "LOW")
    kyc_date = joined + timedelta(days=random.randint(0, 30))
    period   = "{}-{:02d}".format(today.year, today.month)

    # ── Inserts ────────────────────────────────────────────────────────────────

    conn.execute("""
        INSERT OR IGNORE INTO customers
            (id, bank_id, first, last, dob, gender, email, phone,
             address, city, state, pincode, joined, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (cust_id, bank_id, first, last, dob.isoformat(), gender,
          "{}.{}{}@gmail.com".format(first.lower(), last.lower(), i),
          "9{}".format(random.randint(100000000, 999999999)),
          "{} Main Street, {}".format(random.randint(1, 99), city),
          city, state, pincode, joined.isoformat(), "Active"))

    conn.execute("""
        INSERT OR IGNORE INTO accounts
            (id, bank_id, cid, type, balance, open_date, branch_id, ifsc_code, status)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (acc_id, bank_id, cust_id, "Savings",
          round(random.uniform(5000, 500000), 2),
          joined.isoformat(), branch_id, ifsc_code, "Active"))

    conn.execute("""
        INSERT OR IGNORE INTO loans
            (id, bank_id, cid, type, principal, rate, tenure, emi, disbursed, maturity,
             outstanding, status, branch_id, loan_classification)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (loan_id, bank_id, cust_id, ln_name, principal, rate, tenure, emi,
          disbursed.isoformat(), maturity.isoformat(),
          outstanding, "Active", branch_id, loan_classification))

    conn.execute("""
        INSERT OR IGNORE INTO credit_risk_metrics
            (bank_id, lid, de, intcov, profit, liq, df, pd_score, npa_flag, period, obs)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (bank_id, loan_id, de, intcov, profit, liq,
          1 if is_default else 0, pd_score, npa_flag, period, today.isoformat()))

    conn.execute("""
        INSERT OR IGNORE INTO customer_kyc
            (cid, bank_id, pan_verified, aadhaar_verified, kyc_status, kyc_date,
             age, gender, marital_status, education_level, num_dependents,
             employment_type, employer_name, industry_sector, years_employed,
             annual_income, other_income, foir_declared, residence_type,
             years_at_address, city_tier, is_pep, risk_category,
             months_as_customer, num_existing_products, existing_loans_count,
             loan_purpose, previous_default_flag, cibil_score,
             num_late_payments_past_12m, state, is_rural, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (cust_id, bank_id, 1, 1, "VERIFIED", kyc_date.isoformat(),
          age, gender, marital_status, education_level, num_dependents,
          emp_type, employer_name, industry_sector, years_employed,
          annual_income, 0, foir, residence_type, years_at_address,
          city_tier, 0, risk_cat,
          months_as_customer, num_existing_products, existing_loans_count,
          ln_purpose, previous_default_flag, cibil_score,
          num_late_payments, state, is_rural,
          today.isoformat() + " 00:00:00", today.isoformat() + " 00:00:00"))

    flag_label = "DEFAULT" if is_default else "OK     "
    print("[{}] {} | {} {} | {} | CIBIL:{} | Income:{:,.0f} | PD:{:.4f}".format(
        flag_label, cust_id, first, last, emp_type, cibil_score, annual_income, pd_score))
    inserted += 1

conn.commit()
conn.close()
print("\nDone. Inserted {} customers.".format(inserted))
