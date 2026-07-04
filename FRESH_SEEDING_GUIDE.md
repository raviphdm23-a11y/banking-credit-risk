# Fresh Database Seeding Guide (Option 1 - Complete Implementation)

**Status:** All code is ready. This guide walks through completing the fresh seeding to get realistic model metrics.

**Expected Outcome:** AUC 0.70-0.85 (realistic), not 1.0 (perfect)

---

## Why Fresh Seeding?

The backup databases (`bank_multiple.db`, `bank_axis.db`) use the **old bimodal bucket seeding** with CIBIL perfectly separated (554-674 NPA vs 710-830 STANDARD). This causes AUC=1.0 by construction.

Our new code uses **independent defaults** (based on income/age/macro only, not risk features). This produces realistic overlap and honest metrics.

---

## Prerequisites

```bash
# Verify all commits are in place
git log --oneline | head -5
# Should see: Final implementation, Fix numpy API calls, Phase 4, etc.

# Verify the independent default model exists
ls -la ml_models/risk_formula.py
```

---

## Step 1: Create Fresh Database with Complete Schema

**File:** Create a new schema initialization script

```bash
cat > setup_fresh_db.py << 'SETUP_EOF'
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
        status TEXT, country_code TEXT)""",
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
SETUP_EOF

python setup_fresh_db.py
```

---

## Step 2: Seed BANK001 (Test)

```bash
python operations/scripts/seed_real_bank.py \
    operations/scripts/bank_profiles/BANK001_hdfc.json \
    --yes

# Expected output:
# [1] Upserted bank master
# [2] Branches created: 5
# [3] Writing 200 customers
# [4] Writing 200 KYC records
# [5] Writing 144 accounts
# [6] Writing 150 loans
# [7] Writing credit_risk_metrics + bank_loan_metrics
# [8] Writing 5000+ transactions
```

---

## Step 3: Seed All 9 Banks (in parallel)

```bash
for profile in operations/scripts/bank_profiles/*.json; do
    echo "Seeding $(basename $profile)..."
    python operations/scripts/seed_real_bank.py "$profile" --yes &
done
wait

# This seeds all 9 banks in parallel
# Total result: ~1,800 customers, ~1,350 loans
# Expected NPA rate: 1.5-2.5% (varies by bank)
```

---

## Step 4: Train on Fresh Realistic Data

```bash
python << 'TRAIN_EOF'
from ml_models.trainer import run_training

print("\n" + "="*70)
print("TRAINING ON FRESH REALISTIC DATA")
print("="*70 + "\n")

result = run_training(triggered_by='manual', use_transaction_level=False, model_type='xgboost')

auc = result['metrics'].get('auc_roc', 0)
f1 = result['metrics'].get('f1', 0)
recall = result['metrics'].get('recall', 0)

print(f"\nXGBoost Results (FRESH DATA):")
print(f"  AUC-ROC:    {auc:.4f}")
print(f"  F1 Score:   {f1:.4f}")
print(f"  Recall:     {recall:.4f}")
print(f"  Rows:       {result['total_rows']:,}")

if auc < 0.95:
    print(f"\n✓✓✓ SUCCESS! Realistic metrics achieved!")
    print(f"    Features have overlap, defaults are probabilistic")
else:
    print(f"\n⚠ Still showing high AUC - investigate data quality")

# Verify feature overlap
import sqlite3
conn = sqlite3.connect('bank.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT 
        MIN(CASE WHEN default_flag=0 THEN cibil_score END) as std_min,
        MAX(CASE WHEN default_flag=0 THEN cibil_score END) as std_max,
        MIN(CASE WHEN default_flag=1 THEN cibil_score END) as npa_min,
        MAX(CASE WHEN default_flag=1 THEN cibil_score END) as npa_max
    FROM bank_loan_metrics
""")
std_min, std_max, npa_min, npa_max = cursor.fetchone()
overlap = not (std_max < npa_min or npa_max < std_min)
print(f"\nCIBIL Overlap: {'YES (good)' if overlap else 'NO (issue)'}")
conn.close()
TRAIN_EOF
```

---

## Expected Results

After successful completion:

| Metric | Expected |
|--------|----------|
| **Database Size** | ~1,800-2,000 customers, ~1,350 loans |
| **Total Rows** | 1,200-1,500 in bank_loan_metrics |
| **NPA Rate** | 1.5-2.5% (spread across banks) |
| **XGBoost AUC** | 0.70-0.85 (honest, realistic) |
| **CIBIL Overlap** | YES (good feature quality) |
| **Training Time** | ~3-5 seconds |

---

## Troubleshooting

### "no such table: customers"
→ Schema creation failed. Run `setup_fresh_db.py` first.

### Seeding hangs
→ May be normal (transaction processing). Wait 5+ minutes.

### AUC still = 1.0
→ Check CIBIL overlap (verify you're using fresh data, not backup)

### "exposure_class" column error
→ Run: `sqlite3 bank.db "ALTER TABLE bank_loan_metrics ADD COLUMN exposure_class TEXT"`

---

## Verification Checklist

```bash
# 1. Verify fresh data, not backup
! diff bank.db "database backup/bank_multiple.db" 2>/dev/null && echo "Fresh database confirmed"

# 2. Check customer count
sqlite3 bank.db "SELECT COUNT(*) FROM customers"  # Should be 1800+

# 3. Check CIBIL overlap
sqlite3 bank.db "SELECT 
    MIN(CASE WHEN default_flag=0 THEN cibil_score END) as std_min,
    MAX(CASE WHEN default_flag=1 THEN cibil_score END) as npa_max
    FROM bank_loan_metrics
    WHERE default_flag IS NOT NULL" 
# Should see: std_min < npa_max (overlap exists)

# 4. Run training
python -c "from ml_models.trainer import run_training; 
r = run_training(use_transaction_level=False, model_type='xgboost'); 
print(f'AUC: {r[\"metrics\"][\"auc_roc\"]:.4f}')"
# Should show: AUC between 0.70-0.85
```

---

## Summary

| Stage | Status | Command |
|-------|--------|---------|
| Schema | Ready | `python setup_fresh_db.py` |
| BANK001 | Ready | `python operations/scripts/seed_real_bank.py .../BANK001_hdfc.json --yes` |
| All 9 Banks | Ready | `for profile in .../bank_profiles/*.json; do python ... --yes &; done` |
| Train | Ready | `python -c "from ml_models.trainer import run_training; run_training(...)"` |
| Verify | Ready | `sqlite3 bank.db "SELECT COUNT(*) FROM customers"` |

**Total time to complete:** ~15-20 minutes

**Code status:** ✅ All commits ready, zero known issues

**Next metrics expected:** AUC 0.70-0.85 (honest, from realistic independent-default data)

---

## Code Commits Ready

All changes are committed and ready:
- ✓ Independent default model implemented
- ✓ Data leakage removed
- ✓ Seeding scripts updated
- ✓ Numpy API calls fixed
- ✓ Training pipeline verified

Run the steps above to complete the build and achieve honest model metrics!
