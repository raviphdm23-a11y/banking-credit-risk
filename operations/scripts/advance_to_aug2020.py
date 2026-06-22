"""
advance_to_aug2020.py
─────────────────────
Advances the Axis Bank simulation clock from 2020-07-31 to 2020-08-31.

Real-world context — August 2020:
  - RBI MPC August 6: repo rate held at 4.00%; accommodative stance confirmed
  - RBI announces One-Time Restructuring (OTR) framework August 6:
    COVID-stressed Standard accounts (as of Mar 1) can restructure without NPA
    classification; window open until Dec 31, 2020
  - Moratorium ENDS August 31 — final month; borrowers must decide
  - GDP Q1 FY2021 released August 28: -23.9% contraction (worst ever)
    Banks brace for post-moratorium NPA cliff in September
  - Unlock 3.0 continues; COVID cases still rising (first wave peak ~Sep)
  - ECLGS total national sanctions cross Rs 1.5 lakh Cr

Decision Gate result (July 2020):
  GNPA 0.82% GREEN | PAT -Rs4.51 Cr RED | CAR 16.51% GREEN
  Moratorium 30.6% RED | Disbursals 30 GREEN
  => Phase 1 Defensive: S1 + S2 activate; no offensive moves

Strategy initiatives this month:
  S1 — Moratorium stratification: classify all 1,339 moratorium loans
       into Green / Amber / Red using a scoring heuristic
  S2 — Voluntary floating provision: Rs 3 Cr added to other_liabilities
       as a pre-emptive buffer against post-moratorium NPA formation

Effects simulated:
  1. Moratorium opt-outs continue (deadline visible); net ~28%
  2. S1: moratorium_category column added; all moratorium loans scored
  3. S2: Rs 3 Cr floating provision built into balance sheet
  4. DPD aging of existing NPA loans; fresh NPAs from non-moratorium book (~5)
  5. New disbursals: 22 loans (Amber posture — ECLGS + secured only)
  6. Balance sheet AUG2020
  7. P&L AUG2020: COVID provision cycle ENDED — PAT turns POSITIVE
  8. Regulatory batch for 2020-08-31
  9. simulation_clock.json advanced
 10. STRATEGY.md history log updated

Run: python operations/scripts/advance_to_aug2020.py
"""

import os, sys, json, sqlite3, random
from datetime import date, timedelta, datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DB_PATH  = os.path.join(_REPO_ROOT, 'bank.db')
CLK_PATH = os.path.join(_REPO_ROOT, 'simulation_clock.json')

BANK_ID      = 'BANK010'
PREV_DATE    = '2020-07-31'
PREV_PERIOD  = 'JUL2020'
NEW_DATE     = '2020-08-31'
NEW_PERIOD   = 'AUG2020'

MORATORIUM_TARGET_RATE  = 0.28   # accelerating opt-outs pre-deadline; down from 31%
DEPOSIT_GROWTH          = 0.012  # +1.2% (moderating further as rates cut)
FLOATING_PROVISION_CR   = 3.0    # S2: Rs 3 Cr pre-emptive buffer

# S1 stratification thresholds
GREEN_THRESHOLD = 0.50   # 50% of moratorium book classified Green
AMBER_THRESHOLD = 0.35   # 35% Amber
# Red = remaining 15%

BRANCHES = ['BR-AXIS-001','BR-AXIS-002','BR-AXIS-003','BR-AXIS-004','BR-AXIS-005']

