# AEGIS run log — GMSC (Give Me Some Credit)

**Framework:** AEGIS v1.0 · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/GMSC.csv` — 149,391 rows, 10 features, event rate 0.067, real missing values.
**Started:** 2026-10-13 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_GMSC.md`
**Fifth governed run — tests missing-value governance at scale + fairness (age), with plenty of events (10,009).**

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-GMSC0 |
| 1 | G0 | **A — Exclude prohibited age** (MEDIUM) | Ravi / Data Steward | exclude prohibited age before modelling; keep NumberOfDependents proxy for G4; compliance-first | GEN-GMSC0 | 9c550c96 |
| 2 | G1 | **A — Accept screen (9); sentinel caveat MC3** | Ravi / Model Validator | sentinels 96/98 isolated in WOE bin; reliability gate+escalation handled sparse cells; carry cleaned-sentinel sensitivity | 9c550c96 | 4de742cf |
| 3 | G2 | **A — Accept attribution** | Ravi / Model Validator | all 9 confirmed at freq 1.0; cleanest separation 13.5–160× bar | 4de742cf | 292df169 |
| 4 | G3 | **A — Ratify 8-col selection (incl. dependents)** | Ravi / Model Validator | ratify pre-registered selection; test NumberOfDependents proxy + age disparate impact at G4 *(signer-accepted)* | 292df169 | f567f2be |
| 5 | G4 | **A — Approve WOE + keep dependents + monitor age** (dual) | Ravi / Risk Officer + Validator | excellent calibration ECE 0.0023 HL p=0.134; age gap risk-justified; dependents proxy under threshold | f567f2be | 55aaed1e |

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Validator) · entry_hash `f567f2be` · Ratify the pre-registered **8-column** selection
(Gini 0.705, strongest of all runs; rel. loss 0.03%, DeLong p=0.1249). Only NumberOfOpenCreditLines dropped.
Proxy `NumberOfDependents` selected → G4 test.

## G4 — Calibration (+ backtest) & Fairness  ·  status: ✅ DECIDED (Option A, dual)
**Signers:** Ravi (Risk Officer + Validator) · **2026-10-13** · entry_hash `55aaed1e`
**Calibration (cleanest of all runs):** per-grade backtest **10/10 grades pass**, ECE 0.0023, HL p=0.134
(table in `SHARP_GMSC.md` §Stage 4b). **Fairness:** AGE (excluded from model) disparate impact gap 0.071
**breaches** 0.05 but **tracks real default tightly** (younger default ~4×; predictive parity band-by-band) and
age is not an input → **MC-age: monitor** (defensible). `NumberOfDependents` (retained proxy) gap 0.036 **under**
threshold, AIR 0.945, tracks real risk → **kept** (contrast Taiwan's EDUCATION which breached and was dropped).
Rejected B (precautionary drop unnecessary), C (XGBoost), D (NO-GO over-conservative).

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Owner) · **2026-10-13** · entry_hash `6987d0fb`
**Missing-value governance (returns since HMEQ):** MonthlyIncome 19.6% missing, and **missing income is
slightly *protective*** (bad 5.66% missing vs 6.95% present, 0.81× lift) — an omission trap on a self-reported
field. **Adverse floor applied to `MonthlyIncome`** (blank scored at worst-observed WOE). Mandatory =
`RevolvingUtilizationOfUnsecuredLines`, `NumberOfTime30-59DaysPastDueNotWorse`; `incomplete_policy='refer'`;
exact reason codes; PD floor auto; `drift_monitor` + MC-age fairness watch. Rejected B (mandatory income rejects
19.6%), C (leaves trap open), D. **G5 deliverables (cutoff policy + SAMPLE_RUNS pack) produced below — before GF.**

### Acceptance demonstration (committee pack: `SAMPLE_RUNS_GMSC.md`, inputs `acceptance_cases/gmsc.json`)
**Fixed 6-case standard:** 4 real applicants (actual outcome shown) + 2 synthetic composites (PD-floor + stress).

| Candidate | Actual | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|--:|---|---|---|
| R1-low-repaid | repaid | 0.70% | AA | SCORE | NumberOfDependents |
| R2-mid-repaid | repaid | 2.90% | BBB | SCORE | NumberOfDependents, RevolvingUtilization |
| R3-mid-default | defaulted | 2.90% | BBB | SCORE | DebtRatio, NumberRealEstateLoans, NumberOfDependents |
| R4-high-default | defaulted | 41.46% | C | SCORE_FLAGGED | 90d late, revolving utilization, 30-59d past due |
| SYN-best | — | 12.34% | CCC | SCORE | revolving utilization, DebtRatio, real-estate loans |
| SYN-worst | — | 58.65% | D | SCORE | 90d late, 60-89d past due, 30-59d past due |

