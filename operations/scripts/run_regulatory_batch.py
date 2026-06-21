"""
run_regulatory_batch.py
───────────────────────
The daily Regulatory Reporting batch. For every bank in bank.db it computes the
Basel III / RBI returns via backend.regulatory_engine and persists them:

    reg_capital_reports    — one row per bank per run (CRAR, RWA, Tier 1/2 …)
    reg_liquidity_reports  — one row per bank per run (LCR, NSFR, CRR, SLR …)
    reg_client_exposures   — one row per loan per run (EAD, RWA, provision …)
    regulatory_compliance  — refreshed compliance status per RBI requirement

Tables are created on first run (CREATE TABLE IF NOT EXISTS) so a fresh GCP
deployment self-initialises. Re-running on the same calendar date replaces that
date's rows (idempotent), so the scheduler can fire daily without piling up
duplicates while still retaining history across days.

Invoked three ways:
    • python operations/scripts/run_regulatory_batch.py      (manual / cron)
    • APScheduler daily job in app.py
    • POST /regulatory/api/run-batch                          (admin trigger)
"""

import os
import sys
import json
import sqlite3
from datetime import date, datetime, timedelta

# allow "python operations/scripts/run_regulatory_batch.py" from repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.regulatory_engine import (
    bank_capital_report, bank_liquidity_report, compliance_assessment,
    RBI_THRESHOLDS,
)

DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS reg_capital_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id TEXT, report_date TEXT,
    credit_rwa REAL, operational_rwa REAL, market_rwa REAL, total_rwa REAL,
    tier1_capital REAL, tier2_capital REAL, total_capital REAL,
    total_assets REAL, loan_book REAL, deposits REAL, rwa_density REAL,
    car REAL, tier1_ratio REAL, cet1_ratio REAL, leverage_ratio REAL,
    car_status TEXT, tier1_status TEXT, cet1_status TEXT, leverage_status TEXT,
    total_provisions REAL, num_loans INTEGER, num_npa INTEGER,
    generated_at TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS reg_liquidity_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id TEXT, report_date TEXT,
    retail_deposits REAL, wholesale_funding REAL, total_funding REAL, ndtl REAL,
    hqla REAL, net_outflows_30d REAL, lcr REAL, asf REAL, rsf REAL, nsfr REAL,
    crr_ratio REAL, slr_ratio REAL,
    lcr_status TEXT, nsfr_status TEXT, crr_status TEXT, slr_status TEXT,
    generated_at TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS reg_client_exposures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id TEXT, report_date TEXT, cid TEXT, customer_name TEXT,
    loan_id TEXT, loan_type TEXT, classification TEXT,
    ead REAL, pd REAL, lgd REAL, risk_weight REAL, rwa REAL,
    capital_charge REAL, expected_loss REAL, provision REAL,
    generated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cap_bank_date ON reg_capital_reports(bank_id, report_date);
