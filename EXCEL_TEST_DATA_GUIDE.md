# Excel Test Data Guide
## Data-Driven Selenium Testing for Banking Credit Risk Calculator

**Document Date:** June 3, 2026  
**Version:** 1.0  
**File:** `test_data.xlsx`

---

## 📋 Overview

The Selenium test suite is now **data-driven**, meaning all test inputs are stored in an Excel file (`test_data.xlsx`) rather than hard-coded in the test script. This allows you to:

- ✅ Add unlimited test cases without modifying code
- ✅ Manage test data in a familiar Excel format
- ✅ Run multiple test cycles automatically
- ✅ Track expected results per test scenario
- ✅ Easily share test cases with team members

---

## 🗂️ File Location & Structure

**File Path:** `C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk\test_data.xlsx`

**Sheet Name:** "Test Data" (default sheet)

**Layout:**
- **Row 1:** Column headers (frozen for easy scrolling)
- **Rows 2+:** Test case data (one test per row)

---

## 📊 Column Descriptions

### Section A: Test Identification
| Column | Description | Example | Required |
|--------|-------------|---------|----------|
| **Test ID** | Unique identifier for the test case | TC001, TC002 | YES |
| **Test Description** | Human-readable description | "BOTH mode with collateral" | YES |

### Section B: Borrower Information
| Column | Description | Example | Required |
|--------|-------------|---------|----------|
| **Borrower ID** | Unique borrower identifier | CORP001, SOV001 | YES |
| **Borrower Name** | Full name of borrower | ABC Manufacturing | YES |
| **Sector** | Industry/sector category | Manufacturing, Technology, Financial Services | YES |
| **Exposure Amount** | Loan amount in currency units | 1000000, 2500000 | YES |
| **Calc Mode** | Calculation methodology | airb, standardized, both | YES |

### Section C: Financial Metrics (For PD Calculation)
| Column | Description | Range | Example | Required |
|--------|-------------|-------|---------|----------|
| **Debt to Equity** | D/E ratio | 0.0 - 5.0 | 0.8, 1.2 | YES |
| **Interest Coverage** | Interest Coverage Ratio | 0.5 - 20.0 | 3.5, 2.8 | YES |
| **Profitability Margin** | Net profit margin (%) | -50 - 100 | 18, 22, 10 | YES |
| **Liquidity Ratio** | Current/Quick ratio | 0.5 - 3.0 | 1.2, 1.5 | YES |

### Section D: Collateral & Seniority (AIRB Mode)
| Column | Description | Options | Example | Required If |
|--------|-------------|---------|---------|------------|
| **Seniority** | Debt seniority level | Senior Unsecured, Senior Secured - Real Estate, Senior Secured - Financial Assets, Senior Secured - Other, Subordinated | Senior Unsecured | Calc Mode includes AIRB |
| **Loan Type** | Type of loan facility | Working Capital, Short-term Trade Finance, Revolving Credit Facility, Term Loan Short, Term Loan Long, Bond | Term Loan Short | Calc Mode includes AIRB |
| **Collateral Type** | Type of collateral pledged | None, Real Estate, Financial Assets, Equipment, Inventory, Other | Real Estate | Calc Mode includes AIRB |
| **Collateral Value** | Value of collateral (currency) | 0 - Exposure Amount | 500000 | Calc Mode includes AIRB |

### Section E: Standardized Approach (SA Mode)
| Column | Description | Options | Example | Required If |
|--------|-------------|---------|---------|------------|
| **External Rating** | Credit rating from external agency | AAA, AA+, AA, AA-, A+, A, A-, BBB+, BBB, BBB-, BB+, BB, BB-, B+, B, B-, CCC+, CCC, CCC-, D, Unrated | A, AA, BB+ | Calc Mode includes SA |
| **Exposure Category** | Type of counterparty | Sovereign, Bank, Corporate, Financial Institution | Corporate | Calc Mode includes SA |

