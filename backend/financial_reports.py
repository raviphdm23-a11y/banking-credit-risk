"""
financial_reports.py
────────────────────
Pure assembly layer for the Financial Reporting & Disclosures department. It
turns the stored balance sheet (`bank_balance_sheet`), P&L (`bank_profit_loss`)
and the regulatory engine's capital/liquidity returns into four presentation-
ready reports — per bank and consolidated (all-banks aggregate):

    • balance_sheet  — RBI Schedule III (Form A) statement of financial position
    • profit_loss    — income statement (Form B style)
    • key_ratios     — NIM, ROA, ROE, cost-income, CRAR, GNPA, PCR, CD, CASA, LCR…
    • pillar3        — Basel III Pillar 3 disclosure tables (capital, RWA, leverage, liquidity)

No DB access — callers pass plain dicts (app.py gathers them). Every figure is
raw INR; the UI/PDF format to ₹ Cr / L.
"""

# ── helpers ──────────────────────────────────────────────────────────────────
def _g(d, k, default=0.0):
    try:
        return float((d or {}).get(k) or 0.0)
    except (TypeError, ValueError):
        return default


def _pct(num, den):
    den = float(den or 0)
    return round(num / den * 100, 2) if den else None


def _bs_totals(bs):
    deposits = _g(bs, 'deposits_demand') + _g(bs, 'deposits_savings') + _g(bs, 'deposits_term')
    capital = _g(bs, 'equity_capital') + _g(bs, 'reserves_surplus')
    tangible_equity = capital - _g(bs, 'intangible_assets')
    liabilities_capital = capital + deposits + _g(bs, 'borrowings') + _g(bs, 'other_liabilities')
    assets = (_g(bs, 'cash_with_rbi') + _g(bs, 'balances_with_banks') + _g(bs, 'investments')
              + _g(bs, 'advances_net') + _g(bs, 'fixed_assets')
              + _g(bs, 'intangible_assets') + _g(bs, 'other_assets'))
    return deposits, capital, tangible_equity, liabilities_capital, assets


# ── balance sheet ─────────────────────────────────────────────────────────────
def balance_sheet_view(bs):
    """Structured RBI Schedule III balance sheet (sections of {label, key, value})."""
    deposits, capital, _tangible, total_lc, total_assets = _bs_totals(bs)
    liabilities = [
        {'label': 'Capital (Equity Share Capital)', 'value': _g(bs, 'equity_capital')},
        {'label': 'Reserves & Surplus', 'value': _g(bs, 'reserves_surplus')},
        {'label': 'Deposits', 'value': round(deposits, 2), 'group': True},
        {'label': 'Demand deposits', 'value': _g(bs, 'deposits_demand'), 'indent': True},
        {'label': 'Savings bank deposits', 'value': _g(bs, 'deposits_savings'), 'indent': True},
        {'label': 'Term deposits', 'value': _g(bs, 'deposits_term'), 'indent': True},
        {'label': 'Borrowings', 'value': _g(bs, 'borrowings')},
        {'label': 'Other Liabilities & Provisions', 'value': _g(bs, 'other_liabilities')},
    ]
    assets = [
        {'label': 'Cash & Balances with RBI', 'value': _g(bs, 'cash_with_rbi')},
        {'label': 'Balances with Banks / Money at Call', 'value': _g(bs, 'balances_with_banks')},
        {'label': 'Investments', 'value': _g(bs, 'investments')},
        {'label': 'Advances (net)', 'value': _g(bs, 'advances_net')},
        {'label': 'Fixed Assets', 'value': _g(bs, 'fixed_assets')},
        {'label': 'Intangible Assets', 'value': _g(bs, 'intangible_assets')},
        {'label': 'Other Assets', 'value': _g(bs, 'other_assets')},
    ]
    return {
        'period': (bs or {}).get('period'), 'as_on_date': (bs or {}).get('as_on_date'),
        'liabilities': liabilities, 'assets': assets,
        'total_liabilities_capital': round(total_lc, 2), 'total_assets': round(total_assets, 2),
        'total_deposits': round(deposits, 2), 'total_capital': round(capital, 2),
        'tangible_equity': round(_tangible, 2),
        'contingent_liabilities': _g(bs, 'contingent_liabilities'),
        'bills_for_collection': _g(bs, 'bills_for_collection'),
    }


