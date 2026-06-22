"""
seed_sim_metrics.py
───────────────────
Creates and populates the sim_period_metrics table — one row per simulation
period — with moratorium data, stratification counts, and Decision Gate scores.
Idempotent (INSERT OR REPLACE). Run once; advance scripts append each month.

Run: python operations/scripts/seed_sim_metrics.py
"""

import os, sys, sqlite3
from datetime import date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS sim_period_metrics (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id        TEXT NOT NULL,
    period         TEXT NOT NULL,
    as_of_date     TEXT NOT NULL,
    -- moratorium
    morat_count    INTEGER,
    morat_pct      REAL,
    morat_book_cr  REAL,
    morat_green    INTEGER,
    morat_amber    INTEGER,
    morat_red      INTEGER,
    -- decision gate (G/A/R)
    gate_gnpa      TEXT,
    gate_pat       TEXT,
    gate_car       TEXT,
    gate_morat     TEXT,
    gate_disbursals TEXT,
    -- disbursal count this period
    new_disbursals INTEGER,
    notes          TEXT,
    UNIQUE(bank_id, period)
);
"""

# Known values from advance scripts — moratorium data tracked at month-end
# Format: period -> (as_of_date, morat_count, morat_pct, morat_book_cr, G, A, R, disbursals, notes)
KNOWN = {
    'FY2019':  ('2019-03-31', 0,    0.0,  0.0,  0, 0, 0, 0,  'Pre-COVID baseline'),
    'FY2020':  ('2020-03-31', 0,    0.0,  0.0,  0, 0, 0, 0,  'Pre-COVID baseline; moratorium announced Mar 27'),
    'APR2020': ('2020-04-30', 1287, 30.0, 231.5, 0, 0, 0, 5,  'COVID lockdown M1; moratorium 30%; 5 essential disbursals'),
    'MAY2020': ('2020-05-31', 1503, 35.0, 251.0, 0, 0, 0, 20, 'Unlock 1.0; ECLGS launched; moratorium 35%'),
    'JUN2020': ('2020-06-30', 1420, 33.0, 243.6, 0, 0, 0, 25, 'Moratorium opt-outs begin; Unlock 1.0 full month'),
    'JUL2020': ('2020-07-31', 1339, 31.0, 231.7, 0, 0, 0, 30, 'Unlock 3.0; Kharif season; final COVID provision'),
    'AUG2020': ('2020-08-31', 1216, 28.0, 209.8, 413, 728, 75, 22, 'Moratorium ends; S1+S2 activated; OTR announced'),
}

# Decision gate scores derived from known outcomes
GATES = {
    'FY2019':  ('GREEN','GREEN','GREEN','GREEN','GREEN'),
    'FY2020':  ('GREEN','GREEN','GREEN','GREEN','GREEN'),
    'APR2020': ('GREEN','RED',  'GREEN','RED',  'RED'),
    'MAY2020': ('GREEN','RED',  'GREEN','RED',  'AMBER'),
    'JUN2020': ('GREEN','RED',  'GREEN','RED',  'GREEN'),
    'JUL2020': ('GREEN','RED',  'GREEN','RED',  'GREEN'),
    'AUG2020': ('GREEN','GREEN','GREEN','RED',  'AMBER'),
}


def seed(db_path=DB_PATH, verbose=True):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.executescript(SCHEMA)

    inserted = 0
    for period, vals in KNOWN.items():
        as_of, mc, mp, mb, mg, ma, mr, nd, notes = vals
        gg, gp, gc, gm, gd = GATES[period]
        cur.execute("""
            INSERT OR REPLACE INTO sim_period_metrics
              (bank_id, period, as_of_date,
               morat_count, morat_pct, morat_book_cr,
               morat_green, morat_amber, morat_red,
               gate_gnpa, gate_pat, gate_car, gate_morat, gate_disbursals,
               new_disbursals, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, ('BANK010', period, as_of,
              mc, mp, mb, mg, ma, mr,
              gg, gp, gc, gm, gd,
              nd, notes))
        inserted += 1

    conn.commit()
    conn.close()
    if verbose:
        print(f"sim_period_metrics: {inserted} rows seeded for BANK010")


if __name__ == '__main__':
    seed()
