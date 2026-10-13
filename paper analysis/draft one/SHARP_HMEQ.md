# SHARP results — HMEQ (Home Equity)

**Methodology:** SHARP (Shapley Ranking with Parsimony), v3 — see `METHODOLOGY.md`.
**Run id:** `sharp_20261011_hmeq` · **Date:** 2026-10-11 · **Machine record:** `sharp_runs/sharp_20261011_hmeq.json` (sha256[:16] `1c5d20e73932b048`)
**Status:** ✅ complete — first clean SHARP run recorded for the Results section.

> Every figure below traces to the JSON record above, which is regenerable from `data/ml_lab/datasets/hmeq.csv`
> with the fixed config. No numbers are carried over from the v2 era except where explicitly compared.

## Fixed configuration (stated for reproducibility)

| Parameter | Value |
|---|---|
| Primary learner | `woe_logistic` (deterministic, interpretable) |
| Secondary learner | `xgboost` (robustness; `scale_pos_weight=1`, i.e. off) |
| Value function | `auc` |
| `random_state` | 42 |
| CV folds | 5 (stratified, shuffled) |
| Grouping (clustering) threshold | 0.7 on 1−|Spearman ρ| |
| Shadows / quantile / confirm-freq | 10 / 0.95 / ≥0.80 |
| Shapley mode | sampled (200 draws; 20 players > exact cap 15) |
| Selection tolerance | DeLong p ≥ 0.05 **and** relative Gini loss ≤ 5% |

---

## Stage 0 — data profile & governance

**Profile:** 5,960 rows · 12 features (+target) · positives (bad=1) 1,189 · **event rate 0.1995**.

**Eligibility:** 12/12 **permissible** — no name-matched protected/proxy attributes, so nothing to warn-and-retain (contrast German Credit). **Availability:** 7 origination, 5 behavioural (DEROG, DELINQ, CLAGE, NINQ, CLNO — bureau-file fields).

**Leakage / value-code sentinels:** none.

**Missingness-as-signal audit** (is "field blank" itself predictive?):

| Column | Missing % | Bad\|missing | Bad\|present | Lift |
|---|---:|---:|---:|---:|
| **DEBTINC** | 21.26% | 0.6204 | 0.0859 | **7.22×** |
| VALUE | 1.88% | 0.9375 | 0.1854 | 5.06× |
| CLAGE | 5.17% | 0.2532 | 0.1966 | 1.29× |
| CLNO | 3.73% | 0.2387 | 0.1980 | 1.21× |
| MORTDUE | 8.69% | 0.2046 | 0.1990 | 1.03× |
| REASON | 4.23% | 0.1905 | 0.1999 | 0.95× |
| NINQ | 8.56% | 0.1471 | 0.2044 | 0.72× |
| YOJ | 8.64% | 0.1262 | 0.2064 | 0.61× |
| DELINQ | 9.73% | 0.1241 | 0.2076 | 0.60× |
| DEROG | 11.88% | 0.1229 | 0.2098 | 0.59× |
| JOB | 4.68% | 0.0824 | 0.2052 | 0.40× |

**Finding F1 — missingness is informative and is preserved, not imputed away.** Non-disclosure of DEBTINC implies a 62% bad rate vs 8.6% when present (7.2× lift). SHARP's WOE binning gives "missing" its own bin, so this signal enters the model instead of being destroyed by mean-imputation. *Lift = bad-rate(missing) / bad-rate(present); 1.0 = no signal.*

---

## Stage 1 — univariate screening (IV + reliability gate + shape check)