# ── profit & loss ──────────────────────────────────────────────────────────────
def profit_loss_view(pl):
    """Structured income statement."""
    return {
        'period': (pl or {}).get('period'),
        'from_date': (pl or {}).get('from_date'), 'to_date': (pl or {}).get('to_date'),
        'income': [
            {'label': 'Interest on Advances', 'value': _g(pl, 'interest_on_advances'), 'indent': True},
            {'label': 'Interest on Investments', 'value': _g(pl, 'interest_on_investments'), 'indent': True},
            {'label': 'Interest Earned', 'value': _g(pl, 'interest_earned'), 'group': True},
            {'label': 'Other Income (fees, treasury)', 'value': _g(pl, 'other_income')},
            {'label': 'Total Income', 'value': _g(pl, 'total_income'), 'group': True},
        ],
        'expenses': [
            {'label': 'Interest on Deposits', 'value': _g(pl, 'interest_on_deposits'), 'indent': True},
            {'label': 'Interest on Borrowings', 'value': _g(pl, 'interest_on_borrowings'), 'indent': True},
            {'label': 'Interest Expended', 'value': _g(pl, 'interest_expended'), 'group': True},
            {'label': 'Employee Cost', 'value': _g(pl, 'employee_cost'), 'indent': True},
            {'label': 'Other Operating Expenses', 'value': _g(pl, 'other_opex'), 'indent': True},
            {'label': 'Operating Expenses', 'value': _g(pl, 'operating_expenses'), 'group': True},
        ],
        'summary': [
            {'label': 'Net Interest Income (NII)', 'value': _g(pl, 'net_interest_income')},
            {'label': 'Operating Profit', 'value': _g(pl, 'operating_profit')},
            {'label': 'Provisions & Contingencies', 'value': _g(pl, 'provisions_contingencies')},
            {'label': 'Profit Before Tax', 'value': _g(pl, 'profit_before_tax')},
            {'label': 'Tax Expense', 'value': _g(pl, 'tax_expense')},
            {'label': 'Profit After Tax (PAT)', 'value': _g(pl, 'profit_after_tax'), 'strong': True},
        ],
    }


# ── key ratios ─────────────────────────────────────────────────────────────────
def key_ratios(bs, pl, cap, liq, stats):
    """stats: {gnpa_amount, gross_advances, num_loans, num_npa}."""
    deposits, capital, tangible_equity, _, total_assets = _bs_totals(bs)
    earning_assets = _g(bs, 'advances_net') + _g(bs, 'investments')
    pat = _g(pl, 'profit_after_tax')
    nii = _g(pl, 'net_interest_income')
    opex = _g(pl, 'operating_expenses')
    other_income = _g(pl, 'other_income')
    total_income = _g(pl, 'total_income')
    interest_on_advances = _g(pl, 'interest_on_advances')
    interest_expended = _g(pl, 'interest_expended')
    advances_net = _g(bs, 'advances_net')
    borrowings = _g(bs, 'borrowings')
    casa = _g(bs, 'deposits_demand') + _g(bs, 'deposits_savings')
    gnpa = float(stats.get('gnpa_amount') or 0)
    provisions = _g(cap, 'total_provisions')

    return [
        # ── Capital
        {'label': 'Capital Adequacy Ratio (CRAR)', 'value': _g(cap, 'car'), 'unit': '%',
         'min': 11.5, 'status': (cap or {}).get('car_status'), 'section': 'Capital'},
        {'label': 'CET1 Ratio', 'value': _g(cap, 'cet1_ratio'), 'unit': '%',
         'min': 8.0, 'status': (cap or {}).get('cet1_status'), 'section': 'Capital'},
        # ── Profitability
        {'label': 'Net Interest Margin (NIM)', 'value': _pct(nii, earning_assets), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Return on Assets (ROA)', 'value': _pct(pat, total_assets), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Return on Equity (ROE)', 'value': _pct(pat, capital), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Return on Tangible Equity (ROTE)', 'value': _pct(pat, tangible_equity), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Net Profit Margin', 'value': _pct(pat, total_income), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Yield on Advances', 'value': _pct(interest_on_advances, advances_net), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Cost of Funds', 'value': _pct(interest_expended, deposits + borrowings), 'unit': '%', 'section': 'Profitability'},
        {'label': 'Cost-to-Income Ratio', 'value': _pct(opex, nii + other_income), 'unit': '%', 'section': 'Profitability'},
        # ── Asset Quality
        {'label': 'Gross NPA Ratio', 'value': _pct(gnpa, stats.get('gross_advances')), 'unit': '%', 'section': 'Asset Quality'},
        {'label': 'Provision Coverage Ratio (PCR)', 'value': _pct(provisions, gnpa), 'unit': '%', 'section': 'Asset Quality'},
        # ── Funding & Liquidity
        {'label': 'Credit-Deposit Ratio', 'value': _pct(advances_net, deposits), 'unit': '%', 'section': 'Funding'},
        {'label': 'CASA Ratio', 'value': _pct(casa, deposits), 'unit': '%', 'section': 'Funding'},
        {'label': 'Liquidity Coverage Ratio (LCR)', 'value': _g(liq, 'lcr'), 'unit': '%',
         'min': 100.0, 'status': (liq or {}).get('lcr_status'), 'section': 'Funding'},
        {'label': 'Net Stable Funding Ratio (NSFR)', 'value': _g(liq, 'nsfr'), 'unit': '%',
         'min': 100.0, 'status': (liq or {}).get('nsfr_status'), 'section': 'Funding'},
    ]


