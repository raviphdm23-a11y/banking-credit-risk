# Model reliability scorecard - POLISH_1YR

N 5,910 · events 410 · prevalence 6.94% · tier MEDIUM · **bars cleared: 6 of 8 applicable**

_Describes the model and its data together; not a ranking of methods. Out-of-fold / held-out figures only; no cutoff-based metric (the cutoff is an institution input)._
_Intervals marked 95% CI: stratified percentile bootstrap, 1000 resamples, seed 42 (a reporting convention; Gini and AUC use DeLong)._

## 1. Ranking power (out-of-fold, selected model)

| Metric | Value |
|---|---|
| Gini (95% CI) | 0.8260 (0.7966 to 0.8568) |
| AUC | 0.9130 |
| KS | 0.6975 |
| Partial AUC | 0.8927 |
| Events captured in riskiest 5% (95% CI; lift) | 46.8% (43.4% to 50.5%; 9.4x) |
| Events captured in riskiest 10% (95% CI; lift) | 65.8% (61.7% to 70.0%; 6.6x) |
| Events captured in riskiest 20% (95% CI; lift) | 84.4% (80.5% to 88.0%; 4.2x) |

## 2. Probability accuracy (primary WOE-logistic model, out-of-fold)

| Metric | Value |
|---|---|
| Brier skill (95% CI) | 0.3692 (0.3253 to 0.4101) |
| ECE (95% CI) | 0.0068 (0.0051 to 0.0129) |
| Deployed-model ECE on held-out firms, before to after isotonic | 0.0157 to 0.0169 |
| Calibration slope (95% CI) / intercept | 0.954 (0.889 to 1.026) / -0.091 |
| Hosmer-Lemeshow p (10 groups / 5 groups) | 0.0720 / 0.0185 |

_Pipeline calibration step (XGBoost secondary learner, not the primary): Brier baseline / raw / calibrated 0.0646 / 0.0342 / 0.0343; ECE raw / calibrated 0.0128 / 0.0145; calibrated AUC 0.9321._

## 3. Grade reliability (deployed-model backtest, held-out n = 1182)

| Metric | Value |
|---|---|
| Grades inside Wilson 95% | 9 of 10 |
| Sparse grades (n < 30) | none |
| Failing grades | B (realised 0.167 vs expected 0.083, under-predicts risk) |

## 4. Sufficiency (governing basis: candidate pool)

| Metric | Value |
|---|---|
| Events / rows | 410 / 5,910 |
| Pool EPV (P = 64) | 6.4 |
| Riley margin on the pool (met) | 2.05x (yes) |
| Selected model EPV / Riley margin (informational) | 16.4 / 5.22 |

## 5. Stability and parsimony

| Metric | Value |
|---|---|
| Players confirmed above the shadow bar | 19 of 19 |
| Weakest confirmed player (x the bar) / lowest confirmation frequency | 1.74x / 0.9680 |
| Players selected (columns) | 4 (25) |
| Gini retained vs full model / DeLong p / relative loss | 98.6% / 0.2554 / 1.41% |

## 6. Integrity

| Metric | Value |
|---|---|
| Governed (gates sealed) | G0, G1, G2, G3, G4, G5, GF |
| GF verdict | GO-WITH-CONDITIONS |
| Checklist: satisfied / partial / gap | 4 / 6 / 0 |
| Columns whose blanks track the outcome (beyond Bonferroni) | 9 |
| Look-ahead phrase hits in definitions / sentinel flags raised | 1 / 3 |
| Adverse-impact ratio | n/a |

## Bars (existing, cited; n/a = not applicable)

| Bar | Cleared | Source |
|---|---|---|
| AUC at or above the tier floor | yes | tier floor 0.7 |
| Selection tolerance met (DeLong p >= 0.05, loss <= 5%) | yes | pre-registered selection rule |
| Per-grade backtest: every grade inside Wilson 95% | **NO** | Basel CRE36.122-123 |
| Hosmer-Lemeshow (10 groups) not rejected | yes | alpha 0.05 |
| Pool EPV at least 10 | **NO** | Peduzzi 1996 |
| Riley minimum met on the candidate pool | yes | Riley et al. 2020 |
| No sparse grade (every grade n >= 30) | yes | backtest rule |
| Four-fifths rule (fairness) | n/a | only where protected attributes exist |
| No must-have checklist GAP | yes | AEGIS section 8 |
