# AEGIS decisioning note — POLISH1 (Polish bankruptcy, Year-1 horizon), 6-player / 37-column model

**Run:** POLISH1 (Polish companies bankruptcy data, Zięba et al. 2016, UCI #365 — Year-1 horizon:
financial ratios observed in year 1, bankruptcy status over the following 5 years) · **Gate:** G5
(deployment governance) · entry_hash `622222b8` · **GF** `3870d5f4`
**Model:** AEGIS-approved WOE-logistic, **6 confirmed players spanning 37 columns**
(dominant `Attr27`; player blocks of 20 / 7 / 6 correlated ratios + `grp[Attr46+Attr5]` + `Attr21`).
**Discrimination:** Gini **0.783** / AUC **0.892** (out-of-fold) · **calibration passes**
(HL g=10 p=0.379, g=5 p=0.514; ECE 0.0033; per-grade backtest **10/10** grades inside Wilson CI).

> **Gate decisions emitted by `ml_models/aegis_gates.py`** (deterministic option sets + GF engine), not authored by hand.

---

## 1. What this note DOES and DOES NOT set

Governs how a firm's PD is produced and explained — the calibrated PD, the PD floor/cap (Basel CRE32.3),
the rating grade, and exact additive-WOE reason codes. **It does NOT invent an accept/decline cutoff or a
price**: the credit decision is the institution applying its **own risk-appetite PD threshold** —
exogenous, not derived here.

## 2. Scoring configuration (signed at G5)

| Control | Value |
|---|---|
| Model | 6 players / 37 columns (decision-parsimonious, NOT column-parsimonious — see §3) |
| Mandatory field (blank → refer) | `Attr27` (the dominant predictor, IV 2.80) |
| Incomplete policy | `refer` |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Decisions emitted | SCORE / SCORE_FLAGGED / REFER / REJECT + calibrated PD + reason string |

## 3. Binding conditions (carried from G0–G4 → GF)

- **NEVER-DEPLOY.** Research benchmark only (anonymised Polish financial ratios); no model here is fit for a
  live credit decision.
- **EPV-SHORT (MoC + not-for-capital).** Events are thin: 271 bankruptcies against a 64-ratio pool →
  **legacy EPV ≈ 4.2**, below the EPV ≥ 10 rule of thumb. The modern **Riley** minimum is *met*
  (5,141 required vs 7,027 available, 1.37×) because discrimination is strong, so the run proceeds — but the
  EPV shortfall rides along as a mandatory Margin of Conservatism and a **not-for-capital** flag.
- **PARSIMONY-WIDTH.** The selection rule picked **6 players**, but those players are correlation-equivalence
  blocks, so the model spans **37 of 60 screened columns**. It is parsimonious in *decision* terms (6
  independent signals reproduce 99.6% of the full Gini; DeLong p 0.619, rel-loss 0.41%) but **not** in
  column count — unlike German's genuine 5-feature model. Report both numbers; do not call this a
  small-feature model.
- **FAIRNESS N/A.** All 64 attributes are firm financial ratios; **no protected attributes exist**, so no
  adverse-impact ratio is computed and no fairness condition is carried. (Contrast German/SBA/LC, where
  fairness was live.)
- **EARLY-HORIZON MISS RISK.** Year-1 is the longest forecast distance; the acceptance pack includes a real
  defaulted firm the model rated grade A (PD 1.0%) — an honest false-negative that the 5-year-ahead horizon
  makes unavoidable. Any live use would need horizon-matched monitoring.

*(No licensing/vintage condition — freely-citable UCI benchmark.)*

## 4. Acceptance demonstration

See `SAMPLE_RUNS_POLISH1.md` — 4 real firms (spanning the risk range, both outcomes) + 2 synthetic composites
(constructed from observed feature-value extremes: a PD-floor check and a cap/stress check). Confirms: PD
**floor (0.03%) and cap (99.9%) both bind** (floor on real PL-R1 and synthetic PL-S1; cap on synthetic
PL-S2); reason codes coherent; **`Attr27` completeness gate enforced** (real defaulted firm PL-R4 with a
missing `Attr27` is REFERRED, not scored — 311 of 7,027 firms, incl. 120 defaults, carry a missing `Attr27`).
Case PDs: PL-R1 0.03% (AAA, floor) → PL-S2 99.90% (D, cap).
