# AEGIS governed run — POLISH_1YR (Polish bankruptcy, 1-year-ahead horizon)

**Dataset:** Polish companies bankruptcy data (Zięba, Tomczak & Tomczak 2016; UCI #365), file `polish_bankruptcy_1yr_ahead.csv` (UCI's "5year" file): ratios observed 1 year before the status check. 5,910 firms · 410 bankrupt (6.94%) · 64 ratios (descriptive names).
**Materiality tier:** MEDIUM (research benchmark). **Fairness NOT live** — firm financial ratios, no protected attributes. Seed 42.
**Process:** staged protocol — each SHARP stage ran, stopped at its gate, and the next stage ran only after the signer chose an option (`ml_models/staged_run.py`; AEGIS_GOVERNANCE.md §11). Gate option sets are emitted by `ml_models/aegis_gates.py`.
**Rationale caveat (disclosed):** at every gate the human gave the option only; the rationale text was the one I suggested or drafted from the evidence, shown in chat before sealing. The GF checklist statuses were assessed by me from recorded evidence (not code-emitted) and presented for overrule.

## Decision summary

| # | Gate | Decision | Signer | Basis | prev | entry_hash |
|---|---|---|---|---|---|---|
| 0 | G0 | **A** | Data Steward | scope adopted; working_capital sentinel is one row and a plausible amount; Attr24 look-ahead and period confound disclosed | `GEN-POLISH_1YR_0` | `0c3d2aea` |
| 1 | G1 | **A** | Model Validator | advance 63/64; Riley minimum met 2.1x (2839 vs 5910); EPV 6.4 below 10 disclosed, to be carried to GF | `0c3d2aea` | `307ce809` |
| 2 | G2 | **A** | Model Validator | 19/19 clear shadow bar, weakest 1.7x; P1 and Attr24 look-ahead carried as watch item to G3 | `307ce809` | `7b8190c9` |
| 3 | G3 | **A** | Model Validator | k=4 of 19, Gini 0.826, DeLong p 0.255, loss 1.41%; 25 columns, EPV 16.4, Riley met 5.2x; Attr24 watch item carried | `7b8190c9` | `6fcb33a6` |
| 4 | G4 | **B** | Model Validator | AUC 0.913 clears 0.70; grade B 9/54 vs expected 8.3% disclosed as condition; HL g=5 p=0.019 noted; fairness N/A | `6fcb33a6` | `baa1f4ca` |
| 5 | G5 | **A** | Model Validator | mandatory sales-growth gate refers 103 blank firms (99 bankrupt); cap untested, R5 miss and missingness signal disclosed to GF | `baa1f4ca` | `e9a2f3ff` |
| 6 | GF | **GO-WITH-CONDITIONS** | MAC Chair + CRO | GO-WITH-CONDITIONS: no must-have GAP; R1,R4,R6,R7,R8,R10 partials and standing scope (never-deploy, missingness, Attr24) accepted | `e9a2f3ff` | `209136ae` |

**Chain:** `GEN-POLISH_1YR_0 → 0c3d2aea → 307ce809 → 7b8190c9 → 6fcb33a6 → baa1f4ca → e9a2f3ff → 209136ae`

---

## G0 — Data & scope · A · `0c3d2aea`
Scope adopted. Sentinel flag on `working_capital` = 97 rests on one bankrupt row (lift 14.4); an absolute amount, judged plausible. Disclosed: Attr24 (`gross_profit_in_3_years_to_total_assets`) look-ahead unresolved; bankrupt (2000-2012) vs operating (2007-2013) sampling windows.

## G1 — Screening & sufficiency · A · `307ce809`
63 of 64 pass IV >= 0.02 with monotonic WOE; `total_sales_to_total_assets` dropped (MW p 0.138). Dominant `sales_n_to_sales_n_minus_1` IV 2.19. EPV 6.4 (< 10) disclosed; Riley minimum met 2.08x (2,839 required vs 5,910).

## G2 — Importance attribution · A · `7b8190c9`
19 real players, all confirmed; shadow bar 0.00161; weakest 1.74x the bar. P1 is a 21-column profitability group containing Attr24 — carried as a watch item. EPV/Riley recalculated at the signer's request on the G2 basis: EPV 6.5 on columns, 21.6 on the 19-player basis; Riley N 2,839 (63 columns) vs 856 (19 players).

## G3 — Parsimony selection · A · `6fcb33a6`
k = 4 of 19 (25 columns): Gini 0.8260 (CI 0.7966-0.8568) vs full 0.8379, DeLong p 0.2554, relative loss 1.41%. EPV 16.4, Riley N 1,132 (5.22x). `working_capital` earns k=4. Parsimonious in decisions, not columns.

## G4 — Calibration (fairness N/A) · B · `baa1f4ca`
Option B (approve with conditions). AUC 0.913 vs floor 0.70. Deployed-model backtest 9/10 grades; grade B fails (9/54 = 16.7% vs 8.3% expected, under-prediction). HL g=10 p 0.0720, g=5 p 0.0185. Calibration did not improve Brier/ECE. Fairness N/A, no OOT (no time column). Conditions carried to GF.

## G5 — Deployment governance · A · `e9a2f3ff`
Controls confirmed: mandatory `sales_n_to_sales_n_minus_1` (blank -> REFER; 103 firms, 99 bankrupt), exact WOE reason codes, PD floor 0.03% / cap 99.9%. Deliverables: `AEGIS_POLISH_1YR_CUTOFF_POLICY.md`, `SAMPLE_RUNS_POLISH_1YR.md` (5 real + 3 synthetic), `acceptance_cases/polish_1yr.json`. Floor demonstrated; cap NOT (max 51.43% on complete-data firms); real bankrupt R5 rated AAA at 0.32%. `adverse_fallback` was set ok because an incomplete policy (refer) is defined; no adverse-score fallback is configured.

## GF — Final Go/No-Go · **GO-WITH-CONDITIONS** · `209136ae`
`gf_engine` over the sealed gate states and the checklist below (`sharp_runs_staged/POLISH_1YR/gf_proposal.json`). All gates signed; no must-have GAP; residual risk within appetite (input assumed yes, Risk Officer input).

| # | Criterion | Status | Evidence |
|---|---|---|---|
| R1 | PD data history >= 5y | **PARTIAL** | data history: source states bankrupt firms sampled 2000-2012, operating 2007-2013, but the file has no dates and no per-firm history, so >=5 years is not verifiable here |
| R2 | Use test | **SATISFIED** | use test: governed decision + 8-case acceptance pack (research benchmark, not a live decision flow) |
| R3 | Risk differentiation | **SATISFIED** | Gini 0.826 (CI 0.797-0.857), AUC 0.913 vs floor 0.70; 10 grades populated, largest grade AA 25.8% of held-out firms |
| R4 | Calibration backtest | **PARTIAL** | grade B fails Wilson CI (9/54 = 16.7% vs 8.3% expected, under-prediction); 9/10 pass; HL g=10 p=0.072 but g=5 p=0.0185 |
| R5 | Override governance | **SATISFIED** | blank mandatory sales-growth field -> REFER (103 firms); PD floor/cap; override policy per cutoff note |
| R6 | Margin of Conservatism | **PARTIAL** | EPV 6.4 on 64-column pool (selected model 16.4; Riley met 5.2x); MoC required but not quantified in this run |
| R7 | Independent validation | **PARTIAL** | all gates G0-G5 signed by one person in the designated roles; no separate independent validator on record |
| R8 | Governance & accountability | **PARTIAL** | RACI roles exist in the engine but MAC/CRO/validator are not independent people in this run |
| R9 | Risk-proportionate rigour | **SATISFIED** | MEDIUM tier (research benchmark) |
| R10 | Data governance / completeness | **PARTIAL** | completeness: 48.7% of firms (2,879 of 5,910) have >=1 blank among 64 ratios; 844 in the 25 selected; blank sales-growth is 96% bankrupt, cause unknown |

R11 and R13 not assessed (commentary-level, no evidence either way); R12 and R14 not applicable (borrowers are firms, not natural persons).

**Conditions (engine):** R1; R4; R6; R7; R8; R10.
**Standing scope conditions:** NEVER-DEPLOY (research benchmark); PARSIMONY-WIDTH (4 players = 25 columns); MISSING-SALES-GROWTH (103 blanks, 96% bankrupt, cause unknown, in-sample AUC 0.9195 vs 0.8949 on complete rows); ATTR24 look-ahead unresolved; PERIOD CONFOUND; PD cap untested; R5 false negative; fairness N/A.

**Differences from the POLISH1 GF:** POLISH1 carried only R6 and R10 as partials. R1, R7 and R8 are rated PARTIAL here because they cannot be verified from the evidence; R7/R8 (single person signing every role) equally apply to earlier runs, which were not re-rated.

**Not established by this run:** hypothesis H1 (1yr_ahead discriminates better than 5yr_ahead). The files hold different firms and sampling windows; no CI comparison has been made.
