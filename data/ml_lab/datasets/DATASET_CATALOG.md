# Sandbox Dataset Catalog

Reference for every CSV in this folder (`data/ml_lab/datasets/`) — one repository, one place to check what you have
and what's worth trying next.

**How this document was built:** every row/column/size/missing-value/positive-rate number below was computed
directly from the actual files on **2026-10-03** (not estimated). Every provenance claim (which paper, which
competition, which institution) was checked via web search on the same date and is marked accordingly:
- ✅ **Verified** — confirmed from a primary or clearly authoritative source (the dataset's own UCI/Kaggle page, the
  original paper, or equivalent).
- ⚠️ **Unverified** — a plausible identification I could not independently confirm. Treat as a lead, not a fact,
  until you check it yourself.
- Benchmark ("best known result") figures are given **only** where I actually found a real, sourced number — Kaggle
  leaderboards, a cited competition placing, or this project's own measured Sandbox runs. Where no verified number
  exists, that's stated plainly instead of guessing.

This folder is **gitignored** — not backed by version control. There is no recovery path if a file here is deleted
or corrupted; back up externally if that matters to you.

**Target-orientation audit (2026-10-03):** every `target` column was checked against its documented real-world
bad/default rate to confirm `1` consistently means the bad/default outcome, not the reverse. Two files had it
backwards and have been corrected in place (0↔1 flipped, nothing else changed) — see their entries below for the
verification details: `credit_approval_dataset.csv` and `TH02.csv`. Every other file with a true default/bad
target was checked and confirmed already correct (`target=1` = bad/default). The two `bank_marketing_*.csv` files
don't have a default target at all (`y` = whether the client subscribed to a term deposit) — not applicable.

---

## Quick-reference table

| File | Rows | Cols | Size | Missing | Positive rate |
|---|---:|---:|---:|---:|---:|
| `german_credit_record.csv` | 1,000 | 21 | 0.2 MB | 0% | 30.0% |
| `Australian_Credit.csv` | 690 | 15 | 0.03 MB | 0% | 55.5% |
| `credit_approval_dataset.csv` | 690 | 16 | 0.03 MB | 0.6% | 55.5% (fixed, was inverted) |
| `Taiwan_UCI_Credit_Card.csv` | 30,000 | 24 | 2.7 MB | 0% | 22.1% |
| `bank_marketing_dataset.csv` | 45,211 | 17 | 3.3 MB | 6.8% | 11.7% |
| `bank_marketing_additional_full.csv` | 41,188 | 21 | 5.8 MB | 0%* | 11.3% |
| `GMSC.csv` | 149,391 | 11 | 6.5 MB | 2.0% | 6.7% |
| `PAK.csv` | 50,000 | 52 | 7.1 MB | 12.3% | 26.1% |
| `TH02.csv` | 1,225 | 15 | 0.05 MB | 0% | 26.4% (fixed, was inverted) |
| `MSME_Credit_Data.csv` | 1,707 | 88 | 0.5 MB | 1.3% | 6.0% |
| `heloc.csv` | 10,459 | 24 | 0.7 MB | 0%** | 52.2% |
| `hmeq.csv` | 5,960 | 13 | 0.4 MB | 6.8% | 19.9% |
| `loan_data.csv` | 9,578 | 14 | 0.8 MB | 0% | 16.0% |
| `credit_risk_dataset.csv` | 32,581 | 17† | 1.9 MB | 30.1%† | 17.6% |
| `lending_club_q12019.csv` | 39,717 | 111 | 32.5 MB | 51.3%‡ | 14.2% |
| `mortgage.csv` | 622,489 | 23 | 67.2 MB | ~0% | no single target§ |

\* Uses coded category values (`"unknown"` etc.) rather than blank cells, so it doesn't register as missing by a
null-count check — not actually complete. \*\* Uses `-9`/`-7`/`-8` sentinel codes for missing, not blank cells —
**76% of rows (7,957/10,459) have at least one sentinel value**; see HELOC section. † Includes 5 entirely empty
junk columns inflating this figure — see Credit Risk section. ‡ Many LendingClub columns are legitimately
not-applicable per loan type, not all true missingness. § See Mortgage section — this is a panel dataset with a
competing-risks outcome, not a plain binary target.

