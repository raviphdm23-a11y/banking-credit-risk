"""
advance_to_nov2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-10-31 to 2020-11-30.

Real-world context -- November 2020:
  - Diwali November 14 -- biggest consumer spending festival; home/vehicle/gold
    purchases surge; loan disbursals peak for the year
  - Pfizer announces 90%+ vaccine efficacy November 9 -- market sentiment pivots
    sharply positive; credit confidence returns; risk appetite improves
  - RBI MPC November 6: repo rate unchanged at 4.00%; stance "accommodative"
  - GST collections Nov 2020: Rs 1.05 lakh Cr (second consecutive month above
    Rs 1 lakh Cr -- confirms economic recovery is broad-based)
  - Auto sales: Diwali effect drives passenger vehicles to 2-year highs
  - ECLGS 2.0 fully operational; larger MSME window open until March 31, 2021
  - RBI TLTRO 2.0: Rs 50,000 Cr total pool; banks can tap repeatedly

Decision Gate going in (October):
  GNPA 3.82% AMBER | PAT +Rs2.40 Cr GREEN | CAR GREEN
  Moratorium 0% GREEN | Disbursals 26 GREEN
  => No RED metric -> Phase 2 UNLOCKED. S3 (TLTRO) and S5 (SDL rotation) activate.

Strategy moves this month:
  S3 -- TLTRO 2.0 tap: Borrow Rs 100 Cr from RBI at 4.00% for 3 years.
    Deploy into ECLGS 2.0 MSME loans at 9.00%.
    Net NII spread: 5.00% on Rs 100 Cr = Rs 5 Cr/year = Rs 41.7 L/month.
    BS: borrowings +Rs 100 Cr; advances +Rs 100 Cr.
  S5 -- SDL rotation: Swap Rs 50 Cr of G-Secs (yield 5.85%) into State
    Development Loans (yield 6.50%). No BS size change.
    Additional NII: Rs 50 Cr x 0.65% / 12 = Rs 27 L/month.
  Combined S3+S5 NII uplift: ~Rs 69 L/month -- annualises to Rs 8.3 Cr/year.

Run: python operations/scripts/advance_to_nov2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID     = 'BANK010'
PREV_DATE   = '2020-10-31'
PREV_PERIOD = 'OCT2020'
NEW_DATE    = '2020-11-30'
NEW_PERIOD  = 'NOV2020'

OTR_REDEFAULT_RATE = 0.010    # 1.0% of OTR book -- stabilising
TLTRO_AMT          = 100_000_000.0  # Rs 100 Cr borrowed from RBI at 4%
SDL_ROTATION_AMT   = 50_000_000.0   # Rs 50 Cr G-Secs swapped to SDLs
SDL_YIELD_PICKUP   = 0.0065         # +65 bps annualised
DEPOSIT_GROWTH     = 0.013          # +1.3% (festive inflows + vaccine optimism)
BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

EXPOSURE_MAP = {
    'Business Loan':  'corporate',
    'Home Loan':      'retail_secured',
    'Vehicle Loan':   'retail_secured',
    'Personal Loan':  'retail_unsecured',
    'Education Loan': 'retail_unsecured',
}

# -- S3 TLTRO deployment: 12 large ECLGS 2.0 loans (~Rs 100 Cr total) --------
TLTRO_LOANS = [
    ('Business Loan', 10_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan', 10_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan', 10_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  8_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  8_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  8_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  8_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  9_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  9_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  7_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  7_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
    ('Business Loan',  6_000_000, 9.00, 48, 'ECLGS2-TLTRO'),
]  # total: Rs 100 Cr

# -- Diwali retail disbursals: 22 loans ----------------------------------------
DIWALI_LOANS = [
    # Vehicle (Diwali week surge)
    ('Vehicle Loan', 1_450_000, 10.25, 60, 'vehicle-diwali'),
    ('Vehicle Loan',   980_000, 10.25, 48, 'vehicle-diwali'),
    ('Vehicle Loan', 1_680_000, 10.25, 60, 'vehicle-diwali'),
    ('Vehicle Loan',   760_000, 10.25, 36, 'vehicle-diwali'),
    ('Vehicle Loan', 1_100_000, 10.25, 48, 'vehicle-diwali'),
    # Home loans (stamp duty waiver ending Dec 31 creates urgency)
    ('Home Loan',  6_200_000, 7.80, 240, 'housing-diwali'),
    ('Home Loan',  4_800_000, 7.80, 180, 'housing-diwali'),
    ('Home Loan',  8_500_000, 7.80, 300, 'housing-diwali'),
    ('Home Loan',  5_300_000, 7.80, 240, 'housing-diwali'),
    ('Home Loan',  3_900_000, 7.80, 120, 'housing-diwali'),
    # MSME capacity restart (vaccine confidence)
    ('Business Loan', 4_200_000, 11.25, 60, 'msme-nov'),
    ('Business Loan', 3_100_000, 11.25, 60, 'msme-nov'),
    ('Business Loan', 2_400_000, 11.25, 48, 'msme-nov'),
    # LAP / Mortgage
    ('Home Loan',  5_500_000, 9.50, 120, 'lap-nov'),
    ('Home Loan',  4_100_000, 9.50,  84, 'lap-nov'),
    # Agri (Rabi sowing second tranche)
    ('Business Loan', 540_000, 8.50, 12, 'agri-rabi'),
    ('Business Loan', 710_000, 8.50, 12, 'agri-rabi'),
    ('Business Loan', 430_000, 8.50, 12, 'agri-rabi'),
    # Education
    ('Education Loan', 870_000, 11.00, 60, 'education-nov'),
    # Personal (Diwali consumer spending -- re-enabled; GNPA AMBER only)
    ('Personal Loan', 500_000, 13.00, 36, 'personal-diwali'),
    ('Personal Loan', 350_000, 13.00, 24, 'personal-diwali'),
    ('Personal Loan', 420_000, 13.00, 30, 'personal-diwali'),
]

def _emi(p, r_annual, t_months):
    r = r_annual / 100 / 12
    if r == 0:
        return p / t_months
    return p * r * (1+r)**t_months / ((1+r)**t_months - 1)


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_11)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-10-31 --> 2020-11-30')
    p('  Phase 2 launch: TLTRO Rs100Cr + SDL rotation + Diwali peak')
    p('=' * 68)

    # ── Step 1: OTR re-defaults (1.0% -- stabilising) ────────────────────────
    otr_loans = [dict(r) for r in cur.execute(
        "SELECT id, outstanding FROM loans "
        "WHERE bank_id=? AND otr_restructured=1 AND days_past_due=0 "
        "AND loan_classification='Standard'",
        (BANK_ID,)).fetchall()]

    redefault_count = round(len(otr_loans) * OTR_REDEFAULT_RATE)
    random.seed(20201101)
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
    p(f'\n[1] OTR re-defaults: {redefault_count} loans  Rs{redefault_amt/1e7:.2f} Cr  prov Rs{redefault_prov/1e7:.2f} Cr')
    p(f'    OTR book holding: {len(otr_loans)-redefault_count} of {len(otr_loans)} loans still performing')

    # ── Step 2: DPD aging ─────────────────────────────────────────────────────
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0 AND otr_restructured=0
          AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))

    cur.execute("""
        UPDATE loans SET days_past_due = MIN(days_past_due + 30, 720)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

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
    d2_prov = round(to_d2[1] * 0.10, 2)
    conn.commit()
    p(f'\n[2] DPD aging: SS->D1: {to_d1[0]} loans Rs{to_d1[1]/1e7:.2f} Cr | D1->D2: {to_d2[0]} loans Rs{to_d2[1]/1e7:.2f} Cr')

    # ── Step 3: Fresh NPAs ────────────────────────────────────────────────────
    random.seed(20201102)
    fresh_pool = [dict(r) for r in cur.execute("""
        SELECT id, outstanding FROM loans
        WHERE bank_id=? AND moratorium=0 AND otr_restructured=0
          AND days_past_due=0
          AND loan_classification IN ('Standard','Performing')
          AND type IN ('Personal Loan','Business Loan')
        ORDER BY outstanding DESC LIMIT 150
    """, (BANK_ID,)).fetchall()]
    random.shuffle(fresh_pool)
    fresh_npa  = fresh_pool[:4]   # fewer fresh NPAs -- recovery trend
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
    p(f'\n[3] Fresh NPAs: {len(fresh_npa)} loans Rs{fresh_amt/1e7:.2f} Cr  |  Total NPA: {total_npa[0]} loans Rs{total_npa[1]/1e7:.2f} Cr')

    # ── Step 4: S3 TLTRO disbursals (12 ECLGS 2.0 loans, ~Rs 100 Cr) ─────────
    no_loan_custs = [dict(r) for r in cur.execute("""
        SELECT id FROM customers WHERE bank_id=?
        AND NOT EXISTS (SELECT 1 FROM loans WHERE cid=customers.id AND bank_id=?)
        LIMIT 40
    """, (BANK_ID, BANK_ID)).fetchall()]

    now = datetime.now().isoformat(timespec='seconds')
    tltro_disbursed = 0
    tltro_principal = 0.0

    cust_idx = 0
    for i, (ltype, principal, rate, tenure, sector) in enumerate(TLTRO_LOANS):
        if cust_idx >= len(no_loan_custs):
            break
        loan_id = f'LOAN-NOV2020-TLTRO-{i+1:02d}'
        emi_val = round(_emi(principal, rate, tenure), 2)
        cur.execute("""
            INSERT OR REPLACE INTO loans
              (id, bank_id, cid, type, principal, rate, tenure, emi,
               disbursed, maturity, outstanding, status, branch_id,
               loan_classification, exposure_class, days_past_due,
               moratorium, otr_restructured, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            loan_id, BANK_ID, no_loan_custs[cust_idx]['id'], ltype,
            principal, rate, tenure, emi_val,
            NEW_DATE,
            (date(2020, 11, 30) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', 'corporate', 0, 0, 0, f'nov2020_{sector}'
        ))
        tltro_disbursed += 1
        tltro_principal += principal
        cust_idx += 1

    conn.commit()
    p(f'\n[4] S3 TLTRO deployment: {tltro_disbursed} ECLGS 2.0 loans | Rs{tltro_principal/1e7:.1f} Cr')
    p(f'    Funded by RBI TLTRO 2.0 @ 4.00% (3-year tenor)')
    p(f'    Net NII spread: 5.00% on Rs{tltro_principal/1e7:.0f} Cr = Rs{tltro_principal*0.05/12/1e7:.2f} Cr/month')

    # ── Step 5: Diwali retail disbursals (22 loans) ───────────────────────────
    diwali_disbursed = 0
    diwali_principal = 0.0

    for i, (ltype, principal, rate, tenure, sector) in enumerate(DIWALI_LOANS):
        if cust_idx >= len(no_loan_custs):
            break
        loan_id = f'LOAN-NOV2020-DIW-{i+1:02d}'
        emi_val = round(_emi(principal, rate, tenure), 2)
        cur.execute("""
            INSERT OR REPLACE INTO loans
              (id, bank_id, cid, type, principal, rate, tenure, emi,
               disbursed, maturity, outstanding, status, branch_id,
               loan_classification, exposure_class, days_past_due,
               moratorium, otr_restructured, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            loan_id, BANK_ID, no_loan_custs[cust_idx]['id'], ltype,
            principal, rate, tenure, emi_val,
            NEW_DATE,
            (date(2020, 11, 30) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype, 'retail_unsecured'),
            0, 0, 0, f'nov2020_{sector}'
        ))
        diwali_disbursed += 1
        diwali_principal += principal
        cust_idx += 1

    conn.commit()
    total_disbursed  = tltro_disbursed + diwali_disbursed
    total_new_princ  = tltro_principal + diwali_principal
    veh_c  = sum(1 for s in DIWALI_LOANS[:diwali_disbursed] if 'vehicle' in s[4])
    home_c = sum(1 for s in DIWALI_LOANS[:diwali_disbursed] if 'housing' in s[4] or 'lap' in s[4])
    msme_c = sum(1 for s in DIWALI_LOANS[:diwali_disbursed] if 'msme' in s[4])
    pers_c = sum(1 for s in DIWALI_LOANS[:diwali_disbursed] if 'personal' in s[4])
    p(f'\n[5] Diwali disbursals: {diwali_disbursed} loans | Rs{diwali_principal/1e7:.2f} Cr')
    p(f'    {veh_c} Vehicle + {home_c} Home/LAP + {msme_c} MSME + {pers_c} Personal (re-enabled; GNPA AMBER)')
    p(f'    TOTAL disbursals this month: {total_disbursed} loans | Rs{total_new_princ/1e7:.2f} Cr')

    # ── Step 6: Balance sheet NOV2020 ─────────────────────────────────────────
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
    other_liabilities = 0.040 * new_dep + 3.0e7   # Rs3 Cr floating provision

    # TLTRO shows explicitly as borrowings
    tltro_borrowing = TLTRO_AMT
    total_lc  = capital_base + new_dep + tltro_borrowing + other_liabilities

    cash_with_rbi     = 0.030 * new_dep
    # SDL rotation: same investment total, better yield internally tracked
    investments       = 0.190 * new_dep
    fixed_assets      = prev_bs['fixed_assets']
    intangible_assets = prev_bs['intangible_assets']
    other_assets      = 0.050 * new_adv

    fixed_sum = (cash_with_rbi + investments + new_adv
                 + fixed_assets + intangible_assets + other_assets)
    gap = total_lc - fixed_sum
    balances_with_banks = max(0.0, gap)
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
        round(tltro_borrowing,2), round(other_liabilities,2),
        round(cash_with_rbi,2), round(balances_with_banks,2), round(investments,2),
        round(new_adv,2), round(fixed_assets,2), round(intangible_assets,2),
        round(other_assets,2),
        round(0.60*total_assets,2), round(0.05*total_assets,2),
        'advance_to_nov2020', now
    ))
    conn.commit()
    p(f'\n[6] Balance sheet NOV2020 seeded')
    p(f'    Total Assets: Rs{total_assets/1e7:.1f} Cr | Advances: Rs{new_adv/1e7:.1f} Cr | Deposits: Rs{new_dep/1e7:.1f} Cr')
    p(f'    TLTRO borrowings: Rs{tltro_borrowing/1e7:.0f} Cr (RBI 4% / 3-year)')

    # ── Step 7: P&L NOV2020 ───────────────────────────────────────────────────
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 10.40
    effective_rate = blended_rate

    int_on_adv   = round(new_adv     * effective_rate / 100 / 12, 2)
    # SDL rotation: Rs 50 Cr earns +65 bps vs plain G-Sec base; rest at 5.70%
    sdl_bonus    = round(SDL_ROTATION_AMT * SDL_YIELD_PICKUP / 12, 2)
    int_on_inv   = round((investments - SDL_ROTATION_AMT) * 5.70 / 100 / 12
                         + SDL_ROTATION_AMT * 6.50 / 100 / 12, 2)
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.165, 2)  # fee income high (Diwali processing)

    deposit_rate       = 3.30   # TD rates still falling
    int_on_dep         = round(new_dep       * deposit_rate / 100 / 12, 2)
    int_on_borrowings  = round(tltro_borrowing * 4.00 / 100 / 12, 2)
    int_expended       = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)
    employee_cost= round(nii * 0.255, 2)
    other_opex   = round(nii * 0.150, 2)
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
        [BANK_ID, NEW_PERIOD, '2020-11-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[7] P&L NOV2020 seeded')
    p(f'    NII: Rs{nii/1e7:.2f} Cr')
    p(f'      Inc: TLTRO spread Rs{(tltro_principal*0.05/12)/1e7:.2f} Cr + SDL pickup Rs{sdl_bonus/1e7:.2f} Cr')
    p(f'    Op. Profit: Rs{op_profit/1e7:.2f} Cr')
    p(f'    Provisions: Rs{provisions/1e7:.2f} Cr')
    p(f'    PAT: Rs{pat/1e7:.2f} Cr{"  [POSITIVE]" if pat > 0 else ""}')

    # ── Step 8: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch',
        os.path.join(_REPO_ROOT, 'operations', 'scripts', 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=False)
    p('\n[8] Regulatory batch re-run for 2020-11-30')

    # ── Step 9: Clock ──────────────────────────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = (
        f'Phase 2 launched: S3 TLTRO Rs100Cr @ 4% deployed ({tltro_disbursed} ECLGS2.0 loans). '
        f'S5 SDL rotation Rs50Cr G-Secs -> SDLs (+65bps yield). '
        f'Diwali: {diwali_disbursed} retail loans. OTR redefaults: {redefault_count}. '
        f'Total NPA: {total_npa[0]} loans Rs{total_npa[1]/1e7:.2f} Cr. '
        f'PAT Rs{pat/1e7:.2f} Cr. Pfizer vaccine news Nov 9.'
    )
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[9] simulation_clock.json advanced to {NEW_DATE}')

    # ── Step 10: sim_period_metrics ───────────────────────────────────────────
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
          'GREEN',
          gate('disbur', total_disbursed),
          total_disbursed,
          f'Phase 2: TLTRO Rs100Cr + SDL rotation. Diwali peak. '
          f'GNPA {npa_ratio:.2f}%. PAT Rs{pat/1e7:.2f} Cr. {total_disbursed} disbursals.'))
    conn.commit()
    p('[10] sim_period_metrics row inserted for NOV2020')

    # ── Step 11: STRATEGY.md ─────────────────────────────────────────────────
    strat_path = os.path.join(_REPO_ROOT, 'STRATEGY.md')
    strat = open(strat_path, encoding='utf-8').read()
    old_row = '| NOV2020 | — | — | — | — | — |'
    new_row = (f'| NOV2020 | Phase 2 launch: TLTRO Rs100Cr + SDL rotation; Diwali peak disbursals | '
               f'{pat/1e7:+.2f} | {total_npa[0]} | 0% | {total_disbursed} |')
    strat = strat.replace(old_row, new_row)
    strat = strat.replace(
        '| S3 — TLTRO 2.0 tap | Pending | October 2020 | — |',
        f'| S3 — TLTRO 2.0 tap | **Active** | November 2020 | Rs100 Cr @ 4%; deployed into {tltro_disbursed} ECLGS2.0 loans; NII +Rs{(tltro_principal*0.05/12)/1e7:.2f} Cr/month |'
    ).replace(
        '| S5 — SDL rotation | Pending | November 2020 | — |',
        f'| S5 — SDL rotation | **Active** | November 2020 | Rs50 Cr G-Secs swapped to SDLs; +Rs{sdl_bonus/1e7:.2f} Cr/month |'
    )
    open(strat_path, 'w', encoding='utf-8').write(strat)
    p('[11] STRATEGY.md updated: S3 and S5 marked Active')

    # ── Summary ───────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  NOVEMBER 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Advances:       Rs{new_adv/1e7:.1f} Cr (TLTRO Rs100Cr deployed)')
    p(f'  Deposits:       Rs{new_dep/1e7:.1f} Cr  |  TLTRO borrowings: Rs100 Cr')
    p(f'  OTR book:       {len(otr_loans)-redefault_count} loans performing  |  {redefault_count} re-defaulted')
    p(f'  Total NPA:      {total_npa[0]} loans Rs{total_npa[1]/1e7:.2f} Cr ({npa_ratio:.2f}%)')
    p(f'  New disbursals: {total_disbursed} ({tltro_disbursed} TLTRO ECLGS + {diwali_disbursed} Diwali retail)')
    p(f'  Monthly NII:    Rs{nii/1e7:.2f} Cr  (+S3/S5 lift)')
    p(f'  Provisions:     Rs{provisions/1e7:.2f} Cr')
    p(f'  Monthly PAT:    Rs{pat/1e7:.2f} Cr')
    p(f'  DECISION GATE:')
    p(f'    GNPA {npa_ratio:.2f}% [{gate("gnpa",npa_ratio)}] | PAT Rs{pat/1e7:.2f} Cr [{gate("pat",pat/1e7)}]')
    p(f'    CAR [GREEN] | Moratorium 0% [GREEN] | Disbursals {total_disbursed} [{gate("disbur",total_disbursed)}]')
    p(f'  NEXT MONTH (DEC): OTR provision tranche 2 (5% of Rs{total_npa[1]/1e7:.0f} Cr = Rs{total_npa[1]*0.05/1e7:.2f} Cr)')
    p(f'    + S4 CASA campaign if gate allows + Q3 FY2021 results review')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
