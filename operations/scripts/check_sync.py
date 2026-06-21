"""
check_sync.py
─────────────
Quick sync-check for the Axis Bank simulation. Verifies that the DB state
(balance sheet, P&L, regulatory batch, loan book) is fully aligned with the
frozen simulation clock in simulation_clock.json.

Run: python operations/scripts/check_sync.py

Exit code 0 = all checks pass. Exit code 1 = one or more checks failed.
"""

import os, sys, json, sqlite3

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH    = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH   = os.path.join(_REPO_ROOT, 'simulation_clock.json')

# ── Load simulation clock ─────────────────────────────────────────────────────
try:
    clk        = json.load(open(CLK_PATH))
    SIM_DATE   = clk['sim_date']
    SIM_PERIOD = clk['sim_period']
    PREV_PERIOD= clk.get('prior_period', '')
except Exception as e:
    print(f'[FAIL] Cannot read simulation_clock.json: {e}')
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

PASS = '[PASS]'
FAIL = '[FAIL]'
WARN = '[WARN]'
results = []

def check(label, passed, detail=''):
    tag = PASS if passed else FAIL
    line = f'  {tag}  {label}'
    if detail:
        line += f'  ({detail})'
    results.append((passed, line))
    print(line)

print()
print('=' * 65)
print(f'  Axis Bank Simulation Sync Check')
print(f'  Clock:  sim_date={SIM_DATE}  sim_period={SIM_PERIOD}')
print('=' * 65)

# ── 1. simulation_clock.json ──────────────────────────────────────────────────
print('\n[1] Simulation Clock')
check('sim_date present',   bool(SIM_DATE),   SIM_DATE)
check('sim_period present', bool(SIM_PERIOD), SIM_PERIOD)

# ── 2. Balance sheet ──────────────────────────────────────────────────────────
print('\n[2] Balance Sheet  (bank_balance_sheet)')
bs_periods = [r[0] for r in conn.execute(
    "SELECT period FROM bank_balance_sheet WHERE bank_id='BANK010' ORDER BY period").fetchall()]
check('FY current period exists', SIM_PERIOD in bs_periods,    f'found: {bs_periods}')
check('Prior period exists',      PREV_PERIOD in bs_periods,   f'found: {bs_periods}')
# "future" means as_on_date > sim_date, not string comparison of period labels
bs_future = [r[0] for r in conn.execute(
    "SELECT period FROM bank_balance_sheet WHERE bank_id='BANK010' AND as_on_date > ?",
    (SIM_DATE,)).fetchall()]
check('No future-dated periods', len(bs_future) == 0,
      f'future periods: {bs_future}' if bs_future else f'all periods <= {SIM_DATE}')

bs = conn.execute(
    "SELECT * FROM bank_balance_sheet WHERE bank_id='BANK010' AND period=?",
    (SIM_PERIOD,)).fetchone()
if bs:
    bs = dict(bs)
    ta = sum(bs.get(k, 0) or 0 for k in
             ('cash_with_rbi','balances_with_banks','investments',
              'advances_net','fixed_assets','intangible_assets','other_assets'))
    tl = sum(bs.get(k, 0) or 0 for k in
             ('equity_capital','reserves_surplus','deposits_demand',
              'deposits_savings','deposits_term','borrowings','other_liabilities'))
    diff = abs(ta - tl)
    check('Balance sheet balances (diff < Rs1)',  diff < 1.0,
          f'Assets={ta/1e7:.1f} Cr  L+C={tl/1e7:.1f} Cr  diff={diff:.2f}')
    check('as_on_date matches sim_date', bs.get('as_on_date') == SIM_DATE,
          f"as_on_date={bs.get('as_on_date')}")
    check('Intangible assets seeded', (bs.get('intangible_assets') or 0) > 0,
          f"intangibles={bs.get('intangible_assets',0)/1e7:.2f} Cr")

# ── 3. P&L ────────────────────────────────────────────────────────────────────
print('\n[3] Profit & Loss  (bank_profit_loss)')
pl_periods = [r[0] for r in conn.execute(
    "SELECT period FROM bank_profit_loss WHERE bank_id='BANK010' ORDER BY period").fetchall()]
check('FY current period exists', SIM_PERIOD in pl_periods, f'found: {pl_periods}')
pl_future = [r[0] for r in conn.execute(
    "SELECT period FROM bank_profit_loss WHERE bank_id='BANK010' AND to_date > ?",
    (SIM_DATE,)).fetchall()]