---

## German Credit (`german_credit_record.csv`)

**Origin (✅ verified):** Hofmann, H. (1994). *Statlog (German Credit Data)*. UCI Machine Learning Repository,
donated by Universität Hamburg's Institut für Statistik und Ökonometrie. One of the oldest and most-cited credit
scoring benchmark datasets in the literature.

**Used in:** Hundreds of credit-scoring papers; a core dataset in the Lessmann, Baesens, Seow & Thomas (2015)
41-classifier benchmark study (*European Journal of Operational Research*).

**Profile:** 1,000 rows, 20 raw features (13 categorical, several containing "≥" symbols), 0% missing, 30.0%
positive (bad credit) rate.

**Best known result:** this project's own measured Sandbox baseline (honest split, no leakage, no tuning):
Logistic Regression **0.8014 AUC** (best of the five models tried) — see `paper analysis/draft one/RESULTS_LOG.md`
§1. Literature SOTA (e.g. the exact Lessmann et al. 2015 figure) was not independently retrieved this session —
the paper itself would need to be pulled to cite a precise number.

**Caveats:** this project's central finding (Sanity Ratio) treats this as a "boundary regime" dataset — 3 of 5
models pass the ρ≥2.0 threshold, contradicting the original paper's "impossibility regime" claim. See
`RESULTS_LOG.md` §2a.

---

## Australian Credit Approval (`Australian_Credit.csv`)

**Origin (✅ verified):** Submitted by Ross Quinlan to the UCI Machine Learning Repository (Statlog project),
1987. 690 instances, 14 attributes; all names/values anonymized to meaningless symbols for confidentiality.

**Used in:** The standard companion dataset to German Credit in nearly every major credit-scoring benchmark paper,
including Lessmann et al. (2015).

**Profile:** 690 rows, 14 raw features + target, 0% missing, 55.5% positive rate.

**Best known result:** not yet run through this project's Sandbox. Literature SOTA not independently verified
this session.

**Caveats:** none found. This is one of the cleanest datasets in this collection — no missing values, no obvious
outliers.

---

## Credit Approval / "crx" (`credit_approval_dataset.csv`)

**Origin (✅ verified):** Also submitted by Quinlan to UCI (`Credit Approval`, 690 instances, 15 attributes + class).
Used in Quinlan's own *"Simplifying Decision Trees"* (1987) and *C4.5: Programs for Machine Learning* (1992).
**Correction to an earlier claim in this project's conversation history:** I had called this the "Japanese Credit
Screening" dataset — that's wrong. Japanese Credit Screening is a separate, smaller (125-instance) UCI dataset.
This 690-instance file is simply "Credit Approval."

**Used in:** Decision-tree and credit-scoring literature referencing Quinlan's C4.5 work; frequently paired with
Australian Credit as a second small anonymized benchmark.

**Profile:** 690 rows, 15 raw features + target, 0.6% missing (37 rows have at least one missing value per the
original UCI documentation), 55.5% positive rate.

**Target orientation fixed (2026-10-03):** this file's `target` column was inverted — `1` meant "approved" (the
original "+" class, 307 instances), while `Australian_Credit.csv` (the same 307/383 split, same Quinlan lineage)
had `1` meaning "not approved." Confirmed against the UCI documentation (`A16`: "+" = approved = 307, "−" = not
approved = 383) and corrected in place: `target` is now `1 - target`, so `1` consistently means the bad/not-approved
outcome (383 rows, 55.5%), matching the convention used everywhere else in this catalog.

**Best known result:** not yet run through this project's Sandbox. Literature SOTA not independently verified
this session.

---

## Taiwan Credit Default (`Taiwan_UCI_Credit_Card.csv`)

**Origin (✅ verified):** Yeh, I.C. & Lien, C.H. (2009). *"The comparisons of data mining techniques for the
predictive accuracy of probability of default of credit card clients."* Expert Systems with Applications, 36(2),
2473–2480. UCI Machine Learning Repository, 30,000 Taiwanese credit card holders.

**Used in:** Very widely cited (one of the most-used credit-default benchmark datasets after German Credit);
original paper found ANN had the best predictive accuracy among the six methods compared.

