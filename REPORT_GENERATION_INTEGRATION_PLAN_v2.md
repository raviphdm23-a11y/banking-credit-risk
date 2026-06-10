# Report Generation Integration Plan — v2 (Expert Revision)
## Banking Credit Risk Calculator — Phase 6

**Date:** June 8, 2026
**Revises:** `REPORT_GENERATION_INTEGRATION_PLAN.md` (v1)
**Lens:** Credit risk methodology + banking operations + UX + borrower onboarding
**Status:** Strategic design — decisions flagged before build

---

## 0. What changed from v1, and why

v1 was a faithful port of `case_report_builder.py`. But that source file is a **consumer financial-advisory** tool — warm "note from your advisor," wellness language, personal recourse coaching. Our application is a **Basel III bank-internal credit engine**: it computes PD → correlation R → maturity adjustment → AIRB risk weight, LGD from seniority/collateral, RWA, regulatory capital at 8%, and SA risk weights from external ratings. Porting a consumer tool wholesale creates an audience and tone mismatch that would undermine credibility with both auditors and credit officers.

The five structural problems in v1, and how v2 fixes them:

| # | v1 problem | v2 fix |
|---|-----------|--------|
| 1 | **One report, undefined reader.** Mixes auditor-grade Basel math with consumer coaching. | **Two lenses, one engine** (§2): an *Underwriter Report* (internal, decision + audit) and an *Applicant Letter* (external, adverse-action + recourse). |
| 2 | **Explainability framed as a "nice to have."** | Reframed as a **regulatory obligation** (§4): reason codes / adverse-action, model-risk governance, right-to-explanation. The recourse feature is how we *comply*, not decoration. |
| 3 | **Naïve methodology.** ±5/10/15% one-feature perturbations; hardcoded `±8pp` uncertainty; "ensemble" language with one model; arbitrary gauge bands. | **Defensible methods** (§5): SHAP reason codes, *genuine* uncertainty from RandomForest tree variance, PD mapped to an **internal rating masterscale**, and the report anchored to **Expected Loss** and **risk-based pricing** the app already has the inputs for. |
| 4 | **Report ≠ decision.** v1 outputs metrics, never a recommendation. | The report **drives a decision** (§3): Approve / Refer / Decline, with policy knockouts, affordability (DSCR), and EL/pricing — organised on the **Five C's** narrative the data dictionary already uses. |
| 5 | **Ephemeral, unsecured artifacts.** matplotlib-SVG in the request path; JSON cached to disk that GCP wipes on restart; admin password `1234` guarding real borrower financials. | **Durable, governed, performant** (§8): immutable versioned reports in GCS/DB for audit reproducibility, client-side charting (no matplotlib in request path), real auth and PII handling. |

Everything genuinely good in v1 is kept: the risk gauge, peer feature-health, counterfactual recourse, and the three-pathway structure — but each is upgraded to banking standard below.

---

## 1. The single most important decision

**Who is the primary reader of the first version we build?** This is a genuine fork that changes tone, content, and compliance scope. The expert answer is *both, eventually*, from one shared findings object — but we should build one lens first.

- **Underwriter Report (internal) — recommended first.** It matches what the engine already produces, has the clearest near-term user (a credit officer / the user as analyst), and carries lower regulatory exposure than sending letters to real applicants. The Applicant Letter is then a *projection* of the same findings with different framing and disclosure controls.

Treat §3–§6 as the underwriter lens; §7 covers the applicant projection and onboarding journey.

---

## 2. Architecture: two lenses, one engine

```
                    ┌─────────────────────────────┐
   Borrower input → │   ASSESSMENT ENGINE         │  (deterministic, audited)
                    │   - PD (ML) + tree variance │
                    │   - LGD, EAD, R, M, RWA, cap│  ← reuses backend/calculations.py
                    │   - SHAP attribution        │
                    │   - rating grade (masterscale)
                    │   - Expected Loss, pricing  │
                    │   - peer comparison         │
                    │   - counterfactual recourse │
                    │   - policy knockouts        │
                    └──────────────┬──────────────┘
                                   │  one immutable "findings" object (versioned, hashed)
                         ┌─────────┴─────────┐
                         ▼                   ▼
              UNDERWRITER REPORT      APPLICANT LETTER
              (internal, full)        (external, adverse-action + recourse)
              - decision + rationale  - principal reasons (reason codes)
              - Five C's evidence     - top 3 actionable improvements
              - EL, RWA, capital,     - encouraging, plain-language
                pricing               - no internal scores / model internals
              - audit trail, override - regulator-aligned disclosures
```

**Why one engine:** the applicant's "reasons you were declined" and the underwriter's "drivers of the score" must be *the same numbers*. If they diverge, the bank has a fair-lending problem. Generating both from one hashed findings object guarantees consistency and reproducibility.

---

