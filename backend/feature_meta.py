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
    # Trend features — defaults assume stable borrower (no deterioration, 24 months seasoning)
    "delta_de_ratio":            0.0,   # no change in leverage since origination
    "delta_cibil":               0.0,   # no change in credit score
    "months_since_origination": 24.0,   # typical mid-life loan observation
    # Macro regime delta features — defaults assume normal-cycle (no regime shift)
    "delta_gdp_pct":             0.0,   # pp change in GDP growth vs prior year
    "delta_cpi_pct":             0.0,   # pp change in CPI inflation vs prior year
    "delta_policy_rate_pct":     0.0,   # pp change in central bank policy rate
    "delta_unemployment_pct":    0.0,   # pp change in unemployment rate
    "macro_regime_score":        0.0,   # 0-100 composite distress score (0=normal, 56+=severe)
    # Transaction-derived behavioral features (added when the segmented models
    # were retrained on real transaction history - see
    # operations/scripts/build_behavioral_features.py). A brand-new applicant
    # has no transaction history yet, so these MUST default to what a typical
    # NON-defaulting existing customer looks like, not zero - a hard 0 here
    # (e.g. n_transactions=0, avg_balance=0) is wildly out-of-distribution for
    # a tree model trained on real accounts averaging ~40 transactions, and
    # was driving every live assessment's PD toward ~50-80% regardless of
    # borrower quality (confirmed: PD 81%->0.6% on an identical applicant just
    # by supplying these instead of letting them silently default to 0).
    # Values are blended averages across non-defaulting training rows.
    "emi_miss_ratio":            0.067,
    "income_miss_ratio":         0.037,
    "income_cv":                 0.207,
    "income_to_declared_ratio":  1.132,
    "balance_cv":                0.645,
    "max_gap_days":              29.0,
    "n_transactions":            41.0,
    "avg_balance":               3600000.0,
}

_MACRO_COLS = (
    'gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
    'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct',
    'delta_unemployment_pct', 'macro_regime_score',
)


def lookup_country_macro(country_code: str, db_path: str) -> dict:
    """Return macro + regime-delta features for a given ISO-3 country code.

    Queries the latest period in country_macro (which is CY2021 for COVID
    countries after add_macro_regime_score.py is run). Falls back to
    EXTRA_FEATURE_DEFAULTS when the country is not found.
    """
    import sqlite3, os
    result = {}
    if not country_code or not db_path or not os.path.exists(db_path):
        return result
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT gdp_growth_pct, inflation_cpi_pct, policy_rate_pct, unemployment_pct, "
            "       delta_gdp_pct, delta_cpi_pct, delta_policy_rate_pct, "
            "       delta_unemployment_pct, macro_regime_score "
            "FROM country_macro WHERE country_code = ? ORDER BY period DESC LIMIT 1",
            (country_code,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            keys = [
                'gdp_growth_pct', 'inflation_cpi_pct', 'policy_rate_pct', 'unemployment_pct',
                'delta_gdp_pct', 'delta_cpi_pct', 'delta_policy_rate_pct',
                'delta_unemployment_pct', 'macro_regime_score',
            ]
            for i, k in enumerate(keys):
                result[k] = float(row[i]) if row[i] is not None else EXTRA_FEATURE_DEFAULTS.get(k, 0.0)
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