### Section F: Expected Results (For Validation)
| Column | Description | Range | Example | Purpose |
|--------|-------------|-------|---------|---------|
| **Expected PD Min** | Minimum expected PD (%) | 0.0 - 100.0 | 3.5 | Validate PD calculation |
| **Expected PD Max** | Maximum expected PD (%) | 0.0 - 100.0 | 4.2 | Validate PD calculation |
| **Expected LGD Min** | Minimum expected LGD (%) | 0.0 - 100.0 | 44 | Validate LGD calculation |
| **Expected LGD Max** | Maximum expected LGD (%) | 0.0 - 100.0 | 46 | Validate LGD calculation |

---

## 🚀 Quick Start: Adding a New Test Case

### Step 1: Open the Excel File
```
File → Open → test_data.xlsx
```

### Step 2: Go to the Last Row
- Navigate to the last row with data
- The next empty row is where you'll add your test case

### Step 3: Fill in All Required Columns
Start with **Test ID** (Column A) and fill left to right:

**Example: New test case for high-risk corporate**

| Column | Value |
|--------|-------|
| Test ID | TC006 |
| Borrower ID | CORP005 |
| Borrower Name | High Risk Manufacturing Co |
| Sector | Manufacturing |
| Exposure Amount | 3000000 |
| Calc Mode | both |
| Debt to Equity | 2.0 |
| Interest Coverage | 1.5 |
| Profitability Margin | -5 |
| Liquidity Ratio | 0.8 |
| Seniority | Subordinated |
| Loan Type | Term Loan Long |
| Collateral Type | Equipment |
| Collateral Value | 500000 |
| External Rating | BB |
| Exposure Category | Corporate |
| Expected PD Min | 8.0 |
| Expected PD Max | 10.0 |
| Expected LGD Min | 55 |
| Expected LGD Max | 75 |
| Test Description | High risk: Subordinated, negative margin, low liquidity |

### Step 4: Save the File
```
Ctrl+S or File → Save
```

### Step 5: Run the Test Suite
```bash
python test_selenium_e2e.py
```

The test will automatically:
- ✅ Read the new test case from Excel
- ✅ Fill the form with your data
- ✅ Calculate risk parameters
- ✅ Record the loan
- ✅ Verify results in portfolio
- ✅ Report pass/fail for your test case

---

## 📝 Test Case Examples

### Example 1: Simple AIRB Only Test
```
Test ID:           TC002
Borrower ID:       CORP002
Borrower Name:     XYZ Tech Solutions
Sector:            Technology
Exposure Amount:   2500000
Calc Mode:         airb
D/E:               1.2
ICR:               2.8
Margin:            22
Liquidity:         1.5
Seniority:         Senior Secured - Other
Loan Type:         Term Loan Long
Collateral Type:   Equipment
Collateral Value:  1000000
External Rating:   (leave blank)
Category:          (leave blank)
Expected PD Min:   4.5
Expected PD Max:   5.5
Expected LGD Min:  40
Expected LGD Max:  45
Description:       AIRB only mode with equipment collateral
```

### Example 2: SA Only Test (Sovereign)
```
Test ID:           TC005
Borrower ID:       SOV001
Borrower Name:     Ministry of Finance
Sector:            Government
Exposure Amount:   10000000
Calc Mode:         standardized
D/E:               0.3
ICR:               8.0
Margin:            5
Liquidity:         2.5
Seniority:         (leave blank - not needed for SA)
Loan Type:         (leave blank)
Collateral Type:   (leave blank)
Collateral Value:  0
External Rating:   AAA
Category:          Sovereign
Expected PD Min:   0.5
Expected PD Max:   1.5
Expected LGD Min:  20
Expected LGD Max:  25
Description:       Sovereign exposure: Low risk with AAA rating
```

