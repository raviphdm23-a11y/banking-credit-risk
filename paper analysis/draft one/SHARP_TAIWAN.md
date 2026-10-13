# taiwan_eligible - Methodology v3 results

Rows: 30000 | Raw columns: 20 | Event rate: 0.2212

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `LIMIT_BAL` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `EDUCATION` | proxy_risk | origination | Education - recognised proxy for race/national origin and age. |
| `PAY_0` | permissible | near_target | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_2` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_3` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_4` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_5` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_6` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `BILL_AMT1` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `BILL_AMT2` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `BILL_AMT3` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `BILL_AMT4` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `BILL_AMT5` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `BILL_AMT6` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_AMT1` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_AMT2` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_AMT3` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_AMT4` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_AMT5` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PAY_AMT6` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAY_0 | 0.8740 | 0.8694 | 0.8698 | 0.8698 | False | False | 0.4223 | 102.4156 | True | none |  | True |
| PAY_2 | 0.5437 | 0.5417 | 0.5424 | 0.5424 | False | False | 0.3386 | 113.0332 | True | none |  | True |
| PAY_3 | 0.4139 | 0.4090 | 0.4109 | 0.4109 | False | False | 0.2950 | 87.1528 | True | none |  | True |
| PAY_4 | 0.3633 | 0.3552 | 0.3592 | 0.3592 | False | False | 0.2783 | 77.6412 | True | none |  | True |
| PAY_5 | 0.3376 | 0.3293 | 0.3293 | 0.3332 | False | False | 0.2699 | 75.6504 | True | none |  | True |
| PAY_6 | 0.2918 | 0.2817 | 0.2884 | 0.2884 | False | False | 0.2501 | 69.2356 | True | none |  | True |
| LIMIT_BAL | 0.1787 | 0.1553 | 0.1781 | 0.1802 | False | False | 0.1762 | 356.1320 | True | none |  | True |
| PAY_AMT1 | 0.1684 | 0.1548 | 0.1611 | 0.1725 | False | False | 0.1696 | 331.8000 | True | none |  | True |
| PAY_AMT2 | 0.1583 | 0.1395 | 0.1475 | 0.1609 | False | False | 0.1589 | 331.8000 | True | none |  | True |
| PAY_AMT3 | 0.1267 | 0.1168 | 0.1227 | 0.1337 | False | False | 0.1470 | 334.4544 | True | none |  | True |
| PAY_AMT4 | 0.0982 | 0.0822 | 0.0899 | 0.1033 | False | False | 0.1277 | 331.8000 | True | none |  | True |
| PAY_AMT6 | 0.0945 | 0.0805 | 0.0903 | 0.0984 | False | False | 0.1239 | 341.0904 | True | none |  | True |
| PAY_AMT5 | 0.0845 | 0.0689 | 0.0811 | 0.0895 | False | False | 0.1171 | 335.7816 | True | none |  | True |
| EDUCATION | 0.0373 | 0.0160 | 0.0363 | 0.0363 | True | False | 0.0731 | 103.5216 | True | model_check_shape |  | True |
| BILL_AMT1 | 0.0080 | 0.0102 | 0.0120 | 0.0169 | False | True | 0.0371 | 420.7224 | True | model_check_shape |  | False |
| BILL_AMT2 | 0.0048 | 0.0103 | 0.0111 | 0.0141 | False | True | 0.0286 | 331.8000 | True | model_check_shape |  | False |
| BILL_AMT3 | 0.0045 | 0.0095 | 0.0103 | 0.0148 | False | True | 0.0275 | 331.8000 | True | model_check_shape |  | False |
| BILL_AMT5 | 0.0043 | 0.0125 | 0.0141 | 0.0190 | False | True | 0.0271 | 920.4132 | True | model_check_shape |  | False |
| BILL_AMT4 | 0.0030 | 0.0102 | 0.0110 | 0.0170 | False | True | 0.0224 | 332.0212 | True | model_check_shape |  | False |
| BILL_AMT6 | 0.0026 | 0.0134 | 0.0192 | 0.0252 | True | True | 0.0209 | 663.6000 | True | model_check_shape |  | True |

Candidates passing Stage 1: 15 of 20.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| PAY_0 | 1 | False | 0.08891 | 0.00417 | 1.00000 | True | 0.00000 | 1.50707 |
| grp[PAY_2+PAY_3+PAY_4+PAY_5+PAY_6] | 5 | False | 0.05728 | 0.00414 | 1.00000 | True | 0.00000 | 0.97901 |
| LIMIT_BAL | 1 | False | 0.02140 | 0.00220 | 1.00000 | True | 0.00000 | 0.68918 |
| PAY_AMT2 | 1 | False | 0.02012 | 0.00235 | 1.00000 | True | 0.00000 | 0.60435 |
| PAY_AMT3 | 1 | False | 0.01643 | 0.00207 | 1.00000 | True | 0.00000 | 0.56140 |
| PAY_AMT4 | 1 | False | 0.01553 | 0.00203 | 1.00000 | True | 0.00000 | 0.54071 |
| PAY_AMT1 | 1 | False | 0.01532 | 0.00208 | 1.00000 | True | 0.00000 | 0.52130 |
| PAY_AMT6 | 1 | False | 0.01158 | 0.00175 | 1.00000 | True | 0.00000 | 0.46755 |
| PAY_AMT5 | 1 | False | 0.01086 | 0.00164 | 1.00000 | True | 0.00000 | 0.46767 |
| EDUCATION | 1 | False | 0.00679 | 0.00081 | 1.00000 | True | 0.00000 | 0.59552 |
| BILL_AMT6 | 1 | False | 0.00464 | 0.00046 | 1.00000 | True | 0.00000 | 0.72020 |
| __shadow__2_PAY_AMT4 | 1 | True | 0.00084 | 0.00016 | 0.99050 | False | 0.00000 | 0.36352 |
| __shadow__1_BILL_AMT6 | 1 | True | 0.00037 | 0.00009 | 0.00650 | False | 0.00007 | 0.29051 |
| __shadow__8_PAY_3 | 1 | True | 0.00032 | 0.00009 | 0.00300 | False | 0.00076 | 0.24487 |
| __shadow__4_PAY_AMT1 | 1 | True | 0.00003 | 0.00005 | 0.00000 | False | 0.50946 | 0.04673 |
| __shadow__6_PAY_AMT2 | 1 | True | -0.00004 | 0.00004 | 0.00000 | False | 0.42108 | -0.05951 |
| __shadow__0_PAY_AMT5 | 1 | True | -0.00013 | 0.00005 | 0.00000 | False | 0.00727 | -0.19421 |
| __shadow__7_PAY_2 | 1 | True | -0.00017 | 0.00003 | 0.00000 | False | 0.00000 | -0.36471 |
| __shadow__5_PAY_AMT3 | 1 | True | -0.00017 | 0.00003 | 0.00000 | False | 0.00000 | -0.38923 |
| __shadow__3_PAY_AMT6 | 1 | True | -0.00026 | 0.00003 | 0.00000 | False | 0.00000 | -0.69897 |
| __shadow__9_PAY_4 | 1 | True | -0.00029 | 0.00003 | 0.00000 | False | 0.00000 | -0.63736 |

Shadow bar (95th pct of 10 shadow players): **0.00063**. Mode: sampled. Subsets evaluated: 3454. Model fits: 17265.

Implementation audit (efficiency property): sum of Shapley values 0.269368 vs v(full)-v(empty) 0.269368, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | PAY_0 | 1 | 0.4183 | [0.4049, 0.4334] | 0.3717 | 0.7011 | 0.1416 | 22.46% | 0.0000 |
| 2 | grp[PAY_2+PAY_3+PAY_4+PAY_5+PAY_6] | 6 | 0.4895 | [0.4767, 0.5039] | 0.4020 | 0.7291 | 0.1385 | 9.26% | 0.0000 |
| 3 | LIMIT_BAL | 7 | 0.5163 | [0.5041, 0.5306] | 0.4047 | 0.7359 | 0.1377 | 4.30% | 0.0000 |
| 4 | PAY_AMT2 | 8 | 0.5301 | [0.5172, 0.5436] | 0.4087 | 0.7377 | 0.1373 | 1.74% | 0.0000 |
| 5 | PAY_AMT3 | 9 | 0.5344 | [0.5221, 0.5487] | 0.4079 | 0.7394 | 0.1372 | 0.93% | 0.0015 |
| 6 | PAY_AMT4 | 10 | 0.5351 | [0.5225, 0.5495] | 0.4076 | 0.7399 | 0.1371 | 0.80% | 0.0020 |
| 7 | PAY_AMT1 | 11 | 0.5369 | [0.5241, 0.5515] | 0.4078 | 0.7408 | 0.1371 | 0.48% | 0.0338 |
| 8 | PAY_AMT6 | 12 | 0.5367 | [0.5238, 0.5515] | 0.4076 | 0.7407 | 0.1371 | 0.51% | 0.0175 |
| 9 | PAY_AMT5 | 13 | 0.5367 | [0.5240, 0.5516] | 0.4075 | 0.7407 | 0.1371 | 0.52% | 0.0145 |
| 10 | EDUCATION | 14 | 0.5383 | [0.5260, 0.5533] | 0.4081 | 0.7410 | 0.1370 | 0.21% | 0.1300 |
| 11 | BILL_AMT6 | 15 | 0.5395 | [0.5269, 0.5543] | 0.4086 | 0.7414 | 0.1369 | 0.00% | 1.0000 |

**Selected k = 10** (14 columns, Gini 0.5383, relative loss 0.21%, DeLong p = 0.1300). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`PAY_0 [near_target]`, `PAY_2`, `PAY_3`, `PAY_4`, `PAY_5`, `PAY_6`, `LIMIT_BAL`, `PAY_AMT2`, `PAY_AMT3`, `PAY_AMT4`, `PAY_AMT1`, `PAY_AMT6`, `PAY_AMT5`, `EDUCATION [proxy_risk]`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1723 | 0.1359 | **0.1357** |
| ECE | - | 0.0132 | **0.0117** |

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
| `EDUCATION` | proxy_risk | Education - recognised proxy for race/national origin and age. |

**Availability caveat (near_target):** `PAY_0`. Results including these are not an origination-time (application) model; report with and without them (METHODOLOGY v3 s3.3).
