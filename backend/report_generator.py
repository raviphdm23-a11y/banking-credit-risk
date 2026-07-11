"""
report_generator.py
────────────────────
Produces a polished **PDF credit decision report** for a Relationship-Management
case, built from the Machine Recommendation (M) object + the case's governed
outcome. The pipeline is:

    M object  →  matplotlib charts (PNG)  →  LaTeX document  →  pdflatex  →  PDF

Folder structure (everything under data/case_reports/, gitignored & ephemeral
on GCP, same convention as data/reports/):

    data/case_reports/
        <case_id>/
            manifest.json                     ← version index for this borrower
            <version>/                         ← one folder per (re)generation
                charts/*.png
                report.tex
                report.pdf

Each call creates a NEW version folder, so regenerating a person's report never
destroys the previous one — the full history is retained and listed in the
manifest. The newest version is flagged `latest` in the manifest.

Requires a LaTeX engine (pdflatex / MiKTeX or TeX Live) on PATH and matplotlib.
"""

import os
import re
import json
import shutil
import subprocess
from datetime import datetime, timezone

from backend import feature_meta as _feature_meta

# Project-root/data/case_reports
# On App Engine Standard AND Cloud Run, the deployed source directory is
# read-only at runtime, so this must land under /tmp instead - same convention
# as app.py's _BASE_DATA_DIR / _READONLY_FS.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get('GAE_APPLICATION') is not None or os.environ.get('K_SERVICE') is not None:
    REPORTS_ROOT = os.path.join('/tmp', 'data', 'case_reports')
else:
    REPORTS_ROOT = os.path.join(_ROOT, "data", "case_reports")

# Palette (matches the platform UI)
NAVY, RED, GREEN, AMBER, GREY = "#0D1B2A", "#E31837", "#10B981", "#F59E0B", "#8A9AB0"

PD_REFER_CUTOFF = 0.12
PD_DECLINE_CUTOFF = 0.50

# The 36 features every segment PD model is trained on (see
# ml_models/trainer.py FEATURE_COLS and public/data-dictionary.html section 2),
# grouped by the Five C's for the page-1 customer snapshot. Labels/grouping are
# kept in sync with data-dictionary.html and the solution-overview deck.
_ATTRIBUTE_SNAPSHOT_GROUPS = [
    ("Character", [
        ("age", "Borrower Age"),
        ("employment_type_enc", "Employment Type (enc.)"),
        ("years_employed", "Years Employed"),
        ("city_tier_enc", "City Tier (enc.)"),
        ("education_enc", "Education (enc.)"),
        ("cibil_score", "CIBIL Score"),
        ("months_as_customer", "Months as Customer"),
        ("num_late_payments_past_12m", "Late Payments (12m)"),
    ]),
    ("Capacity", [
        ("de_ratio", "Debt / Equity Ratio"),
        ("interest_coverage", "Interest Coverage"),
        ("annual_income", "Annual Income"),
        ("foir", "FOIR"),
        ("num_dependents", "Dependents"),
        ("loan_purpose_enc", "Loan Purpose (enc.)"),
        ("existing_loans_count", "Existing Loans"),
    ]),
    ("Capital", [
        ("profitability", "Net Profit Margin"),
        ("liquidity_ratio", "Current Ratio"),
        ("residence_type_enc", "Residence Type (enc.)"),
        ("num_existing_products", "Existing Bank Products"),
    ]),
    ("Collateral", [
        ("ltv_trend_pct", "LTV Drift"),
    ]),
    ("Conditions", [
        ("gdp_growth_pct", "GDP Growth Rate"),
        ("inflation_cpi_pct", "Inflation (CPI)"),
        ("policy_rate_pct", "Policy Rate"),
        ("unemployment_pct", "Unemployment Rate"),
        ("delta_de_ratio", "Chg. D/E Ratio"),
        ("delta_cibil", "Chg. CIBIL Score"),
        ("months_since_origination", "Months Since Origination"),
        ("delta_gdp_pct", "Chg. GDP Growth"),
        ("delta_cpi_pct", "Chg. Inflation"),
        ("delta_policy_rate_pct", "Chg. Policy Rate"),
        ("delta_unemployment_pct", "Chg. Unemployment"),
        ("macro_regime_score", "Macro Regime Score"),
        ("ecs_bounce_count", "ECS/NACH Bounces"),
        ("other_lender_emi_ratio", "Other-Lender EMI Ratio"),
        ("income_disruption_flag", "Income Disruption Flag"),
        ("sector_stress_index", "Sector Stress Index"),
    ]),
]

_ATTR_PERCENT = {"profitability", "gdp_growth_pct", "inflation_cpi_pct",
                  "policy_rate_pct", "unemployment_pct", "delta_gdp_pct", "delta_cpi_pct",
                  "delta_policy_rate_pct", "delta_unemployment_pct", "ltv_trend_pct"}
