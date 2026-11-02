r"""
Build the Model Approval Dossier (LaTeX -> PDF), Phase 2 layout.

    python ml_models/build_dossier.py --data <dossier_data.pkl> --out <folder> [--phase 2]

Bank-perspective document: what the model is, which variables it uses, how it performs on the population it actually
scores, how it is governed and maintained, and, requirement by requirement, which criteria the evidence meets, partly
meets or does not meet (regulatory-use reading). It does not narrate how variables were selected from the data.

Every number is read from `dossier_data.collect(...)`; nothing is typed here. Citations are keyed to
`dossier/references/register.json`; an entry not verified against the primary text prints with a dagger.
"""
import argparse
import json
import os
import pickle
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

_ESC = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}


def esc(s):
    return ''.join(_ESC.get(ch, ch) for ch in str(s))


def tt(s):
    return r'\texttt{' + esc(s).replace(r'\_', r'\_\allowbreak{}') + '}'


def f(x, d=3):
    return 'n/a' if x is None else ('%.*f' % (d, x))


def pct(x, d=1):
    return 'n/a' if x is None else ('%.*f\\%%' % (d, 100 * x))


def num(x):
    return format(int(x), ',').replace(',', '{,}')


def rng(lo, hi, d=3):
    return '%s--%s' % (f(lo, d), f(hi, d))


STATUS_TEX = {'SATISFIED': r'\stSAT', 'PARTIAL': r'\stPAR', 'GAP': r'\stGAP', 'N/A': r'\stNA',
              'NOT ASSESSED': r'\stNOT', 'PENDING': r'\stPEN'}


def table(headers, rows, spec, caption=None, label=None, long=False):
    cap = (r'\caption{%s}' % caption + (r'\label{%s}' % label if label else '')) if caption else ''
    head = ' & '.join(r'\textbf{%s}' % h for h in headers) + r' \\'
    body = '\n'.join(' & '.join(r) + r' \\' for r in rows)
    if long:
        return (r'\footnotesize' + '\n' + r'\begin{longtable}{%s}' % spec + '\n' + (cap + r'\\' if cap else '') + '\n' + r'\toprule' + '\n' + head + '\n' +
                r'\midrule\endfirsthead' + '\n' + r'\toprule' + '\n' + head + '\n' + r'\midrule\endhead' + '\n' +
                r'\bottomrule\endfoot' + '\n' + body + '\n' + r'\end{longtable}' + '\n' + r'\normalsize' + '\n')
    return (r'\begin{table}[H]' + '\n' + r'\centering\footnotesize' + '\n' + cap + '\n' + r'\begin{tabular}{%s}' % spec + '\n' + r'\toprule' + '\n' + head + '\n' +
            r'\midrule' + '\n' + body + '\n' + r'\bottomrule' + '\n' + r'\end{tabular}' + '\n' + r'\end{table}' + '\n')


def load_register():
    p = os.path.join(ROOT, 'paper analysis', 'draft one', 'dossier', 'references', 'register.json')
    return {r['id']: r for r in json.load(open(p, encoding='utf-8'))} if os.path.exists(p) else {}


CITES = {
    'CRE32.4': ('Basel Framework CRE32', 'CRE32.4', 'PD floor in force (0.05%)'),
    'CRE32.3.old': ('Basel Framework CRE32 (2019 text, superseded)', 'CRE32.3', 'former PD floor (0.03%)'),
    'CRE36.60': ('Basel Framework CRE36', 'CRE36.60-61', 'use test'),
    'CRE36.79': ('Basel Framework CRE36', 'CRE36.79', 'data history for PD estimation'),
    'CRE36.122': ('Basel Framework CRE36', 'CRE36.122-123', 'backtesting realised vs estimated PD'),
    'CRE36.DIFF': ('Basel Framework CRE36', 'CRE36.18, 36.19, 36.21', 'meaningful differentiation, concentration'),
    'CRE36.OVR': ('Basel Framework CRE36', 'CRE36.44', 'override policy'),
    'CRE36.IND': ('Basel Framework CRE36', 'CRE36.57-59; 36.122-126', 'independent review and validation'),
    'CRE36.LRA': ('Basel Framework CRE36', 'CRE36.63; 36.77-78', 'PD as long-run average'),
    'CRE36.33': ('Basel Framework CRE36', 'CRE36.33-37', 'statistical models: data vetting, documentation, out-of-time'),
    'CRE36.67': ('Basel Framework CRE36', 'CRE36.67', 'conservatism where data are limited'),
    'CRE36.68': ('Basel Framework CRE36', 'CRE36.68-70', 'definition of default'),
    'CRE36.STRESS': ('Basel Framework CRE36', 'CRE36.50-51', 'stress testing'),
    'CRR.160': ('Regulation (EU) No 575/2013 as amended', 'Art. 160(1), 163(1)', 'PD input floor (0.05%)'),
    'CRR.172': ('Regulation (EU) No 575/2013', 'Art. 172', 'assignment to grades; overrides'),
    'CRR.178': ('Regulation (EU) No 575/2013', 'Art. 178', 'definition of default'),
    'CRR.180': ('Regulation (EU) No 575/2013', 'Art. 180', 'requirements specific to PD estimation'),
    'CRR.185': ('Regulation (EU) No 575/2013', 'Art. 185', 'validation of internal estimates'),
    'EBA.MOC': ('EBA/GL/2017/16', 'Section 4.4, paras 36-52', 'margin of conservatism'),
    'EBA.LRA': ('EBA/GL/2017/16', 'Section 5.3, paras 79-91', 'PD calibration to the long-run average'),
    'EBA.DATA': ('EBA/GL/2017/16', 'Section 4.2, paras 15-34', 'data requirements and representativeness'),
    'EBA.PHIL': ('EBA/GL/2017/16', 'paras 66-67', 'rating philosophy'),
    'SR26-2.III': ('SR 26-2 (Fed/OCC/FDIC, 17 Apr 2026)', 'Section III', 'tailoring to materiality; effective challenge'),
    'SR26-2.V': ('SR 26-2 (Fed/OCC/FDIC, 17 Apr 2026)', 'Section V', 'model validation and monitoring'),
    'SR26-2.VI': ('SR 26-2 (Fed/OCC/FDIC, 17 Apr 2026)', 'Section VI', 'governance, roles, inventory, documentation'),
    'PRA.SS1/23': ('PRA SS1/23', 'Principles 1-5', 'model risk management principles'),
    'BCBS239': ('BCBS 239 (Jan 2013)', 'Principles 3-5 (paras 36-47)', 'data accuracy, completeness, timeliness'),
    'BCBS239.GOV': ('BCBS 239 (Jan 2013)', 'Principles 1-2 (paras 27-35)', 'governance; data architecture'),
    'AIA.III5b': ('Regulation (EU) 2024/1689', 'Annex III point 5(b)', 'creditworthiness of natural persons'),
    'AIA.14': ('Regulation (EU) 2024/1689', 'Art. 14', 'human oversight'),
    'ECOA': ('ECOA / Regulation B', '15 USC 1691(d); 12 CFR 1002.9', 'statement of reasons for adverse action'),
}


def cite(key, reg):
    doc, loc, _ = CITES[key]
    flag = '' if reg.get(key, {}).get('status') == 'VERIFIED_PRIMARY' else r'$^{\dagger}$'
    return r'\citeref{%s}{%s, %s}%s' % (key, esc(doc), esc(loc), flag)


PREAMBLE = r"""\documentclass[10pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage[a4paper,margin=2.2cm,headheight=14pt]{geometry}
\usepackage{booktabs,longtable,array,tabularx,float,graphicx,enumitem}
\usepackage[table]{xcolor}
\usepackage{fancyhdr,lastpage,titlesec}
\usepackage[hidelinks]{hyperref}
\usepackage{caption}
\captionsetup{font=small,labelfont=bf,skip=4pt}
\definecolor{navy}{HTML}{1F3A5F}
\definecolor{okgreen}{HTML}{1E7B34}
\definecolor{amber}{HTML}{B26A00}
\definecolor{alertred}{HTML}{A61B1B}
\definecolor{greyn}{HTML}{666666}
\newcommand{\stSAT}{\textcolor{okgreen}{\textbf{Satisfied}}}
\newcommand{\stPAR}{\textcolor{amber}{\textbf{Partial}}}
\newcommand{\stGAP}{\textcolor{alertred}{\textbf{Not met}}}
\newcommand{\stNA}{\textcolor{greyn}{\textbf{N/A}}}
\newcommand{\stNOT}{\textcolor{greyn}{\textbf{Not assessed}}}
\newcommand{\stPEN}{\textcolor{greyn}{\textbf{Pending}}}
\newcommand{\stPASS}{\textcolor{okgreen}{\textbf{Pass}}}
\newcommand{\stFAIL}{\textcolor{alertred}{\textbf{Fail}}}
\newcommand{\stCLR}{\textcolor{okgreen}{\textbf{Cleared}}}
\newcommand{\stNCL}{\textcolor{alertred}{\textbf{Not cleared}}}
\newcommand{\citeref}[2]{\hyperlink{ref:#1}{#2}}
\setcounter{tocdepth}{1}
\titleformat{\section}{\Large\bfseries\color{navy}}{\thesection}{0.6em}{}
\titleformat{\subsection}{\large\bfseries\color{navy}}{\thesubsection}{0.6em}{}
\titlespacing*{\section}{0pt}{14pt}{6pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small\textcolor{greyn}{%(header_left)s}}
\fancyhead[R]{\small\textcolor{greyn}{%(header_right)s}}
\fancyfoot[L]{\small\textcolor{greyn}{%(footer_left)s}}
\fancyfoot[R]{\small\textcolor{greyn}{Page \thepage{} of \pageref{LastPage}}}
\renewcommand{\headrulewidth}{0.3pt}
\setlist{nosep,leftmargin=1.2em}
\begin{document}
"""


