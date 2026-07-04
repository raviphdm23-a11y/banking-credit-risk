"""
seed_real_bank.py
─────────────────
Seeds a new bank in bank.db based on a real-world bank profile JSON.

Real-world design:
  Not every deposit customer has a loan, and not every loan customer
  banks here.  Three segments are generated:

    (A) Full-relationship  — account + loan at this bank
    (B) Deposit-only       — savings/current/FD account, no loan here
    (C) Loan-only          — loan here, primary banking elsewhere (no account row)

  Cross-sell rate by exposure class controls A vs C split:
    RETAIL_MORTGAGES 90% | RETAIL_OTHER 70% | SME 50% | CORPORATE 20%

  Loan sizes are differentiated by class so the book looks realistic:
    Corporate >> SME > Mortgages > Retail

  NPA allocation is class-weighted to hit the profile's overall gnpa_rate.

Usage:
  python operations/scripts/seed_real_bank.py <profile.json> [options]

  Options:
    --target-assets CRORE   Total assets in crore (default: 60)
    --loan-customers N      Loan customer count (default: 150)
    --deposit-only N        Extra deposit-only customers (default: 50)
    --dry-run               Print plan only, no DB writes
    --yes                   Skip confirmation prompt

Example:
  python operations/scripts/seed_real_bank.py \\
    operations/scripts/bank_profiles/BANK007_bob.json
"""

import os, sys, json, sqlite3, random, subprocess, argparse
from datetime import date, datetime, timedelta
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# Import shared risk formula (same formula for all seeding)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ml_models.risk_formula import true_pd_nonlinear, simple_default_rate_model, sample_correlated_features, add_measurement_noise

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB   = os.path.join(REPO, 'bank.db')

# ── Cross-sell: % of loan customers who ALSO have a deposit account here ─────
CROSS_SELL = {
    'CORPORATE':        0.20,
    'SME':              0.50,
    'RETAIL_OTHER':     0.70,
    'RETAIL_MORTGAGES': 0.90,
}

# ── Relative loan-size factor per class (corporate loans >> retail) ───────────
LOAN_SIZE_FACTOR = {
    'CORPORATE':        4.0,
    'SME':              2.0,
    'RETAIL_MORTGAGES': 1.8,
    'RETAIL_OTHER':     0.8,
}

# ── NPA weight (relative probability) per class ───────────────────────────────
NPA_WEIGHT = {
    'CORPORATE':        3.5,
    'SME':              3.0,
    'RETAIL_OTHER':     1.5,
    'RETAIL_MORTGAGES': 0.5,
}

# ── Loan products by exposure class ──────────────────────────────────────────
LOAN_TYPES_BY_CLASS = {
    'CORPORATE':        [('Business Loan', 2)],
    'SME':              [('Business Loan', 2)],
    'RETAIL_OTHER':     [('Personal Loan', 1), ('Vehicle Loan', 3), ('Education Loan', 4)],
    'RETAIL_MORTGAGES': [('Home Loan', 5)],
}

# ── Employment type (encoded) pool per class ──────────────────────────────────
EMP_BY_CLASS = {
    'CORPORATE':        [5, 5, 5, 2],       # BUSINESS dominant
    'SME':              [5, 4, 4, 5],       # BUSINESS, SELF_EMPLOYED
    'RETAIL_OTHER':     [2, 1, 4, 2, 2],    # SALARIED, GOVT, SELF_EMPLOYED
    'RETAIL_MORTGAGES': [2, 1, 2, 2],       # SALARIED, GOVT
    None:               [2, 1, 4, 2],       # deposit-only: generic
}
EMP_LABELS = ['GOVT', 'SALARIED', 'RETIRED', 'SELF_EMPLOYED', 'BUSINESS', 'FREELANCE', 'STUDENT']
EDU_LABELS = ['PHD', 'PROFESSIONAL', 'POST_GRADUATE', 'GRADUATE', 'DIPLOMA', 'HIGH_SCHOOL']
RES_LABELS = ['OWNED', 'RENTED', 'FAMILY', 'EMPLOYER']

