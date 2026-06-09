# Credit Risk Calculator — Project Context (CLAUDE.md)

## Project Overview

**Project Name:** Banking Credit Risk Calculator  
**Purpose:** Basel III compliant credit risk calculation platform with ML-powered PD prediction, admin-driven model retraining, and full portfolio management  
**Current Status:** Production-ready — GCP App Engine deployment in progress  
**Location:** `C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk`  
**User Email:** ravi_phdm23@iift.edu  
**Last Updated:** June 7, 2026  

---

## Current Architecture

### Stack
| Layer | Technology |
|-------|-----------|
| Web server | Flask 2.3+ with gunicorn |
| ML model | RandomForestRegressor (scikit-learn 1.7.2) via `pd_model.pkl` |
| Scheduler | APScheduler (BackgroundScheduler) — weekly Sunday 02:00 retraining |
| Frontend | Vanilla HTML5/CSS3/JS — no framework |
| Storage | Browser localStorage (portfolio), local filesystem (model, run history) |
| Deployment target | GCP App Engine (Python 3.10) |
| Python version | 3.10 (venv310 locally) |

### Entry Point
`app.py` — 12 REST API routes + 11 admin API routes + APScheduler

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
├── .env                            Local environment vars (never committed)
├── .gitignore                      Git exclusions
├── .gcloudignore                   GCP deployment exclusions
├── CLAUDE.md                       This file
│
├── backend/
│   ├── __init__.py
│   └── calculations.py             AIRB + SA calculation classes
│
├── ml_models/
│   ├── __init__.py
│   ├── pd_model.pkl                Active RandomForest PD model
│   ├── pd_model_backup.pkl         Previous model (for rollback)
│   ├── pd_model_metadata.json      Model version, metrics, features
│   ├── hyperparameters.json        RF hyperparams + training + schedule config
│   ├── run_history.json            All training run records
│   ├── trainer.py                  Full training pipeline (scan→validate→train→promote→archive)
│   └── synthetic_data.py           Synthetic data generator — 6 Indian banks (INR)
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
│   └── data-dictionary.html        Variable reference + Five C's mapping
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
    └── runs/{run_id}/              Per-run chart .b64 files + metrics
```

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
| GET  | `/api/health` | Health check |
| GET  | `/api/info` | Application info |

### Admin API (`/admin/api/`) — Header: `X-Admin-Password: 1234`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/admin/api/status` | Model status + schedule + last run |
| GET  | `/admin/api/data-sources` | Files in training folder |
| POST | `/admin/api/generate-synthetic` | Generate 6 Indian bank CSV files |
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

---

## ML Model

### Model: `ml_models/pd_model.pkl`
- **Type:** RandomForestRegressor (scikit-learn 1.7.2)
- **Target:** `pd_observed` — probability of default (decimal 0–1)
- **Features (4):** `de_ratio`, `interest_coverage`, `profitability`, `liquidity_ratio`
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
Total: 14,300 rows. Generated via admin panel "Generate Indian Bank Synthetic Data" button.

---

## Admin Module

**URL:** `http://localhost:5000/admin.html`  
**Password:** `1234` (stored in `sessionStorage`)  
**Note:** URL is intentionally unlisted — not linked from the public home page.

### Panels
| Panel | What it does |
|-------|-------------|
| Model Status | Active model KPIs, metadata, Train Now button |
| Data Sources | Files in training folder, generate synthetic data |
| Hyperparameters | Edit RF params + training settings |
| Schedule | Configure weekly/daily/monthly retraining |
| Run History | All past runs with metrics + confusion matrix |
| Charts | 6 evaluation charts per run (ROC, feature importance, etc.) |
| Smoke Tests | Trigger 6 headless Selenium consumer-side tests |

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

---

## Important Technical Notes

### PD Method
- The calculator **always uses ML** (`/api/predict-pd-ml`) with automatic fallback to rule-based if Flask is unreachable
- No toggle on the frontend — ML is the default and only mode
- `api-integration.js` handles the API call + fallback logic

### APScheduler
- Starts only in the main Werkzeug process: `if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'`
- Day-of-week config uses APScheduler 3-letter abbreviations: `"sun"` not `"sunday"`
- Full day names are normalised in `_reconfigure_scheduler()` via `_DOW_MAP`

### Data Directory on GCP
- `data/` is runtime-generated and ephemeral on App Engine
- On first deployment, `data/training/`, `data/archive/`, `data/synthetic/`, `data/runs/` must exist or be created by the app
- Trainer and synthetic_data modules call `os.makedirs(..., exist_ok=True)` so they self-initialise
- Model retraining results (charts, run history) will be lost on instance restart — acceptable for current scope

### app.yaml Issue (to fix before GCP deploy)
- Current `app.yaml` has `entrypoint: gunicorn -b :$PORT main:app` — wrong, should be `app:app`
- Runtime is set to `python312` — should match our Python 3.10 environment

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 6 | GCP App Engine deployment | In progress |
| 7 | Operational Risk (BIA, TSA, AMA) | Planned |
| 8 | Market Risk (VaR) | Planned |
| 9 | Liquidity Risk (LCR, NSFR) | Planned |

---

## Local Development

```powershell
# Start Flask with Python 3.10 venv
.\venv310\Scripts\python.exe app.py

# App available at http://127.0.0.1:5000
# Admin at http://127.0.0.1:5000/admin.html  (password: 1234)
```

**Required:** Python 3.10, Chrome (for smoke tests)