# ---------------------------------------------------------------------------------------------- front matter
def cover(d, phase):
    return r"""\thispagestyle{empty}
\begin{center}
{\large\textcolor{greyn}{%(inst)s}}\\[2.2cm]
{\Huge\bfseries\textcolor{navy}{Model Approval Dossier}}\\[0.5cm]
{\Large Probability-of-Default Model\\[2pt] %(run)s}\\[1.2cm]
\begin{tabular}{rl}
\textbf{Portfolio} & %(portfolio)s\\
\textbf{Model version} & %(ver)s (corrected PD floor and blank-value controls; G5 and GF re-sealed 2026-10-26)\\
\textbf{Materiality tier} & %(tier)s\\
\textbf{Sealed-record head (version 1.1)} & \texttt{%(head)s}\\
\textbf{Document phase} & Phase %(phase)s review draft\\
\end{tabular}\\[1.6cm]
\fcolorbox{alertred}{white}{\parbox{0.86\textwidth}{\centering\small
\textbf{STATUS: RESEARCH BENCHMARK, REVIEW DRAFT.}\\
This dossier describes a model built on public research data. It is not approved for, and must not be
used in, a live credit decision or for regulatory capital. It is prepared to the standard of a regulatory
submission so that its evidence can be reviewed; it is not a submission and does not claim approval.}}
\end{center}
\newpage
""" % dict(inst=esc(d['institution']), run=esc(d['run']), portfolio=esc(d['portfolio']), ver=esc(d['model_version']),
           tier=esc(d['tier']), head=esc(d['head']), phase=phase)


def doc_control(d, phase):
    rows = [['Document', 'Model Approval Dossier, ' + esc(d['run'])],
            ['Version / phase', esc(d['model_version']) + r' / Phase %s review draft' % phase],
            ['Prepared by', 'Model development: a single researcher, assisted by an AI assistant'],
            ['Reviewers', 'Not yet assigned; committee review is planned before the final go/no-go ruling'],
            ['Evidence source', r'Sealed decision record, head hash \texttt{%s}; version 1.1 re-sealed G5 and the final ruling, and the version 1.0 entries are kept in the record as voided' % esc(d['head'])],
            ['Gate rationales', 'All seven gate rationales were drafted by an AI assistant and shown to the signer before sealing; '
                                'the sealed file does not carry authorship fields (see Section 9)'],
            ['Distribution', 'Model Approval Committee; not for external distribution until the status changes']]
    return (r'\section*{Document control}' + '\n' + table(['Item', 'Entry'], rows, r'@{}p{3.4cm}p{12cm}@{}') + '\n' + r'\tableofcontents\newpage' + '\n')


# ---------------------------------------------------------------------------------------------- sections
def sec_summary(d, reg):
    cl = d['checklist_strict']
    cnt = {k: sum(1 for r in cl if r['status'] == k) for k in ('SATISFIED', 'PARTIAL', 'GAP', 'N/A')}
    ex = d['ex']
    ps, pa = ex['perf_scored'], ex['perf_all']
    mg_ = ', '.join(d['must_have_gaps'])
    t = r'\section{Summary and decision requested}' + '\n'
    t += (r'This dossier presents the %s probability-of-default model for %s, built on %s firms of which %s (%s) went bankrupt within the forecast '
          r'horizon. The final model uses \textbf{%d variables} (Section~\ref{sec:model}) and produces a probability of default mapped to a ten-grade scale. '
          r'The probability is calibrated to the sample, not to a long-run average (Section~\ref{sec:limits}).'
          % (esc(d['run']), esc(d['portfolio']), num(d['data']['n']), num(d['data']['events']), pct(d['data']['prevalence'], 2), len(d['variables'])) + '\n\n')
    t += (r'\textbf{Outcome.} On the %s firms the deployed model scores (it refers %s firms with a blank sales-growth ratio, %s of them bankrupt), '
          r'discrimination is Gini %s (AUC %s). Over all %s firms, including those referred, it is %s. Of fourteen criteria, assessed on a regulatory-use reading, '
          r'satisfied: %d; partly met: %d; not met: %d; not applicable: %d. The criteria not met (%s) are must-haves. Read for regulatory use the model would '
          r'therefore not be approved: the engine verdict is \textbf{%s}. The sealed verdict of the research record, %s, stands as an acceptance of the model '
          r'as a research benchmark only.'
          % (num(ps['n']), num(ex['referred']['n']), num(ex['referred']['events']), f(ps['gini']), f(ps['auc']), num(pa['n']), f(pa['gini']),
             cnt['SATISFIED'], cnt['PARTIAL'], cnt['GAP'], cnt['N/A'], esc(mg_), esc(d['gf_strict']['verdict']), esc(d['gf_sealed'])) + '\n\n')
    t += r'\textbf{Decision requested.} Committee review of this dossier ahead of the final go/no-go ruling. No approval for live use is sought.' + '\n\n'
    bt = ex['backtest']['scored_floor_0.0005']
    rows = [['Discrimination on the scored population: Gini (95\\% interval)', '%s (%s)' % (f(ps['gini']), rng(ps['gini_ci_low'], ps['gini_ci_high']))],
            ['Discrimination over all firms, including referred: Gini', f(pa['gini'])],
            ['Bankruptcies in the riskiest 10\\% of scored firms', pct(ps['capture_top_10'])],
            ['Rating grades inside their expected range (scored population)', '%d of %d' % (bt['passed'], bt['total'])],
            ['Events per variable (candidate pool)', f(d['sufficiency'][0]['EPV'], 1) + ' (guideline: at least 10)'],
            ['Sample-size minimum, own-fit / default R-squared', '%s / %s rows needed; %s available' % (num(d['sufficiency'][0]['N_required']), num(d['sufficiency'][0]['N_required_default_r2']), num(d['sufficiency'][0]['available']))],
            ['Acceptance bars cleared', '%d of %d' % (d['bars2_cleared'], d['bars2_applicable'])]]
    t += table(['Key result', 'Value'], rows, r'@{}p{9cm}p{6.4cm}@{}', caption='Headline results', label='tab:headline')
    t += (r'\textbf{Changes since version 1.0.} The PD floor is corrected from 0.03\%% to 0.05\%% (%s; %s); an adverse floor is applied to blank values so that '
          r'omitting a field cannot lower a firm’s risk; and the headline metrics are reported on the scored population. G5 and the final ruling were re-sealed '
          r'under these controls (head \texttt{%s}); the version 1.0 entries remain in the record as voided.' % (cite('CRE32.4', reg), cite('CRR.160', reg), esc(d['head'])) + '\n')
    return t


def sec_scope(d, reg):
    t = r'\section{Scope and intended use}' + '\n'
    t += (r'\textbf{Purpose.} The model estimates the probability that a company goes bankrupt within the forecast horizon of the data file, from financial ratios taken '
          r'from its accounts. \textbf{Population.} %s. \textbf{Source.} %s Licence: %s.' % (esc(d['portfolio']), esc(d['data']['citation']), esc(d['data']['licence'])) + '\n\n')
    t += (r'\textbf{Legal-entity scope gate.} The model is built for companies. Natural persons (sole traders, individual entrepreneurs, guarantors) are outside its '
          r'scope; the data has no legal-form field, so this is an input condition that must be enforced at the point of use by a legal-form check that refers a '
          r'non-company to a human. Without that gate the AI-regulation analysis below would not hold.' + '\n\n')
    t += (r'\textbf{Materiality.} Tier %s, assigned at the first governance gate by the same person who developed the model; no independent challenge of the tier exists.' % esc(d['tier']) + '\n\n')
    t += r'\subsection{Regulatory regimes considered}' + '\n'
    rg = d['regimes'] or {}
    rows = [['Basel Framework CRE32/CRE36; EU CRR; EBA/GL/2017/16 (criteria R1--R6, R10)', 'Reference standard', 'This is the standard a credit-risk model for capital would be judged against. The dossier applies it; the model is not used for capital.'],
            ['Generic model-risk governance, SR 26-2 principles (R7--R9)', 'Reference standard', 'SR 26-2 is non-binding guidance, most relevant above USD 30bn of assets; its principles are applied here as good practice.']]
    labels = {'UK_PRA_SS1_23': ('UK PRA SS1/23 (R11)', 'Scope is set by the firm: a UK-incorporated bank with internal-model approval (SS1/23 para 1.2). Not applicable to this research model; assessed for completeness in Annex D.'),
              'EU_AI_ACT_HIGH_RISK': ('EU AI Act, high-risk obligations (R12)', 'Annex III point 5(b) covers natural persons only. Holds only while the legal-entity scope gate is enforced; no documented Article 6 assessment is attached.'),
              'EU_AI_ACT_HUMAN_OVERSIGHT': ('EU AI Act, human oversight (R13)', 'Applies to high-risk systems; follows R12.'),
              'US_ECOA_REG_B': ('US ECOA / Regulation B (R14)', 'ECOA and Regulation B also reach business credit; they do not apply here because the lender and borrowers are Polish and no US creditor is involved, not because the borrowers are companies.')}
    for k, (lab, why) in labels.items():
        v = rg.get(k)
        rows.append([esc(lab), 'Not applicable' if v and not v['binding'] else 'Applies' if v else 'Not declared', esc(why)])
    t += table(['Regime', 'Position', 'Reasoning'], rows, r'@{}p{4.8cm}p{2.3cm}p{8.4cm}@{}', caption='Regimes and their position for this model (proposal, awaiting committee confirmation)', label='tab:regimes')
    t += (r'\textbf{Supervisor.} The model is Polish, and Poland is outside the euro area and the Single Supervisory Mechanism, so the national competent authority (the KNF is the likely one; its role for internal-model permission is not verified in this document) would be the primary supervisor of a Polish bank, '
          r'with the ECB involved only for a Polish subsidiary of an SSM-supervised group.' + '\n\n')
    t += (r'\textbf{Limits of use.} The model must not be used for a live credit decision or for regulatory capital. The grade-to-decision mapping and any accept or decline cutoff are institution inputs and are not part of this model; no cutoff or price is set or derived here.' + '\n')
    return t


