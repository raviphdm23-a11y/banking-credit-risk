# SBA - Methodology v3 results

Rows: 2102 | Raw columns: 19 | Event rate: 0.3264

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `NAICS` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `Term` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `NoEmp` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `NewExist` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `CreateJob` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `RetainedJob` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `FranchiseCode` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `UrbanRural` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `RevLineCr` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `LowDoc` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `DisbursementGross` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `GrAppv` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `SBA_Appv` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `New` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `RealEstate` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `Portion` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `Recession` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `daysterm` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `ApprovalFY` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| daysterm | 2.8933 | 1.8019 | 2.7678 | 5.3212 | False | False | 0.7316 | 107.3711 | True | none |  | True |
| Term | 2.8933 | 1.8019 | 2.7678 | 5.3212 | False | False | 0.7316 | 107.3711 | True | none |  | True |
| SBA_Appv | 1.1229 | 1.0329 | 1.0785 | 1.1989 | False | False | 0.4465 | 59.7231 | True | none |  | True |
| ApprovalFY | 1.0457 | 1.0557 | 1.1068 | 1.1717 | False | False | 0.4423 | 40.1418 | True | none |  | True |
| GrAppv | 1.0220 | 0.9837 | 1.0097 | 1.2550 | False | False | 0.4261 | 40.1418 | True | none |  | True |
| RealEstate | 0.9775 | 0.0000 | 0.0000 | 0.0000 | True | False | 0.3679 | 188.3073 | True | model_check_shape |  | True |
| Portion | 0.9699 | 1.0776 | 1.0776 | 3.8694 | False | False | 0.3928 | 113.5718 | True | none |  | True |
| DisbursementGross | 0.7494 | 0.7001 | 0.7780 | 0.8103 | False | False | 0.3664 | 34.2674 | True | none |  | True |
| RevLineCr | 0.6826 | 0.6826 | 0.6826 | 0.6826 | False | False | 0.3572 | 0.6527 | False | model_check_nominal |  | True |
| FranchiseCode | 0.5458 | 0.0361 | 0.0361 | 0.0361 | False | False | 0.3512 | 25.7821 | True | none |  | True |
| NAICS | 0.2889 | 0.3024 | 0.3416 | 0.4407 | False | False | 0.2440 | 37.8573 | True | none |  | True |
| UrbanRural | 0.2412 | 0.0087 | 0.0087 | 0.0087 | True | False | 0.1897 | 41.4472 | True | model_check_shape |  | True |
| NoEmp | 0.2303 | 0.1810 | 0.2266 | 0.2397 | False | False | 0.2007 | 34.5937 | True | none |  | True |
| RetainedJob | 0.1624 | 0.1374 | 0.1613 | 0.1731 | False | False | 0.1882 | 35.8991 | True | none |  | True |
| CreateJob | 0.1091 | 0.1477 | 0.1607 | 0.1721 | False | False | 0.1484 | 65.5975 | True | none |  | True |
| Recession | 0.0689 | 0.0000 | 0.0000 | 0.0000 | True | False | 0.1265 | 46.9952 | True | model_check_shape |  | True |
| NewExist | 0.0198 | 0.0106 | 0.0106 | 0.0106 | False | False | 0.0276 | 0.3264 | False | mann_whitney | 0.4044 | False |
| LowDoc | 0.0062 | 0.1155 | 0.1155 | 0.1155 | True | False | 0.0348 | 0.9791 | False | model_check_nominal+model_check_shape |  | False |
| New | 0.0014 | 0.0000 | 0.0000 | 0.0000 | False | False | 0.0162 | 105.7393 | True | none |  | False |

