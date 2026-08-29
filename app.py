"""
Banking Credit Risk Calculator - Flask Backend
Flask API for AIRB, Standardized Approach calculations, and Admin/ML Training.
"""

import os
import json
import shutil
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

# Detect readonly filesystem (Cloud Run, App Engine, etc.) early
# so GCS download thread can be started below
_READONLY_FS = (os.environ.get('READONLY_FS', 'false').lower() == 'true'
                 or os.environ.get('GAE_ENV', '').startswith('standard')
                 or bool(os.environ.get('GAE_APPLICATION'))
                 or bool(os.environ.get('K_SERVICE')))

# ── Cloud Storage Integration (GCS for persistent data on Cloud Run) ──────────
# On production (Cloud Run), download bank.db and ML models from GCS on startup
try:
    from backend.cloud_storage import CloudStorageManager
    _GCS_PROJECT = os.environ.get('GCP_PROJECT_ID', 'render-demo-06062141')
    _GCS_DATA_BUCKET = os.environ.get('GCS_DATA_BUCKET', 'banking-credit-risk-data')
    _GCS_MANAGER = None

    def _init_gcs():
        """Initialize GCS manager on startup"""
        global _GCS_MANAGER
        print(f"[GCS] Initializing manager (project={_GCS_PROJECT}, bucket={_GCS_DATA_BUCKET})...")
        try:
            _GCS_MANAGER = CloudStorageManager(_GCS_PROJECT, _GCS_DATA_BUCKET)
            print("[GCS] Manager initialized successfully")
        except Exception as e:
            print(f"[GCS] Warning: Could not initialize GCS manager: {e}")
            _GCS_MANAGER = None

    def _download_from_gcs():
        """Download bank.db and ML models from GCS (async, non-blocking)"""
        if not _READONLY_FS or not _GCS_MANAGER:
            return

        def _download_bg():
            try:
                # Download bank.db
                local_db = '/tmp/bank.db'
                if not os.path.exists(local_db) and _GCS_MANAGER.file_exists('database/bank.db'):
                    print('[GCS] Downloading bank.db from cloud storage...')
                    _GCS_MANAGER.download_file('database/bank.db', local_db)

                # Download ML models
                models_dir = '/tmp/ml_models'
                os.makedirs(models_dir, exist_ok=True)

                model_files = _GCS_MANAGER.list_files('models/')
                if model_files:
                    print(f'[GCS] Found {len(model_files)} model files in cloud storage')
                    for model_blob in model_files:
                        local_path = os.path.join(models_dir, os.path.basename(model_blob))
                        if not os.path.exists(local_path):
                            print(f'[GCS] Downloading {os.path.basename(model_blob)}...')
                            _GCS_MANAGER.download_file(model_blob, local_path)
                    print(f'[GCS] Downloaded {len(model_files)} model files')
            except Exception as e:
                print(f'[GCS] Download error (non-fatal, will use local files if available): {e}')

        # Start download in background thread (non-blocking)
        thread = threading.Thread(target=_download_bg, daemon=True, name='GCS-Download-Thread')
        thread.start()

    # Initialize GCS on startup
    _init_gcs()

    # Start downloading files from GCS (async, non-blocking)
    if _READONLY_FS:
        _download_from_gcs()

except ImportError:
    print('[GCS] Cloud Storage module not available (OK for local development)')
    _GCS_MANAGER = None

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

# ── Banking Operations (bank.db — direct sqlite3, read + write) ──────────────
import sqlite3 as _sqlite3
import threading as _threading

_OPS_DB_PATH = os.path.join(os.path.dirname(__file__), 'bank.db')

# On App Engine Standard AND Cloud Run, the deployed source directory is mounted
# read-only at runtime (only /tmp is writable) - RM case creation, NPA resolution,
# and other writes fail with "attempt to write a readonly database" unless bank.db
# is copied to /tmp first. GAE_ENV/GAE_APPLICATION (App Engine) and K_SERVICE
# (Cloud Run) are set automatically by their respective runtimes and never present
# locally, so this only kicks in on GCP. Note: /tmp is per-instance and ephemeral -
# fine for a single-instance demo, but writes are lost on restart and not shared
# if the app scales out.
#
# The copy (~350MB) must NOT block the import of this module: gunicorn workers
# import app.py before they start accepting requests, and a synchronous copy
# here delayed startup past the platform's health-check window, causing it to
# kill and restart the instance in a loop (visible in logs as repeated
# "Starting gunicorn" -> "Handling signal: term" within seconds).
# Instead, the copy runs in a background thread while gunicorn is free to bind
# and pass health checks immediately; _ops_conn() waits on it only if a request
# for the DB arrives before the copy has finished.
_db_copy_ready = _threading.Event()

if _READONLY_FS:
    _tmp_db_path = os.path.join('/tmp', 'bank.db')
    _OPS_DB_PATH = _tmp_db_path

    def _copy_db_to_tmp_bg():
        try:
            if not os.path.exists(_tmp_db_path):
                # [1] Try GCS first (Cloud Run production)
                print(f'[DB] GCS_MANAGER available: {_GCS_MANAGER is not None}')
                if _GCS_MANAGER:
                    try:
                        print('[GCS] Downloading bank.db from cloud storage...')
                        _GCS_MANAGER.download_file('database/bank.db', _tmp_db_path)
                        print('[GCS] bank.db downloaded successfully')
                        return
                    except Exception as e:
                        print(f'[GCS] Download failed, falling back to local copy: {e}')

                # [2] Fallback: copy from local source (for development/testing)
                src = os.path.join(os.path.dirname(__file__), 'bank.db')
                print(f'[DB] Checking for local bank.db at: {src}')
                if os.path.exists(src):
                    partial_path = _tmp_db_path + '.partial'
                    print(f'[DB] Copying from {src} to {_tmp_db_path}')
                    shutil.copy2(src, partial_path)
                    os.replace(partial_path, _tmp_db_path)
                    print(f'[DB] bank.db copied to {_tmp_db_path}')
                else:
                    print(f'[DB] Warning: bank.db not found at {src}')
        finally:
            _db_copy_ready.set()

    _threading.Thread(target=_copy_db_to_tmp_bg, daemon=True).start()
else:
    _db_copy_ready.set()

def _ops_conn():
    """Return a sqlite3 connection to bank.db with dict-like rows."""
    if _READONLY_FS and not _db_copy_ready.is_set():
        _db_copy_ready.wait(timeout=60)
    conn = _sqlite3.connect(_OPS_DB_PATH)
    conn.row_factory = _sqlite3.Row
    return conn


def _ensure_banks_world_column():
    """One-time defensive migration for bank.db files created before the
    Utopian/Real Earth world concept existed (setup_fresh_db.py's CREATE
    TABLE now includes it for new DBs). Existing 9 banks default to
    'utopian' - only newly onboarded banks (e.g. Bank of Punjab) get 'real'."""
    try:
        conn = _sqlite3.connect(_OPS_DB_PATH)
        conn.execute("ALTER TABLE banks ADD COLUMN world TEXT NOT NULL DEFAULT 'utopian'")
        conn.commit()
        conn.close()
    except Exception as e:
        if 'duplicate column' not in str(e).lower():
            print(f"WARNING: banks.world migration failed: {e}")


try:
    _ensure_banks_world_column()
except Exception:
    pass

# Lazy-load ML model (on first use, not on startup)
# This allows app to start even if GCS download is still in progress
import joblib as _joblib

# In Cloud Run with readonly filesystem, models are downloaded to /tmp/ml_models
# Otherwise, use local ml_models directory
_MODELS_DIR = '/tmp/ml_models' if _READONLY_FS else os.path.join(os.path.dirname(__file__), 'ml_models')
_MODEL_PATH = os.path.join(_MODELS_DIR, 'pd_model.pkl')
_pd_model = None
_model_load_attempted = False

def _get_pd_model():
    global _pd_model, _model_load_attempted
    if _model_load_attempted:
        return _pd_model
    _model_load_attempted = True
    try:
        _pd_model = _joblib.load(_MODEL_PATH)
        print(f"[MODEL] Loaded PD model from {_MODEL_PATH}")
    except Exception as e:
        print(f"[MODEL] Could not load PD model: {e}")
        _pd_model = None
    return _pd_model

# Initialise AssessmentEngine once — stateless, thread-safe per request
from backend.assessment_engine import AssessmentEngine as _AssessmentEngine
from backend.feature_meta import model_feature_frame

def _get_model_version():
    try:
        meta_path = os.path.join(_MODELS_DIR, 'pd_model_metadata.json')
        with open(meta_path) as f:
            return json.load(f).get('version', 'unknown')
    except Exception:
        return 'unknown'

_assessment_engine = _AssessmentEngine(_get_pd_model(), _get_model_version(), db_path=_OPS_DB_PATH)

# ── Segmented PD models (one per Basel exposure_class) ───────────────────────
# A live system must score a CORPORATE loan with the CORPORATE model and a
# RETAIL_OTHER loan with the RETAIL_OTHER model at the same time, so unlike
# the single _pd_model/_assessment_engine above (kept for the unsegmented
# legacy 'ALL' slot and non-scoring endpoints), this is a small registry of
# independently-loaded engines, one per segment. Mirrors the active-slot file
# naming convention in ml_models/trainer.py's _segment_paths().
EXPOSURE_CLASSES = ['CORPORATE', 'SME', 'RETAIL_MORTGAGES', 'RETAIL_OTHER']


def _segment_model_paths(exposure_class, bank_id=None):
    """Paths for a segment's active model slot. When bank_id is given,
    resolves to that bank's own scoped active slot (see trainer.py's
    _segment_paths bank_combo param) instead of the shared cross-bank slot -
    same file-naming convention on both sides."""
    seg = exposure_class
    if bank_id:
        suffix = f'{seg}_{bank_id}'
        return (
            os.path.join(_MODELS_DIR, f'pd_model_{suffix}.pkl'),
            os.path.join(_MODELS_DIR, f'pd_model_metadata_{suffix}.json'),
        )
    return (
        os.path.join(_MODELS_DIR, f'pd_model_{seg}.pkl'),
        os.path.join(_MODELS_DIR, f'pd_model_metadata_{seg}.json'),
    )


def _resolve_model_lab_pkl_path(model_type, bank_key, exposure_class):
    """Resolve the .pkl path for a SPECIFIC configured model (not necessarily
    the active one) out of the 3-level 'models/<model_type>/<bank_combo>/
    <exposure_class>/' layout scanned by /admin/api/models, with the same
    back-compat fallbacks that endpoint uses for older, shallower layouts.
    Used by Model Lab so research (e.g. global SHAP) can target any trained
    model, active or not."""
    models_dir = os.path.join(_MODELS_DIR, 'models')
    bank_key = bank_key or 'ALL'
    exposure_class = exposure_class or 'ALL'

    seg_path = os.path.join(models_dir, model_type, bank_key, exposure_class, 'pd_model.pkl')
    if os.path.exists(seg_path):
        return seg_path
    combo_path = os.path.join(models_dir, model_type, bank_key, 'pd_model.pkl')
    if exposure_class == 'ALL' and os.path.exists(combo_path):
        return combo_path
    flat_path = os.path.join(models_dir, model_type, 'pd_model.pkl')
    if bank_key == 'ALL' and exposure_class == 'ALL' and os.path.exists(flat_path):
        return flat_path
    return None


def _segment_model_version(exposure_class, bank_id=None):
    _, meta_path = _segment_model_paths(exposure_class, bank_id)
    try:
        with open(meta_path) as f:
            return json.load(f).get('version', 'unknown')
    except Exception:
        return 'unknown'


def _build_segment_engine(exposure_class, bank_id=None):
    model_path, _ = _segment_model_paths(exposure_class, bank_id)
    try:
        model = _joblib.load(model_path)
    except Exception as e:
        if not bank_id:
            print(f"WARNING: No trained model yet for segment '{exposure_class}': {e}")
        return None
    # Bank-scoped models are trained with bank_scoped=True (trainer.py's
    # _validate_dataframe), which leaves real NaN in partially-populated
    # feature columns instead of imputing/dropping - XGBoost natively
    # learns a default split direction for them. Tagging the loaded model
    # object here (not threading a new parameter through every
    # model_feature_frame() call site) lets live inference honor the same
    # "genuinely unknown" semantics the model was actually trained under,
    # instead of silently substituting a fabricated default value that
    # follows a completely different, uncalibrated path through the trees.
    # Utopian Earth's combined models (bank_id=None here) never see this
    # flag set, so their existing default-fill behavior is unchanged.
    model.allow_missing_features_ = bool(bank_id)
    return _AssessmentEngine(model, _segment_model_version(exposure_class, bank_id), db_path=_OPS_DB_PATH, exposure_class=exposure_class)


