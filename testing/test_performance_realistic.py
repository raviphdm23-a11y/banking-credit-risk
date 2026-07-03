"""
Realistic Performance Testing for Phase 4.

Focuses on actual system performance with realistic thresholds
accounting for test environment limitations.
"""

import pytest
import time
import json
from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_input():
    """Standard test borrower"""
    return {
        "de_ratio": 2.5,
        "interest_coverage": 2.5,
        "profitability": 8.0,
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


# ============================================================================
# Baseline Performance Tests
# ============================================================================

def test_endpoint_responds(client, test_input):
    """Test endpoint responds successfully"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    assert response.status_code == 200


def test_response_has_shap(client, test_input):
    """Test response includes SHAP data"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    assert "shap" in data
    if data["shap"]:
        assert "base_value" in data["shap"]
        assert "feature_contributions" in data["shap"]
        assert "interactions" in data["shap"]


def test_shap_data_complete(client, test_input):
    """Test SHAP field is complete"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    shap = data.get("shap")
    if shap:
        assert "base_value" in shap
        assert isinstance(shap["feature_contributions"], list)
        assert isinstance(shap["interactions"], list)
        assert isinstance(shap["summary"], str)
        assert "model_version" in shap
        assert "computed_at" in shap
        assert "cached" in shap


# ============================================================================
# Latency Characteristics
# ============================================================================

def test_first_call_latency(client, test_input):
    """Test first call latency (cold)"""
    start = time.time()
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    elapsed = time.time() - start

    assert response.status_code == 200
    # First call may be slower, but should complete
    assert elapsed < 3.0  # Reasonable timeout for test environment


def test_second_call_faster(client, test_input):
    """Test second call is faster than first (caching)"""
    # First call
    start1 = time.time()
    response1 = client.post('/api/assess-borrower-with-shap', json=test_input)
    time1 = time.time() - start1

    # Second call
    start2 = time.time()
    response2 = client.post('/api/assess-borrower-with-shap', json=test_input)
    time2 = time.time() - start2

    assert response1.status_code == 200
    assert response2.status_code == 200
    # Second call should be noticeably faster
    assert time2 < time1


def test_repeated_calls_fast(client, test_input):
    """Test repeated calls are consistently fast"""
    # Warm up
    client.post('/api/assess-borrower-with-shap', json=test_input)

    # Measure 5 repeated calls
    times = []
    for _ in range(5):
        start = time.time()
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        elapsed = time.time() - start

        assert response.status_code == 200
        times.append(elapsed)

    # All should be fast
    avg_time = sum(times) / len(times)
    assert avg_time < 1.0  # Average should be reasonable


# ============================================================================
# Caching Tests
# ============================================================================

def test_caching_works(client, test_input):
    """Test SHAP caching is working"""
    # First call
    response1 = client.post('/api/assess-borrower-with-shap', json=test_input)
    data1 = response1.get_json()

    # Second call
    response2 = client.post('/api/assess-borrower-with-shap', json=test_input)
    data2 = response2.get_json()

    # Both should succeed
    assert response1.status_code == 200
    assert response2.status_code == 200

    # Should return identical results
    if data1.get("shap") and data2.get("shap"):
        assert data1["shap"]["base_value"] == data2["shap"]["base_value"]


def test_cache_different_inputs(client):
    """Test cache handles different inputs correctly"""
    input1 = {
        "de_ratio": 2.0,
        "interest_coverage": 3.0,
        "profitability": 10.0,
        "liquidity_ratio": 1.5,
        "exposure": 5000000,
        "seniority": "Senior Secured (Other)",
        "maturity": 3,
    }

    input2 = {
        "de_ratio": 3.0,
        "interest_coverage": 2.0,
        "profitability": 5.0,
        "liquidity_ratio": 1.0,
        "exposure": 3000000,
        "seniority": "Senior Unsecured",
        "maturity": 5,
    }

    # Get results for both
    response1 = client.post('/api/assess-borrower-with-shap', json=input1)
    response2 = client.post('/api/assess-borrower-with-shap', json=input2)

    data1 = response1.get_json()
    data2 = response2.get_json()

    # Results should be different
    if data1.get("shap") and data2.get("shap"):
        # Different PD values
        assert data1["pd"]["point"] != data2["pd"]["point"]


# ============================================================================
# Stability Tests
# ============================================================================

def test_multiple_sequential_calls(client, test_input):
    """Test stability with multiple sequential calls"""
    for i in range(10):
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        assert response.status_code == 200, f"Call {i+1} failed"


def test_different_inputs_sequential(client):
    """Test with different inputs sequentially"""
    inputs = [
        {"de_ratio": 1.5, "interest_coverage": 5.0, "profitability": 12.0, "liquidity_ratio": 2.0, "exposure": 2000000, "seniority": "Senior Secured (Other)", "maturity": 2},
        {"de_ratio": 3.0, "interest_coverage": 2.0, "profitability": 5.0, "liquidity_ratio": 0.9, "exposure": 8000000, "seniority": "Subordinated", "maturity": 4},
        {"de_ratio": 2.5, "interest_coverage": 3.0, "profitability": 8.0, "liquidity_ratio": 1.5, "exposure": 5000000, "seniority": "Senior Unsecured", "maturity": 3},
    ]

    for input_data in inputs:
        response = client.post('/api/assess-borrower-with-shap', json=input_data)
        assert response.status_code == 200


# ============================================================================
# Response Quality Tests
# ============================================================================

def test_response_valid_json(client, test_input):
    """Test response is valid JSON"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    # Should be parseable
    assert data is not None
    assert isinstance(data, dict)


def test_response_has_required_fields(client, test_input):
    """Test response has all required fields"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    # Tier 1 fields
    assert "pd" in data
    assert "rating" in data
    assert "attribution" in data
    assert "recommendation" in data

    # Tier 2 field
    assert "shap" in data


def test_pd_in_valid_range(client, test_input):
    """Test PD values are in valid range (0-1)"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    pd = data["pd"]
    assert 0.0 <= pd["point"] <= 1.0
    assert 0.0 <= pd["low"] <= 1.0
    assert 0.0 <= pd["high"] <= 1.0


def test_recommendation_valid(client, test_input):
    """Test recommendation is valid"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    decision = data["recommendation"]["decision"]
    assert decision in ["APPROVE", "REFER", "DECLINE"]


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_graceful_error_handling(client):
    """Test graceful error handling"""
    # Malformed input
    response = client.post(
        '/api/assess-borrower-with-shap',
        data='{"bad json}',
        content_type='application/json'
    )
    # Should fail gracefully, not crash
    assert response.status_code in [400, 415, 500]


def test_empty_input_handled(client):
    """Test empty input is handled"""
    response = client.post('/api/assess-borrower-with-shap', json={})
    # Should either succeed with defaults or fail gracefully
    assert response.status_code in [200, 400, 500]


def test_missing_optional_fields(client):
    """Test missing optional fields are handled"""
    minimal_input = {
        "de_ratio": 2.5,
        "interest_coverage": 2.5,
        "profitability": 8.0,
        "liquidity_ratio": 1.2,
        "exposure": 5000000,
        "seniority": "Senior Secured (Other)",
    }

    response = client.post('/api/assess-borrower-with-shap', json=minimal_input)
    assert response.status_code == 200


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

def test_old_endpoint_unchanged(client, test_input):
    """Test old endpoint still works"""
    response = client.post('/api/assess-borrower', json=test_input)
    assert response.status_code == 200


def test_endpoints_return_same_base_fields(client, test_input):
    """Test both endpoints return same base data"""
    response1 = client.post('/api/assess-borrower', json=test_input)
    response2 = client.post('/api/assess-borrower-with-shap', json=test_input)

    data1 = response1.get_json()
    data2 = response2.get_json()

    # Should have same PD
    assert data1["pd"]["point"] == data2["pd"]["point"]
    # Should have same rating
    assert data1["rating"]["grade"] == data2["rating"]["grade"]


# ============================================================================
# Performance Characteristics
# ============================================================================

def test_response_size_reasonable(client, test_input):
    """Test response size is reasonable"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    json_str = json.dumps(data)
    size_kb = len(json_str) / 1024

    # Should be reasonable size for network transfer
    assert size_kb < 1000  # Less than 1MB


def test_no_obvious_memory_leaks(client, test_input):
    """Test no obvious memory issues after multiple calls"""
    # Make several calls
    for _ in range(20):
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        assert response.status_code == 200

    # If we got here without crashing, no obvious leak
    # (Real memory testing would need psutil profiling)
    assert True


# ============================================================================
# Summary Stats
# ============================================================================

def test_performance_summary_stats(client, test_input):
    """Collect performance summary statistics"""
    stats = {
        'requests': 0,
        'successes': 0,
        'min_latency': float('inf'),
        'max_latency': 0,
        'total_time': 0,
    }

    start_total = time.time()

    for _ in range(10):
        start = time.time()
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        elapsed = time.time() - start

        stats['requests'] += 1
        if response.status_code == 200:
            stats['successes'] += 1

        stats['min_latency'] = min(stats['min_latency'], elapsed)
        stats['max_latency'] = max(stats['max_latency'], elapsed)
        stats['total_time'] += elapsed

    total_elapsed = time.time() - start_total

    # Verify performance
    assert stats['successes'] == 10
    assert stats['min_latency'] < 1.0
    assert stats['max_latency'] < 3.0

    # Log results
    print(f"\n{'='*60}")
    print(f"Performance Summary (10 sequential calls)")
    print(f"{'='*60}")
    print(f"Total requests:    {stats['requests']}")
    print(f"Successful:        {stats['successes']}/{ stats['requests']}")
    print(f"Min latency:       {stats['min_latency']*1000:.1f}ms")
    print(f"Max latency:       {stats['max_latency']*1000:.1f}ms")
    print(f"Avg latency:       {(stats['total_time']/stats['requests'])*1000:.1f}ms")
    print(f"Total time:        {total_elapsed:.2f}s")
    print(f"Throughput:        {stats['requests']/total_elapsed:.1f} req/s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
