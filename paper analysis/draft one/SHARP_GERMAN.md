# german_credit_eligible - Methodology v3 results

Rows: 1000 | Raw columns: 17 | Event rate: 0.3000

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `checking_status` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `months_duration` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `credit_history` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `purpose` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `credit_amount` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `savings_status` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `employment_since` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `installment_rate` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `other_debtors` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `residence_since` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `property` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `other_installment_plans` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `housing` | proxy_risk | origination | Housing/residential tenure - correlated with protected characteristics; treat with care. Includes the RES abbreviation used in several credit-scoring datasets. |
| `existing_credits` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `job` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `people_liable` | proxy_risk | origination | Household composition - proxy for familial status / sex. Includes the common credit-scoring abbreviations NKID (number of children) and DEP (dependents). |
| `telephone` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| checking_status | 0.6660 | 0.6660 | 0.6660 | 0.6660 | False | False | 0.3517 | 18.9000 | True | none |  | True |
| credit_history | 0.2918 | 0.2932 | 0.2932 | 0.2932 | False | False | 0.2478 | 26.4000 | True | none |  | True |
| months_duration | 0.2585 | 0.2162 | 0.2465 | 0.3041 | False | False | 0.2265 | 17.1000 | True | none |  | True |
| savings_status | 0.1960 | 0.1960 | 0.1960 | 0.1960 | False | False | 0.1900 | 14.4000 | True | none |  | True |
| purpose | 0.1545 | 0.1692 | 0.1692 | 0.1692 | False | False | 0.1754 | 15.0000 | True | none |  | True |
| credit_amount | 0.1203 | 0.0934 | 0.1136 | 0.2003 | False | True | 0.1665 | 15.0000 | True | model_check_shape |  | True |
| property | 0.1126 | 0.1126 | 0.1126 | 0.1126 | False | False | 0.1540 | 46.2000 | True | none |  | True |
| employment_since | 0.0864 | 0.0864 | 0.0864 | 0.0864 | False | False | 0.1355 | 18.6000 | True | none |  | True |
| housing | 0.0833 | 0.0833 | 0.0833 | 0.0833 | False | False | 0.1349 | 32.4000 | True | none |  | True |
| other_installment_plans | 0.0576 | 0.0576 | 0.0576 | 0.0576 | False | False | 0.1133 | 14.1000 | True | none |  | True |
| other_debtors | 0.0320 | 0.0320 | 0.0320 | 0.0320 | False | False | 0.0815 | 12.3000 | True | none |  | True |
| installment_rate | 0.0263 | 0.0256 | 0.0256 | 0.0256 | False | False | 0.0740 | 40.8000 | True | none |  | True |
| existing_credits | 0.0114 | 0.0036 | 0.0036 | 0.0036 | False | False | 0.0484 | 10.2000 | True | none |  | False |
| job | 0.0088 | 0.0088 | 0.0088 | 0.0088 | False | False | 0.0434 | 6.6000 | True | none |  | False |
| telephone | 0.0064 | 0.0064 | 0.0064 | 0.0064 | False | False | 0.0342 | 121.2000 | True | none |  | False |
| residence_since | 0.0036 | 0.0002 | 0.0006 | 0.0006 | False | False | 0.0274 | 39.0000 | True | none |  | False |
| people_liable | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0000 | 46.5000 | True | none |  | False |

Candidates passing Stage 1: 12 of 17.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| checking_status | 1 | False | 0.08626 | 0.00327 | 1.00000 | True | 0.00000 | 1.86540 |
| credit_history | 1 | False | 0.03994 | 0.00200 | 1.00000 | True | 0.00000 | 1.41522 |
| months_duration | 1 | False | 0.03286 | 0.00224 | 1.00000 | True | 0.00000 | 1.03910 |
| savings_status | 1 | False | 0.02832 | 0.00191 | 1.00000 | True | 0.00000 | 1.04712 |
| purpose | 1 | False | 0.02479 | 0.00171 | 1.00000 | True | 0.00000 | 1.02506 |
| credit_amount | 1 | False | 0.01797 | 0.00153 | 1.00000 | True | 0.00000 | 0.82920 |
| employment_since | 1 | False | 0.01338 | 0.00139 | 1.00000 | True | 0.00000 | 0.67988 |
| housing | 1 | False | 0.01020 | 0.00113 | 1.00000 | True | 0.00000 | 0.63668 |
| property | 1 | False | 0.00840 | 0.00119 | 0.99950 | True | 0.00000 | 0.49878 |
| other_installment_plans | 1 | False | 0.00831 | 0.00079 | 1.00000 | True | 0.00000 | 0.73939 |
| __shadow__5_savings_status | 1 | True | 0.00543 | 0.00057 | 0.99850 | False | 0.00000 | 0.67667 |
| installment_rate | 1 | False | 0.00376 | 0.00048 | 0.07700 | False | 0.00000 | 0.55011 |
| __shadow__2_installment_rate | 1 | True | 0.00356 | 0.00032 | 0.00000 | False | 0.00000 | 0.77479 |
| __shadow__3_checking_status | 1 | True | 0.00305 | 0.00052 | 0.00150 | False | 0.00000 | 0.41455 |
| __shadow__7_property | 1 | True | 0.00081 | 0.00040 | 0.00000 | False | 0.05348 | 0.14186 |
| __shadow__9_housing | 1 | True | 0.00078 | 0.00045 | 0.00000 | False | 0.09356 | 0.12238 |
| __shadow__0_months_duration | 1 | True | -0.00036 | 0.00036 | 0.00000 | False | 0.31558 | -0.07114 |
| other_debtors | 1 | False | -0.00040 | 0.00039 | 0.00000 | False | 0.31558 | -0.07223 |
| __shadow__1_credit_amount | 1 | True | -0.00298 | 0.00023 | 0.00000 | False | 0.00000 | -0.90006 |
| __shadow__6_purpose | 1 | True | -0.00334 | 0.00024 | 0.00000 | False | 0.00000 | -0.96764 |
| __shadow__4_credit_history | 1 | True | -0.00402 | 0.00040 | 0.00000 | False | 0.00000 | -0.70981 |
| __shadow__8_employment_since | 1 | True | -0.00451 | 0.00030 | 0.00000 | False | 0.00000 | -1.08002 |

