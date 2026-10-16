# LC - Methodology v3 results

Rows: 39717 | Raw columns: 23 | Event rate: 0.1417

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `loan_amnt` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `funded_amnt` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `term` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `int_rate` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `installment` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
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
| int_rate | 0.3221 | 0.3105 | 0.3281 | 0.3414 | False | False | 0.1888 | 282.0796 | True | none |  | True |
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
| installment | 0.0058 | 0.0084 | 0.0091 | 0.0152 | False | True | 0.0270 | 281.3713 | True | model_check_shape |  | False |
| home_ownership | 0.0056 | 0.0068 | 0.0068 | 0.0068 | False | False | 0.0260 | 14.3094 | True | none |  | False |
| mths_since_last_delinq | 0.0051 | 0.0044 | 0.0059 | 0.0075 | False | False | 0.0252 | 286.0466 | True | none |  | False |
| delinq_2yrs | 0.0036 | 0.0000 | 0.0026 | 0.0026 | False | False | 0.0219 | 142.9525 | True | none |  | False |
| revol_bal | 0.0028 | 0.0025 | 0.0043 | 0.0053 | False | True | 0.0184 | 281.2296 | True | model_check_shape |  | False |

Candidates passing Stage 1: 10 of 23.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| int_rate | 1 | False | 0.07287 | 0.00341 | 1.00000 | True | 0.00000 | 1.51050 |
| term | 1 | False | 0.02930 | 0.00204 | 1.00000 | True | 0.00000 | 1.01412 |
| annual_inc | 1 | False | 0.02389 | 0.00109 | 1.00000 | True | 0.00000 | 1.55625 |
| revol_util | 1 | False | 0.02008 | 0.00194 | 1.00000 | True | 0.00000 | 0.73361 |
| inq_last_6mths | 1 | False | 0.01605 | 0.00115 | 1.00000 | True | 0.00000 | 0.98752 |
| purpose | 1 | False | 0.01066 | 0.00091 | 1.00000 | True | 0.00000 | 0.82801 |
| grp[funded_amnt+loan_amnt] | 2 | False | 0.00826 | 0.00087 | 1.00000 | True | 0.00000 | 0.67103 |
| addr_state | 1 | False | 0.00776 | 0.00061 | 1.00000 | True | 0.00000 | 0.89562 |
| pub_rec | 1 | False | 0.00583 | 0.00041 | 1.00000 | True | 0.00000 | 0.99751 |
| __shadow__9_addr_state | 1 | True | 0.00094 | 0.00018 | 0.68450 | False | 0.00000 | 0.36009 |
| __shadow__4_annual_inc | 1 | True | 0.00083 | 0.00013 | 0.31550 | False | 0.00000 | 0.46823 |
| __shadow__5_term | 1 | True | 0.00011 | 0.00003 | 0.00000 | False | 0.00121 | 0.23225 |
| __shadow__3_loan_amnt | 1 | True | -0.00023 | 0.00003 | 0.00000 | False | 0.00000 | -0.46467 |
| __shadow__7_pub_rec | 1 | True | -0.00029 | 0.00004 | 0.00000 | False | 0.00000 | -0.47714 |
| __shadow__0_int_rate | 1 | True | -0.00043 | 0.00004 | 0.00000 | False | 0.00000 | -0.82351 |
| __shadow__6_inq_last_6mths | 1 | True | -0.00061 | 0.00007 | 0.00000 | False | 0.00000 | -0.62898 |
| __shadow__1_revol_util | 1 | True | -0.00083 | 0.00007 | 0.00000 | False | 0.00000 | -0.80252 |
| __shadow__2_funded_amnt | 1 | True | -0.00087 | 0.00014 | 0.00000 | False | 0.00000 | -0.43633 |
| __shadow__8_purpose | 1 | True | -0.00113 | 0.00014 | 0.00000 | False | 0.00000 | -0.58157 |

Shadow bar (95th pct of 10 shadow players): **0.00089**. Mode: sampled. Subsets evaluated: 3012. Model fits: 15055.

Implementation audit (efficiency property): sum of Shapley values 0.192205 vs v(full)-v(empty) 0.192205, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | int_rate | 1 | 0.3077 | [0.2926, 0.3222] | 0.2231 | 0.6120 | 0.1171 | 20.53% | 0.0000 |
| 2 | term | 2 | 0.3272 | [0.3116, 0.3413] | 0.2396 | 0.6232 | 0.1166 | 15.49% | 0.0000 |
| 3 | annual_inc | 3 | 0.3587 | [0.3442, 0.3735] | 0.2603 | 0.6368 | 0.1155 | 7.36% | 0.0000 |
| 4 | revol_util | 4 | 0.3601 | [0.3457, 0.3745] | 0.2617 | 0.6367 | 0.1155 | 7.01% | 0.0000 |
| 5 | inq_last_6mths | 5 | 0.3707 | [0.3569, 0.3844] | 0.2693 | 0.6413 | 0.1151 | 4.26% | 0.0000 |
| 6 | purpose | 6 | 0.3772 | [0.3638, 0.3911] | 0.2759 | 0.6441 | 0.1149 | 2.57% | 0.0000 |
| 7 | grp[funded_amnt+loan_amnt] | 8 | 0.3783 | [0.3645, 0.3924] | 0.2750 | 0.6447 | 0.1148 | 2.29% | 0.0000 |
| 8 | addr_state | 9 | 0.3841 | [0.3708, 0.3979] | 0.2834 | 0.6475 | 0.1147 | 0.80% | 0.0025 |
| 9 | pub_rec | 10 | 0.3872 | [0.3743, 0.4008] | 0.2816 | 0.6490 | 0.1145 | 0.00% | 1.0000 |

**Selected k = 9** (10 columns, Gini 0.3872, relative loss 0.00%, DeLong p = 1.0000). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`int_rate`, `term`, `annual_inc`, `revol_util`, `inq_last_6mths`, `purpose`, `funded_amnt`, `loan_amnt`, `addr_state [proxy_risk]`, `pub_rec`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1216 | 0.1149 | **0.1149** |
| ECE | - | 0.0113 | **0.0044** |

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
