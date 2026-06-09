"""
Synthetic Data Generator for PD Model Training
Generates realistic credit risk data for Indian banks.
Each bank produces a separate CSV file dropped into data/training/.
"""

import numpy as np
import pandas as pd
import os
import random
import string
from datetime import datetime, timedelta

# ── Indian bank configurations ────────────────────────────────────────────────
BANKS = [
    {'bank_id': 'SBI',    'bank_name': 'State Bank of India',        'n_samples': 3000, 'default_rate': 0.09},
    {'bank_id': 'HDFC',   'bank_name': 'HDFC Bank',                   'n_samples': 2500, 'default_rate': 0.06},
    {'bank_id': 'ICICI',  'bank_name': 'ICICI Bank',                  'n_samples': 2800, 'default_rate': 0.07},
    {'bank_id': 'AXIS',   'bank_name': 'Axis Bank',                   'n_samples': 2000, 'default_rate': 0.08},
    {'bank_id': 'PNB',    'bank_name': 'Punjab National Bank',        'n_samples': 2200, 'default_rate': 0.12},
    {'bank_id': 'BOB',    'bank_name': 'Bank of Baroda',              'n_samples': 1800, 'default_rate': 0.10},
]

FILE_NAMES = {
    'SBI':   'sbi_2024.csv',
    'HDFC':  'hdfc_bank_2024.csv',
    'ICICI': 'icici_bank_2024.csv',
    'AXIS':  'axis_bank_2024.csv',
    'PNB':   'pnb_2024.csv',
    'BOB':   'bank_of_baroda_2024.csv',
}

BASE_DATE = datetime(2023, 1, 1)
END_DATE  = datetime(2024, 12, 31)


def _random_loan_id(bank_id, idx):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{bank_id}-LN-{idx:05d}-{suffix}"


def _true_pd(de, ic, pm, lr):
    """
    Ground-truth PD formula the Random Forest is trained to learn.
    Inputs:
        de  – Debt/Equity ratio
        ic  – Interest Coverage ratio
        pm  – Profitability (Net Profit Margin %)
        lr  – Liquidity (Current Ratio)
    Returns PD as a decimal in [0.0001, 1.0].
    """
    pd_val = 0.02                                          # base 2%
    pd_val += de * 0.015                                   # leverage risk
    pd_val += max(0.0, (4.0 - ic) * 0.010)                # low coverage risk
    pd_val -= max(0.0, pm * 0.001)                         # profitability relief
    pd_val += max(0.0, (1.5 - lr) * 0.030)                # liquidity risk
    return float(np.clip(pd_val, 0.0001, 1.0))


def _generate_bank_data(bank_cfg, seed=None):
    """Generate one bank's synthetic loan dataset."""
    rng = np.random.default_rng(seed)

    n          = bank_cfg['n_samples']
    bank_id    = bank_cfg['bank_id']
    bank_name  = bank_cfg['bank_name']
    def_rate   = bank_cfg['default_rate']

    # ── Feature distributions (tuned for Indian corporate lending) ─────────────
    de_ratio    = rng.exponential(scale=1.2, size=n).clip(0.1, 8.0)
    int_cov     = rng.gamma(shape=3.0, scale=2.0, size=n).clip(0.3, 18.0)
    profit_mg   = rng.normal(loc=12.0, scale=10.0, size=n).clip(-40.0, 60.0)
    liq_ratio   = rng.gamma(shape=4.0, scale=0.4, size=n).clip(0.2, 4.0)

    # ── Compute true PD with Gaussian noise ───────────────────────────────────
    noise       = rng.normal(0, 0.015, size=n)
    pd_vals     = np.array([
        float(np.clip(_true_pd(de_ratio[i], int_cov[i], profit_mg[i], liq_ratio[i]) + noise[i], 0.0001, 1.0))
        for i in range(n)
    ])

    # ── Default flag: 1 if pd > threshold or random draw ──────────────────────
    threshold   = np.percentile(pd_vals, (1 - def_rate) * 100)
    def_flag    = (pd_vals >= threshold).astype(int)

    # ── Observation dates spread across 2023–2024 ─────────────────────────────
    total_days  = (END_DATE - BASE_DATE).days
    obs_dates   = [
        (BASE_DATE + timedelta(days=int(rng.integers(0, total_days)))).strftime('%Y-%m-%d')
        for _ in range(n)
    ]

    # ── Loan IDs ───────────────────────────────────────────────────────────────
    random.seed(seed)
    loan_ids = [_random_loan_id(bank_id, i + 1) for i in range(n)]

    df = pd.DataFrame({
        'bank_id':          bank_id,
        'bank_name':        bank_name,
        'loan_id':          loan_ids,
        'de_ratio':         np.round(de_ratio, 4),
        'interest_coverage': np.round(int_cov, 4),
        'profitability':    np.round(profit_mg, 4),
        'liquidity_ratio':  np.round(liq_ratio, 4),
        'default_flag':     def_flag,
        'pd_observed':      np.round(pd_vals, 6),
        'observation_date': obs_dates,
    })

    return df


def generate_all(output_dir=None, copy_to_training=True, seed_base=42):
    """
    Generate synthetic CSV files for all Indian banks.

    Args:
        output_dir       : folder for synthetic files (default: data/synthetic/)
        copy_to_training : if True, also copy files into data/training/
        seed_base        : base random seed (each bank gets seed_base + index)

    Returns:
        dict  { bank_id: filepath }
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if output_dir is None:
        output_dir = os.path.join(project_root, 'data', 'synthetic')

    training_dir = os.path.join(project_root, 'data', 'training')
    os.makedirs(output_dir,   exist_ok=True)
    os.makedirs(training_dir, exist_ok=True)

    results = {}
    total_rows = 0

    print("=" * 60)
    print("Generating synthetic PD training data (Indian banks)")
    print("=" * 60)

    for idx, bank in enumerate(BANKS):
        df        = _generate_bank_data(bank, seed=seed_base + idx)
        filename  = FILE_NAMES[bank['bank_id']]
        out_path  = os.path.join(output_dir, filename)
        df.to_csv(out_path, index=False)

        if copy_to_training:
            train_path = os.path.join(training_dir, filename)
            df.to_csv(train_path, index=False)

        actual_dr = df['default_flag'].mean() * 100
        print(f"  {bank['bank_name']:35s} | {len(df):5,} rows | default rate {actual_dr:.1f}% -> {filename}")
        total_rows += len(df)
        results[bank['bank_id']] = out_path

    print("-" * 60)
    print(f"  Total: {len(BANKS)} banks | {total_rows:,} rows")
    print(f"  Synthetic files  : {output_dir}")
    if copy_to_training:
        print(f"  Training drop    : {training_dir}")
    print("=" * 60)

    return results


if __name__ == '__main__':
    generate_all()
