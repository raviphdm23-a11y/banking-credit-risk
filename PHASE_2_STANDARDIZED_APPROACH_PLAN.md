# 📋 Phase 2: Standardized Approach Implementation Plan

## Overview
Add Standardized Approach for Credit Risk to complement the existing AIRB methodology.

**Estimated Duration:** 2-3 weeks  
**Effort:** 40-50 hours  
**Complexity:** Medium  
**Dependency:** Phase 1 (AIRB) - Complete ✅

---

## 🎯 Phase 2 Objectives

### Primary Goals
1. Provide alternative to AIRB for banks using external ratings
2. Enable comparison between AIRB and Standardized approaches
3. Support banks transitioning from Standardized to AIRB
4. Maintain regulatory compliance

### Scope
- Standardized Approach for Corporate exposures
- External rating-based risk weights
- Fixed LGD values
- Simple RWA calculation
- Capital requirement computation

### Out of Scope (Future Phases)
- Retail exposures (Phase 3+)
- Equity exposures (Phase 4+)
- Operational risk
- Market risk

---

## 📐 Technical Specifications

### Input Requirements

```javascript
{
  // Loan Identification
  loanId: {
    type: "text",
    required: true,
    validation: "non-empty",
    example: "SA001",
    description: "Unique loan identifier"
  },
  
  // Exposure Information
  borrowerName: {
    type: "text",
    required: true,
    validation: "non-empty",
    example: "XYZ Corporation",
    description: "Name of borrowing entity"
  },
  
  exposureAmount: {
    type: "number",
    required: true,
    validation: "positive",
    unit: "USD",
    min: 1000,
    example: 2000000,
    description: "Total exposure amount"
  },
  
  // Rating Information
  externalRating: {
    type: "select",
    required: true,
    validation: "must-select",
    options: ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC", "CC", "C", "D"],
    example: "BBB+",
    description: "Rating from approved ECAI (S&P, Moody's, Fitch)"
  },
  
  ratingAgency: {
    type: "select",
    required: true,
    validation: "must-select",
    options: ["S&P", "Moody's", "Fitch", "Other ECAI"],
    example: "S&P",
    description: "Rating agency providing the rating"
  },
  
  exposureCategory: {
    type: "select",
    required: true,
    validation: "must-select",
    options: ["Corporate", "Central Government", "Bank", "Other Financial", "Unrated"],
    example: "Corporate",
    description: "Category of counterparty"
  },
  
  // Collateral (Optional)
  hasCollateral: {
    type: "checkbox",
    required: false,
    default: false,
    description: "Whether exposure is collateralized"
  },
  
  collateralType: {
    type: "select",
    required: false,
    visible: "if hasCollateral = true",
    options: ["Cash", "Government Securities", "Corporate Bonds", "Equities", "Other"],
    description: "Type of collateral securing the exposure"
  },
  
  collateralValue: {
    type: "number",
    required: false,
    visible: "if hasCollateral = true",
    validation: "non-negative",
    unit: "USD",
    description: "Market value of collateral"
  },
  
  haircut: {
    type: "number",
    required: false,
    visible: "if hasCollateral = true",
    validation: "0-100",
    unit: "%",
    default: 20,
    example: 20,
    description: "Haircut applied to collateral value"
  }
}
```

---

## 📊 Risk Weight Tables

### Corporate Exposures

```javascript
const corporateRiskWeights = {
  'AAA': 20,
  'AA+': 20,
  'AA': 20,
  'AA-': 20,
  'A+': 50,
  'A': 50,
  'A-': 50,
  'BBB+': 75,
  'BBB': 75,
  'BBB-': 75,
  'BB+': 100,
  'BB': 100,
  'BB-': 100,
  'B+': 100,
  'B': 100,
  'B-': 100,
  'CCC': 150,
  'CC': 150,
  'C': 150,
  'D': 150,
  'Unrated': 100  // Conservative default
};
```

### Sovereign Exposures

```javascript
const sovereignRiskWeights = {
  'AAA': 0,
  'AA+': 20,
  'AA': 20,
  'AA-': 20,
  'A+': 50,
  'A': 50,
  'A-': 50,
  'BBB+': 50,
  'BBB': 50,
  'BBB-': 50,
  'BB+': 100,
  'BB': 100,
  'BB-': 100,
  'B+': 100,
  'B': 100,
  'B-': 100,
  'CCC': 150,
  'CC': 150,
  'C': 150,
  'D': 150
};
```