## 3. The report must produce a decision, not just metrics

A credit report that ends at "PD = 45%" is unfinished. Credit officers think in a decision funnel. The engine should walk it explicitly and show its work:

1. **Policy knockouts (hard rules, pre-model).** Independent of the score: e.g., active default flag, missing KYC, sector on exclusion list, exposure over delegated authority. A knockout = automatic Decline/Refer regardless of PD. *Banks decline on policy far more than on score; the model is the second gate, not the first.*
2. **PD → internal rating grade.** Map model PD to a **masterscale** (e.g., 12 grades AAA→D) so the output speaks the bank's language and ties to the SA rating table already in `calculations.py`. A grade is auditable and stable; a raw 45.3% invites false precision.
3. **Affordability / capacity.** Surface DSCR / interest-coverage explicitly — a profitable borrower who still can't service the proposed instalment should Refer even at low PD.
4. **Expected Loss, the money number.** `EL = PD × LGD × EAD`. The app already computes all three. EL in ₹ is what a credit committee actually debates — lead with it, not with PD.
5. **Risk-based pricing (indicative).** Given EL%, RWA and the 8% capital charge, show an **indicative spread/rate** that covers expected loss + cost of capital. This converts risk into the business decision the relationship manager needs.
6. **Recommendation + confidence.** Approve / Approve-with-conditions / Refer-to-committee / Decline, with a confidence band derived from model uncertainty (§5) and proximity to the cutoff.

The report's executive band shows, in one line: **Grade · PD · EL (₹) · Indicative rate · Recommendation** — then the rest of the document justifies it.

---

## 4. Regulatory & governance backbone (new, non-negotiable)

This is the section v1 omitted entirely and the one a real bank would check first.

- **Adverse-action / reason codes.** If credit is declined or priced up, regulation (RBI Fair Practices Code; analogous to ECOA/FCRA, EU CRD, GDPR Art. 22 right-to-explanation, India DPDP Act) generally requires the **principal reasons**. Our SHAP attribution (§5) produces ranked, human-readable reason codes — this is the compliance artifact, surfaced in *both* lenses.
- **Model-risk governance (SR 11-7 / RBI model-risk guidance).** Every report must stamp **model version, training date, and metrics** (already in `pd_model_metadata.json`), and label outputs as model-assisted with human accountability retained.
- **Reproducibility & immutability.** A decision must be re-derivable years later. Persist an **immutable, hashed findings object** (inputs + model version + outputs). Same input + same model version ⇒ byte-identical report. This forces determinism (seed the RF, freeze perturbation logic).
- **Maker-checker & override.** No model auto-declines in a vacuum: a credit officer can **override with a logged justification** (four-eyes for material exposures). Overrides are first-class audit records, not edits.
- **Fair lending.** Keep prohibited-basis attributes out of features and out of reason codes; the dual-lens design (§2) prevents inconsistent rationales across audiences.
- **PII & access control.** Reports contain borrower financials → real authentication, role-based access (officer vs. admin vs. read-only auditor), and encryption at rest. **The `1234` admin password is not acceptable for a system holding applicant data** — flag for replacement before any real-data use.

---

## 5. Methodology upgrades (defensible, not decorative)

**5.1 Genuine uncertainty from the model you already have.**
RandomForest gives free, honest uncertainty: predict with every tree and take the spread.
```python
per_tree = np.array([t.predict(X)[0] for t in model.estimators_])
pd_point = per_tree.mean()
pd_low, pd_high = np.percentile(per_tree, [10, 90])   # 80% band
```
Show the band on the gauge. A wide band near the cutoff is itself a *Refer* signal. This replaces v1's hardcoded `±8`.

**5.2 SHAP for reason codes (replaces ad-hoc perturbation for *attribution*).**
`shap.TreeExplainer` on the RF gives signed per-feature contributions for *this* borrower. Sort by magnitude → the top drivers become regulator-ready reason codes ("High debt-to-equity," "Thin interest coverage"). Attribution (why this score) and recourse (what to change) are different questions — use SHAP for the first.