CREATE INDEX IF NOT EXISTS idx_liq_bank_date ON reg_liquidity_reports(bank_id, report_date);
CREATE INDEX IF NOT EXISTS idx_exp_bank_date ON reg_client_exposures(bank_id, report_date);
CREATE INDEX IF NOT EXISTS idx_exp_cid ON reg_client_exposures(cid);
"""

_CAP_COLS = ['bank_id', 'report_date', 'credit_rwa', 'operational_rwa', 'market_rwa',
             'total_rwa', 'tier1_capital', 'tier2_capital', 'total_capital',
             'total_assets', 'loan_book', 'deposits', 'rwa_density', 'car',
             'tier1_ratio', 'cet1_ratio', 'leverage_ratio', 'car_status',
             'tier1_status', 'cet1_status', 'leverage_status', 'total_provisions',
             'num_loans', 'num_npa']

_LIQ_COLS = ['bank_id', 'report_date', 'retail_deposits', 'wholesale_funding',
             'total_funding', 'ndtl', 'hqla', 'net_outflows_30d', 'lcr', 'asf',
             'rsf', 'nsfr', 'crr_ratio', 'slr_ratio', 'lcr_status', 'nsfr_status',
             'crr_status', 'slr_status']

_EXP_COLS = ['cid', 'customer_name', 'loan_id', 'loan_type', 'classification',
             'ead', 'pd', 'lgd', 'risk_weight', 'rwa', 'capital_charge',
             'expected_loss', 'provision']


def _read_sim_date():
    import json as _json
    clk = os.path.join(_REPO_ROOT, 'simulation_clock.json')
    try:
        return _json.load(open(clk))['sim_date']
    except Exception:
        return '2020-03-31'

SIM_DATE = _read_sim_date()

def run_batch(db_path=DB_PATH, report_date=None, verbose=True):
    report_date = report_date or SIM_DATE
    now = datetime.now().isoformat(timespec='seconds')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    # Ensure the balance sheet exists so capital/liquidity use real figures, not
    # proxies. Self-seeds on a fresh DB (e.g. first GCP deploy).
    try:
        n_bs = cur.execute("SELECT COUNT(*) FROM bank_balance_sheet").fetchone()[0]
    except sqlite3.OperationalError:
        n_bs = 0
    if not n_bs:
        try:
            import importlib.util
            _seed_path = os.path.join(os.path.dirname(__file__), 'seed_bank_balance_sheet.py')
            _spec = importlib.util.spec_from_file_location('seed_bank_balance_sheet', _seed_path)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _mod.seed(db_path=db_path, verbose=False)
        except Exception as e:
            if verbose:
                print(f"[warn] balance-sheet seed skipped: {e}")

    banks = [dict(r) for r in cur.execute("SELECT * FROM banks").fetchall()]
    results = []

    for bank in banks:
        bid = bank['bank_id']
        loans    = [dict(r) for r in cur.execute("SELECT * FROM loans WHERE bank_id=?", (bid,)).fetchall()]
        accounts = [dict(r) for r in cur.execute("SELECT * FROM accounts WHERE bank_id=?", (bid,)).fetchall()]
        metrics  = {r['lid']: dict(r) for r in
                    cur.execute("SELECT * FROM credit_risk_metrics WHERE bank_id=?", (bid,)).fetchall()}
        names = {r['id']: f"{r['first']} {r['last']}" for r in
                 cur.execute("SELECT id, first, last FROM customers WHERE bank_id=?", (bid,)).fetchall()}

        # Latest stored balance sheet for this bank (real capital/liquidity anchors).
        # Falls back to None → engine uses synthetic proxies (e.g. table absent).
        balance_sheet = None
        try:
            bs_row = cur.execute(
                "SELECT * FROM bank_balance_sheet WHERE bank_id=? ORDER BY as_on_date DESC LIMIT 1",
                (bid,)).fetchone()
            balance_sheet = dict(bs_row) if bs_row else None
        except sqlite3.OperationalError:
            balance_sheet = None   # table not seeded yet

        cap = bank_capital_report(bid, loans, accounts, metrics, report_date,
                                  balance_sheet=balance_sheet)
        liq = bank_liquidity_report(bid, accounts, loans, cap['total_capital'], report_date,
                                    balance_sheet=balance_sheet)
        compliance = compliance_assessment(cap, liq)

        # ── idempotent replace for this bank + date ──
        cur.execute("DELETE FROM reg_capital_reports   WHERE bank_id=? AND report_date=?", (bid, report_date))
        cur.execute("DELETE FROM reg_liquidity_reports WHERE bank_id=? AND report_date=?", (bid, report_date))
        cur.execute("DELETE FROM reg_client_exposures  WHERE bank_id=? AND report_date=?", (bid, report_date))

        cur.execute(
            "INSERT INTO reg_capital_reports ({}, generated_at, detail) VALUES ({}, ?, ?)".format(
                ', '.join(_CAP_COLS), ', '.join('?' * len(_CAP_COLS))),
            [cap[c] for c in _CAP_COLS] + [now, json.dumps(cap['assumptions'])])

        cur.execute(
            "INSERT INTO reg_liquidity_reports ({}, generated_at, detail) VALUES ({}, ?, ?)".format(
                ', '.join(_LIQ_COLS), ', '.join('?' * len(_LIQ_COLS))),
            [liq[c] for c in _LIQ_COLS] + [now, json.dumps(liq['assumptions'])])

        for e in cap['exposures']:
            # fill customer name from the bank's customer map
            e['customer_name'] = names.get(e.get('cid'), e.get('cid'))
            cur.execute(
                "INSERT INTO reg_client_exposures (bank_id, report_date, {}, generated_at) "
                "VALUES (?, ?, {}, ?)".format(
                    ', '.join(_EXP_COLS), ', '.join('?' * len(_EXP_COLS))),
                [bid, report_date] + [e[c] for c in _EXP_COLS] + [now])

        # ── refresh regulatory_compliance for this bank ──
        cur.execute("DELETE FROM regulatory_compliance WHERE bank_id=?", (bid,))
        next_audit = (date.fromisoformat(report_date) + timedelta(days=90)).isoformat()
        seen_req = {}
        for f in compliance:
            # collapse multiple metrics under one requirement to worst status
            rank = {'Compliant': 0, 'Monitored': 0, 'Watch': 1, 'Breach': 2}
            rid = f['requirement_id']
            prev = seen_req.get(rid)
            if prev is None or rank.get(f['status'], 0) > rank.get(prev['compliance_status'], 0):
                seen_req[rid] = {
                    'compliance_status': f['status'],
                    'notes': "{}: {} (min {})".format(f['metric'], f['actual'], f['required']),
                }
        for rid, v in seen_req.items():
            cur.execute(
                "INSERT INTO regulatory_compliance "
                "(bank_id, requirement_id, compliance_status, last_audit_date, next_audit_date, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (bid, rid, v['compliance_status'], report_date, next_audit, v['notes']))

        results.append({'bank': bank['bank_name'], 'capital': cap, 'liquidity': liq})

    conn.commit()
    conn.close()

    if verbose:
        _print_summary(results, report_date)
    return results


def _print_summary(results, report_date):
    print("=" * 78)
    print("REGULATORY BATCH  —  report_date {}".format(report_date))
    print("=" * 78)
    print("RBI minimums: CAR>={car_min}%  CET1>={cet1_min}%  LCR>={lcr_min}%  "
          "NSFR>={nsfr_min}%  CRR>={crr_min}%  SLR>={slr_min}%".format(**RBI_THRESHOLDS))
    for r in results:
        c, l = r['capital'], r['liquidity']
        print("\n--- {} ({}) ---".format(r['bank'], c['bank_id']))
        print("  Loan book Rs {:,.0f} | Deposits Rs {:,.0f} | Total RWA Rs {:,.0f} "
              "(credit {:,.0f} + op {:,.0f})".format(
                  c['loan_book'], c['deposits'], c['total_rwa'], c['credit_rwa'], c['operational_rwa']))
        print("  CAR {}% [{}]   CET1 {}% [{}]   Tier1 {}% [{}]   Leverage {}% [{}]".format(
            c['car'], c['car_status'], c['cet1_ratio'], c['cet1_status'],
            c['tier1_ratio'], c['tier1_status'], c['leverage_ratio'], c['leverage_status']))
        print("  LCR {}% [{}]   NSFR {}% [{}]   CRR {}% [{}]   SLR {}% [{}]".format(
            l['lcr'], l['lcr_status'], l['nsfr'], l['nsfr_status'],
            l['crr_ratio'], l['crr_status'], l['slr_ratio'], l['slr_status']))
        print("  NPAs {}/{}  provisions Rs {:,.0f}".format(
            c['num_npa'], c['num_loans'], c['total_provisions']))
    print("\nDone.")


if __name__ == '__main__':
    run_batch()
