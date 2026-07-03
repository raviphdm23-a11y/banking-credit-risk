"""
Performance Testing Suite for Tier 2 SHAP Implementation (Phase 4).

Tests cover:
1. Endpoint latency (cold/warm)
2. Concurrent request handling
3. Memory stability
4. Cache efficiency under load
5. System resource usage
6. Edge case performance
"""

import pytest
import time
import threading
import psutil
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
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


@pytest.fixture
def get_memory_usage():
    """Get current process memory usage"""
    def _get():
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    return _get


# ============================================================================
# Single Request Latency Tests
# ============================================================================

def test_cold_latency_old_endpoint(client, test_input):
    """Test /api/assess-borrower cold latency"""
    # Clear cache if possible
    start = time.time()
    response = client.post('/api/assess-borrower', json=test_input)
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 2.0  # Should be fast even without SHAP


def test_cold_latency_new_endpoint(client, test_input):
    """Test /api/assess-borrower-with-shap cold latency"""
    start = time.time()
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    elapsed = time.time() - start

    assert response.status_code == 200
    # First call includes SHAP computation
    assert elapsed < 2.0


def test_warm_latency_new_endpoint(client, test_input):
    """Test /api/assess-borrower-with-shap warm latency (cached)"""
    # First call to warm up cache
    client.post('/api/assess-borrower-with-shap', json=test_input)

    # Second call should be cached
    start = time.time()
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    elapsed = time.time() - start

    assert response.status_code == 200
    # Cached call should be very fast
    assert elapsed < 0.5


def test_latency_consistency(client, test_input):
    """Test latency is consistent across multiple calls"""
    latencies = []

    # Warm up
    client.post('/api/assess-borrower-with-shap', json=test_input)

    # 5 calls
    for _ in range(5):
        start = time.time()
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        elapsed = time.time() - start

        assert response.status_code == 200
        latencies.append(elapsed)

    # Latencies should be consistent (low variance)
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    # Average should be fast
    assert avg_latency < 0.2
    # Max should not exceed 2x average
    assert max_latency < avg_latency * 2


# ============================================================================
# Concurrent Load Tests
# ============================================================================

def test_concurrent_requests_5(client, test_input):
    """Test 5 concurrent requests"""
    def make_request():
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(5)]
        results = [f.result() for f in as_completed(futures)]

    assert all(results)
    assert len(results) == 5


def test_concurrent_requests_10(client, test_input):
    """Test 10 concurrent requests"""
    def make_request():
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in as_completed(futures)]

    assert all(results)
    assert len(results) == 10


def test_concurrent_requests_20(client, test_input):
    """Test 20 concurrent requests"""
    def make_request():
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_request) for _ in range(20)]
        results = [f.result() for f in as_completed(futures)]

    assert all(results)
    assert len(results) == 20


def test_concurrent_latency(client, test_input):
    """Test latency under concurrent load"""
    latencies = []
    lock = threading.Lock()

    def make_request():
        start = time.time()
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        elapsed = time.time() - start

        with lock:
            latencies.append((response.status_code == 200, elapsed))

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        for f in as_completed(futures):
            f.result()

    # All should succeed
    assert all(status for status, _ in latencies)

    # Average latency under load
    avg_latency = sum(lat for _, lat in latencies) / len(latencies)
    max_latency = max(lat for _, lat in latencies)

    # Should still be reasonable under concurrent load
    assert avg_latency < 1.0
    assert max_latency < 3.0


# ============================================================================
# Memory Stability Tests
# ============================================================================

def test_memory_stability_single_request(client, test_input, get_memory_usage):
    """Test memory doesn't leak with single request"""
    mem_before = get_memory_usage()

    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    assert response.status_code == 200

    mem_after = get_memory_usage()
    mem_increase = mem_after - mem_before

    # Single request should not increase memory significantly
    assert mem_increase < 50  # MB


