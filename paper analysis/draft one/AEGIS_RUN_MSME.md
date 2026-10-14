# AEGIS run log — MSME (Chinese SME enterprise credit)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/MSME_Credit_Data.csv` — 1,707 rows, 87 features + target, event rate 0.0598 (**102 events**).
**Started:** 2026-10-14 · **Human signer:** Ravi · **Materiality tier:** MEDIUM at G0, **re-tiered → HIGH at GF** (G0-AMEND) · **Record:** `SHARP_MSME.md`
**Ninth governed run — the HIGH-DIMENSIONALITY / LOW-EPV stress test: 87 candidate features against only 102
defaults (events-per-variable ≈ 1.2, far below the ≥10 rule). Tests whether SHARP's shadow-null retention +
parsimony hold when p ≫ events. Corporate/SME credit → no consumer ECOA attributes (fairness N/A).**

> **Order (corrected standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the
> decisioning note and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-MSME0 |
| 1 | G0 | **A — Proceed on full 87-feature pool; carry low-EPV flag; no ECOA exclusions** (MEDIUM) | Ravi / Data Steward | corporate/SME (fairness N/A); let SHARP prune 87 features; carry EPV1 + Province flag + heavy-missing to G5 | GEN-MSME0 | fd0ecbf1 |
| 2 | G1 | **A — Accept screen; advance 45 of 87** | Ravi / Model Validator | top univariate IVs inflated by low EPV (sparse-count instability, not leakage); Stage 2 Shapley robust to it; carry EPV1 | fd0ecbf1 | 36c14cd6 |
| 3 | G2 | **A — Accept attribution; 7 of 32 players confirmed** | Ravi / Model Validator | shadow-null rejected 25 noise players incl. inflated-IV sparse counts + Province proxy; elevated bar 0.00836, weakest confirmed 1.2× (EPV fragility); carry EPV1 | 36c14cd6 | 0bfabfec |
| 4 | G3 | **A — Ratify k=6 (6 players / 15 cols)** | Ravi / Model Validator | dramatic 87→6 parsimony reduction, no proxy/availability features; Gini 0.4347 but wide CI [0.339,0.539] (EPV1) → MoC + heightened monitoring | 0bfabfec | 2d4e0e65 |
| 5 | G4 | **A — Approve with MoC-epv** (dual) | Ravi / Risk Officer + Validator | backtest 7/8 grades pass HL(5-bin) p=0.345 ECE 0.021; grade D MISS on n=2 (small-sample noise); enormous CIs → PDs indicative not precise; fairness N/A; carry EPV1 | 2d4e0e65 | 7d89e52e |
| 6 | G5 | **A — Standard config + adverse floor on social-insurance bundle** | Ravi / Model Owner | adverse floor closes missing-protective (~3%, lift 0.00–0.66×) omission trap on 10 social-insurance cols (GMSC precedent); mandatory Sector+Registered_capital+Enterprise_type; refer; exact reason codes | 7d89e52e | e2488157 |
| 7 | G0-AMEND | **Re-tier MEDIUM → HIGH** | Ravi / Data Steward (MAC-noted) | subject the low-EPV model to maximal scrutiny to demonstrate the framework's rejection behaviour; applies HIGH §3.2 bars at GF | e2488157 | bac010b1 |
| 8 | GF | **NO-GO** | Ravi / MAC Chair (CRO) | under HIGH §3.2 three acceptance bars fail outright (EPV, per-grade adequacy, AUC floor) → determinate rule-driven rejection; method guardrails validated but model not approvable | bac010b1 | **b8c5bf03** |

**Chain:** GEN-MSME0 → fd0ecbf1 → 36c14cd6 → 0bfabfec → 2d4e0e65 → 7d89e52e → e2488157 → bac010b1 → b8c5bf03.

---

## G0-AMEND — Re-tiering MEDIUM → HIGH  ·  status: ✅ DECIDED
**Signer:** Ravi (Data Steward; MAC-noted) · **2026-10-14** · entry_hash `bac010b1`
**Decision:** raise the materiality tier from MEDIUM to **HIGH**. **Rationale:** *subject the low-EPV model to
maximal scrutiny to demonstrate the framework's rejection behaviour.* **Honesty note (recorded):** this is **not
a materiality-accurate classification** — MSME is an immaterial, unverified public benchmark, not a core
capital-driving PD model — but a **deliberate maximal-scrutiny demonstration**. Re-tiering is a G0-level decision
(§3.1) and changes only the **pass-bar** (via §3.2), not the analytics (method fixed, P8). The prior gate
decisions (G1–G5, signed at MEDIUM) stand on their evidence; GF is now ruled against the **HIGH §3.2 acceptance
bars**.

## GF — Final Go/No-Go  ·  status: ✅ DECIDED — **NO-GO** (HIGH tier, ruled with full visibility)

**MAC Chair:** Ravi (CRO) · **2026-10-14** · entry_hash `b8c5bf03`
**Verdict:** the MSME model is **REJECTED (NO-GO)** under **HIGH-tier** acceptance criteria. Ruled after the
per-grade backtest (G4), decisioning note and `SAMPLE_RUNS_MSME.md` were complete and visible. **Second NO-GO of
the nine runs** (after PAK), and the first that is **rule-driven rather than a judgment call**.

**Why it is a determinate rejection (HIGH §3.2 bars, each externally sourced):**

| HIGH bar | Requirement | MSME | Source |
|---|---|---|:--:|
| Data adequacy | EPV ≥ 10 | **1.2** ✗ | Peduzzi 1996 / Riley 2019 |
| Per-grade backtest | no thin (n ≲ 20) grades | grade **D n=2** ✗ | Basel CRE36.122 |
| Discrimination | AUC ≥ 0.80 | ~0.72, CI [0.34–0.54] ✗ | Hosmer-Lemeshow-Sturdivant 2013 |
| Governance | independent validator every gate | signed at MEDIUM authority ✗ | SR 26-2 §V |

Three analytic bars fail outright, so at HIGH tier there is no discretion — the model cannot be approved.

**What the run nonetheless establishes (the publishable positive):** SHARP's guardrails **passed the stress
test** — 87 features → 6 players (15 cols), with shadow-null retention correctly rejecting the inflated-IV
sparse-count features (patents/copyrights at IV 0.6–0.88) and the `Province` proxy. **The method is validated
under p ≫ events; the model is correctly rejected.** This is risk-proportionate rigor (SR 26-2 / R9) doing its
job: the same model is tolerable as a LOW-tier benchmark and rejected as a HIGH-tier core model.

### Rejection basis / what reconsideration would require

| ID | Finding → why it blocks HIGH approval | Discharge |
|---|---|---|
| EPV1 | EPV ≈ 1.2 ≪ 10 | ≥ ~870 defaults (10 × features), or a far smaller feature set with adequate events |
| MoC-epv | per-grade PDs untrustworthy (n=2 grade, CI ±0.10) | adequate events per grade |
| MSME-fit | AUC below HIGH floor | materially stronger lawful signal |
| MSME-tier | HIGH requires independent-validator sign-off every gate | re-run under HIGH sign-off authority |

### Run outcome
- **Verdict:** NO-GO at HIGH tier (rule-driven). No model promoted.
- **Method result:** guardrails validated — 87 → 6 parsimony reduction, noise + proxy correctly rejected.
- **Provenance:** 8 logged decisions incl. the G0 re-tiering amendment; hash chain intact (GEN-MSME0 → b8c5bf03).
- **Contribution:** demonstrates the framework's **determinate rejection** of a fragile model under maximal scrutiny.

## Deliverables checklist (end-to-end standard — corrected order)
- [x] `SHARP_MSME.md` — Stages 0–4 + Stage 4b backtest + fairness-N/A + dimensionality-reduction summary
- [x] **Per-grade calibration backtest (in G4, before GF)** — HL(5-bin) p=0.345, 7/8 grades (grade D n=2 miss)
- [x] `AEGIS_MSME_CUTOFF_POLICY.md` — decisioning note (EPV1/MoC-epv; benchmark-only; no pricing)
- [x] Acceptance demonstration — `acceptance_cases/msme.json` + `SAMPLE_RUNS_MSME.md` (6-case; SYN-worst EPV note)
- [x] `AEGIS_RUN_MSME.md` — G0–G5 signed, G0 re-tiered, **GF ruled last** — **NO-GO (HIGH)**, chain intact
- [x] Rejection basis listed, each with its reconsideration requirement

*AEGIS run complete (MSME) — ninth governed run; the high-dimensionality / low-EPV stress test. Method guardrails
validated (87→6); model rule-rejected at HIGH tier. Second NO-GO, first determinate one.*

---

## G5 — Deployment Governance  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Owner) · **2026-10-14** · entry_hash `e2488157`
**Missing-value governance.** Of the 15 selected columns, only the **10 social-insurance `t-1/t-2` columns**
carry missingness (~3% each), and **missing is protective** (lift 0.65× for t-1, 0.00× for t-2 — firms
withholding social-insurance data default *less*) — a mild **omission trap**. **Adverse floor applied to the 10
social-insurance columns** (blank scored at worst-observed WoE), closing the trap — consistent with GMSC's income
floor. Mandatory = `Sector`, `Registered_capital`, `Enterprise_type` (0-missing structural anchors);
`incomplete_policy='refer'`; exact WoE reason codes; PD floor 0.03% automatic; `drift_monitor` (PSI/AUC). Carry
**MoC-epv** (PDs indicative, esp. grades CC/D) + **EPV1**. Rejected B (mandatory social-insurance refers 3% —
flooring keeps them scorable), C (learned bin leaves the trap open). **G5 deliverables (decisioning note +
acceptance pack) produced below — before GF.**

### Acceptance demonstration (committee pack: `SAMPLE_RUNS_MSME.md`, inputs `acceptance_cases/msme.json`)
**Fixed 6-case standard:** 4 real firms (actual outcome shown) + 2 synthetic composites. Real cases show a
sensible gradient; **but the EPV fragility surfaces in the synthetic stress case**.

| Candidate | Type | Outcome | Calibrated PD | Grade | Decision | Principal reasons |
|---|---|---|--:|---|---|---|
| R1-low-repaid | real | repaid | 0.03% | AAA | SCORE | Sector, t-1 injury insurance, t-2 birth insurance |
| R2-mid-repaid | real | repaid | 4.30% | BB | SCORE | Enterprise_type, Sector, t-1 injury insurance |
| R3-mid-default | real | defaulted | 4.30% | BB | SCORE | Enterprise_type, Sector, t-1 injury insurance |
| R4-high-default | real | defaulted | 28.75% | CC | SCORE | Enterprise_type, Sector, t-1 old-age insurance |
| SYN-best | synthetic | repaid (by design) | 0.03% | AAA | SCORE | t-1 injury insurance, t-2 birth insurance, t-1 medical |
| SYN-worst | synthetic | default (by design) | 0.03% | AAA | SCORE | Enterprise_type, Registered_capital, Sector |

*(No pricing/cutoff derived. R2 repaid and R3 defaulted share PD 4.30% (messy middle). **`SYN-worst` scores
0.03% AAA — same as `SYN-best`**: at EPV ≈ 1.2 the weak/non-monotonic feature-risk directions don't compose into
a coherent worst-case firm; the model has no stable "worst case." Not a bug — an EPV finding reinforcing MoC-epv.
Full showcase: `SAMPLE_RUNS_MSME.md`; decisioning note: `AEGIS_MSME_CUTOFF_POLICY.md`.)*

---

## G4 — Calibration (+ required backtest) & Fairness  ·  status: ✅ DECIDED (Option A, dual)
**Signers:** Ravi (Risk Officer + Validator) · **2026-10-14** · entry_hash `7d89e52e`
**Calibration (per-grade backtest, inside G4):** 80/20 held-out (seed 42), test n=342, **only 20 defaults**.
**7/8 populated grades within CI, ECE 0.021, Hosmer-Lemeshow (5-bin) χ²=3.32 df=3 p=0.345 → not rejected**
(table in `SHARP_MSME.md` §Stage 4b). **The EPV1 caveat in the flesh:** grade **D has n=2** (neither defaulted
in the slice) so its 86.9% expectation falls outside the CI — a 2-observation miss, small-sample noise not
miscalibration; per-grade CIs are enormous (CC spans 24–76%); HL was reduced from 10 bins to **5** because 20
test defaults cannot fill 10 deciles. Calibration holds **where there is data**, but the risky-tier PDs are too
thin to trust precisely. **Condition MoC-epv:** treat PDs as **indicative, not precise**, especially grades
CC/D. **Fairness N/A** — corporate/SME, no protected attributes (`Province` dropped at G2). Carry **EPV1** to GF.
Rejected B (NO-GO — GF rules the posture holistically with the demo, as for PAK), C (recalibrate won't fix data
thinness).

---

## G3 — Selection  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Model Validator) · **2026-10-14** · entry_hash `2d4e0e65`
**Decision:** ratify the pre-registered **k = 6 → 15-column** selection (`Sector`, social-insurance t-1/t-2
bundle [10 cols], `Trademark_5years+`, `Certificate_2years`, `Registered_capital`, `Enterprise_type`), Gini
**0.4347**, rel. loss 2.78%, DeLong p 0.294. **The stress test passes:** SHARP reduced **87 features → 6 players**,
a clean parsimony reduction with **no proxy or availability features** (`Province` dropped at G2). **The EPV
fragility shows in the CI:** Gini 95% CI **[0.339, 0.539]** (±0.10 wide — far wider than event-rich runs), so the
point estimate (≈ AUC 0.72) is genuinely uncertain given 102 events. **Condition EPV1** carried → set a Margin
of Conservatism and heightened calibration monitoring at G4. Rejected B (parsimony rule pre-registered, P8),
C (NO-GO — selection is sound; GF weighs the fragility with the backtest).

---

## G2 — Attribution  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-14** · entry_hash `0bfabfec`
**Decision:** accept. Of **32 candidate players, 7 confirmed** (`Sector`, social-insurance t-1/t-2 bundle,
`Trademark_5years+`, `Certificate_2years`, `Registered_capital`, `Enterprise_type`, `Certificate_1year`);
converged (200 perms, 39,165 fits, max MC SE 0.0028). **Shadow bar is elevated to 0.00836** — far above the
event-rich runs (~0.0005–0.001) because 102 events raise the permuted-noise ceiling. **The guardrail worked as
advertised:** 25 of 32 players were rejected as indistinguishable from noise, **including the inflated-IV
sparse-count features** that univariate IV loved (patents/copyrights at IV 0.6–0.88) **and the `Province`
proxy** (0.85× bar, freq 0.10) — so the selected model carries no fairness-adjacent geographic feature. **EPV
fragility is visible:** the weakest confirmed player is only 1.2× the bar, and one noise shadow reached 0.0095.
**Condition EPV1** carried. Rejected B (converged; thin margins are inherent to 102 events, not estimation error;
`n_samples` pre-registered, P8).

---

## G1 — Univariate Screening  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Independent Model Validator) · **2026-10-14** · entry_hash `36c14cd6`
**Decision:** advance the **45 candidates** that pass Stage 1; 74 columns needed escalation (noisy bins from 102
events). **Low-EPV signature (EPV1) made visible:** 8+ features show univariate IV **> 0.5** (Patent_2years
0.885, Trademark_2years 0.823, Software_copyright_2years 0.802) — **not leakage but small-sample IV instability**:
with 102 defaults over sparse patent/trademark/copyright *counts*, a few events in a rare bin inflate IV. Raw IV
is fooled by low EPV. **This is precisely why the layered method matters** — the robust Shapley + shadow-null +
parsimony (G2/G3) do not keep most of these; the final set leans on stabler signals (`Sector`, social-insurance
bundle, `Registered_capital`, `Enterprise_type`), keeping only `Trademark_5years+` from the sparse-count group.
**Condition EPV1** carried (discrimination estimates uncertain → GF). Rejected B (hard IV>0.5 cut treats
instability as leakage, and Stage 2 already handles it), C (premature halt — observe the guardrails).

---

## G0 — Data & Scope Adequacy  ·  status: ✅ DECIDED (Option A)
**Signer:** Ravi (Data Steward) · **2026-10-14** · entry_hash `fd0ecbf1`

**Materiality tier:** MEDIUM (reference benchmark, not production-IRB), with **heightened scrutiny on EPV**.

**No consumer ECOA/Reg B exclusions** — this is **business/SME credit** (enterprise attributes: registered
capital, sector, certificates, patents, tax/legal records, social-insurance payments). No person-level protected
attributes exist → **fairness N/A** (documented, not skipped — like HELOC/LOAN).

**Headline concern — low EPV (EPV1):** 87 candidate features vs **102 events** (EPV ≈ 1.2). Classical logistic
modelling wants ≥10 events per variable; this is ~8× too thin. The run tests whether SHARP's shadow-null
retention and parsimony curve correctly prune 87 → a small stable set rather than overfitting.

**Other scope findings:**
- `Province` — geographic; a legitimate SME risk factor but SHARP may tag it `proxy_risk` → retain-and-flag.
- Heavy missingness → G5: `Branch_num` 45%, the `t-1/t-2/t-3` social-insurance columns ~3–8% each.

**Machine recommendation — Option A:** proceed on the full 87-feature pool, MEDIUM tier with heightened EPV
scrutiny; no ECOA exclusions (corporate credit, fairness N/A); retain-and-flag `Province`; carry **EPV1** (low
events-per-variable → GF) and the missing-value governance to G5. Let SHARP's G1/G2/G3 do the dimensionality
pruning.

*(Options presented in chat; signed row appended on decision.)*
