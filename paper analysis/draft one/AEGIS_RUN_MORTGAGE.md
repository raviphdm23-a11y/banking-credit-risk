# AEGIS governed run — MORTGAGE (US mortgage performance panel, origination snapshot)

**Dataset:** US mortgage performance panel (Baesens, Roesch & Scheule, *Credit Risk Analytics*). The
**first PANEL dataset** taken through a governed run. 622,489 loan-period rows → **50,049 loans** under the
composite entity key `(id, orig_time)` (a bare `id` is reused across refinances). **Snapshot framing**
(`ml_models/panel_adapter.py`): one row per loan, features = origination characteristics, target = loan
**ever defaults** over its observed life. **30.28%** ever-default · 6 governed features.
**Materiality tier:** MEDIUM (immaterial public research benchmark). **Fairness NOT live in data** — no
protected attributes — but borrowers ARE natural persons, so EU AI Act / ECOA are *in scope* (see GF, a
recorded difference from the Polish firm-level run). Source: `data/ml_lab/datasets/mortgage.csv`
(+ manifest `mortgage.manifest.json`; governed frame `mortgage_snapshot.csv`). Seed 42.

> **Gate option sets and the GF verdict are emitted by `ml_models/aegis_gates.py`** (deterministic §4 GDR
> grammar + §7 Go/No-Go engine over the §8 checklist), not authored per run. Panel reshaping is handled by
> `ml_models/panel_adapter.py` in front of the unchanged SHARP pipeline; the snapshot framing yields one
> independent row per loan, so the existing stratified CV is leakage-safe.

## Decision summary

| # | Gate | Decision | Signer | Basis | prev | entry_hash |
|---|---|---|---|---|---|---|
| 0 | G0 | **A — adopt snapshot scope; MEDIUM** | Ravi / Model Validator | panel→snapshot; composite key (id,orig_time)=50,049 loans; co-outcomes payoff_time/status_time excluded as leakage; single viable scope (hazard framing deferred) | GEN-MORTGAGE_0 | `dcc9eff0` |
| 1 | G1 | **A — advance 6/10, sufficiency clears** | Ravi / Model Validator | 6/10 pass IV≥0.02 monotonic WOE; dominant `hpi_orig_time` IV 0.522; EPV ≈1,515; Riley 358 vs 50,049 (**140×**) — event-rich, no caveat | `dcc9eff0` | `a8be7730` |
| 2 | G2 | **A — accept 6/6 confirmed players** | Ravi / Model Validator | shadow bar 0.00086; all 6 confirmed (freq 1.00); `hpi_orig_time` ~143× bar, weakest `term_orig` ~11.9×; sampled estimator (P8); 10 shadows rejected | `a8be7730` | `bf5ab540` |
| 3 | G3 | **A — adopt k=6 (no reduction)** | Ravi / Model Validator | PARSIMONY-NULL: at n=50k DeLong distinguishes every k<6 (p≈0.000), so smallest defensible k = full 6; Gini 0.464; **6 players = 6 columns** (compact, contrast Polish 37) | `bf5ab540` | `0e43f77e` |
| 4 | G4 | **B — approve calibration w/ HL caveat (fairness N/A in data)** | Ravi / Risk Officer | AUC 0.732 (OOF, ≥floor 0.70); ECE 0.0074; HL g10 p≈0.000 **rejected** (large-n) but g5 p=0.341; per-grade backtest **8/8** governs; no sparse grade; no protected attrs | `0e43f77e` | `ee1c5acb` |
| 5 | G5 | **A — confirm controls + deliverables** | Ravi / Model Owner | adverse floor + exact WOE reason codes + reject-on-incomplete; zero missingness (no mandatory field needed); cutoff policy + 6-case acceptance pack | `ee1c5acb` | `cb65985c` |
| F | **GF** | **GO-WITH-CONDITIONS** (engine) | Ravi / MAC Chair + CRO | all gates signed; no must-have GAP; PARTIALs **R4** (HL caveat) + **R12** (natural-person AI-Act, fairness not assessable); conditions also NEVER-DEPLOY, ORIGINATION-ONLY, ISOTONIC-CEILING | `cb65985c` | `56578ceb` |

**Chain:** `GEN-MORTGAGE_0 → dcc9eff0 → a8be7730 → bf5ab540 → 0e43f77e → ee1c5acb → cb65985c → 56578ceb`

---

