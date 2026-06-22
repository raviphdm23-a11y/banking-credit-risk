"""
advance_to_oct2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-09-30 to 2020-10-31.

Real-world context -- October 2020:
  - RBI MPC Oct 9: repo rate held at 4.00%; MPC signals "adequate liquidity"
    and continued accommodative stance for as long as necessary
  - Unlock 5.0 (Oct 15): cinemas reopen at 50%; entertainment venues permitted
  - Festive season begins: Navratri (Oct 17-25), Dussehra (Oct 25)
    Diwali Nov 14 -- advance bookings and purchases surge in October
  - SIAM data: passenger vehicle sales Oct 2020 up 26% YoY (best since COVID)
    Two-wheeler sales also strong; festive discounts boosting volumes
  - GST collections Oct 2020: Rs 1.05 lakh Cr -- FIRST above Rs 1 lakh Cr since
    COVID. Strong signal of economic recovery gathering pace
  - ECLGS 2.0 announced: guarantee coverage extended to larger MSMEs
    (annual turnover up to Rs 250 Cr; outstanding loan up to Rs 50 Cr)
  - COVID first wave subsiding -- daily cases declining from Sep peak
  - KV Kamath committee final OTR parameters in effect; banks processing filings

Decision Gate going in (September):
  GNPA 4.37% AMBER | PAT -Rs6.95 Cr RED | CAR GREEN | Morat 0% GREEN | Disbursals 18 AMBER
  => Phase 1 Defensive: TLTRO (S3) on hold; GNPA must clear 4% before Phase 2

October narrative:
  The cliff has passed. No new large provision events this month.
  OTR book (728 loans) enters first full repayment month; ~1.5% re-default expected.
  Festive demand drives vehicle and home loan originations higher.
  Provisions drop to near-normal; PAT returns to positive.
  GNPA ratio stays elevated (cliff aftermath) but trajectory turns down.
  Watch: TLTRO trigger condition (GNPA < 4%) -- likely Nov/Dec.

Run: python operations/scripts/advance_to_oct2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID     = 'BANK010'
PREV_DATE   = '2020-09-30'
PREV_PERIOD = 'SEP2020'
NEW_DATE    = '2020-10-31'
NEW_PERIOD  = 'OCT2020'

OTR_REDEFAULT_RATE = 0.015   # 1.5% of OTR book fails first month EMI
DEPOSIT_GROWTH     = 0.011   # +1.1% (confidence recovering; festive deposits)
BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 26 loans -- festive uplift; vehicle-heavy; ECLGS 2.0; no unsecured personal
NEW_LOAN_SPECS = [
    # Vehicle (festive Navratri/Dussehra wave)
    ('Vehicle Loan', 1100000, 10.50, 60, 'vehicle-festive'),
    ('Vehicle Loan',  860000, 10.50, 48, 'vehicle-festive'),
    ('Vehicle Loan', 1350000, 10.50, 60, 'vehicle-festive'),
    ('Vehicle Loan',  720000, 10.50, 36, 'vehicle-festive'),
    ('Vehicle Loan',  980000, 10.50, 48, 'vehicle-festive'),
    ('Vehicle Loan', 1500000, 10.50, 60, 'vehicle-festive'),
    # ECLGS 2.0 (larger MSMEs; higher ticket size)
    ('Business Loan', 4500000, 9.00, 48, 'ECLGS2-oct'),
    ('Business Loan', 6200000, 9.00, 48, 'ECLGS2-oct'),
    ('Business Loan', 3800000, 9.00, 48, 'ECLGS2-oct'),
    ('Business Loan', 5100000, 9.00, 48, 'ECLGS2-oct'),
    ('Business Loan', 2900000, 9.00, 48, 'ECLGS2-oct'),
    # Home loans (Diwali pipeline building; stamp duty relief ending Dec 31)
    ('Home Loan', 5800000, 7.85, 240, 'housing-oct'),
    ('Home Loan', 4300000, 7.85, 180, 'housing-oct'),
    ('Home Loan', 6700000, 7.85, 300, 'housing-oct'),
    ('Home Loan', 3500000, 7.85, 120, 'housing-oct'),
    ('Home Loan', 7200000, 7.85, 300, 'housing-oct'),
    # Business loans (non-ECLGS; capacity restart post-festive)
    ('Business Loan', 3200000, 11.50, 60, 'msme-restart'),
    ('Business Loan', 2600000, 11.50, 60, 'msme-restart'),
    ('Business Loan', 1900000, 11.50, 48, 'msme-restart'),
    # Agri (Rabi season sowing -- wheat, mustard)
    ('Business Loan', 480000, 8.50, 12, 'agri-rabi'),
    ('Business Loan', 620000, 8.50, 12, 'agri-rabi'),
    ('Business Loan', 390000, 8.50, 12, 'agri-rabi'),
    # LAP / Mortgage (secured; business working capital)
    ('Home Loan', 4800000,  9.50, 120, 'lap-oct'),
    ('Home Loan', 3600000,  9.50,  84, 'lap-oct'),
    # Education (second semester disbursals)
    ('Education Loan', 780000, 11.00, 60, 'education-oct'),
    ('Education Loan', 920000, 11.00, 72, 'education-oct'),
]

EXPOSURE_MAP = {
    'Business Loan':  'corporate',
    'Home Loan':      'retail_secured',
    'Vehicle Loan':   'retail_secured',
    'Personal Loan':  'retail_unsecured',
    'Education Loan': 'retail_unsecured',
}

def _emi(p, r_annual, t_months):
    r = r_annual / 100 / 12
    if r == 0:
        return p / t_months
    return p * r * (1+r)**t_months / ((1+r)**t_months - 1)


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_10)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-09-30 --> 2020-10-31')
    p('  Recovery month: festive season + normalising provisions')
    p('=' * 68)

    # ── Step 1: OTR re-defaults (1.5% of OTR book) ───────────────────────────
    otr_loans = [dict(r) for r in cur.execute(
        "SELECT id, outstanding FROM loans "
        "WHERE bank_id=? AND otr_restructured=1 AND days_past_due=0 "
        "AND loan_classification='Standard'",
        (BANK_ID,)).fetchall()]

    redefault_count = round(len(otr_loans) * OTR_REDEFAULT_RATE)
    random.seed(20201001)
    random.shuffle(otr_loans)
    redefault_loans = otr_loans[:redefault_count]
    redefault_amt   = sum(l['outstanding'] for l in redefault_loans)
    redefault_prov  = round(redefault_amt * 0.15, 2)

    if redefault_loans:
        rids = [l['id'] for l in redefault_loans]
        cur.execute(
            "UPDATE loans SET days_past_due=91, loan_classification='Sub-Standard', "
            "otr_restructured=0 "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(rids))),
            [BANK_ID] + rids)

    conn.commit()
    p(f'\n[1] OTR re-defaults: {redefault_count} loans failed first restructured EMI')
    p(f'    Rs{redefault_amt/1e7:.2f} Cr  provision @ 15% = Rs{redefault_prov/1e7:.2f} Cr')
    p(f'    OTR book remaining: {len(otr_loans)-redefault_count} loans performing normally')

    # ── Step 2: DPD aging of existing NPA loans ───────────────────────────────
    # Reset seed-artefact DPD on performing non-OTR loans (ongoing cleanup)
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0 AND otr_restructured=0
          AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))

    # Age all non-moratorium, non-OTR NPA loans +30
    cur.execute("""
        UPDATE loans SET days_past_due = MIN(days_past_due + 30, 720)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

    # Sub-Standard at 180+ DPD -> Doubtful-1
    to_d1 = cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification='Sub-Standard'
    """, (BANK_ID,)).fetchone()
    cur.execute("""
        UPDATE loans SET loan_classification='Doubtful-1'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification='Sub-Standard'
    """, (BANK_ID,))

    # Doubtful-1 at 360+ DPD -> Doubtful-2
    to_d2 = cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 360
          AND loan_classification='Doubtful-1'
    """, (BANK_ID,)).fetchone()
    cur.execute("""
        UPDATE loans SET loan_classification='Doubtful-2'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 360
          AND loan_classification='Doubtful-1'
    """, (BANK_ID,))

    d1_prov = round(to_d1[1] * 0.10, 2)
    d2_prov = round(to_d2[1] * 0.10, 2)  # incremental 10% on D1->D2 upgrade
    conn.commit()
    p(f'\n[2] DPD aging complete')
    p(f'    Sub-Standard -> Doubtful-1: {to_d1[0]} loans Rs{to_d1[1]/1e7:.2f} Cr  prov Rs{d1_prov/1e7:.2f} Cr')
    p(f'    Doubtful-1 -> Doubtful-2:   {to_d2[0]} loans Rs{to_d2[1]/1e7:.2f} Cr  prov Rs{d2_prov/1e7:.2f} Cr')

    # ── Step 3: Fresh NPAs from performing book ───────────────────────────────
    random.seed(20201002)
    fresh_pool = [dict(r) for r in cur.execute("""
        SELECT id, outstanding FROM loans
        WHERE bank_id=? AND moratorium=0 AND otr_restructured=0
          AND days_past_due=0
          AND loan_classification IN ('Standard','Performing')
          AND type IN ('Personal Loan','Business Loan')
        ORDER BY outstanding DESC LIMIT 150
    """, (BANK_ID,)).fetchall()]
    random.shuffle(fresh_pool)
    fresh_npa  = fresh_pool[:5]
    fresh_amt  = sum(l['outstanding'] for l in fresh_npa)
    fresh_prov = round(fresh_amt * 0.15, 2)
    if fresh_npa:
        fids = [l['id'] for l in fresh_npa]
        cur.execute(
            "UPDATE loans SET days_past_due=91, loan_classification='Sub-Standard' "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(fids))),
            [BANK_ID] + fids)

    total_npa = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans "
        "WHERE bank_id=? AND days_past_due>=90 AND moratorium=0",
        (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[3] Fresh Sub-Standard: {len(fresh_npa)} loans Rs{fresh_amt/1e7:.2f} Cr  prov Rs{fresh_prov/1e7:.2f} Cr')
    p(f'    Total NPA: {total_npa[0]} loans  Rs{total_npa[1]/1e7:.2f} Cr')

    # ── Step 4: New disbursals -- 26 loans, festive season ────────────────────
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
        loan_id = f'LOAN-OCT2020-{i+1:02d}'
        emi_val = round(_emi(principal, rate, tenure), 2)
        cur.execute("""
            INSERT OR REPLACE INTO loans
              (id, bank_id, cid, type, principal, rate, tenure, emi,
               disbursed, maturity, outstanding, status, branch_id,
               loan_classification, exposure_class, days_past_due,
               moratorium, otr_restructured, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            loan_id, BANK_ID, no_loan_custs[i]['id'], ltype,
            principal, rate, tenure, emi_val,
            NEW_DATE,
            (date(2020, 10, 31) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype, 'retail_unsecured'),
            0, 0, 0, f'oct2020_{sector}'
        ))
        disbursed_count += 1
        total_new_principal += principal

    conn.commit()
    veh_c  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'vehicle' in s[4])
    eclg_c = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'ECLGS' in s[4])
    home_c = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'housing' in s[4] or 'lap' in s[4])
    msme_c = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'restart' in s[4])
    agri_c = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'agri' in s[4])
    edu_c  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'education' in s[4])
    p(f'\n[4] New disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr  [Festive season]')
    p(f'    {veh_c} Vehicle + {eclg_c} ECLGS2.0 + {home_c} Home/LAP + {msme_c} MSME restart + {agri_c} Agri + {edu_c} Education')

    # ── Step 5: Balance sheet OCT2020 ─────────────────────────────────────────
    prev_bs = dict(cur.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?",
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_dep = (prev_bs['deposits_demand'] + prev_bs['deposits_savings']
                + prev_bs['deposits_term'])
    new_dep  = prev_dep * (1 + DEPOSIT_GROWTH)
    new_adv  = cur.execute(
        "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?",
        (BANK_ID,)).fetchone()[0]

    equity_capital   = prev_bs['equity_capital']
    reserves_surplus = prev_bs['reserves_surplus']
    capital_base     = equity_capital + reserves_surplus

    deposits_demand  = 0.12 * new_dep
    deposits_savings = 0.48 * new_dep
    deposits_term    = new_dep - deposits_demand - deposits_savings
    other_liabilities = 0.040 * new_dep + 3.0e7  # Rs3 Cr floating provision

    total_lc  = capital_base + new_dep + other_liabilities
    cash_with_rbi     = 0.030 * new_dep
    investments       = 0.190 * new_dep
    fixed_assets      = prev_bs['fixed_assets']
    intangible_assets = prev_bs['intangible_assets']
    other_assets      = 0.050 * new_adv

    fixed_sum = (cash_with_rbi + investments + new_adv
                 + fixed_assets + intangible_assets + other_assets)
    gap = total_lc - fixed_sum
    balances_with_banks = max(0.0, gap)
    borrowings          = max(0.0, -gap)
    total_assets = fixed_sum + balances_with_banks

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
        round(equity_capital,2), round(reserves_surplus,2),
        round(deposits_demand,2), round(deposits_savings,2), round(deposits_term,2),
        round(borrowings,2), round(other_liabilities,2),
        round(cash_with_rbi,2), round(balances_with_banks,2), round(investments,2),
        round(new_adv,2), round(fixed_assets,2), round(intangible_assets,2),
        round(other_assets,2),
        round(0.60*total_assets,2), round(0.05*total_assets,2),
        'advance_to_oct2020', now
    ))
    conn.commit()
    p(f'\n[5] Balance sheet OCT2020 seeded')
    p(f'    Total Assets: Rs{total_assets/1e7:.1f} Cr | Advances: Rs{new_adv/1e7:.1f} Cr | Deposits: Rs{new_dep/1e7:.1f} Cr')

    # ── Step 6: P&L OCT2020 ───────────────────────────────────────────────────
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 10.40
    effective_rate = blended_rate - 0.01   # minimal further transmission

    int_on_adv   = round(new_adv     * effective_rate / 100 / 12, 2)
    int_on_inv   = round(investments * 5.70 / 100 / 12, 2)
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.160, 2)  # fee income recovering on festive loan processing

    deposit_rate      = 3.40   # TD rates continuing to fall; RBI signalling easy money
    int_on_dep        = round(new_dep   * deposit_rate / 100 / 12, 2)
    int_on_borrowings = round(borrowings * 4.40 / 100 / 12, 2)
    int_expended      = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)
    employee_cost= round(nii * 0.260, 2)
    other_opex   = round(nii * 0.155, 2)
    opex         = round(employee_cost + other_opex, 2)
    op_profit    = round(nii + other_income - opex, 2)

    normal_prov  = round(new_adv * 0.005 / 12, 2)
    provisions   = round(normal_prov + redefault_prov + d1_prov + d2_prov + fresh_prov, 2)

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
        [BANK_ID, NEW_PERIOD, '2020-10-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[6] P&L OCT2020 seeded')
    p(f'    NII: Rs{nii/1e7:.2f} Cr  (lending ~{effective_rate:.2f}%, deposit {deposit_rate}%)')
    p(f'    Op. Profit: Rs{op_profit/1e7:.2f} Cr')
    p(f'    Provisions: Rs{provisions/1e7:.2f} Cr  (normal {normal_prov/1e7:.2f} + OTR redefault {redefault_prov/1e7:.2f} + aging {(d1_prov+d2_prov)/1e7:.2f})')
    p(f'    PAT: Rs{pat/1e7:.2f} Cr{"  [POSITIVE]" if pat > 0 else ""}')

    # ── Step 7: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch',
        os.path.join(_REPO_ROOT, 'operations', 'scripts', 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=False)
    p('\n[7] Regulatory batch re-run for 2020-10-31')

    # ── Step 8: Advance clock ──────────────────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = (
        f'Festive season (Navratri/Dussehra). OTR re-defaults: {redefault_count} loans. '
        f'Total NPA: {total_npa[0]} loans Rs{total_npa[1]/1e7:.2f} Cr. '
        f'{disbursed_count} disbursals (festive vehicle + ECLGS2.0 + home). '
        f'PAT Rs{pat/1e7:.2f} Cr. GST crossed Rs1 lakh Cr first time since COVID.'
    )
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[8] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Step 9: sim_period_metrics ────────────────────────────────────────────
    npa_ratio = round(total_npa[1] / new_adv * 100, 2) if new_adv else 0

    def gate(metric, val):
        if metric == 'gnpa':   return 'GREEN' if val < 2 else ('AMBER' if val < 4 else 'RED')
        if metric == 'pat':    return 'GREEN' if val > 0 else ('AMBER' if val > -3 else 'RED')
        if metric == 'morat':  return 'GREEN' if val < 15 else ('AMBER' if val < 25 else 'RED')
        if metric == 'disbur': return 'GREEN' if val > 25 else ('AMBER' if val > 15 else 'RED')
        return 'GREEN'

    cur.execute("""
        INSERT OR REPLACE INTO sim_period_metrics
          (bank_id, period, as_of_date,
           morat_count, morat_pct, morat_book_cr,
           morat_green, morat_amber, morat_red,
           gate_gnpa, gate_pat, gate_car, gate_morat, gate_disbursals,
           new_disbursals, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (BANK_ID, NEW_PERIOD, NEW_DATE,
          0, 0.0, 0.0, 0, 0, 0,
          gate('gnpa', npa_ratio),
          gate('pat',  pat/1e7),
          'GREEN',
          gate('morat', 0.0),
          gate('disbur', disbursed_count),
          disbursed_count,
          f'Festive month. OTR redefault {redefault_count}. '
          f'GNPA {npa_ratio:.2f}%. PAT Rs{pat/1e7:.2f} Cr.'))
    conn.commit()
    p(f'[9] sim_period_metrics row inserted for OCT2020')

    # ── Step 10: STRATEGY.md ─────────────────────────────────────────────────
    strat_path = os.path.join(_REPO_ROOT, 'STRATEGY.md')
    strat = open(strat_path, encoding='utf-8').read()
    old_row = '| OCT2020 | — | — | — | — | — |'
    new_row = (f'| OCT2020 | Festive season; OTR holds; ECLGS 2.0; GNPA stabilising | '
               f'{pat/1e7:+.2f} | {total_npa[0]} | 0% | {disbursed_count} |')
    strat = strat.replace(old_row, new_row)
    open(strat_path, 'w', encoding='utf-8').write(strat)
    p('[10] STRATEGY.md history log updated')

    # ── Summary ────────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  OCTOBER 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Advances:      Rs{new_adv/1e7:.1f} Cr  |  Deposits: Rs{new_dep/1e7:.1f} Cr')
    p(f'  OTR book:      {len(otr_loans)-redefault_count} loans performing  |  {redefault_count} re-defaulted this month')
    p(f'  Total NPA:     {total_npa[0]} loans  Rs{total_npa[1]/1e7:.2f} Cr  ({npa_ratio:.2f}% of book)')
    p(f'  New disbursals:{disbursed_count} loans  Rs{total_new_principal/1e7:.2f} Cr  (festive seasonal peak)')
    p(f'  Provisions:    Rs{provisions/1e7:.2f} Cr  [near-normal -- no cliff events]')
    p(f'  Monthly PAT:   Rs{pat/1e7:.2f} Cr')
    p(f'  DECISION GATE:')
    p(f'    GNPA {npa_ratio:.2f}% [{gate("gnpa",npa_ratio)}] | PAT Rs{pat/1e7:.2f} Cr [{gate("pat",pat/1e7)}]')
    p(f'    CAR [GREEN] | Moratorium 0% [GREEN] | Disbursals {disbursed_count} [{gate("disbur",disbursed_count)}]')
    tltro_ready = npa_ratio < 4.0
    p(f'  TLTRO (S3) trigger: GNPA < 4% -- {"READY" if tltro_ready else f"NOT YET ({npa_ratio:.2f}% still above 4%)"}')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
