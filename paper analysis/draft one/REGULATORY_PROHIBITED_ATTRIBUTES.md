# Regulatory basis for prohibited & proxy attributes in credit models

**Purpose.** A citable reference for the literature review: *on what legal authority are certain attributes
dropped, retained-with-disclosure, or flagged as proxies?* This underpins SHARP's Stage-0 eligibility tagging and
the AEGIS fairness gates (G0, G4).

**Status.** Enumerations below are verified against named sources (see §7). Exact clause wording and current
effective dates should be confirmed against the primary instrument (eCFR, EUR-Lex, legislation.gov.uk, RBI) before
final citation in the paper. Prepared 2026-10-16.

---

## 1. The key distinction — this is NOT Basel/BIS

Two separate rulebooks are routinely conflated. They answer different questions:

| Rulebook | Source | Governs | On protected attributes |
|---|---|---|---|
| **Basel / BIS** (CRE framework; SR 11-7 → SR 26-2) | BIS + prudential regulators (Fed/OCC/FDIC, RBI, PRA, ECB) | capital adequacy, PD/LGD/RWA, model risk management | **silent** — Basel does not list or forbid any personal attribute |
| **Fair-lending / anti-discrimination law** | national legislatures + conduct regulators (CFPB, FCA, EU, RBI) | *whom* a lender may treat differently | **this is where the prohibited lists live** |

**Takeaway for the paper:** the authority to drop race/sex/geography comes from *fair-lending statute*, not from
Basel. Basel would permit any predictive feature; fair-lending law independently forbids some. SHARP encodes this as
a **permissibility gate (Stage 0) separate from the performance stages (1–3)**.

---

## 2. United States — the most explicit enumerated list

**ECOA** (Equal Credit Opportunity Act, 15 U.S.C. §1691) + **Regulation B** (12 CFR Part 1002), administered by CFPB.

**Prohibited bases** (ECOA §1691(a); Reg B §1002.2(z), §1002.6(b)):
- race or color · religion · national origin · sex (incl. sexual orientation / gender identity) · marital status ·
  age (provided the applicant has capacity to contract) · receipt of income from a public-assistance program ·
  good-faith exercise of rights under the Consumer Credit Protection Act.

**Core rule** — §1002.6(b)(1): a creditor *shall not take a prohibited basis into account in any system of evaluating
creditworthiness.* §1002.5(b) further restricts *collecting* several of these.

**Mortgages add (Fair Housing Act, 42 U.S.C. §3604–3605):** familial status · disability.

### ⚠️ 2.1 Recent change — disparate impact removed from Reg B (2026)
On **22 April 2026** the CFPB published a final rule (effective **21 July 2026**) that **removes the "effects test"
(disparate-impact) from Regulation B**, reframing federal ECOA as a **disparate-treatment-only** statute; facially
neutral criteria are now actionable federally only where **intentionally used as a proxy** for a protected class.
**Important caveats (still live):**
- the **Fair Housing Act** and **state fair-lending laws** may still impose disparate-impact liability (esp. mortgages);
- **intentional** discrimination and intentional proxy use remain prohibited;
- the interpretation faces legal uncertainty (possible litigation; courts may disagree).

**Implication for this project's four-fifths/AIR analysis:** the EEOC four-fifths test we apply remains valid as a
*research fairness diagnostic* and under FHA / state law / EU / UK regimes; but we should **no longer cite federal
ECOA disparate-impact as its authority post-July-2026**. Frame AIR as a disclosure/robustness diagnostic, not a
federal-ECOA compliance test. (This is why the LC run labels AIR "indicative.")

---

## 3. European Union — layered, no single enumerated credit list

- **GDPR Art. 9(1)** "special categories" — de-facto prohibited inputs: racial/ethnic origin · political opinions ·
  religious/philosophical beliefs · trade-union membership · genetic data · biometric data (for unique ID) · health ·
  sex life / sexual orientation. (Processing barred unless an Art. 9(2) exception applies.)
