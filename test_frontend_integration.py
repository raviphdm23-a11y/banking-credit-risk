"""
Frontend Integration Test
Tests the complete flow from HTML form submission through Flask API calls
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api"

def print_test_header(test_num, name):
    print(f"\n{'='*70}")
    print(f"[TEST {test_num}] {name}")
    print(f"{'='*70}")

def print_result(status, message):
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol} {message}")

def test_api_integration():
    """Test complete frontend integration scenario"""

    print("\n" + "="*70)
    print("FRONTEND INTEGRATION TEST SUITE")
    print("Testing borrower-info.html <-> Flask API Communication")
    print("="*70)

    # Simulate a complete user workflow

    # Step 1: Load page (implicit - just check health)
    print_test_header(1, "API Health Check (Page Load)")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Flask API ready: {data['service']} v{data['version']}")
        else:
            print_result(False, f"Unexpected status: {response.status_code}")
            return
    except Exception as e:
        print_result(False, f"Health check failed: {e}")
        return

    # Step 2: User fills form and clicks Calculate
    print_test_header(2, "Calculate PD (Form Submission)")

    # Simulate financial metrics input
    financial_metrics = {
        "de_ratio": 1.5,           # D/E ratio
        "interest_coverage": 2.5,  # Interest coverage
        "profitability": 0.08,     # Profitability margin
        "liquidity_ratio": 1.2     # Liquidity ratio
    }

    try:
        response = requests.post(
            f"{BASE_URL}/calculate-pd",
            json=financial_metrics,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            pd_percentage = data['pd_percentage']
            print_result(True, f"PD calculated: {pd_percentage}%")

            # Store for next steps
            pd_decimal = data['pd']
        else:
            print_result(False, f"PD calculation failed: {response.status_code}")
            return
    except Exception as e:
        print_result(False, f"PD API call failed: {e}")
        return

    # Step 3: User selects AIRB mode and fills additional fields
    print_test_header(3, "Calculate LGD (AIRB Mode)")

    # AIRB specific inputs
    airb_inputs = {
        "seniority": "Senior Unsecured",
        "collateral_type": "Corporate Bonds",
        "collateral_value": 20000,
        "exposure": 500000  # From the form
    }

    try:
        response = requests.post(
            f"{BASE_URL}/calculate-lgd",
            json=airb_inputs,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            lgd_percentage = data['lgd_percentage']
            print_result(True, f"LGD calculated: {lgd_percentage}%")
        else:
            print_result(False, f"LGD calculation failed: {response.status_code}")
            return
    except Exception as e:
        print_result(False, f"LGD API call failed: {e}")
        return

    # Step 4: Calculate correlation (for AIRB)
    print_test_header(4, "Calculate Correlation (AIRB Formula)")

    try:
        response = requests.post(
            f"{BASE_URL}/calculate-correlation",
            json={"pd": pd_decimal},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            correlation = data['r']
            print_result(True, f"Correlation (R) calculated: {correlation:.6f}")
        else:
            print_result(False, f"Correlation calculation failed")
            return
    except Exception as e:
        print_result(False, f"Correlation API call failed: {e}")
        return

    # Step 5: User also selects Standardized Approach mode
    print_test_header(5, "Get Risk Weight (SA Mode)")

    sa_inputs = {
        "category": "Corporate",
        "rating": "A"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/get-risk-weight-sa",
            json=sa_inputs,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            risk_weight = data['risk_weight']
            print_result(True, f"SA Risk Weight: {risk_weight}%")
        else:
            print_result(False, f"Risk weight lookup failed")
            return
    except Exception as e:
        print_result(False, f"Risk weight API call failed: {e}")
        return

    # Step 6: Calculate adjusted exposure with collateral (SA)
    print_test_header(6, "Calculate Adjusted Exposure (Collateral)")

    collateral_inputs = {
        "exposure": 500000,
        "collateral_type": "Government Securities",
        "collateral_value": 100000
    }

    try:
        response = requests.post(
            f"{BASE_URL}/calculate-adjusted-exposure",
            json=collateral_inputs,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            adjusted = data['adjusted_exposure']
            original = data['original_exposure']
            effect = original - adjusted
            print_result(True, f"Original: ${original:,.0f} -> Adjusted: ${adjusted:,.0f} (Effect: ${effect:,.0f})")
        else:
            print_result(False, f"Adjusted exposure calculation failed")
            return
    except Exception as e:
        print_result(False, f"Adjusted exposure API call failed: {e}")
        return

    # Step 7: Calculate RWA and Capital for AIRB
    print_test_header(7, "Calculate RWA & Capital (AIRB)")

    rwa_inputs_airb = {
        "exposure": 500000,
        "risk_weight": 65.5  # Hypothetical AIRB risk weight
    }

    try:
        response = requests.post(
            f"{BASE_URL}/calculate-rwa-airb",
            json=rwa_inputs_airb,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            rwa = data['rwa']
            capital = data['capital_required']
            print_result(True, f"AIRB RWA: ${rwa:,.0f}, Capital: ${capital:,.0f}")
        else:
            print_result(False, f"RWA calculation failed")
            return
    except Exception as e:
        print_result(False, f"RWA API call failed: {e}")
        return

    # Step 8: Calculate RWA and Capital for SA
    print_test_header(8, "Calculate RWA & Capital (SA)")

    rwa_inputs_sa = {
        "exposure": 500000,
        "risk_weight": 50,
        "collateral_type": "Government Securities",
        "collateral_value": 100000
    }

    try:
        response = requests.post(
            f"{BASE_URL}/calculate-rwa-sa",
            json=rwa_inputs_sa,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            rwa = data['rwa']
            capital = data['capital_required']
            print_result(True, f"SA RWA: ${rwa:,.0f}, Capital: ${capital:,.0f}")
        else:
            print_result(False, f"RWA calculation failed")
            return
    except Exception as e:
        print_result(False, f"RWA API call failed: {e}")
        return

    # Step 9: User records two loans and views portfolio
    print_test_header(9, "Portfolio Summary (Mixed AIRB & SA)")

    portfolio_inputs = {
        "loans": [
            {
                "exposure": 500000,
                "rwa": 327500,      # 65.5% of 500k
                "capital_required": 26200,
                "calculation_method": "AIRB",
                "pd": 4.0
            },
            {
                "exposure": 300000,
                "rwa": 141750,      # Adjusted 50% of adjusted exposure
                "capital_required": 11340,
                "calculation_method": "SA",
                "risk_weight": 50
            }
        ]
    }

    try:
        response = requests.post(
            f"{BASE_URL}/portfolio-summary",
            json=portfolio_inputs,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            total_loans = data['total_loans']
            total_exposure = data['total_exposure']
            total_rwa = data['total_rwa']
            risk_density = data['average_risk_density']
            total_capital = data['total_capital_required']

            print_result(True, f"Portfolio Summary:")
            print(f"  - Loans: {total_loans}")
            print(f"  - Total Exposure: ${total_exposure:,.0f}")
            print(f"  - Total RWA: ${total_rwa:,.0f}")
            print(f"  - Risk Density: {risk_density:.2f}%")
            print(f"  - Total Capital: ${total_capital:,.0f}")
        else:
            print_result(False, f"Portfolio summary failed")
            return
    except Exception as e:
        print_result(False, f"Portfolio API call failed: {e}")
        return

    # Summary
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    print("[SUCCESS] All integration tests passed!")
    print("\nThe frontend can now successfully:")
    print("  [OK] Load the page and check API health")
    print("  [OK] Submit form and receive PD calculations")
    print("  [OK] Calculate LGD with collateral adjustment")
    print("  [OK] Get SA risk weights from lookup tables")
    print("  [OK] Calculate adjusted exposure with haircuts")
    print("  [OK] Calculate RWA and capital for both methods")
    print("  [OK] View mixed portfolio summaries")
    print("\nReady to test the full HTML application!")
    print("="*70)

if __name__ == "__main__":
    try:
        test_api_integration()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
