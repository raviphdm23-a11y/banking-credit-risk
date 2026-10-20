# AEGIS decisioning note — GERMAN (South German Credit, Grömping 2019 corrected), 5-feature model

**Run:** GERMAN (South German Credit, UCI #522 — error-corrected recoding of Statlog; supersedes the archived Statlog run) · **Gate:** G5 (deployment governance) · entry_hash `496d214e` · **GF** `a92fa411`
**Model:** AEGIS-approved WOE-logistic, **5 features**:
`checking_status, credit_history, months_duration, savings_status, credit_amount`.
**Discrimination:** Gini **0.542** / AUC **0.771** (out-of-fold) · **calibration passes** (HL g=10 p=0.112, g=5 p=0.194; ECE 0.033; per-grade backtest 8/8 in Wilson CI).

> **Gate decisions emitted by `ml_models/aegis_gates.py`** (deterministic option sets + GF engine), not authored by hand.

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
  worst **0.340** for <25) via correlated features — **true-risk-driven, not bias** (young default 41.3% vs 25.5% for 60+;
  model accurate within each band). AIR is **indicative** (internal master scale; no institution cutoff). Any live use
  would require a fairness-constrained replication + reject-inference study. **Replicates the LC finding: excluding a
  protected attribute is necessary but not sufficient to remove disparate impact.**
- **FW-FRAGILE.** `foreign_worker` fairness **effectively inconclusive** — the 37-row minority cell carries only 2
  approvals, so the AIR (0.730) is statistically fragile, not a reliable result.
- **SPARSE-A.** Grade A holds only n=4; its backtest CI is wide — carry an EBA category-A Margin of Conservatism.

*(No licensing/vintage condition — freely-citable UCI benchmark, CC BY 4.0.)*

## 4. Acceptance demonstration

See `SAMPLE_RUNS_GERMAN.md` — 4 real applicants (spanning repaid/defaulted across the risk range) + 2 synthetic
composites (PD-floor check, cap/stress check). Confirms: PD **floor (0.03%) and cap (99.9%) both bind**; reason codes
coherent; `checking_status` completeness gate enforced. Case PDs: DE-R1 1.79% (A) → DE-R4 70.83% (D); synthetic best
0.03% (AAA, floor binds) → synthetic worst 99.90% (D, cap binds).
