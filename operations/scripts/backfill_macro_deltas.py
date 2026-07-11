"""
backfill_macro_deltas.py
─────────────────────────
Fixes the Macro Regime Score always reading ~0/Normal for every live
assessment: `country_macro` currently has exactly ONE period per country
('2024-Q2'), with delta_gdp_pct/delta_cpi_pct/delta_policy_rate_pct/
delta_unemployment_pct hardcoded to 0.0 and macro_regime_score hardcoded to
1.0 (see setup_fresh_db.py) - there is no earlier period to diff against, so
"change vs prior year" was never a real computation, just a flat placeholder.

This script inserts a genuine prior period ('2023-Q2', one year earlier) with
realistic prior-year macro figures for every country currently in
country_macro, then recomputes real delta_*/macro_regime_score columns on the
existing 2024-Q2 rows from the actual period-over-period change - using the
identical compute_mrs() formula defined in add_macro_regime_score.py, so both
scripts agree on what a given delta means.

Idempotent — safe to re-run (upserts the prior period, recomputes deltas
each time rather than accumulating).

Run: python operations/scripts/backfill_macro_deltas.py
"""

import os
import sqlite3

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB = os.path.join(_ROOT, 'bank.db')

# Same weighting as add_macro_regime_score.py's compute_mrs() - kept identical
# so a delta means the same regime-shift severity regardless of which script
# (training backfill vs this live-inference backfill) produced it.
NORM = {
    'delta_gdp_pct':          12.0,
    'delta_unemployment_pct':  6.0,
    'delta_policy_rate_pct':   3.0,
    'delta_cpi_pct':           4.0,
}
WEIGHTS = {
    'delta_gdp_pct':          40,
    'delta_unemployment_pct': 30,
    'delta_policy_rate_pct':  15,
    'delta_cpi_pct':          15,
}


def compute_mrs(delta_gdp, delta_unemp, delta_rate, delta_cpi):
    """Macro Regime Score 0-100. 0=normal, 26-55=moderate stress, 56+=severe.
    Identical formula to add_macro_regime_score.py's compute_mrs()."""
    contributions = {
        'delta_gdp_pct':          min(1.0, abs(delta_gdp)      / NORM['delta_gdp_pct'])          * WEIGHTS['delta_gdp_pct'],
        'delta_unemployment_pct': min(1.0, max(0, delta_unemp) / NORM['delta_unemployment_pct'])  * WEIGHTS['delta_unemployment_pct'],
        'delta_policy_rate_pct':  min(1.0, abs(delta_rate)     / NORM['delta_policy_rate_pct'])   * WEIGHTS['delta_policy_rate_pct'],
        'delta_cpi_pct':          min(1.0, max(0, delta_cpi)   / NORM['delta_cpi_pct'])           * WEIGHTS['delta_cpi_pct'],
    }
    return round(min(100.0, sum(contributions.values())), 1)


def mrs_label(mrs):
    if mrs <= 25: return 'Normal'
    if mrs <= 55: return 'Moderate Stress'
    return 'Severe Distress'


# Prior-year (2023-Q2) macro figures per country currently in country_macro -
# directionally realistic (global 2023->2024 disinflation, modest growth/
# unemployment drift), illustrative rather than official-statistics-precise,
# consistent with the rest of this platform's synthetic ledger.
# (gdp_growth, cpi, policy_rate, unemployment)
PRIOR_2023Q2 = {
    'IND': (7.8, 5.4, 6.50, 7.9),
    'IN':  (7.8, 5.4, 6.50, 7.9),   # legacy duplicate row - keep in sync with IND
    'USA': (2.1, 4.8, 5.25, 3.6),
    'GBR': (0.2, 7.9, 5.00, 4.0),
    'SGP': (0.5, 4.6, 3.75, 1.9),
    'ARE': (3.4, 3.4, 5.00, 2.6),
    'AUS': (2.0, 6.0, 4.10, 3.6),
}