# ── performance KPI cards ──────────────────────────────────────────────────────
def performance_kpis(bs, pl, cap, liq, stats):
    """Headline performance metrics for KPI card display (mix of ₹ and %)."""
    deposits, capital, tangible_equity, _, total_assets = _bs_totals(bs)
    earning_assets = _g(bs, 'advances_net') + _g(bs, 'investments')
    advances_net = _g(bs, 'advances_net')
    borrowings = _g(bs, 'borrowings')
    pat = _g(pl, 'profit_after_tax')
    nii = _g(pl, 'net_interest_income')
    total_income = _g(pl, 'total_income')
    interest_on_advances = _g(pl, 'interest_on_advances')
    interest_expended = _g(pl, 'interest_expended')
    opex = _g(pl, 'operating_expenses')
    other_income = _g(pl, 'other_income')
    op_profit = _g(pl, 'operating_profit')

    return [
        {'label': 'Profit After Tax (PAT)', 'value': pat, 'unit': 'INR',
         'sub': f"Net Profit Margin {(_pct(pat, total_income) or 0):.2f}%"},
        {'label': 'Net Interest Income (NII)', 'value': nii, 'unit': 'INR',
         'sub': f"NIM {(_pct(nii, earning_assets) or 0):.2f}% on earning assets"},
        {'label': 'Net Interest Margin (NIM)', 'value': _pct(nii, earning_assets), 'unit': '%',
         'sub': "Interest income on earning assets (advances + investments)"},
        {'label': 'Return on Tangible Equity (ROTE)', 'value': _pct(pat, tangible_equity), 'unit': '%',
         'sub': f"ROA {(_pct(pat, total_assets) or 0):.2f}% · ROE {(_pct(pat, capital) or 0):.2f}%"},
        {'label': 'Return on Assets (ROA)', 'value': _pct(pat, total_assets), 'unit': '%',
         'sub': f"Total assets ₹{total_assets/1e7:.0f} Cr"},
        {'label': 'Operating Profit', 'value': op_profit, 'unit': 'INR',
         'sub': f"Cost-to-Income {(_pct(opex, nii + other_income) or 0):.1f}%"},
        {'label': 'Yield on Advances', 'value': _pct(interest_on_advances, advances_net), 'unit': '%',
         'sub': f"Interest income on net advances"},
        {'label': 'Cost of Funds', 'value': _pct(interest_expended, deposits + borrowings), 'unit': '%',
         'sub': f"Interest paid on deposits & borrowings"},
    ]


