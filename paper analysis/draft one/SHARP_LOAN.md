# LOAN - Methodology v3 results

Rows: 9578 | Raw columns: 13 | Event rate: 0.1601

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `credit.policy` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `purpose` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `int.rate` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `installment` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `log.annual.inc` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `dti` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `fico` | permissible | external_score | No name-based match to a prohibited or proxy-risk pattern. |
| `days.with.cr.line` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `revol.bal` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `revol.util` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `inq.last.6mths` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `delinq.2yrs` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `pub.rec` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| int.rate | 0.2427 | 0.2063 | 0.2378 | 0.2515 | False | False | 0.1623 | 76.5060 | True | none |  | True |
| fico | 0.1945 | 0.1712 | 0.1851 | 0.1994 | False | False | 0.1569 | 78.2665 | True | none |  | True |
| credit.policy | 0.1593 | 0.0000 | 0.0000 | 0.0000 | True | False | 0.1578 | 298.9814 | True | model_check_shape |  | True |
| inq.last.6mths | 0.1510 | 0.1267 | 0.1461 | 0.1495 | False | False | 0.1520 | 138.2869 | True | none |  | True |
| revol.util | 0.0593 | 0.0493 | 0.0629 | 0.0748 | False | False | 0.0889 | 76.9861 | True | none |  | True |
| purpose | 0.0587 | 0.0681 | 0.0681 | 0.0681 | False | False | 0.0946 | 99.0736 | True | none |  | True |
| pub.rec | 0.0260 | 0.0000 | 0.0000 | 0.0014 | True | False | 0.0639 | 4.1614 | False | mann_whitney+model_check_shape | 0.0000 | True |
| installment | 0.0207 | 0.0175 | 0.0239 | 0.0453 | True | True | 0.0544 | 150.2910 | True | model_check_shape |  | True |
| log.annual.inc | 0.0185 | 0.0118 | 0.0218 | 0.0312 | True | False | 0.0522 | 76.6660 | True | model_check_shape |  | True |
| revol.bal | 0.0170 | 0.0098 | 0.0236 | 0.0287 | True | True | 0.0503 | 153.3320 | True | model_check_shape |  | True |
| days.with.cr.line | 0.0159 | 0.0057 | 0.0167 | 0.0316 | True | True | 0.0480 | 76.5060 | True | model_check_shape |  | True |
| dti | 0.0133 | 0.0114 | 0.0128 | 0.0174 | False | False | 0.0432 | 76.5060 | True | none |  | False |
| delinq.2yrs | 0.0016 | 0.0000 | 0.0005 | 0.0005 | False | False | 0.0149 | 46.0956 | True | none |  | False |

Candidates passing Stage 1: 11 of 13.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| grp[fico+int.rate] | 2 | False | 0.04149 | 0.00263 | 1.00000 | True | 0.00000 | 1.11623 |
| inq.last.6mths | 1 | False | 0.03468 | 0.00220 | 1.00000 | True | 0.00000 | 1.11503 |
| credit.policy | 1 | False | 0.02934 | 0.00212 | 1.00000 | True | 0.00000 | 0.97901 |
| purpose | 1 | False | 0.02091 | 0.00098 | 1.00000 | True | 0.00000 | 1.51668 |
| revol.util | 1 | False | 0.02041 | 0.00161 | 1.00000 | True | 0.00000 | 0.89469 |
| log.annual.inc | 1 | False | 0.01054 | 0.00056 | 1.00000 | True | 0.00000 | 1.32707 |
| pub.rec | 1 | False | 0.00727 | 0.00043 | 1.00000 | True | 0.00000 | 1.18457 |
| installment | 1 | False | 0.00611 | 0.00060 | 1.00000 | True | 0.00000 | 0.72570 |
| revol.bal | 1 | False | 0.00549 | 0.00051 | 1.00000 | True | 0.00000 | 0.75640 |
| days.with.cr.line | 1 | False | 0.00360 | 0.00045 | 1.00000 | True | 0.00000 | 0.56563 |
| __shadow__1_inq.last.6mths | 1 | True | 0.00085 | 0.00023 | 0.99850 | False | 0.00038 | 0.25767 |
| __shadow__0_credit.policy | 1 | True | 0.00017 | 0.00004 | 0.00150 | False | 0.00002 | 0.30902 |
| __shadow__6_installment | 1 | True | -0.00022 | 0.00010 | 0.00000 | False | 0.03881 | -0.14859 |
| __shadow__2_fico | 1 | True | -0.00026 | 0.00013 | 0.00000 | False | 0.04605 | -0.14195 |
| __shadow__4_revol.util | 1 | True | -0.00048 | 0.00010 | 0.00000 | False | 0.00000 | -0.35655 |
| __shadow__9_pub.rec | 1 | True | -0.00087 | 0.00006 | 0.00000 | False | 0.00000 | -1.01281 |
| __shadow__3_int.rate | 1 | True | -0.00104 | 0.00009 | 0.00000 | False | 0.00000 | -0.79538 |
| __shadow__8_days.with.cr.line | 1 | True | -0.00133 | 0.00013 | 0.00000 | False | 0.00000 | -0.71180 |
| __shadow__5_revol.bal | 1 | True | -0.00172 | 0.00011 | 0.00000 | False | 0.00000 | -1.06646 |
| __shadow__7_log.annual.inc | 1 | True | -0.00225 | 0.00026 | 0.00000 | False | 0.00000 | -0.61411 |