| Column | IV (WOE) | IV q5 | IV q10 | IV q20 | Non-monotonic | Cramér's V | Min expected | Escalation | **Passes** |
|---|---:|---:|---:|---:|:--:|---:|---:|---|:--:|
| DEBTINC | 1.8305 | 1.7382 | 1.8693 | 1.9694 | No | 0.5621 | 93.6 | none | ✅ |
| DELINQ | 0.5653 | 0.4194 | 0.4194 | 0.4524 | No | 0.3343 | 109.1 | none | ✅ |
| VALUE | 0.4464 | 0.4149 | 0.4679 | 0.5061 | No | 0.2820 | 22.3 | none | ✅ |
| DEROG | 0.3859 | 0.0364 | 0.2766 | 0.2766 | No | 0.2811 | 57.9 | none | ✅ |
| CLAGE | 0.2327 | 0.2224 | 0.2338 | 0.2501 | No | 0.1895 | 61.4 | none | ✅ |
| NINQ | 0.1732 | 0.1445 | 0.1656 | 0.1672 | No | 0.1808 | 78.2 | none | ✅ |
| LOAN | 0.1584 | 0.0972 | 0.1602 | 0.2270 | **Yes** | 0.1759 | 59.6 | model_check_shape (rescue) | ✅ |
| JOB | 0.1230 | 0.1237 | 0.1237 | 0.1237 | No | 0.1345 | 55.7 | none | ✅ |
| YOJ | 0.0664 | 0.0443 | 0.0711 | 0.0959 | No | 0.0988 | 97.4 | none | ✅ |
| CLNO | 0.0463 | 0.0257 | 0.0639 | 0.0867 | **Yes** | 0.0923 | 44.3 | model_check_shape (rescue) | ✅ |
| MORTDUE | 0.0436 | 0.0520 | 0.0533 | 0.0868 | No | 0.0852 | 103.3 | none | ✅ |
| REASON | 0.0086 | 0.0086 | 0.0086 | 0.0086 | No | 0.0375 | 50.3 | none | ❌ |