- **EU AI Act, Annex III point 5(b)** — AI used to *evaluate creditworthiness or establish a credit score of natural
  persons* is **high-risk** (applies whether the AI decides or only assists a human; fraud-detection scoring excepted).
  High-risk obligations include bias/data-governance duties. **High-risk application deadline moved 2 Aug 2026 →
  2 Dec 2027** by the Digital Omnibus Reg (EU) 2026/1744 (in force 27 Jul 2026); Art. 50 transparency duties still
  2 Aug 2026 (per project's primary-verified regulatory note).
- **EBA Guidelines on loan origination (EBA/GL/2020/06)** — add fairness/data-quality expectations.
- Anti-discrimination directives (Racial Equality 2000/43/EC; Gender Goods & Services 2004/113/EC) sit above all.

---

## 4. United Kingdom — Equality Act 2010

**Nine protected characteristics (s.4):** age · disability · gender reassignment · marriage & civil partnership ·
pregnancy & maternity · race · religion or belief · sex · sexual orientation. Conduct supervised by the **FCA**;
UK GDPR mirrors EU Art. 9 special categories.

---

## 5. India — a short binding FPC non-discrimination clause; no ECOA-style enumerated model-attribute list

**Constitutional baseline**
- **Constitution of India, Art. 15(1)** — the State shall not discriminate against any citizen on grounds only of
  religion, race, caste, sex, place of birth (or any of them). A guarantee against *State* action framing the
  policy backdrop — not a credit-specific rule binding private lenders directly.

**The explicit RBI non-discrimination clause (binding supervisory guidance)**
- **RBI, *Guidelines on Fair Practices Code for Lenders***, DBOD. Leg. No.BC. 104/09.07.007/2002-03, **5 May 2003**,
  addressed to all Scheduled Commercial Banks / All-India Financial Institutions. Clause **2(v)(b)** ("General"),
  **verbatim**:
  > "Lenders must not discriminate on grounds of sex, caste and religion in the matter of lending. However, this
  > does not preclude lenders from participating in credit-linked schemes framed for weaker sections of the society."
  - This is the **nearest Indian analogue to an ECOA prohibited-basis list — but far shorter**: only **three grounds
    (sex, caste, religion)**, no enumeration of age / marital status / disability / national origin, and **no
    disparate-impact "effects test"** machinery. It is carried forward into the consolidated Fair Practices Code
    instructions for banks (Master Circular on Loans and Advances) and NBFCs (NBFC FPC Master Direction; NBFC
    versions often render "sex" as "gender"). Confirm the current consolidated wording before submission.

**Conduct + AI-governance layer (process fairness, not an attribute list)**
- **RBI Guidelines on Digital Lending (2 Sep 2022)** — fair, transparent, non-exploitative digital-lending conduct
  and disclosure of the basis of credit assessment; process fairness, not a prohibited-column list.
- **RBI FREE-AI report** — *Framework for Responsible and Ethical Enablement of Artificial Intelligence*, committee
  report **released 13 Aug 2025**. Seven guiding principles ("Sutras") including **Fairness & Equity, Accountability,
  and Understandable-by-Design**; recommends that AI used in credit/underwriting be **explainable, auditable and free
  of discriminatory bias**. **Status: a committee report / recommendations, not (yet) binding regulation** — cite as
  direction-of-travel, not an enforceable rule.

**Practical consequence for an India-framed paper**
- "Which attributes are off-limits" is governed by a **short binding FPC clause (sex, caste, religion)** +
  constitutional principle + emerging AI-governance expectations — **not** an ECOA-style enumerated model-attribute
  list with a disparate-impact test. The interpretive burden on the lender is correspondingly higher, and the
  proxy / disparate-impact analysis AEGIS runs at G4 is therefore **voluntary rigor** in the Indian setting rather
  than a statutory requirement — worth flagging explicitly in the literature review.

---

## 6. Proxies & disparate impact — why a *list* is never enough

**No regulator enumerates proxies** (ZIP/PIN code, education, occupation, device/behavioural data). Proxy risk is
governed by doctrine, not a lookup:
- **Redlining** — geography as a proxy for race/national origin (US ECOA/FHA; analogous concerns elsewhere).
- **Disparate-impact doctrine** (where still operative — FHA, EU, UK): a neutral feature causing adverse group impact
  must meet a **business-necessity** test, and must yield to a **less-discriminatory alternative (LDA)** of comparable
  performance. *This LDA test — not the AIR number alone — is what justifies dropping a proxy when a near-equal model
  exists without it* (e.g., LC: dropping `addr_state` costs only 0.007 Gini → LDA favours the no-geo model).
- Because proxies are unlisted, **statistical detection is required** — hence SHARP's shadow-null + proxy tagging.

---

## 7. How this maps to SHARP Stage-0 tags

| SHARP tag | Legal grounding |
|---|---|
| **prohibited** (sex, age/YOB, marital/spouse-income, race) | ECOA §1002.6(b); UK Equality Act s.4; GDPR Art. 9; India — Constitution Art. 15(1) + RBI FPC for Lenders cl. 2(v)(b) (sex, caste, religion only) |
| **proxy_risk** (geography, education, dependents, housing tenure) | redlining doctrine + disparate-impact / LDA test (FHA, EU, UK) |
| **permissible** (income, balances, utilisation, inquiries) | no prohibited-basis match; legitimate risk factors |

Retention of a prohibited/proxy feature in this project is **always** a benchmark-comparability choice with mandatory
disclosure and a **never-deploy** flag — never an endorsement of live use.

---

## 8. Sources (verify primary text before final citation)

- US ECOA / Reg B — [FDIC ECOA exam manual, V-7.1](https://www.fdic.gov/consumer-compliance-examination-manual/v-7-equal-credit-opportunity-act-ecoa) · [CFPB ECOA narrative & procedures (2026-07)](https://files.consumerfinance.gov/f/documents/cfpb_ecoa-narrative-and-procedures_2026-07.pdf) · primary: 15 U.S.C. §1691, 12 CFR Part 1002 (eCFR).
- CFPB 2026 Reg B rule (disparate impact removed) — [Eversheds Sutherland analysis](https://www.eversheds-sutherland.com/en/united-states/insights/cfpb-final-rule-amends-ecoa-regulation-b-disparate-impact-eliminated-discouragement-standard) · [Norton Rose Fulbright](https://www.nortonrosefulbright.com/en-us/knowledge/publications/bcb29048/cfpb-amends-regulation-b-changing-approach-to-fair-lending) · [National Law Review](https://natlawreview.com/article/cfpb-final-rule-revises-ecoa-framework-narrows-disparate-impact-and-discouragement) · primary: [regulations.gov CFPB-2025-0039-0001](https://www.regulations.gov/document/CFPB-2025-0039-0001) (Fed. Reg. 22 Apr 2026; eff. 21 Jul 2026).
- GDPR Art. 9 — [Fraunhofer FOKUS GDPR Art. 9](https://pie.fokus.fraunhofer.de/regulations/gdpr-article-9) · primary: Regulation (EU) 2016/679, Art. 9 (EUR-Lex).
- EU AI Act Annex III 5(b) — [Openlayer credit-scoring compliance guide](https://www.openlayer.com/blog/credit-scoring-eu-ai-act-compliance-guide) · primary: Regulation (EU) 2024/1689, Annex III (EUR-Lex); confirm operative date (Digital Omnibus).
- UK — [legislation.gov.uk Equality Act 2010 s.4] (confirm) · secondary: [Oxford SPI summary](https://dspi.web.ox.ac.uk/node/4251826).
- India — **primary (verbatim, read in full):** RBI *Guidelines on Fair Practices Code for Lenders*, DBOD. Leg.
  No.BC. 104/09.07.007/2002-03, 5 May 2003, clause 2(v)(b) — [RBI PDF](https://www.rbi.org.in/commonman/Upload/English/Notification/PDFs/36102.pdf).
  Also: RBI Digital Lending Guidelines (2 Sep 2022); NBFC FPC Master Direction; RBI *FREE-AI* report (13 Aug 2025,
  committee report — [RBI/MediaNama PDF](https://www.medianama.com/wp-content/uploads/2025/08/Framework-for-Responsible-and-Ethical-Enablement-of-Artificial-Intelligence-FREE-AI-RBI-Report.pdf)); Constitution of India, Art. 15(1).
