"""
v3_pipeline.py - end-to-end orchestration of METHODOLOGY.md v3.

Stage 0  feature_governance   eligibility + availability tags, sentinel audit
Stage 1  stage1_screen        univariate screening -> candidate columns
Stage 2  shapley_utils        grouped players, shadow null -> importance ranking
Stage 3  selection            parsimony curve -> selected subset (or none)
Stage 4  trainer              isotonic calibration of the selected model
Report   model_card_markdown  the mandatory section-10.2 card

The two-stage split between Stage 2 (attribution) and Stage 3 (selection) is
deliberate and is the central correction in v3 - see METHODOLOGY v3 s1 and
review finding M1. Shapley ranks; a pre-declared tolerance selects.

Usage
-----
    import v3_pipeline as v3
    out = v3.run_pipeline(df, target='target', dataset_name='HMEQ')
    print(out['report'])

ASCII-only in emitted strings (Windows cp1252 console).
"""
import json
import warnings

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu

import binning as bn
import feature_governance as fg
import selection as sel
import shapley_utils as su

MIN_EXPECTED_GATE = 5.0
IV_MIN = 0.02
CRAMERS_V_REPORT_ONLY = True


def _md_table(frame, index_name='column', floatfmt='%.4f'):
    """Markdown table without requiring the optional `tabulate` dependency.

    pandas.DataFrame.to_markdown needs tabulate, which is not in this
    project's requirements.txt; adding a dependency just to format a report
    table is not worth it.
    """
    df = frame.copy()
    header = [index_name] + [str(c) for c in df.columns]
    lines = ['| ' + ' | '.join(header) + ' |',
             '|' + '|'.join(['---'] * len(header)) + '|']
    for idx, row in df.iterrows():
        cells = [str(idx)]
        for v in row:
            if isinstance(v, (float, np.floating)):
                cells.append('' if (v is None or (isinstance(v, float) and np.isnan(v)))
                             else (floatfmt % v))
            else:
                cells.append(str(v))
        lines.append('| ' + ' | '.join(cells) + ' |')
    return chr(10).join(lines)


# ===========================================================================
# Stage 1 - univariate screening (METHODOLOGY v3 s4)
# ===========================================================================

def _cramers_v(labels, y):
    ct = pd.crosstab(pd.Series(labels).astype(str), pd.Series(np.asarray(y)))
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return np.nan, np.nan, np.nan, np.nan
    chi2, p, dof, expected = chi2_contingency(ct)
    n = ct.values.sum()
    r, k = ct.shape
    v = np.sqrt((chi2 / n) / max(min(r - 1, k - 1), 1))
    return float(v), float(chi2), float(p), float(expected.min())


def _is_orderable(series):
    """Mann-Whitney needs rankable values: numeric continuous/ordinal only.

    Nominal categoricals are excluded (METHODOLOGY v3 s4.4 / Step 3a): ranking
    unordered category labels is meaningless, so those escalate to the
    single-column model check instead.
    """
    return bool(pd.api.types.is_numeric_dtype(series))


