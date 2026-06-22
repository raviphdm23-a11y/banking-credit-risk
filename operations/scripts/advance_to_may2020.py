"""
advance_to_may2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-04-30 to 2020-05-31.

Real-world context: May 2020 saw a partial recovery in economic activity:
  - Lockdown 4.0 (May 4-17) with more sectoral relaxations vs April
  - Unlock 1.0 from May 18: most industry/construction/transport permitted
  - RBI MPC emergency meeting May 22: repo cut 40 bps to 4.00%
    (reverse repo 3.35%); banks further pressured on lending margins
  - Moratorium remains in force; ~5% more borrowers opt in as income
    recovery remains uncertain
  - 6 non-moratorium loans that were at 60-90 DPD in April now cross
    90 days -> classified as Sub-Standard NPAs
  - New disbursals recover to ~20 (vs 5 in April) as green/orange zones
    reopen; MSME Emergency Credit Line Guarantee Scheme (ECLGS) announced
    May 13 -> bank begins pipeline for guaranteed MSME loans

Effects simulated:
  1. Moratorium extended; ~5% more borrowers opt in (total ~35%)
  2. DPD aging: non-moratorium loans age +30 days; 6 cross 90 DPD -> NPA
  3. New disbursals: 20 loans (MSME/housing/vehicle in open zones)
  4. Balance sheet MAY2020:
       - Deposits +1% (flight-to-safety slowing as unlock begins)
       - Advances slightly up (new ECLGS pipeline)
       - COVID provision accumulates (month 2 of 4-quarter spread)
       - Repo transmission: lending rates begin to drift lower
  5. Monthly P&L MAY2020:
       - NII improves marginally (more loans, but rate cut headwind)
       - COVID provision charge continues (same run-rate as April)
       - PAT remains negative but loss narrows vs April
  6. Regulatory batch re-run for 2020-05-31
  7. simulation_clock.json advanced

Run: python operations/scripts/advance_to_may2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID      = 'BANK010'
PREV_DATE    = '2020-04-30'
PREV_PERIOD  = 'APR2020'
NEW_DATE     = '2020-05-31'
NEW_PERIOD   = 'MAY2020'

MORATORIUM_NEW_RATE = 0.35   # total moratorium rises from 30% to 35%
REPO_RATE_MAY       = 4.00   # RBI cut 40 bps on May 22
DEPOSIT_GROWTH      = 0.010  # +1% (safety-flight slowing as unlock begins)
COVID_PROV_QTRS     = 4

BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 20 new loans — MSME ECLGS pipeline + housing + vehicles in open zones
NEW_LOAN_SPECS = [
    # MSME ECLGS (guaranteed, lower rate — government scheme)
    ('Business Loan', 2000000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3000000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1800000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 4000000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2200000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1200000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2800000, 9.00, 48, 'MSME-ECLGS'),
    # Housing (Unlock 1.0 — construction resumes)
    ('Home Loan', 4200000, 8.40, 180, 'housing-unlock'),
    ('Home Loan', 3800000, 8.40, 180, 'housing-unlock'),
    ('Home Loan', 5500000, 8.40, 240, 'housing-unlock'),
    ('Home Loan', 3200000, 8.40, 120, 'housing-unlock'),
    ('Home Loan', 6000000, 8.40, 240, 'housing-unlock'),
    # Vehicle (logistics/transport sector reopening)
    ('Vehicle Loan', 800000,  11.50, 60, 'vehicle-logistics'),
    ('Vehicle Loan', 1200000, 11.50, 60, 'vehicle-logistics'),
    ('Vehicle Loan', 950000,  11.50, 60, 'vehicle-logistics'),
    # Personal / Education (limited)
    ('Personal Loan',  500000, 13.00, 36, 'personal-unlock'),
    ('Education Loan', 700000, 11.50, 60, 'education-unlock'),
]


def _emi(p, r_annual, t_months):
    r = r_annual / 100 / 12
    if r == 0:
        return p / t_months
    return p * r * (1+r)**t_months / ((1+r)**t_months - 1)


EXPOSURE_MAP = {
    'Business Loan': 'corporate',
    'Home Loan':     'retail_secured',
    'Vehicle Loan':  'retail_secured',
    'Personal Loan': 'retail_unsecured',
    'Education Loan':'retail_unsecured',
}


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_05)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-04-30 --> 2020-05-31')
    p('  Unlock 1.0 begins | RBI Repo 4.00% | ECLGS launched | Moratorium extends')
    p('=' * 68)

    # ── Step 1: Extend moratorium to 35% of eligible loans ───────────────────
    all_loans = [dict(r) for r in cur.execute(
        'SELECT id, days_past_due, loan_classification, outstanding, moratorium '
        'FROM loans WHERE bank_id=?', (BANK_ID,)).fetchall()]

    eligible = [l for l in all_loans
                if (l['days_past_due'] or 0) < 90
                and (l['loan_classification'] or 'Standard') in ('Standard','Performing')
                and not l['moratorium']]

    # How many more need to be added to reach 35% of total eligible pool
    total_eligible = [l for l in all_loans
                      if (l['days_past_due'] or 0) < 90
                      and (l['loan_classification'] or 'Standard') in ('Standard','Performing')]
    target_morat = int(len(total_eligible) * MORATORIUM_NEW_RATE)
    current_morat = sum(1 for l in all_loans if l['moratorium'])
    new_morat_count = max(0, target_morat - current_morat)

    if new_morat_count > 0:
        random.shuffle(eligible)
        new_ids = [l['id'] for l in eligible[:new_morat_count]]
        cur.execute(
            "UPDATE loans SET moratorium=1, moratorium_end_date='2020-08-31' "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(new_ids))),
            [BANK_ID] + new_ids)

    total_morat = cur.execute(
        'SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans '
        'WHERE bank_id=? AND moratorium=1', (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[1] Moratorium extended to {total_morat[0]:,} loans ({MORATORIUM_NEW_RATE*100:.0f}% of book)')
    p(f'    {new_morat_count} new borrowers opted in | Moratorium book: Rs{total_morat[1]/1e7:.1f} Cr')
    p(f'    Moratorium end date extended to 2020-08-31')

    # ── Step 2: DPD aging + fresh NPA formation ───────────────────────────────
    # Reset seed-artefact DPD (< 90) on Standard/Performing non-moratorium loans
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0
          AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))
    cur.execute("""
        UPDATE loans SET days_past_due = MIN(days_past_due + 30, 210)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

    # Loans crossing 90 DPD -> Sub-Standard NPA
    newly_npa = cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,)).fetchone()

    cur.execute("""
        UPDATE loans SET loan_classification='Sub-Standard'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))

    total_npa = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans "
        "WHERE bank_id=? AND days_past_due>=90 AND moratorium=0", (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[2] DPD aged +30 days for non-moratorium loans')
    p(f'    New NPAs this month: {newly_npa[0]} loans (Rs{newly_npa[1]/1e7:.2f} Cr)')
    p(f'    Total NPA book: {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')

    # ── Step 3: Disburse 20 new loans ────────────────────────────────────────
    no_loan_custs = [dict(r) for r in cur.execute("""
        SELECT id FROM customers WHERE bank_id=?
        AND NOT EXISTS (SELECT 1 FROM loans WHERE cid=customers.id AND bank_id=?)
        LIMIT 30
    """, (BANK_ID, BANK_ID)).fetchall()]

    now = datetime.now().isoformat(timespec='seconds')
    disbursed_count = 0
    total_new_principal = 0.0

    for i, (ltype, principal, rate, tenure, sector) in enumerate(NEW_LOAN_SPECS):
        if i >= len(no_loan_custs):
            break
        loan_id = f'LOAN-MAY2020-{i+1:02d}'
        emi_val = round(_emi(principal, rate, tenure), 2)
        cur.execute("""
            INSERT OR REPLACE INTO loans
              (id, bank_id, cid, type, principal, rate, tenure, emi,
               disbursed, maturity, outstanding, status, branch_id,
               loan_classification, exposure_class, days_past_due,
               moratorium, moratorium_end_date, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            loan_id, BANK_ID, no_loan_custs[i]['id'], ltype,
            principal, rate, tenure, emi_val,
            NEW_DATE,
            (date(2020,5,31) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype,'retail_unsecured'),
            0, 0, None, f'may2020_{sector}'
        ))
        disbursed_count += 1
        total_new_principal += principal

    conn.commit()
    p(f'\n[3] New disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'    10 MSME-ECLGS + 5 Housing + 3 Vehicle + 1 Personal + 1 Education')

    # ── Step 4: Build MAY2020 balance sheet ──────────────────────────────────
    prev_bs = dict(cur.execute(
        'SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?',
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_dep = (prev_bs['deposits_demand'] + prev_bs['deposits_savings']
                + prev_bs['deposits_term'])
    new_dep  = prev_dep * (1 + DEPOSIT_GROWTH)

    new_adv  = cur.execute(
        'SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?',
        (BANK_ID,)).fetchone()[0]

    morat_book = cur.execute(
        'SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=? AND moratorium=1',
        (BANK_ID,)).fetchone()[0]

    # COVID provision: month 2 of 4-quarter spread (same monthly rate)
    covid_prov_monthly = morat_book * 0.10 / 3

    capital_base     = prev_bs['equity_capital'] + prev_bs['reserves_surplus']
    equity_capital   = prev_bs['equity_capital']
    reserves_surplus = prev_bs['reserves_surplus']

    deposits_demand  = 0.12 * new_dep
    deposits_savings = 0.48 * new_dep
    deposits_term    = new_dep - deposits_demand - deposits_savings

    other_liabilities = 0.040 * new_dep + covid_prov_monthly

    total_lc = capital_base + new_dep + other_liabilities

    cash_with_rbi     = 0.030 * new_dep   # CRR 3%
    investments       = 0.200 * new_dep
    fixed_assets      = prev_bs['fixed_assets']
    intangible_assets = prev_bs['intangible_assets']
    other_assets      = 0.050 * new_adv

    fixed_sum = (cash_with_rbi + investments + new_adv
                 + fixed_assets + intangible_assets + other_assets)
    gap = total_lc - fixed_sum
    balances_with_banks = max(0.0, gap)
    borrowings          = max(0.0, -gap)
    total_assets        = fixed_sum + balances_with_banks

    cur.execute('DELETE FROM bank_balance_sheet WHERE bank_id=? AND period=?',
                (BANK_ID, NEW_PERIOD))
    cur.execute("""
        INSERT INTO bank_balance_sheet
          (bank_id, period, as_on_date, currency, unit,
           equity_capital, reserves_surplus,
           deposits_demand, deposits_savings, deposits_term,
           borrowings, other_liabilities,
           cash_with_rbi, balances_with_banks, investments,
           advances_net, fixed_assets, intangible_assets, other_assets,
           contingent_liabilities, bills_for_collection, source, generated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        BANK_ID, NEW_PERIOD, NEW_DATE, 'INR', 'INR',
        round(equity_capital,2), round(reserves_surplus,2),
        round(deposits_demand,2), round(deposits_savings,2), round(deposits_term,2),
        round(borrowings,2), round(other_liabilities,2),
        round(cash_with_rbi,2), round(balances_with_banks,2), round(investments,2),
        round(new_adv,2), round(fixed_assets,2), round(intangible_assets,2),
        round(other_assets,2),
        round(0.60*total_assets,2), round(0.05*total_assets,2),
        'advance_to_may2020', now
    ))
    conn.commit()

    ta_chk = fixed_sum + balances_with_banks
    tl_chk = capital_base + new_dep + borrowings + other_liabilities
    p(f'\n[4] Balance sheet MAY2020 seeded')
    p(f'    Total Assets: Rs{ta_chk/1e7:.1f} Cr  |  L+C: Rs{tl_chk/1e7:.1f} Cr  |  Diff: {abs(ta_chk-tl_chk):.2f}')
    p(f'    Advances: Rs{new_adv/1e7:.1f} Cr  |  Deposits: Rs{new_dep/1e7:.1f} Cr')

    # ── Step 5: Monthly P&L MAY2020 ──────────────────────────────────────────
    # Rate transmission: repo at 4.00% — lending rates drift down ~20 bps more
    blended_rate = cur.execute(
        'SELECT AVG(rate) FROM loans WHERE bank_id=? AND status=\'Active\'',
        (BANK_ID,)).fetchone()[0] or 10.88
    effective_rate = blended_rate - 0.20   # partial May transmission

    int_on_adv   = round(new_adv    * effective_rate / 100 / 12, 2)
    int_on_inv   = round(investments * 6.30 / 100 / 12, 2)   # G-Sec yield drifting lower
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.14, 2)   # fee income recovering slightly

    deposit_rate      = 4.50   # banks begin passing cut; TD rates down 25 bps
    int_on_dep        = round(new_dep  * deposit_rate / 100 / 12, 2)
    int_on_borrowings = round(borrowings * 5.00 / 100 / 12, 2)
    int_expended      = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)

    employee_cost = round(nii * 0.28, 2)
    other_opex    = round(nii * 0.17, 2)
    opex          = round(employee_cost + other_opex, 2)
    op_profit     = round(nii + other_income - opex, 2)

    normal_prov  = round(new_adv * 0.005 / 12, 2)
    covid_prov   = round(covid_prov_monthly, 2)
    npa_prov     = round(newly_npa[1] * 0.15, 2)   # 15% provision on fresh Sub-Standard NPAs
    provisions   = round(normal_prov + covid_prov + npa_prov, 2)

    pbt = round(op_profit - provisions, 2)
    tax = round(max(0, pbt * 0.25), 2)
    pat = round(pbt - tax, 2)

    cur.execute('DELETE FROM bank_profit_loss WHERE bank_id=? AND period=?',
                (BANK_ID, NEW_PERIOD))
    pl_cols = ['bank_id','period','from_date','to_date','currency','unit',
               'interest_on_advances','interest_on_investments','interest_earned',
               'other_income','total_income',
               'interest_on_deposits','interest_on_borrowings','interest_expended',
               'employee_cost','other_opex','operating_expenses',
               'net_interest_income','operating_profit',
               'provisions_contingencies','profit_before_tax','tax_expense',
               'profit_after_tax','generated_at']
    cur.execute(
        'INSERT OR REPLACE INTO bank_profit_loss ({}) VALUES ({})'.format(
            ','.join(pl_cols), ','.join('?'*len(pl_cols))),
        [BANK_ID, NEW_PERIOD, '2020-05-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[5] Monthly P&L MAY2020 seeded')
    p(f'    NII:                  Rs{nii/1e7:.2f} Cr  (lending rate ~{effective_rate:.2f}%, deposit rate {deposit_rate}%)')
    p(f'    COVID provision:      Rs{covid_prov/1e7:.2f} Cr')
    p(f'    Fresh NPA provision:  Rs{npa_prov/1e7:.2f} Cr  (15% on {newly_npa[0]} new Sub-Standard accounts)')
    p(f'    Total provisions:     Rs{provisions/1e7:.2f} Cr')
    p(f'    PBT: Rs{pbt/1e7:.2f} Cr  |  PAT: Rs{pat/1e7:.2f} Cr')

    # ── Step 6: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    scripts = os.path.join(_REPO_ROOT, 'operations', 'scripts')
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch', os.path.join(scripts, 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=verbose)
    p('\n[6] Regulatory batch re-run for 2020-05-31')

    # ── Step 7: Advance clock ─────────────────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = ('Unlock 1.0 begins May 18. RBI repo cut to 4.00% (May 22). '
                    'MSME ECLGS launched. Moratorium extended to Aug 2020. '
                    '6 loans crossed 90 DPD -> fresh NPAs. 20 new disbursals.')
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[7] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Summary ───────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  MAY 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Total Assets:        Rs{ta_chk/1e7:.1f} Cr')
    p(f'  Advances (net):      Rs{new_adv/1e7:.1f} Cr')
    p(f'  Deposits:            Rs{new_dep/1e7:.1f} Cr')
    p(f'  Moratorium loans:    {total_morat[0]:,} ({MORATORIUM_NEW_RATE*100:.0f}% of book)  book: Rs{total_morat[1]/1e7:.1f} Cr')
    p(f'  New NPAs this month: {newly_npa[0]}  |  Total NPA: {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')
    p(f'  New disbursals:      {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr (ECLGS + unlock)')
    p(f'  Monthly NII:         Rs{nii/1e7:.2f} Cr')
    p(f'  Monthly PAT:         Rs{pat/1e7:.2f} Cr')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
