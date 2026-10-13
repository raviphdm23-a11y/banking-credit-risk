# AEGIS run log — HELOC (FICO Home Equity Line of Credit)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/heloc.csv` — 10,459 rows, 23 features, event rate 0.5219, 0 NaN (uses −7/−8/−9 "no-record" codes).
**Started:** 2026-10-13 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_HELOC.md`
**Fourth governed run — the first CLEAN run (no protected attributes), validating the corrected order (GF last,
backtest before GF).**

> **Order (corrected standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the
> cutoff policy and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-HLC0 |
| 1 | G0 | **A — Proceed with conditions** (MEDIUM) | Ravi / Data Steward | clean (no protected attrs); carry HC1 no-time-axis and HC2 without-ExternalRiskEstimate variant *(signer-accepted; rationale from evidence)* | GEN-HLC0 | f0ba22a9 |
| 2 | G1 | **A — Accept screen (22 candidates)** | Ravi / Model Validator | external-score caveat carried as HC2; only NumInstallTradesWBalance dropped *(signer-accepted; rationale from evidence)* | f0ba22a9 | 64e12ea4 |
| 3 | G2 | **A — Accept attribution** | Ravi / Model Validator | all 15 confirmed at freq ~1.0; strong players dominate; tight-margin tail non-selected *(signer-accepted; rationale from evidence)* | 64e12ea4 | 5906b25e |
| 4 | G3 | **A — Ratify 17-col selection** | Ravi / Model Validator | ratify pre-registered 17-col selection, Gini 0.587 *(signer-accepted)* | 5906b25e | 91858fd2 |
| 5 | G4 | **A — Approve WOE-logistic + HC-cal** (dual) | Ravi / Risk Officer + Validator | calibration marginal (HL p=0.051) carry monitoring/MoC; fairness N/A *(signer-accepted)* | 91858fd2 | 858f1635 |

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Model Validator) · entry_hash `91858fd2`
Ratify the pre-registered **17-column** selection (k=11), Gini **0.587** (best discrimination of the four runs),
rel. loss 0.12%, DeLong p=0.5069. 5 tail columns dropped. Clean parsimony (no proxy). Rejected B, C.

---

## G4 — Calibration (+ required backtest) & Fairness  ·  status: ✅ DECIDED (Option A, dual)

**Signers:** Ravi (Risk Officer + Validator) · **2026-10-13** · entry_hash `858f1635`
**Decision:** approve WOE-logistic (Gini 0.587). **Per-grade calibration backtest run inside G4** (ordering
fix): held-out n=2,092, ECE 0.030, **Hosmer-Lemeshow p=0.051 — passes marginally**, 5/6 grades pass; B-grade
under-prediction flagged (table in `SHARP_HELOC.md` §Stage 4b). **Condition HC-cal:** monitor calibration
closely + set a MoC for grade B. **Fairness: N/A** — no protected/proxy attributes (G0), so no disparate-impact
test (documented as not-applicable, not skipped). Rejected B (recalibrate-first — it does pass), C (XGBoost —
transparency), D (NO-GO — over-conservative).

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Model Owner) · **2026-10-13** · entry_hash `8a66effe`
Mandatory = `ExternalRiskEstimate, NetFractionRevolvingBurden`; `incomplete_policy='refer'`; exact WOE reason
codes; `drift_monitor` (PSI/AUC + HC-cal calibration watch); PD floor 0.03% automatic. No adverse-floor
overlay (0 NaN). G5 deliverables (cutoff policy + acceptance demo) produced below — **before GF**.

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `5906b25e`
**Decision:** accept. All 15 players (correlated features grouped) confirmed at confirmation frequency ≈ 1.0;
shadow bar 0.00114; strong players 8–40×, tight-margin tail (2.4–3.4×) non-selected at G3. Estimator sampled
per §5.5 (25 players > 15; P8). Rejected B (no instability).

---

## G1 — Screening  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `64e12ea4`
**Decision:** advance **22 candidates**; drop only `NumInstallTradesWBalance` (IV 0.0196). 3 columns rescued
via the non-monotonic shape-check. External-score caveat on `ExternalRiskEstimate` carried as HC2. Rejected B
(leaner cut pre-empts Stage 2), C (hard-exclude the top feature — use HC2).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)

**Materiality tier:** MEDIUM · **Signer:** Ravi (Data Steward) · **2026-10-13** · entry_hash `f0ba22a9`
**Decision:** proceed. **No eligibility exclusions** — all 23 features are credit-bureau/behavioural, no
protected/proxy attributes (first clean run). Event rate 52.2% (near-balanced benchmark). **Conditions:**
**HC1** (no time axis → not-production-IRB), **HC2** (report without-`ExternalRiskEstimate` variant — the
dominant feature is an external score flagged `external_score`; METHODOLOGY §3.3). Rejected B (ignores
external-score dependence), C (hard-excluding it loses the top predictor — use HC2 sensitivity), D.

---

## Acceptance demonstration (required — produced BEFORE GF)

Approved 17-col model + `AEGIS_HELOC_CUTOFF_POLICY.md`. Portfolio default 52.2% (balanced benchmark). PD
floored at 0.03%. All reason codes are legitimate credit-bureau factors (no protected attributes exist).

| Customer | Calibrated PD | Grade | Decision | Indic. rate | Principal reasons |
|---|--:|---|---|--:|---|
| **HE-strong** | 1.9% | A | **APPROVE (standard)** | 7.0% | worst recent delinquency grade (minor) |
| **HE-good** | 17.6% | CCC | **APPROVE (risk-based)** | 14.8% | high revolving utilization, worst-ever delinquency, external score |
| **HE-refer** | 22.5% | CC | **REFER (manual)** | 17.2% | many revolving accounts w/ balances, worst-ever delinquency, utilization |
| **HE-weak** | 90.1% | D | **DECLINE** | 20.0% | recent delinquency, thin file, installment mix |

Spans approve / refer / decline with hand-auditable reasons. **Acceptance: PASS.**

---

| 6 | G5 | **A — Standard config** | Ravi / Model Owner | mandatory ExternalRiskEstimate/NetFractionRevolvingBurden, refer, exact reason codes | 858f1635 | 8a66effe |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | clean run; marginal calibration visible at GF; heightened cal monitoring; not production-IRB | 8a66effe | a291ab7d |

**Chain:** GEN-HLC0 → f0ba22a9 → 64e12ea4 → 5906b25e → 91858fd2 → 858f1635 → 8a66effe → a291ab7d.

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS** (ruled with full visibility)

**MAC Chair:** Ravi (CRO) · **2026-10-13** · entry_hash `a291ab7d`
**Verdict:** approved as a MEDIUM-tier reference benchmark, **not** production-IRB. **First run executed in the
corrected order** — the per-grade backtest (G4), cutoff policy and acceptance demonstration were all complete
and **visible at GF**, so the MAC factored the *marginal* calibration (HL p=0.051) into the verdict as
heightened calibration monitoring rather than discovering it after approval. **Fairness N/A** (no protected
attributes — the clean case). Discrimination the strongest of the four runs (Gini 0.587).

### Open conditions register

| ID | Condition | Tie | Discharge before |
|---|---|---|---|
| HC1 | Not-production-IRB label; no time axis | R1/CRE36.79 | IRB claim |
| HC2 | Report without-`ExternalRiskEstimate` variant (don't be a repackaged external score) | METHODOLOGY §3.3 | internal-only use |
| HC-cal | Heightened calibration monitoring + MoC for grade B (HL p=0.051 marginal) | R4/CRE36.122–123 | production use |
| HC-use | Use test | R2/CRE36.60 | real-decision use |

### Run outcome
- **Production model:** WOE-logistic, 17 features, Gini 0.587, held-out AUC 0.79; calibration marginal (HL p=0.051).
- **Provenance:** 7 logged decisions; backtest + policy + acceptance demo produced **before** GF (corrected order).
- **Status:** APPROVED (conditional), heightened calibration watch. Semi-annual re-validation.

## Deliverables checklist (end-to-end standard — corrected order)
- [x] `SHARP_HELOC.md` — Stages 0–4 + Stage 4b backtest
- [x] **Per-grade calibration backtest (in G4, before GF)** — HL p=0.051, 5/6 grades pass
- [x] `AEGIS_HELOC_CUTOFF_POLICY.md` — fixed cutoffs + grades + pricing
- [x] Acceptance demonstration — 4 candidates with decisions + reason reports
- [x] `AEGIS_RUN_HELOC.md` — G0–G5 signed, **GF ruled last with visibility**, chain intact
- [x] Open GF conditions listed

*AEGIS run complete (HELOC) — validated the corrected GF-last ordering.*
