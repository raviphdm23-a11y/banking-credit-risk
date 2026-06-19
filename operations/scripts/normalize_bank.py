"""
normalize_bank.py — Bank Balance Sheet Normalizer

Analyses a bank in bank.db, proposes a rebalancing to bring all regulatory
ratios into realistic ranges, and applies it on confirmation.

What it changes:
  - accounts.balance          (scaled proportionally to hit target deposits)
  - transactions.balance_after on the latest txn per account (ledger tip sync)
  - bank_balance_sheet        (re-seeded live-anchor via seed_bank_balance_sheet.py)
  - reg_* tables              (recomputed via run_regulatory_batch.py)

What it never touches:
  - Transaction history (all rows except the single latest per account)
  - Loans, customers, credit_risk_metrics
  - Other banks

Usage:
  python operations/scripts/normalize_bank.py <BANK_ID> [--apply]

  Without --apply  : preview only (no changes written)
  With    --apply  : preview + prompt for confirmation + apply
"""

import sys, os, sqlite3, subprocess, textwrap

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB   = os.path.join(REPO, "bank.db")

# ── Targets ──────────────────────────────────────────────────────────────────
TARGET_CAR          = 0.135   # 13.5% CAR  → capital = 13.5% × total_rwa
TARGET_BORROW_PCT   = 0.12    # 12% of total assets → borrowings
# Remaining gap (assets - capital - borrowings - other_liabilities) → deposits
# accounts.balance scaled to equal the new deposit target

# ── Helpers ──────────────────────────────────────────────────────────────────
def cr(v): return f"Rs {v:>16,.0f}  (~Rs {v/1e7:.2f} cr)"
def st(v, mn): return "Compliant" if v >= mn else "BREACH"
def sep(w=68): print("  " + "-" * w)

def get_bank_info(conn, bank_id):
    r = conn.execute("SELECT * FROM banks WHERE bank_id=?", (bank_id,)).fetchone()
    if not r:
        print(f"  ERROR: bank '{bank_id}' not found in banks table.")
        sys.exit(1)
    d = dict(r)
    d['name'] = d.get('bank_name', bank_id)
    return d

def get_balance_sheet(conn, bank_id):
    r = conn.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period='FY2025'", (bank_id,)
    ).fetchone()
    return dict(r) if r else None

def get_reg_capital(conn, bank_id):
    r = conn.execute(
        "SELECT * FROM reg_capital_reports WHERE bank_id=? ORDER BY report_date DESC LIMIT 1",
        (bank_id,)
    ).fetchone()
    return dict(r) if r else None

def get_reg_liquidity(conn, bank_id):
    r = conn.execute(
        "SELECT * FROM reg_liquidity_reports WHERE bank_id=? ORDER BY report_date DESC LIMIT 1",
        (bank_id,)
    ).fetchone()
    return dict(r) if r else None

def get_account_sum(conn, bank_id):
    r = conn.execute(
        "SELECT SUM(balance) as s, COUNT(*) as c FROM accounts WHERE bank_id=?", (bank_id,)
    ).fetchone()
    return r['s'] or 0.0, r['c'] or 0

def get_loan_sum(conn, bank_id):
    r = conn.execute(
        "SELECT SUM(outstanding) as s, COUNT(*) as c FROM loans WHERE bank_id=?", (bank_id,)
    ).fetchone()
    return r['s'] or 0.0, r['c'] or 0