def stage1_screen(df, target, tags=None, iv_min=IV_MIN, model_check_fn=None,
                  verbose=True):
    """Per-column univariate screen. Returns (table, candidates).

    Decision logic, in order:
      1. IV (monotonic-WOE binned) is the single primary statistic (v3 s4.1;
         v2's 'IV >= 0.02 OR CramersV >= 0.1' rule is withdrawn - the two are
         monotone transforms of the same chi-square, so the OR was redundant,
         and it was adopted after seeing which columns it admitted).
      2. Cramers V / chi-square / p-value are reported DESCRIPTIVELY only.
      3. Reliability gate on min_expected >= 5.
      4. Escalation when the gate fails: Mann-Whitney for orderable columns,
         single-column model check for nominal ones.
      5. Escalation when binning is unstable or the shape looks non-monotonic
         (v3 s4.2): decided by model check, not by IV.
    """
    y = df[target]
    cols = [c for c in df.columns if c != target]
    rows = []
    for c in cols:
        s = df[c]
        lab, info = bn.woe_bin(s, y)
        sens = bn.iv_sensitivity(s, y, iv_min=iv_min)
        v, chi2, p, min_exp = _cramers_v(lab, y)
        gate_ok = bool(np.isfinite(min_exp) and min_exp >= MIN_EXPECTED_GATE)
        orderable = _is_orderable(s)

        mw_p = np.nan
        escalation = 'none'
        if not gate_ok:
            if orderable:
                g0 = s[y == 0].dropna()
                g1 = s[y == 1].dropna()
                if len(g0) > 0 and len(g1) > 0 and s.nunique() > 1:
                    mw_p = float(mannwhitneyu(g0, g1).pvalue)
                escalation = 'mann_whitney'
            else:
                escalation = 'model_check_nominal'
        if sens['escalate_to_model_check']:
            escalation = ('model_check_shape' if escalation == 'none'
                          else escalation + '+model_check_shape')

        # DECISION LOGIC. Escalation may only ever RESCUE a column that the
        # primary statistic understates - it must never VETO a column the
        # primary statistic already supports. v1 of this function got this
        # wrong: a shape flag sent a column to a single-column model check,
        # which then rejected it. That inverts the method, because a
        # one-column model on a small sample is a WEAKER test than IV, and
        # "weak alone, useful in combination" is the premise the whole
        # methodology rests on (it is why Stage 2 exists at all). Caught on
        # TH02, where YOB - IV 0.119 reliable, non-monotonic IV 0.288, and an
        # obviously real age effect - was being rejected on a single-column
        # Gini CI.
        iv_mono = sens['primary_iv']
        iv_free = sens['woe_nonmonotonic']
        gate_trustworthy = gate_ok

        # When monotonicity was enforced but the shape is genuinely
        # non-monotonic, the monotone IV is an artefact of the constraint, so
        # the unconstrained value is the fair reading (v3 s4.2).
        iv_decisive = max(iv_mono, iv_free) if sens['shape_nonmonotonic'] else iv_mono

        # When the IV verdict flips across binnings, accept the most
        # favourable binning as a rescue rather than discarding the column -
        # the instability is reported, and Stage 2 adjudicates properly.
        if sens['binning_sensitive']:
            iv_decisive = max(iv_decisive, sens['q5'], sens['q10'], sens['q20'])

        passes = bool(gate_trustworthy and iv_decisive >= iv_min)
        verdict_source = 'iv' if not sens['shape_nonmonotonic'] else 'iv(non-monotonic)'

        rows_extra = {'model_check_gini': np.nan, 'model_check_gini_ci_low': np.nan}

        # Rescue path 1: gate failed, column orderable -> a significant rank
        # test says the relationship is real even though the binned statistic
        # cannot be trusted.
        if not passes and escalation.startswith('mann_whitney') and np.isfinite(mw_p):
            if mw_p < 0.05:
                passes = True
                verdict_source = 'rescued by Mann-Whitney (gate failed)'

        # Rescue path 2: gate failed on a NOMINAL column, where Mann-Whitney is
        # invalid - the single-column model check is the only valid escalation
        # (v3 s4.4 / Step 3a). Still a rescue, never a veto.
        if not passes and model_check_fn is not None and (
                'model_check_nominal' in escalation or not gate_trustworthy):
            mc = model_check_fn(df, target, c)
            rows_extra = {'model_check_gini': mc['gini'],
                          'model_check_gini_ci_low': mc['gini_ci_low']}
            if mc['gini_ci_low'] > 0:
                passes = True
                verdict_source = 'rescued by model check (gini CI excludes 0)'

        rec = {
            'column': c,
            'iv_woe': iv_mono,
            'iv_nonmonotonic': iv_free,
            'iv_decisive': iv_decisive,
            'iv_q5': sens['q5'], 'iv_q10': sens['q10'], 'iv_q20': sens['q20'],
            'binning_sensitive': sens['binning_sensitive'],
            'shape_nonmonotonic': sens['shape_nonmonotonic'],
            'monotonic_iv_cost_rel': sens['monotonic_iv_cost_relative'],
            'cramers_v_descriptive': v,
            'chi2': chi2, 'p_value': p, 'min_expected': min_exp,
            'gate_ok': gate_ok, 'n_bins': info['n_bins'], 'bin_kind': info['kind'],
            'escalation': escalation, 'mann_whitney_p': mw_p,
            'passes_screen': passes, 'verdict_source': verdict_source,
        }
        rec.update(rows_extra)
        if tags is not None and c in tags.index:
            rec['eligibility'] = tags.loc[c, 'eligibility']
            rec['availability'] = tags.loc[c, 'availability']
        rows.append(rec)

    table = pd.DataFrame(rows).set_index('column').sort_values('iv_woe', ascending=False)
    candidates = [c for c in table.index if table.loc[c, 'passes_screen']]
    if verbose:
        print('[stage1] %d of %d columns pass the screen (IV >= %.3f primary)'
              % (len(candidates), len(cols), iv_min), flush=True)
        n_esc = int((table['escalation'] != 'none').sum())
        if n_esc:
            print('[stage1] %d column(s) required escalation (gate failure, unstable '
                  'binning, or non-monotonic shape)' % n_esc, flush=True)
    return table, candidates


