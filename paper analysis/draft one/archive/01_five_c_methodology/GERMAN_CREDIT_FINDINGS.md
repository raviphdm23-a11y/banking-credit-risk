# German Credit — Five C's Findings (private reference, not shown on frontend)

Third dataset tested with the Five C's column-usefulness methodology, after PAK (noisy, unsecured, 51
columns, 4 kept) and HMEQ (clean, secured, 12 columns, 10 kept). Parallel structure to those two files —
purely a private reference for Claude + the user, never surfaced in the Sandbox frontend.

## Methodology

Full shared methodology lives in `METHODOLOGY.md` in this same folder — the four-tool escalation ladder
(IV/Cramér's V together → `min_expected` reliability gate → Mann-Whitney U only if that gate fails →
model validation, mandatory for any surprising single column and for every combination step). See that
file for the full reasoning; this file only records German-Credit-specific results.

## Dataset background

`data/ml_lab/datasets/german_credit_record.csv` — 1,000 rows, 21 columns (20 features + target), 0 missing
values anywhere, 0 duplicate rows. Target: binary, 700 good (0) / 300 bad (1) — matches the dataset's
well-known ~30% bad-credit base rate, so positive class = 1 = default/bad is already correctly oriented.
Cross-sectional (one row per loan application, no time dimension). Structurally different from both prior
datasets: small, and mostly categorical/ordinal (13 of 20 columns) rather than continuous.

## Five C's categorization

| Five C's | Count | Columns |
|---|---:|---|
| Character | 5 | credit_history, personal_status_sex, other_debtors, telephone, foreign_worker |
| Capacity | 5 | employment_since, job, installment_rate, people_liable, residence_since |
| Capital | 4 | credit_amount, savings_status, existing_credits, other_installment_plans |
| Collateral | 2 | property, housing |
| Conditions | 4 | checking_status, months_duration, purpose, age |

Borderline calls flagged at categorization time, not yet revisited: `checking_status` could arguably be
Capital rather than Conditions (describes current funding arrangement, not a durable asset); `age` is
borderline Character vs. Conditions (demographic, not a history signal); `residence_since` (years at
current residence) is stability-related, closer to Capacity than Character.

## Character — results

Target: `target` (positive class = `1` = bad/default, overall rate 30.0%).

**Reference ranges** (shown per the standing format — repeated every time, not just once):

| IV range | Strength |
|---|---|
| < 0.02 | Useless |
| 0.02–0.1 | Weak |
| 0.1–0.3 | Medium |
| > 0.3 | Strong |

| Cramér's V range | Strength |
|---|---|
| < 0.1 | Negligible |
| 0.1–0.3 | Weak |
| 0.3–0.5 | Moderate |
| > 0.5 | Strong |

| Column | Rows (categories) | Cols (target) | dof | min_expected | chi² statistic | p-value | IV | Cramér's V | Step 1/2 verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| credit_history | 5 | 2 | 4 | 12.00 | 61.691 | 1.28e-12 | 0.2932 | 0.2484 | Medium/weak-moderate — clearly useful |
| personal_status_sex | 4 | 2 | 3 | 15.00 | 9.605 | 0.0222 | 0.0447 | 0.0980 | Weak/negligible-weak — borderline |
| other_debtors | 3 | 2 | 2 | 12.30 | 6.645 | 0.0361 | 0.0320 | 0.0815 | Weak/negligible — borderline |
| foreign_worker | 2 | 2 | 1 | 11.10 | 5.822 | 0.0158 | 0.0439 | 0.0763 | Weak/negligible — borderline |
| telephone | 2 | 2 | 1 | 121.20 | 1.173 | 0.2789 | 0.0064 | 0.0342 | Useless/negligible — reject outright |

All five columns cleared the Step 2 reliability gate (min_expected ≥ 5 in every case) — no escalation to
Mann-Whitney was needed; all numbers above can be taken at face value.

**Step 5 — model validation on the three borderline columns:**

| Model | Holdout AUC | 5-fold CV AUC | Run ID |
|---|---:|---:|---|
| credit_history alone | 0.6467 | 0.6188 ± 0.0250 | lab_20261008_062558_german_character_credit_history_only_xgboost |
| + personal_status_sex, other_debtors, foreign_worker | 0.6560 | 0.6329 ± 0.0144 | lab_20261008_062607_german_character_all_four_xgboost |
| credit_history + personal_status_sex + other_debtors (foreign_worker dropped) | 0.6605 | 0.6310 ± 0.0115 | lab_20261008_063944_german_character_final_three_xgboost |

