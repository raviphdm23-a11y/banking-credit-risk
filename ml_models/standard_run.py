"""
Standard run kit: one call per step, so a NEW dataset gets every standard built into the SHARP + AEGIS flow.

What this kit does for you automatically (and what it deliberately leaves to a human) is listed in
AEGIS_GOVERNANCE.md section 11.2. In short, it wires: staged execution with gate cards, the running R1-R14 checklist
(loose and strict), sufficiency on the candidate pool with both Riley bases, primary-model calibration, the
deployed-model backtest with the 0.05% PD floor, the adverse floor on blanks, rule-based acceptance cases, the cutoff
note and sample-runs pack, scored-population / duplicates / challenger / sensitivity analyses, nested validation,
the scorecard, and the Model Approval Dossier. Humans still choose each gate option and rationale, the mandatory
field, the regimes, the roles and the history window; the kit proposes defaults and prints what it assumed.

Typical session (one dataset):

    import standard_run as std
    m   = std.load_manifest('manifests/mydata.json')
    run = std.start(m)
    print(std.present(run, 0))            # stage 0 + G0 card; then run.seal('G0', 'A', rationale, ...)
    print(std.present(run, 1)) ...        # stages 1-4, one gate at a time
    print(std.prepare_g5(run, m))         # cases, cutoff note, sample runs, G5 card
    print(std.present(run, 'GF'))         # both readiness panels and engine verdicts before the final ruling
    std.write_records(run, m)             # SHARP_<name>.md and AEGIS_RUN_<name>.md
    std.build_dossier(run, m, phase=1)    # extras (+ nested validation in the background) and the PDF
"""
import json
import os
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'paper analysis', 'draft one')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'backend'))
import missing_governance as mg      # noqa: E402
import rating_masterscale as rms     # noqa: E402
import staged_run as sr              # noqa: E402

MANIFEST_DEFAULTS = {
    'tier': 'MEDIUM', 'target': 'target', 'mandatory_columns': [], 'refer_column': None,
    'roles': {'Data Steward': 'Researcher', 'Model Validator': 'Researcher', 'Risk Officer': 'Researcher'},
    'history_years': None, 'live_use': False, 'jurisdiction': 'EU', 'borrower_type': 'firm',
    'institution': '[Institution]', 'portfolio': '', 'dictionary': None, 'model_version': '1.0',
    # Indian (RBI) pack facts, read when jurisdiction is IN (see staged_run.StagedRun.india); None = not declared.
    # Set "india_pack": false in a manifest to switch the Indian rows off for an IN dataset.
    'india': None, 'india_pack': True,
}


def load_manifest(path):
    m = dict(MANIFEST_DEFAULTS)
    m.update(json.load(open(path, encoding='utf-8')))
    for k in ('name', 'csv'):
        if k not in m:
            raise ValueError('manifest needs %r' % k)
    return m


def _dictionary(path):
    if not path:
        return None
    d = json.load(open(path, encoding='utf-8'))
    if 'features' in d and 'column_names' in d:             # AttrN dictionary (Polish style)
        return {d['column_names'][a]: t for a, t in d['features'].items() if a in d['column_names']}
    return {k: v for k, v in d.items() if isinstance(v, str)}


