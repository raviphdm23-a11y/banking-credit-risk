"""
selection.py - Stage 3 of METHODOLOGY.md v3 (section 6): SELECTION.

This stage did not exist in v2. There, retention fell out of a significance
test on Shapley values, which conflated two different questions (review M1):
Shapley values are a fair-ATTRIBUTION solution concept, not a subset-selection
criterion. A redundant-but-informative feature still receives a positive share
(attribution says "keep") even when dropping it costs nothing; a feature whose
contribution concentrates in rare coalitions can average below a bar despite
being needed.

So selection is now explicit and separately justified:

  1. Eligible set  = players confirmed by the shadow-null in shapley_utils.
  2. Rank          = descending Shapley value.
  3. Parsimony curve: for k = 1..K, fit on the top-k players and record
     Gini / KS / AUC / partial AUC / Brier with confidence intervals. The FULL
     CURVE is a required output, not a diagnostic.
  4. Stopping rule (pre-declared): smallest k whose model is NOT statistically
     distinguishable from the full-candidate model by DeLong's test for
     correlated ROC curves (DeLong, DeLong & Clarke-Pearson, 1988) at alpha,
     AND whose relative Gini loss is within `max_relative_gini_loss`.
     If no k satisfies both, that is reported as a legitimate result - "no
     parsimonious subset meets the tolerance" - not silently replaced by the
     best available k.

Metrics are computed on OUT-OF-FOLD predictions, so every candidate k is
scored on exactly the same rows and DeLong's paired test is valid.

Gini is primary (review M10/m1): it is the credit-risk field's convention, and
small AUC gaps can be material in Gini terms - PAKDD's v2 result was a 15.5%
relative Gini reduction, which no portfolio owner accepts for parsimony alone.

ASCII-only in emitted strings (Windows cp1252 console).
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold

from shapley_utils import LEARNERS


# ===========================================================================
# DeLong's test for two correlated ROC curves
# ===========================================================================

def _midrank(x):
    """Mid-ranks with ties averaged (the T vector in DeLong's formulation)."""
    x = np.asarray(x, dtype=float)
    J = np.argsort(x)
    Z = x[J]
    N = len(x)
    T = np.zeros(N, dtype=float)
    i = 0
    while i < N:
        j = i
        while j < N and Z[j] == Z[i]:
            j += 1
        T[i:j] = 0.5 * (i + j - 1) + 1
        i = j
    out = np.empty(N, dtype=float)
    out[J] = T
    return out


def _fast_delong(preds_sorted, n_pos):
    """Fast DeLong covariance (Sun & Xu, 2014, implementing DeLong et al. 1988).

    preds_sorted: (k, n) array of k score vectors, columns ordered positives
    first then negatives.
    """
    m, n = n_pos, preds_sorted.shape[1] - n_pos
    pos = preds_sorted[:, :m]
    neg = preds_sorted[:, m:]
    k = preds_sorted.shape[0]
    tx = np.empty((k, m)); ty = np.empty((k, n)); tz = np.empty((k, m + n))
    for r in range(k):
        tx[r] = _midrank(pos[r])
        ty[r] = _midrank(neg[r])
        tz[r] = _midrank(preds_sorted[r])
    aucs = tz[:, :m].sum(axis=1) / m / n - float(m + 1.0) / 2.0 / n
    v01 = (tz[:, :m] - tx) / n
    v10 = 1.0 - (tz[:, m:] - ty) / m
    sx = np.cov(v01)
    sy = np.cov(v10)
    cov = sx / m + sy / n
    return aucs, np.atleast_2d(cov)


def delong_test(y_true, proba_a, proba_b):
    """Two-sided DeLong test comparing two correlated AUCs on the same samples.

    Returns {'auc_a','auc_b','diff','z','p_value'}. A LARGE p-value means the
    two models are not statistically distinguishable - which in this module is
    the condition for accepting a smaller feature set.
    """
    y = np.asarray(y_true).astype(int)
    order = np.argsort(-y, kind='mergesort')  # positives first, stable
    y_s = y[order]
    n_pos = int(y_s.sum())
    if n_pos == 0 or n_pos == len(y_s):
        return {'auc_a': np.nan, 'auc_b': np.nan, 'diff': np.nan,
                'z': np.nan, 'p_value': np.nan}
    preds = np.vstack([np.asarray(proba_a, dtype=float)[order],
                       np.asarray(proba_b, dtype=float)[order]])
    aucs, cov = _fast_delong(preds, n_pos)
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    diff = float(aucs[0] - aucs[1])
    if var <= 0:
        return {'auc_a': float(aucs[0]), 'auc_b': float(aucs[1]), 'diff': diff,
                'z': 0.0, 'p_value': 1.0}
    z = diff / np.sqrt(var)
    p = float(2 * (1 - stats.norm.cdf(abs(z))))
    return {'auc_a': float(aucs[0]), 'auc_b': float(aucs[1]), 'diff': diff,
            'z': float(z), 'p_value': p}


# ===========================================================================
# Metrics (Gini primary)
# ===========================================================================

def ks_statistic(y_true, proba):
    fpr, tpr, _ = roc_curve(y_true, proba)
    return float(np.max(np.abs(tpr - fpr)))


def expected_calibration_error(y_true, proba, n_bins=10):
    y_true = np.asarray(y_true, dtype=float)
    proba = np.asarray(proba, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(proba, edges[1:-1], right=True), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.sum() == 0:
            continue
        ece += (m.sum() / len(proba)) * abs(proba[m].mean() - y_true[m].mean())
    return float(ece)


def score_report(y_true, proba, base_rate=None, n_boot=500, random_state=42,
                 partial_auc_max_fpr=0.5):
    """Gini (primary), KS, AUC, partial AUC, Brier, ECE - with a Gini CI."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)
    auc = float(roc_auc_score(y_true, proba))
    base = float(np.mean(y_true)) if base_rate is None else float(base_rate)
    # Brier and ECE need probabilities; AUC/KS/pAUC are rank-based and do not.
    # Clip rather than raise, so passing raw scores degrades the calibration
    # metrics instead of killing a long parsimony run.
    proba_p = np.clip(proba, 0.0, 1.0)
    rng = np.random.RandomState(random_state)
    boots = []
    n = len(y_true)
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        boots.append(2 * roc_auc_score(y_true[idx], proba[idx]) - 1)
    lo, hi = (np.nanpercentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan))
    return {
        'gini': 2 * auc - 1,
        'gini_ci_low': float(lo),
        'gini_ci_high': float(hi),
        'auc': auc,
        'ks': ks_statistic(y_true, proba),
        'partial_auc': float(roc_auc_score(y_true, proba, max_fpr=partial_auc_max_fpr)),
        'brier': float(brier_score_loss(y_true, proba_p)),
        'brier_baseline': float(brier_score_loss(y_true, np.full(n, base))),
        'ece': expected_calibration_error(y_true, proba_p),
    }


# ===========================================================================
# Out-of-fold predictions and the parsimony curve
# ===========================================================================

def oof_predictions(X, y, columns, learner='woe_logistic', cv_folds=5,
                    random_state=42, hp=None):
    """One honest out-of-fold prediction per row, for the given column subset.

    Using OOF predictions means every candidate subset is scored on exactly the
    same rows, which is what makes DeLong's paired test applicable across the
    parsimony curve.
    """
    X = pd.DataFrame(X).reset_index(drop=True)
    y = pd.Series(np.asarray(y)).reset_index(drop=True)
    oof = np.full(len(y), np.nan)
    if not columns:
        return np.full(len(y), float(y.mean()))
    Xs = X[list(columns)]
    skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    fn = LEARNERS[learner]
    for tr, te in skf.split(Xs, y):
        kwargs = {'random_state': random_state}
        if learner == 'xgboost':
            kwargs['hp'] = hp
        oof[te] = fn(Xs.iloc[tr], y.iloc[tr], Xs.iloc[te], **kwargs)
    return oof


def parsimony_curve(X, y, ranked_players, player_columns, learner='woe_logistic',
                    cv_folds=5, random_state=42, hp=None, n_boot=500,
                    progress=True):
    """Metrics for the top-k players, k = 1..K, plus the full-candidate model.

    ranked_players: player names in descending importance order.
    player_columns: {player_name: [columns]}.

    Returns (curve_df, extras) where extras carries the OOF predictions so the
    caller can run further paired tests without refitting.
    """
    X = pd.DataFrame(X).reset_index(drop=True)
    y = pd.Series(np.asarray(y)).reset_index(drop=True)
    all_cols = [c for p in ranked_players for c in player_columns[p]]

    oof_full = oof_predictions(X, y, all_cols, learner=learner, cv_folds=cv_folds,
                               random_state=random_state, hp=hp)
    full = score_report(y, oof_full, n_boot=n_boot, random_state=random_state)

    rows, oofs = [], {}
    cols_so_far = []
    for k, p in enumerate(ranked_players, start=1):
        cols_so_far = cols_so_far + list(player_columns[p])
        oof_k = oof_predictions(X, y, cols_so_far, learner=learner, cv_folds=cv_folds,
                                random_state=random_state, hp=hp)
        oofs[k] = oof_k
        rep = score_report(y, oof_k, n_boot=n_boot, random_state=random_state)
        dl = delong_test(y, oof_k, oof_full)
        rel_loss = ((full['gini'] - rep['gini']) / full['gini']) if full['gini'] > 0 else np.nan
        rows.append({
            'k': k, 'player_added': p, 'n_columns': len(cols_so_far),
            'gini': rep['gini'], 'gini_ci_low': rep['gini_ci_low'],
            'gini_ci_high': rep['gini_ci_high'], 'auc': rep['auc'], 'ks': rep['ks'],
            'partial_auc': rep['partial_auc'], 'brier': rep['brier'], 'ece': rep['ece'],
            'relative_gini_loss_vs_full': float(rel_loss),
            'delong_p_vs_full': dl['p_value'],
            'distinguishable_from_full': bool(dl['p_value'] < 0.05)
                if not np.isnan(dl['p_value']) else None,
        })
        if progress:
            print('[parsimony] k=%d (%s): gini=%.4f rel_loss=%.2f%% delong_p=%.4f'
                  % (k, p, rep['gini'], 100 * rel_loss, dl['p_value']), flush=True)
    curve = pd.DataFrame(rows)
    extras = {'full_model': full, 'oof_full': oof_full, 'oof_by_k': oofs,
              'all_columns': all_cols}
    return curve, extras


def select_parsimonious(curve, max_relative_gini_loss=0.05, alpha=0.05):
    """Apply the pre-declared stopping rule (METHODOLOGY v3 s6 step 4).

    Returns a dict with the chosen k (or None), the rationale, and the flag
    `tolerance_met` - which is False when NO subset satisfies both conditions.
    That outcome is reported, not papered over.
    """
    ok = curve[(curve['delong_p_vs_full'] >= alpha) &
               (curve['relative_gini_loss_vs_full'] <= max_relative_gini_loss)]
    if len(ok):
        row = ok.iloc[0]
        return {
            'tolerance_met': True,
            'selected_k': int(row['k']),
            'selected_players': list(curve.loc[:row.name, 'player_added']),
            'n_columns': int(row['n_columns']),
            'gini': float(row['gini']),
            'relative_gini_loss': float(row['relative_gini_loss_vs_full']),
            'delong_p': float(row['delong_p_vs_full']),
            'rule': ('smallest k with DeLong p >= %.2f (not distinguishable from the '
                     'full-candidate model) and relative Gini loss <= %.1f%%'
                     % (alpha, 100 * max_relative_gini_loss)),
        }
    best = curve.iloc[curve['relative_gini_loss_vs_full'].idxmin()]
    return {
        'tolerance_met': False,
        'selected_k': None,
        'selected_players': None,
        'rule': ('smallest k with DeLong p >= %.2f and relative Gini loss <= %.1f%%'
                 % (alpha, 100 * max_relative_gini_loss)),
        'note': ('No subset of the ranked players meets the pre-declared tolerance. '
                 'This is a legitimate result and must be reported as such: the '
                 'honest statement is that no parsimonious subset is acceptable at '
                 'this tolerance, not that the best available k is the answer.'),
        'closest_k': int(best['k']),
        'closest_relative_gini_loss': float(best['relative_gini_loss_vs_full']),
        'closest_delong_p': float(best['delong_p_vs_full']),
    }


def curve_markdown(curve, decision=None):
    """The parsimony curve as a markdown table for a findings log."""
    lines = ['| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | '
             'rel. Gini loss | DeLong p vs full |',
             '|---:|---|---:|---:|---|---:|---:|---:|---:|---:|']
    for _, r in curve.iterrows():
        lines.append('| %d | %s | %d | %.4f | [%.4f, %.4f] | %.4f | %.4f | %.4f | %.2f%% | %.4f |'
                     % (r['k'], r['player_added'], r['n_columns'], r['gini'],
                        r['gini_ci_low'], r['gini_ci_high'], r['ks'], r['partial_auc'],
                        r['brier'], 100 * r['relative_gini_loss_vs_full'],
                        r['delong_p_vs_full']))
    if decision is not None:
        lines.append('')
        if decision['tolerance_met']:
            lines.append('**Selected k = %d** (%d columns, Gini %.4f, relative loss %.2f%%, '
                         'DeLong p = %.4f). Rule: %s.'
                         % (decision['selected_k'], decision['n_columns'], decision['gini'],
                            100 * decision['relative_gini_loss'], decision['delong_p'],
                            decision['rule']))
        else:
            lines.append('**No subset met the pre-declared tolerance.** %s Closest: k = %d '
                         '(relative Gini loss %.2f%%, DeLong p = %.4f).'
                         % (decision['note'], decision['closest_k'],
                            100 * decision['closest_relative_gini_loss'],
                            decision['closest_delong_p']))
    return '\n'.join(lines)