Shadow bar (95th pct of 10 shadow players): **0.00459**. Mode: sampled. Subsets evaluated: 3698. Model fits: 18485.

Implementation audit (efficiency property): sum of Shapley values 0.272214 vs v(full)-v(empty) 0.272214, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | checking_status | 1 | 0.3602 | [0.2891, 0.4302] | 0.3671 | 0.6382 | 0.1876 | 35.03% | 0.0000 |
| 2 | credit_history | 2 | 0.4519 | [0.3845, 0.5200] | 0.3671 | 0.6881 | 0.1800 | 18.49% | 0.0000 |
| 3 | months_duration | 3 | 0.5040 | [0.4378, 0.5670] | 0.4057 | 0.7093 | 0.1758 | 9.09% | 0.0083 |
| 4 | savings_status | 4 | 0.5156 | [0.4493, 0.5810] | 0.4057 | 0.7188 | 0.1730 | 7.00% | 0.0193 |
| 5 | purpose | 5 | 0.5317 | [0.4701, 0.5923] | 0.4200 | 0.7221 | 0.1721 | 4.10% | 0.0613 |
| 6 | credit_amount | 6 | 0.5420 | [0.4834, 0.6030] | 0.4405 | 0.7256 | 0.1716 | 2.25% | 0.2130 |
| 7 | employment_since | 7 | 0.5491 | [0.4885, 0.6067] | 0.4362 | 0.7260 | 0.1716 | 0.97% | 0.4341 |
| 8 | housing | 8 | 0.5519 | [0.4905, 0.6091] | 0.4571 | 0.7290 | 0.1710 | 0.46% | 0.6435 |
| 9 | property | 9 | 0.5498 | [0.4884, 0.6081] | 0.4662 | 0.7296 | 0.1712 | 0.83% | 0.3069 |
| 10 | other_installment_plans | 10 | 0.5544 | [0.4943, 0.6108] | 0.4610 | 0.7288 | 0.1711 | 0.00% | 1.0000 |

**Selected k = 5** (5 columns, Gini 0.5317, relative loss 4.10%, DeLong p = 0.0613). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`checking_status`, `credit_history`, `months_duration`, `savings_status`, `purpose`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.2100 | 0.1636 | **0.1639** |
| ECE | - | 0.0534 | **0.0513** |

## Stage 4b - per-grade calibration backtest (AEGIS condition GC4; CRE36.122-123)

Added 2026-10-13 to discharge AEGIS condition GC4. Held-out 80/20 stratified split (`random_state=42`),
selected 5-col WOE-logistic calibrated PD, mapped to the internal master scale. Test n=200, event 0.30,
held-out AUC 0.7814.

| Grade | n | Expected PD | Realised | Realised 95% CI (Wilson) | Within? |
|---|--:|--:|--:|---|:--:|
| AAA | 2 | 0.0% | 0.0% | [0.0%, 65.8%] | OK |
| BBB | 11 | 2.4% | 0.0% | [0.0%, 25.9%] | OK |
| BB | 34 | 6.2% | 14.7% | [6.4%, 30.1%] | REVIEW (thin cell, under-predict) |
| B | 18 | 9.9% | 16.7% | [5.8%, 39.2%] | OK |
| CCC | 16 | 15.3% | 12.5% | [3.5%, 36.0%] | OK |
| CC | 39 | 22.9% | 15.4% | [7.2%, 29.7%] | OK |
| C | 53 | 47.0% | 47.2% | [34.4%, 60.3%] | OK |
| D | 27 | 71.3% | 70.4% | [51.5%, 84.1%] | OK |

**Overall held-out ECE = 0.0334; Hosmer-Lemeshow chi2=4.50, df=3, p=0.212 => calibration not rejected**
(more comfortably than HMEQ's p=0.069). 7/8 occupied grades pass. The wide per-grade CIs reflect the small
sample (200 test rows across 8 grades, 2-53 per cell) and are the quantified estimation uncertainty that
motivates a small-sample Margin of Conservatism (EBA Category C, R6). Re-run on larger/fresh data at deployment.
