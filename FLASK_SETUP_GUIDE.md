# Flask Backend Setup Guide - Phase 1

**Date:** June 5, 2026  
**Status:** Phase 1 Implementation Started  
**Objective:** Migrate calculation logic from JavaScript to Flask backend

---

## What Was Created

### New Files
```
banking-credit-risk/
├── app.py                          # Flask application with all endpoints
├── config.py                       # Configuration management
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables
├── FLASK_SETUP_GUIDE.md           # This file
│
├── backend/
│   ├── __init__.py                # Backend module
│   └── calculations.py            # All calculation logic (migrated from JS)
│
└── ml_models/
    └── __init__.py                # ML models directory (for future)
```

### Key Components

**1. Flask Application (app.py)**
- 25+ API endpoints for all calculations
- CORS enabled for frontend integration
- Static file serving (HTML/CSS/JS)
- Error handling and health checks

**2. Calculation Engine (backend/calculations.py)**
- **AIRBCalculations** class: All AIRB methodology calculations
  - `calculate_pd()` - Probability of Default
  - `calculate_correlation()` - Correlation coefficient
  - `calculate_maturity_adjustment()` - Maturity factor
  - `calculate_lgd()` - Loss Given Default
  - `calculate_risk_weight()` - Risk weight calculation
  - `calculate_rwa_and_capital()` - RWA and capital requirement

- **StandardizedApproachCalculations** class: Standardized Approach
  - `get_risk_weight()` - Risk weight lookup from tables
  - `calculate_with_collateral()` - Collateral adjustment
  - `calculate_rwa_and_capital()` - RWA and capital

- **PortfolioCalculations** class: Portfolio summaries
  - `calculate_portfolio_summary()` - Aggregate portfolio statistics

**3. Configuration (config.py)**
- Development, Production, Testing modes
- Database configuration
- Session management
- CORS settings

---

## Installation Steps

### Step 1: Install Python (if not already installed)
```powershell
# Check Python version (should be 3.9 or higher)
python --version

# If not installed, download from https://www.python.org/
```

### Step 2: Create Virtual Environment
```powershell
# Navigate to project directory
cd "C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk"

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\Activate.ps1

# On Windows, you might see an execution policy error. If so, run:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then try again: .\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Verify installation
pip list
```

### Step 4: Run Flask Server
```powershell
# Make sure virtual environment is activated
# Run Flask development server
flask run

# Or alternatively:
python app.py

# You should see:
# Running on http://127.0.0.1:5000
```

---

## Testing the Flask API

### Option 1: Test with curl (PowerShell)
```powershell
# Health check
$response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/health"
$response.Content | ConvertFrom-Json | Format-Table

# Calculate PD
$body = @{
    de_ratio = 1.5
    interest_coverage = 2.5
    profitability = 0.08
    liquidity_ratio = 1.2
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/calculate-pd" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$response.Content | ConvertFrom-Json | Format-Table
```

### Option 2: Test with Python (requests library)
```python
import requests
import json

BASE_URL = "http://127.0.0.1:5000/api"

# Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# Calculate PD
data = {
    "de_ratio": 1.5,
    "interest_coverage": 2.5,
    "profitability": 0.08,
    "liquidity_ratio": 1.2
}
response = requests.post(f"{BASE_URL}/calculate-pd", json=data)
print(response.json())
```

