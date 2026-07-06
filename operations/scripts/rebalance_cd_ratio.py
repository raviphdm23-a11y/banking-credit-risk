"""
rebalance_cd_ratio.py
──────────────────────
Fixes the system-wide Credit-to-Deposit (CD) ratio, which sat at ~196% across
all 9 banks (real banks run 75-90%) - traced to two causes:

Fix A - ~2,850 synthetic loans (added earlier to give the segmented PD models
enough defaults to train on, id LIKE 'SYN-%') each got a large randomly-sized
principal but only a token linked-account balance (~1 month's income). Tops
up each such account to 4 months' income via a real deposit transaction
(never decreases a balance; skips accounts already at/above target - safe to
rerun).

Fix B - 507 "loan-only" customers (loan at one bank, no account there -
segment C from seed_real_bank.py, "primary banking elsewhere") get a real
second customer+kyc+account record at a DIFFERENT bank in this same 9-bank
universe, sized to 4 months' income, weighted toward whichever bank
currently has the worst (highest) CD ratio. Linked via a new
customer_cross_bank_links table. Skips a loan-only customer who already has
a link - safe to rerun.

Run:  python operations/scripts/rebalance_cd_ratio.py
Then: python operations/scripts/seed_bank_balance_sheet.py
      python operations/scripts/seed_bank_profit_loss.py
      python operations/scripts/run_regulatory_batch.py
"""
import json
import os
import random
import sqlite3
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')
TARGET_MONTHS_INCOME = 4


def _load_sim_clock():
    try:
        with open(os.path.join(_REPO_ROOT, 'simulation_clock.json')) as f:
            return json.load(f)
    except Exception:
        return {'sim_date': '2020-03-31'}


def _next_seq(cur, table, id_col, prefix):
    row = cur.execute(
        f"SELECT MAX(CAST(SUBSTR({id_col}, ?) AS INTEGER)) FROM {table} WHERE {id_col} LIKE ?",
        (len(prefix) + 1, prefix + '%')
    ).fetchone()
    return (row[0] or 0) + 1


def cd_ratios(cur):
    out = {}
    for (bid,) in cur.execute("SELECT bank_id FROM banks").fetchall():
        adv = cur.execute("SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?", (bid,)).fetchone()[0]
        dep = cur.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE bank_id=?", (bid,)).fetchone()[0]
        out[bid] = {'advances': adv, 'deposits': dep, 'cd_pct': (adv / dep * 100) if dep > 0 else None}
    return out


