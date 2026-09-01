"""
bank_field_meta.py
────────────────────
Display metadata for the bank-specific fields auto-discovered by
ml_models.trainer's bank-scoped training (BANK011 Taiwan, BANK012 German) -
none of these exist in the canonical 37-feature schema (backend/feature_meta.py),
so borrower-info.html has no static input for them. Used by the
/api/bank-model-schema/<bank_id> route to tell the frontend what to render.

Three field kinds:
  - 'numeric':  plain number input
  - 'select':   dropdown; `options` is a list of {label, value} - `value` is
                the EXACT numeric code the trained model expects (for
                risk-ordered fields, this is the specific ranking learned
                at onboarding time - see each bank's onboard_*.py)
  - 'derived':  never shown as an input - computed client-side from other
                already-collected fields per `formula` (a plain description;
                the actual computation lives in borrower-info.html,
                mirroring the same formula used at onboarding time)

Risk-order values below are computed POST-HOC on each bank's full source
file (not the 5-fold out-of-fold encoding used during training/eval - that
variation existed only to prevent leakage into the *evaluation* metrics;
once training is done, a single fixed lookup is safe and necessary here so
live inference maps a selection to one stable code, not five slightly
different per-fold ones).
"""

# ── BANK011 (Taiwan) ─────────────────────────────────────────────────────────
_REPAY_STATUS_OPTIONS = [
    {"label": "Paid on time / no delay", "value": -1},
    {"label": "No revolving balance used this month", "value": -2},
    {"label": "Revolving credit used, minimum paid (no delay)", "value": 0},
    {"label": "1 month delinquent", "value": 1},
    {"label": "2 months delinquent", "value": 2},
    {"label": "3 months delinquent", "value": 3},
    {"label": "4 months delinquent", "value": 4},
    {"label": "5 months delinquent", "value": 5},
    {"label": "6 months delinquent", "value": 6},
    {"label": "7 months delinquent", "value": 7},
    {"label": "8 months delinquent", "value": 8},
    {"label": "9+ months delinquent", "value": 9},
]

BANK011_FIELDS = {
    "credit_limit": {"label": "Credit Limit", "kind": "numeric", "unit": "usd",
                      "help": "Total revolving credit line extended to this customer."},
    **{
        f"repay_status_m{i}": {
            "label": f"Repayment Status — {i} month{'s' if i > 1 else ''} ago",
            "kind": "select", "unit": "code", "options": _REPAY_STATUS_OPTIONS,
            "help": "m1 = most recent billing cycle.",
        } for i in range(1, 7)
    },
    **{
        f"bill_amt_m{i}": {
            "label": f"Bill Statement Amount — {i} month{'s' if i > 1 else ''} ago",
            "kind": "numeric", "unit": "usd",
        } for i in range(1, 7)
    },
    **{
        f"payment_amt_m{i}": {
            "label": f"Payment Made — {i} month{'s' if i > 1 else ''} ago",
            "kind": "numeric", "unit": "usd",
        } for i in range(1, 7)
    },
    "credit_utilization_ratio": {
        "label": "Credit Utilization Ratio", "kind": "derived",
        "formula": "bill_amt_m1 / credit_limit",
        "requires": ["bill_amt_m1", "credit_limit"],
    },
    "payment_coverage_ratio": {
        "label": "Payment Coverage Ratio", "kind": "derived",
        "formula": "average(payment_amt_mX / bill_amt_mX for X in 1..6, skipping months where bill_amt_mX <= 0)",
        "requires": [f"payment_amt_m{i}" for i in range(1, 7)] + [f"bill_amt_m{i}" for i in range(1, 7)],
    },
}

# ── BANK012 (German) ─────────────────────────────────────────────────────────
# Risk-order values computed post-hoc on the full german_credit_record.csv
# (1,000 rows) - see the conversation this was built in for the exact
# reproduction command. These are fixed production lookups, not re-derived
# per request.
_CHECKING_STATUS_OPTIONS = [
    {"label": "No checking account", "value": 1},
    {"label": "≥ 200 DM / salary assignment ≥ 1 year", "value": 2},
    {"label": "0 to 200 DM", "value": 3},
    {"label": "Overdrawn (< 0 DM)", "value": 4},
]
_CREDIT_HISTORY_OPTIONS = [
    {"label": "Critical account / credits elsewhere", "value": 1},
    {"label": "Delay in past", "value": 2},
    {"label": "Existing credits paid duly till now", "value": 3},
    {"label": "All credits at this bank paid duly", "value": 4},
    {"label": "No credits taken / all paid duly", "value": 5},
]
_SAVINGS_STATUS_OPTIONS = [
    {"label": "≥ 1000 DM", "value": 1},
    {"label": "500 to 1000 DM", "value": 2},
    {"label": "Unknown / no savings account", "value": 3},
    {"label": "100 to 500 DM", "value": 4},
    {"label": "< 100 DM", "value": 5},
]
_OTHER_DEBTORS_OPTIONS = [
    {"label": "Guarantor", "value": 1},
    {"label": "None", "value": 2},
    {"label": "Co-applicant", "value": 3},
]
_PROPERTY_OPTIONS = [
    {"label": "Real estate", "value": 1},
    {"label": "Building society savings / life insurance", "value": 2},
    {"label": "Car or other (not savings)", "value": 3},
    {"label": "Unknown / none", "value": 4},
]
_OTHER_INSTALLMENT_PLANS_OPTIONS = [
    {"label": "None", "value": 1},
    {"label": "Other stores", "value": 2},
    {"label": "Another bank", "value": 3},
]
_INSTALLMENT_RATE_BAND_OPTIONS = [
    {"label": "Band 1 (lowest burden)", "value": 1},
    {"label": "Band 2", "value": 2},
    {"label": "Band 3", "value": 3},
    {"label": "Band 4 (highest burden)", "value": 4},
]
_YES_NO_OPTIONS = [{"label": "No", "value": 0}, {"label": "Yes", "value": 1}]