def default_regimes(m):
    """Which regimes bind, by jurisdiction and borrower type. A proposal the committee confirms at G0."""
    j, b = m['jurisdiction'].upper(), m['borrower_type'].lower()
    firm = b == 'firm'
    eu = j in ('EU', 'PL', 'DE', 'FR', 'IT', 'ES', 'NL')
    out = {
        'UK_PRA_SS1_23': {'binding': j == 'UK', 'reason': 'scope is set by the firm (a UK-incorporated bank with internal-model approval), not by where the exposure sits'},
        'EU_AI_ACT_HIGH_RISK': {'binding': (eu and not firm), 'reason': 'Annex III point 5(b) covers natural persons only; holds only while a legal-entity scope gate is enforced' if firm else 'natural-person credit scoring in the EU is high-risk (Annex III 5(b))'},
        'EU_AI_ACT_HUMAN_OVERSIGHT': {'binding': (eu and not firm), 'reason': 'applies to high-risk systems; follows the high-risk row'},
        'US_ECOA_REG_B': {'binding': j == 'US', 'reason': 'ECOA and Regulation B also reach business credit; they apply when a US creditor is involved, not because of the borrower type'},
    }
    if j == 'IN' and m.get('india_pack', True):
        # Indian (RBI) pack. Declared binding so that rows R15-R20 are derived: the model is assessed as if used by an
        # RBI-regulated lender. The Draft is a consultation text, so the rows are conditions, not must-haves (regime_registry).
        out['IN_RBI_MRM_DRAFT_2026'] = {'binding': True, 'reason': 'assessed as if used by an RBI-regulated lender; RBI Draft Guidance on Model Risk Management (June 2026) is a consultation text, not yet binding'}
        out['IN_RBI_FREE_AI_2025'] = {'binding': True, 'reason': 'assessed as best practice for an RBI-regulated lender; FREE-AI (13 Aug 2025) is a recommendations report, not a regulation'}
    return out


