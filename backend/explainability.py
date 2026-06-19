"""
Step 2 — Explainability: peer comparison and constrained counterfactuals.

PeerComparison
  Compares applicant feature values against the median of approved borrowers
  (low-PD borrowers from the synthetic training distribution).

CounterfactualEngine
  For each actionable feature with a positive PD contribution, finds the
  *minimum* change to that feature that would move the borrower to the next
  better rating grade. Constrained to realistic ranges.
"""

import numpy as np
import pandas as pd

from backend.feature_meta import FEATURE_ORDER, FEATURE_META, model_feature_frame
from backend.rating_masterscale import pd_to_grade

# ---------------------------------------------------------------------------
# Peer benchmarks: approved-book statistics (PD < 5%)
# Derived from the synthetic Indian bank training distribution.
# Will be overridden by ml_models/peer_benchmarks.json when available.
# ---------------------------------------------------------------------------
_DEFAULT_BENCHMARKS = {
    "de_ratio":          {"median": 0.85, "p25": 0.45, "p75": 1.50, "label": "Debt-to-Equity"},
    "interest_coverage": {"median": 7.00, "p25": 4.50, "p75": 11.0, "label": "Interest Coverage"},
    "profitability":     {"median": 14.5, "p25": 9.00, "p75": 21.0, "label": "Net Profit Margin (%)"},
    "liquidity_ratio":   {"median": 1.85, "p25": 1.40, "p75": 2.50, "label": "Current Ratio"},
}

# Realistic feature bounds for counterfactual search
_BOUNDS = {
    "de_ratio":          (0.10, 8.0),
    "interest_coverage": (0.30, 18.0),
    "profitability":     (-40,  60.0),
    "liquidity_ratio":   (0.20, 4.0),
}


def load_peer_benchmarks(path: str = None) -> dict:
    """Load peer benchmarks from JSON file, falling back to defaults."""
    if path is None:
        import os
        path = os.path.join(
            os.path.dirname(__file__), '..', 'ml_models', 'peer_benchmarks.json'
        )
    try:
        import json
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return _DEFAULT_BENCHMARKS


# ---------------------------------------------------------------------------
# Peer Comparison
# ---------------------------------------------------------------------------

class PeerComparison:
    """
    Compare an applicant's feature values against the approved-borrower median.

    Returns, per feature:
        value       — applicant's value
        peer_median — median of approved borrowers
        peer_p25    — 25th percentile of approved borrowers
        peer_p75    — 75th percentile of approved borrowers
        ratio       — applicant / peer_median
        status      — STRONG | OK | WEAK
        gap         — applicant - peer_median (signed; negative means below median)
        gap_pct     — gap as % of peer_median
    """

    def __init__(self, benchmarks: dict = None):
        self.benchmarks = benchmarks or load_peer_benchmarks()

    def compare(self, inputs: dict) -> dict:
        result = {}
        for feat in FEATURE_ORDER:
            meta  = FEATURE_META[feat]
            bench = self.benchmarks.get(feat, {})
            value = float(inputs.get(feat, meta["baseline"]))
            median = float(bench.get("median", meta["baseline"]))

            ratio = value / (median + 1e-9)
            gap   = value - median
            gap_pct = (gap / (median + 1e-9)) * 100

            direction = meta["risk_direction"]
            if direction == "higher_is_worse":
                # Lower is better for the borrower
                if ratio <= 0.80:   status = "STRONG"
                elif ratio <= 1.20: status = "OK"
                else:               status = "WEAK"
            else:
                # Higher is better
                if ratio >= 1.20:   status = "STRONG"
                elif ratio >= 0.80: status = "OK"
                else:               status = "WEAK"

            result[feat] = {
                "display_name": meta["display_name"],
                "value":        round(value, 4),
                "peer_median":  round(median, 4),
                "peer_p25":     round(float(bench.get("p25", median * 0.7)), 4),
                "peer_p75":     round(float(bench.get("p75", median * 1.3)), 4),
                "ratio":        round(ratio, 4),
                "gap":          round(gap, 4),
                "gap_pct":      round(gap_pct, 1),
                "status":       status,
                "unit":         meta["unit"],
                "five_c":       meta["five_c"],
            }
        return result


# ---------------------------------------------------------------------------
# Constrained Counterfactual Engine
# ---------------------------------------------------------------------------

