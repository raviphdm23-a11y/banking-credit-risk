# AEGIS run log — German Credit

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Analytical engine:** SHARP v3 run 2026-10-13
(report in `SHARP_GERMAN.md`, generated live via `v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/german_credit_record.csv` — 1,000 rows, 20 features, event rate 0.30, 0 missing.
**Started:** 2026-10-13 · **Machine:** AEGIS engine (Claude) · **Human signer:** Ravi (role varies per gate RACI)
**Materiality tier:** *set at G0*

> Interactive governed walkthrough. Each gate: machine recommendation + evidence pack + closed option set
> → human selects one option with rationale → recorded with a running hash chain. Every figure traces to
> the SHARP run (no extrapolation). The headline contrast vs HMEQ: **fairness** — this dataset carries
> prohibited (ECOA/Reg B) and proxy attributes, so G0 and G4 involve real fairness decisions.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-GER0 |
| 1 | G0 | **A — Exclude prohibited attrs** (tier MEDIUM) | Ravi / Data Steward | exclude prohibited attributes before modelling, compliance-first | GEN-GER0 | d3e30cf3 |
| 2 | G1 | **A — Accept screen, 12 candidates** | Ravi / Model Validator | keep housing for G4 disparate-impact testing | d3e30cf3 | 491a1048 |
| 3 | G2 | ~~B — Re-run EXACT Shapley~~ **VOIDED** (methodology deviation) | Ravi / Model Validator | exact Shapley given tight margins | 491a1048 | 79b23079 |
| 4 | G2-CORR | **Accept SAMPLED attribution** (per §5.5) | Ravi / Validator + Machine | exact deviated from pre-registered rule: 22 players>15 ⇒ sampled is the fixed method; reverted | 79b23079 | 93fae307 |
| 5 | G3 | **A — Ratify 5-column selection** | Ravi / Model Validator | Option A, ratify the pre-registered 5-column selection | 93fae307 | d78faf68 |
| 6 | G4 | **A — Approve WOE-logistic + GC3** | Ravi / Risk Officer + Validator (dual) | no disparate treatment, impact tracks real risk | d78faf68 | 9abf47c3 |
| 7 | G5 | **A — Standard config** | Ravi / Model Owner | standard config with mandatory core fields | 9abf47c3 | 72c3b146 |
| 8 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | strong fair-lending posture; conditions GC1/GC3/GC4/GC-use; not production-IRB | 72c3b146 | **00d5d25e** |

**Chain:** GEN-GER0 → d3e30cf3 → 491a1048 → 79b23079 → 93fae307 (G2 correction) → d78faf68 → 9abf47c3 → 72c3b146 → 00d5d25e. The voided G2 entry (`79b23079`) is retained in-chain; its correction supersedes it — tamper-evidence preserved.

---

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS**

**MAC Chair:** Ravi (CRO) · **2026-10-13** · entry_hash `00d5d25e`
**Verdict:** the German Credit WOE-logistic 5-column model is **approved as a MEDIUM-tier reference/benchmark**, **not** production-IRB. §8: 9 SATISFIED (2 emphatically) · 2 PARTIAL · 1 GAP→condition · 0 hard GAP for the declared purpose. **Fair-lending posture is the strength:** no disparate treatment (prohibited attrs excluded at G0), disparate impact passes the 4/5ths rule on all three protected attributes and tracks actual default rates.

### Open conditions register

| ID | Condition | Tie | Discharge before |
|---|---|---|---|
| GC1 | Not-production-IRB label; needs dated ≥5yr data | R1/CRE36.79 | production-IRB claim |
| GC3 | Deploy-time fairness monitoring (age PD gap; thin foreign cell) | R12/EU AI Act; ECOA | scoring real applicants |
| ~~GC4~~ | ~~Per-grade calibration backtest~~ **DISCHARGED 2026-10-13** | R4/CRE36.122–123; R6 | ✅ done — see below |
| GC-use | Use-test (real-decision use) | R2/CRE36.60 | real-decision use |

### Run outcome
- **Production model:** WOE-logistic, 5 features `[checking_status, credit_history, months_duration, savings_status, purpose]`, Gini 0.53.
- **Provenance:** 8 logged decisions incl. one recorded **methodology-deviation correction** (G2) — the governance chain catching the model's own error.
- **Status:** APPROVED (conditional). Semi-annual re-validation (MEDIUM tier).

*AEGIS run complete (German Credit).*

---

## Condition GC4 — DISCHARGED (2026-10-13)

Per-grade calibration backtest on a held-out 80/20 split (n=200, AUC 0.7814). **Calibration holds** —
overall ECE 0.0334, Hosmer-Lemeshow p=0.212 (not rejected; stronger than HMEQ's 0.069), 7/8 occupied grades
with expected PD inside the realised 95% CI. One REVIEW (grade BB, mild under-prediction, thin 34-row cell).
**R4 → SATISFIED.** The wide per-grade CIs (small sample: 2–53 per cell) quantify estimation uncertainty and
inform the R6 small-sample Margin of Conservatism. Full table in `SHARP_GERMAN.md` §"Stage 4b". Re-run on
larger/fresh data at deployment.

**Open conditions now:** GC1 (label — met), **GC3** (fairness monitoring — deferred to deployment),
**GC-use** (use-test — deferred to deployment), R6 MoC (informed, quantification optional). GC4 closed.

---

## Amendment (2026-10-13) — condition GC5 added (PD floor & ceiling)

**Chain:** … → 00d5d25e (GF) → **01524fec** (this amendment). Post-approval change-control: a scoring-time
control identified when a sample applicant (G-strong) scored a **calibrated PD of exactly 0.0%** — an
isotonic-calibration artifact on small data (the safest OOF bin had zero defaults; cf. the AAA grade's GC4
CI of [0%, 65.8%]). A literal 0% PD is unreal and, for IRB, non-compliant.

**GC5 — PD floor & ceiling (→ deployment):**
- **Floor PD at 0.03%** — Basel **CRE32.3** (verified at BIS): PD = greater of the internal estimate or
  **0.03%** (corporate/bank; retail generally mirrors it — *confirm retail-specific before paper*).
- **Defaulted borrowers → PD = 100%** (CRE32.3); apply a prudential cap (e.g., 99.9%) to non-defaulted
  scores for symmetry.
- Implementation: `reported_PD = min(max(calibrated_PD, 0.0003), 0.999)` at scoring time — a documented
  policy overlay, not a model change. Ties to R6 (small-sample MoC) and R4.
- Signer: Ravi (Risk Officer) · entry_hash `01524fec`.
- **GRADUATED TO METHODOLOGY (2026-10-13):** now a standard always-on step in SHARP deployment
  (`METHODOLOGY.md §7.8` item 4), implemented in `missing_governance.Scorer` (default `pd_floor=0.0003`,
  `pd_cap=0.999`). GC5 is therefore **satisfied by methodology**, not a per-run task. Re-scored G-strong:
  reported PD 0.0% → **0.03%** (grade AAA).

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Model Owner) · **2026-10-13** · entry_hash `72c3b146`
**Decision:** mandatory = `checking_status, credit_history, months_duration` with `incomplete_policy='refer'`; exact WOE reason codes (R14); enable `drift_monitor` with GC3 fairness checks + PSI/AUC drift. No adverse-floor overlay needed (0 training missing). Rejected B (all-5 mandatory — over-refers), C (no gate — un-governed blanks), D.

---

## G4 — Calibration & Fairness  ·  status: ✅ DECIDED (Option A, dual sign-off)

**Signers:** Ravi (Risk Officer + Independent Model Validator) · **2026-10-13** · entry_hash `9abf47c3`
**Decision:** approve WOE-logistic (Gini 0.53; selected 5-col model). **Fairness finding (computed, in-sample, n=1,000):** no disparate *treatment* (zero protected/proxy inputs); disparate *impact* passes the 4/5ths rule on all three protected attributes — AIR sex 0.953, age 0.845, foreign 0.829 — and **tracks actual default rates** (predictive parity; model under-differentiates real risk rather than inventing bias). **Condition GC3 added (→ deployment):** monitor the age mean-PD gap (0.056, marginally over the 0.05 `drift_monitor` threshold, risk-justified) and the thin `foreign_worker` domestic cell (n=37, noisy). **GC2 (proxy) effectively resolved** — `housing` not in the selected model. Calibration is noisy (small data) → add **GC4** per-grade backtest like HMEQ's CP4. Rejected B (remediation disproportionate), C (XGBoost — marginal gain, loses transparency, re-test fairness), D (NO-GO over-conservative; breach is marginal and risk-justified).

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `d78faf68`
**Decision:** ratify the pre-registered selection — **5 columns** `[checking_status, credit_history, months_duration, savings_status, purpose]`, Gini 0.5317, rel. loss 4.10%, DeLong p=0.0613 (smallest k passing both fixed criteria). A genuine parsimony reduction (10→5), contrast HMEQ. **Fairness note:** selected set uses **zero proxy/prohibited inputs** (`housing` enters only at k=8, not selected). Rejected B (no business case to deviate from the method), C (Gini 0.53 acceptable for a reference benchmark).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Accept sampled — corrected)

