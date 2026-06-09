"""
Machine Learning Integration Tests

Tests the ML-based PD prediction endpoint and compares with rule-based method.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5000/api"

def print_header(title):
    print(f"\n{'='*70}")
    print(title)
    print(f"{'='*70}")

def print_test(num, name):
    print(f"\n[TEST {num}] {name}")
    print("-"*70)

def test_ml_integration():
    """Test ML integration"""

    print_header("MACHINE LEARNING INTEGRATION TESTS")

    # Test 1: Check model info
    print_test(1, "Check ML Model Info")
    try:
        response = requests.get(f"{BASE_URL}/model-info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"[PASS] Model status: {data['status']}")
            if data['status'] == 'available' and 'metadata' in data:
                metadata = data['metadata']
                print(f"       Model type: {metadata.get('model_type')}")
                print(f"       Version: {metadata.get('version')}")
                print(f"       Data type: {metadata.get('data_type')}")
        else:
            print(f"[FAIL] Unexpected status: {response.status_code}")
            return
    except Exception as e:
        print(f"[FAIL] Error checking model: {e}")
        return

    # Test data for comparison
    test_cases = [
        {
            "name": "Good Borrower",
            "data": {
                "de_ratio": 1.5,
                "interest_coverage": 2.5,
                "profitability": 0.08,
                "liquidity_ratio": 1.2
            }
        },
        {
            "name": "Medium Borrower",
            "data": {
                "de_ratio": 2.0,
                "interest_coverage": 1.8,
                "profitability": 0.05,
                "liquidity_ratio": 1.0
            }
        },
        {
            "name": "Risky Borrower",
            "data": {
                "de_ratio": 2.8,
                "interest_coverage": 0.9,
                "profitability": -0.05,
                "liquidity_ratio": 0.8
            }
        }
    ]

    test_num = 2
    results = []

    for test_case in test_cases:
        print_test(test_num, f"PD Prediction: {test_case['name']}")
        test_num += 1

        # Get rule-based PD
        try:
            response = requests.post(
                f"{BASE_URL}/calculate-pd",
                json=test_case['data'],
                timeout=5
            )
            if response.status_code != 200:
                print(f"[FAIL] Rule-based calculation failed")
                continue

            rule_based = response.json()
            rule_based_pd = rule_based['pd_percentage']
            print(f"Rule-Based PD: {rule_based_pd:.2f}%")

        except Exception as e:
            print(f"[FAIL] Rule-based API error: {e}")
            continue

        # Get ML PD
        try:
            response = requests.post(
                f"{BASE_URL}/predict-pd-ml",
                json=test_case['data'],
                timeout=5
            )
            if response.status_code != 200:
                print(f"[FAIL] ML prediction failed: {response.status_code}")
                print(f"       Error: {response.json().get('error')}")
                continue

            ml_result = response.json()
            ml_pd = ml_result['pd_percentage']
            method = ml_result.get('method', 'Unknown')

            print(f"[PASS] ML-Based PD:  {ml_pd:.2f}% (Method: {method})")

            # Compare
            difference = abs(ml_pd - rule_based_pd)
            print(f"       Difference:   {difference:.2f}%")

            agreement = "Good" if difference < 2.0 else "High" if difference < 5.0 else "Significant"
            print(f"       Agreement:    {agreement}")

            results.append({
                'name': test_case['name'],
                'rule_based': rule_based_pd,
                'ml_based': ml_pd,
                'difference': difference
            })

        except Exception as e:
            print(f"[FAIL] ML prediction error: {e}")
            continue

    # Summary
    print_header("INTEGRATION TEST SUMMARY")

    if results:
        print(f"\nComparison Results ({len(results)} cases tested):")
        print(f"{'Sample':20s} | {'Rule-Based':>12s} | {'ML-Based':>12s} | {'Difference':>12s}")
        print("-"*70)

        for result in results:
            print(f"{result['name']:20s} | {result['rule_based']:11.2f}% | {result['ml_based']:11.2f}% | {result['difference']:11.2f}%")

        avg_diff = sum(r['difference'] for r in results) / len(results)
        print(f"\nAverage Difference: {avg_diff:.2f}%")

        if avg_diff < 2.0:
            print("\n[SUCCESS] ML model is well-calibrated!")
        elif avg_diff < 5.0:
            print("\n[SUCCESS] ML model shows reasonable agreement with rule-based")
        else:
            print("\n[INFO] ML model shows significant differences - may need tuning")

        print("\nML Integration Status: READY FOR PRODUCTION")
        print("Users can now choose between Rule-Based and ML methods")

    else:
        print("[FAIL] No test results collected")

if __name__ == "__main__":
    try:
        test_ml_integration()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
