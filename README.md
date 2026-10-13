# Banking Credit Risk Platform — SHARP + AEGIS research workflow

This repository contains two things:

1. A **Basel III-style banking credit-risk web application** (Flask). Full architecture is in
   [`CLAUDE.md`](CLAUDE.md).
2. The **SHARP + AEGIS research workflow** — a feature-selection methodology (**SHARP**: Shapley Ranking
   with Parsimony) wrapped in a governed model-approval framework (**AEGIS**: Approval & Evidence-based
   Governance for Internal-ratings Systems), driven interactively with **Claude Code**.

This README is about **cloning the repo onto any machine and reproducing the governed workflow** for the
example datasets *and* for any new dataset.

---

## 1. Prerequisites

> **Platform:** this solution targets **Windows 10/11 with PowerShell**. The paths, launcher
> (`run_flask.ps1`), and `venv310\Scripts\` layout assume Windows; it is designed and maintained for Windows
> only.

- **Windows 10/11** (PowerShell)
- **Python 3.10** (exact — `venv310` is the only supported virtual environment)
- **Git for Windows**
- **[Claude Code CLI](https://claude.com/claude-code)** — for the interactive governed workflow
- *(optional)* Google Chrome — only for the web app's Selenium smoke tests

## 2. Setup on a fresh Windows machine

```powershell
git clone https://github.com/raviphdm23-a11y/banking-credit-risk.git
cd banking-credit-risk

