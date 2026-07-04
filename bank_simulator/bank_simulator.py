"""
Bank Balance Sheet Simulator + ALM Learning Lab
Run:  streamlit run bank_simulator.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

st.set_page_config(page_title="Bank Simulator", page_icon="🏦",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.kpi-card { background:#1e2130; border-radius:10px; padding:14px 10px;
            text-align:center; margin:3px; }
.kpi-label { font-size:10px; color:#9aa5b4; text-transform:uppercase; letter-spacing:1px; }
.kpi-value { font-size:22px; font-weight:700; margin:4px 0; }
.kpi-sub   { font-size:11px; color:#9aa5b4; }
.sec { font-size:11px; font-weight:600; color:#9aa5b4; text-transform:uppercase;
       letter-spacing:1.5px; margin:18px 0 6px;
       border-bottom:1px solid #2d3347; padding-bottom:5px; }
.concept-box { background:#1e2130; border-left:3px solid #4da6ff; border-radius:6px;
               padding:14px 18px; margin:10px 0; font-size:13px; line-height:1.7; }
.formula-box { background:#111827; border:1px solid #2d3347; border-radius:6px;
               padding:12px 16px; margin:8px 0; font-family:monospace; font-size:13px;
               color:#00c48c; }
.warn-box { background:#2a1f0a; border-left:3px solid #ffb800; border-radius:6px;
            padding:12px 16px; margin:8px 0; font-size:13px; }
</style>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# EXPOSURE CLASS DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────
EXPOSURE_CLASSES = [
    ("Sovereign / Govt Securities",     0.00,  200,  6.5),
    ("Banks & Financial Institutions",  0.20,  150,  7.5),
    ("Residential Mortgage (LTV≤80%)",  0.35,  300,  8.5),
    ("Retail Loans",                    0.75,  500, 11.0),
    ("SME – Retail",                    0.75,  300, 11.5),
    ("SME – Corporate",                 0.85,  400, 10.5),
    ("Corporate – Rated (A/BBB)",       0.50,  600,  9.5),
    ("Corporate – Unrated",             1.00,  800, 10.0),
    ("Commercial Real Estate",          1.00,  200, 10.5),
    ("NPA – Well Provisioned (≥50%)",   1.00,  100,  0.0),
    ("NPA – Under Provisioned (<50%)",  1.50,   50,  0.0),
]
EC_NAMES   = [e[0] for e in EXPOSURE_CLASSES]
EC_RW      = [e[1] for e in EXPOSURE_CLASSES]
EC_DEFAULT = [e[2] for e in EXPOSURE_CLASSES]
EC_YIELD   = [e[3] for e in EXPOSURE_CLASSES]

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏦 Bank Simulator")
    st.caption("Set ₹ amounts → see ratios as output.")

    st.markdown('<div class="sec">🏛️ Equity & Capital (₹ Cr)</div>', unsafe_allow_html=True)
    equity_input = st.number_input("Equity & Reserves (CET1 base)", 50, 20000, 500, 50,
                                   help="Paid-up capital + retained earnings.")
    tier2_instr  = st.number_input("Tier 2 Instruments", 0, 5000, 150, 50,
                                   help="Subordinated debt, revaluation reserves etc.")

    st.markdown('<div class="sec">💳 Deposit & Borrowing Liabilities (₹ Cr)</div>', unsafe_allow_html=True)
    savings_dep   = st.number_input("Savings Deposits (CASA)",    100, 20000, 1200, 100)
    current_dep   = st.number_input("Current Deposits (CASA)",     50, 10000,  600,  50)
    term_dep_st   = st.number_input("Term Deposits < 1 yr",       100, 20000, 1500, 100)
    term_dep_lt   = st.number_input("Term Deposits > 1 yr",       100, 20000, 1800, 100)
    borrowings_st = st.number_input("Short-term Borrowings",        0, 10000,  400,  50)
    borrowings_lt = st.number_input("Long-term Borrowings",         0, 10000,  600,  50)

    st.markdown('<div class="sec">📈 Non-Loan Assets (₹ Cr)</div>', unsafe_allow_html=True)
    st.caption("Any unallocated funding shows as residual cash.")
    cash_rbi    = st.number_input("Cash & Balances with RBI",     0, 20000,  800, 100)
    investments = st.number_input("Investments (G-Secs / Bonds)", 0, 30000, 2000, 100)
    fixed_other = st.number_input("Fixed Assets & Other Assets",  0,  5000,  400,  50)

    st.markdown('<div class="sec">📋 Loan Portfolio by Exposure Class (₹ Cr)</div>', unsafe_allow_html=True)
    loan_amounts = []
    for i, (name, rw, default, _) in enumerate(EXPOSURE_CLASSES):
        val = st.number_input(f"{name}  [{int(rw*100)}% RW]", 0, 20000, default, 50, key=f"ec_{i}")
        loan_amounts.append(val)

    st.markdown('<div class="sec">📉 Rates & Income</div>', unsafe_allow_html=True)
    use_class_yields = st.toggle("Per-class loan yields", value=False)
    if use_class_yields:
        class_yields = []
        for i, (name, _, _, hint) in enumerate(EXPOSURE_CLASSES):
            class_yields.append(st.slider(f"{name[:28]}…", 0.0, 18.0, float(hint), 0.25, key=f"y_{i}"))
    else:
        _y = st.slider("Blended Loan Yield (%)", 5.0, 16.0, 10.0, 0.25)
        class_yields = [_y] * len(EXPOSURE_CLASSES)

    invest_yield   = st.slider("Investment Yield (%)",        3.0,  9.0, 6.5, 0.25)
    cost_savings   = st.slider("Cost of Savings Dep (%)",     2.0,  6.0, 3.5, 0.25)
    cost_current   = st.slider("Cost of Current Dep (%)",     0.5,  3.0, 1.0, 0.25)
    cost_term_st   = st.slider("Cost of Term Dep <1yr (%)",   4.0,  9.0, 6.0, 0.25)
    cost_term_lt   = st.slider("Cost of Term Dep >1yr (%)",   5.0, 10.0, 6.8, 0.25)
    cost_borrow_st = st.slider("Cost of ST Borrowings (%)",   5.0, 11.0, 7.5, 0.25)
    cost_borrow_lt = st.slider("Cost of LT Borrowings (%)",   6.0, 12.0, 8.0, 0.25)
    other_income_cr= st.number_input("Other Income (₹ Cr)",   0, 2000, 200, 25)
    opex_cr        = st.number_input("Operating Expenses (₹ Cr)", 0, 5000, 600, 25)
    prov_coverage  = st.slider("Provision Coverage on NPA (%)", 30.0, 100.0, 65.0, 5.0)
    tax_rate       = st.slider("Tax Rate (%)", 15.0, 35.0, 25.17, 0.5)

# ─────────────────────────────────────────────────────────────────────────────
# CORE CALCULATIONS (shared across all tabs)
# ─────────────────────────────────────────────────────────────────────────────
total_loans       = sum(loan_amounts)
total_deposits    = savings_dep + current_dep + term_dep_st + term_dep_lt
total_borrowings  = borrowings_st + borrowings_lt
total_liabilities = total_deposits + total_borrowings + tier2_instr
equity            = equity_input
total_funding     = equity + total_liabilities
assets_allocated  = cash_rbi + investments + fixed_other + total_loans
unallocated       = total_funding - assets_allocated
total_assets      = total_funding
effective_cash    = cash_rbi + max(0, unallocated)

tier1_capital = equity * 0.92
total_capital = tier1_capital + tier2_instr

rwa_per_class = [loan_amounts[i] * EC_RW[i] for i in range(len(EXPOSURE_CLASSES))]
credit_rwa    = sum(rwa_per_class)
invest_rwa    = investments * 0.20
other_rwa     = fixed_other * 1.00

interest_income  = sum(loan_amounts[i] * class_yields[i] / 100 for i in range(len(EXPOSURE_CLASSES)))
interest_income += investments * invest_yield / 100
interest_expense = (savings_dep   * cost_savings  / 100 + current_dep   * cost_current  / 100
                  + term_dep_st   * cost_term_st  / 100 + term_dep_lt   * cost_term_lt  / 100
                  + borrowings_st * cost_borrow_st / 100 + borrowings_lt * cost_borrow_lt / 100)
nii          = interest_income - interest_expense
total_income = nii + other_income_cr
op_rwa       = max(0, total_income) * 12.5 * 0.15
total_rwa    = credit_rwa + invest_rwa + other_rwa + op_rwa

car  = total_capital / total_rwa * 100 if total_rwa > 0 else 0
cet1 = tier1_capital / total_rwa * 100 if total_rwa > 0 else 0

npa_well  = loan_amounts[9]; npa_under = loan_amounts[10]; total_npa = npa_well + npa_under
provisions = (npa_well * (1 - prov_coverage/100) * 0.45
            + npa_under * (1 - min(prov_coverage,50)/100) * 0.60)
operating_profit = total_income - opex_cr
pbt  = operating_profit - provisions
tax  = max(0, pbt * tax_rate / 100)
pat  = pbt - tax

nim      = nii / (total_loans + investments) * 100 if (total_loans + investments) > 0 else 0
roe      = pat / equity * 100 if equity > 0 else 0
roa      = pat / total_assets * 100 if total_assets > 0 else 0
cti      = opex_cr / total_income * 100 if total_income > 0 else 0
cof      = interest_expense / (total_deposits + total_borrowings) * 100 if (total_deposits + total_borrowings) > 0 else 0
gnpa_pct = total_npa / total_loans * 100 if total_loans > 0 else 0
net_pm   = pat / total_income * 100 if total_income > 0 else 0

hqla           = effective_cash + investments * 0.85
ndtl           = total_deposits + total_borrowings
net_outflow_30d= (savings_dep + current_dep)*0.10 + term_dep_st*0.15 + borrowings_st*0.25
lcr            = hqla / net_outflow_30d * 100 if net_outflow_30d > 0 else 999
asf = (equity + tier2_instr + (savings_dep+current_dep)*0.90
     + term_dep_lt*0.95 + term_dep_st*0.50 + borrowings_lt*0.50)
rsf = total_loans*0.85 + investments*0.50 + fixed_other*1.0
nsfr    = asf / rsf * 100 if rsf > 0 else 999
crr_pct = effective_cash / ndtl * 100 if ndtl > 0 else 0
slr_pct = investments / ndtl * 100 if ndtl > 0 else 0

RBI = dict(car=11.5, cet1=8.0, lcr=100.0, nsfr=100.0, crr=4.5, slr=18.0)

def st_color(val, thr, hb=True):
    ok  = val >= thr if hb else val <= thr
    gap = abs(val - thr) / thr if thr else 0
    if ok: return "#00c48c" if gap > 0.10 else "#ffb800"
    return "#ff4d4d"

def kcard(label, display_val, sub="", color="#4da6ff"):
    return f"""<div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{display_val}</div>
        <div class="kpi-sub">{sub}</div></div>"""

def gauge(label, value, lo, hi, thr, hb=True, unit="%"):
    color = st_color(value, thr, hb)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number={"suffix": unit, "font": {"size": 18, "color": "#fff"}},
        gauge={"axis": {"range": [lo, hi], "tickfont": {"color":"#9aa5b4","size":9}},
               "bar": {"color": color, "thickness": 0.3},
               "bgcolor": "#1e2130", "bordercolor": "#2d3347",
               "threshold": {"line": {"color":"#ffb800","width":2}, "thickness":0.75, "value":thr},
               "steps": [{"range":[lo,thr],"color":"#2d3347"},{"range":[thr,hi],"color":"#243040"}]},
        title={"text": label, "font": {"color":"#9aa5b4","size":11}},
        domain={"x":[0,1],"y":[0,1]},
    ))
    fig.update_layout(paper_bgcolor="#0e1117", font_color="#fff",
                      height=175, margin=dict(l=8,r=8,t=35,b=8))
    return fig

def concept(title, body):
    st.markdown(f'<div class="concept-box"><strong>{title}</strong><br>{body}</div>',
                unsafe_allow_html=True)

def formula(text):
    st.markdown(f'<div class="formula-box">{text}</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏦 Balance Sheet Simulator",
    "📊 Repricing Gap & Interest Rate Risk",
    "⏱️ Duration & Economic Value of Equity",
    "💧 Liquidity Management",
    "📚 ALM Concepts Glossary",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — EXISTING BALANCE SHEET SIMULATOR
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.title("🏦 Bank Balance Sheet Simulator")
    st.caption("Set asset/liability **amounts** on the left → ratios and metrics update instantly.")

    over_alloc  = unallocated < -1
    alloc_color = "#ff4d4d" if over_alloc else ("#ffb800" if unallocated < 50 else "#00c48c")
    h1,h2,h3,h4 = st.columns(4)
    h1.markdown(kcard("Total Funding = Assets", f"₹{total_funding:,.0f}", "Equity + Liabilities","#4da6ff"), unsafe_allow_html=True)
    h2.markdown(kcard("Equity & Reserves", f"₹{equity:,.0f}", f"{equity/total_funding*100:.1f}% of funding","#00c48c"), unsafe_allow_html=True)
    h3.markdown(kcard("Total Liabilities", f"₹{total_liabilities:,.0f}", f"Dep ₹{total_deposits:,.0f} + Borr ₹{total_borrowings:,.0f} + Tier2 ₹{tier2_instr:,.0f}","#4da6ff"), unsafe_allow_html=True)
    h4.markdown(kcard("Unallocated (Residual Cash)", f"{'−' if unallocated<0 else '+'}₹{abs(unallocated):,.0f}", "Over-allocated" if over_alloc else "Parked as cash at RBI", alloc_color), unsafe_allow_html=True)
    if over_alloc:
        st.error(f"⚠️ Asset allocation exceeds total funding by ₹{abs(unallocated):,.0f} Cr.")
    st.divider()

    st.markdown("### 📖 Balance Sheet Statement")
    bs1, bs2 = st.columns(2)
    with bs1:
        st.markdown("**ASSETS**")
        asset_rows = [
            {"Line Item": "Cash & Balances with RBI", "₹ Cr": cash_rbi + max(0, unallocated)},
            {"Line Item": "Investments (G-Secs / Bonds)", "₹ Cr": investments},
            {"Line Item": "Loans & Advances", "₹ Cr": total_loans},
            {"Line Item": "Fixed Assets & Other Assets", "₹ Cr": fixed_other},
        ]
        st.dataframe(pd.DataFrame(asset_rows).assign(**{"₹ Cr": lambda d: d["₹ Cr"].map(lambda v: f"{v:,.0f}")}),
                     use_container_width=True, hide_index=True)
        st.markdown(f"**TOTAL ASSETS &nbsp;&nbsp; ₹{total_assets:,.0f} Cr**")
    with bs2:
        st.markdown("**LIABILITIES & EQUITY**")
        liab_rows = [
            {"Line Item": "Savings Deposits (CASA)", "₹ Cr": savings_dep},
            {"Line Item": "Current Deposits (CASA)", "₹ Cr": current_dep},
            {"Line Item": "Term Deposits < 1 yr", "₹ Cr": term_dep_st},
            {"Line Item": "Term Deposits > 1 yr", "₹ Cr": term_dep_lt},
            {"Line Item": "Short-term Borrowings", "₹ Cr": borrowings_st},
            {"Line Item": "Long-term Borrowings", "₹ Cr": borrowings_lt},
            {"Line Item": "Tier 2 Instruments", "₹ Cr": tier2_instr},
            {"Line Item": "Equity & Reserves (CET1)", "₹ Cr": equity},
        ]
        st.dataframe(pd.DataFrame(liab_rows).assign(**{"₹ Cr": lambda d: d["₹ Cr"].map(lambda v: f"{v:,.0f}")}),
                     use_container_width=True, hide_index=True)
        st.markdown(f"**TOTAL LIABILITIES + EQUITY &nbsp;&nbsp; ₹{total_liabilities + equity:,.0f} Cr**")
    if abs(total_assets - (total_liabilities + equity)) < 1:
        st.success(f"✅ Balances: Assets ₹{total_assets:,.0f} Cr = Liabilities + Equity ₹{total_liabilities + equity:,.0f} Cr")
    else:
        st.error(f"⚠️ Does not balance: Assets ₹{total_assets:,.0f} Cr ≠ Liabilities + Equity ₹{total_liabilities + equity:,.0f} Cr")
    st.divider()

    st.markdown("### 🔵 Regulatory Compliance")
    g1,g2,g3,g4,g5,g6 = st.columns(6)
    g1.plotly_chart(gauge("CAR",  car,  0,25,  RBI["car"]),  use_container_width=True)
    g2.plotly_chart(gauge("CET1", cet1, 0,20,  RBI["cet1"]), use_container_width=True)
    g3.plotly_chart(gauge("LCR",  lcr,  0,300, RBI["lcr"]),  use_container_width=True)
    g4.plotly_chart(gauge("NSFR", nsfr, 0,200, RBI["nsfr"]), use_container_width=True)
    g5.plotly_chart(gauge("CRR",  crr_pct,0,20,RBI["crr"]),  use_container_width=True)
    g6.plotly_chart(gauge("SLR",  slr_pct,0,40,RBI["slr"]),  use_container_width=True)

    st.markdown("### 📊 Performance Metrics")
    c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
    c1.markdown(kcard("PAT (₹ Cr)",    f"₹{pat:,.0f}",    f"PBT ₹{pbt:,.0f}",          st_color(pat,0)),         unsafe_allow_html=True)
    c2.markdown(kcard("NIM",           f"{nim:.2f}%",      f"NII ₹{nii:,.0f} Cr",        st_color(nim,2.5)),       unsafe_allow_html=True)
    c3.markdown(kcard("ROE",           f"{roe:.2f}%",      f"Equity ₹{equity:,.0f} Cr",  st_color(roe,12.0)),      unsafe_allow_html=True)
    c4.markdown(kcard("ROA",           f"{roa:.2f}%",      f"Assets ₹{total_assets:,.0f} Cr", st_color(roa,0.8)), unsafe_allow_html=True)
    c5.markdown(kcard("Cost-to-Income",f"{cti:.1f}%",      f"Opex ₹{opex_cr:,.0f} Cr",  st_color(cti,50,hb=False)),unsafe_allow_html=True)
    c6.markdown(kcard("Cost of Funds", f"{cof:.2f}%",      f"Int Exp ₹{interest_expense:,.0f} Cr","#4da6ff"),      unsafe_allow_html=True)
    c7.markdown(kcard("GNPA",          f"{gnpa_pct:.2f}%", f"NPA ₹{total_npa:,.0f} Cr",  st_color(gnpa_pct,5.0,hb=False)),unsafe_allow_html=True)
    c8.markdown(kcard("Net Profit Mgn",f"{net_pm:.2f}%",   f"Income ₹{total_income:,.0f} Cr", st_color(net_pm,10.0)),unsafe_allow_html=True)
    st.divider()

    st.markdown("### ⚖️ Risk-Weighted Assets by Exposure Class")
    rwa_l, rwa_r = st.columns([1.6,1])
    with rwa_l:
        rows = []
        for i,(name,rw,_,_) in enumerate(EXPOSURE_CLASSES):
            if loan_amounts[i]>0:
                rows.append({"Exposure Class":name,"Risk Weight":f"{int(rw*100)}%",
                             "Exposure (₹ Cr)":loan_amounts[i],"RWA (₹ Cr)":round(rwa_per_class[i]),
                             "% of Credit RWA":f"{rwa_per_class[i]/credit_rwa*100:.1f}%" if credit_rwa>0 else "—"})
        rows += [{"Exposure Class":"Investments","Risk Weight":"20%","Exposure (₹ Cr)":investments,"RWA (₹ Cr)":round(invest_rwa),"% of Credit RWA":"—"},
                 {"Exposure Class":"Other Assets","Risk Weight":"100%","Exposure (₹ Cr)":fixed_other,"RWA (₹ Cr)":round(other_rwa),"% of Credit RWA":"—"},
                 {"Exposure Class":"Operational RWA","Risk Weight":"—","Exposure (₹ Cr)":"—","RWA (₹ Cr)":round(op_rwa),"% of Credit RWA":"—"},
                 {"Exposure Class":"TOTAL RWA","Risk Weight":"—","Exposure (₹ Cr)":total_assets,"RWA (₹ Cr)":round(total_rwa),"% of Credit RWA":"100%"}]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with rwa_r:
        cn = [EC_NAMES[i][:22] for i in range(len(EXPOSURE_CLASSES)) if rwa_per_class[i]>0]
        cv = [rwa_per_class[i] for i in range(len(EXPOSURE_CLASSES)) if rwa_per_class[i]>0]
        cn += ["Investments","Other","Operational"]; cv += [invest_rwa,other_rwa,op_rwa]
        fig = go.Figure(go.Pie(labels=cn,values=cv,hole=0.45,textinfo="percent",textfont=dict(size=10),
                               marker=dict(colors=px.colors.qualitative.Plotly),
                               hovertemplate="<b>%{label}</b><br>RWA: ₹%{value:,.0f} Cr<extra></extra>"))
        fig.add_annotation(text=f"Total RWA<br>₹{total_rwa:,.0f}Cr",x=0.5,y=0.5,showarrow=False,font=dict(size=11,color="#fff"))
        fig.update_layout(paper_bgcolor="#0e1117",font_color="#fff",height=340,margin=dict(l=0,r=0,t=10,b=10),showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    cap1,cap2,cap3,cap4 = st.columns(4)
    cap1.markdown(kcard("Total Capital",f"₹{total_capital:,.0f}",f"T1 ₹{tier1_capital:,.0f} + T2 ₹{tier2_instr:,.0f}","#4da6ff"),unsafe_allow_html=True)
    cap2.markdown(kcard("Credit RWA",f"₹{credit_rwa:,.0f}",f"{credit_rwa/total_rwa*100:.0f}% of total" if total_rwa else "—","#4da6ff"),unsafe_allow_html=True)
    cap3.markdown(kcard("Capital Shortfall",f"₹{max(0,total_rwa*RBI['car']/100-total_capital):,.0f}" if car<RBI['car'] else "None",f"at {RBI['car']}% CAR","#ff4d4d" if car<RBI['car'] else "#00c48c"),unsafe_allow_html=True)
    cap4.markdown(kcard("Avg Risk Density",f"{credit_rwa/total_loans*100:.1f}%" if total_loans else "—","Credit RWA / Loans","#4da6ff"),unsafe_allow_html=True)
    st.divider()

    st.markdown("### 📋 Balance Sheet & P&L")
    bs_l, pl_r = st.columns(2)
    with bs_l:
        albl = ["Cash & RBI","Investments",f"Loans ₹{total_loans:,.0f}Cr","Fixed & Other"]
        aval = [effective_cash,investments,total_loans,fixed_other]
        llbl = ["Savings Dep","Current Dep","Term <1yr","Term >1yr","ST Borr","LT Borr","Tier 2","Equity"]
        lval = [savings_dep,current_dep,term_dep_st,term_dep_lt,borrowings_st,borrowings_lt,tier2_instr,equity]
        fig2 = go.Figure()
        ca = ["#ffb800","#00c48c","#4da6ff","#9aa5b4"]
        cl = ["#ff6b6b","#ff9f43","#ffd32a","#e55039","#a29bfe","#6c5ce7","#fd79a8","#00b894"]
        for i,(l,v) in enumerate(zip(albl,aval)):
            fig2.add_trace(go.Bar(name=l,x=["Assets"],y=[max(0,v)],marker_color=ca[i],
                                  text=f"₹{v:,.0f}",textposition="inside",insidetextanchor="middle",textfont=dict(size=9)))
        for i,(l,v) in enumerate(zip(llbl,lval)):
            fig2.add_trace(go.Bar(name=l,x=["Liabilities+Equity"],y=[max(0,v)],marker_color=cl[i],
                                  text=f"₹{v:,.0f}",textposition="inside",insidetextanchor="middle",textfont=dict(size=9)))
        fig2.update_layout(barmode="stack",paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",font_color="#fff",
                           height=380,margin=dict(l=10,r=10,t=10,b=10),
                           legend=dict(orientation="h",y=-0.30,font=dict(size=9)),
                           yaxis=dict(gridcolor="#2d3347"))
        st.plotly_chart(fig2, use_container_width=True)
    with pl_r:
        fig3 = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute","relative","relative","relative","relative","relative","total"],
            x=["Int Income","Int Expense","Other Income","Opex","Provisions","Tax","PAT"],
            y=[interest_income,-interest_expense,other_income_cr,-opex_cr,-provisions,-tax,0],
            connector={"line":{"color":"#2d3347"}},
            increasing={"marker":{"color":"#00c48c"}},decreasing={"marker":{"color":"#ff4d4d"}},
            totals={"marker":{"color":"#4da6ff"}},
            text=[f"₹{abs(v):,.0f}" for v in [interest_income,interest_expense,other_income_cr,opex_cr,provisions,tax,pat]],
            textposition="outside",textfont=dict(size=10)))
        fig3.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",font_color="#fff",
                           height=380,margin=dict(l=10,r=10,t=10,b=60),
                           yaxis=dict(gridcolor="#2d3347"),showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)
    st.divider()

    st.markdown("### 🔬 What-If: Shift ₹ Cr Between Exposure Classes")
    wf1,wf2,wf3 = st.columns(3)
    fc = wf1.selectbox("Move FROM", EC_NAMES, index=7)
    tc = wf2.selectbox("Move TO",   EC_NAMES, index=3)
    sa = wf3.number_input("Amount (₹ Cr)", 0, 5000, 200, 50)
    fi,ti    = EC_NAMES.index(fc), EC_NAMES.index(tc)
    drwa     = sa*(EC_RW[ti]-EC_RW[fi]); nrwa=total_rwa+drwa; ncar=total_capital/nrwa*100 if nrwa>0 else 0
    w1,w2,w3,w4 = st.columns(4)
    w1.markdown(kcard("RWA Change",f"{'↓' if drwa<0 else '↑'}₹{abs(drwa):,.0f}","","#00c48c" if drwa<=0 else "#ff4d4d"),unsafe_allow_html=True)
    w2.markdown(kcard("New Total RWA",f"₹{nrwa:,.0f}",f"was ₹{total_rwa:,.0f}","#4da6ff"),unsafe_allow_html=True)
    w3.markdown(kcard("New CAR",f"{ncar:.2f}%",f"was {car:.2f}%",st_color(ncar,RBI["car"])),unsafe_allow_html=True)
    w4.markdown(kcard("CAR Δ",f"{ncar-car:+.2f}%",f"RW: {int(EC_RW[fi]*100)}%→{int(EC_RW[ti]*100)}%","#00c48c" if ncar>=car else "#ff4d4d"),unsafe_allow_html=True)
    st.divider()

    st.markdown("### 💡 Insights")
    tips = []
    if equity<=0: tips.append("🔴 **Insolvent** — liabilities exceed assets.")
    if car<RBI["car"]: tips.append(f"🔴 **CAR {car:.2f}%** breaches 11.5%. Need ₹{total_rwa*RBI['car']/100-total_capital:,.0f} Cr more capital.")
    if cet1<RBI["cet1"]: tips.append(f"🔴 **CET1 {cet1:.2f}%** below 8%.")
    if lcr<RBI["lcr"]: tips.append(f"🔴 **LCR {lcr:.1f}%** below 100%. Increase HQLA.")
    if nsfr<RBI["nsfr"]: tips.append(f"🔴 **NSFR {nsfr:.1f}%** below 100%. Lengthen deposit maturity.")
    if crr_pct<RBI["crr"]: tips.append(f"🔴 **CRR {crr_pct:.2f}%** below 4.5%.")
    if slr_pct<RBI["slr"]: tips.append(f"🔴 **SLR {slr_pct:.2f}%** below 18%.")
    if nim<2.5: tips.append(f"🟡 **NIM {nim:.2f}%** thin — improve CASA or reprice loans.")
    if roe<12 and equity>0: tips.append(f"🟡 **ROE {roe:.2f}%** below 12% hurdle.")
    if gnpa_pct>5: tips.append(f"🟠 **GNPA {gnpa_pct:.1f}%** elevated.")
    if not tips: tips.append("✅ All metrics healthy.")
    for t in tips: st.markdown(t)
    st.caption(f"Balance: Assets ₹{total_assets:,.0f} = Liab ₹{total_liabilities:,.0f} + Equity ₹{equity:,.0f} | RWA ₹{total_rwa:,.0f} Cr")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — REPRICING GAP & INTEREST RATE RISK
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.title("📊 Repricing Gap Analysis & Interest Rate Risk")

    concept("What is the Repricing Gap?",
            "A <b>repricing gap</b> measures the difference between assets and liabilities that will "
            "be re-priced (i.e., face a new interest rate) within a given time bucket. "
            "If Rate-Sensitive Assets (RSA) > Rate-Sensitive Liabilities (RSL), the bank has a <b>positive gap</b> "
            "— it benefits when rates rise (NII goes up). A <b>negative gap</b> means rates rising hurts NII. "
            "ALM committees use this to decide whether to hedge, reprice, or restructure the book.")

    st.markdown("#### Step 1 — Build your Repricing Gap Table")
    st.caption("Distribute your assets and liabilities into time buckets by when they next reprice. "
               "Pre-filled with values derived from your balance sheet above — edit as needed.")

    # Time buckets
    BUCKETS = ["Overnight","2–7 days","8–28 days","1–3 months","3–6 months","6–12 months","1–3 years","3–5 years","5+ years"]

    # Default RSA split: cash=overnight, ST investments=3-6m, LT investments=1-3yr,
    # mortgage & corporate LT = 3-5y, retail = 1-3y, etc.
    def default_rsa():
        return [effective_cash,
                0,
                0,
                investments * 0.15 + loan_amounts[0]*0.1,
                investments * 0.25 + loan_amounts[1]*0.3 + loan_amounts[3]*0.2,
                investments * 0.30 + loan_amounts[4]*0.3 + loan_amounts[6]*0.2 + loan_amounts[7]*0.15,
                investments * 0.20 + loan_amounts[2]*0.3 + loan_amounts[3]*0.4 + loan_amounts[5]*0.4 + loan_amounts[6]*0.4,
                investments * 0.10 + loan_amounts[2]*0.5 + loan_amounts[7]*0.5 + loan_amounts[8]*0.5,
                loan_amounts[2]*0.2 + loan_amounts[7]*0.35 + loan_amounts[8]*0.5]

    def default_rsl():
        return [borrowings_st * 0.3,
                borrowings_st * 0.3,
                borrowings_st * 0.4 + savings_dep * 0.3 + current_dep * 0.5,
                term_dep_st * 0.25 + savings_dep * 0.3 + current_dep * 0.3,
                term_dep_st * 0.40 + savings_dep * 0.2 + current_dep * 0.2,
                term_dep_st * 0.35 + savings_dep * 0.2,
                term_dep_lt * 0.45 + borrowings_lt * 0.3,
                term_dep_lt * 0.40 + borrowings_lt * 0.4,
                term_dep_lt * 0.15 + borrowings_lt * 0.3]

    drsa = [round(x) for x in default_rsa()]
    drsl = [round(x) for x in default_rsl()]

    # Editable table via columns
    gap_cols = st.columns([2,1,1,1,1])
    gap_cols[0].markdown("**Time Bucket**")
    gap_cols[1].markdown("**RSA (₹ Cr)**")
    gap_cols[2].markdown("**RSL (₹ Cr)**")
    gap_cols[3].markdown("**Gap**")
    gap_cols[4].markdown("**Cumul. Gap**")

    rsa_vals, rsl_vals = [], []
    for i, bkt in enumerate(BUCKETS):
        r1,r2,r3,r4,r5 = st.columns([2,1,1,1,1])
        r1.markdown(f"<small>{bkt}</small>", unsafe_allow_html=True)
        rsa = r2.number_input("", min_value=0, max_value=50000, value=drsa[i], step=50, key=f"rsa_{i}", label_visibility="collapsed")
        rsl = r3.number_input("", min_value=0, max_value=50000, value=drsl[i], step=50, key=f"rsl_{i}", label_visibility="collapsed")
        rsa_vals.append(rsa); rsl_vals.append(rsl)
        gap  = rsa - rsl
        cgap = sum(rsa_vals) - sum(rsl_vals)
        gap_color  = "#00c48c" if gap  >= 0 else "#ff4d4d"
        cgap_color = "#00c48c" if cgap >= 0 else "#ff4d4d"
        r4.markdown(f"<span style='color:{gap_color};font-weight:600'>{'+'if gap>=0 else ''}₹{gap:,.0f}</span>", unsafe_allow_html=True)
        r5.markdown(f"<span style='color:{cgap_color};font-weight:600'>{'+'if cgap>=0 else ''}₹{cgap:,.0f}</span>", unsafe_allow_html=True)

    gaps  = [rsa_vals[i] - rsl_vals[i] for i in range(len(BUCKETS))]
    cgaps = [sum(gaps[:i+1]) for i in range(len(BUCKETS))]

    st.divider()

    # ── Visualisation ─────────────────────────────────────────────────────────
    st.markdown("#### Step 2 — Visualise the Gap Profile")
    fig_gap = go.Figure()
    fig_gap.add_trace(go.Bar(name="RSA", x=BUCKETS, y=rsa_vals, marker_color="#4da6ff",
                             text=[f"₹{v:,.0f}" for v in rsa_vals], textposition="outside", textfont=dict(size=9)))
    fig_gap.add_trace(go.Bar(name="RSL", x=BUCKETS, y=rsl_vals, marker_color="#ff6b6b",
                             text=[f"₹{v:,.0f}" for v in rsl_vals], textposition="outside", textfont=dict(size=9)))
    fig_gap.add_trace(go.Scatter(name="Cumulative Gap", x=BUCKETS, y=cgaps,
                                 line=dict(color="#ffb800", width=2, dash="dot"),
                                 mode="lines+markers", yaxis="y2"))
    fig_gap.update_layout(
        barmode="group", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="#fff",
        height=380, margin=dict(l=10,r=10,t=20,b=10),
        yaxis=dict(gridcolor="#2d3347", title="₹ Cr"),
        yaxis2=dict(overlaying="y", side="right", title="Cumulative Gap (₹ Cr)",
                    gridcolor="#2d3347", showgrid=False),
        legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig_gap, use_container_width=True)
    st.divider()

    # ── NII at Risk ───────────────────────────────────────────────────────────
    st.markdown("#### Step 3 — NII at Risk from Rate Shocks")
    concept("How NII at Risk is calculated",
            "The 1-year cumulative gap is the net position that will reprice within 12 months. "
            "A +100 bps rate shock on a positive cumulative gap <i>increases</i> NII. "
            "<b>NII at Risk = 1-Year Cumulative Gap × Rate Shock</b>. "
            "RBI's Supervisory Review (SREP) expects banks to model ±200 bps scenarios.")
    formula("NII at Risk = Σ(RSA – RSL)_within_12m  ×  Δrate/100")

    one_yr_cum_gap = sum(gaps[:6])   # first 6 buckets = within 1 year
    st.markdown(f"**1-Year Cumulative Gap: ₹{one_yr_cum_gap:,.0f} Cr** "
                f"({'Positive – benefits from rate ↑' if one_yr_cum_gap>=0 else 'Negative – hurt by rate ↑'})")

    shocks = [-200,-100,-50,+50,+100,+200]
    nii_risks = [one_yr_cum_gap * s / 100 for s in shocks]
    nii_pct   = [nr / nii * 100 if nii != 0 else 0 for nr in nii_risks]

    df_nii = pd.DataFrame({
        "Rate Shock (bps)": [f"{s:+d}" for s in shocks],
        "ΔNII (₹ Cr)":      [round(x) for x in nii_risks],
        "ΔNII as % of Base NII": [f"{x:.1f}%" for x in nii_pct],
        "New NII (₹ Cr)":   [round(nii + x) for x in nii_risks],
    })
    st.dataframe(df_nii, use_container_width=True, hide_index=True)

    fig_nii = go.Figure(go.Bar(
        x=[f"{s:+d}bps" for s in shocks], y=nii_risks,
        marker_color=["#ff4d4d" if v<0 else "#00c48c" for v in nii_risks],
        text=[f"₹{v:,.0f}" for v in nii_risks], textposition="outside",
    ))
    fig_nii.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",font_color="#fff",
                          height=280,margin=dict(l=10,r=10,t=20,b=10),
                          yaxis=dict(gridcolor="#2d3347",title="ΔNII (₹ Cr)"),
                          title="NII Impact by Rate Shock Scenario")
    st.plotly_chart(fig_nii, use_container_width=True)

    # ── GAP ratio ─────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Step 4 — GAP Ratio Analysis")
    concept("GAP Ratio",
            "GAP Ratio = RSA / RSL within a bucket. "
            "Ratio > 1 means asset-sensitive (bank profits when rates rise). "
            "Ratio < 1 means liability-sensitive (bank profits when rates fall). "
            "Most retail banks are liability-sensitive due to large fixed-rate loan books funded by floating deposits.")
    formula("GAP Ratio = RSA / RSL  |  > 1 = Asset-Sensitive  |  < 1 = Liability-Sensitive")

    ratios = [rsa_vals[i]/rsl_vals[i] if rsl_vals[i]>0 else float('inf') for i in range(len(BUCKETS))]
    fig_ratio = go.Figure(go.Bar(
        x=BUCKETS, y=[min(r,5) for r in ratios],
        marker_color=["#00c48c" if r>=1 else "#ff6b6b" for r in ratios],
        text=[f"{r:.2f}x" if r!=float('inf') else "∞" for r in ratios],
        textposition="outside",
    ))
    fig_ratio.add_hline(y=1.0, line_color="#ffb800", line_dash="dash",
                        annotation_text="GAP Ratio = 1.0 (Neutral)", annotation_position="right")
    fig_ratio.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",font_color="#fff",
                            height=280,margin=dict(l=10,r=10,t=20,b=10),
                            yaxis=dict(gridcolor="#2d3347",title="GAP Ratio (RSA/RSL)"),
                            title="GAP Ratio per Time Bucket")
    st.plotly_chart(fig_ratio, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — DURATION & EVE
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.title("⏱️ Duration Gap & Economic Value of Equity (EVE)")

    concept("Why Duration Matters",
            "Duration measures how sensitive a financial instrument's value is to interest rate changes. "
            "A bond with duration 5 years loses ~5% of its value for every 1% rise in rates. "
            "For a bank, what matters is the <b>Duration Gap</b> between assets and liabilities — "
            "it tells you how much your <b>equity value</b> (not just NII) changes when rates move. "
            "This is the EVE (Economic Value of Equity) perspective — used in Basel III IRRBB framework.")
    formula("Modified Duration Gap = D_A  –  (L/A) × D_L\n"
            "ΔEVE  =  – Modified Duration Gap  ×  ΔR / (1+R)  ×  Total Assets")

    st.markdown("#### Asset Duration Inputs")
    st.caption("Set the modified duration (in years) for each asset class. Higher duration = more rate-sensitive.")
    da_col1, da_col2 = st.columns(2)
    with da_col1:
        dur_cash    = st.slider("Cash & RBI (duration)",        0.0, 0.1, 0.0, 0.01)
        dur_invest  = st.slider("Investments / G-Secs (years)", 0.5, 10.0, 4.5, 0.25)
        dur_fixed   = st.slider("Fixed Assets (years)",         0.0, 1.0, 0.0, 0.1)
    with da_col2:
        dur_mortgage= st.slider("Mortgage Loans (years)",       2.0, 15.0, 7.0, 0.5)
        dur_retail  = st.slider("Retail Loans (years)",         0.5,  5.0, 2.5, 0.25)
        dur_corp    = st.slider("Corporate Loans (years)",      1.0,  8.0, 3.5, 0.25)
        dur_sov     = st.slider("Sovereign / Govt (years)",     1.0, 12.0, 5.0, 0.25)

    # Weighted avg asset duration
    loan_dur_map = [dur_sov, dur_corp*0.6, dur_mortgage, dur_retail, dur_retail, dur_corp,
                    dur_corp, dur_corp, dur_corp, 0.0, 0.0]
    loan_weighted_dur = sum(loan_amounts[i]*loan_dur_map[i] for i in range(len(EXPOSURE_CLASSES))) / total_loans if total_loans>0 else 0
    asset_weights = [effective_cash, investments, total_loans, fixed_other]
    asset_durs    = [dur_cash, dur_invest, loan_weighted_dur, dur_fixed]
    D_A = sum(asset_weights[i]*asset_durs[i] for i in range(4)) / total_assets if total_assets>0 else 0

    st.markdown("#### Liability Duration Inputs")
    lb_col1, lb_col2 = st.columns(2)
    with lb_col1:
        dur_savings  = st.slider("Savings Deposits (years)",    0.1, 2.0, 0.5, 0.1)
        dur_current  = st.slider("Current Deposits (years)",    0.0, 0.5, 0.1, 0.05)
        dur_term_st  = st.slider("Term Dep <1yr (years)",       0.2, 1.0, 0.5, 0.1)
    with lb_col2:
        dur_term_lt  = st.slider("Term Dep >1yr (years)",       1.0, 5.0, 2.5, 0.25)
        dur_borrow_st= st.slider("ST Borrowings (years)",       0.1, 1.0, 0.3, 0.1)
        dur_borrow_lt= st.slider("LT Borrowings (years)",       1.0, 7.0, 3.0, 0.25)

    liab_weights = [savings_dep, current_dep, term_dep_st, term_dep_lt, borrowings_st, borrowings_lt, tier2_instr]
    liab_durs    = [dur_savings, dur_current, dur_term_st, dur_term_lt, dur_borrow_st, dur_borrow_lt, 3.0]
    D_L = sum(liab_weights[i]*liab_durs[i] for i in range(len(liab_weights))) / total_liabilities if total_liabilities>0 else 0

    leverage_ratio = total_liabilities / total_assets if total_assets>0 else 0
    dur_gap = D_A - leverage_ratio * D_L
    base_rate = st.slider("Base Market Interest Rate (%)", 3.0, 12.0, 6.5, 0.25)

    st.divider()
    st.markdown("#### Duration Gap Results")
    d1,d2,d3,d4 = st.columns(4)
    dgap_color = "#00c48c" if dur_gap>0 else ("#ff4d4d" if dur_gap<-0.5 else "#ffb800")
    d1.markdown(kcard("Asset Duration (D_A)", f"{D_A:.2f} yrs", f"Wtd avg across ₹{total_assets:,.0f}Cr", "#4da6ff"), unsafe_allow_html=True)
    d2.markdown(kcard("Liability Duration (D_L)", f"{D_L:.2f} yrs", f"Wtd avg across ₹{total_liabilities:,.0f}Cr", "#4da6ff"), unsafe_allow_html=True)
    d3.markdown(kcard("Leverage Ratio (L/A)", f"{leverage_ratio:.3f}", f"Liab/Assets", "#9aa5b4"), unsafe_allow_html=True)
    d4.markdown(kcard("Duration Gap", f"{dur_gap:.3f} yrs", "D_A – (L/A)×D_L", dgap_color), unsafe_allow_html=True)

    if dur_gap > 0:
        st.success(f"✅ **Positive Duration Gap ({dur_gap:.2f} yrs)** — asset-sensitive. "
                   f"Rising rates increase EVE; falling rates reduce it.")
    elif dur_gap < -0.5:
        st.error(f"🔴 **Negative Duration Gap ({dur_gap:.2f} yrs)** — liability-sensitive. "
                 f"Rising rates reduce EVE. Most retail banks sit here.")
    else:
        st.info(f"⚠️ **Near-zero Duration Gap ({dur_gap:.2f} yrs)** — approximately immunised. "
                f"EVE is relatively insensitive to rate moves.")

    st.divider()
    st.markdown("#### EVE Sensitivity — Rate Shock Scenarios")
    concept("Economic Value of Equity (EVE)",
            "EVE = PV(Assets) – PV(Liabilities). Unlike NII at Risk (which is a 12-month earnings view), "
            "EVE measures the <b>total balance-sheet impact</b> across all future cash flows. "
            "Basel III's IRRBB framework requires banks to report EVE impact for six standard rate shocks. "
            "A >15% decline in EVE triggers supervisory attention.")
    formula("ΔEVE = – Duration Gap × [ΔR / (1 + R)] × Total Assets")

    rate_shocks = [-300,-200,-100,-50,+50,+100,+200,+300]
    eve_changes = []
    for shock in rate_shocks:
        dr = shock / 10000  # bps to decimal
        dEVE = -dur_gap * (dr / (1 + base_rate/100)) * total_assets
        eve_changes.append(dEVE)

    eve_pct = [e/equity*100 if equity>0 else 0 for e in eve_changes]

    df_eve = pd.DataFrame({
        "Rate Shock (bps)":    [f"{s:+d}" for s in rate_shocks],
        "ΔEVE (₹ Cr)":         [round(e) for e in eve_changes],
        "ΔEVE (% of Equity)":  [f"{p:.2f}%" for p in eve_pct],
        "Supervisory Concern": ["⚠️ Yes" if abs(p)>15 else "✅ No" for p in eve_pct],
    })
    st.dataframe(df_eve, use_container_width=True, hide_index=True)

    fig_eve = go.Figure()
    fig_eve.add_trace(go.Bar(
        x=[f"{s:+d}bps" for s in rate_shocks], y=eve_changes,
        marker_color=["#ff4d4d" if v<0 else "#00c48c" for v in eve_changes],
        text=[f"₹{v:,.0f}" for v in eve_changes], textposition="outside",
    ))
    fig_eve.add_hline(y= equity*0.15, line_color="#ffb800",line_dash="dash",annotation_text="+15% equity threshold")
    fig_eve.add_hline(y=-equity*0.15, line_color="#ffb800",line_dash="dash",annotation_text="–15% equity threshold")
    fig_eve.update_layout(paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",font_color="#fff",
                          height=320,margin=dict(l=10,r=10,t=20,b=10),
                          yaxis=dict(gridcolor="#2d3347",title="ΔEVE (₹ Cr)"),
                          title="Economic Value of Equity — Rate Shock Impact")
    st.plotly_chart(fig_eve, use_container_width=True)

    st.divider()
    st.markdown("#### Duration Immunisation")
    concept("Immunisation Strategy",
            "A bank is <b>immunised</b> against interest rate risk when Duration Gap = 0. "
            "To close a negative duration gap (D_A < (L/A)×D_L), the ALM committee can: "
            "<br>① Lengthen asset duration — buy longer-tenor bonds, issue fixed-rate loans "
            "<br>② Shorten liability duration — move to longer-tenor deposits, issue LT bonds "
            "<br>③ Use Interest Rate Swaps — receive fixed / pay floating to synthetically lengthen assets "
            "<br>④ Sell short-duration assets, redeploy into longer-duration ones")
    target_DA = leverage_ratio * D_L
    st.markdown(f"**To immunise:** target Asset Duration = **{target_DA:.2f} years** "
                f"(currently {D_A:.2f} years). "
                f"Gap to close: **{target_DA - D_A:+.2f} years**.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — LIQUIDITY MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    st.title("💧 Liquidity Management — Maturity Ladder & Stress Testing")

    concept("Structural Liquidity Statement (SLS)",
            "The SLS maps all cash <b>inflows</b> (loan repayments, investment maturities, coupon receipts) "
            "and <b>outflows</b> (deposit maturities, borrowing repayments, new loan disbursals) into time buckets. "
            "The <b>net liquidity gap</b> per bucket shows whether the bank faces a cash surplus or deficit. "
            "RBI mandates that Indian banks maintain a positive cumulative gap up to 1 year under normal conditions.")

    LBUCKETS = ["Next Day","2–7 days","8–14 days","15–28 days","1–3 months","3–6 months","6–12 months","1–3 years","3–5 years","5+ years"]

    # Default inflows/outflows
    def default_inflows():
        return [effective_cash * 0.05,
                effective_cash * 0.10 + investments * 0.02,
                investments * 0.03 + total_loans * 0.005,
                investments * 0.05 + total_loans * 0.01,
                investments * 0.10 + total_loans * 0.04,
                investments * 0.15 + total_loans * 0.06,
                investments * 0.20 + total_loans * 0.08,
                investments * 0.25 + total_loans * 0.15,
                investments * 0.10 + total_loans * 0.20,
                effective_cash*0.85 + investments*0.10 + total_loans*0.455]

    def default_outflows():
        return [borrowings_st * 0.05 + (savings_dep+current_dep)*0.02,
                borrowings_st * 0.15 + (savings_dep+current_dep)*0.05,
                borrowings_st * 0.15 + (savings_dep+current_dep)*0.05,
                borrowings_st * 0.35 + (savings_dep+current_dep)*0.08 + term_dep_st*0.10,
                term_dep_st * 0.30 + (savings_dep+current_dep)*0.10,
                term_dep_st * 0.40 + (savings_dep+current_dep)*0.10,
                term_dep_st * 0.20 + savings_dep*0.15 + borrowings_lt*0.10,
                term_dep_lt * 0.45 + borrowings_lt * 0.35,
                term_dep_lt * 0.35 + borrowings_lt * 0.40,
                term_dep_lt * 0.20 + borrowings_lt * 0.15 + savings_dep*0.15]

    dinf = [round(x) for x in default_inflows()]
    dout = [round(x) for x in default_outflows()]

    stress_factor = st.slider("Stress Multiplier on Outflows (1.0 = normal, 1.5 = moderate stress, 2.0 = severe)",
                               1.0, 2.5, 1.0, 0.1)

    st.markdown("#### Structural Liquidity Statement (₹ Cr)")
    st.caption("Adjust inflows and outflows per time bucket. Stress multiplier scales all outflows.")

    hdr = st.columns([2,1,1,1,1])
    hdr[0].markdown("**Bucket**"); hdr[1].markdown("**Inflows**")
    hdr[2].markdown("**Outflows**"); hdr[3].markdown("**Net Gap**"); hdr[4].markdown("**Cumul. Gap**")

    inf_vals, out_vals = [], []
    for i, bkt in enumerate(LBUCKETS):
        r1,r2,r3,r4,r5 = st.columns([2,1,1,1,1])
        r1.markdown(f"<small>{bkt}</small>", unsafe_allow_html=True)
        inf = r2.number_input("", 0, 50000, dinf[i], 50, key=f"inf_{i}", label_visibility="collapsed")
        out_raw = r3.number_input("", 0, 50000, dout[i], 50, key=f"out_{i}", label_visibility="collapsed")
        out = round(out_raw * stress_factor)
        inf_vals.append(inf); out_vals.append(out)
        net  = inf - out
        cgap = sum(inf_vals) - sum(out_vals)
        nc = "#00c48c" if net>=0 else "#ff4d4d"
        cc = "#00c48c" if cgap>=0 else "#ff4d4d"
        r4.markdown(f"<span style='color:{nc};font-weight:600'>{'+'if net>=0 else ''}₹{net:,.0f}</span>", unsafe_allow_html=True)
        r5.markdown(f"<span style='color:{cc};font-weight:600'>{'+'if cgap>=0 else ''}₹{cgap:,.0f}</span>", unsafe_allow_html=True)

    nets  = [inf_vals[i] - out_vals[i] for i in range(len(LBUCKETS))]
    cgaps_liq = [sum(nets[:i+1]) for i in range(len(LBUCKETS))]

    st.divider()
    fig_liq = go.Figure()
    fig_liq.add_trace(go.Bar(name="Inflows",  x=LBUCKETS, y=inf_vals, marker_color="#00c48c",
                             text=[f"₹{v:,.0f}" for v in inf_vals], textposition="outside", textfont=dict(size=8)))
    fig_liq.add_trace(go.Bar(name="Outflows", x=LBUCKETS, y=[-v for v in out_vals], marker_color="#ff4d4d",
                             text=[f"₹{v:,.0f}" for v in out_vals], textposition="outside", textfont=dict(size=8)))
    fig_liq.add_trace(go.Scatter(name="Cumulative Gap", x=LBUCKETS, y=cgaps_liq,
                                 line=dict(color="#ffb800",width=2,dash="dot"),
                                 mode="lines+markers", yaxis="y2"))
    fig_liq.add_hline(y=0, line_color="#9aa5b4", line_dash="solid")
    fig_liq.update_layout(barmode="overlay", paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",font_color="#fff",
                          height=380,margin=dict(l=10,r=10,t=20,b=10),
                          yaxis=dict(gridcolor="#2d3347",title="₹ Cr"),
                          yaxis2=dict(overlaying="y",side="right",title="Cumul. Gap (₹ Cr)",showgrid=False),
                          legend=dict(orientation="h",y=1.05))
    st.plotly_chart(fig_liq, use_container_width=True)
    st.divider()

    # Survival horizon
    st.markdown("#### Liquidity Survival Horizon")
    concept("Survival Horizon",
            "In a stress scenario (e.g., sudden deposit run), the bank can survive as long as its "
            "cumulative inflows exceed cumulative outflows. The <b>survival horizon</b> is the first bucket "
            "where the cumulative gap turns negative — that's when the bank would run out of liquidity "
            "without intervention. A horizon of ≥30 days satisfies LCR; ≥1 year is considered robust.")

    survival = None
    for i, cg in enumerate(cgaps_liq):
        if cg < 0:
            survival = LBUCKETS[i]
            break

    if survival:
        st.error(f"⚠️ **Liquidity shortfall appears at: {survival}** — cumulative gap turns negative. "
                 f"At stress factor {stress_factor:.1f}x, the bank would need external liquidity support "
                 f"before this bucket.")
    else:
        st.success(f"✅ **Cumulative gap remains positive across all {len(LBUCKETS)} buckets** "
                   f"at stress factor {stress_factor:.1f}x. Survival horizon exceeds 5+ years.")

    # LCR / NSFR reminders
    st.markdown("#### LCR & NSFR (from Balance Sheet)")
    l1,l2,l3,l4 = st.columns(4)
    l1.markdown(kcard("HQLA (₹ Cr)", f"₹{hqla:,.0f}", "Cash+RBI + 85% of Investments","#4da6ff"), unsafe_allow_html=True)
    l2.markdown(kcard("30-day Net Outflow", f"₹{net_outflow_30d:,.0f}", "Stress outflows","#4da6ff"), unsafe_allow_html=True)
    l3.markdown(kcard("LCR", f"{lcr:.1f}%", "Min 100% (RBI)", st_color(lcr,100)), unsafe_allow_html=True)
    l4.markdown(kcard("NSFR", f"{nsfr:.1f}%", "Min 100% (RBI)", st_color(nsfr,100)), unsafe_allow_html=True)
    st.divider()

    st.markdown("#### Funding Concentration Analysis")
    concept("Concentration Risk in Funding",
            "Over-reliance on a single funding source (e.g., wholesale borrowings, large depositors) "
            "creates a cliff-edge risk. If that source dries up (as in the 2008 crisis), the bank faces "
            "an immediate liquidity crisis. RBI expects banks to diversify funding and cap wholesale "
            "dependence at <20% of total liabilities for retail banks.")

    total_casa = savings_dep + current_dep
    casa_pct   = total_casa / total_liabilities * 100 if total_liabilities>0 else 0
    td_pct     = (term_dep_st+term_dep_lt) / total_liabilities * 100 if total_liabilities>0 else 0
    borr_pct   = total_borrowings / total_liabilities * 100 if total_liabilities>0 else 0
    tier2_pct  = tier2_instr / total_liabilities * 100 if total_liabilities>0 else 0

    fig_fund = go.Figure(go.Pie(
        labels=["CASA","Term Deposits","Borrowings","Tier 2"],
        values=[total_casa, term_dep_st+term_dep_lt, total_borrowings, tier2_instr],
        hole=0.4,
        marker=dict(colors=["#00c48c","#4da6ff","#ff6b6b","#ffb800"]),
        textinfo="percent+label", textfont=dict(size=12),
    ))
    fig_fund.update_layout(paper_bgcolor="#0e1117",font_color="#fff",
                           height=300,margin=dict(l=0,r=0,t=10,b=10),showlegend=False)

    fc1, fc2 = st.columns([1,2])
    with fc1:
        st.plotly_chart(fig_fund, use_container_width=True)
    with fc2:
        f1,f2 = st.columns(2)
        f1.markdown(kcard("CASA Ratio", f"{casa_pct:.1f}%", "Target: >40% (stable)", st_color(casa_pct,40)), unsafe_allow_html=True)
        f2.markdown(kcard("Term Deposit Ratio", f"{td_pct:.1f}%", "Stable but rate-sensitive","#4da6ff"), unsafe_allow_html=True)
        f1.markdown(kcard("Wholesale Borrowing", f"{borr_pct:.1f}%", "Watch: <20% ideal", st_color(borr_pct,20,hb=False)), unsafe_allow_html=True)
        f2.markdown(kcard("Tier 2 / Long-term", f"{tier2_pct:.1f}%", "Counts as stable funding","#4da6ff"), unsafe_allow_html=True)
        if borr_pct > 20:
            st.markdown(f'<div class="warn-box">⚠️ Wholesale borrowings are {borr_pct:.1f}% of liabilities — above the 20% prudential benchmark. '
                        f'This creates refinancing risk if market conditions tighten.</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — ALM CONCEPTS GLOSSARY
# ═════════════════════════════════════════════════════════════════════════════
with tab5:
    st.title("📚 ALM Concepts — Learning Reference")
    st.caption("A structured reference to Asset Liability Management concepts used in Indian banking (Basel III + RBI framework).")

    with st.expander("🏛️ What is ALM? — Overview", expanded=True):
        st.markdown("""