Feature importance in the 4-column combined model: credit_history 51.5%, personal_status_sex 28.9%,
other_debtors 19.6%, **foreign_worker 0.0%** — despite passing the univariate chi² test (p=0.0158),
`foreign_worker` was never actually used by the model once the other three columns were available. Same
pattern as PAK's `PROFESSIONAL_BOROUGH`: individually-significant-looking, but confirmed noise in
combination by Step 5. Dropping it (3-column model) held CV AUC steady (0.6310 vs 0.6329, within fold
noise) with a tighter fold spread (±0.0115 vs ±0.0144) and a slightly higher holdout (0.6605) — confirms
the column was adding nothing.

**Character final decision:**

| Column | Keep? | Reason |
|---|---|---|
| credit_history | ✅ Keep | Strong univariate + 48.1% importance in final 3-column model |
| personal_status_sex | ✅ Keep | Weak univariate alone, but real importance in combination (27.6%) |
| other_debtors | ✅ Keep | Weak univariate alone, but real importance in combination (24.4%) |
| foreign_worker | ❌ Reject | Passed univariate (p=0.016) but 0% model importance — noise, confirmed via Step 5 |
| telephone | ❌ Reject | Failed Step 1 outright (IV 0.006, p=0.28) |

Best Character-only model: 3 columns (credit_history, personal_status_sex, other_debtors), holdout AUC
0.6605, 5-fold CV AUC 0.6310 ± 0.0115.

> **Methodology note (added after Capital, see below):** the Character and Capacity category-level
> combination models above/below were run under Step 5 **v1** (greedy, category-locked combination testing),
> before the v1→v2 revision in `METHODOLOGY.md` on 2026-10-08. Under v2, no category's keep/reject decision
> is final from a combination model alone — these Step 1-4 survivors (credit_history, personal_status_sex,
> other_debtors from Character; employment_since from Capacity) are **pooled candidates**, pending the single
> pooled Shapley/BH-correction run across all five categories once Collateral and Conditions are also
> screened. The Step 5 v1 combination numbers above are kept in this log as a record of what was tested and
> why the methodology was revised, not as final decisions.

## Capacity — results

Target: `target` (positive class = `1` = bad/default, overall rate 30.0%).

**Reference ranges** (repeated per the standing format):

| IV range | Strength |
|---|---|
| < 0.02 | Useless |
| 0.02–0.1 | Weak |
| 0.1–0.3 | Medium |
| > 0.3 | Strong |

| Cramér's V range | Strength |
|---|---|
| < 0.1 | Negligible |
| 0.1–0.3 | Weak |
| 0.3–0.5 | Moderate |
| > 0.5 | Strong |

| Column | Rows | Cols | dof | min_expected | chi² statistic | p-value | IV | Cramér's V | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| employment_since | 5 | 2 | 4 | 18.60 | 18.368 | 0.0010 | 0.0864 | 0.1355 | Weak/weak — real, pool as candidate |
| job | 4 | 2 | 3 | 6.60 | 1.885 | 0.5966 | 0.0088 | 0.0434 | Useless/negligible — reject |
| installment_rate | 4 | 2 | 3 | 40.80 | 5.477 | 0.1400 | 0.0256 | 0.0740 | Weak (IV) but not significant — reject |
| people_liable | 2 | 2 | 1 | 46.50 | 0.000 | 1.0000 | 0.0000 | 0.0000 | Zero relationship — reject |
| residence_since | 4 | 2 | 3 | 39.00 | 0.749 | 0.8616 | 0.0006 | 0.0274 | Useless/negligible — reject |

All five cleared the min_expected ≥ 5 gate — no Mann-Whitney escalation needed.

**Step 5 v1 combination check (superseded — see methodology note above):** employment_since alone scored
holdout 0.5417 / CV 0.5809±0.0361 (barely above chance). Added to the 3 confirmed Character columns: holdout
0.6511, CV 0.6464±0.0239 (run `lab_20261008_065300_german_character_plus_employment_since_xgboost`), feature
importance 25.3%. A paired t-test on the 5 fold-level AUC differences vs. the Character-only model gave
t=2.20 (df=4) — marginally significant one-tailed (p≈0.046), suggestive but not strong evidence given n=5
folds. **Capacity's only pooled candidate: employment_since.** job, installment_rate, people_liable,
residence_since are rejected outright (not significant at Step 1-2, no ambiguity requiring Step 5).

