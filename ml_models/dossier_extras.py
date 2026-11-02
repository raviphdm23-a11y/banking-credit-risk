"""
Additional evidence for the Model Approval Dossier (Phase 2): analyses that regulators' reviewers asked for and that the
sealed run did not carry.

All of it is computed from the finished run's stored out-of-fold predictions and from the deployable scorer; nothing here
changes a sealed record. It answers:

* performance on the population the model actually SCORES (firms the control refers are excluded) vs all firms
* the PD-floor change (0.03% sealed vs 0.05% in force) on the backtest
* whether 60 exact duplicate rows inflate the cross-validated Gini
* challenger models (unbinned logistic, gradient boosting) on the same folds
* the effect of the adverse floor on blank values (omission must not lower risk)
* a mechanical sensitivity of PDs to an adverse shift in the profitability ratios
* grade concentration, rank-order, grade-level PD, a PD distribution baseline for monitoring
* reason-code examples, file identity
"""
import hashlib
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'backend'))
import calibration_gof as cgof          # noqa: E402
import missing_governance as mg         # noqa: E402
import rating_masterscale as rms        # noqa: E402
import run_scorecard as rsc             # noqa: E402
import selection as sel                 # noqa: E402
import staged_run as sr                 # noqa: E402

GRADE_FN = lambda p: rms.pd_to_grade(p)['grade']      # noqa: E731


def _gini(y, p):
    from sklearn.metrics import roc_auc_score
    a = float(roc_auc_score(y, p))
    return 2 * a - 1, a


def _perf(y, p):
    """Gini with DeLong-style interval (from selection.score_report), AUC, KS, capture with bootstrap CIs."""
    rep = sel.score_report(y, p)
    boot = rsc._bootstrap(y, p, n_boot=400)
    out = {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in rep.items()
           if isinstance(v, (int, float, np.floating))}
    out['gini_ci'] = [float(x) for x in rep.get('gini_ci', [np.nan, np.nan])] if 'gini_ci' in rep else None
    for q in rsc.CAPTURE_PERCENTILES:
        cap, lift = rsc._capture(y, p, q)
        out['capture_top_%d' % round(100 * q)] = float(cap)
    out['capture_ci'] = {k: v for k, v in boot['ci'].items() if k.startswith('capture')}
    out['brier_skill'] = boot['point']['brier_skill_oof']
    out['brier_skill_ci'] = boot['ci']['brier_skill_oof']
    out['ece'] = boot['point']['ece_oof']
    out['ece_ci'] = boot['ci']['ece_oof']
    out['slope'] = boot['point']['calibration_slope_oof']
    out['slope_ci'] = boot['ci']['calibration_slope_oof']
    out['n'] = int(len(y))
    out['events'] = int(np.sum(y))
    return out


def _backtest(y, p, floor, seed=42):
    bt = cgof.deployment_backtest(np.asarray(y), np.asarray(p), GRADE_FN, sr.GRADE_ORDER, random_state=seed, floor=floor)
    tb = bt['table']
    rows = tb.to_dict('records')
    hl = {str(g): {'H': float(v['H']), 'p': float(v['p_value'])} for g, v in bt['hl'].items()}
    real = [float(r['realised']) for r in rows]
    return {'floor': floor, 'passed': int(bt['grades_passed']), 'total': int(bt['grades_total']), 'n_heldout': int(bt['n_test']),
            'table': rows, 'hl': hl, 'ece_raw': float(bt['ece_raw']), 'ece_cal': float(bt['ece_cal']),
            'rank_breaks': int(sum(1 for a, b in zip(real, real[1:]) if b < a)),
            'share_top3': float(sum(r['n'] for r in rows[:3]) / sum(r['n'] for r in rows)),
            'largest_grade_share': float(max(r['n'] for r in rows) / sum(r['n'] for r in rows))}