**Result: 11 of 12 pass; only REASON is dropped** (IV 0.0086 unpredictive, Cramér's V 0.0375 negligible, stable across all binnings). Reproduces the v2 drop decision exactly.

*IV bands: <0.02 unpredictive · 0.02–0.1 weak · 0.1–0.3 medium · 0.3–0.5 strong · >0.5 suspiciously strong. Cramér's V: ~0.1 small · ~0.3 medium · ~0.5 large.*

**Finding F2 — LOAN and CLNO are non-monotonic (U-shaped) and are *rescued*, never vetoed.** Both have modest monotonic IV but a U-shaped bad-rate; the shape-triggered model-check confirms signal a single monotonic bin misses. This exercises the corrected escalation logic (escalation can only rescue). Everything cleared the reliability gate (min-expected 22–109 ≫ 5) and nothing was binning-sensitive, so these IVs are not binning artefacts.

---

## Stage 2 — order-invariant Shapley importance (shadow-null retention)

11 columns → **10 players** (MORTDUE+VALUE grouped, Spearman-correlated). Sampled Shapley (200 draws), 10 shadows. **Shadow-null bar = 0.000930.**

| Player | #cols | Shapley | Confirm freq | **Confirmed** | *diag BH p* | *diag Cohen's d* |
|---|--:|--:|--:|:--:|--:|--:|
| DEBTINC | 1 | 0.15349 | 1.000 | ✅ | 4.2e-74 | 2.11 |
| DELINQ | 1 | 0.06406 | 1.000 | ✅ | 3.9e-42 | 1.26 |
| DEROG | 1 | 0.03732 | 1.000 | ✅ | 3.6e-32 | 1.02 |
| grp[MORTDUE+VALUE] | 2 | 0.03133 | 1.000 | ✅ | 4.2e-34 | 1.07 |
| CLAGE | 1 | 0.02954 | 1.000 | ✅ | 3.1e-24 | 0.83 |
| JOB | 1 | 0.02542 | 1.000 | ✅ | 5.0e-28 | 0.92 |
| NINQ | 1 | 0.02188 | 1.000 | ✅ | 1.1e-19 | 0.73 |
| LOAN | 1 | 0.01831 | 1.000 | ✅ | 4.2e-18 | 0.68 |
| YOJ | 1 | 0.01248 | 1.000 | ✅ | 1.9e-18 | 0.69 |
| CLNO | 1 | 0.01191 | 1.000 | ✅ | 1.5e-33 | 1.05 |
| *__shadow__7_LOAN* | 1 | *0.00138* | *0.9995* | ❌ | *2.9e-10* | *0.47* |
| *(9 more shadows)* | 1 | *≤0.00038* | ≤0.0005 | ❌ | *mixed* | *mixed* |

**Result: all 10 players confirmed.** The weakest real player (CLNO 0.0119) is **12.8×** the shadow bar.

**Finding F3 — the shadow-null correctly rejects a "hugely significant" noise column.** `__shadow__7_LOAN` is a permuted, signal-free copy of LOAN, yet earned BH p = 2.9e-10, Cohen's d = 0.47, and beat the bar in 99.95% of resamples. Under v2's withdrawn "BH-significant + Cohen's d" rule it would have been **confirmed** — pure noise. SHARP rejects it because it is a shadow sitting at the 0.95 null quantile. *The diag BH-p / Cohen's-d columns are reported only, not used for any decision; they are shown precisely to make this point.* One shadow exceeding the bar is expected: a 0.95 bar admits ~1-in-20 shadows by design, and the lowest real player still beats it 8.6×.

---

## Stage 3 — selection (parsimony curve + pre-declared tolerance)

Out-of-fold, WOE-logistic. Full-candidate (k=10) Gini = 0.8133 / AUC = 0.9066.

| k | +Player | Gini | AUC | KS | Brier | ECE | DeLong p vs full | rel. Gini loss |
|--:|---|--:|--:|--:|--:|--:|--:|--:|
| 1 | DEBTINC | 0.6341 | 0.8170 | 0.5774 | 0.1095 | 0.0003 | 0.0e+00 | 22.0% |
| 2 | DELINQ | 0.7142 | 0.8571 | 0.6031 | 0.1016 | 0.0084 | 0.0e+00 | 12.2% |
| 3 | DEROG | 0.7373 | 0.8687 | 0.6294 | 0.0976 | 0.0086 | 0.0e+00 | 9.3% |
| 4 | grp[MORTDUE+VALUE] | 0.7701 | 0.8850 | 0.6393 | 0.0930 | 0.0121 | 1.0e-12 | 5.3% |
| 5 | CLAGE | 0.7971 | 0.8986 | 0.6462 | 0.0889 | 0.0106 | 8.9e-06 | 2.0% |
| 6 | JOB | 0.8041 | 0.9021 | 0.6493 | 0.0876 | 0.0095 | 7.7e-04 | 1.1% |
| 7 | NINQ | 0.8052 | 0.9026 | 0.6514 | 0.0871 | 0.0077 | 1.3e-03 | 1.0% |
| 8 | LOAN | 0.8057 | 0.9028 | 0.6434 | 0.0869 | 0.0098 | 1.2e-03 | 0.9% |
| 9 | YOJ | 0.8074 | 0.9037 | 0.6502 | 0.0865 | 0.0071 | 6.1e-04 | 0.7% |
| **10** | **CLNO** | **0.8133** | **0.9066** | **0.6537** | **0.0861** | **0.0103** | **1.00** | **0.0%** |

**Decision: selected k = 10 → all 11 screened columns** `[DEBTINC, DELINQ, DEROG, MORTDUE, VALUE, CLAGE, JOB, NINQ, LOAN, YOJ, CLNO]`. Gini 0.8133, relative loss 0.0%, DeLong p = 1.0.

**Finding F4 — no parsimony reduction is statistically defensible at this sample size; the two tolerance criteria disagree and the stricter (AND) governs.** On ≤5%-Gini-loss *alone*, k=5 (6 columns) qualifies (loss 2.0%). But DeLong, powerful at n≈6,000, rejects every proper subset (k=9 p = 6.1e-4). Because the pre-registered rule is **AND**, SHARP returns the full screened set rather than claim a 6-column model is equivalent. This is the methodology refusing to overstate parsimony when the data can tell the difference — and it independently reproduces v2's 11-column answer by a defensible route.

---

## Stage 4 — calibration (isotonic, held-out)

Selected 11-column model. Test = 1,192 rows, base rate 0.1997, baseline Brier 0.1598.

| Learner | | AUC | Gini | Brier | ECE |
|---|---|--:|--:|--:|--:|
| WOE-logistic (primary) | raw | 0.9012 | 0.8025 | 0.0894 | 0.0359 |
| | calibrated | 0.9005 | 0.8010 | 0.0887 | **0.0204** |
| XGBoost (secondary) | raw | 0.9419 | 0.8839 | 0.0708 | 0.0298 |
| | calibrated | 0.9409 | 0.8817 | 0.0711 | **0.0213** |

**Finding F5 — with `scale_pos_weight` off, both models are already well-calibrated; isotonic tightens ECE (−43% / −28%) without moving AUC.** XGBoost raw ECE 0.0298 (not the ~0.08 of the v2 era) is direct evidence that most of v2's calibration damage was self-inflicted by class-reweighting, as §7.1 states. XGBoost holdout AUC 0.9419 reproduces the v2 recorded 0.9438 within noise.

---

## Stage 4b — per-grade calibration backtest (AEGIS condition CP4; CRE36.122–123)

Added 2026-10-13 to discharge AEGIS condition CP4. Held-out 80/20 stratified split (`random_state=42`),
model's calibrated PD (no governance-floor overlay), mapped to the internal master scale
(`backend/rating_masterscale.py`). Test n=1,192, event rate 0.1997, **held-out AUC 0.9000**.

| Grade | n | Expected PD | Realised | Realised 95% CI (Wilson) | Within? |
|---|--:|--:|--:|---|:--:|
| AAA | 150 | 0.21% | 0.67% | [0.12%, 3.68%] | ✅ |
| AA | 158 | 0.92% | 1.90% | [0.65%, 5.43%] | ✅ |
| A | 164 | 1.16% | 3.05% | [1.31%, 6.94%] | ⚠ under-predict (thin, 5 defaults) |
| BBB | 25 | 2.83% | 0.00% | [0.00%, 13.32%] | ✅ |
| B | 243 | 8.18% | 8.64% | [5.72%, 12.85%] | ✅ |
| CCC | 174 | 17.75% | 18.39% | [13.34%, 24.81%] | ✅ |
| CC | 27 | 22.68% | 29.63% | [15.85%, 48.48%] | ✅ |
| C | 79 | 43.26% | 46.84% | [36.24%, 57.73%] | ✅ |
| D | 172 | 82.21% | 76.16% | [69.27%, 81.91%] | ⚠ over-predict (conservative) |

**Overall held-out ECE (10-bin) = 0.0239** (reproduces the Stage-4 ~0.020). **Hosmer-Lemeshow χ²=14.51,
df=8, p=0.069 → calibration not rejected at the 5% level.** 7/9 grades pass (expected PD inside the realised
95% CI); the per-decile view passes 8/10. The two exceptions are a thin very-low-risk cell (grade A, mild
under-prediction) and conservative over-prediction at grade D (the safe direction). Single-split result —
re-run at each retrain (the calibration-validation step underpinning the fixed grade/cutoff policy in
`AEGIS_HMEQ_CUTOFF_POLICY.md`).

---

## One-paragraph summary (for the paper)

On HMEQ (5,960 rows, 19.95% bad), SHARP screens out one of twelve columns (REASON; IV 0.009) and confirms the remaining eleven as order-invariantly important, each clearing a shadow-feature null by at least 12.8×. A permuted noise column that would have passed v2's significance rule (BH p = 2.9e-10) is correctly rejected by the shadow bar. The pre-declared selection tolerance (DeLong-indistinguishable from the full model **and** ≤5% relative Gini loss) returns the full eleven-column set, because at this sample size DeLong detects the loss from dropping even the weakest feature — SHARP therefore declines to claim a smaller model, converging on the v2 column set by a defensible route. The selected model calibrates cleanly (WOE-logistic Gini 0.80 / ECE 0.020; XGBoost Gini 0.88 / ECE 0.021). HMEQ is the clean, non-redundant benchmark where honest parsimony ≈ zero and missingness itself (DEBTINC non-disclosure → 7.2× lift) is a preserved, dominant signal.

---

## Appendix A — illustrative scoring & explanation (worked example)

Applying the **selected 11-feature WOE-logistic model, isotonic-calibrated** (intercept −1.378; portfolio
average PD 0.1995). WOE-logistic is additive in log-odds, so the score decomposes exactly:

`log-odds(default) = intercept + Σ ( coefⱼ × WOEⱼ(applicant) )`

Each feature's contribution is exactly `coef × WOE` — a faithful decomposition, not a post-hoc
approximation. WOE > 0 = safer-than-average bin; contribution > 0 raises risk.

### Applicant A — impaired-credit file
Requests $15,000 on a $70,000 home ($50,000 mortgage due); DTI 42%, 1 derogatory, 2 delinquent lines,
3 recent inquiries, 3 years on job, CLAGE 120 mo, 15 lines, JOB Other.
**Calibrated PD = 0.851** (≈4.3× the portfolio average).

| Feature | Value | WOE | Contribution | Reading |
|---|---|--:|--:|---|
| DELINQ | 2 | −1.6729 | +1.5257 | 2 delinquent lines — dominant adverse factor |
| DEROG | 1 | −0.9358 | +0.6661 | a derogatory report on file |
| CLAGE | 120 | −0.3398 | +0.3181 | credit history shorter than the safe cohort |
| YOJ | 3 | −0.2377 | +0.2160 | short job tenure |
| NINQ | 3 | −0.4098 | +0.1843 | several recent inquiries |
| JOB | Other | −0.1924 | +0.1797 | lower-stability job category |
| DEBTINC | 42 | −0.1412 | +0.1307 | DTI slightly above safe band |
| LOAN | 15000 | +0.0010 | −0.0003 | neutral |
| MORTDUE | 50000 | −0.0305 | −0.0093 | neutral |
| VALUE | 70000 | +0.0652 | −0.0590 | property value mildly protective |
| CLNO | 15 | +0.0891 | −0.0927 | reasonable line count — mildly protective |

Sum of contributions +3.059 + intercept −1.378 = logit 1.681 → raw PD 0.843 → calibrated 0.851 (reconstructs exactly).
**Adverse-action reason codes** = the largest positive contributions in order: (1) delinquent credit lines,
(2) derogatory report, (3) length of credit history, (4) job tenure — all Stage-0 permissible reasons.

### Applicant C — strong, clean file (contrast)
$10,000 on a $120,000 home, DTI 28%, 0 derogatory/delinquent/inquiries, 12 years on job, ProfExe.
**Calibrated PD = 0.006.** Every feature protective; largest mitigant is DEBTINC = 28 (WOE +1.447,
contribution −1.339) — a low, *disclosed* debt-to-income.

### Applicant B — thin file (Finding F1 in action)
Identical to Applicant A, but **DEBTINC undisclosed (missing)**.

| | DEBTINC | WOE | Contribution | Calibrated PD |
|---|---|--:|--:|--:|
| Applicant A | 42 (disclosed, high) | −0.1412 | +0.1307 | 0.851 |
| Applicant B | missing | −1.8805 | +1.7397 | 0.962 |

Not disclosing DTI is penalised ~13× harder than disclosing a *high* one, because the data show missing
DEBTINC → 62% bad rate (Stage 0). A mean-imputation pipeline would erase this and mis-score Applicant B as
near-average DTI; SHARP keeps "missing" as its own WOE bin, so the signal survives and remains explainable.

> **Reproducibility / honesty note.** These figures are from the fixed-config model fit on all 5,960 rows for
> demonstration (generalisation estimated by the Stage-4 holdout metrics above). A first scoring attempt was
> discarded: a dtype mismatch routed the discrete count features (DEROG/DELINQ/NINQ/CLNO) to a fallback WOE
> bin, so a clean file and an impaired file received identical penalties from those features. The error was
> caught (a 0-derogatory applicant cannot carry a 2-derogatory penalty), the dtype alignment fixed, and only
> the corrected decomposition above is recorded.

---

## Appendix B — Finding F6: the "missing = good news" trap (and closing it)

A natural concern: if an applicant supplies *fewer* attributes, the risk-raising contributions from the
omitted fields disappear, so the applicant could look safer simply by disclosing less. We tested this
directly on the selected HMEQ model.

### The missing bin's direction is data-driven, per column

The WOE of each column's `__missing__` bin is learned, so omission looks good for some columns and bad for
others:

| Column | Missing-bin WOE | Contribution if omitted | Effect of **omitting** |
|---|--:|--:|---|
| VALUE | −4.098 | +3.713 | RAISES risk (missing looks bad) |
| DEBTINC | −1.881 | +1.740 | RAISES risk (missing looks bad) |
| CLAGE | −0.308 | +0.288 | RAISES risk |
| CLNO | −0.230 | +0.239 | RAISES risk |
| LOAN | 0.000 | 0.000 | neutral (never missing in training) |
| MORTDUE | −0.032 | −0.010 | ~neutral |
| NINQ | +0.368 | −0.166 | LOWERS risk (missing looks good) ⚠ |
| DEROG | +0.576 | −0.410 | LOWERS risk ⚠ |
| YOJ | +0.545 | −0.496 | LOWERS risk ⚠ |
| DELINQ | +0.564 | −0.515 | LOWERS risk ⚠ |
| JOB | +1.020 | −0.953 | LOWERS risk ⚠ |

For 5 of 11 columns — the payment-history / stability fields — omitting the value lowers predicted risk.

### The trap, demonstrated (impaired Applicant A, scoring-time flooring off vs on)

| Applicant A scenario | PD, no mitigation | PD, adverse-floor on |
|---|--:|--:|
| full honest disclosure | 0.8514 | 0.8514 |
| hides DELINQ | 0.4000 | 0.8514 |
| hides DEROG | 0.7188 | 0.8750 |
| **hides DELINQ + DEROG** | **0.1504** (flips to approve) | 0.8750 |
| hides DELINQ + DEROG + NINQ | 0.1504 | 0.9130 |
| hides DELINQ + DEROG + NINQ + YOJ + JOB | **0.0157** (pristine) | 0.9600 |

Without mitigation, an impaired borrower who **withholds** their delinquency and derogatory history flips
from PD 0.85 (decline) to PD 0.15 (approve); hide five fields and PD is 0.016. **This is a genuine failure
mode.**

### The nuance that partly contains it

It is **not** universally true that less information = safer. A **fully-blank application (all 11 fields
missing) scores PD 0.8636** — well above the 0.1995 base rate — because the two highest-weight columns
(VALUE, DEBTINC) treat missing as *bad* and dominate. The trap is therefore **selective**: it requires
strategically omitting the specific fields whose missing bin is protective while still supplying the rest.

### Root cause

MNAR (missing-not-at-random) + correlation ≠ causation. In the HMEQ history, rows with blank DEROG/DELINQ
genuinely defaulted *less* (lift 0.59–0.60, Stage 0). WOE faithfully encodes that correlation, but it almost
certainly reflects how the data was collected (clean/pre-screened files whose bureau detail was never keyed
in), not a causal law that withholding adverse history makes a borrower safe. For HMEQ specifically the risk
is softened because DEROG/DELINQ/NINQ are **bureau-pulled** (the lender obtains them; the applicant cannot
truly withhold them) — but on any dataset with self-reported adverse fields this is directly exploitable.

### Mitigation (implemented): scoring-time adverse flooring

`binning.adverse_missing_floor(encoder, columns)` sets the `__missing__` bin of each applicant-influenceable
column to that column's most-adverse observed WOE, so an unknown value is treated as no safer than the worst
observed category:

| Column | Missing WOE before | → after (worst bin) |
|---|--:|--:|
| DELINQ | +0.5644 | −1.6729 |
| DEROG | +0.5760 | −1.8673 |
| NINQ | +0.3684 | −1.1132 |
| YOJ | +0.5454 | −0.2377 |
| JOB | +1.0202 | −0.6259 |

**Applied at scoring time** (model fit on the true, unfloored WOE first), so honest/complete applicants are
unchanged (Applicant A full disclosure 0.8514 → 0.8514; clean Applicant C 0.0061 → 0.0061) while omission can
no longer reduce risk. Flooring *before* refitting is explicitly wrong — it relabels historically-missing
training rows as worst-bin, weakens the coefficient, and shifts scores for fully-observed applicants (we
observed Applicant A drop to 0.40 that way); the function's docstring records this.

**F6 (limitation + control):** SHARP's WOE treatment preserves informative missingness (Finding F1) but, left
ungoverned, can reward strategic omission on columns where missing historically correlated with lower default.
SHARP's Stage 0 *detects* every such column (the missingness-lift audit); governance must then decide, per
column, whether missing is structural (keep the learned WOE) or applicant-influenceable (apply adverse
flooring). Detection without this governance step is insufficient.

---

## Appendix C — how the score is computed (full arithmetic walkthrough)

A single fresh applicant, scored by the selected WOE-logistic model (isotonic-calibrated), with every step
shown so the output is hand-reconstructable. WOE-logistic is additive in log-odds, so the score is a plain
weighted sum.

**Applicant D:** $20,000 on a $90,000 home ($65,000 mortgage due); DTI 35, 0 derogatory, 1 delinquent line,
1 inquiry, 7 years on job (Mgr), CLAGE 180 mo, 20 credit lines.

### Step 1-2 — raw value → WOE bin → contribution (coef × WOE)

| Feature | Raw | WOE | × Coef | = Contribution |
|---|---|--:|--:|--:|
| DEBTINC | 35 | +1.2422 | −0.9251 | −1.1492 |
| DELINQ | 1 | −0.7237 | −0.9121 | +0.6600 |
| DEROG | 0 | +0.2208 | −0.7118 | −0.1572 |
| VALUE | 90000 | +0.2688 | −0.9062 | −0.2436 |
| CLAGE | 180 | +0.3440 | −0.9361 | −0.3221 |
| JOB | Mgr | −0.2001 | −0.9345 | +0.1870 |
| MORTDUE | 65000 | −0.0305 | +0.3061 | −0.0093 |
| NINQ | 1 | +0.0626 | −0.4496 | −0.0281 |
| LOAN | 20000 | +0.2323 | −0.3158 | −0.0733 |
| YOJ | 7 | +0.0397 | −0.9085 | −0.0361 |
| CLNO | 20 | +0.0891 | −1.0411 | −0.0927 |
| | | | **SUM** | **−1.2645** |

WOE > 0 = safer-than-average bin; negative contribution lowers risk. Low disclosed DTI (−1.15) dominates;
the one delinquency (+0.66) is the main offsetting factor.

### Step 3 — log-odds = intercept + Σ contributions
`logit = −1.3780 + (−1.2645) = −2.6425`  (intercept −1.378 = the log-odds of an average file)

### Step 4 — raw probability via the logistic (sigmoid) function
`raw PD = 1 / (1 + e^(−logit)) = 1 / (1 + e^(2.6425)) = 1 / (1 + 14.0487) = 1 / 15.0487 = 0.0665`

### Step 5 — isotonic calibration → final PD
`calibrated PD = isotonic(0.0665) = 0.0884` (corrected slightly upward; the raw model mildly under-predicted
in this score range). **8.84% is the quoted PD.**

### Interpretation
Calibrated **PD 8.84%** vs portfolio average **19.95%** → **~0.44×** average risk, a good file. Reason codes:
low disclosed debt-to-income, long credit history, solid collateral, clean derogatory record; the single
delinquent line is the only material adverse factor and does not flip the decision. The 11 contributions
(−1.2645) + intercept (−1.378) = −2.6425 logit → 6.65% raw → 8.84% calibrated reconstructs exactly, which is
what makes a WOE-logistic scorecard fully auditable by hand.
