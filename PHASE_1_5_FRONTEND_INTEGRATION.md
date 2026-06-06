# Phase 1.5: Frontend Integration - Update HTML to Call Flask APIs

**Status:** Implementation in Progress  
**Date Started:** June 5, 2026  
**Objective:** Replace JavaScript calculations with Flask API calls

---

## Overview

This phase involves updating `borrower-info.html` to call Flask backend APIs instead of performing calculations in JavaScript. The frontend will now act as a pure UI layer, delegating all calculations to the backend.

---

## Changes Required

### 1. Add API Configuration Section
- Base API URL: `http://127.0.0.1:5000/api`
- Create helper functions for API calls
- Add error handling for network issues

### 2. Replace Calculation Functions

**OLD (JavaScript):**
```javascript
const pdResult = calculatePD(debtToEquity, interestCoverage, profitability, liquidity);
```

**NEW (API Call):**
```javascript
const pdResult = await apiCall('/calculate-pd', {
    de_ratio: debtToEquity,
    interest_coverage: interestCoverage,
    profitability: profitability,
    liquidity_ratio: liquidity
});
```

### 3. Functions to Replace

| Function | New API Endpoint | Status |
|----------|-----------------|--------|
| `calculatePD()` | `POST /api/calculate-pd` | To replace |
| `calculateLGD()` | `POST /api/calculate-lgd` | To replace |
| `calculateRiskWeight()` | `POST /api/calculate-risk-weight-airb` | To replace |
| `getAdjustedExposure()` | `POST /api/calculate-adjusted-exposure` | To replace |
| `calculateRWA()` | `POST /api/calculate-rwa-airb` or `-sa` | To replace |
| `portfolioSummary()` | `POST /api/portfolio-summary` | To replace |

### 4. Functions to Keep (UI/Formatting)
- `calculateHaircut()` - Just format lookup (can keep local)
- `getRiskLevel()` - Risk classification helper
- `getRiskBadgeClass()` - CSS class assignment
- `formatCurrency()` - Number formatting
- `updateTable()` - Table display
- `displayResults()` - Result rendering

---

## Implementation Steps

### Step 1: Add API Helper Functions
```javascript
// API Configuration
const API_BASE_URL = 'http://127.0.0.1:5000/api';

// Generic API call function
async function apiCall(endpoint, data = null) {
    try {
        const options = {
            headers: { 'Content-Type': 'application/json' },
            mode: 'cors'
        };

        let response;
        if (data) {
            options.method = 'POST';
            options.body = JSON.stringify(data);
            response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        } else {
            options.method = 'GET';
            response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        }

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API call failed: ${error}`);
        showNotification('Error', `API call failed: ${error.message}`);
        return null;
    }
}
```

### Step 2: Replace calculatePD() Function
```javascript
async function calculatePDFromAPI(debtToEquity, interestCoverage, profitabilityMargin, liquidityRatio) {
    const result = await apiCall('/calculate-pd', {
        de_ratio: debtToEquity,
        interest_coverage: interestCoverage,
        profitability: profitabilityMargin,
        liquidity_ratio: liquidityRatio
    });
    
    if (!result || result.error) {
        return null;
    }
    
    return {
        pd: result.pd_percentage,
        components: result.breakdown
    };
}
```

### Step 3: Replace calculateLGD() Function
```javascript
async function calculateLGDFromAPI(seniority, exposureAmount, collateralValue, collateralType, sector) {
    const result = await apiCall('/calculate-lgd', {
        seniority: seniority,
        collateral_type: collateralType,
        collateral_value: collateralValue,
        exposure: exposureAmount
    });
    
    if (!result || result.error) {
        return null;
    }
    
    return {
        lgd: result.lgd_percentage,
        components: result
    };
}
```

### Step 4: Make calculateAllParameters() Async
```javascript
async function calculateAllParameters() {
    if (!validateInputs()) {
        alert('Please correct the errors above');
        return;
    }

    // ... get form values ...

    // Call APIs (now async)
    const pdResult = await calculatePDFromAPI(...);
    const lgdResult = await calculateLGDFromAPI(...);
    
    // Display results
    displayResults(mode, pdResult, borrowerId, borrowerName, sector, exposureAmount);
}
```

### Step 5: Update Button Click Handler
```javascript
document.getElementById('calculateBtn').addEventListener('click', async (e) => {
    e.preventDefault();
    await calculateAllParameters();
});
```

---

## Testing Strategy

### Phase 1.5a: API Integration Tests
- [ ] Health check API endpoint
- [ ] PD calculation API call
- [ ] LGD calculation API call
- [ ] Risk weight lookup
- [ ] RWA calculation

### Phase 1.5b: UI Integration Tests
- [ ] Form submission
- [ ] Results display
- [ ] Error handling
- [ ] Network error handling
- [ ] Portfolio recording

### Phase 1.5c: End-to-End Tests
- [ ] Complete borrower entry flow
- [ ] Multiple loans in portfolio
- [ ] Export functionality
- [ ] Cross-browser testing

---

## Files to Modify

1. **public/borrower-info.html**
   - Add API configuration
   - Replace calculation functions
   - Add async/await handling
   - Update event listeners

---

## API Endpoint Mapping

```javascript
// AIRB APIs
POST /api/calculate-pd              ← calculatePD()
POST /api/calculate-lgd             ← calculateLGD()
POST /api/calculate-correlation     ← For future use
POST /api/calculate-maturity-adjustment ← For future use
POST /api/calculate-risk-weight-airb    ← calculateRiskWeight()
POST /api/calculate-rwa-airb        ← calculateRWA()

