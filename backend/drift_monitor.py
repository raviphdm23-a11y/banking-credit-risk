"""
drift_monitor.py
────────────────
Ongoing-monitoring engine for the Governance department: computes the KPI set
prescribed by the AI Risk Governance reference guide —

    Data drift            → PSI          (breach > 0.25, watch > 0.10)
    Performance decay     → AUC stability (breach when drop > 5% vs training baseline)
    Bias                  → Fairness gap  (breach > 0.05 between gender groups)

— per model slot (active_model.json keys), writes gov_kpi_snapshots rows, and
raises gov_alerts on breaches. Baseline distributions are snapshotted at
training time (snapshot_training_baseline, called from ml_models/trainer.py on
promotion) so PSI compares live populations against what the model was
actually trained on.

Honesty rule: thin data reports NO_DATA (or an explicitly-labelled 'cv' basis
for AUC) — numbers are never fabricated to fill a dashboard.
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

from backend import governance_store as gov

ML_DIR = Path(__file__).resolve().parent.parent / 'ml_models'

DEFAULT_THRESHOLDS = {
    'psi_major': 0.25,       # PSI above this = major drift (BREACH)
    'psi_watch': 0.10,       # PSI above this = moderate shift (WATCH)
    'auc_drop_pct': 5.0,     # % AUC degradation vs training baseline = BREACH
    'fairness_gap': 0.05,    # PD gap between gender groups = BREACH
}

MIN_ROWS_PSI = 20            # below this the live sample can't support a PSI
MIN_OUTCOMES_AUC = 10        # matured outcomes needed for a live AUC


def load_thresholds():
    """DEFAULT_THRESHOLDS overridden by hyperparameters.json['governance']."""
    t = dict(DEFAULT_THRESHOLDS)
    try:
        hp = json.loads((ML_DIR / 'hyperparameters.json').read_text())
        for k in t:
            v = (hp.get('governance') or {}).get(k)
            if v is not None:
                t[k] = float(v)
    except Exception:
        pass
    return t


# ── PSI primitives ───────────────────────────────────────────────────────────
def bin_series(values, edges=None, n_bins=10):
    """Decile edges (when edges is None) + relative frequencies. Returns
    (edges list len n+1, freqs list len n)."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return None, None
    if edges is None:
        qs = np.quantile(arr, np.linspace(0, 1, n_bins + 1))
        # de-duplicate edges for near-constant features (PSI on a constant is 0)
        edges = np.unique(qs)
        if edges.size < 2:
            edges = np.array([edges[0] - 0.5, edges[0] + 0.5])
    else:
        edges = np.asarray(edges, dtype=float)
    inner = edges[1:-1]
    idx = np.searchsorted(inner, arr, side='right')
    counts = np.bincount(idx, minlength=edges.size - 1).astype(float)
    freqs = counts / counts.sum()
    return [float(e) for e in edges], [float(f) for f in freqs]


def compute_psi(expected_freqs, actual_freqs, eps=1e-4):
    e = np.clip(np.asarray(expected_freqs, dtype=float), eps, None)
    a = np.clip(np.asarray(actual_freqs, dtype=float), eps, None)
    e, a = e / e.sum(), a / a.sum()
    return float(np.sum((a - e) * np.log(a / e)))


def _psi_status(psi, thresholds):
    if psi is None:
        return 'NO_DATA'
    if psi > thresholds['psi_major']:
        return 'BREACH'
    if psi > thresholds['psi_watch']:
        return 'WATCH'
    return 'OK'


def _slot_filters(slot_key):
    """(where-clause fragment, params) for prediction_store / bank_loan_metrics.
    Segment slots filter on exposure_class; bank slots on bank_id; GENERIC bank
    slots (no Basel segmentation in the source data) on bank_id only."""
    seg, bank = gov.parse_slot(slot_key)
    clauses, params = [], []
    if bank != 'ALL':
        clauses.append('bank_id=?'); params.append(bank)
    if seg != 'GENERIC':
        clauses.append('exposure_class=?'); params.append(seg)
    return (' AND '.join(clauses) or '1=1'), params


