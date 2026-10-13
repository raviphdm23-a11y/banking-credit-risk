# gmsc_eligible - Methodology v3 results

Rows: 149391 | Raw columns: 9 | Event rate: 0.0670

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `RevolvingUtilizationOfUnsecuredLines` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumberOfTime30-59DaysPastDueNotWorse` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `DebtRatio` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `MonthlyIncome` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `NumberOfOpenCreditLinesAndLoans` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumberOfTimes90DaysLate` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumberRealEstateLoansOrLines` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumberOfTime60-89DaysPastDueNotWorse` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumberOfDependents` | proxy_risk | origination | Household composition - proxy for familial status / sex. Includes the common credit-scoring abbreviations NKID (number of children) and DEP (dependents). |

**Sentinel leakage candidates (unresolved):** `NumberOfTime30-59DaysPastDueNotWorse`, `NumberOfTime60-89DaysPastDueNotWorse`, `NumberOfTimes90DaysLate` - see METHODOLOGY v3 s3.5.

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RevolvingUtilizationOfUnsecuredLines | 1.1129 | 1.0613 | 1.1190 | 1.1669 | False | False | 0.2873 | 500.4132 | True | none |  | True |
| NumberOfTimes90DaysLate | 0.8834 | 0.0000 | 0.0000 | 0.4846 | True | False | 0.3564 | 0.0670 | False | mann_whitney+model_check_shape | 0.0000 | True |
| NumberOfTime30-59DaysPastDueNotWorse | 0.7382 | 0.0000 | 0.4702 | 0.4853 | True | False | 0.2788 | 529.6246 | True | model_check_shape |  | True |
| NumberOfTime60-89DaysPastDueNotWorse | 0.6027 | 0.0000 | 0.0000 | 0.2649 | True | False | 0.2896 | 0.0670 | False | mann_whitney+model_check_shape | 0.0000 | True |
| NumberOfOpenCreditLinesAndLoans | 0.0801 | 0.0502 | 0.0710 | 0.0894 | False | False | 0.0811 | 602.4521 | True | none |  | True |
| MonthlyIncome | 0.0710 | 0.0692 | 0.0739 | 0.0788 | False | False | 0.0667 | 692.3644 | True | none |  | True |
| NumberRealEstateLoansOrLines | 0.0569 | 0.0123 | 0.0123 | 0.0186 | True | False | 0.0599 | 666.7709 | True | model_check_shape |  | True |
| NumberOfDependents | 0.0351 | 0.0169 | 0.0266 | 0.0272 | True | False | 0.0482 | 256.4710 | True | model_check_shape |  | True |
| DebtRatio | 0.0204 | 0.0601 | 0.0736 | 0.0787 | False | True | 0.0357 | 500.4132 | True | model_check_shape |  | True |

Candidates passing Stage 1: 9 of 9.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| RevolvingUtilizationOfUnsecuredLines | 1 | False | 0.11344 | 0.00568 | 1.00000 | True | 0.00000 | 1.41328 |
| NumberOfTime30-59DaysPastDueNotWorse | 1 | False | 0.07010 | 0.00433 | 1.00000 | True | 0.00000 | 1.14458 |
| NumberOfTimes90DaysLate | 1 | False | 0.06339 | 0.00376 | 1.00000 | True | 0.00000 | 1.19210 |
| NumberOfTime60-89DaysPastDueNotWorse | 1 | False | 0.03923 | 0.00281 | 1.00000 | True | 0.00000 | 0.98617 |
| MonthlyIncome | 1 | False | 0.01838 | 0.00176 | 1.00000 | True | 0.00000 | 0.73744 |
| NumberRealEstateLoansOrLines | 1 | False | 0.01493 | 0.00133 | 1.00000 | True | 0.00000 | 0.79172 |
| NumberOfDependents | 1 | False | 0.01302 | 0.00114 | 1.00000 | True | 0.00000 | 0.80905 |
| DebtRatio | 1 | False | 0.01041 | 0.00087 | 1.00000 | True | 0.00000 | 0.84133 |
| NumberOfOpenCreditLinesAndLoans | 1 | False | 0.00962 | 0.00118 | 1.00000 | True | 0.00000 | 0.57870 |
| __shadow__4_NumberOfOpenCreditLinesAndLoans | 1 | True | 0.00097 | 0.00014 | 1.00000 | False | 0.00000 | 0.47408 |
| __shadow__6_MonthlyIncome | 1 | True | 0.00040 | 0.00008 | 0.00000 | False | 0.00000 | 0.36422 |
| __shadow__2_NumberOfTime30-59DaysPastDueNotWorse | 1 | True | 0.00034 | 0.00005 | 0.00000 | False | 0.00000 | 0.45839 |
| __shadow__0_NumberOfTimes90DaysLate | 1 | True | -0.00001 | 0.00004 | 0.00000 | False | 0.76752 | -0.02093 |
| __shadow__3_RevolvingUtilizationOfUnsecuredLines | 1 | True | -0.00024 | 0.00004 | 0.00000 | False | 0.00000 | -0.38092 |
| __shadow__1_NumberOfTime60-89DaysPastDueNotWorse | 1 | True | -0.00040 | 0.00004 | 0.00000 | False | 0.00000 | -0.69491 |
| __shadow__9_NumberOfTimes90DaysLate | 1 | True | -0.00040 | 0.00004 | 0.00000 | False | 0.00000 | -0.79475 |
| __shadow__8_NumberOfDependents | 1 | True | -0.00041 | 0.00005 | 0.00000 | False | 0.00000 | -0.53520 |
| __shadow__7_DebtRatio | 1 | True | -0.00063 | 0.00008 | 0.00000 | False | 0.00000 | -0.54718 |
| __shadow__5_NumberRealEstateLoansOrLines | 1 | True | -0.00063 | 0.00011 | 0.00000 | False | 0.00000 | -0.41015 |

Shadow bar (95th pct of 10 shadow players): **0.00071**. Mode: sampled. Subsets evaluated: 3012. Model fits: 15055.

Implementation audit (efficiency property): sum of Shapley values 0.351520 vs v(full)-v(empty) 0.351520, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | RevolvingUtilizationOfUnsecuredLines | 1 | 0.5518 | [0.5415, 0.5612] | 0.4577 | 0.7448 | 0.0574 | 21.73% | 0.0000 |
| 2 | NumberOfTime30-59DaysPastDueNotWorse | 2 | 0.6346 | [0.6251, 0.6433] | 0.5062 | 0.7861 | 0.0542 | 9.99% | 0.0000 |
| 3 | NumberOfTimes90DaysLate | 3 | 0.6791 | [0.6701, 0.6873] | 0.5355 | 0.8114 | 0.0513 | 3.68% | 0.0000 |
| 4 | NumberOfTime60-89DaysPastDueNotWorse | 4 | 0.6942 | [0.6854, 0.7018] | 0.5434 | 0.8195 | 0.0507 | 1.54% | 0.0000 |
| 5 | MonthlyIncome | 5 | 0.6971 | [0.6881, 0.7047] | 0.5427 | 0.8206 | 0.0507 | 1.12% | 0.0000 |
| 6 | NumberRealEstateLoansOrLines | 6 | 0.6994 | [0.6907, 0.7070] | 0.5444 | 0.8216 | 0.0507 | 0.79% | 0.0000 |
| 7 | NumberOfDependents | 7 | 0.7014 | [0.6927, 0.7090] | 0.5415 | 0.8220 | 0.0506 | 0.51% | 0.0000 |
| 8 | DebtRatio | 8 | 0.7048 | [0.6963, 0.7121] | 0.5464 | 0.8232 | 0.0505 | 0.03% | 0.1249 |
| 9 | NumberOfOpenCreditLinesAndLoans | 9 | 0.7050 | [0.6965, 0.7123] | 0.5451 | 0.8232 | 0.0505 | 0.00% | 1.0000 |

**Selected k = 8** (8 columns, Gini 0.7048, relative loss 0.03%, DeLong p = 0.1249). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`RevolvingUtilizationOfUnsecuredLines`, `NumberOfTime30-59DaysPastDueNotWorse`, `NumberOfTimes90DaysLate`, `NumberOfTime60-89DaysPastDueNotWorse`, `MonthlyIncome`, `NumberRealEstateLoansOrLines`, `NumberOfDependents [proxy_risk]`, `DebtRatio`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.0625 | 0.0492 | **0.0491** |
| ECE | - | 0.0030 | **0.0034** |

## Regulatory eligibility

**Regulatory eligibility disclosure.** This analysis retains features that are prohibited or
proxy-prohibited inputs to consumer credit decisions in major jurisdictions (listed below). They are
retained because these are public research benchmark datasets and their inclusion preserves
comparability with the published literature on the same data. No model in this work is intended or
suitable for deployment in a live credit decision. Retention is a methodological choice for
comparability and is not an endorsement of such use. A fairness-constrained replication excluding
these features is planned.

Retained regulatory-ineligible features:

| Column | Tag | Basis |
|---|---|---|
| `NumberOfDependents` | proxy_risk | Household composition - proxy for familial status / sex. Includes the common credit-scoring abbreviations NKID (number of children) and DEP (dependents). |

## Stage 4b - per-grade calibration backtest (G4; CRE36.122-123)

Held-out 80/20 split (random_state=42), 8-col model, calibrated PD floored at 0.03%. Test n=29,879, AUC 0.8535.

| Grade | n | Expected | Realised | 95% CI | Within? |
|---|--:|--:|--:|---|:--:|
| AAA | 17 | 0.06% | 0.00% | [0.00%,18.43%] | OK |
| AA | 6459 | 0.69% | 0.76% | [0.57%,1.00%] | OK |
| A | 7602 | 1.33% | 1.30% | [1.07%,1.58%] | OK |
| BBB | 3785 | 2.60% | 2.80% | [2.32%,3.38%] | OK |
| BB | 4796 | 5.53% | 4.98% | [4.40%,5.64%] | OK |
| B | 3001 | 9.27% | 8.73% | [7.77%,9.79%] | OK |
| CCC | 1351 | 13.68% | 13.69% | [11.96%,15.63%] | OK |
| CC | 1471 | 25.69% | 25.63% | [23.46%,27.92%] | OK |
| C | 747 | 40.77% | 41.63% | [38.15%,45.20%] | OK |
| D | 650 | 59.86% | 57.54% | [53.71%,61.28%] | OK |

**ALL 10 grades pass; ECE 0.0023; Hosmer-Lemeshow chi2=12.41, df=8, p=0.134 => not rejected.** The cleanest
calibration of all runs, full grade spectrum, tight CIs (10,009 events). Confirms the archived CALIBRATION_NOTES
finding: GMSC's v2 mis-calibration (Brier worse than baseline) was caused by class reweighting; WOE-logistic
without reweighting calibrates cleanly (Brier 0.049 < baseline 0.063).
