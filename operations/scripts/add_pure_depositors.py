"""
add_pure_depositors.py
───────────────────────
Adds new pure-depositor customers (no loan) to each bank to bring the
Credit-to-Deposit ratio down toward a realistic target. Root cause: the
existing ledger is 80.7% loan-bearing customers vs only 19.3% pure
depositors - the inverse of a real bank's mix, where non-borrowing
depositors vastly outnumber borrowers and supply most of the funding
base. rebalance_cd_ratio.py already topped up existing borrowers' own
accounts (CD ratio ~196% -> ~88-99%), but that approach structurally
can't go further since it tops up a borrower's own account only to a
few months' income, not loan-principal scale. This script instead grows
the separate non-borrowing depositor population, same as a real bank
would via retail deposit acquisition.

Each new customer follows the exact conventions already used for the
existing "{SHORT}-DEP-{seq:04d}" pure-depositor customers in this DB:
customers + customer_kyc + one Savings account, sized off that bank's
own existing DEP-customer average balance (+/-25% jitter), funded via a
single "[INCOME] Opening balance" transaction (same minimal pattern
rebalance_cd_ratio.py itself already uses for its deposit top-ups).

Run:
    python operations/scripts/add_pure_depositors.py [--target 0.80] [--dry-run]

Then re-derive the balance sheet / regulatory numbers from the updated
ledger:
    python operations/scripts/seed_bank_balance_sheet.py
    python operations/scripts/seed_bank_profit_loss.py
    python operations/scripts/run_regulatory_batch.py
"""

import argparse
import math
import os
import random
import re
import sqlite3
from datetime import date, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

FIRST_NAMES = ['Aarav', 'Vivaan', 'Aditya', 'Ishaan', 'Kabir', 'Ananya', 'Diya',
               'Saanvi', 'Meera', 'Rohan', 'Karan', 'Nisha', 'Priya', 'Arjun',
               'Sanya', 'Rahul', 'Neha', 'Vikram', 'Pooja', 'Amit']
LAST_NAMES = ['Sharma', 'Verma', 'Gupta', 'Iyer', 'Nair', 'Reddy', 'Rao', 'Patel',
              'Mehta', 'Joshi', 'Das', 'Kapoor', 'Malhotra', 'Chatterjee', 'Ghosh']
CITIES = [('Mumbai', 'MH'), ('Bengaluru', 'KA'), ('Delhi', 'DL'), ('Chennai', 'TN'),
          ('Pune', 'MH'), ('Hyderabad', 'TG'), ('Kolkata', 'WB'), ('Ahmedabad', 'GJ')]
EMPLOYMENT_TYPES = ['SALARIED', 'SELF_EMPLOYED', 'GOVT', 'BUSINESS']
EDUCATION = ['GRADUATE', 'POST_GRADUATE', 'DIPLOMA']


def _bank_prefix(cur, bank_id):
    row = cur.execute(
        "SELECT id FROM customers WHERE bank_id=? AND id LIKE '%-DEP-%' LIMIT 1", (bank_id,)
    ).fetchone()
    if not row:
        raise RuntimeError(f"No existing DEP customer found for {bank_id} to infer prefix")
    return row[0].split('-DEP-')[0]


def _next_seq(cur, table, id_col, prefix, sep):
    row = cur.execute(
        f"SELECT MAX(CAST(SUBSTR({id_col}, ?) AS INTEGER)) FROM {table} WHERE {id_col} LIKE ?",
        (len(prefix) + len(sep) + 1, prefix + sep + '%')
    ).fetchone()
    return (row[0] or 0) + 1


def _next_acc_seq(cur, bank_id):
    row = cur.execute(
        "SELECT id FROM accounts WHERE bank_id=? ORDER BY id DESC", (bank_id,)
    ).fetchall()
    best = 0
    for (aid,) in row:
        m = re.match(r'ACC-[A-Z]+-(\d+)', aid)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


def compute_gaps(cur, target_ratio):
    banks = [r[0] for r in cur.execute("SELECT bank_id FROM banks ORDER BY bank_id").fetchall()]
    gaps = {}
    for b in banks:
        adv = cur.execute("SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?", (b,)).fetchone()[0]
        dep = cur.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE bank_id=?", (b,)).fetchone()[0]
        required = adv / target_ratio
        gaps[b] = {'advances': adv, 'deposits': dep, 'required_deposits': required,
                   'gap': max(required - dep, 0.0)}
    return gaps


def avg_dep_balance(cur, bank_id):
    row = cur.execute(
        "SELECT AVG(a.balance) FROM accounts a WHERE a.bank_id=? AND a.cid LIKE '%-DEP-%'",
        (bank_id,)
    ).fetchone()
    return row[0] or 1_500_000.0


