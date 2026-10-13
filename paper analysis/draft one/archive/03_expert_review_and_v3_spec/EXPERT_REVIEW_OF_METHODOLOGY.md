# Expert Review — "Column-Selection Methodology for Credit Risk Models"

**Reviewer profile:** credit risk modelling (retail/consumer lending), applied statistics and ML; PhD; model
development and model-validation experience across application and behavioural scorecards, plus IRB/Basel
model documentation and fair-lending review.
**Document reviewed:** `METHODOLOGY_SUMMARY_FOR_EXPERT_REVIEW.md`, dated 2026-10-09.
**Review date:** 2026-10-09.
**Review type:** pre-submission methodological review, with an eye to what referees at a credit-risk or
applied-ML venue (EJOR, JORS, *Journal of Banking & Finance*, *Expert Systems with Applications*, IEEE TAI)
would raise.

> **Caveat on citations:** references below are given from working knowledge. Verify each against the
> original source before putting it in a submitted bibliography — in particular confirm author initials,
> year and venue. I have flagged the two or three I am least certain about.

---

## 1. Overall assessment

This is a careful, unusually self-aware piece of methodological work. The central insight — that greedy,
category-sequential feature screening produces order-dependent artefacts, demonstrated empirically rather
than merely asserted — is correct, non-trivial, and worth publishing. The author has also done something
most submissions in this space do not: validated their own approximation against a known-exact answer, and
reported the failure honestly when the decision rule broke.

However, in its current form I would not recommend acceptance. There are three issues I consider
publication-blocking in a credit-risk venue (M1, M4, M5 below), one that is a straightforward technical
mis-citation that a referee will catch immediately and which undermines confidence in the rest (M2), and one
where the inference layer is statistically mis-specified in a way that the Cohen's-d patch papers over
rather than solves (M3). None of these are fatal to the *idea*; all are addressable, several with work the
author has already built the infrastructure for.

**Recommendation: major revision.** The methodological core is sound. The framing, the inference layer, and
the credit-risk-domain treatment need substantial work.

---

## 2. What the methodology gets right

I want to be specific here, because these are genuine strengths and should survive the revision intact.

**2.1 The order-dependence critique is correct and well-evidenced.** Greedy forward selection producing
order-dependent "marginal value" is well known in principle but rarely demonstrated cleanly on real credit
data. The German Credit example (two columns that looked additive given `credit_history`, then failed when
tested against the full pool) is a concrete, teachable result. Keep it, and consider making it a headline
contribution rather than background motivation — "we show that category-sequential screening, which is
common practice in scorecard development, produces artefactual variable retention" is a more publishable
claim than "we propose a pipeline."

**2.2 Effect-size discipline over p-values at the screening stage is right**, and the document's reasoning
(at n in the tens of thousands, p<0.05 is nearly uninformative) is exactly correct. Many credit-scoring
papers still report χ² p-values as evidence of variable strength. Good.

**2.3 The `min_expected` reliability gate, and especially the distinction between two failure modes, is
good craft.** The high-cardinality location-field example (Cramér's V = 0.342 collapsing to AUC ≈ 0.53 under
model validation) is a compelling illustration of sparse-cell inflation, and the fact that the author
distinguishes it from the "rare but genuinely informative event" case (where the flag was a false alarm)
shows real understanding rather than mechanical rule-following. This is publishable material in its own
right as a practitioner caution.

**2.4 The nominal-vs-ordinal escalation branch (Stage 1, step 4) is correct and frequently got wrong** in
practice. Applying Mann-Whitney to an unordered categorical is a common error; explicitly routing those
cases elsewhere is to the author's credit.

**2.5 The Mann-Whitney non-monotonicity demonstration** (U-shaped relationship between number of credit
lines and default, detected by χ² and missed by Mann-Whitney) is a nice, concrete result. Credit risk is
full of non-monotonic relationships — utilisation, number of enquiries, time since last delinquency — and
practitioners who reach for rank tests by default should see this.

**2.6 Using the Shapley efficiency property as an implementation audit** is a good idea and under-used.
See m7 for a caveat about what it does and does not validate.

**2.7 The honest reporting of the sampled-Shapley failure.** Reporting that BH-alone gave 0/13 correct
decisions, rather than quietly adopting the patched version, is exactly the behaviour that makes a methods
paper credible. Preserve this in the paper, including the failure, not just the fix.

**2.8 Calibration is addressed at all.** The majority of ML-for-credit-scoring papers report AUC and stop.
Catching that Brier was worse than a base-rate baseline, and fixing it with cross-validated isotonic
regression, is above the norm for this literature.

---

## 3. Major issues