**Asset Liability Management (ALM)** is the practice of managing a bank's balance sheet to optimise
profitability while controlling the risks that arise from mismatches between assets and liabilities.

The three core risks ALM manages:
| Risk | Definition | Key Metric |
|---|---|---|
| **Interest Rate Risk** | Rate changes affect NII and EVE | NII at Risk, Duration Gap, EVE |
| **Liquidity Risk** | Inability to meet cash obligations | LCR, NSFR, Survival Horizon |
| **Funding Risk** | Inability to renew/replace funding | Funding Concentration, NSFR |

**Who runs ALM?** The ALCO (Asset Liability Committee) — typically chaired by the MD/CEO with CFO,
Treasury Head, CRO and key business heads. In India, RBI requires ALCO to meet at least monthly.
        """)

    with st.expander("📊 Interest Rate Risk — NII vs EVE Perspective"):
        st.markdown("""
There are two complementary lenses for interest rate risk:

**1. Earnings Perspective (NII at Risk)**
- Focuses on the next 12 months of interest income
- Managed via Repricing Gap Analysis
- Short-term, accounting-based view
- Formula: `ΔNII = Cumulative 1-yr Gap × Δrate`

**2. Economic Value Perspective (EVE)**
- Measures the present value impact on the entire balance sheet
- Managed via Duration Gap Analysis
- Long-term, market-value view
- Formula: `ΔEVE = –Duration Gap × [ΔR/(1+R)] × Total Assets`

