# AEGIS — TH02 (UK consumer credit; Thomas/Edelman/Crook 2002): decisioning note

**Status:** decisioning note · **Date:** 2026-10-14 · **Model:** AEGIS-approved WOE-logistic 6-feature model
(AEGIS run `AEGIS_RUN_TH02.md`). **MEDIUM-tier research benchmark — not production-IRB.**

> **Research-integrity note.** No accept/refer/decline PD cutoff and no pricing are prescribed here. The lending
> decision and any pricing are institution risk-appetite inputs, exogenous to this methodology and not derived.

## Scope — consumer credit, clean data, weak signal
UK consumer credit (Thomas, Edelman & Crook, *Credit Scoring and its Applications*, 2002; part of the Lessmann et
al. 2015 benchmark suite). This is the **literature-benchmarkable clean run** — the deliberate contrast to MSME:
**healthy EPV (323 defaults / 14 features ≈ 23), 0% missing**, so the model's uncertainty is **genuine signal
weakness, not data insufficiency.** Consumer credit → **fairness live**; age (`YOB`) retained under the ECOA /
Regulation B **EDDSS exception** for literature comparability (G0 Option A).

## What this methodology produces (grounded, citable)
Per applicant: a **calibrated PD** (isotonic; floored 0.03% CRE32.3), a **rating grade**, the **exact WOE reason
codes**, and the **governed completeness decision** (`DAINC` mandatory → refer if blank). See `SAMPLE_RUNS_TH02.md`.

## The binding caveats
- **SIG1 — discrimination ceiling.** Selection **and** holdout Gini both **0.272** (AUC ~0.636), CI [0.199, 0.339].
  The number is *low but reliable* (tight CI, confirmed out-of-sample); adding every remaining feature does not move
  it. **Benchmark-grade separation only.**
- **MoC-cal — calibration not adequate.** Hosmer-Lemeshow **rejects at 5%** (p = 0.025 / 0.012); grade B is
  over-optimistic (predicted 9% vs observed 33%, n=15). **→ treat all PDs as *indicative*, not precise; recalibrate
  before any use.**
- **COVERAGE — no investment grade.** On a 26%-default book the model populates only speculative/distressed grades
  (B→D); even the best synthetic composite reaches only grade B. The model cannot identify clearly-good applicants.

## Fairness disposition (EDDSS satisfied)
The age factor **penalises the young, not the elderly** — under-30s default 54% and are scored worst (empirically
justified); applicants 62+ receive *protective* WOE, so **the EDDSS "no negative factor for the elderly" condition
is met**. AIR-on-approval is degenerate (the weak model approves no one), so there is no favourable-outcome
disparity to measure. **Governance flag (AGE-REASON):** because age carries signal, `YOB` can surface as a
*principal adverse-action reason* for young applicants — a reason that should not be cited as "age" in a live
adverse-action notice. Reinforces the benchmark-only framing. **Data-quality note:** `YOB` holds a few implausible
values (10, 99); negligible count.

## Citations still required before publication
- Rating-grade band edges (PD→grade) — cite the external scale or state as the institution's internal scale.
- Lessmann et al. (2015) / Thomas et al. (2002) published benchmark figure for this dataset, before claiming any
  gap against our honest no-leakage Gini (~0.27). Not yet independently retrieved.
