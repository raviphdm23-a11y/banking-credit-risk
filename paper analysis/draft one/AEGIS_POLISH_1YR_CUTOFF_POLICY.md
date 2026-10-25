# AEGIS decisioning note — POLISH_1YR (Polish bankruptcy, 1-year-ahead horizon), 4-player / 25-column model

**Run:** POLISH_1YR (Zięba et al. 2016, UCI #365; file `polish_bankruptcy_1yr_ahead.csv`, i.e. UCI's "5year" file:
ratios observed 1 year before the bankruptcy-status check) · **Gate:** G5 (deployment governance) · chain through G4 `baa1f4ca`
**Model:** WOE-logistic on 4 confirmed players spanning 25 columns (P1 profitability group of 21 columns + P2 + P3 + P4 `working_capital`).
**Discrimination:** Gini 0.8260 / AUC 0.913 (out-of-fold). **Calibration:** isotonic; deployed-model backtest 9/10 grades pass (grade B fails), HL g=10 p=0.072, g=5 p=0.0185.

## 1. What this note DOES and DOES NOT set
It governs how a firm's PD is produced and explained: calibrated PD, PD floor/cap (Basel CRE32.3), rating grade, exact additive-WOE reason codes.
It does **not** invent an accept/decline cutoff or a price: the credit decision is the institution applying its own risk-appetite PD threshold (exogenous).

## 2. Scoring configuration (to be signed at G5)
| Control | Value |
|---|---|
| Model | 4 players / 25 columns (decision-parsimonious, not column-parsimonious) |
| Mandatory field (blank -> refer) | `sales_n_to_sales_n_minus_1` (proposed; see §3 first bullet) |
| Incomplete policy | `refer` |
| Reason codes | exact additive WOE |
| PD floor / cap | 0.03% / 99.9% (always on) |
| Decisions emitted | SCORE / REFER + calibrated PD + reason string |

## 3. Binding conditions (carried G0-G4 -> GF)
- **MISSING-SALES-GROWTH SIGNAL.** `sales_n_to_sales_n_minus_1` is blank for 103 firms, 99 of them bankrupt (96.1%). Scored as-is, the learned missing bin gives 101 of those 103 a grade-D PD (median 99.9%). This is a missingness pattern, not a financial ratio, and its cause is not known. With the refer gate those firms are not scored. In-sample AUC is 0.9195 on all rows and 0.8949 on complete rows only (descriptive, not out-of-fold).
- **EPV-SHORT.** 410 events against a 64-ratio candidate pool, EPV 6.4 (< 10); the selected model has EPV 16.4. Riley minimum met 5.22x on the selected model (1,132 required vs 5,910).
- **PARSIMONY-WIDTH.** 4 players but 25 columns; do not describe as a small-feature model.
- **GRADE-B UNDER-PREDICTION (G4 condition).** Grade B: 9 defaults of 54 (16.7%) vs expected 8.3%; fails Wilson 95% interval (9.0%-28.7%).
- **HL SENSITIVITY (G4).** HL g=10 p=0.072 passes; g=5 p=0.0185 rejects.
- **ATTR24 LOOK-AHEAD (open).** `gross_profit_in_3_years_to_total_assets` may use post-statement information; unresolved.
- **PERIOD CONFOUND.** Bankrupt firms were sampled 2000-2012, operating firms 2007-2013.
- **FAIRNESS N/A.** Firm financial ratios; no protected attributes.
- **NEVER-DEPLOY.** Research benchmark only.

## 4. Acceptance demonstration
See `SAMPLE_RUNS_POLISH_1YR.md`: 5 real firms + 3 synthetic composites. The PD floor binds (PLY1-R1, 0.03%). **The PD cap (99.9%) did not bind** on any case: the highest PD among complete-data firms is 51.43% (the isotonic map's top step), so the cap is untested here. R5 is a real bankrupt firm rated AAA (PD 0.32%), a false negative. R4 (bankrupt, blank sales growth) is REFERRED, not scored.
