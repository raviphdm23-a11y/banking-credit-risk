# Replication Guide — Governed Feature-Selection Exercise (Claude CLI runbook)

> **Who this is for.** A research collaborator who wants to reproduce, on their own
> Windows laptop, the governed credit-risk feature-selection process (the SHARP
> methodology wrapped in the AEGIS governance gates) exactly as the authors run it.
>
> **How to use it.** Put this file somewhere on your machine, open **Claude Code (CLI)**
> in that folder, and tell Claude:
> *"Read REPLICATION_GUIDE.md and follow it, starting at Phase 1."*
> Claude will clone the repo, build the environment, verify it, and then walk you
> through a governed run gate-by-gate. **You stay in the loop**: Claude presents each
> gate's options and waits for your sign-off before sealing it (that is the method,
> not a limitation).

---

## 0. Instructions to Claude (read this first, then act)

You are driving a reproducible research exercise. Follow these rules throughout — they
are the methodology's pre-registered discipline, not preferences:

1. **Nothing is invented.** Every number you report must come from a run you just
   executed or a file in the repo. No fabricated economics, PD cut-offs, prices, or
   fairness figures. If a value is unknown, say so and compute it. The accept/decline
   threshold and any pricing are *institution inputs* — exogenous, never derived here.
2. **Keep the human honest-checked.** If a result is unfavourable, surprising, or rests
   on a fragile cell, say so plainly. Flag any step you skipped.
3. **Gates decide governance, not analytics (P8).** The analysis parameters are fixed
   across every dataset (see §5). A gate option may change *scope, eligibility,
   conservatism, cut-offs, Go/No-Go* — it may **never** re-open a pre-registered
   parameter (seed, IV threshold, shadow bar, confirmation frequency, selection
   tolerances, CV folds, estimator mode).
4. **Calibration and the PD floor are always-on** final steps: isotonic calibration;
   PD floored at 0.03 % (Basel CRE32.3), capped at 99.9 %.
5. **Present, don't decide.** At each gate emit the option set from
   `ml_models/aegis_gates.py` and wait for the human to choose **A / B / C** with a
   rationale of at least 20 characters. Only then seal the gate and continue.
6. **Platform:** Windows + PowerShell + Python **3.10** only. The single virtual
   environment is `venv310`. Do not scaffold for macOS/Linux.

Before the first gate, **read** `paper analysis/draft one/METHODOLOGY.md` and
`paper analysis/draft one/AEGIS_GOVERNANCE.md` in full, and the module docstring of
`ml_models/aegis_gates.py`. These are the source of truth; this guide is the operating
procedure.

---

## 1. Phase 1 — Clone and build the environment

Run in PowerShell. Replace the clone directory if you like.

```powershell
# 1. Clone (you need read access to the repo)
git clone https://github.com/raviphdm23-a11y/banking-credit-risk.git
cd banking-credit-risk

# 2. Create the Python 3.10 virtual environment named venv310
#    (py -3.10 must resolve to a Python 3.10 install)
py -3.10 -m venv venv310

# 3. Install dependencies (requirements.txt is the source of truth)
.\venv310\Scripts\python.exe -m pip install --upgrade pip
.\venv310\Scripts\python.exe -m pip install -r requirements.txt
```

Notes for Claude:
- If `py -3.10` is missing, tell the user to install Python 3.10 (python.org) and the
  `py` launcher; do **not** silently fall back to another version.
- `run_flask.ps1` also bootstraps `venv310` and installs deps, but it then launches the
  Flask app — which is **not** needed for the governed exercise. Use the explicit steps
  above for the research workflow; only run the app if the user wants the web platform.
- LaTeX (MiKTeX with `pdflatex` + `bibtex`) is needed **only** if the user wants to
  rebuild the paper PDF. It is not needed for the governed run itself.

---

## 2. Phase 2 — Verify the install

```powershell
# a) The governance engine self-test must pass (reproduces the committed SBA verdict)
.\venv310\Scripts\python.exe ml_models\aegis_gates.py

# b) The SHARP pipeline and its dependencies must import cleanly
.\venv310\Scripts\python.exe -I -c "import sys; sys.path.insert(0,'ml_models'); import v3_pipeline, selection, binning, shapley_utils, feature_governance, aegis_gates; print('engine OK')"
```

Expected: the self-test prints `all self-tests passed.` and the import prints `engine OK`.
If either fails, **stop** and diagnose (usually a wrong Python version or a missing
dependency) before going further. Do not proceed to a governed run on a broken install.

---

## 3. Phase 3 — Run one governed exercise, G0 → GF

Pick a dataset from §4 (start with **`south_german_credit_en.csv`**, target `target`, or
**`sba_loans.csv`**, target `Default` — both are fully worked in the repo so the user can
check your output against `AEGIS_RUN_GERMAN.md` / `AEGIS_RUN_SBA.md`).