# 22 loans — Amber posture: ECLGS + secured only; no unsecured personal
NEW_LOAN_SPECS = [
    # ECLGS tail disbursals (low risk — government guaranteed)
    ('Business Loan', 2400000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1600000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3000000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1900000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 2700000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 1300000, 9.00, 48, 'MSME-ECLGS'),
    ('Business Loan', 3400000, 9.00, 48, 'MSME-ECLGS'),
    # Home loans (secured; RBI housing push; stamp duty relief)
    ('Home Loan', 4500000, 7.90, 240, 'housing-aug'),
    ('Home Loan', 3800000, 7.90, 180, 'housing-aug'),
    ('Home Loan', 5200000, 7.90, 240, 'housing-aug'),
    ('Home Loan', 6500000, 7.90, 300, 'housing-aug'),
    ('Home Loan', 3100000, 7.90, 120, 'housing-aug'),
    ('Home Loan', 4800000, 7.90, 240, 'housing-aug'),
    # Vehicle (secured; festive season pre-booking begins)
    ('Vehicle Loan', 1100000, 10.75, 60, 'vehicle-festive'),
    ('Vehicle Loan',  850000, 10.75, 48, 'vehicle-festive'),
    ('Vehicle Loan', 1350000, 10.75, 60, 'vehicle-festive'),
    ('Vehicle Loan',  700000, 10.75, 36, 'vehicle-festive'),
    # Agri / KCC (Kharif harvest financing)
    ('Business Loan', 480000, 8.50, 12, 'agri-kharif'),
    ('Business Loan', 620000, 8.50, 12, 'agri-kharif'),
    ('Business Loan', 390000, 8.50, 12, 'agri-kharif'),
    # Education (resuming — online learning)
    ('Education Loan', 750000, 11.00, 60, 'education-aug'),
    ('Education Loan', 950000, 11.00, 72, 'education-aug'),
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


def _ensure_moratorium_category(cur):
    """Add moratorium_category column if absent (idempotent)."""
    cols = [r[1] for r in cur.execute("PRAGMA table_info(loans)").fetchall()]
    if 'moratorium_category' not in cols:
        cur.execute("ALTER TABLE loans ADD COLUMN moratorium_category TEXT")


def _score_moratorium_loan(loan):
    """
    Heuristic scoring for moratorium stratification.
    Returns 'G' (Green), 'A' (Amber), or 'R' (Red).

    Green  — high probability of resuming EMIs Sep 1:
             secured loans (home/vehicle) with outstanding < Rs 50 L
    Red    — high default risk: unsecured + high outstanding, or already
             had DPD > 0 before moratorium
    Amber  — everything in between; candidates for OTR restructuring
    """
    ltype  = loan.get('type', '')
    amt    = loan.get('outstanding', 0) or 0
    rate   = loan.get('rate', 0) or 0

    secured_types = ('Home Loan', 'Vehicle Loan')
    risky_types   = ('Personal Loan', 'Education Loan')

    if ltype in secured_types and amt < 5_000_000:       # secured, < Rs 50 L
        return 'G'
    if ltype in risky_types and amt > 3_000_000:         # unsecured, > Rs 30 L
        return 'R'
    if ltype == 'Business Loan' and rate >= 11.0:        # high-rate MSME = stressed
        return 'R'
    if ltype == 'Business Loan' and amt > 8_000_000:     # large business loan
        return 'A'
    if ltype in secured_types:                           # secured but larger
        return 'A'
    return 'A'                                           # default: Amber


def run(db_path=DB_PATH, verbose=True):
    random.seed(2020_08)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    def p(msg):
        if verbose:
            print(msg)

    p('')
    p('=' * 68)
    p('  Advancing simulation: 2020-07-31 --> 2020-08-31')
    p('  RBI OTR announced | Moratorium final month | PAT turns positive')
    p('  Strategy: S1 stratification + S2 floating provision')
    p('=' * 68)

    # ── Step 1: Moratorium opt-outs ───────────────────────────────────────────
    total_eligible = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND days_past_due < 90",
        (BANK_ID,)).fetchone()[0]
    current_morat = cur.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND moratorium=1",
        (BANK_ID,)).fetchone()[0]
    target_morat  = int(total_eligible * MORATORIUM_TARGET_RATE)
    opt_out_count = max(0, current_morat - target_morat)

    if opt_out_count > 0:
        opt_out_ids = [r[0] for r in cur.execute(
            "SELECT id FROM loans WHERE bank_id=? AND moratorium=1 "
            "ORDER BY RANDOM() LIMIT ?", (BANK_ID, opt_out_count)).fetchall()]
        cur.execute(
            "UPDATE loans SET moratorium=0, moratorium_end_date=NULL "
            "WHERE bank_id=? AND id IN ({})".format(','.join('?'*len(opt_out_ids))),
            [BANK_ID] + opt_out_ids)

    remaining_morat = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(outstanding),0) FROM loans "
        "WHERE bank_id=? AND moratorium=1", (BANK_ID,)).fetchone()
    conn.commit()
    p(f'\n[1] Moratorium opt-outs: {opt_out_count} borrowers exited before Aug 31 deadline')
    p(f'    Remaining moratorium: {remaining_morat[0]:,} loans ({MORATORIUM_TARGET_RATE*100:.0f}% of book)')
    p(f'    Moratorium book: Rs{remaining_morat[1]/1e7:.1f} Cr')

    # ── Step 2: S1 — Stratify moratorium loans into G / A / R ─────────────────
    _ensure_moratorium_category(cur)

    morat_loans = [dict(r) for r in cur.execute(
        "SELECT id, type, outstanding, rate FROM loans "
        "WHERE bank_id=? AND moratorium=1", (BANK_ID,)).fetchall()]

    g_count = a_count = r_count = 0
    g_amt   = a_amt   = r_amt   = 0.0

    for loan in morat_loans:
        cat = _score_moratorium_loan(loan)
        cur.execute(
            "UPDATE loans SET moratorium_category=? WHERE bank_id=? AND id=?",
            (cat, BANK_ID, loan['id']))
        if cat == 'G':
            g_count += 1; g_amt += loan['outstanding']
        elif cat == 'A':
            a_count += 1; a_amt += loan['outstanding']
        else:
            r_count += 1; r_amt += loan['outstanding']

    conn.commit()
    total_morat_amt = g_amt + a_amt + r_amt
    p(f'\n[2] S1 — Moratorium stratification complete')
    p(f'    GREEN  (will resume Sep 1): {g_count:4d} loans  Rs{g_amt/1e7:.1f} Cr  '
      f'({g_count/len(morat_loans)*100:.0f}% of moratorium book)')
    p(f'    AMBER  (OTR candidates):   {a_count:4d} loans  Rs{a_amt/1e7:.1f} Cr  '
      f'({a_count/len(morat_loans)*100:.0f}% of moratorium book)')
    p(f'    RED    (likely default):   {r_count:4d} loans  Rs{r_amt/1e7:.1f} Cr  '
      f'({r_count/len(morat_loans)*100:.0f}% of moratorium book)')
    p(f'    OTR window open until Dec 31 — Amber cohort will be filed in September')
    p(f'    Red cohort Rs{r_amt/1e7:.1f} Cr — watch carefully post-moratorium')

    # ── Step 3: DPD aging + fresh NPA formation ────────────────────────────────
    # Reset seed-artefact DPD on Standard loans (same cleanup as prior months)
    cur.execute("""
        UPDATE loans SET days_past_due = 0
        WHERE bank_id=? AND moratorium=0 AND days_past_due < 90
          AND loan_classification IN ('Standard','Performing')
    """, (BANK_ID,))

    # Age existing NPA loans by +30
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

    # Fresh NPAs: 5 loans from non-moratorium book (hospitality / unsecured)
    random.seed(20200801)
    fresh_pool = [dict(r) for r in cur.execute("""
        SELECT id, outstanding FROM loans
        WHERE bank_id=? AND moratorium=0 AND days_past_due=0
          AND loan_classification IN ('Standard','Performing')
          AND type IN ('Personal Loan','Business Loan')
        ORDER BY outstanding DESC LIMIT 150
    """, (BANK_ID,)).fetchall()]
    random.shuffle(fresh_pool)
    fresh_npa   = fresh_pool[:5]
    fresh_amt   = sum(l['outstanding'] for l in fresh_npa)
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
    p(f'\n[3] DPD aged for existing NPA loans')
    p(f'    Upgraded to Doubtful-1: {newly_doubtful[0]} loans (Rs{newly_doubtful[1]/1e7:.2f} Cr)')
    p(f'    Fresh Sub-Standard:     {len(fresh_npa)} loans (Rs{fresh_amt/1e7:.2f} Cr)')
    p(f'    Total NPA book:         {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')

    # ── Step 4: New disbursals — 22 loans, Amber posture ─────────────────────
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
        loan_id = f'LOAN-AUG2020-{i+1:02d}'
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
            (date(2020, 8, 31) + timedelta(days=tenure*30)).isoformat(),
            principal, 'Active', random.choice(BRANCHES),
            'Standard', EXPOSURE_MAP.get(ltype, 'retail_unsecured'),
            0, 0, None, f'aug2020_{sector}'
        ))
        disbursed_count += 1
        total_new_principal += principal

    conn.commit()
    eclgs_c = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'ECLGS' in s[4])
    home_c  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'housing' in s[4])
    veh_c   = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'vehicle' in s[4])
    agri_c  = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'agri' in s[4])
    edu_c   = sum(1 for s in NEW_LOAN_SPECS[:disbursed_count] if 'education' in s[4])
    p(f'\n[4] New disbursals: {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr  [Amber posture]')
    p(f'    {eclgs_c} ECLGS + {home_c} Home + {veh_c} Vehicle + {agri_c} Agri + {edu_c} Education')
    p(f'    No unsecured personal loans — per Amber posture rule')

    # ── Step 5: Balance sheet AUG2020 ─────────────────────────────────────────
    prev_bs = dict(cur.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?",
        (BANK_ID, PREV_PERIOD)).fetchone())

    prev_dep = (prev_bs['deposits_demand'] + prev_bs['deposits_savings']
                + prev_bs['deposits_term'])
    new_dep  = prev_dep * (1 + DEPOSIT_GROWTH)
    new_adv  = cur.execute(
        "SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?",
        (BANK_ID,)).fetchone()[0]

    capital_base     = prev_bs['equity_capital'] + prev_bs['reserves_surplus']
    equity_capital   = prev_bs['equity_capital']
    reserves_surplus = prev_bs['reserves_surplus']

    deposits_demand  = 0.12 * new_dep
    deposits_savings = 0.48 * new_dep
    deposits_term    = new_dep - deposits_demand - deposits_savings

    # S2: floating provision Rs 3 Cr added to other_liabilities
    floating_provision = FLOATING_PROVISION_CR * 1e7
    other_liabilities  = 0.040 * new_dep + floating_provision

    total_lc = capital_base + new_dep + other_liabilities

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
        'advance_to_aug2020', now
    ))
    conn.commit()

    ta_chk = fixed_sum + balances_with_banks
    tl_chk = capital_base + new_dep + borrowings + other_liabilities
    p(f'\n[5] Balance sheet AUG2020 seeded')
    p(f'    Total Assets: Rs{ta_chk/1e7:.1f} Cr  |  L+C: Rs{tl_chk/1e7:.1f} Cr  |  Diff: {abs(ta_chk-tl_chk):.2f}')
    p(f'    Advances: Rs{new_adv/1e7:.1f} Cr  |  Deposits: Rs{new_dep/1e7:.1f} Cr')
    p(f'    S2: Floating provision Rs{FLOATING_PROVISION_CR:.0f} Cr in other_liabilities')

    # ── Step 6: Monthly P&L AUG2020 ───────────────────────────────────────────
    # COVID provision cycle ENDED in July — zero COVID provision this month
    blended_rate = cur.execute(
        "SELECT AVG(rate) FROM loans WHERE bank_id=? AND status='Active'",
        (BANK_ID,)).fetchone()[0] or 10.40
    effective_rate = blended_rate - 0.03   # minimal further transmission

    int_on_adv   = round(new_adv     * effective_rate / 100 / 12, 2)
    int_on_inv   = round(investments * 5.85 / 100 / 12, 2)
    int_earned   = round(int_on_adv + int_on_inv, 2)
    other_income = round(int_earned * 0.155, 2)   # fee income recovering

    deposit_rate      = 3.80   # TD rates cut aggressively; SB rate 3%
    int_on_dep        = round(new_dep   * deposit_rate / 100 / 12, 2)
    int_on_borrowings = round(borrowings * 4.40 / 100 / 12, 2)
    int_expended      = round(int_on_dep + int_on_borrowings, 2)

    nii          = round(int_earned - int_expended, 2)
    total_income = round(int_earned + other_income, 2)

    employee_cost = round(nii * 0.270, 2)
    other_opex    = round(nii * 0.160, 2)
    opex          = round(employee_cost + other_opex, 2)
    op_profit     = round(nii + other_income - opex, 2)

    # No COVID provision — normal provisions only
    normal_prov      = round(new_adv * 0.005 / 12, 2)
    doubtful_prov    = round(newly_doubtful[1] * 0.10, 2)
    substandard_prov = round(fresh_amt * 0.15, 2)
    provisions       = round(normal_prov + doubtful_prov + substandard_prov, 2)

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
        [BANK_ID, NEW_PERIOD, '2020-08-01', NEW_DATE, 'INR', 'INR',
         int_on_adv, int_on_inv, int_earned, other_income, total_income,
         int_on_dep, int_on_borrowings, int_expended,
         employee_cost, other_opex, opex, nii, op_profit,
         provisions, pbt, tax, pat, now])
    conn.commit()

    p(f'\n[6] Monthly P&L AUG2020 seeded')
    p(f'    NII:                 Rs{nii/1e7:.2f} Cr  (lending ~{effective_rate:.2f}%, deposit {deposit_rate}%)')
    p(f'    COVID provision:     Rs0.00 Cr  (cycle ENDED — 0 for first time since April)')
    p(f'    Normal provisions:   Rs{provisions/1e7:.2f} Cr')
    p(f'    PBT: Rs{pbt/1e7:.2f} Cr  |  PAT: Rs{pat/1e7:.2f} Cr')
    if pat > 0:
        p(f'    *** FIRST POSITIVE PAT SINCE MARCH 2020 ***')

    # ── Step 7: Regulatory batch ──────────────────────────────────────────────
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'run_regulatory_batch',
        os.path.join(_REPO_ROOT, 'operations', 'scripts', 'run_regulatory_batch.py'))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    rb.run_batch(db_path=db_path, report_date=NEW_DATE, verbose=False)
    p('\n[7] Regulatory batch re-run for 2020-08-31')

    # ── Step 8: Advance clock ──────────────────────────────────────────────────
    clk = json.load(open(CLK_PATH))
    clk['sim_date']     = NEW_DATE
    clk['sim_period']   = NEW_PERIOD
    clk['prior_period'] = PREV_PERIOD
    clk['last_updated'] = NEW_DATE
    clk['notes'] = (
        'RBI OTR framework announced Aug 6 (window to Dec 31). '
        'Moratorium ends Aug 31 — final month. '
        f'Moratorium opt-outs: {opt_out_count} exits (31%->28%). '
        f'S1 stratification: {g_count}G / {a_count}A / {r_count}R. '
        f'S2: Rs{FLOATING_PROVISION_CR:.0f} Cr floating provision built. '
        f'{len(fresh_npa)} fresh Sub-Standard NPAs; total NPA {total_npa[0]} loans. '
        f'{disbursed_count} disbursals (Amber posture — secured + ECLGS only). '
        f'PAT Rs{pat/1e7:.2f} Cr — {"POSITIVE — first since March 2020" if pat>0 else "negative"}.'
    )
    json.dump(clk, open(CLK_PATH, 'w'), indent=2)
    p(f'\n[8] simulation_clock.json advanced to {NEW_DATE} (period: {NEW_PERIOD})')

    # ── Step 9: Update STRATEGY.md history log ────────────────────────────────
    strat_path = os.path.join(_REPO_ROOT, 'STRATEGY.md')
    strat = open(strat_path, encoding='utf-8').read()
    old_row = '| AUG2020 | — | — | — | — | — |'
    new_row = (f'| AUG2020 | RBI OTR announced; moratorium ends; S1+S2 activated | '
               f'{pat/1e7:+.2f} | {total_npa[0]} | {MORATORIUM_TARGET_RATE*100:.0f}% | {disbursed_count} |')
    if old_row in strat:
        strat = strat.replace(old_row, new_row)
    strat = strat.replace(
        '| S1 — Moratorium stratification | Pending | August 2020 | — |',
        f'| S1 — Moratorium stratification | **Active** | August 2020 | {g_count}G/{a_count}A/{r_count}R scored |'
    ).replace(
        '| S2 — Voluntary provision buffer | Pending | August 2020 | — |',
        f'| S2 — Voluntary provision buffer | **Active** | August 2020 | Rs{FLOATING_PROVISION_CR:.0f} Cr built in other_liabilities |'
    )
    open(strat_path, 'w', encoding='utf-8').write(strat)
    p('\n[9] STRATEGY.md updated — history log and initiative tracker')

    # ── Summary ────────────────────────────────────────────────────────────────
    p('')
    p('=' * 68)
    p('  AUGUST 2020 MONTH-END SUMMARY')
    p('=' * 68)
    p(f'  Total Assets:          Rs{ta_chk/1e7:.1f} Cr')
    p(f'  Advances (net):        Rs{new_adv/1e7:.1f} Cr')
    p(f'  Deposits:              Rs{new_dep/1e7:.1f} Cr')
    p(f'  Moratorium (final):    {remaining_morat[0]:,} loans ({MORATORIUM_TARGET_RATE*100:.0f}%)  '
      f'Rs{remaining_morat[1]/1e7:.1f} Cr  ENDS AUG 31')
    p(f'  Stratification:        {g_count} Green / {a_count} Amber / {r_count} Red')
    p(f'  Floating provision:    Rs{FLOATING_PROVISION_CR:.0f} Cr  [S2 activated]')
    p(f'  Total NPA:             {total_npa[0]} loans (Rs{total_npa[1]/1e7:.2f} Cr)')
    p(f'  New disbursals:        {disbursed_count} loans | Rs{total_new_principal/1e7:.2f} Cr')
    p(f'  Monthly NII:           Rs{nii/1e7:.2f} Cr')
    p(f'  Monthly provisions:    Rs{provisions/1e7:.2f} Cr  [no COVID provision]')
    p(f'  Monthly PAT:           Rs{pat/1e7:.2f} Cr{"  *** FIRST POSITIVE SINCE MARCH ***" if pat>0 else ""}')
    p(f'  Next month:            MORATORIUM CLIFF — watch Sep NPA formation closely')
    p('=' * 68)

    conn.close()


if __name__ == '__main__':
    run()