### Bank Exposures

```javascript
const bankRiskWeights = {
  'AAA': 20,
  'AA+': 20,
  'AA': 20,
  'AA-': 20,
  'A+': 50,
  'A': 50,
  'A-': 50,
  'BBB+': 75,
  'BBB': 75,
  'BBB-': 75,
  'BB+': 100,
  'BB': 100,
  'BB-': 100,
  'B+': 100,
  'B': 100,
  'B-': 100,
  'CCC': 150,
  'CC': 150,
  'C': 150,
  'D': 150
};
```

### LGD Values (Fixed)

```javascript
const lgdValues = {
  unsecured: 0.45,              // 45% for unsecured
  secured_real_estate: 0.25,    // 25% for real estate
  secured_securities: 0.35,     // 35% for securities
  secured_cash: 0.05            // 5% for cash
};
```

---

## 🧮 Calculation Formulas

### Core Formula
```
RWA = Exposure Amount × Risk Weight
Capital Requirement = RWA × 8%

Example:
EAD = $1,000,000
Rating = BBB+ (Corporate)
Risk Weight = 75%
RWA = $1,000,000 × 0.75 = $750,000
Capital = $750,000 × 0.08 = $60,000
```

### With Collateral (CRM - Credit Risk Mitigation)
```
Adjusted Exposure = Max(EAD - Collateral Value × (1 - Haircut), Minimum Floor)
RWA = Adjusted Exposure × Risk Weight
Capital = RWA × 8%

Example:
EAD = $1,000,000
Collateral = $300,000 (Cash) with 5% haircut
Adjusted Exposure = $1,000,000 - $300,000 × (1 - 0.05)
                  = $1,000,000 - $285,000
                  = $715,000
Risk Weight = 75%
RWA = $715,000 × 0.75 = $536,250
Capital = $536,250 × 0.08 = $42,900
```

---

## 📋 Output Metrics

```javascript
const outputs = [
  {
    key: "riskWeight",
    label: "Risk Weight",
    format: "percent",
    description: "From rating lookup table"
  },
  {
    key: "adjustedExposure",
    label: "Adjusted Exposure (with CRM)",
    format: "currency",
    description: "After collateral adjustment"
  },
  {
    key: "rwa",
    label: "Risk-Weighted Assets",
    format: "currency",
    description: "Exposure × Risk Weight"
  },
  {
    key: "capitalRequired",
    label: "Capital Required (8%)",
    format: "currency",
    description: "8% of RWA (minimum)"
  },
  {
    key: "capitalRatio",
    label: "Capital Ratio",
    format: "percent",
    description: "Capital as % of Exposure"
  },
  {
    key: "comparison",
    label: "Comparison with AIRB",
    format: "delta",
    description: "RWA difference and percentage"
  }
];
```

---

## 📅 Detailed Implementation Timeline

### Week 1: Design & Specification

**Day 1-2: Regulatory Review**
- [ ] Review Basel III Standardized Approach documentation
- [ ] Verify risk weight tables against CRR/CRD IV
- [ ] Document all LGD values
- [ ] Confirm collateral treatment rules
- [ ] Create regulatory compliance checklist
- [ ] Deliverable: Regulatory documentation folder

**Day 3-4: Detailed Design**
- [ ] Create input/output specification
- [ ] Design database schema (if applicable)
- [ ] Design UI mockups
- [ ] Create calculation flowchart
- [ ] Define validation rules
- [ ] Deliverable: Design specification document

**Day 5: Preparation**
- [ ] Create test cases (20+ scenarios)
- [ ] Build Excel reference model
- [ ] Prepare formula reference outline
- [ ] Create implementation checklist
- [ ] Deliverable: Test cases & Excel model

---

### Week 2: Development

**Day 1-2: Core Module Development**
- [ ] Create standardized-approach.js module
- [ ] Implement risk weight lookup functions
- [ ] Implement RWA calculation
- [ ] Implement collateral adjustment
- [ ] Add input validation
- [ ] Deliverable: Core calculation module

