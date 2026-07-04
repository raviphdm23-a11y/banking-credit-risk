"""
Compare XGBoost vs Logistic Regression on REALISTIC synthetic data.

This script trains both models on the realistic_synthetic_data.csv which includes:
- Feature measurement noise (CIBIL +/-10, income +/-15%)
- Probabilistic defaults (not deterministic threshold)
- Feature correlations (income -> CIBIL -> tenure)
- Non-linear risk curves (DE ratio thresholds)
- Macro regime effects (expansion/stable/contraction)

Expected: Models will show differentiation (0.70-0.85 AUC range) instead of perfect 1.0
"""

import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, classification_report, confusion_matrix,
                             accuracy_score, precision_score, recall_score, f1_score)
from xgboost import XGBClassifier
from sklearn.pipeline import Pipeline
import json
from datetime import datetime

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REALISTIC_DATA_FILE = os.path.join(PROJECT_ROOT, 'data', 'training', 'realistic_synthetic_data.csv')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'model_comparison')
os.makedirs(OUTPUT_DIR, exist_ok=True)

FEATURE_COLS = [
    'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
    'age', 'employment_type_enc', 'years_employed', 'annual_income', 'foir',
    'num_dependents', 'city_tier_enc', 'education_enc', 'residence_type_enc',
    'loan_purpose_enc', 'cibil_score', 'previous_default_flag',
    'months_as_customer', 'num_late_payments_past_12m', 'existing_loans_count',
    'num_existing_products'
]
TARGET_COL = 'default_flag'


def load_realistic_data():
    """Load the realistic synthetic dataset."""
    if not os.path.exists(REALISTIC_DATA_FILE):
        raise FileNotFoundError(f"Realistic data not found: {REALISTIC_DATA_FILE}")

    df = pd.read_csv(REALISTIC_DATA_FILE)
    print(f"[DATA] Loaded {len(df):,} loans from realistic dataset")
    print(f"       Default rate: {df[TARGET_COL].mean() * 100:.2f}%")

    # Keep only required features
    available_cols = [c for c in FEATURE_COLS if c in df.columns]
    missing_cols = [c for c in FEATURE_COLS if c not in df.columns]

    if missing_cols:
        print(f"       WARNING: Missing columns: {missing_cols}")

    return df[available_cols + [TARGET_COL]].dropna()


def train_xgboost(X_train, X_test, y_train, y_test):
    """Train XGBoost model on realistic data."""
    print("\n[XGBOOST] Training on realistic data...")

    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
        verbosity=0
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    return model, {
        'auc_roc': roc_auc_score(y_test, y_pred_proba),
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, zero_division=0),
        'recall': recall_score(y_test, y_pred, zero_division=0),
        'f1': f1_score(y_test, y_pred, zero_division=0),
        'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
    }


def train_logistic_regression(X_train, X_test, y_train, y_test):
    """Train Logistic Regression model on realistic data (with scaling)."""
    print("\n[LOGISTIC REGRESSION] Training on realistic data...")

    # Logistic Regression needs scaling, so use Pipeline
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=1.0,
            penalty='l2',
            solver='lbfgs',
            max_iter=1000,
            class_weight='balanced',
            random_state=42
        ))
    ])

    pipe.fit(X_train, y_train)

    # Evaluate
    y_pred_proba = pipe.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    return pipe, {
        'auc_roc': roc_auc_score(y_test, y_pred_proba),
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, zero_division=0),
        'recall': recall_score(y_test, y_pred, zero_division=0),
        'f1': f1_score(y_test, y_pred, zero_division=0),
        'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
    }


def main():
    """Main comparison workflow."""
    print("\n" + "=" * 80)
    print("MODEL COMPARISON: XGBoost vs Logistic Regression on REALISTIC DATA")
    print("=" * 80)

    # Load data
    df = load_realistic_data()

    X = df[FEATURE_COLS].copy()
    y = df[TARGET_COL].copy()

    # Keep only numeric columns
    X = X.select_dtypes(include=[np.number])

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\n[SPLIT] Train: {len(X_train):,} loans | Test: {len(X_test):,} loans")
    print(f"        Train default rate: {y_train.mean() * 100:.2f}%")
    print(f"        Test default rate: {y_test.mean() * 100:.2f}%")

    # Train XGBoost
    xgb_model, xgb_metrics = train_xgboost(X_train, X_test, y_train, y_test)

    # Train Logistic Regression
    lr_model, lr_metrics = train_logistic_regression(X_train, X_test, y_train, y_test)

    # Results
    print("\n" + "=" * 80)
    print("RESULTS: REALISTIC DATA (Feature noise, macro regimes, feature correlations)")
    print("=" * 80)

    print("\n[XGBOOST]")
    for metric, value in xgb_metrics.items():
        if metric != 'confusion_matrix':
            print(f"  {metric:15s}: {value:.4f}")
    print(f"  confusion_matrix: TP={xgb_metrics['confusion_matrix'][1][1]}, "
          f"TN={xgb_metrics['confusion_matrix'][0][0]}, "
          f"FP={xgb_metrics['confusion_matrix'][0][1]}, "
          f"FN={xgb_metrics['confusion_matrix'][1][0]}")

    print("\n[LOGISTIC REGRESSION]")
    for metric, value in lr_metrics.items():
        if metric != 'confusion_matrix':
            print(f"  {metric:15s}: {value:.4f}")
    print(f"  confusion_matrix: TP={lr_metrics['confusion_matrix'][1][1]}, "
          f"TN={lr_metrics['confusion_matrix'][0][0]}, "
          f"FP={lr_metrics['confusion_matrix'][0][1]}, "
          f"FN={lr_metrics['confusion_matrix'][1][0]}")

    # Comparison
    print("\n" + "=" * 80)
    print("DIFFERENTIATION ANALYSIS")
    print("=" * 80)

    xgb_auc = xgb_metrics['auc_roc']
    lr_auc = lr_metrics['auc_roc']
    auc_diff = abs(xgb_auc - lr_auc)
    winner = 'XGBoost' if xgb_auc > lr_auc else 'Logistic Regression'

    print(f"\nAUC-ROC Comparison:")
    print(f"  XGBoost:              {xgb_auc:.4f}")
    print(f"  Logistic Regression:  {lr_auc:.4f}")
    print(f"  Difference:           {auc_diff:.4f} ({auc_diff * 100:.2f}%)")
    print(f"  Winner:               {winner} (handles non-linear relationships better)")

    print(f"\nInterpretation:")
    if auc_diff > 0.05:
        print(f"  ✓ CLEAR DIFFERENTIATION: Models show meaningful difference")
        print(f"    XGBoost's non-linear trees capture complex patterns better")
        print(f"    than Logistic Regression's linear decision boundary.")
    elif auc_diff > 0.02:
        print(f"  ~ MODERATE DIFFERENTIATION: Some difference visible")
    else:
        print(f"  ✗ MINIMAL DIFFERENTIATION: Models perform similarly")

    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'data_file': REALISTIC_DATA_FILE,
        'data_info': {
            'total_loans': len(df),
            'default_rate': float(df[TARGET_COL].mean()),
            'train_size': len(X_train),
            'test_size': len(X_test),
        },
        'xgboost': xgb_metrics,
        'logistic_regression': lr_metrics,
        'comparison': {
            'xgb_auc': xgb_auc,
            'lr_auc': lr_auc,
            'auc_difference': auc_diff,
            'winner': winner,
        }
    }

    results_file = os.path.join(OUTPUT_DIR, 'comparison_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n[SAVED] Results to: {results_file}")
    print("\n" + "=" * 80 + "\n")


if __name__ == '__main__':
    main()
