"""
Hourly automation: add 1-2 new customers and 2-3 transactions directly into bank.db (SQLite).
Replaces the Excel COM automation in update_bank_data.ps1.

Called by update_bank_data.ps1 (Task Scheduler + CronCreate wrapper).
Can also be run standalone: python update_bank_data.py
"""
import os, sys, sqlite3, random, string, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, '..', '..', 'bank.db')
LOG_PATH = os.path.join(BASE_DIR, 'update_log.txt')

# ── DATA POOLS ────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    'Amit','Priya','Rahul','Neha','Vijay','Sunita','Arun','Kavita',
    'Suresh','Anita','Rajesh','Pooja','Sanjay','Meena','Dinesh',
    'Rekha','Mahesh','Shilpa','Ramesh','Geeta','Ashok','Usha',
    'Deepak','Lata','Vinod','Asha','Prakash','Sudha','Ravi','Mala',
]

LAST_NAMES = [
    'Sharma','Patel','Singh','Kumar','Verma','Gupta','Mehta','Joshi',
    'Shah','Reddy','Nair','Iyer','Pillai','Bose','Das','Mukherjee',
    'Chatterjee','Rao','Mishra','Tiwari','Pandey','Dubey','Shukla',
    'Srivastava','Agarwal','Bansal','Goel','Saxena','Malhotra','Kapoor',
]

CITY_STATE = [
    ('Mumbai',    'Maharashtra'), ('Delhi',     'Delhi'),
    ('Bangalore', 'Karnataka'),   ('Chennai',   'Tamil Nadu'),
    ('Hyderabad', 'Telangana'),   ('Pune',      'Maharashtra'),
    ('Ahmedabad', 'Gujarat'),     ('Kolkata',   'West Bengal'),
    ('Jaipur',    'Rajasthan'),   ('Lucknow',   'Uttar Pradesh'),
    ('Bhopal',    'Madhya Pradesh'), ('Indore', 'Madhya Pradesh'),
    ('Nagpur',    'Maharashtra'), ('Surat',     'Gujarat'),
    ('Kochi',     'Kerala'),
]

DOMAINS  = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'rediffmail.com']
BRANCHES = ['BR001', 'BR002', 'BR003', 'BR004', 'BR005']
EMP_IDS  = ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005', 'EMP006']

TXN_TYPE_POOL = ['Deposit', 'Deposit', 'Withdrawal', 'EMI Payment', 'Transfer']

DEPOSIT_DESCS = [
    'Salary credit from employer',
    'Cash deposit at branch counter',
    'NEFT transfer received',
    'UPI payment received from family',
    'Dividend income credit from mutual fund',
    'Rental income deposit',
    'Insurance maturity proceeds credited',
    'Freelance payment received via IMPS',
    'Bonus credited by employer',
    'Interest income from fixed deposit',
    'Sale proceeds deposited by customer',
    'Refund credited by merchant',
]
WITHDRAW_DESCS = [
    'ATM cash withdrawal',
    'Online shopping payment',
    'Utility bill payment via net banking',
    'Grocery purchase at supermarket',
    'Restaurant and dining expenses',
    'Medical expenses at hospital',
    'Fuel purchase at petrol pump',
    'Cab and transportation payment',
    'Mobile recharge and DTH payment',
    'Gym membership fees paid',
    'Educational fees payment',
    'Clothing and lifestyle purchase',
]
EMI_DESCS = [
    'Home Loan EMI auto-debit',
    'Car Loan EMI auto-debit',
    'Personal Loan EMI auto-debit',
    'Education Loan EMI auto-debit',
    'Two-wheeler Loan EMI auto-debit',
]
TRANSFER_DESCS = [
    'NEFT transfer to savings account',
    'RTGS transfer to business account',
    'IMPS transfer to family member',
    'UPI transfer via mobile banking',
    'Internal fund transfer between own accounts',
    'Transfer to recurring deposit account',
    'SIP debit for mutual fund investment',
]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _desc(txn_type):
    if txn_type == 'Deposit':    return random.choice(DEPOSIT_DESCS)
    if txn_type == 'Withdrawal': return random.choice(WITHDRAW_DESCS)
    if txn_type == 'EMI Payment':return random.choice(EMI_DESCS)
    return random.choice(TRANSFER_DESCS)


def _amount(txn_type):
    if txn_type == 'Deposit':    return random.randint(10_000, 200_000)
    if txn_type == 'Withdrawal': return random.randint(500,    50_000)
    if txn_type == 'EMI Payment':return random.randint(5_000,  35_000)
    return random.randint(1_000, 100_000)


def _banking_time():
    hour = random.choice([9, 10, 10, 11, 11, 12, 13, 14, 14, 15, 15, 16, 16, 17])
    return f'{hour:02d}:{random.randint(0, 59):02d}'


def _dob():
    return f'{random.randint(1960,1998)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}'


def _log(msg):
    ts   = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _parse_num(id_str, prefix):
    return int(id_str.replace(prefix, '')) if id_str else 0


