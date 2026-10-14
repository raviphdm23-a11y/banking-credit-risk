# AEGIS run log — Taiwan UCI Credit Card

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/Taiwan_UCI_Credit_Card.csv` — 30,000 rows, 23 features, event rate 0.2212, 0 missing.
**Started:** 2026-10-13 · **Machine:** AEGIS engine (Claude) · **Human signer:** Ravi (role varies per gate RACI) · **Materiality tier:** MEDIUM
**Record:** `SHARP_TAIWAN.md`. Third governed run; third dataset with prohibited/proxy attributes (fairness).

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-TWN0 |
| 1 | G0 | **A — Exclude prohibited attrs** (tier MEDIUM) | Ravi / Data Steward | exclude prohibited before modelling, compliance-first | GEN-TWN0 | 31766dcb |
| 2 | G1 | **A — Accept screen; behavioural model** | Ravi / Model Validator | behavioural model, keep PAY_0 and report without-PAY_0 variant | 31766dcb | dcfa2d83 |
| 3 | G2 | **A — Accept attribution** | Ravi / Model Validator | data gives strong indications; all 11 confirmed at freq 1.0, clean 7–141× separation | dcfa2d83 | f30a21db |
| 4 | G3 | **A — Ratify 14-column selection (incl. EDUCATION)** | Ravi / Model Validator | ratify pre-registered selection; test EDUCATION disparate impact at G4 *(signer-accepted; rationale from evidence)* | f30a21db | 2350eaea |
| 5 | G4 | **B — Drop EDUCATION proxy** (dual) | Ravi / Risk Officer + Validator | drop proxy EDUCATION; threshold-breaching gap 0.079, removal ~0.002 Gini | 2350eaea | 16d85570 |
| 6 | G5 | **A — Standard config** | Ravi / Model Owner | mandatory PAY_0/PAY_2/LIMIT_BAL, refer policy, behavioural label | 16d85570 | 58f2b7c0 |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | strongest fair-lending posture; proxy removed; behavioural; not production-IRB | 58f2b7c0 | 2c84dccb |

**Chain:** GEN-TWN0 → 31766dcb → dcfa2d83 → f30a21db → 2350eaea → 16d85570 → 58f2b7c0 → 2c84dccb.

---

## G4 — Calibration & Fairness  ·  status: ✅ DECIDED (Option B — the gate changed the model)

**Signers:** Ravi (Risk Officer + Validator) · **2026-10-13** · entry_hash `16d85570`
**Decision:** **drop the proxy `EDUCATION`** → production model = **13 columns** (PAY_0, PAY_2–6, LIMIT_BAL,
PAY_AMT1–6). Gini **0.540** (in-sample AUC 0.770 — no performance loss), ECE 0.0117 (behavioural model).

**Fairness evidence (computed, in-sample, n=30,000):**
- **Excluded prohibited attrs (SEX/AGE/MARRIAGE):** clean — AIR 0.965–0.986, PD gaps 0.003–0.024 (all ≤0.05),
  tracking real default rates. G0 exclusion worked.
- **EDUCATION proxy:** gap 0.079 (AIR 0.881) *with* it as an input → **breached** the 0.05 threshold. After
  removal: AIR 0.900, gap **0.058** — reduced but **not eliminated**, because legitimate features correlate
  with education. Residual gap is via legitimate risk factors only and tracks actual default (HS highest) →
  defensible. **Condition TC2 updated:** monitor the residual education-correlated disparate impact at
  deployment (now proxy-free).

Rejected A (keep a threshold-breaching proxy input — weaker defensibility; removal was ~free), C (XGBoost —
transparency loss + re-test), D (NO-GO — over-conservative; prohibited attrs clean).

**Key lesson (for the paper):** removing a proxy *input* reduces but does not fully remove disparate impact —
proxies leak through correlated legitimate features. The honest fair-lending posture is: remove the proxy
*and* monitor the residual, documenting that the residual tracks real risk.

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Model Owner) · **2026-10-13** · entry_hash `58f2b7c0`
**Decision:** mandatory = `PAY_0, PAY_2, LIMIT_BAL`, `incomplete_policy='refer'`; exact WOE reason codes (R14);
enable `drift_monitor` (PSI/AUC + TC2 residual-fairness check); PD floor 0.03% automatic; behavioural-use
label enforced. No adverse-floor overlay (0 training missing). *(signer-accepted; rationale from evidence.)*
Rejected B (all-13 mandatory — over-refers), C (un-governed blanks), D.

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `2350eaea`
**Decision:** ratify the pre-registered selection — **14 columns** `[PAY_0, PAY_2–6, LIMIT_BAL, PAY_AMT1–6,
EDUCATION]`, behavioural model, Gini 0.5383, rel. loss 0.21%, DeLong p=0.1300 (smallest k passing both fixed
criteria). Only BILL_AMT6 dropped. **The proxy `EDUCATION` is selected and carries non-redundant signal**
(k=9 without it is DeLong-distinguishable, p=0.0145) → its disparate impact is tested at G4 (condition TC2).
Rejected B (fairness-motivated EDUCATION drop — defer to G4 test per G0 plan), C (return — model adequate).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `f30a21db`
**Decision:** accept the Stage-2 attribution. All 11 players (PAY_2–6 grouped) confirmed at confirmation
frequency 1.0; weakest (BILL_AMT6) 7.4× the shadow bar (0.00063), PAY_0 141×. One breaching shadow correctly
rejected. Estimator = sampled per METHODOLOGY §5.5 (22 players > 15 — fixed method, not a gate choice; P8).
EDUCATION (proxy) confirmed important (10.8×) → substantive G4 test. Rejected B (no instability to warrant return).

---

## G1 — Screening  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `dcfa2d83`
**Decision:** advance **15 candidates**; drop 5 unpredictive BILL_AMT1–5 (IV<0.02). **Scope decision:** retain
`PAY_0` (strongest predictor, IV 0.87) but **label the model behavioural / early-warning, NOT origination** —
PAY_0 is `near_target` (most-recent repayment status, unavailable at application). EDUCATION (proxy, rescued)
kept for the G4 test. **Condition TC3 (→ G3/G4):** also report a without-PAY_0 origination-time variant as a
sensitivity (METHODOLOGY §3.3). Rejected B (drop PAY_0 — loses dominant signal; use TC3 sensitivity instead),
C (drop EDUCATION — pre-empts G0/G4), D (build both fully — TC3 covers it as a sensitivity).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)

**Materiality tier:** MEDIUM · **Signer:** Ravi (Data Steward) · **2026-10-13** · entry_hash `31766dcb`
**Decision:** exclude the 3 ECOA/Reg B **prohibited** attributes (`SEX`, `AGE`, `MARRIAGE`) from the candidate
pool **before** modelling; retain the **proxy** `EDUCATION` with disparate-impact testing deferred to G4.
SHARP runs on the 20-feature eligible pool (LIMIT_BAL, PAY_0–6, BILL_AMT1–6, PAY_AMT1–6, EDUCATION).
**Conditions:** TC1 (no time axis → not-production-IRB), TC2 (EDUCATION proxy → G4 test).
Rejected B (prohibited basis enters modelling — ECOA exposure), C (over-excludes EDUCATION), D (ECOA clear).

---

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS**

**MAC Chair:** Ravi (CRO) · **2026-10-13** · entry_hash `2c84dccb`
**Verdict:** the Taiwan 13-column WOE-logistic **behavioural** model is **approved as a MEDIUM-tier reference
benchmark**, **not** production-IRB and **not** an origination model (uses near-target PAY_0). §8: 10 SATISFIED
(2 emphatically) · 1 PARTIAL · 1 GAP→condition · 0 hard GAP for the declared purpose. **Fair lending is the
strength:** prohibited attrs excluded (clean), proxy EDUCATION actively removed, residual disparate impact
monitored and risk-justified.

### Open conditions register

| ID | Condition | Tie | Discharge before |
|---|---|---|---|
| TC1 | Behavioural / not-production-IRB label; not origination | R1/CRE36.79 | IRB or origination claim |
| TC2 | Monitor residual education-correlated disparate impact (proxy-free) | ECOA / EU AI Act | scoring real customers |
| TC3 | Report without-PAY_0 origination-time variant (sensitivity) | METHODOLOGY §3.3 | origination use |
| TC-cal | Per-grade calibration backtest | R4/CRE36.122–123 | production use |
| TC-use | Use test (real-decision use) | R2/CRE36.60 | real-decision use |

### Run outcome
- **Production model:** WOE-logistic, 13 features `[PAY_0, PAY_2–6, LIMIT_BAL, PAY_AMT1–6]`, Gini 0.54, ECE 0.012.
- **Provenance:** 7 logged decisions; the **G4 fairness gate changed the model** (dropped proxy EDUCATION).
- **Status:** APPROVED (conditional). Semi-annual re-validation (MEDIUM tier).

*AEGIS gates complete (Taiwan). Required end-to-end steps — cutoff policy + acceptance demonstration — follow
(`AEGIS_TAIWAN_CUTOFF_POLICY.md` and the acceptance demonstration appended below).*

---

## Acceptance demonstration (required — use-test R2 / transparency EU AI Act Art 13 / ECOA)

Approved 13-column behavioural model + `AEGIS_TAIWAN_CUTOFF_POLICY.md`. Portfolio default 22.1%. PD floored at
0.03%. Account-management actions (behavioural model, not origination). No reason code cites a protected
attribute (proxy EDUCATION removed at G4). **Fixed 6-case standard:** 4 real applicants (actual outcome shown)
+ 2 synthetic composites (PD-floor + stress).

| Candidate | Actual | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|--:|---|---|---|
| R1-low-repaid | repaid | 7.12% | B | SCORE | PAY_AMT4, PAY_AMT6 |
| R2-mid-repaid | repaid | 16.93% | CCC | SCORE | LIMIT_BAL, PAY_AMT4, PAY_AMT2 |
| R3-mid-default | defaulted | 16.93% | CCC | SCORE | PAY_AMT2, PAY_AMT1, PAY_AMT3 |
| R4-high-default | defaulted | 71.50% | D | SCORE | PAY_0, PAY_6, PAY_5 |
| SYN-best | — | 5.44% | BB | SCORE | all protective |
| SYN-worst | — | 88.89% | D | SCORE | PAY_0, PAY_6, PAY_5 |

*(R2 repaid and R3 defaulted share PD 16.93% — the behavioural model's messy middle. SYN-best reaches only BB,
not AAA — a repayment-history model cannot certify a pristine applicant it has not observed over time.)*

Spans the risk spectrum with hand-auditable reasons. The account-management action (maintain/review/reduce)
is an institution risk-appetite input, not derived here (pricing removed). Full showcase: `SAMPLE_RUNS_TAIWAN.md`.
**Acceptance: PASS.**

## Deliverables checklist (end-to-end standard)
- [x] `SHARP_TAIWAN.md` — Stages 0–4
- [x] `AEGIS_RUN_TAIWAN.md` — G0–GF signed, hash chain intact, GF verdict
- [x] `AEGIS_TAIWAN_CUTOFF_POLICY.md` — fixed cutoffs + grades + pricing
- [x] Acceptance demonstration — `acceptance_cases/taiwan.json` + `SAMPLE_RUNS_TAIWAN.md` (6-case standard: 4 real w/ actual outcome + 2 synthetic)
- [x] Open GF conditions listed (TC1, TC2, TC3, TC-cal, TC-use)

## Condition TC-cal — DISCHARGED (2026-10-13)
Per-grade calibration backtest (held-out n=6,000): ECE 0.0120, Hosmer-Lemeshow p=0.307 (not rejected; cleanest
of the three runs), 6/7 grades within the realised 95% CI, tight CIs (30k rows). **R4 → SATISFIED.** Full table
in `SHARP_TAIWAN.md` §"Stage 4b". Open conditions now: TC1 (label), TC2 (fairness monitoring — deploy), TC3
(without-PAY_0 variant — deploy), TC-use (use-test — deploy).