def compute(run, df, mandatory, refer_col, csv_path, dictionary_path, cases_path):
    target = run.target
    y = df[target].astype(int).values
    cols = list(run.state['stage3']['selected_columns'])
    k = int(run.state['stage3']['decision']['selected_k'])
    oof = np.asarray(run.state['stage3']['extras']['oof_by_k'][k], dtype=float)
    scored = df[refer_col].notna().values if refer_col else np.ones(len(df), bool)
    out = {}

    # --- 1. all firms vs scored population -----------------------------------------------------------------------------------
    out['perf_all'] = _perf(y, oof)
    out['perf_scored'] = _perf(y[scored], oof[scored])
    out['referred'] = {'n': int((~scored).sum()), 'events': int(y[~scored].sum()),
                       'share_of_events': float(y[~scored].sum() / y.sum()), 'mean_oof_p': float(oof[~scored].mean())}
    out['backtest'] = {'all_floor_0.0003': _backtest(y, oof, 0.0003), 'all_floor_0.0005': _backtest(y, oof, 0.0005),
                       'scored_floor_0.0005': _backtest(y[scored], oof[scored], 0.0005)}

    # --- 2. duplicates ---------------------------------------------------------------------------------------------------------
    X = df[cols]
    dup = df.drop(columns=[target]).duplicated(keep=False).values
    nodup = ~df.duplicated(keep='first').values
    g0, a0 = _gini(y, oof)
    p_nd = sel.oof_predictions(X[nodup].reset_index(drop=True), pd.Series(y[nodup]), cols, learner='woe_logistic', random_state=42)
    g_nd, _ = _gini(y[nodup], p_nd)
    grp = pd.util.hash_pandas_object(df.drop(columns=[target]), index=False).values
    p_gr = sel.oof_predictions(X.reset_index(drop=True), pd.Series(y), cols, learner='woe_logistic', random_state=42, groups=grp)
    g_gr, _ = _gini(y, p_gr)
    out['duplicates'] = {'rows_in_duplicate_sets': int(dup.sum()), 'extra_copies': int(df.duplicated().sum()),
                         'gini_all': g0, 'gini_duplicates_removed': g_nd, 'gini_duplicates_kept_in_same_fold': g_gr}

    # --- 3. challengers on the scored population, same folds --------------------------------------------------------------------
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    Xs, ys = X[scored].reset_index(drop=True), y[scored]
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    ch = {}
    p_w = sel.oof_predictions(Xs, pd.Series(ys), cols, learner='woe_logistic', random_state=42)
    ch['woe_logistic_deployed_form'] = _gini(ys, p_w)
    for name, mk in (('logistic_on_raw_ratios', lambda: make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler(),
                                                                       LogisticRegression(C=1.0, max_iter=3000))),
                     ('gradient_boosting', lambda: HistGradientBoostingClassifier(max_iter=200, random_state=42))):
        p = np.zeros(len(ys))
        for tr, te in skf.split(Xs, ys):
            m = mk().fit(Xs.iloc[tr], ys[tr])
            p[te] = m.predict_proba(Xs.iloc[te])[:, 1]
        ch[name] = _gini(ys, p)
    out['challengers'] = {k_: {'gini': float(v[0]), 'auc': float(v[1])} for k_, v in ch.items()}
    out['challengers']['n'] = int(len(ys))

    # --- 4. deployed scorers: v1 (mandatory only) vs v2 (adverse floor on every non-mandatory variable) ----------------------------
    floorcols = [c for c in cols if c not in set(mandatory)]
    sc1, _ = mg.build_scorer(df, target, cols, mandatory_columns=list(mandatory), floor_columns=[], incomplete_policy='refer', random_state=42)
    sc2, rep2 = mg.build_scorer(df, target, cols, mandatory_columns=list(mandatory), floor_columns=floorcols, incomplete_policy='refer', random_state=42)
    r1, r2 = sc1.score(df[cols]), sc2.score(df[cols])
    blank_any = df[floorcols].isna().any(axis=1).values & scored
    m_ok = scored
    from sklearn.metrics import roc_auc_score
    out['blank_floor'] = {
        'floor_columns': floorcols, 'firms_with_a_blank_in_a_floor_column': int(blank_any.sum()),
        'bankrupt_share_among_them': float(y[blank_any].mean()) if blank_any.any() else None,
        'mean_pd_v1': float(r1.loc[blank_any, 'probability'].mean()), 'mean_pd_v2': float(r2.loc[blank_any, 'probability'].mean()),
        'in_sample_auc_v1_scored': float(roc_auc_score(y[m_ok], r1.loc[m_ok, 'probability'])),
        'in_sample_auc_v2_scored': float(roc_auc_score(y[m_ok], r2.loc[m_ok, 'probability'])),
        'lowest_blank_woe_gain': {c: float(sc1.encoder.woe_map_[c].get('__missing__', 0.0)) for c in floorcols if sc1.encoder.woe_map_[c].get('__missing__', 0.0) > 0},
        'flagged_v2': int((r2['decision'] == 'SCORE_FLAGGED').sum())}

    # --- 5. mechanical sensitivity: adverse shift of the profitability ratios by one robust SD ---------------------------------------
    pm = [c for c in cols if c.startswith(('ebit', 'gross_profit', 'net_profit', 'operating_profit', 'sales_profit'))]   # profitability ratios only
    Xsh = df[cols].copy()
    for c in pm:
        v = df[c].dropna()
        sd = float((v.quantile(.75) - v.quantile(.25)) / 1.349)
        Xsh[c] = Xsh[c] - sd
    base = sc2.score(df[cols]); shock = sc2.score(Xsh)
    ok = base['probability'].notna() & shock['probability'].notna()
    gb = base.loc[ok, 'probability'].map(GRADE_FN); gs = shock.loc[ok, 'probability'].map(GRADE_FN)
    order = {g: i for i, g in enumerate(sr.GRADE_ORDER)}
    worse = float(np.mean([order[b] > order[a] for a, b in zip(gb, gs)]))
    out['sensitivity'] = {'shifted_variables': pm, 'shift': 'minus one robust SD (IQR/1.349) on each', 'n': int(ok.sum()),
                          'mean_pd_before': float(base.loc[ok, 'probability'].mean()), 'mean_pd_after': float(shock.loc[ok, 'probability'].mean()),
                          'share_moving_to_worse_grade': worse}

    # --- 6. grade structure, monitoring baseline, reason codes ----------------------------------------------------------------------
    pv = base.loc[ok, 'probability'].values
    gr = pd.Series([GRADE_FN(x) for x in pv]).value_counts().reindex(sr.GRADE_ORDER).fillna(0).astype(int)
    out['baseline_distribution'] = {'grades': {g: int(n) for g, n in gr.items()}, 'n': int(len(pv)),
                                    'pd_deciles': [float(np.quantile(pv, q)) for q in np.linspace(0.1, 0.9, 9)]}
    spec = json.load(open(cases_path, encoding='utf-8'))
    ex = {}
    for name in [n for n in spec['cases'] if any(t in n for t in ('R2_', 'R3_', 'R5_'))]:
        row = pd.DataFrame([spec['cases'][name]]).reindex(columns=cols)
        for c in cols:
            row[c] = pd.to_numeric(row[c], errors='coerce')
        W = sc2.encoder.transform(sc2._prep(row)).values.astype(float)[0]
        contrib = sc2.coef * W
        tab = sorted(zip(cols, row.iloc[0].tolist(), W, contrib), key=lambda t: -abs(t[3]))[:5]
        pdv = float(sc2.score(row).iloc[0]['probability'])
        ex[name] = {'pd': pdv, 'grade': GRADE_FN(pdv),
                    'top_reasons': [{'variable': a, 'value': (None if pd.isna(b) else float(b)), 'woe': float(c), 'contribution': float(d)} for a, b, c, d in tab]}
    out['reason_code_examples'] = ex

    # --- 7. file identity -------------------------------------------------------------------------------------------------------------
    h = hashlib.sha256(open(csv_path, 'rb').read()).hexdigest()
    dic = json.load(open(dictionary_path, encoding='utf-8')) if dictionary_path else {}
    fname = os.path.basename(csv_path)
    uci = next(((k_, v) for k_, v in (dic.get('files') or {}).items() if v.get('current_filename') == fname), (None, None))
    out['file'] = {'name': fname, 'sha256': h, 'bytes': os.path.getsize(csv_path), 'rows': int(len(df)),
                   'uci_file': uci[0], 'uci_description': uci[1]}
    return out
