"""
seed_bulk_customers.py
──────────────────────
Adds N customers per bank across all 8 group banks.

Each customer gets the full record set the platform needs:
  customers → customer_kyc → accounts → opening deposit txn
  → loan → EMI transaction history → credit_risk_metrics → bank_loan_metrics

EMI history is written for every Standard loan so the RBI 90-day rule
in sync_bank_loan_metrics.py correctly marks them as performing.
NPA loans are explicitly classified and need no EMI history.

Usage:
  python operations/scripts/seed_bulk_customers.py [N_PER_BANK]
  Default N_PER_BANK = 130
"""
import os, sys, sqlite3, random
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB    = os.path.join(_REPO, 'bank.db')

# ── Bank configs ──────────────────────────────────────────────────────────────

BANKS = [
    {
        'bank_id': 'BANK001', 'name': 'HDFC Bank Limited', 'country_code': 'IND',
        'branch': 'BR-HDFC-003', 'ifsc': 'HDFC0000003',
        'first': ['Aarav','Diya','Kabir','Anaya','Vivaan','Saanvi','Reyansh','Myra',
                  'Aryan','Pari','Dhruv','Avni','Veer','Riya','Shaurya','Anya',
                  'Aditya','Zara','Karthik','Priya','Rohit','Shreya','Nikhil','Pooja'],
        'last':  ['Malhotra','Kapoor','Bhat','Menon','Chauhan','Pillai','Saxena',
                  'Sharma','Verma','Singh','Kumar','Patel','Gupta','Reddy','Nair'],
        'cities': [('Mumbai','Maharashtra',1),('Pune','Maharashtra',2),
                   ('Bengaluru','Karnataka',1),('Ahmedabad','Gujarat',1),
                   ('Jaipur','Rajasthan',2),('Kolkata','West Bengal',1)],
        'principal': (400_000, 4_500_000), 'balance': (60_000, 900_000),
        'npa_rate': 0.13,
    },
    {
        'bank_id': 'BANK002', 'name': 'ICICI Bank Limited', 'country_code': 'IND',
        'branch': 'BR-ICICI-003', 'ifsc': 'ICIC0000003',
        'first': ['Arjun','Kiara','Ishaan','Riya','Aditya','Ira','Krishna','Aadhya',
                  'Rahul','Sneha','Vikram','Meera','Suresh','Kavita','Mohan','Anita',
                  'Kiran','Deepa','Ravi','Sunita','Ganesh','Rekha','Ashok','Leela'],
        'last':  ['Bose','Nayak','Gill','Saxena','Menon','Chauhan','Pillai',
                  'Iyer','Murthy','Venkat','Krishnan','Rajan','Subramaniam'],
        'cities': [('Delhi','Delhi',1),('Hyderabad','Telangana',1),
                   ('Chennai','Tamil Nadu',1),('Lucknow','Uttar Pradesh',2),
                   ('Bhopal','Madhya Pradesh',2),('Nagpur','Maharashtra',2)],
        'principal': (400_000, 4_500_000), 'balance': (60_000, 900_000),
        'npa_rate': 0.13,
    },
    {
        'bank_id': 'BANK003', 'name': 'Atlas Bank N.A.', 'country_code': 'USA',
        'branch': 'BR-ATLAS-003', 'ifsc': 'ATLS0000003',
        'first': ['James','Michael','Robert','David','Emily','Jessica','Sarah','Daniel',
                  'Christopher','Amanda','Matthew','Ashley','Joshua','Jennifer','Andrew',
                  'Stephanie','Ryan','Nicole','Tyler','Melissa','Brandon','Lauren'],
        'last':  ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
                  'Wilson','Anderson','Taylor','Thomas','Jackson','White','Harris'],
        'cities': [('New York','NY',1),('Chicago','IL',1),('San Francisco','CA',1),
                   ('Boston','MA',1),('Seattle','WA',1),('Houston','TX',1),('Miami','FL',1)],
        'principal': (2_000_000, 7_000_000), 'balance': (1_200_000, 4_500_000),
        'npa_rate': 0.12,
    },
    {
        'bank_id': 'BANK004', 'name': 'Britannia Banking Group plc', 'country_code': 'GBR',
        'branch': 'BR-BRITANNIA-003', 'ifsc': 'BRIT0000003',
        'first': ['Oliver','George','Harry','Jack','Charlie','Thomas','Henry','William',
                  'Amelia','Olivia','Emily','Isla','Sophie','Grace','Lily','Freya',
                  'Charlotte','Jessica','Daniel','Edward','Noah','Alfie','Arthur'],
        'last':  ['Smith','Jones','Taylor','Brown','Williams','Wilson','Evans','Thomas',
                  'Roberts','Walker','Wright','Robinson','Thompson','White','Hughes'],
        'cities': [('London','England',1),('Manchester','England',1),('Birmingham','England',1),
                   ('Leeds','England',2),('Glasgow','Scotland',1),('Edinburgh','Scotland',1),
                   ('Bristol','England',1),('Cardiff','Wales',2)],
        'principal': (1_800_000, 6_000_000), 'balance': (1_100_000, 4_000_000),
        'npa_rate': 0.12,
    },
    {
        'bank_id': 'BANK005', 'name': 'Lion City Bank Ltd', 'country_code': 'SGP',
        'branch': 'BR-LIONCITY-003', 'ifsc': 'LION0000003',
        'first': ['Wei','Jun','Hui','Ming','Mei','Xin','Jia','Kai','Ling','Yan',
                  'Arjun','Priya','Ahmad','Nurul','Siti','Daniel','Rachel','Marcus',
                  'Ethan','Chloe','Ryan','Hannah','Kevin','Jasmine'],
        'last':  ['Tan','Lim','Lee','Ng','Wong','Chan','Goh','Koh','Teo','Ong',
                  'Kumar','Raman','Abdullah','Ismail','Yeo','Chua','Lau','Sim'],
        'cities': [('Singapore','Central',1),('Jurong','West',1),('Tampines','East',1),
                   ('Woodlands','North',1),('Bedok','East',1),('Punggol','North-East',1)],
        'principal': (1_800_000, 6_000_000), 'balance': (1_300_000, 4_200_000),
        'npa_rate': 0.10,
    },
    {
        'bank_id': 'BANK006', 'name': 'Gulf Union Bank PJSC', 'country_code': 'ARE',
        'branch': 'BR-GULFUNION-003', 'ifsc': 'GULF0000003',
        'first': ['Mohammed','Ahmed','Ali','Omar','Khalid','Hassan','Saeed','Rashid',
                  'Fatima','Aisha','Mariam','Layla','Noura','Hessa','Sara','Yousef',
                  'Abdullah','Ibrahim','Tariq','Reem','Maryam','Hamdan'],
        'last':  ['Al Maktoum','Al Nahyan','Al Qasimi','Al Falasi','Al Suwaidi',
                  'Khan','Hassan','Abdullah','Rahman','Sharma','Patel','Ahmed',
                  'Al-Rashidi','Al-Mansoori','Al-Hashimi'],
        'cities': [('Dubai','Dubai',1),('Abu Dhabi','Abu Dhabi',1),('Sharjah','Sharjah',1),
                   ('Ajman','Ajman',2),('Al Ain','Abu Dhabi',2),('Ras Al Khaimah','RAK',2)],
        'principal': (1_600_000, 5_500_000), 'balance': (1_000_000, 3_800_000),
        'npa_rate': 0.10,
    },
    {
        'bank_id': 'BANK007', 'name': 'Nippon Commercial Bank Ltd.', 'country_code': 'JPN',
        'branch': 'BR-NIPPON-002', 'ifsc': 'NPCB0000002',
        'first': ['Hiroshi','Kenji','Takashi','Ryota','Shota','Daiki','Kazuki','Naoki',
                  'Sakura','Hana','Aiko','Nana','Mio','Rin','Yui','Saki','Mei','Akane',
                  'Yuki','Haruto','Sota','Riku','Hayato','Kohei','Tomoya'],
        'last':  ['Tanaka','Suzuki','Watanabe','Ito','Yamamoto','Nakamura',
                  'Kobayashi','Kato','Sato','Yoshida','Hayashi','Kimura','Matsumoto',
                  'Inoue','Kimura','Shimizu','Yamaguchi','Saito','Ogawa'],
        'cities': [('Tokyo','Tokyo',1),('Osaka','Osaka',1),('Nagoya','Aichi',1),
                   ('Yokohama','Kanagawa',1),('Kyoto','Kyoto',1),('Fukuoka','Fukuoka',1),
                   ('Sapporo','Hokkaido',2),('Hiroshima','Hiroshima',2)],
        'principal': (1_700_000, 6_000_000), 'balance': (1_100_000, 4_000_000),
        'npa_rate': 0.14,
    },
    {
        'bank_id': 'BANK008', 'name': 'Southern Cross Bank Ltd.', 'country_code': 'AUS',
        'branch': 'BR-SCROSS-002', 'ifsc': 'SCRX0000002',
        'first': ['James','William','Oliver','Noah','Jack','Liam','Ethan','Lucas',
                  'Charlotte','Olivia','Amelia','Isla','Sophie','Grace','Chloe','Hannah',
                  'Emily','Zoe','Thomas','Henry','Alexander','Samuel','Benjamin','Elijah'],
        'last':  ['Smith','Jones','Williams','Brown','Taylor','Wilson','Anderson',
                  'Thompson','White','Harris','Martin','Walker','Robinson','Clark',
                  'Lewis','Hall','Young','King','Wright','Scott'],
        'cities': [('Sydney','New South Wales',1),('Melbourne','Victoria',1),
                   ('Brisbane','Queensland',1),('Perth','Western Australia',1),
                   ('Adelaide','South Australia',1),('Canberra','ACT',1),
                   ('Gold Coast','Queensland',2),('Newcastle','New South Wales',2)],
        'principal': (1_800_000, 7_000_000), 'balance': (1_200_000, 5_000_000),
        'npa_rate': 0.15,
    },
]

