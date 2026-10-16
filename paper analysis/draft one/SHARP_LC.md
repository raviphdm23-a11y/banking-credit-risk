# LC - Methodology v3 results

Rows: 39717 | Raw columns: 21 | Event rate: 0.1417

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `loan_amnt` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `funded_amnt` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `term` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `emp_length` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `home_ownership` | proxy_risk | origination | Housing/residential tenure - correlated with protected characteristics; treat with care. Includes the RES abbreviation used in several credit-scoring datasets. |
| `annual_inc` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `verification_status` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `purpose` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `addr_state` | proxy_risk | origination | Geography - recognised proxy for race/national origin (redlining risk). |
| `dti` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `delinq_2yrs` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `inq_last_6mths` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `mths_since_last_delinq` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `mths_since_last_record` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `open_acc` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `pub_rec` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `revol_bal` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `revol_util` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_acc` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `pub_rec_bankruptcies` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `credit_hist_years` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

**Sentinel leakage candidates (unresolved):** `mths_since_last_delinq` - see METHODOLOGY v3 s3.5.

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| term | 0.1576 | 0.0000 | 0.0000 | 0.0000 | True | False | 0.1460 | 1504.7553 | True | model_check_shape |  | True |
| revol_util | 0.0821 | 0.0781 | 0.0808 | 0.0899 | False | False | 0.0998 | 7.0839 | True | none |  | True |
| annual_inc | 0.0446 | 0.0422 | 0.0430 | 0.0471 | False | False | 0.0733 | 292.9888 | True | none |  | True |
| inq_last_6mths | 0.0443 | 0.0286 | 0.0286 | 0.0288 | False | False | 0.0749 | 83.0229 | True | none |  | True |
| purpose | 0.0320 | 0.0689 | 0.0689 | 0.0689 | False | False | 0.0603 | 309.8484 | True | none |  | True |
| loan_amnt | 0.0240 | 0.0214 | 0.0244 | 0.0287 | False | False | 0.0561 | 622.3887 | True | none |  | True |
| funded_amnt | 0.0223 | 0.0218 | 0.0239 | 0.0272 | False | False | 0.0538 | 532.5652 | True | none |  | True |
| pub_rec | 0.0202 | 0.0000 | 0.0000 | 0.0001 | True | False | 0.0541 | 8.5006 | True | model_check_shape |  | True |
| mths_since_last_record | 0.0197 | 0.0197 | 0.0197 | 0.0197 | False | False | 0.0529 | 193.6730 | True | none |  | False |
| dti | 0.0169 | 0.0166 | 0.0174 | 0.0188 | False | False | 0.0451 | 282.5047 | True | none |  | False |
| pub_rec_bankruptcies | 0.0161 | 0.0009 | 0.0009 | 0.0009 | False | False | 0.0481 | 98.7491 | True | none |  | False |
| verification_status | 0.0140 | 0.0140 | 0.0140 | 0.0140 | False | False | 0.0413 | 1414.9319 | True | none |  | False |
| addr_state | 0.0135 | 0.0393 | 0.0393 | 0.0393 | True | False | 0.0411 | 386.3542 | True | model_check_shape |  | True |
| emp_length | 0.0107 | 0.0091 | 0.0092 | 0.0112 | False | False | 0.0383 | 152.3032 | True | none |  | False |
| credit_hist_years | 0.0084 | 0.0043 | 0.0112 | 0.0138 | False | True | 0.0328 | 286.6133 | True | model_check_shape |  | False |
| total_acc | 0.0081 | 0.0075 | 0.0088 | 0.0118 | False | False | 0.0320 | 295.5390 | True | none |  | False |
| open_acc | 0.0071 | 0.0014 | 0.0065 | 0.0086 | False | False | 0.0306 | 297.2391 | True | none |  | False |
| home_ownership | 0.0056 | 0.0068 | 0.0068 | 0.0068 | False | False | 0.0260 | 14.3094 | True | none |  | False |
| mths_since_last_delinq | 0.0051 | 0.0044 | 0.0059 | 0.0075 | False | False | 0.0252 | 286.0466 | True | none |  | False |
| delinq_2yrs | 0.0036 | 0.0000 | 0.0026 | 0.0026 | False | False | 0.0219 | 142.9525 | True | none |  | False |
| revol_bal | 0.0028 | 0.0025 | 0.0043 | 0.0053 | False | True | 0.0184 | 281.2296 | True | model_check_shape |  | False |

Candidates passing Stage 1: 9 of 21.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| term | 1 | False | 0.04943 | 0.00153 | 1.00000 | True | 0.00000 | 2.28639 |
| revol_util | 1 | False | 0.03547 | 0.00149 | 1.00000 | True | 0.00000 | 1.68750 |
| annual_inc | 1 | False | 0.02876 | 0.00108 | 1.00000 | True | 0.00000 | 1.87468 |
| inq_last_6mths | 1 | False | 0.02252 | 0.00099 | 1.00000 | True | 0.00000 | 1.61329 |
| purpose | 1 | False | 0.01361 | 0.00084 | 1.00000 | True | 0.00000 | 1.15208 |
| grp[funded_amnt+loan_amnt] | 2 | False | 0.01301 | 0.00092 | 1.00000 | True | 0.00000 | 1.00455 |
| addr_state | 1 | False | 0.00816 | 0.00059 | 1.00000 | True | 0.00000 | 0.97865 |
| pub_rec | 1 | False | 0.00699 | 0.00035 | 1.00000 | True | 0.00000 | 1.42463 |
| __shadow__4_revol_util | 1 | True | 0.00116 | 0.00013 | 0.94650 | False | 0.00000 | 0.62340 |
| __shadow__7_purpose | 1 | True | 0.00089 | 0.00011 | 0.05350 | False | 0.00000 | 0.59226 |
| __shadow__1_loan_amnt | 1 | True | 0.00043 | 0.00008 | 0.00000 | False | 0.00000 | 0.40330 |
| __shadow__9_funded_amnt | 1 | True | 0.00020 | 0.00003 | 0.00000 | False | 0.00000 | 0.40111 |
| __shadow__3_term | 1 | True | 0.00016 | 0.00006 | 0.00000 | False | 0.01233 | 0.18005 |
| __shadow__8_addr_state | 1 | True | 0.00007 | 0.00007 | 0.00000 | False | 0.27385 | 0.07759 |
| __shadow__5_pub_rec | 1 | True | -0.00022 | 0.00004 | 0.00000 | False | 0.00000 | -0.37883 |
| __shadow__0_funded_amnt | 1 | True | -0.00023 | 0.00005 | 0.00000 | False | 0.00005 | -0.29494 |
| __shadow__6_inq_last_6mths | 1 | True | -0.00084 | 0.00008 | 0.00000 | False | 0.00000 | -0.72575 |
| __shadow__2_annual_inc | 1 | True | -0.00136 | 0.00011 | 0.00000 | False | 0.00000 | -0.87198 |

Shadow bar (95th pct of 10 shadow players): **0.00104**. Mode: sampled. Subsets evaluated: 2776. Model fits: 13875.

Implementation audit (efficiency property): sum of Shapley values 0.178212 vs v(full)-v(empty) 0.178212, abs diff 2.78e-17. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | term | 1 | 0.1781 | [0.1612, 0.1935] | 0.1854 | 0.5808 | 0.1190 | 50.24% | 0.0000 |
| 2 | revol_util | 2 | 0.2669 | [0.2519, 0.2825] | 0.2014 | 0.6063 | 0.1181 | 25.42% | 0.0000 |
| 3 | annual_inc | 3 | 0.3039 | [0.2896, 0.3180] | 0.2198 | 0.6180 | 0.1170 | 15.09% | 0.0000 |
| 4 | inq_last_6mths | 4 | 0.3302 | [0.3160, 0.3448] | 0.2416 | 0.6268 | 0.1164 | 7.74% | 0.0000 |
| 5 | purpose | 5 | 0.3412 | [0.3276, 0.3546] | 0.2544 | 0.6318 | 0.1161 | 4.68% | 0.0000 |
| 6 | grp[funded_amnt+loan_amnt] | 7 | 0.3459 | [0.3316, 0.3601] | 0.2559 | 0.6332 | 0.1159 | 3.37% | 0.0000 |
| 7 | addr_state | 8 | 0.3524 | [0.3385, 0.3665] | 0.2593 | 0.6349 | 0.1157 | 1.56% | 0.0001 |
| 8 | pub_rec | 9 | 0.3579 | [0.3441, 0.3711] | 0.2639 | 0.6379 | 0.1155 | 0.00% | 1.0000 |

**Selected k = 8** (9 columns, Gini 0.3579, relative loss 0.00%, DeLong p = 1.0000). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`term`, `revol_util`, `annual_inc`, `inq_last_6mths`, `purpose`, `funded_amnt`, `loan_amnt`, `addr_state [proxy_risk]`, `pub_rec`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1216 | 0.1157 | **0.1157** |
| ECE | - | 0.0119 | **0.0051** |

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
| `addr_state` | proxy_risk | Geography - recognised proxy for race/national origin (redlining risk). |
