# PAK - Methodology v3 results

Rows: 50000 | Raw columns: 39 | Event rate: 0.2608

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `PAYMENT_DAY` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `APPLICATION_SUBMISSION_TYPE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `QUANT_ADDITIONAL_CARDS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `POSTAL_ADDRESS_TYPE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `QUANT_DEPENDANTS` | proxy_risk | origination | Household composition - proxy for familial status / sex. Includes the common credit-scoring abbreviations NKID (number of children) and DEP (dependents). |
| `EDUCATION_LEVEL` | proxy_risk | origination | Education - recognised proxy for race/national origin and age. |
| `RESIDENCIAL_STATE` | proxy_risk | origination | Geography - recognised proxy for race/national origin (redlining risk). |
| `FLAG_RESIDENCIAL_PHONE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `RESIDENCIAL_PHONE_AREA_CODE` | proxy_risk | origination | Telephone area code - geographic proxy. |
| `RESIDENCE_TYPE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `MONTHS_IN_RESIDENCE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_MOBILE_PHONE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_EMAIL` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `PERSONAL_MONTHLY_INCOME` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `OTHER_INCOMES` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_VISA` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_MASTERCARD` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_DINERS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_AMERICAN_EXPRESS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_OTHER_CARDS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `QUANT_BANKING_ACCOUNTS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `QUANT_SPECIAL_BANKING_ACCOUNTS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `PERSONAL_ASSETS_VALUE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `QUANT_CARS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `COMPANY` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `PROFESSIONAL_STATE` | proxy_risk | origination | Geography - recognised proxy for race/national origin (redlining risk). |
| `FLAG_PROFESSIONAL_PHONE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `PROFESSIONAL_PHONE_AREA_CODE` | proxy_risk | origination | Telephone area code - geographic proxy. |
| `MONTHS_IN_THE_JOB` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `PROFESSION_CODE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `OCCUPATION_TYPE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `MATE_PROFESSION_CODE` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `EDUCATION_LEVEL_2` | proxy_risk | origination | Education - recognised proxy for race/national origin and age. |
| `FLAG_HOME_ADDRESS_DOCUMENT` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_RG` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_CPF` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_INCOME_PROOF` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `PRODUCT` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FLAG_ACSP_RECORD` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PERSONAL_ASSETS_VALUE | 0.0661 | 0.0000 | 0.0000 | 0.0000 | True | False | 0.0550 | 0.2608 | False | mann_whitney+model_check_shape | 0.0270 | True |
| PAYMENT_DAY | 0.0328 | 0.0315 | 0.0320 | 0.0320 | False | False | 0.0808 | 459.3040 | True | none |  | True |
| RESIDENCIAL_PHONE_AREA_CODE | 0.0222 | 0.0231 | 0.0243 | 0.0354 | False | False | 0.0665 | 738.3814 | True | none |  | True |
| OCCUPATION_TYPE | 0.0217 | 0.0171 | 0.0171 | 0.0171 | True | False | 0.0629 | 83.2016 | True | model_check_shape |  | True |
| FLAG_RESIDENCIAL_PHONE | 0.0182 | 0.0182 | 0.0182 | 0.0182 | False | False | 0.0607 | 2136.3766 | True | none |  | False |
| PROFESSIONAL_STATE | 0.0097 | 0.0097 | 0.0097 | 0.0097 | False | False | 0.0437 | 4.1731 | False | model_check_nominal |  | True |
| MONTHS_IN_THE_JOB | 0.0088 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0174 | 0.2608 | False | mann_whitney | 0.2073 | False |
| MONTHS_IN_RESIDENCE | 0.0076 | 0.0095 | 0.0105 | 0.0114 | False | True | 0.0378 | 985.1171 | True | model_check_shape |  | False |
| RESIDENCIAL_STATE | 0.0065 | 0.0157 | 0.0157 | 0.0157 | False | False | 0.0346 | 804.6297 | True | none |  | False |
| RESIDENCE_TYPE | 0.0041 | 0.0037 | 0.0038 | 0.0038 | False | False | 0.0284 | 351.8462 | True | none |  | False |
| PROFESSION_CODE | 0.0038 | 0.0030 | 0.0033 | 0.0033 | False | False | 0.0268 | 584.2368 | True | none |  | False |
| MATE_PROFESSION_CODE | 0.0034 | 0.0000 | 0.0004 | 0.0004 | False | False | 0.0251 | 385.7528 | True | none |  | False |
| PERSONAL_MONTHLY_INCOME | 0.0030 | 0.0034 | 0.0056 | 0.0084 | False | True | 0.0234 | 652.0500 | True | model_check_shape |  | False |
| APPLICATION_SUBMISSION_TYPE | 0.0026 | 0.0026 | 0.0026 | 0.0026 | False | False | 0.0219 | 608.4931 | True | none |  | False |
| EDUCATION_LEVEL_2 | 0.0023 | 0.0003 | 0.0003 | 0.0003 | False | False | 0.0206 | 434.7869 | True | none |  | False |
| PRODUCT | 0.0020 | 0.0000 | 0.0020 | 0.0020 | False | False | 0.0204 | 337.7619 | True | none |  | False |
| PROFESSIONAL_PHONE_AREA_CODE | 0.0019 | 0.0019 | 0.0029 | 0.0032 | False | False | 0.0194 | 910.5226 | True | none |  | False |
| FLAG_MASTERCARD | 0.0017 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0176 | 1270.9759 | True | none |  | False |
| QUANT_DEPENDANTS | 0.0014 | 0.0006 | 0.0012 | 0.0014 | False | False | 0.0164 | 1037.5420 | True | none |  | False |
| FLAG_PROFESSIONAL_PHONE | 0.0013 | 0.0013 | 0.0013 | 0.0013 | False | False | 0.0158 | 3518.4618 | True | none |  | False |
| QUANT_BANKING_ACCOUNTS | 0.0013 | 0.0006 | 0.0006 | 0.0006 | False | False | 0.0164 | 3.6515 | False | mann_whitney | 0.0086 | True |
| QUANT_SPECIAL_BANKING_ACCOUNTS | 0.0013 | 0.0006 | 0.0006 | 0.0006 | False | False | 0.0164 | 3.6515 | False | mann_whitney | 0.0086 | True |
| OTHER_INCOMES | 0.0009 | 0.0000 | 0.0000 | 0.0009 | False | False | 0.0129 | 641.8780 | True | none |  | False |
| QUANT_CARS | 0.0007 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0117 | 4383.6017 | True | none |  | False |
| COMPANY | 0.0004 | 0.0004 | 0.0004 | 0.0004 | False | False | 0.0082 | 5748.7336 | True | none |  | False |
| FLAG_EMAIL | 0.0003 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0080 | 2578.4665 | True | none |  | False |
| FLAG_VISA | 0.0002 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0053 | 1453.2890 | True | none |  | False |
| POSTAL_ADDRESS_TYPE | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0021 | 85.2881 | True | none |  | False |
| FLAG_DINERS | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0016 | 17.2141 | True | none |  | False |
| FLAG_OTHER_CARDS | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0009 | 26.6036 | True | none |  | False |
| FLAG_AMERICAN_EXPRESS | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0000 | 22.6913 | True | none |  | False |
| EDUCATION_LEVEL | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | mann_whitney |  | False |
| QUANT_ADDITIONAL_CARDS | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | mann_whitney |  | False |
| FLAG_MOBILE_PHONE | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | model_check_nominal |  | False |
| FLAG_HOME_ADDRESS_DOCUMENT | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | mann_whitney |  | False |
| FLAG_RG | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | mann_whitney |  | False |
| FLAG_CPF | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | mann_whitney |  | False |
| FLAG_INCOME_PROOF | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | mann_whitney |  | False |
| FLAG_ACSP_RECORD | 0.0000 | 0.0000 | 0.0000 | 0.0000 | False | False |  |  | False | model_check_nominal |  | False |