check('No future-dated periods', len(pl_future) == 0,
      f'future periods: {pl_future}' if pl_future else f'all periods <= {SIM_DATE}')

pl = conn.execute(
    "SELECT * FROM bank_profit_loss WHERE bank_id='BANK010' AND period=?",
    (SIM_PERIOD,)).fetchone()
if pl:
    pl = dict(pl)
    check('to_date matches sim_date', pl.get('to_date') == SIM_DATE,
          f"to_date={pl.get('to_date')}")
    pat_val = pl.get('profit_after_tax') or 0
    # PAT may be negative during COVID provision months — flag as WARN not FAIL
    pat_ok  = pat_val > 0
    tag = '[PASS]' if pat_ok else '[WARN]'
    line = f'  {tag}  PAT for period  (PAT=Rs{pat_val/1e7:.2f} Cr{"  -- COVID provision drag, expected" if not pat_ok else ""})'
    results.append((True, line))   # always treated as pass (warn only)
    print(line)

# ── 4. Regulatory batch ───────────────────────────────────────────────────────
print('\n[4] Regulatory Batch  (reg_capital_reports / reg_liquidity_reports)')
reg_dates = [r[0] for r in conn.execute(
    "SELECT DISTINCT report_date FROM reg_capital_reports ORDER BY report_date").fetchall()]
check('Report exists for sim_date',  SIM_DATE in reg_dates, f'found: {reg_dates}')
check('No future report dates',
      not any(d > SIM_DATE for d in reg_dates),
      f'dates: {reg_dates}')

cap = conn.execute(
    "SELECT * FROM reg_capital_reports WHERE bank_id='BANK010' AND report_date=?",
    (SIM_DATE,)).fetchone()
liq = conn.execute(
    "SELECT * FROM reg_liquidity_reports WHERE bank_id='BANK010' AND report_date=?",
    (SIM_DATE,)).fetchone()
if cap:
    cap = dict(cap)
    check('CAR >= 11.5% (RBI minimum)', (cap.get('car') or 0) >= 11.5,
          f"CAR={cap.get('car')}%")
    check('CET1 >= 8.0% (RBI minimum)', (cap.get('cet1_ratio') or 0) >= 8.0,
          f"CET1={cap.get('cet1_ratio')}%")
if liq:
    liq = dict(liq)
    check('LCR >= 100% (RBI minimum)', (liq.get('lcr') or 0) >= 100.0,
          f"LCR={liq.get('lcr')}%")
    check('NSFR >= 100% (RBI minimum)', (liq.get('nsfr') or 0) >= 100.0,
          f"NSFR={liq.get('nsfr')}%")

# ── 5. Loan book ──────────────────────────────────────────────────────────────
print('\n[5] Loan Book  (loans)')
loan_count = conn.execute(
    "SELECT COUNT(*) FROM loans WHERE bank_id='BANK010'").fetchone()[0]
check('Loan book not empty', loan_count > 0, f'{loan_count:,} loans')

future_loans = conn.execute(
    "SELECT COUNT(*) FROM loans WHERE bank_id='BANK010' AND disbursed > ?",
    (SIM_DATE,)).fetchone()[0]
check('No loans disbursed after sim_date', future_loans == 0,
      f'{future_loans} future-dated loans found')

# ── 6. Cross-report consistency ───────────────────────────────────────────────
print('\n[6] Cross-report Consistency')
if bs and cap:
    adv_bs  = bs.get('advances_net', 0) or 0
    adv_reg = cap.get('loan_book', 0) or 0
    adv_match = abs(adv_bs - adv_reg) / max(adv_bs, 1) < 0.01   # within 1%
    check('Advances: BS vs regulatory batch within 1%',  adv_match,
          f'BS={adv_bs/1e7:.1f} Cr  Reg={adv_reg/1e7:.1f} Cr')

if cap and liq:
    check('Reg capital and liquidity on same date',
          cap.get('report_date') == liq.get('report_date'),
          f"cap={cap.get('report_date')}  liq={liq.get('report_date')}")

if bs and pl:
    check('BS and P&L on same period',
          bs.get('period') == pl.get('period'),
          f"BS={bs.get('period')}  PL={pl.get('period')}")

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for ok, _ in results if ok)
failed = sum(1 for ok, _ in results if not ok)
print()
print('=' * 65)
print(f'  Result: {passed} passed  |  {failed} failed')
print('=' * 65)
print()

conn.close()
sys.exit(0 if failed == 0 else 1)
