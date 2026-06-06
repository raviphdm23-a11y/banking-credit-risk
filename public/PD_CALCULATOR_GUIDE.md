# Probability of Default (PD) Calculator - User Guide

## Overview

The **PD Calculator** is a rule-based tool that estimates the Probability of Default for corporate borrowers based on key financial metrics. Instead of manually entering PD values, users input financial ratios and the system calculates PD automatically.

## How It Works

### 1. Access the Calculator
- Click **"📊 PD Calculator (Rule-Based)"** button from the main calculator's right panel
- Or open `pd-calculator.html` directly

### 2. Enter Borrower Information
- **Borrower ID:** Unique identifier (e.g., CORP001)
- **Borrower Name:** Company name

### 3. Input Financial Metrics

| Metric | Definition | Example | Impact |
|--------|-----------|---------|--------|
| **Debt-to-Equity Ratio** | Total Debt / Equity | 0.8 | Leverage risk (higher = more risk) |
| **Interest Coverage Ratio** | EBITDA / Interest Expense | 3.5x | Debt service capability (higher = less risk) |
| **Profitability Margin (%)** | EBITDA or Net Profit Margin | 18% | Earnings strength (higher = less risk) |
| **Liquidity Ratio** | Current Assets / Current Liabilities | 1.5 | Short-term solvency (higher = less risk) |

### 4. Click "Calculate PD"

The system will:
- Validate all inputs
- Apply rule-based formula
- Display estimated PD percentage
- Show component breakdown
- Indicate risk level

### 5. Use the Result

The calculated PD can be:
- **Used in AIRB calculator** as the borrower's PD input
- **Used for loan pricing** to estimate interest rates
- **Used for portfolio assessment** to measure overall credit risk
- **Used for regulatory capital** as baseline PD estimate

---

## Rule-Based PD Formula

The PD is calculated using four financial metrics with standardized weights:

```
PD (%) = Base Rate + Leverage Impact + Profitability Impact + 
         Liquidity Impact + Coverage Impact

Where:
• Base Rate = 2.0% (long-term average)
• Leverage Impact = (D/E Ratio) × 0.8
• Profitability Impact = Max(0, -Margin% × 0.15)
• Liquidity Impact = Max(0, (1.5 - Current Ratio) × 3.0)
• Coverage Impact = Max(0, (4.0 - Interest Coverage) × 0.5)
```

### Component Weights

| Component | Weight | Example Impact |
|-----------|--------|-----------------|
| Leverage | 0.8 | Each 1.0 D/E ratio adds 0.80% |
| Profitability | 0.15 | Each -1% margin adds 0.15% |
| Liquidity | 3.0 | Each -0.1 ratio point adds 0.30% |
| Coverage | 0.5 | Each -1x coverage adds 0.50% |

---

## Risk Classification

Based on the calculated PD, borrowers are classified as:

| PD Range | Risk Level | Recommendation |
|----------|-----------|-----------------|
| **0% - 2%** | Very Low | Excellent credit - Standard terms |
| **2% - 5%** | Low | Good credit - Standard terms |
| **5% - 15%** | Medium | Acceptable - Enhanced monitoring |
| **15% - 30%** | High | Elevated risk - Strong covenants |
| **30%+** | Very High | Significant risk - Restrict/decline |

---

## Worked Example

### Scenario: ABC Manufacturing Corp

**Input Metrics:**
- Debt-to-Equity Ratio: 0.8
- Interest Coverage Ratio: 3.5x
- EBITDA Margin: 18%
- Current Ratio: 1.2

**Calculation:**
```
Base Rate               = 2.00%
Leverage Impact        = 0.8 × 0.8 = 0.64%
Profitability Impact   = Max(0, -18 × 0.15) = 0.00%
Liquidity Impact       = Max(0, (1.5 - 1.2) × 3.0) = 0.90%
Coverage Impact        = Max(0, (4.0 - 3.5) × 0.5) = 0.25%
────────────────────────────────────────────────
Total PD               = 3.79%
```

**Result:** Low Risk (3.79% PD)
- Approximately 3.79 in 100 probability of default within 1 year
- Good credit quality
- Suitable for standard commercial lending terms

---

## Integration with AIRB Calculator

Once you have the calculated PD:

1. **Copy the PD value** from the result (e.g., 3.79%)
2. **Go to main calculator** (← Back to Calculator)
3. **Select "AIRB Approach"** in the unified form
4. **Paste the PD value** in the PD (%) field
5. **Continue with other AIRB inputs** (LGD, EAD, Maturity, Sector)
6. **Calculate RWA and capital requirements**

---

## Key Assumptions

⚠️ **Important to understand before using:**

1. **Model Calibration**
   - Calibrated for **medium to large corporate exposures**
   - May not apply to small businesses, startups, or individuals

2. **Data Requirements**
   - Assumes **annual financial statements**
   - Requires **current/recent data**
   - Assumes **normal business operations**

3. **Economic Environment**
   - Model assumes **normal economic conditions**
   - May need adjustment during recessions or booms
   - Industry-specific factors not captured

4. **Time Horizon**
   - PD represents **1-year default probability**
   - May not apply to longer-term loans

5. **Limitations**
   - Does not capture **one-time events** (fraud, management changes)
   - Cannot replace **qualitative credit analysis**
   - Should be updated **regularly** with new financial data
   - May need **industry/geography adjustments**

---

## When to Use Rule-Based PD

✅ **Good Use Cases:**
- Quick credit screening
- Initial loan pricing estimates
- Portfolio risk overview
- Credit rating benchmarking
- Baseline for further analysis

❌ **Not Suitable For:**
- Final credit decisions (use AIRB models)
- Complex exposures needing custom models
- Highly cyclical or distressed industries
- When specific borrower data contradicts results
- Regulatory capital calculations (use approved AIRB)

---

## Comparison: Rule-Based vs AIRB PD

| Aspect | Rule-Based | AIRB Model |
|--------|-----------|-----------|
| **Complexity** | Simple | Complex |
| **Data Needed** | Basic financials | 5+ years history |
| **Time to Calculate** | Instant | Weeks/months |
| **Accuracy** | Good (±2-3%) | Very High |
| **Regulatory Use** | No | Yes (with approval) |
| **Customization** | No | Yes |
| **Best For** | Initial screening | Capital & pricing |

---

## Tips for Better Results

1. **Use Recent Data**
   - Latest annual financial statements
   - Adjust for known changes in business

2. **Verify Metrics**
   - Double-check calculations from financial statements
   - Ensure consistency in definitions

3. **Consider Qualitative Factors**
   - Management quality
   - Industry trends
   - Competitive position
   - Geographic/political risks

4. **Validate Results**
   - Compare with external credit ratings (if available)
   - Benchmark against peer companies
   - Stress test with worse-case scenarios

5. **Update Regularly**
   - Recalculate when new financials available
   - Monitor for significant changes
   - Track actual default performance vs. estimates

---

## Technical Details

### Formula Documentation
See **Complete Formula Reference** → **📊 Probability of Default (PD)** section for:
- Detailed formula explanation
- Component definitions
- Risk thresholds
- Model assumptions
- Limitations and constraints

### File Structure
- `pd-calculator.html` - Interactive calculator
- `formula-reference.html` - Formula documentation
- `standardized-approach.js` - Calculation engine
- `index.html` - Main application

### Browser Requirements
- Modern browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- No external dependencies
- Works offline

---

## Troubleshooting

**Q: Why is my PD showing 0%?**
A: Check that you've entered positive values for all metrics. Excellent metrics can result in very low PD.

**Q: Can I use this for individuals/retail credit?**
A: No, this model is designed for corporate exposures. Retail credit needs different models.

**Q: How often should I recalculate?**
A: Whenever financial statements are updated (typically annually).

**Q: What if the calculated PD doesn't match external ratings?**
A: The rule-based model is simplified. Differences of 1-3% are normal. For significant differences, use more sophisticated models.

**Q: Can I modify the formula weights?**
A: Not in the current version. Contact support if custom weighting is needed.

---

## Support & Documentation

- **Main Calculator:** Start here for AIRB and Standardized Approach
- **Formula Reference:** Complete technical documentation
- **Formula Hub:** Overview of all methodologies
- **This Guide:** PD Calculator specific guidance

---

**Version:** 1.0  
**Last Updated:** June 3, 2026  
**Status:** Production Ready ✅
