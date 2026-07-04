"""
advance_transactions_may_nov2020.py
───────────────────────────────────
Extends the Axis Bank (BANK010) transaction ledger from 2020-04 through 2020-11,
bringing the granular transaction history in line with the regulatory / BS / P&L
layers (which the advance_to_*2020.py scripts already advanced to NOV2020).

It is a month-by-month replay of the exact logic in seed_april2020.py:
  • one income Deposit (days 1-5), sized from the account's historical Deposit avg/std
  • one EMI Payment (days 5-15) — SKIPPED for NPA customers and moratorium loans
  • one Bill Payment (days 14-22) from historical Bill stats
  • one UPI Payment (days 8-28) from historical UPI stats
  • running balance rolled forward from the account's last balance_after
  • txn id format  TX-{aid}-{MON}{YY}-{seq:04d}  (e.g. TX-...-MAY20-0083)
  • accounts.balance updated to the new running balance

Per-month differences vs the static April script:
  • the NPA customer set is re-queried each month (NPAs grow as DPD ages)
  • moratorium loans (moratorium=1) are treated like NPAs for EMI purposes —
    no instalment is paid during the payment holiday
  • correct number of days per month

Idempotent: skips any month that already has BANK010 transactions.

Run:  python operations/scripts/advance_transactions_may_nov2020.py
"""

import os
import sqlite3
import random
import math
import calendar
from datetime import date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

BANK_ID = 'BANK010'

# (year, month, MON-tag, YY-tag, random-seed)
MONTHS = [
    (2020, 5,  'MAY', '20', 2020_05),
    (2020, 6,  'JUN', '20', 2020_06),
    (2020, 7,  'JUL', '20', 2020_07),
    (2020, 8,  'AUG', '20', 2020_08),
    (2020, 9,  'SEP', '20', 2020_09),
    (2020, 10, 'OCT', '20', 2020_10),
    (2020, 11, 'NOV', '20', 2020_11),
]


def rand_amt(avg, std, floor=10.0):
    if std < avg * 0.05:
        std = avg * 0.10
    return max(floor, round(random.gauss(avg, std * 0.5), 2))


def hist_stats(conn, aid, txn_type):
    rows = conn.execute(
        "SELECT amount FROM transactions WHERE aid=? AND type=?", (aid, txn_type)
    ).fetchall()
    if not rows:
        return None
    amounts = [r['amount'] for r in rows]
    avg = sum(amounts) / len(amounts)
    std = (math.sqrt(sum((x - avg) ** 2 for x in amounts) / len(amounts))
           if len(amounts) > 1 else avg * 0.1)
    return {'avg': avg, 'std': std}


def month_already_seeded(conn, year, month):
    like = f"{year:04d}-{month:02d}-%"
    return conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE bank_id=? AND date LIKE ?",
        (BANK_ID, like)).fetchone()[0] > 0


