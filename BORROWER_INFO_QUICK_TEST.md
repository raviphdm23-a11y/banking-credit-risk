# Borrower Assessment Workflow - Quick Testing Guide

**Version:** 1.0  
**Status:** Ready for Testing  
**Last Updated:** June 3, 2026

---

## Quick Start: Test the New Workflow

### Option A: Launch from borrower-info.html directly

1. Open `public/borrower-info.html` in your web browser
2. Fill in the test data below
3. Click "Calculate Risk Parameters"
4. Review the results
5. Click "Proceed to RWA Calculation"
6. Verify data loads into index.html

### Option B: Launch from Main Calculator

1. Open `public/index.html`
2. In the left sidebar, click **"🏢 Borrower Assessment (Recommended)"**
3. This opens borrower-info.html
4. Follow steps 2-6 above

---

## Test Case 1: AIRB Mode (Default)

**Purpose:** Verify complete AIRB flow with PD and LGD auto-calculation

**Input Data:**
```
Step 1: Borrower Information
├─ Borrower ID:           CORP001
├─ Borrower Name:         ABC Manufacturing
├─ Exposure Amount:       $1,000,000
├─ Sector:                Manufacturing
└─ Mode:                  AIRB ✓ (default)

Step 2: Financial Metrics
├─ Debt-to-Equity:        0.8
├─ Interest Coverage:     3.5
├─ Profitability Margin:  18
└─ Liquidity Ratio:       1.2

Step 3: Collateral & Seniority
├─ Seniority:             Senior Unsecured
├─ Collateral Type:       Real Estate
└─ Collateral Value:      $500,000

Step 4: [Skip - AIRB mode only]

Then click: [Calculate Risk Parameters]
```

**Expected Results:**

```
PD Calculation:
├─ Base Rate:                2.00%
├─ Leverage Impact (D/E×0.8): 0.64%
├─ Profitability Impact:     0.00%  [18% positive, so max(0, -18×0.15) = 0]
├─ Liquidity Impact:         0.90%  [max(0, (1.5-1.2)×3.0) = 0.9]
├─ Coverage Impact:          0.00%  [max(0, (4.0-3.5)×0.5) = 0.25] ... actually 0.25%
└─ **Total PD: 3.79%** ✅ (Risk Level: 🟢 Low)

LGD Calculation:
├─ Base LGD (Senior Unsecured): 45%
├─ Collateral Coverage: 500/1000 = 0.5x (< 1.0x, no adjustment)
├─ Coverage Adjustment:  0%
├─ Sector Adjustment (Manufacturing): 0%
└─ **Final LGD: 45%** ✅

Maturity:
├─ Suggested: 3 years (default for term loan)
└─ You can adjust: [input field] ✅
```

**Verification in Results Section:**
- ✅ PD card shows "3.79%" with green "Low" badge
- ✅ PD components table shows all 5 components
- ✅ LGD card shows "45%" 
- ✅ LGD components table shows: Base 45%, Coverage Adj 0%, Sector Adj 0%, Final 45%
- ✅ Maturity card shows "3 years" with override input
- ✅ SA card is NOT shown (AIRB mode)
- ✅ Green summary box appears

**Click "Proceed to RWA Calculation"**

**Verification in index.html:**
```
Expected Pre-filled Fields:
├─ Loan ID:              CORP001 ✅
├─ Borrower Name:        ABC Manufacturing ✅
├─ Exposure Amount:      $1,000,000 ✅
├─ Sector:               Manufacturing ✅
├─ PD:                   3.79 ✅
├─ LGD:                  45 ✅
├─ Maturity:             3 ✅
├─ Calculation Mode:     AIRB ✓ (radio selected) ✅
└─ SA fields:            Hidden (not needed for AIRB) ✅

Expected Notification:
"✅ Data loaded from Borrower Assessment: ABC Manufacturing (PD: 3.79%, LGD: 45%)"
```

**Continue to RWA:**
1. Verify all fields are pre-filled correctly
2. Click "Add Loan"
3. Verify RWA calculation completes
4. Check portfolio table for the new loan

---

## Test Case 2: Standardized Approach (SA) Mode

**Purpose:** Verify SA mode with risk weight lookup

**Input Data:**
```
Step 1: Borrower Information
├─ Borrower ID:           CORP002
├─ Borrower Name:         XYZ Financial Services
├─ Exposure Amount:       $2,000,000
├─ Sector:                Financial Services
└─ Mode:                  SA (select radio button)

Step 2: Financial Metrics
├─ Debt-to-Equity:        0.5
├─ Interest Coverage:     5.0
├─ Profitability Margin:  25
└─ Liquidity Ratio:       1.8

Step 3: [Skip - SA mode, this section hidden]

Step 4: External Rating & Category
├─ External Rating:       A
└─ Exposure Category:     Financial Institution

Then click: [Calculate Risk Parameters]
```

**Expected Results:**

