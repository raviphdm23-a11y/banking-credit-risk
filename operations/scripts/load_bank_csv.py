"""
load_bank_csv.py
----------------
Creates the bank_loan_metrics table (if not exists) and bulk-loads
any external bank loan/credit-risk CSV into it.

Usage:
    python load_bank_csv.py                          # loads icici_bank_2024.csv
    python load_bank_csv.py some_other_bank.csv      # loads a different file

CSV must have columns:
    bank_id, bank_name, loan_id, de_ratio, interest_coverage,
    profitability, liquidity_ratio, default_flag, pd_observed, observation_date

bank_id values in the CSV are mapped to the bank.db banks table:
    ICICI  -> BANK002
    HDFC   -> BANK001
Add more mappings below as needed.
"""

import os
import sys
import csv
import sqlite3
from datetime import datetime

DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')
CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "icici_bank_2024.csv"

BANK_ID_MAP = {
    "ICICI": "BANK002",
    "HDFC":  "BANK001",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bank_loan_metrics (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id          VARCHAR(20)  NOT NULL,
    bank_name        VARCHAR(100),
    loan_id          VARCHAR(40)  NOT NULL,
    de_ratio         FLOAT,
    interest_coverage FLOAT,
    profitability    FLOAT,
    liquidity_ratio  FLOAT,
    default_flag     INTEGER,
    pd_observed      FLOAT,
    observation_date DATE,
    loaded_at        DATETIME     NOT NULL,
    FOREIGN KEY (bank_id) REFERENCES banks(bank_id),
    UNIQUE (loan_id, observation_date)
);
"""


def load_csv(csv_path, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("Table bank_loan_metrics ready.")

    loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    skipped  = 0
    errors   = 0

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    print("Rows in CSV  : {}".format(len(rows)))
    print("Loading into : {}".format(db_path))
    print("=" * 60)

    for row in rows:
        raw_bank_id = row["bank_id"].strip()
        bank_id     = BANK_ID_MAP.get(raw_bank_id, raw_bank_id)

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO bank_loan_metrics
                    (bank_id, bank_name, loan_id, de_ratio, interest_coverage,
                     profitability, liquidity_ratio, default_flag, pd_observed,
                     observation_date, loaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bank_id,
                row["bank_name"].strip(),
                row["loan_id"].strip(),
                float(row["de_ratio"]),
                float(row["interest_coverage"]),
                float(row["profitability"]),
                float(row["liquidity_ratio"]),
                int(row["default_flag"]),
                float(row["pd_observed"]),
                row["observation_date"].strip(),
                loaded_at,
            ))

            if cursor.rowcount:
                inserted += 1
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            print("  ERROR row {}: {}".format(row.get("loan_id"), e))

    conn.commit()
    conn.close()

    print("Inserted : {}".format(inserted))
    print("Skipped  : {} (duplicates)".format(skipped))
    print("Errors   : {}".format(errors))

    verify(db_path)


def verify(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM bank_loan_metrics")
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT bank_id, bank_name, COUNT(*) as cnt,
               SUM(default_flag) as defaults,
               ROUND(AVG(pd_observed), 4) as avg_pd
        FROM bank_loan_metrics
        GROUP BY bank_id
    """)
    rows = cursor.fetchall()

    print("\n" + "=" * 60)
    print("bank_loan_metrics total rows: {}".format(total))
    print("{:<10} {:<22} {:>6} {:>8} {:>8}".format(
        "bank_id", "bank_name", "loans", "defaults", "avg_pd"))
    print("-" * 60)
    for r in rows:
        print("{:<10} {:<22} {:>6} {:>8} {:>8}".format(
            r[0], r[1], r[2], r[3], r[4]))

    conn.close()


if __name__ == "__main__":
    load_csv(CSV_PATH)
