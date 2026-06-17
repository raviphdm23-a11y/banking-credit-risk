"""
seed_global_transactions.py
───────────────────────────
The foreign group banks' customers (seed_global_customers.py) start with a single
opening-deposit transaction each, so every foreign account looks like "one credit
and nothing else" in the operations UI. This adds a realistic **monthly
transaction history** for them — the same shape the India accounts have:

    • monthly income credit (salary / pension / business / freelance)
    • EMI loan-repayment debit
    • a utilities Bill Payment debit
    • a discretionary UPI Payment debit

NPA-classified customers get irregular / reduced income and missed EMI months,
consistent with financial distress.

Key property — **deposit-neutral**: each account is made to END exactly at its
current `accounts.balance` (the grounded deposit figure the balance sheet is
live-anchored to). We do this by computing the opening balance as
`B - net(monthly flows)` and writing `balance_after` on every row ourselves. So
this script does NOT change `accounts.balance` and the balance sheet / regulatory
figures stay valid — no re-seed needed.

Idempotent: skips a bank whose accounts already carry an EMI-Payment history.

Run:  python operations/scripts/seed_global_transactions.py
"""

import os
import sqlite3
import random
from datetime import date, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

HISTORY_MONTHS = 18          # length of the generated history window
FLOOR = 5000.0               # minimum opening balance

# income-line wording by (loose) employment category
def _income_desc(emp_type):
    e = (emp_type or '').lower()
    if 'retired' in e:
        return ('Pension', '[INCOME] Pension - Monthly pension credit')
    if 'business' in e:
        return ('Business Income', '[INCOME] Business Income - Monthly business revenue deposit')
    if 'self-employed' in e or 'self employed' in e:
        return ('Business Income', '[INCOME] Professional Income - Monthly professional fees credit')
    if 'freelance' in e:
        return ('Freelance Income', '[INCOME] Freelance Income - Monthly freelance project payment')
    if 'student' in e:
        return ('Family Support', '[INCOME] Family Support - Monthly allowance received from family')
    return ('Salary', '[INCOME] Salary - Monthly salary credit')


def _months(start, end):
    y, m = start.year, start.month
    out = []
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _foreign_banks(cur):
    return [r[0] for r in cur.execute(
        "SELECT bank_id FROM banks WHERE country_code IS NOT NULL AND country_code <> 'IND' "
        "ORDER BY bank_id").fetchall()]


def _has_history(cur, bank_id):
    return cur.execute(
        "SELECT COUNT(*) FROM transactions t JOIN accounts a ON a.id=t.aid "
        "WHERE a.bank_id=? AND t.type='EMI Payment'", (bank_id,)).fetchone()[0] > 0