def single_column_model_check(df, target, column, learner='woe_logistic',
                              cv_folds=5, random_state=42, n_boot=300, groups=None):
    """Stage-1 model check: is this one column better than chance?

    v3 s4.5 reports a Gini with a confidence interval and requires the CI to
    exclude zero, rather than eyeballing AUC against 0.5 as v2 did.
    """
    y = df[target]
    oof = sel.oof_predictions(df[[column]], y, [column], learner=learner,
                              cv_folds=cv_folds, random_state=random_state, groups=groups)
    rep = sel.score_report(y, oof, n_boot=n_boot, random_state=random_state)
    return {'column': column, 'gini': rep['gini'],
            'gini_ci_low': rep['gini_ci_low'], 'gini_ci_high': rep['gini_ci_high'],
            'auc': rep['auc']}


# ===========================================================================
# Stage 0 helper - sentinel audit with the leakage screen
# ===========================================================================

def stage0_governance(df, target, eligibility_overrides=None,
                      availability_overrides=None, verbose=True):
    """Tags + sentinel/leakage audit (METHODOLOGY v3 s3)."""
    tags = fg.classify_columns(df, target=target,
                               eligibility_overrides=eligibility_overrides,
                               availability_overrides=availability_overrides)
    sentinels = bn.detect_sentinels(df, columns=[c for c in df.columns if c != target])
    lift = bn.sentinel_lift(df, target, {c: list(v.keys()) for c, v in sentinels.items()}) \
        if sentinels else {}
    leakage = {c: d for c, d in lift.items() if d.get('leakage_candidate')}
    if verbose:
        s = fg.summary(tags)
        print('[stage0] eligibility: %s' % s['eligibility'], flush=True)
        print('[stage0] availability: %s' % s['availability'], flush=True)
        if leakage:
            print('[stage0] LEAKAGE CANDIDATES (event-rate lift >= 3x on a sentinel '
                  'value) - resolve against a data dictionary before retaining: %s'
                  % sorted(leakage), flush=True)
    for c in leakage:
        warnings.warn(
            'SENTINEL LEAKAGE CANDIDATE: column ' + str(c) + ' has sentinel value(s) '
            + str(sorted(sentinels[c])) + ' whose event rate is '
            + ('%.3f' % leakage[c]['event_rate_sentinel']) + ' vs a base rate of '
            + ('%.3f' % leakage[c]['base_rate']) + ' (lift '
            + ('%.1fx' % leakage[c]['lift_vs_base']) + '). If these codes encode an '
            'account status such as charge-off, that is outcome information. See '
            'METHODOLOGY.md v3 section 3.5.', UserWarning, stacklevel=2)
    return {'tags': tags, 'sentinels': sentinels, 'sentinel_lift': lift,
            'leakage_candidates': leakage}


# ===========================================================================
# Full pipeline
# ===========================================================================

def _missing_floor_report(df, target, columns, floor_columns=None, random_state=42):
    """Build the scoring-time adverse-missing-floor artifact for the selected set
    (METHODOLOGY v3 s9 #10). Fits a WOEEncoder on the true (unfloored) data, then
    floors the `__missing__` bin of the governed columns to the most-adverse
    observed WOE so omission can never lower predicted risk.

    This is a GOVERNANCE OVERLAY on scoring, not a change to selection or to the
    evaluation metrics: the pipeline's Stage 1-4 numbers are computed on the true
    WOE (honest, including each row's real missingness). `floor_columns=None`
    governs every selected column that has a missing bin (conservative default);
    pass an explicit list to restrict to applicant-influenceable columns.
    """
    X = df[columns].copy()
    for c in X.columns:
        if X[c].dtype != object:
            X[c] = X[c].astype('float64')
    enc = bn.WOEEncoder().fit(X, df[target])
    cols_to_floor = (list(floor_columns) if floor_columns is not None
                     else [c for c in columns if bn.MISSING_LABEL in enc.woe_map_.get(c, {})])
    changes = bn.adverse_missing_floor(enc, cols_to_floor)
    closed = sorted(c for c, r in changes.items() if r['changed'])
    return {'policy': 'adverse_floor', 'floor_columns': cols_to_floor,
            'changes': changes, 'n_changed': len(closed),
            'protective_missing_closed': closed}


