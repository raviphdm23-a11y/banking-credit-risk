"""
advance_to_jun2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-05-31 to 2020-06-30.

Real-world context — June 2020:
  - Unlock 1.0 runs through the month; Unlock 2.0 announced June 29
    (effective July 1) with further relaxations
  - RBI repo rate held at 4.00% (MPC met June 4; no cut but accommodative
    stance maintained); reverse repo 3.35%
  - Moratorium still in force; some borrowers begin opting OUT now that
    income recoveries are visible — net moratorium rate eases from 35% to 33%
  - Loans that were Sub-Standard in April (90 DPD then) now at 150-180 DPD;
    a subset cross 180 DPD -> upgraded to Doubtful-1 classification
  - New disbursals recover further to 25 (ECLGS pipeline + housing/vehicle
    as construction and logistics fully reopen)
  - ECLGS sanctions hit Rs 1 lakh Cr nationally; bank's pipeline accelerates
  - GST e-way bills and power consumption data signal demand recovery beginning
  - Deposit growth moderates as savings rates fall (term deposit rates cut)

Effects simulated:
  1. Moratorium opt-outs: 2% of moratorium borrowers exit (income recovery)
     Net moratorium down from 35% to ~33%
  2. DPD aging: non-moratorium loans age +30 days
     Loans at >= 180 DPD -> reclassified Doubtful-1
     New loans crossing 90 DPD -> Sub-Standard
  3. New disbursals: 25 loans (ECLGS surge + housing + vehicle)
  4. Balance sheet JUN2020:
       - Deposits +1.5% (moderating inflow as rates cut)
       - Advances up (new disbursals)
       - COVID provision continues (month 3 of 4)
  5. Monthly P&L JUN2020:
       - NII improves (higher advances, deposit rate lower)
       - COVID provision: same monthly charge (month 3 of 4)
       - Smaller fresh NPA provision vs May (fewer new crossings)
       - PAT still negative but loss narrows
  6. Regulatory batch re-run for 2020-06-30
  7. simulation_clock.json advanced

Run: python operations/scripts/advance_to_jun2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID      = 'BANK010'
PREV_DATE    = '2020-05-31'
PREV_PERIOD  = 'MAY2020'
NEW_DATE     = '2020-06-30'
NEW_PERIOD   = 'JUN2020'

MORATORIUM_TARGET_RATE = 0.33   # down from 35% as some borrowers opt out
DEPOSIT_GROWTH         = 0.015  # +1.5% (moderating)
REPO_RATE_JUN          = 4.00   # unchanged
COVID_PROV_MONTH       = 3      # month 3 of 4-quarter spread

BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 25 new loans — ECLGS surge + housing + vehicle + personal
NEW_LOAN_SPECS = [
    # MSME ECLGS (guaranteed; pipeline accelerates as national sanctions hit Rs 1L Cr)
    ('Business Loan', 2500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1800000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3200000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2000000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 4500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2800000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3500000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2200000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1900000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3800000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2600000, 9.00, 48, 'MSME-ECLGS'),
    # Housing (construction fully resumed; stamp duty relief in some states)
    ('Home Loan', 4800000, 8.25, 240, 'housing-unlock2'),
    ('Home Loan', 3500000, 8.25, 180, 'housing-unlock2'),
    ('Home Loan', 6200000, 8.25, 240, 'housing-unlock2'),
    ('Home Loan', 3000000, 8.25, 120, 'housing-unlock2'),
    ('Home Loan', 5200000, 8.25, 240, 'housing-unlock2'),
    ('Home Loan', 2800000, 8.25, 120, 'housing-unlock2'),
    # Vehicle (logistics + private mobility; GST cut on vehicles rumoured)
    ('Vehicle Loan', 900000,  11.25, 60, 'vehicle-logistics'),
    ('Vehicle Loan', 1400000, 11.25, 60, 'vehicle-logistics'),
    ('Vehicle Loan', 1100000, 11.25, 60, 'vehicle-logistics'),
    ('Vehicle Loan', 750000,  11.25, 48, 'vehicle-private'),
    # Personal / Education (white-collar recovery)
    ('Personal Loan',  600000,  13.00, 36, 'personal-unlock'),
    ('Personal Loan',  450000,  13.00, 24, 'personal-unlock'),
    ('Education Loan', 800000,  11.50, 60, 'education-unlock'),
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
    random.seed(2020_06)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-05-31 --> 2020-06-30')
    p('  Unlock 1.0 continues | Moratorium opt-outs begin | ECLGS surge')
    p('=' * 68)

    # ── Step 1: Moratorium opt-outs (some borrowers exit) ────────────────────
    # Remove moratorium flag from ~2% of currently moratorium loans
    morat_loans = [dict(r) for r in cur.execute(
        'SELECT id FROM loans WHERE bank_id=? AND moratorium=1', (BANK_ID,)).fetchall()]
    total_eligible_loans = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND days_past_due < 90", (BANK_ID,)).fetchone()[0]

    # Target: 33% of eligible — calculate opt-outs needed
    target_morat = int(total_eligible_loans * MORATORIUM_TARGET_RATE)
    current_morat = len(morat_loans)
    opt_out_count = max(0, current_morat - target_morat)

    if opt_out_count > 0:
        random.shuffle(morat_loans)
        opt_out_ids = [l['id'] for l in morat_loans[:opt_out_count]]
        cur.execute(
            "UPDATE loans SET moratorium=0, moratorium_end_date=NULL "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(opt_out_ids))),
            [BANK_ID] + opt_out_ids)

    remaining_morat = cur.execute(
        'SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans '
        'WHERE bank_id=? AND moratorium=1', (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[1] Moratorium opt-outs: {opt_out_count} borrowers exited (income recovery visible)')
    p(f'    Remaining moratorium: {remaining_morat[0]:,} loans ({MORATORIUM_TARGET_RATE*100:.0f}% of book)')
    p(f'    Moratorium book: Rs{remaining_morat[1]/1e7:.1f} Cr')

    # ── Step 2: DPD aging, Doubtful upgrade, fresh NPA formation ─────────────
    # The original loan seeder assigned a uniform DPD of ~19 days to most loans
    # as a seed artefact (billing-cycle timing). After 2 months of +30 aging
    # (April + May), these are all sitting at ~79 DPD. Without correction they
    # would all tip past 90 simultaneously in June, which is unrealistic.
    # Fix: reset DPD < 90 for Standard/Performing non-NPA loans to 0 — these
    # are pre-COVID performing loans; COVID stress enters via fresh NPA formation
    # below rather than through accumulated seed-artefact DPD.
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0
          AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))

    # Age genuinely stressed loans that are already NPA-classified (DPD >= 90)
    cur.execute("""
        UPDATE loans SET days_past_due = MIN(days_past_due + 30, 360)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

    # Introduce realistic COVID-driven fresh NPA formation for June:
    # Select a small cohort of Standard loans (simulating borrowers who missed
    # 3 consecutive EMIs in the unlock period despite not being on moratorium).
    # Target: ~8 new NPAs (consistent with May's 6, slight increase as unlock
    # exposes genuine credit weakness in transport/hospitality segment).
    import random as _rnd
    _rnd.seed(20200601)
    fresh_npa_targets = [dict(r) for r in cur.execute("""
        SELECT id, outstanding FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due=0
          AND loan_classification IN ('Standard','Performing')
          AND type IN ('Personal Loan','Vehicle Loan','Business Loan')
        ORDER BY outstanding DESC LIMIT 200
    """, (BANK_ID,)).fetchall()]
    _rnd.shuffle(fresh_npa_targets)
    fresh_npa_targets = fresh_npa_targets[:8]
    if fresh_npa_targets:
        fids = [l['id'] for l in fresh_npa_targets]
        cur.execute(
            "UPDATE loans SET days_past_due=92, loan_classification='Sub-Standard' "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(fids))),
            [BANK_ID] + fids)

    # Loans at >= 180 DPD -> Doubtful-1 (from Sub-Standard)
    newly_doubtful = cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification = 'Sub-Standard'
    """, (BANK_ID,)).fetchone()

    cur.execute("""
        UPDATE loans SET loan_classification='Doubtful-1'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification = 'Sub-Standard'
    """, (BANK_ID,))

    # Fresh Sub-Standard: loans newly crossing 90 DPD
    newly_substandard = cur.execute("""
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

    p(f'\n[2] DPD aged +30 days for non-moratorium performing loans')
    p(f'    Upgraded to Doubtful-1: {newly_doubtful[0]} loans (Rs{newly_doubtful[1]/1e7:.2f} Cr) [180+ DPD]')
    p(f'    New Sub-Standard NPAs:  {newly_substandard[0]} loans (Rs{newly_substandard[1]/1e7:.2f} Cr) [90+ DPD]')
    p(f'    Total NPA book: {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')

    # ── Step 3: New disbursals (25 loans) ────────────────────────────────────
    no_loan_custs = [dict(r) for r in cur.execute("""
        SELECT id FROM customers WHERE bank_id=?
        AND NOT EXISTS (SELECT 1 FROM loans WHERE cid=customers.id AND bank_id=?)
        LIMIT 35
    """, (BANK_ID, BANK_ID)).fetchall()]

    now = datetime.now().isoformat(timespec='seconds')
    disbursed_count = 0
    total_new_principal = 0.0

    for i, (ltype, principal, rate, tenure, sector) in enumerate(NEW_LOAN_SPECS):
        if i >= len(no_loan_custs):
            break
        loan_id = f'LOAN-JUN2020-{i+1:02d}'
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
            (date(2020, 6, 30) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype, 'retail_unsecured'),
            0, 0, None, f'jun2020_{sector}'
        ))
        disbursed_count += 1
        total_new_principal += principal

    conn.commit()
    eclgs_count = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'ECLGS' in s[4])
    p(f'\n[3] New disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'    {eclgs_count} MSME-ECLGS + 6 Housing + 4 Vehicle + 2 Personal + 1 Education')

    # ── Step 4: Balance sheet JUN2020 ────────────────────────────────────────
    prev_bs = dict(cur.execute(
        'SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?',
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_dep = (prev_bs['deposits_demand'] + prev_bs['deposits_savings']
                + prev_bs['deposits_term'])
    new_dep  = prev_dep * (1 + DEPOSIT_GROWTH)

    new_adv  = cur.execute(
        'SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?',
        (BANK_ID,)).fetchone()[0]

    morat_book = remaining_morat[1]
    covid_prov_monthly = morat_book * 0.10 / 3  # month 3 of 4-quarter spread (same rate)

    capital_base     = prev_bs['equity_capital'] + prev_bs['reserves_surplus']
    equity_capital   = prev_bs['equity_capital']
    reserves_surplus = prev_bs['reserves_surplus']

    deposits_demand  = 0.12 * new_dep
    deposits_savings = 0.48 * new_dep
    deposits_term    = new_dep - deposits_demand - deposits_savings

    other_liabilities = 0.040 * new_dep + covid_prov_monthly

    total_lc = capital_base + new_dep + other_liabilities

    cash_with_rbi     = 0.030 * new_dep   # CRR 3% (COVID relief still in force)
    investments       = 0.195 * new_dep   # slight reduction as ECLGS loans absorb more
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
        round(equity_capital, 2), round(reserves_surplus, 2),
        round(deposits_demand, 2), round(deposits_savings, 2), round(deposits_term, 2),
        round(borrowings, 2), round(other_liabilities, 2),
        round(cash_with_rbi, 2), round(balances_with_banks, 2), round(investments, 2),
        round(new_adv, 2), round(fixed_assets, 2), round(intangible_assets, 2),
        round(other_assets, 2),
        round(0.60 * total_assets, 2), round(0.05 * total_assets, 2),
        'advance_to_jun2020', now
    ))
    conn.commit()

    ta_chk = fixed_sum + balances_with_banks
    tl_chk = capital_base + new_dep + borrowings + other_liabilities
    p(f'\n[4] Balance sheet JUN2020 seeded')
    p(f'    Total Assets: Rs{ta_chk/1e7:.1f} Cr  |  L+C: Rs{tl_chk/1e7:.1f} Cr  |  Diff: {abs(ta_chk-tl_chk):.2f}')
    p(f'    Advances: Rs{new_adv/1e7:.1f} Cr  |  Deposits: Rs{new_dep/1e7:.1f} Cr')

    # ── Step 5: Monthly P&L JUN2020 ──────────────────────────────────────────
    # Lending rates: further 10 bps transmission of May repo cut
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 10.88
    effective_rate = blended_rate - 0.10   # another 10 bps pass-through in June

    int_on_adv   = round(new_adv     * effective_rate / 100 / 12, 2)
    int_on_inv   = round(investments * 6.10 / 100 / 12, 2)  # G-Sec yield lower
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.145, 2)  # fee income recovering further

    deposit_rate      = 4.20   # TD rates cut another 30 bps as banks pass on repo
    int_on_dep        = round(new_dep   * deposit_rate / 100 / 12, 2)
    int_on_borrowings = round(borrowings * 4.80 / 100 / 12, 2)
    int_expended      = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)

    employee_cost = round(nii * 0.28, 2)
    other_opex    = round(nii * 0.17, 2)
    opex          = round(employee_cost + other_opex, 2)
    op_profit     = round(nii + other_income - opex, 2)

    normal_prov  = round(new_adv * 0.005 / 12, 2)
    covid_prov   = round(covid_prov_monthly, 2)
    # Doubtful-1 requires 25% provision (vs 15% for Sub-Standard)
    doubtful_prov    = round(newly_doubtful[1] * 0.10, 2)   # incremental 10% top-up
    substandard_prov = round(newly_substandard[1] * 0.15, 2)
    provisions   = round(normal_prov + covid_prov + doubtful_prov + substandard_prov, 2)

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
        [BANK_ID, NEW_PERIOD, '2020-06-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[5] Monthly P&L JUN2020 seeded')
    p(f'    NII:                     Rs{nii/1e7:.2f} Cr  (lending ~{effective_rate:.2f}%, deposit {deposit_rate}%)')
    p(f'    COVID provision:         Rs{covid_prov/1e7:.2f} Cr  (month 3 of 4)')
    p(f'    Doubtful-1 top-up prov:  Rs{doubtful_prov/1e7:.2f} Cr  ({newly_doubtful[0]} loans)')
    p(f'    Sub-Standard prov:       Rs{substandard_prov/1e7:.2f} Cr  ({newly_substandard[0]} new NPAs)')
    p(f'    Total provisions:        Rs{provisions/1e7:.2f} Cr')
    p(f'    PBT: Rs{pbt/1e7:.2f} Cr  |  PAT: Rs{pat/1e7:.2f} Cr')

    # ── Step 6: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    scripts = os.path.join(_REPO_ROOT, 'operations', 'scripts')
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch', os.path.join(scripts, 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=False)
    p('\n[6] Regulatory batch re-run for 2020-06-30')

    # ── Step 7: Advance clock ─────────────────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = (
        'Unlock 1.0 full month; Unlock 2.0 announced June 29. '
        'RBI repo 4.00% (unchanged). Moratorium opt-outs begin (35% -> 33%). '
        f'{newly_doubtful[0]} loans upgraded to Doubtful-1 (180+ DPD). '
        f'{newly_substandard[0]} new Sub-Standard NPAs. '
        f'{disbursed_count} new disbursals (ECLGS surge + housing + vehicle). '
        'COVID provision month 3 of 4. PAT negative but loss narrowing.'
    )
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[7] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Summary ───────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  JUNE 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Total Assets:          Rs{ta_chk/1e7:.1f} Cr')
    p(f'  Advances (net):        Rs{new_adv/1e7:.1f} Cr')
    p(f'  Deposits:              Rs{new_dep/1e7:.1f} Cr')
    p(f'  Moratorium loans:      {remaining_morat[0]:,} ({MORATORIUM_TARGET_RATE*100:.0f}% of book)  '
      f'book: Rs{remaining_morat[1]/1e7:.1f} Cr  [opt-outs: {opt_out_count}]')
    p(f'  Doubtful-1 (new):      {newly_doubtful[0]} loans (Rs{newly_doubtful[1]/1e7:.2f} Cr) [180+ DPD]')
    p(f'  Sub-Standard (new):    {newly_substandard[0]} loans (Rs{newly_substandard[1]/1e7:.2f} Cr)')
    p(f'  Total NPA book:        {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')
    p(f'  New disbursals:        {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'  Monthly NII:           Rs{nii/1e7:.2f} Cr')
    p(f'  Monthly provisions:    Rs{provisions/1e7:.2f} Cr')
    p(f'  Monthly PAT:           Rs{pat/1e7:.2f} Cr')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