Drive it in this order. Do **all** computation in Python via `venv310`; keep scratch
scripts in a scratch folder, never commit them.

### 3.1 Run the SHARP pipeline (produces the stage evidence)
```python
import sys; sys.path.insert(0, "ml_models")
import pandas as pd, v3_pipeline as v3
df = pd.read_csv(r"data\ml_lab\datasets\<DATASET>.csv")
out = v3.run_pipeline(df, target="<TARGET>", dataset_name="<NAME>", verbose=True)
open(r"<scratch>\SHARP_<NAME>.md", "w", encoding="utf-8").write(out["report"])
```
From `out` read: Stage 0 eligibility tags, Stage 1 screen (which features pass IV ≥ 0.02
with monotonic WOE, and their IVs), Stage 2 Shapley importances + shadow bar +
confirmation frequencies, Stage 3 parsimony curve + selected `k`, Stage 4 calibration.

### 3.2 Compute data sufficiency (reported diagnostic, never auto-reject)
- **EPV** = events / size of the **candidate pool** (the post-G0 feature count).
- **Riley minimum-N** via `backend/riley_minsize.py` (uses the full-candidate C-statistic).
Report both; a shortfall is governed by disclosure + Margin of Conservatism, not a halt
(unless HIGH tier — see the composition table in `AEGIS_GOVERNANCE.md` §3.2).

### 3.3 Walk the gates G0–G5 (one at a time, human signs each)
For each gate, build the evidence dict and emit the options:
```python
import aegis_gates as ag
gd = ag.build_gate("G1", evidence_dict)   # G0, G1, G2, G3, G4, G5
```
Present `gd` to the human as the machine recommendation + the A/B/C option set (each with
its data / rationale / benefits / risks / residual-risk). **Wait** for the user's choice
and a ≥20-char rationale. Then seal the gate into the hash chain:

```python
import hashlib
def seal(prev, gate, option, signer, rationale):
    content = f"{gate}|{option}|{signer}|{rationale}"
    return hashlib.sha256((prev + content).encode()).hexdigest()[:8]
# genesis is the string  GEN-<NAME>0 ; each gate's prev is the previous entry_hash
```
Record `prev → entry_hash` for every gate. The evidence each gate expects is documented
in the `ml_models/aegis_gates.py` docstrings (e.g. `gate_g1` wants
`tier, n_pass, n_pool, epv, riley_req, riley_avail, dominant_feature, dominant_iv`).

### 3.4 G4 — compute calibration and fairness HONESTLY
This is the gate most easily got wrong. Use **out-of-fold** predictions and do **not**
fit the calibrator on the same rows you then score:
```python
import selection as sel
from rating_masterscale import pd_to_grade, APPROVE_GRADES   # backend/ on sys.path
oof = sel.oof_predictions(df, df["<TARGET>"], SELECTED_COLS,
                          learner="woe_logistic", cv_folds=5, random_state=42)
pd_use = oof.clip(0.0003, 0.999)   # Basel PD floor/cap; assess calibration on these honest OOF PDs
```
Then compute, on `pd_use`: AUC/Gini, Expected Calibration Error, Hosmer–Lemeshow (report
g=10 and g=5), and the **per-grade realised-vs-expected backtest** (map PDs to grades via
`pd_to_grade`, compare each grade's realised default rate's Wilson 95 % CI to its expected
PD). For **fairness**, compute the adverse-impact ratio of the favourable-decision rate
(approve = grade in `APPROVE_GRADES`) across each **excluded** protected attribute, against
the four-fifths (0.80) bar; require a minimum cell of ~20, and where a group fails, run the
**true-risk interpretation step** (is the model accurate *within* each group?). AIR is
indicative — no institution cut-off. Flag any AIR that rests on tiny approve counts.

### 3.5 G5 — generate the deployment deliverables
Build an acceptance-cases spec (4 real applicants spanning the risk range *and both
outcomes*, plus 2 synthetic composites made from **observed** feature-value extremes to
exercise the PD floor and cap — never invented values), then:
```powershell
.\venv310\Scripts\python.exe ml_models\score_acceptance_cases.py `
  --cases "paper analysis\draft one\acceptance_cases\<name>.json" `
  --out   "paper analysis\draft one\SAMPLE_RUNS_<NAME>.md"
```
Also write `AEGIS_<NAME>_CUTOFF_POLICY.md` (rating-grade tiers; state the accept/refer/
decline threshold as an exogenous institution input — do **not** invent one).

### 3.6 GF — run the deterministic Go/No-Go engine (do not hand-rule it)
Assemble the §8 regulatory checklist (R1–R14; R1–R9 are must-haves) with each row
`SATISFIED / PARTIAL / GAP`, then:
```python
verdict = ag.gf_engine(gate_states, checklist, residual_within_appetite=True)
# GO  |  GO-WITH-CONDITIONS (lists the PARTIAL items)  |  NO-GO (names the blocker + gate)
```
Seal GF into the chain the same way. The engine never upgrades a must-have GAP.