*(Accept/refer/decline threshold is an institution input, not derived here — no pricing. R2 repaid and R3
defaulted share PD 2.90% (best-calibrated model's low-end messy middle). Full showcase: `SAMPLE_RUNS_GMSC.md`.)*

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Model Validator) · entry_hash `292df169`
Accept. All 9 players confirmed at confirmation frequency 1.0; shadow bar 0.00071; weakest real player 13.5×,
strongest 160× — cleanest separation of any run (150k rows). Proxy `NumberOfDependents` confirmed (18×) →
substantive G4 test. Sampled per §5.5 (P8). Rejected B.

---

## G1 — Screening  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `4de742cf`
**Decision:** advance all **9 candidates**. **Sentinel finding (new):** the 3 delinquency-count columns carry
codes **96 (×5) / 98 (×220)** — SHARP flagged them; the reliability gate correctly failed on
NumberOfTimes90DaysLate & NumberOfTime60-89 (sentinel sparse cells) and **escalation confirmed real signal**;
WOE binning isolates the sentinels. MonthlyIncome 19.6% missing → learned `__missing__` bin (→ G5).
**Condition MC3:** run a cleaned-sentinel sensitivity (recode 96/98 → missing) as a check. Rejected B (clean
+ re-run — the WOE binning + escalation already handle it; MC3 covers the sensitivity), C (would gut the model).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)

**Materiality tier:** MEDIUM · **Signer:** Ravi (Data Steward) · **2026-10-13** · entry_hash `9c550c96`
**Decision:** exclude the ECOA/Reg B **prohibited** attribute `age` from the candidate pool before modelling;
retain the **proxy** `NumberOfDependents` with disparate-impact testing deferred to G4. SHARP runs on the
9-feature eligible pool. **Conditions:** MC1 (no time axis → not-production-IRB), MC2 (NumberOfDependents
proxy → G4 test), and (carried to G5) the missing-value governance for MonthlyIncome (19.6%) + NumberOfDependents.
Rejected B (ECOA exposure), C (over-excludes NumberOfDependents), D (ECOA clear).

---

*(G1 onward recorded after the SHARP run completes.)*

---

| 6 | G5 | **A — Standard config + adverse floor on income** | Ravi / Model Owner | adverse floor MonthlyIncome (missing-protective omission trap); mandatory utilization+delinquency; refer | 55aaed1e | 6987d0fb |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | best discrimination+calibration of 5 runs; missing-value+fairness handled; not production-IRB | 6987d0fb | 3bc6f197 |

**Chain:** GEN-GMSC0 → 9c550c96 → 4de742cf → 292df169 → f567f2be → 55aaed1e → 6987d0fb → 3bc6f197.

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS** (ruled with full visibility)

**MAC Chair:** Ravi (CRO) · **2026-10-13** · entry_hash `3bc6f197`
**Verdict:** the GMSC 8-column WOE-logistic model is **approved as a MEDIUM-tier reference benchmark**, **not**
production-IRB. Ruled after G4's backtest and G5's decisioning note + `SAMPLE_RUNS_GMSC.md` were complete and
visible (corrected order). **Strengths:** best discrimination (Gini 0.705) and best calibration (per-grade
backtest 10/10 grades, ECE 0.0023) of all five runs; missing-value governance (adverse floor on income);
fairness handled (age excluded, disparate impact risk-justified; proxy under threshold, kept).

### Open conditions register

| ID | Condition | Tie | Discharge before |
|---|---|---|---|
| MC1 | Not-production-IRB label; no time axis | R1/CRE36.79 | IRB claim |
| MC-age | Monitor age-correlated disparate impact (age excluded; gap risk-justified) | ECOA / EU AI Act | scoring real customers |
| MC3 | Cleaned-sentinel sensitivity (recode delinquency-count 96/98 → missing) | R10/BCBS 239 | production use |
| MC-use | Use test | R2/CRE36.60 | real-decision use |

### Run outcome
- **Production model:** WOE-logistic, 8 features, Gini 0.705, ECE 0.0023 (cleanest calibration of all runs).
- **Provenance:** 7 logged decisions; missing-value governance (adverse floor on income) exercised at scale.
- **Status:** APPROVED (conditional). Semi-annual re-validation.

## Deliverables checklist (end-to-end standard — corrected order)
- [x] `SHARP_GMSC.md` — Stages 0–4 + Stage 4b backtest
- [x] **Per-grade calibration backtest (in G4, before GF)** — 10/10 grades pass, ECE 0.0023
- [x] `AEGIS_GMSC_CUTOFF_POLICY.md` — decisioning note (grades; institution threshold; no pricing)
- [x] Acceptance demonstration — `acceptance_cases/gmsc.json` + `SAMPLE_RUNS_GMSC.md` (6-case standard: 4 real w/ actual outcome + 2 synthetic)
- [x] `AEGIS_RUN_GMSC.md` — G0–G5 signed, **GF ruled last** with visibility, chain intact
- [x] Open GF conditions listed

*AEGIS run complete (GMSC) — fifth governed run; missing-value governance at scale + best calibration.*
