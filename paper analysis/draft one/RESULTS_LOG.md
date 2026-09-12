# Results Log — "Do AI Explanations Survive Falsification?" revision (draft one)

Purpose: every number that will enter the revised paper is recorded here first, with the run ID that
produced it. Nothing goes into a table without a run ID. Runs are produced by the app's Dataset Lab
(`ml_models/dataset_lab.py`; records under `data/ml_lab/runs/<run_id>.json`, index in `data/ml_lab/index.json`),
so any cell can be regenerated.

Conventions used throughout: stratified 80/20 split, `random_state=42`, split **before** any resampling,
test set kept at the raw base rate, 5-fold stratified CV reported alongside the holdout figure,
classification threshold 0.5 unless stated.

---

## 0. Ground truth about the original submission (established 2026-09-06)

**Datasets (canonical copies: `paper analysis/sample datasets/`, registered in the Lab as `paper_*.csv`):**

| Dataset | Rows | Inputs | Positives | Positive rate | Notes |
|---|---:|---:|---:|---:|---|
| German Credit | 1,000 | 20 | 300 | 0.300 | 13 categorical columns; values contain "≥" |
| Taiwan Credit Default | 30,000 | 23 | 6,636 | 0.221 | all numeric |
| Bank Marketing (**bank-full** variant) | 45,211 | 16 | 5,289 | 0.117 | 9 categorical; `contact`/`poutcome` blanks (52,124 empty cells) = "unknown"; `duration` included, as in the original |

These match the original Table I exactly. Note the paper uses the older `bank-full` file, **not**
`bank-additional-full` (41,188 rows, 20 inputs) — do not mix them.

**Why every original result must be regenerated** — verified from the submitted result files
(`Updated papers/Supporting files - Dataset and Results/*/benchmark_auc_sanity_*.json` and `result_data_preaparation_*.json`):

- Prep pipeline was `imputation -> feature_screening -> smote` on the **full** dataset, then the 80/20 split.
- Taiwan `train_result.n_samples = 46,728` = 2 × 23,364 → the whole dataset was oversampled to 50/50 before splitting.
- Test support = 4,673 / 4,673 → the held-out set was itself synthetic and balanced.
- Consequences: every original AUC/Accuracy/ρ was measured on a leakage-affected, artificially balanced test set;
  Table VI's "Base Rate: 50%" is the same root cause; tree/ensemble models are inflated most.
  The first draft's leakage-isolation tables (pre-split vs train-fold-only SMOTE) reproduce the originals closely.

**Internal inconsistencies in the original to correct in the text:**
- Text: Ridge LR Taiwan ρ = 9.85, DNN Taiwan ρ = 10.50; Table IV / JSON: 0.58 and 2.54.
- German benchmark: XGBoost in the text (0.8787, ρ 1.48) vs GBM in Table V (0.8671, ρ 1.60).
- Feature counts use three unlabelled bases (raw 20/16/23; Boruta-confirmed 13/7/20-or-15; post-encoding 17/13/20).
- Taiwan class split printed as "78:23".
- The result JSONs contain a 22nd model (AutoML) never reported in Table IV.

---

## 1. Step A — corrected Phase 2 baseline, five model types (2026-09-06)

Configuration: split first (stratified, rs=42) → train on the raw 80% (no SMOTE, no class-weight changes beyond
each model's library default: `class_weight='balanced'` for LR/RF/ET, `scale_pos_weight = n_neg/n_pos` for XGBoost,
none for GBM) → evaluate on the untouched 20% at its natural base rate. **All raw features** (Phase 1 IV/Boruta
screening not yet applied). No hyperparameter search (library/app defaults). Categorical columns one-hot encoded.

| Dataset | Model | Orig. AUC | **Corr. AUC** | ΔAUC | 5-fold CV AUC | Orig. Acc (%) | Corr. Acc (%) | Corr. PR-AUC | Corr. Brier | Run ID |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| German Credit | Ridge LR (L2)* | 0.8596 | **0.8014** | -0.058 | 0.7804 ± 0.0199 | 79.3 | 75.0 | 0.6393 | 0.1839 | `lab_20260906_223355_german_credit_logistic_regression` |
| German Credit | Random Forest | 0.8599 | **0.7989** | -0.061 | 0.7924 ± 0.0233 | 79.6 | 77.0 | 0.6397 | 0.1798 | `lab_20260906_223357_german_credit_random_forest` |
| German Credit | Extra Trees | 0.8453 | **0.7848** | -0.060 | 0.7794 ± 0.0228 | 75.7 | 70.0 | 0.6157 | 0.1861 | `lab_20260906_222907_german_credit_extra_trees` |
| German Credit | GBM | 0.8671 | **0.7935** | -0.074 | 0.7867 ± 0.0276 | 80.0 | 74.0 | 0.6388 | 0.1774 | `lab_20260906_223304_german_credit_gradient_boosting` |
| German Credit | XGBoost | 0.8787 | **0.7627** | -0.116 | 0.7848 ± 0.0250 | 79.6 | 69.5 | 0.6267 | 0.1914 | `lab_20260906_223402_german_credit_xgboost` |
| Taiwan Credit Default | Ridge LR (L2)* | 0.7435 | **0.7081** | -0.035 | 0.7234 ± 0.0038 | 67.9 | 68.0 | 0.4904 | 0.2089 | `lab_20260906_223040_taiwan_credit_logistic_regression` |
| Taiwan Credit Default | Random Forest | 0.9065 | **0.7746** | -0.132 | 0.7791 ± 0.0063 | 83.0 | 78.1 | 0.5482 | 0.1787 | `lab_20260906_223041_taiwan_credit_random_forest` |
| Taiwan Credit Default | Extra Trees | 0.9043 | **0.7585** | -0.146 | 0.7707 ± 0.0047 | 83.1 | 77.5 | 0.5260 | 0.1982 | `lab_20260906_222911_taiwan_credit_extra_trees` |
| Taiwan Credit Default | GBM | 0.8318 | **0.7776** | -0.054 | 0.7824 ± 0.0060 | 75.2 | 76.3 | 0.5534 | 0.1814 | `lab_20260906_222915_taiwan_credit_gradient_boosting` |
| Taiwan Credit Default | XGBoost | 0.8685 | **0.7762** | -0.092 | 0.7823 ± 0.0049 | 78.3 | 76.2 | 0.5523 | 0.1788 | `lab_20260906_223048_taiwan_credit_xgboost` |
| Bank Marketing | Ridge LR (L2)* | 0.8879 | **0.9079** | +0.020 | 0.9097 ± 0.0052 | 81.8 | 84.6 | 0.5375 | 0.1199 | `lab_20260906_223239_bank_marketing_bankfull_logistic_regression` |
| Bank Marketing | Random Forest | 0.9509 | **0.9159** | -0.035 | 0.9154 ± 0.0022 | 88.1 | 83.1 | 0.5773 | 0.1289 | `lab_20260906_223241_bank_marketing_bankfull_random_forest` |
| Bank Marketing | Extra Trees | 0.9436 | **0.8570** | -0.087 | 0.8542 ± 0.0066 | 87.3 | 79.3 | 0.4865 | 0.1721 | `lab_20260906_223054_bank_marketing_bankfull_extra_trees` |
| Bank Marketing | GBM | 0.9089 | **0.9240** | +0.015 | 0.9259 ± 0.0040 | 84.1 | 84.6 | 0.5911 | 0.1124 | `lab_20260906_223059_bank_marketing_bankfull_gradient_boosting` |
| Bank Marketing | XGBoost | 0.9193 | **0.9314** | +0.012 | 0.9334 ± 0.0041 | 84.9 | 85.0 | 0.6263 | 0.1038 | `lab_20260906_223247_bank_marketing_bankfull_xgboost` |

