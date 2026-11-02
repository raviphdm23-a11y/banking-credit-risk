"""
Nested (honest) validation of the whole SHARP selection pipeline.

The headline out-of-fold Gini scores a model whose COLUMNS were chosen with the full data's outcome
(screening, Shapley confirmation, parsimony choice of k). That is a known optimism. This script removes it: for each
outer fold, Stages 0-3 are re-run from scratch on the training part only, the resulting model is fitted on that
training part, and it scores the untouched test part. Pooling the five test parts gives a Gini in which no
outcome of a test firm influenced anything, including which columns were selected.

    python ml_models/nested_validation.py --csv <file> --target target --out <json> [--folds 5]

It also records, per fold, which players/columns were selected, so selection stability is visible.
Runtime is dominated by Stage 2 (sampled Shapley), roughly 10-15 minutes per fold.
"""
import argparse
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'backend'))
import missing_governance as mg      # noqa: E402
import selection as sel              # noqa: E402
import staged_run as sr              # noqa: E402


def _raw_prob(scorer, df_cols):
    W = scorer.encoder.transform(scorer._prep(df_cols)).values.astype(float)
    return 1.0 / (1.0 + np.exp(-(scorer.intercept + W @ scorer.coef)))


def nested_validation(df, target, n_folds=5, seed=42, workdir=None, refer_col=None):
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    df = df.reset_index(drop=True)
    y = df[target].astype(int).values
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    pooled = np.full(len(df), np.nan)
    folds = []
    for f, (tr, te) in enumerate(skf.split(df, y)):
        t0 = time.time()
        dtr = df.iloc[tr].reset_index(drop=True)
        run = sr.StagedRun(dtr, target, 'NESTED_%d' % f, workdir or os.path.join(HERE, '_nested_tmp'),
                           exploratory=True, verbose=False)
        run.stage0(); run.stage1(); run.stage2(); run.stage3()
        d = run.state['stage3']['decision']
        cols = run.state['stage3']['selected_columns']
        sc, _ = mg.build_scorer(dtr, target, cols, random_state=seed)
        p = _raw_prob(sc, df.iloc[te][cols])
        pooled[te] = p
        auc = float(roc_auc_score(y[te], p))
        folds.append({'fold': f, 'k': int(d['selected_k']) if d['tolerance_met'] else None, 'n_columns': len(cols),
                      'columns': cols, 'test_auc': auc, 'test_gini': 2 * auc - 1,
                      'selected_players': list(d.get('selected_players') or []), 'seconds': round(time.time() - t0)})
        print('[nested] fold %d: k=%s columns=%d test Gini %.4f (%.0fs)' % (f, folds[-1]['k'], len(cols), 2 * auc - 1,
                                                                            time.time() - t0), flush=True)
    auc = float(roc_auc_score(y, pooled))
    out = {'folds': folds, 'pooled_auc': auc, 'pooled_gini': 2 * auc - 1, 'n': int(len(df)), 'seed': seed}
    if refer_col and refer_col in df.columns:
        m = df[refer_col].notna().values
        a2 = float(roc_auc_score(y[m], pooled[m]))
        out['scored_population'] = {'n': int(m.sum()), 'pooled_auc': a2, 'pooled_gini': 2 * a2 - 1}
    # selection stability: how often each column is selected across folds
    from collections import Counter
    cnt = Counter(c for fo in folds for c in fo['columns'])
    out['column_frequency'] = {c: v for c, v in sorted(cnt.items(), key=lambda kv: -kv[1])}
    out['columns_in_all_folds'] = [c for c, v in cnt.items() if v == n_folds]
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--target', default='target')
    ap.add_argument('--out', required=True)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--refer-col', default=None)
    a = ap.parse_args()
    d = pd.read_csv(a.csv)
    res = nested_validation(d, a.target, a.folds, refer_col=a.refer_col)
    json.dump(res, open(a.out, 'w', encoding='utf-8'), indent=1)
    print('pooled nested Gini %.4f' % res['pooled_gini'])
