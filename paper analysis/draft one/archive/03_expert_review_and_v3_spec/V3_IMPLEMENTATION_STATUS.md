# SHARP (Shapley Ranking with Parsimony) — v3 implementation status

Written 2026-10-10. Maps every item in `METHODOLOGY_V3_REVIEWED.md` section 9 (the implementation brief) to
what actually landed in code, with verification evidence. Read alongside `METHODOLOGY.md` (the operative
methodology) and `EXPERT_REVIEW_OF_METHODOLOGY.md` (the review that drove it).

Legend: **DONE** implemented and verified · **PARTIAL** implemented, not yet run at scale · **DEFERRED**
specified, deliberately not built yet.

---

## 1. Module inventory

| Module | Status | Lines | Purpose |
|---|---|---:|---|
| `ml_models/feature_governance.py` | DONE | ~260 | Stage 0 eligibility/availability tags, warnings, disclosure |
| `ml_models/binning.py` | DONE | ~493 | Monotonic WOE binning, IV sensitivity, shape detector, sentinel tooling, `WOEEncoder` |
| `ml_models/shapley_utils.py` | DONE | ~480 | Grouped players, shadow null, pluggable learner/value fn, exact+sampled |
| `ml_models/selection.py` | DONE | ~290 | DeLong test, parsimony curve, pre-declared stopping rule |
| `ml_models/v3_pipeline.py` | DONE | ~400 | Stage 1 screening + Stages 0-4 orchestration + reporting |
| `ml_models/benchmarks.py` | PARTIAL | ~280 | 8 comparators incl. TreeSHAP; smoke-tested, not run across all datasets |
| `ml_models/synthetic_validation.py` | PARTIAL | ~230 | Ground-truth generator + power/FDR grid; first cells running |
| `ml_models/trainer.py` | DONE | edited | `scale_pos_weight` now opt-in; calibration retained |

Pre-existing modules left deliberately untouched: `feature_screening.py` (Boruta/SMOTE paths still used by
`dataset_lab.py` and `tuning.py`), `dataset_lab.py`, `tuning.py`. **Regression-checked:** all 11 modules
import cleanly and `dataset_lab.py` still runs end to end.

---

## 2. Brief item -> implementation

### 9.1 `feature_governance.py` — **DONE**
`classify_columns` tags eligibility (`permissible`/`prohibited`/`proxy_risk`/`unclear`) and availability
(`origination`/`behavioural`/`near_target`/`external_score`) by name-pattern rules with per-dataset
overrides. `warn_on_retained_ineligible` emits one `UserWarning` per retained ineligible column and is wired
into the pipeline's final-model path; `availability_warnings` does the same for `near_target` /
`external_score`. `disclosure_block` emits the verbatim section-10.3 text; `flagged_name` produces the
ASCII table marker (`AGE [prohibited]` — ASCII rather than a glyph because the project runs on cp1252
Windows consoles). **No column is ever dropped here**, per the project decision.

Verified counts: PAK 19/51 ineligible · Taiwan 4/23 · German Credit 5/20 · GMSC 2/10 · HMEQ 0/12. Two
false positives found and fixed during testing: `NumberRealEstateLoansOrLines` matched "state" via
realE-**state**, and any "capacity"-style name would match "city" — both resolved with letter-boundary
lookarounds.

### 9.2 Binning and screening upgrades — **DONE** (in `binning.py`, not `feature_screening.py`)
Placed in a new module rather than rewriting the 239-line `feature_screening.py`, whose Boruta/SMOTE paths
are live dependencies of `dataset_lab.py`. `feature_screening.compute_iv` is untouched, so no existing call
site changed behaviour.

- `woe_bin` — monotonic WOE binning, monotonicity enforced **only where supported**, missing always its own
  bin, discrete/count columns on raw levels with rare-level pooling.
- `iv_sensitivity` — IV at WOE + 5/10/20 quantile bins, `binning_sensitive` flag on verdict flip.
- **Non-monotonic shape detector [addition beyond the brief]** — compares IV with and without the
  monotonicity constraint; ≥20% recovered IV sets `shape_nonmonotonic`. **Fires on exactly the three columns
  v2 independently identified as shape-anomalous:** HMEQ `CLNO` (37.9% IV cost), HMEQ `LOAN` (25.0%), GMSC
  `DebtRatio` (73.7%).
- `detect_sentinels` / `sentinel_lift` / `extract_sentinel_indicators` / `thin_file_indicator`.
- `WOEEncoder` — leakage-safe fit/transform (bins and WOE values learned on the training fold only, unseen
  levels map to neutral WOE 0.0).

