"""
alm_engine.py
─────────────
Asset-Liability Management (ALM) - the ALCO function: bucket assets and
liabilities by remaining time-to-maturity (a simplified RBI Structural
Liquidity Statement), and make an explicit, auditable funding decision for
every new loan instead of silently bumping advances_net and leaving the
balance sheet unbalanced until the next full reseed.

Assets (loans) already carry real per-loan maturity dates from origination.
Liabilities never did - Fixed Deposits had no tenor at all, only open_date.
This module adds that (accounts.maturity_date, FD-only) and treats Savings/
Current as on-demand, split behaviourally into a "core" (sticky, long-tenor)
and "volatile" (near-term) portion rather than assuming either 100% overnight
or 100% stable - the standard ALM simplification real banks use in the
absence of a full historical withdrawal study.

Borrowings have no per-instrument maturity anywhere in this schema (a single
aggregate number) - treated as one blended 6-12 month bucket rather than
inventing fake instrument-level detail for data that doesn't exist.
"""
import os
import random
import sqlite3
from datetime import date, datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MATURITY_BUCKETS = ['0-3M', '3-6M', '6-12M', '1-3Y', '3-5Y', '5Y+']

# Behavioral CASA split - what fraction of Savings/Current is assumed sticky
# ("core", bucketed far out) vs. likely to move near-term ("volatile").
CASA_CORE_SHARE = 0.90
CASA_VOLATILE_SHARE = 0.10

# RBI's real SLR floor (see backend/regulatory_engine.py's SLR_HOLDING_PROXY,
# reused here rather than re-defining it) - investments above this floor are
# genuine "spare" liquidity a bank can lend out without raising new liabilities.
SLR_HOLDING_PROXY = 0.205

# ALCO policy ceiling - the ALM committee's own risk-appetite limit on how
# loan-heavy the book gets before deposit funding is judged too risky and
# wholesale borrowing is used instead.
CD_RATIO_CEILING = 90.0

# Realistic Fixed Deposit tenor distribution (years, weight) used only to
# backfill pre-existing FDs that predate this feature - new FDs should pick
# a tenor the same way going forward.
FD_TENOR_WEIGHTS = [(1, 0.35), (2, 0.30), (3, 0.20), (5, 0.15)]

SCHEMA = """
CREATE TABLE IF NOT EXISTS alm_funding_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id TEXT, period TEXT, loan_id TEXT, amount REAL,
    source TEXT, reason TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_alm_events_bank ON alm_funding_events(bank_id, period);
"""

_MIGRATIONS = [
    "ALTER TABLE accounts ADD COLUMN maturity_date TEXT",
]


def _ensure_schema(conn):
    conn.executescript(SCHEMA)
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists


def pick_fd_tenor_years(rng=None):
    """Weighted-random FD tenor in years, per FD_TENOR_WEIGHTS."""
    rng = rng or random
    years, weights = zip(*FD_TENOR_WEIGHTS)
    return rng.choices(years, weights=weights, k=1)[0]


def backfill_fd_maturity(conn, sim_date=None):
    """One-time backfill: assign a maturity_date to every pre-existing Fixed
    Deposit account that doesn't have one yet (open_date + a realistic
    tenor). Savings/Current accounts are intentionally left NULL - they're
    on-demand, handled via the CASA behavioral split instead of a stored date.
    Idempotent - only touches rows where maturity_date IS NULL, safe to call
    on every request.
    """
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT id, open_date FROM accounts WHERE type='Fixed Deposit' AND maturity_date IS NULL"
    ).fetchall()
    if not rows:
        return 0
    rng = random.Random(42)  # deterministic - reruns don't reshuffle existing FDs
    updated = 0
    for aid, open_date_str in rows:
        years = pick_fd_tenor_years(rng)
        try:
            od = date.fromisoformat(open_date_str)
            maturity = date(od.year + years, od.month, min(od.day, 28)).isoformat()
        except Exception:
            maturity = sim_date or datetime.now().date().isoformat()
        conn.execute("UPDATE accounts SET maturity_date=? WHERE id=?", (maturity, aid))
        updated += 1
    conn.commit()
    return updated


def renew_matured_fds(conn, sim_date=None):
    """Roll forward maturity_date for Fixed Deposits that have already
    matured - real FDs auto-renew onto a fresh term of the same tenor
    unless the customer opts out (the default bank convention), so a
    maturity_date sitting in the past just means it was never rolled
    forward, not that the deposit lapsed. accounts.status is left
    untouched - it's already 'Active' and no code branches on it for FD
    lifecycle, only maturity_date feeds the ALM bucketing.
    Idempotent - only touches rows whose maturity_date is <= as_of, safe
    to call on every request (mirrors backfill_fd_maturity above).
    """
    _ensure_schema(conn)
    as_of = date.fromisoformat(sim_date) if sim_date else datetime.now().date()
    rows = conn.execute(
        "SELECT id, open_date, maturity_date FROM accounts "
        "WHERE type='Fixed Deposit' AND maturity_date IS NOT NULL AND maturity_date < ?",
        (as_of.isoformat(),)
    ).fetchall()
    if not rows:
        return 0
    renewed = 0
    for aid, open_date_str, maturity_str in rows:
        od = date.fromisoformat(open_date_str)
        mat = date.fromisoformat(maturity_str[:10])
        # infer the FD's own original tenor from its current term rather
        # than re-rolling a new random one, so renewal is deterministic
        years = max(round(((mat.year - od.year) * 12 + (mat.month - od.month)) / 12), 1)
        while mat < as_of:
            mat = date(mat.year + years, mat.month, min(mat.day, 28))
        conn.execute("UPDATE accounts SET maturity_date=? WHERE id=?", (mat.isoformat(), aid))
        renewed += 1
    conn.commit()
    return renewed