**Day 3: Error Handling & Validation**
- [ ] Add comprehensive error handling
- [ ] Implement input validation
- [ ] Create error message system
- [ ] Add edge case handling
- [ ] Test error scenarios
- [ ] Deliverable: Robust validation layer

**Day 4-5: Unit Testing**
- [ ] Write unit tests for all functions
- [ ] Test edge cases and boundaries
- [ ] Verify all calculations
- [ ] Cross-check with Excel model
- [ ] Achieve 95%+ code coverage
- [ ] Deliverable: Test suite with results

---

### Week 3: Integration & Documentation

**Day 1-2: UI/UX Integration**
- [ ] Create HTML form for inputs
- [ ] Implement tab interface (AIRB vs SA)
- [ ] Add results display cards
- [ ] Implement comparison feature
- [ ] Test responsive design
- [ ] Deliverable: Integrated interface

**Day 3: Formula Reference & Documentation**
- [ ] Create standardized-approach-reference.html
- [ ] Write comprehensive formula explanations
- [ ] Add worked examples (5+)
- [ ] Include regulatory notes
- [ ] Create comparison charts
- [ ] Deliverable: Formula reference page

**Day 4-5: Testing & Validation**
- [ ] Integration testing
- [ ] User acceptance testing
- [ ] Performance testing
- [ ] Cross-browser compatibility
- [ ] Regulatory compliance verification
- [ ] Deliverable: QA sign-off

---

## 🗂️ File Structure

```
Banking_Credit_Risk/
├── index.html (UPDATED)
│   └── Add methodology selector
│   └── Add SA tab
│   └── Link to SA reference
│
├── standardized-approach-reference.html (NEW)
│   ├── Overview
│   ├── Components explanation
│   ├── Risk weight tables
│   ├── Worked examples
│   ├── Regulatory notes
│   └── Comparison with AIRB
│
├── js/
│   ├── standardized-approach.js (NEW)
│   │   ├── riskWeightTables
│   │   ├── calculateRiskWeight()
│   │   ├── calculateRWA()
│   │   ├── applyCollateralAdjustment()
│   │   └── calculateCapital()
│   │
│   └── shared-utils.js (NEW/UPDATED)
│       ├── formatCurrency()
│       ├── validateInput()
│       ├── exportData()
│       └── compareMethodologies()
│
└── PHASE_2_STANDARDIZED_APPROACH_PLAN.md (This file)
```

---

## ✅ Definition of Done

### For Phase 2 Completion:

**Functionality**
- [ ] All input fields functional
- [ ] Risk weight lookup working
- [ ] RWA calculation correct
- [ ] Collateral adjustment working
- [ ] Capital calculation accurate

**Integration**
- [ ] Integrated into main calculator
- [ ] Methodology selector working
- [ ] Tab switching functional
- [ ] Export includes SA data

**Testing**
- [ ] 100% of test cases pass
- [ ] Cross-checked with manual calculations
- [ ] Verified against regulatory standards
- [ ] Edge cases handled
- [ ] Error scenarios tested

**Documentation**
- [ ] Formula reference page complete
- [ ] User guide updated
- [ ] Regulatory compliance confirmed
- [ ] Comparison guide created
- [ ] FAQ section added

**Quality**
- [ ] Code reviewed and approved
- [ ] No console errors
- [ ] Mobile responsive
- [ ] Performance acceptable (<1s for calculations)

---

## 📊 Comparison Matrix: AIRB vs Standardized Approach

```
Feature                 AIRB                Standardized
─────────────────────────────────────────────────────────
PD Source              Internal model      N/A
LGD Source             Internal model      Fixed %
Complexity             High (formulas)     Low (lookups)
Calculation Speed      Fast                Very fast
Data Required          5-7 years           External ratings only
Regulatory Approval    Required            Automatic
Risk Sensitivity       Very high           Medium
Capital Efficiency     Often lower         Higher/conservative
Use Case               Large banks         Mid-size banks
```

---

## 🎓 Worked Example: Full Calculation

### Scenario 1: Unsecured Corporate Loan