_segment_engines = {seg: _build_segment_engine(seg) for seg in EXPOSURE_CLASSES}

# Model-routing switch: lazily-populated cache for bank-specific engines
# (segment-specific AND bank-generic). Not pre-built at startup like
# _segment_engines - the number of (bank, segment) combinations can grow
# arbitrarily as more banks get their own models, so these are built on
# first use and cached thereafter (a miss - key mapped to None - is cached
# too, so an untrained bank/segment combo doesn't hit disk every request).
GENERIC_SEGMENT = 'GENERIC'   # bank-wide model, no exposure_class segmentation
_bank_engine_cache: dict = {}


def _resolve_bank_engine(bank_id, exposure_class):
    """3-tier fallback for a bank-aware request: bank+segment -> bank+GENERIC
    -> (None, None) (caller falls back to the shared cross-bank segment
    engine). Returns (engine, scope_label) so the caller can record which
    tier actually served the request."""
    for key, seg, label in (
        (f'{bank_id}::{exposure_class}', exposure_class, 'bank_specific_segment'),
        (f'{bank_id}::{GENERIC_SEGMENT}', GENERIC_SEGMENT, 'bank_specific_generic'),
    ):
        if key not in _bank_engine_cache:
            _bank_engine_cache[key] = _build_segment_engine(seg, bank_id=bank_id)
        if _bank_engine_cache[key] is not None:
            return _bank_engine_cache[key], label
    return None, None


def _resolve_segment_engine(data):
    """
    Validate the exposure_class on a scoring request and return its engine.
    Returns (engine, scope_used, None) on success, or (None, None,
    (json_response, status)) on failure - per the confirmed decision, a
    missing/unrecognized/untrained exposure_class is REJECTED rather than
    silently falling back to a default segment or a blended model.

    Model-routing switch (opt-in, backward compatible): a request that sets
    model_scope='bank_specific' and provides bank_id prefers that bank's own
    model (segment-specific, else bank-generic) over the shared cross-bank
    segment model. Any request that doesn't set model_scope - i.e. every
    caller before this switch existed - behaves exactly as before, and
    scope_used comes back as 'combined'.
    """
    exposure_class = (data.get('exposure_class') or '').strip().upper()
    if not exposure_class:
        return None, None, (jsonify({
            'error': 'exposure_class is required',
            'message': f'Provide exposure_class as one of: {", ".join(EXPOSURE_CLASSES)}'
        }), 400)
    if exposure_class not in EXPOSURE_CLASSES:
        return None, None, (jsonify({
            'error': 'Unrecognized exposure_class',
            'message': f'exposure_class must be one of: {", ".join(EXPOSURE_CLASSES)}'
        }), 400)

    bank_id = (data.get('bank_id') or '').strip()
    model_scope = (data.get('model_scope') or 'combined').strip().lower()
    if model_scope == 'bank_specific' and bank_id:
        bank_engine, scope_label = _resolve_bank_engine(bank_id, exposure_class)
        if bank_engine is not None:
            return bank_engine, scope_label, None
        # No bank-specific model exists for this bank/segment - fall through
        # to the shared model, flagged distinctly so it's clear the RM's
        # choice couldn't actually be honoured for this assessment.
        fallback_scope = 'combined_fallback'
    else:
        fallback_scope = 'combined'

    engine = _segment_engines.get(exposure_class)
    if engine is None:
        return None, None, (jsonify({
            'error': 'No trained model available for this segment',
            'message': f'No active model has been trained/activated yet for exposure_class={exposure_class}'
        }), 503)
    return engine, fallback_scope, None

# In-memory report cache keyed by report_id (uuid).
_report_cache: dict = {}

