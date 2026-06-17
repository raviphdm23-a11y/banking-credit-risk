"""
seed_bank_profit_loss.py
────────────────────────
Create and populate `bank_profit_loss` — a per-bank, per-period Profit & Loss
(income statement, RBI Form B style) for the Financial Reporting department.

Anchored to live data so it reconciles with the balance sheet:
    interest_on_advances  = SUM(loan.outstanding * loan.rate)   [live, FY2025]
    interest_on_investments, on_deposits, on_borrowings         [from balance sheet]
    other_income, opex, provisions                              [realistic ratios]

Requires `bank_balance_sheet` (it reads the period rows); if that table is empty
it seeds it first via seed_bank_balance_sheet. Prior period (FY2024) is scaled
to give a trend. Idempotent (INSERT OR REPLACE on bank_id+period).

Run:  python operations/scripts/seed_bank_profit_loss.py
"""

import os
import sqlite3
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_profit_loss (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id TEXT NOT NULL,
    period TEXT NOT NULL,
    from_date TEXT, to_date TEXT,
    currency TEXT DEFAULT 'INR', unit TEXT DEFAULT 'INR',
    -- Income
    interest_on_advances REAL, interest_on_investments REAL, interest_earned REAL,
    other_income REAL, total_income REAL,
    -- Expenses
    interest_on_deposits REAL, interest_on_borrowings REAL, interest_expended REAL,
    employee_cost REAL, other_opex REAL, operating_expenses REAL,
    -- Subtotals
    net_interest_income REAL, operating_profit REAL,
    provisions_contingencies REAL, profit_before_tax REAL,
    tax_expense REAL, profit_after_tax REAL,
    source TEXT, generated_at TEXT,
    UNIQUE(bank_id, period)
);
CREATE INDEX IF NOT EXISTS idx_bpl_bank ON bank_profit_loss(bank_id, period);
"""

_COLS = ['bank_id', 'period', 'from_date', 'to_date', 'currency', 'unit',
         'interest_on_advances', 'interest_on_investments', 'interest_earned',
         'other_income', 'total_income',
         'interest_on_deposits', 'interest_on_borrowings', 'interest_expended',
         'employee_cost', 'other_opex', 'operating_expenses',
         'net_interest_income', 'operating_profit',
         'provisions_contingencies', 'profit_before_tax', 'tax_expense',
         'profit_after_tax', 'source', 'generated_at']

# Modelling assumptions (yields/costs/ratios) — disclosed in the report.
INVESTMENT_YIELD = 0.070
DEPOSIT_COST     = 0.045
BORROWING_COST   = 0.0725
OTHER_INCOME_PCT = 0.011     # fee/treasury income as % of total assets
COST_INCOME      = 0.45      # operating expenses / (NII + other income)
EMPLOYEE_SHARE   = 0.55      # employee cost as share of opex
CREDIT_COST      = 0.010     # provisions as % of net advances
TAX_RATE         = 0.25


def _bs_period(cur, bank_id, period):
    r = cur.execute("SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?",
                    (bank_id, period)).fetchone()
    return dict(r) if r else None


def seed(db_path=DB_PATH, verbose=True):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    # Ensure the balance sheet exists (P&L is anchored to it).
    try:
        n_bs = cur.execute("SELECT COUNT(*) FROM bank_balance_sheet").fetchone()[0]
    except sqlite3.OperationalError:
        n_bs = 0
    if not n_bs:
        import importlib.util
        p = os.path.join(os.path.dirname(__file__), 'seed_bank_balance_sheet.py')
        spec = importlib.util.spec_from_file_location('seed_bank_balance_sheet', p)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.seed(db_path=db_path, verbose=False)

    banks = [dict(r) for r in cur.execute("SELECT bank_id FROM banks").fetchall()]
    periods = [('FY2024', '2023-04-01', '2024-03-31', 0.88),
               ('FY2025', '2024-04-01', '2025-03-31', 1.00)]

    rows = []
    for b in banks:
        bid = b['bank_id']
        live_int_adv = cur.execute(
            "SELECT COALESCE(SUM(outstanding * rate / 100.0), 0) FROM loans WHERE bank_id=?",
            (bid,)).fetchone()[0]
        # Foreign group banks (no loan book) are seeded by seed_global.py.
        has_loans = cur.execute("SELECT COUNT(*) FROM loans WHERE bank_id=?", (bid,)).fetchone()[0]
        if not has_loans:
            continue
        for period, fdt, tdt, scale in periods:
            bs = _bs_period(cur, bid, period)
            if not bs:
                continue
            adv = float(bs['advances_net'])
            inv = float(bs['investments'])
            dep = sum(float(bs[k]) for k in ('deposits_demand', 'deposits_savings', 'deposits_term'))
            bor = float(bs['borrowings'])
            ta = sum(float(bs[k]) for k in ('cash_with_rbi', 'balances_with_banks',
                                            'investments', 'advances_net', 'fixed_assets', 'other_assets'))

            interest_on_advances    = live_int_adv * scale
            interest_on_investments = inv * INVESTMENT_YIELD
            interest_earned         = interest_on_advances + interest_on_investments
            interest_on_deposits    = dep * DEPOSIT_COST
            interest_on_borrowings  = bor * BORROWING_COST
            interest_expended       = interest_on_deposits + interest_on_borrowings
            nii        = interest_earned - interest_expended
            other_income = ta * OTHER_INCOME_PCT
            total_income = interest_earned + other_income
            opex = COST_INCOME * (nii + other_income)
            employee_cost = opex * EMPLOYEE_SHARE
            other_opex    = opex - employee_cost
            operating_profit = nii + other_income - opex
            provisions = adv * CREDIT_COST
            pbt = operating_profit - provisions
            tax = max(0.0, pbt) * TAX_RATE
            pat = pbt - tax

            rnd = lambda x: round(float(x), 2)
            rows.append({
                'bank_id': bid, 'period': period, 'from_date': fdt, 'to_date': tdt,
                'currency': 'INR', 'unit': 'INR',
                'interest_on_advances': rnd(interest_on_advances),
                'interest_on_investments': rnd(interest_on_investments),
                'interest_earned': rnd(interest_earned),
                'other_income': rnd(other_income), 'total_income': rnd(total_income),
                'interest_on_deposits': rnd(interest_on_deposits),
                'interest_on_borrowings': rnd(interest_on_borrowings),
                'interest_expended': rnd(interest_expended),
                'employee_cost': rnd(employee_cost), 'other_opex': rnd(other_opex),
                'operating_expenses': rnd(opex),
                'net_interest_income': rnd(nii), 'operating_profit': rnd(operating_profit),
                'provisions_contingencies': rnd(provisions),
                'profit_before_tax': rnd(pbt), 'tax_expense': rnd(tax),
                'profit_after_tax': rnd(pat),
                'source': 'live-anchored (interest on advances from loan book; rest from balance sheet)',
                'generated_at': datetime.now().isoformat(timespec='seconds'),
            })

    for r in rows:
        cur.execute(
            "INSERT OR REPLACE INTO bank_profit_loss ({}) VALUES ({})".format(
                ', '.join(_COLS), ', '.join('?' * len(_COLS))),
            [r[c] for c in _COLS])
    conn.commit()

    if verbose:
        for r in rows:
            print(f"{r['bank_id']} {r['period']}: NII Rs {r['net_interest_income']:,.0f}  "
                  f"OpProfit Rs {r['operating_profit']:,.0f}  PBT Rs {r['profit_before_tax']:,.0f}  "
                  f"PAT Rs {r['profit_after_tax']:,.0f}")
    conn.close()
    return rows


if __name__ == '__main__':
    seed()
