# AEGIS run log — HMEQ (Home Equity)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Analytical engine:** SHARP run `sharp_20261011_hmeq`
(`sharp_runs/sharp_20261011_hmeq.json`, sha256[:16] `1c5d20e73932b048`) · **Record:** `SHARP_HMEQ.md`
**Started:** 2026-10-12 · **Machine:** AEGIS engine (Claude) · **Human signer:** Ravi (role varies per gate RACI)
**Materiality tier:** *set at G0*

> Interactive governed walkthrough. Each gate: machine recommendation + evidence pack + closed option set
> → human selects one option with rationale → recorded below with a running hash chain. Every figure traces
> to the SHARP run above (no extrapolation).

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GENESIS0 |
| 1 | G0 | **B — Proceed with conditions** (tier MEDIUM) | Ravi / Data Steward | build as a benchmark but carry the window-gap and missingness conditions openly | GENESIS0 | a54b25b6 |
| 2 | G1 | **A — Accept screen, 11 features** | Ravi / Model Validator | accepted evidence-driven screen: REASON unpredictive (IV 0.009); rescued U-shaped LOAN/CLNO cleared reliability gate *(signer-accepted; rationale populated from evidence)* | a54b25b6 | 20b1307e |
| 3 | G2 | **A — Accept attribution** | Ravi / Model Validator | accept option A, clean 12.8x separation from noise | 20b1307e | f0e33b4a |
| 4 | G3 | **A — Full 11-column set** | Ravi / Model Validator | Option A, pre-registration governs, don't overstate parsimony | f0e33b4a | 2c17ebe1 |
| 5 | G4 | **A — Approve WOE-logistic + C3** | Ravi / Risk Officer + Validator (dual) | approved: ECE 0.020 well-calibrated, exact auditable reason codes; fairness deferred to deploy-time condition C3 *(signer-accepted; rationale from evidence)* | 2c17ebe1 | 5fbe6862 |
| 6 | G5 | **A — Targeted missing-value config** | Ravi / Model Owner | targeted flooring on self-reported YOJ/JOB; keep bureau learned WOE; exact reason codes; C2/C3 discharged *(signer-accepted; rationale from evidence)* | 5fbe6862 | 6228ef0c |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | approved as MEDIUM-tier benchmark; 5 conditions accepted; not production-IRB until dated ≥5yr data | 6228ef0c | **3b896863** |

**Chain verified:** GENESIS0 → a54b25b6 → 20b1307e → f0e33b4a → 2c17ebe1 → 5fbe6862 → 6228ef0c → 3b896863. Each entry_hash = sha256(prev_hash + gate|option|signer|rationale); altering any past row breaks every hash after it.

---

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS**

**MAC Chair:** Ravi (CRO) · **2026-10-12** · entry_hash `3b896863`
**Verdict:** the HMEQ WOE-logistic model is **approved for use as a MEDIUM-tier reference/benchmark PD model**, **not** as a production IRB model. §8 checklist: 9 SATISFIED · 4 PARTIAL · 1 GAP-converted-to-condition · 0 hard GAP on a must-have for the declared purpose.

### Open conditions register (must be discharged per their escalation point)

| ID | Condition | Regulatory tie | Discharge before |
|---|---|---|---|
| C1 | Carry "not production-IRB" label; a production build needs a dated ≥5yr dataset | R1 / CRE36.79 | any production-IRB claim |
| CP2 | Evidence the use test (model drives real credit decisions) | R2 / CRE36.60 | any real-decision use |
| ~~CP4~~ | ~~Produce per-grade realised-vs-expected calibration backtest~~ **DISCHARGED 2026-10-13** | R4 / CRE36.122–123 | ✅ done — see below |
| CP6 | Quantify the Margin of Conservatism for Category-A missingness | R6 / EBA GL 2017/16 | production use |
| C3 | Enable deploy-time fairness-gap monitoring (threshold 0.05) | R12 / EU AI Act Art 14 | scoring real applicants |

### Run outcome
- **Production model:** WOE-logistic, isotonic-calibrated, 11 features; Gini 0.80 / ECE 0.020.
- **Decision provenance:** 7 gate decisions, hash-chained, each signed by the role the RACI assigns.
- **Status:** APPROVED (conditional). Re-validation cadence: semi-annual (MEDIUM tier).