LOAN_TYPES = [
    ('Home Loan',      'HOME_PURCHASE', 5),
    ('Vehicle Loan',   'VEHICLE',       3),
    ('Personal Loan',  'PERSONAL',      1),
    ('Education Loan', 'EDUCATION',     4),
    ('Business Loan',  'BUSINESS',      2),
]
RISKY_LOANS = [('Personal Loan','PERSONAL',1), ('Business Loan','BUSINESS',2)]

EMP_LABELS  = ['GOVT','SALARIED','RETIRED','SELF_EMPLOYED','BUSINESS','FREELANCE','STUDENT']
EDU_LABELS  = ['PHD','PROFESSIONAL','POST_GRADUATE','GRADUATE','DIPLOMA','HIGH_SCHOOL']
RES_LABELS  = ['OWNED','RENTED','FAMILY','EMPLOYER']

# ── Helpers ───────────────────────────────────────────────────────────────────

def calc_emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)

def determine_exposure_class(loan_type, employment_type):
    """Map loan type + employment to Basel III.1 exposure class."""
    if loan_type == 'Home Loan':
        return 'RETAIL_MORTGAGES'
    if loan_type in ('Vehicle Loan', 'Personal Loan', 'Education Loan'):
        return 'RETAIL_OTHER'
    if loan_type == 'Business Loan':
        return 'SME' if employment_type in ('BUSINESS', 'SELF_EMPLOYED') else 'CORPORATE'
    return 'CORPORATE'  # fallback