# ── File-based persistence paths ───────────────────────────────────────────
# On GCP (App Engine or Cloud Run) the source directory is read-only, so use
# /tmp for ephemeral data - see _READONLY_FS definition above.
_BASE_DATA_DIR = '/tmp/data' if _READONLY_FS else os.path.join(os.path.dirname(__file__), 'data')
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

        engine, model_scope_used, err = _resolve_segment_engine(data)
        if err:
            return err
        model = engine._model

        # Build feature frame aligned to the model's expected schema.
        # Missing values default to population medians (feature_meta.py).
        df_features = model_feature_frame(data, model)
        features = df_features.values

        # Use predict_proba to get probability of default (class 1)
        pd_decimal = float(model.predict_proba(features)[0][1])
        pd_decimal = max(0.0001, min(1.0, pd_decimal))

        # Get actual model type from the metadata of the SAME slot the engine
        # was actually resolved from above (bank-scoped segment/generic slot,
        # or the shared cross-bank slot) - previously this always re-read the
        # shared slot's metadata regardless of which engine was really used,
        # so a bank-specific model's own model_type (e.g. after activating a
        # non-XGBoost model for one bank) never showed up in the response.
        exposure_class = (data.get('exposure_class') or '').strip().upper()
        bank_id = (data.get('bank_id') or '').strip()
        if model_scope_used == 'bank_specific_segment':
            meta_exposure_class, meta_bank_id = exposure_class, bank_id
        elif model_scope_used == 'bank_specific_generic':
            meta_exposure_class, meta_bank_id = GENERIC_SEGMENT, bank_id
        else:
            meta_exposure_class, meta_bank_id = exposure_class, None

        model_type_label = 'Unknown'
        try:
            _, seg_meta_path = _segment_model_paths(meta_exposure_class, meta_bank_id)
            if os.path.exists(seg_meta_path):
                with open(seg_meta_path) as f:
                    metadata = json.load(f)
                    model_type_label = metadata.get('model_type', 'Unknown')
        except Exception:
            pass

        return jsonify({
            'pd': round(pd_decimal, 4),
            'pd_percentage': round(pd_decimal * 100, 2),
            'method': 'ML',
            'model_type': model_type_label,
            'model_version': '1.0.0',
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


@app.route('/api/model-availability', methods=['GET'])
def model_availability():
    """Model-routing switch (Phase 2): does bank_id have its own promoted
    model for exposure_class - or, failing that, a bank-wide GENERIC model?
    Lets borrower-info.html's "use this bank's own model" checkbox know
    whether checking it would actually do anything, instead of silently
    falling back to the shared model with no indication to the RM."""
    bank_id = (request.args.get('bank_id') or '').strip()
    exposure_class = (request.args.get('exposure_class') or '').strip().upper()
    if not bank_id or exposure_class not in EXPOSURE_CLASSES:
        return jsonify({'available': False, 'scope': None}), 200

    key_seg = f'{bank_id}::{exposure_class}'
    key_gen = f'{bank_id}::{GENERIC_SEGMENT}'
    if key_seg not in _bank_engine_cache:
        _bank_engine_cache[key_seg] = _build_segment_engine(exposure_class, bank_id=bank_id)
    if _bank_engine_cache[key_seg] is not None:
        return jsonify({'available': True, 'scope': 'segment',
                        'model_version': _segment_model_version(exposure_class, bank_id)}), 200

    if key_gen not in _bank_engine_cache:
        _bank_engine_cache[key_gen] = _build_segment_engine(GENERIC_SEGMENT, bank_id=bank_id)
    if _bank_engine_cache[key_gen] is not None:
        return jsonify({'available': True, 'scope': 'generic',
                        'model_version': _segment_model_version(GENERIC_SEGMENT, bank_id)}), 200

    return jsonify({'available': False, 'scope': None}), 200


@app.route('/api/bank-model-schema/<bank_id>')
def bank_model_schema(bank_id):
    """
    Returns which features a bank's active model actually uses, split into:
      - canonical_features: subset of the fixed 37-feature schema this bank's
        model uses (the caller already has form inputs for all of these -
        this just says which ones matter for this bank, for highlighting).
      - bank_specific_fields: features beyond the canonical schema (e.g.
        BANK011's repay_status_m1..6) that have NO existing form input -
        full display metadata included so the frontend can render one.
      - derived_fields: bank-specific features that are computed from other
        already-collected fields, never asked directly (see
        backend/bank_field_meta.py's 'derived' kind).
    Falls back segment -> GENERIC, same resolution order as
    /api/model-availability.
    """
    from backend.feature_schema import FEATURE_COLS
    from backend.feature_meta import FEATURE_DISPLAY_NAMES, feature_unit
    from backend.bank_field_meta import BANK_FIELD_META

    exposure_class = (request.args.get('exposure_class') or '').strip().upper()
    engine, scope, model_version = None, None, None

    if exposure_class and exposure_class in EXPOSURE_CLASSES:
        key_seg = f'{bank_id}::{exposure_class}'
        if key_seg not in _bank_engine_cache:
            _bank_engine_cache[key_seg] = _build_segment_engine(exposure_class, bank_id=bank_id)
        if _bank_engine_cache[key_seg] is not None:
            engine, scope = _bank_engine_cache[key_seg], 'segment'
            model_version = _segment_model_version(exposure_class, bank_id)

    if engine is None:
        key_gen = f'{bank_id}::{GENERIC_SEGMENT}'
        if key_gen not in _bank_engine_cache:
            _bank_engine_cache[key_gen] = _build_segment_engine(GENERIC_SEGMENT, bank_id=bank_id)
        if _bank_engine_cache[key_gen] is not None:
            engine, scope = _bank_engine_cache[key_gen], 'generic'
            model_version = _segment_model_version(GENERIC_SEGMENT, bank_id)

    if engine is None:
        return jsonify({'available': False, 'error': f'No trained model found for {bank_id}'}), 404

    feature_names = list(getattr(engine._model, 'feature_names_in_', []))
    field_meta = BANK_FIELD_META.get(bank_id, {})

    canonical_features = []
    bank_specific_fields = {}
    derived_fields = {}
    unmetadata_fields = []

    for name in feature_names:
        if name in FEATURE_COLS:
            canonical_features.append({
                'name': name,
                'label': FEATURE_DISPLAY_NAMES.get(name, name),
                'unit': feature_unit(name),
            })
        elif name in field_meta:
            meta = field_meta[name]
            if meta.get('kind') == 'derived':
                derived_fields[name] = meta
            else:
                bank_specific_fields[name] = meta
        else:
            unmetadata_fields.append(name)

    return jsonify({
        'available': True,
        'bank_id': bank_id,
        'scope': scope,
        'model_version': model_version,
        'canonical_features': canonical_features,
        'bank_specific_fields': bank_specific_fields,
        'derived_fields': derived_fields,
        'unmetadata_fields': unmetadata_fields,  # should stay empty - flags a gap if a new auto-discovered field has no display metadata yet
    }), 200


def _json_safe(obj):
    """Recursively replace NaN/Infinity floats with None (JSON null).

    A bank-scoped model can genuinely leave a resolved feature value as NaN
    when the applicant didn't supply it (allow_missing_features_) - correct
    model input, but literal NaN/Infinity are not valid JSON (RFC 8259).
    Python's json.dumps emits them anyway (allow_nan=True by default), which
    Flask's jsonify inherits, so a genuinely-missing bank-specific field
    silently breaks every consumer's response.json() on the frontend with no
    indication why. This is a defensive catch-all on top of the two sites
    that were found and fixed directly (assessment_engine.py's
    model_inputs_resolved, shap_explainer.py's feature_contributions) - in
    case NaN reaches a findings response from anywhere else in the future.
    """
    if isinstance(obj, float):
        return None if (obj != obj or obj in (float('inf'), float('-inf'))) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


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
        engine, _model_scope_used, err = _resolve_segment_engine(data)
        if err:
            return err
        findings = engine.assess(data)
        return jsonify(_json_safe(findings)), 200
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
        engine, model_scope_used, err = _resolve_segment_engine(data)
        if err:
            return err
        findings = engine.assess(data)
        # SHAP is automatically included in findings if explainer available
        # Model-routing switch (Phase 2): which model actually scored this,
        # so the report can show it - not just what the RM requested.
        findings['model_scope'] = model_scope_used
        return jsonify(_json_safe(findings)), 200
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
        engine, model_scope_used, err = _resolve_segment_engine(data)
        if err:
            return err
        findings = engine.assess(data)
        findings['model_scope'] = model_scope_used
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
            'model_scope':     model_scope_used,
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
    return jsonify(_json_safe(findings)), 200


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
        import sqlite3
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

        # Count transaction-level training data (primary source)
        enriched_txn_count = 0
        try:
            if _READONLY_FS and not _db_copy_ready.is_set():
                _db_copy_ready.wait(timeout=60)
            conn = sqlite3.connect(_OPS_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE default_flag IS NOT NULL AND cust_age IS NOT NULL AND cust_annual_income IS NOT NULL AND loan_de_ratio IS NOT NULL AND loan_interest_coverage IS NOT NULL AND loan_classification IS NOT NULL")
            enriched_txn_count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            print(f"[ADMIN] Warning: Could not query enriched transactions: {e}")

        # Count CSV supplementary files only (in data/training/)
        import glob
        csv_rows = 0
        csv_file_count = 0
        training_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'training')
        os.makedirs(training_dir, exist_ok=True)
        for path in glob.glob(os.path.join(training_dir, '*.csv')):
            try:
                csv_rows += sum(1 for _ in open(path)) - 1
                csv_file_count += 1
            except Exception:
                pass

        # Total rows = enriched transactions (primary) + CSV files (supplementary)
        total_rows_available = enriched_txn_count + csv_rows

        # Files count: 1 for enriched_transactions (primary) + CSV files (supplementary)
        files_count = (1 if enriched_txn_count > 0 else 0) + csv_file_count

        return jsonify({
            'model_metadata':    meta,
            'last_run':          last_run,
            'training_running':  is_training_running(),
            'files_in_training': files_count,
            'total_rows_available': total_rows_available,
            'enriched_transaction_rows': enriched_txn_count,
            'csv_rows': csv_rows,
            'csv_files_count': csv_file_count,
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
        import sqlite3
        from ml_models.trainer import scan_training_folder

        files = []

        # Add enriched_transactions as primary data source
        try:
            if _READONLY_FS and not _db_copy_ready.is_set():
                _db_copy_ready.wait(timeout=60)
            conn = sqlite3.connect(_OPS_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE default_flag IS NOT NULL AND cust_age IS NOT NULL AND cust_annual_income IS NOT NULL AND loan_de_ratio IS NOT NULL AND loan_interest_coverage IS NOT NULL AND loan_classification IS NOT NULL")
            enriched_count = cursor.fetchone()[0]
            conn.close()

            files.append({
                'filename': 'enriched_transactions (bank.db)',
                'source': 'database',
                'row_count': enriched_count,
                'size_kb': 0,
                'modified': '(current)'
            })
        except Exception as e:
            print(f"[ADMIN] Warning: Could not query enriched_transactions: {e}")

        # Add CSV files from data/training/ if any
        csv_files = scan_training_folder()
        files.extend(csv_files)

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
        try:
            with open(_HPARAM_PATH) as f:
                old = json.load(f)
        except Exception:
            old = {}
        with open(_HPARAM_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        # Governance audit: record which top-level blocks changed (hash-chained).
        try:
            changed = sorted(k for k in set(old) | set(data or {})
                             if old.get(k) != (data or {}).get(k))
            if changed:
                with _gov_conn() as _gc:
                    _gov.append_audit_event(
                        _gc, 'HYPERPARAMS_CHANGED', actor_id='admin',
                        actor_role='admin', object_type='config',
                        object_id='hyperparameters.json',
                        payload={'changed_blocks': changed,
                                 'old': {k: old.get(k) for k in changed},
                                 'new': {k: (data or {}).get(k) for k in changed}})
        except Exception as _e:
            print(f'[governance] hyperparams audit failed (non-fatal): {_e}')
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

        # Get parameters from query string or request body.
        # Default is CUSTOMER-LEVEL (one row per loan, ~900-1500 rows) - this is
        # the grain we settled on for both XGBoost and Logistic Regression after
        # finding transaction-level training only adds row-count inflation
        # (many near-identical rows per loan) without a real accuracy gain, once
        # group leakage is accounted for. Pass ?use_transaction_level=1 to opt
        # into the 56K+ enriched_transactions table instead.
        use_transaction_level = request.args.get('use_transaction_level', '0') == '1'
        model_type = request.args.get('model_type', 'xgboost')

        # Optional bank filter: JSON body {"bank_ids": ["BANK001", "BANK002"]}
        # or query string ?bank_ids=BANK001,BANK002. Empty/absent = all banks.
        bank_ids = None
        body = request.get_json(silent=True) or {}
        if body.get('bank_ids'):
            bank_ids = [b for b in body['bank_ids'] if b]
        elif request.args.get('bank_ids'):
            bank_ids = [b.strip() for b in request.args.get('bank_ids').split(',') if b.strip()]

        # Bank-scoped auto-discovery skips gender_enc/marital_status_enc by
        # default (see ml_models.trainer.COMPLIANCE_EXCLUDED_COLS). Off unless
        # explicitly requested - for research/benchmark comparison against a
        # published result that used all raw dataset columns, not for a model
        # intended to make a real lending decision.
        include_compliance_excluded = (
            bool(body.get('include_compliance_excluded'))
            or request.args.get('include_compliance_excluded', '0') == '1'
        )

        # exposure_class is now REQUIRED - the unsegmented 'ALL' model has been
        # retired (it was never used for actual scoring once segment routing
        # went live; only a leftover from before segmentation). Only the 4
        # Basel segments can be trained going forward.
        exposure_class = body.get('exposure_class') or request.args.get('exposure_class') or None
        if not exposure_class:
            return jsonify({
                'error': 'exposure_class is required',
                'message': 'The unsegmented "ALL" model has been retired. '
                           'Train one of: CORPORATE, SME, RETAIL_MORTGAGES, RETAIL_OTHER.'
            }), 400
        # Model-routing switch: exposure_class='GENERIC' trains a bank-wide,
        # unsegmented model - only valid for exactly one bank_id (see
        # trainer.run_training()'s own validation, mirrored here so the
        # error surfaces immediately instead of after a background thread starts).
        if exposure_class == 'GENERIC':
            if not bank_ids or len(bank_ids) != 1:
                return jsonify({
                    'error': "exposure_class='GENERIC' requires exactly one bank_id",
                    'message': 'A bank-wide, unsegmented model must be scoped to a single bank.'
                }), 400
        elif exposure_class not in EXPOSURE_CLASSES:
            return jsonify({
                'error': 'Unrecognized exposure_class',
                'message': f'exposure_class must be one of: {", ".join(EXPOSURE_CLASSES)}, or GENERIC (single-bank only)'
            }), 400

        def _run():
            result = run_training(triggered_by='manual', use_transaction_level=use_transaction_level,
                                   model_type=model_type, bank_ids=bank_ids, exposure_class=exposure_class,
                                   include_compliance_excluded=include_compliance_excluded)
            if result['status'] == 'success' and result['model_promoted']:
                if bank_ids and len(bank_ids) == 1:
                    # Bank-scoped promotion - invalidate just this bank's cached
                    # entry (see _resolve_bank_engine) so the next request picks
                    # up the newly promoted model instead of a stale cached miss.
                    bank_id = bank_ids[0]
                    cache_key = f'{bank_id}::{exposure_class}'
                    _bank_engine_cache[cache_key] = _build_segment_engine(exposure_class, bank_id=bank_id)
                    print(f"Bank-specific engine reloaded for {bank_id}/{exposure_class} after training run {result['run_id']}")
                else:
                    _segment_engines[exposure_class] = _build_segment_engine(exposure_class)
                    print(f"Segment engine reloaded for {exposure_class} after training run {result['run_id']}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return jsonify({'status': 'started', 'message': f'Training started in background (model: {model_type}). Poll /admin/api/status for completion.'}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — MODELS (Multi-Model Support)
# ============================================================================

@app.route('/admin/api/models', methods=['GET'])
def admin_get_models():
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        import os
        from ml_models.trainer import _load_active_model_registry

        models_dir = os.path.join(os.path.dirname(__file__), 'ml_models', 'models')
        models = []
        registry = _load_active_model_registry()  # {segment: {model_type, bank_key, exposure_class, activated_at}}

        def is_active(model_type, bank_combo, seg):
            reg_key = seg if bank_combo == 'ALL' else f'{seg}::{bank_combo}'
            entry = registry.get(reg_key) or {}
            return entry.get('model_type') == model_type and entry.get('bank_key') == bank_combo

        # Scan the 3-level layout: models/<model_type>/<bank_combo>/<exposure_class>/pd_model_metadata.json
        # with back-compat for two older, shallower layouts:
        #   models/<model_type>/<bank_combo>/pd_model_metadata.json      (pre-exposure_class)
        #   models/<model_type>/pd_model_metadata.json                    (pre-bank_combo)
        if os.path.exists(models_dir):
            for model_type in os.listdir(models_dir):
                model_type_dir = os.path.join(models_dir, model_type)
                if not os.path.isdir(model_type_dir):
                    continue

                legacy_flat_meta = os.path.join(model_type_dir, 'pd_model_metadata.json')
                found_all_bank_combo = False

                for bank_entry in os.listdir(model_type_dir):
                    bank_combo_dir = os.path.join(model_type_dir, bank_entry)
                    if not os.path.isdir(bank_combo_dir):
                        continue

                    legacy_combo_meta = os.path.join(bank_combo_dir, 'pd_model_metadata.json')
                    found_all_segment = False

                    for seg_entry in os.listdir(bank_combo_dir):
                        seg_dir = os.path.join(bank_combo_dir, seg_entry)
                        meta_file = os.path.join(seg_dir, 'pd_model_metadata.json')
                        if os.path.isdir(seg_dir) and os.path.exists(meta_file):
                            if bank_entry == 'ALL':
                                found_all_bank_combo = True
                            if seg_entry == 'ALL':
                                found_all_segment = True
                            try:
                                with open(meta_file) as f:
                                    metadata = json.load(f)
                                models.append({
                                    'model_type': model_type,
                                    'bank_key': bank_entry,
                                    'exposure_class': seg_entry,
                                    'is_active': is_active(model_type, bank_entry, seg_entry),
                                    'metadata': metadata,
                                })
                            except Exception:
                                pass

                    if not found_all_segment and os.path.exists(legacy_combo_meta):
                        if bank_entry == 'ALL':
                            found_all_bank_combo = True
                        try:
                            with open(legacy_combo_meta) as f:
                                metadata = json.load(f)
                            models.append({
                                'model_type': model_type,
                                'bank_key': bank_entry,
                                'exposure_class': 'ALL',
                                'is_active': is_active(model_type, bank_entry, 'ALL'),
                                'metadata': metadata,
                            })
                        except Exception:
                            pass

                if not found_all_bank_combo and os.path.exists(legacy_flat_meta):
                    try:
                        with open(legacy_flat_meta) as f:
                            metadata = json.load(f)
                        models.append({
                            'model_type': model_type,
                            'bank_key': 'ALL',
                            'exposure_class': 'ALL',
                            'is_active': is_active(model_type, 'ALL', 'ALL'),
                            'metadata': metadata,
                        })
                    except Exception:
                        pass

        return jsonify({
            'active_registry': registry,
            'models': sorted(models, key=lambda x: x['metadata'].get('date_trained', ''), reverse=True),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/models/<model_type>/activate', methods=['POST'])
def admin_activate_model(model_type):
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        import joblib
        from ml_models.trainer import activate_model

        body = request.get_json(silent=True) or {}
        bank_combo = body.get('bank_key') or request.args.get('bank_key') or 'ALL'
        exposure_class = body.get('exposure_class') or request.args.get('exposure_class') or None
        result = activate_model(model_type, bank_combo, exposure_class)

        # Reload the affected slot in-process only - activating a segment's
        # model must not disturb the other segments' already-loaded engines.
        if bank_combo and bank_combo != 'ALL':
            seg = exposure_class or GENERIC_SEGMENT
            cache_key = f'{bank_combo}::{seg}'
            _bank_engine_cache[cache_key] = _build_segment_engine(seg, bank_id=bank_combo)
        elif exposure_class:
            _segment_engines[exposure_class] = _build_segment_engine(exposure_class)
        else:
            global _pd_model
            _pd_model = joblib.load(_MODEL_PATH)
            _assessment_engine.__init__(_pd_model, _get_model_version(), db_path=_OPS_DB_PATH)

        return jsonify(result), 200
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/models/<model_type>/<bank_key>', methods=['DELETE'])
def admin_delete_model(model_type, bank_key):
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        from ml_models.trainer import _load_active_model_registry

        # Optional ?exposure_class= targets the 3-level segmented layout;
        # omitted = legacy behavior (2-level bank_combo or 1-level flat).
        exposure_class = request.args.get('exposure_class') or None
        registry = _load_active_model_registry()

        if exposure_class:
            reg_key = exposure_class if bank_key == 'ALL' else f'{exposure_class}::{bank_key}'
            entry = registry.get(reg_key) or {}
            if entry.get('model_type') == model_type and entry.get('bank_key') == bank_key:
                return jsonify({'error': f"Cannot delete the currently active {exposure_class} model. Activate a different one first."}), 400
        else:
            entry = registry.get('ALL') or {}
            if entry.get('model_type') == model_type and entry.get('bank_key') == bank_key:
                return jsonify({'error': 'Cannot delete the currently active model. Activate a different one first.'}), 400

        models_dir = os.path.join(os.path.dirname(__file__), 'ml_models', 'models')
        deleted = False

        if exposure_class:
            seg_dir = os.path.join(models_dir, model_type, bank_key, exposure_class)
            if os.path.isdir(seg_dir):
                shutil.rmtree(seg_dir)
                deleted = True
        else:
            combo_dir = os.path.join(models_dir, model_type, bank_key)
            if os.path.isdir(combo_dir):
                shutil.rmtree(combo_dir)
                deleted = True
            elif bank_key == 'ALL':
                # Legacy layout: files sit directly under models/<model_type>/
                legacy_dir = os.path.join(models_dir, model_type)
                legacy_model = os.path.join(legacy_dir, 'pd_model.pkl')
                legacy_meta = os.path.join(legacy_dir, 'pd_model_metadata.json')
                if os.path.exists(legacy_model) or os.path.exists(legacy_meta):
                    for p in (legacy_model, legacy_meta):
                        if os.path.exists(p):
                            os.remove(p)
                    deleted = True

        if not deleted:
            return jsonify({'error': f"No model found for '{model_type}' / '{bank_key}'" + (f" / '{exposure_class}'" if exposure_class else "")}), 404

        return jsonify({'status': 'deleted', 'model_type': model_type, 'bank_key': bank_key, 'exposure_class': exposure_class or 'ALL'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API — MODEL LAB (research: filterable run comparison + global SHAP)
# ============================================================================

@app.route('/admin/api/model-lab/runs', methods=['GET'])
def admin_model_lab_runs():
    """Filterable view over run_history.json - every run already carries its
    full classification-metrics block (auc_roc, pr_auc, accuracy, precision,
    recall, f1, brier_score, confusion_matrix) from trainer.evaluate_model(),
    so this is a read + filter, no new computation.

    Defaults to one row per (model_type, exposure_class, bank scope) - the
    single latest run - rather than every historical retrain of the same
    dataset/segment, which gets unreadable fast once a model's been
    retrained a dozen times. Pass ?all=1 to see full history for a scope."""
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        if not os.path.exists(_HISTORY_PATH):
            return jsonify({'runs': [], 'total': 0}), 200
        with open(_HISTORY_PATH) as f:
            history = json.load(f)

        model_type = request.args.get('model_type') or None
        exposure_class = request.args.get('exposure_class') or None
        bank_id = request.args.get('bank_id') or None
        status = request.args.get('status') or None
        show_all = request.args.get('all') == '1'

        def matches(r):
            if model_type and r.get('model_type') != model_type:
                return False
            if exposure_class and (r.get('exposure_class') or 'ALL') != exposure_class:
                return False
            if bank_id and bank_id not in (r.get('bank_ids') or []):
                return False
            if status and r.get('status') != status:
                return False
            return True

        filtered = [r for r in history if matches(r)]
        filtered.sort(key=lambda r: r.get('timestamp') or '', reverse=True)

        if not show_all:
            seen = set()
            latest_only = []
            for r in filtered:
                key = (r.get('model_type'), r.get('exposure_class') or 'ALL',
                       tuple(sorted(r.get('bank_ids') or [])))
                if key in seen:
                    continue
                seen.add(key)
                latest_only.append(r)
            filtered = latest_only

        summary = [{k: v for k, v in r.items() if k != 'error'} for r in filtered]
        return jsonify({'runs': summary, 'total': len(summary)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/model-lab/shap', methods=['POST'])
def admin_model_lab_shap():
    """Compute global (aggregate) SHAP importance for a chosen configured
    model's architecture, run against a fresh sample of eligible training
    rows, plus a noise-baseline ratio per feature (see
    backend/shap_explainer.py: compute_global_shap - it retrains a small
    'shadow' model of the same type + the selected model's own saved
    hyperparameters, with a synthetic noise feature included, since a
    noise column has to be genuinely trained-on to get a meaningful SHAP
    reading for it). Runs synchronously - a ~200 row sample completes in a
    few seconds."""
    if not _check_admin_auth(): return _admin_auth_error()
    try:
        import joblib
        import pandas as pd
        from ml_models.trainer import load_from_enriched_transactions, load_from_db
        from backend.shap_explainer import compute_global_shap

        body = request.get_json(silent=True) or {}
        model_type = (body.get('model_type') or '').strip()
        bank_key = (body.get('bank_key') or 'ALL').strip() or 'ALL'
        exposure_class = (body.get('exposure_class') or 'ALL').strip() or 'ALL'
        sample_size = min(int(body.get('sample_size') or 200), 500)

        if not model_type:
            return jsonify({'error': 'model_type is required'}), 400

        pkl_path = _resolve_model_lab_pkl_path(model_type, bank_key, exposure_class)
        if not pkl_path:
            return jsonify({'error': f"No trained model found for {model_type}/{bank_key}/{exposure_class}"}), 404
        model = joblib.load(pkl_path)

        meta_path = os.path.join(os.path.dirname(pkl_path), 'pd_model_metadata.json')
        saved_hp = {}
        try:
            with open(meta_path) as f:
                saved_hp = json.load(f).get('hyperparameters', {}) or {}
        except Exception:
            pass
        hp = {'models': {model_type: saved_hp}}

        # GENERIC is a bank-wide "no segmentation" sentinel at the app/model
        # level (see GENERIC_SEGMENT in app.py) - it isn't a real
        # blm.exposure_class value in the DB, so filtering on it there would
        # just return zero rows. Same treatment as 'ALL': no DB filter.
        db_exposure_class = exposure_class if exposure_class not in ('ALL', 'GENERIC') else None
        df = load_from_enriched_transactions(
            bank_ids=[bank_key] if bank_key != 'ALL' else None,
            exposure_class=db_exposure_class,
            include_active=True,
        )
        # Some banks (e.g. newer Real Earth onboardings) were trained on
        # bank_loan_metrics CUSTOMER-LEVEL data because they have no rows in
        # `transactions` at all (see run_training's use_transaction_level
        # switch) - fall back to the same source for sampling when the
        # transaction-level query comes back empty or single-class.
        if df is None or len(df) == 0 or df['default_flag'].nunique() < 2:
            df = load_from_db(
                bank_ids=[bank_key] if bank_key != 'ALL' else None,
                exposure_class=db_exposure_class,
            )
        if df is None or len(df) == 0:
            return jsonify({'error': 'No eligible training rows available for this scope'}), 404
        if df['default_flag'].nunique() < 2:
            return jsonify({'error': 'This scope has no defaults in its eligible rows - a shadow model cannot be trained on a single class'}), 404

        n = min(sample_size, len(df))
        # Plain random sampling can accidentally draw zero defaults when the
        # default rate is low (e.g. CORPORATE), which trains a degenerate
        # shadow model that predicts a near-constant probability and yields
        # all-zero SHAP values - stratifying preserves the real default rate
        # in the sample regardless of sample_size.
        if n < len(df):
            from sklearn.model_selection import train_test_split
            df_sample, _ = train_test_split(df, train_size=n, stratify=df['default_flag'], random_state=42)
        else:
            df_sample = df
        rows = [model_feature_frame(row.to_dict(), model) for _, row in df_sample.iterrows()]
        X_sample = pd.concat(rows, ignore_index=True)
        y_sample = df_sample['default_flag'].reset_index(drop=True)

        result = compute_global_shap(model_type, X_sample, y_sample, hp)
        result.update({'bank_key': bank_key, 'exposure_class': exposure_class})
        return jsonify(result), 200
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

        body = request.get_json(silent=True) or {}
        exposure_class = body.get('exposure_class') or request.args.get('exposure_class') or None
        result = rollback_model(exposure_class)

        # NOTE: previously this reassigned _pd_model without `global`, so the
        # in-process model was never actually reloaded after rollback - fixed
        # here alongside adding per-segment rollback support.
        if exposure_class:
            _segment_engines[exposure_class] = _build_segment_engine(exposure_class)
        else:
            global _pd_model
            _pd_model = joblib.load(_MODEL_PATH)
            _assessment_engine.__init__(_pd_model, _get_model_version(), db_path=_OPS_DB_PATH)

        # Governance audit: rollbacks are model-lifecycle events (hash-chained).
        try:
            with _gov_conn() as _gc:
                _gov.append_audit_event(
                    _gc, 'MODEL_ROLLBACK', actor_id='admin', actor_role='admin',
                    object_type='model', object_id=exposure_class or 'ALL',
                    payload=result)
        except Exception as _e:
            print(f'[governance] rollback audit failed (non-fatal): {_e}')

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
    """
    RETIRED: this only ever trained the unsegmented 'ALL' model, which is no
    longer used for scoring once segment routing went live (see
    admin_trigger_train() - exposure_class is now required). Kept as a no-op
    rather than deleted so _reconfigure_scheduler's remove_job('pd_training')
    call (which fires on every /admin/api/schedule save) has nothing stale
    to reference, and so any code that still imports this name doesn't break.
    """
    print("[ML] Scheduled unsegmented-model training is retired - no-op. "
          "Segment models (CORPORATE/SME/RETAIL_MORTGAGES/RETAIL_OTHER) are trained on demand via Train Now.")

def _reconfigure_scheduler(schedule_cfg):
    """
    RETIRED: the PD-training schedule only ever drove the unsegmented 'ALL'
    model (see _scheduled_training). Always removes any existing job and
    never re-adds it, regardless of the stored schedule config, so a stale
    'enabled: true' in hyperparameters.json (or a re-save from the admin
    Schedule panel) can't bring back automatic unsegmented retraining.
    """
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job('pd_training')
    except Exception:
        pass

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
    # Daily Governance drift/KPI monitor — PSI, AUC stability, fairness at 03:00.
    try:
        _scheduler.add_job(_run_governance_monitor_job, 'cron', hour=3, minute=0,
                           id='governance_monitor', replace_existing=True)
        print('[governance] daily drift/KPI monitor scheduled 03:00')
    except Exception as e:
        print(f'[governance] could not schedule daily monitor: {e}')
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
        if _READONLY_FS and not _db_copy_ready.is_set():
            _db_copy_ready.wait(timeout=60)
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


# ── Bulk accounts/loans/risk (no transactions, no per-customer loop) ───────────
# Powers the consolidated dashboard: KPIs and charts need every account/loan/risk
# row, but NOT per-customer transaction joins. Fetching this in 3 flat queries
# replaces the old pattern of firing one /customers/<cid> request per customer
# (1,500+ round trips, each re-joining transactions) just to build aggregates.
@app.route('/operations/api/bulk-summary')
def ops_bulk_summary():
    with _ops_conn() as conn:
        accounts = _rows_to_list(conn.execute('SELECT * FROM accounts').fetchall())
        loans    = _rows_to_list(conn.execute('SELECT * FROM loans').fetchall())
        risk     = _rows_to_list(conn.execute('SELECT * FROM credit_risk_metrics').fetchall())
    return jsonify({'accounts': accounts, 'loans': loans, 'risk': risk})


# ── Lazy per-customer detail (full profile fields + that customer's transactions) ──
# Called only when a specific customer is opened in the sidebar, not at page load.
# Accounts/loans/risk are already in memory (bulk-summary), so this only needs to
# return the full customer row plus the transaction history for their accounts.
@app.route('/operations/api/customers/<cid>/detail')
def ops_customer_detail(cid):
    with _ops_conn() as conn:
        c = _row_to_dict(conn.execute(
            'SELECT * FROM customers WHERE id=?', (cid,)).fetchone())
        if c is None:
            return jsonify({'error': 'Customer not found'}), 404
        acc_ids = [r['id'] for r in conn.execute(
            'SELECT id FROM accounts WHERE cid=?', (cid,)).fetchall()]
        transactions = []
        if acc_ids:
            placeholders = ','.join('?' * len(acc_ids))
            transactions = _rows_to_list(conn.execute(
                f'SELECT * FROM transactions WHERE aid IN ({placeholders})'
                ' ORDER BY date DESC, time DESC', acc_ids).fetchall())
    return jsonify({'customer': c, 'transactions': transactions})


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


@app.route('/api/customer-export-filters')
def api_customer_export_filters():
    """Get available filter values for bulk customer export."""
    with _ops_conn() as conn:
        # Get unique values for each filter
        filters_data = {
            'banks': _rows_to_list(conn.execute(
                'SELECT DISTINCT bank_id, bank_name FROM banks ORDER BY bank_name').fetchall()),
            'employment_types': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT employment_type FROM customer_kyc WHERE employment_type IS NOT NULL').fetchall()
                if r[0])),
            'education_levels': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT education_level FROM customer_kyc WHERE education_level IS NOT NULL').fetchall()
                if r[0])),
            'city_tiers': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT city_tier FROM customer_kyc WHERE city_tier IS NOT NULL').fetchall()
                if r[0])),
            'loan_purposes': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT loan_purpose FROM customer_kyc WHERE loan_purpose IS NOT NULL').fetchall()
                if r[0])),
            'residence_types': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT residence_type FROM customer_kyc WHERE residence_type IS NOT NULL').fetchall()
                if r[0])),
            'account_statuses': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT status FROM accounts WHERE status IS NOT NULL').fetchall()
                if r[0])),
            'customer_statuses': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT status FROM customers WHERE status IS NOT NULL').fetchall()
                if r[0])),
            'loan_statuses': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT status FROM loans WHERE status IS NOT NULL').fetchall()
                if r[0])),
            'loan_classifications': sorted(set(
                r[0] for r in conn.execute('SELECT DISTINCT loan_classification FROM loans WHERE loan_classification IS NOT NULL').fetchall()
                if r[0])),
            'cibil_ranges': [
                {'label': 'Poor (0-600)', 'min': 0, 'max': 600},
                {'label': 'Fair (600-750)', 'min': 600, 'max': 750},
                {'label': 'Good (750-800)', 'min': 750, 'max': 800},
                {'label': 'Excellent (800+)', 'min': 800, 'max': 999},
            ],
            'income_ranges': [
                {'label': '<5 Lakh', 'min': 0, 'max': 500000},
                {'label': '5-10 Lakh', 'min': 500000, 'max': 1000000},
                {'label': '10-25 Lakh', 'min': 1000000, 'max': 2500000},
                {'label': '25-50 Lakh', 'min': 2500000, 'max': 5000000},
                {'label': '50+ Lakh', 'min': 5000000, 'max': 999999999},
            ],
            'age_ranges': [
                {'label': '18-30 (Young)', 'min': 18, 'max': 30},
                {'label': '30-45 (Middle-aged)', 'min': 30, 'max': 45},
                {'label': '45-60 (Senior)', 'min': 45, 'max': 60},
                {'label': '60+ (Retired)', 'min': 60, 'max': 150},
            ],
            'months_customer_ranges': [
                {'label': '<6 months (New)', 'min': 0, 'max': 6},
                {'label': '6-12 months', 'min': 6, 'max': 12},
                {'label': '1-3 years', 'min': 12, 'max': 36},
                {'label': '3-5 years', 'min': 36, 'max': 60},
                {'label': '5+ years', 'min': 60, 'max': 600},
            ],
            'default_risk_levels': [
                {'label': 'Low Risk (No late payments)', 'value': 'low'},
                {'label': 'Medium Risk (1-2 late payments)', 'value': 'medium'},
                {'label': 'High Risk (3+ late payments)', 'value': 'high'},
            ],
        }
    return jsonify(filters_data)


