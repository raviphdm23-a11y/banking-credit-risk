# AEGIS run log — SBA (US Small Business Administration loans)

**Framework:** AEGIS v1.0 (`AEGIS_GOVERNANCE.md`) · **Engine:** SHARP v3.1 (`v3_pipeline.run_pipeline`, fixed config, `random_state=42`)
**Dataset:** `data/ml_lab/datasets/sba_loans.csv` — 2,102 rows, 35 columns (CA real-estate subset of the national SBA set).
Public: OpenML #43539 (CC0). Paper: Li, Mickel & Taylor (2018), *J. Statistics Education* 26(1).
**Started:** 2026-10-19 · **Human signer:** Ravi · **Materiality tier:** MEDIUM · **Record:** `SHARP_SBA.md`
**Twelfth governed run — the DATA-INTEGRITY showcase for the new G0 exclusion taxonomy (METHODOLOGY §3.7):
perfect/near-perfect leakage, identifiers, constants and junk all caught by computable precondition; plus the
strongest discrimination in the corpus and a geographic true-risk-driven disparate-impact case.**

> **Order (standard):** gates G0→G5, with the per-grade calibration backtest inside G4; then the decisioning note
> and acceptance demonstration; then **GF last** with full visibility.

## Decision log (hash-chained)

| # | Gate | Chosen option | Signer / role | Rationale | prev_hash[:8] | entry_hash[:8] |
|---|---|---|---|---|---|---|
| — | GENESIS | — | — | run initialised | — | GEN-SBA0 |
| 1 | G0 | **A — Exclude leakage/identifiers/constants/junk; 19-feature pool** (MEDIUM) | Ravi / Data Steward | leakage trio excluded by computable precondition (MIS_Status 100%, ChgOffPrinGr/ChgOffDate 99.5% target agreement); identifiers Selected/LoanNr/Name/Zip; constants State(CA)/BalanceGross(0); junk xx + raw dates; retain-flag geography City/BankState/Bank for G4 | GEN-SBA0 | 81defb1b |
| 2 | G1 | **A — Accept screen; advance 16 of 19** | Ravi / Model Validator | drop NewExist(IV0.020)/LowDoc(0.006)/New(0.001); Term/daysterm dominant IV 2.89 (genuine SBA term effect, duplicates); ApprovalFY vintage flagged; EPV 62, Riley req 338 vs 2,102 | 81defb1b | b90e6ac8 |
| 3 | G2 | **A — Accept attribution; all 12 players confirmed** | Ravi / Model Validator | all 12 confirmed freq 1.00; shadow bar 0.00292; sampled 18,485 fits; loan-term cluster grp[RealEstate+Term+daysterm] dominates 57× bar; amounts grouped; ApprovalFY #2; weakest Recession 2.2× | b90e6ac8 | 35243681 |
| 4 | G3 | **A — Ratify k=7 benchmark** | Ravi / Model Validator | k=7 (11 cols) Gini 0.859 DeLong p 0.536 rel loss 0.17%; strongest Gini in corpus (loan-term driven); SBA-VINTAGE sensitivity minor (−1.5% held-out), no circularity | 35243681 | dafbf0b1 |
| 5 | G4 | **A — Approve** (dual) | Ravi / Risk Officer + Validator | test AUC 0.931 Gini 0.862; per-grade 7/7 within CI, ECE 0.040; HL rejects p=0.018 (bimodal PDs → SBA-CAL); geographic AIR 0.41 by BankState true-risk-driven (SBA-GEO); no personal protected attrs | dafbf0b1 | 82d391f4 |
| 6 | G5 | **A — Standard config** | Ravi / Model Owner | mandatory Term+GrAppv; refer; no adverse floor; exact WOE reason codes; PD floor 0.03%; drift+geo+calibration monitoring; 6-case pack + cutoff note | 82d391f4 | 18be815d |
| 7 | **GF** | **A — GO-WITH-CONDITIONS** | Ravi / MAC Chair (CRO) | strongest discrimination in corpus from genuine origination signal; calibration usable grade-by-grade (HL caveat disclosed); geographic disparity true-risk-driven & indicative; MEDIUM reference benchmark, not production-IRB | 18be815d | b9d932b6 |

**Chain:** GEN-SBA0 → 81defb1b → b90e6ac8 → 35243681 → dafbf0b1 → 82d391f4 → 18be815d → **b9d932b6**. ✅ **SEALED**

---

## G0 — Data & Scope Adequacy · ✅ DECIDED — **A** · entry_hash `81defb1b`
**Signer:** Ravi (Data Steward) · 2026-10-19 · tier **MEDIUM**. The G0 exclusion taxonomy (METHODOLOGY §3.7)
applied by computable precondition and recorded with its measured value:
- **Leakage (post-outcome):** `MIS_Status` (CHGOFF/PIF) = **100%** identical to Default; `ChgOffPrinGr>0` and
  `ChgOffDate` present ⟺ Default **99.5%** → excluded.
- **Identifiers / PII:** `LoanNr_ChkDgt` (2102/2102 unique key), `Name`, `Zip`, `Selected` → excluded.
- **Constant:** `State` (all 'CA'), `BalanceGross` (all 0) → excluded.
- **Junk / raw dates:** `xx` (undocumented), `ApprovalDate`, `DisbursementDate` → excluded.
- **Retain-and-flag (geography/institution proxy → G4):** `City`, `BankState`, `Bank`.
**Eligible pool (19, application-time).** SBA is business lending → **no personal protected attributes**; fairness
is geographic/institutional only.