IV validation against v2's figures: GMSC `NumberOfTimes90DaysLate` 0.8834 (exact match), `age` 0.2487 vs
0.2584, `MonthlyIncome` 0.0710 vs 0.0739. The one large intentional change is GMSC
`NumberRealEstateLoansOrLines`: 0.0569 on raw levels vs 0.0123 under v2's quantile cuts — the raw-level read
is where its genuine U-shape lives.

### 9.3 `shapley_utils.py` rework — **DONE**
- **Grouped players** — all subset logic operates on column groups, not columns.
- `cluster_players` — hierarchical clustering on `1 − |Spearman ρ|`, cut at 0.7; `vif_report` flags VIF > 10.
  Replaces v2's greedy pairwise pruning. Observed working: HMEQ collapsed `MORTDUE`+`VALUE` into
  `grp[MORTDUE+VALUE]`.
- `make_shadows` + shadow-quantile bar + bootstrap `confirmation_frequency` — the new retention rule.
- **BH p-value and Cohen's d demoted to `diag_*` reported fields; the `keep` flag they drove is deleted.**
- Pluggable `value_fn` (`auc` / `partial_auc` / `brier_skill`, each with the correct `v(empty)`) and
  `learner` (`woe_logistic` primary, `xgboost` secondary, `scale_pos_weight` forced off).
- Repeated stratified CV; per-player Monte Carlo SE; `target_mc_se` for precision-driven `T`.
- Efficiency check relabelled `implementation_audit` with the "validates arithmetic, not accuracy" note.
- Checkpointing retained.

**Performance work not in the brief but required to make it usable:** a column's WOE bins/values depend only
on (column, training fold), not on the subset, so every (fold, column) WOE vector is computed once and reused
across all subsets — leaving only a cheap logistic fit per subset. Statistically identical (bins still fitted
on training folds only). German Credit: 26 players, 2,316 subsets, 11,575 fits, **55 s**.

**The most useful verification result.** In the German Credit run the permuted shadow column
`__shadow__1_credit_amount` received **BH p = 0.0000** with a **negative** Shapley value, and
`__shadow__2_installment_rate` got BH p = 0.0000 with Cohen's d = 0.58. A significance-based rule would have
confirmed pure noise; the shadow bar (0.00297) rejected all eight shadows correctly. This is the clearest
possible demonstration of why review finding M3 was correct.

### 9.4 `selection.py` — **DONE**
- `delong_test` — fast DeLong (Sun & Xu 2014 form of DeLong et al. 1988). **Validated:** AUCs match
  `roc_auc_score` exactly; self-comparison p = 1.0 with diff = 0; clearly-different models p ≈ 0;
  near-identical models p = 0.31 (correctly *not* distinguishable).
- `score_report` — Gini (primary, with bootstrap CI), KS, AUC, partial AUC, Brier, ECE. Probabilities
  clipped for Brier/ECE so passing raw scores degrades those metrics rather than crashing a long run.
- `oof_predictions` — out-of-fold predictions so every `k` is scored on the same rows and DeLong is paired.
- `parsimony_curve` + `select_parsimonious` + `curve_markdown`. The "no subset meets the tolerance" branch is
  implemented and returns that as a result, not a fallback `k`.

### 9.5 `trainer.py` — **DONE**
`scale_pos_weight` is opt-in via `use_scale_pos_weight` (default off). **Measured on GMSC:** ON gives mean
predicted probability 0.286 against a true base rate of 0.067 (4.3× inflation); OFF gives 0.0673.
Independently, German Credit's full-model **raw** Brier is now 0.1648 — essentially v2's *calibrated* 0.1664,
with no calibration step. Review item m8 confirmed: the calibration damage was self-inflicted. Calibration
functions and the GPU/CPU device auto-selection are untouched.