Candidates passing Stage 1: 7 of 39.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| PAYMENT_DAY | 1 | False | 0.02749 | 0.00075 | 1.00000 | True | 0.00000 | 2.58586 |
| RESIDENCIAL_PHONE_AREA_CODE | 1 | False | 0.01946 | 0.00049 | 1.00000 | True | 0.00000 | 2.81084 |
| OCCUPATION_TYPE | 1 | False | 0.01539 | 0.00062 | 1.00000 | True | 0.00000 | 1.76043 |
| PROFESSIONAL_STATE | 1 | False | 0.00564 | 0.00036 | 1.00000 | True | 0.00000 | 1.09415 |
| grp[QUANT_BANKING_ACCOUNTS+QUANT_SPECIAL_BANKING_ACCOUNTS] | 2 | False | 0.00174 | 0.00013 | 1.00000 | True | 0.00000 | 0.93027 |
| __shadow__9_OCCUPATION_TYPE | 1 | True | 0.00147 | 0.00014 | 1.00000 | False | 0.00000 | 0.71978 |
| __shadow__1_QUANT_SPECIAL_BANKING_ACCOUNTS | 1 | True | 0.00080 | 0.00009 | 0.00000 | False | 0.00000 | 0.66670 |
| __shadow__4_RESIDENCIAL_PHONE_AREA_CODE | 1 | True | 0.00065 | 0.00011 | 0.00000 | False | 0.00000 | 0.42439 |
| PERSONAL_ASSETS_VALUE | 1 | False | 0.00053 | 0.00006 | 0.00000 | False | 0.00000 | 0.61366 |
| __shadow__6_PROFESSIONAL_STATE | 1 | True | 0.00052 | 0.00011 | 0.00000 | False | 0.00000 | 0.34700 |
| __shadow__3_PAYMENT_DAY | 1 | True | 0.00025 | 0.00009 | 0.00000 | False | 0.00445 | 0.20493 |
| __shadow__7_QUANT_BANKING_ACCOUNTS | 1 | True | 0.00008 | 0.00003 | 0.00000 | False | 0.01435 | 0.17467 |
| __shadow__0_QUANT_BANKING_ACCOUNTS | 1 | True | -0.00018 | 0.00003 | 0.00000 | False | 0.00000 | -0.44633 |
| __shadow__8_QUANT_SPECIAL_BANKING_ACCOUNTS | 1 | True | -0.00022 | 0.00004 | 0.00000 | False | 0.00000 | -0.38907 |
| __shadow__2_OCCUPATION_TYPE | 1 | True | -0.00062 | 0.00004 | 0.00000 | False | 0.00000 | -1.02473 |
| __shadow__5_PERSONAL_ASSETS_VALUE | 1 | True | -0.00187 | 0.00003 | 0.00000 | False | 0.00000 | -3.94543 |