Candidates passing Stage 1: 16 of 19.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| grp[RealEstate+Term+daysterm] | 3 | False | 0.16740 | 0.00663 | 1.00000 | True | 0.00000 | 1.78431 |
| ApprovalFY | 1 | False | 0.06147 | 0.00566 | 1.00000 | True | 0.00000 | 0.76787 |
| Portion | 1 | False | 0.04331 | 0.00554 | 1.00000 | True | 0.00000 | 0.55237 |
| grp[DisbursementGross+GrAppv+SBA_Appv] | 3 | False | 0.03334 | 0.00480 | 1.00000 | True | 0.00000 | 0.49137 |
| FranchiseCode | 1 | False | 0.03271 | 0.00366 | 1.00000 | True | 0.00000 | 0.63236 |
| RevLineCr | 1 | False | 0.02672 | 0.00397 | 1.00000 | True | 0.00000 | 0.47582 |
| NAICS | 1 | False | 0.02125 | 0.00244 | 1.00000 | True | 0.00000 | 0.61476 |
| UrbanRural | 1 | False | 0.01325 | 0.00166 | 1.00000 | True | 0.00000 | 0.56515 |
| RetainedJob | 1 | False | 0.01158 | 0.00179 | 1.00000 | True | 0.00000 | 0.45720 |
| NoEmp | 1 | False | 0.01002 | 0.00189 | 1.00000 | True | 0.00000 | 0.37431 |
| CreateJob | 1 | False | 0.00713 | 0.00145 | 0.99850 | True | 0.00000 | 0.34879 |
| Recession | 1 | False | 0.00646 | 0.00068 | 1.00000 | True | 0.00000 | 0.67385 |
| __shadow__0_UrbanRural | 1 | True | 0.00347 | 0.00042 | 0.96350 | False | 0.00000 | 0.58632 |
| __shadow__7_RealEstate | 1 | True | 0.00226 | 0.00047 | 0.03100 | False | 0.00000 | 0.34062 |
| __shadow__4_DisbursementGross | 1 | True | 0.00204 | 0.00036 | 0.00550 | False | 0.00000 | 0.40557 |
| __shadow__6_SBA_Appv | 1 | True | 0.00161 | 0.00032 | 0.00000 | False | 0.00000 | 0.35878 |
| __shadow__8_Term | 1 | True | -0.00122 | 0.00016 | 0.00000 | False | 0.00000 | -0.52743 |
| __shadow__1_RetainedJob | 1 | True | -0.00141 | 0.00021 | 0.00000 | False | 0.00000 | -0.46532 |
| __shadow__2_ApprovalFY | 1 | True | -0.00215 | 0.00030 | 0.00000 | False | 0.00000 | -0.50569 |
| __shadow__5_GrAppv | 1 | True | -0.00223 | 0.00041 | 0.00000 | False | 0.00000 | -0.38801 |
| __shadow__3_FranchiseCode | 1 | True | -0.00228 | 0.00043 | 0.00000 | False | 0.00000 | -0.37754 |
| __shadow__9_daysterm | 1 | True | -0.00403 | 0.00054 | 0.00000 | False | 0.00000 | -0.52969 |

Shadow bar (95th pct of 10 shadow players): **0.00292**. Mode: sampled. Subsets evaluated: 3698. Model fits: 18485.

Implementation audit (efficiency property): sum of Shapley values 0.430712 vs v(full)-v(empty) 0.430712, abs diff 0.00e+00. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | grp[RealEstate+Term+daysterm] | 3 | 0.7669 | [0.7320, 0.8032] | 0.7469 | 0.8644 | 0.1016 | 10.88% | 0.0000 |
| 2 | ApprovalFY | 4 | 0.8436 | [0.8170, 0.8698] | 0.7508 | 0.9053 | 0.0910 | 1.98% | 0.0127 |
| 3 | Portion | 5 | 0.8469 | [0.8205, 0.8726] | 0.7649 | 0.9035 | 0.0907 | 1.59% | 0.0150 |
| 4 | grp[DisbursementGross+GrAppv+SBA_Appv] | 8 | 0.8443 | [0.8175, 0.8711] | 0.7557 | 0.9029 | 0.0906 | 1.89% | 0.0016 |
| 5 | FranchiseCode | 9 | 0.8532 | [0.8259, 0.8783] | 0.7607 | 0.9073 | 0.0894 | 0.85% | 0.0478 |
| 6 | RevLineCr | 10 | 0.8517 | [0.8237, 0.8770] | 0.7600 | 0.9070 | 0.0889 | 1.03% | 0.0201 |
| 7 | NAICS | 11 | 0.8591 | [0.8341, 0.8834] | 0.7586 | 0.9111 | 0.0878 | 0.17% | 0.5363 |
| 8 | UrbanRural | 12 | 0.8589 | [0.8336, 0.8839] | 0.7590 | 0.9114 | 0.0875 | 0.19% | 0.4126 |
| 9 | RetainedJob | 13 | 0.8602 | [0.8347, 0.8849] | 0.7612 | 0.9122 | 0.0876 | 0.04% | 0.7767 |
| 10 | NoEmp | 14 | 0.8606 | [0.8350, 0.8855] | 0.7595 | 0.9130 | 0.0877 | -0.01% | 0.9229 |
| 11 | CreateJob | 15 | 0.8609 | [0.8353, 0.8854] | 0.7582 | 0.9132 | 0.0878 | -0.04% | 0.0350 |
| 12 | Recession | 16 | 0.8606 | [0.8351, 0.8851] | 0.7575 | 0.9130 | 0.0881 | 0.00% | 1.0000 |