# ── Name / city pools by country code ────────────────────────────────────────
COUNTRY_POOLS = {
    'IND': {
        'first': [
            'Rahul', 'Priya', 'Amit', 'Sunita', 'Rajesh', 'Kavita', 'Vikram', 'Anita',
            'Suresh', 'Deepa', 'Nitin', 'Meena', 'Arjun', 'Pooja', 'Sanjay', 'Rekha',
            'Manish', 'Usha', 'Ravi', 'Geeta', 'Anil', 'Shweta', 'Sachin', 'Nisha',
            'Vivek', 'Smita', 'Dinesh', 'Lakshmi', 'Harish', 'Asha', 'Kiran', 'Radha',
            'Mahesh', 'Sarla', 'Arun', 'Seema', 'Pankaj', 'Rina', 'Rakesh', 'Gita',
            'Mohan', 'Lata', 'Vinod', 'Neha', 'Ashok', 'Suman', 'Girish', 'Varsha',
        ],
        'last': [
            'Sharma', 'Patel', 'Gupta', 'Singh', 'Joshi', 'Rao', 'Verma', 'Agarwal',
            'Mehta', 'Shah', 'Kumar', 'Chaudhary', 'Nair', 'Reddy', 'Pillai', 'Iyer',
            'Mishra', 'Tiwari', 'Pandey', 'Dubey', 'Yadav', 'Srivastava', 'Saxena',
            'Bose', 'Mukherjee', 'Chatterjee', 'Das', 'Patil', 'Desai', 'Modi',
            'Thakur', 'Chandra', 'Banerjee', 'Ghosh', 'Menon', 'Kapoor', 'Malhotra',
        ],
        'cities': [
            ('Mumbai', 'Maharashtra'), ('Delhi', 'Delhi'), ('Kolkata', 'West Bengal'),
            ('Chennai', 'Tamil Nadu'), ('Pune', 'Maharashtra'), ('Ahmedabad', 'Gujarat'),
            ('Hyderabad', 'Telangana'), ('Bengaluru', 'Karnataka'), ('Jaipur', 'Rajasthan'),
            ('Lucknow', 'Uttar Pradesh'), ('Vadodara', 'Gujarat'), ('Surat', 'Gujarat'),
            ('Nagpur', 'Maharashtra'), ('Coimbatore', 'Tamil Nadu'), ('Bhopal', 'MP'),
            ('Indore', 'MP'), ('Kochi', 'Kerala'), ('Chandigarh', 'Punjab'),
        ],
    },
}
TIER1_CITIES = {'Mumbai', 'Delhi', 'Kolkata', 'Bengaluru', 'Chennai', 'Hyderabad'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_profile(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def scale_targets(profile: dict, target_cr: float) -> dict:
    """Convert profile ratios to absolute rupee targets at target_cr crore."""
    t = target_cr * 1e7
    dep = t * profile['deposits_pct']
    return {
        'total_assets': t,
        'advances':     t * profile['advances_pct'],
        'deposits':     dep,
        'borrowings':   t * profile['borrowings_pct'],
        'capital':      t * profile['capital_pct'],
        'investments':  t * profile['investments_pct'],
        'cash_rbi':     t * profile['cash_rbi_pct'],
        'demand_dep':   dep * profile['deposit_demand_pct'],
        'savings_dep':  dep * profile['deposit_savings_pct'],
        'term_dep':     dep * profile['deposit_term_pct'],
    }

def _emi(principal, annual_rate, months):
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), 2)

def _loan_counts(exposure_mix: dict, n_loan: int) -> dict:
    """Assign loan counts per class summing exactly to n_loan."""
    counts = {cls: max(1, round(f * n_loan)) for cls, f in exposure_mix.items()}
    diff   = n_loan - sum(counts.values())
    biggest = max(counts, key=lambda c: counts[c])
    counts[biggest] += diff
    return counts

def _avg_loan_sizes(counts: dict, total_advances: float) -> dict:
    """Compute per-class average loan size using LOAN_SIZE_FACTOR."""
    total_units = sum(counts[cls] * LOAN_SIZE_FACTOR[cls] for cls in counts)
    base = total_advances / total_units
    return {cls: base * LOAN_SIZE_FACTOR[cls] for cls in counts}

def _npa_rates(counts: dict, gnpa_rate: float) -> dict:
    """Compute per-class NPA probability so the portfolio hits gnpa_rate overall.
    Expected NPAs are allocated across classes proportional to (count × NPA_WEIGHT),
    then converted back to a per-loan probability for each class.
    """
    total_loans    = sum(counts.values())
    expected_npa   = gnpa_rate * total_loans
    total_w        = sum(counts[cls] * NPA_WEIGHT.get(cls, 1.5) for cls in counts)
    result = {}
    for cls in counts:
        class_w            = counts[cls] * NPA_WEIGHT.get(cls, 1.5)
        class_expected_npa = expected_npa * (class_w / total_w)
        result[cls]        = min(class_expected_npa / counts[cls], 0.85)
    return result

def _spread_balances(aids: list, total: float) -> dict:
    """Distribute total rupees across accounts with natural variation."""
    if not aids:
        return {}
    base   = total / len(aids)
    raw    = [base * random.uniform(0.4, 2.0) for _ in aids]
    factor = total / sum(raw)
    return {aid: round(v * factor, 2) for aid, v in zip(aids, raw)}


# ── Main seed ─────────────────────────────────────────────────────────────────

