"""
add_new_customers.py
────────────────────
Adds a batch of brand-new customers to bank.db with the full record set the
platform needs: customers, customer_kyc, accounts (+ one opening deposit so the
ledger stays reconciled), loans, credit_risk_metrics, and — crucially — a
bank_loan_metrics row per customer (the 21-feature + target row the PD trainer
consumes). pd_observed / default_flag are generated with a realistic
relationship to the risk drivers so the model has genuine signal to learn from.

Run:  python operations/scripts/add_new_customers.py [N]
"""
import os, sys, sqlite3, random
from datetime import date, datetime

random.seed(2026)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')
N = int(sys.argv[1]) if len(sys.argv) > 1 else 14

BANKS = {'BANK001': ('HDFC Bank Limited', 'BR-HDFC-001', 'HDFC0000001', 'IND'),
         'BANK002': ('ICICI Bank Limited', 'BR-ICICI-001', 'ICIC0000001', 'IND')}
FIRST = ['Aarav','Diya','Kabir','Anaya','Vivaan','Saanvi','Reyansh','Myra','Aditya','Ira',
         'Krishna','Aadhya','Arjun','Kiara','Ishaan','Riya']
LAST  = ['Malhotra','Kapoor','Bhat','Menon','Chauhan','Pillai','Saxena','Bose','Nayak','Gill']
LOAN_TYPES = [('Home Loan', 5), ('Vehicle Loan', 3), ('Personal Loan', 1),
              ('Education Loan', 4), ('Business Loan', 2)]
CITIES = [('Mumbai','Maharashtra',1),('Pune','Maharashtra',2),('Indore','Madhya Pradesh',2),
          ('Kochi','Kerala',2),('Patna','Bihar',3),('Bengaluru','Karnataka',1)]


def emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    start = (cur.execute("SELECT MAX(CAST(SUBSTR(id,5) AS INTEGER)) FROM customers WHERE id LIKE 'CUST%'").fetchone()[0] or 0) + 1

    added = []
    for k in range(N):
        idx = start + k
        cid = f"CUST{idx}"
        bank_id = list(BANKS)[k % 2]
        bank_name, branch, ifsc, country_code = BANKS[bank_id]
        first, last = random.choice(FIRST), random.choice(LAST)
        city, state, tier = random.choice(CITIES)
        is_rural = 1 if tier == 3 and random.random() < 0.5 else 0

        good = random.random() < 0.55
        if good:
            de = round(random.uniform(0.5, 1.6), 2); ic = round(random.uniform(4.5, 12), 2)
            profit = round(random.uniform(9, 20), 1); liq = round(random.uniform(1.5, 2.6), 2)
            cibil = random.randint(740, 820); foir = round(random.uniform(0.20, 0.40), 2)
            late = 0; prev_def = 0; income = random.randint(900000, 4500000)
        else:
            de = round(random.uniform(2.8, 6.0), 2); ic = round(random.uniform(1.0, 2.6), 2)
            profit = round(random.uniform(-6, 6), 1); liq = round(random.uniform(0.7, 1.25), 2)
            cibil = random.randint(560, 690); foir = round(random.uniform(0.48, 0.85), 2)
            late = random.randint(1, 6); prev_def = 1 if random.random() < 0.4 else 0
            income = random.randint(300000, 1500000)

        age = random.randint(24, 60); years_emp = round(random.uniform(1, min(age-22, 30)), 1)
        emp_enc = random.randint(1, 7); edu_enc = random.randint(1, 6); res_enc = random.randint(1, 4)
        ltype, purpose_enc = random.choice(LOAN_TYPES)
        deps = random.randint(0, 4); months_cust = random.randint(3, 180)
        ex_loans = random.randint(0, 4); ex_products = random.randint(1, 6)

        # PD generated from the drivers (gives the model real signal)
        risk = (0.01 + max(0, (750 - cibil)) / 900.0 + de * 0.025
                + max(0, 3 - ic) * 0.05 + max(0, foir - 0.40) * 0.6
                + prev_def * 0.20 + late * 0.03 + (0.05 if profit < 0 else 0))
        pd_obs = round(min(0.95, max(0.005, risk)), 4)
        default_flag = 1 if random.random() < pd_obs else 0

        # facility
        principal = random.randint(3, 60) * 100000
        outstanding = round(principal * random.uniform(0.55, 0.98), 2)
        rate = round(random.uniform(8.5, 15.5), 2)
        tenure = random.choice([36, 48, 60, 84, 120, 180])
        loan_emi = emi(principal, rate, tenure)
        classification = 'NPA' if (default_flag and random.random() < 0.6) else 'Standard'
        disb = date(2023, random.randint(1, 12), random.randint(1, 28)).isoformat()
        mat = date(2023 + tenure // 12, random.randint(1, 12), 28).isoformat()
        lid = f"{bank_name.split()[0].upper()}-LN-{idx:05d}-N{idx}"
        aid = f"ACC-{bank_name.split()[0].upper()}-{idx:04d}"
        balance = round(random.uniform(50000, 1500000), 2)
        obs = date.today().isoformat()
        now = datetime.now().isoformat(timespec='seconds')

        cur.execute("INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, bank_id, first, last, f"{1966+ (60-age)}-06-15", random.choice(['Male','Female']),
                     f"{first.lower()}.{last.lower()}{idx}@example.com", f"9{random.randint(100000000,999999999)}",
                     f"{random.randint(1,99)} MG Road", city, state, str(random.randint(100000,999999)),
                     date.today().isoformat(), 'Active'))

        cur.execute("INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (aid, bank_id, cid, 'Savings', balance, '2023-01-10', branch, ifsc, 'Active'))
        # opening deposit so balance == balance_after (ledger stays reconciled)
        cur.execute("INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"TX-NEW-{idx}", bank_id, aid, '2023-01-10', '10:00:00', 'Deposit', balance, balance,
                     '[INCOME] Opening deposit - account funded'))

        cur.execute("INSERT INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,maturity,outstanding,status,branch_id,loan_classification) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (lid, bank_id, cid, ltype, principal, rate, tenure, loan_emi, disb, mat, outstanding,
                     'Active', branch, classification))

        cur.execute("INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,age,gender,"
                    "marital_status,education_level,num_dependents,employment_type,employer_name,industry_sector,"
                    "years_employed,annual_income,other_income,foir_declared,residence_type,years_at_address,city_tier,"
                    "is_pep,risk_category,created_at,updated_at,months_as_customer,num_existing_products,existing_loans_count,"
                    "loan_purpose,previous_default_flag,cibil_score,num_late_payments_past_12m,state,is_rural) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, bank_id, 1, 1, 'VERIFIED', '2023-01-05', age, 'Male', 'MARRIED',
                     ['PHD','PROFESSIONAL','POST_GRADUATE','GRADUATE','DIPLOMA','HIGH_SCHOOL'][edu_enc-1],
                     deps, ['GOVT','SALARIED','RETIRED','SELF_EMPLOYED','BUSINESS','FREELANCE','STUDENT'][emp_enc-1],
                     'Employer Pvt Ltd', 'Services', years_emp, income, 0, foir,
                     ['OWNED','RENTED','FAMILY','EMPLOYER'][res_enc-1], round(random.uniform(1,15),1),
                     f"TIER{tier}", 0, 'HIGH' if not good else 'LOW', now, now, months_cust, ex_products, ex_loans,
                     {'Home Loan':'HOME_PURCHASE','Vehicle Loan':'VEHICLE','Personal Loan':'PERSONAL','Education Loan':'EDUCATION','Business Loan':'BUSINESS'}.get(ltype,'PERSONAL'),
                     prev_def, cibil, late, state, is_rural))

        cur.execute("INSERT INTO credit_risk_metrics (bank_id,lid,de,intcov,profit,liq,df,pd_score,npa_flag,period,obs) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (bank_id, lid, de, ic, profit, liq, default_flag, pd_obs,
                     1 if classification == 'NPA' else 0, '2024-Q2', obs))

        cur.execute("INSERT INTO bank_loan_metrics (bank_id,bank_name,loan_id,de_ratio,interest_coverage,profitability,"
                    "liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,age,employment_type_enc,"
                    "years_employed,annual_income,foir,num_dependents,city_tier_enc,education_enc,residence_type_enc,"
                    "loan_purpose_enc,cibil_score,previous_default_flag,months_as_customer,num_late_payments_past_12m,"
                    "existing_loans_count,num_existing_products,is_rural,country_code) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (bank_id, bank_name, lid, de, ic, profit, liq, default_flag, pd_obs, obs, now,
                     age, emp_enc, years_emp, income, foir, deps, tier, edu_enc, res_enc, purpose_enc,
                     cibil, prev_def, months_cust, late, ex_loans, ex_products, is_rural, country_code))

        added.append((cid, f"{first} {last}", bank_id, 'good' if good else 'risky', pd_obs, default_flag, classification))

    conn.commit()
    print(f"Added {len(added)} customers (CUST{start}–CUST{start+N-1}):")
    for cid, name, bank, prof, pd_o, df, cls in added:
        print(f"  {cid} {name:22} {bank} {prof:5}  pd={pd_o:.3f} default={df} {cls}")
    print(f"\nbank_loan_metrics now has {cur.execute('SELECT COUNT(*) FROM bank_loan_metrics').fetchone()[0]} rows")
    conn.close()


if __name__ == '__main__':
    main()
