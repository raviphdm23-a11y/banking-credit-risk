# AEGIS decisioning note — MORTGAGE_HAZARD (US mortgage panel, discrete-time hazard)

**Run:** MORTGAGE_HAZARD (Baesens et al. US mortgage performance panel) · **discrete-time hazard framing**
via `ml_models/panel_adapter.py` (all 622,489 loan-periods kept; group-aware CV) · **Gate:** G5 (deployment
governance) · entry_hash `f4e28439` · **GF** `dca8af15`
**Model:** AEGIS-approved WOE-logistic, **11 features** = 3 time-varying (`interest_rate_time`, `LTV_time`,
`balance_time`) + 3 macro (`gdp_time`, `hpi_time`, `uer_time`) + 5 origination (`FICO_orig_time`,
`LTV_orig_time`, `Interest_Rate_orig_time`, `balance_orig_time`, `hpi_orig_time`). Predicts default **in a
given period** (per-period hazard, base rate 2.44%).
**Discrimination:** Gini **0.474** / AUC **0.737** (out-of-fold, grouped by loan) · **calibration passes on
the DEPLOYED model under a cluster-robust test** (see §3).

> **Gate decisions emitted by `ml_models/aegis_gates.py`**; calibration GOF by `ml_models/calibration_gof.py`
> (cluster-robust, on the isotonically-calibrated model). Not authored by hand.

---

## 1. What this note DOES and DOES NOT set

Governs how a loan-period's PD is produced and explained — the calibrated per-period PD, the PD floor/cap
(Basel CRE32.3), the rating grade, and exact additive-WOE reason codes. **It does NOT invent an
accept/decline cutoff or a price**: the credit decision is the institution applying its **own risk-appetite
PD threshold** — exogenous, not derived here.

## 2. Scoring configuration (signed at G5)

| Control | Value |
|---|---|
| Unit of scoring | one **loan-period** (the hazard unit), not a loan |
| Model | 11 features / 11 columns (3 time-varying + 3 macro + 5 origination) |
| Mandatory field (blank → refer) | none — only `LTV_time` has trivial missingness (270 / 622,489) |
| Incomplete policy | reject (barely exercised) |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Decisions emitted | SCORE + calibrated per-period PD + grade + reason string |

## 3. Binding conditions (carried from G0–G4 → GF)

- **NEVER-DEPLOY.** Research benchmark only.
- **TIME-LEAKAGE / NO-OUT-OF-TIME (the governing limitation of this run).** Group-aware CV (StratifiedGroup
  KFold by loan) removes **entity** leakage — no loan's rows straddle train/test. It does **not** remove
  **time** leakage: the macro covariates (`gdp_time`, `uer_time`, `hpi_time`) are shared across all loans at
  the same calendar period, so there is cross-sectional (vintage) correlation an i.i.d. CV cannot see. **No
  out-of-time / vintage validation was performed.** Any real use would require a train-past / test-future
  split. Contemporaneous time-varying covariates are a standard discrete-time-hazard design (covariate
  observed at period start), not leakage.
- **CALIBRATION — cluster-robust, deployed-model (resolved, not a defect).** The raw WOE-logistic OOF PDs
  carried small per-grade bias and, on 622k clustered rows, both HL and the per-grade backtest over-rejected
  (1/7, HL p≈0). This was investigated and resolved: (a) the governing test must assess the **deployed**
  (isotonically-calibrated) model, not the raw OOF; (b) on panel data the interval must be **cluster-robust**.
  Under the correct test — calibrated model, held-out 10,010 loans, cluster-bootstrap CI + design-effect HL —
  the model passes **per-grade 7/7**, HL g=10 **p = 0.11 (raw) / 0.65 (adj.)**, ECE 0.0005. The methodology
  was upgraded so this is now automatic (`calibration_gof.deployment_backtest`, wired into Stage 4).
- **ISOTONIC-CEILING.** Isotonic calibration cannot extrapolate above its training max, so the calibrated
  per-period PD **ceilings at ≈14.6%** (the worst grade's realised per-period rate). The 99.9% cap never
  binds; the 0.03% **floor does bind**. Per-period PDs are naturally low (a loan defaults in any single
  period with small probability), so grades read lower than the snapshot ever-default model.
- **FAIRNESS N/A in data, but IN SCOPE.** No protected attributes exist in the dataset (financial/macro
  only), so no AIR is computed — but borrowers are **natural persons**, so EU AI Act Annex III / ECOA remain
  in scope (R12/R14), unlike the Polish firm-level run.

*(No sufficiency condition — event-rich: 15,158 default-periods, EPV ≈ 1,378, Riley met ~9.7× at the loan-
cluster level. No licensing/vintage condition — freely-citable academic benchmark.)*

## 4. Acceptance demonstration

See `SAMPLE_RUNS_MORTGAGE_HAZARD.md` — 4 real loan-periods (spanning the per-period PD range, both outcomes)
+ 2 synthetic composites (observed feature-value extremes: a PD-floor check and a stress check). Confirms:
PD **floor (0.03%) binds** (real MH-R1 and synthetic MH-S1 → AAA); the **99.9% cap does not bind** (isotonic
ceiling ≈14.6%, so the all-risky stress case scores 14.6% / grade CCC); reason codes coherent and dominated
by the time-varying `interest_rate_time` / `LTV_time`. Case PDs: MH-R1 0.03% (AAA, floor) → MH-R4/MH-S2
14.6% (CCC, isotonic ceiling).

## 5. Headline finding (why this run matters)

The full time-varying + macro hazard model (Gini 0.474) **does not materially out-discriminate** the simple
6-feature origination snapshot (Gini 0.464) — the extra 622k rows, dynamic covariates and macro series buy
almost nothing here (the two are not strictly comparable: per-period vs ever-default). The simple
origination scorecard is the preferable model; the hazard run's lasting value was surfacing (and fixing) the
cluster-robust / deployed-model calibration-testing requirement.
