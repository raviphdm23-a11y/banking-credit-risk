"""
Assessment Engine — the single orchestrator that produces one immutable
findings object per borrower assessment.

Design principles
-----------------
* Deterministic: same inputs + same model version → byte-identical output.
* Transparent: every number traces to a named formula or model artifact.
* Audit-ready: findings include a SHA-256 content hash over inputs + model version.
* No matplotlib / heavy deps in the request path.

Features the RF model expects (in this exact order):
  de_ratio, interest_coverage, profitability, liquidity_ratio
  (profitability is in %, e.g. 12.0 means 12%)
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend.calculations import AIRBCalculations, StandardizedApproachCalculations
from backend.rating_masterscale import pd_to_grade, grade_description
from backend.pricing import full_pricing
from backend.feature_meta import FEATURE_ORDER, FEATURE_META, model_feature_frame, lookup_country_macro
from backend.explainability import PeerComparison, CounterfactualEngine
from backend.shap_explainer import create_shap_explainer

# Policy knockout thresholds (hard referral/decline triggers, pre-model)
_POLICY = {
    "auto_decline_pd":          0.50,   # PD ≥ 50% → Decline (model unreliable above this)
    "auto_refer_pd":            0.12,   # PD ≥ 12% → Refer regardless of grade
    "interest_coverage_floor":  1.0,    # ICR < 1.0 → cannot service debt → hard Refer
    "de_ratio_ceiling":         6.0,    # D/E ≥ 6.0 → extreme leverage → hard Refer
    "negative_profitability_refer": True,  # Negative profit → Refer
}


class AssessmentEngine:
    """
    Stateless assessor: initialise once at app startup, call assess() per request.

    Usage:
        engine = AssessmentEngine(model, model_version)
        findings = engine.assess(inputs_dict)
    """

    def __init__(self, model, model_version: str = "unknown", db_path: str = None, exposure_class: str = None):
        self._model        = model
        self._version      = model_version
        self._db_path      = db_path
        self._exposure_class = exposure_class
        # Segment-scoped peer benchmarks: a CORPORATE engine's peer
        # comparisons/counterfactuals are drawn from CORPORATE peers only,
        # not the whole blended portfolio - see explainability.load_peer_benchmarks().
        self._peer         = PeerComparison(exposure_class=exposure_class)
        self._counterfact  = CounterfactualEngine(model, exposure_class=exposure_class)
        # Pre-build baseline feature dict for marginal attribution
        self._baseline_vals = {f: FEATURE_META[f]["baseline"] for f in FEATURE_ORDER}
        # Tier 1: Cache learned thresholds for Five C's (computed on first use)
        self._learned_thresholds = None
        # Tier 2: SHAP explainer for feature interactions (shared cache)
        try:
            self._shap_explainer = create_shap_explainer(model, model_version) if model else None
        except Exception:
            self._shap_explainer = None  # Graceful fallback if SHAP unavailable

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def assess(self, inputs: dict) -> dict:
        """
        Produce the full immutable findings object for one borrower.

        Required inputs keys:
            de_ratio, interest_coverage, profitability, liquidity_ratio
            exposure (EAD), seniority, maturity

        Optional:
            collateral_type, collateral_value, borrower_type (default: Corporate)
            borrower_id, calculation_method (AIRB | SA), rating (for SA)

        Returns a dict suitable for JSON serialisation.
        """
        inputs = self._coerce(inputs)

        # Enrich with country macro features when country_code is available
        if self._db_path:
            macro = lookup_country_macro(inputs.get('country_code', ''), self._db_path)
            for k, v in macro.items():
                inputs.setdefault(k, v)

        # 1. PD via ML model
        pd_result   = self._predict_pd(inputs)
        pd_point    = pd_result["point"]
        pd_low      = pd_result["low"]
        pd_high     = pd_result["high"]

        # 1b. The exact resolved feature row the model was scored on (applicant
        # value where supplied, else the same calibrated defaults model_feature_frame
        # used) - exposed so the report can show "what the model actually saw" for
        # every one of the 36 training features, not just whatever the applicant
        # happened to submit. A bank-scoped model (allow_missing_features_) can
        # genuinely leave a value as NaN when the applicant didn't supply it -
        # that's correct model input, but literal NaN is not valid JSON (RFC
        # 8259) and breaks every consumer's response.json() on the frontend.
        # None (-> JSON null) is the honest "genuinely unknown" representation.
        def _json_safe(v):
            v = float(v)
            return None if v != v else v  # v != v is the standard NaN test
        model_inputs_resolved = {k: _json_safe(v) for k, v in self._feature_vector(inputs).iloc[0].items()}

        # 2. Rating grade
        rating = pd_to_grade(pd_point)
        rating["description"] = grade_description(rating["grade"])

        # 3. Policy knockouts (Tier 1: now uses uncertainty band)
        knockouts = self._check_knockouts(inputs, pd_point, pd_low, pd_high)

        # 4. Feature attribution (reason codes) - prefer real SHAP values, which
        # cover all 36 model features and mathematically sum to the prediction.
        # Falls back to the narrower leave-one-out method (the original 4 core
        # ratios only) if SHAP is unavailable in this process (e.g. shap
        # library/model incompatibility) - see _compute_attribution's docstring.
        shap_data = self._compute_shap(inputs) if self._shap_explainer else None
        if shap_data and shap_data.get("feature_contributions"):
            attribution = shap_data["feature_contributions"]
        else:
            attribution = self._compute_attribution(inputs, pd_point)

        # 4b. Once a loan is actually booked, collateral_register (Phase 2 - see
        # backend/collateral_store.py) is the durable source of truth for its
        # collateral - not whatever a caller happens to pass in `inputs` for a
        # later re-assessment. A brand-new origination has no loan_id yet, so
        # this is a no-op and inputs['collateral_type'/'collateral_value'] (from
        # the borrower-info.html form) are used as before.
        if self._db_path and inputs.get('loan_id'):
            try:
                import sqlite3
                from backend.collateral_store import get_collateral
                _conn = sqlite3.connect(self._db_path)
                stored = get_collateral(_conn, inputs['loan_id'])
                _conn.close()
                if stored:
                    inputs['collateral_type'] = stored['collateral_type']
                    inputs['collateral_value'] = stored['collateral_value']
            except Exception:
                pass

        # 5. LGD
        lgd_result = AIRBCalculations.calculate_lgd(
            seniority       = inputs["seniority"],
            collateral_type = inputs.get("collateral_type"),
            collateral_value= inputs.get("collateral_value", 0),
            exposure        = inputs["exposure"],
        )
        lgd = lgd_result.get("lgd", 0.45)

        # 6. AIRB chain (correlation → maturity adj → risk weight → RWA)
        rwa_result = self._compute_rwa(inputs, pd_point, lgd)

        # 7. Expected Loss + Pricing
        ead = inputs["exposure"]
        price_pkg = full_pricing(pd_point, lgd, ead, rwa_result.get("rwa", 0))

        # 8. Five C's narrative
        five_cs = self._five_cs(inputs, attribution, lgd_result, rwa_result)

        # 9. Recommendation
        recommendation = self._recommend(
            rating, knockouts, pd_point, pd_low, pd_high,
            price_pkg["el"]["percentage"], attribution,
        )

        # 9b. Peer comparison + counterfactuals
        peer_health    = self._peer.compare(inputs)
        counterfactuals = self._counterfact.generate(inputs, attribution)
        peer_meta = self._peer.benchmarks.get('_meta', {}) if isinstance(self._peer.benchmarks, dict) else {}
        peer_segment = {
            "exposure_class": self._exposure_class or inputs.get('exposure_class') or 'ALL',
            "n_peers": peer_meta.get('n_approved'),
        }

        # 10. Assemble & hash
        mrs = float(inputs.get('macro_regime_score', 0.0))
        if   mrs <= 25:  mrs_label = 'Normal'
        elif mrs <= 55:  mrs_label = 'Moderate Stress'
        else:            mrs_label = 'Severe Distress'

        findings = {
            "report_id":     str(uuid.uuid4()),
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "model_version": self._version,
            "inputs":        inputs,
            "model_inputs_resolved": model_inputs_resolved,
            "pd":            pd_result,
            "rating":        rating,
            "attribution":   attribution,
            "shap":          shap_data,
            "lgd":           lgd_result,
            "ead":           round(ead, 2),
            "rwa":           rwa_result,
            "el":            price_pkg["el"],
            "capital_charge": price_pkg["capital_charge"],
            "pricing":       price_pkg["pricing"],
            "policy_knockouts":  knockouts,
            "recommendation":    recommendation,
            "five_cs":           five_cs,
            "peer_health":       peer_health,
            "peer_segment":      peer_segment,
            "counterfactuals":   counterfactuals,
            "macro_regime": {
                "score":                 round(mrs, 1),
                "label":                 mrs_label,
                "delta_gdp_pct":         round(float(inputs.get('delta_gdp_pct', 0.0)), 2),
                "delta_unemployment_pct":round(float(inputs.get('delta_unemployment_pct', 0.0)), 2),
                "delta_policy_rate_pct": round(float(inputs.get('delta_policy_rate_pct', 0.0)), 2),
                "delta_cpi_pct":         round(float(inputs.get('delta_cpi_pct', 0.0)), 2),
                "interpretation": (
                    "No significant regime shift detected — standard cycle conditions." if mrs <= 25
                    else "Moderate macro stress — cyclical headwinds elevating default probability." if mrs <= 55
                    else "Severe macro distress — COVID/crisis-era conditions; PD materially elevated."
                ),
            },
        }
        findings["content_hash"] = self._hash(findings)
        return findings

    # -----------------------------------------------------------------------
    # PD: point estimate + 80% uncertainty band from RF tree variance
    # -----------------------------------------------------------------------

    def _predict_pd(self, inputs: dict) -> dict:
        X = self._feature_vector(inputs)
        if self._model is None:
            # Fallback to rule-based when model is unavailable
            rb = AIRBCalculations.calculate_pd(inputs)
            pd_val = rb.get("pd", 0.05)
            return {"point": pd_val, "low": pd_val, "high": pd_val,
                    "method": "rule_based_fallback", "n_trees": 0}

        # XGBClassifier: predict_proba gives P(default=1)
        point = float(np.clip(self._model.predict_proba(X)[0, 1], 0.0001, 1.0))

        # 80% uncertainty band using binomial standard error approximation
        n_trees = getattr(self._model, 'n_estimators', 200)
        se   = float(np.sqrt(point * (1.0 - point) / max(n_trees, 1)))
        low  = float(np.clip(point - 1.28 * se, 0.0001, 1.0))
        high = float(np.clip(point + 1.28 * se, 0.0001, 1.0))

        return {
            "point":    round(point, 6),
            "low":      round(low, 6),
            "high":     round(high, 6),
            "method":   "XGBoostClassifier",
            "n_trees":  n_trees,
            "band_note": "80% interval via binomial SE around point estimate",
        }

    # -----------------------------------------------------------------------
    # Attribution: marginal contribution per feature (local explanation)
    # -----------------------------------------------------------------------

    def _compute_attribution(self, inputs: dict, pd_point: float) -> list:
        """
        For each feature, compute the marginal PD change when that feature
        is replaced by its training-distribution baseline value.
        contribution_i = pd_full - pd_with_feature_i_at_baseline

        Positive contribution → feature is driving PD up (risk factor).
        Negative contribution → feature is suppressing PD (risk mitigant).

        TIER 1 FIX: Now includes XGBoost feature importance and ranks by
        weighted combination of importance and contribution.
        """
        results = []
        X_full = self._feature_vector(inputs)
        pd_full = (
            float(np.clip(self._model.predict_proba(X_full)[0, 1], 0.0001, 1.0))
            if self._model else pd_point
        )

        # Get XGBoost feature importance (Tier 1 enhancement)
        feature_importance = {}
        if self._model and hasattr(self._model, 'feature_importances_'):
            importances = self._model.feature_importances_
            for i, feat in enumerate(FEATURE_ORDER):
                feature_importance[feat] = float(importances[i]) if i < len(importances) else 0.0
        else:
            # Fallback: uniform importance if model doesn't have feature_importances_
            uniform = 1.0 / len(FEATURE_ORDER)
            for feat in FEATURE_ORDER:
                feature_importance[feat] = uniform

        for feat in FEATURE_ORDER:
            meta  = FEATURE_META[feat]
            value = inputs.get(feat, meta["baseline"])

            # Substitute this feature with its baseline, predict (full model vector)
            sub_inputs = dict(inputs)
            sub_inputs[feat] = meta["baseline"]
            X_sub = model_feature_frame(sub_inputs, self._model)
            pd_sub   = (
                float(np.clip(self._model.predict_proba(X_sub)[0, 1], 0.0001, 1.0))
                if self._model else pd_full
            )

            contribution = pd_full - pd_sub  # positive → this feature raises PD
            direction    = "increases_pd" if contribution > 0 else "decreases_pd"

            # Pick reason code
            if contribution > 0.002:
                reason_code = meta.get("reason_high") if meta["risk_direction"] == "higher_is_worse" else meta.get("reason_low")
            elif contribution < -0.002:
                reason_code = meta.get("reason_low") if meta["risk_direction"] == "higher_is_worse" else meta.get("reason_high")
            else:
                reason_code = None

            # Human-readable reason text
            bench_label = meta.get("bench_label", "")
            if contribution > 0.002:
                reason_text = (
                    f"{meta['display_name']} of {_fmt(value, meta['unit'])} "
                    f"is above the risk threshold (benchmark {bench_label})"
                    if meta["risk_direction"] == "higher_is_worse"
                    else
                    f"{meta['display_name']} of {_fmt(value, meta['unit'])} "
                    f"is below benchmark ({bench_label}) — increases default risk"
                )
            elif contribution < -0.002:
                reason_text = (
                    f"{meta['display_name']} of {_fmt(value, meta['unit'])} "
                    f"is a positive factor — reduces default risk"
                )
            else:
                reason_text = (
                    f"{meta['display_name']} of {_fmt(value, meta['unit'])} "
                    f"is broadly in line with benchmark ({bench_label})"
                )

            # Tier 1: Weighted rank = feature importance * absolute contribution
            weighted_rank = feature_importance[feat] * abs(contribution)

            results.append({
                "feature":        feat,
                "display_name":   meta["display_name"],
                "value":          round(float(value), 4),
                "baseline_value": meta["baseline"],
                "contribution":   round(contribution, 6),
                "direction":      direction,
                "reason_code":    reason_code,
                "reason_text":    reason_text,
                "five_c":         meta["five_c"],
                "xgb_importance": round(feature_importance[feat], 4),
                "weighted_rank":  round(weighted_rank, 6),
            })

        # Sort by weighted rank descending (Tier 1: importance-aware ranking)
        results.sort(key=lambda x: x["weighted_rank"], reverse=True)

        # Add rank position
        for i, r in enumerate(results):
            r["rank_position"] = i + 1

        return results

    # -----------------------------------------------------------------------
    # Policy knockouts
    # -----------------------------------------------------------------------

    def _check_knockouts(self, inputs: dict, pd_point: float, pd_low: float = None, pd_high: float = None) -> list:
        """
        Check for policy knockouts.

        TIER 1 FIX: Now uses pd_low (lower bound of uncertainty band) instead of pd_point
        for auto-decline and auto-refer rules. This prevents false positives when
        the point estimate is marginal but uncertainty is wide.

        If pd_low (best-case scenario) still exceeds threshold → truly risky
        If only pd_point exceeds threshold → might just be model uncertainty
        """
        knockouts = []

        # Use pd_low if available, otherwise fall back to pd_point
        pd_for_decision = pd_low if pd_low is not None else pd_point

        if pd_for_decision >= _POLICY["auto_decline_pd"]:
            knockouts.append({
                "rule":      "PD_EXCEEDS_AUTO_DECLINE",
                "severity":  "DECLINE",
                "detail":    f"PD {pd_point*100:.1f}% (band: {pd_low*100:.1f}%-{pd_high*100:.1f}%) exceeds {_POLICY['auto_decline_pd']*100:.0f}% threshold (even best-case scenario is high-risk)",
            })
        elif pd_for_decision >= _POLICY["auto_refer_pd"]:
            knockouts.append({
                "rule":      "PD_EXCEEDS_AUTO_REFER",
                "severity":  "REFER",
                "detail":    f"PD {pd_point*100:.1f}% (band: {pd_low*100:.1f}%-{pd_high*100:.1f}%) exceeds {_POLICY['auto_refer_pd']*100:.0f}% referral threshold",
            })

        ic = float(inputs.get("interest_coverage", 99))
        if ic < _POLICY["interest_coverage_floor"]:
            knockouts.append({
                "rule":      "INTEREST_COVERAGE_BELOW_FLOOR",
                "severity":  "REFER",
                "detail":    f"Interest coverage {ic:.2f}x < {_POLICY['interest_coverage_floor']}x — insufficient to service proposed debt",
            })

        de = float(inputs.get("de_ratio", 0))
        if de >= _POLICY["de_ratio_ceiling"]:
            knockouts.append({
                "rule":      "DE_RATIO_EXTREME",
                "severity":  "REFER",
                "detail":    f"D/E ratio {de:.1f}x ≥ {_POLICY['de_ratio_ceiling']:.0f}x — extreme leverage",
            })

        if _POLICY["negative_profitability_refer"]:
            pm = float(inputs.get("profitability", 0))
            if pm < 0:
                knockouts.append({
                    "rule":      "NEGATIVE_PROFITABILITY",
                    "severity":  "REFER",
                    "detail":    f"Net profit margin {pm:.1f}% is negative — loss-making entity",
                })

        return knockouts

    # -----------------------------------------------------------------------
    # AIRB risk weight chain
    # -----------------------------------------------------------------------

    def _compute_rwa(self, inputs: dict, pd: float, lgd: float) -> dict:
        exposure = float(inputs.get("exposure", 0))
        maturity = float(inputs.get("maturity", 2.5))
        lgd_pct  = lgd * 100

        rw_result = AIRBCalculations.calculate_risk_weight(pd, lgd_pct, exposure, maturity)
        if "error" in rw_result:
            return {"error": rw_result["error"], "rwa": 0, "capital_required": 0}

        risk_weight = rw_result["risk_weight"]
        rwa_result  = AIRBCalculations.calculate_rwa_and_capital(exposure, risk_weight)

        corr_result = AIRBCalculations.calculate_correlation(pd)
        ma_result   = AIRBCalculations.calculate_maturity_adjustment(maturity, lgd, pd)

        return {
            "rwa":               rwa_result.get("rwa", 0),
            "capital_required":  rwa_result.get("capital_required", 0),
            "risk_weight_pct":   round(risk_weight, 2),
            "correlation_r":     corr_result.get("r", 0),
            "maturity_adj":      ma_result.get("maturity_adjustment", 1.0),
            "b_coefficient":     ma_result.get("b_coefficient", 0),
            "exposure":          round(exposure, 2),
        }

    # -----------------------------------------------------------------------
    # Five C's narrative
    # -----------------------------------------------------------------------

    def _five_cs(self, inputs: dict, attribution: list,
                 lgd_result: dict, rwa_result: dict) -> dict:
        de  = float(inputs.get("de_ratio", 0))
        ic  = float(inputs.get("interest_coverage", 0))
        pm  = float(inputs.get("profitability", 0))
        lr  = float(inputs.get("liquidity_ratio", 0))
        mat = float(inputs.get("maturity", 2.5))
        bt  = inputs.get("borrower_type", "Corporate")

        # Tier 1: Use learned thresholds instead of hardcoded values
        learned = self._get_learned_thresholds()
        ic_threshold = learned.get("interest_coverage", 3.0)
        de_threshold = learned.get("de_ratio", 2.0)
        pm_threshold = learned.get("profitability", 8.0)
        lr_threshold = learned.get("liquidity_ratio", 1.5)

        def _score(conditions: list) -> str:
            # conditions is a list of (is_ok: bool) tuples
            good = sum(1 for ok in conditions if ok)
            if good == len(conditions): return "STRONG"
            if good == 0:               return "WEAK"
            return "MODERATE"

        capacity = {
            "score": _score([ic >= ic_threshold, de <= de_threshold]),
            "items": [
                {"label": "Interest Coverage",   "value": f"{ic:.2f}x",
                 "benchmark": f">= {ic_threshold:.2f}x (model-learned)",
                 "assessment": _assess_range(ic, low=ic_threshold, direction="higher")},
                {"label": "Debt-to-Equity",      "value": f"{de:.2f}x",
                 "benchmark": f"<= {de_threshold:.2f}x (model-learned)",
                 "assessment": _assess_range(de, high=de_threshold, direction="lower")},
            ],
        }

        capital = {
            "score": _score([pm >= pm_threshold, lr >= lr_threshold]),
            "items": [
                {"label": "Net Profit Margin",  "value": f"{pm:.1f}%",
                 "benchmark": f">= {pm_threshold:.1f}% (model-learned)",
                 "assessment": _assess_range(pm, low=pm_threshold, direction="higher")},
                {"label": "Current Ratio",      "value": f"{lr:.2f}x",
                 "benchmark": f">= {lr_threshold:.2f}x (model-learned)",
                 "assessment": _assess_range(lr, low=lr_threshold, direction="higher")},
            ],
        }

        seniority      = inputs.get("seniority", "Senior Unsecured")
        collateral_type = inputs.get("collateral_type")
        lgd_pct        = lgd_result.get("lgd_percentage", 45)
        coll_adj       = lgd_result.get("lgd", 0.45) < lgd_result.get("base_lgd", 45) / 100

        collateral_score = "STRONG" if lgd_pct <= 25 else "MODERATE" if lgd_pct <= 45 else "WEAK"
        coll_items = [
            {"label": "Seniority",        "value": seniority,
             "assessment": _seniority_note(seniority)},
            {"label": "LGD",              "value": f"{lgd_pct:.1f}%",
             "benchmark": "<= 25% (secured)",
             "assessment": f"{'Collateral reduces loss severity' if coll_adj else 'No collateral — base LGD applies'}"},
        ]
        if collateral_type:
            coll_items.append({
                "label": "Collateral Type", "value": collateral_type,
                "assessment": _collateral_quality_note(collateral_type),
            })
        collateral = {"score": collateral_score, "items": coll_items}

        conditions = {
            "score": "NEUTRAL",
            "items": [
                {"label": "Loan Maturity",    "value": f"{mat:.1f} years",
                 "assessment": "Short-term" if mat <= 1 else "Standard" if mat <= 3 else "Long-term tenor"},
                {"label": "Borrower Category","value": bt,
                 "assessment": f"Standard corporate risk weights applied under Basel III"},
                {"label": "Capital Required", "value": f"₹{rwa_result.get('capital_required', 0):,.0f}",
                 "assessment": f"8% of RWA ₹{rwa_result.get('rwa', 0):,.0f}"},
            ],
        }

        character = self._character(inputs)

        return {
            "capacity":   capacity,
            "capital":    capital,
            "collateral": collateral,
            "conditions": conditions,
            "character":  character,
        }

    # -----------------------------------------------------------------------
    # Character C — derived from bureau / credit-history inputs when supplied,
    # else flagged NOT_ASSESSED (the quantitative ratios carry no character info).
    # -----------------------------------------------------------------------

    @staticmethod
    def _character(inputs: dict) -> dict:
        def _num(key):
            v = inputs.get(key)
            if v in (None, ""):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        cibil  = _num("cibil_score")
        prev   = _num("previous_default_flag")
        late   = _num("num_late_payments_past_12m")
        loans  = _num("existing_loans_count")

        # No bureau signal at all → preserve the honest "not assessed" stance.
        if cibil is None and prev is None and late is None:
            return {
                "score": "NOT_ASSESSED",
                "items": [{
                    "label": "Qualitative Due Diligence",
                    "value": "Pending",
                    "assessment": (
                        "Character assessment requires bureau data (CIBIL/Equifax), "
                        "litigation / regulatory history and relationship-officer judgment. "
                        "No bureau inputs were supplied for this assessment."
                    ),
                }],
            }

        items = []
        if cibil is not None:
            if cibil >= 750:
                c_assess = "Strong bureau score — consistent, disciplined repayment history"
            elif cibil >= 650:
                c_assess = "Moderate bureau score — generally satisfactory credit conduct"
            else:
                c_assess = "Sub-prime bureau score — elevated character / willingness-to-pay risk"
            items.append({"label": "CIBIL Score", "value": f"{cibil:.0f}",
                          "benchmark": ">= 750", "assessment": c_assess})

        if prev is not None:
            items.append({"label": "Previous Default",
                          "value": "Yes" if prev else "No",
                          "assessment": ("Prior default on record — significant adverse indicator"
                                         if prev else "No prior defaults on record")})

        if late is not None:
            if late == 0:
                l_assess = "Clean recent repayment record (no delinquencies in 12m)"
            elif late <= 2:
                l_assess = "Occasional recent delinquency — monitor repayment discipline"
            else:
                l_assess = "Frequent recent delinquency — weak repayment discipline"
            items.append({"label": "Late Payments (12m)", "value": f"{late:.0f}",
                          "benchmark": "0", "assessment": l_assess})

        if loans is not None:
            items.append({"label": "Existing Loan Relationships", "value": f"{loans:.0f}",
                          "assessment": ("No existing leverage on file" if loans == 0
                                         else "Established borrowing track record"
                                         if loans <= 3 else "High number of active facilities — monitor")})

        # Composite score: any hard adverse signal → WEAK; clean across the board → STRONG.
        adverse = bool(prev) or (cibil is not None and cibil < 650) or (late is not None and late >= 3)
        pristine = (cibil is not None and cibil >= 750) and not prev and (late == 0 if late is not None else True)
        score = "WEAK" if adverse else "STRONG" if pristine else "MODERATE"
        return {"score": score, "items": items}

    # -----------------------------------------------------------------------
    # Tier 1: Learned thresholds from model
    # -----------------------------------------------------------------------

    def _get_learned_thresholds(self) -> dict:
        """
        Tier 1 FIX: Learn feature thresholds from model behavior instead of
        using hardcoded metadata.

        For key features (de_ratio, interest_coverage), find the value where
        the model's PD prediction increases significantly from baseline.

        Caches result to avoid recomputation.
        """
        if self._learned_thresholds is not None:
            return self._learned_thresholds

        thresholds = {}

        # If model not available, fall back to defaults
        if not self._model:
            return {
                "de_ratio": 2.0,
                "interest_coverage": 3.0,
                "profitability": 8.0,
                "liquidity_ratio": 1.5,
            }

        # Learn thresholds by testing where PD doubles from baseline
        baseline_inputs = dict(self._baseline_vals)
        X_baseline = model_feature_frame(baseline_inputs, self._model)
        pd_baseline = float(self._model.predict_proba(X_baseline)[0, 1])

        for feat in ["de_ratio", "interest_coverage", "profitability", "liquidity_ratio"]:
            meta = FEATURE_META[feat]
            min_val = meta.get("baseline", 1.0) * 0.5
            max_val = meta.get("baseline", 1.0) * 3.0

            # Binary search for where PD doubles
            found_threshold = None
            for test_val in np.linspace(min_val, max_val, 20):
                test_inputs = dict(baseline_inputs)
                test_inputs[feat] = test_val
                X_test = model_feature_frame(test_inputs, self._model)
                pd_test = float(self._model.predict_proba(X_test)[0, 1])

                if pd_test >= pd_baseline * 1.5:  # PD increased by 50%
                    found_threshold = test_val
                    break

            # Use learned threshold, or fall back to metadata baseline
            thresholds[feat] = found_threshold if found_threshold else meta.get("baseline", 1.0)

        self._learned_thresholds = thresholds
        return thresholds

    # -----------------------------------------------------------------------
    # Recommendation
    # -----------------------------------------------------------------------

    def _recommend(self, rating: dict, knockouts: list,
                   pd_point: float, pd_low: float, pd_high: float,
                   el_pct: float, attribution: list) -> dict:

        # Hard knockout overrides grade-based logic
        if any(k["severity"] == "DECLINE" for k in knockouts):
            return self._build_rec("DECLINE", "LOW", knockouts, attribution)

        # Grade-based base decision
        base = rating["default_decision"]

        # Uncertainty escalation: if the 80% band spans a grade boundary, escalate
        lo_grade = pd_to_grade(pd_low)["default_decision"]
        hi_grade = pd_to_grade(pd_high)["default_decision"]
        band_spans_boundary = lo_grade != hi_grade
        if band_spans_boundary and base == "APPROVE":
            base = "REFER"

        # Referral knockouts
        if any(k["severity"] == "REFER" for k in knockouts) and base == "APPROVE":
            base = "REFER"

        # Confidence
        pd_band_width = pd_high - pd_low
        if pd_band_width < 0.02:
            confidence = "HIGH"
        elif pd_band_width < 0.05:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        return self._build_rec(base, confidence, knockouts, attribution)

    def _build_rec(self, decision: str, confidence: str,
                   knockouts: list, attribution: list) -> dict:
        _labels = {
            "APPROVE":  "Approve",
            "REFER":    "Refer to Credit Committee",
            "DECLINE":  "Decline",
        }
        _rationale = {
            "APPROVE":  "Credit metrics are within policy parameters.",
            "REFER":    "One or more metrics require committee review before sanction.",
            "DECLINE":  "Credit metrics breach minimum policy thresholds.",
        }
        key_drivers = [
            a["reason_code"] for a in attribution
            if a["reason_code"] and a["contribution"] > 0.005
        ][:3]

        return {
            "decision":        decision,
            "decision_label":  _labels[decision],
            "confidence":      confidence,
            "rationale":       _rationale[decision],
            "key_drivers":     key_drivers,
            "knockouts_fired": [k["rule"] for k in knockouts],
            "override_note":   "Override requires documented credit officer justification.",
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _feature_vector(self, inputs: dict) -> pd.DataFrame:
        """Return a single-row DataFrame aligned to the model's expected feature
        set (4-ratio fallback when no model is loaded)."""
        return model_feature_frame(inputs, self._model)

    @staticmethod
    def _coerce(inputs: dict) -> dict:
        """Normalise and fill defaults on raw request data."""
        out = dict(inputs)
        # Numeric coercions
        for f in FEATURE_ORDER:
            try:
                out[f] = float(out.get(f, FEATURE_META[f]["baseline"]))
            except (TypeError, ValueError):
                out[f] = FEATURE_META[f]["baseline"]
        for num_key in ("exposure", "collateral_value", "maturity"):
            try:
                out[num_key] = float(out.get(num_key, 0))
            except (TypeError, ValueError):
                out[num_key] = 0.0
        if out.get("exposure", 0) <= 0:
            out["exposure"] = 1_000_000  # default ₹10 lakh if not provided
        _seniority_map = {
            "senior_secured":   "Senior Secured",
            "senior_unsecured": "Senior Unsecured",
            "subordinated":     "Subordinated",
            "junior":           "Junior",
        }
        raw_sen = out.get("seniority", "Senior Unsecured")
        out["seniority"] = _seniority_map.get(str(raw_sen).lower().replace(" ", "_"), raw_sen) if raw_sen else "Senior Unsecured"
        out.setdefault("borrower_type",    "Corporate")
        out.setdefault("calculation_method", "AIRB")
        out.setdefault("maturity",         2.5)
        return out

    @staticmethod
    def _hash(findings: dict) -> str:
        """SHA-256 over inputs + model_version (excluding report_id, timestamp, hash)."""
        payload = {
            "inputs":        findings["inputs"],
            "model_version": findings["model_version"],
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _compute_shap(self, inputs: dict) -> dict:
        """
        TIER 2: Compute SHAP values and feature interactions.

        Returns dict with:
        - base_value: baseline PD from model
        - feature_contributions: SHAP value per feature
        - interactions: top 3 feature interactions
        - summary: one-line executive summary
        - model_version, computed_at, cached: metadata

        Returns None if SHAP explainer unavailable.
        """
        if not self._shap_explainer:
            return None

        try:
            return self._shap_explainer.explain_assessment(inputs, use_cache=True)
        except Exception as e:
            # Log error but don't block assessment
            import sys
            print(f"Warning: SHAP computation failed: {e}", file=sys.stderr)
            return None


# ---------------------------------------------------------------------------
# Narrative helpers (module-level, no instance state)
# ---------------------------------------------------------------------------

def _fmt(value, unit: str) -> str:
    """Format a feature value with its unit for human display."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "percent":
        return f"{v:.1f}%"
    if unit == "ratio":
        return f"{v:.2f}x"
    return f"{v:.2f}"


