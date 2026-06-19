"""
Shared feature metadata constants — imported by both assessment_engine and explainability
to avoid a circular import.
"""

FEATURE_ORDER = ["de_ratio", "interest_coverage", "profitability", "liquidity_ratio"]

FEATURE_META = {
    "de_ratio": {
        "display_name":  "Debt-to-Equity Ratio",
        "unit":          "ratio",
        "baseline":      1.20,
        "healthy_max":   2.0,
        "risk_direction": "higher_is_worse",
        "five_c":        "capacity",
        "reason_high":   "HIGH_LEVERAGE",
        "reason_low":    None,
        "bench_label":   "<= 2.0x",
    },
    "interest_coverage": {
        "display_name":  "Interest Coverage Ratio",
        "unit":          "ratio",
        "baseline":      6.00,
        "healthy_min":   3.0,
        "risk_direction": "lower_is_worse",
        "five_c":        "capacity",
        "reason_high":   None,
        "reason_low":    "THIN_COVERAGE",
        "bench_label":   ">= 3.0x",
    },
    "profitability": {
        "display_name":  "Net Profit Margin (%)",
        "unit":          "percent",
        "baseline":      12.0,
        "healthy_min":   8.0,
        "risk_direction": "lower_is_worse",
        "five_c":        "capital",
        "reason_high":   None,
        "reason_low":    "WEAK_PROFITABILITY",
        "bench_label":   ">= 8%",
    },
    "liquidity_ratio": {
        "display_name":  "Current Ratio (Liquidity)",
        "unit":          "ratio",
        "baseline":      1.60,
        "healthy_min":   1.5,
        "risk_direction": "lower_is_worse",
        "five_c":        "capital",
        "reason_high":   None,
        "reason_low":    "LOW_LIQUIDITY",
        "bench_label":   ">= 1.5x",
    },
}

# The active model was retrained on a wider 21-feature schema (the 4 ratios above
# plus borrower/bureau attributes). The 4 ratios remain the explainable drivers;
# the remaining features are filled from these neutral defaults (or from the
# application when the value is supplied), keeping the model vector aligned with
# whatever `model.feature_names_in_` the deployed pickle expects.
EXTRA_FEATURE_DEFAULTS = {
    "age":                       40.0,
    "employment_type_enc":       1.0,
    "years_employed":            6.0,
    "annual_income":             800000.0,
    "foir":                      0.40,
    "num_dependents":            1.0,
    "city_tier_enc":             1.0,
    "education_enc":             2.0,
    "residence_type_enc":        1.0,
    "loan_purpose_enc":          1.0,
    "cibil_score":               720.0,
    "previous_default_flag":     0.0,
    "months_as_customer":        36.0,
    "num_late_payments_past_12m": 0.0,
    "existing_loans_count":      1.0,
    "num_existing_products":     2.0,
    "is_rural":                  0.0,
    # Country macro — global medians used as fallback when country_code is unknown
    "gdp_growth_pct":            4.0,   # % — blended emerging/developed median
    "inflation_cpi_pct":         4.5,   # %
    "policy_rate_pct":           5.0,   # %
    "unemployment_pct":          6.0,   # %
}

_MACRO_COLS = ('gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct')


def lookup_country_macro(country_code: str, db_path: str) -> dict:
    """Return macro feature dict for a given ISO-3 country code from bank.db.

    Queries the latest period in country_macro. Falls back to EXTRA_FEATURE_DEFAULTS
    values when the country is not found.
    """
    import sqlite3, os
    result = {}
    if not country_code or not db_path or not os.path.exists(db_path):
        return result
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct "
            "FROM country_macro WHERE country_code = ? ORDER BY period DESC LIMIT 1",
            (country_code,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            result['gdp_growth_pct']    = float(row[0]) if row[0] is not None else EXTRA_FEATURE_DEFAULTS['gdp_growth_pct']
            result['inflation_cpi_pct'] = float(row[1]) if row[1] is not None else EXTRA_FEATURE_DEFAULTS['inflation_cpi_pct']
            result['policy_rate_pct']   = float(row[2]) if row[2] is not None else EXTRA_FEATURE_DEFAULTS['policy_rate_pct']
            result['unemployment_pct']  = float(row[3]) if row[3] is not None else EXTRA_FEATURE_DEFAULTS['unemployment_pct']
    except Exception:
        pass
    return result


def model_feature_frame(inputs: dict, model=None):
    """Build a single-row DataFrame aligned to the model's expected feature set.

    Uses ``model.feature_names_in_`` when available (so it tracks whatever schema
    the deployed pickle was trained on); otherwise falls back to the 4 ratios.
    Missing values come from the application, then FEATURE_META baselines, then
    EXTRA_FEATURE_DEFAULTS.
    """
    import pandas as pd
    names_attr = getattr(model, "feature_names_in_", None)
    names = list(names_attr) if names_attr is not None and len(names_attr) > 0 else list(FEATURE_ORDER)

    def _val(name):
        if name in inputs and inputs[name] is not None:
            try:
                return float(inputs[name])
            except (TypeError, ValueError):
                pass
        if name in FEATURE_META:
            return float(FEATURE_META[name]["baseline"])
        return float(EXTRA_FEATURE_DEFAULTS.get(name, 0.0))

    return pd.DataFrame([{n: _val(n) for n in names}])[names]