### 9.6 `benchmarks.py` — **PARTIAL**
Eight comparators on shared folds/learner: `full_model`, `lasso_select`, `elasticnet_select`, `rfe_select`,
`boruta_select`, `iv_topk`, `permutation_topk`, `treeshap_topk`, plus `rank_concordance` (Kendall's τ) for
the learner-vs-learner and value-function-vs-value-function checks. Smoke-tested on German Credit:

| method | n | Gini |
|---|---:|---:|
| iv_threshold | 15 | 0.5668 |
| full_model | 20 | 0.5660 |
| lasso | 19 | 0.5660 |
| permutation_positive | 19 | 0.5660 |
| treeshap_meanabs | 7 | 0.5491 |

Already informative: TreeSHAP mean|φ| at 7 features is within 3.0% relative Gini of the full 20-column model
— which is precisely the cheap-comparator question a referee will ask. **Not yet run across all six
datasets**, so no comparative-superiority claim is licensed.

### 9.7 `synthetic_validation.py` — **PARTIAL**
`make_synthetic` builds data with known support containing every structure the methodology claims to handle:
correlated informative features (ρ configurable), an exact duplicate, a U-shaped feature, an
**interaction-only** feature, a proxy of an informative feature, and pure noise. Verified: requested event
rates 0.05/0.15/0.30 realise as 0.056/0.152/0.295 (an intercept-solver parenthesis bug was found and fixed
here); `interaction_only` has marginal |corr| with y of 0.087 against `informative_0`'s 0.318.
`run_grid` reports power/FDR across n, event rate, ρ and `T`; `grid_markdown` formats it.

First completed cell (n = 2,000, ρ = 0.0, T = 150): **power 1.00, FDR 0.00** — all 8 truly-predictive
features confirmed, zero noise features admitted. Remaining cells running; results land in
`V3_SYNTHETIC_VALIDATION.md` and `v3_synthetic_grid.csv`.

### 9.8 Reporting — **DONE**
`v3_pipeline.build_report` emits the full section-10.1 report (governance table, Stage-1 table with
sensitivity and escalation columns, Stage-2 player table with shadow bar and diagnostics, parsimony curve,
selected set with eligibility markers, calibration, disclosure block, availability caveats).
`model_card_markdown` emits the section-10.2 card including the dedicated "regulatory-ineligible features
retained" field. A local `_md_table` helper avoids adding `tabulate` as a dependency.

Example outputs committed: `V3_RUN_HMEQ.md`, `V3_MODELCARD_HMEQ.md`.

### 9.9 Retrospective re-runs — **DEFERRED** (code ready, runs not done)
| Required re-run | Status |
|---|---|
| PAK + German Credit re-reported against the ≤5% Gini tolerance (both currently fail) | Pending |
| PAK income conclusion rewritten per accept-only truncation | **Text correction already carried into `METHODOLOGY.md` §3.2** |
| Taiwan with/without `PAY_0`; HELOC with/without `ExternalRiskEstimate` | Pending |
| GMSC `96`/`98` leakage resolution | Pending — flagged automatically by `detect_sentinels` |
| Stability selection for all six | Pending (§7.3) |
| Gini/KS/DeLong reporting for all six | Pending |

---

## 3. End-to-end verification

`v3_pipeline.run_pipeline` on HMEQ, 85 s total:

- Stage 0: 12 columns tagged, 0 ineligible, 5 behavioural.
- Stage 1: 11 of 12 pass (`REASON` rejected); 2 columns required escalation.
- Stage 2: 10 real players (from 11 columns — `MORTDUE`+`VALUE` grouped) + 6 shadows, sampled mode, 1,249
  subsets, 6,240 fits.
- Stage 3: parsimony curve computed for k = 1..10; **no k below 10 was statistically indistinguishable from
  the full model** (DeLong p < 0.05 for k = 1..9), so k = 10 selected at 0.00% relative Gini loss.
- Result: 11 columns selected — **independently reproducing v2's HMEQ answer (11 of 12, dropping `REASON`)**
  through an entirely rebuilt pipeline.

That agreement on a dataset where v2's answer was already known, combined with the shadow-null correctly
rejecting noise that the old significance test would have confirmed, is the main evidence that the rebuild is
sound rather than merely different.

---

## 4. Known gaps and judgement calls made during implementation

1. **Shadow replications are bootstrapped, not re-run.** The spec called for R ≥ 20 full re-runs with fresh
   shadow seeds. Bootstrapping the existing per-player estimate distribution against a bootstrapped shadow
   bar answers the same question at a small fraction of the compute. Documented in `METHODOLOGY.md` §5.4;
   flag it if a reviewer wants literal re-runs.
2. **`cv_repeats` defaults to 1-2, not 5×5.** Repeated CV mattered in the spec mainly to fix the invalid
   fold-level t-test, which no longer exists — the shadow null is what makes inference valid. Repeats now
   only reduce `v(S)` variance, at linear cost. Raise it for final reported runs.
3. **Adding shadows usually forces sampled mode** (a 13-column pool plus 10 shadows is 23 players, far past
   exact's reach). This is expected and is why the exact/sampled distinction matters less in v3 than v2.
4. **`partial_auc` band is parameterised but not yet defaulted to a business cutoff** — currently
   `max_fpr=0.5`. Set it from an actual approval-rate band when one is specified.
5. **Five C's categorisation is not implemented in code at all** — by design. It drives no statistical
   decision (`METHODOLOGY.md` §9 item 7), so encoding it would imply a role it does not have.
6. **`GMSC.csv` is sorted by target** (discovered while testing). All splits use
   `StratifiedKFold(shuffle=True)`, so nothing is affected, but any future non-shuffled split would be
   catastrophic.
