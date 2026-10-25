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
from staged_run import StagedRun

fails = []


def check(label, ok):
    print(('PASS  ' if ok else 'FAIL  ') + label, flush=True)
    if not ok:
        fails.append(label)


df = pd.read_csv(os.path.join(ROOT, 'data', 'ml_lab', 'datasets', 'south_german_credit_en.csv'))
one = v3.run_pipeline(df, target='target', dataset_name='EQ', verbose=False)

run = StagedRun(df, 'target', 'EQ', tempfile.mkdtemp(prefix='staged_eq_'), verbose=False)

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

# --- reopen voids this gate and later ones, keeps the audit trail -----------
n = run.reopen('G2', 'test: a G2 player is challenged as a leak')
check('reopen(G2) -> re-run stage 2', n == 2)
check('G2..G4 voided, G0/G1 kept',
      [e['gate'] for e in run.chain] == ['G0', 'G1'] and len(run.voided) == 3)
try:
    run.stage3()
    check('stage3 refused after reopen', False)
except (RuntimeError, KeyError):
    check('stage3 refused after reopen', True)

print('\n%d failure(s)' % len(fails))
sys.exit(1 if fails else 0)