def _assess_range(value: float, low: float = None, high: float = None,
                  direction: str = "higher") -> str:
    """Return a one-line assessment of a metric vs its benchmark."""
    v = float(value)
    if direction == "higher" and low is not None:
        if v >= low * 1.2:  return f"{v:.2f} - well above benchmark ({low:.1f}), healthy"
        if v >= low:        return f"{v:.2f} - meets benchmark ({low:.1f}), satisfactory"
        if v >= low * 0.75: return f"{v:.2f} - slightly below benchmark ({low:.1f}), monitor"
        return              f"{v:.2f} - materially below benchmark ({low:.1f}), risk factor"
    if direction == "lower" and high is not None:
        if v <= high * 0.8:  return f"{v:.2f} - well within benchmark (<= {high:.1f}), healthy"
        if v <= high:        return f"{v:.2f} - within benchmark (<= {high:.1f}), acceptable"
        if v <= high * 1.25: return f"{v:.2f} - modestly exceeds benchmark (<= {high:.1f}), monitor"
        return               f"{v:.2f} - materially exceeds benchmark (<= {high:.1f}), risk factor"
    return f"{v:.2f}"


def _seniority_note(seniority: str) -> str:
    _notes = {
        "Senior Secured":   "First-ranking charge on collateral — preferred recovery position",
        "Senior Unsecured": "Unsecured but ranks pari passu with other senior creditors",
        "Subordinated":     "Ranks behind senior creditors — elevated loss risk",
        "Junior":           "Last in recovery waterfall — very high loss severity",
    }
    return _notes.get(seniority, "Unknown seniority class")


def _collateral_quality_note(collateral_type: str) -> str:
    _notes = {
        "Cash":                   "Highest quality collateral — zero haircut, immediate liquidity",
        "Government Securities":  "High quality — 5% haircut under Basel standard supervisory haircuts",
        "Corporate Bonds":        "Moderate quality — 10% haircut, subject to issuer credit risk",
        "Equities":               "Volatile collateral — 20% haircut, mark-to-market exposure",
        "Other":                  "Non-standard collateral — 25% haircut applied conservatively",
    }
    return _notes.get(collateral_type, "Collateral type not classified")
