# AEGIS decisioning note — SBA (US Small Business Administration loans), 7-player model

**Run:** SBA (12th governed run) · **Gate:** G5 · entry_hash `18be815d`
**Model:** AEGIS-approved WOE-logistic, **7 players / 11 columns**:
`RealEstate, Term, daysterm, ApprovalFY, Portion, DisbursementGross, GrAppv, SBA_Appv, FranchiseCode, RevLineCr, NAICS`.
**Held-out discrimination:** AUC **0.931** / Gini **0.862** — the strongest in the corpus · **per-grade backtest passes 7/7**, ECE 0.040.

---

## 1. What this note DOES and DOES NOT set
Governs how an applicant's PD is produced and explained — the calibrated PD, the PD floor/cap (Basel CRE32.3), the
rating grade, and exact WOE reason codes. **It does NOT invent an accept/decline cutoff or a price**: the lending
decision is the institution applying its own risk-appetite PD threshold — exogenous, not derived here.

## 2. Scoring configuration (signed at G5)
| Control | Value |
|---|---|
| Model | 7-player / 11-column WOE-logistic |
| Mandatory fields (blank → refer) | `Term` (dominant predictor), `GrAppv` (loan amount) |
| Incomplete policy | `refer` |
| Adverse floor | none (selected features effectively complete) |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Monitoring | drift (PSI/AUC) + geographic-disparity watch + calibration watch (bimodal-PD / HL caveat) |

## 3. Binding conditions (carried G0–G4 → GF)
- **SBA-VINTAGE.** `ApprovalFY` is a vintage/time proxy (recession-era cohorts default more); known at origination
  but encodes a period trend. Removing it costs only ΔGini 0.013 (**−1.5%**) — no circularity concern, disclosed.
- **SBA-CAL.** Hosmer–Lemeshow rejects (p=0.018) because the PD distribution is strongly **bimodal** (long
  real-estate loans near 0, short loans near 0.83); the **per-grade realised-vs-expected backtest passes 7/7**
  (ECE 0.040), so PDs are usable grade-by-grade. Monitor.
- **SBA-GEO.** Approve-rate adverse-impact ratio **0.41 by `BankState`** (excluded from the model) fails four-fifths,
  but is **true-risk-driven** — approve rates track actual default rates by state. Indicative only (business lending:
  no personal protected attributes; `BankState` is lender geography). Any live use would need a geographic
  fairness-constrained review.
- **SBA-USE.** Use test required before any real-decision use (R2 / CRE36.60).

*(Leakage, identifiers, constants and junk — MIS_Status, ChgOffPrinGr/ChgOffDate, State, BalanceGross, xx — were
excluded at G0 by computable precondition; see METHODOLOGY §3.7.)*

## 4. Acceptance demonstration
See `SAMPLE_RUNS_SBA.md` — 4 real applicants (good/bad across the range) + 2 synthetic composites. Confirms the
PD **floor (0.03%)** binds (SBA-R1 at AAA) and the cap approaches on the stress case; reason codes coherent;
`Term`/`GrAppv` completeness gate enforced. Case PDs: SBA-R1 0.03% (AAA) → SBA-R2 31.8% → SBA-R3 49.0% →
SBA-R4 95.9% (D).