def seed(profile: dict, scale: dict, n_loan: int, n_dep_only: int,
         dry_run: bool = False, yes: bool = False, db_path: str = DB):

    random.seed(42)

    classes    = list(profile['exposure_mix'].keys())
    counts     = _loan_counts(profile['exposure_mix'], n_loan)
    avg_sizes  = _avg_loan_sizes(counts, scale['advances'])
    npa_rates  = _npa_rates(counts, profile['gnpa_rate'])

    # Pre-determine which ordinal positions within each class get NPA (deterministic)
    npa_slots = {}
    for cls in classes:
        n_npa = max(0, round(counts[cls] * npa_rates[cls]))
        positions = random.sample(range(counts[cls]), min(n_npa, counts[cls]))
        npa_slots[cls] = set(positions)
    pools      = COUNTRY_POOLS.get(profile['country_code'], COUNTRY_POOLS['IND'])
    bank_id    = profile['bank_id']
    short      = profile['bank_code']        # e.g. BOB
    stem       = short[:4].upper()

    # ── Build segment list ────────────────────────────────────────────────────
    # Each entry: (segment, exposure_class)
    #   segment = 'full_rel' | 'loan_only' | 'dep_only'
    segments = []
    for cls in classes:
        n_rel = max(1, round(counts[cls] * CROSS_SELL.get(cls, 0.5)))
        n_lo  = counts[cls] - n_rel
        segments += [('full_rel',  cls)] * n_rel
        segments += [('loan_only', cls)] * n_lo
    segments += [('dep_only', None)] * n_dep_only
    random.shuffle(segments)

    n_accounts = sum(1 for s, _ in segments if s in ('full_rel', 'dep_only'))
    n_loans    = sum(1 for s, _ in segments if s in ('full_rel', 'loan_only'))

    # ── Dry-run summary ───────────────────────────────────────────────────────
    print(f"\n  Bank         : {profile['bank_name']}  ({bank_id})")
    print(f"  Target assets: Rs {scale['total_assets']/1e7:.2f} cr")
    print(f"  Advances     : Rs {scale['advances']/1e7:.2f} cr")
    print(f"  Deposits     : Rs {scale['deposits']/1e7:.2f} cr")
    print(f"  LDR          : {scale['advances']/scale['deposits']*100:.1f}%\n")

    n_full = sum(1 for s, _ in segments if s == 'full_rel')
    n_lo   = sum(1 for s, _ in segments if s == 'loan_only')
    n_do   = sum(1 for s, _ in segments if s == 'dep_only')
    print(f"  Customer segments:")
    print(f"    (A) Full-relationship (account + loan) : {n_full}")
    print(f"    (B) Deposit-only (account, no loan)    : {n_do}")
    print(f"    (C) Loan-only (loan, no account here)  : {n_lo}")
    print(f"    Total unique customers                 : {len(segments)}")
    print(f"    Total accounts                         : {n_accounts}")
    print(f"    Total loans                            : {n_loans}\n")

    print(f"  Loan book by exposure class:")
    for cls in classes:
        n  = counts[cls]
        sz = avg_sizes[cls]
        np_r = npa_rates[cls]
        cs = CROSS_SELL.get(cls, 0.5)
        n_rel = max(1, round(n * cs))
        print(f"    {cls:<25} {n:>3} loans  avg Rs {sz/1e5:>6.1f}L  "
              f"cross-sell {cs*100:.0f}%  NPA~{np_r*100:.1f}%  "
              f"({n_rel} full-rel / {n - n_rel} loan-only)")

    expected_npa = sum(round(counts[cls] * npa_rates[cls]) for cls in classes)
    print(f"\n  Expected NPAs: ~{expected_npa}  ({expected_npa/n_loans*100:.1f}% of loans)")

    if dry_run:
        print("\n  [DRY RUN — no changes written]")
        return

    if not yes:
        ans = input("\n  Proceed? (yes/no): ").strip().lower()
        if ans != 'yes':
            print("  Aborted.")
            return

    # ── Connect & insert ──────────────────────────────────────────────────────
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    today = date.today()
    now   = datetime.now().isoformat(timespec='seconds')

    # -- bank master (always upsert so re-seeding fixes the name) --
    conn.execute(
        "INSERT INTO banks (bank_id,bank_name,bank_code,country,headquarters_city,"
        "headquarters_state,year_established,status,country_code) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bank_id) DO UPDATE SET bank_name=excluded.bank_name, bank_code=excluded.bank_code, "
        "country=excluded.country, headquarters_city=excluded.headquarters_city, "
        "headquarters_state=excluded.headquarters_state, year_established=excluded.year_established",
        (bank_id, profile['bank_name'], short,
         profile.get('country', profile['country_code']),
         profile.get('hq_city', ''), profile.get('hq_state', ''),
         profile.get('year_established', 1900), 'Active', profile['country_code']))
    print(f"\n  [1] Upserted bank master: {bank_id} — {profile['bank_name']}")

    # -- branches (5) --
    branch_rows = []
    for i, (city, state) in enumerate(pools['cities'][:5], 1):
        bid  = f"BR-{short}-{i:03d}"
        ifsc = f"{stem}{i:08d}"
        conn.execute(
            "INSERT OR IGNORE INTO branches "
            "(branch_id,bank_id,branch_name,ifsc_code,city,state,pincode,address,contact_phone,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (bid, bank_id, f"{city} Branch", ifsc, city, state,
             str(random.randint(100000, 999999)), city, None, 'Active'))
        branch_rows.append((bid, ifsc))
    print(f"  [2] Branches created: {len(branch_rows)}")

    # -- macro row for training features --
    macro = conn.execute(
        "SELECT gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,unemployment_pct "
        "FROM country_macro WHERE country_code=? ORDER BY period DESC LIMIT 1",
        (profile['country_code'],)).fetchone()
    macro = tuple(macro) if macro else (7.0, 4.5, 6.5, 4.0)

    # -- collect account aids for deposit distribution --
    # Pre-assign account type so we can split pools before writing
    acc_plan = []   # (aid, acc_type, cid) — populated as we iterate
    loan_records = []  # full loan dict list
    cust_records = []
    kyc_records  = []
    acc_records  = []
    txn_records  = []
    crm_records  = []
    blm_records  = []

    cls_counter = {cls: 0 for cls in classes}
    dep_counter = 0

    for g_idx, (seg, cls) in enumerate(segments, 1):
        # -- IDs
        if cls:
            cls_counter[cls] += 1
            cls_abbr = cls[:4]
            cid = f"{short}-{cls_abbr}-{cls_counter[cls]:04d}"
            lid = f"{short}-LN-{cls_abbr}-{cls_counter[cls]:05d}"
        else:
            dep_counter += 1
            cid = f"{short}-DEP-{dep_counter:04d}"
            lid = None
        aid = f"ACC-{short}-{g_idx:05d}" if seg in ('full_rel', 'dep_only') else None

        branch, ifsc = random.choice(branch_rows)
        first  = random.choice(pools['first'])
        last   = random.choice(pools['last'])
        city, state = random.choice(pools['cities'])
        age    = random.randint(24, 62)
        gender = random.choice(['Male', 'Female'])
        dob    = date(today.year - age, random.randint(1, 12), random.randint(1, 28)).isoformat()
        joined = date(today.year - random.randint(0, 6), random.randint(1, 12), 1).isoformat()

        # -- employment & financial profile
        emp_enc   = random.choice(EMP_BY_CLASS.get(cls, EMP_BY_CLASS[None]))
        emp_label = EMP_LABELS[emp_enc - 1]
        edu_enc   = random.randint(1, 4) if cls in ('CORPORATE', 'SME') else random.randint(3, 6)
        res_enc   = random.randint(1, 3)
        tier      = 1 if city in TIER1_CITIES else random.choice([1, 2, 2])

        income_ranges = {
            'CORPORATE':        (5_000_000, 25_000_000),
            'SME':              (2_000_000, 10_000_000),
            'RETAIL_MORTGAGES': (1_200_000,  5_000_000),
            'RETAIL_OTHER':     (  400_000,  3_000_000),
            None:               (  300_000,  2_000_000),
        }
        lo, hi = income_ranges.get(cls, income_ranges[None])
        income = random.randint(lo, hi)

        years_emp    = round(random.uniform(1, min(age - 22, 30)), 1)
        months_cust  = random.randint(6, 240)
        ex_loans     = random.randint(0, 3)
        ex_products  = random.randint(1, 5)
        deps         = random.randint(0, 4)

        # -- Realistic credit quality: continuous features + probabilistic defaults
        rng = np.random.default_rng(seed=random.randint(1, 1000000))

        # Sample continuous features with realistic distributions (not bimodal buckets)
        de_true      = float(np.clip(rng.exponential(scale=1.0), 0.1, 6.0))
        ic_true      = float(np.clip(rng.gamma(shape=3.0, scale=2.0), 0.5, 15.0))
        profit_true  = float(np.clip(rng.normal(loc=10.0, scale=12.0), -50.0, 60.0))
        liq_true     = float(np.clip(rng.gamma(shape=4.0, scale=0.4), 0.3, 4.0))

        # CIBIL correlated with income and tenure
        cibil_base = 680 + (np.log(max(income, 100000)) - 12.5) * 30 + years_emp * 2
        cibil_true = int(np.clip(cibil_base + rng.normal(0, 20), 300, 900))

        foir_true = float(np.clip(rng.beta(2.2, 3.5), 0.05, 0.75))

        # Add measurement noise to observed values (banks don't see true values)
        noisy = add_measurement_noise(
            rng, de_true, ic_true, profit_true, liq_true,
            income, years_emp, foir_true
        )
        de      = round(noisy['de_ratio'], 2)
        ic      = round(noisy['int_coverage'], 2)
        profit  = round(noisy['profitability'], 1)
        liq     = round(noisy['liquidity_ratio'], 2)
        cibil   = int(noisy['cibil_score'] if noisy.get('cibil_score') else cibil_true)
        foir    = round(noisy['foir'], 2)

        # Payment history: late payments correlation with credit quality
        if cibil < 600:
            late = random.randint(2, 8)
            prev_def = 1 if random.random() < 0.6 else 0
        else:
            late = 0
            prev_def = 0

        # CHANGED: Use simple default model (income/age/macro only) NOT feature-derived
        # This breaks the feature→default determinism that caused AUC=1.0
        # Features are still realistic (continuous, correlated, noisy) but defaults are independent
        pd_score = simple_default_rate_model(income, age, macro_regime_score=1.0, rng=rng)

        # Sample default probabilistically (Bernoulli trial with PD as probability)
        df = int(rng.binomial(1, p=pd_score))
        pd_obs = round(pd_score, 4)

        # prior_de and prior_cibil: derive as trend, not independent random
        # Prior = current + small trend noise (customer improving or declining ~5%)
        prior_de    = round(np.clip(de * (1 + float(rng.normal(0, 0.05))), 0.1, 10.0), 4)
        prior_cibil = int(np.clip(cibil * (1 + float(rng.normal(0, 0.05))), 300, 900))

        ltype_pool   = LOAN_TYPES_BY_CLASS.get(cls or 'RETAIL_OTHER', [('Personal Loan', 1)])
        ltype, purp_enc = random.choice(ltype_pool)
        purp_str = {5: 'HOME_PURCHASE', 3: 'VEHICLE', 1: 'PERSONAL',
                    4: 'EDUCATION', 2: 'BUSINESS'}.get(purp_enc, 'PERSONAL')

        # ── customer ─────────────────────────────────────────────────────────
        cust_records.append((
            cid, bank_id, first, last, dob, gender,
            f"{first.lower()}.{last.lower().replace(' ','')}{g_idx}@example.com",
            f"+91{random.randint(7000000000, 9999999999)}",
            f"{random.randint(1,999)} {random.choice(['MG Road','Gandhi Nagar','Nehru Street','Station Road'])}",
            city, state, str(random.randint(100000, 999999)), joined, 'Active'))

        kyc_records.append((
            cid, bank_id, 1, 1, 'VERIFIED', '2022-01-05',
            age, gender, 'MARRIED', EDU_LABELS[edu_enc - 1], deps,
            emp_label, 'Employer Ltd',
            'Services' if cls not in ('RETAIL_MORTGAGES', None) else 'Real Estate',
            years_emp, income, 0, foir, RES_LABELS[res_enc - 1],
            round(random.uniform(1, 15), 1), f"TIER{tier}", 0,
            'HIGH' if df else 'LOW', now, now,
            months_cust, ex_products, ex_loans, purp_str, prev_def,
            cibil, late, state, 0))

        # ── account (A and B segments) ────────────────────────────────────────
        if aid:
            # Determine account type from exposure class / segment
            if cls == 'CORPORATE':
                acc_type = 'Current'
            elif cls == 'RETAIL_MORTGAGES' and random.random() < 0.15:
                acc_type = 'Fixed Deposit'
            elif seg == 'dep_only' and random.random() < 0.20:
                acc_type = 'Fixed Deposit'
            else:
                acc_type = 'Savings'
            open_date = date(today.year - random.randint(0, 5),
                             random.randint(1, 12), 1).isoformat()
            acc_records.append((aid, bank_id, cid, acc_type, 0.0,
                                open_date, branch, ifsc, 'Active'))
            txn_records.append((f"TX-{short}-{g_idx:05d}", bank_id, aid,
                                open_date, '10:00:00', 'Deposit', 0.0, 0.0,
                                '[INCOME] Opening deposit'))
            acc_plan.append((aid, acc_type))

        # ── loan (A and C segments) ───────────────────────────────────────────
        if lid:
            avg     = avg_sizes[cls]
            # Target avg_sizes is the OUTSTANDING target per loan.
            # Set outstanding directly, then back-compute principal.
            outst   = round(avg * random.uniform(0.60, 1.50), 2)
            outst   = max(150_000, outst)
            # Principal is always >= outstanding; loan is partially paid down
            paid_frac = random.uniform(0.05, 0.60)
            princ   = round(outst / (1 - paid_frac) / 100_000) * 100_000
            princ   = max(outst, princ)
            lo_r    = 7.5 if cls == 'RETAIL_MORTGAGES' else (8.0 if cls == 'CORPORATE' else 8.5)
            hi_r    = 11.0 if cls == 'CORPORATE' else (12.0 if cls == 'SME' else 18.0)
            rate    = round(random.uniform(lo_r, hi_r), 2)
            tenures = ([120, 180, 240, 300] if cls == 'RETAIL_MORTGAGES'
                       else [24, 36, 48, 60, 84])
            tenure  = random.choice(tenures)
            emi     = _emi(princ, rate, tenure)
            disb    = date(today.year - random.randint(1, 4),
                           random.randint(1, 12), random.randint(1, 28)).isoformat()
            mat_yr  = today.year + tenure // 12
            mat     = date(min(mat_yr, 2099), random.randint(1, 12), 28).isoformat()
            classif = 'NPA' if df else 'Standard'
            ltv     = round(random.uniform(0.55, 0.78), 2) if cls == 'RETAIL_MORTGAGES' else None
            ext_rat = (random.choice(['AA', 'A', 'A', 'BBB', 'BBB', 'BB'])
                       if cls == 'CORPORATE' else None)
            obs     = today.isoformat()
            months_orig = round((today - date.fromisoformat(disb)).days / 30.44, 1)

            loan_records.append((
                lid, bank_id, cid, ltype, princ, rate, tenure, emi, disb, mat,
                outst, 'Active', branch, classif, cls, ext_rat, ltv))

            crm_records.append((
                bank_id, lid, de, ic, profit, liq, df, pd_obs,
                df, '2025-Q1', obs, prior_de, prior_cibil))

            blm_records.append((
                bank_id, profile['bank_name'], lid,
                de, ic, profit, liq, df, pd_obs, obs, now,
                age, emp_enc, years_emp, income, foir, deps, tier,
                edu_enc, res_enc, purp_enc, cibil, prev_def,
                months_cust, late, ex_loans, ex_products, 0,
                profile['country_code'],
                macro[0], macro[1], macro[2], macro[3],
                round(de - prior_de, 4), round(float(cibil - prior_cibil), 1),
                months_orig, cls))

    # ── Distribute deposit balances across accounts ───────────────────────────
    # Split aids by account type to honour demand / savings / term ratios
    sav_aids = [a for a, t in acc_plan if t == 'Savings']
    cur_aids = [a for a, t in acc_plan if t == 'Current']
    fd_aids  = [a for a, t in acc_plan if t == 'Fixed Deposit']

    sav_tot = scale['savings_dep']
    dem_tot = scale['demand_dep']
    ter_tot = scale['term_dep']

    # Fold empty pools into savings
    if not cur_aids: sav_tot += dem_tot;  dem_tot = 0
    if not fd_aids:  sav_tot += ter_tot;  ter_tot = 0

    bal_map = {}
    bal_map.update(_spread_balances(sav_aids, sav_tot))
    bal_map.update(_spread_balances(cur_aids, dem_tot))
    bal_map.update(_spread_balances(fd_aids,  ter_tot))

    # Patch balances into acc_records and txn_records
    acc_by_aid = {r[0]: i for i, r in enumerate(acc_records)}
    txn_by_aid = {r[2]: i for i, r in enumerate(txn_records)}
    for aid, bal in bal_map.items():
        i = acc_by_aid[aid];  acc_records[i] = acc_records[i][:4] + (round(bal, 2),) + acc_records[i][5:]
        j = txn_by_aid[aid];  txn_records[j] = txn_records[j][:6] + (round(bal, 2), round(bal, 2)) + txn_records[j][8:]

    # ── Write to DB ───────────────────────────────────────────────────────────
    print(f"\n  [3] Writing {len(cust_records)} customers …", end='', flush=True)
    conn.executemany(
        "INSERT OR IGNORE INTO customers "
        "(id,bank_id,first,last,dob,gender,email,phone,address,city,state,pincode,joined,status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cust_records)
    print(f" done")

    print(f"  [4] Writing {len(kyc_records)} KYC records …", end='', flush=True)
    conn.executemany(
        "INSERT OR IGNORE INTO customer_kyc "
        "(cid,bank_id,pan_verified,aadhaar_verified,kyc_status,kyc_date,age,gender,marital_status,"
        "education_level,num_dependents,employment_type,employer_name,industry_sector,years_employed,"
        "annual_income,other_income,foir_declared,residence_type,years_at_address,city_tier,is_pep,"
        "risk_category,created_at,updated_at,months_as_customer,num_existing_products,existing_loans_count,"
        "loan_purpose,previous_default_flag,cibil_score,num_late_payments_past_12m,state,is_rural) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", kyc_records)
    print(f" done")

    print(f"  [5] Writing {len(acc_records)} accounts …", end='', flush=True)
    conn.executemany(
        "INSERT OR IGNORE INTO accounts "
        "(id,bank_id,cid,type,balance,open_date,branch_id,ifsc_code,status) "
        "VALUES (?,?,?,?,?,?,?,?,?)", acc_records)
    conn.executemany(
        "INSERT OR IGNORE INTO transactions "
        "(id,bank_id,aid,date,time,type,amount,balance_after,desc) "
        "VALUES (?,?,?,?,?,?,?,?,?)", txn_records)
    print(f" done")

    print(f"  [6] Writing {len(loan_records)} loans …", end='', flush=True)
    conn.executemany(
        "INSERT OR IGNORE INTO loans "
        "(id,bank_id,cid,type,principal,rate,tenure,emi,disbursed,maturity,outstanding,"
        "status,branch_id,loan_classification,exposure_class,external_rating,ltv_ratio) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", loan_records)
    print(f" done")

    print(f"  [7] Writing credit_risk_metrics + bank_loan_metrics …", end='', flush=True)
    conn.executemany(
        "INSERT OR IGNORE INTO credit_risk_metrics "
        "(bank_id,lid,de,intcov,profit,liq,df,pd_score,npa_flag,period,obs,prior_de,prior_cibil) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", crm_records)
    conn.executemany(
        "INSERT OR IGNORE INTO bank_loan_metrics "
        "(bank_id,bank_name,loan_id,de_ratio,interest_coverage,profitability,liquidity_ratio,"
        "default_flag,pd_observed,observation_date,loaded_at,age,employment_type_enc,years_employed,"
        "annual_income,foir,num_dependents,city_tier_enc,education_enc,residence_type_enc,loan_purpose_enc,"
        "cibil_score,previous_default_flag,months_as_customer,num_late_payments_past_12m,existing_loans_count,"
        "num_existing_products,is_rural,country_code,gdp_growth_pct,inflation_cpi_pct,policy_rate_pct,"
        "unemployment_pct,delta_de_ratio,delta_cibil,months_since_origination,exposure_class) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", blm_records)
    print(f" done")

    conn.commit()
    conn.close()

    # ── Verify ledger totals ──────────────────────────────────────────────────
    conn2 = sqlite3.connect(db_path)
    actual_adv = conn2.execute("SELECT COALESCE(SUM(outstanding),0) FROM loans WHERE bank_id=?",
                               (bank_id,)).fetchone()[0]
    actual_dep = conn2.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE bank_id=?",
                               (bank_id,)).fetchone()[0]
    actual_npa = conn2.execute(
        "SELECT COUNT(*) FROM loans WHERE bank_id=? AND loan_classification='NPA'",
        (bank_id,)).fetchone()[0]
    conn2.close()

    actual_ldr = actual_adv / actual_dep * 100 if actual_dep else 0
    print(f"\n  LEDGER CHECK")
    print(f"  Advances (SUM outstanding): Rs {actual_adv:>15,.0f}  (~Rs {actual_adv/1e7:.2f} cr)  "
          f"target Rs {scale['advances']/1e7:.2f} cr")
    print(f"  Deposits (SUM balance):     Rs {actual_dep:>15,.0f}  (~Rs {actual_dep/1e7:.2f} cr)  "
          f"target Rs {scale['deposits']/1e7:.2f} cr")
    print(f"  Loan-to-Deposit Ratio:      {actual_ldr:.1f}%  (real BoB: 82.2%)")
    print(f"  NPA loans:                  {actual_npa} / {len(loan_records)}  "
          f"({actual_npa/len(loan_records)*100:.1f}%)  target {profile['gnpa_rate']*100:.1f}%")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    print(f"\n  [8] Running balance sheet seeder + regulatory batch …")
    python = os.path.join(REPO, 'venv310', 'Scripts', 'python.exe')
    if not os.path.exists(python):
        python = sys.executable
    for script_name in ['seed_bank_balance_sheet.py', 'run_regulatory_batch.py']:
        s = os.path.join(REPO, 'operations', 'scripts', script_name)
        r = subprocess.run([python, s], capture_output=True, text=True, cwd=REPO)
        status = 'OK' if r.returncode == 0 else f'FAILED\n{r.stderr[-400:]}'
        print(f"      {script_name}: {status}")

    # ── Generate transaction history ─────────────────────────────────────────
    print(f"\n  [9] Generating 18-month transaction history …")
    conn3 = sqlite3.connect(db_path)
    n_txns = generate_transactions(conn3, bank_id, today)
    conn3.commit(); conn3.close()
    print(f"      {n_txns} transactions inserted (deposit-neutral)")

    print(f"\n  Done.  Run normalize_bank.py {bank_id} to verify ratios.")


