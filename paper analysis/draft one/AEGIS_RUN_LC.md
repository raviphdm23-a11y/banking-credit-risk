# AEGIS run log — LC (LendingClub consumer loans; public quarterly loan-level slice)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/lending_club_q12019.csv` — 39,717 rows, 111 raw columns → **~23 application-time features** after G0 scoping, event rate 0.1417 (**5,627 events**).
**Started:** 2026-10-16 · **Human signer:** Ravi · **Materiality tier:** MEDIUM (public benchmark; internal/sandbox use) · **Record:** `SHARP_LC.md`
**Eleventh governed run — the LARGEST, highest-EPV run of the corpus (EPV ≈ 5,627 / ~14 selected ≫ 10).** Deliberate
contrast on the *volume* axis: where MSME failed on data insufficiency, LC has abundant events, so any weakness here is
genuine signal/quality, not sample size. **Grade/sub_grade (LendingClub's own risk-model output) excluded at G0 (option B)**
so the run is a pure test of SHARP on raw applicant features, not a re-prediction of LC's score.

> **Order (standard):** gates G0→G5, with the **per-grade calibration backtest inside G4**; then the decisioning
> note and acceptance demonstration; then **GF last** with full visibility.

## Standing caveats (carried to GF)
- **LICENSING** — LendingClub data-reuse terms permit internal/sandbox testing; **citing these results in the ICOPEX
  paper requires confirming those terms first.** Until cleared, results are internal-only.
- **PROVENANCE/VINTAGE** — file is named `q12019` but internal dates (`issue_d` Aug-09, `last_pymnt_d` Oct-11,
  `earliest_cr_line` Feb-94) indicate **2009–2011 vintage, not 2019**. True vintage to be verified before citation.
- **FAIRNESS SCOPE** — no direct demographic fields (no age/sex/race); only geography (`addr_state`). Fairness analysis
  is limited to **geographic disparity** — weaker than TH02's age-based ECOA story. Stated plainly.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-LC0 |
| 1 | G0 | **B — Exclude LendingClub's own grade/sub_grade; purer methodology test** (MEDIUM) | Ravi / Data Steward | drop all 100%-empty (~53), post-outcome leakage (13), IDs/free-text (7), constants (9); exclude `grade`/`sub_grade` to avoid predicting LC's score with LC's score; retain geography for SHARP proxy handling; licensing/vintage/fairness caveats carried | GEN-LC0 | 9b382c00 |
| 2 | G1 | **B — Exclude `int_rate`+`installment`; grade-free re-run** | Ravi / Model Validator | `int_rate` is a continuous re-encoding of the excluded `sub_grade` (LC prices from grade) → back-door circularity, undermines G0 intent; `installment` is rate-derived; data sufficiency emphatically met (EPV ≈ 245); rate-included model retained as comparison point | 9b382c00 | d04b7ee5 |
| 3 | G2 | **A — Retain `addr_state`; bind geographic-disparity review at G4** | Ravi / Model Validator | all 8 players confirmed over shadow bar 0.00104 (weakest `pub_rec` 7×); `addr_state` is a *confirmed real* proxy at 8× bar — retain to study the proxy honestly rather than hide it; grade-free Gini 0.358 vs rate-included 0.387 (only −0.029 → raw features recover ~92% of discrimination) | d04b7ee5 | c95a3945 |
| 4 | G3 | **B — Ratify pre-registered k=8 (9 cols); also report k=5 parsimony point** | Ravi / Model Validator | method fixed (P8) → rule selects k=8 (Gini 0.358/AUC 0.679); large-N DeLong under-parsimonizes (SIG-N), so k=5 (Gini 0.341/AUC 0.671 ≈ 95% of discrimination at 5 features) reported descriptively; geographic-disparity + HL-large-N + ceiling escalated to G4 | c95a3945 | f85b8db1 |
| 5 | G4 | **A — Adopt no-geo model as primary; calibration clean (PDs usable); retain with-geo as comparability** (dual) | Ravi / Risk Officer + Validator | held-out Gini 0.358 = selection (reliable); **HL passes p=0.48–0.54 + ECE 0.0020** → SIG-N fear did not bite, PDs usable unlike TH02; 8/9 grades in Wilson CI; geographic AIR fails four-fifths (with-geo worst 0.568; no-geo worst 0.622 — West/South cured, Midwest persists via correlated features) but **disparate impact driven by true regional risk, not bias**; no-geo costs only −0.007 Gini; never-deploy | f85b8db1 | 9901f49d |
| 6 | G5 | **A — Standard config; deliverables on no-geo model** | Ravi / Model Owner | `annual_inc` mandatory (blank→refer); incomplete_policy refer; exact WOE reason codes; all conditions (NEVER-DEPLOY/LICENSING/VINTAGE/GEO-AIR/DQ-BBB/SIG-N) carried to decisioning note; no cutoff/pricing; 6-case pack (4 real + 2 synthetic) confirms PD floor+cap bind and completeness gate | 9901f49d | 7c8d5e06 |
| 7 | GF | **GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | approve as MEDIUM research benchmark; method validated (clean 21→8, grade-free, all players confirmed, proxies studied); calibration **clean** (HL pass, ECE 0.0020 → PDs usable, unlike TH02); weak-but-reliable Gini 0.351; fairness weakness disclosed + mitigated (no-geo primary; residual Midwest impact true-risk-driven); two publishable findings (LC grade adds ~0.03 Gini; proxy removal necessary-not-sufficient); conditions NEVER-DEPLOY/LICENSING/VINTAGE/GEO-AIR/DQ-BBB/SIG-N binding | 7c8d5e06 | **1c280308** |

**Chain:** GEN-LC0 → 9b382c00 → d04b7ee5 → c95a3945 → f85b8db1 → 9901f49d → 7c8d5e06 → 1c280308.

---

## G0 — Eligibility & scope  ·  status: ✅ DECIDED — **B** (exclude grade/sub_grade)

**Signer:** Ravi (Data Steward) · **2026-10-16** · entry_hash `9b382c00`

**Decision:** proceed on a **cleaned ~23-feature application-time pool**, **excluding** LendingClub's own `grade` and
`sub_grade`. **Rationale:** *exclude LendingClub's own grade — purer test of the methodology.* Including LC's grade would
make the model largely re-predict LC's own PD output (circularity → inflated Gini, weak scientific contribution);
excluding it tests SHARP + AEGIS on genuine raw applicant features. Geography (`addr_state`) retained so the pipeline can
demonstrate detecting/handling a geographic proxy rather than hiding it.

### Column audit (111 → ~23) — basis for scope

| Group | Count | Fate | Basis |
|---|--:|---|---|
| 100% empty in this slice | ~53 | ❌ dropped | joint-application + detailed bureau columns entirely blank (0 non-null) |
| Post-outcome leakage | 13 | ❌ dropped | `out_prncp(_inv)`, `total_pymnt(_inv)`, `total_rec_prncp/int/late_fee`, `recoveries`, `collection_recovery_fee`, `last_pymnt_d/amnt`, `next_pymnt_d`, `last_credit_pull_d` — values exist only *after* repayment/default |
| Identifiers / free text | 7 | ❌ dropped | `id`, `member_id`, `url`, `desc`, `title`, `emp_title`, `zip_code` |
| Constant (nunique=1) | 9 | ❌ dropped | `policy_code`, `application_type`, `pymnt_plan`, `initial_list_status`, `acc_now_delinq`, `tax_liens`, `chargeoff_within_12_mths`, `collections_12_mths_ex_med`, `delinq_amnt` |
| LendingClub grade output | 2 | ❌ dropped (**G0=B**) | `grade`, `sub_grade` — LC's own risk score; excluded to avoid circularity |
| **Legitimate application-time features** | **~23** | ✅ **kept → SHARP** | known at origination, genuinely predictive |

### Kept feature pool (fed to SHARP)
`loan_amnt`, `funded_amnt`, `term`, `int_rate`, `installment`, `emp_length`, `home_ownership`, `annual_inc`,
`verification_status`, `purpose`, `addr_state`, `dti`, `delinq_2yrs`, `credit_hist_years` (engineered from
`issue_d − earliest_cr_line`), `inq_last_6mths`, `mths_since_last_delinq`, `mths_since_last_record`, `open_acc`,
`pub_rec`, `revol_bal`, `revol_util`, `total_acc`, `pub_rec_bankruptcies`.

**Parsing applied (standard prep, not a methodology change):** `int_rate`/`revol_util` "11.89%" → 11.89; `term`
"36 months" → 36; `emp_length` "< 1 year"→0.5 … "10+ years"→10; `earliest_cr_line`/`issue_d` → `credit_hist_years`.

### Protected / proxy inventory (SHARP Stage-0 governance layer)

| Column | Tag | Basis | Disposition |
|---|---|---|---|
| `addr_state` | proxy_risk | geography ⇒ may correlate with protected traits (redlining risk) | retained for G2 shadow/fairness assessment; geographic disparity reviewed at G4 |
| `zip_code` | proxy_risk | fine-grained geography | **dropped** at G0 (high-cardinality identifier; `addr_state` is the retained geographic signal) |
| others | permissible | loan terms, income, credit-bureau counts | — |

**Materiality tier:** **MEDIUM** — immaterial public research benchmark, internal/sandbox use (AEGIS §3.1).

**Honesty note (recorded):** no model in this run is intended or suitable for a live credit decision. Results are
internal until licensing + vintage are confirmed. A replication retaining `grade`/`sub_grade` (option A) remains
available on request as a predictive-ceiling comparison.

---

## G1 — Data sufficiency & screen integrity  ·  status: ✅ DECIDED — **B** (grade-free re-run)

**Signer:** Ravi (Model Validator) · **2026-10-16** · entry_hash `d04b7ee5`

**Decision:** data sufficiency **emphatically met** (5,627 events / 23 features → **EPV ≈ 245**, the highest-powered run
of the corpus; the opposite of MSME's EPV ≈ 1.2 — no sufficiency caveat). **Additionally, exclude `int_rate` and
`installment` and re-run grade-free.** **Rationale:** *option B — int_rate is a re-encoding of the excluded grade.*

**Key finding (basis for the re-run):** on the first (rate-included) screen, `int_rate` was by far the strongest
feature (IV 0.322 "strong"; Shapley 0.073 ≈ 2.4× the next; alone → Gini 0.308). But **LendingClub sets `int_rate`
*from* `sub_grade`**, so `int_rate` is a continuous shadow of the grade excluded at G0 — a back-door that undermines
G0's "grade-free" intent. `installment` is a deterministic function of `int_rate`, `term` and `loan_amnt`, so it
carries the same shadow. Both excluded. `int_rate` is genuinely known at origination (not outcome leakage), so the
rate-included model is **retained as a comparison point** (`SHARP_LC_rate_comparison.md`) to quantify how much lift
came from LC's own pricing.

**Rate-included comparison (k=9, 10 cols):** Gini 0.387 / AUC 0.694; calibrated AUC 0.687, **ECE 0.0044** (well
calibrated). Stage-1: 10/23 passed. Selected: `int_rate, term, annual_inc, revol_util, inq_last_6mths, purpose,
funded_amnt, loan_amnt, addr_state[proxy], pub_rec`.

**Sentinel-leakage flag resolved:** `mths_since_last_delinq` (codes 96/97, 3.5× event-rate lift) **failed the Stage-1
screen and is not in any model** → no action beyond this record.

**Carry-forward concern (SIG-N, to G3):** with N ≈ 39,717, DeLong is hyper-sensitive — relative Gini loss falls below
the 5% tolerance by k=5 (4.26%), yet DeLong p stays < 0.05 until the full model, so the pre-registered rule mechanically
selects the near-full k. This large-sample behaviour is a selection-interpretation point for G3, not a method change (P8).

## G2 — Importance attribution  ·  status: ✅ DECIDED — **A** (retain `addr_state`; G4 disparity review)

**Signer:** Ravi (Model Validator) · **2026-10-16** · entry_hash `c95a3945`

**Decision:** accept the Shapley attribution; **retain `addr_state`** and **bind a geographic-disparity review at G4**.
**Rationale:** *retain the confirmed proxy to study it honestly, not hide it.*

**Attribution (grade-free, shadow bar 0.00104; all 8 players confirmed, no fragile players):**

| Rank | Player | Shapley | × bar |
|---|---|--:|--:|
| 1 | term | 0.0494 | 48× |
| 2 | revol_util | 0.0355 | 34× |
| 3 | annual_inc | 0.0288 | 28× |
| 4 | inq_last_6mths | 0.0225 | 22× |
| 5 | purpose | 0.0136 | 13× |
| 6 | grp[funded_amnt+loan_amnt] | 0.0130 | 13× |
| 7 | `addr_state` [proxy] | 0.0082 | 8× |
| 8 | pub_rec | 0.0070 | 7× |

Best decoy (shadow) 0.0012 — below bar. Clean real/noise separation.

**Grade-shadow comparison (the G1=B payoff):** grade-free Gini **0.358** (AUC 0.679) vs rate-included **0.387**
(AUC 0.694) → excluding LC's own pricing costs only **−0.029 Gini**; raw applicant features independently recover
**~92%** of discrimination. Publishable: LC's proprietary grade adds little separation beyond observable attributes.

**Binding condition (→ G4):** `addr_state` is a *confirmed real* geographic proxy (redlining risk). G4 must report a
**geographic-disparity assessment** and a **fairness-constrained replication** (model with `addr_state` removed)
alongside the retained-proxy model.

## G3 — Parsimony selection  ·  status: ✅ DECIDED — **B** (ratify k=8; report k=5)

**Signer:** Ravi (Model Validator) · **2026-10-16** · entry_hash `f85b8db1`

**Decision:** ratify the pre-registered **k=8** selection (9 columns, **Gini 0.358 / AUC 0.679**); **additionally report
the k=5 parsimony point** (Gini 0.341 / AUC 0.671) as a descriptive finding. **Rationale:** *method is fixed (P8);
report k=5 to show the parsimony story.*

**Selected model (k=8, 9 cols):** `term, revol_util, annual_inc, inq_last_6mths, purpose, funded_amnt, loan_amnt,
addr_state [proxy], pub_rec`.

**Parsimony curve (grade-free):**

| k | +feature | Gini | AUC | rel. loss | DeLong p |
|--:|---|--:|--:|--:|--:|
| 4 | inq_last_6mths | 0.330 | 0.665 | 7.74% | 0.0000 |
| **5** | purpose | **0.341** | **0.671** | 4.68% | 0.0000 |
| 6 | loan+funded_amnt | 0.346 | 0.673 | 3.37% | 0.0000 |
| 7 | addr_state | 0.352 | 0.676 | 1.56% | 0.0001 |
| **8** ✅ | pub_rec | **0.358** | **0.679** | 0.00% | 1.0000 |

**SIG-N (recorded):** relative Gini loss is ≤5% from **k=5** (4.68%), yet DeLong p stays <0.05 until k=8 purely because
N ≈ 39,717 makes the paired-AUC test hyper-sensitive. The rule behaves as written (selects k=8); **a 5-feature model
recovers ~95% of discrimination** — reported as a methodological point (with big data, effect size should govern
selection, not p-values). Not a method change.

**Escalated to G4:** (1) bound **geographic-disparity review** + **fairness-constrained replication** (drop
`addr_state`); (2) **HL-vs-ECE large-N watch** (HL may reject on N alone despite tiny ECE); (3) discrimination
**ceiling ≈ 0.358 Gini / 0.679 AUC**.

## G4 — Performance, calibration & fairness backtest  ·  status: ✅ DECIDED — **A** (no-geo primary; calibration clean)

**Signers:** Ravi (Risk Officer + Model Validator, dual) · **2026-10-16** · entry_hash `9901f49d`
**Held-out test:** 80/20 stratified (seed 42) — 7,944 loans / 1,125 defaults.

**Decision:** approve; **adopt the fairness-constrained no-geo model as primary** (drop `addr_state`), **retain the
with-geo model as a comparability benchmark**. Calibration is clean → **PDs usable as stated (no MoC-cal)**.
**Rationale:** *adopt no-geo model as primary.*

### 1. Discrimination (reliable, no overfit)
| | Gini | AUC |
|---|--:|--:|
| Selection | 0.358 | 0.679 |
| Held-out (with-geo) | 0.358 | 0.679 |
| **Held-out (NO-GEO, primary)** | **0.351** | **0.676** |

### 2. Calibration — CLEAN (SIG-N fear did not materialise)
HL g=10 **p=0.481**, g=5 **p=0.536** (both pass ≫0.05); **ECE 0.0020**; **8/9 grades in Wilson CI** (only BBB out —
obs 0.053 vs pred 0.035, mildly optimistic). Even an N-overpowered HL cannot reject → **LC PDs are usable as stated**,
the clean contrast to TH02 (HL-rejected, indicative-only).

| Grade | n | obs | Wilson 95% | pred | in CI |
|---|--:|--:|---|--:|:--:|
| AAA | 37 | .000 | [.000,.094] | .000 | ✅ |
| A | 84 | .024 | [.007,.083] | .019 | ✅ |
| BBB | 550 | .053 | [.037,.075] | .035 | ❌ |
| BB | 515 | .049 | [.033,.071] | .057 | ✅ |
| B | 2692 | .092 | [.082,.104] | .090 | ✅ |
| CCC | 2034 | .153 | [.138,.169] | .156 | ✅ |
| CC | 1920 | .245 | [.226,.265] | .243 | ✅ |
| C | 110 | .364 | [.280,.457] | .403 | ✅ |
| D | 2 | — | thin | .588 | ✅ |

### 3. Fairness — geographic disparity (binding condition from G2)
Model is **accurate within every region** (mean pred PD ≈ observed), so the gap is **disparate impact from true risk,
not model bias**. AIR on the internal masterscale "approve" grade (**indicative — no institution cutoff**):

| Region | obs default | AIR (with-geo) | AIR (**no-geo, primary**) |
|---|--:|--:|--:|
| Northeast (ref) | 12.8% | 1.000 | 1.000 |
| South | 13.5% | 0.876 ✅ | **0.961 ✅** |
| Midwest | 14.7% | **0.568 ❌** | **0.622 ❌** |
| West | 15.9% | 0.591 ❌ | **0.938 ✅** |
| **worst** | | **0.568 FAIL** | **0.622 FAIL** |

**Finding (publishable):** dropping the explicit geographic proxy **cures West & South** (West 0.591→0.938) and lifts
the worst AIR 0.568→0.622, but **Midwest still fails** — its higher true default rate flows through correlated features
(income, utilisation). **Explicit proxy removal is necessary but not sufficient** to eliminate disparate impact.

### 4. Fairness-constrained replication cost
Removing `addr_state` costs only **−0.007 Gini** (0.358→0.351) — the explicit redlining channel is removable at
near-zero performance cost, which is why the no-geo model is adopted as primary.

### Binding conditions carried to GF
- **GEO-AIR** — residual Midwest four-fifths failure (0.622) disclosed; impact is true-risk-driven, not bias; AIR is
  indicative (no institution cutoff). Never deploy without a jurisdiction-specific fairness review.
- **DQ-BBB** — BBB grade mildly optimistic (obs 5.3% vs pred 3.5%); monitor.
- **SIG-N** — selection at large N governed by effect size (k=5 ≈ 95%); reported.
- **LICENSING / VINTAGE** — citation gated on LendingClub reuse terms + true-vintage verification.
- **NEVER-DEPLOY** — research benchmark; no model here is fit for a live credit decision.

## G5 — Deliverables & decisioning  ·  status: ✅ DECIDED — **A** (standard config; no-geo deliverables)

**Signer:** Ravi (Model Owner) · **2026-10-16** · entry_hash `7c8d5e06`

**Decision:** standard deployment-governance config on the **no-geo primary model**; generate decisioning note +
6-case acceptance pack. **Rationale:** *standard config, generate deliverables on no-geo model.*

**Config:** `annual_inc` mandatory (blank→refer); incomplete_policy `refer`; exact additive WOE reason codes; PD
floor 0.03% / cap 99.9%; **no cutoff or pricing invented** (institution inputs, exogenous).

**Deliverables generated:**
- `AEGIS_LC_CUTOFF_POLICY.md` — decisioning note; carries NEVER-DEPLOY / LICENSING / VINTAGE / GEO-AIR / DQ-BBB / SIG-N.
- `acceptance_cases/lc.json` + `SAMPLE_RUNS_LC.md` — 6-case pack (4 real spanning repaid/defaulted; 2 synthetic
  best/worst). Confirms PD **floor (0.03%) and cap (99.9%) both bind**, reason codes coherent, `annual_inc`
  completeness gate enforced. Case PDs: R1 0.03% (AAA) → R2 10.2% (B) → R3 20.2% (CC) → R4 99.9% (D); S1 floor, S2 cap.
- `data/ml_lab/datasets/LC_nogeo.csv` — the cleaned 8-feature modelling frame (renderer input).

## GF — Final verdict  ·  status: ✅ SEALED — **GO-WITH-CONDITIONS**

**Signer:** Ravi (MAC Chair / CRO) · **2026-10-16** · entry_hash `1c280308`

**Verdict:** **GO-WITH-CONDITIONS** — approved as a MEDIUM-tier research benchmark; **never deploy**.

**Basis:** method validated end-to-end (21-feature pool → 8 confirmed players, grade-free, no fragile players,
proxies studied not hidden); **calibration clean** (HL p=0.48–0.54, ECE 0.0020 → PDs usable as stated, the clean
contrast to TH02); discrimination **weak but reliable** (held-out Gini 0.351 / AUC 0.676 = selection); fairness
weakness **disclosed and mitigated** (no-geo primary; residual Midwest four-fifths miss is true-risk-driven, not bias).

**Contribution to the corpus:** the **highest-EPV run** (≈245) — the anti-MSME: abundant data yet only modest Gini,
proving the verdict tracks calibration + fairness + tier, **not** Gini. Joins the crossover cluster (LC 0.351, LOAN
0.343, TH02 0.272 all GO-WITH-CONDITIONS, all **below** the NO-GO MSME 0.435). Two original findings: (1) LendingClub's
own grade adds only ~0.03 Gini over raw applicant features; (2) explicit proxy removal is **necessary but not
sufficient** for fairness.

**Binding conditions:** NEVER-DEPLOY · LICENSING (confirm LC reuse terms before citation) · VINTAGE (verify 2009–2011
not 2019) · GEO-AIR (residual Midwest disparate impact disclosed; indicative, no institution cutoff) · DQ-BBB (grade
BBB mildly optimistic; monitor) · SIG-N (large-N selection governed by effect size; k=5 ≈ 95%).

**Deliverables:** `SHARP_LC.md` (grade-free) · `SHARP_LC_rate_comparison.md` · `AEGIS_LC_CUTOFF_POLICY.md` ·
`acceptance_cases/lc.json` + `SAMPLE_RUNS_LC.md` · `data/ml_lab/datasets/LC_nogeo.csv`.

---

**Run complete — 11th governed run. Full chain:**
`GEN-LC0 → 9b382c00 → d04b7ee5 → c95a3945 → f85b8db1 → 9901f49d → 7c8d5e06 → 1c280308`.