## G1 — Univariate Screening & Data Sufficiency · ✅ DECIDED — **A** · entry_hash `b90e6ac8`
**Signer:** Ravi (Model Validator). Advance **16 of 19**; drop `NewExist`/`LowDoc`/`New`. `Term`/`daysterm` dominate
(IV 2.89 — the genuine SBA loan-term effect; identical IV → duplicates). `ApprovalFY` vintage flagged. **Sufficiency
(v3.1):** EPV ≈ 62; Riley minimum-N **338** vs **2,102**.

## G2 — Importance Attribution · ✅ DECIDED — **A** · entry_hash `35243681`
**Signer:** Ravi (Model Validator). 16 screened features → **12 players** (grouping collapsed the loan-term cluster
grp[RealEstate+Term+daysterm] and the amounts cluster). All **12 confirmed** at freq 1.00; shadow bar 0.00292;
sampled estimator (P8), 18,485 fits. Loan-term cluster dominates (57× the bar); weakest (`Recession`) 2.2×.

## G3 — Parsimony Selection · ✅ DECIDED — **A** · entry_hash `dafbf0b1`
**Signer:** Ravi (Model Validator). Ratify pre-registered **k=7** → 11 columns (`RealEstate, Term, daysterm,
ApprovalFY, Portion, DisbursementGross, GrAppv, SBA_Appv, FranchiseCode, RevLineCr, NAICS`); **Gini 0.859**,
DeLong p 0.536, rel loss 0.17% (k≤6 fail: k=5 p=0.048, k=6 p=0.020). **Strongest Gini in the corpus**, legitimately
(loan term is almost deterministic for SBA). **SBA-VINTAGE sensitivity:** without `ApprovalFY`, held-out Gini 0.849
vs 0.862 — ΔGini 0.013 (**−1.5%**), so no circularity/availability concern (clean contrast to CREDITRISK).

## G4 — Calibration (+ per-grade backtest) & Fairness · ✅ DECIDED — **A** (dual) · entry_hash `82d391f4`
**Signers:** Ravi (Risk Officer + Validator). Held-out 80/20 (seed 42), test n=421. **Discrimination:** AUC **0.931**
/ Gini **0.862**. **Calibration:** **7/7 populated grades within Wilson CI** (full AAA→D), **ECE 0.040**; **HL rejects
(χ²=13.66, df=5, p=0.018)** — the PD distribution is strongly **bimodal** (long real-estate loans near 0, short loans
near 0.83), which collapses the HL bins; calibration is adequate grade-by-grade → **SBA-CAL** (monitor). **Fairness
(geographic; `BankState` excluded):** approve-rate AIR **0.41** (< four-fifths), **true-risk-driven** — approve rates
track actual default rates by state (CA 0.169 default → 0.378 approve; VA 0.677 → 0.226). Indicative only (business
lending; no personal protected attributes) → **SBA-GEO**. Carry SBA-VINTAGE + SBA-CAL + SBA-GEO.

## G5 — Deployment Governance & Deliverables · ✅ DECIDED — **A** · entry_hash `18be815d`
**Signer:** Ravi (Model Owner). Mandatory = `Term`, `GrAppv`; `incomplete_policy='refer'`; no adverse floor; exact
WOE reason codes; PD floor 0.03% / cap 99.9%; drift + geographic-disparity + calibration monitoring. **Deliverables:**
`AEGIS_SBA_CUTOFF_POLICY.md`; `acceptance_cases/sba.json` + `SAMPLE_RUNS_SBA.md` (6 cases — PDs SBA-R1 0.03%/AAA →
SBA-R2 31.8% → SBA-R3 49.0% → SBA-R4 95.9%/D; floor binds).

## GF — Final verdict · ✅ SEALED — **A (GO-WITH-CONDITIONS)** · entry_hash `b9d932b6` · prev `18be815d`
**MAC Chair:** Ravi (CRO) · 2026-10-19. The SBA 7-player WOE-logistic model is **approved as a MEDIUM-tier reference
benchmark, not production-IRB**, ruled after the G4 backtest and G5 deliverables were complete and visible. It is the
corpus's data-integrity showcase for the computable G0 exclusion taxonomy, the strongest-discriminating run (genuine
loan-term signal), with calibration usable grade-by-grade and a true-risk-driven geographic disparity disclosed.

### Open conditions register
| ID | Condition | Discharge before |
|---|---|---|
| SBA-VINTAGE | `ApprovalFY` is a vintage/time proxy (−1.5% if removed; no circularity) | out-of-period use |
| SBA-CAL | HL rejects on bimodal PDs; per-grade backtest passes 7/7 — monitor | production use |
| SBA-GEO | Geographic AIR 0.41 by `BankState` — true-risk-driven, indicative | scoring real customers |
| SBA-USE | Use test | real-decision use |

**Run status: COMPLETE (G0 → GF sealed).** No parameter re-opened at any gate (P8); every figure traces to
`SHARP_SBA.md`, `g4_sba`, and the recorded dataset. **12th governed run.**
