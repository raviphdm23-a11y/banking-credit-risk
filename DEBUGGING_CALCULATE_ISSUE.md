# Debugging: Calculate Button Not Working

**Issue:** When clicking "Calculate Risk Parameters" manually, nothing happens.

---

## Step 1: Check Browser Console for Errors

### How to Open Console:
1. Open the form in browser
2. Press **F12** to open Developer Tools
3. Click on **"Console"** tab
4. Look for any red error messages

### Common Errors to Look For:
```
- Uncaught TypeError: ...
- Uncaught ReferenceError: ...
- Failed to fetch (API error)
- validateInputs is not defined
```

---

## Step 2: Verify All Required Fields Are Filled

### Minimal Required Fields:
```
SECTION 1 - Financial Metrics:
[ ] Debt-to-Equity (debtToEquity)
[ ] Interest Coverage (interestCoverage)
[ ] Profitability Margin (profitabilityMargin)
[ ] Liquidity Ratio (liquidityRatio)
[ ] Loan Type (loanType)
[ ] Exposure Amount (exposureAmount)

SECTION 2 - AIRB Specific:
[ ] Seniority (seniority)
[ ] Maturity (maturityValue)
[ ] Collateral Type (collateralType)
[ ] Collateral Value (collateralValue)

SECTION 3 - KYC:
[ ] Age (kycAge)
[ ] Employment Type (kycEmploymentType)
[ ] Annual Income (kycAnnualIncome)
[ ] CIBIL Score (kycCibilScore)
[ ] Previous Default (kycPreviousDefault)
[ ] City Tier (kycCityTier)
[ ] Education (kycEducation)
[ ] Residence Type (kycResidenceType)
[ ] Loan Purpose (kycLoanPurpose)
```

---

## Step 3: Quick Test - Use Auto-Fill First

**This will help isolate the issue:**

```
1. Click [🟢 Healthy Borrower] OR [🟡 Medium Risk] OR [🔴 Risky Borrower]
2. Click [Calculate Risk Parameters]

If it works with auto-fill but not manual entry:
→ Problem is with your manual field entries
→ Check which field might be empty or invalid
```

---

## Step 4: Check Individual Field Values

### Using Browser Console:

```javascript
// Copy-paste each line into console (F12 → Console tab)
// Press Enter after each line

// Check if fields exist and have values:
console.log("debtToEquity:", document.getElementById('debtToEquity').value);
console.log("interestCoverage:", document.getElementById('interestCoverage').value);
console.log("profitabilityMargin:", document.getElementById('profitabilityMargin').value);
console.log("liquidityRatio:", document.getElementById('liquidityRatio').value);
console.log("kycAge:", document.getElementById('kycAge').value);
console.log("kycCibilScore:", document.getElementById('kycCibilScore').value);

// Test the validation function:
console.log("Validation result:", validateInputs());
```

---

## Step 5: Manual Step-by-Step Test

### Follow these exact steps:

```
1. Load page: http://127.0.0.1:5000/borrower-info.html

2. Click auto-fill button to fill form completely:
   [🟡 Medium Risk] button

3. Scroll down to see Calculate button

4. Open Console (F12)

5. Click [Calculate Risk Parameters]

6. Check console for ANY error messages

7. Look for "Calculate button clicked" message if it was added
```

---

## Step 6: Test if Function Exists

### In Browser Console, type:
```javascript
// Check if the calculate function exists
typeof calculateAllParameters

// You should see: "function"

// If you see "undefined", the function isn't loaded
```

---

## Step 7: Manually Trigger Calculate

### In Browser Console, type:
```javascript
// This will manually call the calculation function
calculateAllParameters();

// Watch for errors in console
```

---

## Most Likely Issue & Solution

### Issue #1: Form Validation Failing (Most Common)

**Symptoms:**
- Button clicked but nothing happens
- No errors in console
- Form just doesn't submit

**Solution:**
Check if any field has a red error message:
```
Look for text like:
"Must be 18–100"
"Enter a value (≥ 0)"
"Required"
```

If you see errors:
1. Scroll up to find the field with red text
2. Fix the value
3. Try Calculate again

### Issue #2: Required Dropdown Not Selected

**Symptoms:**
- Form seems complete
- Button clicked but nothing happens

**Solution:**
Make sure these dropdowns have selections (not blank):
```
- Sector (required)
- Loan Type (required)
- Seniority (required for AIRB)
- KYC fields (all required)
```

### Issue #3: JavaScript Not Loaded

**Symptoms:**
- Button exists but unresponsive
- Console shows "calculateAllParameters is not defined"

**Solution:**
```
1. Refresh page: Ctrl+F5 (hard refresh)
2. Wait 2 seconds for page to fully load
3. Check console for any load errors
4. Try again
```

---

## Quick Fix Checklist

