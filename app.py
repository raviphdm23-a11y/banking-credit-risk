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

# ── Simulation clock (frozen for the Axis Bank experiment) ───────────────────
# Single source of truth is simulation_clock.json in the repo root.
# Advance by editing that file and re-running the seeders + regulatory batch.
def _load_sim_clock():
    import json as _json
    _clk = os.path.join(os.path.dirname(__file__), 'simulation_clock.json')
    try:
        with open(_clk) as _f:
            return _json.load(_f)
    except Exception:
        return {'sim_date': '2020-03-31', 'sim_period': 'FY2020'}

_SIM_CLOCK = _load_sim_clock()
SIM_DATE   = _SIM_CLOCK['sim_date']
SIM_PERIOD = _SIM_CLOCK.get('sim_period', 'FY2020')

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
from backend.feature_meta import model_feature_frame

def _get_model_version():
    try:
        meta_path = os.path.join(os.path.dirname(__file__), 'ml_models', 'pd_model_metadata.json')
        with open(meta_path) as f:
            return json.load(f).get('version', 'unknown')
    except Exception:
        return 'unknown'

_assessment_engine = _AssessmentEngine(_pd_model, _get_model_version(), db_path=_OPS_DB_PATH)

# In-memory report cache keyed by report_id (uuid).
_report_cache: dict = {}

# ── File-based persistence paths ───────────────────────────────────────────
# On GCP App Engine, /workspace is read-only, so use /tmp for ephemeral data
_ON_GAE = os.environ.get('GAE_APPLICATION') is not None
_BASE_DATA_DIR = '/tmp/data' if _ON_GAE else os.path.join(os.path.dirname(__file__), 'data')
_REPORTS_DIR   = os.path.join(_BASE_DATA_DIR, 'reports')
_AUDIT_LOG_PATH = os.path.join(_BASE_DATA_DIR, 'audit_log.json')
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

def _load_report(report_id: str):
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

        # Build feature frame aligned to the model's expected schema.
        # Missing values default to population medians (feature_meta.py).
        df_features = model_feature_frame(data, _pd_model)
        features = df_features.values

        # Use predict_proba to get probability of default (class 1)
        pd_decimal = float(_pd_model.predict_proba(features)[0][1])
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

    TIER 1: Feature importance ranking, uncertainty-aware knockouts, learned thresholds.
    TIER 2: SHAP values (feature interactions) - see /api/assess-borrower-with-shap.

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


@app.route('/api/assess-borrower-with-shap', methods=['POST'])
def assess_borrower_with_shap():
    """
    POST /api/assess-borrower-with-shap

    TIER 2: Full assessment with SHAP values and feature interactions.

    Identical to /api/assess-borrower, but includes SHAP analysis:
    - base_value: Model's baseline PD
    - feature_contributions: SHAP value per feature (proper additive attribution)
    - interactions: Top 3 feature interactions (amplifying/mitigating)
    - summary: One-line executive summary

    Performance:
    - First call (cold): ~100-150ms (SHAP computation)
    - Cached call: ~2-5ms (cache hit)
    - Budget: <150ms per request

    Request body: Same as /api/assess-borrower

    Response: Same as /api/assess-borrower + "shap" field

    Example response excerpt:
        {
            "shap": {
                "base_value": 0.0253,
                "feature_contributions": [
                    {
                        "feature": "de_ratio",
                        "shap_value": 0.0286,
                        "feature_value": 2.5,
                        "direction": "increases_pd"
                    },
                    ...
                ],
                "interactions": [
                    {
                        "feature_pair": ["de_ratio", "interest_coverage"],
                        "interaction_strength": 0.0152,
                        "type": "amplifying",
                        "explanation": "D/E & IC together amplify risk"
                    }
                ],
                "summary": "Top drivers: de_ratio, interest_coverage, profitability. Key interaction: de_ratio × interest_coverage (amplifying).",
                "model_version": "run_20260702_045113",
                "computed_at": "2026-07-03T10:30:00Z",
                "cached": false
            }
        }
    """
    try:
        data = request.get_json(force=True) or {}
        findings = _assessment_engine.assess(data)
        # SHAP is automatically included in findings if explainer available
        return jsonify(findings), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/masterscale', methods=['GET'])
def masterscale():
    """GET /api/masterscale — return the internal rating grade table."""
    from backend.rating_masterscale import masterscale_table
    return jsonify({'grades': masterscale_table()}), 200