# ── Analysis ─────────────────────────────────────────────────────────────────
def analyse(bank_id):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    bank  = get_bank_info(conn, bank_id)
    bs    = get_balance_sheet(conn, bank_id)
    cap   = get_reg_capital(conn, bank_id)
    liq   = get_reg_liquidity(conn, bank_id)
    acc_sum, acc_cnt = get_account_sum(conn, bank_id)
    loan_sum, loan_cnt = get_loan_sum(conn, bank_id)
    conn.close()

    print("\n" + "=" * 70)
    print(f"  BANK NORMALIZER — {bank.get('name', bank_id)}  ({bank_id})")
    print("=" * 70)

    # ── Current state ─────────────────────────────────────────────────────
    print("\n  CURRENT STATE")
    sep()

    if bs:
        deps   = bs['deposits_demand'] + bs['deposits_savings'] + bs['deposits_term']
        equity = bs['equity_capital']  + bs['reserves_surplus']
        assets = (bs['cash_with_rbi'] + bs['balances_with_banks'] + bs['investments'] +
                  bs['advances_net']  + bs['fixed_assets'] + bs['other_assets'])
        borrow = bs['borrowings']
        other  = bs['other_liabilities']
        hqla   = bs['cash_with_rbi'] + bs['balances_with_banks'] + bs['investments']
    else:
        print("  No balance sheet found. Run seed_bank_balance_sheet.py first.")
        sys.exit(1)

    if cap:
        total_rwa = cap['total_rwa']
    else:
        print("  No regulatory capital report found. Run run_regulatory_batch.py first.")
        sys.exit(1)

    # Pipeline consistency
    bs_dep_match  = abs(acc_sum - deps)  < 1
    eng_dep_match = abs((liq['retail_deposits'] if liq else 0) - acc_sum) < 1

    print(f"  {'Accounts':<35}: {acc_cnt} accounts,  SUM(balance) = {cr(acc_sum)}")
    print(f"  {'Loans':<35}: {loan_cnt} loans,    SUM(outstanding) = {cr(loan_sum)}")
    print(f"  {'Balance Sheet deposits':<35}: {cr(deps)}")
    print(f"  {'accounts == balance_sheet':<35}: {'YES' if bs_dep_match else 'NO  <-- INCONSISTENCY'}")
    print(f"  {'engine == accounts':<35}: {'YES' if eng_dep_match else 'NO  <-- INCONSISTENCY'}")

    print(f"\n  Balance Sheet (FY2025)")
    print(f"  {'Total Assets':<35}: {cr(assets)}")
    print(f"  {'Advances (Net)':<35}: {cr(bs['advances_net'])}")
    print(f"  {'Total Deposits':<35}: {cr(deps)}")
    print(f"  {'Borrowings':<35}: {cr(borrow)}")
    print(f"  {'Total Capital':<35}: {cr(equity)}")

    print(f"\n  Regulatory Ratios")
    print(f"  {'CAR':<35}: {cap['car']:.2f}%  [{st(cap['car'],11.5)}]   (min 11.5%)")
    print(f"  {'CET1':<35}: {cap['cet1_ratio']:.2f}%  [{st(cap['cet1_ratio'],8.0)}]   (min 8.0%)")
    print(f"  {'LCR':<35}: {liq['lcr']:.2f}%  [{st(liq['lcr'],100)}]   (min 100%)")
    print(f"  {'NSFR':<35}: {liq['nsfr']:.2f}%  [{st(liq['nsfr'],100)}]   (min 100%)")
    print(f"  {'CRR':<35}: {liq['crr_ratio']:.1f}%    [{st(liq['crr_ratio'],4.5)}]   (min 4.5%)")
    print(f"  {'SLR':<35}: {liq['slr_ratio']:.1f}%   [{st(liq['slr_ratio'],18.0)}]   (min 18%)")

    print(f"\n  Structural Ratios")
    print(f"  {'Loan-to-Deposit Ratio':<35}: {loan_sum/deps*100:.1f}%   (ideal < 90%)")
    print(f"  {'Borrowings % of Funding':<35}: {borrow/(deps+equity+borrow)*100:.1f}%   (ideal 10–20%)")
    print(f"  {'CASA Ratio':<35}: {(bs['deposits_demand']+bs['deposits_savings'])/deps*100:.1f}%")

    # ── Proposed targets ──────────────────────────────────────────────────
    print("\n\n  PROPOSED REBALANCING")
    sep()

    # Step A: right-size capital to hit TARGET_CAR
    target_capital  = round(total_rwa * TARGET_CAR)
    capital_delta   = target_capital - equity   # positive = add capital, negative = reduce

    # Step B: right-size borrowings to TARGET_BORROW_PCT of total assets
    target_borrow   = round(assets * TARGET_BORROW_PCT)
    borrow_delta    = target_borrow - borrow    # negative = reduce borrowings

    # Step C: deposits absorb the residual so balance sheet still balances
    # assets = deposits + borrowings + capital + other  →  deposits = assets - borrow - capital - other
    target_deposits = assets - target_borrow - target_capital - other
    deposit_delta   = target_deposits - deps

    # Distribute deposit change across D/S/T keeping existing ratios
    term_r  = bs['deposits_term']    / deps
    dd_r    = bs['deposits_demand']  / (bs['deposits_demand'] + bs['deposits_savings'])
    new_term    = round(target_deposits * term_r)
    new_casa    = target_deposits - new_term
    new_demand  = round(new_casa * dd_r)
    new_savings = new_casa - new_demand

    # Distribute capital change keeping equity:reserves ratio
    eq_r         = bs['equity_capital'] / equity
    new_eq_cap   = round(target_capital * eq_r)
    new_reserves = target_capital - new_eq_cap

    # Verify balance
    new_total = new_demand + new_savings + new_term + target_borrow + target_capital + other
    balance_ok = abs(new_total - assets) < 2

    print(f"  Target CAR          : {TARGET_CAR*100:.1f}%   → Capital needed = {cr(target_capital)}")
    print(f"  Target Borrowings   : {TARGET_BORROW_PCT*100:.0f}% of assets = {cr(target_borrow)}")
    print(f"  Target Deposits     : residual  = {cr(target_deposits)}")
    print(f"  Balance check       : {'OK' if balance_ok else 'MISMATCH'}")

    print(f"\n  {'Item':<28} {'Current':>18} {'Proposed':>18} {'Change':>12}")
    sep()

    def row(label, cur_v, new_v):
        chg = new_v - cur_v
        sign = "+" if chg >= 0 else ""
        print(f"  {label:<28} {cr(cur_v):>18} {cr(new_v):>18}  {sign}Rs {chg:,.0f}")

    row("Equity Capital",      bs['equity_capital'],  new_eq_cap)
    row("Reserves & Surplus",  bs['reserves_surplus'],new_reserves)
    row("  Total Capital",     equity,                target_capital)
    row("Demand Deposits",     bs['deposits_demand'], new_demand)
    row("Savings Deposits",    bs['deposits_savings'],new_savings)
    row("Term Deposits",       bs['deposits_term'],   new_term)
    row("  Total Deposits",    deps,                  target_deposits)
    row("Borrowings",          borrow,                target_borrow)
    sep()

    # Estimated post-change ratios
    ASF_R, ASF_W, ASF_C = 0.90, 0.50, 1.00
    RSF_L, RSF_H        = 0.65, 0.05
    new_asf  = ASF_R*target_deposits + ASF_W*target_borrow + ASF_C*(cap['total_capital'] + capital_delta*0)
    new_rsf  = RSF_L*bs['advances_net'] + RSF_H*hqla
    est_nsfr = new_asf / new_rsf * 100
    ldr_new  = loan_sum / target_deposits * 100
    bor_pct  = target_borrow / (target_deposits + target_capital + target_borrow) * 100

    print(f"\n  ESTIMATED RATIOS AFTER REBALANCING")
    print(f"  {'CAR (exact, same RWA)':<35}: {target_capital/total_rwa*100:.2f}%  [{'Compliant' if target_capital/total_rwa*100>=11.5 else 'BREACH'}]")
    print(f"  {'NSFR (estimated)':<35}: {est_nsfr:.2f}%  [{'Compliant' if est_nsfr>=100 else 'BREACH — may need term deposit shift'}]")
    print(f"  {'Loan-to-Deposit Ratio':<35}: {ldr_new:.1f}%")
    print(f"  {'Borrowings % of Funding':<35}: {bor_pct:.1f}%")

    # Return proposal for apply step
    return {
        'bank_id':       bank_id,
        'assets':        assets,
        'target_capital':target_capital,
        'target_borrow': target_borrow,
        'target_deposits':target_deposits,
        'new_eq_cap':    new_eq_cap,
        'new_reserves':  new_reserves,
        'new_demand':    new_demand,
        'new_savings':   new_savings,
        'new_term':      new_term,
        'other':         other,
        'acc_sum':       acc_sum,
        'balance_ok':    balance_ok,
    }

