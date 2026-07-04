#!/usr/bin/env python
"""
Verification script for Tier 1 ML underwriting improvements.
Run this to confirm all three fixes are working correctly.

Usage:
    python verify_tier1_fixes.py
"""

import json
import sys
from backend.assessment_engine import AssessmentEngine
import joblib

def test_case_risky_borrower():
    """Test borrower with risky profile (D/E=2.5, IC=2.5, Profit=8%)"""
    return {
        "de_ratio": 2.5,
        "interest_coverage": 2.5,
        "profitability": 8,
        "liquidity_ratio": 1.2,
        "exposure": 5000000,
        "seniority": "Senior Secured (Other)",
        "maturity": 3.0,
        "collateral_type": "Real Estate",
        "collateral_value": 3000000,
        "age": 45,
        "employment_type_enc": 2,
        "years_employed": 8,
        "annual_income": 1500000,
        "foir": 0.45,
        "num_dependents": 3,
        "city_tier_enc": 2,
        "education_enc": 3,
        "residence_type_enc": 1,
        "loan_purpose_enc": 2,
        "cibil_score": 650,
        "previous_default_flag": 0,
        "months_as_customer": 12,
        "num_late_payments_past_12m": 1,
        "existing_loans_count": 2,
        "num_existing_products": 2,
        "is_rural": 0,
        "country_code": "IND",
    }

def verify_fix_1_feature_importance(findings):
    """Verify Fix 1: XGBoost feature importance in ranking"""
    print("\n" + "="*80)
    print("FIX 1: XGBoost Feature Importance Ranking")
    print("="*80)

    checks = {
        "xgb_importance in attribution": "xgb_importance" in findings['attribution'][0],
        "weighted_rank in attribution": "weighted_rank" in findings['attribution'][0],
        "rank_position in attribution": "rank_position" in findings['attribution'][0],
        "Top feature has rank_position=1": findings['attribution'][0]['rank_position'] == 1,
        "Features sorted by weighted_rank": (
            findings['attribution'][0]['weighted_rank'] >= findings['attribution'][1]['weighted_rank']
        ),
        "xgb_importance is 0-1 scale": (
            0 <= findings['attribution'][0]['xgb_importance'] <= 1
        ),
    }

    for check_name, result in checks.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")

    print(f"\nTop 3 drivers by model importance:")
    for i, attr in enumerate(findings['attribution'][:3], 1):
        print(f"  {i}. {attr['display_name']}")
        print(f"     - Importance: {attr['xgb_importance']*100:.1f}%")
        print(f"     - Contribution: {attr['contribution']:+.6f}")
        print(f"     - Rank Score: {attr['weighted_rank']:.6f}")

    all_pass = all(checks.values())
    print(f"\n{'>>> FIX 1: PASS' if all_pass else '>>> FIX 1: FAIL'}")
    return all_pass

def verify_fix_2_uncertainty_knockouts(findings):
    """Verify Fix 2: Uncertainty-aware policy knockouts"""
    print("\n" + "="*80)
    print("FIX 2: Uncertainty-Aware Policy Knockouts")
    print("="*80)

    pd_data = findings['pd']
    checks = {
        "PD has point estimate": "point" in pd_data,
        "PD has low bound": "low" in pd_data,
        "PD has high bound": "high" in pd_data,
        "low <= point <= high": pd_data['low'] <= pd_data['point'] <= pd_data['high'],
        "Knockouts structure is list": isinstance(findings['policy_knockouts'], list),
    }

    # If knockouts exist, check they mention band
    if findings['policy_knockouts']:
        detail = findings['policy_knockouts'][0]['detail']
        checks["Knockout detail mentions band"] = "band:" in detail
    else:
        checks["Knockout detail mentions band"] = True  # Pass if no knockouts

    for check_name, result in checks.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")

    print(f"\nPD Information:")
    print(f"  Point Estimate: {pd_data['point']*100:.2f}%")
    print(f"  Lower Bound:    {pd_data['low']*100:.2f}%")
    print(f"  Upper Bound:    {pd_data['high']*100:.2f}%")
    print(f"  Band Width:     {(pd_data['high'] - pd_data['low'])*100:.2f}pp")

    if findings['policy_knockouts']:
        print(f"\nKnockouts (using pd_low for decisions):")
        for ko in findings['policy_knockouts']:
            print(f"  {ko['rule']} ({ko['severity']})")
            print(f"  {ko['detail']}")
    else:
        print(f"\nNo knockouts triggered")

    all_pass = all(checks.values())
    print(f"\n{'>>> FIX 2: PASS' if all_pass else '>>> FIX 2: FAIL'}")
    return all_pass

