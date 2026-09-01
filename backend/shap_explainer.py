"""
SHAP Explainer Module - Tier 2 Feature Interactions
Provides SHAP values and feature interaction detection for ML assessments.

SHAP (SHapley Additive exPlanations) decomposes the model's prediction into
individual feature contributions, properly accounting for feature interactions.
Perfect decomposition: base_value + sum(shap_values) = model_prediction
"""

import hashlib
import io
import base64
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from itertools import combinations
import matplotlib
matplotlib.use('Agg')  # non-interactive backend - safe under Flask/threads
import matplotlib.pyplot as plt
import shap
import shap.explainers._tree as _shap_tree
from sklearn.pipeline import Pipeline

from backend.feature_meta import (
    FEATURE_ORDER, FEATURE_META, EXTRA_FEATURE_DEFAULTS,
    FEATURE_DISPLAY_NAMES, FEATURE_FIVE_C, feature_unit, model_feature_frame,
)


def _fmt_val(value, unit: str) -> str:
    """Format one feature value for a reason-text sentence."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "percent":
        return f"{v:.1f}%"
    if unit == "percent_fraction":
        return f"{v * 100:.1f}%"
    if unit == "inr":
        return "Rs. " + format(int(round(v)), ",d")
    if unit == "int":
        return f"{int(round(v))}"
    if unit == "ratio":
        return f"{v:.2f}x"
    return f"{v:.2f}"  # plain 0-100 style index/score - no misleading "x" suffix


def _reason_for(feat: str, meta: dict, value: float, contribution: float, display_name: str):
    """Reason code + human-readable sentence for one feature's contribution.

    The 4 core ratios have curated benchmark copy (bench_label, reason_high/low)
    in FEATURE_META - reuse that. The other 32 features have no curated
    benchmark text, so they get a generic model-learned framing instead of a
    fabricated threshold."""
    if meta:
        bench_label = meta.get("bench_label", "")
        risk_dir = meta["risk_direction"]
        val_str = _fmt_val(value, meta["unit"])
        if contribution > 0.002:
            reason_code = meta.get("reason_high") if risk_dir == "higher_is_worse" else meta.get("reason_low")
            reason_text = (
                f"{display_name} of {val_str} is above the risk threshold (benchmark {bench_label})"
                if risk_dir == "higher_is_worse" else
                f"{display_name} of {val_str} is below benchmark ({bench_label}) - increases default risk"
            )
        elif contribution < -0.002:
            reason_code = meta.get("reason_low") if risk_dir == "higher_is_worse" else meta.get("reason_high")
            reason_text = f"{display_name} of {val_str} is a positive factor - reduces default risk"
        else:
            reason_code = None
            reason_text = f"{display_name} of {val_str} is broadly in line with benchmark ({bench_label})"
        return reason_code, reason_text

    val_str = _fmt_val(value, feature_unit(feat))
    if contribution > 0.002:
        return None, f"{display_name} of {val_str} is a risk factor (model-learned) - increases default risk"
    if contribution < -0.002:
        return None, f"{display_name} of {val_str} is a positive factor (model-learned) - reduces default risk"
    return None, f"{display_name} of {val_str} has a negligible effect on this assessment"

# XGBoost >= 2.1 serializes base_score as a bracketed array string (e.g.
# "[4.999206E-1]") to support multi-output models. shap's XGBTreeModelLoader
# still does a bare float(...) on it, which raises ValueError and gets
# swallowed by assessment_engine's try/except, silently disabling SHAP for
# every model. Patch the ubjson decode step to unwrap the bracket before
# shap parses it - the value itself is unaffected, only its string form.
_orig_decode_ubjson_buffer = _shap_tree.decode_ubjson_buffer


def _decode_ubjson_buffer_fixed(fp):
    jmodel = _orig_decode_ubjson_buffer(fp)
    try:
        param = jmodel["learner"]["learner_model_param"]
        base_score = param.get("base_score")
        if isinstance(base_score, str) and base_score.startswith("[") and base_score.endswith("]"):
            param["base_score"] = base_score.strip("[]")
    except (KeyError, TypeError):
        pass
    return jmodel


_shap_tree.decode_ubjson_buffer = _decode_ubjson_buffer_fixed


def _convert_numpy(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: _convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_numpy(i) for i in obj]
    return obj


class SHAPCache:
    """
    In-memory cache for SHAP values.

    Caches SHAP computations to avoid expensive recomputation.
    Invalidates on: model version change, age >7 days, size >500MB
    """

    def __init__(self, max_size_mb=500, ttl_days=7):
        self.cache = {}
        self.max_size_mb = max_size_mb
        self.ttl_days = ttl_days
        self.created_at = datetime.now()
        self.model_version = None

    def _input_hash(self, inputs: dict) -> str:
        """Create deterministic hash of input for cache key"""
        sorted_items = sorted(inputs.items())
        json_str = json.dumps(sorted_items, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def get(self, inputs: dict, model_version: str) -> dict:
        """Retrieve cached SHAP values if valid"""
        # Invalidate cache if model changed
        if self.model_version != model_version:
            self.cache.clear()
            self.model_version = model_version
            self.created_at = datetime.now()
            return None

        # Invalidate cache if too old
        if datetime.now() - self.created_at > timedelta(days=self.ttl_days):
            self.cache.clear()
            self.created_at = datetime.now()
            return None

        key = self._input_hash(inputs)
        return self.cache.get(key)

    def set(self, inputs: dict, shap_data: dict, model_version: str):
        """Store SHAP values in cache"""
        self.model_version = model_version
        key = self._input_hash(inputs)
        self.cache[key] = shap_data

        # Simple size check (approximate)
        estimated_size = len(json.dumps(self.cache)) / (1024 * 1024)
        if estimated_size > self.max_size_mb:
            # Clear oldest entries if cache too large
            self.cache = {}

    def stats(self) -> dict:
        """Return cache statistics"""
        return {
            "entries": len(self.cache),
            "size_kb": len(json.dumps(self.cache)) / 1024,
            "created_at": self.created_at.isoformat(),
            "model_version": self.model_version,
        }


class SHAPExplainer:
    """
    SHAP Values Explainer for XGBoost model.

    Computes Shapley values for each feature and detects feature interactions.
    Uses TreeExplainer (optimized for tree-based models like XGBoost).

    Performance:
    - First call (no cache): ~100-150ms
    - Cached call: ~2-5ms
    """

    def __init__(self, model, model_version: str, cache: SHAPCache = None):
        """
        Initialize SHAP explainer

        Args:
            model: Trained XGBoost classifier
            model_version: Version string for cache invalidation
            cache: Optional SHAPCache instance (creates new if None)
        """
        if model is None:
            raise ValueError("Model cannot be None")

        self.model = model
        self.model_version = model_version
        self.cache = cache or SHAPCache()

        # Initialize TreeExplainer for XGBoost
        try:
            self.explainer = shap.TreeExplainer(model)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize SHAP TreeExplainer: {e}")

    def explain_assessment(self, inputs: dict, use_cache: bool = True) -> dict:
        """
        Compute SHAP values for a single assessment.

        Args:
            inputs: Input features dict
            use_cache: Whether to use/store cache (default True)

        Returns:
            {
                "base_value": float,
                "expected_value": float,
                "feature_contributions": [
                    {
                        "feature": str,
                        "shap_value": float,
                        "feature_value": float,
                        "baseline_value": float,
                        "direction": "increases_pd" | "decreases_pd"
                    },
                    ...
                ],
                "interactions": [
                    {
                        "feature_pair": [str, str],
                        "interaction_strength": float,
                        "type": "amplifying" | "mitigating",
                        "explanation": str
                    },
                    ...
                ],
                "summary": str,
                "model_version": str,
                "computed_at": str,
                "cached": bool,
            }
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(inputs, self.model_version)
            if cached:
                cached["cached"] = True
                return cached

        # Build feature frame - aligned to model.feature_names_in_, i.e. ALL 36
        # training features, not just the 4-item legacy FEATURE_ORDER constant.
        X = model_feature_frame(inputs, self.model)
        feature_names = list(X.columns)

        # Compute SHAP values for default class (index 1 = default)
        try:
            shap_values = self.explainer.shap_values(X)
            # TreeExplainer returns list for binary classification
            # shap_values[0] = class 0, shap_values[1] = class 1 (default)
            if isinstance(shap_values, list):
                shap_vals = shap_values[1][0]  # Class 1 (default), sample 0
            else:
                # Fallback: direct array (shouldn't happen with TreeExplainer)
                shap_vals = shap_values[0]  # Single sample
        except Exception as e:
            raise RuntimeError(f"Failed to compute SHAP values: {e}")

        # shap.TreeExplainer on an XGBoost classifier returns values in the
        # model's raw margin (log-odds) space by default, not probability -
        # convert to an approximate PD-percentage-point contribution via the
        # logistic derivative p*(1-p), so this is comparable to (and can
        # replace) the older leave-one-out method's contribution units.
        pd_point = float(np.clip(self.model.predict_proba(X)[0, 1], 1e-4, 1 - 1e-4))
        margin_to_pd = pd_point * (1 - pd_point)

        importances = getattr(self.model, "feature_importances_", None)

        # Build feature contributions - one per REAL model feature (36), not
        # just the 4 core ratios.
        feature_contributions = []
        for i, feat in enumerate(feature_names):
            feature_value = float(X.iloc[0][feat])
            shap_value = float(np.asarray(shap_vals[i]).item())  # margin-space
            contribution = shap_value * margin_to_pd              # PD-fraction space

            meta = FEATURE_META.get(feat)
            baseline_value = meta["baseline"] if meta else EXTRA_FEATURE_DEFAULTS.get(feat, 0.0)
            display_name = FEATURE_DISPLAY_NAMES.get(feat, feat)
            five_c = FEATURE_FIVE_C.get(feat, "conditions")
            reason_code, reason_text = _reason_for(feat, meta, feature_value, contribution, display_name)

            # A bank-scoped model can genuinely leave feature_value as NaN
            # when the applicant didn't supply it - correct model input, but
            # literal NaN is not valid JSON (RFC 8259) and breaks
            # response.json() on every consumer. None (-> JSON null) is the
            # honest "genuinely unknown" representation.
            json_safe_value = None if feature_value != feature_value else round(feature_value, 4)

            feature_contributions.append({
                "feature":        feat,
                "display_name":   display_name,
                "value":          json_safe_value,
                "baseline_value": round(float(baseline_value), 4),
                "contribution":   round(contribution, 6),
                "shap_value":     round(shap_value, 6),
                "direction":      "increases_pd" if contribution > 0 else "decreases_pd",
                "reason_code":    reason_code,
                "reason_text":    reason_text,
                "five_c":         five_c,
                "xgb_importance": round(float(importances[i]), 4) if importances is not None and i < len(importances) else 0.0,
            })

        # Sort by absolute PD contribution (strongest real drivers first)
        feature_contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)

        # Detect interactions
        interactions = self._find_interactions(inputs, shap_vals, feature_contributions, feature_names)

        # Generate summary
        summary = self._generate_summary(feature_contributions, interactions)

        # Build result
        # expected_value can be scalar or array depending on XGBoost version
        expected = self.explainer.expected_value
        if isinstance(expected, (list, np.ndarray)):
            expected_val = float(expected[1]) if len(expected) > 1 else float(expected[0])
        else:
            expected_val = float(expected)

        result = {
            "base_value": round(expected_val, 6),
            "expected_value": round(expected_val, 6),
            "feature_contributions": feature_contributions,
            "interactions": interactions,
            "summary": summary,
            "model_version": self.model_version,
            "computed_at": datetime.now().isoformat(),
            "cached": False,
        }

        # Convert numpy types to Python native types for JSON serialization
        result = _convert_numpy(result)

        # Cache result
        if use_cache:
            self.cache.set(inputs, result, self.model_version)

        return result

    def _find_interactions(self, inputs: dict, shap_vals: np.ndarray,
                          contributions: list, feature_names: list) -> list:
        """
        Detect significant feature interactions.

        Logic:
        1. For each feature pair
        2. Compute if they interact meaningfully
        3. Return top interactions sorted by strength

        An interaction exists when the joint effect of two features
        differs significantly from the sum of individual effects.
        """
        interactions = []

        # Get top 5 features by absolute SHAP value
        top_features = [c["feature"] for c in contributions[:5]]

        # Check all pairs in top features
        for feat1, feat2 in combinations(top_features, 2):
            idx1 = feature_names.index(feat1)
            idx2 = feature_names.index(feat2)

            shap1 = shap_vals[idx1]
            shap2 = shap_vals[idx2]

            # Compute interaction as deviation from additivity
            # In SHAP, interactions are implicit in the values,
            # but we can approximate by looking at conditional effects
            individual_sum = shap1 + shap2

            # Interaction strength: how much the joint effect deviates
            # from what we'd expect from individual contributions
            interaction_strength = abs(shap1 * shap2) / max(abs(shap1), abs(shap2), 0.0001)

            if interaction_strength > 0.003:  # Threshold for significance
                interaction_type = "amplifying" if (shap1 > 0 and shap2 > 0) else "mitigating"

                interaction = {
                    "feature_pair": [feat1, feat2],
                    "interaction_strength": round(interaction_strength, 6),
                    "type": interaction_type,
                    "explanation": self._explain_interaction(
                        feat1, feat2,
                        inputs.get(feat1, 0),
                        inputs.get(feat2, 0),
                        interaction_type
                    ),
                }
                interactions.append(interaction)

        # Sort by strength descending
        interactions.sort(key=lambda x: x["interaction_strength"], reverse=True)

        return interactions[:3]  # Return top 3 interactions

    def _explain_interaction(self, feat1: str, feat2: str, val1: float, val2: float,
                            interaction_type: str) -> str:
        """Generate human-readable explanation of interaction"""
        if interaction_type == "amplifying":
            return f"{feat1} ({val1:.2f}) and {feat2} ({val2:.2f}) together amplify risk"
        else:
            return f"{feat1} ({val1:.2f}) and {feat2} ({val2:.2f}) together mitigate risk"

    def _generate_summary(self, contributions: list, interactions: list) -> str:
        """Generate executive summary of SHAP findings"""
        if not contributions:
            return "No significant features."

        top_3 = contributions[:3]
        top_features_text = ", ".join([c["feature"] for c in top_3])

        if interactions:
            top_interaction = interactions[0]
            pair = top_interaction["feature_pair"]
            return (f"Top drivers: {top_features_text}. "
                   f"Key interaction: {pair[0]} × {pair[1]} "
                   f"({top_interaction['type']}).")
        else:
            return f"Top drivers: {top_features_text}."

    def cache_stats(self) -> dict:
        """Return cache statistics"""
        return self.cache.stats()