def bucket_for(as_of_date, target_date):
    """Which maturity bucket target_date falls in, relative to as_of_date.
    Already-matured/overdue dates fall into the nearest (0-3M) bucket."""
    if not target_date:
        return None
    try:
        d0 = date.fromisoformat(as_of_date)
        d1 = date.fromisoformat(target_date[:10])
    except Exception:
        return None
    days = (d1 - d0).days
    if days <= 90:
        return '0-3M'
    if days <= 180:
        return '3-6M'
    if days <= 365:
        return '6-12M'
    if days <= 365 * 3:
        return '1-3Y'
    if days <= 365 * 5:
        return '3-5Y'
    return '5Y+'


def structural_liquidity_statement(conn, bank_id, as_of_date, period):
    """Simplified RBI Structural Liquidity Statement: assets and liabilities
    bucketed by remaining maturity, with the running (cumulative) gap and a
    Green/Amber/Red compliance flag on the near-term (0-3M) cumulative
    mismatch - a coarser analogue of RBI's actual 1-14/15-28 day ceilings,
    adapted to this platform's 6-bucket ladder.

    bank_id=None means consolidated (all banks).
    """
    _ensure_schema(conn)
    buckets = {b: {'assets': 0.0, 'liabilities': 0.0} for b in MATURITY_BUCKETS}

    loan_filter = "WHERE bank_id=?" if bank_id else ""
    loan_params = (bank_id,) if bank_id else ()
    for maturity, outstanding in conn.execute(
            f"SELECT maturity, outstanding FROM loans {loan_filter}", loan_params).fetchall():
        b = bucket_for(as_of_date, maturity)
        if b:
            buckets[b]['assets'] += outstanding or 0.0

    fd_filter = "WHERE type='Fixed Deposit'" + (" AND bank_id=?" if bank_id else "")
    fd_params = (bank_id,) if bank_id else ()
    for maturity_date, balance in conn.execute(
            f"SELECT maturity_date, balance FROM accounts {fd_filter}", fd_params).fetchall():
        b = bucket_for(as_of_date, maturity_date) if maturity_date else '1-3Y'
        buckets[b]['liabilities'] += balance or 0.0

    casa_filter = "WHERE type IN ('Savings','Current')" + (" AND bank_id=?" if bank_id else "")
    casa_params = (bank_id,) if bank_id else ()
    casa = conn.execute(
        f"SELECT COALESCE(SUM(balance),0) FROM accounts {casa_filter}", casa_params).fetchone()[0]
    buckets['0-3M']['liabilities'] += casa * CASA_VOLATILE_SHARE
    buckets['3-5Y']['liabilities'] += casa * CASA_CORE_SHARE

    # Remaining balance-sheet lines with no per-instrument maturity data of
    # their own - bucketed by standard ALM convention so the ladder
    # reconciles to the bank's actual Total Assets = Total Liabilities+Capital
    # (verified elsewhere this session to balance to the paisa) rather than
    # silently covering only the loan-vs-deposit subset:
    #   - cash/interbank: on-demand -> nearest bucket
    #   - investments (SLR/HQLA securities), borrowings: no instrument-level
    #     maturity in this schema -> one blended medium-term bucket each
    #   - fixed/intangible/other assets, capital, other liabilities: no
    #     maturity concept at all (physical/intangible/permanent) -> longest
    #     bucket, the standard ALM treatment for non-rate-sensitive items
    bsh_filter = "WHERE period=?" + (" AND bank_id=?" if bank_id else "")
    bsh_params = (period, bank_id) if bank_id else (period,)
    bsh_cols = ("cash_with_rbi", "balances_with_banks", "investments", "borrowings",
                "fixed_assets", "intangible_assets", "other_assets",
                "equity_capital", "reserves_surplus", "other_liabilities")
    bsh_row = conn.execute(
        f"SELECT {','.join('SUM(%s)' % c for c in bsh_cols)} FROM bank_balance_sheet {bsh_filter}",
        bsh_params
    ).fetchone()
    if bsh_row:
        (cash, interbank, investments, borrowings, fixed_a, intangible_a, other_a,
         equity, reserves, other_l) = [v or 0.0 for v in bsh_row]
        buckets['0-3M']['assets'] += cash + interbank
        buckets['3-5Y']['assets'] += investments
        buckets['5Y+']['assets'] += fixed_a + intangible_a + other_a
        buckets['6-12M']['liabilities'] += borrowings
        buckets['5Y+']['liabilities'] += equity + reserves
        buckets['0-3M']['liabilities'] += other_l

    total_assets = sum(v['assets'] for v in buckets.values())
    rows = []
    cum_gap = 0.0
    for b in MATURITY_BUCKETS:
        a, l = buckets[b]['assets'], buckets[b]['liabilities']
        gap = a - l
        cum_gap += gap
        rows.append({'bucket': b, 'assets': round(a, 2), 'liabilities': round(l, 2),
                     'gap': round(gap, 2), 'cumulative_gap': round(cum_gap, 2)})

    near_term_gap_pct = (rows[0]['cumulative_gap'] / total_assets * 100) if total_assets else 0.0
    if near_term_gap_pct >= -20.0:
        compliance_status = 'Green'
    elif near_term_gap_pct >= -30.0:
        compliance_status = 'Amber'
    else:
        compliance_status = 'Red'

    return {
        'bank_id': bank_id or 'CONSOLIDATED', 'as_of_date': as_of_date, 'period': period,
        'buckets': rows, 'total_assets': round(total_assets, 2),
        'near_term_gap_pct': round(near_term_gap_pct, 1),
        'compliance_status': compliance_status, 'compliance_threshold_pct': -20.0,
    }