# ── KPI computations ─────────────────────────────────────────────────────────
def score_psi(conn, slot_key, thresholds):
    """PSI of live predicted-PD distribution (prediction_store, last 90 days)
    vs the training-time score deciles."""
    baselines = gov.get_latest_baselines(conn, slot_key)
    if not baselines or not baselines.get('score'):
        return {'value': None, 'status': 'NO_DATA',
                'detail': {'reason': 'no training-time score baseline snapshotted yet'}}
    where, params = _slot_filters(slot_key)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    rows = conn.execute(
        f"SELECT pd_point FROM prediction_store WHERE {where} AND as_of_date>=? "
        f"AND pd_point IS NOT NULL", params + [cutoff]).fetchall()
    values = [r[0] for r in rows]
    if len(values) < MIN_ROWS_PSI:
        return {'value': None, 'status': 'NO_DATA',
                'detail': {'reason': f'only {len(values)} predictions in last 90d '
                                     f'(need {MIN_ROWS_PSI})'}}
    base = baselines['score']
    _, freqs = bin_series(values, edges=base['edges'])
    psi = compute_psi(base['freqs'], freqs)
    return {'value': psi, 'status': _psi_status(psi, thresholds),
            'detail': {'n_live': len(values), 'baseline_run': baselines['run_id'],
                       'baseline_n': base['n_rows']}}


def feature_psi(conn, slot_key, thresholds):
    """Per-feature PSI: training-time bins vs current bank_loan_metrics rows.
    Returns (headline dict, per-feature list) — headline is the worst feature."""
    baselines = gov.get_latest_baselines(conn, slot_key)
    if not baselines or not baselines.get('features'):
        return ({'value': None, 'status': 'NO_DATA',
                 'detail': {'reason': 'no training-time feature baselines snapshotted yet'}}, [])
    where, params = _slot_filters(slot_key)
    blm_cols = {r[1] for r in conn.execute('PRAGMA table_info(bank_loan_metrics)')}
    per_feature = []
    for feat, base in baselines['features'].items():
        if feat not in blm_cols:
            continue
        rows = conn.execute(
            f'SELECT "{feat}" FROM bank_loan_metrics WHERE {where} AND "{feat}" IS NOT NULL',
            params).fetchall()
        values = [r[0] for r in rows]
        if len(values) < MIN_ROWS_PSI:
            per_feature.append({'feature': feat, 'psi': None, 'status': 'NO_DATA'})
            continue
        _, freqs = bin_series(values, edges=base['edges'])
        psi = compute_psi(base['freqs'], freqs)
        per_feature.append({'feature': feat, 'psi': round(psi, 4),
                            'status': _psi_status(psi, thresholds)})
    scored = [f for f in per_feature if f['psi'] is not None]
    if not scored:
        return ({'value': None, 'status': 'NO_DATA',
                 'detail': {'reason': 'no feature had enough live rows'}}, per_feature)
    worst = max(scored, key=lambda f: f['psi'])
    return ({'value': worst['psi'], 'status': worst['status'],
             'detail': {'worst_feature': worst['feature'],
                        'features_scored': len(scored),
                        'baseline_run': baselines['run_id']}}, per_feature)


def auc_stability(conn, slot_key, thresholds):
    """AUC degradation vs training baseline. Live AUC from matured RM outcomes
    (prediction_store ⋈ rm_outcomes) when there are enough of both classes;
    otherwise falls back to the latest run's CV-mean AUC, labelled basis 'cv'."""
    seg, bank = gov.parse_slot(slot_key)
    reg = gov._latest_registry_row(conn, seg, bank)
    baseline_auc = (reg or {}).get('auc_roc')
    if baseline_auc is None:
        return {'value': None, 'status': 'NO_DATA',
                'detail': {'reason': 'no promoted model in model_registry for this slot'}}

    where, params = _slot_filters(slot_key)
    live, basis = None, None
    try:
        rows = conn.execute(
            f"SELECT p.pd_point, o.default_flag FROM prediction_store p "
            f"JOIN rm_outcomes o ON o.case_id=p.case_id "
            f"WHERE {where} AND p.pd_point IS NOT NULL AND o.default_flag IS NOT NULL",
            params).fetchall()
    except sqlite3.OperationalError:
        rows = []
    scores = [r[0] for r in rows]
    labels = [r[1] for r in rows]
    if len(rows) >= MIN_OUTCOMES_AUC and len(set(labels)) == 2:
        from sklearn.metrics import roc_auc_score
        live, basis = float(roc_auc_score(labels, scores)), 'outcomes'
    else:
        # proxy: cross-validated AUC from the slot's latest training run
        try:
            history = json.loads((ML_DIR / 'run_history.json').read_text())
            for run in history:
                if run.get('status') != 'success' or run.get('exposure_class') != seg:
                    continue
                run_bank = (run.get('bank_ids') or [None])[0] if len(run.get('bank_ids') or []) == 1 else 'ALL'
                if (bank == 'ALL') != (run_bank == 'ALL') or (bank != 'ALL' and run_bank != bank):
                    continue
                cv = (run.get('cv_metrics') or {}).get('cv_auc_mean')
                if cv is not None:
                    live, basis = float(cv), 'cv'
                    break
        except Exception:
            pass

    if live is None:
        return {'value': None, 'status': 'NO_DATA',
                'detail': {'reason': f'fewer than {MIN_OUTCOMES_AUC} matured outcomes '
                                     'and no CV metrics available',
                           'baseline_auc': baseline_auc}}
    drop_pct = (baseline_auc - live) / baseline_auc * 100 if baseline_auc else 0.0
    thr = thresholds['auc_drop_pct']
    status = 'BREACH' if drop_pct > thr else ('WATCH' if drop_pct > thr / 2 else 'OK')
    return {'value': round(drop_pct, 3), 'status': status,
            'detail': {'baseline_auc': baseline_auc, 'current_auc': round(live, 4),
                       'basis': basis, 'n_outcomes': len(rows)}}


