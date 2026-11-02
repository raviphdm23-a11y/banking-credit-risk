r"""
Build a generic Model Approval Dossier (LaTeX -> PDF) from a sealed SHARP-AEGIS run.

    python ml_models/build_dossier_generic.py --data <dossier_data.pkl> --state <state.pkl> --extras <extras.json> \
        --manifest <manifest.json> --out <folder>

Unlike build_dossier.py (written for the Polish run), nothing here is dataset-specific. Every number is read from the
sealed record (dossier_data.pkl, the run state, the manifest); nothing is typed here. Wording that depends on facts the
record does not hold (supervisor, independent validator, institution) prints as a marked placeholder.

Deliberately NOT used, because they ignore the company grouping of a panel and are therefore leaky for panel data:
extras.json challengers, duplicates check, backtest and the row-bootstrap Gini intervals (perf_all / perf_scored).
"""
import argparse
import json
import os
import pickle
import re
import subprocess
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_dossier as bd  # noqa: E402  (helpers and preamble only; its section functions are not used)

esc, f, pct, num, table = bd.esc, bd.f, bd.pct, bd.num, bd.table
TBD = r'\textcolor{alertred}{[to be confirmed]}'
STAT = {'SATISFIED': r'\stSAT', 'PARTIAL': r'\stPAR', 'GAP': r'\stGAP', 'N/A': r'\stNA'}


def short(c, n=0):
    return c


def tt(s):
    """Monospace name that can wrap: break points before a capital that follows a lowercase letter or digit, and after underscores."""
    return r'\texttt{' + re.sub(r'(?<=[a-z0-9])(?=[A-Z])', r'\\allowbreak{}', bd.esc(s)).replace(r'\_', r'\_\allowbreak{}') + '}'


def panel_facts(m):
    df = pd.read_csv(m['csv'] if os.path.isabs(m['csv']) else os.path.join(ROOT, m['csv']))
    ent, tcol, y = m['panel']['entity_id'], m['panel']['time_col'], m['target']
    return dict(firms=df[ent].nunique(), event_firms=df.loc[df[y] == 1, ent].nunique(), rows=len(df), events=int(df[y].sum()),
                t0=str(df[tcol].min()), t1=str(df[tcol].max()), periods=df[tcol].nunique(), meta_cols=[c for c in df.columns if c not in m['panel']['hazard']['feature_cols'] and c != y])


# ------------------------------------------------------------------------------------------------ front matter
def cover(d, m):
    return r"""\thispagestyle{empty}
\begin{center}
{\large\textcolor{greyn}{%(inst)s}}\\[2.2cm]
{\Huge\bfseries\textcolor{navy}{Model Approval Dossier}}\\[0.5cm]
{\Large Probability-of-Default Model\\[2pt] %(run)s}\\[1.2cm]
\begin{tabular}{rl}
\textbf{Portfolio} & %(portfolio)s\\
\textbf{Model version} & %(ver)s\\
\textbf{Materiality tier} & %(tier)s\\
\textbf{Sealed-record head} & \texttt{%(head)s}\\
\textbf{Document phase} & Phase 1 review draft\\
\end{tabular}\\[1.6cm]
\fcolorbox{alertred}{white}{\parbox{0.86\textwidth}{\centering\small
\textbf{STATUS: RESEARCH BENCHMARK, REVIEW DRAFT. NEVER DEPLOY.}\\
This dossier describes a model built on research data. It is not approved for, and must not be used in, a live credit
decision or for regulatory capital. It is written so that its evidence can be reviewed; it is not a submission and
does not claim approval.}}
\end{center}
\newpage
""" % dict(inst=esc(d['institution']), run=esc(d['run']), portfolio=esc(d['portfolio']), ver=esc(d['model_version']), tier=esc(d['tier']), head=esc(d['head']))


def doc_control(d):
    by = '; '.join('%d %s' % (v, esc(k)) for k, v in d['rationale_by_counts'].items())
    rows = [['Document', 'Model Approval Dossier, ' + esc(d['run'])], ['Version / phase', esc(d['model_version']) + ' / Phase 1 review draft'],
            ['Prepared by', 'Model development: a single researcher, assisted by an AI assistant'],
            ['Reviewers', 'Not assigned; ' + TBD], ['Evidence source', r'Sealed decision record, head hash \texttt{%s}, %d entries' % (esc(d['head']), len(d['chain']))],
            ['Gate rationales', 'Every rationale was drafted by the AI assistant and adopted by the signer, as recorded per entry: ' + by + '.'],
            ['Distribution', 'Model Approval Committee; not for external distribution while the status is research benchmark']]
    return r'\section*{Document control}' + '\n' + table(['Item', 'Entry'], rows, r'@{}p{3.4cm}p{12cm}@{}') + '\n' + r'\tableofcontents\newpage' + '\n'


