# HMEQ - Methodology v3 results

Rows: 5960 | Raw columns: 12 | Event rate: 0.1995

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `LOAN` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `MORTDUE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `VALUE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `REASON` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `JOB` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `YOJ` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DEROG` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `DELINQ` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `CLAGE` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NINQ` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `CLNO` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `DEBTINC` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEBTINC | 1.8305 | 1.7382 | 1.8693 | 1.9694 | False | False | 0.5621 | 93.5639 | True | none |  | True |
| DELINQ | 0.5653 | 0.4194 | 0.4194 | 0.4524 | False | False | 0.3343 | 109.1247 | True | none |  | True |
| VALUE | 0.4464 | 0.4149 | 0.4679 | 0.5061 | False | False | 0.2820 | 22.3436 | True | none |  | True |
| DEROG | 0.3859 | 0.0364 | 0.2766 | 0.2766 | False | False | 0.2811 | 57.8540 | True | none |  | True |
| CLAGE | 0.2327 | 0.2224 | 0.2338 | 0.2501 | False | False | 0.1895 | 61.4450 | True | none |  | True |
| NINQ | 0.1732 | 0.1445 | 0.1656 | 0.1672 | False | False | 0.1808 | 78.2027 | True | none |  | True |
| LOAN | 0.1584 | 0.0972 | 0.1602 | 0.2270 | False | True | 0.1759 | 59.6495 | True | model_check_shape |  | True |
| JOB | 0.1230 | 0.1237 | 0.1237 | 0.1237 | False | False | 0.1345 | 55.6596 | True | none |  | True |
| YOJ | 0.0664 | 0.0443 | 0.0711 | 0.0959 | False | False | 0.0988 | 97.3544 | True | none |  | True |
| CLNO | 0.0463 | 0.0257 | 0.0639 | 0.0867 | False | True | 0.0923 | 44.2883 | True | model_check_shape |  | True |
| MORTDUE | 0.0436 | 0.0520 | 0.0533 | 0.0868 | False | False | 0.0852 | 103.3393 | True | none |  | True |
| REASON | 0.0086 | 0.0086 | 0.0086 | 0.0086 | False | False | 0.0375 | 50.2732 | True | none |  | False |

Candidates passing Stage 1: 11 of 12.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| DEBTINC | 1 | False | 0.15040 | 0.00729 | 1.00000 | True | 0.00000 | 1.88220 |
| DELINQ | 1 | False | 0.07180 | 0.00467 | 1.00000 | True | 0.00000 | 1.40356 |
| DEROG | 1 | False | 0.03797 | 0.00351 | 1.00000 | True | 0.00000 | 0.98804 |
| CLAGE | 1 | False | 0.03289 | 0.00330 | 1.00000 | True | 0.00000 | 0.90908 |
| grp[MORTDUE+VALUE] | 2 | False | 0.02841 | 0.00242 | 1.00000 | True | 0.00000 | 1.07116 |
| NINQ | 1 | False | 0.02158 | 0.00292 | 1.00000 | True | 0.00000 | 0.67532 |
| JOB | 1 | False | 0.02151 | 0.00218 | 1.00000 | True | 0.00000 | 0.90134 |
| LOAN | 1 | False | 0.01544 | 0.00222 | 1.00000 | True | 0.00000 | 0.63438 |
| YOJ | 1 | False | 0.01480 | 0.00189 | 1.00000 | True | 0.00000 | 0.71320 |
| CLNO | 1 | False | 0.01227 | 0.00105 | 1.00000 | True | 0.00000 | 1.06862 |
| __shadow__2_CLAGE | 1 | True | 0.00023 | 0.00008 | 0.46300 | False | 0.00324 | 0.27825 |
| __shadow__3_YOJ | 1 | True | 0.00021 | 0.00022 | 0.44050 | False | 0.34850 | 0.08990 |
| __shadow__5_VALUE | 1 | True | 0.00009 | 0.00013 | 0.09650 | False | 0.50555 | 0.06096 |
| __shadow__4_MORTDUE | 1 | True | -0.00063 | 0.00012 | 0.00000 | False | 0.00000 | -0.49855 |
| __shadow__1_DEROG | 1 | True | -0.00081 | 0.00008 | 0.00000 | False | 0.00000 | -0.96541 |
| __shadow__0_DELINQ | 1 | True | -0.00082 | 0.00019 | 0.00000 | False | 0.00004 | -0.39488 |

Shadow bar (95th pct of 6 shadow players): **0.00023**. Mode: sampled. Subsets evaluated: 1483. Model fits: 7410.

Implementation audit (efficiency property): sum of Shapley values 0.405349 vs v(full)-v(empty) 0.405349, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | DEBTINC | 1 | 0.6341 | [0.6026, 0.6630] | 0.5774 | 0.8005 | 0.1095 | 22.04% | 0.0000 |
| 2 | DELINQ | 2 | 0.7142 | [0.6863, 0.7396] | 0.6031 | 0.8379 | 0.1016 | 12.18% | 0.0000 |
| 3 | DEROG | 3 | 0.7373 | [0.7093, 0.7606] | 0.6294 | 0.8494 | 0.0976 | 9.34% | 0.0000 |
| 4 | CLAGE | 4 | 0.7780 | [0.7547, 0.7987] | 0.6323 | 0.8664 | 0.0927 | 4.33% | 0.0000 |
| 5 | grp[MORTDUE+VALUE] | 6 | 0.7971 | [0.7758, 0.8179] | 0.6462 | 0.8763 | 0.0889 | 1.99% | 0.0000 |
| 6 | NINQ | 7 | 0.7978 | [0.7755, 0.8187] | 0.6448 | 0.8767 | 0.0882 | 1.90% | 0.0000 |
| 7 | JOB | 8 | 0.8052 | [0.7846, 0.8241] | 0.6514 | 0.8779 | 0.0871 | 0.99% | 0.0013 |
| 8 | LOAN | 9 | 0.8057 | [0.7848, 0.8243] | 0.6434 | 0.8783 | 0.0869 | 0.93% | 0.0012 |
| 9 | YOJ | 10 | 0.8074 | [0.7866, 0.8261] | 0.6502 | 0.8795 | 0.0865 | 0.73% | 0.0006 |
| 10 | CLNO | 11 | 0.8133 | [0.7923, 0.8316] | 0.6537 | 0.8826 | 0.0861 | 0.00% | 1.0000 |

**Selected k = 10** (11 columns, Gini 0.8133, relative loss 0.00%, DeLong p = 1.0000). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`DEBTINC`, `DELINQ`, `DEROG`, `CLAGE`, `MORTDUE`, `VALUE`, `NINQ`, `JOB`, `LOAN`, `YOJ`, `CLNO`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1598 | 0.0710 | **0.0687** |
| ECE | - | 0.0235 | **0.0157** |
