"""
Risk-based pricing: converts EL%, RWA, and capital requirement into an
indicative lending rate and spread. All monetary values in INR (₹).

Methodology
-----------
Indicative Rate = Base Rate + EL Spread + Capital Charge Spread + Operating Margin

  Base Rate        — RBI repo rate (configurable; default 6.50%)
  EL Spread        — Expected Loss % (PD × LGD) expressed as bps; the bank must
                     earn at least this to break even on credit losses.
  Capital Charge   — (RWA × min_capital_ratio × target_ROE) / EAD; cost of holding
                     regulatory capital against this exposure.
  Operating Margin — Bank's cost-to-income contribution (default 150 bps).

The output is indicative / directional only. Actual pricing incorporates
relationship premium, competitive positioning, and treasury funding costs.
"""

# ---------------------------------------------------------------------------
# Default policy parameters (can be overridden per call)
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "base_rate_pct":       6.50,   # RBI repo (June 2026)
    "min_capital_ratio":   0.08,   # Basel III Pillar 1 minimum
    "target_roe_pct":      15.0,   # Bank's hurdle rate on equity
    "operating_margin_bps": 150,   # Operating cost allocation
    "floor_rate_pct":       7.0,   # Hard floor — never price below this
    "ceiling_rate_pct":    24.0,   # Hard ceiling — above this = unviable
}


def calculate_expected_loss(pd: float, lgd: float, ead: float) -> dict:
    """
    EL = PD × LGD × EAD

    Args:
        pd:  Probability of Default (decimal, e.g. 0.045)
        lgd: Loss Given Default (decimal, e.g. 0.25)
        ead: Exposure at Default in INR

    Returns dict with amount_inr, percentage, and the three inputs used.
    """
    pd  = max(0.0001, min(1.0, float(pd)))
    lgd = max(0.0,    min(1.0, float(lgd)))
    ead = max(0.0, float(ead))

    el_amount = pd * lgd * ead
    el_pct    = pd * lgd * 100  # percentage of EAD

    return {
        "amount_inr": round(el_amount, 2),
        "percentage": round(el_pct, 4),
        "pd_used":    round(pd, 6),
        "lgd_used":   round(lgd, 4),
        "ead_used":   round(ead, 2),
        "formula":    "PD × LGD × EAD",
    }


def calculate_capital_charge(rwa: float, ead: float,
                              min_capital_ratio: float = None,
                              target_roe_pct: float = None) -> dict:
    """
    Capital required = RWA × min_capital_ratio
    Cost of that capital = capital_required × target_ROE
    Expressed as a spread over EAD in basis points.

    Args:
        rwa:               Risk-weighted assets in INR
        ead:               Exposure at default in INR
        min_capital_ratio: Regulatory minimum (default 8%)
        target_roe_pct:    Bank's target ROE % (default 15%)

    Returns dict with capital_required_inr, spread_bps, spread_pct.
    """
    if min_capital_ratio is None:
        min_capital_ratio = _DEFAULTS["min_capital_ratio"]
    if target_roe_pct is None:
        target_roe_pct = _DEFAULTS["target_roe_pct"]

    rwa = max(0.0, float(rwa))
    ead = max(1.0, float(ead))  # avoid division by zero

    capital_required = rwa * min_capital_ratio
    capital_cost     = capital_required * (target_roe_pct / 100)

    spread_pct = (capital_cost / ead) * 100
    spread_bps = spread_pct * 100

    return {
        "capital_required_inr": round(capital_required, 2),
        "capital_cost_inr":     round(capital_cost, 2),
        "spread_bps":           round(spread_bps, 1),
        "spread_pct":           round(spread_pct, 4),
    }


def calculate_indicative_rate(el_pct: float,
                               capital_charge_bps: float,
                               base_rate_pct: float = None,
                               operating_margin_bps: float = None,
                               floor_rate_pct: float = None,
                               ceiling_rate_pct: float = None) -> dict:
    """
    Assemble the four components into an indicative all-in lending rate.

    Args:
        el_pct:               Expected Loss as % of EAD
        capital_charge_bps:   Capital cost spread in bps
        base_rate_pct:        Benchmark rate (default: RBI repo 6.50%)
        operating_margin_bps: Bank operating cost allocation in bps
        floor_rate_pct:       Hard floor on the rate
        ceiling_rate_pct:     Hard ceiling on the rate

    Returns dict with each component in bps and the all-in rate in %.
    """
    if base_rate_pct       is None: base_rate_pct       = _DEFAULTS["base_rate_pct"]
    if operating_margin_bps is None: operating_margin_bps = _DEFAULTS["operating_margin_bps"]
    if floor_rate_pct      is None: floor_rate_pct      = _DEFAULTS["floor_rate_pct"]
    if ceiling_rate_pct    is None: ceiling_rate_pct    = _DEFAULTS["ceiling_rate_pct"]

    el_bps               = el_pct * 100
    total_spread_bps     = el_bps + capital_charge_bps + operating_margin_bps
    indicative_rate_pct  = base_rate_pct + (total_spread_bps / 100)

    # Apply floor / ceiling
    clamped = max(floor_rate_pct, min(ceiling_rate_pct, indicative_rate_pct))
    clamped_note = None
    if indicative_rate_pct < floor_rate_pct:
        clamped_note = f"Rate floored at {floor_rate_pct:.2f}%"
    elif indicative_rate_pct > ceiling_rate_pct:
        clamped_note = f"Rate capped at {ceiling_rate_pct:.2f}% — exposure may be unviable"

    return {
        "base_rate_pct":        round(base_rate_pct, 2),
        "el_spread_bps":        round(el_bps, 1),
        "capital_charge_bps":   round(capital_charge_bps, 1),
        "operating_margin_bps": round(operating_margin_bps, 1),
        "total_spread_bps":     round(total_spread_bps, 1),
        "indicative_rate_pct":  round(clamped, 2),
        "unclamped_rate_pct":   round(indicative_rate_pct, 2),
        "basis": (
            f"RBI Repo {base_rate_pct:.2f}% "
            f"+ EL {el_bps:.0f}bps "
            f"+ Capital {capital_charge_bps:.0f}bps "
            f"+ Ops {operating_margin_bps:.0f}bps"
        ),
        "note": clamped_note,
    }


def full_pricing(pd: float, lgd: float, ead: float, rwa: float,
                 policy: dict = None) -> dict:
    """
    Convenience wrapper: compute EL, capital charge, and indicative rate
    in one call.

    Args:
        pd, lgd, ead, rwa: standard credit risk inputs
        policy: optional dict overriding any _DEFAULTS key

    Returns combined dict with el, capital_charge, and pricing sub-dicts.
    """
    p = {**_DEFAULTS, **(policy or {})}

    el      = calculate_expected_loss(pd, lgd, ead)
    cap     = calculate_capital_charge(rwa, ead,
                                       p["min_capital_ratio"],
                                       p["target_roe_pct"])
    pricing = calculate_indicative_rate(
        el["percentage"],
        cap["spread_bps"],
        p["base_rate_pct"],
        p["operating_margin_bps"],
        p["floor_rate_pct"],
        p["ceiling_rate_pct"],
    )

    return {
        "el":             el,
        "capital_charge": cap,
        "pricing":        pricing,
    }
