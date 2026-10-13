# AEGIS — Taiwan product cutoff & grade policy (illustrative)

**Status:** draft policy artifact · **Date:** 2026-10-13 · **Model:** approved Taiwan WOE-logistic **13-column
behavioural** model (AEGIS run `AEGIS_RUN_TAIWAN.md`, GF `2c84dccb`) · **Owner (to ratify):** Risk Committee.

> Same structure as the HMEQ/German policies: fixed **absolute** PD cutoffs (retrain-stable), mapped to rating
> grades, with risk-based pricing. **Behavioural-model caveat:** this model uses near-target `PAY_0`, so it is
> an **account-management / early-warning** model, not an origination scorer. The bands therefore map to
> **account actions** (maintain / review / reduce line), not new-application approve/decline.

## 1. Principle (unchanged)
PD is a fact about the account; the cutoff is a fixed, documented policy number independent of the base rate.
Cutoffs do not move on retrain; only the features→PD mapping does (re-validated via the TC-cal backtest).

## 2. Economic derivation *(parameters ILLUSTRATIVE — Risk Committee to set)*
Unsecured revolving card: **LGD 80%**, cost+opex 6%, target margin 3%, standard rate 18%, max rate 36%.

| Cutoff | Formula | Fixed PD value |
|---|---|--:|
| Maintain at **standard** pricing | (18% − 6% − 3%) / 80% | **PD ≤ 11.3%** |
| Review floor | risk-appetite | **PD > 25%** |
| Reduce line (unpriceable within cap) | (36% − 6% − 3%) / 80% | **PD > 33.8%** |

## 3. Decision bands (fixed — retrain-stable)

| Calibrated PD | Grade | Account action | Indicative gross rate = 9% + PD×80% (cap 36%) |
|---|---|---|---|
| ≤ 11.3% | B or better | **APPROVE / maintain** (standard) | ≤ 18% |
| 11.3% – 25% | B / CCC / CC | **APPROVE / maintain** (risk-based) | 18% – 29% |
| 25% – 33.8% | CC | **REFER / review** (manual) | 29% – 36% |
| > 33.8% | C / D | **DECLINE / reduce line** | capped 36% |

## 4. Acceptance demonstration (approved 13-col model + this policy)

Portfolio default rate 22.1%. PD floored at 0.03% (Basel CRE32.3). Every reason code is a legitimate
behavioural factor (no protected attributes; proxy EDUCATION removed at G4).

| Customer | Calibrated PD | Grade | Account action | Indic. rate | Principal reasons |
|---|--:|---|---|--:|---|
| **T-strong** | 5.44% | BB | **MAINTAIN (standard)** | 13.4% | all factors protective (all accounts paid duly, high limit) |
| **T-mid** | 8.91% | B | **MAINTAIN (standard)** | 16.1% | moderate credit limit |
| **T-watch** | 28.02% | CC | **REVIEW (manual)** | 31.4% | recent repayment delay (PAY_0), lower limit, earlier delay (PAY_2) |
| **T-weak** | 71.50% | D | **REDUCE LINE** | 36.0% | recent repayment delay (PAY_0), low limit, prior delays |

Spans maintain / review / reduce across the behavioural risk spectrum, each with hand-auditable reasons.
**Acceptance: PASS.**

## 5. Retrain behaviour & caveats
- Cutoffs (11.3 / 25 / 33.8%) are fixed; on retrain, re-validate calibration (TC-cal). Policy unchanged if
  calibration holds.
- **All economic parameters illustrative** (LGD 80%, 6%/3%/18%/36%) — Risk Committee sets the real appetite.
- **Behavioural, not origination:** for new-application decisions, use the without-PAY_0 variant (TC3), which
  will have lower discrimination and needs its own policy.
