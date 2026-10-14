# AEGIS — LOAN (LendingClub 2007–2010 educational subset): decisioning note

**Status:** decisioning note · **Date:** 2026-10-14 · **Model:** AEGIS-approved WOE-logistic 7-column benchmark
(AEGIS run `AEGIS_RUN_LOAN.md`). **MEDIUM-tier reference benchmark — not production-IRB.**

> **Research-integrity note.** This note prescribes **no** accept/refer/decline PD cutoff and **no** pricing.
> The accept / refer / decline **lending decision and any pricing are institution risk-appetite inputs,
> exogenous to this methodology and not derived here** (consistent with every other run in this work).

## What this methodology produces (grounded, citable)
For each applicant: a **calibrated PD** (isotonic; floored at 0.03% per Basel CRE32.3; backtested per
CRE36.122–123 — HL p=0.437, 8/8 populated grades within CI, full AAA–D spectrum), a **rating grade / risk tier**
(institution internal master scale), the **exact WOE reason codes** (ECOA/Reg B adverse-action), and the
**governed completeness decision** (SCORE / REFER / REJECT from the mandatory-field gate). See `SAMPLE_RUNS_LOAN.md`.

## What is an institution input (NOT derived here)
- The **accept / refer / decline PD threshold(s)** — set by the institution's risk appetite and economics.
- Any **pricing** of the loan.

## LOAN-specific caveat the committee must read — AVAILABILITY
Three of the seven benchmark features are **not valid inputs to an origination (application-time) decision**:
- `int.rate` — the interest rate the incumbent lender **set from its own risk view** (risk-based pricing): an
  *output* of a prior decision, circular at a fresh origination.
- `credit.policy` — a **prior underwriting-screen outcome** (1 = met LendingClub's criteria).
- `fico` — an **external credit score** (METHODOLOGY §3.3).

The **7-column model is a benchmark only.** The **deployable application-time model is the 4-column
origination-only variant** (`inq.last.6mths, purpose, revol.util, log.annual.inc`), which drops all three flagged
features: Gini **0.300** / AUC 0.650 (vs benchmark 0.343 / 0.672 — −12.4% relative), and is **better calibrated**
(ECE 0.003). Unlike PAK, the model does **not** collapse without the circular features — genuine origination-time
signal remains. Fairness: **N/A** (no protected/proxy attributes).

## Citations still required before publication
- **Rating-grade band edges** (PD→grade) — cite the external scale they align to (e.g. S&P/Moody's idealised
  cumulative default rates) or state them explicitly as the institution's internal scale.
