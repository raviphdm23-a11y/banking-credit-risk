# Column-Selection Methodology for Credit Risk Models — Summary for Expert Review

**Prepared:** 2026-10-09
**Purpose of this document:** self-contained summary for review by a domain expert (credit risk modeling,
applied ML/statistics). Written to stand alone — the reviewer has no access to the underlying codebase or
prior working sessions, only what is stated here. Please flag gaps, unjustified choices, or places where a
more established alternative exists; honesty about limitations is explicitly wanted over a defensive summary.

**Context:** this methodology was developed as part of rebuilding a credit-scoring feature-selection pipeline
for an academic paper revision (originally an IEEE TAI submission on explainability/feature selection in
credit risk, currently being rebuilt on more defensible statistical footing). The methodology has been
applied end-to-end to 6 public credit-risk datasets so far (German Credit, PAKDD-2009, HMEQ, GMSC, Taiwan UCI
Credit Card, FICO HELOC), each independently, with results that diverge meaningfully from dataset to dataset
(described below) — intended as evidence the methodology adapts to genuine data structure rather than
producing a fixed answer regardless of input.

---

## 1. Problem statement

Given a credit-risk dataset (binary target: default/no-default, or equivalent), decide **which raw columns
are genuinely useful predictors**, in a way that is:
1. Statistically rigorous at each step (not relying on p-values alone at realistic sample sizes, where
   trivial effects are routinely "significant").
2. **Order-invariant** — a column's "usefulness" must not depend on the arbitrary sequence in which
   candidate columns happen to be tested or added to a model.
3. Reproducible and auditable (fixed random seeds, paired statistical comparisons wherever possible, every
   numeric claim traceable to a specific recorded model run).

The "Five C's of Credit" (Character, Capacity, Capital, Collateral, Conditions) is used as an organizing,
domain-driven scaffold for grouping raw columns before testing — purely descriptive/presentational, not
itself a statistical step, and does not influence any keep/reject decision.

---

## 2. Why this methodology exists — the flaw in the first version

The first version of this pipeline (informally, "v1") screened columns within each Five C's category
independently (fine), then tested combinations in a **fixed, greedy sequence**: lock in Character's
keep-list, then test whether Capacity's survivors add value *given Character is already fixed*, then
Capital given Character+Capacity, etc.

This is a greedy forward-selection procedure, and it has a well-known failure mode: **a column's apparent
marginal value depends on what was already in the model when it was tested**, which is an artifact of
*testing order*, not a property of the column. This was caught directly and concretely on the German Credit
dataset: two demographic columns (`personal_status_sex`, `other_debtors`) looked clearly additive when
tested after `credit_history` was already locked in (CV AUC moved from 0.6188 to 0.6310), but when later
re-tested against the *complete* pool of candidates (not just the ones that happened to be tested earlier),
their true marginal contribution was statistically indistinguishable from zero (p=0.335 and 0.571 after
correction). The same order-sensitivity was independently confirmed on the PAKDD dataset, where a column
(`OCCUPATION_TYPE`) that v1 had marked "useful" failed to clear even the univariate screening bar once a
consistent, non-cherry-picked threshold was applied.

This motivated replacing the greedy sequential procedure with an **order-invariant one based on Shapley
values** (below).

---

## 3. Stage 1 — univariate screening (per column, independent of all others)

For each raw column against the binary target:

1. **Information Value (IV)** and **Cramér's V**, both derived from the same chi-square contingency-table
   statistic (binned for continuous columns), reported on their respective conventional interpretation
   scales (Siddiqi for IV: <0.02 useless, 0.02–0.1 weak, 0.1–0.3 medium, >0.3 strong; general effect-size
   convention for Cramér's V: <0.1 negligible, 0.1–0.3 weak, 0.3–0.5 moderate, >0.5 strong). These two are
   treated as **one check, not two independent votes** — they are mechanically the same statistic rescaled
   two different ways, and have agreed on every column tested across all 6 datasets so far.
2. **Reliability gate**: the chi-square test's minimum expected cell count (`min_expected`) must clear ~5
   before Step 1's number is trusted at face value. Two distinct failure modes were found and distinguished:
   - **Sparse-category inflation** (too many categories spread over too few rows) — confirmed to produce
     spuriously large effect sizes. Example: a high-cardinality location column in the PAKDD dataset showed
     Cramér's V = 0.342 (apparently "moderate," rivaling the dataset's best predictor), but a direct
     model-validation check (see Stage 2) showed it was barely above chance (holdout AUC 0.53) — the
     statistic was an artifact of ~5,000 categories averaging 3 rows each.
   - **Skewed count variable with a thin tail** (e.g. a "number of 90-day-late payments in 2 years" column
     where >95% of values are 0) — here the flagged-as-unreliable result turned out to be **genuinely real**
     on independent escalation (below), the opposite resolution from the first failure mode. The two cases
     are distinguished by checking whether the underlying mechanism is "too many near-empty categories"
     (which only inflates) vs. "a genuinely rare but informative event" (direction of bias unclear without
     further checking).
3. **Escalation when the gate fails, on ordinal/continuous columns**: Mann-Whitney U test on the raw values
   (rank-based, immune to the sparse-cell problem). Explicitly noted and demonstrated as having its own blind
   spot — it is powerful for monotonic shifts but can miss a genuine non-monotonic (U-shaped) relationship.
   This was proven directly: a column ("number of existing credit lines") showed a real U-shaped
   relationship with default (both very few and very many lines were riskier than a moderate number);
   chi-square/Cramér's V correctly flagged it as related, Mann-Whitney said "not significant" because the
   rank-based test's directional assumption cancels out across the two tails of the U-shape.
4. **Escalation when the gate fails, on nominal (non-orderable) columns**: Mann-Whitney is invalid here (it
   requires rankable data). The procedure escalates directly to a single-column model-validation check
   instead (train/evaluate a model on that one column, compare CV AUC to chance) — resolved correctly on at
   least one case where the univariate test's own assumptions clearly didn't apply (a "loan purpose"
   categorical column with no natural order).
5. **Disagreement resolution**: when the gate-reliable chi-square-family result and Mann-Whitney disagree,
   the raw binned default-rate table is inspected directly to diagnose *why* (monotonic vs. non-monotonic
   shape), rather than mechanically picking whichever test "wins."

**Pooling criterion**: a column proceeds to Stage 2 if it clears the reliability gate and satisfies
`IV ≥ 0.02 OR Cramér's V ≥ 0.1` (an "or," not "and" — either scale clearing its own conventional threshold is
sufficient; this was specifically chosen after finding at least one real column that cleared the IV
threshold clearly while falling just short of Cramér's V's, and vice versa in another case).

---

## 4. Stage 2 — order-invariant combination testing (Shapley values)

### 4.1 Rationale

Univariate tests, by construction, can never answer whether a column adds value *given the others already
present* — that is an inherently multivariate question. The chosen tool is the **Shapley value** from
cooperative game theory, applied to a model-performance value function: for any subset `S` of the pooled
candidate columns, define `v(S)` = 5-fold cross-validated AUC of an XGBoost classifier trained on exactly
those columns (`v(∅) := 0.5`, chance). A column's Shapley value is its AUC contribution, averaged fairly
across **every possible subset of the other columns it could be combined with** — not just the one path a
greedy procedure happened to walk. This specific construction (Shapley values applied to a model-performance
value function) is formally equivalent to **SAGE** (Covert, Lundberg & Lee, NeurIPS 2020) — see §4.4.

### 4.2 Exact computation (preferred whenever tractable)

For a pool of `n` candidates, exact computation evaluates `v(S)` for all `2ⁿ − 1` non-empty subsets. This has
been run to completion, exactly, on 6 datasets with pool sizes 4–20 (post-pruning 12–13 for the two largest),
using the project's fixed `StratifiedKFold(random_state=42)` for every subset evaluation — since fold
assignment depends only on the target column and row count, not on which features are present, every
subset's AUC is directly comparable across subsets (a paired structure), and runs were checkpointed/resumable
and in some cases executed in phases over several hours of wall-clock time for the largest pools.

