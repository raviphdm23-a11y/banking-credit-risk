# HMEQ — SUPERSEDED by v2 redo below (2026-10-08)

> Everything below until "## v2 REDO" is the original v1 analysis (greedy, category-locked combination
> testing). Its univariate (Step 1-4) results held up and were reconfirmed in the redo, but its final
> combination decision (rejecting `MORTDUE`) did not — see the v2 section at the bottom for the current,
> methodology-approved result.

# HMEQ (Home Equity) — Exploratory Findings Log

Private reference for the ad hoc column-by-column investigation, started 2026-10-07. Same purpose and placement
as `PAK_FINDINGS.md` — **not shown anywhere in the Sandbox frontend** (unlike `DATASET_CATALOG.md`), purely for
Claude + the user to refer back to in later sessions. Lives in `paper analysis/draft one/` (untracked), not
`data/ml_lab/datasets/`, specifically so it does NOT get picked up by the per-dataset "Dataset Info" catalog
panel in the admin UI.

This dataset was picked specifically to test whether the methodology developed on PAK.csv generalizes to a
differently-shaped dataset — see "Why HMEQ" below.

All numbers below were computed directly against `data/ml_lab/datasets/hmeq.csv` (5,960 rows, 13 columns) on
2026-10-07 — nothing here is estimated or inferred from memory.

---

## Dataset background

- **Origin (confirmed earlier in this project, see `DATASET_CATALOG.md`):** SAS `SAMPSIO` library sample dataset,
  associated with Baesens, Roesch & Scheule, *Credit Risk Analytics* (Wiley, 2016) — same source family as the
  Mortgage panel dataset.
- **Structure confirmed 2026-10-07: cross-sectional, not time series.** No date/time/period column anywhere in
  the 13 columns; one row = one loan application (a static snapshot), zero duplicate rows. Direct contrast to the
  Mortgage panel dataset (50,000 loans × up to 60 monthly observations each) — HMEQ has none of that structure.
