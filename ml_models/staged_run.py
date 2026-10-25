"""
Staged SHARP + AEGIS runner: one SHARP stage at a time, each followed by its gate.

The one-shot `v3_pipeline.run_pipeline` runs Stages 0-4 end to end and the gates are
walked afterwards. That wastes runs when an early gate changes direction, and lets the
signer see downstream numbers before deciding upstream gates. This runner enforces the
agreed process instead:

    stage0 -> G0 sealed -> stage1 -> G1 sealed -> stage2 -> G2 sealed
           -> stage3 -> G3 sealed -> stage4 -> G4 sealed -> (G5 deliverables) -> G5 -> GF

* A stage will not start until the previous gate is sealed (RuntimeError).
* A gate cannot be sealed before its stage has run, nor without a >=20-char rationale.
* Seal hash is the AEGIS chain hash: sha256(prev + f"{gate}|{option}|{signer}|{rationale}")[:8].
* A gate that changes direction -> `reopen(gate, reason)`: entries from that gate on are
  voided (kept in the audit trail), downstream state is discarded, and the stage that gate
  governs is re-run. G4/G5/GF changes need no SHARP re-run.
* Every stage calls the SAME primitives, with the same arguments and seed, as
  `run_pipeline`, so an all-approved staged run reproduces the one-shot run exactly
  (checked by `testing/test_staged_equivalence.py`; `run_pipeline` is left unchanged so
  sealed records stay reproducible).

Gate options are NOT authored here: `gate_evidence()` builds the evidence dict and
`aegis_gates.build_gate` emits the A/B/C options. `show_stage()` / `show_gate()` print the
FULL stage output and FULL options for the decision maker (no summaries).
"""
import hashlib
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), 'backend'))

import v3_pipeline as v3          # noqa: E402
import selection as sel           # noqa: E402
import shapley_utils as su        # noqa: E402
import aegis_gates as ag          # noqa: E402

