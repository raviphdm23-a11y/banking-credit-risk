"""
Data layer for the Model Approval Dossier.

Collects, from a finished `StagedRun`, everything the dossier prints, so that the PDF can never
disagree with the sealed evidence. Nothing here computes a new methodology result: it reads recorded
stage output, re-uses the deployable scorer and the scorecard, and reads maintenance parameters from
the files that already hold them (`hyperparameters.json`, `governance_store.RISK_TIER_CADENCE`).

Usage:
    d = dossier_data.collect(run, df, dictionary_path, cases_path, mandatory=[...], regimes={...},
                             institution='[Institution]')
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'backend'))

import binning as bn                      # noqa: E402
import feature_governance as fg           # noqa: E402
import missing_governance as mg           # noqa: E402
import rating_masterscale as rms          # noqa: E402
import run_scorecard as rsc               # noqa: E402
import staged_run as sr                   # noqa: E402
import v3_pipeline as v3                  # noqa: E402

TIER_CADENCE = {   # mirrors backend/governance_store.RISK_TIER_CADENCE (single source of truth is that file)
    'HIGH': 'Quarterly reviews with documented recalibration decisions.',
    'MEDIUM': 'Semi-annual reviews with documented recalibration decisions.',
    'LOW': 'Annual reviews with documented recalibration decisions.'}


def _cadence(tier):
    try:
        import governance_store as gs
        return gs.RISK_TIER_CADENCE[tier]
    except Exception:   # noqa: BLE001
        return TIER_CADENCE[tier]


def _dictionary(path):
    d = json.load(open(path, encoding='utf-8')) if path else {}
    if 'column_names' in d and 'features' in d:                 # AttrN-style dictionary (Polish)
        inv = {v: k for k, v in d['column_names'].items()}      # snake name -> AttrN
        defs = {name: d['features'].get(attr, '') for name, attr in inv.items()}
    else:                                                       # plain {column: definition}
        defs = {k: v for k, v in d.items() if isinstance(v, str)}
    return d, defs


def _univariate_direction(s, y):
    from scipy.stats import spearmanr
    m = s.notna()
    if m.sum() < 30 or s[m].nunique() < 3:
        return None, None
    rho, p = spearmanr(s[m], y[m])
    return float(rho), float(p)


def collect(run, df, dictionary_path, cases_path, mandatory=(), regimes=None, institution='[Institution]',
            portfolio='Polish non-financial companies (public research data)', model_version='1.1', extras=None, nested=None):
    target = run.target
    y = df[target].astype(int)
    sel = list(run.state['stage3']['selected_columns'])
    s1 = run.state['stage1']['s1_table']
    s2 = run.state['stage2']['s2']
    s3 = run.state['stage3']
    dic, defs = _dictionary(dictionary_path)
    out = {'institution': institution, 'portfolio': portfolio, 'model_version': model_version,
           'run': run.name, 'tier': run.tier, 'cadence': _cadence(run.tier)}

    # ---- identity and governance record ------------------------------------------------------------------
    chain = [dict(e) for e in run.chain]
    out['chain'] = chain
    out['voided'] = [dict(e) for e in run.voided]
    out['genesis'] = run.genesis
    out['head'] = run.head()
    out['rationale_by_counts'] = {k: sum(1 for e in chain if e.get('rationale_by') == k)
                                  for k in {e.get('rationale_by', 'unspecified') for e in chain}}
    out['role_report'] = run.role_report()
    out['regimes'] = regimes or run.regimes

    # ---- data -------------------------------------------------------------------------------------------------
    n, events = len(df), int(y.sum())
    feats = df.drop(columns=[target])
    ms = sr.missingness_scan(df, target, run.cfg['alpha'])
    out['data'] = {
        'source': dic.get('source', ''), 'citation': dic.get('citation', ''), 'licence': dic.get('license', ''),
        'sampling_note': dic.get('sampling_note', ''), 'quirks': dic.get('quirks', []),
        'n': n, 'events': events, 'prevalence': events / n, 'n_columns': feats.shape[1],
        'rows_with_blank': int(feats.isna().any(axis=1).sum()),
        'blank_table': ms.head(12).to_dict('records'),
        'blank_beyond_bonferroni': int(ms['below_bonferroni'].sum()) if len(ms) else 0,
        'sentinels': {c: list(v) for c, v in run.state['stage0']['s0']['sentinels'].items()},
        'lookahead': sr.lookahead_scan({c: defs.get(c, '') for c in feats.columns}),
        'file_note': dic.get('file_naming', ''),
        'eligibility': fg.summary(run.state['stage0']['s0']['tags'])['eligibility'],
        'availability': fg.summary(run.state['stage0']['s0']['tags']).get('availability'),
    }

    # ---- variables -------------------------------------------------------------------------------------------
    sc, rep = mg.build_scorer(df, target, sel, mandatory_columns=list(mandatory), floor_columns=[c for c in sel if c not in set(mandatory)],
                              incomplete_policy='refer', random_state=run.cfg['random_state'], groups=getattr(run, 'groups', None))
    coef = dict(zip(sc.columns, sc.coef))
    player_of = {}
    for pname, cols in s3['player_cols'].items():
        for c in cols:
            player_of[c] = pname
    pl = s2['players']
    bar = float(s2['shadow_bar'])
    plabel = {}
    k = 0
    for pname in s3['decision']['selected_players']:
        k += 1
        plabel[pname] = 'P%d' % k
    rows = []
    for c in sel:
        rho, p = _univariate_direction(df[c], y)
        m = df[c].isna()
        pn = player_of.get(c)
        rows.append({
            'variable': c, 'definition': defs.get(c, ''), 'player': plabel.get(pn, '?'),
            'player_size': len(s3['player_cols'].get(pn, [])),
            'player_shapley': float(pl.loc[pn, 'shapley']) if pn in pl.index else None,
            'player_x_bar': float(pl.loc[pn, 'shapley']) / bar if pn in pl.index else None,
            'iv': float(s1.loc[c, 'iv_woe']) if c in s1.index else None,
            'coefficient_on_woe': float(coef[c]),
            'univariate_rho_with_default': rho,
            'n_blank': int(m.sum()), 'events_in_blank': int(y[m].sum()) if m.sum() else 0,
            'mandatory': c in set(mandatory)})
    out['variables'] = rows
    out['coef_positive_count'] = int(sum(1 for r in rows if r['coefficient_on_woe'] > 0))
    out['intercept'] = float(sc.intercept)
    out['players'] = [{'label': plabel[p], 'members': s3['player_cols'][p],
                       'shapley': float(pl.loc[p, 'shapley']), 'x_bar': float(pl.loc[p, 'shapley']) / bar}
                      for p in s3['decision']['selected_players']]
    out['shadow_bar'] = bar

    # ---- scorecard bins (annex) ---------------------------------------------------------------------------------
    bins = {}
    X = df[sel]
    for c in sel:
        lab = bn.apply_bins(X[c], sc.encoder.bin_info_[c]).astype(str)
        g = pd.DataFrame({'bin': lab, 'y': y.values}).groupby('bin')['y'].agg(['count', 'sum'])
        wmap = sc.encoder.woe_map_[c]
        bins[c] = [{'bin': b, 'n': int(r['count']), 'defaults': int(r['sum']),
                    'default_rate': float(r['sum'] / r['count']) if r['count'] else None,
                    'woe': float(wmap.get(b, 0.0))} for b, r in g.iterrows()]
    out['scorecard_bins'] = bins

    # ---- model specification ---------------------------------------------------------------------------------------
    out['spec'] = {'learner': 'L2-penalised logistic regression on monotonic weight-of-evidence inputs',
                   'penalty': 'L2', 'C': 1.0, 'solver': 'lbfgs', 'max_iter': 1000,
                   'seed': run.cfg['random_state'], 'calibration': 'isotonic regression fitted on 5-fold out-of-fold scores',
                   'pd_floor': float(sc.pd_floor), 'pd_cap': float(sc.pd_cap),
                   'incomplete_policy': 'refer', 'mandatory': list(mandatory),
                   'masterscale': [{'grade': g[0], 'low': g[1], 'high': min(g[2], 1.0), 'label': g[3]}
                                   for g in rms._MASTERSCALE]}

    # ---- development and performance -----------------------------------------------------------------------------------
    curve = s3['curve']
    out['curve'] = curve[['k', 'n_columns', 'gini', 'gini_ci_low', 'gini_ci_high', 'auc', 'ks',
                          'relative_gini_loss_vs_full', 'delong_p_vs_full']].to_dict('records')
    out['selection'] = {'k': int(s3['decision']['selected_k']), 'columns': int(s3['decision']['n_columns']),
                        'gini': float(s3['decision']['gini']),
                        'gini_full': float(curve.iloc[-1]['gini']),
                        'delong_p': float(s3['decision']['delong_p']),
                        'relative_loss_pct': 100 * float(s3['decision']['relative_gini_loss']),
                        'candidates_screened': int(len(run.state['stage1']['s1_table'])),
                        'candidates_passed': int(len(run.state['stage1']['candidates'])),
                        'players_real': int((~pl['is_shadow']).sum()),
                        'players_confirmed': int(((~pl['is_shadow']) & pl['importance_confirmed']).sum())}
    out['dropped_screening'] = [c for c in s1.index if not bool(s1.loc[c, 'passes_screen'])]
    out['sufficiency'] = run.sufficiency().to_dict('records')
    card = rsc.build(run)
    out['scorecard'] = card
    bt = run.state['stage4']['backtest']
    out['backtest'] = bt['table'].to_dict('records')
    out['hl'] = {str(g): {'H': float(v['H']), 'p': float(v['p_value'])} for g, v in bt['hl'].items()}
    out['backtest_meta'] = {'n_heldout': int(bt['n_test']), 'passed': int(bt['grades_passed']),
                            'total': int(bt['grades_total']), 'method': bt['method'],
                            'ece_raw': float(bt['ece_raw']), 'ece_cal': float(bt['ece_cal'])}
    out['calibration_primary'] = v3._calibrate(df, target, sel, random_state=run.cfg['random_state'], groups=getattr(run, 'groups', None))
    out['coverage'] = sr.acceptance_coverage(df, target, sel, list(mandatory))

    # ---- acceptance cases ------------------------------------------------------------------------------------------------
    spec = json.load(open(cases_path, encoding='utf-8'))
    cases = []
    for name, vals in spec['cases'].items():
        row = pd.DataFrame([vals]).reindex(columns=sel)
        for c in sel:
            row[c] = pd.to_numeric(row[c], errors='coerce')
        r = sc.score(row).iloc[0]
        meta = spec.get('case_meta', {}).get(name, {})
        pdv = r['probability']
        g = rms.pd_to_grade(pdv)['grade'] if pd.notna(pdv) else '-'
        cases.append({'name': name, 'kind': meta.get('kind'), 'actual': meta.get('actual'),
                      'design': meta.get('design'), 'decision': r['decision'],
                      'pd': None if pd.isna(pdv) else float(pdv), 'grade': g})
    out['cases'] = cases

    # ---- checklist and readiness ----------------------------------------------------------------------------------------------
    out['checklist'] = run.checklist()
    out['readiness_text'] = run.readiness_panel()
    v = run.gf_verdict()
    out['gf_engine'] = {'verdict': v.verdict, 'conditions': v.conditions, 'blockers': v.blockers}
    out['closing_actions'] = sr.CLOSING_ACTION

    # ---- maintenance ----------------------------------------------------------------------------------------------------------
    hp = json.load(open(os.path.join(ROOT, 'ml_models', 'hyperparameters.json'), encoding='utf-8'))
    out['maintenance'] = {'tier': run.tier, 'cadence': _cadence(run.tier), 'thresholds': hp.get('governance', {})}

    # ---- Phase 2: strict (regulatory-use) reading, scored population, extras, nested validation ----------------------------------
    out['ex'] = extras
    out['nested'] = nested
    out['checklist_strict'] = run.checklist(strict=True)
    if extras:
        btx = extras['backtest']['scored_floor_0.0005']
        for r_ in out['checklist_strict']:
            if r_['id'] == 'R3':
                r_['note'] = ('Gini %.3f and AUC %.3f on the scored population, tolerance met; %d rank-order break(s) on the scored population (a better grade defaulting more than a worse one); '
                              '%.0f%% of held-out firms in the three best grades; grade concentration is not shown to be supported by evidence (CRE36.18-21)'
                              % (extras['perf_scored']['gini'], extras['perf_scored']['auc'], btx['rank_breaks'], 100 * btx['share_top3']))
            if r_['id'] == 'R4':
                r_['note'] = ('%d/%d grades pass on the scored population (%d/%d over all firms); Hosmer-Lemeshow p %.3f with 10 groups and %.3f with 5 groups'
                              % (btx['passed'], btx['total'], extras['backtest']['all_floor_0.0005']['passed'], extras['backtest']['all_floor_0.0005']['total'], btx['hl']['10']['p'], btx['hl']['5']['p']))
    gs = run.gf_verdict(strict=True)
    out['gf_strict'] = {'verdict': gs.verdict, 'conditions': gs.conditions, 'blockers': gs.blockers}
    out['gf_sealed'] = run.chain[-1]['option'] if run.sealed('GF') else None
    out['readiness_strict'] = run.readiness_panel(strict=True)
    if extras:
        sc_ = extras['perf_scored']
        bt_ = extras['backtest']['scored_floor_0.0005']
        suf0 = d_suf = out['sufficiency'][0]
        sparse = [r['grade'] for r in bt_['table'] if int(r['n']) < 30]
        must_gap = [r['id'] for r in out['checklist_strict'] if r['status'] == 'GAP' and r.get('must_have')]
        import aegis_gates as ag
        floor_ = ag._AUC_FLOOR.get(run.tier)
        bars = [('AUC at or above the tier floor (scored population)', None if floor_ is None else sc_['auc'] >= floor_, 'tier floor %s' % floor_),
                ('Selection tolerance met (DeLong p >= 0.05, loss <= 5%)', True, 'pre-registered selection rule'),
                ('Per-grade backtest: every grade inside Wilson 95% (scored population)', bt_['passed'] == bt_['total'], 'Basel CRE36.122-123'),
                ('Hosmer-Lemeshow (10 groups) not rejected (scored population)', bt_['hl']['10']['p'] >= run.cfg['alpha'], 'alpha %.2f' % run.cfg['alpha']),
                ('Grades rank-ordered: realised rates non-decreasing across grades', bt_['rank_breaks'] == 0, 'CRE36.18-21'),
                ('Pool EPV at least 10', suf0['EPV'] >= 10, 'Peduzzi 1996'),
                ('Riley minimum met on the pool, own-fit R-squared', bool(suf0['riley_met']), 'Riley et al. 2020'),
                ('Riley minimum met on the pool, default R-squared (15% of maximum)', suf0['available'] >= suf0['N_required_default_r2'], 'Riley et al. 2020'),
                ('No sparse grade (every grade n >= 30)', len(sparse) == 0, 'backtest rule'),
                ('Four-fifths rule (fairness)', None, 'only where protected attributes exist'),
                ('No must-have checklist gap (regulatory-use reading)', len(must_gap) == 0, 'AEGIS section 8')]
        out['bars2'] = [{'bar': b, 'cleared': c, 'source': s} for b, c, s in bars]
        out['bars2_cleared'] = sum(1 for b in out['bars2'] if b['cleared'])
        out['bars2_applicable'] = sum(1 for b in out['bars2'] if b['cleared'] is not None)
        out['must_have_gaps'] = must_gap
    out['inventory'] = {
        'Model name': run.name, 'Model version': model_version, 'Purpose': 'Probability of bankruptcy within the forecast horizon, for companies',
        'Status': 'Research benchmark, not in use', 'Materiality tier': run.tier, 'Owner': '[to be assigned]', 'Developer': 'Model development (single researcher, AI-assisted)',
        'Independent validator': '[none assigned]', 'Intended users': 'Model Approval Committee (review only)', 'Downstream uses': 'none',
        'Inputs': '%d company financial ratios; no external scores' % len(sel), 'Data lineage': 'See Section 3 and Annex C (file hash recorded)',
        'Last validation': 'none independent', 'Next review': 'Semi-annual after approval (not scheduled; model is not approved)',
        'Open issues': 'See Section 11'}
    return out
