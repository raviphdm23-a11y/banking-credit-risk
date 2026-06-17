"""
regulatory_engine.py
────────────────────
Pure Basel III / RBI regulatory computations for the Regulatory Reporting
department. No database access — every function takes plain dicts/lists (fed by
operations/scripts/run_regulatory_batch.py) and returns plain dicts, so the
logic is easy to test and reuse.

Three levels of report:
    • client exposure   — per loan: EAD, PD, LGD, risk weight, RWA, capital
                          charge, expected loss, IRAC provision
    • bank capital      — credit + operational + market RWA, Tier-1/Tier-2
                          capital, CRAR (CAR), CET1, leverage ratio
    • bank liquidity     — HQLA, LCR, ASF/RSF, NSFR, CRR, SLR

────────────────────────────────────────────────────────────────────────────
IMPORTANT — synthetic-data proxies
This platform's bank.db is a synthetic teaching dataset. It has a loan book,
customer deposits and risk metrics, but NO equity/balance-sheet ledger and no
trading book. Where a real Basel III return would read those off the books, we
use clearly-labelled proxies (see the *_PROXY constants below). Every proxy is
surfaced in the report `assumptions` block so the UI can disclose it. The
*relationships* (higher risk density → lower CAR, loans funded beyond retail
deposits → weaker NSFR) are modelled correctly; only the absolute capital/HQLA
anchors are assumed.
────────────────────────────────────────────────────────────────────────────
"""

from datetime import date

# ── RBI / Basel III regulatory minimums (India, FY2024 norms) ────────────────
RBI_THRESHOLDS = {
    'car_min':      11.5,   # CRAR: 9.0% Pillar-1 + 2.5% Capital Conservation Buffer
    'tier1_min':     9.5,   # 7.0% + 2.5% CCB
    'cet1_min':      8.0,   # 5.5% + 2.5% CCB
    'leverage_min':  3.5,   # Tier-1 leverage ratio
    'lcr_min':     100.0,   # Liquidity Coverage Ratio
    'nsfr_min':    100.0,   # Net Stable Funding Ratio
    'crr_min':       4.5,   # Cash Reserve Ratio (% of NDTL)
    'slr_min':      18.0,   # Statutory Liquidity Ratio (% of NDTL)
}

# ── RBI Standardised-Approach risk weights for the retail/banking book ───────
# (representative values; real RW varies by LTV and ticket size)
RISK_WEIGHT_BY_TYPE = {
    'Home Loan':      0.35,   # housing, avg of 35-50% by LTV
    'Vehicle Loan':   0.75,   # regulatory retail, secured
    'Education Loan': 0.75,   # regulatory retail
    'Personal Loan':  1.00,   # unsecured consumer credit
    'Business Loan':  1.00,   # SME / commercial
}
DEFAULT_RISK_WEIGHT = 1.00
NPA_RISK_WEIGHT      = 1.50   # NPA with provision cover < 20%

# ── IRAC provisioning rates (RBI Master Circular) ────────────────────────────
PROVISION_RATES = {
    'Standard':  0.0040,   # 0.40% general provision on standard assets
    'NPA':       0.15,     # sub-standard, secured
    'Sub-Standard': 0.15,
    'Doubtful':  0.40,
    'Loss':      1.00,
}

# ── LGD by loan type (downturn LGD, secured collateral lowers it) ────────────
LGD_BY_TYPE = {
    'Home Loan':      0.20,
    'Vehicle Loan':   0.35,
    'Education Loan': 0.50,
    'Personal Loan':  0.65,
    'Business Loan':  0.45,
}
DEFAULT_LGD = 0.45

# ── Synthetic balance-sheet proxies (see module docstring) ───────────────────
CAPITAL_TO_ASSETS_PROXY = 0.120   # Tier-1 capital ≈ 12% of banking-book assets
TIER2_SUBDEBT_PROXY     = 0.015   # subordinated debt ≈ 1.5% of total RWA
GEN_PROV_T2_CAP         = 0.0125  # general provisions admissible as T2, ≤1.25% credit RWA
OP_RISK_ALPHA           = 0.15    # Basel Basic Indicator Approach alpha
RWA_DENSITY_FOR_OP      = 12.5    # 1 / 8% — capital→RWA scaling