# ── Pillar 3 disclosures ────────────────────────────────────────────────────────
def pillar3(cap, liq, bs, exposure_mix):
    """Basel III Pillar 3 quantitative disclosure tables."""
    _, capital, _tangible, _, total_assets = _bs_totals(bs)
    cet1 = _g(cap, 'tier1_capital')
    return {
        'capital_structure': [
            {'label': 'Common Equity Tier 1 (CET1) — equity + reserves', 'value': cet1},
            {'label': 'Additional Tier 1', 'value': 0.0},
            {'label': 'Tier 1 Capital', 'value': _g(cap, 'tier1_capital')},
            {'label': 'Tier 2 Capital (eligible provisions/sub-debt)', 'value': _g(cap, 'tier2_capital')},
            {'label': 'Total Regulatory Capital', 'value': _g(cap, 'total_capital'), 'strong': True},
        ],
        'rwa': [
            {'label': 'Credit Risk RWA', 'value': _g(cap, 'credit_rwa')},
            {'label': 'Operational Risk RWA (Basel BIA)', 'value': _g(cap, 'operational_rwa')},
            {'label': 'Market Risk RWA', 'value': _g(cap, 'market_rwa')},
            {'label': 'Total RWA', 'value': _g(cap, 'total_rwa'), 'strong': True},
        ],
        'capital_ratios': [
            {'label': 'CET1 Ratio', 'value': _g(cap, 'cet1_ratio'), 'min': 8.0, 'status': (cap or {}).get('cet1_status')},
            {'label': 'Tier 1 Ratio', 'value': _g(cap, 'tier1_ratio'), 'min': 9.5, 'status': (cap or {}).get('tier1_status')},
            {'label': 'Total Capital Ratio (CRAR)', 'value': _g(cap, 'car'), 'min': 11.5, 'status': (cap or {}).get('car_status')},
            {'label': 'Leverage Ratio', 'value': _g(cap, 'leverage_ratio'), 'min': 3.5, 'status': (cap or {}).get('leverage_status')},
        ],
        'liquidity': [
            {'label': 'High-Quality Liquid Assets (HQLA)', 'value': _g(liq, 'hqla')},
            {'label': 'Net 30-day Stressed Outflows', 'value': _g(liq, 'net_outflows_30d')},
            {'label': 'LCR', 'value': _g(liq, 'lcr'), 'min': 100.0, 'status': (liq or {}).get('lcr_status'), 'ratio': True},
            {'label': 'Available Stable Funding (ASF)', 'value': _g(liq, 'asf')},
            {'label': 'Required Stable Funding (RSF)', 'value': _g(liq, 'rsf')},
            {'label': 'NSFR', 'value': _g(liq, 'nsfr'), 'min': 100.0, 'status': (liq or {}).get('nsfr_status'), 'ratio': True},
        ],
        'credit_risk_mix': exposure_mix or [],
        'rwa_density': _g(cap, 'rwa_density'),
        'total_assets': round(total_assets, 2),
    }


# ── per-bank bundle ──────────────────────────────────────────────────────────────
def bank_bundle(bank, bs, pl, cap, liq, stats, exposure_mix):
    return {
        'scope': 'bank', 'bank_id': bank.get('bank_id'), 'bank': bank,
        'period': (bs or {}).get('period'),
        'as_on_date': (bs or {}).get('as_on_date'),
        'balance_sheet': balance_sheet_view(bs),
        'profit_loss': profit_loss_view(pl),
        'key_ratios': key_ratios(bs, pl, cap, liq, stats),
        'performance_kpis': performance_kpis(bs, pl, cap, liq, stats),
        'pillar3': pillar3(cap, liq, bs, exposure_mix),
        'raw': {'capital': cap, 'liquidity': liq, 'stats': stats},
    }


# ── consolidated (all-banks aggregate) ───────────────────────────────────────────
_BS_SUM = ['equity_capital', 'reserves_surplus', 'deposits_demand', 'deposits_savings',
           'deposits_term', 'borrowings', 'other_liabilities', 'cash_with_rbi',
           'balances_with_banks', 'investments', 'advances_net', 'fixed_assets',
           'other_assets', 'contingent_liabilities', 'bills_for_collection']
_PL_SUM = ['interest_on_advances', 'interest_on_investments', 'interest_earned',
           'other_income', 'total_income', 'interest_on_deposits', 'interest_on_borrowings',
           'interest_expended', 'employee_cost', 'other_opex', 'operating_expenses',
           'net_interest_income', 'operating_profit', 'provisions_contingencies',
           'profit_before_tax', 'tax_expense', 'profit_after_tax']
_CAP_SUM = ['credit_rwa', 'operational_rwa', 'market_rwa', 'total_rwa', 'tier1_capital',
            'tier2_capital', 'total_capital', 'total_assets', 'loan_book', 'deposits',
            'total_provisions']
_LIQ_SUM = ['retail_deposits', 'wholesale_funding', 'total_funding', 'ndtl', 'hqla',
            'net_outflows_30d', 'asf', 'rsf']


