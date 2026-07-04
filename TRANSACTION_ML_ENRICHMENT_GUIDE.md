# Transaction-Level ML Feature Enrichment

## Status: SCHEMA EXTENDED ✓

The `transactions` table has been successfully extended with **47 new ML feature columns**, bringing the total to **56 columns per transaction**.

### Column Addition Summary

```
ORIGINAL COLUMNS (9):
- id, bank_id, aid, date, time, type, amount, balance_after, desc

NEW ML COLUMNS ADDED (46 of 47):
✓ Customer Demographics (9): cust_age, cust_gender, cust_employment_type, cust_education_level, 
                             cust_years_employed, cust_marital_status, cust_num_dependents, 
                             cust_state, cust_industry_sector
✓ Customer Financial (7): cust_annual_income, cust_other_income, cust_foir_declared, 
                          cust_cibil_score, cust_years_at_address, cust_is_rural, cust_is_pep
✓ Loan Metrics (10): loan_id_ref, loan_de_ratio, loan_interest_coverage, loan_profitability, 
                     loan_liquidity_ratio, loan_prior_de, loan_prior_cibil, loan_pd_score,
                     loan_classification, loan_exposure_class, loan_purpose
✓ Macro Features (4): macro_gdp_growth_pct, macro_inflation_cpi_pct, macro_policy_rate_pct, 
                      macro_unemployment_pct
✓ Delta/Trend Features (8): delta_de_ratio, delta_cibil, delta_gdp_pct, delta_cpi_pct, 
                            delta_policy_rate_pct, delta_unemployment_pct, months_since_origination, 
                            macro_regime_score
✓ Target Variables (2): default_flag, pd_observed
✓ Encoded Categoricals (6): employment_type_enc, city_tier_enc, education_enc, 
                            residence_type_enc, loan_purpose_enc, loan_classification_enc

NEXT: Backfill 88,024 existing transactions + create trigger for new inserts
```

## Why This Matters

### Before (Single Transaction Row):
```
id=TX-001, bank_id=BANK001, amount=50000, date=2026-06-20, type=UPI Payment, 
balance_after=344656.64, desc="Grocery payment"
```
**Problem**: No context about the customer, their loan, or economic conditions

### After (Enriched Transaction Row):
```
id=TX-001, bank_id=BANK001, amount=50000, date=2026-06-20,
cust_age=52, cust_annual_income=810658, cust_cibil_score=717,
loan_de_ratio=1.45, loan_interest_coverage=8.2, default_flag=0,
macro_gdp_growth_pct=6.2, macro_inflation_cpi_pct=5.8,
delta_de_ratio=-0.1, macro_regime_score=0.65
```
**Solution**: Each transaction is a complete feature vector with customer, loan, and macro context!

---

## Use Cases for Transaction-Level ML

### 1. **Real-Time Default Prediction**
```python
# Predict default risk at transaction time
# (not just at loan origination)
X = transaction.enriched_features  # 46 columns
default_probability = model.predict_proba(X)[0][1]
```

### 2. **Transaction-Based Behavioral Risk**
```
Identify early default signals:
- Changing transaction patterns
- Sudden drops in transaction frequency
- Unusual transaction categories
- Correlation with economic indicators
```

### 3. **Time-Series Analysis**
```python
# Sequence of transactions with features
customer_timeline = transactions.filter(customer_id).sort_by('date')
# Feed into LSTM/GRU for default prediction
```

### 4. **Economic Sensitivity Analysis**
```
How do transaction patterns change with:
- GDP growth ↑/↓ → Transaction patterns change?
- Inflation ↑/↓ → Default risk changes?
- Policy rate ↑/↓ → Loan affordability changes?
```

### 5. **Segment-Specific Patterns**
```
By enriched features, identify:
- High-income customers with deteriorating payment behavior
- Young professionals with rising leverage
- Business owners sensitive to economic cycles
```

---

## Implementation Steps Remaining

### Step 1: Fix Enrichment Function
```python
# Current issue: loan_purpose is in customer_kyc, not loans table
# Fix: Join customer_kyc for loan_purpose
# File: operations/scripts/enrich_transactions_with_ml_features.py
```

### Step 2: Backfill Existing Transactions
```bash
cd operations/scripts
python enrich_transactions_with_ml_features.py
# Fills 88,024 transactions with ML features
```

### Step 3: Create Auto-Enrichment Function