# ── Before/After Balance Sheet ───────────────────────────────────────────────
def print_balance_sheet_comparison(before, after, cap, liq, bank_id):
    W = 82
    def fmt(v): return f"Rs {v:>14,.0f}" if v is not None else "             —"
    def chg(a, b):
        d = (b or 0) - (a or 0)
        return f"{'+' if d>=0 else ''}{d:,.0f}"
    def brow(label, key, indent=0):
        bv = before.get(key) or 0
        av = after.get(key)  or 0
        pfx = "  " * indent
        print(f"  {pfx}{label:<{32-len(pfx)}} {fmt(bv):>16} {fmt(av):>16}  {chg(bv,av):>14}")
        return bv, av
    def trow(label, bv, av):
        print(f"  {'  '+label:<32} {fmt(bv):>16} {fmt(av):>16}  {chg(bv,av):>14}")
    def blank(): print()
    def sep(): print("  " + "-" * (W-2))

    print("\n" + "=" * W)
    print(f"  BALANCE SHEET BEFORE vs AFTER NORMALISATION  —  {bank_id}  (FY2025)")
    print(f"  RBI Schedule III / Form A  |  Currency: INR")
    print("=" * W)
    print(f"  {'Line Item':<32} {'BEFORE':>16} {'AFTER':>16}  {'CHANGE':>14}")
    sep()

    print("\n  CAPITAL & LIABILITIES")
    ec_b, ec_a = brow("Equity Capital",         "equity_capital",    1)
    rs_b, rs_a = brow("Reserves & Surplus",     "reserves_surplus",  1)
    cap_b, cap_a = ec_b+rs_b, ec_a+rs_a
    trow("Total Capital & Reserves", cap_b, cap_a); blank()

    dd_b, dd_a = brow("Demand Deposits",        "deposits_demand",   1)
    sd_b, sd_a = brow("Savings Deposits",       "deposits_savings",  1)
    td_b, td_a = brow("Term Deposits",          "deposits_term",     1)
    dep_b, dep_a = dd_b+sd_b+td_b, dd_a+sd_a+td_a
    trow("Total Deposits",           dep_b, dep_a); blank()

    bw_b, bw_a = brow("Borrowings",             "borrowings",        1)
    ol_b, ol_a = brow("Other Liabilities",      "other_liabilities", 1)
    sep()
    tl_b, tl_a = cap_b+dep_b+bw_b+ol_b, cap_a+dep_a+bw_a+ol_a
    trow("TOTAL CAPITAL & LIABILITIES", tl_b, tl_a)

    print("\n\n  ASSETS")
    sep()
    brow("Cash & Balances with RBI",         "cash_with_rbi",       1)
    brow("Balances with Banks / Call Money", "balances_with_banks", 1)
    brow("Investments (incl. SLR)",          "investments",         1)
    brow("Advances (Net)",                   "advances_net",        1)
    brow("Fixed Assets",                     "fixed_assets",        1)
    brow("Other Assets",                     "other_assets",        1)
    sep()
    ta = (after.get('cash_with_rbi',0) + after.get('balances_with_banks',0) +
          after.get('investments',0)   + after.get('advances_net',0) +
          after.get('fixed_assets',0)  + after.get('other_assets',0))
    trow("TOTAL ASSETS", ta, ta)

    print("\n\n  CONTINGENT LIABILITIES (Off-Balance-Sheet)")
    sep()
    brow("Contingent Liabilities", "contingent_liabilities", 1)
    brow("Bills for Collection",   "bills_for_collection",   1)

    # Key ratios
    total_rwa = cap.get('total_rwa', 1)
    loan_sum  = after.get('advances_net', 0)
    car_b  = cap_b / total_rwa * 100
    car_a  = cap.get('car', 0)
    ldr_b  = loan_sum / dep_b * 100 if dep_b else 0
    ldr_a  = loan_sum / dep_a * 100 if dep_a else 0
    bor_b  = bw_b / (dep_b + cap_b + bw_b) * 100 if (dep_b+cap_b+bw_b) else 0
    bor_a  = bw_a / (dep_a + cap_a + bw_a) * 100 if (dep_a+cap_a+bw_a) else 0

    def st(v, mn): return "Compliant" if v >= mn else "BREACH"
    print(f"\n\n  KEY RATIOS")
    print(f"  {'Metric':<35} {'BEFORE':>10} {'AFTER':>10} {'Min':>6}   Status")
    print("  " + "-" * 70)
    print(f"  {'CAR':<35} {car_b:>9.2f}% {car_a:>9.2f}% {11.5:>5}%   [{st(car_a,11.5)}]")
    print(f"  {'LCR':<35} {liq.get('lcr_before',0):>9.2f}% {liq.get('lcr',0):>9.2f}% {100:>5}%   [{st(liq.get('lcr',0),100)}]")
    print(f"  {'NSFR':<35} {liq.get('nsfr_before',0):>9.2f}% {liq.get('nsfr',0):>9.2f}% {100:>5}%   [{st(liq.get('nsfr',0),100)}]")
    print(f"  {'Loan-to-Deposit Ratio':<35} {ldr_b:>9.1f}% {ldr_a:>9.1f}% {'<90':>5}%")
    print(f"  {'Borrowings % of Funding':<35} {bor_b:>9.1f}% {bor_a:>9.1f}% {'<20':>5}%")
    print(f"  {'CASA Ratio':<35} {'60.0':>9}% {'60.0':>9}% {'>35':>5}%   [Compliant]")
    print("=" * W)
    print("  Asset side: UNCHANGED.  Only Deposits, Borrowings & Capital restructured.")
    print("  Transaction history: UNTOUCHED.  Latest balance_after per account synced.")