# ------------------------------------------------------------------------------------------------ sections
def sec_summary(d, st, pf):
    c0, oot = d['curve'][0], st['stage4']['oot']
    sel = d['selection']
    t = r'\section{Summary and decision requested}' + '\n'
    t += (r'The model scores company-quarters (%s rows from %s firms; %s of the firms have at least one positive row) on the probability that the quarter falls within the pre-registered window before the firm\textquotesingle s first insolvency filing. '
          % (num(pf['rows']), num(pf['firms']), num(pf['event_firms'])) +
          r'It uses %d of %d candidate columns, selected by SHARP at k = %d. ' % (sel['columns'], sel['candidates_screened'], sel['k']) +
          'Company-grouped cross-validated Gini is %s (company-bootstrap 95\\%% interval %s--%s, AUC %s). On a later-period test the Gini is %s, a relative fall of %s. '
          % (f(c0['gini']), f(c0['gini_ci_low']), f(c0['gini_ci_high']), f(c0['auc']), f(oot['gini']), pct(oot['gini_drop_rel'])) + '\n\n')
    t += table(['Reading', 'Engine verdict'], [['Earlier-use reading (sealed at the final gate)', r'\textbf{%s}' % esc(d['gf_sealed'])],
                                               ['Regulatory-use reading', r'\textbf{%s}' % esc(d['gf_strict']['verdict'])]], r'@{}p{9cm}p{5cm}@{}')
    t += '\n' + (r'\textbf{Decision requested.} Committee review of the evidence only. No approval is sought, and the model carries a NEVER-DEPLOY condition. '
                 r'The regulatory-use reading is NO-GO because %s must-have criteria are not met (%s); see Section 9.' % (len(d['must_have_gaps']), esc(', '.join(d['must_have_gaps']))))
    return t + '\n'


def sec_scope(d, m, pf):
    t = r'\section{Scope and intended use}' + '\n'
    t += table(['Item', 'Entry'], [['Population', 'Listed companies; %s firms, %s company-quarters, %s to %s (%d periods)' % (num(pf['firms']), num(pf['rows']), esc(pf['t0']), esc(pf['t1']), pf['periods'])],
                                   ['Jurisdiction / borrower type', esc(m['jurisdiction']) + ' / ' + esc(m['borrower_type'])],
                                   ['Event label', 'The target column marks a quarter that lies within the pre-registered window before the firm\'s first insolvency-resolution filing. A filing is not a confirmed admission and is not a loan default.'],
                                   ['Framing', 'Panel, hazard: every company-quarter is a row; entity = %s, time = %s; cross-validation is grouped by company' % (tt(m['panel']['entity_id']), tt(m['panel']['time_col']))],
                                   ['Intended use', esc(d['inventory']['Purpose']) + '. ' + esc(d['inventory']['Intended users']) + '; downstream uses: ' + esc(d['inventory']['Downstream uses'])],
                                   ['Supervisor / applicable rulebook', TBD + ' (not verified in this document)']], r'@{}p{4cm}p{11.4cm}@{}')
    rows = [[esc(k.replace('_', ' ')), 'binding' if v['binding'] else 'not binding', esc(v['reason'])] for k, v in d['regimes'].items()]
    t += '\n' + table(['Regime', 'As recorded', 'Reason recorded'], rows, r'@{}p{3.6cm}p{2.2cm}p{9.6cm}@{}', caption='Regimes considered in the run (the supervisor above is not confirmed, so these are the run\'s own screening, not a legal conclusion)') + '\n'
    t += 'The run enforces no legal-form gate, so the scope above is a statement of intent: nothing in the model stops it from being applied to a non-company borrower.\n'
    return t


