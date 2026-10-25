# Riley et al. minimum sample size — reported sufficiency diagnostic (SHARP v3.1 / AEGIS G1)

**Added:** 2026-10-17 (SHARP v3 → v3.1). **Status:** *reported diagnostic* at G1, **alongside** EPV —
**never an auto-reject**. A shortfall is a disclosed caveat that the MAC weighs; it does not fail the gate by
itself (consistent with AEGIS P8 "gates decide governance, not analytics" and the user instruction to add this
as a reported, droppable-later diagnostic).

**Engine:** `backend/riley_minsize.py` (Python, venv310; numpy + scipy only — no R dependency, consistent with
the Windows/Python-only project rule). **Regenerable record:** `sharp_runs/riley_retro.json`.

---

## 1. Why add it (what EPV cannot see)

EPV (events ÷ parameters ≥ 10; Peduzzi 1996) counts events but is **blind to signal strength**. Riley et al.
(2019/2020) tie the required sample size to the model's *anticipated discrimination* (via the Cox-Snell R²),
so a weak-signal model is correctly told it needs **more** rows even when its EPV looks generous. The two are
reported together: EPV as the familiar rule of thumb, Riley as the signal-aware refinement.

## 2. The three binary criteria (fixed targets — identical for every dataset)

The required N is the **largest** of three criterion-specific minimums; each is solved against a fixed target.

| Criterion | Controls | Minimum target | Formula (P = parameters, φ = prevalence, S = shrinkage) |
|---|---|---|---|
| **B1** | overall default-rate precision | 95% CI half-width **≤ 0.05** | n = (1.96/0.05)²·φ(1−φ) |
| **B3** | overfitting (shrinkage) | uniform shrinkage **S ≥ 0.90** | n = P / [(S−1)·ln(1 − R²cs/S)] |
| **B4** | optimism in apparent R² | expected optimism **≤ 0.05** (Nagelkerke) | n = P / [(S₄−1)·ln(1 − R²cs/S₄)], S₄ = R²nag/(R²nag + 0.05) |

**N_required = max(B1, B3, B4).** Verdict: **meets** if N_actual ≥ N_required, else **short**.
max(R²cs) = 1 − exp(2·[φ·lnφ + (1−φ)·ln(1−φ)]); R²nag = R²cs / max(R²cs).

**R²cs source.** For forward use at G1 (before a model is fit) only an *anticipated C-statistic* is available,
so R²cs is obtained from the C-statistic + prevalence by the **Riley–Van Calster–Collins (2020)** seeded
simulation — the same route `pmsampsize`'s `cstatistic=` option uses. The retrospective below feeds each run's
*observed* selection-stage C-statistic as that anticipated value, so the forward gate and the retrospective use
one identical engine.

**Parameter count P.** Taken as the **selected-feature count** (= β count for the WOE-logistic model, one
coefficient per feature). Riley's P is strictly "candidate parameters considered"; using the Stage-2 screened
pool would raise every bar. Selected-P is used as primary because SHARP's selection is pre-registered and
penalised, not a free search — but the stricter candidate-pool view is acknowledged.

## 3. Engine validation (against the primary sources, before any real figure)

| Check | Computed | Published |
|---|---|---|
| max(R²cs) @ prev 0.5 / 0.3 / 0.05 | 0.750 / 0.705 / 0.328 | 0.75 / 0.71 / 0.33 (BMJ m441) |
| B1 @ prev 0.5 / 0.1 / 0.2 | 385 / 139 / 246 | 385 / 139 / 246 (BMJ m441) |
| B3 @ R²cs 0.05, P 30 | 5,249 | 5,249 (BMJ m441) |
| **BMJ Example 1 (pre-eclampsia)** | **N=5,249, events=263, EPP=8.75** | **5,249 / 263 / 8.75** |
| C→R²cs sim @ C=0.89, prev 0.174 | R²cs = 0.291 | pmsampsize manual pairs it with **0.288** |

## 4. Retrospective across the 11 governed runs

Inputs are the **recorded** values from each `SHARP_<D>.md`: full-dataset event rate (φ), selected-column
count (P), and selection-stage OOF Gini → C-statistic = (Gini+1)/2. Bold = the governing (max) criterion.

