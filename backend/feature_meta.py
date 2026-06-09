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
