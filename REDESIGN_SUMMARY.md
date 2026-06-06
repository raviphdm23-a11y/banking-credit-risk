# Form Redesign Summary - Unified AIRB + Standardized Approach

## Changes Made

### ✅ UI Layout
- **Removed:** Tab-based methodology selector at top
- **Added:** Single unified form on one page
- **Layout:** 
  - Top row: 3 common fields (Loan ID, Borrower Name, Exposure Amount)
  - Middle: 2-column side-by-side layout
    - Left: AIRB Parameters (Sector, PD, LGD, Maturity)
    - Right: Standardized Approach (Rating, Category, Collateral)
  - Bottom: Radio buttons to select calculation method (AIRB / SA / Both)
  - Action buttons: Add Loan, Clear

### ✅ JavaScript Functions
**New/Updated:**
- `addLoan()` - Now handles unified form with all three calculation modes
  - AIRB mode: Validates and calculates AIRB loans
  - Standardized mode: Validates and calculates SA loans  
  - Both mode: Adds 2 loans (AIRB + SA) for the same borrower
- `clearForm()` - Clears all fields (AIRB, SA, and common)
- `validateAIRBLoan()` - Validates AIRB-specific fields
- `validateCommonFields()` - Validates Loan ID, Borrower, Exposure
- `toggleSACollateral()` - Shows/hides collateral section

**Removed:**
- `switchMethodology()` - No longer needed
- `addSALoan()` - Merged into unified `addLoan()`
- `clearSAForm()` - Merged into unified `clearForm()`
- `updateTableHeader()` - Table now shows all columns for both methods
- `currentMethodology` variable - Replaced by radio button `calcMode`

### ✅ Table Rendering
- Table now intelligently renders both AIRB and SA loans
- AIRB rows show: Sector, EAD, PD%, LGD%
- SA rows show: Category, Exposure, Rating, Risk Wt%
- Mixed portfolios (AIRB + SA loans) display correctly

### ✅ HTML Elements Modified
- Header updated: "Credit Risk Calculator" (was "AIRB Credit Risk Calculator")
- Form labels updated to be optional ("Select Rating" instead of "External Rating *")
- Info-box message updated to explain unified interface
- Collateral section now nested inside Standardized Approach column
- Calculation mode selector uses radio buttons for clear selection

---

## Testing Checklist

1. **AIRB Only Mode**
   - Fill: Loan ID, Borrower, Exposure, Sector, PD, LGD, Maturity
   - Select: "AIRB Approach" radio
   - Click: Add Loan
   - Expected: AIRB loan appears in table with sector/PD/LGD columns

2. **Standardized Approach Only Mode**
   - Fill: Loan ID, Borrower, Exposure, Rating, Category
   - Select: "Standardized Approach" radio
   - Click: Add Loan
   - Expected: SA loan appears in table with category/rating/RW columns

3. **Both Methods Mode**
   - Fill: All fields (both AIRB and SA)
   - Select: "Both Methods" radio
   - Click: Add Loan
   - Expected: 2 rows added (1 AIRB, 1 SA)

4. **Collateral Functionality**
   - Check "Exposure has Collateral?" checkbox
   - Collateral section should appear
   - Fill Type, Value, Haircut
   - Add loan and verify adjustment applied

5. **Validation**
   - Try adding with empty fields
   - Check error messages appear correctly
   - Verify field-specific errors display

6. **Portfolio & Exports**
   - Add multiple loans (mix of AIRB and SA)
   - Verify summary calculates correctly
   - Test Export to CSV/JSON

---

## Notes

- All existing functionality preserved (portfolio management, exports, summary)
- Same calculation engines used (no business logic changes)
- Responsive design maintained
- Formula reference links still work
- Data persistence (localStorage) unchanged

---

## Version
- **Old:** AIRB Credit Risk Calculator v1.0
- **New:** Credit Risk Calculator v2.0
- **Date:** June 3, 2026
