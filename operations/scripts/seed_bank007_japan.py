"""
seed_bank007_japan.py
─────────────────────
One-shot: creates BANK007 (Nippon Commercial Bank Ltd., Japan) with:
  - bank master row + branch
  - 30 initial customers with full records
    (customers + customer_kyc + accounts + opening deposit txn +
     loans + credit_risk_metrics + bank_loan_metrics)
Idempotent: skips customer seeding if BANK007 already has customers.
"""
import os, sqlite3, random
from datetime import date, datetime

random.seed(20260801)

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB    = os.path.join(_REPO, 'bank.db')

BANK_ID   = 'BANK007'
BANK_NAME = 'Nippon Commercial Bank Ltd.'
BRANCH_ID = 'BR-NIPPON-001'
IFSC      = 'NPCB0000001'
N_CUSTOMERS = 30

FIRST_NAMES = [
    'Hiroshi', 'Kenji', 'Takashi', 'Ryota', 'Shota', 'Daiki', 'Kazuki', 'Naoki', 'Masato', 'Yuto',
    'Sakura', 'Hana', 'Aiko', 'Nana', 'Mio', 'Rin', 'Yui', 'Saki', 'Mei', 'Akane',
]
LAST_NAMES  = [
    'Tanaka', 'Suzuki', 'Watanabe', 'Ito', 'Yamamoto', 'Nakamura',
    'Kobayashi', 'Kato', 'Sato', 'Yoshida', 'Hayashi', 'Kimura', 'Matsumoto',
]
CITIES = ['Tokyo', 'Osaka', 'Nagoya', 'Yokohama', 'Kyoto', 'Fukuoka']

LOAN_TYPES = [('Home Loan', 5), ('Vehicle Loan', 3), ('Personal Loan', 1),
              ('Education Loan', 4), ('Business Loan', 2)]

PRINCIPAL_RANGE = (2_000_000, 5_500_000)
BALANCE_RANGE   = (1_400_000, 3_800_000)


def emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def main():
    conn = sqlite3.connect(DB)
    cur  = conn.cursor()

    # ── 1. Bank master row ─────────────────────────────────────────────────
    cur.execute("SELECT bank_id FROM banks WHERE bank_id=?", (BANK_ID,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO banks (bank_id, bank_name, bank_code, country, headquarters_city, "
            "headquarters_state, year_established, status, country_code) VALUES (?,?,?,?,?,?,?,?,?)",
            (BANK_ID, BANK_NAME, 'NCB007', 'Japan', 'Tokyo', 'Tokyo', 1962, 'Active', 'JPN')
        )
        print(f"  Created bank master row: {BANK_ID} — {BANK_NAME}")
    else:
        print(f"  Bank {BANK_ID} already exists, skipping master row.")

    # ── 2. Branch ──────────────────────────────────────────────────────────
    cur.execute("SELECT branch_id FROM branches WHERE branch_id=?", (BRANCH_ID,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO branches (branch_id, bank_id, branch_name, city, state, ifsc_code, status) "
            "VALUES (?,?,?,?,?,?,?)",
            (BRANCH_ID, BANK_ID, 'Nippon Commercial Bank — Tokyo Main', 'Tokyo', 'Tokyo', IFSC, 'Active')
        )

    # ── 3. Customers ───────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM customers WHERE bank_id=?", (BANK_ID,))
    if cur.fetchone()[0] > 0:
        print(f"  BANK007 already has customers — skipping seed.")
        conn.close()
        return

    start = (cur.execute(
        "SELECT MAX(CAST(SUBSTR(id,5) AS INTEGER)) FROM customers WHERE id LIKE 'CUST%'"
    ).fetchone()[0] or 0) + 1

    added = []
    for i in range(N_CUSTOMERS):
        idx  = start + i
        cid  = f"CUST{idx}"
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        city  = random.choice(CITIES)
        now   = datetime.now().isoformat(timespec='seconds')
        obs   = date.today().isoformat()

        good = random.random() < 0.55
        if good:
            de = round(random.uniform(0.4, 1.5), 2);  ic = round(random.uniform(5.0, 14.0), 2)
            pm = round(random.uniform(8.0, 22.0), 1);  lq = round(random.uniform(1.5, 2.8), 2)
            cibil = random.randint(740, 830);           foir = round(random.uniform(0.18, 0.38), 2)
            late = 0;  prev_def = 0;                    income = random.randint(1_000_000, 5_500_000)
        else:
            de = round(random.uniform(2.5, 6.0), 2);   ic = round(random.uniform(0.8, 2.5), 2)
            pm = round(random.uniform(-8.0, 5.0), 1);  lq = round(random.uniform(0.6, 1.2), 2)
            cibil = random.randint(550, 680);           foir = round(random.uniform(0.50, 0.88), 2)
            late = random.randint(1, 7);               prev_def = 1 if random.random() < 0.4 else 0
            income = random.randint(400_000, 1_800_000)

        age         = random.randint(24, 62)
        years_emp   = round(random.uniform(1.0, min(age - 22, 32)), 1)
        emp_enc     = random.randint(1, 7)
        edu_enc     = random.randint(1, 6)
        res_enc     = random.randint(1, 4)
        ltype, purpose_enc = random.choice(LOAN_TYPES)
        deps        = random.randint(0, 4)
        months_cust = random.randint(3, 200)
        ex_loans    = random.randint(0, 4)
        ex_products = random.randint(1, 6)
        tier        = 1  # all cities are tier-1 urban Japan

        risk = (0.01 + max(0, (750 - cibil)) / 900.0 + de * 0.025
                + max(0, 3 - ic) * 0.05 + max(0, foir - 0.40) * 0.6
                + prev_def * 0.20 + late * 0.03 + (0.05 if pm < 0 else 0))
        pd_obs       = round(min(0.95, max(0.005, risk)), 4)
        default_flag = 1 if random.random() < pd_obs else 0

        principal   = random.randint(PRINCIPAL_RANGE[0] // 100_000,
                                     PRINCIPAL_RANGE[1] // 100_000) * 100_000
        outstanding = round(principal * random.uniform(0.55, 0.98), 2)
        rate        = round(random.uniform(8.0, 14.5), 2)
        tenure      = random.choice([36, 48, 60, 84, 120, 180])
        loan_emi    = emi(principal, rate, tenure)
        classif     = 'NPA' if (default_flag and random.random() < 0.6) else 'Standard'
        disb        = date(2023, random.randint(1, 12), random.randint(1, 28)).isoformat()
        mat         = date(2023 + tenure // 12, random.randint(1, 12), 28).isoformat()

        lid     = f"NIPPON-LN-{idx:05d}-N{idx}"
        aid     = f"ACC-NIPPON-{idx:04d}"
        balance = round(random.uniform(BALANCE_RANGE[0], BALANCE_RANGE[1]), 2)

        cur.execute(
            "INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,"
            "address,city,state,pincode,joined,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, BANK_ID, first, last, f"{1966+(60-age)}-06-15",
             random.choice(['Male', 'Female']),
             f"{first.lower()}.{last.lower()}{idx}@example.com",
             f"+81-{random.randint(10,99)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
             f"{random.randint(1,99)} Chome", city, city,
             str(random.randint(100_0000, 999_9999)),
             date.today().isoformat(), 'Active'))

        cur.execute(
            "INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (aid, BANK_ID, cid, 'Savings', balance, '2024-01-10', BRANCH_ID, IFSC, 'Active'))

        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (f"TX-NEW-{idx}", BANK_ID, aid, '2024-01-10', '10:00:00', 'Deposit',
             balance, balance, '[INCOME] Opening deposit - account funded'))

        cur.execute(
            "INSERT INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,maturity,"
            "outstanding,status,branch_id,loan_classification) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, BANK_ID, cid, ltype, principal, rate, tenure, loan_emi, disb, mat,
             outstanding, 'Active', BRANCH_ID, classif))

        cur.execute(
            "INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,"
            "age,gender,marital_status,education_level,num_dependents,employment_type,employer_name,"
            "industry_sector,years_employed,annual_income,other_income,foir_declared,residence_type,"
            "years_at_address,city_tier,is_pep,risk_category,created_at,updated_at,months_as_customer,"
            "num_existing_products,existing_loans_count,loan_purpose,previous_default_flag,cibil_score,"
            "num_late_payments_past_12m,state,is_rural) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, BANK_ID, 1, 1, 'Verified', '2024-01-05', age,
             random.choice(['Male', 'Female']), 'Married',
             ['Below 10th','10th','12th','Graduate','Post-Graduate','Doctorate'][edu_enc - 1],
             deps,
             ['Salaried-Govt','Salaried-Private','Self-Employed-Prof','Self-Employed-Business',
              'Retired','Freelance','Student'][emp_enc - 1],
             f"Nippon Corp", 'Financial Services', years_emp, income, 0, foir,
             ['Owned','Rented','Parental','Company'][res_enc - 1],
             round(random.uniform(1, 20), 1), f"Tier-{tier}", 0,
             'High' if not good else 'Low', now, now, months_cust, ex_products, ex_loans,
             ltype, prev_def, cibil, late, city, 0))

        cur.execute(
            "INSERT INTO credit_risk_metrics (bank_id,lid,de,intcov,profit,liq,df,pd_score,"
            "npa_flag,period,obs) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (BANK_ID, lid, de, ic, pm, lq, default_flag, pd_obs,
             1 if classif == 'NPA' else 0, '2025-Q1', obs))

        cur.execute(
            "INSERT INTO bank_loan_metrics (bank_id,bank_name,loan_id,de_ratio,interest_coverage,"
            "profitability,liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,age,"
            "employment_type_enc,years_employed,annual_income,foir,num_dependents,city_tier_enc,"
            "education_enc,residence_type_enc,loan_purpose_enc,cibil_score,previous_default_flag,"
            "months_as_customer,num_late_payments_past_12m,existing_loans_count,num_existing_products,"
            "is_rural) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (BANK_ID, BANK_NAME, lid, de, ic, pm, lq, default_flag, pd_obs, obs, now,
             age, emp_enc, years_emp, income, foir, deps, tier, edu_enc, res_enc, purpose_enc,
             cibil, prev_def, months_cust, late, ex_loans, ex_products, 0))

        added.append((cid, f"{first} {last}", 'good' if good else 'risky', pd_obs, classif))

    conn.commit()
    conn.close()

    print(f"\n  Seeded {len(added)} customers for {BANK_ID} ({BANK_NAME}):\n")
    print(f"  {'CID':<10} {'Name':<25} {'Profile':<6}  PD      Class")
    print(f"  {'-'*65}")
    for cid, name_, prof, pd_o, cls in added:
        print(f"  {cid:<10} {name_:<25} {prof:<6}  {pd_o:.4f}  {cls}")


if __name__ == '__main__':
    main()
