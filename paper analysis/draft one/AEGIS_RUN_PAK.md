# AEGIS run log — PAK (PAKDD-2009 Brazilian retail credit)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/PAK.csv` — 50,000 rows, 51 features + target, event rate 0.2608 (13,041 events), 320,143 missing cells.
**Started:** 2026-10-13 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_PAK.md`
**Sixth governed run — the "messy real-world robustness" case: high-dimensional (51-col) screening + heavy missing
(320k cells) + the richest fairness surface so far (4 directly-prohibited ECOA bases + birthplace + proxies).**

> **Order (corrected standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the
> decisioning note and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-PAK0 |
| 1 | G0 | **A — Exclude prohibited + birthplace + high-card geo** (MEDIUM) | Ravi / Data Steward | compliance-first; exclude 4 prohibited bases + birthplace + redlining geo before modelling; retain softer proxies for G4 | GEN-PAK0 | 60f9b3aa |
| 2 | G1 | **A — Accept screen; advance 7 of 39** | Ravi / Model Validator | let Stage 2 arbitrate; 8 zero-variance dropped as predicted; carry PC-weak (max IV 0.066) + PC2 (geo proxies in candidate set) | 60f9b3aa | 8c7d877a |
| 3 | G2 | **A — Accept attribution; 5 players confirmed** | Ravi / Model Validator | all confirmed at freq 1.0, converged; PERSONAL_ASSETS_VALUE dropped (0.45× bar) despite top IV — Shapley over raw IV; 2 geo proxies confirmed (area-code #2) | 8c7d877a | c2ff8f70 |
| 4 | G3 | **A — Ratify 6-col benchmark; proxy-excluded variant as G4 sensitivity** | Ravi / Model Validator | ratify pre-registered k=5 (Gini 0.148) for comparability, 2 geo proxies flagged not-for-live; carry 4-col proxy-excluded (Gini 0.1175) as headline fairness replication | c2ff8f70 | 6e7fe46c |
| 5 | G4 | **A — Approve 6-col WoE-logistic** (dual) | Ravi / Risk Officer + Validator | backtest passes (HL p=0.382, 5/5 grades, ECE 0.0082); no material disparate impact (all PD gaps <0.05, predictive parity); AIR degenerate→documented; MC-proxy + PC-weak carried | 6e7fe46c | 95997309 |
| 6 | G5 | **A — Standard config + adverse floor on PROFESSIONAL_STATE** | Ravi / Model Owner | adverse floor closes missing-protective (0.91×) omission trap on 68.6%-missing field (GMSC precedent); mandatory PAYMENT_DAY+banking; refer; exact reason codes | 95997309 | 0fb81f52 |
| 7 | GF | **NO-GO** | Ravi / MAC Chair (CRO) | fails use-test: cannot discriminate (Gini 0.148, no approvable applicant) + leans on redlining proxies; calibration/fairness sound but insufficient; first NO-GO of six runs | 0fb81f52 | **17814d7b** |

**Chain:** GEN-PAK0 → 60f9b3aa → 8c7d877a → c2ff8f70 → 6e7fe46c → 95997309 → 0fb81f52 → 17814d7b.

---

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **NO-GO** (ruled with full visibility)

**MAC Chair:** Ravi (CRO) · **2026-10-13** · entry_hash `17814d7b`
**Verdict:** the PAK 6-column WOE-logistic model is **REJECTED (NO-GO)** — for any use, including as a decisioning
benchmark. Ruled **after** the per-grade backtest (G4), the decisioning note and the `SAMPLE_RUNS_PAK.md` pack
were complete and visible (corrected order). **First NO-GO of the six governed runs.**

**Basis for rejection (what GF saw):**
- **Fails the use-test / discrimination floor.** Gini **0.148**, AUC **0.584** — the weakest of all runs. The
  backtest piles 8,665/10,000 into a single grade; the acceptance pack shows **all four representative real
  applicants (incl. a non-defaulter) compressing into CC–C with no approvable / investment-grade output**. A
  model that cannot separate a good applicant from a bad one must not be approved, even as a decisioning
  benchmark.
- **Proxy dependence.** The two features carrying most of the little signal there is
  (`RESIDENCIAL_PHONE_AREA_CODE` #2, `PROFESSIONAL_STATE` #4) are **geographic redlining proxies**; the
  fairness-constrained replication that removes them (Gini 0.1175) is weaker still.
- **Calibration and measured fairness are sound** (HL p=0.382; all PD gaps <0.05, predictive parity) — **but
  soundness on those axes does not rescue a model that cannot discriminate and relies on prohibited-proxy
  geography.** AIR was degenerate (near-zero approve-grade population).

**The result is the finding.** The run is preserved in full as the evidence base: SHARP correctly refused to
manufacture signal that is not in the (post-exclusion) data, and AEGIS correctly **rejected** rather than
rubber-stamped. This is the governance framework demonstrating a negative verdict — the counterpoint to the five
prior GO-WITH-CONDITIONS runs.

### Rejection basis / what reconsideration would require

| ID | Finding → why it blocks approval | What a resubmission would need |
|---|---|---|
| GF-disc | Cannot discriminate (Gini 0.148; no approvable applicant) | materially stronger lawful signal (new eligible features / richer data) |
| GF-proxy | Signal depends on geographic redlining proxies | a proxy-excluded model that still meets a discrimination floor |
| GF-race | Possible race/ethnicity proxying is untestable (attribute absent) | data permitting the untested fairness axes to be checked |
| GF-scope | No time axis; not-production-IRB | a dated performance window for IRB framing |

### Run outcome
- **Verdict:** NO-GO (rejected for all use). No production model promoted.
- **Provenance:** 7 logged decisions, hash chain intact (GEN-PAK0 → 17814d7b).
- **Contribution:** the framework's first negative verdict — a weak-signal, proxy-dependent real-world dataset
  correctly rejected with full documentation.

## Deliverables checklist (end-to-end standard — corrected order)
- [x] `SHARP_PAK.md` — Stages 0–4 + Stage 4b backtest + fairness
- [x] **Per-grade calibration backtest (in G4, before GF)** — HL p=0.382, 5/5 populated grades pass
- [x] `AEGIS_PAK_CUTOFF_POLICY.md` — decisioning note (grades; institution threshold; no pricing; weak-signal + proxy caveats)
- [x] Acceptance demonstration — `acceptance_cases/pak.json` + `SAMPLE_RUNS_PAK.md` (6-case standard: 4 real w/ actual outcome + 2 synthetic; repayer & defaulter share PD 34.04%)
- [x] `AEGIS_RUN_PAK.md` — G0–G5 signed, **GF ruled last** with visibility — **NO-GO**, chain intact
- [x] Rejection basis listed, each with its reconsideration requirement

*AEGIS run complete (PAK) — sixth governed run; the first NO-GO. Weak-signal + redlining-proxy dependence on a
high-dimensional, heavy-missing real-world dataset, correctly rejected.*

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Owner) · **2026-10-13** · entry_hash `0fb81f52`
**Heavy-missing governance (PC3) resolved.** Of the 6 selected features, three carry missingness:
`RESIDENCIAL_PHONE_AREA_CODE` 16.4% (**adverse**, missing→32.1% vs 24.9%, 1.29× — learned `__missing__` bin kept,
no omission incentive), `OCCUPATION_TYPE` 14.6% (neutral), and **`PROFESSIONAL_STATE` 68.6%** (**protective**,
missing→25.3% vs 27.8%, 0.91× — an **omission trap**). **Adverse floor applied to `PROFESSIONAL_STATE`** (blank
scored at worst-observed WoE), closing the trap — consistent with GMSC's income floor. Mandatory =
`PAYMENT_DAY, QUANT_BANKING_ACCOUNTS, QUANT_SPECIAL_BANKING_ACCOUNTS` (structural, ~always present);
`incomplete_policy='refer'`; exact WoE reason codes; PD floor 0.03% automatic; `drift_monitor` (PSI/AUC) +
MC-proxy + PC-weak watch. Making `PROFESSIONAL_STATE` mandatory would reject 68.6% of applicants → rejected B;
C leaves the trap open; D (drop it) diverges from the ratified benchmark (sensitivity already covers it).
**G5 deliverables (decisioning note + acceptance pack) produced below — before GF.**

### Acceptance demonstration (committee pack: `SAMPLE_RUNS_PAK.md`, inputs `acceptance_cases/pak.json`)
**Fixed 6-case standard:** 4 real applicants (actual outcome shown) + 2 synthetic composites (PD-floor + stress).
**The predicted-vs-actual view is damning (and honest):** a repayer (R2) and a defaulter (R3) get the **identical
34.04% PD**, every real applicant lands in CC–C, and even `SYN-best` (all best-observed values) cannot clear grade
CC — the model produces **no approvable applicant even synthetically**. The empirical face of Gini 0.148, reinforcing the NO-GO.

| Candidate | Type | Actual | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|---|--:|---|---|---|
| R1-low-repaid | real | repaid | 23.99% | CC | SCORE | OCCUPATION_TYPE, PAYMENT_DAY, banking-accounts |
| R2-mid-repaid | real | repaid | 34.04% | CC | SCORE_FLAGGED | PAYMENT_DAY, banking-accounts |
| R3-mid-default | real | defaulted | 34.04% | CC | SCORE_FLAGGED | PAYMENT_DAY, banking-accounts |
| R4-high-default | real | defaulted | 45.78% | C | SCORE | RESIDENCIAL_PHONE_AREA_CODE, PAYMENT_DAY, PROFESSIONAL_STATE |
| SYN-best | synthetic | — | 20.22% | CC | SCORE | PAYMENT_DAY, RESIDENCIAL_PHONE_AREA_CODE |
| SYN-worst | synthetic | — | 65.40% | D | SCORE | banking-accounts, PAYMENT_DAY |

*(Accept/refer/decline threshold is an institution input, not derived here — no pricing. R2 repaid and R3
defaulted share an identical PD (34.04%): the model cannot separate the two outcomes; the lowest-risk real
applicant still scores CC. Full showcase: `SAMPLE_RUNS_PAK.md`; decisioning note: `AEGIS_PAK_CUTOFF_POLICY.md`.)*

**Scorer notes:** `score_acceptance_cases.py` was extended (a) to coerce JSON `null`→`NaN` by training-column
dtype so a missing *numeric* input routes into the learned `__missing__` bin / adverse floor, and (b) to render
the fixed 6-case standard — `Type` (real/synthetic) + `Actual outcome` columns via an optional `case_meta` block
(a pack with no `case_meta` still generates — PDs unchanged; the new columns show real/unknown).

---

## G4 — Calibration (+ required backtest) & Fairness  ·  status: ✅ DECIDED (Option A, dual)
**Signers:** Ravi (Risk Officer + Validator) · **2026-10-13** · entry_hash `95997309`
**Calibration (per-grade backtest, inside G4):** 80/20 held-out (seed 42), test n=10,000. **5/5 populated
grades within CI, ECE 0.0082, Hosmer-Lemeshow χ²=8.54 df=8 p=0.382 → not rejected** (table in `SHARP_PAK.md`
§Stage 4b). The model is **well-calibrated but barely discriminating** — 8,665/10,000 land in a single grade
(CC, ~base rate); honest PDs, minimal tier separation. *Calibration ≠ discrimination* — PAK is the clean
example. **Fairness (disparate impact across the 4 excluded prohibited attrs):** every mean-PD gap is **under
0.05** and tracks the real default-rate gap (predictive parity; e.g. 65+ PD −0.049 because they default less,
19.9% vs 27.3%). No disparate treatment (attrs not inputs), no material disparate impact. **AIR (four-fifths)
is degenerate** — with 26% base rate + near-flat scores, ≈0.01% reach an approve grade, so approval rates ≈0
and the ratio is 0/0 noise → **reported as uninformative; relied on the cutoff-free mean-PD gap + predictive
parity instead** (no invented approval cutoff). **PC-fair headline:** 6-col vs 4-col proxy-excluded fairness is
**virtually identical** (SEX gap −0.003/−0.003; AGE 65+ −0.049/−0.054) — the geo proxies do not measurably
drive disparate impact on these axes; they stay flagged because they could proxy **race/ethnicity, which is
absent from the data and untestable**. **Conditions:** **MC-proxy** (geo proxies not-for-live) and **PC-weak**
(weak discrimination AUC 0.584 → GF). Rejected B (switch to proxy-excluded primary — sensitivity captures it),
C (NO-GO — GF rules weakness with demo), D (recalibrate unnecessary — calibration passes).

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Validator) · **2026-10-13** · entry_hash `6e7fe46c`
**Decision:** ratify the pre-registered **k = 5 → 6-column** selection as the MEDIUM-tier **benchmark**
(`PAYMENT_DAY, RESIDENCIAL_PHONE_AREA_CODE [proxy], OCCUPATION_TYPE, PROFESSIONAL_STATE [proxy],
QUANT_BANKING_ACCOUNTS, QUANT_SPECIAL_BANKING_ACCOUNTS`), Gini **0.148**, rel. loss 0.00%, DeLong p 1.0. The two
geographic proxies are **retained-but-flagged** ("not suitable for a live credit decision" — standing §Regulatory
eligibility disclosure), preserving comparability with published PAKDD-2009 results.
**Grounded proxy sensitivity (faithful 5-fold OOF, seed 42, same WoE-logistic):** the 4-col proxy-excluded model
scores Gini **0.1175** / AUC 0.559 vs 0.148 / 0.574 — ΔGini 0.030 (**−20.6% relative**), DeLong **p = 6.3e-13**
(statistically real but practically near-random either way; proxy-excluded is better calibrated, ECE 0.0037).
**Condition PC-fair:** the proxy-excluded 4-col model is carried as the **mandatory headline fairness-constrained
replication** (methodology already commits to it), reported at G4. Rejected B (adopt proxy-excluded as primary —
defensible, but forgoes benchmark comparability; sensitivity captures it either way), C (NO-GO — GF rules this
with full visibility).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `c2ff8f70`
**Decision:** accept. **6 real players → 5 confirmed** at confirmation frequency 1.00; shadow bar 0.00117;
sampled estimator (16 players > 15, P8), converged (200 perms, 11,740 fits, max MC SE 0.00075; efficiency audit
1.4e-17). Confirmed: `PAYMENT_DAY` (23.5×), `RESIDENCIAL_PHONE_AREA_CODE` (16.6×, **proxy**), `OCCUPATION_TYPE`
(13.2×), `PROFESSIONAL_STATE` (4.8×, **proxy**), `grp[QUANT_BANKING+QUANT_SPECIAL_BANKING]` (1.5×).
**`PERSONAL_ASSETS_VALUE` dropped** (Shapley 0.00053 = 0.45× bar, freq 0.00) **despite the highest univariate
IV (0.066)** — its marginal contribution is below the noise floor once the other features are present. This is
the canonical demonstration of why SHARP uses Shapley attribution over raw IV. **PC2 sharpened:** two geo
proxies confirmed and the area-code proxy is the #2 strongest signal in the model. Rejected B (no instability —
all confirmed at freq 1.00, tiny MC SE).

---

## G1 — Univariate Screening  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `8c7d877a`
**Decision:** advance the **7 candidates** that pass Stage 1 (`PERSONAL_ASSETS_VALUE, PAYMENT_DAY,
RESIDENCIAL_PHONE_AREA_CODE, OCCUPATION_TYPE, PROFESSIONAL_STATE, QUANT_BANKING_ACCOUNTS,
QUANT_SPECIAL_BANKING_ACCOUNTS`). The **8 zero-variance/constant columns auto-dropped** (IV 0.0000 — as
flagged at G0); 16 columns required escalation. **Signal is weak across the whole pool:** max IV = 0.066
(`PERSONAL_ASSETS_VALUE`), nothing reaches "medium" (Siddiqi); all Cramér's V ≤ 0.08. 3 sub-0.02-IV columns
rescued by escalation (`PROFESSIONAL_STATE` nominal model-check; the two banking-account columns Mann-Whitney
p=0.0086). **Conditions:** **PC-weak** (weak whole-pool signal → carry to GF) and **PC2** (geographic proxies
`RESIDENCIAL_PHONE_AREA_CODE` + `PROFESSIONAL_STATE` in the candidate set → G3/G4 fairness test). Rejected
B (tightening pre-empts Stage 2, violates P8 fixed method), C (premature NO-GO — surface the honest result for GF).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Data Steward) · **2026-10-13** · entry_hash `60f9b3aa`

**Materiality tier:** MEDIUM (reference benchmark, not production-IRB — consistent with the five prior runs).

**Machine recommendation — Option A:** exclude the **directly ECOA/Reg B-prohibited** attributes and the
**birthplace (national-origin) proxies** from the candidate pool *before* modelling; retain the softer proxies
(`QUANT_DEPENDANTS`, `EDUCATION_LEVEL_2`, residential geography) with disparate-impact testing deferred to G4;
then re-run SHARP on the eligible pool.

**Exclude before modelling (prohibited + birthplace proxy):**
`SEX`, `AGE`, `MARITAL_STATUS`, `NACIONALITY`, `STATE_OF_BIRTH`, `CITY_OF_BIRTH`.

**Also excluded (redlining proxy + unmodellable free-text geography/IDs):**
`RESIDENCIAL_CITY`, `RESIDENCIAL_BOROUGH`, `PROFESSIONAL_CITY`, `PROFESSIONAL_BOROUGH`,
`RESIDENCIAL_ZIP_3`, `PROFESSIONAL_ZIP_3` (up to 14,510 levels each).

**Left to SHARP G1 (technical screening):** 8 zero-variance/constant columns auto-dropped.

**Conditions (carried):**
- **PC1** — no time axis → not-production-IRB (R1 / CRE36.79).
- **PC2** — `QUANT_DEPENDANTS`, `EDUCATION_LEVEL_2`, `RESIDENCIAL_STATE` retained as proxies → G4 disparate-impact test.
- **PC3** (→ G5) — heavy-missing governance: `PROFESSIONAL_*` ~68–73%, `EDUCATION_LEVEL_2` 65%, `MATE_PROFESSION_CODE` 58%, `APPLICATION_SUBMISSION_TYPE` 39%.
- **PC-dq** — data-integrity note: `AGE` min = 6 (impossible for an applicant); AGE is excluded anyway, logged for provenance.

*(Options presented in chat; signed row appended on decision.)*
