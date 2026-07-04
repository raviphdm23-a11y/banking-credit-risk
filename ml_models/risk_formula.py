"""
Shared continuous PD formula and feature sampling logic.

Used by both:
1. One-time DB migration (realism_migration.py)
2. Seeding scripts (seed_real_bank.py, add_new_customers.py, seed_global_customers.py)

This ensures consistency: same formula, no drift between migration and future seeding.
"""

import numpy as np


def true_pd_nonlinear(de, ic, profit, liq, cibil=700, foir=0.4, regime_multiplier=1.0):
    """
    Non-linear PD formula with risk zones and macro effects.
    Captures real-world behavior better than linear models.

    Args:
        de: debt-to-equity ratio
        ic: interest coverage ratio
        profit: profitability margin (%)
        liq: liquidity ratio
        cibil: CIBIL credit score
        foir: Fixed Obligation to Income ratio
        regime_multiplier: macro regime effect (expansion=0.5, stable=1.0, contraction=2.5)

    Returns:
        float: PD probability (0.0-1.0)
    """
    pd_val = 0.010  # base 1%

    # ── Non-linear DE ratio risk (thresholds matter) ──────────────────
    if de < 2.0:
        pd_val += 0.002  # Safe zone
    elif de < 3.0:
        pd_val += (de - 2.0) * 0.020  # Transition zone (non-linear)
    else:
        pd_val += 0.020 + (de - 3.0) * 0.050  # Danger zone (accelerating risk)

    # ── Interest coverage (concave: low coverage is dangerous) ────────
    if ic > 3.0:
        pd_val += 0.002  # Good coverage
    elif ic > 1.5:
        pd_val += max(0.0, (3.0 - ic) * 0.015)
    else:
        pd_val += 0.040  # Very risky

    # ── Profitability (non-linear relief) ──────────────────────────
    if profit > 15.0:
        pd_val -= 0.010  # Highly profitable → relief
    elif profit > 5.0:
        pd_val -= max(0.0, (profit - 5.0) * 0.0008)
    # else: negative profitability adds risk (already in base)

    # ── Liquidity ratio ───────────────────────────────────────────
    if liq < 1.0:
        pd_val += 0.030  # Danger
    elif liq < 1.5:
        pd_val += 0.015  # Moderate risk
    # else: healthy liquidity

    # ── CIBIL score impact (non-linear; low scores very risky) ────
    if cibil < 550:
        pd_val += 0.050  # Very risky
    elif cibil < 650:
        pd_val += (700 - cibil) / 100 * 0.040
    else:
        pd_val += max(0.0, (700 - cibil) / 700 * 0.015)

    # ── FOIR (Fixed Obligation to Income) ─────────────────────────
    if foir > 0.60:
        pd_val += (foir - 0.60) * 0.10  # Accelerating risk
    elif foir > 0.40:
        pd_val += (foir - 0.40) * 0.05

    # ── Macro regime effect ──────────────────────────────────────
    pd_val *= regime_multiplier

    return float(np.clip(pd_val, 0.0001, 0.999))


def sample_correlated_features(rng, base_income, base_tenure, base_profitability):
    """
    Sample realistic, correlated customer features.

    Income → CIBIL (correlation ~0.6)
    Tenure → CIBIL (correlation ~0.5)
    Profitability → CIBIL (correlation ~0.4)

    Args:
        rng: numpy random generator
        base_income: annual income
        base_tenure: years employed
        base_profitability: profitability margin (%)

    Returns:
        dict: sampled features with noise and correlations
    """
    # CIBIL score with correlations to income, tenure, profitability
    cibil_base = 680  # mean CIBIL

    # Income contribution: log(income) → CIBIL correlation
    income_log = np.log(max(base_income, 100000))
    cibil_income_effect = (income_log - 12.5) * 30

    # Tenure contribution: more tenure → better CIBIL
    cibil_tenure_effect = base_tenure * 2

    # Profitability contribution: better profit → better CIBIL
    cibil_profit_effect = np.clip(base_profitability, 0, 30)

    # Combined with noise
    cibil = cibil_base + cibil_income_effect + cibil_tenure_effect + cibil_profit_effect
    cibil = cibil + rng.normal(0, 20)  # Additional measurement noise
    cibil = int(np.clip(cibil, 300, 900))

    return {
        'cibil_score': cibil,
    }