BANK012_FIELDS = {
    "checking_account_status_enc": {"label": "Checking Account Status", "kind": "select", "options": _CHECKING_STATUS_OPTIONS},
    "credit_history_enc":          {"label": "Credit History", "kind": "select", "options": _CREDIT_HISTORY_OPTIONS},
    "requested_loan_amount":       {"label": "Requested Loan Amount", "kind": "numeric", "unit": "usd"},
    "savings_status_enc":          {"label": "Savings Account Status", "kind": "select", "options": _SAVINGS_STATUS_OPTIONS},
    "installment_rate_band":       {"label": "Installment Rate Band", "kind": "select", "options": _INSTALLMENT_RATE_BAND_OPTIONS,
                                     "help": "Installment as a % of disposable income, banded (not a literal percentage)."},
    "other_debtors_enc":           {"label": "Other Debtors / Guarantors", "kind": "select", "options": _OTHER_DEBTORS_OPTIONS},
    "property_type_enc":           {"label": "Property Owned", "kind": "select", "options": _PROPERTY_OPTIONS},
    "other_installment_plans_enc": {"label": "Other Installment Plans Elsewhere", "kind": "select", "options": _OTHER_INSTALLMENT_PLANS_OPTIONS},
    "has_registered_phone":        {"label": "Has Registered Phone", "kind": "select", "options": _YES_NO_OPTIONS},
    "loan_duration_months":        {"label": "Loan Duration (months)", "kind": "numeric", "unit": "months"},
}

# ── BANK013 (US HELOC Reference Bank) ────────────────────────────────────────
# Pure bureau/trade-line data - all numeric, no encoded categoricals (no
# risk-order lookups needed, unlike BANK012's fields).
BANK013_FIELDS = {
    "external_risk_score":              {"label": "External Risk Score (FICO-style)", "kind": "numeric",
                                          "help": "Higher = lower risk. Typical range 30-95."},
    "months_since_oldest_trade":        {"label": "Months Since Oldest Trade Opened", "kind": "numeric", "unit": "months"},
    "months_since_recent_trade":        {"label": "Months Since Most Recent Trade Opened", "kind": "numeric", "unit": "months"},
    "avg_months_in_file":               {"label": "Average Months in File", "kind": "numeric", "unit": "months"},
    "num_satisfactory_trades":          {"label": "Number of Satisfactory Trades", "kind": "numeric"},
    "num_trades_60d_derog":             {"label": "Trades 60+ Days Derogatory (Ever)", "kind": "numeric"},
    "num_trades_90d_derog":             {"label": "Trades 90+ Days Derogatory (Ever)", "kind": "numeric"},
    "pct_trades_never_delinquent":      {"label": "% Trades Never Delinquent", "kind": "numeric", "unit": "pct"},
    "months_since_recent_delinquency":  {"label": "Months Since Most Recent Delinquency", "kind": "numeric", "unit": "months",
                                          "help": "Leave blank if never delinquent."},
    "max_delinquency_12m":              {"label": "Max Delinquency (Last 12 Months)", "kind": "numeric"},
    "max_delinquency_ever":             {"label": "Max Delinquency Ever", "kind": "numeric"},
    "num_total_trades":                 {"label": "Total Number of Trades", "kind": "numeric"},
    "num_trades_opened_12m":            {"label": "Trades Opened (Last 12 Months)", "kind": "numeric"},
    "pct_installment_trades":           {"label": "% Installment Trades", "kind": "numeric", "unit": "pct"},
    "months_since_recent_inquiry":      {"label": "Months Since Most Recent Inquiry", "kind": "numeric", "unit": "months"},
    "num_inquiries_6m":                 {"label": "Credit Inquiries (Last 6 Months)", "kind": "numeric"},
    "num_inquiries_6m_excl7d":          {"label": "Credit Inquiries (Last 6mo, excl. 7 days)", "kind": "numeric"},
    "net_fraction_revolving_burden":    {"label": "Net Revolving Burden (%)", "kind": "numeric", "unit": "pct"},
    "net_fraction_installment_burden":  {"label": "Net Installment Burden (%)", "kind": "numeric", "unit": "pct"},
    "num_revolving_trades_w_balance":   {"label": "Revolving Trades with Balance", "kind": "numeric"},
    "num_installment_trades_w_balance": {"label": "Installment Trades with Balance", "kind": "numeric"},
    "num_trades_high_utilization":      {"label": "Trades with High Utilization", "kind": "numeric"},
    "pct_trades_w_balance":             {"label": "% Trades with Balance", "kind": "numeric", "unit": "pct"},
}