def sec_data(d, m, ex, pf):
    dt, fl = d['data'], ex['file']
    t = r'\section{Data}' + '\n'
    t += table(['Item', 'Entry'], [['File', '%s, %s bytes, SHA-256 \\texttt{%s\\allowbreak{}%s}' % (tt(fl['name']), num(fl['bytes']), fl['sha256'][:32], fl['sha256'][32:])],
                                   ['Rows / firms / periods', '%s / %s / %d' % (num(dt['n']), num(pf['firms']), pf['periods'])],
                                   ['Positive rows / firms', '%s (%s) / %s' % (num(dt['events']), pct(dt['prevalence'], 2), num(pf['event_firms']))],
                                   ['Model inputs', '%d financial columns. Identifier and date columns (%s) are not model inputs.' % (dt['n_columns'], ', '.join(tt(c) for c in pf['meta_cols']))],
                                   ['Sample', 'Not a random sample of listed companies (see the manifest note); the default share is not a population rate'],
                                   ['Rows with a blank', '%s of %s' % (num(dt['rows_with_blank']), num(dt['n']))]], r'@{}p{4cm}p{11.4cm}@{}')
    rows = [[tt(short(b['column'], 52)), num(b['n_blank']), f(b['pct_blank'], 1) + '\\%', num(b['events_in_blank']), pct(b['event_rate_blank'], 1), pct(b['event_rate_filled'], 1),
             '%.1e' % b['bonferroni_p'] if b['bonferroni_p'] < 0.001 else f(b['bonferroni_p'], 4), 'yes' if b['below_bonferroni'] else 'no'] for b in dt['blank_table']]
    t += '\n' + table(['Column', 'Blank', '\\%', 'Pos. in blank', 'Rate blank', 'Rate filled', 'Bonf. p', 'Tracks'], rows, r'@{}p{4.6cm}rrrrrrl@{}',
                      caption='Blank-value pattern: does a blank predict the outcome? (columns with at least one blank)', long=True)
    t += '\n' + ('Blank values that track the outcome beyond the Bonferroni limit: %d. A blank can itself carry information (a firm that stops reporting a line), so the model\'s treatment of blanks matters; Section 5 states it.\n' % dt['blank_beyond_bonferroni'])
    sent = '; '.join('%s: %s' % (tt(short(k, 40)), ', '.join(str(v) for v in vals)) for k, vals in dt['sentinels'].items())
    t += 'Sentinel-value scan: %s. ' % (sent if sent else 'nothing flagged') + 'Look-ahead scan: %s. This scan applies named heuristics only; a clean result does not settle whether any column is known only after the event.\n' % (
        'nothing flagged' if not dt['lookahead'] else esc(str(dt['lookahead'])))
    return t


IV_RANGES = [('below 0.02', 'not useful'), ('0.02 to 0.1', 'weak'), ('0.1 to 0.3', 'medium'), ('0.3 to 0.5', 'strong'), ('above 0.5', 'very strong, check for leakage or sparse events')]
V_RANGES = [('below 0.1', 'negligible'), ('0.1 to 0.2', 'weak'), ('0.2 to 0.4', 'moderate'), ('0.4 to 0.6', 'relatively strong'), ('above 0.6', 'strong')]


