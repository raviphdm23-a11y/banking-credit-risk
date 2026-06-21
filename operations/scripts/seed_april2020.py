"""Generate April 2020 transactions for all Axis Bank customers
based on their historical transaction patterns."""

import sqlite3, random, math
from datetime import date

random.seed(42)

BANK_ID = 'BANK010'

conn = sqlite3.connect('bank.db')
conn.row_factory = sqlite3.Row

# NPA customer IDs — skip EMI for them
npa_cids = {r['cid'] for r in conn.execute(
    "SELECT DISTINCT cid FROM loans WHERE bank_id=? AND loan_classification != 'Standard'",
    (BANK_ID,)
).fetchall()}

# All accounts with transaction history (skip Fixed Deposit — no monthly activity)
accounts = conn.execute("""
    SELECT a.id, a.cid, a.type FROM accounts a
    WHERE a.bank_id=? AND a.type != 'Fixed Deposit'
    AND EXISTS (SELECT 1 FROM transactions t WHERE t.aid=a.id)
""", (BANK_ID,)).fetchall()

print(f"Accounts to process: {len(accounts)}")

def rand_amt(avg, std, floor=10.0):
    if std < avg * 0.05:
        std = avg * 0.10
    return max(floor, round(random.gauss(avg, std * 0.5), 2))

def pick_date(day_from, day_to):
    return date(2020, 4, random.randint(day_from, min(day_to, 30))).isoformat()

def hist_stats(conn, aid, txn_type):
    rows = conn.execute(
        "SELECT amount FROM transactions WHERE aid=? AND type=?", (aid, txn_type)
    ).fetchall()
    if not rows:
        return None
    amounts = [r['amount'] for r in rows]
    avg = sum(amounts) / len(amounts)
    std = math.sqrt(sum((x - avg)**2 for x in amounts) / len(amounts)) if len(amounts) > 1 else avg * 0.1
    return {'avg': avg, 'std': std}

inserted_total = 0

for acct in accounts:
    aid   = acct['id']
    cid   = acct['cid']
    atype = acct['type']

    # Get last running balance
    last_row = conn.execute(
        "SELECT balance_after FROM transactions WHERE aid=? ORDER BY date DESC, rowid DESC LIMIT 1",
        (aid,)
    ).fetchone()
    balance = float(last_row['balance_after']) if last_row else 0.0

    # Next sequence number
    last_tx = conn.execute(
        "SELECT id FROM transactions WHERE aid=? ORDER BY rowid DESC LIMIT 1", (aid,)
    ).fetchone()
    try:
        seq = int(last_tx['id'].split('-')[-1]) if last_tx else 0
    except Exception:
        seq = 0

    new_txns = []  # (date_str, type, amount, desc)

    # 1. Deposit — income, days 1–5
    h = hist_stats(conn, aid, 'Deposit')
    if h:
        amt = rand_amt(h['avg'], h['std'], floor=500.0)
        if 'CORP' in cid or 'SME' in cid:
            desc = '[INCOME] Business Income - Monthly business revenue deposit'
        else:
            desc = '[INCOME] Salary - Monthly salary credit'
        new_txns.append((pick_date(1, 5), 'Deposit', amt, desc))

    # 2. EMI Payment — fixed from loan, days 5–15 (skip NPA customers)
    if cid not in npa_cids:
        loan = conn.execute("""
            SELECT emi FROM loans
            WHERE cid=? AND bank_id=? AND emi > 0 AND loan_classification='Standard'
            LIMIT 1
        """, (cid, BANK_ID)).fetchone()
        if loan and float(loan['emi']) > 0:
            new_txns.append((pick_date(5, 15), 'EMI Payment',
                             round(float(loan['emi']), 2),
                             '[LOAN] EMI Payment - Monthly loan instalment'))

    # 3. Bill Payment — utilities, days 14–22
    h = hist_stats(conn, aid, 'Bill Payment')
    if h:
        amt = rand_amt(h['avg'], h['std'], floor=200.0)
        new_txns.append((pick_date(14, 22), 'Bill Payment', amt,
                         '[UTILITIES] Bill Payment - Electricity, internet and water'))

    # 4. UPI Payment — lifestyle, days 8–28
    h = hist_stats(conn, aid, 'UPI Payment')
    if h:
        amt = rand_amt(h['avg'], h['std'], floor=100.0)
        new_txns.append((pick_date(8, 28), 'UPI Payment', amt,
                         '[LIFESTYLE] UPI Payment - Groceries and daily expenses'))

    # Sort by date ascending
    new_txns.sort(key=lambda x: x[0])

    for txn_date, txn_type, txn_amount, txn_desc in new_txns:
        seq += 1
        tx_id = f"TX-{aid}-APR20-{seq:04d}"
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
        inserted_total += 1

    # Update account balance
    conn.execute("UPDATE accounts SET balance=? WHERE id=?", (balance, aid))

conn.commit()
print(f"Inserted: {inserted_total:,} transactions")

# Summary
new_count = conn.execute(
    "SELECT COUNT(*) FROM transactions WHERE bank_id=? AND date LIKE '2020-04-%'", (BANK_ID,)
).fetchone()[0]
max_date = conn.execute("SELECT MAX(date) FROM transactions WHERE bank_id=?", (BANK_ID,)).fetchone()[0]
print(f"April 2020 transactions in DB: {new_count:,}")
print(f"Latest transaction date now:   {max_date}")

# Sample check
sample = conn.execute("""
    SELECT id, date, type, amount, balance_after FROM transactions
    WHERE bank_id=? AND date LIKE '2020-04-%' LIMIT 8
""", (BANK_ID,)).fetchall()
print("\nSample April 2020 transactions:")
for r in sample:
    print(f"  {r['date']} | {r['type']:15s} | ₹{r['amount']:>12,.2f} | bal=₹{r['balance_after']:>12,.2f}")

conn.close()
