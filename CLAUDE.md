# Credit Risk Calculator — Project Context (CLAUDE.md)

## Project Overview

**Project Name:** Banking Credit Risk Calculator  
**Purpose:** Basel III compliant credit risk calculation platform with ML-powered PD prediction, admin-driven model retraining, full portfolio management, banking operations, and supervisory regulatory reporting  
**Current Status:** Production-ready — GCP App Engine deployment in progress  
**Location:** `C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk`  
**User Email:** ravi_phdm23@iift.edu  
**Last Updated:** June 16, 2026  

**Four departments** surfaced from the home page (`public/index.html`): **Credit Risk** (calculator + ML), **Banking Operations** (`/operations/`), **Regulatory Reporting** (`/regulatory/` — Basel III / RBI capital & liquidity returns), and **Relationship Management & Decision Support** (`/relationship/` — front-line RM workflow with AI-assisted decisioning, four-eyes, and the M/H/O provenance ledger). Each has its own section below.

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
│   └── report_generator.py         PDF credit decision report: matplotlib charts (PNG) → LaTeX → pdflatex → PDF; versioned per case under data/case_reports/<case_id>/<version>/ (regeneration keeps history)
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
│       ├── run_regulatory_batch.py Daily Regulatory Reporting batch — computes & stores Basel III/RBI returns into the reg_* tables; also wired into APScheduler (daily 01:00) and POST /regulatory/api/run-batch
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
│   └── relationship/
│       └── index.html              RM decision-support cockpit (served at /relationship/) — intake, recommendation, provenance, four-eyes, insights
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

A separate banking-operations demo, backed by **`bank.db`** (SQLite, project root) — distinct from the credit-risk calculator's own data. Schema: `banks`, `branches`, `customers`, `accounts`, `loans`, `transactions`, `credit_risk_metrics`, plus regulatory tables (`regulatory_bodies`, `regulatory_requirements`, `regulatory_compliance`).

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
- **Synthetic-data proxies:** the dataset has no equity ledger or trading book, so the capital base (Tier-1 ≈ 12% of banking-book assets) and HQLA (≈ 30% of funding) are **clearly-labelled proxies** surfaced in each report's `assumptions` block and on the UI's amber methodology panel. RWA, deposits, loan book and provisions are computed from live data.
- **Batch:** `operations/scripts/run_regulatory_batch.py` runs the engine for all banks + all loans and writes the `reg_*` tables. Idempotent per `report_date` (re-running the same day replaces; history retained across days). Self-creates its tables (`CREATE TABLE IF NOT EXISTS`) so a fresh GCP deploy initialises automatically. Also refreshes the previously-empty `regulatory_compliance` table.
- **New `bank.db` tables:** `reg_capital_reports`, `reg_liquidity_reports`, `reg_client_exposures` (+ indices). All gitignored with `bank.db`, deployed to GCP.
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
