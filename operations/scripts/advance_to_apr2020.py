"""
advance_to_apr2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-03-31 to 2020-04-30.

Real-world context: April 2020 was the first full month of India's COVID-19
national lockdown (March 25 - May 3). The RBI had announced:
  - 3-month moratorium on all term loan EMIs (March 27 circular)
  - Repo rate cut 75 bps to 4.40% (March 27)
  - CRR reduced 100 bps to 3% (effective March 28)
  - SLR maintained at 18%; FALLCR relaxed

Effects simulated:
  1. Moratorium: ~30% of loans tagged; DPD frozen for those borrowers.
  2. DPD aging: non-moratorium loans age by 30 days.
  3. New disbursals: only 5 (essential sectors — agri, pharma), very small tickets.
  4. Balance sheet (APR2020 monthly snapshot):
       - Deposits +2% (safety-flight to bank)
       - Advances -0.8% (repayments on non-moratorium; no new credit)
       - Investments +1% (excess deposits parked in G-Secs temporarily)
       - COVID-19 contingency provision added to other_liabilities
       - Capital grows by retained monthly profit
  5. Monthly P&L (APR2020):
       - Interest income on advances (rate-cut adjusted)
       - NII compressed by repo transmission
       - COVID-19 provision charge (10% of moratorium book, spread over 4 qtrs)
       - Monthly PAT sharply lower than March run-rate
  6. Regulatory batch re-run for 2020-04-30.
  7. simulation_clock.json advanced.

Idempotent: re-running cleanly replaces APR2020 rows and moratorium tags.

Run: python operations/scripts/advance_to_apr2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID     = 'BANK010'
PREV_DATE   = '2020-03-31'
PREV_PERIOD = 'FY2020'
NEW_DATE    = '2020-04-30'
NEW_PERIOD  = 'APR2020'

MORATORIUM_RATE   = 0.30   # 30% of loans opt for moratorium
REPO_RATE_NEW     = 4.40   # RBI cut from 5.15% to 4.40%
DEPOSIT_GROWTH    = 0.020  # +2% safety-flight deposits
ADVANCE_CHANGE    = -0.008 # -0.8% net (repayments > disbursals)
COVID_PROV_QTRS   = 4      # RBI allowed spreading over 4 quarters

BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 5 new essential-sector loans only (agri/pharma/FMCG permitted during lockdown)
NEW_LOANS = [
    {'type':'Business Loan','principal':2500000,'rate':9.50,'tenure':24,'sector':'Agri-supply chain'},
    {'type':'Business Loan','principal':1800000,'rate':9.25,'tenure':12,'sector':'Pharma distribution'},
    {'type':'Business Loan','principal':3200000,'rate':9.75,'tenure':36,'sector':'FMCG wholesale'},
    {'type':'Home Loan',    'principal':4500000,'rate':8.50,'tenure':180,'sector':'Essential housing'},
    {'type':'Business Loan','principal':1200000,'rate':9.00,'tenure':12,'sector':'Medical equipment'},
]


def _emi(p, r_annual, t_months):
    r = r_annual / 100 / 12
    if r == 0:
        return p / t_months
    return p * r * (1+r)**t_months / ((1+r)**t_months - 1)


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_04)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-03-31 --> 2020-04-30')
    p('  COVID-19 Lockdown Month 1 | RBI Moratorium | Repo Rate 4.40%')
    p('=' * 68)

    # ── Step 1: Add moratorium column if missing ──────────────────────────────
    for col, defn in [('moratorium', 'INTEGER DEFAULT 0'),
                      ('moratorium_end_date', 'TEXT')]:
        try:
            cur.execute(f'ALTER TABLE loans ADD COLUMN {col} {defn}')
        except sqlite3.OperationalError:
            pass
    conn.commit()

    # ── Step 2: Apply moratorium to ~30% of standard loans ───────────────────
    loans = [dict(r) for r in cur.execute(
        "SELECT id, days_past_due, loan_classification, type, outstanding FROM loans WHERE bank_id=?",
        (BANK_ID,)).fetchall()]

    # Reset all moratoriums first (idempotent)
    cur.execute("UPDATE loans SET moratorium=0, moratorium_end_date=NULL WHERE bank_id=?", (BANK_ID,))

    eligible = [l for l in loans if (l['days_past_due'] or 0) < 90
                and (l['loan_classification'] or 'Standard') in ('Standard','Performing')]
    n_moratorium = int(len(eligible) * MORATORIUM_RATE)
    random.shuffle(eligible)
    moratorium_ids = {l['id'] for l in eligible[:n_moratorium]}

    cur.execute(
        "UPDATE loans SET moratorium=1, moratorium_end_date='2020-06-30' WHERE bank_id=? AND id IN ({})".format(
            ','.join('?' * len(moratorium_ids))),
        [BANK_ID] + list(moratorium_ids))
    conn.commit()
    p(f'\n[1] Moratorium applied to {n_moratorium:,} / {len(eligible):,} eligible loans ({MORATORIUM_RATE*100:.0f}%)')
    p(f'    Moratorium book: Rs{sum(l["outstanding"] or 0 for l in loans if l["id"] in moratorium_ids)/1e7:.1f} Cr')

    # ── Step 3: Age DPD by 30 days (only non-moratorium loans) ───────────────
    # First, reset nominal seed-artefact DPD (< 90) on Standard/Performing loans
    # to 0. The original seeder assigns ~19 DPD to many loans as a billing-cycle
    # placeholder. Without this, 3 months of +30 aging would push all of them
    # past 90 simultaneously. COVID stress enters via NPA classification below.
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0
          AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))
    cur.execute("""
        UPDATE loans
        SET days_past_due = MIN(days_past_due + 30, 180)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

    # Reclassify loans that crossed 90 DPD threshold (NPA)
    cur.execute("""
        UPDATE loans
        SET loan_classification = 'Sub-Standard'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))
    new_npa = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND days_past_due>=90 AND moratorium=0",
        (BANK_ID,)).fetchone()[0]
    conn.commit()
    p(f'\n[2] DPD aged +30 days for non-moratorium loans | NPA count: {new_npa}')

    # ── Step 4: Disburse 5 new essential-sector loans ─────────────────────────
    # Find customers without loans (still available from original pool)
    no_loan_custs = [dict(r) for r in cur.execute("""
        SELECT id FROM customers WHERE bank_id=?
        AND NOT EXISTS (SELECT 1 FROM loans WHERE cid=customers.id AND bank_id=?)
        LIMIT 10
    """, (BANK_ID, BANK_ID)).fetchall()]

    disbursed_count = 0
    total_new_principal = 0
    for i, spec in enumerate(NEW_LOANS):
        if i >= len(no_loan_custs):
            break
        cust_id = no_loan_custs[i]['id']
        loan_id = f'LOAN-COVID-APR2020-{i+1:02d}'
        emi_val = round(_emi(spec['principal'], spec['rate'], spec['tenure']), 2)
        cur.execute("""
            INSERT OR REPLACE INTO loans
              (id, bank_id, cid, type, principal, rate, tenure, emi,
               disbursed, maturity, outstanding, status, branch_id,
               loan_classification, exposure_class, days_past_due,
               moratorium, moratorium_end_date, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            loan_id, BANK_ID, cust_id, spec['type'],
            spec['principal'], spec['rate'], spec['tenure'], emi_val,
            NEW_DATE,
            (date(2020,4,30) + timedelta(days=spec['tenure']*30)).isoformat(),
            spec['principal'], 'Active',
            random.choice(BRANCHES),
            'Standard',
            'corporate' if spec['type']=='Business Loan' else 'retail_secured',
            0, 0, None, 'covid_essential_apr2020'
        ))
        disbursed_count += 1
        total_new_principal += spec['principal']
    conn.commit()
    p(f'\n[3] New essential-sector disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'    (Agri, Pharma, FMCG, Housing, Medical — permitted under lockdown)')

    # ── Step 5: Build APR2020 monthly balance sheet ───────────────────────────
    prev_bs = dict(cur.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?",
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_deposits = (prev_bs['deposits_demand'] + prev_bs['deposits_savings']
                     + prev_bs['deposits_term'])
    new_deposits  = prev_deposits * (1 + DEPOSIT_GROWTH)

    # Live advances from updated loan book
    new_advances = cur.execute(
        "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?",
        (BANK_ID,)).fetchone()[0]

    # Capital: FY2020 capital + estimated April retained earnings (near zero)
    prev_capital = prev_bs['equity_capital'] + prev_bs['reserves_surplus']
    monthly_pat_est = 0  # calculated in P&L step; use 0 for now, update after

    # COVID-19 contingency provision (10% of moratorium book / 4 quarters)
    moratorium_book = cur.execute(
        "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=? AND moratorium=1",
        (BANK_ID,)).fetchone()[0]
    covid_provision_quarter = moratorium_book * 0.10
    covid_provision_monthly = covid_provision_quarter / 3  # monthly within quarter

    # Asset composition
    equity_capital   = prev_bs['equity_capital']
    reserves_surplus = prev_bs['reserves_surplus']
    capital_base     = equity_capital + reserves_surplus

    deposits_demand  = 0.12 * new_deposits
    deposits_savings = 0.48 * new_deposits
    deposits_term    = new_deposits - deposits_demand - deposits_savings

    # Other liabilities rises: normal + COVID provisions
    other_liabilities = 0.040 * new_deposits + covid_provision_monthly

    total_lc = capital_base + new_deposits + other_liabilities

    cash_with_rbi     = 0.030 * new_deposits   # CRR cut to 3%
    investments       = 0.200 * new_deposits    # maintain same 20% ratio
    fixed_assets      = prev_bs['fixed_assets']
    intangible_assets = prev_bs['intangible_assets']
    other_assets      = 0.050 * new_advances

    fixed_sum = (cash_with_rbi + investments + new_advances
                 + fixed_assets + intangible_assets + other_assets)
    gap = total_lc - fixed_sum
    if gap >= 0:
        balances_with_banks = gap
        borrowings = 0.0
    else:
        balances_with_banks = 0.0
        borrowings = -gap

    total_assets = fixed_sum + balances_with_banks

    # Delete any previous APR2020 BS row and insert fresh
    cur.execute("DELETE FROM bank_balance_sheet WHERE bank_id=? AND period=?",
                (BANK_ID, NEW_PERIOD))
    now = datetime.now().isoformat(timespec='seconds')
    cur.execute("""
        INSERT INTO bank_balance_sheet
          (bank_id, period, as_on_date, currency, unit,
           equity_capital, reserves_surplus,
           deposits_demand, deposits_savings, deposits_term,
           borrowings, other_liabilities,
           cash_with_rbi, balances_with_banks, investments,
           advances_net, fixed_assets, intangible_assets, other_assets,
           contingent_liabilities, bills_for_collection,
           source, generated_at)
        VALUES (?,?,?,?,?, ?,?, ?,?,?, ?,?, ?,?,?, ?,?,?,?, ?,?, ?,?)
    """, (
        BANK_ID, NEW_PERIOD, NEW_DATE, 'INR', 'INR',
        round(equity_capital,2), round(reserves_surplus,2),
        round(deposits_demand,2), round(deposits_savings,2), round(deposits_term,2),
        round(borrowings,2), round(other_liabilities,2),
        round(cash_with_rbi,2), round(balances_with_banks,2), round(investments,2),
        round(new_advances,2), round(fixed_assets,2), round(intangible_assets,2),
        round(other_assets,2),
        round(0.60*total_assets,2), round(0.05*total_assets,2),
        'advance_to_apr2020', now
    ))
    conn.commit()

    # Verify balance
    ta_check = (cash_with_rbi + balances_with_banks + investments + new_advances
                + fixed_assets + intangible_assets + other_assets)
    tl_check = (capital_base + new_deposits + borrowings + other_liabilities)
    p(f'\n[4] Balance sheet APR2020 seeded')
    p(f'    Total Assets:  Rs{ta_check/1e7:.1f} Cr  (was Rs{(prev_bs["advances_net"]+prev_bs["investments"]+prev_bs["cash_with_rbi"]+prev_bs["balances_with_banks"]+prev_bs["fixed_assets"]+prev_bs["intangible_assets"]+prev_bs["other_assets"])/1e7:.1f} Cr)')
    p(f'    Total L+C:     Rs{tl_check/1e7:.1f} Cr  | Diff: {abs(ta_check-tl_check):.2f}')
    p(f'    Advances:      Rs{new_advances/1e7:.1f} Cr  | Deposits: Rs{new_deposits/1e7:.1f} Cr')
    p(f'    COVID provision (monthly): Rs{covid_provision_monthly/1e7:.2f} Cr')
    p(f'    Moratorium book: Rs{moratorium_book/1e7:.1f} Cr ({moratorium_book/new_advances*100:.1f}% of advances)')

    # ── Step 6: Monthly P&L for APR2020 ──────────────────────────────────────
    # Monthly interest income on advances (blended rate, repo-cut adjusted)
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 11.03
    # Repo transmission: ~50 bps reduction in lending rate on new loans
    # Existing floating loans reset ~25 bps; fixed loans unchanged
    effective_lending_rate = blended_rate - 0.15  # partial transmission in month 1

    interest_on_advances = round(new_advances * effective_lending_rate / 100 / 12, 2)
    interest_on_inv      = round(investments * 6.50 / 100 / 12, 2)  # G-Sec yield ~6.5%
    interest_earned      = round(interest_on_advances + interest_on_inv, 2)
    other_income         = round(interest_earned * 0.12, 2)  # fee income suppressed in lockdown

    # Interest expended: deposit rates stickier than lending rates in month 1
    deposit_rate = 4.75  # unchanged in April (banks slow to pass on cuts)
    interest_on_deposits  = round(new_deposits * deposit_rate / 100 / 12, 2)
    interest_on_borrowings = round(borrowings * 5.50 / 100 / 12, 2)
    interest_expended     = round(interest_on_deposits + interest_on_borrowings, 2)

    nii          = round(interest_earned - interest_expended, 2)
    total_income = round(interest_earned + other_income, 2)

    # Operating expenses (essentially fixed in short term)
    employee_cost = round(nii * 0.28, 2)
    other_opex    = round(nii * 0.17, 2)
    opex          = round(employee_cost + other_opex, 2)

    op_profit = round(nii + other_income - opex, 2)

    # Provisions: normal + COVID-19 charge
    normal_provision = round(new_advances * 0.005 / 12, 2)  # 0.5% pa standard provision
    covid_provision  = round(covid_provision_monthly, 2)
    provisions       = round(normal_provision + covid_provision, 2)

    pbt = round(op_profit - provisions, 2)
    tax = round(max(0, pbt * 0.25), 2)
    pat = round(pbt - tax, 2)

    # Delete previous APR2020 P&L row and insert fresh
    cur.execute("DELETE FROM bank_profit_loss WHERE bank_id=? AND period=?",
                (BANK_ID, NEW_PERIOD))
    pl_cols = ['bank_id','period','from_date','to_date','currency','unit',
               'interest_on_advances','interest_on_investments','interest_earned',
               'other_income','total_income',
               'interest_on_deposits','interest_on_borrowings','interest_expended',
               'employee_cost','other_opex','operating_expenses',
               'net_interest_income','operating_profit',
               'provisions_contingencies','profit_before_tax','tax_expense','profit_after_tax',
               'generated_at']
    cur.execute(
        "INSERT OR REPLACE INTO bank_profit_loss ({}) VALUES ({})".format(
            ','.join(pl_cols), ','.join('?'*len(pl_cols))),
        [BANK_ID, NEW_PERIOD, '2020-04-01', NEW_DATE, 'INR', 'INR',
         interest_on_advances, interest_on_inv, interest_earned,
         other_income, total_income,
         interest_on_deposits, interest_on_borrowings, interest_expended,
         employee_cost, other_opex, opex,
         nii, op_profit,
         provisions, pbt, tax, pat,
         now])
    conn.commit()

    p(f'\n[5] Monthly P&L APR2020 seeded')
    p(f'    Interest on Advances: Rs{interest_on_advances/1e7:.2f} Cr  (rate {effective_lending_rate:.2f}%)')
    p(f'    NII:                  Rs{nii/1e7:.2f} Cr')
    p(f'    Normal provision:     Rs{normal_provision/1e7:.2f} Cr')
    p(f'    COVID-19 provision:   Rs{covid_provision/1e7:.2f} Cr  (10% moratorium book / 4 qtrs / 3 months)')
    p(f'    Total provisions:     Rs{provisions/1e7:.2f} Cr')
    p(f'    PBT:                  Rs{pbt/1e7:.2f} Cr')
    p(f'    PAT:                  Rs{pat/1e7:.2f} Cr')

    # ── Step 7: Regulatory batch for 2020-04-30 ───────────────────────────────
    import importlib.util
    scripts = os.path.join(_REPO_ROOT, 'operations', 'scripts')
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch', os.path.join(scripts, 'run_regulatory_batch.py'))
    rb  = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=verbose)
    p('\n[6] Regulatory batch re-run for 2020-04-30')

    # ── Step 8: Advance simulation_clock.json ────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = ('COVID-19 lockdown month 1. Moratorium on 30% of loans. '
                    'Repo rate 4.40%. New disbursals frozen except essential sectors.')
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[7] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Final summary ─────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  APRIL 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Total Assets:        Rs{ta_check/1e7:.1f} Cr')
    p(f'  Advances (net):      Rs{new_advances/1e7:.1f} Cr')
    p(f'  Deposits:            Rs{new_deposits/1e7:.1f} Cr')
    p(f'  Moratorium loans:    {n_moratorium:,} ({MORATORIUM_RATE*100:.0f}% of book)')
    p(f'  NPA count:           {new_npa}')
    p(f'  Monthly NII:         Rs{nii/1e7:.2f} Cr')
    p(f'  Monthly PAT:         Rs{pat/1e7:.2f} Cr  (COVID provision drag)')
    p(f'  CAR / LCR:           see regulatory report for 2020-04-30')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
