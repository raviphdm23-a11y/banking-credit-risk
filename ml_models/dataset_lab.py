"""
dataset_lab.py — generic binary-classification benchmark harness.

Reuses the platform's model builders, evaluation and cross-validation
(trainer.train_model / evaluate_model / cross_validate_model) against ANY
tabular CSV with a binary target — banking or not — without onboarding the
dataset as a bank. Nothing here touches bank.db, bank_loan_metrics,
active_model.json or the governance tables: results are recorded
separately under data/ml_lab/.

    python ml_models/dataset_lab.py --csv data/ml_lab/datasets/x.csv --target y --positive yes
    python ml_models/dataset_lab.py --csv ... --target y --positive yes --model random_forest --drop duration
    python ml_models/dataset_lab.py --csv ... --target y --positive yes --all-models
    python ml_models/dataset_lab.py --list

Each run writes data/ml_lab/runs/<run_id>.json and appends a summary row
to data/ml_lab/index.json.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ml_models.trainer import (  # noqa: E402
    MODEL_BUILDERS, _get_feature_importance, _load_hyperparameters,
    compute_epv, cross_validate_model, evaluate_model, train_model,
)
from ml_models import feature_screening as _screen  # noqa: E402
from ml_models import tuning as _tuning  # noqa: E402

LAB_DIR = os.path.join(_ROOT, 'data', 'ml_lab')
RUNS_DIR = os.path.join(LAB_DIR, 'runs')
INDEX_PATH = os.path.join(LAB_DIR, 'index.json')

_TRUTHY = {'yes', 'y', 'true', 't', '1', 'positive', 'pos'}
_FALSY = {'no', 'n', 'false', 'f', '0', 'negative', 'neg'}


def _sniff_sep(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        head = f.readline()
    return max([',', ';', '\t', '|'], key=head.count)


def load_dataset(csv_path, target, positive_label=None, sep=None):
    """Read a CSV and return (df, y, target_note) with y as a 0/1 int Series."""
    sep = sep or _sniff_sep(csv_path)
    df = pd.read_csv(csv_path, sep=sep, encoding='utf-8-sig')  # -sig strips a BOM from the first header
    if target not in df.columns:
        raise ValueError(f"target column '{target}' not in CSV columns: {list(df.columns)}")

    raw = df[target]
    uniques = pd.unique(raw.dropna())
    if len(uniques) != 2:
        raise ValueError(f"target '{target}' has {len(uniques)} distinct values; need exactly 2 "
                         f"for binary classification (found: {list(uniques)[:10]})")

    if positive_label is not None:
        pos = positive_label
        matches = raw.astype(str).str.strip().str.lower() == str(pos).strip().lower()
        if not matches.any():
            raise ValueError(f"positive label '{pos}' never occurs in '{target}' (values: {list(uniques)})")
        y = matches.astype(int)
        note = f"positive class = '{pos}'"
    else:
        lowered = {str(u).strip().lower(): u for u in uniques}
        truthy = [v for k, v in lowered.items() if k in _TRUTHY]
        if len(truthy) == 1:
            pos = truthy[0]
            y = (raw == pos).astype(int)
            note = f"positive class auto-detected as '{pos}'"
        else:
            counts = raw.value_counts()
            pos = counts.idxmin()
            y = (raw == pos).astype(int)
            note = (f"positive class defaulted to the MINORITY value '{pos}' "
                    f"({int(counts.min())} of {int(counts.sum())} rows) — pass --positive to override")
    return df, y, note


def prepare_features(df, target, drop_columns=None):
    """Numeric columns pass through (coerced); string/categorical columns are
    one-hot encoded; booleans become 0/1. Returns (X, encoding_info)."""
    drop_columns = list(drop_columns or [])
    missing = [c for c in drop_columns if c not in df.columns]
    if missing:
        raise ValueError(f"--drop columns not in CSV: {missing}")
    feats = df.drop(columns=[target] + drop_columns)

    bool_cols = [c for c in feats.columns if feats[c].dtype == bool]
    for c in bool_cols:
        feats[c] = feats[c].astype(int)

    cat_cols = [c for c in feats.columns if feats[c].dtype == object]
    num_cols = [c for c in feats.columns if c not in cat_cols]
    for c in num_cols:
        feats[c] = pd.to_numeric(feats[c], errors='coerce')

    X = pd.get_dummies(feats, columns=cat_cols, dtype=float) if cat_cols else feats.astype(float)
    # XGBoost rejects feature names containing [, ] or <
    X.columns = [re.sub(r'[\[\]<]', '_', str(c)) for c in X.columns]

    info = {
        'n_raw_features': int(feats.shape[1]),
        'n_encoded_features': int(X.shape[1]),
        'numeric_columns': num_cols,
        'categorical_columns': cat_cols,
        'dropped_columns': drop_columns,
        'rows_with_any_missing': int(X.isna().any(axis=1).sum()),
    }
    return X, info


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')[:40]


def run_experiment(csv_path, target, positive_label=None, model_type='xgboost',
                   dataset_name=None, drop_columns=None, test_size=0.2,
                   threshold=0.5, n_splits=5, notes=None, sep=None, record=True,
                   iv_boruta=False, iv_min=_screen.IV_MIN_DEFAULT, boruta_perc=_screen.BORUTA_PERC_DEFAULT,
                   include_tentative=True, resample=None, tune=False, tune_iter=20, tune_folds=5,
                   random_state=42):
    """
    iv_boruta   - run the Phase-1 IV + Boruta dual gate (feature_screening.py) on the RAW
                  columns (after `drop_columns` is removed but before one-hot encoding /
                  the train-test split), keeping only Confirmed (+ Tentative if
                  include_tentative) columns for modelling.
    resample    - None (default) or 'smote': SMOTE applied to the TRAINING FOLD ONLY, after
                  the split, on the already-encoded numeric matrix - never to the test fold
                  and never before splitting (this is the ordering the TAI paper's reviewers
                  flagged as missing; see paper analysis/draft one/RESULTS_LOG.md Step "SMOTE").
    tune        - RandomizedSearchCV (tuning.py) in place of the fixed-default estimator,
                  scored by AUC over `tune_folds` StratifiedKFold, `tune_iter` candidates.
    """
    if model_type not in MODEL_BUILDERS:
        raise ValueError(f"unknown model_type '{model_type}'; choose from {list(MODEL_BUILDERS)}")

    dataset_name = dataset_name or os.path.splitext(os.path.basename(csv_path))[0]
    df, y, target_note = load_dataset(csv_path, target, positive_label, sep=sep)

    drop_columns = list(drop_columns or [])
    screening_report = None
    if iv_boruta:
        df_for_screen = df.drop(columns=[c for c in drop_columns if c in df.columns])
        screening_report = _screen.screen(df_for_screen, target, iv_min=iv_min, boruta_perc=boruta_perc,
                                          random_state=random_state, include_tentative=include_tentative)
        retained = set(screening_report['retained_columns'])
        drop_columns = list(set(drop_columns) | {c for c in df.columns if c != target and c not in retained})

    X, enc = prepare_features(df, target, drop_columns)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state)

    resample_report = None
    if resample not in (None, 'none', 'smote'):
        raise ValueError(f"unknown resample '{resample}'; choose from None, 'smote'")

    hp = _load_hyperparameters()
    started = datetime.now()
    tune_report = None
    if tune:
        # SMOTE + tuning together: X_tr/y_tr are passed RAW (not pre-resampled) to
        # tune_and_fit, which re-fits SMOTE inside every inner CV fold via an
        # imblearn Pipeline. Pre-resampling here and then handing the search a
        # single already-balanced training set would leak a synthetic point's
        # real "parent" row across the search's own train/validation folds -
        # the exact mechanism the TAI paper's reviewers flagged, just relocated
        # into the tuning step. See ml_models/tuning.py's module docstring.
        n_before = {int(k): int(v) for k, v in y_tr.value_counts().items()} if resample == 'smote' else None
        model, tune_report = _tuning.tune_and_fit(model_type, X_tr, y_tr, n_iter=tune_iter,
                                                  cv_folds=tune_folds, random_state=random_state,
                                                  resample=resample)
        if resample == 'smote':
            resample_report = {'method': 'smote', 'applied_to': 'inside_every_tuning_cv_fold_and_final_refit',
                               'class_counts_before_final_refit': n_before,
                               'note': 'resampling happens once per inner CV fold during search, and once '
                                       'more on the full training fold for the final refit - no single '
                                       'before/after count applies; see tuning.resample_inside_cv'}
    elif resample == 'smote':
        from imblearn.over_sampling import SMOTE
        n_min = int(y_tr.value_counts().min())
        k_neighbors = min(5, max(1, n_min - 1))
        n_before = {int(k): int(v) for k, v in y_tr.value_counts().items()}
        X_tr, y_tr = SMOTE(random_state=random_state, k_neighbors=k_neighbors).fit_resample(X_tr, y_tr)
        n_after = {int(k): int(v) for k, v in y_tr.value_counts().items()}
        resample_report = {'method': 'smote', 'applied_to': 'training_fold_only_after_split',
                           'k_neighbors': k_neighbors, 'class_counts_before': n_before,
                           'class_counts_after': n_after}
        model = train_model(X_tr, y_tr, hp, model_type=model_type)
    else:
        model = train_model(X_tr, y_tr, hp, model_type=model_type)
    metrics, cm, _ = evaluate_model(model, X_te, y_te, X_te, threshold)
    # Cross-validation is run on the ORIGINAL (X, y) - i.e. without resampling and without the
    # tuned hyperparameters - so it remains a fixed, comparable generalisation check across every
    # run regardless of `resample`/`tune`, not a re-tuned or re-resampled number itself.
    cv = cross_validate_model(X, y, hp, model_type, n_splits=n_splits)
    elapsed = (datetime.now() - started).total_seconds()

    # evaluate_model speaks "default" because it was written for PD models —
    # translate to neutral names for a generic harness.
    metrics = dict(metrics)
    metrics['n_positive'] = metrics.pop('n_defaults')
    metrics['positive_rate'] = metrics.pop('default_rate')

    imp = np.asarray(_get_feature_importance(model, n_features=X.shape[1]), dtype=float)
    order = np.argsort(imp)[::-1][:15]
    top_features = [{'feature': str(X.columns[i]), 'importance': round(float(imp[i]), 6)}
                    for i in order]

    n_pos_train = int(y_tr.sum() if hasattr(y_tr, 'sum') else np.sum(y_tr))
    tag = ('_iv-boruta' if iv_boruta else '') + (f'_{resample}' if resample and resample != 'none' else '') + ('_tuned' if tune else '')
    run_id = f"lab_{started.strftime('%Y%m%d_%H%M%S')}_{_slug(dataset_name)}_{model_type}{tag}"
    record_obj = {
        'run_id': run_id,
        'timestamp': started.isoformat(timespec='seconds'),
        'dataset': {
            'name': dataset_name,
            'csv_path': os.path.relpath(csv_path, _ROOT) if os.path.isabs(csv_path) else csv_path,
            'n_rows': int(len(df)),
            'target': target,
            'target_note': target_note,
            'positive_rate_overall': round(float(y.mean()), 4),
            **enc,
        },
        'model_type': model_type,
        'hyperparameters': tune_report['best_params'] if tune_report else hp.get('models', {}).get(model_type, {}),
        'pipeline_options': {
            'iv_boruta': iv_boruta, 'resample': resample or 'none', 'tuned': tune,
        },
        'screening': screening_report,
        'resampling': resample_report,
        'tuning': tune_report,
        'split': {'test_size': test_size, 'n_train': int(len(y_tr)), 'n_test': int(len(y_te)),
                  'threshold': threshold, 'stratified': True, 'random_state': random_state},
        'metrics': metrics,
        'confusion_matrix': cm,
        'cross_validation': cv,
        'epv': compute_epv(n_pos_train, X.shape[1]),
        'top_features': top_features,
        'train_seconds': round(elapsed, 1),
        'notes': notes,
    }
    if record:
        _record(record_obj)
    return record_obj


def _record(rec):
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(os.path.join(RUNS_DIR, rec['run_id'] + '.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=2, default=str)
    index = list_runs()
    m, cv = rec['metrics'], rec['cross_validation']
    index.append({
        'run_id': rec['run_id'], 'timestamp': rec['timestamp'],
        'dataset': rec['dataset']['name'], 'target': rec['dataset']['target'],
        'n_rows': rec['dataset']['n_rows'], 'n_features': rec['dataset']['n_encoded_features'],
        'dropped_columns': rec['dataset']['dropped_columns'],
        'positive_rate': rec['dataset']['positive_rate_overall'],
        'model_type': rec['model_type'],
        'pipeline_options': rec.get('pipeline_options', {'iv_boruta': False, 'resample': 'none', 'tuned': False}),
        'auc_roc': m['auc_roc'], 'pr_auc': m['pr_auc'], 'f1': m['f1'],
        'precision': m['precision'], 'recall': m['recall'], 'brier_score': m['brier_score'],
        'cv_auc_mean': cv.get('mean_auc'), 'cv_auc_std': cv.get('std_auc'),
        'notes': rec['notes'],
    })
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, default=str)


def list_runs():
    if not os.path.exists(INDEX_PATH):
        return []
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def delete_run(run_id):
    """Delete one recorded run: its JSON file under RUNS_DIR and its entry in
    index.json. `run_id` must be an exact run_id as returned by list_runs() -
    the caller (app.py) is responsible for filename-safety validation before
    calling this. Returns True if a run was found and removed, False if
    run_id wasn't present in either place (not an error - caller decides how
    to report)."""
    run_path = os.path.join(RUNS_DIR, run_id + '.json')
    found = os.path.isfile(run_path)
    if found:
        os.remove(run_path)
    index = list_runs()
    new_index = [r for r in index if r.get('run_id') != run_id]
    if len(new_index) != len(index):
        found = True
        with open(INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(new_index, f, indent=2, default=str)
    return found


def _print_summary(rec):
    m, cv = rec['metrics'], rec['cross_validation']
    d = rec['dataset']
    print(f"\n{rec['run_id']}")
    print(f"  dataset  : {d['name']}  rows={d['n_rows']:,}  features={d['n_raw_features']}"
          f" -> {d['n_encoded_features']} encoded  positive rate={d['positive_rate_overall']:.1%}")
    print(f"  target   : {d['target']}  ({d['target_note']})")
    if d['dropped_columns']:
        print(f"  dropped  : {d['dropped_columns']}")
    opts = rec.get('pipeline_options', {})
    opt_str = ', '.join(k for k in ('iv_boruta', 'tuned') if opts.get(k)) or 'none'
    if opts.get('resample', 'none') != 'none':
        opt_str += f", resample={opts['resample']}"
    print(f"  model    : {rec['model_type']}  ({rec['train_seconds']}s)  options: {opt_str}")
    if rec.get('screening'):
        s = rec['screening']; b = s['boruta']
        print(f"  Phase 1  : IV>= {s['iv_min']} dropped {len(s['iv_dropped'])}/{s['n_raw_total']} raw cols; "
              f"Boruta(perc={b['perc']}) confirmed {len(b['confirmed'])}, "
              f"tentative {len(b['tentative'])} ({'included' if s['include_tentative'] else 'excluded'}), "
              f"rejected {len(b['rejected'])} -> retained {s['n_retained']}/{s['n_raw_total']}")
    if rec.get('resampling'):
        r = rec['resampling']
        if 'class_counts_after' in r:
            print(f"  SMOTE    : train class counts {r['class_counts_before']} -> {r['class_counts_after']} "
                  f"(k_neighbors={r['k_neighbors']}, {r['applied_to']})")
        else:
            print(f"  SMOTE    : {r['applied_to']} (pre-refit train class counts {r['class_counts_before_final_refit']})")
    if rec.get('tuning'):
        t = rec['tuning']
        print(f"  Tuning   : {t['n_iter_effective']}/{t['n_candidates_full_grid']} candidates, "
              f"{t['cv_folds']}-fold CV AUC={t['best_cv_auc']}, best_params={t['best_params']}")
    print(f"  holdout  : AUC-ROC {m['auc_roc']}  PR-AUC {m['pr_auc']}  F1 {m['f1']}  "
          f"precision {m['precision']}  recall {m['recall']}  Brier {m['brier_score']}")
    print(f"  {cv['n_splits']}-fold CV: AUC {cv['mean_auc']} ± {cv['std_auc']}")
    print(f"  EPV      : {rec['epv']}")
    print("  top features:")
    for t in rec['top_features'][:8]:
        print(f"    {t['feature']:<40} {t['importance']:.4f}")


def main(argv=None):
    # Windows consoles default to cp1252; feature names from real datasets can
    # carry characters outside it (e.g. German Credit's "≥ 7 years"), which
    # would otherwise abort the whole --all-models batch mid-way with a
    # UnicodeEncodeError from a mere print.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--csv')
    p.add_argument('--target')
    p.add_argument('--positive', help="value of --target treated as the positive class (e.g. yes)")
    p.add_argument('--model', default='xgboost', choices=sorted(MODEL_BUILDERS))
    p.add_argument('--all-models', action='store_true', help='run every model type in turn')
    p.add_argument('--name', help='dataset label for the record (default: CSV filename)')
    p.add_argument('--drop', nargs='*', default=[], help='columns to exclude (e.g. leakage columns)')
    p.add_argument('--sep', help='CSV separator (auto-detected if omitted)')
    p.add_argument('--test-size', type=float, default=0.2)
    p.add_argument('--threshold', type=float, default=0.5)
    p.add_argument('--folds', type=int, default=5)
    p.add_argument('--notes')
    p.add_argument('--iv-boruta', action='store_true',
                   help='Phase-1 IV + Boruta dual-gate feature screening (feature_screening.py) before modelling')
    p.add_argument('--iv-min', type=float, default=_screen.IV_MIN_DEFAULT)
    p.add_argument('--boruta-perc', type=int, default=_screen.BORUTA_PERC_DEFAULT)
    p.add_argument('--exclude-tentative', action='store_true',
                   help='keep only Boruta-Confirmed columns (default keeps Confirmed + Tentative)')
    p.add_argument('--resample', choices=['none', 'smote'], default='none',
                   help="'smote': SMOTE on the TRAINING FOLD ONLY, after the split (never on the test fold)")
    p.add_argument('--tune', action='store_true',
                   help='RandomizedSearchCV (tuning.py) instead of fixed-default hyperparameters')
    p.add_argument('--tune-iter', type=int, default=20)
    p.add_argument('--tune-folds', type=int, default=5)
    p.add_argument('--random-state', type=int, default=42)
    p.add_argument('--list', action='store_true', help='print recorded runs and exit')
    a = p.parse_args(argv)

    if a.list:
        runs = list_runs()
        if not runs:
            print('no recorded runs yet')
            return 0
        print(f"{'run_id':<58} {'model':<20} {'options':<28} {'AUC':>6} {'PR-AUC':>7} {'F1':>6} {'CV AUC':>14}")
        for r in runs:
            cvs = f"{r['cv_auc_mean']} ± {r['cv_auc_std']}" if r['cv_auc_mean'] is not None else '—'
            po = r.get('pipeline_options', {})
            opt = ','.join(k for k in ('iv_boruta', 'tuned') if po.get(k))
            if po.get('resample', 'none') != 'none':
                opt = (opt + ',' if opt else '') + po['resample']
            print(f"{r['run_id']:<58} {r['model_type']:<20} {(opt or '-'):<28} {r['auc_roc']:>6} {str(r['pr_auc']):>7} "
                  f"{r['f1']:>6} {cvs:>14}")
        return 0

    if not a.csv or not a.target:
        p.error('--csv and --target are required (or use --list)')

    models = sorted(MODEL_BUILDERS) if a.all_models else [a.model]
    for mt in models:
        rec = run_experiment(a.csv, a.target, a.positive, model_type=mt, dataset_name=a.name,
                             drop_columns=a.drop, test_size=a.test_size, threshold=a.threshold,
                             n_splits=a.folds, notes=a.notes, sep=a.sep,
                             iv_boruta=a.iv_boruta, iv_min=a.iv_min, boruta_perc=a.boruta_perc,
                             include_tentative=not a.exclude_tentative,
                             resample=a.resample, tune=a.tune, tune_iter=a.tune_iter,
                             tune_folds=a.tune_folds, random_state=a.random_state)
        _print_summary(rec)
    return 0


if __name__ == '__main__':
    sys.exit(main())
