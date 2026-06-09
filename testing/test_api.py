"""
Flask API Test Suite
Tests all endpoints to verify they work correctly
"""

import requests
import json
import time
import sys

BASE_URL = "http://127.0.0.1:5000/api"
TESTS_PASSED = 0
TESTS_FAILED = 0

def print_header(title):
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}")

def print_test(test_num, name):
    print(f"\n[TEST {test_num}] {name}")
    print("-" * 70)

def print_success(message):
    print(f"[PASS] {message}")

def print_error(message):
    print(f"[FAIL] {message}")

def test_endpoint(test_num, name, endpoint, method, data=None):
    global TESTS_PASSED, TESTS_FAILED

    print_test(test_num, name)

    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
        else:
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print_success(f"Status {response.status_code}")
            return result
        else:
            print_error(f"Status {response.status_code}: {response.text}")
            TESTS_FAILED += 1
            return None

    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to Flask server (http://127.0.0.1:5000)")
        TESTS_FAILED += 1
        return None
    except Exception as e:
        print_error(f"Error: {str(e)}")
        TESTS_FAILED += 1
        return None

def main():
    global TESTS_PASSED, TESTS_FAILED

    print_header("FLASK API TEST SUITE")
    print("Banking Credit Risk Calculator")

    # Wait for server
    print("\nWaiting for Flask server to be ready...")
    for i in range(30):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print("[OK] Flask server is ready!")
                break
        except:
            time.sleep(1)

    # TEST 1: Health Check
    result = test_endpoint(1, "Health Check", "/health", "GET")
    if result and 'status' in result:
        print_success(f"Service: {result.get('service')}")
        print_success(f"Version: {result.get('version')}")
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 2: Calculate PD
    result = test_endpoint(2, "Calculate Probability of Default (PD)", "/calculate-pd", "POST", {
        "de_ratio": 1.5,
        "interest_coverage": 2.5,
        "profitability": 0.08,
        "liquidity_ratio": 1.2
    })
    if result and 'pd' in result:
        print_success(f"PD (Decimal): {result['pd']}")
        print_success(f"PD (Percentage): {result['pd_percentage']}%")
        assert 0.02 < result['pd'] < 0.08, "PD out of expected range"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 3: Calculate LGD
    result = test_endpoint(3, "Calculate Loss Given Default (LGD)", "/calculate-lgd", "POST", {
        "seniority": "Senior Unsecured",
        "collateral_type": "Corporate Bonds",
        "collateral_value": 20000,
        "exposure": 100000
    })
    if result and 'lgd' in result:
        print_success(f"LGD (Decimal): {result['lgd']}")
        print_success(f"LGD (Percentage): {result['lgd_percentage']}%")
        print_success(f"Seniority: {result['seniority']}")
        assert 0.25 < result['lgd'] < 0.50, "LGD out of expected range"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 4: Calculate Correlation
    result = test_endpoint(4, "Calculate Correlation Coefficient (R)", "/calculate-correlation", "POST", {
        "pd": 0.035
    })
    if result and 'r' in result:
        print_success(f"Correlation (R): {result['r']}")
        assert 0 < result['r'] < 1, "Correlation out of expected range"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 5: Calculate Maturity Adjustment
    result = test_endpoint(5, "Calculate Maturity Adjustment", "/calculate-maturity-adjustment", "POST", {
        "maturity": 3,
        "lgd": 0.45,
        "pd": 0.035
    })
    if result and 'maturity_adjustment' in result:
        print_success(f"Maturity Adjustment: {result['maturity_adjustment']}")
        print_success(f"B Coefficient: {result['b_coefficient']}")
        assert result['maturity_adjustment'] > 0, "Maturity adjustment invalid"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 6: Get SA Risk Weight
    result = test_endpoint(6, "Get Standardized Approach Risk Weight", "/get-risk-weight-sa", "POST", {
        "category": "Corporate",
        "rating": "A"
    })
    if result and 'risk_weight' in result:
        print_success(f"Risk Weight: {result['risk_weight']}%")
        print_success(f"Category: {result['category']}")
        print_success(f"Rating: {result['rating']}")
        assert result['risk_weight'] == 50, "Risk weight should be 50% for Corporate A"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 7: Calculate Adjusted Exposure
    result = test_endpoint(7, "Calculate Adjusted Exposure (with Collateral)", "/calculate-adjusted-exposure", "POST", {
        "exposure": 100000,
        "collateral_type": "Government Securities",
        "collateral_value": 30000
    })
    if result and 'adjusted_exposure' in result:
        print_success(f"Original Exposure: ${result['original_exposure']:.2f}")
        print_success(f"Collateral Type: {result['collateral_type']}")
        print_success(f"Haircut: {result['haircut']}%")
        print_success(f"Adjusted Exposure: ${result['adjusted_exposure']:.2f}")
        # 30000 * (1 - 0.05) = 28500
        assert result['adjusted_exposure'] < result['original_exposure'], "Adjusted exposure should be less"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 8: Calculate RWA (AIRB)
    result = test_endpoint(8, "Calculate RWA & Capital (AIRB)", "/calculate-rwa-airb", "POST", {
        "exposure": 100000,
        "risk_weight": 65.5
    })
    if result and 'rwa' in result:
        print_success(f"Exposure: ${result['exposure']:.2f}")
        print_success(f"Risk Weight: {result['risk_weight']}%")
        print_success(f"RWA: ${result['rwa']:.2f}")
        print_success(f"Capital Required (8%): ${result['capital_required']:.2f}")
        assert result['rwa'] == 65500, "RWA calculation incorrect"
        assert result['capital_required'] == 5240, "Capital calculation incorrect"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 9: Calculate RWA (SA)
    result = test_endpoint(9, "Calculate RWA & Capital (SA)", "/calculate-rwa-sa", "POST", {
        "exposure": 100000,
        "risk_weight": 50,
        "collateral_type": "Government Securities",
        "collateral_value": 30000
    })
    if result and 'rwa' in result:
        print_success(f"Adjusted Exposure: ${result['adjusted_exposure']:.2f}")
        print_success(f"Risk Weight: {result['risk_weight']}%")
        print_success(f"RWA: ${result['rwa']:.2f}")
        print_success(f"Capital Required (8%): ${result['capital_required']:.2f}")
        assert result['rwa'] < 50000, "RWA should be reduced by collateral"
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # TEST 10: Portfolio Summary
    result = test_endpoint(10, "Portfolio Summary (Mixed AIRB & SA)", "/portfolio-summary", "POST", {
        "loans": [
            {
                "exposure": 100000,
                "rwa": 65000,
                "capital_required": 5200,
                "calculation_method": "AIRB",
                "pd": 0.035
            },
            {
                "exposure": 50000,
                "rwa": 25000,
                "capital_required": 2000,
                "calculation_method": "SA",
                "risk_weight": 50
            }
        ]
    })
    if result and 'total_loans' in result:
        print_success(f"Total Loans: {result['total_loans']}")
        print_success(f"Total Exposure: ${result['total_exposure']:.2f}")
        print_success(f"Total RWA: ${result['total_rwa']:.2f}")
        print_success(f"Risk Density: {result['average_risk_density']:.2f}%")
        print_success(f"Total Capital Required: ${result['total_capital_required']:.2f}")
        print_success(f"Loans: AIRB={result['loans_by_method']['AIRB']}, SA={result['loans_by_method']['SA']}")
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1

    # Summary
    print_header("TEST SUMMARY")
    total_tests = TESTS_PASSED + TESTS_FAILED
    print(f"Total Tests: {total_tests}")
    print(f"[PASS] Passed: {TESTS_PASSED}")
    print(f"[FAIL] Failed: {TESTS_FAILED}")

    if TESTS_FAILED == 0:
        print(f"\nALL TESTS PASSED!")
        return 0
    else:
        print(f"\n{TESTS_FAILED} TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
