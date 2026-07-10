"""
resolve_loan_lifecycle.py
──────────────────────────
Idempotent lifecycle-consistency pass over `loans`. Fixes two problems
found in the ledger:

1. Stored `maturity` drifting from `disbursed + tenure` (a day-of-month
   rounding bug in seed_bulk_customers.py, now fixed there too) — this
   pass recomputes `maturity` for every loan from its own disbursed/tenure.

2. Loans whose (corrected) maturity date has already passed while
   `status` is still 'Active'. These loans' EMI transaction history was
   only ever seeded for a fixed window (18 months per
   seed_global_transactions.py / until "today" at seed time in
   seed_bulk_customers.py), so payments appear to stop long before the
   loan's real maturity even for a performing borrower. Resolve each one
   from its actual EMI payment ratio rather than assuming default:
     - loan_classification already NPA/Doubtful/Loss  -> Written-Off
     - EMI payment ratio >= 0.85 over its observed life -> Closed
       (treated as fully repaid — the gap is a data-seeding artifact,
       not evidence of default)
     - otherwise (sparse/no payment history, not already flagged)
                                                        -> Written-Off

Safe to rerun anytime (e.g. periodically, or after fast-forwarding
simulation_clock.json) — loans already resolved are left untouched.

Run:
    python resolve_loan_lifecycle.py [--dry-run]
"""

import os
import sqlite3
import sys
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')

PAID_RATIO_CLOSED_THRESHOLD = 0.85


def add_months(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, min(d.day, 28))


def fix_maturity_dates(conn, dry_run):
    cur = conn.cursor()
    cur.execute("SELECT id, disbursed, tenure, maturity FROM loans")
    rows = cur.fetchall()

    fixed = 0
    for lid, disbursed, tenure, maturity in rows:
        disb = datetime.strptime(disbursed, '%Y-%m-%d').date()
        expected = add_months(disb, tenure)
        stored = datetime.strptime(maturity, '%Y-%m-%d').date()
        if abs((stored - expected).days) > 3:
            fixed += 1
            if not dry_run:
                cur.execute("UPDATE loans SET maturity = ? WHERE id = ?",
                            (expected.isoformat(), lid))

    print(f"[maturity] {'would fix' if dry_run else 'fixed'} {fixed} / {len(rows)} loans "
          f"(stored maturity != disbursed + tenure)")
    return fixed


def emi_payment_ratio(cursor, loan_id, cid, disbursed, tenure, maturity):
    """
    Ratio of EMI-tagged transactions found vs. EMIs due, measured over the
    loan's *observed* window (disbursement -> its own last recorded EMI
    payment), not all the way to maturity/today.

    Why: transaction history for these loans was only ever seeded for a
    fixed window post-disbursement (18 months / "as of" seed-script run
    time) — payments stopping there is a data-generation artifact, not
    necessarily a sign the borrower defaulted. Measuring against maturity
    would flag every one of these loans as near-total non-payment, which
    is a seeding-window effect, not a real repayment signal. Measuring
    against the loan's own last paid month instead reveals whether it was
    paying *consistently* while the seed data covered it (few/no gaps ->
    performing loan, data just ran out) vs. genuinely spotty even within
    the observed window (real delinquency signal).
    """
    disb = datetime.strptime(disbursed, '%Y-%m-%d').date()

    cursor.execute("""
        SELECT MAX(t.date), COUNT(DISTINCT strftime('%Y-%m', t.date))
        FROM transactions t
        JOIN accounts a ON a.id = t.aid
        WHERE a.cid = ? AND t.desc LIKE '%EMI Payment%'
    """, (cid,))
    last_emi_str, paid = cursor.fetchone()

    if not last_emi_str:
        return 0.0, 0, 0

    horizon = datetime.strptime(last_emi_str, '%Y-%m-%d').date()

    y, m = disb.year, disb.month + 1
    if m > 12:
        m, y = 1, y + 1

    expected = 0
    for _ in range(tenure):
        if date(y, m, 1) > horizon:
            break
        expected += 1
        m += 1
        if m > 12:
            m, y = 1, y + 1

    if expected == 0:
        return 1.0, paid, 0

    return min(paid, expected) / expected, paid, expected


