"""
sanity_ratio.py — Sanity Ratio (rho) with an empirical permutation null.

rho = S_real / S_rand, where S = mean |SHAP| over (test rows x features) for
a model trained on the true labels (S_real) vs. an identical model retrained
on label-permuted training data (S_rand). Instead of ONE permutation, K
permutations give a null distribution of S_rand, so rho is reported as a
median with a percentile interval and a permutation p-value, and a
null-derived threshold can be compared with the fixed rho_min = 2.0.

Runs on top of a recorded Dataset Lab run: the same CSV, target, dropped
columns, test_size, threshold and random_state are re-used so the model is
the same configuration evaluated in that run. No SMOTE is involved anywhere
(the Lab pipeline does not resample), so the real and permuted pipelines are
symmetric by construction.

    python ml_models/sanity_ratio.py --run-id lab_..._xgboost --k 20
    python ml_models/sanity_ratio.py --dataset-name german_credit --notes-contains "Step A" --k 20
    python ml_models/sanity_ratio.py --list

Results: data/ml_lab/sanity/<run_id>__K<k>.json + data/ml_lab/sanity_index.json
"""
import argparse
import json
import os
import sys
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ml_models.dataset_lab import LAB_DIR, RUNS_DIR, load_dataset, prepare_features  # noqa: E402
from ml_models.trainer import _load_hyperparameters, train_model  # noqa: E402

SANITY_DIR = os.path.join(LAB_DIR, 'sanity')
SANITY_INDEX = os.path.join(LAB_DIR, 'sanity_index.json')
RHO_MIN = 2.0


def _final_estimator(model):
    """(estimator, transform_fn) — unwrap the Lab's sklearn Pipelines so SHAP
    sees the estimator and the features it was actually fitted on."""
    if hasattr(model, 'steps'):
        pre = model[:-1]
        return model.steps[-1][1], (lambda X: pre.transform(X))
    return model, (lambda X: X.values if hasattr(X, 'values') else X)


def shap_matrix(model, model_type, X_bg, X_eval):
    """|SHAP| is taken over an (n_eval x n_features) matrix of positive-class
    attributions. Explainer per model family (recorded in the output):
      xgboost            -> XGBoost native TreeSHAP (pred_contribs, bias column dropped);
                            shap.TreeExplainer cannot parse xgboost>=2.1's base_score.
      random_forest /
      extra_trees        -> shap.TreeExplainer, class-1 slice of the (n, f, 2) output
      gradient_boosting  -> shap.TreeExplainer, (n, f) log-odds output
      logistic_regression-> shap.LinearExplainer on the scaled features, background = training rows
    Units differ across families (probability vs log-odds), which is fine:
    rho is a ratio within one model."""
    import shap
    est, tf = _final_estimator(model)
    Xe = tf(X_eval)
    Xe = np.asarray(Xe, dtype=float)
    if model_type == 'xgboost':
        import xgboost as xgb
        booster = est.get_booster()
        contrib = booster.predict(xgb.DMatrix(Xe, feature_names=list(X_eval.columns)), pred_contribs=True)
        return contrib[:, :-1], 'xgboost pred_contribs (native TreeSHAP, tree_path_dependent)'
    if model_type in ('random_forest', 'extra_trees', 'gradient_boosting'):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            sv = shap.TreeExplainer(est).shap_values(Xe, check_additivity=False)
        if isinstance(sv, list):
            sv = sv[1] if len(sv) == 2 else sv[-1]
        sv = np.asarray(sv)
        if sv.ndim == 3:
            sv = sv[:, :, 1]
        return sv, 'shap.TreeExplainer (tree_path_dependent, no background)'
    if model_type == 'logistic_regression':
        Xb = np.asarray(tf(X_bg), dtype=float)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            sv = shap.LinearExplainer(est, Xb).shap_values(Xe)
        return np.asarray(sv), 'shap.LinearExplainer (background = training rows, scaled space)'
    raise ValueError(f'no SHAP strategy for model_type {model_type}')


def aggregate(sv):
    a = np.abs(sv)
    per_feature = a.mean(axis=0)
    return {
        'mean_abs': float(a.mean()),                      # S as used for rho
        'median_abs': float(np.median(a)),
        'per_sample_mean_abs_mean': float(a.mean(axis=1).mean()),
        'top5_mass_share': float(np.sort(per_feature)[::-1][:5].sum() / max(per_feature.sum(), 1e-12)),
    }, per_feature


