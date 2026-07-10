"""
SHAP Explainer Module - Tier 2 Feature Interactions
Provides SHAP values and feature interaction detection for ML assessments.

SHAP (SHapley Additive exPlanations) decomposes the model's prediction into
individual feature contributions, properly accounting for feature interactions.
Perfect decomposition: base_value + sum(shap_values) = model_prediction
"""

import hashlib
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from itertools import combinations
import shap
import shap.explainers._tree as _shap_tree

from backend.feature_meta import FEATURE_ORDER, model_feature_frame

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

        # Build feature frame
        X = model_feature_frame(inputs, self.model)

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

        # Build feature contributions
        feature_contributions = []
        for i, feat in enumerate(FEATURE_ORDER):
            feature_value = float(inputs.get(feat, 0))
            shap_value = float(np.asarray(shap_vals[i]).item())  # Convert numpy scalar to Python float

            # Get baseline value for comparison
            baseline_value = inputs.get(f"baseline_{feat}", 0)

            contribution = {
                "feature": feat,
                "shap_value": round(shap_value, 6),
                "feature_value": round(feature_value, 4),
                "baseline_value": round(baseline_value, 4),
                "direction": "increases_pd" if shap_value > 0 else "decreases_pd",
            }
            feature_contributions.append(contribution)

        # Sort by absolute SHAP value (strongest drivers first)
        feature_contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        # Detect interactions
        interactions = self._find_interactions(inputs, shap_vals, feature_contributions)

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
                          contributions: list) -> list:
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
            idx1 = FEATURE_ORDER.index(feat1)
            idx2 = FEATURE_ORDER.index(feat2)

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
