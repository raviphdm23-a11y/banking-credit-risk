# AEGIS — HMEQ (Home Equity): decisioning note

**Status:** decisioning note · **Date:** 2026-10-13 (revised — pricing removed) · **Model:** AEGIS-approved
WOE-logistic 11-column model (AEGIS run `AEGIS_RUN_HMEQ.md`).

> **Revision note (research integrity).** An earlier version of this file prescribed specific accept/refer/
> decline **PD cutoffs** and an **indicative interest rate**, derived from assumed economics (LGD, cost, margin,
> rate caps). Those parameters had **no literature or empirical basis** and have been **removed**: the
> accept / refer / decline **lending decision and any pricing are institution risk-appetite inputs, exogenous
> to this methodology and not derived here.**

## What this methodology produces (grounded, citable)
For each applicant: a **calibrated PD** (isotonic; floored at 0.03% per Basel CRE32.3; backtested per
CRE36.122–123), a **rating grade / risk tier** (institution internal master scale), the **exact WOE reason
codes** (ECOA/Reg B adverse-action), and the **governed completeness decision** (SCORE / REFER / REJECT from
the mandatory-field + missing-value gate). See `SAMPLE_RUNS_HMEQ.md` for the per-candidate showcase.

## What is an institution input (NOT derived here)
- The **accept / refer / decline PD threshold(s)** — set by the institution's risk appetite and economics.
- Any **pricing** of the loan.
The methodology's role is to supply a trustworthy, explainable PD + grade + reasons that *feed* those
institution-set thresholds; it does not set or price them.

## Citations still required before publication
- **Rating-grade band edges** (PD→grade) — cite the external scale they align to (e.g., S&P/Moody's idealised
  cumulative default rates) or state them explicitly as the institution's internal scale.
- **Fairness:** the adverse-impact ratio (AIR ≥ 0.80) uses the EEOC Uniform Guidelines "four-fifths rule"
  (citable). The 0.05 mean-PD-gap monitor threshold is an operational setting, not a standard — cite or reframe.