**⚠ Correction (2026-10-13).** The first G2 decision (Option B, "re-run exact Shapley") was a **deviation
from the pre-registered methodology** and is **VOIDED**. METHODOLOGY §5.5 fixes the estimator by player
count: **exact only when players incl. shadows ≤ 15, else sampled** — German's eligible pool is 22 players
(12 real + 10 shadow) > 15, so **sampled (200 draws) is the pre-registered method, not a choice.** Exact over
22 players (2²² coalitions) is also computationally infeasible. The entry is kept (not erased) for audit
honesty; the correction supersedes it.

> **Governance-design lesson (carried to `AEGIS_GOVERNANCE.md`):** a gate's closed option set must **never
> re-open a pre-registered analytics parameter** (estimator mode, tolerances, thresholds, seed). Those are
> fixed methodology, identical across datasets. Gates decide *governance* (scope, fairness, cutoffs, Go/No-Go),
> not *analytics*. Offering "exact vs sampled" at G2 was a category error.

**Corrected decision (entry `93fae307`):** accept the **sampled** attribution (`SHARP_GERMAN.md`, the governed
eligible-pool run). Basis it is trustworthy: all 10 confirmed players had **confirmation frequency ≥ 0.9995**
(cleared the shadow bar in ~100% of resamples), the Monte-Carlo SE is reported per player, and the
tight-ratio tail players (`housing`, `property`, `other_installment_plans`) are **not selected** at G3 anyway.