# foir is stored as a 0-1 fraction (unlike the fields above, which are already in
# percentage-point units) - needs x100 before the % suffix.
_ATTR_PERCENT_FRACTION = {"foir"}
_ATTR_INR = {"annual_income"}
_ATTR_INT = {"age", "employment_type_enc", "city_tier_enc", "education_enc", "cibil_score",
              "months_as_customer", "num_late_payments_past_12m", "num_dependents",
              "loan_purpose_enc", "existing_loans_count", "residence_type_enc",
              "num_existing_products", "delta_cibil", "months_since_origination",
              "ecs_bounce_count", "income_disruption_flag"}


# ── public API ───────────────────────────────────────────────────────────────
def latex_available() -> bool:
    return _pdflatex_path() is not None


def generate_report(case: dict) -> dict:
    """Generate a new PDF report version for an RM case.

    `case` is the dict returned by rm_case_store.get_case (must contain
    'machine' = the M object, plus case/provenance/outcome fields).

    Returns a metadata dict: {case_id, version, generated_at, decision,
    state, pdf_exists, pdf_rel, error?}. Raises nothing for LaTeX failure —
    it records the error in the metadata and still keeps the .tex + charts.
    """
    M = case.get("machine") or {}
    case_id = case.get("case_id", "UNKNOWN")
    now = datetime.now(timezone.utc)
    version = "report_" + now.strftime("%Y%m%d_%H%M%S")

    case_dir = os.path.join(REPORTS_ROOT, _safe(case_id))
    version_dir = os.path.join(case_dir, version)
    charts_dir = os.path.join(version_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    charts = _build_charts(M, charts_dir)
    tex = _build_latex(case, M, charts, now)
    tex_path = os.path.join(version_dir, "report.tex")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(tex)

    pdf_ok, log_tail = _compile(tex_path, version_dir)

    meta = {
        "case_id": case_id,
        "version": version,
        "generated_at": now.isoformat(timespec="seconds"),
        "customer_name": case.get("customer_name"),
        "product": case.get("product"),
        "state": case.get("state"),
        "decision": case.get("final_decision") or (M.get("composed") or {}).get("recommendation"),
        "pdf_exists": pdf_ok,
        "pdf_rel": f"{_safe(case_id)}/{version}/report.pdf" if pdf_ok else None,
    }
    if not pdf_ok:
        meta["error"] = "LaTeX compilation failed"
        meta["log_tail"] = log_tail
    _update_manifest(case_dir, case, meta)
    return meta


def list_versions(case_id: str) -> list:
    """Newest-first list of report versions for a case (from its manifest)."""
    manifest = _read_manifest(os.path.join(REPORTS_ROOT, _safe(case_id)))
    return manifest.get("versions", [])


def pdf_path(case_id: str, version: str):
    """Absolute path to a version's PDF, or None if it doesn't exist."""
    p = os.path.join(REPORTS_ROOT, _safe(case_id), _safe(version), "report.pdf")
    return p if os.path.exists(p) else None


# ── manifest ─────────────────────────────────────────────────────────────────
def _read_manifest(case_dir: str) -> dict:
    path = os.path.join(case_dir, "manifest.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"versions": []}


def _update_manifest(case_dir: str, case: dict, meta: dict) -> None:
    os.makedirs(case_dir, exist_ok=True)
    manifest = _read_manifest(case_dir)
    manifest["case_id"] = meta["case_id"]
    manifest["customer_name"] = case.get("customer_name")
    versions = [v for v in manifest.get("versions", [])]
    for v in versions:
        v["latest"] = False
    meta_entry = dict(meta)
    meta_entry["latest"] = True
    versions.insert(0, meta_entry)            # newest first
    manifest["versions"] = versions
    manifest["latest_version"] = meta["version"]
    with open(os.path.join(case_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, default=str)


# ── charts ───────────────────────────────────────────────────────────────────
def _build_charts(M: dict, charts_dir: str) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager  # noqa: F401

    plt.rcParams.update({
        "font.size": 10, "axes.edgecolor": "#CBD5E1", "axes.linewidth": 0.8,
        "axes.grid": False, "figure.dpi": 150,
    })
    out = {}

    # 1. PD band vs decision cutoffs --------------------------------------------
    pd_ = M.get("pd") or {}
    point = float(pd_.get("point", 0)) * 100
    low = float(pd_.get("low", point / 100)) * 100
    high = float(pd_.get("high", point / 100)) * 100
    fig, ax = plt.subplots(figsize=(6.6, 1.55))
    xmax = max(high * 1.25, PD_DECLINE_CUTOFF * 100 * 1.05, 5)
    ax.barh([0], [high - low], left=[low], height=0.4, color=NAVY, alpha=0.18,
            label="80% prediction band")
    ax.plot([point], [0], "o", color=RED, markersize=11, zorder=5, label="PD estimate")
    ax.axvline(PD_REFER_CUTOFF * 100, color=AMBER, ls="--", lw=1.3)
    ax.axvline(PD_DECLINE_CUTOFF * 100, color=RED, ls="--", lw=1.3)
    ax.text(PD_REFER_CUTOFF * 100, 0.32, " Refer 12%", color=AMBER, fontsize=8, va="bottom")
    ax.text(PD_DECLINE_CUTOFF * 100, 0.32, " Decline 50%", color=RED, fontsize=8, va="bottom")
    ax.annotate(f"{point:.2f}%", (point, 0), textcoords="offset points", xytext=(0, -20),
                ha="center", color=RED, fontweight="bold", fontsize=11)
    ax.set_xlim(0, xmax); ax.set_ylim(-0.6, 0.85)
    ax.set_yticks([]); ax.set_xlabel("Probability of Default (%)", fontsize=8.5)
    ax.tick_params(axis="x", labelsize=8)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper center", ncol=2, fontsize=7.5, frameon=False,
              bbox_to_anchor=(0.5, 1.08))
    out["pd_band"] = _save(fig, charts_dir, "pd_band.png")

    # 2. Feature attribution (reason codes) -------------------------------------
    attr = [a for a in (M.get("attribution") or []) if abs(a.get("contribution", 0)) > 1e-4][:6]
    if attr:
        attr = sorted(attr, key=lambda a: a["contribution"])
        names = [_short(a["display_name"]) for a in attr]
        vals = [a["contribution"] * 100 for a in attr]
        colors = [RED if v > 0 else GREEN for v in vals]
        fig, ax = plt.subplots(figsize=(6.6, max(1.3, 0.42 * len(attr) + 0.55)))
        ax.barh(names, vals, color=colors, height=0.6)
        ax.axvline(0, color="#CBD5E1", lw=1)
        ax.set_xlabel("Marginal effect on PD (percentage points)", fontsize=8.5)
        ax.tick_params(labelsize=8.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        # Pad both x-limits so the +x.xx / -x.xx value labels never clip at the
        # plot edge (the old version clipped the leftmost negative label).
        vmin, vmax = min(vals + [0]), max(vals + [0])
        vrange = max(vmax - vmin, 1)
        ax.set_xlim(vmin - 0.16 * vrange, vmax + 0.16 * vrange)
        for y, v in enumerate(vals):
            ax.text(v + (0.02 if v >= 0 else -0.02) * vrange,
                    y, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right",
                    fontsize=8, color=NAVY)
        out["attribution"] = _save(fig, charts_dir, "attribution.png")

    # Five C's scorecard and risk-economics bar chart were retired: the Five C
    # scores render as native LaTeX colour pills and the four rupee figures as a
    # one-row table - both carry the same information in a fraction of the space.
    return out


def _save(fig, charts_dir, name):
    import matplotlib.pyplot as plt
    path = os.path.join(charts_dir, name)
    fig.tight_layout(pad=0.6)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return name  # relative to version dir is charts/<name>; we return basename


# ── LaTeX ────────────────────────────────────────────────────────────────────
def _build_latex(case: dict, M: dict, charts: dict, now: datetime) -> str:
    comp = M.get("composed") or {}
    conf = M.get("confidence") or {}
    rating = M.get("rating") or {}
    be = M.get("business_explanation") or {}
    pol = M.get("policy") or {}
    el = M.get("el") or {}
    rwa = M.get("rwa") or {}
    pricing = M.get("pricing") or {}

    decision = case.get("final_decision") or comp.get("recommendation") or "—"
    decision_label = _DECISION_LABEL.get(decision, decision)
    dcolor = {"APPROVE": GREEN, "APPROVE_WITH_CONDITIONS": AMBER, "COUNTER_OFFER": AMBER,
              "REFER": AMBER, "DECLINE": RED}.get(decision, NAVY)

    def img(key, width="\\linewidth"):
        if key not in charts:
            return ""
        return (f"\\begin{{center}}\\includegraphics[width={width}]"
                f"{{charts/{charts[key]}}}\\end{{center}}")

    # KPI tile strip — the six numbers an approver needs before anything else.
    pd_pct = float((M.get('pd') or {}).get('point', 0)) * 100
    try:
        el_pct_str = f"{float(el.get('percentage')):.2f}\\%"
    except (TypeError, ValueError):
        el_pct_str = "---"
    kpi_caps = ["RISK GRADE", "DEFAULT PROBABILITY", "EL \\% OF EAD",
                "INDICATIVE RATE", "RWA", "CAPITAL REQUIRED"]
    kpi_vals = [
        rf"\textcolor{{decision}}{{{_tex(rating.get('grade','-'))}}}",
        f"{pd_pct:.2f}\\%",
        el_pct_str,
        f"{pricing.get('indicative_rate_pct','-')}\\%",
        _inr_short(rwa.get('rwa') or 0),
        _inr_short(rwa.get('capital_required') or 0),
    ]
    kpi_strip = (
        r"\renewcommand{\arraystretch}{1.0}"
        r"\begin{tabularx}{\linewidth}{*{6}{>{\centering\arraybackslash}X}}" + "\n"
        + " & ".join(rf"\cellcolor{{lightgrey}}{{\fontsize{{6.2}}{{8}}\selectfont\textcolor{{gray}}{{{c}}}}}"
                      for c in kpi_caps) + r" \\" + "\n"
        + " & ".join(rf"\cellcolor{{lightgrey}}{{\fontsize{{12.5}}{{15}}\selectfont\textbf{{\textcolor{{navy}}{{{v}}}}}}}"
                      for v in kpi_vals) + r" \\" + "\n"
        + r"\end{tabularx}")

    # Secondary decision detail — everything from the old Decision Summary list
    # not already carried by a tile, as one compact line.
    kpi_detail_line = (
        rf"{{\small \textbf{{Rating}} {_tex(rating.get('description',''))} \quad"
        rf"\textbf{{Confidence}} {_tex(conf.get('class','-'))} "
        rf"(band {float(conf.get('pd_low',0))*100:.1f}--{float(conf.get('pd_high',0))*100:.1f}\%) \quad"
        rf"\textbf{{LGD}} {(M.get('lgd') or {}).get('lgd_percentage','-')}\% \quad"
        rf"\textbf{{Suggested limit}} {_inr_short(comp.get('suggested_limit') or 0)}}}")

    # Five C's score pills (replaces the retired bar chart)
    five_pills = _five_cs_pills(M)

    # Risk economics one-row table (replaces the retired rupee bar chart)
    ead_val = float(M.get('ead') or rwa.get('exposure') or 0)
    rwa_val = float(rwa.get('rwa') or 0)
    risk_weight_cell = f"{(rwa_val / ead_val * 100):.0f}\\%" if ead_val > 0 else "---"
    risk_econ_row = (
        f"{_inr(ead_val)} & {_inr(rwa_val)} & {risk_weight_cell} & "
        f"{_inr(rwa.get('capital_required') or 0)} & "
        f"{_inr(el.get('amount_inr') or 0)} & {el.get('percentage','-')}\\%")

    # page-1 high-level snapshot: all 36 model-input attribute values
    attribute_snapshot = _attribute_snapshot(M.get("application"))

    # conditions / watch / recourse
    conditions = comp.get("conditions") or []
    watch = be.get("watch_items") or []
    recourse = _recourse_items(M, be)
    top_factors = be.get("top_factors") or []

    # rich underwriter detail (folded in from the same findings the dossier shows)
    five_detail = _five_cs_detail(M)
    peer_rows = _peer_rows(M)
    reason_rows = _reason_rows(M)
    reason_section = ""
    if reason_rows:
        reason_section = (
            r"\vspace{4pt}\textbf{Reason codes}\\[2pt]"
            r"\renewcommand{\arraystretch}{1.2}"
            r"\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{0.24\linewidth} l l X@{}}"
            r"\toprule \textbf{Driver} & \textbf{Value} & \textbf{PD} & \textbf{Why it matters} \\ \midrule "
            + reason_rows + r"\bottomrule\end{tabularx}")
    peer_section = ""
    if peer_rows:
        peer_seg = M.get("peer_segment") or {}
        seg_label = ""
        if peer_seg.get("exposure_class"):
            seg_name = _tex(peer_seg["exposure_class"].replace('_', ' '))
            n_note = f" (n={peer_seg['n_peers']})" if peer_seg.get("n_peers") else ""
            seg_label = rf"\textit{{\small Compared against: {seg_name} peers{n_note}}}\\[4pt]"
        peer_section = (
            r"\rsec{Metrics vs Approved Borrowers}"
            + seg_label +
            r"\renewcommand{\arraystretch}{1.2}"
            r"\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}X l l l l@{}}"
            r"\toprule \textbf{Metric} & \textbf{Applicant} & \textbf{Approved median} & "
            r"\textbf{Approved P25--P75} & \textbf{Status} \\ \midrule "
            + peer_rows + r"\bottomrule\end{tabularx}")
    five_detail_section = ""
    if five_detail:
        five_detail_section = r"\vspace{4pt}" + five_detail

    def bullets(items):
        # Trailing \par is mandatory even in the empty branch: without it, this
        # text stays in the same paragraph as the \textbf{...}\par heading that
        # precedes it AND the next heading that follows, so "Conditions
        # attached" + "None." + "Watch items / policy flags" all ran together
        # on one line instead of stacking as three separate labelled rows.
        if not items:
            return "{\\small\\textit{None.}}\\par"
        return "\\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]\n" + \
               "\n".join(f"  \\item {_tex(str(x))}" for x in items) + \
               "\n\\end{itemize}"

    # NOTE: the old "raises/lowers" bullet list was dropped - it repeated the
    # Reason codes table verbatim, minus the values. The table alone carries it.
    _ = top_factors  # retained in findings; intentionally not rendered twice

    # provenance summary
    prov = case.get("provenance") or []
    prov_rows = ""
    for ev in prov:
        prov_rows += (f"{_tex((ev.get('ts','')).replace('T',' ').replace('+00:00',''))} & "
                      f"{_tex(ev.get('event_type','').replace('_',' '))} & "
                      f"{_tex(ev.get('actor_role','').replace('_',' '))} & "
                      f"{_tex((ev.get('hash','') or '')[:12])} \\\\\n")

    outcome = case.get("outcome") or {}

    headline = _tex(be.get("headline", ""))
    reassessment = _tex(be.get("reassessment", ""))
    model_v = _tex(M.get("model_version", ""))
    policy_v = _tex(pol.get("policy_version", ""))

    dcolor_tex = dcolor.lstrip("#")

    return rf"""\documentclass[10pt]{{article}}
\usepackage[a4paper,top=1.3cm,bottom=1.3cm,left=1.7cm,right=1.7cm,headheight=14pt]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{amssymb}}
\usepackage[table]{{xcolor}}
\usepackage{{enumitem}}
\usepackage{{booktabs}}
\usepackage{{array}}
\usepackage{{tabularx}}
\usepackage{{helvet}}
\usepackage{{fancyhdr}}
\usepackage[hidelinks]{{hyperref}}
\renewcommand{{\familydefault}}{{\sfdefault}}
\definecolor{{navy}}{{HTML}}{{0D1B2A}}
\definecolor{{rred}}{{HTML}}{{E31837}}
\definecolor{{rgreen}}{{HTML}}{{10B981}}
\definecolor{{ramber}}{{HTML}}{{F59E0B}}
\definecolor{{ramberdk}}{{HTML}}{{B45309}}
\definecolor{{decision}}{{HTML}}{{{dcolor_tex}}}
\definecolor{{lightgrey}}{{HTML}}{{F4F6FA}}
\definecolor{{bordergrey}}{{HTML}}{{E2E8F0}}
\definecolor{{rgreenlt}}{{HTML}}{{E6F7F1}}
\definecolor{{ramberlt}}{{HTML}}{{FEF3E2}}
\definecolor{{rredlt}}{{HTML}}{{FDEBED}}
% Slim uppercase section heading with a hairline rule - denser than \section*
\newcommand{{\rsec}}[1]{{\par\vspace{{7pt}}\noindent{{\color{{navy}}\fontsize{{10.5}}{{13}}\selectfont\bfseries\MakeUppercase{{#1}}}}\par\vspace{{1.5pt}}\noindent{{\color{{bordergrey}}\rule{{\linewidth}}{{0.8pt}}}}\par\vspace{{3pt}}}}
\pagestyle{{fancy}}\fancyhf{{}}
\renewcommand{{\headrulewidth}}{{0.4pt}}
\lhead{{\footnotesize\textcolor{{navy}}{{\textbf{{CREDIT DECISION REPORT}} --- {_tex(case.get('customer_name','Applicant'))}}}}}
\rhead{{\footnotesize\textcolor{{navy}}{{{_tex(case.get('case_id',''))}}}}}
\lfoot{{\tiny\textcolor{{gray}}{{Confidential --- internal credit-decisioning use only}}}}
\rfoot{{\footnotesize\textcolor{{gray}}{{Page \thepage}}}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{3pt}}

\begin{{document}}

% ── page 1: letterhead band ──────────────────────────────
\thispagestyle{{empty}}
\noindent\colorbox{{navy}}{{\parbox{{\dimexpr\linewidth-2\fboxsep\relax}}{{%
\vspace{{4pt}}\color{{white}}\hspace{{2pt}}{{\fontsize{{13}}{{16}}\selectfont\textbf{{CREDIT DECISION REPORT}}}}\hfill
{{\fontsize{{7.5}}{{9}}\selectfont CONFIDENTIAL --- INTERNAL USE ONLY\hspace{{2pt}}}}\vspace{{4pt}}}}}}\\[3pt]
{{\footnotesize\textcolor{{gray}}{{Case {_tex(case.get('case_id',''))}
\;\textbullet\; Generated {now.strftime('%d %b %Y, %H:%M UTC')}
\;\textbullet\; Model {model_v}
\;\textbullet\; Policy {policy_v}}}}}

\vspace{{7pt}}
% ── borrower + decision ──────────────────────────────────
\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}
{{\fontsize{{17}}{{20}}\selectfont\textcolor{{navy}}{{\textbf{{{_tex(case.get('customer_name','Applicant'))}}}}}}} &
\raisebox{{2pt}}{{\colorbox{{decision}}{{\color{{white}}\fontsize{{11}}{{13}}\selectfont\textbf{{\ {_tex(decision_label)}\ }}}}}}\\
\end{{tabularx}}
\vspace{{2pt}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}XXX@{{}}}}
{{\scriptsize\textcolor{{gray}}{{PRODUCT}}}} & {{\scriptsize\textcolor{{gray}}{{REQUESTED AMOUNT}}}} & {{\scriptsize\textcolor{{gray}}{{FINAL AUTHORITY}}}}\\
\textbf{{{_tex(case.get('product','—'))}}} & \textbf{{{_inr(case.get('requested_amount') or 0)}}} & \textbf{{Relationship Manager}}\\
\end{{tabularx}}

\vspace{{6pt}}
% ── KPI strip ────────────────────────────────────────────
{kpi_strip}
\vspace{{2pt}}\begin{{center}}{kpi_detail_line}\end{{center}}

\vspace{{2pt}}
\textit{{{headline}}}

% ── page 1: high-level customer snapshot (all 36 model inputs) ───────────
\rsec{{Customer Attribute Snapshot --- 36 Model Inputs}}
\footnotesize
{attribute_snapshot}
\normalsize

% Fill the remainder of page 1 with the two most decision-relevant visuals
% (PD gauge + Five C's summary) instead of leaving the lower half blank -
% both are compact and belong on the cover page alongside the KPI strip.
\vspace{{4pt}}
\rsec{{Probability of Default}}
{img('pd_band')}

\vspace{{2pt}}
\rsec{{Five C's of Credit --- Summary}}
{five_pills}
\newpage

% ── attribution ──────────────────────────────────────────
\rsec{{Key Risk Drivers}}
{img('attribution')}
{reason_section}

% ── five Cs detail ────────────────────────────────────────
\rsec{{Five C's of Credit --- Detailed Evidence}}
{five_detail_section}

% ── peer comparison ──────────────────────────────────────
{peer_section}

% ── risk economics ───────────────────────────────────────
\rsec{{Risk \& Capital}}
\renewcommand{{\arraystretch}}{{1.2}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}*{{6}}{{>{{\raggedright\arraybackslash}}X}}@{{}}}}
\toprule
\textbf{{Exposure (EAD)}} & \textbf{{RWA}} & \textbf{{Risk weight}} & \textbf{{Capital (8\% RWA)}} & \textbf{{Expected loss}} & \textbf{{EL \% of EAD}}\\
\midrule
{risk_econ_row}\\
\bottomrule
\end{{tabularx}}

% ── conditions / watch / recourse ────────────────────────
\rsec{{Conditions \& Recourse}}
\begin{{minipage}}[t]{{0.48\linewidth}}
\textbf{{Conditions attached}}\par
{bullets(conditions)}
\vspace{{3pt}}
\textbf{{Watch items / policy flags}}\par
{bullets(watch)}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.48\linewidth}}
\textbf{{What could change the outcome}}\par
{bullets(recourse)}
\end{{minipage}}
\vspace{{4pt}}\par
\textbf{{Reassessment:}} {reassessment}

% ── provenance ───────────────────────────────────────────
\rsec{{Decision Provenance (hash-chained)}}
\renewcommand{{\arraystretch}}{{1.1}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}l X l l@{{}}}}
\toprule
\textbf{{Timestamp}} & \textbf{{Event}} & \textbf{{Actor}} & \textbf{{Hash}} \\
\midrule
{prov_rows}
\bottomrule
\end{{tabularx}}

{_outcome_block(outcome)}

% Fixed spacing rather than \vfill: forcing this paragraph to the very bottom
% of the page pushed the whole 3-line disclaimer onto a near-empty extra page
% whenever the provenance table left too little room above it to fit both the
% stretch and the text. A small fixed gap lets it flow right after the table.
\vspace{{10pt}}
{{\fontsize{{7.5}}{{9.5}}\selectfont\color{{gray}} This report is generated from the platform's Machine Recommendation (M),
the relationship manager's decision (H) and the governed organisational outcome (O).
PD, LGD, RWA and pricing follow the Basel III AIRB methodology; capital required is 8\% of RWA.
The relationship manager is the final approving authority. Document is reproducible from the
case content hash and is for internal credit-decisioning use.}}

\end{{document}}
"""


def _fmt_peer(v, unit) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return _tex(str(v))
    u = (unit or "").lower()
    if u in ("inr", "rs", "rupee", "₹"):
        return _inr(v)
    if u in ("%", "pct", "percent"):
        return f"{v:.1f}\\%"
    if u == "ratio":
        return f"{v:.2f}x"
    return f"{v:.2f}"


_FIVE_C_STYLE = {  # score -> (label-bar background, text colour) - shared with _five_cs_pills
    "STRONG":       ("rgreenlt", "rgreen"),
    "MODERATE":     ("ramberlt", "ramberdk"),
    "WEAK":         ("rredlt", "rred"),
    "NEUTRAL":      ("lightgrey", "gray"),
    "NOT_ASSESSED": ("lightgrey", "gray"),
}


def _five_cs_detail(M: dict) -> str:
    """Per-C evidence/commentary tables (the textual detail the underwriter view shows,
    which the scorecard chart alone omits). Each C gets a coloured label bar (matching
    the summary pills) plus a ruled, zebra-striped table with an explicit header row -
    a flat run of text with no header/row separation reads as one undifferentiated block."""
    five = M.get("five_cs") or {}
    order = ["character", "capacity", "capital", "collateral", "conditions"]
    blocks = []
    for c in order:
        d = five.get(c)
        if not d:
            continue
        items = d.get("items") or []
        if not items:
            continue
        score = str(d.get("score", "NEUTRAL"))
        bg, fg = _FIVE_C_STYLE.get(score, ("lightgrey", "gray"))
        rows = "".join(
            f"{_tex(it.get('label',''))} & {_tex(str(it.get('value','')))} & "
            f"{_tex(str(it.get('benchmark','')))} & {_tex(it.get('assessment',''))} \\\\\n"
            for it in items)
        # Wrapped in a minipage so the coloured label bar can never be orphaned
        # at the bottom of a page while its table starts on the next one -
        # LaTeX treats a minipage as one unbreakable unit and pushes the whole
        # block over instead. Each block is short (2-4 rows), so this never
        # creates a large stranded gap.
        blocks.append(
            rf"\begin{{minipage}}{{\linewidth}}"
            rf"\colorbox{{{bg}}}{{\makebox[\dimexpr\linewidth-2\fboxsep\relax][l]{{\small"
            rf"\textbf{{\textcolor{{navy}}{{{_tex(c.capitalize())}}}}}"
            rf"\hfill\textbf{{\textcolor{{{fg}}}{{{_tex(score.replace('_',' '))}}}}}\ }}}}\\[3pt]"
            rf"\rowcolors{{2}}{{white}}{{lightgrey!45}}"
            rf"\renewcommand{{\arraystretch}}{{1.25}}"
            rf"\begin{{tabularx}}{{\linewidth}}{{@{{}}>{{\raggedright\arraybackslash}}p{{0.22\linewidth}} l l X@{{}}}}"
            rf"\toprule \textbf{{\footnotesize Metric}} & \textbf{{\footnotesize Value}} & "
            rf"\textbf{{\footnotesize Benchmark}} & \textbf{{\footnotesize Assessment}}\\ \midrule{{}}"
            rf"{rows}\bottomrule\end{{tabularx}}"
            rf"\end{{minipage}}\vspace{{7pt}}")
    return "\n".join(blocks)


def _peer_rows(M: dict) -> str:
    peer = M.get("peer_health") or {}
    rows = ""
    for f, h in list(peer.items())[:8]:
        u = h.get("unit")
        rows += (f"{_tex(h.get('display_name', f))} & {_fmt_peer(h.get('value'), u)} & "
                 f"{_fmt_peer(h.get('peer_median'), u)} & "
                 f"{_fmt_peer(h.get('peer_p25'), u)}--{_fmt_peer(h.get('peer_p75'), u)} & "
                 f"{_tex(str(h.get('status', '')))} \\\\\n")
    return rows


def _reason_rows(M: dict) -> str:
    attr = [a for a in (M.get("attribution") or []) if abs(a.get("contribution", 0)) > 1e-4][:6]
    rows = ""
    for a in attr:
        rows += (f"{_tex(a.get('display_name', ''))} & {_tex(str(a.get('value', '')))} & "
                 f"{a.get('contribution', 0) * 100:+.2f}pp & {_tex(a.get('reason_text', ''))} \\\\\n")
    return rows


def _recourse_items(M: dict, be: dict) -> list:
    """Prefer the structured counterfactual recourse from the findings; fall back to
    the business-explanation summary."""
    cf = [c.get("action_text") for c in (M.get("counterfactuals") or []) if c.get("action_text")]
    return cf or (be.get("what_could_change") or [])


def _outcome_block(outcome: dict) -> str:
    if not outcome:
        return ""
    return (rf"""\rsec{{Post-Decision Outcome}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}l X@{{}}}}
\textbf{{Performance}} & {_tex(str(outcome.get('performance_status','—')))} \\
\textbf{{Days past due}} & {outcome.get('dpd',0)} \\
\textbf{{Default}} & {'Yes' if outcome.get('default_flag') else 'No'} \\
\end{{tabularx}}""")


# ── compile ──────────────────────────────────────────────────────────────────
def _pdflatex_path():
    return shutil.which("pdflatex") or shutil.which("xelatex")


def _compile(tex_path: str, work_dir: str):
    engine = _pdflatex_path()
    if not engine:
        return False, "No LaTeX engine (pdflatex/xelatex) on PATH."
    log_tail = ""
    try:
        for _ in range(2):  # twice: resolve refs / layout
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", "report.tex"],
                cwd=work_dir, capture_output=True, text=True, timeout=120)
            log_tail = (proc.stdout or "")[-1500:]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    pdf = os.path.join(work_dir, "report.pdf")
    ok = os.path.exists(pdf)
    if ok:  # tidy aux artefacts, keep .tex + .pdf + charts
        for ext in (".aux", ".log", ".out", ".toc"):
            f = os.path.join(work_dir, "report" + ext)
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
    return ok, log_tail


# ── helpers ──────────────────────────────────────────────────────────────────
_TEX_ESCAPE = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}", "<": r"\textless{}", ">": r"\textgreater{}",
}


