"""
Comprehensive case report system: analysis, visualization, and LaTeX/PDF generation.

This module contains the complete pipeline for generating per-case financial advisory reports:
  - Feature metadata and actionability scoring
  - Counterfactual recourse analysis
  - Visualization functions for charts and gauges
  - LaTeX/PDF report builder

Typical usage:
  from case_report_builder import analyse_case, CaseReportBuilder
  findings = analyse_case(case_dict, preprocessor, models, approved_raw, approved_enc)
  builder = CaseReportBuilder(case_id, findings, preprocessor, calibration)
  pdf_path = builder.build()
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, FancyBboxPatch
from matplotlib import patheffects

from tabular_preprocessing import drop_id_columns, build_preprocessor

warnings.filterwarnings('ignore')

MODELS_BASE = Path('output')

# ============================================================================
# PREPROCESSOR WRAPPER: Handle both dictionary and ColumnTransformer formats
# ============================================================================

def _normalize_preprocessor(preprocessor):
    """Convert ColumnTransformer or dict preprocessor to standardized dict format."""
    if isinstance(preprocessor, dict):
        return preprocessor

    # Handle ColumnTransformer object
    from sklearn.compose import ColumnTransformer
    if isinstance(preprocessor, ColumnTransformer):
        try:
            feature_names = preprocessor.get_feature_names_out().tolist()
        except:
            feature_names = []

        return {
            'raw_feature_names': feature_names,
            'feature_names': feature_names,
            'categorical_cols': [],
            'categorical_levels': {},
            'preprocessor': preprocessor
        }

    return preprocessor

DATASET_LABELS = {
    'german':   'German Credit Risk Dataset',
    'taiwan':   'Taiwan Credit Default Dataset',
    'approval': 'Credit Approval Dataset',
}

# ============================================================================
# COLUMN MAPPING: Original Names → Standardized Names
# ============================================================================

def load_five_cs_mapping():
    """Load the Five C's standardization mapping file."""
    mapping_file = Path('metadata') / 'five_cs_columns_mapping.csv'
    if not mapping_file.exists():
        print(f"[WARN] Mapping file not found: {mapping_file}")
        return None
    try:
        return pd.read_csv(mapping_file)
    except Exception as e:
        print(f"[WARN] Could not load mapping file: {e}")
        return None


def map_use_case_columns(df, mapping_df=None):
    """
    Map use case column names to standardized names.

    For each column in df:
    - If it's already a standardized_name → keep it
    - If it matches an original_name → map to standardized_name
    - Otherwise → raise error

    Args:
        df: Use case DataFrame with potentially mixed column names
        mapping_df: Five C's mapping DataFrame (loaded if None)

    Returns:
        DataFrame with standardized column names
    """
    if mapping_df is None:
        mapping_df = load_five_cs_mapping()
        if mapping_df is None:
            print("[WARN] No mapping available. Assuming columns are already standardized.")
            return df

    # Build mapping dictionaries
    original_to_standard = {}  # original_name → standardized_name
    standardized_names = set()  # Set of all standardized_name values

    for _, row in mapping_df.iterrows():
        original = row['original_name']
        standardized = row['standardized_name']
        original_to_standard[original] = standardized
        standardized_names.add(standardized)

    # Map each column
    column_mapping = {}  # old_name → new_name
    unmapped_cols = []

    for col in df.columns:
        if col in standardized_names:
            # Already standardized
            column_mapping[col] = col
        elif col in original_to_standard:
            # Original name → map to standardized
            column_mapping[col] = original_to_standard[col]
        else:
            # Unknown column
            unmapped_cols.append(col)

    if unmapped_cols:
        print(f"[WARN] Could not map columns: {unmapped_cols}")
        print("       These columns will be kept as-is")
        for col in unmapped_cols:
            column_mapping[col] = col

    # Rename columns
    df_mapped = df.rename(columns=column_mapping)

    if column_mapping:
        mapped_cols = [col for old, col in column_mapping.items() if old != col]
        if mapped_cols:
            print(f"[OK] Mapped {len(mapped_cols)} columns to standardized names")

    return df_mapped

# ============================================================================
# FEATURE METADATA & PATHWAYS
# ============================================================================

PATHWAY_A = 'restructure'
PATHWAY_B = 'routine'
PATHWAY_C = 'longterm'
PATHWAY_X = 'fixed'

PATHWAY_LABELS = {
    PATHWAY_A: 'Restructure the Request',
    PATHWAY_B: 'Build Financial Routine',
    PATHWAY_C: 'Strengthen Long-term Profile',
    PATHWAY_X: 'Not actionable',
}

PATHWAY_DESCRIPTIONS = {
    PATHWAY_A: 'Immediate changes to the loan itself — duration, amount, purpose. '
               'Low effort, no waiting period, but limited impact ceiling.',
    PATHWAY_B: 'Establish routine financial behaviour visible to lenders — '
               'a checking account, documented savings, paying down small debts. '
               'Medium effort, 1–6 month horizon.',
    PATHWAY_C: 'Structural improvements to your overall profile — employment '
               'tenure, paying off existing credits, reducing installment burden. '
               'Higher effort, 6–12 month horizon, biggest cumulative impact.',
}

_FEATURE_TABLE = {
    'checking_status': {
        'display':  'Checking account status',
        'actionable': True,
        'pathway':  PATHWAY_B,
        'time_months': (1, 3),
        'difficulty': 1,
        'why': "An active checking account is the most basic signal of financial "
               "routine to a lender. Borrowers without one appear higher-risk "
               "even when other indicators are strong.",
        'how': "Open a checking account at any local bank and use it regularly for "
               "salary, bills, and day-to-day expenses for at least 3 months "
               "before reapplying. Keep the balance positive throughout.",
    },
    'duration': {
        'display':  'Loan duration (months)',
        'actionable': True,
        'pathway':  PATHWAY_A,
        'time_months': (0, 0),
        'difficulty': 1,
        'why': "Shorter loans are statistically less risky because there is less "
               "time for your financial circumstances to change. Lenders price "
               "this in directly.",
        'how': "Request a shorter loan duration when you reapply. If the monthly "
               "payment becomes too high, consider also reducing the loan amount.",
    },
    'credit_history': {
        'display':  'Credit history',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Your existing credit history with this bank is fixed and reflects "
               "how previous credits were managed. It cannot be changed retroactively.",
        'how': "Going forward, pay every installment on time. Each clean year "
               "gradually improves how lenders read this signal.",
    },
    'purpose': {
        'display':  'Loan purpose',
        'actionable': True,
        'pathway':  PATHWAY_A,
        'time_months': (0, 0),
        'difficulty': 2,
        'why': "Lenders categorise loan purposes by historical default rates. "
               "Education, car, and household goods loans typically score better "
               "than 'other' or unspecified purposes.",
        'how': "If your loan can be reframed under a more specific approved "
               "category (e.g. car purchase, home improvement), do so. Be honest "
               "but precise.",
    },
    'credit_amount': {
        'display':  'Credit amount requested',
        'actionable': True,
        'pathway':  PATHWAY_A,
        'time_months': (0, 0),
        'difficulty': 1,
        'why': "Larger loans relative to income are riskier from the lender's "
               "view. Right-sizing the request can be the single fastest way to "
               "improve approval odds.",
        'how': "Reduce the requested amount to the minimum you actually need, "
               "and provide supporting documentation for the use of funds.",
    },
    'savings_status': {
        'display':  'Savings balance',
        'actionable': True,
        'pathway':  PATHWAY_B,
        'time_months': (3, 12),
        'difficulty': 2,
        'why': "Documented savings act as a buffer against repayment difficulty "
               "and are strong evidence of financial discipline.",
        'how': "Open a savings account and set up an automatic transfer of "
               "even a small monthly amount. Three to six months of consistent "
               "deposits creates a visible track record.",
    },
    'employment': {
        'display':  'Employment tenure',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (12, 48),
        'difficulty': 4,
        'why': "Longer tenure with the same employer signals income stability, "
               "which directly reduces perceived default risk.",
        'how': "Stay in your current role and document the tenure. If a "
               "change is unavoidable, prefer moves within the same industry "
               "without gaps.",
    },
    'installment_commitment': {
        'display':  'Installment as % of income',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (3, 6),
        'difficulty': 3,
        'why': "A high installment-to-income ratio leaves little buffer for "
               "unexpected expenses, which lenders read as elevated risk.",
        'how': "Reduce other monthly obligations first (consolidate debts, "
               "close unused credit lines, pay off small balances) so that the "
               "new installment occupies a smaller share of your income.",
    },
    'personal_status': {
        'display':  'Personal status',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Personal/marital status is a feature lenders observe but it is "
               "not something to change for credit reasons.",
        'how': "No action recommended on this basis.",
    },
    'other_parties': {
        'display':  'Other parties on the loan',
        'actionable': True,
        'pathway':  PATHWAY_A,
        'time_months': (0, 1),
        'difficulty': 2,
        'why': "Having a co-applicant or guarantor materially lowers lender "
               "risk because there is a second source of repayment.",
        'how': "If a creditworthy family member or partner is willing to "
               "co-sign or act as guarantor, this can dramatically change the "
               "lender's view.",
    },
    'residence_since': {
        'display':  'Years at current address',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (12, 24),
        'difficulty': 4,
        'why': "Length of residence is a proxy for stability. Frequent moves "
               "are read as higher risk.",
        'how': "Stay at your current address and document the duration. This "
               "feature improves naturally over time.",
    },
    'property_magnitude': {
        'display':  'Property holdings',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (12, 60),
        'difficulty': 5,
        'why': "Owning property (real estate, life insurance, savings policy) "
               "demonstrates asset accumulation and provides implicit collateral.",
        'how': "Building property holdings is a long-term project. In the "
               "near term, ensure any property you do own is properly "
               "documented and disclosed.",
    },
    'age': {
        'display':  'Age',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Age is observed by lenders but is not actionable. Younger "
               "applicants often score lower because of shorter overall credit "
               "and employment histories.",
        'how': "Other features can compensate for age. Focus on the "
               "actionable items in your roadmap.",
    },
    'other_payment_plans': {
        'display':  'Other payment plans',
        'actionable': True,
        'pathway':  PATHWAY_B,
        'time_months': (1, 6),
        'difficulty': 2,
        'why': "Existing installment plans elsewhere reduce your available "
               "income for the new loan, which lenders see as competing claims "
               "on your monthly cash flow.",
        'how': "Pay off or close any small open payment plans before reapplying. "
               "Even one closed plan can change how this signal reads.",
    },
    'housing': {
        'display':  'Housing situation',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (6, 24),
        'difficulty': 4,
        'why': "Owning your home is the strongest housing signal; renting is "
               "neutral; living rent-free with family is often read as a "
               "stability question by lenders.",
        'how': "If you live with family, formalising a rental arrangement "
               "with documented payments can shift this signal. Owning is a "
               "long-term goal.",
    },
    'existing_credits': {
        'display':  'Existing credits at this bank',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (6, 24),
        'difficulty': 4,
        'why': "More existing credits at the same bank can be read either way: "
               "a track record of repayment is positive, but high current "
               "exposure is negative.",
        'how': "Pay down or close any low-balance existing credits before "
               "applying for a new one, so your total exposure looks lower.",
    },
    'job': {
        'display':  'Job classification',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (12, 60),
        'difficulty': 4,
        'why': "Job category (skilled, unskilled, management) is observed and "
               "weighed by lenders. Career progression takes years and is not "
               "a short-term lever for this loan.",
        'how': "No action recommended for this specific loan application.",
    },
    'num_dependents': {
        'display':  'Number of dependents',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Number of dependents affects disposable income from the "
               "lender's view, but is not a credit-strategy lever.",
        'how': "No action recommended on this basis.",
    },
    'own_telephone': {
        'display':  'Registered telephone',
        'actionable': True,
        'pathway':  PATHWAY_B,
        'time_months': (1, 1),
        'difficulty': 1,
        'why': "A registered telephone is a small but real signal of "
               "stability and reachability — historically a contact-traceability "
               "indicator that still factors into some models.",
        'how': "Register a landline or fixed contact number under your own "
               "name before reapplying.",
    },
    'foreign_worker': {
        'display':  'Foreign worker status',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "This is a static demographic feature observed by lenders but "
               "not actionable.",
        'how': "No action recommended on this basis.",
    },
    'LIMIT_BAL': {
        'display':  'Credit limit',
        'actionable': True,
        'pathway':  PATHWAY_A,
        'time_months': (0, 3),
        'difficulty': 2,
        'why': "A lower credit limit relative to your income reduces lender "
               "exposure and improves approval odds for a new credit line.",
        'how': "Request a lower credit limit on your existing cards before "
               "reapplying.",
    },
    'SEX': {
        'display':  'Sex',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Demographic feature, not actionable.",
        'how': "No action recommended on this basis.",
    },
    'EDUCATION': {
        'display':  'Education level',
        'actionable': True,
        'pathway':  PATHWAY_C,
        'time_months': (12, 60),
        'difficulty': 5,
        'why': "Higher education levels statistically correlate with lower "
               "default rates in this dataset.",
        'how': "Long-term lever only. For the current application, focus on "
               "more immediately actionable features.",
    },
    'MARRIAGE': {
        'display':  'Marital status',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Demographic feature, not a credit-strategy lever.",
        'how': "No action recommended on this basis.",
    },
    'AGE': {
        'display':  'Age',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Static demographic feature.",
        'how': "Other features can compensate.",
    },
    'grade': {
        'display':  'Credit risk grade',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Your credit grade (A-G) is Lending Club's summary assessment of "
               "your overall creditworthiness based on your credit history, income, "
               "debt-to-income ratio, and payment behavior. It cannot be changed "
               "directly; it reflects accumulated financial history.",
        'how': "Work on improving the underlying factors: pay all bills on time, "
               "reduce debt balances, maintain low credit utilization, and avoid "
               "excessive credit inquiries. As these improve over 6-12 months, "
               "your grade will improve.",
    },
    'sub_grade': {
        'display':  'Credit risk sub-grade',
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 5,
        'why': "Your sub-grade (A1-G5) is a refinement of your letter grade, "
               "providing finer-grained risk assessment. Like the main grade, "
               "it's derived from your overall credit profile and cannot be "
               "directly changed.",
        'how': "Focus on the actionable features that feed into grading: maintain "
               "on-time payments, reduce outstanding balances, lower your "
               "debt-to-income ratio, and minimize new credit inquiries. "
               "Steady improvement over 6-12 months will shift you to a better "
               "sub-grade.",
    },
}

