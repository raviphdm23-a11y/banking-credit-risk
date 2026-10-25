# SHARP — Shapley Ranking with Parsimony (Column-Usefulness Methodology, v3.1, operative)

**Name:** The methodology is called **SHARP** (**Sha**pley **R**anking with **P**arsimony), reflecting its
two-stage core: order-invariant Shapley *attribution* ranks features, and a separate, pre-declared
*parsimony* rule (DeLong equivalence + relative-Gini tolerance) selects the set. "v3" refers to the current
revision of SHARP, not a different method.

Standing methodology for deciding which raw columns are useful for predicting a binary credit-risk target.
**This is the operative document.** It is now **v3.1**, revised 2026-10-17 (v3 was 2026-10-10, in response to
external methodological review), and **it is implemented in code** — the module map in §2 is authoritative and
the code and this document are meant to stay in step.

**v3.1 change (2026-10-17):** added the **Riley et al. minimum-sample-size calculation** as a *reported*
data-sufficiency diagnostic alongside EPV (§4.6; AEGIS G1). It is reported, never an auto-reject — a shortfall
is a disclosed caveat the MAC weighs. Engine: `backend/riley_minsize.py`; retrospective across all runs:
`RILEY_SAMPLE_SIZE.md`. No selection parameter changed; v3 runs are unaffected and reproduce identically.

**History and companion documents** *(moved to `archive/` — see `archive/PROVENANCE.md` for the full
methodology-evolution narrative and file index)*
- `archive/03_expert_review_and_v3_spec/METHODOLOGY_V2_ARCHIVED.md` — the previous (v2) version, kept for provenance. Superseded.
- `archive/03_expert_review_and_v3_spec/METHODOLOGY_SUMMARY_FOR_EXPERT_REVIEW.md` — the v2 summary that was submitted for review.
- `archive/03_expert_review_and_v3_spec/EXPERT_REVIEW_OF_METHODOLOGY.md` — the review. Findings are referenced below as M1-M10 (major) and
  m1-m15 (minor).
- `archive/03_expert_review_and_v3_spec/METHODOLOGY_V3_REVIEWED.md` — the full v3 specification, including rationale and the implementation
  brief. **Where this document is terse, that one is the detail.**

**Not shown anywhere in the Sandbox frontend** — a private reference for Claude + the user.

---

## 1. What this methodology claims, and what it does not

Two questions are kept separate, because conflating them was v2's central error (review M1):

| Stage | Question | Tool |
|---|---|---|
| **Importance** | "How much predictive value is attributable to this feature, order-invariantly?" | Shapley over cross-validated predictiveness |
| **Selection** | "What is the smallest feature set whose performance is acceptable?" | Parsimony curve + pre-declared tolerance + DeLong equivalence test |

Shapley values are a *fair-attribution* solution concept (efficiency, symmetry, dummy, additivity). They do
not identify an optimal subset: a redundant-but-informative feature still receives a positive share, and a
feature whose value concentrates in rare coalitions can average below a bar despite being needed. So
attribution ranks; a separately-justified rule selects.

**The inference target, stated precisely:** population feature importance *with respect to a specified
learner and value function* — "how much cross-validated predictiveness is recoverable from this feature set,
for this learner class, on this population." Not "how much this feature matters to credit risk in general."

**Licensed claim:** that category-sequential (greedy) screening produces order-dependent, artefactual
variable retention; that an order-invariant importance estimate plus an explicit selection rule avoids it;
and that the four diagnostic findings in §8 occur in real credit data.

**Not licensed yet:** that this pipeline selects *better* subsets than established alternatives. That needs
the benchmark study (§7.2), which is implemented but not yet run across datasets.

**Correct literature positioning (review M2).** This construction — refit per subset, value function =
cross-validated performance — is the **Shapley Population Variable Importance Measure (SPVIM)** of
**Williamson & Feng (2020, ICML)**. It is *not* SAGE: SAGE (Covert, Lundberg & Lee, 2020) marginalises absent
features out of a single fitted model. v2 claimed SAGE equivalence; **that claim is withdrawn.**

---

## 2. Module map (authoritative)

| Stage | Module | Key entry points |
|---|---|---|
| 0 Governance | `ml_models/feature_governance.py` | `classify_columns`, `warn_on_retained_ineligible`, `disclosure_block` |
| 1 Binning / IV | `ml_models/binning.py` | `woe_bin`, `iv_sensitivity`, `WOEEncoder`, `detect_sentinels`, `thin_file_indicator` |
| 1 Screening | `ml_models/v3_pipeline.py` | `stage1_screen`, `single_column_model_check` |
| 2 Importance | `ml_models/shapley_utils.py` | `shapley_importance`, `cluster_players`, `make_shadows`, `vif_report` |
| 3 Selection | `ml_models/selection.py` | `parsimony_curve`, `delong_test`, `select_parsimonious`, `score_report` |
| 4 Calibration | `ml_models/trainer.py` | `calibrate_model`, `evaluate_calibration` |
| 5 Benchmarks | `ml_models/benchmarks.py` | `run_benchmarks`, `rank_concordance` |
| 5 Ground truth | `ml_models/synthetic_validation.py` | `make_synthetic`, `run_grid` |
| Deployment / missing-value governance | `ml_models/missing_governance.py`, `ml_models/binning.py` | `build_scorer`, `Scorer.score`, `adverse_missing_floor`, `mandatory_missing_penalty` |
| Orchestration | `ml_models/v3_pipeline.py` | `run_pipeline`, `build_report`, `model_card_markdown` |

`run_pipeline` governance parameters (declared at the start of a run): `missing_policy`
(`'as_learned'` \| `'adverse_floor'`) with `floor_columns`; `mandatory_columns` with `incomplete_policy`
(`'reject'` \| `'refer'` \| `'adverse_score'`). See Stage 0 (§3.6) and Deployment (§7.8).

