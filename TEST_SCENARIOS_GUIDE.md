# Test Scenarios Guide - Enhanced Auto-Fill

**Date:** July 3, 2026  
**Version:** 2.0 (Multi-Scenario)  
**Status:** Ready for Testing

---

## Overview

The borrower-info.html form now includes **three pre-configured test scenarios** covering different risk profiles:

1. 🟢 **Healthy Borrower** (Low Risk → APPROVE)
2. 🟡 **Medium Risk Borrower** (Moderate Risk → REFER)
3. 🔴 **Risky Borrower** (High Risk → DECLINE)

Each button auto-fills the form with realistic borrower data and generates appropriate expected outcomes.

---

## Scenario 1: Healthy Borrower 🟢

**Expected Decision:** ✅ **APPROVE**

### When to Use
- Test the approval pathway
- Verify positive SHAP interactions
- Test risk mitigation factors
- Demonstrate successful applications

### Auto-Filled Values

**Borrower Profile:**
```
Name:              Healthy Corp Ltd.
ID:                DEV-HEALTHY-001
Age:               50 years (mature)
Employment:        Salaried (stable)
Years Employed:    15 (long tenure)
Annual Income:     Rs 30,00,000 (high)
City Tier:         Tier 1 (metro)
Education:         Post-Graduate
Residence:         Owned
Previous Default:  No
CIBIL Score:       750 (excellent)
```

**Financial Metrics:**
```
Debt-to-Equity:        1.0  (LOW - well-leveraged)
Interest Coverage:    10.0  (HIGH - strong ability to service)
Profitability Margin: 15.0% (HIGH - strong earnings)
Current Ratio:         2.0  (STRONG - good liquidity)
LTV Ratio:             75%  (acceptable)
```

**Credit Behavior:**
```
Late Payments:       0    (perfect payment history)
Months as Customer:  36   (long customer relationship)
Existing Loans:      1    (minimal debt)
FOIR:               0.25  (low obligations)
```

### Expected SHAP Analysis
- **Top Drivers:** Positive factors (high income, strong coverage)
- **Interactions:** All mitigating (synergistic positive effects)
- **Summary:** "Strong financial position with excellent coverage ratios"
- **Recommendation:** APPROVE with confidence

### Key Features to Verify
- ✅ PD very low (1-2%)
- ✅ Grade: AAA or AA
- ✅ All green (positive) factors
- ✅ Interactions amplify positive outlook
- ✅ "Refer" button should show APPROVE

---

## Scenario 2: Medium Risk Borrower 🟡

**Expected Decision:** ⚠️ **REFER**

### When to Use
- Test the typical workflow
- Verify balanced risk assessment
- Test SHAP interaction detection
- Demonstrate Relationship Manager referral

### Auto-Filled Values

**Borrower Profile:**
```
Name:              Test Borrower Inc.
ID:                DEV-MEDIUM-002
Age:               45 years
Employment:        Self Employed
Years Employed:    8 (moderate tenure)
Annual Income:     Rs 15,00,000 (moderate)
City Tier:         Tier 2 (semi-urban)
Education:         Graduate
Residence:         Owned
Previous Default:  No
CIBIL Score:       650 (fair)
```

**Financial Metrics:**
```
Debt-to-Equity:        2.5  (MODERATE - elevated leverage)
Interest Coverage:     2.5  (MODERATE - adequate but tight)
Profitability Margin:  8.0% (MODEST - thin margins)
Current Ratio:         1.2  (ADEQUATE - basic liquidity)
LTV Ratio:             75%  (acceptable)
```

**Credit Behavior:**
```
Late Payments:       1    (one recent late payment)
Months as Customer:  12   (relatively new customer)
Existing Loans:      2    (moderate debt exposure)
FOIR:               0.45  (moderate obligations)
```

### Expected SHAP Analysis
- **Top Drivers:** Mixed factors (debt offset by coverage)
- **Interactions:** Some mitigating (D/E × Coverage)
- **Summary:** "Moderate risk with offsetting factors - requires review"
- **Recommendation:** REFER to Relationship Manager for detailed assessment

### Key Features to Verify
- ✅ PD moderate (4-5%)
- ✅ Grade: BB or BBB
- ✅ Mixed factors (some red, some green)
- ✅ Key interactions visible
- ✅ "Refer" button shows REFER recommendation

---

## Scenario 3: Risky Borrower 🔴