def seed_month(conn, year, month, mon_tag, yy_tag, seed):
    random.seed(seed)
    last_day = calendar.monthrange(year, month)[1]

    def pick_date(day_from, day_to):
        return date(year, month, random.randint(day_from, min(day_to, last_day))).isoformat()

    # NPA customers this month — skip EMI for them
    npa_cids = {r['cid'] for r in conn.execute(
        "SELECT DISTINCT cid FROM loans WHERE bank_id=? AND loan_classification != 'Standard'",
        (BANK_ID,)).fetchall()}

    # Customers whose (Standard) loan is under moratorium this month — also skip EMI
    morat_cids = {r['cid'] for r in conn.execute(
        "SELECT DISTINCT cid FROM loans WHERE bank_id=? AND moratorium=1",
        (BANK_ID,)).fetchall()}

    accounts = conn.execute("""
        SELECT a.id, a.cid, a.type FROM accounts a
        WHERE a.bank_id=? AND a.type != 'Fixed Deposit'
        AND EXISTS (SELECT 1 FROM transactions t WHERE t.aid=a.id)
    """, (BANK_ID,)).fetchall()

    inserted = 0
    for acct in accounts:
        aid, cid, atype = acct['id'], acct['cid'], acct['type']

        last_row = conn.execute(
            "SELECT balance_after FROM transactions WHERE aid=? "
            "ORDER BY date DESC, rowid DESC LIMIT 1", (aid,)).fetchone()
        balance = float(last_row['balance_after']) if last_row and last_row['balance_after'] is not None else 0.0

        last_tx = conn.execute(
            "SELECT id FROM transactions WHERE aid=? ORDER BY rowid DESC LIMIT 1", (aid,)).fetchone()
        try:
            seq = int(last_tx['id'].split('-')[-1]) if last_tx else 0
        except Exception:
            seq = 0

        new_txns = []  # (date, type, amount, desc)

        # 1. Income Deposit
        h = hist_stats(conn, aid, 'Deposit')
        if h:
            amt = rand_amt(h['avg'], h['std'], floor=500.0)
            if 'CORP' in cid or 'SME' in cid:
                desc = '[INCOME] Business Income - Monthly business revenue deposit'
            else:
                desc = '[INCOME] Salary - Monthly salary credit'
            new_txns.append((pick_date(1, 5), 'Deposit', amt, desc))

        # 2. EMI Payment — skip NPA and moratorium customers
        if cid not in npa_cids and cid not in morat_cids:
            loan = conn.execute("""
                SELECT emi FROM loans
                WHERE cid=? AND bank_id=? AND emi > 0
                  AND loan_classification='Standard' AND moratorium=0
                LIMIT 1
            """, (cid, BANK_ID)).fetchone()
            if loan and float(loan['emi']) > 0:
                new_txns.append((pick_date(5, 15), 'EMI Payment',
                                 round(float(loan['emi']), 2),
                                 '[LOAN] EMI Payment - Monthly loan instalment'))

        # 3. Bill Payment
        h = hist_stats(conn, aid, 'Bill Payment')
        if h:
            amt = rand_amt(h['avg'], h['std'], floor=200.0)
            new_txns.append((pick_date(14, 22), 'Bill Payment', amt,
                             '[UTILITIES] Bill Payment - Electricity, internet and water'))

        # 4. UPI Payment
        h = hist_stats(conn, aid, 'UPI Payment')
        if h:
            amt = rand_amt(h['avg'], h['std'], floor=100.0)
            new_txns.append((pick_date(8, 28), 'UPI Payment', amt,
                             '[LIFESTYLE] UPI Payment - Groceries and daily expenses'))

        new_txns.sort(key=lambda x: x[0])

        for txn_date, txn_type, txn_amount, txn_desc in new_txns:
            seq += 1
            tx_id = f"TX-{aid}-{mon_tag}{yy_tag}-{seq:04d}"
            if txn_type == 'Deposit':
                balance += txn_amount
            else:
                balance = max(0.0, balance - txn_amount)
            balance = round(balance, 2)
            conn.execute("""
                INSERT INTO transactions (id, bank_id, aid, date, time, type, amount, balance_after, desc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_id, BANK_ID, aid, txn_date, '00:00:00',
                  txn_type, txn_amount, balance, txn_desc))
            inserted += 1

        conn.execute("UPDATE accounts SET balance=? WHERE id=?", (balance, aid))

    return inserted, len(accounts), len(npa_cids), len(morat_cids)


def run(db_path=DB_PATH, verbose=True):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    grand_total = 0
    for (year, month, mon_tag, yy_tag, seed) in MONTHS:
        if month_already_seeded(conn, year, month):
            if verbose:
                print(f"{year}-{month:02d}: already has BANK010 transactions — skipped")
            continue
        inserted, n_acc, n_npa, n_mor = seed_month(conn, year, month, mon_tag, yy_tag, seed)
        conn.commit()
        grand_total += inserted
        if verbose:
            print(f"{year}-{month:02d} ({mon_tag}): +{inserted:,} txns across {n_acc} accounts "
                  f"| NPA cids={n_npa}, moratorium cids={n_mor}")

    max_date = conn.execute(
        "SELECT MAX(date) FROM transactions WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
    if verbose:
        print(f"\nDone. Inserted {grand_total:,} transactions. "
              f"Latest BANK010 transaction date now: {max_date}")
    conn.close()
    return grand_total


if __name__ == '__main__':
    run()
