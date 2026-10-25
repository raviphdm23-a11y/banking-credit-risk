# SHARP v3 — MORTGAGE_HAZARD (US mortgage panel, discrete-time hazard)

**Dataset:** US mortgage performance panel (Baesens et al.). **Discrete-time HAZARD framing** via
`ml_models/panel_adapter.py`: all 622,489 loan-period rows kept (50,049 loans, composite key `(id,orig_time)`),
target = default **in that period** (per-period hazard, 2.44%). Group-aware CV (StratifiedGroupKFold by loan)
threaded through Stages 2–4. Fixed config otherwise as per corpus (seed 42, IV≥0.02 monotonic WOE, shadows
10/q0.95/confirm≥0.80, DeLong p≥0.05 AND rel-Gini ≤5%, isotonic calibration, PD floor 0.03%). Governed →
GO-WITH-CONDITIONS (`AEGIS_RUN_MORTGAGE_HAZARD.md`).

## Stage 0 — governance
15 eligible features: 3 time-varying (`balance_time`, `LTV_time`, `interest_rate_time`), 3 macro
(`hpi_time`, `gdp_time`, `uer_time`), 9 origination. Co-outcomes `payoff_time` / `status_time` excluded as
leakage.

## Stage 1 — screening
**11 of 15 pass** IV ≥ 0.02 (vs snapshot's 6/10 — the time-varying covariates clear). Top IVs: `LTV_time`
0.399 (dynamic LTV), `interest_rate_time` 0.257, `hpi_orig_time` 0.213, `gdp_time` 0.208, `FICO_orig_time`
0.153. Dropped: the 4 property-type / investor dummies (IV < 0.02).

## Stage 2 — importance (grouped-CV Shapley, shadow-null)
Sampled estimator (19 players > 15, P8), 200 permutations on a group-aware 80k-row subsample; shadow bar
**0.00089**. **All 9 players confirmed** (freq 1.00):

| player | Shapley | × bar |
|---|--:|--:|
| interest_rate_time *(time-varying)* | 0.0532 | 60× |
| LTV_time *(time-varying)* | 0.0426 | 48× |
| FICO_orig_time | 0.0308 | 35× |
| hpi_orig_time | 0.0260 | 29× |
| gdp_time *(macro)* | 0.0259 | 29× |
| Interest_Rate_orig_time | 0.0216 | 24× |
| grp[hpi_time+uer_time] *(macro)* | 0.0185 | 21× |
| LTV_orig_time | 0.0097 | 11× |
| grp[balance_orig_time+balance_time] | 0.0092 | 10× |

All 10 shadow-null players rejected (top shadow freq 0.85). The two strongest drivers are the dynamic,
time-varying covariates — signal the origination snapshot cannot access.

## Stage 3 — parsimony (PARSIMONY-NULL)
k = 9 of 9 (**11 columns**). At n = 622,489 DeLong distinguishes every k<9 from the full set (all p ≈ 0),
so the full confirmed set is adopted. Gini **0.474**. Curve: k1 (interest_rate) 0.276 → k2 (+LTV_time) 0.437
→ k3 (+FICO) 0.453 → k5 (+gdp) 0.463 → k9 (full) 0.474. **Checked afterwards:** a cluster-robust DeLong
(`selection.cluster_delong_test`, cluster bootstrap over loans) does not rescue parsimony — k=2/3/5 stay
distinguishable from the full set (p ≈ 0; the 0.006 AUC gap at k=5 is ~10 cluster SEs). PARSIMONY-NULL is
genuine at 50,049 loans (k=2 reaches 92% of full Gini but at 7.8% relative loss, over the 5% bar).

## Stage 4 — calibration (deployed model, cluster-robust)
Discrimination AUC 0.737 / Gini 0.474 (grouped OOF). Calibration assessed on the **deployed**
(isotonically-calibrated) model, held out on 10,010 loans, cluster-robust:

| | value |
|---|---|
| per-grade backtest (cluster-bootstrap CI) | **7/7 inside CI** |
| HL g=10 | p = 0.11 raw / 0.65 design-effect-adj (not rejected) |
| HL g=5 | p = 0.36 / 0.69 |
| ECE | 0.0005 |

**Methodology finding (important).** The per-grade backtest and HL, run the old way (on the raw WOE-logistic
OOF, i.i.d. CIs over 622k clustered rows), over-rejected badly (1/7, HL p≈0). Investigation showed this was
**not** a pseudo-replication rescue — the raw per-grade bias was real — but it is removed by the always-on
isotonic step, and the interval must be cluster-robust. Fix shipped as `ml_models/calibration_gof.py`
(`deployment_backtest`, wired into Stage 4): assess the CALIBRATED model with a cluster-bootstrap per-grade CI
+ design-effect HL, auto-triggered by the groups vector. Now standard for every panel run.

## Honest findings
- **Hazard vs snapshot is not a like-for-like comparison.** The hazard Gini (0.474) is per-period default;
  the snapshot Gini (0.464) is ever-default. Neither run supports "one is better"; a horizon-aggregated
  loan-level evaluation would be needed.
- **Two methodology upgrades were forced by this run, both shipped:** (1) the deployed-model, cluster-robust
  calibration backtest; (2) a cluster-robust DeLong for parsimony — which confirmed rather than rescued
  PARSIMONY-NULL.
- **Out-of-time validation (R7) was added post-GF** (`ml_models/oot_validation.py`): train t ≤ 42, test t > 42
  → OOT Gini **0.319** (−33% vs in-time 0.474), OOT AUC 0.660, calibrated-on-past per-grade **3/7**, HL
  rejected; consistent across cuts 0.2/0.3/0.4 (Gini 0.315/0.319/0.299). The cause is only partly the
  macro covariates (dropping them: +0.028 Gini) and is confounded by loan-age mix shift (mean age 10 → 29
  months across the cut; no loan-age feature in the model) — untested. See the addendum in
  `AEGIS_RUN_MORTGAGE_HAZARD.md`.