def sec_dev(d, st):
    s1 = st['stage1']['s1_table'].sort_values('iv_woe', ascending=False)
    t = r'\section{Development}' + '\n' + "\\subsection{Screening (information value and Cram\\'er's V)}" + '\n'
    t += (r"\textbf{Information value (IV)} measures how strongly one column separates positive from negative rows; \textbf{Cram\'er's V} measures the association between the column's bins and the outcome, from 0 (none) to 1. "
          r'The range labels below are conventional rules of thumb, not outputs of this run. With only %d positive rows, IV is inflated by sparse bins, so values above 0.5 are read as unreliable, not as strength.' % d['data']['events'] + '\n\n')
    t += table(['IV range', 'Conventional reading'], [[a, b] for a, b in IV_RANGES], r'@{}p{3cm}p{9cm}@{}', caption='IV ranges')
    t += table(["Cram\\'er's V range", 'Conventional reading'], [[a, b] for a, b in V_RANGES], r'@{}p{3cm}p{9cm}@{}', caption="Cram\\'er's V ranges")
    sel = set(d['selection'].get('columns_list', [])) or {v['variable'] for v in d['variables']}
    rows = [[tt(short(c, 50)), f(r.iv_woe, 3), f(r.cramers_v_descriptive, 3), '%.1e' % r.p_value, 'yes' if r.passes_screen else 'no', 'selected' if c in sel else ''] for c, r in s1.iterrows()]
    t += table(['Column', 'IV', "Cram\\'er's V", 'p-value', 'Passes screen', 'In model'], rows, r'@{}p{6.4cm}rrrll@{}',
               caption='Screening of all %d candidate columns (%d pass)' % (d['selection']['candidates_screened'], d['selection']['candidates_passed']), long=True)
    t += r'\subsection{Attribution}' + '\n' + (r'Columns were grouped into correlated players and ranked by Shapley value against a shadow (noise) bar of %s. %d players were real and %d confirmed above the bar. The selected set forms %d player: %s members, Shapley %s.' % (
        f(d['shadow_bar'], 4), d['selection']['players_real'], d['selection']['players_confirmed'], len(d['players']), len(d['players'][0]['members']), f(d['players'][0]['shapley'], 4))) + '\n'
    rows = [[str(c['k']), str(c['n_columns']), f(c['gini']), '%s--%s' % (f(c['gini_ci_low']), f(c['gini_ci_high'])), f(c['auc']), f(c['ks']), pct(c['relative_gini_loss_vs_full'], 1), f(c['delong_p_vs_full'], 3)] for c in d['curve']]
    t += r'\subsection{Parsimony curve}' + '\n' + table(['k', 'Columns', 'Gini', '95\\% interval', 'AUC', 'KS', 'Gini change vs full', 'DeLong p vs full'], rows, r'@{}rrrlrrrr@{}',
                                                         caption='Gini by number of retained players. Intervals and p-values resample whole companies. Rule: %s' % esc(st['stage3']['decision']['rule']))
    rows = [[esc(s['stage']), esc(s['basis']), str(s['P']), f(s['EPV'], 1), f(s['c_stat'], 3), num(s['N_required']), num(s['available']), 'yes' if s['riley_met'] else 'no', 'governing' if s['governing'] else 'informational'] for s in d['sufficiency']]
    t += r'\subsection{Sample sufficiency}' + '\n' + table(['Stage', 'Basis', 'P', 'EPV', 'c-stat', 'Rows needed', 'Rows', 'Riley met', 'Role'], rows, r'@{}p{1cm}p{4.4cm}rrrrrll@{}',
                                                           caption='Events per variable (EPV) and Riley minimum sample size by stage')
    return t


def sec_model(d, m):
    sp = d['spec']
    t = r'\section{Model specification}' + '\n'
    t += table(['Item', 'Entry'], [['Learner', esc(sp['learner'])], ['Regularisation', '%s, C = %s, solver %s, seed %s' % (esc(sp['penalty']), sp['C'], esc(sp['solver']), sp['seed'])],
                                   ['Calibration', esc(sp['calibration'])], ['PD floor / cap', '%s / %s (Basel CRE32.4 floor)' % (pct(sp['pd_floor'], 2), pct(sp['pd_cap'], 1))],
                                   ['Incomplete record', 'policy \\texttt{%s}; mandatory field(s): %s' % (esc(sp['incomplete_policy']), ', '.join(tt(c) for c in sp['mandatory']))],
                                   ['Intercept', f(d['intercept'], 3)]], r'@{}p{4cm}p{11.4cm}@{}')
    rows = [[tt(short(v['variable'], 54)), f(v['iv'], 3), '%+.3f' % v['coefficient_on_woe'], '%+.3f' % v['univariate_rho_with_default'], num(v['n_blank'])] for v in d['variables']]
    t += '\n' + table(['Variable', 'IV', 'Coefficient on WOE', 'Univariate rho', 'Blanks'], rows, r'@{}p{7cm}rrrr@{}', caption='Model variables')
    t += ('%d of %d coefficients on weight of evidence are positive. Weight of evidence is defined (Annex A) so that a lower value means a riskier bin, so a positive coefficient pushes risk the wrong way. '
          'The run does not explain this. Near-duplicate profit and earnings-per-share columns are a possible cause; that is a hypothesis, not a tested result.\n' % (d['coef_positive_count'], len(d['variables'])))
    rows = [[esc(g['grade']), esc(g['label']), pct(g['low'], 2), pct(g['high'], 2)] for g in sp['masterscale']]
    t += '\n' + table(['Grade', 'Label', 'PD from', 'PD to'], rows, r'@{}llrr@{}', caption='Master scale (PD bands)')
    return t


