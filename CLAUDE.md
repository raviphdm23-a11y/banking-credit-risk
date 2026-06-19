# Credit Risk Calculator — Project Context (CLAUDE.md)

## Project Overview

**Project Name:** Banking Credit Risk Calculator  
**Purpose:** Basel III compliant credit risk calculation platform with ML-powered PD prediction, admin-driven model retraining, full portfolio management, banking operations, and supervisory regulatory reporting  
**Current Status:** Production-ready — GCP App Engine deployment in progress  
**Location:** `C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk`  
**User Email:** ravi_phdm23@iift.edu  
**Last Updated:** June 19, 2026  

**Five departments + a global reference layer** surfaced from the home page (`public/index.html`): **Credit Risk** (calculator + ML), **Banking Operations** (`/operations/`), **Regulatory Reporting** (`/regulatory/` — Basel III / RBI capital & liquidity returns), **Relationship Management & Decision Support** (`/relationship/` — front-line RM workflow with AI-assisted decisioning and the M/H/O provenance ledger), **Financial Reporting & Disclosures** (`/financials/` — per-bank & consolidated Balance Sheet, P&L, Key Ratios, Basel III Pillar 3, with combined LaTeX→PDF export), and **Global Reference Data** (`/reference/` — the country/jurisdiction layer above the banks: regulators, macro indicators, sovereign ratings, per-jurisdiction Basel minimums). Each has its own section below.

**Global group hierarchy (June 19, 2026):** the platform is now a **global group bank** organised as **Group → Region → Country → Bank**. Banks map to a country (`banks.country_code`); countries carry region/currency/regulator + macro variables (`countries` + `country_macro` tables). Nine real-world banks span 5 countries / 4 regions: **India** — BANK001 HDFC Bank, BANK002 ICICI Bank, BANK007 Bank of Baroda, BANK009 Punjab National Bank; **USA** — BANK003 JPMorgan Chase N.A.; **UK** — BANK004 Barclays Bank PLC; **Singapore** — BANK005 DBS Bank Ltd; **UAE** — BANK006 Emirates NBD PJSC; **Australia** — BANK008 Commonwealth Bank of Australia. **All nine banks are grounded in a real ledger** (Phase 5.18): each bank's balance sheet ratios, GNPA, NIM, ROA, CRAR, and deposit mix are derived from actual FY2025 annual reports; every bank has its own customers/loans/accounts/transactions so its `advances_net` == `SUM(loans.outstanding)` and deposits == `SUM(accounts.balance)`, and CAR/LCR/GNPA/P&L all roll up from the per-loan ledger. Foreign ledgers are denominated in the **group reporting currency (₹)**. Financial Reporting rolls up at every level (region & country aggregates reuse `financial_reports.consolidate()`). The `regulatory_engine` no-loan RWA fallback remains only as a safety net for genuinely empty banks.

---

## Current Architecture

### Stack
| Layer | Technology |
|-------|-----------|
| Web server | Flask 3.x with gunicorn |
| ML model | RandomForestRegressor (scikit-learn 1.7.2) via `pd_model.pkl` |
| Scheduler | APScheduler (BackgroundScheduler) — weekly Sunday 02:00 retraining |
| Banking operations data | SQLite (`bank.db`, project root) — read via raw `sqlite3`, not an ORM |
| Frontend | Vanilla HTML5/CSS3/JS — no framework |
| Storage | Browser localStorage (portfolio), local filesystem (model, run history, case reports, audit log) |
| Deployment target | GCP App Engine (Python 3.10) |
| Python version | 3.10 — **`venv310` is the only environment**; there is no other venv in this project |

### Entry Point
`app.py` — ~18 consumer API routes + ~15 admin API routes + ~10 operations routes + APScheduler startup

---

## Project Structure