### Before Clicking Calculate:

- [ ] Auto-fill button worked (form filled automatically)
- [ ] All visible fields have values (not blank)
- [ ] No red error messages visible on form
- [ ] Dropdown fields selected (not blank options)
- [ ] Page fully loaded (all content visible)
- [ ] Calculate button visible at bottom

### If Still Not Working:

- [ ] Open Console: F12
- [ ] Refresh page: Ctrl+F5
- [ ] Click auto-fill button
- [ ] Scroll down completely
- [ ] Click Calculate
- [ ] Check console for errors

---

## Testing Script - Add to Console

Copy this entire script into browser console (F12 → Console):

```javascript
// Comprehensive debugging script
console.log("=== DEBUGGING CALCULATE ISSUE ===");

// 1. Check function exists
console.log("Function exists:", typeof calculateAllParameters === 'function');

// 2. Check key fields
const fields = [
    'debtToEquity', 'interestCoverage', 'profitabilityMargin',
    'liquidityRatio', 'kycAge', 'kycCibilScore'
];

console.log("\n=== FIELD VALUES ===");
fields.forEach(field => {
    const elem = document.getElementById(field);
    if (elem) {
        console.log(`${field}: ${elem.value}`);
    } else {
        console.log(`${field}: NOT FOUND`);
    }
});

// 3. Test validation
console.log("\n=== VALIDATION ===");
try {
    const valid = validateInputs();
    console.log("Validation result:", valid);
} catch (e) {
    console.log("Validation error:", e.message);
}

// 4. Manually call calculate
console.log("\n=== ATTEMPTING CALCULATE ===");
try {
    calculateAllParameters();
    console.log("Calculate function called successfully");
} catch (e) {
    console.log("Calculate error:", e.message);
    console.log("Stack:", e.stack);
}
```

---

## Video of What Should Happen

When you click Calculate, you should see:

```
1. Form disappears (hidden)
2. Results section appears with:
   - PD value (e.g., "4.09%")
   - Risk Badge (e.g., "BB")
   - Result Cards with calculated values
   - Recommendation box

3. SHAP section appears below with:
   - Feature Contributions
   - Feature Interactions
   - Summary text
```

If none of this happens → validation is failing

---

## Common Validation Errors

### Error: "Must be 18–100"
**Field:** Age  
**Fix:** Enter a number between 18 and 100

### Error: "Must be 300–900"
**Field:** CIBIL Score  
**Fix:** Enter a number between 300 and 900

### Error: "Must be ≥ 100000"
**Field:** Annual Income  
**Fix:** Enter at least 100,000

### Error: "Required"
**Field:** Any dropdown  
**Fix:** Click dropdown and select a value (don't leave it blank)

### Error: "Must be 0.00–0.90"
**Field:** FOIR  
**Fix:** Enter a decimal between 0 and 0.9

---

## Guaranteed Working Method

**Follow this exact sequence:**

```
1. Load: http://127.0.0.1:5000/borrower-info.html

2. Click: [🟡 Medium Risk] button
   (Auto-fill with known-good data)

3. Alert appears: Click OK

4. Wait 2 seconds

5. Scroll down to see Calculate button

6. Click: [Calculate Risk Parameters]

If THIS doesn't work:
→ Open F12 Console
→ Type: calculateAllParameters()
→ Press Enter
→ Check for errors
```

---

## Still Not Working? Follow This:

### 1. Get Exact Error Message
```
1. Open F12 Console
2. Click Calculate button
3. Copy any error message
4. Share the exact error
```

### 2. Check Page Source
```
1. Right-click on page
2. Select "View Page Source"
3. Search for "calculateAllParameters"
4. Verify function exists in HTML
```

### 3. Check Network Tab
```
1. Open F12
2. Click "Network" tab
3. Click Calculate button
4. Look for failed requests (red text)
5. Check API responses
```

---

## Solution by Symptom

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Nothing happens, no errors | Validation fails | Check for red error messages on form |
| Console shows "not defined" | JS not loaded | Refresh page (Ctrl+F5) |
| Console shows validation error | Field invalid | Fix field value and try again |
| API fails (red in Network tab) | Server error | Check if Flask running |
| Only partial results show | SHAP computation failed | Graceful fallback, should still work |

---

## Next Steps:

1. **First:** Use auto-fill button (this proves system works)
2. **Then:** Try Calculate with auto-filled data
3. **If works:** Problem is with manual data entry
4. **If fails:** Share console error message

---

## Need Help?

Share this information:

```
1. Browser: Chrome/Firefox/Safari?
2. Error message from console (F12)?
3. Screenshot of form with values?
4. Did auto-fill button work?
5. Can you open console and run:
   calculateAllParameters()
   - What error appears?
```

---

**Let me know what error you see in the console!** 🔍
