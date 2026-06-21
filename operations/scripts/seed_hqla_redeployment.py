"""
seed_hqla_redeployment.py
─────────────────────────
Simulates redeployment of excess HQLA into advances for Axis Bank (BANK010).

Context (simulation date 2020-03-31):
  LCR was 411% vs RBI minimum 100% — Rs275 Cr of excess HQLA sitting in
  low-yield government securities. Target: bring LCR to ~130–150% by
  deploying ~Rs230 Cr into 500 new loans across a balanced retail mix,
  funded by liquidating part of the investments (SLR) portfolio.

Changes:
  1. Creates 500 new loans for customers currently without a loan.
  2. Reduces the investments ratio in bank_balance_sheet (27% → 20% of D)
     to reflect the securities sold to fund the lending.
  3. Re-seeds bank_balance_sheet and bank_profit_loss.
  4. Re-runs the regulatory batch (report_date 2020-03-31).

Idempotent: loans are tagged with source='hqla_redeployment'; re-running
deletes and recreates them, then re-seeds downstream tables.

Run: python operations/scripts/seed_hqla_redeployment.py
"""

import os, sys, sqlite3, random, math
from datetime import date, timedelta
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')
BANK_ID  = 'BANK010'
SIM_DATE = '2020-03-31'
TARGET_LOANS    = 500
TARGET_BOOK_CR  = 230       # Rs Crore total new advances
NEW_INV_RATIO   = 0.20      # reduce investments from 27% → 20% of deposits

# Balanced retail mix: (loan_type, weight, rate_range, tenure_range_months)
LOAN_MIX = [
    ('Business Loan',  0.30, (9.0,  11.5), (24,  84)),
    ('Home Loan',      0.30, (8.5,  10.5), (120, 240)),
    ('Personal Loan',  0.20, (12.5, 14.5), (24,  60)),
    ('Vehicle Loan',   0.10, (11.0, 13.5), (36,  60)),
    ('Education Loan', 0.10, (11.5, 14.0), (36,  84)),
]

BRANCHES = ['BR-AXIS-001', 'BR-AXIS-002', 'BR-AXIS-003',
            'BR-AXIS-004', 'BR-AXIS-005']

EXPOSURE_CLASS = {
    'Business Loan':  'corporate',
    'Home Loan':      'retail_secured',
    'Personal Loan':  'retail_unsecured',
    'Vehicle Loan':   'retail_secured',
    'Education Loan': 'retail_unsecured',
}


def _emi(principal, annual_rate, tenure_months):
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / tenure_months
    return principal * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)


def _disbursal_date(sim_date_str, tenure_months):
    """Random disbursal between (sim_date - tenure) and (sim_date - 3 months)."""
    sim = date.fromisoformat(sim_date_str)
    earliest = sim - timedelta(days=tenure_months * 30)
    latest   = sim - timedelta(days=90)
    if earliest >= latest:
        return earliest.isoformat()
    delta = (latest - earliest).days
    return (earliest + timedelta(days=random.randint(0, delta))).isoformat()


