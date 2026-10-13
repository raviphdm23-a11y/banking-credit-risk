# USER JOURNEY — running a new dataset through SHARP + AEGIS, end to end

The complete, **required** process for taking a new credit dataset from a raw CSV to an approved, governed,
**decisioning** model with an applicant reason report. Every step is mandatory — there are no optional stages.
Run it interactively with Claude Code; you are the human signer, Claude is the machine.

**Deliverables at the end** (per dataset `<NAME>`):
1. `SHARP_<NAME>.md` — the analytical record (Stages 0–4, every figure traceable)
2. `AEGIS_RUN_<NAME>.md` — the hash-chained gate decision log (G0–GF) + acceptance demonstration
3. `AEGIS_<NAME>_CUTOFF_POLICY.md` — the fixed cutoff / rating-grade / risk-based-pricing policy
4. Scored sample candidates with **approve/decline decisions and reason-code reports**

---

## Step 0 — Setup (once per machine; Windows)

```powershell
git clone https://github.com/raviphdm23-a11y/banking-credit-risk.git
cd banking-credit-risk
python -m venv venv310 ; .\venv310\Scripts\python.exe -m pip install -r requirements.txt
```
Drop your CSV into `data\ml_lab\datasets\`. Know **(a)** the label column and **(b)** which value = *default*.

## Step 1 — Open Claude and orient it
```powershell
claude
```
> "Read `paper analysis/draft one/METHODOLOGY.md`, `AEGIS_GOVERNANCE.md`, `USER_JOURNEY.md`, and the README
> working agreements. We're running the full SHARP + AEGIS end-to-end process on a new dataset."

## Step 2 — Run SHARP (analytical engine)
> "Run SHARP v3 on `data/ml_lab/datasets/<file>.csv` (target = `<col>`, positive class = `<value>` = default).
> Record it as `SHARP_<NAME>.md`."

Claude runs `v3_pipeline.run_pipeline(...)`, writes the record (Stages 0–4). Review the selected features,
discrimination (Gini/AUC) and calibration.

> **Ordering (important):** the final **Go/No-Go (GF) is the LAST step**, ruled only *after* the per-grade
> calibration backtest (Step 3/G4), the cutoff policy (Step 4) and the acceptance demonstration (Step 5) are
> complete. Go/No-Go must have visibility of whether the PDs are honest and the decisions sensible — you do
> not approve first and check later. (Our first three runs did GF before the policy/demo; that ordering is
> corrected here.)

## Step 3 — Walk the AEGIS gates G0–G5 (governance; you decide, Claude recommends)
> "Take me through the AEGIS gates G0 to G5 — I'll sign each. Hold the final Go/No-Go for the end."

Each gate: machine recommendation + evidence + 2–4 options → you pick one with a one-line rationale → logged
to `AEGIS_RUN_<NAME>.md` (hash-chained).
- **G0** Data & scope — *you confirm protected/prohibited attributes* and the materiality tier.
- **G1** Screening · **G2** Attribution · **G3** Selection (ratify the feature set).
- **G4** Calibration & **Fairness** — disparate impact (if protected attributes exist) **AND the required
  per-grade realised-vs-expected calibration backtest** (CRE36.122–123): prove the PDs are honest grade by
  grade ("the model said 17%, did ~17% actually default?"). On small data, flag the wide confidence intervals
  and set a Margin of Conservatism — don't pretend to precision you don't have.
- **G5** Deployment governance — missing-value controls + reason-code format (PD floor automatic). **G5
  produces the two required deliverables in Steps 4–5.**

## Step 4 — Cutoff & grade policy [REQUIRED — G5 deliverable, BEFORE Go/No-Go]
> "Draft the cutoff / grade / risk-based-pricing policy for this product as `AEGIS_<NAME>_CUTOFF_POLICY.md`."

A **required risk-appetite governance decision**, not analytics: fixed **absolute PD cutoffs** →
approve / refer / decline bands, mapped to rating grades, with risk-based pricing. Cutoffs are documented and
**retrain-stable** (see `AEGIS_HMEQ_CUTOFF_POLICY.md` as the template). Without this, the model outputs a PD
but makes no decision — incomplete.

## Step 5 — Acceptance demonstration: score candidates + reason reports [REQUIRED — G5 deliverable, BEFORE Go/No-Go]
> "Build the approved scorer and score these representative candidates: [paste 3–5 applicant profiles, or ask
> Claude to pick a strong / borderline / weak example — include a deliberately extreme one to check nothing
> breaks]. For each give: calibrated PD (floored), rating grade, the policy decision (approve/refer/decline +
> indicative rate), and the adverse-action **reason codes**."

Claude produces, per candidate, the applicant report you need — e.g.:
> *Customer X — PD 16.9% (grade CCC) — APPROVE (risk-based pricing, 14.5%). Principal reasons: ① one
> delinquent credit line, ② short job tenure, ③ debt-to-income above safe band.*

This is both the **demonstration** and a **sanity test** of the whole pipeline, and the model's **use-test +
transparency evidence** (R2 / EU AI Act Art 13 / ECOA). Appended to `AEGIS_RUN_<NAME>.md`.

## Step 6 — GF Final Go/No-Go [LAST — with full visibility]
> "Now run the Go/No-Go engine and I'll rule as MAC chair."

GF synthesises everything — the §8 regulatory checklist, the signed gates, **the per-grade backtest (is the
model honest?), the cutoff policy and the acceptance demonstration (are the decisions sensible?)** — and you
rule **GO / GO-WITH-CONDITIONS / NO-GO**. Because the backtest and demo are already done, a failing backtest
or a misbehaving demo *becomes* a NO-GO or a condition here — which is exactly why they precede GF.

---

## Done — acceptance checklist

A dataset's end-to-end run is complete only when **all** of these exist and are consistent:

- [ ] `SHARP_<NAME>.md` — Stages 0–4 recorded, figures traceable
- [ ] **Per-grade calibration backtest** (G4) — realised vs expected by grade; small-data caveat/MoC noted
- [ ] `AEGIS_<NAME>_CUTOFF_POLICY.md` — fixed cutoffs + grades + pricing
- [ ] Acceptance demonstration — ≥3 candidates scored with decisions **and** reason-code reports
- [ ] `AEGIS_RUN_<NAME>.md` — G0–G5 signed, **then GF ruled last** with visibility of the backtest + policy + demo; hash chain intact
- [ ] Open GF conditions listed, each with its discharge point

Standing rules apply throughout (see README working agreements): no extrapolation; calibration and the 0.03%
PD floor are standard; gates decide governance not analytics (P8); verify regulatory thresholds against
primary sources.
