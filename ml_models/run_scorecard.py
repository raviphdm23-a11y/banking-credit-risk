"""
Model reliability scorecard: one page per run, comparable across datasets.

The staged flow ends in a verdict (GO / GO-WITH-CONDITIONS / NO-GO) and many tables, but no
single page that lets two runs on different datasets be set side by side. This module builds that
page from a finished (or exploratory) `StagedRun`.

Design rules (standing project rules):
* NO composite score and no weights - any weighting would be an invented parameter. The headline
  is a count of EXISTING, cited bars cleared (AUC tier floor, selection tolerance, Wilson per-grade
  backtest, Hosmer-Lemeshow, EPV >= 10, Riley minimum, no sparse grade, four-fifths rule where
  fairness is live, no must-have GAP). Nothing else is pass/fail.
* Every number is out-of-fold or held-out and comes from the run's own recorded stage output.
* No accept/decline cutoff is used (it is an institution input). Capture rates are taken at fixed
  PERCENTILES of the model's own ranking, not at a PD threshold, so F1 / precision / recall at a
  cutoff are deliberately not reported.
* The scorecard describes the model AND its data together; it does not rank methods.

Usage:
    sc = run_scorecard.build(run)             # dict
    open(...).write(run_scorecard.markdown(sc))
    run_scorecard.compare(sc_a, sc_b)         # markdown side by side
"""
import json
import os

import numpy as np
import pandas as pd

CAPTURE_PERCENTILES = (0.05, 0.10, 0.20)
FOUR_FIFTHS = 0.8          # adverse-impact bar already used by the fairness gate
EPV_RULE = 10              # Peduzzi rule of thumb already used by the sufficiency gate
# Reporting precision for the bootstrap intervals (a reporting convention, fixed for every dataset;
# it decides nothing): stratified by class so every resample keeps the event count.
BOOT_N = 1000
BOOT_SEED = 42
BOOT_LEVEL = 0.95


def _capture(y, score, q):
    """Share of all events inside the riskiest fraction q of the ranking, and lift."""
    n = len(y)
    m = int(np.ceil(q * n))
    order = np.argsort(-np.asarray(score), kind='mergesort')
    ev = int(np.asarray(y)[order[:m]].sum())
    tot = int(np.asarray(y).sum())
    cap = ev / tot if tot else float('nan')
    return cap, (cap / q if tot else float('nan'))


def _calibration_slope(y, p):
    """Logistic recalibration of out-of-fold predictions: logit(P(y=1)) = a + b*logit(p).
    b = 1 and a = 0 are ideal; b < 1 means predictions are too extreme (overfit)."""
    from sklearn.linear_model import LogisticRegression
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    x = np.log(p / (1 - p)).reshape(-1, 1)
    m = LogisticRegression(C=1e9, solver='lbfgs', max_iter=1000).fit(x, np.asarray(y).astype(int))
    return float(m.coef_[0][0]), float(m.intercept_[0])


def _bootstrap(y, p, n_boot=BOOT_N, seed=BOOT_SEED, level=BOOT_LEVEL):
    """Stratified percentile bootstrap of the out-of-fold metrics that have no closed-form interval:
    capture in the riskiest 5/10/20%, Brier skill (raw out-of-fold), ECE (raw out-of-fold) and
    calibration slope. Resamples events and non-events separately so the event count is preserved."""
    import selection as sel
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    rng = np.random.RandomState(seed)
    ev, ne = np.where(y == 1)[0], np.where(y == 0)[0]
    out = {'capture_top_5': [], 'capture_top_10': [], 'capture_top_20': [],
           'brier_skill_oof': [], 'ece_oof': [], 'calibration_slope_oof': []}
    for _ in range(n_boot):
        idx = np.concatenate([rng.choice(ev, len(ev)), rng.choice(ne, len(ne))])
        yb, pb = y[idx], p[idx]
        for q in CAPTURE_PERCENTILES:
            out['capture_top_%d' % round(100 * q)].append(_capture(yb, pb, q)[0])
        base = float(yb.mean() * (1 - yb.mean()))
        out['brier_skill_oof'].append(1 - float(np.mean((pb - yb) ** 2)) / base)
        out['ece_oof'].append(float(sel.expected_calibration_error(yb, pb)))
        out['calibration_slope_oof'].append(_calibration_slope(yb, pb)[0])
    lo, hi = 100 * (1 - level) / 2, 100 * (1 + level) / 2
    ci = {k: [float(np.percentile(v, lo)), float(np.percentile(v, hi))] for k, v in out.items()}
    point = {'brier_skill_oof': 1 - float(np.mean((p - y) ** 2)) / float(y.mean() * (1 - y.mean())),
             'ece_oof': float(sel.expected_calibration_error(y, p)),
             'calibration_slope_oof': _calibration_slope(y, p)[0]}
    for q in CAPTURE_PERCENTILES:
        point['capture_top_%d' % round(100 * q)] = _capture(y, p, q)[0]
    return {'n_boot': n_boot, 'seed': seed, 'level': level, 'point': point, 'ci': ci}


