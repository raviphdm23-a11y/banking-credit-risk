# Machine Learning Model Guide

## Where is the Trained Model?

The trained ML model is located in the project directory:

```
Banking_Credit_Risk/
├── ml_models/
│   ├── pd_model.pkl                    ← The trained model (pickle format)
│   ├── pd_model_metadata.json          ← Model metadata
│   └── __init__.py
└── train_pd_model.py                   ← Training script
```

---

## Model Details

### Current Model (Demo)

**File:** `ml_models/pd_model.pkl`

**Type:** RandomForestRegressor (scikit-learn)

**Created:** June 5, 2026

**Version:** 1.0.0

**Data Type:** Synthetic (Demo) - Replace with real data in production

### Model Specifications

| Property | Value |
|----------|-------|
| **Algorithm** | Random Forest Regressor |
| **Estimators** | 100 trees |
| **Max Depth** | 10 |
| **Input Features** | 4 (D/E, Coverage, Profit, Liquidity) |
| **Output** | PD (0.5% to 50%) |
| **Training Samples** | 500 (synthetic) |
| **Test Samples** | 100 (synthetic) |

### Model Performance (Demo)

```
Training Metrics:
  R² Score: 0.7631
  RMSE: 0.53%

Test Metrics:
  R² Score: 0.1195
  RMSE: 1.14%

Feature Importance:
  D/E Ratio: 32.61%
  Interest Coverage: 28.36%
  Liquidity Ratio: 22.98%
  Profitability: 16.05%
```

---

## How to Use the Trained Model

### Option 1: Use in Web Application (Automatic)

The Flask API automatically loads and uses the model:

```bash
# Start the Flask server
python app.py

# Access at http://127.0.0.1:5000/borrower-info.html
# Select "Machine Learning" for PD method
# Click Calculate Risk Parameters
```

**Endpoints:**
- `POST /api/predict-pd-ml` - Get ML-based PD prediction
- `GET /api/model-info` - Get model metadata

### Option 2: Load Model in Python

```python
import joblib

# Load the trained model
model = joblib.load('ml_models/pd_model.pkl')

# Prepare input data (4 features)
import numpy as np
borrower_data = np.array([[
    1.5,   # D/E Ratio
    2.5,   # Interest Coverage
    0.08,  # Profitability (8%)
    1.2    # Liquidity Ratio
]])

# Make prediction
pd_prediction = model.predict(borrower_data)[0]  # Returns PD as decimal (e.g., 0.04 = 4%)
print(f"PD: {pd_prediction * 100:.2f}%")
```

### Option 3: Load with Metadata

```python
import joblib
import json

# Load model
model = joblib.load('ml_models/pd_model.pkl')

# Load metadata
with open('ml_models/pd_model_metadata.json', 'r') as f:
    metadata = json.load(f)

print(f"Model Type: {metadata['model_type']}")
print(f"Version: {metadata['version']}")
print(f"Features: {', '.join(metadata['features'])}")
print(f"Data Type: {metadata['data_type']}")
```

---

## How to Retrain with Real Data

### Step 1: Prepare Real Historical Data

You need a CSV or DataFrame with:

```
Column Headers:
- de_ratio (float): Debt-to-Equity Ratio
- interest_coverage (float): Interest Coverage Ratio
- profitability (float): Profitability Margin (as decimal: 0.08 = 8%)
- liquidity_ratio (float): Liquidity Ratio
- pd_actual (float): Actual PD outcome (0.005 = 0.5%, 0.20 = 20%)

Example:
de_ratio,interest_coverage,profitability,liquidity_ratio,pd_actual
1.5,2.5,0.08,1.2,0.04
2.0,1.8,0.05,1.0,0.07
2.8,0.9,-0.05,0.8,0.16
```

### Step 2: Modify train_pd_model.py

Replace the `generate_synthetic_data()` function with real data loading:

```python
import pandas as pd
from sklearn.model_selection import train_test_split

def load_real_data(csv_file):
    """Load real historical borrower data"""
    df = pd.read_csv(csv_file)
    
    # Extract features
    X = df[['de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio']].values
    
    # Extract target
    y = df['pd_actual'].values
    
    return X, y

# In the main section, replace:
# X, y = generate_synthetic_data()
# With:
X, y = load_real_data('path/to/your/real_data.csv')
```

### Step 3: Run Training Script

```bash
# Train model with real data
python train_pd_model.py

# This will:
# 1. Load your real data
# 2. Train RandomForestRegressor
# 3. Display performance metrics
# 4. Save model to ml_models/pd_model.pkl
# 5. Save metadata to ml_models/pd_model_metadata.json
```

### Step 4: Test the New Model

```bash
# Start Flask (it will load the new model automatically)
python app.py

# Test in the web interface or run the test suite
python test_mixed_method_scenarios.py
```

---