| Dataset | N actual | φ | P | AUC | R²cs | B1 | B3 | B4 | **N req** | EPP@req | EPV act | Verdict |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|
| HMEQ | 5,960 | .200 | 11 | .907 | .343 | 246 | 230 | **278** | **278** | 5.0 | 108 | ✅ meets |
| CREDITRISK | 32,581 | .218 | 6 | .880 | .311 | **263** | 142 | 151 | **263** | 9.6 | 1,185 | ✅ meets |
| GMSC | 149,391 | .067 | 8 | .852 | .118 | 97 | **570** | 384 | **570** | 4.8 | 1,251 | ✅ meets |
| HELOC | 10,459 | .522 | 17 | .793 | .250 | 384 | **522** | 385 | **522** | 16.0 | 321 | ✅ meets |
| TAIWAN | 30,000 | .221 | 14 | .769 | .156 | 265 | **737** | 388 | **737** | 11.6 | 474 | ✅ meets |
| GERMAN | 1,000 | .300 | 5 | .766 | .180 | **323** | 224 | 126 | **323** | 19.4 | 60 | ✅ meets |
| **MSME** | **1,707** | .060 | 15 | .717 | .036 | 87 | **3,654** | 802 | **3,654** | 14.6 | **6.8** | ❌ **SHORT 1,947** |
| LC | 39,717 | .142 | 9 | .679 | .050 | 187 | **1,581** | 310 | **1,581** | 24.9 | 625 | ✅ meets |
| LOAN | 9,578 | .160 | 7 | .671 | .050 | 207 | **1,220** | 230 | **1,220** | 27.9 | 219 | ✅ meets |
| TH02 | 1,225 | .264 | 6 | .636 | .045 | 299 | **1,170** | 169 | **1,170** | 51.4 | 54 | ✅ meets (+55) |
| PAK | 50,000 | .261 | 6 | .574 | .013 | 297 | **4,041** | 172 | **4,041** | 175.7 | 2,173 | ✅ meets |

## 5. Reading

1. **Riley and EPV are concordant on the one run that matters.** MSME is the *only* run short of Riley (needs
   3,654, has 1,707) and the *only* run failing EPV (6.8 < 10) — and it was already the **NO-GO·HIGH** verdict.
   The two sufficiency diagnostics agree, and the single failure is the case already rejected.
2. **Riley penalises weak signal, which EPV cannot.** PAK has a huge EPV (2,173) yet needs 4,041 rows, purely
   because AUC 0.574 → R²cs 0.013 makes the shrinkage criterion (B3) demand volume to stabilise tiny
   coefficients. B3 governs 8 of 11 runs; B1 only where the model is strong *and* lean (CREDITRISK, GERMAN);
   B4 only HMEQ.
3. **It surfaces thin margins.** TH02 passes by only **+55 rows** — technically adequate, worth disclosing;
   EPV (54) does not convey the tightness as sharply.

## 6. How to read any verdict yourself (worked on MSME)

1. Three criterion-minimums: B1 = 87, B3 = 3,654, B4 = 802.
2. Governing value = **max** = 3,654 (B3 / shrinkage).
3. N_actual = 1,707 < 3,654 → **SHORT by 1,947**.
4. EPV cross-check: events = 1,707 × 0.060 = 102; 102 ÷ 15 = **6.8 < 10** → EPV also fails. Both agree.

## 7. Citations

- **Riley RD, Snell KIE, Ensor J, et al. (2019).** Minimum sample size for developing a multivariable
  prediction model: PART II — binary and time-to-event outcomes. *Statistics in Medicine* 38(7):1276–1296.
  doi:10.1002/sim.7992.
- **Riley RD, Ensor J, Snell KIE, et al. (2020).** Calculating the sample size required for developing a
  clinical prediction model. *BMJ* 368:m441. doi:10.1136/bmj.m441.
- **Riley RD, Van Calster B, Collins GS (2020).** A note on estimating the Cox-Snell R² from a reported
  C-statistic (AUROC) to inform sample size calculations for developing a prediction model with a binary
  outcome. *Statistics in Medicine* 39(21):2957–2966.
- **van Smeden M, Moons KGM, de Groot JAH, et al. (2019).** Sample size for binary logistic prediction models:
  beyond events per variable criteria. *Statistical Methods in Medical Research* 28(8):2455–2474.