def build(run, air=None):
    """Scorecard dict from a StagedRun that has completed Stages 0-4 (gates may be unsealed, in
    which case the integrity block says so). `air` = adverse-impact ratio when fairness is live."""
    for k in ('stage1', 'stage2', 'stage3', 'stage4'):
        if k not in run.state:
            raise RuntimeError('scorecard needs stages 0-4 (missing %s)' % k)
    cfg, df, target = run.cfg, run.df, run.target
    y = df[target].astype(int).values
    n, events = len(y), int(y.sum())
    s3, s4 = run.state['stage3'], run.state['stage4']
    d = s3['decision']
    if not d['tolerance_met']:
        raise RuntimeError('no k met the selection tolerance; scorecard needs a selected model')
    k = int(d['selected_k'])
    row = s3['curve'][s3['curve']['k'] == k].iloc[0]
    full = s3['curve'].iloc[-1]
    oof = np.asarray(s3['extras']['oof_by_k'][k], dtype=float)
    cal, bt = s4['calibration'], s4['backtest']

    # 1 ranking power ------------------------------------------------------------------------
    rank = {'gini': float(row['gini']), 'gini_ci': [float(row['gini_ci_low']), float(row['gini_ci_high'])],
            'auc': float(row['auc']), 'ks': float(row['ks']), 'partial_auc': float(row['partial_auc'])}
    for q in CAPTURE_PERCENTILES:
        cap, lift = _capture(y, oof, q)
        rank['capture_top_%d' % round(100 * q)] = round(cap, 4)
        rank['lift_top_%d' % round(100 * q)] = round(lift, 2)

    boot = _bootstrap(y, oof)

    # 2 probability accuracy -----------------------------------------------------------------
    slope, intercept = _calibration_slope(y, oof)
    hl = bt['hl']
    pt = boot['point']
    # PRIMARY-MODEL figures: the out-of-fold predictions of the selected WOE-logistic model, plus the
    # held-out deployed-model ECE from the backtest. Runs recorded before 2026-10-25 carry a Stage-4
    # calibration block from an XGBoost model (legacy); the block's 'learner' field says which it is.
    acc = {'brier_baseline_always_base_rate': round(float(y.mean() * (1 - y.mean())), 4),
           'brier_skill_oof': round(pt['brier_skill_oof'], 4), 'ece_oof': round(pt['ece_oof'], 4),
           'ece_heldout_raw': float(bt['ece_raw']), 'ece_heldout_calibrated': float(bt['ece_cal']),
           'calibration_slope_oof': round(slope, 3), 'calibration_intercept_oof': round(intercept, 3),
           'hl_p_g10': float(hl[10]['p_value']) if 10 in hl else None,
           'hl_p_g5': float(hl[5]['p_value']) if 5 in hl else None}
    xgb_step = {'learner': cal.get('learner', 'xgboost (legacy record: secondary learner on an 80/20 split)'),
                'brier_baseline': float(cal['baseline_brier_always_base_rate']),
                'brier_raw': float(cal['raw_brier']), 'brier_calibrated': float(cal['calibrated_brier']),
                'ece_raw': float(cal['raw_ece']), 'ece_calibrated': float(cal['calibrated_ece']),
                'auc_calibrated': float(cal['calibrated_auc'])}

    # 3 grade reliability --------------------------------------------------------------------
    tb = bt['table']
    failing = [{'grade': str(r['grade']), 'n': int(r['n']), 'realised': round(float(r['realised']), 4),
                'expected': round(float(r['expected']), 4),
                'direction': 'under-predicts risk' if float(r['realised']) > float(r['expected'])
                else 'over-predicts risk'}
               for _, r in tb.iterrows() if not bool(r['pass'])]
    grade = {'grades_passed': int(bt['grades_passed']), 'grades_total': int(bt['grades_total']),
             'sparse_grades': [str(r['grade']) for _, r in tb.iterrows() if int(r['n']) < 30],
             'failing': failing, 'n_heldout': int(bt['n_test']), 'method': bt['method']}

    # 4 sufficiency --------------------------------------------------------------------------
    suf = run.sufficiency()
    gov = suf[suf['governing']].iloc[0]
    sel_row = suf[suf['stage'] == 'G3']
    sufficiency = {'events': events, 'n': n, 'pool_P': int(gov['P']), 'pool_epv': float(gov['EPV']),
                   'pool_riley_required': int(gov['N_required']), 'pool_riley_margin': float(gov['margin']),
                   'pool_riley_met': bool(gov['riley_met']),
                   'selected_epv': float(sel_row.iloc[0]['EPV']) if len(sel_row) else None,
                   'selected_riley_margin': float(sel_row.iloc[0]['margin']) if len(sel_row) else None}

    # 5 stability and parsimony ----------------------------------------------------------------
    pl = run.state['stage2']['s2']['players']
    real = pl[~pl['is_shadow']]
    conf = real[real['importance_confirmed']]
    bar = float(run.state['stage2']['s2']['shadow_bar'])
    stab = {'players_real': int(len(real)), 'players_confirmed': int(len(conf)),
            'weakest_confirmed_x_bar': round(float(conf['shapley'].min()) / bar, 2) if len(conf) else 0.0,
            'min_confirmation_frequency': round(float(conf['confirmation_frequency'].min()), 4) if len(conf) else None,
            'k_selected': k, 'columns_selected': int(d['n_columns']),
            'gini_retained_vs_full': round(float(row['gini']) / float(full['gini']), 4),
            'delong_p_vs_full': round(float(d['delong_p']), 4),
            'relative_gini_loss_pct': round(100 * float(d['relative_gini_loss']), 2)}

    # 6 integrity ----------------------------------------------------------------------------
    cl = run.checklist()
    st = run.state['stage0']
    ms = st.get('missingness')
    n_blank_flags = int(ms['below_bonferroni'].sum()) if ms is not None and len(ms) else None
    integrity = {'gates_sealed': [e['gate'] for e in run.chain],
                 'governed': len(run.chain) > 0,
                 'gf_verdict': (run.chain[-1]['option'] if run.sealed('GF') else None),
                 'checklist_satisfied': sum(1 for r in cl if r['status'] == 'SATISFIED'),
                 'checklist_partial': sum(1 for r in cl if r['status'] == 'PARTIAL'),
                 'checklist_gap': sum(1 for r in cl if r['status'] == 'GAP'),
                 'blank_pattern_columns_beyond_bonferroni': n_blank_flags,
                 'lookahead_phrase_hits': len(st.get('lookahead') or {}),
                 'sentinel_leakage_candidates': len(run.state['stage0']['s0'].get('sentinel_lift') or {}),
                 'adverse_impact_ratio': air}

    # bars (existing, cited; None = not applicable) --------------------------------------------
    import aegis_gates as ag
    floor = ag._AUC_FLOOR.get(run.tier)
    bars = [
        ('AUC at or above the tier floor', None if floor is None else rank['auc'] >= floor,
         'tier floor %s' % floor),
        ('Selection tolerance met (DeLong p >= 0.05, loss <= 5%)', bool(d['tolerance_met']),
         'pre-registered selection rule'),
        ('Per-grade backtest: every grade inside Wilson 95%', grade['grades_passed'] == grade['grades_total'],
         'Basel CRE36.122-123'),
        ('Hosmer-Lemeshow (10 groups) not rejected', None if acc['hl_p_g10'] is None
         else acc['hl_p_g10'] >= cfg['alpha'], 'alpha %.2f' % cfg['alpha']),
        ('Pool EPV at least 10', sufficiency['pool_epv'] >= EPV_RULE, 'Peduzzi 1996'),
        ('Riley minimum met on the candidate pool', sufficiency['pool_riley_met'], 'Riley et al. 2020'),
        ('No sparse grade (every grade n >= 30)', len(grade['sparse_grades']) == 0, 'backtest rule'),
        ('Four-fifths rule (fairness)', None if air is None else air >= FOUR_FIFTHS,
         'only where protected attributes exist'),
        ('No must-have checklist GAP', not any(r['status'] == 'GAP' and r.get('must_have') for r in cl),
         'AEGIS section 8'),
    ]
    bars = [{'bar': b, 'cleared': c, 'source': s} for b, c, s in bars]
    applicable = [b for b in bars if b['cleared'] is not None]
    return {'run': run.name, 'tier': run.tier, 'n': n, 'events': events, 'prevalence': round(events / n, 4),
            'ranking': rank, 'uncertainty': boot, 'accuracy': acc, 'calibration_step': xgb_step, 'grades': grade, 'sufficiency': sufficiency,
            'stability': stab, 'integrity': integrity, 'bars': bars,
            'bars_cleared': sum(1 for b in applicable if b['cleared']), 'bars_applicable': len(applicable),
            'note': 'Describes the model and its data together; not a ranking of methods. '
                    'Out-of-fold / held-out figures only; no cutoff-based metric (the cutoff is an institution input).'}


