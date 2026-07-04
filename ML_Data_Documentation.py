import pandas as pd

df = pd.read_csv('ML_Training_Data.csv')

print("=" * 130)
print("ML TRAINING DATA - COMPLETE DOCUMENTATION")
print("=" * 130)

print("\n" + "=" * 130)
print("TARGET VARIABLE: default_flag (What we are predicting)")
print("=" * 130)

print("\nColumn Name: default_flag")
print("Data Type: Integer (0 or 1)")
print("\nMeaning:")
print("  0 = HEALTHY LOAN - Borrower is performing well, no default")
print("  1 = DEFAULT LOAN - Borrower has defaulted (90+ days overdue per RBI rules)")
print("\nDistribution in Training Data:")
print(df['default_flag'].value_counts().sort_index().to_string())
print(f"\nDefault Rate: {df['default_flag'].sum() / len(df) * 100:.2f}%")
print(f"Class Balance: {(df['default_flag'] == 0).sum()} healthy : {(df['default_flag'] == 1).sum()} defaults")

print("\n" + "=" * 130)
print("CORE FINANCIAL METRICS (Most Important Features)")
print("=" * 130)

financial = ["de_ratio", "interest_coverage", "profitability", "liquidity_ratio"]
descriptions = {
    "de_ratio": "Debt-to-Equity Ratio = Total Debt / Equity | Risk Indicator | Lower is better",
    "interest_coverage": "EBIT / Interest Expense | Ability to pay debt | Higher is better",
    "profitability": "Net Profit Margin (%) | Earnings quality | Higher is better",
    "liquidity_ratio": "Current Assets / Current Liabilities | Can pay short-term debt | Higher is better"
}

for col in financial:
    print(f"\n{col.upper()}")
    print(f"  Description: {descriptions[col]}")
    stats = df[col].describe()
    print(f"  Mean: {stats['mean']:8.2f} | Median: {df[col].median():8.2f} | Std Dev: {stats['std']:8.2f}")
    print(f"  Min:  {stats['min']:8.2f} | Max:    {stats['max']:8.2f}")
    healthy_avg = df[df['default_flag']==0][col].mean()
    default_avg = df[df['default_flag']==1][col].mean()
    print(f"  Healthy avg: {healthy_avg:.2f} | Default avg: {default_avg:.2f}")

print("\n" + "=" * 130)
print("BORROWER DEMOGRAPHICS")
print("=" * 130)

print("\nAGE:")
print(f"  Type: Float (years) | Range: {df['age'].min():.0f} to {df['age'].max():.0f}")
print(f"  Mean: {df['age'].mean():.0f} | Median: {df['age'].median():.0f}")

print("\nEMPLOYMENT TYPE:")
print(f"  Type: Integer (1-5)")
print(f"  1=Salaried, 2=Self-employed, 3=Business, 4=Professional, 5=Corporate")
print(f"  Distribution: {dict(df['employment_type_enc'].value_counts().sort_index())}")

print("\nYEARS EMPLOYED:")
print(f"  Type: Float | Range: {df['years_employed'].min():.1f} to {df['years_employed'].max():.1f}")
print(f"  Mean: {df['years_employed'].mean():.1f}")

print("\nANNUAL INCOME:")
print(f"  Type: Float (INR) | Range: {df['annual_income'].min():,.0f} to {df['annual_income'].max():,.0f}")
print(f"  Mean: {df['annual_income'].mean():,.0f}")

print("\nNUM DEPENDENTS:")
print(f"  Type: Integer | Range: {df['num_dependents'].min()} to {df['num_dependents'].max()}")
print(f"  Distribution: {dict(df['num_dependents'].value_counts().sort_index())}")

print("\nCITY TIER:")
print(f"  Type: Integer (1-2) | 1=Metro/Tier-1, 2=Non-metro/Tier-2+")
print(f"  Distribution: {dict(df['city_tier_enc'].value_counts().sort_index())}")

print("\nEDUCATION LEVEL:")
print(f"  Type: Integer (1-6) | Higher = More educated")
print(f"  Distribution: {dict(df['education_enc'].value_counts().sort_index())}")

print("\nRESIDENCE TYPE:")
print(f"  Type: Integer (1-3) | 1=Owned, 2=Rented, 3=Other")
print(f"  Distribution: {dict(df['residence_type_enc'].value_counts().sort_index())}")

print("\nRURAL/URBAN:")
print(f"  Type: Integer (0-1) | 0=Urban, 1=Rural")
print(f"  Distribution: {dict(df['is_rural'].value_counts().sort_index())}")

print("\n" + "=" * 130)
print("CREDIT HISTORY & PAYMENT BEHAVIOR")
print("=" * 130)

print("\nCIBIL SCORE:")
print(f"  Type: Integer | Range: {df['cibil_score'].min()} to {df['cibil_score'].max()}")
print(f"  Mean: {df['cibil_score'].mean():.0f} | Median: {df['cibil_score'].median():.0f}")
print(f"  Purpose: Credit Information Bureau score (higher = better credit)")
healthy_cibil = df[df['default_flag']==0]['cibil_score'].mean()
default_cibil = df[df['default_flag']==1]['cibil_score'].mean()
print(f"  Healthy borrowers avg: {healthy_cibil:.0f}")
print(f"  Default borrowers avg: {default_cibil:.0f}")