_TAIWAN_PAY_TEMPLATE = {
    'actionable': True,
    'pathway':  PATHWAY_B,
    'time_months': (3, 12),
    'difficulty': 3,
    'why': "Recent repayment history is the strongest single signal of credit "
           "risk. Even one or two consecutive on-time months meaningfully "
           "improves the read.",
    'how': "Pay the minimum due on time for the next 3–6 consecutive months "
           "before reapplying. Avoid any rolled-over balances if possible.",
}
_TAIWAN_BILL_TEMPLATE = {
    'actionable': True,
    'pathway':  PATHWAY_B,
    'time_months': (3, 12),
    'difficulty': 3,
    'why': "High outstanding bill amounts increase your debt-to-limit ratio, "
           "a strong negative signal.",
    'how': "Reduce outstanding balances on existing cards. Target a utilisation "
           "ratio below 30% of the credit limit.",
}
_TAIWAN_PAYAMT_TEMPLATE = {
    'actionable': True,
    'pathway':  PATHWAY_B,
    'time_months': (1, 6),
    'difficulty': 2,
    'why': "Higher payment amounts (relative to bills) signal active debt "
           "reduction rather than minimum-payment behaviour.",
    'how': "Where possible, pay more than the minimum due each month. Even "
           "small over-payments compound into a visibly healthier pattern.",
}

for i in range(7):
    _FEATURE_TABLE[f'PAY_{i}'] = {**_TAIWAN_PAY_TEMPLATE,
                                   'display': f'Repayment status (month {i})'}
    _FEATURE_TABLE[f'BILL_AMT{i+1}'] = {**_TAIWAN_BILL_TEMPLATE,
                                         'display': f'Bill amount (month {i+1})'}
    _FEATURE_TABLE[f'PAY_AMT{i+1}'] = {**_TAIWAN_PAYAMT_TEMPLATE,
                                        'display': f'Payment amount (month {i+1})'}

def get_meta(feature_name):
    """Return the metadata dict for a feature, or a safe default for unknowns."""
    if feature_name in _FEATURE_TABLE:
        return _FEATURE_TABLE[feature_name]
    return {
        'display':  feature_name.replace('_', ' ').title(),
        'actionable': False,
        'pathway':  PATHWAY_X,
        'time_months': (0, 0),
        'difficulty': 3,
        'why': "No specific guidance available for this feature.",
        'how': "Consult a financial adviser for personalised advice.",
    }

def is_actionable(feature_name):
    return get_meta(feature_name)['actionable']

def display_name(feature_name):
    return get_meta(feature_name)['display']

def time_range_text(feature_name):
    lo, hi = get_meta(feature_name)['time_months']
    if lo == 0 and hi == 0:
        return "Immediate"
    if lo == hi:
        return f"{lo} month{'s' if lo != 1 else ''}"
    return f"{lo}–{hi} months"

def difficulty_stars(feature_name):
    n = get_meta(feature_name)['difficulty']
    return '*' * n + '.' * (5 - n)

# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

RISK_COLORS = ['#1a9641', '#a6d96a', '#ffffbf', '#fdae61', '#d7191c']
RISK_LABELS = ['Excellent', 'Good', 'Fair', 'Borderline', 'Concerning']

def _band_index(prob):
    """Map a probability [0,1] to one of 5 band indices."""
    if prob < 0.20: return 0
    if prob < 0.40: return 1
    if prob < 0.60: return 2
    if prob < 0.80: return 3
    return 4

def _band_label(prob):
    return RISK_LABELS[_band_index(prob)]

def risk_gauge(prob, save_path, title=None):
    """Draw a 5-band semi-circular risk gauge with a needle at `prob`."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-0.2, 1.2)
    ax.set_aspect('equal')
    ax.axis('off')

    for i, color in enumerate(RISK_COLORS):
        start_angle = 180 - i * 36
        end_angle   = start_angle - 36
        ax.add_patch(Wedge(center=(0, 0), r=1.0, theta1=end_angle,
                             theta2=start_angle, width=0.30,
                             facecolor=color, edgecolor='white', linewidth=2))
        mid_angle = np.radians((start_angle + end_angle) / 2)
        lx, ly = 0.85 * np.cos(mid_angle), 0.85 * np.sin(mid_angle)
        ax.text(lx, ly, RISK_LABELS[i], ha='center', va='center',
                 fontsize=8, fontweight='bold', color='black',
                 family='serif')

    needle_angle = np.radians(180 - prob * 180)
    nx = 0.95 * np.cos(needle_angle)
    ny = 0.95 * np.sin(needle_angle)
    ax.plot([0, nx], [0, ny], color='black', linewidth=3, solid_capstyle='round')
    ax.add_patch(plt.Circle((0, 0), 0.05, color='black', zorder=5))

    ax.text(0, -0.10, f"{prob*100:.1f}%", ha='center', va='top',
             fontsize=22, fontweight='bold', family='serif')
    ax.text(0, 0.05, _band_label(prob), ha='center', va='bottom',
             fontsize=12, style='italic', family='serif', color='#444')

    if title:
        ax.set_title(title, fontsize=13, family='serif', pad=10)

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return save_path

def case_tornado(counterfactuals, save_path, top_n=8, title=None):
    """Show the top-impact actionable recommendations as a tornado."""
    recs = [r for r in counterfactuals if r['actionable']][:top_n]
    if not recs:
        fig, ax = plt.subplots(figsize=(7, 2))
        ax.text(0.5, 0.5, "No actionable recommendations available.",
                 ha='center', va='center', fontsize=11, family='serif',
                 color='#666')
        ax.axis('off')
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return save_path

    labels = [f"{display_name(r['feature'])}\n→ {r['new_display']}" for r in recs]
    impacts = [r['mean_impact'] * 100 for r in recs]
    colors = ['#2c7bb6' if i < 0 else '#d7191c' for i in impacts]

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.55 * len(recs) + 1)))
    y = np.arange(len(recs))
    ax.barh(y, impacts, color=colors, edgecolor='black', linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9, family='serif')
    ax.invert_yaxis()
    ax.axvline(0, color='black', linewidth=0.7)
    ax.set_xlabel("Change in default probability (percentage points)",
                  fontsize=10, family='serif')
    ax.grid(axis='x', alpha=0.3, linestyle=':')
    if title:
        ax.set_title(title, fontsize=12, family='serif', pad=10)

    for i, (val, rec) in enumerate(zip(impacts, recs)):
        x_text = val - 0.5 if val < 0 else val + 0.5
        ha = 'right' if val < 0 else 'left'
        ax.text(x_text, i, f"{val:+.1f} pp ({rec['n_models_agree']}/6 models)",
                 va='center', ha=ha, fontsize=8, family='serif')

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return save_path

def timeline_projection(baseline_mean, baseline_std, pathway_outcomes,
                          save_path, title=None):
    """Plot probability over 12 months for three pathways."""
    months = np.arange(0, 13)
    fig, ax = plt.subplots(figsize=(8, 4.5))

    pathway_specs = [
        (PATHWAY_A, 1, '#2c7bb6', 'Pathway A: Restructure the Request'),
        (PATHWAY_B, 6, '#fdae61', 'Pathway B: Build Financial Routine'),
        (PATHWAY_C, 12, '#1a9641', 'Pathway C: Long-term Profile'),
    ]

    inaction = baseline_mean + 0.005 * months
    inaction = np.clip(inaction, 0, 1)
    ax.plot(months, inaction * 100, color='#888', linestyle=':',
             linewidth=2, label='If you take no action')

    for p_key, t_target, color, label in pathway_specs:
        out = pathway_outcomes.get(p_key)
        if out is None:
            continue
        traj = []
        for m in months:
            if m == 0:
                traj.append(baseline_mean)
            elif m <= t_target:
                f = 1 - (1 - m / t_target) ** 1.6
                traj.append(baseline_mean + f * (out['mean'] - baseline_mean))
            else:
                traj.append(out['mean'])
        traj = np.array(traj) * 100
        ax.plot(months, traj, color=color, linewidth=2.2, label=label, marker='o',
                 markersize=4)

        if out['std'] > 0:
            band_lo = traj - out['std'] * 100 * (months / 12.0)
            band_hi = traj + out['std'] * 100 * (months / 12.0)
            ax.fill_between(months, band_lo, band_hi, color=color, alpha=0.13)

    ax.axhline(50, color='black', linewidth=1.0, linestyle='--', alpha=0.7)
    ax.text(11.5, 51, 'Approval threshold (50%)', fontsize=8, family='serif',
             ha='right', va='bottom', color='black', style='italic')

    ax.set_xlabel("Months from today", fontsize=11, family='serif')
    ax.set_ylabel("Default probability (%)", fontsize=11, family='serif')
    ax.set_xticks(months[::2])
    ax.set_ylim(0, max(100, baseline_mean * 100 + 10))
    ax.grid(alpha=0.3, linestyle=':')
    ax.legend(loc='lower left', fontsize=9, framealpha=0.95)
    if title:
        ax.set_title(title, fontsize=12, family='serif', pad=10)

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return save_path

def model_strip(per_model_probs, save_path, title=None):
    """Horizontal strip showing each model's reading as a colored chip."""
    models = list(per_model_probs.keys())
    probs  = list(per_model_probs.values())
    n = len(models)

    fig, ax = plt.subplots(figsize=(8, 1.5 + 0.05 * n))
    ax.set_xlim(0, n)
    ax.set_ylim(0, 2.2)
    ax.axis('off')

    for i, (name, p) in enumerate(zip(models, probs)):
        color = RISK_COLORS[_band_index(p)]
        ax.add_patch(FancyBboxPatch(
            (i + 0.07, 0.45), 0.86, 1.45,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor='black', linewidth=0.6
        ))
        ax.text(i + 0.5, 1.45, f"{p*100:.0f}%", ha='center', va='center',
                 fontsize=18, fontweight='bold', family='serif',
                 path_effects=[patheffects.withStroke(linewidth=2,
                                                       foreground='white')])
        ax.text(i + 0.5, 0.85, name, ha='center', va='center',
                 fontsize=8, family='serif')
        ax.text(i + 0.5, 0.20, _band_label(p), ha='center', va='center',
                 fontsize=7, style='italic', family='serif', color='#444')

    if title:
        ax.text(n / 2.0, 2.10, title, ha='center', va='center',
                 fontsize=11, family='serif', fontweight='bold')

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return save_path

def feature_health_bars(case_row_dict, peer_median_dict, save_path,
                          top_n=8, title=None):
    """Horizontal bars: each feature shows the case's value vs peer median."""
    rows = []
    for f, v in case_row_dict.items():
        if f == 'target' or f not in peer_median_dict:
            continue
        try:
            v_num = float(v)
            pm = float(peer_median_dict[f])
        except (TypeError, ValueError):
            continue
        if pm == 0 and v_num == 0:
            continue
        rows.append({'feature': f, 'case': v_num, 'peer': pm,
                      'ratio': v_num / (pm + 1e-9)})

    rows = sorted(rows, key=lambda r: abs(r['ratio'] - 1), reverse=True)[:top_n]
    if not rows:
        fig, ax = plt.subplots(figsize=(7, 2))
        ax.text(0.5, 0.5, "Insufficient numeric data for comparison.",
                 ha='center', va='center', family='serif', color='#666')
        ax.axis('off')
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return save_path

    labels = [display_name(r['feature']) for r in rows]
    case_vals = [r['case'] for r in rows]
    peer_vals = [r['peer'] for r in rows]

    fig, ax = plt.subplots(figsize=(8, max(3, 0.55 * len(rows) + 1)))
    y = np.arange(len(rows))
    width = 0.4
    ax.barh(y - width / 2, case_vals, width, color='#2c7bb6',
              edgecolor='black', linewidth=0.4, label='Your value')
    ax.barh(y + width / 2, peer_vals, width, color='#1a9641',
              edgecolor='black', linewidth=0.4, label='Approved peer median')
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9, family='serif')
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3, linestyle=':')
    ax.legend(loc='lower right', fontsize=9)
    if title:
        ax.set_title(title, fontsize=12, family='serif', pad=10)

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return save_path

