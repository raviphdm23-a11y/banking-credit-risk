# Phase 2: Machine Learning Integration for PD Prediction

**Status:** Implementation Starting  
**Date Started:** June 5, 2026  
**Objective:** Add ML-based PD prediction alongside rule-based calculations

---

## Overview

Phase 2 adds machine learning capabilities to the Banking Credit Risk Calculator. Users can now choose between:
- **Rule-Based PD** (existing) - Deterministic formula
- **ML-Based PD** (new) - Trained model prediction

---

## Architecture

```
┌─────────────────────────────────┐
│   User Selects PD Method        │
│   ┌─ Rule-Based (Existing)      │
│   └─ ML-Based (New)             │
└────────────┬────────────────────┘
             │
             ├─ If Rule-Based:
             │  POST /api/calculate-pd
             │  (Existing endpoint)
             │
             └─ If ML-Based:
                POST /api/predict-pd-ml
                (New endpoint)
                │
                Load ml_models/pd_model.pkl
                │
                Return ML prediction
```

---

## Phase 2 Components

### 1. ML Model Creation
- **File:** `ml_models/pd_model.pkl`
- **Type:** Trained scikit-learn model
- **Input Features:** D/E, Interest Coverage, Profitability, Liquidity
- **Output:** PD prediction (0-100%)

### 2. Flask Integration
- **New Endpoint:** `POST /api/predict-pd-ml`
- **Functionality:** Load model, predict PD
- **Error Handling:** Fallback to rule-based if model fails

### 3. UI Updates
- **New Control:** Radio button/Toggle for PD method
- **Display:** Show which method was used
- **Flexibility:** User can switch between methods

### 4. Testing & Validation
- **Tests:** Verify ML predictions vs rule-based
- **Comparison:** Show both predictions for validation

---

## Implementation Steps

### Step 1: Create/Train ML Model
```python
# Option A: Train with real data (if available)
from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor()
model.fit(X_train, y_train)
joblib.dump(model, 'ml_models/pd_model.pkl')

# Option B: Use demo model (for now)
# Create a simple regression model
# Export as pickle
```

### Step 2: Create Flask Endpoint
```python
@app.route('/api/predict-pd-ml', methods=['POST'])
def predict_pd_ml():
    import joblib
    
    # Load model
    model = joblib.load('ml_models/pd_model.pkl')
    
    # Get features from request
    data = request.json
    features = [[
        data['de_ratio'],
        data['interest_coverage'],
        data['profitability'],
        data['liquidity_ratio']
    ]]
    
    # Predict
    pd_prediction = model.predict(features)[0]
    
    return jsonify({
        'pd': pd_prediction,
        'pd_percentage': pd_prediction * 100,
        'method': 'ML',
        'model_version': '1.0'
    })
```

### Step 3: Update Frontend
```html
<!-- PD Method Selection -->
<div class="form-group">
    <label>PD Calculation Method</label>
    <label>
        <input type="radio" name="pdMethod" value="rule-based" checked>
        Rule-Based (Deterministic)
    </label>
    <label>
        <input type="radio" name="pdMethod" value="ml">
        Machine Learning (Predictive)
    </label>
</div>
```

### Step 4: Update API Integration
```javascript
// In api-integration.js
async function calculatePDFromAPI(debtToEquity, interestCoverage, profitabilityMargin, liquidityRatio) {
    const pdMethod = document.querySelector('input[name="pdMethod"]:checked').value;
    
    const endpoint = pdMethod === 'ml' 
        ? '/predict-pd-ml' 
        : '/calculate-pd';
    
    const result = await apiCall(endpoint, {
        de_ratio: debtToEquity,
        interest_coverage: interestCoverage,
        profitability: profitabilityMargin,
        liquidity_ratio: liquidityRatio
    });
    
    return result;
}
```

---

## Model Training Options

### Option A: Real Data (Recommended)
**Requires:** Historical borrower data with actual defaults
**Process:**
1. Collect 500+ borrowers with outcomes
2. Calculate financial metrics for each
3. Label: Defaulted (1) or Non-Defaulted (0)
4. Train classification model (LogisticRegression, RandomForest, XGBoost)
5. Validate on test set (80/20 split)
6. Export as pickle

**Timeline:** 4-6 weeks

### Option B: Synthetic Data (Demo)
**For:** Testing/demonstration purposes
**Process:**
1. Generate synthetic borrower data
2. Create synthetic PD outcomes
3. Train model on synthetic data
4. Export as pickle
5. Clearly label as "Demo Model"

**Timeline:** 2-3 hours

### Option C: Transfer Learning
**Option:** Use pre-trained model from:
- Alternative sources
- Industry benchmarks
- Academic datasets

**Timeline:** 1-2 weeks

---

## Model Comparison Strategy

Show both predictions to users:

```
┌─────────────────────────────┐
│ PD Prediction Results       │
├─────────────────────────────┤
│ Rule-Based:    3.50%        │
│ ML Prediction: 4.20%        │
│                             │
│ Difference:   +0.70%        │
│ Agree:        [YES/NO]      │
└─────────────────────────────┘
```

**Benefits:**
- Users see both methods
- Can validate model quality
- Easy to switch between methods
- Builds confidence in model

---

## Risk Management

### Model Risks
- **Overfitting:** Validate on out-of-sample data
- **Data Drift:** Monitor predictions vs actuals
- **Black Box:** Use SHAP values to explain predictions

### Mitigation
1. Keep rule-based as fallback
2. Show both predictions
3. Monitor model performance
4. Retrain periodically
5. Document model assumptions

---

## Success Criteria

- [ ] ML model created and tested
- [ ] Flask endpoint working
- [ ] UI shows both methods
- [ ] User can switch between methods
- [ ] Results match expectations
- [ ] Error handling working
- [ ] Documentation complete
- [ ] Tests passing

---

## Timeline

**Week 1:** Model creation/demo
**Week 2:** Flask integration
**Week 3:** UI updates & testing
**Week 4:** Validation & documentation

**Total: 2-4 weeks** (depending on data availability)

---

## Deployment Considerations

### Development
- Demo model for testing
- Both predictions shown
- Easy method switching

### Staging
- Real model (if available)
- Performance monitoring
- A/B testing support

### Production
- Model serving (Flask)
- Prediction logging
- Model versioning
- Fallback to rule-based

---

## Next Steps After Phase 2

1. **Phase 3:** Operational Risk (BIA/TSA/AMA)
2. **Phase 4:** Market Risk (VaR/Standard)
3. **Phase 5:** Liquidity Risk (LCR/NSFR)
4. **Phase 6:** React Frontend Migration

---

**Ready to start Phase 2 implementation!**