One call runs everything:

```python
import sys; sys.path.insert(0, 'ml_models')
import pandas as pd, v3_pipeline as v3
out = v3.run_pipeline(pd.read_csv('data/ml_lab/datasets/hmeq.csv'),
                      target='target', dataset_name='HMEQ')
print(out['report'])
```

---

## 3. Stage 0 — Feature eligibility and data governance

Runs **before any statistics**. Output is a per-column classification that travels with every downstream
result. **No column is dropped here** — classification drives warnings and disclosures.

### 3.1 Protected / proxy attributes: warn, retain, disclose

**Project decision (data owner, 2026-10-09): prohibited and proxy-risk attributes are RETAINED, with
mandatory warning and disclosure.** Stated justification, reproduced verbatim by
`feature_governance.disclosure_block()`:

> These are public, de-identified research benchmark datasets analysed for methodological purposes.
> Protected and proxy-risk attributes are retained so results remain comparable with the substantial
> published literature on these same datasets, which overwhelmingly includes them. No model produced in this
> work is intended for, or suitable for, deployment in a live credit decision. Retention is a methodological
> choice for comparability, **not** an endorsement of using these attributes in practice.

Four tags, assigned by name-pattern rules with per-dataset overrides:

| Tag | Examples found in these datasets |
|---|---|
| `permissible` | `credit_history`, `DEBTINC`, `NetFractionRevolvingBurden` |
| `prohibited` | `SEX`, `MARRIAGE`, `AGE`/`age`, `personal_status_sex`, `foreign_worker`, `NACIONALITY` |
| `proxy_risk` | `EDUCATION`, geography (`RESIDENCIAL_*`, `*_ZIP_3`, `*_CITY`, `*_BOROUGH`, `*_AREA_CODE`), `people_liable`, `NumberOfDependents`, `housing` |
| `unclear` | requires a jurisdictional determination; document and resolve |

Mandatory behaviour when such a column is retained in a final set: (1) a `UserWarning` naming the column and
tag; (2) the standard disclosure block in the findings log; (3) an ASCII marker in results tables —
`AGE [prohibited]`, via `flagged_name()`; (4) a dedicated model-card field.

Counts as implemented (`classify_columns`): PAK 19 ineligible of 51; Taiwan 4 of 23 (`SEX`, `EDUCATION`,
`MARRIAGE`, `AGE`); German Credit 5 of 20; GMSC 2 of 10; HMEQ 0 of 12. **Note PAK's
`RESIDENCIAL_PHONE_AREA_CODE` is `proxy_risk` and was in PAK's v2 final keep-list** — exactly the case the
warning exists to surface.

**Fairness testing [SPECIFIED — see §7.10].** The adverse-impact-ratio identification procedure (proxy-leakage
AIR on excluded protected/proxy attributes + the true-risk-driven interpretation test) is **documented in §7.10
and applied at G4 on every run**. Still **[DEFERRED]**: the fairness-constrained replication (pipeline re-run with
`prohibited` + `proxy_risk` excluded) and the resulting Gini delta — the "cost of compliance" / less-
discriminatory-alternative study.

### 3.2 Accept-only sample disclosure (review M5)

Every dataset here contains only applicants **approved** under a prior credit policy, so feature
distributions are truncated on a function of the variables being evaluated. This systematically
**understates** variables the original underwriter used.

> **Correction carried forward.** v2's conclusion that PAK's `PERSONAL_MONTHLY_INCOME` is "surprisingly
> weak — weaker than most demographics" is **retracted as stated**. It is consistent with range restriction
> from the original income-based approval cutoff. The defensible statement: "within the accepted population,
> income shows little residual discriminatory power — as expected where income was used in the original
> approval decision." Not a finding about income and default.

Cite Hand & Henley (1997); Crook & Banasik (2004). No reject inference is performed.

### 3.3 Point-in-time availability (review M6)

Tags: `origination`, `behavioural`, `near_target`, `external_score`. Two cases require explicit handling:

- **Taiwan `PAY_0`** → `near_target`: repayment status in the month immediately before the target month, so
  partially definitional. Its IV of 0.87 and ~47% model importance reflect label proximity. Report Taiwan
  with and without it.
- **HELOC `ExternalRiskEstimate`** → `external_score` (IV 0.955, 36% importance): another vendor's score, so
  the exercise is partly score recovery. Report with and without it.

Mixing classes is acceptable **if disclosed and scoped** ("behavioural scorecard"); it must not be presented
as an application scorecard. `availability_warnings()` fires automatically.

### 3.4 Target definition and performance window (m11)

Record per dataset: default definition (90+ DPD / Basel / charge-off / author's own), performance window,
observation date. Where undocumented, state "not documented in source" — never leave blank.

### 3.5 Sentinel and leakage audit (m6)

v2's principle — never silently drop or impute a special code without checking its relationship to the
target — is **retained**, plus:

1. Any value that cannot be a literal measurement (GMSC `96`/`98`; HELOC `-7`/`-8`/`-9`) is recoded as an
   **explicit indicator** via `extract_sentinel_indicators()`, so the information is attributable to a named
   Shapley player instead of leaking diffusely (also addresses m5).
2. `detect_sentinels()` + `sentinel_lift()` flag any sentinel group with event-rate lift ≥ 3× as a
   **leakage candidate**, with a warning. **Open item:** GMSC's `96`/`98` group (225 rows, 60.4% bad vs 6.6%
   base) must be resolved against a data dictionary — if those codes encode charge-off or closed-for-cause,
   that is outcome information and the rows or codes must be excluded.