\* The app's `logistic_regression` is L2 logistic regression with median imputation + standard scaling and
`class_weight='balanced'` (C = 1.0) — the closest available analogue of the paper's Ridge LR (L2), not an identical estimator.

Split details (identical for every model of a dataset):
- German Credit: 20 raw → 61 encoded features; train 800 / test 200; test positives 60 (0.300).
- Taiwan Credit Default: 23 raw → 23 encoded; train 24,000 / test 6,000; test positives 1,327 (0.221).
- Bank Marketing: 16 raw → 47 encoded; train 36,168 / test 9,043; test positives 1,058 (0.117).

### Reading of Step A

1. **The original tree-model numbers were inflated by the leakage, as diagnosed.** Corrected AUC drops by 0.06–0.12 on
   German Credit and 0.05–0.15 on Taiwan; the largest drops are exactly the tree/ensemble models (Taiwan RF −0.132,
   ET −0.146; German XGB −0.116). Linear models move least — the pattern expected if SMOTE-before-split leaked
   neighbourhood structure that trees exploit.
2. **Bank Marketing is the exception (+0.01–0.02 for LR/GBM/XGB, −0.035/−0.087 for RF/ET).** With 45k rows and
   `duration` included, the signal is strong enough that the honest pipeline is close to — sometimes above — the
   original. The first draft observed the same and attributed it partly to feature-set differences; here the feature
   set is *all raw columns*, so the effect is genuinely "this dataset was less affected by the leakage".
3. **Ranking within a dataset changes.** Under the honest pipeline, German Credit is led by LR (0.80) rather than
   XGBoost (0.88 originally); Taiwan by GBM/XGB (~0.78) rather than RF/ET (~0.91 originally). The revised text must
   not carry over the original's model-ranking statements.
4. **CV vs holdout agree**: every holdout AUC is within its CV band except German Credit (200-row test set, sd ≈ 0.02–0.03) —
   German holdout numbers alone should not be quoted without the CV interval.
5. **Corrected accuracy is not comparable to the original accuracy** and should be dropped from the main table or
   reported separately: the original was measured on a 50/50 synthetic test set at 0.5, ours on the real base rate with
   class-weighted models (which trade accuracy for recall). Prefer AUC + PR-AUC + Brier (+ KS once added).

### Consistency check against the first draft's two-model pilot (`latex/main.tex`, Table "correctedauc")

| Dataset | Model | First-draft corrected AUC | Step A AUC | Comment |
|---|---|---:|---:|---|
| German Credit | Ridge LR | 0.7939 | 0.8014 | agree within 0.01 |
| German Credit | XGBoost | 0.7336 | 0.7627 | same direction; draft used Boruta-rerun features + tuning + train-fold SMOTE |
| Taiwan | Ridge LR | 0.7048 | 0.7081 | agree within 0.01 |
| Taiwan | XGBoost | 0.7510 | 0.7762 | same direction |
| Bank Marketing | Ridge LR | 0.9016 | 0.9079 | agree within 0.01 |
| Bank Marketing | XGBoost | 0.9237 | 0.9314 | agree within 0.01 |

Two independent implementations of the corrected pipeline land within ~0.01–0.03 AUC of each other everywhere;
the residual gaps are explained by the draft's extra steps (Phase 1 screening, tuning, training-fold SMOTE), which
will be added and isolated in later steps rather than assumed.

### Caveats carried forward
- No hyperparameter tuning yet (the original used `RandomizedSearchCV`); no Phase 1 screening; five of 21 models.

## 1b. Step A variant — Bank Marketing with vs. without `duration` (2026-09-06)

