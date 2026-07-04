"""
Realistic Synthetic Data Generator for PD Model Training

Generates credit risk data that mimics real-world challenges:
1. Measurement noise on all features (CIBIL ±10 points, income ±15%, etc.)
2. Probabilistic defaults (PD as actual probability, not deterministic threshold)
3. Feature correlations (income→CIBIL→tenure, etc.)
4. Non-linear risk curves (DE ratios: safe/transition/danger zones)
5. Macro regime effects (economic cycles change default rates)

This allows models to differentiate and show realistic AUC (0.70-0.85) instead of perfect 1.0.
"""

import numpy as np
import pandas as pd
import os
from datetime import datetime, timedelta
import random
import string

# Bank configurations with segment-specific default rates
BANKS = [
    {'bank_id': 'BANK001_HDFC_Bank', 'code': 'HDFC', 'n_samples': 2500, 'segment': 'corporate', 'base_default_rate': 0.01},
    {'bank_id': 'BANK002_ICICI_Bank', 'code': 'ICICI', 'n_samples': 2800, 'segment': 'sme', 'base_default_rate': 0.02},
    {'bank_id': 'BANK003_Axis_Bank', 'code': 'AXIS', 'n_samples': 2000, 'segment': 'corporate', 'base_default_rate': 0.015},
    {'bank_id': 'BANK004_SBI', 'code': 'SBI', 'n_samples': 3000, 'segment': 'retail', 'base_default_rate': 0.015},
    {'bank_id': 'BANK005_BoB', 'code': 'BOB', 'n_samples': 1800, 'segment': 'sme', 'base_default_rate': 0.025},
    {'bank_id': 'BANK006_PNB', 'code': 'PNB', 'n_samples': 2200, 'segment': 'retail', 'base_default_rate': 0.02},
]

OUTPUT_FILENAME = 'realistic_synthetic_data.csv'
BASE_DATE = datetime(2020, 1, 1)
END_DATE = datetime(2025, 12, 31)

# Macro regime definitions
MACRO_REGIMES = [
    {'name': 'expansion', 'period_months': 18, 'default_rate_multiplier': 0.5, 'policy_rate': 4.0},
    {'name': 'stable', 'period_months': 12, 'default_rate_multiplier': 1.0, 'policy_rate': 5.5},
    {'name': 'contraction', 'period_months': 6, 'default_rate_multiplier': 2.5, 'policy_rate': 7.0},
]


