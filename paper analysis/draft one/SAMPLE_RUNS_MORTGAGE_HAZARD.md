# SAMPLE RUNS - US mortgage (discrete-time HAZARD, per-period)

**Committee-facing acceptance pack** - generated directly from the full-frame governed scorer (the 622,489-row per-period frame is regenerable via `panel_adapter` from `mortgage.csv` + `mortgage_hazard.manifest.json`; it is too large to commit as a CSV).

**Model:** AEGIS-approved WOE-logistic, **11 features** (3 time-varying + 3 macro + 5 origination) - predicts default **in a given period**. **Portfolio per-period default rate:** 2.44% - PD floored at 0.03% (Basel CRE32.3).

> **Scope.** Each case is a loan-PERIOD (the hazard unit), not a loan. Reports only methodology/regulation-grounded outputs: calibrated per-period PD, rating grade, exact WOE reason codes, governed decision. The accept/decline cutoff is the institution's own risk-appetite threshold - exogenous, not derived here.

| Candidate | Type | Outcome | Per-period PD | vs portfolio | Grade | Decision | Principal reasons |
|---|---|---|--:|--:|---|---|---|
| **MH-R1_low_nondefault** | real | survived (this period) | 0.03% | 0.01x | AAA | SCORE | Interest_Rate_orig_time |
| **MH-R2_elevated_nondefault** | real | survived (this period) | 7.30% | 3.00x | B | SCORE | LTV_time, interest_rate_time, gdp_time |
| **MH-R3_default_period** | real | defaulted (this period) | 2.84% | 1.17x | BBB | SCORE | interest_rate_time, gdp_time, LTV_time |
| **MH-R4_high_default_period** | real | defaulted (this period) | 14.63% | 6.01x | CCC | SCORE | interest_rate_time, LTV_time, gdp_time |
| **MH-S1_floor_check** | synthetic | non-default (by design) | 0.03% | 0.01x | AAA | SCORE | all protective |
| **MH-S2_stress_check** | synthetic | default (by design) | 14.63% | 6.01x | CCC | SCORE | interest_rate_time, LTV_time, gdp_time |

Floor binds on the all-protective case (0.03%); stress case reaches CCC. Isotonic ceiling applies as in the snapshot model.