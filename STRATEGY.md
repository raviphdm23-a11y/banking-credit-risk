# Axis Bank (BANK010) — Balance Sheet Strategy Playbook
**Simulation Reference Document · Updated: July 2020**

---

## 1. Where We Stand Today (July 2020 Baseline)

| Metric | Value | Status |
|---|---|---|
| Total Assets | Rs 1,081 Cr | — |
| Advances (net) | Rs 789 Cr | Growing |
| Deposits | Rs 937 Cr | Growing |
| Capital (Eq + Reserves) | Rs 986 Cr | Stable |
| CAR | 16.7% | Well above 11.5% minimum |
| CET1 | 16.1% | Well above 8.0% minimum |
| LCR | ~255% | Excess liquidity |
| GNPA | 36 loans / Rs 10.82 Cr | ~1.4% of advances |
| Moratorium | 1,339 loans / Rs 231.7 Cr (31%) | Deadline: Aug 31 |
| PAT (July) | Rs −4.51 Cr | 4th consecutive loss month |
| COVID provision cycle | **COMPLETE** (4 of 4 months done) | Aug onwards normalises |

**The single most important upcoming event:** Moratorium ends August 31, 2020.
All strategy decisions flow from how that cliff resolves.

---

## 2. Six Strategic Initiatives

| # | Initiative | Type | Urgency | Expected Impact |
|---|---|---|---|---|
| S1 | Moratorium stratification + OTR | Defensive | **Critical — Aug** | Prevents cliff NPA shock |
| S2 | Voluntary floating provision buffer | Defensive | **Critical — Aug** | Absorbs Q3 NPA provisions |
| S3 | TLTRO 2.0 tap (Rs 100 Cr at 4%) | Offensive | Medium — Oct | +Rs 5 Cr NII/year |
| S4 | CASA campaign targeting ECLGS borrowers | Offensive | Low — Dec | Lower deposit cost |
| S5 | SDL rotation within investment portfolio | Optimisation | Low — Nov | +Rs 35–40 L/year |
| S6 | AT1 bond shelf prospectus (contingency) | Capital | Contingency — Jan | Ready if CAR < 14% |

---

## 3. Phased Execution Roadmap

### Phase 1 — Defensive (August–September 2020)
> **Objective:** Survive the moratorium cliff with minimal NPA formation.

**August 2020**
- [ ] Stratify all 1,339 moratorium loans into Green / Amber / Red
- [ ] Build Rs 3 Cr voluntary floating provision in other_liabilities
- [ ] File OTR applications for all Amber accounts before Aug 31
- [ ] Hold all offensive initiatives — no TLTRO, no CASA campaign

**September 2020**
- [ ] Moratorium ends: observe which accounts resume EMIs
- [ ] Execute OTR restructuring for Amber cohort (extend tenure / reduce EMI)
- [ ] Classify Red accounts as Sub-Standard; provision at 15%
- [ ] **Decision gate:** Read the September NPA formation number before any offensive action

---

### Phase 2 — Stabilise (October 2020)
> **Objective:** First offensive move once cliff risk is quantified.

**October 2020**
- [ ] Tap TLTRO 2.0: borrow Rs 100 Cr from RBI at 4.00% for 3 years
- [ ] Deploy TLTRO funds into ECLGS 2.0 / MSME loans (9.00% yield, guaranteed)
- [ ] Monitor OTR restructured accounts for early re-default signals
- [ ] CASA campaign design and pilot (targeting ECLGS borrowers)

---

### Phase 3 — Optimise (November 2020 – January 2021)
> **Objective:** Structural margin improvement; capital readiness.

**November 2020**
- [ ] SDL rotation: swap Rs 50 Cr G-Secs → State Development Loans (+60–75 bps yield)
- [ ] Review blended deposit cost — accelerate TD repricing if CASA ratio > 62%

**December 2020**
- [ ] CASA campaign launch: zero-balance current accounts for all ECLGS borrowers
- [ ] Target CASA ratio: 65% (from current ~60%)
- [ ] Q3 FY2021 results review — publish internal performance scorecard

**January 2021**
- [ ] AT1 bond decision: raise if CAR has fallen below 14% or NPA > 5%
- [ ] Full 6-month strategy retrospective — update this document

---

## 4. Monthly Decision Gate — Run This Every Month

Before advancing the simulation clock, check these five numbers.
**If any metric is Red, pause offensive initiatives and add defensive provisions.**

| Metric | Green ✅ | Amber ⚠️ | Red ❌ |
|---|---|---|---|
| GNPA ratio | < 2% | 2–4% | > 4% |
| Monthly PAT | Positive | −Rs 1 to −Rs 3 Cr | < −Rs 3 Cr |
| CAR | > 15% | 13–15% | < 13% |
| Moratorium residual | < 15% of book | 15–25% | > 25% |
| New disbursals (monthly) | > 25 loans | 15–25 loans | < 15 loans |

**Decision rules:**
- All five Green → proceed with scheduled offensive initiative
- One or two Amber → proceed with caution; reduce offensive scale by 50%
- Any Red → pause Phase 2/3 initiatives; revert to defensive posture

---

## 5. Monthly Onboarding Checklist

*Run this checklist before writing each advance script.*

### A. Read the Prior Month
- [ ] Open `simulation_clock.json` — confirm current `sim_date` and `sim_period`
- [ ] Run `python operations/scripts/check_sync.py` — all checks must pass
- [ ] Open `http://localhost:5000/analytics/` — review all 6 charts
- [ ] Note: PAT trend, NPA count delta, moratorium residual, CAR/LCR

