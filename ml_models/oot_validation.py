"""oot_validation.py - out-of-time (train-past / test-future) validation.

WHY THIS EXISTS
---------------
Group-aware CV (panel_adapter / selection / shapley_utils) removes ENTITY
leakage: no loan's rows straddle train and test. It does NOT remove TIME
leakage. Covariates shared across entities within a calendar period (macro
series such as gdp / unemployment / house-price index) and regime shifts in the
base rate are visible to the model in every fold, so a grouped-CV score can be
optimistic about forward prediction. The realistic test is: fit on the past,
score the future.

This module reports that test next to the in-time number, so the gap is visible
rather than assumed away. It is DIAGNOSTIC: it decides nothing and gates
nothing (no pass/fail threshold is invented here). It is what the governance
layer reads to substantiate - or retire - a TIME-LEAKAGE condition (R7).

Fixed conventions (not tuned): chronological cut at the (1 - test_frac) quantile
of the time vector, test_frac = 0.3; the learner is the run's primary learner;
the isotonic calibrator is fit on the TRAIN period's own scores and assessed on
the future period, with the same cluster-robust per-grade backtest used in
Stage 4 when a `groups` key is supplied. Isotonic is fit on in-sample training
scores (not nested OOF): for the low-capacity WOE-logistic this bias is small,
but it is a stated approximation.

ASCII-only in emitted strings (Windows cp1252 console).
"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import selection as sel
import calibration_gof as cgof
from panel_adapter import temporal_split


def out_of_time_validation(X, y, columns, time_values, *, groups=None,
                           learner='woe_logistic', test_frac=0.3,
                           grade_fn=None, grade_order=None, in_time_gini=None,
                           random_state=42, n_boot=500, floor=0.0003, cap=0.999,
                           hp=None):
    """Fit on rows up to the time cut, score the later rows.

    X, y         : modelling frame and 0/1 outcome (row-aligned with time_values).
    columns      : the selected feature columns.
    time_values  : calendar time per row (any orderable numeric).
    groups       : optional entity key per row -> cluster-robust calibration CI.
    grade_fn     : pd -> grade label; with grade_order enables the calibrated
                   per-grade backtest + HL on the future period.
    in_time_gini : the grouped-CV Gini of the same model, for the comparison.

    Returns a dict (see keys below); `ok=False` with a `reason` if the split is
    degenerate (a period with a single outcome class).
    """
    X = pd.DataFrame(X).reset_index(drop=True)
    y = np.asarray(y).astype(int)
    t = np.asarray(time_values)
    tr, te, t_cut = temporal_split(pd.DataFrame({'t': t}), 't', test_frac)
    if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
        return {'ok': False, 'reason': 'train or test period has a single outcome class',
                't_cut': float(t_cut), 'test_frac': test_frac}

    Xs = X[list(columns)]
    kwargs = {'random_state': random_state}
    if learner == 'xgboost':
        kwargs['hp'] = hp
    fn = sel.LEARNERS[learner]
    p_te = np.clip(np.asarray(fn(Xs[tr], y[tr], Xs[te], **kwargs), dtype=float), floor, cap)
    p_tr = np.clip(np.asarray(fn(Xs[tr], y[tr], Xs[tr], **kwargs), dtype=float), floor, cap)

    auc = float(roc_auc_score(y[te], p_te))
    gini = 2 * auc - 1
    out = {'ok': True, 'learner': learner, 'test_frac': float(test_frac),
           't_cut': float(t_cut), 'n_train': int(tr.sum()), 'n_test': int(te.sum()),
           'train_event_rate': float(y[tr].mean()), 'test_event_rate': float(y[te].mean()),
           'auc': auc, 'gini': float(gini), 'in_time_gini': in_time_gini,
           'gini_drop_rel': (float((in_time_gini - gini) / in_time_gini)
                             if in_time_gini else None),
           'clustered': groups is not None}
    if groups is not None:
        g = np.asarray(groups)
        out['n_test_entities'] = int(len(np.unique(g[te])))
        out['n_test_new_entities'] = int(len(set(g[te]) - set(g[tr])))

    if grade_fn is not None and grade_order is not None:
        from sklearn.isotonic import IsotonicRegression
        iso = IsotonicRegression(out_of_bounds='clip').fit(p_tr, y[tr])
        cal = np.clip(iso.predict(p_te), floor, cap)
        grades = np.array([grade_fn(float(x)) for x in cal])
        g_te = np.asarray(groups)[te] if groups is not None else None
        table, summ = cgof.per_grade_backtest(y[te], cal, grades, grade_order,
                                              groups=g_te, n_boot=n_boot,
                                              random_state=random_state)
        gi = (np.unique(g_te, return_inverse=True)[1] if g_te is not None else None)
        hl = cgof.hosmer_lemeshow(y[te], cal, g=10, group_idx=gi,
                                  n_groups=(gi.max() + 1 if gi is not None else None))
        out.update({'grades_passed': summ['grades_passed'],
                    'grades_total': summ['grades_total'], 'backtest_method': summ['method'],
                    'table': table, 'hl': hl, 'ece_cal': cgof._ece(y[te], cal)})
    return out


def oot_markdown(res):
    """Compact markdown for the out-of-time result."""
    if not res:
        return ''
    if not res.get('ok'):
        return '## Out-of-time validation\n\nNot run: %s.\n' % res.get('reason', 'degenerate split')
    L = ['## Out-of-time validation (train past, test future; diagnostic)', '']
    L.append('Cut at time %.0f (test_frac %.2f): train n=%d (event rate %.4f) | test n=%d (event rate %.4f).'
             % (res['t_cut'], res['test_frac'], res['n_train'], res['train_event_rate'],
                res['n_test'], res['test_event_rate']))
    if res.get('clustered'):
        L.append('Test entities: %d (%d not seen in training).'
                 % (res['n_test_entities'], res['n_test_new_entities']))
    drop = res.get('gini_drop_rel')
    L.append('')
    L.append('| | In-time (grouped CV) | Out-of-time |')
    L.append('|---|--:|--:|')
    L.append('| Gini | %s | **%.4f** |'
             % (('%.4f' % res['in_time_gini']) if res.get('in_time_gini') is not None else 'n/a', res['gini']))
    L.append('| AUC | - | %.4f |' % res['auc'])
    if drop is not None:
        L.append('')
        L.append('Relative Gini change vs in-time: **%+.1f%%**.' % (-100 * drop))
    if 'grades_total' in res:
        hl = res['hl']
        hlp = hl.get('p_adj', hl.get('p_value'))
        L.append('')
        L.append('Calibrated on the past, assessed on the future: per-grade **%d/%d** (%s CI); HL g=10 p=%.4f%s; ECE %.4f.'
                 % (res['grades_passed'], res['grades_total'],
                    'cluster-bootstrap' if res['backtest_method'] == 'cluster' else 'Wilson',
                    hlp, ' (design-effect adj.)' if hl.get('clustered') else '', res['ece_cal']))
    L.append('')
    return '\n'.join(L)