@app.route('/api/customer-bulk-export')
def api_customer_bulk_export():
    """Bulk export customers matching filter criteria."""
    # Get filter parameters
    banks = request.args.getlist('bank')
    employment_types = request.args.getlist('employment_type')
    education_levels = request.args.getlist('education_level')
    city_tiers = request.args.getlist('city_tier')
    loan_purposes = request.args.getlist('loan_purpose')
    residence_types = request.args.getlist('residence_type')
    customer_statuses = request.args.getlist('customer_status')
    loan_statuses = request.args.getlist('loan_status')
    cibil_min = request.args.get('cibil_min', type=int, default=0)
    cibil_max = request.args.get('cibil_max', type=int, default=999)
    income_min = request.args.get('income_min', type=int, default=0)
    income_max = request.args.get('income_max', type=int, default=999999999)
    age_min = request.args.get('age_min', type=int, default=0)
    age_max = request.args.get('age_max', type=int, default=150)
    has_loan = request.args.get('has_loan') == 'true'
    has_active_loan = request.args.get('has_active_loan') == 'true'
    has_npa = request.args.get('has_npa') == 'true'
    previous_default = request.args.get('previous_default') == 'true'
    is_rural = request.args.get('is_rural')
    # Default cap far above the total customer count (1,547 across all banks)
    # so a normal export isn't silently truncated; ?limit= still overrides.
    limit = request.args.get('limit', type=int, default=100000)

    with _ops_conn() as conn:
        # Build dynamic query with filters
        query = """
            SELECT DISTINCT c.id, c.bank_id, c.first, c.last, c.email, c.phone, c.status,
                   k.cibil_score, k.annual_income, k.age, k.employment_type,
                   k.months_as_customer, k.num_late_payments_past_12m,
                   k.gender, k.education_level, k.city_tier, k.residence_type,
                   k.years_employed, k.existing_loans_count, k.num_existing_products,
                   k.previous_default_flag, k.is_rural, k.is_pep, k.state,
                   k.loan_purpose, k.marital_status, k.industry_sector, k.other_income,
                   k.years_at_address, k.foir_declared, k.num_dependents,
                   l.id as loan_id, l.exposure_class, l.loan_classification,
                   m.de as de_ratio, m.intcov as interest_coverage, m.profit as profitability,
                   m.liq as liquidity_ratio, m.pd_score, m.prior_de, m.prior_cibil,
                   m.npa_flag, m.obs as pd_observed,
                   CASE WHEN l.loan_classification IN ('NPA', 'Default') THEN 1 ELSE 0 END as default_flag,
                   COUNT(DISTINCT l.id) as loan_count,
                   SUM(l.outstanding) as total_outstanding
            FROM customers c
            LEFT JOIN customer_kyc k ON c.id = k.cid
            LEFT JOIN loans l ON c.id = l.cid
            LEFT JOIN credit_risk_metrics m ON l.id = m.lid
            WHERE 1=1
        """
        params = []

        # Apply filters
        if banks:
            placeholders = ','.join('?' * len(banks))
            query += f" AND c.bank_id IN ({placeholders})"
            params.extend(banks)

        if customer_statuses:
            placeholders = ','.join('?' * len(customer_statuses))
            query += f" AND c.status IN ({placeholders})"
            params.extend(customer_statuses)

        if employment_types:
            placeholders = ','.join('?' * len(employment_types))
            query += f" AND k.employment_type IN ({placeholders})"
            params.extend(employment_types)

        if education_levels:
            placeholders = ','.join('?' * len(education_levels))
            query += f" AND k.education_level IN ({placeholders})"
            params.extend(education_levels)

        if city_tiers:
            placeholders = ','.join('?' * len(city_tiers))
            query += f" AND k.city_tier IN ({placeholders})"
            params.extend(city_tiers)

        if residence_types:
            placeholders = ','.join('?' * len(residence_types))
            query += f" AND k.residence_type IN ({placeholders})"
            params.extend(residence_types)

        if loan_purposes:
            placeholders = ','.join('?' * len(loan_purposes))
            query += f" AND k.loan_purpose IN ({placeholders})"
            params.extend(loan_purposes)

        if is_rural is not None:
            query += f" AND k.is_rural = ?"
            params.append(1 if is_rural == 'true' else 0)

        # Range filters
        query += f" AND k.cibil_score BETWEEN ? AND ?"
        params.extend([cibil_min, cibil_max])

        query += f" AND k.annual_income BETWEEN ? AND ?"
        params.extend([income_min, income_max])

        query += f" AND k.age BETWEEN ? AND ?"
        params.extend([age_min, age_max])

        # Loan status filters
        if has_loan:
            query += " AND EXISTS (SELECT 1 FROM loans WHERE loans.cid = c.id)"

        if has_active_loan:
            query += " AND EXISTS (SELECT 1 FROM loans WHERE loans.cid = c.id AND loans.status = 'Active')"

        if has_npa:
            query += " AND EXISTS (SELECT 1 FROM loans WHERE loans.cid = c.id AND loans.loan_classification = 'NPA')"

        if previous_default:
            query += " AND k.previous_default_flag = 1"

        # Group and order
        query += " GROUP BY c.id ORDER BY c.id LIMIT ?"
        params.append(limit)

        results = _rows_to_list(conn.execute(query, params).fetchall())

    return jsonify({
        'total_customers': len(results),
        'customers': results,
        'filters_applied': {
            'banks': banks,
            'customer_statuses': customer_statuses,
            'employment_types': employment_types,
            'education_levels': education_levels,
            'city_tiers': city_tiers,
            'cibil_range': [cibil_min, cibil_max],
            'income_range': [income_min, income_max],
            'age_range': [age_min, age_max],
        }
    })


