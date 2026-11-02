# annual_panel (firm-year default data)

Current file: `annual_panel_clean.csv` (88,229 rows, 81 columns, 703 positive rows, 842 defaulting firms).
Built from `archive/annual_panel_raw.csv` in two steps:
1. `archive/annual_panel_target1y.csv`: added `target` (1 if the default date is 0-365 days after the FY end), dropped rows dated after the firm's default date (90,309 rows).
2. `annual_panel_clean.csv`: cleanup A1-A4 (dropped FY end after 2025-10-31, non-12-month periods, total assets <= 0; blanked codes -9/-8/-7 with `n_sentinel_blanked`; blanked impossible cells).

Do not use the firm-level default flag, `Default date`, or `Year basis` as features (they equal or reveal the outcome).
Open: meaning of "default", filing dates, Slice/Limits/Onset known, units.
Manifest: `ml_models/manifests/ANNUAL_PANEL_1Y.json`.
