# AEGIS — MSME (Chinese SME enterprise credit): decisioning note

**Status:** decisioning note · **Date:** 2026-10-14 · **Model:** AEGIS-approved WOE-logistic 6-player (15-column)
model (AEGIS run `AEGIS_RUN_MSME.md`). **MEDIUM-tier reference benchmark — not production-IRB.**

> **Research-integrity note.** No accept/refer/decline PD cutoff and no pricing are prescribed here. The lending
> decision and any pricing are institution risk-appetite inputs, exogenous to this methodology and not derived.

## Scope — corporate/SME, high-dimensional, low-EPV
This is **business/SME credit** (enterprise attributes), not consumer — so **fairness (disparate impact) is N/A**
(no person-level protected attributes; the one geographic feature `Province` was dropped at Stage 2). The run is
the **high-dimensionality / low-EPV stress test**: 87 candidate features against **102 defaults** (EPV ≈ 1.2).

## What this methodology produces (grounded, citable)
Per firm: a **calibrated PD** (isotonic; floored 0.03%; backtested per CRE36.122–123), a **rating grade**, the
**exact WOE reason codes**, and the **governed completeness decision**. See `SAMPLE_RUNS_MSME.md`.

## The binding caveat — EPV fragility (EPV1 / MoC-epv)
With only 102 defaults, the model's numbers are **uncertain**:
- Selection Gini 0.4347 but **95% CI [0.339, 0.539]** (±0.10 wide).
- Per-grade backtest: 7/8 grades within CI, HL (5-bin) p=0.345 — but grade **D rests on n=2**, CIs are enormous
  (CC spans 24–76%), and HL had to be reduced from 10 bins to 5 for power.
- The synthetic `SYN-worst` stress case could not be constructed coherently (per-feature extremes net to low
  risk) — the model has no stable "worst case" at this EPV.

**→ Margin of Conservatism (MoC-epv): treat all PDs as *indicative, not precise*, especially the risky tiers
(CC/D). This model is a methodological benchmark, not a basis for live SME lending decisions.**

## What the stress test showed (the positive result)
SHARP's guardrails held: **87 features → 6 players (15 columns)**. Shadow-null retention correctly rejected the
inflated-IV sparse-count features (patents/copyrights at univariate IV 0.6–0.88 — small-sample artifacts) and the
`Province` proxy, rather than overfitting 87 columns to 102 events.

## Citations still required before publication
- Rating-grade band edges (PD→grade) — cite the external scale or state as the institution's internal scale.
