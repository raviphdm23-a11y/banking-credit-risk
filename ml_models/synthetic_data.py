"""
Synthetic Data Generator for PD Model Training
Generates realistic credit risk data for Indian banks.
All banks are consolidated into a single CSV file dropped into data/training/.
"""

import numpy as np
import pandas as pd
import os
import random
import string
from datetime import datetime, timedelta

# ── Indian bank configurations ────────────────────────────────────────────────
# bank_id embeds both code and full name: CODE_Full_Bank_Name
BANKS = [
    {'bank_id': 'SBI_State_Bank_of_India',   'code': 'SBI',   'n_samples': 3000, 'default_rate': 0.09},
    {'bank_id': 'HDFC_HDFC_Bank',            'code': 'HDFC',  'n_samples': 2500, 'default_rate': 0.06},
    {'bank_id': 'ICICI_ICICI_Bank',          'code': 'ICICI', 'n_samples': 2800, 'default_rate': 0.07},
    {'bank_id': 'AXIS_Axis_Bank',            'code': 'AXIS',  'n_samples': 2000, 'default_rate': 0.08},
    {'bank_id': 'PNB_Punjab_National_Bank',  'code': 'PNB',   'n_samples': 2200, 'default_rate': 0.12},
    {'bank_id': 'BOB_Bank_of_Baroda',        'code': 'BOB',   'n_samples': 1800, 'default_rate': 0.10},
]

OUTPUT_FILENAME = 'indian_banks_synthetic_2024.csv'

BASE_DATE = datetime(2023, 1, 1)
END_DATE  = datetime(2024, 12, 31)


def _random_loan_id(code, idx):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{code}-LN-{idx:05d}-{suffix}"


def _true_pd(de, ic, pm, lr, cibil=700, prev_default=0, foir=0.4, late_payments=0):
    """
    Ground-truth PD formula incorporating financial ratios and key KYC signals.
    Returns PD as a decimal in [0.0001, 1.0].
    """
    pd_val = 0.02                                          # base 2%
    pd_val += de * 0.015                                   # leverage risk
    pd_val += max(0.0, (4.0 - ic) * 0.010)                # low coverage risk
    pd_val -= max(0.0, pm * 0.001)                         # profitability relief
    pd_val += max(0.0, (1.5 - lr) * 0.030)                # liquidity risk
    # KYC signals
    pd_val += max(0.0, (700 - cibil) / 700 * 0.04)        # CIBIL: lower score → higher PD
    pd_val += prev_default * 0.06                          # prior default: +6%
    pd_val += max(0.0, (foir - 0.4) * 0.05)               # FOIR above 40% → risk
    pd_val += late_payments * 0.005                        # each late payment adds 0.5%
    return float(np.clip(pd_val, 0.0001, 1.0))