def _tex(s) -> str:
    """Escape a Python string for safe inclusion in LaTeX, and normalise the
    rupee sign / common unicode the default fonts can't render."""
    if s is None:
        return ""
    s = str(s)
    # Drop unicode the default LaTeX fonts can't render BEFORE char-escaping.
    s = s.replace("₹", "Rs. ").replace("—", "-").replace("–", "-") \
         .replace("≥", ">=").replace("≤", "<=").replace("×", "x") \
         .replace("→", "->").replace("“", '"').replace("”", '"') \
         .replace("’", "'").replace("‘", "'").replace("…", "...") \
         .replace("≈", "~").replace("•", "-")
    # Safety net: drop any remaining non-ASCII the default fonts can't render.
    s = s.encode("ascii", "ignore").decode("ascii")
    return "".join(_TEX_ESCAPE.get(ch, ch) for ch in s)


def _inr(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    return "Rs.~" + format(int(round(v)), ",d")


def _fmt_attr(key: str, value) -> str:
    """Format one resolved feature value for the page-1 snapshot table."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _tex(str(value))
    if key in _ATTR_INR:
        return _inr(v)
    if key in _ATTR_PERCENT_FRACTION:
        return f"{v * 100:.2f}\\%"
    if key in _ATTR_PERCENT:
        return f"{v:.2f}\\%"
    if key in _ATTR_INT:
        return f"{int(round(v))}"
    return f"{v:.2f}"


def _resolve_attribute_value(key: str, application: dict):
    """Same fallback chain as feature_meta.model_feature_frame(): applicant-
    supplied value first, then the core-ratio baseline, then the calibrated
    neutral default - so the snapshot shows exactly what the model actually saw,
    not just whatever the applicant happened to fill in."""
    if key in application and application[key] is not None:
        try:
            return float(application[key])
        except (TypeError, ValueError):
            return application[key]
    if key in _feature_meta.FEATURE_META:
        return _feature_meta.FEATURE_META[key]["baseline"]
    return _feature_meta.EXTRA_FEATURE_DEFAULTS.get(key, 0.0)


def _attribute_snapshot(application: dict) -> str:
    """Page-1 'high-level view of the customer': all 36 model-input attribute
    values, grouped by the Five C's, laid out as two columns so it fits on a
    single page regardless of the analysis that follows on page 2+.

    Columns are balanced by row count: Character+Capacity+Capital (19 rows) on
    the left, Collateral+Conditions (17 rows) on the right."""
    application = application or {}
    left_groups = _ATTRIBUTE_SNAPSHOT_GROUPS[:3]   # Character, Capacity, Capital
    right_groups = _ATTRIBUTE_SNAPSHOT_GROUPS[3:]  # Collateral, Conditions

    def col(groups):
        blocks = []
        for label, items in groups:
            rows = "".join(
                f"{_tex(display)} & {_fmt_attr(key, _resolve_attribute_value(key, application))} \\\\\n"
                for key, display in items
            )
            blocks.append(
                rf"\colorbox{{lightgrey}}{{\makebox[\dimexpr\linewidth-2\fboxsep\relax][l]"
                rf"{{\scriptsize\textbf{{\textcolor{{navy}}{{{_tex(label.upper())}}}}}}}}}\\[2pt]"
                rf"\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}"
                rf"{rows}\end{{tabularx}}\vspace{{5pt}}")
        return "\n".join(blocks)

    return (
        r"\begin{minipage}[t]{0.48\linewidth}" + "\n" + col(left_groups) + "\n" + r"\end{minipage}"
        r"\hfill"
        r"\begin{minipage}[t]{0.48\linewidth}" + "\n" + col(right_groups) + "\n" + r"\end{minipage}"
    )


def _inr_short(v) -> str:
    """Compact rupee figure for KPI tiles: Rs 6.25 Cr / Rs 50.00 L / Rs 43,785."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 1e7:
        return f"Rs.~{v / 1e7:.2f}~Cr"
    if abs(v) >= 1e5:
        return f"Rs.~{v / 1e5:.2f}~L"
    return "Rs.~" + format(int(round(v)), ",d")


def _five_cs_pills(M: dict) -> str:
    """Five C scores as a row of colour-tinted cells - replaces the retired
    bar chart with the same information at a fraction of the page height."""
    five = M.get("five_cs") or {}
    order = ["character", "capacity", "capital", "collateral", "conditions"]
    style = {  # score -> (cell background, text colour)
        "STRONG":       ("rgreenlt", "rgreen"),
        "MODERATE":     ("ramberlt", "ramberdk"),
        "WEAK":         ("rredlt", "rred"),
        "NEUTRAL":      ("lightgrey", "gray"),
        "NOT_ASSESSED": ("lightgrey", "gray"),
    }
    present = [c for c in order if five.get(c)]
    if not present:
        return ""
    name_cells, score_cells = [], []
    for c in present:
        score = str((five[c] or {}).get("score", "NEUTRAL"))
        bg, fg = style.get(score, ("lightgrey", "gray"))
        name_cells.append(rf"\cellcolor{{{bg}}}{{\small\textbf{{{_tex(c.capitalize())}}}}}")
        score_cells.append(rf"\cellcolor{{{bg}}}{{\scriptsize\textbf{{\textcolor{{{fg}}}{{{_tex(score.replace('_', ' '))}}}}}}}")
    ncols = len(present)
    return (
        rf"\renewcommand{{\arraystretch}}{{1.15}}"
        rf"\begin{{tabularx}}{{\linewidth}}{{*{{{ncols}}}{{>{{\centering\arraybackslash}}X}}}}"
        + " & ".join(name_cells) + r" \\" + "\n"
        + " & ".join(score_cells) + r" \\" + "\n"
        + r"\end{tabularx}")


def _short(s, n=26):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _safe(s) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))


_DECISION_LABEL = {
    "APPROVE": "APPROVE", "APPROVE_WITH_CONDITIONS": "APPROVE (CONDITIONS)",
    "COUNTER_OFFER": "COUNTER-OFFER", "REFER": "REFER", "DECLINE": "DECLINE",
}
