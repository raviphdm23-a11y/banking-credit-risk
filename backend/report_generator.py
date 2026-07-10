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
    fig, ax = plt.subplots(figsize=(6.6, 1.9))
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
    ax.set_yticks([]); ax.set_xlabel("Probability of Default (%)")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper center", ncol=2, fontsize=7.5, frameon=False,
              bbox_to_anchor=(0.5, 1.05))
    out["pd_band"] = _save(fig, charts_dir, "pd_band.png")

    # 2. Feature attribution (reason codes) -------------------------------------
    attr = [a for a in (M.get("attribution") or []) if abs(a.get("contribution", 0)) > 1e-4][:6]
    if attr:
        attr = sorted(attr, key=lambda a: a["contribution"])
        names = [_short(a["display_name"]) for a in attr]
        vals = [a["contribution"] * 100 for a in attr]
        colors = [RED if v > 0 else GREEN for v in vals]
        fig, ax = plt.subplots(figsize=(6.6, max(1.6, 0.5 * len(attr) + 0.7)))
        ax.barh(names, vals, color=colors, height=0.6)
        ax.axvline(0, color="#CBD5E1", lw=1)
        ax.set_xlabel("Marginal effect on PD (percentage points)")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for y, v in enumerate(vals):
            ax.text(v + (0.02 if v >= 0 else -0.02) * max(abs(min(vals)), abs(max(vals)), 1),
                    y, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right",
                    fontsize=8, color=NAVY)
        out["attribution"] = _save(fig, charts_dir, "attribution.png")

    # 3. Five C's scorecard -----------------------------------------------------
    five = M.get("five_cs") or {}
    score_map = {"STRONG": 3, "MODERATE": 2, "WEAK": 1, "NEUTRAL": 1.5,
                 "NOT_ASSESSED": 0}
    order = ["character", "capacity", "capital", "collateral", "conditions"]
    labels, scores = [], []
    for c in order:
        if c in five:
            labels.append(c.capitalize())
            scores.append(score_map.get((five[c] or {}).get("score", "NEUTRAL"), 1.5))
    if labels:
        cmap = {3: GREEN, 2: AMBER, 1.5: GREY, 1: RED, 0: "#CBD5E1"}
        fig, ax = plt.subplots(figsize=(6.6, 2.2))
        bars = ax.bar(labels, scores, color=[cmap.get(s, GREY) for s in scores], width=0.6)
        ax.set_ylim(0, 3.4); ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels(["N/A", "Weak", "Moderate", "Strong"], fontsize=8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for b, c in zip(bars, order[:len(labels)]):
            sc = (five[c] or {}).get("score", "")
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.08, sc,
                    ha="center", fontsize=7.5, color=NAVY)
        out["five_cs"] = _save(fig, charts_dir, "five_cs.png")

    # 4. Risk economics (EAD / RWA / Capital / EL) ------------------------------
    rwa = M.get("rwa") or {}
    el = M.get("el") or {}
    items = [
        ("Exposure (EAD)", float(M.get("ead") or rwa.get("exposure") or 0)),
        ("RWA", float(rwa.get("rwa") or 0)),
        ("Capital reqd", float(rwa.get("capital_required") or 0)),
        ("Expected loss", float(el.get("amount_inr") or 0)),
    ]
    items = [(k, v) for k, v in items if v > 0]
    if items:
        fig, ax = plt.subplots(figsize=(6.6, 2.1))
        names = [k for k, _ in items]
        vals = [v for _, v in items]
        bars = ax.barh(names[::-1], vals[::-1], color=NAVY, alpha=0.85, height=0.6)
        ax.set_xlabel("₹ (INR)")
        ax.set_xlim(0, max(vals) * 1.18)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for b, v in zip(bars, vals[::-1]):
            ax.text(v * 1.01, b.get_y() + b.get_height() / 2,
                    "₹" + format(int(round(v)), ",d"),
                    va="center", fontsize=8.5, color=NAVY)
        out["risk_econ"] = _save(fig, charts_dir, "risk_econ.png")

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

    # KPI table rows — values are already-final LaTeX (escaped where needed)
    kpis = [
        ("Risk grade", f"{_tex(rating.get('grade','-'))} --- {_tex(rating.get('description',''))}"),
        ("Probability of default", f"{float((M.get('pd') or {}).get('point',0))*100:.2f}\\%"),
        ("Confidence", f"{_tex(conf.get('class','-'))} (band "
                       f"{float(conf.get('pd_low',0))*100:.1f}--{float(conf.get('pd_high',0))*100:.1f}\\%)"),
        ("Loss given default", f"{(M.get('lgd') or {}).get('lgd_percentage','-')}\\%"),
        ("Exposure at default", _inr(M.get('ead') or rwa.get('exposure') or 0)),
        ("Risk-weighted assets", _inr(rwa.get('rwa') or 0)),
        ("Capital required", _inr(rwa.get('capital_required') or 0)),
        ("Expected loss", f"{_inr(el.get('amount_inr') or 0)} ({el.get('percentage','-')}\\%)"),
        ("Indicative rate", f"{pricing.get('indicative_rate_pct','-')}\\%"),
        ("Suggested limit", _inr(comp.get('suggested_limit') or 0)),
    ]
    kpi_rows = "\\\\\n".join(f"\\textbf{{{_tex(k)}}} & {v}" for k, v in kpis)

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
            r"\section*{\textcolor{navy}{Metrics vs Approved Borrowers}}"
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
        if not items:
            return "\\textit{None.}"
        return "\\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]\n" + \
               "\n".join(f"  \\item {_tex(str(x))}" for x in items) + \
               "\n\\end{itemize}"

    factor_rows = ""
    for f in top_factors:
        eff = f.get("effect", "")
        tag = "\\textcolor{rred}{$\\blacktriangle$ raises}" if eff == "raises risk" \
              else "\\textcolor{rgreen}{$\\blacktriangledown$ lowers}"
        factor_rows += f"{tag} & \\textbf{{{_tex(f.get('factor',''))}}}: {_tex(f.get('plain',''))} \\\\[2pt]\n"

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

    return rf"""\documentclass[11pt]{{article}}
\usepackage[a4paper,margin=2cm]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{amssymb}}
\usepackage{{xcolor}}
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
\definecolor{{decision}}{{HTML}}{{{dcolor_tex}}}
\definecolor{{lightgrey}}{{HTML}}{{F4F6FA}}
\definecolor{{bordergrey}}{{HTML}}{{E2E8F0}}
\pagestyle{{fancy}}\fancyhf{{}}
\renewcommand{{\headrulewidth}}{{0.4pt}}
\lhead{{\small\textcolor{{navy}}{{\textbf{{Credit Decision Report}}}}}}
\rhead{{\small\textcolor{{navy}}{{{_tex(case.get('case_id',''))}}}}}
\cfoot{{\small\thepage}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{4pt}}

\begin{{document}}

% ── header ───────────────────────────────────────────────
{{\fontsize{{20}}{{22}}\selectfont\textcolor{{navy}}{{\textbf{{{_tex(case.get('customer_name','Applicant'))}}}}}}}\\[2pt]
{{\color{{bordergrey}}\rule{{\linewidth}}{{1pt}}}}\\[4pt]
\begin{{tabularx}}{{\linewidth}}{{@{{}}lX r@{{}}}}
\textcolor{{gray}}{{Product}} & \textbf{{{_tex(case.get('product','—'))}}} &
\colorbox{{decision}}{{\textcolor{{white}}{{\textbf{{ {_tex(decision_label)} }}}}}}\\
\textcolor{{gray}}{{Requested}} & {_inr(case.get('requested_amount') or 0)} & \\
\textcolor{{gray}}{{Report date}} & {now.strftime('%d %b %Y, %H:%M UTC')} & \\
\end{{tabularx}}

\vspace{{6pt}}
\textit{{{headline}}}

\vspace{{4pt}}
\colorbox{{lightgrey}}{{\parbox{{\linewidth}}{{\small\textbf{{Final authority:}} Relationship Manager (accept / reject).\\
\textbf{{Model}} {model_v} \quad\textbf{{Policy}} {policy_v}}}}}

% ── page 1: high-level customer snapshot (all 36 model inputs) ───────────
\vspace{{8pt}}
\section*{{\textcolor{{navy}}{{Customer Attribute Snapshot (36 Model Inputs)}}}}
\footnotesize
{attribute_snapshot}
\normalsize
\newpage

% ── KPIs ─────────────────────────────────────────────────
\section*{{\textcolor{{navy}}{{Decision Summary}}}}
\renewcommand{{\arraystretch}}{{1.25}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}>{{\raggedright\arraybackslash}}p{{0.42\linewidth}} X@{{}}}}
{kpi_rows}
\end{{tabularx}}

% ── PD band ──────────────────────────────────────────────
\section*{{\textcolor{{navy}}{{Probability of Default}}}}
{img('pd_band')}

% ── attribution ──────────────────────────────────────────
\section*{{\textcolor{{navy}}{{Key Risk Drivers}}}}
{img('attribution')}
\vspace{{2pt}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}l X@{{}}}}
{factor_rows}
\end{{tabularx}}
{reason_section}

% ── five Cs ──────────────────────────────────────────────
\section*{{\textcolor{{navy}}{{Five C's of Credit}}}}
{img('five_cs')}
{five_detail_section}

% ── peer comparison ──────────────────────────────────────
{peer_section}

% ── risk economics ───────────────────────────────────────
\section*{{\textcolor{{navy}}{{Risk \& Capital}}}}
{img('risk_econ')}

% ── conditions / watch / recourse ────────────────────────
\section*{{\textcolor{{navy}}{{Conditions \& Recourse}}}}
\textbf{{Conditions attached}}
{bullets(conditions)}
\textbf{{Watch items / policy flags}}
{bullets(watch)}
\textbf{{What could change the outcome}}
{bullets(recourse)}
\vspace{{4pt}}
\textbf{{Reassessment:}} {reassessment}

% ── provenance ───────────────────────────────────────────
\section*{{\textcolor{{navy}}{{Decision Provenance (hash-chained)}}}}
\renewcommand{{\arraystretch}}{{1.15}}
\begin{{tabularx}}{{\linewidth}}{{@{{}}l X l l@{{}}}}
\toprule
\textbf{{Timestamp}} & \textbf{{Event}} & \textbf{{Actor}} & \textbf{{Hash}} \\
\midrule
{prov_rows}
\bottomrule
\end{{tabularx}}

{_outcome_block(outcome)}

\vfill
{{\footnotesize\color{{gray}} This report is generated from the platform's Machine Recommendation (M),
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


def _five_cs_detail(M: dict) -> str:
    """Per-C evidence/commentary tables (the textual detail the underwriter view shows,
    which the scorecard chart alone omits)."""
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
        rows = "".join(
            f"{_tex(it.get('label',''))} & {_tex(str(it.get('value','')))} & "
            f"{_tex(str(it.get('benchmark','')))} & {_tex(it.get('assessment',''))} \\\\\n"
            for it in items)
        blocks.append(
            rf"\textbf{{{c.capitalize()}}}~\textcolor{{gray}}{{[{_tex(d.get('score','-'))}]}}\\[1pt]"
            rf"\begin{{tabularx}}{{\linewidth}}{{@{{}}>{{\raggedright\arraybackslash}}p{{0.22\linewidth}} l l X@{{}}}}"
            rf"{rows}\end{{tabularx}}\vspace{{5pt}}")
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
    return (rf"""\section*{{\textcolor{{navy}}{{Post-Decision Outcome}}}}
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
    single page regardless of the analysis that follows on page 2+."""
    application = application or {}
    left_groups = _ATTRIBUTE_SNAPSHOT_GROUPS[:4]   # Character, Capacity, Capital, Collateral
    right_groups = _ATTRIBUTE_SNAPSHOT_GROUPS[4:]  # Conditions

    def col(groups):
        blocks = []
        for label, items in groups:
            rows = "".join(
                f"{_tex(display)} & {_fmt_attr(key, _resolve_attribute_value(key, application))} \\\\\n"
                for key, display in items
            )
            blocks.append(
                rf"\textbf{{\textcolor{{navy}}{{{_tex(label)}}}}}\\[1pt]"
                rf"\begin{{tabularx}}{{\linewidth}}{{@{{}}X r@{{}}}}"
                rf"{rows}\end{{tabularx}}\vspace{{4pt}}")
        return "\n".join(blocks)

    return (
        r"\begin{minipage}[t]{0.48\linewidth}" + "\n" + col(left_groups) + "\n" + r"\end{minipage}"
        r"\hfill"
        r"\begin{minipage}[t]{0.48\linewidth}" + "\n" + col(right_groups) + "\n" + r"\end{minipage}"
    )


def _short(s, n=26):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _safe(s) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))


_DECISION_LABEL = {
    "APPROVE": "APPROVE", "APPROVE_WITH_CONDITIONS": "APPROVE (CONDITIONS)",
    "COUNTER_OFFER": "COUNTER-OFFER", "REFER": "REFER", "DECLINE": "DECLINE",
}