A built-in **correctness check** exploits Shapley's efficiency property: the sum of all columns' Shapley
values must reconstruct `v(full pool) − v(∅)` exactly. This was confirmed to floating-point precision
(typically 1e-16-level agreement) on every exact run completed.

### 4.3 Correlation-based pre-pruning (when the pool exceeds ~15-16 columns)

Exact Shapley's `2ⁿ` cost becomes impractical beyond roughly 15-16 candidates. Rather than tightening the
Stage-1 pooling threshold arbitrarily (which would silently discard real signal without justification), the
pool is reduced by **removing genuine redundancy**: pairwise Spearman correlation is computed among pooled
candidates, and within any cluster of columns correlated above 0.7, only the single highest-IV member is
kept. This is applied via a **greedy, iterative** procedure (highest remaining correlated pair first, drop
the weaker-IV member, re-evaluate, repeat) rather than naive transitive-closure clustering — the iterative
version was specifically verified not to over-collapse a correlated *chain* of variables (e.g. six
sequential monthly repayment-status columns, where adjacent months correlate strongly but distant ones less
so) into a single survivor; it correctly retained three well-spaced representatives spanning the time range
instead of collapsing the whole chain to one column.

### 4.4 Sampled/approximate Shapley (when pruning still isn't enough)

For pools still too large after pruning (e.g., a 111-raw-column dataset not yet processed), or where
individual model fits are themselves too slow (very large row counts) for `2ⁿ` evaluations regardless of
`n`'s size, the methodology falls back to **permutation-sampling Shapley** (SAGE's standard estimator):
sample `T` random orderings of the pooled columns, walk each ordering adding one column at a time, record
each column's marginal AUC contribution at that point, and average across all `T` samples. This gives an
unbiased estimate with error `O(1/√T)`.

**A significant pitfall was found and corrected during validation of this fallback**: the decision rule used
for exact Shapley (Benjamini-Hochberg-corrected significance on a paired test) does **not** transfer safely
to the sampled regime. Validated directly by re-running sampled Shapley (T=300) on a dataset where the exact
answer was already known (German Credit, 13 pooled candidates, 5 truly useful by exact computation):
relying on BH-significance alone flagged **all 13** columns as "significant," including ones confirmed
useless by the exact method — because with 300 samples, the test has enough statistical power to detect even
a trivially small, practically meaningless true effect as "significantly different from zero." (The exact
method's test, by contrast, only had 5 observations — fold-level values — giving it much less power, which
had been inadvertently functioning as an implicit, uncontrolled filter against small effects.)

**Fix**: require **both** BH-significance **and** a standardized effect size (Cohen's d = mean ÷ standard
deviation of the sampled marginal contributions, *not* mean ÷ standard error) above the conventional "large
effect" threshold (d ≥ 0.8, Cohen 1988) before keeping a column. Cohen's d does not shrink as sample size
grows (unlike a p-value), so it remains a meaningful filter regardless of `T`. Re-validated against the same
known-answer dataset: 11 of 13 decisions now match the exact result, with **zero false negatives** (no
genuinely useful column was ever dropped) and 2 false positives (two borderline columns retained that the
exact method rejected, differing by Cohen's d of ~0.04 from a correctly-kept column — the residual
imprecision of a 300-sample approximation, not a logic error). This is explicitly documented as accepted,
disclosed behavior, not treated as a solved problem — more samples would tighten it further at proportionally
increasing compute cost.

### 4.5 Decision rule and reporting

- Keep a column only if it clears the (BH-corrected, and for sampled mode, also Cohen's-d-gated)
  significance test from the pooled analysis — never an arbitrary/invented magnitude threshold like "must
  add ≥0.01 AUC."
- Two distinct questions about any resulting AUC number are kept separate and never conflated: "did this
  column help" (a relative, paired-comparison question) vs. "is the resulting model good" (an absolute
  question, judged against a fixed scale — Hosmer-Lemeshow convention: 0.5-0.7 poor, 0.7-0.8 acceptable,
  0.8-0.9 excellent, >0.9 outstanding).
