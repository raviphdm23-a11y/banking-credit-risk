"""
seed_global.py
──────────────
Turn the platform into a **global group bank**. Adds the country dimension that
sits above the existing per-bank data so the group can be navigated as:

        Group  →  Region  →  Country  →  Bank

What it creates / populates (all in bank.db, idempotent):

  • `countries`       — jurisdiction master: ISO-3 code, region / sub-region,
                        currency, central bank, Basel framework, sovereign
                        rating and the per-jurisdiction regulatory minimums.
  • `country_macro`   — periodic high-level macro indicators per country
                        (GDP, GDP growth, CPI inflation, policy rate,
                        unemployment, public-debt/GDP, current-account/GDP,
                        FX rate, population) — one row per country per period.
  • `banks.country_code` — new column mapping every bank to a country
                        (existing India banks back-filled to IND).
  • Four **foreign group banks** (USA / UK / Singapore / UAE) as bank-master rows,
    then **grounded in a real ledger** via seed_global_customers.py (customers /
    loans / accounts / …) — their balance sheet & P&L are live-anchored by the
    BS/P&L seeders afterwards, exactly like the India banks (no hardcoded figures).
  • A handful of foreign **regulatory_bodies** rows (Fed, BoE, MAS, CBUAE).

Reporting-currency note: every monetary figure in bank.db is denominated in INR
(₹). Consistent with how real global groups publish one *consolidated* currency,
the foreign banks' ledgers are seeded in the **group reporting currency (₹)**;
each bank's home country, local currency and macro context come from the
`countries` / `country_macro` tables. So consolidation stays additive while the
country dimension stays truthful.

Run:  python operations/scripts/seed_global.py
"""

import os
import sqlite3
import importlib.util
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(_REPO_ROOT, 'bank.db')

# ── schema ───────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS countries (
    country_code TEXT PRIMARY KEY,            -- ISO-3166 alpha-3
    country_name TEXT NOT NULL,
    region TEXT,                              -- top-level grouping
    sub_region TEXT,
    currency_code TEXT,
    currency_symbol TEXT,
    central_bank TEXT,
    central_bank_abbr TEXT,
    capital_regulator TEXT,
    basel_framework TEXT,
    sovereign_rating TEXT,
    min_crar REAL, min_cet1 REAL, min_tier1 REAL, min_lcr REAL, min_nsfr REAL,
    is_home INTEGER DEFAULT 0,                -- 1 = group home jurisdiction
    generated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_countries_region ON countries(region, sub_region);