Shadow bar (95th pct of 10 shadow players): **0.00117**. Mode: sampled. Subsets evaluated: 2349. Model fits: 11740.

Implementation audit (efficiency property): sum of Shapley values 0.071145 vs v(full)-v(empty) 0.071145, abs diff 1.39e-17. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | PAYMENT_DAY | 1 | 0.0913 | [0.0798, 0.1034] | 0.0795 | 0.5382 | 0.1916 | 38.33% | 0.0000 |
| 2 | RESIDENCIAL_PHONE_AREA_CODE | 2 | 0.1273 | [0.1154, 0.1384] | 0.1010 | 0.5495 | 0.1908 | 14.04% | 0.0000 |
| 3 | OCCUPATION_TYPE | 3 | 0.1438 | [0.1323, 0.1539] | 0.1026 | 0.5489 | 0.1904 | 2.90% | 0.0218 |
| 4 | PROFESSIONAL_STATE | 4 | 0.1460 | [0.1351, 0.1564] | 0.1058 | 0.5495 | 0.1903 | 1.41% | 0.0087 |
| 5 | grp[QUANT_BANKING_ACCOUNTS+QUANT_SPECIAL_BANKING_ACCOUNTS] | 6 | 0.1480 | [0.1373, 0.1583] | 0.1073 | 0.5503 | 0.1903 | 0.00% | 1.0000 |