### M1. The methodology conflates *attribution* with *selection*. This needs to be confronted directly.

Shapley values are a solution concept for *fair credit allocation* among cooperating players, characterised
by efficiency, symmetry, dummy and additivity. They answer: "given that this coalition achieved value V, how
should credit for V be fairly divided?" They do **not** answer: "which subset of players should I hire?"

Those are different problems, and the difference bites here. Two concrete consequences:

- A feature can have a substantial Shapley value and still be *droppable with zero performance loss*,
  because Shapley splits credit between redundant features rather than declaring one unnecessary. Two
  perfectly collinear informative features each receive half the credit; both look "significant"; either
  alone would do.
- A feature can have a *low* Shapley value and still be necessary in the optimal subset, if its contribution
  is concentrated in coalitions that the averaging washes out (e.g. it only matters in the absence of a
  feature that is usually present).

This is not a hypothetical objection — it is argued formally in **Kumar, Venkatasubramanian, Scheidegger &
Friedler (2020), "Problems with Shapley-value-based explanations as feature importance measures," ICML**,
which a referee in this area will almost certainly cite at you. The paper's thesis is precisely that the
game-theoretic axioms do not transfer to the inferential questions practitioners want answered.

Note that the document's own results exhibit the symptom: on three of six datasets (HMEQ, GMSC, HELOC)
essentially every pooled candidate came back "significant." That is what you would expect from an
attribution method applied as a selection filter — Shapley will hand every non-dummy player a positive
share, and with a sensitive enough test, every positive share becomes "keep."

**What to do:** do not abandon Shapley — reframe. Two defensible framings:

1. *Attribution framing (recommended, lower risk):* position the Shapley stage as producing an
   **order-invariant importance ranking**, and then make selection an explicit, separate decision — e.g.
   choose the smallest prefix of the ranking whose model is statistically indistinguishable from the full
   model (tested properly; see M9/m1), or whose performance loss is below a pre-declared business tolerance.
   This is honest about what Shapley gives you and what the selection rule adds.
2. *Selection framing (higher risk, more work):* compare directly against methods that target subset
   selection as such — regularised selection, stability selection, knockoffs — and argue empirically that
   the Shapley route selects better or more stably. That requires the benchmark work in M8.

Either way, the paper must state explicitly that Shapley's axioms characterise fair attribution, not optimal
subset choice, and that the selection rule is an additional, separately justified layer.

### M2. The construction is **not** SAGE. It is SPVIM (or "retrain-based Shapley"). This mis-citation will be caught.

§4.1 claims the construction is "formally equivalent to SAGE (Covert, Lundberg & Lee, NeurIPS 2020)." It is
not, and the difference is material.

- **SAGE** applies Shapley values to a *loss-based* value function evaluated by **marginalising held-out
  features out of a single, fixed, already-trained model** (it imputes/conditions on absent features rather
  than refitting). The model is trained once.
- **This document's construction retrains the model on every subset** and uses cross-validated AUC as the
  value function. That is a different estimand: it measures how much predictive performance is *recoverable*
  from a feature set, allowing the learner to re-optimise and compensate via correlated features.

The retrain-based construction already has a name and a rigorous treatment in the literature:
**Williamson & Feng (2020), "Efficient nonparametric statistical inference on population feature importance
using Shapley values," ICML** — the Shapley Population Variable Importance Measure (SPVIM). This is almost
exactly what the document describes: Shapley values over a *population predictiveness* measure, with subsets
re-fit, and — critically for M3 — **with an inference framework that provides valid confidence intervals
accounting for both the subset-sampling and the data-sampling variability.**

That the author independently reinvented SPVIM is a point in their favour, but the paper must cite it,
position relative to it, and ideally adopt its inference machinery. Also note: SAGE's value function being
loss-based (not AUC) is itself worth considering — see M9.

Minor but embarrassing if it ships: the SAGE first author is **Ian** Covert; the document has "Covert, S."

Also add **Aas, Jullum & Løland (2021), *Artificial Intelligence* 298, "Explaining individual predictions
when features are dependent"** for the marginal-vs-conditional Shapley distinction, which interacts directly
with M7.

### M3. The inference layer is mis-specified, and the Cohen's-d fix is a patch, not a solution.

Three distinct problems:

**(a) A one-sample t-test on 5 CV-fold values is not valid.** The folds are not independent — each fold's
training set overlaps roughly 75% with every other fold's, so the fold-level Shapley values are positively
correlated and the usual variance estimator is biased downward, making the test anti-conservative. This is
well established: **Dietterich (1998), *Neural Computation*, "Approximate statistical tests for comparing
supervised classification learning algorithms"**, and definitively **Bengio & Grandvalet (2004), JMLR, "No
unbiased estimator of the variance of K-fold cross-validation."** See also **Nadeau & Bengio (2003),
*Machine Learning*, "Inference for the generalization error."** A referee who knows this literature will
treat every p-value in §4 as unreliable. (The document's §7 lists nine limitations; this is not among them,
and it should be near the top.)

