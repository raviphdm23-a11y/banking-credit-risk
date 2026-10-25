"""
shapley_utils.py - Stage 2 of METHODOLOGY.md v3 (section 5):
order-invariant importance estimation.

WHAT THIS IS (and is not). For a set of players P and subset S of P, v(S) is
the repeated cross-validated predictiveness of a model trained on exactly the
columns in S. Shapley values over that value function are the Shapley
Population Variable Importance Measure of **Williamson & Feng (2020, ICML)**
- NOT SAGE. SAGE (Covert, Lundberg & Lee, 2020) marginalises absent features
out of a single fitted model; this refits per subset, which is a different
estimand. v2 of this module claimed SAGE equivalence; that claim is withdrawn.

Shapley values answer ATTRIBUTION, not SELECTION (Kumar et al., 2020, ICML).
This module therefore produces an order-invariant importance ranking plus an
`importance_confirmed` flag; choosing a subset from that ranking is a separate,
separately-justified step and lives in `selection.py`.

CHANGES FROM v2, each tracing to a review finding:
- M2  Positioned as SPVIM, not SAGE.
- M3  The significance layer is replaced. v2 ran a one-sample t-test on 5 CV
      fold values, which is invalid (folds share ~75% of training data, so the
      variance estimate is biased down - Bengio & Grandvalet 2004; Dietterich
      1998), against an uncharacterised null, and then patched the result with
      a Cohen's d >= 0.8 rule borrowed from behavioural science and tuned on one
      dataset's known answer. All of that is gone. Retention is now decided by
      an empirical null built from SHADOW (permuted) players - Boruta's device
      (Kursa & Rudnicki, 2010) - which needs no distributional assumption and
      no multiple-testing correction, because the bar is a quantile of a null
      distribution rather than a family of p-values.
      BH p-values and Cohen's d are still computed and reported as diagnostics.
      They no longer decide anything.
- M7  Correlation pruning is replaced by GROUPED (coalitional) players:
      correlated clusters become a single Shapley player, which cuts the
      combinatorial cost exactly as pruning did while keeping the efficiency
      property over the full candidate set and handling redundancy the way
      Shapley is designed to. Pruning also reintroduced a univariate criterion
      ("keep the highest-IV member") into the multivariate stage, which is the
      artefact the methodology exists to avoid.
- M9  The value function and learner are both pluggable. Primary learner is a
      penalised logistic regression on monotonic-WOE-transformed inputs
      (deterministic, hyperparameter-insensitive, the credit-scoring standard
      form); XGBoost with fixed hyperparameters is the secondary/robustness
      learner. Value function can be AUC, partial AUC over an operating band,
      or Brier skill (loss-based, with a well-defined empty-model baseline).
- m7  The efficiency property is reported as `implementation_audit`, because it
      validates arithmetic, not statistical accuracy: it passes to machine
      precision even if every v(S) is badly estimated.
- m8  scale_pos_weight is off for the value-function learner.

ASCII-only in emitted strings (Windows cp1252 console).
"""
import itertools
import json
import math
import os
import random
import time

import numpy as np
import pandas as pd
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform
from scipy.stats import ttest_1samp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from binning import WOEEncoder

SHADOW_PREFIX = '__shadow__'


# ===========================================================================
# Value functions
# ===========================================================================

def _auc(y_true, proba, base_rate):
    return float(roc_auc_score(y_true, proba))


def _partial_auc(y_true, proba, base_rate, max_fpr=0.5):
    """McClish-corrected partial AUC over the low-FPR region.

    Rationale (review M9a): lenders operate at a cutoff, so the region of the
    ROC curve that matters is narrow; full AUC integrates over operating points
    that will never be used, letting a feature earn credit for discrimination
    in a commercially irrelevant score region.
    """
    return float(roc_auc_score(y_true, proba, max_fpr=max_fpr))


