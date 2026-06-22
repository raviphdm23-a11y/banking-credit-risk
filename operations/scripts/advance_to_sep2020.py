"""
advance_to_sep2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-08-31 to 2020-09-30.

Real-world context — September 2020:
  - Moratorium ended August 31 — September 1 is the first EMI demand for 1,216
    previously deferred borrowers. This is the "moratorium cliff."
  - GDP Q1 FY2021: -23.9% (released Aug 28) — worst contraction on record.
    Market and regulator expect sharp NPA formation in Q2 FY2021.
  - RBI OTR window open — banks racing to file restructuring applications before
    Dec 31, 2020 deadline. KV Kamath committee parameters published Sep 7.
  - Unlock 4.0 (Sep 1): metro rail, open-air assemblies permitted; partial normalcy.
  - Repo rate unchanged at 4.00% (MPC Sep 4 — accommodative stance).
  - COVID cases: India crossing 5 million (first wave peak ~mid-Sep).

Moratorium cliff — what happens Sep 1:
  GREEN  (413 loans): resume EMIs as expected; ~8% slip in first month
  AMBER  (728 loans): OTR restructuring executed; tenure extended 12 months;
                      DPD stays 0 (RBI OTR protects classification);
                      10% provision required (built in 2 tranches: 5% Sep, 5% Dec)
  RED    (75 loans):  fail to resume; immediately Sub-Standard (DPD = 91)

Decision Gate going in (August):
  GNPA 0.93% GREEN | PAT +Rs2.42 Cr GREEN | CAR 16.42% GREEN
  Moratorium 28% RED | Disbursals 22 AMBER
  => Phase 1 Defensive continues

Expected September outcome:
  GNPA will spike to ~4% (RED/AMBER border) — the single largest monthly NPA jump
  PAT large negative (massive OTR + Red-cohort provisions) — RED
  Moratorium: 0% (GREEN — it's over!) | CAR stays GREEN
  => Phase 1 Defensive, no offensive moves. October will determine recovery trajectory.

Run: python operations/scripts/advance_to_sep2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID     = 'BANK010'
PREV_DATE   = '2020-08-31'
PREV_PERIOD = 'AUG2020'
NEW_DATE    = '2020-09-30'
NEW_PERIOD  = 'SEP2020'

# Moratorium cliff parameters
GREEN_SLIP_RATE     = 0.08   # 8% of Green cohort miss first EMI
OTR_PROVISION_PCT   = 0.05   # 5% upfront (remaining 5% in Dec per RBI 2-tranche rule)
RED_PROVISION_PCT   = 0.15   # Sub-Standard: 15%
SLIP_PROVISION_PCT  = 0.15   # Green slippage also Sub-Standard: 15%

DEPOSIT_GROWTH = 0.010       # +1.0% (cautious; people holding liquidity)
BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 18 loans — Defensive posture: GNPA will be RED this month
# Only ECLGS + secured; absolutely no unsecured personal
NEW_LOAN_SPECS = [
    # ECLGS (government guarantee = 0 credit risk)
    ('Business Loan', 2200000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1800000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3100000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2600000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1400000, 9.00, 48, 'MSME-ECLGS'),
    # Home loans (secured; property values stable)
    ('Home Loan', 4200000, 7.90, 240, 'housing-sep'),
    ('Home Loan', 5500000, 7.90, 240, 'housing-sep'),
    ('Home Loan', 3600000, 7.90, 180, 'housing-sep'),
    ('Home Loan', 6800000, 7.90, 300, 'housing-sep'),
    # Vehicle (festive season Navratri pre-bookings)
    ('Vehicle Loan',  900000, 10.75, 48, 'vehicle-festive'),
    ('Vehicle Loan', 1250000, 10.75, 60, 'vehicle-festive'),
    ('Vehicle Loan',  780000, 10.75, 36, 'vehicle-festive'),
    # Agri (Kharif harvest credit; short tenure)
    ('Business Loan', 550000, 8.50, 12, 'agri-kharif'),
    ('Business Loan', 420000, 8.50, 12, 'agri-kharif'),
    ('Business Loan', 680000, 8.50, 12, 'agri-kharif'),
    # Education (semester disbursals)
    ('Education Loan', 850000, 11.00, 60, 'education-sep'),
    ('Education Loan', 620000, 11.00, 48, 'education-sep'),
    # Mortgage LAP (secured; conservative LTV)
    ('Home Loan', 3900000, 9.50, 120, 'lap-sep'),
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


def _ensure_otr_column(cur):
    cols = [r[1] for r in cur.execute("PRAGMA table_info(loans)").fetchall()]
    if 'otr_restructured' not in cols:
        cur.execute("ALTER TABLE loans ADD COLUMN otr_restructured INTEGER DEFAULT 0")


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_09)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-08-31 --> 2020-09-30')
    p('  THE MORATORIUM CLIFF — Green resume, Amber OTR, Red NPA')
    p('=' * 68)

    _ensure_otr_column(cur)

    # ── Step 1: RED cohort -> Sub-Standard ─────────────────────────────────────
    red_loans = [dict(r) for r in cur.execute(
        "SELECT id, outstanding FROM loans "
        "WHERE bank_id=? AND moratorium=1 AND moratorium_category='R'",
        (BANK_ID,)).fetchall()]
    red_amt = sum(l['outstanding'] for l in red_loans)

    if red_loans:
        red_ids = [l['id'] for l in red_loans]
        cur.execute(
            "UPDATE loans SET moratorium=0, moratorium_end_date=?, "
            "days_past_due=91, loan_classification='Sub-Standard' "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(red_ids))),
            [NEW_DATE, BANK_ID] + red_ids)

    red_prov = round(red_amt * RED_PROVISION_PCT, 2)
    conn.commit()
    p(f'\n[1] RED cohort exits moratorium -> Sub-Standard')
    p(f'    {len(red_loans)} loans  Rs{red_amt/1e7:.2f} Cr  provision @ 15% = Rs{red_prov/1e7:.2f} Cr')

    # ── Step 2: GREEN cohort — resume EMIs, ~8% slip ───────────────────────────
    green_loans = [dict(r) for r in cur.execute(
        "SELECT id, outstanding FROM loans "
        "WHERE bank_id=? AND moratorium=1 AND moratorium_category='G'",
        (BANK_ID,)).fetchall()]
    green_total = sum(l['outstanding'] for l in green_loans)

    # Shuffle; first 8% slip
    random.shuffle(green_loans)
    slip_count  = round(len(green_loans) * GREEN_SLIP_RATE)
    slip_loans  = green_loans[:slip_count]
    resume_loans= green_loans[slip_count:]
    slip_amt    = sum(l['outstanding'] for l in slip_loans)
    slip_prov   = round(slip_amt * SLIP_PROVISION_PCT, 2)

    # Slipped: Sub-Standard
    if slip_loans:
        sids = [l['id'] for l in slip_loans]
        cur.execute(
            "UPDATE loans SET moratorium=0, moratorium_end_date=?, "
            "days_past_due=91, loan_classification='Sub-Standard' "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(sids))),
            [NEW_DATE, BANK_ID] + sids)

    # Resumed: normal, DPD=0
    if resume_loans:
        rids = [l['id'] for l in resume_loans]
        cur.execute(
            "UPDATE loans SET moratorium=0, moratorium_end_date=? "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(rids))),
            [NEW_DATE, BANK_ID] + rids)

    conn.commit()
    p(f'\n[2] GREEN cohort exits moratorium')
    p(f'    {len(resume_loans)} loans resumed EMIs normally')
    p(f'    {slip_count} loans slipped (first EMI missed) -> Sub-Standard')
    p(f'    Slip amount: Rs{slip_amt/1e7:.2f} Cr  provision Rs{slip_prov/1e7:.2f} Cr')

    # ── Step 3: AMBER cohort — OTR restructuring ───────────────────────────────
    amber_loans = [dict(r) for r in cur.execute(
        "SELECT id, outstanding, tenure FROM loans "
        "WHERE bank_id=? AND moratorium=1 AND moratorium_category='A'",
        (BANK_ID,)).fetchall()]
    amber_amt = sum(l['outstanding'] for l in amber_loans)

    if amber_loans:
        aids = [l['id'] for l in amber_loans]
        # OTR: exit moratorium, keep classification Standard, extend tenure +12
        cur.executemany(
            "UPDATE loans SET moratorium=0, moratorium_end_date=?, "
            "days_past_due=0, loan_classification='Standard', "
            "otr_restructured=1, tenure=tenure+12 "
            "WHERE bank_id=? AND id=?",
            [(NEW_DATE, BANK_ID, l['id']) for l in amber_loans])

    otr_prov_sep  = round(amber_amt * OTR_PROVISION_PCT, 2)  # 5% tranche 1
    conn.commit()
    p(f'\n[3] AMBER cohort -> OTR restructured (RBI window; KV Kamath committee)')
    p(f'    {len(amber_loans)} loans restructured  Rs{amber_amt/1e7:.2f} Cr')
    p(f'    Tenure extended +12 months; DPD=0; classification preserved (Standard)')
    p(f'    OTR provision tranche 1 (5% of Rs{amber_amt/1e7:.1f} Cr) = Rs{otr_prov_sep/1e7:.2f} Cr')
    p(f'    Remaining 5% tranche to be built in December (RBI 2-quarter allowance)')

    # ── Step 4: Age existing NPA loans ────────────────────────────────────────
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0 AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
          AND otr_restructured = 0
    """, (BANK_ID,))

    cur.execute("""
        UPDATE loans SET days_past_due = MIN(days_past_due + 30, 360)
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 90
    """, (BANK_ID,))

    # Doubtful-1 upgrade check (Sub-Standard at 180+ DPD)
    newly_d1 = cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification='Sub-Standard'
    """, (BANK_ID,)).fetchone()
    cur.execute("""
        UPDATE loans SET loan_classification='Doubtful-1'
        WHERE bank_id=? AND moratorium=0 AND days_past_due >= 180
          AND loan_classification='Sub-Standard'
    """, (BANK_ID,))
    d1_prov = round(newly_d1[1] * 0.10, 2)

    conn.commit()
    p(f'\n[4] Existing NPA loans aged +30 DPD')
    p(f'    Upgraded to Doubtful-1: {newly_d1[0]} loans (Rs{newly_d1[1]/1e7:.2f} Cr)  incremental prov Rs{d1_prov/1e7:.2f} Cr')

    # ── Step 5: Fresh NPAs from non-moratorium performing book ─────────────────
    random.seed(20200901)
    fresh_pool = [dict(r) for r in cur.execute("""
        SELECT id, outstanding FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due=0
          AND otr_restructured=0
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
        "WHERE bank_id=? AND days_past_due>=90 AND moratorium=0", (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[5] Fresh Sub-Standard (non-morat book): {len(fresh_npa)} loans Rs{fresh_amt/1e7:.2f} Cr  prov Rs{fresh_prov/1e7:.2f} Cr')
    p(f'    TOTAL NPA (post-cliff): {total_npa[0]} loans  Rs{total_npa[1]/1e7:.2f} Cr')

    # ── Step 6: New disbursals — 18 loans, defensive posture ──────────────────
    no_loan_custs = [dict(r) for r in cur.execute("""
        SELECT id FROM customers WHERE bank_id=?
        AND NOT EXISTS (SELECT 1 FROM loans WHERE cid=customers.id AND bank_id=?)
        LIMIT 25
    """, (BANK_ID, BANK_ID)).fetchall()]

    now = datetime.now().isoformat(timespec='seconds')
    disbursed_count = 0
    total_new_principal = 0.0

    for i, (ltype, principal, rate, tenure, sector) in enumerate(NEW_LOAN_SPECS):
        if i >= len(no_loan_custs):
            break
        loan_id = f'LOAN-SEP2020-{i+1:02d}'
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
            (date(2020, 9, 30) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype,'retail_unsecured'),
            0, 0, 0, f'sep2020_{sector}'
        ))
        disbursed_count += 1
        total_new_principal += principal

    conn.commit()
    eclgs_c = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'ECLGS' in s[4])
    home_c  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'housing' in s[4] or 'lap' in s[4])
    veh_c   = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'vehicle' in s[4])
    agri_c  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'agri' in s[4])
    edu_c   = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'education' in s[4])
    p(f'\n[6] New disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr  [Defensive posture]')
    p(f'    {eclgs_c} ECLGS + {home_c} Secured (Home/LAP) + {veh_c} Vehicle + {agri_c} Agri + {edu_c} Education')

    # ── Step 7: Balance sheet SEP2020 ─────────────────────────────────────────
    prev_bs = dict(cur.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?",
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_dep = (prev_bs['deposits_demand'] + prev_bs['deposits_savings'] + prev_bs['deposits_term'])
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

    # Floating provision (S2) carried forward; also retains OTR provision build
    other_liabilities = 0.040 * new_dep + (3.0e7)  # Rs3 Cr floating provision

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
        'advance_to_sep2020', now
    ))
    conn.commit()
    p(f'\n[7] Balance sheet SEP2020 seeded')
    p(f'    Total Assets: Rs{total_assets/1e7:.1f} Cr  |  Advances: Rs{new_adv/1e7:.1f} Cr  |  Deposits: Rs{new_dep/1e7:.1f} Cr')

    # ── Step 8: Monthly P&L SEP2020 ───────────────────────────────────────────
    # NPA provision charges: the cliff month
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 10.40
    effective_rate = blended_rate - 0.02

    int_on_adv   = round(new_adv     * effective_rate / 100 / 12, 2)
    int_on_inv   = round(investments * 5.75 / 100 / 12, 2)
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.150, 2)

    deposit_rate      = 3.60
    int_on_dep        = round(new_dep   * deposit_rate / 100 / 12, 2)
    int_on_borrowings = round(borrowings * 4.40 / 100 / 12, 2)
    int_expended      = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)
    employee_cost= round(nii * 0.265, 2)
    other_opex   = round(nii * 0.158, 2)
    opex         = round(employee_cost + other_opex, 2)
    op_profit    = round(nii + other_income - opex, 2)

    normal_prov  = round(new_adv * 0.005 / 12, 2)
    provisions   = round(normal_prov + red_prov + slip_prov + otr_prov_sep
                         + d1_prov + fresh_prov, 2)

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
        [BANK_ID, NEW_PERIOD, '2020-09-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[8] Monthly P&L SEP2020 seeded  [CLIFF MONTH]')
    p(f'    NII:                   Rs{nii/1e7:.2f} Cr')
    p(f'    Op. Profit:            Rs{op_profit/1e7:.2f} Cr')
    p(f'    Red cohort provision:  Rs{red_prov/1e7:.2f} Cr  ({len(red_loans)} loans @ 15%)')
    p(f'    Green slip provision:  Rs{slip_prov/1e7:.2f} Cr  ({slip_count} loans @ 15%)')
    p(f'    OTR provision tranche: Rs{otr_prov_sep/1e7:.2f} Cr  ({len(amber_loans)} loans @ 5%, tranche 1/2)')
    p(f'    Doubtful-1 provision:  Rs{d1_prov/1e7:.2f} Cr')
    p(f'    Fresh NPA provision:   Rs{fresh_prov/1e7:.2f} Cr')
    p(f'    Normal provision:      Rs{normal_prov/1e7:.2f} Cr')
    p(f'    TOTAL PROVISIONS:      Rs{provisions/1e7:.2f} Cr')
    p(f'    PAT:                   Rs{pat/1e7:.2f} Cr  (cliff impact)')

    # ── Step 9: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch',
        os.path.join(_REPO_ROOT, 'operations', 'scripts', 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=False)
    p('\n[9] Regulatory batch re-run for 2020-09-30')

    # ── Step 10: Advance simulation clock ─────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = (
        'Moratorium cliff executed. '
        f'Red: {len(red_loans)} loans to Sub-Standard (Rs{red_amt/1e7:.1f} Cr). '
        f'Green: {len(resume_loans)} resumed, {slip_count} slipped. '
        f'Amber: {len(amber_loans)} OTR restructured (Rs{amber_amt/1e7:.1f} Cr, 5% prov tranche 1). '
        f'Total NPA: {total_npa[0]} loans Rs{total_npa[1]/1e7:.2f} Cr. '
        f'PAT Rs{pat/1e7:.2f} Cr. Moratorium: 0% (moratorium era over).'
    )
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[10] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Step 11: Update sim_period_metrics ────────────────────────────────────
    adv_total = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0]
    npa_ratio = round(total_npa[1] / new_adv * 100, 2) if new_adv else 0

    def gate(metric, val):
        if metric == 'gnpa':   return 'GREEN' if val < 2 else ('AMBER' if val < 4 else 'RED')
        if metric == 'pat':    return 'GREEN' if val > 0 else ('AMBER' if val > -3 else 'RED')
        if metric == 'car':    return 'GREEN' if val > 15 else ('AMBER' if val > 13 else 'RED')
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
          0, 0.0, 0.0,  # moratorium is over
          0, 0, 0,
          gate('gnpa', npa_ratio),
          gate('pat',  pat/1e7),
          'GREEN',
          gate('morat', 0.0),
          gate('disbur', disbursed_count),
          disbursed_count,
          f'Moratorium cliff: {len(red_loans)}R NPA + {slip_count} Green slip + {len(amber_loans)} OTR. '
          f'GNPA {npa_ratio:.2f}%. PAT Rs{pat/1e7:.2f} Cr.'))
    conn.commit()
    p(f'[11] sim_period_metrics row inserted for SEP2020')

    # ── Step 12: Update STRATEGY.md ───────────────────────────────────────────
    strat_path = os.path.join(_REPO_ROOT, 'STRATEGY.md')
    strat = open(strat_path, encoding='utf-8').read()
    old_row = '| SEP2020 | — | — | — | — | — |'
    new_row = (f'| SEP2020 | Moratorium cliff; {len(red_loans)}R NPA + {slip_count} Green slip + {len(amber_loans)} OTR restructured | '
               f'{pat/1e7:+.2f} | {total_npa[0]} | 0% | {disbursed_count} |')
    strat = strat.replace(old_row, new_row)
    open(strat_path, 'w', encoding='utf-8').write(strat)
    p('[12] STRATEGY.md history log updated')

    # ── Summary ────────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  SEPTEMBER 2020 MONTH-END SUMMARY  —  THE CLIFF')
    p('=' * 68)
    p(f'  Moratorium:  0 loans (0%)  — moratorium era is OVER')
    p(f'  OTR book:    {len(amber_loans)} loans  Rs{amber_amt/1e7:.1f} Cr  (tenure extended, DPD=0)')
    p(f'  Red NPA:     {len(red_loans)} new Sub-Standard  Rs{red_amt/1e7:.2f} Cr')
    p(f'  Green slip:  {slip_count} new Sub-Standard  Rs{slip_amt/1e7:.2f} Cr')
    p(f'  Total NPA:   {total_npa[0]} loans  Rs{total_npa[1]/1e7:.2f} Cr  ({npa_ratio:.2f}% of book)')
    p(f'  New loans:   {disbursed_count}  Rs{total_new_principal/1e7:.2f} Cr')
    p(f'  Provisions:  Rs{provisions/1e7:.2f} Cr  [OTR tranche 1 dominant]')
    p(f'  Monthly PAT: Rs{pat/1e7:.2f} Cr')
    p(f'  DECISION GATE:')
    p(f'    GNPA {npa_ratio:.2f}% [{gate("gnpa",npa_ratio)}]  |  PAT Rs{pat/1e7:.2f} Cr [{gate("pat",pat/1e7)}]')
    p(f'    CAR  [GREEN assumed]  |  Moratorium 0% [GREEN]  |  Disbursals {disbursed_count} [{gate("disbur",disbursed_count)}]')
    p(f'  NEXT MONTH: Watch OTR re-default signals. TLTRO remains on hold until GNPA < 4%.')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