def fix_a_topup_synthetic_loans(conn, sim_date):
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT DISTINCT l.bank_id, l.cid, a.id as aid, a.balance, k.annual_income
        FROM loans l
        JOIN accounts a ON a.cid = l.cid AND a.bank_id = l.bank_id
        JOIN customer_kyc k ON k.cid = l.cid AND k.bank_id = l.bank_id
        WHERE l.id LIKE 'SYN-%'
    """).fetchall()

    updated, total_uplift, seen_aid = 0, 0.0, set()
    for bank_id, cid, aid, balance, income in rows:
        if aid in seen_aid:
            continue
        seen_aid.add(aid)
        target = (income or 0) / 12.0 * TARGET_MONTHS_INCOME
        if target <= balance:
            continue
        uplift = round(target - balance, 2)
        new_balance = round(balance + uplift, 2)
        tx_id = f'TX-{cid}-CDTOPUP'
        if cur.execute("SELECT 1 FROM transactions WHERE id=?", (tx_id,)).fetchone():
            continue
        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (tx_id, bank_id, aid, sim_date, '11:00:00', 'Deposit', uplift, new_balance,
             '[INCOME] Deposit base rebalancing top-up'))
        cur.execute("UPDATE accounts SET balance=? WHERE id=?", (new_balance, aid))
        updated += 1
        total_uplift += uplift

    conn.commit()
    return updated, total_uplift


def fix_b_cross_bank_deposits(conn, sim_date):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customer_cross_bank_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_bank_id TEXT NOT NULL,
            loan_cid TEXT NOT NULL,
            deposit_bank_id TEXT NOT NULL,
            deposit_cid TEXT NOT NULL,
            created_at TEXT,
            UNIQUE(loan_bank_id, loan_cid)
        )
    """)
    conn.commit()

    banks = cur.execute("SELECT bank_id, bank_code FROM banks").fetchall()
    bank_code = {b: code for b, code in banks}

    ratios = cd_ratios(cur)
    # Only banks with a real ledger (advances or deposits > 0) can host a new
    # deposit account - foreign group banks with no loan/account book are
    # balance-sheet-only (seeded by seed_global.py), same skip rule
    # seed_bank_balance_sheet.py already applies.
    active_banks = [bid for bid, r in ratios.items() if r['advances'] > 0 or r['deposits'] > 0]
    # Weight = current CD ratio (or a high default for a zero-deposit bank,
    # so it's still eligible but not favored over worse-but-nonzero banks).
    weight = {bid: (ratios[bid]['cd_pct'] or 300.0) for bid in active_banks}

    loan_only = cur.execute("""
        SELECT DISTINCT l.bank_id, l.cid FROM loans l
        WHERE l.cid NOT IN (SELECT cid FROM accounts WHERE accounts.bank_id = l.bank_id)
    """).fetchall()

    rng = random.Random(2028)
    branch_cache = {}
    created, total_new_deposits, skipped = 0, 0.0, 0

    for loan_bank_id, loan_cid in loan_only:
        if cur.execute(
            "SELECT 1 FROM customer_cross_bank_links WHERE loan_bank_id=? AND loan_cid=?",
            (loan_bank_id, loan_cid)
        ).fetchone():
            continue

        kyc = cur.execute(
            "SELECT * FROM customer_kyc WHERE cid=? AND bank_id=?", (loan_cid, loan_bank_id)
        ).fetchone()
        cust = cur.execute(
            "SELECT * FROM customers WHERE id=? AND bank_id=?", (loan_cid, loan_bank_id)
        ).fetchone()
        if not kyc or not cust:
            skipped += 1
            continue

        candidates = [b for b in active_banks if b != loan_bank_id]
        if not candidates:
            skipped += 1
            continue
        weights = [weight[b] for b in candidates]
        dest_bank = rng.choices(candidates, weights=weights, k=1)[0]
        dest_code = bank_code[dest_bank]

        new_cid = f"{dest_code}-DEP-{_next_seq(cur, 'customers', 'id', f'{dest_code}-DEP-'):04d}"
        new_aid = f"ACC-{dest_code}-{_next_seq(cur, 'accounts', 'id', f'ACC-{dest_code}-'):05d}"

        if dest_bank not in branch_cache:
            r = cur.execute("SELECT branch_id, ifsc_code FROM branches WHERE bank_id=? LIMIT 1", (dest_bank,)).fetchone()
            branch_cache[dest_bank] = r or (f'BR-{dest_bank}-001', f'{dest_bank}0000001')
        branch_id, ifsc = branch_cache[dest_bank]

        cur.execute(
            "INSERT INTO customers (id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (new_cid, dest_bank, cust['first'], cust['last'], cust['dob'], cust['gender'],
             f"{new_cid.lower()}@example.com", cust['phone'], cust['address'], cust['city'],
             cust['state'], cust['pincode'], sim_date, 'Active'))

        income = kyc['annual_income'] or 0
        target_balance = round(income / 12.0 * TARGET_MONTHS_INCOME, 2) or 50000.0

        cur.execute(
            "INSERT INTO accounts (id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (new_aid, dest_bank, new_cid, 'Savings', target_balance, sim_date, branch_id, ifsc, 'Active'))

        cur.execute(
            "INSERT INTO transactions (id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (f'TX-{new_cid}-OPEN', dest_bank, new_aid, sim_date, '10:00:00', 'Deposit',
             target_balance, target_balance,
             '[INCOME] Opening deposit - cross-bank relationship (primary banking elsewhere)'))

        now = datetime.now().isoformat(timespec='seconds')
        cur.execute(
            "INSERT INTO customer_kyc (cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,age,gender,"
            "marital_status,education_level,num_dependents,employment_type,employer_name,industry_sector,"
            "years_employed,annual_income,other_income,foir_declared,residence_type,years_at_address,city_tier,"
            "is_pep,risk_category,created_at,updated_at,months_as_customer,num_existing_products,existing_loans_count,"
            "loan_purpose,previous_default_flag,cibil_score,num_late_payments_past_12m,state,is_rural) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (new_cid, dest_bank, kyc['pan_verified'], kyc['aadhaar_verified'], 'VERIFIED', sim_date,
             kyc['age'], kyc['gender'], kyc['marital_status'], kyc['education_level'], kyc['num_dependents'],
             kyc['employment_type'], kyc['employer_name'], kyc['industry_sector'], kyc['years_employed'],
             income, kyc['other_income'], kyc['foir_declared'], kyc['residence_type'], kyc['years_at_address'],
             kyc['city_tier'], kyc['is_pep'], kyc['risk_category'], now, now,
             0, 1, 0, kyc['loan_purpose'], 0, kyc['cibil_score'], 0, kyc['state'], kyc['is_rural']))

        cur.execute(
            "INSERT INTO customer_cross_bank_links (loan_bank_id, loan_cid, deposit_bank_id, deposit_cid, created_at) "
            "VALUES (?,?,?,?,?)", (loan_bank_id, loan_cid, dest_bank, new_cid, now))

        created += 1
        total_new_deposits += target_balance

    conn.commit()
    return created, total_new_deposits, skipped


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sim = _load_sim_clock()
    sim_date = sim['sim_date']

    print("=" * 70)
    print("BEFORE")
    print("=" * 70)
    before = cd_ratios(cur)
    for bid, r in before.items():
        cd = f"{r['cd_pct']:.0f}%" if r['cd_pct'] is not None else "n/a"
        print(f"  {bid}: advances Rs{r['advances']:,.0f}  deposits Rs{r['deposits']:,.0f}  CD={cd}")

    print("\nRunning Fix A (top up underfunded synthetic-loan accounts)...")
    n_a, uplift_a = fix_a_topup_synthetic_loans(conn, sim_date)
    print(f"  Updated {n_a} accounts, +Rs{uplift_a:,.0f} total")

    print("\nRunning Fix B (cross-bank deposit accounts for loan-only customers)...")
    n_b, uplift_b, skipped_b = fix_b_cross_bank_deposits(conn, sim_date)
    print(f"  Created {n_b} cross-bank deposit relationships, +Rs{uplift_b:,.0f} total ({skipped_b} skipped)")

    print("\n" + "=" * 70)
    print("AFTER")
    print("=" * 70)
    after = cd_ratios(cur)
    for bid, r in after.items():
        cd = f"{r['cd_pct']:.0f}%" if r['cd_pct'] is not None else "n/a"
        print(f"  {bid}: advances Rs{r['advances']:,.0f}  deposits Rs{r['deposits']:,.0f}  CD={cd}")

    tot_adv = sum(r['advances'] for r in after.values())
    tot_dep = sum(r['deposits'] for r in after.values())
    print(f"\nSystem-wide CD ratio: {tot_adv/tot_dep*100:.0f}%")

    conn.close()


if __name__ == '__main__':
    main()