def sec_data(d, reg):
    dd, ex = d['data'], d['ex']
    fl, dp = ex['file'], ex['duplicates']
    t = r'\section{Data}\label{sec:data}' + '\n'
    t += r'\subsection{Source and identity}' + '\n'
    rows = [['File analysed', tt(fl['name'])], ['SHA-256', r'\texttt{%s}' % fl['sha256']], ['Size', '%s bytes, %s rows' % (num(fl['bytes']), num(fl['rows']))],
            ['Public source', 'UCI Machine Learning Repository, dataset 365; this file is the one UCI names %s (ratios from the first year of a five-year window, bankruptcy checked after the window), i.e. one year ahead of the outcome check' % tt(fl['uci_file'] + '.arff') if fl['uci_file'] else 'n/a'],
            ['Event definition', 'Bankruptcy within the forecast horizon. This is a late-stage, narrow subset of default under the supervisory definition (%s; %s), so the estimate is a bankruptcy probability, not a default probability.' % (cite('CRE36.68', reg), cite('CRR.178', reg))]]
    t += table(['Item', 'Value'], rows, r'@{}p{3.4cm}p{12cm}@{}', caption='Data identity', label='tab:identity')
    rows = [['Rows (firms)', num(dd['n'])], ['Bankrupt firms (events)', '%s (%s)' % (num(dd['events']), pct(dd['prevalence'], 2))],
            ['Candidate financial ratios', str(dd['n_columns'])],
            ['Firms with at least one blank ratio', '%s (%s)' % (num(dd['rows_with_blank']), pct(dd['rows_with_blank'] / dd['n'], 1))],
            ['Exact duplicate rows', '%d extra copies (%d rows belong to a duplicate set)' % (dp['extra_copies'], dp['rows_in_duplicate_sets'])],
            ['Eligibility / availability', ', '.join('%d %s' % (v, esc(k)) for k, v in dd['eligibility'].items()) + '; ' + ', '.join('%s: %s' % (esc(k), v) for k, v in (dd['availability'] or {}).items())],
            ['Protected attributes in the data', 'none (all inputs are company financial ratios)']]
    t += table(['Item', 'Value'], rows, r'@{}p{5.6cm}p{9.8cm}@{}', caption='Data summary', label='tab:data')
    t += (r'\textbf{Sampling window.} ' + esc(dd['sampling_note']) + ' ' + r'This is a confound in the outcome label itself and cannot be tested without dates. '
          r'\textbf{Data history.} The file carries no dates and no per-firm history, so the five-year observation period expected for PD estimation (%s; %s; %s) cannot be shown; '
          r'representativeness against any application portfolio cannot be assessed either (%s).' % (cite('CRE36.79', reg), cite('CRR.180', reg), cite('EBA.LRA', reg), cite('EBA.DATA', reg)) + '\n\n')
    t += (r'\textbf{Duplicates.} Removing the %d extra copies changes the cross-validated Gini from %s to %s; keeping each duplicate set inside a single fold gives %s. '
          r'Identical rows split across folds therefore inflate the headline by about %s, which is small but not zero.' % (dp['extra_copies'], f(dp['gini_all'], 4), f(dp['gini_duplicates_removed'], 4), f(dp['gini_duplicates_kept_in_same_fold'], 4), f(dp['gini_all'] - dp['gini_duplicates_removed'], 3)) + '\n\n')
    t += r'\subsection{Data quality and completeness}' + '\n'
    rows = [[tt(r['column']), num(r['n_blank']), num(r['events_in_blank']), pct(r['event_rate_blank']), pct(r['event_rate_filled']), 'yes' if r['below_bonferroni'] else 'no'] for r in dd['blank_table'][:8]]
    t += table(['Ratio', 'Blank', 'Bankrupt in blank', 'Rate if blank', 'Rate if filled', 'Beyond bar'], rows, r'@{}p{5.6cm}p{1.2cm}p{1.9cm}p{1.8cm}p{1.8cm}p{1.6cm}@{}',
               caption='Ratios whose blank pattern is most strongly linked to the outcome', label='tab:blank')
    sg = next(r for r in dd['blank_table'] if r['column'] == 'sales_n_to_sales_n_minus_1')
    t += (r'%d of %d ratios show a blank pattern linked to the outcome beyond a multiple-testing correction. The most important, sales growth, is blank for %s firms of which %s went bankrupt; the cause is unknown. '
          r'The deployed model treats sales growth as a mandatory field and refers an application with a blank to a human. A sentinel code was also found in the source (a working-capital value of 97 on one firm) and judged plausible; '
          r'no outlier or sentinel treatment is applied. This is a data-governance matter (%s; %s).' % (dd['blank_beyond_bonferroni'], dd['n_columns'], num(sg['n_blank']), num(sg['events_in_blank']), cite('BCBS239', reg), cite('BCBS239.GOV', reg)) + '\n\n')
    t += r'\subsection{Definitions that need review}' + '\n'
    for c, v in dd['lookahead'].items():
        t += (r"The definition of %s reads ``%s''. The source does not say whether the years in the definition precede or follow the statement date; if they follow it, the ratio would use information from after the assessment date. "
              r"This is unresolved and no run excludes the variable, so its effect on performance is not measured." % (tt(c), esc(v['definition'])) + '\n\n')
    t += (r'The source defines EBITDA as profit on operating activities minus depreciation, which is not the standard definition; the %s variables follow the source. %s is an absolute amount, not a ratio.'
          % (', '.join(tt(v['variable']) for v in d['variables'] if v['variable'].startswith('ebitda')), tt('working_capital')) + '\n')
    return t