### B. Apply the Decision Gate
- [ ] Score all five metrics (Green / Amber / Red) from the analytics dashboard
- [ ] Determine which phase we are in (Defensive / Stabilise / Optimise)
- [ ] Confirm which initiatives are scheduled this month (Section 3 above)
- [ ] Check if any Red metric forces a pause

### C. Define the Month's Real-World Context
Before coding, note down:
- RBI policy actions (repo rate changes, new schemes announced)
- Regulatory changes (moratorium extensions, OTR window, CRR/SLR changes)
- Macroeconomic events (GDP release, lockdown/unlock announcements, GST data)
- Sector-specific signals (auto volumes, ECLGS sanctions data, sowing season)

### D. Calibrate New Disbursals
Each month, set the disbursal volume based on the Decision Gate score:
- All Green: 30–35 new loans
- Mixed Green/Amber: 20–25 new loans
- Any Red: 10–15 new loans (essential/guaranteed only)

Loan mix guidance by phase:

| Phase | Preferred types | Avoid |
|---|---|---|
| Defensive (Aug–Sep) | ECLGS (guaranteed), Agri/KCC | Unsecured personal, new Business Loans |
| Stabilise (Oct) | ECLGS, Home Loan, Vehicle | Unsecured personal |
| Optimise (Nov+) | All types; tilt toward secured | Nothing excluded; manage mix |

### E. Provision Calibration
Each month, provisions have three components:

| Component | Formula | Notes |
|---|---|---|
| Normal portfolio provision | Advances × 0.5% ÷ 12 | Always applies |
| Fresh NPA provision | New Sub-Standard outstanding × 15% | Applies when new NPAs form |
| Doubtful-1 top-up | New Doubtful-1 outstanding × 10% | Incremental above 15% already held |
| COVID floating provision | See Section 3 — August only | One-time build |
| OTR restructured provision | Restructured outstanding × 5% | From September onwards |

### F. After Running the Advance Script
- [ ] Verify balance sheet balances: `Assets == Liabilities + Capital` (diff < Rs 1)
- [ ] Confirm `sim_date` and `sim_period` in `simulation_clock.json`
- [ ] Restart Flask (SIM_DATE loads at import time)
- [ ] Reload `/analytics/` — new period should appear in all charts
- [ ] Run `check_sync.py` — all checks pass
- [ ] Commit and push

---

## 6. Key Thresholds and Triggers

### Regulatory Floors (RBI, COVID-adjusted)
| Ratio | Normal minimum | COVID relief | Our current |
|---|---|---|---|
| CAR | 11.5% | 11.5% | 16.7% |
| CET1 | 8.0% | 8.0% | 16.1% |
| LCR | 100% | 80% (relief) | ~255% |
| NSFR | 100% | — | ~174% |
| CRR | 4.5% | 3.0% (relief) | 3.0% |
| SLR | 18.0% | — | 20.4% |

### Management Action Triggers
| Trigger | Action |
|---|---|
| CAR falls below 14% | Begin AT1 bond preparation (S6) |
| GNPA crosses 3% | Pause all new unsecured disbursals |
| GNPA crosses 5% | Emergency ALCO — capital plan review |
| Monthly PAT < −Rs 8 Cr | Review provision strategy; check for one-off items |
| LCR falls below 150% | Pause TLTRO deployment; rebuild HQLA first |
| Moratorium residual > 25% in any month after Sep | Extend OTR window; rebuild floating provision |

---

## 7. Initiative Status Tracker

*Update this table each month as initiatives activate.*

| Initiative | Status | Activation Month | Impact Observed |
|---|---|---|---|
| S1 — Moratorium stratification | Pending | August 2020 | — |
| S2 — Voluntary provision buffer | Pending | August 2020 | — |
| S3 — TLTRO 2.0 tap | Pending | October 2020 | — |
| S4 — CASA campaign | Pending | December 2020 | — |
| S5 — SDL rotation | Pending | November 2020 | — |
| S6 — AT1 bond (contingency) | Pending | January 2021 (if needed) | — |

---

## 8. Simulation History Log

*One-line entry per month, updated as we advance the clock.*

| Month | Key Event | PAT (Rs Cr) | GNPA | Moratorium | New Loans |
|---|---|---|---|---|---|
| FY2019 | Base year | +16.90 | — | — | — |
| FY2020 | Pre-COVID baseline | +19.21 | — | — | — |
| APR2020 | COVID lockdown month 1; moratorium 30% | −4.66 | 10 | 30% | 5 |
| MAY2020 | Unlock 1.0; ECLGS launched; repo 4.00% | −6.18 | 20 | 35% | 20 |
| JUN2020 | Unlock 1.0 full; moratorium opt-outs begin | −4.73 | 28 | 33% | 25 |
| JUL2020 | Unlock 3.0; Kharif season; final COVID prov | −4.51 | 36 | 31% | 30 |
| AUG2020 | — | — | — | — | — |
| SEP2020 | — | — | — | — | — |
| OCT2020 | — | — | — | — | — |
| NOV2020 | — | — | — | — | — |
| DEC2020 | — | — | — | — | — |
| JAN2021 | — | — | — | — | — |

---

*This document should be reviewed and updated at the start of each monthly advance. If a strategic assumption changes (e.g., RBI extends moratorium, repo rate cuts resume), update Section 3 timeline accordingly.*