# ============================================================================
# RECOURSE ANALYSIS ENGINE
# ============================================================================

ROBUSTNESS_MIN_MODELS = 4

_BASELINE_CACHE = {}

def ensemble_predict(models, X_encoded, X_scaled):
    """Return {model_name: proba_array} for all 6 saved models."""
    out = {}
    for name, fn in models.items():
        try:
            out[name] = fn(X_encoded, X_scaled)
        except Exception as e:
            print(f"  [WARN] {name} ensemble call failed: {e}")
    return out

def ensemble_summary(predictions, idx=0):
    """Reduce {model: array} → mean, std, and per-model dict for one case."""
    per_model = {name: float(arr[idx]) for name, arr in predictions.items()}
    values = np.array(list(per_model.values()))
    return {
        'per_model':  per_model,
        'mean':       float(values.mean()),
        'std':        float(values.std()),
        'min':        float(values.min()),
        'max':        float(values.max()),
        'n_models':   len(values),
        'votes_default': int((values >= 0.5).sum()),
    }

def _candidate_values_for_feature(feature_name, current_value, preprocessor,
                                  approved_df):
    """Return a list of candidate replacement values to test for this feature."""
    categorical_cols = preprocessor.get('categorical_cols', [])
    categorical_levels = preprocessor.get('categorical_levels', {})

    if feature_name in categorical_cols:
        return [v for v in categorical_levels.get(feature_name, []) if str(v) != str(current_value)]

    if feature_name not in approved_df.columns:
        return []
    series = pd.to_numeric(approved_df[feature_name], errors='coerce').dropna()
    if len(series) < 5:
        return []
    quantiles = [0.10, 0.25, 0.50, 0.75, 0.90]
    candidates = [float(series.quantile(q)) for q in quantiles]
    out = []
    for c in candidates:
        try:
            if abs(c - float(current_value)) / (abs(float(current_value)) + 1e-6) < 0.01:
                continue
        except Exception:
            pass
        out.append(c)
    return list(dict.fromkeys(out))

