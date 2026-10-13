# heloc - Methodology v3 results

Rows: 10459 | Raw columns: 23 | Event rate: 0.5219

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `ExternalRiskEstimate` | permissible | external_score | No name-based match to a prohibited or proxy-risk pattern. |
| `MSinceOldestTradeOpen` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `MSinceMostRecentTradeOpen` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `AverageMInFile` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumSatisfactoryTrades` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumTrades60Ever2DerogPubRec` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumTrades90Ever2DerogPubRec` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PercentTradesNeverDelq` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `MSinceMostRecentDelq` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `MaxDelq2PublicRecLast12M` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `MaxDelqEver` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumTotalTrades` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumTradesOpeninLast12M` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PercentInstallTrades` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `MSinceMostRecentInqexcl7days` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumInqLast6M` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumInqLast6Mexcl7days` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NetFractionRevolvingBurden` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NetFractionInstallBurden` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumRevolvingTradesWBalance` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumInstallTradesWBalance` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `NumBank2NatlTradesWHighUtilization` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |
| `PercentTradesWBalance` | permissible | behavioural | No name-based match to a prohibited or proxy-risk pattern. |

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ExternalRiskEstimate | 0.8724 | 0.8411 | 0.9006 | 0.9155 | False | False | 0.4396 | 255.7606 | True | none |  | True |
| NetFractionRevolvingBurden | 0.4398 | 0.4368 | 0.5390 | 0.5429 | False | False | 0.3164 | 250.9800 | True | none |  | True |
| NumBank2NatlTradesWHighUtilization | 0.3429 | 0.2164 | 0.3266 | 0.3290 | False | False | 0.2859 | 278.7073 | True | none |  | True |
| MaxDelq2PublicRecLast12M | 0.3043 | 0.2646 | 0.2780 | 0.2780 | False | False | 0.2686 | 281.0976 | True | none |  | True |
| PercentTradesNeverDelq | 0.2951 | 0.2768 | 0.3064 | 0.3094 | False | False | 0.2660 | 268.6681 | True | none |  | True |
| PercentTradesWBalance | 0.2787 | 0.2686 | 0.2850 | 0.2943 | False | False | 0.2572 | 267.7120 | True | none |  | True |
| MSinceMostRecentInqexcl7days | 0.2698 | 0.1654 | 0.2265 | 0.2321 | False | False | 0.2553 | 281.0976 | True | none |  | True |
| MSinceMostRecentDelq | 0.2579 | 0.2545 | 0.2599 | 0.2621 | False | False | 0.2471 | 275.3609 | True | none |  | True |
| AverageMInFile | 0.2513 | 0.2437 | 0.2549 | 0.2616 | False | False | 0.2456 | 269.1462 | True | none |  | True |
| MaxDelqEver | 0.2092 | 0.2044 | 0.2049 | 0.2055 | False | False | 0.2258 | 281.0976 | True | none |  | True |
| MSinceOldestTradeOpen | 0.1768 | 0.1661 | 0.1997 | 0.2065 | False | False | 0.2069 | 265.7998 | True | none |  | True |
| NumTrades60Ever2DerogPubRec | 0.1728 | 0.1649 | 0.1649 | 0.1653 | False | False | 0.2031 | 274.8829 | True | none |  | True |
| NumTrades90Ever2DerogPubRec | 0.1261 | 0.1212 | 0.1212 | 0.1217 | False | False | 0.1729 | 281.0976 | True | none |  | True |
| NumInqLast6M | 0.0896 | 0.0719 | 0.0806 | 0.0899 | False | False | 0.1476 | 281.0976 | True | none |  | True |
| NumSatisfactoryTrades | 0.0880 | 0.0838 | 0.0876 | 0.0923 | False | False | 0.1467 | 261.4973 | True | none |  | True |
| NumInqLast6Mexcl7days | 0.0824 | 0.0680 | 0.0738 | 0.0816 | False | False | 0.1416 | 281.0976 | True | none |  | True |
| PercentInstallTrades | 0.0806 | 0.0769 | 0.0910 | 0.0948 | False | False | 0.1397 | 261.9753 | True | none |  | True |
| NumRevolvingTradesWBalance | 0.0610 | 0.0686 | 0.0817 | 0.0832 | False | True | 0.1222 | 355.6745 | True | model_check_shape |  | True |
| NumTotalTrades | 0.0468 | 0.0450 | 0.0490 | 0.0543 | False | False | 0.1076 | 441.2468 | True | none |  | True |
| NetFractionInstallBurden | 0.0300 | 0.0316 | 0.0317 | 0.0405 | False | False | 0.0863 | 522.0384 | True | none |  | True |
| NumTradesOpeninLast12M | 0.0196 | 0.0158 | 0.0164 | 0.0206 | True | False | 0.0697 | 281.0976 | True | model_check_shape |  | True |
| NumInstallTradesWBalance | 0.0196 | 0.0155 | 0.0155 | 0.0156 | False | False | 0.0697 | 281.0976 | True | none |  | False |
| MSinceMostRecentTradeOpen | 0.0171 | 0.0123 | 0.0207 | 0.0235 | True | False | 0.0653 | 274.8829 | True | model_check_shape |  | True |

Candidates passing Stage 1: 22 of 23.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| ExternalRiskEstimate | 1 | False | 0.04603 | 0.00454 | 1.00000 | True | 0.00000 | 0.71747 |
| grp[NetFractionRevolvingBurden+NumBank2NatlTradesWHighUtilization] | 2 | False | 0.04352 | 0.00368 | 1.00000 | True | 0.00000 | 0.83565 |
| MSinceMostRecentDelq | 1 | False | 0.03004 | 0.00309 | 1.00000 | True | 0.00000 | 0.68794 |
| grp[AverageMInFile+MSinceOldestTradeOpen] | 2 | False | 0.02933 | 0.00270 | 1.00000 | True | 0.00000 | 0.76884 |
| grp[MaxDelq2PublicRecLast12M+MaxDelqEver+PercentTradesNeverDelq] | 3 | False | 0.02783 | 0.00336 | 1.00000 | True | 0.00000 | 0.58566 |
| MSinceMostRecentInqexcl7days | 1 | False | 0.02550 | 0.00196 | 1.00000 | True | 0.00000 | 0.92161 |
| PercentTradesWBalance | 1 | False | 0.02280 | 0.00269 | 1.00000 | True | 0.00000 | 0.59953 |
| grp[NumTrades60Ever2DerogPubRec+NumTrades90Ever2DerogPubRec] | 2 | False | 0.01498 | 0.00192 | 1.00000 | True | 0.00000 | 0.55238 |
| grp[NumSatisfactoryTrades+NumTotalTrades] | 2 | False | 0.01221 | 0.00146 | 1.00000 | True | 0.00000 | 0.59066 |
| NumRevolvingTradesWBalance | 1 | False | 0.01172 | 0.00157 | 1.00000 | True | 0.00000 | 0.52794 |
| PercentInstallTrades | 1 | False | 0.01003 | 0.00123 | 1.00000 | True | 0.00000 | 0.57920 |
| grp[NumInqLast6M+NumInqLast6Mexcl7days] | 2 | False | 0.00947 | 0.00133 | 1.00000 | True | 0.00000 | 0.50507 |
| NetFractionInstallBurden | 1 | False | 0.00392 | 0.00074 | 1.00000 | True | 0.00000 | 0.37678 |
| NumTradesOpeninLast12M | 1 | False | 0.00346 | 0.00064 | 1.00000 | True | 0.00000 | 0.37966 |
| MSinceMostRecentTradeOpen | 1 | False | 0.00277 | 0.00049 | 0.99950 | True | 0.00000 | 0.39871 |
| __shadow__5_NetFractionInstallBurden | 1 | True | 0.00142 | 0.00027 | 0.97900 | False | 0.00000 | 0.37643 |
| __shadow__0_NumTrades60Ever2DerogPubRec | 1 | True | 0.00080 | 0.00018 | 0.02100 | False | 0.00001 | 0.32127 |
| __shadow__7_NumTotalTrades | 1 | True | 0.00034 | 0.00011 | 0.00000 | False | 0.00260 | 0.22174 |
| __shadow__8_NetFractionRevolvingBurden | 1 | True | 0.00011 | 0.00007 | 0.00000 | False | 0.12951 | 0.10913 |
| __shadow__3_PercentTradesWBalance | 1 | True | 0.00007 | 0.00003 | 0.00000 | False | 0.01292 | 0.18183 |
| __shadow__1_NumTrades90Ever2DerogPubRec | 1 | True | -0.00001 | 0.00002 | 0.00000 | False | 0.51310 | -0.04633 |
| __shadow__9_NumBank2NatlTradesWHighUtilization | 1 | True | -0.00004 | 0.00002 | 0.00000 | False | 0.06338 | -0.13466 |
| __shadow__6_NumSatisfactoryTrades | 1 | True | -0.00011 | 0.00006 | 0.00000 | False | 0.05006 | -0.14329 |
| __shadow__2_MSinceMostRecentDelq | 1 | True | -0.00012 | 0.00004 | 0.00000 | False | 0.00317 | -0.21621 |
| __shadow__4_PercentInstallTrades | 1 | True | -0.00230 | 0.00037 | 0.00000 | False | 0.00000 | -0.44438 |

Shadow bar (95th pct of 10 shadow players): **0.00114**. Mode: sampled. Subsets evaluated: 4320. Model fits: 21595.

Implementation audit (efficiency property): sum of Shapley values 0.293756 vs v(full)-v(empty) 0.293756, abs diff 5.55e-17. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | ExternalRiskEstimate | 1 | 0.4896 | [0.4695, 0.5091] | 0.3921 | 0.6979 | 0.2018 | 16.70% | 0.0000 |
| 2 | grp[NetFractionRevolvingBurden+NumBank2NatlTradesWHighUtilization] | 3 | 0.5192 | [0.5004, 0.5374] | 0.3988 | 0.7166 | 0.1988 | 11.67% | 0.0000 |
| 3 | MSinceMostRecentDelq | 4 | 0.5228 | [0.5041, 0.5408] | 0.4004 | 0.7186 | 0.1980 | 11.04% | 0.0000 |
| 4 | grp[AverageMInFile+MSinceOldestTradeOpen] | 6 | 0.5452 | [0.5264, 0.5620] | 0.4226 | 0.7299 | 0.1934 | 7.23% | 0.0000 |
| 5 | grp[MaxDelq2PublicRecLast12M+MaxDelqEver+PercentTradesNeverDelq] | 9 | 0.5474 | [0.5288, 0.5641] | 0.4252 | 0.7307 | 0.1928 | 6.86% | 0.0000 |
| 6 | MSinceMostRecentInqexcl7days | 10 | 0.5750 | [0.5569, 0.5908] | 0.4366 | 0.7443 | 0.1872 | 2.17% | 0.0000 |
| 7 | PercentTradesWBalance | 11 | 0.5799 | [0.5627, 0.5955] | 0.4424 | 0.7478 | 0.1863 | 1.34% | 0.0004 |
| 8 | grp[NumTrades60Ever2DerogPubRec+NumTrades90Ever2DerogPubRec] | 13 | 0.5813 | [0.5642, 0.5968] | 0.4440 | 0.7486 | 0.1859 | 1.09% | 0.0023 |
| 9 | grp[NumSatisfactoryTrades+NumTotalTrades] | 15 | 0.5832 | [0.5657, 0.5988] | 0.4461 | 0.7489 | 0.1854 | 0.77% | 0.0081 |
| 10 | NumRevolvingTradesWBalance | 16 | 0.5838 | [0.5664, 0.5995] | 0.4510 | 0.7489 | 0.1852 | 0.67% | 0.0124 |
| 11 | PercentInstallTrades | 17 | 0.5870 | [0.5692, 0.6027] | 0.4528 | 0.7509 | 0.1845 | 0.12% | 0.5069 |
| 12 | grp[NumInqLast6M+NumInqLast6Mexcl7days] | 19 | 0.5883 | [0.5711, 0.6044] | 0.4528 | 0.7515 | 0.1841 | -0.10% | 0.3417 |
| 13 | NetFractionInstallBurden | 20 | 0.5886 | [0.5714, 0.6045] | 0.4535 | 0.7519 | 0.1841 | -0.14% | 0.0751 |
| 14 | NumTradesOpeninLast12M | 21 | 0.5881 | [0.5710, 0.6040] | 0.4539 | 0.7517 | 0.1842 | -0.07% | 0.2631 |
| 15 | MSinceMostRecentTradeOpen | 22 | 0.5877 | [0.5708, 0.6036] | 0.4531 | 0.7514 | 0.1843 | 0.00% | 1.0000 |

**Selected k = 11** (17 columns, Gini 0.5870, relative loss 0.12%, DeLong p = 0.5069). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`ExternalRiskEstimate [external_score]`, `NetFractionRevolvingBurden`, `NumBank2NatlTradesWHighUtilization`, `MSinceMostRecentDelq`, `AverageMInFile`, `MSinceOldestTradeOpen`, `MaxDelq2PublicRecLast12M`, `MaxDelqEver`, `PercentTradesNeverDelq`, `MSinceMostRecentInqexcl7days`, `PercentTradesWBalance`, `NumTrades60Ever2DerogPubRec`, `NumTrades90Ever2DerogPubRec`, `NumSatisfactoryTrades`, `NumTotalTrades`, `NumRevolvingTradesWBalance`, `PercentInstallTrades`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.2495 | 0.1848 | **0.1843** |
| ECE | - | 0.0132 | **0.0127** |

**Availability caveat (external_score):** `ExternalRiskEstimate`. Results including these are not an origination-time (application) model; report with and without them (METHODOLOGY v3 s3.3).

## Stage 4b - per-grade calibration backtest (AEGIS condition in G4; CRE36.122-123)

Held-out 80/20 split (random_state=42), 17-col model, calibrated PD floored at 0.03%, mapped to master scale.
Test n=2,092, AUC 0.7899.

| Grade | n | Expected | Realised | 95% CI (Wilson) | Within? |
|---|--:|--:|--:|---|:--:|
| BB | 27 | 5.5% | 3.7% | [0.7%, 18.3%] | OK |
| B | 149 | 9.7% | 14.8% | [10.0%, 21.3%] | REVIEW (under-predict) |
| CCC | 170 | 14.9% | 17.1% | [12.1%, 23.4%] | OK |
| CC | 274 | 25.7% | 29.9% | [24.8%, 35.6%] | OK |
| C | 282 | 42.0% | 37.9% | [32.5%, 43.7%] | OK |
| D | 1190 | 72.0% | 71.5% | [68.9%, 74.0%] | OK |

**Overall ECE 0.0300; Hosmer-Lemeshow chi2=15.45, df=8, p=0.051 => passes MARGINALLY** (on the 0.05 line).
5/6 grades pass. 52%-default balanced benchmark concentrates mass in grade D. Carry a Margin of Conservatism
for the under-predicting B grade and monitor calibration closely (condition HC-cal).