def verify_fix_3_learned_thresholds(findings):
    """Verify Fix 3: Model-learned Five C's thresholds"""
    print("\n" + "="*80)
    print("FIX 3: Model-Learned Five C's Thresholds")
    print("="*80)

    capacity = findings['five_cs']['capacity']

    checks = {
        "Capacity items exist": len(capacity['items']) > 0,
        "All benchmarks mention model-learned": all(
            "model-learned" in item['benchmark'] for item in capacity['items']
        ),
        "Interest Coverage has benchmark": "Interest Coverage" in [
            item['label'] for item in capacity['items']
        ],
        "Debt-to-Equity has benchmark": "Debt-to-Equity" in [
            item['label'] for item in capacity['items']
        ],
    }

    for check_name, result in checks.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")

    print(f"\nFive C's - Capacity Items (with learned thresholds):")
    for item in capacity['items']:
        print(f"  {item['label']}: {item['value']}")
        print(f"    Benchmark: {item['benchmark']}")
        print(f"    Assessment: {item['assessment']}")

    capital = findings['five_cs']['capital']
    print(f"\nFive C's - Capital Items (with learned thresholds):")
    for item in capital['items']:
        print(f"  {item['label']}: {item['value']}")
        print(f"    Benchmark: {item['benchmark']}")

    all_pass = all(checks.values())
    print(f"\n{'>>> FIX 3: PASS' if all_pass else '>>> FIX 3: FAIL'}")
    return all_pass

def main():
    """Run all verification checks"""
    print("\n" + "="*80)
    print("TIER 1 VERIFICATION SCRIPT")
    print("Testing ML-Driven Underwriting Improvements")
    print("="*80)

    try:
        # Load model and engine
        print("\nLoading model...")
        model = joblib.load('ml_models/pd_model.pkl')
        engine = AssessmentEngine(model, "run_20260702_045113", db_path="bank.db")
        print("  Model loaded successfully")

        # Generate assessment
        print("\nGenerating test assessment...")
        test_input = test_case_risky_borrower()
        findings = engine.assess(test_input)
        print("  Assessment completed")

        # Run verification checks
        fix1_pass = verify_fix_1_feature_importance(findings)
        fix2_pass = verify_fix_2_uncertainty_knockouts(findings)
        fix3_pass = verify_fix_3_learned_thresholds(findings)

        # Summary
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)

        results = {
            "Fix 1 (Feature Importance)": "PASS" if fix1_pass else "FAIL",
            "Fix 2 (Uncertainty Knockouts)": "PASS" if fix2_pass else "FAIL",
            "Fix 3 (Learned Thresholds)": "PASS" if fix3_pass else "FAIL",
        }

        for fix_name, status in results.items():
            symbol = "[OK]" if status == "PASS" else "[ERROR]"
            print(f"  {symbol} {fix_name}: {status}")

        overall_pass = all(v == "PASS" for v in results.values())

        if overall_pass:
            print(f"\n>>> TIER 1 VERIFICATION: ALL CHECKS PASSED")
            print(f">>> ML-driven underwriting improvements are working correctly")
            return 0
        else:
            print(f"\n>>> TIER 1 VERIFICATION: SOME CHECKS FAILED")
            print(f">>> Review errors above and check implementation")
            return 1

    except Exception as e:
        print(f"\n[ERROR] Verification failed with exception:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