# ── Balance-sheet-only banks (foreign/group entities carried without a per-loan
#    ledger): derive credit/operational RWA from the stored net advances. ───────
FOREIGN_AVG_RISK_WEIGHT     = 0.75    # blended Standardised-Approach RW on the book
FOREIGN_GROSS_INCOME_YIELD  = 0.095   # gross income proxy ≈ 9.5% of net advances
FOREIGN_PROVISION_RATE      = 0.010   # general provision ≈ 1.0% of net advances

HQLA_TO_FUNDING_PROXY   = 0.30    # HQLA ≈ 30% of total funding (CRR+SLR+buffer)
RETAIL_RUNOFF           = 0.10    # 30-day stressed run-off on retail deposits
WHOLESALE_RUNOFF        = 0.25    # 30-day stressed run-off on wholesale funding
ASF_RETAIL              = 0.90    # available stable funding factor, retail deposits
ASF_WHOLESALE           = 0.50    # ASF factor, wholesale/market funding
ASF_CAPITAL             = 1.00    # ASF factor, regulatory capital
RSF_LOANS               = 0.65    # required stable funding factor, retail loan book
RSF_HQLA                = 0.05    # RSF factor, HQLA
CRR_HOLDING_PROXY       = 0.050   # cash with RBI ≈ 5.0% of NDTL
SLR_HOLDING_PROXY       = 0.205   # SLR securities ≈ 20.5% of NDTL


def _status(actual, minimum, watch_buffer=1.0):
    """Compliant / Watch / Breach against a regulatory floor."""
    if actual < minimum:
        return 'Breach'
    if actual < minimum + watch_buffer:
        return 'Watch'
    return 'Compliant'


# ── balance-sheet helpers (when a stored bank_balance_sheet row is available) ─
def bs_total_assets(bs):
    """Total assets from a bank_balance_sheet dict (raw INR)."""
    return sum(float(bs.get(k) or 0) for k in
               ('cash_with_rbi', 'balances_with_banks', 'investments',
                'advances_net', 'fixed_assets', 'other_assets'))


def bs_total_deposits(bs):
    return sum(float(bs.get(k) or 0) for k in
               ('deposits_demand', 'deposits_savings', 'deposits_term'))


# ════════════════════════════════════════════════════════════════════════════
# CLIENT-LEVEL EXPOSURE
# ════════════════════════════════════════════════════════════════════════════
def client_exposure(loan, metrics=None, customer_name=None):
    """Regulatory exposure for a single loan.

    Args:
        loan (dict): row from `loans` (type, outstanding, loan_classification, …)
        metrics (dict|None): row from `credit_risk_metrics` (pd_score, …)
        customer_name (str|None)
    """
    ead = float(loan.get('outstanding') or 0)
    ltype = loan.get('type') or ''
    classification = loan.get('loan_classification') or 'Standard'
    is_npa = classification not in ('Standard', 'Performing')

    # PD: prefer observed model score, else infer from classification
    if metrics and metrics.get('pd_score') is not None:
        pd = float(metrics['pd_score'])
    else:
        pd = 0.95 if is_npa else 0.02
    pd = max(0.0003, min(1.0, pd))

    lgd = LGD_BY_TYPE.get(ltype, DEFAULT_LGD)

    risk_weight = NPA_RISK_WEIGHT if is_npa else RISK_WEIGHT_BY_TYPE.get(ltype, DEFAULT_RISK_WEIGHT)
    rwa = ead * risk_weight
    capital_charge = rwa * (RBI_THRESHOLDS['car_min'] / 100.0)

    prov_rate = PROVISION_RATES.get(classification, PROVISION_RATES['Standard'] if not is_npa else 0.15)
    provision = ead * prov_rate
    expected_loss = pd * lgd * ead

    return {
        'cid':            loan.get('cid'),
        'customer_name':  customer_name,
        'loan_id':        loan.get('id'),
        'loan_type':      ltype,
        'classification': classification,
        'ead':            round(ead, 2),
        'pd':             round(pd, 4),
        'lgd':            round(lgd, 4),
        'risk_weight':    round(risk_weight * 100, 1),   # as %
        'rwa':            round(rwa, 2),
        'capital_charge': round(capital_charge, 2),
        'expected_loss':  round(expected_loss, 2),
        'provision':      round(provision, 2),
    }


