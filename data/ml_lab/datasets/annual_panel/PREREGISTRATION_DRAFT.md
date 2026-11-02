# Pre-registration decisions - annual firm-year default dataset (DRAFT, 2026-11-02)

Status key: **DECIDED** = chosen by the user in this project; **FIXED** = a pre-registered setting of the pipeline, not tuned for this dataset; **PROPOSED** = drafted by Claude, not yet decided by the user; **OPEN** = unknown, needs the data owner.
Nothing here is final until the user marks the PROPOSED items. The governed run (G0, G1 sealed) must not be read as confirmatory beyond what is DECIDED or FIXED.

## 1. Data
| Item | Value | Status |
|---|---|---|
| Source file | `archive/annual_panel_raw.csv` (94,708 rows, 9,875 firms, FY ends 2012-2026) | DECIDED (supplied by the user) |
| Origin of the data, definition of "default", meaning of Slice / Limits / Onset known, currency and units | not known | OPEN |
| Analysis file | `annual_panel_clean.csv` (88,229 rows, 9,840 firms, 703 positive rows, 842 defaulting firms) | DECIDED |

## 2. Target (outcome)
| Item | Value | Status |
|---|---|---|
| Unit of observation | one firm-year (statement) | DECIDED |
| Event | `target` = 1 if the firm's default date is 0-365 days after the statement date (FY end); 0 otherwise | DECIDED |
| Rows after the default date | dropped (4,399) | DECIDED |
| Rows whose 12-month window is not fully observed (FY end after 2025-10-31) | dropped (1,553) | DECIDED |
| Filing-lag buffer / window start at filing date | not applied - no filing date in the file | OPEN. Consequence: 22% of positives default within 90 days of FY end, 45% within 180 days, so the statement may not have been public. |

## 3. Cleaning (applied once, before any selection; written to `annual_panel_clean.csv`)
- Drop periods that are not 12 months (526 rows); drop the row with total assets <= 0 (1 row). DECIDED
- Blank the codes -9 / -8 / -7 (380 cells), add `n_sentinel_blanked`. Codes 96-99 left as they are. DECIDED
- Blank impossible cells: negative total income (14), net fixed assets above gross (38 rows, both cells), current assets above total assets (3 rows, both cells). DECIDED
- Not done: winsorising of extremes, duplicate-looking rows (274), year gaps (1,093), derived columns that do not tie out. Left open; tail treatment, if any, must be fitted on training folds only. OPEN

## 4. Feature pool (fixed before results)
| Item | Value | Status |
|---|---|---|
| Primary specification | the full pool: 68 financial columns + `n_sentinel_blanked` = 69 candidates, with the pipeline's fixed rules choosing among them | PROPOSED (this is how the governed run is already set) |
| Never features | Company Code, Company Name, FY end, Months, Slice, Limits, Category, Onset known, Year basis, the firm-level default flag, Default date | DECIDED |
| Robustness specification | ratios only + a size control (log total assets), same rules | PROPOSED - not yet defined or run |
| Which specification is primary | must be stated before the governed run completes | PROPOSED |

## 5. Method (FIXED - not tuned for this dataset)
- Learner: WOE-logistic. Value function: AUC. Seed 42.
- Screening: IV >= 0.02 with a sensible WOE pattern.
- Attribution: sampled Shapley, **200 permutations**, 10 shadow players, shadow bar = 95th percentile, confirmation frequency >= 0.80, correlation cluster threshold 0.7.
- Parsimony: smallest k with DeLong p >= 0.05 and relative Gini loss <= 5%.
- Validation: 5-fold cross-validation grouped by Company Code. Out-of-time: chronological cut at the 70th percentile of the year-and-quarter index, train past / test future.
- Calibration: isotonic, always on. PD floor 0.05% (Basel CRE32.4), cap below 100%.
- Confidence intervals: cluster (company) bootstrap.

## 6. What will be reported, whatever the result
Gini and AUC in-time and out-of-time; calibration in-time and out-of-time (per-grade backtest, Hosmer-Lemeshow, ECE); results by size band (Micro, Small, Medium) with event counts; ratio-only and full specifications side by side; the borrowing-column sensitivity; results for positives by time from FY end to default; sufficiency on rows and on firms; all open items in section 7. Unfavourable results are reported as they are. PROPOSED

## 7. Known limitations to state
Unknown definition of default and unknown source; no filing dates; defaulters and non-defaulters cover different calendar years (median statement year 2016 vs 2020); positives fall from 165 in FY2015 to 11 in FY2025; out-of-time calibration failed in the exploratory run; a very high in-time AUC that is not explained; a column named "Total borrowings including default" whose definition is unknown; jurisdiction `IN` is provisional; one person holds all governance roles; model carries a not-for-capital-use condition.

## 8. Disclosure of exploratory work (done before the governed run completed)
One exploratory run with 20 Shapley permutations (separate folder `runs_exploratory`, nothing sealed), and checks of ratio-only vs amount-only, without borrowing columns, by size band, and by time from FY end to default. Exploratory results: selected k=21 (44 columns), in-time Gini 0.807, out-of-time Gini 0.685, out-of-time per-grade 1/8, event rate 0.94% in training vs 0.29% in the test period. These did not change any FIXED setting. They informed the proposals in sections 4 and 6, so the robustness specification is **not** independent of having seen them.

## 9. Code changes during the work (no effect on results)
Per-permutation progress and checkpoint/resume for the Shapley stage; progress output for the parsimony stage; a fix so column names containing commas are not split. Uncommitted.

## 10. Decisions still needed from the user
1. Confirm the full pool as the primary specification.
2. Confirm or change the robustness specification (ratios + log total assets).
3. Whether to wait for filing dates and the default definition before treating the run as confirmatory.
4. Whether to apply any tail treatment (winsorising) to the extremes, and how.