def decide_funding(conn, bank_id, period, amount, loan_id=None, actor='ALCO-AUTO'):
    """The ALCO funding-waterfall decision for a new loan - replaces the old
    silent advances_net-only bump. Draws down spare SLR-surplus investments
    first (no new liability raised), else funds from incremental deposits
    (cheapest real liability) unless that would breach the CD-ratio ceiling,
    else falls back to borrowings. Updates the balance sheet and advances_net
    together so the sheet stays genuinely balanced at the moment of booking,
    and logs the decision to alm_funding_events for audit.

    Returns {'source': 'INVESTMENTS'|'DEPOSITS'|'BORROWINGS'|'NONE', 'reason': str}.
    """
    _ensure_schema(conn)
    row = conn.execute(
        "SELECT advances_net, investments, deposits_demand, deposits_savings, "
        "deposits_term, borrowings FROM bank_balance_sheet WHERE bank_id=? AND period=?",
        (bank_id, period)).fetchone()

    if not row:
        # No balance-sheet row for this period yet - fall back to the old
        # asset-only bump so booking never hard-fails; nothing to fund from.
        conn.execute(
            "UPDATE bank_balance_sheet SET advances_net = advances_net + ? "
            "WHERE bank_id=? AND period=?", (amount, bank_id, period))
        source, reason = 'NONE', 'No balance_sheet row for this period - asset-only fallback'
    else:
        advances_net, investments, dep_demand, dep_savings, dep_term, borrowings = \
            [v or 0.0 for v in row]
        deposits_total = dep_demand + dep_savings + dep_term
        slr_floor = SLR_HOLDING_PROXY * deposits_total
        surplus = investments - slr_floor
        cd_if_deposit_funded = ((advances_net + amount) / (deposits_total + amount) * 100
                                 if (deposits_total + amount) else 999.0)

        if surplus > amount:
            conn.execute(
                "UPDATE bank_balance_sheet SET investments = investments - ?, "
                "advances_net = advances_net + ? WHERE bank_id=? AND period=?",
                (amount, amount, bank_id, period))
            source = 'INVESTMENTS'
            reason = f'Drew down SLR-surplus investments (surplus Rs{surplus:,.0f}) - no new liability raised'
        elif cd_if_deposit_funded <= CD_RATIO_CEILING:
            conn.execute(
                "UPDATE bank_balance_sheet SET deposits_savings = deposits_savings + ?, "
                "advances_net = advances_net + ? WHERE bank_id=? AND period=?",
                (amount, amount, bank_id, period))
            source = 'DEPOSITS'
            reason = f'Funded from incremental deposit growth (resulting CD ratio {cd_if_deposit_funded:.1f}%)'
        else:
            conn.execute(
                "UPDATE bank_balance_sheet SET borrowings = borrowings + ?, "
                "advances_net = advances_net + ? WHERE bank_id=? AND period=?",
                (amount, amount, bank_id, period))
            source = 'BORROWINGS'
            reason = (f'Deposit funding would breach the {CD_RATIO_CEILING:.0f}% ALCO CD ceiling '
                      f'({cd_if_deposit_funded:.1f}%) - drew wholesale borrowings instead')

    conn.execute(
        "INSERT INTO alm_funding_events (bank_id, period, loan_id, amount, source, reason, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (bank_id, period, loan_id, amount, source, reason, datetime.now().isoformat(timespec='seconds')))
    return {'source': source, 'reason': reason}


def recent_funding_events(conn, bank_id, limit=20):
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT period, loan_id, amount, source, reason, created_at FROM alm_funding_events "
        "WHERE bank_id=? ORDER BY id DESC LIMIT ?", (bank_id, limit)).fetchall()
    cols = ['period', 'loan_id', 'amount', 'source', 'reason', 'created_at']
    return [dict(zip(cols, r)) for r in rows]