### Example 3: BOTH Mode Combined Test
```
Test ID:           TC001
Borrower ID:       CORP001
Borrower Name:     ABC Manufacturing
Sector:            Manufacturing
Exposure Amount:   1000000
Calc Mode:         both
D/E:               0.8
ICR:               3.5
Margin:            18
Liquidity:         1.2
Seniority:         Senior Unsecured
Loan Type:         Term Loan Short
Collateral Type:   Real Estate
Collateral Value:  500000
External Rating:   A
Category:          Corporate
Expected PD Min:   3.5
Expected PD Max:   4.2
Expected LGD Min:  44
Expected LGD Max:  46
Description:       BOTH mode: AIRB + SA combined with collateral
```

---

## ✅ Validation Rules

### Field Validation
- **Test ID:** Must be unique (no duplicates)
- **Numeric Fields:** Must be valid numbers (decimals OK)
- **Dropdown Fields:** Must match exact values from the application
- **Required Fields:** Never leave blank for your selected mode

### Calculation Mode Restrictions
| Mode | What's Required | What's Optional |
|------|-----------------|-----------------|
| **airb** | Borrower Info, Financial Metrics, Seniority, Loan Type | Collateral (can be "None") |
| **standardized** | Borrower Info, Financial Metrics, External Rating, Category | Collateral (optional) |
| **both** | ALL columns | None |

### Expected Results
- **Expected PD Min/Max:** Must be between 0.5 and 10.0 for typical cases
- **Expected LGD Min/Max:** Must be between 5 and 90 (per Basel III)
- **Min must be ≤ Max:** Otherwise test will fail validation

---

## 🎯 Best Practices

### DO ✅
- ✅ Use clear, descriptive Test IDs (TC001, TC_AIRB_HIGH_RISK, etc.)
- ✅ Add meaningful descriptions for complex test cases
- ✅ Test edge cases (very high/low financial metrics)
- ✅ Test all three calculation modes regularly
- ✅ Keep a backup copy of the Excel file
- ✅ Update expected results based on manual calculations