def fairness_gap(conn, slot_key, thresholds):
    """Gap in mean observed PD (fallback: default rate) between the two largest
    gender_enc groups in the slot's population. NO_DATA when gender isn't
    recorded for this population — most segments, by design, since protected
    attributes are excluded from training (COMPLIANCE_EXCLUDED_COLS)."""
    where, params = _slot_filters(slot_key)
    rows = conn.execute(
        f"SELECT gender_enc, pd_observed, default_flag FROM bank_loan_metrics "
        f"WHERE {where} AND gender_enc IS NOT NULL", params).fetchall()
    if len(rows) < MIN_ROWS_PSI:
        return {'value': None, 'status': 'NO_DATA',
                'detail': {'reason': 'gender not recorded for this population '
                                     '(protected attributes excluded by policy)'}}
    groups = {}
    for g, pd_obs, dflag in rows:
        groups.setdefault(g, []).append((pd_obs, dflag))
    if len(groups) < 2:
        return {'value': None, 'status': 'NO_DATA',
                'detail': {'reason': 'only one gender group present'}}
    top2 = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:2]
    means, basis = [], 'pd_observed'
    for _, members in top2:
        pds = [m[0] for m in members if m[0] is not None]
        if len(pds) >= MIN_ROWS_PSI // 2:
            means.append(float(np.mean(pds)))
        else:
            basis = 'default_rate'
            flags = [m[1] for m in members if m[1] is not None]
            means.append(float(np.mean(flags)) if flags else 0.0)
    gap = abs(means[0] - means[1])
    status = 'BREACH' if gap > thresholds['fairness_gap'] else 'OK'
    return {'value': round(gap, 4), 'status': status,
            'detail': {'basis': basis,
                       'groups': {str(top2[0][0]): {'n': len(top2[0][1]), 'mean': round(means[0], 4)},
                                  str(top2[1][0]): {'n': len(top2[1][1]), 'mean': round(means[1], 4)}}}}


def prediction_volume(conn, slot_key):
    where, params = _slot_filters(slot_key)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    n = conn.execute(
        f"SELECT COUNT(*) FROM prediction_store WHERE {where} AND as_of_date>=?",
        params + [cutoff]).fetchone()[0]
    return {'value': float(n), 'status': 'OK', 'detail': {'window_days': 30}}


# ── training-time baseline snapshot (called from trainer.py) ─────────────────
def snapshot_training_baseline(conn, run_id, slot_key, X_train, proba_train,
                               max_features=40):
    """Persist decile bins of the training-set predicted PD ('score') and of
    each training feature, so later monitor runs can compute PSI against the
    population the model was actually fitted on."""
    gov.init_schema(conn)
    n = len(proba_train)
    edges, freqs = bin_series(list(proba_train))
    if edges:
        gov.save_baseline(conn, run_id, slot_key, 'score', None, edges, freqs, n)
    count = 0
    for col in X_train.columns:
        if count >= max_features:
            break
        try:
            series = X_train[col].dropna().astype(float)
        except (TypeError, ValueError):
            continue
        if series.empty or series.nunique() < 2:
            continue
        edges, freqs = bin_series(series.tolist())
        if edges:
            gov.save_baseline(conn, run_id, slot_key, 'feature', col, edges, freqs,
                              len(series))
            count += 1
    return count