STAGE_OF_GATE = {'G0': 0, 'G1': 1, 'G2': 2, 'G3': 3, 'G4': 4}
GATE_ORDER = ['G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'GF']
GRADE_ORDER = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C', 'D']
# Reporting convention for the G2 "borderline" watch list ONLY (midway between the
# pre-registered 0.80 confirmation minimum and 1.0). It decides nothing: the full players
# table is always shown, and the option set is merely extended with a watch-item option.
BORDERLINE_CONFIRM_FREQ = 0.90
MIN_RATIONALE = 20


class StagedRun:
    def __init__(self, df, target, name, outdir, tier='MEDIUM', *, groups=None,
                 time_values=None, learner='woe_logistic', value_fn='auc',
                 cluster_threshold=0.7, n_shadows=10, shadow_quantile=0.95,
                 confirm_frequency_min=0.80, n_samples=200, cv_repeats=1,
                 shapley_mode='auto', exact_max_players=15,
                 max_relative_gini_loss=0.05, alpha=0.05, run_model_checks=True,
                 random_state=42, shapley_row_subsample=None, oot_test_frac=0.3,
                 verbose=False):
        self.df = df.reset_index(drop=True)
        self.target, self.name, self.tier = target, name, tier
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.cfg = dict(learner=learner, value_fn=value_fn,
                        cluster_threshold=cluster_threshold, n_shadows=n_shadows,
                        shadow_quantile=shadow_quantile,
                        confirm_frequency_min=confirm_frequency_min,
                        n_samples=n_samples, cv_repeats=cv_repeats,
                        shapley_mode=shapley_mode, exact_max_players=exact_max_players,
                        max_relative_gini_loss=max_relative_gini_loss, alpha=alpha,
                        run_model_checks=run_model_checks, random_state=random_state,
                        shapley_row_subsample=shapley_row_subsample,
                        oot_test_frac=oot_test_frac)
        self.groups, self.time_values, self.verbose = groups, time_values, verbose
        self.genesis = 'GEN-%s_0' % name
        self.chain = []          # sealed entries (active)
        self.voided = []         # entries voided by reopen()
        self.state = {}          # stage outputs
        self._load_chain()

    # ------------------------------------------------------------------ chain
    def _chain_path(self):
        return os.path.join(self.outdir, 'chain.json')

    def _load_chain(self):
        if os.path.exists(self._chain_path()):
            d = json.load(open(self._chain_path(), encoding='utf-8'))
            self.chain, self.voided = d['chain'], d['voided']

    def _save_chain(self):
        json.dump({'genesis': self.genesis, 'chain': self.chain, 'voided': self.voided},
                  open(self._chain_path(), 'w', encoding='utf-8'), indent=1)

    def sealed(self, gate):
        return any(e['gate'] == gate for e in self.chain)

    def head(self):
        return self.chain[-1]['entry_hash'] if self.chain else self.genesis

    def seal(self, gate, option, rationale, signer=None):
        """Seal a gate decision. Enforces order, stage-done and the >=20-char rationale."""
        if gate not in GATE_ORDER:
            raise ValueError('unknown gate %r' % gate)
        i = GATE_ORDER.index(gate)
        if self.sealed(gate):
            raise RuntimeError('%s is already sealed; reopen() it to change it' % gate)
        if i > 0 and not self.sealed(GATE_ORDER[i - 1]):
            raise RuntimeError('cannot seal %s: %s is not sealed' % (gate, GATE_ORDER[i - 1]))
        if gate in STAGE_OF_GATE and ('stage%d' % STAGE_OF_GATE[gate]) not in self.state:
            raise RuntimeError('cannot seal %s: stage %d has not run'
                               % (gate, STAGE_OF_GATE[gate]))
        if len((rationale or '').strip()) < MIN_RATIONALE:
            raise ValueError('rationale must be >= %d characters' % MIN_RATIONALE)
        signer = signer or ag.signer_role(self.tier)
        prev = self.head()
        content = '%s|%s|%s|%s' % (gate, option, signer, rationale)
        h = hashlib.sha256((prev + content).encode()).hexdigest()[:8]
        entry = {'gate': gate, 'option': option, 'signer': signer, 'rationale': rationale,
                 'prev': prev, 'entry_hash': h}
        self.chain.append(entry)
        self._save_chain()
        return entry

    def reopen(self, gate, reason):
        """A gate changed direction: void it and everything after it; drop downstream state.
        Returns the stage number to re-run (None if no SHARP re-run is needed)."""
        if len((reason or '').strip()) < MIN_RATIONALE:
            raise ValueError('reason must be >= %d characters' % MIN_RATIONALE)
        i = GATE_ORDER.index(gate)
        keep = [e for e in self.chain if GATE_ORDER.index(e['gate']) < i]
        for e in self.chain:
            if GATE_ORDER.index(e['gate']) >= i:
                self.voided.append(dict(e, voided_because=reason))
        self.chain = keep
        self._save_chain()
        if gate in STAGE_OF_GATE:
            for k in [k for k in self.state if k[5:].isdigit()
                      and int(k[5:]) >= STAGE_OF_GATE[gate]]:
                del self.state[k]
            return STAGE_OF_GATE[gate]
        return None

    def _need(self, gate):
        if not self.sealed(gate):
            raise RuntimeError('%s must be sealed by its stakeholder before the next '
                               'SHARP stage may run' % gate)

    # ------------------------------------------------------------------ stages
    def stage0(self, eligibility_overrides=None, availability_overrides=None):
        s0 = v3.stage0_governance(self.df, self.target, eligibility_overrides,
                                  availability_overrides, verbose=self.verbose)
        self.state['stage0'] = {'s0': s0, 'eligibility_overrides': eligibility_overrides,
                                'availability_overrides': availability_overrides}
        return s0

    def stage1(self, excluded=()):
        """Screening. `excluded`: columns G0 removed (applied as eligibility overrides by
        re-running Stage 0 first, so call reopen('G0') + stage0(overrides) for that)."""
        self._need('G0')
        s0 = self.state['stage0']['s0']
        c = self.cfg
        mc = (lambda d, t, col: v3.single_column_model_check(
            d, t, col, learner=c['learner'], random_state=c['random_state'],
            groups=self.groups)) if c['run_model_checks'] else None
        s1_table, candidates = v3.stage1_screen(self.df, self.target, tags=s0['tags'],
                                                model_check_fn=mc, verbose=self.verbose)
        dropped = [x for x in candidates if x in set(excluded)]
        candidates = [x for x in candidates if x not in set(excluded)]
        # Sufficiency (Riley): the anticipated C-statistic comes from ONE out-of-fold fit of
        # all Stage-1 candidates (cheap). The one-shot records used the full-model C-stat
        # from Stage 3 (confirmed players only); here Stage 2/3 do not exist yet.
        y = self.df[self.target]
        oof = sel.oof_predictions(self.df[candidates], y, candidates,
                                  learner=c['learner'], random_state=c['random_state'],
                                  groups=self.groups)
        from sklearn.metrics import roc_auc_score
        cstat = float(roc_auc_score(y, oof))
        import riley_minsize as rl
        prev = float(y.mean())
        riley = rl.riley_min_n(prev, len(candidates), cstat=cstat)
        self.state['stage1'] = {'s1_table': s1_table, 'candidates': candidates,
                                'dropped_by_gate': dropped, 'cstat_all_candidates': cstat,
                                'riley': riley, 'prev': prev}
        return s1_table, candidates

    def stage2(self, excluded_players=()):
        self._need('G1')
        c, s1 = self.cfg, self.state['stage1']
        X, y = self.df[s1['candidates']], self.df[self.target]
        s2 = su.shapley_importance(
            X, y, learner=c['learner'], value_fn=c['value_fn'], cv_repeats=c['cv_repeats'],
            cluster_threshold=c['cluster_threshold'], n_shadows=c['n_shadows'],
            shadow_quantile=c['shadow_quantile'],
            confirm_frequency_min=c['confirm_frequency_min'], n_samples=c['n_samples'],
            random_state=c['random_state'], mode=c['shapley_mode'],
            exact_max_players=c['exact_max_players'],
            progress_every=(50 if self.verbose else 0), cv_groups=self.groups,
            row_subsample=c['shapley_row_subsample'])
        self.state['stage2'] = {'s2': s2}
        return s2

    def _ranked(self):
        s2 = self.state['stage2']['s2']
        dropped = set(self.state.get('stage3_excluded_players', ()))
        return [p for p in su.ranked_players(s2, confirmed_only=True) if p not in dropped]

    def stage3(self, excluded_players=()):
        self._need('G2')
        c, s1, s2 = self.cfg, self.state['stage1'], self.state['stage2']['s2']
        self.state['stage3_excluded_players'] = tuple(excluded_players)
        ranked = self._ranked()
        player_cols = {p: str(s2['players'].loc[p, 'columns']).split(',')
                       for p in s2['players'].index}
        X, y = self.df[s1['candidates']], self.df[self.target]
        curve, extras = sel.parsimony_curve(
            X, y, ranked, player_cols, learner=c['learner'],
            random_state=c['random_state'], progress=self.verbose, groups=self.groups)
        decision = sel.select_parsimonious(
            curve, max_relative_gini_loss=c['max_relative_gini_loss'], alpha=c['alpha'])
        selected = []
        if decision['tolerance_met']:
            for p in decision['selected_players']:
                selected.extend(player_cols[p])
        self.state['stage3'] = {'ranked': ranked, 'player_cols': player_cols,
                                'curve': curve, 'extras': extras, 'decision': decision,
                                'selected_columns': selected}
        return curve, decision

    def stage4(self):
        self._need('G3')
        c, s3 = self.cfg, self.state['stage3']
        selected, decision, extras = s3['selected_columns'], s3['decision'], s3['extras']
        tags = self.state['stage0']['s0']['tags']
        df, target, rs = self.df, self.target, c['random_state']
        retained = selected or [x for p in s3['ranked'] for x in s3['player_cols'][p]]
        import feature_governance as fg
        offenders = fg.warn_on_retained_ineligible(retained, tags, context=self.name)
        avail = fg.availability_warnings(retained, tags, context=self.name)
        calib = v3._calibrate(df, target, selected, random_state=rs,
                              groups=self.groups) if selected else None
        backtest = oot = None
        if selected:
            import calibration_gof as cgof
            import rating_masterscale as rms
            k_sel = len(decision.get('selected_players') or [])
            oof_sel = extras.get('oof_by_k', {}).get(k_sel, extras.get('oof_full'))
            if oof_sel is not None:
                backtest = cgof.deployment_backtest(
                    np.asarray(df[target].values), np.asarray(oof_sel),
                    lambda pd_: rms.pd_to_grade(pd_)['grade'], GRADE_ORDER,
                    groups=self.groups, random_state=rs)
            if self.time_values is not None:
                import oot_validation as ov
                curve = s3['curve']
                row = curve[curve['k'] == k_sel]
                in_gini = float(row['gini'].iloc[0]) if len(row) else None
                oot = ov.out_of_time_validation(
                    df[selected], df[target].values, selected, self.time_values,
                    groups=self.groups, learner=c['learner'], test_frac=c['oot_test_frac'],
                    grade_fn=lambda pd_: rms.pd_to_grade(pd_)['grade'],
                    grade_order=GRADE_ORDER, in_time_gini=in_gini, random_state=rs)
        self.state['stage4'] = {'calibration': calib, 'backtest': backtest, 'oot': oot,
                                'ineligible_retained': offenders,
                                'availability_flags': avail}
        return self.state['stage4']

    def final_report(self):
        """The same markdown report the one-shot pipeline writes (needs stages 0-4)."""
        s0, s1, s3, s4 = (self.state[k] for k in ('stage0', 'stage1', 'stage3', 'stage4'))
        return v3.build_report(
            self.name, self.df, self.target, s0['s0'], s1['s1_table'], s1['candidates'],
            self.state['stage2']['s2'], s3['curve'], s3['decision'], s3['selected_columns'],
            s4['ineligible_retained'], s4['availability_flags'], s4['calibration'],
            learner=self.cfg['learner'], value_fn=self.cfg['value_fn'],
            missing_floor=None, governance=None, backtest=s4['backtest'], oot=s4['oot'])

    # ------------------------------------------------------------ gate evidence
    def gate_evidence(self, gate, **extra):
        y, n = self.df[self.target], len(self.df)
        events = int(y.sum())
        if gate == 'G0':
            s0 = self.state['stage0']['s0']
            return {'tier': self.tier, 'n_rows': n, 'event_rate': round(events / n, 4),
                    'history_years': None, 'excluded': extra.get('excluded', []),
                    'borderline_exclusions': [], 'label_integrity': True,
                    'epv_pool': round(events / (self.df.shape[1] - 1), 1)}
        if gate == 'G1':
            s1 = self.state['stage1']
            t = s1['s1_table']
            top = t.sort_values('iv_woe', ascending=False).iloc[0]
            return {'tier': self.tier, 'n_pass': len(s1['candidates']),
                    'n_pool': self.df.shape[1] - 1,
                    'epv': round(events / (self.df.shape[1] - 1), 1),
                    'riley_req': s1['riley']['N_required'], 'riley_avail': n,
                    'dominant_feature': str(top.name),
                    'dominant_iv': round(float(top['iv_woe']), 2)}
        if gate == 'G2':
            s2 = self.state['stage2']['s2']
            pl = s2['players']
            real = pl[~pl['is_shadow']]
            conf = real[real['importance_confirmed']]
            bar = float(s2['shadow_bar'])
            weakest = float(conf['shapley'].min()) / bar if len(conf) else 0.0
            border = [str(i) for i in conf.index
                      if float(conf.loc[i, 'confirmation_frequency']) < BORDERLINE_CONFIRM_FREQ]
            return {'tier': self.tier, 'n_players': len(real), 'n_confirmed': len(conf),
                    'shadow_bar': bar, 'weakest_mult': round(weakest, 2),
                    'estimator': s2['info']['mode'],
                    'borderline_players': border}
        if gate == 'G3':
            s3 = self.state['stage3']
            d, curve = s3['decision'], s3['curve']
            kf = int(curve['k'].max())
            return {'tier': self.tier, 'k_selected': int(d['selected_k']), 'k_full': kf,
                    'cols_selected': int(d['n_columns']), 'gini_sel': round(d['gini'], 4),
                    'gini_full': round(float(s3['extras']['full_model']['gini']), 4),
                    'delong_p': round(float(d['delong_p']), 4),
                    'rel_loss': round(100 * float(d['relative_gini_loss']), 2),
                    'full_within_tol': bool(d['tolerance_met'])}
        if gate == 'G4':
            s3, s4 = self.state['stage3'], self.state['stage4']
            bt, curve = s4['backtest'], s3['curve']
            k_sel = int(s3['decision']['selected_k'])
            auc = float(curve.loc[curve['k'] == k_sel, 'auc'].iloc[0])
            tb = bt['table']
            sparse = [str(r['grade']) for _, r in tb.iterrows()
                      if int(r['n']) < 30] if hasattr(tb, 'iterrows') else []
            hl = bt['hl'].get(10) or next(iter(bt['hl'].values()))
            hl_p = hl.get('p_adj', hl.get('p_value'))
            return {'tier': self.tier, 'auc': round(auc, 4),
                    'hl_p': None if hl_p is None else round(float(hl_p), 4),
                    'grade_backtest_pass': bt['grades_passed'] == bt['grades_total'],
                    'grades_total': bt['grades_total'], 'grades_passed': bt['grades_passed'],
                    'sparse_grades': sparse, 'air': extra.get('air', {}),
                    'air_min': extra.get('air_min')}
        raise ValueError('G5/GF evidence is supplied by the caller (deliverables)')

    def build_gate(self, gate, **extra):
        ev = extra.pop('evidence', None) or self.gate_evidence(gate, **extra)
        return ag.build_gate(gate, ev), ev

    # ----------------------------------------------------------------- display
    def show_gate(self, gate, **extra):
        """FULL gate card: question, recommendation, flags and every option in full."""
        gd, ev = self.build_gate(gate, **extra)
        out = ['=' * 78, '%s - %s   [tier %s | signer: %s]' % (gd.gate, gd.name, gd.tier, gd.signer),
               'Q: ' + gd.question, '-' * 78, 'EVIDENCE: ' + json.dumps(ev, default=str),
               'MACHINE RECOMMENDATION: ' + gd.recommendation]
        if gd.flags:
            out.append('FLAGS: ' + ' | '.join(gd.flags))
        out.append('-' * 78)
        for o in gd.options:
            out += ['[%s] %s  (%s)%s' % (o.label, o.option, o.kind,
                                         '  <== RECOMMENDED' if o.recommended else ''),
                    '     data     : ' + o.data, '     rationale: ' + o.rationale,
                    '     benefits : ' + o.benefits, '     risks    : ' + o.risks,
                    '     residual : ' + o.residual, '']
        if gd.single_viable:
            out.append('** single viable option (anti-strawman): escalate-for-confirmation **')
        return '\n'.join(out)

    def show_stage(self, n):
        """FULL stage output as markdown tables (nothing truncated)."""
        st = self.state['stage%d' % n]
        if n == 0:
            s0 = st['s0']
            import feature_governance as fg
            txt = fg.governance_table_markdown(s0['tags'])
            txt += '\n\nSentinel values detected: %s' % json.dumps(
                {c: list(v) for c, v in s0['sentinels'].items()}, default=str)
            txt += '\nSentinel leakage candidates: %s' % (
                json.dumps(s0['sentinel_lift'], default=str) or 'none')
            return txt
        if n == 1:
            show = ['iv_woe', 'iv_q5', 'iv_q10', 'iv_q20', 'binning_sensitive',
                    'shape_nonmonotonic', 'cramers_v_descriptive', 'min_expected',
                    'gate_ok', 'escalation', 'mann_whitney_p', 'passes_screen']
            t = st['s1_table']
            return (v3._md_table(t[[c for c in show if c in t.columns]].round(4)) +
                    '\n\nCandidates passing Stage 1: %d. Riley minimum N (P=%d, C-stat of '
                    'all-candidate OOF model=%.4f, prevalence=%.4f): %s'
                    % (len(st['candidates']), len(st['candidates']),
                       st['cstat_all_candidates'], st['prev'], json.dumps(st['riley'])))
        if n == 2:
            s2 = st['s2']
            p = s2['players'].copy()
            p['player'] = p.index
            cols = ['n_columns', 'is_shadow', 'shapley', 'mc_se', 'confirmation_frequency',
                    'importance_confirmed', 'diag_bh_p', 'diag_cohens_d']
            return (v3._md_table(p[[c for c in cols if c in p.columns]].round(5),
                                 index_name='player') +
                    '\n\nShadow bar (95th pct of shadow players): %.5f. Mode: %s.'
                    % (s2['shadow_bar'], s2['info']['mode']))
        if n == 3:
            return sel.curve_markdown(st['curve'], st['decision'])
        if n == 4:
            import calibration_gof as cgof
            parts = ['Calibration: ' + json.dumps(st['calibration'], default=str)]
            if st['backtest']:
                parts.append(cgof.backtest_markdown(st['backtest']))
            if st['oot']:
                import oot_validation as ov
                parts.append(ov.oot_markdown(st['oot']))
            return '\n\n'.join(parts)

    # -------------------------------------------------------------- persistence
    def save(self):
        with open(os.path.join(self.outdir, 'state.pkl'), 'wb') as f:
            pickle.dump({'state': self.state, 'cfg': self.cfg}, f)

    def load(self):
        p = os.path.join(self.outdir, 'state.pkl')
        if os.path.exists(p):
            d = pickle.load(open(p, 'rb'))
            self.state = d['state']
        return self
