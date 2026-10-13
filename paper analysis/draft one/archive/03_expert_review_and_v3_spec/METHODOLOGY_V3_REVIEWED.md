# SHARP (Shapley Ranking with Parsimony) — v3 Reviewed and Updated Specification

**Status:** supersedes `METHODOLOGY.md` (v2). Written 2026-10-09 by the external methodological reviewer, in
response to `EXPERT_REVIEW_OF_METHODOLOGY.md`, and intended as the **implementation specification** handed to
the engineer. Every change from v2 is marked and justified; everything retained from v2 is marked as such so
it is not disturbed unnecessarily.

**Reading guide for the engineer:** §9 is the concrete code-change list. §§1-8 are the specification those
changes must satisfy. §10 is the mandatory reporting template. If §9 and §§1-8 ever appear to disagree,
§§1-8 govern.

**Document conventions**
- **[RETAINED]** — carried over from v2 unchanged; do not alter.
- **[CHANGED]** — v2 behaviour replaced; the old behaviour must be removed, not merely supplemented.
- **[NEW]** — did not exist in v2.
- **[DEFERRED]** — specified here, explicitly scheduled for later, not required for the next milestone.

---

## 1. Scope and claims — what this methodology does and does not assert

**[CHANGED — addresses review M1]**

v2 implicitly treated the Shapley stage as a *selection* procedure. It is not one, and the paper must not
claim it is. Shapley values are characterised by efficiency, symmetry, dummy and additivity — a *fair
attribution* solution concept. They do not identify an optimal subset: a redundant-but-informative feature
receives a positive share (so attribution says "keep") even when dropping it costs nothing, and a feature
whose contribution is concentrated in rarely-occurring coalitions can be averaged down below a retention bar
despite being necessary in the chosen model.

The methodology is therefore restructured into **two explicitly separate stages with separate justifications**:

| Stage | Question answered | Tool |
|---|---|---|
| **Importance estimation** (§5) | "How much predictive value is attributable to this feature/group, order-invariantly?" | Shapley over cross-validated predictiveness (SPVIM-style) |
| **Selection** (§6) | "What is the smallest feature set whose performance is acceptable?" | Parsimony curve + pre-declared tolerance + statistical equivalence test |

**Claim the paper is licensed to make:** that category-sequential (greedy) screening produces
order-dependent, artefactual variable retention; that an order-invariant importance estimate plus an explicit
selection rule avoids this; and that four specific, reproducible screening failure modes occur in real credit
data (§11).

**Claim the paper is NOT licensed to make:** that this pipeline selects better subsets than established
alternatives. That requires the benchmark study in §8.2 and must not be asserted before it exists.

**Inference target, stated precisely:** all importance estimates are **population feature importance with
respect to a specified learner and value function** — i.e. "how much cross-validated predictiveness is
recoverable from this feature set, for this learner class, on this population." Not "how much this feature
matters to credit risk in general," and not "how much this feature contributes to a particular fitted model's
predictions." State this in the paper's methods section verbatim.

---

## 2. Correct positioning in the literature

**[CHANGED — addresses review M2]**

v2 claimed equivalence to SAGE. **Remove that claim.** SAGE marginalises absent features out of a *single
fitted model*; this methodology *refits* per subset and uses cross-validated performance. Those are different
estimands.

The correct primary citation is **Williamson & Feng (2020), "Efficient nonparametric statistical inference on
population feature importance using Shapley values," ICML** — the Shapley Population Variable Importance
Measure (SPVIM), which is the refit-per-subset, performance-based construction this methodology implements.
Where SPVIM's influence-function-based confidence intervals can be adopted, prefer them; where the
shadow-feature null (§5.4) is used instead, say so and explain why.

Required citations in the methods section: Williamson & Feng (2020) for the estimand; Covert, Lundberg & Lee
(2020) for SAGE *as a contrast*; Kumar et al. (2020) for the attribution-vs-importance critique; Aas, Jullum
& Løland (2021) for dependent-feature Shapley. Correct the SAGE first-author initial (Ian Covert, "I.", not
"S.").

---

## 3. Stage 0 — Feature eligibility and data governance review

**[NEW — addresses review M4, M5, M6, m6, m11]**

This stage runs **before any statistics**. Its output is a per-column classification table that travels with
every downstream result. No column is silently dropped at this stage; classification drives *warnings and
disclosures*, not exclusions.

### 3.1 Protected and proxy-attribute classification — warn, retain, disclose

**Project decision (confirmed by the data owner, 2026-10-09): protected and proxy-risk attributes are
RETAINED in the analysis for now, with mandatory warning and disclosure.** The justification to be stated in
the paper:

> These are public, de-identified research benchmark datasets analysed for methodological purposes. Protected
> and proxy-risk attributes are retained so that results remain comparable with the substantial published
> literature on these same datasets, which overwhelmingly includes them. No model produced in this work is
> intended for, or suitable for, deployment in a live credit decision. Retention is a methodological choice
> for comparability, **not** an endorsement of using these attributes in practice.

Every column must be tagged with exactly one eligibility class:

| Tag | Meaning | Examples seen in this project |
|---|---|---|
| `permissible` | No known legal/regulatory bar to use in a credit decision | `credit_history`, `DEBTINC`, `NetFractionRevolvingBurden` |
| `prohibited` | Directly prohibited in most consumer-credit jurisdictions | `SEX`, `MARRIAGE`, `personal_status_sex`, `AGE`/`age` (US ECOA/Reg B), `foreign_worker` (national-origin proxy) |
| `proxy_risk` | Not directly prohibited but a recognised proxy for a protected class | `EDUCATION`, geographic fields (`RESIDENCIAL_*`, `*_ZIP_3`, `CITY_OF_BIRTH`), `NACIONALITY` |
| `unclear` | Requires a jurisdictional determination not yet made | document and resolve before any production claim |

**Mandatory behaviour when a `prohibited` or `proxy_risk` column is retained in a final feature set:**
1. A runtime warning is emitted (see §9.1) naming the column and its tag.
2. The dataset's findings log carries the standard disclosure block (§10.3) — not optional, not shortened.
3. Every results table marks such columns with a visible flag (e.g. `AGE ⚠️prohibited`).
4. The model card (§10.2) lists them in a dedicated "regulatory-ineligible features retained" field.

**[DEFERRED]** A fairness-constrained replication (same pipeline, `prohibited` + `proxy_risk` excluded) and
the resulting Gini delta — "cost of compliance" — is a high-value addition and should be scheduled, but is
not required for the next milestone. Also deferred: adverse-impact-ratio testing on the final models.

### 3.2 Sample-selection (accept-only) disclosure

**[NEW — addresses M5]** Every dataset in use contains only applicants *approved* under some prior credit
policy. Feature distributions are therefore truncated on a function of the variables being evaluated, which
systematically **understates** the apparent strength of variables the original underwriter used.

Required: each dataset's findings log states whether the sample is accept-only (or unknown), and **every
"variable X is weak/useless" conclusion is qualified by this**. Specifically:

> **Correction required to existing PAK findings.** The v2 conclusion that `PERSONAL_MONTHLY_INCOME` is
> "surprisingly weak — weaker than most demographics" must be retracted as stated and rewritten. The finding
> is consistent with range restriction induced by the original income-based approval cutoff. The defensible
> statement is: "within the accepted population, income shows little residual discriminatory power — as
> expected where income was used in the original approval decision." Do not present it as a finding about
> income and default.

Cite Hand & Henley (1997) and Crook & Banasik (2004). Where a policy/cutoff variable is observable, run a
sensitivity analysis restricted to sub-populations away from the cutoff.

### 3.3 Point-in-time availability and near-target screening

**[NEW — addresses M6]** Tag every column with its availability class:

| Tag | Meaning |
|---|---|
| `origination` | Observable at application/decision time |
| `behavioural` | Only observable after account opening (account performance history) |
| `near_target` | Behavioural *and* temporally adjacent to the target window — partially definitional |
| `external_score` | Another model's output used as an input |

Two cases in the existing work require explicit treatment:
- **Taiwan `PAY_0`** (repayment status in the month immediately before the target month) is `near_target`. A
  customer two months delinquent in September is close to definitionally a default in October. Its IV of
  0.87 and ~47% model importance reflect label proximity. **Required:** report Taiwan results both with and
  without `PAY_0` (and ideally the whole `PAY_*` block), and state that the headline figure includes a
  near-target feature.
- **HELOC `ExternalRiskEstimate`** is `external_score` (IV 0.955, 36% of model importance). **Required:**
  report HELOC results with and without it; note that including it makes the exercise partly a recovery of an
  existing score.