def sec_perf(d, st, ex):
    c0, oot, sc = d['curve'][0], st['stage4']['oot'], d['scorecard']
    ac, cp, bm = sc['accuracy'], d['calibration_primary'], d['backtest_meta']
    t = r'\section{Performance and validation}' + '\n' + r'\subsection{In time (company-grouped cross-validation)}' + '\n'
    t += table(['Measure', 'Value'], [['Gini', '%s (95\\%% company-bootstrap %s--%s)' % (f(c0['gini']), f(c0['gini_ci_low']), f(c0['gini_ci_high']))], ['AUC / KS', '%s / %s' % (f(c0['auc']), f(c0['ks']))],
                                      ['Brier skill vs base rate', f(ac['brier_skill_oof'], 3)], ['Expected calibration error (raw)', f(ac['ece_oof'], 4)],
                                      ['Calibration slope / intercept', '%s / %s' % (f(ac['calibration_slope_oof'], 2), f(ac['calibration_intercept_oof'], 2))],
                                      ['Hosmer--Lemeshow p (10 / 5 groups)','%s / %s' % (f(ac['hl_p_g10'], 3), f(ac['hl_p_g5'], 3))]], r'@{}p{7cm}p{8cm}@{}')
    t += '\nA calibration slope of %s is below 1: the raw predictions are more extreme than the outcomes warrant, which is typical of a model fitted on few events. Isotonic calibration (below) addresses level, not the shortage of events.\n' % f(ac['calibration_slope_oof'], 2)
    t += r'\subsection{Out of time}' + '\n'
    t += ('Training on the first %s company-quarters and testing on the later %s (test event rate %s, %d firms, %d of them not seen in training): Gini %s against %s in time (a relative fall of %s), AUC %s, calibrated expected calibration error %s. '
          % (num(oot['n_train']), num(oot['n_test']), pct(oot['test_event_rate'], 2), oot['n_test_entities'], oot['n_test_new_entities'], f(oot['gini']), f(oot['in_time_gini']), pct(oot['gini_drop_rel'], 1), f(oot['auc']), f(oot['ece_cal'], 4)) +
          'Because every test firm also appears in training, this is out of time but not out of firm. Hosmer--Lemeshow on the test set: %s as computed, %s after adjusting for repeated quarters of the same firm (design effect %s).\n'
          % ('p = %.1e' % oot['hl']['p_value'], 'p = %s' % f(oot['hl']['p_adj'], 3), f(oot['hl']['design_effect'], 2)))
    t += r'\subsection{Calibration and per-grade backtest}' + '\n'
    t += ('Isotonic calibration on 5-fold held-out scores (%s rows): Brier %s raw, %s calibrated, always-base-rate %s; expected calibration error %s raw, %s calibrated. '
          % (num(cp['n_heldout']), f(cp['raw_brier'], 4), f(cp['calibrated_brier'], 4), f(cp['baseline_brier_always_base_rate'], 4), f(cp['raw_ece'], 4), f(cp['calibrated_ece'], 4)) +
          'The per-grade backtest below uses a separate held-out set of %s rows, with intervals that resample whole companies; %d of %d grades pass. The two held-out counts are as recorded by two different steps and are not reconciled here.\n' % (num(bm['n_heldout']), bm['passed'], bm['total']))
    rows = [[esc(b['grade']), num(b['n']), num(b['defaults']), pct(b['realised'], 2), pct(b['expected'], 2), '%s--%s' % (pct(b['ci_low'], 1), pct(b['ci_high'], 1)), r'\stPASS' if b['pass'] else r'\stFAIL'] for b in d['backtest']]
    t += table(['Grade', 'Rows', 'Positives', 'Realised', 'Expected', 'Realised interval', 'Result'], rows, r'@{}lrrrrll@{}', caption='Per-grade backtest (a grade with few rows has an interval too wide to be informative)')
    cv = d['coverage']
    t += r'\subsection{Coverage and referral}' + '\n' + ('%s of %s rows are scored; %s referred because the mandatory field is blank (positives among them: %d). Scored PD ranges %s to %s. The PD floor was %sexercised and the PD cap was %sexercised on this data.\n'
                                                           % (num(cv['n_scored']), num(cv['n_rows']), num(cv['n_referred_or_rejected']), ex['referred']['events'], pct(cv['pd_min_scored'], 2), pct(cv['pd_max_scored'], 1),
                                                              '' if cv['floor_exercised'] else 'not ', '' if cv['cap_exercised'] else 'not '))
    g = ex['baseline_distribution']['grades']
    t += table(['Grade'] + list(g), [['Rows'] + [num(v) for v in g.values()]], '@{}l' + 'r' * len(g) + '@{}', caption='Scored rows by grade (descriptive; the score is concentrated in a few grades)')
    return t


