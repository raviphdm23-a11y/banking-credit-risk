"""
policy_engine.py
────────────────
Deterministic, versioned credit-policy engine — **separate from the ML model**.

This is the enterprise pattern called out in the architecture review: the model
produces a *risk estimate*; this engine applies the bank's *eligibility rules,
regulatory limits and risk-appetite cutoffs*. The organisation's decision is a
policy decision informed by the model — not the model's raw output. Policy can
change here (and be re-versioned) without ever retraining the model, and a
decline can be proven to a regulator as policy-driven rather than a black box.

Rules are declarative and evaluated in order. Each rule that fires records a
machine-readable code, a severity, and a plain-language explanation. Output is a
policy decision in {ELIGIBLE, REFER, DECLINE} plus the eligible exposure ceiling
and any flags (e.g. mandatory EDD).

Nothing here touches the model. `decision_orchestrator.py` combines the two.
"""

from datetime import date

POLICY_VERSION = "credit-policy-v1.0 (2026-06)"

# ── Risk-appetite / regulatory parameters (business-owned, versioned) ────────
PARAMS = {
    "foir_decline":          0.55,   # debt-service ratio above which we decline
    "foir_refer":            0.45,   # debt-service ratio requiring review
    "min_age":               21,
    "max_age_at_maturity":   70,
    "ltv_max": {                     # max loan-to-value by secured product
        "Home Loan":     0.80,
        "Vehicle Loan":  0.85,
        "Business Loan": 0.70,
    },
    "min_annual_income": {           # minimum income gate by product (INR)
        "Personal Loan":   300000,
        "Education Loan":  200000,
        "Vehicle Loan":    250000,
        "Home Loan":       500000,
        "Business Loan":   600000,
    },
    "single_borrower_cap":   20000000,   # exposure ceiling before committee
    "rm_unsecured_ceiling":  1000000,    # unsecured exposure RMs may hold
}

_SEVERITY_RANK = {"ELIGIBLE": 0, "REFER": 1, "DECLINE": 2}


def _worst(a, b):
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b


def evaluate(application: dict) -> dict:
    """
    Evaluate credit policy for one application (model-independent).

    Expected application keys (all optional — rules degrade gracefully):
        product, requested_amount, existing_exposure,
        annual_income, existing_monthly_obligations, proposed_emi, foir,
        collateral_value, applicant_age, tenure_years,
        kyc_status ('Verified'|...), sanctions_hit (bool), pep_flag (bool)
    """
    product   = application.get("product", "Personal Loan")
    requested = float(application.get("requested_amount") or application.get("exposure") or 0)
    existing  = float(application.get("existing_exposure") or 0)
    income    = float(application.get("annual_income") or 0)
    collateral = float(application.get("collateral_value") or 0)

    rules_fired = []
    flags = []
    decision = "ELIGIBLE"

    def fire(code, severity, detail, category="policy"):
        nonlocal decision
        rules_fired.append({"rule": code, "severity": severity,
                            "detail": detail, "category": category})
        decision = _worst(decision, severity)

    # ── 1. Financial-crime / KYC eligibility (hard gates) ──
    kyc = str(application.get("kyc_status", "Verified"))
    if application.get("sanctions_hit"):
        fire("AML_SANCTIONS_HIT", "DECLINE",
             "Sanctions/AML screening returned a match — mandatory financial-crime referral.",
             category="financial_crime")
        flags.append("FINANCIAL_CRIME_ESCALATION")
    if kyc.lower() not in ("verified", "complete", "completed"):
        fire("KYC_INCOMPLETE", "DECLINE",
             f"KYC status is '{kyc}' — onboarding cannot proceed until CDD is complete.",
             category="onboarding")
    if application.get("pep_flag"):
        fire("PEP_EDD_REQUIRED", "REFER",
             "Politically Exposed Person — Enhanced Due Diligence and senior sign-off required.",
             category="financial_crime")
        flags.append("EDD_REQUIRED")

    # ── 2. Affordability (FOIR / debt-service) ──
    foir = application.get("foir")
    if foir is None and income > 0:
        monthly_income = income / 12.0
        obligations = float(application.get("existing_monthly_obligations") or 0) \
            + float(application.get("proposed_emi") or 0)
        foir = obligations / monthly_income if monthly_income > 0 else None
    if foir is not None:
        foir = float(foir)
        if foir >= PARAMS["foir_decline"]:
            fire("FOIR_EXCEEDS_LIMIT", "DECLINE",
                 f"FOIR {foir*100:.0f}% ≥ {PARAMS['foir_decline']*100:.0f}% — debt-service burden unaffordable.")
        elif foir >= PARAMS["foir_refer"]:
            fire("FOIR_ELEVATED", "REFER",
                 f"FOIR {foir*100:.0f}% in {PARAMS['foir_refer']*100:.0f}–{PARAMS['foir_decline']*100:.0f}% review band.")

    # ── 3. Minimum income by product ──
    min_inc = PARAMS["min_annual_income"].get(product)
    if min_inc and income > 0 and income < min_inc:
        fire("INCOME_BELOW_MINIMUM", "REFER",
             f"Annual income ₹{income:,.0f} below ₹{min_inc:,.0f} minimum for {product}.")

    # ── 4. LTV on secured products ──
    ltv_max = PARAMS["ltv_max"].get(product)
    if ltv_max and collateral > 0 and requested > 0:
        ltv = requested / collateral
        if ltv > ltv_max:
            fire("LTV_EXCEEDS_LIMIT", "REFER",
                 f"LTV {ltv*100:.0f}% exceeds {ltv_max*100:.0f}% policy cap for {product} — "
                 f"reduce loan amount or add collateral.")

    # ── 5. Age / tenor ──
    age = application.get("applicant_age")
    tenure = float(application.get("tenure_years") or 0)
    if age is not None:
        age = float(age)
        if age < PARAMS["min_age"]:
            fire("AGE_BELOW_MINIMUM", "DECLINE",
                 f"Applicant age {age:.0f} below minimum {PARAMS['min_age']}.")
        elif age + tenure > PARAMS["max_age_at_maturity"]:
            fire("AGE_AT_MATURITY", "REFER",
                 f"Age at maturity {age+tenure:.0f} exceeds {PARAMS['max_age_at_maturity']} — "
                 f"shorten tenor or add co-applicant.")

    # ── 6. Exposure ceiling ──
    total_exposure = requested + existing
    max_exposure = PARAMS["single_borrower_cap"]
    if total_exposure > PARAMS["single_borrower_cap"]:
        fire("SINGLE_BORROWER_CAP", "REFER",
             f"Total exposure ₹{total_exposure:,.0f} exceeds single-borrower cap "
             f"₹{PARAMS['single_borrower_cap']:,.0f} — committee approval required.")
        flags.append("COMMITTEE_REQUIRED")

    return {
        "policy_version": POLICY_VERSION,
        "evaluated_at":   date.today().isoformat(),
        "decision":       decision,           # ELIGIBLE | REFER | DECLINE
        "rules_fired":    rules_fired,
        "flags":          sorted(set(flags)),
        "foir":           round(foir, 4) if foir is not None else None,
        "total_exposure": round(total_exposure, 2),
        "max_exposure":   max_exposure,
        "eligible":       decision != "DECLINE",
    }
