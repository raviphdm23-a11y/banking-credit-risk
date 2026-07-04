# End-User Testing Guide: Tier 2 SHAP Features

**Date:** July 3, 2026  
**Version:** 1.0  
**Status:** Ready for Testing

---

## Quick Start

### Step 1: Start the Application

**Option A: Using PowerShell (Easiest)**
```powershell
cd "C:\Users\Arnav\OneDrive\Desktop\Axis_bank_credit_risk_analysis"
.\run_flask.ps1
```

**Option B: Using Python Directly**
```powershell
cd "C:\Users\Arnav\OneDrive\Desktop\Axis_bank_credit_risk_analysis"
.\venv310\Scripts\python.exe app.py
```

You should see:
```
Starting Banking Credit Risk Calculator API
Environment: development
Debug mode: True
CORS enabled for all /api/* routes
 * Running on http://127.0.0.1:5000
```

### Step 2: Open in Browser

Navigate to: **http://127.0.0.1:5000**

---

## Testing Path 1: Credit Risk Calculator (Main Feature)

### 1.1 Navigate to Credit Risk Assessment

1. From the home page, click **"Credit Risk Calculator"**
2. You'll see the borrower information form
3. Form has two sections:
   - **Section 1:** Basic Financial Metrics
   - **Section 2:** Borrower Details

### 1.2 Fill in Test Data

**Use this risky borrower profile:**

**Financial Metrics (Section 1):**
```
Debt-to-Equity Ratio:           2.5
Interest Coverage Ratio:        2.5
Net Profit Margin (%):          8.0
Current Ratio (Liquidity):      1.2
Loan Exposure (Rs):             5,000,000
Seniority:                      Senior Secured (Other)
Maturity (years):               3.0
```

**Borrower Details (Section 2):**
```
Collateral Type:                Real Estate
Collateral Value (Rs):          3,000,000
Age:                            45
Employment Type:                Self Employed (2)
Years Employed:                 8
Annual Income (Rs):             1,500,000
FOIR (Fixed Obligation/Income): 0.45
Number of Dependents:           3
City Tier:                       Tier 2 (2)
Education:                      Graduate (3)
Residence Type:                 Owned (1)
Loan Purpose:                   Business Expansion (2)
CIBIL Score:                    650
Previous Default Flag:          No (0)
Months as Customer:             12
Late Payments (past 12m):       1
Existing Loans:                 2
Existing Products:              2
Rural Area:                     No (0)
Country Code:                   IND
```

### 1.3 Submit Assessment

1. Click **"Calculate & Get Recommendation"** button
2. **Wait 1-2 seconds** for the calculation
3. You should see: **"Assessment complete! Refer to Relationship Manager →"**
4. Click the link to proceed

---

## Testing Path 2: Assessment Results (NEW - Tier 2 Feature!)

This is where you see the **SHAP analysis** for the first time.

### 2.1 View Results Page

After clicking the referral link, you'll see the new **Assessment Results** page with:

#### **Top Section: PD & Rating**
You should see **4 metrics displayed:**
```
┌─────────────────────────────────────────┐
│ Probability of Default (PD)             │
├─────────────────────────────────────────┤
│ Point Estimate:    4.09%                │
│ Risk Grade:        BB                   │
│ Lower Bound (80%): 2.47%                │
│ Upper Bound (80%): 5.71%                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Rating & Recommendation                 │
├─────────────────────────────────────────┤
│ Grade: BB (Speculative)                 │
│ [REFER - Orange Box]                    │
│ "Speculative grade with uncertainties"  │
└─────────────────────────────────────────┘
```

**What to verify:**
- ✅ PD is between 0-100% (should be ~4%)
- ✅ Grade shows "BB" with orange color
- ✅ Recommendation shows "REFER" in orange
- ✅ Confidence bounds make sense (low < point < high)

### 2.2 Tier 1: Feature Attribution (Existing)

Scroll down to see **"Tier 1: Feature Attribution"** section.

You should see a **ranked list of top features:**

```
Tier 1: Feature Attribution (XGBoost Importance)

1. Debt-to-Equity Ratio                +0.286%    [RED arrow]
2. Current Ratio (Liquidity)           -0.204%    [GREEN arrow]
3. Net Profit Margin (%)               +0.048%    [RED arrow]
4. (more features...)
```

**What to verify:**
- ✅ Top 10 features are listed
- ✅ Features have % contributions
- ✅ Red arrows = increases risk
- ✅ Green arrows = decreases risk
- ✅ Debt-to-Equity is #1 (riskiest factor)

### 2.3 Tier 2: SHAP Analysis (NEW!)

**This is the new Tier 2 feature!** Scroll down further to see it.

#### **2.3a SHAP Feature Contributions**

You should see:

```
Tier 2: SHAP Analysis (Feature Interactions)

Feature Contributions (SHAP Values):

1. Debt-to-Equity Ratio                +0.286%    [RED arrow]
2. Liquidity Ratio                     -0.278%    [GREEN arrow]
3. Interest Coverage                   -0.257%    [GREEN arrow]
...
```

