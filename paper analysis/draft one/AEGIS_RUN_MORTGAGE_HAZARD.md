# AEGIS governed run — MORTGAGE_HAZARD (US mortgage panel, discrete-time hazard)

**Dataset:** US mortgage performance panel (Baesens, Rösch & Scheule, *Credit Risk Analytics*).
**Discrete-time HAZARD framing** via `ml_models/panel_adapter.py`: **all 622,489 loan-period rows kept**
(50,049 loans, composite key `(id, orig_time)`), target = default **in that period** (per-period hazard,
base rate **2.44%**). The richer counterpart to the origination-snapshot run (`AEGIS_RUN_MORTGAGE.md`):
it uses the time-varying + macro covariates the snapshot excludes. **11 governed features** = 3 time-varying
+ 3 macro + 5 origination. **Materiality tier:** MEDIUM. **Fairness NOT live in data** (no protected
attrs), but borrowers are natural persons so EU AI Act / ECOA are in scope. Source:
`data/ml_lab/datasets/mortgage.csv` (+ `mortgage_hazard.manifest.json`). Seed 42.

> **Leakage control.** Group-aware CV (StratifiedGroupKFold by loan) keeps every loan's rows inside one fold,
> threaded through Stages 2–4 (`selection`, `shapley_utils`, parsimony, calibration). Shapley importance ran
> on a group-aware 80k-row subsample for tractability; parsimony + calibration on all 622k rows. The
> calibration GOF is cluster-robust and assesses the DEPLOYED (isotonically-calibrated) model
> (`ml_models/calibration_gof.py`). Gate options emitted by `ml_models/aegis_gates.py`.

## Decision summary

| # | Gate | Decision | Signer | Basis | prev | entry_hash |
|---|---|---|---|---|---|---|
| 0 | G0 | **A — adopt hazard scope; MEDIUM** | Ravi / Model Validator | panel→hazard; composite key; co-outcomes payoff/status excluded as leakage; time-leakage disclosed; single viable scope | GEN-MORTGAGE_HAZARD_0 | `9ececb8c` |
| 1 | G1 | **A — advance 11/15, sufficiency clears** | Ravi / Model Validator | 11/15 pass IV≥0.02; dominant `LTV_time` IV 0.399; EPV ≈1,011; Riley 5,177 vs **50,049 loans (9.7×)** — event-rich | `9ececb8c` | `52f57eb3` |
| 2 | G2 | **A — accept 9/9 confirmed players** | Ravi / Model Validator | shadow bar 0.00089; all 9 confirmed (freq 1.00); dominant `interest_rate_time` ~60× bar, weakest ~10.3×; sampled (P8) | `52f57eb3` | `4802715c` |
| 3 | G3 | **A — adopt k=9 (11 cols), PARSIMONY-NULL** | Ravi / Model Validator | at n=622k DeLong distinguishes every k<9 (p≈0), so full set adopted; Gini 0.474, rel loss 0% | `4802715c` | `ba6d95cb` |
| 4 | G4 | **A — approve calibration (clean)** | Ravi / Risk Officer | DEPLOYED model: cluster-robust per-grade **7/7**; HL g10 p=0.11/0.65-adj (not rejected); ECE 0.0005; AUC 0.737 ≥ floor; fairness N/A | `ba6d95cb` | `a877b2b0` |
| 5 | G5 | **A — confirm controls + deliverables** | Ravi / Model Owner | adverse floor + exact WOE reason codes + reject-on-incomplete; near-zero missingness; cutoff policy + 6-case per-period acceptance pack | `a877b2b0` | `f4e28439` |
| F | **GF** | **GO-WITH-CONDITIONS** (engine) | Ravi / MAC Chair + CRO | all gates signed; no must-have GAP; PARTIALs **R7** (TIME-LEAKAGE) + **R12** (AI-Act); conditions also NEVER-DEPLOY, ISOTONIC-CEILING | `f4e28439` | `dca8af15` |

**Chain:** `GEN-MORTGAGE_HAZARD_0 → 9ececb8c → 52f57eb3 → 4802715c → ba6d95cb → a877b2b0 → f4e28439 → dca8af15`

---

## G0 — Data & Scope Adequacy · A · `9ececb8c`
Discrete-time hazard scope: all 622,489 loan-periods retained, target = per-period `default_time`, using the
time-varying (dynamic LTV/balance/rate) + macro (gdp/uer/hpi) covariates the snapshot excludes. Composite key
`(id, orig_time)` = 50,049 loans. Co-outcomes `payoff_time` / `status_time` excluded as leakage by
precondition. **Disclosed at G0 and carried to GF:** group-aware CV removes entity leakage but NOT time
leakage (shared macro per calendar period); no out-of-time validation. Single viable scope.

