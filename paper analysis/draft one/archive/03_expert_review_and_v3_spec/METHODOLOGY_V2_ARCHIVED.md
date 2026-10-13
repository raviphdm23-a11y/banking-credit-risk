# Column-Usefulness Methodology — shared across all dataset findings logs

Standing methodology for deciding whether a column is useful for predicting a binary target, used in
`PAK_FINDINGS.md`, `HMEQ_FINDINGS.md`, `GERMAN_CREDIT_FINDINGS.md`, and any future dataset findings log in this
folder. Steps 1-4 written up on 2026-10-07 after being developed ad hoc across the PAK and HMEQ deep dives. Step
5 was revised to v2 on 2026-10-08, during the German Credit analysis, after the v1 approach (greedy
category-by-category combination testing) was found to have two concrete flaws — see "Why Step 5 was revised"
below for the evidence. This is intended as a dataset-agnostic, standardized solution — designed for rigor over
convenience, not scaled back for compute cost or dataset size.

**Not shown anywhere in the Sandbox frontend** — purely a private reference for Claude + the user.

---

## The core design decision: this is an escalation ladder, not a four-way vote

Four tools are used across this process: IV, Cramér's V (chi-square-based), Mann-Whitney U, and model validation
(holdout vs. CV AUC). **These are not four independent opinions to be tallied.** They split into two different
jobs, and within one of those jobs two of the tools are mechanically redundant with each other. Treating them as
equal voters would be wrong — e.g. "3 of 4 agree, so keep the column" is not how this methodology works.

**Job A — does this one column relate to the target, by itself?** Answered by IV, Cramér's V, and Mann-Whitney.
**Job B — does this column add real value in an actual model, combined with others?** Answered only by model
validation. No univariate test, run any number of times, can ever answer a multivariate question — by
construction, each of IV/Cramér's V/Mann-Whitney looks at exactly one column against the target in isolation.

---

## Step 1 — IV + Cramér's V together (cheap first pass)

Compute both. **They are mechanically the same test wearing different clothes** — both work by binning the
column and measuring divergence in target rate across bins. They have agreed on every column tested so far
(e.g. HMEQ's `DEBTINC`: IV 1.267, Cramér's V 0.437, same verdict either way). Running both is not two
independent checks — it is one check counted twice, kept because IV carries the credit-industry-standard
interpretation scale (Siddiqi: <0.02 useless, 0.02–0.1 weak, 0.1–0.3 medium, >0.3 strong) while Cramér's V is the
general statistics effect-size version (<0.1 negligible, 0.1–0.3 weak, 0.3–0.5 moderate, >0.5 strong). Also
record the chi-square p-value, but **p-value alone is never sufficient** — at realistic sample sizes (n in the
thousands to hundreds of thousands across the datasets tested so far), even trivially small real effects clear
p<0.05. p-value answers "is this probably not pure chance," not "is this useful."

## Step 2 — reliability gate: check `min_expected`

Before trusting Step 1's number, check the chi-square test's minimum expected cell count. **Below ~5, the
Cramér's V/IV number cannot be trusted at face value**, regardless of what it says. Two distinct ways this shows
up, both confirmed directly in this project:
- **Too many categories spread over too few rows** (PAK's `PROFESSIONAL_BOROUGH`: 5,056 categories, ~3 rows each,
  `min_expected` 0.26, Cramér's V an inflated 0.342 that a model check proved was fake — see PAK_FINDINGS.md).
- **A skewed count variable with a long, thin tail of rare high values** (HMEQ's `DEROG`/`DELINQ`/`NINQ`: median
  0, max 10–17, `min_expected` 0.20–0.40 — but here the flagged result turned out to be real, confirmed by Step
  3; see HMEQ_FINDINGS.md). Flagged-as-unreliable does not mean "reject" — it means "needs a second opinion."

## Step 3 — escalate to Mann-Whitney U when Step 2 fails

Only run this when Step 2 flags a reliability concern — it is a specialist tool for one specific failure mode,
not a routine fourth check. Rather than binning into a contingency table, it compares the full rank distribution
of the column between the two target groups directly, so it is immune to the sparse-cell problem.

**Hypotheses tested:**
- H₀ (null): the column's distribution is identical between the two target groups — no relationship.
- H₁ (alternative): the distributions differ — a real relationship exists.
A small p-value (conventionally <0.05) rejects H₀.

**Mann-Whitney has its own blind spot: it is powerful for a monotonic/directional shift, but can miss a genuine
non-monotonic (e.g. U-shaped) relationship**, because the shift partially cancels out in rank terms. Confirmed
directly with HMEQ's `CLNO`: chi-square correctly detected a real U-shaped relationship with default (both very
few and very many existing credit lines are riskier than a moderate amount); Mann-Whitney said "not significant"
(p=0.258) because it is blind to that shape. **Mann-Whitney is not a strictly stronger replacement for
chi-square — the two are complementary, each blind to a different pattern.**