python -m venv venv310
.\venv310\Scripts\python.exe -m pip install -r requirements.txt
# or simply: .\run_flask.ps1   (creates venv310, installs deps, and launches the app)
```

`requirements.txt` includes `scikit-learn`, `xgboost`, `shap`, `pandas`, `numpy` — everything SHARP/AEGIS
needs.

## 3. Datasets

The two worked examples ship in `data/ml_lab/datasets/`:
- `hmeq.csv` — Home Equity (5,960 rows, secured, informative missingness)
- `german_credit_record.csv` — German Credit (1,000 rows, has protected attributes → fairness)

For a **new dataset**, drop any binary-classification CSV into `data/ml_lab/datasets/` with a label column
(e.g. `target`). SHARP auto-detects numeric vs categorical features.

> Note: the project normally gitignores raw benchmark CSVs; these two are committed deliberately so the
> documented runs reproduce on a fresh clone. `venv310/`, `bank.db`, and `*.pkl` models stay gitignored and
> are recreated locally.

---

## 4. The method (read these — they *are* the methodology)

| File (`paper analysis/draft one/`) | What it is |
|---|---|
| `METHODOLOGY.md` | **SHARP** — the analytical engine: Stages 0–4, fixed config (§ Fixed configuration), deployment controls (§7.8, incl. the standard PD floor), governance operating model (§7.9) |
| `AEGIS_GOVERNANCE.md` | **AEGIS** — the governance lifecycle: decision gates G0–GF, RACI, Model Approval Committee, Go/No-Go engine, primary-verified regulatory criteria, design principles (incl. P8) |
| `SHARP_HMEQ.md` + `AEGIS_RUN_HMEQ.md` | Worked HMEQ run (SHARP record + hash-chained AEGIS gate log) |
| `SHARP_GERMAN.md` + `AEGIS_RUN_GERMAN.md` | Worked German Credit run (incl. the fairness gate) |
| `AEGIS_HMEQ_CUTOFF_POLICY.md` | Example fixed-cutoff / rating-grade / risk-based-pricing policy |
| `CLAUDE.md` (repo root) | Repo guidance Claude Code reads automatically |

## 5. Running SHARP directly (without Claude)

```powershell
.\venv310\Scripts\python.exe -c "import sys; sys.path.insert(0,'ml_models'); import pandas as pd, v3_pipeline as v3; df=pd.read_csv('data/ml_lab/datasets/hmeq.csv'); print(v3.run_pipeline(df, target='target', dataset_name='hmeq', verbose=False)['report'])"
```

For German Credit, exclude the prohibited attributes first (`personal_status_sex`, `age`,
`foreign_worker`) — see `AEGIS_RUN_GERMAN.md` gate G0 for why.

---

## 6. The governed workflow with Claude Code (the main goal)

1. Install and authenticate Claude Code, then run `claude` **inside the repo directory**.
2. Claude auto-reads `CLAUDE.md`. Point it at the method once per session:
   > "Read `paper analysis/draft one/METHODOLOGY.md` and `AEGIS_GOVERNANCE.md`, and the working agreements
   > in the README. We'll run SHARP + AEGIS."
3. For a **new dataset**, ask something like:
   > "Run SHARP v3 on `data/ml_lab/datasets/<file>.csv` (target=`<col>`), record it as `SHARP_<NAME>.md`,
   > then take me through the full AEGIS governance process — I'll be the human signer at each gate."
4. What Claude does, matching the two examples in this repo:
   - runs `v3_pipeline.run_pipeline(...)` and writes the `SHARP_<NAME>.md` record (every figure traces to
     the run);
   - drives gates **G0 → G1 → G2 → G3 → G4 → G5 → GF**, presenting at each gate a **machine recommendation
     + evidence pack + a closed set of 2–4 options** (each with data / rationale / benefits / risks /
     residual-risk);
   - **you pick one option with a short rationale**; Claude logs a **hash-chained decision** in
     `AEGIS_RUN_<NAME>.md`;
   - at **GF** it runs the Go/No-Go engine; you rule **GO / GO-WITH-CONDITIONS / NO-GO** as MAC chair;
   - **[required] produces the cutoff / grade / risk-based-pricing policy** (`AEGIS_<NAME>_CUTOFF_POLICY.md`)
     and an **acceptance demonstration** — ≥3 representative candidates scored with **approve/decline
     decisions and reason-code reports**. A PD with no decision and no applicant report is not complete.

You end with a SHARP analytical record, an auditable hash-chained AEGIS approval log, a decisioning policy,
and applicant reason reports — the same artifacts as the HMEQ and German examples here.

**The full step-by-step process (with the exact prompts) is in `paper analysis/draft one/USER_JOURNEY.md`** —
every stage is mandatory, ending in scored candidates with approve/decline + reasons.

---

## 7. Working agreements (how the workflow stays honest)

These conventions are part of the method. A fresh Claude session on a new machine should follow them (they
are encoded here because Claude Code's per-machine memory does **not** travel with a clone):

- **No extrapolation** — every figure must trace to a recorded run; flag unfavourable or unverified results
  rather than smoothing them over.
- **Calibration is standard** — apply isotonic calibration to every final model automatically.
- **PD floor is standard** — report PD floored at **0.03%** (Basel CRE32.3) and capped below 100%
  (`METHODOLOGY.md §7.8`; implemented in `ml_models/missing_governance.py`).
- **Gates decide governance, not analytics (AEGIS P8)** — fixed methodology parameters (exact-vs-sampled per
  §5.5, selection tolerances, random seed) are *never* re-opened as per-run gate options.
- **Record convention** — per dataset: `SHARP_<DATASET>.md` + `AEGIS_RUN_<DATASET>.md` with a hash-chained
  decision log; a `sharp_runs/*.json` machine record where applicable.
- **Verify regulatory thresholds against primary sources** (BIS/CRE, Fed SR letters, EBA, EU AI Act) before
  writing them into the methodology — never cite a threshold from memory.
- **Confirm before outward-facing or hard-to-reverse actions** (pushing, deleting, deploying).

---

## 8. Repo layout

See [`CLAUDE.md`](CLAUDE.md) for the full project structure, commands, API routes, and architecture. In
brief: `app.py` (Flask server) · `backend/` (calculation/assessment/governance modules) · `ml_models/`
(SHARP pipeline: `v3_pipeline.py`, `shapley_utils.py`, `selection.py`, `binning.py`, `missing_governance.py`)
· `operations/scripts/` (seeders/onboarders) · `public/` (frontend) · `paper analysis/draft one/` (the
research artifacts).