**Why both matter?** A bank can be NII-positive but EVE-negative in the same rate scenario.
Basel III IRRBB (Interest Rate Risk in the Banking Book) mandates reporting both.

**RBI requirement:** Banks must disclose NII impact for ±100/200 bps scenarios and EVE impact
for all six Basel standard rate shocks (parallel, steepener, flattener, short shock up/down).
        """)

    with st.expander("⏱️ Duration — Key Concepts"):
        st.markdown("""
**Macaulay Duration** — weighted average time to receive cash flows (in years)

**Modified Duration** — percentage price change per 1% rate change
`Modified Duration = Macaulay Duration / (1 + y/m)` where y=yield, m=payments per year

**Key duration facts for banking:**
| Instrument | Typical Duration |
|---|---|
| Overnight deposits / call money | ~0.003 years |
| 91-day T-bill | ~0.24 years |
| 3-year G-Sec | ~2.7 years |
| 10-year G-Sec | ~7.5 years |
| Retail home loan (20yr, fixed) | ~8-11 years |
| Corporate floating-rate loan | ~0.25–1 year |
| CASA deposits (behavioural) | ~0.5–2 years |

**Duration Gap:**
`D_gap = D_A – (L/A) × D_L`

Most Indian retail banks have a **negative duration gap** because:
- Assets: large long-tenor fixed-rate home loans (high duration)
- Liabilities: CASA + short-term deposits repricing frequently (low duration)
- But: L/A ≈ 0.90 compresses the liability side significantly

