# SHARP feature selection across runs — what each dataset dropped

**Source.** Extracted from the recorded `SHARP_<DATASET>.md` reports (Stage-1 screen → Stage-2 shadow-null →
Stage-3 parsimony). "Removed" = features in the SHARP modelling pool that are **not** in the final selected set.
Grounded in the run records; no values invented. Prepared 2026-10-16.

> **Scope note.** Counts are relative to the **SHARP modelling pool** (the features that entered Stage 1), i.e.
> *after* any Gate-0 data scoping. For **LC** and **MSME**, heavy G0 pre-scoping happened first (LC: 111 raw
> LendingClub columns → 21-feature grade-free pool after dropping empty/leakage/ID/constant + grade + int_rate;
> MSME: raw export → 87-feature pool). This table shows the **statistical** SHARP removals, not those upstream G0
> data-cleaning drops. Removed features are tagged **[S1]** if they failed the univariate screen, **[S2/S3]** if they
> passed the screen but were dropped by shadow-null / parsimony.

## Summary

| # | Dataset | Pool | Kept | Removed | % removed | Final Gini / AUC |
|--:|---|--:|--:|--:|--:|---|
| 1 | HMEQ | 12 | 11 | **1** | 8% | 0.80 / 0.90 |
| 2 | CREDITRISK | 9 | 6 | **3** | 33% | 0.76 / 0.88 |
| 3 | GMSC | 9 | 8 | **1** | 11% | 0.705 / 0.853 |
| 4 | HELOC | 23 | 17 | **6** | 26% | 0.587 / 0.794 |
| 5 | Taiwan | 20 | 14 | **6** | 30% | 0.54 / 0.77 |
| 6 | German | 17 | 5 | **12** | 71% | 0.53 / 0.765 |
| 7 | MSME | 87 | 15 | **72** | 83% | 0.435 / 0.718 |
| 8 | LOAN | 13 | 7 | **6** | 46% | 0.343 / 0.672 |
| 9 | TH02 | 14 | 6 | **8** | 57% | 0.272 / 0.636 |
| 10 | PAK | 39 | 6 | **33** | 85% | 0.148 / 0.574 |
| 11 | LC (grade-free) | 21 | 9 | **12** | 57% | 0.351 / 0.676 |

**Across the corpus SHARP removed on average ~50% of the pool** — and far more where features were redundant or
noisy (MSME 83%, PAK 85%, German 71%), confirming the method is genuinely selective, not a rubber stamp.

## Removed features, per dataset

**1. HMEQ** (1) — `REASON` [S1] (IV 0.009, unpredictive).
**Kept (11):** DEBTINC, DELINQ, DEROG, MORTDUE, VALUE, CLAGE, JOB, NINQ, LOAN, YOJ, CLNO.

**2. CREDITRISK** (3) — `person_emp_length` [S1]; `loan_amnt`, `cb_person_cred_hist_length` [S2/S3].
**Kept (6):** loan_percent_income, loan_grade, person_income, loan_int_rate, person_home_ownership, loan_intent.

**3. GMSC** (1) — `NumberOfOpenCreditLinesAndLoans` [S2/S3].
**Kept (8):** RevolvingUtilizationOfUnsecuredLines, NumberOfTime30-59DaysPastDueNotWorse, NumberOfTimes90DaysLate,
NumberOfTime60-89DaysPastDueNotWorse, MonthlyIncome, NumberRealEstateLoansOrLines, NumberOfDependents, DebtRatio.

**4. HELOC** (6) — `MSinceMostRecentTradeOpen` [S1]; `NumTradesOpeninLast12M`, `NumInqLast6M`, `NumInqLast6Mexcl7days`,
`NetFractionInstallBurden`, `NumInstallTradesWBalance` [S2/S3].
**Kept (17):** ExternalRiskEstimate, NetFractionRevolvingBurden, NumBank2NatlTradesWHighUtilization,
MSinceMostRecentDelq, AverageMInFile, MSinceOldestTradeOpen, MaxDelq2PublicRecLast12M, MaxDelqEver,
PercentTradesNeverDelq, MSinceMostRecentInqexcl7days, PercentTradesWBalance, NumTrades60Ever2DerogPubRec,
NumTrades90Ever2DerogPubRec, NumSatisfactoryTrades, NumTotalTrades, NumRevolvingTradesWBalance, PercentInstallTrades.