# ── orchestrator ─────────────────────────────────────────────────────────────
_ALERT_TYPES = {'psi_score': 'MAJOR_DRIFT', 'psi_feature': 'MAJOR_DRIFT',
                'auc_stability': 'PERFORMANCE_DEGRADATION', 'fairness_gap': 'BIAS'}
_THRESHOLD_KEYS = {'psi_score': 'psi_major', 'psi_feature': 'psi_major',
                   'auc_stability': 'auc_drop_pct', 'fairness_gap': 'fairness_gap'}


def run_monitor(conn, thresholds=None):
    """One full monitoring pass over every active model slot. Writes one
    gov_kpi_snapshots row per (slot, KPI), raises deduped alerts on breaches,
    and seals the pass with a MONITOR_RUN audit event."""
    gov.init_schema(conn)
    thresholds = thresholds or load_thresholds()
    run_ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    slots = gov._load_active_registry()
    kpis_written, alerts_created, breaches = 0, [], []

    def _write(slot_key, model_id, kpi, result, feature=None):
        nonlocal kpis_written
        conn.execute(
            "INSERT INTO gov_kpi_snapshots (run_ts, slot_key, model_id, kpi, feature, "
            "value, threshold, status, detail_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_ts, slot_key, model_id, kpi, feature, result.get('value'),
             thresholds.get(_THRESHOLD_KEYS.get(kpi)), result['status'],
             json.dumps(result.get('detail') or {}, default=str)))
        kpis_written += 1

    for slot_key in slots:
        seg, bank = gov.parse_slot(slot_key)
        reg = gov._latest_registry_row(conn, seg, bank)
        model_id = (reg or {}).get('model_id')

        results = {
            'psi_score': score_psi(conn, slot_key, thresholds),
            'auc_stability': auc_stability(conn, slot_key, thresholds),
            'fairness_gap': fairness_gap(conn, slot_key, thresholds),
            'prediction_volume': prediction_volume(conn, slot_key),
        }
        headline, per_feature = feature_psi(conn, slot_key, thresholds)
        results['psi_feature'] = headline

        for kpi, result in results.items():
            _write(slot_key, model_id, kpi, result)
        for f in per_feature:
            if f['psi'] is not None:
                _write(slot_key, model_id, 'psi_feature',
                       {'value': f['psi'], 'status': f['status'], 'detail': {}},
                       feature=f['feature'])

        for kpi, result in results.items():
            if result['status'] != 'BREACH':
                continue
            alert_type = _ALERT_TYPES.get(kpi)
            if not alert_type:
                continue
            thr = thresholds.get(_THRESHOLD_KEYS[kpi])
            msg = (f"{kpi} = {result['value']} breached threshold {thr} for {slot_key}"
                   + (f" (worst feature: {result['detail'].get('worst_feature')})"
                      if kpi == 'psi_feature' else ''))
            alert_id = gov.create_alert(conn, slot_key, alert_type, kpi,
                                        result['value'], thr, 'BREACH', msg,
                                        model_id=model_id)
            alerts_created.append(alert_id)
            breaches.append({'slot_key': slot_key, 'kpi': kpi,
                             'value': result['value'], 'threshold': thr})

    # system-level human-oversight KPI
    try:
        from backend.rm_case_store import insights
        ins = insights(conn)
        _write('SYSTEM', None, 'override_rate',
               {'value': ins.get('override_rate_pct', 0.0), 'status': 'OK',
                'detail': {'decisions_final': ins.get('decisions_final'),
                           'agreement_rate_pct': ins.get('agreement_rate_pct'),
                           'override_default_rate_pct': ins.get('override_default_rate_pct'),
                           'aligned_default_rate_pct': ins.get('aligned_default_rate_pct')}})
    except Exception as e:
        print(f'[drift_monitor] override_rate KPI failed (non-fatal): {e}')

    conn.commit()
    summary = {'run_ts': run_ts, 'slots': len(slots), 'kpis_written': kpis_written,
               'alerts_created': len(set(alerts_created)), 'breaches': breaches,
               'thresholds': thresholds}
    gov.append_audit_event(conn, 'MONITOR_RUN', actor_role='monitor',
                           object_type='monitor', object_id=run_ts, payload=summary)
    return summary