```
Banking_Credit_Risk/
├── app.py                          Flask server — all routes + scheduler startup
├── config.py                       Flask environment configs (dev/prod)
├── requirements.txt                Python dependencies
├── app.yaml                        GCP App Engine deployment config
├── Procfile                        Heroku/Render deployment (gunicorn)
├── runtime.txt                     Python version pin for Render
├── run_flask.ps1                   Local dev launcher — creates/activates venv310, installs deps, runs app.py
├── bank.db                         SQLite banking-operations DB (gitignored, runtime data — see "Banking Operations Module")
├── .env                            Local environment vars (never committed)
├── .gitignore                      Git exclusions
├── .gcloudignore                   GCP deployment exclusions
├── CLAUDE.md                       This file
│
├── backend/
│   ├── __init__.py
│   ├── calculations.py             AIRB + SA calculation classes
│   ├── assessment_engine.py        Orchestrates one borrower's full findings object (PD→rating→LGD→RWA→EL→pricing→recommendation)
│   ├── rating_masterscale.py       PD → internal rating grade mapping (AAA…D scale)
│   ├── pricing.py                  Risk-based indicative pricing from EL + grade
│   ├── explainability.py           Feature attribution (reason codes), peer comparison, counterfactual recourse
│   ├── feature_meta.py             Feature ordering + metadata; `model_feature_frame()` aligns inputs to the model's expected schema (4 ratios → 21-feature model)
│   ├── regulatory_engine.py        Basel III / RBI returns — per-client RWA + provisioning, per-bank CAR/CET1/Tier1, LCR/NSFR/CRR/SLR (pure functions, no DB)
│   ├── policy_engine.py            Deterministic, versioned credit-policy rules — SEPARATE from the ML model (FOIR/LTV/income/age/KYC/sanctions/exposure)
│   ├── decision_orchestrator.py    Composes Machine Recommendation (M): model findings + policy + confidence routing/OOD + sensitivity + risk-adjusted reco + DoA control + tiered business explanation
│   ├── rm_case_store.py            RM case ledger — M/H/O constructs + hash-chained provenance events + outcomes; RM is final authority (accept/reject finalise; legacy four_eyes retained but unused) (sqlite in bank.db)
│   ├── report_generator.py         PDF credit decision report: matplotlib charts (PNG) → LaTeX → pdflatex → PDF; versioned per case under data/case_reports/<case_id>/<version>/ (regeneration keeps history)
│   ├── financial_reports.py        Pure assembly for the Financial Reporting dept — Balance Sheet, P&L, Key Ratios, Pillar 3 per bank + consolidated (all-banks aggregate); dicts in/out, reuses regulatory_engine
│   └── financial_report_pdf.py     Combined annual-report PDF (BS + P&L + Ratios + Pillar 3 + charts) per scope (bank / consolidated); LaTeX → pdflatex, versioned under data/financial_reports/<scope>/<version>/ (reuses report_generator helpers)
│
├── ml_models/
│   ├── __init__.py
│   ├── pd_model.pkl                Active RandomForest PD model
│   ├── pd_model_backup.pkl         Previous model (created on first successful promotion; absent until then)
│   ├── pd_model_metadata.json      Model version, metrics, features
│   ├── hyperparameters.json        RF hyperparams + training + schedule config
│   ├── run_history.json            All training run records
│   ├── trainer.py                  Full training pipeline (scan→validate→train→promote→archive); also reads bank_loan_metrics from bank.db
│   └── synthetic_data.py           Synthetic data generator — 6 Indian banks (INR)
│
├── operations/
│   └── scripts/                    Standalone seeding/sync scripts run manually against bank.db (not wired into app.py)
│       ├── generate_customers.py   Generates 48 demo customers/accounts/loans across BANK001 (HDFC) / BANK002 (ICICI)
│       ├── create_priya_sharma.py  One-off script that seeded a specific demo customer + transaction history
│       ├── load_bank_csv.py        Bulk-loads an external CSV into the bank_loan_metrics table
│       ├── sync_bank_loan_metrics.py  Derives bank_loan_metrics from customers/loans/transactions/credit_risk_metrics
│       ├── backfill_transactions.py   Adds realistic income/expense transactions for the 48 bulk-generated customers (who only had EMI debits)
│       ├── add_new_customers.py    Adds new customers with full records + a 21-feature bank_loan_metrics training row each (then retrain) — `python operations/scripts/add_new_customers.py [N]`
│       ├── reconcile_ledger.py     Rebalances monthly cash flow + recomputes balance_after for every txn so accounts.balance == latest balance_after (fixes balance-sync)
│       ├── run_regulatory_batch.py Daily Regulatory Reporting batch — computes & stores Basel III/RBI returns into the reg_* tables; reads bank_balance_sheet for real capital/liquidity (self-seeds it if empty); also wired into APScheduler (daily 01:00) and POST /regulatory/api/run-batch
│       ├── seed_bank_balance_sheet.py  Creates & populates bank_balance_sheet (RBI Schedule III, per bank per period); FY2025 anchored to live advances/deposits so assets==liabilities and CRAR is realistic; idempotent (INSERT OR REPLACE). Skips zero-loan foreign banks (seeded by seed_global.py)
│       ├── seed_global.py          Global group layer — creates/populates `countries` + `country_macro` (region/currency/regulator + macro vars), adds `banks.country_code`, seeds 4 foreign group bank master rows (USA/UK/SGP/UAE) then calls seed_global_customers to ground them; idempotent
│       ├── seed_global_customers.py  Grounds the 4 foreign banks in a REAL ledger — per-bank branches/customers/kyc/accounts(+opening deposit txn)/loans/credit_risk_metrics/bank_loan_metrics (country-appropriate name/city pools, group ₹, ~86 customers); idempotent (skips a bank that already has customers)
│       ├── seed_global_transactions.py  Adds an 18-month monthly transaction history (income/EMI/Bill/UPI, NPA misses) for the foreign customers; **deposit-neutral** — writes balance_after itself so each account ends at its grounded balance (no balance-sheet re-seed needed); idempotent
│       └── update_bank_data.py     Hourly automation: adds a couple of new customers/transactions (intended for Task Scheduler/cron, not currently scheduled)
│
├── public/                         Flask serves everything here as static
│   ├── index.html                  Landing / home page (links to all pages)
│   ├── borrower-info.html          Main calculator SPA (AIRB + SA + portfolio)
│   ├── admin.html                  Admin dashboard (password: 1234)
│   ├── api-integration.js          Flask API bridge with local fallback
│   ├── standardized-approach.js    SA risk weight tables + calculation engine
│   ├── formula-reference.html      AIRB methodology docs + worked examples
│   ├── formula-references.html     Unified methodology hub (all 5 phases)
│   ├── standardized-approach-reference.html  SA methodology docs
│   ├── data-dictionary.html        Variable reference + Five C's mapping
│   ├── report-underwriter.html     Internal case report view (decision + audit trail, Five C's evidence)
│   ├── report-applicant.html       External adverse-action / recourse letter view of the same findings
│   ├── report-charts.js            Client-side charting for the report views (no matplotlib in the request path)
│   ├── operations/
│   │   ├── index.html              Single-bank customer/account/loan/transaction explorer (served at /operations/) — fetches live data from /operations/api/* (no longer a hardcoded mock)
│   │   └── multibank.html          Cross-bank dashboard (served at /operations/multibank)
│   ├── regulatory/
│   │   └── index.html              Regulatory Reporting dashboard (served at /regulatory/) — system / per-bank / per-client Basel III & RBI returns
│   ├── relationship/
│   │   └── index.html              RM decision-support cockpit (served at /relationship/) — intake, recommendation, provenance, four-eyes, insights
│   ├── financials/
│   │   └── index.html              Financial Reporting dashboard (served at /financials/) — Group → Region → Country → Bank tree, BS/P&L/Ratios/Pillar 3 + PDF
│   └── reference/
│       └── index.html              Global Reference dashboard (served at /reference/) — country/jurisdiction register + macro indicators
│
├── templates/
│   └── ops_admin.html              Jinja2-rendered live bank.db schema viewer (served at /operations/db-admin)
│
├── testing/
│   ├── README.md
│   ├── smoke_tests.py              Headless Selenium — 6 consumer-side test cases
│   │                               (called by Flask admin endpoint at runtime)
│   ├── test_admin_smoke_trigger.py Selenium test for admin smoke test UI flow
│   ├── test_api.py                 Flask API endpoint tests
│   ├── test_ml_integration.py      ML model integration tests
│   └── [superseded scripts]        Kept locally, gitignored
│
└── data/                           Runtime data (gitignored, ephemeral on GCP)
    ├── training/                   Drop CSV files here to trigger retraining
    ├── archive/                    Processed training files moved here after run
    ├── synthetic/                  Generated synthetic bank CSVs
    ├── runs/{run_id}/              Per-run chart .b64 files + metrics
    ├── reports/{report_id}.json    Persisted assessment findings (disk-backed cache for /api/get-report and admin case list)
    ├── case_reports/{case_id}/     RM case PDF reports — manifest.json (version index) + {version}/charts/*.png + report.tex + report.pdf (newest = latest)
    ├── financial_reports/{scope}/  Combined financial-report PDFs per bank / CONSOLIDATED — manifest.json + {version}/charts/*.png + report.tex + report.pdf
    └── audit_log.json              Append-only log of REPORT_GENERATED / REPORT_VIEWED / OVERRIDE_RECORDED events
```

**Note:** `instance/credit_risk.db`, `backend/banking_models.py`, `case_report_builder.py`, and `operations/scripts/excel_loader.py` were removed June 16, 2026 — they were orphaned artifacts (unused SQLAlchemy scaffolding, a superseded report-builder prototype, and a script importing a `models` module that never existed in this repo). `bank.db` was also moved into this project root from a sibling `Creating a Bank` folder — nothing in this repo references that external folder anymore.

---

## API Routes