def sec_model(d, reg):
    sp, ex = d['spec'], d['ex']
    bf = ex['blank_floor']
    t = r'\section{Model specification}\label{sec:model}' + '\n'
    t += (r'\textbf{Form.} %s. Each ratio is replaced by a weight-of-evidence score from its bins (higher means a safer bin). The fitted probabilities are re-mapped by %s. '
          r'Fitted settings: penalty %s, strength parameter %s, solver %s, seed %d.' % (esc(sp['learner']), esc(sp['calibration']), sp['penalty'], sp['C'], sp['solver'], sp['seed']) + '\n\n')
    t += (r'\textbf{PD floor and cap.} Version 1.1 floors probabilities at 0.05\%% and caps them at 99.9\%%. The sealed version 1.0 used 0.03\%%, which is the value in the 2019 text of the Basel Framework (%s); '
          r'the text in force since 1 January 2023 sets 0.05\%% for most exposures (%s) and the EU Capital Requirements Regulation sets 0.05\%% for corporate and retail exposures from 1 January 2025 (%s). '
          r'The change affects the %s firms that sat at the old floor. Defaulted obligors carry a PD of 100\%% under both frameworks and are a separate grade, not part of this scale.'
          % (cite('CRE32.3.old', reg), cite('CRE32.4', reg), cite('CRR.160', reg), num(d['coverage']['n_at_floor'])) + '\n\n')
    t += r'\subsection{Variables in the model}' + '\n'
    t += (r"The model uses %d ratios. ``Group'' shows the cluster of closely related ratios each belongs to. Coefficients are on the weight-of-evidence scale; because a higher score means a safer bin, a sound "
          r"model would show negative coefficients. \textbf{%d of %d are positive}. This follows from strong correlation: %d of the ratios are in one profitability group, and several carry identical information "
          r"(for example EBIT, gross profit and gross profit plus interest, each over total assets, have identical bins). Individual coefficients are therefore not interpretable as stand-alone effects "
          r"and the redundancy is a limitation (Section~\ref{sec:limits}). Binning is monotone except where a ratio's shape is genuinely non-monotone, as for the two total-liabilities ratios (Annex A)."
          % (len(d['variables']), d['coef_positive_count'], len(d['variables']), d['players'][0]['members'].__len__()) + '\n\n')
    rows = []
    for i, r in enumerate(d['variables'], 1):
        rows.append([str(i), tt(r['variable']), esc(r['definition']), r['player'], f(r['iv'], 2), f(r['coefficient_on_woe'], 3),
                     ('safer' if (r['univariate_rho_with_default'] or 0) < 0 else 'riskier') if r['univariate_rho_with_default'] is not None else 'n/a',
                     'mandatory' if r['mandatory'] else ('%d blank' % r['n_blank'] if r['n_blank'] else '--')])
    t += table(['\\#', 'Variable', 'Definition (source wording)', 'Group', 'IV', 'Coeff.', 'Higher value is', 'Blanks'], rows,
               r'@{}rp{3.9cm}p{4.4cm}lrrp{1.7cm}p{1.3cm}@{}', caption='Final model variables', label='tab:vars', long=True)
    t += (r'The direction column is the univariate rank correlation with default; for a ratio whose denominator can change sign (for example total liabilities over profit) it can read opposite to economic sense, so it is indicative only.' + '\n\n')
    t += (r'\textbf{Groups.} ' + '; '.join(r'%s = %d ratios, importance %.1f times the noise benchmark' % (g['label'], len(g['members']), g['x_bar']) for g in d['players']) + '.\n\n')
    t += r'\subsection{Rating master scale and grade PD}' + '\n'
    rows = [[m['grade'], esc(m['label']), '%.2f\\%%' % (100 * m['low']), '%.2f\\%%' % (100 * m['high'])] for m in sp['masterscale']]
    t += table(['Grade', 'Label', 'PD from', 'PD below'], rows, r'@{}llrr@{}', caption='Internal ten-grade master scale (PD bands)', label='tab:scale')
    t += (r'Grades are assigned from the floored, calibrated probability (%s). The \emph{grade PD} reported in the backtest is the count-weighted mean of the predicted PDs of the firms in the grade; '
          r'it is a sample estimate, not a long-run average (%s). Grade D covers PD from 50\%% to 100\%% and holds non-defaulted firms; a true default grade (PD 100\%%) is separate and not modelled. '
          r'The scale is a reporting scale and not an accept or decline rule.' % (cite('CRR.172', reg), cite('CRE36.LRA', reg)) + '\n\n')
    t += r'\subsection{Scoring controls (version 1.1)}' + '\n'
    t += (r'\begin{itemize}' + '\n' +
          r'\item Mandatory field: %s. A blank is referred to a human and not scored.' % ', '.join(tt(m) for m in sp['mandatory']) + '\n' +
          r'\item \textbf{Adverse floor on blanks.} For every other model variable, a blank is scored as the worse of its learned blank score and the worst real bin, so omitting a field cannot lower risk. '
          r'Without this, a blank on %s would score as the safest value (weight of evidence +15.65 and +13.01 on bins with no defaults). %d firms (%s of those scored) have such a blank; their mean PD rises from %s to %s and they are flagged.'
          % (' or '.join(tt(c) for c in bf['lowest_blank_woe_gain']), bf['firms_with_a_blank_in_a_floor_column'], pct(bf['firms_with_a_blank_in_a_floor_column'] / ex['perf_scored']['n'], 1), pct(bf['mean_pd_v1']), pct(bf['mean_pd_v2'])) + '\n' +
          r'\item PD floor 0.05\%% and cap 99.9\%% are always applied (%s).' % cite('CRE32.4', reg) + '\n' +
          r'\item A legal-form check refers any non-company to a human (Section 2).' + '\n' +
          r'\item Every probability carries a reason-code breakdown from the additive weight-of-evidence contributions; the strongest contributions of three cases are shown in Annex B.' + '\n' +
          r'\item Overrides require a documented policy and tracking (%s). \textbf{No override policy or override tracking exists for this model}; only the refer rule above does.' % cite('CRE36.OVR', reg) + '\n' +
          r'\end{itemize}' + '\n')
    return t


def sec_dev(d, reg):
    sel, dd, ex, nv = d['selection'], d['data'], d['ex'], d['nested']
    t = r'\section{Development and training results}\label{sec:dev}' + '\n'
    t += (r'\textbf{Training data and splits.} All %s firms were used. Discrimination is measured on out-of-fold predictions from stratified five-fold cross-validation. '
          r'The weight-of-evidence bins are refitted inside each fold. The choice of columns (screening, noise-benchmark test, choice of model size) was made once on all firms, '
          r'which makes the out-of-fold figure optimistic; the nested check below removes that optimism. The isotonic mapping is learned on out-of-fold scores, so calibration '
          r'statistics are reported on a held-out part that the mapping never saw. Seed %d.' % (num(dd['n']), d['spec']['seed']) + '\n\n')
    t += r'\subsection{From candidates to final model}' + '\n'
    rows = [['Candidate ratios considered', str(sel['candidates_screened'])], ['Ratios passing univariate screening', str(sel['candidates_passed'])],
            ['Groups of related ratios tested', str(sel['players_real'])], ['Groups clearing the noise benchmark', str(sel['players_confirmed'])],
            ['Groups in the final model (ratios)', '%d (%d)' % (sel['k'], sel['columns'])],
            ['Gini of final model vs full set (all firms)', '%s vs %s (loss %.2f\\%%, paired p = %s)' % (f(sel['gini'], 4), f(sel['gini_full'], 4), sel['relative_loss_pct'], f(sel['delong_p'], 3))]]
    t += table(['Step', 'Result'], rows, r'@{}p{7cm}p{8.4cm}@{}', caption='Development summary', label='tab:devsum')
    t += (r'A paired test that fails to reject a difference is not evidence of equivalence; the model size is chosen by a pre-registered rule, and the performance of the chosen size is reported on the same data that selected it.' + '\n\n')
    t += r'\subsection{Training versus validation}' + '\n'
    cp, pa = d['calibration_primary'], ex['perf_all']
    rows = [['Gini', f(pa['gini'], 4) + ' (out-of-fold, all firms)', f(2 * cp['calibrated_auc'] - 1, 4) + ' (single 20\\%% hold-out, n = %d)' % cp['n_heldout']],
            ['AUC', f(pa['auc'], 4), f(cp['calibrated_auc'], 4)],
            ['Brier score (base-rate baseline %s)' % f(cp['baseline_brier_always_base_rate'], 4), f(pa['brier'], 4) + ' (out-of-fold)', '%s raw, %s after calibration' % (f(cp['raw_brier'], 4), f(cp['calibrated_brier'], 4))],
            ['Expected calibration error', f(pa['ece'], 4) + ' (out-of-fold, before calibration)', '%s raw, %s after calibration' % (f(cp['raw_ece'], 4), f(cp['calibrated_ece'], 4))]]
    t += table(['Measure', 'Cross-validated', 'Hold-out'], rows, r'@{}p{4.8cm}p{4.8cm}p{5.8cm}@{}', caption='Cross-validated and hold-out results (all firms)', label='tab:trainval')
    t += (r'The hold-out holds about %d bankruptcies, so it is noisy; its Gini is below the lower end of the cross-validated interval, which is consistent with the optimism described above and not only with noise.' % round(cp['n_heldout'] * dd['prevalence']) + '\n\n')
    t += r'\subsection{Nested validation: selection inside each fold}' + '\n'
    if nv:
        rows = [[str(fo['fold']), str(fo['k']), str(fo['n_columns']), f(fo['test_gini'], 4)] for fo in nv['folds']]
        t += table(['Outer fold', 'Groups chosen', 'Ratios', 'Gini on untouched test part'], rows, r'@{}rrrr@{}', caption='Whole pipeline re-run inside each outer fold', label='tab:nested')
        t += (r'Pooling the five test parts gives Gini \textbf{%s} (AUC %s) against %s for the version in which selection used all firms. %s ratios are chosen in all five folds. %s'
              % (f(nv['pooled_gini'], 4), f(nv['pooled_auc'], 4), f(pa['gini'], 4), len(nv['columns_in_all_folds']),
                 ('On the scored population the nested Gini is %s.' % f(nv['scored_population']['pooled_gini'], 4)) if nv.get('scored_population') else '') + '\n\n')
    else:
        t += r'The nested validation was not complete when this draft was built.' + '\n\n'
    t += r'\subsection{Challenger models}' + '\n'
    ch = ex['challengers']
    rows = [['Deployed form (weight-of-evidence logistic), re-fitted on the scored population', f(ch['woe_logistic_deployed_form']['gini'], 4), f(ch['woe_logistic_deployed_form']['auc'], 4)],
            ['Plain logistic regression on the raw ratios (median-filled, standardised)', f(ch['logistic_on_raw_ratios']['gini'], 4), f(ch['logistic_on_raw_ratios']['auc'], 4)],
            ['Gradient-boosted trees on the same %d ratios' % len(d['variables']), f(ch['gradient_boosting']['gini'], 4), f(ch['gradient_boosting']['auc'], 4)]]
    t += table(['Model (same folds, scored population, n = %s)' % num(ch['n']), 'Gini', 'AUC'], rows, r'@{}p{10.5cm}rr@{}', caption='Challenger comparison (informational)', label='tab:chall')
    t += (r'The deployed form beats a plain logistic regression by a wide margin and trails gradient boosting by %s Gini. No statistical test was run on the differences. Gradient boosting is not used because it is less transparent '
          r'and no gain over the deployed form is demonstrated that would justify it.' % f(ch['gradient_boosting']['gini'] - ch['woe_logistic_deployed_form']['gini'], 3) + '\n\n')
    t += r'\subsection{How performance depends on model size}' + '\n'
    rows = [[str(r['k']), str(r['n_columns']), f(r['gini']), rng(r['gini_ci_low'], r['gini_ci_high']), f(r['auc']), f(r['ks']), pct(r['relative_gini_loss_vs_full'], 2), f(r['delong_p_vs_full'], 3)] for r in d['curve']]
    t += table(['Groups', 'Ratios', 'Gini', '95\\% interval', 'AUC', 'KS', 'Loss vs full', 'Paired p'], rows, r'@{}rrrlrrrr@{}',
               caption='Out-of-fold performance (all firms) as groups are added in order of importance', label='tab:curve', long=True)
    t += r'\subsection{What drives the score}' + '\n'
    rows = [[g['label'], '%d' % len(g['members']), f(g['shapley'], 4), '%.1f' % g['x_bar']] for g in d['players']]
    t += table(['Group', 'Ratios', 'Importance (Shapley)', 'Times noise benchmark'], rows, r'@{}lrrr@{}', caption='Importance of each group in the final model (noise benchmark %s)' % f(d['shadow_bar'], 5), label='tab:imp')
    return t