*AEGIS run complete.*

---

## Condition CP4 — DISCHARGED (2026-10-13)

Per-grade realised-vs-expected PD calibration backtest run on a held-out 80/20 split (n=1,192, AUC 0.9000).
**Result: calibration holds** — overall ECE 0.0239, Hosmer-Lemeshow p=0.069 (not rejected at 5%), 7/9 rating
grades with expected PD inside the realised 95% CI (8/10 deciles). Two monitorable deviations: grade A mild
under-prediction (thin low-risk cell) and grade D conservative over-prediction (safe direction). Full table
in `SHARP_HMEQ.md` §"Stage 4b". **R4 moves PARTIAL → SATISFIED.** Re-run at each retrain (the calibration-
validation step the fixed grade/cutoff policy depends on — `AEGIS_HMEQ_CUTOFF_POLICY.md`).

**Open conditions now:** C1 (label — met), **CP2** (use-test — deferred to deployment), **CP6** (MoC
quantification — open), **C3** (fairness monitoring — deferred to deployment). CP4 closed.

---

## Amendment (2026-10-13) — condition C-PDfloor added (PD floor & ceiling)

**Chain:** … → 3b896863 (GF) → **1fd2baf9** (this amendment). Post-approval change-control, added alongside
the German run's GC5: isotonic calibration on small data can emit a degenerate ~0% PD in the safest bin,
which is unreal and non-compliant for IRB.

**C-PDfloor — PD floor & ceiling (→ deployment):**
- **Floor PD at 0.03%** — Basel **CRE32.3** (verified at BIS): PD = greater of internal estimate or 0.03%
  (corporate/bank; retail generally mirrors — *confirm retail-specific before paper*).
- **Defaulted → PD 100%**; prudential cap (e.g., 99.9%) on non-defaulted for symmetry.
- Implementation: `reported_PD = min(max(calibrated_PD, 0.0003), 0.999)` at scoring time (policy overlay).
- Signer: Ravi (Risk Officer) · entry_hash `1fd2baf9`.
- **GRADUATED TO METHODOLOGY (2026-10-13):** now a standard always-on step (`METHODOLOGY.md §7.8` item 4),
  implemented in `missing_governance.Scorer`. Satisfied by methodology, not a per-run task.

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Model Owner) · **2026-10-12** · entry_hash `6228ef0c`
**Decision — scoring-time controls:**
- Adverse flooring on self-reported influenceable fields **YOJ, JOB** (omission can't lower risk).
- Keep learned `__missing__` WOE for bureau-pulled fields **DEROG, DELINQ, NINQ** (un-withholdable; flooring would over-penalise).
- Exact additive WOE reason codes (no approximation) — **R14/ECOA discharged**.
- `incomplete_policy = 'refer'` for a missing essential field.
- **C2 discharged** (missingness governed, no imputation). **C3 discharged** (deploy-time fairness-gap monitoring enabled, threshold 0.05).
- *Carried watch:* if a bureau field becomes self-reported upstream, the omission trap reopens — data-contract flag.

Rejected B (rejects 21% on blank DEBTINC; over-declines honest thin files), C (leaves YOJ/JOB exploitable), D (unnecessary deferral).

---

## G4 — Calibration & Fairness  ·  status: ✅ DECIDED (Option A, dual sign-off)

**Signers:** Ravi (Risk Officer + Independent Model Validator) · **2026-10-12** · entry_hash `5fbe6862`
**Decision:** approve **WOE-logistic** (isotonic-calibrated, ECE 0.0204, Gini 0.8010) as the production model; XGBoost (Gini 0.88) retained as challenger/benchmark. Chosen for exact additive reason codes (regulatory transparency) over XGBoost's +0.08 Gini. **Condition C3 added (→ G5/deployment):** HMEQ has no in-dataset protected attribute, so fairness-gap monitoring (`drift_monitor`, threshold 0.05) must run against protected characteristics at deployment. Rejected B (black-box transparency cost), C (aggregate ECE already strong), D (over-conservative).

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-12** · entry_hash `2c17ebe1`
**Decision:** adopt the **full 11-column set** `[DEBTINC, DELINQ, VALUE, DEROG, CLAGE, NINQ, LOAN, JOB, YOJ, CLNO, MORTDUE]` per the pre-registered AND rule (DeLong p≥0.05 **and** rel. Gini loss ≤5%). Only k=10 passes both; every proper subset is DeLong-rejected at n≈6k, so no parsimony reduction is claimed. Gini 0.8133. Rejected B/C (would overstate parsimony on the ≤5% criterion alone, against DeLong evidence), D (no escalation needed — pre-registration already resolves it).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-12** · entry_hash `f0e33b4a`
**Decision:** accept the Stage-2 attribution. All 10 players (MORTDUE+VALUE grouped) confirmed above the shadow-null bar 0.000930, weakest (CLNO) at 12.8×. The lone breaching shadow (`__shadow__7_LOAN`) correctly rejected (expected 1-in-20 at a 0.95 bar; F3). Proceed to selection on the sampled attribution. Rejected B (exact re-run — unnecessary given the margin), C/D (over-conservative).

---

## G1 — Screening  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-12** · entry_hash `20b1307e`
**Decision:** advance **11 features** — `[DEBTINC, DELINQ, VALUE, DEROG, CLAGE, NINQ, LOAN, JOB, YOJ, CLNO, MORTDUE]`; **drop REASON** (IV 0.009). LOAN and CLNO retained via shape-check rescue (confirmed U-shaped signal, F2). Rejected B (pre-empts Stage 2), C (discards validated U-shape signal), D (carries noise column REASON).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option B)

