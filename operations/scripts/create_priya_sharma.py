import os
import sqlite3
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def generate_monthly_dates(start_year, start_month, end_year, end_month, day):
    dates = []
    current = date(start_year, start_month, day)
    end    = date(end_year,   end_month,   day)
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        if current.month == 12:
            current = date(current.year + 1, 1, day)
        else:
            current = date(current.year, current.month + 1, day)
    return dates

def recalculate_balances(cursor, account_id):
    cursor.execute("""
        SELECT id, type, amount FROM transactions
        WHERE aid = ? ORDER BY date, time, id
    """, (account_id,))
    txns    = cursor.fetchall()
    running = 0
    for txn in txns:
        if txn['type'] == 'Deposit':
            running += txn['amount']
        else:
            running -= txn['amount']
        cursor.execute(
            "UPDATE transactions SET balance_after = ? WHERE id = ?",
            (running, txn['id'])
        )
    cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (running, account_id))
    return running

# ─── DETERMINE NEXT IDs ────────────────────────────────────────────────────────

conn   = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT MAX(CAST(SUBSTR(id,5) AS INTEGER)) FROM customers WHERE id LIKE 'CUST%'")
max_cust = cursor.fetchone()[0] or 0
CUST_ID  = 'CUST{:03d}'.format(max_cust + 1)

cursor.execute("SELECT MAX(CAST(SUBSTR(id,4) AS INTEGER)) FROM accounts WHERE id LIKE 'ACC%'")
max_acc  = cursor.fetchone()[0] or 0
ACC_ID   = 'ACC{:03d}'.format(max_acc + 1)

conn.close()

print("=" * 80)
print("CREATING NEW CUSTOMER: Priya Sharma")
print("  Customer ID : {}".format(CUST_ID))
print("  Account ID  : {}".format(ACC_ID))
print("=" * 80)

# ─── LIFE STORY ────────────────────────────────────────────────────────────────
# Priya Sharma is a 35-year-old software engineer at a Bangalore tech firm.
# She opened her HDFC account in January 2024 with Rs 3,00,000 saved from
# her previous job. She earns Rs 95,000/month, pays utilities and groceries
# online every month, and invests in annual health insurance.
# In Nov 2024 she received freelance income from a UI/UX project.
# She received annual bonuses in Feb 2025 and Feb 2026.
# In April 2026 she took a Rs 5,00,000 personal loan for flat renovation —
# the full amount was transferred to the interior contractor the same day.
# She has paid EMIs consistently since May 2026.

BANK_ID    = 'BANK001'
BRANCH_ID  = 'BR-HDFC-003'
IFSC       = 'HDFC0000003'
LOAN_ID    = 'HDFC-LN-00001-PRIYA1'
MONTHLY_SALARY = 95000
MONTHLY_EMI    = 13167   # Personal loan Rs 5L @ 12% p.a. / 48 months
MONTHLY_UTIL   = 4500
MONTHLY_GROC   = 10000

# ─── 5C PRE-CHECK ─────────────────────────────────────────────────────────────
emi_foir   = round(MONTHLY_EMI / MONTHLY_SALARY * 100, 2)
total_foir = round((MONTHLY_EMI + MONTHLY_UTIL + MONTHLY_GROC) / MONTHLY_SALARY * 100, 2)
disposable = MONTHLY_SALARY - MONTHLY_EMI - MONTHLY_UTIL - MONTHLY_GROC

print("\n5C PRE-CHECK:")
print("  EMI-only FOIR    : {}%  (target < 40%)  {}".format(emi_foir,   "OK" if emi_foir < 40 else "FAIL"))
print("  Total FOIR       : {}%  (target < 50%)  {}".format(total_foir, "OK" if total_foir < 50 else "FAIL"))
print("  Monthly disposable: Rs {:,}  {}".format(disposable, "OK" if disposable > 0 else "FAIL"))

# ─── MASTER DATA ──────────────────────────────────────────────────────────────

customer = {
    'id': CUST_ID, 'bank_id': BANK_ID,
    'first': 'Priya', 'last': 'Sharma',
    'dob': '1990-03-22', 'gender': 'Female',
    'email': 'priya.sharma.blr@gmail.com', 'phone': '9845012345',
    'address': '12 Koramangala 4th Block', 'city': 'Bangalore',
    'state': 'Karnataka', 'pincode': '560034',
    'joined': '2024-01-10', 'status': 'Active'
}