**Key Differences from Tier 1:**
- Tier 1 = Simple importance ranking
- **Tier 2 = True additive contributions** (accounts for interactions)
- SHAP values are mathematically rigorous

**What to verify:**
- ✅ SHAP values present and different from Tier 1
- ✅ Values sum approximately to the PD
- ✅ Red = increases risk, Green = decreases risk

#### **2.3b SHAP Summary**

Look for the **purple box** with:

```
Summary: Top drivers: de_ratio, liquidity_ratio, 
interest_coverage. Key interaction: de_ratio × 
liquidity_ratio (mitigating).
```

**What to verify:**
- ✅ Summary mentions top drivers
- ✅ Summary mentions a key interaction
- ✅ Makes intuitive sense

#### **2.3c Feature Interactions**

Below the summary, see **"Feature Interactions"** section:

```
Feature Interactions:

1. Debt-to-Equity × Liquidity Ratio
   [MITIGATING] Strength: 60.72%
   "de_ratio (2.50) and liquidity_ratio (1.20) 
    together mitigate risk"

2. Debt-to-Equity × Interest Coverage
   [MITIGATING] Strength: 38.01%
   ...

3. Liquidity × Interest Coverage
   [MITIGATING] Strength: 38.01%
   ...
```

**What to verify:**
- ✅ Shows top 3 feature interactions
- ✅ Shows interaction type (Amplifying or Mitigating)
- ✅ Shows interaction strength (0-100%)
- ✅ Provides plain English explanation
- ✅ All interactions are MITIGATING (good news - they reduce risk!)

---

## Test Scenarios

### Scenario 1: Healthy Borrower (Should APPROVE)

**Fill in:**
```
Debt-to-Equity Ratio:      1.0  (LOW)
Interest Coverage:         10.0 (HIGH)
Net Profit Margin:         15.0 (HIGH)
Current Ratio:             2.0  (HIGH)
CIBIL Score:               750  (EXCELLENT)
Late Payments:             0    (NONE)
```

**Expected Results:**
- ✅ PD should be very low (~1-2%)
- ✅ Grade should be AAA or AA
- ✅ **Recommendation: APPROVE** (green box)
- ✅ Tier 2 interactions should all be mitigating
- ✅ Positive factors highlighted in green

### Scenario 2: Risky Borrower (Should DECLINE)

**Fill in:**
```
Debt-to-Equity Ratio:      5.0  (VERY HIGH)
Interest Coverage:         1.0  (CRITICAL)
Net Profit Margin:         -5.0 (LOSS)
Current Ratio:             0.5  (CRITICAL)
CIBIL Score:               550  (POOR)
Late Payments:             5    (MANY)
Existing Default:          Yes
```

**Expected Results:**
- ✅ PD should be high (~20-30%)
- ✅ Grade should be C or D
- ✅ **Recommendation: DECLINE** (red box)
- ✅ Tier 2 interactions showing amplifying effects
- ✅ Risk factors highlighted in red

### Scenario 3: Medium Risk (Should REFER)

**Fill in:**
```
Debt-to-Equity Ratio:      2.5
Interest Coverage:         2.5
Net Profit Margin:         8.0
Current Ratio:             1.2
CIBIL Score:               650
Late Payments:             1
```

**Expected Results:**
- ✅ PD should be medium (~4-5%)
- ✅ Grade should be BB or BBB
- ✅ **Recommendation: REFER** (orange box)
- ✅ Mixed factors - some amplifying, some mitigating
- ✅ Uncertainty bands relatively wide

---

## What to Look For (Verification Checklist)

### ✅ General Functionality
- [ ] Page loads without errors
- [ ] All sections render properly (no missing text)
- [ ] Responsive design works (try resizing browser)
- [ ] Loading spinner appears briefly, then disappears
- [ ] No console errors (check browser DevTools F12)

### ✅ Tier 1: Feature Attribution
- [ ] Top 10 features are listed
- [ ] Contribution percentages shown
- [ ] Direction indicators (red/green arrows) present
- [ ] Ranking makes logical sense
- [ ] Total contributions roughly sum to PD

### ✅ Tier 2: SHAP Analysis (NEW!)
- [ ] SHAP section appears below Tier 1
- [ ] Feature contributions list is present
- [ ] Interactions list shows 3 items
- [ ] Summary box with purple background
- [ ] Interaction types correct (amplifying/mitigating)
- [ ] Explanations are understandable

### ✅ Data Quality
- [ ] PD values between 0-100%
- [ ] Rating grades valid (AAA, AA, A, BBB, BB, B, CCC, D)
- [ ] Recommendations valid (APPROVE, REFER, DECLINE)
- [ ] Confidence bounds: low < point < high
- [ ] SHAP values sum approximately to PD

