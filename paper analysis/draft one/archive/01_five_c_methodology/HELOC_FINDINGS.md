# HELOC (FICO Explainable ML Challenge) — Five C's Findings

Sixth dataset tested with the Five C's methodology, built under v2 from the start (Steps 1-4 per category,
correlation-based pre-pruning per `METHODOLOGY.md` Step 2a, then pooled Shapley/Benjamini-Hochberg).

## Dataset background

`data/ml_lab/datasets/heloc.csv` — FICO Explainable ML Challenge dataset. 10,459 rows, 23 raw features +
target. Target: binary, near-balanced (52.2% positive — the most balanced target of any dataset in this
project). Despite "Home Equity" in the name, this is **pure credit-bureau behavioral data** — no property
value/LTV field exists, so Collateral has zero genuine columns, same as PAK/GMSC/Taiwan.

**Major data-quality pattern:** special sentinel codes appear in nearly every column — `-9` ("no data
available," ~588 rows, likely the same thin-file group across columns), `-8` ("condition not met"), `-7`
("condition not applicable" — e.g. `MSinceMostRecentDelq=-7` for 44.6% of rows means "never delinquent,"
*good* news, not missing data). These were kept as explicit categories via hybrid binning (special codes as
their own bin, remaining values quantile-binned) rather than dropped or imputed — confirmed directly that
different columns' special-code groups carry *opposite*-direction signal (e.g. `MSinceMostRecentDelq`'s
special group has *lower* default rate; `NumBank2NatlTradesWHighUtilization`'s has *higher*).

## Five C's categorization

| Five C's | Count | Columns |
|---|---:|---|
| Character | 9 | ExternalRiskEstimate, NumSatisfactoryTrades, NumTrades60Ever2DerogPubRec, NumTrades90Ever2DerogPubRec, PercentTradesNeverDelq, MSinceMostRecentDelq, MaxDelq2PublicRecLast12M, MaxDelqEver, NumBank2NatlTradesWHighUtilization |
| Capacity | 4 | MSinceOldestTradeOpen, MSinceMostRecentTradeOpen, AverageMInFile, NumTotalTrades |
| Capital | 6 | NetFractionRevolvingBurden, NetFractionInstallBurden, NumRevolvingTradesWBalance, NumInstallTradesWBalance, PercentTradesWBalance, PercentInstallTrades |
| Collateral | 0 | None — pure bureau data despite the "Home Equity" name |
| Conditions | 4 | NumTradesOpeninLast12M, MSinceMostRecentInqexcl7days, NumInqLast6M, NumInqLast6Mexcl7days |

## Character — results (hybrid binning: special codes as own category + quantile bins for normal range)

**Reference ranges:**

| IV range | Strength | | Cramér's V range | Strength |
|---|---|---|---|---|
| < 0.02 | Useless | | < 0.1 | Negligible |
| 0.02–0.1 | Weak | | 0.1–0.3 | Weak |
| 0.1–0.3 | Medium | | 0.3–0.5 | Moderate |
| > 0.3 | Strong | | > 0.5 | Strong |

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| ExternalRiskEstimate | 285.88 | 2,152.3 | ~0 | **0.9552** | **0.4536** | ~0 | **Strong — by far the strongest predictor** |
| PercentTradesNeverDelq | 281.10 | 826.4 | 3.09e-175 | **0.3396** | 0.2811 | 4.75e-150 | Strong (IV) — keep |
| MaxDelq2PublicRecLast12M | 2.868 (minor dip) | 725.0 | 1.35e-155 | **0.2916** | 0.2633 | 3.66e-138 | Medium/weak, confirmed — keep |
| MSinceMostRecentDelq | 84.14 | 719.4 | 3.13e-146 | **0.2898** | 0.2623 | 3.50e-37 | Medium/weak — keep |
| NumBank2NatlTradesWHighUtilization | 278.71 | 573.1 | 1.29e-121 | **0.2317** | 0.2341 | 4.45e-71 | Medium — keep |
| MaxDelqEver | 281.10 | 550.5 | 5.40e-119 | **0.2157** | 0.2294 | 5.48e-103 | Medium — keep |
| NumSatisfactoryTrades | 281.10 | 265.9 | 2.41e-51 | 0.1060 | 0.1595 | 1.42e-46 | Medium (barely)/weak — keep |
| NumTrades60Ever2DerogPubRec | 274.88 | 241.1 | 5.39e-52 | 0.0988 | 0.1518 | 1.89e-69 | Weak/weak — keep |
| NumTrades90Ever2DerogPubRec | 281.10 | 159.8 | 1.97e-35 | 0.0662 | 0.1236 | 9.97e-47 | Weak/weak — keep |

All nine kept — `ExternalRiskEstimate` is the strongest predictor found anywhere in this project (IV=0.955),
unsurprising since it's a pre-computed FICO-style risk score, not a raw behavioral feature.

## Capacity — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| AverageMInFile | 281.10 | 714.1 | 5.95e-147 | **0.2932** | 0.2613 | 1.09e-130 | Medium — keep |
| MSinceOldestTradeOpen | 114.26 | 530.4 | 1.02e-106 | **0.2165** | 0.2252 | 5.44e-90 | Medium — keep |
| NumTotalTrades | 281.10 | 137.9 | 1.15e-24 | 0.0537 | 0.1148 | 6.46e-26 | Weak/weak — keep |
| MSinceMostRecentTradeOpen | 281.10 | 47.5 | 3.19e-07 | 0.0183 | 0.0674 | 1.13e-07 | Useless/negligible — reject |

Three kept, one rejected (fails both pooling thresholds narrowly).

## Capital — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| NetFractionRevolvingBurden | 88.92 | 1,323.6 | 3.62e-277 | **0.5599** | 0.3557 | 1.79e-180 | **Strong — keep** |
| PercentTradesWBalance | 8.61 | 815.6 | 9.04e-169 | **0.3309** | 0.2793 | 3.21e-138 | Strong (IV) — keep |
| NumRevolvingTradesWBalance | 74.58 | 256.8 | 3.60e-50 | 0.1041 | 0.1567 | 2.74e-19 | Medium (barely)/weak — keep |
| PercentInstallTrades | 281.10 | 234.0 | 1.25e-44 | 0.0930 | 0.1496 | 2.96e-29 | Weak/weak — keep |
| NetFractionInstallBurden | 259.59 | 105.9 | 1.19e-17 | 0.0409 | 0.1006 | 2.31e-15 | Weak/weak (barely) — keep |
| NumInstallTradesWBalance | 281.10 | 50.1 | 1.32e-09 | 0.0193 | 0.0692 | 7.15e-08 | Useless/negligible — reject |

Five kept, one rejected.

## Conditions — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| MSinceMostRecentInqexcl7days | 227.56 | 614.5 | 1.71e-129 | **0.2562** | 0.2424 | 4.11e-29 | Medium — keep |
| NumInqLast6M | 281.10 | 196.4 | 2.20e-41 | 0.0777 | 0.1370 | 2.78e-37 | Weak/weak — keep |
| NumInqLast6Mexcl7days | 281.10 | 178.3 | 1.77e-37 | 0.0703 | 0.1306 | 2.12e-34 | Weak/weak — keep |
| NumTradesOpeninLast12M | 281.10 | 49.8 | 1.54e-09 | 0.0192 | 0.0690 | 1.23e-08 | Useless/negligible — reject |

Three kept, one rejected.

## Full Step 1-4 pooled candidate list — 20 of 23 raw columns

Only 3 rejected (all narrow misses on both thresholds). 20-column pool makes exact Shapley infeasible
(2²⁰ ≈ 1,048,575 subsets).

## Step 2a — correlation-based pre-pruning (20 → 13 columns)

Checked pairwise Spearman correlation among the 20 pooled candidates. Automated greedy pruning (iteratively
drop the weaker-IV member of the highest remaining correlated pair above 0.7) found 6 clusters:

| Cluster | Correlation | Kept | Dropped |
|---|---:|---|---|
| Inquiry counts | 0.985 | NumInqLast6M | NumInqLast6Mexcl7days |
| Delinquency severity (3-way) | 0.85-0.92 | PercentTradesNeverDelq | MaxDelq2PublicRecLast12M, MaxDelqEver |
| Account count | 0.882 | NumSatisfactoryTrades | NumTotalTrades |
| Derogatory severity | 0.871 | NumTrades60Ever2DerogPubRec | NumTrades90Ever2DerogPubRec |
| Account age | 0.740 | AverageMInFile | MSinceOldestTradeOpen |
| Utilization-related | 0.730 | NetFractionRevolvingBurden | NumBank2NatlTradesWHighUtilization |

Plus `MSinceMostRecentTradeOpen`/`NumTradesOpeninLast12M`/`NumInstallTradesWBalance` already rejected at
Step 1-4. **Final pruned pool: 13 columns.**

## Step 5 v2 — pooled Shapley / Benjamini-Hochberg analysis

8,191 subsets (2¹³−1) × 5 folds = 40,955 fits, ~66 minutes. Efficiency check: sum of Shapley values
reconstructs `v(full) − v(empty)` to within 1.67×10⁻¹⁶ (floating-point level) — confirmed correct.

| Column | Mean Shapley (ΔAUC) | Std | t-stat | raw p | BH-adjusted p | Keep? |
|---|---:|---:|---:|---:|---:|---:|
| ExternalRiskEstimate | 0.05691 | 0.00337 | 37.82 | 2.92e-06 | 3.66e-05 | **YES** |
| NetFractionRevolvingBurden | 0.03958 | 0.00447 | 19.79 | 3.84e-05 | 7.14e-05 | **YES** |
| AverageMInFile | 0.02871 | 0.00281 | 22.88 | 2.16e-05 | 4.69e-05 | **YES** |
| MSinceMostRecentInqexcl7days | 0.02841 | 0.00517 | 12.28 | 2.53e-04 | 3.65e-04 | **YES** |
| PercentTradesNeverDelq | 0.02718 | 0.00190 | 32.07 | 5.64e-06 | 3.66e-05 | **YES** |
| MSinceMostRecentDelq | 0.02375 | 0.00186 | 28.56 | 8.95e-06 | 3.76e-05 | **YES** |
| PercentTradesWBalance | 0.02293 | 0.00206 | 24.87 | 1.55e-05 | 4.04e-05 | **YES** |
| NumTrades60Ever2DerogPubRec | 0.01419 | 0.00178 | 17.81 | 5.84e-05 | 9.48e-05 | **YES** |
| NumSatisfactoryTrades | 0.01397 | 0.00264 | 11.81 | 2.94e-04 | 3.83e-04 | **YES** |
| NumRevolvingTradesWBalance | 0.01361 | 0.00114 | 26.78 | 1.16e-05 | 3.76e-05 | **YES** |
| NumInqLast6M | 0.01149 | 0.00258 | 9.96 | 5.71e-04 | 6.75e-04 | **YES** |
| PercentInstallTrades | 0.00881 | 0.00276 | 7.13 | 2.05e-03 | 2.05e-03 | **YES** |
| NetFractionInstallBurden | 0.00513 | 0.00134 | 8.53 | 1.04e-03 | 1.12e-03 | **YES** |

**All 13 pruned candidates confirmed real and additive — no further elimination at the pooled stage.**

## Final model

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| All 13 pruned/confirmed columns | 0.7949 | **0.7942 ± 0.0069** | `lab_20261009_135420_heloc_v2_final_thirteen_v2_xgboost` |
| Full 23-column baseline | 0.7928 | 0.7950 ± 0.0065 | `lab_20261009_...heloc_full_baseline_xgboost` |

**Gap to full-column baseline: only 0.0008 AUC** — the smallest gap of any dataset in this project so far,
and notably, the 13-column pruned model's *holdout* AUC (0.7949) actually slightly *exceeds* the full
23-column baseline's (0.7928), though CV (the more reliable estimate) shows the full model marginally ahead.
Feature importance: `ExternalRiskEstimate` 35.9%, `MSinceMostRecentInqexcl7days` 9.3%,
`NetFractionRevolvingBurden` 7.7%, `PercentTradesNeverDelq` 6.5%, `AverageMInFile` 5.9%, `NumSatisfactoryTrades` 5.9%.

## Probability calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier score | 0.2495 | 0.1852 | **0.1834** |
| ECE | — | 0.0241 | **0.0216** |
| AUC | — | 0.7949 | 0.7968 |

Smallest calibration gap of any dataset so far — makes sense given HELOC's near-balanced target (52.2%)
means `scale_pos_weight` has much less distorting effect than on heavily imbalanced datasets like GMSC
(6.7% positive) or PAK (26%). Still a real, if modest, improvement.