### 3.7 Write the run records
Produce `SHARP_<NAME>.md` and `AEGIS_RUN_<NAME>.md` (gate-by-gate decision table + the
full chain), place the cut-off policy and acceptance pack, and add/commit the
`acceptance_cases/<name>.json`. If this run supersedes an earlier one, **move** (never
delete) the old records to `paper analysis/draft one/archive/…` and note it in
`archive/PROVENANCE.md`.

---

## 4. Datasets available in the repo (`data/ml_lab/datasets/`)

All are tracked, so they arrive with the clone. Target columns and positive labels are in
each dataset's own run record / onboarding map; confirm before use rather than guessing.

| File | What it is | Fully-worked reference in repo |
|---|---|---|
| `south_german_credit_en.csv` | South German Credit (Grömping 2019, corrected German), 1,000×20 | `AEGIS_RUN_GERMAN.md` |
| `sba_loans.csv` | US SBA guaranteed loans, 2,102×35 | `AEGIS_RUN_SBA.md` |
| `hmeq.csv` | Home-equity (HMEQ) | `sharp_runs/sharp_20261011_hmeq.json` |
| `heloc.csv` | FICO HELOC panel | — |
| `credit_risk_dataset.csv` | "Credit Risk" (CREDITRISK) | — |
| `GMSC.csv` | Give-Me-Some-Credit | — |
| `Taiwan_UCI_Credit_Card.csv` | Taiwan default-of-credit-card | — |
| `LC_nogeo.csv` | LendingClub extract (geography removed) | — |
| `loan_data.csv` | LendingClub-style loan set (LOAN) | — |
| `MSME_Credit_Data.csv` | MSME portfolio (a NO-GO: sufficiency) | — |
| `TH02.csv` | Thai retail credit | — |
| `PAK.csv` | PAKDD-2009 Brazilian retail credit (a NO-GO) | — |
| `polish_bankruptcy_{1..5}year.csv` | Polish bankruptcy, 1–5 year horizons (descriptive column names per `polish_bankruptcy.dictionary.json`; Year-1 governed run used the original `AttrN` labels — original kept at `archive/polish_bankruptcy_1year_Attr.csv`) | Year 1 governed (`AEGIS_RUN_POLISH1.md`); Years 2–5 not yet run |
| `south_german_credit.csv` | raw German-named source of the `_en` file | — |
| `archive/german_clean.csv`, `archive/german_credit_record.csv` | superseded Statlog German | archived |

**Adding a new dataset:** drop the CSV in `data/ml_lab/datasets/`, confirm its target
column and positive class with the user, and run Phase 3 on it. For the banking platform
(not required here) new portfolios are onboarded via `operations/scripts/onboard_*.py`.

---

## 5. The fixed (pre-registered) configuration — identical for every dataset

Never change these per run (P8). They are set in `METHODOLOGY.md` / `hyperparameters.json`:

- Primary learner **WOE-logistic** (XGBoost only as a robustness learner); value function
  cross-validated AUC; correlated columns grouped at |ρ| = 0.7.
- Stage 1: keep features with **IV ≥ 0.02** under monotonic WOE binning.
- Stage 2: ≥ 10 shadow players, 95th-percentile shadow bar, confirmation frequency ≥ 0.80;
  **exact** Shapley when players (incl. shadows) ≤ 15, **sampled** otherwise.
- Stage 3 selection rule: the **smallest k** at which DeLong p ≥ 0.05 **and** relative
  Gini loss ≤ 5 % both hold.
- Stage 4: isotonic calibration; PD floor 0.03 %, cap 99.9 %.
- Random seed **42** throughout; stratified 80/20 split taken *before* any resampling;
  parsimony scored on stratified 5-fold out-of-fold predictions (so DeLong is valid).

---

## 6. What a finished run leaves behind

In `paper analysis/draft one/`: `SHARP_<NAME>.md`, `AEGIS_RUN_<NAME>.md`,
`AEGIS_<NAME>_CUTOFF_POLICY.md`, `SAMPLE_RUNS_<NAME>.md`,
`acceptance_cases/<name>.json`, and (if applicable) a `PROVENANCE.md` note. The hash chain
in the run record lets anyone re-run and confirm the same gates and digests
deterministically. The gate option sets and the GF verdict all come from
`ml_models/aegis_gates.py`, so two people running the same inputs get the same governance
output — that is the point.

---

*This guide reproduces the authors' own procedure. If any step here conflicts with
`METHODOLOGY.md` or `AEGIS_GOVERNANCE.md`, those documents win — tell the user about the
conflict rather than guessing.*
