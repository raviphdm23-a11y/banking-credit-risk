"""panel_adapter.py - panel -> cross-sectional modelling frame for SHARP/AEGIS.

SHARP models a cross-section of INDEPENDENT units, one outcome each. Panel data
has repeated observations of the same unit over time, so feeding it raw into the
row-independent pipeline leaks the same entity across train/test folds and
inflates every metric - the exact failure class the revision exists to remove.

This module is the ONLY place that knows about panel structure. Given a
per-dataset manifest it validates the panel, picks the modelling unit, and
returns (frame, target, groups) that the unchanged SHARP pipeline consumes. All
panel leakage control lives here, in one auditable layer in front of SHARP.

Declared shapes (manifest `data_shape`):
  cross_section  (default; no manifest needed) - passthrough, today's behaviour.
  panel          - reshaped per the manifest.

Panel framings (manifest `framing`):
  snapshot  one row per entity. Features taken from an as-of observation
            (default the first in time); target = an entity-level event (ever
            within the observed life, or within a horizon of the as-of date).
            Rows are independent by construction, so the existing stratified CV
            is already leakage-safe - `groups` is returned but not needed.
  hazard    one row per entity-period is KEPT; target = the per-period event; a
            `groups` vector (entity id) is returned so entity-aware CV keeps
            every row of an entity inside one fold. REQUIRES group-aware CV
            threaded through Stages 2-4 before its numbers can be trusted.

`segment` (corporate|retail) only sets sensible DEFAULTS (corporate -> snapshot;
retail -> hazard). Both segments share one code path and both ultimately yield
"independent rows (+ a group key)", which is all SHARP ever required.

Signalling policy (see AEGIS G0): the MANIFEST is the source of truth. The
`detect_panel` heuristic only PROPOSES and CROSS-CHECKS; a mismatch between a
declared shape and the detected shape is a hard error, never silently resolved,
because a wrong guess here is precisely the leakage we must avoid.

ASCII-only in emitted strings (Windows cp1252 console).
"""
import json
import os
import warnings

import numpy as np
import pandas as pd

# Columns that are almost never model features in a panel: bookkeeping time
# indices and co-outcome markers. Used only to DERIVE a feature list when the
# manifest does not give one explicitly; an explicit `feature_cols` overrides.
_COMMON_NON_FEATURES = {'payoff_time', 'status_time'}


# ---------------------------------------------------------------------------
# Manifest loading / discovery
# ---------------------------------------------------------------------------

def find_manifest(dataset_path):
    """Return the sibling `<stem>.manifest.json` for a dataset CSV, or None.

    Absence of a manifest means the dataset is treated as `cross_section`
    (today's behaviour) - panels must opt in explicitly.
    """
    stem, _ = os.path.splitext(dataset_path)
    cand = stem + '.manifest.json'
    return cand if os.path.exists(cand) else None


def load_manifest(path):
    with open(path, 'r', encoding='utf-8') as fh:
        m = json.load(fh)
    return m


# ---------------------------------------------------------------------------
# Detection (PROPOSES only - never decides)
# ---------------------------------------------------------------------------

def detect_panel(df, entity_id=None):
    """Heuristic smoke-alarm: does this frame look like a panel?

    Returns a dict describing what was seen. This is advisory only; the manifest
    decides. If `entity_id` is given, the repetition of THAT column is measured;
    otherwise every column is scanned for the most repeated-looking id-like key.
    """
    n = len(df)
    best = None
    cols = [entity_id] if entity_id else list(df.columns)
    for c in cols:
        if c not in df.columns:
            continue
        nun = df[c].nunique(dropna=True)
        if nun == 0:
            continue
        rows_per = n / nun
        # id-like: many-to-one repetition, not a near-unique key, not a constant
        if rows_per >= 1.5 and 1 < nun < n:
            if best is None or rows_per > best['rows_per_entity']:
                vc = df[c].value_counts()
                best = {'entity_id_guess': c, 'n_entities': int(nun),
                        'rows_per_entity': float(rows_per),
                        'max_rows_one_entity': int(vc.iloc[0])}
    looks_panel = best is not None and best['rows_per_entity'] >= 1.5
    return {'looks_panel': bool(looks_panel), 'n_rows': int(n), 'detail': best}


# ---------------------------------------------------------------------------
# Validation - the manifest must agree with the data, or we stop
# ---------------------------------------------------------------------------

