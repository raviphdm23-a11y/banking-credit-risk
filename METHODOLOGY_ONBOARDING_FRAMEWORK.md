# 🏗️ Risk Methodology Onboarding Framework

## Overview
This document provides a complete framework for adding new risk calculation methodologies to the AIRB Credit Risk Calculator platform.

---

## 📋 Supported Methodologies (Current & Future)

### Phase 1: AIRB Credit Risk (✅ Complete)
- ✅ Advanced Internal Ratings Based Approach
- ✅ PD, LGD, EAD, Maturity factors
- ✅ RWA calculation
- ✅ Basel III compliant

### Phase 2: Standardized Approach (⏳ Planned)
- ⏳ Standardized approach for credit risk
- ⏳ External rating-based weights
- ⏳ Fixed PD/LGD percentages
- ⏳ Simpler calculation methodology

### Phase 3: Operational Risk (⏳ Planned)
- ⏳ Basic Indicator Approach (BIA)
- ⏳ Standardized Approach (TSA)
- ⏳ Advanced Measurement Approach (AMA)

### Phase 4: Market Risk (⏳ Planned)
- ⏳ Value at Risk (VaR)
- ⏳ Stressed VaR
- ⏳ Incremental Risk Charge (IRC)

### Phase 5: Liquidity Risk (⏳ Planned)
- ⏳ Liquidity Coverage Ratio (LCR)
- ⏳ Net Stable Funding Ratio (NSFR)

---

## 🎯 Architecture Overview

### Current Technology Stack
```
Frontend:
├── Single HTML5 file (index.html)
├── Pure CSS3 styling
└── Vanilla JavaScript (ES6)

Features:
├── Form-based input
├── Real-time calculations
├── Portfolio management
├── Data export (CSV/JSON)
└── Mobile responsive

Backend:
└── None (browser-based)
```

### Proposed Modular Architecture
```
Multi-Methodology Platform:
├── Core Framework (Shared)
│   ├── Input validation
│   ├── Data management
│   ├── Export functionality
│   ├── UI components
│   └── State management
│
├── Methodology Modules (Pluggable)
│   ├── AIRB Credit Risk
│   ├── Standardized Approach
│   ├── Operational Risk
│   ├── Market Risk
│   └── Liquidity Risk
│
└── Supporting Pages
    ├── Dashboard/Home
    ├── Formula References
    ├── Methodology Selector
    └── Settings/Config
```

---

## 📐 Implementation Framework

### Step 1: Define Methodology Structure

Every methodology must define:

```javascript
{
  // Metadata
  id: "standardized-approach",
  name: "Standardized Approach for Credit Risk",
  shortName: "SA",
  version: "1.0",
  description: "Basel III Standardized Approach using external ratings",
  category: "credit-risk",
  status: "active", // active, beta, deprecated, archived
  
  // Input Requirements
  inputs: {
    exposureAmount: {
      label: "Exposure Amount ($)",
      type: "number",
      required: true,
      min: 0,
      description: "Total exposure value"
    },
    externalRating: {
      label: "External Rating",
      type: "select",
      required: true,
      options: ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "Default"],
      description: "Rating from approved ECAI"
    },
    riskWeight: {
      label: "Risk Weight (%)",
      type: "number",
      computed: true, // Auto-calculated from rating
      description: "Based on external rating"
    }
  },
  
  // Calculation Functions
  calculations: {
    getRiskWeight: function(rating) { /* logic */ },
    calculateRWA: function(exposure, riskWeight) { /* logic */ },
    calculateCapital: function(rwa) { /* logic */ }
  },
  
  // Validation Rules
  validation: {
    rules: [
      { field: "exposureAmount", rule: "required", message: "Amount required" },
      { field: "externalRating", rule: "required", message: "Rating required" }
    ]
  },
  
  // Output Metrics
  outputs: [
    { key: "riskWeight", label: "Risk Weight (%)", format: "percent" },
    { key: "rwa", label: "Risk-Weighted Assets", format: "currency" },
    { key: "capital", label: "Capital Required (8%)", format: "currency" }
  ],
  
  // Regulatory Reference
  regulatory: {
    framework: "Basel III",
    standard: "CRR/CRD IV",
    documentation: "https://..."
  },
  
  // Formula Reference
  formula: {
    rwa: "RWA = Exposure Amount × Risk Weight",
    capital: "Capital = RWA × 8%"
  }
}
```

---

## 🔄 Development Workflow

### For Each New Methodology:

**Phase A: Design & Documentation (2-3 days)**
```
1. Define inputs and outputs
2. Document calculation formulas
3. Create formula reference page
4. Prepare regulatory compliance notes
5. List validation rules
6. Define test cases
```

**Phase B: Core Development (3-5 days)**
```
1. Create methodology module (JavaScript)
2. Implement calculation functions
3. Add input validation
4. Implement error handling
5. Write unit tests
6. Code review
```