def _generate_loan_transactions(cur, last_txn):
    """Generate loan disbursement and EMI payment transactions for active loans"""
    run_log = []

    # Get all loans that don't have disbursement transactions
    cur.execute("""
        SELECT l.id, l.principal, l.type, l.cid, l.bank_id, c.first, c.last,
               a.id as aid, a.balance
        FROM loans l
        JOIN customers c ON l.cid = c.id
        JOIN accounts a ON a.cid = l.cid
        WHERE l.status = 'Active'
        AND a.type IN ('Current', 'Savings')
        AND NOT EXISTS (
            SELECT 1 FROM transactions t
            WHERE t.desc LIKE '%' || l.id || '%' AND t.type = 'Deposit'
        )
        GROUP BY l.id
        LIMIT 2
    """)

    for loan in cur.fetchall():
        loan_id = loan['id']
        principal = loan['principal']
        loan_type = loan['type']
        cid = loan['cid']
        bank_id = loan['bank_id']
        aid = loan['aid']
        first = loan['first']
        last = loan['last']

        # Add loan disbursement transaction
        last_txn += 1
        txn_id = f'TXN{last_txn:03d}'
        today = datetime.date.today().isoformat()

        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (txn_id, bank_id, aid, today, '10:00', 'Deposit', principal,
             loan['balance'] + principal, f'Loan disbursement - {loan_type} ({loan_id})')
        )

        run_log.append(f'  [LOAN] {txn_id}: Disbursement {first} {last} Rs.{principal:,} ({loan_id})')

    return run_log, last_txn


# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    if not os.path.exists(DB_PATH):
        _log(f'ERROR: {DB_PATH} not found. Run migrate_from_excel.py first.')
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    today  = datetime.date.today().isoformat()
    run_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Last IDs
    cur.execute("SELECT id FROM customers ORDER BY id DESC LIMIT 1")
    row = cur.fetchone(); last_cust = _parse_num(row['id'] if row else '', 'CUST')

    cur.execute("SELECT id FROM accounts ORDER BY id DESC LIMIT 1")
    row = cur.fetchone(); last_acc  = _parse_num(row['id'] if row else '', 'ACC')

    cur.execute("SELECT id FROM transactions ORDER BY id DESC LIMIT 1")
    row = cur.fetchone(); last_txn  = _parse_num(row['id'] if row else '', 'TXN')

    cur.execute("SELECT id FROM accounts")
    all_acc_ids = [r['id'] for r in cur.fetchall()]

    new_custs = 0
    new_txns  = 0
    run_log   = []

    # ── LOAN TRANSACTION AUTOMATION ───────────────────────────────────────────
    loan_logs, last_txn = _generate_loan_transactions(cur, last_txn)
    run_log.extend(loan_logs)
    new_txns += len(loan_logs)

    # ── 1-2 NEW CUSTOMERS ─────────────────────────────────────────────────────
    for _ in range(random.randint(1, 2)):
        last_cust += 1
        last_acc  += 1
        last_txn  += 1

        cid    = f'CUST{last_cust:03d}'
        aid    = f'ACC{last_acc:03d}'
        tid    = f'TXN{last_txn:03d}'
        first  = random.choice(FIRST_NAMES)
        last_n = random.choice(LAST_NAMES)
        city, state = random.choice(CITY_STATE)
        email  = f'{first.lower()}.{last_n.lower()}{last_cust}@{random.choice(DOMAINS)}'
        phone  = f'9{random.randint(100_000_000, 999_999_999)}'
        gender = random.choice(['Male', 'Female'])
        branch = random.choice(BRANCHES)
        bal    = random.randint(10_000, 200_000)
        addr   = f'{random.randint(1,999)} {last_n} Nagar'
        pin    = str(random.randint(100_000, 999_999))

        cur.execute(
            "INSERT INTO customers "
            "(id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, 'BANK001', first, last_n, _dob(), gender, email, phone, addr, city, state, pin, today, 'Active')
        )
        cur.execute(
            "INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (aid, 'BANK001', cid, 'Savings', bal, today, 'BR-HDFC-001', 'HDFC0000001', 'Active')
        )
        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (tid, 'BANK001', aid, today, '09:00', 'Deposit', bal, bal, 'Account opening initial deposit')
        )

        all_acc_ids.append(aid)
        new_custs += 1
        new_txns  += 1
        run_log.append(f'  New customer: {cid} - {first} {last_n} ({city}) -> {aid} Rs.{bal:,}')
        run_log.append(f'  {tid}: Opening deposit Rs.{bal:,} {aid} 09:00')

    # ── 2-3 ADDITIONAL TRANSACTIONS ───────────────────────────────────────────
    for _ in range(random.randint(2, 3)):
        last_txn += 1
        tid       = f'TXN{last_txn:03d}'
        acc_id    = random.choice(all_acc_ids)
        txn_type  = random.choice(TXN_TYPE_POOL)
        amount    = _amount(txn_type)
        desc      = _desc(txn_type)
        t_time    = _banking_time()

        cur.execute("SELECT balance FROM accounts WHERE id=?", (acc_id,))
        row = cur.fetchone()
        bal_before = row['balance'] if row else 0
        bal_after  = (
            bal_before + amount if txn_type == 'Deposit'
            else max(0, bal_before - amount)
        )

        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (tid, 'BANK001', acc_id, today, t_time, txn_type, amount, bal_after, desc)
        )
        cur.execute("UPDATE accounts SET balance=? WHERE id=?", (bal_after, acc_id))

        new_txns += 1
        run_log.append(f'  {tid}: {txn_type} Rs.{amount:,} {acc_id} {t_time} | {desc}')

    conn.commit()
    conn.close()

    # Final counts
    conn2 = sqlite3.connect(DB_PATH)
    cur2  = conn2.cursor()
    cur2.execute("SELECT COUNT(*) FROM customers");   total_c = cur2.fetchone()[0]
    cur2.execute("SELECT COUNT(*) FROM transactions"); total_t = cur2.fetchone()[0]
    conn2.close()

    _log(f'=== Hourly run {run_ts} ===')
    for line in run_log:
        _log(line)
    _log(f'  Added: {new_custs} customers, {new_txns} transactions')
    _log(f'  Totals: {total_c} customers, {total_t} transactions')


if __name__ == '__main__':
    run()
