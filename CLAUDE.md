# Credit Risk Calculator — Project Context (CLAUDE.md)

## Project Overview

**Project Name:** Banking Credit Risk Calculator  
**Purpose:** Basel III compliant credit risk platform with ML-powered PD, banking operations, supervisory regulatory reporting, RM decision support, financial reporting, and global reference data  
**Status:** Production-ready — GCP App Engine deployment in progress  
**Location:** `C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk`  
**Last Updated:** June 19, 2026  

> **⚠️ Axis Bank Simulation Clock:** For the `bank_Axis.db` experiment, the frozen simulation date is **2020-03-31**. All date-sensitive operations (NPA batch `as_of_date`, transaction generation, DPD, regulatory reports) must use this date — not the real system date. The user will say "the date has changed to X" to advance the clock.

**Six departments** from home page (`public/index.html`): Credit Risk (`/`), Banking Operations (`/operations/`), Regulatory Reporting (`/regulatory/`), Relationship Management (`/relationship/`), Financial Reporting (`/financials/`), Global Reference Data (`/reference/`).

**Global group hierarchy:** Group → Region → Country → Bank. Nine real-world banks (FY2025 annual reports):  
- **India:** BANK001 HDFC Bank, BANK002 ICICI Bank, BANK007 Bank of Baroda, BANK009 Punjab National Bank  
- **USA:** BANK003 JPMorgan Chase N.A. | **UK:** BANK004 Barclays Bank PLC | **Singapore:** BANK005 DBS Bank Ltd | **UAE:** BANK006 Emirates NBD PJSC | **Australia:** BANK008 Commonwealth Bank of Australia  

All 9 banks grounded in a real ledger: `advances_net == SUM(loans.outstanding)`, deposits == `SUM(accounts.balance)`, CAR/LCR/GNPA/P&L roll up from per-loan ledger. Foreign ledgers denominated in group reporting currency (₹).

---

## Architecture

### Stack
| Layer | Technology |
|-------|-----------|
| Web server | Flask 3.x + gunicorn |
| ML model | XGBoostClassifier — `pd_model.pkl` |
| Scheduler | APScheduler (BackgroundScheduler) |
| DB | SQLite `bank.db` (project root) — raw `sqlite3`, no ORM |
| Frontend | Vanilla HTML5/CSS3/JS |
| Deployment | GCP App Engine (Python 3.10) |
| Python | 3.10 — **`venv310` is the only venv** |

**Entry point:** `app.py` — all routes + APScheduler startup (scheduler call at bottom of file — after regulatory job functions are defined to avoid NameError).

---

## Project Structure

```
Banking_Credit_Risk/
├── app.py                    Flask server — all routes + scheduler
├── bank.db                   SQLite banking DB (gitignored, deployed to GCP)
├── run_flask.ps1             Local dev launcher
├── backend/
│   ├── calculations.py       AIRB + SA calculation classes
│   ├── assessment_engine.py  Full borrower findings (PD→rating→LGD→RWA→EL→pricing→reco)
│   ├── rating_masterscale.py PD → AAA…D grade
│   ├── pricing.py            Risk-based pricing
│   ├── explainability.py     Feature attribution, peer comparison, counterfactual recourse
│   ├── feature_meta.py       model_feature_frame() — aligns inputs to 27-feature pickle schema
│   ├── regulatory_engine.py  Basel III/RBI — client RWA, bank CAR/LCR/NSFR (pure functions)
│   ├── policy_engine.py      Deterministic credit policy rules (model-independent)
│   ├── decision_orchestrator.py  Machine Recommendation (M) composer
│   ├── rm_case_store.py      M/H/O + hash-chained provenance + outcomes (bank.db)
│   ├── report_generator.py   matplotlib→LaTeX→pdflatex PDF per case
│   ├── financial_reports.py  BS/P&L/Ratios/Pillar3 per bank + consolidated
│   └── financial_report_pdf.py  Combined annual-report PDF per scope
├── ml_models/
│   ├── pd_model.pkl          Active model
│   ├── pd_model_backup.pkl   Previous model
│   ├── pd_model_metadata.json
│   ├── hyperparameters.json
│   ├── run_history.json
│   ├── trainer.py            Training pipeline
│   └── synthetic_data.py     Synthetic data generator (6 Indian banks, 14,300 rows)
├── operations/scripts/       Standalone seeders — run manually against bank.db
│   ├── seed_global.py        countries + country_macro + foreign bank masters + customers
│   ├── seed_global_customers.py  Real ledger for foreign banks (~86 customers each)
│   ├── seed_global_transactions.py  18-month deposit-neutral transaction history
│   ├── seed_bank_balance_sheet.py  RBI Schedule III BS (FY2025 live-anchored)
│   ├── run_regulatory_batch.py     Daily reg batch → reg_* tables (also APScheduler 01:00)
│   ├── reconcile_ledger.py   Recomputes balance_after; syncs accounts.balance
│   ├── add_new_customers.py  New customers + bank_loan_metrics training row
│   ├── seed_real_bank.py     9-step full-ledger seeder from profile JSON
│   ├── normalize_bank.py     Rebalances capital/borrowings; reruns reg batch
│   └── _delete_bank.py       Wipes per-bank data (preserves master row)
├── public/                   Flask static files
│   ├── index.html, borrower-info.html, admin.html
│   ├── operations/index.html, multibank.html
│   ├── regulatory/index.html
│   ├── relationship/index.html
│   ├── financials/index.html
│   └── reference/index.html
├── templates/ops_admin.html  Live bank.db schema viewer (/operations/db-admin)
├── testing/                  smoke_tests.py (Selenium, 6 cases), test_api.py, test_ml_integration.py
└── data/                     Runtime (gitignored, ephemeral on GCP — all self-initialised)
    ├── training/, archive/, synthetic/, runs/, reports/
    ├── case_reports/{case_id}/{version}/  RM PDF reports (versioned)
    └── financial_reports/{scope}/{version}/  Financial PDF reports (versioned)
```