### DON'T ❌
- ❌ Use duplicate Test IDs
- ❌ Leave required fields blank
- ❌ Use values outside documented ranges
- ❌ Delete header row (it's needed by the test code)
- ❌ Change column order or names
- ❌ Use commas in numeric values (use 1000000 not 1,000,000)

---

## 🔍 How the Test Suite Works

### Test Cycle Flow (Per Row)

```
1. Open borrower-info.html
   ↓
2. Fill form with Excel data
   ├─ Borrower info section
   ├─ Financial metrics section
   ├─ Conditional sections based on Calc Mode
   └─ SA fields (if BOTH or standardized)
   ↓
3. Click "Calculate Risk Parameters"
   ↓
4. Verify calculation results
   ├─ Check PD is within Expected PD Min/Max
   └─ Check LGD is within Expected LGD Min/Max
   ↓
5. Click "Confirm & Record Loan"
   ↓
6. Verify loan in portfolio table
   ↓
7. Report PASS or FAIL for this test case
```

### Multiple Test Cycles

The test suite automatically:
1. Reads all rows from Excel (starting from row 2)
2. For each row, runs the complete cycle above
3. Pauses 2 seconds between cycles
4. Generates individual report for each test case
5. Prints summary showing all test results

---

## 📊 Understanding Test Results

### Success Output
```
[PASS] Test ID: TC001 - ABC Manufacturing
  [PASS] Open borrower-info.html
  [PASS] Fill Form from Excel Data
  [PASS] Click Calculate
  [PASS] Verify PD Result: PD: 3.79% (Expected: 3.5-4.2%)
  [PASS] Verify LGD Result: LGD: 45% (Expected: 44-46%)
  [PASS] Click Confirm & Record
  [PASS] Verify Loan in Portfolio
```

### Failure Output
```
[FAIL] Test ID: TC002 - XYZ Tech
  [PASS] Open borrower-info.html
  [PASS] Fill Form from Excel Data
  [PASS] Click Calculate
  [FAIL] Verify PD Result: PD: 5.5% (Expected: 4.5-5.5%)
         └─ PD outside expected range
```

---

## 🛠️ Troubleshooting

### Problem: Test can't find Excel file
**Solution:**
- Verify `test_data.xlsx` is in the same directory as `test_selenium_e2e.py`
- Check file path in Python console output
- Ensure you've installed openpyxl: `pip install openpyxl`

### Problem: Test fails with "Unknown value for dropdown"
**Solution:**
- Verify exact dropdown value from the application
- Common mistake: "Term Loan Short" not "Term Loan - Short"
- Use reference section below for exact values

### Problem: Expected results don't match calculation
**Solution:**
- Recalculate expected PD/LGD manually using formulas
- Add 0.5% buffer to account for rounding: Min-0.5, Max+0.5
- Check financial metrics are realistic for the sector

### Problem: Test hangs on "Click Calculate"
**Solution:**
- Check that all required fields for the calculation mode are filled
- Verify no validation errors on the form (red text)
- Increase wait time in test code if server is slow

---

## 📚 Dropdown Value Reference

### Sector Values
```
Manufacturing
Technology
Financial Services
Retail
Healthcare
Government
Energy
Real Estate
Transportation
Telecommunications
Utilities
Construction
Agriculture
Mining
Other
```

### Seniority Values
```
Senior Unsecured
Senior Secured - Real Estate
Senior Secured - Financial Assets
Senior Secured - Other
Subordinated
```

### Loan Type Values
```
Working Capital
Short-term Trade Finance
Revolving Credit Facility
Term Loan Short
Term Loan Long
Bond
```

### Collateral Type Values
```
None
Real Estate
Financial Assets
Equipment
Inventory
Other
```

### External Rating Values
```
AAA
AA+
AA
AA-
A+
A
A-
BBB+
BBB
BBB-
BB+
BB
BB-
B+
B
B-
CCC+
CCC
CCC-
D
Unrated
```

### Exposure Category Values
```
Sovereign
Bank
Corporate
Financial Institution
```

---

## 🎓 Tips & Tricks

### Tip 1: Quick Copy Test Case
To duplicate a test case:
1. Select entire row
2. Right-click → Insert Copied Cells
3. Change Test ID (must be unique)
4. Modify only the fields you need to change

### Tip 2: Track Test Purpose
Use the description column strategically:
```
"Boundary test: Minimum viable PD"
"Edge case: Very high leverage"
"Regression test: Previous bug scenario"
"Performance test: Large exposure"
```

### Tip 3: Group Related Tests
Keep related test cases together:
- Rows 2-5: AIRB modes
- Rows 6-10: SA modes
- Rows 11-15: Edge cases
- Rows 16-20: Regression tests

### Tip 4: Auto-Calculate Expected Results
Use Excel formulas to calculate expected PD:
```
PD = 2.0 + (D/E × 0.8) + max(0, -Margin × 0.15) 
     + max(0, (1.5 - Liquidity) × 3.0) 
     + max(0, (4.0 - ICR) × 0.5)
```

Create a helper column to calculate this automatically!

---

## 📞 Support

**For issues with:**
- **Test data:** Update Excel file, re-run tests
- **Expected results:** Verify calculation formulas in CLAUDE.md
- **Selenium code:** Check Python error messages in console
- **Application:** Verify borrower-info.html works manually first

---

## 📈 Next Steps

### Immediate
1. ✅ Review existing 5 test cases
2. ✅ Add 2-3 new test cases for your use cases
3. ✅ Run the test suite: `python test_selenium_e2e.py`

### Short Term
4. Expand to 20+ test cases covering all scenarios
5. Create regression test suite for known bugs
6. Set up automated nightly test runs

### Long Term
7. Integrate with CI/CD pipeline
8. Generate test reports automatically
9. Expand to other modules (Operational Risk, etc.)

---

**Last Updated:** June 3, 2026  
**Test Suite Version:** 2.0 (Data-Driven)  
**Excel Version:** 1.0