**Profile:** 30,000 rows, 23 raw features, 0% missing, 22.1% positive rate. Structurally the cleanest genuine
"6-month observation → 1-month-ahead default" panel in this collection — `PAY_0`–`PAY_6` are repayment-status
history, `BILL_AMT1`–`6`/`PAY_AMT1`–`6` are 6 months of billing/payment amounts, target is default in the
following month.

**Best known result:** this project's own measured baseline: GBM **0.7776 AUC** (best of five). See
`RESULTS_LOG.md` §1.

---

## Bank Marketing — bank-full (`bank_marketing_dataset.csv`)

**Origin (✅ verified):** Moro, S., Cortez, P., & Rita, P. (2014). *"A data-driven approach to predict the success
of bank telemarketing."* Decision Support Systems, 62, 22–31. Portuguese banking institution's phone-based
marketing campaign data, UCI Machine Learning Repository.

**Used in:** One of the most-cited marketing-response datasets in applied ML; this is the older "bank-full"
45,211-row/16-input variant (not the newer `bank-additional-full`).

**Profile:** 45,211 rows, 16 raw features, 6.8% missing (52,124 blank cells in `contact`/`poutcome`, recorded as
"unknown" in the original schema rather than blank — see `n_missing` caveat), 11.7% positive rate (subscribed to
term deposit).

**Best known result:** this project's own measured baseline (with `duration` included, as in the original):
XGBoost **0.9314 AUC** (best of five). See `RESULTS_LOG.md` §1. **Important caveat already established in this
project:** `duration` is a post-outcome leakage feature (call length is only known after the call happens) —
dropping it costs 0.08–0.14 AUC uniformly across models. See `RESULTS_LOG.md` §1b.

---

## Bank Marketing — bank-additional-full (`bank_marketing_additional_full.csv`)

**Origin (✅ verified):** Same Moro, Cortez & Rita (2014) paper and UCI dataset page — this is the newer,
extended 41,188-row/20-input variant covering campaigns through May 2008–November 2010, with additional
macroeconomic context features (`emp.var.rate`, `cons.price.idx`, `cons.conf.idx`, `euribor3m`, `nr.employed`)
not present in bank-full.

**Profile:** 41,188 rows, 20 raw features, 11.3% positive rate. Reads as semicolon-delimited (raw UCI format),
unlike the comma-delimited bank-full file.

**Best known result:** not yet run through this project's Sandbox.

**Caveats:** not yet checked for the same `duration` leakage issue as bank-full — the column is present here too
and should be treated with the same caution.

---

## Give Me Some Credit / GMSC (`GMSC.csv`)

**Origin (✅ verified):** Kaggle competition, 2011. *"Give Me Some Credit"* — predict the probability a borrower
experiences serious delinquency (90+ days past due) within the next 2 years. ~150,000 anonymized borrower records.

**Profile:** 149,391 rows (the real Kaggle `cs-training.csv` has 150,000 including 609 exact duplicates — this
file was confirmed row-for-row identical to the real file, just deduplicated), 10 raw features, 2.0% missing
(`MonthlyIncome` 19.6% missing, `NumberOfDependents` 2.6% missing), 6.7% positive rate.

**Best known result (✅ verified from the actual Kaggle leaderboard, screenshot-confirmed 2026-09-27):**
Team "Perfect Storm" — **0.86955 AUC-ROC**, the competition's evaluation metric. Top 8 all sit within 0.00057 AUC
of each other (0.86898–0.86955), indicating a hard practical ceiling around 0.869 for this feature set.

This project's own measured baseline (cleaned, untuned): XGBoost **0.8653 AUC** — within 0.004 of the actual
competition winner, using default hyperparameters on raw features. See `RESULTS_LOG.md` and prior conversation.

**Caveats (established this session):** two real data-quality issues exist in the raw file — `NumberOfTimes90DaysLate`
and `NumberOfTime60-89DaysPastDueNotWorse` contain sentinel codes `96`/`98` (225 rows each, not real counts), and
`RevolvingUtilizationOfUnsecuredLines` has implausible outliers up to 50,708 (should be a ~0–2 ratio). Both are
fixed in a cleaned variant that was deleted from this folder per your 2026-10-03 request to keep only originals —
re-derive it if needed (recode 96/98 to NaN, cap utilization at 2.0).