## G1 — Screening  ·  status: ✅ DECIDED (Option A)

**Signer:** Ravi (Independent Model Validator) · **2026-10-13** · entry_hash `491a1048`
**Decision:** advance **12 candidates**; drop 5 weak-IV columns (existing_credits, job, telephone, residence_since, **people_liable** IV 0.000). The proxy `people_liable` falls out on its own (no signal); the proxy **`housing`** (IV 0.083) is retained into Stage 2 for disparate-impact testing at G4 (condition GC2). `credit_amount` rescued (non-monotonic). Rejected B (proactive housing removal — pre-empts G0 plan), C/D.

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)

**Materiality tier:** MEDIUM (heightened G4 fairness scrutiny) · **Signer:** Ravi (Data Steward) · **2026-10-13** · entry_hash `d3e30cf3`

**Decision:** exclude the 3 ECOA/Reg B **prohibited** attributes (`personal_status_sex`, `age`, `foreign_worker`) from the candidate pool **before** modelling; retain the 2 **proxy** attributes (`housing`, `people_liable`) with disparate-impact testing deferred to G4. Triggers a **clean re-run** of Stages 1–4 on the 17-feature eligible pool so no downstream number is derived from a prohibited basis.

**Conditions carried:**
- **GC1 (→ GF):** observation-window gap vs CRE36.79 (cross-sectional, no time axis) — not production-IRB until dated data.
- **GC2 (→ G4):** proxy attributes `housing`/`people_liable` retained — must pass disparate-impact testing at G4.

Rejected: B (lets a prohibited basis enter the modelling process — ECOA exposure), C (over-excludes legitimate `housing` signal), D (ECOA position already clear; no escalation needed).