Mixing availability classes in one feature set is acceptable *if disclosed and scoped* ("behavioural
scorecard") but must not be presented as an application scorecard.

### 3.4 Target definition and performance window

**[NEW — addresses m11]** Record, per dataset: the default definition (90+ DPD / Basel / charge-off / dataset
author's own), the performance window (12/18/24 months), and the observation date if known. Where
undocumented, say "not documented in source" explicitly — do not leave it blank.

### 3.5 Sentinel / leakage audit

**[NEW — addresses m6; partially retains v2 practice]** v2's *principle* was right — never silently drop or
impute a special code without first checking its relationship to the target — and is retained. Added
requirements:

1. Any value that cannot be a literal measurement (GMSC's `96`/`98` in late-payment counts; HELOC's
   `-7`/`-8`/`-9`) must be **recoded as an explicit indicator column**, not left embedded in the numeric
   range. This makes the information attributable to a named player in the Shapley stage instead of leaking
   diffusely through many columns (see also m5).
2. Any sentinel group with an extreme bad-rate lift must be assessed for **label leakage** before retention.
   GMSC's `96`/`98` group (225 rows, 60.4% bad vs 6.6% base rate, identical rows across all three
   late-payment columns) is a specific open item: if these codes encode an account status such as
   charge-off or closed-for-cause, that is outcome information and the rows or the codes must be excluded.
   **Required:** document a data-dictionary basis for retention, or run with/without and report both.
3. Where missingness is shared across many columns (HELOC's ~588-row "no data available" group), extract a
   single explicit `thin_file` indicator.

---

## 4. Stage 1 — Univariate screening

### 4.1 Single primary screening statistic

**[CHANGED — addresses m3]** v2 used `IV ≥ 0.02 OR Cramér's V ≥ 0.1`, a rule adopted after observing which
columns it admitted. Since IV and Cramér's V are monotone transforms of the same χ² statistic, the "OR" is
both redundant and outcome-informed.

**New rule:** **Information Value is the single primary screen, with threshold `IV ≥ 0.02` declared a priori**
(Siddiqi's conventional "weak or better" boundary; the threshold is a published convention, not a tuned
value). Cramér's V continues to be computed and reported **descriptively**, as a cross-check that the two
agree — but it does not enter the decision.

Rationale for choosing IV over Cramér's V as the primary: it is the credit-scoring field's own convention,
its interpretation bands come from the domain literature, and it composes naturally with WOE binning (§4.2).

### 4.2 Binning specification and sensitivity

**[CHANGED — addresses m2]** IV is bin-count dependent and increases with bin count, so v2's fixed 10
quantile bins left the threshold unanchored.

**New requirements:**
1. **Primary binning: monotonic WOE binning** (the credit-scoring standard) for ordinal/continuous columns,
   with a minimum bin size of 5% of rows, merging bins to enforce monotonicity where a monotone relationship
   is supported.
2. **Mandatory sensitivity report:** IV recomputed at 5, 10 and 20 quantile bins alongside the WOE-binned
   value. If the `IV ≥ 0.02` decision **flips** across any of these, the column is tagged
   `binning_sensitive` and escalated to the Stage-1 model check (§4.5) rather than decided on IV.
3. Nominal categoricals: each level is its own bin (retained from v2), with high-cardinality capping declared
   explicitly (current practice: top 51 levels + "other").
4. **Hybrid binning for sentinel codes is RETAINED** from v2 (special codes as their own bins, remaining
   values binned normally) — it was the right call and is now additionally supported by the §3.5 indicator
   extraction.

### 4.3 Reliability gate

**[RETAINED]** χ² minimum expected cell count `min_expected ≥ 5` before the Stage-1 statistic is trusted at
face value. Both documented failure modes are retained, including the distinction between them:
- **sparse-category inflation** (many near-empty categories; inflates only) — a weak-looking result under this
  mechanism needs no rescue; a strong-looking one must be escalated;
- **rare-but-real event** (skewed count with a thin informative tail; bias direction not determined) — always
  escalate.

This was good craft in v2 and the review endorsed it. Keep the diagnostic language in the outputs.

### 4.4 Escalation branches

**[RETAINED]**
- Gate fails, column is **ordinal/continuous** → Mann-Whitney U on raw values. Keep the documented caveat that
  Mann-Whitney is blind to non-monotonic (U-shaped) relationships, with the existing worked example.
- Gate fails, column is **nominal** → Mann-Whitney is invalid; escalate directly to the single-column model
  check (§4.5).
- Stage-1 statistic and Mann-Whitney **disagree** → print the per-bin bad-rate table and diagnose the shape;
  do not pick a winner mechanically.

### 4.5 Single-column model check

**[RETAINED, with one addition]** Train/evaluate the column alone and compare cross-validated performance to
chance. **[CHANGED]** Report the comparison as a Gini with a confidence interval rather than "AUC vs 0.5 by
eye," and require the CI to exclude zero for a "real" verdict.

### 4.6 Output of Stage 1

A per-column table containing: eligibility tags (§3), availability tag (§3.3), IV (WOE-binned) plus the
three sensitivity values, Cramér's V (descriptive), χ², dof, `min_expected`, p-value, escalation path taken,
Mann-Whitney p where applicable, and the screen verdict. Columns passing `IV ≥ 0.02` (or rescued by §4.4/§4.5)
proceed to Stage 2 as **candidates**.

---

## 5. Stage 2 — Order-invariant importance estimation

### 5.1 Estimand and value function

**[CHANGED — addresses M9]**

For a set of players `P` and subset `S ⊆ P`, define `v(S)` as the **repeated** cross-validated predictiveness
of a model trained on exactly the features in `S`.

**Primary value function: cross-validated AUC**, retained for continuity with the six completed datasets, but
with two mandatory robustness replications on at least two datasets (one small-n, one large-n):
1. **Partial AUC** restricted to the plausible operating region (specify the region; absent a business
   cutoff, use the band corresponding to approval rates of 50-90%).
2. **Brier skill score** (loss-based), for which `v(∅)` is the well-defined base-rate prediction rather than a
   stipulated constant, and which makes calibration quality visible *inside* selection.

Report **Kendall's τ** between the importance rankings produced under each value function. If τ is high, the
AUC-based results stand with a robustness note; if low, the loss-based version becomes primary.

**[CHANGED]** `v(∅)`: under AUC, `v(∅) := 0.5` remains a stated *convention* (AUC of a constant predictor is
undefined) — label it as such. Under Brier skill, `v(∅) := 0` by construction.

### 5.2 Value-function learner

**[CHANGED — addresses M9(c) and v2 §7.1]** v2 used XGBoost with fixed hyperparameters for all subsets. Fixed
hyperparameters mis-estimate small-subset performance, and the bias does not cancel in the marginal
differences Shapley is built from.

**New specification — two learners, both reported:**
1. **Primary: penalised logistic regression on monotonic-WOE-transformed inputs.** This is the credit-scoring
   standard form, is near-insensitive to hyperparameter choice, is deterministic, and is the learner the
   Shapley-feature-selection literature typically assumes. It removes the refit-noise objection entirely.
2. **Secondary: XGBoost with fixed hyperparameters** (as v2), to preserve comparability with existing results
   and to capture interaction effects a linear-in-WOE model cannot.

Report both importance rankings and their Kendall's τ. Where they disagree materially on a feature, that
disagreement is a finding (it indicates the feature's value is interaction-dependent) and should be reported,
not averaged away.

**[CHANGED]** Drop `scale_pos_weight` from the value-function learner by default (see m8), with a one-off
ablation confirming ranking performance is materially unaffected. Class-prior reweighting mainly distorts the
probability scale, which Stage 4 then has to repair.

### 5.3 Players: grouped (coalitional) Shapley replaces correlation pruning

**[CHANGED — addresses M7]** v2 pruned correlated clusters by keeping the highest-IV member. That reintroduced
a univariate criterion into the multivariate stage, was itself greedy/path-dependent, and used pairwise ρ
which misses multi-way collinearity.

**New specification:**
1. Compute the pairwise Spearman matrix over Stage-1 candidates. Cluster via **hierarchical clustering on
   distance `1 − |ρ|`** with the cut at `|ρ| = 0.7`. Additionally compute **VIF** and report any variable with
   VIF > 10 (pairwise ρ alone misses joint collinearity).
2. **Treat each resulting cluster as a single Shapley player.** A cluster of size 1 is an ordinary feature.
   This reduces the player count exactly as pruning did — which was pruning's only real motivation — while
   preserving the efficiency property over the complete candidate set and handling redundancy the way Shapley
   is designed to.
3. Compute group-level Shapley values. **Only if a group is retained** by the selection rule (§6) is it
   decomposed internally, by re-running the Shapley computation with that group's members as separate
   players against the other retained groups. This is where the "which member of the cluster do we keep"
   question is answered — multivariately, not by univariate IV.
4. **Mandatory sensitivity analysis:** repeat at cut thresholds `|ρ| ∈ {0.6, 0.7, 0.8}` and report whether the
   retained set changes.
5. Name each cluster descriptively in all outputs (e.g. `delinquency_severity {PercentTradesNeverDelq,
   MaxDelq2PublicRecLast12M, MaxDelqEver}`) so results stay legible.

### 5.4 Null calibration via shadow features — replaces the significance test

**[CHANGED — addresses M3, and removes the Cohen's d rule entirely]**

v2's inference layer is withdrawn: a one-sample t-test on 5 CV-fold Shapley values is invalid (folds share
~75% of training data, so the variance estimate is biased downward — Bengio & Grandvalet 2004; Dietterich
1998), the null distribution of a Shapley-of-CV-AUC statistic for a useless feature is uncharacterised, and
Cohen's `d ≥ 0.8` is a behavioural-science convention with no interpretation here that was, in any case,
chosen after observing which value reproduced one dataset's known answer.

**New specification — empirical null from shadow features (Boruta-style):**

1. For each Stage-1 candidate (or each group, under §5.3), construct a **shadow**: a copy of that column with
   its values randomly permuted across rows. This preserves the marginal distribution exactly and destroys
   the relationship with the target. Use a minimum of **10 shadow players** (if the candidate count is below
   10, generate multiple shadows per candidate to reach 10).
2. Add the shadows to the player set and run the **identical** Shapley computation over the augmented set.
3. The shadows' Shapley values form the **empirical null distribution** for "a player of this type, in this
   dataset, under this learner and value function, that contributes nothing."
4. **Retention bar:** a real player is `importance-confirmed` if its Shapley value exceeds the **95th
   percentile of the shadow distribution**. Report, for every player, its Shapley value, the shadow 95th
   percentile, and the margin between them.
5. **Repeat the whole procedure `R ≥ 20` times with different permutation seeds** and report each player's
   **confirmation frequency** (how often it cleared the bar). This gives a per-feature stability measure for
   free and makes the single-pass fragility of v2's keep-lists visible.

Why this is better than what it replaces: it is assumption-light (no distributional claim about the test
statistic), it requires no multiple-testing correction (the bar is a quantile of an empirical null, not a
family of p-values — so review item m10 dissolves), it is unaffected by the fold-dependence problem, and it
behaves identically in exact and sampled mode, so the exact-vs-sampled discrepancy that motivated the
Cohen's-d patch does not arise.

**Retain BH-corrected p-values and Cohen's d as reported diagnostics only.** They are informative context;
they are no longer decision inputs. Delete the `keep` flag currently driven by them.

### 5.5 Exact vs sampled computation

**[RETAINED, with changes to the switch rule]**
- **Exact** enumeration of all `2ⁿ − 1` subsets when the **player** count (post-grouping, including shadows)
  is ≤ 15.
- **Sampled** permutation estimation otherwise. **[CHANGED]** Report the Monte Carlo standard error for every
  estimate (the code already computes it) and increase `T` until the MC standard error is below one quarter of
  the smallest margin that matters for a retention decision. Do not use a fixed `T = 300` as a default answer;
  `T` is determined by the required precision.
- **[RETAINED]** The efficiency check (Shapley values summing to `v(full) − v(∅)`). **[CHANGED]** Relabel it in
  all outputs as an **implementation audit**, not a validation of statistical accuracy — it will pass to
  machine precision even if every `v(S)` is badly estimated (review m7).

### 5.6 Shared-missingness caveat

**[NEW — addresses m5]** Where missingness is correlated across features, subsets share a latent indicator and
subset evaluations are not independent in the way the Shapley averaging implicitly assumes. §3.5's requirement
to extract explicit indicators (`thin_file` etc.) is the mitigation. Where it cannot be fully mitigated,
state it.

---

## 6. Stage 3 — Selection

**[NEW — addresses M1, M10]** This stage did not exist separately in v2; retention was an artefact of the
significance test. It is now explicit, and its criterion is declared before results are seen.

1. **Eligible set** = players that are `importance-confirmed` (§5.4) at a confirmation frequency ≥ 0.80 across
   the `R` shadow replications.
2. **Rank** the eligible set by Shapley value (descending).
3. **Build the parsimony curve:** for `k = 1 … |eligible|`, fit the model on the top-`k` players and record
   Gini, KS, AUC, partial AUC and Brier, each with a confidence interval. Report the full curve — this is a
   required output, not a diagnostic.
4. **Selection rule (pre-declared):** choose the smallest `k` such that the top-`k` model is **not
   statistically distinguishable** from the full-candidate-pool model by **DeLong's test for correlated ROC
   curves** (DeLong et al., 1988) at α = 0.05, *and* whose **relative Gini loss is ≤ 5%**. If no `k` satisfies
   both, report that no parsimonious subset meets the tolerance — that is a legitimate result, not a failure.
5. **Report the selected set, the curve, and the stopping rationale together.** Never present a single
   selected set without the curve behind it.

**On the existing six datasets, this rule changes the narrative and must be applied retrospectively.** In
Gini terms (the metric the domain actually uses):

| Dataset | Selected Gini | Full-pool Gini | Relative Gini loss | Meets ≤5% tolerance? |
|---|---:|---:|---:|---|
| PAKDD-2009 | 0.2394 | 0.2832 | −15.5% | **No** |
| German Credit | 0.5302 | 0.5708 | −7.1% | **No** |
| Taiwan | 0.5508 | 0.5646 | −2.4% | Yes |
| HELOC | 0.5884 | 0.5900 | −0.3% | Yes |
| HMEQ | 0.8996 | 0.9014 | −0.2% | Yes |
| GMSC | 0.7304 | 0.7304 | 0.0% | Yes |

PAKDD and German Credit must be re-reported: under a pre-declared 5% tolerance their v2 "final" sets are
**not** acceptable parsimonious models, and the honest statement is that no subset of that size meets the
tolerance. Presenting a −15.5% relative Gini reduction as a successful outcome will not survive review.

**Also required:** state what the parsimony is *for*. If the benefit is interpretability, data-acquisition
cost, or model-risk documentation burden, say so and quantify where possible. Do not let small AUC gaps imply
a performance win.

---

## 7. Stage 4 — Probability calibration

**[RETAINED, with two changes]**

Isotonic regression via cross-validated `CalibratedClassifierCV`, so the calibration map is learned on
held-out predictions. Report Brier, ECE and a reliability diagram, for **both** the selected and the
full-pool model.

**[CHANGED]** (a) With `scale_pos_weight` dropped from the value-function learner (§5.2), re-measure
calibration need — much of v2's ECE damage was self-inflicted by the reweighting. (b) Where the Brier-skill
value function (§5.1) is used, calibration quality enters selection directly and this stage becomes a
confirmation rather than a repair.

**[RETAINED]** The reporting discipline: raw scores are valid for ranking decisions; calibrated probabilities
must be used whenever an actual probability is quoted to a person.

---

## 8. Stage 5 — Validation and evidence requirements

### 8.1 Synthetic ground-truth study

**[NEW — addresses M8(c); highest-value single addition]**

Build a generator with known support and run the full pipeline against it:
- informative features, pairwise-correlated at ρ ∈ {0, 0.5, 0.9};
- one exact duplicate of an informative feature (redundancy);
- one non-monotonic (U-shaped) informative feature;
- one interaction-only feature (no marginal signal);
- pure-noise features (at least as many as informative ones);
- a prohibited-attribute analogue correlated with both target and a permissible feature (to test proxy behaviour).

Report **power and FDR curves** versus sample size (n ∈ {1k, 10k, 100k}), versus event rate, and versus `T` for
the sampled estimator. This is what converts §6's "outcomes vary across six datasets" argument — correctly
labelled informal in v2 — into evidence, and it is the only way to substantiate any sensitivity/FDR claim.

### 8.2 Benchmark comparators

**[NEW — addresses M8(a)]** On identical folds, identical preprocessing: full model; LASSO / elastic-net;
recursive feature elimination; Boruta; univariate IV top-`k`; permutation importance top-`k`; **TreeSHAP
global mean |φ| top-`k`**. Report Gini, KS, AUC, Brier, selected-set size and selection stability for each.

The TreeSHAP comparison is not optional: it is exact and polynomial-time for tree ensembles (Lundberg et al.,
2020), so a referee will ask whether it gives the same ranking at a fraction of the compute. If it largely
does, the paper's contribution becomes the Stage 0/Stage 3/null-calibration layers rather than the Shapley
computation — still publishable, but the claim must change accordingly.

### 8.3 Stability selection

**[NEW — addresses M8(b)]** Bootstrap (B ≥ 200) or 10×5 repeated CV over the **entire** pipeline; report
per-feature selection frequency (Meinshausen & Bühlmann, 2010). Required for every dataset, and especially
for German Credit (n = 1,000; 300 bads; full-model fold SD ±0.0315 against marginal contributions of
0.005-0.08 — several v2 decisions cannot be stable at that sample size).

### 8.4 Metrics and statistical comparison

**[CHANGED — addresses M10, m1]**
- **Primary metric: Gini** (domain convention). Report AUC alongside for cross-literature comparability, plus
  KS, partial AUC in the operating band, Brier and ECE.
- **All model comparisons get a test:** DeLong for correlated ROC curves, or a paired bootstrap. No more gap
  columns without inference.
- **[CHANGED]** Replace the Hosmer-Lemeshow 0.5-0.7/0.7-0.8/0.8-0.9 AUC bands — a clinical rule of thumb —
  with domain benchmarks from Lessmann et al. (2015). Note in the paper that an application scorecard at
  Gini 0.40-0.50 is often serviceable, and that HMEQ-style Gini ≈ 0.90 reflects a curated dataset with
  behavioural features, not a realistic application-scoring ceiling.

### 8.5 Out-of-time validation

**[DEFERRED, with a scoping requirement]** No dataset currently in use has a reliable time field, so
out-of-time validation is not presently possible. **Required now:** state this explicitly and scope every
claim to i.i.d. random cross-validation. Do not imply production-readiness. Where the `mortgage.csv` panel
dataset (622,489 loan-months, explicit `time` index) is brought in, it is the natural vehicle for a genuine
out-of-time test and for a survival/competing-risks extension.

### 8.6 Multiplicity and pre-registration

**[NEW — addresses m9]** The study makes many decisions across six datasets, five categories and several
escalation branches, and several thresholds were revised mid-study. Disclose the exploratory character of the
work completed to date, and **pre-specify** the synthetic study (§8.1) and the benchmark study (§8.2) before
running them — including the selection tolerance (§6.4) and the shadow-bar quantile (§5.4).

---

## 9. Implementation specification for the engineer

Ordered by dependency. Items marked **[blocking]** gate the next milestone.

### 9.1 New module: `ml_models/feature_governance.py` **[blocking]**
- `classify_columns(df, target, overrides=None) -> DataFrame` returning per-column `eligibility`
  (`permissible`/`prohibited`/`proxy_risk`/`unclear`) and `availability`
  (`origination`/`behavioural`/`near_target`/`external_score`) tags.
- Ship a maintained keyword/column-name mapping for the known cases (`SEX`, `MARRIAGE`, `AGE`, `age`,
  `personal_status_sex`, `foreign_worker`, `EDUCATION`, `NACIONALITY`, `*ZIP*`, `*CITY*`, `*BOROUGH*`,
  `*STATE*`, `PAY_0`, `ExternalRiskEstimate`), overridable per dataset.
- `warn_on_retained_ineligible(selected_cols, tags)` — emits a `UserWarning` per retained
  `prohibited`/`proxy_risk` column. Must fire from the final-model build path and from report generation.
- `disclosure_block(tags) -> str` producing the §10.3 text for insertion into findings logs.
- Columns are **never dropped** by this module.

### 9.2 `ml_models/feature_screening.py` **[blocking]**
- Add monotonic WOE binning (`woe_bin(series, y, min_bin_frac=0.05, enforce_monotonic=True)`).
- `compute_iv` gains a `binning=` argument (`'woe'` | `'quantile'`) and a `bins=` argument; add
  `iv_sensitivity(series, y) -> {'woe':…, 'q5':…, 'q10':…, 'q20':…}` plus a `binning_sensitive` flag when the
  `IV ≥ 0.02` verdict flips across them.
- Remove the `IV ≥ 0.02 OR Cramér's V ≥ 0.1` composite rule from any decision path; Cramér's V becomes
  report-only.
- Add `extract_sentinel_indicators(df, sentinel_values)` returning the recoded frame plus new indicator
  columns, and `thin_file_indicator(df)` for shared-missingness groups.

### 9.3 `ml_models/shapley_utils.py` — substantial rework **[blocking]**
- **Players abstraction:** accept `players` as a list of column *groups* (`List[List[str]]`), not just
  columns. All subset logic operates on groups.
- **Clustering helper:** `cluster_players(X, threshold=0.7, method='hierarchical')` on distance `1−|ρ|`
  (Spearman), returning named groups; plus `vif_report(X)`.
- **Shadow features:** `make_shadows(X, n_shadows=10, random_state=...)` (per-column permutation) and
  integration so shadows are added to the player set for the run.
- **Null calibration:** `shadow_bar(shadow_shapley_values, quantile=0.95)`; per-player
  `importance_confirmed` flag and `confirmation_frequency` across `R ≥ 20` replications.
- **Remove** the `keep` flag driven by BH p-value and Cohen's d. Retain both as reported diagnostic fields.
- **Pluggable value function:** `value_fn` parameter supporting `'auc'`, `'partial_auc'` (with a band
  argument) and `'brier_skill'`; correct `v(∅)` per metric.
- **Pluggable learner:** `learner` parameter supporting `'woe_logistic'` (penalised logistic on WOE-transformed
  inputs — new, becomes primary) and `'xgboost'` (existing, secondary). Drop `scale_pos_weight` by default.
- **Repeated CV:** replace single 5-fold with repeated stratified CV (default 5 folds × 5 repeats) for every
  `v(S)` evaluation.
- Keep: subset caching, checkpointing/resumability, phased execution, Monte Carlo SE reporting.
- Relabel the efficiency check output as `implementation_audit`.
- `T` selection: add `target_mc_se` so sampled mode increases `T` until the MC standard error meets the
  required precision rather than stopping at a fixed count.

### 9.4 New module: `ml_models/selection.py` **[blocking]**
- `parsimony_curve(X, y, ranked_players, ...)` returning per-`k` Gini/KS/AUC/pAUC/Brier with CIs.
- `delong_test(y, proba_a, proba_b)` for correlated ROC comparison.
- `select_parsimonious(curve, max_relative_gini_loss=0.05, alpha=0.05)` implementing §6.4, returning the
  chosen `k`, the rationale, and a flag when no `k` meets the tolerance.

### 9.5 `ml_models/trainer.py`
- `scale_pos_weight` becomes opt-in (default off) with the ablation recorded.
- Keep `calibrate_model` / `evaluate_calibration`; add reliability-diagram output and apply to both selected
  and full-pool models.
- Retain the existing GPU/CPU device auto-selection work unchanged.

### 9.6 New module: `ml_models/benchmarks.py`
- Comparators per §8.2 on shared folds: `lasso_select`, `elasticnet_select`, `rfe_select`, `boruta_select`,
  `iv_topk`, `permutation_topk`, `treeshap_topk`, `full_model`.
- Common return shape so results drop straight into the §10.1 table.

### 9.7 New module: `ml_models/synthetic_validation.py`
- Generator per §8.1 and a harness producing power/FDR curves across n, event rate and `T`.

### 9.8 Reporting
- Model card emitter (§10.2) and the disclosure block (§10.3) wired into every findings log.
- Every results table gains the eligibility/availability flag columns.

### 9.9 Retrospective re-runs required once 9.1-9.4 land
- Re-report PAKDD and German Credit against the §6 selection tolerance (both currently fail it).
- Rewrite the PAK income conclusion per §3.2.
- Taiwan and HELOC: add the with/without `PAY_0` and with/without `ExternalRiskEstimate` variants (§3.3).
- GMSC: resolve the `96`/`98` leakage question (§3.5).
- All six: add stability-selection frequencies (§8.3) and Gini/KS/DeLong reporting (§8.4).

---

## 10. Mandatory reporting templates

### 10.1 Per-dataset results table (replaces v2's "Gap" table)

| Field | Required content |
|---|---|
| Dataset, rows, raw columns | — |
| Target definition, performance window | Or "not documented in source" |
| Sample type | accept-only / through-the-door / unknown |
| Players after clustering | Count, with named groups |
| Shadow bar | 95th percentile of shadow Shapley distribution |
| Importance-confirmed players | Count, with confirmation frequency each |
| Selected set | Size, members, with eligibility/availability flags |
| Parsimony curve | Full curve, not just the selected point |
| Metrics | Gini (primary), KS, AUC, partial AUC, Brier, ECE — selected and full-pool |
| Statistical comparison | DeLong p-value, selected vs full-pool |
| Relative Gini loss | And whether it meets the pre-declared tolerance |
| Stability | Selection frequency per feature (B ≥ 200) |
| Learner concordance | Kendall's τ, WOE-logistic vs XGBoost rankings |
| Value-function concordance | Kendall's τ across AUC / pAUC / Brier-skill |
| Compute | Model fits, wall-clock, MC SE if sampled |

### 10.2 Model card (per final model)
Intended use and explicit non-use statement; feature list with eligibility and availability tags;
**regulatory-ineligible features retained** (dedicated field); near-target / external-score features;
sample-selection caveat; target definition and window; performance (Gini/KS/AUC/Brier/ECE) with CIs;
calibration method; known limitations; reproducibility block (seeds, library versions, data provenance).

### 10.3 Standard disclosure block (verbatim, where ineligible features are retained)

> **Regulatory eligibility disclosure.** This analysis retains features that are prohibited or
> proxy-prohibited inputs to consumer credit decisions in major jurisdictions (listed in the model card).
> They are retained because these are public research benchmark datasets and their inclusion preserves
> comparability with the published literature on the same data. No model in this work is intended or suitable
> for deployment in a live credit decision. Retention is a methodological choice for comparability and is not
> an endorsement of such use. A fairness-constrained replication excluding these features is planned.

---

## 11. The four diagnostic findings to foreground

**[NEW framing — addresses review m15]** The most defensible contributions here are the concrete, reproducible
failure modes, not the pipeline. Structure the paper around these, with the pipeline as the vehicle:

1. **Category-sequential (greedy) screening retains artefactual variables** — demonstrated on German Credit
   (two columns additive given `credit_history`, null against the full pool) and PAKDD.
2. **Sparse-cell inflation of χ²-family effect sizes** — a high-cardinality location field at Cramér's V =
   0.342 collapsing to Gini ≈ 0.06 under model validation.
3. **Rank tests are blind to non-monotonic relationships** — a genuinely U-shaped credit-lines/default
   relationship detected by χ² and missed by Mann-Whitney.
4. **Significance-based Shapley selection degenerates as evidence accumulates** — the same pipeline, with
   more permutation samples, confirms *every* candidate, because power eventually detects arbitrarily small
   true effects. This is a general caution about significance testing of importance measures and is, in my
   judgement, the most broadly interesting of the four.

---

## 12. Limitations that remain after v3

State these plainly in the paper; they are not resolved by this revision.

1. **Model-conditionality.** Importance is defined relative to a learner. v3 mitigates by reporting two
   learners and their concordance, but does not eliminate the dependence.
2. **Accept-only samples.** Disclosed (§3.2) and qualified, but not corrected — no reject inference is
   performed.
3. **No out-of-time validation** until the panel dataset is brought in (§8.5).
4. **Regulatory-ineligible features retained by project decision** (§3.1), with the fairness-constrained
   replication deferred.
5. **Shadow-feature nulls are learner- and dataset-specific**, not a distribution-free guarantee; they
   characterise "no signal under this setup," which is the relevant null but not a universal one.
6. **Grouped Shapley answers questions about groups**; within-group attribution is only resolved for retained
   groups, and group definitions depend on the clustering threshold (sensitivity-tested, not eliminated).
7. **Five C's framing remains presentational.** v3 keeps it as data-description scaffolding only. Either make
   it load-bearing (test category-blind vs category-aware screening) or reduce it to a sentence — do not leave
   an inconsistently-applied decorative element in a methods paper.
8. **Public benchmark datasets only**, all of modest size by portfolio standards. Scope claims accordingly.

---

## 13. Reference list for the methods section

Shapley / importance: Williamson & Feng (2020, ICML — SPVIM, the estimand); Covert, Lundberg & Lee (2020,
NeurIPS — SAGE, for contrast); Kumar, Venkatasubramanian, Scheidegger & Friedler (2020, ICML — attribution vs
importance); Aas, Jullum & Løland (2021, *Artificial Intelligence* 298 — dependent features); Lundberg & Lee
(2017, NeurIPS); Lundberg et al. (2020, *Nature Machine Intelligence* — TreeSHAP).

Selection / stability / CV inference: Meinshausen & Bühlmann (2010, JRSS-B — stability selection); Kursa &
Rudnicki (2010, *J. Stat. Software* — Boruta/shadow features); Bengio & Grandvalet (2004, JMLR — CV variance);
Dietterich (1998, *Neural Computation*); Nadeau & Bengio (2003, *Machine Learning*); Benjamini & Yekutieli
(2001, *Annals of Statistics*) if BH diagnostics are retained.

Credit scoring: Lessmann, Baesens, Seow & Thomas (2015, EJOR — benchmark conventions); Baesens et al. (2003,
JORS); Thomas, Edelman & Crook, *Credit Scoring and Its Applications* (SIAM); Siddiqi, *Credit Risk
Scorecards* (Wiley — IV/WOE conventions); Hand & Henley (1997, JRSS-A — reject inference review); Crook &
Banasik (2004, *J. Banking & Finance* — reject inference); Hand (2009, *Machine Learning* — the AUC critique);
DeLong, DeLong & Clarke-Pearson (1988, *Biometrics*); Dumitrescu, Hué, Hurlin & Tokpavi (2022, EJOR);
Gunnarsson et al. (2021, EJOR).

Calibration: Niculescu-Mizil & Caruana (2005, ICML); Zadrozny & Elkan (2002, KDD); Platt (1999).

Fairness / regulatory: Hardt, Price & Srebro (2016, NeurIPS); Chouldechova (2017, *Big Data*); Barocas, Hardt
& Narayanan, *Fairness and Machine Learning*.

**Verify every citation against the original before submission** — initials, year and venue in particular.
Two flagged as less certain in the review: a Szepannek-et-al. paper on transparency/auditability of ML in
credit scoring (JORS, c. 2022), and the precise attribution of the AUC interpretation bands commonly credited
to Hosmer & Lemeshow (being removed in v3 regardless, per §8.4).