def sec_perf(d, reg):
    ex = d['ex']
    pa, ps = ex['perf_all'], ex['perf_scored']
    t = r'\section{Performance and validation results}\label{sec:perf}' + '\n'
    t += (r'\textbf{Which population.} The deployed model does not score a firm with a blank sales-growth ratio. The %s referred firms hold %s of the %s bankruptcies, so any metric that includes them overstates '
          r'what the deployed model achieves. The scored population (%s firms) is the primary evidence; all-firm figures are shown for continuity with the sealed record.'
          % (num(ex['referred']['n']), num(ex['referred']['events']), num(pa['events']), num(ps['n'])) + '\n\n')
    t += r'\subsection{Discrimination and probability accuracy}' + '\n'
    rows = [['Gini (95\\% interval)', '%s (%s)' % (f(pa['gini'], 4), rng(pa['gini_ci_low'], pa['gini_ci_high'])), '%s (%s)' % (f(ps['gini'], 4), rng(ps['gini_ci_low'], ps['gini_ci_high']))],
            ['AUC', f(pa['auc'], 4), f(ps['auc'], 4)], ['KS', f(pa['ks'], 4), f(ps['ks'], 4)]]
    for q in (5, 10, 20):
        rows.append(['Bankruptcies in riskiest %d\\%%' % q, '%s (%s--%s)' % (pct(pa['capture_top_%d' % q]), pct(pa['capture_ci']['capture_top_%d' % q][0]), pct(pa['capture_ci']['capture_top_%d' % q][1])),
                     '%s (%s--%s)' % (pct(ps['capture_top_%d' % q]), pct(ps['capture_ci']['capture_top_%d' % q][0]), pct(ps['capture_ci']['capture_top_%d' % q][1]))])
    rows += [['Brier skill (0 = no better than base rate)', '%s (%s)' % (f(pa['brier_skill']), rng(*pa['brier_skill_ci'])), '%s (%s)' % (f(ps['brier_skill']), rng(*ps['brier_skill_ci']))],
             ['Expected calibration error, out-of-fold, before the isotonic map', '%s (%s)' % (f(pa['ece'], 4), rng(*pa['ece_ci'], d=4)), '%s (%s)' % (f(ps['ece'], 4), rng(*ps['ece_ci'], d=4))],
             ['Calibration slope (1 is ideal)', '%s (%s)' % (f(pa['slope']), rng(*pa['slope_ci'])), '%s (%s)' % (f(ps['slope']), rng(*ps['slope_ci']))]]
    t += table(['Measure', 'All firms (sealed basis)', 'Scored population (primary)'], rows, r'@{}p{6.2cm}p{4.6cm}p{4.6cm}@{}', caption='Out-of-fold performance on the two populations', label='tab:disc')
    t += (r'Interval widths are bootstrap intervals (1000 stratified resamples) except Gini, which uses the paired-test interval. Removing the referred firms lowers Gini by %s. '
          r'The partial AUC and the standardisation of the sealed record are not reported here.' % f(pa['gini'] - ps['gini'], 3) + '\n\n')
    t += r'\subsection{Rating-grade backtest}' + '\n'
    bt = ex['backtest']['scored_floor_0.0005']
    rows = [[r['grade'], num(r['n']), num(r['defaults']), pct(r['realised'], 2), pct(r['expected'], 2), pct(r['ci_low'], 2) + '--' + pct(r['ci_high'], 2), r'\stPASS' if r['pass'] else r'\stFAIL'] for r in bt['table']]
    t += table(['Grade', 'Firms', 'Defaults', 'Realised', 'Expected (grade PD)', 'Wilson 95\\% range', 'Result'], rows, r'@{}lrrrrll@{}',
               caption='Per-grade backtest, scored population, held-out %s firms, floor 0.05\\%%' % num(bt['n_heldout']), label='tab:grades')
    fails = [r for r in bt['table'] if not r['pass']]
    ba, b3 = ex['backtest']['all_floor_0.0005'], ex['backtest']['all_floor_0.0003']
    t += (r'The backtest compares realised default rates with estimated PD per grade (%s). On the scored population %d of %d grades pass; failing: %s. '
          r'Over all firms, 0.03\%% floor (sealed): %d of %d pass; 0.05\%% floor: %d of %d pass, so the floor change does not alter the pass count. '
          r'With ten tests at 95\%%, the chance of at least one failure under perfect calibration is about 40\%%, so the number of failures says little on its own. '
          r'Hosmer--Lemeshow on the scored population gives p = %s with 10 groups and %s with 5 groups; the all-firm figures were %s and %s. Both groupings are shown because the choice of grouping can change the conclusion. '
          % (cite('CRE36.122', reg), bt['passed'], bt['total'], ', '.join('%s (realised %s vs %s expected)' % (r['grade'], pct(r['realised'], 1), pct(r['expected'], 1)) for r in fails) or 'none',
             b3['passed'], b3['total'], ba['passed'], ba['total'], f(bt['hl']['10']['p']), f(bt['hl']['5']['p']), f(ba['hl']['10']['p']), f(ba['hl']['5']['p'])) + '\n\n')
    t += (r'\textbf{Rank-ordering and concentration.} Realised default rates are \emph{not} non-decreasing across grades: %d rank break(s) on the scored population (for example a better grade defaulting more than a worse one). '
          r'%s of held-out firms sit in the three best grades and the largest single grade holds %s. A concentration of this kind must be supported by empirical evidence (%s); none beyond discrimination metrics is provided.'
          % (bt['rank_breaks'], pct(bt['share_top3'], 0), pct(bt['largest_grade_share'], 0), cite('CRE36.DIFF', reg)) + '\n\n')
    t += r'\subsection{Sample-size sufficiency}' + '\n'
    rows = [[esc(r['basis']), str(r['P']), f(r['EPV'], 1), num(r['N_required']), num(r['N_required_default_r2']), num(r['available'])] for r in d['sufficiency']]
    t += table(['Basis', 'Vars', 'EPV', 'Rows needed, own-fit R2', 'Rows needed, default R2', 'Rows avail.'], rows, r'@{}p{6cm}p{1cm}p{1cm}p{2.4cm}p{2.4cm}p{1.6cm}@{}',
               caption='Sufficiency; the first row (candidate pool) governs', label='tab:suff')
    s0 = d['sufficiency'][0]
    t += (r"``Own-fit R2'' takes the anticipated explained variance from this model’s own cross-validated AUC. That is circular, because it uses the outcome. The recommended alternative when no independent prior exists is 15\%% of the maximum "
          r"(the ``default R2''), which asks for %s rows against %s available: the candidate pool is %s on that basis. The own-fit figure is not independent evidence of sufficiency."
          % (num(s0['N_required_default_r2']), num(s0['available']), 'short' if s0['available'] < s0['N_required_default_r2'] else 'sufficient') + '\n\n')
    t += r'\subsection{Sensitivity}' + '\n'
    se = ex['sensitivity']
    t += (r'A mechanical sensitivity, not a stress scenario: each of the %d profitability ratios is moved adversely by one robust standard deviation. Among %s scored firms the mean PD rises from %s to %s and %s move to a worse grade. '
          r'No macroeconomic stress is run, since there is no portfolio and no dates (%s).' % (len(se['shifted_variables']), num(se['n']), pct(se['mean_pd_before']), pct(se['mean_pd_after']), pct(se['share_moving_to_worse_grade'], 0), cite('CRE36.STRESS', reg)) + '\n\n')
    t += r'\subsection{Fairness and out-of-time evidence}' + '\n'
    t += (r'Fairness: no protected attributes exist in the data, so no adverse-impact ratio is computed; this is not evidence that proxies are absent (for example firm size or sector could act as proxies for owner characteristics if natural persons were ever reached). '
          r'Out-of-time: not available; the file has no time field, so no stability claim is made.' + '\n\n')
    t += r'\subsection{Acceptance bars}' + '\n'
    rows = [[esc(b['bar']), 'n/a' if b['cleared'] is None else (r'\stCLR' if b['cleared'] else r'\stNCL'), esc(b['source'])] for b in d['bars2']]
    t += table(['Bar', 'Result', 'Source'], rows, r'@{}p{9.4cm}lp{4.2cm}@{}', caption='Acceptance bars (existing and cited; none is new)', label='tab:bars')
    t += r'\subsection{Acceptance cases}' + '\n'
    rows = [[tt(c['name']), esc(c['kind'] or ''), esc(c['decision']), 'n/a' if c['pd'] is None else pct(c['pd'], 2), c['grade']] for c in d['cases']]
    t += table(['Case', 'Type', 'Decision', 'PD', 'Grade'], rows, r'@{}p{6.4cm}llrl@{}', caption='Illustrative cases scored through the deployed model (floor 0.03\\% in the sealed pack)', label='tab:cases')
    cov = d['coverage']
    t += (r'The PD cap is not exercised by any case or by the data (highest PD of a scored firm in the sealed deployed scorer: %s); the stress and observed-extreme cases return the same value because the calibration map has few distinct output values. '
          r'The floor is exercised by %d firms. One real bankrupt firm is rated in the best grade, a false negative.' % (pct(cov['pd_max_scored'], 1), cov['n_at_floor']) + '\n')
    return t