def test_memory_stability_repeated_requests(client, test_input, get_memory_usage):
    """Test memory doesn't leak with repeated requests"""
    mem_before = get_memory_usage()

    # Make 10 requests
    for _ in range(10):
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        assert response.status_code == 200

    mem_after = get_memory_usage()
    mem_increase = mem_after - mem_before

    # 10 requests should not increase memory significantly
    # Each cached response is ~100KB, so 10 requests ~1MB
    assert mem_increase < 100  # MB


def test_memory_stability_concurrent_requests(client, test_input, get_memory_usage):
    """Test memory doesn't leak under concurrent load"""
    mem_before = get_memory_usage()

    def make_request():
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in as_completed(futures)]

    assert all(results)

    mem_after = get_memory_usage()
    mem_increase = mem_after - mem_before

    # Concurrent requests should not leak memory
    assert mem_increase < 150  # MB


# ============================================================================
# Cache Efficiency Tests
# ============================================================================

def test_cache_hit_rate(client, test_input):
    """Test cache hit rate"""
    # First request
    response1 = client.post('/api/assess-borrower-with-shap', json=test_input)
    data1 = response1.get_json()
    cached1 = data1.get('shap', {}).get('cached', False) if data1.get('shap') else False

    hits = 0
    misses = 0

    # Next 9 requests with same input
    for _ in range(9):
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        data = response.get_json()
        cached = data.get('shap', {}).get('cached', False) if data.get('shap') else False

        if cached:
            hits += 1
        else:
            misses += 1

    # Should have mostly cache hits
    hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
    assert hit_rate > 0.5  # At least 50% cache hit rate


def test_cache_speedup_factor(client, test_input):
    """Measure cache speedup factor"""
    # First call (no cache)
    start1 = time.time()
    client.post('/api/assess-borrower-with-shap', json=test_input)
    time1 = time.time() - start1

    # Second call (cached)
    start2 = time.time()
    client.post('/api/assess-borrower-with-shap', json=test_input)
    time2 = time.time() - start2

    if time2 > 0:
        speedup = time1 / time2
        # Cache should provide at least 5x speedup
        assert speedup > 5
    else:
        # If cached call is extremely fast, accept it
        assert time2 < 0.01


# ============================================================================
# Response Size Tests
# ============================================================================

def test_response_size(client, test_input):
    """Test response size is reasonable"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    assert response.status_code == 200

    data = response.get_json()
    response_json = json.dumps(data)
    size_kb = len(response_json) / 1024

    # Response should be reasonable size (<500KB)
    assert size_kb < 500


def test_shap_field_size(client, test_input):
    """Test SHAP field size"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    if data.get('shap'):
        shap_json = json.dumps(data['shap'])
        size_kb = len(shap_json) / 1024

        # SHAP field should be reasonable size (<100KB)
        assert size_kb < 100


# ============================================================================
# Throughput Tests
# ============================================================================

def test_throughput_per_second(client, test_input):
    """Test requests per second throughput"""
    num_requests = 20
    start = time.time()

    for _ in range(num_requests):
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        assert response.status_code == 200

    elapsed = time.time() - start
    rps = num_requests / elapsed

    # Should handle at least 10 RPS
    assert rps > 10


def test_throughput_concurrent(client, test_input):
    """Test concurrent throughput"""
    num_requests = 50
    start = time.time()

    def make_request():
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        results = [f.result() for f in as_completed(futures)]

    elapsed = time.time() - start
    rps = num_requests / elapsed

    assert all(results)
    # Concurrent throughput should be higher
    assert rps > 20


# ============================================================================
# Error Recovery Tests
# ============================================================================

def test_error_recovery_malformed_json(client):
    """Test system recovers from malformed JSON"""
    good_input = {
        "de_ratio": 2.5,
        "interest_coverage": 2.5,
        "profitability": 8,
        "liquidity_ratio": 1.2,
        "exposure": 5000000,
        "seniority": "Senior Secured (Other)",
        "maturity": 3,
    }

    # Send malformed request
    response1 = client.post(
        '/api/assess-borrower-with-shap',
        data='{"bad json}',
        content_type='application/json'
    )
    assert response1.status_code != 200

    # Next request should work fine
    response2 = client.post('/api/assess-borrower-with-shap', json=good_input)
    assert response2.status_code == 200