---

## API Routes

### Consumer `/api/`
`POST /api/predict-pd-ml` · `POST /api/calculate-pd` · `POST /api/calculate-lgd` · `POST /api/calculate-correlation` · `POST /api/calculate-maturity-adjustment` · `POST /api/calculate-risk-weight-airb` · `POST /api/calculate-rwa-airb` · `POST /api/get-risk-weight-sa` · `POST /api/calculate-adjusted-exposure` · `POST /api/calculate-rwa-sa` · `POST /api/portfolio-summary` · `GET /api/model-info` · `POST /api/assess-borrower` (full findings, no persist) · `GET /api/masterscale` · `POST /api/generate-report` (persists to `data/reports/`) · `GET /api/get-report/<id>` · `GET /api/customer-lookup/<cid>` · `GET /api/health` · `GET /api/info`

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

---

## ML Model

- **Type:** XGBoostClassifier — target `default_flag` (binary, RBI 90-day NPA rule)
- **Features:** 27 (`de_ratio`, `interest_coverage`, `profitability`, `liquidity_ratio` + 16 borrower/bureau attrs + 4 country macro + 3 trend). `feature_meta.model_feature_frame()` aligns any input dict to the pickle schema (fills missing features with neutral defaults).
- **Current metrics (Phase 5.19 — 1,166 real-bank rows):** R²=0.70, AUC-ROC=0.955, Accuracy=80.2%, Recall=95.6%
- **Training pipeline** (`trainer.py`): scan `data/training/` → validate → train 80/20 → evaluate → generate 6 charts → promote if R² improves >0.01 → archive → log to `run_history.json`
- **Synthetic data** (`synthetic_data.py`): 14,300 rows, 6 Indian banks. Run manually — no admin button.

---

## Key Module Notes

### Borrower Assessment
`backend/assessment_engine.py` produces one findings object: PD band → rating grade → reason codes → LGD → RWA → EL → pricing → Five C's → policy knockouts → Approve/Refer/Decline.  
Two views: `report-underwriter.html` (internal) and `report-applicant.html` (adverse-action). `?case=<id>` mode on underwriter loads from RM case `machine_json` (no disk fetch needed).

### Banking Operations (`bank.db`)
Schema: `banks`, `bank_balance_sheet`, `branches`, `customers`, `accounts`, `loans`, `transactions`, `credit_risk_metrics`, `regulatory_bodies/requirements/compliance`, `reg_capital_reports`, `reg_liquidity_reports`, `reg_client_exposures`, `rm_cases`, `rm_case_events`, `rm_outcomes`, `bank_profit_loss`, `countries`, `country_macro`.  
**`bank.db` is gitignored but deployed to GCP** (not in `.gcloudignore`). All reg/RM/financial tables self-create on first use.

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
Tables: `countries` (ISO-3, region, Basel minimums, sovereign rating) + `country_macro` (GDP, CPI, policy rate, FX — 2 periods per country). 7 countries seeded. All foreign bank figures in group ₹. `seed_global.py` is idempotent; called by `_ensure_global` before BS/P&L seed.

---

## Important Technical Notes

### APScheduler
- Starts only in main Werkzeug process: `if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'`
- Scheduler call is at **bottom of `app.py`** (after regulatory job functions defined — avoids NameError)
- Two jobs: `pd_training` (configurable) and `regulatory_batch` (daily 01:00)
- Day-of-week uses 3-letter abbreviations: `"sun"` not `"sunday"` — normalised via `_DOW_MAP`

### PD Method
Always ML (`/api/predict-pd-ml`) with rule-based fallback. No toggle. `api-integration.js` handles the call.

### GCP / Data Directory
- `data/` is ephemeral on App Engine — all subdirs self-initialise via `os.makedirs(..., exist_ok=True)`
- `bank.db` is the one file deliberately NOT in `.gcloudignore`
- `app.yaml`: `runtime: python310`, `entrypoint: gunicorn -b :$PORT app:app`
- Smoke tests (Selenium/Chrome) will error on GCP — run locally before deploying

### Admin
URL: `http://localhost:5000/admin.html` · Password: `1234` (sessionStorage) · Unlisted (not linked from home)

---

## Recent Phases (current state)

| Phase | Description | Date |
|-------|-------------|------|
| 5.17 | Grounded foreign banks with real ledger (~86 customers each, 18-month txn history, deposit-neutral) | June 17 |
| 5.18 | Real-world bank network (9 banks, FY2025 annual reports); `seed_real_bank.py`, `normalize_bank.py`, `bank_profiles/*.json`; NPA dashboard metrics | June 19 |
| 5.19 | P&L seeded for all 9 banks; PD model retrained on 1,166 real-bank rows (all 9 banks, model promoted) | June 19 |

**Roadmap:** Phase 6 = GCP deployment (in progress) · Phase 7 = Operational Risk TSA/AMA · Phase 8 = Market Risk VaR

---

## Local Development

```powershell
.\run_flask.ps1          # creates venv310 if missing, installs deps, runs app.py
# OR
.\venv310\Scripts\python.exe app.py

# http://127.0.0.1:5000  |  /admin.html (pw: 1234)  |  /operations/  |  /regulatory/  |  /relationship/  |  /financials/  |  /reference/
```

**Required:** Python 3.10, Chrome (smoke tests). `venv310` is the only venv.