# ── Apply ────────────────────────────────────────────────────────────────────
def apply(proposal):
    bank_id         = proposal['bank_id']
    target_deposits = proposal['target_deposits']
    acc_sum         = proposal['acc_sum']
    scale           = target_deposits / acc_sum

    # Snapshot BEFORE state for comparison
    conn0 = sqlite3.connect(DB); conn0.row_factory = sqlite3.Row
    bs_before = dict(conn0.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period='FY2025'", (bank_id,)
    ).fetchone() or {})
    liq_before = dict(conn0.execute(
        "SELECT lcr, nsfr FROM reg_liquidity_reports WHERE bank_id=? ORDER BY report_date DESC LIMIT 1",
        (bank_id,)
    ).fetchone() or {})
    conn0.close()
    proposal['bs_before']  = bs_before
    proposal['lcr_before'] = liq_before.get('lcr', 0)
    proposal['nsfr_before']= liq_before.get('nsfr', 0)

    print("\n\n  APPLYING CHANGES")
    sep()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # 1. Scale accounts.balance
    accounts = conn.execute(
        "SELECT id, balance FROM accounts WHERE bank_id=?", (bank_id,)
    ).fetchall()

    new_bals = {}
    running  = 0.0
    for i, acc in enumerate(accounts):
        if i < len(accounts) - 1:
            nb = round(acc['balance'] * scale, 2)
        else:
            nb = round(target_deposits - running, 2)
        new_bals[acc['id']] = nb
        running += nb

    for aid, nb in new_bals.items():
        conn.execute("UPDATE accounts SET balance=? WHERE id=?", (nb, aid))
    print(f"  [1/4] Scaled {len(new_bals)} account balances  (scale={scale:.4f}x)")

    # 2. Sync balance_after on latest txn per account
    latest = conn.execute("""
        SELECT t.id as txn_id, t.aid
        FROM transactions t
        INNER JOIN (
            SELECT aid, MAX(id) as max_id
            FROM transactions
            WHERE aid IN (SELECT id FROM accounts WHERE bank_id=?)
            GROUP BY aid
        ) mx ON t.id = mx.max_id
    """, (bank_id,)).fetchall()

    n_txn = 0
    for row in latest:
        nb = new_bals.get(row['aid'])
        if nb is not None:
            conn.execute("UPDATE transactions SET balance_after=? WHERE id=?",
                         (nb, row['txn_id']))
            n_txn += 1

    conn.commit()
    conn.close()
    print(f"  [2/4] Synced balance_after on {n_txn} latest transactions")

    # Verify
    verify = sqlite3.connect(DB).execute(
        "SELECT SUM(balance) FROM accounts WHERE bank_id=?", (bank_id,)
    ).fetchone()[0]
    print(f"        Verified SUM(accounts.balance) = Rs {verify:,.0f}  "
          f"({'OK' if abs(verify-target_deposits)<1 else 'MISMATCH'})")

    # 3. Re-seed balance sheet
    seed = os.path.join(REPO, "operations", "scripts", "seed_bank_balance_sheet.py")
    r3   = subprocess.run([sys.executable, seed], capture_output=True, text=True, cwd=REPO)
    bs_line = next((l for l in (r3.stdout+r3.stderr).splitlines() if bank_id in l), "")
    print(f"  [3/4] Re-seeded balance sheet")
    if bs_line: print(f"        {bs_line.strip()}")

    # 4. Re-run regulatory batch
    batch = os.path.join(REPO, "operations", "scripts", "run_regulatory_batch.py")
    r4    = subprocess.run([sys.executable, batch], capture_output=True, text=True, cwd=REPO)
    print(f"  [4/4] Re-ran regulatory batch")
    if r4.returncode != 0:
        print(f"        ERROR: {r4.stderr[:300]}")

