# AEGIS — PAK (PAKDD-2009 Brazilian retail credit): decisioning note

**Status:** decisioning note · **Date:** 2026-10-13 · **Model:** AEGIS-approved WOE-logistic 6-column benchmark
(AEGIS run `AEGIS_RUN_PAK.md`). **MEDIUM-tier reference benchmark — explicitly NOT for a live credit decision.**

> **Research-integrity note.** This note prescribes **no** accept/refer/decline PD cutoff and **no** pricing.
> The accept / refer / decline **lending decision and any pricing are institution risk-appetite inputs,
> exogenous to this methodology and not derived here** (consistent with every other run in this work).

## What this methodology produces (grounded, citable)
For each applicant: a **calibrated PD** (isotonic; floored at 0.03% per Basel CRE32.3; backtested per
CRE36.122–123 — HL p=0.382, 5/5 populated grades within CI), a **rating grade / risk tier** (institution
internal master scale), the **exact WOE reason codes** (ECOA/Reg B adverse-action), and the **governed
completeness decision** (SCORE / SCORE_FLAGGED / REFER / REJECT from the mandatory-field + missing-value gate).
See `SAMPLE_RUNS_PAK.md` for the per-candidate showcase.

## What is an institution input (NOT derived here)
- The **accept / refer / decline PD threshold(s)** — set by the institution's risk appetite and economics.
- Any **pricing** of the loan.

## PAK-specific caveats the committee must read alongside any decision
1. **The model barely discriminates (Gini 0.148, AUC 0.584).** On the backtest, 8,665 of 10,000 applicants land
   in a single grade (CC, at the ~26% base rate); the acceptance pack shows all four representative real
   applicants compressing into grades CC–C. **The model cannot reliably separate a good applicant from a bad
   one** — it must not drive a lending decision. Its value is as a governed benchmark and a fairness study.
2. **Two selected features are flagged geographic proxies** (`RESIDENCIAL_PHONE_AREA_CODE`, `PROFESSIONAL_STATE`)
   — redlining risk, retained only for benchmark comparability, **not suitable for live use**. A fairness-
   constrained 4-column replication (Gini 0.1175) is reported as the headline alternative (`AEGIS_RUN_PAK.md` G3/G4).
3. **Adverse floor on `PROFESSIONAL_STATE`** (68.6% missing, missing-protective) closes an omission trap; on a
   model this weak the floor visibly re-ranks missing-value applicants (see `SAMPLE_RUNS_PAK.md`).

## Citations still required before publication
- **Rating-grade band edges** (PD→grade) — cite the external scale they align to (e.g. S&P/Moody's idealised
  cumulative default rates) or state them explicitly as the institution's internal scale.
- **Fairness:** the adverse-impact ratio (AIR ≥ 0.80) uses the EEOC Uniform Guidelines "four-fifths rule"
  (citable) — but it is **degenerate/uninformative on PAK** (near-zero approve-grade population); the reported
  fair-lending read relies on the **mean-PD gap + predictive parity**. The 0.05 mean-PD-gap monitor threshold is
  an operational setting, not a standard — cite or reframe.
