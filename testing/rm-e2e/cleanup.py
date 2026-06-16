"""Remove every RM case created by the Playwright suite (customer name starts
with 'PWTEST'), plus its provenance/outcome rows and generated PDF reports.
Resolves the project root two levels up from this file so it works no matter
where it's invoked from. Safe to run repeatedly."""
import os
import shutil
import sqlite3

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "bank.db")


def main():
    if not os.path.exists(DB):
        print("[cleanup] bank.db not found — nothing to do")
        return
    conn = sqlite3.connect(DB)
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT case_id FROM rm_cases WHERE customer_name LIKE 'PWTEST%'").fetchall()]
        for cid in ids:
            for table in ("rm_case_events", "rm_outcomes", "rm_cases"):
                conn.execute(f"DELETE FROM {table} WHERE case_id=?", (cid,))
            report_dir = os.path.join(ROOT, "data", "case_reports", cid)
            if os.path.isdir(report_dir):
                shutil.rmtree(report_dir, ignore_errors=True)
        conn.commit()
        print(f"[cleanup] removed {len(ids)} PWTEST case(s) + reports")
    except sqlite3.OperationalError as e:
        print(f"[cleanup] skipped ({e})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