**Selected k = 5** (6 columns, Gini 0.1480, relative loss 0.00%, DeLong p = 1.0000). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`PAYMENT_DAY`, `RESIDENCIAL_PHONE_AREA_CODE [proxy_risk]`, `OCCUPATION_TYPE`, `PROFESSIONAL_STATE [proxy_risk]`, `QUANT_BANKING_ACCOUNTS`, `QUANT_SPECIAL_BANKING_ACCOUNTS`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1928 | 0.1892 | **0.1892** |
| ECE | - | 0.0039 | **0.0074** |

## Stage 4b - per-grade calibration backtest (G4; CRE36.122-123)

Held-out 80/20 split (random_state=42), 6-col benchmark model, calibrated PD floored at 0.03%. Test n=10,000, AUC 0.584.

| Grade | n | Expected | Realised | 95% CI | Within? |
|---|--:|--:|--:|---|:--:|
| B | 180 | 9.93% | 10.00% | [6.42%,15.25%] | OK |
| CCC | 685 | 15.25% | 14.89% | [12.42%,17.75%] | OK |
| CC | 8665 | 26.55% | 26.71% | [25.78%,27.65%] | OK |
| C | 465 | 36.98% | 36.77% | [32.52%,41.25%] | OK |
| D | 5 | 50.00% | 60.00% | [23.07%,88.24%] | OK |

**All 5 populated grades pass; ECE 0.0082; Hosmer-Lemeshow chi2=8.54, df=8, p=0.382 => not rejected.**
The model is **well-calibrated but barely discriminating**: 8,665 of 10,000 held-out rows fall in a single
grade (CC, at the ~26% base rate). Honest PDs, minimal risk-tier separation — the clean illustration that
calibration and discrimination are distinct (AUC 0.584, Gini 0.148). Grades AAA-BB and investment grades are
essentially unpopulated (near-flat score distribution over a 26% base rate).

### Fairness - disparate impact across excluded prohibited attributes (G4)

In-sample; model-excluded attributes joined back. Mean predicted-PD gap vs the reference (largest) group, with
the actual default rate for a predictive-parity check. **All gaps < 0.05 and track real default** (no material
disparate impact). **AIR (four-fifths) is degenerate** - with a 26% base rate and near-flat scores, ~0.01%
reach an "approve" investment grade, so group approval rates are ~0 and the ratio is 0/0 noise; reported as
uninformative and the cutoff-free PD gap + predictive parity are used instead (no invented approval cutoff).

| Attribute | Group (vs ref) | mean PD | actual default | PD gap |
|---|---|--:|--:|--:|
| SEX | M vs F | 0.259 / 0.262 | 0.273 / 0.253 | -0.003 |
| AGE | 65+ vs 35-44 | 0.223 / 0.271 | 0.199 / 0.273 | -0.049 |
| AGE | 25-34 vs 35-44 | 0.272 / 0.271 | 0.305 / 0.273 | +0.001 |
| NACIONALITY | 0 vs 1 | 0.260 / 0.261 | 0.263 / 0.261 | -0.000 |
| MARITAL_STATUS | 4 vs 2 | 0.228 / 0.264 | 0.213 / 0.242 | -0.036 |

**Proxy sensitivity (PC-fair):** the 4-col proxy-excluded model (Gini 0.1175) is **fairness-equivalent** to the
6-col benchmark on all four attributes (SEX gap -0.003/-0.003; AGE 65+ -0.049/-0.054) - removing the geographic
proxies does not measurably change disparate impact on these axes. The proxies remain flagged not-for-live
because they could proxy race/ethnicity, which is absent from the dataset and therefore untestable here.

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
| `RESIDENCIAL_PHONE_AREA_CODE` | proxy_risk | Telephone area code - geographic proxy. |
| `PROFESSIONAL_STATE` | proxy_risk | Geography - recognised proxy for race/national origin (redlining risk). |