**(b) The null reference distribution is not characterised.** Testing "mean Shapley value = 0" presumes you
know the sampling distribution of a Shapley-of-CV-AUC statistic for a truly useless feature. You do not, and
there is no reason to think it is a centred *t* with 4 df. In practice, adding a pure-noise feature to a
gradient-boosted model usually *slightly degrades* CV AUC, so the null may well have negative mean, in which
case the test is mis-centred in the conservative direction for nulls and the whole exercise is not measuring
what it claims to.

**(c) Cohen's d ≥ 0.8 is not a principled fix.** Cohen's conventions were proposed for standardised
mean differences between groups in behavioural research; they carry no interpretation for the ratio of a
mean Shapley-of-AUC increment to its across-permutation standard deviation. The threshold was also, by the
document's own account, selected *after* observing which value reproduced a known answer on one dataset —
which is the same data-driven threshold selection the methodology criticises elsewhere (Stage 1's "OR" rule
has the same issue; see m3). And the headline validation statistic ("11/13, zero false negatives") is
*n = 1 dataset*; it supports no general claim about sensitivity or FDR.

**What to do — replace, don't patch.** Two good options, in order of preference:

1. **Shadow/knockoff features for an empirical null (strongly recommended; cheap given existing code).** Add
   to the candidate pool a set of synthetic features with no true relationship to the target — e.g. permuted
   copies of real candidates (preserving marginal distributions, destroying the target relationship), as in
   **Boruta (Kursa & Rudnicki, 2010, *Journal of Statistical Software*)** — and compute their Shapley values
   through the identical pipeline. Their empirical distribution *is* the null reference for "a feature of
   this type, in this dataset, under this learner, contributes nothing." Retain a real feature only if its
   Shapley value exceeds, say, the 95th percentile of the shadow distribution. This is assumption-light,
   directly interpretable, works identically in exact and sampled mode, and removes both the fold-dependence
   problem and the Cohen's-d arbitrariness at once. It also gives you a defensible FDR story.
2. **Adopt SPVIM's inference** (Williamson & Feng 2020), which supplies confidence intervals built for this
   exact estimand. More faithful to the literature; more implementation work.

If the author keeps any paired-t machinery, use **repeated** cross-validation (e.g. 10 repeats × 5 folds)
with a corrected variance estimator, and say explicitly which correction.

### M4. Protected and proxy attributes are retained as "useful" with no fair-lending treatment. In a credit-risk venue this is the most damaging issue in the document.

The reported keep-lists include `AGE` and `EDUCATION` (Taiwan), `age` (German Credit pool), and the document
discusses `personal_status_sex` and `foreign_worker` as candidates evaluated on equal footing with
everything else. In most jurisdictions these are not permissible inputs to a consumer credit decision:

- **US:** ECOA / Regulation B prohibits use of race, colour, religion, national origin, sex, marital status
  and age (with narrow exceptions) in credit decisions. `personal_status_sex` combines sex and marital
  status; `foreign_worker` proxies national origin.
- **EU:** creditworthiness assessment is a high-risk application under the AI Act (Annex III), with
  attendant obligations; the Consumer Credit Directive and national equality law constrain inputs.
- Even where an attribute is not directly prohibited, **proxy** risk and **disparate impact** apply.

The document treats "statistically useful" as the only axis. A referee — and certainly a practitioner
reviewer — will read "we kept `personal_status_sex`" and question whether the authors understand the
application domain. This is fixable and the fix strengthens the paper:

- Partition candidate features explicitly into *permissible*, *prohibited*, and *proxy-risk* classes before
  Stage 1, with jurisdictional justification. Make this a documented step of the methodology, not an
  afterthought.
- Report results **both ways**: full statistical analysis (scientifically complete) *and* a
  constraint-respecting variant that excludes prohibited/proxy features. The delta between them is itself an
  interesting, publishable quantity — "how much discriminatory power is forgone by complying?" is a real
  question in the fairness-in-lending literature.
- Add a disparate-impact check on the final model (e.g. adverse-impact ratio across available demographic
  splits where the data permits), citing e.g. **Hardt, Price & Srebro (2016)**, **Chouldechova (2017)**, or
  Barocas, Hardt & Narayanan's *Fairness and Machine Learning* for framing.

