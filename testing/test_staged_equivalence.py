"""Staged runner == one-shot pipeline, and the gate-order guards hold.

Plain script (like the rest of testing/): prints PASS/FAIL, exits non-zero on failure.
Uses the 1,000-row south_german_credit_en.csv so it runs in a few minutes.

    .\\venv310\\Scripts\\python.exe testing\\test_staged_equivalence.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'ml_models'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
import numpy as np
import pandas as pd
import v3_pipeline as v3
import staged_run as sr
import run_scorecard as rsc
from staged_run import StagedRun

fails = []


def check(label, ok):
    print(('PASS  ' if ok else 'FAIL  ') + label, flush=True)
    if not ok:
        fails.append(label)


df = pd.read_csv(os.path.join(ROOT, 'data', 'ml_lab', 'datasets', 'south_german_credit_en.csv'))
one = v3.run_pipeline(df, target='target', dataset_name='EQ', verbose=False)

run = StagedRun(df, 'target', 'EQ', tempfile.mkdtemp(prefix='staged_eq_'), verbose=False,
                roles={'Data Steward': 'A', 'Model Validator': 'A', 'Risk Officer': 'B'},
                dictionary={'x': 'profit in 3 years', 'y': 'ratio of assets'})

# --- order guards -----------------------------------------------------------
try:
    run.stage1()
    check('stage1 refused before G0 sealed', False)
except RuntimeError:
    check('stage1 refused before G0 sealed', True)
run.stage0()
try:
    run.seal('G0', 'A', 'too short')
    check('short rationale refused', False)
except ValueError:
    check('short rationale refused', True)
try:
    run.seal('G1', 'A', 'x' * 30)
    check('G1 refused before stage1 ran / G0 sealed', False)
except RuntimeError:
    check('G1 refused before stage1 ran / G0 sealed', True)

# --- walk every gate as option A --------------------------------------------
R = 'staged equivalence test rationale'
run.seal('G0', 'A', R)
run.stage1(); run.seal('G1', 'A', R)
run.stage2(); run.seal('G2', 'A', R)
run.stage3(); run.seal('G3', 'A', R)
run.stage4(); run.seal('G4', 'A', R)

# --- equivalence ------------------------------------------------------------
check('candidates identical', run.state['stage1']['candidates'] == one['candidates'])
check('selected columns identical',
      run.state['stage3']['selected_columns'] == one['selected_columns'])
check('selected k identical',
      run.state['stage3']['decision']['selected_k'] == one['decision']['selected_k'])
check('parsimony curve identical',
      np.allclose(run.state['stage3']['curve'].select_dtypes('number').values,
                  one['curve'].select_dtypes('number').values, equal_nan=True))
check('shadow bar identical',
      run.state['stage2']['s2']['shadow_bar'] == one['stage2']['shadow_bar'])
check('calibration identical', str(run.state['stage4']['calibration']) == str(one['calibration']))
check('backtest grades identical',
      run.state['stage4']['backtest']['grades_passed'] == one['backtest']['grades_passed'])
check('markdown report identical', run.final_report() == one['report'])

# --- gate cards build from the staged evidence ------------------------------
for g in ('G0', 'G1', 'G2', 'G3', 'G4'):
    try:
        run.show_gate(g)
        check('%s card builds' % g, True)
    except Exception as e:     # noqa: BLE001
        check('%s card builds (%r)' % (g, e), False)


# --- revision 2026-10-25 additions (report-only diagnostics + running checklist) ----------
# synthetic frame: column 'b' is blank mostly for events, column 'n' blank at random
rng = np.random.RandomState(0)
sy = rng.binomial(1, 0.2, 2000)
sdf = pd.DataFrame({'a': rng.randn(2000), 'b': rng.randn(2000), 'n': rng.randn(2000), 'target': sy})
sdf.loc[(sy == 1) & (rng.rand(2000) < 0.6), 'b'] = np.nan
sdf.loc[rng.rand(2000) < 0.05, 'n'] = np.nan
ms = sr.missingness_scan(sdf, 'target')
check('missingness scan ranks the outcome-linked blank column first', ms.iloc[0]['column'] == 'b')
check('missingness scan: random blanks not below Bonferroni',
      not bool(ms[ms['column'] == 'n']['below_bonferroni'].iloc[0]))
check('look-ahead scan hits only the temporal definition',
      list(sr.lookahead_scan({'x': 'profit in 3 years', 'y': 'ratio of assets'})) == ['x'])
check('stage0 stores missingness + lookahead', 'missingness' in run.state['stage0']
      and list(run.state['stage0']['lookahead']) == ['x'])
suf = run.sufficiency()
check('sufficiency has pool (governing), IV-screened, players and selected rows',
      list(suf['stage']) == ['G1', 'G1', 'G2', 'G3'] and int(suf['governing'].sum()) == 1
      and bool(suf.iloc[0]['governing']))
check('pool P is the number of columns that entered Stage 1',
      int(suf.iloc[0]['P']) == len(run.state['stage1']['s1_table']))
check('R6 is governed on the pool', 'candidate pool' in {r['id']: r for r in run.checklist()}['R6']['note'])
check('role report flags the multi-role person',
      run.role_report()['multi_role_persons'] == {'A': ['Data Steward', 'Model Validator']})
check('seal records person and rationale_by outside the hash',
      run.chain[0]['person'] == 'A' and 'rationale_by' in run.chain[0])
check('hash format unchanged',
      run.chain[0]['entry_hash'] == __import__('hashlib').sha256(
          (run.genesis + 'G0|A|' + run.chain[0]['signer'] + '|' + R).encode()).hexdigest()[:8])
cl = {r['id']: r for r in run.checklist()}
check('checklist derives R3/R4/R6/R9 and R7/R8 from roles',
      all(k in cl for k in ('R1', 'R3', 'R4', 'R6', 'R7', 'R8', 'R9', 'R10'))
      and cl['R7']['status'] == 'PARTIAL')
run.set_checklist('R1', 'SATISFIED', 'ten-year window confirmed by the data steward', 'A')
check('checklist override is recorded',
      {r['id']: r for r in run.checklist()}['R1']['source'].startswith('override'))
try:
    run.set_checklist('R1', 'SATISFIED', 'short', 'A')
    check('override with a short note refused', False)
except ValueError:
    check('override with a short note refused', True)
cov = sr.acceptance_coverage(df, 'target', run.state['stage3']['selected_columns'])
check('acceptance coverage reports cap/floor exercise',
      'cap_exercised' in cov and isinstance(cov['not_exercised'], list))
run.record_g5(True, True, True, cov)
check('G5 facts fill R2 and R5', all(k in {r['id'] for r in run.checklist()} for k in ('R2', 'R5')))
run.seal('G5', 'A', R)
run.seal('GF', 'GO-WITH-CONDITIONS', R)
check('gf_verdict runs from the running checklist', run.gf_verdict().verdict in
      ('GO', 'GO-WITH-CONDITIONS', 'NO-GO'))


# --- scorecard -------------------------------------------------------------------------------
card = rsc.build(run)
check('scorecard has all six dimensions',
      all(k in card for k in ('ranking', 'accuracy', 'grades', 'sufficiency', 'stability', 'integrity')))
check('capture rates rise with the percentile',
      card['ranking']['capture_top_5'] <= card['ranking']['capture_top_10'] <= card['ranking']['capture_top_20'] <= 1)
check('Brier skill CI brackets the point value',
      card['uncertainty']['ci']['brier_skill_oof'][0] <= card['accuracy']['brier_skill_oof']
      <= card['uncertainty']['ci']['brier_skill_oof'][1])
check('Stage-4 calibration describes the deployed WOE-logistic model (not XGBoost)',
      run.state['stage4']['calibration']['learner'].startswith('woe_logistic')
      and card['calibration_step']['learner'].startswith('woe_logistic'))
check('calibration block keeps its keys',
      all(k in run.state['stage4']['calibration'] for k in
          ('baseline_brier_always_base_rate', 'raw_brier', 'raw_ece', 'calibrated_brier',
           'calibrated_ece', 'calibrated_auc', 'method', 'cv')))
check('bars cleared <= applicable and fairness bar n/a without an AIR',
      card['bars_cleared'] <= card['bars_applicable'] == 8)
check('integrity block says governed', card['integrity']['governed'] is True)
check('compare() renders both runs', 'EQ' in rsc.compare(card, card) and 'Lead' in rsc.compare(card, card))
check('capture helper: perfect ranking captures all events in the top share',
      rsc._capture([1, 1, 0, 0, 0, 0, 0, 0, 0, 0], [9, 8, 1, 1, 1, 1, 1, 1, 1, 1], 0.2)[0] == 1.0)

# --- reopen voids this gate and later ones, keeps the audit trail -----------
n = run.reopen('G2', 'test: a G2 player is challenged as a leak')
check('reopen(G2) -> re-run stage 2', n == 2)
check('G2..GF voided (5 entries), G0/G1 kept',
      [e['gate'] for e in run.chain] == ['G0', 'G1'] and len(run.voided) == 5)
try:
    run.stage3()
    check('stage3 refused after reopen', False)
except (RuntimeError, KeyError):
    check('stage3 refused after reopen', True)

print('\n%d failure(s)' % len(fails))
sys.exit(1 if fails else 0)