def _brier_skill(y_true, proba, base_rate):
    """1 - Brier/Brier_baseline, baseline = constant training base rate.

    Loss-based, so the empty model has a well-defined value (0) rather than a
    stipulated 0.5, and calibration quality enters selection directly instead
    of being repaired afterwards (review M9b).
    """
    ref = np.full(len(y_true), base_rate, dtype=float)
    denom = brier_score_loss(y_true, ref)
    if denom <= 0:
        return 0.0
    return float(1.0 - brier_score_loss(y_true, proba) / denom)


VALUE_FNS = {
    'auc': (_auc, 0.5),
    'partial_auc': (_partial_auc, 0.5),
    'brier_skill': (_brier_skill, 0.0),
}


# ===========================================================================
# Learners
# ===========================================================================

def _fit_predict_woe_logistic(X_tr, y_tr, X_te, C=1.0, random_state=42):
    enc = WOEEncoder().fit(X_tr, y_tr)
    W_tr, W_te = enc.transform(X_tr), enc.transform(X_te)
    clf = LogisticRegression(penalty='l2', C=C, solver='lbfgs', max_iter=1000,
                             class_weight=None, random_state=random_state)
    clf.fit(W_tr.values, y_tr)
    return clf.predict_proba(W_te.values)[:, 1]


def _fit_predict_xgboost(X_tr, y_tr, X_te, hp=None, random_state=42):
    from trainer import train_model, _load_hyperparameters
    hp = dict(hp or _load_hyperparameters())
    # m8: no class-prior reweighting for the value-function learner.
    models = dict(hp.get('models', {}))
    xgb_hp = dict(models.get('xgboost', {}))
    xgb_hp['scale_pos_weight'] = 1.0
    models['xgboost'] = xgb_hp
    hp['models'] = models
    model = train_model(X_tr, y_tr, hp, model_type='xgboost')
    return model.predict_proba(X_te)[:, 1]


LEARNERS = {
    'woe_logistic': _fit_predict_woe_logistic,
    'xgboost': _fit_predict_xgboost,
}


# ===========================================================================
# Players: clustering and shadows
# ===========================================================================

def vif_report(X, columns=None):
    """Variance inflation factor per column (review M7 item 3).

    Pairwise correlation misses multi-way collinearity: three variables each
    pairwise at rho ~ 0.5 can be nearly perfectly collinear jointly. VIF > 10
    is the conventional flag.
    """
    cols = list(columns or X.columns)
    num = X[cols].apply(pd.to_numeric, errors='coerce')
    num = num.fillna(num.median(numeric_only=True)).dropna(axis=1, how='all')
    out = []
    for c in num.columns:
        others = [o for o in num.columns if o != c]
        if not others:
            out.append({'column': c, 'vif': 1.0})
            continue
        try:
            from sklearn.linear_model import LinearRegression
            r2 = LinearRegression().fit(num[others].values, num[c].values).score(
                num[others].values, num[c].values)
            vif = float('inf') if r2 >= 1 - 1e-12 else 1.0 / (1.0 - r2)
        except Exception:
            vif = float('nan')
        out.append({'column': c, 'vif': float(vif)})
    df = pd.DataFrame(out).set_index('column')
    df['flag_vif_gt_10'] = df['vif'] > 10
    return df.sort_values('vif', ascending=False)


def cluster_players(X, columns=None, threshold=0.7, linkage_method='average'):
    """Group columns into Shapley players by correlation (METHODOLOGY v3 s5.3).

    Hierarchical clustering on distance 1 - |Spearman rho|, cut at
    1 - threshold. Replaces v2's greedy pairwise pruning, which was itself
    path-dependent and dropped columns using a univariate (IV) tie-break.

    Returns (players, info) where players is a list of column lists and info
    carries the names and the correlation matrix used.
    """
    cols = list(columns or X.columns)
    if len(cols) <= 1:
        return [[c] for c in cols], {'n_players': len(cols), 'threshold': threshold,
                                     'names': {c: c for c in cols}}
    rho = X[cols].apply(pd.to_numeric, errors='coerce').corr(method='spearman').abs()
    rho = rho.fillna(0.0)
    np.fill_diagonal(rho.values, 1.0)
    dist = 1.0 - rho.values
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2.0
    Z = hierarchy.linkage(squareform(dist, checks=False), method=linkage_method)
    labels = hierarchy.fcluster(Z, t=1.0 - threshold, criterion='distance')
    groups = {}
    for c, lab in zip(cols, labels):
        groups.setdefault(int(lab), []).append(c)
    players = [sorted(v) for _, v in sorted(groups.items())]
    names = {}
    for grp in players:
        names[_player_name(grp)] = grp
    return players, {'n_players': len(players), 'n_columns': len(cols),
                     'threshold': threshold, 'linkage': linkage_method,
                     'names': names,
                     'correlation': rho}


