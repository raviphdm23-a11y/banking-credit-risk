# Taiwan Credit Card (UCI "Default of Credit Card Clients") — Five C's Findings

Fifth dataset tested with the Five C's methodology, built under v2 from the start (Steps 1-4 per category,
then correlation-based pre-pruning per `METHODOLOGY.md` Step 2a, then pooled Shapley/Benjamini-Hochberg).

## Dataset background

`data/ml_lab/datasets/Taiwan_UCI_Credit_Card.csv` — classic UCI "Default of Credit Card Clients" dataset.
30,000 rows, 23 raw features + target. Target: binary, overall default rate 22.12%. No missing values.
Known quirks: `EDUCATION` and `MARRIAGE` both have undocumented codes beyond the official UCI documentation
(EDUCATION 0/5/6, MARRIAGE 0, beyond the documented 1-4/1-3 ranges respectively); `PAY_0` is the *current*
month, not month 1 of a sequence (there is no `PAY_1` — a known naming quirk in the original dataset).

## Five C's categorization

| Five C's | Count | Columns |
|---|---:|---|
| Character | 10 | PAY_0, PAY_2, PAY_3, PAY_4, PAY_5, PAY_6 (repayment status, last 6 months), SEX, EDUCATION, MARRIAGE, AGE |
| Capacity | 6 | PAY_AMT1-6 (amount actually paid, last 6 months) |
| Capital | 6 | BILL_AMT1-6 (outstanding bill balance, last 6 months) |
| Collateral | 0 | None — unsecured revolving credit, same as PAK and GMSC |
| Conditions | 1 | LIMIT_BAL (credit limit assigned to the card) |

Debatable calls: demographics bundled into Character (following PAK's precedent, since this dataset has no
loan-specific "conditions" field); `LIMIT_BAL` treated as a Condition of the credit line rather than Capacity.

## Character — results

**Reference ranges:**

| IV range | Strength | | Cramér's V range | Strength |
|---|---|---|---|---|
| < 0.02 | Useless | | < 0.1 | Negligible |
| 0.02–0.1 | Weak | | 0.1–0.3 | Weak |
| 0.1–0.3 | Medium | | 0.3–0.5 | Moderate |
| > 0.3 | Strong | | > 0.5 | Strong |

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| PAY_0 (current month) | 1.991 | 5,365.97 | ~0 | **0.8698** | **0.4229** | ~0 | Strong — keep |
| PAY_2 | 0.221 | 3,474.47 | ~0 | **0.5424** | **0.3403** | ~6.4e-309 | Strong — keep |
| PAY_3 | 0.664 | 2,622.46 | ~0 | **0.4109** | 0.2957 | ~1.8e-249 | Strong — keep |
| PAY_4 | 0.442 | 2,341.47 | ~0 | **0.3592** | 0.2794 | ~8.0e-199 | Strong — keep |
| PAY_5 | 0.221 | 2,197.70 | ~0 | **0.3293** | 0.2707 | ~4.9e-167 | Strong — keep |
| PAY_6 | 0.442 | 1,886.84 | ~0 | **0.2884** | 0.2508 | ~1.5e-134 | Medium/weak — keep |
| EDUCATION | 3.097 | 163.22 | 1.23e-32 | 0.0363 | 0.0738 | — | Weak (IV) — pool |
| AGE | 506.11 | 108.55 | 2.90e-19 | 0.0206 | 0.0602 | — | Weak (IV, barely) — pool |
| SEX | 2629.63 | 47.71 | 4.95e-12 | 0.0000 | 0.0399 | — | Useless/negligible — reject |
| MARRIAGE | 11.945 | 35.66 | 8.83e-08 | 0.0056 | 0.0345 | — | Useless/negligible — reject |

All six PAY_* columns gate-failed slightly (rare high-delay categories) but Mann-Whitney confirms all
overwhelmingly real (p≈0 at n=30,000) — the strongest Character columns found in any dataset in this
project so far. `SEX`/`MARRIAGE` rejected despite "significant" p-values — a clean demonstration of why
p-value alone is insufficient at this sample size.

