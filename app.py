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
CORS(app, resources={r"/api/*": {"origins": "*"}})

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

        # Create breakdown based on feature importance (estimated from RF model)
        # This provides transparency for the ML-based PD calculation
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

@app.route('/admin/api/generate-synthetic', methods=['POST'])
def admin_generate_synthetic():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        from ml_models.synthetic_data import generate_all
        results = generate_all(copy_to_training=True)
        return jsonify({'status': 'success', 'files_generated': len(results),
                        'banks': list(results.keys())}), 200
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
            if result['status'] == 'success' and result['model_promoted']:
                import joblib
                _pd_model = joblib.load(_MODEL_PATH)

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
    """Called by APScheduler — runs training and reloads model if promoted."""
    try:
        from ml_models.trainer import run_training
        import joblib
        result = run_training(triggered_by='schedule')
        if result.get('model_promoted'):
            global _pd_model
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

# Start scheduler only in the main process (not Flask reloader watcher)
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