def _player_name(group):
    """Readable name for a group player, e.g. 'grp[A+B+C]' or just 'A'."""
    if len(group) == 1:
        return group[0]
    return 'grp[' + '+'.join(group) + ']'


def make_shadows(X, players, n_shadows=10, random_state=42):
    """Append permuted-copy shadow players to build the empirical null.

    A shadow is a column whose values are randomly permuted across rows: the
    marginal distribution is preserved exactly, the relationship with the
    target is destroyed. The Shapley values the shadows receive are therefore a
    direct, assumption-free answer to "what does a player of this kind score
    in this dataset, under this learner and value function, when it carries no
    signal?" (Boruta's device - Kursa & Rudnicki, 2010.)

    Source columns are sampled from the real players so shadow marginals
    resemble real ones. Returns (X_augmented, shadow_players).
    """
    rng = np.random.RandomState(random_state)
    flat = [c for grp in players for c in grp]
    X_aug = X.copy()
    shadow_players = []
    for i in range(n_shadows):
        src = flat[i % len(flat)]
        name = SHADOW_PREFIX + str(i) + '_' + str(src)
        X_aug[name] = X[src].to_numpy()[rng.permutation(len(X))]
        shadow_players.append([name])
    return X_aug, shadow_players


def is_shadow(player_name):
    return str(player_name).startswith(SHADOW_PREFIX) or str(player_name).startswith(
        'grp[' + SHADOW_PREFIX)


# ===========================================================================
# Core: v(S) with repeated CV, cached
# ===========================================================================

