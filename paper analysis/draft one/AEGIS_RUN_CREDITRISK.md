# AEGIS run log — CREDITRISK (Kaggle "Credit Risk Dataset", laotse) — CLEANED-FILE RE-RUN

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3.1 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/credit_risk_dataset.csv` — **cleaned** (corrupt `target` deleted, genuine `loan_status`
renamed `target`, 5 junk cols dropped; original at `credit_risk_dataset.ORIGINAL_backup.csv`). 32,581 rows, event rate 0.2182.
**Started:** 2026-10-18 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_CREDITRISK.md`
**Fresh re-run from scratch on the cleaned file.** Deterministic (seed 42) → reproduces the committed SHARP analytics
(8/9 screen, shadow bar 0.00085, k=6 Gini 0.7597, DeLong p 0.883). The data-integrity issue is now resolved **at source**
in the file itself (CR-label discharged), rather than handled in-pipeline as in the first run.

> **Order (standard):** gates G0→G5, with the per-grade calibration backtest inside G4; then the decisioning note and
> acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-CR0 |
| 1 | G0 | **A — Adopt cleaned label; exclude age; retain-and-flag circular pair** (MEDIUM) | Ravi / Data Steward | label resolved upstream (corrupt target deleted, loan_status→target, junk dropped, backup kept); exclude person_age (ECOA); retain-and-flag loan_grade+loan_int_rate (CR-avail); flag impossibles (CR-dq); 9-feature pool | GEN-CR0 | f6ecc700 |
| 2 | G1 | **A — Accept screen; advance 8 of 9** | Ravi / Model Validator | drop cb_person_cred_hist_length (IV 0.004); leak-band resolves (loan_percent_income genuine affordability vs loan_grade/int_rate circular, CR-avail); sufficiency met EPV 1185, Riley req 263 vs 32,581 | f6ecc700 | 5833db6d |
| 3 | G2 | **A — Accept attribution; all 8 confirmed** | Ravi / Model Validator | all 8 real players confirmed freq 1.00; shadow bar 0.00085; sampled 13,875 fits; weakest emp_length 17× bar; circular loan_grade #2 (87×) + loan_int_rate #4 (72×) confirmed | 5833db6d | b1e7d326 |
| 4 | G3 | **A — Ratify k=6 benchmark; origination-only as headline sensitivity** | Ravi / Model Validator | k=6 Gini 0.7597 rel loss −0.01% DeLong p 0.883; CR-orig 4-col origination-only Gini 0.609 held-out (−19%; OOF −22% committed) — largest circularity cost in corpus | b1e7d326 | 4ea50ec6 |
| 5 | G4 | **A — Approve 6-col benchmark** (dual) | Ravi / Risk Officer + Validator | test AUC 0.877 Gini 0.754; HL p=0.44 not rejected, ECE 0.011, 9/10 grades in CI (CCC over-predicts n=192); age fairness broadly clean (gaps<0.05 except 45–54 +0.060, n=139 noisy); carry CR-avail/CR-orig/CR-age | 4ea50ec6 | 1f151229 |
| 6 | G5 | **A — Standard config; origination-available mandatory fields** | Ravi / Model Owner | mandatory loan_percent_income+person_income (not grade/int_rate); refer; no adverse floor (origination-only 4-col missing-free); exact WOE reason codes; PD floor 0.03%; 6-case pack + cutoff note generated | 1f151229 | c0080bc2 |
| 7 | **GF** | **A — GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | integrity resolved at source; strong Gini 0.754 + calibration HL p=0.44 + age fairness clean; circularity handled via origination-only 4-col; MEDIUM reference benchmark, not production-IRB | c0080bc2 | d90a5ffa |

**Chain:** GEN-CR0 → f6ecc700 → 5833db6d → b1e7d326 → 4ea50ec6 → 1f151229 → c0080bc2 → **d90a5ffa**. ✅ **SEALED**

---

## G0 — Data & Scope Adequacy · ✅ DECIDED — **A** · entry_hash `f6ecc700`
**Signer:** Ravi (Data Steward) · 2026-10-18 · Materiality tier **MEDIUM**.
Integrity resolved **at source** in the cleaned file: the corrupt `target` column (73.9% agreement with the genuine
label; nonsensical by-grade default pattern — 0% defaults in grades A/B) was **deleted**, `loan_status` (monotonic
A 10%→G 98%; defaulters pay higher interest; sensible ownership gradient) was **adopted and renamed `target`**, and
5 blank junk columns dropped. Original preserved at `credit_risk_dataset.ORIGINAL_backup.csv`. **CR-label discharged.**
`person_age` excluded (ECOA; also impossible max 144 → CR-dq); `loan_grade`+`loan_int_rate` retained-and-flagged
(circular → CR-avail). **Eligible pool (9):** person_income, person_home_ownership, person_emp_length, loan_intent,
loan_grade, loan_amnt, loan_int_rate, loan_percent_income, cb_person_cred_hist_length.