def add_measurement_noise(rng, de_ratio, int_coverage, profitability, liquidity_ratio,
                          annual_income, years_employed, foir):
    """
    Add realistic measurement noise to observed features.

    This simulates that banks don't observe true values perfectly:
    - CIBIL has update lag and observation error
    - Income is estimated/declared, not verified
    - Financial ratios are computed from statements with noise

    Args:
        rng: numpy random generator
        de_ratio: debt-to-equity ratio
        int_coverage: interest coverage
        profitability: profitability margin
        liquidity_ratio: liquidity ratio
        annual_income: annual income
        years_employed: years employed
        foir: FOIR ratio

    Returns:
        dict: features with noise applied
    """
    return {
        'de_ratio': np.clip(de_ratio + rng.normal(0, 0.15), 0.05, 10.0),
        'int_coverage': np.clip(int_coverage + rng.normal(0, 0.3), 0.3, 20.0),
        'profitability': np.clip(profitability + rng.normal(0, 2.0), -60.0, 80.0),
        'liquidity_ratio': np.clip(liquidity_ratio + rng.normal(0, 0.1), 0.2, 5.0),
        'annual_income': np.clip(annual_income * (1 + rng.normal(0, 0.15)), 100000, 7000000),
        'years_employed': np.clip(years_employed + rng.normal(0, 0.5), 0, 50),
        'foir': np.clip(foir + rng.normal(0, 0.03), 0.05, 0.85),
    }


def simple_default_rate_model(annual_income, age, macro_regime_score, rng):
    """
    Simple, independent default-rate model (NOT derived from risk features).

    This creates default probability based ONLY on:
    - Income level (proxy for repayment capacity)
    - Age/maturity
    - Macro regime (economic cycle)
    - Random noise

    NOT on financial ratios, CIBIL, or any features that the model will learn.
    This breaks the deterministic feature→default relationship.

    Args:
        annual_income: annual income (numeric)
        age: customer age
        macro_regime_score: macro regime multiplier (0.5=expansion, 1.0=stable, 2.5=contraction)
        rng: numpy random generator

    Returns:
        float: default probability (0.0-1.0) independent of risk features
    """
    # Base default rate: ~2%
    pd = 0.02

    # Income effect: lower income → higher default risk
    # Piecewise: <300k → +3%, 300-500k → +1%, 500-1M → 0%, >1M → -0.5%
    if annual_income < 300000:
        pd += 0.03
    elif annual_income < 500000:
        pd += 0.01
    elif annual_income > 1000000:
        pd -= 0.005

    # Age effect: younger → higher risk (proxy for maturity)
    if age < 30:
        pd += 0.01
    elif age > 55:
        pd += 0.005

    # Macro regime effect (independent of feature-level PD)
    # Expansion: lower defaults, Contraction: higher defaults
    pd *= macro_regime_score

    # Random noise: ±50% to break perfect separability
    noise = rng.normal(1.0, 0.3)  # mean=1.0, std=0.3
    pd *= noise

    return float(np.clip(pd, 0.001, 0.15))  # cap at 15% max


def calibrate_pd_threshold_per_bank(current_default_rate, target_npa_rate):
    """
    Calibrate PD scale so that aggregate NPA rate stays close to target.

    When resampling features, PD will change. This function returns a scale factor
    to adjust PD values per-bank so the final aggregate NPA rate matches the
    original target (e.g., if bank had 5% GNPA, keep it at ~5% ±1-2%).

    Args:
        current_default_rate: observed default rate after resampling (0.0-1.0)
        target_npa_rate: target NPA rate to maintain (0.0-1.0)

    Returns:
        float: scale factor to apply to pd_score before binomial sampling
    """
    if current_default_rate < 0.001:
        current_default_rate = 0.001  # avoid division by zero

    # Ratio adjustment: if we're at 12% but want 8%, scale by 8/12 = 0.667
    scale = target_npa_rate / current_default_rate
    return float(np.clip(scale, 0.5, 2.0))  # don't go too extreme