def _to_display(feature, value, categorical_cols):
    """Convert an encoded value back to its display label."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'N/A'
    if feature in categorical_cols:
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"

def generate_counterfactuals(case_row_raw_dict, preprocessor, models,
                              approved_df, baseline_prob_mean):
    """Generate counterfactual recommendations for all features."""
    feature_names    = preprocessor.get('raw_feature_names', preprocessor['feature_names'])
    categorical_cols = preprocessor.get('categorical_cols', [])

    results = []

    for feat_idx, feat in enumerate(feature_names):
        meta = get_meta(feat)
        current_val = case_row_raw_dict.get(feat)

        candidates = _candidate_values_for_feature(
            feat, current_val, preprocessor, approved_df
        )
        if not candidates:
            continue

        for new_val in candidates:
            row = dict(case_row_raw_dict)
            row[feat] = new_val
            X_raw = pd.DataFrame([row], columns=feature_names)
            X_proc = preprocessor['preprocessor'].transform(X_raw)

            try:
                preds = ensemble_predict(models, X_proc, X_proc)
            except Exception:
                continue

            new_probs = np.array([float(arr[0]) for arr in preds.values()])
            mean_impact = float(new_probs.mean()) - baseline_prob_mean

            baseline_per_model = np.array(
                [arr[0] for arr in baseline_per_model_cache(case_row_raw_dict,
                                                              preprocessor,
                                                              models).values()]
            )
            improvements = new_probs < baseline_per_model
            n_agree = int(improvements.sum())

            cur_disp = _to_display(feat, current_val, categorical_cols)
            new_disp = _to_display(feat, new_val, categorical_cols)

            results.append({
                'feature':         feat,
                'current_value':   current_val,
                'new_value':       new_val,
                'current_display': cur_disp,
                'new_display':     new_disp,
                'mean_impact':     mean_impact,
                'std_impact':      float(new_probs.std()),
                'n_models_agree':  n_agree,
                'new_prob_mean':   float(new_probs.mean()),
                'actionable':      meta['actionable'],
                'pathway':         meta['pathway'],
                'time_months':     meta['time_months'],
                'difficulty':      meta['difficulty'],
            })

    return results

def baseline_per_model_cache(case_row_raw_dict, preprocessor, models):
    feature_names = preprocessor.get('raw_feature_names', preprocessor['feature_names'])
    key = tuple(case_row_raw_dict.get(f) for f in feature_names)
    if key not in _BASELINE_CACHE:
        X_raw = pd.DataFrame([case_row_raw_dict], columns=feature_names)
        X_proc = preprocessor['preprocessor'].transform(X_raw)
        _BASELINE_CACHE[key] = ensemble_predict(models, X_proc, X_proc)
    return _BASELINE_CACHE[key]

def clear_baseline_cache():
    _BASELINE_CACHE.clear()

def filter_robust_improvements(counterfactuals, min_models=ROBUSTNESS_MIN_MODELS):
    """Keep only changes that reduce probability and are agreed-on by models."""
    out = []
    for c in counterfactuals:
        if not c['actionable']:
            continue
        if c['mean_impact'] >= -0.005:
            continue
        if c['n_models_agree'] < min_models:
            continue
        out.append(c)
    return out

def rank_by_cost_benefit(recommendations):
    """Rank by impact divided by time cost."""
    def score(r):
        time_avg = (r['time_months'][0] + r['time_months'][1]) / 2.0 + 0.5
        return abs(r['mean_impact']) / (time_avg * (1 + r['difficulty'] / 5.0))
    return sorted(recommendations, key=score, reverse=True)

def deduplicate_keep_best(recommendations):
    """If multiple candidate values exist for the same feature, keep the most impactful."""
    best = {}
    for r in recommendations:
        prev = best.get(r['feature'])
        if prev is None or r['mean_impact'] < prev['mean_impact']:
            best[r['feature']] = r
    return list(best.values())

def cluster_into_pathways(recommendations):
    """Group recommendations into the three pathway buckets."""
    bins = {PATHWAY_A: [], PATHWAY_B: [], PATHWAY_C: []}
    for r in recommendations:
        p = r['pathway']
        if p in bins:
            bins[p].append(r)
    return bins

def combined_pathway_impact(pathway_recs, case_row_raw_dict, preprocessor, models):
    """Apply all changes in a pathway simultaneously and re-predict."""
    if not pathway_recs:
        return None
    feature_names = preprocessor.get('raw_feature_names', preprocessor['feature_names'])
    row = dict(case_row_raw_dict)
    for r in pathway_recs:
        row[r['feature']] = r['new_value']
    X_raw = pd.DataFrame([row], columns=feature_names)
    X_proc = preprocessor['preprocessor'].transform(X_raw)
    preds = ensemble_predict(models, X_proc, X_proc)
    arr = np.array([float(v[0]) for v in preds.values()])
    return {
        'mean': float(arr.mean()),
        'std':  float(arr.std()),
        'min':  float(arr.min()),
        'max':  float(arr.max()),
    }

def find_peer_approved(case_row_raw_dict, approved_df_raw, preprocessor, k=10):
    """Find the k nearest approved applicants in the transformed feature space."""
    if approved_df_raw.empty:
        return None, []

    feature_names = preprocessor.get('raw_feature_names', preprocessor['feature_names'])
    approved_raw = approved_df_raw[feature_names].copy()
    peer_arr = preprocessor['preprocessor'].transform(approved_raw)
    case_arr = preprocessor['preprocessor'].transform(pd.DataFrame([case_row_raw_dict], columns=feature_names))

    col_std = peer_arr.std(axis=0)
    col_std[col_std == 0] = 1.0

    diffs = (peer_arr - case_arr) / col_std
    dists = np.sqrt((diffs ** 2).sum(axis=1))
    nearest_idx = np.argsort(dists)[:k]
    peers = approved_raw.iloc[nearest_idx].reset_index(drop=True)

    peer_median = peers.median(numeric_only=True)
    deltas = []
    for col in peers.columns:
        if col not in peer_median.index:
            continue
        case_v = case_row_raw_dict.get(col)
        try:
            delta = float(case_v) - float(peer_median[col])
        except Exception:
            continue
        if abs(delta) < 1e-6:
            continue
        deltas.append({'feature': col, 'case': float(case_v),
                       'peer_median': float(peer_median[col]),
                       'delta': delta})
    deltas = sorted(deltas, key=lambda d: abs(d['delta']) /
                    (pd.to_numeric(peers[d['feature']], errors='coerce').std() + 1e-6), reverse=True)
    return peers, deltas[:5]

def analyse_case(case_row_raw_dict, preprocessor, models,
                  approved_df_raw, approved_df_encoded):
    """Run the full recourse analysis for one case."""
    # Normalize preprocessor format (should already be dict from main, but be defensive)
    preprocessor = _normalize_preprocessor(preprocessor)

    feature_names = preprocessor.get('raw_feature_names', preprocessor.get('feature_names', []))
    categorical_cols = preprocessor.get('categorical_cols', [])
    preprocessor_obj = preprocessor.get('preprocessor', preprocessor)

    case_row_raw = {f: case_row_raw_dict.get(f) for f in feature_names}
    case_df = pd.DataFrame([case_row_raw], columns=feature_names)
    case_row_encoded = preprocessor_obj.transform(case_df)

    baseline_preds = ensemble_predict(models, case_row_encoded, case_row_encoded)
    baseline = ensemble_summary(baseline_preds, idx=0)

    clear_baseline_cache()
    cfs = generate_counterfactuals(case_row_raw, preprocessor, models,
                                      approved_df_raw, baseline['mean'])
    robust = filter_robust_improvements(cfs)
    deduped = deduplicate_keep_best(robust)
    ranked  = rank_by_cost_benefit(deduped)

    pathway_bins = cluster_into_pathways(ranked)

    pathway_outcomes = {}
    for pname, recs in pathway_bins.items():
        outcome = combined_pathway_impact(recs, case_row_raw,
                                             preprocessor, models)
        pathway_outcomes[pname] = outcome

    peers, peer_deltas = find_peer_approved(case_row_raw,
                                               approved_df_raw,
                                               preprocessor)

    strengths = []
    if peers is not None:
        peer_median = peers.median(numeric_only=True)
        for f in feature_names:
            if f not in peer_median.index:
                continue
            v = case_row_raw.get(f)
            pmed = float(peer_median[f])
            if not any(r['feature'] == f for r in ranked[:10]):
                try:
                    case_val = float(v)
                except Exception:
                    continue
                strengths.append({'feature': f, 'case': case_val,
                                   'peer_median': pmed})

    return {
        'case_row_encoded':  case_row_encoded,
        'case_row_raw':      case_row_raw,
        'baseline':          baseline,
        'baseline_per_model': {k: float(v[0]) for k, v in baseline_preds.items()},
        'counterfactuals':   ranked,
        'pathway_recs':      pathway_bins,
        'pathway_outcomes':  pathway_outcomes,
        'peers':             peers,
        'peer_deltas':       peer_deltas,
        'strengths':         strengths[:5],
        'feature_names':     feature_names,
    }

# ============================================================================
# LaTeX HELPERS & PREAMBLE
# ============================================================================

def _esc(s):
    """Escape characters that have special meaning in LaTeX."""
    if s is None:
        return ''
    s = str(s)
    return (s.replace('\\', r'\textbackslash{}')
              .replace('&',  r'\&')
              .replace('%',  r'\%')
              .replace('$',  r'\$')
              .replace('#',  r'\#')
              .replace('_',  r'\_')
              .replace('{',  r'\{')
              .replace('}',  r'\}')
              .replace('~',  r'\textasciitilde{}')
              .replace('^',  r'\textasciicircum{}'))

PREAMBLE = r"""
\documentclass[11pt,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{tcolorbox}
\tcbuselibrary{skins,breakable}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{fontspec}
\usepackage{float}
\usepackage{array}
\usepackage{longtable}
\usepackage{hyperref}
\hypersetup{hidelinks}

% colour-blind friendly palette
\definecolor{riskgreen}{HTML}{1a9641}
\definecolor{risklime}{HTML}{a6d96a}
\definecolor{riskyellow}{HTML}{ffffbf}
\definecolor{riskorange}{HTML}{fdae61}
\definecolor{riskred}{HTML}{d7191c}
\definecolor{advisorblue}{HTML}{2c5f8a}
\definecolor{lightgrey}{HTML}{f3f3f3}

\titleformat{\section}{\large\bfseries\color{advisorblue}}{\thesection}{0.6em}{}
\titleformat{\subsection}{\normalsize\bfseries}{}{0em}{}

\newtcolorbox{advisorbox}[1]{
  colback=lightgrey, colframe=advisorblue, boxrule=0.5pt,
  left=8pt, right=8pt, top=6pt, bottom=6pt,
  title=#1, fonttitle=\bfseries\color{white},
  coltitle=white, attach boxed title to top left={yshift=-2mm,xshift=4mm},
  boxed title style={colback=advisorblue, boxrule=0pt}
}

\newtcolorbox{actioncard}[1]{
  enhanced, colback=white, colframe=advisorblue, boxrule=0.7pt,
  left=10pt, right=10pt, top=8pt, bottom=8pt,
  title=#1, fonttitle=\bfseries\color{white},
  coltitle=white, attach boxed title to top left={yshift=-2mm,xshift=6mm},
  boxed title style={colback=advisorblue, boxrule=0pt},
  breakable
}

\renewcommand{\arraystretch}{1.25}
\setlength{\parskip}{0.4em}
\setlength{\parindent}{0pt}
"""

# ============================================================================
# CASE REPORT BUILDER
# ============================================================================

class CaseReportBuilder:
    """Builds one PDF per case from the recourse-engine findings."""

    def __init__(self, case_id, findings, preprocessor, model_calibration,
                  dataset_label='', output_dir='output/cases', threshold=0.5,
                  advisor_name="Credit Advisory Team"):
        self.case_id     = str(case_id)
        self.findings    = findings
        self.preprocessor = preprocessor
        self.calibration = model_calibration or {}
        self.dataset_label = dataset_label
        self.threshold   = threshold
        self.advisor_name = advisor_name

        safe_id = re.sub(r'[^A-Za-z0-9_.-]', '_', self.case_id)
        self.case_dir = Path(output_dir) / safe_id
        self.fig_dir  = self.case_dir / 'figures'
        self.fig_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime('%Y%m%d_%H%M')
        self.tex_path = self.case_dir / f'case_report_{safe_id}_{date_str}.tex'
        self.pdf_path = self.tex_path.with_suffix('.pdf')

        self.tex = []

    def _fig_path(self, p):
        """LaTeX path relative to case_dir with forward slashes."""
        rel = Path(p).relative_to(self.case_dir)
        return str(rel).replace('\\', '/')

    def build(self):
        for old in self.case_dir.glob('case_report_*'):
            try: old.unlink()
            except: pass

        self.tex.append(PREAMBLE)
        self.tex.append(r'\begin{document}')

        self._write_header()
        self._write_section1_summary()
        self._write_section2_examination()
        self._write_section3_diagnosis()
        self._write_section4_pathways()
        self._write_section5_action_cards()
        self._write_section6_wellness()
        self._write_section7_reassessment()
        self._write_section8_technical()
        self._write_section9_advisor_note()

        self.tex.append(r'\end{document}')
        self.tex_path.write_text('\n'.join(self.tex), encoding='utf-8')
        self._compile_pdf()
        self._cleanup_intermediate_files()
        return self.pdf_path

    def _write_header(self):
        date = datetime.now().strftime('%d %B %Y')
        self.tex.append(rf"""
\begin{{center}}
  {{\Large\bfseries\color{{advisorblue}} Personal Credit Health Report}}\\[2pt]
  {{\large\itshape A financial advisory assessment prepared for you}}\\[6pt]
  \rule{{\linewidth}}{{0.4pt}}\\[2pt]
  \begin{{tabular}}{{l@{{\quad}}l@{{\hspace{{2em}}}}l@{{\quad}}l}}
    \textbf{{Applicant:}} & {_esc(self.case_id)} &
    \textbf{{Date:}}      & {_esc(date)}\\
    \textbf{{Dataset:}}   & {_esc(self.dataset_label)} &
    \textbf{{Prepared by:}} & {_esc(self.advisor_name)}\\
  \end{{tabular}}\\
  \rule{{\linewidth}}{{0.4pt}}
\end{{center}}
\vspace{{0.5em}}
""")

    def _write_section1_summary(self):
        baseline = self.findings['baseline']
        prob = baseline['mean']
        gap = max(0, prob - self.threshold) * 100

        headline = self._headline_diagnosis()

        gauge_path = self.fig_dir / 'gauge.png'
        risk_gauge(prob, gauge_path, title=None)
        strip_path = self.fig_dir / 'model_strip.png'
        model_strip(self.findings['baseline_per_model'], strip_path,
                                  title='How each of the six models reads your profile')

        self.tex.append(r'\section{Your Credit Health Summary}')
        self.tex.append(rf"""
\begin{{advisorbox}}{{Headline Diagnosis}}
{_esc(headline)}
\end{{advisorbox}}

\begin{{figure}}[H]\centering
\includegraphics[width=0.72\textwidth]{{{self._fig_path(gauge_path)}}}
\end{{figure}}

\begin{{center}}
\begin{{tabular}}{{lcc}}
\toprule
\textbf{{Indicator}} & \textbf{{Value}} & \textbf{{Status}}\\
\midrule
Current default probability   & {prob*100:.1f}\% & {_esc(_band_label(prob))}\\
Approval threshold            & {self.threshold*100:.0f}\% & --\\
Gap to close                  & {gap:.1f} percentage points & --\\
Model agreement               & {baseline['votes_default']}/{baseline['n_models']} models say high-risk & --\\
Ensemble uncertainty (±1 std) & ±{baseline['std']*100:.1f} pp & --\\
\bottomrule
\end{{tabular}}
\end{{center}}

\vspace{{0.5em}}
\begin{{figure}}[H]\centering
\includegraphics[width=\textwidth]{{{self._fig_path(strip_path)}}}
\end{{figure}}

\textbf{{How to read this strip:}} each of the six models trained on the same dataset gives its independent reading. When the six agree, confidence in the assessment is high. When they disagree, the actual answer is likely somewhere in between, and human judgement matters more.
""")

    def _headline_diagnosis(self):
        """Generate a paragraph-style headline in advisor tone."""
        b = self.findings['baseline']
        prob = b['mean']
        verdict = _band_label(prob)
        strengths = self.findings.get('strengths', [])
        pathway_outcomes = self.findings.get('pathway_outcomes', {})

        best_p, best_outcome = None, None
        for p, outcome in pathway_outcomes.items():
            if outcome and (best_outcome is None or outcome['mean'] < best_outcome['mean']):
                best_p, best_outcome = p, outcome

        pieces = []
        if prob < 0.30:
            pieces.append("Your credit profile is in good shape overall, and there are no significant red flags in the analysis.")
        elif prob < 0.50:
            pieces.append("Your credit profile is in fair shape — close enough to approval that targeted changes can realistically get you there.")
        elif prob < 0.70:
            pieces.append("Your credit profile currently presents elevated risk to lenders, but the analysis identifies specific, addressable factors driving this.")
        else:
            pieces.append("Your credit profile currently presents high risk to lenders. This report walks through the specific factors and what realistic changes would shift them.")

        if strengths:
            pieces.append(f"The analysis recognises real strengths in your profile that are working in your favour.")

        if best_outcome is not None and best_outcome['mean'] < prob - 0.05:
            improvement = (prob - best_outcome['mean']) * 100
            label = PATHWAY_LABELS[best_p].split(':')[-1].strip()
            pieces.append(f"If followed through, the most promising route ({label}) is projected to reduce your default probability by roughly {improvement:.0f} percentage points.")

        return ' '.join(pieces)

    def _write_section2_examination(self):
        case_raw = self.findings['case_row_raw']
        peers = self.findings.get('peers')
        peer_median = peers.median(numeric_only=True).to_dict() if peers is not None else {}

        bars_path = self.fig_dir / 'feature_bars.png'
        feature_health_bars(
            {k: v for k, v in case_raw.items() if not isinstance(v, str)},
            peer_median, bars_path,
            title='Your numeric features vs approved-applicant medians')

        tornado_path = self.fig_dir / 'tornado.png'
        case_tornado(
            self.findings['counterfactuals'], tornado_path,
            title='What would change your score the most')

        self.tex.append(r'\newpage \section{Your Credit Profile Examination}')
        self.tex.append(r"""
This section is the diagnostic step in your assessment: each of your reported features is read against the typical profile of applicants the same lender previously approved. Think of it as a panel of routine tests --- the value, the reference range, and a status indicator.
""")

        self.tex.append(r'\subsection*{Feature health table}')
        self.tex.append(self._feature_health_table())

        self.tex.append(rf"""
\begin{{figure}}[H]\centering
\includegraphics[width=\textwidth]{{{self._fig_path(bars_path)}}}
\end{{figure}}

\textbf{{What this tells you:}} bars where your value sits well above or below the green peer-median bar are the places lenders' eyes go first. Not every difference is a problem --- but the larger the gap, the more it influences the model's read.

\subsection*{{Top factors influencing your score}}

The chart below ranks the actionable features by how much your score would shift if that single feature were the suggested value. Negative bars (blue) mean the change would lower your default probability. The figure shows how many of the six models agree with that direction.

\begin{{figure}}[H]\centering
\includegraphics[width=\textwidth]{{{self._fig_path(tornado_path)}}}
\end{{figure}}
""")

    def _feature_health_table(self):
        """Build LaTeX table of case value vs peer median per feature."""
        case_raw = self.findings['case_row_raw']
        peers = self.findings.get('peers')
        if peers is None or peers.empty:
            return r"\textit{Peer comparison data unavailable.}"
        peer_median = peers.median(numeric_only=True)

        rows = []
        for f in self.findings['feature_names']:
            val = case_raw.get(f, '?')
            meta = get_meta(f)
            if f in peer_median.index:
                pmed = peer_median[f]
                try:
                    diff = abs(float(val) - float(pmed)) / (abs(float(pmed)) + 1e-9)
                    if diff < 0.10:    status = r'{\color{riskgreen}\textbf{OK}}'
                    elif diff < 0.35:  status = r'{\color{riskorange}\textbf{Check}}'
                    else:              status = r'{\color{riskred}\textbf{Out of range}}'
                except (TypeError, ValueError):
                    status = r'{\color{riskgreen}\textbf{OK}}' if val == pmed else r'{\color{riskorange}\textbf{Check}}'
                pmed_disp = (f"{pmed:.1f}" if isinstance(pmed, float) and not pmed.is_integer()
                             else f"{int(pmed)}")
            else:
                pmed_disp = '–'
                status = ''
            rows.append((_esc(meta['display']), _esc(val), _esc(pmed_disp), status))

        body = r' \\ ' + '\n'.join([
            ' & '.join([r[0], r[1], r[2], r[3]]) + r' \\' for r in rows
        ])
        return rf"""
\begin{{center}}\small
\begin{{longtable}}{{p{{4.5cm}} p{{3cm}} p{{3cm}} p{{3cm}}}}
\toprule
\textbf{{Feature}} & \textbf{{Your value}} & \textbf{{Approved peer median}} & \textbf{{Status}}\\
\midrule
\endhead
{body}
\bottomrule
\end{{longtable}}
\end{{center}}
"""

    def _write_section3_diagnosis(self):
        b = self.findings['baseline']
        cfs = self.findings['counterfactuals']
        peer_deltas = self.findings.get('peer_deltas', [])

        if cfs:
            top1 = cfs[0]
            top1_name = display_name(top1['feature'])
            top1_impact = abs(top1['mean_impact'] * 100)
        else:
            top1_name, top1_impact = '(none)', 0

        narrative_p1 = (
            f"Looking at the full pattern of your profile, the single biggest factor "
            f"pulling your score toward higher risk is your {top1_name.lower()}. "
            f"In our data, that one factor alone accounts for approximately "
            f"{top1_impact:.0f} percentage points of your current probability. "
            f"The other significant contributors are listed in the previous section's tornado chart."
            if cfs else
            "The model assessment does not isolate a single dominant factor for your case. "
            "This is sometimes a good sign — it can mean no one feature is acutely problematic — "
            "and sometimes a difficult one, when several factors are jointly contributing."
        )

        if peer_deltas:
            top_delta = peer_deltas[0]
            delta_name = display_name(top_delta['feature'])
            narrative_p2 = (
                f"Among the {len(self.findings['peers'])} most similar borrowers in our records "
                f"who were ultimately approved, the most consistent difference from your profile "
                f"is in {delta_name.lower()}: your value sits at "
                f"{top_delta['case']:.1f} while the typical approved peer is at "
                f"{top_delta['peer_median']:.1f}. This is not destiny — it is a pattern. "
                f"Borrowers who closed that gap, even partially, saw their assessments shift."
            )
        else:
            narrative_p2 = (
                "Peer comparison data is not available for this assessment, but the "
                "model-level findings above are still your most reliable signal."
            )

        narrative_p3 = (
            f"Out of the six independent models the bank's analytics team runs, "
            f"{b['votes_default']} of them currently classify your case as high-risk. "
            + ("This is a clear consensus, which means the assessment is reliable and reflects "
               "a genuine pattern in your data — not a quirk of one model."
               if b['votes_default'] in (0, 6) else
               "The models disagree, which means your case sits near a decision boundary. "
               "A small, well-chosen change can move the consensus.")
        )

        self.tex.append(r'\section{Diagnostic Findings}')
        self.tex.append(rf"""
\begin{{advisorbox}}{{What the analysis reveals}}
{_esc(narrative_p1)}

{_esc(narrative_p2)}

{_esc(narrative_p3)}
\end{{advisorbox}}
""")

        strengths = self.findings.get('strengths', [])[:5]
        if strengths:
            items = ''.join([rf'\item \textbf{{{_esc(display_name(s["feature"]))}}}: '
                              rf'your value is in line with approved borrowers.' + '\n'
                              for s in strengths])
            self.tex.append(rf"""
\subsection*{{What is already working for you}}
\begin{{itemize}}[leftmargin=*,itemsep=0pt,topsep=2pt]
{items}\end{{itemize}}
""")

    def _write_section4_pathways(self):
        b = self.findings['baseline']
        pathway_recs = self.findings.get('pathway_recs', {})
        pathway_outcomes = self.findings.get('pathway_outcomes', {})

        timeline_path = self.fig_dir / 'timeline.png'
        timeline_projection(
            b['mean'], b['std'], pathway_outcomes, timeline_path,
            title='Projected default probability over the next 12 months')

        self.tex.append(r'\newpage \section{Your Personalised Path to Approval}')
        self.tex.append(r"""
Rather than offering one optimal route, we map out three diverse pathways — each suiting a different borrower situation. Some readers will identify with one, others may combine elements from two. There is no single right answer; only the route that best matches your circumstances.
""")

        for p_key in [PATHWAY_A, PATHWAY_B, PATHWAY_C]:
            recs = pathway_recs.get(p_key, [])
            outcome = pathway_outcomes.get(p_key)
            label = PATHWAY_LABELS[p_key]
            desc = PATHWAY_DESCRIPTIONS[p_key]

            if outcome is not None and recs:
                improvement = (b['mean'] - outcome['mean']) * 100
                outcome_line = (f"Projected probability after this pathway: "
                                f"\\textbf{{{outcome['mean']*100:.1f}\\%}} "
                                f"({improvement:+.1f} percentage points from today). "
                                f"Uncertainty band: \\textpm{{}}{outcome['std']*100:.1f} pp.")
            else:
                outcome_line = "No robust recommendations available in this pathway."

            steps = ''
            if recs:
                steps_list = []
                for i, r in enumerate(recs[:4], 1):
                    steps_list.append(
                        rf"\item \textbf{{{_esc(display_name(r['feature']))}}}: "
                        rf"change to \emph{{{_esc(r['new_display'])}}} "
                        rf"({r['mean_impact']*100:+.1f} pp, "
                        rf"{r['n_models_agree']}/6 models agree, "
                        rf"{_esc(time_range_text(r['feature']))})"
                    )
                steps = (r'\begin{enumerate}[leftmargin=*,itemsep=2pt,topsep=2pt]' + '\n'
                          + '\n'.join(steps_list) + '\n'
                          + r'\end{enumerate}')

            self.tex.append(rf"""
\subsection*{{{_esc(label)}}}
\textit{{{_esc(desc)}}}

{steps}

\textbf{{Outcome:}} {outcome_line}
""")

        self.tex.append(rf"""
\begin{{figure}}[H]\centering
\includegraphics[width=\textwidth]{{{self._fig_path(timeline_path)}}}
\end{{figure}}

\textbf{{How to read this chart:}} each coloured line shows the projected default probability if you follow that pathway. The dashed black line marks the approval threshold. Shaded bands around each line show the uncertainty inherent in model projections — the real outcome will fall somewhere in that band, with the line itself being the most likely value.
""")

    def _write_section5_action_cards(self):
        cfs = self.findings['counterfactuals'][:8]
        if not cfs:
            return

        self.tex.append(r'\newpage \section{Detailed Action Cards}')
        self.tex.append(r"""
Each card below is a complete, self-contained action plan for one specific change. Read the cards relevant to your chosen pathway in order, or treat them as a menu and pick the ones that fit your circumstances best.
""")

        for r in cfs:
            meta = get_meta(r['feature'])
            impact = r['mean_impact'] * 100
            interval = max(1.0, r['std_impact'] * 100)
            self.tex.append(rf"""
\begin{{actioncard}}{{{_esc(display_name(r['feature']))}: change to {_esc(r['new_display'])}}}
\begin{{description}}[leftmargin=4em,style=nextline,itemsep=2pt]
\item[\textbf{{Why this matters}}] {_esc(meta['why'])}
\item[\textbf{{How to start}}] {_esc(meta['how'])}
\item[\textbf{{Expected effect}}] Reduces your default probability by approximately
{impact:+.1f} pp (±{interval:.1f}), agreed by {r['n_models_agree']}/6 models.
\item[\textbf{{Realistic time}}] {_esc(time_range_text(r['feature']))}.
\item[\textbf{{Difficulty}}] {_esc(difficulty_stars(r['feature']))} ({meta['difficulty']}/5).
\item[\textbf{{Evidence for reapplication}}] Bring documentation of the change
(bank statements, account statements, employment letter, or equivalent) when
you reapply.
\end{{description}}
\end{{actioncard}}
\vspace{{0.4em}}
""")

    def _write_section6_wellness(self):
        self.tex.append(r'\newpage \section{Beyond This Loan: Financial Wellness Advice}')
        self.tex.append(r"""
This section steps outside the immediate question of loan approval and focuses on the longer game — the financial habits that will keep your credit profile healthy for years to come. None of these are urgent for this specific application, but each one compounds quietly over time.

\subsection*{Build and protect your savings-to-income ratio}
Lenders look at savings not because of the absolute amount, but because savings are evidence that your income exceeds your expenses with a margin. Aim for a savings buffer equal to 3--6 months of essential expenses. Automatic transfers, even modest ones, make this happen without willpower.

\subsection*{Prefer shorter loan durations when possible}
A longer loan reduces the monthly payment but increases the total interest paid and your exposure to changing circumstances. When you can comfortably afford a shorter term, take it — it costs less in interest and signals financial confidence to future lenders.

\subsection*{Watch for early signs of debt accumulation}
The danger signs are subtle: paying only the minimum on a credit card, taking out a new loan to manage payments on an old one, or using credit for routine living expenses. If you notice these patterns, treat them as the early-warning indicators they are, not as temporary fixes.

\subsection*{Maintain a clean credit profile, even after approval}
The actions in your roadmap matter for this loan — but they also matter for every future credit decision. Continuing the same habits (regular checking-account use, on-time payments, documented savings growth) means that next time around, you start from a stronger position.

\subsection*{Know when to seek qualified human advice}
Statistical models like the ones used in this report are pattern-recognition tools. They are not financial advisers, and they cannot account for your full personal context. For decisions that significantly affect your future, a qualified human adviser remains the right resource.
""")

    def _write_section7_reassessment(self):
        today = datetime.now()
        check_3m = (today + timedelta(days=90)).strftime('%B %Y')
        check_6m = (today + timedelta(days=180)).strftime('%B %Y')
        check_12m = (today + timedelta(days=365)).strftime('%B %Y')

        self.tex.append(r'\section{Reassessment Schedule}')
        self.tex.append(rf"""
We recommend reassessing your credit profile at the following milestones. Each
reassessment uses the same six models and the same methodology, so the numbers
are directly comparable.

\begin{{center}}
\begin{{tabular}}{{p{{3cm}} p{{4cm}} p{{8cm}}}}
\toprule
\textbf{{Milestone}} & \textbf{{Recommended date}} & \textbf{{What to expect}}\\
\midrule
3 months & {_esc(check_3m)} & Pathway A items should already be reflected. Pathway B items should be partly visible (e.g.\ first 2--3 months of checking-account history).\\
6 months & {_esc(check_6m)} & Pathway B fully reflected. First measurable effects from Pathway C if you have started on it.\\
12 months & {_esc(check_12m)} & Full effect of all pathways. If approval has not been achieved by this point, consider escalation to a human credit adviser.\\
\bottomrule
\end{{tabular}}
\end{{center}}

\textbf{{Red flags that warrant earlier reassessment:}} a new missed payment,
a significant change in employment, opening additional credit lines, or any
event that materially changes your circumstances.
""")

    def _write_section8_technical(self):
        b = self.findings['baseline']
        self.tex.append(r'\newpage \section{Technical Appendix}')
        self.tex.append(r"""
This section is for the reader who wants to understand the underlying methodology. None of it is required reading for acting on the report.

\subsection*{The six models}
Your assessment is the consensus reading of six different machine-learning models, each trained on the same dataset but using a different mathematical approach:

\begin{itemize}[leftmargin=*,itemsep=1pt]
\item \textbf{Random Forest} --- ensemble of decision trees, robust to outliers.
\item \textbf{Logistic Regression} --- linear model, the industry baseline.
\item \textbf{XGBoost} --- gradient boosting, currently the strongest classical method on tabular data.
\item \textbf{PyTorch TabNet} --- attention-based neural network for tabular data.
\item \textbf{FTTransformer} --- feature-tokeniser transformer, deep-learning architecture.
\item \textbf{TabFPN} --- tabular feature-pyramid network, deep-learning architecture.
\end{itemize}

\subsection*{Calibration --- how to read the probability numbers}
Probability estimates from any model carry uncertainty. The Expected Calibration Error (ECE) below tells you, roughly, how much to trust the exact number versus the direction of the verdict:
""")

        rows = []
        for name, cal in self.calibration.items():
            ece = cal.get('ECE', 0)
            quality = cal.get('Quality', 'N/A')
            rows.append(f"{_esc(name)} & {ece*100:.1f}\\% & {_esc(quality)} \\\\")
        if rows:
            self.tex.append(rf"""
\begin{{center}}
\begin{{tabular}}{{lcc}}
\toprule
\textbf{{Model}} & \textbf{{ECE}} & \textbf{{Calibration quality}}\\
\midrule
{chr(10).join(rows)}
\bottomrule
\end{{tabular}}
\end{{center}}
""")

        self.tex.append(r"""
A model with ECE of 5\% means its predicted probabilities are, on average, within 5 percentage points of the true frequency. So when the model says ``72\%'', the truthful interpretation is closer to ``somewhere between 67\% and 77\%''.

\subsection*{Your right to recourse}
Under data-protection law (GDPR Article 22 in the European Union and equivalent frameworks elsewhere), you have the right not to be subject to a purely automated decision that significantly affects you, and the right to receive a meaningful explanation. This report is one form of that explanation. If after reading it you disagree with any element, you may request a human review of your case.
""")

    def _write_section9_advisor_note(self):
        note = self._generate_advisor_note()
        self.tex.append(r'\section{Advisor\textquoteright s Notes}')
        self.tex.append(rf"""
\begin{{advisorbox}}{{A note from your advisor}}
{_esc(note)}
\end{{advisorbox}}

\vspace{{1em}}
\textit{{This report was generated by the credit advisory analytics platform on
{_esc(datetime.now().strftime('%d %B %Y at %H:%M'))}. It is intended as a
diagnostic and educational tool. For binding credit decisions or matters
involving legal, tax, or regulatory implications, please consult a qualified
human adviser.}}
""")

    def _generate_advisor_note(self):
        """Auto-generate a warm, personal closing note based on findings."""
        b = self.findings['baseline']
        prob = b['mean']
        cfs = self.findings.get('counterfactuals', [])
        pathway_outcomes = self.findings.get('pathway_outcomes', {})
        strengths = self.findings.get('strengths', [])

        best_p, best_outcome = None, None
        for p, out in pathway_outcomes.items():
            if out is None: continue
            if best_outcome is None or out['mean'] < best_outcome['mean']:
                best_p, best_outcome = p, out

        parts = []

        if prob < 0.30:
            parts.append("Reading through your report, what stands out first is that you are already in a healthy place. Most of the work of this analysis was finding what's working — and there's a lot working for you.")
        elif prob < 0.50:
            parts.append("Your situation is one of the more encouraging ones I see: close enough to approval that small, deliberate changes really do shift the verdict. The frustration of being on the wrong side of a 50-50 line is real, but so is the opportunity.")
        elif prob < 0.75:
            parts.append("I want to be honest with you: today, the assessment is not in your favour. But the reason I want you to read this whole report — not just the summary — is that the path back to a healthy assessment is concrete and walkable. It is not vague advice; it is specific actions with measurable effects.")
        else:
            parts.append("This report has likely been a difficult read in places. The assessment is clear, and I'm not going to soften it. What I will say is that statistical risk profiles are not life sentences. Every borrower in the data who eventually got approved started somewhere — sometimes from a position more difficult than yours.")

        if strengths:
            strength_name = display_name(strengths[0]['feature']).lower()
            parts.append(f"Your {strength_name} is genuinely a positive signal — don't lose sight of that while focusing on what needs improvement.")

        if cfs:
            top = cfs[0]
            top_name = display_name(top['feature']).lower()
            t = time_range_text(top['feature'])
            parts.append(f"If you do nothing else from this report, focus on the {top_name}. It is the single highest-leverage change available to you, and the time investment ({t.lower()}) is the smallest for its impact.")

        if best_outcome is not None and best_outcome['mean'] < prob - 0.03:
            label = PATHWAY_LABELS[best_p].split(':')[-1].strip().lower()
            if best_p == PATHWAY_A:
                t_horizon = "immediately"
            elif best_p == PATHWAY_B:
                t_horizon = "within 3-6 months"
            else:
                t_horizon = "over 6-12 months"
            parts.append(f"Realistically, following the {label} pathway, a healthy credit profile is achievable {t_horizon}.")

        parts.append("Come back to this report after each milestone — your situation will look different at month three than it does today, and the report should evolve with it.")

        return ' '.join(parts)

    def _compile_pdf(self):
        last_stderr = ''
        for engine in ('lualatex', 'xelatex'):
            if shutil.which(engine) is None:
                continue
            try:
                for _ in range(2):
                    result = subprocess.run(
                        [engine, '-interaction=nonstopmode', self.tex_path.name],
                        cwd=self.case_dir, capture_output=True, text=True,
                        timeout=120
                    )
                if self.pdf_path.exists():
                    return self.pdf_path
                last_stderr = (result.stdout or '') + '\n' + (result.stderr or '')
            except Exception as e:
                last_stderr = str(e)

        self._adapt_for_pdflatex()
        try:
            for _ in range(2):
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', self.tex_path.name],
                    cwd=self.case_dir, capture_output=True, text=True,
                    timeout=120
                )
            if self.pdf_path.exists():
                return self.pdf_path
            last_stderr = (result.stdout or '') + '\n' + (result.stderr or '')
        except Exception as e:
            last_stderr = str(e)

        log = self.tex_path.with_suffix('.log')
        if log.exists():
            tail = log.read_text(errors='ignore').splitlines()[-25:]
            print("  [LaTeX log tail]\n    " + '\n    '.join(tail))
        else:
            print(f"  [stderr] {last_stderr[-500:]}")
        raise RuntimeError(f"PDF compilation failed; LaTeX log at {log}")

    def _cleanup_intermediate_files(self):
        for ext in ('.log', '.aux', '.out'):
            try:
                self.tex_path.with_suffix(ext).unlink()
            except:
                pass
        try:
            if self.fig_dir.exists():
                shutil.rmtree(self.fig_dir)
        except Exception as e:
            pass

    def _adapt_for_pdflatex(self):
        """Strip fontspec + replace UTF-8 symbols for pdflatex compatibility."""
        src = self.tex_path.read_text(encoding='utf-8')
        src = src.replace(r'\usepackage{fontspec}', '')
        replacements = {
            '✓': r'\checkmark',
            '✗': r'\(\times\)',
            'OK': '!',
            '±': r'\(\pm\)',
            '–': r'--',
            '—': r'---',
            ''': "'", ''': "'",
            '"': '``', '"': "''",
        }
        for u, latex in replacements.items():
            src = src.replace(u, latex)
        self.tex_path.write_text(src, encoding='utf-8')

# ============================================================================
# ONE-PAGER: Dense 16:9 landscape single-page summary
# ============================================================================

_ONE_PAGER_PREAMBLE = r"""
\documentclass[8pt]{article}
\usepackage[paperwidth=33.87cm,paperheight=19.05cm,
            top=0.45cm,bottom=0.45cm,left=0.55cm,right=0.55cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{array}
\usepackage{enumitem}
\usepackage{lmodern}
\usepackage[most]{tcolorbox}
\usepackage{calc}
\setlength{\parindent}{0pt}
\setlength{\parskip}{1.5pt}
\renewcommand{\arraystretch}{1.1}
\setlist{nosep,leftmargin=1em}

\definecolor{advisorblue}{HTML}{2c5f8a}
\definecolor{riskgreen}{HTML}{1a9641}
\definecolor{riskorange}{HTML}{fdae61}
\definecolor{riskred}{HTML}{d7191c}
\definecolor{lightgrey}{HTML}{f3f3f3}
\definecolor{colsep}{HTML}{dce3ea}
\definecolor{headerbg}{HTML}{2c5f8a}
\definecolor{darktext}{HTML}{1a1a2e}

\newtcolorbox{panel}[2][]{
  colback=#2, colframe=advisorblue, boxrule=0.4pt,
  left=4pt, right=4pt, top=3pt, bottom=3pt,
  title={\footnotesize\bfseries\color{white}##1},
  fonttitle=\bfseries, coltitle=white,
  attach boxed title to top left={yshift=-1.5mm,xshift=3mm},
  boxed title style={colback=advisorblue,boxrule=0pt,
                     left=2pt,right=2pt,top=1pt,bottom=1pt},
  #1
}

\newtcolorbox{riskverdictbox}[2]{
  colback=#2, colframe=#2!80!black, boxrule=0.6pt,
  left=6pt, right=6pt, top=4pt, bottom=4pt,
  sharp corners
}
"""

def _risk_color(prob):
    if prob < 0.35:   return 'riskgreen'
    if prob < 0.55:   return 'riskorange'
    return 'riskred'

def _risk_label(prob):
    if prob < 0.35:   return 'LOW RISK'
    if prob < 0.55:   return 'MODERATE RISK'
    return 'HIGH RISK'

def _risk_bg(prob):
    if prob < 0.35:   return 'green!12'
    if prob < 0.55:   return 'orange!15'
    return 'red!12'


class OnePagerBuilder:
    """Generates a dense single-page 16:9 landscape PDF summary of a case."""

    def __init__(self, case_id, findings, fig_dir, calibration=None):
        self.case_id    = case_id
        self.findings   = findings
        self.fig_dir    = Path(fig_dir)
        self.calibration = calibration or {}
        self.tex        = []

    def _fp(self, p):
        # Use absolute paths so fragments compile correctly from any working directory
        return str(Path(p).resolve()).replace('\\', '/')

    def _page_body(self):
        """Return the LaTeX body for this case (no preamble/document tags)."""
        self.tex = []
        self._write_header()
        self._write_body()
        self._write_footer()
        self.tex.append(r'\clearpage')
        body = '\n'.join(self.tex)
        body = body.replace('—', '---').replace('–', '--')
        return body

    def build(self, batch_dir, fragments_dir, index_path):
        """Add/update this case's page in the batch one-pager and recompile.

        Args:
            batch_dir:     directory where onepager_batch.pdf lives
            fragments_dir: directory where per-case .tex fragments are stored
            index_path:    path to onepager_index.json (preserves page order)

        Returns:
            Path to the compiled onepager_batch.pdf
        """
        batch_dir     = Path(batch_dir)
        fragments_dir = Path(fragments_dir)
        fragments_dir.mkdir(parents=True, exist_ok=True)

        safe_id = re.sub(r'[^A-Za-z0-9_\-]', '_', str(self.case_id))

        # Save/overwrite this case's fragment
        fragment_path = fragments_dir / f'{safe_id}.tex'
        fragment_path.write_text(self._page_body(), encoding='utf-8')

        # Update ordered index — add if new, keep position if already present
        index = []
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding='utf-8'))
        if safe_id not in index:
            index.append(safe_id)
        index_path.write_text(json.dumps(index, indent=2), encoding='utf-8')

        # Assemble and compile batch document
        return self._compile_batch(batch_dir, fragments_dir, index)

    def _compile_batch(self, batch_dir, fragments_dir, index):
        """Assemble all fragments into one document and compile to PDF."""
        pages = []
        for sid in index:
            fpath = fragments_dir / f'{sid}.tex'
            if fpath.exists():
                pages.append(fpath.read_text(encoding='utf-8'))

        full_doc = (
            _ONE_PAGER_PREAMBLE + '\n'
            r'\begin{document}' + '\n'
            r'\pagestyle{empty}' + '\n' +
            '\n'.join(pages) +
            '\n' + r'\end{document}'
        )

        batch_tex = batch_dir / 'onepager_batch.tex'
        batch_tex.write_text(full_doc, encoding='utf-8')
        self._compile(batch_tex)
        for ext in ('.log', '.aux', '.out'):
            try: batch_tex.with_suffix(ext).unlink()
            except: pass
        return batch_tex.with_suffix('.pdf')

    def _write_header(self):
        b    = self.findings['baseline']
        prob = b['mean']
        rc   = _risk_color(prob)
        rl   = _risk_label(prob)
        date = datetime.now().strftime('%d %B %Y')
        n_high = sum(1 for v in self.findings['baseline_per_model'].values() if v >= 0.5)
        n_tot  = len(self.findings['baseline_per_model'])
        gap    = max(0.0, prob - 0.5) * 100

        self.tex.append(rf"""
\begin{{tcolorbox}}[colback=headerbg, colframe=headerbg, boxrule=0pt,
  left=8pt, right=8pt, top=3pt, bottom=3pt, sharp corners]
\color{{white}}
\begin{{minipage}}{{0.55\textwidth}}
  {{\large\bfseries Personal Credit Health Report}}\quad
  {{\normalsize\itshape A one-page financial advisory summary}}
\end{{minipage}}\hfill
\begin{{minipage}}{{0.44\textwidth}}\raggedleft\small
  \textbf{{Applicant:}} {_esc(self.case_id)}\quad
  \textbf{{Date:}} {date}\quad
  \textbf{{Models:}} {n_tot} ensemble
\end{{minipage}}
\end{{tcolorbox}}
\vspace{{1pt}}
""")

    def _write_body(self):
        cw1 = r'0.265\textwidth'
        cw2 = r'0.415\textwidth'
        cw3 = r'0.285\textwidth'
        self.tex.append(
            r'\begin{minipage}[t]{' + cw1 + r'}\vspace{0pt}' + '\n' +
            self._col1() +
            r'\end{minipage}' + '\n' +
            r'\hfill\textcolor{colsep}{\vrule width 0.4pt}\hfill' + '\n' +
            r'\begin{minipage}[t]{' + cw2 + r'}\vspace{0pt}' + '\n' +
            self._col2() +
            r'\end{minipage}' + '\n' +
            r'\hfill\textcolor{colsep}{\vrule width 0.4pt}\hfill' + '\n' +
            r'\begin{minipage}[t]{' + cw3 + r'}\vspace{0pt}' + '\n' +
            self._col3() +
            r'\end{minipage}'
        )

    # ------------------------------------------------------------------
    # Column 1: Risk verdict + model scores + calibration
    # ------------------------------------------------------------------
    def _col1(self):
        b    = self.findings['baseline']
        prob = b['mean']
        std  = b['std']
        rc   = _risk_color(prob)
        rl   = _risk_label(prob)
        rbg  = _risk_bg(prob)
        n_high = sum(1 for v in self.findings['baseline_per_model'].values() if v >= 0.5)
        n_tot  = len(self.findings['baseline_per_model'])
        gap    = max(0.0, prob - 0.5) * 100

        # Risk verdict box
        verdict = rf"""
\begin{{tcolorbox}}[colback={rbg},colframe={rc}!70!black,boxrule=0.5pt,
  left=4pt,right=4pt,top=3pt,bottom=3pt,sharp corners]
\centering
{{\fontsize{{28}}{{30}}\selectfont\bfseries\color{{{rc}}} {prob*100:.1f}\%}}\\[1pt]
{{\small\bfseries\color{{{rc}}} {rl}}}\\[2pt]
{{\footnotesize\color{{darktext}}
  Gap to approval threshold: \textbf{{{gap:.1f} pp}}\\
  Ensemble uncertainty: {{\small$\pm${std*100:.1f} pp}}\\
  Model consensus: \textbf{{{n_high}/{n_tot} models flag high-risk}}
}}
\end{{tcolorbox}}
\vspace{{3pt}}
"""

        # Model-by-model scores
        model_rows = []
        short = {'Random Forest':'RF', 'Logistic Regression':'LR', 'XGBoost':'XGB',
                 'PyTorch TabNet':'TabNet', 'FTTransformer':'FTTransf.', 'TabFPN':'TabFPN'}
        for name, val in self.findings['baseline_per_model'].items():
            col   = _risk_color(val)
            label = r'{\color{' + col + r'}\bfseries ' + f'{val*100:.1f}\\%' + r'}'
            bar_w = f'{val*3:.2f}cm'
            model_rows.append(
                rf'{_esc(short.get(name,name))} & {label} & '
                rf'\textcolor{{{col}}}{{\rule{{{bar_w}}}{{5pt}}}} \\'
            )

        models_block = rf"""
\begin{{panel}}[title={{Model Scores}}]{{lightgrey}}
{{\tiny
\begin{{tabular}}{{@{{}}l r l@{{}}}}
""" + '\n'.join(model_rows) + rf"""
\end{{tabular}}
}}
\end{{panel}}
\vspace{{3pt}}
"""

        # Calibration
        cal_rows = []
        model_order = ['Random Forest','Logistic Regression','XGBoost',
                       'PyTorch TabNet','FTTransformer','TabFPN']
        for m in model_order:
            if m in self.calibration:
                ece = self.calibration[m].get('ece', None)
                if ece is not None:
                    q = 'Good' if ece < 0.08 else ('Fair' if ece < 0.12 else 'Poor')
                    qcol = 'riskgreen' if q=='Good' else ('riskorange' if q=='Fair' else 'riskred')
                    cal_rows.append(
                        rf'{_esc(short.get(m,m))} & {ece*100:.1f}\% & '
                        rf'{{\color{{{qcol}}}\textbf{{{q}}}}} \\'
                    )

        cal_block = ''
        if cal_rows:
            cal_block = rf"""
\begin{{panel}}[title={{Calibration (ECE)}}]{{lightgrey}}
{{\tiny
\begin{{tabular}}{{@{{}}l r l@{{}}}}
\toprule
\textbf{{Model}} & \textbf{{ECE}} & \textbf{{Quality}} \\
\midrule
""" + '\n'.join(cal_rows) + rf"""
\bottomrule
\end{{tabular}}
}}
\end{{panel}}
"""

        # Gauge figure if available
        gauge_path = self.fig_dir / 'gauge.png'
        gauge_block = ''
        if gauge_path.exists():
            gauge_block = rf"""
\begin{{center}}
\includegraphics[width=0.88\linewidth]{{{self._fp(gauge_path)}}}
\end{{center}}
\vspace{{2pt}}
"""

        return verdict + gauge_block + models_block + cal_block

    # ------------------------------------------------------------------
    # Column 2: Feature health table + strengths + diagnosis excerpt
    # ------------------------------------------------------------------
    def _col2(self):
        case_raw = self.findings['case_row_raw']
        peers    = self.findings.get('peers')
        strengths = self.findings.get('strengths', [])

        peer_medians = {}
        if peers is not None and len(peers) > 0:
            for col in peers.columns:
                try:
                    peer_medians[col] = peers[col].median()
                except: pass

        # Only rows where the case actually has a non-null value
        feat_rows = []
        skip_cols = {'source_dataset', 'target'}
        for f in self.findings.get('feature_names', []):
            if f in skip_cols:
                continue
            val = case_raw.get(f)
            if val is None or (isinstance(val, float) and np.isnan(val)) or val == '':
                continue
            pm = peer_medians.get(f)
            if isinstance(pm, float) and np.isnan(pm):
                pm = None

            if pm is not None:
                ratio = float(val) / (float(pm) + 1e-9) if _is_numeric(val) and _is_numeric(pm) else None
                if ratio is not None:
                    if ratio > 1.25:   status = rf'{{\color{{riskred}}\textbf{{High}}}}'
                    elif ratio < 0.75: status = rf'{{\color{{riskorange}}\textbf{{Low}}}}'
                    else:              status = rf'{{\color{{riskgreen}}\checkmark}}'
                else:
                    status = '--'
            else:
                status = '--'

            disp_name = ' '.join(w.capitalize() for w in f.replace('_',' ').split())
            if len(disp_name) > 28:
                disp_name = disp_name[:26] + '..'
            val_str = f'{float(val):.2g}' if _is_numeric(val) else str(val)
            if len(val_str) > 14: val_str = val_str[:12] + '..'
            peer_str = f'{float(pm):.2g}' if pm is not None and _is_numeric(pm) else (str(pm) if pm is not None else '--')
            feat_rows.append((disp_name, val_str, peer_str, status))

        # Cap at 18 rows to fit the page
        feat_rows = feat_rows[:18]

        table_body = '\n'.join(
            rf'\scriptsize {_esc(n)} & \scriptsize {_esc(v)} & \scriptsize {p} & {s} \\'
            for n, v, p, s in feat_rows
        )

        feature_block = rf"""
\begin{{panel}}[title={{Feature Health — Your Values vs Approved Peer Median}}]{{lightgrey}}
{{\tiny
\begin{{tabular}}{{@{{}} p{{3.8cm}} r r c @{{}}}}
\toprule
\textbf{{Feature}} & \textbf{{Yours}} & \textbf{{Peer}} & \textbf{{St.}} \\
\midrule
{table_body}
\bottomrule
\end{{tabular}}
}}
\end{{panel}}
\vspace{{3pt}}
"""

        # Strengths
        strengths_block = ''
        if strengths:
            items = '\n'.join(
                rf'\item \scriptsize {_esc(" ".join(w.capitalize() for w in (s["feature"] if isinstance(s, dict) else s).replace("_"," ").split()))}'
                for s in strengths[:5]
            )
            strengths_block = rf"""
\begin{{panel}}[title={{Your Strengths}}]{{green!8}}
\begin{{itemize}}
{items}
\end{{itemize}}
\end{{panel}}
\vspace{{3pt}}
"""

        # Diagnosis excerpt
        b = self.findings['baseline']
        prob = b['mean']
        n_high = sum(1 for v in self.findings['baseline_per_model'].values() if v >= 0.5)
        n_tot  = len(self.findings['baseline_per_model'])
        diag = (f"{n_high} of {n_tot} models classify this case as high-risk. "
                f"Ensemble default probability: {prob*100:.1f}\\%. "
                f"A small, well-chosen change can shift the consensus.")

        diag_block = rf"""
\begin{{panel}}[title={{Diagnostic Summary}}]{{lightgrey}}
{{\scriptsize {_esc(diag)}}}
\end{{panel}}
"""

        return feature_block + strengths_block + diag_block

    # ------------------------------------------------------------------
    # Column 3: Top actions + pathways + reassessment + tornado
    # ------------------------------------------------------------------
    def _col3(self):
        cfs = self.findings.get('counterfactuals', [])
        pathway_recs = self.findings.get('pathway_recs', {})

        # Top 5 counterfactuals
        cf_rows = []
        for cf in cfs[:6]:
            feat    = cf.get('feature', '')
            impact  = cf.get('mean_impact', 0) * 100
            new_val = cf.get('new_display', cf.get('new_value', ''))
            agree   = cf.get('n_models_agree', 0)
            disp    = ' '.join(w.capitalize() for w in feat.replace('_',' ').split())
            if len(disp) > 24: disp = disp[:22] + '..'
            direction = r'{\color{riskgreen}$\downarrow$}' if impact < 0 else r'{\color{riskred}$\uparrow$}'
            cf_rows.append(
                rf'\scriptsize {_esc(disp)} & \scriptsize {_esc(str(new_val))} & '
                rf'\scriptsize {direction}{abs(impact):.1f}pp & \scriptsize {agree}/{len(self.findings["baseline_per_model"])} \\'
            )

        actions_block = ''
        if cf_rows:
            actions_block = rf"""
\begin{{panel}}[title={{Top Actions to Improve Score}}]{{lightgrey}}
{{\tiny
\begin{{tabular}}{{@{{}} p{{2.5cm}} p{{1.2cm}} r r @{{}}}}
\toprule
\textbf{{Feature}} & \textbf{{Target}} & \textbf{{Impact}} & \textbf{{Agree}} \\
\midrule
""" + '\n'.join(cf_rows) + rf"""
\bottomrule
\end{{tabular}}
}}
\end{{panel}}
\vspace{{3pt}}
"""

        # Pathway summary
        pathway_labels = {
            'restructure':  ('A', 'Restructure Loan',    'orange!12'),
            'routine':      ('B', 'Build Routine',        'blue!8'),
            'long_term':    ('C', 'Strengthen Profile',   'purple!8'),
        }
        pw_items = []
        for key, (letter, label, bg) in pathway_labels.items():
            recs = pathway_recs.get(key, [])
            n    = len(recs)
            if n > 0:
                first = recs[0].get('feature','') if recs else ''
                fdsp  = ' '.join(w.capitalize() for w in first.replace('_',' ').split())
                if len(fdsp) > 20: fdsp = fdsp[:18] + '..'
                pw_items.append(
                    rf'\textbf{{Path {letter}: {_esc(label)}}} ({n} action{"s" if n!=1 else ""}) — '
                    rf'e.g.\ \textit{{{_esc(fdsp)}}}'
                )
            else:
                pw_items.append(rf'\textbf{{Path {letter}: {_esc(label)}}} — no robust actions found')

        pw_block = rf"""
\begin{{panel}}[title={{Three Pathways to Approval}}]{{lightgrey}}
\begin{{itemize}}
""" + '\n'.join(rf'\item \scriptsize {row}' for row in pw_items) + rf"""
\end{{itemize}}
\end{{panel}}
\vspace{{3pt}}
"""

        # Tornado figure
        tornado_path = self.fig_dir / 'tornado.png'
        tornado_block = ''
        if tornado_path.exists():
            tornado_block = rf"""
\begin{{center}}
\includegraphics[width=\linewidth,height=4.5cm,keepaspectratio]{{{self._fp(tornado_path)}}}
\end{{center}}
\vspace{{2pt}}
"""

        # Reassessment schedule
        today = datetime.now()
        m3  = (today + timedelta(days=90)).strftime('%b %Y')
        m6  = (today + timedelta(days=180)).strftime('%b %Y')
        m12 = (today + timedelta(days=365)).strftime('%b %Y')
        reassess_block = rf"""
\begin{{panel}}[title={{Reassessment Schedule}}]{{lightgrey}}
{{\tiny
\begin{{tabular}}{{@{{}}l l@{{}}}}
3 months  & {m3} — Pathway A items visible \\
6 months  & {m6} — Pathway B fully reflected \\
12 months & {m12} — Full effect; escalate if needed \\
\end{{tabular}}
}}
\end{{panel}}
"""

        return actions_block + tornado_block + pw_block + reassess_block

    def _write_footer(self):
        date = datetime.now().strftime('%d %B %Y at %H:%M')
        self.tex.append(rf"""
\vspace{{2pt}}
\noindent\textcolor{{colsep}}{{\rule{{\textwidth}}{{0.4pt}}}}\\[1pt]
{{\tiny\color{{darktext}} Generated by the credit advisory analytics platform on {date}. \
Diagnostic and educational tool only. For binding credit decisions, consult a qualified human adviser.}}
""")

    def _compile(self, tex_path):
        pdf_path = tex_path.with_suffix('.pdf')
        # Replace Unicode em-dash with LaTeX ---
        src = tex_path.read_text(encoding='utf-8')
        src = src.replace('—', '---').replace('–', '--')
        tex_path.write_text(src, encoding='utf-8')

        for engine in ('pdflatex', 'xelatex', 'lualatex'):
            try:
                for _ in range(2):
                    subprocess.run(
                        [engine, '-interaction=nonstopmode', tex_path.name],
                        cwd=tex_path.parent, capture_output=True, text=True, timeout=120
                    )
                if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                    return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        raise RuntimeError(f"PDF compilation failed for one-pager: {tex_path}")


def _is_numeric(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


# ============================================================================
# MODEL LOADING & CLI
# ============================================================================

def _build_model_callables(models_dir):
    """Return a dict {model_name: callable(X_encoded, X_scaled) -> proba_array}"""
    callables = {}

    rf_path = models_dir / 'random_forest.pkl'
    if rf_path.exists():
        import joblib
        rf = joblib.load(rf_path)
        callables['Random Forest'] = lambda X_enc, X_sc, _m=rf: _m.predict_proba(X_enc)[:, 1]

    lr_path = models_dir / 'logistic_regression.pkl'
    if lr_path.exists():
        import joblib
        lr = joblib.load(lr_path)
        callables['Logistic Regression'] = lambda X_enc, X_sc, _m=lr: _m.predict_proba(X_sc)[:, 1]

    xgb_path = models_dir / 'xgboost.json'
    if xgb_path.exists():
        import xgboost as xgb
        xm = xgb.XGBClassifier()
        xm.load_model(str(xgb_path))
        callables['XGBoost'] = lambda X_enc, X_sc, _m=xm: _m.predict_proba(X_enc)[:, 1]

    tabnet_path = models_dir / 'tabnet.zip'
    if tabnet_path.exists():
        from pytorch_tabnet.tab_model import TabNetClassifier
        tn = TabNetClassifier()
        tn.load_model(str(tabnet_path))
        callables['TabNet'] = lambda X_enc, X_sc, _m=tn: _m.predict_proba(
            X_enc.astype(np.float32))[:, 1]

    ftt_path = models_dir / 'fttransformer.pt'
    ftt_cfg  = models_dir / 'fttransformer_config.json'
    if ftt_path.exists() and ftt_cfg.exists():
        import torch
        sys.path.insert(0, str(Path(__file__).parent))
        from run_fttransformer import FTTransformer
        with open(ftt_cfg) as f:
            cfg = json.load(f)
        ftt = FTTransformer(**cfg)
        ftt.load_state_dict(torch.load(str(ftt_path), map_location='cpu'))
        ftt.eval()
        def _ftt(X_enc, X_sc, _m=ftt):
            with torch.no_grad():
                t = torch.FloatTensor(X_sc.astype(np.float32))
                return torch.softmax(_m(t), dim=1)[:, 1].numpy()
        callables['FTTransformer'] = _ftt

    tabfpn_path = models_dir / 'tabfpn.pt'
    tabfpn_cfg  = models_dir / 'tabfpn_config.json'
    if tabfpn_path.exists() and tabfpn_cfg.exists():
        import torch
        sys.path.insert(0, str(Path(__file__).parent))
        from run_tabfpn import TabFPN
        with open(tabfpn_cfg) as f:
            cfg = json.load(f)
        tfpn = TabFPN(**cfg)
        tfpn.load_state_dict(torch.load(str(tabfpn_path), map_location='cpu'))
        tfpn.eval()
        def _tfpn(X_enc, X_sc, _m=tfpn):
            with torch.no_grad():
                t = torch.FloatTensor(X_sc.astype(np.float32))
                return torch.softmax(_m(t), dim=1)[:, 1].numpy()
        callables['TabFPN'] = _tfpn

    return callables

def _load_calibration_metrics(models_dir):
    """Return {model_name: {ECE, Quality}} from saved JSONs (best effort)."""
    out = {}
    cls = models_dir / 'classical_results.json'
    if cls.exists():
        try:
            data = json.loads(cls.read_text())
            for name, d in data.items():
                ece = d.get('ece') or 0
                out[name] = {'ECE': float(ece), 'Quality': d.get('quality', 'N/A')}
        except Exception: pass

    for fname, key in [('fttransformer_results.json', 'FTTransformer'),
                        ('tabfpn_results.json',        'TabFPN')]:
        p = models_dir / fname
        if p.exists():
            try:
                d = json.loads(p.read_text())
                cal = d.get('calibration', {})
                out[key] = {'ECE': float(cal.get('ECE', 0)),
                            'Quality': str(cal.get('Quality', 'N/A'))}
            except Exception: pass
    return out

def _load_approved_pool(models_dir, preprocessor):
    """Load saved test_data.csv, split into raw and encoded approved subset."""
    test_csv = models_dir / 'test_data.csv'
    if not test_csv.exists():
        return None, None
    df = pd.read_csv(test_csv)
    if 'target' not in df.columns:
        return None, None
    approved_raw = df[df['target'] == 0].drop(columns=['target']).reset_index(drop=True)
    feature_names = preprocessor.get('raw_feature_names', preprocessor['feature_names'])
    preproc = preprocessor['preprocessor']
    enc = preproc.transform(approved_raw[feature_names].copy())
    return approved_raw, enc

def _build_fallback_preprocessor(slug, models_dir=None):
    # First: look for a sample CSV saved inside the run folder
    data_path = None
    if models_dir is not None:
        sample_csvs = sorted(Path(models_dir).glob('sample_*_rows.csv'))
        if sample_csvs:
            data_path = sample_csvs[0]
            print(f"[INFO] Using sample CSV for preprocessor rebuild: {data_path}")

    # Second: try known per-dataset filenames
    if data_path is None:
        slug_to_filename = {
            'lending': 'lending_club_q12019_processed_noleak.csv',
            'german': 'german_credit.csv',
            'taiwan': 'credit_default_taiwan.csv',
            'approval': 'credit_approval.csv',
            'mortgage': 'mortgage_with_lags.csv',
        }
        filename = slug_to_filename.get(slug, f'{slug}_credit.csv')
        data_path = Path('data') / filename

    if not Path(data_path).exists():
        raise FileNotFoundError(f"Fallback dataset not found: {data_path}")
    df = pd.read_csv(data_path, low_memory=False)
    if 'target' not in df.columns:
        raise ValueError("Fallback dataset must contain a target column")
    X = df.drop(columns=['target'])
    X, _ = drop_id_columns(X)
    preproc, metadata = build_preprocessor(X)
    return {
        'preprocessor': preproc,
        'feature_names': metadata['raw_feature_names'],
        'raw_feature_names': metadata['raw_feature_names'],
        'transformed_feature_names': metadata['transformed_feature_names'],
        'categorical_cols': metadata['categorical_cols'],
        'numeric_cols': metadata['numeric_cols'],
        'categorical_levels': metadata['categorical_levels'],
    }

def main():
    parser = argparse.ArgumentParser(
        description='Generate a personalised financial-advisory PDF report per case.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Generate a personalised financial-advisory PDF report for one or more
borrowers, using pre-trained models saved by run_models_only.py or run_all_enhanced.py.

Each case in the input becomes one PDF file written to
  output/case_reports/<applicant_id>/case_report_<applicant_id>_<timestamp>.pdf

Plus a single batch summary CSV at output/case_reports/batch_summary.csv

Column names in the use case CSV can be either:
  - Original names (e.g., 'age', 'credit_amount' for German)
  - Standardized names (e.g., 'borrower_age_years', 'loan_amount_requested')
They will be automatically mapped using the Five C's standardization file.

Usage
-----
  python case_report_builder.py                                       # list available model families
  python case_report_builder.py character_capital_capacity_unified    # show input format
  python case_report_builder.py character_capital_capacity_unified --csv cases.csv
  python case_report_builder.py character_capital_capacity_unified --csv cases.csv --applicant-id IND_001
  python case_report_builder.py character_capital_capacity_unified --json '{...}' --id ALICE

Examples
--------
  # Process all cases in CSV
  python case_report_builder.py five_cs_fulldata_xgboost --csv cases/five_cs_test_cases.csv

  # Process ONLY applicant IND_001 from CSV
  python case_report_builder.py five_cs_fulldata_xgboost --csv cases/five_cs_test_cases.csv --applicant-id IND_001

  # Process multiple specific applicants (run command multiple times)
  python case_report_builder.py five_cs_50000rows_classical --csv cases/five_cs_test_cases.csv --applicant-id APP_001
  python case_report_builder.py five_cs_50000rows_classical --csv cases/five_cs_test_cases.csv --applicant-id IND_001

Requires: a previous run of `python run_models_only.py <dataset.csv>`
to have populated `output/models/<family_name>/`.
        """
    )
    parser.add_argument('family', nargs='?',
                        help='Model family folder name (e.g., character_capital_capacity_unified, capital_unified)')
    parser.add_argument('--csv',    help='CSV file with one or more cases (columns can be original or standardized names)')
    parser.add_argument('--json',   help='JSON string with a single case dict')
    parser.add_argument('--id-col', default='applicant_id',
                        help='Column name to use as the applicant identifier '
                             '(default: applicant_id; falls back to row number)')
    parser.add_argument('--id',     help='Override id for single JSON case '
                                          '(ignored for CSV input)')
    parser.add_argument('--applicant-id',
                        help='Filter by specific applicant ID when using --csv '
                             '(e.g., --applicant-id IND_001; processes only this applicant)')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Approval threshold (default 0.5)')
    parser.add_argument('--output-dir', default='output/case_reports',
                        help='Directory where case reports are written')
    parser.add_argument('--max-cases', type=int, default=50,
                        help='Safety cap on the number of cases per batch')
    parser.add_argument('--one-pager', action='store_true',
                        help='Also generate a dense single-page 16:9 landscape summary PDF per case')
    args = parser.parse_args()

    if args.family is None:
        families = [d.name for d in MODELS_BASE.iterdir() if d.is_dir()] if MODELS_BASE.exists() else []
        if families:
            print(f"Available model families: {', '.join(sorted(families))}")
            print("Usage: python case_report_builder.py <family_name> --csv cases.csv")
        else:
            print("No saved models found. Run the full pipeline first.")
        return

    slug = args.family
    models_dir = MODELS_BASE / slug
    if not models_dir.exists():
        print(f"No saved models for '{slug}'.")
        families = [d.name for d in MODELS_BASE.iterdir() if d.is_dir()] if MODELS_BASE.exists() else []
        if families:
            print(f"Available: {', '.join(sorted(families))}")
        return

    import joblib
    try:
        preprocessor = joblib.load(models_dir / 'preprocessor.pkl')
    except (FileNotFoundError, AttributeError) as e:
        print(f"[WARN] Saved preprocessor not found or incompatible: {e}")
        print("[WARN] Rebuilding a fresh preprocessor from the run folder sample CSV...")
        preprocessor = _build_fallback_preprocessor(slug, models_dir)

    # Load metadata separately (contains feature names)
    preprocessor_metadata = {}
    try:
        preprocessor_metadata = joblib.load(models_dir / 'preprocessor_metadata.pkl')
    except FileNotFoundError:
        print("[WARN] Preprocessor metadata not found.")

    # Normalize preprocessor to standard dict format
    preprocessor = _normalize_preprocessor(preprocessor)
    if preprocessor_metadata:
        preprocessor.update(preprocessor_metadata)

    print(f"[INFO] Loading the six saved models for '{slug}'...")
    models = _build_model_callables(models_dir)
    if len(models) == 0:
        print("[ERROR] No usable models found.")
        return
    print(f"[OK] Loaded models: {', '.join(models.keys())}")

    calibration = _load_calibration_metrics(models_dir)
    try:
        approved_raw, approved_enc = _load_approved_pool(models_dir, preprocessor)
    except Exception as e:
        print(f"[WARN] Saved preprocessor failed during case loading: {e}")
        print("[WARN] Rebuilding a fresh preprocessor from the run folder sample CSV...")
        preprocessor = _build_fallback_preprocessor(slug, models_dir)
        approved_raw, approved_enc = _load_approved_pool(models_dir, preprocessor)
    if approved_raw is None:
        print("[WARN] No saved test_data.csv — peer comparison will be unavailable.")

    # Get feature names from metadata if available, otherwise use defaults
    if preprocessor_metadata and 'raw_feature_names' in preprocessor_metadata:
        feature_names = preprocessor_metadata['raw_feature_names']
    elif preprocessor_metadata and 'feature_names' in preprocessor_metadata:
        feature_names = preprocessor_metadata['feature_names']
    else:
        # Fallback: try to get from preprocessor if it has the method
        try:
            feature_names = preprocessor.get_feature_names_out().tolist()
        except:
            feature_names = [f"feature_{i}" for i in range(65)]  # Default for character dataset
    if args.csv is None and args.json is None:
        print(f"\nExpected features for '{slug}' ({len(feature_names)} total):")
        for i, f in enumerate(feature_names, 1):
            print(f"  {i:2d}. {f}")
        print(f"\nUsage:")
        print(f"  python case_report_builder.py {slug} --csv cases.csv")
        print(f"  python case_report_builder.py {slug} --json '{{...}}' --id ALICE")
        return

    if args.csv:
        if not Path(args.csv).exists():
            print(f"Error: file not found: {args.csv}")
            return
        df = pd.read_csv(args.csv)

        # Apply column mapping from Five C's standardization file
        print("\n[MAPPING] Standardizing column names...")
        mapping_df = load_five_cs_mapping()
        df = map_use_case_columns(df, mapping_df)

        # Filter by applicant_id if --applicant-id is specified
        if args.applicant_id:
            if args.id_col not in df.columns:
                print(f"[ERROR] Column '{args.id_col}' not found in CSV. Cannot filter by applicant ID.")
                return
            matched = df[df[args.id_col].astype(str) == str(args.applicant_id)]
            if matched.empty:
                print(f"[ERROR] No applicant found with ID: {args.applicant_id}")
                available_ids = df[args.id_col].astype(str).unique().tolist()
                print(f"[INFO] Available IDs in CSV: {', '.join(available_ids[:10])}")
                if len(available_ids) > 10:
                    print(f"       ... and {len(available_ids) - 10} more")
                return
            df = matched
            print(f"[OK] Filtered to applicant: {args.applicant_id}")

        if 'target' in df.columns:
            df = df.drop(columns=['target'])
        if args.id_col in df.columns:
            ids = df[args.id_col].astype(str).tolist()
            cases_df = df.drop(columns=[args.id_col])
        else:
            ids = [f"case_{i+1:03d}" for i in range(len(df))]
            cases_df = df
    else:
        case = json.loads(args.json)

        # Apply column mapping to single JSON case as well
        print("\n[MAPPING] Standardizing column names...")
        mapping_df = load_five_cs_mapping()
        case_df = pd.DataFrame([case])
        case_df = map_use_case_columns(case_df, mapping_df)
        case = case_df.iloc[0].to_dict()

        case_id = args.id or 'case_001'
        cases_df = pd.DataFrame([case])
        ids = [case_id]

    n_cases = min(len(cases_df), args.max_cases)
    if n_cases < len(cases_df):
        print(f"[WARN] Capping batch at {args.max_cases} cases (use --max-cases to raise).")

    summary_rows = []
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(n_cases):
        case_id = ids[i]
        print(f"\n{'='*60}")
        print(f"  CASE {i+1}/{n_cases}: {case_id}")
        print(f"{'='*60}")

        case_raw = {}
        for f in feature_names:
            v = cases_df.iloc[i].get(f)
            case_raw[f] = v

        print("  [1/2] Running recourse analysis...")
        try:
            findings = analyse_case(case_raw, preprocessor, models,
                                     approved_raw if approved_raw is not None
                                     else pd.DataFrame(columns=feature_names),
                                     approved_enc if approved_enc is not None
                                     else pd.DataFrame(columns=feature_names))
        except Exception as e:
            print(f"  [ERROR] Analysis failed: {e}")
            import traceback; traceback.print_exc()
            continue

        print("  [2/2] Building PDF report...")
        builder = CaseReportBuilder(
            case_id=case_id,
            findings=findings,
            preprocessor=preprocessor,
            model_calibration=calibration,
            dataset_label=DATASET_LABELS.get(slug, slug),
            output_dir=str(output_dir),
            threshold=args.threshold,
        )
        try:
            pdf_path = builder.build()
            kb = pdf_path.stat().st_size / 1024
            print(f"  [OK] {pdf_path.name}  ({kb:.0f} KB)")
        except Exception as e:
            print(f"  [ERROR] PDF compile failed: {e}")
            continue

        if args.one_pager:
            try:
                safe_id       = re.sub(r'[^A-Za-z0-9_.-]', '_', str(case_id))
                fig_dir       = output_dir / safe_id / 'figures'
                fragments_dir = output_dir / 'onepager_fragments'
                index_path    = output_dir / 'onepager_index.json'
                op = OnePagerBuilder(case_id, findings, fig_dir, calibration)
                op_path = op.build(output_dir, fragments_dir, index_path)
                op_kb = op_path.stat().st_size / 1024
                n_pages = len(json.loads(index_path.read_text())) if index_path.exists() else '?'
                print(f"  [OK] {op_path.name}  ({op_kb:.0f} KB, {n_pages} page(s))  [one-pager]")
            except Exception as e:
                print(f"  [WARN] One-pager failed: {e}")

        b = findings['baseline']
        summary_rows.append({
            'applicant_id': case_id,
            'ensemble_probability': round(b['mean'], 4),
            'verdict': 'HIGH_RISK' if b['mean'] >= args.threshold else 'LOW_RISK',
            'votes_default': b['votes_default'],
            'n_models': b['n_models'],
            'std': round(b['std'], 4),
            'pdf_path': str(pdf_path),
        })

    if summary_rows:
        summary_path = output_dir / 'batch_summary.csv'
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
        print(f"\n[OK] Batch summary: {summary_path}")
        print(f"[OK] {len(summary_rows)} report(s) generated in: {output_dir}")
    else:
        print("\n[WARN] No reports generated.")

if __name__ == '__main__':
    main()
