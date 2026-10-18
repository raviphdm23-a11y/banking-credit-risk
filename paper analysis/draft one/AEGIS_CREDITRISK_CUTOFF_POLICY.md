# AEGIS decisioning note — CREDITRISK (cleaned), 6-feature benchmark

**Run:** CREDITRISK (fresh re-run on the cleaned file) · **Gate:** G5 · entry_hash `c0080bc2`
**Benchmark model:** AEGIS-approved WOE-logistic, **6 features**:
`loan_percent_income, loan_grade, person_income, loan_int_rate, person_home_ownership, loan_intent`.
**Held-out discrimination:** AUC **0.877** / Gini **0.754** · **calibration passes** (HL p=0.44, ECE 0.011, 9/10 grades in CI).
**Deployable model:** the **4-feature origination-only** variant (drop `loan_grade`+`loan_int_rate`), Gini 0.591 — independent of the incumbent lender's verdict.

---

## 1. What this note DOES and DOES NOT set
Governs how an applicant's PD is produced and explained — the calibrated PD, the PD floor/cap (Basel CRE32.3), the
rating grade, and exact WOE reason codes. **It does NOT invent an accept/decline cutoff or a price**: the lending
decision is the institution applying its own risk-appetite PD threshold — exogenous, not derived here.

## 2. Scoring configuration (signed at G5)
| Control | Value |
|---|---|
| Benchmark model | 6-feature (comparability); **deployable = 4-feature origination-only** |
| Mandatory fields (blank → refer) | `loan_percent_income`, `person_income` (origination-available; **not** grade/int_rate) |
| Incomplete policy | `refer` |
| Adverse floor | none (deployable 4-col is missing-free) |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Monitoring | drift (PSI/AUC) + age-disparate-impact watch |

## 3. Binding conditions (carried G0–G4 → GF)
- **CR-avail.** `loan_grade` + `loan_int_rate` are **circular** (incumbent's own grade + risk-based price); the
  6-col benchmark is comparability-only, **not** an origination-time model.
- **CR-orig.** Origination deployments use the **4-col origination-only model** (Gini 0.591) — removing the circular
  pair costs ΔGini 0.169 (−22.2%, the largest circularity cost in the corpus), but the result is independent and usable.
- **CR-age.** `person_age` excluded (ECOA); monitor age-disparate impact. Backtest: gaps <0.05 except the 45–54 cell
  (+0.060, n=139, noisy and over-predicting) — predictive parity broadly holds.
- **CR-dq.** Impossible values (`person_age` 144, `person_emp_length` 123) → upstream data-quality fix before production.
- **CR-use.** Use test required before any real-decision use (R2 / CRE36.60).

*(CR-label from the first run is **discharged at source**: the corrupt `target` column was deleted and the genuine
`loan_status` adopted as `target` in the cleaned file; the original file is backed up.)*

## 4. Acceptance demonstration
See `SAMPLE_RUNS_CREDITRISK.md` — 4 real applicants (good/bad across the range) + 2 synthetic composites. Confirms the
PD **floor (0.03%) and cap (99.9%) both bind** and reason codes are coherent. Case PDs: CR-R1 0.03% (AAA) → CR-R2 20.4%
→ CR-R3 46.1% → CR-R4 99.9% (D).