def validate(df, m):
    """Check a panel manifest against the data; raise on any mismatch.

    Enforces the AEGIS G0 rule: declared shape and detected shape must agree.
    Returns the manifest unchanged when valid.
    """
    shape = m.get('data_shape', 'cross_section')
    if shape == 'cross_section':
        det = detect_panel(df)
        if det['looks_panel']:
            raise ValueError(
                'Manifest declares data_shape=cross_section but the data looks '
                'like a panel (column %r repeats ~%.1f rows/entity). Supply a '
                'panel manifest or confirm cross_section at G0 - a panel run '
                'through the row-independent pipeline leaks and inflates metrics.'
                % (det['detail']['entity_id_guess'], det['detail']['rows_per_entity']))
        return m
    if shape != 'panel':
        raise ValueError("data_shape must be 'cross_section' or 'panel', got %r" % shape)

    for key in ('entity_id', 'time_col', 'target'):
        if not m.get(key):
            raise ValueError('panel manifest missing required key %r' % key)
    keys = _key_cols(m)
    for c in keys + [m['time_col'], m['target']]:
        if c not in df.columns:
            raise ValueError('manifest references %r, not a column in the data' % c)

    # composite-key repetition check: the entity key must actually repeat
    ng = df.groupby(keys).ngroups
    if not (ng < len(df)):
        raise ValueError(
            'Manifest declares a panel on entity_id=%r but that key does not '
            'repeat (%d keys for %d rows - looks cross-sectional). Refusing to '
            'proceed on a mismatch.' % (m['entity_id'], ng, len(df)))

    framing = m.get('framing') or _default_framing(m)
    if framing not in ('snapshot', 'hazard'):
        raise ValueError("framing must be 'snapshot' or 'hazard', got %r" % framing)
    return m


def temporal_split(df, time_col, test_frac=0.3):
    """Train-past / test-future split by calendar time, for out-of-time (OOT)
    validation. Rows at or before the (1-test_frac) quantile of `time_col` are
    train; later rows are test. Returns (train_mask, test_mask, t_cut).

    This is what remediates the TIME-LEAKAGE limitation that group-aware CV
    cannot: grouped CV keeps an entity's rows together but still lets the model
    see every calendar period in training, so macro covariates shared across
    entities per period leak across folds. A train-past / test-future split is
    the realistic forward-prediction test of whether the model generalises in
    time (e.g. whether it survives a shift in the macro regime / default rate).
    """
    t = df[time_col].to_numpy()
    t_cut = float(pd.Series(t).quantile(1 - test_frac))
    return (t <= t_cut), (t > t_cut), t_cut


def _key_cols(m):
    """Entity key as a list of columns (supports a composite key).

    Mortgage is the motivating case: a bare `id` is reused across refinances, so
    the true loan is the composite `(id, orig_time)`. Declaring entity_id as a
    list separates those vintages; a string key still works as a 1-element list.
    """
    eid = m['entity_id']
    return list(eid) if isinstance(eid, (list, tuple)) else [eid]


def _group_vector(frame_index_or_df, keys):
    """A 1-D integer group key per row, from one or more key columns."""
    if isinstance(frame_index_or_df, pd.DataFrame):
        if len(keys) == 1:
            return pd.factorize(frame_index_or_df[keys[0]])[0]
        return pd.factorize(list(map(tuple, frame_index_or_df[keys].to_numpy())))[0]
    return pd.factorize(frame_index_or_df)[0]


def _default_framing(m):
    """segment -> default framing. Corporate statements are sparse/annual, so a
    snapshot is the natural default; retail accounts are dense time series, so a
    hazard framing is the natural default."""
    return 'snapshot' if m.get('segment') == 'corporate' else (
        'hazard' if m.get('segment') == 'retail' else 'snapshot')


# ---------------------------------------------------------------------------
# Derived features (trajectory bridge: panel info -> a static column)
# ---------------------------------------------------------------------------

def _apply_derived(frame, derived):
    """Add derived columns. Each spec: {name, op, a, b?}. Supported ops:
    sub (a-b), add, ratio (a/b, 0-safe), abs_diff. This is the bridge that lets
    corporate trajectory signals (e.g. change in leverage) enter SHARP as plain
    static columns without SHARP needing to know about time.
    """
    for d in (derived or []):
        name, op, a = d['name'], d['op'], d['a']
        if op in ('sub', 'add', 'ratio', 'abs_diff'):
            b = d['b']
            av, bv = frame[a].astype(float), frame[b].astype(float)
            if op == 'sub':
                frame[name] = av - bv
            elif op == 'add':
                frame[name] = av + bv
            elif op == 'abs_diff':
                frame[name] = (av - bv).abs()
            else:  # ratio
                frame[name] = np.where(bv != 0, av / bv.replace(0, np.nan), np.nan)
        else:
            raise ValueError('unknown derived op %r for %r' % (op, name))
    return frame


