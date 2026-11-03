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
import regime_registry as rr      # noqa: E402
import rbi_checks as rbc          # noqa: E402

STAGE_OF_GATE = {'G0': 0, 'G1': 1, 'G2': 2, 'G3': 3, 'G4': 4}
GATE_ORDER = ['G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'GF']
GRADE_ORDER = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C', 'D']
# Reporting convention for the G2 "borderline" watch list ONLY (midway between the
# pre-registered 0.80 confirmation minimum and 1.0). It decides nothing: the full players
# table is always shown, and the option set is merely extended with a watch-item option.
BORDERLINE_CONFIRM_FREQ = 0.90
MIN_RATIONALE = 20
# Look-ahead review (reporting only): definition phrases that MAY refer to information after
# the statement date. A hit prompts a human to read the definition; it excludes nothing.
LOOKAHEAD_PATTERN = r'\b(in \d+ years?|next|following|future|forecast|subsequent|after)\b'
# Checklist metadata lives in regime_registry.py (R1-R14 identical to the literals that used to be here, frozen in
# testing/test_rbi_regime.py; R15-R20 are the Indian RBI pack).
MUST_HAVE_ROWS = tuple(rr.must_have_rows())
CHECKLIST_GATE = rr.checklist_gate()
# Rows R11-R14 apply only if their regime is declared binding at G0 (AEGIS section 8: "the MAC records
# which regime(s) bind a given model at G0"). R1-R10 are treated as binding whatever the regime
# (Basel/EBA credit-risk criteria and generic model-risk governance).
REGIME_OF = rr.regime_of()
# Rows R15-R20 (Indian RBI pack) are derived only when the Indian regime keys are declared at G0.
IN_REGIME_OF = rr.in_regime_of()
# What closes a PARTIAL / GAP row, and who owns it. Generic actions only - no numbers.
CLOSING_ACTION = rr.closing_actions()


def missingness_scan(df, target, alpha=0.05):
    """Per column with blanks: share blank, event rate among blanks vs base, Fisher exact p.
    REPORT ONLY - no column is excluded or flagged by a threshold here; the table is sorted
    by p so the strongest blank-vs-outcome associations are on top. `bonferroni_p` is
    alpha / number of columns tested, shown as a multiple-testing reference."""
    from scipy.stats import fisher_exact
    y = df[target].astype(int)
    base = float(y.mean())
    rows = []
    for c in df.columns:
        if c == target:
            continue
        m = df[c].isna()
        nb = int(m.sum())
        if nb == 0:
            continue
        ev_b, ev_o = int(y[m].sum()), int(y[~m].sum())
        p = float(fisher_exact([[ev_b, nb - ev_b], [ev_o, int((~m).sum()) - ev_o]])[1])
        rows.append({'column': c, 'n_blank': nb, 'pct_blank': round(100 * nb / len(df), 2),
                     'events_in_blank': ev_b,
                     'event_rate_blank': round(ev_b / nb, 4),
                     'event_rate_filled': round(ev_o / max(1, len(df) - nb), 4),
                     'lift_vs_base': round(ev_b / nb / base, 2) if base > 0 else None,
                     'fisher_p': p})
    t = pd.DataFrame(rows)
    if len(t):
        t = t.sort_values('fisher_p').reset_index(drop=True)
        t['bonferroni_p'] = alpha / max(1, len(df.columns) - 1)
        t['below_bonferroni'] = t['fisher_p'] < t['bonferroni_p']
    return t


def lookahead_scan(dictionary):
    """dictionary: {column: definition text}. Returns the columns whose definition matches
    LOOKAHEAD_PATTERN (reporting only; a human reads each and records a verdict)."""
    import re
    out = {}
    for c, d in (dictionary or {}).items():
        m = re.findall(LOOKAHEAD_PATTERN, str(d), flags=re.I)
        if m:
            out[c] = {'definition': str(d), 'matched': sorted(set(x.lower() for x in m))}
    return out


def acceptance_coverage(df, target, selected, mandatory_columns=(), incomplete_policy='refer',
                        random_state=42, groups=None):
    """Score every row through the deployable scorer and report which scoring controls the
    data actually exercises: PD floor / cap bound, referrals, PD range of scored firms.
    A control that no row triggers is reported NOT EXERCISED (the acceptance pack cannot
    demonstrate it from this data)."""
    import missing_governance as mg
    sc, _ = mg.build_scorer(df, target, selected, mandatory_columns=list(mandatory_columns),
                            incomplete_policy=incomplete_policy,
                            random_state=random_state, groups=groups)
    r = sc.score(df[selected])
    scored = r['decision'].isin(['SCORE', 'SCORE_FLAGGED'])
    p = r.loc[scored, 'probability'].astype(float)
    eps = 1e-12
    out = {'n_rows': int(len(df)), 'n_scored': int(scored.sum()),
           'n_referred_or_rejected': int((~scored).sum()),
           'pd_min_scored': float(p.min()), 'pd_max_scored': float(p.max()),
           'floor': float(sc.pd_floor), 'cap': float(sc.pd_cap),
           'n_at_floor': int((p <= sc.pd_floor + eps).sum()),
           'n_at_cap': int((p >= sc.pd_cap - eps).sum())}
    out['floor_exercised'] = out['n_at_floor'] > 0
    out['cap_exercised'] = out['n_at_cap'] > 0
    out['refer_exercised'] = (out['n_referred_or_rejected'] > 0) if mandatory_columns else None
    out['not_exercised'] = [k for k, v in (('PD floor', out['floor_exercised']),
                                           ('PD cap', out['cap_exercised']),
                                           ('mandatory-field gate', out['refer_exercised']))
                            if v is False]
    return out


class StagedRun:
    def __init__(self, df, target, name, outdir, tier='MEDIUM', *, groups=None,
                 time_values=None, learner='woe_logistic', value_fn='auc',
                 cluster_threshold=0.7, n_shadows=10, shadow_quantile=0.95,
                 confirm_frequency_min=0.80, n_samples=200, cv_repeats=1,
                 shapley_mode='auto', exact_max_players=15,
                 max_relative_gini_loss=0.05, alpha=0.05, run_model_checks=True,
                 random_state=42, shapley_row_subsample=None, oot_test_frac=0.3,
                 verbose=False, roles=None, history_years=None, dictionary=None,
                 exploratory=False, regimes=None, live_use=True, india=None):
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
        # roles: {signing role: person}; history_years: observation window of the PD data
        # (None = not verifiable from the file); dictionary: {column: definition text}
        self.roles, self.history_years, self.dictionary = roles, history_years, dictionary
        # exploratory: stages run without waiting for a signed gate (used to compute a scorecard
        # for comparison). Nothing is sealed, and the scorecard says so. Never use for a governed run.
        self.exploratory = exploratory
        # regimes: {regime key: {'binding': bool, 'reason': str}} for the keys in REGIME_OF; None = not
        # declared (R11-R14 then read NOT ASSESSED). Declare at G0; the signer confirms it.
        self.regimes = regimes
        # live_use=False marks a research benchmark with no use in decisions, so the use test (R2) cannot be evidenced
        self.live_use = live_use
        # india: the Indian (RBI) pack's declared facts, e.g. intended_use, exposure_materiality, complexity, autonomy,
        # tier_justification, mrmf_in_place, validation_report_months, retention_years, dependencies,
        # explainability_threshold, monitoring_plan, override_path, human_review_rate. None = pack not declared.
        self.india = india
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

    def seal(self, gate, option, rationale, signer=None, person=None,
             rationale_by='unspecified'):
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
        # person / rationale_by are recorded but NOT hashed, so the hash format is unchanged.
        # rationale_by: 'signer' (the human wrote it) | 'assistant-drafted' (the human chose
        # the option; the assistant drafted the text and showed it before sealing).
        entry = {'gate': gate, 'option': option, 'signer': signer, 'rationale': rationale,
                 'prev': prev, 'entry_hash': h,
                 'person': person or (self.roles or {}).get(signer),
                 'rationale_by': rationale_by}
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
        if not self.exploratory and not self.sealed(gate):
            raise RuntimeError('%s must be sealed by its stakeholder before the next '
                               'SHARP stage may run' % gate)

    # ------------------------------------------------------------------ stages
    def stage0(self, eligibility_overrides=None, availability_overrides=None):
        s0 = v3.stage0_governance(self.df, self.target, eligibility_overrides,
                                  availability_overrides, verbose=self.verbose)
        self.state['stage0'] = {'s0': s0, 'eligibility_overrides': eligibility_overrides,
                                'availability_overrides': availability_overrides,
                                'missingness': missingness_scan(self.df, self.target,
                                                                self.cfg['alpha']),
                                'lookahead': lookahead_scan(self.dictionary)}
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
            progress_every=self.cfg.get('shapley_progress_every', 50 if self.verbose else 0),
            checkpoint_path=os.path.join(self.outdir, 'shapley_checkpoint.json'), cv_groups=self.groups,
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
        player_cols = {p: su.player_columns(s2['players'], p)
                       for p in s2['players'].index}
        X, y = self.df[s1['candidates']], self.df[self.target]
        curve, extras = sel.parsimony_curve(
            X, y, ranked, player_cols, learner=c['learner'],
            random_state=c['random_state'], progress=self.cfg.get('parsimony_progress', self.verbose), groups=self.groups)
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

    # ------------------------------------------------------ sufficiency (EPV, Riley)
    def sufficiency(self):
        """EPV and Riley minimum N on every basis the run has reached. Shown at G1, G2, G3
        (and again wherever the column set changes). Pure arithmetic on recorded numbers."""
        import riley_minsize as rl
        y = self.df[self.target]
        events, n, prev = int(y.sum()), len(self.df), float(y.mean())
        rows = []

        def add(stage, basis, P, cstat, governing=False):
            r = rl.riley_min_n(prev, int(P), cstat=cstat)
            rows.append({'stage': stage, 'basis': basis, 'governing': governing, 'P': int(P),
                         'EPV': round(events / P, 1), 'c_stat': round(cstat, 4),
                         'B1': r['n_B1_risk'], 'B3': r['n_B3_shrinkage'],
                         'B4': r['n_B4_optimism'], 'N_required': r['N_required'],
                         'N_required_default_r2': rl.riley_min_n(prev, int(P), r2cs=0.15 * rl.max_r2cs(prev))['N_required'],
                         'available': n, 'margin': round(n / r['N_required'], 2),
                         'riley_met': n >= r['N_required']})
        if 'stage1' in self.state:
            s1 = self.state['stage1']
            # GOVERNING basis (convention of 2026-10-25): the candidate pool = every column that
            # entered Stage 1 after the outcome-blind Stage-0 eligibility step. Riley's P is the
            # number of candidate parameters considered before data-driven selection, so a count
            # reduced by IV screening, Shapley or parsimony (all outcome-dependent) cannot
            # lower the requirement. The C-statistic is the out-of-fold AUC of the Stage-1
            # candidate model (the pool model itself is never fitted).
            add('G1', 'candidate pool (Stage-0 eligible, outcome-blind)', len(s1['s1_table']),
                s1['cstat_all_candidates'], governing=True)
            add('G1', 'after IV screening (outcome-dependent)', len(s1['candidates']),
                s1['cstat_all_candidates'])
            if 'stage2' in self.state:
                pl = self.state['stage2']['s2']['players']
                nconf = int(((~pl['is_shadow']) & pl['importance_confirmed']).sum())
                add('G2', 'confirmed players (correlated columns grouped)', nconf,
                    s1['cstat_all_candidates'])
        if 'stage3' in self.state and self.state['stage3']['selected_columns']:
            s3 = self.state['stage3']
            k = int(s3['decision']['selected_k'])
            auc = float(s3['curve'].loc[s3['curve']['k'] == k, 'auc'].iloc[0])
            add('G3', 'selected model (after data-driven selection)', len(s3['selected_columns']), auc)
        return pd.DataFrame(rows)

    # ------------------------------------------------------------ role independence
    def role_report(self):
        """Who holds which signing role. R7/R8 need effective challenge, so a person holding
        more than one role is surfaced at G0, not discovered at GF."""
        if not self.roles:
            return {'declared': False, 'multi_role_persons': None,
                    'note': 'role holders not declared'}
        by = {}
        for role, who in self.roles.items():
            by.setdefault(who, []).append(role)
        multi = {w: r for w, r in by.items() if len(r) > 1}
        return {'declared': True, 'roles': dict(self.roles), 'multi_role_persons': multi,
                'note': ('one person holds several roles (%s)' % '; '.join('%d roles: %s' % (len(r), ', '.join(r)) for w, r in multi.items())) if multi
                else 'each role held by a different person'}

    # ------------------------------------------------------------ Indian (RBI) pack
    def _in_active(self):
        """True when the Indian regime keys were declared at G0 (standard_run.default_regimes does it for jurisdiction IN)."""
        return bool(self.regimes) and any(k in self.regimes for k in rr.IN_REGIME_KEYS)

    def tier_proposal(self):
        """RBI anti-dilution tier proposal (Draft 19-20, 52) from the declared materiality, complexity and autonomy.
        None when no materiality was declared. It only proposes; the G0 signer adopts it or records a justification."""
        p = self.india or {}
        if not p.get('exposure_materiality'):
            return None
        return ag.propose_tier(p['exposure_materiality'], p.get('complexity', 'LOW'), p.get('autonomy', 'LOW'))

    def record_rbi_check(self, name, result):
        """Store a reporting-only diagnostic from rbi_checks (row_order, seed_stability, feature_drift, segments,
        rolling_oot, label_lag, sign_audit, perturbation, outlier, benchmark, material_change). Decides nothing."""
        self.state.setdefault('rbi_checks', {})[name] = result
        return result

    def write_inventory_card(self, observations=None):
        """Model inventory card (Draft 21-24, FREE-AI Rec 23): owners, developers, validators, approvers, tier, intended
        use, dependencies, key observations, retention. Written next to the chain and kept in the run state."""
        import datetime
        p = self.india or {}
        cl = self.checklist()
        obs = observations or ['%s %s: %s' % (r['id'], r['status'], r['note'][:160]) for r in cl
                               if r['status'] in ('PARTIAL', 'GAP')]
        card = {'model': self.name, 'tier': self.tier, 'tier_proposal': self.tier_proposal(),
                'intended_use': p.get('intended_use'), 'learner': self.cfg['learner'],
                'roles': dict(self.roles or {}), 'role_note': self.role_report()['note'],
                'dependencies': list(p.get('dependencies') or []), 'retention_years': p.get('retention_years'),
                'key_observations': obs, 'regime_pack': rr.provenance(),
                'written': datetime.date.today().isoformat(),
                'note': 'Inventory fields follow RBI Draft para 22; this card is evidence for R17, not an RBI filing.'}
        path = os.path.join(self.outdir, 'inventory_card.json')
        json.dump(card, open(path, 'w', encoding='utf-8'), indent=1, default=str)
        self.state['inventory_card'] = path
        return card

    def _in_rows(self, rows, strict):
        """Derive R15-R20 from the declared india facts and the recorded rbi_checks. Earlier reading: conditions only.
        Regulatory-use reading (strict): R15 and R16 are marked must-have, so a gap blocks (decision of 3 Nov 2026)."""
        p = self.india or {}
        chk = self.state.get('rbi_checks', {})
        must = set(rr.must_have_rows())

        def put(r, status, note):
            meta = rr.row(r)
            rows[r] = {'id': r, 'status': status, 'note': note, 'gate': meta['gate'],
                       'must_have': (r in must) or (strict and meta['must_have_strict']),
                       'source': 'derived', 'legal_status': meta['legal_status']}

        def inactive(r):
            key = IN_REGIME_OF[r]
            if not self.regimes or key not in self.regimes:
                rows[r] = {'id': r, 'status': 'NOT ASSESSED', 'must_have': False, 'gate': rr.row(r)['gate'], 'source': 'derived',
                           'note': 'regime %s not declared at G0' % key}
                return True
            if not self.regimes[key].get('binding'):
                rows[r] = {'id': r, 'status': 'N/A', 'must_have': False, 'gate': rr.row(r)['gate'], 'source': 'derived',
                           'note': 'not binding: %s' % self.regimes[key].get('reason', 'declared not binding')}
                return True
            return False
        rank = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}

        # R15 - framework, tier, use statement (Draft 9-20, 26)
        if not inactive('R15'):
            tp = self.tier_proposal()
            issues, block = [], False
            if not (p.get('intended_use') or '').strip():
                issues.append('no written intended-use statement (Draft 26(1))')
                block = True
            if not p.get('mrmf_in_place'):
                issues.append('no board-approved model risk framework referenced (Draft 9-11)')
            if tp is None:
                issues.append('no materiality declared, so the anti-dilution tier proposal (Draft 20) cannot be checked')
            elif rank[self.tier] < rank[tp['proposed']]:
                if len((p.get('tier_justification') or '').strip()) >= MIN_RATIONALE:
                    issues.append('tier %s is below the proposed %s; justification recorded' % (self.tier, tp['proposed']))
                else:
                    issues.append('tier %s is below the anti-dilution proposal %s and no justification is recorded (Draft 20)'
                                  % (self.tier, tp['proposed']))
                    block = True
            put('R15', 'SATISFIED' if not issues else ('GAP' if (strict and block) else 'PARTIAL'),
                '; '.join(issues) if issues else 'use statement, framework and tier %s consistent with the proposal' % self.tier)

        # R16 - independent validation and report (Draft 7(8), 15, 29-33)
        if not inactive('R16'):
            rr_ = self.role_report()
            months = p.get('validation_report_months')
            if not rr_['declared']:
                put('R16', 'PARTIAL', 'role holders not declared')
            elif rr_['multi_role_persons']:
                put('R16', 'GAP' if strict else 'PARTIAL',
                    'no validator independent of development, ownership and use (Draft 7(8)): ' + rr_['note'])
            elif months is None:
                put('R16', 'PARTIAL', 'roles are separate, but no validation report has been placed before the committee yet (Draft 33)')
            elif months > 3:
                put('R16', 'PARTIAL', 'validation report reached the committee after %s months; Draft 33 asks for three' % months)
            else:
                put('R16', 'SATISFIED', 'independent validator; report placed before the committee within %s months' % months)

        # R17 - inventory, documentation, dependencies, retention (Draft 21-24, 57)
        if not inactive('R17'):
            issues = []
            if not self.state.get('inventory_card'):
                issues.append('inventory card not written (Draft 21-22)')
            ret = p.get('retention_years')
            if ret is None or ret < 10:
                issues.append('retention not stated as at least ten years after decommissioning (Draft 23-24)')
            if not p.get('dependencies'):
                issues.append('upstream dependencies not listed (Draft 22)')
            put('R17', 'SATISFIED' if not issues else 'PARTIAL',
                '; '.join(issues) if issues else 'inventory card written; retention %s years; dependencies listed' % ret)

        # R18 - Draft para 54(1)-(7): seven sub-items, each reported
        if not inactive('R18'):
            subs = []
            thr = (p.get('explainability_threshold') or '').strip()
            woe = self.cfg['learner'] == 'woe_logistic'
            subs.append(('54(1) explainability', 'SATISFIED' if (woe and thr) else 'PARTIAL',
                         'additive WOE reason codes' + ('' if woe else ' not available for this learner') +
                         ('; threshold declared' if thr else '; no explainability threshold declared')))
            subs.append(('54(2) hallucination', 'N/A', 'not a generative model'))
            seg = chk.get('segments')
            if seg is None:
                subs.append(('54(3) fairness', 'PARTIAL', 'no group assessment recorded'))
            elif seg.get('passes_four_fifths') is False:
                subs.append(('54(3) fairness', 'PARTIAL', 'favourable-decision ratio %.2f < %.2f across segments (indicative cutoff)'
                             % (seg['ratio'], rbc.FOUR_FIFTHS)))
            else:
                thin = seg.get('thin_segments') or []
                subs.append(('54(3) fairness', 'SATISFIED' if not thin else 'PARTIAL',
                             'segment ratio %s%s' % ('n/a' if seg.get('ratio') is None else '%.2f' % seg['ratio'],
                                                     ('; thin segments: ' + ', '.join(thin)) if thin else '')))
            oot = (self.state.get('stage4') or {}).get('oot')
            if not oot or not oot.get('ok'):
                subs.append(('54(4) generalisation', 'PARTIAL', 'validation is cross-validation only; no out-of-time test'))
            else:
                mcx = rbc.material_change(oot=oot)
                subs.append(('54(4) generalisation', 'PARTIAL' if mcx['triggered'] else 'SATISFIED',
                             '; '.join(mcx['triggered']) if mcx['triggered'] else 'out-of-time discrimination within the material-change criterion'))
            s1 = self.state.get('stage1')
            if s1 is None:
                subs.append(('54(5) spurious correlation', 'PARTIAL', 'Stage 1 not run'))
            else:
                t = s1['s1_table']
                n_big = int((t['iv_woe'] > 0.5).sum()) if 'iv_woe' in t.columns else 0
                lag = chk.get('label_lag')
                subs.append(('54(5) spurious correlation', 'PARTIAL' if n_big else 'SATISFIED',
                             ('%d column(s) with IV above 0.5 (unusually strong; leakage or label mirroring not excluded)' % n_big
                              if n_big else 'no column with IV above 0.5') + ('; label-lag sensitivity recorded' if lag is not None else '')))
            roi, ss = chk.get('row_order'), chk.get('seed_stability')
            if roi is None or ss is None:
                subs.append(('54(6) output variability', 'PARTIAL', 'row-order and seed stability not both recorded'))
            else:
                ok = bool(roi.get('invariant')) and bool(ss.get('stable'))
                subs.append(('54(6) output variability', 'SATISFIED' if ok else 'PARTIAL',
                             'row-order max PD difference %.2e; selected-set min Jaccard %.2f' % (roi['max_abs_pd_diff'], ss['min_jaccard'])))
            dr = chk.get('feature_drift')
            if dr is None:
                subs.append(('54(7) data and concept drift', 'PARTIAL', 'no drift measure recorded'))
            else:
                subs.append(('54(7) data and concept drift', 'PARTIAL' if dr.get('n_major') else 'SATISFIED',
                             'max feature PSI %.3f; %d feature(s) above the major threshold' % (dr['max_psi'], dr['n_major'])))
            status = 'SATISFIED' if all(x[1] in ('SATISFIED', 'N/A') for x in subs) else 'PARTIAL'
            put('R18', status, ' | '.join('%s %s: %s' % x for x in subs))

        # R19 - change management, material-change threshold, monitoring (Draft 36-42)
        if not inactive('R19'):
            oot = (self.state.get('stage4') or {}).get('oot')
            mc = chk.get('material_change') or rbc.material_change(oot=oot, drift=chk.get('feature_drift'))
            issues = []
            if not (p.get('monitoring_plan') or '').strip():
                issues.append('no monitoring plan declared (Draft 37)')
            if mc['revalidation_required']:
                issues.append('this run breaches the material-change criteria (%s): revalidation required before use (Draft 42)'
                              % '; '.join(mc['triggered']))
            put('R19', 'SATISFIED' if not issues else 'PARTIAL',
                '; '.join(issues) if issues else 'criteria defined from the governance thresholds; none breached by this run; monitoring plan declared')

        # R20 - human oversight (Draft 60-63; FREE-AI 4.4.62)
        if not inactive('R20'):
            g5 = self.state.get('g5') or {}
            issues = []
            if not (p.get('override_path') or '').strip():
                issues.append('no override path documented (Draft 60)')
            if not g5.get('override_policy'):
                issues.append('no override policy evidenced at G5')
            if p.get('human_review_rate') is None:
                issues.append('no periodic human review of a decision sample (FREE-AI 4.4.62)')
            put('R20', 'SATISFIED' if not issues else 'PARTIAL',
                '; '.join(issues) if issues else 'override path, G5 override policy and human review sample declared')

    # ----------------------------------------------------------- running checklist
    def record_g5(self, controls_ok, cutoff_policy_present, acceptance_pack_present,
                  coverage=None, override_policy=False):
        """Caller supplies the G5 facts; `coverage` is acceptance_coverage()'s dict."""
        self.state['g5'] = {'controls_ok': bool(controls_ok),
                            'cutoff_policy_present': bool(cutoff_policy_present),
                            'acceptance_pack_present': bool(acceptance_pack_present),
                            'coverage': coverage, 'override_policy': bool(override_policy)}
        return self.state['g5']

    def checklist(self, strict=False):
        """strict=True is the REGULATORY-USE reading (used by the dossier): R1 is a gap when the data history cannot be
        shown, R6 a gap while no Margin of Conservatism is quantified (EBA/GL/2017/16 para 47(a) requires it to be above
        zero), R7/R8 a gap while one person holds every role, R3 partial if realised default rates are not rank-ordered
        across grades, R5 partial without an override policy, and R2 N/A for a benchmark with no live use. strict=False
        keeps the earlier reading, which the sealed records used.

        Section-8 rows R1-R10 derived from the evidence recorded so far; a row with no
        evidence yet is omitted. Statuses are PROPOSALS for the signer (override with
        set_checklist). The derivation uses only existing parameters (alpha, the tier AUC
        floor, the EPV>=10 rule of thumb, the Wilson per-grade backtest) - no new thresholds."""
        alpha = self.cfg['alpha']
        rows = {}

        def put(r, status, note):
            rows[r] = {'id': r, 'status': status, 'note': note, 'gate': CHECKLIST_GATE[r],
                       'must_have': r in MUST_HAVE_ROWS, 'source': 'derived'}
        if 'stage0' in self.state:
            hy = self.history_years
            if hy is None:
                put('R1', 'PARTIAL', 'observation window not verifiable from the file')
            elif hy >= 5:
                put('R1', 'SATISFIED', 'observation window %s years' % hy)
            else:
                put('R1', 'GAP', 'observation window %s years < 5' % hy)
            put('R9', 'SATISFIED', 'tier %s assigned at G0' % self.tier)
            m = self.state['stage0'].get('missingness')
            if m is not None:
                hit = m[m['below_bonferroni']] if len(m) else m
                share = float(self.df.drop(columns=[self.target]).isna().any(axis=1).mean())
                if len(hit):
                    put('R10', 'PARTIAL', '%d column(s) whose blanks track the outcome beyond '
                        'Bonferroni (%s); %.1f%% of rows have at least one blank'
                        % (len(hit), ', '.join(hit['column'].head(3)), 100 * share))
                else:
                    put('R10', 'SATISFIED', 'no blank pattern tracks the outcome beyond '
                        'Bonferroni; %.1f%% of rows have at least one blank' % (100 * share))
        if 'stage3' in self.state:
            s3 = self.state['stage3']
            d = s3['decision']
            auc_floor = ag._AUC_FLOOR.get(self.tier)
            k = int(d['selected_k']) if d['tolerance_met'] else None
            auc = (float(s3['curve'].loc[s3['curve']['k'] == k, 'auc'].iloc[0])
                   if k else None)
            if auc is not None and auc_floor is not None and auc < auc_floor:
                put('R3', 'GAP', 'AUC %.3f below tier floor %.2f' % (auc, auc_floor))
            elif not d['tolerance_met']:
                put('R3', 'PARTIAL', 'no k met the pre-declared tolerance')
            else:
                put('R3', 'SATISFIED', 'Gini %.4f, AUC %.3f, tolerance met at k=%d'
                    % (d['gini'], auc, k))
        if 'stage1' in self.state:
            suf = self.sufficiency()
            gov = suf[suf['governing']].iloc[0]
            bad = []
            if float(gov['EPV']) < 10:
                bad.append('EPV %.1f on the candidate pool' % float(gov['EPV']))
            if not bool(gov['riley_met']):
                bad.append('Riley minimum not met on the candidate pool (%d needed, %d '
                           'available)' % (gov['N_required'], gov['available']))
            sel = suf[suf['stage'] == 'G3']
            info = ''
            if len(sel):
                info = '; selected model EPV %.1f, Riley %s (informational, post-selection)' % (
                    float(sel.iloc[0]['EPV']), 'met' if bool(sel.iloc[0]['riley_met'])
                    else 'not met')
            put('R6', 'PARTIAL' if bad else 'SATISFIED',
                ('; '.join(bad) + '; ' if bad else 'EPV >= 10 and Riley minimum met on the '
                 'candidate pool; ') + 'governed on the candidate pool' + info +
                '; Margin of Conservatism not quantified by this run')
        s4 = self.state.get('stage4')
        if s4 and s4.get('backtest'):
            bt = s4['backtest']
            hl = bt['hl'].get(10) or next(iter(bt['hl'].values()))
            hp = hl.get('p_adj', hl.get('p_value'))
            allpass = bt['grades_passed'] == bt['grades_total']
            if allpass and hp is not None and hp >= alpha:
                put('R4', 'SATISFIED', 'all %d grades inside Wilson CI; HL p %.3f'
                    % (bt['grades_total'], hp))
            else:
                put('R4', 'PARTIAL', '%d/%d grades pass; HL g=10 p %s'
                    % (bt['grades_passed'], bt['grades_total'],
                       'n/a' if hp is None else '%.4f' % hp))
        g5 = self.state.get('g5')
        if g5:
            ok = (g5['controls_ok'] and g5['cutoff_policy_present']
                  and g5['acceptance_pack_present'])
            ne = (g5.get('coverage') or {}).get('not_exercised') or []
            put('R2', 'SATISFIED' if ok else 'GAP',
                'governed decision + acceptance pack' if ok else 'deliverables incomplete')
            put('R5', 'SATISFIED' if g5['controls_ok'] else 'GAP',
                'override/refer controls configured' +
                ('; NOT EXERCISED by the data: ' + ', '.join(ne) if ne else ''))
        if self.sealed('G0'):
            rr = self.role_report()
            if not rr['declared']:
                put('R7', 'PARTIAL', 'role holders not declared')
                put('R8', 'PARTIAL', 'role holders not declared')
            elif rr['multi_role_persons']:
                put('R7', 'PARTIAL', 'no independent validator: ' + rr['note'])
                put('R8', 'PARTIAL', 'accountability not separated: ' + rr['note'])
            else:
                put('R7', 'SATISFIED', rr['note'])
                put('R8', 'SATISFIED', rr['note'])
        for r, key in REGIME_OF.items():
            if self.regimes is None or key not in self.regimes:
                rows[r] = {'id': r, 'status': 'NOT ASSESSED', 'must_have': False, 'gate': 'GF',
                           'source': 'derived',
                           'note': 'regimes not declared at G0, so it is not known whether %s binds' % key}
            elif not self.regimes[key].get('binding'):
                rows[r] = {'id': r, 'status': 'N/A', 'must_have': False, 'gate': 'GF', 'source': 'derived',
                           'note': 'not binding: %s' % self.regimes[key].get('reason', 'declared not binding')}
            else:
                rows[r] = {'id': r, 'status': 'PARTIAL', 'must_have': False, 'gate': 'GF', 'source': 'derived',
                           'note': 'binding regime (%s); no assessment recorded' % key}
        if self._in_active():
            self._in_rows(rows, strict)
        if strict:
            def worsen(r, status, add):
                if r in rows:
                    rows[r] = dict(rows[r], status=status, note=rows[r]['note'] + '; ' + add)
            if 'R1' in rows and rows['R1']['status'] == 'PARTIAL':
                worsen('R1', 'GAP', 'for regulatory use a history that cannot be shown is a gap (CRE36.79)')
            if 'R6' in rows and rows['R6']['status'] in ('PARTIAL', 'SATISFIED'):
                worsen('R6', 'GAP', 'no Margin of Conservatism is quantified; EBA/GL/2017/16 para 47(a) requires a positive category-C margin')
            rr_ = self.role_report()
            if rr_['declared'] and rr_['multi_role_persons']:
                for r_ in ('R7', 'R8'):
                    worsen(r_, 'GAP', 'regulatory use needs a validator and approver independent of the developer')
            s4_ = self.state.get('stage4')
            if s4_ and s4_.get('backtest') and 'R3' in rows:
                tb_ = s4_['backtest']['table']
                real_ = [float(x) for x in tb_['realised']]
                viol_ = sum(1 for a_, b_ in zip(real_, real_[1:]) if b_ < a_)
                if viol_ and rows['R3']['status'] == 'SATISFIED':
                    worsen('R3', 'PARTIAL', '%d rank-order break(s): realised default rates are not non-decreasing across grades, and grade concentration is not shown to be supported by evidence (CRE36.18-21)' % viol_)
            g5_ = self.state.get('g5')
            if g5_ and 'R5' in rows and not g5_.get('override_policy') and rows['R5']['status'] == 'SATISFIED':
                worsen('R5', 'PARTIAL', 'no override policy or override tracking is evidenced (CRE36.44); only a refer rule exists')
            if not self.live_use and 'R2' in rows:
                rows['R2'] = dict(rows['R2'], status='N/A', note='research benchmark with no live use: the use test cannot be evidenced')
        for r, o in self.state.get('checklist_overrides', {}).items():
            base = rows.get(r, {'id': r, 'must_have': r in MUST_HAVE_ROWS,
                                'gate': CHECKLIST_GATE.get(r, 'GF')})
            rows[r] = dict(base, status=o['status'], note=o['note'],
                           source='override by ' + o['by'])
        return [rows[k] for k in sorted(rows, key=lambda x: int(x[1:]))]

    def readiness_panel(self, strict=False):
        """Regulatory-readiness panel shown BEFORE the final sign-off: which acceptance criteria are
        complete, partial, pending, not applicable, and what closes each partial. It is an internal gate
        summary, NOT a prediction of regulatory approval."""
        cl = {r['id']: r for r in self.checklist(strict)}
        names = rr.names()
        order = rr.ids(india=self._in_active())
        done = [r for r in order if r in cl and cl[r]['status'] == 'SATISFIED']
        part = [r for r in order if r in cl and cl[r]['status'] == 'PARTIAL']
        gap = [r for r in order if r in cl and cl[r]['status'] == 'GAP']
        na = [r for r in order if r in cl and cl[r]['status'] == 'N/A']
        nass = [r for r in order if r in cl and cl[r]['status'] == 'NOT ASSESSED']
        pend = [r for r in order if r not in cl]
        L = ['REGULATORY-READINESS PANEL - %s' % self.name, '',
             'Complete %d | Partial %d | Gap %d | Pending (evidence not yet produced) %d | Not applicable %d | Not assessed %d'
             % (len(done), len(part), len(gap), len(pend), len(na), len(nass)), '']
        if self.regimes is None:
            L += ['Regimes: NOT DECLARED. R11-R14 cannot be classified until the committee records which regimes bind (AEGIS section 8).', '']
        else:
            L += ['Regimes declared (confirm at G0): ' + '; '.join(
                '%s = %s (%s)' % (k, 'BINDING' if v.get('binding') else 'not binding', v.get('reason', ''))
                for k, v in self.regimes.items()), '']

        def block(title, rows, with_action):
            if not rows:
                return
            L.append(title)
            for r in rows:
                line = '  %s  %s - %s' % (r, names[r], cl[r]['note'] if r in cl else 'no evidence yet (stage not reached)')
                L.append(line)
                if with_action and r in CLOSING_ACTION:
                    L.append('        closes with: %s [owner: %s]' % CLOSING_ACTION[r])
            L.append('')
        block('COMPLETE', done, False)
        block('PARTIAL - what closes each', part, True)
        block('GAP - hard stop if a must-have', gap, True)
        block('PENDING - evidence produced at a later gate', pend, False)
        block('NOT APPLICABLE', na, False)
        block('NOT ASSESSED', nass, False)
        L += ['Roles: ' + self.role_report()['note'], '',
              'READ THIS AS: a gap analysis against the framework\'s own acceptance criteria. It does not predict a',
              'supervisor\'s decision. A research benchmark on public data carries a NEVER-DEPLOY condition, which',
              'a supervisor would not approve for capital use whatever the checklist says.', '',
              'NOT COVERED BY THIS CHECKLIST (general knowledge, not verified in this session; confirm against the',
              'primary texts before relying on it): the default definition used; long-run-average calibration of PD',
              '(this model is estimated on one cross-section); LGD and EAD models; a quantified Margin of Conservatism.']
        if self._in_active():
            L += ['', 'INDIAN (RBI) PACK: rows R15-R20 are read from the RBI Draft (consultation text, June 2026) and the FREE-AI report;',
                  'they are conditions, not must-haves, while the source is a draft. NOT YET READ and therefore not scored: RBI default',
                  'definition (asset classification), the expected-credit-loss directions, Basel III capital use of ratings.']
        return '\n'.join(L)

    def set_checklist(self, row, status, note, by):
        """The signer overrides a derived row; kept with who and why."""
        if status not in ag.VALID_STATUS | {'N/A'}:
            raise ValueError('status must be one of %s' % sorted(ag.VALID_STATUS | {'N/A'}))
        if len((note or '').strip()) < MIN_RATIONALE:
            raise ValueError('note must be >= %d characters' % MIN_RATIONALE)
        self.state.setdefault('checklist_overrides', {})[row] = {
            'status': status, 'note': note, 'by': by}

    def gf_verdict(self, residual_within_appetite=True, strict=False):
        """Engine verdict from the sealed gates and the running checklist."""
        states = {g: ('signed' if self.sealed(g) else 'unsigned')
                  for g in ('G0', 'G1', 'G2', 'G3', 'G4', 'G5')}
        rows = [r for r in self.checklist(strict) if r['status'] in ag.VALID_STATUS]   # engine reads only assessed rows
        return ag.gf_engine(states, rows, residual_within_appetite=residual_within_appetite)

    # ------------------------------------------------------------ gate evidence
    def gate_evidence(self, gate, **extra):
        y, n = self.df[self.target], len(self.df)
        events = int(y.sum())
        if gate == 'G0':
            s0 = self.state['stage0']['s0']
            ev = {'tier': self.tier, 'n_rows': n, 'event_rate': round(events / n, 4),
                  'history_years': None, 'excluded': extra.get('excluded', []),
                  'borderline_exclusions': [], 'label_integrity': True,
                  'epv_pool': round(events / (self.df.shape[1] - 1), 1)}
            if self._in_active():           # Indian pack only: keys absent otherwise, so other runs are unchanged
                tp = self.tier_proposal()
                if tp:
                    ev['tier_proposal'] = tp
                ev['regime_pack'] = {'pack_version': rr.PACK_VERSION, 'final_rbi_issued': rr.FINAL_RBI_ISSUED,
                                     'sources': {k: {'sha256': v['sha256'], 'verified_on': v['verified_on']}
                                                 for k, v in rr.RBI_SOURCES.items()}}
            return ev
        if gate == 'G1':
            s1 = self.state['stage1']
            t = s1['s1_table']
            top = t.sort_values('iv_woe', ascending=False).iloc[0]
            gov = self.sufficiency()
            gov = gov[gov['governing']].iloc[0]
            return {'tier': self.tier, 'n_pass': len(s1['candidates']),
                    'n_pool': int(gov['P']),
                    'epv': round(events / int(gov['P']), 1),
                    'riley_req': int(gov['N_required']), 'riley_avail': n,
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
            m = st.get('missingness')
            if m is not None:
                txt += ('\n\nBlank-vs-outcome scan (report only; Fisher exact; columns with no '
                        'blanks omitted):\n' +
                        (v3._md_table(m.round(5).drop(columns=['bonferroni_p']),
                                      index_name='#') if len(m) else 'no column has blanks'))
            la = st.get('lookahead')
            if la:
                txt += ('\n\nLook-ahead review - definitions matching a temporal phrase:\n' +
                        '\n'.join('- %s: "%s" (matched: %s)'
                                   % (c, v['definition'], ', '.join(v['matched']))
                                   for c, v in la.items()))
            txt += '\n\nRole holders: ' + self.role_report()['note']
            return txt
        if n == 1:
            show = ['iv_woe', 'iv_q5', 'iv_q10', 'iv_q20', 'binning_sensitive',
                    'shape_nonmonotonic', 'cramers_v_descriptive', 'min_expected',
                    'gate_ok', 'escalation', 'mann_whitney_p', 'passes_screen']
            t = st['s1_table']
            return (v3._md_table(t[[c for c in show if c in t.columns]].round(4)) +
                    '\n\nSufficiency on every basis reached so far:\n' +
                    v3._md_table(self.sufficiency(), index_name='#') +
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