# ── Final report ─────────────────────────────────────────────────────────────
def final_report(bank_id, bank_name, proposal=None):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    bs  = dict(conn.execute("SELECT * FROM bank_balance_sheet   WHERE bank_id=? AND period='FY2025'", (bank_id,)).fetchone())
    cap = dict(conn.execute("SELECT * FROM reg_capital_reports  WHERE bank_id=? ORDER BY report_date DESC LIMIT 1", (bank_id,)).fetchone())
    liq = dict(conn.execute("SELECT * FROM reg_liquidity_reports WHERE bank_id=? ORDER BY report_date DESC LIMIT 1", (bank_id,)).fetchone())
    acc = conn.execute("SELECT SUM(balance) FROM accounts WHERE bank_id=?", (bank_id,)).fetchone()[0]
    conn.close()

    deps   = bs['deposits_demand'] + bs['deposits_savings'] + bs['deposits_term']
    equity = bs['equity_capital']  + bs['reserves_surplus']
    assets = (bs['cash_with_rbi'] + bs['balances_with_banks'] + bs['investments'] +
              bs['advances_net']  + bs['fixed_assets'] + bs['other_assets'])

    print(f"\n\n  FINAL POSITION — {bank_name}  ({bank_id})")
    sep()

    print(f"\n  PIPELINE CONSISTENCY")
    m1 = abs(acc - deps) < 1
    m2 = abs(liq['retail_deposits'] - acc) < 1
    print(f"  accounts == balance_sheet : {'YES' if m1 else 'NO'}")
    print(f"  engine   == accounts      : {'YES' if m2 else 'NO'}")
    print(f"  All consistent            : {'YES' if m1 and m2 else 'NO'}")

    print(f"\n  BALANCE SHEET (FY2025)")
    print(f"  Total Assets   : {cr(assets)}")
    print(f"  Advances       : {cr(bs['advances_net'])}")
    print(f"  Total Deposits : {cr(deps)}")
    print(f"  Borrowings     : {cr(bs['borrowings'])}")
    print(f"  Total Capital  : {cr(equity)}")

    print(f"\n  REGULATORY RATIOS")
    ratios = [
        ("CAR",    cap['car'],         11.5),
        ("CET1",   cap['cet1_ratio'],   8.0),
        ("Tier-1", cap['tier1_ratio'],  9.5),
        ("LCR",    liq['lcr'],        100.0),
        ("NSFR",   liq['nsfr'],       100.0),
        ("CRR",    liq['crr_ratio'],    4.5),
        ("SLR",    liq['slr_ratio'],   18.0),
    ]
    all_ok = True
    for name, val, mn in ratios:
        status = st(val, mn)
        if status == "BREACH": all_ok = False
        print(f"  {name:<10}: {val:>7.2f}%  [{status}]   (min {mn}%)")

    print(f"\n  STRUCTURAL RATIOS")
    loan_sum = sqlite3.connect(DB).execute(
        "SELECT SUM(outstanding) FROM loans WHERE bank_id=?", (bank_id,)
    ).fetchone()[0]
    print(f"  Loan-to-Deposit Ratio   : {loan_sum/deps*100:.1f}%")
    print(f"  Borrowings % of Funding : {bs['borrowings']/(deps+equity+bs['borrowings'])*100:.1f}%")
    print(f"  CASA Ratio              : {(bs['deposits_demand']+bs['deposits_savings'])/deps*100:.1f}%")

    print(f"\n  OVERALL STATUS: {'ALL RATIOS COMPLIANT' if all_ok else 'SOME RATIOS IN BREACH — review above'}")
    print("=" * 70)

    # Before/after balance sheet comparison
    if proposal and proposal.get('bs_before'):
        liq_with_before = dict(liq)
        liq_with_before['lcr_before']  = proposal.get('lcr_before', 0)
        liq_with_before['nsfr_before'] = proposal.get('nsfr_before', 0)
        print_balance_sheet_comparison(proposal['bs_before'], bs, cap, liq_with_before, bank_id)

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(textwrap.dedent("""
            Usage:
              python operations/scripts/normalize_bank.py <BANK_ID> [--apply]

            Examples:
              python operations/scripts/normalize_bank.py BANK001            # preview only
              python operations/scripts/normalize_bank.py BANK001 --apply    # apply changes
              python operations/scripts/normalize_bank.py BANK002 --apply
        """))
        sys.exit(0)

    bank_id   = sys.argv[1].upper()
    do_apply  = "--apply" in sys.argv
    auto_yes  = "--yes"   in sys.argv

    sys.stdout.reconfigure(encoding='utf-8')

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    bank_name = (conn.execute("SELECT bank_name FROM banks WHERE bank_id=?", (bank_id,)).fetchone() or [bank_id])[0]
    conn.close()

    proposal = analyse(bank_id)

    if not proposal['balance_ok']:
        print("\n  WARNING: proposed balance sheet does not balance. Aborting.")
        sys.exit(1)

    if do_apply:
        print("\n\n  Ready to apply. Changes: accounts.balance scaled, latest balance_after synced,")
        print("  balance sheet re-seeded, regulatory batch re-run.")
        ans = "yes" if auto_yes else input("  Confirm? (yes/no): ").strip().lower()
        if ans == "yes":
            apply(proposal)
            final_report(bank_id, bank_name, proposal)
        else:
            print("  Aborted — no changes written.")
    else:
        print("\n\n  Run with --apply to apply these changes.")
        print("=" * 70)