# ════════════════════════════════════════════════════════════════════════════
# BANK-LEVEL CAPITAL ADEQUACY
# ════════════════════════════════════════════════════════════════════════════
def bank_capital_report(bank_id, loans, accounts, metrics_by_lid, report_date=None,
                        balance_sheet=None):
    """Basel III capital-adequacy return for one bank.

    If `balance_sheet` (a bank_balance_sheet row dict) is supplied, the capital
    base and total assets are read from it (real figures); otherwise the
    synthetic proxies are used.
    """
    report_date = report_date or date.today().isoformat()

    exposures = []
    credit_rwa = 0.0
    total_provisions = 0.0
    for l in loans:
        e = client_exposure(l, metrics_by_lid.get(l.get('id')))
        exposures.append(e)
        credit_rwa += e['rwa']
        total_provisions += e['provision']

    loan_book   = sum(float(l.get('outstanding') or 0) for l in loans)
    deposits    = sum(float(a.get('balance') or 0) for a in accounts)

    # Operational-risk RWA via Basel Basic Indicator Approach.
    # Gross income proxy = annual interest income on the loan book.
    gross_income = sum(float(l.get('outstanding') or 0) * float(l.get('rate') or 0) / 100.0
                       for l in loans)
    operational_rwa = OP_RISK_ALPHA * gross_income * RWA_DENSITY_FOR_OP
    market_rwa = 0.0   # no trading book in this dataset

    # Balance-sheet-only banks (no per-loan rows, e.g. foreign group entities):
    # derive credit & operational RWA from the stored net advances.
    if not loans and balance_sheet:
        adv = float(balance_sheet.get('advances_net') or 0)
        credit_rwa      = adv * FOREIGN_AVG_RISK_WEIGHT
        loan_book       = adv
        gross_income    = adv * FOREIGN_GROSS_INCOME_YIELD
        operational_rwa = OP_RISK_ALPHA * gross_income * RWA_DENSITY_FOR_OP
        total_provisions = adv * FOREIGN_PROVISION_RATE

    total_rwa = credit_rwa + operational_rwa + market_rwa

    gen_prov_admissible = min(total_provisions, GEN_PROV_T2_CAP * credit_rwa)

    if balance_sheet:
        # Real capital base from the stored balance sheet (CET1 = equity + reserves).
        tier1_capital = (float(balance_sheet.get('equity_capital') or 0)
                         + float(balance_sheet.get('reserves_surplus') or 0))
        tier2_capital = gen_prov_admissible
        total_capital = tier1_capital + tier2_capital
        total_assets  = bs_total_assets(balance_sheet)
        capital_source = 'bank_balance_sheet ' + str(balance_sheet.get('period', ''))
    else:
        # Capital base (synthetic proxy — see module docstring).
        total_assets = loan_book + HQLA_TO_FUNDING_PROXY * max(loan_book, deposits)
        tier1_capital = CAPITAL_TO_ASSETS_PROXY * total_assets
        tier2_capital = gen_prov_admissible + TIER2_SUBDEBT_PROXY * total_rwa
        total_capital = tier1_capital + tier2_capital
        capital_source = 'synthetic proxy (no balance sheet on file)'

    rwa_safe = total_rwa or 1.0
    assets_safe = total_assets or 1.0
    car          = total_capital / rwa_safe * 100
    tier1_ratio  = tier1_capital / rwa_safe * 100
    cet1_ratio   = tier1_capital / rwa_safe * 100   # assume Tier-1 is all CET1
    leverage     = tier1_capital / assets_safe * 100

    return {
        'bank_id':        bank_id,
        'report_date':    report_date,
        'credit_rwa':     round(credit_rwa, 2),
        'operational_rwa': round(operational_rwa, 2),
        'market_rwa':     round(market_rwa, 2),
        'total_rwa':      round(total_rwa, 2),
        'tier1_capital':  round(tier1_capital, 2),
        'tier2_capital':  round(tier2_capital, 2),
        'total_capital':  round(total_capital, 2),
        'total_assets':   round(total_assets, 2),
        'loan_book':      round(loan_book, 2),
        'deposits':       round(deposits, 2),
        'rwa_density':    round(total_rwa / assets_safe * 100, 1),
        'car':            round(car, 2),
        'tier1_ratio':    round(tier1_ratio, 2),
        'cet1_ratio':     round(cet1_ratio, 2),
        'leverage_ratio': round(leverage, 2),
        'car_status':     _status(car, RBI_THRESHOLDS['car_min']),
        'tier1_status':   _status(tier1_ratio, RBI_THRESHOLDS['tier1_min']),
        'cet1_status':    _status(cet1_ratio, RBI_THRESHOLDS['cet1_min']),
        'leverage_status': _status(leverage, RBI_THRESHOLDS['leverage_min']),
        'total_provisions': round(total_provisions, 2),
        'num_loans':      len(loans),
        'num_npa':        sum(1 for l in loans
                              if (l.get('loan_classification') or 'Standard') not in ('Standard', 'Performing')),
        'capital_source': capital_source,
        'assumptions': {
            'capital_source': capital_source,
            'capital_to_assets_proxy': None if balance_sheet else CAPITAL_TO_ASSETS_PROXY,
            'op_risk_method': 'Basel Basic Indicator Approach (alpha=15% of gross income)',
            'market_rwa': 'nil — dataset has no trading book',
            'note': ('Capital base & total assets sourced from the stored balance sheet; '
                     'RWA computed from the live loan book.' if balance_sheet else
                     'Capital base is a synthetic proxy; RWA is computed from the live loan book.'),
        },
        'exposures': exposures,
    }