**Expected Decision:** ❌ **DECLINE**

### When to Use
- Test the decline pathway
- Verify risk detection
- Test high-risk SHAP analysis
- Demonstrate risk concentration

### Auto-Filled Values

**Borrower Profile:**
```
Name:              Struggling Business Ltd.
ID:                DEV-RISKY-003
Age:               35 years
Employment:        Self Employed/Unemployed
Years Employed:    2 (very short tenure)
Annual Income:     Rs 8,00,000 (low)
City Tier:         Tier 2 (semi-urban)
Education:         High School
Residence:         Rented (unstable)
Previous Default:  Yes (prior default)
CIBIL Score:       550 (poor)
```

**Financial Metrics:**
```
Debt-to-Equity:        5.0   (VERY HIGH - over-leveraged)
Interest Coverage:     1.0   (CRITICAL - barely serviceable)
Profitability Margin: -5.0%  (NEGATIVE - loss-making)
Current Ratio:         0.5   (POOR - severe liquidity crisis)
LTV Ratio:             75%   (unacceptable given risk)
```

**Credit Behavior:**
```
Late Payments:       5    (multiple late payments)
Months as Customer:  6    (very new customer)
Existing Loans:      4    (high debt load)
Dependents:          5    (high family obligations)
FOIR:               0.75  (excessive obligations)
```

### Expected SHAP Analysis
- **Top Drivers:** All negative factors (high leverage, losses, defaults)
- **Interactions:** Amplifying (debt × losses compound risk)
- **Summary:** "Multiple risk concentrations - critical factors align adversely"
- **Recommendation:** DECLINE - Unacceptable risk profile

### Key Features to Verify
- ✅ PD high (20-30%+)
- ✅ Grade: C or D
- ✅ All red (risk) factors
- ✅ Interactions amplify negative outlook
- ✅ "Refer" button shows DECLINE recommendation

---

## How to Use the Scenarios

### Step 1: Open the Form
Navigate to: **http://127.0.0.1:5000/borrower-info.html**

### Step 2: Select a Scenario
You'll see **three colored buttons**:

```
[Healthy Borrower] [Medium Risk] [Risky Borrower] | Calculate Risk Parameters |
```

- 🟢 **Green button** = Healthy/Low-risk
- 🟡 **Orange button** = Medium-risk
- 🔴 **Red button** = Risky/High-risk

### Step 3: Click Your Scenario
The form auto-fills with appropriate test data for that scenario.

### Step 4: Verify the Data
Scroll down and check:
- Financial metrics filled
- KYC data populated
- All required fields complete

### Step 4: Click Calculate
Click **"Calculate Risk Parameters"** button

### Step 5: Review Results
Check:
- **PD value** (should match expectation)
- **Grade** (should match expectation)
- **Recommendation** (APPROVE/REFER/DECLINE)
- **SHAP data** (interactions and drivers)
- **Feature importance** (Tier 1 and Tier 2)

---

## Testing Workflow by Scenario

### Test Healthy Borrower (5 min)
```
1. Click [Healthy Borrower]
2. Scroll down, verify data
3. Click [Calculate Risk Parameters]
4. Expected: PD ~1-2%, Grade AAA, Recommendation APPROVE
5. Verify: All green factors, mitigating interactions
```

### Test Medium Risk Borrower (5 min)
```
1. Click [Medium Risk]
2. Scroll down, verify data
3. Click [Calculate Risk Parameters]
4. Expected: PD ~4-5%, Grade BB, Recommendation REFER
5. Verify: Mixed factors, balanced interactions
```

### Test Risky Borrower (5 min)
```
1. Click [Risky Borrower]
2. Scroll down, verify data
3. Click [Calculate Risk Parameters]
4. Expected: PD ~20-30%, Grade D, Recommendation DECLINE
5. Verify: All red factors, amplifying interactions
```

**Total Testing Time: ~15 minutes for all scenarios**

---

## Field Mappings by Scenario

### Scenario-Specific Variables

