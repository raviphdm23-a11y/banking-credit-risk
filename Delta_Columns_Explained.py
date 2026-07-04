import pandas as pd

df = pd.read_csv('ML_Training_Data.csv')

print("=" * 130)
print("DELTA COLUMNS - TREND & CHANGE FEATURES")
print("=" * 130)

print("\nDelta columns capture HOW METRICS CHANGE OVER TIME")
print("They represent the trend/momentum - are things getting better or worse?\n")

# Get delta columns
delta_cols = ['delta_de_ratio', 'delta_cibil', 'delta_gdp_pct', 'delta_cpi_pct',
              'delta_policy_rate_pct', 'delta_unemployment_pct', 'months_since_origination',
              'macro_regime_score']

print("=" * 130)
print("DETAILED BREAKDOWN OF EACH DELTA COLUMN")
print("=" * 130)

explanations = {
    'delta_de_ratio': {
        'description': 'Change in Debt-to-Equity Ratio (trend)',
        'meaning': 'How the borrower\'s leverage has changed',
        'interpretation': 'Positive = Getting MORE leveraged (WORSE) | Negative = Getting LESS leveraged (BETTER)',
        'example': '+0.5 means D/E ratio increased by 0.5 (borrower took on more debt)'
    },
    'delta_cibil': {
        'description': 'Change in CIBIL Score (absolute points)',
        'meaning': 'How credit score has moved over time',
        'interpretation': 'Positive = Score improving (BETTER) | Negative = Score declining (WORSE)',
        'example': '+50 means CIBIL increased 50 points | -30 means decreased 30 points'
    },
    'delta_gdp_pct': {
        'description': 'Change in GDP Growth Rate (percentage points)',
        'meaning': 'How economic growth is trending',
        'interpretation': 'Positive = Economy accelerating (BETTER) | Negative = Economy slowing (WORSE)',
        'example': '+0.5 means GDP growth increased by 0.5 percentage points'
    },
    'delta_cpi_pct': {
        'description': 'Change in Inflation/CPI (percentage points)',
        'meaning': 'How inflation is trending',
        'interpretation': 'Positive = Inflation rising (usually WORSE) | Negative = Inflation falling (usually BETTER)',
        'example': '+0.3 means inflation increased by 0.3 percentage points'
    },
    'delta_policy_rate_pct': {
        'description': 'Change in Central Bank Policy Rate (percentage points)',
        'meaning': 'How interest rates are trending',
        'interpretation': 'Positive = Rates rising = HARDER for borrowers | Negative = Rates falling = EASIER',
        'example': '+0.25 means policy rate increased by 25 basis points'
    },
    'delta_unemployment_pct': {
        'description': 'Change in Unemployment Rate (percentage points)',
        'meaning': 'How labor market is trending',
        'interpretation': 'Positive = Unemployment rising (WORSE) | Negative = Unemployment falling (BETTER)',
        'example': '+1.5 means unemployment increased 1.5 percentage points'
    },
    'months_since_origination': {
        'description': 'Months elapsed since loan was originated',
        'meaning': 'Loan vintage/age - how old is the loan?',
        'interpretation': 'Higher = Older loan | Lower = Newer loan',
        'example': '36 months = 3-year-old loan | 6 months = newly originated'
    },
    'macro_regime_score': {
        'description': 'Overall macro-economic regime strength score',
        'meaning': 'Composite score of economic environment quality',
        'interpretation': 'Higher = Better macro environment | Lower = Worse macro environment',
        'example': 'Score reflecting combined effect of GDP, inflation, unemployment, rates'
    }
}

for col, info in explanations.items():
    stats = df[col].describe()
    print(f"\n{'='*130}")
    print(f"COLUMN: {col.upper()}")
    print(f"{'='*130}")
    print(f"\nDescription: {info['description']}")
    print(f"Meaning: {info['meaning']}")
    print(f"Interpretation: {info['interpretation']}")
    print(f"Example: {info['example']}")
    print(f"\nData Statistics:")
    print(f"  Mean: {stats['mean']:10.4f}")
    print(f"  Median: {stats['50%']:10.4f}")
    print(f"  Std Dev: {stats['std']:10.4f}")
    print(f"  Min: {stats['min']:10.4f}")
    print(f"  Max: {stats['max']:10.4f}")
    print(f"  Range: {stats['max'] - stats['min']:10.4f}")

print("\n" + "="*130)
print("WHY ARE DELTA/TREND FEATURES IMPORTANT?")
print("="*130)