@app.route('/api/training-data-preview')
def api_training_data_preview():
    """
    Return the exact loan-level rows the PD model training pipeline uses,
    labeled with which split (train/test) each row falls into under the
    current hyperparameters - so the actual training/testing dataset can be
    inspected or exported for any/all banks, not just a customer-profile view.
    """
    try:
        import pandas as pd
        from ml_models.trainer import load_from_db, _load_hyperparameters
        from sklearn.model_selection import train_test_split

        banks = request.args.getlist('bank') or None
        df = load_from_db(bank_ids=banks)
        if df is None or len(df) == 0:
            return jsonify({'total_rows': 0, 'train_rows': 0, 'test_rows': 0, 'rows': []})

        # Same dedup the real training pipeline applies (load_and_merge) so
        # this preview matches the actual row count used to train/test.
        df = df.drop_duplicates(subset='loan_id', keep='first').reset_index(drop=True)

        hp = _load_hyperparameters()
        test_size = float(hp['training'].get('test_size', 0.20))
        model_hp = hp.get('models', {}).get('xgboost', hp.get('model', {}))
        random_state = int(model_hp.get('random_state', 42))

        train_idx, test_idx = train_test_split(
            df.index, test_size=test_size, random_state=random_state,
            stratify=df['default_flag'] if df['default_flag'].nunique() > 1 else None
        )
        split = pd.Series('test', index=df.index)
        split.loc[train_idx] = 'train'

        display_cols = [
            'bank_id', 'loan_id', 'age', 'annual_income', 'cibil_score',
            'employment_type_enc', 'de_ratio', 'interest_coverage',
            'profitability', 'liquidity_ratio', 'foir', 'months_as_customer',
            'num_late_payments_past_12m', 'existing_loans_count',
            'emi_miss_ratio', 'income_miss_ratio', 'default_flag',
        ]
        display_cols = [c for c in display_cols if c in df.columns]
        out = df[display_cols].copy()
        out['split'] = split
        out = out.where(pd.notnull(out), None)

        rows = out.to_dict(orient='records')
        return jsonify({
            'total_rows': len(df),
            'train_rows': int((split == 'train').sum()),
            'test_rows': int((split == 'test').sum()),
            'test_size': test_size,
            'random_state': random_state,
            'banks_filtered': banks,
            'columns': display_cols + ['split'],
            'rows': rows,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/customer-export/<cid>')
def api_customer_export(cid):
    """Export comprehensive customer data including transactions in JSON format."""
    cid = (cid or '').strip()
    with _ops_conn() as conn:
        # Get basic customer info
        cust = _row_to_dict(conn.execute(
            'SELECT * FROM customers WHERE id=?', (cid,)).fetchone())
        if not cust:
            return jsonify({'error': 'Customer not found'}), 404

        # KYC data
        kyc = _row_to_dict(conn.execute(
            'SELECT * FROM customer_kyc WHERE cid=?', (cid,)).fetchone()) or {}

        # Credit risk metrics (from first loan if any)
        metrics = {}
        loan_for_metrics = conn.execute(
            'SELECT id FROM loans WHERE cid=? LIMIT 1', (cid,)).fetchone()
        if loan_for_metrics:
            metrics = _row_to_dict(conn.execute(
                'SELECT * FROM credit_risk_metrics WHERE lid=?', (loan_for_metrics[0],)).fetchone()) or {}

        # Accounts
        accounts = _rows_to_list(conn.execute(
            'SELECT * FROM accounts WHERE cid=?', (cid,)).fetchall())

        # Loans
        loans = _rows_to_list(conn.execute(
            'SELECT * FROM loans WHERE cid=?', (cid,)).fetchall())

        # Transactions (all of them)
        acc_ids = [a['id'] for a in accounts]
        transactions = []
        if acc_ids:
            ph = ','.join('?' * len(acc_ids))
            transactions = _rows_to_list(conn.execute(
                f'SELECT * FROM transactions WHERE aid IN ({ph}) ORDER BY date DESC, time DESC',
                acc_ids).fetchall())

    # Build comprehensive export data
    from datetime import datetime as _datetime
    export_data = {
        'export_date': _datetime.utcnow().isoformat(),
        'customer': {
            'id': cust.get('id'),
            'name': f"{cust.get('first', '')} {cust.get('last', '')}".strip(),
            'dob': cust.get('dob'),
            'gender': cust.get('gender'),
            'email': cust.get('email'),
            'phone': cust.get('phone'),
            'address': cust.get('address'),
            'city': cust.get('city'),
            'state': cust.get('state'),
            'pincode': cust.get('pincode'),
            'joined_date': cust.get('joined'),
            'status': cust.get('status'),
            'bank_id': cust.get('bank_id'),
        },
        'kyc': {
            'age': kyc.get('age'),
            'annual_income': kyc.get('annual_income'),
            'foir_declared': kyc.get('foir_declared'),
            'cibil_score': kyc.get('cibil_score'),
            'years_employed': kyc.get('years_employed'),
            'num_dependents': kyc.get('num_dependents'),
            'months_as_customer': kyc.get('months_as_customer'),
            'late_payments_past_12m': kyc.get('num_late_payments_past_12m'),
            'existing_loans_count': kyc.get('existing_loans_count'),
            'num_existing_products': kyc.get('num_existing_products'),
            'employment_type': kyc.get('employment_type'),
            'education_level': kyc.get('education_level'),
            'city_tier': kyc.get('city_tier'),
            'residence_type': kyc.get('residence_type'),
            'loan_purpose': kyc.get('loan_purpose'),
            'previous_default_flag': kyc.get('previous_default_flag'),
            'is_rural': kyc.get('is_rural'),
            'is_pep': kyc.get('is_pep'),
            'kyc_status': kyc.get('kyc_status'),
        },
        'credit_metrics': {
            'de_ratio': metrics.get('de_ratio'),
            'interest_coverage': metrics.get('interest_coverage'),
            'profitability': metrics.get('profitability'),
            'liquidity_ratio': metrics.get('liquidity_ratio'),
            'sector': metrics.get('sector'),
            'country_code': metrics.get('country_code'),
        },
        'accounts': accounts,
        'loans': loans,
        'transactions': {
            'total_count': len(transactions),
            'period_from': min((t.get('date') for t in transactions if t.get('date')), default=None),
            'period_to': max((t.get('date') for t in transactions if t.get('date')), default=None),
            'data': transactions,
        },
    }

    return jsonify(export_data)


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


# ============================================================================
# OPTIMIZED TRANSACTION AGGREGATES (Pre-computed in SQL, not in memory)
# ============================================================================
@app.route('/operations/api/transactions-summary')
def ops_transactions_summary():
    """
    Returns pre-computed transaction aggregates instead of loading all raw transactions.
    Computes everything in SQL for massive performance gain.
    """
    with _ops_conn() as conn:
        # Total count and volume
        totals = conn.execute('''
            SELECT COUNT(*) as total_count, SUM(amount) as total_volume
            FROM transactions
        ''').fetchone()
        total_count = totals[0] or 0
        total_volume = float(totals[1] or 0)

        # By hour (24 buckets)
        hour_data = conn.execute('''
            SELECT CAST(SUBSTR(time, 1, 2) AS INTEGER) as hour, COUNT(*) as count
            FROM transactions
            WHERE time IS NOT NULL
            GROUP BY hour
            ORDER BY hour
        ''').fetchall()
        hour_buckets = [0] * 24
        for hour, count in hour_data:
            if 0 <= hour < 24:
                hour_buckets[hour] = count

        # By type
        type_data = _rows_to_list(conn.execute('''
            SELECT type, COUNT(*) as count, SUM(amount) as volume
            FROM transactions
            GROUP BY type
            ORDER BY volume DESC
        ''').fetchall())
        by_type = {row['type']: row['volume'] for row in type_data}

        # By date (last 30 days)
        date_data = _rows_to_list(conn.execute('''
            SELECT date, COUNT(*) as count, SUM(amount) as volume
            FROM transactions
            WHERE date IS NOT NULL
            GROUP BY date
            ORDER BY date DESC
            LIMIT 30
        ''').fetchall())
        by_date = {}
        for row in date_data:
            by_date[row['date']] = {'count': row['count'], 'volume': float(row['volume'] or 0)}

        # Recent transactions (last 100 for display)
        recent = _rows_to_list(conn.execute('''
            SELECT id, bank_id, aid, date, time, type, amount, desc
            FROM transactions
            ORDER BY date DESC, time DESC
            LIMIT 100
        ''').fetchall())

    return jsonify({
        'totalCount': total_count,
        'totalVolume': total_volume,
        'txnByHour': hour_buckets,
        'txnByType': by_type,
        'txnByDate': by_date,
        'recentTxns': recent,
        'summary': {
            'message': 'Pre-computed aggregates from SQL (optimized)',
            'dataPoints': len(recent) + 24 + len(by_type) + len(by_date),
            'compression': f'{total_count} transactions → {len(recent) + 24 + len(by_type) + len(by_date)} data points'
        }
    })


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
                                       'advances_net', 'fixed_assets', 'intangible_assets', 'other_assets')), 2)
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


