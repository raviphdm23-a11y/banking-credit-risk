# AEGIS — HELOC product cutoff & grade policy (illustrative)

**Status:** draft policy artifact · **Date:** 2026-10-13 · **Model:** approved HELOC WOE-logistic 17-column
model (AEGIS run `AEGIS_RUN_HELOC.md`) · **Owner (to ratify):** Risk Committee.

> Secured home-equity line of credit — same economics as HMEQ (LGD 50%). **Benchmark caveat:** the FICO HELOC
> dataset is near-balanced (52% "Bad"), so predicted PDs cluster high and most applicants map to low grades;
> a real HELOC book would have a far lower base rate. Cutoffs below are fixed absolute PD values and
> retrain-stable regardless.

## 1. Economic derivation *(ILLUSTRATIVE — Risk Committee to set)*
LGD 50%, cost+opex 4%, target margin 2%, standard rate 12%, max rate 20%.

| Cutoff | Formula | Fixed PD |
|---|---|--:|
| Approve standard | (12% − 4% − 2%) / 50% | **PD ≤ 12%** |
| Review floor | risk-appetite | **PD > 20%** |
| Decline | (20% − 4% − 2%) / 50% | **PD > 28%** |

## 2. Decision bands (fixed — retrain-stable)

| Calibrated PD | Grade | Decision | Indicative rate = 6% + PD×50% (cap 20%) |
|---|---|---|---|
| ≤ 12% | A–B | **APPROVE** (standard) | ≤ 12% |
| 12% – 20% | CCC | **APPROVE** (risk-based) | 12% – 16% |
| 20% – 28% | CC | **REFER** (manual) | 16% – 20% |
| > 28% | C / D | **DECLINE** | capped 20% |

## 3. Acceptance demonstration (approved 17-col model + this policy)

Representative actual applicants; PD floored at 0.03%. All reason codes are legitimate credit-bureau factors.

| Customer | Calibrated PD | Grade | Decision | Indic. rate | Principal reasons |
|---|--:|---|---|--:|---|
| **HE-strong** | 1.9% | A | **APPROVE (standard)** | 7.0% | worst recent delinquency grade (minor) |
| **HE-good** | 17.6% | CCC | **APPROVE (risk-based)** | 14.8% | high revolving utilization, worst-ever delinquency, external score |
| **HE-refer** | 22.5% | CC | **REFER (manual)** | 17.2% | many revolving accounts with balances, worst-ever delinquency, high utilization |
| **HE-weak** | 90.1% | D | **DECLINE** | 20.0% | recent delinquency, thin credit file, installment mix |

Spans approve / refer / decline with hand-auditable reasons. **Acceptance: PASS.**

## 4. Caveats
- Economic parameters illustrative; Risk Committee ratifies.
- Calibration passed only marginally (HL p=0.051, condition HC-cal) — set a Margin of Conservatism, especially
  for grade B (observed under-prediction), and monitor closely.
- `ExternalRiskEstimate` dependence: for a pure internal-score policy, use the without-it variant (HC2).