Given the original paper was reportedly about *explainability* in credit risk, omitting the
fairness/regulatory dimension is a conspicuous gap.

### M5. Accepted-only samples: no reject inference, and the PAKDD income finding is very likely a truncation artefact.

Nearly all public credit datasets of this type contain only applicants who were **approved** under some
prior credit policy. The feature distributions are therefore truncated on a function of the very variables
being evaluated. Standard consequence: variables that the original underwriter used heavily appear *weak*,
because their range has been restricted and the bad-rate variation they would explain has been selected out.

The document reports, as a substantive finding, that `PERSONAL_MONTHLY_INCOME` in PAKDD is "surprisingly
weak — weaker than most demographics." In a review setting I would push back hard: that is exactly the
signature of range restriction from the original income-based cutoff, not evidence that income is
uninformative about default in the applicant population. Presenting it as a finding about income rather than
about the sample invites an easy, damaging referee objection.

**What to do:** at minimum, add an explicit discussion of accept-sample selection bias and label it as a
limitation on *all* "variable X is weak" conclusions. Cite the reject-inference literature — **Hand &
Henley (1997), JRSS-A, "Statistical classification methods in consumer credit scoring: a review"**; **Crook
& Banasik (2004), *Journal of Banking & Finance*, "Does reject inference really improve the performance of
application scoring models?"** Better: run a sensitivity analysis on any dataset where a policy/cutoff
variable is observable. Best, if feasible: demonstrate the methodology on one dataset with
through-the-door data, even synthetic.

### M6. Near-target and cross-model features inflate the headline results, and point-in-time availability is not addressed.

Two specific cases:

- **Taiwan `PAY_0`** is repayment status in the month immediately preceding the target month. A customer
  two months delinquent in September is nearly definitionally a default in October. Its IV of 0.87 and 47%
  of model importance reflect proximity to the label, not predictive insight. This is a *behavioural*
  variable, not an origination-time one.
- **HELOC `ExternalRiskEstimate`** is another vendor's risk score (IV 0.955). Including it means the
  exercise partly measures "can we recover a score we were already given," and it dominates the feature set.

Neither is wrong to include, but both must be flagged, and ideally the analysis should be run with and
without them. More generally, the paper needs a **point-in-time / feature-availability** discussion: which
selected features would actually be observable at the decision moment for the intended use case
(application vs behavioural scoring), and whether the selected set changes when restricted to
origination-time features. Referees in this field care about this a great deal; a methodology that selects
`PAY_0` as the dominant predictor of next-month default is technically correct and practically uninteresting
without that framing.

### M7. Correlation pre-pruning partially defeats the purpose of using Shapley, and reintroduces the univariate/greedy logic the paper criticises.

§4.3 prunes correlated clusters by keeping "the single highest-IV member." Three objections:

1. **It reintroduces a univariate criterion into the multivariate stage.** Within a correlated pair, the
   member with higher *marginal* IV is not necessarily the member with higher *conditional* contribution.
   The classic counter-case: X₁ with slightly higher IV but largely redundant with the rest of the pool, and
   X₂ with slightly lower IV carrying unique conditional information. The rule systematically prefers X₁.
   This is precisely the sort of order/criterion artefact §2 condemns.
2. **It is also greedy and path-dependent** — the iterative "highest-correlation pair first" procedure's
   outcome depends on processing order, as the author discovered when worrying about chain collapse. The
   Taiwan outcome (PAY_0 / PAY_2 / PAY_6 retained; PAY_3/4/5 dropped) is a reasonable *result* but it was
   reached by a procedure with no optimality guarantee.
3. **Pairwise correlation misses multi-way collinearity.** Three variables pairwise at ρ ≈ 0.5 can be
   near-perfectly collinear jointly. Standard diagnostics here are **VIF** or the condition number of the
   design matrix, not pairwise ρ.

**What to do:** use **grouped (coalitional) Shapley** instead. Treat each correlated cluster as a single
player, compute Shapley values over groups, and only decompose within a group if the group is retained. This
is the principled handling of dependent features, it reduces the combinatorial burden exactly as pruning
does (the motivation for pruning in the first place), it preserves the efficiency property over the full
feature set, and it is supported in the SAGE/SHAP tooling ecosystem. Cite Aas et al. (2021) for the
dependent-feature issue. If the author keeps pruning, it must be presented as an approximation with a
sensitivity analysis over the threshold (ρ ∈ {0.6, 0.7, 0.8}) and over the tie-break rule.

### M8. No benchmark comparison, no stability analysis, no ground-truth validation. For a methods paper, this is the largest gap in evidence.

The document is candid about the absence of benchmarks (§7.2), but I want to be concrete about what a
referee will require:

