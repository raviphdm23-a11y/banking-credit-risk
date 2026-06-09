"""
Internal rating masterscale: maps model PD to a 10-grade scale aligned
to the SA external rating labels already used in StandardizedApproachCalculations.
"""

# ---------------------------------------------------------------------------
# Masterscale definition
# Each band: (grade, pd_low, pd_high, label, is_investment_grade, sa_equivalent)
# PD bounds are inclusive on the low end, exclusive on the high end.
# ---------------------------------------------------------------------------
_MASTERSCALE = [
    # grade   pd_low   pd_high  label               inv_grade  sa_equiv
    ("AAA",   0.0000,  0.0050,  "Exceptional",       True,     "AAA"),
    ("AA",    0.0050,  0.0100,  "Very Strong",        True,     "AA"),
    ("A",     0.0100,  0.0200,  "Strong",             True,     "A"),
    ("BBB",   0.0200,  0.0400,  "Adequate",           True,     "BBB"),
    ("BB",    0.0400,  0.0700,  "Speculative",        False,    "BB"),
    ("B",     0.0700,  0.1200,  "Vulnerable",         False,    "B"),
    ("CCC",   0.1200,  0.2000,  "Distressed",         False,    "CCC"),
    ("CC",    0.2000,  0.3500,  "Highly Distressed",  False,    "CC"),
    ("C",     0.3500,  0.5000,  "Near Default",       False,    "C"),
    ("D",     0.5000,  1.0001,  "Default",            False,    "D"),
]

# Decision thresholds (can be overridden via policy config)
APPROVE_GRADES   = {"AAA", "AA", "A", "BBB"}
REFER_GRADES     = {"BB", "B"}
DECLINE_GRADES   = {"CCC", "CC", "C", "D"}


def pd_to_grade(pd_value: float) -> dict:
    """
    Map a PD decimal (e.g. 0.045 for 4.5%) to an internal rating grade.

    Returns a dict with grade, label, pd_band_low, pd_band_high,
    sa_equivalent, is_investment_grade, default_decision.
    """
    pd_value = max(0.0, min(1.0, float(pd_value)))
    for grade, lo, hi, label, inv_grade, sa_equiv in _MASTERSCALE:
        if lo <= pd_value < hi:
            if grade in APPROVE_GRADES:
                decision = "APPROVE"
            elif grade in REFER_GRADES:
                decision = "REFER"
            else:
                decision = "DECLINE"
            return {
                "grade":              grade,
                "label":              label,
                "pd_band_low":        lo,
                "pd_band_high":       hi,
                "sa_equivalent":      sa_equiv,
                "is_investment_grade": inv_grade,
                "default_decision":   decision,
            }
    # Fallback — should never reach here given the final band covers to 1.0001
    return {
        "grade": "D", "label": "Default",
        "pd_band_low": 0.50, "pd_band_high": 1.0,
        "sa_equivalent": "D", "is_investment_grade": False,
        "default_decision": "DECLINE",
    }


def grade_description(grade: str) -> str:
    """Return a one-sentence narrative for a grade."""
    _desc = {
        "AAA": "Exceptional credit quality — highest confidence in debt repayment.",
        "AA":  "Very strong capacity to meet financial commitments; minimal default risk.",
        "A":   "Strong credit profile; minor susceptibility to adverse economic conditions.",
        "BBB": "Adequate credit quality; adverse conditions could weaken capacity.",
        "BB":  "Speculative grade — significant uncertainties; business risk exposure is present.",
        "B":   "Vulnerable; currently able to service debt but with deteriorating financial flexibility.",
        "CCC": "Currently distressed; dependent on favourable conditions to meet commitments.",
        "CC":  "Highly distressed; default appears probable without substantial restructuring.",
        "C":   "Near default; recovery of principal unlikely at full value.",
        "D":   "In default or likely to default imminently.",
    }
    return _desc.get(grade, "Unknown grade.")


def masterscale_table() -> list:
    """Return the full masterscale as a list of dicts (for API or admin display)."""
    return [
        {
            "grade":        g,
            "pd_band":      f"{lo*100:.2f}% – {hi*100:.2f}%",
            "label":        label,
            "investment_grade": inv,
            "sa_equivalent": sa,
            "default_decision": (
                "APPROVE" if g in APPROVE_GRADES
                else "REFER" if g in REFER_GRADES
                else "DECLINE"
            ),
        }
        for g, lo, hi, label, inv, sa in _MASTERSCALE
    ]