@app.route('/api/exposure-classes', methods=['GET'])
def exposure_classes():
    """GET /api/exposure-classes — Basel III.1 SA exposure class reference.

    Returns the 14 exposure classes from ref_lookup (domain='exposure_class')
    enriched with the default risk weight from regulatory_engine.EXPOSURE_CLASS_RW.
    Used by the calculator UI for the exposure class dropdown.
    """
    from backend.regulatory_engine import EXPOSURE_CLASS_RW
    try:
        conn = _ops_conn()
        rows = conn.execute(
            "SELECT code, label, description, risk_order "
            "FROM ref_lookup WHERE domain='exposure_class' ORDER BY risk_order"
        ).fetchall()
        conn.close()
        classes = []
        for r in rows:
            code = r['code']
            classes.append({
                'code':        code,
                'label':       r['label'],
                'description': r['description'],
                'risk_order':  r['risk_order'],
                'default_rw':  EXPOSURE_CLASS_RW.get(code, 1.0),
                'default_rw_pct': round(EXPOSURE_CLASS_RW.get(code, 1.0) * 100, 1),
            })
        return jsonify({'exposure_classes': classes, 'count': len(classes)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
                    _assessment_engine.__init__(_pd_model, _get_model_version(), db_path=_OPS_DB_PATH)
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
        _assessment_engine.__init__(_pd_model, _get_model_version(), db_path=_OPS_DB_PATH)
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
            _assessment_engine.__init__(_pd_model, _get_model_version(), db_path=_OPS_DB_PATH)
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
    # Daily NPA Classification batch — DPD-based loan reclassification at 02:00.
    try:
        _scheduler.add_job(_run_npa_batch_job, 'cron', hour=2, minute=0,
                           id='npa_batch', replace_existing=True)
    except Exception as e:
        print(f'[npa-batch] could not schedule daily batch: {e}')
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


# ── Customer lookup for the Credit Risk data-collection page ───────────────────
# Given a customer id typed into the calculator, see if the person already banks
# with ANY group bank. If so, return their KYC mapped onto the calculator's input
# encodings + bank/country + an existing-relationship summary (accounts, loans,
# transaction-history-derived variables) so the analyst need not re-key.
_EMP_MAP = {'GOVERNMENT': 1, 'GOVT': 1, 'SALARIED': 2, 'PRIVATE': 2, 'SELF_EMPLOYED': 3,
            'SELF-EMPLOYED': 3, 'PROFESSIONAL': 3, 'BUSINESS': 4, 'BUSINESS_OWNER': 4,
            'FREELANCE': 5, 'FREELANCER': 5, 'CONTRACT': 5, 'RETIRED': 6,
            'STUDENT': 7, 'UNEMPLOYED': 7}
_EDU_MAP = {'BELOW_10TH': 1, 'PRIMARY': 1, 'SECONDARY': 2, '10TH': 2, 'HIGHER_SECONDARY': 3,
            '12TH': 3, 'DIPLOMA': 3, 'GRADUATE': 4, 'UNDER_GRADUATE': 4, 'POST_GRADUATE': 5,
            'POSTGRADUATE': 5, 'DOCTORATE': 6, 'PHD': 6}
_TIER_MAP = {'TIER1': 1, 'TIER_1': 1, 'TIER2': 2, 'TIER_2': 2, 'TIER3': 3, 'TIER_3': 3}
_RES_MAP = {'OWNED': 1, 'OWN': 1, 'RENTED': 2, 'RENT': 2, 'COMPANY_PROVIDED': 3, 'COMPANY': 3,
            'PARENTS': 4, 'FAMILY': 4, 'WITH_PARENTS': 4}
_PURP_MAP = {'HOME_PURCHASE': 1, 'HOME': 1, 'HOME_RENOVATION': 2, 'RENOVATION': 2, 'CAR': 3,
             'VEHICLE': 3, 'AUTO': 3, 'PERSONAL': 4, 'BUSINESS': 5, 'BUSINESS_EXPANSION': 5,
             'EDUCATION': 6, 'MEDICAL': 7, 'MEDICAL_EMERGENCY': 7}
_SECTOR_MAP = {'IT': 'Technology', 'TECHNOLOGY': 'Technology', 'MANUFACTURING': 'Manufacturing',
               'RETAIL': 'Retail', 'FINANCIAL': 'Financial', 'BANKING': 'Financial',
               'REAL_ESTATE': 'Real Estate', 'HEALTHCARE': 'Healthcare', 'HEALTH': 'Healthcare',
               'ENERGY': 'Energy', 'GOVERNMENT': 'Government', 'UTILITIES': 'Utilities'}
_CREDIT_TYPES = {'DEPOSIT', 'SALARY', 'INTEREST', 'REFUND', 'CREDIT'}


def _emap(table, key, default=''):
    if key is None:
        return default
    return table.get(str(key).upper().replace(' ', '_').replace('-', '_'), default)


@app.route('/api/customer-lookup/<cid>')
def api_customer_lookup(cid):
    cid = (cid or '').strip()
    with _ops_conn() as conn:
        cust = _row_to_dict(conn.execute(
            'SELECT * FROM customers WHERE id=?', (cid,)).fetchone())
        if not cust:
            return jsonify({'found': False})
        bank = _row_to_dict(conn.execute(
            'SELECT * FROM banks WHERE bank_id=?', (cust['bank_id'],)).fetchone()) or {}
        kyc = _row_to_dict(conn.execute(
            'SELECT * FROM customer_kyc WHERE cid=?', (cid,)).fetchone()) or {}
        accounts = _rows_to_list(conn.execute(
            'SELECT * FROM accounts WHERE cid=?', (cid,)).fetchall())
        loans = _rows_to_list(conn.execute(
            'SELECT * FROM loans WHERE cid=?', (cid,)).fetchall())
        acc_ids = [a['id'] for a in accounts]
        txns = []
        if acc_ids:
            ph = ','.join('?' * len(acc_ids))
            txns = _rows_to_list(conn.execute(
                f'SELECT type, amount, date, desc FROM transactions WHERE aid IN ({ph})',
                acc_ids).fetchall())

    # ── transaction-history-derived variables ──
    months = sorted({(t['date'] or '')[:7] for t in txns if t.get('date')})
    n_months = max(1, len(months))
    inflow = outflow = 0.0
    n_income = n_emi = 0
    for t in txns:
        typ = (t.get('type') or '').upper()
        desc = (t.get('desc') or '').upper()
        amt = float(t.get('amount') or 0)
        is_credit = typ in _CREDIT_TYPES or desc.startswith('[INCOME]')
        if is_credit:
            inflow += amt
            n_income += 1
        else:
            outflow += amt
            if typ == 'EMI PAYMENT' or 'EMI' in desc:
                n_emi += 1
    total_emi = sum(float(l.get('emi') or 0) for l in loans if (l.get('status') == 'Active' or l.get('loan_classification')))
    # expected EMIs = months elapsed since each loan's disbursement (capped at its tenure),
    # so "missed" only counts months the loan was actually live — not the whole history.
    from datetime import date as _date
    def _months_since(dstr):
        try:
            y, m = int(dstr[:4]), int(dstr[5:7])
            t = _date.today()
            return max(0, (t.year - y) * 12 + (t.month - m))
        except Exception:
            return 0
    expected_emi = 0
    for l in loans:
        if float(l.get('emi') or 0) > 0:
            tenure = int(l.get('tenure') or 0)
            elapsed = _months_since(l.get('disbursed') or '')
            expected_emi += min(elapsed, tenure) if tenure else elapsed
    txn_vars = {
        'months_observed': len(months),
        'num_transactions': len(txns),
        'avg_monthly_inflow': round(inflow / n_months, 0),
        'avg_monthly_outflow': round(outflow / n_months, 0),
        'net_monthly_surplus': round((inflow - outflow) / n_months, 0),
        'num_income_credits': n_income,
        'num_emi_debits': n_emi,
        'expected_emi': expected_emi,
        'num_missed_emi': max(0, expected_emi - n_emi),
        'current_balance': round(sum(float(a.get('balance') or 0) for a in accounts), 0),
        'last_txn_date': months[-1] if months else None,
    }

    income = float(kyc.get('annual_income') or 0) + float(kyc.get('other_income') or 0)
    # the 4 explainable ratios come from the customer's loan risk metrics (latest)
    ratios = {}
    if loans:
        with _ops_conn() as conn:
            lid = loans[0]['id']
            m = _row_to_dict(conn.execute(
                'SELECT * FROM credit_risk_metrics WHERE lid=? ORDER BY obs DESC LIMIT 1',
                (lid,)).fetchone())
        if m:
            ratios = {'debtToEquity': m.get('de'), 'interestCoverage': m.get('intcov'),
                      'profitabilityMargin': m.get('profit'), 'liquidityRatio': m.get('liq')}

    fields = {
        'borrowerName': f"{cust.get('first', '')} {cust.get('last', '')}".strip(),
        'sector': _emap(_SECTOR_MAP, kyc.get('industry_sector'), ''),
        'exposureAmount': round(sum(float(l.get('outstanding') or 0) for l in loans), 0) or '',
        'kycAge': kyc.get('age'),
        'kycAnnualIncome': round(income) or '',
        'kycFoir': kyc.get('foir_declared'),
        'kycCibilScore': kyc.get('cibil_score'),
        'kycYearsEmployed': kyc.get('years_employed'),
        'kycNumDependents': kyc.get('num_dependents'),
        'kycMonthsAsCustomer': kyc.get('months_as_customer'),
        'kycLatePayments': kyc.get('num_late_payments_past_12m'),
        'kycExistingLoans': kyc.get('existing_loans_count'),
        'kycExistingProducts': kyc.get('num_existing_products'),
        'kycEmploymentType': _emap(_EMP_MAP, kyc.get('employment_type'), ''),
        'kycEducation': _emap(_EDU_MAP, kyc.get('education_level'), ''),
        'kycCityTier': _emap(_TIER_MAP, kyc.get('city_tier'), ''),
        'kycResidenceType': _emap(_RES_MAP, kyc.get('residence_type'), ''),
        'kycLoanPurpose': _emap(_PURP_MAP, kyc.get('loan_purpose'), ''),
        'kycPreviousDefault': kyc.get('previous_default_flag'),
        'kycIsRural': kyc.get('is_rural'),
        'kyc_status': 'Verified' if str(kyc.get('kyc_status', '')).upper() == 'VERIFIED' else 'Pending',
        'screening': 'pep' if kyc.get('is_pep') else 'clean',
    }
    fields.update({k: v for k, v in ratios.items() if v is not None})

    return jsonify({
        'found': True,
        'customer_id': cid,
        'bank_id': cust.get('bank_id'),
        'bank_name': bank.get('bank_name'),
        'country': bank.get('country'),
        'country_code': bank.get('country_code'),
        'fields': fields,
        'relationship': {
            'accounts': {'count': len(accounts),
                         'total_balance': round(sum(float(a.get('balance') or 0) for a in accounts), 0),
                         'types': sorted({a.get('type') for a in accounts if a.get('type')})},
            'loans': {'count': len(loans),
                      'total_outstanding': round(sum(float(l.get('outstanding') or 0) for l in loans), 0),
                      'total_emi': round(total_emi, 0),
                      'classifications': sorted({l.get('loan_classification') or 'Standard' for l in loans})},
            'transactions': txn_vars,
        },
    })


@app.route('/operations/api/system-dashboard')
def ops_system_dashboard():
    with _ops_conn() as conn:
        banks        = _rows_to_list(conn.execute('SELECT * FROM banks').fetchall())
        customers    = _rows_to_list(conn.execute('SELECT * FROM customers').fetchall())
        accounts     = _rows_to_list(conn.execute('SELECT * FROM accounts').fetchall())
        loans        = _rows_to_list(conn.execute('SELECT * FROM loans').fetchall())
        # OPTIMIZATION: Load only recent transactions for display (not all 88K+)
        transactions = _rows_to_list(conn.execute(
            'SELECT * FROM transactions ORDER BY date DESC, time DESC LIMIT 10000'
        ).fetchall())
        # RWA per bank from latest regulatory report
        rwa_rows = _rows_to_list(conn.execute(
            "SELECT bank_id, credit_rwa FROM reg_capital_reports r1 "
            "WHERE report_date = (SELECT MAX(report_date) FROM reg_capital_reports r2 WHERE r2.bank_id=r1.bank_id)"
        ).fetchall())
    rwa_map = {r['bank_id']: (r['credit_rwa'] or 0) for r in rwa_rows}

    # OPTIMIZATION: Aggregate loan/customer data using SQL
    with _ops_conn() as conn:
        loan_stats = _rows_to_list(conn.execute('''
            SELECT bank_id,
                   COUNT(*) as loan_count,
                   SUM(outstanding) as total_advances,
                   SUM(CASE WHEN loan_classification='NPA' THEN outstanding ELSE 0 END) as npa_amount,
                   SUM(CASE WHEN loan_classification='NPA' THEN 1 ELSE 0 END) as npa_count
            FROM loans
            GROUP BY bank_id
        ''').fetchall())

        account_stats = _rows_to_list(conn.execute('''
            SELECT bank_id, COUNT(*) as acc_count, SUM(balance) as total_deposits
            FROM accounts
            GROUP BY bank_id
        ''').fetchall())

        customer_stats = _rows_to_list(conn.execute('''
            SELECT bank_id, COUNT(*) as customer_count
            FROM customers
            GROUP BY bank_id
        ''').fetchall())

    # Build lookup maps
    loan_map = {l['bank_id']: l for l in loan_stats}
    acct_map = {a['bank_id']: a for a in account_stats}
    cust_map = {c['bank_id']: c for c in customer_stats}

    # Build bank summary using aggregated data
    bank_summary = []
    for b in banks:
        bid = b['bank_id']
        ls = loan_map.get(bid, {})
        ac = acct_map.get(bid, {})
        cs = cust_map.get(bid, {})

        n_loans = ls.get('loan_count', 0) or 0
        npa_amt = float(ls.get('npa_amount') or 0)
        advances = float(ls.get('total_advances') or 0)
        npa_count = ls.get('npa_count', 0) or 0

        bank_summary.append({
            'bank_id':      bid,
            'bank_name':    b['bank_name'],
            'customers':    cs.get('customer_count', 0),
            'accounts':     ac.get('acc_count', 0),
            'deposits':     float(ac.get('total_deposits', 0) or 0),
            'loans':        n_loans,
            'npas':         npa_count,
            'npaCountPct':  round(npa_count / n_loans * 100, 2) if n_loans else 0,
            'npaAmount':    npa_amt,
            'npaAmountPct': round(npa_amt / advances * 100, 2) if advances else 0,
            'advances':     advances,
            'rwa':          rwa_map.get(bid, 0),
        })

    payload = _ops_build_payload(None, customers, accounts, loans, transactions)
    payload['title'] = 'India Banking System — All Banks Combined'
    payload['banks'] = bank_summary

    # Aggregate system-level totals from SQL aggregations
    total_loans = sum(l.get('loan_count', 0) for l in loan_stats)
    total_advances = sum(float(l.get('total_advances', 0) or 0) for l in loan_stats)
    total_npa_amount = sum(float(l.get('npa_amount', 0) or 0) for l in loan_stats)
    total_npas = sum(l.get('npa_count', 0) for l in loan_stats)

    payload['kpis']['totalLoans']      = total_loans
    payload['kpis']['totalNPAs']       = total_npas
    payload['kpis']['totalNPAAmount']  = total_npa_amount
    payload['kpis']['npaCountPct']     = round(total_npas / total_loans * 100, 2) if total_loans else 0
    payload['kpis']['npaAmountPct']    = round(total_npa_amount / total_advances * 100, 2) if total_advances else 0
    payload['kpis']['totalAdvances']   = total_advances
    payload['kpis']['totalRWA']        = sum(rwa_map.values())
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
        # Basel III.1 SA: RWA breakdown by exposure_class
        rwa_by_exposure_class = _rows_to_list(conn.execute(
            "SELECT l.exposure_class, COUNT(rce.loan_id) n, "
            "SUM(rce.rwa) rwa, SUM(rce.ead) ead, "
            "ROUND(100.0*SUM(rce.rwa)/NULLIF(SUM(SUM(rce.rwa)) OVER(),0),1) rwa_pct "
            "FROM reg_client_exposures rce "
            "LEFT JOIN loans l ON l.id = rce.loan_id "
            "WHERE rce.bank_id=? AND rce.report_date=? "
            "GROUP BY l.exposure_class ORDER BY rwa DESC",
            (bank_id, d)).fetchall())
        # trend across dates
        trend = _rows_to_list(conn.execute(
            "SELECT cr.report_date, cr.car, cr.cet1_ratio, lr.lcr, lr.nsfr "
            "FROM reg_capital_reports cr LEFT JOIN reg_liquidity_reports lr "
            "ON cr.bank_id=lr.bank_id AND cr.report_date=lr.report_date "
            "WHERE cr.bank_id=? ORDER BY cr.report_date", (bank_id,)).fetchall())
        # balance sheet — all stored periods, newest first
        balance_sheets = _safe_balance_sheets(conn, bank_id)

    for r in (cap, liq):
        if r and r.get('detail'):
            try:
                r['assumptions'] = json.loads(r['detail'])
            except Exception:
                pass
    return jsonify({'available': True, 'report_date': d, 'thresholds': _RBI_THRESHOLDS,
                    'bank': bank, 'capital': cap, 'liquidity': liq,
                    'compliance': compliance, 'exposure_mix': mix,
                    'rwa_by_exposure_class': rwa_by_exposure_class,
                    'trend': trend, 'balance_sheets': balance_sheets})


def _safe_balance_sheets(conn, bank_id):
    """Balance-sheet rows for a bank (newest first), with computed totals.
    Returns [] if the table hasn't been seeded yet."""
    try:
        rows = _rows_to_list(conn.execute(
            "SELECT * FROM bank_balance_sheet WHERE bank_id=? ORDER BY as_on_date DESC",
            (bank_id,)).fetchall())
    except Exception:
        return []
    for r in rows:
        r['total_deposits'] = round(sum(float(r.get(k) or 0) for k in
                                        ('deposits_demand', 'deposits_savings', 'deposits_term')), 2)
        r['total_capital'] = round(float(r.get('equity_capital') or 0)
                                   + float(r.get('reserves_surplus') or 0), 2)
        r['total_liabilities_capital'] = round(
            r['total_capital'] + r['total_deposits']
            + float(r.get('borrowings') or 0) + float(r.get('other_liabilities') or 0), 2)
        r['total_assets'] = round(sum(float(r.get(k) or 0) for k in
                                      ('cash_with_rbi', 'balances_with_banks', 'investments',
                                       'advances_net', 'fixed_assets', 'other_assets')), 2)
    return rows


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


@app.route('/regulatory/api/banks/<bank_id>/balance-sheet')
def reg_bank_balance_sheet(bank_id):
    """RBI Schedule III balance sheet for one bank (all stored periods, newest first)."""
    with _ops_conn() as conn:
        bank = _row_to_dict(conn.execute(
            "SELECT * FROM banks WHERE bank_id=?", (bank_id,)).fetchone())
        sheets = _safe_balance_sheets(conn, bank_id)
    return jsonify({'available': bool(sheets), 'bank_id': bank_id, 'bank': bank,
                    'balance_sheets': sheets})


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
        results = run_batch(report_date=SIM_DATE, verbose=False)
        return jsonify({'success': True, 'banks_processed': len(results),
                        'report_date': SIM_DATE})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _run_regulatory_batch_job():
    """APScheduler entry point for the daily regulatory batch."""
    try:
        from operations.scripts.run_regulatory_batch import run_batch
        run_batch(report_date=SIM_DATE, verbose=False)
        print('[regulatory] daily batch completed')
    except Exception as e:
        print(f'[regulatory] batch error: {e}')


# ── NPA Classification Batch ─────────────────────────────────────────────────

def _run_npa_batch(conn=None, as_of_date=None):
    """Scan all loans, compute DPD from last EMI Payment, auto-classify NPA.

    DPD buckets (RBI):
      0-89   days → Standard
      90-179 days → Sub-Standard NPA
      180-359 days → Doubtful NPA
      360+   days → Loss Asset NPA

    Manual override_default=1 loans are preserved — batch never overwrites
    a credit-officer override (it still updates DPD for reporting).

    Uses bulk SQL to handle large loan books efficiently.
    Returns a summary dict.
    """
    import datetime
    close_conn = False
    if conn is None:
        conn = _ops_conn().__enter__()
        close_conn = True

    today_str = as_of_date if as_of_date else datetime.date.today().isoformat()

    # Step 1: compute last EMI payment per (cid, bank_id) in one query
    conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _npa_last_pmt AS
        SELECT a.cid, a.bank_id, MAX(t.date) AS last_pmt
        FROM transactions t
        JOIN accounts a ON t.aid = a.id
        WHERE t.type = 'EMI Payment'
        GROUP BY a.cid, a.bank_id
    """)

    # Step 2: bulk-update last_payment_date + days_past_due on all loans
    conn.execute(f"""
        UPDATE loans SET
            last_payment_date = COALESCE(
                (SELECT last_pmt FROM _npa_last_pmt p WHERE p.cid=loans.cid AND p.bank_id=loans.bank_id),
                loans.disbursed
            ),
            days_past_due = MAX(0, CAST(
                julianday('{today_str}') -
                julianday(COALESCE(
                    (SELECT last_pmt FROM _npa_last_pmt p WHERE p.cid=loans.cid AND p.bank_id=loans.bank_id),
                    loans.disbursed,
                    '{today_str}'
                ))
            AS INTEGER))
    """)

    # Step 3: reclassify — skip manual overrides
    # Sub-Standard: 90-179 DPD
    conn.execute("""
        UPDATE loans SET loan_classification='Sub-Standard', status='Defaulted'
        WHERE override_default=0 AND days_past_due BETWEEN 90 AND 179
          AND loan_classification NOT IN ('Sub-Standard','Doubtful','Loss Asset')
    """)
    # Doubtful: 180-359 DPD
    conn.execute("""
        UPDATE loans SET loan_classification='Doubtful', status='Defaulted'
        WHERE override_default=0 AND days_past_due BETWEEN 180 AND 359
          AND loan_classification != 'Loss Asset'
    """)
    # Loss Asset: 360+ DPD
    conn.execute("""
        UPDATE loans SET loan_classification='Loss Asset', status='Defaulted'
        WHERE override_default=0 AND days_past_due >= 360
    """)
    # Restore Standard if DPD < 90 (loan caught up) — only non-overridden
    conn.execute("""
        UPDATE loans SET loan_classification='Standard', status='Active'
        WHERE override_default=0 AND days_past_due < 90
          AND loan_classification IN ('Sub-Standard','Doubtful','Loss Asset')
    """)

    # Step 4: sync credit_risk_metrics npa_flag from loans
    conn.execute("""
        UPDATE credit_risk_metrics SET
            npa_flag = CASE WHEN l.loan_classification != 'Standard' THEN 1 ELSE 0 END,
            df       = CASE WHEN l.loan_classification != 'Standard' THEN 1 ELSE 0 END
        FROM loans l WHERE credit_risk_metrics.lid = l.id
    """)

    conn.execute("DROP TABLE IF EXISTS _npa_last_pmt")
    conn.commit()

    # Collect stats
    total   = conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
    npa     = conn.execute("SELECT COUNT(*) FROM loans WHERE loan_classification IN ('Sub-Standard','Doubtful','Loss Asset','NPA')").fetchone()[0]
    overrides = conn.execute("SELECT COUNT(*) FROM loans WHERE override_default=1").fetchone()[0]
    stats = {'processed': total, 'npa_total': npa, 'overridden': overrides}

    if close_conn:
        conn.close()
    return stats


def _run_npa_batch_job():
    """APScheduler entry point for the daily NPA classification batch."""
    try:
        with _ops_conn() as conn:
            stats = _run_npa_batch(conn)
        print(f'[npa-batch] completed: {stats}')
    except Exception as e:
        print(f'[npa-batch] error: {e}')


@app.route('/operations/api/ml-training-viz')
def ops_ml_training_viz():
    """Get ML training data visualizations - bank-wise and consolidated"""
    try:
        viz_file = os.path.join(os.path.dirname(__file__), 'ml_training_viz_data.json')
        if not os.path.exists(viz_file):
            return jsonify({'error': 'Visualization data not available'}), 404

        with open(viz_file, 'r') as f:
            viz_data = json.load(f)

        return jsonify(viz_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/operations/api/npa-batch', methods=['POST'])
def ops_npa_batch():
    """Manually trigger the NPA DPD batch. Optional body: {"as_of_date": "YYYY-MM-DD"}"""
    body = request.get_json(force=True) or {}
    as_of = body.get('as_of_date')
    try:
        with _ops_conn() as conn:
            stats = _run_npa_batch(conn, as_of_date=as_of)
        return jsonify({'success': True, 'stats': stats,
                        'as_of_date': as_of or __import__('datetime').date.today().isoformat()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/operations/api/loans/<loan_id>/classify', methods=['POST'])
def ops_loan_classify(loan_id):
    """Manual credit-officer override: classify any loan as NPA or restore to Standard.

    Body:
      classification  — 'Sub-Standard' | 'Doubtful' | 'Loss Asset' | 'Standard'
      reason          — mandatory free-text justification (>= 20 chars)
      officer         — officer ID / name (optional, defaults to 'CREDIT-OFFICER')
    """
    import datetime
    body = request.get_json(force=True) or {}
    classification = body.get('classification', '').strip()
    reason = body.get('reason', '').strip()
    officer = body.get('officer', 'CREDIT-OFFICER').strip()

    valid = {'Sub-Standard', 'Doubtful', 'Loss Asset', 'Standard'}
    if classification not in valid:
        return jsonify({'error': f'classification must be one of {sorted(valid)}'}), 400
    if len(reason) < 20:
        return jsonify({'error': 'reason must be at least 20 characters'}), 400

    with _ops_conn() as conn:
        loan = conn.execute("SELECT id, bank_id, loan_classification FROM loans WHERE id=?",
                            (loan_id,)).fetchone()
        if not loan:
            return jsonify({'error': f'Loan {loan_id} not found'}), 404

        is_npa = 0 if classification == 'Standard' else 1
        new_status = 'Active' if classification == 'Standard' else 'Defaulted'
        override_flag = 0 if classification == 'Standard' else 1
        now = datetime.datetime.utcnow().isoformat()

        conn.execute("""UPDATE loans SET loan_classification=?, status=?,
                        override_default=?, override_reason=?, override_by=?, override_at=?
                        WHERE id=?""",
                     (classification, new_status, override_flag, reason, officer, now, loan_id))
        conn.execute("UPDATE credit_risk_metrics SET npa_flag=?, df=? WHERE lid=?",
                     (is_npa, is_npa, loan_id))
        conn.commit()

    return jsonify({
        'loan_id': loan_id,
        'previous_classification': loan[2],
        'new_classification': classification,
        'override': bool(override_flag),
        'reason': reason,
        'officer': officer,
        'timestamp': now
    })


def _ensure_regulatory_reports():
    """Run the batch once at startup if the simulation-date report is missing."""
    try:
        with _ops_conn() as conn:
            if _reg_latest_date(conn) == SIM_DATE:
                return
        _run_regulatory_batch_job()
    except Exception as e:
        print(f'[regulatory] startup batch skipped: {e}')

# ============================================================================
# FINANCIAL REPORTING & DISCLOSURES DEPARTMENT
# Per-bank and consolidated Balance Sheet + P&L + Key Ratios + Basel III
# Pillar 3 disclosures, assembled from bank_balance_sheet / bank_profit_loss
# + the regulatory engine. Combined PDF (LaTeX) export per scope.
# ============================================================================
from backend import financial_reports as _fr
from backend import financial_report_pdf as _frpdf


def _seed_script(fname, modname):
    """Load and return a standalone operations/scripts seeder module."""
    import importlib.util
    base = os.path.join(os.path.dirname(__file__), 'operations', 'scripts')
    spec = importlib.util.spec_from_file_location(modname, os.path.join(base, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_financials(conn):
    """Seed the global layer + bank_balance_sheet + bank_profit_loss (self-init).

    The global layer (country reference + foreign banks + their real ledger) must
    be seeded FIRST so the BS/P&L seeders live-anchor all six banks from real
    loans/accounts rather than skipping the (then loan-less) foreign banks.
    """
    _ensure_global(conn)
    for tbl, fname, modname in (
            ('bank_balance_sheet', 'seed_bank_balance_sheet.py', 'seed_bank_balance_sheet'),
            ('bank_profit_loss',   'seed_bank_profit_loss.py',   'seed_bank_profit_loss')):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        except Exception:
            n = 0
        if not n:
            _seed_script(fname, modname).seed(db_path=_OPS_DB_PATH, verbose=False)


def _ensure_global(conn):
    """Seed the country reference layer + foreign group banks (self-init)."""
    try:
        n = conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    except Exception:
        n = 0
    if not n:
        _seed_script('seed_global.py', 'seed_global').seed(db_path=_OPS_DB_PATH, verbose=False)


def _country_index(conn):
    """country_code -> country dict (with macro latest snapshot attached)."""
    _ensure_global(conn)
    out = {}
    for r in conn.execute("SELECT * FROM countries").fetchall():
        d = _row_to_dict(r)
        out[d['country_code']] = d
    return out


def _macro_for(conn, code):
    rows = _rows_to_list(conn.execute(
        "SELECT * FROM country_macro WHERE country_code=? ORDER BY period", (code,)).fetchall())
    return rows


def _fin_gather(conn, bank, period=None):
    period = period or SIM_PERIOD
    """Gather one bank's stored + computed inputs for the financial reports."""
    from backend import regulatory_engine as _reg
    bid = bank['bank_id']
    loans = _rows_to_list(conn.execute("SELECT * FROM loans WHERE bank_id=?", (bid,)).fetchall())
    accts = _rows_to_list(conn.execute("SELECT * FROM accounts WHERE bank_id=?", (bid,)).fetchall())
    metrics = {r['lid']: dict(r) for r in
               conn.execute("SELECT * FROM credit_risk_metrics WHERE bank_id=?", (bid,)).fetchall()}
    bs = _row_to_dict(conn.execute(
        "SELECT * FROM bank_balance_sheet WHERE bank_id=? AND period=?", (bid, period)).fetchone())
    pl = _row_to_dict(conn.execute(
        "SELECT * FROM bank_profit_loss WHERE bank_id=? AND period=?", (bid, period)).fetchone())
    cap = _reg.bank_capital_report(bid, loans, accts, metrics, balance_sheet=bs)
    liq = _reg.bank_liquidity_report(bid, accts, loans, cap['total_capital'], balance_sheet=bs)
    mix = {}
    for e in cap['exposures']:
        k = (e['loan_type'], e['classification'])
        a = mix.setdefault(k, {'loan_type': k[0], 'classification': k[1],
                               'n': 0, 'ead': 0.0, 'rwa': 0.0, 'provision': 0.0})
        a['n'] += 1; a['ead'] += e['ead']; a['rwa'] += e['rwa']; a['provision'] += e['provision']
    def _is_npa(l): return (l.get('loan_classification') or 'Standard') not in ('Standard', 'Performing')
    stats = {
        'gnpa_amount': sum(float(l.get('outstanding') or 0) for l in loans if _is_npa(l)),
        'gross_advances': sum(float(l.get('outstanding') or 0) for l in loans),
        'num_loans': len(loans),
        'num_npa': sum(1 for l in loans if _is_npa(l)),
    }
    return {'bank': bank, 'bs': bs, 'pl': pl, 'cap': cap, 'liq': liq,
            'stats': stats, 'exposure_mix': list(mix.values())}


def _fin_bundle(conn, scope, period=None, as_on=None):
    period = period or SIM_PERIOD
    as_on  = as_on  or SIM_DATE
    """Return a report bundle for a bank_id, a region, a country, or the group.

    scope:  'CONSOLIDATED' | 'REGION:<region>' | 'COUNTRY:<iso3>' | '<bank_id>'.
    Region / country roll-ups reuse financial_reports.consolidate() over the
    member banks, so the maths is identical at every level of the hierarchy.
    """
    banks = _rows_to_list(conn.execute("SELECT * FROM banks").fetchall())
    countries = _country_index(conn)
    scope_s = str(scope)

    def _aggregate(members, scope_id, scope_name, scope_kind, scope_meta=None):
        raws = [_fin_gather(conn, b, period) for b in members]
        raws = [r for r in raws if r['bs'] and r['pl']]
        if not raws:
            return None
        return _fr.consolidate(raws, period, as_on, scope_id=scope_id,
                               scope_name=scope_name, scope=scope_kind, scope_meta=scope_meta)

    if scope_s.upper() == 'CONSOLIDATED':
        return _aggregate(banks, 'CONSOLIDATED', 'Group — All Banks', 'consolidated',
                          {'level': 'group'})

    if scope_s.upper().startswith('REGION:'):
        region = scope_s.split(':', 1)[1]
        members = [b for b in banks if (countries.get(b.get('country_code')) or {}).get('region') == region]
        return _aggregate(members, 'REGION:' + region, region + ' — Regional Aggregate',
                          'region', {'level': 'region', 'region': region})

    if scope_s.upper().startswith('COUNTRY:'):
        code = scope_s.split(':', 1)[1].upper()
        members = [b for b in banks if (b.get('country_code') or '').upper() == code]
        cdef = countries.get(code) or {}
        name = cdef.get('country_name', code)
        return _aggregate(members, 'COUNTRY:' + code, name + ' — Country Aggregate',
                          'country', {'level': 'country', 'country_code': code,
                                      'country_name': name, 'region': cdef.get('region')})

    bank = next((b for b in banks if b['bank_id'] == scope_s), None)
    if not bank:
        return None
    g = _fin_gather(conn, bank, period)
    if not g['bs'] or not g['pl']:
        return None
    bundle = _fr.bank_bundle(g['bank'], g['bs'], g['pl'], g['cap'], g['liq'],
                             g['stats'], g['exposure_mix'])
    cdef = countries.get(bank.get('country_code')) or {}
    bundle['country'] = {'country_code': bank.get('country_code'),
                         'country_name': cdef.get('country_name'),
                         'region': cdef.get('region'), 'sub_region': cdef.get('sub_region'),
                         'currency_code': cdef.get('currency_code'),
                         'currency_symbol': cdef.get('currency_symbol'),
                         'central_bank': cdef.get('central_bank'),
                         'basel_framework': cdef.get('basel_framework')}
    return bundle


@app.route('/financials/')
@app.route('/financials')
def financials_home():
    return send_from_directory('public/financials', 'index.html')


@app.route('/financials/api/system')
def fin_system():
    """Bank list with snapshot KPIs + a Group → Region → Country → Bank tree."""
    with _ops_conn() as conn:
        _ensure_financials(conn)
        countries = _country_index(conn)
        banks = _rows_to_list(conn.execute("SELECT * FROM banks").fetchall())
        cards = []
        for b in banks:
            g = _fin_gather(conn, b)
            if not g['bs'] or not g['pl']:
                continue
            cap, liq, pl = g['cap'], g['liq'], g['pl']
            cdef = countries.get(b.get('country_code')) or {}
            cards.append({
                'bank_id': b['bank_id'], 'bank_name': b['bank_name'],
                'country_code': b.get('country_code'),
                'country_name': cdef.get('country_name') or b.get('country'),
                'region': cdef.get('region') or 'Unassigned',
                'sub_region': cdef.get('sub_region'),
                'currency_code': cdef.get('currency_code'),
                'currency_symbol': cdef.get('currency_symbol'),
                'total_assets': cap['total_assets'], 'pat': float(pl['profit_after_tax']),
                'car': cap['car'], 'car_status': cap['car_status'],
                'lcr': liq['lcr'], 'lcr_status': liq['lcr_status'],
                'gnpa_pct': round(g['stats']['gnpa_amount'] / (g['stats']['gross_advances'] or 1) * 100, 2),
            })
        consol = _fin_bundle(conn, 'CONSOLIDATED')

    # Build the region → country → bank tree with rolled-up assets per node.
    regions = {}
    for c in cards:
        reg = regions.setdefault(c['region'], {'region': c['region'], 'total_assets': 0.0,
                                               'pat': 0.0, 'num_banks': 0, 'countries': {}})
        ctry = reg['countries'].setdefault(c['country_code'], {
            'country_code': c['country_code'], 'country_name': c['country_name'],
            'currency_code': c['currency_code'], 'total_assets': 0.0, 'pat': 0.0, 'banks': []})
        ctry['banks'].append({'bank_id': c['bank_id'], 'bank_name': c['bank_name'],
                              'total_assets': c['total_assets'], 'car': c['car'],
                              'lcr': c['lcr'], 'gnpa_pct': c['gnpa_pct']})
        ctry['total_assets'] += c['total_assets']; ctry['pat'] += c['pat']
        reg['total_assets'] += c['total_assets']; reg['pat'] += c['pat']; reg['num_banks'] += 1
    tree = []
    for reg in sorted(regions.values(), key=lambda r: -r['total_assets']):
        reg['countries'] = sorted(reg['countries'].values(), key=lambda c: -c['total_assets'])
        reg['num_countries'] = len(reg['countries'])
        reg['total_assets'] = round(reg['total_assets'], 2); reg['pat'] = round(reg['pat'], 2)
        for ctry in reg['countries']:
            ctry['total_assets'] = round(ctry['total_assets'], 2); ctry['pat'] = round(ctry['pat'], 2)
        tree.append(reg)

    snap = None
    if consol:
        cap, liq = consol['raw']['capital'], consol['raw']['liquidity']
        perf = {k['label']: k['value'] for k in (consol.get('performance_kpis') or [])}
        snap = {'total_assets': cap['total_assets'],
                'pat': float(consol['profit_loss']['summary'][-1]['value']),
                'nii': perf.get('Net Interest Income (NII)'),
                'nim': perf.get('Net Interest Margin (NIM)'),
                'operating_profit': perf.get('Operating Profit'),
                'roa': perf.get('Return on Assets (ROA)'),
                'rote': perf.get('Return on Tangible Equity (ROTE)'),
                'roe': perf.get('Return on Tangible Equity (ROTE)'),
                'yield_on_advances': perf.get('Yield on Advances'),
                'net_profit_margin': None, 'cost_to_income': None,
                'car': cap['car'], 'lcr': liq['lcr'], 'num_banks': len(cards),
                'num_countries': len({c['country_code'] for c in cards}),
                'num_regions': len(tree)}
        for r in (consol.get('key_ratios') or []):
            if r.get('label') == 'Net Profit Margin':
                snap['net_profit_margin'] = r['value']
            if r.get('label') == 'Cost-to-Income Ratio':
                snap['cost_to_income'] = r['value']
    return jsonify({'period': SIM_PERIOD, 'banks': cards, 'consolidated': snap, 'tree': tree})


@app.route('/financials/api/region/<region>')
def fin_region(region):
    with _ops_conn() as conn:
        _ensure_financials(conn)
        bundle = _fin_bundle(conn, 'REGION:' + region)
    if not bundle:
        return jsonify({'available': False, 'error': 'No financials for this region'}), 404
    bundle['available'] = True
    return jsonify(bundle)


@app.route('/financials/api/country/<code>')
def fin_country(code):
    with _ops_conn() as conn:
        _ensure_financials(conn)
        bundle = _fin_bundle(conn, 'COUNTRY:' + code)
    if not bundle:
        return jsonify({'available': False, 'error': 'No financials for this country'}), 404
    bundle['available'] = True
    return jsonify(bundle)


@app.route('/financials/api/banks/<bank_id>')
def fin_bank(bank_id):
    with _ops_conn() as conn:
        _ensure_financials(conn)
        bundle = _fin_bundle(conn, bank_id)
    if not bundle:
        return jsonify({'available': False, 'error': 'No financials for this bank'}), 404
    bundle['available'] = True
    return jsonify(bundle)


@app.route('/financials/api/consolidated')
def fin_consolidated():
    with _ops_conn() as conn:
        _ensure_financials(conn)
        bundle = _fin_bundle(conn, 'CONSOLIDATED')
    if not bundle:
        return jsonify({'available': False, 'error': 'No financials available'}), 404
    bundle['available'] = True
    return jsonify(bundle)


@app.route('/financials/api/reports/<scope>', methods=['GET', 'POST'])
def fin_reports(scope):
    """GET → list report versions; POST → generate a new combined PDF version."""
    scope_id = 'CONSOLIDATED' if str(scope).upper() == 'CONSOLIDATED' else scope
    if request.method == 'POST':
        with _ops_conn() as conn:
            _ensure_financials(conn)
            bundle = _fin_bundle(conn, scope_id)
        if not bundle:
            return jsonify({'error': 'No financials for this scope'}), 404
        try:
            meta = _frpdf.generate_report(bundle)
        except Exception as e:
            return jsonify({'error': f'Report generation failed: {e}'}), 500
        code = 201 if meta.get('pdf_exists') else 500
        return jsonify({'success': meta.get('pdf_exists', False), 'report': meta,
                        'versions': _frpdf.list_versions(scope_id)}), code
    return jsonify({'scope_id': scope_id, 'latex_available': _frpdf.latex_available(),
                    'versions': _frpdf.list_versions(scope_id)})


@app.route('/financials/api/reports/<scope>/<version>/pdf')
def fin_report_pdf(scope, version):
    scope_id = 'CONSOLIDATED' if str(scope).upper() == 'CONSOLIDATED' else scope
    path = _frpdf.pdf_path(scope_id, version)
    if not path:
        return jsonify({'error': 'PDF not found'}), 404
    download = request.args.get('dl') in ('1', 'true', 'yes')
    return _send_file(path, mimetype='application/pdf', as_attachment=download,
                      download_name=f'{scope_id}_{version}.pdf')


# ============================================================================
# GLOBAL REFERENCE DATA — COUNTRIES & MACRO INDICATORS
# Jurisdiction master + high-level economic variables (GDP, inflation, policy
# rate, …) that sit above the banks: the group operates Group → Region →
# Country → Bank. Sourced from the `countries` / `country_macro` tables.
# ============================================================================
def _macro_snapshot(macro_rows):
    """Latest macro row (by period) from a country's macro history."""
    return dict(macro_rows[-1]) if macro_rows else None


@app.route('/reference/')
@app.route('/reference')
def reference_home():
    return send_from_directory('public/reference', 'index.html')


@app.route('/reference/api/countries')
def ref_countries():
    """All jurisdictions with latest macro snapshot, region grouping + bank counts."""
    with _ops_conn() as conn:
        _ensure_global(conn)
        countries = [_row_to_dict(r) for r in conn.execute(
            "SELECT * FROM countries ORDER BY region, sub_region, country_name").fetchall()]
        bank_counts = {r['country_code']: r['n'] for r in conn.execute(
            "SELECT country_code, COUNT(*) AS n FROM banks GROUP BY country_code").fetchall()}
        out = []
        for c in countries:
            macro = _macro_snapshot(_macro_for(conn, c['country_code']))
            c['num_banks'] = bank_counts.get(c['country_code'], 0)
            c['macro'] = macro
            out.append(c)
    # group by region for the UI
    regions = {}
    for c in out:
        regions.setdefault(c['region'], []).append(c)
    tree = [{'region': r, 'countries': cs,
             'num_banks': sum(x['num_banks'] for x in cs)}
            for r, cs in sorted(regions.items())]
    return jsonify({'countries': out, 'regions': tree,
                    'num_countries': len(out),
                    'num_with_banks': sum(1 for c in out if c['num_banks'])})


@app.route('/reference/api/countries/<code>')
def ref_country(code):
    """One jurisdiction: profile, macro history, and the group's banks there."""
    code = code.upper()
    with _ops_conn() as conn:
        _ensure_global(conn)
        row = conn.execute("SELECT * FROM countries WHERE country_code=?", (code,)).fetchone()
        if not row:
            return jsonify({'available': False, 'error': 'Unknown country'}), 404
        country = _row_to_dict(row)
        macro = _macro_for(conn, code)
        banks = _rows_to_list(conn.execute(
            "SELECT * FROM banks WHERE country_code=?", (code,)).fetchall())
        cards = []
        for b in banks:
            g = _fin_gather(conn, b)
            if not g['bs'] or not g['pl']:
                cards.append({'bank_id': b['bank_id'], 'bank_name': b['bank_name'], 'available': False})
                continue
            cap, liq, pl = g['cap'], g['liq'], g['pl']
            cards.append({
                'bank_id': b['bank_id'], 'bank_name': b['bank_name'], 'available': True,
                'headquarters_city': b.get('headquarters_city'),
                'total_assets': cap['total_assets'], 'pat': float(pl['profit_after_tax']),
                'car': cap['car'], 'car_status': cap['car_status'],
                'lcr': liq['lcr'], 'lcr_status': liq['lcr_status'],
                'gnpa_pct': round(g['stats']['gnpa_amount'] / (g['stats']['gross_advances'] or 1) * 100, 2),
            })
    return jsonify({'available': True, 'country': country, 'macro': macro, 'banks': cards})


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
# ANALYTICS — Performance Time-Series Dashboard
# ============================================================================

@app.route('/analytics/')
@app.route('/analytics')
def analytics_home():
    return send_from_directory('public/analytics', 'index.html')


@app.route('/analytics/api/timeseries')
def analytics_timeseries():
    """
    Returns all time-series datasets for the performance dashboard.
    Query params: bank_id (default BANK001 - HDFC Bank)
    Uses latest available data, not hardcoded simulation date.
    """
    bank_id = request.args.get('bank_id', 'BANK001')
    with _ops_conn() as conn:
        # ── Capital adequacy (from regulatory batch) ──────────────────────
        # Use ALL available data, sorted by date (not filtered to SIM_DATE)
        cap_rows = [dict(r) for r in conn.execute(
            """SELECT report_date, car, cet1_ratio, tier1_ratio, leverage_ratio,
                      total_rwa, loan_book, num_loans, num_npa, total_provisions
               FROM reg_capital_reports WHERE bank_id=? ORDER BY report_date""",
            (bank_id,)).fetchall()]

        # ── Liquidity ratios ──────────────────────────────────────────────
        liq_rows = [dict(r) for r in conn.execute(
            """SELECT report_date, lcr, nsfr, crr_ratio, slr_ratio, hqla, ndtl
               FROM reg_liquidity_reports WHERE bank_id=? ORDER BY report_date""",
            (bank_id,)).fetchall()]

        # ── Balance sheet ─────────────────────────────────────────────────
        bs_rows = [dict(r) for r in conn.execute(
            """SELECT period, as_on_date,
                      advances_net, investments,
                      deposits_demand+deposits_savings+deposits_term AS deposits,
                      equity_capital+reserves_surplus AS capital,
                      cash_with_rbi, balances_with_banks, other_assets,
                      borrowings, other_liabilities, intangible_assets
               FROM bank_balance_sheet WHERE bank_id=? ORDER BY as_on_date""",
            (bank_id,)).fetchall()]

        # ── P&L ───────────────────────────────────────────────────────────
        pl_rows = [dict(r) for r in conn.execute(
            """SELECT period, from_date, to_date,
                      net_interest_income, other_income, total_income,
                      interest_expended, operating_expenses,
                      provisions_contingencies, operating_profit,
                      profit_before_tax, profit_after_tax
               FROM bank_profit_loss WHERE bank_id=? ORDER BY to_date""",
            (bank_id,)).fetchall()]

    # ── Derived metrics ───────────────────────────────────────────────────
    def _cr(v): return round(v / 1e7, 2) if v else 0   # rupees → Cr
    def _pct(v): return round(v, 2) if v else 0

    capital_series, liquidity_series, balance_series, pl_series = [], [], [], []

    for r in cap_rows:
        lbook = r.get('loan_book') or 0
        npa   = r.get('num_npa') or 0
        loans = r.get('num_loans') or 1
        capital_series.append({
            'date':          r['report_date'],
            'car':           _pct(r.get('car')),
            'cet1':          _pct(r.get('cet1_ratio')),
            'tier1':         _pct(r.get('tier1_ratio')),
            'leverage':      _pct(r.get('leverage_ratio')),
            'total_rwa_cr':  _cr(r.get('total_rwa')),
            'loan_book_cr':  _cr(lbook),
            'num_loans':     loans,
            'num_npa':       npa,
            'npa_ratio':     round(npa / loans * 100, 2) if loans else 0,
            'provisions_cr': _cr(r.get('total_provisions')),
        })

    for r in liq_rows:
        liquidity_series.append({
            'date':      r['report_date'],
            'lcr':       _pct(r.get('lcr')),
            'nsfr':      _pct(r.get('nsfr')),
            'crr':       _pct(r.get('crr_ratio')),
            'slr':       _pct(r.get('slr_ratio')),
            'hqla_cr':   _cr(r.get('hqla')),
            'ndtl_cr':   _cr(r.get('ndtl')),
        })

    for r in bs_rows:
        cap  = r.get('capital') or 0
        intan= r.get('intangible_assets') or 0
        tang = cap - intan
        balance_series.append({
            'period':       r['period'],
            'date':         r['as_on_date'],
            'advances_cr':  _cr(r.get('advances_net')),
            'investments_cr': _cr(r.get('investments')),
            'deposits_cr':  _cr(r.get('deposits')),
            'capital_cr':   _cr(cap),
            'tang_equity_cr': _cr(tang),
            'cash_cr':      _cr((r.get('cash_with_rbi') or 0) + (r.get('balances_with_banks') or 0)),
            'borrowings_cr': _cr(r.get('borrowings')),
        })

    for r in pl_rows:
        pat  = r.get('profit_after_tax') or 0
        # match tangible equity from balance sheet by period
        bs_m = next((b for b in balance_series if b['period'] == r['period']), None)
        te   = (bs_m['tang_equity_cr'] * 1e7) if bs_m else 1
        rote = round(pat / te * 100, 2) if te else 0
        pl_series.append({
            'period':        r['period'],
            'date':          r['to_date'],
            'nii_cr':        _cr(r.get('net_interest_income')),
            'other_income_cr': _cr(r.get('other_income')),
            'total_income_cr': _cr(r.get('total_income')),
            'interest_exp_cr': _cr(r.get('interest_expended')),
            'opex_cr':       _cr(r.get('operating_expenses')),
            'provisions_cr': _cr(r.get('provisions_contingencies')),
            'op_profit_cr':  _cr(r.get('operating_profit')),
            'pat_cr':        _cr(pat),
            'rote':          rote,
        })

    # ── Thresholds for reference lines ───────────────────────────────────
    thresholds = {
        'car_min': 11.5, 'cet1_min': 8.0, 'tier1_min': 9.5, 'leverage_min': 3.0,
        'lcr_min': 100.0, 'nsfr_min': 100.0, 'crr_min': 3.0, 'slr_min': 18.0,
        'nim_min': 2.5, 'ci_max': 60.0,
    }

    # ── Efficiency series (NIM, Cost-to-Income, ROA) ───────────────────────
    from datetime import datetime as _dt
    efficiency_series = []
    for pl_r, bs_r in zip(pl_rows, bs_rows):
        adv   = bs_r.get('advances_net') or 1
        nii   = pl_r.get('net_interest_income') or 0
        oi    = pl_r.get('other_income') or 0
        opex  = pl_r.get('operating_expenses') or 0
        pat   = pl_r.get('profit_after_tax') or 0
        ta    = sum(bs_r.get(k) or 0 for k in
                   ('cash_with_rbi','balances_with_banks','investments',
                    'advances_net','fixed_assets','intangible_assets','other_assets'))
        # annualise monthly figures (monthly periods have from_date != to_date - 28-31 days)
        from_d = pl_r.get('from_date','')
        to_d   = pl_r.get('to_date','')
        try:
            days = (_dt.strptime(to_d,'%Y-%m-%d') - _dt.strptime(from_d,'%Y-%m-%d')).days
            scale = 365 / max(days, 1)
        except Exception:
            scale = 1
        nim_ann  = round(nii * scale / adv * 100, 2) if adv else 0
        ci_ratio = round(opex / (nii + oi) * 100, 2) if (nii + oi) > 0 else 0
        roa_ann  = round(pat * scale / ta * 100, 2) if ta else 0
        efficiency_series.append({
            'period': pl_r['period'],
            'date':   to_d,
            'nim':    nim_ann,
            'cost_to_income': ci_ratio,
            'roa':    roa_ann,
        })

    # ── Moratorium time series (from sim_period_metrics) ──────────────────
    moratorium_series = []
    try:
        conn.execute("SELECT 1 FROM sim_period_metrics LIMIT 1")
        sm_rows = [dict(r) for r in conn.execute(
            """SELECT period, as_of_date, morat_count, morat_pct, morat_book_cr,
                      morat_green, morat_amber, morat_red,
                      gate_gnpa, gate_pat, gate_car, gate_morat, gate_disbursals,
                      new_disbursals
               FROM sim_period_metrics WHERE bank_id=? ORDER BY as_of_date""",
            (bank_id,)).fetchall()]
        for r in sm_rows:
            moratorium_series.append({
                'period':      r['period'],
                'date':        r['as_of_date'],
                'count':       r['morat_count'] or 0,
                'pct':         round(r['morat_pct'] or 0, 1),
                'book_cr':     round(r['morat_book_cr'] or 0, 1),
                'green':       r['morat_green'] or 0,
                'amber':       r['morat_amber'] or 0,
                'red':         r['morat_red'] or 0,
                'new_disbursals': r['new_disbursals'] or 0,
                'gate': {
                    'gnpa':       r['gate_gnpa'],
                    'pat':        r['gate_pat'],
                    'car':        r['gate_car'],
                    'moratorium': r['gate_morat'],
                    'disbursals': r['gate_disbursals'],
                },
            })
    except Exception:
        pass

    # ── Decision gate for latest period ───────────────────────────────────
    def _gate_score(metric, val):
        if metric == 'gnpa':    return 'GREEN' if val < 2 else ('AMBER' if val < 4 else 'RED')
        if metric == 'pat':     return 'GREEN' if val > 0 else ('AMBER' if val > -3 else 'RED')
        if metric == 'car':     return 'GREEN' if val > 15 else ('AMBER' if val > 13 else 'RED')
        if metric == 'morat':   return 'GREEN' if val < 15 else ('AMBER' if val < 25 else 'RED')
        if metric == 'disbur':  return 'GREEN' if val > 25 else ('AMBER' if val > 15 else 'RED')
        return 'GREEN'

    decision_gate = {}
    # Build decision gate from available capital and P&L data (moratorium data optional)
    if capital_series and pl_series:
        latest_cap   = capital_series[-1]
        latest_pl    = pl_series[-1]
        latest_morat = moratorium_series[-1] if moratorium_series else {}
        nd_count     = latest_morat.get('new_disbursals', 0)
        decision_gate = {
            'period': latest_cap['date'],
            'gnpa':   {'value': latest_cap['npa_ratio'],
                       'status': _gate_score('gnpa', latest_cap['npa_ratio'])},
            'pat':    {'value': latest_pl['pat_cr'],
                       'status': _gate_score('pat', latest_pl['pat_cr'])},
            'car':    {'value': latest_cap['car'],
                       'status': _gate_score('car', latest_cap['car'])},
            'moratorium': {'value': latest_morat.get('pct', 0),
                           'status': _gate_score('morat', latest_morat.get('pct', 0))},
            'disbursals': {'value': nd_count,
                           'status': _gate_score('disbur', nd_count)},
        }

    # Use latest date from actual data, not hardcoded SIM_DATE
    latest_date = SIM_DATE
    if capital_series:
        latest_date = max(r['date'] for r in capital_series)
    elif liquidity_series:
        latest_date = max(r['date'] for r in liquidity_series)
    elif balance_series:
        latest_date = max(r['date'] for r in balance_series)
    elif pl_series:
        latest_date = max(r['date'] for r in pl_series)

    return jsonify({
        'bank_id':    bank_id,
        'sim_date':   latest_date,  # Use latest date from actual data
        'sim_period': SIM_PERIOD,
        'capital':    capital_series,
        'liquidity':  liquidity_series,
        'balance':    balance_series,
        'pl':         pl_series,
        'efficiency': efficiency_series,
        'moratorium': moratorium_series,
        'decision_gate': decision_gate,
        'thresholds': thresholds,
    })


@app.route('/analytics/api/banks')
def analytics_banks():
    """List of banks available for the analytics scope picker."""
    with _ops_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT bank_id, bank_name, country_code FROM banks ORDER BY bank_id").fetchall()]
    return jsonify(rows)


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