def resolve_matured_active_loans(conn, dry_run):
    cur = conn.cursor()
    today_str = date.today().isoformat()

    cur.execute("""
        SELECT id, cid, disbursed, tenure, maturity, loan_classification
        FROM loans
        WHERE status = 'Active' AND maturity < ?
    """, (today_str,))
    loans = cur.fetchall()

    closed = written_off = skipped = 0
    for lid, cid, disbursed, tenure, maturity, classification in loans:
        ratio, paid, expected = emi_payment_ratio(cur, lid, cid, disbursed, tenure, maturity)

        if classification in ('NPA', 'Doubtful', 'Loss'):
            new_status, new_class, reason = 'Written-Off', 'Written-Off', f'already {classification}'
        elif paid == 0 and expected == 0:
            # No EMI transactions were ever recorded for this customer at all -
            # a separate seeding gap (loan row created without matching account
            # transactions), not evidence of default. Absence of data is not a
            # signal either way, so leave the loan's status untouched.
            print(f"  {lid:<16} -> SKIPPED      (no transaction data at all - can't determine outcome)")
            skipped += 1
            continue
        elif ratio >= PAID_RATIO_CLOSED_THRESHOLD:
            new_status, new_class, reason = 'Closed', 'Standard', f'paid {paid}/{expected} EMIs ({ratio:.0%})'
        else:
            new_status, new_class, reason = 'Written-Off', 'Written-Off', f'only paid {paid}/{expected} EMIs ({ratio:.0%})'

        if new_status == 'Closed':
            closed += 1
        else:
            written_off += 1

        print(f"  {lid:<16} -> {new_status:<12} ({reason})")

        if dry_run:
            continue

        cur.execute("""
            SELECT MAX(t.date) FROM transactions t
            JOIN accounts a ON a.id = t.aid
            WHERE a.cid = ? AND t.desc LIKE '%EMI Payment%'
        """, (cid,))
        last_emi = cur.fetchone()[0]

        if new_status == 'Closed':
            cur.execute("""
                UPDATE loans
                SET status = 'Closed', loan_classification = 'Standard',
                    outstanding = 0, days_past_due = 0,
                    last_payment_date = COALESCE(?, last_payment_date)
                WHERE id = ?
            """, (last_emi, lid))
        else:
            days_overdue = (date.today() - datetime.strptime(maturity, '%Y-%m-%d').date()).days
            cur.execute("""
                UPDATE loans
                SET status = 'Written-Off', loan_classification = 'Written-Off',
                    days_past_due = ?,
                    last_payment_date = COALESCE(?, last_payment_date)
                WHERE id = ?
            """, (max(days_overdue, 0), last_emi, lid))
            cur.execute("""
                UPDATE credit_risk_metrics SET npa_flag = 1 WHERE lid = ?
            """, (lid,))

    print()
    print(f"[lifecycle] {len(loans)} matured-but-Active loans checked: "
          f"{closed} -> Closed, {written_off} -> Written-Off, {skipped} skipped (no data)"
          f"{' (dry run — no changes written)' if dry_run else ''}")


def main():
    dry_run = '--dry-run' in sys.argv
    conn = sqlite3.connect(DB_PATH)

    print("=" * 70)
    print(f"resolve_loan_lifecycle.py — {date.today().isoformat()}"
          f"{'  [DRY RUN]' if dry_run else ''}")
    print("=" * 70)

    fix_maturity_dates(conn, dry_run)
    print()
    resolve_matured_active_loans(conn, dry_run)

    if not dry_run:
        conn.commit()
    conn.close()
    print("=" * 70)


if __name__ == "__main__":
    main()
