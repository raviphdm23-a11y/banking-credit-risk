"""
ML Training Engine for PD (Probability of Default) Model
Orchestrates data ingestion, validation, training, evaluation, and model promotion.
"""

import os
import json
import shutil
import time
import traceback
import io
import base64
import glob
import threading
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.cm as cm

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    roc_auc_score, accuracy_score, precision_score,
    recall_score, f1_score, confusion_matrix
)
import joblib

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAINING_DIR  = os.path.join(_ROOT, 'data', 'training')
ARCHIVE_DIR   = os.path.join(_ROOT, 'data', 'archive')
RUNS_DIR      = os.path.join(_ROOT, 'data', 'runs')
ML_DIR        = os.path.join(_ROOT, 'ml_models')

MODEL_PATH    = os.path.join(ML_DIR, 'pd_model.pkl')
BACKUP_PATH   = os.path.join(ML_DIR, 'pd_model_backup.pkl')
META_PATH     = os.path.join(ML_DIR, 'pd_model_metadata.json')
HISTORY_PATH  = os.path.join(ML_DIR, 'run_history.json')
HPARAM_PATH   = os.path.join(ML_DIR, 'hyperparameters.json')

REQUIRED_COLUMNS = {
    'bank_id', 'loan_id', 'de_ratio', 'interest_coverage',
    'profitability', 'liquidity_ratio', 'default_flag', 'pd_observed', 'observation_date'
}
FEATURE_COLS  = ['de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio']
TARGET_COL    = 'pd_observed'

# Lock to prevent concurrent training runs
_training_lock = threading.Lock()
_training_running = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_hyperparameters():
    with open(HPARAM_PATH, 'r') as f:
        return json.load(f)


def _load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, 'r') as f:
        return json.load(f)


def _save_history(history):
    with open(HISTORY_PATH, 'w') as f:
        json.dump(history, f, indent=2, default=str)


def _fig_to_base64(fig):
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64


def is_training_running():
    return _training_running


# ── Step 1: Scan ──────────────────────────────────────────────────────────────

def scan_training_folder():
    """Return list of CSV file info dicts from data/training/."""
    os.makedirs(TRAINING_DIR, exist_ok=True)
    files = []
    for path in glob.glob(os.path.join(TRAINING_DIR, '*.csv')):
        stat = os.stat(path)
        try:
            df = pd.read_csv(path, nrows=1)
            row_count = sum(1 for _ in open(path)) - 1
        except Exception:
            row_count = -1
        files.append({
            'filename':  os.path.basename(path),
            'filepath':  path,
            'size_kb':   round(stat.st_size / 1024, 1),
            'modified':  datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            'row_count': row_count,
        })
    return sorted(files, key=lambda x: x['filename'])


# ── Step 2: Validate ──────────────────────────────────────────────────────────