### Option 3: Test with Postman
1. Download Postman (https://www.postman.com/)
2. Create new request
3. Method: POST
4. URL: http://127.0.0.1:5000/api/calculate-pd
5. Body (JSON):
```json
{
    "de_ratio": 1.5,
    "interest_coverage": 2.5,
    "profitability": 0.08,
    "liquidity_ratio": 1.2
}
```
6. Send request

---

## Available API Endpoints

### AIRB Calculation Endpoints

**1. Calculate PD**
```
POST /api/calculate-pd
Content-Type: application/json

{
    "de_ratio": 1.5,
    "interest_coverage": 2.5,
    "profitability": 0.08,
    "liquidity_ratio": 1.2
}

Response: { "pd": 0.035, "pd_percentage": 3.5, ... }
```

**2. Calculate LGD**
```
POST /api/calculate-lgd
{
    "seniority": "Senior Unsecured",
    "collateral_type": "Corporate Bonds",
    "collateral_value": 50000,
    "exposure": 100000
}

Response: { "lgd": 0.40, "lgd_percentage": 40.0, ... }
```

**3. Calculate Risk Weight (AIRB)**
```
POST /api/calculate-risk-weight-airb
{
    "pd": 0.035,
    "lgd": 45.0,
    "ead": 100000,
    "maturity": 3,
    "borrower_type": "Corporate"
}

Response: { "risk_weight": 65.5, "components": {...} }
```

**4. Calculate RWA (AIRB)**
```
POST /api/calculate-rwa-airb
{
    "exposure": 100000,
    "risk_weight": 65.5
}

Response: { "rwa": 65500.0, "capital_required": 5240.0, ... }
```

### Standardized Approach Endpoints

**1. Get Risk Weight**
```
POST /api/get-risk-weight-sa
{
    "category": "Corporate",
    "rating": "A"
}

Response: { "risk_weight": 50, "category": "Corporate", "rating": "A" }
```

**2. Calculate Adjusted Exposure**
```
POST /api/calculate-adjusted-exposure
{
    "exposure": 100000,
    "collateral_type": "Government Securities",
    "collateral_value": 30000
}

Response: { "adjusted_exposure": 98500.0, ... }
```

**3. Calculate RWA (SA)**
```
POST /api/calculate-rwa-sa
{
    "exposure": 100000,
    "risk_weight": 50,
    "collateral_type": "Government Securities",
    "collateral_value": 30000
}

Response: { "rwa": 48500.0, "capital_required": 3880.0, ... }
```

### Portfolio Endpoint

**Calculate Portfolio Summary**
```
POST /api/portfolio-summary
{
    "loans": [
        {
            "exposure": 100000,
            "rwa": 65000,
            "capital_required": 5200,
            "calculation_method": "AIRB",
            "pd": 0.035
        },
        {
            "exposure": 50000,
            "rwa": 25000,
            "capital_required": 2000,
            "calculation_method": "SA",
            "risk_weight": 50
        }
    ]
}

Response: {
    "total_loans": 2,
    "total_exposure": 150000.0,
    "total_rwa": 90000.0,
    "average_risk_density": 60.0,
    "total_capital_required": 7200.0,
    ...
}
```

---

## Next Steps: Integrate with HTML Frontend

### Step 1: Update borrower-info.html
Replace JavaScript calculation functions with API calls:

**Before (JavaScript):**
```javascript
const pd = calculatePD(deRatio, interestCoverage, profitability, liquidity);
```

**After (API Call):**
```javascript
const response = await fetch('/api/calculate-pd', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        de_ratio: deRatio,
        interest_coverage: interestCoverage,
        profitability: profitability,
        liquidity_ratio: liquidity
    })
});
const data = await response.json();
const pd = data.pd;
```

### Step 2: Create Helper Functions in HTML
Add these to borrower-info.html:

```javascript
// API Helper
const API_BASE = 'http://127.0.0.1:5000/api';

async function apiCall(endpoint, data) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return await response.json();
    } catch (error) {
        console.error(`API Error: ${error}`);
        return { error: error.message };
    }
}

// Calculation helpers
async function calculatePD(metrics) {
    return await apiCall('/calculate-pd', metrics);
}

async function calculateLGD(seniority, collateral) {
    return await apiCall('/calculate-lgd', {
        seniority: seniority,
        collateral_type: collateral.type,
        collateral_value: collateral.value,
        exposure: collateral.exposure
    });
}

// ... more helpers as needed
```

---

## Running Both Frontend and Backend

### Terminal 1: Start Flask Backend
```powershell
cd "C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk"
.\venv\Scripts\Activate.ps1
flask run
# Server running on http://127.0.0.1:5000
```

### Terminal 2: Start Frontend
```powershell
# Open borrower-info.html in browser
Start-Process "http://127.0.0.1:5000/"
```

The HTML will now make API calls to Flask instead of using JavaScript calculations.

---

## Troubleshooting

### Issue: "flask: The term 'flask' is not recognized"
**Solution:** Activate virtual environment first
```powershell
.\venv\Scripts\Activate.ps1
```

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution:** Install dependencies
```powershell
pip install -r requirements.txt
```

### Issue: "Port 5000 already in use"
**Solution:** Use different port
```powershell
flask run --port 5001
```

### Issue: CORS errors from frontend
**Solution:** Ensure CORS is enabled in Flask (already done in app.py)

### Issue: API returns 404
**Solution:** Check endpoint URL spelling and HTTP method (POST vs GET)

---

## Phase 1 Checklist

- [x] Create Flask project structure
- [x] Create requirements.txt with dependencies
- [x] Migrate PD calculation to Python
- [x] Migrate LGD calculation to Python
- [x] Migrate RWA calculation to Python
- [x] Create Flask API endpoints (25+ endpoints)
- [x] Set up CORS for frontend integration
- [x] Create database configuration
- [ ] Update HTML to call Flask APIs (Next step)
- [ ] Test all calculations (Next step)
- [ ] Verify results match original (Next step)

---

## Next Phase: Machine Learning Integration

Once Phase 1 is stable:

1. **Train ML Model** for PD prediction
2. **Export as pickle file** (`pd_model.pkl`)
3. **Create Flask endpoint** `/api/predict-pd-ml`
4. **Update HTML** to offer ML vs Rule-based option

Example Flask endpoint:
```python
@app.route('/api/predict-pd-ml', methods=['POST'])
def predict_pd_ml():
    import joblib
    model = joblib.load('ml_models/pd_model.pkl')
    features = [data['de_ratio'], data['interest_coverage'], ...]
    pd_prediction = model.predict([features])[0]
    return jsonify({'pd': pd_prediction})
```

---

## Resources

- Flask Documentation: https://flask.palletsprojects.com/
- Python Virtual Environments: https://docs.python.org/3/tutorial/venv.html
- RESTful API Design: https://www.restfulapi.net/
- CORS Handling: https://flask-cors.readthedocs.io/

---

## Questions?

Refer to ARCHITECTURE_RECOMMENDATIONS.md for overall design rationale, or CLAUDE.md for project context.

**Document Status:** Phase 1 Setup Complete  
**Last Updated:** June 5, 2026  
**Owner:** Development Team
