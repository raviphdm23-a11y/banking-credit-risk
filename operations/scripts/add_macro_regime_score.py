"""
add_macro_regime_score.py
─────────────────────────
Adds Macro Regime Score (MRS) infrastructure to the database.

Steps
  1. Patch country_macro: insert realistic COVID-year (CY2021) rows for all 7
     countries and add 5 computed columns:
       delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct,
       delta_unemployment_pct, macro_regime_score
  2. Extend bank_loan_metrics with the same 5 columns and backfill them using
     observation_date to determine which regime each row belongs to.
  3. Print a summary.

Idempotent — safe to re-run.

Run: python operations/scripts/add_macro_regime_score.py
"""

import os, sys, sqlite3, math
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB    = os.path.join(_ROOT, 'bank.db')

# ── COVID-year macro values (Calendar Year 2020 actuals) ─────────────────────
# Sources: IMF World Economic Outlook, World Bank, central bank databases
COVID_MACRO = {
    # code : (gdp_growth, cpi, policy_rate, unemployment)
    'IND': (-7.3,  6.2,  4.00, 11.4),   # RBI repo; CMIE unemployment peak
    'USA': (-3.5,  1.2,  0.25,  8.1),   # Fed funds lower bound; BLS U-3
    'GBR': (-9.8,  0.9,  0.10,  4.5),   # Bank of England base rate; ONS
    'SGP': (-5.4, -0.2,  0.30,  3.0),   # MAS; MOM
    'ARE': (-6.1, -2.1,  1.50,  5.3),   # CBUAE; IMF estimate
    'AUS': (-2.4,  0.9,  0.10,  6.4),   # RBA cash rate; ABS
    'CHN': ( 2.2,  2.5,  3.85,  5.6),   # PBOC 1Y LPR; NBS — least impacted
}

# Normalisation denominators for each delta (pp movement = 100% contribution)
NORM = {
    'delta_gdp_pct':          12.0,   # ±12pp GDP shock → max contribution
    'delta_unemployment_pct':  6.0,   # +6pp unemployment spike → max
    'delta_policy_rate_pct':   3.0,   # ±3pp rate swing → max
    'delta_cpi_pct':           4.0,   # +4pp inflation spike → max
}
WEIGHTS = {
    'delta_gdp_pct':          40,
    'delta_unemployment_pct': 30,
    'delta_policy_rate_pct':  15,
    'delta_cpi_pct':          15,
}


def compute_mrs(delta_gdp, delta_unemp, delta_rate, delta_cpi):
    """Macro Regime Score 0-100.  0=normal, 56+=severe distress."""
    contributions = {
        'delta_gdp_pct':          min(1.0, abs(delta_gdp)         / NORM['delta_gdp_pct'])          * WEIGHTS['delta_gdp_pct'],
        'delta_unemployment_pct': min(1.0, max(0, delta_unemp)    / NORM['delta_unemployment_pct']) * WEIGHTS['delta_unemployment_pct'],
        'delta_policy_rate_pct':  min(1.0, abs(delta_rate)        / NORM['delta_policy_rate_pct'])  * WEIGHTS['delta_policy_rate_pct'],
        'delta_cpi_pct':          min(1.0, max(0, delta_cpi)      / NORM['delta_cpi_pct'])          * WEIGHTS['delta_cpi_pct'],
    }
    return round(min(100.0, sum(contributions.values())), 1)


def mrs_label(mrs):
    if mrs <= 25: return 'Normal'
    if mrs <= 55: return 'Moderate Stress'
    return 'Severe Distress'