| Field | Healthy | Medium | Risky |
|-------|---------|--------|-------|
| **Debt-to-Equity** | 1.0 | 2.5 | 5.0 |
| **Interest Coverage** | 10.0 | 2.5 | 1.0 |
| **Profitability** | 15.0% | 8.0% | -5.0% |
| **Liquidity Ratio** | 2.0 | 1.2 | 0.5 |
| **Annual Income** | 30,00,000 | 15,00,000 | 8,00,000 |
| **CIBIL Score** | 750 | 650 | 550 |
| **Late Payments** | 0 | 1 | 5 |
| **Employment Years** | 15 | 8 | 2 |
| **Previous Default** | No | No | Yes |
| **City Tier** | 1 | 2 | 2 |
| **Education** | Post-Grad | Graduate | High School |
| **Residence** | Owned | Owned | Rented |
| **External Rating** | AAA | BB | D |

---

## SHAP Analysis Expectations

### Healthy Borrower - Expected SHAP Output
```
Top Drivers:
1. High Annual Income              (+3%)
2. Strong Interest Coverage        (+2%)
3. High Profitability Margin       (+2%)

Feature Interactions:
1. Income × Coverage    (MITIGATING - 45%)
2. Coverage × Profitability (MITIGATING - 35%)
3. All ratios strongly positive

Summary: "Strong financial position with excellent coverage 
         ratios. Key synergy: high income + strong coverage
         significantly reduce default probability."
```

### Medium Borrower - Expected SHAP Output
```
Top Drivers:
1. Moderate Leverage               (+2%)
2. Adequate Interest Coverage      (-1%)
3. Thin Profit Margins             (+1%)

Feature Interactions:
1. Leverage × Coverage  (MITIGATING - 25%)
2. Coverage × Profitability (NEUTRAL - 10%)
3. Mixed effects

Summary: "Moderate risk profile with offsetting factors.
         Key interaction: adequate coverage partially mitigates
         elevated leverage. Requires RM review for final decision."
```

### Risky Borrower - Expected SHAP Output
```
Top Drivers:
1. Excessive Leverage              (+8%)
2. Loss-Making Operations          (+6%)
3. Poor Coverage Ratios            (+5%)

Feature Interactions:
1. Leverage × Losses   (AMPLIFYING - 60%)
2. Losses × Coverage (AMPLIFYING - 45%)
3. All factors align negatively

Summary: "Critical risk concentrations. Key amplification:
         high debt + negative profitability create severe
         debt service capacity issues. Unacceptable risk."
```

---

## Verification Checklist

### For Each Scenario Test

- [ ] Correct scenario button clicked
- [ ] All form fields populated
- [ ] No validation errors shown
- [ ] Calculate button clicked
- [ ] Results page appears
- [ ] PD value in expected range
- [ ] Grade matches expectations
- [ ] Recommendation correct
- [ ] SHAP data visible
- [ ] Feature interactions logical
- [ ] Summary text appropriate

---

## Quick Reference Table

| Aspect | Healthy | Medium | Risky |
|--------|---------|--------|-------|
| **Button Color** | 🟢 Green | 🟡 Orange | 🔴 Red |
| **Expected PD** | 1-2% | 4-5% | 20-30% |
| **Expected Grade** | AAA/AA | BB/BBB | C/D |
| **Expected Recommendation** | APPROVE | REFER | DECLINE |
| **SHAP Type** | All Mitigating | Mixed | All Amplifying |
| **Risk Level** | Low | Medium | High |
| **Use Case** | Success Path | Typical Path | Decline Path |

---

## Tips for Testing

✅ **Test all three scenarios** - covers full risk spectrum
✅ **Check SHAP interactions** - validates Tier 2 feature
✅ **Compare scenarios** - understand risk drivers
✅ **Take screenshots** - document expected outcomes
✅ **Verify recommendations** - ensure decision logic works
✅ **Check feature explanations** - confirm interpretability

---

## Troubleshooting

### Form Not Filling
- Check browser console (F12) for errors
- Ensure Flask is running
- Try a different scenario

### SHAP Data Not Showing
- Wait 5 seconds after clicking Calculate
- Check if calculation completed
- Scroll down to see Tier 2 section

### Unexpected Recommendation
- Verify all fields filled correctly
- Check if data matches scenario expectations
- Review SHAP explanation for drivers

---

## Summary

**Three Test Scenarios Available:**

1. 🟢 **Healthy** → Tests approval workflow → Expect APPROVE
2. 🟡 **Medium** → Tests typical workflow → Expect REFER  
3. 🔴 **Risky** → Tests decline workflow → Expect DECLINE

Each button auto-fills realistic borrower data. Perfect for comprehensive testing of the Tier 2 SHAP system!

---

**Ready to Test? Click a scenario button and calculate!** 🚀