# ---------------------------------------------------------------------------
# Framing: snapshot (one row per entity)
# ---------------------------------------------------------------------------

def frame_snapshot(df, m):
    """Collapse the panel to one row per entity.

    Config under manifest['snapshot']:
      as_of           'first' | 'last' | <int time>   (which obs supplies features)
      target_policy   'ever'  | 'within_horizon'
      horizon         int (periods after as_of; required for within_horizon)
      feature_cols    explicit list of as-of feature columns (recommended)
      derived_features list of derive specs (see _apply_derived)
    """
    cfg = m.get('snapshot', {})
    keys, tcol, ev = _key_cols(m), m['time_col'], m['target']
    as_of = cfg.get('as_of', 'first')
    target_policy = cfg.get('target_policy', 'ever')

    g = df.sort_values(keys + [tcol]).reset_index(drop=True)

    # --- pick the as-of row per entity (supplies the features; keeps all cols
    #     so derived features can reference columns outside the feature list) ---
    if as_of == 'first':
        asof = g.groupby(keys, as_index=False, sort=False).first()
    elif as_of == 'last':
        asof = g.groupby(keys, as_index=False, sort=False).last()
    elif isinstance(as_of, (int, float)):
        at = g[g[tcol] == as_of]
        if at.empty:
            raise ValueError('as_of time %r not present in %r' % (as_of, tcol))
        asof = at.groupby(keys, as_index=False, sort=False).first()
    else:
        raise ValueError('as_of must be first|last|<int>, got %r' % (as_of,))

    # --- feature columns ---
    feat = cfg.get('feature_cols')
    if not feat:
        drop = set(keys) | {tcol, ev} | _COMMON_NON_FEATURES
        feat = [c for c in g.columns if c not in drop]
    missing = [c for c in feat if c not in asof.columns]
    if missing:
        raise ValueError('snapshot feature_cols not in data: %s' % missing)

    # warn if a declared as-of feature is NOT constant within entity (a
    # point-in-time reading of a time-varying column, not an as-of constant)
    varying = [c for c in feat
               if g.groupby(keys)[c].nunique(dropna=False).max() > 1]
    if varying:
        warnings.warn(
            'snapshot features vary within entity - taken as the as-of (%s) '
            'reading, not an invariant: %s' % (as_of, varying),
            UserWarning, stacklevel=2)

    # derived features are computed from the full as-of row (keys are columns
    # here, so a derive spec may reference a key column such as orig_time)
    asof = _apply_derived(asof, cfg.get('derived_features'))
    derived_names = [d['name'] for d in (cfg.get('derived_features') or [])]

    # --- entity-level target, aligned back onto the as-of rows by key ---
    if target_policy == 'ever':
        tgt = g.groupby(keys, as_index=False)[ev].max()
    elif target_policy == 'within_horizon':
        H = int(cfg['horizon'])
        if as_of == 'first':
            asof_time = g.groupby(keys)[tcol].first()
        elif as_of == 'last':
            asof_time = g.groupby(keys)[tcol].last()
        else:
            asof_time = pd.Series(as_of, index=pd.MultiIndex.from_frame(asof[keys]))
        at = asof_time.rename('_asof').reset_index()
        gg = g[keys + [tcol, ev]].merge(at, on=keys, how='left')
        win = gg[(gg[tcol] > gg['_asof']) & (gg[tcol] <= gg['_asof'] + H)]
        tgt = win.groupby(keys, as_index=False)[ev].max()
    else:
        raise ValueError("target_policy must be 'ever' or 'within_horizon'")

    asof = asof.merge(tgt.rename(columns={ev: '__tgt__'}), on=keys, how='left')
    frame = asof[list(feat) + derived_names].copy()
    frame[ev] = asof['__tgt__'].fillna(0).astype(int)
    # snapshot is one row per entity, so every row is its own group; a group key
    # is returned for interface symmetry with the hazard framing but is trivial.
    groups = np.arange(len(frame))
    frame = frame.reset_index(drop=True)
    meta = {'framing': 'snapshot', 'as_of': as_of, 'target_policy': target_policy,
            'entity_key': keys, 'n_entities': int(len(frame)),
            'feature_cols': list(feat) + derived_names,
            'features_varying_within_entity': varying,
            'event_rate': float(frame[ev].mean()),
            '_time': asof[tcol].to_numpy()}   # as-of (vintage) time per entity row
    return frame, groups, meta