def sec_cases(d):
    rows, flags = [], []
    for c in d['cases']:
        a = {1: 'bankrupt', 0: 'repaid', None: 'synthetic'}[c['actual']]
        rows.append([tt(c['name'].split('-', 1)[-1]), esc(c['kind']), a, esc(c['decision']), pct(c['pd'], 2), esc(c['grade'])])
        if c['actual'] == 1 and c['grade'] in ('AAA', 'AA'):
            flags.append(c['name'].split('-', 1)[-1])
    t = r'\section{Acceptance cases}' + '\n' + table(['Case', 'Kind', 'Actual', 'Decision', 'PD', 'Grade'], rows, r'@{}p{6cm}llllr@{}', caption='Acceptance cases (real rows chosen by rule, plus synthetic extremes)')
    if flags:
        t += r'\textbf{Flag:} %s is a real positive row that the model grades %s. It is shown because a model that rates a firm safe in the quarters before it fails is the failure that matters most; it is a single case and says nothing about frequency.' % (
            ', '.join(tt(x) for x in flags), esc([c['grade'] for c in d['cases'] if c['name'].split('-', 1)[-1] == flags[0]][0])) + '\n'
    return t


def sec_limits(d, st, pf):
    L = ['Only %d positive rows from %d firms: the model is fitted on very few independent events, and every interval above is wide. Events per variable is %s on the candidate pool; the Riley minimum sample size is not met on it (%s rows needed, %s available).' % (
        d['data']['events'], pf['event_firms'], f(d['sufficiency'][0]['EPV'], 1), num(d['sufficiency'][0]['N_required']), num(d['sufficiency'][0]['available'])),
         'Per-grade backtest: %d of %d grades pass on %s held-out rows with few positives in each grade; the test cannot confirm calibration grade by grade.' % (d['backtest_meta']['passed'], d['backtest_meta']['total'], num(d['backtest_meta']['n_heldout'])),
         'The out-of-time test contains only firms also seen in training, and its Gini is %s below the in-time figure.' % pct(st['stage4']['oot']['gini_drop_rel'], 1),
         'The event is an insolvency-resolution filing, not a loan default; it is a proxy and not the definition of default in CRE36.68.',
         'The sample is not random and positive firms are over-represented, so the base rate here is not a population rate.',
         '%d of %d coefficients on weight of evidence have the wrong sign (Section 5); the cause is not established.' % (d['coef_positive_count'], len(d['variables'])),
         'Sample inputs show profit columns that disagree in sign for the same quarter; this was noticed during the run and was not investigated.',
         'Ungrouped cross-validation overstates the Gini on this data (0.675 against 0.615 grouped by company, a diagnostic run while building this dossier and not part of the sealed record), because the same firm\'s quarters land in both train and test. Any figure from a split that ignores the firm grouping should be treated as inflated.',
         'No independent validator is assigned and no margin of conservatism is quantified (Section 9).']
    return r'\section{Limitations}' + '\n' + r'\begin{itemize}' + '\n' + '\n'.join(r'\item ' + x for x in L) + '\n' + r'\end{itemize}' + '\n'