def run():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT country_code, period, gdp_growth_pct, inflation_cpi_pct, "
                "policy_rate_pct, unemployment_pct FROM country_macro")
    current_rows = cur.fetchall()

    print(f'[1] Found {len(current_rows)} country_macro rows to backfill a prior period for.')

    updated = 0
    for code, period, gdp, cpi, rate, unemp in current_rows:
        prior = PRIOR_2023Q2.get(code)
        if prior is None:
            print(f'    ! No prior-period figures defined for {code} - skipping.')
            continue
        p_gdp, p_cpi, p_rate, p_unemp = prior

        # Insert/replace the prior period itself (its own deltas are 0 - nothing
        # earlier to compare it to).
        cur.execute("DELETE FROM country_macro WHERE country_code=? AND period='2023-Q2'", (code,))
        cur.execute(
            """INSERT INTO country_macro
               (country_code, period, gdp_growth_pct, inflation_cpi_pct,
                policy_rate_pct, unemployment_pct,
                delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct,
                delta_unemployment_pct, macro_regime_score, source)
               VALUES (?, '2023-Q2', ?, ?, ?, ?, 0, 0, 0, 0, 0, 'backfill_macro_deltas.py')""",
            (code, p_gdp, p_cpi, p_rate, p_unemp)
        )

        # Recompute genuine deltas for the current (2024-Q2) row vs this prior period.
        d_gdp   = round(gdp   - p_gdp,   2)
        d_cpi   = round(cpi   - p_cpi,   2)
        d_rate  = round(rate  - p_rate,  2)
        d_unemp = round(unemp - p_unemp, 2)
        mrs     = compute_mrs(d_gdp, d_unemp, d_rate, d_cpi)

        cur.execute(
            """UPDATE country_macro SET
               delta_gdp_pct=?, delta_cpi_pct=?, delta_policy_rate_pct=?,
               delta_unemployment_pct=?, macro_regime_score=?
               WHERE country_code=? AND period=?""",
            (d_gdp, d_cpi, d_rate, d_unemp, mrs, code, period)
        )
        updated += 1
        print(f'    {code} {period}: dGDP={d_gdp:+.2f}pp dCPI={d_cpi:+.2f}pp '
              f'dRate={d_rate:+.2f}pp dUnemp={d_unemp:+.2f}pp  '
              f'MRS={mrs:.1f} [{mrs_label(mrs)}]')

    conn.commit()

    # ── 2. Backfill bank_loan_metrics (the TRAINING table) ───────────────────
    # bank_loan_metrics is a current-portfolio snapshot (every row's
    # observation_date is today's sim date, not a real historical panel), and
    # its existing macro LEVEL columns (gdp_growth_pct etc.) are already a
    # constant-per-country value applied to every loan from that country - see
    # sync_bank_loan_metrics.py. This backfill follows the identical pattern
    # for the 5 delta/regime columns instead of leaving them NULL, which is
    # what silently zeroed out their XGBoost feature_importances_ (100% missing
    # training data -> the model never had a split to learn).
    print('\n[3] Backfilling bank_loan_metrics delta/regime columns per country...')
    cur.execute("SELECT country_code, delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, "
                "delta_unemployment_pct, macro_regime_score FROM country_macro WHERE period='2024-Q2'")
    latest_by_country = {row[0]: row[1:] for row in cur.fetchall()}

    cur.execute("SELECT DISTINCT country_code FROM bank_loan_metrics")
    loan_countries = [r[0] for r in cur.fetchall()]

    total_rows_updated = 0
    for code in loan_countries:
        vals = latest_by_country.get(code)
        if vals is None:
            print(f'    ! No country_macro row for {code} (present in bank_loan_metrics) - skipping.')
            continue
        d_gdp, d_cpi, d_rate, d_unemp, mrs = vals
        cur.execute(
            """UPDATE bank_loan_metrics SET
               delta_gdp_pct=?, delta_cpi_pct=?, delta_policy_rate_pct=?,
               delta_unemployment_pct=?, macro_regime_score=?
               WHERE country_code=?""",
            (d_gdp, d_cpi, d_rate, d_unemp, mrs, code)
        )
        total_rows_updated += cur.rowcount
        print(f'    {code}: {cur.rowcount} rows -> MRS={mrs:.1f}')

    conn.commit()
    conn.close()
    print(f'\n[4] Done. Backfilled prior period + recomputed real deltas for {updated} '
          f'country_macro rows, and {total_rows_updated} bank_loan_metrics rows.')


if __name__ == '__main__':
    run()