### ✅ Color Coding
- [ ] Healthy factors = Green
- [ ] Risky factors = Red
- [ ] Neutral/interactions = Purple
- [ ] Recommendation boxes color-coded (green/orange/red)

---

## Testing with API (Advanced)

If you want to test the API directly:

### Using Postman or cURL

**Test the new endpoint:**

```bash
curl -X POST http://127.0.0.1:5000/api/assess-borrower-with-shap \
  -H "Content-Type: application/json" \
  -d '{
    "de_ratio": 2.5,
    "interest_coverage": 2.5,
    "profitability": 8.0,
    "liquidity_ratio": 1.2,
    "exposure": 5000000,
    "seniority": "Senior Secured (Other)",
    "maturity": 3
  }'
```

**Expected Response:**
```json
{
  "report_id": "uuid-string",
  "timestamp": "2026-07-03T...",
  "model_version": "run_20260702_...",
  "pd": {
    "point": 0.0409,
    "low": 0.0247,
    "high": 0.0571,
    ...
  },
  "rating": {
    "grade": "BB",
    ...
  },
  "shap": {
    "base_value": 0.545765,
    "feature_contributions": [...],
    "interactions": [...],
    "summary": "...",
    ...
  }
}
```

**Verify:**
- ✅ Response contains "shap" field
- ✅ SHAP has feature_contributions array
- ✅ SHAP has interactions array
- ✅ All values are valid JSON

---

## Troubleshooting

### Issue: Page shows "Loading..." forever

**Solution:**
1. Check browser console (F12 → Console tab)
2. Look for error messages
3. Try refreshing the page
4. Restart Flask: `.\run_flask.ps1`

### Issue: No SHAP data visible

**Likely cause:** Model not loaded or SHAP computation failed (graceful fallback)

**Check:**
1. Verify model exists: `ls ml_models/pd_model.pkl`
2. Check Flask console for errors
3. Try a simpler borrower profile first

### Issue: Results page shows "Error Loading Results"

**Solution:**
1. Go back to home page
2. Start a new assessment
3. Make sure all required fields are filled
4. Check browser console for specific error

### Issue: Latency is very slow (>2 seconds)

**Normal for test environment:**
- First call: 400-500ms (includes SHAP computation)
- Subsequent calls: Much faster (cached)
- Production with gunicorn will be 1.5-2x faster

---

## Performance Testing (Optional)

### Test Caching Speed

1. Fill in the same borrower details
2. Submit first time - **note the latency** (400-500ms)
3. Submit again with **identical details** - **should be much faster** (10-50ms)
4. Verify in console that caching is working

### Test with Different Inputs

1. Change ONE value (e.g., CIBIL score)
2. Submit - should compute new SHAP values
3. Verify results changed appropriately

---

## Success Criteria

You'll know Tier 2 is working when:

✅ **Functional**
- Assessment results page loads without errors
- SHAP section appears with all data
- Feature interactions displayed correctly
- Explanations make intuitive sense

✅ **Accurate**
- PD values reasonable (0-100%)
- Grades and recommendations logical
- SHAP values sum to approximately the PD
- Interactions correctly identified

✅ **Responsive**
- First call completes in <1 second
- Cached calls are very fast (<100ms)
- No memory issues (no crashes after multiple calls)
- All data loads correctly

✅ **User-Friendly**
- Colors are intuitive (red=bad, green=good)
- Explanations are clear and understandable
- Layout is clean and organized
- Mobile view works properly

---

## What's Different from Before (Tier 1)

### Tier 1 Only (Before)
```
Features ranked by importance
Simple ranking: Feature 1, Feature 2, Feature 3...
"This feature is important"
```

### Tier 2 (NEW!)
```
Features ranked by SHAP values (true contribution)
Shows how features combine (interactions)
"D/E × Liquidity together REDUCE risk by 61%"
Mathematically rigorous attribution
Feature interactions explicitly explained
```

---

## Feedback & Issues

If you find any issues:

1. **Screenshot the error** (including any red text)
2. **Note the borrower inputs** you used
3. **Check the browser console** (F12 → Console)
4. **Report:** What you did, what you expected, what you got

Common things to check:
- Does the page load at all?
- Do you see Tier 1 (feature attribution)?
- Do you see Tier 2 (SHAP analysis)?
- Are the values reasonable?
- Does the color coding make sense?

---

## Next Steps

After testing:

1. ✅ Verify basic functionality works
2. ✅ Test with 3-5 different borrower profiles
3. ✅ Check that SHAP values make sense
4. ✅ Confirm performance is acceptable
5. ✅ Report any issues or feedback

**Questions?** Check the documentation files:
- `TIER2_SHAP_IMPLEMENTATION_PLAN.md` - Technical details
- `TIER2_API_SCHEMA.md` - API format specification
- `TIER2_PHASE5_COMPLETION.md` - Frontend details

---

**Happy Testing!** 🚀

Your feedback helps us improve the system. Enjoy exploring the new SHAP-powered insights!
