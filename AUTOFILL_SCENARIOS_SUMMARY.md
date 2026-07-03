# Auto-Fill Test Scenarios - Summary

**Date:** July 3, 2026  
**Based On:** Selenium Automation Testing Learnings  
**Status:** ✅ Complete & Ready

---

## What Changed

### Before
```
[🔧 Auto-Fill Test Data] | [Calculate Risk Parameters]

Single button with one fixed test case
```

### After
```
[🟢 Healthy Borrower] [🟡 Medium Risk] [🔴 Risky Borrower] | [Calculate Risk Parameters]

Three buttons with distinct test scenarios covering full risk spectrum
```

---

## Three Comprehensive Test Scenarios

### Scenario 1: 🟢 Healthy Borrower (LOW RISK)

**What to Expect:**
- ✅ **Recommendation:** APPROVE
- ✅ **PD Range:** 1-2%
- ✅ **Grade:** AAA or AA
- ✅ **SHAP:** All mitigating interactions

**Borrower Profile:**
| Metric | Value | Risk Level |
|--------|-------|-----------|
| Debt-to-Equity | 1.0 | LOW |
| Interest Coverage | 10.0 | STRONG |
| Profitability | 15.0% | HIGH |
| Liquidity Ratio | 2.0 | STRONG |
| Annual Income | Rs 30L | HIGH |
| CIBIL Score | 750 | EXCELLENT |
| Late Payments | 0 | NONE |
| Employment Years | 15 | STABLE |

**Key Features:**
- Salaried professional (stable income)
- Mature age (50 years)
- Post-graduate education
- Owned residence
- Perfect payment history
- Low FOIR (0.25)

**SHAP Expectations:**
```
Top Positive Drivers:
1. High Annual Income (+3%)
2. Strong Interest Coverage (+2%)
3. High Profitability (+2%)

Interactions: MITIGATING (45-50% strength)
- Income × Coverage reduce default risk
- Multiple positive factors reinforce each other

Summary: "Excellent credit profile with strong fundamentals"
```

---

### Scenario 2: 🟡 Medium Risk Borrower (MODERATE RISK)

**What to Expect:**
- ⚠️ **Recommendation:** REFER
- ⚠️ **PD Range:** 4-5%
- ⚠️ **Grade:** BB or BBB
- ⚠️ **SHAP:** Mixed interactions

**Borrower Profile:**
| Metric | Value | Risk Level |
|--------|-------|-----------|
| Debt-to-Equity | 2.5 | MODERATE |
| Interest Coverage | 2.5 | MODERATE |
| Profitability | 8.0% | MODEST |
| Liquidity Ratio | 1.2 | ADEQUATE |
| Annual Income | Rs 15L | MODERATE |
| CIBIL Score | 650 | FAIR |
| Late Payments | 1 | RECENT |
| Employment Years | 8 | MODERATE |

**Key Features:**
- Self-employed (variable income)
- Middle age (45 years)
- Graduate education
- Owned residence
- 1 recent late payment
- Moderate FOIR (0.45)

**SHAP Expectations:**
```
Mixed Drivers (Positive & Negative):
1. Moderate Leverage (+2%)
2. Adequate Interest Coverage (-1%)
3. Thin Profit Margins (+1%)

Interactions: MIXED (25-30% strength)
- D/E × Coverage: Some mitigation
- Coverage × Profitability: Neutral effect

Summary: "Moderate risk with offsetting factors - requires RM review"
```

---

### Scenario 3: 🔴 Risky Borrower (HIGH RISK)

**What to Expect:**
- ❌ **Recommendation:** DECLINE
- ❌ **PD Range:** 20-30%+
- ❌ **Grade:** C or D
- ❌ **SHAP:** All amplifying interactions

**Borrower Profile:**
| Metric | Value | Risk Level |
|--------|-------|-----------|
| Debt-to-Equity | 5.0 | VERY HIGH |
| Interest Coverage | 1.0 | CRITICAL |
| Profitability | -5.0% | LOSS |
| Liquidity Ratio | 0.5 | POOR |
| Annual Income | Rs 8L | LOW |
| CIBIL Score | 550 | POOR |
| Late Payments | 5 | MULTIPLE |
| Employment Years | 2 | UNSTABLE |