- **Peduzzi P, Concato J, Kemper E, et al. (1996).** A simulation study of the number of events per variable in
  logistic regression analysis. *Journal of Clinical Epidemiology* 49(12):1373–1379. *(EPV comparator.)*
- Software reference for the criteria: **pmsampsize** (Ensor J., CRAN) — our `backend/riley_minsize.py`
  re-implements its binary criteria natively and is validated against the BMJ m441 worked examples above.

**Caveat (recorded honestly).** Pavlou et al. (medRxiv 2026) report that the closed-form pmsampsize
recommendations can *under*-estimate required N when discrimination is very high (C ≳ 0.85); HMEQ (C 0.907),
CREDITRISK (0.880) and GMSC (0.852) sit in that zone, so their Riley minimums are, if anything, slightly
optimistic — all three clear their bar by orders of magnitude regardless, so no verdict is affected.

---

## 8. Update 2026-10-25 - the candidate pool is the governing basis

**Convention (runs after this date; earlier records not re-opened).** Riley's P is the number of candidate
parameters considered *before* data-driven selection. EPV and the Riley minimum N are therefore **governed on the
candidate pool** = every column that entered Stage 1 after the outcome-blind Stage-0 eligibility step. The
figures after IV screening, after Shapley (players) and after selection are shown beside it as informational:
IV screening, Shapley confirmation and parsimony selection all use the outcome, so a count reduced by them cannot
lower the requirement. Correlation grouping is outcome-blind and is shown (players basis) but does not govern.
The selected-P figures in section 4 were the primary basis until this date.

**Retrospective on the 14-dataset corpus.** Same engine and inputs as section 4 (prevalence and selection-stage
C-statistic from the records; C-statistic of the selected model used for the pool figure, since the pool model is
never fitted), with P = the pool size from the corpus table. N required varies by about +/-2 against section 4
because the R2cs simulation is seeded on rounded inputs. SBA, POLISH and MORTGAGE (not in section 4) are added
from their SHARP records.

| Dataset | N | N req (selected P) | Pool P | **N req (pool)** | EPV (selected) | EPV (pool) | Meets pool basis? |
|---|--:|--:|--:|--:|--:|--:|:--|
| SBA | 2,102 | 338 | 19 | 380 | 62 | 36.1 | yes |
| HMEQ | 5,960 | 278 | 12 | 304 | 108 | 99.1 | yes |
| POLISH-5y | 7,027 | 3,212 | 64 | 5,555 | 7.3 | 4.2 | yes |
| CREDITRISK | 32,581 | 263 | 9 | 263 | 1185 | 789.9 | yes |
| GMSC | 149,391 | 570 | 9 | 642 | 1251 | 1112.1 | yes |
| HELOC | 10,459 | 522 | 23 | 706 | 321 | 237.3 | yes |
| TAIWAN | 30,000 | 737 | 20 | 1,052 | 474 | 331.8 | yes |
| GERMAN | 1,000 | 323 | 17 | 760 | 60 | 17.6 | yes |
| MORTGAGE | 50,049 | 358 | 10 | 597 | 2526 | 1515.5 | yes |
| MSME | 1,707 | 3,654 | 87 | 21,200 | 6.8 | 1.2 | **SHORT** |
| LC | 39,717 | 1,581 | 21 | 3,690 | 625 | 268.0 | yes |
| LOAN | 9,578 | 1,220 | 13 | 2,267 | 219 | 118.0 | yes |
| TH02 | 1,225 | 1,170 | 14 | 2,731 | 54 | 23.1 | **SHORT** |
| PAK | 50,000 | 4,041 | 39 | 26,262 | 2173 | 334.4 | yes |

**Reading.** (1) 12 of 14 meet Riley on the pool basis; MSME (needs 21,200, has 1,707) is short, as before.
(2) **TH02 is newly short** (needs 2,731, has 1,225; it passed by +55 on the selected basis). Its sealed verdict
(GO-WITH-CONDITIONS) is *not* altered - sufficiency is a reported diagnostic, never an auto-reject - but R6 would be
PARTIAL on the pool basis. (3) POLISH-5y's earlier figure of 5,141 used P=60 (the screened count), not the
selected count (37) as the other rows did; on the selected basis it is 3,212, on the pool basis 5,555 (meets,
margin 1.26x). (4) EPV on the pool is below 10 for POLISH-5y (4.2) and MSME (1.2).