importance = """
1. PREDICTIVE POWER:
   - Static metrics tell WHAT is happening NOW
   - Delta metrics tell WHICH DIRECTION things are moving
   - Direction is often more predictive than absolute value

   Example: Two borrowers with same D/E ratio of 1.5
     Borrower A: D/E was 1.0 last year (DELTA = +0.5) - GETTING WORSE
     Borrower B: D/E was 2.0 last year (DELTA = -0.5) - GETTING BETTER
     Borrower B is lower risk despite same current D/E!

2. MOMENTUM/TREND ANALYSIS:
   - Deteriorating CIBIL score (-30 points) = RED FLAG
   - Improving CIBIL score (+50 points) = GOOD SIGN
   - Even if current scores are same, direction matters

3. MACRO-ECONOMIC CONTEXT:
   - Rising rates (delta_policy_rate_pct > 0) = harder for borrowers
   - Rising unemployment (delta_unemployment_pct > 0) = riskier environment
   - Slowing GDP (delta_gdp_pct < 0) = worse economy

4. LOAN PERFORMANCE OVER TIME:
   - months_since_origination tells how the loan has aged
   - Early defaults (6 months) vs late defaults (36+ months) are different
   - Model learns different patterns for different loan ages

EXAMPLE RISK SCENARIOS:

Scenario 1: DETERIORATING BORROWER
  Current D/E: 1.5 (okay)
  Delta D/E: +0.8 (getting worse) --> RISK SIGNAL
  Current CIBIL: 700 (good)
  Delta CIBIL: -60 (declining) --> RISK SIGNAL

Scenario 2: IMPROVING BORROWER
  Current D/E: 1.8 (high)
  Delta D/E: -0.5 (improving) --> REDUCING RISK
  Current CIBIL: 680 (fair)
  Delta CIBIL: +40 (improving) --> REDUCING RISK

Scenario 3: DIFFICULT MACRO ENVIRONMENT
  Delta Policy Rate: +0.75% (rates rising) --> TIGHTENS CONDITIONS
  Delta Unemployment: +1.2% (jobs declining) --> WORSENS CONDITIONS
  Delta GDP: -0.5% (economy slowing) --> WORSENS CONDITIONS
"""

print(importance)

print("\n" + "="*130)
print("CURRENT DATA STATUS")
print("="*130)

# Check current values
print(f"\nCurrent status of delta columns in your data:")
print(f"  delta_de_ratio values: min={df['delta_de_ratio'].min():.4f}, max={df['delta_de_ratio'].max():.4f}")
print(f"  delta_cibil values: min={df['delta_cibil'].min():.0f}, max={df['delta_cibil'].max():.0f}")
print(f"  delta_gdp_pct values: min={df['delta_gdp_pct'].min():.4f}, max={df['delta_gdp_pct'].max():.4f}")
print(f"  delta_cpi_pct values: min={df['delta_cpi_pct'].min():.4f}, max={df['delta_cpi_pct'].max():.4f}")
print(f"  delta_unemployment_pct values: min={df['delta_unemployment_pct'].min():.4f}, max={df['delta_unemployment_pct'].max():.4f}")
print(f"  months_since_origination: min={df['months_since_origination'].min():.2f}, max={df['months_since_origination'].max():.2f}")

# Check correlation with default
print(f"\nCorrelation with default_flag:")
for col in delta_cols:
    corr = df[col].corr(df['default_flag'])
    strength = ''
    if abs(corr) > 0.3:
        strength = '(HIGH CORRELATION)'
    elif abs(corr) > 0.1:
        strength = '(MODERATE)'
    print(f"  {col:30} : {corr:8.4f} {strength}")

print("\n" + "="*130)
print("SUMMARY TABLE: ALL DELTA COLUMNS AT A GLANCE")
print("="*130)

summary_data = []
for col in delta_cols:
    stats = df[col].describe()
    summary_data.append({
        'Column': col,
        'Mean': f"{stats['mean']:.4f}",
        'Min': f"{stats['min']:.4f}",
        'Max': f"{stats['max']:.4f}",
        'Correlation': f"{df[col].corr(df['default_flag']):.4f}"
    })

summary_df = pd.DataFrame(summary_data)
print(summary_df.to_string(index=False))

print("\n" + "="*130)
print("KEY TAKEAWAY")
print("="*130)
print("""
Delta columns are "LEADING INDICATORS" of default risk.

Static metrics (current D/E, current CIBIL) show CURRENT condition.
Delta metrics (change in D/E, change in CIBIL) show TRAJECTORY.

A borrower with:
  - High current D/E BUT declining delta D/E = improving, lower risk
  - Low current D/E BUT increasing delta D/E = deteriorating, higher risk

The model uses BOTH to make better predictions about future default!
""")