def start(m, outroot=None):
    df = pd.read_csv(m['csv'] if os.path.isabs(m['csv']) else os.path.join(ROOT, m['csv']))
    groups = time_values = None
    if m.get('panel'):                       # panel manifest: panel_adapter reshapes and returns the entity groups + row time
        import panel_adapter as pa
        pm = dict(m['panel'], target=m['target'])
        t = pd.to_datetime(df[pm['time_col']])
        df = df.assign(**{pm['time_col']: t.dt.year * 4 + (t.dt.month - 1) // 3})   # quarter index, numeric for the OOT split
        prep = pa.prepare(df, pm)
        df, groups, time_values = prep['frame'], prep['groups'], prep['time']
    outdir = os.path.join(outroot or os.path.join(ROOT, 'sharp_runs_staged'), m['name'])
    run = sr.StagedRun(df, m['target'], m['name'], outdir, tier=m['tier'], groups=groups, time_values=time_values, roles=m['roles'],
                       history_years=m['history_years'], dictionary=_dictionary(m['dictionary']),
                       regimes=m.get('regimes') or default_regimes(m), live_use=m['live_use'], india=m.get('india'))
    return run.load()


# ------------------------------------------------------------------------------------------------ presenting a gate
def _checklist_lines(run, strict):
    return '\n'.join('  %s %s - %s' % (r['id'], r['status'], r['note'][:150]) for r in run.checklist(strict))


def present(run, n):
    """Run stage n if it has not run, and return EVERYTHING a decision maker needs for gate n: the full stage output,
    sufficiency on every basis, the code-emitted gate card, and the running checklist."""
    out = []
    if n == 'GF':
        gl, gs = run.gf_verdict(), run.gf_verdict(strict=True)
        return '\n'.join(['FINAL RULING INPUTS - %s' % run.name, '', 'READINESS (earlier reading):', run.readiness_panel(), '', 'READINESS (regulatory-use reading):', run.readiness_panel(strict=True), '',
                          'Engine verdict, earlier reading: %s %s' % (gl.verdict, gl.conditions), 'Engine verdict, regulatory-use reading: %s %s' % (gs.verdict, gs.blockers or gs.conditions)])
    stage = {0: run.stage0, 1: run.stage1, 2: run.stage2, 3: run.stage3, 4: run.stage4}[n]
    if 'stage%d' % n not in run.state:
        stage()
        run.save()
    out.append(run.show_stage(n))
    if n >= 1:
        out.append('\nSUFFICIENCY (governing basis = candidate pool):\n' + run.sufficiency().to_string())
    out.append('\n' + run.show_gate('G%d' % n))
    out.append('\nCHECKLIST SO FAR (earlier reading):\n' + _checklist_lines(run, False))
    out.append('\nCHECKLIST SO FAR (regulatory-use reading):\n' + _checklist_lines(run, True))
    return '\n'.join(out)


# ------------------------------------------------------------------------------------------------ acceptance cases
def auto_cases(run, m):
    """Rule-based acceptance cases (no hand picking): lowest-PD repaid, median repaid, median bankrupt, first bankrupt
    with a blank mandatory field, the bankrupt firm rated safest (an honest false negative), and three synthetic
    composites built from observed value extremes. Scored through the deployable scorer with every standard control."""
    df, target = run.df, run.target
    sel = list(run.state['stage3']['selected_columns'])
    mand = list(m['mandatory_columns'])
    y = df[target].astype(int)
    sc, _ = mg.build_scorer(df, target, sel, mandatory_columns=mand, incomplete_policy='refer', random_state=run.cfg['random_state'], groups=run.groups)
    r = sc.score(df[sel])
    ok = (r['decision'] == 'SCORE').values
    pr = r['probability'].values.astype(float)
    idx = np.arange(len(df))
    ok0, ok1 = idx[ok & (y.values == 0)], idx[ok & (y.values == 1)]
    pick = {}
    pick['R1_lowest_PD_repaid'] = int(ok0[np.argmin(pr[ok0])])
    pick['R2_median_PD_repaid'] = int(ok0[np.argsort(pr[ok0])[len(ok0) // 2]])
    noun = ((m.get('dossier') or {}).get('event_noun')) or 'bankrupt'      # what a positive row is called (Polish data: bankrupt; annual data: defaulter)
    pick['R3_median_PD_%s' % noun] = int(ok1[np.argsort(pr[ok1])[len(ok1) // 2]])
    dec = r['decision'].values
    ref_hard = idx[(dec == 'REFER') & (y.values == 1)]          # a positive row referred because the mandatory field is blank
    ref_soft = idx[(dec == 'SCORE_FLAGGED') & (y.values == 1)]  # a positive row scored but flagged for a blank in another variable
    if len(ref_hard):
        pick['R4_%s_referred_blank_mandatory' % noun] = int(ref_hard[0])
    elif len(ref_soft):
        pick['R4_%s_flagged_blank_other_variable' % noun] = int(ref_soft[0])
    pick['R5_%s_rated_safest' % noun] = int(ok1[np.argmin(pr[ok1])])
    row = lambda i: {c: (None if pd.isna(df.at[i, c]) else float(df.at[i, c])) for c in sel}   # noqa: E731
    cases = {('%s-%s' % (m['name'], k)): row(i) for k, i in pick.items()}
    meta = {('%s-%s' % (m['name'], k)): {'kind': 'real', 'actual': int(y.iloc[i])} for k, i in pick.items()}
    safe, risk, ext = {}, {}, {}
    for c in sel:
        up = df.loc[y == 1, c].median() > df.loc[y == 0, c].median()
        lo, hi = df[c].quantile(.05), df[c].quantile(.95)
        safe[c] = float(lo if up else hi); risk[c] = float(hi if up else lo)
        ext[c] = float(df[c].max() if up else df[c].min())
    for nm, vals, des in (('S1_safe_extreme', safe, 'repaid'), ('S2_risky_extreme', risk, 'default'), ('S3_observed_extreme', ext, 'default')):
        key = '%s-%s' % (m['name'], nm)
        cases[key] = vals; meta[key] = {'kind': 'synthetic', 'design': des}
    spec = {'title': '%s, version %s controls' % (m['name'], m['model_version']), 'dataset': (m['csv'].replace('\\', '/').split('data/ml_lab/datasets/', 1)[1] if 'data/ml_lab/datasets/' in m['csv'].replace('\\', '/') else os.path.basename(m['csv'])), 'target': target,
            'selected_columns': sel, 'mandatory_columns': mand, 'floor_columns': [c for c in sel if c not in set(mand)],
            'incomplete_policy': 'refer', 'group_column': (m.get('panel') or {}).get('entity_id'), 'cases': cases, 'case_meta': meta}
    path = os.path.join(DOCS, 'acceptance_cases', '%s.json' % m['name'].lower())
    json.dump(spec, open(path, 'w', encoding='utf-8'), indent=1)
    return path


def prepare_g5(run, m):
    """Everything G5 needs: acceptance cases, sample-runs pack, cutoff note, coverage report; returns the G5 card text."""
    cases = auto_cases(run, m)
    pack = os.path.join(DOCS, 'SAMPLE_RUNS_%s.md' % m['name'])
    subprocess.run([sys.executable, os.path.join(HERE, 'score_acceptance_cases.py'), '--cases', cases, '--out', pack], check=True, cwd=ROOT)
    cov = sr.acceptance_coverage(run.df, run.target, list(run.state['stage3']['selected_columns']), list(m['mandatory_columns']), groups=run.groups)
    run.record_g5(True, True, True, cov, override_policy=bool(((m.get('india') or {}).get('override_path') or '').strip()))
    if run._in_active():
        run.write_inventory_card()          # Indian pack: evidence for R17 (RBI Draft paras 21-24)
    note = os.path.join(DOCS, 'AEGIS_%s_CUTOFF_POLICY.md' % m['name'])
    ps = open(os.path.join(DOCS, 'AEGIS_POLISH_1YR_CUTOFF_POLICY.md'), encoding='utf-8').read() if False else None
    with open(note, 'w', encoding='utf-8') as fh:
        fh.write(_cutoff_note(run, m, cov))
    run.save()
    ev = {'tier': run.tier, 'cutoff_policy_present': True, 'acceptance_pack_present': True, 'mandatory_field_gate': bool(m['mandatory_columns']),
          'adverse_fallback': True, 'reason_codes': True}
    return ('G5 DELIVERABLES WRITTEN\n  acceptance cases: %s\n  sample runs: %s\n  cutoff note: %s\n  controls NOT exercised by the data: %s\n\n%s\n\nCHECKLIST (regulatory-use reading):\n%s'
            % (cases, pack, note, cov['not_exercised'] or 'none', run.show_gate('G5', evidence=ev), _checklist_lines(run, True)))


def _cutoff_note(run, m, cov):
    sel = run.state['stage3']['selected_columns']
    mand = ', '.join('`%s`' % c for c in m['mandatory_columns']) or 'none'
    return """# AEGIS decisioning note - {name} (version {ver} controls)

**Run:** {name} - gate G5 (deployment governance). **Model:** WOE-logistic scorer, {k} players / {n} columns, tier {tier}.

## 1. What this note DOES and DOES NOT set
It governs how a PD is produced and explained: calibrated PD, PD floor 0.05% / cap 99.9% (Basel CRE32.4; CRR Art 160(1)/163(1)), rating grade, exact additive-WOE reason codes.
It does **not** set an accept/decline cutoff or a price: those are the institution's own inputs.

## 2. Scoring configuration
| Control | Value |
|---|---|
| Mandatory field (blank -> refer) | {mand} |
| Blank values (all other variables) | Adverse floor: a blank scores no better than the worst real bin; application flagged |
| PD floor / cap | 0.05% / 99.9% (always on) |
| Reason codes | exact additive WOE |
| Legal-form gate | {legal} |
| Override policy | none documented - to be written by the model owner |

## 3. Acceptance demonstration
`SAMPLE_RUNS_{name}.md`. PD floor exercised: {fl}; PD cap exercised: {cp}; mandatory-field referral exercised: {rf}. Controls the data does not exercise: {ne}.
""".format(name=run.name, ver=m['model_version'], k=len(run.state['stage3']['decision']['selected_players']), n=len(sel), tier=run.tier, mand=mand,
           fl=cov['floor_exercised'], cp=cov['cap_exercised'], rf=cov['refer_exercised'], ne=', '.join(cov['not_exercised']) or 'none',
           legal=('a non-company applicant is referred (needed if the model is built for legal entities)' if m.get('legal_form_gate') else
                  'none configured: the data holds no legal-form field, so every applicant is scored and none is referred for legal form'))


# ------------------------------------------------------------------------------------------------ Indian (RBI) diagnostics
def run_rbi_checks(run, m, segments=None, days_to_event=None, select_fn=None, seeds=(42, 7, 11, 23, 99)):
    """Reporting-only diagnostics behind R18/R19 (RBI Draft para 54, 42). Each needs its inputs; one without inputs is
    skipped and its sub-item stays PARTIAL. Nothing here decides a gate.
      segments       : array of segment labels per row (for example the size band)  -> 54(3)
      days_to_event  : days from statement date to default per row (NaN if none)     -> 54(5)
      select_fn      : callable(seed) -> selected feature names (re-runs attribution and selection) -> 54(6)
    Returns the dict of what was recorded."""
    import rbi_checks as rbc
    from panel_adapter import temporal_split
    df, target = run.df, run.target
    sel = list(run.state['stage3']['selected_columns'])
    mand = list(m['mandatory_columns'])
    rs = run.cfg['random_state']
    grade_fn = lambda p: rms.pd_to_grade(p)['grade']      # noqa: E731
    out = {}
    sc, _ = mg.build_scorer(df, target, sel, mandatory_columns=mand, incomplete_policy='refer', random_state=rs, groups=run.groups)
    p_all = sc.score(df[sel])['probability'].values.astype(float)
    if run.time_values is not None:                       # 54(7): training period against test period, same split as the OOT test
        tr, te, _t = temporal_split(pd.DataFrame({'t': np.asarray(run.time_values)}), 't', run.cfg['oot_test_frac'])
        out['feature_drift'] = run.record_rbi_check('feature_drift', rbc.feature_drift(df[tr], df[te], sel))
        out['score_drift'] = run.record_rbi_check('score_drift', rbc.score_drift(p_all[tr], p_all[te]))
    out['row_order'] = run.record_rbi_check('row_order', rbc.row_order_invariance(
        df, target, sel, mg.build_scorer, groups=run.groups, mandatory_columns=mand, incomplete_policy='refer', random_state=rs))
    if segments is not None:
        out['segments'] = run.record_rbi_check('segments', rbc.segment_assessment(df[target].values, p_all, segments))
    if days_to_event is not None:
        out['label_lag'] = run.record_rbi_check('label_lag', rbc.label_lag_sensitivity(df[target].values, p_all, days_to_event))
    out['sign_audit'] = run.record_rbi_check('sign_audit', rbc.coefficient_sign_audit(
        sc.columns, sc.coef, corr=df[sel].apply(pd.to_numeric, errors='coerce').corr(method='spearman')))
    out['perturbation'] = run.record_rbi_check('perturbation', rbc.perturbation_sensitivity(sc, df, sel, grade_fn))
    out['outlier'] = run.record_rbi_check('outlier', rbc.outlier_sensitivity(sc, df, sel))
    small = (m.get('india') or {}).get('benchmark_small_columns')
    if small:
        X = df[sel].apply(pd.to_numeric, errors='coerce')
        out['benchmark'] = run.record_rbi_check('benchmark', rbc.benchmark_models(X, df[target].values, small, groups=run.groups, seed=rs))
    if select_fn is not None:
        out['seed_stability'] = run.record_rbi_check('seed_stability', rbc.selection_stability(select_fn, seeds))
    s4 = run.state.get('stage4') or {}
    out['material_change'] = run.record_rbi_check('material_change', rbc.material_change(oot=s4.get('oot'), drift=out.get('feature_drift')))
    run.save()
    return out


# ------------------------------------------------------------------------------------------------ records and dossier
def write_records(run, m):
    """SHARP_<name>.md (the stage report) and AEGIS_RUN_<name>.md (the sealed decision table), both generated, not typed."""
    sharp = os.path.join(DOCS, 'SHARP_%s.md' % m['name'])
    with open(sharp, 'w', encoding='utf-8') as fh:
        fh.write('# SHARP record - %s\n\n' % m['name'] + run.final_report() + '\n\n## Sufficiency\n\n' + run.sufficiency().to_markdown(index=False) + '\n')
    rows = ['| Gate | Option | Signer | Person | Rationale | Authorship | prev | entry_hash |', '|---|---|---|---|---|---|---|---|']
    for e in run.chain:
        rows.append('| %s | %s | %s | %s | %s | %s | `%s` | `%s` |' % (e['gate'], e['option'], e['signer'], e.get('person') or '', e['rationale'], e.get('rationale_by', ''), e['prev'], e['entry_hash']))
    voided = ['| %s | %s | `%s` |' % (e['gate'], e['option'], e['entry_hash']) for e in run.voided]
    aegis = os.path.join(DOCS, 'AEGIS_RUN_%s.md' % m['name'])
    with open(aegis, 'w', encoding='utf-8') as fh:
        fh.write('# AEGIS governed run - %s\n\nTier %s. Staged protocol. Rationale authorship is recorded per entry.\n\n## Sealed decisions\n\n%s\n\n' % (m['name'], run.tier, '\n'.join(rows)))
        if voided:
            fh.write('## Voided entries (kept in the audit trail)\n\n| Gate | Option | Hash |\n|---|---|---|\n%s\n\n' % '\n'.join(voided))
        fh.write('## Readiness (regulatory-use reading)\n\n```\n%s\n```\n' % run.readiness_panel(strict=True))
    return sharp, aegis


def build_dossier(run, m, phase=1, nested=True):
    """Compute the supporting analyses, start nested validation in the background, collect, and build the PDF."""
    import dossier_data as dd
    import dossier_extras as dx
    import build_dossier as bd
    base = os.path.join(DOCS, 'dossier', m['name'], 'phase%s' % phase)
    os.makedirs(base, exist_ok=True)
    csv = m['csv'] if os.path.isabs(m['csv']) else os.path.join(ROOT, m['csv'])
    mand = list(m['mandatory_columns'])
    cases = os.path.join(DOCS, 'acceptance_cases', '%s.json' % m['name'].lower())
    dic = m['dictionary'] if (m['dictionary'] and os.path.isabs(m['dictionary'])) else (os.path.join(ROOT, m['dictionary']) if m['dictionary'] else None)
    if nested:
        cmd = [sys.executable, os.path.join(HERE, 'nested_validation.py'), '--csv', csv, '--target', run.target, '--out', os.path.join(base, 'nested_validation.json')]
        if m['refer_column']:
            cmd += ['--refer-col', m['refer_column']]
        subprocess.Popen(cmd, cwd=ROOT, stdout=open(os.path.join(base, 'nested_log.txt'), 'w'), stderr=subprocess.STDOUT)
    extras = dx.compute(run, run.df, mand, m['refer_column'] or (mand[0] if mand else None), csv, dic, cases)
    json.dump(extras, open(os.path.join(base, 'extras.json'), 'w', encoding='utf-8'), indent=1, default=str)
    return base, extras


def finish_dossier(run, m, phase=1):
    """After extras.json (and, if wanted, nested_validation.json) exist: collect everything and build the PDF."""
    import pickle
    import dossier_data as dd
    import build_dossier as bd
    base = os.path.join(DOCS, 'dossier', m['name'], 'phase%s' % phase)
    extras = json.load(open(os.path.join(base, 'extras.json'), encoding='utf-8'))
    npath = os.path.join(base, 'nested_validation.json')
    nested = json.load(open(npath, encoding='utf-8')) if os.path.exists(npath) else None
    dic = m['dictionary'] if (m['dictionary'] and os.path.isabs(m['dictionary'])) else (os.path.join(ROOT, m['dictionary']) if m['dictionary'] else None)
    cases = os.path.join(DOCS, 'acceptance_cases', '%s.json' % m['name'].lower())
    d = dd.collect(run, run.df, dic, cases, mandatory=list(m['mandatory_columns']), regimes=run.regimes, institution=m['institution'],
                   portfolio=m['portfolio'] or m['name'], model_version=m['model_version'], extras=extras, nested=nested)
    pickle.dump(d, open(os.path.join(base, 'dossier_data.pkl'), 'wb'))
    return bd.build(d, base, phase)
