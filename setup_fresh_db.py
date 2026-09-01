import sqlite3
import os

if os.path.exists('bank.db'):
    os.remove('bank.db')

conn = sqlite3.connect('bank.db')
cur = conn.cursor()

# Create all core banking tables
tables = {
    'banks': """CREATE TABLE banks (
        bank_id TEXT PRIMARY KEY, bank_name TEXT, bank_code TEXT, country TEXT,
        headquarters_city TEXT, headquarters_state TEXT, year_established INTEGER,
        status TEXT, country_code TEXT,
        world TEXT NOT NULL DEFAULT 'utopian')""",
        # world: 'utopian' (the original 9 banks - uniform schema, safe to pool
        # into combined/cross-bank model training) or 'real' (onboarded from
        # heterogeneous external data - e.g. Bank of Punjab from PAK.csv -
        # never pooled, always its own bank-specific/GENERIC model).
    'branches': """CREATE TABLE branches (
        branch_id TEXT PRIMARY KEY, bank_id TEXT, branch_name TEXT, ifsc_code TEXT,
        city TEXT, state TEXT, pincode TEXT, address TEXT, contact_phone TEXT, status TEXT)""",
    'customers': """CREATE TABLE customers (
        id TEXT PRIMARY KEY, bank_id TEXT, first TEXT, last TEXT, dob TEXT, gender TEXT,
        email TEXT, phone TEXT, address TEXT, city TEXT, state TEXT, pincode TEXT,
        joined TEXT, status TEXT)""",
    'accounts': """CREATE TABLE accounts (
        id TEXT PRIMARY KEY, bank_id TEXT, cid TEXT, type TEXT, balance REAL, open_date TEXT,
        branch_id TEXT, ifsc_code TEXT, status TEXT)""",
    'loans': """CREATE TABLE loans (
        id TEXT PRIMARY KEY, bank_id TEXT, cid TEXT, type TEXT, principal REAL, rate REAL,
        tenure INTEGER, emi REAL, disbursed TEXT, maturity TEXT, outstanding REAL, status TEXT,
        branch_id TEXT, loan_classification TEXT, exposure_class TEXT, external_rating TEXT,
        ltv REAL, ltv_ratio REAL)""",
    'transactions': """CREATE TABLE transactions (
        id TEXT PRIMARY KEY, bank_id TEXT, aid TEXT, date TEXT, time TEXT, type TEXT,
        amount REAL, balance_after REAL, desc TEXT)""",
    'customer_kyc': """CREATE TABLE customer_kyc (
        kyc_id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT, bank_id TEXT, pan_verified INTEGER,
        aadhaar_verified INTEGER, kyc_status TEXT, kyc_date TEXT, age INTEGER, gender TEXT,
        marital_status TEXT, education_level TEXT, num_dependents INTEGER, employment_type TEXT,
        employer_name TEXT, industry_sector TEXT, years_employed REAL, annual_income REAL,
        other_income REAL, foir_declared REAL, residence_type TEXT, years_at_address REAL,
        city_tier TEXT, is_pep INTEGER, risk_category TEXT, created_at TEXT, updated_at TEXT,
        months_as_customer INTEGER, num_existing_products INTEGER, existing_loans_count INTEGER,
        loan_purpose TEXT, previous_default_flag INTEGER, cibil_score INTEGER,
        num_late_payments_past_12m INTEGER, state TEXT, is_rural INTEGER)""",
    'credit_risk_metrics': """CREATE TABLE credit_risk_metrics (
        metric_id INTEGER PRIMARY KEY AUTOINCREMENT, bank_id TEXT, lid TEXT, de REAL, intcov REAL,
        profit REAL, liq REAL, df INTEGER, pd_score REAL, npa_flag INTEGER, period TEXT, obs TEXT,
        prior_de REAL, prior_cibil INTEGER)""",
    'bank_loan_metrics': """CREATE TABLE bank_loan_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT, bank_id TEXT, bank_name TEXT, loan_id TEXT,
        de_ratio REAL, interest_coverage REAL, profitability REAL, liquidity_ratio REAL,
        default_flag INTEGER, pd_observed REAL, observation_date TEXT, loaded_at TEXT, age INTEGER,
        employment_type_enc INTEGER, years_employed REAL, annual_income REAL, foir REAL,
        num_dependents INTEGER, city_tier_enc INTEGER, education_enc INTEGER, residence_type_enc INTEGER,
        loan_purpose_enc INTEGER, cibil_score INTEGER, previous_default_flag INTEGER,
        months_as_customer INTEGER, num_late_payments_past_12m INTEGER, existing_loans_count INTEGER,
        num_existing_products INTEGER, is_rural INTEGER, country_code TEXT, gdp_growth_pct REAL,
        inflation_cpi_pct REAL, policy_rate_pct REAL, unemployment_pct REAL, delta_de_ratio REAL,
        delta_cibil REAL, months_since_origination REAL, exposure_class TEXT)""",
    'countries': """CREATE TABLE countries (
        country_code TEXT PRIMARY KEY, country_name TEXT, region TEXT, sub_region TEXT,
        currency_code TEXT, currency_symbol TEXT, central_bank TEXT, central_bank_abbr TEXT,
        capital_regulator TEXT, basel_framework TEXT, sovereign_rating TEXT, min_crar REAL,
        min_cet1 REAL, min_tier1 REAL, min_lcr REAL, min_nsfr REAL, is_home INTEGER,
        generated_at TEXT)""",
    'country_macro': """CREATE TABLE country_macro (
        id INTEGER PRIMARY KEY AUTOINCREMENT, country_code TEXT, period TEXT, gdp_usd_bn REAL,
        gdp_growth_pct REAL, inflation_cpi_pct REAL, policy_rate_pct REAL, unemployment_pct REAL,
        public_debt_gdp_pct REAL, current_account_gdp_pct REAL, fx_rate_per_usd REAL,
        population_mn REAL, source TEXT, generated_at TEXT)"""
}

for table, schema in tables.items():
    cur.execute(schema)

# Seed minimal reference data
cur.execute("""INSERT INTO countries VALUES 
    ('IN','India','Asia','South','INR','Rs','RBI','RBI','RBI','Basel III','BBB-',
     11.5,8.0,9.5,100,100,1,NULL)""")
cur.execute("""INSERT INTO country_macro VALUES 
    (NULL,'IN','2024-Q2',3734,6.7,4.5,6.25,7.6,80,-1.2,83.0,1412,'RBI',NULL)""")

conn.commit()
conn.close()
print("Fresh database created successfully with complete schema!")