---

## PAKDD 2009 / PAK (`PAK.csv`)

**Origin (✅ verified):** PAKDD (Pacific-Asia Conference on Knowledge Discovery and Data Mining) 2009 Data Mining
Competition, co-organized by NeuroTech Ltd. and the Center for Informatics, Federal University of Pernambuco.
Data from the private-label credit card operation of a Brazilian retail chain. Over 140 teams participated.

**Profile:** 50,000 rows, 51 raw features, 12.3% missing, 26.1% positive rate (`TARGET_LABEL_BAD`). Several
extreme-cardinality categorical columns (`RESIDENCIAL_BOROUGH` 14,510 distinct values, `CITY_OF_BIRTH` 9,909) —
this is the dataset that originally caused an 18GB memory blowup in the Sandbox before the native-categorical-XGBoost
fix (see prior conversation / git history).

**Best known result:** the only specific competition figure I could verify is a documented **3rd-place finish at
AUC 0.655** (an approach that fed KNN output into logistic regression). I could not find the 1st-place winning
score in available sources — do not assume 0.655 is the best achievable number, it's just the one figure I could
confirm.

This project's own measured baseline: XGBoost **0.6466 AUC** (native categorical handling, no tuning).

---

## TH02 (`TH02.csv`)

**Origin (✅ verified 2026-10-03, upgraded from an earlier unverified guess):** this is the "Thomas" dataset
(L.C. Thomas, D.B. Edelman & J.N. Crook, *Credit Scoring and its Applications*, 2002), part of the Lessmann et
al. (2015) benchmark suite. Confirmed via an independently documented fact that matches this file exactly:
1,225 applicants, 13 features, and — critically — a documented **26.37% default rate**, which is what nailed the
target-orientation fix below. Column names (`YOB`, `NKID`, `DEP`, `PHON`, `SINC`, `AES`, `DAINC`, `RES`, `DHVAL`,
`DMORT`, `DOUTM`, `DOUTL`, `DOUTHP`, `DOUTCC`) are UK consumer-credit scoring variables (year of birth, number of
kids, dependents, phone, income, employment status, disposable income, residential status, dwelling value,
mortgage/loan/HP/credit-card outstanding balances).

**Profile:** 1,225 rows, 14 raw features, 0% missing, 23 duplicate rows, 26.4% positive rate.

**Target orientation fixed (2026-10-03):** this file's `target` was inverted — `1` occurred 73.6% of the time,
but the documented real default rate for this exact dataset is 26.37%, which matched `target=0`'s count (323/1,225)
almost exactly. Corrected in place (`target = 1 - target`); positive rate is now 26.4%, matching the literature
figure to two decimal places.

**Best known result:** not yet run through this project's Sandbox.

---

## MSME Credit Data (`MSME_Credit_Data.csv`)

**Origin (⚠️ unverified):** Kaggle dataset "MSME Credit Data by 30S-CR" — confirmed to exist on Kaggle (referenced
in at least one public notebook), but I could not find its original compiler, institutional source, or any
associated academic paper. Appears to be small/medium enterprise credit data, likely Chinese in origin based on
column content (renminbi-denominated capital fields, insurance/tax/patent/legal-proceeding history fields).

**Profile:** 1,707 rows, 87 raw features (unusually wide — covers registered capital, enterprise type, multi-year
insurance payment history, legal proceedings, patents, trademarks), 1.3% missing, 6.0% positive rate.

**Best known result:** not yet run; no verified benchmark found.

---

## HELOC (`heloc.csv`)

**Origin (✅ verified):** FICO (Fair Isaac Corporation) *Explainable Machine Learning Challenge*, 2018, co-sponsored
with Google, UC Berkeley, Oxford, Imperial College, MIT, and UC Irvine. ~10,000 home equity line of credit
applicants; outcome label is whether the applicant was ever 90+ days delinquent.

