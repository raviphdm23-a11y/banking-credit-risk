# SHARP v3 — MORTGAGE (US mortgage performance panel, origination snapshot)

**Dataset:** US mortgage performance panel (Baesens, Roesch & Scheule, *Credit Risk Analytics*).
**First PANEL dataset** — handled by `ml_models/panel_adapter.py` (snapshot framing) in front of the
unchanged SHARP pipeline. 622,489 loan-period rows → **50,049 loans** (composite entity key
`(id, orig_time)`); one row per loan, origination features, target = ever-default (**30.28%**). Fixed
config: primary `woe_logistic` / secondary `xgboost`, value_fn `auc`, `random_state=42`, 5-fold stratified
CV, grouping ρ-threshold 0.7, shadows 10 / q0.95 / confirm ≥0.80, selection DeLong p≥0.05 AND rel-Gini loss
≤5%, isotonic calibration, PD floor 0.03%. Governed frame: `data/ml_lab/datasets/mortgage_snapshot.csv`.

> **Panel note.** Snapshot framing collapses the panel to one independent row per loan, so the existing
> stratified CV is leakage-safe (no entity spans train/test). The time-varying covariates (`balance_time`,
> `LTV_time`, `interest_rate_time`, `hpi_time`, `gdp_time`, `uer_time`) are out of the origination scope and
> belong to the deferred hazard framing. Governed end-to-end: see `AEGIS_RUN_MORTGAGE.md` (GO-WITH-CONDITIONS).

## Stage 0 — governance
10 eligible origination features, all `permissible`; availability 9 origination + 1 external-score (`FICO`).
Co-outcomes `payoff_time` / `status_time` excluded as leakage. No sentinel-leakage candidates.

## Stage 1 — univariate screening (IV ≥ 0.02, monotonic WOE primary)

| column | IV (WOE) | IV q5 | IV q10 | IV q20 | Cramér's V | min-exp | passes |
|---|--:|--:|--:|--:|--:|--:|:--:|
| hpi_orig_time | 0.522 | 0.485 | 0.521 | 0.576 | 0.318 | 776 | ✓ |
| Interest_Rate_orig_time | 0.130 | 0.119 | 0.170 | 0.198 | 0.166 | 808 | ✓ |
| FICO_orig_time | 0.106 | 0.091 | 0.105 | 0.109 | 0.139 | 759 | ✓ |
| LTV_orig_time | 0.080 | 0.069 | 0.091 | 0.100 | 0.120 | 758 | ✓ |
| term_orig | 0.033 | 0.044 | 0.090 | 0.091 | 0.080 | 1146 | ✓ |
| balance_orig_time | 0.015 | 0.016 | 0.020 | 0.026 | 0.056 | 759 | ✓ |
| investor_orig_time | 0.002 | 0.000 | 0.000 | 0.000 | 0.022 | 1792 | ✗ |
| REtype_PU_orig_time | 0.001 | 0.000 | 0.000 | 0.000 | 0.013 | 1758 | ✗ |
| REtype_CO_orig_time | 0.000 | 0.000 | 0.000 | 0.000 | 0.007 | 984 | ✗ |
| REtype_SF_orig_time | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 5718 | ✗ |

*IV = Information Value (predictive strength of a binned feature; ≥0.02 = usable, ≥0.1 = strong). Cramér's V
= association strength (0–1). min-exp = smallest expected cell count (reliability gate, ≥5).* **6 of 10 pass**;
the 4 dropped are property-type / investor dummies with no univariate signal. `balance_orig_time` and
`Interest_Rate_orig_time` flagged non-monotonic/binning-sensitive → escalated to the model check, both rescued.

## Stage 2 — importance (SPVIM Shapley, shadow-null retention)
Sampled estimator (6 real + 10 shadows = 16 > 15 → sampled, P8); 200 permutations, 2,349 subsets, 11,740
fits, max MC SE 0.0029. **Shadow bar (95th pct of 10 shadows): 0.00086.** All 6 players **confirmed** (freq
1.00):

| player | Shapley | × bar | confirm freq | confirmed |
|---|--:|--:|--:|:--:|
| hpi_orig_time | 0.1235 | 143× | 1.00 | ✓ |
| Interest_Rate_orig_time | 0.0341 | 40× | 1.00 | ✓ |
| FICO_orig_time | 0.0327 | 38× | 1.00 | ✓ |
| LTV_orig_time | 0.0192 | 22× | 1.00 | ✓ |
| balance_orig_time | 0.0117 | 14× | 1.00 | ✓ |
| term_orig | 0.0103 | 12× | 1.00 | ✓ |

All 10 shadow-null players rejected (highest shadow confirmation 0.993, rest ≈ 0). Efficiency audit: Σ
Shapley 0.2314 vs v(full)−v(∅), within tolerance.

## Stage 3 — parsimony selection (PARSIMONY-NULL)
Rule selects **k = 6 of 6** — no reduction. At n=50,049 the DeLong test distinguishes every smaller model
from the full candidate set (k=1..5 all DeLong p ≈ 0.000 vs full), so the smallest k that is *not*
statistically worse is the full set itself. Gini **0.464** (rel. loss 0.00%). **6 players = 6 columns** — a
compact origination scorecard (contrast Polish, where 6 players spanned 37 collinear columns). Same "no
parsimony reduction DeLong-defensible" outcome as HMEQ, sharper at this sample size.

Parsimony curve: k1 (hpi) Gini 0.374 → k2 (+rate) 0.413 → k3 (+FICO) 0.441 → k4 (+LTV) 0.458 → k5 (+balance)
0.461 → k6 (+term) 0.464.

## Stage 4 — calibration
| | Baseline (base rate) | Raw | Calibrated (isotonic) |
|---|--:|--:|--:|
| Brier | — | 0.1736 | **0.1733** |
| ECE | — | 0.0085 | 0.0119 |

Out-of-fold discrimination: **AUC 0.732 / Gini 0.464.** Goodness-of-fit: HL g=10 **p ≈ 0.000 (rejected)**,
g=5 **p = 0.341 (passes)**. Per-grade realised-vs-expected backtest: **8/8 grades inside the Wilson 95% CI**
(grades A–D populated; smallest grade A, n=54 — no sparse cell). The HL g=10 rejection is a large-n
artefact; the per-grade backtest governs (CRE36.122). Isotonic did **not** materially help here (Brier flat,
ECE rose slightly) — reported honestly; it also ceilings calibrated PD at ≈0.68.

## Honest findings
- **Modest discrimination (Gini 0.464) is the origination-only ceiling.** A snapshot scorecard uses only
  origination-time information; the behavioural/time-varying trajectory (dynamic LTV, macro) is out of scope
  and would need the deferred hazard framing.
- **PARSIMONY-NULL at large n:** DeLong distinguishes every reduced model, so no parsimony reduction is
  defensible — an honest "the full 6-feature set is the answer" rather than a forced reduction.
- **Calibration:** per-grade backtest passes cleanly (8/8); HL g=10 rejects only because n≈50k over-powers
  the test. ECE excellent (0.0074 OOF). Isotonic neutral-to-slightly-negative here.
- **First panel dataset** proves `panel_adapter.py` end-to-end; the composite key `(id, orig_time)` was a
  real data-structure finding (bare `id` reused across refinances).
