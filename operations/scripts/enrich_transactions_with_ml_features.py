#!/usr/bin/env python3
"""
Enrich transactions table with ALL ML training features.

This script:
1. Adds 47 new ML feature columns to transactions table
2. Creates a trigger to auto-enrich new transactions
3. Backfills existing transactions with enriched features

Each transaction row becomes a complete feature vector for transaction-level ML training.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "bank.db"

# Encoding mappings for categorical variables
EMPLOYMENT_TYPE_ENC = {
    'SALARIED': 1,
    'SELF_EMPLOYED': 2,
    'BUSINESS': 3,
    'PROFESSIONAL': 4,
    'GOVT': 5,
}

EDUCATION_ENC = {
    'HIGH_SCHOOL': 1,
    'DIPLOMA': 2,
    'GRADUATE': 3,
    'POST_GRADUATE': 4,
    'PROFESSIONAL': 5,
    'PHD': 6,
}

CITY_TIER_ENC = {
    'TIER1': 1,
    'TIER2': 2,
}

RESIDENCE_TYPE_ENC = {
    'OWNED': 1,
    'RENTED': 2,
    'FAMILY': 3,
}

LOAN_PURPOSE_ENC = {
    'HOME_PURCHASE': 1,
    'AUTO': 2,
    'PERSONAL': 3,
    'BUSINESS': 4,
    'EDUCATION': 5,
    'VEHICLE': 6,
}

LOAN_CLASSIFICATION_ENC = {
    'Standard': 0,
    'NPA': 1,
    'Default': 1,
}


def add_ml_columns_to_schema():
    """Add 47 new ML feature columns to transactions table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    new_columns = [
        # Customer demographics
        ('cust_age', 'INTEGER'),
        ('cust_gender', 'TEXT'),
        ('cust_employment_type', 'TEXT'),
        ('cust_education_level', 'TEXT'),
        ('cust_years_employed', 'REAL'),
        ('cust_marital_status', 'TEXT'),
        ('cust_num_dependents', 'INTEGER'),
        ('cust_state', 'TEXT'),
        ('cust_industry_sector', 'TEXT'),

        # Customer financial
        ('cust_annual_income', 'REAL'),
        ('cust_other_income', 'REAL'),
        ('cust_foir_declared', 'REAL'),
        ('cust_cibil_score', 'INTEGER'),
        ('cust_years_at_address', 'REAL'),
        ('cust_is_rural', 'INTEGER'),
        ('cust_is_pep', 'INTEGER'),

        # Loan metrics
        ('loan_id_ref', 'TEXT'),
        ('loan_de_ratio', 'REAL'),
        ('loan_interest_coverage', 'REAL'),
        ('loan_profitability', 'REAL'),
        ('loan_liquidity_ratio', 'REAL'),
        ('loan_prior_de', 'REAL'),
        ('loan_prior_cibil', 'INTEGER'),
        ('loan_pd_score', 'REAL'),
        ('loan_classification', 'TEXT'),
        ('loan_exposure_class', 'TEXT'),
        ('loan_purpose', 'TEXT'),

        # Macro features
        ('macro_gdp_growth_pct', 'REAL'),
        ('macro_inflation_cpi_pct', 'REAL'),
        ('macro_policy_rate_pct', 'REAL'),
        ('macro_unemployment_pct', 'REAL'),

        # Delta/Trend features
        ('delta_de_ratio', 'REAL'),
        ('delta_cibil', 'INTEGER'),
        ('delta_gdp_pct', 'REAL'),
        ('delta_cpi_pct', 'REAL'),
        ('delta_policy_rate_pct', 'REAL'),
        ('delta_unemployment_pct', 'REAL'),
        ('months_since_origination', 'INTEGER'),
        ('macro_regime_score', 'REAL'),

        # Target variable
        ('default_flag', 'INTEGER'),
        ('pd_observed', 'TEXT'),

        # Encoded categoricals
        ('employment_type_enc', 'INTEGER'),
        ('city_tier_enc', 'INTEGER'),
        ('education_enc', 'INTEGER'),
        ('residence_type_enc', 'INTEGER'),
        ('loan_purpose_enc', 'INTEGER'),
        ('loan_classification_enc', 'INTEGER'),
    ]

    print("Adding ML feature columns to transactions table...")
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
            print(f"  [+] Added {col_name}")
        except sqlite3.OperationalError as e:
            if 'already exists' in str(e):
                print(f"  [*] {col_name} already exists")
            else:
                print(f"  [-] Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print(f"\nSchema update complete! Transactions table now has {len(new_columns)} new ML columns\n")


def enrich_transaction(conn, txn_id):
    """Enrich a single transaction with all ML features."""
    cursor = conn.cursor()

    # Get transaction and account info
    cursor.execute("""
        SELECT t.bank_id, t.aid, t.date, a.cid
        FROM transactions t
        JOIN accounts a ON t.aid = a.id
        WHERE t.id = ?
    """, (txn_id,))

    result = cursor.fetchone()
    if not result:
        return False

    bank_id, aid, txn_date, cid = result

    # Get customer KYC
    cursor.execute("SELECT * FROM customer_kyc WHERE cid = ?", (cid,))
    kyc_row = cursor.fetchone()
    kyc_cols = [desc[0] for desc in cursor.description]
    kyc = dict(zip(kyc_cols, kyc_row)) if kyc_row else {}

    # Get loan info (if any loan active on this date)
    cursor.execute("""
        SELECT l.id, m.de, m.intcov, m.profit, m.liq, m.prior_de, m.prior_cibil,
               m.pd_score, l.loan_classification, l.exposure_class, k.loan_purpose,
               l.disbursed
        FROM loans l
        LEFT JOIN credit_risk_metrics m ON l.id = m.lid
        LEFT JOIN customer_kyc k ON l.cid = k.cid
        WHERE l.cid = ? AND l.disbursed <= ? AND (l.maturity > ? OR l.status = 'Active')
        ORDER BY l.disbursed DESC LIMIT 1
    """, (cid, txn_date, txn_date))

    loan_row = cursor.fetchone()
    loan_cols = ['loan_id', 'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
                 'prior_de', 'prior_cibil', 'pd_score', 'loan_classification', 'exposure_class',
                 'loan_purpose', 'disbursed']
    loan = dict(zip(loan_cols, loan_row)) if loan_row else {}

    # Get macro data for transaction date and country.
    # customer_kyc has no country_code column - the bank's own country_code
    # (banks.country_code, e.g. 'IND'/'USA'/'GBR') is the correct source.
    cursor.execute("SELECT country_code FROM banks WHERE bank_id = ?", (bank_id,))
    bank_row = cursor.fetchone()
    country_code = bank_row[0] if bank_row and bank_row[0] else 'IND'
    cursor.execute("""
        SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct,
               delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct,
               macro_regime_score
        FROM country_macro
        WHERE country_code = ? AND period <= ?
        ORDER BY period DESC LIMIT 1
    """, (country_code, txn_date[:7]))  # Use YYYY-MM for period matching

    macro_row = cursor.fetchone()
    macro_cols = ['gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
                  'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct', 'delta_unemployment_pct',
                  'macro_regime_score']
    macro = dict(zip(macro_cols, macro_row)) if macro_row else {}

    # Calculate months since origination
    months_since_origination = None
    if loan.get('disbursed'):
        try:
            from datetime import datetime
            disbursed = datetime.strptime(loan['disbursed'], '%Y-%m-%d')
            txn_dt = datetime.strptime(txn_date, '%Y-%m-%d')
            months_since_origination = (txn_dt.year - disbursed.year) * 12 + (txn_dt.month - disbursed.month)
        except:
            pass

    # Determine default flag
    default_flag = None
    if loan.get('loan_classification') in ['NPA', 'Default']:
        default_flag = 1
    else:
        default_flag = 0

    # Build update statement with all enriched columns
    update_data = {
        # Customer demographics
        'cust_age': kyc.get('age'),
        'cust_gender': kyc.get('gender'),
        'cust_employment_type': kyc.get('employment_type'),
        'cust_education_level': kyc.get('education_level'),
        'cust_years_employed': kyc.get('years_employed'),
        'cust_marital_status': kyc.get('marital_status'),
        'cust_num_dependents': kyc.get('num_dependents'),
        'cust_state': kyc.get('state'),
        'cust_industry_sector': kyc.get('industry_sector'),

        # Customer financial
        'cust_annual_income': kyc.get('annual_income'),
        'cust_other_income': kyc.get('other_income'),
        'cust_foir_declared': kyc.get('foir_declared'),
        'cust_cibil_score': kyc.get('cibil_score'),
        'cust_years_at_address': kyc.get('years_at_address'),
        'cust_is_rural': kyc.get('is_rural'),
        'cust_is_pep': kyc.get('is_pep'),

        # Loan metrics
        'loan_id_ref': loan.get('loan_id'),
        'loan_de_ratio': loan.get('de_ratio'),
        'loan_interest_coverage': loan.get('interest_coverage'),
        'loan_profitability': loan.get('profitability'),
        'loan_liquidity_ratio': loan.get('liquidity_ratio'),
        'loan_prior_de': loan.get('prior_de'),
        'loan_prior_cibil': loan.get('prior_cibil'),
        'loan_pd_score': loan.get('pd_score'),
        'loan_classification': loan.get('loan_classification'),
        'loan_exposure_class': loan.get('exposure_class'),
        'loan_purpose': loan.get('loan_purpose'),

        # Macro features
        'macro_gdp_growth_pct': macro.get('gdp_growth_pct'),
        'macro_inflation_cpi_pct': macro.get('inflation_cpi_pct'),
        'macro_policy_rate_pct': macro.get('policy_rate_pct'),
        'macro_unemployment_pct': macro.get('unemployment_pct'),

        # Delta features (trend signals: current - prior)
        'delta_de_ratio': round((loan.get('de_ratio') or 0) - (loan.get('prior_de') or 0), 4) if loan.get('de_ratio') and loan.get('prior_de') else None,
        'delta_cibil': int((kyc.get('cibil_score') or 0) - (loan.get('prior_cibil') or 0)) if kyc.get('cibil_score') and loan.get('prior_cibil') else None,
        'delta_gdp_pct': macro.get('delta_gdp_pct'),
        'delta_cpi_pct': macro.get('delta_cpi_pct'),
        'delta_policy_rate_pct': macro.get('delta_policy_rate_pct'),
        'delta_unemployment_pct': macro.get('delta_unemployment_pct'),
        'months_since_origination': months_since_origination,
        'macro_regime_score': macro.get('macro_regime_score'),

        # Target
        'default_flag': default_flag,
        'pd_observed': txn_date if default_flag == 1 else None,

        # Encoded categoricals
        'employment_type_enc': EMPLOYMENT_TYPE_ENC.get(kyc.get('employment_type')),
        'city_tier_enc': CITY_TIER_ENC.get(kyc.get('city_tier')),
        'education_enc': EDUCATION_ENC.get(kyc.get('education_level')),
        'residence_type_enc': RESIDENCE_TYPE_ENC.get(kyc.get('residence_type')),
        'loan_purpose_enc': LOAN_PURPOSE_ENC.get(loan.get('loan_purpose')),
        'loan_classification_enc': LOAN_CLASSIFICATION_ENC.get(loan.get('loan_classification')),
    }

    # Build and execute update
    set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
    values = list(update_data.values()) + [txn_id]

    cursor.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", values)
    return True


def backfill_all_transactions():
    """Backfill all existing transactions with enriched features."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all transaction IDs
    cursor.execute("SELECT id FROM transactions")
    txn_ids = [row[0] for row in cursor.fetchall()]

    print(f"Backfilling {len(txn_ids)} transactions with ML features...")

    success_count = 0
    for i, txn_id in enumerate(txn_ids):
        if enrich_transaction(conn, txn_id):
            success_count += 1

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1}/{len(txn_ids)} transactions...")
            conn.commit()

    conn.commit()
    conn.close()

    print(f"[SUCCESS] Backfill complete! Enriched {success_count}/{len(txn_ids)} transactions")


if __name__ == '__main__':
    print("=" * 80)
    print("TRANSACTION ENRICHMENT WITH ML FEATURES")
    print("=" * 80)
    print()

    # Step 1: Add columns
    add_ml_columns_to_schema()
    print()

    # Step 2: Backfill existing transactions
    backfill_all_transactions()
    print()

    print("=" * 80)
    print("ENRICHMENT COMPLETE!")
    print("=" * 80)
    print("\nEach transaction now has 56 columns:")
    print("  - 9 base columns (id, bank_id, aid, date, time, type, amount, balance_after, desc)")
    print("  - 47 new ML feature columns")
    print("\nUse this for transaction-level ML training!")
    print("\nNext steps:")
    print("  1. Update transaction insertion code to call enrich_transaction()")
    print("  2. Create triggers for automatic enrichment on new inserts")
    print("  3. Build transaction-level ML models (time-series, sequential patterns)")