def _load_run(run_id):
    p = os.path.join(RUNS_DIR, run_id + '.json')
    if not os.path.isfile(p):
        raise FileNotFoundError(f'no recorded run {run_id}')
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_sanity(run_id, k=20, shap_sample=2000, seed=42):
    run = _load_run(run_id)
    d, s = run['dataset'], run['split']
    csv_path = d['csv_path'] if os.path.isabs(d['csv_path']) else os.path.join(_ROOT, d['csv_path'])
    positive = None
    note = d.get('target_note', '')
    if note.startswith("positive class = '"):
        positive = note.split("'")[1]
    df, y, _ = load_dataset(csv_path, d['target'], positive)
    X, _ = prepare_features(df, d['target'], d.get('dropped_columns') or [])
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=s['test_size'], stratify=y,
                                              random_state=s['random_state'])
    hp = _load_hyperparameters()
    mt = run['model_type']

    rng = np.random.default_rng(seed)
    if len(X_te) > shap_sample:
        idx = np.sort(rng.choice(len(X_te), size=shap_sample, replace=False))
        X_eval, y_eval = X_te.iloc[idx], y_te.iloc[idx]
    else:
        X_eval, y_eval = X_te, y_te

    started = datetime.now()
    real_model = train_model(X_tr, y_tr, hp, model_type=mt)
    auc_real = float(roc_auc_score(y_te, real_model.predict_proba(X_te)[:, 1]))
    sv_real, explainer = shap_matrix(real_model, mt, X_tr, X_eval)
    agg_real, pf_real = aggregate(sv_real)

    null = []
    for i in range(k):
        y_perm = pd.Series(rng.permutation(y_tr.values), index=y_tr.index)
        m_perm = train_model(X_tr, y_perm, hp, model_type=mt)
        auc_perm = float(roc_auc_score(y_te, m_perm.predict_proba(X_te)[:, 1]))
        sv_perm, _ = shap_matrix(m_perm, mt, X_tr, X_eval)
        agg_perm, _ = aggregate(sv_perm)
        null.append({'perm': i, 'auc_test': round(auc_perm, 4), **{k_: round(v, 8) for k_, v in agg_perm.items()}})

    S_real = agg_real['mean_abs']
    S_rand = np.array([r['mean_abs'] for r in null])
    rhos = S_real / S_rand
    p_value = float((1 + np.sum(S_rand >= S_real)) / (k + 1))   # one-sided, +1 correction
    p50, p95, p99 = (float(np.percentile(S_rand, q)) for q in (50, 95, 99))

    # Alternative aggregation (reviewer B4): median |SHAP| instead of mean
    S_real_med = agg_real['median_abs']
    S_rand_med = np.array([r['median_abs'] for r in null])
    rho_med_agg = float(np.median(S_real_med / np.where(S_rand_med > 0, S_rand_med, np.nan))) if np.any(S_rand_med > 0) else None

    rec = {
        'run_id': run_id,
        'dataset': d['name'], 'model_type': mt, 'target': d['target'],
        'dropped_columns': d.get('dropped_columns') or [],
        'k_permutations': k, 'seed': seed,
        'explainer': explainer,
        'shap_eval_rows': int(len(X_eval)), 'test_rows': int(len(X_te)), 'n_features': int(X.shape[1]),
        'auc_real_test': round(auc_real, 4),
        'auc_perm_test_mean': round(float(np.mean([r['auc_test'] for r in null])), 4),
        'S_real_mean_abs': round(S_real, 8),
        'S_rand_mean_abs': {'median': round(p50, 8), 'p95': round(p95, 8), 'p99': round(p99, 8),
                            'min': round(float(S_rand.min()), 8), 'max': round(float(S_rand.max()), 8)},
        'rho_single_definition': 'S_real / S_rand_k for each permutation k',
        'rho_median': round(float(np.median(rhos)), 4),
        'rho_mean': round(float(np.mean(rhos)), 4),
        'rho_ci95': [round(float(np.percentile(rhos, 2.5)), 4), round(float(np.percentile(rhos, 97.5)), 4)],
        'rho_min_over_k': round(float(rhos.min()), 4),
        'rho_max_over_k': round(float(rhos.max()), 4),
        'p_value_one_sided': round(p_value, 4),
        'passes_fixed_2_0': bool(np.median(rhos) >= RHO_MIN),
        'passes_fixed_2_0_all_k': bool(rhos.min() >= RHO_MIN),
        'null_derived': {
            'S_real_over_p95': round(S_real / p95, 4) if p95 > 0 else None,
            'S_real_over_p99': round(S_real / p99, 4) if p99 > 0 else None,
            'threshold_ratio_p95_over_median': round(p95 / p50, 4) if p50 > 0 else None,
            'threshold_ratio_p99_over_median': round(p99 / p50, 4) if p50 > 0 else None,
            'passes_p95': bool(S_real > p95), 'passes_p99': bool(S_real > p99),
        },
        'alt_aggregation_median_abs': {'rho_median': None if rho_med_agg is None else round(rho_med_agg, 4)},
        'real_aggregates': {k_: round(v, 8) for k_, v in agg_real.items()},
        'top_features_real_mean_abs_shap': [
            {'feature': str(X.columns[i]), 'mean_abs_shap': round(float(pf_real[i]), 8)}
            for i in np.argsort(pf_real)[::-1][:15]],
        'null_runs': null,
        'elapsed_seconds': round((datetime.now() - started).total_seconds(), 1),
        'timestamp': started.isoformat(timespec='seconds'),
    }
    _record(rec)
    return rec