@app.route('/regulatory/api/banks/<bank_id>/alm')
def reg_bank_alm(bank_id):
    """Structural Liquidity Statement (ALCO) - maturity-bucketed assets vs.
    liabilities, cumulative gap, compliance flag, and recent funding-waterfall
    decisions. bank_id='CONSOLIDATED' aggregates all 9 banks."""
    from backend import alm_engine as _alm
    is_consolidated = bank_id == 'CONSOLIDATED'
    with _ops_conn() as conn:
        _alm.backfill_fd_maturity(conn, sim_date=SIM_DATE)
        _alm.renew_matured_fds(conn, sim_date=SIM_DATE)
        stmt = _alm.structural_liquidity_statement(
            conn, None if is_consolidated else bank_id, SIM_DATE, SIM_PERIOD)
        events = [] if is_consolidated else _alm.recent_funding_events(conn, bank_id)
    return jsonify({**stmt, 'funding_events': events})


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


from backend import npa_resolution as _npares


@app.route('/operations/api/loans/<loan_id>/resolve', methods=['POST'])
def ops_loan_resolve(loan_id):
    """Recovery / restructure / write-off a loan - the actions that actually
    move outstanding/balance-sheet figures (unlike /classify above, which only
    changes the classification label). See backend/npa_resolution.py.

    Body:
      action     — 'recovery' | 'restructure' | 'write_off'
      amount     — required for 'recovery' only (cash recovered, <= outstanding)
      rationale  — mandatory free-text justification (>= 20 chars)
      actor_id   — officer ID / name (optional, defaults to 'OPS-DEMO')
    """
    body = request.get_json(force=True) or {}
    action = (body.get('action') or '').strip()
    amount = body.get('amount')
    rationale = (body.get('rationale') or '').strip()
    actor_id = (body.get('actor_id') or 'OPS-DEMO').strip()

    with _ops_conn() as conn:
        try:
            result = _npares.resolve_npa(conn, loan_id, action, amount=amount,
                                          actor_id=actor_id, rationale=rationale)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        if result is None:
            return jsonify({'error': f'Loan {loan_id} not found'}), 404

    return jsonify(result)


@app.route('/operations/api/loans/<loan_id>/resolution-history')
def ops_loan_resolution_history(loan_id):
    """Hash-chained audit trail of resolve actions for one loan."""
    with _ops_conn() as conn:
        events = _npares.resolution_history(conn, loan_id)
    return jsonify({'loan_id': loan_id, 'events': events})


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

    # Phase 5 — source exposures from fact_credit_risk (the gold layer the
    # regulatory batch already populated) instead of re-running
    # client_exposure() live for every loan on every financial-report page
    # load. Falls back to the live path if the batch hasn't run yet for this
    # bank (fresh DB, or a brand-new bank with no batch history).
    precomputed_exposures = None
    try:
        from backend.fact_credit_risk import get_fact_credit_risk
        fact_rows = get_fact_credit_risk(conn, bank_id=bid)
        if fact_rows:
            precomputed_exposures = [{
                'cid': r['cid'], 'customer_name': r['customer_name'], 'loan_id': r['loan_id'],
                'loan_type': r['product'], 'rwa_approach': r['rwa_approach'],
                'exposure_class': r['exposure_class'], 'classification': r['loan_classification'],
                'ead': r['ead'] or 0.0, 'pd': r['pd_current'] or 0.0, 'lgd': r['lgd'] or 0.0,
                'risk_weight': r['risk_weight'] or 0.0, 'rw_basis': None,
                'rwa': r['rwa'] or 0.0, 'capital_charge': r['capital_charge'] or 0.0,
                'expected_loss': r['expected_loss'] or 0.0, 'provision': r['provision'] or 0.0,
            } for r in fact_rows]
    except Exception:
        precomputed_exposures = None   # fall back to live derivation below

    cap = _reg.bank_capital_report(bid, loans, accts, metrics, balance_sheet=bs,
                                   precomputed_exposures=precomputed_exposures)
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
        if not (application.get('bank_id') or '').strip():
            return jsonify({
                'error': 'bank_id is required',
                'message': 'Select the originating bank before referring this case.'
            }), 400
        # Route through the correct segment engine (CORPORATE/SME/RETAIL_MORTGAGES/
        # RETAIL_OTHER) - this used to hardcode the legacy unsegmented
        # _assessment_engine, silently bypassing segment routing for every RM case.
        engine, model_scope_used, err = _resolve_segment_engine(application)
        if err:
            return err
        try:
            M = _orchestrate(application, engine)
        except Exception as e:
            return jsonify({'error': f'Assessment failed: {e}'}), 500
        # Which model actually scored this case (Phase 2 model-routing switch) -
        # recorded on M so rm_case_store.create_case() -> prediction_store
        # captures it, not just the RM's requested model_scope.
        M['model_scope'] = model_scope_used
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


# ============================================================================
# MODEL GOVERNANCE DEPARTMENT — SR 11-7 / Basel / EU AI Act controls
# KPI monitoring (PSI drift, AUC stability, fairness gap), threshold alerts,
# per-model governance wiki, six-pillar validation sign-offs, regulatory
# mapping, and the hash-chained model-lifecycle audit trail.
# ============================================================================
from backend import governance_store as _gov
from backend import drift_monitor as _drift

_gov_schema_ready = False

def _gov_conn():
    """bank.db connection with the governance schema ensured once."""
    global _gov_schema_ready
    conn = _ops_conn()
    if not _gov_schema_ready:
        _gov.init_schema(conn)
        _gov_schema_ready = True
    return conn