Shadow bar (95th pct of 10 shadow players): **0.00055**. Mode: sampled. Subsets evaluated: 3230. Model fits: 16145.

Implementation audit (efficiency property): sum of Shapley values 0.172709 vs v(full)-v(empty) 0.172709, abs diff 2.78e-17. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | grp[fico+int.rate] | 2 | 0.2489 | [0.2190, 0.2772] | 0.1796 | 0.5814 | 0.1308 | 29.33% | 0.0000 |
| 2 | inq.last.6mths | 3 | 0.3082 | [0.2784, 0.3393] | 0.2104 | 0.6122 | 0.1289 | 12.48% | 0.0000 |
| 3 | credit.policy | 4 | 0.3173 | [0.2892, 0.3488] | 0.2255 | 0.6170 | 0.1288 | 9.91% | 0.0000 |
| 4 | purpose | 5 | 0.3341 | [0.3049, 0.3651] | 0.2358 | 0.6260 | 0.1277 | 5.13% | 0.0048 |
| 5 | revol.util | 6 | 0.3344 | [0.3047, 0.3653] | 0.2309 | 0.6259 | 0.1276 | 5.05% | 0.0040 |
| 6 | log.annual.inc | 7 | 0.3429 | [0.3126, 0.3733] | 0.2434 | 0.6293 | 0.1275 | 2.63% | 0.0743 |
| 7 | pub.rec | 8 | 0.3478 | [0.3188, 0.3790] | 0.2455 | 0.6313 | 0.1272 | 1.24% | 0.3194 |
| 8 | installment | 9 | 0.3496 | [0.3203, 0.3781] | 0.2465 | 0.6326 | 0.1270 | 0.73% | 0.2686 |
| 9 | revol.bal | 10 | 0.3526 | [0.3247, 0.3815] | 0.2490 | 0.6345 | 0.1268 | -0.10% | 0.4507 |
| 10 | days.with.cr.line | 11 | 0.3522 | [0.3244, 0.3808] | 0.2524 | 0.6345 | 0.1268 | 0.00% | 1.0000 |

**Selected k = 6** (7 columns, Gini 0.3429, relative loss 2.63%, DeLong p = 0.0743). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`fico [external_score]`, `int.rate`, `inq.last.6mths`, `credit.policy`, `purpose`, `revol.util`, `log.annual.inc`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1346 | 0.1306 | **0.1292** |
| ECE | - | 0.0229 | **0.0062** |

**Availability caveat (external_score):** `fico`. Results including these are not an origination-time (application) model; report with and without them (METHODOLOGY v3 s3.3).

## Stage 4b - per-grade calibration backtest (G4; CRE36.122-123)

Held-out 80/20 split (random_state=42), 7-col benchmark model, calibrated PD floored at 0.03%. Test n=1,916, AUC 0.668.

| Grade | n | Expected | Realised | 95% CI | Within? |
|---|--:|--:|--:|---|:--:|
| AAA | 46 | 0.03% | 0.00% | [0.00%,7.71%] | OK |
| BBB | 53 | 2.35% | 3.77% | [1.04%,12.75%] | OK |
| BB | 285 | 5.36% | 7.72% | [5.15%,11.41%] | OK |
| B | 335 | 11.71% | 10.15% | [7.35%,13.85%] | OK |
| CCC | 747 | 15.68% | 17.00% | [14.48%,19.86%] | OK |
| CC | 347 | 26.42% | 22.77% | [18.67%,27.46%] | OK |
| C | 97 | 36.69% | 40.21% | [31.00%,50.16%] | OK |
| D | 6 | 52.63% | 66.67% | [30.00%,90.32%] | OK |

**All 8 populated grades pass; ECE 0.0175; Hosmer-Lemeshow chi2=6.93, df=7, p=0.437 => not rejected.** Unlike
PAK, the model spreads applicants across the full AAA-D spectrum (46 reach AAA) with honest grade-by-grade PDs -
a genuinely discriminating, well-calibrated model.

### Availability sensitivity (origination-only, LC-orig)

Faithful 5-fold OOF (seed 42, same WoE-logistic). Dropping the three availability-flagged features
(`fico` external score, `int.rate`/`credit.policy` prior-decision artifacts) leaves a valid application-time
model: Gini **0.300** / AUC 0.650 vs the 7-col benchmark 0.343 / 0.672 - ΔGini 0.043 (**-12.4% relative**),
DeLong p 2e-06, and **better calibrated** (ECE 0.003 vs 0.0079). The model does not collapse without the circular
features (contrast PAK) - genuine origination-time signal (inquiries, revolving utilization, purpose, income).

### Fairness

**N/A** - the dataset carries no protected or proxy attributes (Stage 0), so no disparate-impact test applies
(documented as not-applicable, not skipped) - the clean case, as HELOC.