**Key Features:**
- Self-employed/unstable (variable income)
- Young age (35 years)
- High school education
- Rented residence
- Multiple late payments
- High FOIR (0.75)
- Previous default: YES

**SHAP Expectations:**
```
All Negative Drivers:
1. Excessive Leverage (+8%)
2. Loss-Making Operations (+6%)
3. Poor Coverage Ratios (+5%)

Interactions: AMPLIFYING (60% strength)
- D/E × Losses: Compound risk significantly
- Losses × Coverage: Severe capacity issues

Summary: "Critical risk concentrations - unacceptable profile"
```

---

## Comparative Analysis

### Visual Comparison

```
                    HEALTHY     MEDIUM      RISKY
                    ═══════     ══════      ═════
                    
Debt-to-Equity      1.0 ✓       2.5 ⚠      5.0 ✗
Interest Coverage  10.0 ✓       2.5 ⚠      1.0 ✗
Profitability      15.0% ✓      8.0% ⚠     -5.0% ✗
Liquidity           2.0 ✓       1.2 ⚠      0.5 ✗
Income            30L ✓        15L ⚠       8L ✗
CIBIL Score        750 ✓        650 ⚠      550 ✗
Payment History    Perfect ✓   1 Late ⚠   5 Late ✗

Expected Decision   APPROVE     REFER      DECLINE
Expected PD         1-2%        4-5%       20-30%
Expected Grade      AAA         BB         D
SHAP Type          Mitigating   Mixed      Amplifying
```

---

## Testing Strategy

### Complete Workflow Testing

#### Test 1: Healthy Borrower (5 minutes)
```
1. Click [🟢 Healthy Borrower]
2. Scroll down → Verify all green indicators
3. Click [Calculate Risk Parameters]
4. Verify:
   - PD shows ~1-2%
   - Grade is AAA/AA
   - Recommendation shows APPROVE
   - SHAP shows positive interactions
5. Screenshot for documentation
```

#### Test 2: Medium Risk Borrower (5 minutes)
```
1. Click [🟡 Medium Risk]
2. Scroll down → Verify mixed indicators
3. Click [Calculate Risk Parameters]
4. Verify:
   - PD shows ~4-5%
   - Grade is BB/BBB
   - Recommendation shows REFER
   - SHAP shows balanced interactions
5. Screenshot for documentation
```

#### Test 3: Risky Borrower (5 minutes)
```
1. Click [🔴 Risky Borrower]
2. Scroll down → Verify all red indicators
3. Click [Calculate Risk Parameters]
4. Verify:
   - PD shows ~20-30%
   - Grade is C/D
   - Recommendation shows DECLINE
   - SHAP shows negative amplification
5. Screenshot for documentation
```

**Total Testing Time: 15 minutes for comprehensive coverage**

---

## Key Learning from Automation

### What We Learned
1. ✅ Auto-fill function works reliably when field IDs are correct
2. ✅ Form validation passes with complete data
3. ✅ Calculation completes in consistent time
4. ✅ SHAP data displays for all test cases
5. ✅ Different inputs produce different outputs

### How We Applied It
1. Created three realistic borrower profiles
2. Each covers different decision pathway
3. All use correct field IDs and mappings
4. Each generates appropriate SHAP analysis
5. Scenarios test full spectrum of outcomes

---

## Features of New Scenarios

### ✅ Comprehensive Coverage
- Low risk → Medium risk → High risk
- APPROVE → REFER → DECLINE decisions
- Positive → Mixed → Negative SHAP interactions

### ✅ Realistic Data
- Borrower demographics vary by scenario
- Financial metrics logically consistent
- Credit behavior realistic for risk level
- FOIR and other ratios appropriate

### ✅ Rapid Testing
- Three buttons instead of manual entry
- Each fills 35+ fields instantly
- No need to type data
- ~5 minutes per scenario
- ~15 minutes for complete suite

