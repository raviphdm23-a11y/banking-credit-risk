# AEGIS run log — CREDITRISK (Kaggle "Credit Risk Dataset", laotse)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/credit_risk_dataset.csv` — 32,581 rows, 12 real columns (+5 empty junk).
**Started:** 2026-10-14 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_CREDITRISK.md`
**Eighth governed run — the DATA-INTEGRITY showcase: a corrupted label column, 5 empty junk columns, and
impossible values, all caught at G0 — plus fairness (age) and availability (loan_grade/int_rate) themes.**

> **Order (corrected standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the
> decisioning note and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-CR0 |
| 1 | G0 | **A — Adopt loan_status; reject corrupt target; drop junk; exclude age; flag impossibles** (MEDIUM) | Ravi / Data Steward | data-integrity resolved: loan_status verified monotonic; corrupt target + 5 junk cols rejected; age excluded; loan_grade/int_rate flagged | GEN-CR0 | 1685ce74 |
| 2 | G1 | **A — Accept screen; advance 8 of 9** | Ravi / Model Validator | let Stage 2 arbitrate; drop cb_person_cred_hist_length (IV 0.004); IV>0.5 leakage-check resolves to circular availability (loan_grade/int_rate) + legitimate affordability (loan_percent_income); carry CR-avail | 1685ce74 | 1290421a |
| 3 | G2 | **A — Accept attribution; all 8 players confirmed** | Ravi / Model Validator | converged, all confirmed at freq 1.0, clean separation (weakest 17× bar); availability features loan_grade #2 (87×) + loan_int_rate #4 (72×) confirmed; carry CR-avail | 1290421a | d26a215f |
| 4 | G3 | **A — Ratify 6-col benchmark; origination-only variant as headline sensitivity** | Ravi / Model Validator | ratify k=6 (Gini 0.760) for comparability, loan_grade/int_rate flagged not-origination; carry origination-only 4-col (Gini 0.591) — largest circularity cost of any run (−22.2%) | d26a215f | 66a5c9e6 |
| 5 | G4 | **A — Approve 6-col WoE-logistic** (dual) | Ravi / Risk Officer + Validator | backtest passes (HL p=0.716, 9/9 grades, full AAA–D, ECE 0.007); age disparate impact negligible (<0.05, predictive parity); carry CR-avail + CR-orig | 66a5c9e6 | 5eb1f19b |
| 6 | G5 | **A — Standard config; origination-available mandatory fields** | Ravi / Model Owner | mandatory loan_percent_income+person_income (not loan_grade/int_rate); refer; no adverse floor (deployable origination-only model missing-free); exact reason codes; reaffirm CR-orig | 5eb1f19b | 7a0fab55 |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | data-integrity showcase (corrupt target rejected, loan_status verified); strong Gini 0.760 + calibration HL p=0.716 + age fairness clean; availability caveat, deploy origination-only 4-col | 7a0fab55 | **13290780** |

**Chain:** GEN-CR0 → 1685ce74 → 1290421a → d26a215f → 66a5c9e6 → 5eb1f19b → 7a0fab55 → 13290780.

---

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS** (ruled with full visibility)

**MAC Chair:** Ravi (CRO) · **2026-10-14** · entry_hash `13290780`
**Verdict:** the CREDITRISK 6-column WOE-logistic model is **approved as a MEDIUM-tier reference benchmark**,
**not** production-IRB. Ruled **after** the per-grade backtest (G4), the decisioning note and
`SAMPLE_RUNS_CREDITRISK.md` were complete and visible (corrected order). **The data-integrity showcase of the
corpus.**

**Strengths (what GF saw):**
- **Data integrity handled at source** — a corrupted `target` column (73.9% agreement, nonsensical grade pattern)
  and 5 empty junk columns were caught and rejected at G0; the run uses the **verified `loan_status`** label.
- **Discrimination** Gini 0.760 / AUC 0.877 — 2nd-strongest of the eight runs, full AAA–D spread.
- **Calibration** HL p=0.716, 9/9 grades within CI, ECE 0.007 — excellent.
- **Fairness** — age disparate impact negligible (all gaps < 0.05, predictive parity; age excluded).

**The governing caveat — availability.** `loan_grade` (incumbent risk verdict) and `loan_int_rate` (risk-based
price) are not valid origination-time inputs; the 6-col benchmark is comparability-only. The **deployable
application-time model is the 4-col origination-only variant** (Gini 0.591, HELOC-tier, independent) — removing
the circular features costs 22.2%, the largest of any run.

### Open conditions register

| ID | Condition | Tie | Discharge before |
|---|---|---|---|
| CR-label | Use verified `loan_status`; corrupted `target` rejected (provenance) | R10 / BCBS 239 | any reuse of the file |
| CR-avail | `loan_grade` + `loan_int_rate` circular — benchmark not origination-valid | METHODOLOGY §3.3 | origination use |
| CR-orig | Origination deployments use the 4-col origination-only model (Gini 0.591) | R2 use-test | application-time use |
| CR-age | Age excluded; monitor age disparate impact | ECOA / EU AI Act | scoring real customers |
| CR-dq | Impossible values (age 144, emp_length 123) → upstream data-quality fix | R10 / BCBS 239 | production use |
| CR-use | Use test | R2 / CRE36.60 | real-decision use |

### Run outcome
- **Benchmark model:** WOE-logistic, 6 features, Gini 0.760, AUC 0.877; calibration excellent (HL p=0.716).
- **Deployable model:** 4-col origination-only, Gini 0.591, independent of the incumbent's verdict.
- **Provenance:** 7 logged decisions, hash chain intact (GEN-CR0 → 13290780); data-integrity finding resolved at G0.
- **Status:** APPROVED (conditional). Semi-annual re-validation.

## Deliverables checklist (end-to-end standard — corrected order)
- [x] `SHARP_CREDITRISK.md` — Stages 0–4 + Stage 4b backtest + availability sensitivity + age fairness
- [x] **Per-grade calibration backtest (in G4, before GF)** — HL p=0.716, 9/9 grades pass
- [x] `AEGIS_CREDITRISK_CUTOFF_POLICY.md` — decisioning note (grades; institution threshold; no pricing; integrity + availability caveats)
- [x] Acceptance demonstration — `acceptance_cases/creditrisk.json` + `SAMPLE_RUNS_CREDITRISK.md` (6-case standard)
- [x] `AEGIS_RUN_CREDITRISK.md` — G0–G5 signed, **GF ruled last** with visibility — **GO-WITH-CONDITIONS**, chain intact
- [x] Open GF conditions listed, each with its discharge point

*AEGIS run complete (CREDITRISK) — eighth governed run; the data-integrity showcase (corrupted label caught at
G0) plus the largest availability/circularity cost of any run.*

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Owner) · **2026-10-14** · entry_hash `7a0fab55`
Mandatory = `loan_percent_income`, `person_income` (strongest **origination-available** predictors —
deliberately **not** `loan_grade`/`loan_int_rate`, which are availability-flagged); `incomplete_policy='refer'`;
**no adverse-floor overlay** — the deployable origination-only 4-col model is **missing-free** (all 4 features
0 missing); the benchmark's `loan_int_rate` (9.6% missing, mildly protective 0.94×) is handled by the learned
`__missing__` bin and is a flagged not-deployable feature. Exact WoE reason codes; PD floor 0.03% automatic;
`drift_monitor` (PSI/AUC) + age-disparate-impact watch. **CR-orig reaffirmed:** deploy the 4-col origination-only
model. Rejected B (adverse floor/mandatory on `loan_int_rate` — moot, it's excluded from the deployable model),
C (un-governed incomplete applications). **G5 deliverables (decisioning note + acceptance pack) produced below —
before GF.**

### Acceptance demonstration (committee pack: `SAMPLE_RUNS_CREDITRISK.md`, inputs `acceptance_cases/creditrisk.json`)
**Fixed 6-case standard:** 4 real applicants (actual outcome shown) + 2 synthetic composites (PD-floor + stress).
Strong, clean gradient — contrast PAK; label is the **verified `loan_status`** (corrupt target rejected at G0).

| Candidate | Type | Outcome | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|---|--:|---|---|---|
| R1-low-repaid | real | repaid | 2.03% | BBB | SCORE | person_income |
| R2-mid-repaid | real | repaid | 8.78% | B | SCORE | loan_grade, loan_int_rate |
| R3-mid-default | real | defaulted | 8.78% | B | SCORE | person_home_ownership, person_income |
| R4-high-default | real | defaulted | 89.12% | D | SCORE | loan_percent_income, person_income, person_home_ownership |
| SYN-best | synthetic | repaid (by design) | 0.03% | AAA | SCORE | all protective (PD floor hit) |
| SYN-worst | synthetic | default (by design) | 99.90% | D | SCORE | loan_grade, loan_percent_income, person_income |

*(Accept/refer/decline threshold is an institution input, not derived here — no pricing. R2 repaid and R3
defaulted share PD 8.78% (messy middle); SYN-best confirms the 0.03% floor. The benchmark's reasons include the
availability-flagged `loan_grade`/`loan_int_rate`; the deployable origination-only model excludes them. Full
showcase: `SAMPLE_RUNS_CREDITRISK.md`; decisioning note: `AEGIS_CREDITRISK_CUTOFF_POLICY.md`.)*

---

## G4 — Calibration (+ required backtest) & Fairness  ·  status: ✅ DECIDED (Option A, dual)
**Signers:** Ravi (Risk Officer + Validator) · **2026-10-14** · entry_hash `5eb1f19b`
**Calibration (per-grade backtest, inside G4):** 80/20 held-out (seed 42), test n=6,517. **9/9 populated grades
within CI, ECE 0.007, Hosmer-Lemeshow χ²=5.38 df=8 p=0.716 → not rejected** (table in `SHARP_CREDITRISK.md`
§Stage 4b). Strong discrimination *and* excellent calibration — full AAA–D spectrum, 241 applicants reach AAA,
honest grade-by-grade PDs (AUC 0.877). **Fairness (age disparate impact; `person_age` excluded from model but
tested):** every mean-PD gap **< 0.05** and tracks actual default tightly (predictive parity — <25 model 0.230
vs actual 0.232; 55+ 0.241 vs 0.245). No material disparate impact; age is not an input. **Conditions:**
**CR-avail** (`loan_grade`+`loan_int_rate` circular, retained-but-flagged) and **CR-orig** (origination-only 4-col
= the valid deployable model). Rejected B (switch to origination-only primary — sensitivity captures it), C
(NO-GO — strong+calibrated), D (recalibrate unnecessary).

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Validator) · **2026-10-14** · entry_hash `66a5c9e6`
**Decision:** ratify the pre-registered **k = 6 → 6-column** selection as the MEDIUM-tier **benchmark**
(`loan_percent_income, loan_grade, person_income, loan_int_rate, person_home_ownership, loan_intent`),
Gini **0.760** (2nd-strongest of 8 runs), rel. loss −0.01%, DeLong p 0.883. `loan_grade`/`loan_int_rate` are
**retained-but-flagged** (not an origination-time model), preserving comparability. **Grounded availability
sensitivity (faithful 5-fold OOF, seed 42):** the 4-col **origination-only** model (dropping both flagged)
scores Gini **0.591** / AUC 0.796 vs 0.760 / 0.880 — ΔGini 0.169 (**−22.2% relative**, the **largest circularity
cost of any run**), DeLong p ≈ 0 (z=36). `loan_grade` alone is the incumbent lender's risk verdict (adding it
jumps Gini 0.43→0.67). The origination-only model is still genuinely usable (HELOC-tier) and **independent**.
**Condition CR-orig:** the origination-only 4-col model is the **headline deployable variant**, reported at G4.
Rejected B (adopt origination-only as primary — strong case; sensitivity captures it, comparability retained),
C (NO-GO — solid independent signal remains).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-14** · entry_hash `d26a215f`
**Decision:** accept. **All 8 real players confirmed** at confirmation frequency 1.00; shadow bar 0.00085;
sampled estimator (18 players > 15, P8), converged (200 perms, 13,875 fits, max MC SE 0.0051; efficiency audit
5.6e-17). Clean separation — weakest player `person_emp_length` is 17× the noise floor. The two **availability
features rank high**: `loan_grade` #2 (0.0742, 87×) and `loan_int_rate` #4 (0.0615, 72×) — they carry real
weight, so CR-avail's without-them sensitivity is the decisive G3/G4 test. Rejected B (no instability — all
confirmed at freq 1.00).

---

## G1 — Univariate Screening  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-14** · entry_hash `1290421a`
**Decision:** advance the **8 candidates** that pass Stage 1; drop `cb_person_cred_hist_length` (IV 0.0044).
**Strong signal:** five features at "strong" IV (>0.3), three **above 0.5** (the "check-for-leakage" band):
`loan_percent_income` 0.876, `loan_grade` 0.858, `loan_int_rate` 0.675. The leakage-check resolves cleanly —
`loan_grade` (incumbent lender's risk grade) and `loan_int_rate` (risk-based price) are **circular availability
features** (CR-avail → without-them sensitivity at G3/G4), while `loan_percent_income` is a **genuine
debt-affordability ratio** (loan/income), high IV but not leakage. **Condition CR-avail** carried. Rejected
B (hard-exclude loan_grade/int_rate pre-empts Stage 2; sensitivity captures the cost), C (premature halt —
strong genuine origination signal exists: loan_percent_income, person_income, home ownership).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Data Steward) · **2026-10-14** · entry_hash `1685ce74`

**Materiality tier:** MEDIUM (reference benchmark, not production-IRB — consistent with the seven prior runs).

### Target verification (data-integrity — resolved first, per request)
The file ships **two** binary label columns. `target` is **corrupted** and must be rejected:
- `target` vs `loan_status` agree on only **73.9%** of rows (rates 17.6% vs 21.8%).
- `target` default rate by loan grade is **nonsensical** (A 0%, B 0%, then C–G flat ~50%).
- `loan_status` is the genuine label: default rate rises **monotonically** A 10% → G 98%; higher interest rate
  for defaulters (13.06% vs 10.44%); sensible home-ownership gradient (OWN 7.5% vs RENT 31.6%) — and matches the
  known public "Credit Risk Dataset" default flag.
**→ Adopt `loan_status` as the label; reject `target`.**

### Other integrity / scope findings
- **5 empty junk columns** `Unnamed: 12–16` (all-NaN / blank) → drop.
- **Impossible values:** `person_age` max 144; `person_emp_length` max 123 years (2 rows > 60) → data-quality flag.
- **Prohibited (ECOA/Reg B):** `person_age` → exclude before modelling.
- **Availability (prior-decision artifacts):** `loan_grade` (incumbent lender's own risk grade) and
  `loan_int_rate` (risk-based price) → flag, carry without-them sensitivity (cf. LOAN).

**Machine recommendation — Option A:** adopt `loan_status`, reject `target`; drop the 5 junk columns; exclude
prohibited `person_age`; flag the impossible values; retain-and-flag `loan_grade`/`loan_int_rate` with a
without-them sensitivity. Run SHARP on the resulting **9-feature eligible pool**.

Eligible pool (9): `person_income, person_home_ownership, person_emp_length, loan_intent, loan_grade, loan_amnt,
loan_int_rate, loan_percent_income, cb_person_cred_hist_length`.

*(Options presented in chat; signed row appended on decision.)*