- Feature-importance percentages from the fitted model (e.g. XGBoost's gain-based importance) are never
  trusted in isolation — only when corroborated by the Shapley/ablation evidence above.

---

## 5. Stage 3 — probability calibration (reporting layer, downstream of column selection)

Every model in this pipeline uses XGBoost's `scale_pos_weight` to handle class imbalance, which improves
ranking (AUC) — the metric the entire column-selection procedure above optimizes for — but systematically
distorts the *absolute* scale of predicted probabilities (the model is effectively trained on an
artificially rebalanced view of the class distribution). This was caught concretely: one dataset's final
model had a Brier score *worse* than the trivial "always predict the base rate" baseline, despite good AUC
(0.865).

**Fix**: isotonic-regression calibration (via scikit-learn's cross-validated `CalibratedClassifierCV`, so the
calibration mapping is learned on held-out predictions, never the rows the base model was fit on). Isotonic
regression was chosen over Platt scaling specifically because the literature consulted found it better
suited to tree-ensemble models; Platt scaling is generally preferred for linear/logistic models instead.

Applied to all 6 completed datasets: Expected Calibration Error (ECE) improved by 65-98% in every case
(two datasets' raw models had been worse-than-trivial-baseline on Brier score; both corrected to clearly
better than baseline), while AUC moved by at most ~0.007 in either direction (within normal cross-validation
fold-to-fold noise) — i.e., calibration fixes the absolute probability scale without affecting the ranking
quality the column-selection stages were built around.

---

## 6. Results across datasets completed so far

| Dataset | Rows | Raw columns | Columns kept | Final CV AUC | Full-column baseline CV AUC | Gap |
|---|---:|---:|---:|---:|---:|---:|
| German Credit | 1,000 | 20 | 5 | 0.7651 ± 0.0227 | 0.7854 ± 0.0315 | −0.0203 |
| PAKDD-2009 | 50,000 | 51 | 4 | 0.6197 ± 0.0031 | 0.6416 ± 0.0018 | −0.0219 |
| HMEQ | 5,960 | 12 | 11 | 0.9498 ± 0.0053 | 0.9507 ± 0.0042 | −0.0009 |
| GMSC | 149,391 | 10 | 10 | 0.8652 ± 0.0019 | 0.8652 ± 0.0019 | 0.0000 |
| Taiwan UCI Credit Card | 30,000 | 23 | 12 (pruned pool) | 0.7754 ± 0.0046 | 0.7823 ± 0.0049 | −0.0069 |
| FICO HELOC | 10,459 | 23 | 13 (pruned pool) | 0.7942 ± 0.0069 | 0.7950 ± 0.0065 | −0.0008 |

**Interpretive note on variety of outcomes**: the methodology's conclusions differ substantially by dataset
— from "keep almost nothing" (PAKDD, 4 of 51 raw columns, mostly a noisy real-world extract with several
high-cardinality location fields that looked statistically powerful but were confirmed fake via
model-validation) to "keep nearly everything" (GMSC, 10 of 10; HMEQ, 11 of 12 — both curated datasets with
little genuine redundancy). This variation is treated as evidence the procedure is responsive to actual data
structure rather than producing a fixed-shape answer regardless of input — though this is an informal
argument, not a formal validation against synthetic ground truth (see §7).

---

## 7. Known limitations and open questions (not resolved, explicitly flagged for review)

1. **Model choice for the Shapley value function is XGBoost throughout**, not the textbook default
   (logistic regression, generally preferred in the classic Shapley-feature-selection literature for
   determinism/low refitting variance). This was a deliberate choice for consistency with the production
   model type used elsewhere in the broader project, but it means every subset evaluation carries XGBoost's
   own fitting noise across potentially tens of thousands of refits, and the resulting "useful column" list
   is to some extent **model-conditional** — a different model class might assign different marginal values,
   especially for features whose usefulness depends on interactions XGBoost's tree structure can exploit but
   a linear model cannot (or vice versa).
2. **No comparison against alternative feature-selection baselines** (e.g., L1/Lasso-based selection,
   recursive feature elimination, Boruta, mutual information ranking) has been run. The methodology's
   relative merit is argued from first principles (order-invariance, statistical rigor at each step) and
   from internal consistency checks (the Shapley efficiency property, validation against a known-exact
   sampled-vs-exact comparison), not from a head-to-head benchmark against established alternatives.
3. **No out-of-time validation.** All cross-validation is i.i.d. random `StratifiedKFold` — there is no
   test of whether a selected feature set remains stable or predictive across a genuine time split (e.g.,
   train on one vintage, test on a later one), which matters materially for real-world credit risk models
   given known population and macroeconomic drift. The datasets used are mostly static, de-identified
   research extracts without reliable time fields, which is a real constraint, not just an oversight, but it
   limits how strongly any claim here should be read as applying to a live production scoring context.
4. **The correlation-pruning threshold (Spearman > 0.7) and the sampled-Shapley Cohen's d threshold (0.8)
   are both conventional, literature-grounded choices, not derived from or tuned to this project's specific
   data.** This is intentional (avoiding the appearance of cherry-picking a threshold to produce a desired
   answer), but it also means neither threshold has been stress-tested for sensitivity — e.g., it is not yet
   known how much the final keep-lists would change under a 0.6 or 0.8 correlation-pruning threshold instead
   of 0.7.
5. **Benjamini-Hochberg's independence/positive-dependence assumption.** BH correction is applied across
   pooled candidates that, even after correlation pruning, may retain some residual dependence structure.
   BH is known to remain valid under positive regression dependence (Benjamini & Yekutieli, 2001), which
   plausibly covers this setting, but this has not been explicitly verified for the specific dependence
   structure present in any of these datasets.
6. **Five C's categorization is informal and somewhat inconsistent across datasets** (e.g., `age` was
   grouped under "Character" in one dataset and "Conditions" in another, by local judgment rather than a
   fixed rule). This does not affect any statistical decision (the pooling/Shapley stages are
   category-agnostic), but it means the categorization itself would not reproduce identically if redone by
   a different analyst, and is presented as an organizing narrative device, not a scientific claim.