3. Shared missingness (HELOC's ~588-row "no data" group across nearly every column) becomes one
   `thin_file` indicator.

**Data-handling note discovered during implementation:** `GMSC.csv` is **sorted by target**. Any
non-shuffled split on it would be catastrophic. All splits here use `StratifiedKFold(shuffle=True)`, so
existing results are unaffected — but it must be stated.

### 3.6 Mandatory columns and missingness classification (declared here)

Two governance decisions about *blanks* are made at Stage 0, before any model is fit, and travel downstream
to deployment (§7.8):

1. **Missingness-lift audit → classification.** For every column with blanks, record the default rate when
   the field is missing vs present (`lift`). WOE keeps `__missing__` as its own bin, so informative
   missingness is preserved (e.g. HMEQ undisclosed debt-to-income → 7.2× lift, correctly adverse). Each such
   column is then classified as **structural / MCAR** (the missing pattern is a property of the data-
   generating process — keep the learned WOE) or **applicant-influenceable** (the applicant could omit the
   field — governed at scoring; see §7.8). This classification is a documented manual judgement, not inferred.

2. **Mandatory columns.** Columns deemed *essential* — a credit decision should not be made without them —
   are declared up front via `run_pipeline(mandatory_columns=...)`. An essential column is typically never
   blank in the training sample, so it has **no learned `__missing__` bin**; a blank at scoring would
   otherwise fall through to WOE 0 (numeric) or be conflated with the rare/unseen `__other__` bucket
   (categorical). The deployment gate (§7.8) handles this. A declared-mandatory column that Stage 3 does not
   retain is still honoured as a **data-quality gate** (flagged), though it does not enter scoring.

Neither decision drops or alters any training row; both configure the scoring-time governance in §7.8.

### 3.7 Eligibility exclusion taxonomy — computable preconditions [documented]

Beyond the protected/proxy tagging (§3.1, which flags but does **not** drop), Stage 0 excludes four
kinds of **non-modellable** columns before screening. Each exclusion is driven by a **computable
precondition** (a deterministic test or a measured threshold) and is written to the G0 record with
its measured value, so every call is reproducible and a reviewer can re-derive it. The deterministic
tests (constant, all-blank, key cardinality) need no judgement; the leakage / PII / undocumented-junk
calls pair the computed signal with a recorded rationale — a documented judgement, never a silent drop.

| Category | Computable precondition (the test) | Judgement component | Examples |
|---|---|---|---|
| **Constant / zero-variance** | `nunique() ≤ 1` | none (fully deterministic) | SBA `State` (all `CA`), `BalanceGross` (all 0) |
| **Identifier / key / PII** | cardinality `nunique/n → 1` (a key), or high-cardinality free text | "is a record key / name / PII" — carries no generalisable signal | SBA `LoanNr_ChkDgt` (2102/2102 unique), `Name` (2005), `Zip` (814) |
| **Leakage (post-outcome)** | near-perfect **target agreement** (→ 1), or sentinel **event-rate lift ≥ 3×** (`sentinel_lift`, §3.5) | "defined only after the outcome" (point-in-time, §3.3) | SBA `MIS_Status` (100% = the label), `ChgOffPrinGr`/`ChgOffDate` (99.5%) |
| **Junk / undocumented** | `isna().all()` (all-blank) → auto-drop | non-blank but **absent from the data dictionary** → excluded pending documentation | CREDITRISK `Unnamed:12–16` (all-blank); SBA `xx` (undocumented) |

**How it is computed in practice.** The variance (`nunique`), cardinality ratio (`nunique/n`),
all-blank (`isna().all()`) and sentinel-lift (`sentinel_lift`, ≥3×) tests are deterministic and run on
the raw frame. The leakage **target-agreement** figure is `mean((col-derived indicator) == y)` — e.g.
SBA `MIS_Status=='CHGOFF'` vs `Default==1` → 100%; `ChgOffPrinGr>0` vs `Default==1` → 99.5%. The
computed test *flags the candidate*; where meaning decides the call (PII, post-outcome, undocumented),
the exclusion records both the number and the one-line rationale (consistent with §3.3, §3.5, §3.6 and
the "documented manual judgement, not inferred" principle).

---

## 4. Stage 1 — Univariate screening

### 4.1 One primary statistic (review m3)

**Information Value is the single primary screen, threshold `IV >= 0.02` declared a priori** (Siddiqi's
conventional "weak or better"). v2's `IV >= 0.02 OR Cramér's V >= 0.1` rule is **withdrawn**: the two are
monotone transforms of the same χ², so the OR was redundant, and it was adopted after observing which
columns it admitted. **Cramér's V, χ² and the p-value are computed and reported descriptively only** — they
decide nothing.

Reference bands, reported every time (per standing preference):

| IV | Strength | | Cramér's V | Strength |
|---|---|---|---|---|
| < 0.02 | Useless | | < 0.1 | Negligible |
| 0.02–0.1 | Weak | | 0.1–0.3 | Weak |
| 0.1–0.3 | Medium | | 0.3–0.5 | Moderate |
| > 0.3 | Strong | | > 0.5 | Strong |

### 4.2 Binning (review m2)

1. **Primary: monotonic WOE binning** (`binning.woe_bin`), min bin 5% of rows — the credit-scoring standard.
2. **Monotonicity is enforced only where supported.** This matters: HMEQ `CLNO` and GMSC
   `NumberRealEstateLoansOrLines` are genuinely U-shaped and economically sensible. If enforcement would
   collapse a column below 3 bins, size-constrained non-monotonic bins are kept and `monotonic_enforced=False`
   is reported.
3. **Non-monotonic shape detector [NEW].** IV is computed with and without the monotonicity constraint; if
   freeing it recovers ≥20% more IV, `shape_nonmonotonic=True` and the column routes to the model check
   rather than being decided on IV. **Validated:** this fires on HMEQ `CLNO` (37.9% IV cost), HMEQ `LOAN`
   (25.0%) and GMSC `DebtRatio` (73.7%) — all three independently identified as shape-anomalous in v2.
4. **Mandatory bin-count sensitivity:** IV at WOE and 5/10/20 quantile bins. If the `IV >= 0.02` verdict
   **flips**, the column is `binning_sensitive` and routes to the model check.
5. **Discrete/count columns use raw levels, not quantile cuts** (rare levels pooled). v2 lost signal both
   ways here: IV collapsing to 0.0 on zero-inflated counts, and IV understated 6× on GMSC
   `NumberRealEstateLoansOrLines` (0.012 quantile-binned vs 0.072 on raw levels — where its U-shape lives).
6. **Hybrid binning for sentinel codes retained** from v2 (special codes as their own bins).

### 4.3 Reliability gate [RETAINED]

χ² `min_expected >= 5` before the binned statistic is trusted. Both documented failure modes retained,
including the distinction: **sparse-category inflation** (inflates only — a weak result needs no rescue, a
strong one must be escalated) vs **rare-but-real event** (bias direction undetermined — always escalate).

### 4.4 Escalation [RETAINED]

- Gate fails, column **orderable** → Mann-Whitney U. Caveat retained: it is blind to non-monotonic shapes
  (demonstrated on `CLNO`).
- Gate fails, column **nominal** → Mann-Whitney is invalid (unordered labels cannot be ranked); escalate
  directly to the single-column model check.
- Statistic and Mann-Whitney **disagree** → print the per-bin bad-rate table and diagnose the shape.

### 4.5 Single-column model check

Gini with a bootstrap confidence interval; the CI must exclude zero for a "real" verdict. v2 eyeballed AUC
against 0.5.

### 4.6 Data-sufficiency diagnostics — EPV + Riley minimum-N [NEW in v3.1]

Two sufficiency diagnostics are computed on the dataset entering Stage 1 and **reported together** (they are
surfaced at AEGIS **G1**; both are *reported*, neither auto-rejects — a shortfall is a disclosed caveat):

1. **EPV** (events per variable) = events ÷ P, guideline **≥ 10** (Peduzzi 1996; van Smeden 2019). Familiar,
   but blind to signal strength.
2. **Riley minimum-N** (Riley 2019 Part II; Riley 2020 BMJ m441) — ties the required sample size to the
   model's *anticipated discrimination*, so a weak-signal model is told it needs more rows even at generous
   EPV. Required N = **max** of three binary criteria, each against a fixed target:
   - **B1** overall-risk precision — 95% CI half-width ≤ 0.05 — `n = (1.96/0.05)²·φ(1−φ)`;
   - **B3** shrinkage ≥ 0.90 — `n = P / [(S−1)·ln(1 − R²cs/S)]`, S = 0.9;
   - **B4** optimism ≤ 0.05 in Nagelkerke R² — `n = P / [(S₄−1)·ln(1 − R²cs/S₄)]`, S₄ = R²nag/(R²nag+0.05).

   where `max(R²cs) = 1 − exp(2·[φ·lnφ + (1−φ)·ln(1−φ)])` and `R²nag = R²cs/max(R²cs)`. The anticipated R²cs is
   obtained from the anticipated C-statistic + prevalence by the Riley–Van Calster–Collins (2020) seeded
   simulation (forward-consistent: at G1 no model is yet fit, so only an expected C is available).
   **P = selected-feature count** (β count for WOE-logistic); the stricter candidate-pool P is acknowledged.

   Engine `backend/riley_minsize.py`, validated against the BMJ m441 worked examples (Example 1 →
   N=5,249/events=263/EPP=8.75) and the pmsampsize C→R²cs pairing (C=0.89, φ=0.174 → R²cs 0.291 vs 0.288).
   Retrospective across all governed runs (one SHORT — MSME, concordant with its EPV failure and NO-GO):
   `RILEY_SAMPLE_SIZE.md`.

**Comparability discipline.** Both diagnostics are computed identically and version-tagged (v3.1) so the
retrospective is comparable across datasets; the method is fixed (P8) and neither diagnostic changes any
selection or gate-pass analytics.

---

## 5. Stage 2 — Order-invariant importance

### 5.1 Value function (review M9a/M9b)

`v(S)` = repeated cross-validated predictiveness on exactly the columns in `S`. Pluggable:

| `value_fn` | `v(empty)` | Notes |
|---|---|---|
| `auc` (default) | 0.5 *(stated convention — AUC of a constant predictor is undefined)* | Continuity with the six completed datasets |
| `partial_auc` | 0.5 | McClish-corrected over the low-FPR operating band — lenders work at a cutoff |
| `brier_skill` | 0.0 | Loss-based; well-defined empty baseline; calibration enters selection directly |

Required robustness: run ≥2 value functions on at least two datasets and report **Kendall's τ** between the
importance rankings (`benchmarks.rank_concordance`). If τ is low, the loss-based version becomes primary.

### 5.2 Learner (review M9c)

| `learner` | Role |
|---|---|
| `woe_logistic` (**default**) | Penalised logistic on monotonic-WOE inputs — credit-scoring standard form, deterministic, hyperparameter-insensitive. Removes v2's refit-noise objection. |
| `xgboost` | Available in the learner registry; **not used in the governed process** (since 2026-10-25 every stage, including calibration, uses `woe_logistic`). |

Report both rankings and their Kendall's τ; material disagreement is itself a finding (the feature's value
is interaction-dependent), not something to average away.

**`scale_pos_weight` is OFF by default** (review m8), opt-in via `use_scale_pos_weight`. **Measured:** on
GMSC it inflated mean predicted probability to **0.286 against a true base rate of 0.067 — a 4.3× inflation**.
With it off, mean predicted probability is 0.0673. The calibration damage v2 repaired post-hoc was
self-inflicted.

**Performance note that makes this tractable:** a column's WOE bins and values depend only on (column,
training fold), *not* on the subset. The `woe_logistic` path computes every (fold, column) WOE vector once
and reuses it across all subsets, leaving only a cheap logistic fit per subset. Statistically identical —
bins are still fitted on the training fold only — but the difference between a usable and an unusable
runtime (German Credit: 26 players, 11,575 fits, **55 s**).

### 5.3 Grouped (coalitional) players replace correlation pruning (review M7)

v2 pruned correlated clusters by keeping the highest-IV member. That reintroduced a *univariate* criterion
into the multivariate stage, was itself greedy and path-dependent, and used pairwise ρ, which misses
multi-way collinearity.

**v3:** hierarchical clustering on distance `1 − |Spearman ρ|`, cut at `|ρ| = 0.7`; **each cluster is a single
Shapley player** (`cluster_players`). This cuts the combinatorial cost exactly as pruning did — pruning's
only real motivation — while preserving the efficiency property over the full candidate set and handling
redundancy the way Shapley is designed to. `vif_report()` additionally flags VIF > 10. Within-group
decomposition happens only for retained groups. Mandatory sensitivity at `ρ ∈ {0.6, 0.7, 0.8}`.

Observed working: on HMEQ, `MORTDUE` and `VALUE` were correctly collapsed into one player
`grp[MORTDUE+VALUE]`.

### 5.4 Shadow-feature null replaces the significance test (review M3) — the central fix

**Withdrawn:** v2's one-sample t-test on 5 CV-fold Shapley values, and the Cohen's d ≥ 0.8 patch. The t-test
is invalid (folds share ~75% of training data, so the variance estimate is biased down — Bengio & Grandvalet
2004; Dietterich 1998), the null distribution was uncharacterised, and the Cohen's d threshold is a
behavioural-science convention with no interpretation here that was chosen after seeing which value
reproduced one dataset's known answer.

**v3 retention rule:**
1. Add ≥10 **shadow players** — copies of real columns with values permuted across rows, preserving the
   marginal distribution and destroying the target relationship (Boruta's device, Kursa & Rudnicki 2010).
2. Run the identical Shapley computation over the augmented player set.
3. The shadows' Shapley values **are** the empirical null.
4. A real player is `importance_confirmed` if its Shapley value exceeds the **95th percentile of the shadow
   distribution**, and its bootstrap `confirmation_frequency` ≥ 0.80.
5. Confirmation frequency comes from bootstrapping the per-player estimate distribution against a
   bootstrapped shadow bar. *(v3's spec called for R ≥ 20 full re-runs; bootstrapping the existing estimates
   answers the same question — "would this player still clear the bar under resampling?" — at a small
   fraction of the compute, which is what makes it usable on real pools.)*

**Why this is better:** assumption-light; **no multiple-testing correction needed** (the bar is a quantile of
an empirical null, not a family of p-values — so review item m10 dissolves); unaffected by fold dependence;
behaves identically in exact and sampled mode, so the exact-vs-sampled discrepancy that motivated the
Cohen's d patch does not arise.

**BH p-values and Cohen's d are retained as reported diagnostics and decide nothing.** Keep them visible,
because they are self-refuting in a useful way: in the German Credit run, the permuted noise column
`__shadow__1_credit_amount` received **BH p = 0.0000** with a **negative** Shapley value. A significance-based
rule would have confirmed pure noise. The shadow bar rejected it correctly.

### 5.5 Exact vs sampled

- **Exact** enumeration when player count (**including shadows**) ≤ 15. Note that adding shadows usually
  pushes realistic pools into sampled mode — this is expected.
- **Sampled** permutation estimation otherwise, with the Monte Carlo standard error reported per player. Set
  `target_mc_se` so `T` is determined by the precision the decision needs rather than a fixed default.
- **The efficiency check is reported as `implementation_audit`** (review m7): it validates arithmetic, not
  statistical accuracy — it passes to machine precision even if every `v(S)` is badly estimated. Observed
  5.55e-17 on German Credit.

---

## 6. Stage 3 — Selection

1. **Eligible set** = players with `importance_confirmed` and confirmation frequency ≥ 0.80.
2. **Rank** by Shapley value, descending.
3. **Parsimony curve** (`selection.parsimony_curve`): for `k = 1..K`, fit on the top-`k` players and record
   Gini / KS / AUC / partial AUC / Brier / ECE with CIs, on **out-of-fold predictions** so every `k` is
   scored on the same rows and DeLong's paired test is valid. **The full curve is a required output.**
4. **Stopping rule, pre-declared:** smallest `k` that is **not statistically distinguishable** from the
   full-candidate model by **DeLong's test** (DeLong, DeLong & Clarke-Pearson, 1988) at α = 0.05, **and**
   whose **relative Gini loss ≤ 5%**. If no `k` qualifies, that is reported as the result — "no parsimonious
   subset meets the tolerance" — not replaced by the best available `k`.
5. **State what the parsimony is for** (interpretability, data cost, model-risk documentation) and quantify
   where possible. Small AUC gaps do not imply a performance win.

**DeLong implementation validated:** AUCs match `roc_auc_score` exactly; self-comparison gives p = 1.0 and
diff = 0; clearly different models give p ≈ 0; near-identical models give p = 0.31 (correctly *not*
distinguishable).

### 6.1 Retrospective consequence for the completed datasets (review M10)

In **Gini** terms — the metric the domain uses:

| Dataset | Selected Gini | Full-pool Gini | Relative Gini loss | Meets ≤5%? |
|---|---:|---:|---:|---|
| PAKDD-2009 | 0.2394 | 0.2832 | −15.5% | **No** |
| German Credit | 0.5302 | 0.5708 | −7.1% | **No** |
| Taiwan | 0.5508 | 0.5646 | −2.4% | Yes |
| HELOC | 0.5884 | 0.5900 | −0.3% | Yes |
| HMEQ | 0.8996 | 0.9014 | −0.2% | Yes |
| GMSC | 0.7304 | 0.7304 | 0.0% | Yes |

**PAK and German Credit must be re-reported:** under the pre-declared tolerance their v2 "final" sets are
not acceptable parsimonious models. A −15.5% relative Gini reduction presented as a success will not survive
review.

---

## 7. Stage 4-5 — Calibration, benchmarks, validation

### 7.1 Calibration [RETAINED, with changes]

Isotonic regression on the **deployed WOE-logistic scorer** (map learned on 5-fold out-of-fold scores; Brier and ECE
before and after are measured on a held-out 20%). Until 2026-10-25 this step trained an XGBoost model instead, so earlier
Stage-4 tables describe the secondary learner (labelled legacy).
Report Brier, ECE and a reliability diagram for **both** selected and full-pool models. With
`scale_pos_weight` now off (§5.2), re-measure: much of v2's ECE damage was self-inflicted. Under the
`brier_skill` value function, calibration enters selection directly and this stage becomes confirmation
rather than repair. Raw scores remain valid for ranking; calibrated probabilities must be used whenever a
probability is quoted to a person.

### 7.2 Benchmarks (review M8a) — implemented, not yet run across datasets

`benchmarks.run_benchmarks` compares, on identical folds and learner: full model, LASSO, elastic-net, RFE,
Boruta, univariate IV top-`k`, permutation importance top-`k`, **TreeSHAP global mean |φ| top-`k`**. The
TreeSHAP comparison is not optional — it is exact and polynomial-time for tree ensembles (Lundberg et al.,
2020), so a referee will ask whether it gives the same ranking far more cheaply. If it largely does, the
contribution becomes the Stage 0 / Stage 3 / null-calibration layers rather than the Shapley computation —
still publishable, but the claim must change.

### 7.3 Stability selection (review M8b)

Bootstrap (B ≥ 200) or 10×5 repeated CV over the **entire** pipeline; report per-feature selection frequency
(Meinshausen & Bühlmann, 2010). Required for every dataset, and especially German Credit (n = 1,000; 300
bads; full-model fold SD ±0.0315 against marginal contributions of 0.005–0.08 — several v2 decisions cannot
be stable at that sample size).

### 7.4 Synthetic ground truth (review M8c) — implemented

`synthetic_validation.make_synthetic` generates data with known support containing every structure the
methodology claims to handle: correlated informative features (ρ configurable), an exact duplicate
(redundancy), a U-shaped feature, an **interaction-only** feature with ~zero marginal signal, a proxy
correlated with both an informative feature and the target, and pure noise. `run_grid` reports **power and
FDR** across sample size, event rate, ρ and `T`. Generator verified: requested event rates 0.05/0.15/0.30
realise as 0.056/0.152/0.295, and `interaction_only` has marginal |corr| with y of 0.09 against
`informative_0`'s 0.32.

### 7.5 Metrics and comparison (review M10, m1)

**Gini is primary.** Report AUC alongside for cross-literature comparability, plus KS, partial AUC, Brier,
ECE. **Every** model comparison gets a test (DeLong or paired bootstrap) — no more gap columns without
inference. The Hosmer-Lemeshow 0.5-0.7/0.7-0.8/0.8-0.9 AUC bands are **removed**: they are a clinical rule of
thumb. Use domain benchmarks (Lessmann et al., 2015); an application scorecard at Gini 0.40-0.50 is often
serviceable, and HMEQ-style Gini ≈ 0.90 reflects a curated dataset with behavioural features, not a realistic
application-scoring ceiling.

### 7.6 Out-of-time validation [DEFERRED, with a scoping requirement]

No dataset in use has a reliable time field. **Required now:** state this and scope every claim to i.i.d.
random cross-validation; do not imply production readiness. `mortgage.csv` (622,489 loan-months with an
explicit `time` index) is the natural vehicle when brought in, and also for a survival/competing-risks
extension.

### 7.7 Multiplicity and pre-registration (review m9)

Disclose the exploratory character of the work to date (six datasets × five categories × several escalation
branches, with thresholds revised mid-study). **Pre-specify** the synthetic study and the benchmark study
before running them, including the selection tolerance and the shadow-bar quantile.

### 7.8 Deployment — scoring and missing-value governance

The selected + calibrated model scores a new application, and the Stage 0 governance decisions (§3.6) are
enforced here. Because the primary learner is WOE-logistic, the score is an **exact additive decomposition**,
`log-odds = intercept + Σ(coefⱼ × WOEⱼ)`, so a calibrated PD comes with faithful per-feature **reason codes**
(no post-hoc approximation). Three controls sit on top, all applied **at scoring** — they do not change
selection or the Stage 1–7 metrics, and complete/honest applicants are unaffected:

1. **Omission floor** (`missing_policy='adverse_floor'`, `floor_columns`). For applicant-influenceable
   columns whose learned `__missing__` WOE is *protective*, the missing bin is floored to the most-adverse
   observed WOE (`binning.adverse_missing_floor`), so disclosing less can never lower predicted risk.
   Flooring must be applied after model fit (flooring before fit corrupts the training representation).
2. **Mandatory gate (primary control)** (`mandatory_columns`, `incomplete_policy='reject'`/`'refer'`). An
   application missing any declared-essential field is **incomplete and not scored** — routed to REJECT/REFER.
   You cannot assess risk on an absent essential field.
3. **Adverse fallback** (`incomplete_policy='adverse_score'`). If a score must still be produced, a blank
   mandatory field is scored at the column's most-adverse observed WOE. The override is applied on the WOE
   vector directly, so it works identically for numeric and categorical columns and sidesteps the
   `__missing__`/`__other__` conflation. **Caveat:** its deterrent scales with the feature's predictive power
   — strong for a dominant column, negligible for a weak one, which isotonic calibration can absorb — so the
   **reject gate is the robust primary control** and `adverse_score` is a fallback only.
4. **Regulatory PD floor & ceiling [STANDARD, always on]** (`build_scorer(pd_floor=0.0003, pd_cap=0.999)`).
   The reported PD is bounded at scoring: **floored at 0.03%** — Basel **CRE32.3** (verified at BIS): PD is the
   *greater of* the internal estimate or 0.03% (corporate/bank; retail mirrors — confirm per exposure class) —
   and capped strictly below a literal 100% (a *defaulted* borrower is assigned PD = 100% directly). This is a
   **mandatory** regulatory control applied like isotonic calibration (§7.1) — not an option. It fixes the
   degenerate ~0% PD that isotonic calibration can emit from a zero-default bin on small data (observed on
   German Credit's safest grade, whose GC4 CI was [0%, 65.8%]). The floor **value** is a documented parameter
   (per class/jurisdiction); the **step** is universal. Applied **at scoring only** — it does not alter the
   Stage 1–4 selection or calibration metrics. *(This step was surfaced as a per-run AEGIS condition, then
   graduated into the methodology once recognised as a necessary universal requirement — the governance→
   methodology feedback loop; cf. §7.9.)*

`missing_governance.build_scorer` returns a `Scorer` whose `.score()` emits, per application,
`decision ∈ {SCORE, SCORE_FLAGGED, REFER, REJECT}` with a calibrated PD and a reason string. The worst-case
WOE used by controls 1–3 is a *policy* value where training has no missing rows for the column, not a learned
estimate. Worked examples: `SHARP_HMEQ.md` (Appendices A–C) and `SHARP_CREDIT_RISK.md` (§3).

### 7.9 Governance operating model (AEGIS)

SHARP is the analytical engine; the decision to *approve and deploy* a SHARP model is governed separately
by **AEGIS** (Approval & Evidence-based Governance for Internal-ratings Systems — full spec in
`AEGIS_GOVERNANCE.md`). AEGIS turns each SHARP stage into a **decision gate** (G0 data/scope, G1 screening,
G2 attribution, G3 selection, G4 calibration/fairness, G5 deployment governance, GF final Go/No-Go): the
engine presents a recommendation + full evidence pack + a *closed set of 2–4 genuinely viable options* (each
with data, rationale, benefits, risks, residual-risk acceptance), an independent role-holder signs exactly
one, and the choice is written to a hash-chained log. Segregation of duties (Developer ≠ Validator ≠
Approver) and a CRO-chaired Model Approval Committee guard against rubber-stamping.

The regulatory acceptance criteria that gate GF were **verified against primary sources** (2026-10-12):
PD history ≥5yr (Basel **CRE36.79**), use test (**CRE36.60**), calibration backtest (**CRE36.122–123**),
Margin of Conservatism categories A/B/C (**EBA/GL/2017/16 §4.4**), independent validation / effective
challenge (**SR 26-2** — which superseded SR 11-7 on 17 Apr 2026), and EU AI Act high-risk obligations
(Annex III §5(b), deadline now 2 Dec 2027). AEGIS maps onto the deployed app's `backend/governance_store.py`
(hash-chained `gov_audit_events`, six-pillar validation sign-offs, state-derived `regulatory_mapping`), the
missing-value controls of §7.8, and the `trainer.py` promotion gate. See `AEGIS_GOVERNANCE.md` for the gate
anatomy, RACI, committee constitution, Go/No-Go engine, and the full verified criteria table.

### 7.10 Fairness identification procedure (G4) [documented]

Fairness is tested at **G4** as a **proxy-leakage test** on the attributes *excluded from the model* at G0
(the `prohibited`, and where relevant `proxy_risk`, columns). Testing an attribute the model does **not** use is
what distinguishes disparate *impact* (reconstructed via correlated features) from disparate *treatment* (direct
use). The procedure is fixed and reported identically across datasets:

1. **Groups.** Partition the held-out test set by the protected attribute's natural bands (e.g. age
   <25 / 25–39 / 40–59 / 60+; sex; foreign-worker yes/no; geography by state/region). A **minimum cell size of
   ≥ 20–25 test rows** is required for a reliable ratio; smaller cells are reported **inconclusive** (e.g. German
   `foreign_worker`; thin SBA state cells).
2. **Decision rate.** Score each applicant, map the calibrated PD to a rating grade, and take the model's
   **favourable (APPROVE) rate** on the internal master scale. This rate is **indicative only** — the real
   accept/decline cutoff is an exogenous institution input and is not set here.
3. **Adverse-impact ratio.** `AIR = (min group favourable rate) / (max group favourable rate)`, tested against the
   **four-fifths rule** (EEOC, ≥ 0.80). Where decision-rate cells are thin, report the **predictive-parity**
   variant instead: each group's mean predicted PD vs a reference group, shown alongside its actual default rate.
4. **True-risk-driven test (the interpretation step).** If AIR < 0.80, compare each group's mean predicted PD
   with its **actual** default rate. If the model is accurate within each group (predicted ≈ observed) and the
   disparity tracks real outcome-rate differences, the disparate impact is **true-risk-driven, not proxy bias**;
   if predictions are systematically off for a group, that is a bias signal. (Observed true-risk-driven: German
   age, LC/CREDITRISK geography, SBA `BankState`.)
5. **Disposition.** Excluding a protected attribute is **necessary but not sufficient** — correlated features
   reconstruct it. A failing-but-true-risk-driven AIR is recorded as a **binding GF condition** (indicative, no
   live use); any live deployment requires a **fairness-constrained replication / less-discriminatory-alternative
   (LDA) search and reject inference** (§3.1 cost-of-compliance study, still future work). Anchors: four-fifths =
   EEOC 29 CFR 1607; the 0.05 mean-PD-gap monitor is operational (`drift_monitor.py`), not a reported bar.

---

## 8. The four diagnostic findings to foreground (review m15)

The most defensible contributions are the concrete failure modes, not the pipeline. Structure the paper
around these:

1. **Category-sequential screening retains artefactual variables** — German Credit (two columns additive
   given `credit_history`, null against the full pool) and PAK.
2. **Sparse-cell inflation of χ²-family effect sizes** — a high-cardinality location field at Cramér's V =
   0.342 collapsing to Gini ≈ 0.06 under model validation.
3. **Rank tests are blind to non-monotonic relationships** — a genuinely U-shaped credit-lines/default
   relationship caught by χ² and missed by Mann-Whitney; now detected automatically (§4.2).
4. **Significance-based importance selection degenerates as evidence accumulates** — more permutation
   samples confirm *every* candidate, because power eventually detects arbitrarily small true effects. Now
   demonstrated in the starkest possible form: a permuted shadow column scoring BH p = 0.0000 with a
   negative Shapley value. The most broadly interesting of the four.

---

## 9. Limitations that remain after v3

1. **Model-conditionality** — importance is relative to a learner. Mitigated by reporting two learners and
   their concordance; not eliminated.
2. **Accept-only samples** — disclosed and qualified (§3.2), not corrected. No reject inference.
3. **No out-of-time validation** until the panel dataset is brought in.
4. **Regulatory-ineligible features retained by project decision** (§3.1); fairness-constrained replication
   deferred.
5. **Shadow nulls are learner- and dataset-specific** — they characterise "no signal under this setup,"
   which is the relevant null, not a universal one.
6. **Grouped Shapley answers questions about groups**; within-group attribution is resolved only for
   retained groups, and group definitions depend on the clustering threshold (sensitivity-tested, not
   eliminated).
7. **Five C's framing is presentational only.** It is kept as data-description scaffolding and drives no
   statistical decision. Either make it load-bearing (test category-blind vs category-aware screening) or
   reduce it to a sentence — an inconsistently-applied decorative element costs credibility for no benefit.
8. **Public benchmark datasets only**, all modest by portfolio standards. Scope claims accordingly.
9. **Benchmarks and stability selection are implemented but not yet run** across the six datasets; until
   they are, no comparative-superiority claim is licensed (§1).
10. **Missingness governance is a manual classification, and its controls have residual limits.** The
    mechanism is now part of the process (§3.6 classification, §7.8 controls), so these are the *residual*
    caveats: (a) the structural-MCAR vs applicant-influenceable split is a documented **manual judgement**,
    not inferred; (b) the omission floor must be applied after model fit (flooring before fit corrupts the
    training representation); (c) the `adverse_score` fallback's deterrent **scales with feature strength** —
    strong for a dominant column, negligible for a weak one that calibration absorbs — so the reject gate is
    the robust control and `adverse_score` is a fallback only; (d) at the encoder level a categorical blank
    is still routed to `__other__` (missing conflated with rare/unseen), which §7.8's scoring-layer override
    works around rather than fixing in `apply_bins`. Worked evidence: `SHARP_HMEQ.md` Appendix B (Finding F6).
11. **Essential-column completeness depends on correct Stage 0 declaration.** The mandatory gate (§3.6, §7.8)
    only protects columns the user declares `mandatory`; an essential column *not* declared still gets the
    numeric-WOE-0 / categorical-`__other__` free pass. There is no automatic detection of which columns
    *ought* to be mandatory — it is a required human input at the start of the run.

---

## 10. Summary — the decision rule in one paragraph

Tag every column for regulatory eligibility and point-in-time availability first, warning on anything
retained that would be inadmissible in practice. Screen each column univariately on monotonic-WOE
Information Value alone, with Cramér's V and p-values reported but not deciding, a reliability gate on
expected cell counts, rank-test escalation only where values are orderable, and automatic escalation to a
model check whenever binning is unstable or the shape looks non-monotonic. Pool the survivors, collapse
correlated clusters into single Shapley players, add permuted shadow players, and estimate order-invariant
importance as Shapley values over cross-validated predictiveness — retaining a player only when it beats the
95th percentile of the shadow null with a bootstrap confirmation frequency of 0.80, never on a p-value.
Then, separately, select: walk the parsimony curve and take the smallest feature set that is statistically
indistinguishable from the full candidate model by DeLong's test and within a pre-declared 5% relative Gini
tolerance — reporting honestly when no subset qualifies. Calibrate the result, report Gini first, and test
every comparison.

---

## 11. Governed execution - the merged SHARP-AEGIS flow (added 2026-10-25)

The stages above are run one at a time under AEGIS. Each stage ends at its gate; the next stage
starts only after the signer has chosen an option and the entry is sealed in the hash chain
(`ml_models/staged_run.py`; `AEGIS_GOVERNANCE.md` Section 11 and 11.1). The merged flow adds
four reports and one running checklist to the stages, with **no change to any pre-registered
parameter**:

- Stage 0 also reports a blank-vs-outcome table (Fisher exact, Bonferroni reference) and a
  look-ahead scan of the column definitions. Both are reports; neither excludes a column.
- Stages 1-3 report EPV and the Riley minimum N on every basis reached (candidate pool, after IV
  screening, confirmed players, selected model) in one table. The **candidate pool** (columns that
  entered Stage 1 after outcome-blind eligibility) is the governing basis; the others are
  informational because they follow outcome-dependent selection (`RILEY_SAMPLE_SIZE.md` section 8).
- Stage 5 (deliverables) reports which scoring controls the data actually exercises.
- One learner (`woe_logistic`) is used for every stage including calibration; XGBoost is no longer part of the governed process.
- The Section 8 checklist (R1-R10) is derived as evidence appears, so the final Go/No-Go reads it.
- Every run ends in a model reliability scorecard (`ml_models/run_scorecard.py`): six dimensions of
  out-of-fold or held-out metrics and a count of the existing cited bars cleared. There is no composite
  score and no cutoff-based metric; two scorecards are compared side by side, not ranked.

Earlier runs were executed one-shot and are not re-run under this flow.