**Selected k = 7** (11 columns, Gini 0.8591, relative loss 0.17%, DeLong p = 0.5363). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`RealEstate`, `Term`, `daysterm`, `ApprovalFY`, `Portion`, `DisbursementGross`, `GrAppv`, `SBA_Appv`, `FranchiseCode`, `RevLineCr`, `NAICS`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.2195 | 0.0512 | **0.0483** |
| ECE | - | 0.0436 | **0.0176** |

---

## Stage 4b — per-grade calibration backtest (G4; CRE36.122-123)

Held-out 80/20 (seed 42), 7-player benchmark, calibrated PD floored at 0.03%. Test n=421. **AUC 0.931 / Gini 0.862** (strongest in the corpus).

| Grade | n | Expected | Realised | Within CI? |
|---|--:|--:|--:|:--:|
| AAA | 44 | 0.0% | 0.0% | OK |
| A | 45 | 1.5% | 0.0% | OK |
| BBB | 47 | 2.4% | 6.4% | OK |
| B | 121 | 11.4% | 9.9% | OK |
| CC | 12 | 23.9% | 25.0% | OK |
| C | 11 | 35.0% | 27.3% | OK |
| D | 141 | 82.7% | 82.3% | OK |

**7/7 populated grades within Wilson CI; ECE 0.040.** Hosmer-Lemeshow **rejects (chi2=13.66, df=5, p=0.018)** — the
PD distribution is strongly **bimodal** (long real-estate loans near 0, short loans near 0.83), collapsing the HL
bins (df=5). Calibration is adequate grade-by-grade (the CRE36 requirement) despite the global HL rejection →
condition **SBA-CAL** (monitor).

### Availability / vintage sensitivity (held-out)
Dropping `ApprovalFY` (vintage/time proxy) leaves held-out **Gini 0.849 / AUC 0.925** vs the benchmark 0.862 / 0.931
— ΔGini **0.013 (-1.5%)**. Unlike CREDITRISK's circular features (-19-22%), the vintage feature costs almost nothing,
so there is **no circularity concern**; the model's strength is genuine loan-term signal. Condition **SBA-VINTAGE**.

### Fairness — geographic disparate impact (G4)
SBA is business lending with **no personal protected attributes**; `BankState` (lender geography) is excluded from
the model but tested on the scored output (indicative; no institution cutoff).

| BankState | n | approve rate | actual default |
|---|--:|--:|--:|
| CA | 201 | 0.378 | 0.169 |
| OH | 35 | 0.257 | 0.257 |
| NC | 59 | 0.237 | 0.627 |
| VA | 31 | 0.226 | 0.677 |
| SD | 39 | 0.154 | 0.410 |

Worst approve-rate AIR **0.41** (< four-fifths) but **true-risk-driven**: approve rates track actual default rates
by state. Replicates the corpus lesson (German age, LC/CREDITRISK geography) on an independent business-lending
dataset. Condition **SBA-GEO** (indicative; a geographic fairness-constrained review would precede any live use).
