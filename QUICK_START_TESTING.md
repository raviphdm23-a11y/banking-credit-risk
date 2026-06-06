# Quick Start: Data-Driven Selenium Testing
## 30-Second Setup Guide

---

## 🚀 In 3 Steps

### Step 1: Open Excel File
```
File: test_data.xlsx
Location: C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk\
```

### Step 2: Add Your Test Case (Copy Template Below)
```
Test ID:              TC006
Borrower ID:          CORP006
Borrower Name:        Your Company Name
Sector:               Manufacturing
Exposure Amount:      1500000
Calc Mode:            both
Debt to Equity:       0.9
Interest Coverage:    3.2
Profitability Margin: 20
Liquidity Ratio:      1.3
Seniority:            Senior Unsecured
Loan Type:            Term Loan Short
Collateral Type:      Real Estate
Collateral Value:     600000
External Rating:      A
Exposure Category:    Corporate
Expected PD Min:      3.8
Expected PD Max:      4.3
Expected LGD Min:     44
Expected LGD Max:     46
Test Description:     Your test scenario description
```

### Step 3: Run Tests
```bash
python test_selenium_e2e.py
```

✅ Done! Tests will run automatically for all rows in Excel.

---

## 📋 Column Quick Reference

**ALWAYS fill these (Required):**
- Test ID ← Make it unique (TC001, TC_SCENARIO, etc.)
- Borrower ID, Name, Sector, Exposure Amount
- Debt to Equity, Interest Coverage, Profitability Margin, Liquidity Ratio
- Calc Mode (airb / standardized / both)
- Expected PD Min/Max, Expected LGD Min/Max
- Test Description

**FILL ONLY IF CALC MODE INCLUDES:**

| If Mode = "airb" or "both" | If Mode = "standardized" or "both" |
|---------------------------|-----------------------------------|
| Seniority | External Rating |
| Loan Type | Exposure Category |
| Collateral Type | |
| Collateral Value | |

**LEAVE BLANK if not needed:**
- If no collateral: Leave "Collateral Type" as "None"
- If AIRB only: Leave "External Rating" and "Exposure Category" blank

---

## ✅ Pre-Check Before Running

- [ ] Excel file saved
- [ ] No duplicate Test IDs
- [ ] All required columns filled for your Calc Mode
- [ ] Numeric values have no commas (1000000 not 1,000,000)
- [ ] Expected PD/LGD are realistic ranges

---

## 🎯 Example Test Cases Ready to Use

### Copy & Paste Template 1: Conservative Borrower (AIRB)
```
TC007 | CORP007 | Conservative Corp | Manufacturing | 2000000
both | 0.5 | 4.5 | 25 | 1.8
Senior Secured - Other | Term Loan Long | Real Estate | 1500000
AAA | Corporate | 2.0 | 2.5 | 30 | 35
Conservative: Low leverage, high margins, excellent coverage
```

### Copy & Paste Template 2: High Growth Tech (BOTH)
```
TC008 | CORP008 | Tech Startup Inc | Technology | 5000000
both | 1.8 | 2.5 | 15 | 1.2
Senior Unsecured | Term Loan Short | None | 0
BBB+ | Corporate | 6.0 | 7.0 | 50 | 60
Growth stage: Higher leverage, lower margins, fast growth
```

### Copy & Paste Template 3: Government Bond (SA Only)
```
TC009 | GOV001 | Federal Treasury | Government | 50000000
standardized | 0.1 | 10.0 | 5 | 2.8
| | | 0
AAA | Sovereign | 0.3 | 0.7 | 15 | 20
Safe haven: Sovereign exposure, AAA rated
```

---

## 🔍 How to Verify Your Test Works

### Check 1: Form Gets Filled
- Browser opens borrower-info.html
- All fields populate with your Excel data
- No red "required field" errors appear

### Check 2: Calculation Runs
- "Calculate Risk Parameters" button works
- Results appear (PD, LGD, Risk Weight values)
- No JavaScript errors in browser console

### Check 3: Results Match Expectations
- Calculated PD falls within your Expected PD Min/Max
- Calculated LGD falls within your Expected LGD Min/Max
- Test shows [PASS] for these verifications

### Check 4: Loan Records
- "Confirm & Record Loan" button works
- Loan appears in portfolio table below
- Test shows [PASS] for portfolio verification

---

## ⚠️ Common Mistakes & Fixes

| Mistake | Fix |
|---------|-----|
| "Dropdown value not found" error | Use exact value from dropdown (Case-sensitive!) |
| Test skipped entire row | Probably has duplicate Test ID |
| Expected results don't match | Recalculate manually; allow 0.5% tolerance |
| "File not found" error | Move test_data.xlsx to correct directory |
| Test hangs on Calculate button | Check all required fields for calc mode are filled |

---

## 📞 Getting Help

**Question:** How do I know what values to put?  
**Answer:** Use the column descriptions in `EXCEL_TEST_DATA_GUIDE.md` or check dropdown values in the application.

**Question:** My test failed. What now?  
**Answer:** Check if calculated PD/LGD match your expected ranges. If not, recalculate manually.

**Question:** Can I add unlimited test cases?  
**Answer:** Yes! Add as many rows as you want. The test will run all of them automatically.

**Question:** How long do tests take?  
**Answer:** ~2-3 minutes per test case (form filling + calculation + verification + 2-sec pause).

---

## 🎓 Calculation Formulas (For Expected Values)

### PD Formula
```
PD = 2.0 + (D/E × 0.8) + max(0, -Margin × 0.15)
     + max(0, (1.5 - Liquidity) × 3.0)
     + max(0, (4.0 - ICR) × 0.5)
```

### LGD Formula (depends on seniority, collateral, sector)
```
Base LGD = Lookup table by seniority
Coverage Adjustment = Based on collateral ratio
Sector Adjustment = Based on industry
Final LGD = Base + Coverage + Sector (clamped 5-90%)
```

**Example:**
```
D/E=0.8, ICR=3.5, Margin=18%, Liquidity=1.2
PD = 2.0 + 0.64 + 0 + 0.9 + 0.25 = 3.79%
```

---

## 📊 Success Pattern

✅ Successful test output looks like:
```
========================================
TEST CYCLE: TC006 - Your Company Name
========================================
  [PASS] Open borrower-info.html
  [PASS] Fill Form from Excel Data
  [PASS] Click Calculate
  [PASS] Verify PD Result: PD: 3.95% (Expected: 3.8-4.3%)
  [PASS] Verify LGD Result: LGD: 45% (Expected: 44-46%)
  [PASS] Click Confirm & Record
  [PASS] Verify Loan in Portfolio

========================================
TEST EXECUTION SUMMARY
========================================
Total Test Cases: 6
[PASS] Passed: 6
[FAIL] Failed: 0
[SUCCESS] ALL TESTS PASSED!
```

---

## 🔗 Related Files

- **Full Guide:** `EXCEL_TEST_DATA_GUIDE.md` - Complete documentation
- **Test Code:** `test_selenium_e2e.py` - Automated test suite
- **Test Data:** `test_data.xlsx` - Your test scenarios
- **App:** `public/borrower-info.html` - Application being tested
- **CLAUDE.md** - Project context and technical details

---

**Last Updated:** June 3, 2026  
**Time to Add Test Case:** ~2 minutes  
**Time to Run 5 Tests:** ~10-15 minutes