## Capital — results

Target: `target` (positive class = `1` = bad/default, overall rate 30.0%).

**Reference ranges:**

| IV range | Strength |
|---|---|
| < 0.02 | Useless |
| 0.02–0.1 | Weak |
| 0.1–0.3 | Medium |
| > 0.3 | Strong |

| Cramér's V range | Strength |
|---|---|
| < 0.1 | Negligible |
| 0.1–0.3 | Weak |
| 0.3–0.5 | Moderate |
| > 0.5 | Strong |

| Column | Rows | Cols | dof | min_expected | chi² statistic | p-value | IV | Cramér's V | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| credit_amount (10-bin, continuous) | 10 | 2 | 9 | 29.70 | 24.789 | 0.0032 | 0.1136 | 0.1574 | Medium/weak — real, pool as candidate |
| savings_status | 5 | 2 | 4 | 14.40 | 36.099 | 2.76e-07 | 0.1960 | 0.1900 | Medium/weak — real, strongest in category, pool as candidate |
| other_installment_plans | 3 | 2 | 2 | 14.10 | 12.839 | 0.0016 | 0.0576 | 0.1133 | Weak/weak — real, pool as candidate |
| existing_credits | 4 | 2 | 3 | **1.80** | 2.671 | 0.4451 | 0.0036 | 0.0517 | Failed reliability gate — escalated |

`credit_amount` initially computed on raw unbinned values (921 unique prices) gave nonsense numbers
(min_expected 0.30, dof 920) — a textbook sparse-cell failure from treating a continuous column as 921
categories. Re-binned into 10 quantile bins (matching how `compute_iv` already bins internally) before
testing — the numbers in the table above are the corrected version. Cross-checked with Pearson point-biserial
r=0.1547 (p=8.8e-7) and Mann-Whitney p=0.0059 — both agree it's a real, if modest, positive relationship
(higher credit amounts, somewhat higher default rate, most visible in the top bin: 47% default in the
7,179-18,424 DM bucket vs. 22-36% elsewhere).

`existing_credits` failed Step 2 (min_expected=1.80, driven by the rare `existing_credits=4` category, n=6).
Escalated to Mann-Whitney: **p=0.1348, not significant.** Unlike HMEQ's DEROG/DELINQ/NINQ (where the gate
failure masked a real signal), here the escalation confirms the column really is noise — **reject outright.**

**Capital pooled candidates: credit_amount, savings_status, other_installment_plans.** existing_credits
rejected (gate failure + Mann-Whitney both negative, no Step 5 needed for an unambiguous reject).

## Collateral — results

Target: `target` (positive class = `1` = bad/default, overall rate 30.0%).

**Reference ranges:**

| IV range | Strength |
|---|---|
| < 0.02 | Useless |
| 0.02–0.1 | Weak |
| 0.1–0.3 | Medium |
| > 0.3 | Strong |

| Cramér's V range | Strength |
|---|---|
| < 0.1 | Negligible |
| 0.1–0.3 | Weak |
| 0.3–0.5 | Moderate |
| > 0.5 | Strong |

| Column | Rows | Cols | dof | min_expected | chi² statistic | p-value | IV | Cramér's V | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| property | 4 | 2 | 3 | 46.20 | 23.720 | 2.86e-05 | 0.1126 | 0.1540 | Medium/weak — real, pool as candidate |
| housing | 3 | 2 | 2 | 32.40 | 18.200 | 1.12e-04 | 0.0833 | 0.1349 | Weak/weak — real, pool as candidate |

Both cleared the gate comfortably, no escalation needed. `property`: lowest risk `real estate` (21.3%),
highest `unknown/none` (43.5%). `housing`: lowest risk `own` (26.1%), both `for free` (40.7%) and `rent`
(39.1%) notably higher. **Both pool as candidates.**

## Conditions — results

Target: `target` (positive class = `1` = bad/default, overall rate 30.0%).

**Reference ranges:**

| IV range | Strength |
|---|---|
| < 0.02 | Useless |
| 0.02–0.1 | Weak |
| 0.1–0.3 | Medium |
| > 0.3 | Strong |

| Cramér's V range | Strength |
|---|---|
| < 0.1 | Negligible |
| 0.1–0.3 | Weak |
| 0.3–0.5 | Moderate |
| > 0.5 | Strong |