## Capacity — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| PAY_AMT1 | 637.94 | 842.5 | 1.40e-176 | 0.1611 | 0.1676 | 4.62e-170 | Medium — keep |
| PAY_AMT2 | 542.38 | 737.5 | 5.95e-154 | 0.1475 | 0.1568 | 9.96e-151 | Medium — keep |
| PAY_AMT3 | 616.26 | 632.9 | 2.01e-131 | 0.1227 | 0.1452 | 8.99e-129 | Medium — keep |
| PAY_AMT6 | 490.62 | 435.7 | 5.34e-90 | 0.0903 | 0.1205 | 3.18e-98 | Weak — keep |
| PAY_AMT4 | 525.57 | 446.3 | 2.72e-92 | 0.0899 | 0.1220 | 7.29e-109 | Weak — keep |
| PAY_AMT5 | 516.72 | 392.6 | 9.11e-81 | 0.0811 | 0.1144 | 1.13e-90 | Weak — keep |

All six cleared the gate comfortably, all kept — clean recency pattern (more recent payment amounts are
stronger predictors).

## Capital — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| BILL_AMT6 | 287.78 | 96.9 | 6.71e-17 | 0.0192 | 0.0568 | 0.9895 | Useless/negligible — reject |
| BILL_AMT5 | 407.01 | 72.1 | 5.83e-12 | 0.0141 | 0.0490 | 0.2354 | Useless/negligible — reject |
| BILL_AMT1 | 663.60 | 62.5 | 4.41e-10 | 0.0120 | 0.0456 | 1.15e-05 | Useless/negligible — reject |
| BILL_AMT2 | 624.89 | 58.5 | 2.56e-09 | 0.0111 | 0.0442 | 0.00706 | Useless/negligible — reject |
| BILL_AMT4 | 471.38 | 56.5 | 6.43e-09 | 0.0110 | 0.0434 | 0.1478 | Useless/negligible — reject |
| BILL_AMT3 | 547.47 | 53.6 | 2.25e-08 | 0.0103 | 0.0423 | 0.0282 | Useless/negligible — reject |

**All six rejected.** Raw bill balance alone carries almost no signal — it's payment *status* (PAY_*) and
actual amount *paid* (PAY_AMT*) that matter, not the balance owed. `BILL_AMT1`'s Mann-Whitney p (1.15e-05)
noticeably stronger than `BILL_AMT6`'s (0.99, essentially random) — recency fades to nothing for this
particular signal.

## Conditions — results

| Column | min_expected | chi² | p-value | IV | Cramér's V | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| LIMIT_BAL | 344.19 | 929.0 | 3.42e-194 | **0.1781** | 0.1760 | 1.23e-189 | Medium — keep |

Clean, strong, single-column result.

## Full Step 1-4 pooled candidate list — 15 of 23 raw columns

| Category | Pooled candidates | Rejected |
|---|---|---|
| Character | PAY_0, PAY_2, PAY_3, PAY_4, PAY_5, PAY_6, EDUCATION, AGE | SEX, MARRIAGE |
| Capacity | PAY_AMT1-6 (all 6) | — |
| Capital | — | BILL_AMT1-6 (all 6) |
| Conditions | LIMIT_BAL | — |

## Step 2a — correlation-based pre-pruning (15 → 12 columns)

15 pooled candidates made exact Shapley impractical (2¹⁵−1 = 32,767 subsets, ~8.7 hours estimated —
confirmed via timed sampling across subset sizes). Per `METHODOLOGY.md` Step 2a: checked pairwise Spearman
correlation, found `PAY_0` through `PAY_6` form a temporal correlation chain (adjacent months correlate
0.80-0.82, more distant months less so but still substantial). Automated greedy pruning (iteratively drop
the weaker-IV member of the highest remaining correlated pair above 0.7, re-checking after each removal —
avoids over-collapsing the whole chain into one survivor) dropped only `PAY_3`, `PAY_4`, `PAY_5`, keeping
`PAY_0`, `PAY_2`, `PAY_6` spanning the time range plus all of `PAY_AMT1-6`, `EDUCATION`, `AGE`, `LIMIT_BAL`.

**Final pruned pool: 12 columns.**

## Phased execution and checkpoint reuse

