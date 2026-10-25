# SHARP record — POLISH_1YR (Polish bankruptcy, 1-year-ahead horizon)

**Run:** POLISH_1YR · staged SHARP+AEGIS protocol (`ml_models/staged_run.py`; each stage stopped at its gate and ran only after the previous gate was signed). Chain and state: `sharp_runs_staged/POLISH_1YR/chain.json`, `state.pkl`.
**Data:** `data/ml_lab/datasets/polish_bankruptcy_1yr_ahead.csv` (UCI #365 "5year" file; ratios observed 1 year before the status check). 5,910 firms · 410 bankrupt (6.94%) · 64 candidate ratios. Cross-section, not a panel. Seed 42, fixed SHARP configuration (unchanged `v3_pipeline`).
**Equivalence:** the staged runner reproduces the one-shot `run_pipeline` output (`testing/test_staged_equivalence.py`, 17 checks pass on `south_german_credit_en.csv`; same shadow bar 0.00161 and Shapley values on this file's first one-shot run).
**Governed outcome:** GF **GO-WITH-CONDITIONS** `209136ae` — see `AEGIS_RUN_POLISH_1YR.md`.

> Everything below the rule is the pipeline's own stage report (`StagedRun.final_report()`); the addendum after it records points the report does not carry.

---

# POLISH_1YR - Methodology v3 results

Rows: 5910 | Raw columns: 64 | Event rate: 0.0694

Learner (value function): `woe_logistic` | Value function: `auc`

## Stage 0 - governance

| Column | Eligibility | Availability | Basis |
|---|---|---|---|
| `net_profit_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_liabilities_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `working_capital_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `current_assets_to_short_term_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `cash_sec_recv_minus_stl_to_opex_minus_depr_x365` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `retained_earnings_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `ebit_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `book_value_equity_to_total_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `equity_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_plus_extraord_items_plus_fin_expenses_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_to_short_term_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_plus_depreciation_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_plus_interest_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_liabilities_x365_to_gross_profit_plus_depreciation` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_plus_depreciation_to_total_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_assets_to_total_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `inventory_x365_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_n_to_sales_n_minus_1` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `operating_profit_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `net_profit_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_in_3_years_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `equity_minus_share_capital_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `net_profit_plus_depreciation_to_total_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `operating_profit_to_financial_expenses` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `working_capital_to_fixed_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `log_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_liabilities_minus_cash_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `gross_profit_plus_interest_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `current_liabilities_x365_to_cost_of_products_sold` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `operating_expenses_to_short_term_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `operating_expenses_to_total_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_profit_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_sales_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `current_assets_minus_inventories_to_long_term_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `constant_capital_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_profit_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `ca_minus_inv_minus_recv_to_stl` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_liabilities_to_operating_profit_plus_depreciation_x_12_365` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `operating_profit_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `receivables_plus_inventory_turnover_days` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `receivables_x365_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `net_profit_to_inventory` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `current_assets_minus_inventory_to_short_term_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `inventory_x365_to_cost_of_products_sold` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `ebitda_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `ebitda_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `current_assets_to_total_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `short_term_liabilities_to_total_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `short_term_liabilities_x365_to_cost_of_products_sold` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `equity_to_fixed_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `constant_capital_to_fixed_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `working_capital` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_minus_cost_of_products_sold_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `ca_minus_inv_minus_stl_to_sales_minus_gp_minus_depr` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `total_costs_to_total_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `long_term_liabilities_to_equity` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_to_inventory` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_to_receivables` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `short_term_liabilities_x365_to_sales` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_to_short_term_liabilities` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |
| `sales_to_fixed_assets` | permissible | origination | No name-based match to a prohibited or proxy-risk pattern. |

**Sentinel leakage candidates (unresolved):** `working_capital` - see METHODOLOGY v3 s3.5.

## Stage 1 - univariate screening

| column | iv_woe | iv_q5 | iv_q10 | iv_q20 | binning_sensitive | shape_nonmonotonic | cramers_v_descriptive | min_expected | gate_ok | escalation | mann_whitney_p | passes_screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sales_n_to_sales_n_minus_1 | 2.1917 | 2.1354 | 2.2418 | 2.2655 | False | False | 0.5139 | 7.1455 | True | none |  | True |
| operating_profit_to_financial_expenses | 1.5959 | 1.3489 | 1.7747 | 2.4182 | False | False | 0.3962 | 27.1252 | True | none |  | True |
| sales_profit_to_total_assets | 1.4596 | 1.1020 | 1.3413 | 1.5540 | False | False | 0.4106 | 0.2081 | False | mann_whitney | 0.0000 | True |
| sales_profit_to_sales | 1.4347 | 1.1257 | 1.3749 | 1.4811 | False | False | 0.3965 | 20.4653 | True | none |  | True |
| total_liabilities_to_operating_profit_plus_depreciation_x_12_365 | 1.4078 | 1.1573 | 1.5410 | 1.6378 | False | False | 0.3255 | 5.8274 | True | none |  | True |
| total_liabilities_x365_to_gross_profit_plus_depreciation | 1.3850 | 1.0549 | 1.0815 | 1.3883 | False | False | 0.3573 | 0.4162 | False | mann_whitney | 0.0000 | True |
| gross_profit_plus_depreciation_to_sales | 1.3406 | 1.0888 | 1.2697 | 1.3657 | False | False | 0.3744 | 20.4653 | True | none |  | True |
| gross_profit_plus_depreciation_to_total_liabilities | 1.3398 | 1.1989 | 1.3300 | 1.3827 | False | False | 0.3554 | 1.2487 | False | mann_whitney | 0.0000 | True |
| net_profit_plus_depreciation_to_total_liabilities | 1.3297 | 1.1727 | 1.3199 | 1.3959 | False | False | 0.3540 | 1.2487 | False | mann_whitney | 0.0000 | True |
| operating_profit_to_total_assets | 1.3150 | 0.6682 | 1.1719 | 1.5520 | False | False | 0.3922 | 0.2081 | False | mann_whitney | 0.0000 | True |
| operating_profit_to_sales | 1.2932 | 0.7094 | 1.1723 | 1.4577 | False | False | 0.3860 | 20.4653 | True | none |  | True |
| net_profit_to_total_assets | 1.2499 | 1.0113 | 1.1848 | 1.3184 | False | False | 0.3660 | 0.2081 | False | mann_whitney | 0.0000 | True |
| net_profit_to_sales | 1.2241 | 1.0297 | 1.1832 | 1.2759 | False | False | 0.3518 | 20.4653 | True | none |  | True |
| gross_profit_to_sales | 1.2071 | 1.0467 | 1.1909 | 1.3377 | False | False | 0.3521 | 20.4653 | True | none |  | True |
| gross_profit_plus_interest_to_total_assets | 1.2059 | 1.0045 | 1.1690 | 1.2711 | False | False | 0.3585 | 0.2081 | False | mann_whitney | 0.0000 | True |
| gross_profit_to_total_assets | 1.2059 | 1.0045 | 1.1690 | 1.2711 | False | False | 0.3585 | 0.2081 | False | mann_whitney | 0.0000 | True |
| ebit_to_total_assets | 1.2058 | 1.0045 | 1.1689 | 1.2710 | False | False | 0.3585 | 0.2081 | False | mann_whitney | 0.0000 | True |
| gross_profit_plus_interest_to_sales | 1.1752 | 1.0504 | 1.1477 | 1.2641 | False | False | 0.3375 | 20.4653 | True | none |  | True |
| gross_profit_plus_extraord_items_plus_fin_expenses_to_total_assets | 1.1659 | 0.9659 | 1.1378 | 1.2142 | False | False | 0.3600 | 0.2081 | False | mann_whitney | 0.0000 | True |
| net_profit_to_inventory | 1.1611 | 1.0470 | 1.1879 | 1.2347 | False | False | 0.3137 | 18.5922 | True | none |  | True |
| gross_profit_to_short_term_liabilities | 1.1611 | 1.0827 | 1.1748 | 1.2369 | False | False | 0.3148 | 1.4569 | False | mann_whitney | 0.0000 | True |
| equity_minus_share_capital_to_total_assets | 1.0188 | 0.8751 | 0.9911 | 1.0377 | False | False | 0.2951 | 0.2081 | False | mann_whitney | 0.0000 | True |
| current_assets_minus_inventory_to_short_term_liabilities | 1.0090 | 0.8540 | 1.0041 | 1.1021 | False | False | 0.3152 | 1.4569 | False | mann_whitney | 0.0000 | True |
| working_capital | 0.9413 | 0.9114 | 0.9264 | 0.9638 | False | False | 0.2499 | 20.4653 | True | none |  | True |
| sales_minus_cost_of_products_sold_to_sales | 0.9317 | 0.7242 | 0.8945 | 1.0222 | False | False | 0.3226 | 20.4653 | True | none |  | True |
| retained_earnings_to_total_assets | 0.8690 | 0.7210 | 0.8267 | 0.9016 | False | False | 0.2360 | 0.2081 | False | mann_whitney | 0.0000 | True |
| gross_profit_in_3_years_to_total_assets | 0.8360 | 0.8313 | 0.9572 | 1.0375 | False | False | 0.2677 | 9.3655 | True | none |  | True |
| total_costs_to_total_sales | 0.8241 | 0.6706 | 0.7993 | 0.8741 | False | False | 0.2999 | 20.4653 | True | none |  | True |
| current_assets_to_short_term_liabilities | 0.8096 | 0.6722 | 0.7795 | 0.8830 | False | False | 0.2813 | 1.4569 | False | mann_whitney | 0.0000 | True |
| constant_capital_to_total_assets | 0.8070 | 0.6772 | 0.7498 | 0.8923 | False | False | 0.2804 | 0.2081 | False | mann_whitney | 0.0000 | True |
| ebitda_to_total_assets | 0.7839 | 0.6239 | 0.7484 | 0.8379 | False | False | 0.2823 | 0.2081 | False | mann_whitney | 0.0000 | True |
| working_capital_to_total_assets | 0.7727 | 0.6027 | 0.7335 | 0.8669 | False | False | 0.2845 | 0.2081 | False | mann_whitney | 0.0000 | True |
| constant_capital_to_fixed_assets | 0.7639 | 0.7421 | 0.8899 | 0.9808 | False | False | 0.2615 | 7.4230 | True | none |  | True |
| ebitda_to_sales | 0.7547 | 0.5941 | 0.7697 | 0.8426 | False | False | 0.2717 | 20.4653 | True | none |  | True |
| working_capital_to_fixed_assets | 0.7434 | 0.6785 | 0.8488 | 0.9090 | False | False | 0.2560 | 7.4230 | True | none |  | True |
| book_value_equity_to_total_liabilities | 0.7401 | 0.6404 | 0.7417 | 0.8265 | False | False | 0.2611 | 1.2487 | False | mann_whitney | 0.0000 | True |
| total_assets_to_total_liabilities | 0.7298 | 0.6340 | 0.7162 | 0.8308 | False | False | 0.2629 | 1.2487 | False | mann_whitney | 0.0000 | True |
| total_liabilities_to_total_assets | 0.7200 | 0.6145 | 0.6952 | 0.7940 | False | False | 0.2631 | 0.2081 | False | mann_whitney | 0.0000 | True |
| short_term_liabilities_to_total_assets | 0.7080 | 0.5655 | 0.6798 | 0.7701 | False | False | 0.2628 | 0.2081 | False | mann_whitney | 0.0000 | True |
| equity_to_total_assets | 0.7078 | 0.6123 | 0.7106 | 0.8210 | False | False | 0.2574 | 0.2081 | False | mann_whitney | 0.0000 | True |
| equity_to_fixed_assets | 0.6892 | 0.6607 | 0.7765 | 0.8551 | False | False | 0.2415 | 7.4230 | True | none |  | True |
| sales_to_short_term_liabilities | 0.6435 | 0.5045 | 0.6135 | 0.7126 | False | False | 0.2472 | 1.4569 | False | mann_whitney | 0.0000 | True |
| short_term_liabilities_x365_to_sales | 0.6316 | 0.4848 | 0.6134 | 0.7248 | False | False | 0.2465 | 20.4653 | True | none |  | True |
| current_assets_to_total_liabilities | 0.6158 | 0.5110 | 0.6349 | 0.7044 | False | False | 0.2329 | 1.2487 | False | mann_whitney | 0.0000 | True |
| cash_sec_recv_minus_stl_to_opex_minus_depr_x365 | 0.6147 | 0.5689 | 0.6001 | 0.6270 | False | False | 0.2203 | 0.7631 | False | mann_whitney | 0.0000 | True |
| ca_minus_inv_minus_stl_to_sales_minus_gp_minus_depr | 0.5620 | 0.5522 | 0.7376 | 0.8839 | False | True | 0.2528 | 0.2081 | False | mann_whitney+model_check_shape | 0.0000 | True |
| total_liabilities_minus_cash_to_sales | 0.4907 | 0.4338 | 0.4747 | 0.5323 | False | False | 0.2071 | 20.4653 | True | none |  | True |
| ca_minus_inv_minus_recv_to_stl | 0.4874 | 0.4022 | 0.4479 | 0.5192 | False | False | 0.2103 | 1.4569 | False | mann_whitney | 0.0000 | True |
| current_liabilities_x365_to_cost_of_products_sold | 0.4087 | 0.3564 | 0.4497 | 0.5463 | False | False | 0.1908 | 3.1912 | False | mann_whitney | 0.0000 | True |
| log_total_assets | 0.3921 | 0.3261 | 0.3816 | 0.4107 | False | False | 0.1809 | 0.2081 | False | mann_whitney | 0.0000 | True |
| short_term_liabilities_x365_to_cost_of_products_sold | 0.3768 | 0.3760 | 0.4493 | 0.5459 | False | False | 0.1480 | 2.4975 | False | mann_whitney | 0.0000 | True |
| operating_expenses_to_short_term_liabilities | 0.3024 | 0.2912 | 0.3341 | 0.3892 | False | False | 0.1564 | 1.4569 | False | mann_whitney | 0.0000 | True |
| long_term_liabilities_to_equity | 0.2245 | 0.1631 | 0.1976 | 0.2239 | False | False | 0.1107 | 0.2081 | False | mann_whitney | 0.0000 | True |
| inventory_x365_to_cost_of_products_sold | 0.1799 | 0.1719 | 0.2051 | 0.2583 | False | False | 0.0857 | 2.4281 | False | mann_whitney | 0.0001 | True |
| sales_to_total_assets | 0.1755 | 0.2586 | 0.3305 | 0.3771 | False | True | 0.1224 | 0.0694 | False | mann_whitney+model_check_shape | 0.0636 | True |
| receivables_x365_to_sales | 0.1402 | 0.1734 | 0.2119 | 0.2596 | False | True | 0.1058 | 20.4653 | True | model_check_shape |  | True |
| sales_to_receivables | 0.1373 | 0.1754 | 0.2109 | 0.2570 | False | True | 0.1061 | 1.0406 | False | mann_whitney+model_check_shape | 0.0000 | True |
| receivables_plus_inventory_turnover_days | 0.1122 | 0.1633 | 0.2121 | 0.2406 | False | True | 0.0982 | 20.4653 | True | model_check_shape |  | True |
| operating_expenses_to_total_liabilities | 0.0927 | 0.1256 | 0.1917 | 0.2609 | False | True | 0.0939 | 1.2487 | False | mann_whitney+model_check_shape | 0.2721 | True |
| sales_to_inventory | 0.0885 | 0.0896 | 0.1495 | 0.1900 | False | True | 0.0830 | 18.5922 | True | model_check_shape |  | True |
| total_sales_to_total_assets | 0.0754 | 0.0777 | 0.0996 | 0.1828 | False | True | 0.0827 | 0.2081 | False | mann_whitney+model_check_shape | 0.1380 | False |
| current_assets_minus_inventories_to_long_term_liabilities | 0.0665 | 0.0524 | 0.0581 | 0.0765 | False | False | 0.0619 | 35.0338 | True | none |  | True |
| inventory_x365_to_sales | 0.0642 | 0.0844 | 0.1460 | 0.1924 | False | True | 0.0729 | 20.4653 | True | model_check_shape |  | True |
| sales_to_fixed_assets | 0.0482 | 0.0651 | 0.1038 | 0.1375 | False | True | 0.0659 | 7.4230 | True | model_check_shape |  | True |

Candidates passing Stage 1: 63 of 64.

## Stage 2 - importance (SPVIM-style Shapley, shadow-null retention)

| player | n_columns | is_shadow | shapley | mc_se | confirmation_frequency | importance_confirmed | diag_bh_p | diag_cohens_d |
|---|---|---|---|---|---|---|---|---|
| grp[ebit_to_total_assets+ebitda_to_sales+ebitda_to_total_assets+gross_profit_in_3_years_to_total_assets+gross_profit_plus_depreciation_to_sales+gross_profit_plus_depreciation_to_total_liabilities+gross_profit_plus_extraord_items_plus_fin_expenses_to_total_assets+gross_profit_plus_interest_to_sales+gross_profit_plus_interest_to_total_assets+gross_profit_to_sales+gross_profit_to_short_term_liabilities+gross_profit_to_total_assets+net_profit_plus_depreciation_to_total_liabilities+net_profit_to_inventory+net_profit_to_sales+net_profit_to_total_assets+operating_profit_to_financial_expenses+operating_profit_to_sales+operating_profit_to_total_assets+sales_profit_to_sales+sales_profit_to_total_assets] | 21 | False | 0.07197 | 0.00529 | 1.00000 | True | 0.00000 | 0.96118 |
| sales_n_to_sales_n_minus_1 | 1 | False | 0.07017 | 0.00545 | 1.00000 | True | 0.00000 | 0.90976 |
| grp[total_liabilities_to_operating_profit_plus_depreciation_x_12_365+total_liabilities_x365_to_gross_profit_plus_depreciation] | 2 | False | 0.03382 | 0.00498 | 1.00000 | True | 0.00000 | 0.48036 |
| working_capital | 1 | False | 0.03219 | 0.00487 | 1.00000 | True | 0.00000 | 0.46752 |
| grp[book_value_equity_to_total_liabilities+constant_capital_to_total_assets+equity_minus_share_capital_to_total_assets+equity_to_total_assets+short_term_liabilities_to_total_assets+total_assets_to_total_liabilities+total_liabilities_to_total_assets] | 7 | False | 0.02841 | 0.00429 | 1.00000 | True | 0.00000 | 0.46857 |
| grp[sales_minus_cost_of_products_sold_to_sales+total_costs_to_total_sales] | 2 | False | 0.02757 | 0.00473 | 1.00000 | True | 0.00000 | 0.41259 |
| grp[cash_sec_recv_minus_stl_to_opex_minus_depr_x365+constant_capital_to_fixed_assets+current_assets_minus_inventory_to_short_term_liabilities+current_assets_to_short_term_liabilities+current_assets_to_total_liabilities+equity_to_fixed_assets+working_capital_to_fixed_assets+working_capital_to_total_assets] | 8 | False | 0.02470 | 0.00421 | 1.00000 | True | 0.00000 | 0.41469 |
| grp[current_liabilities_x365_to_cost_of_products_sold+operating_expenses_to_short_term_liabilities+sales_to_short_term_liabilities+short_term_liabilities_x365_to_cost_of_products_sold+short_term_liabilities_x365_to_sales+total_liabilities_minus_cash_to_sales] | 6 | False | 0.02129 | 0.00368 | 1.00000 | True | 0.00000 | 0.40929 |
| log_total_assets | 1 | False | 0.01860 | 0.00304 | 1.00000 | True | 0.00000 | 0.43216 |
| ca_minus_inv_minus_stl_to_sales_minus_gp_minus_depr | 1 | False | 0.01730 | 0.00287 | 1.00000 | True | 0.00000 | 0.42602 |
| ca_minus_inv_minus_recv_to_stl | 1 | False | 0.01606 | 0.00300 | 1.00000 | True | 0.00000 | 0.37814 |
| retained_earnings_to_total_assets | 1 | False | 0.01554 | 0.00346 | 1.00000 | True | 0.00002 | 0.31761 |
| grp[receivables_x365_to_sales+sales_to_receivables] | 2 | False | 0.01142 | 0.00171 | 1.00000 | True | 0.00000 | 0.47182 |
| grp[current_assets_minus_inventories_to_long_term_liabilities+long_term_liabilities_to_equity] | 2 | False | 0.00873 | 0.00200 | 1.00000 | True | 0.00003 | 0.30776 |
| grp[inventory_x365_to_cost_of_products_sold+inventory_x365_to_sales+sales_to_inventory] | 3 | False | 0.00688 | 0.00149 | 1.00000 | True | 0.00001 | 0.32725 |
| receivables_plus_inventory_turnover_days | 1 | False | 0.00654 | 0.00101 | 1.00000 | True | 0.00000 | 0.45778 |
| sales_to_total_assets | 1 | False | 0.00544 | 0.00127 | 1.00000 | True | 0.00003 | 0.30187 |
| sales_to_fixed_assets | 1 | False | 0.00333 | 0.00068 | 0.99700 | True | 0.00000 | 0.34853 |
| operating_expenses_to_total_liabilities | 1 | False | 0.00280 | 0.00065 | 0.96800 | True | 0.00003 | 0.30251 |
| __shadow__0_receivables_x365_to_sales | 1 | True | 0.00174 | 0.00030 | 0.76950 | False | 0.00000 | 0.41174 |
| __shadow__9_long_term_liabilities_to_equity | 1 | True | 0.00145 | 0.00032 | 0.23050 | False | 0.00001 | 0.32238 |
| __shadow__6_total_liabilities_to_operating_profit_plus_depreciation_x_12_365 | 1 | True | 0.00041 | 0.00011 | 0.00000 | False | 0.00045 | 0.25361 |
| __shadow__7_total_liabilities_x365_to_gross_profit_plus_depreciation | 1 | True | 0.00010 | 0.00011 | 0.00000 | False | 0.38699 | 0.06131 |
| __shadow__2_inventory_x365_to_cost_of_products_sold | 1 | True | -0.00018 | 0.00015 | 0.00000 | False | 0.23187 | -0.08627 |
| __shadow__8_current_assets_minus_inventories_to_long_term_liabilities | 1 | True | -0.00061 | 0.00009 | 0.00000 | False | 0.00000 | -0.46817 |
| __shadow__1_sales_to_receivables | 1 | True | -0.00078 | 0.00010 | 0.00000 | False | 0.00000 | -0.57190 |
| __shadow__4_sales_to_inventory | 1 | True | -0.00098 | 0.00012 | 0.00000 | False | 0.00000 | -0.60175 |
| __shadow__3_inventory_x365_to_sales | 1 | True | -0.00263 | 0.00026 | 0.00000 | False | 0.00000 | -0.70392 |
| __shadow__5_receivables_plus_inventory_turnover_days | 1 | True | -0.00305 | 0.00053 | 0.00000 | False | 0.00000 | -0.40595 |

Shadow bar (95th pct of 10 shadow players): **0.00161**. Mode: sampled. Subsets evaluated: 5158. Model fits: 25785.

Implementation audit (efficiency property): sum of Shapley values 0.418224 vs v(full)-v(empty) 0.418224, abs diff 1.67e-16. Validates ARITHMETIC, not statistical accuracy: the efficiency property holds to machine precision in exact mode even if every v(S) is badly estimated. In sampled mode a large gap means too few permutations.

`diag_bh_p` and `diag_cohens_d` are DIAGNOSTICS ONLY and decide nothing (METHODOLOGY v3 s5.4). Check them against the shadow rows: a permuted noise column can show a highly "significant" BH p-value, which is precisely why v2's significance-based rule was withdrawn.

## Stage 3 - selection (parsimony curve + pre-declared tolerance)

| k | player added | cols | Gini | Gini 95% CI | KS | pAUC | Brier | rel. Gini loss | DeLong p vs full |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | grp[ebit_to_total_assets+ebitda_to_sales+ebitda_to_total_assets+gross_profit_in_3_years_to_total_assets+gross_profit_plus_depreciation_to_sales+gross_profit_plus_depreciation_to_total_liabilities+gross_profit_plus_extraord_items_plus_fin_expenses_to_total_assets+gross_profit_plus_interest_to_sales+gross_profit_plus_interest_to_total_assets+gross_profit_to_sales+gross_profit_to_short_term_liabilities+gross_profit_to_total_assets+net_profit_plus_depreciation_to_total_liabilities+net_profit_to_inventory+net_profit_to_sales+net_profit_to_total_assets+operating_profit_to_financial_expenses+operating_profit_to_sales+operating_profit_to_total_assets+sales_profit_to_sales+sales_profit_to_total_assets] | 21 | 0.7330 | [0.6932, 0.7736] | 0.6215 | 0.8413 | 0.0513 | 12.52% | 0.0000 |
| 2 | sales_n_to_sales_n_minus_1 | 22 | 0.8113 | [0.7763, 0.8450] | 0.6869 | 0.8862 | 0.0418 | 3.17% | 0.0222 |
| 3 | grp[total_liabilities_to_operating_profit_plus_depreciation_x_12_365+total_liabilities_x365_to_gross_profit_plus_depreciation] | 24 | 0.8120 | [0.7773, 0.8470] | 0.6926 | 0.8880 | 0.0417 | 3.09% | 0.0273 |
| 4 | working_capital | 25 | 0.8260 | [0.7966, 0.8568] | 0.6975 | 0.8927 | 0.0407 | 1.41% | 0.2554 |
| 5 | grp[book_value_equity_to_total_liabilities+constant_capital_to_total_assets+equity_minus_share_capital_to_total_assets+equity_to_total_assets+short_term_liabilities_to_total_assets+total_assets_to_total_liabilities+total_liabilities_to_total_assets] | 32 | 0.8357 | [0.8073, 0.8671] | 0.7047 | 0.8988 | 0.0402 | 0.26% | 0.8135 |
| 6 | grp[sales_minus_cost_of_products_sold_to_sales+total_costs_to_total_sales] | 34 | 0.8359 | [0.8074, 0.8673] | 0.7012 | 0.8986 | 0.0396 | 0.24% | 0.8229 |
| 7 | grp[cash_sec_recv_minus_stl_to_opex_minus_depr_x365+constant_capital_to_fixed_assets+current_assets_minus_inventory_to_short_term_liabilities+current_assets_to_short_term_liabilities+current_assets_to_total_liabilities+equity_to_fixed_assets+working_capital_to_fixed_assets+working_capital_to_total_assets] | 42 | 0.8345 | [0.8037, 0.8678] | 0.7083 | 0.8992 | 0.0388 | 0.40% | 0.6819 |
| 8 | grp[current_liabilities_x365_to_cost_of_products_sold+operating_expenses_to_short_term_liabilities+sales_to_short_term_liabilities+short_term_liabilities_x365_to_cost_of_products_sold+short_term_liabilities_x365_to_sales+total_liabilities_minus_cash_to_sales] | 48 | 0.8331 | [0.8010, 0.8645] | 0.7214 | 0.9001 | 0.0389 | 0.57% | 0.4182 |
| 9 | log_total_assets | 49 | 0.8311 | [0.7985, 0.8635] | 0.7175 | 0.9000 | 0.0387 | 0.81% | 0.2602 |
| 10 | ca_minus_inv_minus_stl_to_sales_minus_gp_minus_depr | 50 | 0.8315 | [0.7983, 0.8635] | 0.7182 | 0.9002 | 0.0387 | 0.76% | 0.2886 |
| 11 | ca_minus_inv_minus_recv_to_stl | 51 | 0.8315 | [0.7981, 0.8625] | 0.7152 | 0.9000 | 0.0386 | 0.76% | 0.2464 |
| 12 | retained_earnings_to_total_assets | 52 | 0.8303 | [0.7968, 0.8636] | 0.7183 | 0.9003 | 0.0387 | 0.90% | 0.0541 |
| 13 | grp[receivables_x365_to_sales+sales_to_receivables] | 54 | 0.8346 | [0.8032, 0.8667] | 0.7113 | 0.9015 | 0.0387 | 0.39% | 0.2301 |
| 14 | grp[current_assets_minus_inventories_to_long_term_liabilities+long_term_liabilities_to_equity] | 56 | 0.8346 | [0.8026, 0.8654] | 0.7130 | 0.9008 | 0.0390 | 0.39% | 0.1109 |
| 15 | grp[inventory_x365_to_cost_of_products_sold+inventory_x365_to_sales+sales_to_inventory] | 59 | 0.8344 | [0.8022, 0.8657] | 0.7123 | 0.9009 | 0.0390 | 0.41% | 0.0813 |
| 16 | receivables_plus_inventory_turnover_days | 60 | 0.8374 | [0.8053, 0.8683] | 0.7118 | 0.9023 | 0.0390 | 0.06% | 0.7102 |
| 17 | sales_to_total_assets | 61 | 0.8366 | [0.8040, 0.8679] | 0.7121 | 0.9024 | 0.0390 | 0.15% | 0.2092 |
| 18 | sales_to_fixed_assets | 62 | 0.8381 | [0.8065, 0.8685] | 0.7109 | 0.9030 | 0.0388 | -0.02% | 0.6620 |
| 19 | operating_expenses_to_total_liabilities | 63 | 0.8379 | [0.8062, 0.8685] | 0.7143 | 0.9030 | 0.0389 | 0.00% | 1.0000 |

**Selected k = 4** (25 columns, Gini 0.8260, relative loss 1.41%, DeLong p = 0.2554). Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%.

### Selected feature set

`ebit_to_total_assets`, `ebitda_to_sales`, `ebitda_to_total_assets`, `gross_profit_in_3_years_to_total_assets`, `gross_profit_plus_depreciation_to_sales`, `gross_profit_plus_depreciation_to_total_liabilities`, `gross_profit_plus_extraord_items_plus_fin_expenses_to_total_assets`, `gross_profit_plus_interest_to_sales`, `gross_profit_plus_interest_to_total_assets`, `gross_profit_to_sales`, `gross_profit_to_short_term_liabilities`, `gross_profit_to_total_assets`, `net_profit_plus_depreciation_to_total_liabilities`, `net_profit_to_inventory`, `net_profit_to_sales`, `net_profit_to_total_assets`, `operating_profit_to_financial_expenses`, `operating_profit_to_sales`, `operating_profit_to_total_assets`, `sales_profit_to_sales`, `sales_profit_to_total_assets`, `sales_n_to_sales_n_minus_1`, `total_liabilities_to_operating_profit_plus_depreciation_x_12_365`, `total_liabilities_x365_to_gross_profit_plus_depreciation`, `working_capital`

## Stage 4 - calibration

| | Baseline (base rate) | Raw | Calibrated |
|---|---:|---:|---:|
| Brier | 0.0646 | 0.0342 | **0.0343** |
| ECE | - | 0.0128 | **0.0145** |

## Calibration backtest (deployed/calibrated model)

Held-out n=1182; per-grade **9/10** inside the Wilson 95% CI; ECE 0.0157->0.0169 (raw->calibrated); HL g=10  p=0.0720.

| Grade | n | realised | expected | CI low | CI high | pass |
|---|--:|--:|--:|--:|--:|:--:|
| AAA | 237 | 0.0042 | 0.0011 | 0.0007 | 0.0235 | PASS |
| AA | 305 | 0.0131 | 0.0067 | 0.0051 | 0.0332 | PASS |
| A | 264 | 0.0152 | 0.0186 | 0.0059 | 0.0383 | PASS |
| BBB | 88 | 0.0227 | 0.0295 | 0.0063 | 0.0791 | PASS |
| BB | 43 | 0.0930 | 0.0469 | 0.0368 | 0.2160 | PASS |
| B | 54 | 0.1667 | 0.0828 | 0.0902 | 0.2874 | FAIL |
| CCC | 62 | 0.0645 | 0.1338 | 0.0254 | 0.1545 | PASS |
| CC | 48 | 0.1667 | 0.2275 | 0.0870 | 0.2958 | PASS |
| C | 32 | 0.3125 | 0.3811 | 0.1795 | 0.4857 | PASS |
| D | 49 | 0.7347 | 0.7553 | 0.5974 | 0.8379 | PASS |



---

## Addendum — decisions and findings beyond the stage report (2026-10-25)

### Headline numbers (all from this run)
| Item | Value |
|---|---|
| Stage 1 | 63 of 64 pass IV >= 0.02 with monotonic WOE; `total_sales_to_total_assets` dropped (Mann-Whitney p 0.138); dominant `sales_n_to_sales_n_minus_1`, IV 2.19 |
| Sufficiency (Stage 1, 63 columns) | EPV 6.4 (< 10); Riley minimum N 2,839 vs 5,910 available (2.08x); B1 100, B3 2,680, B4 2,839 |
| Stage 2 | 19 real players, all confirmed; shadow bar 0.00161; weakest player 1.74x the bar |
| Stage 3 | k = 4 players = 25 columns; Gini 0.8260 (CI 0.7966-0.8568) vs full 0.8379; DeLong p 0.2554; relative loss 1.41% |
| Selected model sufficiency | EPV 16.4; Riley N 1,132 (5.22x margin) |
| Stage 4 | AUC 0.913 (OOF, k=4); pipeline calibration step (XGBoost secondary learner, see correction) Brier 0.0343, ECE 0.0145; deployed-model backtest 9 of 10 grades pass (held-out n = 1,182); HL g=10 p 0.0720, g=5 p 0.0185 |

Parsimony curve: k=1 Gini 0.733 (DeLong p 2e-9), k=2 0.811 (p 0.022), k=3 0.812 (p 0.027), **k=4 0.826 (p 0.255, first not distinguishable)**. `working_capital` is the player that earns k=4. The model is parsimonious in decisions (4 players), not in columns (25).

### Unfavourable or open results (not hidden)
- **Grade B fails the Wilson backtest:** 9 defaults of 54 (16.7%) vs 8.3% expected, i.e. under-prediction. 9 of 10 grades pass. Not tested formally whether one failure in ten is within chance.
- **HL depends on grouping:** g=10 passes narrowly, g=5 rejects.
- **Isotonic calibration did not improve ECE on the deployed WOE-logistic model** (held-out ECE 0.0157 -> 0.0169). The Brier/ECE figures in the Stage-4 calibration table above belong to the XGBoost secondary learner (see correction at the end of this file), not to the primary model.
- **Blank `sales_n_to_sales_n_minus_1`:** 103 firms, 99 bankrupt (96.1%). Scored as-is, 101 of 103 land in grade D (median PD 99.9%). In-sample AUC (descriptive, not out-of-fold) is 0.9195 on all rows and 0.8949 on complete rows. Cause of the blanks unknown. Deployment control: mandatory field -> REFER. **The Stage 1-4 figures above include these firms.**
- **Other blank pattern:** `operating_profit_to_financial_expenses` is blank for 391 firms, 123 bankrupt (31.5%).
- **Completeness:** 2,879 of 5,910 firms (48.7%) have at least one blank among the 64 ratios; 844 among the 25 selected.
- **Attr24 look-ahead unresolved:** `gross_profit_in_3_years_to_total_assets` sits in the selected profitability group (P1, 21 columns). Dropping it moved the 5yr-ahead file's Gini 0.7832 -> 0.7766 (p 0.177); not tested on this file.
- **Period confound:** bankrupt firms sampled 2000-2012, operating firms 2007-2013 (source statement; not testable without dates).
- **Sentinel flag at G0:** `working_capital` = 97 is 1 bankrupt row (lift 14.4); absolute amount, judged plausible.
- **Acceptance pack:** PD floor binds (0.03%); the 99.9% cap never binds on complete-data firms (maximum 51.43%); a real bankrupt firm (R5) is rated AAA at 0.32%.
- **Secondary learner (XGBoost) not run** for this record; no secondary Gini is reported.
- **H1 (1yr_ahead better than 5yr_ahead) is NOT tested here.** The files hold different firms and sampling windows. For orientation only, POLISH1 (5yr_ahead) selected-model Gini was 0.783 (full 0.786) vs 0.826 (full 0.838) here, with different firms, event rates and candidate sets; no confidence-interval comparison has been made.

### Difference from older records
Stage 1's Riley C-statistic comes from ONE out-of-fold fit of all Stage-1 candidates (the confirmed-model C-statistic does not exist yet at that stage), unlike older one-shot records. Backtest uses the deployed-model (isotonic) method, not raw OOF, so G4 here is stricter than POLISH1's (which reported 10/10 on raw OOF); they are not directly comparable.

### Correction (2026-10-25): the Stage-4 calibration table is the XGBoost learner

The "Stage 4 - calibration" table above (Brier 0.0646 / 0.0342 / 0.0343, ECE 0.0128 / 0.0145, calibrated AUC 0.9321)
comes from `v3_pipeline._calibrate`, which trains an **XGBoost** model on the selected columns on a random
80/20 split and calibrates that. It therefore describes the secondary (robustness) learner, not the primary
WOE-logistic model whose Gini 0.8260, per-grade backtest and Hosmer-Lemeshow figures are reported elsewhere in this
record. In the chat presentation of G4 these figures were described as the model's own calibration; they were not.
The primary model's figures, from its out-of-fold predictions (scorecard, 95% bootstrap intervals): Brier skill
0.369 (0.325 to 0.410), ECE 0.0068 (0.0051 to 0.0129), calibration slope 0.954 (0.889 to 1.026); held-out
deployed-model ECE 0.0157 before and 0.0169 after isotonic. The sealed G4 decision (option B) rested on the AUC,
the per-grade backtest (grade B), and Hosmer-Lemeshow, all of which are primary-model figures, so the seal stands.

Recomputed with the corrected Stage-4 function (deployed WOE-logistic scorer, same 80/20 split, held-out n = 1,182;
not written back into the sealed state): Brier baseline / raw / isotonic 0.0646 / 0.0426 / 0.0427; ECE raw / isotonic
0.0217 / 0.0158; AUC after isotonic 0.8895. Isotonic therefore lowered ECE here and left Brier unchanged on this split;
the held-out figures in the per-grade backtest (0.0157 to 0.0169) use a different split of the out-of-fold scores.
Neither changes a gate outcome.