```
PD Calculation:
├─ Base: 2.0%
├─ Leverage: 0.4%
├─ Profitability: 0%
├─ Liquidity: 0%
├─ Coverage: 0.5%
└─ **Total PD: 2.9%** ✅

[LGD and Maturity cards NOT shown - SA mode only]

SA Results:
├─ External Rating:           A
├─ Category:                  Financial Institution
├─ Risk Weight:               **50%** ✅ [From SA tables]
└─ RWA Calculation:           $2,000,000 × 50% = **$1,000,000**
```

**Verification in Results Section:**
- ✅ PD card shown with components
- ✅ LGD card is NOT shown
- ✅ Maturity card is NOT shown
- ✅ SA card shown with risk weight and RWA calculation

**Click "Proceed to RWA Calculation"**

**Verification in index.html:**
```
Expected Pre-filled Fields:
├─ Loan ID:              CORP002 ✅
├─ Borrower Name:        XYZ Financial Services ✅
├─ Exposure Amount:      $2,000,000 ✅
├─ Sector:               Financial Services ✅
├─ Calculation Mode:     Standardized ✓ (radio selected) ✅
├─ External Rating:      A ✅
├─ Exposure Category:    Financial Institution ✅
├─ PD/LGD/Maturity:      Empty (SA mode, not needed) ✅
└─ Collateral fields:    Empty (optional for SA) ✅

Expected Notification:
"✅ Data loaded from Borrower Assessment: XYZ Financial Services (PD: 2.90%)"
```

---

## Test Case 3: Both Modes (AIRB + SA)

**Purpose:** Verify hybrid mode with both calculation approaches

**Input Data:**
```
Step 1: Borrower Information
├─ Borrower ID:           CORP003
├─ Borrower Name:         DEF Manufacturing
├─ Exposure Amount:       $1,500,000
├─ Sector:                Manufacturing
└─ Mode:                  Both (select radio button)

Step 2: Financial Metrics
├─ Debt-to-Equity:        1.0
├─ Interest Coverage:     2.5
├─ Profitability Margin:  10
└─ Liquidity Ratio:       1.5

Step 3: Collateral & Seniority
├─ Seniority:             Senior Secured - Other
├─ Collateral Type:       Equipment
└─ Collateral Value:      $750,000

Step 4: External Rating & Category
├─ External Rating:       BB+
└─ Exposure Category:     Corporate

Then click: [Calculate Risk Parameters]
```

**Expected Results:**

```
All three result cards shown:

PD Result:
├─ Base: 2.0%
├─ Leverage: 0.8%
├─ Profitability: 1.5%
├─ Liquidity: 0%
├─ Coverage: 1.5%
└─ **Total PD: 5.8%** ✅ (Risk Level: 🟡 Medium)

LGD Result:
├─ Base: 40% (Senior Secured - Other)
├─ Coverage Ratio: 750/1500 = 0.50x (< 1.0x)
├─ Coverage Adj: 0%
├─ Sector Adj: 0%
└─ **Final LGD: 40%** ✅

Maturity Result:
└─ **Suggested: 3 years** ✅

SA Result:
├─ External Rating: BB+
├─ Category: Corporate
├─ Risk Weight: **100%** ✅ [BB+ Corporate = 100%]
└─ RWA: $1,500,000 × 100% = **$1,500,000**
```

**Verification in Results Section:**
- ✅ ALL three result cards visible
- ✅ PD shown with "Medium" risk badge (5.8%)
- ✅ LGD shown as 40%
- ✅ Maturity shown as 3 years
- ✅ SA shown with 100% risk weight

**Click "Proceed to RWA Calculation"**

**Verification in index.html:**
- ✅ Calculation mode set to "Both"
- ✅ All AIRB fields pre-filled: PD 5.8, LGD 40, Maturity 3
- ✅ All SA fields pre-filled: BB+, Corporate
- ✅ Both tabs available in main calculator for calculation

---

## Test Case 4: Error Handling

**Purpose:** Verify validation and error messages

### Test 4A: Missing Required Fields
```
1. Open borrower-info.html
2. Leave Borrower ID blank
3. Click "Calculate Risk Parameters"
4. Expected: Red error message under Borrower ID field
5. Fill in Borrower ID
6. Click again - error should clear
```

### Test 4B: Invalid Numeric Values
```
1. Fill Borrower ID, Name, Exposure, Sector normally
2. Enter Debt-to-Equity: -1 (negative, should be >= 0)
3. Click "Calculate Risk Parameters"
4. Expected: Error message "Valid D/E ratio required (≥ 0)"
5. Correct to valid value and try again
```

### Test 4C: Mode-Specific Validation
```
1. Select "Both" mode
2. Fill Step 1 & 2 normally
3. Skip Step 3 (Collateral) - leave blank
4. Skip Step 4 (External Rating) - leave as "--"
5. Click "Calculate Risk Parameters"
6. Expected: Error messages for:
   - "Seniority is required for AIRB"
   - "Rating is required for SA"
7. Fill in missing fields
8. Click again - should work
```

---

## Test Case 5: Data Integrity

**Purpose:** Verify data is correctly transferred and not duplicated