## G0 — Data & Scope Adequacy · A · `dcc9eff0`
First panel dataset. The scope decision is the **snapshot framing**: the 622,489 loan-period rows collapse
to **50,049 loans** (composite key `(id, orig_time)` — a bare `id` is reused across refinances, so id alone
would merge two distinct loans' outcomes). Features come from each loan's **first observed period**
(origination characteristics); the target is read from **all** of the loan's rows (ever-default). The
time-varying covariates and co-outcomes (`payoff_time`, `status_time`) are out of the origination scope;
the latter two are excluded as leakage by computable precondition. Engine emitted a **single viable
option** (within the snapshot framing nothing else is eligible to exclude) and flagged it for confirmation.
The alternative **hazard** framing (keep the time-varying trajectory) is deferred — its group-aware CV is
not yet wired through Stage 2.

## G1 — Screening & Data Sufficiency · A · `a8be7730`
6 of 10 candidates pass IV ≥ 0.02 with monotonic WOE; the 4 dropped are all property-type / investor
dummies (IV < 0.01). Dominant `hpi_orig_time` IV **0.522** (house-price index at origination — loans
originated near HPI peaks default more). **Sufficiency is the mirror image of Polish:** event-rich, with
**EPV ≈ 1,515** (15,155 defaulting loans / 10-feature pool) and the modern **Riley minimum MET ~140×**
(358 required vs 50,049 available; B1 325 / B3 358 / B4 155; EPP@req 18.1). No sufficiency caveat — clean A.

## G2 — Importance Attribution · A · `bf5ab540`
Sampled SPVIM Shapley (6 real + 10 shadows = 16 > 15 → sampled, P8; 200 permutations, max MC SE 0.0029);
shadow bar **0.00086**. **All 6 players confirmed** at confirmation frequency 1.00 — none borderline.
`hpi_orig_time` dominates (Shapley 0.1235, ~143× the bar); weakest confirmed `term_orig` (0.0103, ~11.9×).
The shadow-null correctly rejected all 10 noise players (highest shadow confirmation 0.993, rest ≈ 0).

## G3 — Parsimony Selection · A · `0e43f77e`
Parsimony rule (smallest k with DeLong p ≥ 0.05 **and** rel-Gini loss ≤ 5%) returns **k = 6 of 6** — a
**PARSIMONY-NULL** outcome: at n = 50,049 the DeLong test distinguishes every smaller model from the full
set (k=1..5 all p ≈ 0.000), so the smallest defensible k is the full candidate set itself. Gini **0.464**,
rel. loss 0.00%. **6 players span 6 columns** — a genuinely compact origination scorecard, the opposite of
Polish's PARSIMONY-WIDTH (6 players = 37 columns). Same "no reduction DeLong-defensible" outcome as HMEQ,
sharper at this n. Selected: `hpi_orig_time, Interest_Rate_orig_time, FICO_orig_time, LTV_orig_time,
balance_orig_time, term_orig`.

## G4 — Calibration (fairness N/A in data) · B · `ee1c5acb`
**Discrimination:** AUC 0.732 / Gini 0.464 (out-of-fold; MEDIUM floor 0.70 — clears, modestly; the honest
ceiling of an origination-only scorecard). **Calibration:** ECE 0.0074; HL g=10 **p ≈ 0.000 (rejected)**
but g=5 **p = 0.341 (passes)**; per-grade realised-vs-expected backtest **8/8 grades inside the Wilson 95%
CI** (smallest grade A, n=54 — no sparse cell). The HL g=10 rejection is a large-n artefact (n≈50k makes HL
hyper-powered); the **per-grade backtest is the governing calibration test** (CRE36.122), so the HL
rejection rides as a disclosed caveat + MoC — the **same pattern as SBA**. **Fairness: not computed** — no
protected attributes exist in the data. Engine recommended **B (ADOPT_WITH_CONDITION)**.

## G5 — Deployment Governance · A · `cb65985c`
Scoring controls: exact additive-WOE reason codes; adverse floor active on all 6 features; reject-on-
incomplete policy. **No field is designated mandatory** — the collapsed frame has **zero missingness** on
all 6 features, so there is no missing input to gate. PD floor 0.03% / cap 99.9% (though the cap never
binds — see below). Deliverables: `AEGIS_MORTGAGE_CUTOFF_POLICY.md` + `SAMPLE_RUNS_MORTGAGE.md` (4 real +
2 synthetic). Acceptance pack confirms the **PD floor binds** (MG-R1/S1 → 0.03% AAA) and the **99.9% cap
does NOT bind** — isotonic calibration ceilings at ≈0.68, so even the all-worst-origination stress case
scores 68% (grade D). Real defaulted loan MG-R3 honestly scores only 17.5% (grade CCC) — a false-negative
the origination-only scope makes unavoidable without behavioural data.

## GF — Final Go/No-Go · **GO-WITH-CONDITIONS** (engine) · `56578ceb`
`gf_engine` over the sealed gate states + §8 checklist: all gates signed; **no must-have (R1–R9) GAP**;
remediable PARTIALs on **R4** (MORTGAGE-CAL — HL large-n rejection, per-grade backtest governs, disclosed
caveat + MoC) and **R12** (MORTGAGE-AIACT). **R12 is the recorded contrast with Polish:** mortgage
borrowers are **natural persons**, so EU AI Act Annex III high-risk credit scoring **is in scope** (it was
N/A for Polish firms), and ECOA adverse-action (R14) is likewise in scope and SATISFIED by the exact WOE
reason codes — but fairness/bias cannot be assessed (no protected attributes in the dataset), so R12 is a
disclosed PARTIAL under NEVER-DEPLOY. **R6 is SATISFIED** (event-rich, no EPV shortfall) and **R10
SATISFIED** (zero missingness) — both the opposite of Polish. Standing scope conditions: **NEVER-DEPLOY**
(research benchmark), **ORIGINATION-ONLY** (snapshot; hazard framing with time-varying covariates deferred),
**ISOTONIC-CEILING** (calibrated PD tops at ≈0.68; 99.9% cap never binds). Verdict **GO-WITH-CONDITIONS**;
no blockers, no return.