# ════════════════════════════════════════════════════════════════════════════
# BANK-LEVEL LIQUIDITY
# ════════════════════════════════════════════════════════════════════════════
def bank_liquidity_report(bank_id, accounts, loans, total_capital=0.0, report_date=None,
                          balance_sheet=None):
    """Basel III liquidity return (LCR, NSFR) + RBI CRR/SLR for one bank.

    With a `balance_sheet`, HQLA (cash with RBI + balances with banks + SLR
    investments), wholesale funding (borrowings) and CRR/SLR holdings are read
    off the real sheet; otherwise Basel-style proxies are used.
    """
    report_date = report_date or date.today().isoformat()

    retail_deposits = sum(float(a.get('balance') or 0) for a in accounts)
    loan_book       = sum(float(l.get('outstanding') or 0) for l in loans)
    # Balance-sheet-only banks have no account/loan rows — read totals off the sheet.
    if balance_sheet and retail_deposits <= 0:
        retail_deposits = bs_total_deposits(balance_sheet)
    if balance_sheet and loan_book <= 0:
        loan_book = float(balance_sheet.get('advances_net') or 0)
    ndtl            = retail_deposits   # net demand & time liabilities proxy

    if balance_sheet:
        cash_rbi   = float(balance_sheet.get('cash_with_rbi') or 0)
        bal_banks  = float(balance_sheet.get('balances_with_banks') or 0)
        investments = float(balance_sheet.get('investments') or 0)
        wholesale_funding = float(balance_sheet.get('borrowings') or 0)
        total_funding = retail_deposits + wholesale_funding
        hqla = cash_rbi + bal_banks + investments          # cash + SLR securities
        crr_ratio = cash_rbi / (ndtl or 1.0) * 100
        slr_ratio = investments / (ndtl or 1.0) * 100
        liq_source = 'bank_balance_sheet ' + str(balance_sheet.get('period', ''))
    else:
        # Loans beyond the retail deposit base are funded with wholesale/market money.
        wholesale_funding = max(0.0, loan_book - retail_deposits)
        total_funding     = retail_deposits + wholesale_funding
        hqla = HQLA_TO_FUNDING_PROXY * total_funding
        crr_ratio = CRR_HOLDING_PROXY * 100
        slr_ratio = SLR_HOLDING_PROXY * 100
        liq_source = 'synthetic proxy (no balance sheet on file)'

    # LCR — 30-day stressed net cash outflows
    net_outflows = RETAIL_RUNOFF * retail_deposits + WHOLESALE_RUNOFF * wholesale_funding
    net_outflows = max(net_outflows, 1.0)
    lcr = hqla / net_outflows * 100

    # NSFR — available vs required stable funding
    asf = (ASF_RETAIL * retail_deposits + ASF_WHOLESALE * wholesale_funding
           + ASF_CAPITAL * total_capital)
    rsf = RSF_LOANS * loan_book + RSF_HQLA * hqla
    rsf = max(rsf, 1.0)
    nsfr = asf / rsf * 100

    return {
        'bank_id':          bank_id,
        'report_date':      report_date,
        'retail_deposits':  round(retail_deposits, 2),
        'wholesale_funding': round(wholesale_funding, 2),
        'total_funding':    round(total_funding, 2),
        'ndtl':             round(ndtl, 2),
        'hqla':             round(hqla, 2),
        'net_outflows_30d': round(net_outflows, 2),
        'lcr':              round(lcr, 2),
        'asf':              round(asf, 2),
        'rsf':              round(rsf, 2),
        'nsfr':             round(nsfr, 2),
        'crr_ratio':        round(crr_ratio, 2),
        'slr_ratio':        round(slr_ratio, 2),
        'lcr_status':       _status(lcr, RBI_THRESHOLDS['lcr_min'], watch_buffer=10),
        'nsfr_status':      _status(nsfr, RBI_THRESHOLDS['nsfr_min'], watch_buffer=10),
        'crr_status':       _status(crr_ratio, RBI_THRESHOLDS['crr_min'], watch_buffer=0.25),
        'slr_status':       _status(slr_ratio, RBI_THRESHOLDS['slr_min'], watch_buffer=0.5),
        'liquidity_source': liq_source,
        'assumptions': {
            'liquidity_source': liq_source,
            'hqla_to_funding_proxy': None if balance_sheet else HQLA_TO_FUNDING_PROXY,
            'funding_model': ('retail deposits + borrowings from the stored balance sheet'
                              if balance_sheet else
                              'retail deposits (live) + wholesale plug for the loan-to-deposit gap'),
            'note': ('HQLA, CRR/SLR holdings and wholesale funding sourced from the stored '
                     'balance sheet; run-off factors remain Basel-style assumptions.'
                     if balance_sheet else
                     'HQLA and run-off factors are Basel-style proxies; deposits & loan book are live.'),
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# COMPLIANCE ASSESSMENT (maps metrics → RBI requirement_ids)
# ════════════════════════════════════════════════════════════════════════════
def compliance_assessment(capital_report, liquidity_report):
    """Return a list of compliance findings keyed to regulatory_requirements."""
    th = RBI_THRESHOLDS
    findings = [
        {'requirement_id': 'REQ-RBI-002', 'metric': 'CRAR (CAR)',
         'actual': capital_report['car'], 'required': th['car_min'],
         'status': capital_report['car_status']},
        {'requirement_id': 'REQ-RBI-002', 'metric': 'CET1 Ratio',
         'actual': capital_report['cet1_ratio'], 'required': th['cet1_min'],
         'status': capital_report['cet1_status']},
        {'requirement_id': 'REQ-RBI-005', 'metric': 'CRR',
         'actual': liquidity_report['crr_ratio'], 'required': th['crr_min'],
         'status': liquidity_report['crr_status']},
        {'requirement_id': 'REQ-RBI-005', 'metric': 'SLR',
         'actual': liquidity_report['slr_ratio'], 'required': th['slr_min'],
         'status': liquidity_report['slr_status']},
        {'requirement_id': 'REQ-RBI-002', 'metric': 'LCR',
         'actual': liquidity_report['lcr'], 'required': th['lcr_min'],
         'status': liquidity_report['lcr_status']},
        {'requirement_id': 'REQ-RBI-002', 'metric': 'NSFR',
         'actual': liquidity_report['nsfr'], 'required': th['nsfr_min'],
         'status': liquidity_report['nsfr_status']},
        {'requirement_id': 'REQ-RBI-001', 'metric': 'NPA Ratio',
         'actual': round(capital_report['num_npa'] / max(capital_report['num_loans'], 1) * 100, 2),
         'required': None, 'status': 'Monitored'},
    ]
    return findings