**Phase C: UI/UX Integration (2-3 days)**
```
1. Add form inputs to HTML
2. Create tabbed interface (if multi-methodology)
3. Implement methodology selector
4. Add summary cards
5. Integrate export functionality
6. Test responsive design
```

**Phase D: Formula Reference (1-2 days)**
```
1. Create detailed formula page
2. Add worked examples
3. Include regulatory notes
4. Add comparison tables
5. Provide reference material
```

**Phase E: Testing & Validation (2-3 days)**
```
1. Unit test calculations
2. Compare with manual examples
3. Validate against regulatory standards
4. Test all input scenarios
5. Cross-check with Excel models
6. User acceptance testing
```

**Phase F: Documentation & Deployment (1-2 days)**
```
1. Update user guides
2. Add methodology to help system
3. Create deployment checklist
4. Train users
5. Deploy to production
6. Monitor for issues
```

---

## 📊 Phase 1: AIRB Credit Risk ✅

**Status:** Complete
**Timeline:** Already Implemented
**Deliverables:**
- ✅ Web calculator (index.html)
- ✅ Formula reference page (formula-reference.html)
- ✅ Deployment guide
- ✅ User documentation

---

## 📊 Phase 2: Standardized Approach (Recommended Next)

**Estimated Timeline:** 2-3 weeks
**Complexity:** Medium (Similar to AIRB but simpler)
**Effort:** 40-50 hours

### Key Differences from AIRB:
```
AIRB:                          Standardized Approach:
Internal PD/LGD estimation  →  External ratings only
Complex formulas            →  Simple lookup tables
Regulatory approval needed  →  Automatic applicability
High capital sensitivity    →  Fixed risk weights
```

### Implementation Approach:

**Step 1: Input Design**
```
- Exposure Amount (like AIRB)
- External Rating (new: AAA-Default)
- Exposure Type (new: Corporate, Sovereign, Bank, etc.)
- Risk Weight (auto-calculated from rating)
```

**Step 2: Risk Weight Table**
```javascript
const riskWeights = {
  corporate: {
    'AAA': 20,      // 20% risk weight
    'AA': 30,
    'A': 40,
    'BBB': 50,
    'BB': 75,
    'B': 100,
    'CCC': 150,
    'Default': 150
  },
  sovereign: { /* ... */ },
  bank: { /* ... */ }
}
```

**Step 3: Calculations**
```javascript
// Simple calculation
RWA = Exposure × Risk Weight
Capital = RWA × 8%
```

**Step 4: Outputs**
```
- Risk Weight (from table)
- RWA (Exposure × Weight)
- Capital Required (8% of RWA)
- Comparison with AIRB result (optional)
```

---

## 📊 Phase 3: Operational Risk

**Estimated Timeline:** 4-6 weeks
**Complexity:** High (Multiple approaches)
**Effort:** 80-100 hours

### Three Approaches to Implement:

**1. Basic Indicator Approach (BIA)**
```
Capital = Gross Income × 15%
- Simple but conservative
- No data requirements
- Not based on actual losses
```

**2. Standardized Approach (TSA)**
```
Capital = Σ (Business Line Income × Beta Factor)
- Business line dependent
- Beta factors: 12%, 15%, 18%, etc.
- More risk-sensitive than BIA
```

**3. Advanced Measurement Approach (AMA)**
```
Capital = Loss Given Event × Probability × Exposure
- Complex modeling required
- Requires 5+ years of loss data
- Most risk-sensitive
```

---

## 📊 Phase 4: Market Risk

**Estimated Timeline:** 4-6 weeks
**Complexity:** Very High (Statistical models)
**Effort:** 100-120 hours

### Key Components:
- Value at Risk (VaR) calculation
- Stressed VaR
- Historical simulation
- Monte Carlo simulation
- Greeks (Delta, Gamma, Vega)
- Backtesting

---

## 📊 Phase 5: Liquidity Risk

**Estimated Timeline:** 3-4 weeks
**Complexity:** High (Complex ratios)
**Effort:** 60-80 hours

### Key Components:
- Liquidity Coverage Ratio (LCR)
- Net Stable Funding Ratio (NSFR)
- Cash flow analysis
- Maturity mismatch
- Funding stress scenarios

---

## 🛠️ Implementation Checklist

### For Each New Methodology:

- [ ] **Design Phase**
  - [ ] Regulatory requirements documented
  - [ ] Input/output mapping defined
  - [ ] Formulas validated
  - [ ] Test cases prepared
  - [ ] Excel model created for validation

- [ ] **Development Phase**
  - [ ] Core calculation module created
  - [ ] Input validation implemented
  - [ ] Error handling added
  - [ ] Unit tests written and passing
  - [ ] Code reviewed

