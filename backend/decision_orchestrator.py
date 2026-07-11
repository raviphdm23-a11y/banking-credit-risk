"""
decision_orchestrator.py
────────────────────────
Composes the **Machine Recommendation (M)** for the Relationship-Management
decision-support workflow. It does NOT make the decision — it assembles
everything an RM/credit officer needs to make one:

    model findings (reuses backend.assessment_engine)   →  risk estimate + explanation
  + credit policy (reuses backend.policy_engine)         →  eligibility / appetite
  + confidence & out-of-distribution routing            →  who must review
  + decision sensitivity (knife-edge detection)         →  could a small change flip it?
  + risk-adjusted, structured recommendation            →  approve / conditions / counter-offer / refer / decline
  + tiered, plain-language business explanation         →  for RMs, not data scientists
  + required control level (Delegation of Authority)    →  RM single / four-eyes / committee / auto-decline

The output is a single immutable, content-hashed object stored as the M node of
the case provenance graph.
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta

from backend import policy_engine
from backend.feature_meta import FEATURE_ORDER, FEATURE_META

# ── Delegation-of-Authority parameters (governance-owned) ────────────────────
DOA = {
    "rm_finalize_exposure": 2000000,    # ≤ ₹20L: an RM may finalise alone (if low risk)
    "committee_exposure":   10000000,   # > ₹1Cr: risk committee only
    "near_boundary_pct":    0.20,       # within ±20% of a PD cutoff = knife-edge
}

# PD cutoffs the org cares about (mirror assessment_engine policy knockouts)
PD_REFER_CUTOFF   = 0.12
PD_DECLINE_CUTOFF = 0.50

_MODEL_MAP   = {"APPROVE": "ELIGIBLE", "REFER": "REFER", "DECLINE": "DECLINE"}
_RANK        = {"ELIGIBLE": 0, "APPROVE": 0, "REFER": 1, "DECLINE": 2}


def orchestrate(application: dict, engine) -> dict:
    """Build the Machine Recommendation object for one application."""
    now = datetime.now(timezone.utc).isoformat()

    # 1. Model findings (M-core) — reuse the existing assessment engine.
    # Map intake fields onto the model's wider feature schema where names differ
    # (annual_income already matches; applicant_age → age). Unsupplied features
    # fall back to neutral defaults inside model_feature_frame.
    enriched = dict(application)
    if enriched.get("age") is None and application.get("applicant_age") is not None:
        enriched["age"] = application["applicant_age"]
    findings = engine.assess(enriched)
    pd_block   = findings["pd"]
    pd_point   = pd_block["point"]
    pd_low     = pd_block["low"]
    pd_high    = pd_block["high"]
    model_reco = findings["recommendation"]          # APPROVE | REFER | DECLINE
    attribution = findings["attribution"]
    counterfactuals = findings.get("counterfactuals", {})

    # 2. Credit policy (independent of model)
    policy = policy_engine.evaluate(application)

    # 3. Confidence + out-of-distribution
    band_width = round(pd_high - pd_low, 6)
    confidence_class = model_reco["confidence"]       # HIGH | MODERATE | LOW
    ood = _ood_flags(application)
    mandatory_review = bool(ood) or confidence_class == "LOW"

    # 4. Decision sensitivity (knife-edge)
    sensitivity = _sensitivity(pd_point, pd_low, pd_high, attribution)

    # 5. Compose risk-adjusted, structured recommendation
    composed = _compose(model_reco, policy, findings, application, sensitivity)

    # 6. Required control level (DoA)
    routing = _routing(application, policy, composed, confidence_class,
                       sensitivity, mandatory_review)

    # 7. Tiered business explanation
    business = _business_explanation(findings, policy, sensitivity, composed, counterfactuals)

    M = {
        "machine_recommendation": True,
        "created_at":      now,
        "model_version":   findings["model_version"],
        "policy_version":  policy["policy_version"],
        "report_id":       findings["report_id"],
        "model_content_hash": findings["content_hash"],
        "application":     application,
        "model_inputs_resolved": findings.get("model_inputs_resolved"),
        # model layer
        "pd":              pd_block,
        "rating":          findings["rating"],
        "model_recommendation": model_reco,
        "attribution":     attribution[:6],
        "lgd":             findings["lgd"],
        "ead":             findings["ead"],
        "rwa":             findings["rwa"],
        "el":              findings["el"],
        "pricing":         findings["pricing"],
        "five_cs":         findings["five_cs"],
        "counterfactuals": counterfactuals,
        "peer_health":     findings.get("peer_health"),
        "macro_regime":    findings.get("macro_regime"),
        # decision-support layers
        "policy":          policy,
        "confidence":      {"class": confidence_class, "band_width": band_width,
                            "pd_low": pd_low, "pd_high": pd_high,
                            "ood_flags": ood, "mandatory_review": mandatory_review},
        "sensitivity":     sensitivity,
        "composed":        composed,
        "routing":         routing,
        "business_explanation": business,
    }
    M["content_hash"] = _hash(M)
    return M


# ─────────────────────────────────────────────────────────────────────────────
def _ood_flags(application: dict) -> list:
    """Flag onboarding values far outside the model's training distribution.
    New / thin-file customers are exactly where a 4-feature model is weakest."""
    flags = []
    bounds = {  # plausible in-distribution range per feature
        "de_ratio":          (0.0, 8.0),
        "interest_coverage": (0.0, 30.0),
        "profitability":     (-30.0, 60.0),
        "liquidity_ratio":   (0.0, 6.0),
    }
    for f in FEATURE_ORDER:
        try:
            v = float(application.get(f))
        except (TypeError, ValueError):
            continue
        lo, hi = bounds[f]
        if v < lo or v > hi:
            flags.append({"feature": f, "display_name": FEATURE_META[f]["display_name"],
                          "value": v, "expected_range": [lo, hi]})
    return flags


def _sensitivity(pd_point, pd_low, pd_high, attribution) -> dict:
    """How robust is this recommendation? Could a small change flip the outcome?"""
    near = None
    for cutoff, name in ((PD_REFER_CUTOFF, "referral"), (PD_DECLINE_CUTOFF, "decline")):
        if abs(pd_point - cutoff) <= cutoff * DOA["near_boundary_pct"]:
            near = name
            break
    band_spans_referral = pd_low < PD_REFER_CUTOFF <= pd_high
    # Features whose improvement would most reduce PD = the levers that could flip it
    flip_factors = [
        {"feature": a["feature"], "display_name": a["display_name"],
         "value": a["value"], "contribution": a["contribution"]}
        for a in attribution if a["contribution"] > 0.005
    ][:3]
    is_sensitive = bool(near) or band_spans_referral
    return {
        "near_boundary": near,
        "band_spans_referral_cutoff": band_spans_referral,
        "is_knife_edge": is_sensitive,
        "flip_factors": flip_factors,
        "note": ("Recommendation is close to a decision boundary — a small change "
                 "in the highlighted factors could change the outcome."
                 if is_sensitive else
                 "Recommendation is robust to small input changes."),
    }


def _compose(model_reco, policy, findings, application, sensitivity) -> dict:
    """Worst-of(model, policy) then risk-adjust into a structured recommendation."""
    model_sev  = _MODEL_MAP[model_reco["decision"]]
    worst = model_sev if _RANK[model_sev] >= _RANK[policy["decision"]] else policy["decision"]

    requested = float(application.get("requested_amount") or application.get("exposure") or 0)
    suggested_limit = min(requested or float("inf"), policy["max_exposure"])
    if suggested_limit == float("inf"):
        suggested_limit = requested
    rate = findings["pricing"].get("indicative_rate_pct")
    conditions = []
    flags = policy.get("flags", [])

    if "EDD_REQUIRED" in flags:
        conditions.append("Complete Enhanced Due Diligence (PEP) and obtain senior sign-off.")
    for r in policy["rules_fired"]:
        if r["rule"] == "LTV_EXCEEDS_LIMIT":
            conditions.append("Reduce loan amount or pledge additional collateral to meet LTV cap.")
        if r["rule"] == "FOIR_ELEVATED":
            conditions.append("Add a co-applicant or reduce quantum to bring FOIR within policy.")
        if r["rule"] == "AGE_AT_MATURITY":
            conditions.append("Shorten tenor or add a younger co-applicant.")
        if r["rule"] == "INCOME_BELOW_MINIMUM":
            conditions.append("Provide additional income proof or co-applicant income.")

    # Map to a structured outcome (risk-adjusted, not bare approve/reject)
    if worst == "DECLINE":
        outcome, label = "DECLINE", "Decline"
    elif worst == "REFER":
        outcome, label = "REFER", "Refer for review"
    else:
        if conditions:
            outcome, label = "APPROVE_WITH_CONDITIONS", "Approve with conditions"
        elif suggested_limit < (requested or 0) - 1:
            outcome, label = "COUNTER_OFFER", "Counter-offer (reduced limit)"
        else:
            outcome, label = "APPROVE", "Approve"

    return {
        "recommendation":  outcome,
        "label":           label,
        "model_component": model_reco["decision"],
        "policy_component": policy["decision"],
        "conditions":      conditions,
        "suggested_limit": round(suggested_limit, 2) if suggested_limit else None,
        "suggested_rate":  rate,
        "risk_grade":      findings["rating"]["grade"],
        "expected_loss_pct": findings["el"].get("percentage"),
    }


def _routing(application, policy, composed, confidence_class, sensitivity, mandatory_review) -> dict:
    """Delegation-of-Authority: who is allowed to act, and how."""
    exposure = float(application.get("requested_amount") or application.get("exposure") or 0) \
        + float(application.get("existing_exposure") or 0)

    if composed["recommendation"] == "DECLINE" or "FINANCIAL_CRIME_ESCALATION" in policy["flags"]:
        control, reason = "AUTO_DECLINE", "Hard policy/financial-crime decline — RM cannot approve; escalation only."
    elif exposure > DOA["committee_exposure"] or "COMMITTEE_REQUIRED" in policy["flags"]:
        control, reason = "COMMITTEE", "Exposure or policy flag requires Risk Committee approval."
    elif (exposure > DOA["rm_finalize_exposure"] or confidence_class == "LOW"
          or sensitivity["is_knife_edge"] or composed["recommendation"] == "REFER"
          or mandatory_review):
        control, reason = "FOUR_EYES", "Requires credit-officer approval (four-eyes)."
    else:
        control, reason = "RM_SINGLE", "Within RM delegated authority."

    return {
        "required_control": control,
        "rm_can_finalize":  control == "RM_SINGLE",
        "override_allowed": control in ("RM_SINGLE", "FOUR_EYES"),
        "escalation_only":  control in ("AUTO_DECLINE", "COMMITTEE"),
        "reason":           reason,
        "exposure_assessed": round(exposure, 2),
    }


def _business_explanation(findings, policy, sensitivity, composed, counterfactuals) -> dict:
    """Plain-language explanation for business users (not data scientists)."""
    rating = findings["rating"]
    pd_pct = findings["pd"]["point"] * 100

    headline = (f"Risk grade {rating['grade']} ({rating.get('description','')}), "
                f"estimated default probability {pd_pct:.1f}%. "
                f"Recommended action: {composed['label']}.")

    top_factors = []
    for a in findings["attribution"][:4]:
        if abs(a["contribution"]) < 0.002:
            continue
        top_factors.append({
            "factor": a["display_name"],
            "effect": "raises risk" if a["contribution"] > 0 else "lowers risk",
            "plain":  a["reason_text"],
        })

    # Actionable recourse from counterfactuals (customer-permissible levers only)
    what_could_change = []
    cf_items = counterfactuals if isinstance(counterfactuals, list) else []
    for c in cf_items[:3]:
        if not isinstance(c, dict):
            what_could_change.append(str(c))
            continue
        txt = c.get("action_text")
        if not txt:
            txt = (f"Move {c.get('display_name','a factor')} from "
                   f"{c.get('current_value')} to {c.get('target_value')}.")
        if c.get("pd_reduction_pp"):
            txt += f" (≈ {c['pd_reduction_pp']}pp lower default probability)"
        what_could_change.append(txt)
    if not what_could_change and sensitivity["flip_factors"]:
        for f in sensitivity["flip_factors"]:
            what_could_change.append(
                f"Improving {f['display_name']} would have the largest effect on the outcome.")

    watch_items = [r["detail"] for r in policy["rules_fired"]]
    if sensitivity["is_knife_edge"]:
        watch_items.insert(0, sensitivity["note"])

    # Reassessment recommendation
    if composed["recommendation"] in ("APPROVE_WITH_CONDITIONS", "COUNTER_OFFER", "REFER"):
        reassess = "Recommend formal reassessment in 6 months given conditions/borderline profile."
    elif rating["grade"] in ("BBB-", "BB+", "BB", "BB-", "B+", "B", "B-"):
        reassess = "Recommend annual reassessment; monitor via early-warning signals."
    else:
        reassess = "Standard periodic review cycle applies."

    return {
        "headline":         headline,
        "top_factors":      top_factors,
        "what_could_change": what_could_change,
        "watch_items":      watch_items,
        "reassessment":     reassess,
    }


def _hash(M: dict) -> str:
    payload = {"application": M["application"], "model_version": M["model_version"],
               "policy_version": M["policy_version"],
               "composed": M["composed"]["recommendation"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