## G1 — Screening & Data Sufficiency · A · `52f57eb3`
11 of 15 candidates pass IV ≥ 0.02 (vs snapshot's 6/10 — the time-varying covariates clear the screen).
Dominant `LTV_time` IV **0.399** (dynamic LTV). The 4 dropped are property-type / investor dummies.
**Sufficiency reported conservatively at the loan-cluster level:** EPV ≈ 1,011; Riley 5,177 required vs
**50,049 loans (9.7×)** — not the flattering 622k-row figure (120×), since the rows are clustered. Event-rich,
no shortfall.

## G2 — Importance Attribution · A · `4802715c`
Sampled SPVIM Shapley under grouped CV (9 real + 10 shadows = 19 > 15 → sampled, P8; 200 permutations).
Shadow bar **0.00089**. **All 9 players confirmed** (freq 1.00). Dominant `interest_rate_time` (~60× bar) and
`LTV_time` — both time-varying; macro `grp[hpi_time+uer_time]` and `gdp_time` also confirm. All 10 shadow-null
players rejected (top shadow freq 0.85). The hazard framing genuinely extracts trajectory + macro signal.

## G3 — Parsimony Selection · A · `ba6d95cb`
**PARSIMONY-NULL**: k = 9 of 9 (11 columns). At n = 622,489 DeLong distinguishes every smaller model from the
full set (k=1..8 all p ≈ 0), so the full confirmed set is adopted. Gini **0.474**, rel loss 0%. Same pattern
as the snapshot (k=6 of 6). **Caveat recorded for the methodology:** the DeLong test is over-powered by the
clustered loan-periods (pseudo-replication), so this PARSIMONY-NULL is partly an artefact — a cluster-robust
DeLong (future upgrade) may recover genuine parsimony (k=2, `interest_rate_time`+`LTV_time`, already reaches
92% of full Gini).

## G4 — Calibration (fairness N/A) · A · `a877b2b0`
**Discrimination:** AUC 0.737 / Gini 0.474 (grouped OOF; MEDIUM floor 0.70 — clears). **Calibration — tested
on the DEPLOYED (isotonically-calibrated) model, cluster-robust (held-out 10,010 loans):** per-grade backtest
**7/7 inside the cluster-bootstrap CI**; HL g=10 **p = 0.11 (raw) / 0.65 (design-effect adj.)**, g=5 0.36 /
0.69 — **not rejected**; ECE **0.0005**. *Cleaner than the snapshot run (whose HL rejected).* **Methodology
note:** the raw WOE-logistic OOF had small per-grade bias and over-rejected (1/7, HL p≈0) on the clustered
622k rows; this was resolved by (a) testing the calibrated model and (b) a cluster-robust interval — both now
automatic via `calibration_gof.deployment_backtest` wired into Stage 4. **Fairness: not computed** — no
protected attributes. Engine emitted a single clean ADOPT.

## G5 — Deployment Governance · A · `f4e28439`
Scoring controls: exact additive-WOE reason codes; adverse floor on all 11 features; reject-on-incomplete.
**No mandatory field** — near-zero missingness (only `LTV_time` 270/622,489). PD floor 0.03% / cap 99.9% (cap
never binds — isotonic ceiling ≈14.6% for a rare per-period event). Deliverables: `AEGIS_MORTGAGE_HAZARD_
CUTOFF_POLICY.md` + `SAMPLE_RUNS_MORTGAGE_HAZARD.md` (4 real loan-periods + 2 synthetic). Floor binds on
MH-R1/S1 → 0.03% AAA.

## GF — Final Go/No-Go · **GO-WITH-CONDITIONS** (engine) · `dca8af15`
`gf_engine` over the sealed gate states + §8 checklist: all gates signed; **no must-have (R1–R9) GAP**;
remediable PARTIALs on **R7** (MORTGAGE-HZ-TIME — validation is grouped i.i.d. CV only; no out-of-time /
vintage validation on a time panel; remediable with a train-past/test-future split) and **R12**
(MORTGAGE-AIACT — natural persons → EU AI Act Annex III in scope; fairness not assessable). **R4 is
SATISFIED** (deployed calibration clean) and **R6 SATISFIED** (event-rich) — the calibration scare resolved
into a methodology upgrade, not a defect. Standing scope conditions: **NEVER-DEPLOY**, **ISOTONIC-CEILING**.
**Headline:** the full time-varying + macro hazard model (Gini 0.474) barely out-discriminates the simple
6-feature origination snapshot (0.464) — the simple scorecard is preferable; the hazard run's lasting value
was forcing the cluster-robust / deployed-model calibration fix. Verdict **GO-WITH-CONDITIONS**; no blockers.
