# Dataset Tracker — Five C's Methodology Status Across All Sandbox Datasets

> ## STATUS: all results below are v2 and are SUPERSEDED pending v3 re-runs (2026-10-10)
>
> The methodology was revised to **v3** after external review (`EXPERT_REVIEW_OF_METHODOLOGY.md`,
> `METHODOLOGY.md`, `V3_IMPLEMENTATION_STATUS.md`). The v3 code is implemented and verified, but the six
> datasets below have **not yet been re-run through it**. Three things in this table are known to be wrong or
> unsupported as stated:
>
> 1. **The selection rule changed.** v3 requires a pre-declared tolerance: DeLong-indistinguishable from the
>    full model AND relative Gini loss <= 5%. Converted to Gini, **PAKDD (-15.5%) and German Credit (-7.1%)
>    FAIL that tolerance** - their v2 "final" sets are not acceptable parsimonious models, and the honest
>    statement is that no subset of that size qualifies.
> 2. **Retention was decided by an invalid test.** v2 used a t-test on 5 CV-fold Shapley values plus a
>    Cohen's d cutoff. Both are withdrawn (review M3). v3 decides by a shadow-feature empirical null. Every
>    v2 keep-list is therefore provisional.
> 3. **`scale_pos_weight` was inflating probabilities.** It is now off by default; measured 4.3x inflation on
>    GMSC. The calibration figures below were largely repairing self-inflicted damage.
>
> The AUC/Gini numbers themselves are real recorded runs - they are not retracted as measurements. What is
> withdrawn is the *selection decision* layered on top of them.


Master tracking table for the column-usefulness methodology (`METHODOLOGY.md`) across every dataset
available in the Sandbox (`data/ml_lab/datasets/`). Private reference, not shown on the frontend.