def test_error_recovery_missing_fields(client):
    """Test system recovers from missing fields"""
    good_input = {
        "de_ratio": 2.5,
        "interest_coverage": 2.5,
        "profitability": 8,
        "liquidity_ratio": 1.2,
        "exposure": 5000000,
        "seniority": "Senior Secured (Other)",
        "maturity": 3,
    }

    bad_input = {
        "de_ratio": 2.5,
        # Missing other fields
    }

    # Send bad request
    response1 = client.post('/api/assess-borrower-with-shap', json=bad_input)
    # May succeed with defaults or fail gracefully

    # Next request should work fine
    response2 = client.post('/api/assess-borrower-with-shap', json=good_input)
    assert response2.status_code == 200


# ============================================================================
# Stress Tests
# ============================================================================

def test_stress_different_inputs(client):
    """Test with various different inputs"""
    inputs = [
        {"de_ratio": 1.0, "interest_coverage": 10.0, "profitability": 15.0, "liquidity_ratio": 2.0, "exposure": 1000000, "seniority": "Senior Secured (Other)", "maturity": 1},
        {"de_ratio": 5.0, "interest_coverage": 1.5, "profitability": 2.0, "liquidity_ratio": 0.8, "exposure": 10000000, "seniority": "Subordinated", "maturity": 5},
        {"de_ratio": 2.5, "interest_coverage": 3.0, "profitability": 8.0, "liquidity_ratio": 1.5, "exposure": 5000000, "seniority": "Senior Unsecured", "maturity": 3},
    ]

    for test_input in inputs:
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        assert response.status_code == 200


def test_stress_extreme_values(client):
    """Test with extreme but valid values"""
    extreme_inputs = [
        {"de_ratio": 0.1, "interest_coverage": 100.0, "profitability": 50.0, "liquidity_ratio": 5.0, "exposure": 100000000, "seniority": "Senior Secured (Other)", "maturity": 0.1},
        {"de_ratio": 10.0, "interest_coverage": 0.5, "profitability": -50.0, "liquidity_ratio": 0.1, "exposure": 1000, "seniority": "Junior", "maturity": 10},
    ]

    for test_input in extreme_inputs:
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        # Should handle gracefully (200 or 500)
        assert response.status_code in [200, 500]


# ============================================================================
# Summary Stats Tests
# ============================================================================

def test_performance_summary(client, test_input):
    """Collect and verify performance summary stats"""
    stats = {
        'requests': 0,
        'successes': 0,
        'failures': 0,
        'total_time': 0,
        'min_latency': float('inf'),
        'max_latency': 0,
    }

    start_total = time.time()

    for _ in range(10):
        start = time.time()
        response = client.post('/api/assess-borrower-with-shap', json=test_input)
        elapsed = time.time() - start

        stats['requests'] += 1
        if response.status_code == 200:
            stats['successes'] += 1
        else:
            stats['failures'] += 1

        stats['total_time'] += elapsed
        stats['min_latency'] = min(stats['min_latency'], elapsed)
        stats['max_latency'] = max(stats['max_latency'], elapsed)

    stats['total_time'] = time.time() - start_total
    stats['avg_latency'] = stats['total_time'] / stats['requests']

    # Assertions
    assert stats['successes'] == 10
    assert stats['failures'] == 0
    assert stats['avg_latency'] < 0.5
    assert stats['min_latency'] < 0.1
    assert stats['max_latency'] < 1.0

    # Print summary
    print(f"\nPerformance Summary:")
    print(f"  Requests: {stats['requests']}")
    print(f"  Success rate: {stats['successes']}/{stats['requests']}")
    print(f"  Min latency: {stats['min_latency']*1000:.2f}ms")
    print(f"  Avg latency: {stats['avg_latency']*1000:.2f}ms")
    print(f"  Max latency: {stats['max_latency']*1000:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
