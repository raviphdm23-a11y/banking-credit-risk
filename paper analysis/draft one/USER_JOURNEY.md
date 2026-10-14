# USER JOURNEY — running a new dataset through SHARP + AEGIS, end to end

The complete, **required** process for taking a new credit dataset from a raw CSV to an approved, governed,
**decisioning** model with an applicant reason report. Every step is mandatory — there are no optional stages.
Run it interactively with Claude Code; you are the human signer, Claude is the machine.

**Deliverables at the end** (per dataset `<NAME>`):
1. `SHARP_<NAME>.md` — the analytical record (Stages 0–4, every figure traceable)
2. `AEGIS_RUN_<NAME>.md` — the hash-chained gate decision log (G0–GF) + acceptance demonstration
3. `AEGIS_<NAME>_CUTOFF_POLICY.md` — the decisioning note (rating-grade risk tiers; the accept/refer/decline threshold is an institution input, **not derived and not priced here**)
4. Scored sample candidates: PD, grade, governed decision, reason-code reports (the lending decision applies the institution's own threshold)

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

## Step 4 — Decisioning note [REQUIRED — G5 deliverable, BEFORE Go/No-Go]
> "Write the decisioning note for this product as `AEGIS_<NAME>_CUTOFF_POLICY.md`."

Record how the model's outputs **feed** a decision: **calibrated PD → rating grade (risk tier)**, and that the
**accept / refer / decline threshold is an institution risk-appetite input — exogenous to this methodology,
not derived here, and NOT priced** (see `AEGIS_HMEQ_CUTOFF_POLICY.md` as the template). **Do not invent PD
cutoffs, LGD, margins or interest rates — they have no research basis** (an earlier version did; it was
removed). The grade-scale band edges need a citation (e.g., agency idealised default rates) or must be stated
as the institution's internal scale.

## Step 5 — Acceptance demonstration: score candidates + reason reports [REQUIRED — G5 deliverable, BEFORE Go/No-Go]
> "Build the approved scorer and score the fixed 6-case committee set. For each give: calibrated PD (floored),
> rating grade (risk tier), the governed completeness decision, and the adverse-action **reason codes**. Do not
> invent a price or a cutoff."

**Fixed case-composition standard (6 cases per pack — identical across every dataset, for committee
comparability):**
- **4 REAL applicants** drawn from the dataset, each with its **actual outcome (default / repaid) shown** next to
  the predicted PD. They are composed to span the risk range *and* include both outcomes:
  `R1-low-repaid` (low PD, repaid), `R2-mid-repaid` (mid PD, repaid), `R3-mid-default` (mid PD, defaulted),
  `R4-high-default` (high PD, defaulted). This surfaces the honest "messy middle" where a repayer and a defaulter
  can share a near-identical PD.
- **2 SYNTHETIC composites**, clearly labelled, with **no actual outcome**: `SYN-best` (each feature set to its
  lowest-risk *observed* value → checks the 0.03% PD floor) and `SYN-worst` (each feature at its highest-risk
  *observed* value → stress check that nothing breaks). Each synthetic value is a real observed value; only the
  **combination** is constructed — never an invented number.

The real-case actuals and the synthetic extremes are both **data-derived** (no fabricated inputs); the pack's
`case_meta` block records each case's `kind` (real/synthetic) and `actual` (0/1/null). The scorer renders the
`Type` and `Actual outcome` columns from it.

Claude produces, per candidate, the applicant report you need — e.g.:
> *Customer X — PD 16.9% · grade CCC (risk tier) · governed decision SCORE. Principal reasons: ① one
> delinquent credit line, ② short job tenure, ③ debt-to-income above safe band. (Accept/decline applies the
> institution's own PD threshold — not derived here.)*

This is both the **demonstration** and a **sanity test** of the whole pipeline, and the model's **use-test +
transparency evidence** (R2 / EU AI Act Art 13 / ECOA).

**It is persisted as a committee-facing, reproducible artifact — not a one-off:**
- the candidate input profiles are saved to `acceptance_cases/<name>.json` (selected columns, governance
  config, product policy, and each candidate's feature values);
- the pack is generated by `ml_models/score_acceptance_cases.py --cases acceptance_cases/<name>.json --out
  SAMPLE_RUNS_<NAME>.md`, producing **`SAMPLE_RUNS_<NAME>.md`** — a per-candidate showcase (inputs → governed
  decision → raw/calibrated PD → grade → decision + rate → full exact reason-code table → principal reasons);
- **the Model Approval Committee reviews `SAMPLE_RUNS_<NAME>.md` at GF** to see how the model behaves on
  concrete cases before ruling. Because the inputs are saved, anyone can re-run and reproduce the pack.

## Step 6 — GF Final Go/No-Go [LAST — with full visibility]
> "Now run the Go/No-Go engine and I'll rule as MAC chair."

GF synthesises everything — the §8 regulatory checklist, the signed gates, **the per-grade backtest (is the
model honest?), the cutoff policy and the `SAMPLE_RUNS_<NAME>.md` pack (the committee reads the sample runs to
see the decisions and reasons on concrete cases)** — and you rule **GO / GO-WITH-CONDITIONS / NO-GO**. Because the backtest and demo are already done, a failing backtest
or a misbehaving demo *becomes* a NO-GO or a condition here — which is exactly why they precede GF.

---

## Done — acceptance checklist

A dataset's end-to-end run is complete only when **all** of these exist and are consistent:

- [ ] `SHARP_<NAME>.md` — Stages 0–4 recorded, figures traceable
- [ ] **Per-grade calibration backtest** (G4) — realised vs expected by grade; small-data caveat/MoC noted
- [ ] `AEGIS_<NAME>_CUTOFF_POLICY.md` — decisioning note (grades; accept/decline = institution threshold; **no pricing, no invented cutoffs**)
- [ ] Acceptance demonstration — `acceptance_cases/<name>.json` (saved inputs + `case_meta`) + `SAMPLE_RUNS_<NAME>.md` (committee pack: **fixed 6-case standard — 4 real w/ actual outcome + 2 synthetic**, decisions + full reason-code reports), reproducible via `score_acceptance_cases.py`
- [ ] `AEGIS_RUN_<NAME>.md` — G0–G5 signed, **then GF ruled last** with visibility of the backtest + policy + demo; hash chain intact
- [ ] Open GF conditions listed, each with its discharge point

Standing rules apply throughout (see README working agreements): no extrapolation; calibration and the 0.03%
PD floor are standard; gates decide governance not analytics (P8); verify regulatory thresholds against
primary sources.