def consolidate(bundles_raw, period, as_on_date,
                scope_id='CONSOLIDATED', scope_name='Consolidated — All Banks',
                scope='consolidated', scope_meta=None):
    """Aggregate per-bank stored rows into a consolidated set, recomputing ratios.

    bundles_raw: list of {bank, bs, pl, cap, liq, stats, exposure_mix}.
    The same aggregation is reused for the whole group, a region or a country —
    pass scope_id / scope_name / scope to label the resulting bundle.
    """
    def _sum(rows, keys):
        out = {}
        for k in keys:
            out[k] = round(sum(_g(r, k) for r in rows), 2)
        return out

    bs_rows = [b['bs'] for b in bundles_raw]
    pl_rows = [b['pl'] for b in bundles_raw]
    cap_rows = [b['cap'] for b in bundles_raw]
    liq_rows = [b['liq'] for b in bundles_raw]

    bs = _sum(bs_rows, _BS_SUM); bs['period'] = period; bs['as_on_date'] = as_on_date
    pl = _sum(pl_rows, _PL_SUM); pl['period'] = period
    cap = _sum(cap_rows, _CAP_SUM)
    liq = _sum(liq_rows, _LIQ_SUM)

    # recompute consolidated ratios from aggregates
    rwa = cap['total_rwa'] or 1.0
    ta = cap['total_assets'] or 1.0
    cap['car'] = round(cap['total_capital'] / rwa * 100, 2)
    cap['tier1_ratio'] = round(cap['tier1_capital'] / rwa * 100, 2)
    cap['cet1_ratio'] = cap['tier1_ratio']
    cap['leverage_ratio'] = round(cap['tier1_capital'] / ta * 100, 2)
    cap['rwa_density'] = round(rwa / ta * 100, 1)
    cap['car_status'] = _status(cap['car'], 11.5)
    cap['cet1_status'] = _status(cap['cet1_ratio'], 8.0)
    cap['tier1_status'] = _status(cap['tier1_ratio'], 9.5)
    cap['leverage_status'] = _status(cap['leverage_ratio'], 3.5)
    cap['num_loans'] = sum(int((b['stats'] or {}).get('num_loans') or 0) for b in bundles_raw)
    cap['num_npa'] = sum(int((b['stats'] or {}).get('num_npa') or 0) for b in bundles_raw)

    outflow = liq['net_outflows_30d'] or 1.0
    rsf = liq['rsf'] or 1.0
    liq['lcr'] = round(liq['hqla'] / outflow * 100, 2)
    liq['nsfr'] = round(liq['asf'] / rsf * 100, 2)
    liq['crr_ratio'] = round(bs['cash_with_rbi'] / (liq['ndtl'] or 1.0) * 100, 2)
    liq['slr_ratio'] = round(bs['investments'] / (liq['ndtl'] or 1.0) * 100, 2)
    liq['lcr_status'] = _status(liq['lcr'], 100.0, 10)
    liq['nsfr_status'] = _status(liq['nsfr'], 100.0, 10)

    stats = {
        'gnpa_amount': round(sum(float((b['stats'] or {}).get('gnpa_amount') or 0) for b in bundles_raw), 2),
        'gross_advances': round(sum(float((b['stats'] or {}).get('gross_advances') or 0) for b in bundles_raw), 2),
        'num_loans': cap['num_loans'], 'num_npa': cap['num_npa'],
    }

    # aggregate exposure mix by (loan_type, classification)
    agg = {}
    for b in bundles_raw:
        for m in (b.get('exposure_mix') or []):
            key = (m.get('loan_type'), m.get('classification'))
            a = agg.setdefault(key, {'loan_type': m.get('loan_type'),
                                     'classification': m.get('classification'),
                                     'n': 0, 'ead': 0.0, 'rwa': 0.0, 'provision': 0.0})
            a['n'] += int(m.get('n') or 0)
            a['ead'] += float(m.get('ead') or 0)
            a['rwa'] += float(m.get('rwa') or 0)
            a['provision'] += float(m.get('provision') or 0)
    exposure_mix = list(agg.values())

    bank = {'bank_id': scope_id, 'bank_name': scope_name,
            'bank_code': '—', 'headquarters_city': 'Group', 'headquarters_state': '',
            'num_banks': len(bundles_raw),
            'members': [ (b.get('bank') or {}).get('bank_id') for b in bundles_raw ]}
    if scope_meta:
        bank.update(scope_meta)
    return {
        'scope': scope, 'scope_id': scope_id, 'bank_id': scope_id, 'bank': bank, 'period': period,
        'as_on_date': as_on_date,
        'balance_sheet': balance_sheet_view(bs),
        'profit_loss': profit_loss_view(pl),
        'key_ratios': key_ratios(bs, pl, cap, liq, stats),
        'performance_kpis': performance_kpis(bs, pl, cap, liq, stats),
        'pillar3': pillar3(cap, liq, bs, exposure_mix),
        'raw': {'capital': cap, 'liquidity': liq, 'stats': stats},
    }


def _status(actual, minimum, watch_buffer=1.0):
    if actual is None:
        return 'Monitored'
    if actual < minimum:
        return 'Breach'
    if actual < minimum + watch_buffer:
        return 'Watch'
    return 'Compliant'
