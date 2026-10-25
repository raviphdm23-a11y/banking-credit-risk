# AEGIS governed run — MORTGAGE_HAZARD (US mortgage panel, discrete-time hazard)

**Dataset:** US mortgage performance panel (Baesens, Rösch & Scheule, *Credit Risk Analytics*).
**Discrete-time HAZARD framing** via `ml_models/panel_adapter.py`: **all 622,489 loan-period rows kept**
(50,049 loans, composite key `(id, orig_time)`), target = default **in that period** (per-period hazard,
base rate **2.44%**). The richer counterpart to the origination-snapshot run (`AEGIS_RUN_MORTGAGE.md`):
it uses the time-varying + macro covariates the snapshot excludes. **11 governed features** = 3 time-varying
+ 3 macro + 5 origination. **Materiality tier:** MEDIUM. **Fairness NOT live in data** (no protected
attrs), but borrowers are natural persons so EU AI Act / ECOA are in scope. Source:
`data/ml_lab/datasets/mortgage.csv` (+ `mortgage_hazard.manifest.json`). Seed 42.

> **Leakage control.** Group-aware CV (StratifiedGroupKFold by loan) keeps every loan's rows inside one fold,
> threaded through Stages 2–4 (`selection`, `shapley_utils`, parsimony, calibration). Shapley importance ran
> on a group-aware 80k-row subsample for tractability; parsimony + calibration on all 622k rows. The
> calibration GOF is cluster-robust and assesses the DEPLOYED (isotonically-calibrated) model
> (`ml_models/calibration_gof.py`). Gate options emitted by `ml_models/aegis_gates.py`.

## Decision summary

| # | Gate | Decision | Signer | Basis | prev | entry_hash |
|---|---|---|---|---|---|---|
| 0 | G0 | **A — adopt hazard scope; MEDIUM** | Ravi / Model Validator | panel→hazard; composite key; co-outcomes payoff/status excluded as leakage; time-leakage disclosed; single viable scope | GEN-MORTGAGE_HAZARD_0 | `9ececb8c` |
| 1 | G1 | **A — advance 11/15, sufficiency clears** | Ravi / Model Validator | 11/15 pass IV≥0.02; dominant `LTV_time` IV 0.399; EPV ≈1,011; Riley 5,177 vs **50,049 loans (9.7×)** — event-rich | `9ececb8c` | `52f57eb3` |
| 2 | G2 | **A — accept 9/9 confirmed players** | Ravi / Model Validator | shadow bar 0.00089; all 9 confirmed (freq 1.00); dominant `interest_rate_time` ~60× bar, weakest ~10.3×; sampled (P8) | `52f57eb3` | `4802715c` |
| 3 | G3 | **A — adopt k=9 (11 cols), PARSIMONY-NULL** | Ravi / Model Validator | at n=622k DeLong distinguishes every k<9 (p≈0), so full set adopted; Gini 0.474, rel loss 0% | `4802715c` | `ba6d95cb` |
| 4 | G4 | **A — approve calibration (clean)** | Ravi / Risk Officer | DEPLOYED model: cluster-robust per-grade **7/7**; HL g10 p=0.11/0.65-adj (not rejected); ECE 0.0005; AUC 0.737 ≥ floor; fairness N/A | `ba6d95cb` | `a877b2b0` |
| 5 | G5 | **A — confirm controls + deliverables** | Ravi / Model Owner | adverse floor + exact WOE reason codes + reject-on-incomplete; near-zero missingness; cutoff policy + 6-case per-period acceptance pack | `a877b2b0` | `f4e28439` |
| F | **GF** | **GO-WITH-CONDITIONS** (engine) | Ravi / MAC Chair + CRO | all gates signed; no must-have GAP; PARTIALs **R7** (TIME-LEAKAGE) + **R12** (AI-Act); conditions also NEVER-DEPLOY, ISOTONIC-CEILING | `f4e28439` | `dca8af15` |
| F′ | **GF reconvened** | **B — GO-WITH-CONDITIONS** (engine) | Ravi / MAC Chair + CRO | out-of-time evidence (post-GF addendum) made **binding for calibration**: **R4 → PARTIAL** (3/7 forward, HL rejected); discrimination bar kept on in-time AUC, consistent with the corpus; R7 updated to "OOT performed, unfavourable" | `dca8af15` | `000af56d` |

