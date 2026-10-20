# AEGIS governed run — GERMAN (South German Credit, Grömping 2019 corrected)

**Dataset:** South German Credit (Grömping 2019, UCI #522) — the error-corrected recoding of the Statlog German
Credit data. **Supersedes** the archived Statlog run (`archive/german_statlog_superseded/`); this is a draft-stage
**input correction**, not a reported finding. 1,000 loans · 30.0% bad rate · 20 variables.
**Materiality tier:** MEDIUM (immaterial public research benchmark). **Fairness LIVE** (age / sex / foreign-worker).
Consumer credit → protected attributes present. Source CSV: `data/ml_lab/datasets/south_german_credit_en.csv`. Seed 42.

> **Gate option sets and the GF verdict are emitted by `ml_models/aegis_gates.py`** (deterministic §4 GDR grammar +
> §7 Go/No-Go engine over the §8 checklist), not authored per run. Reproduces the committed German verdict
> (GO-WITH-CONDITIONS, k=5, Gini ~0.54, sex clean, age true-risk-driven).

## Decision summary

| # | Gate | Decision | Signer | Basis | prev | entry_hash |
|---|---|---|---|---|---|---|
| 0 | G0 | **A — exclude age + personal_status_sex + foreign_worker (hard protected); MEDIUM** | Ravi / Data Steward | compliance-first; 17-feature pool; single viable scope (no borderline columns) | GEN-GERMAN0 | `eeaa6cd7` |
| 1 | G1 | **A — accept 12/17 screen; sufficiency met** | Ravi / Model Validator | EPV ≈ 17.6 (300/17); Riley 323 vs 1,000 (3.1×); `checking_status` IV 0.666; `credit_amount` shape-escalated | `eeaa6cd7` | `670b8e1a` |
| 2 | G2 | **A — accept 12/12 confirmed players** | Ravi / Model Validator | all 12 clear shadow bar 0.00214; sampled estimator (P8); `installment_rate` borderline-confirmed (watch) | `670b8e1a` | `f8a3cfab` |
| 3 | G3 | **A — adopt parsimonious k=5** | Ravi / Model Validator | `checking_status, credit_history, months_duration, savings_status, credit_amount`; Gini 0.542, DeLong p 0.107, rel loss 4.56% | `f8a3cfab` | `0c9b65dd` |
| 4 | G4 | **B — approve with conditions (dual: calibration + fairness)** | Ravi / Risk Officer + Validator | AUC 0.771; HL g10 p0.112 / g5 p0.194; per-grade 8/8 in CI; sex AIR 0.933 PASS; age AIR 0.340 true-risk-driven; foreign fragile | `0c9b65dd` | `1ac12b5e` |
| 5 | G5 | **A — confirm controls + deliverables** | Ravi / Model Owner | mandatory `checking_status`/refer; exact WOE reason codes; PD floor/cap; cutoff policy + 6-case acceptance pack | `1ac12b5e` | `496d214e` |
| F | **GF** | **GO-WITH-CONDITIONS** (engine) | Ravi / MAC Chair + CRO | all gates signed; no must-have GAP; PARTIALs R4 (SPARSE-A) + R12 (AGE-IMPACT, FW-FRAGILE); NEVER-DEPLOY | `496d214e` | `a92fa411` |

**Chain:** `GEN-GERMAN0 → eeaa6cd7 → 670b8e1a → f8a3cfab → 0c9b65dd → 1ac12b5e → 496d214e → a92fa411`

---

## G0 — Data & Scope Adequacy · A · `eeaa6cd7`
Exclude the three hard protected attributes (`age`, `personal_status_sex`, `foreign_worker`) by the computable
G0 taxonomy (METHODOLOGY §3.7) → 17-feature pool. MEDIUM tier. The engine emitted a **single viable option**
(no borderline columns to retain under MoC, no hard adequacy flag) and flagged it per the anti-strawman rule.

## G1 — Screening & Data Sufficiency · A · `670b8e1a`
12 of 17 candidates pass IV ≥ 0.02 with monotonic WOE; `checking_status` dominant (IV 0.666). Sufficiency met:
**EPV ≈ 17.6** (300 events / 17-feature pool), **Riley minimum 323 vs 1,000 available (3.1× headroom)**.
`credit_amount` carries a non-monotonic (U-shape) flag → routed to the Stage-2 model check, not judged on IV.

## G2 — Importance Attribution · A · `f8a3cfab`
Sampled SPVIM Shapley (>15-player rule, P8); shadow bar 0.00214. **All 12 players confirmed** (confirmation
frequency ≥ 0.80). `checking_status` dominates (~46× the bar); weakest `installment_rate` (freq 0.864, ~1.4× bar)
flagged borderline-confirmed → G3 watch item. `credit_amount` confirmed and vindicated from its IV-screen shape flag.

## G3 — Parsimony Selection · A · `0c9b65dd`
Parsimony rule (smallest k with DeLong p ≥ 0.05 **and** rel-Gini loss ≤ 5%) selects **k = 5**:
`checking_status, credit_history, months_duration, savings_status, credit_amount`. Gini **0.5422**, DeLong
**p = 0.107**, rel. loss **4.56%**. (`installment_rate`, the G2 watch item, sits at k=12 — well outside the set.)

## G4 — Calibration & Fairness (dual) · B · `1ac12b5e`
**Discrimination:** AUC 0.771 / Gini 0.542 (out-of-fold, floor 0.70 MEDIUM — clears). **Calibration:** ECE 0.033;
HL g=10 **p=0.112**, g=5 p=0.194 (both pass); per-grade realised-vs-expected backtest **8/8 grades inside Wilson CI**
(only grade A sparse, n=4). **Fairness** (proxy-leakage AIR on the *excluded* protected attributes; indicative, no cutoff):
- **sex** AIR **0.933 — PASS** (no proxy leakage);
- **age** AIR **0.340 — FAIL** four-fifths but **true-risk-driven** (default <25 = 41.3% → 60+ = 25.5%; age excluded
  yet impact persists via correlated features — necessary-not-sufficient);
- **foreign_worker** AIR 0.730 — **fragile/inconclusive** (2 approvals in the 37-row minority).
- *Caveat:* approve rate is 4.0%, so all AIRs rest on small approve counts (k = 2–38).

Engine recommends **B (approve with conditions)**: SPARSE-A (grade A MoC) + AGE-IMPACT / FW-FRAGILE fairness caveats.

## G5 — Deployment Governance · A · `496d214e`
Scoring controls: mandatory `checking_status` (blank → refer); `incomplete_policy=refer`; exact WOE reason codes;
PD floor 0.03% / cap 99.9%. Deliverables on the corrected 5-feature model: `AEGIS_GERMAN_CUTOFF_POLICY.md` +
`SAMPLE_RUNS_GERMAN.md` (6 cases: both floor and cap bind; completeness gate enforced).

## GF — Final Go/No-Go · **GO-WITH-CONDITIONS** (engine) · `a92fa411`
`gf_engine` over the sealed gate states + §8 checklist: all gates signed; no must-have (R1–R9) GAP; remediable
PARTIALs on **R4** (SPARSE-A) and **R12** (AGE-IMPACT, FW-FRAGILE). Verdict **GO-WITH-CONDITIONS**, conditions
AGE-IMPACT / FW-FRAGILE / SPARSE-A / NEVER-DEPLOY. Reproduces the committed German verdict (determinism confirmed).