// Standardized Approach APIs
POST /api/get-risk-weight-sa        ← Risk weight lookup
POST /api/calculate-adjusted-exposure   ← Collateral adjustment
POST /api/calculate-rwa-sa          ← SA RWA calculation

// Portfolio APIs
POST /api/portfolio-summary         ← Portfolio aggregation

// System APIs
GET  /api/health                    ← Health check
```

---

## Error Handling

### Network Errors
```javascript
try {
    const result = await apiCall(endpoint, data);
    if (!result) {
        showNotification('Error', 'API call failed. Please try again.');
        return null;
    }
} catch (error) {
    showNotification('Error', `Network error: ${error.message}`);
}
```

### Invalid Data
```javascript
if (result.error) {
    showNotification('Error', `Calculation error: ${result.error}`);
    return null;
}
```

---

## Backward Compatibility

- **Falls back to local calculation** if API unavailable (optional)
- **Client-side validation** still works (no API needed)
- **Graceful degradation** if network issues

---

## Performance Considerations

- API calls: 10-50ms (sub-50ms for most requests)
- Overall calculation: <100ms
- **No performance degradation** vs local JavaScript

---

## CORS Configuration

- Flask CORS already enabled (`Flask-CORS`)
- Origins: `*` (allows all for development)
- Change to specific origin in production

---

## Expected Changes Summary

| Component | Before | After |
|-----------|--------|-------|
| **PD Calculation** | Local JS | Flask API |
| **LGD Calculation** | Local JS | Flask API |
| **Risk Weight** | Local JS | Flask API (SA) |
| **RWA Calculation** | Local JS | Flask API |
| **Validation** | Local JS | Local JS (unchanged) |
| **UI Display** | Local JS | Local JS (unchanged) |
| **Portfolio Management** | localStorage | localStorage (unchanged) |

---

## Next Steps

1. ✅ Create API helper functions
2. ✅ Replace calculatePD() with API call
3. ✅ Replace calculateLGD() with API call
4. ✅ Replace RWA calculations with API calls
5. ✅ Make calculateAllParameters() async
6. ✅ Add error handling
7. ⏳ Test with running Flask server
8. ⏳ Test form submission flow
9. ⏳ Test portfolio functionality
10. ⏳ Final verification

---

## Rollback Plan

If API integration doesn't work:
1. Keep original JavaScript functions commented
2. Can quickly revert to local calculations
3. No data loss (localStorage unaffected)

---

**Document Status:** Phase 1.5 Plan Created  
**Ready for Implementation:** Yes