**Methodology version note:** only results produced under the current **Step 5 v2** procedure (per-category
Steps 1-4, then one pooled Shapley/Benjamini-Hochberg-correction run across all survivors — see
`METHODOLOGY.md`) are treated as final. Earlier **v1** results (greedy, category-locked combination testing)
are not trusted as final column-selection decisions, since v1 was found to have an order-dependency problem —
see `GERMAN_CREDIT_FINDINGS.md`'s "Step 5 v2" section for the concrete evidence. PAK and HMEQ were both fully
redone under v2 on 2026-10-08 (see each file's "v2 REDO" section). The Sandbox's recorded-runs list
(`data/ml_lab/index.json`) is kept cleaned to hold only the three current final models — one per completed
dataset, no intermediate/diagnostic runs.

**v1 → v2 correction pattern across all three datasets:**
- **German Credit**: v2 *removed* several v1-confirmed columns (`personal_status_sex`, `other_debtors`,
  `employment_since`) — order-dependency artifacts.
- **PAK**: v2 both *removed* a non-additive column (`OCCUPATION_TYPE`) and *added* a strong one v1 never
  tested at all (`RESIDENCIAL_PHONE_AREA_CODE`) — the biggest net improvement of the three (CV AUC 0.5904 →
  0.6197).
- **HMEQ**: the mildest correction — v2 *added back* one column v1 had rejected on a narrow miss
  (`MORTDUE`, Cramér's V 0.0933 vs. the 0.1 threshold), confirmed genuinely additive by the pooled test.

---

## Status table

| Dataset | Rows | Total cols (+target) | File size | Status | Cols selected | Selected CV AUC | Selected Holdout AUC | **Full-column CV AUC** | **Gap** | Findings log |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| german_credit_record.csv | 1,000 | 20 | 0.211 MB | ✅ **Complete (v2)** | 5 / 20 | 0.7651 ± 0.0227 | 0.7724 | 0.7854 ± 0.0315 | −0.0203 | `GERMAN_CREDIT_FINDINGS.md` |
| PAK.csv | 50,000 | 51 | 6.776 MB | ✅ **Complete (v2)** | 4 / 51 | 0.6197 ± 0.0031 | 0.6238 | 0.6416 ± 0.0018 | −0.0219 | `PAK_FINDINGS.md` |
| hmeq.csv | 5,960 | 12 | 0.375 MB | ✅ **Complete (v2)** | 11 / 12 | 0.9498 ± 0.0053 | 0.9438 | 0.9507 ± 0.0042 | **−0.0009** | `HMEQ_FINDINGS.md` |
| GMSC.csv | 149,391 | 10 | 6.239 MB | ✅ **Complete (v2)** | **10 / 10** | 0.8652 ± 0.0019 | 0.8654 | 0.8652 ± 0.0019 (same model) | **0.0000** | `GMSC_FINDINGS.md` |
| Taiwan_UCI_Credit_Card.csv | 30,000 | 23 | 2.610 MB | ✅ **Complete (v2, pruned)** | 12 / 23 | 0.7754 ± 0.0046 | 0.7718 | 0.7823 ± 0.0049 | −0.0069 | `TAIWAN_FINDINGS.md` |
| heloc.csv | 10,459 | 23 | 0.622 MB | ✅ **Complete (v2, pruned)** | 13 / 23 | 0.7942 ± 0.0069 | 0.7949 | 0.7950 ± 0.0065 | −0.0008 | `HELOC_FINDINGS.md` |

**Full-column baseline run IDs** (kept permanently in the Sandbox as reference points, not deleted in
cleanups): German Credit `lab_20261008_201201_german_credit_full_baseline_xgboost` (all 20 cols); PAK
`lab_20261008_201219_pak_full_baseline_xgboost` (42 non-constant cols, high-cardinality capped to top 51
categories); HMEQ `lab_20261008_201205_hmeq_full_baseline_xgboost` (all 12 cols, including `REASON`).

## Calibration results (2026-10-09)

All four models use XGBoost's `scale_pos_weight` for class imbalance, which inflates raw predicted
probabilities away from true real-world odds (ranking stays correct, absolute magnitude does not — see
`CALIBRATION_NOTES.md`). Isotonic-regression calibration applied to each final model, 5-fold internal CV:

| Dataset | Baseline Brier (base rate) | Raw Brier | Raw ECE | Calibrated Brier | Calibrated ECE | AUC change |
|---|---:|---:|---:|---:|---:|---:|
| German Credit | 0.2100 | 0.1955 | 0.1492 | **0.1664** | **0.0519** | 0.7724→0.7795 |
| PAK | 0.1928 | 0.2368 ⚠️ worse than baseline | 0.2236 | **0.1855** | **0.0064** | 0.6238→0.6259 |
| HMEQ | 0.1598 | 0.0779 | 0.0819 | **0.0681** | **0.0123** | 0.9438→0.9472 |
| GMSC | 0.0625 | 0.1425 ⚠️ worse than baseline | 0.2513 | **0.0487** | **0.0044** | 0.8654→0.8649 |
| Taiwan Credit Card | 0.1723 | 0.1810 ⚠️ worse than baseline | 0.2011 | **0.1359** | **0.0093** | 0.7718→0.7700 |
| HELOC | 0.2495 | 0.1852 | 0.0241 | **0.1834** | **0.0216** | 0.7949→0.7968 |

PAK and GMSC's raw models were *worse than a trivial always-predict-the-base-rate baseline* before
calibration — now fixed. ECE improved 65-98% across all four; AUC changed by at most 0.007 (within normal
fold noise), confirming calibration fixes absolute probability scale without touching ranking quality.

**Reading the gap column:** this is "full-column CV AUC minus selected-column CV AUC" — how much AUC the
screened-down model gives up relative to using everything. HMEQ's gap is essentially zero (0.0009, within
fold noise) — strong confirmation that its one excluded column (`REASON`) truly carries nothing. PAK and
German Credit both give up ~0.02 AUC for a much smaller column count (4/51 and 5/20 respectively) — a
reasonable interpretability/parsimony trade-off, not a sign the screening missed something, given both gaps
are small relative to the full model's own CV standard deviation (German Credit's full-model std alone is
0.0315 — larger than the entire gap).
| mortgage.csv | 622,489 | 23 | 64.061 MB | Not started | — | — | — | — |
| lending_club_q12019.csv | 39,717 | 111 | 30.996 MB | Not started (111 cols — Shapley step will need heavy Step 1-4 pre-screening before it's tractable) | — | — | — | — |
| GMSC.csv | 149,391 | 11 | 6.239 MB | Not started | — | — | — | — |
| bank_marketing_additional_full.csv | 41,188 | 21 | 5.565 MB | Not started | — | — | — | — |
| bank_marketing_dataset.csv | 45,211 | 17 | 3.181 MB | Not started | — | — | — | — |
| Taiwan_UCI_Credit_Card.csv | 30,000 | 24 | 2.610 MB | Not started | — | — | — | — |
| credit_risk_dataset.csv | 32,581 | 17 | 1.815 MB | Not started | — | — | — | — |
| loan_data.csv | 9,578 | 14 | 0.726 MB | Not started | — | — | — | — |
| heloc.csv | 10,459 | 24 | 0.622 MB | Not started | — | — | — | — |
| MSME_Credit_Data.csv | 1,707 | 88 | 0.462 MB | Not started | — | — | — | — |
| TH02.csv | 1,225 | 15 | 0.048 MB | Not started | — | — | — | — |
| credit_approval_dataset.csv | 690 | 16 | 0.031 MB | Not started | — | — | — | — |
| Australian_Credit.csv | 690 | 15 | 0.028 MB | Not started | — | — | — | — |

---

## Notes

- **"Cols selected"** counts only the raw feature columns kept in the final model (excludes target), out of
  the dataset's total raw feature columns (also excluding target) — matches the convention used in each
  dataset's own findings log.
- **GPU note:** per `gpu_cpu_benchmark_2d_results.json`, the auto device-selection heuristic in
  `trainer.py` (`_gpu_worthwhile`) picks GPU once `rows × cols ≥ 2,000,000` or `rows ≥ 200,000`. Of the
  not-yet-started datasets, only `mortgage.csv` (622,489 rows) and `lending_club_q12019.csv` (39,717 rows ×
  111 cols ≈ 4.4M cells) would currently trigger GPU automatically during training.
- Update this table's status/cols-selected/AUC columns as each dataset completes the full v2 procedure
  (Steps 1-4 per Five C's category, then the pooled Shapley/BH run) — do not fill these in from a partial or
  v1-style analysis.
- **Calibration (Step 6) is now a standard part of completing any dataset, not an optional extra** — every
  future dataset's final model should get isotonic-regression calibration applied and its Brier/ECE
  before-vs-after results added to this table's calibration section and to that dataset's own findings log,
  the same way it was done for German Credit, PAK, HMEQ, and GMSC on 2026-10-09.
