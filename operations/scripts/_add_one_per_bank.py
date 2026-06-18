"""
_add_one_per_bank.py
────────────────────
One-shot: adds exactly one new customer to each of the 6 group banks.
Follows the same full-record pattern as add_new_customers.py and
seed_global_customers.py (customers + customer_kyc + accounts + opening
deposit txn + loans + credit_risk_metrics + bank_loan_metrics).
"""
import os, sqlite3, random
from datetime import date, datetime

random.seed(20260724)

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB = os.path.join(_REPO, 'bank.db')

BANKS = [
    {
        'bank_id': 'BANK001', 'name': 'HDFC Bank Limited',
        'branch': 'BR-HDFC-002', 'ifsc': 'HDFC0000002',
        'first': ['Aarav','Diya','Kabir','Anaya','Vivaan','Saanvi','Reyansh','Myra'],
        'last':  ['Malhotra','Kapoor','Bhat','Menon','Chauhan','Pillai','Saxena'],
        'cities': [('Mumbai','Maharashtra',1),('Pune','Maharashtra',2),('Bengaluru','Karnataka',1)],
        'principal': (500_000, 4_000_000), 'balance': (80_000, 800_000),
        'state_field': True,
    },
    {
        'bank_id': 'BANK002', 'name': 'ICICI Bank Limited',
        'branch': 'BR-ICICI-002', 'ifsc': 'ICIC0000002',
        'first': ['Arjun','Kiara','Ishaan','Riya','Aditya','Ira','Krishna','Aadhya'],
        'last':  ['Bose','Nayak','Gill','Saxena','Menon','Chauhan','Pillai'],
        'cities': [('Delhi','Delhi',1),('Hyderabad','Telangana',1),('Chennai','Tamil Nadu',1)],
        'principal': (500_000, 4_000_000), 'balance': (80_000, 800_000),
        'state_field': True,
    },
    {
        'bank_id': 'BANK003', 'name': 'Atlas Bank N.A.',
        'branch': 'BR-ATLAS-002', 'ifsc': 'ATLS0000002',
        'first': ['James','Michael','Robert','David','Emily','Jessica','Sarah','Daniel'],
        'last':  ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis'],
        'cities': [('New York','NY',1),('Chicago','IL',1),('San Francisco','CA',1),('Boston','MA',1)],
        'principal': (2_500_000, 6_000_000), 'balance': (1_500_000, 3_800_000),
        'state_field': False,
    },
    {
        'bank_id': 'BANK004', 'name': 'Britannia Banking Group plc',
        'branch': 'BR-BRITANNIA-002', 'ifsc': 'BRIT0000002',
        'first': ['Oliver','George','Harry','Jack','Amelia','Olivia','Emily','Daniel'],
        'last':  ['Smith','Jones','Taylor','Brown','Williams','Wilson','Evans','Thomas'],
        'cities': [('London','England',1),('Manchester','England',1),('Edinburgh','Scotland',1)],
        'principal': (2_200_000, 5_500_000), 'balance': (1_400_000, 3_500_000),
        'state_field': False,
    },
    {
        'bank_id': 'BANK005', 'name': 'Lion City Bank Ltd',
        'branch': 'BR-LIONCITY-002', 'ifsc': 'LION0000002',
        'first': ['Wei','Jun','Hui','Ming','Mei','Arjun','Ahmad','Rachel'],
        'last':  ['Tan','Lim','Lee','Ng','Wong','Chan','Goh','Kumar'],
        'cities': [('Singapore','Central',1),('Jurong','West',1),('Tampines','East',1)],
        'principal': (2_200_000, 5_200_000), 'balance': (1_600_000, 3_600_000),
        'state_field': False,
    },
    {
        'bank_id': 'BANK006', 'name': 'Gulf Union Bank PJSC',
        'branch': 'BR-GULFUNION-002', 'ifsc': 'GULF0000002',
        'first': ['Mohammed','Ahmed','Ali','Omar','Fatima','Aisha','Mariam','Khalid'],
        'last':  ['Al-Rashidi','Al-Farsi','Al-Mansoori','Al-Hashimi','Ibrahim','Hassan','Malik'],
        'cities': [('Dubai','Dubai',1),('Abu Dhabi','Abu Dhabi',1),('Sharjah','Sharjah',1)],
        'principal': (1_800_000, 4_500_000), 'balance': (1_200_000, 3_000_000),
        'state_field': False,
    },
]

