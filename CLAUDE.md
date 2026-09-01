# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Project Name:** Banking Credit Risk Calculator
**Purpose:** Basel III compliant credit risk platform with ML-powered PD, banking operations, supervisory regulatory reporting, RM decision support, financial reporting, and global reference data
**Status:** Deployed on Cloud Run (migrated from GCP App Engine)

> **📅 Reporting Clock:** Balance sheet, P&L, and regulatory reports are anchored to the most recently closed fiscal year, tracked in `simulation_clock.json` (`sim_date`/`sim_period` = current, `prior_date`/`prior_period` = prior-year comparison column). To roll forward to a new fiscal year-end, update `simulation_clock.json` and rerun `operations/scripts/seed_bank_balance_sheet.py`, `seed_bank_profit_loss.py`, and the regulatory batch (`POST /regulatory/api/run-batch`), then restart Flask — the clock loads once at import time.

**Eight departments** from home page (`public/index.html`): Credit Risk (`/`), Banking Operations (`/operations/`), Regulatory Reporting (`/regulatory/`), Relationship Management (`/relationship/`), Financial Reporting (`/financials/`), Global Reference Data (`/reference/`), Performance Analytics (`/analytics/`), Model Governance & AI Risk (`/governance/`).

**Model Governance module** (`/governance/`): SR 11-7 / Basel / EU AI Act controls over the ML pipeline — `backend/governance_store.py` (hash-chained `gov_audit_events` model-lifecycle audit log, `gov_alerts` with mandatory ≥20-char acknowledgements, DB-backed per-model wiki with version history, six-pillar validation sign-offs, auto-derived regulatory mapping) + `backend/drift_monitor.py` (PSI vs training-time baselines, AUC stability, fairness gap; thresholds in `hyperparameters.json["governance"]`: PSI>0.25, AUC drop>5%, gap>0.05; daily APScheduler job 03:00 + `POST /governance/api/run-monitor`). `trainer.run_training()` has a challenger-vs-champion **promotion gate** (blocks activation when challenger AUC < champion − tolerance; `status_detail: trained_not_promoted`; override via `trainer.force_promote()` / `POST /governance/api/force-promote`, admin-authed, rationale required) and snapshots PSI baselines on every promotion.