7. **Dataset-specific data-quality handling (sentinel/placeholder values, hybrid binning schemes) was
   applied case-by-case with manual inspection**, following a consistent *principle* (never silently discard
   or blindly impute a special code without checking its actual relationship to the target first) but not a
   fully automated, one-size-fits-all procedure. Reproducing this methodology on a new dataset would require
   a human (or an equally careful automated check) to similarly inspect for dataset-specific quirks before
   applying the standard statistical battery.
8. **The sampled-Shapley fallback (§4.4) has been validated on only one dataset** (as a deliberate
   retrospective check against a known answer, not yet as the primary analysis method for a new, genuinely
   oversized dataset). Its real-world behavior on, e.g., a 100+-column dataset where the "true" Shapley-based
   answer is not independently known, remains to be observed.
9. **Calibration is applied post-hoc and is not jointly optimized with the feature-selection objective** —
   i.e., features are selected purely to maximize ranking quality (AUC) via the stages above, and calibration
   is a separate, later correction for probability scale. A methodology that jointly considered calibration
   quality during feature selection itself was not explored.

---

## 8. Request to reviewer

Given the above, the specific questions this review is intended to help answer:
- Are there established feature-selection or Shapley-approximation techniques from the credit-risk/ML
  literature that would materially outperform or simplify this pipeline, that have not been considered here?
- Is the univariate screening battery (IV/Cramér's V/Mann-Whitney/model-validation escalation) missing any
  standard check a credit-risk practitioner would expect?
- Is the exact-vs-pruned-vs-sampled Shapley cascade (§4.2-4.4) a defensible design, or is there a more
  standard way to handle the exact-computation scaling problem in this literature that wasn't considered?
- Are the stated limitations (§7) the right ones to flag, or is there a more serious methodological gap not
  listed there?

Full supporting detail (per-dataset statistical tables, exact run outputs, code) is available on request —
this document is intended as the top-level summary for an initial review pass, not the complete record.