account = {
    'id': ACC_ID, 'bank_id': BANK_ID, 'cid': CUST_ID,
    'type': 'Savings', 'open_date': '2024-01-10',
    'branch_id': BRANCH_ID, 'ifsc_code': IFSC, 'status': 'Active'
}

# Outstanding after 2 EMIs:
# Month 1: interest = 5,00,000 * 0.01 = 5000, principal = 13167-5000 = 8167, bal = 4,91,833
# Month 2: interest = 4,91,833 * 0.01 = 4918, principal = 13167-4918 = 8249, bal = 4,83,584
loan = {
    'id': LOAN_ID, 'bank_id': BANK_ID, 'cid': CUST_ID,
    'type': 'Personal Loan', 'principal': 500000, 'rate': 12.0,
    'tenure': 48, 'emi': MONTHLY_EMI,
    'disbursed': '2026-04-01', 'maturity': '2030-04-01',
    'outstanding': 483584, 'status': 'Active',
    'branch_id': BRANCH_ID, 'loan_classification': 'Standard'
}

risk = {
    'bank_id': BANK_ID, 'lid': LOAN_ID,
    'de': 0.30, 'intcov': 3.8, 'profit': 18.0, 'liq': 1.9,
    'df': 0, 'pd_score': 0.018, 'npa_flag': 0,
    'period': '2026-Q2', 'obs': '2026-06-15'
}

# ─── TRANSACTIONS ─────────────────────────────────────────────────────────────

transactions = []

# 1. Opening deposit
transactions.append({
    'id': 'PXNO01', 'bank_id': BANK_ID, 'aid': ACC_ID,
    'date': '2024-01-10', 'time': '09:00', 'type': 'Deposit', 'amount': 300000,
    'desc': '[SAVINGS] Opening Deposit - Transferred accumulated savings from previous bank on joining HDFC'
})

# 2. Monthly salary — 1st of each month, Jan 2024 to Jun 2026 (30 months)
for i, d in enumerate(generate_monthly_dates(2024, 1, 2026, 6, 1)):
    transactions.append({
        'id': 'PSAL{:03d}'.format(i + 1), 'bank_id': BANK_ID, 'aid': ACC_ID,
        'date': d, 'time': '09:00', 'type': 'Deposit', 'amount': MONTHLY_SALARY,
        'desc': '[INCOME] Salary - Monthly salary credit from employer. Software engineer at tech firm in Bangalore'
    })

# 3. Monthly utility bills — 10th of each month, Jan 2024 to Jun 2026 (30 months)
for i, d in enumerate(generate_monthly_dates(2024, 1, 2026, 6, 10)):
    transactions.append({
        'id': 'PUTL{:03d}'.format(i + 1), 'bank_id': BANK_ID, 'aid': ACC_ID,
        'date': d, 'time': '10:00', 'type': 'Bill Payment', 'amount': MONTHLY_UTIL,
        'desc': '[UTILITIES] Bill Payment - Monthly electricity, internet and water bill paid via net banking'
    })

# 4. Monthly grocery — 20th of each month, Jan 2024 to Jun 2026 (30 months)
for i, d in enumerate(generate_monthly_dates(2024, 1, 2026, 6, 20)):
    transactions.append({
        'id': 'PGRC{:03d}'.format(i + 1), 'bank_id': BANK_ID, 'aid': ACC_ID,
        'date': d, 'time': '20:00', 'type': 'UPI Payment', 'amount': MONTHLY_GROC,
        'desc': '[LIFESTYLE] Online Grocery - Monthly grocery and household essentials via BigBasket and Blinkit'
    })