## G1 — Univariate Screening & Data Sufficiency · ✅ DECIDED — **A** · entry_hash `5833db6d`
**Signer:** Ravi (Model Validator). Advance **8 of 9**; drop `cb_person_cred_hist_length` (IV 0.0044). Three features in
the >0.5 "leakage-check" band resolve cleanly: `loan_percent_income` 0.876 (genuine affordability), `loan_grade` 0.858
+ `loan_int_rate` 0.675 (circular, CR-avail). **Sufficiency (v3.1, reported):** EPV ≈ 1,185 (7,108/6); Riley minimum-N
= **263** vs **32,581** available → amply powered.

## G2 — Importance Attribution · ✅ DECIDED — **A** · entry_hash `b1e7d326`
**Signer:** Ravi (Model Validator). All **8 players confirmed** at frequency 1.00; shadow bar 0.00085; sampled estimator
(18 players > 15, P8), 13,875 fits, efficiency audit 5.6e-17. Clean separation — weakest (`person_emp_length`) 17× the
bar; circular `loan_grade` #2 (87×) and `loan_int_rate` #4 (72×) confirmed → the without-them sensitivity is the decisive
G3/G4 test.

## G3 — Parsimony Selection · ✅ DECIDED — **A** · entry_hash `4ea50ec6`
**Signer:** Ravi (Model Validator). Ratify pre-registered **k = 6**: `loan_percent_income, loan_grade, person_income,
loan_int_rate, person_home_ownership, loan_intent`; **Gini 0.7597**, rel. loss −0.01%, DeLong p 0.883. **CR-avail
sensitivity:** the 4-col origination-only model (drop the circular pair) scores **Gini 0.609 / AUC 0.804** (held-out)
vs 0.754 / 0.877 — ΔGini 0.145 (**−19% held-out**; −22% OOF in the committed run), the **largest circularity cost in the
corpus**. The origination-only model is HELOC-tier and **independent of the incumbent's verdict** → **CR-orig** (headline
deployable).

## G4 — Calibration (+ per-grade backtest) & Fairness · ✅ DECIDED — **A** (dual) · entry_hash `1f151229`
**Signers:** Ravi (Risk Officer + Validator). Held-out 80/20 (seed 42), test n=6,517.
**Discrimination:** AUC **0.877** / Gini **0.754**. **Calibration:** Hosmer–Lemeshow χ²=7.93, df=8, **p=0.44 → not
rejected**; **ECE 0.011**; **9 of 10 grades within Wilson CI** (full AAA→D; the miss is CCC, expected 14.9% vs realised
8.9%, n=192 — over-predicts, conservative). **Fairness (age excluded; predictive-parity PD-gap):** gaps vs 25–34 are
<0.05 except **45–54 at +0.060 (n=139)** — a small, noisy cell that over-predicts (pred 0.273 vs actual 0.252), so
predictive parity broadly holds. No material disparate impact → **CR-age** (monitor). Carry CR-avail + CR-orig + CR-age.

## G5 — Deployment Governance & Deliverables · ✅ DECIDED — **A** · entry_hash `c0080bc2`
**Signer:** Ravi (Model Owner). Mandatory = `loan_percent_income`, `person_income` (origination-available, **not**
grade/int_rate); `incomplete_policy='refer'`; **no adverse floor** (deployable 4-col missing-free); exact WOE reason
codes; PD floor 0.03% / cap 99.9%; drift + age-disparate-impact monitoring. **Deployable = CR-orig 4-col.**
**Deliverables:** `AEGIS_CREDITRISK_CUTOFF_POLICY.md`; `acceptance_cases/creditrisk.json` + `SAMPLE_RUNS_CREDITRISK.md`
(6 cases — PDs CR-R1 0.03%/AAA → CR-R2 20.4% → CR-R3 46.1% → CR-R4 99.9%/D; floor and cap both bind).

## GF — Final verdict · ✅ SEALED — **A (GO-WITH-CONDITIONS)** · entry_hash `d90a5ffa` · prev `c0080bc2`
**MAC Chair:** Ravi (CRO) · 2026-10-18. The CREDITRISK 6-column WOE-logistic model is **approved as a MEDIUM-tier
reference benchmark, not production-IRB**, ruled after the G4 backtest and G5 deliverables were complete and visible.
Data integrity is resolved at source; discrimination is 2nd-strongest in the corpus; calibration is excellent; age
fairness is broadly clean. The governing caveat is circularity — **deploy the origination-only 4-col model** (Gini 0.609,
independent). The cleaned-file re-run reproduces the committed SHARP analytics, confirming determinism.

### Open conditions register
| ID | Condition | Discharge before |
|---|---|---|
| CR-avail | `loan_grade`+`loan_int_rate` circular — benchmark not origination-valid | origination use |
| CR-orig | Deploy the 4-col origination-only model (Gini 0.609) | application-time use |
| CR-age | Age excluded; monitor age disparate impact (esp. 45–54 cell) | scoring real customers |
| CR-dq | Impossible values (age 144, emp_length 123) → upstream fix | production use |
| CR-use | Use test | real-decision use |

*(CR-label discharged at source: corrupt `target` deleted, genuine label adopted; original backed up.)*

**Run status: COMPLETE (G0 → GF sealed).** No parameter re-opened at any gate (P8); every figure traces to
`SHARP_CREDITRISK.md`, `g4_creditrisk`, and the cleaned dataset.
