# Test Case Template
## Copy & Paste Ready Format

---

## 📋 Blank Template (Copy This)

Use this template to quickly create new test cases. Copy the section below and fill in your values.

```
Test ID              | TC_______
Test Description     | _______________________________________________
Borrower ID          | ________
Borrower Name        | _________________________________
Sector               | _________________________________
Exposure Amount      | ___________
Calc Mode            | [airb / standardized / both]
Debt to Equity       | ___.___
Interest Coverage    | ___.___
Profitability Margin | ___.__
Liquidity Ratio      | ___.___
Seniority            | _________________________________
Loan Type            | _________________________________
Collateral Type      | _________________________________
Collateral Value     | ___________
External Rating      | ___
Exposure Category    | _________________________________
Expected PD Min      | ___.___
Expected PD Max      | ___.___
Expected LGD Min     | ___.___
Expected LGD Max     | ___.___
```

---

## 🎯 Pre-Filled Templates by Scenario

### Template A: Conservative Borrower
Best for: Testing low-risk scenarios
```
Test ID              | TC_CONSERVATIVE_001
Test Description     | Low leverage, high profitability, strong collateral
Borrower ID          | CORP_LR_001
Borrower Name        | Established Manufacturing Corp
Sector               | Manufacturing
Exposure Amount      | 5000000
Calc Mode            | both
Debt to Equity       | 0.4
Interest Coverage    | 5.5
Profitability Margin | 28
Liquidity Ratio      | 2.0
Seniority            | Senior Secured - Real Estate
Loan Type            | Term Loan Long
Collateral Type      | Real Estate
Collateral Value     | 3000000
External Rating      | A
Exposure Category    | Corporate
Expected PD Min      | 1.5
Expected PD Max      | 2.5
Expected LGD Min     | 28
Expected LGD Max     | 35
```

### Template B: Growth Company
Best for: Testing moderate-risk scenarios
```
Test ID              | TC_GROWTH_001
Test Description     | Higher leverage, growth stage, moderate collateral
Borrower ID          | CORP_GR_001
Borrower Name        | Tech Solutions Startup
Sector               | Technology
Exposure Amount      | 3000000
Calc Mode            | both
Debt to Equity       | 1.5
Interest Coverage    | 2.8
Profitability Margin | 15
Liquidity Ratio      | 1.3
Seniority            | Senior Unsecured
Loan Type            | Term Loan Short
Collateral Type      | Equipment
Collateral Value     | 800000
External Rating      | BBB
Exposure Category    | Corporate
Expected PD Min      | 4.5
Expected PD Max      | 5.5
Expected LGD Min     | 42
Expected LGD Max     | 48
```

### Template C: High Risk
Best for: Testing stress scenarios
```
Test ID              | TC_HIGHRISK_001
Test Description     | Very high leverage, weak margins, minimal collateral
Borrower ID          | CORP_HR_001
Borrower Name        | Struggling Retailer Inc
Sector               | Retail
Exposure Amount      | 2000000
Calc Mode            | both
Debt to Equity       | 3.0
Interest Coverage    | 1.2
Profitability Margin | -2
Liquidity Ratio      | 0.9
Seniority            | Subordinated
Loan Type            | Working Capital
Collateral Type      | Inventory
Collateral Value     | 200000
External Rating      | BB-
Exposure Category    | Corporate
Expected PD Min      | 12.0
Expected PD Max      | 15.0
Expected LGD Min     | 65
Expected LGD Max     | 80
```

### Template D: AIRB Only
Best for: Testing advanced internal ratings based approach
```
Test ID              | TC_AIRB_001
Test Description     | AIRB methodology only, no external rating needed
Borrower ID          | CORP_AI_001
Borrower Name        | Manufacturing Specialist
Sector               | Manufacturing
Exposure Amount      | 4000000
Calc Mode            | airb
Debt to Equity       | 0.7
Interest Coverage    | 4.0
Profitability Margin | 22
Liquidity Ratio      | 1.6
Seniority            | Senior Secured - Financial Assets
Loan Type            | Term Loan Long
Collateral Type      | Financial Assets
Collateral Value     | 2000000
External Rating      | (leave blank)
Exposure Category    | (leave blank)
Expected PD Min      | 2.8
Expected PD Max      | 3.5
Expected LGD Min     | 32
Expected LGD Max     | 38
```

### Template E: Standardized Approach Only
Best for: Testing standardized approach with external ratings
```
Test ID              | TC_SA_001
Test Description     | SA methodology only, external rating required
Borrower ID          | CORP_SA_001
Borrower Name        | Financial Services Ltd
Sector               | Financial Services
Exposure Amount      | 10000000
Calc Mode            | standardized
Debt to Equity       | 0.8
Interest Coverage    | 6.0
Profitability Margin | 18
Liquidity Ratio      | 1.7
Seniority            | (leave blank)
Loan Type            | (leave blank)
Collateral Type      | None
Collateral Value     | 0
External Rating      | AA
Exposure Category    | Financial Institution
Expected PD Min      | 1.5
Expected PD Max      | 2.5
Expected LGD Min     | 20
Expected LGD Max     | 25
```

### Template F: Sovereign Exposure
Best for: Testing government/sovereign bonds
```
Test ID              | TC_SOVEREIGN_001
Test Description     | Low risk sovereign exposure, AAA rated government
Borrower ID          | SOV_001
Borrower Name        | Ministry of Finance - Country X
Sector               | Government
Exposure Amount      | 50000000
Calc Mode            | standardized
Debt to Equity       | 0.1
Interest Coverage    | 15.0
Profitability Margin | 8
Liquidity Ratio      | 2.5
Seniority            | (leave blank)
Loan Type            | (leave blank)
Collateral Type      | None
Collateral Value     | 0
External Rating      | AAA
Exposure Category    | Sovereign
Expected PD Min      | 0.3
Expected PD Max      | 0.8
Expected LGD Min     | 10
Expected LGD Max     | 20
```