def run_pipeline(df, target='target', dataset_name='dataset', *,
                 learner='woe_logistic', value_fn='auc',
                 cluster_threshold=0.7, n_shadows=10, shadow_quantile=0.95,
                 confirm_frequency_min=0.80, n_samples=200, cv_repeats=1,
                 shapley_mode='auto', exact_max_players=15,
                 max_relative_gini_loss=0.05, alpha=0.05,
                 missing_policy='as_learned', floor_columns=None,
                 mandatory_columns=None, incomplete_policy='reject',
                 eligibility_overrides=None, availability_overrides=None,
                 run_model_checks=True, random_state=42, verbose=True, groups=None,
                 shapley_row_subsample=None, time_values=None, oot_test_frac=0.3):
    """Stages 0-4 end to end. Returns a dict including a markdown report.

    missing_policy: 'as_learned' (default) keeps each column's learned WOE,
        including the informative `__missing__` bin. 'adverse_floor' additionally
        emits a scoring-time governance overlay (see `_missing_floor_report`) that
        prevents omission from lowering predicted risk; it does NOT change the
        selection decision or the reported metrics. `floor_columns` optionally
        restricts the overlay to named (applicant-influenceable) columns.

    mandatory_columns: columns declared ESSENTIAL at the start of the process. A
        scored application missing any of them is INCOMPLETE. incomplete_policy
        decides what then happens: 'reject' / 'refer' (PRIMARY gate - not scored)
        or 'adverse_score' (FALLBACK - scored at worst-case WOE). When set (or when
        missing_policy='adverse_floor'), the pipeline builds a deployment `scorer`
        (missing_governance.Scorer) and returns it; this is a scoring-time overlay
        and does not change selection or the Stage 1-4 metrics.
    """
    if missing_policy not in ('as_learned', 'adverse_floor'):
        raise ValueError("missing_policy must be 'as_learned' or 'adverse_floor'")
    if incomplete_policy not in ('reject', 'refer', 'adverse_score'):
        raise ValueError("incomplete_policy must be 'reject', 'refer' or 'adverse_score'")
    df = df.reset_index(drop=True)

    s0 = stage0_governance(df, target, eligibility_overrides,
                           availability_overrides, verbose=verbose)
    tags = s0['tags']

    mc = (lambda d, t, c: single_column_model_check(d, t, c, learner=learner,
                                                    random_state=random_state,
                                                    groups=groups)) \
        if run_model_checks else None
    s1_table, candidates = stage1_screen(df, target, tags=tags,
                                         model_check_fn=mc, verbose=verbose)
    if not candidates:
        return {'dataset': dataset_name, 'stage0': s0, 'stage1': s1_table,
                'candidates': [], 'report': '(no column passed Stage 1)'}

    X = df[candidates]
    y = df[target]

    s2 = su.shapley_importance(
        X, y, learner=learner, value_fn=value_fn, cv_repeats=cv_repeats,
        cluster_threshold=cluster_threshold, n_shadows=n_shadows,
        shadow_quantile=shadow_quantile, confirm_frequency_min=confirm_frequency_min,
        n_samples=n_samples, random_state=random_state,
        mode=shapley_mode, exact_max_players=exact_max_players,
        progress_every=(50 if verbose else 0), cv_groups=groups,
        row_subsample=shapley_row_subsample)

    ranked = su.ranked_players(s2, confirmed_only=True)
    player_cols = {p: str(s2['players'].loc[p, 'columns']).split(',')
                   for p in s2['players'].index}
    if not ranked:
        return {'dataset': dataset_name, 'stage0': s0, 'stage1': s1_table,
                'candidates': candidates, 'stage2': s2,
                'report': '(no player cleared the shadow-null bar)'}

    curve, extras = sel.parsimony_curve(X, y, ranked, player_cols, learner=learner,
                                        random_state=random_state, progress=verbose,
                                        groups=groups)
    decision = sel.select_parsimonious(curve,
                                       max_relative_gini_loss=max_relative_gini_loss,
                                       alpha=alpha)

    selected_cols = []
    if decision['tolerance_met']:
        for p in decision['selected_players']:
            selected_cols.extend(player_cols[p])
    # Governance warnings fire on whatever is actually retained.
    retained = selected_cols or [c for p in ranked for c in player_cols[p]]
    offenders = fg.warn_on_retained_ineligible(retained, tags, context=dataset_name)
    avail_flags = fg.availability_warnings(retained, tags, context=dataset_name)

    calib = None
    if selected_cols:
        calib = _calibrate(df, target, selected_cols, random_state=random_state,
                           groups=groups)

    # Deployment-relevant calibration backtest: assess the CALIBRATED model with a
    # cluster-robust per-grade test (auto cluster-aware when `groups` present).
    # Reuses the selected model's group-aware OOF from the parsimony stage, so no
    # refit. This is the governing calibration evidence for G4 (CRE36.122).
    backtest = None
    if selected_cols:
        try:
            import calibration_gof as cgof
            import rating_masterscale as _rms
            k_sel = len(decision.get('selected_players') or [])
            oof_sel = extras.get('oof_by_k', {}).get(k_sel, extras.get('oof_full'))
            if oof_sel is not None:
                _order = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C', 'D']
                backtest = cgof.deployment_backtest(
                    np.asarray(df[target].values), np.asarray(oof_sel),
                    lambda pd_: _rms.pd_to_grade(pd_)['grade'], _order,
                    groups=groups, random_state=random_state)
                if verbose:
                    print('[stage4] calibrated per-grade backtest (%s): %d/%d pass'
                          % (backtest['method'], backtest['grades_passed'],
                             backtest['grades_total']), flush=True)
        except Exception as _e:   # backtest is diagnostic; never break the run
            if verbose:
                print('[stage4] backtest skipped: %r' % _e, flush=True)

    # Out-of-time (train-past / test-future) validation, reported next to the
    # in-time score whenever a calendar-time vector is supplied (panel runs).
    # Diagnostic only: decides nothing, invents no threshold. Substantiates or
    # retires a TIME-LEAKAGE condition at the gates (R7).
    oot = None
    if selected_cols and time_values is not None:
        try:
            import oot_validation as _oot
            import rating_masterscale as _rms2
            _k = len(decision.get('selected_players') or [])
            _row = curve[curve['k'] == _k]
            _in_gini = float(_row['gini'].iloc[0]) if len(_row) else None
            oot = _oot.out_of_time_validation(
                df[selected_cols], df[target].values, selected_cols, time_values,
                groups=groups, learner=learner, test_frac=oot_test_frac,
                grade_fn=lambda pd_: _rms2.pd_to_grade(pd_)['grade'],
                grade_order=['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C', 'D'],
                in_time_gini=_in_gini, random_state=random_state)
            if verbose and oot.get('ok'):
                print('[stage4] out-of-time: Gini %.4f (in-time %s); per-grade %s/%s'
                      % (oot['gini'],
                         ('%.4f' % oot['in_time_gini']) if oot['in_time_gini'] is not None else 'n/a',
                         oot.get('grades_passed', '?'), oot.get('grades_total', '?')), flush=True)
        except Exception as _e:   # diagnostic; never break the run
            if verbose:
                print('[stage4] out-of-time skipped: %r' % _e, flush=True)

    # resolve the omission-floor set once, shared by the report artifact and scorer
    resolved_floor = None
    if missing_policy == 'adverse_floor':
        resolved_floor = (floor_columns if floor_columns is not None
                          else [c for c in selected_cols])

    missing_floor = None
    if missing_policy == 'adverse_floor' and selected_cols:
        missing_floor = _missing_floor_report(df, target, selected_cols,
                                               resolved_floor, random_state)

    # Deployment scorer with the mandatory gate + adverse fallback (+ omission floor).
    scorer = None
    governance = None
    mand = [c for c in (mandatory_columns or [])]
    if selected_cols and (mand or missing_policy == 'adverse_floor'):
        import missing_governance as mgov
        scorer, governance = mgov.build_scorer(
            df, target, selected_cols,
            mandatory_columns=mand,
            floor_columns=(resolved_floor or []),
            incomplete_policy=incomplete_policy, random_state=random_state)

    report = build_report(dataset_name, df, target, s0, s1_table, candidates, s2,
                          curve, decision, selected_cols, offenders, avail_flags,
                          calib, learner=learner, value_fn=value_fn,
                          missing_floor=missing_floor, governance=governance,
                          backtest=backtest, oot=oot)
    return {'dataset': dataset_name, 'stage0': s0, 'stage1': s1_table,
            'candidates': candidates, 'stage2': s2, 'curve': curve,
            'decision': decision, 'selected_columns': selected_cols,
            'ineligible_retained': offenders, 'availability_flags': avail_flags,
            'calibration': calib, 'backtest': backtest, 'oot': oot,
            'missing_policy': missing_policy,
            'missing_floor': missing_floor, 'incomplete_policy': incomplete_policy,
            'mandatory_columns': mand, 'governance': governance,
            'scorer': scorer, 'report': report}


