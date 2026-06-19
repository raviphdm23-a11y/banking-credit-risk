"""
backfill_exposure_class.py
═══════════════════════════════════════════════════════════════

Backfill exposure_class for all 1,408 existing loans based on:
  1. loans.type (loan product category)
  2. customer_kyc.employment_type (borrower employment)

Mapping aligns with Basel III.1 Standardized Approach.
Idempotent — safe to re-run.

Usage:
  python operations/scripts/backfill_exposure_class.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'bank.db')

# Basel III.1 exposure class mapping logic
def determine_exposure_class(loan_type, employment_type, is_rural=False):
    """
    Map loan type + employment type to Basel III.1 exposure class.

    Args:
        loan_type: from loans.type (e.g., 'Home Loan', 'Business Loan')
        employment_type: from customer_kyc.employment_type (e.g., 'SALARIED', 'BUSINESS')
        is_rural: customer is rural (future refinement: ADC for rural land)

    Returns:
        str: exposure_class code (e.g., 'RETAIL_MORTGAGES', 'CORPORATE')
    """

    # Home Loan → Retail Mortgages (will use LTV banding if captured)
    if loan_type == 'Home Loan':
        return 'RETAIL_MORTGAGES'

    # Vehicle Loan → Retail Other (auto lending)
    if loan_type == 'Vehicle Loan':
        return 'RETAIL_OTHER'

    # Personal Loan → Retail Other (unsecured retail)
    if loan_type == 'Personal Loan':
        return 'RETAIL_OTHER'

    # Education Loan → Retail Other (education lending)
    if loan_type == 'Education Loan':
        return 'RETAIL_OTHER'

    # Business Loan → depends on employment type
    if loan_type == 'Business Loan':
        # BUSINESS or SELF_EMPLOYED → SME (small/medium enterprise)
        if employment_type in ('BUSINESS', 'SELF_EMPLOYED'):
            return 'SME'
        # Salaried person taking business loan → unclear, assume CORPORATE
        # (In practice, would need turnover/employee count to classify as SME)
        else:
            return 'CORPORATE'

    # Fallback for unrecognized types
    return 'CORPORATE'


def backfill(db_path=DB_PATH, verbose=True):
    """Backfill exposure_class for all existing loans."""
    if not os.path.exists(db_path):
        print(f'ERROR: {db_path} does not exist')
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Load all loans with their employment type
    c.execute('''
        SELECT l.id, l.type, kyc.employment_type, kyc.is_rural
        FROM loans l
        LEFT JOIN customers cust ON cust.id = l.cid AND cust.bank_id = l.bank_id
        LEFT JOIN customer_kyc kyc ON kyc.cid = l.cid AND kyc.bank_id = l.bank_id
        ORDER BY l.bank_id, l.id
    ''')
    loans = c.fetchall()

    updated = 0
    mapping_summary = {}

    for loan_id, loan_type, emp_type, is_rural in loans:
        ec = determine_exposure_class(loan_type, emp_type or 'UNKNOWN', is_rural or 0)

        c.execute('UPDATE loans SET exposure_class = ? WHERE id = ?', (ec, loan_id))
        updated += 1

        # Track mapping counts
        key = f'{loan_type} + {emp_type} => {ec}'
        mapping_summary[key] = mapping_summary.get(key, 0) + 1

    conn.commit()

    if verbose:
        print(f'[OK] Backfilled exposure_class for {updated} loans')
        print()
        print('Mapping Summary:')
        for mapping, count in sorted(mapping_summary.items()):
            print(f'  {count:4d}  {mapping}')

    # Verify
    c.execute('''
        SELECT exposure_class, COUNT(*) FROM loans
        GROUP BY exposure_class ORDER BY exposure_class
    ''')
    print()
    print('Final Distribution by Exposure Class:')
    for ec, count in c.fetchall():
        pct = 100 * count / updated
        print(f'  {ec:<20}  {count:4d} ({pct:5.1f}%)')

    # Check for NULLs
    c.execute('SELECT COUNT(*) FROM loans WHERE exposure_class IS NULL')
    nulls = c.fetchone()[0]
    if nulls > 0:
        print(f'\n[WARN] {nulls} loans still have NULL exposure_class')

    conn.close()


if __name__ == '__main__':
    backfill()