def add_depositors_for_bank(conn, bank_id, gap, sim_date, dry_run):
    cur = conn.cursor()
    if gap <= 0:
        print(f"  {bank_id}: already at/above target, skipping")
        return 0, 0.0

    prefix = _bank_prefix(cur, bank_id)
    avg_balance = avg_dep_balance(cur, bank_id)

    branch_rows = cur.execute(
        "SELECT branch_id, ifsc_code FROM branches WHERE bank_id=?", (bank_id,)
    ).fetchall()

    dep_seq = _next_seq(cur, 'customers', 'id', prefix, '-DEP-')
    acc_seq = _next_acc_seq(cur, bank_id)

    today = date.fromisoformat(sim_date) if sim_date else date.today()
    now_iso = datetime.now().isoformat(timespec='seconds')

    added_count = 0
    added_total = 0.0
    rng = random.Random(hash(bank_id) & 0xffffffff)

    while added_total < gap:
        balance = round(avg_balance * rng.uniform(0.75, 1.25), 2)
        cid = f"{prefix}-DEP-{dep_seq:04d}"
        aid = f"ACC-{prefix}-{acc_seq:05d}"
        txn_id = f"TX-{aid}-0001"

        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        city, state = rng.choice(CITIES)
        age = rng.randint(24, 60)
        gender = rng.choice(['Male', 'Female'])
        dob = date(today.year - age, rng.randint(1, 12), rng.randint(1, 28)).isoformat()
        joined = date(today.year - rng.randint(0, 5), rng.randint(1, 12), 1).isoformat()
        emp_type = rng.choice(EMPLOYMENT_TYPES)
        annual_income = round(balance / rng.uniform(2.5, 5.0), 2)  # balance implies a plausible income
        branch_id, ifsc = rng.choice(branch_rows)

        if not dry_run:
            cur.execute("""
                INSERT INTO customers (id, bank_id, first, last, dob, gender, email, phone,
                    address, city, state, pincode, joined, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, bank_id, first, last, dob, gender,
                  f"{first.lower()}.{last.lower()}{dep_seq}@example.com",
                  f"+91{rng.randint(7000000000, 9999999999)}",
                  f"{rng.randint(1, 999)} Main Road", city, state,
                  str(rng.randint(100000, 999999)), joined, 'Active'))

            cur.execute("""
                INSERT INTO customer_kyc (cid, bank_id, pan_verified, aadhaar_verified,
                    kyc_status, kyc_date, age, gender, marital_status, education_level,
                    num_dependents, employment_type, employer_name, industry_sector,
                    years_employed, annual_income, other_income, foir_declared,
                    residence_type, years_at_address, city_tier, is_pep, risk_category,
                    created_at, updated_at, months_as_customer, num_existing_products,
                    existing_loans_count, loan_purpose, previous_default_flag, cibil_score,
                    num_late_payments_past_12m, state, is_rural)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, bank_id, 1, 1, 'VERIFIED', joined, age, gender,
                  rng.choice(['MARRIED', 'SINGLE']), rng.choice(EDUCATION),
                  rng.randint(0, 3), emp_type, 'Employer Ltd', rng.choice(
                      ['IT', 'Manufacturing', 'Retail', 'Healthcare', 'Finance']),
                  round(rng.uniform(2, min(age - 22, 25)), 1), annual_income, 0.0,
                  round(rng.uniform(0.2, 0.4), 2), rng.choice(['OWNED', 'RENTED']),
                  round(rng.uniform(1, 10), 1), 'TIER1' if city in ('Mumbai', 'Delhi', 'Bengaluru', 'Chennai') else 'TIER2',
                  0, 'LOW', now_iso, now_iso,
                  max(0, (today.year - date.fromisoformat(joined).year) * 12),
                  rng.randint(1, 3), 0, 'NONE', 0, rng.randint(700, 820), 0, state, 0))

            cur.execute("""
                INSERT INTO accounts (id, bank_id, cid, type, balance, open_date,
                    branch_id, ifsc_code, status, maturity_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (aid, bank_id, cid, 'Savings', balance, joined, branch_id, ifsc, 'Active', None))

            cur.execute("""
                INSERT INTO transactions (id, bank_id, aid, date, time, type, amount,
                    balance_after, desc)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (txn_id, bank_id, aid, joined, '08:00:00', 'Deposit', balance, balance,
                  '[INCOME] Opening balance - account funded'))

        added_count += 1
        added_total += balance
        dep_seq += 1
        acc_seq += 1

    print(f"  {bank_id}: added {added_count} pure-depositor customers, "
          f"Rs{added_total/1e7:,.2f} Cr new deposits (gap was Rs{gap/1e7:,.2f} Cr)")
    return added_count, added_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', type=float, default=0.80, help='Target CD ratio (default 0.80)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        import json
        with open(os.path.join(_REPO_ROOT, 'simulation_clock.json')) as f:
            sim_date = json.load(f).get('sim_date')
    except Exception:
        sim_date = None

    print("=" * 70)
    print(f"add_pure_depositors.py — target CD ratio {args.target*100:.0f}%"
          f"{'  [DRY RUN]' if args.dry_run else ''}")
    print("=" * 70)

    gaps = compute_gaps(cur, args.target)
    total_added_count = 0
    total_added_amount = 0.0
    for bank_id, g in gaps.items():
        n, amt = add_depositors_for_bank(conn, bank_id, g['gap'], sim_date, args.dry_run)
        total_added_count += n
        total_added_amount += amt

    if not args.dry_run:
        conn.commit()

    print()
    print(f"Total: {total_added_count} new depositor customers, "
          f"Rs{total_added_amount/1e7:,.2f} Cr new deposits added"
          f"{' (dry run — no changes written)' if args.dry_run else ''}")

    if not args.dry_run:
        print()
        print("Now recomputing post-add CD ratios (live ledger, not yet re-derived balance sheet):")
        gaps_after = compute_gaps(cur, args.target)
        for b, g in gaps_after.items():
            cd = (g['advances'] / g['deposits'] * 100) if g['deposits'] else 0
            print(f"  {b}: CD = {cd:.1f}%")

    conn.close()
    print("=" * 70)


if __name__ == "__main__":
    main()