def _calibrate(df, target, columns, random_state=42, groups=None):
    """Stage 4: isotonic calibration of the PRIMARY (WOE-logistic) model on a held-out split.

    Changed 2026-10-25. Earlier versions (kept as `_calibrate_xgboost_legacy`) trained an XGBoost
    model here, so the Stage-4 calibration table described the secondary learner, not the model that
    is selected, backtested and deployed. This version fits exactly the deployed scorer
    (`missing_governance.build_scorer`: WOE encoder + L2 logistic + isotonic map learned on 5-fold
    out-of-fold scores) on the training part of an 80/20 split and reports Brier and ECE before and
    after isotonic on the held-out part. `groups` makes the split group-aware (GroupShuffleSplit)
    so no entity straddles train and test. The returned keys are unchanged.
    """
    import missing_governance as mg
    X = df[list(columns)].copy()
    y = df[target].astype(int)
    if groups is None:
        from sklearn.model_selection import train_test_split
        tr, te = train_test_split(np.arange(len(df)), test_size=0.2, stratify=y,
                                  random_state=random_state)
    else:
        from sklearn.model_selection import GroupShuffleSplit
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
        tr, te = next(gss.split(X, y, groups=np.asarray(groups)))
    train = df.iloc[tr][list(columns) + [target]]
    sc, _ = mg.build_scorer(train, target, list(columns), random_state=random_state)
    Xte, yte = df.iloc[te][list(columns)], y.iloc[te].values
    W = sc.encoder.transform(sc._prep(Xte)).values.astype(float)
    raw = 1.0 / (1.0 + np.exp(-(sc.intercept + W @ sc.coef)))
    cal = np.asarray(sc.iso.transform(raw), dtype=float)
    from sklearn.metrics import brier_score_loss, roc_auc_score
    base = float(brier_score_loss(yte, np.full(len(yte), float(y.iloc[tr].mean()))))
    return {
        'baseline_brier_always_base_rate': round(base, 4),
        'raw_brier': round(float(brier_score_loss(yte, raw)), 4),
        'raw_ece': round(sel.expected_calibration_error(yte, raw), 4),
        'calibrated_brier': round(float(brier_score_loss(yte, cal)), 4),
        'calibrated_ece': round(sel.expected_calibration_error(yte, cal), 4),
        'calibrated_auc': round(float(roc_auc_score(yte, cal)), 4),
        'method': 'isotonic', 'cv': 5, 'learner': 'woe_logistic (deployed scorer)',
        'n_heldout': int(len(te)),
    }


