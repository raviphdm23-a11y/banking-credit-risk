"""
archive_old_transactions.py
────────────────────────────
Moves old, no-longer-operationally-relevant rows out of `transactions` into
a separate `transactions_archive` table (same schema), then deletes them
from the live table. Nothing is destroyed - archived rows remain queryable
via `transactions_archive`, just no longer scanned by day-to-day app queries.

Why this cutoff is safe (see conversation this was designed from):
  - Every row with `loan_id_ref IS NOT NULL` (i.e. tied to loan NPA/
    delinquency tracking) falls on/after 2025-01-01 - nothing before that
    date has ever been loan-linked. Archiving before that date cannot affect
    NPA resolution, bank_loan_metrics, or fact_credit_risk lineage.
  - It matches the platform's own documented "18-month deposit-neutral
    transaction history" design window for foreign-bank ledgers.

Two safety guards (both non-negotiable, apply regardless of DEFAULT_CUTOFF):
  1. ACTIVE-LOAN GUARD: any transaction linked (via loan_id_ref) to a loan
     whose status is still 'Active' is NEVER archived, no matter how old.
     At the recommended cutoff this is a no-op (zero loan-linked rows exist
     that far back) - it exists so that if this cutoff is ever pushed later
     without re-reading this file's docstring, Active loans stay protected
     automatically.
  2. LAST-TRANSACTION GUARD: an account's single most recent transaction is
     never archived, even if it predates the cutoff - so no account/customer
     view in Operations ever goes to literally zero visible history.

This script is DELETE-then-VACUUM, not a hard destructive drop:
  - Rows are copied to `transactions_archive` first (idempotent - reruns
    just insert whatever's newly eligible, `INSERT OR IGNORE` on primary key)
  - Only rows successfully copied are deleted from `transactions`
  - VACUUM is opt-in (--vacuum) since it locks the DB and takes a while

Does NOT touch `loans` at all - a loan's status/lifecycle is untouched by
archiving its transaction history. See reconcile_ledger.py's docstring
before ever re-running that script against an archived ledger - it assumes
full per-account history from account inception to size an opening balance
cushion, which archived accounts no longer have.

Run:
    python operations/scripts/archive_old_transactions.py            # dry run
    python operations/scripts/archive_old_transactions.py --apply    # actually archive
    python operations/scripts/archive_old_transactions.py --apply --vacuum   # + reclaim disk space
    python operations/scripts/archive_old_transactions.py --apply --cutoff 2024-07-12
"""

import argparse
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')
DEFAULT_CUTOFF = '2025-01-01'

ARCHIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions_archive (
    id TEXT PRIMARY KEY, bank_id TEXT, aid TEXT, date TEXT, time TEXT, type TEXT,
    amount REAL, balance_after REAL, desc TEXT,
    cust_age INTEGER, cust_gender TEXT, cust_employment_type TEXT, cust_education_level TEXT,
    cust_years_employed REAL, cust_marital_status TEXT, cust_num_dependents INTEGER,
    cust_state TEXT, cust_industry_sector TEXT, cust_annual_income REAL, cust_other_income REAL,
    cust_foir_declared REAL, cust_cibil_score INTEGER, cust_years_at_address REAL,
    cust_is_rural INTEGER, cust_is_pep INTEGER,
    loan_id_ref TEXT, loan_de_ratio REAL, loan_interest_coverage REAL, loan_profitability REAL,
    loan_liquidity_ratio REAL, loan_prior_de REAL, loan_prior_cibil INTEGER, loan_pd_score REAL,
    loan_classification TEXT, loan_exposure_class TEXT, loan_purpose TEXT,
    macro_gdp_growth_pct REAL, macro_inflation_cpi_pct REAL, macro_policy_rate_pct REAL,
    macro_unemployment_pct REAL, delta_de_ratio REAL, delta_cibil INTEGER, delta_gdp_pct REAL,
    delta_cpi_pct REAL, delta_policy_rate_pct REAL, delta_unemployment_pct REAL,
    months_since_origination INTEGER, macro_regime_score REAL, default_flag INTEGER,
    pd_observed TEXT, employment_type_enc INTEGER, city_tier_enc INTEGER, education_enc INTEGER,
    residence_type_enc INTEGER, loan_purpose_enc INTEGER, loan_classification_enc INTEGER,
    archived_at TEXT DEFAULT (datetime('now'))
)
"""

# Eligibility query, both guards applied:
#   - date < cutoff
#   - NOT this account's single most-recent transaction (LAST-TRANSACTION GUARD)
#   - NOT linked to a currently-Active loan (ACTIVE-LOAN GUARD)
ELIGIBLE_SQL = """
    SELECT t.*
    FROM transactions t
    WHERE t.date < ?
      AND t.id NOT IN (
          SELECT id FROM (
              SELECT id, aid, date,
                     ROW_NUMBER() OVER (PARTITION BY aid ORDER BY date DESC, time DESC, id DESC) AS rn
              FROM transactions
          ) WHERE rn = 1
      )
      AND (
          t.loan_id_ref IS NULL
          OR t.loan_id_ref NOT IN (SELECT id FROM loans WHERE status = 'Active')
      )
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cutoff', default=DEFAULT_CUTOFF, help=f'Archive rows older than this date (default {DEFAULT_CUTOFF})')
    ap.add_argument('--apply', action='store_true', help='Actually archive + delete. Without this flag, dry-run only.')
    ap.add_argument('--vacuum', action='store_true', help='Run VACUUM after deleting, to reclaim disk space. Slower, locks the DB.')
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_before = cur.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]

    eligible = cur.execute(ELIGIBLE_SQL, (args.cutoff,)).fetchall()
    n_eligible = len(eligible)

    # Diagnostics: how many rows were excluded by each guard, for visibility.
    n_older = cur.execute('SELECT COUNT(*) FROM transactions WHERE date < ?', (args.cutoff,)).fetchone()[0]
    n_protected_by_last_txn = n_older - cur.execute(f"""
        SELECT COUNT(*) FROM transactions t WHERE t.date < ?
        AND t.id NOT IN (
            SELECT id FROM (
                SELECT id, aid, date, ROW_NUMBER() OVER (PARTITION BY aid ORDER BY date DESC, time DESC, id DESC) AS rn
                FROM transactions
            ) WHERE rn = 1
        )
    """, (args.cutoff,)).fetchone()[0]
    n_active_loan_linked_old = cur.execute("""
        SELECT COUNT(*) FROM transactions t
        WHERE t.date < ? AND t.loan_id_ref IN (SELECT id FROM loans WHERE status = 'Active')
    """, (args.cutoff,)).fetchone()[0]

    print(f'Cutoff: rows with date < {args.cutoff}')
    print(f'  Total transactions in table today: {total_before:,}')
    print(f'  Rows older than cutoff:            {n_older:,}')
    print(f'    - protected (account\'s last txn): {n_protected_by_last_txn:,}')
    print(f'    - protected (linked to Active loan): {n_active_loan_linked_old:,}')
    print(f'  Eligible for archival:             {n_eligible:,} ({n_eligible/total_before*100:.1f}% of table)')
    print()

    if not args.apply:
        print('Dry run only - no changes made. Re-run with --apply to archive + delete these rows.')
        conn.close()
        return

    if n_eligible == 0:
        print('Nothing eligible to archive.')
        conn.close()
        return

    cur.execute(ARCHIVE_SCHEMA)

    cols = [d for d in eligible[0].keys()]
    placeholders = ','.join('?' * len(cols))
    col_list = ','.join(cols)
    rows = [tuple(r[c] for c in cols) for r in eligible]
    cur.executemany(
        f'INSERT OR IGNORE INTO transactions_archive ({col_list}) VALUES ({placeholders})', rows
    )
    n_archived = cur.rowcount if cur.rowcount != -1 else len(rows)
    print(f'Copied {len(rows):,} rows into transactions_archive (executemany rowcount is per-statement, not cumulative - verifying via COUNT next).')

    archive_total = cur.execute('SELECT COUNT(*) FROM transactions_archive').fetchone()[0]
    print(f'transactions_archive now holds {archive_total:,} rows total.')

    ids = [r['id'] for r in eligible]
    deleted = 0
    CHUNK = 500
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        ph = ','.join('?' * len(chunk))
        deleted += cur.execute(f'DELETE FROM transactions WHERE id IN ({ph})', chunk).rowcount

    conn.commit()

    total_after = cur.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
    print(f'\nDeleted {deleted:,} rows from transactions.')
    print(f'transactions: {total_before:,} -> {total_after:,} rows')

    if args.vacuum:
        print('\nRunning VACUUM to reclaim disk space (this can take a while + locks the DB)...')
        conn.execute('VACUUM')
        print('VACUUM complete.')
    else:
        print('\nNote: SQLite does not shrink the file on DELETE alone. '
              'Re-run with --vacuum to actually reclaim disk space.')

    conn.close()
    print('\nDone. Archived rows remain queryable in transactions_archive - nothing was destroyed.')


if __name__ == '__main__':
    main()