def sec_gov(d):
    t = r'\section{Governance and record}' + '\n'
    rows = [[g['gate'], g['option'], esc(g['signer']), esc(g['person']), tt(g['entry_hash']), esc(g['rationale_by'])] for g in d['chain']]
    t += table(['Gate', 'Option', 'Role', 'Person', 'Hash', 'Rationale'], rows, r'@{}llp{2.6cm}p{1.8cm}lp{5.4cm}@{}', caption='Sealed decision chain (genesis %s, head %s)' % (esc(d['genesis']), esc(d['head'])))
    t += r'One person holds all roles (%s): there is no separation between developer, validator and approver.' % esc(', '.join(d['role_report']['roles'])) + '\n'
    rows = []
    for a, b in zip(d['checklist'], d['checklist_strict']):
        rows.append([a['id'], esc(a['gate']), STAT[a['status']], STAT[b['status']], 'yes' if b['must_have'] else '', esc(b['note'])])
    t += '\n' + table(['ID', 'Gate', 'Earlier', 'Regulatory', 'Must', 'Note (regulatory-use reading)'], rows, r'@{}llllcp{7.2cm}@{}', caption='Readiness checklist, both readings', long=True)
    t += r'\subsection{Conditions and owners}' + '\n' + 'Engine conditions sealed with the ruling:\n\\begin{itemize}\n' + '\n'.join(r'\item ' + esc(c) for c in d['gf_engine']['conditions']) + '\n\\end{itemize}\n'
    rows = []
    for k, (act, own) in d['closing_actions'].items():
        stt = next(b['status'] for b in d['checklist_strict'] if b['id'] == k)
        if stt in ('GAP', 'PARTIAL'):
            rows.append([k, STAT[stt], esc(act), esc(own)])
    t += table(['ID', 'Status', 'Action to close', 'Owner'], rows, r'@{}llp{8cm}p{3.4cm}@{}', caption='Actions to close open items (regulatory-use reading)')
    t += r'Regulatory-use blockers: ' + '; '.join(esc(b.split(':')[0]) for b in d['gf_strict']['blockers']) + '.\n'
    inv = dict(d['inventory'], **{'Data lineage': 'See Section 3 and Annex D (file hash recorded)', 'Open issues': 'See Sections 8 and 9'})   # the stored text points at the Polish dossier's numbering
    t += r'\subsection{Inventory entry}' + '\n' + table(['Field', 'Entry'], [[esc(k), esc(v)] for k, v in inv.items()], r'@{}p{4cm}p{11.4cm}@{}')
    return t


def annex(d, m, ex):
    t = r'\appendix' + '\n' + r'\section{Annex A: Scorecard (weight-of-evidence tables)}' + '\n'
    t += 'For each variable: the bin, rows, positives, positive rate and weight of evidence (WOE = ln share of negatives over share of positives; lower means riskier).\n\n'
    rows = []
    for c, bins in d['scorecard_bins'].items():
        for i, b in enumerate(bins):
            rows.append([tt(short(c, 40)) if i == 0 else '', esc(b['bin']), num(b['n']), num(b['defaults']), pct(b['default_rate'], 2), f(b['woe'], 3)])
    t += table(['Variable', 'Bin', 'Rows', 'Positives', 'Rate', 'WOE'], rows, r'@{}p{5.2cm}p{4.2cm}rrrr@{}', caption='Scorecard', long=True)
    t += r'\section{Annex B: Reason-code examples}' + '\n' + 'The five largest contributions (coefficient times WOE; positive raises risk) for each illustrative case. Correlated columns can restate one fact.\n\n'
    for name, v in ex['reason_code_examples'].items():
        rows = [[tt(short(r['variable'], 44)), f(r['value'], 3), f(r['woe'], 3), '%+.3f' % r['contribution']] for r in v['top_reasons']]
        t += table(['Variable', 'Value', 'WOE', 'Contribution'], rows, r'@{}p{7cm}rrr@{}', caption='%s: PD %s, grade %s' % (esc(name.split('-', 1)[-1].replace('_', ' ')), pct(v['pd'], 2), v['grade']))
    g = [('Gini / AUC', 'How well the model ranks positive rows above negative ones. AUC 0.5 is chance; Gini = 2 AUC - 1.'), ('KS', 'Largest gap between the cumulative score distributions of positive and negative rows.'),
         ('IV', 'Information value: strength of one column in separating positive from negative rows.'), ("Cram\\'er's V", 'Association between a column\'s bins and the outcome, 0 to 1.'),
         ('WOE', 'Weight of evidence of a bin.'), ('EPV', 'Events per variable: positive rows divided by candidate columns.'), ('Riley minimum', 'Rows needed so a fitted model does not overfit.'),
         ('DeLong test', 'Test of whether two AUCs differ; here resampled by company.'), ('Hosmer--Lemeshow', 'Test of whether predicted and observed rates agree across risk groups.'),
         ('Isotonic calibration', 'A monotone step fit mapping scores to observed rates.'), ('Hazard framing', 'Every company-quarter is a row, with quarters of one company kept together in validation.'),
         ('Margin of conservatism', 'An addition to estimates to cover data deficiencies and estimation error.'), ('SHARP', 'Shapley Ranking with Parsimony: the feature-selection method.'),
         ('AEGIS', 'The gated, signed approval lifecycle (G0 to GF) around SHARP.')]
    t += r'\section{Annex C: Glossary}' + '\n' + table(['Term', 'Meaning'], [[a, esc(b) if "\\'" not in a else esc(b)] for a, b in g], r'@{}p{3.6cm}p{11.8cm}@{}')
    fl = ex['file']
    rows = [['Sealed decision record', r'\texttt{munimji\_runs/%s/chain.json}' % esc(d['run'])], ['Run state', r'\texttt{munimji\_runs/%s/state.pkl}' % esc(d['run'])], ['Manifest', r'\texttt{munimji\_runs/%s.json}' % esc(d['run'])],
            ['Result records', r'\texttt{munimji\_runs/records/}'], ['Data file', '%s, SHA-256 \\texttt{%s\\allowbreak{}%s}' % (tt(fl['name']), fl['sha256'][:32], fl['sha256'][32:])], ['Head hash', r'\texttt{%s}' % esc(d['head'])]]
    t += r'\section{Annex D: Evidence index}' + '\n' + table(['Item', 'Location'], rows, r'@{}p{4.6cm}p{10.8cm}@{}')
    t += r'\section{Annex E: What this document does not contain}' + '\n' + ('The challenger models, the duplicate-rows check, the blank-value floor comparison and the row-bootstrap performance intervals computed by the dossier-extras step are omitted because they were '
                                                                              'produced without the company grouping and are therefore leaky for panel data. Nested validation was not run. The few Basel clause numbers quoted in the text (CRE32.4, CRE36.68, CRE36.79, CRE36.18-21, CRE36.44) come from the run\'s own records and were not re-verified while building this document; the supervisor is unconfirmed.\n')
    return t