**Convexity** — the second-order effect. For large rate moves (>200bps), duration alone understates
the impact. High convexity assets (e.g., mortgage-backed securities with prepayment) behave
non-linearly and require convexity adjustment.
        """)

    with st.expander("💧 Liquidity Risk — LCR, NSFR, SLS"):
        st.markdown("""
**Liquidity Coverage Ratio (LCR)**
Ensures the bank can survive a 30-day severe liquidity stress event.
```
LCR = HQLA / Net Cash Outflows (30-day stress)  ≥ 100%
```
- **HQLA** = High Quality Liquid Assets (cash, G-Secs, certain bonds)
- **Level 1 HQLA**: Cash, RBI balances, sovereign bonds (0% haircut)
- **Level 2A HQLA**: AAA-rated corporate bonds, covered bonds (15% haircut)
- **Level 2B HQLA**: Lower-rated assets (25–50% haircut, capped at 15% of HQLA)

**Net Stable Funding Ratio (NSFR)**
Ensures the bank's long-term assets are funded by stable long-term liabilities.
```
NSFR = Available Stable Funding (ASF) / Required Stable Funding (RSF)  ≥ 100%
```
- Horizon: 1 year (vs LCR's 30 days)
- ASF: equity, long-term deposits, stable retail deposits get high ASF factors
- RSF: illiquid assets (loans, mortgages) get high RSF factors

**Structural Liquidity Statement (SLS)**
RBI-mandated report mapping all inflows and outflows into time buckets from overnight to 5+ years.
Indian banks must maintain cumulative positive gap up to 1 year under normal conditions.
Structural mismatches >15% of outflows in any bucket require ALCO approval and remediation.

**CRR (Cash Reserve Ratio):** Banks must maintain 4.5% of NDTL as cash with RBI.
**SLR (Statutory Liquidity Ratio):** Banks must hold 18% of NDTL in approved securities (G-Secs).
Both are RBI's built-in liquidity buffers unique to the Indian framework.
        """)

    with st.expander("📐 Repricing Gap — Mechanics"):
        st.markdown("""
**Rate-Sensitive Assets (RSA):** Assets that reprice within a given period:
- Floating-rate loans linked to MCLR/repo rate → reprice at next reset date
- Treasury bills, commercial paper → reprice at maturity
- Fixed deposits made by the bank → reprice at maturity

**Rate-Sensitive Liabilities (RSL):** Liabilities that reprice within a given period:
- Savings deposits → reprice immediately when savings rate changes
- Fixed deposits taken from customers → reprice at maturity
- Repo borrowings → daily repricing

**Non-rate-sensitive:** Fixed-rate long-term loans, equity capital, demand deposits
(behavioural analysis needed — RBI allows banks to treat ~20–30% of CASA as "core"
and assign longer effective maturities)

**Gap Ratio interpretation:**
| GAP Ratio | Position | Rate Rise Effect | Rate Fall Effect |
|---|---|---|---|
| > 1.0 | Asset-sensitive | NII ↑ | NII ↓ |
| = 1.0 | Neutral | No change | No change |
| < 1.0 | Liability-sensitive | NII ↓ | NII ↑ |

**Hedging tools:**
- **Interest Rate Swaps (IRS):** Receive-fixed / pay-floating to lengthen asset duration synthetically
- **Forward Rate Agreements (FRA):** Lock in borrowing rates for future periods
- **Interest Rate Futures:** Exchange-traded contracts on G-Secs (NSE)
- **Caps/Floors:** Options on interest rates for one-sided protection
        """)

    with st.expander("🏦 ALCO — Governance & RBI Requirements"):
        st.markdown("""
**ALCO (Asset Liability Committee)** is the apex body for ALM governance.

**RBI Master Circular requirements (SCBs):**
- ALCO must meet at least monthly (large banks: fortnightly)
- Chairman: MD & CEO or ED
- Members: CFO, CRO, Treasury Head, Business Heads
- Must cover: NII projections, rate sensitivity, liquidity gaps, FX exposures, capital adequacy

**Reports ALCO reviews:**
1. Structural Liquidity Statement (bucket-wise maturity profile)
2. Interest Rate Sensitivity Statement (gap report)
3. Dynamic Liquidity Statement (short-term inflows/outflows)
4. Currency Risk Statement (for banks with forex book)
5. Equity Risk Statement

**Transfer Pricing (FTP):**
ALCO sets internal transfer prices — the rate at which the treasury "buys" deposits from
branches and "sells" funds to the lending book. FTP allocates the margin fairly between
deposit-gathering and lending businesses and ensures ALM decisions are embedded in business incentives.

**Stress Testing:**
RBI requires annual liquidity stress tests covering:
- Idiosyncratic stress (bank-specific event — e.g., credit rating downgrade)
- Market-wide stress (systemic event — e.g., 2008-style freeze)
- Combined stress
        """)

    with st.expander("📈 Key ALM Metrics — Quick Reference"):
        df_ref = pd.DataFrame([
            ["NII at Risk",          "ΔNII = 1yr Cum. Gap × Δrate/100",                    "< ±20% of NII",          "Earnings risk"],
            ["ΔEVE",                 "–Dur_Gap × ΔR/(1+R) × Assets",                       "< ±15% of Equity",       "Value risk"],
            ["Duration Gap",         "D_A – (L/A)×D_L",                                    "Within ±2 years",        "Rate sensitivity"],
            ["LCR",                  "HQLA / Net 30d Outflows",                             "≥ 100% (RBI)",           "Short-term liquidity"],
            ["NSFR",                 "ASF / RSF",                                           "≥ 100% (RBI)",           "Structural liquidity"],
            ["CRR",                  "Cash with RBI / NDTL",                                "≥ 4.5% (RBI)",           "Reserve requirement"],
            ["SLR",                  "Approved Securities / NDTL",                          "≥ 18% (RBI)",            "Reserve requirement"],
            ["Funding Conc. Ratio",  "Top-10 depositors / Total deposits",                  "< 20%",                  "Concentration risk"],
            ["Wholesale Funding %",  "Interbank + Market borrowings / Total liabilities",   "< 20% (retail banks)",   "Funding stability"],
            ["CASA Ratio",           "(Savings+Current) / Total Deposits",                  "> 40% (good)",           "Cost of funds"],
            ["NIM",                  "NII / Earning Assets",                                "> 2.5% (Indian banks)",  "Profitability"],
        ], columns=["Metric","Formula","Benchmark","Purpose"])
        st.dataframe(df_ref, use_container_width=True, hide_index=True)
