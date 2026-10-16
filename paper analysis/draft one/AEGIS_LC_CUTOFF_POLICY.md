# AEGIS decisioning note — LC (LendingClub), no-geo primary model

**Run:** LC (11th governed run) · **Gate:** G5 (deployment governance) · entry_hash `7c8d5e06`
**Model:** AEGIS-approved WOE-logistic, **8 features (grade-free, no geography)**:
`term, revol_util, annual_inc, inq_last_6mths, purpose, funded_amnt, loan_amnt, pub_rec`.
**Held-out discrimination:** Gini **0.351** / AUC **0.676** · **Calibration clean** (HL p=0.48–0.54, ECE 0.0020).

---

## 1. What this note DOES and DOES NOT set

This note governs how an applicant's PD is produced and explained. It reports **only methodology/regulation-grounded
outputs**: the calibrated PD, the PD floor/cap (Basel CRE32.3), the rating grade on the institution's internal master
scale, and exact WOE reason codes.

**It does NOT invent an accept/refer/decline cutoff or a price.** The lending decision is the institution applying its
**own risk-appetite PD threshold** to the grade/PD — that threshold and any pricing are **exogenous inputs**, not derived
here. (No economics are fabricated — standing project rule.)

## 2. Scoring configuration (signed at G5)

| Control | Value |
|---|---|
| Primary model | no-geo (8 features; `addr_state` dropped at G4) |
| Mandatory field (blank → refer) | `annual_inc` |
| Incomplete policy | `refer` (an application missing a declared-essential field is never silently scored) |
| Reason codes | exact additive WOE (faithful per-feature; no post-hoc approximation) |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Decisions emitted | SCORE / SCORE_FLAGGED / REFER / REJECT, each with calibrated PD + reason string |

## 3. Binding conditions (carried from G0–G4 → GF)

- **NEVER-DEPLOY.** Research benchmark only. No model in this run is intended or suitable for a live credit decision.
- **LICENSING.** LendingClub data-reuse terms permit internal/sandbox testing; **citing results in the ICOPEX paper
  requires confirming those terms first.**
- **VINTAGE.** File named `q12019` but internal dates indicate **2009–2011 vintage**; verify true vintage before citation.
- **GEO-AIR.** Geographic disparate impact: with-geo worst-region AIR 0.568, **no-geo worst 0.622 (Midwest still fails
  four-fifths)**. Dropping the explicit proxy cured West (0.591→0.938) and South (0.876→0.961) but residual impact
  persists via correlated features because regional default rates genuinely differ (model accurate within region; impact
  is **true-risk-driven, not bias**). AIR is **indicative** (internal master scale; no institution cutoff). Any live use
  would require a jurisdiction-specific fairness review and reject-inference study.
- **DQ-BBB.** Grade BBB mildly optimistic on backtest (observed 5.3% vs predicted 3.5%); monitor.
- **SIG-N.** At N≈39,717 the DeLong selection rule under-parsimonizes; a 5-feature model recovers ~95% of discrimination
  (reported as a methodological point — effect size, not p-value, should govern at large N).

## 4. Comparison artifact

A **with-geo** model (adds `addr_state`; Gini 0.358/AUC 0.679) and a **rate-included** model (adds `int_rate`+
`installment` ≈ LendingClub's own grade; Gini 0.387/AUC 0.694) are retained as comparison points
(`SHARP_LC.md` is no-geo-adjacent; `SHARP_LC_rate_comparison.md`). Key findings: LC's own pricing adds only ~0.03 Gini
over raw applicant features; geography adds only ~0.007.

## 5. Acceptance demonstration

See `SAMPLE_RUNS_LC.md` — 4 real applicants (spanning repaid/defaulted across the risk range) + 2 synthetic composites
(PD-floor check, stress check). Confirms: PD floor (0.03%) and cap (99.9%) both bind; reason codes coherent;
`annual_inc` completeness gate enforced.