## Step 3a — when the reliability gate fails on a nominal (non-ordinal) column, skip Mann-Whitney

Mann-Whitney U requires a column whose values can be meaningfully ranked — valid for continuous and ordinal
columns (counts, ratios, ordered categories), but **not valid for nominal categoricals with no natural order**
(e.g. German Credit's `purpose`: car, education, furniture... have no inherent ranking). Confirmed directly:
`purpose` failed the Step 2 gate (min_expected=2.70, driven by sparse categories like `retraining` n=9), but
Mann-Whitney is not a meaningful escalation for it. **When this combination occurs, escalate directly to Step 5
model validation instead of Step 3** — train/evaluate the column alone and check whether its AUC is
meaningfully above chance (German Credit's `purpose` alone: CV AUC 0.5881 ± 0.0217, clearly above 0.5, roughly
4 standard deviations — confirmed real, not sparse-cell inflation).

## Step 4 — when Step 1 and Step 3 disagree, inspect the actual binned rates

Do not mechanically pick a winner between a reliable-but-disagreeing Cramér's V and Mann-Whitney result (the
`CLNO` case). Print the per-bin default rate table and look at the shape directly — the diagnosis of *why* they
disagree (monotonic vs. non-monotonic) is itself the useful finding, not a tie to be broken by preference.

## Step 5 (v2) — pooled, order-invariant model validation

Model validation (Step 5) is mandatory, not optional — no univariate test (Steps 1-4) can ever answer a
multivariate question, by construction. But **how** Step 5 is run changed on 2026-10-08 — see "Why Step 5 was
revised" below for the two concrete problems with the original (v1) approach.

### Why Step 5 was revised

**Problem 1 — no formal significance test on "did adding a column help."** v1 judged combination value by
eyeballing whether CV AUC moved up or down between two runs. This has no rigor: a small movement could just be
fold-to-fold noise. **Fix:** this project's CV implementation (`trainer.cross_validate_model`) uses a *fixed*
`StratifiedKFold(random_state=42)` whose fold row-assignment depends only on the target column and row count —
**not** on which feature columns are included. That means two runs on the same dataset always use *identical*
fold row-groupings, making every comparison a **paired** comparison. Use a **paired t-test on the 5 fold-level
AUC differences** (or Wilcoxon signed-rank if normality is doubtful at such a small n) rather than comparing
mean±std informally. Confirmed directly on German Credit: comparing Character-only (3 cols) vs. +`employment_since`
gave fold-level differences [+0.0302, +0.0248, −0.0102, +0.0190, +0.0131] — paired t = 2.20, marginally
significant one-tailed (p≈0.046) — a real, if modest, signal, legitimately distinguishable from noise unlike a
naive "mean went up" read would suggest at this sample size.

**Problem 2 — greedy, order-dependent combination testing.** v1 tested categories in a fixed sequence
(Character → Capacity → Capital → Collateral → Conditions) and locked in each category's keep/reject decision
before testing the next. This is a greedy forward-selection path, and greedy forward selection is known to be
**order-dependent**: a column's apparent "additive value" depends on what was already accepted before it, which
is an artifact of testing order, not a property of the column itself. Caught directly on German Credit:
`employment_since` looked nearly useless alone (holdout 0.5417) but became the strongest, most consistent
combination result seen yet once tested *after* three Character columns were already locked in — raising the
question of whether that's genuine complementary signal, or an artifact of the order it happened to be tested in.
**This is the core flaw Step 5 v2 fixes.**

### The v2 procedure

1. **Run Steps 1-4 independently per category, exactly as before** — this part is unaffected and safe to keep
   doing category-by-category, because testing one column against the target in isolation never depends on any
   other column. Use this purely to discard the unambiguously dead columns (not significant at Step 1, or
   confirmed dead after Step 2-4 if flagged) before the expensive step below.
