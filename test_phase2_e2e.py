"""
Phase 2 End-to-End Testing
Complete workflow testing for ML integration
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api"

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

def print_subsection(title):
    print(f"\n{'-'*80}")
    print(f"  {title}")
    print(f"{'-'*80}")

def test_flask_health():
    """Test 1: Verify Flask is running"""
    print_section("TEST 1: FLASK SERVER HEALTH")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"[PASS] Flask is running")
            print(f"       Service: {data['service']}")
            print(f"       Version: {data['version']}")
            print(f"       Environment: {data['environment']}")
            return True
        else:
            print(f"[FAIL] Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Cannot connect to Flask: {e}")
        return False

def test_model_availability():
    """Test 2: Check if ML model is available"""
    print_section("TEST 2: ML MODEL AVAILABILITY")

    try:
        response = requests.get(f"{BASE_URL}/model-info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'available':
                print(f"[PASS] ML model is available")
                if 'metadata' in data:
                    meta = data['metadata']
                    print(f"       Model Type: {meta.get('model_type')}")
                    print(f"       Version: {meta.get('version')}")
                    print(f"       Data Type: {meta.get('data_type')}")
                return True
            else:
                print(f"[FAIL] Model status: {data.get('status')}")
                return False
        else:
            print(f"[FAIL] Cannot get model info: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Error checking model: {e}")
        return False

def test_rule_based_calculation():
    """Test 3: Rule-based PD calculation"""
    print_section("TEST 3: RULE-BASED PD CALCULATION")

    borrower_data = {
        "de_ratio": 1.5,
        "interest_coverage": 2.5,
        "profitability": 0.08,
        "liquidity_ratio": 1.2
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/calculate-pd",
            json=borrower_data,
            timeout=5
        )
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()
            pd_pct = data['pd_percentage']
            print(f"[PASS] Rule-based PD calculated")
            print(f"       PD: {pd_pct:.2f}%")
            print(f"       Response Time: {response_time:.1f}ms")

            if 'breakdown' in data:
                print(f"       Components:")
                for key, value in data['breakdown'].items():
                    print(f"         - {key}: {value}")

            return True, pd_pct
        else:
            print(f"[FAIL] Calculation failed: {response.status_code}")
            return False, None
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False, None

def test_ml_prediction():
    """Test 4: ML-based PD prediction"""
    print_section("TEST 4: MACHINE LEARNING PD PREDICTION")

    borrower_data = {
        "de_ratio": 1.5,
        "interest_coverage": 2.5,
        "profitability": 0.08,
        "liquidity_ratio": 1.2
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/predict-pd-ml",
            json=borrower_data,
            timeout=5
        )
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()
            pd_pct = data['pd_percentage']
            method = data.get('method', 'Unknown')

            print(f"[PASS] ML PD predicted successfully")
            print(f"       PD: {pd_pct:.2f}%")
            print(f"       Method: {method}")
            print(f"       Response Time: {response_time:.1f}ms")
            print(f"       Model Version: {data.get('model_version')}")

            return True, pd_pct
        else:
            print(f"[FAIL] Prediction failed: {response.status_code}")
            if response.text:
                print(f"       Error: {response.json().get('error')}")
            return False, None
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False, None

def test_comparison(rb_pd, ml_pd):
    """Test 5: Compare rule-based vs ML predictions"""
    print_section("TEST 5: RULE-BASED VS ML COMPARISON")

    if rb_pd is None or ml_pd is None:
        print("[SKIP] Missing data for comparison")
        return False

    difference = abs(ml_pd - rb_pd)
    percent_diff = (difference / rb_pd * 100) if rb_pd > 0 else 0

    print(f"[PASS] Comparison Results:")
    print(f"       Rule-Based PD:  {rb_pd:.2f}%")
    print(f"       ML-Based PD:    {ml_pd:.2f}%")
    print(f"       Difference:     {difference:.2f}% (absolute)")
    print(f"       Difference:     {percent_diff:.1f}% (relative)")

    if difference < 2.0:
        print(f"       Agreement:      EXCELLENT")
    elif difference < 5.0:
        print(f"       Agreement:      GOOD")
    elif difference < 10.0:
        print(f"       Agreement:      ACCEPTABLE (demo model)")
    else:
        print(f"       Agreement:      SIGNIFICANT DIFFERENCE (demo model expected)")

    return True

def test_multiple_scenarios():
    """Test 6: Test multiple borrower scenarios"""
    print_section("TEST 6: MULTIPLE BORROWER SCENARIOS")

    scenarios = [
        {
            "name": "Good Borrower",
            "data": {"de_ratio": 1.5, "interest_coverage": 2.5, "profitability": 0.08, "liquidity_ratio": 1.2}
        },
        {
            "name": "Medium Borrower",
            "data": {"de_ratio": 2.0, "interest_coverage": 1.8, "profitability": 0.05, "liquidity_ratio": 1.0}
        },
        {
            "name": "Risky Borrower",
            "data": {"de_ratio": 2.8, "interest_coverage": 0.9, "profitability": -0.05, "liquidity_ratio": 0.8}
        }
    ]

    results = []

    for scenario in scenarios:
        print_subsection(f"Testing: {scenario['name']}")

        # Rule-based
        try:
            r1 = requests.post(f"{BASE_URL}/calculate-pd", json=scenario['data'], timeout=5)
            rb_pd = r1.json()['pd_percentage'] if r1.status_code == 200 else None
        except:
            rb_pd = None

        # ML-based
        try:
            r2 = requests.post(f"{BASE_URL}/predict-pd-ml", json=scenario['data'], timeout=5)
            ml_pd = r2.json()['pd_percentage'] if r2.status_code == 200 else None
        except:
            ml_pd = None

        if rb_pd and ml_pd:
            diff = abs(ml_pd - rb_pd)
            print(f"Rule-Based: {rb_pd:.2f}% | ML-Based: {ml_pd:.2f}% | Diff: {diff:.2f}%")
            results.append((scenario['name'], rb_pd, ml_pd, diff))
        else:
            print(f"[FAIL] Could not get both predictions")

    return len(results) == len(scenarios), results

def test_html_ui():
    """Test 7: Verify HTML has ML UI"""
    print_section("TEST 7: HTML UI VERIFICATION")

    try:
        response = requests.get("http://127.0.0.1:5000/", timeout=5)
        if response.status_code == 200:
            html = response.text

            checks = {
                "PD Method Radio Buttons": "pdMethod" in html,
                "ML Option": "Machine Learning" in html,
                "Rule-Based Option": "Rule-Based" in html,
                "API Integration Script": "api-integration.js" in html,
            }

            all_passed = True
            for check, result in checks.items():
                status = "[PASS]" if result else "[FAIL]"
                print(f"{status} {check}")
                if not result:
                    all_passed = False

            return all_passed
        else:
            print(f"[FAIL] Cannot load HTML: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def generate_report(results):
    """Generate final test report"""
    print_section("PHASE 2 TEST REPORT")

    print("\nTest Summary:")
    print(f"  Tests Run: {len(results)}")

    passed = sum(1 for r in results.values() if r)
    failed = len(results) - passed

    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Success Rate: {passed/len(results)*100:.1f}%")

    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:8s} - {test_name}")

    if failed == 0:
        print("\n" + "="*80)
        print("  [SUCCESS] ALL TESTS PASSED! Phase 2 is ready for use.")
        print("="*80)
    else:
        print("\n" + "="*80)
        print(f"  [WARNING] {failed} test(s) failed. Review errors above.")
        print("="*80)

    return failed == 0

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  PHASE 2: MACHINE LEARNING INTEGRATION - END-TO-END TESTS")
    print("="*80)

    results = {}

    # Test 1: Flask Health
    results["Flask Server Health"] = test_flask_health()
    if not results["Flask Server Health"]:
        print("\n[ERROR] Flask server not running. Cannot continue.")
        return

    # Test 2: Model Availability
    results["ML Model Available"] = test_model_availability()

    # Test 3: Rule-based PD
    rb_ok, rb_pd = test_rule_based_calculation()
    results["Rule-Based PD Calculation"] = rb_ok

    # Test 4: ML PD
    ml_ok, ml_pd = test_ml_prediction()
    results["ML PD Prediction"] = ml_ok

    # Test 5: Comparison
    if rb_ok and ml_ok:
        results["Rule-Based vs ML Comparison"] = test_comparison(rb_pd, ml_pd)
    else:
        results["Rule-Based vs ML Comparison"] = False

    # Test 6: Multiple Scenarios
    multi_ok, multi_results = test_multiple_scenarios()
    results["Multiple Borrower Scenarios"] = multi_ok

    # Test 7: HTML UI
    results["HTML UI With ML Features"] = test_html_ui()

    # Generate Report
    success = generate_report(results)

    # Show Multi-Scenario Summary
    if multi_results:
        print_section("MULTI-SCENARIO SUMMARY")
        print(f"{'Scenario':<20} | {'Rule-Based':>12} | {'ML-Based':>12} | {'Difference':>12}")
        print("-"*80)
        for name, rb, ml, diff in multi_results:
            print(f"{name:<20} | {rb:11.2f}% | {ml:11.2f}% | {diff:11.2f}%")

    return success

if __name__ == "__main__":
    try:
        success = main()
        import sys
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