class CounterfactualEngine:
    """
    For each actionable feature with a positive PD contribution, find the
    *minimum* single-feature change that moves the borrower to the next
    better rating grade.

    Also computes a "combined" scenario — all weak features moved to their
    peer P75 — to show the maximum achievable improvement.
    """

    def __init__(self, model):
        self._model = model

    def generate(self, inputs: dict, attribution: list) -> list:
        """
        Returns a list of counterfactual dicts, sorted by PD reduction
        (largest improvement first).

        Each dict:
            feature         — feature name
            display_name    — human label
            current_value   — applicant's current value
            target_value    — the value needed to reach the next grade
            current_grade   — current rating grade
            target_grade    — grade achieved after this change
            pd_current      — current PD
            pd_target       — PD after the change
            pd_reduction_pp — reduction in percentage points
            pct_change      — % change in feature value
            direction       — "increase" | "decrease"
            difficulty      — 1 (easy) to 4 (hard)
            timeline_months — (min, max) realistic time horizon
            action_text     — plain-language guidance
        """
        if self._model is None:
            return []

        # Current PD + grade
        X_current = self._to_df(inputs)
        pd_current = float(np.clip(self._model.predict_proba(X_current)[0, 1], 0.0001, 1.0))
        current_grade = pd_to_grade(pd_current)["grade"]
        target_pd_threshold = self._next_grade_threshold(pd_current)

        results = []

        # Single-feature counterfactuals
        for attr in attribution:
            feat = attr["feature"]
            if attr["contribution"] <= 0.002:
                # Not a meaningful risk driver — skip
                continue

            meta = FEATURE_META[feat]
            direction = "decrease" if meta["risk_direction"] == "higher_is_worse" else "increase"
            current_val = float(inputs.get(feat, meta["baseline"]))

            target_val, pd_achieved = self._binary_search(
                inputs, feat, current_val, target_pd_threshold, direction
            )

            if target_val is None:
                continue

            pd_reduction = pd_current - pd_achieved
            if pd_reduction < 0.005:
                continue

            pct_change = (target_val - current_val) / (abs(current_val) + 1e-9) * 100
            target_grade = pd_to_grade(pd_achieved)["grade"]

            results.append({
                "feature":          feat,
                "display_name":     meta["display_name"],
                "current_value":    round(current_val, 4),
                "target_value":     round(target_val, 4),
                "current_grade":    current_grade,
                "target_grade":     target_grade,
                "pd_current":       round(pd_current, 6),
                "pd_target":        round(pd_achieved, 6),
                "pd_reduction_pp":  round(pd_reduction * 100, 2),
                "pct_change":       round(pct_change, 1),
                "direction":        direction,
                **self._action_guidance(feat, current_val, target_val, direction),
            })

        results.sort(key=lambda x: x["pd_reduction_pp"], reverse=True)

        # Combined scenario: all weak features moved to P75 of peers
        combined = self._combined_scenario(inputs, pd_current, current_grade)
        if combined:
            results.append(combined)

        return results

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _binary_search(self, inputs: dict, feat: str,
                       current_val: float, target_pd: float,
                       direction: str, max_iter: int = 40):
        """
        Binary search for the minimum feature change to reach target_pd.
        Returns (target_value, pd_achieved) or (None, None) if not feasible.
        """
        lo_bound, hi_bound = _BOUNDS[feat]

        if direction == "decrease":
            lo, hi = lo_bound, current_val
        else:
            lo, hi = current_val, hi_bound

        # Quick feasibility check: does the extreme value achieve target?
        extreme_val = lo if direction == "decrease" else hi
        test_inputs = dict(inputs)
        test_inputs[feat] = extreme_val
        pd_extreme = float(np.clip(self._model.predict_proba(self._to_df(test_inputs))[0, 1], 0.0001, 1.0))

        if pd_extreme >= target_pd:
            return None, None  # Not achievable even at extreme

        # Binary search
        for _ in range(max_iter):
            mid = (lo + hi) / 2
            test_inputs[feat] = mid
            pd_mid = float(np.clip(self._model.predict_proba(self._to_df(test_inputs))[0, 1], 0.0001, 1.0))

            if direction == "decrease":
                if pd_mid <= target_pd:
                    lo = mid   # mid is sufficient; try to be less aggressive
                else:
                    hi = mid   # need to go lower
            else:
                if pd_mid <= target_pd:
                    hi = mid   # mid is sufficient; try to be less aggressive
                else:
                    lo = mid   # need to go higher

        # Final value: use the boundary that achieves the target
        final_val = lo if direction == "decrease" else hi
        test_inputs[feat] = final_val
        pd_final = float(np.clip(self._model.predict_proba(self._to_df(test_inputs))[0, 1], 0.0001, 1.0))

        return round(final_val, 4), round(pd_final, 6)

    def _next_grade_threshold(self, pd: float) -> float:
        """Return the upper bound of the next better grade."""
        from backend.rating_masterscale import _MASTERSCALE
        for i, (grade, lo, hi, *_) in enumerate(_MASTERSCALE):
            if lo <= pd < hi and i > 0:
                # The grade one step better has PD ceiling at lo of current
                prev_grade = _MASTERSCALE[i - 1]
                return prev_grade[2] * 0.98  # target just inside better grade
        return pd * 0.7  # fallback: 30% reduction

    def _combined_scenario(self, inputs: dict, pd_current: float,
                            current_grade: str) -> dict:
        """Compute combined impact of moving all weak features to P75 of approved peers."""
        benchmarks = load_peer_benchmarks()
        combined_inputs = dict(inputs)
        features_changed = []

        for feat in FEATURE_ORDER:
            meta  = FEATURE_META[feat]
            bench = benchmarks.get(feat, {})
            current_val = float(inputs.get(feat, meta["baseline"]))
            p75 = float(bench.get("p75", meta["baseline"]))

            if meta["risk_direction"] == "higher_is_worse":
                median = float(bench.get("median", meta["baseline"]))
                if current_val > median * 1.1:
                    combined_inputs[feat] = min(current_val, p75)
                    features_changed.append(meta["display_name"])
            else:
                median = float(bench.get("median", meta["baseline"]))
                if current_val < median * 0.9:
                    combined_inputs[feat] = max(current_val, p75)
                    features_changed.append(meta["display_name"])

        if not features_changed:
            return None

        X_combined = self._to_df(combined_inputs)
        pd_combined = float(np.clip(self._model.predict_proba(X_combined)[0, 1], 0.0001, 1.0))
        target_grade = pd_to_grade(pd_combined)["grade"]
        pd_reduction = pd_current - pd_combined

        if pd_reduction < 0.005:
            return None

        return {
            "feature":          "_combined",
            "display_name":     "Combined Improvement Scenario",
            "current_value":    None,
            "target_value":     None,
            "current_grade":    current_grade,
            "target_grade":     target_grade,
            "pd_current":       round(pd_current, 6),
            "pd_target":        round(pd_combined, 6),
            "pd_reduction_pp":  round(pd_reduction * 100, 2),
            "pct_change":       None,
            "direction":        "combined",
            "difficulty":       3,
            "timeline_months":  (6, 12),
            "action_text": (
                f"Improving {', '.join(features_changed)} to approved-borrower P75 levels "
                f"would move the grade from {current_grade} to {target_grade}, "
                f"reducing PD by {pd_reduction*100:.1f}pp."
            ),
        }

    def _to_df(self, inputs: dict) -> pd.DataFrame:
        # Align to the model's expected feature set (handles the 21-feature model;
        # falls back to the 4 ratios when no model is loaded).
        return model_feature_frame(inputs, self._model)

    @staticmethod
    def _action_guidance(feat: str, current_val: float, target_val: float,
                         direction: str) -> dict:
        """Return difficulty, timeline, and plain-language action text."""
        meta = FEATURE_META[feat]
        change_pct = abs(target_val - current_val) / (abs(current_val) + 1e-9) * 100

        _guidance = {
            "de_ratio": {
                "decrease": {
                    "short": "Repay or restructure existing debt to reduce leverage.",
                    "action": (
                        "Target: reduce D/E by retiring high-cost debt or injecting equity. "
                        "Options: use operating cash flows for debt repayment, negotiate "
                        "debt-for-equity swap, or raise fresh equity capital."
                    ),
                    "difficulty": 2 if change_pct < 30 else 3,
                    "timeline": (1, 6) if change_pct < 20 else (3, 12),
                },
            },
            "interest_coverage": {
                "increase": {
                    "short": "Improve EBIT or reduce interest burden.",
                    "action": (
                        "Target: grow EBIT through revenue expansion / cost reduction, "
                        "or reduce interest expense by refinancing at lower rates. "
                        "A 1-point improvement in ICR typically requires either "
                        f"a {change_pct:.0f}% EBIT improvement or equivalent debt reduction."
                    ),
                    "difficulty": 2 if change_pct < 25 else 3,
                    "timeline": (3, 9) if change_pct < 30 else (6, 18),
                },
            },
            "profitability": {
                "increase": {
                    "short": "Strengthen net profit margin through cost discipline or pricing.",
                    "action": (
                        "Review cost structure — particularly operating leverage. "
                        "Identify low-margin product lines for repricing or exit. "
                        "Working capital efficiency improvements can also lift margins."
                    ),
                    "difficulty": 2,
                    "timeline": (3, 9),
                },
            },
            "liquidity_ratio": {
                "increase": {
                    "short": "Improve current ratio by accelerating receivables or extending payables.",
                    "action": (
                        "Reduce current liabilities (retire short-term debt) or "
                        "increase current assets (faster debtor collections, "
                        "reduce slow-moving inventory, establish revolving credit facility "
                        "to convert short-term into long-term debt)."
                    ),
                    "difficulty": 1 if change_pct < 20 else 2,
                    "timeline": (1, 6),
                },
            },
        }

        g = _guidance.get(feat, {}).get(direction, {})
        return {
            "difficulty":      g.get("difficulty", 2),
            "timeline_months": g.get("timeline", (3, 9)),
            "action_text":     g.get("action", f"Improve {meta['display_name']} to {target_val:.2f}."),
        }