class _ValueFunction:
    """v(S) -> vector of per-fold values (one entry per fold per repeat).

    Keeping the per-fold vector (rather than only its mean) is what lets the
    bootstrap in `shapley_importance` express uncertainty in the estimate.

    PERFORMANCE NOTE (the thing that makes this tractable at all). A column's
    WOE binning and WOE values depend only on (that column, that training
    fold) - NOT on which other columns happen to be in the subset. So for the
    woe_logistic learner every (fold, column) WOE vector is computed ONCE and
    reused across all 2^n subsets, leaving only a cheap logistic fit per
    subset. Without this the same binning work is repeated thousands of times
    and a realistic pool is unaffordable. The caching changes nothing
    statistically: bins are still fitted on the training fold only, so no
    held-out row informs them.
    """

    def __init__(self, X, y, learner='woe_logistic', value_fn='auc', cv_folds=5,
                 cv_repeats=2, random_state=42, hp=None, value_fn_kwargs=None,
                 logistic_C=1.0, cv_groups=None):
        if learner not in LEARNERS:
            raise ValueError('learner must be one of ' + str(sorted(LEARNERS)))
        if value_fn not in VALUE_FNS:
            raise ValueError('value_fn must be one of ' + str(sorted(VALUE_FNS)))
        self.X = pd.DataFrame(X).reset_index(drop=True)
        self.y = pd.Series(np.asarray(y)).reset_index(drop=True)
        self.learner = learner
        self.value_fn_name = value_fn
        self.fn, self.empty_value = VALUE_FNS[value_fn]
        self.value_fn_kwargs = value_fn_kwargs or {}
        self.hp = hp
        self.random_state = random_state
        self.logistic_C = logistic_C
        # cv_groups is the panel/entity key (panel_adapter, hazard framing). When
        # given, folds are cut with StratifiedGroupKFold so every row of an entity
        # stays in one fold - the leakage guard for repeated-measures data. Repeats
        # re-seed the splitter so the bootstrap still sees fold-to-fold variation.
        # When None (every cross-sectional / snapshot run) the folds are the
        # unchanged RepeatedStratifiedKFold - byte-for-byte as before.
        if cv_groups is None:
            rskf = RepeatedStratifiedKFold(n_splits=cv_folds, n_repeats=cv_repeats,
                                           random_state=random_state)
            self.folds = list(rskf.split(self.X, self.y))
        else:
            from sklearn.model_selection import StratifiedGroupKFold
            g = np.asarray(cv_groups)
            self.folds = []
            for r in range(cv_repeats):
                sgkf = StratifiedGroupKFold(n_splits=cv_folds, shuffle=True,
                                            random_state=random_state + r)
                self.folds.extend(sgkf.split(self.X, self.y, groups=g))
        self.n_evals = len(self.folds)
        self.cache = {}
        self.n_fits = 0
        self._woe = None
        if self.learner == 'woe_logistic':
            self._precompute_woe()

    def _precompute_woe(self):
        """WOE-transform every column once per fold (see class docstring)."""
        self._woe = []
        for tr, te in self.folds:
            y_tr = self.y.iloc[tr]
            per_col = {}
            for c in self.X.columns:
                enc = WOEEncoder().fit(self.X[[c]].iloc[tr], y_tr)
                per_col[c] = (enc.transform(self.X[[c]].iloc[tr])[c].to_numpy(dtype=float),
                              enc.transform(self.X[[c]].iloc[te])[c].to_numpy(dtype=float))
            self._woe.append(per_col)

    def _woe_fit_predict(self, cols, fold_i, tr, te):
        per_col = self._woe[fold_i]
        W_tr = np.column_stack([per_col[c][0] for c in cols])
        W_te = np.column_stack([per_col[c][1] for c in cols])
        clf = LogisticRegression(penalty='l2', C=self.logistic_C, solver='lbfgs',
                                 max_iter=1000, class_weight=None,
                                 random_state=self.random_state)
        clf.fit(W_tr, self.y.iloc[tr])
        return clf.predict_proba(W_te)[:, 1]

    def __call__(self, cols):
        key = frozenset(cols)
        if key in self.cache:
            return self.cache[key]
        if not key:
            val = np.full(self.n_evals, float(self.empty_value))
            self.cache[key] = val
            return val
        cols = sorted(key)
        Xs = self.X[cols]
        vals = []
        for fold_i, (tr, te) in enumerate(self.folds):
            y_tr, y_te = self.y.iloc[tr], self.y.iloc[te]
            if y_te.nunique() < 2 or y_tr.nunique() < 2:
                continue
            if self.learner == 'woe_logistic':
                proba = self._woe_fit_predict(cols, fold_i, tr, te)
            else:
                kwargs = {'random_state': self.random_state, 'hp': self.hp}
                proba = LEARNERS[self.learner](Xs.iloc[tr], y_tr, Xs.iloc[te], **kwargs)
            self.n_fits += 1
            vals.append(self.fn(y_te, proba, float(y_tr.mean()), **self.value_fn_kwargs))
        out = np.asarray(vals, dtype=float) if vals else np.full(self.n_evals, np.nan)
        self.cache[key] = out
        return out


# ===========================================================================
# Shapley computation
# ===========================================================================

def _exact_shapley(vf, players, progress_every=0):
    """Exact Shapley per player, as a vector over CV evaluations."""
    n = len(players)
    fact = math.factorial
    n_evals = len(vf(frozenset()))
    shap = np.zeros((n, n_evals))
    for i in range(n):
        others = [j for j in range(n) if j != i]
        total = np.zeros(n_evals)
        for r in range(n):
            w = fact(r) * fact(n - r - 1) / fact(n)
            for combo in itertools.combinations(others, r):
                s_cols = [c for j in combo for c in players[j]]
                total += w * (vf(s_cols + list(players[i])) - vf(s_cols))
        shap[i] = total
        if progress_every:
            print('[shapley exact] player %d/%d done, %d fits so far'
                  % (i + 1, n, vf.n_fits), flush=True)
    return shap, {'mode': 'exact', 'n_subsets_evaluated': len(vf.cache)}


