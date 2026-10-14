# AEGIS run log — TH02 (UK consumer credit; Thomas/Edelman/Crook 2002)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/TH02.csv` — 1,225 rows, 14 features + target, event rate 0.2637 (**323 events**).
**Started:** 2026-10-14 · **Human signer:** Ravi · **Materiality tier:** MEDIUM (public benchmark) · **Record:** `SHARP_TH02.md`
**Tenth governed run — the LITERATURE-BENCHMARKABLE CLEAN run (Thomas, Edelman & Crook, *Credit Scoring and its
Applications*, 2002; part of the Lessmann et al. 2015 suite). The deliberate contrast to MSME: healthy EPV
(323/14 ≈ 23), 0% missing — so uncertainty is genuine SIGNAL weakness, not data insufficiency. Consumer credit →
ECOA fairness live (age `YOB` prohibited-but-permitted-under-EDDSS; `SINC` prohibited; `NKID`/`DEP`/`RES` proxy).**

> **Order (standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the decisioning
> note and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-TH020 |
| 1 | G0 | **A — Retain age under EDDSS for literature comparability** (MEDIUM) | Ravi / Data Steward | age (`YOB`) permitted under ECOA/Reg B EDDSS exception (verify no negative weight for 62+ at G4); `RES` proxy retained with disclosure; `SINC`/`NKID`/`DEP` dropped on no signal; preserves comparability with published benchmark | GEN-TH020 | b5c6ab98 |
| 2 | G1 | **C — Accept screen; log low signal as carry-forward concern** | Ravi / Model Validator | EPV ≈ 23 healthy (no sufficiency caveat, unlike MSME); screen advanced 11/14; `DOUTHP` (IV 1.48 concentration-inflated), `PHON`, `DEP` correctly dropped; weak univariate signal flagged (SIG1) to G3/G4 | b5c6ab98 | 296b3191 |
| 3 | G2 | **A — Accept attribution; retain `YOB`+`RES` per G0** | Ravi / Model Validator | 7 of 11 players confirmed over shadow bar 0.00493; `SINC` (prohibited) and `NKID` (proxy) self-excluded below bar (fairness-favourable); weakest confirmed `DOUTM` 1.4× bar — healthy, no EPV fragility | 296b3191 | 22c7d5ee |
| 4 | G3 | **C — Ratify k=5 (6 cols); escalate ~0.27 ceiling to G4** | Ravi / Model Validator | pre-registered parsimony rule → k=5 (k=4 fails loss 8.96%, k=5 passes 1.59%/p=0.776); method fixed (P8); +0.004 for k=7 is noise; discrimination ceiling ~0.27 Gini (tight CI) escalated as decisive G4 question (SIG1) | 22c7d5ee | 851bec72 |
| 5 | G4 | **A — Approve with MoC-cal** (dual) | Ravi / Risk Officer + Validator | test Gini 0.2726 (matches selection — reliable weak ceiling); 3/4 grades in Wilson CI, grade B over-optimistic (n=15); HL p=0.012–0.025 rejects calibration → PDs indicative, recalibrate before use; fairness clean, EDDSS satisfied (adverse weight on young, empirically justified) | 851bec72 | 308bd385 |
| 6 | G5 | **A — Standard config; benchmark-only framing** | Ravi / Model Owner | mandatory `DAINC` (blank→refer), incomplete_policy refer, exact WOE reason codes; MoC-cal/SIG1/grade-B/coverage + never-deploy carried to decisioning note; no cutoff/pricing; deliverables generated (6-case pack: SYN-worst forms coherently, PD 0.80) | 308bd385 | ae00f327 |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | approve as MEDIUM-tier research benchmark; method validated (clean 14→6, proxies self-removed, healthy EPV, coherent SYN-worst); weak but reliable Gini 0.272; conditions SIG1/MoC-cal/COVERAGE/AGE-REASON/DQ-AGE binding; fairness clean (EDDSS); never-deploy, recalibrate before use | ae00f327 | **d98cbee9** |

**Chain:** GEN-TH020 → b5c6ab98 → 296b3191 → 22c7d5ee → 851bec72 → 308bd385 → ae00f327 → d98cbee9.

---

## G0 — Eligibility & scope  ·  status: ✅ DECIDED — **A** (retain, EDDSS)

**Signer:** Ravi (Data Steward) · **2026-10-14** · entry_hash `b5c6ab98`

**Decision:** proceed on the **full 14-feature pool**; treat age (`YOB`) as a **permitted** predictor under the
ECOA / Regulation B §1002.6(b)(2) **empirically-derived, demonstrably-and-statistically-sound (EDDSS)** scoring
exception, subject to the binding condition that the final WOE assigns **no negative factor to applicants aged
62+** (verified at G4). Retain `RES` (proxy_risk) under the research-comparability disclosure. **Rationale:**
*retain age under EDDSS for literature comparability.*

**Fairness disposition:** consumer credit → **fairness LIVE**. The only hard protected basis present is **age**
(no race/sex field in the data). Disparate-impact (AIR, EEOC four-fifths ≥ 0.80) to be assessed on age bands at
G4 where sample permits.

### Protected / proxy inventory (SHARP Stage-0 governance layer, independently confirmed)

| Column | Tag | Basis | Fate in final model |
|---|---|---|---|
| `YOB` | **prohibited** | year of birth ⇒ age (ECOA/Reg B) | **retained** (EDDSS) — survived to final 6-col set |
| `SINC` | **prohibited** | spouse income ⇒ reveals marital status | dropped — no signal (Shapley below shadow bar) |
| `NKID` | proxy_risk | household composition / familial status | dropped — no signal |
| `DEP` | proxy_risk | household composition / familial status | dropped — failed Stage-1 screen |
| `RES` | proxy_risk | residential tenure ⇒ correlated with protected traits | **retained** with disclosure — survived to final set |
| others | permissible | income, balances, phone, dwelling value | — |

**Materiality tier:** **MEDIUM** — immaterial public research benchmark (AEGIS §3.1). Stage gates + MAC notice;
not a core capital-driving PD model.

**Honesty note (recorded):** retention of `YOB`/`RES` is a **methodological choice for literature comparability**,
not an endorsement of deploying age/tenure in a live decision. No model in this run is intended or suitable for a
live credit decision. A fairness-constrained replication excluding these features remains available on request.

### SHARP full-pool evidence available at sign time (informs G1)
- Funnel: 14 → 11 (Stage-1 screen) → 7 confirmed over shadow bar (0.00493) → parsimony **k=5 (6 columns)**.
- Selected: `DAINC`, `AES`, `YOB [prohibited]`, `grp[DHVAL+DMORT]`, `RES [proxy_risk]`.
- Selection **Gini 0.2725**, 95% CI **[0.199, 0.339]** — weak discrimination, **tight** CI (healthy EPV).
- DeLong p vs full = 0.776; relative Gini loss 1.59%; calibrated AUC 0.615, ECE 0.077.

---

## G1 — Data sufficiency  ·  status: ✅ DECIDED — **C** (accept; low-signal flag)

**Signer:** Ravi (Model Validator) · **2026-10-14** · entry_hash `296b3191`

**Decision:** accept the Stage-1 screen (**11 of 14** advanced); **declare data sufficiency met** — EPV ≈ 23
(323 events / 14 features) is well above the ≥10 rule (Peduzzi 1996) and the file is 0% missing, so **no
sufficiency caveat applies** (the deliberate contrast to MSME's EPV ≈ 1.2). **Additionally log a carry-forward
concern (SIG1):** overall univariate signal is weak. **Rationale:** *accept screen, log low signal as carry-forward
concern.*

**Screen result (dropped, all correct):**

| Dropped | Univariate IV | Basis |
|---|--:|---|
| `DOUTHP` | 1.48 | concentration-inflated (near-all-zero); fails robustness gate (binning-sensitive, MW p=0.10) — high IV ≠ signal |
| `PHON` | 0.009 | no signal |
| `DEP` | 0.004 | no signal (MW p=0.86) — also a watched proxy, clean exit |

**Survivors led by** `DAINC` (IV 0.23), `AES` (0.15), `YOB` (0.12) — all weak-to-medium; **no strong standalone
feature**, which foreshadows the low selection Gini.

> **SIG1 (carry-forward concern):** weak univariate signal across the pool. Not a data-sufficiency failure (EPV is
> healthy) but a genuine discrimination-ceiling flag. To be weighed at G3 (selection) and G4 (performance/backtest).

## G2 — Feature governance / attribution  ·  status: ✅ DECIDED — **A** (accept; retain per G0)

**Signer:** Ravi (Model Validator) · **2026-10-14** · entry_hash `22c7d5ee`

**Decision:** accept the SPVIM-style Shapley attribution with shadow-null retention. **7 of 11** players confirmed
over the shadow bar (0.00493). Retain `YOB` and `RES` per **G0 Option A**. **Rationale:** *accept attribution,
retain YOB and RES per G0.*

| Player | Shapley | × bar | Confirmed |
|---|--:|--:|:--:|
| `DAINC` | 0.0449 | 9.1× | ✅ |
| `AES` | 0.0258 | 5.2× | ✅ |
| `YOB` [prohibited] | 0.0134 | 2.7× | ✅ |
| `grp[DHVAL+DMORT]` | 0.0112 | 2.3× | ✅ |
| `RES` [proxy_risk] | 0.0108 | 2.2× | ✅ |
| `DOUTCC` | 0.0101 | 2.0× | ✅ |
| `DOUTM` | 0.0070 | 1.4× | ✅ (weakest) |
| `SINC` [prohibited], `NKID` [proxy], `DOUTL` | ≤ 0.001 | < bar | ❌ |

**Fairness note (favourable):** the two worst remaining sensitive features — `SINC` (spouse income ⇒ marital
status, *prohibited*) and `NKID` (familial proxy) — **fell below the shadow bar on their own**, so the only live
sensitive features entering selection are `YOB` and `RES`, both governed by the G0 EDDSS/disclosure decision.
**Robustness note:** weakest confirmed player sits at 1.4× the bar (healthy) — no EPV fragility (contrast MSME 1.2×).

## G3 — Model & method  ·  status: ✅ DECIDED — **C** (ratify k=5; escalate ceiling)

**Signer:** Ravi (Model Validator) · **2026-10-14** · entry_hash `851bec72`

**Decision:** ratify the parsimony selection **k=5 (6 columns)** produced by the pre-registered rule (smallest k
with DeLong p ≥ 0.05 **and** relative Gini loss ≤ 5%). Method fixed — **not re-opened** (P8). **Additionally
escalate** the discrimination-ceiling question to G4. **Rationale:** *ratify k=5, escalate the ~0.27 ceiling to G4.*

| k | +player | cols | Gini | 95% CI | rel. loss | DeLong p |
|--:|---|--:|--:|---|--:|--:|
| 4 | grp[DHVAL+DMORT] | 5 | 0.252 | [0.175, 0.325] | 8.96% ✗ | 0.207 |
| **5** | **RES** | **6** | **0.2725** | **[0.199, 0.339]** | **1.59% ✓** | **0.776 ✓** |
| 7 | DOUTM | 8 | 0.277 | [0.204, 0.354] | 0.00% | 1.000 |

k=4 fails the loss tolerance (8.96% > 5%); k=5 passes both. k=7 buys only +0.004 Gini (noise) for two more columns.

> **SIG1 → G4:** the dataset's discrimination ceiling is **~0.27 Gini (AUC ~0.635)**, unchanged by adding every
> remaining feature. The CI is **tight** [0.199, 0.339], so this is a *reliable* low number — genuine weak signal,
> not uncertainty. Whether it clears the bar is the decisive G4 question.

## G4 — Performance & calibration backtest  ·  status: ✅ DECIDED — **A** (approve, MoC-cal)

**Signers:** Ravi (Risk Officer + Model Validator — dual) · **2026-10-14** · entry_hash `308bd385`
**Backtest:** 80/20 split, seed 42; deployed scorer (`missing_governance.build_scorer`, isotonic, PD floor 0.03%);
test n=245, 65 defaults (26.5%).

**Decision:** approve with a **Margin of Conservatism (MoC-cal)** at MEDIUM tier. **Rationale:** *approve with
MoC-cal, fairness clean.*

### Discrimination (reliable, weak)
| Metric | Value |
|---|---|
| Test AUC | 0.6363 |
| **Test Gini** | **0.2726** (selection CI [0.199, 0.339]) — lands on the selection estimate ⇒ reliable low ceiling (SIG1 confirmed) |

### Per-grade calibration (3/4 in Wilson CI; omnibus HL fails)
| Grade | n | def | observed | Wilson 95% | pred PD | in CI |
|---|--:|--:|--:|---|--:|:--:|
| B | 15 | 5 | 0.333 | [0.152, 0.583] | 0.091 | ✗ (over-optimistic) |
| CCC | 100 | 16 | 0.160 | [0.101, 0.244] | 0.160 | ✅ |
| CC | 118 | 39 | 0.331 | [0.252, 0.420] | 0.309 | ✅ |
| D | 12 | 5 | 0.417 | [0.193, 0.680] | 0.667 | ✅ |

- Only **4 grades populate**, all speculative/distressed (B→D); no investment-grade applicants surface — a real
  limitation of a weak model on a 26%-default book.
- **Hosmer-Lemeshow p = 0.025 (10-bin) / 0.012 (5-bin) → rejects calibration adequacy at 5%**; ECE 0.070.
  Grade-B over-optimism drives it. Caveat: PD clustering limits HL to ~4 bins (jumpy), but it is a fail — **PDs are
  treated as indicative; recalibration required before any use (MoC-cal binding condition).**

### Fairness / EDDSS (G0 Option A condition) — **satisfied**
| Age band | n | observed def | mean pred PD |
|---|--:|--:|--:|
| <30 | 26 | 0.538 | 0.422 |
| 30–44 | 41 | 0.220 | 0.260 |
| 45–61 | 105 | 0.238 | 0.200 |
| 62+ | 73 | 0.233 | 0.263 |

- **Adverse weight falls on the young** (under-30s default 54% and are scored worst) — empirically justified. The
  **age factor does not penalise the 62+ group → EDDSS "no negative factor for elderly" condition met.**
- 62+ mildly over-predicted (+~3pp vs observed) — within noise (n=73), not age-driven.
- **AIR-on-approval degenerate** — the weak model approves no one (every PD ≥ ~9%); no favourable-outcome disparity
  to measure. Recorded as a finding, not a protected-class impact.
- Minor data-quality note: `YOB` holds a few implausible values (10, 99); negligible count.

### Binding conditions carried to G5/GF
| ID | Condition |
|---|---|
| SIG1 | discrimination ceiling ~0.27 Gini — benchmark-grade only |
| MoC-cal | HL rejects calibration → PDs **indicative**, recalibrate before any use |
| GRADE-B | grade B thin (n=15) and over-optimistic — flag in reason output |
| COVERAGE | no investment-grade band populated; model cannot identify clearly-good applicants |

## G5 — Deliverables & deployed-scorer config  ·  status: ✅ DECIDED — **A** (standard; benchmark-only)

**Signer:** Ravi (Model Owner) · **2026-10-14** · entry_hash `ae00f327`

**Decision:** standard config — mandatory `DAINC` (blank → refer), `incomplete_policy='refer'`, **exact WOE reason
codes**; no accept/decline cutoff, no pricing (institution inputs, exogenous). **Rationale:** *standard config,
benchmark-only framing.*

**Deliverables generated:** `AEGIS_TH02_CUTOFF_POLICY.md` (decisioning note), `acceptance_cases/th02.json` (6-case
pack), `SAMPLE_RUNS_TH02.md` (rendered pack).

**Acceptance-pack result (6 cases):** 4 real applicants span calibrated PD 0.03% → 99.9% (both outcomes); 2
synthetic composites — **SYN-best PD 7.41% (grade B)**, **SYN-worst PD 80.0% (grade D)**. Unlike MSME, the
**synthetic worst case forms coherently** (healthy EPV) — a clean illustration of the stress direction.

**Two honest observations recorded from the pack:**
- **AGE-REASON:** `YOB` (age) surfaces as a *principal adverse-action reason* for young applicants (R4: YOB=16;
  SYN-worst: YOB=28). The WOE *favours* the elderly (ages 52–68 all protective), so **EDDSS holds (62+ never
  penalised)**; but citing age as an adverse reason to the young is a governance flag — reinforces benchmark-only.
- **DQ-AGE:** R4 (highest-PD default) carries YOB=16, an implausible/under-contracting-age value (the `YOB`
  10–99 data-quality artifact from G4). Illustrative only.
- **COVERAGE confirmed:** even SYN-best reaches only grade B — the model surfaces no investment-grade profile.

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **GO-WITH-CONDITIONS** (MEDIUM tier)

**MAC Chair:** Ravi (CRO) · **2026-10-14** · entry_hash `d98cbee9`
**Verdict:** the TH02 model is **APPROVED as a MEDIUM-tier research benchmark (GO-WITH-CONDITIONS)**, ruled after
the per-grade backtest (G4), decisioning note and `SAMPLE_RUNS_TH02.md` were complete and visible. **Eighth
GO-WITH-CONDITIONS of the ten runs.** **Rationale:** *approve as MEDIUM-tier research benchmark.*

**What the run establishes (the positive):** on clean, healthy-EPV data SHARP ran exactly as designed — 14 → 6
columns, with shadow-null **removing every protected/proxy feature that carried no signal** (`SINC`, `NKID`, `DEP`)
on its own, tight CIs, and a **coherent synthetic worst case** (the clean contrast to MSME, where it could not
form). Fairness passes: the age factor favours the elderly (EDDSS satisfied); the adverse weight falls on the
young and is empirically justified (<30 default 54%).

**Binding conditions (carried on the approval):**

| ID | Condition | Discharge |
|---|---|---|
| SIG1 | Gini 0.272 — benchmark-grade separation only | materially stronger lawful signal |
| MoC-cal | HL rejects calibration → PDs **indicative** | recalibrate on fuller data before any use |
| COVERAGE | no investment-grade band populates | — (a property of a weak model on a 26%-default book) |
| AGE-REASON | age can surface as an adverse reason for the young | do not cite "age" in any live adverse-action notice |
| DQ-AGE | implausible `YOB` values (10, 99, 16) | clean the age field before any non-benchmark use |
| NEVER-DEPLOY | research-comparability only | not for live lending in current form |

**The publishable headline (second Gini crossover):** TH02 (Gini **0.272**) is **weaker** than MSME (0.435) yet is
**approvable** where MSME was **not** — because the verdict tracks **EPV + data quality + fairness + tier**, not
Gini. MSME failed on low EPV at HIGH tier; TH02 is a clean, fairness-passing, healthy-EPV benchmark whose only
limits are weak-but-honest signal and imperfect calibration — precisely what a MEDIUM-tier benchmark may be, with
conditions.

### Run outcome
- **Verdict:** GO-WITH-CONDITIONS at MEDIUM tier. Model approved as a research benchmark; **not** promoted to any
  live decisioning. Recalibration required before any non-benchmark use.
- **Benchmark caveat:** published Lessmann/Thomas figure **not** retrieved — no gap is claimed against our honest
  no-leakage Gini (~0.27) pending that citation.

**Chain sealed:** GEN-TH020 → b5c6ab98 → 296b3191 → 22c7d5ee → 851bec72 → 308bd385 → ae00f327 → **d98cbee9**.