2. **Do not lock in any category's final keep/reject decision from a combination model yet.** Pool every
   survivor from every category — Character, Capacity, Capital, Collateral, Conditions — into one flat candidate
   list, with no category labels attached for the purposes of step 3. Locking in category-by-category here is
   exactly the mistake v1 made.
3. **Run an exact Shapley-value marginal-contribution analysis once, over the entire pooled list together.** For
   n pooled candidates, this means evaluating the model over all 2ⁿ subsets (tractable without approximation for
   realistic pool sizes of 10-15 post-screening columns — 2¹⁵ = 32,768 fast XGBoost fits, not a reason to
   shortcut). This is what makes the result order-invariant: it is the average of a column's marginal AUC
   contribution across *every possible ordering/coalition* of the other pooled columns, not just the one
   Five-C's-driven path v1 happened to walk.

   **Model choice for the value function:** use XGBoost, for consistency with every other step in this
   methodology (univariate ablation checks, the production model itself) — not the textbook default (logistic
   regression, preferred in the classic Shapley-feature-selection literature for its determinism and low
   refitting variance). This is a deliberate, acknowledged deviation; XGBoost adds its own fitting noise across
   tens of thousands of subset refits, which is part of why the per-fold paired significance test below is
   mandatory, not optional, for this step.

   **Folds inside the Shapley computation:** evaluate every subset `S` using the *same* fixed
   `StratifiedKFold(random_state=42)` splits used everywhere else in this methodology (fold assignment depends
   only on the target/row count, not which columns are present — confirmed directly in `trainer.py`), producing
   5 fold-level AUC values `v₁(S)...v₅(S)` per subset rather than one. For a given column being added to subset
   S, compute its marginal contribution **separately per fold** (`v_k(S∪{column}) − v_k(S)` for each fold k),
   then apply the Shapley weighted-subset-average formula once per fold. The result is **5 fold-level Shapley
   values per column**, not one point estimate.
**2a. If the pooled list is too large for exact Shapley, prune by correlation first — not by tightening the
pooling threshold.** Exact Shapley needs `2ⁿ` subset evaluations, so a pool above roughly 15-16 columns
becomes impractical even with the phased/checkpointed approach used for large runs (confirmed directly:
HELOC's initial 20-column pool would need ~2²⁰ ≈ 1,048,575 subsets, dozens of times longer than Taiwan's
already-long 15-column, ~8.7-hour run). The fix is **not** to arbitrarily raise the Step 1 IV/Cramér's V
bar (that would silently exclude genuine, if modest, candidates without justification) — it's to check
pairwise correlation (Spearman) among the pooled candidates and, within any cluster of columns correlated
above ~0.7, **keep only the single strongest individual performer (highest IV from Step 1-4) and drop the
rest as redundant.** This only removes a column when a close substitute is already staying in the pool, so
it addresses genuine multicollinearity rather than cutting real, independent signal. Confirmed directly on
HELOC: 6 correlated clusters (e.g. `NumInqLast6M`/`NumInqLast6Mexcl7days` at Spearman 0.985) let the pool
shrink from 20 to 13 columns by dropping only the weaker member of each pair/cluster.