```
Input Data:
- Loan ID: SA001
- Borrower: ABC Manufacturing Ltd
- Exposure: $2,000,000
- Rating: BBB+ (S&P)
- Category: Corporate
- Collateral: None

Step 1: Lookup Risk Weight
Rating: BBB+ (Corporate) → Risk Weight = 75%

Step 2: Calculate RWA
RWA = $2,000,000 × 0.75 = $1,500,000

Step 3: Calculate Capital
Capital Required = $1,500,000 × 0.08 = $120,000

Output:
- Risk Weight: 75%
- RWA: $1,500,000
- Capital Required: $120,000
- Capital Ratio: 6.0%
```

### Scenario 2: Secured Corporate Loan

```
Input Data:
- Loan ID: SA002
- Borrower: XYZ Corp
- Exposure: $1,000,000
- Rating: A (Moody's)
- Category: Corporate
- Collateral: Government Securities
- Collateral Value: $400,000
- Haircut: 10%

Step 1: Lookup Risk Weight
Rating: A (Corporate) → Risk Weight = 50%

Step 2: Apply Collateral Adjustment
Collateral Effect = $400,000 × (1 - 0.10) = $360,000
Adjusted Exposure = $1,000,000 - $360,000 = $640,000

Step 3: Calculate RWA
RWA = $640,000 × 0.50 = $320,000

Step 4: Calculate Capital
Capital Required = $320,000 × 0.08 = $25,600

Output:
- Risk Weight: 50%
- Adjusted Exposure: $640,000
- RWA: $320,000
- Capital Required: $25,600
- Capital Ratio: 2.56%
```

---

## 📞 Validation Against Regulatory Standards

### Basel III Compliance Checklist
- [ ] Risk weights aligned with CRR/CRD IV
- [ ] LGD values consistent with standards
- [ ] Collateral treatment correct
- [ ] Haircuts appropriate
- [ ] Calculation formula verified
- [ ] Edge cases handled per regulations

### Test Cases Verification
- [ ] All 25+ test cases pass
- [ ] Results match manual calculations
- [ ] Edge cases produce correct output
- [ ] Error handling appropriate
- [ ] Performance meets requirements

---

## 🚀 Deployment Checklist

### Pre-Deployment
- [ ] All tests passed
- [ ] Code reviewed
- [ ] Documentation complete
- [ ] User training prepared
- [ ] Rollback plan documented

### Deployment
- [ ] Backup created
- [ ] Files uploaded
- [ ] Links updated
- [ ] Formula reference accessible
- [ ] Help system updated

### Post-Deployment
- [ ] All features working
- [ ] No errors in console
- [ ] Users trained
- [ ] Support documentation distributed
- [ ] Feedback collection process established

---

## 📝 Success Criteria

### Phase 2 is complete when:

1. **Functionality**: All calculations correct and verified
2. **Integration**: Seamlessly integrated with AIRB approach
3. **Documentation**: Complete formula references and guides
4. **Testing**: 100% test coverage with all cases passing
5. **Quality**: Production-ready code with no issues
6. **Compliance**: Verified against Basel III standards
7. **User Experience**: Intuitive interface matching AIRB design

---

## 📞 Next Steps

Once Phase 2 is approved:

1. **Initiation**
   - Schedule kick-off meeting
   - Confirm timeline and resources
   - Prepare development environment

2. **Execution**
   - Follow week-by-week timeline
   - Weekly progress updates
   - Daily testing and validation

3. **Completion**
   - Final testing and QA
   - User acceptance testing
   - Deployment to production

4. **Post-Launch**
   - Monitor for issues
   - Gather user feedback
   - Plan Phase 3

---

## 📚 Reference Materials

### Regulatory Documents
- Basel III: A global regulatory framework on bank capital adequacy
- CRR/CRD IV: EU Capital Requirements Regulation/Directive
- EBA Guidelines on credit risk mitigation

### Additional Resources
- Risk weight tables (attached)
- Collateral treatment rules (attached)
- Test case database (attached)
- Excel reference model (attached)

---

**Phase 2 Implementation Plan v1.0**  
**Created:** June 2026  
**Status:** Ready for Implementation  
**Next Phase:** Phase 3 - Operational Risk

---

## 🎯 Ready to Start?

Once you approve this plan, I will:

1. ✅ Create the core calculation module (standardized-approach.js)
2. ✅ Build the UI form and integration
3. ✅ Create the formula reference page
4. ✅ Implement comprehensive testing
5. ✅ Prepare documentation

**Just confirm: "Start Phase 2 Implementation" and I'll begin!**
