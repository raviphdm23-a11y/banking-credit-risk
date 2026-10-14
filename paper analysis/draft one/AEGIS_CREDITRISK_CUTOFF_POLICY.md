# AEGIS — CREDITRISK (Kaggle "Credit Risk Dataset"): decisioning note

**Status:** decisioning note · **Date:** 2026-10-14 · **Model:** AEGIS-approved WOE-logistic 6-column benchmark
(AEGIS run `AEGIS_RUN_CREDITRISK.md`). **MEDIUM-tier reference benchmark — not production-IRB.**

> **Research-integrity note.** This note prescribes **no** accept/refer/decline PD cutoff and **no** pricing.
> The accept / refer / decline **lending decision and any pricing are institution risk-appetite inputs,
> exogenous to this methodology and not derived here.**

## Data-integrity provenance (resolved at G0)
This dataset shipped a **corrupted `target` column** (agreed with the real outcome only 73.9% of the time;
nonsensical default rates by loan grade) and **5 empty junk columns**. The run uses the **verified `loan_status`**
label (monotonic default A 10% → G 98%); `target` and the junk columns were rejected at G0. Impossible values
(`person_age` 144, `person_emp_length` 123) were flagged. `person_age` (ECOA-prohibited) was excluded before
modelling.

## What this methodology produces (grounded, citable)
Per applicant: a **calibrated PD** (isotonic; floored 0.03% per Basel CRE32.3; backtested per CRE36.122–123 —
HL p=0.716, 9/9 populated grades within CI, full AAA–D spectrum), a **rating grade / risk tier**, the **exact
WOE reason codes**, and the **governed completeness decision** (SCORE / REFER / REJECT). See `SAMPLE_RUNS_CREDITRISK.md`.

## What is an institution input (NOT derived here)
- The **accept / refer / decline PD threshold(s)** — institution risk appetite.
- Any **pricing**.

## CREDITRISK-specific caveat — AVAILABILITY
Two of the six benchmark features are **not valid origination-time inputs**:
- `loan_grade` — the **incumbent lender's own risk grade** (its risk verdict compressed to one column).
- `loan_int_rate` — the **risk-based price** set from that verdict.

The **6-column model is a benchmark only.** The **deployable application-time model is the 4-column
origination-only variant** (`loan_percent_income, person_income, person_home_ownership, loan_intent`): Gini
**0.591** / AUC 0.796 (vs benchmark 0.760 / 0.880 — **−22.2% relative, the largest circularity cost of any run**).
It remains genuinely usable (HELOC-tier) and independent of the incumbent's verdict. Fairness: age disparate
impact negligible (all PD gaps < 0.05, predictive parity; age excluded).

## Citations still required before publication
- **Rating-grade band edges** (PD→grade) — cite the external scale (e.g. S&P/Moody's idealised default rates)
  or state as the institution's internal scale.
- The 0.05 mean-PD-gap fairness-monitor threshold is an operational setting, not a standard — cite or reframe.
