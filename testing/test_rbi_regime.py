"""Indian (RBI) regime pack: registry, tier proposal, rows R15-R20, reporting-only diagnostics.

Plain script (like the rest of testing/): prints PASS/FAIL, exits non-zero on failure. Uses a small synthetic panel,
so it runs in about a minute. The existing testing/test_staged_equivalence.py is the regression test for everything
else (it must still pass with this change).

    .\\venv310\\Scripts\\python.exe testing\\test_rbi_regime.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'ml_models'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
import numpy as np
import pandas as pd
import aegis_gates as ag
import regime_registry as rr
import rbi_checks as rbc
import staged_run as sr
import standard_run as std
from staged_run import StagedRun

fails = []


def check(label, ok):
    print(('PASS  ' if ok else 'FAIL  ') + label, flush=True)
    if not ok:
        fails.append(label)


# --- 1. registry: R1-R14 are identical to the literals that used to live in staged_run.py ---------------------------
LEGACY_GATE = {'R1': 'G0', 'R2': 'G5', 'R3': 'G3', 'R4': 'G4', 'R5': 'G5', 'R6': 'G4', 'R7': 'GF', 'R8': 'GF',
               'R9': 'G0', 'R10': 'G0', 'R11': 'GF', 'R12': 'GF', 'R13': 'GF', 'R14': 'GF'}
LEGACY_MUST = ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9')
LEGACY_REGIME = {'R11': 'UK_PRA_SS1_23', 'R12': 'EU_AI_ACT_HIGH_RISK', 'R13': 'EU_AI_ACT_HUMAN_OVERSIGHT', 'R14': 'US_ECOA_REG_B'}
LEGACY_NAMES = {'R1': 'PD data history >= 5 years', 'R2': 'Use test', 'R3': 'Risk differentiation', 'R4': 'Calibration backtest',
                'R5': 'Override governance', 'R6': 'Margin of Conservatism', 'R7': 'Independent validation',
                'R8': 'Governance and accountability', 'R9': 'Risk-proportionate rigour', 'R10': 'Data governance / completeness',
                'R11': 'Model risk management principles (PRA SS1/23)', 'R12': 'High-risk AI obligations (EU AI Act)',
                'R13': 'Human-oversight operability (EU AI Act Art 14)', 'R14': 'Adverse-action reasons (ECOA / Reg B)'}
LEGACY_ACTION = {
    'R1': ('Verify the observation window of the PD data (data-owner statement or dated records)', 'Data Steward / data owner'),
    'R2': ('Complete the cutoff note and acceptance pack, and show the PDs feed real decisions', 'Model Owner'),
    'R3': ('Justify or down-tier if discrimination is below the tier floor or no k meets the tolerance', 'Model Validator'),
    'R4': ('Resolve failing grades and the HL result, or document them with an ongoing-monitoring plan', 'Risk Officer'),
    'R5': ('Configure and document the override / refer controls', 'Model Owner'),
    'R6': ('Quantify the Margin of Conservatism by category (EBA A/B/C) and address the EPV shortfall', 'Model Owner + Risk Officer'),
    'R7': ('Appoint a validator independent of the developer', 'MAC Chair'),
    'R8': ('Separate developer, validator and approver roles and constitute the committee', 'MAC Chair + CRO'),
    'R9': ('Assign the materiality tier at G0', 'Data Steward'),
    'R10': ('Explain or resolve blank patterns that track the outcome; lineage and completeness report', 'Data Steward'),
    'R11': ('Map the lifecycle to the PRA SS1/23 principles and record the assessment', 'Model Owner'),
    'R12': ('Record the Art 9/10/12/13/14 assessment for natural-person credit scoring', 'Model Owner'),
    'R13': ('Show that overseers can understand, decline and halt the model output', 'Model Owner'),
    'R14': ('Provide specific principal reasons for adverse action', 'Model Owner')}
old14 = ['R%d' % i for i in range(1, 15)]
check('registry: R1-R14 gates unchanged', {k: rr.checklist_gate()[k] for k in old14} == LEGACY_GATE)
check('registry: must-have rows are still R1-R9 (R15-R20 are conditions while RBI is a draft)',
      tuple(rr.must_have_rows()) == LEGACY_MUST and tuple(sr.MUST_HAVE_ROWS) == LEGACY_MUST and ag.MUST_HAVE == set(LEGACY_MUST))
check('registry: R11-R14 regime keys unchanged', rr.regime_of() == LEGACY_REGIME and sr.REGIME_OF == LEGACY_REGIME)
check('registry: R1-R14 readiness names unchanged', {k: rr.names()[k] for k in old14} == LEGACY_NAMES)
check('registry: R1-R14 closing actions and owners unchanged', {k: rr.closing_actions()[k] for k in old14} == LEGACY_ACTION)
check('registry: Indian rows are R15-R20 and only in the Indian id list',
      rr.ids(india=False) == old14 and rr.ids(india=True) == old14 + ['R%d' % i for i in range(15, 21)])
check('registry: Indian rows carry a legal status and a verified source',
      all(rr.row(r)['legal_status'] in ('draft', 'recommendation') for r in ('R15', 'R16', 'R17', 'R18', 'R19', 'R20'))
      and all(v['sha256'] and len(v['sha256']) == 64 for v in rr.RBI_SOURCES.values()))
check('registry: R15 and R16 block only in the regulatory-use reading', rr.row('R15')['must_have_strict'] and rr.row('R16')['must_have_strict']
      and not rr.row('R15')['must_have'] and not rr.row('R17')['must_have_strict'])
check('registry: rows built on unread text are listed as pending and not scored', len(rr.PENDING_SOURCES) == 3
      and not any(k in {r['regime'] for r in rr.ROWS} for k in rr.PENDING_SOURCES))
here = os.path.dirname(os.path.dirname(ROOT))
pdfs = os.path.join(ROOT, 'paper analysis', 'important papers', 'papers', 'RBI folder')
if os.path.isdir(pdfs):
    import hashlib
    ok = True
    for k, v in rr.RBI_SOURCES.items():
        f = os.path.join(ROOT, 'paper analysis', v['file'].replace('/', os.sep))
        if os.path.exists(f):
            ok = ok and hashlib.sha256(open(f, 'rb').read()).hexdigest() == v['sha256']
    check('registry: recorded SHA-256 matches the RBI PDFs in the RBI folder', ok)

# --- 2. tier proposal with the anti-dilution rule (RBI Draft 19-20, 52) ---------------------------------------------
tp = ag.propose_tier('HIGH', 'LOW', 'LOW')
check('tier: low complexity cannot dilute a highly material model', tp['proposed'] == 'HIGH' and tp['diluted_by_low_complexity'])
check('tier: complexity or autonomy can raise the tier', ag.propose_tier('LOW', 'HIGH')['proposed'] == 'HIGH'
      and ag.propose_tier('MEDIUM', 'LOW', 'HIGH')['proposed'] == 'HIGH')
check('tier: never below materiality', all(ag._TIER_RANK[ag.propose_tier(m, c, a)['proposed']] >= ag._TIER_RANK[m]
                                          for m in ag.TIERS for c in ag.TIERS for a in ag.TIERS))
try:
    ag.propose_tier('EXTREME')
    check('tier: bad input refused', False)
except ValueError:
    check('tier: bad input refused', True)

# --- 3. a small synthetic panel for the staged run ---------------------------------------------------------------------------
rng = np.random.RandomState(1)
n_ent, n_yr = 350, 4
ent = np.repeat(np.arange(n_ent), n_yr)
yr = np.tile(np.arange(n_yr), n_ent)
X = pd.DataFrame({'x%d' % i: rng.randn(n_ent * n_yr) for i in range(1, 6)})
lin = -2.6 + 1.1 * X['x1'] + 0.8 * X['x2'] - 0.4 * yr
yb = (rng.rand(len(X)) < 1 / (1 + np.exp(-lin))).astype(int)
df = X.assign(target=yb)
seg = np.where(X['x3'] > 0, 'large', 'small')
tv = yr.astype(float)


def make(jurisdiction, india=None, roles=None, tier='MEDIUM'):
    m = dict(std.MANIFEST_DEFAULTS)
    m['jurisdiction'] = jurisdiction
    return StagedRun(df, 'target', 'RBI_T', tempfile.mkdtemp(prefix='rbi_t_'), verbose=False, tier=tier, groups=ent,
                     time_values=tv, n_shadows=4, n_samples=20, shapley_row_subsample=None,
                     roles=roles or {'Data Steward': 'A', 'Model Validator': 'A', 'Risk Officer': 'A'},
                     regimes=std.default_regimes(m), india=india)


# --- 4. non-Indian runs are untouched --------------------------------------------------------------------------------------
eu = make('EU')
check('EU run: no R15-R20 rows and the readiness panel is the old one',
      [r['id'] for r in eu.checklist()] == [r['id'] for r in eu.checklist() if r['id'] in old14]
      and 'INDIAN (RBI) PACK' not in eu.readiness_panel() and 'R15' not in eu.readiness_panel())
check('default regimes: no Indian key outside IN; both keys for IN',
      not any(k.startswith('IN_') for k in std.default_regimes(dict(std.MANIFEST_DEFAULTS, jurisdiction='EU')))
      and {'IN_RBI_MRM_DRAFT_2026', 'IN_RBI_FREE_AI_2025'} <= set(std.default_regimes(dict(std.MANIFEST_DEFAULTS, jurisdiction='IN'))))
check('default regimes: india_pack false switches the Indian rows off',
      not any(k.startswith('IN_') for k in std.default_regimes(dict(std.MANIFEST_DEFAULTS, jurisdiction='IN', india_pack=False))))

# --- 5. Indian runs: rows R15-R20 ----------------------------------------------------------------------------------------------
inn = make('IN', india={'exposure_materiality': 'HIGH', 'complexity': 'LOW'})
cl = {r['id']: r for r in inn.checklist()}
check('IN run: rows R15-R20 are derived', all(k in cl for k in ('R15', 'R16', 'R17', 'R18', 'R19', 'R20')))
check('IN run: R15 is PARTIAL when tier MEDIUM is below the proposed HIGH and no use statement exists',
      cl['R15']['status'] == 'PARTIAL' and 'below the anti-dilution proposal' in cl['R15']['note'] and 'intended-use' in cl['R15']['note'])
st = {r['id']: r for r in inn.checklist(strict=True)}
check('IN run: R15 and R16 become must-have GAPs in the regulatory-use reading only',
      st['R15']['status'] == 'GAP' and st['R15']['must_have'] and st['R16']['status'] == 'GAP' and st['R16']['must_have']
      and not cl['R15']['must_have'] and not cl['R16']['must_have'])
check('IN run: R17-R20 stay conditions in the strict reading', all(not st[r]['must_have'] for r in ('R17', 'R18', 'R19', 'R20')))
check('IN run: the engine blocks on R15/R16 only in the regulatory-use reading',
      inn.gf_verdict(strict=True).verdict == 'NO-GO' and any('R15' in b or 'R16' in b for b in inn.gf_verdict(strict=True).blockers))
check('IN run: R18 lists all seven para-54 items', all(k in cl['R18']['note'] for k in
      ('54(1)', '54(2)', '54(3)', '54(4)', '54(5)', '54(6)', '54(7)')))
good = make('IN', india={'exposure_materiality': 'MEDIUM', 'complexity': 'LOW', 'intended_use': 'rank firms by one-year default risk; not for capital',
                         'mrmf_in_place': True, 'retention_years': 10, 'dependencies': ['data vendor', 'rating agencies'],
                         'explainability_threshold': 'principal reasons for every adverse decision', 'monitoring_plan': 'quarterly PSI and Gini',
                         'override_path': 'relationship manager may override with a recorded reason', 'human_review_rate': 0.01,
                         'validation_report_months': 2},
            roles={'Data Steward': 'A', 'Model Validator': 'B', 'Risk Officer': 'C'})
good.record_g5(True, True, True, {'not_exercised': []}, override_policy=True)
good.write_inventory_card()
g = {r['id']: r for r in good.checklist()}
check('IN run, complete declarations: R15, R16, R17, R19 and R20 are SATISFIED',
      all(g[r]['status'] == 'SATISFIED' for r in ('R15', 'R16', 'R17', 'R19', 'R20')))
check('IN run: R18 stays PARTIAL until the diagnostics are recorded', g['R18']['status'] == 'PARTIAL')
check('IN run: tier below the proposal with a recorded justification is PARTIAL, not a strict GAP',
      (lambda r: {x['id']: x for x in r.checklist(strict=True)}['R15']['status'] == 'PARTIAL')(
          make('IN', india={'exposure_materiality': 'HIGH', 'intended_use': 'research ranking only', 'tier_justification':
                            'research benchmark with no live use and no capital use'})))
check('inventory card is written with roles, tier proposal and the pack provenance',
      os.path.exists(good.state['inventory_card']) and 'pack_version' in good.write_inventory_card()['regime_pack'])

# --- 6. a real (small) staged run: evidence, diagnostics and rows -------------------------------------------------------------
run = good
R = 'rbi regime test rationale text'
run.stage0()
ev0 = run.gate_evidence('G0')
check('IN run: G0 evidence carries the tier proposal and the SHA-256 of the RBI sources',
      ev0['tier_proposal']['proposed'] == 'MEDIUM' and all('sha256' in v for v in ev0['regime_pack']['sources'].values()))
check('EU run: G0 evidence has none of the Indian keys', (lambda e: 'tier_proposal' not in e and 'regime_pack' not in e)(
    (lambda r: (r.stage0(), r.gate_evidence('G0'))[1])(make('EU'))))
run.seal('G0', 'A', R)
run.stage1(); run.seal('G1', 'A', R)
run.stage2(); run.seal('G2', 'A', R)
run.stage3(); run.seal('G3', 'A', R)
run.stage4(); run.seal('G4', 'A', R)
import missing_governance as mg
sel = list(run.state['stage3']['selected_columns'])
check('stage 4 ran an out-of-time test on the synthetic panel', bool((run.state['stage4'].get('oot') or {}).get('ok')))
out = std.run_rbi_checks(run, dict(std.MANIFEST_DEFAULTS, mandatory_columns=[], india=run.india), segments=seg,
                         select_fn=lambda s: sel if s != 7 else sel[:-1] if len(sel) > 1 else sel)
check('diagnostics recorded: drift, row order, segments, sign audit, perturbation, outlier, material change',
      all(k in out for k in ('feature_drift', 'score_drift', 'row_order', 'segments', 'sign_audit', 'perturbation',
                             'outlier', 'material_change', 'seed_stability')))
g2 = {r['id']: r for r in run.checklist()}
check('R18 now reports every para-54 item from recorded evidence', all(('54(%d)' % i) in g2['R18']['note'] for i in range(1, 8))
      and 'not both recorded' not in g2['R18']['note'] and 'no drift measure' not in g2['R18']['note'])
check('R19 uses the application thresholds and reports whether this run breaches them',
      g2['R19']['status'] in ('SATISFIED', 'PARTIAL') and (g2['R19']['status'] == 'SATISFIED' or 'material-change' in g2['R19']['note']))
check('panel for an Indian run lists R15-R20 and the pending-document note',
      'R15' in run.readiness_panel() and 'NOT YET READ' in run.readiness_panel())
check('hash chain format is unchanged by the Indian pack',
      run.chain[0]['entry_hash'] == __import__('hashlib').sha256((run.genesis + 'G0|A|' + run.chain[0]['signer'] + '|' + R).encode()).hexdigest()[:8])

# --- 7. rbi_checks unit tests --------------------------------------------------------------------------------------------------
a = pd.Series(rng.randn(5000))
check('PSI: identical samples give ~0 and a shifted sample is major',
      rbc.psi(a, a) < 1e-6 and rbc.psi(a, a + 1.5) > rbc.thresholds()['psi_major'])
check('PSI: categorical shares work', rbc.psi(pd.Series(['a'] * 90 + ['b'] * 10), pd.Series(['a'] * 10 + ['b'] * 90)) > 0.25)
check('drift status uses the application thresholds', rbc.drift_status(0.05) == 'stable' and rbc.drift_status(0.15) == 'watch'
      and rbc.drift_status(0.3) == 'major')


class _Const:
    def __init__(self, v):
        self.v = v

    def score(self, d):
        return pd.DataFrame({'probability': np.full(len(d), self.v)})


order_free = lambda d, t, c, groups=None, **k: (_Const(0.1), {})                       # noqa: E731
order_bound = lambda d, t, c, groups=None, **k: (_Const(float(d.iloc[0][c[0]])), {})   # noqa: E731
small = df.iloc[:300]
check('row-order test: an order-free builder is invariant', rbc.row_order_invariance(small, 'target', ['x1'], order_free)['invariant'])
check('row-order test: an order-dependent builder is caught', not rbc.row_order_invariance(small, 'target', ['x1'], order_bound)['invariant'])
stab = rbc.selection_stability(lambda s: ['a', 'b', 'c'], [1, 2, 3])
check('selection stability: identical sets give Jaccard 1', stab['min_jaccard'] == 1.0 and stab['stable'])
check('selection stability: different sets lower the Jaccard', rbc.selection_stability(
    lambda s: ['a', 'b'] if s == 1 else ['c', 'd'], [1, 2])['min_jaccard'] == 0.0)
yy = np.array([0] * 80 + [1] * 20)
pp = np.where(yy == 1, 0.3, 0.1) + rng.rand(100) * 0.05
sa = rbc.segment_assessment(yy, pp, np.array(['a'] * 50 + ['b'] * 50), min_events=5)
check('segment assessment: per-segment rows, a ratio and a stated indicative cutoff', len(sa['table']) == 2
      and sa['ratio'] is not None and 'indicative' in sa['cutoff_basis'])
ll = rbc.label_lag_sensitivity(yy, pp, np.where(yy == 1, np.arange(100) % 360, np.nan), lags=(0, 90, 180))
check('label-lag sensitivity drops positives that fall within the lag', list(ll['n_positives']) == sorted(ll['n_positives'], reverse=True)
      and ll['n_positives'].iloc[0] == 20)
cs = rbc.coefficient_sign_audit(['u', 'v', 'w'], [-0.5, 0.2, -0.3], corr=pd.DataFrame({'u': [1, .9, 0], 'v': [.9, 1, 0], 'w': [0, 0, 1]},
                                                                                        index=['u', 'v', 'w']))
check('coefficient sign audit: with WOE = ln(good/bad) a POSITIVE coefficient is unexpected; its correlated partner is named',
      cs['unexpected'] == ['v'] and cs['partners']['v'] == ['u'] and cs['expected_sign'] == 'negative')
mc = rbc.material_change(oot={'ok': True, 'gini_drop_rel': 0.149}, drift={'max_psi': 0.1})
check('material change: a 14.9% fall breaches the application criterion of 5%',
      mc['revalidation_required'] and any('fell' in t for t in mc['triggered']))
check('material change: nothing breached when within thresholds',
      not rbc.material_change(oot={'ok': True, 'gini_drop_rel': 0.01}, drift={'max_psi': 0.1})['revalidation_required'])
bm = rbc.benchmark_models(X, yb, ['x1', 'x2'], groups=ent)
check('benchmark: small logistic and gradient boosting both report an out-of-fold AUC', all(0.5 < bm[k]['auc'] <= 1 for k in bm) and len(bm) == 2)

print('\n%d failure(s)' % len(fails))
sys.exit(1 if fails else 0)
