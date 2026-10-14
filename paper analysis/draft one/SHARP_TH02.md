# TH02 - Methodology v3 results

Rows: 1225 | Raw columns: 14 | Event rate: 0.2637

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `YOB` | prohibited | origination | Date/year of birth implies age - prohibited basis (ECOA/Reg B). Note `YOB` is a standard credit-scoring abbreviation and is frequently stored as a two-digit year, which is easy to mistake for an ordinary numeric feature. |
| `NKID` | proxy_risk | origination | Household composition - proxy for familial status / sex. Includes the common credit-scoring abbreviations NKID (number of children) and DEP (dependents). |
| `DEP` | proxy_risk | origination | Household composition - proxy for familial status / sex. Includes the common credit-scoring abbreviations NKID (number of children) and DEP (dependents). |
| `PHON` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `SINC` | prohibited | origination | Spouse income reveals marital status - prohibited basis (ECOA/Reg B). |
| `AES` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DAINC` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `RES` | proxy_risk | origination | Housing/residential tenure - correlated with protected characteristics; treat with care. Includes the RES abbreviation used in several credit-scoring datasets. |
| `DHVAL` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DMORT` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DOUTM` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DOUTL` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DOUTHP` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DOUTCC` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOUTHP | 1.4756 | 0.0000 | 0.0152 | 0.0226 | True | False | 0.2268 | 0.2637 | False | mann_whitney+model_check_shape | 0.1040 | False |
| DOUTCC | 1.1216 | 0.0000 | 0.0282 | 0.0747 | True | False | 0.1817 | 0.2637 | False | mann_whitney+model_check_shape | 0.0003 | True |
| DAINC | 0.2340 | 0.2212 | 0.2412 | 0.2766 | False | False | 0.2158 | 16.0841 | True | none |  | True |
| AES | 0.1547 | 0.1764 | 0.1764 | 0.1764 | False | False | 0.1798 | 27.4220 | True | none |  | True |
| YOB | 0.1186 | 0.0677 | 0.2077 | 0.2879 | False | True | 0.1618 | 16.8751 | True | model_check_shape |  | True |
| DOUTM | 0.0629 | 0.0408 | 0.0657 | 0.1017 | False | True | 0.1107 | 16.6114 | True | model_check_shape |  | True |
| RES | 0.0593 | 0.0593 | 0.0593 | 0.0593 | False | False | 0.1148 | 17.4024 | True | none |  | True |
| DMORT | 0.0499 | 0.0394 | 0.0459 | 0.0709 | False | False | 0.0941 | 31.9045 | True | none |  | True |
| DHVAL | 0.0438 | 0.0381 | 0.0454 | 0.0497 | False | False | 0.0880 | 16.3478 | True | none |  | True |
| DOUTL | 0.0355 | 0.0171 | 0.0270 | 0.0388 | True | False | 0.0789 | 16.0841 | True | model_check_shape |  | True |
| SINC | 0.0239 | 0.0066 | 0.0188 | 0.0367 | True | True | 0.0654 | 31.1135 | True | model_check_shape |  | True |
| PHON | 0.0091 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0401 | 31.1135 | True | none |  | False |
| NKID | 0.0059 | 0.0030 | 0.0047 | 0.0225 | True | False | 0.0334 | 20.0392 | True | model_check_shape |  | True |
| DEP | 0.0039 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0294 | 1.8457 | False | mann_whitney | 0.8589 | False |

