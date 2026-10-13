# GMSC ("Give Me Some Credit") — Five C's Findings (private reference, not shown on frontend)

Fourth dataset tested with the Five C's methodology, after PAK, HMEQ, and German Credit — all previously
redone/built under the current **Step 5 v2** procedure (pooled Shapley/Benjamini-Hochberg). GMSC was built
under v2 from the start, no v1 history to supersede.

## Methodology

Full shared methodology lives in `METHODOLOGY.md` in this same folder.

## Dataset background

`data/ml_lab/datasets/GMSC.csv` — Kaggle's "Give Me Some Credit" competition dataset. 149,391 rows, 11
columns (10 raw features + target). Target: binary, overall default rate 6.70% (much lower base rate than
PAK's 26% or German Credit's 30% — closer to HMEQ's 20%, but still the leanest of the four so far).

## Five C's categorization

| Five C's | Count | Columns |
|---|---:|---|
| Character | 3 | NumberOfTime30-59DaysPastDueNotWorse, NumberOfTime60-89DaysPastDueNotWorse, NumberOfTimes90DaysLate |
| Capacity | 3 | age, MonthlyIncome, DebtRatio |
| Capital | 2 | NumberOfOpenCreditLinesAndLoans, NumberRealEstateLoansOrLines |
| Collateral | 1 | RevolvingUtilizationOfUnsecuredLines |
| Conditions | 1 | NumberOfDependents |

Flagged as debatable at categorization time: `RevolvingUtilizationOfUnsecuredLines` is a weak fit for
Collateral (it's a credit-utilization ratio, arguably closer to Capital) — this dataset has **no genuine
collateral/asset-value field at all**, same as PAK. `NumberOfDependents` as Conditions is also a stretch
(household-burden indicator, arguably closer to Capacity) — categorized there mainly by elimination.

## Major data-quality finding — Character columns' 96/98 sentinel values

All three Character columns share the exact same 225 rows with values of 96 or 98 (5 rows at 96, 220 at 98),
almost certainly a special status/error code rather than a literal count (96-98 late payments is not
realistic). **This is not noise to discard — it's extremely informative**: those 225 rows have a 60.4%
default rate vs. 6.6% baseline (9x elevation). Tested directly: excluding these rows barely changes IV/Cramér's
V for any of the three columns (e.g. `NumberOfTimes90DaysLate` IV drops only 0.8834→0.8514) — confirming the
columns are genuinely strong across their normal 0-17 range, not propped up by this anomaly alone.

## Character — results

Target: `target` (positive class = `1` = default, overall rate 6.70%).

**Reference ranges:**

| IV range | Strength | | Cramér's V range | Strength |
|---|---|---|---|---|
| < 0.02 | Useless | | < 0.1 | Negligible |
| 0.02–0.1 | Weak | | 0.1–0.3 | Weak |
| 0.1–0.3 | Medium | | 0.3–0.5 | Moderate |
| > 0.3 | Strong | | > 0.5 | Strong |

| Column | min_expected | chi² | p-value | IV (raw-category) | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| NumberOfTimes90DaysLate | 0.067 | 18,977.5 | ~0 | **0.8834** | 0.3564 | ~0 | Strong — keep |
| NumberOfTime30-59DaysPastDueNotWorse | 0.067 | 12,538.2 | ~0 | **0.7635** | 0.2897 | ~0 | Strong — keep |
| NumberOfTime60-89DaysPastDueNotWorse | 0.067 | 12,530.5 | ~0 | **0.6027** | 0.2896 | ~0 | Strong — keep |

All three failed the Step 2 gate (extreme skew + 96/98 tail) but resolved via Mann-Whitney (p≈0 at
n=149,391) — the "real signal masked by a thin tail" failure mode, same as HMEQ's DEROG/DELINQ/NINQ, not the
PAK-style inflation artifact. Note: `compute_iv`'s default quantile-binning collapsed to **IV=0** for two of
the three columns (degenerate-bin artifact from extreme skew) — IV recomputed using raw-category binning
instead, matching the chi²/Cramér's V treatment.

## Capacity — results

| Column | Missing % | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| age | 0.0% | 864.95 | 2,066.8 | ~0 | 0.2584 | 0.1176 | ~0 | Medium/weak — real, pool |
| MonthlyIncome | 19.56% | 30.22 | 698.1 | 1.78e-144 | 0.0739 | 0.0684 | 1.74e-120 | Weak (IV) — pool |
| DebtRatio | 0.0% | 1000.56 | 788.5 | 6.27e-164 | 0.0736 | 0.0727 | 2.99e-14 | Weak (IV) — pool, with major caveat below |

**DebtRatio measurement-quality caveat:** 19.3% of rows have DebtRatio>10 (a ratio normally well under 2),
and 92.7% of those also have missing `MonthlyIncome` — strongly suggesting the extreme tail is a computation
artifact from unknown income, not genuine debt burden. Tellingly, that extreme-tail group has a *lower*
default rate (5.57%) than the rest (6.97%) — the opposite of what a real high-debt-ratio risk signal would
show. The Mann-Whitney significance is real, but the column's economic interpretation can't be trusted the
way `age`'s clean pattern can. Even restricted to known-income rows, a smaller tail (1.75%) still shows
implausible DebtRatio values up to 61,106 — a second, smaller data-quality layer beyond the missing-income one.

`age=0` (1 row, clearly a data-entry error) is negligible and not separately treated.

## Capital — results

| Column | Treatment | min_expected | chi² | p-value | IV | Cramér's V | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| NumberOfOpenCreditLinesAndLoans | 10-bin quantile | 644.73 | 769.7 | 7.09e-160 | 0.0710 | 0.0718 | Weak — pool |
| NumberRealEstateLoansOrLines | raw-category | 0.067 (gate fail, resolved by shape) | 754.5 | 1.41e-141 | 0.0716 | 0.0711 | Weak, real U-shape — pool |

`NumberRealEstateLoansOrLines` initially gave IV=0.0123 under quantile binning (too aggressive given its
concentration at 0/1/2) — recomputed with raw-category treatment (IV=0.0716). The underlying pattern is a
genuine **U-shape**: 0 RE loans → 8.4% default, 1-2 loans → 5.3-5.6% (lowest, likely homeownership-stability
effect), then climbing steadily to 24.7% at 8 loans (overleveraged). Same non-monotonic signature as HMEQ's
`CLNO` — resolved by shape diagnosis (Step 4), not Mann-Whitney (which would likely be blind to this shape).

## Collateral & Conditions — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| RevolvingUtilizationOfUnsecuredLines | 1000.83 | 12,168.7 | ~0 | **1.1190** | 0.2854 | ~0 | **Strong — clear keep, strongest predictor in dataset** |
| NumberOfDependents | 0.07 (gate fail) | 347.9 | 3.87e-67 | 0.0355 | 0.0483 | 5.23e-68 | Weak (IV), confirmed real via Mann-Whitney — pool |

`RevolvingUtilizationOfUnsecuredLines` shares the same extreme-value measurement issue as `DebtRatio` (max
50,708 for a ratio that should sit near 0-1.5), but tells a different story: its extreme tail (util>1.5,
only 0.40% of rows) has a **26% default rate vs. 6.6% baseline** (4x elevation, in the directionally-sensible
direction — unlike `DebtRatio`'s tail, which pointed the wrong way). This is the strongest univariate
predictor found in the entire dataset (IV=1.119).

## Full pooled candidate list — all 10 of 10 raw columns

Unlike PAK (4/51 survived) or even HMEQ (11/12), **GMSC has zero dead columns at Step 1-4** — every raw
column clears the IV≥0.02 OR Cramér's V≥0.1 pooling bar. Consistent with this being a deliberately curated,
small feature set (a Kaggle competition dataset), not a messy real-world extract like PAK.

## Step 5 v2 — pooled Shapley / Benjamini-Hochberg analysis

2¹⁰ − 1 = 1,023 subsets × 5 folds = 5,115 XGBoost fits (~30 min wall-clock at 149,391 rows — the largest
per-fit dataset size run through this procedure so far). Efficiency check: sum of Shapley values
reconstructs `v(full) − v(empty)` to within 2.2×10⁻¹⁶ (floating-point level) — confirmed correct.

| Column | Mean Shapley (ΔAUC) | Std | t-stat | raw p | BH-adjusted p | Keep? |
|---|---:|---:|---:|---:|---:|---:|
| RevolvingUtilizationOfUnsecuredLines | 0.09609 | 0.00348 | 61.83 | 4.10e-07 | 3.69e-06 | **YES** |
| NumberOfTime30-59DaysPastDueNotWorse | 0.06403 | 0.00324 | 44.15 | 1.58e-06 | 4.68e-06 | **YES** |
| NumberOfTimes90DaysLate | 0.05380 | 0.00335 | 35.89 | 3.60e-06 | 7.20e-06 | **YES** |
| NumberOfTime60-89DaysPastDueNotWorse | 0.03845 | 0.00203 | 42.28 | 1.87e-06 | 4.68e-06 | **YES** |
| age | 0.03245 | 0.00136 | 53.39 | 7.37e-07 | 3.69e-06 | **YES** |
| DebtRatio | 0.02270 | 0.00187 | 27.17 | 1.09e-05 | 1.70e-05 | **YES** |
| NumberOfOpenCreditLinesAndLoans | 0.01746 | 0.00153 | 25.46 | 1.41e-05 | 1.77e-05 | **YES** |
| MonthlyIncome | 0.01607 | 0.00179 | 20.08 | 3.63e-05 | 4.04e-05 | **YES** |
| NumberRealEstateLoansOrLines | 0.01553 | 0.00131 | 26.60 | 1.19e-05 | 1.70e-05 | **YES** |
| NumberOfDependents | 0.00868 | 0.00162 | 11.97 | 2.79e-04 | 2.79e-04 | **YES** |

**All 10 confirmed real and additive — no elimination at the pooled stage either.** Full subset-level data:
`gmsc_v2_shapley_results.json`; full analysis: `gmsc_v2_shapley_analysis.json`. Note `DebtRatio` survives the
significance test despite its measurement-quality caveat — real signal, just not necessarily meaning what it
looks like it means.

## Final model

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| All 10 columns (= full-column baseline, since nothing was excluded) | 0.8654 | **0.8652 ± 0.0019** | `lab_20261008_231618_gmsc_v2_final_all_ten_xgboost` |

By the Hosmer-Lemeshow scale, this sits solidly in the **"excellent"** band (0.8-0.9) — the strongest result
of the four datasets tested so far. Feature importance: `NumberOfTimes90DaysLate` 28.7%, `NumberOfTime30-59...`
25.7%, `RevolvingUtilizationOfUnsecuredLines` 18.4%, `NumberOfTime60-89...` 13.0%, `NumberRealEstateLoansOrLines`
3.8%, `age` 3.0%, `NumberOfOpenCreditLinesAndLoans` 2.4%, `DebtRatio` 1.8% — the four Character/Collateral
columns dominate (86% of total importance combined), consistent with their much larger IV values.

## Probability calibration (2026-10-09)

Raw model's Brier score (0.1419 at original holdout; 0.1425 at the calibration-check split) is *worse* than
the trivial "always predict the 6.70% base rate" baseline (0.0625) — a model that ranks well (AUC 0.865) but
whose raw probabilities don't mean what they look like they mean, due to `scale_pos_weight` training (see
`CALIBRATION_NOTES.md` for full literature review and mechanism). Isotonic-regression calibration applied:

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier score | 0.0625 | 0.1425 | **0.0487** |
| ECE | — | 0.2513 | **0.0044** |
| AUC | — | 0.8654 | 0.8649 |

ECE improved 98% (0.2513→0.0044) and Brier score moved from worse-than-trivial to clearly better than
baseline, while AUC stayed essentially unchanged (−0.0005, within fold noise) — ranking quality fully
preserved. GMSC had the worst raw calibration of the four datasets tested, and the biggest fix.

## Cross-dataset note

GMSC is the first dataset in this project where **Step 1-4 screening eliminated nothing** — every raw
column was genuinely useful. This is itself a useful data point for the methodology's generalizability: it
correctly recognizes a "keep everything" dataset just as readily as it recognized PAK's "keep almost
nothing" (4/51) and German Credit's "keep about a quarter" (5/20) cases — three different ground truths,
correctly identified by the same unchanged procedure.
