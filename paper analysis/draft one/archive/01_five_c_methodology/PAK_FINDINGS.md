# PAK.csv (PAKDD 2009) — Exploratory Findings Log

> **SUPERSEDED by the v2 redo below (2026-10-08).** Everything from here down to "## v2 REDO" is the
> original v1 analysis (greedy, category-locked combination testing) — kept for historical record, but its
> final keep-list and combined-model numbers are **not** the current answer. Jump to the v2 section at the
> bottom for the current, methodology-approved result.

Private reference for the ad hoc column-by-column investigation worked through in conversation starting
2026-10-06. **Not shown anywhere in the Sandbox frontend** — unlike `DATASET_CATALOG.md`, this file is purely
for Claude + the user to refer back to in later sessions. Lives in `paper analysis/draft one/` (untracked, same
as `RESULTS_LOG.md`) rather than `data/ml_lab/datasets/`, specifically so it does NOT get picked up by the
per-dataset "Dataset Info" catalog panel in the admin UI.

All numbers below were computed directly against `data/ml_lab/datasets/PAK.csv` (50,000 rows, 52 columns) on
2026-10-06 — nothing here is estimated or inferred from memory.

---

## Methodology

Full shared methodology (the four-tool escalation ladder — IV/Cramér's V → reliability gate → Mann-Whitney →
model validation, and why this is not a four-way vote) now lives in `METHODOLOGY.md` in this same folder,
written up formally on 2026-10-07 after being developed ad hoc across this PAK analysis and the follow-up HMEQ
one. This section keeps only what's specific to reading the tables below.