- Target: `target` (`BAD` in the original SAS file), 1 = bad/defaulted. Overall default rate: **19.95%**.
- **Why HMEQ, as a follow-up to PAK:** deliberately picked for being structurally different — no high-cardinality
  geography/location columns, no sparse demographic junk. Almost entirely genuine financial-behavior fields. A
  secured product (home equity), unlike PAK's unsecured retail card — meaning, unlike PAK, HMEQ has real
  Collateral columns to test (see Five C's table below).

---

## Methodology

Full shared methodology now lives in `METHODOLOGY.md` in this same folder — the four-tool **escalation ladder**
(IV/Cramér's V as the cheap first pass → `min_expected` reliability gate → Mann-Whitney U only when that gate
fails → model validation, mandatory for any surprising single column and for every combination step) developed
across this HMEQ analysis specifically to formalize what PAK's investigation had done ad hoc. **This is not a
four-way vote** — see that file for the full reasoning, including the two concrete proof points from this HMEQ
analysis: `CLNO`'s U-shaped relationship (chi-square caught it correctly, Mann-Whitney missed it — Mann-Whitney
is not a strict upgrade, it has its own blind spot) and the Character-column case (sparse-cell-flagged Cramér's V
results that Mann-Whitney then confirmed were real, the opposite resolution from PAK's `PROFESSIONAL_BOROUGH`).

---

## Five C's categorization

| Five C's | Count | Columns |
|---|---:|---|
| **Character** | 4 | `DEROG` (major derogatory reports), `DELINQ` (delinquent credit lines), `CLAGE` (age of oldest credit line), `NINQ` (recent credit inquiries) |
| **Capacity** | 3 | `JOB` (occupational category), `YOJ` (years at present job), `DEBTINC` (debt-to-income ratio) |
| **Capital** | 1 | `CLNO` (number of existing credit lines) |
| **Collateral** | 2 | `VALUE` (property value), `MORTDUE` (amount due on existing mortgage) |
| **Conditions** | 2 | `LOAN` (amount requested), `REASON` (loan purpose — debt consolidation vs. home improvement) |
| **Target** | 1 | `target` |

4+3+1+2+2+1 = 13, matches the file. **Structural note vs. PAK:** PAK had zero Collateral columns (unsecured
retail card). HMEQ has two genuine ones — `VALUE` and `MORTDUE` — because this is a home-equity-secured loan;
`VALUE` minus `MORTDUE` is effectively the borrower's available equity cushion backing this specific loan.

Missingness is also structurally different from PAK's "useful" columns — real but moderate across several HMEQ
fields: `DEBTINC` 21.3% missing (worst), `DEROG` 11.9%, `DELINQ` 9.7%, `NINQ` 8.6%, `CLAGE` 5.2%.

---

## Character columns — final verdict (resolved via Mann-Whitney, not just Cramér's V)

| Column | Cramér's V | min_expected | Mann-Whitney p-value | Reject H₀? | Verdict |
|---|---:|---:|---:|---|---|
| `DELINQ` | 0.358 | 0.20 (unreliable alone) | 4.37×10⁻¹³¹ | **Yes** | ✅ **Useful — strongest Character column, confirmed by both methods** |
| `DEROG` | 0.293 | 0.40 (unreliable alone) | 1.97×10⁻⁸⁷ | **Yes** | ✅ **Useful — confirmed** |
| `CLAGE` | 0.187 | 87.98 (reliable on its own) | 1.45×10⁻⁴⁴ | **Yes** | ✅ **Useful — confirmed, no caveat needed even on Cramér's V alone** |
| `NINQ` | 0.192 | 0.20 (unreliable alone) | 4.54×10⁻²⁹ | **Yes** | ✅ **Useful — confirmed** |

**All four Character columns are genuinely useful**, and unlike anything found so far in PAK, three of them
(`DELINQ`, `DEROG`, `NINQ`) initially had a sparse-cell reliability caveat on their Cramér's V — but **Mann-Whitney
confirmed real, highly significant signal for all three independently**, so the caveat is resolved, not a
rejection. This is the opposite outcome from PAK's `PROFESSIONAL_BOROUGH` case, where the second-method check
*disproved* the suspicious result rather than confirming it — a useful contrast showing the sparse-cell flag
doesn't automatically mean "fake," it means "needs a second opinion."

Directionally sensible across the board: defaulters have more derogatory marks, more delinquent lines, more
recent credit inquiries, and a shorter credit history (`CLAGE` median 132.87 months vs. 180.42 for non-defaulters)
— exactly what domain expectations would predict, and markedly stronger than any PAK demographic column (best
PAK result was `AGE` at Cramér's V 0.114; HMEQ's weakest Character column, `CLAGE` at 0.187, already beats it).

**Running keep list so far: `DELINQ`, `DEROG`, `CLAGE`, `NINQ` (all 4 Character columns).**

### Model evidence — cumulative model tracking

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| `DELINQ` + `DEROG` + `CLAGE` + `NINQ` (all 4 Character) | 0.7734 | **0.8032 ± 0.0064** | `lab_20261007_123736_hmeq_character_only_xgboost` |

Feature importance: `DELINQ` 49.2%, `DEROG` 23.9%, `CLAGE` 15.9%, `NINQ` 11.0% — matches the Cramér's
V/Mann-Whitney ranking exactly.

**Striking result vs. PAK:** with only 4 of 12 columns, this already reaches 0.77–0.80 AUC — beating PAK's best
4-column model (0.5955/0.5904) *and* PAK's full 51-column model (0.6466). Confirms the filter-stage read: HMEQ's
Character columns (past delinquency behavior) carry genuinely strong signal, where PAK's best columns were only
weakly predictive. One caveat for the record: CV AUC (0.8032) is noticeably higher than holdout (0.7734) here —
the opposite direction from typical overfitting, likely just this particular holdout split being harder than
average. Treat 0.77–0.80 as the honest range, not a single anchor number.

---

## Capacity columns — final verdict

| Column | Cramér's V | IV | min_expected | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---|
| `DEBTINC` | **0.437** | **1.267** | 111.32 (reliable) | 1.11×10⁻²³ | ✅ **Useful — by far the strongest column found in this project so far** |
| `JOB` | 0.135 | 0.124 | 21.75 (reliable) | n/a (categorical) | ✅ **Useful** |
| `YOJ` | 0.101 | 0.068 | 52.47 (reliable) | 2.83×10⁻⁵ | ✅ **Useful (modest)**, Pearson r=-0.060 |

No sparse-cell caveats on any of these three — all reliable on Cramér's V alone, no Mann-Whitney rescue needed
(ran it anyway for the two numeric columns as a cross-check; both confirm).

**`DEBTINC` (debt-to-income ratio) is the single strongest predictor found across both datasets in this entire
project** — IV of 1.267 is enormously above the 0.3 "strong" threshold, Cramér's V of 0.437 crosses into
moderate-to-strong. **Sharp, genuinely informative contrast with PAK:** PAK's `PERSONAL_MONTHLY_INCOME` (raw
income) was nearly useless (Cramér's V 0.026). The lesson: raw income alone barely matters, but income *relative
to debt obligations* — an actual repayment-strain measure — matters enormously. Worth remembering for any future
dataset: prefer ratio/relative capacity measures over raw income level when both are available.

`JOB` shows a real occupational risk spread: `Sales` (34.9% default) and `Self` (self-employed, 30.1%) notably
riskier than `Office` (13.2%, safest). `YOJ` (tenure) is modest but genuine — more years at the job, lower
default risk.

**Running keep list: all 7 columns tested so far — `DELINQ`, `DEROG`, `CLAGE`, `NINQ` (Character) + `DEBTINC`,
`JOB`, `YOJ` (Capacity).**

---

## Collateral columns — final verdict

| Column | Cramér's V | IV | min_expected | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---|
| `VALUE` | **0.168** | 0.165 | 107.73 (reliable) | 4.45×10⁻⁹ | ✅ **Useful** |
| `MORTDUE` | 0.093 | 0.053 | 67.23 (reliable) | 1.61×10⁻⁸ | ❌ Just below the 0.1 threshold — negligible |
| *(derived, not a real column)* `EQUITY = VALUE − MORTDUE` | 0.110 | 0.079 | 58.65 (reliable) | 1.92×10⁻⁶ | Borderline — tested out of curiosity, didn't outperform `VALUE` alone |

No sparse-cell issues — all three fully reliable, Mann-Whitney confirms significance across the board.

**Counter-intuitive finding:** expected the derived equity measure (property value minus amount still owed) to
be the strongest Collateral signal, since that's literally the cushion backing this specific loan. It wasn't —
`VALUE` alone (0.168) beats the derived equity variable (0.110). Property value carries more signal on its own
than the equity calculation does.

**Data point flagged, not yet explored further:** the derived equity variable has a minimum of **-205,445** —
some borrowers owe more on their existing mortgage than their home is currently worth (underwater). A real,
extreme tail worth a closer look later, though it didn't move the overall correlation much.

**Keep list from Collateral: `VALUE` only.**

**Running keep list: 8 of 12 columns — `DELINQ`, `DEROG`, `CLAGE`, `NINQ` (Character), `DEBTINC`, `JOB`, `YOJ`
(Capacity), `VALUE` (Collateral).**

---

## Capital columns — final verdict

| Column | Cramér's V | IV | min_expected | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---|
| `CLNO` | 0.0997 | 0.0585 | 86.78 (reliable) | 0.258 (not significant — see below) | ✅ **Useful (borderline), real U-shaped relationship** |

**Methodology lesson — Mann-Whitney has its own blind spot, confirmed here:** chi-square said significant
(p=1.89×10⁻⁹, reliable `min_expected`), but Mann-Whitney said not significant (p=0.258) — the opposite
disagreement direction from the Character columns, where chi-square was the unreliable one. Checked the actual
binned default rates to resolve it:

| `CLNO` (existing credit lines) | Default rate |
|---|---:|
| 0–10 (fewest) | **28.80%** (highest) |
| 10–25 (middle) | 15.9–18.8% (safest zone) |
| 34–71 (most) | **24.56%** (second-highest) |

**Genuine U-shaped relationship** — both too few and too many existing credit lines carry more risk than a
moderate amount (plausible: too few = thin/inexperienced credit file, too many = overextension). This explains
the test disagreement: Mann-Whitney specifically tests for a *consistent directional shift*, which a U-shape
cancels out in rank terms, making Mann-Whitney blind to this exact pattern type. Chi-square doesn't assume
direction, so it correctly caught it. **Conclusion: Mann-Whitney is not a universal upgrade over chi-square — it
resolves the sparse-cell problem but has its own blind spot for non-monotonic relationships. Use both; they're
complementary, not a strict hierarchy. When they disagree, check the actual binned rates before trusting either.**

**Running keep list: 9 of 12 columns — `DELINQ`, `DEROG`, `CLAGE`, `NINQ` (Character), `DEBTINC`, `JOB`, `YOJ`
(Capacity), `VALUE` (Collateral), `CLNO` (Capital).**

---

## Conditions columns — final verdict

| Column | Cramér's V | IV | min_expected | Mann-Whitney p | Verdict |
|---|---:|---:|---:|---:|---|
| `LOAN` | **0.170** | 0.160 | 114.91 (reliable) | 5.87×10⁻¹⁷ | ✅ **Useful** |
| `REASON` | 0.038 | 0.009 | 50.27 (reliable) | n/a (categorical) | ❌ Negligible (barely significant, p=0.015, but tiny effect) |

`REASON`: `HomeImp` (22.2% default) vs. `DebtCon` (19.0%) — real but too small to matter.

`LOAN`: not a clean monotonic trend — dominated by one sharp effect at the bottom of the range:

| Loan amount | Default rate |
|---|---:|
| $1,100–$7,600 (smallest) | **37.98%** (far highest) |
| $7,600–$16,300 | 17.5–22.7% |
| $16,300–$30,500 | 12.5–17.5% (safest zone) |
| $30,500–$89,900 (largest) | 19.66% |

The smallest loan requests are dramatically riskier than everything else — this single effect drives most of the
signal, not a smooth "bigger loans are safer" relationship (the largest bin isn't even the safest). Plausible
explanation (not confirmed): very small home-equity requests may come from applicants in financial distress
taking whatever they can get, rather than a calculated home-improvement decision.

**Keep list from Conditions: `LOAN` only.**

---

## FINAL — all five C's categories complete (2026-10-07)

**10 of 12 columns confirmed useful: `DELINQ`, `DEROG`, `CLAGE`, `NINQ` (Character), `DEBTINC`, `JOB`, `YOJ`
(Capacity), `VALUE` (Collateral), `CLNO` (Capital), `LOAN` (Conditions).**
**Rejected: `MORTDUE` (Collateral, just below threshold), `REASON` (Conditions, negligible effect size).**

This is a dramatically different outcome from PAK, where only 4 of 51 columns passed (and most of the dataset
was dead weight). HMEQ's columns are almost all genuinely predictive — consistent with it being a purpose-built,
curated textbook dataset (Baesens/Roesch/Scheule) rather than raw operational data with lots of noise like PAK.

### Combined model — all 10 confirmed-useful columns

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| All 10 Character+Capacity+Collateral+Capital+Conditions columns | **0.9449** | **0.9477 ± 0.0044** | `lab_20261007_153037_hmeq_all_confirmed_useful_xgboost` |

**Holdout and CV agree closely (0.003 apart)** — fully stable, not a lucky split, unlike the Character-only run
(which had holdout/CV disagreeing by 0.03).

Feature importance, all 10 columns:

| Feature | Importance |
|---|---:|
| `DEBTINC` | 34.04% |
| `DELINQ` | 14.00% |
| `DEROG` | 10.95% |
| `JOB` | 6.60% |
| `CLAGE` | 6.36% |
| `VALUE` | 6.24% |
| `CLNO` | 5.78% |
| `NINQ` | 5.64% |
| `LOAN` | 5.53% |
| `YOJ` | 4.85% |

`DEBTINC` dominates at 34% — more than double the next column — confirming the Capacity-stage finding. Every one
of the 10 kept columns contributes meaningfully (none below 4.85%), unlike PAK where the 4th column
(`OCCUPATION_TYPE`) barely moved the model at all.

### Cross-dataset comparison — methodology validated on two very different dataset shapes

| Dataset | Columns kept | Combined holdout AUC | Combined CV AUC |
|---|---:|---:|---:|
| PAK | 4 of 51 | 0.5955 | 0.5904 |
| **HMEQ** | **10 of 12** | **0.9449** | **0.9477** |

The filter-then-validate methodology (Cramér's V/IV → Mann-Whitney for sparse cells → combined model check)
correctly identified PAK as a mostly-noise dataset with a handful of weak signals, and correctly identified HMEQ
as an almost entirely strong-signal dataset — two opposite outcomes from the same process, both confirmed by the
final model numbers. This is the strongest evidence yet that the methodology itself generalizes, rather than
being tuned to produce a particular kind of answer.

---

## v2 REDO (2026-10-08) — full re-screening under the pooled Shapley/BH methodology

Per `METHODOLOGY.md` Step 5 v2. Re-verified all 12 raw columns' Step 1-4 results fresh (not reused from
memory) — all matched the v1 numbers above exactly, confirming the univariate screening work was sound.
Pooling criterion made explicit and applied consistently (also used in the PAK v2 redo): **a reliable column
pools as a candidate if IV ≥ 0.02 OR Cramér's V ≥ 0.1** (either threshold clearing is sufficient — not
requiring both).

**One reversal from v1 at the Step 1 pooling stage:** `MORTDUE` (IV=0.0532, Cramér's V=0.0933) clears the IV
threshold even though it falls just short of the Cramér's V one — v1 rejected it outright on Cramér's V alone
("just below 0.1 threshold"). Under the explicit OR-rule, it pools as a candidate rather than being dismissed.
`REASON` (IV=0.0086, Cramér's V=0.0375) fails both thresholds — rejected, consistent with v1.

**Final pool: 11 of 12 columns** — `LOAN`, `VALUE`, `JOB`, `YOJ`, `DEROG`, `DELINQ`, `CLAGE`, `NINQ`, `CLNO`,
`DEBTINC`, `MORTDUE`. Reconfirmed Mann-Whitney for the three gate-failed columns (`DEROG` p=1.97e-87,
`DELINQ` p=4.37e-131, `NINQ` p=4.54e-29) — all still real.

### Pooled Shapley / Benjamini-Hochberg results

2¹¹ − 1 = 2,047 subsets × 5 folds = 10,235 XGBoost fits, same fixed `StratifiedKFold(random_state=42)`
throughout. Efficiency check: sum of Shapley values reconstructs `v(full) − v(empty)` to within 4.4×10⁻¹⁶
(floating-point level) — computation confirmed correct.

| Column | Mean Shapley (ΔAUC) | Std | t-stat | raw p | BH-adjusted p | Keep? |
|---|---:|---:|---:|---:|---:|---:|
| DEBTINC | 0.12156 | 0.01134 | 23.97 | 1.80e-05 | 6.82e-05 | **YES** |
| DELINQ | 0.05709 | 0.01110 | 11.50 | 3.27e-04 | 5.80e-04 | **YES** |
| VALUE | 0.03946 | 0.00371 | 23.77 | 1.86e-05 | 6.82e-05 | **YES** |
| CLAGE | 0.03708 | 0.00240 | 34.57 | 4.18e-06 | 4.60e-05 | **YES** |
| DEROG | 0.03514 | 0.00676 | 11.63 | 3.13e-04 | 5.80e-04 | **YES** |
| LOAN | 0.03451 | 0.00839 | 9.20 | 7.76e-04 | 9.48e-04 | **YES** |
| JOB | 0.02744 | 0.00918 | 6.68 | 2.61e-03 | 2.61e-03 | **YES** |
| CLNO | 0.02707 | 0.00543 | 11.14 | 3.69e-04 | 5.80e-04 | **YES** |
| YOJ | 0.02700 | 0.00577 | 10.46 | 4.72e-04 | 6.49e-04 | **YES** |
| NINQ | 0.02482 | 0.00674 | 8.24 | 1.19e-03 | 1.30e-03 | **YES** |
| MORTDUE | 0.01814 | 0.00353 | 11.49 | 3.28e-04 | 5.80e-04 | **YES** |

**All 11 pooled candidates confirmed real and additive — including `MORTDUE`, reversing v1's rejection.**
No order-dependency ambiguity surfaced here the way it did for PAK's `OCCUPATION_TYPE` or German Credit's
`personal_status_sex`/`other_debtors` — every column that passed Step 1-4 also held up in the full pooled
test. Full subset-level data: `hmeq_v2_shapley_results.json`; full analysis: `hmeq_v2_shapley_analysis.json`.

### Final model

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| All 11 confirmed columns (`REASON` excluded) | 0.9438 | **0.9498 ± 0.0053** | `lab_20261008_200018_hmeq_v2_final_eleven_xgboost` |
| v1 (10 columns, no `MORTDUE`) — for comparison | 0.9449 | 0.9477 ± 0.0044 | superseded, run deleted from Sandbox |

Adding `MORTDUE` moved CV AUC up modestly (0.9477 → 0.9498, +0.0021) with holdout essentially flat (within
noise) — a small but real improvement, consistent with its confirmed-positive Shapley contribution. Top
feature importances: `DEBTINC` 29.8%, `DELINQ` 15.0%, `CLAGE` 8.35%, `DEROG` 8.25%, `JOB` 7.61%, `VALUE`
6.80%, `CLNO` 5.22%, `MORTDUE` 5.04%.

### v1 vs. v2 comparison

| | v1 (superseded) | v2 (current) |
|---|---|---|
| Columns kept | 10 of 12 (no `MORTDUE`) | **11 of 12** (adds `MORTDUE`) |
| 5-fold CV AUC | 0.9477 ± 0.0044 | **0.9498 ± 0.0053** |

Unlike PAK (where v2 both removed a column and added a new one) and German Credit (where v2 removed several
v1-confirmed columns), HMEQ's redo shows the **mildest** correction of the three datasets — v1's category-by-
category screening happened to get 10 of 11 final columns right on its own merits here, and the single miss
(`MORTDUE`) was a genuinely close call (Cramér's V 0.0933 vs. the 0.1 threshold) rather than an
order-dependency artifact. This is itself useful evidence: the v1→v2 revision matters more for some datasets
than others, and HMEQ's relatively clean, low-redundancy column set is the likely reason it was more robust
to v1's shortcuts than PAK or German Credit were.

### Probability calibration (2026-10-09)

Raw model's Brier score (0.0779) was already better than the trivial base-rate baseline (0.1598) — HMEQ had
the best raw calibration of the four datasets, consistent with it also having the strongest AUC. Isotonic
calibration applied anyway for consistency (see `CALIBRATION_NOTES.md`):

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier score | 0.1598 | 0.0779 | **0.0681** |
| ECE | — | 0.0819 | **0.0123** |
| AUC | — | 0.9438 | 0.9472 |

ECE still improved 85% (0.0819→0.0123) even starting from the best base case of the four — calibration
helps regardless of how good the raw model already looks on Brier score alone. AUC essentially unchanged
(+0.0034, within fold noise).
