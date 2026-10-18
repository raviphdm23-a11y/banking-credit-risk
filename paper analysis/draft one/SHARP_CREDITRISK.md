# CREDITRISK - Methodology v3 results

Rows: 32581 | Raw columns: 9 | Event rate: 0.2182

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `person_income` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `person_home_ownership` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `person_emp_length` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `loan_intent` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `loan_grade` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `loan_amnt` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `loan_int_rate` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `loan_percent_income` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `cb_person_cred_hist_length` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| loan_percent_income | 0.8759 | 0.7066 | 0.8715 | 0.8903 | False | False | 0.4220 | 355.6073 | True | none |  | True |
| loan_grade | 0.8578 | 0.8817 | 0.8817 | 0.8817 | False | False | 0.4133 | 276.8501 | True | none |  | True |
| loan_int_rate | 0.6754 | 0.5943 | 0.6464 | 0.6832 | False | False | 0.3583 | 379.8235 | True | none |  | True |
| person_income | 0.5256 | 0.4617 | 0.4704 | 0.5579 | False | False | 0.3122 | 355.6073 | True | none |  | True |
| person_home_ownership | 0.3770 | 0.3770 | 0.3770 | 0.3770 | False | False | 0.2420 | 23.3435 | True | none |  | True |
| loan_intent | 0.0958 | 0.0958 | 0.0958 | 0.0958 | False | False | 0.1264 | 786.4811 | True | none |  | True |
| loan_amnt | 0.0765 | 0.0735 | 0.0856 | 0.0909 | False | False | 0.1195 | 365.8610 | True | none |  | True |
| person_emp_length | 0.0671 | 0.0599 | 0.0671 | 0.0680 | False | False | 0.1080 | 195.2567 | True | none |  | True |
| cb_person_cred_hist_length | 0.0044 | 0.0036 | 0.0038 | 0.0040 | False | False | 0.0273 | 403.6033 | True | none |  | False |

Candidates passing Stage 1: 8 of 9.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| loan_percent_income | 1 | False | 0.08778 | 0.00507 | 1.00000 | True | 0.00000 | 1.22354 |
| loan_grade | 1 | False | 0.07422 | 0.00491 | 1.00000 | True | 0.00000 | 1.06829 |
| person_income | 1 | False | 0.06253 | 0.00409 | 1.00000 | True | 0.00000 | 1.07979 |
| loan_int_rate | 1 | False | 0.06149 | 0.00508 | 1.00000 | True | 0.00000 | 0.85619 |
| person_home_ownership | 1 | False | 0.03843 | 0.00312 | 1.00000 | True | 0.00000 | 0.87194 |
| loan_intent | 1 | False | 0.02076 | 0.00170 | 1.00000 | True | 0.00000 | 0.86273 |
| loan_amnt | 1 | False | 0.01871 | 0.00167 | 1.00000 | True | 0.00000 | 0.79433 |
| person_emp_length | 1 | False | 0.01438 | 0.00171 | 1.00000 | True | 0.00000 | 0.59289 |
| __shadow__0_loan_percent_income | 1 | True | 0.00088 | 0.00016 | 0.60250 | False | 0.00000 | 0.38459 |
| __shadow__1_loan_amnt | 1 | True | 0.00082 | 0.00013 | 0.38900 | False | 0.00000 | 0.43802 |
| __shadow__4_loan_int_rate | 1 | True | 0.00052 | 0.00012 | 0.00850 | False | 0.00002 | 0.31431 |
| __shadow__6_person_home_ownership | 1 | True | 0.00027 | 0.00006 | 0.00000 | False | 0.00001 | 0.32235 |
| __shadow__7_loan_intent | 1 | True | 0.00014 | 0.00008 | 0.00000 | False | 0.06965 | 0.12898 |
| __shadow__8_loan_percent_income | 1 | True | -0.00003 | 0.00001 | 0.00000 | False | 0.06965 | -0.13009 |
| __shadow__3_person_emp_length | 1 | True | -0.00007 | 0.00003 | 0.00000 | False | 0.00867 | -0.19036 |
| __shadow__2_person_income | 1 | True | -0.00016 | 0.00003 | 0.00000 | False | 0.00000 | -0.40005 |
| __shadow__9_loan_amnt | 1 | True | -0.00047 | 0.00006 | 0.00000 | False | 0.00000 | -0.53981 |
| __shadow__5_loan_grade | 1 | True | -0.00052 | 0.00007 | 0.00000 | False | 0.00000 | -0.51079 |

Shadow bar (95th pct of 10 shadow players): **0.00085**. Mode: sampled. Subsets evaluated: 2776. Model fits: 13875.