**2b. If the pool is still too large for exact Shapley even after correlation pruning (2a), switch to
sampled/approximate Shapley — don't keep scaling up exact enumeration.** Added 2026-10-09 after Taiwan's
original 15-column pool (~8.7 hours exact) made clear that even correlation-pruned pools can still be
infeasible for genuinely wide datasets (`lending_club_q12019.csv` has 111 raw columns) or where each
individual model fit is itself slow (very large row counts, e.g. `mortgage.csv`'s 622,489 rows). Exact
Shapley costs `2ⁿ` subset evaluations — a known, fundamental, exponential scaling limit documented
throughout the Shapley-value literature, not specific to this project's implementation.

The standard fix is **permutation sampling** — this project's exact Shapley procedure (Steps 2-3) is
mathematically the same thing Covert, Lundberg & Lee (2020) formalized as **SAGE** (Shapley Additive Global
importancE): applying Shapley values to a *model-performance* value function, exactly this project's
`v(S) = CV AUC using columns S`. SAGE's standard estimator doesn't enumerate all `2ⁿ` subsets — instead, it
samples a chosen number `T` of random column orderings, walks through each ordering adding one column at a
time, records each column's marginal AUC contribution at that point, and averages across all `T` samples.
This gives an **unbiased estimate** of the same Shapley value, with error shrinking at rate `O(1/√T)` — slower
than linear, but a world away from exponential. Implementation: `ml_models/shapley_utils.py`,
`sampled_shapley()`. Reference: Covert, S., Lundberg, S., & Lee, S.-I. (2020). *Understanding Global Feature
Contributions With Additive Importance Measures.* NeurIPS 2020 — see `BIBLIOGRAPHY.md`.

**Practical guidance on when to switch:** exact Shapley remains preferred whenever it's affordable (every
dataset completed so far — German Credit, PAK, HMEQ, GMSC, Taiwan, HELOC — used exact computation, the
pruned pools in Taiwan/HELOC's case) because it gives a floating-point-exact answer, not an estimate. Switch
to sampling once the pool (after 2a pruning) still exceeds roughly 15-18 columns, or whenever individual
model fits are themselves slow enough that even a pruned pool's `2ⁿ` cost is impractical (very large row
counts). `sampled_shapley()`'s default `n_samples=300` is a starting point, not a fixed rule — report the
estimate's standard error (`std/√T`) alongside the result so the reader can judge precision, and increase
`T` if the keep/reject decision for any borderline column is sensitive to it.

**What changes in the decision layer, and why Cohen's d is required (not optional) for sampled mode:**
validated directly against German Credit's known-exact answer (only 5 of 13 columns truly useful) — running
`sampled_shapley()` with `n_samples=300` and relying on BH-corrected p-value alone flagged **all 13** columns
as significant, including ones exact Shapley clearly rejected (e.g. `other_debtors`, true mean contribution
0.0026 AUC). **This is because more samples means more statistical power, and enough power will eventually
call even a trivially small, unimportant effect "significant" — the opposite problem from the exact method's
5-observation significance test, which had too little power to be misled this way.** The fix:
`sampled_shapley()` requires **both** BH-adjusted p < 0.05 **and** Cohen's d (`mean ÷ std`, not `mean ÷ SEM`)
≥ 0.8 (Cohen's 1988 "large effect" convention) before keeping a column. Cohen's d doesn't shrink as sample
size grows the way a p-value does, so it remains a meaningful filter regardless of how many samples are
drawn. Implemented in `shapley_utils.sampled_shapley()`'s `cohens_d_threshold` parameter.

**Validated, accepted accuracy (2026-10-09):** re-running the German Credit validation with the BH+Cohen's-d
rule recovered **11 of 13 correct decisions** (up from 0/13 under BH alone) at `n_samples=300` — critically,
**zero false negatives** (every column exact Shapley kept, sampling also kept) and 2 false positives
(`savings_status`, `credit_amount` kept when exact Shapley rejected them — their Cohen's d, 0.94 and 0.91,
landed just above `purpose`'s 0.90, which *was* correctly kept, so a single scalar threshold can't cleanly
separate them at this sample size). **Accepted as documented behavior**, not a bug to chase further: a
sampled approximation erring toward occasionally keeping 1-2 extra borderline columns is a safe failure
mode for a screening method (never drops a genuinely useful column), and `n_samples` can be increased for a
tighter estimate if a specific borderline decision matters enough to justify the extra compute.

4. **Decide keep/reject via Benjamini-Hochberg-corrected paired significance — not a magnitude/materiality
   threshold.** For each pooled column, run a one-sample paired test (paired t-test, or Wilcoxon signed-rank
   given n=5) on its 5 fold-level Shapley values against the null of zero contribution, producing one raw
   p-value per column. Because many columns (typically 10-15) are tested simultaneously, a flat p<0.05 per
   column is not valid on its own — some genuinely useless columns will clear it by chance alone (the multiple
   comparisons problem). Apply the **Benjamini-Hochberg (BH) procedure** (Benjamini & Hochberg, 1995) across all
   the pooled columns' p-values: sort ascending, compare each to `rank/total × 0.05`, and keep every column up to
   the largest rank that still clears its threshold. BH controls the false discovery rate rather than a fixed
   per-test error rate, and is the standard, well-established choice for exactly this "many candidate features,
   which are real" scenario (preferred over the stricter Bonferroni correction, which would discard real but
   modest signals, especially among correlated credit-risk columns). **No separate magnitude/materiality
   threshold is used** — an invented number like "must add ≥0.01 AUC" has no grounding and was deliberately
   rejected in favor of this statistically principled alternative.