def _sampled_shapley(vf, players, n_samples, random_state=42, progress_every=25,
                     target_mc_se=None, max_samples=5000, checkpoint_path=None):
    """Permutation-sampling Shapley. Returns (per-player sample matrix, info).

    Each row of the returned matrix is one player; each column is one sampled
    permutation's marginal contribution (averaged over CV evaluations).

    target_mc_se: keep drawing permutations until every player's Monte Carlo
    standard error is below this, instead of stopping at a fixed count
    (METHODOLOGY v3 s5.5 - T is set by the precision the decision needs).
    """
    rng = random.Random(random_state)
    n = len(players)
    samples = [[] for _ in range(n)]
    t0 = time.time()
    s = 0
    while True:
        order = list(range(n))
        rng.shuffle(order)
        current = []
        v_cur = float(np.nanmean(vf(current)))
        for j in order:
            nxt = current + list(players[j])
            v_nxt = float(np.nanmean(vf(nxt)))
            samples[j].append(v_nxt - v_cur)
            current, v_cur = nxt, v_nxt
        s += 1
        if progress_every and s % progress_every == 0:
            ses = [np.std(v, ddof=1) / math.sqrt(len(v)) if len(v) > 1 else np.inf
                   for v in samples]
            print('[shapley sampled] %d permutations, %d unique subsets, %d fits, '
                  'max MC SE %.5f, %.0fs'
                  % (s, len(vf.cache), vf.n_fits, max(ses), time.time() - t0), flush=True)
            if checkpoint_path:
                _save_checkpoint(checkpoint_path, players, samples, s)
        if target_mc_se is not None and s >= 50:
            ses = [np.std(v, ddof=1) / math.sqrt(len(v)) for v in samples]
            if max(ses) <= target_mc_se or s >= max_samples:
                break
        elif s >= n_samples:
            break
    return np.asarray([np.asarray(v, dtype=float) for v in samples]), {
        'mode': 'sampled', 'n_permutations': s, 'n_subsets_evaluated': len(vf.cache)}


def _save_checkpoint(path, players, samples, n_done):
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f:
            json.dump({'players': [list(p) for p in players],
                       'samples': [list(map(float, v)) for v in samples],
                       'n_permutations': n_done}, f)
    except Exception as exc:  # checkpointing must never kill a long run
        print('[shapley] checkpoint write failed: ' + str(exc), flush=True)