print("\nPREVIOUS DEFAULT:")
print(f"  Type: Integer (0-1) | 0=No prior default, 1=Has defaulted before")
print(f"  Distribution: {dict(df['previous_default_flag'].value_counts().sort_index())}")

print("\nMONTHS AS CUSTOMER:")
print(f"  Type: Integer (months) | Range: {df['months_as_customer'].min()} to {df['months_as_customer'].max()}")
print(f"  Mean: {df['months_as_customer'].mean():.0f}")

print("\nLATE PAYMENTS (Last 12 months):")
print(f"  Type: Integer | Range: {df['num_late_payments_past_12m'].min()} to {df['num_late_payments_past_12m'].max()}")
print(f"  Mean: {df['num_late_payments_past_12m'].mean():.2f}")

print("\nEXISTING LOANS:")
print(f"  Type: Integer | Range: {df['existing_loans_count'].min()} to {df['existing_loans_count'].max()}")
print(f"  Distribution: {dict(df['existing_loans_count'].value_counts().sort_index())}")

print("\nEXISTING PRODUCTS:")
print(f"  Type: Integer | Range: {df['num_existing_products'].min()} to {df['num_existing_products'].max()}")
print(f"  Distribution: {dict(df['num_existing_products'].value_counts().sort_index())}")

print("\n" + "=" * 130)
print("LOAN DETAILS")
print("=" * 130)

print("\nLOAN PURPOSE:")
print(f"  Type: Integer (1-5)")
print(f"  1=Home, 2=Auto, 3=Personal, 4=Business, 5=Education")
print(f"  Distribution: {dict(df['loan_purpose_enc'].value_counts().sort_index())}")

print("\nFOIR (Fixed Obligations to Income Ratio):")
print(f"  Type: Float | Range: {df['foir'].min():.2f} to {df['foir'].max():.2f}")
print(f"  Mean: {df['foir'].mean():.2f}")
print(f"  Purpose: Debt servicing capacity (lower is better)")

print("\nEXPOSURE CLASS (Basel III):")
print(f"  Type: String | Categories: {df['exposure_class'].unique().tolist()}")
print(f"  Distribution: {dict(df['exposure_class'].value_counts())}")

print("\n" + "=" * 130)
print("MACRO-ECONOMIC FACTORS (Country level)")
print("=" * 130)

print("\nCOUNTRY CODE:")
print(f"  Type: String | Countries: {df['country_code'].unique().tolist()}")

macro = ["gdp_growth_pct", "inflation_cpi_pct", "policy_rate_pct", "unemployment_pct"]
for col in macro:
    print(f"\n{col.upper().replace('_PCT', ' (%)')}:")
    print(f"  Type: Float | Range: {df[col].min():.2f} to {df[col].max():.2f}")
    print(f"  Mean: {df[col].mean():.2f}")

print("\n" + "=" * 130)
print("DELTA/TREND FEATURES (Changes over time)")
print("=" * 130)

deltas = ["delta_de_ratio", "delta_cibil", "delta_gdp_pct", "delta_cpi_pct",
          "delta_policy_rate_pct", "delta_unemployment_pct", "months_since_origination", "macro_regime_score"]

for col in deltas:
    print(f"\n{col.upper()}:")
    print(f"  Type: Float | Range: {df[col].min():.2f} to {df[col].max():.2f}")
    print(f"  Mean: {df[col].mean():.2f}")
    print(f"  Purpose: Trend indicator")

print("\n" + "=" * 130)
print("OTHER COLUMNS")
print("=" * 130)

print("\nPD_OBSERVED (Observed Probability of Default):")
print(f"  Type: Float | Range: {df['pd_observed'].min():.2f} to {df['pd_observed'].max():.2f}")
print(f"  Purpose: Historical PD label (for evaluation)")

print("\nOBSERVATION_DATE:")
print(f"  Type: String (YYYY-MM-DD) | Sample: {df['observation_date'].iloc[0]}")

print("\nLOADED_AT:")
print(f"  Type: String (ISO 8601) | Sample: {df['loaded_at'].iloc[0]}")

print("\n" + "=" * 130)
print("SUMMARY: THE COMPLETE PICTURE")
print("=" * 130)

summary = """
TARGET VARIABLE: default_flag (0=Healthy, 1=Default)

32 INPUT FEATURES:
  Financial Metrics (4):     de_ratio, interest_coverage, profitability, liquidity_ratio
  Demographics (9):          age, employment, years_employed, income, dependents, etc.
  Credit History (6):        cibil_score, previous_default, customer_tenure, late_payments
  Macro-Economic (4):        GDP growth, inflation, policy rate, unemployment
  Trends (8):                Delta features + macro_regime_score
  Other (1):                 is_rural

DATASET SIZE: 1,166 records
  Healthy: 1,141 (97.86%)
  Defaults: 25 (2.14%)
  Split: 932 train, 234 test

WHAT THE MODEL LEARNS:
  Using 32 financial and personal features to predict if a borrower will default
  Output: Probability of Default (0% to 100%)
  Decision: Approve, Refer, or Decline based on risk level
"""

print(summary)
