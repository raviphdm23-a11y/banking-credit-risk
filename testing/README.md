# Testing Suite - Banking Credit Risk Calculator

This folder contains all automated tests for the Flask backend and API integration.

## Test Files

### 1. `test_api.py`
- **Purpose:** Tests Flask API endpoints
- **Coverage:** Health checks, PD calculation, LGD calculation, Risk weight lookups
- **Run:** `python test_api.py`

### 2. `test_ml_integration.py`
- **Purpose:** Tests ML model integration
- **Coverage:** `/api/predict-pd-ml` endpoint, RandomForest model loading
- **Run:** `python test_ml_integration.py`

### 3. `test_frontend_integration.py`
- **Purpose:** Tests frontend to Flask API wiring
- **Coverage:** API calls from borrower-info.html, PD/LGD calculations via API
- **Run:** `python test_frontend_integration.py`

### 4. `test_complete_flow.py`
- **Purpose:** End-to-end workflow test
- **Coverage:** Full loan entry → calculation → portfolio recording
- **Run:** `python test_complete_flow.py`

### 5. `test_simple_workflow.py`
- **Purpose:** Basic workflow verification
- **Coverage:** Simple loan entry and API calls
- **Run:** `python test_simple_workflow.py`

### 6. `test_mixed_method_scenarios.py`
- **Purpose:** Tests mixed AIRB and SA scenarios
- **Coverage:** Portfolio with both AIRB and Standardized Approach loans
- **Run:** `python test_mixed_method_scenarios.py`

### 7. `test_phase2_e2e.py`
- **Purpose:** End-to-end tests for Phase 2 (SA) implementation
- **Coverage:** Standardized Approach calculations and risk weights
- **Run:** `python test_phase2_e2e.py`

## Running Tests

### Run All Tests:
```bash
cd testing
python test_api.py && python test_ml_integration.py && python test_frontend_integration.py
```

### Run Specific Test:
```bash
python test_api.py
```

### Run with Flask Server:
Ensure Flask is running on http://127.0.0.1:5000 before running tests:
```bash
python test_complete_flow.py
```

## Requirements

All tests require:
- Flask >= 2.3.0
- Flask-CORS >= 4.0.0
- requests (for HTTP calls)
- scikit-learn >= 1.3.0 (for ML tests)
- joblib >= 1.3.0 (for ML tests)

Install with:
```bash
pip install -r ../requirements.txt
```

## Notes

- Tests assume Flask server is running on `http://127.0.0.1:5000`
- ML tests verify the RandomForest model is loaded and functioning
- Frontend integration tests check that API calls are being made correctly
- All tests use synthetic/demo data