5. **Built-in correctness check, from Shapley's efficiency property:** the sum of every pooled column's average
   Shapley value should reconstruct `v(full pool) − v(empty)` almost exactly, since Shapley values are
   mathematically guaranteed to sum to the total improvement with nothing left over or double-counted. If the
   reconstruction is off, something in the computation is wrong.
6. **Final keep list = pooled candidates surviving the BH-corrected significance test.** Build the final
   modeling dataset from this list — not from five separately-decided category keep-lists.

### Reading the AUC itself — a separate, absolute benchmark

Two different questions get asked of an AUC number and must not be conflated:
- *"Did this column help?"* — answered by the paired comparison above (relative, not absolute).
- *"Is the resulting model actually good?"* — answered by a fixed, absolute scale (commonly attributed to
  Hosmer & Lemeshow): **0.5-0.7 poor, 0.7-0.8 acceptable, 0.8-0.9 excellent, >0.9 outstanding.** Report both every
  time — a column can legitimately "help" (pass the paired test) while the resulting model is still in the
  "poor" band overall, which is itself a useful, honest thing to flag rather than letting a relative improvement
  imply the model is good in absolute terms.

### Feature importance is not self-evidencing

A model's reported feature-importance percentage (e.g. XGBoost's gain-based importance) has no agreed-upon
"good" threshold on its own, and can be non-trivial purely by chance with few features/modest sample size. It is
only trustworthy when backed by the ablation/ Shapley evidence above (with vs. without, or marginal contribution
across coalitions) — never read in isolation. A clean 0% (as seen with PAK's `PROFESSIONAL_BOROUGH` and German
Credit's `foreign_worker`) is unambiguous; anything above that requires the paired-significance check before
being called "real."

## Step 6 — probability calibration (reporting step, not a column-selection step)

Added 2026-10-09, after noticing GMSC's final model had a Brier score *worse* than the trivial "always
predict the base rate" baseline — a model that ranks well (good AUC) but whose raw predicted probabilities
don't mean what they look like they mean. Full literature review in `CALIBRATION_NOTES.md`.

**Why it happens:** every model in this methodology is trained with XGBoost's `scale_pos_weight` to handle
class imbalance — this genuinely improves ranking/AUC (the metric Steps 1-5 are built around), but it works
by training on an artificially rebalanced view of the data, so raw `predict_proba` output reflects that
rebalanced scale, not true real-world odds. The *ranking* stays correct; the *absolute magnitude* of any one
prediction does not.

**What to do about it:** calibrate via `trainer.calibrate_model()` (isotonic regression, via sklearn's
`CalibratedClassifierCV` with internal cross-validation so the calibration curve is learned on held-out
predictions, never leaking from the rows the base model was fit on). Isotonic regression specifically
(not Platt scaling) because the literature consistently found it better suited to tree-based models like
XGBoost, while Platt scaling suits logistic regression better.

**This is a reporting-layer step, not a column-selection step** — it happens *after* Steps 1-5 have already
decided which columns to keep and the final model is built. It doesn't change which columns are kept or the
model's ranking (AUC), only how its output probabilities should be read. Confirmed across all four completed
datasets: calibration cut ECE by 65-98% and brought Brier score below the trivial baseline in every case
where it wasn't already, while AUC moved by at most ~0.007 (within normal fold-to-fold noise) — see
`CALIBRATION_NOTES.md` for the full results table.

**Report both the raw and calibrated model going forward:** the raw model remains correct for anything that
only needs ranking (threshold-based decisions, the Shapley/BH column-selection process itself); the
calibrated model should be used whenever an actual probability is reported to a person.

---

## Summary — the decision rule in one sentence

**Rely on Cramér's V/IV by default; escalate to Mann-Whitney only when the reliability gate (Step 2) fails; when
the two disagree, diagnose the shape rather than vote; screen every category's columns independently with Steps
1-4, but never lock in a combination decision category-by-category — pool every category's survivors and run one
order-invariant Shapley analysis across the whole pool, using the same fixed CV folds throughout; and decide
keep/reject by Benjamini-Hochberg-corrected paired significance, never by an invented magnitude threshold —
because order-dependent greedy combination testing and arbitrary materiality cutoffs are both sources of error,
not convenience shortcuts worth keeping.**