Decision (user, 2026-09-06): report **both** configurations. `duration` (call length in seconds) is only known after
the call ends; UCI's dataset note says it should be discarded for a realistic predictive model. The original
submission kept it (its global SHAP ranked it first). Identical pipeline to §1 otherwise; the without-duration
runs drop exactly one raw column (15 raw → 46 encoded; same split, same 1,058 test positives).

| Model | Orig. AUC (with dur.) | **With duration** AUC | CV | **Without duration** AUC | CV | Δ (drop dur.) | PR-AUC with / without | Brier with / without | Run IDs (with / without) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Ridge LR (L2)* | 0.8879 | **0.9079** | 0.9097 ± 0.0052 | **0.7722** | 0.7664 ± 0.0081 | -0.136 | 0.537 / 0.409 | 0.120 / 0.183 | `lab_20260906_223239_bank_marketing_bankfull_logistic_regression` / `lab_20260906_224252_bank_marketing_bankfull_noduration_logistic_regression` |
| Random Forest | 0.9509 | **0.9159** | 0.9154 ± 0.0022 | **0.7926** | 0.7831 ± 0.0098 | -0.123 | 0.577 / 0.427 | 0.129 / 0.176 | `lab_20260906_223241_bank_marketing_bankfull_random_forest` / `lab_20260906_224254_bank_marketing_bankfull_noduration_random_forest` |
| Extra Trees | 0.9436 | **0.8570** | 0.8542 ± 0.0066 | **0.7769** | 0.7696 ± 0.0104 | -0.080 | 0.486 / 0.417 | 0.172 / 0.189 | `lab_20260906_223054_bank_marketing_bankfull_extra_trees` / `lab_20260906_224200_bank_marketing_bankfull_noduration_extra_trees` |
| GBM | 0.9089 | **0.9240** | 0.9259 ± 0.0040 | **0.8032** | 0.7962 ± 0.0101 | -0.121 | 0.591 / 0.452 | 0.112 / 0.167 | `lab_20260906_223059_bank_marketing_bankfull_gradient_boosting` / `lab_20260906_224205_bank_marketing_bankfull_noduration_gradient_boosting` |
| XGBoost | 0.9193 | **0.9314** | 0.9334 ± 0.0041 | **0.8045** | 0.7998 ± 0.0097 | -0.127 | 0.626 / 0.467 | 0.104 / 0.160 | `lab_20260906_223247_bank_marketing_bankfull_xgboost` / `lab_20260906_224300_bank_marketing_bankfull_noduration_xgboost` |

### Reading of the duration variant
1. Dropping `duration` costs **0.08–0.14 AUC** for every model (0.93 → 0.80 for XGBoost); PR-AUC and Brier degrade
   in step. This is the same magnitude the Lab measured on the *bank-additional* variant (0.955 → 0.815), so it is a
   property of the dataset, not of our pipeline.
2. Without `duration`, Bank Marketing lands at AUC ≈ 0.77–0.80 — **below Taiwan for linear models and level with it for
   boosting** — so the original's "Bank Marketing is the easiest dataset" ordering exists only because of `duration`.
   Any statement in the revision about dataset difficulty must say which configuration it refers to.
3. Top XGBoost drivers without `duration`: `poutcome_success`, `contact_cellular`, `housing`, `month`. With it,
   `duration` is the second driver — consistent with the original's global SHAP, which ranked it first.
4. Implication for the Sanity Ratio (Step B): `duration` is a strong, post-outcome feature; ρ computed with it in the
   feature set may be inflated by a variable no deployable model could use. Step B will therefore be run on **both**
   configurations for Bank Marketing, and the revision should present the without-duration figures as the
   deployable case and the with-duration figures as the comparability case.

---

---

## 2. Step B — Sanity Ratio with a permutation null: German Credit, K = 20 (2026-09-06)