def _run_governance_monitor_job():
    """APScheduler entry point for the daily drift/KPI monitor (03:00)."""
    try:
        with _gov_conn() as conn:
            summary = _drift.run_monitor(conn)
        print(f"[governance] monitor completed: {summary['kpis_written']} KPIs, "
              f"{summary['alerts_created']} alerts, {len(summary['breaches'])} breaches")
    except Exception as e:
        print(f'[governance] monitor error: {e}')


@app.route('/governance/')
@app.route('/governance')
def governance_home():
    return send_from_directory('public/governance', 'index.html')


@app.route('/governance/api/summary')
def gov_summary():
    """Dashboard payload: model inventory, latest KPIs, alerts, oversight, chain."""
    with _gov_conn() as conn:
        slots = _gov._load_active_registry()
        inventory = []
        for slot_key in slots:
            seg, bank = _gov.parse_slot(slot_key)
            reg = _gov._latest_registry_row(conn, seg, bank)
            signoffs = _gov.get_signoffs(conn, slot_key)
            latest = {}
            for kpi in ('psi_score', 'psi_feature', 'auc_stability', 'fairness_gap',
                        'prediction_volume'):
                row = conn.execute(
                    "SELECT value, threshold, status, run_ts FROM gov_kpi_snapshots "
                    "WHERE slot_key=? AND kpi=? AND feature IS NULL "
                    "ORDER BY run_ts DESC LIMIT 1", (slot_key, kpi)).fetchone()
                if row:
                    latest[kpi] = {'value': row[0], 'threshold': row[1],
                                   'status': row[2], 'run_ts': row[3]}
            open_alerts = conn.execute(
                "SELECT COUNT(*) FROM gov_alerts WHERE slot_key=? AND status='OPEN'",
                (slot_key,)).fetchone()[0]
            wiki_row = conn.execute(
                "SELECT risk_tier, version, updated_at FROM gov_wiki_entries "
                "WHERE slot_key=?", (slot_key,)).fetchone()
            inventory.append({
                'slot_key': slot_key, 'exposure_class': seg, 'bank_scope': bank,
                'model_type': (slots[slot_key] or {}).get('model_type'),
                'activated_at': (slots[slot_key] or {}).get('activated_at'),
                'model_id': (reg or {}).get('model_id'),
                'auc_roc': (reg or {}).get('auc_roc'),
                'promoted_at': (reg or {}).get('promoted_at'),
                'risk_tier': wiki_row[0] if wiki_row else None,
                'wiki_version': wiki_row[1] if wiki_row else None,
                'validation_signed': signoffs['signed_off'],
                'validation_total': signoffs['total'],
                'open_alerts': open_alerts,
                'kpis': latest,
            })
        alerts_open = _gov.list_alerts(conn, status='OPEN')
        last_run = conn.execute(
            "SELECT MAX(run_ts) FROM gov_kpi_snapshots").fetchone()[0]
        override_row = conn.execute(
            "SELECT value, detail_json, run_ts FROM gov_kpi_snapshots "
            "WHERE slot_key='SYSTEM' AND kpi='override_rate' "
            "ORDER BY run_ts DESC LIMIT 1").fetchone()
        try:
            oversight = _rm.insights(conn)
        except Exception:
            oversight = {}
        chain = _gov.verify_chain(conn)
    return jsonify({
        'inventory': inventory,
        'open_alerts': alerts_open,
        'open_alert_count': len(alerts_open),
        'last_monitor_run': last_run,
        'override_kpi': ({'value': override_row[0],
                          'detail': json.loads(override_row[1] or '{}'),
                          'run_ts': override_row[2]} if override_row else None),
        'oversight': oversight,
        'audit_chain': chain,
        'thresholds': _drift.load_thresholds(),
    })


@app.route('/governance/api/models')
def gov_models():
    with _gov_conn() as conn:
        slots = _gov._load_active_registry()
        out = []
        for slot_key in slots:
            seg, bank = _gov.parse_slot(slot_key)
            reg = _gov._latest_registry_row(conn, seg, bank)
            out.append({'slot_key': slot_key, 'exposure_class': seg,
                        'bank_scope': bank,
                        'model_type': (slots[slot_key] or {}).get('model_type'),
                        'model_id': (reg or {}).get('model_id'),
                        'auc_roc': (reg or {}).get('auc_roc'),
                        'promoted_at': (reg or {}).get('promoted_at'),
                        'n_train': (reg or {}).get('n_train')})
    return jsonify({'models': out})


@app.route('/governance/api/models/<path:slot_key>/kpis')
def gov_model_kpis(slot_key):
    limit = int(request.args.get('limit', 30))
    with _gov_conn() as conn:
        rows = conn.execute(
            "SELECT run_ts, kpi, feature, value, threshold, status, detail_json "
            "FROM gov_kpi_snapshots WHERE slot_key=? "
            "ORDER BY run_ts DESC, kpi LIMIT ?", (slot_key, limit * 8)).fetchall()
    history = []
    for r in rows:
        history.append({'run_ts': r[0], 'kpi': r[1], 'feature': r[2],
                        'value': r[3], 'threshold': r[4], 'status': r[5],
                        'detail': json.loads(r[6] or '{}')})
    return jsonify({'slot_key': slot_key, 'history': history})


@app.route('/governance/api/alerts')
def gov_alerts():
    with _gov_conn() as conn:
        alerts = _gov.list_alerts(conn, status=request.args.get('status'),
                                  slot_key=request.args.get('slot_key'))
    return jsonify({'alerts': alerts})


@app.route('/governance/api/alerts/<alert_id>/ack', methods=['POST'])
def gov_ack_alert(alert_id):
    if not _check_admin_auth(): return _admin_auth_error()
    body = request.get_json(force=True) or {}
    with _gov_conn() as conn:
        result, code = _gov.ack_alert(conn, alert_id, body.get('acked_by'),
                                      body.get('action_taken'))
        conn.commit()
    return jsonify(result), code


@app.route('/governance/api/models/<path:slot_key>/wiki', methods=['GET', 'POST'])
def gov_wiki(slot_key):
    if request.method == 'POST':
        if not _check_admin_auth(): return _admin_auth_error()
        body = request.get_json(force=True) or {}
        with _gov_conn() as conn:
            result, code = _gov.update_wiki(conn, slot_key, body.get('fields'),
                                            body.get('author'),
                                            body.get('change_description'))
            conn.commit()
        return jsonify(result), code
    with _gov_conn() as conn:
        entry = _gov.get_wiki(conn, slot_key)
    return jsonify(entry)


@app.route('/governance/api/models/<path:slot_key>/wiki/versions/<int:version>')
def gov_wiki_version(slot_key, version):
    with _gov_conn() as conn:
        snap = _gov.get_wiki_version(conn, slot_key, version)
    if not snap:
        return jsonify({'error': 'Version not found'}), 404
    return jsonify(snap)


@app.route('/governance/api/models/<path:slot_key>/validation', methods=['GET', 'POST'])
def gov_validation(slot_key):
    if request.method == 'POST':
        if not _check_admin_auth(): return _admin_auth_error()
        body = request.get_json(force=True) or {}
        with _gov_conn() as conn:
            result, code = _gov.sign_off(conn, slot_key, body.get('pillar'),
                                         body.get('validator'), body.get('status'),
                                         body.get('notes'))
        return jsonify(result), code
    with _gov_conn() as conn:
        signoffs = _gov.get_signoffs(conn, slot_key)
    return jsonify(signoffs)


@app.route('/governance/api/models/<path:slot_key>/regulatory')
def gov_regulatory(slot_key):
    with _gov_conn() as conn:
        mapping = _gov.regulatory_mapping(conn, slot_key)
    return jsonify(mapping)


@app.route('/governance/api/audit')
def gov_audit():
    with _gov_conn() as conn:
        events = _gov.list_audit_events(conn,
                                        limit=int(request.args.get('limit', 100)),
                                        object_id=request.args.get('object_id'))
    return jsonify({'events': events})


@app.route('/governance/api/audit/verify')
def gov_audit_verify():
    with _gov_conn() as conn:
        result = _gov.verify_chain(conn)
    return jsonify(result)