### Consumer API (`/api/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/predict-pd-ml` | ML PD prediction (RandomForest) |
| POST | `/api/calculate-pd` | Rule-based PD calculation |
| POST | `/api/calculate-lgd` | LGD from seniority + collateral |
| POST | `/api/calculate-correlation` | AIRB correlation factor R |
| POST | `/api/calculate-maturity-adjustment` | AIRB maturity adjustment |
| POST | `/api/calculate-risk-weight-airb` | AIRB risk weight |
| POST | `/api/calculate-rwa-airb` | AIRB RWA |
| POST | `/api/get-risk-weight-sa` | SA risk weight table lookup |
| POST | `/api/calculate-adjusted-exposure` | SA collateral-adjusted exposure |
| POST | `/api/calculate-rwa-sa` | SA RWA |
| POST | `/api/portfolio-summary` | Portfolio aggregate stats |
| GET  | `/api/model-info` | Active model metadata |
| POST | `/api/assess-borrower` | Full assessment findings (PD+band, rating grade, reason codes, LGD, RWA, EL, pricing, Five C's, Approve/Refer/Decline) — does not persist |
| GET  | `/api/masterscale` | Internal rating grade table (AAA…D) |
| POST | `/api/generate-report` | Runs the same assessment, persists findings to `data/reports/`, returns an executive summary + `report_id` |
| GET  | `/api/get-report/<report_id>` | Fetch full persisted findings (memory cache, falls back to disk) |
| GET  | `/api/health` | Health check |
| GET  | `/api/info` | Application info |

### Admin API (`/admin/api/`) — Header: `X-Admin-Password: 1234`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/admin/api/status` | Model status + schedule + last run |
| GET  | `/admin/api/data-sources` | Files in training folder |
| GET/POST | `/admin/api/hyperparameters` | Read/update hyperparameters.json |
| GET/POST | `/admin/api/schedule` | Read/update training schedule |
| GET  | `/admin/api/runs` | Full run history |
| GET  | `/admin/api/runs/<run_id>` | Single run detail |
| POST | `/admin/api/train` | Trigger manual training run |
| GET  | `/admin/api/charts/<run_id>` | List charts for a run |
| GET  | `/admin/api/charts/<run_id>/<name>` | Fetch base64 chart PNG |
| POST | `/admin/api/rollback` | Rollback to backup model |
| POST | `/admin/api/smoke-tests` | Start consumer UI smoke test run |
| GET  | `/admin/api/smoke-tests/status` | Poll smoke test results |
| GET  | `/admin/api/cases` | List all persisted case reports, newest first |
| POST | `/admin/api/cases/<report_id>/override` | Record a credit officer's Approve/Refer/Decline override + justification (min 20 chars) |
| GET  | `/admin/api/audit-log` | Read `data/audit_log.json` |

### Operations API (`/operations/api/`) — banking ops data, reads `bank.db` directly via `sqlite3`, no auth header
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/operations/api/banks` | List all banks |
| GET  | `/operations/api/banks/<bank_id>` | Single bank detail |
| GET  | `/operations/api/banks/<bank_id>/customers` | Customers at one bank |
| GET  | `/operations/api/banks/<bank_id>/dashboard` | Per-bank aggregate dashboard |
| GET  | `/operations/api/customers` | List all customers + loan health across all banks |
| GET  | `/operations/api/customers/<cid>` | Full customer profile: accounts, loans, transactions, risk metrics |
| GET  | `/operations/api/system-dashboard` | Cross-bank system-wide dashboard |

### Operations pages (no auth — URLs are unlisted, same convention as admin)
| Route | Renders |
|-------|---------|
| `/operations/` | `public/operations/index.html` — single-bank customer/account/loan/transaction explorer |
| `/operations/multibank` | `public/operations/multibank.html` — cross-bank dashboard |
| `/operations/db-admin` | `templates/ops_admin.html` — live `bank.db` schema + ER diagram viewer |

### Regulatory Reporting API (`/regulatory/api/`) — reads the `reg_*` tables in `bank.db`, no auth header
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/regulatory/api/system` | System-wide (all-banks) snapshot: consolidated CAR/CET1/LCR/NSFR, total RWA/capital/deposits, per-bank scorecard, breach/watch counts |
| GET  | `/regulatory/api/banks/<bank_id>` | Full per-bank return: capital adequacy, liquidity, RBI compliance register, exposure mix, ratio trend |
| GET  | `/regulatory/api/banks/<bank_id>/exposures` | Client-level exposure register for one bank (latest report date) |
| GET  | `/regulatory/api/clients/<cid>` | Client-level regulatory report: per-loan EAD/PD/LGD/RW/RWA/capital/EL/provision + totals |
| POST | `/regulatory/api/run-batch` | Manually trigger the regulatory batch (also runs daily via APScheduler) |

| Route | Renders |
|-------|---------|
| `/regulatory/` | `public/regulatory/index.html` — Regulatory Reporting dashboard (system / bank / client views) |

### Relationship Mgmt & Decision Support API (`/relationship/api/`) — RM case ledger in `bank.db`, no auth header
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/relationship/api/cases` | Create a case from onboarding inputs → runs the orchestrator, stores Machine Recommendation (M), returns recommendation + required control |
| GET  | `/relationship/api/cases` | Queue list (filter by `?state=` / `?control=`) |
| GET  | `/relationship/api/cases/<id>` | Full case: M, policy, confidence, sensitivity, business explanation, H actions, O, hash-chained provenance, outcome |
| POST | `/relationship/api/cases/<id>/action` | RM action: **accept** or **reject** only — the RM is the final authority, each action finalises the case (reject requires a ≥20-char rationale). `four_eyes` remains in `rm_case_store` but is no longer surfaced. |
| POST | `/relationship/api/cases/<id>/approve` | (Legacy) four-eyes approve/return — retained but unused by the simplified two-option UI |
| POST | `/relationship/api/cases/<id>/report` | Generate a NEW PDF report version (LaTeX→PDF + matplotlib charts); regeneration keeps prior versions |
| GET  | `/relationship/api/cases/<id>/reports` | List all report versions for a case (newest first) + `latex_available` flag |
| GET  | `/relationship/api/reports/<id>/<version>/pdf` | Serve a report PDF inline, or as a download with `?dl=1` |
| POST | `/relationship/api/cases/<id>/outcome` | Record post-decision performance (learning loop) |
| GET  | `/relationship/api/insights` | HITL governance aggregates: override rate, model agreement, override hit-rate, pipeline by control/state |

| Route | Renders |
|-------|---------|
| `/relationship/` | `public/relationship/index.html` — RM decision-support cockpit |

### Financial Reporting & Disclosures API (`/financials/api/`) — assembles bank_balance_sheet + bank_profit_loss + regulatory engine, no auth header
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/financials/api/system` | Bank list with snapshot KPIs + a **Group → Region → Country → Bank `tree`** (rolled-up assets per node) + consolidated snapshot (self-seeds tables incl. the global layer) |
| GET  | `/financials/api/banks/<bank_id>` | Full bundle for one bank: balance_sheet, profit_loss, key_ratios, pillar3 (+ `country` block: code/region/currency/regulator) |
| GET  | `/financials/api/region/<region>` | Regional aggregate bundle (all banks in the region) — reuses `consolidate()` |
| GET  | `/financials/api/country/<code>` | Country aggregate bundle (all banks in the ISO-3 country) |
| GET  | `/financials/api/consolidated` | Consolidated (whole-group aggregate) bundle, ratios recomputed on aggregates |
| GET/POST | `/financials/api/reports/<scope>` | GET = list PDF versions; POST = generate a new combined PDF (`scope` = `<bank_id>` \| `consolidated` \| `REGION:<region>` \| `COUNTRY:<iso3>`; `:` is folder-sanitised to `_`) |
| GET  | `/financials/api/reports/<scope>/<version>/pdf` | Serve a report PDF inline, or download with `?dl=1` |

| Route | Renders |
|-------|---------|
| `/financials/` | `public/financials/index.html` — Financial Reporting dashboard (Group → Region → Country → Bank tree, all 4 reports + PDF at every level) |

### Global Reference Data API (`/reference/api/`) — `countries` + `country_macro` tables, no auth header
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/reference/api/countries` | All jurisdictions with latest macro snapshot, grouped by region, with group-bank counts (self-seeds the global layer) |
| GET  | `/reference/api/countries/<code>` | One jurisdiction: profile + regulatory minimums + full macro history + the group's banks there (with KPI cards) |

| Route | Renders |
|-------|---------|
| `/reference/` | `public/reference/index.html` — Global Reference dashboard (world overview + per-country macro drill) |

---

## ML Model

### Model: `ml_models/pd_model.pkl`
- **Type:** RandomForestRegressor (scikit-learn 1.7.2)
- **Target:** `pd_observed` — probability of default (decimal 0–1)
- **Features:** the **active `pd_model.pkl` was retrained on 21 features** (`model.feature_names_in_`): the 4 core ratios (`de_ratio`, `interest_coverage`, `profitability`, `liquidity_ratio`) **plus** borrower/bureau attributes (`age`, `annual_income`, `foir`, `cibil_score`, `num_late_payments_past_12m`, `previous_default_flag`, `existing_loans_count`, etc.). The 4 ratios remain the explainable drivers; `backend/feature_meta.py:model_feature_frame()` aligns any input dict to whatever schema the loaded pickle expects (filling unsupplied features from neutral defaults), so `assessment_engine`/`explainability` work regardless of model arity. **Note:** before June 16 2026 the engine only built the 4-feature vector, which silently broke against the 21-feature pickle — this shim fixed `/api/assess-borrower`, `/api/generate-report`, and the new decisioning flow.
- **Trained on:** 14,300 rows from 6 Indian banks (synthetic)
- **Current metrics:** R²=0.70, AUC-ROC=0.955, Accuracy=80.2%, Recall=95.6%
- **Currency:** INR (₹)

### Training Pipeline (`ml_models/trainer.py`)
1. Scan `data/training/` for CSV files
2. Validate schema (9 required columns)
3. Merge all files, split 80/20 train/test
4. Train RandomForest with hyperparameters from `hyperparameters.json`
5. Evaluate: R², RMSE, MAE, AUC-ROC, precision, recall, F1, confusion matrix
6. Generate 6 matplotlib charts saved as `.b64` files in `data/runs/{run_id}/`
7. Promote only if new R² > old R² + 0.01 (model promotion gate)
8. Archive processed CSVs to `data/archive/`
9. Log run to `ml_models/run_history.json`

### Synthetic Data (`ml_models/synthetic_data.py`)
6 Indian banks: SBI (3,000), HDFC (2,500), ICICI (2,800), AXIS (2,000), PNB (2,200), BOB (1,800)  
Total: 14,300 rows. Run manually as a script (`python ml_models/synthetic_data.py`) — drops the CSV straight into `data/training/`. There is no admin-panel button for this; the "Generate Indian Bank Synthetic Data" button referenced in earlier notes no longer exists in `admin.html`.

---

## Admin Module

**URL:** `http://localhost:5000/admin.html`  
**Password:** `1234` (stored in `sessionStorage`)  
**Note:** URL is intentionally unlisted — not linked from the public home page.

### Panels
| Panel | What it does |
|-------|-------------|
| Model Status | Active model KPIs, metadata, Train Now button |
| Data Sources | Files in training folder (synthetic data generation is a manual script, not a button here) |
| Hyperparameters | Edit RF params + training settings |
| Schedule | Configure weekly/daily/monthly retraining |
| Run History | All past runs with metrics + confusion matrix |
| Charts | 6 evaluation charts per run (ROC, feature importance, etc.) |
| Smoke Tests | Trigger 6 headless Selenium consumer-side tests |
| Cases | List persisted assessment reports (`/admin/api/cases`), record credit-officer overrides |
| Audit Log | View `data/audit_log.json` (`/admin/api/audit-log`) |

---

## Borrower Assessment & Case Reports

**Engine:** `backend/assessment_engine.py` — given the same inputs as the AIRB calculator, produces one immutable findings object covering:
PD (point + 80% band from RandomForest tree variance) → internal rating grade (`rating_masterscale.py`) → feature attribution / reason codes (`explainability.py`) → LGD → AIRB RWA (reuses `backend/calculations.py`) → Expected Loss (₹) → indicative risk-based pricing (`pricing.py`) → Five C's narrative → policy knockouts → Approve/Refer/Decline recommendation.

**Two lenses on one findings object** (per `REPORT_GENERATION_INTEGRATION_PLAN_v2.md`):
- `public/report-underwriter.html` — internal, full detail, decision + audit trail
- `public/report-applicant.html` — external, adverse-action notice + recourse (top actionable improvements)

**Persistence:** `POST /api/generate-report` writes findings to `data/reports/{report_id}.json` (disk-backed cache, survives Flask restart) and appends to `data/audit_log.json`. Credit officers can override the engine's decision via `POST /admin/api/cases/<report_id>/override` (requires ≥20-char justification); the override is layered onto the same JSON file, not a separate table.

**Note:** `case_report_builder.py`, a standalone v1 prototype this was based on (consumer financial-advisory tone, LaTeX/PDF output, imported a `tabular_preprocessing` module that was never part of this repo), was removed June 16, 2026 as dead code — the live implementation above fully superseded it.

---

## Banking Operations Module

A separate banking-operations demo, backed by **`bank.db`** (SQLite, project root) — distinct from the credit-risk calculator's own data. Schema: `banks` (static bank master details), `bank_balance_sheet` (per-bank per-period RBI Schedule III balance sheet — see below), `branches`, `customers`, `accounts`, `loans`, `transactions`, `credit_risk_metrics`, plus regulatory tables (`regulatory_bodies`, `regulatory_requirements`, `regulatory_compliance`).

- Two demo banks seeded: **BANK001 (HDFC)** and **BANK002 (ICICI)**.
- `app.py` reads `bank.db` with raw `sqlite3` via `_ops_conn()` — no ORM, read-mostly except for the `operations/scripts/` seeders.
- Frontend: `public/operations/index.html` (single-bank explorer) and `multibank.html` (cross-bank dashboard), served at `/operations/` and `/operations/multibank`.
- `/operations/db-admin` renders a live schema + ER-diagram viewer (`templates/ops_admin.html`) — useful for sanity-checking the DB after running a seed script.
- `operations/scripts/*.py` are run manually (not wired into `app.py` or any scheduler) to seed/refresh demo data — see the Project Structure section above for what each one does.
- **`bank.db` is gitignored** (runtime data) but **is deployed to GCP** (not in `.gcloudignore`) — without it, every `/operations/api/*` route would 500. It resets to whatever was last deployed on instance restart, same as the rest of `data/`.
- As of June 16, 2026, `bank.db` lives only in this project; it was previously a copy shared with a sibling `Creating a Bank` folder, which has been fully decoupled (original file there deleted).

### Ledger reconciliation (balance sync)
- `accounts.balance` used to be a frozen seed value unrelated to the transaction history, and `balance_after` was NULL on ~97% of transactions. `operations/scripts/reconcile_ledger.py` fixes this: it rebalances the bulk-backfilled discretionary spend so monthly cash flow is realistic, forward-computes a running `balance_after` for every transaction, and sets `accounts.balance` to the latest balance. After it runs, `accounts.balance == ` the last txn's `balance_after` for all 50 accounts (0 mismatches). Re-runnable (idempotent). Run it after `backfill_transactions.py` / any bulk transaction change.

---

## Regulatory Reporting Department

Third department (`/regulatory/`), built on the same `bank.db`. Produces Basel III / RBI **supervisory returns** at three levels: **system** (all banks), **individual bank**, and **individual client**.

- **Engine:** `backend/regulatory_engine.py` — pure functions, no DB. Computes:
  - *Client exposure:* EAD (outstanding), PD (model `pd_score`), LGD (by collateral/type), RBI Standardised-Approach risk weight (35% home … 100% unsecured, 150% NPA), RWA, capital charge (RWA × 11.5%), expected loss, IRAC provision (0.40% standard / 15%+ NPA).
  - *Bank capital:* credit RWA + operational RWA (Basel Basic Indicator Approach) + market RWA (nil), Tier-1/Tier-2 capital, CRAR/CET1/Tier-1/leverage ratios vs RBI minimums.
  - *Bank liquidity:* HQLA, LCR, ASF/RSF → NSFR, CRR, SLR. Funding modelled as live retail deposits + a wholesale plug for the loan-to-deposit gap.
- **RBI minimums used:** CRAR ≥ 11.5% (incl. 2.5% CCB), Tier-1 ≥ 9.5%, CET1 ≥ 8%, LCR ≥ 100%, NSFR ≥ 100%, CRR ≥ 4.5%, SLR ≥ 18%.
- **Balance sheet now feeds real figures (June 16 2026):** a `bank_balance_sheet` table (RBI Schedule III / Form A, per bank per period — equity capital, reserves, demand/savings/term deposits, borrowings, other liabilities; cash with RBI, balances with banks, investments, net advances, fixed/other assets; contingent liabilities & bills for collection) holds the financial position. The latest period (FY2025) is **live-anchored** (advances = SUM loan outstanding, deposits = SUM account balances) so assets == liabilities and the CRAR is realistic. `regulatory_engine.bank_capital_report` / `bank_liquidity_report` take an optional `balance_sheet` arg: when present they use the **real capital base** (CET1 = equity + reserves), total assets, HQLA (cash + SLR investments) and CRR/SLR holdings; when absent they fall back to the original proxies. The batch passes the latest balance sheet automatically. **Consequence:** ratios are now truthful — e.g. BANK001's ~265% loan-to-deposit ratio surfaces a genuine **LCR breach** (was masked by the old 30%-of-funding HQLA proxy).
- **Legacy synthetic-data proxies (fallback only):** if no balance sheet is on file, the capital base (Tier-1 ≈ 12% of assets) and HQLA (≈ 30% of funding) proxies still apply, labelled in each report's `assumptions` block. Operational RWA (Basel BIA) and nil market RWA remain assumptions either way. RWA, deposits, loan book and provisions are always computed from live data.
- **Batch:** `operations/scripts/run_regulatory_batch.py` runs the engine for all banks + all loans and writes the `reg_*` tables. Idempotent per `report_date` (re-running the same day replaces; history retained across days). Self-creates its tables (`CREATE TABLE IF NOT EXISTS`) so a fresh GCP deploy initialises automatically. Also refreshes the previously-empty `regulatory_compliance` table.
- **New `bank.db` tables:** `reg_capital_reports`, `reg_liquidity_reports`, `reg_client_exposures` (+ indices), and `bank_balance_sheet`. All gitignored with `bank.db`, deployed to GCP.
- **Balance-sheet API/UI:** `GET /regulatory/api/banks/<bank_id>/balance-sheet` (all periods, with computed totals); also embedded in the `GET /regulatory/api/banks/<bank_id>` response as `balance_sheets`. The per-bank dashboard view renders an RBI Schedule III "Statement of Financial Position" card (assets vs capital & liabilities, periods as columns) between the Liquidity and RWA panels.
- **Scheduling:** an APScheduler **daily 01:00** job (`regulatory_batch`) plus a startup run-if-missing (`_ensure_regulatory_reports`) — both in `app.py`'s `_start_scheduler()`, which is now invoked at the **bottom** of `app.py` (after the regulatory job functions are defined). Manual trigger via `POST /regulatory/api/run-batch` or the dashboard's "Run Batch" button.
- **Frontend:** `public/regulatory/index.html` — system overview (KPI cards, RWA-composition + capital-vs-RWA charts, bank scorecard), per-bank drill-down (ratio bars vs RBI floors, compliance register, exposure mix, top exposures, trend), and per-client regulatory report (EAD/RWA/capital/EL/provision register). Matches the operations UI design system (Syne/IBM Plex, red accent).

---

## Relationship Management & Decision Support Department

Fourth department (`/relationship/`) — the front-line RM workflow that sits between the customer and the automated decisioning core. It does **not** auto-decide; it produces a decision-support package and routes it through human controls. Built on the architecture review the user commissioned (RM layer, four-eyes, M/H/O separation, provenance, HITL learning).

**Three constructs kept strictly separate** (the keystone design point):
- **M — Machine recommendation:** `backend/decision_orchestrator.py` composes the existing `assessment_engine` findings (PD band, reason codes, counterfactuals) + `backend/policy_engine.py` (deterministic, **model-independent** credit policy) + confidence/OOD routing + decision sensitivity (knife-edge detection) + a **risk-adjusted** structured recommendation (Approve / Approve-with-conditions / Counter-offer / Refer / Decline) + a tiered, plain-language business explanation.
- **H — Human judgment:** the RM is the **final approving authority** with exactly two actions — **accept** (finalise the recommendation) or **reject** (decline; ≥20-char rationale required). Both finalise the case immediately; there is no four-eyes / committee / escalation routing in the live workflow (the brief was simplified at the user's request June 16 2026). The orchestrator still computes a `routing` block (advisory) and `rm_case_store.four_eyes` is retained but unused.
- **O — Organisational decision:** the final governed outcome, distinct from both.

**Governance built in:**
- **Delegation of Authority** (`decision_orchestrator._routing`): RM_SINGLE (small, low-risk, high-confidence) → FOUR_EYES (borderline / larger / low-confidence) → COMMITTEE / AUTO_DECLINE. **Escalation-instead-of-override**: above thresholds the RM cannot override, only escalate (API returns `ESCALATION_REQUIRED`). Any deviation from the machine line needs a ≥20-char rationale.
- **Confidence routing:** wide PD band (RF tree variance) or out-of-distribution intake → mandatory human review; model shown as advisory.
- **Decision provenance:** every M/H/O step is an append-only, **hash-chained** event (`rm_case_events`) — tamper-evident audit + the "decision provenance graph" rendered in the cockpit.
- **HITL learning loop:** outcomes captured post-decision (`rm_outcomes`); `/relationship/api/insights` reports override rate, model-agreement, and **override hit-rate** (default rate of overridden vs model-aligned decisions once matured) — overrides are *not* assumed correct.

**New `bank.db` tables:** `rm_cases` (queue/projection), `rm_case_events` (append-only provenance), `rm_outcomes`. Self-initialised on first use (`rm_case_store.init_schema`); gitignored with `bank.db`, deployed to GCP.

**Frontend:** `public/relationship/index.html` — queue (All / Pending / Decided), intake form (onboarding/KYC/bureau/financials), decision cockpit (recommendation hero + confidence dial, influential factors, counterfactual recourse, sensitivity, policy flags, M/H/O provenance timeline, **two-button accept/reject action panel**, **Case Report (PDF) card** with generate + versioned open/download links, outcome capture), and a governance/insights view.

**Design note (challenged the brief):** the requirement said "pass onboarding data into existing predictive models" and "modify the recommendation." Implemented as (a) an OOD/data-quality-aware path rather than blind pass-through, and (b) authority-gated actions with escalation-instead-of-override — both per the architecture review.

**Underwriter dossier reunified with the RM loop + richer PDF (June 17, 2026):** `report-underwriter.html` now has a **`?case=<case_id>` mode** that renders the full dossier (PD gauge, attribution + reason codes, Five C's scorecard **and** commentary, peer comparison, counterfactual recourse) directly from the RM case's `machine_json` (M) — no new endpoint, no disk persistence needed (`mapCaseToFindings()` maps M → the findings shape). **Decision framing:** pre-decision it shows the **model-suggested decision (advisory)** with a caption that the final decision rests with the RM; once the RM decides (`?case=` with `final_decision`), the **RM's decision is the authoritative pill** and the model line is labelled advisory. The RM cockpit's report card links **"📑 Underwriter report"** (`/report-underwriter.html?case=<id>`). The post-decision **PDF** (`report_generator.py`) now folds in the same rich detail it previously omitted: **Five C's per-C commentary** tables, a **Metrics vs Approved Borrowers** peer table, a **reason-code table** (driver/value/PD/why), and **counterfactual recourse** (from `M.counterfactuals`). All sourced from the existing M — no recomputation. The calculator's `?id=` applicant-letter link is hidden in `?case=` mode (findings aren't on disk for RM cases).

**Single origination channel — Credit Risk → RM (June 17, 2026):** data collection happens **only** on the Credit Risk data-collection page (`public/borrower-info.html`); the RM no longer has its own intake form. The flow:
- The calculator's summary band is **"Risk Assessment Summary"** and shows **risk measurements only** (grade, PD band, EL, indicative rate) — the **Approve/Refer/Decline verdict was removed**; the lend/no-lend decision belongs to the RM.
- A **"Refer to Relationship Manager →"** button (`sendToRM()`) maps the full borrower profile (4 ratios + KYC/bureau + exposure/collateral/age/income + onboarding/compliance: `kyc_status`, screening→`pep_flag`/`sanctions_hit`, `proposed_emi`, `existing_monthly_obligations` + `country_code`/`country`) onto the RM `application` shape and `POST`s `/relationship/api/cases` → INTERIM_ASSESSED case, tagged `source=credit_risk_calculator`, carrying `customer_id`. Cockpit deep-links via `/relationship/?case=<id>`.
- **RM page:** the "+ New Assessment" button is now **"+ New Customer"** and simply navigates to `/static/borrower-info.html` (single channel); the RM intake form (`showNewCase`/`submitCase`) was removed and an empty-state shown instead.
- **Country linkage:** the calculator has a **Country/Jurisdiction** dropdown populated from `/reference/api/countries` (shows a region·currency·regulator chip); the chosen `country_code` rides into the case.
- **Customer-ID lookup (`GET /api/customer-lookup/<cid>`, app.py):** when a typed Borrower/Loan ID matches a customer in **any** group bank, a green "Existing customer found" banner shows the relationship summary (accounts, loans, and transaction-history-derived variables: avg monthly inflow/outflow, income-credit count, EMI payments, **missed EMIs computed from each loan's disbursed date + tenure**, current balance) with an **"Autofill from records →"** button that populates the form (KYC mapped from `customer_kyc` enum→encoded values, 4 ratios from `credit_risk_metrics`, bank/country). Autofill is applied on the confirm click, not automatically.
No DB schema change — country/source ride in the case's application JSON; `create_case` already persists `customer_id`/`product`.

---

## Financial Reporting & Disclosures Department

Fifth department (`/financials/`), built on `bank.db`. Produces **bank-level and consolidated financial statements + regulatory disclosures**, with combined PDF export.

- **Reports (per bank + consolidated, period FY2025 with FY2024 history in the tables):**
  - *Balance Sheet* — RBI Schedule III (Form A), from `bank_balance_sheet`.
  - *Profit & Loss* — income statement, from `bank_profit_loss` (interest on advances live-anchored to the loan book; rest modelled from the balance sheet — yields/costs in `seed_bank_profit_loss.py`).
  - *Key Ratios* — CRAR, CET1, NIM, ROA, ROE, cost-income, Gross NPA, PCR, credit-deposit, CASA, LCR, NSFR.
  - *Basel III Pillar 3* — capital structure, RWA composition, capital-adequacy & leverage ratios, liquidity (LCR/NSFR), credit-risk exposure mix.
- **Engine:** `backend/financial_reports.py` (pure dict in/out) assembles the four reports; `consolidate()` aggregates per-bank stored rows and recomputes group ratios. Pillar 3 capital/liquidity reuse `regulatory_engine` (with the real balance sheet, so figures match the Regulatory dept).
- **PDF:** `backend/financial_report_pdf.py` builds one combined annual-report-style PDF per scope (matplotlib charts → LaTeX → pdflatex), versioned under `data/financial_reports/<scope>/<version>/` (scope = `<bank_id>` or `CONSOLIDATED`); regeneration keeps history. Reuses `report_generator`'s LaTeX helpers.
- **New `bank.db` table:** `bank_profit_loss` (per bank per period). Self-seeded (along with `bank_balance_sheet`) on first API hit via `_ensure_financials` → `seed_bank_balance_sheet.py` + `seed_bank_profit_loss.py`. Gitignored with `bank.db`, deployed to GCP.
- **Engine roll-ups:** `consolidate(bundles_raw, period, as_on, scope_id, scope_name, scope, scope_meta)` is generic — the same aggregation produces the whole-group, a **region** or a **country** bundle. `app._fin_bundle(conn, scope)` dispatches on `'CONSOLIDATED' | 'REGION:<region>' | 'COUNTRY:<iso3>' | '<bank_id>'`.
- **Foreign group banks:** carried balance-sheet-only (no loan/account rows). `regulatory_engine.bank_capital_report` / `bank_liquidity_report` detect `not loans and balance_sheet` and derive credit RWA from net advances (`FOREIGN_AVG_RISK_WEIGHT=0.75`), gross-income proxy (`FOREIGN_GROSS_INCOME_YIELD=0.095`) and read deposits/HQLA off the sheet — so their Basel III ratios are realistic. `seed_bank_balance_sheet.py` / `seed_bank_profit_loss.py` **skip** zero-loan banks so they never clobber the global seed.
- **PDF:** scope can also be `REGION:<region>` / `COUNTRY:<iso3>`; `report_generator._safe()` sanitises `:` → `_` for the folder name (`data/financial_reports/COUNTRY_USA/…`).
- **Frontend:** `public/financials/index.html` — **Group → Region → Country → Bank tree** sidebar; Group Overview with per-region cards; per-scope view (bank / country / region / group) with a Combined Report PDF card (generate + versioned open/download), Key Ratios, Balance Sheet (two-column), P&L, and Pillar 3 panels. Foreign-bank views disclose the group-reporting-currency assumption. Matches the platform design system.

---

## Global Reference Data Department

Sixth surface (`/reference/`) — the **country/jurisdiction layer above the banks**, making this a global group bank navigable as **Group → Region → Country → Bank**. Built on `bank.db`.

- **Tables:** `countries` (jurisdiction master — ISO-3 code, region, sub-region, currency, central bank, capital regulator, Basel framework, sovereign rating, per-jurisdiction min CRAR/CET1/Tier1/LCR/NSFR, `is_home`) and `country_macro` (periodic high-level indicators per country per period — GDP USD bn, GDP growth %, CPI inflation %, policy rate %, unemployment %, public-debt/GDP, current-account/GDP, FX per USD, population). 7 countries seeded (IND home + USA/GBR/SGP/ARE with banks; DEU/JPN reference-only), 2 macro periods each (CY2024/CY2025).
- **`banks.country_code`** column added + back-filled (`IND` for the original banks). Four foreign group banks (USA/GBR/SGP/ARE) are **grounded in a real ledger** (Phase 5.17): `seed_global_customers.py` generates per-bank customers/loans/accounts/transactions/credit_risk_metrics/bank_loan_metrics, so their `bank_balance_sheet`/`bank_profit_loss` are **live-anchored** by the standard seeders (not hardcoded) — same path as the India banks, in group reporting currency (₹).
- **Seed:** `operations/scripts/seed_global.py` — creates/populates `countries` + `country_macro`, adds `banks.country_code`, inserts the foreign **bank-master rows**, a few foreign `regulatory_bodies` rows, then calls `seed_global_customers.seed()` (ledger) and `seed_global_transactions.seed()` (18-month transaction history) to ground them. Idempotent. Self-seeded via `app._ensure_global` (called **before** the BS/P&L seed inside `_ensure_financials`, so the foreign loans exist when the sheets are live-anchored).
- **Transaction history:** `seed_global_transactions.py` gives each foreign customer a realistic monthly history (income credit / EMI / Bill / UPI; NPA customers miss income & EMIs). It is **deposit-neutral** — the opening balance is computed as `closing − net(flows)` and `balance_after` is written per row, so each account ends exactly at its grounded `accounts.balance` and the balance sheet / regulatory figures stay valid without a re-seed.
- **Frontend:** `public/reference/index.html` — world overview (KPIs + jurisdiction register grouped by region with macro snapshot, teal accent) and per-country drill (macro indicator cards with CY-on-CY trend arrows, jurisdiction regulatory minimums, full macro history table, and the group's banks there with links into Financial Reporting).
- **Reporting-currency note:** every bank.db figure is INR; foreign banks' statements are seeded in the **group reporting currency (₹)** (consistent with how groups publish one consolidated currency), while home country / local currency / FX / macro come from the country tables — so consolidation stays additive and the country dimension stays truthful.

---

## Smoke Tests

**File:** `testing/smoke_tests.py` — called by Flask admin endpoint  
**6 test cases:** Home page loads → Calculator loads → AIRB form input → ML PD calculation → Loan recorded to portfolio → Portfolio summary updates  
**Admin Selenium test:** `testing/test_admin_smoke_trigger.py` — 8 steps, all passing  
**Last run result:** 6/6 passed in ~7.6s

**GCP note:** Smoke tests require Chrome. On GCP App Engine, the smoke test button will return an import/driver error since Chrome is not available in the App Engine environment. This is expected — run smoke tests locally before deploying.

---

## Completed Work

| Phase | Description | Date |
|-------|-------------|------|
| Phase 1 | AIRB calculation engine (PD, LGD, EAD, Maturity, RWA) | June 2, 2026 |
| Phase 2 | Standardized Approach (risk weight tables, collateral haircuts) | June 3, 2026 |
| Phase 2.5 | Single-page app consolidation (borrower-info.html) | June 3, 2026 |
| Phase 3 | Flask backend + REST API (14 endpoints) | June 5, 2026 |
| Phase 3.5 | ML model integration (RandomForest PD via /api/predict-pd-ml) | June 5, 2026 |
| Phase 4 | Python 3.10 migration (scikit-learn 1.7.2 compatibility) | June 6, 2026 |
| Phase 5 | ML Admin Module (training, charts, schedule, smoke tests) | June 7, 2026 |
| Phase 5.5 | GCP pre-deployment cleanup + data dictionary | June 7, 2026 |
| Phase 5.6 | Banking Operations Module (bank.db, operations UI, db-admin schema viewer) | June 9–16, 2026 |
| Phase 5.7 | Assessment engine + case reports (rating masterscale, pricing, explainability, underwriter/applicant report views) | June 9–16, 2026 |
| Phase 5.8 | Repo audit: consolidated bank.db into project root, removed orphaned files (banking_models.py, case_report_builder.py, excel_loader.py, stray instance/ db), deleted unused venv/, fixed requirements.txt drift (selenium/webdriver-manager/requests), tightened .gitignore/.gcloudignore | June 16, 2026 |
| Phase 5.9 | Ledger reconciliation (reconcile_ledger.py — balance_after on every txn, accounts.balance synced); operations/index.html rewired from hardcoded mock to live /operations/api/* | June 16, 2026 |
| Phase 5.10 | **Regulatory Reporting Department** — regulatory_engine.py (Basel III/RBI capital + liquidity + client exposure), daily batch + reg_* tables, /regulatory/api/* routes, /regulatory/ dashboard (system/bank/client), home-page 3rd department card | June 16, 2026 |
| Phase 5.11 | Model-alignment fix: `feature_meta.model_feature_frame()` aligns engine/explainability inputs to the deployed 21-feature pickle (was silently broken at 4 features) | June 16, 2026 |
| Phase 5.12 | **Relationship Mgmt & Decision Support Department** — policy_engine (model-independent), decision_orchestrator (M), rm_case_store (M/H/O + hash-chained provenance + four-eyes/DoA + outcomes), /relationship/api/* routes, /relationship/ cockpit, home-page 4th card | June 16, 2026 |
| Phase 5.13 | **RM workflow simplified to two options** (accept / reject; RM is final authority — four-eyes/escalation/modify/defer/request-info removed from the live flow) **+ PDF case reports** (`report_generator.py`: matplotlib charts → LaTeX → pdflatex, versioned per case under `data/case_reports/`, generate/list/open/download routes, cockpit Report card) | June 16, 2026 |
| Phase 5.14 | **Bank balance sheet** — `bank_balance_sheet` table (RBI Schedule III, per bank per period, live-anchored), `seed_bank_balance_sheet.py`; regulatory_engine now uses real capital base/HQLA/CRR-SLR from it (proxies are fallback); balance-sheet API + Schedule III card on the per-bank Regulatory dashboard; Playwright RM E2E tests added under `testing/rm-e2e/` | June 16, 2026 |
| Phase 5.15 | **Financial Reporting & Disclosures Department** (`/financials/`) — `bank_profit_loss` table + `seed_bank_profit_loss.py`; `financial_reports.py` (Balance Sheet / P&L / Key Ratios / Pillar 3, per bank + consolidated); `financial_report_pdf.py` (combined LaTeX→PDF per scope, versioned); `/financials/api/*` routes with self-seed; `/financials/` dashboard; home-page 5th department card | June 16, 2026 |
| Phase 5.16 | **Global group bank — country reference layer** (`/reference/`): `countries` + `country_macro` tables + `seed_global.py` (macro vars, regulators, per-jurisdiction Basel minimums); `banks.country_code`; 4 foreign group banks (USA/UK/Singapore/UAE, balance-sheet-only, group ₹); `regulatory_engine` advances-based RWA fallback for loan-less banks; `financial_reports.consolidate()` generalised for region/country roll-ups; `/financials/api/{region,country}` + Group→Region→Country→Bank tree UI; `/reference/api/*` + reference dashboard; home-page 6th card; region-level PDF button | June 17, 2026 |
| Phase 5.17 | **Grounded the foreign banks** — `seed_global_customers.py` generates a real ledger (customers/loans/accounts/credit_risk_metrics/bank_loan_metrics) for BANK003–006 so their balance sheet/P&L/CAR/LCR/GNPA roll up from actual loans (parity with the India banks; ~86 foreign customers, group ₹). `seed_global_transactions.py` adds an 18-month, deposit-neutral transaction history (4.5k txns). `seed_global.py` no longer hardcodes foreign BS/P&L; `_ensure_financials` seeds the global layer before BS/P&L; BS/P&L seeders skip-guard now naturally includes the foreign banks. PD model corpus (`bank_loan_metrics`) now spans all 6 banks | June 17, 2026 |
| Phase 5.18 | **Real-world bank network — all 9 banks from actual FY2025 annual reports.** Replaced all fictitious banks with real institutions. India: HDFC Bank, ICICI Bank, Bank of Baroda, Punjab National Bank. Foreign: BANK003 JPMorgan Chase N.A. (USA, NPL 0.66%, CAR 15.6%), BANK004 Barclays Bank PLC (UK, NPL 2.1%, CAR 16.1%), BANK005 DBS Bank Ltd (SGP, NPL 1.0%, CAR 17.5%), BANK006 Emirates NBD PJSC (UAE, NPL 3.5%, CAR 16.0%), BANK008 Commonwealth Bank of Australia (AUS, NPL 0.5%, CAR 18.7%). Added Australia to the group. New tooling: `seed_real_bank.py` (9-step full-ledger seeder from profile JSON), `normalize_bank.py` (rebalances capital/borrowings; reruns reg batch), `_delete_bank.py` (wipes per-bank data, preserves master row), `bank_profiles/*.json` (one JSON per bank with real balance-sheet ratios + deposit mix + exposure mix). System dashboard enhanced with NPA KPI row (count, count%, amount, GNPA%) and per-bank NPA columns | June 19, 2026 |

---

## Important Technical Notes

### PD Method
- The calculator **always uses ML** (`/api/predict-pd-ml`) with automatic fallback to rule-based if Flask is unreachable
- No toggle on the frontend — ML is the default and only mode
- `api-integration.js` handles the API call + fallback logic

### APScheduler
- Starts only in the main Werkzeug process: `if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'`
- **The scheduler start call lives at the bottom of `app.py`** (not next to `_start_scheduler`'s definition) because `_start_scheduler()` references the regulatory job functions defined later in the module — calling it earlier would `NameError`.
- Two jobs: `pd_training` (configurable weekly/daily/monthly) and `regulatory_batch` (daily 01:00).
- Day-of-week config uses APScheduler 3-letter abbreviations: `"sun"` not `"sunday"`
- Full day names are normalised in `_reconfigure_scheduler()` via `_DOW_MAP`

### Data Directory on GCP
- `data/` is runtime-generated and ephemeral on App Engine
- On first deployment, `data/training/`, `data/archive/`, `data/synthetic/`, `data/runs/`, `data/reports/` and `data/audit_log.json` must exist or be created by the app
- Trainer, synthetic_data, and the report-persistence code all call `os.makedirs(..., exist_ok=True)` so they self-initialise
- Model retraining results (charts, run history) and case reports/audit log will be lost on instance restart — acceptable for current scope
- `bank.db` is the one runtime file that's deliberately NOT excluded from `.gcloudignore` — see "Banking Operations Module"

### app.yaml
- Confirmed correct as of June 16, 2026: `runtime: python310`, `entrypoint: gunicorn -b :$PORT app:app`

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 6 | GCP App Engine deployment | In progress |
| 7 | Operational Risk (BIA, TSA, AMA) | Partially delivered — operational RWA via BIA in `regulatory_engine.py`; TSA/AMA still planned |
| 8 | Market Risk (VaR) | Planned (market RWA currently nil — no trading book in dataset) |
| 9 | Liquidity Risk (LCR, NSFR) | Delivered via Regulatory Reporting (LCR/NSFR/CRR/SLR in `regulatory_engine.py`) |

---

## Local Development

```powershell
# Option 1: one-shot launcher — creates venv310 if missing, installs requirements.txt, runs app.py
.\run_flask.ps1

# Option 2: manual
.\venv310\Scripts\python.exe app.py

# App available at http://127.0.0.1:5000
# Admin at http://127.0.0.1:5000/admin.html  (password: 1234)
# Operations module at http://127.0.0.1:5000/operations/
```

**Required:** Python 3.10, Chrome (for smoke tests)  
**Note:** `venv310` is the only virtual environment in this project (a stray Python 3.12 `venv/` was removed June 16, 2026).