def run():
    conn = sqlite3.connect(DB)
    cur  = conn.cursor()

    # ── 1a. Add delta/MRS columns to country_macro ───────────────────────────
    print('[1] Extending country_macro table...')
    for col, dtype in [
        ('delta_gdp_pct',          'REAL'),
        ('delta_cpi_pct',          'REAL'),
        ('delta_policy_rate_pct',  'REAL'),
        ('delta_unemployment_pct', 'REAL'),
        ('macro_regime_score',     'REAL'),
    ]:
        try:
            cur.execute(f'ALTER TABLE country_macro ADD COLUMN {col} {dtype}')
            print(f'    + {col}')
        except Exception:
            pass  # already exists

    # ── 1b. Insert / replace CY2021 COVID rows ────────────────────────────────
    print('[2] Upserting COVID-year (CY2021) macro rows...')

    # Fetch prior-period values (CY2020) for delta computation
    prior = {}
    for row in cur.execute(
        "SELECT country_code, gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct "
        "FROM country_macro WHERE period='CY2020'"
    ):
        prior[row[0]] = row[1:]

    for code, (gdp, cpi, rate, unemp) in COVID_MACRO.items():
        p_gdp, p_cpi, p_rate, p_unemp = prior.get(code, (gdp, cpi, rate, unemp))
        d_gdp   = round(gdp   - p_gdp,   2)
        d_cpi   = round(cpi   - p_cpi,   2)
        d_rate  = round(rate  - p_rate,  2)
        d_unemp = round(unemp - p_unemp, 2)
        mrs     = compute_mrs(d_gdp, d_unemp, d_rate, d_cpi)

        # Delete existing CY2021 row if any, then insert fresh
        cur.execute("DELETE FROM country_macro WHERE country_code=? AND period='CY2021'", (code,))
        cur.execute(
            """INSERT INTO country_macro
               (country_code, period, gdp_growth_pct, inflation_cpi_pct,
                policy_rate_pct, unemployment_pct,
                delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct,
                delta_unemployment_pct, macro_regime_score, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'add_macro_regime_score.py')""",
            (code, 'CY2021', gdp, cpi, rate, unemp,
             d_gdp, d_cpi, d_rate, d_unemp, mrs)
        )
        print(f'    {code} CY2021: GDP={gdp:+.1f}% dGDP={d_gdp:+.1f}pp  '
              f'Unemp={unemp}% dUnemp={d_unemp:+.1f}pp  '
              f'MRS={mrs:.0f} [{mrs_label(mrs)}]')

    # ── 1c. Backfill existing CY2019/CY2020 rows with near-zero deltas ────────
    print('[3] Backfilling pre-COVID country_macro rows (near-zero MRS)...')
    for code in COVID_MACRO:
        # CY2020 vs CY2019 — typically small deltas
        rows = {r[0]: r[1:] for r in cur.execute(
            "SELECT period, gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct "
            "FROM country_macro WHERE country_code=? AND period IN ('CY2019','CY2020') ORDER BY period",
            (code,)
        )}
        prev_vals = None
        for period in ['CY2019', 'CY2020']:
            if period not in rows:
                continue
            vals = rows[period]
            if prev_vals is None:
                d_gdp, d_cpi, d_rate, d_unemp, mrs = 0.0, 0.0, 0.0, 0.0, 0.0
            else:
                d_gdp   = round(vals[0] - prev_vals[0], 2)
                d_cpi   = round(vals[1] - prev_vals[1], 2)
                d_rate  = round(vals[2] - prev_vals[2], 2)
                d_unemp = round(vals[3] - prev_vals[3], 2)
                mrs     = compute_mrs(d_gdp, d_unemp, d_rate, d_cpi)
            cur.execute(
                """UPDATE country_macro SET
                   delta_gdp_pct=?, delta_cpi_pct=?, delta_policy_rate_pct=?,
                   delta_unemployment_pct=?, macro_regime_score=?
                   WHERE country_code=? AND period=?""",
                (d_gdp, d_cpi, d_rate, d_unemp, mrs, code, period)
            )
            prev_vals = vals

    # ── 2. Extend bank_loan_metrics ───────────────────────────────────────────
    print('[4] Extending bank_loan_metrics table...')
    for col, dtype in [
        ('delta_gdp_pct',          'REAL DEFAULT 0'),
        ('delta_cpi_pct',          'REAL DEFAULT 0'),
        ('delta_policy_rate_pct',  'REAL DEFAULT 0'),
        ('delta_unemployment_pct', 'REAL DEFAULT 0'),
        ('macro_regime_score',     'REAL DEFAULT 0'),
    ]:
        try:
            cur.execute(f'ALTER TABLE bank_loan_metrics ADD COLUMN {col} {dtype}')
            print(f'    + {col}')
        except Exception:
            pass

    # ── 3. Backfill bank_loan_metrics ─────────────────────────────────────────
    print('[5] Backfilling bank_loan_metrics with MRS values...')

    # Build lookup: country_code → {period_label: (d_gdp, d_cpi, d_rate, d_unemp, mrs)}
    macro_lookup = {}
    for row in cur.execute(
        "SELECT country_code, period, delta_gdp_pct, delta_cpi_pct, "
        "       delta_policy_rate_pct, delta_unemployment_pct, macro_regime_score "
        "FROM country_macro WHERE delta_gdp_pct IS NOT NULL"
    ):
        cc, period = row[0], row[1]
        macro_lookup.setdefault(cc, {})[period] = row[2:]

    def _mrs_for_date(country_code, obs_date):
        """Map observation date to the right country_macro period."""
        if not obs_date:
            return (0.0, 0.0, 0.0, 0.0, 0.0)
        year = int(obs_date[:4])
        # COVID period: 2020 April onwards → CY2021 macro
        if obs_date >= '2020-04-01':
            period = 'CY2021'
        elif year >= 2020:
            period = 'CY2020'
        else:
            period = 'CY2019'

        cm = macro_lookup.get(country_code or 'IND', {})
        vals = cm.get(period) or cm.get('CY2021') or (0.0, 0.0, 0.0, 0.0, 0.0)
        return vals  # (d_gdp, d_cpi, d_rate, d_unemp, mrs)

    rows = cur.execute(
        "SELECT id, country_code, observation_date FROM bank_loan_metrics"
    ).fetchall()

    updated = 0
    for row_id, cc, obs in rows:
        d_gdp, d_cpi, d_rate, d_unemp, mrs = _mrs_for_date(cc or 'IND', obs)
        cur.execute(
            """UPDATE bank_loan_metrics SET
               delta_gdp_pct=?, delta_cpi_pct=?, delta_policy_rate_pct=?,
               delta_unemployment_pct=?, macro_regime_score=?
               WHERE id=?""",
            (d_gdp, d_cpi, d_rate, d_unemp, mrs, row_id)
        )
        updated += 1

    conn.commit()
    conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f'\n[6] Done.  Updated {updated} bank_loan_metrics rows.')
    print('\nMRS thresholds:  0-25 Normal | 26-55 Moderate Stress | 56-100 Severe Distress')
    print('\nIndia COVID MRS check:')
    ind = COVID_MACRO['IND']
    p_ind = (6.5, 4.8, 6.5, 7.8)  # IND CY2019
    d = (ind[0]-p_ind[0], ind[1]-p_ind[1], ind[2]-p_ind[2], ind[3]-p_ind[3])
    print(f'  dGDP={d[0]:+.1f}pp  dUnemployment={d[3]:+.1f}pp  '
          f'dRate={d[2]:+.1f}pp  dCPI={d[1]:+.1f}pp')
    mrs_val = compute_mrs(d[0], d[3], d[2], d[1])
    print(f'  MRS = {mrs_val} -> {mrs_label(mrs_val)}')


if __name__ == '__main__':
    run()