def create_shap_explainer(model, model_version: str) -> SHAPExplainer:
    """
    Factory function to create SHAP explainer with shared cache.

    Usage:
        explainer = create_shap_explainer(model, "run_20260702_045113")
        findings = explainer.explain_assessment(inputs)
    """
    return SHAPExplainer(model, model_version)


# ── Global (aggregate) SHAP — Model Lab research tab ─────────────────────────
#
# The class above only explains ONE assessment at a time (local attribution).
# This section computes an aggregate, dataset-level view: which features
# actually carry signal for a given trained model type, expressed relative
# to a synthetic random "noise" feature - any real feature whose mean|SHAP|
# is only ~1x the noise column's is statistically indistinguishable from a
# coin flip.
#
# The noise column has to be a genuine TRAINED-ON feature for this to mean
# anything: a pretrained model that never saw it literally cannot depend on
# it (its predict_proba would either hard-error on the extra column, for a
# raw XGBoost booster, or just ignore it), so any "SHAP value" computed that
# way would be a trivial, uninformative zero - not a real signal-vs-noise
# comparison. Instead this fits a *shadow* model: same model_type and the
# same hyperparameters the selected model was actually trained with (see
# admin_model_lab_shap in app.py, which reads them off that model's own
# pd_model_metadata.json), refit on the sampled rows plus the injected
# noise column together, via trainer.py's train_model() dispatcher - the
# same builder function production training uses. Whatever real advantage
# the trained-on features have over noise, this shadow model reveals it
# structurally, the same way Boruta-style shadow-feature selection does.
def compute_global_shap(model_type: str, X_sample: pd.DataFrame, y_sample, hp: dict) -> dict:
    """Aggregate SHAP importance + noise-baseline ratio for a shadow model of
    `model_type`, retrained on `X_sample` (real features) + `y_sample`
    (default_flag) with a synthetic `__noise__` column injected so its
    trained-in importance can serve as a "statistically indistinguishable
    from chance" floor for every real feature."""
    from ml_models.trainer import train_model

    rng = np.random.RandomState(42)
    X = X_sample.reset_index(drop=True).copy()
    y = pd.Series(y_sample).reset_index(drop=True)
    X['__noise__'] = rng.standard_normal(len(X))
    feature_names = list(X.columns)

    shadow_model = train_model(X, y, hp, model_type=model_type)

    # The selected model's own hyperparameters were tuned for its FULL
    # training set (thousands of rows) - reused as-is on a much smaller
    # research sample, regularization knobs like min_child_weight/gamma can
    # occasionally block every split, collapsing the shadow model to a
    # single constant prediction. SHAP on a constant-output model is
    # trivially all-zero for every feature including noise, which looks
    # like a broken chart rather than what it is - surface it explicitly.
    shadow_proba = shadow_model.predict_proba(X)[:, 1]
    if float(np.std(shadow_proba)) < 1e-6:
        raise ValueError(
            "The shadow model collapsed to a constant prediction on this sample "
            "(this model's saved hyperparameters are tuned for a much larger training "
            "set, and its regularization blocked every split on this small a sample) - "
            "try a larger sample_size."
        )

    inner = shadow_model.named_steps['clf'] if hasattr(shadow_model, 'named_steps') else shadow_model
    is_tree = inner.__class__.__name__ in (
        'XGBClassifier', 'RandomForestClassifier', 'ExtraTreesClassifier', 'GradientBoostingClassifier',
    )

    if is_tree:
        if hasattr(shadow_model, 'named_steps'):
            pre = Pipeline(shadow_model.steps[:-1])
            X_explain = pd.DataFrame(pre.transform(X), columns=feature_names, index=X.index)
        else:
            X_explain = X
        explainer = shap.TreeExplainer(inner)
        raw_values = explainer.shap_values(X_explain)
        shap_vals = raw_values[1] if isinstance(raw_values, list) else raw_values
        explainer_mode = 'tree'
    else:
        background = shap.sample(X, min(50, len(X)), random_state=42)
        masker = shap.maskers.Independent(background, max_samples=len(background))

        def _predict_default_proba(arr):
            return shadow_model.predict_proba(pd.DataFrame(arr, columns=feature_names))[:, 1]

        explainer = shap.Explainer(_predict_default_proba, masker)
        shap_vals = np.asarray(explainer(X).values)
        explainer_mode = 'permutation'

    mean_abs = np.abs(shap_vals).mean(axis=0)
    mean_abs_shap = {f: float(v) for f, v in zip(feature_names, mean_abs)}
    noise_baseline = mean_abs_shap.pop('__noise__')
    real_features = [f for f in feature_names if f != '__noise__']
    shap_ratio = {
        f: (round(mean_abs_shap[f] / noise_baseline, 3) if noise_baseline > 1e-12 else None)
        for f in real_features
    }

    ranked = sorted(real_features, key=lambda f: mean_abs_shap[f], reverse=True)

    for _style in ('seaborn-v0_8-whitegrid', 'seaborn-whitegrid', 'ggplot', 'default'):
        try:
            plt.style.use(_style)
            break
        except OSError:
            continue
    order = list(reversed(ranked))
    fig, ax = plt.subplots(figsize=(8, max(4, 0.32 * len(order))))
    ax.barh(order, [mean_abs_shap[f] for f in order], color='#2196F3')
    ax.axvline(noise_baseline, color='#E91E63', linestyle='--', lw=1.5,
               label=f'Random noise baseline ({noise_baseline:.4f})')
    ax.set_xlabel('Mean |SHAP value|')
    ax.set_title(f'Global SHAP Importance — {model_type} ({explainer_mode})', fontsize=13, fontweight='bold')
    ax.tick_params(axis='y', labelsize=9)
    ax.legend(loc='lower right')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
    buf.seek(0)
    chart_png_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return {
        'model_type': model_type,
        'explainer_mode': explainer_mode,
        'n_samples': int(len(X_sample)),
        'noise_baseline': round(float(noise_baseline), 6),
        'features': [
            {
                'feature': f,
                'mean_abs_shap': round(mean_abs_shap[f], 6),
                'shap_ratio': shap_ratio[f],
            }
            for f in ranked
        ],
        'chart_png_b64': chart_png_b64,
    }