def validate_file(filepath):
    """
    Validate a single CSV file.
    Returns (ok: bool, error_message: str | None, row_count: int).
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return False, f"Cannot read CSV: {e}", 0

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return False, f"Missing columns: {sorted(missing)}", 0

    if df.isnull().any().any():
        null_cols = df.columns[df.isnull().any()].tolist()
        return False, f"Null values in columns: {null_cols}", len(df)

    if not df['default_flag'].isin([0, 1]).all():
        return False, "default_flag must be 0 or 1 only", len(df)

    if not ((df['pd_observed'] >= 0.0001) & (df['pd_observed'] <= 1.0)).all():
        return False, "pd_observed values must be between 0.0001 and 1.0", len(df)

    for col, lo, hi in [
        ('de_ratio',          0.0, 10.0),
        ('interest_coverage', 0.0, 20.0),
        ('profitability',   -50.0, 100.0),
        ('liquidity_ratio',   0.1,  5.0),
    ]:
        if not ((df[col] >= lo) & (df[col] <= hi)).all():
            return False, f"{col} has values outside valid range [{lo}, {hi}]", len(df)

    if len(df) < 50:
        return False, f"Too few rows ({len(df)}); minimum 50 required", len(df)

    return True, None, len(df)


# ── Step 3: Load & merge ──────────────────────────────────────────────────────

def load_and_merge():
    """
    Load all valid CSVs from data/training/, merge, deduplicate.
    Returns (DataFrame, files_used, files_skipped).
    """
    files       = scan_training_folder()
    frames      = []
    files_used  = []
    files_skip  = []

    for f in files:
        ok, err, rows = validate_file(f['filepath'])
        if ok:
            df = pd.read_csv(f['filepath'])
            frames.append(df)
            files_used.append({'filename': f['filename'], 'rows': rows})
        else:
            files_skip.append({'filename': f['filename'], 'reason': err})

    if not frames:
        raise ValueError("No valid training files found in data/training/")

    merged = pd.concat(frames, ignore_index=True)

    # Deduplicate on loan_id (keep first occurrence)
    before = len(merged)
    merged = merged.drop_duplicates(subset='loan_id', keep='first')
    dupes  = before - len(merged)

    if len(merged) < 50:
        raise ValueError(f"Only {len(merged)} rows after deduplication; minimum 50 required")

    return merged, files_used, files_skip, dupes


# ── Step 4: Train ─────────────────────────────────────────────────────────────

def train_model(X_train, y_train, hp):
    """Fit RandomForestRegressor with given hyperparameters."""
    model_hp = hp.get('model', {})
    model = RandomForestRegressor(
        n_estimators     = int(model_hp.get('n_estimators', 100)),
        max_depth        = model_hp.get('max_depth') or None,
        min_samples_split= int(model_hp.get('min_samples_split', 2)),
        min_samples_leaf = int(model_hp.get('min_samples_leaf', 1)),
        max_features     = model_hp.get('max_features', 'sqrt'),
        bootstrap        = bool(model_hp.get('bootstrap', True)),
        random_state     = int(model_hp.get('random_state', 42)),
        n_jobs           = -1,
    )
    model.fit(X_train, y_train)
    return model


# ── Step 5: Evaluate ──────────────────────────────────────────────────────────

def evaluate_model(model, X_test, y_test, df_test, threshold):
    """
    Compute regression + classification metrics.
    Classification threshold converts continuous PD to default/no-default.
    """
    y_pred   = model.predict(X_test)
    y_pred   = np.clip(y_pred, 0.0001, 1.0)

    # Regression metrics
    r2   = float(r2_score(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae  = float(mean_absolute_error(y_test, y_pred))

    # Classification metrics
    y_true_bin = df_test['default_flag'].values
    y_pred_bin = (y_pred >= threshold).astype(int)

    auc   = float(roc_auc_score(y_true_bin, y_pred))
    acc   = float(accuracy_score(y_true_bin, y_pred_bin))
    prec  = float(precision_score(y_true_bin, y_pred_bin, zero_division=0))
    rec   = float(recall_score(y_true_bin, y_pred_bin, zero_division=0))
    f1    = float(f1_score(y_true_bin, y_pred_bin, zero_division=0))
    cm    = confusion_matrix(y_true_bin, y_pred_bin).tolist()

    metrics = {
        'r2': round(r2, 4), 'rmse': round(rmse, 6), 'mae': round(mae, 6),
        'auc_roc': round(auc, 4), 'accuracy': round(acc, 4),
        'precision': round(prec, 4), 'recall': round(rec, 4), 'f1': round(f1, 4),
    }
    return metrics, cm, y_pred


# ── Step 6: Charts ────────────────────────────────────────────────────────────

def generate_charts(model, X_test, y_test, y_pred, df_test, threshold):
    """Generate 6 evaluation charts, return dict of base64 PNG strings."""
    charts = {}
    y_true_bin = df_test['default_flag'].values
    plt.style.use('seaborn-v0_8-whitegrid')

    # 1. Feature Importance
    fig, ax = plt.subplots(figsize=(7, 4))
    importances = model.feature_importances_
    idx = np.argsort(importances)
    ax.barh([FEATURE_COLS[i] for i in idx], importances[idx], color='#2196F3')
    ax.set_title('Feature Importance', fontsize=13, fontweight='bold')
    ax.set_xlabel('Importance Score')
    ax.tick_params(axis='y', labelsize=10)
    charts['feature_importance'] = _fig_to_base64(fig)

    # 2. ROC Curve
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true_bin, y_pred)
    auc_val = roc_auc_score(y_true_bin, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, color='#2196F3', lw=2, label=f'AUC = {auc_val:.3f}')
    ax.plot([0, 1], [0, 1], 'k--', lw=1)
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title('ROC Curve', fontsize=13, fontweight='bold')
    ax.legend(loc='lower right')
    charts['roc_curve'] = _fig_to_base64(fig)

    # 3. Confusion Matrix
    cm = confusion_matrix(y_true_bin, (y_pred >= threshold).astype(int))
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.colorbar(im, ax=ax)
    labels = ['No Default', 'Default']
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel('Predicted'); ax.set_ylabel('Actual')
    ax.set_title(f'Confusion Matrix (threshold={threshold})', fontsize=12, fontweight='bold')
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                    color='white' if cm[i, j] > cm.max() / 2 else 'black', fontsize=14)
    charts['confusion_matrix'] = _fig_to_base64(fig)

    # 4. PD Distribution
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(y_pred,        bins=40, alpha=0.6, color='#2196F3', label='Predicted PD')
    ax.hist(y_test.values, bins=40, alpha=0.6, color='#FF5722', label='Actual PD')
    ax.set_xlabel('PD Value')
    ax.set_ylabel('Count')
    ax.set_title('PD Distribution — Predicted vs Actual', fontsize=13, fontweight='bold')
    ax.legend()
    charts['pd_distribution'] = _fig_to_base64(fig)

    # 5. Actual vs Predicted Scatter
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(y_test, y_pred, alpha=0.3, s=10, color='#2196F3')
    mn, mx = min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())
    ax.plot([mn, mx], [mn, mx], 'r--', lw=1.5, label='Perfect fit')
    ax.set_xlabel('Actual PD')
    ax.set_ylabel('Predicted PD')
    ax.set_title('Actual vs Predicted PD', fontsize=13, fontweight='bold')
    ax.legend()
    charts['actual_vs_predicted'] = _fig_to_base64(fig)

    # 6. Residual Distribution
    residuals = y_pred - y_test.values
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(residuals, bins=40, color='#9C27B0', alpha=0.75)
    ax.axvline(0, color='red', linestyle='--', lw=1.5)
    ax.set_xlabel('Residual (Predicted − Actual)')
    ax.set_ylabel('Count')
    ax.set_title('Residual Distribution', fontsize=13, fontweight='bold')
    charts['residual_distribution'] = _fig_to_base64(fig)

    return charts


# ── Step 7: Archive ───────────────────────────────────────────────────────────

def archive_training_files(files_used, run_id):
    """Move processed CSVs to data/archive/{run_id}/."""
    run_archive = os.path.join(ARCHIVE_DIR, run_id)
    os.makedirs(run_archive, exist_ok=True)
    for f in files_used:
        src = os.path.join(TRAINING_DIR, f['filename'])
        dst = os.path.join(run_archive, f['filename'])
        if os.path.exists(src):
            shutil.move(src, dst)


# ── Main training orchestrator ────────────────────────────────────────────────

def run_training(triggered_by='manual'):
    """
    Full training pipeline.
    Returns a run record dict (same structure as stored in run_history.json).
    Raises RuntimeError if another run is already in progress.
    """
    global _training_running

    if not _training_lock.acquire(blocking=False):
        raise RuntimeError("A training run is already in progress.")

    _training_running = True
    run_id    = 'run_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    started   = time.time()
    timestamp = datetime.now().isoformat(timespec='seconds')

    record = {
        'run_id':        run_id,
        'timestamp':     timestamp,
        'triggered_by':  triggered_by,
        'status':        'failed',
        'files_used':    [],
        'files_skipped': [],
        'total_rows':    0,
        'train_rows':    0,
        'test_rows':     0,
        'metrics':       {},
        'confusion_matrix': [],
        'model_promoted':   False,
        'duration_seconds': 0,
        'error':         None,
    }

    try:
        hp        = _load_hyperparameters()
        threshold = float(hp['training'].get('pd_classification_threshold', 0.05))
        test_size = float(hp['training'].get('test_size', 0.20))
        min_improv= float(hp['training'].get('min_r2_improvement', 0.01))

        # Load data
        merged, files_used, files_skip, dupes = load_and_merge()
        record['files_used']    = files_used
        record['files_skipped'] = files_skip
        record['total_rows']    = len(merged)

        # Split
        X = merged[FEATURE_COLS]
        y = merged[TARGET_COL]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size,
            random_state=hp['model'].get('random_state', 42)
        )
        df_test = merged.loc[X_test.index]
        record['train_rows'] = len(X_train)
        record['test_rows']  = len(X_test)

        # Train
        model = train_model(X_train, y_train, hp)

        # Evaluate
        metrics, cm, y_pred = evaluate_model(model, X_test, y_test, df_test, threshold)
        record['metrics']          = metrics
        record['confusion_matrix'] = cm

        # Generate charts and save to data/runs/{run_id}/
        charts = generate_charts(model, X_test, y_test, y_pred, df_test, threshold)
        run_charts_dir = os.path.join(RUNS_DIR, run_id)
        os.makedirs(run_charts_dir, exist_ok=True)
        for name, b64 in charts.items():
            with open(os.path.join(run_charts_dir, f'{name}.b64'), 'w') as f:
                f.write(b64)

        # Model promotion: replace only if new model is better
        current_r2 = -999.0
        if os.path.exists(META_PATH):
            with open(META_PATH, 'r') as f:
                meta = json.load(f)
            current_r2 = meta.get('metrics', {}).get('r2', -999.0)

        if metrics['r2'] >= current_r2 + min_improv or current_r2 == -999.0:
            if os.path.exists(MODEL_PATH):
                shutil.copy2(MODEL_PATH, BACKUP_PATH)
            joblib.dump(model, MODEL_PATH)
            new_meta = {
                'model_type':   'RandomForestRegressor',
                'version':      run_id,
                'date_trained': timestamp,
                'triggered_by': triggered_by,
                'features':     FEATURE_COLS,
                'target':       TARGET_COL,
                'metrics':      metrics,
                'hyperparameters': hp['model'],
                'rows_trained': len(X_train),
                'currency':     'INR',
                'note':         'Trained on Indian bank synthetic data',
            }
            with open(META_PATH, 'w') as f:
                json.dump(new_meta, f, indent=2)
            record['model_promoted'] = True

        # Archive used files
        archive_training_files(files_used, run_id)

        record['status'] = 'success'

    except Exception as e:
        record['error'] = traceback.format_exc()

    finally:
        record['duration_seconds'] = round(time.time() - started, 2)

        history = _load_history()
        history.insert(0, {k: v for k, v in record.items()})
        history = history[:50]  # keep last 50 runs
        _save_history(history)

        _training_running = False
        _training_lock.release()

    return record


# ── Rollback ──────────────────────────────────────────────────────────────────

def rollback_model():
    """Restore pd_model_backup.pkl as the active model."""
    if not os.path.exists(BACKUP_PATH):
        raise FileNotFoundError("No backup model found to roll back to.")
    shutil.copy2(BACKUP_PATH, MODEL_PATH)
    return {'status': 'rolled back', 'message': 'Previous model restored as active model.'}


if __name__ == '__main__':
    print(run_training(triggered_by='cli'))