def emi_months_up_to(disb_str, tenure, stop_before=None):
    """Return list of date objects for each monthly EMI due (5th of month)."""
    from datetime import datetime as dt2
    disb = dt2.strptime(disb_str, '%Y-%m-%d').date()
    today = stop_before or date.today()
    months = []
    y, m = disb.year, disb.month
    m += 1
    if m > 12:
        m, y = 1, y + 1
    for _ in range(tenure):
        due = date(y, m, 5)
        if due > today:
            break
        months.append(due)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


# ── Main seeder ───────────────────────────────────────────────────────────────

def seed(n_per_bank=130, db_path=None, verbose=True):
    db_path = db_path or DB

    try:
        from dateutil.relativedelta import relativedelta  # noqa
    except ImportError:
        pass  # not needed — using manual month arithmetic

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    start_id = (cur.execute(
        "SELECT MAX(CAST(SUBSTR(id,5) AS INTEGER)) FROM customers WHERE id LIKE 'CUST%'"
    ).fetchone()[0] or 0) + 1

    total_added   = 0
    total_emi_txn = 0

    for b in BANKS:
        bank_id    = b['bank_id']
        bank_name  = b['name']
        npa_target = b['npa_rate']
        short      = ''.join(w[0] for w in bank_name.split()[:3]).upper()

        macro = cur.execute(
            "SELECT gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct "
            "FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
            (b['country_code'],)).fetchone() or (6.7, 4.5, 6.25, 7.6)

        bank_added = 0
        for i in range(n_per_bank):
            idx = start_id + total_added
            cid = f"CUST{idx}"

            # ── Profile ──────────────────────────────────────────────────────
            is_npa   = random.random() < npa_target
            is_good  = not is_npa

            if is_good:
                de      = round(random.uniform(0.4, 1.8), 2)
                ic      = round(random.uniform(4.0, 13.0), 2)
                profit  = round(random.uniform(8.0, 22.0), 1)
                liq     = round(random.uniform(1.4, 2.8), 2)
                cibil   = random.randint(720, 825)
                foir    = round(random.uniform(0.18, 0.42), 2)
                late    = 0
                prev_def = 0
                income  = random.randint(800_000, 5_000_000)
            else:
                de      = round(random.uniform(3.0, 7.0), 2)
                ic      = round(random.uniform(0.8, 2.4), 2)
                profit  = round(random.uniform(-8.0, 5.0), 1)
                liq     = round(random.uniform(0.5, 1.2), 2)
                cibil   = random.randint(530, 680)
                foir    = round(random.uniform(0.50, 0.88), 2)
                late    = random.randint(2, 7)
                prev_def = 1 if random.random() < 0.5 else 0
                income  = random.randint(250_000, 1_200_000)

            age         = random.randint(24, 62)
            years_emp   = round(random.uniform(1.0, min(age - 22, 28)), 1)
            emp_enc     = random.randint(1, 7)
            edu_enc     = random.randint(1, 6)
            res_enc     = random.randint(1, 4)
            deps        = random.randint(0, 4)
            months_cust = random.randint(6, 200)
            ex_loans    = random.randint(0, 4)
            ex_products = random.randint(1, 6)

            city, state, tier = random.choice(b['cities'])
            is_rural    = 0

            lt_name, lt_purpose, lt_enc = random.choice(RISKY_LOANS if is_npa else LOAN_TYPES)
            emp_label = EMP_LABELS[emp_enc - 1]
            exposure_class = determine_exposure_class(lt_name, emp_label)

            # pd_observed kept for legacy column
            risk = (0.01 + max(0, (750 - cibil)) / 900.0 + de * 0.025
                    + max(0, 3.0 - ic) * 0.05 + max(0, foir - 0.40) * 0.6
                    + prev_def * 0.20 + late * 0.03 + (0.05 if profit < 0 else 0))
            pd_obs       = round(min(0.95, max(0.005, risk)), 4)
            default_flag = 1 if is_npa else 0

            # ── Loan ─────────────────────────────────────────────────────────
            principal    = (random.randint(b['principal'][0] // 100_000,
                                           b['principal'][1] // 100_000) * 100_000)
            outstanding  = round(principal * random.uniform(0.50, 0.97), 2)
            rate         = round(random.uniform(7.5, 15.5), 2)
            tenure       = random.choice([36, 48, 60, 84, 120, 180])
            loan_emi_val = calc_emi(principal, rate, tenure)

            # Disbursement: 2–4 years back so there's meaningful EMI history
            months_back  = random.randint(24, 48)
            today_d      = date.today()
            disb_d       = today_d - timedelta(days=months_back * 30)
            disb         = disb_d.isoformat()
            mat_d        = date(disb_d.year + tenure // 12 + (1 if disb_d.month + tenure % 12 > 12 else 0),
                                (disb_d.month + tenure % 12 - 1) % 12 + 1, min(disb_d.day, 28))
            mat          = mat_d.isoformat()

            # NPA: classify explicitly; Standard: will have full EMI history
            classification = 'NPA' if is_npa else 'Standard'
            npa_flag_val   = 1 if is_npa else 0

            lid = f"{short}-LN-{idx:05d}-{'N' if is_npa else 'G'}{idx}"
            aid = f"ACC-{short}-{idx:04d}"
            balance = round(random.uniform(b['balance'][0], b['balance'][1]), 2)
            obs = today_d.isoformat()
            now = datetime.now().isoformat(timespec='seconds')

            # ── Insert records ────────────────────────────────────────────────
            cur.execute(
                "INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,"
                "address,city,state,pincode,joined,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, bank_id,
                 random.choice(b['first']), random.choice(b['last']),
                 f"{1900 + (2026 - age)}-06-15",
                 random.choice(['Male','Female']),
                 f"cust{idx}@example.com",
                 f"9{random.randint(100_000_000,999_999_999)}",
                 f"{random.randint(1,99)} Main Street", city, state,
                 str(random.randint(100_000, 999_999)),
                 today_d.isoformat(), 'Active'))

            cur.execute(
                "INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,"
                "branch_id,ifsc_code,status) VALUES (?,?,?,?,?,?,?,?,?)",
                (aid, bank_id, cid, 'Savings', balance,
                 disb_d.isoformat(), b['branch'], b['ifsc'], 'Active'))

            # Opening deposit
            cur.execute(
                "INSERT OR IGNORE INTO transactions "
                "(id,bank_id,aid,date,time,type,amount,balance_after,desc) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"TX-OPEN-{idx}", bank_id, aid,
                 disb_d.isoformat(), '09:00:00', 'Deposit',
                 balance, balance, '[INCOME] Opening deposit - account funded'))

            cur.execute(
                "INSERT INTO loans (id,bank_id,cid,type,principal,rate,tenure,emi,"
                "disbursed,maturity,outstanding,status,branch_id,loan_classification,exposure_class) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lid, bank_id, cid, lt_name, principal, rate, tenure, loan_emi_val,
                 disb, mat, outstanding, 'Active', b['branch'], classification, exposure_class))

            cur.execute(
                "INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,"
                "kyc_status,kyc_date,age,gender,marital_status,education_level,"
                "num_dependents,employment_type,employer_name,industry_sector,"
                "years_employed,annual_income,other_income,foir_declared,residence_type,"
                "years_at_address,city_tier,is_pep,risk_category,created_at,updated_at,"
                "months_as_customer,num_existing_products,existing_loans_count,"
                "loan_purpose,previous_default_flag,cibil_score,"
                "num_late_payments_past_12m,state,is_rural) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, bank_id, 1, 1, 'VERIFIED', disb_d.isoformat(), age,
                 random.choice(['Male','Female']), 'MARRIED',
                 EDU_LABELS[edu_enc - 1], deps, EMP_LABELS[emp_enc - 1],
                 f"{bank_name.split()[0]} Corp", 'Financial Services',
                 years_emp, income, 0, foir, RES_LABELS[res_enc - 1],
                 round(random.uniform(1, 15), 1), f"TIER{tier}",
                 0, 'HIGH' if is_npa else 'LOW',
                 now, now, months_cust, ex_products, ex_loans,
                 lt_purpose, prev_def, cibil, late, state, is_rural))

            # Prior values: uniform origination baseline (same distribution for all loans)
            prior_de    = round(random.uniform(0.5, 1.8), 4)
            prior_cibil = random.randint(710, 820)

            cur.execute(
                "INSERT INTO credit_risk_metrics "
                "(bank_id,lid,de,intcov,profit,liq,df,pd_score,npa_flag,period,obs,prior_de,prior_cibil) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bank_id, lid, de, ic, profit, liq, default_flag, pd_obs,
                 npa_flag_val, '2025-Q4', obs, prior_de, prior_cibil))

            from datetime import date as _date
            months_orig = round((_date.today() - _date.fromisoformat(disb)).days / 30.44, 1)

            cur.execute(
                "INSERT INTO bank_loan_metrics "
                "(bank_id,bank_name,loan_id,de_ratio,interest_coverage,profitability,"
                "liquidity_ratio,default_flag,pd_observed,observation_date,loaded_at,"
                "age,employment_type_enc,years_employed,annual_income,foir,"
                "num_dependents,city_tier_enc,education_enc,residence_type_enc,"
                "loan_purpose_enc,cibil_score,previous_default_flag,months_as_customer,"
                "num_late_payments_past_12m,existing_loans_count,num_existing_products,"
                "is_rural,country_code,"
                "gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct,"
                "delta_de_ratio,delta_cibil,months_since_origination) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bank_id, bank_name, lid, de, ic, profit, liq,
                 default_flag, pd_obs, obs, now,
                 age, emp_enc, years_emp, income, foir, deps,
                 tier, edu_enc, res_enc, lt_enc,
                 cibil, prev_def, months_cust, late, ex_loans, ex_products,
                 is_rural, b['country_code'],
                 macro[0], macro[1], macro[2], macro[3],
                 round(de - prior_de, 4), round(float(cibil - prior_cibil), 1), months_orig))

            # ── EMI transactions for Standard (performing) loans ──────────────
            if not is_npa:
                emi_dates = emi_months_up_to(disb, tenure)
                bal = balance
                for j, due in enumerate(emi_dates):
                    bal = round(max(10_000, bal - loan_emi_val + random.uniform(-5000, 15000)), 2)
                    cur.execute(
                        "INSERT OR IGNORE INTO transactions "
                        "(id,bank_id,aid,date,time,type,amount,balance_after,desc) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"TX-EMI-{idx}-{j+1:03d}", bank_id, aid,
                         due.isoformat(), '05:00:00', 'Debit',
                         -round(loan_emi_val, 2), bal,
                         f'EMI Payment - {lid}'))
                    total_emi_txn += 1

            total_added += 1
            bank_added  += 1

        if verbose:
            print(f"  {bank_id}: +{bank_added} customers")

    conn.commit()
    conn.close()

    if verbose:
        print(f"\nDone. Added {total_added} customers, {total_emi_txn} EMI transactions.")

    return total_added, total_emi_txn


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 130
    random.seed(20260619)
    print(f"Seeding {n} customers per bank across all 8 banks ({n * 8} total)...\n")
    seed(n_per_bank=n, verbose=True)
