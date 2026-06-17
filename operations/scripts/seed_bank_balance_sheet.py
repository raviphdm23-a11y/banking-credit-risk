"""
seed_bank_balance_sheet.py
──────────────────────────
Create and populate the `bank_balance_sheet` table — a periodic, RBI Schedule III
(Form A) style balance sheet per bank, keyed by (bank_id, period).

Design
------
* Static bank master data stays in `banks`; this table holds the point-in-time
  financial position, one row per bank per reporting period (so history is kept).
* Figures are stored in **raw INR** (same unit as loans/accounts elsewhere in
  bank.db) so the regulatory engine can consume them directly.
* The **latest period (FY2025)** is anchored to the live data:
      advances_net   = SUM(loans.outstanding)        for the bank
      total deposits = SUM(accounts.balance)          for the bank
  and the rest of the sheet is built around those with realistic proportions so
  that  Total Assets == Total Capital & Liabilities  and the capital base yields
  a sensible CRAR (~15-16%). A prior period (FY2024) is scaled down to give a
  visible trend; only the latest period is wired into the regulatory engine.

Idempotent: INSERT OR REPLACE on the (bank_id, period) unique key, so re-running
refreshes figures without duplicating rows. Self-creates its table on a fresh DB.

Run:  python operations/scripts/seed_bank_balance_sheet.py
"""