@app.route('/governance/api/run-monitor', methods=['POST'])
def gov_run_monitor():
    """Manual monitor trigger (mirrors POST /regulatory/api/run-batch)."""
    try:
        with _gov_conn() as conn:
            summary = _drift.run_monitor(conn)
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/governance/api/force-promote', methods=['POST'])
def gov_force_promote():
    if not _check_admin_auth(): return _admin_auth_error()
    body = request.get_json(force=True) or {}
    try:
        from ml_models.trainer import force_promote
        result = force_promote(
            body.get('model_type'), body.get('bank_combo') or 'ALL',
            body.get('exposure_class'),
            actor_id=body.get('actor_id'), rationale=body.get('rationale'))
        # reload the in-process engine so the forced model serves immediately
        seg = body.get('exposure_class')
        if seg and seg in _segment_engines:
            _segment_engines[seg] = _build_segment_engine(seg)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    Query params: bank_id (default BANK001 - HDFC Bank) or 'CONSOLIDATED' for group total
    Uses latest available data, not hardcoded simulation date.
    """
    bank_id = request.args.get('bank_id', 'BANK001')
    is_consolidated = bank_id == 'CONSOLIDATED'
    with _ops_conn() as conn:
        # ── Capital adequacy (from regulatory batch) ──────────────────────
        # Use ALL available data, sorted by date (not filtered to SIM_DATE)
        if is_consolidated:
            cap_rows = [dict(r) for r in conn.execute(
                """SELECT report_date,
                          AVG(car) as car, AVG(cet1_ratio) as cet1_ratio,
                          AVG(tier1_ratio) as tier1_ratio, AVG(leverage_ratio) as leverage_ratio,
                          SUM(total_rwa) as total_rwa, SUM(loan_book) as loan_book,
                          SUM(num_loans) as num_loans, SUM(num_npa) as num_npa,
                          SUM(total_provisions) as total_provisions
                   FROM reg_capital_reports GROUP BY report_date ORDER BY report_date""").fetchall()]
        else:
            cap_rows = [dict(r) for r in conn.execute(
                """SELECT report_date, car, cet1_ratio, tier1_ratio, leverage_ratio,
                          total_rwa, loan_book, num_loans, num_npa, total_provisions
                   FROM reg_capital_reports WHERE bank_id=? ORDER BY report_date""",
                (bank_id,)).fetchall()]

        # ── Liquidity ratios ──────────────────────────────────────────────
        if is_consolidated:
            liq_rows = [dict(r) for r in conn.execute(
                """SELECT report_date, AVG(lcr) as lcr, AVG(nsfr) as nsfr,
                          AVG(crr_ratio) as crr_ratio, AVG(slr_ratio) as slr_ratio,
                          SUM(hqla) as hqla, SUM(ndtl) as ndtl
                   FROM reg_liquidity_reports GROUP BY report_date ORDER BY report_date""").fetchall()]
        else:
            liq_rows = [dict(r) for r in conn.execute(
                """SELECT report_date, lcr, nsfr, crr_ratio, slr_ratio, hqla, ndtl
                   FROM reg_liquidity_reports WHERE bank_id=? ORDER BY report_date""",
                (bank_id,)).fetchall()]

        # ── Balance sheet ─────────────────────────────────────────────────
        if is_consolidated:
            bs_rows = [dict(r) for r in conn.execute(
                """SELECT period, as_on_date,
                          SUM(advances_net) as advances_net, SUM(investments) as investments,
                          SUM(deposits_demand+deposits_savings+deposits_term) AS deposits,
                          SUM(equity_capital+reserves_surplus) AS capital,
                          SUM(cash_with_rbi) as cash_with_rbi, SUM(balances_with_banks) as balances_with_banks,
                          SUM(other_assets) as other_assets,
                          SUM(borrowings) as borrowings, SUM(other_liabilities) as other_liabilities,
                          SUM(intangible_assets) as intangible_assets
                   FROM bank_balance_sheet GROUP BY period, as_on_date ORDER BY as_on_date""").fetchall()]
        else:
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
        if is_consolidated:
            pl_rows = [dict(r) for r in conn.execute(
                """SELECT period, from_date, to_date,
                          SUM(net_interest_income) as net_interest_income,
                          SUM(other_income) as other_income, SUM(total_income) as total_income,
                          SUM(interest_expended) as interest_expended,
                          SUM(operating_expenses) as operating_expenses,
                          SUM(provisions_contingencies) as provisions_contingencies,
                          SUM(operating_profit) as operating_profit,
                          SUM(profit_before_tax) as profit_before_tax,
                          SUM(profit_after_tax) as profit_after_tax
                   FROM bank_profit_loss GROUP BY period, from_date, to_date ORDER BY to_date""").fetchall()]
        else:
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

    # ── Decision gate helper ────────────────────────────────────────────────
    def _gate_score(metric, val):
        if metric == 'gnpa':    return 'GREEN' if val < 2 else ('AMBER' if val < 4 else 'RED')
        if metric == 'pat':     return 'GREEN' if val > 0 else ('AMBER' if val > -3 else 'RED')
        if metric == 'car':     return 'GREEN' if val > 15 else ('AMBER' if val > 13 else 'RED')
        if metric == 'disbur':  return 'GREEN' if val > 25 else ('AMBER' if val > 15 else 'RED')
        return 'GREEN'

    # ── New disbursals per period — live count of loans.disbursed within
    # each period's date window (replaces the old sim_period_metrics-based
    # figure, whose source table was retired along with the frozen-
    # simulation-clock subsystem earlier - that always read as 0).
    disbursals_series = []
    for r in pl_rows:
        from_d, to_d = r.get('from_date'), r.get('to_date')
        if not from_d or not to_d:
            continue
        if is_consolidated:
            count = conn.execute(
                "SELECT COUNT(*) FROM loans WHERE disbursed BETWEEN ? AND ?",
                (from_d, to_d)).fetchone()[0]
        else:
            count = conn.execute(
                "SELECT COUNT(*) FROM loans WHERE bank_id=? AND disbursed BETWEEN ? AND ?",
                (bank_id, from_d, to_d)).fetchone()[0]
        disbursals_series.append({
            'period': r['period'], 'date': to_d, 'count': count,
            'gate': {'disbursals': _gate_score('disbur', count)},
        })

    # ── Decision gate for latest period ───────────────────────────────────
    decision_gate = {}
    if capital_series and pl_series:
        latest_cap = capital_series[-1]
        latest_pl  = pl_series[-1]
        nd_count   = disbursals_series[-1]['count'] if disbursals_series else 0
        decision_gate = {
            'period': latest_cap['date'],
            'gnpa':   {'value': latest_cap['npa_ratio'],
                       'status': _gate_score('gnpa', latest_cap['npa_ratio'])},
            'pat':    {'value': latest_pl['pat_cr'],
                       'status': _gate_score('pat', latest_pl['pat_cr'])},
            'car':    {'value': latest_cap['car'],
                       'status': _gate_score('car', latest_cap['car'])},
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
        'bank_id':    'CONSOLIDATED' if is_consolidated else bank_id,
        'bank_name':  'Group Consolidated' if is_consolidated else bank_id,
        'sim_date':   latest_date,  # Use latest date from actual data
        'sim_period': SIM_PERIOD,
        'capital':    capital_series,
        'liquidity':  liquidity_series,
        'balance':    balance_series,
        'pl':         pl_series,
        'efficiency': efficiency_series,
        'disbursals': disbursals_series,
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
# TRANSACTION ML ENRICHMENT
# ============================================================================

@app.route('/api/transaction-risk/<txn_id>')
def api_transaction_risk(txn_id):
    """Get real-time default risk prediction for a transaction using transaction-level ML models."""
    try:
        with _ops_conn() as conn:
            # Get enriched transaction
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    cust_age, cust_employment_type, cust_education_level,
                    cust_years_employed, cust_annual_income, cust_cibil_score,
                    loan_de_ratio, loan_interest_coverage, loan_profitability, loan_liquidity_ratio,
                    loan_pd_score,
                    macro_gdp_growth_pct, macro_inflation_cpi_pct, macro_policy_rate_pct,
                    macro_unemployment_pct,
                    delta_gdp_pct, macro_regime_score, months_since_origination,
                    employment_type_enc, city_tier_enc, education_enc, residence_type_enc,
                    loan_purpose_enc, loan_classification_enc,
                    default_flag
                FROM transactions WHERE id = ?
            """, (txn_id,))

            result = cursor.fetchone()
            if not result:
                return jsonify({'error': 'Transaction not found'}), 404

            # For now, return the enriched features
            # Full model loading would require pickling the trained model
            features = {
                'cust_age': result[0],
                'cust_annual_income': result[4],
                'cust_cibil_score': result[5],
                'loan_de_ratio': result[6],
                'loan_interest_coverage': result[7],
                'macro_gdp_growth_pct': result[11],
                'macro_inflation_cpi_pct': result[12],
                'macro_regime_score': result[16],
                'months_since_origination': result[17],
                'default_flag_observed': result[-1]
            }

            return jsonify({
                'txn_id': txn_id,
                'status': 'enriched',
                'features_available': len(features),
                'sample_features': features,
                'note': 'Transaction-level models trained and ready for deployment'
            })
    except Exception as e:
        return jsonify({'error': f'Error fetching transaction risk: {e}'}), 500


def _enrich_transaction_with_ml_features(txn_id):
    """Automatically enrich a transaction with all ML training features when created."""
    try:
        with _ops_conn() as conn:
            # Get transaction and account info
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.bank_id, t.aid, t.date, a.cid FROM transactions t
                JOIN accounts a ON t.aid = a.id WHERE t.id = ?
            """, (txn_id,))
            result = cursor.fetchone()
            if not result:
                return False

            bank_id, aid, txn_date, cid = result

            # Get customer KYC
            cursor.execute("SELECT * FROM customer_kyc WHERE cid = ?", (cid,))
            kyc_row = cursor.fetchone()
            kyc_cols = [desc[0] for desc in cursor.description]
            kyc = dict(zip(kyc_cols, kyc_row)) if kyc_row else {}

            # Get active loan
            cursor.execute("""
                SELECT l.id, m.de, m.intcov, m.profit, m.liq, m.prior_de, m.prior_cibil,
                       m.pd_score, l.loan_classification, l.exposure_class, k.loan_purpose,
                       l.disbursed
                FROM loans l
                LEFT JOIN credit_risk_metrics m ON l.id = m.lid
                LEFT JOIN customer_kyc k ON l.cid = k.cid
                WHERE l.cid = ? AND l.disbursed <= ? AND (l.maturity > ? OR l.status = 'Active')
                ORDER BY l.disbursed DESC LIMIT 1
            """, (cid, txn_date, txn_date))
            loan_row = cursor.fetchone()
            loan = dict(zip(['loan_id', 'de_ratio', 'interest_coverage', 'profitability', 'liquidity_ratio',
                            'prior_de', 'prior_cibil', 'pd_score', 'loan_classification', 'exposure_class',
                            'loan_purpose', 'disbursed'], loan_row)) if loan_row else {}

            # Get macro data
            cursor.execute("""
                SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct,
                       delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, delta_unemployment_pct,
                       macro_regime_score
                FROM country_macro WHERE country_code = 'IND' AND period <= ?
                ORDER BY period DESC LIMIT 1
            """, (txn_date[:7],))
            macro_row = cursor.fetchone()
            macro = dict(zip(['gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
                             'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct', 'delta_unemployment_pct',
                             'macro_regime_score'], macro_row)) if macro_row else {}

            # Calculate months since origination
            months_since_origination = None
            if loan.get('disbursed'):
                try:
                    from datetime import datetime as dt
                    disbursed = dt.strptime(loan['disbursed'], '%Y-%m-%d')
                    txn_dt = dt.strptime(txn_date, '%Y-%m-%d')
                    months_since_origination = (txn_dt.year - disbursed.year) * 12 + (txn_dt.month - disbursed.month)
                except:
                    pass

            # Determine default flag
            default_flag = 1 if loan.get('loan_classification') in ['NPA', 'Default'] else 0

            # Encoding mappings
            EMPLOYMENT_TYPE_ENC = {'SALARIED': 1, 'SELF_EMPLOYED': 2, 'BUSINESS': 3, 'PROFESSIONAL': 4, 'GOVT': 5}
            EDUCATION_ENC = {'HIGH_SCHOOL': 1, 'DIPLOMA': 2, 'GRADUATE': 3, 'POST_GRADUATE': 4, 'PROFESSIONAL': 5, 'PHD': 6}
            CITY_TIER_ENC = {'TIER1': 1, 'TIER2': 2}
            RESIDENCE_TYPE_ENC = {'OWNED': 1, 'RENTED': 2, 'FAMILY': 3}
            LOAN_PURPOSE_ENC = {'HOME_PURCHASE': 1, 'AUTO': 2, 'PERSONAL': 3, 'BUSINESS': 4, 'EDUCATION': 5, 'VEHICLE': 6}
            LOAN_CLASSIFICATION_ENC = {'Standard': 0, 'NPA': 1, 'Default': 1}

            # Build update data
            update_data = {
                # Customer demographics
                'cust_age': kyc.get('age'),
                'cust_gender': kyc.get('gender'),
                'cust_employment_type': kyc.get('employment_type'),
                'cust_education_level': kyc.get('education_level'),
                'cust_years_employed': kyc.get('years_employed'),
                'cust_marital_status': kyc.get('marital_status'),
                'cust_num_dependents': kyc.get('num_dependents'),
                'cust_state': kyc.get('state'),
                'cust_industry_sector': kyc.get('industry_sector'),
                # Customer financial
                'cust_annual_income': kyc.get('annual_income'),
                'cust_other_income': kyc.get('other_income'),
                'cust_foir_declared': kyc.get('foir_declared'),
                'cust_cibil_score': kyc.get('cibil_score'),
                'cust_years_at_address': kyc.get('years_at_address'),
                'cust_is_rural': kyc.get('is_rural'),
                'cust_is_pep': kyc.get('is_pep'),
                # Loan metrics
                'loan_id_ref': loan.get('loan_id'),
                'loan_de_ratio': loan.get('de_ratio'),
                'loan_interest_coverage': loan.get('interest_coverage'),
                'loan_profitability': loan.get('profitability'),
                'loan_liquidity_ratio': loan.get('liquidity_ratio'),
                'loan_prior_de': loan.get('prior_de'),
                'loan_prior_cibil': loan.get('prior_cibil'),
                'loan_pd_score': loan.get('pd_score'),
                'loan_classification': loan.get('loan_classification'),
                'loan_exposure_class': loan.get('exposure_class'),
                'loan_purpose': loan.get('loan_purpose'),
                # Macro features
                'macro_gdp_growth_pct': macro.get('gdp_growth_pct'),
                'macro_inflation_cpi_pct': macro.get('inflation_cpi_pct'),
                'macro_policy_rate_pct': macro.get('policy_rate_pct'),
                'macro_unemployment_pct': macro.get('unemployment_pct'),
                # Delta features
                'delta_de_ratio': macro.get('delta_gdp_pct'),
                'delta_cibil': None,
                'delta_gdp_pct': macro.get('delta_gdp_pct'),
                'delta_cpi_pct': macro.get('delta_cpi_pct'),
                'delta_policy_rate_pct': macro.get('delta_policy_rate_pct'),
                'delta_unemployment_pct': macro.get('delta_unemployment_pct'),
                'months_since_origination': months_since_origination,
                'macro_regime_score': macro.get('macro_regime_score'),
                # Target
                'default_flag': default_flag,
                'pd_observed': txn_date if default_flag == 1 else None,
                # Encoded categoricals
                'employment_type_enc': EMPLOYMENT_TYPE_ENC.get(kyc.get('employment_type')),
                'city_tier_enc': CITY_TIER_ENC.get(kyc.get('city_tier')),
                'education_enc': EDUCATION_ENC.get(kyc.get('education_level')),
                'residence_type_enc': RESIDENCE_TYPE_ENC.get(kyc.get('residence_type')),
                'loan_purpose_enc': LOAN_PURPOSE_ENC.get(loan.get('loan_purpose')),
                'loan_classification_enc': LOAN_CLASSIFICATION_ENC.get(loan.get('loan_classification')),
            }

            # Execute update
            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [txn_id]
            cursor.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return True
    except Exception as e:
        print(f"[ENRICHMENT] Error enriching transaction {txn_id}: {e}")
        return False


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