Implementation audit (efficiency property): sum of Shapley values 0.379676 vs v(full)-v(empty) 0.379676, abs diff 5.55e-17. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | loan_percent_income | 1 | 0.4343 | [0.4203, 0.4496] | 0.3397 | 0.7003 | 0.1412 | 42.83% | 0.0000 |
| 2 | loan_grade | 2 | 0.6728 | [0.6624, 0.6843] | 0.5812 | 0.8105 | 0.1170 | 11.44% | 0.0000 |
| 3 | person_income | 3 | 0.7300 | [0.7195, 0.7400] | 0.6145 | 0.8388 | 0.1092 | 3.91% | 0.0000 |
| 4 | loan_int_rate | 4 | 0.7306 | [0.7200, 0.7406] | 0.6135 | 0.8390 | 0.1093 | 3.83% | 0.0000 |
| 5 | person_home_ownership | 5 | 0.7444 | [0.7340, 0.7547] | 0.6175 | 0.8502 | 0.1009 | 2.01% | 0.0000 |
| 6 | loan_intent | 6 | 0.7597 | [0.7498, 0.7694] | 0.6274 | 0.8575 | 0.0979 | -0.01% | 0.8833 |
| 7 | loan_amnt | 7 | 0.7601 | [0.7504, 0.7694] | 0.6288 | 0.8579 | 0.0978 | -0.05% | 0.1835 |
| 8 | person_emp_length | 8 | 0.7597 | [0.7502, 0.7693] | 0.6283 | 0.8578 | 0.0975 | 0.00% | 1.0000 |

**Selected k = 6** (6 columns, Gini 0.7597, relative loss -0.01%, DeLong p = 0.8833). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`loan_percent_income`, `loan_grade`, `person_income`, `loan_int_rate`, `person_home_ownership`, `loan_intent`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.1706 | 0.0632 | **0.0629** |
| ECE | - | 0.0133 | **0.0050** |

---

> **Cleaned-file re-run (2026-10-18).** This record is the fresh run on the cleaned
> `credit_risk_dataset.csv` (corrupt `target` deleted, genuine `loan_status` adopted as `target`, junk dropped).
> Stages 0–3 reproduce the committed analytics exactly (8/9 screen, shadow bar 0.00085, k=6 Gini 0.7597, DeLong
> p 0.883). The Stage-4b backtest and fairness below are recomputed on this file.

## Stage 4b — per-grade calibration backtest (G4; CRE36.122-123) — cleaned-file re-run

Held-out 80/20 (seed 42), 6-col benchmark, calibrated PD floored at 0.03%. Test n=6,517. **AUC 0.877 / Gini 0.754.**

| Grade | n | Expected | Realised | Within CI? |
|---|--:|--:|--:|:--:|
| AAA | 241 | 0.1% | 0.4% | OK |
| AA | 107 | 1.0% | 2.8% | OK |
| A | 27 | 1.9% | 3.7% | OK |
| BBB | 956 | 2.8% | 2.9% | OK |
| BB | 730 | 5.4% | 5.5% | OK |
| B | 2275 | 8.6% | 8.7% | OK |
| CCC | 192 | 14.9% | 8.9% | **X** (over-predicts, small cell) |
| CC | 450 | 22.5% | 23.8% | OK |
| C | 339 | 41.6% | 40.1% | OK |
| D | 1200 | 74.3% | 74.2% | OK |

**9 of 10 grades within CI; ECE 0.011; Hosmer-Lemeshow χ²=7.93, df=8, p=0.44 → not rejected.** Excellent calibration
across the full AAA–D spectrum; the one miss (CCC) over-predicts (conservative), n=192.

### Availability sensitivity (origination-only, held-out) — cleaned-file re-run
Dropping the two circular features (`loan_grade`, `loan_int_rate`) leaves the valid application-time model:
**Gini 0.609 / AUC 0.804** vs the 6-col benchmark 0.754 / 0.877 — **ΔGini 0.145 (−19.2% held-out**; −22.2% on OOF in
the committed run), the largest circularity cost in the corpus. The origination-only model is HELOC-tier and
independent of the incumbent lender's verdict.

### Fairness — age disparate impact (G4), cleaned-file re-run
`person_age` is excluded from the model (ECOA, G0) but tested on the scored held-out output (predictive parity).

| Age band | n | mean PD | actual default | PD gap vs 25–34 |
|---|--:|--:|--:|--:|
| <25 | 2,378 | 0.226 | 0.230 | +0.013 |
| 25–34 (ref) | 3,268 | 0.213 | 0.213 | 0 |
| 35–44 | 689 | 0.213 | 0.199 | ~0 |
| 45–54 | 139 | 0.273 | 0.252 | +0.060 |
| 55+ | 43 | 0.171 | 0.186 | −0.042 |

Gaps < 0.05 except the small, noisy 45–54 cell (+0.060, n=139), which over-predicts (pred 0.273 vs actual 0.252) — so
predictive parity broadly holds. No material disparate impact; the model mirrors the real age–default gradient.