def _build_account_history(B, monthly_income, emi, is_npa, emp_type, window_start, window_end):
    """Return an ordered list of txn dicts (without ids) that ends exactly at B."""
    _, inc_desc = _income_desc(emp_type)
    flows = []   # (date, time, type, amount, is_credit, desc)

    for (y, m) in _months(window_start, window_end):
        # income
        if not (is_npa and random.random() < 0.30):
            var = random.uniform(0.55, 0.90) if is_npa else random.uniform(0.90, 1.05)
            inc = round(monthly_income * var, 2)
            flows.append((date(y, m, 1), '09:00:00', 'Deposit', inc, True, inc_desc))
            income_landed = True
        else:
            income_landed = False

        # EMI (missed sometimes for NPA)
        if emi > 0 and not (is_npa and random.random() < 0.40):
            flows.append((date(y, m, 5), '08:30:00', 'EMI Payment', round(emi, 2), False,
                          '[LOAN] EMI Payment - Monthly loan instalment'))

        # utilities
        bill = round(monthly_income * random.uniform(0.06, 0.10), 2)
        flows.append((date(y, m, 12), '11:00:00', 'Bill Payment', bill, False,
                      '[UTILITIES] Bill Payment - Electricity, internet and water'))

        # discretionary spend
        if income_landed:
            savings = monthly_income * random.uniform(0.05, 0.10)
            upi = max(monthly_income * 0.03, monthly_income - emi - bill - savings)
        else:
            upi = monthly_income * random.uniform(0.02, 0.06)
        flows.append((date(y, m, 20), '19:30:00', 'UPI Payment', round(upi, 2), False,
                      '[LIFESTYLE] UPI Payment - Groceries and daily household expenses'))

    net = sum(f[3] if f[4] else -f[3] for f in flows)
    opening = round(B - net, 2)
    rows = []
    if opening < FLOOR:
        # rare: lifetime surplus exceeds the closing balance — open at FLOOR and
        # add one closing adjustment debit so the account still ends exactly at B.
        adj = round(net - B + FLOOR, 2)
        opening = FLOOR
        flows.append((window_end, '23:59:00', 'Debit', adj, False,
                      '[ADJUSTMENT] Net discretionary spend reconciliation'))

    rows.append((window_start, '08:00:00', 'Deposit', opening, True,
                 '[INCOME] Opening balance - account funded'))
    rows.extend(flows)
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def seed(db_path=DB_PATH, verbose=True):
    random.seed(2028)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    today = date.today()

    banks = _foreign_banks(cur)
    total = 0
    touched_banks = 0
    for bank_id in banks:
        if _has_history(cur, bank_id):
            if verbose:
                print(f"{bank_id}: already has transaction history — skipped")
            continue
        touched_banks += 1
        custs = cur.execute(
            "SELECT c.id AS cid, a.id AS aid, a.balance AS balance, k.annual_income, "
            "k.employment_type, l.emi, l.loan_classification, l.disbursed "
            "FROM customers c JOIN accounts a ON a.cid=c.id "
            "JOIN customer_kyc k ON k.cid=c.id JOIN loans l ON l.cid=c.id "
            "WHERE c.bank_id=?", (bank_id,)).fetchall()

        bank_rows = 0
        for cu in custs:
            aid = cu['aid']
            B = float(cu['balance'] or 0)
            monthly_income = round(float(cu['annual_income'] or 0) / 12.0, 2)
            if monthly_income <= 0:
                continue
            emi = float(cu['emi'] or 0)
            is_npa = (cu['loan_classification'] or 'Standard') in ('NPA', 'Doubtful', 'Loss')

            start = datetime.strptime(cu['disbursed'], '%Y-%m-%d').date()
            earliest = date(today.year - HISTORY_MONTHS // 12, today.month, 1)
            if start < earliest:
                start = earliest
            window_start, window_end = start, today

            # replace the single opening-deposit row with a full history
            cur.execute("DELETE FROM transactions WHERE aid=?", (aid,))
            hist = _build_account_history(B, monthly_income, emi, is_npa,
                                          cu['employment_type'], window_start, window_end)

            running = 0.0
            to_insert = []
            for seq, (d, t, typ, amt, is_credit, desc) in enumerate(hist, start=1):
                running += amt if is_credit else -amt
                running = round(running, 2)
                tid = f"TX-{aid}-{seq:03d}"
                to_insert.append((tid, bank_id, aid, d.isoformat(), t, typ, amt, running, desc))
            cur.executemany(
                "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
                "VALUES (?,?,?,?,?,?,?,?,?)", to_insert)
            # keep accounts.balance exactly at B (deposit-neutral); guard float drift
            cur.execute("UPDATE accounts SET balance=? WHERE id=?", (round(B, 2), aid))
            bank_rows += len(to_insert)
        total += bank_rows
        if verbose:
            print(f"{bank_id}: +{bank_rows} transactions across {len(custs)} accounts")

    conn.commit()
    if verbose and not touched_banks:
        print("All foreign banks already have history — nothing to do.")
    elif verbose:
        print(f"Done. Inserted {total} transactions; deposits unchanged (deposit-neutral).")
    conn.close()
    return total


if __name__ == '__main__':
    seed()