### ✅ Educational Value
- Shows how factors drive decisions
- Demonstrates SHAP interaction patterns
- Illustrates risk assessment process
- Good for training and demos

---

## Implementation Details

### Button Styling
- 🟢 **Green (#10b981)** - Healthy/Approve
- 🟡 **Orange (#f59e0b)** - Medium/Refer (default)
- 🔴 **Red (#ef4444)** - Risky/Decline

### Data Structure
```javascript
{
  healthy: {
    borrowerId: 'DEV-HEALTHY-001',
    borrowerName: 'Healthy Corp Ltd.',
    debtToEquity: 1.0,
    interestCoverage: 10.0,
    // ... 30+ more fields
    scenarioLabel: 'Healthy Borrower (Expected: APPROVE)'
  },
  medium: {
    // ... moderate risk profile
  },
  risky: {
    // ... high risk profile
  }
}
```

### Function Signature
```javascript
autoFillScenario(scenario)
// Accepts: 'healthy', 'medium', 'risky'
// Returns: Form filled + Alert shown
```

---

## Testing Checklist

### Pre-Testing
- [ ] Flask running on http://127.0.0.1:5000
- [ ] Borrower-info.html page loaded
- [ ] All three buttons visible
- [ ] No console errors

### During Testing (Each Scenario)
- [ ] Button clicked successfully
- [ ] Form fields populate correctly
- [ ] No validation errors shown
- [ ] All 35+ fields have values
- [ ] Calculate button visible
- [ ] Calculate button clickable

### After Calculation
- [ ] Results page displays
- [ ] PD value in expected range
- [ ] Grade matches expectations
- [ ] Recommendation correct
- [ ] SHAP section visible
- [ ] Feature interactions logical
- [ ] Summary text appropriate

---

## Performance Metrics

**From Selenium Testing:**
- Page load: ~2 seconds
- Auto-fill time: ~2 seconds
- Form validation: <1 second
- Calculation time: ~5 seconds
- SHAP computation: <2 seconds
- **Total per scenario: ~12-15 seconds**

---

## Files Modified/Created

| File | Change | Impact |
|------|--------|--------|
| `public/borrower-info.html` | Added 3 scenario buttons | UI Enhancement |
| `public/borrower-info.html` | New autoFillScenario() function | Functionality |
| `TEST_SCENARIOS_GUIDE.md` | Complete testing guide | Documentation |

---

## Quick Start Guide

### How to Test

```bash
# 1. Start Flask
.\run_flask.ps1

# 2. Open browser to form
http://127.0.0.1:5000/borrower-info.html

# 3. Click a scenario button
[🟢 Healthy] or [🟡 Medium] or [🔴 Risky]

# 4. Click Calculate
[Calculate Risk Parameters]

# 5. View Results
Check PD, Grade, Recommendation, SHAP data
```

### What to Look For

**Healthy Scenario:**
- ✓ PD ~1-2%
- ✓ Green indicators
- ✓ APPROVE recommendation
- ✓ Positive SHAP interactions

**Medium Scenario:**
- ✓ PD ~4-5%
- ✓ Mixed indicators  
- ✓ REFER recommendation
- ✓ Balanced SHAP interactions

**Risky Scenario:**
- ✓ PD ~20-30%
- ✓ Red indicators
- ✓ DECLINE recommendation
- ✓ Negative SHAP amplification

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Test Scenarios** | 1 (Medium) | 3 (Low/Med/High) |
| **Decision Paths** | 1 (REFER) | 3 (Approve/Refer/Decline) |
| **Testing Time** | 5 min | 15 min (comprehensive) |
| **Risk Coverage** | Partial | Complete |
| **Documentation** | Basic | Comprehensive |
| **Educational Value** | Limited | High |

---

## Ready to Test?

1. **For Quick Testing:** Click any button
2. **For Comprehensive Testing:** Test all three scenarios
3. **For Training/Demo:** Use scenarios to explain risk assessment
4. **For Troubleshooting:** Each scenario tests specific pathways

**Click a scenario button and start testing!** 🚀

---

**Status: ✅ Enhanced Auto-Fill Ready for Comprehensive Testing**