For each column tested against `target` (positive class = `1` = default, overall rate 26.08%): IV and Cramér's V
are reported together (interpretation scale: <0.02/0.1 negligible, 0.02–0.1/0.1–0.3 weak, >0.1/0.3 moderate+ —
IV/Cramér's V scales respectively), chi-square p-value is reported but not treated as sufficient on its own, and
Pearson correlation is added for genuinely continuous columns (`AGE`, `PERSONAL_MONTHLY_INCOME`). The Mann-Whitney
U test and the sparse-cell reliability gate were developed *after* this PAK analysis (during the HMEQ follow-up)
— see `METHODOLOGY.md` for why, and note that means some PAK results below (`PROFESSIONAL_BOROUGH` etc.) were
resolved via direct model validation instead, which is still consistent with the final methodology's Step 5.

---

## Character / demographic columns — final verdict

| Rank | Column | Cramér's V | IV | Chi-sq p-value | Statistically significant? | Verdict |
|---|---|---:|---:|---:|---|---|
| 1 | `AGE` | **0.114** | 0.0699 | 3.8×10⁻¹³⁸ | Yes | **Useful — keep** |
| 2 | `MARITAL_STATUS` | 0.073 | 0.0265 | 1.8×10⁻⁵³ | Yes | Real but modest — keep, lower priority |
| 3 | `STATE_OF_BIRTH` | 0.050 | 0.0136 | 2.4×10⁻¹⁴ | Yes, but min expected cell count 0.26 (test assumptions strained by small states) | Weak — use with caution, don't over-trust the p-value |
| 4 | `EDUCATION_LEVEL_2` | 0.040 | 0.0 (binning artifact — see methodology) | — | n/a (IV misleading) | Not useful — negligible effect, 65% missing, undocumented codes |
| 5 | `SEX` | 0.024 | 0.0029 | 2.5×10⁻⁶ | Yes | Not useful — negligible |
| 6 | `QUANT_DEPENDANTS` | 0.020 | 0.0012 | 0.195 | **No** | Not useful — no real signal |
| 7 | `NACIONALITY` | 0.001 | 0.0000 | 0.966 | **No** | Not useful — near-constant (95.8% one value), no signal |
| — | `EDUCATION_LEVEL` | n/a | n/a | n/a | n/a | Excluded — constant (1 value across all 50,000 rows) |

**Bottom line on demographics:** only `AGE` clears a genuinely useful bar. `MARITAL_STATUS` is a distant second
with real-but-modest value. Everything else ranges from weak-with-caveats to statistically indistinguishable
from noise. Pure demographics are a weak predictor group in this dataset overall — expected for credit risk in
general, but worth having confirmed with actual numbers rather than assumed.

### Model evidence supporting this ranking
XGBoost run on `AGE` + `MARITAL_STATUS` only (the two "useful" columns), native categorical handling, no tuning:
- **Holdout AUC-ROC: 0.586**, 5-fold CV: 0.5823 ± 0.0059 — stable, not a lucky split.
- Feature importance split almost evenly: `AGE` 50.97%, `MARITAL_STATUS` 49.03%.
- Run ID: `lab_20261006_052418_pak_age_marital_only_xgboost`.
- Compare to full-feature-set XGBoost baseline on the same dataset: **0.6466 AUC** (run ID
  `lab_20261003_110840_pak_xgboost`, from the earlier 5-model PAK batch). The ~0.06 AUC gap confirms demographics
  alone leave real predictive power on the table — consistent with the weak Cramér's V numbers above.

---

## Capacity columns — final verdict

| Column | Cramér's V | Missing | Verdict |
|---|---:|---:|---|
| `PROFESSIONAL_BOROUGH` | 0.342 (raw stat) | 69.4% | ❌ **Not useful — statistical artifact, see model check below** |
| `PROFESSIONAL_CITY` | 0.234 (raw stat) | 68.2% | ⚠️ Same sparse-category issue as above, downgraded by association — not individually model-tested |
| `PROFESSIONAL_ZIP_3` | 0.147 (raw stat) | 67.2% | ⚠️ Same issue, less severe — not individually model-tested |
| `OCCUPATION_TYPE` | 0.056 | 14.6% | ✅ **Useful (modest) — keep** |
| `PROFESSIONAL_STATE` | 0.044 | 68.6% | Weak, high missingness |
| `PERSONAL_MONTHLY_INCOME` | 0.026 | 0.0% | Not useful — surprisingly weak despite being fully populated |
| `PROFESSION_CODE` | 0.025 | 15.5% | Negligible |
| `PROFESSIONAL_PHONE_AREA_CODE` | 0.021 | 73.1% | Negligible |
| `FLAG_PROFESSIONAL_PHONE` | 0.016 | 0.0% | Negligible |
| `EDUCATION_LEVEL_2` | 0.040 | 64.7% | Not useful (tested earlier in demographic comparison) |
| `COMPANY` | 0.008 | 0.0% | Not significant (p=0.066) |
| `MATE_PROFESSION_CODE` | 0.008 | 57.8% | Not significant (p=0.077) |
| `OTHER_INCOMES` | ~0 (Pearson 0.0044) | 0.0% | No signal — 94.5% of rows are exactly zero |
| `MONTHS_IN_THE_JOB` | ~0 (Pearson -0.0071) | 0.0% | No signal — 99.8% of rows are exactly zero, likely a data quality issue, not real tenure data |
| `FLAG_INCOME_PROOF` | n/a | 0.0% | Excluded — constant |

**Note on `PERSONAL_MONTHLY_INCOME`:** the most-expected-to-matter column tested so far (direct income measure,
the intuitive core of "ability to repay"), and it turned out weaker than most demographics — weaker than
`MARITAL_STATUS`, barely above `SEX`. Distribution is heavily right-skewed (median 500, mean 886.7, max 959,000;
47 rows above 50,000). Binned default rate is flat across the bulk of the population (300–800 range = 69% of
rows, default rate 26.08–26.43%, essentially identical to the 26.08% overall rate) — the only real,
directionally-sensible drop shows up in the thin 3,000+ tail (19.17% default, but only 1.5% of rows). Cause not
established; flagged as an open question, not a settled explanation.

**Important methodological finding — sparse-category Cramér's V inflation (verified via model check):**
`PROFESSIONAL_BOROUGH` showed the single highest Cramér's V of anything tested in this dataset (0.342) — on
paper, a "moderate" effect size that should rival or beat `AGE`. This was suspicious on its face: 69.4% missing,
and 5,056 categories spread across only ~15,287 populated rows (≈3 rows/category on average), with a chi-square
`min_expected` cell count of 0.26 — far below the reliability threshold of 5. **Ran an XGBoost model on
`PROFESSIONAL_BOROUGH` alone (capped to its top 51 categories, same treatment every high-cardinality column in
this project gets) to settle it: holdout AUC 0.5318, 5-fold CV AUC 0.5247 ± 0.0053** — barely above a coin flip,
and holdout/CV agree closely, so it's not even an overfitting story; the model genuinely cannot extract useful
signal from this column. Run ID: `lab_20261006_221739_pak_professional_borough_only_xgboost`.
**Conclusion: Cramér's V is unreliable for any high-cardinality, heavily-missing categorical column — it must be
validated with an actual holdout-vs-CV model check before being trusted.** `PROFESSIONAL_CITY` and
`PROFESSIONAL_ZIP_3` share the same sparse-category structure and are downgraded by association, though neither
was individually model-tested — worth doing before fully resolving this group. The same caution should apply to
any other high-cardinality demographic/location column in this dataset not yet model-checked (e.g.
`CITY_OF_BIRTH`, `RESIDENCIAL_BOROUGH`, `RESIDENCIAL_CITY`), since the one place `CITY_OF_BIRTH` has been seen
so far (as the #2 feature in the 7-demographic-column run) came with the same holdout/CV disagreement warning
sign.

**Bottom line on Capacity:** only `OCCUPATION_TYPE` is genuinely useful, and it's weaker than either useful
demographic column. Everything else is negligible, not significant, or a measurement artifact.

---

## Confirmed useful columns so far — cumulative model tracking

As each category is finished, columns confirmed "useful" are added here and re-tested together, to track
whether combining them actually improves the model (not guaranteed — see the discussion below).

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| `AGE` + `MARITAL_STATUS` | 0.5860 | 0.5823 ± 0.0059 | `lab_20261006_052418_pak_age_marital_only_xgboost` |
| + `OCCUPATION_TYPE` | 0.5892 | 0.5817 ± 0.0050 | `lab_20261006_222155_pak_age_marital_occupation_xgboost` |
| + `PAYMENT_DAY` (final, all 5 C's categories tested) | **0.5955** | **0.5904 ± 0.0057** | `lab_20261006_222728_pak_age_marital_occupation_paymentday_xgboost` |

**Adding `OCCUPATION_TYPE` made no real difference** — holdout ticked up by 0.003 (noise-level), and the more
reliable 5-fold CV estimate was flat-to-slightly-down. Consistent with the Cramér's V ranking: `OCCUPATION_TYPE`
(0.056) is real but meaningfully weaker than `AGE` (0.114) or `MARITAL_STATUS` (0.073), and a weak-but-real
individual effect doesn't automatically produce a visible AUC gain once stronger variables are already in the
model.

**Adding `PAYMENT_DAY` was a real, consistent improvement** — unlike the `OCCUPATION_TYPE` step, both holdout
*and* 5-fold CV moved up together (+0.0063 holdout, +0.0087 CV from the 3-variable run), which is a much more
convincing signal than a holdout-only bump. `PAYMENT_DAY` was also the single most important feature in this run
(30.87%), ahead of `AGE` (29.55%), `MARITAL_STATUS` (21.80%), and `OCCUPATION_TYPE` (17.78%) — consistent with
its Cramér's V (0.0808) being the second-strongest of everything tested across all four categories, behind only
`AGE` itself.

**Final keep list across all five C's categories (Character, Capacity, Capital, Conditions; Collateral n/a):
`AGE`, `MARITAL_STATUS`, `OCCUPATION_TYPE`, `PAYMENT_DAY`.** 4 out of 51 feature columns tested as genuinely
useful. Combined AUC (0.5955 holdout / 0.5904 CV) is still meaningfully below the full 51-column baseline
(0.6466 AUC, run `lab_20261003_110840_pak_xgboost`) — a ~0.05 AUC gap remains even with the four best
individually-validated columns, meaning either (a) real incremental signal exists elsewhere that univariate
testing doesn't catch (interaction effects), or (b) part of the full-model's advantage comes from the kind of
high-cardinality overfitting flagged with `CITY_OF_BIRTH` and `PROFESSIONAL_BOROUGH` — not yet disentangled.

---

## Capital columns — final verdict

| Column | Cramér's V / Pearson r | Chi-sq p-value | Verdict |
|---|---:|---:|---|
| `FLAG_MASTERCARD` | 0.0176 | 0.000084 (significant) | Negligible |
| `QUANT_BANKING_ACCOUNTS` | 0.0164 | 0.0012 | Negligible — the one high-rate group (2 accounts, 57% default) has only 14 rows |
| `QUANT_SPECIAL_BANKING_ACCOUNTS` | 0.0164 | 0.0012 | Identical numbers to `QUANT_BANKING_ACCOUNTS` — worth checking later whether these are duplicate columns |
| `QUANT_CARS` | 0.0117 | 0.0091 | Negligible |
| `FLAG_VISA` | 0.0053 | 0.234 (not significant) | No signal |
| `PERSONAL_ASSETS_VALUE` | r=-0.0039 (raw), -0.0102 (log) | n/a | No signal — 95.2% of rows have exactly zero assets recorded |
| `FLAG_DINERS` | 0.0016 | 0.718 (not significant) | No signal |
| `FLAG_OTHER_CARDS` | 0.0009 | 0.840 (not significant) | No signal |
| `FLAG_AMERICAN_EXPRESS` | 0.0000 | 1.000 (not significant) | No signal at all |
| `FLAG_ACSP_RECORD` | n/a | n/a | Excluded — constant |

Unlike Capacity, there was no binning-artifact confusion here — correctly used raw 0/1/2/3 values directly for
every low-cardinality column instead of forcing a 10-quantile cut (which is what broke several Capacity columns
initially). `PERSONAL_ASSETS_VALUE` (95.2% exactly zero, same zero-inflation pattern as `OTHER_INCOMES` and
`MONTHS_IN_THE_JOB` in Capacity) was checked via direct Pearson correlation instead of the broken binned
chi-square, consistent with how those were handled.

**Bottom line on Capital: every single column is negligible or not statistically significant.** None of the
existing-credit-card ownership flags, asset values, or banking-account counts carry a meaningful relationship
with default in this dataset. **Zero columns from Capital added to the keep list.**

## Conditions columns — final verdict

| Column | Cramér's V | Missing | Verdict |
|---|---:|---:|---|
| `PAYMENT_DAY` | **0.0808** | 0.0% | ✅ **Useful — keep** |
| `APPLICATION_SUBMISSION_TYPE` | 0.0219 | 38.9% | Negligible |
| `PRODUCT` | 0.0204 | 0.0% | Negligible — one small subgroup (code 7, 1,295 rows) shows 31.6% default vs ~25.9% elsewhere, not acted on alone |
| `QUANT_ADDITIONAL_CARDS` | n/a | 0.0% | Excluded — constant |

**`PAYMENT_DAY` is a genuine, trustworthy finding** — only 6 clean categories, fully populated, chi-square
`min_expected` = 459.30 (nowhere near the sparse-category danger zone that discredited `PROFESSIONAL_BOROUGH`).
Clean, interpretable monotonic-ish pattern: default rate climbs from 23.17% (day 10, the modal/lowest group,
20,422 rows) up to 33.08% (day 25, 7,026 rows) as the chosen payment day moves later in the month — a genuine
10-point spread. Comparable in strength to `MARITAL_STATUS` (0.073). **Added to the keep list.**

**Bottom line on Conditions: `PAYMENT_DAY` is useful, the other three are not.**

## Collateral
None exist in this dataset — unsecured private-label retail credit card data, confirmed from the PAKDD 2009
competition description.

---

## Background research notes (2026-10-06)

- Competition: PAKDD 2009 Data Mining Competition, co-organized by NeuroTech Ltd. and the Center for
  Informatics, Federal University of Pernambuco (UFPE). Originally hosted at
  `sede.neurotech.com.br/PAKDD2009` — now dead/archived.
- Data source: private-label credit card operation of a major Brazilian retail chain. 50,000 instances, 140+
  participating teams.
- One documented result (not confirmed as the winner): Linhart, Harari, Abramovich & Buchris (Tel Aviv
  University) placed 3rd with AUC 0.655, published in *"PAKDD Data Mining Competition 2009: New Ways of Using
  Known Methods."* The actual 1st-place score was not found in any available source — do not treat 0.655 as a
  benchmark ceiling.
- **Unresolved column-count discrepancy**: secondary sources disagree on the original raw column count (one
  says 28 explanatory attributes, another analysis used 20 predictors after removing constants from a reduced
  subset, one mentions an `Id_client` field that doesn't exist in our copy at all). Our file has 51 feature
  columns + target, confirmed directly. No single canonical "official" version of this file appears to still be
  circulating; treat column-count claims from any other source about this dataset with caution.

---

## Status: all five C's categories complete (2026-10-06)

- Character (demographics): **done** — `AGE`, `MARITAL_STATUS` confirmed useful; `STATE_OF_BIRTH` borderline/caution.
- Capacity: **done** — `OCCUPATION_TYPE` confirmed useful (modest). `PROFESSIONAL_CITY`/`PROFESSIONAL_ZIP_3` were
  never individually model-tested (downgraded by association with `PROFESSIONAL_BOROUGH`'s confirmed artifact) —
  still an open item if more confidence is wanted there.
- Capital: **done** — nothing useful, every column negligible or not significant.
- Conditions: **done** — `PAYMENT_DAY` confirmed useful (second-strongest Cramér's V overall, 0.0808).
- Collateral: n/a — no such columns exist in this unsecured retail-card dataset.

**Final keep list (4 of 51 feature columns): `AGE`, `MARITAL_STATUS`, `OCCUPATION_TYPE`, `PAYMENT_DAY`.**
Combined model: 0.5955 holdout AUC / 0.5904 CV AUC — vs. 0.6466 AUC for the full 51-column baseline.

### Open items for a future session
1. The ~0.05 AUC gap between the 4-column "validated useful" model and the full 51-column model is not yet
   explained — worth testing whether it's real multivariate/interaction signal invisible to univariate tests, or
   partly inflated by the same high-cardinality overfitting risk flagged for `CITY_OF_BIRTH` in the full-feature
   run (never individually model-checked either).
2. `PROFESSIONAL_CITY` and `PROFESSIONAL_ZIP_3` were downgraded by association with `PROFESSIONAL_BOROUGH`, not
   individually model-tested — could still hold a small amount of real signal worth checking.
3. `QUANT_BANKING_ACCOUNTS` and `QUANT_SPECIAL_BANKING_ACCOUNTS` produced identical statistics in Capital — worth
   a quick check on whether they're literally duplicate columns.
4. Consider a 5-model comparison (not just XGBoost) on the 4-column keep list, the way the original Step A
   baseline did for the full feature set — all testing here used XGBoost only.

**All four open items above were resolved in the v2 redo below** (items 2-3 confirmed directly: `PROFESSIONAL_CITY`
model-checked and confirmed fake; `RESIDENCIAL_ZIP_3`/`PROFESSIONAL_ZIP_3` confirmed to be literal 100%-identical
duplicate columns, not just similar statistics).

---

## v2 REDO (2026-10-08) — full re-screening under the pooled Shapley/BH methodology

Per `METHODOLOGY.md` Step 5 v2. Re-screened **all 51 raw feature columns from scratch** (not just the ~35
covered in the v1 analysis above — 16 columns, including `CITY_OF_BIRTH`, `RESIDENCIAL_CITY`,
`RESIDENCIAL_BOROUGH`, `RESIDENCE_TYPE`, `MONTHS_IN_RESIDENCE`, `FLAG_EMAIL`, `FLAG_RG`/`FLAG_CPF` etc., were
never individually tested in v1). 8 columns excluded outright as constants (`QUANT_ADDITIONAL_CARDS`,
`EDUCATION_LEVEL`, `FLAG_MOBILE_PHONE`, `FLAG_HOME_ADDRESS_DOCUMENT`, `FLAG_RG`, `FLAG_CPF`,
`FLAG_INCOME_PROOF`, `FLAG_ACSP_RECORD`) — 43 columns tested.

**Binning convention:** numeric columns with >20 unique values AND representing a genuinely continuous/ordinal
quantity (income, months, age, assets) use 10-quantile binning, matching `compute_iv`'s internal method.
Numeric columns that are actually nominal codes despite their dtype (`RESIDENCIAL_PHONE_AREA_CODE`,
`PROFESSIONAL_PHONE_AREA_CODE`, `PROFESSION_CODE`, `MATE_PROFESSION_CODE`, `OCCUPATION_TYPE`,
`EDUCATION_LEVEL_2`, `MARITAL_STATUS`, `NACIONALITY`, `POSTAL_ADDRESS_TYPE`, `PRODUCT`, `RESIDENCE_TYPE`) use
raw-value crosstabs instead — qcut would impose a false ordering on an unordered code.

**Duplicate column found:** `RESIDENCIAL_ZIP_3` and `PROFESSIONAL_ZIP_3` are **literally identical** (100%
row-for-row match, confirmed directly) — not just similar statistics as suspected in v1. Only one tested going
forward.

### Step 1-2 results — all 43 non-constant columns

Full battery (rows/cols/dof/min_expected/chi²/p/IV/Cramér's V) computed for every column; raw results in
`pak_step1_2_results.json`-equivalent output. Headline finding: **7 columns showed enormous apparent IV/Cramér's
V** (`RESIDENCIAL_BOROUGH` IV=8.04!, `CITY_OF_BIRTH` IV=5.17, `PROFESSIONAL_BOROUGH` IV=2.89,
`RESIDENCIAL_CITY` IV=1.93, `PROFESSIONAL_CITY` IV=1.22, `RESIDENCIAL_ZIP_3`/`PROFESSIONAL_ZIP_3` IV=0.27) — all
sharing the exact same `min_expected=0.261`, the sparse-cell failure signature already confirmed fake for
`PROFESSIONAL_BOROUGH` in v1 (traced to each having at least one category with only 1 row: expected count for
that row's minority-class cell = 1 × 13,041/50,000 = 0.2608).

### Step 3a — model-check resolution of all 7 suspiciously-strong, gate-failed columns

| Column | Holdout AUC | 5-fold CV AUC | Verdict |
|---|---:|---:|---|
| `PROFESSIONAL_BOROUGH` | 0.5318 | 0.5247 ± 0.0053 | ❌ Fake (confirmed in v1) |
| `RESIDENCIAL_BOROUGH` | 0.5099 | 0.5129 ± 0.0032 | ❌ Fake |
| `CITY_OF_BIRTH` | 0.5216 | 0.5200 ± 0.0042 | ❌ Fake |
| `RESIDENCIAL_CITY` | 0.5300 | 0.5309 ± 0.0052 | ❌ Fake |
| `PROFESSIONAL_CITY` | 0.5212 | 0.5208 ± 0.0050 | ❌ Fake |
| `RESIDENCIAL_ZIP_3` | 0.5105 | 0.5134 ± 0.0076 | ❌ Fake |
| `PROFESSIONAL_ZIP_3` | — | — | Duplicate of `RESIDENCIAL_ZIP_3`, not separately tested |

**All 7 confirmed fake — barely above chance despite IV values up to 8.04.** This is the single strongest
demonstration in this project so far of why the Step 2 reliability gate exists: without it, these 7 columns
would have looked like the dataset's most powerful predictors by a wide margin.

**One ambiguous gate-failed case resolved differently:** `RESIDENCIAL_PHONE_AREA_CODE` (101 categories,
min_expected=0.261, but untrusted IV=0.0239/Cramér's V=0.1078 — marginally *above* the weak threshold, unlike
the clearly-weak-even-untrusted cases below) was model-checked rather than dismissed: **holdout 0.5612,
5-fold CV 0.5597 ± 0.0051 — confirmed real**, and in fact the single strongest individual column found in
this entire dataset. Never tested in the v1 analysis at all.

### Columns rejected without needing a model check

Everything else either (a) passed the reliability gate and showed IV<0.02 AND Cramér's V<0.1 (genuinely weak,
trustworthy number), or (b) failed the gate via the same single-rare-row mechanism above but was *already*
weak even on the inflated/untrusted number (e.g. `STATE_OF_BIRTH`: untrusted IV=0.0136, Cramér's V=0.0502 —
since this failure mode only inflates, a weak result even under inflation confirms the true value is weaker
still, no rescue needed). This includes `OCCUPATION_TYPE` (IV=0.0171, Cramér's V=0.0629 — both just under
threshold; notably, this reverses v1's verdict, which had called it "useful, keep" — consistent with v1's own
combination test already showing it added nothing, a second independent demonstration that v1 was too lenient).

### Final pooled candidate list (4 columns) and Shapley/BH results

| Column | Mean Shapley (ΔAUC) | t-stat | raw p | BH-adjusted p | Keep? |
|---|---:|---:|---:|---:|---:|
| `AGE` | 0.04521 | 16.92 | 7.15e-05 | 9.53e-05 | **YES** |
| `RESIDENCIAL_PHONE_AREA_CODE` | 0.03850 | 19.38 | 4.18e-05 | 9.27e-05 | **YES** |
| `PAYMENT_DAY` | 0.02050 | 12.68 | 2.23e-04 | 2.23e-04 | **YES** |
| `MARITAL_STATUS` | 0.01660 | 18.88 | 4.64e-05 | 9.27e-05 | **YES** |

Efficiency check: sum of Shapley values reconstructs `v(full)-v(empty)` to within 1.4×10⁻¹⁷ (floating-point
level) — computation confirmed correct. **All 4 pooled candidates confirmed real and additive — no column
pre-filtering ambiguity at this stage.** Full subset-level data: `pak_v2_shapley_analysis.json`.

### Final model

| Columns used | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| `AGE`, `MARITAL_STATUS`, `PAYMENT_DAY`, `RESIDENCIAL_PHONE_AREA_CODE` | **0.6238** | **0.6197 ± 0.0031** | `lab_20261008_194228_pak_v2_final_four_xgboost` |
| Fresh full-column baseline (42 non-constant cols, high-cardinality capped to top 51 categories) | 0.6489 | 0.6416 ± 0.0018 | `lab_20261008_194233_pak_v2_full_baseline_xgboost` |

Feature importance in the 4-column model: `RESIDENCIAL_PHONE_AREA_CODE` 32.7%, `AGE` 26.6%, `PAYMENT_DAY`
20.8%, `MARITAL_STATUS` 19.9% — and notably, `RESIDENCIAL_PHONE_AREA_CODE` is also the **single most important
feature in the full 42-column baseline model** (6.3%, ahead of `AGE` at 5.4%), despite never having been tested
in the original v1 analysis.

### v1 vs. v2 comparison

| | v1 (superseded) | v2 (current) |
|---|---|---|
| Columns kept | `AGE`, `MARITAL_STATUS`, `OCCUPATION_TYPE`, `PAYMENT_DAY` | `AGE`, `MARITAL_STATUS`, `PAYMENT_DAY`, `RESIDENCIAL_PHONE_AREA_CODE` |
| Holdout AUC | 0.5955 | **0.6238** |
| 5-fold CV AUC | 0.5904 ± 0.0057 | **0.6197 ± 0.0031** |
| Gap to full-model baseline | ~0.05 AUC | **~0.022 AUC** — roughly half the gap |

The v2 redo both swaps out a column that didn't deserve to be there (`OCCUPATION_TYPE`) and discovers a
genuinely strong column the original analysis simply never tested (`RESIDENCIAL_PHONE_AREA_CODE`) — a
materially better, more defensible result, not just a methodologically cleaner one.

### Probability calibration (2026-10-09)

Raw model's Brier score (0.2368) is *worse* than the trivial "always predict the base rate" baseline
(0.1928) — the worst raw calibration gap of the four datasets besides GMSC. Isotonic-regression calibration
applied (see `CALIBRATION_NOTES.md` for mechanism/literature):

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier score | 0.1928 | 0.2368 | **0.1855** |
| ECE | — | 0.2236 | **0.0064** |
| AUC | — | 0.6238 | 0.6259 |

ECE improved 97% (0.2236→0.0064), Brier moved from worse-than-baseline to better, AUC essentially unchanged
(+0.0021, within fold noise).