## Production Deployment Checklist

### Before Going Live with Real Data:

- [ ] Collect 3-5 years of historical borrower data
- [ ] Ensure PD labels are accurate (actual defaults, not estimated)
- [ ] Clean and validate data (remove outliers, handle missing values)
- [ ] Split data into train/test sets (80/20 or 70/30)
- [ ] Train model with `train_pd_model.py`
- [ ] Validate performance metrics on test set
- [ ] Compare model predictions with rule-based method
- [ ] Implement A/B testing (deploy both methods)
- [ ] Monitor model performance in production
- [ ] Set up retraining schedule (quarterly or annually)

### Model Monitoring in Production

Track these metrics periodically:

```
1. Prediction Accuracy
   - Compare ML predictions vs actual outcomes
   - Track prediction error over time

2. Feature Importance
   - Ensure important features remain stable
   - Detect data drift

3. Portfolio Impact
   - Monitor RWA changes when using ML predictions
   - Track capital requirement changes
   - Compare with rule-based method

4. Model Stability
   - Detect concept drift
   - Monitor prediction distribution
   - Identify when retraining is needed
```

---

## Demo Model Limitations

The current model uses **synthetic data** for demonstration:

❌ **NOT for production use** - Uses randomly generated data
❌ **Limited accuracy** - Training R² = 0.76, Test R² = 0.12
❌ **Unrealistic relationships** - Simple formulas, not real default patterns
❌ **Small sample size** - Only 500 samples (real models need 10,000+)

✅ **Good for** - Testing the architecture, UI/UX, calculations
✅ **Good for** - Understanding how ML integration works
✅ **Good for** - Development and testing purposes

---

## Alternative Models to Consider

### 1. Logistic Regression (Default Classifier)
```
Pros: Interpretable, fast, probabilistic output
Cons: Assumes linear relationships
Use: Simple PD estimation
```

### 2. Gradient Boosting (XGBoost, LightGBM)
```
Pros: Higher accuracy, handles interactions, feature importance
Cons: Slower training, more complex
Use: Production models with real data
```

### 3. Neural Networks
```
Pros: Handles complex patterns, flexible
Cons: Black box, needs lots of data, slow inference
Use: Large datasets (100k+ samples)
```

### 4. Ensemble Methods
```
Pros: Combine multiple models for robustness
Cons: Complex, maintenance overhead
Use: Production with critical risk assessment
```

---

## API Integration

### Flask Endpoint: POST /api/predict-pd-ml

**Request:**
```json
{
  "de_ratio": 1.5,
  "interest_coverage": 2.5,
  "profitability": 0.08,
  "liquidity_ratio": 1.2
}
```

**Response (Success):**
```json
{
  "pd": 0.0406,
  "pd_percentage": "4.06%",
  "method": "ML",
  "model_version": "1.0.0",
  "note": "Demo model trained on synthetic data"
}
```

**Response (Error):**
```json
{
  "error": "ML model not found",
  "message": "Please train the model first: python train_pd_model.py",
  "fallback_to_rule_based": true
}
```

---

## Files Reference

### Model Files
- `ml_models/pd_model.pkl` - The actual trained model (binary)
- `ml_models/pd_model_metadata.json` - Model metadata and version

### Training & Testing
- `train_pd_model.py` - Script to train/retrain the model
- `test_ml_integration.py` - Tests ML prediction accuracy
- `test_phase2_e2e.py` - End-to-end tests including ML
- `test_mixed_method_scenarios.py` - Tests all method combinations

### Documentation
- `PHASE_2_COMPLETION.md` - Phase 2 implementation details
- `PHASE_2_SUMMARY.txt` - Phase 2 summary
- `PHASE_2_TEST_RESULTS.txt` - Detailed test results
- `ML_MODEL_GUIDE.md` - This file

---

## Quick Commands

### Train with Real Data
```bash
python train_pd_model.py
```

### Start Flask Server
```bash
python app.py
```

### Run ML Integration Tests
```bash
python test_ml_integration.py
```

### Run All Tests (Including ML)
```bash
python test_phase2_e2e.py
```

### Load Model in Python REPL
```python
import joblib
model = joblib.load('ml_models/pd_model.pkl')
prediction = model.predict([[1.5, 2.5, 0.08, 1.2]])[0]
print(f"PD: {prediction*100:.2f}%")
```

---

## Contact & Support

**Project:** Banking Credit Risk Calculator  
**Phase:** 2 - Machine Learning Integration  
**Status:** Production Ready (Demo Model)  
**Last Updated:** June 5, 2026

For questions about model training or production deployment:
- Check `PHASE_2_COMPLETION.md` for architecture details
- Review `train_pd_model.py` for training configuration
- Run `test_mixed_method_scenarios.py` to verify functionality

---

**Note:** Replace the demo model with a real model trained on actual historical data before production use.