# ---------------------------------------------------------------------------
# Framing: hazard (one row per entity-period kept) - returns a group key
# ---------------------------------------------------------------------------

def frame_hazard(df, m):
    """Keep entity-period rows; return a `groups` vector of entity ids.

    NOTE: this framing is only leakage-safe once group-aware CV is threaded
    through Stages 2-4 (selection supports `groups=`; shapley_utils does not
    yet). Until then its metrics are NOT trustworthy; prepare() refuses to run
    it unless the manifest sets hazard.allow_ungrouped_cv=true (for development).
    """
    cfg = m.get('hazard', {})
    keys, tcol, ev = _key_cols(m), m['time_col'], m['target']
    g = df.sort_values(keys + [tcol]).reset_index(drop=True)

    # optional: cap observations per entity so long-lived entities do not
    # dominate (sample evenly across the entity's timeline)
    cap = cfg.get('max_obs_per_entity')
    if cap:
        def _take(sub):
            if len(sub) <= cap:
                return sub
            idx = np.linspace(0, len(sub) - 1, cap).round().astype(int)
            return sub.iloc[np.unique(idx)]
        g = g.groupby(keys, group_keys=False).apply(_take).reset_index(drop=True)

    feat = cfg.get('feature_cols')
    if not feat:
        drop = set(keys) | {tcol, ev} | _COMMON_NON_FEATURES
        feat = [c for c in g.columns if c not in drop]
    frame = g[feat].copy()
    frame[ev] = g[ev].astype(int)
    groups = _group_vector(g, keys)
    meta = {'framing': 'hazard', 'entity_key': keys,
            'n_entities': int(g.groupby(keys).ngroups),
            'n_rows': int(len(frame)), 'feature_cols': list(feat),
            'event_rate': float(frame[ev].mean()),
            'max_obs_per_entity': cap,
            '_time': g[tcol].to_numpy()}   # calendar time per row, for OOT validation
    return frame, groups, meta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def prepare(source, manifest=None, verbose=True):
    """Produce a SHARP-ready modelling frame from a dataset + manifest.

    source   : a DataFrame, or a path to a CSV (its sibling manifest is used if
               `manifest` is not given).
    manifest : a manifest dict, a path to one, or None.

    Returns {frame, target, groups, data_shape, segment, framing, meta}.
    For cross_section (the default when no manifest) `frame` is the data
    unchanged, `groups` is None, and today's pipeline behaviour is preserved.
    """
    if isinstance(source, str):
        df = pd.read_csv(source)
        if manifest is None:
            mp = find_manifest(source)
            manifest = load_manifest(mp) if mp else None
    else:
        df = source.copy()
    if isinstance(manifest, str):
        manifest = load_manifest(manifest)

    if not manifest or manifest.get('data_shape', 'cross_section') == 'cross_section':
        m = manifest or {'data_shape': 'cross_section'}
        validate(df, m)   # raises if it actually looks like a panel
        tgt = m.get('target')
        if verbose:
            print('[panel_adapter] cross_section passthrough (%d rows)' % len(df), flush=True)
        return {'frame': df, 'target': tgt, 'groups': None, 'time': None,
                'data_shape': 'cross_section', 'segment': m.get('segment'),
                'framing': None, 'meta': {'n_rows': int(len(df))}}

    m = validate(df, manifest)
    framing = m.get('framing') or _default_framing(m)
    if framing == 'snapshot':
        frame, groups, meta = frame_snapshot(df, m)
    else:
        # Group-aware CV is now wired through selection, shapley_utils and the
        # pipeline, so hazard is supported. CONTRACT: the caller MUST pass the
        # returned `groups` to run_pipeline(groups=...) (which threads it into
        # Stage 2/3/4) - otherwise the repeated entity rows leak across folds.
        frame, groups, meta = frame_hazard(df, m)

    if verbose:
        print('[panel_adapter] panel/%s (%s): %d entities -> %d modelling rows, '
              'event rate %.4f'
              % (framing, m.get('segment', '?'), meta.get('n_entities', -1),
                 len(frame), meta['event_rate']), flush=True)
    time_values = meta.pop('_time', None)   # row-aligned calendar time (for OOT)
    return {'frame': frame, 'target': m['target'], 'groups': groups,
            'time': time_values,
            'data_shape': 'panel', 'segment': m.get('segment'),
            'framing': framing, 'meta': meta}