Run in phases (by subset size, checkpointed/resumable) rather than one unbroken ~8.7-hour job — full detail
in `TAIWAN_SHAPLEY_PROGRESS.md`. Phases 1-2 of the original 15-column plan (sizes 1-7, 16,384 subsets)
completed before the pruning decision. Since a subset's value doesn't depend on which larger pool it was
drawn from, every already-computed subset using only the 12 survivors was directly reusable: of the 4,095
subsets needed for the pruned pool, **3,301 were reused for free, only 794 new subsets needed**.

## Step 5 v2 — pooled Shapley / Benjamini-Hochberg analysis

Efficiency check: sum of Shapley values reconstructs `v(full) − v(empty)` to within 3.3×10⁻¹⁶
(floating-point level) — confirmed correct.

| Column | Mean Shapley (ΔAUC) | Std | t-stat | raw p | BH-adjusted p | Keep? |
|---|---:|---:|---:|---:|---:|---:|
| PAY_0 | 0.07692 | 0.00363 | 47.35 | 1.19e-06 | 7.14e-06 | **YES** |
| PAY_2 | 0.03974 | 0.00246 | 36.10 | 3.51e-06 | 1.05e-05 | **YES** |
| LIMIT_BAL | 0.02568 | 0.00335 | 17.15 | 6.79e-05 | 1.02e-04 | **YES** |
| PAY_6 | 0.02566 | 0.00158 | 36.30 | 3.44e-06 | 1.05e-05 | **YES** |
| PAY_AMT1 | 0.02230 | 0.00267 | 18.69 | 4.83e-05 | 8.27e-05 | **YES** |
| PAY_AMT2 | 0.01992 | 0.00086 | 51.61 | 8.44e-07 | 7.14e-06 | **YES** |
| PAY_AMT3 | 0.01771 | 0.00266 | 14.91 | 1.18e-04 | 1.42e-04 | **YES** |
| PAY_AMT4 | 0.01604 | 0.00153 | 23.44 | 1.96e-05 | 4.71e-05 | **YES** |
| PAY_AMT5 | 0.01080 | 0.00125 | 19.35 | 4.20e-05 | 8.27e-05 | **YES** |
| PAY_AMT6 | 0.01018 | 0.00198 | 11.52 | 3.24e-04 | 3.54e-04 | **YES** |
| EDUCATION | 0.00719 | 0.00098 | 16.40 | 8.09e-05 | 1.08e-04 | **YES** |
| AGE | 0.00365 | 0.00145 | 5.63 | 4.89e-03 | 4.89e-03 | **YES** |

**All 12 pruned candidates confirmed real and additive — no further elimination at the pooled stage.**

## Final model

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| All 12 pruned/confirmed columns | 0.7718 | **0.7754 ± 0.0046** | `lab_20261009_124744_taiwan_v2_final_twelve_xgboost` |

Feature importance: `PAY_0` 46.8%, `PAY_2` 17.5%, `PAY_6` 8.5%, `LIMIT_BAL` 4.1%, `PAY_AMT2` 4.0%, `PAY_AMT3`
3.7%, `PAY_AMT1` 3.2%, `PAY_AMT4` 2.7% — `PAY_0` alone carries nearly half the model's total importance.

## Probability calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier score | 0.1723 | 0.1810 | **0.1359** |
| ECE | — | 0.2011 | **0.0093** |
| AUC | — | 0.7718 | 0.7700 |

Raw model's Brier score was worse than the trivial baseline — now fixed. ECE improved 95% (0.2011→0.0093).
AUC essentially unchanged.

## Methodology note — correlation pruning validated as sound

Unlike PAK's/German Credit's order-dependency corrections, Taiwan's story is specifically about **pool size
management**, not a flawed v1 decision (there was no v1 here). The automated greedy pruning approach proved
appropriately conservative — it correctly avoided collapsing the entire PAY_2→PAY_6 correlation chain into
a single survivor (a risk flagged before running it), instead keeping 3 well-spaced representatives
(`PAY_0`, `PAY_2`, `PAY_6`) spanning the full 6-month window, each later confirmed independently significant
by the pooled Shapley/BH test.