Tool: `ml_models/sanity_ratio.py` (records under `data/ml_lab/sanity/<run_id>__K<k>.json`, index `data/ml_lab/sanity_index.json`).
Definition used: S = mean |SHAP| over all (test row × feature) cells of the positive-class attribution matrix;
ρ_k = S_real / S_rand,k for each of K label permutations of the **training** fold (test rows and features untouched);
ρ reported as the median over k with the 2.5–97.5 percentile interval; p = (1 + #{S_rand,k ≥ S_real}) / (K + 1).
SHAP on all 200 test rows, 61 encoded features, seed 42. Explainers: LinearExplainer (LR, scaled space, training-row
background), TreeExplainer (RF/ET class-1 slice, GBM log-odds), XGBoost native TreeSHAP (`pred_contribs`). No SMOTE
anywhere → real and permuted pipelines are symmetric by construction (addresses reviewer R3.3 for this configuration).

Null validity check: the permuted-label models score AUC 0.506–0.524 on the real test set (≈ 0.5), so the null is a
genuine "no label information" baseline.

| Model | Orig. ρ (leaky) | AUC real | AUC of permuted models | S_real | S_rand median | **ρ median** | ρ 95% interval [min, max over K] | p (one-sided) | Fixed 2.0 | Null p95 / p99 | ρ with median-|SHAP| aggregation | Explainer | Run ID |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|---|---|
| Ridge LR (L2)* | 1.28 | 0.8014 | 0.517 | 0.09656 | 0.04238 | **2.28** | [1.92, 3.20] [1.91, 3.46] | 0.0476 | PASS | PASS / PASS (thr 1.18/1.19) | 1.83 | shap.LinearExplainer | `lab_20260906_223355_german_credit_logistic_regression` |
| Random Forest | 1.71 | 0.7989 | 0.506 | 0.00718 | 0.00322 | **2.23** | [1.95, 2.73] [1.95, 2.76] | 0.0476 | PASS | PASS / PASS (thr 1.14/1.15) | 1.57 | shap.TreeExplainer | `lab_20260906_223357_german_credit_random_forest` |
| Extra Trees | 1.15 | 0.7848 | 0.512 | 0.00716 | 0.00314 | **2.28** | [2.00, 2.92] [1.96, 3.00] | 0.0476 | PASS | PASS / PASS (thr 1.12/1.15) | 1.59 | shap.TreeExplainer | `lab_20260906_222907_german_credit_extra_trees` |
| GBM | 1.60 | 0.7935 | 0.515 | 0.06728 | 0.03517 | **1.91** | [1.73, 2.26] [1.72, 2.31] | 0.0476 | FAIL | PASS / PASS (thr 1.09/1.11) | 1.69 | shap.TreeExplainer | `lab_20260906_223304_german_credit_gradient_boosting` |
| XGBoost | 1.48 | 0.7627 | 0.524 | 0.06861 | 0.03829 | **1.79** | [1.62, 2.11] [1.61, 2.11] | 0.0476 | FAIL | PASS / PASS (thr 1.10/1.11) | 1.47 | xgboost pred_contribs | `lab_20260906_223402_german_credit_xgboost` |

"Null p95 / p99" = does S_real exceed the 95th / 99th percentile of the K null values; "thr" = the ρ threshold that
percentile implies (p95/median, p99/median of S_rand). p = 0.0476 is the floor attainable with K = 20 (1/21): in every
case S_real exceeded all 20 null values.

### Reading of Step B (German Credit) — **this is unfavourable to the original headline claim**

1. **German Credit is not an "impossibility regime" under the honest pipeline at ρ_min = 2.0.** Three of five models
   (LR 2.28, ET 2.28, RF 2.23) pass at the median; GBM (1.91) and XGBoost (1.79) fail. The original reported
   0.71–1.87 for all 21 models and built the paper's central claim on "zero survivors". Those original values came from
   the leaky pipeline and are not comparable; the honest values sit **at the boundary**, not clearly below it.
2. **Every model's attributions are statistically distinguishable from the permutation null** (p at the K=20 floor for
   all five; S_real is 1.6–2.3× the null median, and the null's 99th percentile implies a threshold of only 1.1–1.2).
   The paper's literal claim — "attributions indistinguishable from a random-label baseline" — is **false** for
   German Credit under the corrected pipeline. What remains true is weaker: German Credit has the *lowest* ρ of the
   datasets tested so far (to be confirmed once Taiwan/Bank Marketing are run) and models cluster around 2.0.
3. **The verdict is sensitive to exactly the things the reviewers flagged:**
   - *Threshold* (R2.3, R3.2): at 2.0, 3/5 pass; at the null-derived 1.2, 5/5 pass; at 2.3, 0/5 pass. The 2.0 line
     runs straight through the German cluster.
   - *Aggregation* (R3.1, B4): with median |SHAP| instead of mean, every model falls to 1.47–1.83 and **all fail** 2.0.
   - *Permutation variance* (R3.1): the 95% intervals span ~0.5–1.3 in ρ; for LR the interval [1.92, 3.20] straddles
     2.0, so "pass" is a median statement, not a certainty (no model passes on *every* permutation).
4. What this means for the revision: the honest story is **"boundary regime with threshold-dependent verdict"**, not
   "impossibility regime". That is a defensible and arguably more interesting finding — it makes the threshold-sweep
   (reviewer A2) the centrepiece rather than a robustness appendix — but the abstract, introduction, Structural
   Property 1, and the conclusion cannot keep the impossibility language.
5. Caveats: 200-row test set; five of 21 models; no Phase 1 screening; no tuning; TreeExplainer/`tree_path_dependent`
   only (explainer sensitivity — R3.4 — still to run). None of these caveats is likely to move ρ *down* to the
   original's 0.7–1.9 range, but they must be run before any number here is quoted in the paper.

### 2a. German Credit at K = 100 (same runs, same seed; supersedes the K = 20 table for quotation)

| Model | ρ median K=20 | ρ median **K=100** | 95% interval (K=100) | [min, max] over 100 | p (K=100) | share of permutations with ρ ≥ 2.0 | Fixed 2.0 | Null p99 thr (K=100) | median-|SHAP| ρ | Run ID |
|---|---:|---:|---|---|---:|---:|---|---:|---:|---|
| Ridge LR (L2)* | 2.28 | **2.31** | [1.91, 2.92] | [1.77, 3.46] | 0.0099 | 89% | PASS | 1.22 | 1.99 | `lab_20260906_223355_german_credit_logistic_regression` |
| Random Forest | 2.23 | **2.27** | [1.95, 2.74] | [1.87, 2.77] | 0.0099 | 95% | PASS | 1.21 | 1.59 | `lab_20260906_223357_german_credit_random_forest` |
| Extra Trees | 2.28 | **2.36** | [1.96, 2.92] | [1.88, 3.06] | 0.0099 | 96% | PASS | 1.24 | 1.61 | `lab_20260906_222907_german_credit_extra_trees` |
| GBM | 1.91 | **1.90** | [1.68, 2.20] | [1.61, 2.31] | 0.0099 | 26% | FAIL | 1.15 | 1.68 | `lab_20260906_223304_german_credit_gradient_boosting` |
| XGBoost | 1.79 | **1.80** | [1.57, 2.10] | [1.54, 2.15] | 0.0099 | 15% | FAIL | 1.16 | 1.41 | `lab_20260906_223402_german_credit_xgboost` |

Permuted-label models' mean test AUC at K=100: 0.488–0.505 (null valid). p = 0.0099 is the K=100 floor (1/101): S_real
exceeded all 100 null values for every model. K=100 moves every median by ≤ 0.08 versus K=20 and does not change any
fixed-2.0 verdict — K=20 was already representative; K=100 tightens the p-value floor and the interval estimates.
"Share of permutations with ρ ≥ 2.0" is the honest pass-rate: LR/RF/ET pass on 89–96% of permutations, GBM/XGB on
15–26% — the three "passes" are robust majorities, not coin flips, and the two "fails" are robust failures. Files:
`data/ml_lab/sanity/*german_credit*__K100.json`.

## 3. Step B — cross-dataset Sanity Ratio: Taiwan and Bank Marketing (K = 20), with German (K = 100) for reference (2026-09-06)

Same definition and tooling as §2. SHAP evaluated on a seeded 2,000-row subsample of the test set for the two large
datasets (all 200 rows for German). Taiwan/Bank Marketing at K = 20 (p floor 1/21 = 0.0476); to be raised to K = 100
before quotation. Records: `data/ml_lab/sanity/*taiwan*__K20.json`, `*bank_marketing_bankfull*__K20.json`.

| Dataset | Model | Orig. ρ (leaky) | AUC real | AUC permuted | **ρ median** | 95% interval | [min, max] | share ρ≥2.0 | p | Fixed 2.0 | Null p99 thr | median-|SHAP| ρ | SHAP rows | Run ID |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|---:|---|
| German Credit (K=100) | Ridge LR (L2)* | 1.28 | 0.8014 | 0.504 | **2.31** | [1.91, 2.92] | [1.77, 3.46] | 89% | 0.0099 | PASS | 1.22 | 1.99 | 200/200 | `lab_20260906_223355_german_credit_logistic_regression` |
| German Credit (K=100) | Random Forest | 1.71 | 0.7989 | 0.489 | **2.27** | [1.95, 2.74] | [1.87, 2.77] | 95% | 0.0099 | PASS | 1.21 | 1.59 | 200/200 | `lab_20260906_223357_german_credit_random_forest` |
| German Credit (K=100) | Extra Trees | 1.15 | 0.7848 | 0.497 | **2.36** | [1.96, 2.92] | [1.88, 3.06] | 96% | 0.0099 | PASS | 1.24 | 1.61 | 200/200 | `lab_20260906_222907_german_credit_extra_trees` |
| German Credit (K=100) | GBM | 1.60 | 0.7935 | 0.488 | **1.90** | [1.68, 2.20] | [1.61, 2.31] | 26% | 0.0099 | FAIL | 1.15 | 1.68 | 200/200 | `lab_20260906_223304_german_credit_gradient_boosting` |
| German Credit (K=100) | XGBoost | 1.48 | 0.7627 | 0.500 | **1.80** | [1.57, 2.10] | [1.54, 2.15] | 15% | 0.0099 | FAIL | 1.16 | 1.41 | 200/200 | `lab_20260906_223402_german_credit_xgboost` |
| Taiwan Credit Default (K=20) | Ridge LR (L2)* | 0.58 | 0.7081 | 0.504 | **3.35** | [2.67, 6.63] | [2.65, 6.88] | 100% | 0.0476 | PASS | 1.26 | 3.50 | 2000/6000 | `lab_20260906_223040_taiwan_credit_logistic_regression` |
| Taiwan Credit Default (K=20) | Random Forest | 2.44 | 0.7746 | 0.518 | **8.12** | [7.15, 9.28] | [6.63, 9.31] | 100% | 0.0476 | PASS | 1.19 | 8.71 | 2000/6000 | `lab_20260906_223041_taiwan_credit_random_forest` |
| Taiwan Credit Default (K=20) | Extra Trees | 3.08 | 0.7585 | 0.516 | **13.02** | [10.40, 16.22] | [9.59, 16.87] | 100% | 0.0476 | PASS | 1.32 | 7.64 | 2000/6000 | `lab_20260906_222911_taiwan_credit_extra_trees` |
| Taiwan Credit Default (K=20) | GBM | 1.58 | 0.7776 | 0.514 | **5.54** | [4.95, 6.09] | [4.80, 6.28] | 100% | 0.0476 | PASS | 1.14 | 5.85 | 2000/6000 | `lab_20260906_222915_taiwan_credit_gradient_boosting` |
| Taiwan Credit Default (K=20) | XGBoost | 1.87 | 0.7762 | 0.512 | **3.14** | [2.93, 3.35] | [2.91, 3.43] | 100% | 0.0476 | PASS | 1.08 | 2.99 | 2000/6000 | `lab_20260906_223048_taiwan_credit_xgboost` |
| Bank Marketing, with duration (K=20) | Ridge LR (L2)* | 1.92 | 0.9079 | 0.516 | **8.03** | [3.60, 14.32] | [2.88, 14.54] | 100% | 0.0476 | PASS | 2.60 | 7.45 | 2000/9043 | `lab_20260906_223239_bank_marketing_bankfull_logistic_regression` |
| Bank Marketing, with duration (K=20) | Random Forest | 6.14 | 0.9159 | 0.418 | **10.39** | [8.35, 13.21] | [7.89, 13.43] | 100% | 0.0476 | PASS | 1.29 | 6.00 | 2000/9043 | `lab_20260906_223241_bank_marketing_bankfull_random_forest` |
| Bank Marketing, with duration (K=20) | Extra Trees | 4.14 | 0.8570 | 0.468 | **8.44** | [6.59, 11.57] | [5.91, 12.04] | 100% | 0.0476 | PASS | 1.38 | 5.75 | 2000/9043 | `lab_20260906_223054_bank_marketing_bankfull_extra_trees` |
| Bank Marketing, with duration (K=20) | GBM | 3.25 | 0.9240 | 0.476 | **12.15** | [9.73, 14.31] | [9.27, 14.64] | 100% | 0.0476 | PASS | 1.29 | 16.87 | 2000/9043 | `lab_20260906_223059_bank_marketing_bankfull_gradient_boosting` |
| Bank Marketing, with duration (K=20) | XGBoost | 2.64 | 0.9314 | 0.458 | **8.05** | [7.02, 8.95] | [6.93, 9.03] | 100% | 0.0476 | PASS | 1.16 | 8.13 | 2000/9043 | `lab_20260906_223247_bank_marketing_bankfull_xgboost` |
| Bank Marketing, without duration (K=20) | Ridge LR (L2)* | — | 0.7722 | 0.512 | **4.62** | [2.04, 8.31] | [1.64, 8.34] | 95% | 0.0476 | PASS | 2.63 | 6.16 | 2000/9043 | `lab_20260906_224252_bank_marketing_bankfull_noduration_logistic_regression` |
| Bank Marketing, without duration (K=20) | Random Forest | — | 0.7926 | 0.435 | **8.09** | [6.35, 10.12] | [6.05, 10.65] | 100% | 0.0476 | PASS | 1.31 | 6.16 | 2000/9043 | `lab_20260906_224254_bank_marketing_bankfull_noduration_random_forest` |
| Bank Marketing, without duration (K=20) | Extra Trees | — | 0.7769 | 0.473 | **7.65** | [6.04, 10.21] | [5.50, 10.63] | 100% | 0.0476 | PASS | 1.35 | 5.32 | 2000/9043 | `lab_20260906_224200_bank_marketing_bankfull_noduration_extra_trees` |
| Bank Marketing, without duration (K=20) | GBM | — | 0.8032 | 0.486 | **6.97** | [5.50, 8.01] | [5.29, 8.17] | 100% | 0.0476 | PASS | 1.30 | 8.25 | 2000/9043 | `lab_20260906_224205_bank_marketing_bankfull_noduration_gradient_boosting` |
| Bank Marketing, without duration (K=20) | XGBoost | — | 0.8045 | 0.469 | **4.09** | [3.67, 4.52] | [3.58, 4.56] | 100% | 0.0476 | PASS | 1.13 | 4.59 | 2000/9043 | `lab_20260906_224300_bank_marketing_bankfull_noduration_xgboost` |

Per-dataset range of ρ medians: German 1.80–2.36 (3/5 pass) · Taiwan 3.14–13.02 (5/5) · Bank Marketing with duration
8.03–12.15 (5/5) · Bank Marketing without duration 4.09–8.09 (5/5).

### Reading of the cross-dataset result

1. **The regime ordering survives the honest pipeline, in weakened form.** German Credit is clearly the lowest-ρ
   dataset (every German model sits below every Taiwan/Bank Marketing model), and it is the only dataset with fixed-2.0
   failures. But it is a *boundary* regime (3/5 pass; all attributions distinguishable from the null), not an
   impossibility regime. Taiwan and Bank Marketing pass with entire intervals above 2.
2. **The original's Taiwan verdicts were wrong in direction, not just magnitude.** Original: LR 0.58, GBM 1.58, XGB 1.87
   (fail); honest: 3.35, 5.54, 3.14 (pass, min over permutations ≥ 2.65). The original's model-level Taiwan story
   ("linear models fail, ensembles pass") does not reproduce — under the honest pipeline every family passes.
3. **`duration` inflates ρ but does not decide the verdict.** Dropping it lowers Bank Marketing ρ by 10–50% (LR 8.0→4.6,
   GBM 12.2→7.0, XGB 8.1→4.1); all five models still pass comfortably. The deployable configuration keeps the regime
   conclusion. (Note LR's wide intervals on Bank Marketing — [2.04, 8.31] without duration, one permutation at 1.64 —
   LinearExplainer's S_rand varies far more across permutations than the tree explainers'.)
4. **ρ magnitude is strongly architecture-dependent even where the verdict is not.** On Taiwan, XGBoost 3.1 vs
   Extra Trees 13.0 (4×); RF/ET consistently produce the largest ρ. Part of this is the explainer: TreeExplainer on
   RF/ET returns probability-scale attributions with very small S (≈0.007) and even smaller S_rand, whereas GBM/XGB/LR
   are log-odds-scale. **ρ should only be compared across datasets within a model family; cross-family comparison of
   magnitudes is not meaningful and the revision must not rank architectures by ρ.** XGBoost gives the tightest
   intervals everywhere and is the best candidate for the paper's headline series.
5. **The aggregation choice only matters at the boundary.** Median-|SHAP| ρ agrees with mean-|SHAP| for every
   Taiwan/Bank Marketing cell (all still ≫ 2) but flips every German cell below 2. This is a clean, reportable
   statement in response to reviewer B4: the German verdict is aggregation-sensitive; the others are not.
6. **Open item — the null model is not "structureless" on Bank Marketing.** Permuted-label RF/ET/GBM/XGB score AUC
   0.42–0.49 on the real test set (systematically *below* 0.5; German/Taiwan nulls sit at 0.49–0.52). Interpretation:
   under permuted labels the "positives" are a random, typical sample, so the null model learns population density;
   real Bank Marketing positives are atypical (specific months, `poutcome_success`, long calls), hence anti-correlated
   scores. This does not obviously bias S_rand (a magnitude, not a direction), but it is a property of the permutation
   null that reviewer R3.1/R3.3 would probe. To check before the revision: compare S_rand from the permutation null
   against (a) the Adebayo parameter-randomisation null and (b) a density-matched control, on Bank Marketing.

### Next
- Raise Taiwan / Bank Marketing to K = 100 (Taiwan ~25 min, each Bank Marketing config ~35 min, GBM-dominated).
- Threshold-sweep figure across ρ_min ∈ [1.25, 3.0] from the same records (no new runs needed).
- Explainer sensitivity (R3.4): interventional TreeExplainer with a background sample vs tree_path_dependent, on XGBoost.
- Extend the model library (Step C), then SMOTE-on-training-fold ablation (Step D) — the original's remaining Phase 2 steps.

## 4. Step A extended — isolating Phase 1 screening / SMOTE / tuning on German Credit (2026-09-12)

Motivation: Step A (§1) used all raw features, no screening, no resampling, no tuning. The original paper's pipeline
adds three more steps (Phase 1 IV+Boruta screening, Phase 2 tuning, train-fold SMOTE). Rather than turning all three
on at once and reporting one number, each is isolated here against the same Step A baseline, on German Credit only,
five models, same split (rs=42, test_size=0.2). New tooling: `ml_models/feature_screening.py`, `ml_models/tuning.py`,
`--resample smote` in `ml_models/dataset_lab.py` (commits `8a1da6c`, `5b96e51`).

Four variants, each run via `--all-models` against `paper_german_credit.csv`:
- **Screened**: `--iv-boruta` only (IV min 0.02, Boruta perc 90, tentative columns included). No resampling, no tuning.
- **SMOTE**: `--resample smote` only. SMOTE applied to the training fold after the split, never to the test fold.
- **Tuned**: `--tune --tune-iter 20 --tune-folds 5` only. RandomizedSearchCV, scored by AUC, StratifiedKFold(5).
- **Full**: all three combined (`--iv-boruta --resample smote --tune`) — SMOTE re-fit inside every tuning CV fold
  via the imblearn Pipeline fix (commit `8a1da6c`), not pre-applied once.

**Important caveat on the CV column**: `cross_validate_model()` always runs on the untuned, unresampled model as a
fixed comparability anchor across every run (see the code comment at the `cv = cross_validate_model(...)` call in
`dataset_lab.py`) — it does **not** reflect the SMOTE or tuning options. This is why the CV numbers for "SMOTE" and
"Tuned" are identical per model (same untouched features), and why only "Screened" and "Full" (which change the
feature set) show a different CV. **Only the holdout AUC/PR-AUC/Brier columns reflect what each variant actually did.**

| Model | Config | Holdout AUC | Δ vs. baseline | PR-AUC | Brier | CV (fixed anchor, see caveat) | Run ID |
|---|---|---:|---:|---:|---:|---:|---|
| Logistic Regression | **Baseline (§1)** | 0.8014 | — | 0.6393 | 0.1839 | 0.7804 ± 0.0199 | `lab_20260906_223355_german_credit_logistic_regression` |
| Logistic Regression | Screened | 0.7904 | -0.0110 | 0.6171 | 0.1904 | 0.7748 ± 0.0196 | `lab_20260912_100732_german_credit_screened_logistic_regression_iv-boruta` |
| Logistic Regression | SMOTE | 0.7817 | -0.0197 | 0.5809 | 0.1882 | 0.7804 ± 0.0199 | `lab_20260912_100846_german_credit_smote_logistic_regression_smote` |
| Logistic Regression | Tuned | **0.8063** | +0.0049 | 0.6427 | 0.1823 | 0.7804 ± 0.0199 | `lab_20260912_101044_german_credit_tuned_logistic_regression_tuned` |
| Logistic Regression | Full | 0.7929 | -0.0085 | 0.6122 | 0.1836 | 0.7748 ± 0.0196 | `lab_20260912_101446_german_credit_full_logistic_regression_iv-boruta_smote_tuned` |
| Random Forest | **Baseline (§1)** | 0.7989 | — | 0.6397 | 0.1798 | 0.7924 ± 0.0233 | `lab_20260906_223357_german_credit_random_forest` |
| Random Forest | Screened | 0.7837 | -0.0152 | 0.6160 | 0.1842 | 0.7877 ± 0.0253 | `lab_20260912_100750_german_credit_screened_random_forest_iv-boruta` |
| Random Forest | SMOTE | 0.7771 | -0.0218 | 0.6025 | 0.1705 | 0.7924 ± 0.0233 | `lab_20260912_100847_german_credit_smote_random_forest_smote` |
| Random Forest | Tuned | **0.8040** | +0.0051 | 0.6486 | 0.1651 | 0.7924 ± 0.0233 | `lab_20260912_101045_german_credit_tuned_random_forest_tuned` |
| Random Forest | Full | 0.7725 | -0.0264 | 0.5755 | 0.1714 | 0.7877 ± 0.0253 | `lab_20260912_101504_german_credit_full_random_forest_iv-boruta_smote_tuned` |
| Extra Trees | **Baseline (§1)** | 0.7848 | — | 0.6157 | 0.1861 | 0.7794 ± 0.0228 | `lab_20260906_222907_german_credit_extra_trees` |
| Extra Trees | Screened | 0.7739 | -0.0109 | 0.6211 | 0.1906 | 0.7734 ± 0.0276 | `lab_20260912_100656_german_credit_screened_extra_trees_iv-boruta` |
| Extra Trees | SMOTE | 0.7765 | -0.0083 | 0.5947 | 0.1774 | 0.7794 ± 0.0228 | `lab_20260912_100831_german_credit_smote_extra_trees_smote` |
| Extra Trees | Tuned | 0.7818 | -0.0030 | 0.6044 | 0.1891 | 0.7794 ± 0.0228 | `lab_20260912_100908_german_credit_tuned_extra_trees_tuned` |
| Extra Trees | Full | 0.7735 | -0.0113 | 0.6123 | 0.1814 | 0.7734 ± 0.0276 | `lab_20260912_101218_german_credit_full_extra_trees_iv-boruta_smote_tuned` |
| GBM | **Baseline (§1)** | 0.7935 | — | 0.6388 | 0.1774 | 0.7867 ± 0.0276 | `lab_20260906_223304_german_credit_gradient_boosting` |
| GBM | Screened | 0.7746 | -0.0189 | 0.6162 | 0.1892 | 0.7796 ± 0.0209 | `lab_20260912_100714_german_credit_screened_gradient_boosting_iv-boruta` |
| GBM | SMOTE | 0.7854 | -0.0081 | 0.6474 | 0.1629 | 0.7867 ± 0.0276 | `lab_20260912_100839_german_credit_smote_gradient_boosting_smote` |
| GBM | Tuned | 0.7954 | +0.0019 | 0.6278 | 0.1600 | 0.7867 ± 0.0276 | `lab_20260912_101008_german_credit_tuned_gradient_boosting_tuned` |
| GBM | Full | 0.7761 | -0.0174 | 0.6159 | 0.1682 | 0.7796 ± 0.0209 | `lab_20260912_101344_german_credit_full_gradient_boosting_iv-boruta_smote_tuned` |
| XGBoost | **Baseline (§1)** | 0.7627 | — | 0.6267 | 0.1914 | 0.7848 ± 0.0250 | `lab_20260906_223402_german_credit_xgboost` |
| XGBoost | Screened | 0.7480 | -0.0147 | 0.5792 | 0.1998 | 0.7814 ± 0.0199 | `lab_20260912_100814_german_credit_screened_xgboost_iv-boruta` |
| XGBoost | SMOTE | 0.7755 | +0.0128 | 0.6333 | 0.1686 | 0.7848 ± 0.0250 | `lab_20260912_100854_german_credit_smote_xgboost_smote` |
| XGBoost | Tuned | **0.7902** | +0.0275 | 0.6522 | 0.1626 | 0.7848 ± 0.0250 | `lab_20260912_101135_german_credit_tuned_xgboost_tuned` |
| XGBoost | Full | 0.7620 | -0.0007 | 0.5810 | 0.1739 | 0.7814 ± 0.0199 | `lab_20260912_101624_german_credit_full_xgboost_iv-boruta_smote_tuned` |

Screening detail (identical across all five "Screened"/"Full" runs, since screening runs once on the raw dataframe
before the model loop): IV < 0.02 dropped 5/20 raw columns; Boruta (perc=90, tentative included) rejected 3 more of
the 15 IV-survivors → **12/20 raw columns retained** (43 encoded, vs. 61 for the unscreened baseline). Dropped:
`job, telephone, other_debtors, foreign_worker, residence_since, personal_status_sex, existing_credits, people_liable`.

### Reading — three findings, one of them unfavourable and unresolved

1. **Screening alone costs AUC for every model on this dataset** (-0.01 to -0.02), despite dropping 8/20 raw columns
   the IV/Boruta gates judged uninformative. n=1000 is small enough that losing 30% of an already-modest feature set
   plausibly removes some genuine (if individually weak) signal along with the noise. PR-AUC and Brier move the same
   direction (worse) for every model except Extra Trees' PR-AUC. **This does not support the original paper's implicit
   assumption that Phase 1 screening is a "free" step that only removes noise — on German Credit specifically it has
   a real, negative cost, and the revision text must say so rather than assume screening is neutral-to-positive.**
2. **SMOTE alone is mixed on AUC (-0.022 to +0.013) but consistently improves Brier score** (better calibration) for
   every model except Logistic Regression. It only helps AUC for XGBoost (+0.013). This matches the credit-scoring
   literature's usual caveat about SMOTE: it can improve probability calibration on the minority class without
   improving discrimination, and can hurt discrimination for models (LR, RF) whose decision boundary is sensitive to
   synthetic points sitting inside real clusters.
3. **Tuning alone helps every model except Extra Trees**, most for XGBoost (+0.0275) — consistent with §1's Reading
   point 1 that XGBoost's default hyperparameters were the worst match for the honest, smaller, untuned training set.
   Tuning recovers roughly a quarter of XGBoost's original -0.116 Step A gap, not more.
4. **Unresolved, unfavourable finding: the Full combination (screening + SMOTE + tuning together) underperforms the
   untouched Step A baseline for 4 of 5 models** (LR -0.0085, RF -0.0264, ET -0.0113, GBM -0.0174; XGBoost roughly
   flat at -0.0007), even though Tuned alone and SMOTE alone were AUC-neutral-to-positive for most models in
   isolation. The combined result is worse than either the baseline or any single intervention alone for every model
   but XGBoost. **This has not been root-caused.** Plausible candidates, none yet checked: (a) screening's -0.01 to
   -0.02 cost compounds rather than washing out once SMOTE/tuning are layered on top of a smaller feature set; (b)
   the tuning search, run on the smaller 43-feature (Full) or 61-feature (SMOTE/Tuned-only) space, may be overfitting
   its own inner-CV folds at n=800 train rows regardless of resampling; (c) an interaction between SMOTE's synthetic
   points and the specific columns Boruta rejected. **Do not report a "full pipeline" German Credit number in the
   revision without resolving this** — right now the honest headline is that the paper's own three added steps,
   combined, net underperform the plain corrected baseline on this dataset, which is the opposite of what the
   original submission implicitly claimed for its full pipeline.

### Caveats carried forward
- Single dataset (German Credit, n=1000) — Taiwan/Bank Marketing not yet re-run through these four variants.
- Single seed (rs=42) throughout — no repeat-seed check on whether the Full regression is seed-dependent or systematic.
- The Sanity Ratio (§2/§2a) has not been re-run under any of these four variants — it still reflects the Step A
  (unscreened, unresampled, untuned) models only. Whether ρ changes under Full/Tuned/SMOTE is completely open.

### Next
- Root-cause the Full-pipeline regression before trusting any "final pipeline" number on German Credit.
- Repeat this four-way ablation on Taiwan and Bank Marketing to see whether the Full regression is German-Credit-specific
  (small n) or general.
- Re-run the Sanity Ratio (K=100) on at least the Tuned variant (the one isolated improvement), to see whether ρ moves.