# 5. One-off life events
one_off = [
    ('PXNO02', '2024-03-15', '11:00', 'Bill Payment', 18000,
     '[INSURANCE] Premium Payment - Annual health insurance premium paid for FY2024-25 policy renewal'),

    ('PXNO03', '2024-05-12', '15:30', 'UPI Payment', 8500,
     '[LIFESTYLE] Online Purchase - Summer clothing and accessories ordered from Myntra and Amazon'),

    ('PXNO04', '2024-07-22', '18:00', 'UPI Payment', 28000,
     '[LIFESTYLE] Travel - Flight and hotel booking for Goa vacation via MakeMyTrip'),

    ('PXNO05', '2024-11-08', '14:00', 'Deposit', 45000,
     '[INCOME] Freelance Work - UI/UX design project payment received from startup client via NEFT'),

    ('PXNO06', '2024-12-20', '19:00', 'UPI Payment', 14000,
     '[LIFESTYLE] Online Purchase - Festive season electronics and gifts purchased online'),

    ('PXNO07', '2025-02-05', '09:00', 'Deposit', 150000,
     '[INCOME] Bonus - Annual performance bonus for FY2024-25. Excellent rating from employer'),

    ('PXNO08', '2025-03-15', '11:00', 'Bill Payment', 18000,
     '[INSURANCE] Premium Payment - Annual health insurance premium paid for FY2025-26 policy renewal'),

    ('PXNO09', '2025-06-14', '20:30', 'UPI Payment', 6500,
     '[LIFESTYLE] Dining & Entertainment - Team outing dinner and movie at PVR Cinemas Bangalore'),

    ('PXNO10', '2025-10-10', '18:00', 'UPI Payment', 11000,
     '[LIFESTYLE] Online Purchase - Diwali shopping for home decor and ethnic wear online'),

    ('PXNO11', '2026-02-05', '09:00', 'Deposit', 150000,
     '[INCOME] Bonus - Annual performance bonus for FY2025-26. Promoted to Senior Engineer this year'),

    ('PXNO12', '2026-03-15', '11:00', 'Bill Payment', 18000,
     '[INSURANCE] Premium Payment - Annual health insurance premium paid for FY2026-27 policy renewal'),

    # Loan disbursement → immediate transfer to contractor (same day, 2 hours apart)
    ('PXNO13', '2026-04-01', '10:00', 'Deposit', 500000,
     '[HOUSING] Loan Disbursement - Personal loan of Rs 5,00,000 credited for home renovation project'),

    ('PXNO14', '2026-04-01', '12:00', 'Online Transfer', 500000,
     '[HOUSING] Home Renovation - Full payment transferred to interior designer for Koramangala flat renovation'),

    # Monthly EMIs — 25th of each month starting May 2026
    ('PXNO15', '2026-05-25', '10:00', 'EMI Payment', MONTHLY_EMI,
     '[HOUSING] EMI Payment - First personal loan installment. Started repayment for flat renovation loan'),

    ('PXNO16', '2026-06-25', '10:00', 'EMI Payment', MONTHLY_EMI,
     '[HOUSING] EMI Payment - June installment. Consistent repayment on schedule'),
]

for row in one_off:
    txn_id, d, t, typ, amt, desc = row
    transactions.append({
        'id': txn_id, 'bank_id': BANK_ID, 'aid': ACC_ID,
        'date': d, 'time': t, 'type': typ, 'amount': amt, 'desc': desc
    })

# ─── VALIDATION BEFORE INSERT ─────────────────────────────────────────────────

print("\nVALIDATION:")

# Sort chronologically
transactions.sort(key=lambda x: (x['date'], x['time'], x['id']))

# 1. Balance simulation (no negatives, no mismatches)
running = 0
min_balance = float('inf')
for txn in transactions:
    if txn['type'] == 'Deposit':
        running += txn['amount']
    else:
        running -= txn['amount']
    min_balance = min(min_balance, running)

print("  Min balance during history : Rs {:,}  {}".format(int(min_balance), "OK" if min_balance >= 0 else "FAIL - NEGATIVE BALANCE"))
print("  Final projected balance    : Rs {:,}".format(int(running)))

# 2. Salary count check
salary_txns = [t for t in transactions if 'PSAL' in t['id']]
print("  Salary months              : {}  (expected 30)  {}".format(len(salary_txns), "OK" if len(salary_txns) == 30 else "FAIL"))

# 3. Loan date consistency
loan_disbursement = [t for t in transactions if t['id'] == 'PXNO13'][0]
print("  Loan date matches table    : {}  {}".format(loan_disbursement['date'], "OK" if loan_disbursement['date'] == loan['disbursed'] else "FAIL"))

# 4. Freelance not on loan day
freelance = [t for t in transactions if 'Freelance' in t['desc']][0]
print("  Freelance vs loan date     : {} vs {}  {}".format(freelance['date'], loan['disbursed'], "OK" if freelance['date'] != loan['disbursed'] else "FAIL"))

# 5. Total transactions
print("  Total transactions         : {}".format(len(transactions)))

# ─── INSERT INTO DATABASE ─────────────────────────────────────────────────────

print("\nINSERTING INTO DATABASE...")

