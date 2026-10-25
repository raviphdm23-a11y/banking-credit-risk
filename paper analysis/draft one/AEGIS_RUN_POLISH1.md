# AEGIS governed run — POLISH1 (Polish companies bankruptcy, Year-1 horizon)

**Dataset:** Polish companies bankruptcy data (Zięba, Tomczak & Tomczak 2016; UCI #365). **Year-1 horizon** —
financial ratios observed in the 1st year of the forecasting period, bankruptcy status checked over the
following 5 years (the longest / hardest horizon of the five files). 7,027 firms · 3.86% bad rate (271
bankruptcies) · 64 anonymised financial ratios (`Attr1–Attr64`).
**Materiality tier:** MEDIUM (immaterial public research benchmark). **Fairness NOT live** — all features are
firm financial ratios; no protected attributes exist. Source CSV: `data/ml_lab/datasets/polish_bankruptcy_1year.csv`
(target `class`). Seed 42.

> **Gate option sets and the GF verdict are emitted by `ml_models/aegis_gates.py`** (deterministic §4 GDR
> grammar + §7 Go/No-Go engine over the §8 checklist), not authored per run.

## Decision summary

| # | Gate | Decision | Signer | Basis | prev | entry_hash |
|---|---|---|---|---|---|---|
| 0 | G0 | **A — adopt scope: all 64 ratios eligible; MEDIUM** | Ravi / Data Steward | no protected attributes; Attr55 sentinel-leakage flag investigated (2 rows) and dismissed; single viable scope | GEN-POLISH1_0 | `40c99d36` |
| 1 | G1 | **B — advance 60/64 with EPV-MoC caveat** | Ravi / Model Validator | 60 pass IV≥0.02 monotonic WOE; dominant `Attr27` IV 2.80; EPV 4.2 (<10) → MoC + not-for-capital; Riley 5,141 vs 7,027 (1.37×) MET | `40c99d36` | `12a4cf62` |
| 2 | G2 | **A — accept 15/18 confirmed players** | Ravi / Model Validator | shadow bar 0.00270; dominant Attr27 ~48× bar; weakest confirmed ~2.2×; sampled estimator (P8); null correctly rejected Attr37 + 2 weak clusters | `12a4cf62` | `af7044c8` |
| 3 | G3 | **A — adopt parsimonious k=6 players (37 cols)** | Ravi / Model Validator | `Attr27`+4 clusters+`Attr21`; Gini 0.783, DeLong p 0.619, rel loss 0.41%; decision-parsimonious, NOT column-parsimonious | `af7044c8` | `87a1472a` |
| 4 | G4 | **A — approve calibration (fairness N/A)** | Ravi / Risk Officer | AUC 0.892 (OOF, floor 0.70); HL g10 p0.379 / g5 p0.514; ECE 0.0033; per-grade backtest 10/10 in Wilson CI; no sparse grade; no protected attrs | `87a1472a` | `55f05829` |
| 5 | G5 | **A — confirm controls + deliverables** | Ravi / Model Owner | mandatory `Attr27`/refer; exact WOE reason codes; PD floor/cap; cutoff policy + 6-case acceptance pack | `55f05829` | `622222b8` |
| F | **GF** | **GO-WITH-CONDITIONS** (engine) | Ravi / MAC Chair + CRO | all gates signed; no must-have GAP; PARTIALs **R6** (EPV-SHORT) + **R10** (completeness); conditions also NEVER-DEPLOY, PARSIMONY-WIDTH | `622222b8` | `3870d5f4` |

**Chain:** `GEN-POLISH1_0 → 40c99d36 → 12a4cf62 → af7044c8 → 87a1472a → 55f05829 → 622222b8 → 3870d5f4`

---

## G0 — Data & Scope Adequacy · A · `40c99d36`
All 64 attributes are anonymised firm financial ratios → **no protected attributes → fairness not live** at
G4 (a recorded difference from the consumer-credit runs). The Stage-0 heuristic raised a **sentinel-leakage
candidate on `Attr55`** (values −999 / 98, event rate 0.500 vs base 0.039, lift 13×); investigated and
**dismissed** — the flag rests on exactly 2 rows (one value −999 at 1 firm, one value 98 at 1 firm); the other
7,025 firms sit at the base rate. No systematic outcome leakage → no exclusion. Engine emitted a **single
viable option** (nothing eligible to exclude) and flagged it for confirmation per the anti-strawman rule.

## G1 — Screening & Data Sufficiency · B · `12a4cf62`
60 of 64 candidates pass IV ≥ 0.02 with monotonic WOE (4 dropped: `Attr47/64/36/59`, IV ≤ 0.076). Dominant
`Attr27` IV **2.80** (Cramér's V 0.39). **Sufficiency disagreement, disclosed:** legacy **EPV ≈ 4.2**
(271 events / 64-ratio pool) is below the EPV ≥ 10 rule, but the modern **Riley minimum is MET** — 5,141
required (P=60, c=0.893, prev 3.9%) vs 7,027 available (**1.37×**). Engine recommended **B
(ADOPT_WITH_CONDITION)**: proceed, disclose the EPV limit, carry a mandatory MoC + not-for-capital.

## G2 — Importance Attribution · A · `af7044c8`
Sampled SPVIM Shapley (28 players incl. 10 shadows > 15 → sampled, P8); shadow bar **0.00270**. The 60 screened
columns cluster (|ρ|=0.7) into 18 real players; **15 confirmed** (confirmation freq ≥ 0.9965 — none borderline).
`Attr27` dominates (~48× the bar); weakest confirmed `grp[Attr34+Attr9]` ~2.2× the bar. The shadow-null
**correctly rejected** the 3 weakest players — `grp[Attr44+Attr61]` (freq 0.43), `grp[Attr20+Attr43+Attr60]`
(freq 0.0005) and **`Attr37`** (the ~44%-missing column, freq 0.0).

## G3 — Parsimony Selection · A · `87a1472a`
Parsimony rule (smallest k with DeLong p ≥ 0.05 **and** rel-Gini loss ≤ 5%) selects **k = 6 players of 15**:
`Attr27`, `grp[20 ratios]`, `grp[Attr46+Attr5]`, `grp[7 ratios]`, `grp[6 ratios]`, `Attr21`. Gini **0.783**
vs full 0.786, DeLong **p = 0.619**, rel. loss **0.41%**. **PARSIMONY-WIDTH caveat:** because the ratios are
highly collinear, the 6 players span **37 of 60 columns** — parsimonious in *decision* terms (6 independent
signals reproduce 99.6% of full Gini) but **not** in column count, unlike German's genuine 5-feature model.
Both numbers are reported.

## G4 — Calibration (fairness N/A) · A · `55f05829`
**Discrimination:** AUC 0.892 / Gini 0.783 (out-of-fold; MEDIUM floor 0.70 — clears). **Calibration:**
ECE 0.0033; HL g=10 **p=0.379**, g=5 **p=0.514** (both pass); per-grade realised-vs-expected backtest
**10/10 grades inside the Wilson 95% CI** (smallest grade C, n=42 — **no sparse cell**, unlike German).
**Fairness: not computed** — no protected attributes exist (firm financials). Engine emitted a single viable
ADOPT option (no fairness-conditions path) and flagged it for confirmation.

## G5 — Deployment Governance · A · `622222b8`
Scoring controls: mandatory `Attr27` (blank → refer; 311 of 7,027 firms, incl. 120 defaults, carry a missing
`Attr27`); `incomplete_policy=refer`; exact WOE reason codes; PD floor 0.03% / cap 99.9%. Deliverables on the
approved 6-player/37-column model: `AEGIS_POLISH1_CUTOFF_POLICY.md` + `SAMPLE_RUNS_POLISH1.md` (4 real + 2
synthetic; floor binds on PL-R1 & PL-S1, cap binds on PL-S2, completeness gate REFERs PL-R4).

## GF — Final Go/No-Go · **GO-WITH-CONDITIONS** (engine) · `3870d5f4`
`gf_engine` over the sealed gate states + §8 checklist: all gates signed; **no must-have (R1–R9) GAP**;
remediable PARTIALs on **R6** (EPV-SHORT — EBA category-A deficiency, MoC + not-for-capital; Riley met) and
**R10** (completeness — 54.5% of rows carry ≥1 missing ratio, handled by WOE `__missing__` + mandatory-field
refer). Standing scope conditions: **NEVER-DEPLOY** (research benchmark) and **PARSIMONY-WIDTH** (6 players =
37 columns). **R12 / R14 are N/A** — borrowers are firms, not natural persons, so EU AI Act Annex III
high-risk credit-scoring and ECOA adverse-action do not bind (they did for the consumer-credit runs). Verdict
**GO-WITH-CONDITIONS**; no blockers, no return.

---

## Addendum — G0 evidence annotated with the published feature dictionary (2026-10-25; chain unchanged)

*Append-only; no gate decision is altered.* Definitions now recorded in
`data/ml_lab/datasets/polish_bankruptcy.dictionary.json` (UCI 365, verified; see `SHARP_POLISH1.md` addendum).

- **`Attr55` flag:** `Attr55` is *working capital* (an absolute amount), so −999 and 98 are plausible real
  values, not codes. The G0 dismissal stands; the flag was a false positive of the sentinel heuristic.
- **"All 64 ratios"** (G0 wording) is loose: `Attr29` is log(total assets) and `Attr55` an absolute amount.
- **Leakage review, now possible by name:** the selected features are financial-statement ratios
  (profitability, liquidity, leverage, coverage, growth, interest cover). **One open item:** `Attr24` =
  "gross profit (in 3 years) / total assets" — the source does not say whether the 3 years precede or follow
  the statement date. If they follow, it is outcome leakage. It is in the selected profitability group and is
  the most frequent reason code in the acceptance pack. **Definition unresolved** (needs the original paper
  / data author), **but bounded:** dropping Attr24 moves selected-model OOF Gini 0.7832 → 0.7766 (−0.83%,
  DeLong p 0.177 — not distinguishable), so no gate outcome depends on it; the residual exposure is the
  reason codes. No other selected definition suggests post-statement information.
- **New G0-relevant fact from the source:** bankrupt firms were sampled over 2000–2012 and operating firms
  over 2007–2013, i.e. the two classes come from different calendar windows. It is a period confound that
  cannot be tested without dates. It is recorded here as a disclosure and does not alter GF.
