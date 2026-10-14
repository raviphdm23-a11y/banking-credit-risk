# AEGIS run log — LOAN (LendingClub 2007–2010 educational subset)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/loan_data.csv` — 9,578 rows, 13 features + target, event rate 0.1601 (1,533 events), 0 missing.
**Started:** 2026-10-13 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_LOAN.md`
**Seventh governed run — clean (no protected attributes, like HELOC); the showcase for AVAILABILITY governance:
three features are prior-decision / external-model artifacts (`int.rate` risk-based pricing, `credit.policy`
underwriting-screen outcome, `fico` external score).**

> **Order (corrected standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the
> decisioning note and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-LOAN0 |
| 1 | G0 | **A — Proceed on full pool; retain-and-flag availability features** (MEDIUM) | Ravi / Data Steward | clean (no protected attrs); let SHARP availability screen flag int.rate/credit.policy/fico; carry without-them sensitivity | GEN-LOAN0 | d424d46b |
| 2 | G1 | **A — Accept screen; advance 11 of 13** | Ravi / Model Validator | let Stage 2 arbitrate; drop dti+delinq.2yrs; 4 medium-IV features; carry LC2 (int.rate+credit.policy prior-decision) + LC3 (fico external_score) to without-them sensitivity | d424d46b | e2ad954f |
| 3 | G2 | **A — Accept attribution; all 10 players confirmed** | Ravi / Model Validator | converged, every Stage-1 survivor confirmed at freq 1.0; fico+int.rate clustered as #1 player (75× bar) confirms circularity; credit.policy #3 | e2ad954f | 326162dc |
| 4 | G3 | **A — Ratify 7-col benchmark; origination-only variant as headline sensitivity** | Ravi / Model Validator | ratify k=6 (Gini 0.343) for comparability, 3 availability features flagged not-origination; carry origination-only 4-col (Gini 0.300, better calibrated) as deployable variant | 326162dc | 8176ab7d |
| 5 | G4 | **A — Approve 7-col WoE-logistic** (dual) | Ravi / Risk Officer + Validator | backtest passes (HL p=0.437, 8/8 grades, full AAA–D spectrum, ECE 0.0175); model discriminates+spreads; fairness N/A (no protected attrs); carry LC2/LC3/LC-orig | 8176ab7d | 3db377b8 |
| 6 | G5 | **A — Standard config; origination-available mandatory fields** | Ravi / Model Owner | mandatory inq.last.6mths+revol.util (not fico/int.rate); refer; no adverse floor (0 missing); exact reason codes; reaffirm LC-orig | 3db377b8 | 3f6813c6 |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | sound discrimination+calibration+fairness-clean; availability caveat (benchmark not origination-valid; deploy 4-col origination-only); clean contrast to PAK NO-GO | 3f6813c6 | **1bf26785** |

**Chain:** GEN-LOAN0 → d424d46b → e2ad954f → 326162dc → 8176ab7d → 3db377b8 → 3f6813c6 → 1bf26785.

---

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS** (ruled with full visibility)

**MAC Chair:** Ravi (CRO) · **2026-10-14** · entry_hash `1bf26785`
**Verdict:** the LOAN 7-column WOE-logistic model is **approved as a MEDIUM-tier reference benchmark**, **not**
production-IRB. Ruled **after** the per-grade backtest (G4), the decisioning note and `SAMPLE_RUNS_LOAN.md` were
complete and visible (corrected order). **The clean contrast to PAK's NO-GO.**

**Strengths (what GF saw):**
- **Discrimination** Gini 0.343 / AUC 0.668 — genuinely separates risk, spreading applicants across the full
  **AAA–D** spectrum (acceptance pack shows a real BB→C gradient; the model identifies low-risk applicants).
- **Calibration** HL p=0.437, 8/8 populated grades within CI, ECE 0.0175 — honest PDs grade-by-grade.
- **Fairness N/A** — no protected/proxy attributes (the clean case).

**The governing caveat — availability.** Three of the seven benchmark features (`fico` external score; `int.rate`,
`credit.policy` prior-decision artifacts) are **not valid origination-time inputs**, so the 7-col benchmark is for
literature comparability only. Unlike PAK, a valid **origination-only model stands on its own** (4-col, Gini
0.300, better calibrated ECE 0.003) and is the deployable application-time model.

### Open conditions register

| ID | Condition | Tie | Discharge before |
|---|---|---|---|
| LC1 | Not-production-IRB label; no time axis | R1 / CRE36.79 | IRB claim |
| LC2 | `int.rate` + `credit.policy` = prior-decision artifacts — benchmark not origination-valid | METHODOLOGY §3.3 | origination use |
| LC3 | `fico` external score — report with/without | METHODOLOGY §3.3 | internal-only use |
| LC-orig | Origination deployments use the 4-col origination-only model (Gini 0.300) | R2 use-test | application-time use |
| LC-use | Use test | R2 / CRE36.60 | real-decision use |

### Run outcome
- **Benchmark model:** WOE-logistic, 7 features, Gini 0.343, AUC 0.668; calibration sound (HL p=0.437).
- **Deployable model:** 4-col origination-only, Gini 0.300, better calibrated (ECE 0.003).
- **Provenance:** 7 logged decisions, hash chain intact (GEN-LOAN0 → 1bf26785).
- **Status:** APPROVED (conditional). Semi-annual re-validation.

## Deliverables checklist (end-to-end standard — corrected order)
- [x] `SHARP_LOAN.md` — Stages 0–4 + Stage 4b backtest + availability sensitivity + fairness-N/A
- [x] **Per-grade calibration backtest (in G4, before GF)** — HL p=0.437, 8/8 grades pass
- [x] `AEGIS_LOAN_CUTOFF_POLICY.md` — decisioning note (grades; institution threshold; no pricing; availability caveat)
- [x] Acceptance demonstration — `acceptance_cases/loan.json` + `SAMPLE_RUNS_LOAN.md` (6-case standard: 4 real w/ actual outcome, BB→C + 2 synthetic; SYN-best floors at AAA)
- [x] `AEGIS_RUN_LOAN.md` — G0–G5 signed, **GF ruled last** with visibility — **GO-WITH-CONDITIONS**, chain intact
- [x] Open GF conditions listed, each with its discharge point

*AEGIS run complete (LOAN) — seventh governed run; the availability-governance showcase and the clean deployable
contrast to PAK's NO-GO.*

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Owner) · **2026-10-14** · entry_hash `3f6813c6`
**Clean-data config (0 missing, as HELOC).** Mandatory = `inq.last.6mths`, `revol.util` (the strongest
**origination-available** predictors — deliberately **not** `fico`/`int.rate`, which are availability-flagged);
`incomplete_policy='refer'`; **no adverse-floor overlay** (0 training missing); exact WoE reason codes; PD floor
0.03% automatic; `drift_monitor` (PSI/AUC). **LC-orig reaffirmed:** an origination deployment uses the **4-col
origination-only model**, not the 7-col benchmark that contains the circular/external features. Rejected B
(mandatory `fico` contradicts origination-only + availability flags), C (un-governed incomplete applications).
**G5 deliverables (decisioning note + acceptance pack) produced below — before GF.**

### Acceptance demonstration (committee pack: `SAMPLE_RUNS_LOAN.md`, inputs `acceptance_cases/loan.json`)
**Fixed 6-case standard:** 4 real applicants (actual outcome shown, spanning the risk range with both outcomes)
+ 2 synthetic composites (built from observed feature-value extremes — PD-floor check + stress check).
**Predicted vs actual is sensible** (contrast PAK): repaid cases sit low, defaulters high.

| Candidate | Type | Actual | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|---|--:|---|---|---|
| R1-low-repaid | real | repaid | 4.46% | BB | SCORE | revol.util |
| R2-mid-repaid | real | repaid | 15.04% | CCC | SCORE | int.rate, log.annual.inc, fico |
| R3-mid-default | real | defaulted | 17.42% | CCC | SCORE | fico, int.rate, revol.util |
| R4-high-default | real | defaulted | 38.52% | C | SCORE | purpose, log.annual.inc, fico |
| SYN-best | synthetic | — | 0.03% | AAA | SCORE | all protective (PD floor hit) |
| SYN-worst | synthetic | — | 80.00% | D | SCORE | purpose, inq.last.6mths, log.annual.inc |

*(Accept/refer/decline threshold is an institution input, not derived here — no pricing. Honest messy-middle:
R2 repaid at 15.0% vs R3 defaulted at 17.4% — close but correctly ordered; SYN-best confirms the 0.03% floor.
Full showcase: `SAMPLE_RUNS_LOAN.md`; decisioning note: `AEGIS_LOAN_CUTOFF_POLICY.md`.)*

---

## G4 — Calibration (+ required backtest) & Fairness  ·  status: ✅ DECIDED (Option A, dual)
**Signers:** Ravi (Risk Officer + Validator) · **2026-10-14** · entry_hash `3db377b8`
**Calibration (per-grade backtest, inside G4):** 80/20 held-out (seed 42), test n=1,916. **8/8 populated grades
within CI, ECE 0.0175, Hosmer-Lemeshow χ²=6.93 df=7 p=0.437 → not rejected** (table in `SHARP_LOAN.md` §Stage 4b).
Unlike PAK, the model **spreads applicants across the full AAA–D spectrum** (46 reach AAA — it can identify
low-risk applicants) with honest grade-by-grade PDs; AUC 0.668, Gini 0.343. The origination-only 4-col variant is
**better calibrated** (OOF ECE 0.003). **Fairness: N/A** — no protected/proxy attributes (G0), so no
disparate-impact test (documented as not-applicable, not skipped) — the clean case, as HELOC. **Conditions:**
**LC2** (`int.rate`+`credit.policy` prior-decision), **LC3** (`fico` external score), **LC-orig** (origination-
only 4-col = the valid application-time model). Rejected B (switch to origination-only primary — sensitivity
captures it), C (NO-GO — sound), D (recalibrate unnecessary — calibration passes).

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Validator) · **2026-10-14** · entry_hash `8176ab7d`
**Decision:** ratify the pre-registered **k = 6 → 7-column** selection as the MEDIUM-tier **benchmark**
(`fico [external_score], int.rate, inq.last.6mths, credit.policy, purpose, revol.util, log.annual.inc`),
Gini **0.343**, rel. loss 2.63%, DeLong p 0.0743. The three availability-flagged features (`fico, int.rate,
credit.policy`) are **retained-but-flagged** — "not an origination-time (application) model" (METHODOLOGY §3.3) —
preserving comparability. **Grounded availability sensitivity (faithful 5-fold OOF, seed 42, same WoE-logistic):**
the 4-col **origination-only** model (dropping all three flagged) scores Gini **0.300** / AUC 0.650 vs 0.343 /
0.672 — ΔGini 0.043 (**−12.4% relative**), DeLong p 2e-06, and is **better calibrated** (ECE 0.003 vs 0.0079).
**The model does not collapse without the circular features** — a genuinely usable application-time model remains
(contrast PAK). **Condition LC-orig:** the origination-only 4-col model is the **headline deployable variant**
(the only valid application-time model), reported at G4. Rejected B (adopt origination-only as primary — strong
here, but sensitivity captures it and benchmark comparability is retained), C (NO-GO — real signal exists).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-14** · entry_hash `326162dc`
**Decision:** accept. **All 10 real players confirmed** at confirmation frequency 1.00 (nothing dropped — contrast
PAK); shadow bar 0.00055; sampled estimator (20 players > 15, P8), converged (200 perms, 16,145 fits, max MC SE
0.00263; efficiency audit 2.8e-17). **Structural finding:** `fico` and `int.rate` are correlated enough (ρ > 0.7)
to be **grouped into a single player**, which is the **#1 contributor (0.0415, 75× the noise floor)** — the
quantitative signature of the circularity (external score + lender's risk-based price carry the same risk
information). `credit.policy` is #3 (53×). Weakest confirmed player `days.with.cr.line` 6.5× bar. Carry LC2/LC3.
Rejected B (no instability — all confirmed at freq 1.00, well-separated from shadows).

---

## G1 — Univariate Screening  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-14** · entry_hash `e2ad954f`
**Decision:** advance the **11 candidates** that pass Stage 1; drop `dti` (IV 0.013) and `delinq.2yrs` (IV 0.002).
**Healthy signal spread:** four features reach "medium" IV — `int.rate` 0.243 (highest), `fico` 0.195,
`credit.policy` 0.159, `inq.last.6mths` 0.151; the rest weak. 6 columns rescued via escalation (shape-check /
Mann-Whitney). **Availability (key governance point):** SHARP's name-based screen flagged **only `fico`**
(`external_score`); `int.rate` and `credit.policy` were **not** auto-flagged but are carried by governance
judgment as **prior-decision artifacts** — the evidence supports this (int.rate has the highest IV and clusters
with fico as the #1 Shapley player; i.e. it encodes the incumbent lender's own risk-based price). **Conditions:**
**LC2** (`int.rate` + `credit.policy` prior-decision artifacts) and **LC3** (`fico` external score) → the
without-them sensitivity at G3/G4. Rejected B (hard-exclude int.rate+credit.policy pre-empts Stage 2; sensitivity
captures the cost), C (premature halt — genuine origination-time signal exists beyond the flagged features).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Data Steward) · **2026-10-14** · entry_hash `d424d46b`

**Materiality tier:** MEDIUM (reference benchmark, not production-IRB — consistent with the six prior runs).

**No ECOA/Reg B exclusions** — all 13 features are credit-bureau / application / behavioural; **no protected or
proxy attributes** (the second clean run after HELOC). Event rate 16.0%, 1,533 events, 0 missing.

**Availability concern (the governance interest of this run):**
- `int.rate` — the interest rate the incumbent lender **set from its own risk assessment** (risk-based pricing)
  → circular / near-target (an *output* of a prior decision, not an independent applicant characteristic).
- `credit.policy` — 1 if the applicant **met LendingClub's underwriting criteria** → a prior-decision outcome.
- `fico` — **external credit score** → `external_score` flag (METHODOLOGY §3.3; cf. HELOC `ExternalRiskEstimate`).

**Machine recommendation — Option A:** proceed on the full 13-feature pool; let SHARP's availability screen flag
`int.rate` / `credit.policy` / `fico`; **retain-and-flag** for benchmark comparability and carry a mandatory
without-those-features sensitivity (mirrors HELOC's HC2 and PAK's proxy-excluded variant). MEDIUM tier.

*(Options presented in chat; signed row appended on decision.)*
