from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from backend.calculations import (
    AIRBCalculations,
    StandardizedApproachCalculations,
    PortfolioCalculations
)

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# ── Frontend static serving ───────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('public', filename)

# ── Health check ──────────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': 'Banking Credit Risk Calculator'})

# ── AIRB endpoints ────────────────────────────────────────────────────────────

@app.route('/api/calculate-pd', methods=['POST'])
def calculate_pd():
    data = request.get_json(force=True)
    return jsonify(AIRBCalculations.calculate_pd(data))

@app.route('/api/calculate-lgd', methods=['POST'])
def calculate_lgd():
    data = request.get_json(force=True)
    return jsonify(AIRBCalculations.calculate_lgd(
        data.get('seniority'),
        data.get('collateral_type'),
        float(data.get('collateral_value', 0)),
        float(data.get('exposure', 0))
    ))

@app.route('/api/calculate-risk-weight', methods=['POST'])
def calculate_risk_weight():
    data = request.get_json(force=True)
    return jsonify(AIRBCalculations.calculate_risk_weight(
        data.get('pd'),
        data.get('lgd'),
        data.get('ead'),
        data.get('maturity'),
        data.get('borrower_type', 'Corporate')
    ))

@app.route('/api/calculate-rwa', methods=['POST'])
def calculate_rwa():
    data = request.get_json(force=True)
    return jsonify(AIRBCalculations.calculate_rwa_and_capital(
        data.get('exposure'),
        data.get('risk_weight')
    ))

# ── Standardized Approach endpoints ──────────────────────────────────────────

@app.route('/api/sa-risk-weight', methods=['POST'])
def sa_risk_weight():
    data = request.get_json(force=True)
    return jsonify(StandardizedApproachCalculations.get_risk_weight(
        data.get('category'),
        data.get('rating')
    ))

@app.route('/api/sa-calculate', methods=['POST'])
def sa_calculate():
    data = request.get_json(force=True)
    return jsonify(StandardizedApproachCalculations.calculate_rwa_and_capital(
        data.get('exposure'),
        data.get('risk_weight'),
        data.get('collateral_type'),
        float(data.get('collateral_value', 0))
    ))

# ── Portfolio endpoint ────────────────────────────────────────────────────────

@app.route('/api/portfolio-summary', methods=['POST'])
def portfolio_summary():
    data = request.get_json(force=True)
    return jsonify(PortfolioCalculations.calculate_portfolio_summary(
        data.get('loans', [])
    ))

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run()