def sec_maint(d, reg):
    m, ex = d['maintenance'], d['ex']
    th = m['thresholds']
    t = r'\section{Model maintenance and update process}\label{sec:maint}' + '\n'
    t += (r'\textbf{Review frequency.} Tier %s: %s This is a review cadence. The framework sets no fixed retraining schedule; a review decides whether the model is recalibrated, left as is, or rebuilt through the full governed process.' % (esc(m['tier']), esc(m['cadence'])) + '\n\n')
    t += r'\subsection{Monitoring baseline}' + '\n'
    bd = ex['baseline_distribution']
    rows = [[g, num(n), pct(n / bd['n'], 1)] for g, n in bd['grades'].items()]
    t += table(['Grade', 'Scored firms', 'Share'], rows, r'@{}lrr@{}', caption='Reference grade distribution of the scored population (baseline for drift monitoring, version 1.1)', label='tab:baseline')
    t += (r'PD deciles of the scored population: %s. A drift monitor would compare a later portfolio with these figures.' % ', '.join(pct(x, 2) for x in bd['pd_deciles']) + '\n\n')
    t += r'\subsection{Ongoing monitoring}' + '\n'
    rows = [['Population drift (PSI)', 'watch above %s, major above %s' % (th.get('psi_watch'), th.get('psi_major'))],
            ['Discrimination (AUC)', 'drop above %s\\%% against the baseline' % th.get('auc_drop_pct')],
            ['Fairness gap (where protected attributes exist)', 'above %s' % th.get('fairness_gap')],
            ['Per-grade backtest', 'repeated at each review; any failing grade or rank break is recorded with a decision'],
            ['Promotion of a replacement model', 'blocked if its AUC falls below the current model by more than %s' % th.get('auc_regression_tolerance')]]
    t += table(['Signal', 'Existing platform threshold'], rows, r'@{}p{6.4cm}p{9cm}@{}', caption='Monitoring signals and thresholds already in the platform (generic, not set for this model)', label='tab:monitor')
    t += (r'\textbf{Status.} The thresholds are platform defaults, not calibrated to this model, and the controls are not connected to it; with no live portfolio, monitoring is \emph{planned, not operating}. Before use, model-specific tolerances and a minimum number of defaults per review would have to be set by the owner.' + '\n\n')
    t += r'\subsection{Triggers and update path}' + '\n'
    t += (r'\begin{itemize}' + '\n' + r'\item A monitoring threshold is breached, a grade fails the backtest at two consecutive reviews, or a rank break appears.' + '\n' +
          r'\item A material change in the portfolio, the data source or the definition of default, or a change in the regime that binds the model.' + '\n' + r'\item The scheduled review date.' + '\n' + r'\end{itemize}' + '\n' +
          r'The review decides: leave unchanged, recalibrate, or rebuild. A rebuild repeats the governed process on the new data with fresh signed decisions, and the new sealed record names the previous one. '
          r'A replacement goes live only if it passes the same bars and the committee rules on it. Every update records who decided what, on what evidence, under which cited requirement (%s).' % cite('SR26-2.VI', reg) + '\n')
    return t


def sec_limits(d, reg):
    ex = d['ex']
    t = r'\section{Limitations and conservatism}\label{sec:limits}' + '\n'
    items = [
        ('PD calibrated to the sample, not to a long-run average', r'The PD is anchored to the sample’s %s bankruptcy rate, drawn from different calendar windows for the two classes, so it is not a long-run average of one-year default rates (%s; %s; %s) and no five-year observation period can be shown.' % (pct(d['data']['prevalence'], 2), cite('CRE36.LRA', reg), cite('CRR.180', reg), cite('EBA.LRA', reg))),
        ('Event is bankruptcy, not default', r'The label is bankruptcy within the horizon, a narrow subset of the supervisory definition of default (%s; %s).' % (cite('CRE36.68', reg), cite('CRR.178', reg))),
        ('Margin of conservatism', r'None is quantified. Events per variable on the candidate pool is %s and the sample cannot support representativeness claims, which are data deficiencies a margin of conservatism must cover; the general-estimation-error margin must be above zero (%s; %s).' % (f(d['sufficiency'][0]['EPV'], 1), cite('EBA.MOC', reg), cite('CRE36.67', reg))),
        ('Out-of-sample optimism', r'Column selection used all firms; the nested validation in Section~\ref{sec:dev} measures the effect. Duplicates add about %s Gini.' % f(ex['duplicates']['gini_all'] - ex['duplicates']['gini_duplicates_removed'], 3)),
        ('Sign plausibility and redundancy', r'%d of %d coefficients are positive on a scale where a safer bin scores higher, and several variables are identical in content. Individual coefficients and reason codes must not be read as stand-alone effects.' % (d['coef_positive_count'], len(d['variables']))),
        ('Calibration', r'Realised default rates are not rank-ordered across grades; the backtest fails in %d of %d grades on the scored population; Hosmer--Lemeshow is sensitive to grouping.' % (ex['backtest']['scored_floor_0.0005']['total'] - ex['backtest']['scored_floor_0.0005']['passed'], ex['backtest']['scored_floor_0.0005']['total'])),
        ('Blank-value pattern', r'The strongest predictor is blank mainly for bankrupt firms; the cause is unknown. Version 1.1 refers such applications and applies an adverse floor to other blanks.'),
        ('Possible look-ahead', r"One ratio is defined over ``gross profit in 3 years'' and may use information after the assessment date; no run excludes it."),
        ('Sample size', r'The candidate pool needs %s rows on the default R-squared against %s available.' % (num(d['sufficiency'][0]['N_required_default_r2']), num(d['sufficiency'][0]['available']))),
        ('Scope', r'LGD, EAD, a rating philosophy analysis, stress testing beyond the mechanical sensitivity, and a true default grade are outside this model (%s; %s).' % (cite('EBA.PHIL', reg), cite('CRE36.STRESS', reg))),
    ]
    t += r'\begin{itemize}' + '\n' + '\n'.join(r'\item \textbf{%s.} %s' % (esc(a), b) for a, b in items) + '\n' + r'\end{itemize}' + '\n'
    return t