**Steps:**
```
1. Open borrower-info.html
2. Fill in Test Case 1 data
3. Click "Calculate Risk Parameters"
4. Review results
5. Click "Proceed to RWA Calculation"
6. In index.html, verify all fields match:
   ├─ Loan ID = Borrower ID from form
   ├─ Borrower Name = Borrower Name from form
   ├─ Exposure = Exposure Amount from form
   └─ PD, LGD, Maturity = Calculated values
7. Do NOT click "Add Loan" yet
8. Open browser developer console (F12)
9. Check localStorage - should show "borrowerLoanData" is EMPTY
   └─ Confirms: auto-cleared after loading ✓
10. Go back to borrower-info.html (browser back button)
11. Fill DIFFERENT data (Test Case 2)
12. Click "Calculate Risk Parameters"
13. Click "Proceed to RWA Calculation"
14. Verify NEW data loaded (not old data)
    └─ Confirms: no data retention ✓
```

---

## Test Case 6: Formula Accuracy

**Purpose:** Verify calculation formulas match documentation

### Verify PD Formula:
```
Expected formula:
PD = 2.0 + (D/E × 0.8) + max(0, -ProfitMargin × 0.15) 
     + max(0, (1.5 - LiquidityRatio) × 3.0)
     + max(0, (4.0 - ICR) × 0.5)

Test with values: D/E=0.8, ICR=3.5, Margin=18%, LR=1.2
├─ 2.0 + (0.8×0.8) + max(0, -18×0.15) + max(0, (1.5-1.2)×3.0) + max(0, (4.0-3.5)×0.5)
├─ 2.0 + 0.64 + 0 + 0.9 + 0.25
└─ = 3.79% ✓ (should match)
```

### Verify LGD Formula:
```
Expected formula:
Base LGD = table(seniority)
Coverage Adj = (-10% if ratio > 1.5) or (-5% if 1.0 ≤ ratio ≤ 1.5) or 0%
Sector Adj = (-5% for RE) or (+5% for Finance) or 0%
Final = max(5%, min(90%, Base + Coverage + Sector))

Test with: Senior Unsecured, $500K collateral, $1M exposure, Manufacturing
├─ Base = 45% (Senior Unsecured)
├─ Ratio = 0.5x (< 1.0), Coverage Adj = 0%
├─ Sector = Manufacturing, Adj = 0%
├─ Final = 45% + 0 + 0 = 45% ✓ (should match)
```

---

## Troubleshooting

### Issue: "Data not loading in index.html"
```
Solution:
1. Check browser console for errors (F12 → Console)
2. Verify standardized-approach.js is loaded:
   - In borrower-info.html, look for <script src="standardized-approach.js">
3. Check localStorage is enabled in browser
4. Try clearing browser cache and reload
```

### Issue: "Results not displaying"
```
Solution:
1. Verify all required fields are filled (watch for red error messages)
2. Check browser console for JavaScript errors
3. Try different values (especially for financial metrics)
4. Ensure you clicked "Calculate Risk Parameters" button, not elsewhere
```

### Issue: "SA Risk Weight showing 0% or incorrect"
```
Solution:
1. Verify External Rating is selected (not blank)
2. Verify Exposure Category is selected
3. Check standardized-approach.js has risk weight tables loaded
4. Cross-reference with formula-reference.html for expected values
5. Example: Corporate + A rating should = 50%
```

### Issue: "Calculation mode not changing sections"
```
Solution:
1. Ensure you're clicking the radio button (not the label)
2. Wait for page to fully load before changing mode
3. Refresh page and try again
4. Check browser console for JavaScript errors
```

---

## Performance Notes

**Expected Response Times:**
- Opening borrower-info.html: < 1 second
- Entering all data: 2-3 minutes (manual entry)
- Clicking "Calculate": < 100ms (instant)
- Redirecting to index.html: < 1 second

**Browser Compatibility:**
- ✅ Chrome/Chromium (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Edge (latest)
- ⚠️ Internet Explorer (not recommended, use modern browser)

---

## Sign-Off Checklist

After running all 6 test cases, verify:

- [ ] Test Case 1 (AIRB): PD and LGD calculated correctly
- [ ] Test Case 2 (SA): Risk weight looked up correctly  
- [ ] Test Case 3 (Both): All fields calculated in both modes
- [ ] Test Case 4 (Errors): Validation works for all fields
- [ ] Test Case 5 (Data Integrity): Data correctly transferred
- [ ] Test Case 6 (Formulas): Calculations match expected values
- [ ] No console errors during any test
- [ ] Data properly clears from localStorage after transfer
- [ ] Old pdCalculatorLoan flow still works (backward compatibility)
- [ ] Responsive design works on mobile/tablet/desktop

**Overall Status:** ☐ READY FOR PRODUCTION  ☐ NEEDS FIXES

---

## Reporting Issues

If you find any bugs or issues:

1. **Document the issue:**
   - What you were trying to do
   - What input values you used
   - What you expected to happen
   - What actually happened
   - Browser type and version

2. **Provide screenshots if possible**

3. **Check the browser console:**
   - Press F12 → Console tab
   - Look for red error messages
   - Take a screenshot of the errors

4. **Send to:** ravi_phdm23@iift.edu

---

**Testing Guide v1.0 | June 3, 2026**