CREATE TABLE IF NOT EXISTS country_macro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    period TEXT NOT NULL,                     -- calendar year, e.g. 'CY2025'
    gdp_usd_bn REAL,                          -- nominal GDP, USD billions
    gdp_growth_pct REAL,                      -- real GDP growth %
    inflation_cpi_pct REAL,                   -- headline CPI %
    policy_rate_pct REAL,                     -- central-bank policy rate %
    unemployment_pct REAL,
    public_debt_gdp_pct REAL,                 -- general govt debt / GDP %
    current_account_gdp_pct REAL,             -- current account / GDP %
    fx_rate_per_usd REAL,                     -- local currency units per 1 USD
    population_mn REAL,
    source TEXT, generated_at TEXT,
    UNIQUE(country_code, period)
);
CREATE INDEX IF NOT EXISTS idx_macro_country ON country_macro(country_code, period);
"""

# ── country master ───────────────────────────────────────────────────────────
# code, name, region, sub_region, ccy, symbol, central bank, abbr, regulator,
# basel framework, rating, min_crar, cet1, tier1, lcr, nsfr, is_home
_COUNTRIES = [
    ('IND', 'India', 'Asia-Pacific', 'South Asia', 'INR', '₹',
     'Reserve Bank of India', 'RBI', 'Reserve Bank of India', 'Basel III (RBI)',
     'BBB-', 11.5, 8.0, 9.5, 100, 100, 1),
    ('USA', 'United States', 'Americas', 'North America', 'USD', '$',
     'Federal Reserve System', 'FED', 'Federal Reserve / OCC', 'Basel III (US Final)',
     'AA+', 10.5, 7.0, 8.5, 100, 100, 0),
    ('GBR', 'United Kingdom', 'Europe', 'Western Europe', 'GBP', '£',
     'Bank of England', 'BoE', 'Prudential Regulation Authority', 'Basel 3.1 (UK)',
     'AA', 10.5, 7.0, 8.5, 100, 100, 0),
    ('SGP', 'Singapore', 'Asia-Pacific', 'Southeast Asia', 'SGD', 'S$',
     'Monetary Authority of Singapore', 'MAS', 'Monetary Authority of Singapore', 'Basel III (MAS)',
     'AAA', 10.0, 6.5, 8.0, 100, 100, 0),
    ('ARE', 'United Arab Emirates', 'Middle East & Africa', 'GCC', 'AED', 'د.إ',
     'Central Bank of the UAE', 'CBUAE', 'Central Bank of the UAE', 'Basel III (CBUAE)',
     'AA-', 13.0, 7.0, 8.5, 100, 100, 0),
    # reference-only jurisdictions (no group bank yet) — show the world is bigger
    ('DEU', 'Germany', 'Europe', 'Western Europe', 'EUR', '€',
     'European Central Bank', 'ECB', 'ECB / BaFin (SSM)', 'Basel III (CRR/CRD)',
     'AAA', 10.5, 7.0, 8.5, 100, 100, 0),
    ('JPN', 'Japan', 'Asia-Pacific', 'East Asia', 'JPY', '¥',
     'Bank of Japan', 'BoJ', 'Financial Services Agency', 'Basel III (FSA)',
     'A+', 10.5, 7.0, 8.5, 100, 100, 0),
]

# ── macro indicators: country_code -> {period -> tuple} ──────────────────────
# (gdp_usd_bn, gdp_growth, cpi, policy_rate, unemployment, debt/gdp, ca/gdp, fx_per_usd, pop_mn)
_MACRO = {
    'IND': {'CY2024': (3937, 6.5, 4.8, 6.50, 7.8, 83.0, -1.2, 83.5, 1441),
            'CY2025': (4340, 6.7, 4.5, 6.25, 7.6, 82.0, -1.0, 85.0, 1451)},
    'USA': {'CY2024': (28780, 2.7, 3.0, 5.00, 4.1, 122.0, -3.3, 1.00, 341),
            'CY2025': (30000, 2.2, 2.6, 4.25, 4.2, 124.0, -3.2, 1.00, 342)},
    'GBR': {'CY2024': (3590, 0.9, 2.5, 4.75, 4.3, 101.0, -3.0, 0.79, 68.3),
            'CY2025': (3730, 1.4, 2.3, 4.25, 4.4, 103.0, -2.8, 0.79, 68.5)},
    'SGP': {'CY2024': (530, 3.5, 2.4, 3.50, 2.0, 168.0, 17.5, 1.34, 5.9),
            'CY2025': (560, 2.8, 1.8, 3.00, 2.1, 165.0, 16.8, 1.35, 6.0)},
    'ARE': {'CY2024': (545, 3.8, 2.3, 4.90, 2.7, 30.0, 8.0, 3.67, 10.6),
            'CY2025': (575, 4.5, 2.1, 4.40, 2.6, 29.0, 7.5, 3.67, 10.7)},
    'DEU': {'CY2024': (4590, -0.2, 2.4, 3.40, 3.4, 63.0, 6.0, 0.92, 84.5),
            'CY2025': (4740, 0.8, 2.1, 2.65, 3.5, 62.0, 6.2, 0.92, 84.6)},
    'JPN': {'CY2024': (4070, 0.1, 2.7, 0.25, 2.5, 251.0, 3.6, 151.0, 123.9),
            'CY2025': (4190, 1.1, 2.0, 0.50, 2.4, 249.0, 3.8, 148.0, 123.4)},
}

# ── foreign group banks (carried at balance-sheet + P&L level, group ccy ₹) ──
# bank_id, name, code, country_code, hq_city, year, advances_anchor, deposits_anchor
_GLOBAL_BANKS = [
    ('BANK003', 'Atlas Bank N.A.',            '0030', 'USA', 'New York',   2001, 95_000_000, 70_000_000),
    ('BANK004', 'Britannia Banking Group plc', '0040', 'GBR', 'London',     1994, 72_000_000, 60_000_000),
    ('BANK005', 'Lion City Bank Ltd',          '0050', 'SGP', 'Singapore',  2008, 52_000_000, 50_000_000),
    ('BANK006', 'Gulf Union Bank PJSC',        '0060', 'ARE', 'Dubai',      2011, 40_000_000, 33_000_000),
]
_HQ_STATE = {'USA': 'New York', 'GBR': 'England', 'SGP': 'Singapore', 'ARE': 'Dubai'}

# foreign regulators for the regulatory_bodies table (cosmetic completeness)
_FOREIGN_REGULATORS = [
    ('REG-FED',   'Federal Reserve System', 'FED', 'U.S. Government', 'United States',
     'Central bank and prudential regulator of the United States'),
    ('REG-BOE',   'Bank of England (PRA)', 'BoE/PRA', 'HM Treasury', 'United Kingdom',
     'UK central bank and prudential regulation authority'),
    ('REG-MAS',   'Monetary Authority of Singapore', 'MAS', 'Government of Singapore', 'Singapore',
     'Central bank and integrated financial regulator of Singapore'),
    ('REG-CBUAE', 'Central Bank of the UAE', 'CBUAE', 'UAE Government', 'United Arab Emirates',
     'Central bank and banking regulator of the United Arab Emirates'),
]

def _load(modname):
    p = os.path.join(os.path.dirname(__file__), modname + '.py')
    spec = importlib.util.spec_from_file_location(modname, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_country_code_column(cur):
    cols = [r[1] for r in cur.execute("PRAGMA table_info(banks)").fetchall()]
    if 'country_code' not in cols:
        cur.execute("ALTER TABLE banks ADD COLUMN country_code TEXT")


def seed(db_path=DB_PATH, verbose=True):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    now = datetime.now().isoformat(timespec='seconds')

    # 1. country master
    for c in _COUNTRIES:
        cur.execute(
            """INSERT OR REPLACE INTO countries
               (country_code, country_name, region, sub_region, currency_code,
                currency_symbol, central_bank, central_bank_abbr, capital_regulator,
                basel_framework, sovereign_rating, min_crar, min_cet1, min_tier1,
                min_lcr, min_nsfr, is_home, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*c, now))

    # 2. macro indicators
    for code, periods in _MACRO.items():
        for period, m in periods.items():
            cur.execute(
                """INSERT OR REPLACE INTO country_macro
                   (country_code, period, gdp_usd_bn, gdp_growth_pct, inflation_cpi_pct,
                    policy_rate_pct, unemployment_pct, public_debt_gdp_pct,
                    current_account_gdp_pct, fx_rate_per_usd, population_mn,
                    source, generated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code, period, *m, 'reference data (IMF/World Bank style, illustrative)', now))

    # 3. banks.country_code + back-fill existing (India) banks
    _ensure_country_code_column(cur)
    cur.execute("UPDATE banks SET country_code='IND' WHERE country_code IS NULL OR country_code=''")

    # 4. foreign regulators
    for r in _FOREIGN_REGULATORS:
        cur.execute(
            """INSERT OR REPLACE INTO regulatory_bodies
               (regulator_id, regulator_name, abbreviation, governing_body_name, country, description)
               VALUES (?,?,?,?,?,?)""", r)

    # 5. foreign group bank master rows (banks table only). Their balance sheet
    #    and P&L are NOT hardcoded here — the banks are grounded in a real ledger
    #    (seed_global_customers) and then live-anchored by the BS/P&L seeders, the
    #    same path the India banks use. _GLOBAL_BANKS advances/deposits are now just
    #    target sizes consumed by the customer generator.
    for bid, name, code, ccode, hq_city, year, adv, dep in _GLOBAL_BANKS:
        cur.execute(
            """INSERT OR REPLACE INTO banks
               (bank_id, bank_name, bank_code, country, headquarters_city,
                headquarters_state, year_established, status, country_code)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (bid, name, code,
             next(c[1] for c in _COUNTRIES if c[0] == ccode),   # country display name
             hq_city, _HQ_STATE.get(ccode, hq_city), year, 'Active', ccode))
    conn.commit()

    # 6. ground each foreign bank in a real ledger (customers/loans/accounts/...)
    _load('seed_global_customers').seed(db_path=db_path, verbose=verbose)

    if verbose:
        nc = cur.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
        nm = cur.execute("SELECT COUNT(*) FROM country_macro").fetchone()[0]
        print(f"countries: {nc}   macro rows: {nm}")
        print("Banks by region:")
        for row in cur.execute(
                """SELECT c.region, c.country_name, COUNT(b.bank_id)
                   FROM countries c LEFT JOIN banks b ON b.country_code=c.country_code
                   GROUP BY c.country_code ORDER BY c.region, c.country_name"""):
            print(f"  {row[0]:22s} {row[1]:20s} banks={row[2]}")
    conn.close()
    return {'countries': len(_COUNTRIES), 'banks_added': len(_GLOBAL_BANKS)}


if __name__ == '__main__':
    seed()
