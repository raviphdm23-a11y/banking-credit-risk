# PROVENANCE — methodology evolution & learning trail (literature-review source map)

**Purpose.** This folder preserves the full development history of the credit-risk feature-selection and
governance methodology — *what we tried, what worked, what didn't, what was critiqued, and what changed.*
Nothing here is dead weight: it is the raw material for the **literature review / methodology-evolution**
section of the paper. The *operative* documents live one level up in `paper analysis/draft one/`
(`METHODOLOGY.md`, `AEGIS_GOVERNANCE.md`, `USER_JOURNEY.md`, the `SHARP_*.md` runs); everything in `archive/`
is the trail that led to them.

Read this file first; it narrates the phases and maps every archived file to the lesson it records.

---

## The arc in one paragraph

The work began as a **manual "Five C's" column-usefulness screen** (domain categorisation + Information Value
/ Cramér's V + a reliability gate + a Mann-Whitney escalation). That was interpretable but had concrete
failure modes, so it was replaced by a **Shapley-based importance method (v2)** that selected features by
statistical significance (Benjamini-Hochberg p-values + Cohen's d). An **external expert review** (M1–M10
below) then showed the v2 construction was mis-specified in several ways — most seriously, significance-based
selection *degenerates* (a permuted noise column scored BH p ≈ 0), it conflated attribution with selection,
and it retained protected/proxy attributes with no fair-lending treatment. The review drove a full rewrite
into **SHARP (Shapley Ranking with Parsimony) v3**: shadow-null retention instead of significance, an explicit
attribution→selection split, grouped coalitional players, availability flags, and benchmark/stability/
synthetic validation. SHARP was then wrapped in **AEGIS**, a governed human+machine approval lifecycle (gates
G0–GF, fairness gates, calibration backtests, PD floor, decisioning policy, committee-reviewed sample runs).
A separate but related lineage is the **"Do AI Explanations Survive Falsification?" / Sanity-Ratio paper**,
whose original results suffered SMOTE-before-split leakage and are being rebuilt via the ML Lab
(`RESULTS_LOG.md`, kept in the main folder).

---

## Timeline of phases

| Phase | ~Date | What it was | Superseded by | Archived under |
|---|---|---|---|---|
| **1. Five C's column-usefulness** | 2026-10-08/09 | Manual domain categorisation + IV/Cramér's V + reliability gate + Mann-Whitney escalation; per-dataset `*_FINDINGS.md` | SHARP Stage 0–1 | `01_five_c_methodology/` |
| **2. Shapley importance v2** | 2026-10-08/09 | SPVIM/retrain-based Shapley + significance selection (BH p + Cohen's d); raw outputs as JSON | SHARP Stage 2 (shadow-null) | `02_v2_shapley_and_benchmarks/` |
| **3. External expert review** | 2026-10-09 | Independent methodological critique (M1–M10) + summary | drove the v3 rewrite | `03_expert_review_and_v3_spec/` |
| **4. SHARP v3 spec & implementation** | 2026-10-09/11 | The reviewed v3 specification, an implementation-status map, and early v3 one-off artifacts | operative `METHODOLOGY.md` + `SHARP_*.md` | `03_…` and `04_v3_one_offs/` |
| **5. SHARP runs + AEGIS governance** | 2026-10-11/13 | Clean per-dataset SHARP runs + the AEGIS approval framework | *current / active* | *(main folder)* |

---

## The expert review's M1–M10 → what SHARP v3 changed

This table is the heart of the methodology-evolution story (source: `03_.../EXPERT_REVIEW_OF_METHODOLOGY.md`).

| # | What the review criticised (v2) | How SHARP v3 / AEGIS resolved it |
|---|---|---|
| **M1** | Conflates **attribution** with **selection** | Explicit split: Stage 2 = order-invariant Shapley *attribution*; Stage 3 = parsimony *selection* under a pre-declared tolerance |
| **M2** | Mis-cited as **SAGE**; it is actually **SPVIM** / retrain-based Shapley | Re-described correctly as SPVIM-style; efficiency property reported as an implementation audit |
| **M3** | Inference mis-specified; the **Cohen's-d fix was a patch** | Significance rule **withdrawn**; replaced by **shadow-null retention** (a feature must beat a permuted-copy null bar; demonstrated a permuted shadow scoring BH p ≈ 0 to prove the point) |
| **M4** | **Protected/proxy attributes retained** with no fair-lending treatment (most damaging in a credit venue) | AEGIS G0 excludes ECOA-prohibited attributes before modelling; G4 computes disparate impact on proxies; Taiwan run actually *dropped* a selected proxy (EDUCATION) |
| **M5** | Accepted-only samples; **no reject inference**; PAKDD income finding likely a truncation artefact | Documented as a residual limitation; flagged for reject-inference in future work |
| **M6** | **Near-target / cross-model features** inflate results; point-in-time availability unaddressed | Stage-0 **availability flags** (`near_target`, `external_score`); "report with and without" conditions (Taiwan PAY_0, HELOC ExternalRiskEstimate) |
| **M7** | **Correlation pre-pruning** defeats the purpose of Shapley | **Grouped coalitional players**: correlated columns become one Shapley player (the `grp[...]` coalitions) instead of being pruned |
| **M8** | No **benchmark / stability / ground-truth** validation | Benchmarks, stability selection, and synthetic ground-truth added to the methodology (§7.2–7.4) |
| **M9** | **Value function** (full-range AUC, ranking-only, fixed hyperparameters) is weak | Documented; value function stated explicitly; two learners reported (WOE-logistic primary, XGBoost secondary) |
| **M10** | **Parsimony/performance trade-off under-argued**; 2 of 6 v2 results not favourable | Pre-declared selection tolerance (DeLong p≥0.05 **and** ≤5% Gini loss); unfavourable results reported honestly (no-extrapolation rule) |

---

## What worked / what didn't (for the discussion section)

**Worked and kept:**
- Shadow-null retention (robust to the significance-degeneration failure mode).
- The attribution→selection split with a pre-registered parsimony tolerance.
- Grouped coalitional players for correlated features.
- Isotonic calibration as a standard step; later the PD floor (Basel CRE32.3) as a standard step.
- The governance→methodology feedback loop (controls surfaced in AEGIS that proved universal were graduated
  into SHARP — e.g., the PD floor).

**Tried and withdrawn / flagged as failure modes (good discussion material):**
- v2 **significance-based importance selection** — degenerates as evidence accumulates (a permuted shadow
  column scored BH p ≈ 0 with a negative Shapley value).
- **Category-sequential Five C's screening** — retained artefactual variables (e.g., German Credit columns
  additive given `credit_history`).
- **Sparse-cell χ²-family inflation** — a high-cardinality location field at Cramér's V = 0.34 collapsing to
  Gini ≈ 0.06 under model validation.
- **Rank tests blind to non-monotonic relationships** — a genuinely U-shaped relationship missed by
  Mann-Whitney, caught by the shape check.
- **SMOTE-before-split leakage** (the original Sanity-Ratio paper) — rebuilt via the ML Lab.
- **An exact-Shapley gate option** offered during an AEGIS run — a methodology-vs-governance category error,
  corrected and codified as AEGIS principle P8 (gates decide governance, not analytics).

---

## File index (what each archived file is, and the lesson it records)

### `01_five_c_methodology/` — Phase 1 (manual column-usefulness)
- `HMEQ_FINDINGS.md`, `GERMAN_CREDIT_FINDINGS.md`, `GMSC_FINDINGS.md`, `HELOC_FINDINGS.md`, `PAK_FINDINGS.md`,
  `TAIWAN_FINDINGS.md` — per-dataset Five C's results; the source of the four foregrounded failure modes.
- `DATASET_TRACKER.md` — status board (its header already marks all results v2/SUPERSEDED).
- `TAIWAN_SHAPLEY_PROGRESS.md` — a progress note from the transition to Shapley.

### `02_v2_shapley_and_benchmarks/` — Phase 2 (Shapley v2 raw outputs)
- `{hmeq,taiwan,heloc,gmsc}_v2_shapley_results.json` + `*_analysis.json`, `german_credit_shapley_*.json`,
  `pak_v2_shapley_analysis.json` — the v2 Shapley runs selected by significance (the method M3 withdrew).
- `gpu_cpu_benchmark_*.json` — early compute benchmarks.
- `calibration_results.json`, `v3_synthetic_grid.csv` — early calibration/synthetic experiments.

### `03_expert_review_and_v3_spec/` — Phases 3–4 (critique → spec)
- `EXPERT_REVIEW_OF_METHODOLOGY.md` — **the external review (M1–M10)**; the single most important provenance
  document for the methodology-evolution narrative.
- `METHODOLOGY_SUMMARY_FOR_EXPERT_REVIEW.md` — the summary handed to the reviewer.
- `METHODOLOGY_V2_ARCHIVED.md` — the pre-review (v2) methodology.
- `METHODOLOGY_V3_REVIEWED.md` — the reviewed v3 specification (the formal spec `METHODOLOGY.md` operationalises).
- `V3_IMPLEMENTATION_STATUS.md` — maps the v3 spec to what landed in code (verification evidence).

### `04_v3_one_offs/` — Phase 4 (early v3 artifacts, superseded by `SHARP_HMEQ.md`)
- `V3_MODELCARD_HMEQ.md`, `V3_RUN_HMEQ.md`, `V3_SYNTHETIC_VALIDATION.md` — first v3 outputs before the
  standardised `SHARP_<DATASET>.md` record convention.

---

## SHARP v3 → v3.1 (2026-10-17) — Riley minimum-N added as a reported G1 diagnostic
- Added the **Riley et al. minimum-sample-size calculation** alongside EPV as a *reported* data-sufficiency
  diagnostic at Stage 1 / AEGIS G1 (never auto-reject). No selection parameter changed; all v3 runs reproduce
  identically. Engine `backend/riley_minsize.py` (Python/venv310; validated against BMJ m441 worked examples
  and the pmsampsize C→R²cs pairing). Reference artifact `RILEY_SAMPLE_SIZE.md` + regenerable
  `sharp_runs/riley_retro.json` hold the retrospective across all 11 governed runs. Finding: one SHORT (MSME,
  needs 3,654 vs 1,707) — concordant with its EPV failure (6.8) and its existing NO-GO·HIGH verdict; TH02
  passes thinly (+55). Spec edits: `METHODOLOGY.md` §4.6 + header v3.1; `AEGIS_GOVERNANCE.md` G1 row +
  per-criterion/composition tables. Citations: Riley 2019 (Stat. Med. 38(7)), Riley 2020 (BMJ 368:m441),
  Riley–Van Calster–Collins 2020 (Stat. Med. 39(21)), van Smeden 2019 (Stat. Methods Med. Res. 28(8)).

## German run superseded: Statlog → South German (corrected), 2026-10-20
- The German corpus run was **re-based from the Statlog German Credit data onto its error-corrected recoding**,
  **South German Credit** (Grömping 2019, UCI #522; CC BY 4.0) — same 1,000 loans, 30.0% bad rate, 20 variables,
  with Grömping's category-coding errors fixed. Treated as a **draft-stage input correction**, NOT reported as a
  finding in the paper (the paper is unpublished/unversioned; a before/after note would only confuse readers).
- **Result reproduces the committed verdict:** GO-WITH-CONDITIONS, k=5, Gini 0.542 (was 0.5317), sex AIR clean
  (0.933), age AIR fails four-fifths but true-risk-driven (0.340). Only *improvement* from the corrected coding:
  grade BB no longer fails its backtest (8/8 vs 7/8), so the old `DQ-BB` condition drops. Selected 5th feature is
  now `credit_amount` (was `purpose`) — a near-tie reshuffle. New code-sealed chain
  `GEN-GERMAN0 → eeaa6cd7 → 670b8e1a → f8a3cfab → 0c9b65dd → 1ac12b5e → 496d214e → GF a92fa411`
  (gates emitted by `ml_models/aegis_gates.py`).
- **Archived here** (`archive/german_statlog_superseded/`): the Statlog run records — `AEGIS_RUN_GERMAN.md`,
  `SHARP_GERMAN.md`, `AEGIS_GERMAN_CUTOFF_POLICY.md`, `SAMPLE_RUNS_GERMAN.md`, `german.json`. **Datasets archived**
  to `data/ml_lab/datasets/archive/`: `german_clean.csv`, `german_credit_record.csv` (the Statlog copies; old
  Sanity-Ratio ML-Lab lineage in `RESULTS_LOG.md` references these archived paths).
- **New canonical files** (main folder): corrected `SHARP_GERMAN.md`, `AEGIS_RUN_GERMAN.md`,
  `AEGIS_GERMAN_CUTOFF_POLICY.md`, `SAMPLE_RUNS_GERMAN.md`, `acceptance_cases/german.json`; new dataset
  `data/ml_lab/datasets/south_german_credit_en.csv` (English-renamed) from source `south_german_credit.csv`.
  Paper citation updated Statlog `german1994` → `groemping2019`.

## Kept in the main folder (NOT archived — still forward-useful)
- `METHODOLOGY.md`, `AEGIS_GOVERNANCE.md`, `USER_JOURNEY.md` — operative framework.
- `SHARP_*.md`, `AEGIS_RUN_*.md`, `AEGIS_*_CUTOFF_POLICY.md`, `SAMPLE_RUNS_*.md`, `acceptance_cases/`,
  `sharp_runs/` — the current governed runs and artifacts.
- `CALIBRATION_NOTES.md` — a standalone calibration literature review (directly reusable for the paper).
- `BIBLIOGRAPHY.md` — reference list.
- `RESULTS_LOG.md` — results log for the related "Do AI Explanations Survive Falsification?" paper (separate
  active workstream).
- `SHARP_CREDIT_RISK.md` — a SHARP-era data-integrity demonstration (not a completed run; kept as a reference
  example of the G0 data-integrity concern).
