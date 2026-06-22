"""
advance_to_jul2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-06-30 to 2020-07-31.

Real-world context — July 2020:
  - Unlock 3.0 effective July 1: gyms, yoga centres, religious places open;
    most economic activity now permitted except containment zones
  - COVID-19 cases still rising (India's first wave peaks in Sep 2020), but
    the government commits to no fresh national lockdown
  - RBI repo rate held at 4.00% (MPC met August 6 — no July action)
  - Moratorium still in force (deadline: August 31, 2020); borrowers now
    aware the extension will NOT be renewed — opt-out pace accelerates
  - Q1 FY2021 GDP data (released Aug 28) will show -23.9% contraction —
    worst ever; banks begin bracing for post-moratorium cliff
  - Kharif sowing season: agricultural credit demand picks up — bank
    disburses Kisan Credit Card (KCC) and farm equipment loans
  - ECLGS disbursals continue; total national sanctions approach Rs 1.5L Cr
  - Auto sector shows first month of positive wholesale numbers since lockdown
  - COVID contingency provision: FINAL month of our 4-month spread
    (April–July); total 10% of moratorium book now fully provisioned

Effects simulated:
  1. Moratorium opt-outs accelerate: net moratorium eases from 33% to 31%
  2. DPD aging: existing NPA loans age +30 days; Sub-Standard loans that
     reach 180 DPD move to Doubtful-1; fresh standard NPA formation (~8 loans)
     in hospitality / retail / unsecured personal segment
  3. New disbursals: 30 loans (agri/KCC + ECLGS + housing + auto)
  4. Balance sheet JUL2020:
       - Deposits +1.5% (continued but moderating inflow)
       - Advances up (new disbursals, net of normal repayments)
  5. Monthly P&L JUL2020:
       - NII marginally higher (loan book growth + lower deposit rates)
       - COVID provision: FINAL monthly charge (month 4 of 4)
       - After this month provisions normalise — path to PAT recovery begins
  6. Regulatory batch re-run for 2020-07-31
  7. simulation_clock.json advanced

Run: python operations/scripts/advance_to_jul2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID      = 'BANK010'
PREV_DATE    = '2020-06-30'
PREV_PERIOD  = 'JUN2020'
NEW_DATE     = '2020-07-31'
NEW_PERIOD   = 'JUL2020'

MORATORIUM_TARGET_RATE = 0.31   # accelerating opt-outs; down from 33%
DEPOSIT_GROWTH         = 0.015  # +1.5% (moderating)
REPO_RATE_JUL          = 4.00   # unchanged
COVID_PROV_MONTH       = 4      # FINAL month of 4-month COVID provision cycle

BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 30 new loans — agri/KCC season + ECLGS tail + housing + auto recovery
NEW_LOAN_SPECS = [
    # Kisan Credit Card / agricultural loans (Kharif sowing season)
    ('Business Loan', 500000,   8.50, 12, 'agri-kcc'),
    ('Business Loan', 350000,   8.50, 12, 'agri-kcc'),
    ('Business Loan', 750000,   8.50, 12, 'agri-kcc'),
    ('Business Loan', 420000,   8.50, 12, 'agri-kcc'),
    ('Business Loan', 600000,   8.50, 12, 'agri-kcc'),
    # ECLGS tail (late sanctions reaching disbursement)
    ('Business Loan', 2000000,  9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3200000,  9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1800000,  9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2600000,  9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1400000,  9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 4000000,  9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2200000,  9.00, 48, 'MSME-ECLGS'),
    # Housing (Unlock 3.0 — stamp duty waivers in Maharashtra announced)
    ('Home Loan', 5500000, 8.10, 240, 'housing-unlock3'),
    ('Home Loan', 4200000, 8.10, 180, 'housing-unlock3'),
    ('Home Loan', 3800000, 8.10, 240, 'housing-unlock3'),
    ('Home Loan', 6800000, 8.10, 300, 'housing-unlock3'),
    ('Home Loan', 3200000, 8.10, 120, 'housing-unlock3'),
    ('Home Loan', 4600000, 8.10, 240, 'housing-unlock3'),
    # Vehicle / Auto (wholesale volumes positive; retail EMI schemes)
    ('Vehicle Loan', 1200000, 11.00, 60, 'auto-recovery'),
    ('Vehicle Loan',  900000, 11.00, 48, 'auto-recovery'),
    ('Vehicle Loan', 1600000, 11.00, 60, 'auto-recovery'),
    ('Vehicle Loan',  750000, 11.00, 48, 'auto-recovery'),
    ('Vehicle Loan', 1050000, 11.00, 60, 'auto-recovery'),
    # Personal / Education
    ('Personal Loan',  700000, 12.75, 48, 'personal-recovery'),
    ('Personal Loan',  550000, 12.75, 36, 'personal-recovery'),
    ('Personal Loan',  900000, 12.75, 48, 'personal-recovery'),
    ('Education Loan', 900000, 11.25, 72, 'education-recovery'),
    ('Education Loan', 650000, 11.25, 60, 'education-recovery'),
    ('Personal Loan',  480000, 12.75, 24, 'personal-recovery'),
    ('Personal Loan',  620000, 12.75, 36, 'personal-recovery'),
]


def _emi(p, r_annual, t_months):
    r = r_annual / 100 / 12
    if r == 0:
        return p / t_months
    return p * r * (1+r)**t_months / ((1+r)**t_months - 1)


EXPOSURE_MAP = {
    'Business Loan':  'corporate',
    'Home Loan':      'retail_secured',
    'Vehicle Loan':   'retail_secured',
    'Personal Loan':  'retail_unsecured',
    'Education Loan': 'retail_unsecured',
}


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_07)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-06-30 --> 2020-07-31')
    p('  Unlock 3.0 | Kharif season | FINAL COVID provision month')
    p('=' * 68)

    # ── Step 1: Moratorium opt-outs (accelerating) ────────────────────────────
    total_eligible_loans = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND days_past_due < 90",
        (BANK_ID,)).fetchone()[0]
    current_morat = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND moratorium=1",
        (BANK_ID,)).fetchone()[0]
    target_morat   = int(total_eligible_loans * MORATORIUM_TARGET_RATE)
    opt_out_count  = max(0, current_morat - target_morat)

    if opt_out_count > 0:
        morat_loans = [r[0] for r in cur.execute(
            "SELECT id FROM loans WHERE bank_id=? AND moratorium=1 ORDER BY RANDOM() LIMIT ?",
            (BANK_ID, opt_out_count)).fetchall()]
        cur.execute(
            "UPDATE loans SET moratorium=0, moratorium_end_date=NULL "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(morat_loans))),
            [BANK_ID] + morat_loans)

    remaining_morat = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans "
        "WHERE bank_id=? AND moratorium=1", (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[1] Moratorium opt-outs accelerate: {opt_out_count} borrowers exited')
    p(f'    Remaining moratorium: {remaining_morat[0]:,} loans ({MORATORIUM_TARGET_RATE*100:.0f}% of book)')
    p(f'    Moratorium book: Rs{remaining_morat[1]/1e7:.1f} Cr')
    p(f'    Deadline approaching: Aug 31 end-of-moratorium visible to borrowers')

    # ── Step 2: DPD aging + NPA classification ────────────────────────────────
    # Reset seed-artefact DPD (<90) on Standard/Performing non-moratorium loans
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0
          AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))

    # Age existing NPA-classified loans (DPD >= 90) by +30 days
    cur.execute("""
        UPDATE loans SET days_past_due = MIN(days_past_due + 30, 360)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

    # Sub-Standard at 180+ DPD -> Doubtful-1
    newly_doubtful = cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification='Sub-Standard'
    """, (BANK_ID,)).fetchone()
    cur.execute("""
        UPDATE loans SET loan_classification='Doubtful-1'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification='Sub-Standard'
    """, (BANK_ID,))

    # Fresh NPA formation: hospitality, retail, unsecured personal (COVID stress)
    random.seed(20200701)
    fresh_npa_pool = [dict(r) for r in cur.execute("""
        SELECT id, outstanding FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due=0
          AND loan_classification IN ('Standard','Performing')
          AND type IN ('Personal Loan','Vehicle Loan','Business Loan')
        ORDER BY outstanding DESC LIMIT 200
    """, (BANK_ID,)).fetchall()]
    random.shuffle(fresh_npa_pool)
    fresh_npa_loans = fresh_npa_pool[:8]
    fresh_npa_amt   = sum(l['outstanding'] for l in fresh_npa_loans)
    if fresh_npa_loans:
        fids = [l['id'] for l in fresh_npa_loans]
        cur.execute(
            "UPDATE loans SET days_past_due=93, loan_classification='Sub-Standard' "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(fids))),
            [BANK_ID] + fids)

    total_npa = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans "
        "WHERE bank_id=? AND days_past_due>=90 AND moratorium=0", (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[2] DPD aged +30 days for existing NPA loans')
    p(f'    Upgraded to Doubtful-1: {newly_doubtful[0]} loans (Rs{newly_doubtful[1]/1e7:.2f} Cr) [180+ DPD]')
    p(f'    Fresh Sub-Standard:     {len(fresh_npa_loans)} loans (Rs{fresh_npa_amt/1e7:.2f} Cr) [hospitality/retail]')
    p(f'    Total NPA book:         {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')

    # ── Step 3: New disbursals (30 loans) ────────────────────────────────────
    no_loan_custs = [dict(r) for r in cur.execute("""
        SELECT id FROM customers WHERE bank_id=?
        AND NOT EXISTS (SELECT 1 FROM loans WHERE cid=customers.id AND bank_id=?)
        LIMIT 40
    """, (BANK_ID, BANK_ID)).fetchall()]

    now = datetime.now().isoformat(timespec='seconds')
    disbursed_count = 0
    total_new_principal = 0.0

    for i, (ltype, principal, rate, tenure, sector) in enumerate(NEW_LOAN_SPECS):
        if i >= len(no_loan_custs):
            break
        loan_id = f'LOAN-JUL2020-{i+1:02d}'
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
            (date(2020, 7, 31) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype, 'retail_unsecured'),
            0, 0, None, f'jul2020_{sector}'
        ))
        disbursed_count += 1
        total_new_principal += principal

    conn.commit()
    agri_count  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'agri' in s[4])
    eclgs_count = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'ECLGS' in s[4])
    p(f'\n[3] New disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'    {agri_count} Agri/KCC + {eclgs_count} MSME-ECLGS + 6 Housing + 5 Vehicle + 5 Personal/Edu')

    # ── Step 4: Balance sheet JUL2020 ────────────────────────────────────────
    prev_bs = dict(cur.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?",
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_dep = (prev_bs['deposits_demand'] + prev_bs['deposits_savings']
                + prev_bs['deposits_term'])
    new_dep  = prev_dep * (1 + DEPOSIT_GROWTH)
    new_adv  = cur.execute(
        "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?",
        (BANK_ID,)).fetchone()[0]

    morat_book = remaining_morat[1]
    # Final COVID provision month — same monthly charge as before
    covid_prov_monthly = morat_book * 0.10 / 3

    capital_base     = prev_bs['equity_capital'] + prev_bs['reserves_surplus']
    equity_capital   = prev_bs['equity_capital']
    reserves_surplus = prev_bs['reserves_surplus']

    deposits_demand  = 0.12 * new_dep
    deposits_savings = 0.48 * new_dep
    deposits_term    = new_dep - deposits_demand - deposits_savings
    other_liabilities = 0.040 * new_dep + covid_prov_monthly

    total_lc = capital_base + new_dep + other_liabilities

    cash_with_rbi     = 0.030 * new_dep
    investments       = 0.190 * new_dep   # slight reduction as loan book grows
    fixed_assets      = prev_bs['fixed_assets']
    intangible_assets = prev_bs['intangible_assets']
    other_assets      = 0.050 * new_adv

    fixed_sum = (cash_with_rbi + investments + new_adv
                 + fixed_assets + intangible_assets + other_assets)
    gap = total_lc - fixed_sum
    balances_with_banks = max(0.0, gap)
    borrowings          = max(0.0, -gap)
    total_assets        = fixed_sum + balances_with_banks

    cur.execute("DELETE FROM bank_balance_sheet WHERE bank_id=? AND period=?",
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
        round(equity_capital, 2), round(reserves_surplus, 2),
        round(deposits_demand, 2), round(deposits_savings, 2), round(deposits_term, 2),
        round(borrowings, 2), round(other_liabilities, 2),
        round(cash_with_rbi, 2), round(balances_with_banks, 2), round(investments, 2),
        round(new_adv, 2), round(fixed_assets, 2), round(intangible_assets, 2),
        round(other_assets, 2),
        round(0.60 * total_assets, 2), round(0.05 * total_assets, 2),
        'advance_to_jul2020', now
    ))
    conn.commit()

    ta_chk = fixed_sum + balances_with_banks
    tl_chk = capital_base + new_dep + borrowings + other_liabilities
    p(f'\n[4] Balance sheet JUL2020 seeded')
    p(f'    Total Assets: Rs{ta_chk/1e7:.1f} Cr  |  L+C: Rs{tl_chk/1e7:.1f} Cr  |  Diff: {abs(ta_chk-tl_chk):.2f}')
    p(f'    Advances: Rs{new_adv/1e7:.1f} Cr  |  Deposits: Rs{new_dep/1e7:.1f} Cr')

    # ── Step 5: Monthly P&L JUL2020 ──────────────────────────────────────────
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 10.50
    # Minimal further rate transmission in July (repo on hold)
    effective_rate = blended_rate - 0.05

    int_on_adv   = round(new_adv     * effective_rate / 100 / 12, 2)
    int_on_inv   = round(investments * 5.95 / 100 / 12, 2)   # G-Sec yields drifting lower
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.150, 2)               # fee income recovering

    deposit_rate      = 4.00   # banks aggressively cut TD rates; SB at 3%
    int_on_dep        = round(new_dep   * deposit_rate / 100 / 12, 2)
    int_on_borrowings = round(borrowings * 4.60 / 100 / 12, 2)
    int_expended      = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)

    employee_cost = round(nii * 0.275, 2)
    other_opex    = round(nii * 0.165, 2)
    opex          = round(employee_cost + other_opex, 2)
    op_profit     = round(nii + other_income - opex, 2)

    normal_prov      = round(new_adv * 0.005 / 12, 2)
    covid_prov       = round(covid_prov_monthly, 2)
    doubtful_prov    = round(newly_doubtful[1] * 0.10, 2)   # incremental Doubtful-1 top-up
    substandard_prov = round(fresh_npa_amt     * 0.15, 2)   # 15% on fresh Sub-Standard
    provisions       = round(normal_prov + covid_prov + doubtful_prov + substandard_prov, 2)

    pbt = round(op_profit - provisions, 2)
    tax = round(max(0, pbt * 0.25), 2)
    pat = round(pbt - tax, 2)

    cur.execute("DELETE FROM bank_profit_loss WHERE bank_id=? AND period=?",
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
        "INSERT OR REPLACE INTO bank_profit_loss ({}) VALUES ({})".format(
            ','.join(pl_cols), ','.join('?'*len(pl_cols))),
        [BANK_ID, NEW_PERIOD, '2020-07-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[5] Monthly P&L JUL2020 seeded')
    p(f'    NII:                     Rs{nii/1e7:.2f} Cr  (lending ~{effective_rate:.2f}%, deposit {deposit_rate}%)')
    p(f'    COVID provision:         Rs{covid_prov/1e7:.2f} Cr  (FINAL month — cycle ends Jul)')
    p(f'    Doubtful-1 top-up prov:  Rs{doubtful_prov/1e7:.2f} Cr')
    p(f'    Sub-Standard prov:       Rs{substandard_prov/1e7:.2f} Cr  ({len(fresh_npa_loans)} loans)')
    p(f'    Total provisions:        Rs{provisions/1e7:.2f} Cr')
    p(f'    PBT: Rs{pbt/1e7:.2f} Cr  |  PAT: Rs{pat/1e7:.2f} Cr')
    p(f'    --> COVID provision cycle ends this month; Aug onwards normalises')

    # ── Step 6: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    scripts = os.path.join(_REPO_ROOT, 'operations', 'scripts')
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch', os.path.join(scripts, 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=False)
    p('\n[6] Regulatory batch re-run for 2020-07-31')

    # ── Step 7: Advance clock ─────────────────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = (
        'Unlock 3.0 full month. RBI repo 4.00% (unchanged). '
        f'Moratorium opt-outs accelerating (33%->31%, {opt_out_count} exits). '
        f'{newly_doubtful[0]} loans to Doubtful-1 (180+ DPD). '
        f'{len(fresh_npa_loans)} fresh Sub-Standard NPAs (hospitality/retail). '
        f'{disbursed_count} disbursals (Kharif agri + ECLGS tail + housing + auto). '
        'FINAL COVID provision month — Aug onwards provisions normalise. '
        'Moratorium deadline Aug 31 approaching.'
    )
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[7] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Summary ───────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  JULY 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Total Assets:          Rs{ta_chk/1e7:.1f} Cr')
    p(f'  Advances (net):        Rs{new_adv/1e7:.1f} Cr')
    p(f'  Deposits:              Rs{new_dep/1e7:.1f} Cr')
    p(f'  Moratorium loans:      {remaining_morat[0]:,} ({MORATORIUM_TARGET_RATE*100:.0f}% of book)  '
      f'book: Rs{remaining_morat[1]/1e7:.1f} Cr  [opt-outs: {opt_out_count}]')
    p(f'  Doubtful-1 (new):      {newly_doubtful[0]} loans (Rs{newly_doubtful[1]/1e7:.2f} Cr)')
    p(f'  Fresh Sub-Standard:    {len(fresh_npa_loans)} loans (Rs{fresh_npa_amt/1e7:.2f} Cr)')
    p(f'  Total NPA:             {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')
    p(f'  New disbursals:        {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'  Monthly NII:           Rs{nii/1e7:.2f} Cr')
    p(f'  Monthly provisions:    Rs{provisions/1e7:.2f} Cr  [COVID cycle ENDS]')
    p(f'  Monthly PAT:           Rs{pat/1e7:.2f} Cr')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