def _calibrate_xgboost_legacy(df, target, columns, random_state=42, groups=None):
    """LEGACY (before 2026-10-25): isotonic calibration of an XGBoost model on the selected columns.
    Not called by the pipeline any more; kept only so older Stage-4 tables can be regenerated.
    It describes the secondary learner, not the deployed WOE-logistic model.

    `groups` (panel/entity key) makes the calibration holdout split group-aware
    (GroupShuffleSplit) so no entity straddles train/test; None keeps the
    stratified split unchanged.
    """
    from trainer import evaluate_calibration, train_model, _load_hyperparameters
    X = df[columns].copy()
    for c in X.columns:
        if X[c].dtype == object:
            X[c] = X[c].astype('category')
    y = df[target]
    if groups is None:
        from sklearn.model_selection import train_test_split
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y,
                                              random_state=random_state)
    else:
        from sklearn.model_selection import GroupShuffleSplit
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
        tr, te = next(gss.split(X, y, groups=np.asarray(groups)))
        Xtr, Xte, ytr, yte = X.iloc[tr], X.iloc[te], y.iloc[tr], y.iloc[te]
    hp = _load_hyperparameters()
    raw = train_model(Xtr, ytr, hp, model_type='xgboost')
    rep, _ = evaluate_calibration(raw, Xtr, ytr, Xte, yte, hp)
    return rep


# ===========================================================================
# Reporting (METHODOLOGY v3 s10)
# ===========================================================================