### Template G: Boundary Test - Maximum D/E
Best for: Testing extreme leverage scenarios
```
Test ID              | TC_BOUNDARY_MAXDE
Test Description     | Boundary: Maximum sustainable D/E ratio
Borrower ID          | CORP_B1_001
Borrower Name        | Maximum Leverage Corp
Sector               | Manufacturing
Exposure Amount      | 2500000
Calc Mode            | both
Debt to Equity       | 5.0
Interest Coverage    | 0.9
Profitability Margin | 5
Liquidity Ratio      | 0.7
Seniority            | Subordinated
Loan Type            | Working Capital
Collateral Type      | None
Collateral Value     | 0
External Rating      | CCC
Exposure Category    | Corporate
Expected PD Min      | 25.0
Expected PD Max      | 35.0
Expected LGD Min     | 75
Expected LGD Max     | 85
```

### Template H: Boundary Test - Minimum ICR
Best for: Testing minimum interest coverage scenarios
```
Test ID              | TC_BOUNDARY_MINICR
Test Description     | Boundary: Minimum viable interest coverage
Borrower ID          | CORP_B2_001
Borrower Name        | Tight Coverage Corp
Sector               | Retail
Exposure Amount      | 1500000
Calc Mode            | both
Debt to Equity       | 1.2
Interest Coverage    | 0.5
Profitability Margin | 8
Liquidity Ratio      | 1.1
Seniority            | Senior Unsecured
Loan Type            | Term Loan Short
Collateral Type      | Equipment
Collateral Value     | 300000
External Rating      | B
Exposure Category    | Corporate
Expected PD Min      | 18.0
Expected PD Max      | 22.0
Expected LGD Min     | 45
Expected LGD Max     | 55
```

### Template I: Zero Collateral Test
Best for: Testing unsecured lending scenarios
```
Test ID              | TC_NOCOLLATERAL_001
Test Description     | Unsecured lending: Zero collateral value
Borrower ID          | CORP_NC_001
Borrower Name        | Unsecured Services Inc
Sector               | Technology
Exposure Amount      | 3000000
Calc Mode            | airb
Debt to Equity       | 1.1
Interest Coverage    | 3.2
Profitability Margin | 20
Liquidity Ratio      | 1.4
Seniority            | Senior Unsecured
Loan Type            | Revolving Credit Facility
Collateral Type      | None
Collateral Value     | 0
External Rating      | (leave blank)
Exposure Category    | (leave blank)
Expected PD Min      | 4.2
Expected PD Max      | 5.0
Expected LGD Min     | 45
Expected LGD Max     | 50
```

### Template J: Full Collateral Coverage
Best for: Testing highly secured lending scenarios
```
Test ID              | TC_FULLCOLLATERAL_001
Test Description     | Over-collateralized exposure, haircut adjustment
Borrower ID          | CORP_FC_001
Borrower Name        | Secured Assets Corp
Sector               | Real Estate
Exposure Amount      | 2000000
Calc Mode            | both
Debt to Equity       | 0.5
Interest Coverage    | 4.5
Profitability Margin | 25
Liquidity Ratio      | 1.8
Seniority            | Senior Secured - Real Estate
Loan Type            | Term Loan Long
Collateral Type      | Real Estate
Collateral Value     | 2500000
External Rating      | AA
Exposure Category    | Corporate
Expected PD Min      | 1.8
Expected PD Max      | 2.3
Expected LGD Min     | 20
Expected LGD Max     | 28
```

---

## 📊 How to Use These Templates

### Option 1: Direct Copy
1. Copy the template text that matches your scenario
2. Paste it into your Excel file (one value per column)
3. Modify the fields as needed for your specific test

### Option 2: Manual Reference
1. Use the template as a guide for realistic values
2. Adjust each field based on your test requirements
3. Verify Expected PD/LGD ranges using the formula in EXCEL_TEST_DATA_GUIDE.md

### Option 3: Mix & Match
1. Take the financial metrics from Template A (conservative)
2. Use the sector from Template D (different industry)
3. Adjust collateral from Template J
4. Create a custom hybrid scenario

---

## 🎯 Choosing the Right Template

| Scenario | Template | Best For |
|----------|----------|----------|
| Testing normal business | A or B | Day-to-day validation |
| Testing problem loans | C | Stress testing |
| Pure AIRB methodology | D | Component testing |
| Pure SA methodology | E | Regulatory approach |
| Government bonds | F | Safe exposures |
| High leverage | G | Extreme scenarios |
| Tight coverage | H | Edge cases |
| Unsecured loans | I | Risky lending |
| Secured loans | J | Safe lending |

---

## ✅ Validation Checklist

Before adding your test case to Excel, verify:

- [ ] Test ID is unique (no duplicates)
- [ ] All required fields for calc mode are filled
- [ ] No commas in numeric values (use 1000000, not 1,000,000)
- [ ] Financial metrics are realistic (no negative ratios except margin)
- [ ] Expected PD/LGD ranges are reasonable
- [ ] Collateral Type matches if Collateral Value > 0
- [ ] Description clearly explains what the test validates

---

## 🚀 Next Steps

1. **Select a template** that matches your test scenario
2. **Copy the template values** to your Excel file
3. **Customize fields** for your specific test
4. **Calculate expected values** using formulas if needed
5. **Run the test suite**: `python test_selenium_e2e.py`
6. **Verify results** against Expected PD/LGD ranges

---

**Template Version:** 1.0  
**Last Updated:** June 3, 2026  
**Related Files:** QUICK_START_TESTING.md, EXCEL_TEST_DATA_GUIDE.md