# ── Transaction history ───────────────────────────────────────────────────────

HISTORY_MONTHS = 18
TXN_FLOOR      = 5_000.0   # minimum opening balance (₹)

def _income_desc(emp_type: str) -> tuple:
    e = (emp_type or '').upper()
    if 'RETIRED' in e:
        return ('Deposit', '[INCOME] Pension - Monthly pension credit')
    if 'BUSINESS' in e:
        return ('Deposit', '[INCOME] Business Income - Monthly business revenue deposit')
    if 'SELF_EMPLOYED' in e:
        return ('Deposit', '[INCOME] Professional Income - Monthly professional fees credit')
    if 'FREELANCE' in e:
        return ('Deposit', '[INCOME] Freelance Income - Monthly freelance payment')
    if 'STUDENT' in e:
        return ('Deposit', '[INCOME] Family Support - Monthly allowance received')
    return ('Deposit', '[INCOME] Salary - Monthly salary credit')

def _month_range(start: date, end: date):
    """Yield (year, month) pairs from start month to end month inclusive."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield (y, m)
        m += 1
        if m > 12:
            m, y = 1, y + 1

def _build_history(closing_bal: float, monthly_income: float, emi: float,
                   is_npa: bool, emp_type: str,
                   window_start: date, window_end: date) -> list:
    """
    Build an ordered list of (date, time, type, amount, is_credit, desc) rows
    whose net flow ends exactly at closing_bal.

    Segment A (emi > 0): salary + EMI debit + bill + UPI each month
    Segment B (emi == 0): salary + bill + UPI each month (no EMI)
    NPA customers: occasional missed income and missed EMIs
    """
    inc_type, inc_desc = _income_desc(emp_type)
    flows = []

    for (y, mo) in _month_range(window_start, window_end):
        # ── income ───────────────────────────────────────────────────────────
        income_missed = is_npa and random.random() < 0.25
        if not income_missed:
            var = random.uniform(0.55, 0.88) if is_npa else random.uniform(0.92, 1.05)
            inc = round(monthly_income * var, 2)
            flows.append((date(y, mo, 1), '09:00:00', inc_type, inc, True, inc_desc))
            income_ok = True
        else:
            income_ok = False

        # ── EMI (Segment A only, missed sometimes for NPA) ───────────────────
        if emi > 0:
            emi_missed = is_npa and random.random() < 0.40
            if not emi_missed:
                flows.append((date(y, mo, 5), '08:30:00',
                              'EMI Payment', round(emi, 2), False,
                              '[LOAN] EMI Payment - Monthly loan instalment'))

        # ── utility bill ─────────────────────────────────────────────────────
        bill = round(monthly_income * random.uniform(0.06, 0.11), 2)
        flows.append((date(y, mo, 12), '11:00:00',
                      'Bill Payment', bill, False,
                      '[UTILITIES] Bill Payment - Electricity, internet and water'))

        # ── UPI / discretionary spend ─────────────────────────────────────────
        if income_ok:
            # Segment B spends more via UPI (no EMI going out here)
            upi_rate = random.uniform(0.25, 0.40) if emi == 0 else random.uniform(0.10, 0.22)
            upi = max(500.0, round(monthly_income * upi_rate, 2))
        else:
            upi = round(monthly_income * random.uniform(0.02, 0.06), 2)
        flows.append((date(y, mo, 20), '19:30:00',
                      'UPI Payment', upi, False,
                      '[LIFESTYLE] UPI Payment - Groceries and daily expenses'))

    # ── compute opening balance ───────────────────────────────────────────────
    net   = sum(f[3] if f[4] else -f[3] for f in flows)
    opening = round(closing_bal - net, 2)

    if opening < TXN_FLOOR:
        # net surplus exceeds closing balance — add an adjustment debit
        adj     = round(net - closing_bal + TXN_FLOOR, 2)
        opening = TXN_FLOOR
        flows.append((window_end, '23:59:00', 'Debit', adj, False,
                      '[ADJUSTMENT] Net spend reconciliation'))

    rows = [(window_start, '08:00:00', 'Deposit', opening, True,
             '[INCOME] Opening balance - account funded')]
    rows.extend(flows)
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def generate_transactions(conn, bank_id: str, today: date) -> int:
    """
    Generate 18-month transaction history for all deposit accounts of bank_id.
    Segment A (has loan here): salary + EMI debit + bill + UPI
    Segment B (no loan here):  salary + bill + UPI only
    Deposit-neutral: accounts.balance stays unchanged.
    Idempotent: skips accounts that already have EMI Payment history.
    """
    random.seed(hash(bank_id) & 0xFFFFFFFF)

    # Already has history?
    existing = conn.execute(
        "SELECT COUNT(*) FROM transactions t JOIN accounts a ON a.id=t.aid "
        "WHERE a.bank_id=? AND t.type='EMI Payment'", (bank_id,)).fetchone()[0]
    if existing:
        print(f"      {bank_id} already has transaction history — skipped")
        return 0

    window_start = date(today.year - HISTORY_MONTHS // 12,
                        today.month, 1)
    # If HISTORY_MONTHS not evenly divisible by 12, adjust
    m = today.month - (HISTORY_MONTHS % 12)
    y = today.year - HISTORY_MONTHS // 12
    if m <= 0:
        m += 12; y -= 1
    window_start = date(y, m, 1)
    window_end   = date(today.year, today.month, 1)

    # LEFT JOIN loans so deposit-only customers (no loan) still appear
    rows = conn.execute("""
        SELECT a.id   AS aid,
               a.balance,
               COALESCE(k.annual_income,  600000)   AS income,
               COALESCE(k.employment_type,'SALARIED') AS emp_type,
               l.emi,
               l.loan_classification,
               l.disbursed
        FROM   accounts a
        JOIN   customer_kyc k  ON k.cid=a.cid AND k.bank_id=a.bank_id
        LEFT JOIN loans l      ON l.cid=a.cid AND l.bank_id=a.bank_id
        WHERE  a.bank_id=?
    """, (bank_id,)).fetchall()

    total_inserted = 0
    for aid, balance, income, emp_type, emi, loan_class, disbursed in rows:
        B              = float(balance or 0)
        monthly_income = round(float(income) / 12.0, 2)
        if monthly_income <= 0:
            continue

        emi_amt = float(emi or 0)
        is_npa  = (loan_class or 'Standard') in ('NPA', 'Doubtful', 'Loss')

        # Loan-start aware: don't generate EMIs before the loan was disbursed
        if disbursed and emi_amt > 0:
            disb_date = date.fromisoformat(disbursed)
            eff_start = max(window_start, date(disb_date.year, disb_date.month, 1))
        else:
            eff_start = window_start
            emi_amt   = 0.0   # deposit-only: no EMI regardless

        hist = _build_history(B, monthly_income, emi_amt, is_npa,
                              emp_type, eff_start, window_end)

        # Replace existing single opening-deposit row with full history
        conn.execute("DELETE FROM transactions WHERE aid=?", (aid,))

        running = 0.0
        to_insert = []
        for seq, (d, t, typ, amt, is_credit, desc) in enumerate(hist, 1):
            running += amt if is_credit else -amt
            running  = round(running, 2)
            tid      = f"TX-{aid}-{seq:04d}"
            to_insert.append((tid, bank_id, aid, d.isoformat(), t,
                               typ, round(amt, 2), running, desc))

        conn.executemany(
            "INSERT INTO transactions "
            "(id,bank_id,aid,date,time,type,amount,balance_after,desc) "
            "VALUES (?,?,?,?,?,?,?,?,?)", to_insert)

        # Deposit-neutral: lock accounts.balance to B (guard float drift)
        conn.execute("UPDATE accounts SET balance=? WHERE id=?", (round(B, 2), aid))
        total_inserted += len(to_insert)

    return total_inserted


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Seed a new bank from a real-world profile JSON')
    parser.add_argument('profile',          help='Path to bank profile JSON')
    parser.add_argument('--target-assets',  type=float, default=60.0,
                        help='Target total assets in crore (default: 60)')
    parser.add_argument('--loan-customers', type=int,   default=150,
                        help='Number of loan customers (default: 150)')
    parser.add_argument('--deposit-only',   type=int,   default=50,
                        help='Extra deposit-only customers (default: 50)')
    parser.add_argument('--dry-run',        action='store_true',
                        help='Print plan only, no DB writes')
    parser.add_argument('--yes',            action='store_true',
                        help='Skip confirmation prompt')
    args = parser.parse_args()

    profile = load_profile(args.profile)
    scale   = scale_targets(profile, args.target_assets)

    # Guard: check if bank already exists
    conn = sqlite3.connect(DB)
    existing = conn.execute("SELECT COUNT(*) FROM customers WHERE bank_id=?",
                            (profile['bank_id'],)).fetchone()[0]
    conn.close()
    if existing and not args.dry_run:
        print(f"\n  WARNING: {profile['bank_id']} already has {existing} customers.")
        if not args.yes:
            ans = input("  Delete existing and re-seed? (yes/no): ").strip().lower()
            if ans != 'yes':
                print("  Aborted.")
                return
        # Clean up existing data
        conn = sqlite3.connect(DB)
        bid = profile['bank_id']
        for tbl in ['bank_loan_metrics', 'credit_risk_metrics', 'loans',
                    'transactions', 'accounts', 'customer_kyc', 'customers']:
            conn.execute(f"DELETE FROM {tbl} WHERE bank_id=?", (bid,))
        conn.commit(); conn.close()
        print(f"  Cleared existing {profile['bank_id']} data.")

    seed(profile, scale,
         n_loan=args.loan_customers,
         n_dep_only=args.deposit_only,
         dry_run=args.dry_run,
         yes=args.yes)


if __name__ == '__main__':
    main()
