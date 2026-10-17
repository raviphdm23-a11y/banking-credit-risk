# AEGIS decisioning note — GERMAN (UCI Statlog German credit), 5-feature model

**Run:** GERMAN (fresh re-run) · **Gate:** G5 (deployment governance) · entry_hash `884c20a1`
**Model:** AEGIS-approved WOE-logistic, **5 features**:
`checking_status, credit_history, months_duration, savings_status, purpose`.
**Held-out discrimination:** Gini **0.532** / AUC **0.766** (selection) · **calibration passes** (HL p=0.46/0.21, ECE 0.040).

---

## 1. What this note DOES and DOES NOT set

Governs how an applicant's PD is produced and explained — the calibrated PD, the PD floor/cap (Basel CRE32.3), the
rating grade, and exact WOE reason codes. **It does NOT invent an accept/decline cutoff or a price**: the lending
decision is the institution applying its **own risk-appetite PD threshold** — exogenous, not derived here.

## 2. Scoring configuration (signed at G5)

| Control | Value |
|---|---|
| Model | 5-feature (genuine parsimony: 5 of 17) |
| Mandatory field (blank → refer) | `checking_status` (the dominant predictor, IV 0.666) |
| Incomplete policy | `refer` |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Decisions emitted | SCORE / SCORE_FLAGGED / REFER / REJECT + calibrated PD + reason string |

## 3. Binding conditions (carried from G0–G4 → GF)

- **NEVER-DEPLOY.** Research benchmark only; no model here is fit for a live credit decision.
- **AGE-IMPACT.** Though `age` was excluded at G0, the model reproduces **age-disparate impact** (approve-rate AIR
  worst 0.574 for <25) via correlated features — **true-risk-driven, not bias** (young default 48.7% vs 13.3% for 60+;
  model accurate within each band). AIR is **indicative** (internal master scale; no institution cutoff). Any live use
  would require a fairness-constrained replication + reject-inference study. **Replicates the LC finding: excluding a
  protected attribute is necessary but not sufficient to remove disparate impact.**
- **FW-THIN.** `foreign_worker` fairness **inconclusive** — only 37/1,000 non-foreign (6 in the test split); AIR
  degenerate on that cell, not a reliable result.
- **DQ-BB.** Grade BB under-predicts on backtest (observed 14.7% vs predicted 6.2%, n=34); monitor.

*(No licensing/vintage condition — German is a freely-citable UCI benchmark.)*

## 4. Acceptance demonstration

See `SAMPLE_RUNS_GERMAN.md` — 4 real applicants (spanning good/bad across the risk range) + 2 synthetic composites
(PD-floor check, stress check). Confirms: PD **floor (0.03%) and cap (99.9%) both bind**; reason codes coherent;
`checking_status` completeness gate enforced. Case PDs: R1 0.03% (AAA) → R2 28.4% (CC) → R3 47.4% (C) → R4 99.9% (D).