**(a) Comparators.** At minimum: full model; LASSO / elastic-net selection; recursive feature elimination;
Boruta; univariate IV top-*k*; permutation importance top-*k*; TreeSHAP global mean |φ| top-*k*. Report on
equal footing. Without this, "our pipeline is better" is unsupported, and the obvious referee question —
"would TreeSHAP global importance on one fitted model, at a fraction of the compute, have given the same
answer?" — goes unanswered. Given TreeSHAP is exact and polynomial-time for tree ensembles
(**Lundberg et al., 2020, *Nature Machine Intelligence***), that comparison is cheap and essential. If the
answer is "the rankings mostly agree," the paper's contribution becomes the *inference* layer rather than the
Shapley computation — still publishable, but a different claim.

**(b) Selection stability.** Bootstrap or repeated-CV the *entire* pipeline and report per-feature selection
frequency (**stability selection; Meinshausen & Bühlmann, 2010, JRSS-B**). This matters especially for German
Credit: n = 1,000, 300 bads, full-model fold SD ± 0.0315, and marginal contributions being tested in the
range 0.005–0.08. Several of those decisions cannot be stable at that sample size, and a single-pass keep-list
overstates what the data support. I would expect the five-feature German Credit answer to vary materially
across bootstrap replicates; the paper should show that rather than leave it to a referee to suspect it.

**(c) Synthetic ground truth.** This is the single most persuasive addition available. Simulate data with a
known sparse support — correlated informative features, pure-noise features, a redundant duplicate, a
non-monotonic effect, an interaction-only feature — and report **power and FDR curves** for the pipeline
versus the comparators, across sample sizes and across `n_samples` for the sampled variant. This converts
the "variety of outcomes across six datasets" argument (§6, which the author correctly labels informal) into
actual evidence, and it is the only way to substantiate claims like "zero false negatives."

### M9. The value function — full-range AUC, ranking-only, with hyperparameters held fixed — is a weak point on three counts.