**5.3 Constrained, realistic counterfactuals (upgrades v1 recourse).**
Keep the "what if" idea, fix the rigor:
- Search toward the **cutoff/next grade**, not arbitrary % steps — the goal is "what gets you to approvable," not "what moves the needle 2pp."
- **Constrain to plausible, monotonic, single-or-paired** moves within `healthy_range`; respect direction (you can't wish liquidity to 10×).
- Report **impact as grade/decision change**, not just pp — "raising interest coverage from 1.8 to 2.5 moves you from Grade B to Grade BB, Decline → Refer."
- Validate each counterfactual against model uncertainty so we don't promise a flip the model can't reliably deliver.

**5.4 PD → rating masterscale.**
Define ~12 grade bands with PD ranges and align to the existing SA rating labels (`AAA…D`) in `calculations.py`. The gauge's bands become **the rating grades**, not the arbitrary 15/35/55/75 from v1. Now AIRB (model PD) and SA (external rating) speak one language.

**5.5 Peer comparison — keep, but caveat honestly.**
Feature-health vs. approved-peer medians stays (it's intuitive and useful). But: standardize features before distance, and **label the peer set as synthetic** until real approved-book data exists. Don't present synthetic peers as ground truth in an audit context.

**5.6 Five C's as the report's spine.**
The data dictionary already maps variables to **Character, Capacity, Capital, Collateral, Conditions**. Organize the evidence section by the Five C's — the universal credit narrative every officer and committee already reads. Our 4 ratios populate Capacity/Capital/Liquidity; seniority+collateral populate Collateral; sector/maturity populate Conditions. This single change makes the report instantly legible to a banker.

---

## 6. UX for the underwriter (where v1 was weakest)

**6.1 Progressive disclosure, not a page redirect.** v1 redirects via `localStorage` — fragile and loses the input context. Instead: render an **inline executive band** in the calculator on calculate (Grade · PD±band · EL · rate · recommendation), with **"Open full report"** expanding the detailed view in place (or a dedicated route fed by a report ID from the server, not localStorage). The officer should never lose the case they're working.

**6.2 Inverted pyramid.** Decision first, then drivers, then evidence (Five C's), then recourse, then technical appendix. A busy officer reads the top band; a committee reads to the appendix. Same document, layered depth.

**6.3 Charts: render client-side from JSON — do not ship matplotlib SVG.**
matplotlib in a Flask request path is slow (~500ms), memory-heavy, **not thread-safe** (needs a global lock, which serializes concurrent requests on App Engine), and produces visually heavy SVG. Instead the engine returns **numbers**; a light client library (Chart.js or hand-rolled SVG) draws the gauge, the reason-code tornado, and the feature-health bars. Faster, prettier, responsive, and it removes a real concurrency hazard. (Keep matplotlib only for the *offline PDF/batch* path, behind the existing training lock.)

**6.4 First-class states.** Design loading (skeleton, ~1–2s), **model-unreachable fallback** (rule-based PD with a visible "degraded — rule-based" banner, since `api-integration.js` already falls back), low-confidence (wide band → "manual review recommended"), and clear-approve (suppress recourse — don't coach an obvious yes).

**6.5 Accessibility & print.** WCAG 2.1 AA: don't encode status by color alone (pair with label/icon — color-blind safe), keyboard-navigable, semantic headings, print stylesheet that reflows to clean A4 for the credit file.

---

## 7. The applicant lens & the onboarding journey

The report is one moment in a journey. Designing it in isolation is the v1 trap.

```
Apply → Capture & consent → Assess (engine) → DECISION ──┬─ Approve  → Offer → e-sign → Drawdown → Monitor
                                                          ├─ Refer    → Officer review / committee → re-decision
                                                          └─ Decline  → APPLICANT LETTER (adverse-action + recourse)
                                                                              │
                                                                        re-apply when improved  ◄── nurture loop
```

- **The Applicant Letter is the onboarding nurture engine.** A decline today is a customer tomorrow. The three pathways (A: restructure the *request* — lower amount, add collateral, shorten tenor → recomputed live; B: 3–6mo financial routine; C: 6–12mo profile) turn a rejection into a roadmap and a reason to come back. **Pathway A is special: it's not advice, it's a re-quote** — let the applicant test "what if I post collateral / borrow less" against the live engine and see the grade move.
- **Disclosure discipline.** The letter shows principal reasons and recourse in plain language; it must **not** leak internal grades, model internals, peer raw data, or competitor-sensitive pricing logic.
- **Consent & data.** Onboarding realities the report depends on: KYC status, data-sharing consent (account aggregator in the India context), and document collection — surface these as gating "Conditions," not afterthoughts.
- **Tone scales to outcome** (the one genuinely good idea to keep from `case_report_builder.py`): encouraging when near-miss, honest and concrete when far. Borrower-facing only — never in the underwriter report.

---

## 8. Revised architecture, durability & security

```
backend/
  assessment_engine.py     orchestrator → builds the immutable findings object
  rating_masterscale.py    PD ↔ grade bands, aligned to SA rating labels
  explainability.py        SHAP reason codes + RF tree-variance uncertainty
  recourse.py              constrained counterfactuals → grade/decision deltas
  pricing.py               EL, capital charge, indicative risk-based rate
  policy_rules.py          knockouts & referral triggers (config-driven)
  peer_comparison.py       standardized feature-health vs (synthetic) approved book
  five_cs.py               maps features → Character/Capacity/Capital/Collateral/Conditions
  report_render.py         findings → underwriter HTML / applicant HTML (Jinja2)
ml_models/
  approved_borrowers.parquet   cached approved set (clearly labelled synthetic)
  pd_model_metadata.json       + feature_importance, masterscale, model hash
public/
  report-charts.js         client-side gauge / tornado / health bars from JSON
  report-underwriter.html  internal lens
  report-applicant.html    external lens
```

- **Durability for audit:** write the immutable, **hashed** findings object to **GCS (or a DB)** — *not* ephemeral `data/`. App Engine wipes local disk on restart; an unreproducible credit decision is a compliance failure. Store: inputs, model version+hash, full findings, rendered report, timestamp, officer/override events.
- **Determinism:** seed the RF; freeze recourse search; same input+version ⇒ identical report.
- **Performance:** engine target <300ms (no matplotlib); SHAP on a 4-feature RF is fast, but **precompute the SHAP explainer once at startup**, not per request.
- **Security:** replace `1234` with real auth + RBAC (officer / admin / auditor-read-only) **before** any real borrower data; encrypt findings at rest; log every report view (PII access trail).
- **Config over code:** policy knockouts, masterscale bands, pricing parameters, and pathway metadata live in JSON the admin can edit (extends the existing hyperparameters pattern) — credit policy changes shouldn't need a redeploy.

---

## 9. Banking-team experience (the other half of "best experience")

The user asked for the banking team's experience too — extend the existing `admin.html`, but separate **Credit Ops** from **ML Ops**:

- **Case queue:** applications by status (New / Referred / Approved / Declined), sortable by EL and exposure.
- **Override workspace:** open a case, see the findings, **override with mandatory justification**; four-eyes for exposures over a configurable threshold.
- **Audit log:** immutable trail of decisions, overrides, and report views (who saw which borrower's data, when).
- **Portfolio monitoring:** reuse `PortfolioCalculations` — concentration by grade/sector, EL trend, rating migration, capital consumption. This connects single-case reports to portfolio risk.
- **Policy console:** edit knockouts / masterscale / pricing params (config-driven, §8).
- Keep ML Ops (training, charts, schedule, smoke tests) as-is, but gate behind the new RBAC.

---

## 10. Revised roadmap (sequenced by value & risk)

| Step | Deliverable | Why first |
|------|------------|-----------|
| **0. Decide** | Confirm primary lens (rec: underwriter) + masterscale grades + policy knockouts | Everything keys off these |
| **1. Engine core** | `assessment_engine` + `rating_masterscale` + EL/pricing reusing `calculations.py`; immutable findings object | Decision-grade output, the spine |
| **2. Explainability** | `explainability` (SHAP reason codes + tree-variance band) | The regulatory artifact; powers both lenses |
| **3. Underwriter report** | `five_cs` + `report_render` + client-side charts; inline exec band + full view | First usable end-to-end value |
| **4. Recourse** | `recourse` (constrained counterfactuals → grade deltas) + Pathway-A live re-quote | Turns assessment into action |
| **5. Durability & auth** | GCS/DB persistence + RBAC, replace `1234` | Required before real data |
| **6. Applicant letter** | `report-applicant.html` projection + disclosure controls | External lens once internal is proven |
| **7. Credit Ops console** | Case queue, override + maker-checker, audit log | Team experience & governance |
| **8. Portfolio & policy** | Monitoring views + config console | Scale from case to book |

Steps 1–4 deliver a credible internal report; 5 gates real data; 6–8 complete the experience. (v1's 33-hour single-pass estimate understated governance/durability, which is where credit systems actually live.)

---

## 11. Decisions to confirm before building

1. **Primary lens first** — Underwriter (recommended) or Applicant?
2. **Rating masterscale** — adopt a standard 12-grade scale aligned to the SA labels (`AAA…D`), or a simpler internal 5-grade scale?
3. **Pricing in scope now?** — include indicative risk-based rate in v1, or assessment-only first?
4. **Persistence target** — GCS bucket vs. a small managed DB (Cloud SQL/Firestore) for findings + audit?
5. **Auth** — minimum acceptable before real borrower data (the `1234` replacement): simple login + roles now, or defer applicant lens until SSO exists?
6. **Peer data** — keep synthetic approved-book (clearly labelled) for now, or hold peer comparison until real approved data is available?

---

## 12. What we keep from v1 (so nothing good is lost)

Risk gauge ✔ (now grade-banded) · Peer feature-health ✔ (now standardized + labelled) · Counterfactual recourse ✔ (now constrained, grade-aware) · Three pathways ✔ (Pathway A now a live re-quote) · Outcome-scaled tone ✔ (applicant lens only) · Reassessment timeline ✔ · Client report viewer ✔ (now server-fed by report ID, charts client-side).

---

**Author:** Claude Code
**Supersedes design intent of:** `REPORT_GENERATION_INTEGRATION_PLAN.md`
**Next:** confirm §11 decisions, then build Step 1 (engine core).
