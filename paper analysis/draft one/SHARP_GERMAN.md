<!-- PROVENANCE: South German Credit (Groemping 2019, UCI #522) — the error-corrected
recoding of the Statlog German Credit data. Supersedes the archived Statlog run
(see archive/german_statlog_superseded/). 1,000 loans, 30.0% bad rate, 20 variables;
3 protected attributes excluded at G0 -> 17-feature pool. Source CSV:
data/ml_lab/datasets/south_german_credit_en.csv. Seed 42. -->

# GERMAN - Methodology v3 results

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
| checking_status | 0.6660 | 0.6394 | 0.6394 | 0.6394 | False | False | 0.3517 | 18.9000 | True | none |  | True |
| credit_history | 0.2918 | 0.1341 | 0.1791 | 0.2918 | False | False | 0.2478 | 26.4000 | True | none |  | True |
| months_duration | 0.2585 | 0.2162 | 0.2465 | 0.3041 | False | False | 0.2265 | 17.1000 | True | none |  | True |
| savings_status | 0.1960 | 0.0910 | 0.1909 | 0.1944 | False | False | 0.1900 | 14.4000 | True | none |  | True |
| purpose | 0.1545 | 0.0655 | 0.0662 | 0.0725 | False | False | 0.1754 | 15.0000 | True | none |  | True |
| credit_amount | 0.1203 | 0.0934 | 0.1138 | 0.2016 | False | True | 0.1665 | 15.0000 | True | model_check_shape |  | True |
| property | 0.1126 | 0.0834 | 0.0834 | 0.0834 | False | False | 0.1540 | 46.2000 | True | none |  | True |
| employment_since | 0.0864 | 0.0853 | 0.0853 | 0.0853 | False | False | 0.1355 | 18.6000 | True | none |  | True |
| housing | 0.0854 | 0.0313 | 0.0313 | 0.0313 | False | False | 0.1367 | 32.1000 | True | none |  | True |
| other_installment_plans | 0.0576 | 0.0000 | 0.0000 | 0.0576 | True | False | 0.1133 | 14.1000 | True | model_check_shape |  | True |
| other_debtors | 0.0320 | 0.0000 | 0.0000 | 0.0000 | True | False | 0.0815 | 12.3000 | True | model_check_shape |  | True |
| installment_rate | 0.0263 | 0.0256 | 0.0256 | 0.0256 | False | False | 0.0740 | 40.8000 | True | none |  | True |
| existing_credits | 0.0114 | 0.0036 | 0.0036 | 0.0036 | False | False | 0.0484 | 10.2000 | True | none |  | False |
| job | 0.0088 | 0.0081 | 0.0081 | 0.0081 | False | False | 0.0434 | 6.6000 | True | none |  | False |
| telephone | 0.0064 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0342 | 121.2000 | True | none |  | False |
| residence_since | 0.0036 | 0.0002 | 0.0006 | 0.0006 | False | False | 0.0274 | 39.0000 | True | none |  | False |
| people_liable | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0000 | 46.5000 | True | none |  | False |

Candidates passing Stage 1: 12 of 17.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| checking_status | 1 | False | 0.09919 | 0.00360 | 1.00000 | True | 0.00000 | 1.94954 |
| credit_history | 1 | False | 0.03754 | 0.00234 | 1.00000 | True | 0.00000 | 1.13292 |
| months_duration | 1 | False | 0.03365 | 0.00230 | 1.00000 | True | 0.00000 | 1.03382 |
| savings_status | 1 | False | 0.02842 | 0.00203 | 1.00000 | True | 0.00000 | 0.99089 |
| credit_amount | 1 | False | 0.02075 | 0.00166 | 1.00000 | True | 0.00000 | 0.88358 |
| purpose | 1 | False | 0.01634 | 0.00123 | 1.00000 | True | 0.00000 | 0.93612 |
| property | 1 | False | 0.01372 | 0.00153 | 1.00000 | True | 0.00000 | 0.63284 |
| employment_since | 1 | False | 0.01141 | 0.00128 | 1.00000 | True | 0.00000 | 0.63009 |
| housing | 1 | False | 0.00911 | 0.00122 | 1.00000 | True | 0.00000 | 0.52957 |
| other_debtors | 1 | False | 0.00716 | 0.00048 | 1.00000 | True | 0.00000 | 1.05580 |
| other_installment_plans | 1 | False | 0.00525 | 0.00084 | 0.99900 | True | 0.00000 | 0.44218 |
| installment_rate | 1 | False | 0.00294 | 0.00054 | 0.86350 | True | 0.00000 | 0.38425 |
| __shadow__6_credit_amount | 1 | True | 0.00229 | 0.00056 | 0.58400 | False | 0.00009 | 0.28749 |
| __shadow__5_months_duration | 1 | True | 0.00196 | 0.00049 | 0.29650 | False | 0.00013 | 0.27997 |
| __shadow__0_checking_status | 1 | True | 0.00163 | 0.00051 | 0.11950 | False | 0.00197 | 0.22492 |
| __shadow__9_credit_history | 1 | True | 0.00014 | 0.00026 | 0.00000 | False | 0.60720 | 0.03641 |
| __shadow__2_other_debtors | 1 | True | -0.00022 | 0.00007 | 0.00000 | False | 0.00333 | -0.21119 |
| __shadow__4_housing | 1 | True | -0.00044 | 0.00015 | 0.00000 | False | 0.00298 | -0.21476 |
| __shadow__7_installment_rate | 1 | True | -0.00099 | 0.00019 | 0.00000 | False | 0.00000 | -0.35925 |
| __shadow__3_property | 1 | True | -0.00320 | 0.00023 | 0.00000 | False | 0.00000 | -1.00186 |
| __shadow__1_savings_status | 1 | True | -0.00567 | 0.00024 | 0.00000 | False | 0.00000 | -1.65395 |
| __shadow__8_employment_since | 1 | True | -0.00593 | 0.00070 | 0.00000 | False | 0.00000 | -0.60002 |

Shadow bar (95th pct of 10 shadow players): **0.00214**. Mode: sampled. Subsets evaluated: 3698. Model fits: 18485.

Implementation audit (efficiency property): sum of Shapley values 0.275024 vs v(full)-v(empty) 0.275024, abs diff 5.55e-17. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | checking_status | 1 | 0.3818 | [0.3046, 0.4530] | 0.3671 | 0.6487 | 0.1856 | 32.79% | 0.0000 |
| 2 | credit_history | 2 | 0.4645 | [0.3871, 0.5335] | 0.3748 | 0.6915 | 0.1781 | 18.24% | 0.0000 |
| 3 | months_duration | 3 | 0.5173 | [0.4498, 0.5751] | 0.4057 | 0.7146 | 0.1736 | 8.96% | 0.0081 |
| 4 | savings_status | 4 | 0.5321 | [0.4686, 0.5915] | 0.4210 | 0.7275 | 0.1697 | 6.35% | 0.0331 |
| 5 | credit_amount | 5 | 0.5422 | [0.4738, 0.6006] | 0.4333 | 0.7315 | 0.1687 | 4.56% | 0.1074 |
| 6 | purpose | 6 | 0.5521 | [0.4924, 0.6092] | 0.4386 | 0.7308 | 0.1689 | 2.82% | 0.1827 |
| 7 | property | 7 | 0.5557 | [0.4958, 0.6134] | 0.4414 | 0.7340 | 0.1679 | 2.18% | 0.2823 |
| 8 | employment_since | 8 | 0.5632 | [0.5033, 0.6198] | 0.4510 | 0.7369 | 0.1679 | 0.87% | 0.5810 |
| 9 | housing | 9 | 0.5623 | [0.5029, 0.6184] | 0.4490 | 0.7366 | 0.1681 | 1.03% | 0.4788 |
| 10 | other_debtors | 10 | 0.5694 | [0.5078, 0.6260] | 0.4581 | 0.7409 | 0.1668 | -0.21% | 0.8693 |
| 11 | other_installment_plans | 11 | 0.5679 | [0.5067, 0.6243] | 0.4486 | 0.7395 | 0.1673 | 0.04% | 0.9714 |
| 12 | installment_rate | 12 | 0.5681 | [0.5032, 0.6228] | 0.4548 | 0.7404 | 0.1665 | 0.00% | 1.0000 |

**Selected k = 5** (5 columns, Gini 0.5422, relative loss 4.56%, DeLong p = 0.1074). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`checking_status`, `credit_history`, `months_duration`, `savings_status`, `credit_amount`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.2100 | 0.1764 | **0.1756** |
| ECE | - | 0.0839 | **0.0634** |