def run(db_path=DB_PATH, verbose=True):
    random.seed(42)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    # ── 1. Add source column if missing, remove previous redeployment loans ──
    try:
        cur.execute("ALTER TABLE loans ADD COLUMN source TEXT")
    except sqlite3.OperationalError:
        pass  # already exists
    cur.execute("DELETE FROM loans WHERE bank_id=? AND source='hqla_redeployment'", (BANK_ID,))
    conn.commit()
    if verbose:
        print(f"[1] Cleared previous redeployment loans.")

    # ── 2. Pick customers without existing loans ──────────────────────────────
    pool = [dict(r) for r in cur.execute("""
        SELECT c.id, c.first, c.last FROM customers c
        WHERE c.bank_id=?
          AND NOT EXISTS (
              SELECT 1 FROM loans l WHERE l.cid=c.id AND l.bank_id=?
          )
        ORDER BY c.id
    """, (BANK_ID, BANK_ID)).fetchall()]

    if len(pool) < TARGET_LOANS:
        print(f"[warn] Only {len(pool)} eligible customers; creating {len(pool)} loans.")
    selected = pool[:TARGET_LOANS]

    # ── 3. Build loan allocation per type ────────────────────────────────────
    target_raw = TARGET_BOOK_CR * 1e7   # convert Cr → raw INR
    per_loan   = target_raw / TARGET_LOANS

    # Expand mix into per-customer assignments
    assignments = []
    for ltype, weight, _, _ in LOAN_MIX:
        n = round(weight * TARGET_LOANS)
        assignments.extend([ltype] * n)
    # Trim / pad to exactly TARGET_LOANS
    while len(assignments) < TARGET_LOANS:
        assignments.append('Business Loan')
    assignments = assignments[:TARGET_LOANS]
    random.shuffle(assignments)

    mix_cfg = {lt: (rng, ten) for lt, _, rng, ten in LOAN_MIX}

    # ── 4. Insert loans ───────────────────────────────────────────────────────
    sim = date.fromisoformat(SIM_DATE)
    now = datetime.now().isoformat(timespec='seconds')
    created = 0
    total_principal = 0.0

    for cust, ltype in zip(selected, assignments):
        rate_lo, rate_hi = mix_cfg[ltype][0]
        ten_lo,  ten_hi  = mix_cfg[ltype][1]

        rate    = round(random.uniform(rate_lo, rate_hi), 2)
        tenure  = random.randint(ten_lo // 12, ten_hi // 12) * 12  # round to years
        # Vary principal ±40% around per_loan target
        principal = round(per_loan * random.uniform(0.6, 1.4), 2)
        emi_val   = round(_emi(principal, rate, tenure), 2)

        disbursed  = _disbursal_date(SIM_DATE, tenure)
        dis_date   = date.fromisoformat(disbursed)
        mat_date   = dis_date + timedelta(days=tenure * 30)
        months_paid = max(0, (sim - dis_date).days // 30)
        outstanding = round(max(0, principal - emi_val * months_paid * 0.3), 2)
        dpd         = random.choices([0, 0, 0, 0, 0, 0, 0, 15, 30, 45],
                                     weights=[70,5,5,5,5,3,2,2,2,1])[0]
        classification = 'Standard' if dpd < 90 else 'Sub-Standard'

        loan_id = f'LOAN-HQLA-{created+1:04d}'
        cur.execute("""
            INSERT INTO loans
              (id, bank_id, cid, type, principal, rate, tenure, emi, disbursed, maturity,
               outstanding, status, branch_id, loan_classification, exposure_class,
               days_past_due, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            loan_id, BANK_ID, cust['id'], ltype, principal, rate, tenure, emi_val,
            disbursed, mat_date.isoformat(), outstanding, 'Active',
            random.choice(BRANCHES), classification,
            EXPOSURE_CLASS.get(ltype, 'retail_unsecured'), dpd,
            'hqla_redeployment'
        ))
        total_principal += principal
        created += 1

    conn.commit()
    if verbose:
        print(f"[2] Created {created} new loans  |  Total principal: Rs{total_principal/1e7:.1f} Cr")

    # ── 5. Re-seed balance sheet with reduced investments ratio ───────────────
    import importlib.util

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    scripts = os.path.join(_REPO_ROOT, 'operations', 'scripts')

    bs_mod = _load('seed_bank_balance_sheet', os.path.join(scripts, 'seed_bank_balance_sheet.py'))
    # Temporarily override the investments ratio
    _orig_ratio = None
    src = open(os.path.join(scripts, 'seed_bank_balance_sheet.py')).read()
    # Patch via monkey-patching _build_sheet at runtime
    orig_build = bs_mod._build_sheet

    def patched_build(bank_id, period, as_on_date, advances_net, total_deposits, scale, source):
        row = orig_build(bank_id, period, as_on_date, advances_net, total_deposits, scale, source)
        # Reduce investments, let balances_with_banks absorb the slack
        D = total_deposits * scale
        old_inv = row['investments']
        new_inv = round(NEW_INV_RATIO * D, 2)
        diff    = old_inv - new_inv          # released liquidity
        row['investments']       = new_inv
        row['balances_with_banks'] = round(row['balances_with_banks'] + diff, 2)
        return row

    bs_mod._build_sheet = patched_build
    bs_mod.seed(db_path=db_path, verbose=verbose)
    if verbose:
        print(f"[3] Balance sheet re-seeded (investments ratio: 27% -> {int(NEW_INV_RATIO*100)}% of deposits).")

    pl_mod = _load('seed_bank_profit_loss', os.path.join(scripts, 'seed_bank_profit_loss.py'))
    pl_mod.seed(db_path=db_path, verbose=verbose)
    if verbose:
        print("[4] P&L re-seeded.")

    # ── 6. Re-run regulatory batch ────────────────────────────────────────────
    rb_mod = _load('run_regulatory_batch', os.path.join(scripts, 'run_regulatory_batch.py'))
    rb_mod.run_batch(db_path=db_path, report_date=SIM_DATE, verbose=verbose)
    if verbose:
        print("[5] Regulatory batch re-run.")

    conn.close()


if __name__ == '__main__':
    run()
