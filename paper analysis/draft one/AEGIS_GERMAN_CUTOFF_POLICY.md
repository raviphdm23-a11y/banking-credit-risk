# AEGIS — German Credit product cutoff & grade policy (illustrative)

**Status:** draft policy artifact · **Date:** 2026-10-13 · **Model:** approved German WOE-logistic 5-column model
(AEGIS run `AEGIS_RUN_GERMAN.md`, GF `00d5d25e`) · **Owner (to ratify):** Risk Committee / Model Owner.
**Governs:** the accept/decline/price decision downstream of the model's calibrated PD.

> Same structure as `AEGIS_HMEQ_CUTOFF_POLICY.md`: fixed **absolute** PD cutoffs (retrain-stable), mapped to
> rating grades, with risk-based pricing. German is **unsecured consumer credit** with a **30% portfolio
> default rate**, so the economics differ from HMEQ (secured home equity, 20%): higher LGD, higher rates.

## 1. Principle (unchanged)
PD is a *fact about the borrower*; the cutoff is a *fixed, documented policy number* independent of the base
rate. The 0.5 "more-likely-than-not" rule does not apply — lending is an economic decision. Cutoffs do not move
on retrain; only the features→PD mapping does (re-validated via the GC4 per-grade backtest).

## 2. Economic derivation *(parameters ILLUSTRATIVE — Risk Committee to set)*
Required gross yield ≈ **cost + opex (5%) + expected loss (PD × LGD) + target margin (3%)**, with **LGD 75%**
(unsecured consumer), a **standard offered rate of 15%**, and a **maximum rate cap of 30%**.

| Cutoff | Formula | Fixed PD value |
|---|---|--:|
| Approve at **standard** pricing | (15% − 5% − 3%) / 75% | **PD ≤ 9.3%** |
| Manual-review floor | risk-appetite | **PD > 20%** |
| Decline (unpriceable within cap) | (30% − 5% − 3%) / 75% | **PD > 29.3%** |

## 3. Decision bands (fixed — retrain-stable)

| Calibrated PD | Generic grade | Policy decision | Indicative gross rate = 8% + PD×75% (cap 30%) |
|---|---|---|---|
| ≤ 9.3% | B or better | **APPROVE** (standard pricing) | ≤ 15% |
| 9.3% – 20% | B / CCC | **APPROVE** (risk-based pricing) | 15% – 23% |
| 20% – 29.3% | CC | **REFER** (manual underwrite) | 23% – 30% |
| > 29.3% | C / D | **DECLINE** | capped 30% |

## 4. Acceptance demonstration (same approved model + this policy)

| Customer | Calibrated PD | Grade | **Decision** | Indicative rate | Principal reasons |
|---|--:|---|---|--:|---|
| **A-strong** | 0.03% | AAA | **APPROVE (standard)** | 8.0% | *(all factors protective)* |
| **B-good** | 19.90% | CCC | **APPROVE (risk-based)** | 22.9% | low savings, long term, credit history |
| **C-weaker** | 35.45% | C | **DECLINE** | 30.0% (uneconomic) | long term, checking balance, low savings |
| **D-weak** | 85.71% | D | **DECLINE** | 30.0% | long term (48mo), overdrawn checking, loan purpose |

A-strong's PD is the **0.03% floor** (Basel CRE32.3), not a literal 0% — the floor in action. Every reason
code is a **legitimate credit factor** (no protected attributes), so adverse-action notices never cite
age/sex/nationality.

## 5. Retrain behaviour & caveats
- Cutoffs (9.3 / 20 / 29.3%) and grade bands are **fixed**; on retrain, re-validate calibration (GC4). If
  calibration holds, the policy is unchanged; if it drifts, recalibrate the model, not the policy.
- **All economic parameters are illustrative placeholders** (LGD 75%, 5%/3%/15%/30%) to demonstrate the
  method; the Risk Committee sets the real appetite. The *structure* is the deliverable.
- The **refer band (20–29.3%) is sparsely populated** for this model: the small-data isotonic calibration has
  few steps in the 20–30% range, so profiles tend to land either side of it. A documented small-sample MoC
  (R6) and a larger recalibration dataset would smooth this. Noted as a monitorable at deployment.