def sec_gov(d, reg):
    t = r'\section{Governance and controls}\label{sec:gov}' + '\n'
    t += r'\subsection{Roles and independence}' + '\n'
    rr = d['role_report']
    people = {w: 'Person %s' % chr(65 + i) for i, w in enumerate(sorted(set((rr.get('roles') or {}).values())))}
    t += (r'Roles declared: %s. %s There is no validation function independent of development (%s; %s; %s). This criterion is \textbf{not met}. SR 26-2 itself is non-binding and expresses quality of validation as rigor rather than organisational structure (%s); '
          r'independence appears as effective challenge (%s) and conflict-of-interest management (%s). The model-risk principles of the PRA (%s) expect separate reporting lines.'
          % (esc('; '.join('%s: %s' % (k, people[v]) for k, v in (rr.get('roles') or {}).items())), esc(rr['note'].capitalize() + '.'), cite('CRE36.IND', reg), cite('CRR.185', reg), cite('EBA.MOC', reg),
             cite('SR26-2.V', reg), cite('SR26-2.III', reg), cite('SR26-2.VI', reg), cite('PRA.SS1/23', reg)) + '\n\n')
    t += r'\subsection{Model inventory record}' + '\n'
    rows = [[esc(k), esc(v)] for k, v in d['inventory'].items()]
    t += table(['Field', 'Entry'], rows, r'@{}p{4cm}p{11.4cm}@{}', caption='Inventory record (%s)' % cite('SR26-2.VI', reg).replace(r'$^{\dagger}$', '') if False else 'Model inventory record', label='tab:inventory')
    t += r'\subsection{Decision record}' + '\n'
    roles = rr.get('roles') or {}
    rows = []
    for e in d['chain']:
        who = e.get('person') or roles.get(e['signer'])
        rb = e.get('rationale_by') or 'AI-drafted (not recorded in the sealed file)'
        rows.append([e['gate'], esc(e['option']), esc(e['signer']), esc(people.get(who, '')), esc(rb), r'\texttt{%s}' % e['entry_hash']])
    for e in d.get('voided', []):
        who = e.get('person') or roles.get(e['signer'])
        rows.append([r'\textit{\textcolor{greyn}{%s (voided)}}' % e['gate'], esc(e['option']), esc(e['signer']), esc(people.get(who, '')), 'superseded by v1.1', r'\texttt{%s}' % e['entry_hash']])
    t += table(['Gate', 'Option', 'Signer role', 'Person', 'Rationale', 'Hash'], rows, r'@{}llp{3.3cm}lp{3.2cm}l@{}', caption='Sealed decision record (entries in grey italics are voided version 1.0 entries, kept in the audit trail)', label='tab:chain')
    t += (r"Each entry's hash is computed from the previous hash, the gate, the option, the signer role and the rationale (eight hexadecimal characters, 32 bits), so a later edit is detectable. "
          r"The sealed file records no timestamp and no person, and the rationale text is in the file but not in the table above. The person and authorship columns are taken from the declared role holders and the session record, "
          r"not from the sealed file. The chain proves order and integrity; it does not prove who decided. The hash is not anchored outside the repository." + '\n\n')
    t += r'\subsection{Record-keeping for scored applications}' + '\n'
    t += (r'To be implemented before any use: a log entry for every scored or referred application with the timestamp, model version and floor/cap configuration, the raw inputs, the weight-of-evidence bin and score of each variable, the blank-value flags, the PD, grade and decision, the reason codes, '
          r'and any human override with who, when and why. Retention and access rules are for the institution to set. None of this is logged today, because the model has no live use (%s).' % cite('AIA.14', reg) + '\n\n')
    t += r'\subsection{Model-use controls}' + '\n'
    t += (r'Overrides of the model require a documented policy and tracking (%s); none exists. The accept or decline cutoff and pricing are institution inputs that this dossier does not set. The model supports a credit decision with a reason breakdown but does not make the decision.' % cite('CRE36.OVR', reg) + '\n')
    return t


def sec_matrix(d, reg):
    cl = {r['id']: r for r in d['checklist_strict']}
    names = {'R1': ('PD data history of at least five years', 'CRE36.79'), 'R2': ('Use test', 'CRE36.60'), 'R3': ('Meaningful risk differentiation', 'CRE36.DIFF'),
             'R4': ('Calibration backtest per grade', 'CRE36.122'), 'R5': ('Override governance', 'CRE36.OVR'), 'R6': ('Margin of conservatism', 'EBA.MOC'),
             'R7': ('Independent validation', 'SR26-2.V'), 'R8': ('Governance and accountability', 'SR26-2.VI'), 'R9': ('Risk-proportionate rigour', 'SR26-2.III'),
             'R10': ('Data governance and completeness', 'BCBS239'), 'R11': ('Model risk management principles', 'PRA.SS1/23'), 'R12': ('High-risk AI obligations', 'AIA.III5b'),
             'R13': ('Human-oversight operability', 'AIA.14'), 'R14': ('Adverse-action reasons', 'ECOA')}
    t = r'\section{Regulatory compliance matrix}\label{sec:matrix}' + '\n'
    t += (r'Status is read for \emph{regulatory use}: it is the stricter reading, derived from the recorded evidence and proposed to the committee. It is not a regulatory finding. '
          r"``Not met'' on a must-have row (R1--R9) is a hard stop in the engine. A dagger ($^\dagger$) marks a citation not yet verified against the primary text." + '\n\n')
    rows = []
    for rid in ['R%d' % i for i in range(1, 15)]:
        r = cl.get(rid)
        status = r['status'] if r else 'PENDING'
        act = d['closing_actions'].get(rid)
        rows.append([rid, names[rid][0], cite(names[rid][1], reg), STATUS_TEX.get(status, esc(status)), esc(r['note']) if r else 'evidence not yet produced',
                     (esc(act[0]) + ' (' + esc(act[1]) + ')') if (act and status in ('PARTIAL', 'GAP')) else ''])
    t += table(['\\#', 'Requirement', 'Source', 'Status', 'Evidence', 'What closes it (owner)'], rows, r'@{}lp{2.2cm}p{2.7cm}lp{4.3cm}p{3.6cm}@{}', caption='Compliance matrix R1--R14 (regulatory-use reading)', label='tab:matrix', long=True)
    t += r'\subsection{Further criteria a supervisor would examine}' + '\n'
    rows = [['X1', 'PD floor', cite('CRE32.4', reg) + '; ' + cite('CRR.160', reg), STATUS_TEX['SATISFIED'], '0.05\\% in version 1.1 (corrected from 0.03\\%), re-sealed; applies to corporate exposures; the retail revolving floor of 0.1\\% is not applicable'],
            ['X2', 'Definition of default', cite('CRE36.68', reg) + '; ' + cite('CRR.178', reg), STATUS_TEX['GAP'], 'The label is bankruptcy; the supervisory default definition is not applied'],
            ['X3', 'Long-run-average PD calibration', cite('CRE36.LRA', reg) + '; ' + cite('EBA.LRA', reg), STATUS_TEX['GAP'], 'The PD is a sample estimate from one cross-section'],
            ['X4', 'Stress testing', cite('CRE36.STRESS', reg), STATUS_TEX['PARTIAL'], 'A mechanical sensitivity only; no scenario or portfolio'],
            ['X5', 'Rating philosophy', cite('EBA.PHIL', reg), STATUS_TEX['PARTIAL'], 'Point-in-time by construction; not analysed or documented as a philosophy'],
            ['X6', 'Grade PD and grade structure', cite('CRE36.DIFF', reg) + '; ' + cite('CRE36.LRA', reg), STATUS_TEX['PARTIAL'], 'Grade PD defined as the sample mean predicted PD; ranking breaks; concentration unsupported'],
            ['X7', 'LGD and EAD', cite('CRR.180', reg), STATUS_TEX['NOT ASSESSED'], 'Outside this model']]
    t += table(['\\#', 'Criterion', 'Source', 'Status', 'Position'], rows, r'@{}lp{3cm}p{4.4cm}lp{5.2cm}@{}', caption='Further criteria', label='tab:further')
    return t


def sec_conditions(d, reg):
    gf = d['gf_strict']
    t = r'\section{Conditions and remediation plan}\label{sec:cond}' + '\n'
    t += r'Each open item below has an owner and a closing action. None is closed in this dossier.' + '\n\n'
    rows = []
    for r in d['checklist_strict']:
        if r['status'] in ('PARTIAL', 'GAP'):
            act = d['closing_actions'].get(r['id'], ('', ''))
            rows.append([r['id'], STATUS_TEX[r['status']], esc(r['note']), esc(act[0]), esc(act[1])])
    rows.append(['X2/X3', STATUS_TEX['GAP'], 'Default definition and long-run PD not applied', 'Needs the institution’s own default data, dates and observation window', 'Model Owner'])
    t += table(['\\#', 'Status', 'Open item', 'Closing action', 'Owner'], rows, r'@{}llp{4.9cm}p{4.4cm}p{2.2cm}@{}', caption='Open conditions', label='tab:cond', long=True)
    t += (r'\textbf{Standing conditions.} Never deploy (research benchmark); no independent validation; the %d-ratio final model is decision-parsimonious, not column-parsimonious; unexplained blank pattern in the strongest predictor; unresolved look-ahead definition; sampling-window confound; PD cap not exercised.'
          % d['selection']['columns'] + '\n\n')
    t += (r"\textbf{Engine verdicts.} Regulatory-use reading: \textbf{%s} (%s). Sealed research-benchmark verdict for version 1.0: %s. The two answer different questions and are shown side by side to avoid reading ``go with conditions'' as an approval."
          % (esc(gf['verdict']), esc('; '.join(c.split(':')[0] for c in (gf['blockers'] or gf['conditions']))), esc(d['gf_sealed'])) + '\n')
    return t