**Global group hierarchy:** Group → Region → Country → Bank. 16 banks in `bank.db` — 9 real-world banks grounded in FY2025 annual reports plus 7 reference/onboarded portfolios from public credit datasets:
- **Real-world (India):** BANK001 HDFC Bank, BANK002 ICICI Bank, BANK007 Bank of Baroda, BANK009 Punjab National Bank
- **Real-world (int'l):** BANK003 JPMorgan Chase N.A. (USA) · BANK004 Barclays Bank PLC (UK) · BANK005 DBS Bank Ltd (Singapore) · BANK006 Emirates NBD PJSC (UAE) · BANK008 Commonwealth Bank of Australia
- **Reference/onboarded portfolios:** BANK010 Banco Bradesco (Brazil), BANK011 Taiwan Composite Bank, BANK012 German Composite Bank, BANK013 US HELOC Reference Bank, BANK014 US Personal Loan Reference Bank, BANK015 US Home Equity Reference Bank, BANK016 UK Consumer Credit Reference Bank

All banks grounded in a real ledger: `advances_net == SUM(loans.outstanding)`, deposits == `SUM(accounts.balance)`, CAR/LCR/GNPA/P&L roll up from per-loan ledger. Foreign ledgers denominated in group reporting currency (₹). New portfolios are added via `operations/scripts/onboard_*.py` scripts (one per source dataset, e.g. `onboard_german.py`, `onboard_heloc.py`, `onboard_hmeq.py`, `onboard_taiwan.py`, `onboard_th02.py`, `onboard_banco_bradesco.py`, `onboard_credit_risk.py`) each paired with a mapping file under `operations/scripts/onboarding_maps/`.

---

## Commands

```powershell
# Run the app locally
.\run_flask.ps1                                # creates venv310 if missing, installs deps, runs app.py
.\venv310\Scripts\python.exe app.py            # if venv already set up

# Run a single test (plain scripts, not pytest — each hits a live Flask server at 127.0.0.1:5000 unless noted)
.\venv310\Scripts\python.exe testing\test_api.py
.\venv310\Scripts\python.exe testing\test_ml_integration.py
.\venv310\Scripts\python.exe testing\test_shap.py
.\venv310\Scripts\python.exe testing\smoke_tests.py       # Selenium/Chrome — local only, will error on Cloud Run

# Retrain a model (per exposure-class or per-bank; see ML Model section)
.\venv310\Scripts\python.exe ml_models\trainer.py

# Seed / reconcile bank.db (run manually, in this rough order for a fresh bank)
.\venv310\Scripts\python.exe operations\scripts\seed_global.py
.\venv310\Scripts\python.exe operations\scripts\seed_real_bank.py
.\venv310\Scripts\python.exe operations\scripts\seed_bank_balance_sheet.py
.\venv310\Scripts\python.exe operations\scripts\seed_bank_profit_loss.py
.\venv310\Scripts\python.exe operations\scripts\reconcile_ledger.py
.\venv310\Scripts\python.exe operations\scripts\run_regulatory_batch.py

# Deploy — see the gcp-deploy skill; do not hand-roll gcloud/docker commands
```

There is no lint/format/build step configured (no `.flake8`/`pyproject.toml`/`package.json`) — vanilla JS frontend has no bundler. `requirements.txt` is the dependency source of truth; `google-cloud-storage` and `certifi` are installed separately in the Dockerfile (not in `requirements.txt`).

**Required:** Python 3.10, Chrome (Selenium smoke tests). `venv310` is the only venv.

---

## Architecture

### Stack
| Layer | Technology |
|-------|-----------|
| Web server | Flask 3.x + gunicorn, single monolithic `app.py` (no blueprints) |
| ML model | XGBoost/RandomForest/etc., **one model per exposure-class × bank combination** — see ML Model |
| Scheduler | APScheduler (BackgroundScheduler) |
| DB | SQLite `bank.db` (project root) — raw `sqlite3`, no ORM (SQLAlchemy config in `config.py` is unused legacy) |
| Frontend | Vanilla HTML5/CSS3/JS, no build step |
| Deployment | Docker + gunicorn → Cloud Run (see `Dockerfile`, `.env.production`); GCS for persistent `bank.db`/models/reports on the read-only Cloud Run filesystem |
| Python | 3.10 — **`venv310` is the only venv** |

**Entry point:** `app.py` — all routes + APScheduler startup (scheduler call at bottom of file — after regulatory job functions are defined to avoid NameError). Near the top, `app.py` detects a read-only filesystem (Cloud Run/App Engine) and, if so, spins up `backend/cloud_storage.CloudStorageManager` to asynchronously download `bank.db` and ML models from GCS into `/tmp` before serving requests.

### Cloud Storage / Deployment (Cloud Run)
- `.env.production`: `READONLY_FS=true`, `DATABASE_URL=sqlite:////tmp/bank.db`, `MODELS_DIR=/tmp/ml_models`, `DATA_DIR=/tmp/data` — buckets `GCS_DATA_BUCKET`/`GCS_MODELS_BUCKET`/`GCS_REPORTS_BUCKET`/`GCS_AUDIT_BUCKET`.
- `backend/cloud_storage.py` handles download-on-startup (db + models) and upload-on-write (reports/audit) so state survives container restarts despite the read-only/ephemeral Cloud Run filesystem.
- Local dev never sets `READONLY_FS`, so it always reads/writes `bank.db` and `ml_models/` directly on disk — GCS code paths are skipped entirely.
- To actually deploy, use the `gcp-deploy` skill rather than improvising `gcloud`/`docker` commands — it re-derives current project/service state instead of assuming stale values.

---

## Project Structure

```
├── app.py                       Flask server — all routes + scheduler + GCS bootstrap
├── config.py                    Legacy Flask/SQLAlchemy config classes — not wired into app.py's raw-sqlite3 usage
├── bank.db                      SQLite banking DB (gitignored; downloaded from GCS on Cloud Run)
├── Dockerfile, .dockerignore, .env.production   Cloud Run deployment
├── run_flask.ps1                Local dev launcher
├── backend/
│   ├── calculations.py          AIRB + SA calculation classes
│   ├── assessment_engine.py     Full borrower findings (PD→rating→LGD→RWA→EL→pricing→reco)
│   ├── rating_masterscale.py    PD → AAA…D grade
│   ├── pricing.py               Risk-based pricing
│   ├── explainability.py        Feature attribution, peer comparison, counterfactual recourse
│   ├── shap_explainer.py        SHAP-based explanations (`/api/assess-borrower-with-shap`)
│   ├── feature_meta.py          model_feature_frame() — aligns inputs to the pickle schema
│   ├── feature_schema.py        Feature schema definitions backing feature_meta
│   ├── bank_field_meta.py       Per-bank/exposure-class field metadata for dynamic forms
│   ├── model_registry.py        Resolves exposure-class × bank → active model file (active_model.json)
│   ├── prediction_store.py      Persists PD predictions
│   ├── regulatory_engine.py     Basel III/RBI — client RWA, bank CAR/LCR/NSFR (pure functions)
│   ├── policy_engine.py         Deterministic credit policy rules (model-independent)
│   ├── decision_orchestrator.py Machine Recommendation (M) composer
│   ├── rm_case_store.py         M/H/O + hash-chained provenance + outcomes (bank.db)
│   ├── loan_booking.py          Loan origination/booking into the ledger
│   ├── npa_resolution.py        NPA workout/resolution workflows
│   ├── collateral_store.py      Collateral register
│   ├── fact_credit_risk.py      Credit-risk fact table assembly
│   ├── alm_engine.py            Asset-liability management (liquidity/duration) calcs
│   ├── governance_store.py      Model governance: audit log, alerts, wiki, sign-offs (see Model Governance above)
│   ├── drift_monitor.py         PSI/AUC/fairness drift monitoring
│   ├── report_generator.py      matplotlib→LaTeX→pdflatex PDF per case
│   ├── financial_reports.py     BS/P&L/Ratios/Pillar3 per bank + consolidated
│   ├── financial_report_pdf.py  Combined annual-report PDF per scope
│   └── cloud_storage.py         GCS download/upload for Cloud Run persistence
├── ml_models/
│   ├── active_model.json        Registry: {exposure_class[::bank_key]} → active model file + type
│   ├── pd_model_<CLASS>.pkl, pd_model_<CLASS>_<BANK>.pkl   Active models (per exposure-class, some per-bank)
│   ├── pd_model_backup_<CLASS>.pkl + _metadata_<CLASS>.json  Previous model per class
│   ├── models/                  Candidate model types (extra_trees, gradient_boosting, logistic_regression, random_forest, xgboost)
│   ├── hyperparameters.json     Includes `governance` drift thresholds
│   ├── run_history.json
│   ├── trainer.py               Training pipeline (per exposure-class/bank, promotion-gated)
│   ├── synthetic_data.py / synthetic_data_realistic.py   Synthetic data generators
│   └── transaction_level_models.py
├── operations/scripts/          Standalone seeders/onboarders — run manually against bank.db
│   ├── seed_global.py, seed_global_customers.py, seed_global_transactions.py   Foreign bank masters + ledger
│   ├── seed_bank_balance_sheet.py, seed_bank_profit_loss.py   RBI Schedule III BS/P&L (fiscal-clock anchored)
│   ├── seed_real_bank.py, normalize_bank.py, bank_profiles/*.json   9-step full-ledger seeder from bank profile JSON
│   ├── onboard_*.py + onboarding_maps/   Add a new bank/portfolio from an external credit dataset
│   ├── run_regulatory_batch.py  Daily reg batch → reg_* tables (also APScheduler 01:00)
│   ├── reconcile_ledger.py      Recomputes balance_after; syncs accounts.balance
│   ├── sync_bank_loan_metrics.py, backfill_*.py, add_*_columns.py   Feature-store maintenance/migrations
│   └── _delete_bank.py          Wipes per-bank data (preserves master row)
├── public/                      Flask static files — one subdir per department (operations/, regulatory/, relationship/, financials/, reference/, analytics/, governance/)
├── testing/                     Plain-script tests (no pytest) — see README.md and Commands above
└── data/                        Runtime (gitignored, ephemeral on Cloud Run — all self-initialised)
    ├── training/, archive/, synthetic/, runs/, reports/
    ├── case_reports/{case_id}/{version}/       RM PDF reports (versioned)
    └── financial_reports/{scope}/{version}/    Financial PDF reports (versioned)
```

---

## API Routes

### Consumer `/api/`
`POST /api/predict-pd-ml` · `POST /api/assess-borrower` (full findings, no persist) · `POST /api/assess-borrower-with-shap` · `POST /api/calculate-pd` · `POST /api/calculate-lgd` · `POST /api/calculate-correlation` · `POST /api/calculate-maturity-adjustment` · `POST /api/calculate-risk-weight-airb` · `POST /api/calculate-rwa-airb` · `POST /api/get-risk-weight-sa` · `POST /api/calculate-adjusted-exposure` · `POST /api/calculate-rwa-sa` · `POST /api/portfolio-summary` · `GET /api/model-info` · `GET /api/model-availability` · `GET /api/bank-model-schema` · `GET /api/exposure-classes` · `GET /api/masterscale` · `POST /api/generate-report` (persists to `data/reports/`) · `GET /api/get-report/<id>` · `GET /api/customer-lookup/<cid>` · `GET /api/customer-export` · `GET /api/customer-bulk-export` · `GET /api/customer-export-filters` · `GET /api/training-data-preview` · `GET /api/transaction-risk` · `GET /api/health` · `GET /api/info`

### Admin `/admin/api/` — Header `X-Admin-Password: 1234`
Status, data-sources, hyperparameters (GET/POST), schedule (GET/POST), runs, train, charts, rollback, smoke-tests, cases, override, audit-log.

### Operations `/operations/api/` — no auth
`GET /operations/api/banks` · `banks/<id>` · `banks/<id>/customers` · `banks/<id>/dashboard` · `customers` · `customers/<cid>` · `system-dashboard`
Pages: `/operations/` · `/operations/multibank` · `/operations/db-admin`

### Regulatory `/regulatory/api/` — no auth
`GET /regulatory/api/system` · `banks/<id>` · `banks/<id>/exposures` · `clients/<cid>` · `POST /regulatory/api/run-batch`
Page: `/regulatory/`

### Relationship `/relationship/api/` — no auth
`POST /relationship/api/cases` · `GET cases` · `GET cases/<id>` · `POST cases/<id>/action` (accept/reject — RM final authority) · `POST cases/<id>/report` · `GET cases/<id>/reports` · `GET reports/<id>/<version>/pdf` · `POST cases/<id>/outcome` · `GET insights`
Page: `/relationship/`

### Financials `/financials/api/` — no auth
`GET /financials/api/system` · `banks/<id>` · `region/<region>` · `country/<code>` · `consolidated` · `GET/POST reports/<scope>` · `GET reports/<scope>/<version>/pdf`
Page: `/financials/`

### Reference `/reference/api/` — no auth
`GET /reference/api/countries` · `countries/<code>`
Page: `/reference/`

### Analytics `/analytics/api/` and Governance `/governance/api/`
Both exist as full departments with page + API namespace (see Model Governance above for governance's routes: `run-monitor`, `force-promote`, plus audit/wiki/sign-off endpoints in `governance_store.py`). Grep `app.py` for `/analytics/api` and `/governance/api` to enumerate exact endpoints — they change frequently.

---

## ML Model

- **Registry, not a single model:** `ml_models/active_model.json` maps a key (`EXPOSURE_CLASS` or `EXPOSURE_CLASS::BANK_ID`, e.g. `"CORPORATE"`, `"CORPORATE::BANK001"`, `"GENERIC::BANK011"`) to the active model type/file. `backend/model_registry.py` resolves which model to use for a given assessment. Exposure classes in use: `CORPORATE`, `SME`, `RETAIL_MORTGAGES`, `RETAIL_OTHER`, `GENERIC` (per-bank fallback for onboarded reference portfolios that don't fit the four standard classes).
- Model files: `pd_model_<CLASS>.pkl` (and `pd_model_<CLASS>_<BANK>.pkl` for bank-specific overrides), each with a matching `pd_model_metadata_<CLASS>.json` and a `pd_model_backup_<CLASS>.pkl`/`_backup_metadata_` pair from the previous promotion.
- Model type varies per key — `xgboost` is typical but `random_forest` etc. also appear in `active_model.json`; `ml_models/models/` holds candidate model-type implementations (extra_trees, gradient_boosting, logistic_regression, random_forest, xgboost).
- `feature_meta.model_feature_frame()` aligns any input dict to the schema for the resolved model (fills missing features with neutral defaults); `feature_schema.py` defines the schema itself.
- **Training pipeline** (`ml_models/trainer.py`): trains per exposure-class/bank key → evaluates → **promotion gate** (blocks activation if challenger underperforms champion — see Model Governance) → archives old model as backup → snapshots drift-monitor PSI baseline → logs to `run_history.json`.
- `synthetic_data.py` / `synthetic_data_realistic.py`: synthetic training-data generators, run manually — no admin-panel button.

---

## Key Module Notes

### Borrower Assessment
`backend/assessment_engine.py` produces one findings object: PD band → rating grade → reason codes → LGD → RWA → EL → pricing → Five C's → policy knockouts → Approve/Refer/Decline. `shap_explainer.py` adds SHAP-based attribution via `/api/assess-borrower-with-shap`.
Two views: `report-underwriter.html` (internal) and `report-applicant.html` (adverse-action). `?case=<id>` mode on underwriter loads from RM case `machine_json` (no disk fetch needed).

### Banking Operations (`bank.db`)
Core schema: `banks`, `bank_balance_sheet`, `branches`, `customers`, `accounts`, `loans`, `transactions`, `credit_risk_metrics`, `regulatory_bodies/requirements/compliance`, `reg_capital_reports`, `reg_liquidity_reports`, `reg_client_exposures`, `rm_cases`, `rm_case_events`, `rm_outcomes`, `bank_profit_loss`, `countries`, `country_macro`, plus governance tables (`gov_audit_events`, `gov_alerts`, model wiki/sign-off tables) and a collateral register. All reg/RM/financial/governance tables self-create on first use.
On Cloud Run, `bank.db` lives at `/tmp/bank.db` (downloaded from GCS at startup, uploaded back on write) rather than the repo root.

### Regulatory Reporting
`backend/regulatory_engine.py` — pure functions. RBI minimums: CRAR ≥ 11.5%, Tier-1 ≥ 9.5%, CET1 ≥ 8%, LCR ≥ 100%, NSFR ≥ 100%, CRR ≥ 4.5%, SLR ≥ 18%. `bank_balance_sheet` feeds real capital base / HQLA; proxy fallback if absent. Daily batch via APScheduler 01:00 + `POST /regulatory/api/run-batch`.

### Relationship Management (M/H/O)
- **M (Machine):** `decision_orchestrator.py` — assessment findings + policy + OOD routing + sensitivity + DoA control.
- **H (Human):** RM has two actions only — **accept** or **reject** (≥20-char rationale); both finalise immediately. `four_eyes` retained in store but unused in UI.
- **O (Org decision):** final governed outcome.
Provenance: hash-chained `rm_case_events`. HITL learning: `rm_outcomes` → `/relationship/api/insights`.

**Single origination channel:** data collected on `borrower-info.html` only → "Refer to Relationship Manager →" button POSTs to `/relationship/api/cases`. RM "+ New Customer" navigates to calculator. Customer-ID lookup (`GET /api/customer-lookup/<cid>`) autofills form from existing bank records.

### Financial Reporting
`backend/financial_reports.py` assembles BS/P&L/Key Ratios/Pillar 3. `consolidate()` is generic — same fn produces bank/region/country/group roll-ups. `bank_profit_loss` and `bank_balance_sheet` self-seed on first API hit. Foreign banks use `FOREIGN_AVG_RISK_WEIGHT=0.75` for RWA when no loan rows present.

### Global Reference Data
Tables: `countries` (ISO-3, region, Basel minimums, sovereign rating) + `country_macro` (GDP, CPI, policy rate, FX — 2 periods per country). All foreign bank figures in group ₹. `seed_global.py` is idempotent; called by `_ensure_global` before BS/P&L seed.

---

## Important Technical Notes

### APScheduler
- Starts only in main Werkzeug process: `if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'`
- Scheduler call is at **bottom of `app.py`** (after regulatory/governance job functions defined — avoids NameError)
- Jobs: `pd_training` (configurable), `regulatory_batch` (daily 01:00), drift-monitor `run-monitor` (daily 03:00)
- Day-of-week uses 3-letter abbreviations: `"sun"` not `"sunday"` — normalised via `_DOW_MAP`

### PD Method
Always ML (`/api/predict-pd-ml`) with rule-based fallback. No toggle. `api-integration.js` handles the call; the exact model used depends on the borrower's resolved exposure class + bank (see ML Model / `model_registry.py`).

### GCP / Data Directory
- `data/` is ephemeral on Cloud Run — all subdirs self-initialise via `os.makedirs(..., exist_ok=True)`
- On Cloud Run (`READONLY_FS=true`), `bank.db` and `ml_models/` are downloaded from GCS into `/tmp` at startup by `backend/cloud_storage.py`; reports/audit logs are uploaded back to GCS
- Locally, `READONLY_FS` is unset — the app reads/writes the repo-root `bank.db`/`ml_models/` directly and GCS code paths never run
- Smoke tests (Selenium/Chrome) will error on Cloud Run — run locally before deploying

### Admin
URL: `http://localhost:5000/admin.html` · Password: `1234` (sessionStorage) · Unlisted (not linked from home)