**5. Taiwan** (6) — `BILL_AMT1`–`BILL_AMT6` (the six raw bill-amount columns; 5×[S1] + 1×[S2/S3] — redundant with
the PAY_* repayment-status series).
**Kept (14):** PAY_0, PAY_2–PAY_6, LIMIT_BAL, PAY_AMT1–PAY_AMT6, EDUCATION.

**6. German** (12) — `credit_amount`, `employment_since`, `installment_rate`, `other_debtors`, `residence_since`,
`property`, `other_installment_plans`, `housing`, `existing_credits`, `job`, `people_liable`, `telephone`.
**Kept (5):** checking_status, credit_history, months_duration, savings_status, purpose.

**7. MSME** (72) — almost the entire **time-stratified history block** (the `_1year … _5years+` series for
`CL_*`, `Certificate_num_*`, `Executee_num_*`, `Overdue_tax_num_*`, `Administrative_penalty_num_*`,
`Trademark/Patent/Work_copyright/Software_copyright_info_num_*`, `Legal_proceedings_num_*`, `Filing_information_num_*`),
plus the `t-3` social-insurance columns, `Province`, `Establishment_Duration`, `Paid_in_capital`, `SH_num`, `MS_num`,
`Branch_num`, `Ratepaying_Credit_Grade_A_num`. (Mostly [S1] — sparse / zero-inflated counts.)
**Kept (15):** Sector, Enterprise_type, Registered_capital, Certificate_num_2years, Trademark_info_num_5years+, and the
`t-1`/`t-2` social-insurance series (medical, old-age, birth, injury, unemployment × 2 periods).

**8. LOAN** (6) — `installment` [S1], `dti`, `days.with.cr.line`, `revol.bal`, `delinq.2yrs`, `pub.rec` [S2/S3].
**Kept (7):** fico, int.rate, inq.last.6mths, credit.policy, purpose, revol.util, log.annual.inc.

**9. TH02** (8) — `NKID`, `DEP`, `PHON`, `SINC` [S1, incl. self-removed proxies/prohibited]; `DOUTM`, `DOUTL`,
`DOUTHP`, `DOUTCC` [S2/S3].
**Kept (6):** DAINC, AES, YOB, DHVAL, DMORT, RES.

**10. PAK** (33) — the bulk of the application-form flags and sparse fields: `FLAG_*` (VISA, MASTERCARD, DINERS,
AMERICAN_EXPRESS, OTHER_CARDS, MOBILE_PHONE, EMAIL, RESIDENCIAL_PHONE, PROFESSIONAL_PHONE, RG, CPF, INCOME_PROOF,
HOME_ADDRESS_DOCUMENT, ACSP_RECORD), `PERSONAL_MONTHLY_INCOME`, `OTHER_INCOMES`, `PERSONAL_ASSETS_VALUE`, `QUANT_*`
(DEPENDANTS, CARS, ADDITIONAL_CARDS), `EDUCATION_LEVEL(_2)`, `RESIDENCE_TYPE`, `MONTHS_IN_RESIDENCE/THE_JOB`,
`PROFESSION_CODE`, `MATE_PROFESSION_CODE`, `COMPANY`, `PRODUCT`, address/submission-type fields. (Mostly [S1].)
**Kept (6):** PAYMENT_DAY, RESIDENCIAL_PHONE_AREA_CODE, OCCUPATION_TYPE, PROFESSIONAL_STATE, QUANT_BANKING_ACCOUNTS,
QUANT_SPECIAL_BANKING_ACCOUNTS.

**11. LC (grade-free)** (12) — `emp_length`, `home_ownership`, `verification_status`, `dti`, `delinq_2yrs`,
`mths_since_last_delinq`, `mths_since_last_record`, `open_acc`, `revol_bal`, `total_acc`, `pub_rec_bankruptcies`,
`credit_hist_years` (all [S1]).
**Kept (9):** term, revol_util, annual_inc, inq_last_6mths, purpose, funded_amnt, loan_amnt, addr_state [proxy], pub_rec.
*(Plus upstream G0 drops: int_rate, installment, grade, sub_grade, 13 leakage, ~53 empty, 7 ID/text, 9 constant.)*