LOAN_TYPES = [('Home Loan', 5), ('Vehicle Loan', 3), ('Personal Loan', 1),
              ('Education Loan', 4), ('Business Loan', 2)]


def emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # next CUST ID
    start = (cur.execute(
        "SELECT MAX(CAST(SUBSTR(id,5) AS INTEGER)) FROM customers WHERE id LIKE 'CUST%'"
    ).fetchone()[0] or 0) + 1

    added = []
    for i, b in enumerate(BANKS):
        idx = start + i
        cid = f"CUST{idx}"
        bank_id  = b['bank_id']
        bank_name = b['name']
        branch   = b['branch']
        ifsc     = b['ifsc']

        first = random.choice(b['first'])
        last  = random.choice(b['last'])
        city, state, tier = random.choice(b['cities'])
        is_rural = 0

        good = random.random() < 0.55
        if good:
            de = round(random.uniform(0.5, 1.6), 2);  ic = round(random.uniform(4.5, 12), 2)
            profit = round(random.uniform(9, 20), 1);  liq = round(random.uniform(1.5, 2.6), 2)
            cibil = random.randint(740, 820);           foir = round(random.uniform(0.20, 0.40), 2)
            late = 0;  prev_def = 0;                   income = random.randint(900_000, 4_500_000)
        else:
            de = round(random.uniform(2.8, 6.0), 2);  ic = round(random.uniform(1.0, 2.6), 2)
            profit = round(random.uniform(-6, 6), 1);  liq = round(random.uniform(0.7, 1.25), 2)
            cibil = random.randint(560, 690);           foir = round(random.uniform(0.48, 0.85), 2)
            late = random.randint(1, 6);               prev_def = 1 if random.random() < 0.4 else 0
            income = random.randint(300_000, 1_500_000)

        age         = random.randint(24, 60)
        years_emp   = round(random.uniform(1, min(age - 22, 30)), 1)
        emp_enc     = random.randint(1, 7)
        edu_enc     = random.randint(1, 6)
        res_enc     = random.randint(1, 4)
        ltype, purpose_enc = random.choice(LOAN_TYPES)
        deps        = random.randint(0, 4)
        months_cust = random.randint(3, 180)
        ex_loans    = random.randint(0, 4)
        ex_products = random.randint(1, 6)

        risk = (0.01 + max(0, (750 - cibil)) / 900.0 + de * 0.025
                + max(0, 3 - ic) * 0.05 + max(0, foir - 0.40) * 0.6
                + prev_def * 0.20 + late * 0.03 + (0.05 if profit < 0 else 0))
        pd_obs       = round(min(0.95, max(0.005, risk)), 4)
        default_flag = 1 if random.random() < pd_obs else 0

        principal    = random.randint(b['principal'][0] // 100_000,
                                      b['principal'][1] // 100_000) * 100_000
        outstanding  = round(principal * random.uniform(0.55, 0.98), 2)
        rate         = round(random.uniform(8.5, 15.5), 2)
        tenure       = random.choice([36, 48, 60, 84, 120, 180])
        loan_emi     = emi(principal, rate, tenure)
        classification = 'NPA' if (default_flag and random.random() < 0.6) else 'Standard'
        disb = date(2023, random.randint(1, 12), random.randint(1, 28)).isoformat()
        mat  = date(2023 + tenure // 12, random.randint(1, 12), 28).isoformat()

        short = bank_name.split()[0].upper()
        lid = f"{short}-LN-{idx:05d}-N{idx}"
        aid = f"ACC-{short}-{idx:04d}"
        balance = round(random.uniform(b['balance'][0], b['balance'][1]), 2)
        obs = date.today().isoformat()
        now = datetime.now().isoformat(timespec='seconds')

        cur.execute(
            "INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, bank_id, first, last, f"{1966 + (60-age)}-06-15",
             random.choice(['Male', 'Female']),
             f"{first.lower()}.{last.lower()}{idx}@example.com",
             f"9{random.randint(100_000_000, 999_999_999)}",
             f"{random.randint(1, 99)} Main Street", city, state,
             str(random.randint(100_000, 999_999)),
             date.today().isoformat(), 'Active'))

        cur.execute(
            "INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (aid, bank_id, cid, 'Savings', balance, '2024-01-10', branch, ifsc, 'Active'))

        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (f"TX-NEW-{idx}", bank_id, aid, '2024-01-10', '10:00:00', 'Deposit',
             balance, balance, '[INCOME] Opening deposit - account funded'))

        cur.execute(
            "INSERT INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,maturity,"
            "outstanding,status,branch_id,loan_classification) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, bank_id, cid, ltype, principal, rate, tenure, loan_emi, disb, mat,
             outstanding, 'Active', branch, classification))

        cur.execute(
            "INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,"
            "age,gender,marital_status,education_level,num_dependents,employment_type,employer_name,"
            "industry_sector,years_employed,annual_income,other_income,foir_declared,residence_type,"
            "years_at_address,city_tier,is_pep,risk_category,created_at,updated_at,months_as_customer,"
            "num_existing_products,existing_loans_count,loan_purpose,previous_default_flag,cibil_score,"
            "num_late_payments_past_12m,state,is_rural) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, bank_id, 1, 1, 'Verified', '2024-01-05', age,
             random.choice(['Male', 'Female']), 'Married',
             ['Below 10th','10th','12th','Graduate','Post-Graduate','Doctorate'][edu_enc - 1],
             deps,
             ['Salaried-Govt','Salaried-Private','Self-Employed-Prof','Self-Employed-Business','Retired','Freelance','Student'][emp_enc - 1],
             f"{bank_name.split()[0]} Corp", 'Financial Services', years_emp, income, 0, foir,
             ['Owned','Rented','Parental','Company'][res_enc - 1],
             round(random.uniform(1, 15), 1), f"Tier-{tier}", 0,
             'High' if not good else 'Low', now, now, months_cust, ex_products, ex_loans,
             ltype, prev_def, cibil, late, state, is_rural))

        cur.execute(
            "INSERT INTO credit_risk_metrics (bank_id,lid,de,intcov,profit,liq,df,pd_score,npa_flag,period,obs) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (bank_id, lid, de, ic, profit, liq, default_flag, pd_obs,
             1 if classification == 'NPA' else 0, '2025-Q1', obs))

        cur.execute(
            "INSERT INTO bank_loan_metrics (bank_id,bank_name,loan_id,de_ratio,interest_coverage,"
            "profitability,liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,age,"
            "employment_type_enc,years_employed,annual_income,foir,num_dependents,city_tier_enc,"
            "education_enc,residence_type_enc,loan_purpose_enc,cibil_score,previous_default_flag,"
            "months_as_customer,num_late_payments_past_12m,existing_loans_count,num_existing_products,is_rural) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bank_id, bank_name, lid, de, ic, profit, liq, default_flag, pd_obs, obs, now,
             age, emp_enc, years_emp, income, foir, deps, tier, edu_enc, res_enc, purpose_enc,
             cibil, prev_def, months_cust, late, ex_loans, ex_products, is_rural))

        added.append((cid, f"{first} {last}", bank_id, 'good' if good else 'risky', pd_obs, classification))

    conn.commit()
    print(f"\nAdded 1 customer per bank ({len(added)} total):\n")
    print(f"  {'CID':<10} {'Name':<25} {'Bank':<10} {'Profile':<6}  PD      Class")
    print(f"  {'-'*72}")
    for cid, name, bank, prof, pd_o, cls in added:
        print(f"  {cid:<10} {name:<25} {bank:<10} {prof:<6}  {pd_o:.4f}  {cls}")
    cur2 = conn.cursor() if conn else None
    conn2 = sqlite3.connect(DB)
    c2 = conn2.cursor()
    c2.execute("SELECT COUNT(*) FROM customers")
    total = c2.fetchone()[0]
    print(f"\nTotal customers in bank.db: {total}")
    conn2.close()


if __name__ == '__main__':
    main()
