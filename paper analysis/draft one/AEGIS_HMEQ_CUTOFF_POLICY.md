# AEGIS — HMEQ product cutoff & grade policy (illustrative)

**Status:** draft policy artifact · **Date:** 2026-10-12 · **Model:** approved HMEQ WOE-logistic (AEGIS run `AEGIS_RUN_HMEQ.md`, GF `3b896863`)
**Owner (to ratify):** Risk Committee / Model Owner · **Governs:** the accept/decline/price decision that sits *downstream* of the model's calibrated PD.

> **Why a product-specific policy exists.** The generic internal master scale
> (`backend/rating_masterscale.py`) treats only investment grade (PD < 4%) as APPROVE. HMEQ is a
> subprime home-equity book with a **19.95% portfolio default rate**, so the generic cutoff would
> **decline the entire portfolio**. The decision rule must therefore be set *per product*, anchored to
> **fixed absolute PD values**, not to the portfolio average (which shifts on every retrain).

---

## 1. Principle — separate the fact from the decision

- **PD** is a *fact about the borrower* the model outputs (calibrated to real default frequency).
- **The cutoff** is a *fixed, documented policy number*. It does **not** move when the model is retrained;
  only the features→PD mapping changes. This is what makes the rule auditable and reproducible: a
  reviewer reads this policy, never reverse-engineers a threshold from the dataset size or base rate.
- The **0.5 "more-likely-than-not" rule does not apply** — lending is an economic decision (does the
  loan cover its expected loss + costs + margin?), not a most-likely-class guess.

## 2. Economic derivation of the cutoffs *(parameters ILLUSTRATIVE — Risk Committee to set)*

Required gross yield to be viable ≈ **cost + opex (4%) + expected loss (PD × LGD) + target margin (2%)**,
with LGD assumed **50%** (home-equity blended — to be confirmed per lien position), a **standard offered
rate of 12%**, and a **maximum offered rate cap of 20%** (competitiveness/usury).

| Cutoff | Formula | Fixed PD value |
|---|---|--:|
| Approve at **standard** pricing | std rate covers cost+margin: PD ≤ (12%−4%−2%)/50% | **PD ≤ 12%** |
| Manual-review floor | risk-appetite (aligns to CC grade start) | **PD > 20%** |
| Decline (unpriceable within cap) | max rate can't cover cost+margin: PD > (20%−4%−2%)/50% | **PD > 28%** |

## 3. The decision bands (fixed — retrain-stable)

| Calibrated PD | Generic grade | HMEQ policy decision | Indicative gross rate = 6% + PD×50% (cap 20%) |
|---|---|---|---|
| ≤ 12% | B or better | **APPROVE** (standard pricing) | ≤ 12% |
| 12% – 20% | CCC | **APPROVE** (risk-based pricing, auto) | 12% – 16% |
| 20% – 28% | CC (lower) | **REFER** (manual underwrite; compensating factors / extra collateral) | 16% – 20% |
| > 28% | CC (upper) / C / D | **DECLINE** (cannot be priced within the cap) | capped 20% |

## 4. Re-scored worked examples (same approved model)

| Customer | Calibrated PD | Grade | Label | **Policy decision** | Indicative rate |
|---|--:|---|---|---|--:|
| **N** | 16.94% | CCC | Distressed | **APPROVE (risk-based pricing)** | 14.47% |
| **Q** | 22.95% | CC | Highly Distressed | **REFER (manual underwrite)** | 17.48% |
| **P** | 96.77% | D | Default | **DECLINE** | 20.00% (uneconomic) |

Now the outcomes differentiate honestly: N is approvable *if repriced* for its elevated risk, Q needs a
human underwriter, P is declined. None of this depends on knowing the dataset size or base rate.

## 5. Behaviour under retraining (the reproducibility guarantee)

1. The **cutoffs (12% / 20% / 28%) and grade bands do NOT change** on retrain.
2. The retrained model's PDs are **re-validated for calibration** (the per-grade realised-vs-expected
   backtest — AEGIS condition **CP4**). If "17% PD" still means "~17% default", the policy is unchanged.
3. If calibration has **drifted** (caught by `drift_monitor`), the model is **recalibrated** — the
   mapping moves, the **policy numbers stay fixed**. A reviewer always reads the same documented rule.

## 6. Governance status & honesty caveats

- This is a **governed policy artifact**: to take effect it is a **signed Risk-Committee / Model-Owner
  decision** (an AEGIS gate-style sign-off), versioned — not an emergent property of the data.
- **All economic parameters (LGD 50%, cost 4%, margin 2%, rates 12%/20%) are illustrative placeholders**
  to demonstrate the method; the Risk Committee sets the real appetite. The *structure* (fixed absolute
  cutoffs + risk-based pricing + retrain-stability) is the point, not these specific numbers.
- LGD for home equity depends on **lien position** (1st vs 2nd) and property dynamics — a single 50%
  figure is a simplification; a real policy would segment it.
- Pricing here is single-period and ignores the **cost of regulatory capital** — a fuller model adds a
  capital charge, which would raise the required yield and lower the decline cutoff.
