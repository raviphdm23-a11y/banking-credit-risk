"""
financial_report_pdf.py
────────────────────────
Generates a combined, annual-report-style **PDF** for a bank (or the consolidated
all-banks group): Balance Sheet + Profit & Loss + Key Ratios + Basel III Pillar 3
disclosures, with charts. matplotlib (PNG) → LaTeX → pdflatex.

Versioned per scope under data/financial_reports/<scope_id>/<version>/ — each
generation is a new version; the manifest keeps the history.

Reuses the LaTeX escaping / compile helpers from report_generator so the two PDF
pipelines stay consistent.
"""

import os
import json
from datetime import datetime, timezone

from backend.report_generator import _tex, _compile, _safe, _save

# On App Engine Standard AND Cloud Run, the deployed source directory is
# read-only at runtime, so this must land under /tmp instead - same convention
# as app.py's _BASE_DATA_DIR / _READONLY_FS.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get('GAE_APPLICATION') is not None or os.environ.get('K_SERVICE') is not None:
    REPORTS_ROOT = os.path.join('/tmp', 'data', 'financial_reports')
else:
    REPORTS_ROOT = os.path.join(_ROOT, "data", "financial_reports")

NAVY, RED, GREEN, AMBER, BLUE, PURPLE = (
    "#0D1B2A", "#E31837", "#10B981", "#F59E0B", "#3B82F6", "#8B5CF6")


def latex_available():
    from backend.report_generator import _pdflatex_path
    return _pdflatex_path() is not None