def markdown(sc):
    r, a, g, s, st, ig = (sc[k] for k in ('ranking', 'accuracy', 'grades', 'sufficiency', 'stability', 'integrity'))
    f = lambda x, d=4: 'n/a' if x is None else ('%.*f' % (d, x))
    L = ['# Model reliability scorecard - %s' % sc['run'], '',
         'N %s · events %s · prevalence %.2f%% · tier %s · **bars cleared: %d of %d applicable**'
         % (format(sc['n'], ','), format(sc['events'], ','), 100 * sc['prevalence'], sc['tier'],
            sc['bars_cleared'], sc['bars_applicable']), '', '_%s_' % sc['note'],
         '_Intervals marked 95%% CI: stratified percentile bootstrap, %d resamples, seed %d (a reporting convention; Gini and AUC use DeLong)._' % (sc['uncertainty']['n_boot'], sc['uncertainty']['seed']), '',
         '## 1. Ranking power (out-of-fold, selected model)', '',
         '| Metric | Value |', '|---|---|',
         '| Gini (95%% CI) | %s (%s to %s) |' % (f(r['gini']), f(r['gini_ci'][0]), f(r['gini_ci'][1])),
         '| AUC | %s |' % f(r['auc']), '| KS | %s |' % f(r['ks']),
         '| Partial AUC | %s |' % f(r['partial_auc'])]
    for q in CAPTURE_PERCENTILES:
        p = round(100 * q)
        ci = sc['uncertainty']['ci']['capture_top_%d' % p]
        L.append('| Events captured in riskiest %d%% (95%% CI; lift) | %.1f%% (%.1f%% to %.1f%%; %.1fx) |'
                 % (p, 100 * r['capture_top_%d' % p], 100 * ci[0], 100 * ci[1], r['lift_top_%d' % p]))
    U = sc['uncertainty']
    L += ['', '## 2. Probability accuracy (primary WOE-logistic model, out-of-fold)', '', '| Metric | Value |', '|---|---|',
          '| Brier skill (95%% CI) | %s (%s to %s) |' % (f(U['point']['brier_skill_oof']), f(U['ci']['brier_skill_oof'][0]), f(U['ci']['brier_skill_oof'][1])),
          '| ECE (95%% CI) | %s (%s to %s) |' % (f(U['point']['ece_oof']), f(U['ci']['ece_oof'][0]), f(U['ci']['ece_oof'][1])),
          '| Deployed-model ECE on held-out firms, before to after isotonic | %s to %s |' % (f(a['ece_heldout_raw']), f(a['ece_heldout_calibrated'])),
          '| Calibration slope (95%% CI) / intercept | %s (%s to %s) / %s |' % (f(a['calibration_slope_oof'], 3), f(U['ci']['calibration_slope_oof'][0], 3), f(U['ci']['calibration_slope_oof'][1], 3), f(a['calibration_intercept_oof'], 3)),
          '| Hosmer-Lemeshow p (10 groups / 5 groups) | %s / %s |' % (f(a['hl_p_g10']), f(a['hl_p_g5'])),
          '', '_Pipeline calibration step (%s): Brier baseline / raw / calibrated %s / %s / %s; ECE raw / calibrated %s / %s; calibrated AUC %s._' % (
              sc['calibration_step']['learner'], f(sc['calibration_step']['brier_baseline']), f(sc['calibration_step']['brier_raw']), f(sc['calibration_step']['brier_calibrated']),
              f(sc['calibration_step']['ece_raw']), f(sc['calibration_step']['ece_calibrated']), f(sc['calibration_step']['auc_calibrated'])),
          '', '## 3. Grade reliability (deployed-model backtest, held-out n = %d)' % g['n_heldout'], '',
          '| Metric | Value |', '|---|---|',
          '| Grades inside Wilson 95%% | %d of %d |' % (g['grades_passed'], g['grades_total']),
          '| Sparse grades (n < 30) | %s |' % (', '.join(g['sparse_grades']) or 'none'),
          '| Failing grades | %s |' % ('; '.join('%s (realised %.3f vs expected %.3f, %s)' % (x['grade'], x['realised'], x['expected'], x['direction']) for x in g['failing']) or 'none')]
    L += ['', '## 4. Sufficiency (governing basis: candidate pool)', '', '| Metric | Value |', '|---|---|',
          '| Events / rows | %s / %s |' % (format(s['events'], ','), format(s['n'], ',')),
          '| Pool EPV (P = %d) | %.1f |' % (s['pool_P'], s['pool_epv']),
          '| Riley margin on the pool (met) | %.2fx (%s) |' % (s['pool_riley_margin'], 'yes' if s['pool_riley_met'] else 'NO'),
          '| Selected model EPV / Riley margin (informational) | %s / %s |' % (f(s['selected_epv'], 1), f(s['selected_riley_margin'], 2)),
          '', '## 5. Stability and parsimony', '', '| Metric | Value |', '|---|---|',
          '| Players confirmed above the shadow bar | %d of %d |' % (st['players_confirmed'], st['players_real']),
          '| Weakest confirmed player (x the bar) / lowest confirmation frequency | %.2fx / %s |' % (st['weakest_confirmed_x_bar'], f(st['min_confirmation_frequency'])),
          '| Players selected (columns) | %d (%d) |' % (st['k_selected'], st['columns_selected']),
          '| Gini retained vs full model / DeLong p / relative loss | %.1f%% / %s / %.2f%% |' % (100 * st['gini_retained_vs_full'], f(st['delong_p_vs_full']), st['relative_gini_loss_pct']),
          '', '## 6. Integrity', '', '| Metric | Value |', '|---|---|',
          '| Governed (gates sealed) | %s |' % (', '.join(ig['gates_sealed']) if ig['governed'] else 'no - exploratory run, no gate signed'),
          '| GF verdict | %s |' % (ig['gf_verdict'] or 'not sealed'),
          '| Checklist: satisfied / partial / gap | %d / %d / %d |' % (ig['checklist_satisfied'], ig['checklist_partial'], ig['checklist_gap']),
          '| Columns whose blanks track the outcome (beyond Bonferroni) | %s |' % ig['blank_pattern_columns_beyond_bonferroni'],
          '| Look-ahead phrase hits in definitions / sentinel flags raised | %d / %d |' % (ig['lookahead_phrase_hits'], ig['sentinel_leakage_candidates']),
          '| Adverse-impact ratio | %s |' % f(ig['adverse_impact_ratio'], 2),
          '', '## Bars (existing, cited; n/a = not applicable)', '', '| Bar | Cleared | Source |', '|---|---|---|']
    for b in sc['bars']:
        L.append('| %s | %s | %s |' % (b['bar'], 'n/a' if b['cleared'] is None else ('yes' if b['cleared'] else '**NO**'), b['source']))
    return '\n'.join(L) + '\n'


