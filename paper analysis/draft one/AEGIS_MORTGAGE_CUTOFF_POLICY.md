# AEGIS decisioning note — MORTGAGE (US mortgage performance panel, origination snapshot)

**Run:** MORTGAGE (Baesens et al. "Credit Risk Analytics" US mortgage performance panel) · **first PANEL
dataset governed** via `ml_models/panel_adapter.py` (snapshot framing) · **Gate:** G5 (deployment
governance) · entry_hash `cb65985c` · **GF** `56578ceb`
**Model:** AEGIS-approved WOE-logistic, **6 features** (a genuinely compact origination scorecard):
`hpi_orig_time` (dominant), `Interest_Rate_orig_time`, `FICO_orig_time`, `LTV_orig_time`,
`balance_orig_time`, `term_orig`.
**Discrimination:** Gini **0.464** / AUC **0.732** (out-of-fold) · **calibration** ECE 0.0074, per-grade
backtest **8/8** grades inside Wilson CI (HL g=10 rejected at large n — see §3).

> **Gate decisions emitted by `ml_models/aegis_gates.py`** (deterministic option sets + GF engine), not authored by hand.

---

## 1. What this note DOES and DOES NOT set

Governs how a loan's PD is produced and explained — the calibrated PD, the PD floor/cap (Basel CRE32.3),
the rating grade, and exact additive-WOE reason codes. **It does NOT invent an accept/decline cutoff or a
price**: the credit decision is the institution applying its **own risk-appetite PD threshold** —
exogenous, not derived here.

## 2. Scoring configuration (signed at G5)

| Control | Value |
|---|---|
| Model | 6 features / 6 columns (compact — one column per confirmed player; contrast Polish 6 players = 37 cols) |
| Mandatory field (blank → refer) | none — the collapsed frame has **zero missingness** on all 6 features |
| Incomplete policy | reject (not exercised; no missing inputs occur) |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always-on) |
| Decisions emitted | SCORE + calibrated PD + grade + reason string |

## 3. Binding conditions (carried from G0–G4 → GF)

- **NEVER-DEPLOY.** Research benchmark only; no model here is fit for a live credit decision.
- **ORIGINATION-ONLY (snapshot framing).** The panel (622,489 loan-period rows, 50,049 loans under the
  composite key `(id, orig_time)`) was collapsed to **one row per loan**: features are the loan's
  **origination** characteristics, target = the loan **ever defaults** over its observed life. The
  time-varying covariates (`balance_time`, `LTV_time`, `interest_rate_time`, `hpi_time`, `gdp_time`,
  `uer_time`) are deliberately **out of scope** — a snapshot can only use origination-time information.
  Modest discrimination (Gini 0.464) is the honest ceiling of an origination-only scorecard; a behavioural
  **hazard** model that uses the trajectory is the deferred alternative (needs group-aware CV through
  Stage 2). Report Gini 0.464 as origination-only, not as the dataset's achievable ceiling.
- **HL-CAVEAT (calibration, SR/CRE36.122).** Hosmer-Lemeshow g=10 is **rejected** (p≈0.000), but this is a
  large-n artefact (n=50,049): HL g=5 passes (p=0.341), ECE is 0.0074, and the **per-grade realised-vs-expected
  backtest passes 8/8** grades inside the Wilson 95% CI. The per-grade backtest is the **governing** calibration
  test; the HL rejection rides as a disclosed caveat + MoC. (Same pattern as the SBA run.)
- **ISOTONIC-CEILING.** Isotonic calibration cannot extrapolate above its training maximum, so calibrated PD
  **ceilings at ≈0.68** (the worst grade's realised rate). The 99.9% cap therefore **never binds** on this
  model — even the all-worst-origination stress case tops out at 68%. The PD **floor (0.03%) does bind**.
- **FAIRNESS N/A.** All 6 features are origination financials / macro (`FICO`, `LTV`, rate, balance, `hpi`,
  term); **no protected attributes exist**, so no adverse-impact ratio is computed and no fairness condition
  is carried. (Contrast German/SBA/LC, where fairness was live.)

*(No sufficiency condition — event-rich: 15,155 defaulting loans, EPV ≈ 1,515, Riley met ~140×. No
licensing/vintage condition — freely-citable academic benchmark. Both the opposite of Polish.)*

## 4. Acceptance demonstration

See `SAMPLE_RUNS_MORTGAGE.md` — 4 real loans (spanning the risk range, both outcomes) + 2 synthetic
composites (observed feature-value extremes: a PD-floor check and a stress check). Confirms: PD **floor
(0.03%) binds** (real MG-R1 and synthetic MG-S1 → AAA); the **99.9% cap does not bind** (isotonic ceiling
≈0.68, so the all-risky MG-S2 stress case scores 68% / grade D, not 99.9%); reason codes coherent; the
origination-only model honestly scores a real defaulted loan (MG-R3) at only 17.5% (grade CCC) — a
false-negative the origination-only horizon makes unavoidable without behavioural data. Case PDs: MG-R1
0.03% (AAA, floor) → MG-R4/MG-S2 68.00% (D, isotonic ceiling).