def _generate_bank_data(bank_cfg, seed=None):
    """Generate one bank's synthetic loan dataset."""
    rng = np.random.default_rng(seed)

    n         = bank_cfg['n_samples']
    bank_id   = bank_cfg['bank_id']
    code      = bank_cfg['code']
    def_rate  = bank_cfg['default_rate']

    # ── Financial ratio distributions (tuned for Indian corporate lending) ──────
    de_ratio    = rng.exponential(scale=1.2, size=n).clip(0.1, 8.0)
    int_cov     = rng.gamma(shape=3.0, scale=2.0, size=n).clip(0.3, 18.0)
    profit_mg   = rng.normal(loc=12.0, scale=10.0, size=n).clip(-40.0, 60.0)
    liq_ratio   = rng.gamma(shape=4.0, scale=0.4, size=n).clip(0.2, 4.0)

    # ── KYC / demographic distributions ──────────────────────────────────────
    age               = rng.normal(35, 10, size=n).clip(18, 80).astype(float)
    emp_type          = rng.choice([1,2,3,4,5,6,7], size=n,
                                   p=[0.18,0.35,0.15,0.15,0.07,0.05,0.05])
    years_employed    = rng.gamma(shape=2.5, scale=3.0, size=n).clip(0, 45).round(1)
    annual_income     = np.exp(rng.normal(13.3, 0.7, size=n)).clip(100000, 9999999).round(-3)
    foir              = rng.beta(2, 3, size=n).clip(0.05, 0.85).round(4)
    num_dependents    = rng.poisson(2.0, size=n).clip(0, 10)
    city_tier         = rng.choice([1,2,3], size=n, p=[0.25, 0.40, 0.35])
    education         = rng.choice([1,2,3,4,5,6], size=n,
                                   p=[0.05, 0.10, 0.20, 0.40, 0.20, 0.05])
    residence_type    = rng.choice([1,2,3,4], size=n, p=[0.35, 0.40, 0.10, 0.15])
    loan_purpose      = rng.choice(range(1, 11), size=n)
    cibil_score       = rng.normal(680, 80, size=n).clip(300, 900).round().astype(int)
    prev_default      = rng.binomial(1, def_rate * 1.5, size=n).clip(0, 1)
    months_as_cust    = rng.integers(0, 241, size=n)
    late_payments     = rng.poisson(0.4, size=n).clip(0, 12)
    existing_loans    = rng.poisson(1.5, size=n).clip(0, 8)
    existing_products = rng.poisson(3.0, size=n).clip(0, 15)
    is_rural          = rng.binomial(1, 0.30, size=n)

    # ── Compute true PD with Gaussian noise ───────────────────────────────────
    noise       = rng.normal(0, 0.015, size=n)
    pd_vals     = np.array([
        float(np.clip(
            _true_pd(de_ratio[i], int_cov[i], profit_mg[i], liq_ratio[i],
                     cibil_score[i], prev_default[i], foir[i], late_payments[i]) + noise[i],
            0.0001, 1.0
        ))
        for i in range(n)
    ])

    # ── Default flag: 1 if pd > threshold ─────────────────────────────────────
    threshold   = np.percentile(pd_vals, (1 - def_rate) * 100)
    def_flag    = (pd_vals >= threshold).astype(int)

    # ── Observation dates spread across 2023–2024 ─────────────────────────────
    total_days  = (END_DATE - BASE_DATE).days
    obs_dates   = [
        (BASE_DATE + timedelta(days=int(rng.integers(0, total_days)))).strftime('%Y-%m-%d')
        for _ in range(n)
    ]

    # ── Loan IDs (use short code as prefix for readability) ───────────────────
    random.seed(seed)
    loan_ids = [_random_loan_id(code, i + 1) for i in range(n)]

    df = pd.DataFrame({
        'bank_id':                    bank_id,
        'loan_id':                    loan_ids,
        'de_ratio':                   np.round(de_ratio, 4),
        'interest_coverage':          np.round(int_cov, 4),
        'profitability':              np.round(profit_mg, 4),
        'liquidity_ratio':            np.round(liq_ratio, 4),
        'default_flag':               def_flag,
        'pd_observed':                np.round(pd_vals, 6),
        'observation_date':           obs_dates,
        'age':                        np.round(age, 1),
        'employment_type_enc':        emp_type.astype(int),
        'years_employed':             years_employed,
        'annual_income':              annual_income.astype(float),
        'foir':                       foir,
        'num_dependents':             num_dependents.astype(int),
        'city_tier_enc':              city_tier.astype(int),
        'education_enc':              education.astype(int),
        'residence_type_enc':         residence_type.astype(int),
        'loan_purpose_enc':           loan_purpose.astype(int),
        'cibil_score':                cibil_score,
        'previous_default_flag':      prev_default.astype(int),
        'months_as_customer':         months_as_cust.astype(int),
        'num_late_payments_past_12m': late_payments.astype(int),
        'existing_loans_count':       existing_loans.astype(int),
        'num_existing_products':      existing_products.astype(int),
        'is_rural':                   is_rural.astype(int),
    })

    return df


def generate_all(output_dir=None, copy_to_training=True, seed_base=42):
    """
    Generate a single consolidated synthetic CSV for all Indian banks.

    Args:
        output_dir       : folder for synthetic file (default: data/synthetic/)
        copy_to_training : if True, also copy file into data/training/
        seed_base        : base random seed (each bank gets seed_base + index)

    Returns:
        dict  { 'file': filepath, 'total_rows': int, 'banks': [bank_id, ...] }
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if output_dir is None:
        output_dir = os.path.join(project_root, 'data', 'synthetic')

    training_dir = os.path.join(project_root, 'data', 'training')
    os.makedirs(output_dir,   exist_ok=True)
    os.makedirs(training_dir, exist_ok=True)

    print("=" * 60)
    print("Generating synthetic PD training data (Indian banks)")
    print("=" * 60)

    frames = []
    for idx, bank in enumerate(BANKS):
        df        = _generate_bank_data(bank, seed=seed_base + idx)
        actual_dr = df['default_flag'].mean() * 100
        print(f"  {bank['bank_id']:35s} | {len(df):5,} rows | default rate {actual_dr:.1f}%")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True).sample(frac=1, random_state=seed_base).reset_index(drop=True)

    out_path = os.path.join(output_dir, OUTPUT_FILENAME)
    combined.to_csv(out_path, index=False)

    if copy_to_training:
        train_path = os.path.join(training_dir, OUTPUT_FILENAME)
        combined.to_csv(train_path, index=False)

    print("-" * 60)
    print(f"  Total: {len(BANKS)} banks | {len(combined):,} rows -> {OUTPUT_FILENAME}")
    print(f"  Synthetic file   : {out_path}")
    if copy_to_training:
        print(f"  Training drop    : {training_dir}")
    print("=" * 60)

    return {
        'file':       out_path,
        'total_rows': len(combined),
        'banks':      [b['bank_id'] for b in BANKS],
    }


if __name__ == '__main__':
    generate_all()