| Column | Rows | Cols | dof | min_expected | chi² statistic | p-value | IV | Cramér's V | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| checking_status | 4 | 2 | 3 | 18.90 | 123.721 | 1.22e-26 | 0.6660 | 0.3517 | **Strong — strongest predictor in this dataset so far** |
| months_duration (10-bin) | 8 | 2 | 7 | 17.10 | 51.516 | 7.27e-09 | 0.2465 | 0.2270 | Medium/weak — real |
| purpose | 10 | 2 | 9 | **2.70** | 33.356 | 1.16e-04 | 0.1692 | 0.1826 | Gate-flagged — see resolution below |
| age (10-bin) | 10 | 2 | 9 | 22.20 | 20.618 | 0.0145 | 0.1006 | 0.1436 | Medium/weak — real |

`months_duration`/`age` cross-checked (both ordinal/continuous, Mann-Whitney valid): months_duration
Pearson r=0.215/Mann-Whitney p=7.98e-11 (longer loans, higher risk); age Pearson r=−0.091/Mann-Whitney
p=0.0004 (older borrowers, somewhat lower risk) — both intuitive, both confirmed real.

`purpose` failed Step 2 (min_expected=2.70, driven by sparse categories like `retraining` n=9,
`domestic appliances`/`others` n=12 each) — **but Mann-Whitney doesn't apply here**, since `purpose` is a
nominal categorical with no natural order (car/education/furniture... can't be ranked). This surfaced a real
gap in Step 3 as written, now documented in `METHODOLOGY.md` as Step 3a: when the gate fails on a nominal
column, escalate directly to Step 5 model validation instead of Mann-Whitney. Run: `purpose` alone scored
CV AUC 0.5881 ± 0.0217 (run `lab_20261008_080333_german_conditions_purpose_only_xgboost`) — clearly above
chance (≈4 standard deviations above 0.5), confirming the signal is real, not sparse-cell inflation.

**All four Conditions columns pool as candidates: checking_status, months_duration, purpose, age.**

## Full pooled candidate list — Steps 1-4 complete for all five categories

| Category | Pooled candidates | Rejected |
|---|---|---|
| Character | credit_history, personal_status_sex, other_debtors | foreign_worker, telephone |
| Capacity | employment_since | job, installment_rate, people_liable, residence_since |
| Capital | credit_amount, savings_status, other_installment_plans | existing_credits |
| Collateral | property, housing | (none) |
| Conditions | checking_status, months_duration, purpose, age | (none) |

**13 pooled candidates total**, out of 20 raw columns, pending the single Step 5 v2 Shapley/BH-correction
run across the complete pool (not yet executed — requires 2¹³ = 8,192 subset model evaluations with 5-fold
CV each, i.e. XGBoost retrained and cross-validated ~40,960 times).

## Step 5 v2 — pooled Shapley / Benjamini-Hochberg analysis (final column decision)

Ran the complete Step 5 v2 procedure from `METHODOLOGY.md` across all 13 pooled candidates: value function =
5-fold CV AUC per subset (same fixed `StratifiedKFold(random_state=42)` as every other comparison in this
file), XGBoost as the model throughout, `v({})` defined as the constant 0.5 (chance). 2¹³ − 1 = 8,191
non-empty subsets evaluated, 5 folds each = 40,955 XGBoost fits, ~43.6 minutes wall-clock.

**Efficiency check (correctness sanity check on the computation):** sum of all 13 columns' average Shapley
contributions reconstructs the full-pool model's total AUC improvement over chance (`v(full) − v(empty)`)
almost exactly — max discrepancy 3.3×10⁻¹⁶ (floating-point-level). Computation confirmed correct.

**Per-column results**, sorted by mean Shapley contribution, with paired one-sample t-test (5 fold-level
Shapley values vs. null of zero) and Benjamini-Hochberg-corrected p-value:

| Column | Mean Shapley (ΔAUC) | Std across folds | t-stat | raw p | BH-adjusted p | Keep? |
|---|---:|---:|---:|---:|---:|---:|
| checking_status | 0.0835 | 0.0243 | 7.68 | 0.0015 | 0.0076 | **YES** |
| months_duration | 0.0407 | 0.0109 | 8.37 | 0.0011 | 0.0076 | **YES** |
| credit_history | 0.0382 | 0.0115 | 7.43 | 0.0018 | 0.0076 | **YES** |
| savings_status | 0.0246 | 0.0175 | 3.15 | 0.0346 | 0.0729 | no |
| purpose | 0.0223 | 0.0098 | 5.09 | 0.0070 | 0.0229 | **YES** |
| credit_amount | 0.0169 | 0.0125 | 3.02 | 0.0393 | 0.0729 | no |
| other_installment_plans | 0.0126 | 0.0071 | 3.98 | 0.0164 | 0.0427 | **YES** |
| property | 0.0121 | 0.0207 | 1.31 | 0.2611 | 0.3293 | no |
| employment_since | 0.0103 | 0.0142 | 1.62 | 0.1805 | 0.2608 | no |
| housing | 0.0091 | 0.0109 | 1.86 | 0.1367 | 0.2222 | no |
| age | 0.0088 | 0.0157 | 1.25 | 0.2786 | 0.3293 | no |
| personal_status_sex | 0.0050 | 0.0101 | 1.09 | 0.3353 | 0.3632 | no |
| other_debtors | 0.0017 | 0.0063 | 0.62 | 0.5711 | 0.5711 | no |

Full subset-level AUC data: `german_credit_shapley_results.json`. Full per-column Shapley/significance
output: `german_credit_shapley_analysis.json`.

**Final keep list: 5 of 20 raw columns** — `checking_status`, `months_duration`, `credit_history`, `purpose`,
`other_installment_plans`.

**What changed relative to the v1 (greedy, category-locked) results earlier in this file, and why it
matters:** `savings_status` and `credit_amount` both looked clearly real at Step 1 (IV 0.196 and 0.114) but
do not survive the pooled, BH-corrected test — their univariate signal is largely redundant with the 5 kept
columns once averaged across every combination. More tellingly, `personal_status_sex` and `other_debtors` —
which the superseded Step 5 v1 Character-only combination model called "additive" (27.6%/24.4% feature
importance in that now-retired analysis) — also fail here. That earlier result is very likely exactly the
order-dependency artifact flagged when this methodology was revised: those two columns looked valuable only
in the narrow context of "credit_history already present, nothing else," not against the full 13-column pool.
`employment_since` (the "marginally significant, one-tailed p≈0.046" borderline case from the earlier paired
t-test against the Character-only baseline) also fails once tested against the full pool rather than a
3-column baseline. This is direct, concrete evidence that the v1→v2 methodology revision was necessary, not
just theoretically cleaner.

## Final model

5 columns (checking_status, months_duration, credit_history, purpose, other_installment_plans), XGBoost:

| Metric | Value |
|---|---:|
| Holdout AUC | 0.7724 |
| 5-fold CV AUC | 0.7651 ± 0.0227 |
| Run ID | lab_20261008_090540_german_shapley_final_five_xgboost |

By the Hosmer-Lemeshow absolute scale (0.5-0.7 poor, 0.7-0.8 acceptable, 0.8-0.9 excellent, >0.9 outstanding),
this model sits in the **"acceptable"** band — a substantial jump from any of the partial-category models
tested earlier in this file (all of which were in the "poor" 0.6-range band).

Feature importance in the final model: checking_status 37.1%, credit_history 17.3%, other_installment_plans
15.9%, months_duration 15.3%, purpose 14.3% — notably balanced, no single column dominating the way
`credit_history` did in the earlier (now-superseded) Character-only models.

## Open reference point

Original TAI paper Step A baseline for this dataset: Logistic Regression on all 20 raw features (no
screening), 0.8014 AUC. The 5-column Shapley/BH-confirmed model (CV AUC 0.7651, holdout 0.7724) comes close
to that full-feature baseline using only 5 of 20 columns (a 75% reduction) — notable, but **not a clean
apples-to-apples comparison**: different model type (XGBoost vs. Logistic Regression) and no screening was
applied to the baseline. Flagging this honestly rather than claiming the screened model "beats" or "matches"
the baseline — that would require re-running the baseline with the same model type to be a fair comparison.

## Probability calibration (2026-10-09)

Raw model's Brier score (0.1955) was already better than the trivial base-rate baseline (0.2100), but ECE
(0.1492) showed real room for improvement. Isotonic calibration applied (see `CALIBRATION_NOTES.md`):

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier score | 0.2100 | 0.1955 | **0.1664** |
| ECE | — | 0.1492 | **0.0519** |
| AUC | — | 0.7724 | 0.7795 |

ECE improved 65% (0.1492→0.0519) — the smallest relative improvement of the four datasets, but still
substantial. This is also the smallest dataset (1,000 rows), so the calibration curve has the least data to
fit from, consistent with it ending up the least refined of the four. AUC essentially unchanged (+0.0071,
within fold noise).
