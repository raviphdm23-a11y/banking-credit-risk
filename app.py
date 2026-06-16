"""
Banking Credit Risk Calculator - Flask Backend
Flask API for AIRB, Standardized Approach calculations, and Admin/ML Training.
"""

import os
import json
import threading
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
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/operations/api/*": {"origins": "*"}})

# ── Banking Operations (bank.db — direct sqlite3, read-only) ─────────────────
import sqlite3 as _sqlite3

_OPS_DB_PATH = os.path.join(os.path.dirname(__file__), 'bank.db')

def _ops_conn():
    """Return a read-only sqlite3 connection to bank.db with dict-like rows."""
    conn = _sqlite3.connect(_OPS_DB_PATH)
    conn.row_factory = _sqlite3.Row
    return conn

# Load ML model once at startup (not on every request)
import joblib as _joblib

_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ml_models', 'pd_model.pkl')
try:
    _pd_model = _joblib.load(_MODEL_PATH)
except Exception as e:
    print(f"WARNING: Could not load ML model at startup: {e}")
    _pd_model = None

# Initialise AssessmentEngine once — stateless, thread-safe per request
from backend.assessment_engine import AssessmentEngine as _AssessmentEngine

def _get_model_version():
    try:
        meta_path = os.path.join(os.path.dirname(__file__), 'ml_models', 'pd_model_metadata.json')
        with open(meta_path) as f:
            return json.load(f).get('version', 'unknown')
    except Exception:
        return 'unknown'

_assessment_engine = _AssessmentEngine(_pd_model, _get_model_version())

# In-memory report cache keyed by report_id (uuid).
_report_cache: dict = {}

# ── File-based persistence paths ───────────────────────────────────────────
_REPORTS_DIR   = os.path.join(os.path.dirname(__file__), 'data', 'reports')
_AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), 'data', 'audit_log.json')
_audit_lock = threading.Lock()

os.makedirs(_REPORTS_DIR, exist_ok=True)

def _save_report(report_id: str, findings: dict) -> None:
    """Persist findings to data/reports/<report_id>.json. Silent on error."""
    try:
        path = os.path.join(_REPORTS_DIR, f'{report_id}.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(findings, fh, ensure_ascii=False, default=str)
    except Exception as e:
        print(f'[report] save error for {report_id}: {e}')

def _load_report(report_id: str) -> dict | None:
    """Load findings from disk if not in memory cache. Returns None if missing."""
    try:
        path = os.path.join(_REPORTS_DIR, f'{report_id}.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                return json.load(fh)
    except Exception as e:
        print(f'[report] load error for {report_id}: {e}')
    return None

def _log_audit(event: str, report_id: str, findings: dict,
               actor: str = 'system', note: str = '') -> None:
    """Append one event to the audit log (thread-safe)."""
    from datetime import datetime, timezone
    entry = {
        'event':       event,
        'report_id':   report_id,
        'borrower_id': (findings.get('inputs') or {}).get('borrower_id', ''),
        'decision':    (findings.get('recommendation') or {}).get('decision', ''),
        'grade':       (findings.get('rating') or {}).get('grade', ''),
        'timestamp':   datetime.now(timezone.utc).isoformat(),
        'actor':       actor,
        'note':        note,
    }
    with _audit_lock:
        try:
            log = []
            if os.path.exists(_AUDIT_LOG_PATH):
                with open(_AUDIT_LOG_PATH, encoding='utf-8') as fh:
                    log = json.load(fh)
        except Exception:
            log = []
        log.append(entry)
        try:
            with open(_AUDIT_LOG_PATH, 'w', encoding='utf-8') as fh:
                json.dump(log, fh, ensure_ascii=False, default=str, indent=2)
        except Exception as e:
            print(f'[audit] write error: {e}')

# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve home page with navigation"""
    return send_from_directory('public', 'index.html')

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
    """Predict Probability of Default using ML model.

    Core financial ratios are required. KYC fields are optional and default
    to representative median values when omitted (backward-compatible).
    """
    try:
        data = request.get_json()

        if _pd_model is None:
            return jsonify({
                'error': 'ML model not available',
                'message': 'Model could not be loaded at startup'
            }), 503

        # Build feature vector matching trainer.py FEATURE_COLS order.
        # KYC defaults are population medians so callers that only supply the
        # four financial ratios still get a sensible prediction.
        features = [[
            float(data.get('de_ratio', 0)),
            float(data.get('interest_coverage', 0)),
            float(data.get('profitability', 0)),
            float(data.get('liquidity_ratio', 0)),
            float(data.get('age', 35)),
            float(data.get('employment_type_enc', 2)),
            float(data.get('years_employed', 5)),
            float(data.get('annual_income', 500000)),
            float(data.get('foir', 0.4)),
            float(data.get('num_dependents', 2)),
            float(data.get('city_tier_enc', 2)),
            float(data.get('education_enc', 3)),
            float(data.get('residence_type_enc', 2)),
            float(data.get('loan_purpose_enc', 1)),
            float(data.get('cibil_score', 700)),
            float(data.get('previous_default_flag', 0)),
            float(data.get('months_as_customer', 24)),
            float(data.get('num_late_payments_past_12m', 0)),
            float(data.get('existing_loans_count', 1)),
            float(data.get('num_existing_products', 2)),
            float(data.get('is_rural', 0)),
        ]]

        pd_decimal = float(_pd_model.predict(features)[0])
        pd_decimal = max(0.0001, min(1.0, pd_decimal))

        breakdown = {
            'base_rate': 0.5,
            'de_ratio_adjustment': round(float(data.get('de_ratio', 0)) * 0.8, 4),
            'interest_coverage_adjustment': round(max(0, (4.0 - float(data.get('interest_coverage', 0))) * 0.5), 4),
            'profitability_adjustment': round(max(0, -float(data.get('profitability', 0)) * 0.15), 4),
            'liquidity_adjustment': round(max(0, (1.5 - float(data.get('liquidity_ratio', 0))) * 3.0), 4)
        }

        return jsonify({
            'pd': round(pd_decimal, 4),
            'pd_percentage': round(pd_decimal * 100, 2),
            'method': 'ML',
            'model_type': 'RandomForest',
            'model_version': '1.0.0',
            'breakdown': breakdown,
            'note': 'ML prediction with rule-based component breakdown for transparency'
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
# ASSESSMENT ENGINE — full borrower assessment (Step 1 engine core)
# ============================================================================

@app.route('/api/assess-borrower', methods=['POST'])
def assess_borrower():
    """
    POST /api/assess-borrower

    Produces a complete, immutable assessment findings object for one borrower,
    including: PD (point + 80% band), internal rating grade, feature attribution
    (reason codes), LGD, AIRB RWA, Expected Loss (₹), indicative risk-based
    pricing, Five C's narrative, policy knockouts, and a Approve/Refer/Decline
    recommendation.

    Required body fields:
        de_ratio            float   Debt-to-Equity ratio
        interest_coverage   float   EBIT / Interest Expense
        profitability       float   Net Profit Margin in % (e.g. 12.0 for 12%)
        liquidity_ratio     float   Current Assets / Current Liabilities
        exposure            float   EAD in INR (₹)
        seniority           str     Senior Secured | Senior Unsecured | Subordinated | Junior

    Optional:
        collateral_type     str     Cash | Government Securities | Corporate Bonds | Equities | Other
        collateral_value    float   Collateral value in INR
        maturity            float   Loan tenor in years (1–5), default 2.5
        borrower_type       str     Corporate | Sovereign | Bank | Financial
        borrower_id         str     Reference identifier
        calculation_method  str     AIRB (default) | SA
    """
    try:
        data = request.get_json(force=True) or {}
        findings = _assessment_engine.assess(data)
        return jsonify(findings), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/masterscale', methods=['GET'])
def masterscale():
    """GET /api/masterscale — return the internal rating grade table."""
    from backend.rating_masterscale import masterscale_table
    return jsonify({'grades': masterscale_table()}), 200


@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    """
    POST /api/generate-report

    Runs the full assessment and stores the findings in the server-side
    report cache. Returns a compact executive summary plus the report_id
    needed to fetch the full findings via GET /api/get-report/<report_id>.

    Accepts the same body as /api/assess-borrower.
    """
    try:
        data = request.get_json(force=True) or {}
        findings = _assessment_engine.assess(data)
        report_id = findings['report_id']
        _report_cache[report_id] = findings

        # Trim cache to last 500 reports
        if len(_report_cache) > 500:
            oldest = list(_report_cache.keys())[0]
            _report_cache.pop(oldest, None)

        # Persist to disk (survives Flask restart)
        _save_report(report_id, findings)
        _log_audit('REPORT_GENERATED', report_id, findings)

        r = findings['rating']
        p = findings['pd']
        rec = findings['recommendation']
        el  = findings['el']
        pr  = findings['pricing']

        return jsonify({
            'report_id':       report_id,
            'grade':           r['grade'],
            'grade_label':     r['label'],
            'pd_pct':          round(p['point'] * 100, 2),
            'pd_low_pct':      round(p['low'] * 100, 2),
            'pd_high_pct':     round(p['high'] * 100, 2),
            'el_amount_inr':   el['amount_inr'],
            'el_pct':          el['percentage'],
            'rate_pct':        pr['indicative_rate_pct'],
            'decision':        rec['decision'],
            'decision_label':  rec['decision_label'],
            'confidence':      rec['confidence'],
            'key_drivers':     rec['key_drivers'],
            'is_investment_grade': r['is_investment_grade'],
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-report/<report_id>', methods=['GET'])
def get_report(report_id):
    """GET /api/get-report/<report_id> — cache-aside: memory first, then disk."""
    findings = _report_cache.get(report_id) or _load_report(report_id)
    if findings is None:
        return jsonify({'error': 'Report not found or expired. Re-generate from the calculator.'}), 404
    # Warm memory cache on disk hit
    _report_cache.setdefault(report_id, findings)
    _log_audit('REPORT_VIEWED', report_id, findings, actor='officer')
    return jsonify(findings), 200


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
    return jsonify({'error': 'Method not allowed'}), 405

# ============================================================================
# ADMIN — AUTH HELPER
# ============================================================================

ADMIN_PASSWORD = '1234'

def _check_admin_auth():
    """Return True if request carries the correct admin password header."""
    return request.headers.get('X-Admin-Password') == ADMIN_PASSWORD

def _admin_auth_error():
    return jsonify({'error': 'Unauthorized. Provide correct X-Admin-Password header.'}), 401

# ============================================================================
# ADMIN — PATHS
# ============================================================================

_ML_DIR      = os.path.join(os.path.dirname(__file__), 'ml_models')
_HPARAM_PATH = os.path.join(_ML_DIR, 'hyperparameters.json')
_HISTORY_PATH= os.path.join(_ML_DIR, 'run_history.json')
_META_PATH   = os.path.join(_ML_DIR, 'pd_model_metadata.json')
_RUNS_DIR    = os.path.join(os.path.dirname(__file__), 'data', 'runs')
_TRAIN_DIR   = os.path.join(os.path.dirname(__file__), 'data', 'training')

# ============================================================================
# ADMIN API — STATUS
# ============================================================================

@app.route('/admin/api/status', methods=['GET'])
def admin_status():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        from ml_models.trainer import is_training_running, scan_training_folder
        meta = {}
        if os.path.exists(_META_PATH):
            with open(_META_PATH) as f:
                meta = json.load(f)
        history = []
        if os.path.exists(_HISTORY_PATH):
            with open(_HISTORY_PATH) as f:
                history = json.load(f)
        last_run = history[0] if history else None
        hp = {}
        if os.path.exists(_HPARAM_PATH):
            with open(_HPARAM_PATH) as f:
                hp = json.load(f)
        files = scan_training_folder()
        return jsonify({
            'model_metadata':    meta,
            'last_run':          last_run,
            'training_running':  is_training_running(),
            'files_in_training': len(files),
            'total_rows_available': sum(f['row_count'] for f in files if f['row_count'] > 0),
            'schedule':          hp.get('schedule', {}),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — DATA SOURCES
# ============================================================================

@app.route('/admin/api/data-sources', methods=['GET'])
def admin_data_sources():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        from ml_models.trainer import scan_training_folder
        files = scan_training_folder()
        return jsonify({'files': files, 'total_files': len(files),
                        'total_rows': sum(f['row_count'] for f in files if f['row_count'] > 0)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ADMIN API — HYPERPARAMETERS
# ============================================================================

@app.route('/admin/api/hyperparameters', methods=['GET'])
def admin_get_hyperparameters():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        with open(_HPARAM_PATH) as f:
            hp = json.load(f)
        return jsonify(hp), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/hyperparameters', methods=['POST'])
def admin_save_hyperparameters():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        data = request.get_json()
        with open(_HPARAM_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({'status': 'saved'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — SCHEDULE
# ============================================================================

@app.route('/admin/api/schedule', methods=['GET'])
def admin_get_schedule():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        with open(_HPARAM_PATH) as f:
            hp = json.load(f)
        return jsonify(hp.get('schedule', {})), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/schedule', methods=['POST'])
def admin_save_schedule():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        new_schedule = request.get_json()
        with open(_HPARAM_PATH) as f:
            hp = json.load(f)
        hp['schedule'] = new_schedule
        with open(_HPARAM_PATH, 'w') as f:
            json.dump(hp, f, indent=2)
        _reconfigure_scheduler(new_schedule)
        return jsonify({'status': 'saved', 'schedule': new_schedule}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — RUN HISTORY
# ============================================================================

@app.route('/admin/api/runs', methods=['GET'])
def admin_run_history():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        if not os.path.exists(_HISTORY_PATH):
            return jsonify({'runs': []}), 200
        with open(_HISTORY_PATH) as f:
            history = json.load(f)
        # Strip error tracebacks from list view (available on individual run detail)
        summary = [{k: v for k, v in r.items() if k != 'error'} for r in history]
        return jsonify({'runs': summary, 'total': len(summary)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/runs/<run_id>', methods=['GET'])
def admin_run_detail(run_id):
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        with open(_HISTORY_PATH) as f:
            history = json.load(f)
        run = next((r for r in history if r['run_id'] == run_id), None)
        if not run:
            return jsonify({'error': 'Run not found'}), 404
        return jsonify(run), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — MANUAL TRAIN
# ============================================================================

@app.route('/admin/api/train', methods=['POST'])
def admin_trigger_train():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        from ml_models.trainer import run_training, is_training_running
        if is_training_running():
            return jsonify({'error': 'Training already in progress'}), 409

        def _run():
            global _pd_model
            result = run_training(triggered_by='manual')
            if result['status'] == 'success' and (result['model_promoted'] or _pd_model is None):
                try:
                    import joblib
                    _pd_model = joblib.load(_MODEL_PATH)
                    print(f"Model reloaded in-process after training run {result['run_id']}")
                except Exception as reload_err:
                    print(f"WARNING: Could not reload model after training: {reload_err}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return jsonify({'status': 'started', 'message': 'Training started in background. Poll /admin/api/status for completion.'}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — CHARTS
# ============================================================================

@app.route('/admin/api/charts/<run_id>/<chart_name>', methods=['GET'])
def admin_get_chart(run_id, chart_name):
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        chart_file = os.path.join(_RUNS_DIR, run_id, f'{chart_name}.b64')
        if not os.path.exists(chart_file):
            return jsonify({'error': 'Chart not found'}), 404
        with open(chart_file) as f:
            b64 = f.read()
        return jsonify({'chart': b64, 'run_id': run_id, 'name': chart_name}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/charts/<run_id>', methods=['GET'])
def admin_list_charts(run_id):
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        run_dir = os.path.join(_RUNS_DIR, run_id)
        if not os.path.exists(run_dir):
            return jsonify({'charts': []}), 200
        charts = [f.replace('.b64', '') for f in os.listdir(run_dir) if f.endswith('.b64')]
        return jsonify({'charts': sorted(charts), 'run_id': run_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — ROLLBACK
# ============================================================================

@app.route('/admin/api/rollback', methods=['POST'])
def admin_rollback():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        from ml_models.trainer import rollback_model
        import joblib
        result = rollback_model()
        _pd_model = joblib.load(_MODEL_PATH)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — SMOKE TESTS
# ============================================================================

_smoke_state = {'running': False, 'result': None}

@app.route('/admin/api/smoke-tests', methods=['POST'])
def admin_run_smoke_tests():
    if not _check_admin_auth(): return _admin_auth_error()
    if _smoke_state['running']:
        return jsonify({'status': 'already_running'}), 409

    # Capture before leaving request context
    base_url = request.host_url.rstrip('/')

    def _run():
        _smoke_state['running'] = True
        _smoke_state['result'] = None
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'testing'))
            from smoke_tests import run_smoke_tests
            _smoke_state['result'] = run_smoke_tests(base_url)
        except Exception as e:
            _smoke_state['result'] = {
                'status': 'error', 'error': str(e),
                'tests': [],
                'summary': {'total': 0, 'passed': 0, 'failed': 0, 'duration_seconds': 0}
            }
        finally:
            _smoke_state['running'] = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({'status': 'started'}), 202

@app.route('/admin/api/smoke-tests/status', methods=['GET'])
def admin_smoke_tests_status():
    if not _check_admin_auth(): return _admin_auth_error()
    return jsonify({
        'running': _smoke_state['running'],
        'result': _smoke_state['result']
    }), 200

# ============================================================================
# ADMIN — CREDIT OPS
# ============================================================================

@app.route('/admin/api/cases', methods=['GET'])
def admin_cases():
    """GET /admin/api/cases — list all persisted reports, newest first."""
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        cases = []
        if os.path.isdir(_REPORTS_DIR):
            for fname in sorted(os.listdir(_REPORTS_DIR), reverse=True):
                if not fname.endswith('.json'):
                    continue
                try:
                    path = os.path.join(_REPORTS_DIR, fname)
                    with open(path, encoding='utf-8') as fh:
                        f = json.load(fh)
                    rec = f.get('recommendation', {})
                    rat = f.get('rating', {})
                    pd_ = f.get('pd', {})
                    el_ = f.get('el', {})
                    cases.append({
                        'report_id':   f.get('report_id', fname[:-5]),
                        'borrower_id': (f.get('inputs') or {}).get('borrower_id', ''),
                        'grade':       rat.get('grade', ''),
                        'grade_label': rat.get('label', ''),
                        'pd_pct':      round((pd_.get('point') or 0) * 100, 2),
                        'decision':    rec.get('decision', ''),
                        'decision_label': rec.get('decision_label', ''),
                        'el_amount_inr':  el_.get('amount_inr', 0),
                        'timestamp':   f.get('timestamp', ''),
                        'override':    f.get('_override'),
                    })
                except Exception:
                    continue
        return jsonify({'cases': cases, 'total': len(cases)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/cases/<report_id>/override', methods=['POST'])
def admin_override(report_id):
    """POST /admin/api/cases/<report_id>/override — record a credit officer override."""
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        body = request.get_json(force=True) or {}
        new_decision  = body.get('decision', '').upper()
        justification = body.get('justification', '').strip()

        if new_decision not in ('APPROVE', 'REFER', 'DECLINE'):
            return jsonify({'error': 'decision must be APPROVE, REFER, or DECLINE'}), 400
        if len(justification) < 20:
            return jsonify({'error': 'justification must be at least 20 characters'}), 400

        findings = _report_cache.get(report_id) or _load_report(report_id)
        if findings is None:
            return jsonify({'error': f'Report {report_id} not found'}), 404

        from datetime import datetime, timezone
        override = {
            'original_decision': findings.get('recommendation', {}).get('decision'),
            'override_decision': new_decision,
            'justification':     justification,
            'timestamp':         datetime.now(timezone.utc).isoformat(),
            'actor':             'credit_officer',
        }
        findings['_override'] = override
        # Persist updated findings
        _save_report(report_id, findings)
        _report_cache[report_id] = findings
        _log_audit('OVERRIDE_RECORDED', report_id, findings,
                   actor='credit_officer', note=justification[:80])

        return jsonify({'status': 'recorded', 'override': override}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/audit-log', methods=['GET'])
def admin_audit_log():
    """GET /admin/api/audit-log — return last 100 audit events."""
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        log = []
        if os.path.exists(_AUDIT_LOG_PATH):
            with open(_AUDIT_LOG_PATH, encoding='utf-8') as fh:
                log = json.load(fh)
        limit = int(request.args.get('limit', 100))
        return jsonify({'events': log[-limit:][::-1], 'total': len(log)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SCHEDULER
# ============================================================================

_scheduler = None

def _scheduled_training():
    """Called by APScheduler — runs training and reloads model if promoted or previously unavailable."""
    global _pd_model
    try:
        from ml_models.trainer import run_training
        import joblib
        result = run_training(triggered_by='schedule')
        if result.get('model_promoted') or _pd_model is None:
            _pd_model = joblib.load(_MODEL_PATH)
    except Exception as e:
        print(f"Scheduled training error: {e}")

def _reconfigure_scheduler(schedule_cfg):
    """Add/replace the training job in APScheduler based on schedule config."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job('pd_training')
    except Exception:
        pass

    if not schedule_cfg.get('enabled', False):
        return

    freq = schedule_cfg.get('frequency', 'weekly')
    hour = int(schedule_cfg.get('hour', 2))
    minute = int(schedule_cfg.get('minute', 0))

    if freq == 'daily':
        _scheduler.add_job(_scheduled_training, 'cron',
                           hour=hour, minute=minute, id='pd_training', replace_existing=True)
    elif freq == 'weekly':
        dow = schedule_cfg.get('day_of_week', 'sun')
        # Normalize full day names to APScheduler 3-letter abbreviations
        _DOW_MAP = {'monday':'mon','tuesday':'tue','wednesday':'wed','thursday':'thu',
                    'friday':'fri','saturday':'sat','sunday':'sun'}
        dow = _DOW_MAP.get(dow.lower(), dow.lower())
        _scheduler.add_job(_scheduled_training, 'cron',
                           day_of_week=dow, hour=hour, minute=minute,
                           id='pd_training', replace_existing=True)
    elif freq == 'monthly':
        dom = int(schedule_cfg.get('day_of_month', 1))
        _scheduler.add_job(_scheduled_training, 'cron',
                           day=dom, hour=hour, minute=minute,
                           id='pd_training', replace_existing=True)

def _start_scheduler():
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    if os.path.exists(_HPARAM_PATH):
        with open(_HPARAM_PATH) as f:
            hp = json.load(f)
        _reconfigure_scheduler(hp.get('schedule', {}))
    # Daily Regulatory Reporting batch — recompute Basel III / RBI returns at 01:00.
    try:
        _scheduler.add_job(_run_regulatory_batch_job, 'cron', hour=1, minute=0,
                           id='regulatory_batch', replace_existing=True)
    except Exception as e:
        print(f'[regulatory] could not schedule daily batch: {e}')
    # Ensure today's reports exist on startup (App Engine instances are ephemeral).
    _ensure_regulatory_reports()

# NOTE: scheduler is started at the bottom of this module (after all job
# functions — including the regulatory batch — are defined). See _bootstrap.

# ============================================================================
# BANKING OPERATIONS DEPARTMENT
# ============================================================================

@app.route('/operations/')
@app.route('/operations')
def operations_home():
    return send_from_directory('public/operations', 'index.html')


@app.route('/operations/multibank')
def operations_multibank():
    return send_from_directory('public/operations', 'multibank.html')


@app.route('/operations/db-admin')
def operations_db_admin():
    """Database schema viewer — renders Jinja2 template with live schema info."""
    schema        = {}
    foreign_keys  = {}
    total_records = 0
    tables        = []
    try:
        import sqlite3 as _sa
        conn = _sa.connect(_OPS_DB_PATH)
        cur  = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            columns = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            total_records += count
            cur.execute(f"PRAGMA foreign_key_list({table})")
            fks = cur.fetchall()
            foreign_keys[table] = [{'from': fk[3], 'to_table': fk[2], 'to_col': fk[4]} for fk in fks]
            schema[table] = {
                'count': count,
                'columns': [{'name': col[1], 'type': col[2], 'notnull': col[3],
                              'default': col[4], 'pk': col[5]} for col in columns]
            }
        conn.close()
    except Exception as e:
        print(f'[ops_db_admin] error: {e}')

    def _mermaid(schema, foreign_keys):
        lines = ['erDiagram']
        seen  = set()
        for table, fks in foreign_keys.items():
            for fk in fks:
                key = tuple(sorted([table, fk['to_table']]))
                if key not in seen:
                    lines.append(f'    {table} ||--o| {fk["to_table"]} : "{fk["from"]}"')
                    seen.add(key)
        for table in sorted(schema.keys()):
            cols = schema[table]['columns']
            if cols:
                lines.append(f'    {table} {{')
                for col in cols:
                    t  = col['type'].split('(')[0].upper()[:8]
                    n  = col['name'].replace('-', '_')
                    pk = ' PK' if col['pk'] else ''
                    lines.append(f'        {t} {n}{pk}')
                lines.append('    }')
        return '\n'.join(lines)

    mermaid_diagram = _mermaid(schema, foreign_keys)
    return render_template('ops_admin.html', schema=schema, tables=sorted(tables),
                           total_records=total_records, mermaid_diagram=mermaid_diagram)


def _row_to_dict(row):
    return dict(row) if row else None

def _rows_to_list(rows):
    return [dict(r) for r in rows]

def _ops_loan_health(loans):
    statuses = [l['status'] for l in loans]
    if 'Defaulted' in statuses:
        return 'def'
    if 'NPA' in statuses:
        return 'watch'
    return 'good'


@app.route('/operations/api/banks')
def ops_list_banks():
    with _ops_conn() as conn:
        banks = _rows_to_list(conn.execute('SELECT * FROM banks').fetchall())
        for b in banks:
            bid = b['bank_id']
            b['branch_count']   = conn.execute(
                'SELECT COUNT(*) FROM branches WHERE bank_id=?', (bid,)).fetchone()[0]
            b['customer_count'] = conn.execute(
                'SELECT COUNT(*) FROM customers WHERE bank_id=?', (bid,)).fetchone()[0]
    return jsonify(banks)


@app.route('/operations/api/banks/<bank_id>')
def ops_get_bank(bank_id):
    with _ops_conn() as conn:
        b = _row_to_dict(conn.execute(
            'SELECT * FROM banks WHERE bank_id=?', (bank_id,)).fetchone())
        if b is None:
            return jsonify({'error': 'Bank not found'}), 404
        branches   = _rows_to_list(conn.execute(
            'SELECT * FROM branches WHERE bank_id=?', (bank_id,)).fetchall())
        compliance = _rows_to_list(conn.execute(
            'SELECT * FROM regulatory_compliance WHERE bank_id=?', (bank_id,)).fetchall())
        reqs = []
        for c in compliance:
            req = _row_to_dict(conn.execute(
                'SELECT * FROM regulatory_requirements WHERE requirement_id=?',
                (c['requirement_id'],)).fetchone())
            if req:
                reqs.append({'requirement': req,
                             'compliance_status': c['compliance_status'],
                             'last_audit_date': c['last_audit_date']})
    return jsonify({'bank': b, 'branches': branches, 'compliance': reqs})


@app.route('/operations/api/banks/<bank_id>/customers')
def ops_get_bank_customers(bank_id):
    with _ops_conn() as conn:
        if not conn.execute('SELECT 1 FROM banks WHERE bank_id=?', (bank_id,)).fetchone():
            return jsonify({'error': 'Bank not found'}), 404
        customers = _rows_to_list(conn.execute(
            'SELECT id, first, last, city, bank_id FROM customers WHERE bank_id=?',
            (bank_id,)).fetchall())
        loans = _rows_to_list(conn.execute(
            'SELECT cid, status FROM loans WHERE bank_id=?', (bank_id,)).fetchall())
    loan_map = {}
    for l in loans:
        loan_map.setdefault(l['cid'], []).append(l)
    for c in customers:
        c['health'] = _ops_loan_health(loan_map.get(c['id'], []))
    return jsonify(customers)


@app.route('/operations/api/banks/<bank_id>/dashboard')
def ops_bank_dashboard(bank_id):
    with _ops_conn() as conn:
        b = _row_to_dict(conn.execute(
            'SELECT * FROM banks WHERE bank_id=?', (bank_id,)).fetchone())
        if b is None:
            return jsonify({'error': 'Bank not found'}), 404
        customers    = _rows_to_list(conn.execute(
            'SELECT * FROM customers WHERE bank_id=?', (bank_id,)).fetchall())
        accounts     = _rows_to_list(conn.execute(
            'SELECT * FROM accounts WHERE bank_id=?', (bank_id,)).fetchall())
        loans        = _rows_to_list(conn.execute(
            'SELECT * FROM loans WHERE bank_id=?', (bank_id,)).fetchall())
        transactions = _rows_to_list(conn.execute(
            'SELECT * FROM transactions WHERE bank_id=?', (bank_id,)).fetchall())
    return jsonify(_ops_build_payload(b, customers, accounts, loans, transactions))


@app.route('/operations/api/customers')
def ops_list_customers():
    with _ops_conn() as conn:
        customers = _rows_to_list(conn.execute(
            'SELECT id, first, last, city, bank_id FROM customers').fetchall())
        loans = _rows_to_list(conn.execute(
            'SELECT cid, status FROM loans').fetchall())
    loan_map = {}
    for l in loans:
        loan_map.setdefault(l['cid'], []).append(l)
    for c in customers:
        c['health'] = _ops_loan_health(loan_map.get(c['id'], []))
    return jsonify(customers)


@app.route('/operations/api/customers/<cid>')
def ops_get_customer(cid):
    with _ops_conn() as conn:
        c = _row_to_dict(conn.execute(
            'SELECT * FROM customers WHERE id=?', (cid,)).fetchone())
        if c is None:
            return jsonify({'error': 'Customer not found'}), 404
        accounts     = _rows_to_list(conn.execute(
            'SELECT * FROM accounts WHERE cid=?', (cid,)).fetchall())
        loans        = _rows_to_list(conn.execute(
            'SELECT * FROM loans WHERE cid=?', (cid,)).fetchall())
        acc_ids      = [a['id'] for a in accounts]
        transactions = []
        if acc_ids:
            placeholders = ','.join('?' * len(acc_ids))
            transactions = _rows_to_list(conn.execute(
                f'SELECT * FROM transactions WHERE aid IN ({placeholders})'
                ' ORDER BY date DESC, time DESC', acc_ids).fetchall())
        loan_ids     = [l['id'] for l in loans]
        risk_metrics = []
        if loan_ids:
            placeholders = ','.join('?' * len(loan_ids))
            risk_metrics = _rows_to_list(conn.execute(
                f'SELECT * FROM credit_risk_metrics WHERE lid IN ({placeholders})',
                loan_ids).fetchall())
    c['health'] = _ops_loan_health(loans)
    return jsonify({'customer': c, 'accounts': accounts, 'loans': loans,
                    'transactions': transactions, 'risk': risk_metrics})


@app.route('/operations/api/system-dashboard')
def ops_system_dashboard():
    with _ops_conn() as conn:
        banks        = _rows_to_list(conn.execute('SELECT * FROM banks').fetchall())
        customers    = _rows_to_list(conn.execute('SELECT * FROM customers').fetchall())
        accounts     = _rows_to_list(conn.execute('SELECT * FROM accounts').fetchall())
        loans        = _rows_to_list(conn.execute('SELECT * FROM loans').fetchall())
        transactions = _rows_to_list(conn.execute('SELECT * FROM transactions').fetchall())
    bank_summary = []
    for b in banks:
        bid = b['bank_id']
        b_accs = [a for a in accounts if a['bank_id'] == bid]
        bank_summary.append({
            'bank_id':   bid,
            'bank_name': b['bank_name'],
            'customers': sum(1 for c in customers if c['bank_id'] == bid),
            'accounts':  len(b_accs),
            'deposits':  sum(a['balance'] for a in b_accs),
        })
    payload = _ops_build_payload(None, customers, accounts, loans, transactions)
    payload['title'] = 'India Banking System — All Banks Combined'
    payload['banks'] = bank_summary
    return jsonify(payload)


def _ops_build_payload(bank_dict, customers, accounts, loans, transactions):
    loan_map = {}
    for l in loans:
        loan_map.setdefault(l['cid'], []).append(l)

    total_deposits    = sum(a['balance'] for a in accounts)
    total_outstanding = sum(l['outstanding'] for l in loans)
    total_txn_vol     = sum(t['amount'] for t in transactions)
    active_loans      = sum(1 for l in loans if l['status'] == 'Active')
    stressed_loans    = sum(1 for l in loans if l['status'] in ('Defaulted', 'NPA'))

    health_dist = {'good': 0, 'watch': 0, 'def': 0}
    for c in customers:
        h = _ops_loan_health(loan_map.get(c['id'], []))
        health_dist[h] += 1

    hour_buckets = [0] * 24
    for t in transactions:
        try:
            h = int(str(t.get('time') or '0').split(':')[0])
            if 0 <= h < 24:
                hour_buckets[h] += 1
        except (ValueError, AttributeError):
            pass

    by_type = {}
    by_date = {}
    for t in transactions:
        by_type[t['type']] = by_type.get(t['type'], 0) + t['amount']
        d = str(t.get('date') or 'Unknown')
        if d not in by_date:
            by_date[d] = {'count': 0, 'volume': 0}
        by_date[d]['count']  += 1
        by_date[d]['volume'] += t['amount']

    loan_by_status = {}
    acc_by_type    = {}
    for l in loans:
        loan_by_status[l['status']] = loan_by_status.get(l['status'], 0) + l['outstanding']
    for a in accounts:
        acc_by_type[a['type']] = acc_by_type.get(a['type'], 0) + a['balance']

    total_out = total_outstanding or 1
    loan_book = [{'id': l['id'], 'cid': l['cid'], 'type': l['type'],
                  'status': l['status'], 'outstanding': l['outstanding'],
                  'pct': round((l['outstanding'] / total_out) * 100, 1)} for l in loans]

    txn_log = sorted(transactions,
                     key=lambda x: (str(x.get('date') or ''), str(x.get('time') or '')),
                     reverse=True)

    payload = {
        'kpis': {
            'customers':        len(customers),
            'accounts':         len(accounts),
            'totalDeposits':    total_deposits,
            'totalOutstanding': total_outstanding,
            'totalTxns':        len(transactions),
            'totalTxnVol':      total_txn_vol,
            'activeLoans':      active_loans,
            'stressedLoans':    stressed_loans,
        },
        'health':       health_dist,
        'txnByHour':    hour_buckets,
        'txnByType':    by_type,
        'txnByDate':    by_date,
        'loanByStatus': loan_by_status,
        'accByType':    acc_by_type,
        'loanBook':     loan_book,
        'txnLog':       txn_log,
    }
    if bank_dict:
        payload['bank'] = bank_dict
    return payload

# ============================================================================
# REGULATORY REPORTING DEPARTMENT
# Basel III / RBI capital, liquidity & client-exposure returns, read from the
# reg_* tables produced by the daily batch (operations/scripts/run_regulatory_batch.py).
# ============================================================================
from backend.regulatory_engine import RBI_THRESHOLDS as _RBI_THRESHOLDS


@app.route('/regulatory/')
@app.route('/regulatory')
def regulatory_home():
    return send_from_directory('public/regulatory', 'index.html')


def _reg_tables_exist(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='reg_capital_reports'"
    ).fetchone()
    return row is not None


def _reg_latest_date(conn):
    if not _reg_tables_exist(conn):
        return None
    row = conn.execute("SELECT MAX(report_date) FROM reg_capital_reports").fetchone()
    return row[0] if row else None


@app.route('/regulatory/api/system')
def reg_system():
    """System-wide (all-banks) regulatory snapshot for the latest report date."""
    with _ops_conn() as conn:
        d = _reg_latest_date(conn)
        if not d:
            return jsonify({'available': False,
                            'message': 'No regulatory reports yet — run the batch.'})
        caps = _rows_to_list(conn.execute(
            "SELECT * FROM reg_capital_reports WHERE report_date=?", (d,)).fetchall())
        liqs = {r['bank_id']: dict(r) for r in conn.execute(
            "SELECT * FROM reg_liquidity_reports WHERE report_date=?", (d,)).fetchall()}
        banks = {b['bank_id']: dict(b) for b in conn.execute("SELECT * FROM banks").fetchall()}
        dates = [r[0] for r in conn.execute(
            "SELECT DISTINCT report_date FROM reg_capital_reports ORDER BY report_date").fetchall()]

    agg = lambda key: sum(c[key] for c in caps)
    tot_rwa     = agg('total_rwa')      or 1.0
    tot_assets  = agg('total_assets')   or 1.0
    tot_cap     = agg('total_capital')
    tot_t1      = agg('tier1_capital')
    tot_hqla    = sum(l['hqla'] for l in liqs.values())
    tot_out     = sum(l['net_outflows_30d'] for l in liqs.values()) or 1.0
    tot_asf     = sum(l['asf'] for l in liqs.values())
    tot_rsf     = sum(l['rsf'] for l in liqs.values()) or 1.0

    bank_rows = []
    breaches = watches = 0
    for c in caps:
        l = liqs.get(c['bank_id'], {})
        for st in (c['car_status'], l.get('lcr_status'), l.get('nsfr_status'), c['cet1_status']):
            if st == 'Breach':
                breaches += 1
            elif st == 'Watch':
                watches += 1
        bank_rows.append({
            'bank_id': c['bank_id'],
            'bank_name': banks.get(c['bank_id'], {}).get('bank_name', c['bank_id']),
            'car': c['car'], 'car_status': c['car_status'],
            'cet1_ratio': c['cet1_ratio'], 'tier1_ratio': c['tier1_ratio'],
            'leverage_ratio': c['leverage_ratio'],
            'lcr': l.get('lcr'), 'lcr_status': l.get('lcr_status'),
            'nsfr': l.get('nsfr'), 'nsfr_status': l.get('nsfr_status'),
            'crr_ratio': l.get('crr_ratio'), 'slr_ratio': l.get('slr_ratio'),
            'total_rwa': c['total_rwa'], 'loan_book': c['loan_book'],
            'deposits': c['deposits'], 'num_loans': c['num_loans'], 'num_npa': c['num_npa'],
            'total_provisions': c['total_provisions'],
        })

    return jsonify({
        'available': True,
        'report_date': d,
        'history_dates': dates,
        'thresholds': _RBI_THRESHOLDS,
        'system': {
            'total_rwa': round(tot_rwa, 2),
            'credit_rwa': round(agg('credit_rwa'), 2),
            'operational_rwa': round(agg('operational_rwa'), 2),
            'total_capital': round(tot_cap, 2),
            'tier1_capital': round(tot_t1, 2),
            'total_assets': round(tot_assets, 2),
            'loan_book': round(agg('loan_book'), 2),
            'deposits': round(agg('deposits'), 2),
            'total_provisions': round(agg('total_provisions'), 2),
            'num_loans': agg('num_loans'),
            'num_npa': agg('num_npa'),
            'car': round(tot_cap / tot_rwa * 100, 2),
            'cet1_ratio': round(tot_t1 / tot_rwa * 100, 2),
            'leverage_ratio': round(tot_t1 / tot_assets * 100, 2),
            'lcr': round(tot_hqla / tot_out * 100, 2),
            'nsfr': round(tot_asf / tot_rsf * 100, 2),
            'hqla': round(tot_hqla, 2),
            'num_banks': len(caps),
            'breaches': breaches,
            'watches': watches,
        },
        'banks': bank_rows,
    })


@app.route('/regulatory/api/banks/<bank_id>')
def reg_bank(bank_id):
    """Full capital + liquidity + compliance + trend for one bank."""
    with _ops_conn() as conn:
        d = _reg_latest_date(conn)
        if not d:
            return jsonify({'available': False,
                            'message': 'No regulatory reports yet — run the batch.'})
        cap = _row_to_dict(conn.execute(
            "SELECT * FROM reg_capital_reports WHERE bank_id=? AND report_date=?",
            (bank_id, d)).fetchone())
        if cap is None:
            return jsonify({'error': 'No report for this bank'}), 404
        liq = _row_to_dict(conn.execute(
            "SELECT * FROM reg_liquidity_reports WHERE bank_id=? AND report_date=?",
            (bank_id, d)).fetchone())
        bank = _row_to_dict(conn.execute(
            "SELECT * FROM banks WHERE bank_id=?", (bank_id,)).fetchone())
        compliance = []
        for c in conn.execute(
                "SELECT * FROM regulatory_compliance WHERE bank_id=?", (bank_id,)).fetchall():
            req = _row_to_dict(conn.execute(
                "SELECT * FROM regulatory_requirements WHERE requirement_id=?",
                (c['requirement_id'],)).fetchone())
            compliance.append({'compliance': dict(c), 'requirement': req})
        # exposure mix by loan type + classification
        mix = _rows_to_list(conn.execute(
            "SELECT loan_type, classification, COUNT(*) n, SUM(rwa) rwa, SUM(ead) ead, "
            "SUM(provision) provision FROM reg_client_exposures "
            "WHERE bank_id=? AND report_date=? GROUP BY loan_type, classification",
            (bank_id, d)).fetchall())
        # trend across dates
        trend = _rows_to_list(conn.execute(
            "SELECT cr.report_date, cr.car, cr.cet1_ratio, lr.lcr, lr.nsfr "
            "FROM reg_capital_reports cr LEFT JOIN reg_liquidity_reports lr "
            "ON cr.bank_id=lr.bank_id AND cr.report_date=lr.report_date "
            "WHERE cr.bank_id=? ORDER BY cr.report_date", (bank_id,)).fetchall())

    for r in (cap, liq):
        if r and r.get('detail'):
            try:
                r['assumptions'] = json.loads(r['detail'])
            except Exception:
                pass
    return jsonify({'available': True, 'report_date': d, 'thresholds': _RBI_THRESHOLDS,
                    'bank': bank, 'capital': cap, 'liquidity': liq,
                    'compliance': compliance, 'exposure_mix': mix, 'trend': trend})


@app.route('/regulatory/api/banks/<bank_id>/exposures')
def reg_bank_exposures(bank_id):
    """Client-level exposure register for one bank (latest report date)."""
    with _ops_conn() as conn:
        d = _reg_latest_date(conn)
        if not d:
            return jsonify({'available': False, 'exposures': []})
        rows = _rows_to_list(conn.execute(
            "SELECT * FROM reg_client_exposures WHERE bank_id=? AND report_date=? "
            "ORDER BY rwa DESC", (bank_id, d)).fetchall())
    return jsonify({'available': True, 'report_date': d, 'bank_id': bank_id, 'exposures': rows})


@app.route('/regulatory/api/clients/<cid>')
def reg_client(cid):
    """Client-level regulatory report — exposures + RWA/provision contribution."""
    with _ops_conn() as conn:
        d = _reg_latest_date(conn)
        cust = _row_to_dict(conn.execute(
            "SELECT * FROM customers WHERE id=?", (cid,)).fetchone())
        if cust is None:
            return jsonify({'error': 'Customer not found'}), 404
        bank = _row_to_dict(conn.execute(
            "SELECT * FROM banks WHERE bank_id=?", (cust['bank_id'],)).fetchone())
        exposures = []
        if d:
            exposures = _rows_to_list(conn.execute(
                "SELECT * FROM reg_client_exposures WHERE cid=? AND report_date=? "
                "ORDER BY rwa DESC", (cid, d)).fetchall())
    totals = {
        'ead': round(sum(e['ead'] for e in exposures), 2),
        'rwa': round(sum(e['rwa'] for e in exposures), 2),
        'capital_charge': round(sum(e['capital_charge'] for e in exposures), 2),
        'expected_loss': round(sum(e['expected_loss'] for e in exposures), 2),
        'provision': round(sum(e['provision'] for e in exposures), 2),
        'num_loans': len(exposures),
        'num_npa': sum(1 for e in exposures if e['classification'] not in ('Standard', 'Performing')),
    }
    return jsonify({'available': bool(d), 'report_date': d, 'thresholds': _RBI_THRESHOLDS,
                    'customer': cust, 'bank': bank, 'exposures': exposures, 'totals': totals})


@app.route('/regulatory/api/run-batch', methods=['POST'])
def reg_run_batch():
    """Manually trigger the regulatory batch (also runs daily via APScheduler)."""
    try:
        from operations.scripts.run_regulatory_batch import run_batch
        results = run_batch(verbose=False)
        return jsonify({'success': True, 'banks_processed': len(results),
                        'report_date': __import__('datetime').date.today().isoformat()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _run_regulatory_batch_job():
    """APScheduler entry point for the daily regulatory batch."""
    try:
        from operations.scripts.run_regulatory_batch import run_batch
        run_batch(verbose=False)
        print('[regulatory] daily batch completed')
    except Exception as e:
        print(f'[regulatory] batch error: {e}')


def _ensure_regulatory_reports():
    """Run the batch once at startup if today's reports are missing (GCP is ephemeral)."""
    try:
        with _ops_conn() as conn:
            if _reg_latest_date(conn) == __import__('datetime').date.today().isoformat():
                return
        _run_regulatory_batch_job()
    except Exception as e:
        print(f'[regulatory] startup batch skipped: {e}')

# ============================================================================
# RELATIONSHIP MANAGEMENT & DECISION SUPPORT DEPARTMENT
# Front-line RM workflow that sits between the customer and the automated
# decisioning core: machine recommendation (M) + human judgment (H) +
# organisational decision (O), joined by a hash-chained provenance ledger.
# Reuses _assessment_engine (model) + backend.policy_engine + decision_orchestrator.
# ============================================================================
from backend import rm_case_store as _rm
from backend.decision_orchestrator import orchestrate as _orchestrate

_rm_schema_ready = False

def _rm_conn():
    """bank.db connection with the RM case-ledger schema ensured once."""
    global _rm_schema_ready
    conn = _ops_conn()
    if not _rm_schema_ready:
        _rm.init_schema(conn)
        _rm_schema_ready = True
    return conn


@app.route('/relationship/')
@app.route('/relationship')
def relationship_home():
    return send_from_directory('public/relationship', 'index.html')


@app.route('/relationship/api/cases', methods=['GET', 'POST'])
def rm_cases():
    if request.method == 'POST':
        application = request.get_json(force=True) or {}
        rm_id = application.pop('rm_id', 'RM-DEMO')
        try:
            M = _orchestrate(application, _assessment_engine)
        except Exception as e:
            return jsonify({'error': f'Assessment failed: {e}'}), 500
        with _rm_conn() as conn:
            case_id = _rm.create_case(conn, M, rm_id=rm_id)
        return jsonify({'success': True, 'case_id': case_id,
                        'recommendation': M['composed'], 'routing': M['routing']}), 201
    # GET — queue list
    with _rm_conn() as conn:
        cases = _rm.list_cases(conn, state=request.args.get('state'),
                               control=request.args.get('control'))
    return jsonify({'cases': cases})


@app.route('/relationship/api/cases/<case_id>')
def rm_get_case(case_id):
    with _rm_conn() as conn:
        c = _rm.get_case(conn, case_id)
    if not c:
        return jsonify({'error': 'Case not found'}), 404
    return jsonify(c)


@app.route('/relationship/api/cases/<case_id>/action', methods=['POST'])
def rm_case_action(case_id):
    """RM action: accept | reject. The RM is the final authority; each action
    finalises the case (reject requires a >=20-char rationale)."""
    body = request.get_json(force=True) or {}
    with _rm_conn() as conn:
        result, code = _rm.rm_action(
            conn, case_id,
            action=body.get('action'),
            actor_id=body.get('actor_id', 'RM-DEMO'),
            rationale_code=body.get('rationale_code'),
            rationale_text=body.get('rationale_text'),
            modified_recommendation=body.get('modified_recommendation'),
            extra=body)
    return jsonify(result), code


@app.route('/relationship/api/cases/<case_id>/approve', methods=['POST'])
def rm_case_approve(case_id):
    """Four-eyes / committee: approve | return an RM proposal."""
    body = request.get_json(force=True) or {}
    with _rm_conn() as conn:
        result, code = _rm.four_eyes(
            conn, case_id, decision=body.get('decision'),
            actor_id=body.get('actor_id', 'CO-DEMO'),
            rationale_text=body.get('rationale_text'))
    return jsonify(result), code


@app.route('/relationship/api/cases/<case_id>/outcome', methods=['POST'])
def rm_case_outcome(case_id):
    """Record post-decision performance (closes the human-in-the-loop learning loop)."""
    body = request.get_json(force=True) or {}
    with _rm_conn() as conn:
        result, code = _rm.record_outcome(
            conn, case_id,
            performance_status=body.get('performance_status', 'performing'),
            booked=body.get('booked', True),
            dpd=int(body.get('dpd', 0) or 0),
            default_flag=int(body.get('default_flag', 0) or 0),
            notes=body.get('notes'))
    return jsonify(result), code


@app.route('/relationship/api/insights')
def rm_insights():
    with _rm_conn() as conn:
        return jsonify(_rm.insights(conn))


# ── PDF case reports (LaTeX → PDF, versioned per borrower) ───────────────────
from backend import report_generator as _reportgen
from flask import send_file as _send_file


@app.route('/relationship/api/cases/<case_id>/report', methods=['POST'])
def rm_generate_report(case_id):
    """Generate a NEW PDF report version for a case (regeneration keeps history)."""
    with _rm_conn() as conn:
        case = _rm.get_case(conn, case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    try:
        meta = _reportgen.generate_report(case)
    except Exception as e:
        return jsonify({'error': f'Report generation failed: {e}'}), 500
    code = 201 if meta.get('pdf_exists') else 500
    return jsonify({'success': meta.get('pdf_exists', False),
                    'report': meta,
                    'versions': _reportgen.list_versions(case_id)}), code


@app.route('/relationship/api/cases/<case_id>/reports', methods=['GET'])
def rm_list_reports(case_id):
    """List all past report versions (newest first) for a case."""
    return jsonify({'case_id': case_id,
                    'latex_available': _reportgen.latex_available(),
                    'versions': _reportgen.list_versions(case_id)})


@app.route('/relationship/api/reports/<case_id>/<version>/pdf', methods=['GET'])
def rm_report_pdf(case_id, version):
    """Serve a report PDF inline (open) or as an attachment (?dl=1 to download)."""
    path = _reportgen.pdf_path(case_id, version)
    if not path:
        return jsonify({'error': 'PDF not found'}), 404
    download = request.args.get('dl') in ('1', 'true', 'yes')
    return _send_file(path, mimetype='application/pdf', as_attachment=download,
                      download_name=f'{case_id}_{version}.pdf')


# Start scheduler only in the main process (not the Flask reloader watcher).
# Placed here, after all scheduled-job functions are defined.
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    _start_scheduler()

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
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