conn   = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Customer
cursor.execute("""
    INSERT INTO customers (id, bank_id, first, last, dob, gender, email, phone,
                           address, city, state, pincode, joined, status)
    VALUES (:id, :bank_id, :first, :last, :dob, :gender, :email, :phone,
            :address, :city, :state, :pincode, :joined, :status)
""", customer)
print("  [1/5] Customer inserted: {} - {} {}".format(CUST_ID, customer['first'], customer['last']))

# Account
cursor.execute("""
    INSERT INTO accounts (id, bank_id, cid, type, balance, open_date, branch_id, ifsc_code, status)
    VALUES (:id, :bank_id, :cid, :type, 0, :open_date, :branch_id, :ifsc_code, :status)
""", account)
print("  [2/5] Account inserted: {} (Savings)".format(ACC_ID))

# Loan
cursor.execute("""
    INSERT INTO loans (id, bank_id, cid, type, principal, rate, tenure, emi,
                       disbursed, maturity, outstanding, status, branch_id, loan_classification)
    VALUES (:id, :bank_id, :cid, :type, :principal, :rate, :tenure, :emi,
            :disbursed, :maturity, :outstanding, :status, :branch_id, :loan_classification)
""", loan)
print("  [3/5] Loan inserted: {} (Personal Loan Rs 5,00,000 @ 12%)".format(LOAN_ID))

# Risk metrics
cursor.execute("""
    INSERT INTO credit_risk_metrics (bank_id, lid, de, intcov, profit, liq, df, pd_score, npa_flag, period, obs)
    VALUES (:bank_id, :lid, :de, :intcov, :profit, :liq, :df, :pd_score, :npa_flag, :period, :obs)
""", risk)
print("  [4/5] Risk metrics inserted: PD Score {}, NPA Flag {}".format(risk['pd_score'], risk['npa_flag']))

# Transactions
for txn in transactions:
    txn['balance_after'] = 0
    cursor.execute("""
        INSERT OR IGNORE INTO transactions (id, bank_id, aid, date, time, type, amount, balance_after, desc)
        VALUES (:id, :bank_id, :aid, :date, :time, :type, :amount, :balance_after, :desc)
    """, txn)
print("  [5/5] {} transactions inserted".format(len(transactions)))

# Recalculate all balances
final_balance = recalculate_balances(cursor, ACC_ID)
conn.commit()
conn.close()

# ─── FINAL SUMMARY ────────────────────────────────────────────────────────────

print("\n" + "=" * 80)
print("CUSTOMER CREATED SUCCESSFULLY!")
print("=" * 80)
print("\nPROFILE SUMMARY:")
print("  Name            : Priya Sharma")
print("  Customer ID     : {}".format(CUST_ID))
print("  Account ID      : {}".format(ACC_ID))
print("  Bank            : HDFC Bank Limited (BANK001)")
print("  Branch          : Bangalore IT Park ({}/ {})".format(BRANCH_ID, IFSC))
print("  City            : Bangalore, Karnataka")
print("  Joined          : 2024-01-10")
print("  Occupation      : Software Engineer (Salaried)")
print("  Monthly Salary  : Rs {:,}".format(MONTHLY_SALARY))
print("\nLOAN SUMMARY:")
print("  Loan ID         : {}".format(LOAN_ID))
print("  Type            : Personal Loan (Home Renovation)")
print("  Principal       : Rs 5,00,000")
print("  Rate            : 12% p.a.")
print("  Tenure          : 48 months")
print("  EMI             : Rs {:,}".format(MONTHLY_EMI))
print("  Disbursed       : 2026-04-01")
print("  Outstanding     : Rs 4,83,584 (after 2 EMIs)")
print("  Classification  : Standard (Non-NPA)")
print("\nACCOUNT SUMMARY:")
print("  Total transactions : {}".format(len(transactions)))
print("  Final balance      : Rs {:,.2f}".format(final_balance))
print("\n5C FINAL VERDICT:")
print("  Character   : All EMIs on time (2/2 = 100%)")
print("  Capacity    : FOIR = {}% (EMI) / {}% (total) - Comfortable".format(emi_foir, total_foir))
print("  Capital     : Rs {:,} in account, Rs 3L pre-existing savings".format(int(final_balance)))
print("  Collateral  : Unsecured personal loan (no physical collateral)")
print("  Conditions  : Renovation loan, legitimate purpose, 12% rate, PD = 1.8%")
print("=" * 80)