# ── public API ───────────────────────────────────────────────────────────────
def generate_report(bundle):
    """Generate a new combined PDF version for a financial-report `bundle`
    (output of financial_reports.bank_bundle or .consolidate)."""
    scope_id = bundle.get("bank_id", "UNKNOWN")
    now = datetime.now(timezone.utc)
    version = "report_" + now.strftime("%Y%m%d_%H%M%S")
    scope_dir = os.path.join(REPORTS_ROOT, _safe(scope_id))
    version_dir = os.path.join(scope_dir, version)
    charts_dir = os.path.join(version_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    charts = _build_charts(bundle, charts_dir)
    tex = _build_latex(bundle, charts, now)
    tex_path = os.path.join(version_dir, "report.tex")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(tex)
    pdf_ok, log_tail = _compile(tex_path, version_dir)

    meta = {
        "scope": bundle.get("scope"), "scope_id": scope_id,
        "bank_name": (bundle.get("bank") or {}).get("bank_name"),
        "period": bundle.get("period"), "as_on_date": bundle.get("as_on_date"),
        "version": version, "generated_at": now.isoformat(timespec="seconds"),
        "pdf_exists": pdf_ok,
        "pdf_rel": f"{_safe(scope_id)}/{version}/report.pdf" if pdf_ok else None,
    }
    if not pdf_ok:
        meta["error"] = "LaTeX compilation failed"
        meta["log_tail"] = log_tail
    _update_manifest(scope_dir, bundle, meta)
    return meta


def list_versions(scope_id):
    return _read_manifest(os.path.join(REPORTS_ROOT, _safe(scope_id))).get("versions", [])


def pdf_path(scope_id, version):
    p = os.path.join(REPORTS_ROOT, _safe(scope_id), _safe(version), "report.pdf")
    return p if os.path.exists(p) else None


# ── manifest ─────────────────────────────────────────────────────────────────
def _read_manifest(scope_dir):
    path = os.path.join(scope_dir, "manifest.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"versions": []}


def _update_manifest(scope_dir, bundle, meta):
    os.makedirs(scope_dir, exist_ok=True)
    manifest = _read_manifest(scope_dir)
    manifest["scope_id"] = meta["scope_id"]
    manifest["bank_name"] = meta["bank_name"]
    versions = manifest.get("versions", [])
    for v in versions:
        v["latest"] = False
    entry = dict(meta); entry["latest"] = True
    versions.insert(0, entry)
    manifest["versions"] = versions
    with open(os.path.join(scope_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, default=str)


# ── money formatting ──────────────────────────────────────────────────────────
def _money(v):
    """LaTeX-safe INR in crore / lakh for readability."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    a = abs(v)
    if a >= 1e7:
        return f"Rs.~{v / 1e7:,.2f} Cr"
    if a >= 1e5:
        return f"Rs.~{v / 1e5:,.2f} L"
    return "Rs.~" + format(int(round(v)), ",d")


def _money_plain(v):
    """₹ crore for matplotlib labels (matplotlib renders the rupee glyph)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    return f"₹{v / 1e7:,.2f} Cr"


# ── charts ────────────────────────────────────────────────────────────────────
def _build_charts(bundle, charts_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#CBD5E1",
                         "axes.linewidth": 0.8, "figure.dpi": 150})
    out = {}
    bs = bundle["balance_sheet"]
    pl = bundle["profit_loss"]
    p3 = bundle["pillar3"]

    # 1. Balance-sheet structure — assets vs capital & liabilities (stacked) -----
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.2))
    asset_items = [(i["label"], i["value"]) for i in bs["assets"] if i["value"] > 0]
    liab_items = [(i["label"], i["value"]) for i in bs["liabilities"]
                  if i.get("value", 0) > 0 and not i.get("indent")]
    for ax, items, title in ((axes[0], asset_items, "Assets"),
                             (axes[1], liab_items, "Capital & Liabilities")):
        labels = [_short(k) for k, _ in items]
        vals = [v for _, v in items]
        ax.pie(vals, labels=None, autopct=lambda p: f"{p:.0f}%", pctdistance=0.78,
               colors=[NAVY, BLUE, GREEN, RED, AMBER, PURPLE][:len(vals)],
               wedgeprops={"width": 0.42, "edgecolor": "white"})
        ax.set_title(title, fontsize=10, color=NAVY, fontweight="bold")
        ax.legend(labels, loc="center", fontsize=6.2, frameon=False,
                  bbox_to_anchor=(0.5, -0.12), ncol=2)
    fig.tight_layout()
    out["bs_mix"] = _save(fig, charts_dir, "bs_mix.png")

    # 2. P&L bridge -------------------------------------------------------------
    seq = [("Interest\nEarned", _v(pl["income"], "Interest Earned")),
           ("Interest\nExpended", -_v(pl["expenses"], "Interest Expended")),
           ("Other\nIncome", _v(pl["income"], "Other Income (fees, treasury)")),
           ("Operating\nExpenses", -_v(pl["expenses"], "Operating Expenses")),
           ("Provisions", -_v(pl["summary"], "Provisions & Contingencies")),
           ("Tax", -_v(pl["summary"], "Tax Expense")),
           ("PAT", _v(pl["summary"], "Profit After Tax (PAT)"))]
    fig, ax = plt.subplots(figsize=(6.8, 2.6))
    labels = [s[0] for s in seq]
    vals = [s[1] / 1e7 for s in seq]
    colors = [GREEN if v >= 0 else RED for v in vals]
    colors[-1] = NAVY
    ax.bar(labels, vals, color=colors, width=0.62)
    ax.axhline(0, color="#CBD5E1", lw=1)
    ax.set_ylabel("₹ Cr")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for i, v in enumerate(vals):
        ax.text(i, v + (0.02 if v >= 0 else -0.02) * max(abs(min(vals)), abs(max(vals)), 1),
                f"{v:,.2f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
    ax.tick_params(axis="x", labelsize=7)
    out["pnl"] = _save(fig, charts_dir, "pnl.png")

    # 3. RWA composition --------------------------------------------------------
    rwa_items = [(i["label"].replace(" RWA", "").replace(" (Basel BIA)", ""), i["value"])
                 for i in p3["rwa"] if not i.get("strong") and i["value"] > 0]
    if rwa_items:
        fig, ax = plt.subplots(figsize=(3.3, 2.8))
        ax.pie([v for _, v in rwa_items], labels=[k for k, _ in rwa_items],
               autopct=lambda p: f"{p:.0f}%", colors=[RED, AMBER, BLUE],
               wedgeprops={"edgecolor": "white"}, textprops={"fontsize": 7.5})
        ax.set_title("RWA Composition", fontsize=10, color=NAVY, fontweight="bold")
        out["rwa"] = _save(fig, charts_dir, "rwa.png")

    # 4. Capital ratios vs RBI minimums -----------------------------------------
    ratios = p3["capital_ratios"]
    fig, ax = plt.subplots(figsize=(3.3, 2.8))
    names = [r["label"].replace(" Ratio", "").replace(" (CRAR)", "") for r in ratios]
    vals = [r["value"] for r in ratios]
    mins = [r.get("min") for r in ratios]
    x = range(len(names))
    ax.bar(x, vals, color=[GREEN if (m is None or v >= m) else RED for v, m in zip(vals, mins)],
           width=0.6)
    for i, m in enumerate(mins):
        if m is not None:
            ax.plot([i - 0.3, i + 0.3], [m, m], color=NAVY, lw=1.4, ls="--")
    ax.set_xticks(list(x)); ax.set_xticklabels(names, rotation=20, ha="right", fontsize=7)
    ax.set_ylabel("%"); ax.set_title("Capital Ratios vs RBI Floors", fontsize=9.5,
                                     color=NAVY, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    out["cap_ratios"] = _save(fig, charts_dir, "cap_ratios.png")

    return out


def _v(items, label):
    for i in items:
        if i["label"] == label:
            return float(i.get("value") or 0)
    return 0.0


def _short(s, n=22):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


# ── LaTeX ──────────────────────────────────────────────────────────────────────
def _build_latex(bundle, charts, now):
    bank = bundle.get("bank") or {}
    bs = bundle["balance_sheet"]
    pl = bundle["profit_loss"]
    ratios = bundle["key_ratios"]
    p3 = bundle["pillar3"]
    is_consol = bundle.get("scope") == "consolidated"

    title = _tex(bank.get("bank_name", "Bank"))
    subtitle = ("Consolidated Financial Statements & Pillar 3 Disclosures"
                if is_consol else "Annual Financial Report & Pillar 3 Disclosures")
    meta_line = (f"{_tex(bank.get('bank_code',''))} · {_tex(bank.get('headquarters_city',''))}"
                 if not is_consol else f"{bank.get('num_banks', 0)} banks aggregated")

    def img(key, frac=1.0):
        if key not in charts:
            return ""
        width = f"{frac}\\linewidth"
        return f"\\begin{{center}}\\includegraphics[width={width}]{{charts/{charts[key]}}}\\end{{center}}"

    def line_rows(items):
        rows = []
        for it in items:
            lbl = _tex(it["label"])
            if it.get("indent"):
                lbl = "\\quad " + lbl
            if it.get("group") or it.get("strong"):
                lbl = "\\textbf{" + lbl + "}"
                val = "\\textbf{" + _money(it["value"]) + "}"
            else:
                val = _money(it["value"])
            rows.append(f"{lbl} & {val} \\\\")
        return "\n".join(rows)

    def ratio_rows(items):
        rows = []
        for r in items:
            v = r.get("value")
            vtxt = ("-" if v is None else f"{v:.2f}\\%")
            mn = f"{r['min']:.1f}\\%" if r.get("min") is not None else "--"
            st = _tex(r.get("status") or "")
            rows.append(f"{_tex(r['label'])} & {vtxt} & {mn} & {st} \\\\")
        return "\n".join(rows)

    bs_off = (f"Contingent liabilities {_money(bs['contingent_liabilities'])} \\quad "
              f"Bills for collection {_money(bs['bills_for_collection'])}")

    mix_rows = ""
    for m in (p3.get("credit_risk_mix") or []):
        mix_rows += (f"{_tex(m.get('loan_type',''))} & {_tex(m.get('classification',''))} & "
                     f"{int(m.get('n') or 0)} & {_money(m.get('ead'))} & {_money(m.get('rwa'))} & "
                     f"{_money(m.get('provision'))} \\\\\n")
    mix_section = ""
    if mix_rows:
        mix_section = (
            r"\vspace{6pt}\textbf{Credit Risk --- Exposure Mix}\\[2pt]"
            r"\begin{tabularx}{\linewidth}{@{}X l r r r r@{}}\toprule "
            r"\textbf{Product} & \textbf{Class} & \textbf{\#} & \textbf{EAD} & "
            r"\textbf{RWA} & \textbf{Provision} \\ \midrule " + mix_rows
            + r"\bottomrule \end{tabularx}")
    anchor_note = "aggregated across all banks" if is_consol else "live-anchored"

    return rf"""\documentclass[11pt]{{article}}
\usepackage[a4paper,margin=1.8cm]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{xcolor}}
\usepackage{{booktabs}}
\usepackage{{array}}
\usepackage{{tabularx}}
\usepackage{{helvet}}
\usepackage{{fancyhdr}}
\usepackage[hidelinks]{{hyperref}}
\renewcommand{{\familydefault}}{{\sfdefault}}
\definecolor{{navy}}{{HTML}}{{0D1B2A}}
\definecolor{{rred}}{{HTML}}{{E31837}}
\definecolor{{bordergrey}}{{HTML}}{{E2E8F0}}
\definecolor{{lightgrey}}{{HTML}}{{F4F6FA}}
\pagestyle{{fancy}}\fancyhf{{}}
\renewcommand{{\headrulewidth}}{{0.4pt}}
\lhead{{\small\textcolor{{navy}}{{\textbf{{Financial Report \& Pillar 3}}}}}}
\rhead{{\small\textcolor{{navy}}{{{_tex(bundle.get('period',''))}}}}}
\cfoot{{\small\thepage}}
\setlength{{\parindent}}{{0pt}}\setlength{{\parskip}}{{4pt}}
\newcommand{{\sectionrule}}[1]{{\vspace{{4pt}}{{\large\textcolor{{navy}}{{\textbf{{#1}}}}}}\\[-4pt]{{\color{{bordergrey}}\rule{{\linewidth}}{{0.8pt}}}}\\}}

\begin{{document}}

% ── cover ───────────────────────────────────────────────
\vspace*{{1.2cm}}
\begin{{center}}
{{\fontsize{{26}}{{30}}\selectfont\textcolor{{navy}}{{\textbf{{{title}}}}}}}\\[8pt]
{{\Large {_tex(subtitle)}}}\\[10pt]
{{\large {_tex(bundle.get('period',''))} \quad (as at {_tex(bundle.get('as_on_date',''))})}}\\[4pt]
{meta_line}\\[6pt]
{{\small\color{{gray}} Figures in INR. Generated {now.strftime('%d %b %Y, %H:%M UTC')}.}}
\end{{center}}
\vspace{{0.6cm}}

% ── key ratios ──────────────────────────────────────────
\sectionrule{{Key Financial Ratios}}
\renewcommand{{\arraystretch}}{{1.25}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r r l@{{}}}}
\toprule \textbf{{Ratio}} & \textbf{{Value}} & \textbf{{RBI Min}} & \textbf{{Status}} \\ \midrule
{ratio_rows(ratios)}
\bottomrule
\end{{tabularx}}

% ── balance sheet ───────────────────────────────────────
\sectionrule{{Balance Sheet — RBI Schedule III (Form A)}}
\begin{{minipage}}[t]{{0.49\linewidth}}
\renewcommand{{\arraystretch}}{{1.2}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}
\multicolumn{{2}}{{@{{}}l}}{{\textbf{{Capital \& Liabilities}}}} \\ \midrule
{line_rows(bs['liabilities'])}
\midrule \textbf{{Total}} & \textbf{{{_money(bs['total_liabilities_capital'])}}} \\
\end{{tabularx}}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.49\linewidth}}
\renewcommand{{\arraystretch}}{{1.2}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}
\multicolumn{{2}}{{@{{}}l}}{{\textbf{{Assets}}}} \\ \midrule
{line_rows(bs['assets'])}
\midrule \textbf{{Total}} & \textbf{{{_money(bs['total_assets'])}}} \\
\end{{tabularx}}
\end{{minipage}}

\vspace{{4pt}}{{\small\color{{gray}} {bs_off}}}
{img('bs_mix', 0.92)}

% ── profit & loss ───────────────────────────────────────
\newpage
\sectionrule{{Profit \& Loss Statement}}
\renewcommand{{\arraystretch}}{{1.2}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}
\multicolumn{{2}}{{@{{}}l}}{{\textbf{{Income}}}} \\ \midrule
{line_rows(pl['income'])}
\addlinespace \multicolumn{{2}}{{@{{}}l}}{{\textbf{{Expenses}}}} \\ \midrule
{line_rows(pl['expenses'])}
\addlinespace \multicolumn{{2}}{{@{{}}l}}{{\textbf{{Results}}}} \\ \midrule
{line_rows(pl['summary'])}
\end{{tabularx}}
{img('pnl', 0.95)}

% ── pillar 3 ────────────────────────────────────────────
\newpage
\sectionrule{{Basel III Pillar 3 Disclosures}}
\begin{{minipage}}[t]{{0.49\linewidth}}
\textbf{{Capital Structure}}\\[2pt]
\renewcommand{{\arraystretch}}{{1.18}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}\midrule
{line_rows(p3['capital_structure'])}
\end{{tabularx}}
\vspace{{6pt}}

\textbf{{Risk-Weighted Assets}}\\[2pt]
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}\midrule
{line_rows(p3['rwa'])}
\end{{tabularx}}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.49\linewidth}}
{img('rwa', 1.0)}
\end{{minipage}}

\vspace{{6pt}}
\textbf{{Capital Adequacy \& Leverage}}\\[2pt]
\renewcommand{{\arraystretch}}{{1.2}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r r l@{{}}}}
\toprule \textbf{{Ratio}} & \textbf{{Value}} & \textbf{{RBI Min}} & \textbf{{Status}} \\ \midrule
{ratio_rows(p3['capital_ratios'])}
\bottomrule
\end{{tabularx}}
{img('cap_ratios', 0.6)}

\vspace{{6pt}}
\textbf{{Liquidity Disclosures (LCR / NSFR)}}\\[2pt]
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}\midrule
{_liq_rows(p3['liquidity'])}
\end{{tabularx}}

{mix_section}

\vfill
{{\footnotesize\color{{gray}} Prepared on a Basel III / RBI basis. Balance-sheet capital, deposits and advances
are {anchor_note}; the P\&L is modelled from the loan book yield and
balance-sheet funding (yields/costs disclosed in the methodology). Operational RWA via the Basel Basic Indicator
Approach; market RWA nil (no trading book). RWA density {p3.get('rwa_density','-')}\\% of assets.}}

\end{{document}}
"""


def _liq_rows(items):
    rows = []
    for i in items:
        if i.get("ratio"):
            val = f"{float(i['value']):.2f}\\%"
            extra = f" (min {i['min']:.0f}\\%, {_tex(i.get('status',''))})" if i.get("min") else ""
            rows.append(f"\\textbf{{{_tex(i['label'])}}} & \\textbf{{{val}{extra}}} \\\\")
        else:
            rows.append(f"{_tex(i['label'])} & {_money(i['value'])} \\\\")
    return "\n".join(rows)