import os
import sys
import sqlite3
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id TEXT NOT NULL,
    period TEXT NOT NULL,
    as_on_date TEXT,
    currency TEXT DEFAULT 'INR',
    unit TEXT DEFAULT 'INR',
    -- Capital & Liabilities (RBI Schedule III, Form A)
    equity_capital REAL,
    reserves_surplus REAL,
    deposits_demand REAL,
    deposits_savings REAL,
    deposits_term REAL,
    borrowings REAL,
    other_liabilities REAL,
    -- Assets
    cash_with_rbi REAL,
    balances_with_banks REAL,
    investments REAL,
    advances_net REAL,
    fixed_assets REAL,
    other_assets REAL,
    -- Off-balance-sheet
    contingent_liabilities REAL,
    bills_for_collection REAL,
    source TEXT,
    generated_at TEXT,
    UNIQUE(bank_id, period)
);
CREATE INDEX IF NOT EXISTS idx_bbs_bank ON bank_balance_sheet(bank_id, period);
"""

_COLS = ['bank_id', 'period', 'as_on_date', 'currency', 'unit',
         'equity_capital', 'reserves_surplus',
         'deposits_demand', 'deposits_savings', 'deposits_term',
         'borrowings', 'other_liabilities',
         'cash_with_rbi', 'balances_with_banks', 'investments',
         'advances_net', 'fixed_assets', 'other_assets',
         'contingent_liabilities', 'bills_for_collection',
         'source', 'generated_at']


def _build_sheet(bank_id, period, as_on_date, advances_net, total_deposits, scale, source):
    """Construct one internally-consistent balance sheet (raw INR).

    advances_net & total_deposits are the live anchors (scaled for prior years)."""
    A = advances_net * scale
    D = total_deposits * scale

    # ── Assets ──────────────────────────────────────────────────────────────
    cash_with_rbi       = 0.050 * D            # cash with RBI ~5.0% of NDTL (CRR floor 4.5% + buffer)
    investments         = 0.27 * D             # SLR/HQLA securities book
    balances_with_banks = 0.020 * A            # money at call & short notice
    fixed_assets        = 0.012 * A
    other_assets        = 0.050 * A
    total_assets = (cash_with_rbi + balances_with_banks + investments
                    + A + fixed_assets + other_assets)

    # ── Capital base sized to a healthy CRAR (~16% of an ~0.8x-density RWA) ──
    capital_base = 0.16 * 0.80 * A
    equity_capital   = 0.20 * capital_base     # paid-up equity share capital
    reserves_surplus = capital_base - equity_capital

    # ── Deposits split (data is savings-only; present a realistic mix) ───────
    deposits_demand  = 0.12 * D
    deposits_savings = 0.48 * D
    deposits_term    = D - deposits_demand - deposits_savings

    # ── Other liabilities, then borrowings as the balancing (plug) item ──────
    other_liabilities = 0.040 * total_assets
    borrowings = total_assets - (D + capital_base + other_liabilities)
    if borrowings < 0:                         # well-funded bank → absorb into reserves
        reserves_surplus += -borrowings
        borrowings = 0.0

    # ── Off-balance-sheet ────────────────────────────────────────────────────
    contingent_liabilities = 0.60 * total_assets
    bills_for_collection   = 0.05 * total_assets

    rnd = lambda x: round(float(x), 2)
    return {
        'bank_id': bank_id, 'period': period, 'as_on_date': as_on_date,
        'currency': 'INR', 'unit': 'INR',
        'equity_capital': rnd(equity_capital), 'reserves_surplus': rnd(reserves_surplus),
        'deposits_demand': rnd(deposits_demand), 'deposits_savings': rnd(deposits_savings),
        'deposits_term': rnd(deposits_term), 'borrowings': rnd(borrowings),
        'other_liabilities': rnd(other_liabilities),
        'cash_with_rbi': rnd(cash_with_rbi), 'balances_with_banks': rnd(balances_with_banks),
        'investments': rnd(investments), 'advances_net': rnd(A),
        'fixed_assets': rnd(fixed_assets), 'other_assets': rnd(other_assets),
        'contingent_liabilities': rnd(contingent_liabilities),
        'bills_for_collection': rnd(bills_for_collection),
        'source': source, 'generated_at': datetime.now().isoformat(timespec='seconds'),
    }


def seed(db_path=DB_PATH, verbose=True):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    banks = [dict(r) for r in cur.execute("SELECT bank_id, bank_name FROM banks").fetchall()]
    # Two periods: prior FY (scaled down for a trend) and current FY (live-anchored).
    periods = [
        ('FY2024', '2024-03-31', 0.88, 'synthetic (prior year, scaled)'),
        ('FY2025', '2025-03-31', 1.00, 'live-anchored (advances=SUM loans, deposits=SUM accounts)'),
    ]

    rows = []
    for b in banks:
        bid = b['bank_id']
        advances = cur.execute(
            "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?", (bid,)).fetchone()[0]
        deposits = cur.execute(
            "SELECT COALESCE(SUM(balance),0) FROM accounts WHERE bank_id=?", (bid,)).fetchone()[0]
        # Balance-sheet-only foreign group banks (no loan/account ledger) are
        # seeded by seed_global.py — don't clobber them with zero-anchored sheets.
        if advances == 0 and deposits == 0:
            continue
        for period, as_on, scale, source in periods:
            rows.append(_build_sheet(bid, period, as_on, advances, deposits, scale, source))

    for r in rows:
        cur.execute(
            "INSERT OR REPLACE INTO bank_balance_sheet ({}) VALUES ({})".format(
                ', '.join(_COLS), ', '.join('?' * len(_COLS))),
            [r[c] for c in _COLS])

    conn.commit()

    if verbose:
        for r in rows:
            ta = (r['cash_with_rbi'] + r['balances_with_banks'] + r['investments']
                  + r['advances_net'] + r['fixed_assets'] + r['other_assets'])
            tl = (r['equity_capital'] + r['reserves_surplus'] + r['deposits_demand']
                  + r['deposits_savings'] + r['deposits_term'] + r['borrowings']
                  + r['other_liabilities'])
            print(f"{r['bank_id']} {r['period']}: assets Rs {ta:,.0f}  liab+cap Rs {tl:,.0f}  "
                  f"(diff {ta - tl:,.2f})  | advances {r['advances_net']:,.0f}  "
                  f"deposits {r['deposits_demand'] + r['deposits_savings'] + r['deposits_term']:,.0f}  "
                  f"capital {r['equity_capital'] + r['reserves_surplus']:,.0f}")
    conn.close()
    return rows


if __name__ == '__main__':
    seed()
