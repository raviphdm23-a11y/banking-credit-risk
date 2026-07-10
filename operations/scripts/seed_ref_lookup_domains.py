"""
seed_ref_lookup_domains.py
──────────────────────────
Seeds the 5 KYC-categorical domains (employment_type, education_level,
residence_type, city_tier, loan_purpose) into ref_lookup, using the same
codes/risk-ordering already used elsewhere in the codebase
(operations/scripts/enrich_transactions_with_ml_features.py's
EMPLOYMENT_TYPE_ENC / EDUCATION_ENC / CITY_TIER_ENC / RESIDENCE_TYPE_ENC /
LOAN_PURPOSE_ENC dicts) so sync_bank_loan_metrics.py's ref_lookup joins
resolve instead of silently returning NULL for every row.

Root cause: these domain rows were apparently dropped/never (re)created in
a prior DB rebuild - ref_lookup only had the exposure_class domain seeded
by create_exposure_class_taxonomy.py, which self-documents this same gap.

Idempotent - only inserts a domain's rows if that domain has none yet.

Run:
    python operations/scripts/seed_ref_lookup_domains.py
"""

import os
import sqlite3

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

DOMAINS = {
    # First 5 codes/risk_order per domain match
    # operations/scripts/enrich_transactions_with_ml_features.py's
    # EMPLOYMENT_TYPE_ENC/EDUCATION_ENC/CITY_TIER_ENC/RESIDENCE_TYPE_ENC/
    # LOAN_PURPOSE_ENC exactly, so the customer-level (bank_loan_metrics)
    # and transaction-level training paths encode the same code the same
    # way. Extra codes appended below (found via customer_kyc's actual
    # distinct values, which is a superset of that older dict) get the
    # next risk_order slot so they don't collide with the shared ones.
    # employment_type_enc's valid range (trainer._validate_dataframe /
    # validate_file) is capped at 7, so the 3 extra codes found in
    # customer_kyc beyond the original 5 are folded into risk_order 6-7
    # rather than given their own slots past that ceiling.
    'employment_type': {
        'SALARIED':      1,
        'SELF_EMPLOYED': 2,
        'BUSINESS':      3,
        'PROFESSIONAL':  4,
        'GOVT':          5,
        'FREELANCE':     6,
        'RETIRED':       7,
        'STUDENT':       7,
    },
    'education_level': {
        'HIGH_SCHOOL':    1,
        'DIPLOMA':        2,
        'GRADUATE':       3,
        'POST_GRADUATE':  4,
        'PROFESSIONAL':   5,
        'PHD':            6,
    },
    'city_tier': {
        'TIER1': 1,
        'TIER2': 2,
        'TIER3': 3,
        # Legacy/bad seed value found in a handful of customer_kyc rows -
        # aliased to TIER1's risk_order rather than left NULL.
        '1':     1,
    },
    'residence_type': {
        'OWNED':    1,
        'RENTED':   2,
        'FAMILY':   3,
        'EMPLOYER': 4,
    },
    'loan_purpose': {
        'HOME_PURCHASE': 1,
        'AUTO':          2,
        'PERSONAL':      3,
        'BUSINESS':      4,
        'EDUCATION':     5,
        'VEHICLE':       6,
    },
}


def seed(db_path=DB_PATH, verbose=True):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

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

    for domain, codes in DOMAINS.items():
        c.execute("SELECT COUNT(*) FROM ref_lookup WHERE domain=?", (domain,))
        existing = c.fetchone()[0]
        if existing > 0:
            if verbose:
                print(f'{domain}: already seeded ({existing} rows). Skipping.')
            continue

        for code, risk_order in codes.items():
            c.execute(
                """INSERT INTO ref_lookup (domain, code, label, risk_order, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (domain, code, code.replace('_', ' ').title(), risk_order)
            )
        if verbose:
            print(f'{domain}: inserted {len(codes)} codes.')

    conn.commit()
    conn.close()


if __name__ == '__main__':
    seed()