- [ ] **Integration Phase**
  - [ ] HTML form created
  - [ ] UI styling applied
  - [ ] Results display implemented
  - [ ] Export functionality tested
  - [ ] Responsive design verified

- [ ] **Documentation Phase**
  - [ ] Formula reference page created
  - [ ] Worked examples provided
  - [ ] Regulatory notes added
  - [ ] User guide written
  - [ ] FAQ section added

- [ ] **Testing Phase**
  - [ ] All calculations verified
  - [ ] Edge cases tested
  - [ ] Integration testing complete
  - [ ] UAT sign-off obtained
  - [ ] Performance validated

- [ ] **Deployment Phase**
  - [ ] Deployment checklist completed
  - [ ] Backup created
  - [ ] Rollback plan documented
  - [ ] User training completed
  - [ ] Support documentation ready

---

## 📝 Code Structure (HTML-based)

### Current (Single Methodology):
```html
<body>
  <header>...</header>
  <div class="main-content">
    <div class="input-form">
      <!-- AIRB inputs only -->
    </div>
    <div class="results">
      <!-- AIRB results only -->
    </div>
  </div>
</body>
```

### Future (Multi-Methodology):
```html
<body>
  <header>
    <select id="methodology-selector">
      <option value="airb">AIRB Credit Risk</option>
      <option value="sa">Standardized Approach</option>
      <option value="opex">Operational Risk</option>
      <option value="market">Market Risk</option>
    </select>
  </header>
  
  <div class="main-content">
    <!-- Tab-based interface -->
    <div id="airb-tab" class="methodology-tab active">...</div>
    <div id="sa-tab" class="methodology-tab">...</div>
    <div id="opex-tab" class="methodology-tab">...</div>
    <div id="market-tab" class="methodology-tab">...</div>
  </div>
  
  <script>
    // Methodology manager
    const methodologies = {
      airb: { /* calculations */ },
      sa: { /* calculations */ },
      opex: { /* calculations */ },
      market: { /* calculations */ }
    };
    
    function switchMethodology(name) {
      // Load appropriate methodology
    }
  </script>
</body>
```

---

## 🔑 Key Principles for Onboarding

### 1. **Modularity**
- Each methodology is independent
- Can be enabled/disabled separately
- Shared core functionality

### 2. **Extensibility**
- Easy to add new methodologies
- Plugin-like architecture
- Minimal changes to existing code

### 3. **Maintainability**
- Clear separation of concerns
- Well-documented code
- Comprehensive test coverage

### 4. **User Experience**
- Consistent interface across methodologies
- Clear labeling and instructions
- Helpful error messages
- Export capabilities

### 5. **Regulatory Compliance**
- Formulas validated against standards
- Regulatory references provided
- Audit trail capability
- Version control

---

## 📈 Recommended Implementation Sequence

```
Week 1-2:   Phase 2 - Standardized Approach
Week 3-4:   Phase 2 - Testing & Documentation
Week 5-6:   Phase 2 - Deployment
Week 7-10:  Phase 3 - Operational Risk (BIA)
Week 11-14: Phase 3 - Operational Risk (TSA)
Week 15-18: Phase 3 - Operational Risk (AMA)
... (Continue with Market Risk, Liquidity Risk)
```

---

## 🚀 Getting Started

### To Request a New Methodology:

```
1. Specify the methodology name
2. Provide regulatory framework (Basel III, etc.)
3. Define key inputs
4. List required calculations
5. Specify timeline preference
6. Provide any reference materials
```

### Example Request Format:

```markdown
## New Methodology Request: Standardized Approach

**Methodology:** Standardized Approach for Credit Risk

**Regulatory Framework:** Basel III / CRR/CRD IV

**Key Inputs:**
- Exposure Amount
- External Rating
- Exposure Category

**Key Outputs:**
- Risk Weight
- RWA
- Capital Requirement

**Timeline:** 3 weeks

**Priority:** High

**Reference Materials:**
- Link to Basel III document
- Link to regulatory guidance
- Link to example calculation
```

---

## 📞 Support & Questions

### When ready to add a new methodology:
1. Use the request format above
2. I will create:
   - Detailed design document
   - Phase-wise implementation plan
   - Code templates
   - Test cases
   - Documentation outline

3. Follow the workflow:
   - Design & Documentation
   - Core Development
   - UI/UX Integration
   - Formula Reference
   - Testing & Validation
   - Documentation & Deployment

---

## Summary

This framework provides a structured approach to onboarding new risk calculation methodologies. Each methodology follows the same development workflow, ensuring quality, consistency, and maintainability.

**Ready to add your first new methodology? Just let me know which one and I'll create the full phase-wise plan!**

---

**Framework Version:** 1.0
**Last Updated:** June 2026
**Status:** Active & Accepting Requests