**Chain:** `GEN-MORTGAGE_HAZARD_0 → 9ececb8c → 52f57eb3 → 4802715c → ba6d95cb → a877b2b0 → f4e28439 → dca8af15 → 000af56d` (current; `dca8af15` retained as history)

---

## G0 — Data & Scope Adequacy · A · `9ececb8c`
Discrete-time hazard scope: all 622,489 loan-periods retained, target = per-period `default_time`, using the
time-varying (dynamic LTV/balance/rate) + macro (gdp/uer/hpi) covariates the snapshot excludes. Composite key
`(id, orig_time)` = 50,049 loans. Co-outcomes `payoff_time` / `status_time` excluded as leakage by
precondition. **Disclosed at G0 and carried to GF:** group-aware CV removes entity leakage but NOT time
leakage (shared macro per calendar period); no out-of-time validation. Single viable scope.

## G1 — Screening & Data Sufficiency · A · `52f57eb3`
11 of 15 candidates pass IV ≥ 0.02 (vs snapshot's 6/10 — the time-varying covariates clear the screen).
Dominant `LTV_time` IV **0.399** (dynamic LTV). The 4 dropped are property-type / investor dummies.
**Sufficiency reported conservatively at the loan-cluster level:** EPV ≈ 1,011; Riley 5,177 required vs
**50,049 loans (9.7×)** — not the flattering 622k-row figure (120×), since the rows are clustered. Event-rich,
no shortfall.

## G2 — Importance Attribution · A · `4802715c`
Sampled SPVIM Shapley under grouped CV (9 real + 10 shadows = 19 > 15 → sampled, P8; 200 permutations).
Shadow bar **0.00089**. **All 9 players confirmed** (freq 1.00). Dominant `interest_rate_time` (~60× bar) and
`LTV_time` — both time-varying; macro `grp[hpi_time+uer_time]` and `gdp_time` also confirm. All 10 shadow-null
players rejected (top shadow freq 0.85). The hazard framing genuinely extracts trajectory + macro signal.

## G3 — Parsimony Selection · A · `ba6d95cb`
**PARSIMONY-NULL**: k = 9 of 9 (11 columns). At n = 622,489 DeLong distinguishes every smaller model from the
full set (k=1..8 all p ≈ 0), so the full confirmed set is adopted. Gini **0.474**, rel loss 0%. Same pattern
as the snapshot (k=6 of 6). **Checked after the seal (see addendum):** a cluster-robust DeLong
(`selection.cluster_delong_test`, resampling whole loans) was built to test whether the i.i.d. DeLong was
over-powered by the clustered loan-periods. It was not: k=2/3/5 all remain distinguishable from the full set
(p ≈ 0; even the 0.006 AUC gap at k=5 is ~10 cluster-robust SEs), so PARSIMONY-NULL is genuine at 50,049
loans. (An earlier version of this section called it "partly an artefact"; that was wrong and is corrected.)

## G4 — Calibration (fairness N/A) · A · `a877b2b0`
**Discrimination:** AUC 0.737 / Gini 0.474 (grouped OOF; MEDIUM floor 0.70 — clears). **Calibration — tested
on the DEPLOYED (isotonically-calibrated) model, cluster-robust (held-out 10,010 loans):** per-grade backtest
**7/7 inside the cluster-bootstrap CI**; HL g=10 **p = 0.11 (raw) / 0.65 (design-effect adj.)**, g=5 0.36 /
0.69 — **not rejected**; ECE **0.0005**. *Cleaner than the snapshot run (whose HL rejected).* **Methodology
note:** the raw WOE-logistic OOF had small per-grade bias and over-rejected (1/7, HL p≈0) on the clustered
622k rows; this was resolved by (a) testing the calibrated model and (b) a cluster-robust interval — both now
automatic via `calibration_gof.deployment_backtest` wired into Stage 4. **Fairness: not computed** — no
protected attributes. Engine emitted a single clean ADOPT.

## G5 — Deployment Governance · A · `f4e28439`
Scoring controls: exact additive-WOE reason codes; adverse floor on all 11 features; reject-on-incomplete.
**No mandatory field** — near-zero missingness (only `LTV_time` 270/622,489). PD floor 0.03% / cap 99.9% (cap
never binds — isotonic ceiling ≈14.6% for a rare per-period event). Deliverables: `AEGIS_MORTGAGE_HAZARD_
CUTOFF_POLICY.md` + `SAMPLE_RUNS_MORTGAGE_HAZARD.md` (4 real loan-periods + 2 synthetic). Floor binds on
MH-R1/S1 → 0.03% AAA.

## GF — Final Go/No-Go · **GO-WITH-CONDITIONS** (engine) · `dca8af15`
`gf_engine` over the sealed gate states + §8 checklist: all gates signed; **no must-have (R1–R9) GAP**;
remediable PARTIALs on **R7** (MORTGAGE-HZ-TIME — validation is grouped i.i.d. CV only; no out-of-time /
vintage validation on a time panel; remediable with a train-past/test-future split) and **R12**
(MORTGAGE-AIACT — natural persons → EU AI Act Annex III in scope; fairness not assessable). **R4 is
SATISFIED** (deployed calibration clean) and **R6 SATISFIED** (event-rich) — the calibration scare resolved
into a methodology upgrade, not a defect. Standing scope conditions: **NEVER-DEPLOY**, **ISOTONIC-CEILING**.
**Headline:** the full time-varying + macro hazard model (Gini 0.474) barely out-discriminates the simple
6-feature origination snapshot (0.464) — the simple scorecard is preferable; the hazard run's lasting value
was forcing the cluster-robust / deployed-model calibration fix. Verdict **GO-WITH-CONDITIONS**; no blockers.

---

## Post-GF addendum — R7 out-of-time validation (2026-10-25; chain unchanged at `dca8af15`)

*Append-only. The sealed gates and hash chain are not modified; this records evidence produced after GF.*

R7 (MORTGAGE-HZ-TIME) was carried because grouped CV removes entity leakage but not time leakage and no
out-of-time (OOT) validation had been done. It has now been run: `ml_models/oot_validation.py`
(`panel_adapter.temporal_split`; wired into Stage 4 as an optional diagnostic when a time vector is
supplied). Fit on the past, score the future; isotonic calibrator fit on the past, assessed on the future
with the cluster-robust per-grade backtest. Diagnostic only — no threshold is invented.

| Cut (test_frac) | Train → test default rate | OOT Gini | OOT AUC | vs in-time 0.4742 | Per-grade | HL g10 (adj.) |
|---|---|--:|--:|--:|--:|--:|
| t ≤ 47 (0.2) | 2.70% → 1.29% | 0.3151 | 0.6575 | −33.6% | 0/6 | p ≈ 0 |
| **t ≤ 42 (0.3)** | 2.70% → 1.75% | **0.3194** | 0.6597 | −32.7% | 3/7 | p ≈ 0 |
| t ≤ 37 (0.4) | 2.59% → 2.19% | 0.2989 | 0.6495 | −37.0% | 1/7 | p ≈ 0 |

The primary cut (0.3) is a fixed convention, not tuned; the other two show the result does not depend on it.
At t=42 the test set has 14,295 loans, 2,020 of them not seen in training.

**What the evidence supports**
1. **Forward discrimination is about a third below the in-time score at every cut** (Gini 0.30–0.32 vs
   0.474). The in-time grouped-CV number overstated forward performance. OOT AUC (0.650–0.660) is below the
   0.70 MEDIUM floor that G4 applied to the in-time AUC; the floor is applied to in-time OOF across the
   corpus, so this is recorded as an observation, not a re-ruling.
2. **Calibration does not carry forward.** Calibrated on the past, 0/6–3/7 grades pass on the future and HL
   rejects at every cut. Direction: realised below expected in the higher-risk grades (e.g. grade B at t=42:
   expected 8.4%, realised 4.1%), consistent with the falling base rate (2.70% → 1.75%) — a level shift that a
   calibrator fit on the past cannot anticipate.
3. **Time-varying covariates do carry forward signal.** At t=42: 8 features without the three contemporaneous
   macro series → Gini 0.347; static origination only (5) → 0.256.

**What it does NOT establish (stated so it is not over-read)**
- *Cause — what was tested and ruled out (at the t=42 cut):*
  - **Contemporaneous macro overfit — minor.** Dropping `gdp_time`, `hpi_time`, `uer_time` raises OOT Gini
    only 0.319 → 0.347 (+0.028 of a ~0.155 drop).
  - **Loan-age (seasoning) mix shift — ruled out.** Mean loan age is 10.0 months in training vs 28.8 in test,
    so this was the leading candidate. But adding `loan_age = time − orig_time` as a feature leaves OOT Gini
    unchanged (0.316; in-time 0.481), and restricting both periods to the same ages (12–36 months) makes OOT
    *worse* (Gini 0.255, per-grade 0/6) — within that age band the default rate still falls 2.73% → 1.41%.
  - **Covariate extrapolation — ruled out.** 0% of test-period rows fall outside the training range on
    `gdp_time`, `uer_time`, `hpi_time`, `interest_rate_time` or `LTV_time`.
- *What the evidence is consistent with (interpretation, not proven):* a **credit-cycle regime shift**. The
  per-period default rate runs ~1–2% early, spikes to 3.7–4.4% at t=30–40 (inside the training window), then
  falls to 0.5–1.5% in the test window. Training spans the crisis peak and testing the recovery; with
  covariates in range and age held fixed, the same covariate values carry different default risk across the
  cycle, which neither the macro series nor isotonic recalibration on the past captures.
- *No hazard-vs-snapshot comparison follows from these numbers.* The earlier statement that the simple
  origination scorecard is "preferable" compared Ginis on different targets (per-period vs ever-default) and
  is not established by either run; the snapshot has not itself had OOT validation. Retracted here.

**Effect on conditions.** R7 stays PARTIAL but its content changes from "not performed" to "performed;
forward Gini −33%, calibration fails OOT; macro overfit, seasoning and extrapolation tested and
not the cause; consistent with a credit-cycle regime shift". NEVER-DEPLOY is reinforced.

## GF reconvened · **B — GO-WITH-CONDITIONS** · `000af56d` (prev `dca8af15`)

The MAC reconvened GF on the out-of-time evidence. The engine was run under three ratings of that evidence:
**A** disclosed only (GO-WITH-CONDITIONS: R7, R12); **B** binding for calibration (GO-WITH-CONDITIONS: R4,
R7, R12); **C** binding for discrimination, R3 GAP because OOT AUC 0.66 < the 0.70 MEDIUM floor (NO-GO,
return to G3). **Signed: B** — rationale *"option B: OOT binding for calibration, discrimination bar
consistent with corpus"*.

Reasoning recorded: the 0.70 floor is applied to the in-time grouped-CV AUC for all 14 corpus datasets, and
the cross-sectional datasets cannot be validated out-of-time (no time field), so applying it to OOT AUC for
this run alone would set a stricter bar for one dataset; the forward calibration failure, by contrast, is
unambiguous and is made binding. Option C remains the right reading if "out-of-time binds for panel models"
is later adopted as a methodology rule — it would then apply to every panel run, not this one only.

**Conditions now in force:** **R4** (MORTGAGE-HZ-CAL-OOT — calibrated on the past, 3/7 grades pass on the
future and HL rejects; in-time 7/7), **R7** (MORTGAGE-HZ-TIME — OOT performed: Gini 0.319 vs 0.474,
AUC 0.660; macro overfit minor, seasoning and extrapolation ruled out; consistent with a credit-cycle
regime shift), **R12** (MORTGAGE-AIACT), plus NEVER-DEPLOY and ISOTONIC-CEILING.