# ── BANK014 (US Personal Loan Reference Bank) ────────────────────────────────
# Category labels are INFERRED (standard alphabetical LabelEncoder
# convention for this well-known Kaggle dataset), moderate confidence - see
# onboard_credit_risk.py's docstring. A wrong label guess only affects this
# dropdown caption, never the underlying stored integer.
_LOAN_GRADE_OPTIONS = [{"label": f"Grade {chr(65+i)}", "value": i + 1} for i in range(7)]  # A..G

BANK014_FIELDS = {
    "requested_loan_amount":       {"label": "Requested Loan Amount", "kind": "numeric", "unit": "usd"},
    "loan_grade_enc":              {"label": "Loan Grade", "kind": "select", "options": _LOAN_GRADE_OPTIONS,
                                     "help": "Inferred grade labels A (best) - G (worst), moderate confidence."},
    "loan_interest_rate_pct":      {"label": "Interest Rate (%)", "kind": "numeric", "unit": "pct"},
    "loan_to_income_ratio":        {"label": "Loan-to-Income Ratio", "kind": "numeric",
                                     "help": "Loan amount as a fraction of annual income (e.g. 0.17 = 17%)."},
    "credit_history_length_years": {"label": "Credit History Length (years)", "kind": "numeric", "unit": "years"},
}

# ── BANK015 (US Home Equity Reference Bank) ──────────────────────────────────
# mortgage_balance/home_value are SHARED with BANK016 - same metadata entry
# repeated in both banks' dicts (the DB column is shared; only the display
# metadata needs repeating per bank).
BANK015_FIELDS = {
    "requested_loan_amount":         {"label": "Requested Loan Amount", "kind": "numeric", "unit": "usd"},
    "mortgage_balance":               {"label": "Existing Mortgage Balance", "kind": "numeric", "unit": "usd"},
    "home_value":                     {"label": "Current Property Value", "kind": "numeric", "unit": "usd"},
    "num_derogatory_reports":         {"label": "Major Derogatory Reports", "kind": "numeric"},
    "num_delinquent_lines":           {"label": "Delinquent Credit Lines", "kind": "numeric"},
    "oldest_credit_line_age_months":  {"label": "Age of Oldest Credit Line (months)", "kind": "numeric", "unit": "months"},
    "num_recent_inquiries":           {"label": "Recent Credit Inquiries", "kind": "numeric"},
    "num_credit_lines":               {"label": "Number of Credit Lines", "kind": "numeric"},
}

# ── BANK016 (UK Consumer Credit Reference Bank) ──────────────────────────────
BANK016_FIELDS = {
    "has_registered_phone":               {"label": "Has Registered Phone", "kind": "select", "options": _YES_NO_OPTIONS},
    "mortgage_balance":                   {"label": "Existing Mortgage Balance", "kind": "numeric", "unit": "usd"},
    "home_value":                         {"label": "Current Property Value", "kind": "numeric", "unit": "usd"},
    "year_of_birth_2digit":               {"label": "Year of Birth (2-digit)", "kind": "numeric",
                                            "help": "Raw 2-digit year as recorded - reference century not confirmed, not converted to age."},
    "num_additional_dependents":          {"label": "Additional Dependents", "kind": "numeric",
                                            "help": "Beyond number of children."},
    "spouse_income":                      {"label": "Spouse Income", "kind": "numeric", "unit": "usd"},
    "outstanding_debt_mortgage_related":  {"label": "Outstanding Debt - Mortgage-Related", "kind": "numeric", "unit": "usd"},
    "outstanding_debt_other_loan":        {"label": "Outstanding Debt - Other Loans", "kind": "numeric", "unit": "usd"},
    "outstanding_debt_hire_purchase":     {"label": "Outstanding Debt - Hire Purchase", "kind": "numeric", "unit": "usd"},
    "outstanding_debt_credit_card":       {"label": "Outstanding Debt - Credit Card", "kind": "numeric", "unit": "usd"},
}

BANK_FIELD_META = {
    "BANK010": {},  # Bradesco has no auto-discovered fields beyond canonical
    "BANK011": BANK011_FIELDS,
    "BANK012": BANK012_FIELDS,
    "BANK013": BANK013_FIELDS,
    "BANK014": BANK014_FIELDS,
    "BANK015": BANK015_FIELDS,
    "BANK016": BANK016_FIELDS,
}