def _get_macro_regime(observation_date, seed):
    """Determine macro regime based on observation date."""
    days_from_start = (observation_date - BASE_DATE).days
    regime_index = (days_from_start // 180) % len(MACRO_REGIMES)  # Switch every ~6 months
    return MACRO_REGIMES[regime_index]


def _true_pd_nonlinear(de, ic, pm, lr, cibil=700, foir=0.4, regime_multiplier=1.0):
    """
    Non-linear PD formula with risk zones and macro effects.
    Captures real-world behavior better than linear models.
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
    if pm > 15.0:
        pd_val -= 0.010  # Highly profitable → relief
    elif pm > 5.0:
        pd_val -= max(0.0, (pm - 5.0) * 0.0008)
    # else: negative profitability adds risk (already in base)

    # ── Liquidity ratio ───────────────────────────────────────────
    if lr < 1.0:
        pd_val += 0.030  # Danger
    elif lr < 1.5:
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


def _generate_bank_data_realistic(bank_cfg, seed=None):
    """Generate realistic loan dataset with all enhancements."""
    rng = np.random.default_rng(seed)
    n = bank_cfg['n_samples']
    bank_id = bank_cfg['bank_id']
    code = bank_cfg['code']
    segment = bank_cfg['segment']
    base_default_rate = bank_cfg['base_default_rate']

    print(f"\n  Generating {bank_id} ({segment} segment, {n} loans)...")

    # ── Base feature distributions ────────────────────────────────────
    de_ratio_true = rng.exponential(scale=1.0, size=n).clip(0.1, 6.0)
    int_cov_true = rng.gamma(shape=3.0, scale=2.0, size=n).clip(0.5, 15.0)
    profit_mg_true = rng.normal(loc=10.0, scale=12.0, size=n).clip(-50.0, 60.0)
    liq_ratio_true = rng.gamma(shape=4.0, scale=0.4, size=n).clip(0.3, 4.0)

    age = rng.normal(42, 12, size=n).clip(25, 75)
    emp_type = rng.choice([1, 2, 3, 4, 5, 6, 7], size=n,
                           p=[0.18, 0.35, 0.15, 0.15, 0.07, 0.05, 0.05])
    years_employed_true = rng.gamma(shape=2.0, scale=4.0, size=n).clip(0, 40)
    annual_income_true = np.exp(rng.normal(13.2, 0.8, size=n)).clip(200000, 5000000)
    foir_true = rng.beta(2.2, 3.5, size=n).clip(0.05, 0.75)
    cibil_score_true = rng.normal(680, 95, size=n).clip(300, 900).round()

    num_dependents = rng.poisson(2.0, size=n).clip(0, 10)
    city_tier = rng.choice([1, 2, 3], size=n, p=[0.25, 0.40, 0.35])
    education = rng.choice([1, 2, 3, 4, 5, 6], size=n,
                           p=[0.05, 0.10, 0.20, 0.40, 0.20, 0.05])
    residence_type = rng.choice([1, 2, 3, 4], size=n, p=[0.35, 0.40, 0.10, 0.15])
    loan_purpose = rng.choice(range(1, 11), size=n)
    prev_default = rng.binomial(1, base_default_rate * 2.0, size=n).clip(0, 1)
    months_as_cust = rng.integers(0, 240, size=n)
    late_payments = rng.poisson(0.3, size=n).clip(0, 10)
    existing_loans = rng.poisson(1.2, size=n).clip(0, 8)
    existing_products = rng.poisson(2.5, size=n).clip(0, 15)
    is_rural = rng.binomial(1, 0.25, size=n)

    # ── Feature correlations (realistic) ──────────────────────────────
    # Higher income → better CIBIL (correlation ~0.6)
    cibil_score = cibil_score_true + (np.log(annual_income_true) - 13.0) * 30 + rng.normal(0, 30, size=n)
    cibil_score = cibil_score.clip(300, 900).round().astype(int)

    # More employment tenure → better CIBIL (correlation ~0.5)
    cibil_score = cibil_score + years_employed_true * 2 + rng.normal(0, 15, size=n)
    cibil_score = cibil_score.clip(300, 900).round().astype(int)

    # Higher profitability → better CIBIL
    cibil_score = cibil_score + np.clip(profit_mg_true, 0, 30) + rng.normal(0, 10, size=n)
    cibil_score = cibil_score.clip(300, 900).round().astype(int)

    # ── Observation dates and macro regime ───────────────────────────
    total_days = (END_DATE - BASE_DATE).days
    obs_dates = []
    regimes = []
    for i in range(n):
        date = BASE_DATE + timedelta(days=int(rng.integers(0, total_days)))
        obs_dates.append(date)
        regime = _get_macro_regime(date, seed)
        regimes.append(regime)

    # ── Feature measurement noise (realistic observation errors) ──────
    # Features observed with measurement error, not true values
    de_ratio = de_ratio_true + rng.normal(0, 0.15, size=n)  # ±0.15 error
    int_cov = int_cov_true + rng.normal(0, 0.3, size=n)
    profit_mg = profit_mg_true + rng.normal(0, 2.0, size=n)
    liq_ratio = liq_ratio_true + rng.normal(0, 0.1, size=n)
    years_employed = years_employed_true + rng.normal(0, 0.5, size=n)
    foir = foir_true + rng.normal(0, 0.03, size=n)
    foir = foir.clip(0.05, 0.85)

    # Income observations have ±15% error
    annual_income = annual_income_true * (1 + rng.normal(0, 0.15, size=n))
    annual_income = annual_income.clip(150000, 6000000)

    # ── Compute PD with macro effects ────────────────────────────────
    pd_vals = np.zeros(n)
    for i in range(n):
        regime = regimes[i]
        pd_vals[i] = _true_pd_nonlinear(
            de_ratio[i], int_cov[i], profit_mg[i], liq_ratio[i],
            cibil_score[i], foir[i],
            regime_multiplier=regime['default_rate_multiplier']
        )

    # ── Probabilistic defaults (PD as actual probability, not threshold) ────
    # This creates realistic variation: some high-PD survive, some low-PD default
    def_flag = rng.binomial(1, p=pd_vals).astype(int)

    # ── Unexpected defaults: some good customers default by external shock ─
    # Add ~10% "unexpected" defaults (economic shock, personal hardship)
    unexpected_defaults = rng.binomial(1, p=0.10, size=n)  # 10% of loans get macro shock
    pd_shock = 0.30  # If shocked, 30% probability of default
    for i in range(n):
        if unexpected_defaults[i] and def_flag[i] == 0:  # Don't override existing defaults
            if rng.random() < pd_shock:
                def_flag[i] = 1

    # ── Loan IDs ──────────────────────────────────────────────────────
    loan_ids = [
        f"{code}-LN-{i+1:05d}-{''.join(rng.choice(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'), 4))}"
        for i in range(n)
    ]

    # Build dataframe
    df = pd.DataFrame({
        'bank_id': bank_id,
        'loan_id': loan_ids,
        'de_ratio': np.round(np.clip(de_ratio, 0.1, 10.0), 4),
        'interest_coverage': np.round(np.clip(int_cov, 0.3, 20.0), 4),
        'profitability': np.round(np.clip(profit_mg, -60.0, 80.0), 4),
        'liquidity_ratio': np.round(np.clip(liq_ratio, 0.2, 5.0), 4),
        'default_flag': def_flag,
        'pd_observed': np.round(pd_vals, 6),
        'observation_date': [d.strftime('%Y-%m-%d') for d in obs_dates],
        'macro_regime': [r['name'] for r in regimes],
        'age': np.round(age, 1),
        'employment_type_enc': emp_type.astype(int),
        'years_employed': np.round(np.clip(years_employed, 0, 50), 1),
        'annual_income': np.round(np.clip(annual_income, 100000, 7000000), 0).astype(int),
        'foir': np.round(foir, 4),
        'num_dependents': num_dependents.astype(int),
        'city_tier_enc': city_tier.astype(int),
        'education_enc': education.astype(int),
        'residence_type_enc': residence_type.astype(int),
        'loan_purpose_enc': loan_purpose.astype(int),
        'cibil_score': cibil_score.astype(int),
        'previous_default_flag': prev_default.astype(int),
        'months_as_customer': months_as_cust.astype(int),
        'num_late_payments_past_12m': late_payments.astype(int),
        'existing_loans_count': existing_loans.astype(int),
        'num_existing_products': existing_products.astype(int),
        'is_rural': is_rural.astype(int),
    })

    actual_dr = df['default_flag'].mean() * 100
    print(f"    [OK] Generated {len(df):,} loans | Default rate: {actual_dr:.2f}% | "
          f"Macro regimes: {', '.join(set(df['macro_regime']))}")

    return df


def generate_all_realistic(output_dir=None, copy_to_training=False, seed_base=42):
    """
    Generate consolidated realistic synthetic dataset for all banks.

    Returns:
        dict with file path, total rows, banks, and realistic metrics
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if output_dir is None:
        output_dir = os.path.join(project_root, 'data', 'synthetic')

    training_dir = os.path.join(project_root, 'data', 'training')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(training_dir, exist_ok=True)

    print("\n" + "=" * 80)
    print("GENERATING REALISTIC SYNTHETIC DATA FOR PD MODEL TRAINING")
    print("=" * 80)
    print("\nEnhancements:")
    print("  [+] Measurement noise on all features (CIBIL +/-10, income +/-15%, ratios +/-noise)")
    print("  [+] Probabilistic defaults (PD as actual probability, not threshold)")
    print("  [+] Feature correlations (income -> CIBIL -> tenure)")
    print("  [+] Non-linear risk curves (DE ratio: safe/transition/danger zones)")
    print("  [+] Macro regime effects (expansion/stable/contraction cycles)")
    print("  [+] Unexpected defaults (external shocks: ~10% of loans)")
    print("\nExpected result: AUC 0.70-0.85 (realistic) instead of 1.0 (synthetic)")
    print("=" * 80)

    frames = []
    total_rows = 0

    for idx, bank in enumerate(BANKS):
        df = _generate_bank_data_realistic(bank, seed=seed_base + idx)
        frames.append(df)
        total_rows += len(df)

    # Consolidate
    consolidated = pd.concat(frames, ignore_index=True)

    # Save
    filepath = os.path.join(output_dir, OUTPUT_FILENAME)
    consolidated.to_csv(filepath, index=False)
    print(f"\n[OK] Saved {total_rows:,} rows to: {filepath}")

    # Copy to training if requested
    if copy_to_training:
        training_filepath = os.path.join(training_dir, OUTPUT_FILENAME)
        consolidated.to_csv(training_filepath, index=False)
        print(f"[OK] Copied to training dir: {training_filepath}")

    # Summary statistics
    print("\n" + "=" * 80)
    print("DATASET SUMMARY")
    print("=" * 80)
    print(f"Total loans: {total_rows:,}")
    print(f"Total defaults: {consolidated['default_flag'].sum():,}")
    print(f"Overall default rate: {consolidated['default_flag'].mean() * 100:.2f}%")
    print(f"\nBy segment:")
    for segment in ['corporate', 'sme', 'retail']:
        segment_df = consolidated[consolidated['bank_id'].str.contains(
            '|'.join([b['bank_id'] for b in BANKS if b['segment'] == segment])
        )]
        if len(segment_df) > 0:
            dr = segment_df['default_flag'].mean() * 100
            print(f"  {segment:12s}: {len(segment_df):6,} loans | default rate {dr:.2f}%")

    print(f"\nBy macro regime:")
    for regime in consolidated['macro_regime'].unique():
        regime_df = consolidated[consolidated['macro_regime'] == regime]
        dr = regime_df['default_flag'].mean() * 100
        print(f"  {regime:12s}: {len(regime_df):6,} loans | default rate {dr:.2f}%")

    print("\nFeature statistics (mean ± std):")
    print(f"  DE Ratio:          {consolidated['de_ratio'].mean():.2f} ± {consolidated['de_ratio'].std():.2f}")
    print(f"  Interest Coverage: {consolidated['interest_coverage'].mean():.2f} ± {consolidated['interest_coverage'].std():.2f}")
    print(f"  Profitability:     {consolidated['profitability'].mean():.2f} ± {consolidated['profitability'].std():.2f}")
    print(f"  CIBIL Score:       {consolidated['cibil_score'].mean():.0f} ± {consolidated['cibil_score'].std():.0f}")
    print(f"  FOIR:              {consolidated['foir'].mean():.3f} ± {consolidated['foir'].std():.3f}")
    print("=" * 80 + "\n")

    return {
        'file': filepath,
        'total_rows': total_rows,
        'banks': [b['bank_id'] for b in BANKS],
        'default_rate': consolidated['default_flag'].mean(),
    }


if __name__ == '__main__':
    result = generate_all_realistic(copy_to_training=True)
    print(f"\n[OK] Ready for training from: {result['file']}")
