# AEGIS run log — GERMAN (UCI Statlog German credit)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/german_credit_record.csv` — 1,000 rows, 20 features + target → **17-feature pool** after G0,
event rate 0.30 (**300 events**).
**Started:** 2026-10-17 · **Human signer:** Ravi · **Materiality tier:** MEDIUM (public benchmark) · **Record:** `SHARP_GERMAN.md`
**Fresh re-run (repeat of the governed exercise).** Deterministic (seed 42) → with the G0=A scope this reproduces the
previously committed German result. Consumer credit → **fairness LIVE** (age/sex/national-origin present).

> **Order (standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the decisioning
> note and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-GERMAN0 |
| 1 | G0 | **A — Exclude age + personal_status_sex + foreign_worker (hard prohibited); retain housing + people_liable proxies** (MEDIUM) | Ravi / Data Steward | compliance-first; drop the 3 hard protected bases before modelling; retain the 2 softer proxies for the G4 fairness review; reproduces committed German scope (17-feature pool) | GEN-GERMAN0 | b1d70c29 |
| 2 | G1 | **A — Accept 12/17 screen; sufficiency met** | Ravi / Model Validator | EPV ≈ 17.6 (300/17) healthy, no caveat; `checking_status` genuinely strong (IV 0.666); proxy `people_liable` self-removed (IV 0.000, fairness-favourable); `housing` passed weak (0.083); `credit_amount` escalated for non-monotonic shape | b1d70c29 | 5139746d |
| 3 | G2 | **A — Accept attribution; retain `housing` per G0 (parsimony-trimmed → final model proxy-free)** | Ravi / Model Validator | 10/12 players confirmed over shadow bar 0.00459; `credit_amount` vindicated at model-check (4× bar despite U-shape); `installment_rate` + `other_debtors` dropped below bar; `housing` confirmed (2.2×) but ranks 8th → excluded by top-5 parsimony | 5139746d | 2d292965 |
| 4 | G3 | **A — Ratify k=5 (genuine parsimony; both criteria agree)** | Ravi / Model Validator | selected 5 cols, Gini 0.5317 / AUC 0.766; at k=5 DeLong p=0.061 (≥0.05) AND rel loss 4.10% (≤5%) clear together — real parsimony (5 of 17 features), the clean contrast to LC's large-N SIG-N; method fixed (P8) | 2d292965 | 49559806 |
| 5 | G4 | **A — Approve; calibration passes; age disparate-impact disclosed (true-risk-driven)** (dual) | Ravi / Risk Officer + Validator | selection Gini 0.532 reliable; HL pass p=0.46/0.21, ECE 0.040 → PDs usable; 7/8 grades in Wilson CI (BB under-predicts, n=34); **sex clean (AIR 0.99)**, **age fails four-fifths (worst 0.574) but true-risk-driven** (young default 48.7% vs 13.3%; age excluded yet impact persists via correlated features — replicates LC necessary-not-sufficient); foreign_worker inconclusive (6 test rows); never-deploy | 49559806 | 403d8a81 |
| 6 | G5 | **A — Standard config; deliverables on 5-feature model** | Ravi / Model Owner | `checking_status` mandatory (blank→refer); incomplete_policy refer; exact WOE reason codes; conditions AGE-IMPACT/FW-THIN/DQ-BB/NEVER-DEPLOY carried; no cutoff/pricing; 6-case pack confirms PD floor+cap bind and completeness gate | 403d8a81 | 884c20a1 |
| 7 | **GF** | **A — GO-WITH-CONDITIONS** | Ravi / MAC Chair + CRO | method validated; Gini 0.532/AUC 0.766 reliable; calibration clean (PDs usable); genuine parsimony k=5 (both criteria agree — clean contrast to LC SIG-N); sex clean; age disparate-impact disclosed true-risk-driven (replicates LC necessary-not-sufficient on an independent dataset); foreign_worker inconclusive; MEDIUM never-deploy; conditions AGE-IMPACT/FW-THIN/DQ-BB/NEVER-DEPLOY carried; **reproduces the committed German verdict** (determinism confirmed) | 884c20a1 | a6adf8b1 |

**Chain:** GEN-GERMAN0 → b1d70c29 → 5139746d → 2d292965 → 49559806 → 403d8a81 → 884c20a1 → **a6adf8b1**. ✅ **SEALED**

---

## G0 — Eligibility & scope  ·  status: ✅ DECIDED — **A** (exclude 3 prohibited; retain 2 proxies)

**Signer:** Ravi (Data Steward) · **2026-10-17** · entry_hash `b1d70c29`

**Decision:** proceed on a **17-feature pool**, excluding the three hard protected attributes
(`age`, `personal_status_sex`, `foreign_worker`); **retain** `housing` and `people_liable` (proxy_risk) for the G4
geographic/familial-fairness review. **Rationale:** *compliance-first — exclude the hard prohibited bases.*

### Protected / proxy inventory

| Column | Tag | Basis | Fate |
|---|---|---|---|
| `age` | **prohibited** | age (ECOA/Reg B; UK Equality Act) | **excluded** at G0 |
| `personal_status_sex` | **prohibited** | sex + marital status | **excluded** at G0 |
| `foreign_worker` | **prohibited** | national origin | **excluded** at G0 |
| `housing` | proxy_risk | residential tenure ⇒ correlated with protected traits | **retained** (disclosure; G4 review) |
| `people_liable` | proxy_risk | household composition ⇒ familial-status/sex proxy | **retained** (disclosure; G4 review) |

**Materiality tier:** MEDIUM — immaterial public research benchmark. **Fairness LIVE** (though the hard protected
columns are excluded, the two proxies are watched through to G4).

**Honesty note:** retention of proxies is a benchmark-comparability choice with disclosure; no model in this run is
intended or suitable for a live credit decision. A proxy-excluded replication (option C) remains available on request.

## G1 — Data sufficiency & screen integrity  ·  status: ✅ DECIDED — **A** (accept screen)

**Signer:** Ravi (Model Validator) · **2026-10-17** · entry_hash `5139746d`

**Decision:** accept the Stage-1 screen (**12 of 17** passed); **data sufficiency met** — EPV ≈ 17.6, well above the
≥10 rule, 0% missing. **Rationale:** *accept screen; healthy EPV.*

**Screen highlights:** `checking_status` IV **0.666** (strong — rare dominant feature) leads; medium-band
`credit_history` 0.292, `months_duration` 0.259, `savings_status` 0.196, `purpose` 0.155. **Dropped (5, IV<0.02):**
`existing_credits`, `job`, `telephone`, `residence_since`, **`people_liable` (IV 0.000 — proxy self-removed)**.
**Escalation:** `credit_amount` flagged `shape_nonmonotonic` (U-shaped) → routed to Stage-2 model-check, not judged on IV.

## G2 — Importance attribution  ·  status: ✅ DECIDED — **A** (accept; housing retained, trimmed at selection)

**Signer:** Ravi (Model Validator) · **2026-10-17** · entry_hash `2d292965`

**Decision:** accept the Shapley attribution; retain `housing` per G0 (confirmed real), noting it is parsimony-trimmed
so the final model carries no proxy. **Rationale:** *clean attribution; proxy resolves itself at selection.*

**Attribution (shadow bar 0.00459; 10 of 12 players confirmed):** `checking_status` 0.0863 (19×), `credit_history`
0.0399, `months_duration` 0.0329, `savings_status` 0.0283, `purpose` 0.0248, `credit_amount` 0.0180 (4× — vindicated
at model-check despite U-shape), `employment_since` 0.0134, `housing [proxy]` 0.0102 (2.2×), `property` 0.0084,
`other_installment_plans` 0.0083. **Dropped below bar:** `installment_rate` (0.0038), `other_debtors` (−0.0004).

## G3 — Parsimony selection  ·  status: ✅ DECIDED — **A** (ratify k=5)

**Signer:** Ravi (Model Validator) · **2026-10-17** · entry_hash `49559806`

**Decision:** ratify the pre-registered **k=5** selection — `checking_status`, `credit_history`, `months_duration`,
`savings_status`, `purpose`. **Gini 0.5317 / AUC 0.766.** **Rationale:** *genuine parsimony — both criteria agree.*

At k=5 **both** stopping conditions clear together (DeLong p=0.061 ≥0.05 **and** rel. Gini loss 4.10% ≤5%); k≤4 fails
both. This is real parsimony — **5 of 17 features, statistically indistinguishable from the full model** — the clean
contrast to LC, where N≈40k forced the near-full set (SIG-N). No large-N tension here.

## G4 — Performance, calibration & fairness backtest  ·  status: ✅ DECIDED — **A** (approve; age impact disclosed)

**Signers:** Ravi (Risk Officer + Validator, dual) · **2026-10-17** · entry_hash `403d8a81`
**Held-out test:** 80/20 stratified (seed 42) — 200 loans / 60 defaults.

**Decision:** approve; calibration passes (PDs usable); age disparate-impact disclosed as true-risk-driven.
**Rationale:** *age impact traces to real risk, not bias; calibration clean.*

### Discrimination & calibration
Selection Gini **0.532** / AUC 0.766 (held-out 0.56/0.78, small-sample wobble). **HL g=10 p=0.460, g=5 p=0.212
(pass); ECE 0.040.** 7/8 grades in Wilson CI — only **BB** out (obs 14.7% vs pred 6.2%, under-predicts; n=34).

### Fairness — tested across the EXCLUDED protected attributes (proxy-leakage test)
The final 5-feature model uses none of `age`/`sex`/`foreign_worker`; AIR on the internal masterscale "approve" grade
(indicative, no institution cutoff):

| Attribute | Worst AIR | Verdict |
|---|--:|---|
| **Sex** (female vs male) | 0.987 | ✅ PASS — no proxy leakage |
| **Age** (<25 … 60+) | **0.574** | ❌ FAIL — but **true-risk-driven** |
| foreign_worker | 0.000 | ⚠️ inconclusive (only 6 non-foreign in test) |

**Age finding:** <25 default 48.7% → 60+ 13.3%; approve AIR <25 = 0.574. **Age was excluded at G0, yet the model
reproduces age-disparate impact via correlated features** (`checking_status`, `months_duration`). Model is accurate
within each band → disparate *impact* from true risk, **not bias**. **Replicates the LC lesson: excluding the protected
attribute is necessary but not sufficient.**

### Conditions carried to GF
- **AGE-IMPACT** — age-disparate impact disclosed (true-risk-driven; AIR indicative, no cutoff); fairness-constrained
  replication / reject-inference needed before any live use.
- **FW-THIN** — foreign_worker fairness inconclusive (6 test rows; non-foreign only 37/1000).
- **DQ-BB** — grade BB under-predicts on backtest; monitor.
- **NEVER-DEPLOY** — research benchmark. (German is a freely-citable UCI dataset → no licensing/vintage condition.)

## G5 — Deliverables & decisioning  ·  status: ✅ DECIDED — **A** (standard config)

**Signer:** Ravi (Model Owner) · **2026-10-17** · entry_hash `884c20a1`

**Decision:** standard deployment-governance config on the 5-feature model; generate decisioning note + 6-case pack.
**Rationale:** *standard config.* `checking_status` mandatory (blank→refer); incomplete_policy `refer`; exact WOE reason
codes; PD floor 0.03% / cap 99.9%; **no cutoff/pricing invented.**

**Deliverables generated:**
- `AEGIS_GERMAN_CUTOFF_POLICY.md` — decisioning note; carries AGE-IMPACT / FW-THIN / DQ-BB / NEVER-DEPLOY.
- `acceptance_cases/german.json` + `SAMPLE_RUNS_GERMAN.md` — 6-case pack (4 real spanning good/bad; 2 synthetic
  best/worst). PD **floor (0.03%) and cap (99.9%) both bind**; reason codes coherent; `checking_status` gate enforced.
  Case PDs: R1 0.03% (AAA) → R2 28.4% (CC) → R3 47.4% (C) → R4 99.9% (D).
- `data/ml_lab/datasets/german_clean.csv` — de-BOM'd renderer input.

## GF — Final verdict  ·  status: ✅ SEALED — **A (GO-WITH-CONDITIONS)**

**Signer:** Ravi (MAC Chair + CRO) · **2026-10-17** · entry_hash `a6adf8b1` · prev `884c20a1`

**Verdict: GO-WITH-CONDITIONS.** The SHARP method is validated on German and the run is accepted into the paper's
corpus. Discrimination is medium and **reliable** (Gini 0.532 / AUC 0.766); calibration is **clean** (HL p=0.46/0.21,
ECE 0.040 → PDs usable); fairness is **fully characterised** with the age-disparate impact disclosed as true-risk-driven,
tolerable at a MEDIUM never-deploy research tier. The deterministic re-run **reproduces the committed German verdict**,
confirming the pipeline is reproducible (seed 42).

### Why German matters to the paper
1. **The parsimony showcase.** At N=1,000 the fixed rule delivers **genuine parsimony — 5 of 17 features** — because
   both stopping criteria agree (DeLong p=0.061 ≥0.05 **and** rel. Gini loss 4.10% ≤5%). The clean counterpoint to LC,
   where N≈40k forced the near-full set (SIG-N). **Same rule, opposite behaviour, both honest.**
2. **A second proof of "necessary-but-not-sufficient."** Age was excluded at G0, yet the model reproduces age-disparate
   impact via correlated features — replicating the LC Midwest finding on an independent dataset. Two datasets, one lesson.
3. **Signal beats volume.** German reaches Gini 0.53 on 1,000 rows (dominant `checking_status`) while LC reaches 0.35 on
   40,000 — feature signal, not sample size, sets the ceiling.

### Binding conditions (carried to the paper write-up)
- **AGE-IMPACT** — age-disparate impact disclosed (true-risk-driven; AIR indicative, no cutoff); fairness-constrained
  replication / reject-inference required before any live use.
- **FW-THIN** — foreign_worker fairness inconclusive (6 test rows; non-foreign only 37/1000).
- **DQ-BB** — grade BB under-predicts on backtest; monitor.
- **NEVER-DEPLOY** — research benchmark only (freely-citable UCI; no licensing/vintage condition).

**Run status: COMPLETE (G0 → GF sealed).** This is the 12th governed run in the corpus. No parameter was re-opened at
any gate (P8); every figure traces to `SHARP_GERMAN.md`, `g4_german.json`, and `german_summary.json`.