def compare(a, b):
    """Side-by-side markdown. A 'lead' is awarded only when the two 95% intervals do not overlap;
    otherwise the row reads 'within CI'. Rows with no interval show the difference only
    ('no CI')."""
    def lead(va, vb, higher, ca, cb):
        if ca is not None and cb is not None:
            if not (ca[1] < cb[0] or cb[1] < ca[0]):
                return 'within CI'
            return a['run'] if (va > vb) == higher else b['run']
        return 'no CI'
    ua, ub = a['uncertainty'], b['uncertainty']
    rows = [
        ('Gini (DeLong CI)', a['ranking']['gini'], b['ranking']['gini'], True, a['ranking']['gini_ci'], b['ranking']['gini_ci']),
        ('Events captured, riskiest 5%', a['ranking']['capture_top_5'], b['ranking']['capture_top_5'], True, ua['ci']['capture_top_5'], ub['ci']['capture_top_5']),
        ('Events captured, riskiest 10%', a['ranking']['capture_top_10'], b['ranking']['capture_top_10'], True, ua['ci']['capture_top_10'], ub['ci']['capture_top_10']),
        ('Events captured, riskiest 20%', a['ranking']['capture_top_20'], b['ranking']['capture_top_20'], True, ua['ci']['capture_top_20'], ub['ci']['capture_top_20']),
        ('Brier skill (raw out-of-fold)', ua['point']['brier_skill_oof'], ub['point']['brier_skill_oof'], True, ua['ci']['brier_skill_oof'], ub['ci']['brier_skill_oof']),
        ('ECE (raw out-of-fold)', ua['point']['ece_oof'], ub['point']['ece_oof'], False, ua['ci']['ece_oof'], ub['ci']['ece_oof']),
        ('Calibration slope (1 is ideal)', ua['point']['calibration_slope_oof'], ub['point']['calibration_slope_oof'], True, ua['ci']['calibration_slope_oof'], ub['ci']['calibration_slope_oof']),
        ('Grades inside Wilson (fraction)', a['grades']['grades_passed'] / a['grades']['grades_total'],
         b['grades']['grades_passed'] / b['grades']['grades_total'], True, None, None),
        ('Pool EPV', a['sufficiency']['pool_epv'], b['sufficiency']['pool_epv'], True, None, None),
        ('Riley margin on the pool', a['sufficiency']['pool_riley_margin'], b['sufficiency']['pool_riley_margin'], True, None, None),
        ('Bars cleared (fraction)', a['bars_cleared'] / a['bars_applicable'], b['bars_cleared'] / b['bars_applicable'], True, None, None),
    ]
    L = ['# Scorecard comparison: %s vs %s' % (a['run'], b['run']), '',
         '| Metric | %s | %s | Lead |' % (a['run'], b['run']), '|---|---|---|---|']
    for name, va, vb, hi, ca, cb in rows:
        fa = '%.4f' % va + ('' if ca is None else ' (%.3f to %.3f)' % tuple(ca))
        fb = '%.4f' % vb + ('' if cb is None else ' (%.3f to %.3f)' % tuple(cb))
        L.append('| %s | %s | %s | %s |' % (name, fa, fb, lead(va, vb, hi, ca, cb)))
    L += ['', '| | %s | %s |' % (a['run'], b['run']), '|---|---|---|',
          '| Rows / events / prevalence | %s / %s / %.2f%% | %s / %s / %.2f%% |' % (
              format(a['n'], ','), format(a['events'], ','), 100 * a['prevalence'],
              format(b['n'], ','), format(b['events'], ','), 100 * b['prevalence']),
          '| Sparse grades (n < 30) | %s | %s |' % (', '.join(a['grades']['sparse_grades']) or 'none', ', '.join(b['grades']['sparse_grades']) or 'none'),
          '| Players confirmed | %d of %d | %d of %d |' % (a['stability']['players_confirmed'], a['stability']['players_real'], b['stability']['players_confirmed'], b['stability']['players_real']),
          '| Players selected (columns) | %d (%d) | %d (%d) |' % (a['stability']['k_selected'], a['stability']['columns_selected'], b['stability']['k_selected'], b['stability']['columns_selected']),
          '| Bars cleared | %d of %d | %d of %d |' % (a['bars_cleared'], a['bars_applicable'], b['bars_cleared'], b['bars_applicable']),
          '| Governed | %s | %s |' % ('yes' if a['integrity']['governed'] else 'exploratory', 'yes' if b['integrity']['governed'] else 'exploratory'),
          '', '_A lead is awarded only when the 95% intervals do not overlap. It is a difference between these two '
          'runs, not a verdict on either method: the datasets differ in firms, event rates and signal. '
          'Rows with no interval (grade count, EPV, Riley margin, bars) show the difference only._']
    return '\n'.join(L) + '\n'


def save(run, sc):
    with open(os.path.join(run.outdir, 'scorecard.json'), 'w', encoding='utf-8') as fh:
        json.dump(sc, fh, indent=1, default=str)
    with open(os.path.join(run.outdir, 'scorecard.md'), 'w', encoding='utf-8') as fh:
        fh.write(markdown(sc))