def _index_row(rec, fn):
    return {k_: rec[k_] for k_ in ('run_id', 'dataset', 'model_type', 'dropped_columns', 'k_permutations',
                                    'explainer', 'auc_real_test', 'auc_perm_test_mean', 'S_real_mean_abs',
                                    'rho_median', 'rho_ci95', 'p_value_one_sided', 'passes_fixed_2_0',
                                    'timestamp')} | {'S_rand_median': rec['S_rand_mean_abs']['median'],
                                                      'passes_p95': rec['null_derived']['passes_p95'],
                                                      'passes_p99': rec['null_derived']['passes_p99'],
                                                      'file': fn}


def rebuild_index():
    """The index is derived purely from the per-run files, so concurrent jobs
    (each writing its own uniquely named file) can never lose each other's
    rows through a read-modify-write race on the index."""
    os.makedirs(SANITY_DIR, exist_ok=True)
    rows = []
    for fn in sorted(os.listdir(SANITY_DIR)):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(SANITY_DIR, fn), 'r', encoding='utf-8') as f:
                rows.append(_index_row(json.load(f), fn))
        except (OSError, ValueError, KeyError):
            continue      # a file mid-write by another job; picked up on the next rebuild
    rows.sort(key=lambda r: r['timestamp'])
    tmp = SANITY_INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2, default=str)
    os.replace(tmp, SANITY_INDEX)
    return rows


def _record(rec):
    os.makedirs(SANITY_DIR, exist_ok=True)
    fn = f"{rec['run_id']}__K{rec['k_permutations']}.json"
    tmp = os.path.join(SANITY_DIR, fn + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=2, default=str)
    os.replace(tmp, os.path.join(SANITY_DIR, fn))
    rebuild_index()


def list_sanity():
    return rebuild_index()


def _select_runs(dataset_name, notes_contains, models):
    from ml_models.dataset_lab import list_runs
    latest = {}
    for r in sorted(list_runs(), key=lambda r: r['timestamp']):
        if dataset_name and r['dataset'] != dataset_name:
            continue
        if notes_contains and notes_contains not in (r.get('notes') or ''):
            continue
        if models and r['model_type'] not in models:
            continue
        latest[r['model_type']] = r['run_id']      # latest per model type
    return list(latest.values())


def _print(rec):
    nd = rec['null_derived']
    print(f"\n{rec['run_id']}  [{rec['model_type']}]  K={rec['k_permutations']}  explainer: {rec['explainer']}")
    print(f"  AUC real {rec['auc_real_test']}  | permuted-label models mean AUC {rec['auc_perm_test_mean']} (should be ~0.5)")
    print(f"  S_real {rec['S_real_mean_abs']:.6f} | S_rand median {rec['S_rand_mean_abs']['median']:.6f} "
          f"(p95 {rec['S_rand_mean_abs']['p95']:.6f}, p99 {rec['S_rand_mean_abs']['p99']:.6f})")
    print(f"  rho median {rec['rho_median']}  95% [{rec['rho_ci95'][0]}, {rec['rho_ci95'][1]}]  "
          f"min {rec['rho_min_over_k']} max {rec['rho_max_over_k']}  p={rec['p_value_one_sided']}")
    print(f"  fixed 2.0: {'PASS' if rec['passes_fixed_2_0'] else 'FAIL'} (all K: {rec['passes_fixed_2_0_all_k']})  "
          f"| null-derived: S_real/p95={nd['S_real_over_p95']} ({'PASS' if nd['passes_p95'] else 'FAIL'}), "
          f"S_real/p99={nd['S_real_over_p99']} ({'PASS' if nd['passes_p99'] else 'FAIL'})  "
          f"| equivalent rho threshold p95/median={nd['threshold_ratio_p95_over_median']}, p99/median={nd['threshold_ratio_p99_over_median']}")
    print(f"  alt aggregation (median |SHAP|) rho={rec['alt_aggregation_median_abs']['rho_median']}  | {rec['elapsed_seconds']}s")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--run-id', nargs='*', default=[])
    p.add_argument('--dataset-name')
    p.add_argument('--notes-contains')
    p.add_argument('--models', nargs='*')
    p.add_argument('--k', type=int, default=20)
    p.add_argument('--shap-sample', type=int, default=2000, help='max test rows used for SHAP (seeded subsample)')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--list', action='store_true')
    a = p.parse_args(argv)
    if a.list:
        for r in list_sanity():
            print(f"{r['run_id']:<62} K={r['k_permutations']:<4} rho={r['rho_median']:<8} ci={r['rho_ci95']}  p={r['p_value_one_sided']}  "
                  f"2.0:{'PASS' if r['passes_fixed_2_0'] else 'FAIL'} p95:{'PASS' if r['passes_p95'] else 'FAIL'}")
        return 0
    run_ids = a.run_id or _select_runs(a.dataset_name, a.notes_contains, a.models)
    if not run_ids:
        p.error('no runs selected (use --run-id or --dataset-name [--notes-contains] [--models])')
    for rid in run_ids:
        _print(compute_sanity(rid, k=a.k, shap_sample=a.shap_sample, seed=a.seed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
