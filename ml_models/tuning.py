"""
tuning.py - RandomizedSearchCV hyperparameter calibration for the Dataset Lab
(Phase 2 of the TAI paper's pipeline: "Hyperparameter Calibration").

trainer.py's _build_* functions construct AND fit a model in one call (they
were written for the banking app's single-shot training run), so they can't
be handed to RandomizedSearchCV, which needs an unfitted estimator with
get_params/set_params. This module provides that unfitted counterpart for
each of the five model types the Lab supports, with parameter grids and a
random_state consistent with trainer.py's defaults (see ml_models/
hyperparameters.json) so an untuned run and a tuned run differ only in the
tuning step itself.

SMOTE + tuning together, done correctly: if the caller wants both, SMOTE
must be re-fit on each inner CV fold's training portion only, not applied
once to the whole training set before the search runs - otherwise a
synthetic point's real "parent" row can land in that fold's held-out
validation split, which is exactly the leakage mechanism the TAI paper's
reviewers flagged (see paper analysis/draft one/RESULTS_LOG.md). This is
why every model here is wrapped in a Pipeline with a uniform 'clf' step
(even XGBoost, normally used unwrapped elsewhere in this codebase) and,
when resample='smote', an imblearn Pipeline with a leading 'smote' step:
imblearn's Pipeline re-fits every step, including resampling, on each CV
fold's training portion and is a no-op at predict time, which is exactly
the semantics needed here.
"""
import numpy as np
from sklearn.ensemble import (ExtraTreesClassifier, GradientBoostingClassifier,
                               RandomForestClassifier)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

# All keys are 'clf__'-prefixed since every model_type is now Pipeline-wrapped
# for tuning purposes (see build_unfitted), regardless of `resample`.
PARAM_GRIDS = {
    'xgboost': {
        'clf__n_estimators': [100, 150, 200, 300, 400],
        'clf__max_depth': [3, 4, 5, 6, 8],
        'clf__learning_rate': [0.01, 0.03, 0.05, 0.1, 0.2],
        'clf__subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
        'clf__colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
        'clf__min_child_weight': [1, 3, 5, 10],
        'clf__gamma': [0, 0.1, 0.5, 1.0],
        'clf__reg_alpha': [0, 0.1, 0.5, 1.0],
        'clf__reg_lambda': [0.5, 1.0, 2.0, 3.0],
    },
    'random_forest': {
        'clf__n_estimators': [100, 200, 300, 400, 500],
        'clf__max_depth': [4, 6, 8, 10, 12, None],
        'clf__min_samples_leaf': [1, 2, 5, 10],
        'clf__max_features': ['sqrt', 'log2', None],
    },
    'extra_trees': {
        'clf__n_estimators': [100, 200, 300, 400, 500],
        'clf__max_depth': [4, 6, 8, 10, 12, None],
        'clf__min_samples_leaf': [1, 2, 5, 10],
        'clf__max_features': ['sqrt', 'log2', None],
    },
    'gradient_boosting': {
        'clf__n_estimators': [100, 150, 200, 300],
        'clf__max_depth': [2, 3, 4, 5],
        'clf__learning_rate': [0.01, 0.03, 0.05, 0.1, 0.2],
        'clf__subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
        'clf__min_samples_leaf': [1, 2, 5, 10],
    },
    'logistic_regression': {
        'clf__C': [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0],
        'clf__penalty': ['l2'],
        'clf__solver': ['lbfgs'],
    },
}


def _base_steps(model_type, random_state):
    """(name, transformer_or_estimator) steps, classifier always keyed 'clf'."""
    if model_type == 'xgboost':
        return [('clf', XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8,
                                      colsample_bytree=0.8, min_child_weight=5, gamma=0.1, reg_alpha=0.1,
                                      reg_lambda=1.0, random_state=random_state, eval_metric='logloss',
                                      verbosity=0, n_jobs=-1))]
    if model_type == 'random_forest':
        return [('imputer', SimpleImputer(strategy='median')),
               ('clf', RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=5,
                                              max_features='sqrt', class_weight='balanced',
                                              random_state=random_state, n_jobs=-1))]
    if model_type == 'extra_trees':
        return [('imputer', SimpleImputer(strategy='median')),
               ('clf', ExtraTreesClassifier(n_estimators=300, max_depth=8, min_samples_leaf=5,
                                            max_features='sqrt', class_weight='balanced',
                                            random_state=random_state, n_jobs=-1))]
    if model_type == 'gradient_boosting':
        return [('imputer', SimpleImputer(strategy='median')),
               ('clf', GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                                                  subsample=0.8, min_samples_leaf=5,
                                                  random_state=random_state))]
    if model_type == 'logistic_regression':
        return [('imputer', SimpleImputer(strategy='median')),
               ('scaler', StandardScaler()),
               ('clf', LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=1000,
                                          class_weight='balanced', random_state=random_state))]
    raise ValueError(f'no tuning grid for model_type {model_type}')


def build_unfitted(model_type, random_state=42, resample=None):
    """Unfitted Pipeline for `model_type`. If resample='smote', an imblearn
    Pipeline with a leading 'smote' step is returned instead of a plain
    sklearn one, so SMOTE is re-fit per CV fold rather than applied once
    up front (see module docstring)."""
    steps = _base_steps(model_type, random_state)
    if resample == 'smote':
        from imblearn.over_sampling import SMOTE
        from imblearn.pipeline import Pipeline as ImbPipeline
        return ImbPipeline([('smote', SMOTE(random_state=random_state))] + steps)
    if resample not in (None, 'none'):
        raise ValueError(f"unknown resample '{resample}'; choose from None, 'smote'")
    return Pipeline(steps)


def tune_and_fit(model_type, X_train, y_train, n_iter=20, cv_folds=5, random_state=42,
                 n_jobs=-1, resample=None):
    """RandomizedSearchCV over PARAM_GRIDS[model_type], scored by AUC,
    StratifiedKFold(cv_folds). X_train/y_train must be the RAW (not yet
    resampled) training fold when resample='smote' - resampling happens
    inside each CV fold and again on the full data for the final refit.
    Returns (fitted_best_estimator, report_dict)."""
    est = build_unfitted(model_type, random_state, resample=resample)
    grid = PARAM_GRIDS[model_type]
    n_candidates = int(np.prod([len(v) for v in grid.values()]))
    n_iter_eff = min(n_iter, n_candidates)  # RandomizedSearchCV errors if n_iter > the full grid size
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    search = RandomizedSearchCV(est, param_distributions=grid, n_iter=n_iter_eff, scoring='roc_auc',
                                cv=cv, random_state=random_state, n_jobs=n_jobs, refit=True)
    search.fit(X_train, y_train)
    report = {
        'n_iter_requested': n_iter, 'n_iter_effective': n_iter_eff, 'n_candidates_full_grid': n_candidates,
        'cv_folds': cv_folds, 'scoring': 'roc_auc', 'resample_inside_cv': resample or 'none',
        'best_params': {k: (v if not isinstance(v, (np.integer, np.floating)) else v.item())
                        for k, v in search.best_params_.items()},
        'best_cv_auc': round(float(search.best_score_), 4),
    }
    return search.best_estimator_, report