**Materiality tier:** MEDIUM · **Signer:** Ravi (Data Steward) · **2026-10-12** · entry_hash `a54b25b6`

**Decision:** Proceed to build HMEQ as a reference/benchmark PD model, with two conditions carried forward:
- **C1 (→ GF):** document the observation-window gap vs Basel CRE36.79 — HMEQ has no default-date/time axis, so a ≥5-year PD observation window cannot be evidenced. Model is labelled *not production-IRB* until a dated dataset is used.
- **C2 (→ G5):** govern DEBTINC and the other informative-missing columns explicitly — preserve the WOE `__missing__` bin (no imputation), and decide per-column adverse flooring at G5. (EBA MoC Category A item.)

Rejected: A (would overstate regulatory posture), C (over-conservative; blocks a legitimate benchmark use), D (discards 21% of rows and destroys the strongest signal).

---

## Acceptance demonstration (required — use-test R2 / transparency EU AI Act Art 13 / ECOA)

Approved WOE-logistic model + `AEGIS_HMEQ_CUTOFF_POLICY.md`. Portfolio default rate 19.95%. PD floored at
0.03% (Basel CRE32.3). Reason codes = exact WOE decomposition. **Fixed 6-case standard:** 4 real applicants
(actual outcome shown) + 2 synthetic composites (PD-floor + stress). Strong model — wide tail separation
(R1 0.9% → R4 90.8%); SYN-best floors at 0.03% AAA.

| Candidate | Outcome | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|--:|---|---|---|
| R1-low-repaid | repaid | 0.89% | AA | SCORE | JOB, LOAN, MORTDUE |
| R2-mid-repaid | repaid | 9.31% | B | SCORE | LOAN, DEBTINC, MORTDUE |
| R3-mid-default | defaulted | 9.31% | B | SCORE_FLAGGED | VALUE, LOAN, CLNO |
| R4-high-default | defaulted | 90.76% | D | SCORE | DEBTINC, DELINQ, VALUE |
| SYN-best | repaid (by design) | 0.03% | AAA | SCORE | all protective (PD floor hit) |
| SYN-worst | default (by design) | 99.90% | D | SCORE | DELINQ, DEROG, CLNO |

*(Accept/refer/decline threshold is an institution risk-appetite input, not derived here — no pricing. Honest
messy-middle: R2 repaid and R3 defaulted share PD 9.31%. Full showcase: `SAMPLE_RUNS_HMEQ.md`.)*

Spans approve / refer / decline with defensible, hand-auditable reasons. Demonstrates the model+policy
produce governed, explainable decisions — not just a PD. **Acceptance: PASS.**