def _bh_adjust(pvals):
    p = np.asarray(pvals, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj_sorted = p[order] * m / np.arange(1, m + 1)
    for k in range(m - 2, -1, -1):
        adj_sorted[k] = min(adj_sorted[k], adj_sorted[k + 1])
    out = np.empty(m)
    out[order] = np.minimum(adj_sorted, 1.0)
    return out


def shapley_importance(X, y, players=None, *, learner='woe_logistic', value_fn='auc',
                       value_fn_kwargs=None, cv_folds=5, cv_repeats=2,
                       cluster_threshold=0.7, auto_cluster=True,
                       n_shadows=10, shadow_quantile=0.95,
                       n_bootstrap=2000, confirm_frequency_min=0.80,
                       mode='auto', exact_max_players=15, n_samples=300,
                       target_mc_se=None, random_state=42, hp=None,
                       row_subsample=None, progress_every=25, checkpoint_path=None,
                       cv_groups=None):
    """Order-invariant importance for column selection (METHODOLOGY v3 s5).

    players: list of column groups. If None and auto_cluster, groups are derived
        by correlation clustering (s5.3). Pass explicit groups to override.
    learner: 'woe_logistic' (primary) or 'xgboost' (secondary/robustness).
    value_fn: 'auc' | 'partial_auc' | 'brier_skill'.
    mode: 'auto' (exact when player count incl. shadows <= exact_max_players,
        else sampled), or force 'exact'/'sampled'.

    Retention: a player is `importance_confirmed` when its Shapley value
    exceeds the `shadow_quantile` of the shadow players' Shapley values, and
    its bootstrap `confirmation_frequency` is at least confirm_frequency_min.
    No p-value and no Cohen's d enters this decision (see module docstring).

    Returns {'players': DataFrame, 'shadow_bar': float, 'info': {...}}.
    """
    X = pd.DataFrame(X).reset_index(drop=True)
    y = pd.Series(np.asarray(y)).reset_index(drop=True)

    if row_subsample is not None and row_subsample < len(X):
        if cv_groups is not None:
            # group-aware subsample: keep WHOLE entities until ~row_subsample rows,
            # so no entity is split across the in/out of the subsample.
            g = np.asarray(cv_groups)
            rng = np.random.RandomState(random_state)
            uniq = rng.permutation(np.unique(g))
            keep, n = [], 0
            for gid in uniq:
                keep.append(gid); n += int((g == gid).sum())
                if n >= row_subsample:
                    break
            mask = np.isin(g, keep)
            X, y, cv_groups = X[mask].reset_index(drop=True), y[mask].reset_index(drop=True), g[mask]
        else:
            from sklearn.model_selection import train_test_split
            X, _, y, _ = train_test_split(X, y, train_size=row_subsample, stratify=y,
                                          random_state=random_state)
            X, y = X.reset_index(drop=True), y.reset_index(drop=True)

    cluster_info = None
    if players is None:
        if auto_cluster:
            players, cluster_info = cluster_players(X, threshold=cluster_threshold)
        else:
            players = [[c] for c in X.columns]
    players = [list(p) for p in players]

    X_aug, shadow_players = make_shadows(X, players, n_shadows=n_shadows,
                                         random_state=random_state)
    all_players = players + shadow_players
    names = [_player_name(p) for p in all_players]

    use_exact = (mode == 'exact') or (mode == 'auto' and len(all_players) <= exact_max_players)
    if mode == 'sampled':
        use_exact = False

    vf = _ValueFunction(X_aug, y, learner=learner, value_fn=value_fn, cv_folds=cv_folds,
                        cv_repeats=cv_repeats, random_state=random_state, hp=hp,
                        value_fn_kwargs=value_fn_kwargs, cv_groups=cv_groups)

    print('[shapley] %d real players + %d shadows = %d; mode=%s; learner=%s; value_fn=%s'
          % (len(players), len(shadow_players), len(all_players),
             'exact' if use_exact else 'sampled', learner, value_fn), flush=True)

    if use_exact:
        mat, run_info = _exact_shapley(vf, all_players, progress_every=progress_every)
    else:
        mat, run_info = _sampled_shapley(vf, all_players, n_samples=n_samples,
                                         random_state=random_state,
                                         progress_every=progress_every,
                                         target_mc_se=target_mc_se,
                                         checkpoint_path=checkpoint_path)

    means = np.nanmean(mat, axis=1)
    shadow_idx = [i for i, p in enumerate(all_players) if is_shadow(_player_name(p))]
    real_idx = [i for i in range(len(all_players)) if i not in shadow_idx]
    shadow_vals = means[shadow_idx]
    shadow_bar = float(np.nanquantile(shadow_vals, shadow_quantile)) if len(shadow_vals) else 0.0

    # Bootstrap over the per-player estimate distribution (permutation samples in
    # sampled mode, CV evaluations in exact mode) to get a confirmation
    # frequency. METHODOLOGY v3 s5.4 specified R full re-runs with fresh
    # shadow seeds; bootstrapping the existing estimates is the same question
    # ("would this player still clear the bar under resampling?") at a tiny
    # fraction of the compute, which is what makes it usable on real pools.
    rng = np.random.RandomState(random_state)
    n_cols_mat = mat.shape[1]
    boot_means = np.empty((len(all_players), n_bootstrap))
    for b in range(n_bootstrap):
        idx = rng.randint(0, n_cols_mat, n_cols_mat)
        boot_means[:, b] = np.nanmean(mat[:, idx], axis=1)
    boot_bars = np.nanquantile(boot_means[shadow_idx, :], shadow_quantile, axis=0) \
        if len(shadow_idx) else np.zeros(n_bootstrap)
    confirm_freq = (boot_means > boot_bars[None, :]).mean(axis=1)

    # Diagnostics only - these no longer decide retention (review M3).
    pvals, cohens = [], []
    for i in range(len(all_players)):
        v = mat[i][~np.isnan(mat[i])]
        if len(v) > 1 and np.std(v, ddof=1) > 0:
            t, p = ttest_1samp(v, 0.0)
            pvals.append(float(p))
            cohens.append(float(np.mean(v) / np.std(v, ddof=1)))
        else:
            pvals.append(np.nan)
            cohens.append(np.nan)
    bh = _bh_adjust([1.0 if np.isnan(p) else p for p in pvals])

    rows = []
    for i, p in enumerate(all_players):
        v = mat[i][~np.isnan(mat[i])]
        sd = float(np.std(v, ddof=1)) if len(v) > 1 else np.nan
        rows.append({
            'player': names[i],
            'columns': ','.join(p),
            'n_columns': len(p),
            'is_shadow': bool(is_shadow(names[i])),
            'shapley': float(means[i]),
            'std': sd,
            'mc_se': float(sd / math.sqrt(len(v))) if len(v) > 1 else np.nan,
            'shadow_bar': shadow_bar,
            'margin_over_shadow': float(means[i] - shadow_bar),
            'confirmation_frequency': float(confirm_freq[i]),
            'diag_bh_p': float(bh[i]),
            'diag_cohens_d': cohens[i],
        })
    out = pd.DataFrame(rows).set_index('player')
    out['importance_confirmed'] = (~out['is_shadow']) & \
        (out['shapley'] > shadow_bar) & \
        (out['confirmation_frequency'] >= confirm_frequency_min)
    out = out.sort_values('shapley', ascending=False)

    v_full = float(np.nanmean(vf([c for p in all_players for c in p])))
    v_empty = float(np.nanmean(vf([])))
    audit_sum = float(np.nansum(means))
    info = {
        'mode': run_info['mode'],
        'n_subsets_evaluated': run_info['n_subsets_evaluated'],
        'n_model_fits': vf.n_fits,
        'n_real_players': len(players),
        'n_shadows': len(shadow_players),
        'learner': learner,
        'value_fn': value_fn,
        'cv_folds': cv_folds,
        'cv_repeats': cv_repeats,
        'shadow_quantile': shadow_quantile,
        'confirm_frequency_min': confirm_frequency_min,
        'shadow_bar': shadow_bar,
        'shadow_values': [float(s) for s in shadow_vals],
        'cluster_info': None if cluster_info is None else {
            k: v for k, v in cluster_info.items() if k != 'correlation'},
        'implementation_audit': {
            'sum_of_shapley_values': audit_sum,
            'v_full_minus_v_empty': v_full - v_empty,
            'abs_diff': abs(audit_sum - (v_full - v_empty)),
            'note': ('Validates ARITHMETIC, not statistical accuracy: the '
                     'efficiency property holds to machine precision in exact '
                     'mode even if every v(S) is badly estimated. In sampled '
                     'mode a large gap means too few permutations.'),
        },
    }
    info.update(run_info)
    return {'players': out, 'shadow_bar': shadow_bar, 'info': info}


def confirmed_columns(result):
    """Flatten the confirmed players back to a column list, ranked by Shapley."""
    df = result['players']
    conf = df[df['importance_confirmed']]
    cols = []
    for _, row in conf.iterrows():
        cols.extend(str(row['columns']).split(','))
    return [c for c in cols if c]


def ranked_players(result, confirmed_only=True):
    """Player names in descending Shapley order (shadows excluded)."""
    df = result['players']
    df = df[~df['is_shadow']]
    if confirmed_only:
        df = df[df['importance_confirmed']]
    return list(df.index)
