#!/usr/bin/env python3
"""
Derive behavioral features from each loan's transaction history and backfill
them onto bank_loan_metrics (one row per loan - same grain as the existing
customer-level training source, so this adds real signal from transactions
without the group-leakage risk of training on individual transaction rows).

Features per loan (only computed for loans whose customer has an account with
transaction history; others get neutral defaults, not zeros, to avoid biasing
in either direction):
    n_transactions          total transaction count on the account
    n_income_txns           count of income-type deposits (salary/business income)
    n_emi_txns              count of EMI Payment transactions
    expected_emi_count      months since origination (only meaningful if the
                             loan actually carries an EMI - i.e. emi > 0)
    emi_miss_ratio          1 - n_emi_txns / expected_emi_count, clipped [0,1]
    expected_income_count   months since account was opened (proxy: same as
                             months_since_origination, since income is monthly)
    income_miss_ratio       1 - n_income_txns / expected_income_count, clipped [0,1]
    avg_income_amt          mean amount of income-type transactions
    income_cv               coefficient of variation (std/mean) of income amounts -
                             volatility of the borrower's income, a classic
                             behavioral-scorecard feature
    income_to_declared_ratio (avg_income_amt * 12) / annual_income - flags
                             borrowers whose actual observed income is much
                             lower than what they declared at origination
    min_balance             minimum balance_after seen on the account
    avg_balance             mean balance_after
    balance_cv              coefficient of variation of balance_after
    max_gap_days            longest gap in days between consecutive transactions
                             (dormancy/irregularity signal)

Run:  python operations/scripts/build_behavioral_features.py
"""
import os
import sqlite3
import statistics
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

NEW_COLUMNS = [
    ('n_transactions',           'INTEGER'),
    ('n_income_txns',            'INTEGER'),
    ('n_emi_txns',                'INTEGER'),
    ('expected_emi_count',       'INTEGER'),
    ('emi_miss_ratio',           'REAL'),
    ('expected_income_count',    'INTEGER'),
    ('income_miss_ratio',        'REAL'),
    ('avg_income_amt',           'REAL'),
    ('income_cv',                'REAL'),
    ('income_to_declared_ratio', 'REAL'),
    ('min_balance',              'REAL'),
    ('avg_balance',              'REAL'),
    ('balance_cv',               'REAL'),
    ('max_gap_days',             'REAL'),
]

INCOME_TYPES = ('Deposit',)  # salary/business income modeled as 'Deposit' type in seed scripts


def add_columns(conn):
    cur = conn.cursor()
    for col, typ in NEW_COLUMNS:
        try:
            cur.execute(f"ALTER TABLE bank_loan_metrics ADD COLUMN {col} {typ}")
            print(f"  [+] Added {col}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  [*] {col} already exists")
            else:
                raise
    conn.commit()


def _cv(values):
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    return statistics.pstdev(values) / abs(mean)


def build_features(conn):
    cur = conn.cursor()

    loans = cur.execute("""
        SELECT bank_id, loan_id, months_since_origination, annual_income
        FROM bank_loan_metrics
    """).fetchall()

    # Map loan_id -> cid via loans table, then cid -> account ids via accounts.
    loan_to_cid = dict(cur.execute("SELECT id, cid FROM loans").fetchall())
    cid_accounts = {}
    for aid, cid in cur.execute("SELECT id, cid FROM accounts").fetchall():
        cid_accounts.setdefault(cid, []).append(aid)

    updated, skipped = 0, 0
    for bank_id, loan_id, months_since_origination, annual_income in loans:
        cid = loan_to_cid.get(loan_id)
        acc_ids = cid_accounts.get(cid, []) if cid else []
        if not acc_ids:
            skipped += 1
            continue

        placeholders = ','.join('?' * len(acc_ids))
        rows = cur.execute(f"""
            SELECT date, type, amount, balance_after
            FROM transactions
            WHERE aid IN ({placeholders})
            ORDER BY date, time
        """, acc_ids).fetchall()

        if not rows:
            skipped += 1
            continue

        n_transactions = len(rows)
        income_amts = [r[2] for r in rows if r[1] in INCOME_TYPES]
        emi_amts    = [r[2] for r in rows if r[1] == 'EMI Payment']
        balances    = [r[3] for r in rows if r[3] is not None]

        # Expected month count MUST come from the account's own observed
        # transaction span, not months_since_origination (loan age). Loans can
        # be years older than the ~18-month transaction history window that
        # was actually generated, so using loan age as the denominator would
        # manufacture a large "miss ratio" for old-but-current loans purely
        # from window mismatch - noise, not behavior.
        all_dates = sorted({r[0] for r in rows if r[0]})
        if len(all_dates) >= 2:
            d0 = datetime.strptime(all_dates[0], '%Y-%m-%d')
            d1 = datetime.strptime(all_dates[-1], '%Y-%m-%d')
            observed_months = max(1, round((d1 - d0).days / 30.44) + 1)
        else:
            observed_months = 1

        n_income_txns = len(income_amts)
        n_emi_txns    = len(emi_amts)

        expected_income_count = observed_months
        income_miss_ratio = max(0.0, min(1.0, 1 - n_income_txns / expected_income_count))

        # Only loans that actually have EMI history are expected to show one;
        # for EMI-less products (e.g. deposit-only relationships) leave neutral.
        expected_emi_count = observed_months if n_emi_txns > 0 else 0
        emi_miss_ratio = (max(0.0, min(1.0, 1 - n_emi_txns / expected_emi_count))
                          if expected_emi_count > 0 else 0.0)

        avg_income_amt = statistics.mean(income_amts) if income_amts else 0.0
        income_cv = _cv(income_amts)
        income_to_declared_ratio = (
            (avg_income_amt * 12) / annual_income if annual_income else 1.0
        )

        min_balance = min(balances) if balances else 0.0
        avg_balance = statistics.mean(balances) if balances else 0.0
        balance_cv = _cv(balances)

        dates = [datetime.strptime(r[0], '%Y-%m-%d') for r in rows if r[0]]
        max_gap_days = 0.0
        if len(dates) > 1:
            dates.sort()
            gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates) - 1)]
            max_gap_days = float(max(gaps))

        cur.execute("""
            UPDATE bank_loan_metrics SET
                n_transactions = ?, n_income_txns = ?, n_emi_txns = ?,
                expected_emi_count = ?, emi_miss_ratio = ?,
                expected_income_count = ?, income_miss_ratio = ?,
                avg_income_amt = ?, income_cv = ?, income_to_declared_ratio = ?,
                min_balance = ?, avg_balance = ?, balance_cv = ?, max_gap_days = ?
            WHERE loan_id = ?
        """, (
            n_transactions, n_income_txns, n_emi_txns,
            expected_emi_count, round(emi_miss_ratio, 4),
            expected_income_count, round(income_miss_ratio, 4),
            round(avg_income_amt, 2), round(income_cv, 4), round(income_to_declared_ratio, 4),
            round(min_balance, 2), round(avg_balance, 2), round(balance_cv, 4), max_gap_days,
            loan_id
        ))
        updated += 1

    conn.commit()
    print(f"\nUpdated {updated} loans with behavioral features; skipped {skipped} (no transaction history)")


def main():
    conn = sqlite3.connect(DB_PATH)
    print("Adding behavioral feature columns to bank_loan_metrics...")
    add_columns(conn)
    print("\nComputing behavioral features from transaction history...")
    build_features(conn)
    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