def build_report(dataset_name, df, target, s0, s1_table, candidates, s2, curve,
                 decision, selected_cols, offenders, avail_flags, calib,
                 learner='woe_logistic', value_fn='auc', missing_floor=None,
                 governance=None, backtest=None, oot=None):
    tags = s0['tags']
    L = []
    L.append('# ' + dataset_name + ' - Methodology v3 results')
    L.append('')
    L.append('Rows: %d | Raw columns: %d | Event rate: %.4f'
             % (len(df), len([c for c in df.columns if c != target]), df[target].mean()))
    L.append('')
    L.append('Learner (value function): `%s` | Value function: `%s`' % (learner, value_fn))
    L.append('')

    L.append('## Stage 0 - governance')
    L.append('')
    L.append(fg.governance_table_markdown(tags))
    L.append('')
    if s0['leakage_candidates']:
        L.append('**Sentinel leakage candidates (unresolved):** `%s` - see METHODOLOGY v3 s3.5.'
                 % '`, `'.join(sorted(s0['leakage_candidates'])))
        L.append('')

    L.append('## Stage 1 - univariate screening')
    L.append('')
    show = ['iv_woe', 'iv_q5', 'iv_q10', 'iv_q20', 'binning_sensitive',
            'shape_nonmonotonic', 'cramers_v_descriptive', 'min_expected',
            'gate_ok', 'escalation', 'mann_whitney_p', 'passes_screen']
    L.append(_md_table(s1_table[[c for c in show if c in s1_table.columns]].round(4)))
    L.append('')
    L.append('Candidates passing Stage 1: %d of %d.'
             % (len(candidates), len([c for c in df.columns if c != target])))
    L.append('')

    L.append('## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)')
    L.append('')
    p = s2['players'].copy()
    p['player'] = p.index
    cols = ['n_columns', 'is_shadow', 'shapley', 'mc_se', 'confirmation_frequency',
            'importance_confirmed', 'diag_bh_p', 'diag_cohens_d']
    L.append(_md_table(p[cols].round(5), index_name='player', floatfmt='%.5f'))
    L.append('')
    info = s2['info']
    L.append('Shadow bar (%.0fth pct of %d shadow players): **%.5f**. Mode: %s. '
             'Subsets evaluated: %d. Model fits: %d.'
             % (100 * info['shadow_quantile'], info['n_shadows'], s2['shadow_bar'],
                info['mode'], info['n_subsets_evaluated'], info['n_model_fits']))
    L.append('')
    a = info['implementation_audit']
    L.append('Implementation audit (efficiency property): sum of Shapley values %.6f '
             'vs v(full)-v(empty) %.6f, abs diff %.2e. %s'
             % (a['sum_of_shapley_values'], a['v_full_minus_v_empty'], a['abs_diff'],
                a['note']))
    L.append('')
    L.append('`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing '
             '(METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted '
             'noise column can show a highly "significant" BH p-value, which is '
             'precisely why v2\'s significance-based rule was withdrawn.')
    L.append('')

    L.append('## Stage 3 - selection (parsimony curve + pre-declared tolerance)')
    L.append('')
    L.append(sel.curve_markdown(curve, decision))
    L.append('')

    if selected_cols:
        L.append('### Selected feature set')
        L.append('')
        L.append(', '.join('`' + fg.flagged_name(c, tags) + '`' for c in selected_cols))
        L.append('')
    else:
        L.append('### No feature set selected')
        L.append('')
        L.append('No subset met the pre-declared tolerance. Reported as such rather '
                 'than substituting the best available k.')
        L.append('')

    if calib:
        L.append('## Stage 4 - calibration (%s)' % calib.get('learner', 'XGBoost, legacy record'))
        L.append('')
        L.append('| | Baseline (base rate) | Raw | Calibrated |')
        L.append('|---|---:|---:|---:|')
        L.append('| Brier | %.4f | %.4f | **%.4f** |'
                 % (calib['baseline_brier_always_base_rate'], calib['raw_brier'],
                    calib['calibrated_brier']))
        L.append('| ECE | - | %.4f | **%.4f** |' % (calib['raw_ece'], calib['calibrated_ece']))
        L.append('')

    if backtest:
        import calibration_gof as _cgof
        bmd = _cgof.backtest_markdown(backtest)
        if bmd:
            L.append(bmd)
            L.append('')

    if oot:
        import oot_validation as _ootm
        omd = _ootm.oot_markdown(oot)
        if omd:
            L.append(omd)
            L.append('')

    if missing_floor and missing_floor.get('changes'):
        L.append('## Missing-value policy - adverse floor (anti-omission, METHODOLOGY v3 s9 #10)')
        L.append('')
        closed = missing_floor.get('protective_missing_closed') or []
        if closed:
            L.append('Scoring-time overlay: an omitted value on a governed column is scored at that '
                     'column\'s most-adverse observed WOE, so disclosing less can never lower predicted '
                     'risk. Columns whose `__missing__` bin was protective and is now floored:')
            L.append('')
            L.append('| Column | Missing WOE (learned) | -> floored to worst bin |')
            L.append('|---|---:|---:|')
            for c in closed:
                r = missing_floor['changes'][c]
                L.append('| `%s` | %+.4f | %+.4f |'
                         % (c, r['old_missing_woe'], r['new_missing_woe']))
            L.append('')
        else:
            L.append('No governed column had a protective `__missing__` bin; the floor changed nothing '
                     '(omission was already non-advantageous on the selected set).')
            L.append('')
        L.append('This overlay is applied at scoring only: Stage 1-4 metrics above are computed on the '
                 'true (unfloored) WOE, so complete/honest applicants are unaffected. See '
                 '`SHARP_HMEQ.md` Appendix B (Finding F6).')
        L.append('')

    if governance:
        import missing_governance as mgov
        gmd = mgov.governance_report_markdown(governance)
        if gmd:
            L.append(gmd)
            L.append('')

    disc = fg.disclosure_block(tags, selected_cols or None)
    if disc:
        L.append('## Regulatory eligibility')
        L.append('')
        L.append(disc)
        L.append('')
    for tag, cols_ in (avail_flags or {}).items():
        if cols_:
            L.append('**Availability caveat (%s):** `%s`. Results including these are '
                     'not an origination-time (application) model; report with and '
                     'without them (METHODOLOGY v3 s3.3).' % (tag, '`, `'.join(cols_)))
            L.append('')
    return '\n'.join(L)