Candidates passing Stage 1: 11 of 14.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| DAINC | 1 | False | 0.04489 | 0.00194 | 1.00000 | True | 0.00000 | 1.63402 |
| AES | 1 | False | 0.02581 | 0.00224 | 1.00000 | True | 0.00000 | 0.81585 |
| YOB | 1 | False | 0.01336 | 0.00112 | 1.00000 | True | 0.00000 | 0.84672 |
| grp[DHVAL+DMORT] | 2 | False | 0.01121 | 0.00103 | 1.00000 | True | 0.00000 | 0.76691 |
| RES | 1 | False | 0.01082 | 0.00067 | 1.00000 | True | 0.00000 | 1.14440 |
| DOUTCC | 1 | False | 0.01007 | 0.00062 | 1.00000 | True | 0.00000 | 1.15823 |
| DOUTM | 1 | False | 0.00698 | 0.00096 | 0.98050 | True | 0.00000 | 0.51402 |
| __shadow__1_DMORT | 1 | True | 0.00520 | 0.00035 | 0.84100 | False | 0.00000 | 1.04549 |
| __shadow__6_YOB | 1 | True | 0.00459 | 0.00041 | 0.13250 | False | 0.00000 | 0.79274 |
| __shadow__9_AES | 1 | True | 0.00416 | 0.00041 | 0.02650 | False | 0.00000 | 0.71491 |
| __shadow__5_SINC | 1 | True | 0.00180 | 0.00040 | 0.00000 | False | 0.00001 | 0.31923 |
| __shadow__7_DOUTL | 1 | True | 0.00166 | 0.00061 | 0.00000 | False | 0.00724 | 0.19312 |
| SINC | 1 | False | 0.00109 | 0.00064 | 0.00000 | False | 0.09195 | 0.11974 |
| NKID | 1 | False | -0.00074 | 0.00014 | 0.00000 | False | 0.00000 | -0.36077 |
| DOUTL | 1 | False | -0.00451 | 0.00066 | 0.00000 | False | 0.00000 | -0.48450 |
| __shadow__4_NKID | 1 | True | -0.00701 | 0.00028 | 0.00000 | False | 0.00000 | -1.77938 |
| __shadow__2_DOUTM | 1 | True | -0.00915 | 0.00032 | 0.00000 | False | 0.00000 | -2.02583 |
| __shadow__3_DAINC | 1 | True | -0.01222 | 0.00057 | 0.00000 | False | 0.00000 | -1.51089 |
| __shadow__8_DOUTCC | 1 | True | -0.01236 | 0.00039 | 0.00000 | False | 0.00000 | -2.23375 |
| __shadow__0_DHVAL | 1 | True | -0.01268 | 0.00060 | 0.00000 | False | 0.00000 | -1.49312 |

Shadow bar (95th pct of 10 shadow players): **0.00493**. Mode: sampled. Subsets evaluated: 3230. Model fits: 16145.

Implementation audit (efficiency property): sum of Shapley values 0.082979 vs v(full)-v(empty) 0.082979, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | DAINC | 1 | 0.1956 | [0.1179, 0.2627] | 0.1921 | 0.5848 | 0.1874 | 29.36% | 0.0044 |
| 2 | AES | 2 | 0.2380 | [0.1613, 0.3061] | 0.2025 | 0.6042 | 0.1858 | 14.05% | 0.1297 |
| 3 | YOB | 3 | 0.2366 | [0.1597, 0.3063] | 0.2107 | 0.6025 | 0.1852 | 14.57% | 0.0749 |
| 4 | grp[DHVAL+DMORT] | 5 | 0.2521 | [0.1750, 0.3250] | 0.2122 | 0.6043 | 0.1848 | 8.96% | 0.2066 |
| 5 | RES | 6 | 0.2725 | [0.1990, 0.3392] | 0.2281 | 0.6141 | 0.1837 | 1.59% | 0.7757 |
| 6 | DOUTCC | 7 | 0.2757 | [0.2014, 0.3528] | 0.2205 | 0.6094 | 0.1862 | 0.44% | 0.7462 |
| 7 | DOUTM | 8 | 0.2769 | [0.2038, 0.3537] | 0.2166 | 0.6092 | 0.1863 | 0.00% | 1.0000 |

**Selected k = 5** (6 columns, Gini 0.2725, relative loss 1.59%, DeLong p = 0.7757). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`DAINC`, `AES`, `YOB [prohibited]`, `DHVAL`, `DMORT`, `RES [proxy_risk]`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1949 | 0.1902 | **0.1948** |
| ECE | - | 0.0474 | **0.0768** |

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
| `YOB` | prohibited | Date/year of birth implies age - prohibited basis (ECOA/Reg B). Note `YOB` is a standard credit-scoring abbreviation and is frequently stored as a two-digit year, which is easy to mistake for an ordinary numeric feature. |
| `RES` | proxy_risk | Housing/residential tenure - correlated with protected characteristics; treat with care. Includes the RES abbreviation used in several credit-scoring datasets. |
