"""
Banking Credit Risk Calculator - Flask Backend
Flask API for AIRB and Standardized Approach calculations
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from config import config
from backend.calculations import (
    AIRBCalculations,
    StandardizedApproachCalculations,
    PortfolioCalculations
)

# Initialize Flask app
app = Flask(__name__, static_folder='public', static_url_path='/static')

# Load configuration
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Enable CORS for all routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Load ML model once at startup (not on every request)
import joblib as _joblib

_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ml_models', 'pd_model.pkl')
try:
    _pd_model = _joblib.load(_MODEL_PATH)
except Exception as e:
    print(f"WARNING: Could not load ML model at startup: {e}")
    _pd_model = None

# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve main application"""
    return send_from_directory('public', 'borrower-info.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (HTML, CSS, JS)"""
    return send_from_directory('public', filename)

# ============================================================================
# AIRB CALCULATION ENDPOINTS
# ============================================================================

@app.route('/api/calculate-pd', methods=['POST'])
def calculate_pd():
    """Calculate Probability of Default from financial metrics

    Expected request body:
    {
        "de_ratio": float,
        "interest_coverage": float,
        "profitability": float,
        "liquidity_ratio": float
    }
    """
    try:
        data = request.get_json()
        result = AIRBCalculations.calculate_pd(data)
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-correlation', methods=['POST'])
def calculate_correlation():
    """Calculate correlation coefficient from PD

    Expected request body:
    {
        "pd": float (decimal, e.g., 0.035 for 3.5%)
    }
    """
    try:
        data = request.get_json()
        pd = data.get('pd')
        result = AIRBCalculations.calculate_correlation(pd)
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-maturity-adjustment', methods=['POST'])
def calculate_maturity_adjustment():
    """Calculate maturity adjustment factor

    Expected request body:
    {
        "maturity": float (years, 1-5),
        "lgd": float (decimal, 0-1),
        "pd": float (decimal, 0.0001-1.0)
    }
    """
    try:
        data = request.get_json()
        maturity = data.get('maturity')
        lgd = data.get('lgd')
        pd = data.get('pd')
        result = AIRBCalculations.calculate_maturity_adjustment(maturity, lgd, pd)
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-lgd', methods=['POST'])
def calculate_lgd():
    """Calculate Loss Given Default

    Expected request body:
    {
        "seniority": str (Senior Secured, Senior Unsecured, Subordinated, Junior),
        "collateral_type": str (optional),
        "collateral_value": float (optional),
        "exposure": float (optional)
    }
    """
    try:
        data = request.get_json()
        seniority = data.get('seniority')
        collateral_type = data.get('collateral_type')
        collateral_value = data.get('collateral_value', 0)
        exposure = data.get('exposure', 0)

        result = AIRBCalculations.calculate_lgd(
            seniority, collateral_type, collateral_value, exposure
        )
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-risk-weight-airb', methods=['POST'])
def calculate_risk_weight_airb():
    """Calculate AIRB risk weight

    Expected request body:
    {
        "pd": float (decimal),
        "lgd": float (percentage, 0-100),
        "ead": float,
        "maturity": float (1-5),
        "borrower_type": str (optional)
    }
    """
    try:
        data = request.get_json()
        pd = data.get('pd')
        lgd = data.get('lgd')
        ead = data.get('ead')
        maturity = data.get('maturity')
        borrower_type = data.get('borrower_type', 'Corporate')

        result = AIRBCalculations.calculate_risk_weight(pd, lgd, ead, maturity, borrower_type)
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-rwa-airb', methods=['POST'])
def calculate_rwa_airb():
    """Calculate AIRB RWA and capital requirement

    Expected request body:
    {
        "exposure": float,
        "risk_weight": float (percentage)
    }
    """
    try:
        data = request.get_json()
        exposure = data.get('exposure')
        risk_weight = data.get('risk_weight')

        result = AIRBCalculations.calculate_rwa_and_capital(exposure, risk_weight)
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# STANDARDIZED APPROACH ENDPOINTS
# ============================================================================

@app.route('/api/get-risk-weight-sa', methods=['POST'])
def get_risk_weight_sa():
    """Get Standardized Approach risk weight from tables

    Expected request body:
    {
        "category": str (Corporate, Sovereign, Bank, Financial),
        "rating": str (AAA-D, Unrated)
    }
    """
    try:
        data = request.get_json()
        category = data.get('category')
        rating = data.get('rating')

        result = StandardizedApproachCalculations.get_risk_weight(category, rating)
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-adjusted-exposure', methods=['POST'])
def calculate_adjusted_exposure():
    """Calculate exposure adjusted for collateral

    Expected request body:
    {
        "exposure": float,
        "collateral_type": str (optional),
        "collateral_value": float (optional)
    }
    """
    try:
        data = request.get_json()
        exposure = data.get('exposure')
        collateral_type = data.get('collateral_type')
        collateral_value = data.get('collateral_value', 0)

        result = StandardizedApproachCalculations.calculate_with_collateral(
            exposure, collateral_type, collateral_value
        )
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-rwa-sa', methods=['POST'])
def calculate_rwa_sa():
    """Calculate Standardized Approach RWA and capital

    Expected request body:
    {
        "exposure": float,
        "risk_weight": float (percentage),
        "collateral_type": str (optional),
        "collateral_value": float (optional)
    }
    """
    try:
        data = request.get_json()
        exposure = data.get('exposure')
        risk_weight = data.get('risk_weight')
        collateral_type = data.get('collateral_type')
        collateral_value = data.get('collateral_value', 0)

        result = StandardizedApproachCalculations.calculate_rwa_and_capital(
            exposure, risk_weight, collateral_type, collateral_value
        )
        return jsonify(result), 200 if 'error' not in result else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# PORTFOLIO ENDPOINTS
# ============================================================================

@app.route('/api/portfolio-summary', methods=['POST'])
def portfolio_summary():
    """Calculate portfolio summary statistics

    Expected request body:
    {
        "loans": [
            {
                "exposure": float,
                "rwa": float,
                "capital_required": float,
                "calculation_method": str (AIRB or SA),
                "pd": float (for AIRB),
                "risk_weight": float (for SA)
            },
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        loans = data.get('loans', [])

        result = PortfolioCalculations.calculate_portfolio_summary(loans)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# MACHINE LEARNING ENDPOINTS
# ============================================================================

@app.route('/api/predict-pd-ml', methods=['POST'])
def predict_pd_ml():
    """Predict Probability of Default using ML model

    Expected request body:
    {
        "de_ratio": float,
        "interest_coverage": float,
        "profitability": float,
        "liquidity_ratio": float
    }
    """
    try:
        data = request.get_json()

        # Check if model was loaded at startup
        if _pd_model is None:
            return jsonify({
                'error': 'ML model not available',
                'message': 'Model could not be loaded at startup'
            }), 503

        # Prepare features
        features = [[
            float(data.get('de_ratio', 0)),
            float(data.get('interest_coverage', 0)),
            float(data.get('profitability', 0)),
            float(data.get('liquidity_ratio', 0))
        ]]

        # Make prediction
        pd_decimal = float(_pd_model.predict(features)[0])

        # Ensure PD is within valid range
        pd_decimal = max(0.0001, min(1.0, pd_decimal))

        return jsonify({
            'pd': round(pd_decimal, 4),
            'pd_percentage': round(pd_decimal * 100, 2),
            'method': 'ML',
            'model_type': 'RandomForest',
            'model_version': '1.0.0',
            'note': 'Demo model trained on synthetic data. Use real data in production.'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/model-info', methods=['GET'])
def model_info():
    """Get information about the ML model"""
    try:
        import json

        metadata_path = os.path.join(os.path.dirname(__file__), 'ml_models', 'pd_model_metadata.json')

        info = {
            'status': 'available' if _pd_model is not None else 'not_available',
            'model_path': _MODEL_PATH
        }

        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                info['metadata'] = json.load(f)

        return jsonify(info), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# HEALTH CHECK & INFO ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'Banking Credit Risk Calculator API',
        'version': '1.0.0',
        'environment': config_name
    }), 200

@app.route('/api/info', methods=['GET'])
def api_info():
    """API information"""
    return jsonify({
        'name': 'Banking Credit Risk Calculator',
        'version': '1.0.0',
        'description': 'Flask backend for AIRB and Standardized Approach credit risk calculations',
        'endpoints': {
            'AIRB': {
                'calculate_pd': 'POST /api/calculate-pd',
                'calculate_correlation': 'POST /api/calculate-correlation',
                'calculate_maturity_adjustment': 'POST /api/calculate-maturity-adjustment',
                'calculate_lgd': 'POST /api/calculate-lgd',
                'calculate_risk_weight': 'POST /api/calculate-risk-weight-airb',
                'calculate_rwa': 'POST /api/calculate-rwa-airb'
            },
            'Standardized': {
                'get_risk_weight': 'POST /api/get-risk-weight-sa',
                'calculate_adjusted_exposure': 'POST /api/calculate-adjusted-exposure',
                'calculate_rwa': 'POST /api/calculate-rwa-sa'
            },
            'Portfolio': {
                'portfolio_summary': 'POST /api/portfolio-summary'
            }
        }
    }), 200

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(405)
def method_not_allowed(error):
    """405 error handler"""
    return jsonify({'error': 'Method not allowed'}), 405

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Development server
    print(f"Starting Banking Credit Risk Calculator API")
    print(f"Environment: {config_name}")
    print(f"Debug mode: {app.debug}")
    print(f"CORS enabled for all /api/* routes")

    app.run(
        host='127.0.0.1',
        port=5000,
        debug=app.debug,
        use_reloader=True
    )
