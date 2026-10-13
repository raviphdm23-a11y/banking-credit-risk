"""
missing_governance.py - deployment-time missing-value governance for SHARP.

Implements the two-tier control for blanks in a scored application
(METHODOLOGY v3 s9 #10):

  1. PRIMARY - validation gate. Columns declared MANDATORY at the start of the
     process must be present. A new application missing any mandatory field is
     INCOMPLETE and is not scored: it is routed to REJECT or REFER. You cannot
     assess risk on an absent essential field.

  2. FALLBACK - adverse assignment. When a score must still be produced
     (incomplete_policy='adverse_score'), a blank mandatory field is scored at
     that column's most-adverse observed WOE (worst case), so omitting it is
     maximally penalised rather than treated as neutral.

Also carries the omission-trap floor (floor_columns): applicant-influenceable
columns whose learned '__missing__' WOE was protective are floored to worst-case
so disclosing less cannot lower predicted risk.

Everything here is applied AT SCORING, on top of a model fitted on the true
(unfloored) WOE - so selection and the reported Stage 1-4 metrics are unchanged,
and complete/honest applicants are unaffected. Overrides are applied to the WOE
vector directly, which works identically for numeric and categorical columns
(it does not depend on how apply_bins routes a blank).

ASCII-only emitted strings (Windows cp1252 console).
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression

import binning as bn


def _worst_case_woe(woe_map):
    """Most-adverse observed WOE for a column (min over non-missing bins).

    Convention WOE = ln(%good/%bad): lower = higher risk. Includes '__other__'
    (a real rare/unseen bin) but excludes the '__missing__' sentinel.
    """
    others = [w for k, w in woe_map.items() if k != bn.MISSING_LABEL]
    return float(min(others)) if others else 0.0


class Scorer:
    """A fitted WOE-logistic scorer plus the missing-value governance overlay.

    .score(df) -> DataFrame with columns:
        decision      one of SCORE, SCORE_FLAGGED, REFER, REJECT
        probability   calibrated PD (NaN when gated, i.e. not scored)
        reason        short explanation for gated/flagged rows
    """

    def __init__(self, columns, encoder, coef, intercept, iso,
                 mandatory, floor, incomplete_policy, override_woe,
                 pd_floor=0.0003, pd_cap=0.999):
        self.columns = list(columns)
        self.encoder = encoder
        self.coef = np.asarray(coef, dtype=float)
        self.intercept = float(intercept)
        self.iso = iso
        self.mandatory = [c for c in mandatory if c in self.columns]
        self.floor = [c for c in floor if c in self.columns]
        self.incomplete_policy = incomplete_policy
        self.override_woe = dict(override_woe)   # col -> WOE used when that col is blank
        # Regulatory PD floor/ceiling (Basel CRE32.3): the reported PD is bounded at
        # scoring. Floor 0.03% (corporate/bank; retail mirrors - confirm per class);
        # cap non-defaulted strictly below a literal 100%. Fixes degenerate ~0% PD
        # that isotonic calibration can emit from a zero-default bin on small data.
        self.pd_floor = float(pd_floor)
        self.pd_cap = float(pd_cap)

    def _prep(self, df):
        r = pd.DataFrame(df).reindex(columns=self.columns).reset_index(drop=True)
        for c in self.columns:
            if self.encoder.bin_info_[c].get('kind') == 'categorical' \
               or r[c].dtype == object:
                r[c] = r[c].astype(object)
            else:
                r[c] = pd.to_numeric(r[c], errors='coerce').astype('float64')
        return r

    def score(self, df):
        r = self._prep(df)
        n = len(r)
        W = self.encoder.transform(r).values.astype(float).copy()
        miss = r.isna().to_numpy()
        colidx = {c: i for i, c in enumerate(self.columns)}

        decision = np.array(['SCORE'] * n, dtype=object)
        reason = np.array([''] * n, dtype=object)

        # --- PRIMARY: mandatory completeness gate ---
        mand_idx = [colidx[c] for c in self.mandatory]
        if mand_idx:
            mand_blank = miss[:, mand_idx]
            incomplete = mand_blank.any(axis=1)
            for i in np.where(incomplete)[0]:
                blanks = [self.mandatory[j] for j, b in enumerate(mand_blank[i]) if b]
                reason[i] = 'missing mandatory: ' + ', '.join(blanks)
            if self.incomplete_policy in ('reject', 'refer'):
                decision[incomplete] = self.incomplete_policy.upper()
            else:  # adverse_score: score it but flag, with worst-case overrides below
                decision[incomplete] = 'SCORE_FLAGGED'

        # --- Overrides for rows that WILL be scored ---
        scored = np.isin(decision, ['SCORE', 'SCORE_FLAGGED'])
        for c in set(self.floor) | set(self.mandatory):
            if c not in self.override_woe:
                continue
            j = colidx[c]
            rows = scored & miss[:, j]
            if rows.any():
                W[rows, j] = self.override_woe[c]
                # tag floor-driven flags (mandatory already tagged by the gate)
                for i in np.where(rows)[0]:
                    if decision[i] == 'SCORE':
                        decision[i] = 'SCORE_FLAGGED'
                        reason[i] = ('adverse floor: ' + c if not reason[i]
                                     else reason[i] + '; adverse floor: ' + c)

        logit = self.intercept + W @ self.coef
        praw = 1.0 / (1.0 + np.exp(-logit))
        pcal = self.iso.transform(praw)
        pcal = np.asarray(pcal, dtype=float)
        pcal = np.clip(pcal, self.pd_floor, self.pd_cap)   # Basel CRE32.3 PD floor/ceiling
        gated = np.isin(decision, ['REJECT', 'REFER'])
        pcal[gated] = np.nan

        return pd.DataFrame({'decision': decision, 'probability': pcal, 'reason': reason})


def build_scorer(df, target, columns, *, mandatory_columns=(), floor_columns=(),
                 incomplete_policy='reject', random_state=42,
                 pd_floor=0.0003, pd_cap=0.999):
    """Fit a WOE-logistic scorer on the true data and attach the governance overlay.

    incomplete_policy: 'reject' | 'refer' (PRIMARY gate - a blank mandatory field
        is not scored) or 'adverse_score' (FALLBACK - score the blank at worst case).
    Returns (Scorer, report_dict). The report records, per governed column, the
    worst-case WOE used and whether a learned missing bin existed.
    """
    if incomplete_policy not in ('reject', 'refer', 'adverse_score'):
        raise ValueError("incomplete_policy must be 'reject', 'refer' or 'adverse_score'")
    cols = list(columns)
    X = df[cols].copy()
    for c in cols:
        if X[c].dtype != object:
            X[c] = X[c].astype('float64')
    y = df[target].astype(int)
    enc = bn.WOEEncoder().fit(X, y)
    clf = LogisticRegression(penalty='l2', C=1.0, solver='lbfgs', max_iter=1000,
                             random_state=random_state).fit(enc.transform(X).values, y)
    # isotonic calibration map from 5-fold OOF on the fitted representation
    from sklearn.model_selection import StratifiedKFold
    oof = np.full(len(y), np.nan)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
    W_all = enc.transform(X).values
    for tr, te in skf.split(W_all, y):
        m = LogisticRegression(penalty='l2', C=1.0, solver='lbfgs', max_iter=1000,
                               random_state=random_state).fit(W_all[tr], y.iloc[tr])
        oof[te] = m.predict_proba(W_all[te])[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip').fit(oof, y.values)

    mandatory = [c for c in mandatory_columns if c in cols]
    floor = [c for c in floor_columns if c in cols]

    override = {}
    report = {'incomplete_policy': incomplete_policy, 'mandatory_columns': mandatory,
              'floor_columns': floor, 'not_selected_mandatory': [c for c in mandatory_columns
                                                                 if c not in cols],
              'training_mandatory_blanks': {}, 'columns': {}}
    for c in mandatory:
        worst = _worst_case_woe(enc.woe_map_[c])
        nblank = int(X[c].isna().sum()) if X[c].dtype != object else int(df[c].isna().sum())
        report['training_mandatory_blanks'][c] = nblank
        if incomplete_policy == 'adverse_score':
            override[c] = worst
        report['columns'][c] = {'role': 'mandatory', 'worst_case_woe': worst,
                                'had_training_missing_bin': bn.MISSING_LABEL in enc.woe_map_[c]}
    for c in floor:
        m = enc.woe_map_[c]
        worst = _worst_case_woe(m)
        learned = m.get(bn.MISSING_LABEL, worst)
        # A mandatory field is gated (reject/refer) when blank, so it is only
        # scored via an override under adverse_score; do not let the floor relax
        # a mandatory column's worst-case override.
        if c in mandatory and incomplete_policy == 'adverse_score':
            override[c] = min(override.get(c, worst), learned, worst)
        elif c not in mandatory:
            override[c] = min(learned, worst)
        entry = report['columns'].setdefault(c, {'role': 'floor'})
        entry.update({'worst_case_woe': worst, 'learned_missing_woe': learned,
                      'override_when_blank': override.get(c)})
        if entry.get('role') == 'mandatory':
            entry['role'] = 'mandatory+floor'

    scorer = Scorer(cols, enc, clf.coef_[0], float(clf.intercept_[0]), iso,
                    mandatory, floor, incomplete_policy, override,
                    pd_floor=pd_floor, pd_cap=pd_cap)
    report['pd_floor'] = float(pd_floor)
    report['pd_cap'] = float(pd_cap)
    return scorer, report


def governance_report_markdown(report):
    """Render the missing-value governance config as a report section."""
    if not report:
        return ''
    L = ['## Missing-value governance (mandatory gate + adverse fallback)', '']
    L.append('Incomplete-application policy: **%s** %s' % (
        report['incomplete_policy'],
        {'reject': '(blank mandatory field -> REJECT, not scored)',
         'refer': '(blank mandatory field -> REFER, not scored)',
         'adverse_score': '(blank mandatory field -> scored at worst-case WOE)'}[
            report['incomplete_policy']]))
    L.append('')
    if report.get('not_selected_mandatory'):
        L.append('**Warning:** declared-mandatory column(s) not in the selected model: `%s`. '
                 'The gate still applies as a data-quality rule, but these do not enter scoring.'
                 % '`, `'.join(report['not_selected_mandatory']))
        L.append('')
    if report['mandatory_columns']:
        L.append('| Mandatory column | Training blanks | Worst-case WOE | Had missing bin |')
        L.append('|---|---:|---:|---|')
        for c in report['mandatory_columns']:
            info = report['columns'].get(c, {})
            L.append('| `%s` | %d | %+.4f | %s |'
                     % (c, report['training_mandatory_blanks'].get(c, 0),
                        info.get('worst_case_woe', 0.0),
                        info.get('had_training_missing_bin', False)))
        L.append('')
    if report['floor_columns']:
        L.append('Omission-floor columns (applicant-influenceable): `%s`.'
                 % '`, `'.join(report['floor_columns']))
        L.append('')
    return '\n'.join(L)
