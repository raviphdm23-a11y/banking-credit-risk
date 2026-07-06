"""
create_exposure_class_taxonomy.py
═══════════════════════════════════════════════════════════════

Create Basel III.1 Standardized Approach exposure class taxonomy
in ref_lookup table. Idempotent — safe to re-run.

14 exposure classes aligned with CRE20–CRE22 updates:
  1. SOVEREIGN_HOME (0% RW)
  2. SOVEREIGN_FOREIGN (20–150% by rating)
  3. PSE (0–100% by issuer rating)
  4. MDB (0% RW — Multilateral Development Banks)
  5. BANK (20–150% by rating)
  6. CORPORATE (100% standard / 50% if rated AAA-AA-)
  7. SME (85% — Small & Medium Enterprise)
  8. RETAIL_MORTGAGES (20–70% by LTV band)
  9. RETAIL_REVOLVING (45% — credit cards, lines)
 10. RETAIL_OTHER (75% — auto, personal loans, education)
 11. COMMERCIAL_RE (60–100% by LTV band)
 12. ADC (100–150% — Land Acquisition, Development, Construction)
 13. COVERED_BONDS (10–100% by credit quality)
 14. DEFAULT_NPA (150% — >90 days past due)

Usage:
  python operations/scripts/create_exposure_class_taxonomy.py
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'bank.db')

EXPOSURE_CLASSES = [
    {
        'code': 'SOVEREIGN_HOME',
        'label': 'Sovereign (Home)',
        'description': 'Sovereign exposure (home country). RW 0% for central bank of home country.',
        'risk_order': 1,
        'rw': 0.00,
        'haircut': '0-0%',
    },
    {
        'code': 'SOVEREIGN_FOREIGN',
        'label': 'Sovereign (Foreign)',
        'description': 'Sovereign exposure (foreign country). RW 20-150% depends on external rating (AAA-AA- 20%, A+ 50%, etc.)',
        'risk_order': 2,
        'rw': 0.20,
        'haircut': '0-2%',
    },
    {
        'code': 'PSE',
        'label': 'Public Sector Entity',
        'description': 'Public Sector Entities (government agencies). RW same as sovereign issuer rating; typically 0-100%.',
        'risk_order': 3,
        'rw': 0.50,
        'haircut': '0-2%',
    },
    {
        'code': 'MDB',
        'label': 'Multilateral Dev Bank',
        'description': 'Multilateral Development Banks (IMF, World Bank, IADB). RW 0% for qualifying MDBs per Basel list.',
        'risk_order': 4,
        'rw': 0.00,
        'haircut': '0-0%',
    },
    {
        'code': 'BANK',
        'label': 'Bank',
        'description': 'Banks and credit institutions. RW 20% (AAA-AA-), 50% (A+), 100% (A- to BBB-), 150% (below BBB-).',
        'risk_order': 5,
        'rw': 0.50,
        'haircut': '0-2%',
    },
    {
        'code': 'CORPORATE',
        'label': 'Corporate',
        'description': 'Corporate borrowers (large enterprises). Unrated: 100% RW; Rated AAA-AA-: 20% RW; A+: 50%; A- to BBB-: 100%; Below BBB-: 150%.',
        'risk_order': 6,
        'rw': 1.00,
        'haircut': '8-25%',
    },
    {
        'code': 'SME',
        'label': 'SME',
        'description': 'Small & Medium Enterprises (per Basel definition). RW 85% for SME exposures; annual sales < local threshold (typically INR 5-250 Cr).',
        'risk_order': 7,
        'rw': 0.85,
        'haircut': '8-25%',
    },
    {
        'code': 'RETAIL_MORTGAGES',
        'label': 'Retail Mortgages',
        'description': 'Retail mortgages on residential immovable property. RW 20-50% by LTV band.',
        'risk_order': 8,
        'rw': 0.35,
        'haircut': '10-15%',
    },
    {
        'code': 'RETAIL_REVOLVING',
        'label': 'Retail Revolving',
        'description': 'Retail revolving exposures (credit cards, overdrafts). RW 45% (Basel III.1 update).',
        'risk_order': 9,
        'rw': 0.45,
        'haircut': '20-35%',
    },
    {
        'code': 'RETAIL_OTHER',
        'label': 'Retail Other',
        'description': 'Retail other (auto loans, personal loans, education loans). RW 75% for retail unsecured and secured non-mortgage exposures.',
        'risk_order': 10,
        'rw': 0.75,
        'haircut': '15-25%',
    },
    {
        'code': 'COMMERCIAL_RE',
        'label': 'Commercial Real Estate',
        'description': 'Commercial real estate (office, retail, industrial, income-producing). RW 60-100% by LTV band.',
        'risk_order': 11,
        'rw': 0.80,
        'haircut': '20-30%',
    },
    {
        'code': 'ADC',
        'label': 'Land/Construction',
        'description': 'Land Acquisition, Development & Construction loans. RW 100-150% for ADC exposures.',
        'risk_order': 12,
        'rw': 1.00,
        'haircut': '0-0%',
    },
    {
        'code': 'COVERED_BONDS',
        'label': 'Covered Bonds',
        'description': 'Covered bonds (collateral-backed senior debt). RW 10-100% by credit quality.',
        'risk_order': 13,
        'rw': 0.20,
        'haircut': '0-2%',
    },
    {
        'code': 'DEFAULT_NPA',
        'label': 'Default/NPA',
        'description': 'Past-due exposures (>90 days or classified as doubtful/loss). RW 150% per Basel SA.',
        'risk_order': 14,
        'rw': 1.50,
        'haircut': '50-50%',
    },
]

def seed(db_path=DB_PATH, verbose=True):
    """Insert all 14 exposure classes into ref_lookup."""
    if not os.path.exists(db_path):
        print(f'ERROR: {db_path} does not exist')
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # ref_lookup is a shared reference table (also used by employment_type,
    # education_level, residence_type, city_tier, loan_purpose domains via
    # sync_bank_loan_metrics.py) but nothing actually creates it - it was
    # apparently dropped/never recreated in a prior DB rebuild, which is why
    # GET /api/exposure-classes 500s with "no such table: ref_lookup".
    # Idempotent create here so this seeder (and that endpoint) work standalone.
    c.execute("""
        CREATE TABLE IF NOT EXISTS ref_lookup (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            domain      TEXT NOT NULL,
            code        TEXT NOT NULL,
            label       TEXT,
            description TEXT,
            risk_order  INTEGER,
            is_active   INTEGER DEFAULT 1,
            UNIQUE(domain, code)
        )
    """)
    conn.commit()

    # Check if domain already exists
    c.execute("SELECT COUNT(*) FROM ref_lookup WHERE domain='exposure_class'")
    existing = c.fetchone()[0]

    if existing > 0:
        if verbose:
            print(f'Exposure class domain already seeded ({existing} rows). Skipping.')
        conn.close()
        return

    inserted = 0
    for ec in EXPOSURE_CLASSES:
        c.execute(
            """INSERT INTO ref_lookup
               (domain, code, label, description, risk_order, is_active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('exposure_class', ec['code'], ec['label'], ec['description'],
             ec['risk_order'], 1)
        )
        inserted += 1

    conn.commit()

    if verbose:
        print(f'[OK] Inserted {inserted} exposure classes into ref_lookup')
        print()
        print('Basel III.1 Exposure Classes (Risk Order):')
        print(f'  {"Code":<20} {"Label":<25} {"RW":>5} {"Haircut":>8}')
        print('  ' + '-' * 62)
        for ec in EXPOSURE_CLASSES:
            print(f'  {ec["code"]:<20} {ec["label"]:<25} {ec["rw"]*100:>4.0f}% {ec["haircut"]:>8}')

    conn.close()

if __name__ == '__main__':
    seed()