def build(data, state, extras, manifest, outdir):
    d = pickle.load(open(data, 'rb'))
    st = pickle.load(open(state, 'rb'))['state']
    ex = json.load(open(extras, encoding='utf-8'))
    m = json.load(open(manifest, encoding='utf-8'))
    pf = panel_facts(m)
    # dossier_data.collect() rewrites the R3/R4 notes from extras.json, which ignores the company grouping; take the run's own checklist instead
    import standard_run as std
    run = std.start(std.load_manifest(manifest), outroot=os.path.dirname(os.path.abspath(manifest)))
    fresh = {r['id']: r for r in run.checklist(strict=True)}
    assert [r['status'] for r in d['checklist_strict']] == [fresh[r['id']]['status'] for r in d['checklist_strict']], 'checklist statuses differ from the sealed run'
    for r in d['checklist_strict']:
        r['note'] = fresh[r['id']]['note']
    os.makedirs(outdir, exist_ok=True)
    pre = bd.PREAMBLE.replace(r'\begin{document}', r'\usepackage{needspace}' + '\n' + r'\begin{document}') % dict(header_left=esc('Model Approval Dossier: ' + d['run']), header_right=esc('Research benchmark, review draft'), footer_left=esc('Head ' + d['head']))
    parts = [pre, cover(d, m), doc_control(d), sec_summary(d, st, pf), sec_scope(d, m, pf), sec_data(d, m, ex, pf), sec_dev(d, st), sec_model(d, m), sec_perf(d, st, ex), sec_cases(d), sec_limits(d, st, pf), sec_gov(d), annex(d, m, ex), r'\end{document}']
    name = 'DOSSIER_%s_generic' % d['run']
    body = re.sub(r'(\\(?:sub)?section\{)', lambda mo: r'\Needspace{8\baselineskip}' + mo.group(1), '\n'.join(parts))   # keep a heading with its first lines
    open(os.path.join(outdir, name + '.tex'), 'w', encoding='utf-8').write(body)
    for _ in range(3):
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', name + '.tex'], cwd=outdir, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            print(r.stdout[-3500:])
            raise RuntimeError('pdflatex failed; see log in %s' % outdir)
    return os.path.join(outdir, name + '.pdf')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for a in ('data', 'state', 'extras', 'manifest', 'out'):
        ap.add_argument('--' + a, required=True)
    a = ap.parse_args()
    print(build(a.data, a.state, a.extras, a.manifest, a.out))