**(a) AUC is not the decision-relevant metric in credit risk.** Lenders operate at a cutoff; the region of
the ROC curve that matters is narrow. Full AUC integrates over operating points that will never be used, so
a feature can earn Shapley credit for discrimination in a commercially irrelevant score region. Report
**Gini** (the field's convention; trivially 2·AUC − 1) and **KS**, and consider a decision-relevant value
function: partial AUC over the plausible cutoff range, bad-rate capture in the top deciles, or approval rate
at fixed bad rate. See **Hand (2009), *Machine Learning*, "Measuring classifier performance: a coherent
alternative to the area under the ROC curve"** for the standard critique of AUC, and **Lessmann, Baesens,
Seow & Thomas (2015), EJOR** for the benchmark conventions this literature expects.

**(b) A loss-based value function would be better founded** and would make calibration visible *inside*
selection rather than a post-hoc repair (which is M10/§5's awkwardness). With log-loss or Brier, v(∅) is
naturally the base-rate prediction rather than a stipulated 0.5, and the efficiency decomposition becomes
"total reducible loss," which is cleaner to interpret. SAGE itself is loss-based for exactly this reason.

**(c) Hyperparameters are held constant across all subsets.** A one-feature model and a thirteen-feature
model should not share `max_depth`, `n_estimators` and `min_child_weight`. Fixed hyperparameters tuned for
(or defaulted toward) larger feature sets systematically mis-estimate small-subset performance, and the bias
is *not* uniform across subsets — which means it does not cancel in the marginal differences that Shapley
values are built from. Nested tuning for 2ⁿ subsets is infeasible; acceptable mitigations are (i) use a
learner with minimal tuning sensitivity for the value function (regularised logistic regression is the
classic choice precisely for this reason, and is what the Shapley-feature-selection literature typically
uses), (ii) tune once per subset *size*, or (iii) at minimum, quantify the bias on a small pool by comparing
fixed-hyperparameter against per-subset-tuned Shapley values. Option (i) also addresses §7.1's
model-conditionality concern and would let the author report both a GBM and a logistic value function as a
robustness check — which referees will like.

### M10. The parsimony/performance trade-off is under-argued, and in Gini terms two of the six results are not favourable.

The document's "Gap" column invites the reader to see small numbers. Converted to Gini — the metric a credit
practitioner will actually use — the picture changes:

| Dataset | Selected Gini | Full-model Gini | Relative Gini loss | Features retained |
|---|---:|---:|---:|---|
| PAKDD-2009 | 0.2394 | 0.2832 | **−15.5%** | 4 / 51 |
| German Credit | 0.5302 | 0.5708 | **−7.1%** | 5 / 20 |
| Taiwan | 0.5508 | 0.5646 | −2.4% | 12 / 23 |
| HELOC | 0.5884 | 0.5900 | −0.3% | 13 / 23 |
| HMEQ | 0.8996 | 0.9014 | −0.2% | 11 / 12 |
| GMSC | 0.7304 | 0.7304 | 0.0% | 10 / 10 |

A 15.5% relative Gini reduction on PAKDD is not a rounding error — no portfolio owner accepts that for
parsimony without a specific justification (data acquisition cost, model-risk/interpretability constraints,
regulatory documentation burden). Conversely, on three datasets the selected model is statistically
indistinguishable from using everything, which raises the question the paper must answer head-on: **what is
the claimed benefit?** If it is interpretability or data cost, say so and quantify it. If it is predictive
performance, the results do not support that claim. Right now the paper reads as if small AUC gaps are
self-evidently a win; they are not, and a referee will say so.

Relatedly: the gaps are reported without any test. Use **DeLong, DeLong & Clarke-Pearson (1988),
*Biometrics*** for correlated ROC comparison, or a paired bootstrap, and state which differences are
statistically distinguishable. German Credit's −0.0203 gap against a full-model fold SD of ±0.0315 is, on its
face, not distinguishable.

---

## 4. Minor and technical issues

**m1.** §4.5's "is the model good" scale (0.5–0.7 poor, etc.) is loosely attributed to Hosmer & Lemeshow and
is a rule of thumb from clinical/biostatistical contexts. In credit scoring, an application scorecard Gini of
0.40–0.50 (AUC 0.70–0.75) is often perfectly serviceable, and a behavioural scorecard can exceed 0.80 Gini.
Replace with domain-appropriate benchmarks from Lessmann et al. (2015) rather than importing a clinical scale.

**m2.** IV is computed on 10 quantile bins. IV is known to increase with bin count; no bin-count sensitivity
analysis is reported, and the Stage-1 threshold (0.02) is therefore not scale-free. Report IV at 5/10/20 bins,
or use a supervised binning procedure (monotonic WOE binning is the industry standard) and say which.

**m3.** The Stage-1 pooling rule (`IV ≥ 0.02 OR Cramér's V ≥ 0.1`) was, per §3, adopted "after finding at
least one real column that cleared the IV threshold clearly while falling just short of Cramér's V's." That
is threshold selection informed by observed outcomes — the same practice criticised elsewhere. Since the two
statistics are acknowledged to be monotone transforms of the same χ², using both with an OR is also
redundant: pick one (IV, for domain convention), justify the threshold *a priori*, and report the other
descriptively.

**m4.** `v(∅) := 0.5` is a stipulation, not a derivation (AUC of a constant predictor is undefined). Fine, but
state it as a convention and note that under a loss-based value function the empty-model baseline is
well defined — see M9(b).

**m5.** Missingness is not neutral across subsets. XGBoost routes NaNs via learned default directions, so a
feature's *missingness pattern* carries information; when that feature is excluded from subset S, the
information disappears. Where missingness is correlated across features (the document notes HELOC's ~588-row
"no data" group appearing in nearly every column), subsets share a latent thin-file indicator, inducing
dependence between subset evaluations that the Shapley averaging does not account for. Recommend extracting
such indicators as explicit features (e.g. a `thin_file` flag) so the information is attributable to a
specific player rather than leaking through many.

**m6.** GMSC's sentinel values (96/98, 225 rows, 60% bad rate vs 6.6% base rate) deserve more scrutiny than
"keep as-is." A 9× bad-rate lift on a value that cannot be a literal count is a candidate for **label
leakage** — if 96/98 encode an account status (charge-off, closed-for-cause), that is outcome information,
not a predictor. The paper should either justify retention with a documented data-dictionary basis, exclude
those rows, or (preferred) recode as an explicit indicator and show results with and without it.

**m7.** The efficiency check validates *arithmetic*, not statistical accuracy. The Shapley values are exact
functions of noisy v(S) estimates; the sum will reconstruct v(full) − v(∅) to machine precision even if every
v(S) is badly estimated. §4.2's "confirmed to floating-point precision" is a correct statement about the
implementation but reads as a stronger claim than it is. Rephrase explicitly as an implementation audit.

**m8.** `scale_pos_weight` is used throughout and then corrected for with post-hoc calibration. AUC is
invariant to monotone transformations of the score, and class-prior reweighting has at best a modest effect on
GBM ranking performance. The simpler design is to drop `scale_pos_weight`, avoid distorting the probability
scale in the first place, and verify empirically that ranking performance is unaffected. Worth one ablation
to justify whichever choice is kept.

**m9.** Multiplicity across the whole study is not controlled or pre-registered: six datasets × five
categories × multiple escalation branches, plus mid-study threshold revisions (the Cohen's-d rule, the OR
rule, the pruning threshold). For a methods paper this is tolerable if *disclosed* as exploratory, but it
should be disclosed, and the synthetic-ground-truth study (M8c) should be pre-specified.

**m10.** BH's validity under dependence is mentioned (§7.5) but not addressed. Benjamini–Yekutieli (2001)
covers positive regression dependence; whether that holds for Shapley values of correlated credit features is
unverified. The shadow-feature approach (M3) side-steps this entirely, which is another reason to prefer it.

**m11.** Target definitions are taken as given. In credit risk, the default definition (90+ DPD per Basel,
versus charge-off, versus the dataset author's choice) and the performance window (12/18/24 months) materially
change which features matter. State each dataset's definition and window where documented, and flag where it
is unknown.

**m12.** The Five C's scaffold is acknowledged as presentational, and the inconsistency across datasets
(`age` placed differently) is acknowledged. My advice: either make it load-bearing — e.g. test whether
category-blind screening differs from category-aware, or impose a representation constraint — or reduce it
to a sentence in the data-description section. As it stands a referee may read it as decorative, and
inconsistency in a decorative element costs credibility for no benefit.

**m13.** Report compute cost and estimator variance. For the sampled variant, report the Monte Carlo standard
error alongside each Shapley estimate (the document's own code computes it); for the exact runs, report total
model fits and wall-clock. Reproducibility-minded venues will also want library versions, seeds, dataset DOIs
and a code repository.

**m14.** Six datasets is a reasonable start but all are well-known public benchmarks of modest size, and two
(Australian/credit-approval style datasets referenced elsewhere in the project) are n ≈ 690. Consider whether
the claim set should be scoped to "public benchmark datasets" explicitly, and avoid generalising to portfolio
scale without at least one large, genuinely messy dataset analysed end-to-end.

**m15.** One framing suggestion: the document's most novel, most defensible contribution may be the
*diagnostic* material — the sparse-cell inflation case, the Mann-Whitney non-monotonicity blind spot, the
demonstration that greedy category-sequential screening retains artefactual variables, and the demonstration
that significance-based Shapley selection degenerates as sample count rises. Those four results are concrete,
reproducible and useful to practitioners. A paper built around them, with the pipeline as the vehicle, is
stronger and much easier to defend than a paper claiming a new best-in-class selection pipeline.

---

## 5. Suggested priority order for revision

**Tier 1 — must fix before submission anywhere**
1. M4 — protected/proxy attribute handling and a fairness-constrained variant.
2. M2 — correct the SAGE mis-citation; position against SPVIM (Williamson & Feng 2020).
3. M3 — replace the fold-level t-test and the Cohen's-d rule with shadow-feature null calibration (or SPVIM CIs).
4. M1 — reframe attribution vs selection explicitly; cite Kumar et al. (2020).
5. M5 — accept-sample truncation discussion; retract or heavily qualify the PAKDD income claim.

**Tier 2 — needed for a credible methods contribution**
6. M8(c) — synthetic ground-truth study with power/FDR curves.
7. M8(a) — benchmark comparators, TreeSHAP top-*k* in particular.
8. M8(b) — stability selection frequencies via bootstrap/repeated CV.
9. M10 — report Gini/KS, add DeLong/paired-bootstrap tests, and argue the parsimony case explicitly.
10. M6 — near-target and cross-model feature treatment; point-in-time availability.

**Tier 3 — strengthens, can be scoped as future work if space-constrained**
11. M7 — grouped/coalitional Shapley in place of correlation pruning (or threshold sensitivity analysis).
12. M9 — value-function choice: loss-based alternative, decision-relevant metric, hyperparameter-bias check.
13. m2, m3 — binning and threshold sensitivity analyses.
14. m5, m6 — explicit missingness/sentinel indicators and the GMSC leakage question.
15. M8 + m13 — compute reporting, code release, reproducibility package.

---

## 6. Suggested additions to the reference list

*Shapley / importance methodology*
- Williamson, B. D., & Feng, J. (2020). Efficient nonparametric statistical inference on population feature importance using Shapley values. *ICML*. — **SPVIM; the correct citation for this construction.**
- Covert, I., Lundberg, S., & Lee, S.-I. (2020). Understanding global feature contributions with additive importance measures. *NeurIPS*. — SAGE; cite for contrast, not equivalence.
- Kumar, I. E., Venkatasubramanian, S., Scheidegger, C., & Friedler, S. (2020). Problems with Shapley-value-based explanations as feature importance measures. *ICML*.
- Aas, K., Jullum, M., & Løland, A. (2021). Explaining individual predictions when features are dependent. *Artificial Intelligence*, 298.
- Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. *NeurIPS*.
- Lundberg, S. M., et al. (2020). From local explanations to global understanding with explainable AI for trees. *Nature Machine Intelligence*, 2(1).

*Selection, stability, inference on CV*
- Meinshausen, N., & Bühlmann, P. (2010). Stability selection. *JRSS-B*, 72(4).
- Kursa, M. B., & Rudnicki, W. R. (2010). Feature selection with the Boruta package. *Journal of Statistical Software*, 36(11).
- Bengio, Y., & Grandvalet, Y. (2004). No unbiased estimator of the variance of K-fold cross-validation. *JMLR*, 5.
- Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms. *Neural Computation*, 10(7).
- Nadeau, C., & Bengio, Y. (2003). Inference for the generalization error. *Machine Learning*, 52.
- Benjamini, Y., & Yekutieli, D. (2001). The control of the false discovery rate in multiple testing under dependency. *Annals of Statistics*, 29(4).

*Credit scoring domain*
- Lessmann, S., Baesens, B., Seow, H.-V., & Thomas, L. C. (2015). Benchmarking state-of-the-art classification algorithms for credit scoring: An update of research. *EJOR*, 247(1). — **the benchmark-conventions reference for this literature.**
- Baesens, B., Van Gestel, T., Viaene, S., Stepanova, M., Suykens, J., & Vanthienen, J. (2003). Benchmarking state-of-the-art classification algorithms for credit scoring. *JORS*, 54(6).
- Thomas, L. C., Edelman, D. B., & Crook, J. N. *Credit Scoring and Its Applications*. SIAM.
- Siddiqi, N. *Credit Risk Scorecards*. Wiley. — already used for IV conventions; cite formally.
- Hand, D. J., & Henley, W. E. (1997). Statistical classification methods in consumer credit scoring: a review. *JRSS-A*, 160(3).
- Crook, J., & Banasik, J. (2004). Does reject inference really improve the performance of application scoring models? *Journal of Banking & Finance*, 28(4).
- Hand, D. J. (2009). Measuring classifier performance: a coherent alternative to the area under the ROC curve. *Machine Learning*, 77(1).
- DeLong, E. R., DeLong, D. M., & Clarke-Pearson, D. L. (1988). Comparing the areas under two or more correlated ROC curves. *Biometrics*, 44(3).
- Dumitrescu, E., Hué, S., Hurlin, C., & Tokpavi, S. (2022). Machine learning for credit scoring: Improving logistic regression with non-linear decision-tree effects. *EJOR*, 297(3).
- Gunnarsson, B. R., vanden Broucke, S., Baesens, B., Óskarsdóttir, M., & Lemahieu, W. (2021). Deep learning for credit scoring: Do or don't? *EJOR*, 295(1).

*Calibration*
- Niculescu-Mizil, A., & Caruana, R. (2005). Predicting good probabilities with supervised learning. *ICML*.
- Zadrozny, B., & Elkan, C. (2002). Transforming classifier scores into accurate multiclass probability estimates. *KDD*.
- Platt, J. (1999). Probabilistic outputs for support vector machines. *Advances in Large Margin Classifiers*.

*Fairness / regulatory*
- Hardt, M., Price, E., & Srebro, N. (2016). Equality of opportunity in supervised learning. *NeurIPS*.
- Chouldechova, A. (2017). Fair prediction with disparate impact. *Big Data*, 5(2).
- Barocas, S., Hardt, M., & Narayanan, A. *Fairness and Machine Learning*. fairmlbook.org.

*Less certain — verify before citing*
- Szepannek, G., and co-authors have work on transparency/auditability of ML in credit scoring (JORS, c. 2022); I believe this exists and is relevant to the explainability framing, but confirm the exact reference.
- Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *KDD*. — certain, but cite only if the implementation is discussed in detail.

---

## 7. Closing comment

I want to end where I began: the diagnostic work here is good, and the intellectual honesty — particularly
reporting the sampled-Shapley failure rather than burying it — is better than what I typically see at
this stage. The problems are fixable. My strongest single piece of advice is **M8(c) plus m15**: build the
synthetic ground-truth study, and reframe the paper around the four concrete diagnostic findings rather than
around a pipeline claim. That combination turns a pipeline description, which referees will pick at, into a
set of reproducible results about how feature screening fails in credit risk — which is both harder to
dispute and more useful to the field.

The two things that would most embarrass the paper in review, if left as they are, are the SAGE
mis-attribution (M2) and the retention of protected attributes with no fair-lending discussion (M4). Fix
those first.