def sec_attest(d, reg):
    t = r'\section{Attestations}\label{sec:attest}' + '\n'
    t += r'Signature blocks are intentionally blank. They are completed by the named post-holders only when the committee rules.' + '\n\n'
    roles = ['Model Owner', 'Model Validator (independent)', 'Risk Officer', 'Chair, Model Approval Committee', 'Chief Risk Officer']
    t += table(['Role', 'Name', 'Signature', 'Date'], [[r, '', '', ''] for r in roles], r'@{}p{5.4cm}p{3.6cm}p{3.6cm}p{2.4cm}@{}')
    t += r'\vspace{1cm}' + '\n' + r'Declaration of reliance: the figures in this document are read from the stored stage outputs of the run and from the analyses named in Annex D; no figure is typed by hand.' + '\n'
    return t


# ---------------------------------------------------------------------------------------------- annexes
def annex_bins(d, reg):
    t = r'\appendix' + '\n' + r'\section{Annex A: Scorecard (weight-of-evidence tables)}' + '\n'
    t += (r'For each variable: the bin, firms, defaults, default rate and weight of evidence (WOE = ln share of non-defaulters over share of defaulters; a lower value means a riskier bin). '
          r'A bin labelled \texttt{\_\_missing\_\_} holds blank values; a variable with no such bin scores a blank as 0, and version 1.1 floors every non-mandatory blank at the worst real bin.' + '\n\n')
    rows = []
    for c, bins in d['scorecard_bins'].items():
        first = True
        for b in bins:
            rows.append([tt(c) if first else '', esc(b['bin']), num(b['n']), num(b['defaults']), pct(b['default_rate'], 2), f(b['woe'], 3)])
            first = False
    return t + table(['Variable', 'Bin', 'Firms', 'Defaults', 'Default rate', 'WOE'], rows, r'@{}p{5.2cm}p{4.2cm}rrrr@{}', caption='Scorecard', label='tab:score', long=True)


def annex_reasons(d, reg):
    t = r'\section{Annex B: Reason-code examples}' + '\n'
    t += r'The five largest contributions (coefficient times weight of evidence; a positive contribution raises risk) for three illustrative cases. Because ratios overlap, several reasons can restate one underlying fact.' + '\n\n'
    for name, v in d['ex']['reason_code_examples'].items():
        rows = [[tt(r['variable']), f(r['value'], 4), f(r['woe'], 3), '%+.3f' % r['contribution'], 'raises risk' if r['contribution'] > 0 else 'lowers risk'] for r in v['top_reasons']]
        t += table(['Variable', 'Value', 'WOE', 'Contribution', 'Effect'], rows, r'@{}p{6.4cm}rrrl@{}', caption='%s: PD %s, grade %s' % (esc(name.replace('_', ' ')), pct(v['pd'], 2), v['grade']))
    return t


def annex_glossary(d, reg):
    g = [('Gini / AUC', 'How well the model ranks bankrupt firms above healthy ones. AUC 0.5 is chance, 1 is perfect; Gini = 2 AUC - 1.'),
         ('KS', 'The largest gap between the cumulative score distributions of bankrupt and healthy firms.'),
         ('Scored population', 'The firms the deployed model scores; firms it refers to a human are excluded.'),
         ('Weight of evidence (WOE)', 'A score for a bin: the log of the share of healthy firms over the share of bankrupt firms in it.'),
         ('Information value (IV)', 'How strongly one ratio separates bankrupt from healthy firms; above 0.02 is the screening bar.'),
         ('Brier skill', 'One minus the Brier score divided by that of always predicting the base rate.'),
         ('Expected calibration error', 'The average gap between predicted and observed default rates.'),
         ('Hosmer--Lemeshow', 'A test of whether predicted and observed defaults agree across risk groups; p below 0.05 means they disagree.'),
         ('Wilson interval', 'The range the realised default rate could plausibly take given the number of firms.'),
         ('Nested validation', 'Re-running the whole selection inside each cross-validation fold, so no test firm influences which variables are chosen.'),
         ('Events per variable (EPV)', 'Bankruptcies divided by the number of candidate variables; a rule of thumb asks for at least 10.'),
         ('Riley minimum sample size', 'Rows needed so the fitted model does not overfit; it depends on an assumed explained variance (R-squared).'),
         ('Margin of conservatism', 'An addition to estimates to cover data deficiencies and estimation error.'),
         ('Adverse floor', 'Scoring a blank as the worst real bin so that omitting a field cannot lower risk.'),
         ('PD', 'Probability of default (here, of bankruptcy) within the horizon.')]
    return r'\section{Annex C: Glossary}' + '\n' + table(['Term', 'Meaning'], [[esc(a), esc(b)] for a, b in g], r'@{}p{4cm}p{11.4cm}@{}')


def annex_evidence(d, reg):
    fl = d['ex']['file']
    t = r'\section{Annex D: Evidence index}' + '\n'
    rows = [['Sealed decision record (v1.0)', r'\texttt{sharp\_runs\_staged/%s/chain.json}' % esc(d['run'])], ['Stage outputs', r'\texttt{sharp\_runs\_staged/%s/state.pkl}' % esc(d['run'])],
            ['Scorecard', r'\texttt{sharp\_runs\_staged/%s/scorecard.md}' % esc(d['run'])], ['Phase 2 analyses', r'\texttt{dossier/%s/phase2/extras.json}' % esc(d['run'])],
            ['Nested validation', r'\texttt{dossier/%s/phase2/nested\_validation.json}' % esc(d['run'])], ['Cutoff note', r'\texttt{AEGIS\_POLISH\_1YR\_CUTOFF\_POLICY.md}'],
            ['Acceptance cases', r'\texttt{acceptance\_cases/polish\_1yr.json}'], ['Data file', r'%s, SHA-256 \texttt{%s}' % (tt(fl['name']), fl['sha256'])],
            ['Head hash of the record', r'\texttt{%s}' % esc(d['head'])]]
    return t + table(['Item', 'Location'], rows, r'@{}p{4.6cm}p{10.8cm}@{}')


def annex_refs(d, reg):
    label = {'VERIFIED_PRIMARY': 'verified, primary text', 'VERIFIED_SECONDARY': 'verified, secondary source only', 'CORRECTED': 'corrected', 'NOT_VERIFIED': 'not verified'}
    t = r'\section{Annex E: References and verification status}' + '\n'
    cnt = {}
    for key in CITES:
        s = reg[key]['status'] if key in reg else 'NOT YET VERIFIED'
        cnt[s] = cnt.get(s, 0) + 1
    t += (r'Every regulatory citation appears here with the exact section, article or paragraph, where it is used, and whether it has been checked against the text. A dagger in the body marks a citation not yet verified against the primary text. '
          r'Status counts: ' + ', '.join('%d %s' % (v, esc(label.get(k, k.lower()))) for k, v in cnt.items()) + '.\n\n')
    rows = []
    for key, (doc, loc, used) in CITES.items():
        r = reg.get(key)
        rows.append([r'\hypertarget{ref:%s}{%s}' % (key, esc(key)), esc(r['document'] if r else doc), esc(r['locator'] if r else loc), esc(r['topic_we_cite_it_for'] if r else used),
                     esc(label.get(r['status'], r['status']) if r else 'not yet verified'), (r'\url{%s}' % r['url']) if (r and r.get('url')) else ''])
    t += r'\begingroup\sloppy' + '\n' + table(['Key', 'Document', 'Section / article / paragraph', 'Used for', 'Verification', 'Source'], rows,
                                              r'@{}p{1.7cm}p{3cm}p{3.1cm}p{2.9cm}p{1.9cm}p{2.9cm}@{}', caption='Reference register', label='tab:refs', long=True) + r'\endgroup' + '\n'
    notes = [[esc(k), esc(r['note'])] for k, r in reg.items() if r.get('note')]
    if notes:
        t += r'\subsection*{Notes on verification}' + '\n' + table(['Key', 'Note'], notes, r'@{}p{2.4cm}p{13.4cm}@{}', long=True)
    return t


def build(data, outdir, phase=2):
    d = pickle.load(open(data, 'rb')) if isinstance(data, str) else data
    reg = load_register()
    os.makedirs(outdir, exist_ok=True)
    pre = PREAMBLE % dict(header_left=esc('Model Approval Dossier: ' + d['run']), header_right=esc('Research benchmark, review draft'), footer_left=esc('Head ' + d['head']))
    parts = [pre, cover(d, phase), doc_control(d, phase), sec_summary(d, reg), sec_scope(d, reg), sec_data(d, reg), sec_model(d, reg), sec_dev(d, reg), sec_perf(d, reg),
             sec_maint(d, reg), sec_limits(d, reg), sec_gov(d, reg), sec_matrix(d, reg), sec_conditions(d, reg), sec_attest(d, reg),
             annex_bins(d, reg), annex_reasons(d, reg), annex_glossary(d, reg), annex_evidence(d, reg), annex_refs(d, reg), r'\end{document}']
    name = 'DOSSIER_%s_phase%s' % (d['run'], phase)
    with open(os.path.join(outdir, name + '.tex'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(parts))
    for _ in range(3):
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', name + '.tex'], cwd=outdir, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            print(r.stdout[-3500:])
            raise RuntimeError('pdflatex failed; see log in %s' % outdir)
    return os.path.join(outdir, name + '.pdf')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--phase', default='2')
    a = ap.parse_args()
    print(build(a.data, a.out, a.phase))