def model_card_markdown(dataset_name, result, intended_use='Methodological research only.'):
    """The mandatory section-10.2 model card."""
    tags = result['stage0']['tags']
    sel_cols = result.get('selected_columns') or []
    L = ['# Model card - ' + dataset_name, '',
         '**Intended use:** ' + intended_use,
         '**NOT for use in:** any live or production credit decision.', '']
    L.append('## Features')
    L.append('')
    L.append('| Column | Eligibility | Availability |')
    L.append('|---|---|---|')
    for c in sel_cols:
        if c in tags.index:
            L.append('| `%s` | %s | %s |' % (c, tags.loc[c, 'eligibility'],
                                             tags.loc[c, 'availability']))
    L.append('')
    L.append('## Regulatory-ineligible features retained')
    L.append('')
    off = result.get('ineligible_retained') or []
    L.append(('`' + '`, `'.join(off) + '`') if off else 'None.')
    L.append('')
    dec = result.get('decision') or {}
    L.append('## Selection')
    L.append('')
    L.append('Tolerance met: %s. Rule: %s' % (dec.get('tolerance_met'), dec.get('rule')))
    L.append('')
    if result.get('calibration'):
        c = result['calibration']
        L.append('## Calibration')
        L.append('')
        L.append('Method: %s. Brier %.4f -> %.4f. ECE %.4f -> %.4f.'
                 % (c['method'], c['raw_brier'], c['calibrated_brier'],
                    c['raw_ece'], c['calibrated_ece']))
        L.append('')
    mf = result.get('missing_floor')
    if mf:
        L.append('## Missing-value policy')
        L.append('')
        closed = mf.get('protective_missing_closed') or []
        L.append('Scoring-time adverse floor active on: %s.'
                 % (('`' + '`, `'.join(closed) + '`') if closed
                    else 'no column needed it (no protective missing bin)'))
        L.append('')
    gov = result.get('governance')
    if gov and (gov.get('mandatory_columns') or gov.get('not_selected_mandatory')):
        L.append('## Mandatory-field gate')
        L.append('')
        L.append('Incomplete-application policy: **%s**. Mandatory columns: %s.'
                 % (gov['incomplete_policy'],
                    ('`' + '`, `'.join(gov['mandatory_columns']) + '`')
                    if gov['mandatory_columns'] else '(none in selected model)'))
        if gov.get('not_selected_mandatory'):
            L.append('')
            L.append('Declared-mandatory but not selected (gate as data-quality only): `%s`.'
                     % '`, `'.join(gov['not_selected_mandatory']))
        L.append('')
    L.append('## Known limitations')
    L.append('')
    L.append('- Accept-only sample: feature strength is attenuated by the original '
             'approval policy (METHODOLOGY v3 s3.2). No reject inference performed.')
    L.append('- No out-of-time validation; all cross-validation is i.i.d. random.')
    L.append('- Importance is conditional on the value-function learner used.')
    L.append('')
    return '\n'.join(L)