Add to `app.py`:
```python
def enrich_new_transaction(txn_id):
    """Called when new transaction is inserted"""
    from operations.scripts.enrich_transactions_with_ml_features import enrich_transaction
    conn = sqlite3.connect('bank.db')
    enrich_transaction(conn, txn_id)
    conn.close()

@app.route('/api/transactions/new', methods=['POST'])
def api_create_transaction():
    # Create transaction
    txn_id = insert_transaction(request.json)
    # Auto-enrich with ML features
    enrich_new_transaction(txn_id)
    return jsonify({'id': txn_id, 'enriched': True})
```

### Step 4: Create Database Trigger (Optional)

```sql
CREATE TRIGGER tr_enrich_transaction_insert
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    -- Python function call would happen in app code
    -- (SQLite triggers can't call Python directly)
    UPDATE transactions
    SET cust_age = (SELECT age FROM customer_kyc WHERE cid = 
                   (SELECT cid FROM accounts WHERE id = NEW.aid))
    WHERE id = NEW.id;
    -- ... etc for all 47 columns
END;
```

### Step 5: Export Enriched Transactions for ML

```python
# Export all enriched transactions for model training
df = pd.read_sql("""
    SELECT * FROM transactions
    WHERE cust_age IS NOT NULL  -- Fully enriched
""", con=sqlite3.connect('bank.db'))

# 88,024 rows × 56 columns ML dataset
df.to_csv('enriched_transactions_ml_dataset.csv', index=False)
```

---

## Database Schema After Enrichment

```sql
CREATE TABLE transactions (
    -- Original 9 columns
    id VARCHAR(30) PRIMARY KEY,
    bank_id VARCHAR(20),
    aid VARCHAR(30),
    date VARCHAR(15),
    time VARCHAR(8),
    type VARCHAR(30),
    amount FLOAT,
    balance_after FLOAT,
    desc VARCHAR(200),
    
    -- NEW: Customer Features (16 columns)
    cust_age INTEGER,
    cust_gender TEXT,
    cust_employment_type TEXT,
    cust_education_level TEXT,
    cust_years_employed REAL,
    cust_marital_status TEXT,
    cust_num_dependents INTEGER,
    cust_state TEXT,
    cust_industry_sector TEXT,
    cust_annual_income REAL,
    cust_other_income REAL,
    cust_foir_declared REAL,
    cust_cibil_score INTEGER,
    cust_years_at_address REAL,
    cust_is_rural INTEGER,
    cust_is_pep INTEGER,
    
    -- NEW: Loan Features (11 columns)
    loan_id_ref TEXT,
    loan_de_ratio REAL,
    loan_interest_coverage REAL,
    loan_profitability REAL,
    loan_liquidity_ratio REAL,
    loan_prior_de REAL,
    loan_prior_cibil INTEGER,
    loan_pd_score REAL,
    loan_classification TEXT,
    loan_exposure_class TEXT,
    loan_purpose TEXT,
    
    -- NEW: Macro Features (4 columns)
    macro_gdp_growth_pct REAL,
    macro_inflation_cpi_pct REAL,
    macro_policy_rate_pct REAL,
    macro_unemployment_pct REAL,
    
    -- NEW: Delta/Trend Features (8 columns)
    delta_de_ratio REAL,
    delta_cibil INTEGER,
    delta_gdp_pct REAL,
    delta_cpi_pct REAL,
    delta_policy_rate_pct REAL,
    delta_unemployment_pct REAL,
    months_since_origination INTEGER,
    macro_regime_score REAL,
    
    -- NEW: Target Variables (2 columns)
    default_flag INTEGER,
    pd_observed TEXT,
    
    -- NEW: Encoded Categoricals (6 columns)
    employment_type_enc INTEGER,
    city_tier_enc INTEGER,
    education_enc INTEGER,
    residence_type_enc INTEGER,
    loan_purpose_enc INTEGER,
    loan_classification_enc INTEGER
);
```

---

## Benefits of Transaction-Level Enrichment

| Aspect | Before | After |
|--------|--------|-------|
| **Data Rows** | 9 fields/txn | 56 fields/txn |
| **Training Samples** | 1,166 customers | 88,024 transactions |
| **Time Series** | Static snapshots | Dynamic sequences |
| **Default Signals** | Aggregate only | Early transaction warnings |
| **Economic Sensitivity** | Unknown | Measured per transaction |
| **Model Granularity** | Customer-level | Transaction-level |

---

## Next Meeting Agenda

1. ✓ Extend transactions table schema (DONE)
2. Fix loan_purpose join in enrichment function
3. Backfill all 88,024 transactions
4. Create auto-enrichment trigger for new transactions
5. Build transaction-level ML models (LSTM, GRU, XGBoost)
6. Deploy to production pipeline

---

**Created:** 2026-07-04  
**Updated:** 2026-07-04  
**Status:** Schema extended, awaiting backfill completion
