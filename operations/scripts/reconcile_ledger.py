"""
reconcile_ledger.py
───────────────────
Fixes the data-integrity bug where `accounts.balance` was frozen at its
seeded value and never reflected the account's transaction history, and
`balance_after` was NULL on ~97% of transactions (everything created by the
bulk generator + backfill_transactions.py).

After this script runs, the ledger is fully internally consistent:
    • every transaction has a correct running `balance_after`
    • `accounts.balance` == the latest transaction's `balance_after`

It also keeps balances *realistic*. The bulk backfill credited large monthly
salaries (e.g. ~₹290k/mo) against much smaller outflows, which — if simply
accumulated — would explode every account to ₹8-10M. So for the
bulk-backfilled discretionary-spend rows (UPI Payment, id `TX-BF-*`) we rescale
each month's amount so the account retains only a small, random monthly surplus
(6-16% of income) — i.e. the customer spends most of what they earn, as real
households do. EMI debits, bill payments, salary credits and the two
hand-seeded accounts (ACC005, ACC048) are left untouched.

Sign convention (matches the hand-seeded ledger):
    credit  = type == 'Deposit'              → increases balance
    debit   = everything else                → decreases balance
              (Bill Payment, UPI Payment, EMI Payment, Loan Payment,
               Online Transfer, Withdrawal, Debit)

Run:
    python operations/scripts/reconcile_ledger.py
"""

import os
import sqlite3
import random
from collections import defaultdict

random.seed(11)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

CREDIT_TYPES = {'Deposit'}
# Rows we are allowed to rescale to balance the monthly cash flow:
ADJUSTABLE_PREFIX = 'TX-BF-'
ADJUSTABLE_TYPES = {'UPI Payment'}


def month_key(date_str):
    # 'YYYY-MM-DD' -> 'YYYY-MM'
    return date_str[:7]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # monthly income estimate per customer (annual_income / 12), for the opening cushion
    income_by_cid = {}
    for r in cur.execute("SELECT cid, annual_income FROM customer_kyc"):
        income_by_cid[r['cid']] = (r['annual_income'] or 0) / 12.0

    accounts = cur.execute("SELECT id, cid, balance FROM accounts ORDER BY id").fetchall()
    print("Reconciling {} accounts...".format(len(accounts)))

    amount_updates = []   # (amount, txn_id)
    balance_updates = []  # (balance_after, txn_id)
    account_updates = []  # (balance, account_id)

    rescaled_rows = 0
    flagged_negative = []

    for acc in accounts:
        aid = acc['id']
        cid = acc['cid']
        txns = cur.execute(
            "SELECT id, date, time, type, amount FROM transactions "
            "WHERE aid=? ORDER BY date, time, id", (aid,)).fetchall()
        if not txns:
            continue

        # work on mutable copies of amounts
        amounts = {t['id']: float(t['amount']) for t in txns}

        # ── 1. Rebalance bulk-backfilled discretionary spend, month by month ──
        by_month = defaultdict(list)
        for t in txns:
            by_month[month_key(t['date'])].append(t)

        for mkey, rows in by_month.items():
            income = sum(amounts[t['id']] for t in rows if t['type'] in CREDIT_TYPES)
            if income <= 0:
                continue
            adjustable = [t for t in rows
                          if t['type'] in ADJUSTABLE_TYPES and t['id'].startswith(ADJUSTABLE_PREFIX)]
            if not adjustable:
                continue
            fixed_out = sum(amounts[t['id']] for t in rows
                            if t['type'] not in CREDIT_TYPES and t not in adjustable)

            target_savings = income * random.uniform(0.06, 0.16)
            desired_disc = income - fixed_out - target_savings
            # keep discretionary spend sane: between 5% and 90% of income, never negative
            desired_disc = max(income * 0.05, min(desired_disc, income * 0.90))

            current_total = sum(amounts[t['id']] for t in adjustable)
            if current_total <= 0:
                share = desired_disc / len(adjustable)
                for t in adjustable:
                    amounts[t['id']] = round(share, 2)
            else:
                factor = desired_disc / current_total
                for t in adjustable:
                    amounts[t['id']] = round(amounts[t['id']] * factor, 2)
            rescaled_rows += len(adjustable)

        # ── 2. Choose an opening balance ──
        # Pass A: run the ledger from zero to find the deepest dip, then size the
        # opening cushion so the running balance never falls below FLOOR. For a
        # distressed customer with net lifetime outflow this yields the realistic
        # narrative "had savings, drained them down to near-zero, then defaulted".
        FLOOR = 1000.0
        run0 = 0.0
        min0 = 0.0
        for t in txns:
            amt = amounts[t['id']]
            run0 += amt if t['type'] in CREDIT_TYPES else -amt
            min0 = min(min0, run0)
        base_cushion = max(50000.0, income_by_cid.get(cid, 0) * 1.0)
        opening = round(max(base_cushion, FLOOR - min0), 2)

        # Pass B: write the running balance
        running = opening
        min_running = running
        for t in txns:
            amt = amounts[t['id']]
            running += amt if t['type'] in CREDIT_TYPES else -amt
            running = round(running, 2)
            min_running = min(min_running, running)
            balance_updates.append((running, t['id']))
            if abs(amounts[t['id']] - float(t['amount'])) > 0.005:
                amount_updates.append((amounts[t['id']], t['id']))

        account_updates.append((running, aid))
        if min_running < 0:
            flagged_negative.append((aid, cid, round(min_running, 2), round(running, 2)))

    # ── 3. Persist ──
    cur.executemany("UPDATE transactions SET amount=? WHERE id=?", amount_updates)
    cur.executemany("UPDATE transactions SET balance_after=? WHERE id=?", balance_updates)
    cur.executemany("UPDATE accounts SET balance=? WHERE id=?", account_updates)
    conn.commit()

    print("  rescaled {} discretionary rows".format(rescaled_rows))
    print("  updated amount on {} rows".format(len(amount_updates)))
    print("  wrote balance_after on {} rows".format(len(balance_updates)))
    print("  updated {} account balances".format(len(account_updates)))

    null_left = cur.execute("SELECT COUNT(*) FROM transactions WHERE balance_after IS NULL").fetchone()[0]
    print("  balance_after still NULL: {}".format(null_left))

    if flagged_negative:
        print("\n  NOTE: {} account(s) dipped below zero at some point "
              "(distressed/NPA customers):".format(len(flagged_negative)))
        for aid, cid, mn, fin in flagged_negative[:10]:
            print("    {} ({}) min={} final={}".format(aid, cid, mn, fin))

    # quick sanity: show a few final balances
    print("\n  Sample reconciled balances:")
    for r in cur.execute(
        "SELECT a.id, c.first||' '||c.last AS name, a.balance "
        "FROM accounts a JOIN customers c ON c.id=a.cid "
        "ORDER BY a.id LIMIT 6"):
        print("    {:18} {:22} Rs {:,.2f}".format(r['id'], r['name'], r['balance']))

    conn.close()
    print("\nDone. Ledger reconciled — accounts.balance now equals the latest balance_after.")


if __name__ == '__main__':
    main()
