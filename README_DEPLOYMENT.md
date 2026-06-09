# Banking Credit Risk Calculator — Deployment Guide

## Target Platform: Google Cloud Platform — App Engine

---

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- A GCP project created (`gcloud projects create <project-id>`)
- App Engine enabled in the project (`gcloud app create --region=asia-south1`)

---

## Files Involved in Deployment

| File | Purpose |
|------|---------|
| `app.yaml` | App Engine configuration (runtime, entrypoint, env vars) |
| `requirements.txt` | Python dependencies installed at build time |
| `Procfile` | Gunicorn start command (used by Render/Heroku, not GCP) |
| `runtime.txt` | Python version pin (used by Render, not GCP) |
| `.gcloudignore` | Files excluded from the GCP upload |

---

## Step-by-Step Deployment

### 1. Verify `app.yaml`

```yaml
runtime: python310
entrypoint: gunicorn -b :$PORT app:app

env_variables:
  FLASK_ENV: "production"
  SECRET_KEY: "your-secret-key-here"

automatic_scaling:
  min_instances: 1
  max_instances: 3
```

Key points:
- `runtime: python310` — matches our Python 3.10 environment
- `entrypoint` must reference `app:app` (the `app` variable inside `app.py`)
- Set `SECRET_KEY` to a strong random string before deploying

### 2. Verify `requirements.txt`

All dependencies must be pinned or range-specified. Run locally first:

```powershell
venv310\Scripts\pip.exe install -r requirements.txt
```

### 3. Set environment variables

Either add to `app.yaml` under `env_variables`, or set via GCP Console → App Engine → Settings → Environment Variables:

```
FLASK_ENV=production
SECRET_KEY=<random-32-char-string>
```

Do **not** commit `.env` — it is gitignored.

### 4. Deploy

```bash
gcloud app deploy app.yaml --project=<your-project-id>
```

Watch the build log. First deploy takes 3–5 minutes.

### 5. Open the application

```bash
gcloud app browse
```

Or navigate to: `https://<project-id>.appspot.com`

---

## What Gets Deployed (from `.gcloudignore`)

**Included:**
- `app.py`, `config.py`, `requirements.txt`, `app.yaml`
- `backend/` — calculation engine
- `ml_models/` — RandomForest model + trainer + metadata
- `public/` — all HTML/JS pages (except api-test.html, pd-calculator.html)

**Excluded:**
- `venv/`, `venv310/` — not needed, GCP installs from requirements.txt
- `testing/` — Selenium tests require Chrome, not available on App Engine
- `data/archive/`, `data/synthetic/`, `data/runs/` — ephemeral, regenerated at runtime
- `*.log`, `.env`, `__pycache__/`
- Dev-only scripts and documentation

---

## Post-Deployment Checklist

- [ ] `https://<project>.appspot.com/api/health` returns `{"status": "healthy"}`
- [ ] Home page loads at `https://<project>.appspot.com`
- [ ] Calculator at `/borrower-info.html` — enter sample loan, click Calculate, verify PD shown
- [ ] `/api/predict-pd-ml` returns ML prediction (check browser Network tab)
- [ ] Admin panel at `/admin.html` — login with password `1234`, check Model Status panel
- [ ] Admin → Generate Synthetic Data → Train Now (note: first run after deploy has empty data folder)

---

## Known Limitations on App Engine

| Feature | Local | App Engine |
|---------|-------|------------|
| ML PD prediction | Works | Works |
| Model retraining (Train Now) | Works | Works |
| Training data persistence | Persists on disk | **Lost on instance restart** |
| Run history / charts | Persists on disk | **Lost on instance restart** |
| Smoke Tests button | Works (Chrome available) | **Fails — no Chrome on App Engine** |
| Scheduled retraining | Works | Works (APScheduler runs in process) |

**For production persistence** of training data and run history, connect Google Cloud Storage (GCS) and update paths in `ml_models/trainer.py` to write to a GCS bucket instead of local `data/`.

---

## Updating the Deployed App

```bash
# Make code changes, then:
gcloud app deploy app.yaml --project=<your-project-id>
```

To update the ML model after retraining locally:

```bash
# Retrain locally via admin panel, then redeploy
# ml_models/pd_model.pkl is included in the deployment
gcloud app deploy app.yaml --project=<your-project-id>
```

---

## Viewing Logs

```bash
gcloud app logs tail --project=<your-project-id>
```

Or via GCP Console → App Engine → Versions → View Logs

---

## Local Development

```powershell
# Start with Python 3.10 venv
.\venv310\Scripts\python.exe app.py

# Available at http://127.0.0.1:5000
```