**Profile:** 10,459 rows, 23 raw features, 0% blank cells **but uses FICO's documented `-9`/`-7`/`-8` sentinel
codes for missing/not-applicable data** — confirmed directly: 7,957 of 10,459 rows (76%) have at least one
negative sentinel value somewhere (e.g. `ExternalRiskEstimate` has 598 rows at `-9`, `MSinceOldestTradeOpen` has
827). **These must be recoded to NaN before modeling** — treating `-9` as a real numeric value would badly corrupt
any model trained on this file as-is. 52.2% positive rate.

**Best known result:** not yet run through this project's Sandbox (and should not be, until the sentinel values
are cleaned). Used extensively in the explainable-AI literature (e.g. Chen et al., *"An Interpretable Model with
Globally Consistent Explanations for Credit Risk,"* 2018) for interpretability comparisons rather than pure
accuracy benchmarking.

---

## HMEQ (`hmeq.csv`)

**Origin (✅ verified):** SAS `SAMPSIO` library sample dataset, associated with Baesens, Roesch & Scheule,
*Credit Risk Analytics: Measurement Techniques, Applications and Examples in SAS* (Wiley, 2016). 5,960 home
equity loan applicants; built to help a bank automate HELOC approval decisions per Equal Credit Opportunity Act
guidance.

**Profile:** 5,960 rows, 12 raw features, 6.8% missing overall, 19.9% positive rate (`BAD`), with real per-column
missingness: `DEBTINC` (21.3% missing, worst), `DEROG` (11.9%), `DELINQ` (9.7%), `YOJ`/`NINQ` (~8.6%), down to
`VALUE` (1.9%, least).

**Best known result:** not yet run through this project's Sandbox; this is primarily a teaching/tutorial dataset
rather than a competitive benchmark, so no "best score" exists in the same sense as a competition leaderboard.

---

## Loan Data (`loan_data.csv`)

**Origin (✅ verified):** A cleaned, pre-processed subset of LendingClub's public 2007–2010 loan data, widely
redistributed for tutorials (this exact `loan_data.csv` / `credit.policy`/`not.fully.paid` column schema appears
in numerous GitHub/Kaggle educational projects). Not a single canonical academic source — more a de facto
standard teaching dataset.

**Profile:** 9,578 rows, 13 raw features + target, 0% missing, 16.0% positive rate (`not.fully.paid`).

**Best known result:** no formal benchmark exists for this specific pre-cleaned educational variant.

---

## Credit Risk Dataset (`credit_risk_dataset.csv`)

**Origin (✅ verified):** Kaggle dataset by user "laotse" (`laotse/credit-risk-dataset`) — a community-contributed
dataset, not tied to a formal academic paper or competition.

**Profile:** 32,581 rows, **12 real columns** (the file carries 17 total — 5 are entirely empty "Unnamed"
artifact columns from however it was originally exported, inflating the raw column/missing-cell counts above),
30.1% missing is mostly those junk columns plus genuine gaps in `person_emp_length` (895 rows) and
`loan_int_rate` (3,116 rows), 17.6% positive rate.

**Known data-quality issue (confirmed directly):** 5 rows have `person_age` up to **144** (clearly erroneous),
and `person_emp_length` reaches **123** years for 2 rows — neither is fixed in this raw copy. A separate
`credit_risk_cleaned.csv` existed with junk columns dropped, missing values median-imputed, and categoricals
label-encoded, but it did **not** fix these age/employment-length outliers either — it was deleted from this
folder per your 2026-10-03 request to keep only originals.

**Best known result:** no verified literature/competition benchmark found (this is a Kaggle community dataset, not
a competition with a leaderboard).

---

## LendingClub Q1 2019 (`lending_club_q12019.csv`)

**Origin (✅ verified):** LendingClub's own publicly released quarterly loan-level data (2019 Q1 slice). The full
111-column raw schema (not a pre-cleaned tutorial subset like `loan_data.csv` above) — **correction to an earlier
claim in this catalog:** the raw `loan_status` column has already been replaced with a ready-made binary `target`
column at some point before this file reached this project; it is *not* still a multi-category field needing a
grouping decision, as an earlier version of this entry incorrectly stated.

**Profile:** 39,717 rows, 111 raw columns, 51.3% missing overall — but this is largely structural, not data
quality: many LendingClub columns only apply to certain loan sub-types (e.g. joint-application fields are blank
for individual applications), so a high missing rate here doesn't mean the data is broken. 14.2% positive rate.

**Target orientation confirmed (2026-10-03):** `loan_status` isn't present to cross-check directly, so this was
verified indirectly instead — `target=1` loans carry a markedly higher average interest rate (13.82% vs. 11.72%)
and a much worse grade mix (10.7% grade-A vs. 27.8% for `target=0`, with heavy right-shift into D/E/F/G). Both are
exactly what you'd expect if `target=1` means higher default risk, so this file's orientation is correct — no fix
needed.

**Usage caveat already flagged in this project:** LendingClub's own data-reuse terms apply — fine for internal
testing, but check licensing before citing results from this file in any publication.

**Best known result:** not yet run through this project's Sandbox.

---

## Mortgage Panel (`mortgage.csv`)

**Origin (✅ verified via a deep-dive pass on 2026-10-03, correcting an earlier guess):** this is the companion
dataset to Baesens, B., Roesch, D., & Scheule, H., *Credit Risk Analytics: Measurement Techniques, Applications,
and Examples in SAS* (Wiley, 2016) and its R companion, *Credit Risk Analytics: The R Companion* (2017) — hosted
on the authors' own site, `creditriskanalytics.net` (direct link to `mortgage_csv.rar`), and on their newer
platform `deepcreditrisk.com`, which describes it precisely as "50,000 mortgages with 15,000 defaults across 60
quarters" — matching this file's structure exactly. The underlying raw data is a randomized sample from U.S.
residential mortgage-backed-securities (RMBS) securitization portfolios, sourced from "International Financial
Research." The book builds its **Discrete-Time Hazard Models** and **Continuous-Time Hazard Models** chapters
(probability of default) specifically around this dataset — matching the competing-risks structure
(`default_time`/`payoff_time`) confirmed directly from the data.

**Correction to an earlier claim in this catalog:** I had speculated this might be the replication data behind
Deng, Quigley & Van Order, *"Mortgage Terminations, Heterogeneity and the Exercise of Mortgage Options,"*
Econometrica 68(2), 2000, flagged at the time as unconfirmed. A further search found no actual evidence connecting
them — that paper uses the same general competing-risks hazard methodology, which is standard in this field, but
that is a methodological resemblance, not a data lineage. There is no basis for that earlier guess; the
Baesens/Roesch/Scheule textbook above is the real, confirmed source.

**Usage requirement found during this research:** the authors' site states a request to **reference their books
upon use of this dataset** — if any result from this file goes into the TAI paper revision, cite Baesens, Roesch
& Scheule accordingly.

**What I still could not find:** despite a genuinely thorough search (the exact column-name fingerprint, the
dataset's specific "50,000 loans / 60 periods" description, and author-name searches for a standalone paper), I
found no independent, peer-reviewed journal article outside the textbook itself that uses this exact dataset. That
doesn't prove none exists — course assignments, theses, and paywalled papers are hard to fully surface by search —
but no such citation should be assumed or invented.

**Profile:** 622,489 rows = 50,000 unique loans × ~12.4 observed periods each (confirmed directly). **Not a
binary-target dataset** — `default_time`/`payoff_time`/`status_time` together encode three mutually exclusive
terminal states confirmed directly from the data: 580,742 rows still active/censored, 15,158 rows terminate in
default, 26,589 rows terminate in payoff. At the loan level: 53% eventually paid off, 30% defaulted, 17% were
still active and unresolved when the data collection ended.

**Best known result:** no benchmark applies in the usual sense — this needs a modeling-approach decision (discrete-time
competing-risks hazard model vs. collapsed single-row-per-loan classification) before any result is meaningful. See
the "multiple output scenarios" discussion earlier in this project's conversation history — not yet built.

---

## What's genuinely missing from this catalog

A few datasets discussed earlier in this project were never added to this folder: **Kaggle's Home Credit Default
Risk** (~300K rows, 2018 competition) and the **full multi-GB LendingClub accepted-loans file** (1.67 GB,
impractical to store here) were mentioned as candidates but never copied in. If you want either, say so and I'll
fetch/verify them the same way as everything above.
