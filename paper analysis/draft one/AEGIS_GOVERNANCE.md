# AEGIS — Approval & Evidence-based Governance for Internal-ratings Systems

**Status:** Framework v1.0 (draft) · **Date:** 2026-10-12
**Relationship to SHARP:** AEGIS is the *governance lifecycle* that wraps **SHARP** (Shapley Ranking
with Parsimony, the analytical engine — see `METHODOLOGY.md`). SHARP decides *which features and which
model*; AEGIS decides *whether that model may be built, approved, and deployed, by whom, and on what
recorded evidence*. SHARP is the "how good is the model"; AEGIS is the "may we use it, and who owns that
decision."

> **Regulatory-verification status.** Every regulatory criterion in §7–§8 was checked against a primary
> or authoritative source during a dedicated verification pass (2026-10-12). Each row carries a
> **source-confidence flag**: ✅ **primary** (the regulator's own text was read) or ⚠️ **authoritative/
> commentary** (official landing page + practitioner sources; flagged for a final primary read before
> publication). No threshold here is asserted from memory.

---

## 1. Why AEGIS exists (the problem it solves)

SHARP produces a defensible *model*. It does not, by itself, produce a defensible *decision to use that
model*. A regulator (and an internal audit function) will ask questions SHARP cannot answer:

- Who decided the data was adequate, and could they have decided otherwise?
- Who chose this feature set over the alternatives, on what recorded rationale?
- Who is accountable if the model is wrong — and were they independent of the person who built it?
- Where is the evidence that each regulatory expectation was actually met, not merely claimed?

AEGIS answers these by making **each SHARP stage a governed decision gate**: the machine produces a
recommendation and a full evidence pack, a human with the right role and sufficient independence chooses
from a **closed set of genuinely viable options**, and the choice is written to a tamper-evident log.

### 1.1 The one risk AEGIS is designed against: rubber-stamping

A governance layer that always presents one real option and three strawmen is theatre. AEGIS treats
rubber-stamping as the **primary failure mode** and designs against it structurally:

1. **Options must be genuinely viable.** Each gate presents 2–4 options that are each *defensible*; the
   machine must attach data, rationale, benefits, risks, and a residual-risk statement to every one, not
   just the recommended one. If only one option is truly viable, the gate says so and routes to a higher
   authority rather than manufacturing fake alternatives.
2. **The sign-off is accountable and independent.** The approver's role, identity, and rationale are
   recorded; segregation of duties (§5) means the person who built the thing cannot be the person who
   approves it.
3. **The decision is reversible on evidence, not erasable.** The log is hash-chained (append-only); a
   reversal is a *new* recorded decision, never a quiet edit.
4. **Effective challenge is a named step, not an attitude.** Per SR 26-2, challenge requires expertise,
   independence, and the organisational standing to *effect change* — AEGIS gives the validator and the
   committee explicit authority to return a gate or veto the model.

---

## 2. Design principles

| # | Principle | Consequence in AEGIS |
|---|---|---|
| P1 | **Machine recommends, human decides, record proves.** | Every gate = recommendation + evidence pack + closed options + human sign-off + log entry. |
| P2 | **Segregation of duties.** | Developer ≠ Validator ≠ Approver (§5). Enforced at the gate, not by policy memo. |
| P3 | **Closed, viable option sets.** | No free-text "do whatever"; but also no strawmen. Each option is defensible and carries its own risk. |
| P4 | **Evidence over assertion.** | A requirement is "met" only when live system state proves it (mirrors `governance_store.regulatory_mapping`, which computes status from state, never hand-asserts it). |
| P5 | **Tamper-evidence.** | Append-only hash chain (`gov_audit_events` already implements this); reversals are new events. |
| P6 | **Risk-proportionate rigor.** | Gate depth scales with model materiality (SR 26-2's risk-based approach; EBA/CRE tiering). A low-materiality reference portfolio does not get the same ceremony as a core PD model. |
| P7 | **Primary-sourced criteria.** | Acceptance criteria cite the regulator's own text; each citation carries a confidence flag. |
| P8 | **Gates decide governance, not analytics.** | A gate's closed option set must **never** re-open a pre-registered methodology parameter (estimator mode e.g. exact/sampled, selection tolerances, shadow bar, confirm-frequency, `random_state`, CV folds). Those are fixed in `METHODOLOGY.md`, identical across every dataset, and chosen/reported once. Gates decide *scope, eligibility, fairness treatment, cutoffs, Go/No-Go* — never the analysis method. Letting a per-run gate switch the estimator is the un-reportable, dataset-dependent path-changing a research methodology must avoid. |

---

## 3. The decision-gate model

SHARP's stages become AEGIS gates **G0–GF**. Each gate has the same anatomy (§4). The gates:

| Gate | Name | SHARP stage it governs | Core question decided |
|---|---|---|---|
| **G0** | Data & Scope Adequacy | Stage 0 (data assembly, label definition); ineligible-column exclusions (leakage / identifier / constant / junk) by computable precondition — METHODOLOGY §3.7 | Is the dataset fit to build a model on? (coverage, label integrity, history length, representativeness); which columns are ineligible to model, and why? |
| **G1** | Screening | Stage 1 (IV/correlation screening, grouping); data sufficiency — EPV + Riley min-N (reported) | Which candidate features survive screening, and what is dropped and why? Is the dataset large enough (EPV + Riley)? |
| **G2** | Attribution | Stage 2 (Shapley ranking, shadow/Boruta confirmation) | Is the attribution stable and trustworthy enough to select on? |
| **G3** | Selection | Stage 3 (parsimony selection under DeLong + Gini-loss tolerance) | Which feature set is adopted — parsimonious vs full, and the trade-off accepted? |
| **G4** | Calibration & Fairness | Stage 4 (isotonic calibration, backtest, fairness gap) | Is the model well-calibrated, discriminating, and fair enough to approve? **G4 requires the per-grade realised-vs-expected calibration backtest** (CRE36.122–123) — proof the PDs are honest grade by grade, since the whole cutoff policy rests on it; on small data, flag the wide CIs and set a Margin of Conservatism. |
| **G5** | Deployment Governance | Scoring layer (missing-value gate, adverse floor, reason codes) | Are the deployment-time controls (mandatory-field gate, adverse fallback, adverse-action transparency) correctly configured? **G5 must also produce two required deliverables: (a) a decisioning note (`AEGIS_<NAME>_CUTOFF_POLICY.md`) — rating-grade risk tiers, with the accept/refer/decline threshold stated as an institution risk-appetite input that is exogenous to this methodology and NOT priced or derived here (no invented PD cutoffs, LGD or rates), and (b) an acceptance demonstration — ≥3 representative candidates scored with approve/decline decisions and reason-code reports, **persisted as a committee-facing, reproducible pack** (`SAMPLE_RUNS_<NAME>.md`, generated by `ml_models/score_acceptance_cases.py` from saved inputs in `acceptance_cases/<name>.json`). The Model Approval Committee reviews this pack at GF.** A model that outputs a PD but no governed decision and no applicant report is not deployment-complete. The acceptance demonstration is the use-test (R2) and transparency (EU AI Act Art 13 / ECOA) evidence. |
| **GF** | Final Go/No-Go | — (whole-model) | GO / GO-WITH-CONDITIONS / NO-GO, decided by the Model Approval Committee (§6). **GF is the LAST gate and is ruled only after G4's per-grade calibration backtest and G5's cutoff policy + acceptance demonstration are complete and visible** — these are inputs to Go/No-Go, never post-approval tasks. You do not approve deployment and then check whether the PDs are honest and the decisions sensible. A failing backtest or a misbehaving acceptance demo therefore becomes a NO-GO or a condition at GF. |

G0–G5 are **stage gates** (a role-holder signs each); **GF is the committee gate** (the MAC decides).
The Go/No-Go engine (§7) synthesises G0–G5 plus the regulatory checklist (§8) into the recommendation
the MAC rules on at GF.

### 3.1 Gate severity tiers

Not every gate needs a committee. Each model is assigned a **materiality tier** at G0 (HIGH / MEDIUM /
LOW), mirroring `governance_store.RISK_TIER_CADENCE` and SR 26-2's materiality logic (model exposure ×
purpose). The tier sets *who* must sign each gate and *how often* the model is revalidated:

- **HIGH** (core PD model driving capital/credit decisions): every gate signed by the named independent
  role; MAC approval at GF; quarterly revalidation.
- **MEDIUM**: stage gates signed; GF by delegated authority with MAC notification; semi-annual review.
- **LOW** (reference/onboarded portfolio, immaterial exposure): stage gates may be batch-approved by the
  Model Owner; annual review. *Lowering a tier is itself a G0 decision with a recorded rationale* — it
  cannot be used to quietly skip scrutiny.

### 3.2 Materiality-tier acceptance criteria (every threshold is externally sourced)

The tier does **not** change the analytics — the method is fixed (P8) and every metric is measured
identically across datasets. The tier sets *how high the pass-bar sits*. To keep the framework citable, **each
individual threshold is anchored to either peer-reviewed literature or supervisory guidance**; only the
*composition* (which cited bar applies at which tier) is AEGIS's own operationalization of SR 26-2's
risk-proportionate principle (R9). No numeric bar is asserted from memory.

**Per-criterion sources**

| Criterion | Threshold | Source |
|---|---|---|
| Data adequacy — events per variable (EPV) | ≥ 10 EPV (guideline, not law) | Peduzzi et al., *J. Clin. Epidemiol.* 49(12), 1996; van Smeden et al., *BMC Med. Res. Methodol.* 16, 2016; Riley et al., *Statistics in Medicine* 38, 2019 |
| Data adequacy — Riley minimum-N (**reported, not auto-reject**) | N ≥ max(B1,B3,B4): shrinkage ≥0.9, optimism ≤0.05, risk-precision ±0.05 | Riley et al., *BMJ* 368:m441, 2020; Riley et al., *Stat. Med.* 38(7), 2019; Riley, Van Calster & Collins, *Stat. Med.* 39(21), 2020 (C→R²cs). Engine `backend/riley_minsize.py`; retrospective `RILEY_SAMPLE_SIZE.md` |
| Discrimination — AUC interpretation bands | 0.7–0.8 acceptable; ≥0.8 excellent | Hosmer, Lemeshow & Sturdivant, *Applied Logistic Regression*, 3rd ed., Wiley 2013 |
| Discrimination — ROC CI & paired comparison | DeLong CI / DeLong test | DeLong, DeLong & Clarke-Pearson, *Biometrics* 44(3), 1988 |
| Calibration — goodness-of-fit | Hosmer-Lemeshow p > 0.05 | Hosmer & Lemeshow, *Commun. Stat. Theory Methods* 9(10), 1980 |
| Calibration — per-grade realised-vs-expected backtest | realised within expected CI, by grade | Basel **CRE36.122–123** |
| Conservatism under data deficiency | Margin of Conservatism, category A/B/C | EBA Guidelines on PD/LGD estimation (EBA/GL/2017/16) |
| Fairness — adverse-impact ratio | AIR ≥ 0.80 (four-fifths) | EEOC Uniform Guidelines on Employee Selection, 29 CFR 1607 |
| Use test | model must feed real credit decisions | Basel **CRE36.60** |
| Univariate IV interpretation bands | <0.02 … >0.5 | Siddiqi, *Credit Risk Scorecards*, Wiley 2006 (**book**, not a journal) |
| Risk-proportionate rigor (the tiering itself) | gate depth ∝ exposure × purpose | **SR 26-2** §II–III (Fed/OCC/FDIC, 17 Apr 2026) |

**Composition — how the cited bars apply per tier** (AEGIS design, operationalizing SR 26-2):

| | LOW | MEDIUM | HIGH |
|---|---|---|---|
| EPV ≥ 10 (Peduzzi/Riley) | waived **with** documented MoC (EBA) | preferred; if < 10 → mandatory MoC + not-for-capital | **required** |
| Riley minimum-N (BMJ m441) — *reported diagnostic* | reported | reported alongside EPV; shortfall → disclosed caveat | reported; shortfall → disclosed caveat + MoC |
| AUC floor (HLS 2013) | none (benchmark) | ≥ 0.70 (acceptable) | ≥ 0.80 (excellent) or justified |
| HL (HL 1980) + per-grade backtest (CRE36.122) | run; MoC for sparse grades | must **not** be rejected; adequate grade n | must pass; no thinly-populated (n ≲ 20) grades |
| Use test (CRE36.60) | n/a (benchmark) | required if deployed | required |
| Governance ceremony | Owner batch-sign | stage gates + MAC notice | independent validator every gate |

**Citation discipline for the paper.** Cite the *principles* to the regulators (SR 26-2, CRE36.60/.122–123,
EBA MoC, EEOC) and the *statistical bars* to the journals (Peduzzi/van Smeden/Riley, HL 1980, DeLong 1988,
HLS 2013). Present the **composition table as AEGIS's operational policy** — defensible because every cell is a
sourced bar, not an invented number. The **0.05 mean-PD-gap** deployment-monitor threshold remains operational
(not a standard) and is excluded here. All references above are recorded from domain knowledge and **must be
verified against the primary source** (author/year/clause/page) before publication, per the standing working
agreement; the Siddiqi IV bands are from a book — substitute a journal treatment (e.g. the WoE/IV usage in
Lessmann et al., *EJOR* 247(1), 2015) if journal-only sourcing is required.

---

## 4. Anatomy of a gate

Every gate G0–G5 produces one **Gate Decision Record (GDR)** with exactly these parts:

1. **Machine recommendation** — the single option SHARP/AEGIS computes as best, with its numeric basis.
2. **Full data report** — the evidence pack: all metrics, diagnostics, and tables a reviewer needs to
   second-guess the recommendation (not a summary — the actual numbers, traceable to a run).
3. **Closed option set (2–4 options).** For each option:
   - *Option* — what is chosen.
   - *Data* — the figures that support it.
   - *Rationale* — why it is defensible.
   - *Benefits* — what it buys.
   - *Risks* — what it costs or exposes.
   - *Residual-risk acceptance* — what risk remains if this option is chosen, stated so the signer is
     explicitly accepting it.
4. **Human sign-off** — role, identity, chosen option (exactly one), free-text rationale (≥20 chars,
   matching the app's `ack` minimum), timestamp.
5. **Log entry** — appended to the hash-chained decision log (`gov_audit_events`), event type
   `AEGIS_GATE_DECISION`, carrying the gate id, chosen option, signer role/id, and a hash of the GDR.

> **Anti-strawman rule.** The machine must be able to *defend each option it presents*. If it cannot
> construct a genuine rationale/benefit case for an alternative, it must not pad the set — it presents
> fewer options (minimum 1) and flags "single viable option; escalate" so the human knows the choice is
> constrained and the gate routes upward rather than down.

### 4.1 Worked example — G3 (Selection)

> **Machine recommendation:** Adopt the parsimonious set (11 of 12 features; drop `REASON`).
> **Data report:** full Stage-3 table — per-candidate Gini, DeLong p vs full set, relative Gini loss.
> **Options:**
> - **(A, recommended)** Parsimonious 11-feature set. *Data:* Gini 0.80 WOE-logistic; DeLong p=0.31 vs
>   full; rel. Gini loss 0.0%. *Benefit:* simpler, cheaper to monitor, one fewer data dependency. *Risk:*
>   marginal; `REASON` carried near-zero IV. *Residual:* accept loss of a low-signal categorical.
> - **(B)** Full 12-feature set. *Data:* Gini 0.80; identical within tolerance. *Benefit:* maximal
>   information retention. *Risk:* extra data-collection/monitoring burden for no measured gain. *Residual:*
>   accept added operational surface.
> - **(C)** Escalate — DeLong forces the full set at this n (n≈6k); if the business wants fewer than 11,
>   that is a materiality trade-off above the developer's authority. *Residual:* delay.
> **Sign-off:** Independent Model Validator selects (A), rationale recorded, event logged.

---

## 5. Roles, RACI and segregation of duties

AEGIS defines seven roles. The hard rule (P2): **the three functions Develop / Validate / Approve are
never held by the same person for the same model.** This mirrors SR 26-2 §VI, which calls out conflicts
of interest from "misalignment of incentives between different reporting lines, such as model development
and validation groups."

| Role | Owns | Independent of |
|---|---|---|
| **Data Steward** | Data lineage, quality, label integrity (G0 evidence). | — |
| **Model Developer** | Builds the model via SHARP; proposes G1–G4 recommendations. | Validator, Approver |
| **Independent Model Validator** | Effective challenge; signs G1–G4; can return a gate. | Developer |
| **Risk Officer** | Risk-appetite alignment; sets residual-risk thresholds; co-signs G4/G5. | Developer |
| **Compliance / Regulatory** | Confirms the §8 regulatory checklist; signs the regulatory view. | Developer |
| **Model Owner** | Accountable business owner; signs G5; LOW-tier GF authority. | — |
| **Model Approval Committee (MAC)** | The GF Go/No-Go decision. | Developer (chair = CRO) |

### 5.1 RACI per gate

| Gate | Responsible (proposes) | Accountable (signs) | Consulted | Informed |
|---|---|---|---|---|
| G0 Data & Scope | Data Steward | Validator (HIGH) / Owner (LOW) | Developer, Compliance | MAC |
| G1 Screening | Developer | Validator | Data Steward | Owner |
| G2 Attribution | Developer | Validator | Risk Officer | Owner |
| G3 Selection | Developer | Validator | Risk Officer, Owner | MAC |
| G4 Calibration & Fairness | Developer | Risk Officer + Validator (dual) | Compliance | MAC |
| G5 Deployment Governance | Developer | Model Owner | Risk Officer, Compliance | MAC |
| GF Final Go/No-Go | Go/No-Go engine | **MAC** | all roles | Board/Audit |

Dual sign-off at G4 (Risk Officer *and* Validator) reflects that calibration and fairness are where
model error becomes capital error and conduct risk — the two places least safe to leave to one signer.

---

## 6. Model Approval Committee (MAC)

**Purpose:** the body that rules on GF. It does not re-run the analysis; it rules on whether the
accumulated evidence and the gate decisions justify deployment.

- **Chair:** CRO (or delegate independent of model development).
- **Core members:** Independent Model Validator, Risk Officer, Compliance/Regulatory, Model Owner, a
  data/analytics lead. Internal Audit attends as observer (per SR 26-2: audit evaluates whether MRM is
  effective, and does **not** duplicate development or validation).
- **Quorum:** chair + validator + compliance + one business member; no quorum without an *independent*
  validator present.
- **Conflict of interest:** any member who developed the model recuses from the vote and is minuted as
  recused. The developer presents but does not vote.
- **Decisions:** **GO** / **GO-WITH-CONDITIONS** (deploy with named, time-bound remediations and
  heightened monitoring) / **NO-GO** (return to a specified gate with reasons).
- **Record:** every MAC decision is a hash-chained event (`AEGIS_MAC_DECISION`) with the vote, the
  conditions, and each member's recorded position.

---

## 7. The Go/No-Go recommendation engine

At GF, the engine synthesises six inputs into a recommended verdict for the MAC. It **recommends**; the
MAC **decides** (P1 holds at the top gate too).

**Inputs:**
1. **Dataset adequacy** (G0 outcome) — history length, label integrity, representativeness, coverage.
2. **Gate decisions** (G1–G5) — all signed, by the right independent roles, with no unresolved
   "escalate/single-option" flags.
3. **Risk-acceptance threshold** (Risk Officer) — are all accepted residual risks within appetite?
4. **Regulatory acceptance checklist** (§8) — each criterion SATISFIED / PARTIAL / GAP.
5. **SR 26-2 / BCBS audit expectations** — validation completeness, effective challenge evidenced,
   documentation present.
6. **New-model acceptance criteria** — the regulator-facing bar for a *first* deployment (use test,
   discriminatory power, calibration backtest, MoC).

**Recommendation logic (deterministic, auditable):**

| Condition | Engine recommendation |
|---|---|
| All gates signed + every §8 criterion SATISFIED + residual risk within appetite | **GO** |
| Gates signed + §8 has PARTIALs that are remediable + residual risk within appetite with conditions | **GO-WITH-CONDITIONS** (engine lists the conditions = the PARTIAL items) |
| Any §8 **GAP** on a must-have criterion, OR an unsigned/returned gate, OR residual risk outside appetite | **NO-GO** (engine names the blocking item and the gate to return to) |

The engine never upgrades a NO-GO to GO; a GAP on a must-have is a hard stop. The MAC may *downgrade*
(GO → conditions → NO-GO) on judgement, and must minute why — it cannot *upgrade* past a hard GAP without
first resolving the GAP (which is a new gate decision, re-synthesised).

---

## 8. Regulatory acceptance-criteria table (verified)

The spine of the Go/No-Go checklist. Each row is a criterion the model must satisfy before GF, the
primary citation, and the evidence AEGIS looks for. **Confidence flags:** ✅ primary text read · ⚠️
authoritative/commentary, flagged for final primary confirmation.

| # | Acceptance criterion | Framework & citation | Conf. | Evidence AEGIS requires | Gate |
|---|---|---|---|---|---|
| R1 | **PD data history ≥ 5 years** for at least one source (LGD ≥7yr wholesale / ≥5yr retail; EAD similar). | Basel IRB **CRE36.79** | ✅ | G0 data report states observation-window length per source. | G0 |
| R2 | **Use test** — ratings & PD/loss estimates play an "essential role" in credit approval, risk management, capital allocation and governance; a model built *only* to qualify for IRB is "not acceptable." | Basel IRB **CRE36.60** | ✅ | Evidence the model feeds real credit decisions (RM accept/reject flow, pricing), not capital-only. | G5/GF |
| R3 | **Meaningful risk differentiation** — rating system ranks and quantifies risk; meaningful distribution across grades, no excessive concentration. | Basel IRB **CRE36** (rating-structure clauses) | ✅ | G3/G4: discrimination (Gini/AUC), grade distribution, concentration check. | G3,G4 |
| R4 | **Calibration backtest** — regularly compare realised default rates with estimated PDs per grade; realised within the expected range. | Basel IRB **CRE36.122–123** | ✅ | G4: calibration curve + per-grade realised-vs-expected backtest; ongoing-monitoring plan. | G4 |
| R5 | **Override governance** — documented policy for overriding model output; monitoring of overrides; written guidance when combining model + human judgement. | Basel IRB **CRE36 §5 (overrides)** | ✅ | G5: override policy documented; RM override rate tracked (`rm_outcomes`). | G5 |
| R6 | **Margin of Conservatism** — add MoC for (A) identified data/methodological deficiencies, (B) relevant changes to underwriting/risk-appetite/recovery policies & other uncertainty, (C) general estimation error; final MoC = sum(A,B,C). | **EBA/GL/2017/16 §4.4, ¶36–43** | ✅ | G0/G4: deficiencies classified A/B/C; MoC quantified and documented per category. | G0,G4 |
| R7 | **Independent validation / effective challenge** — critical analysis by objective experts with expertise, independence, and standing to effect change; quality judged by *rigor of review, not org-chart position*; components: conceptual soundness, outcomes analysis, ongoing monitoring. | **SR 26-2** (§V), Apr 17 2026 (supersedes SR 11-7 & SR 21-8) | ✅ | Six-pillar sign-off complete by a validator independent of the developer (§5); MAC includes independent validator. | G1–G4, GF |
| R8 | **Model governance & accountability** — clear roles, accountability, conflict-of-interest management (dev vs validation reporting lines); policies & controls; internal audit evaluates MRM without duplicating it. | **SR 26-2** (§VI) | ✅ | RACI (§5) enforced; MAC constituted; audit observer role. | GF |
| R9 | **Risk-proportionate rigor** — MRM tailored to model materiality (exposure × purpose) and org size/complexity; most relevant >$30bn assets; GenAI/agentic AI out of scope. | **SR 26-2** (§II–III) | ✅ | G0 materiality tiering (§3.1) drives gate depth & revalidation cadence. | G0 |
| R10 | **Data governance / aggregation quality** — accuracy & integrity (P3), completeness (P4), timeliness (P5); lineage & auditability. | **BCBS 239** (Jan 2013), P3–P5 | ⚠️ | G0: Data Steward lineage + quality report; completeness/timeliness checks. | G0 |
| R11 | **Model risk management principles** — model identification/classification, governance, development-implementation-use, independent validation, risk mitigants. | **PRA SS1/23** (eff. 17 May 2024; amended Apr 2026, LIAF01/26 — expectations are **not** conditions for internal-model approval) | ⚠️ | Whole-lifecycle coverage mapped to the five principles. | all |
| R12 | **High-risk AI — risk management, data governance, logging, transparency, human oversight.** Credit scoring/creditworthiness of natural persons = high-risk. | **EU AI Act**, Annex III §5(b); Arts 9, 10, 12, 13, 14 | ⚠️ | Arts 12/13/14: audit log (`gov_audit_events`), SHAP + reason codes + adverse-action report, RM human-in-the-loop with anti-automation-bias. | G5,GF |
| R13 | **AI transparency / human oversight operability** — overseers can understand output, avoid automation bias, and decline/intervene/halt. | **EU AI Act** Art 14 | ⚠️ | RM accept/reject is a real, recorded intervention point; override path exists. | G5 |
| R14 | **Adverse-action reasons** — specific principal reasons for denial. | **ECOA / Reg B** (US) | ⚠️ | Reason codes + `report-applicant.html`. | G5 |

**Timeline note (R12):** the EU AI Act **high-risk (Annex III) obligations deadline was moved from
2 Aug 2026 to 2 December 2027** by the "Digital Omnibus" (Reg (EU) 2026/1744, in force 27 Jul 2026);
Art 50 transparency duties still apply from 2 Aug 2026. ⚠️ *Confirm on EUR-Lex before publication.*

**Must-have vs should-have.** R1–R9 (Basel + SR 26-2 + EBA) are **must-haves** — a GAP is a hard NO-GO.
R10–R14 are **context-dependent**: must-have where the model is in that jurisdiction's scope, else
tracked as applicable best practice. The MAC records which regime(s) bind a given model at G0.

### 8.1 Primary-source provenance

| Source | How verified (2026-10-12) |
|---|---|
| Basel CRE36 | BIS chapter PDF extracted locally (`tool-results/cre.txt`); clauses .60/.79/.122–123/rating-structure/§5 read. |
| SR 26-2 | Fed landing page + **attachment SR2602a1.pdf read in full** (§I–VI): non-binding, >$30bn relevance, GenAI carve-out (fn 3), three validation components (§V), independence decoupled from org chart (p.8). |
| EBA/GL/2017/16 | Guidelines PDF extracted; §4.4 ¶36–43 read — Category A/B/C definitions verbatim. |
| BCBS 239 | Standard (Jan 2013) — principle structure from BIS; ⚠️ P3–P5 wording not re-read this pass. |
| PRA SS1/23 | BoE publication page + Apr 2026 amendment (LIAF01/26); ⚠️ five-principle wording from official summary. |
| EU AI Act | Annex III §5(b) + Arts 9/10/12/13/14; Digital Omnibus delay — ⚠️ practitioner sources, EUR-Lex confirmation pending. |

---

## 9. Mapping onto the existing application

AEGIS is **not** a new subsystem — it is a lifecycle on top of infrastructure the app already has in
`backend/governance_store.py`. The mapping:

| AEGIS concept | Existing app mechanism |
|---|---|
| Hash-chained decision log | `gov_audit_events` + `append_audit_event()` / `verify_chain()` (already append-only, hash-linked). |
| Gate sign-off (≥20-char rationale) | `gov_alerts` ack rule (≥20 chars) + `sign_off()`; AEGIS adds event type `AEGIS_GATE_DECISION`. |
| Validation evidence (R7) | **Six-pillar sign-off** (`PILLARS`: Conceptual Soundness, Data Quality Assessment, Process Verification, Outcomes Analysis, Ongoing Monitoring, Governance Framework) — maps 1:1 to SR 26-2's validation components + governance. |
| Regulatory checklist (§8) | `regulatory_mapping()` — already computes SATISFIED/PARTIAL/GAP **from live state**, never hand-asserted (exactly P4). AEGIS extends its requirement list to R1–R14. |
| Ongoing monitoring (R4) | `drift_monitor.py` (PSI>0.25, AUC drop>5%, fairness gap>0.05) + KPI snapshots within 48h. |
| Materiality tiering (§3.1) | `RISK_TIER_CADENCE` (HIGH/MEDIUM/LOW review cadence). |
| Per-model documentation | DB-backed wiki (`WIKI_PROSE_FIELDS`: purpose, assumptions, validation_methods, data_lineage, escalation_rules, review_cadence, regulatory_references) with version history. |
| Promotion gate (GF deployment control) | `trainer.run_training()` challenger-vs-champion gate + `force_promote()` (admin-authed, rationale required). |
| Deployment governance (G5) | `ml_models/missing_governance.py` (mandatory gate + adverse floor), SHAP + reason codes + `report-applicant.html`. |

### 9.1 Applied change: SR 11-7 → SR 26-2

SR 11-7 was **superseded by SR 26-2 on 17 Apr 2026**, so the app's references to the rescinded letter were
updated (2026-10-12). The *substance* carries forward (three validation components, effective challenge),
so this was primarily a citation correctness fix — the regulatory view should not cite a rescinded letter.
Changed:

- `backend/governance_store.py` — `regulatory_mapping()` requirement `frameworks` lists (`'SR 11-7'` →
  `'SR 26-2'`), the `regulatory_references` wiki default, the module docstring and the function docstring.
- `app.py`, `public/governance/index.html`, `public/governance/story.html`, `public/index.html` — all
  user-facing "SR 11-7" labels/prose updated to SR 26-2 (with a "superseded SR 11-7" note where helpful).
- `CLAUDE.md` and `AGENTS.md` — Model Governance section updated.

Remaining literal "SR 11-7" occurrences in the codebase are all deliberate "superseded SR 11-7" context,
not active citations.

---

## 10. Residual risks & limitations of AEGIS itself

1. **Governance cannot fix a bad model** — AEGIS makes the *decision* defensible and accountable; it does
   not make a poorly-fit model good. SHARP's own limitations (`METHODOLOGY.md §9`) still bind.
2. **Option quality depends on the engine's honesty** — the anti-strawman rule (§4) is a design intent;
   it must be audited. A reviewer should periodically test whether presented "alternatives" were real.
3. **Independence is organisational, not just logical** — segregation of duties assumes the roles are
   genuinely staffed by different, appropriately-empowered people. In a small team this is the hardest
   part to satisfy honestly; SR 26-2's "rigor over org-chart" framing helps but does not remove the need.
4. **Commentary-level citations remain** (R10–R14): BCBS 239 wording, PRA SS1/23 principle text, and the
   EU AI Act Omnibus dates should get a final primary read (EUR-Lex / BoE / BIS) before this framework is
   cited in the paper.
5. **AEGIS is a framework, not a deployed workflow** — the gate records, MAC minutes, and option engine
   described here are specified, not yet all implemented as code paths.

---

## Appendix A — Source links

- Basel CRE36: https://www.bis.org/basel_framework/chapter/CRE/36.htm
- SR 26-2 (letter + attachment SR2602a1.pdf): https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm
- EBA/GL/2017/16: https://www.eba.europa.eu/documents/10180/2033363/6b062012-45d6-4655-af04-801d26493ed0/
- BCBS 239: https://www.bis.org/publ/bcbs239.htm
- PRA SS1/23: https://www.bankofengland.co.uk/prudential-regulation/publication/2023/may/model-risk-management-principles-for-banks-ss
- EU AI Act (Annex III, high-risk): consolidated text on EUR-Lex (confirm Digital Omnibus Reg (EU) 2026/1744 dates)
