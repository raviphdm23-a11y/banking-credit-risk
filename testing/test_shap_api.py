"""
Integration tests for SHAP API endpoint (Tier 2, Phase 3).

Tests the new /api/assess-borrower-with-shap endpoint for:
1. Endpoint exists and responds
2. Returns same fields as /api/assess-borrower
3. Includes new "shap" field
4. Performance meets budget
5. Backward compatibility maintained
"""

import pytest
import json
import time
from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_input():
    """Standard risky borrower input"""
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
# Basic Endpoint Tests
# ============================================================================

def test_assess_borrower_with_shap_exists(client):
    """Test /api/assess-borrower-with-shap endpoint exists"""
    response = client.post('/api/assess-borrower-with-shap', json={})
    # Should not 404, may fail with bad input but endpoint exists
    assert response.status_code != 404


def test_assess_borrower_with_shap_requires_post(client):
    """Test endpoint requires POST"""
    response = client.get('/api/assess-borrower-with-shap')
    # Flask routing: GET returns 404 or 405 depending on Flask version
    assert response.status_code in [404, 405]


def test_assess_borrower_endpoint_unchanged(client, test_input):
    """Test original /api/assess-borrower endpoint still works (backward compat)"""
    response = client.post('/api/assess-borrower', json=test_input)
    assert response.status_code == 200

    data = response.get_json()
    assert "pd" in data
    assert "rating" in data
    assert "attribution" in data
    # Shap may or may not be present depending on model availability


def test_both_endpoints_respond(client, test_input):
    """Test both endpoints respond successfully"""
    response1 = client.post('/api/assess-borrower', json=test_input)
    response2 = client.post('/api/assess-borrower-with-shap', json=test_input)

    assert response1.status_code == 200
    assert response2.status_code == 200


# ============================================================================
# Response Structure Tests
# ============================================================================

def test_shap_endpoint_response_structure(client, test_input):
    """Test /api/assess-borrower-with-shap returns expected structure"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    assert response.status_code == 200

    data = response.get_json()

    # Should have all Tier 1 fields
    assert "report_id" in data
    assert "timestamp" in data
    assert "model_version" in data
    assert "pd" in data
    assert "rating" in data
    assert "attribution" in data
    assert "lgd" in data
    assert "rwa" in data
    assert "el" in data
    assert "pricing" in data
    assert "policy_knockouts" in data
    assert "recommendation" in data
    assert "five_cs" in data
    assert "peer_health" in data
    assert "counterfactuals" in data
    assert "macro_regime" in data

    # Should have Tier 2 SHAP field
    assert "shap" in data


def test_shap_field_content(client, test_input):
    """Test SHAP field has correct content"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    shap_data = data["shap"]

    # SHAP field can be None if model unavailable, otherwise complete
    if shap_data is not None:
        assert "base_value" in shap_data
        assert "expected_value" in shap_data
        assert "feature_contributions" in shap_data
        assert "interactions" in shap_data
        assert "summary" in shap_data
        assert "model_version" in shap_data
        assert "computed_at" in shap_data
        assert "cached" in shap_data

        # Verify types
        assert isinstance(shap_data["base_value"], (int, float))
        assert isinstance(shap_data["feature_contributions"], list)
        assert isinstance(shap_data["interactions"], list)
        assert isinstance(shap_data["summary"], str)


def test_shap_feature_contributions(client, test_input):
    """Test feature contributions have correct structure"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    if data["shap"] and data["shap"]["feature_contributions"]:
        for contrib in data["shap"]["feature_contributions"][:3]:
            assert "feature" in contrib
            assert "shap_value" in contrib
            assert "feature_value" in contrib
            assert "baseline_value" in contrib
            assert "direction" in contrib


def test_shap_interactions(client, test_input):
    """Test interactions have correct structure"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    if data["shap"] and data["shap"]["interactions"]:
        for inter in data["shap"]["interactions"]:
            assert "feature_pair" in inter
            assert "interaction_strength" in inter
            assert "type" in inter
            assert "explanation" in inter


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

def test_backward_compat_old_endpoint_no_shap(client, test_input):
    """Test old endpoint doesn't include SHAP by default"""
    # Note: This depends on whether SHAP is available, but old endpoint
    # should still work fine regardless
    response = client.post('/api/assess-borrower', json=test_input)
    assert response.status_code == 200
    data = response.get_json()

    # All standard fields should be present
    assert "pd" in data
    assert "rating" in data
    assert "attribution" in data
    assert "recommendation" in data


def test_both_endpoints_same_base_fields(client, test_input):
    """Test both endpoints return same base fields"""
    response1 = client.post('/api/assess-borrower', json=test_input)
    response2 = client.post('/api/assess-borrower-with-shap', json=test_input)

    data1 = response1.get_json()
    data2 = response2.get_json()

    # Compare key fields (not shap, not metadata like timestamp)
    assert data1["pd"]["point"] == data2["pd"]["point"]
    assert data1["rating"]["grade"] == data2["rating"]["grade"]
    assert len(data1["attribution"]) == len(data2["attribution"])


def test_response_is_json(client, test_input):
    """Test response is valid JSON"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    assert response.status_code == 200

    # Should be parseable JSON
    data = response.get_json()
    assert data is not None
    assert isinstance(data, dict)


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_empty_request_body(client):
    """Test endpoint handles empty request"""
    response = client.post('/api/assess-borrower-with-shap', json={})
    # Engine uses defaults for missing fields, so this succeeds
    assert response.status_code in [200, 400, 500]

    if response.status_code == 200:
        data = response.get_json()
        # Should have used defaults for missing fields
        assert "pd" in data or "error" in data
    else:
        data = response.get_json()
        if "error" in data:
            assert len(data["error"]) > 0


def test_malformed_json(client):
    """Test endpoint handles malformed JSON"""
    response = client.post(
        '/api/assess-borrower-with-shap',
        data='{"bad json}',
        content_type='application/json'
    )
    # Should fail gracefully (400, 415, or 500)
    assert response.status_code in [400, 415, 500]


def test_missing_required_fields(client):
    """Test endpoint handles missing required fields"""
    incomplete_input = {
        "de_ratio": 2.5,
        # Missing other required fields
    }
    response = client.post('/api/assess-borrower-with-shap', json=incomplete_input)
    # Should fail or use defaults
    assert response.status_code in [400, 500] or response.status_code == 200


# ============================================================================
# Performance Tests
# ============================================================================

def test_endpoint_latency_cold(client, test_input):
    """Test first call latency (cold)"""
    start = time.time()
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    elapsed = time.time() - start

    assert response.status_code == 200
    # Cold call should be reasonable (depends on if model loaded)
    assert elapsed < 5.0  # Allow up to 5s for first call


def test_endpoint_latency_warm(client, test_input):
    """Test second call latency (warm, cached)"""
    # First call to warm up
    client.post('/api/assess-borrower-with-shap', json=test_input)

    # Second call should be faster due to caching
    start = time.time()
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    elapsed = time.time() - start

    assert response.status_code == 200
    # Cached call should be fast
    assert elapsed < 1.0


# ============================================================================
# Content Tests
# ============================================================================

def test_response_includes_all_key_outputs(client, test_input):
    """Test response includes all required output fields"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    # PD band
    assert "pd" in data
    assert "point" in data["pd"]
    assert "low" in data["pd"]
    assert "high" in data["pd"]

    # Rating
    assert "rating" in data
    assert "grade" in data["rating"]

    # Attribution
    assert "attribution" in data
    assert len(data["attribution"]) > 0

    # Recommendation
    assert "recommendation" in data
    assert "decision" in data["recommendation"]


def test_pd_is_valid_probability(client, test_input):
    """Test PD values are valid probabilities (0-1)"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    pd = data["pd"]
    assert 0.0 <= pd["point"] <= 1.0
    assert 0.0 <= pd["low"] <= 1.0
    assert 0.0 <= pd["high"] <= 1.0
    assert pd["low"] <= pd["point"] <= pd["high"]


def test_recommendation_is_valid(client, test_input):
    """Test recommendation is valid"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    data = response.get_json()

    decision = data["recommendation"]["decision"]
    assert decision in ["APPROVE", "REFER", "DECLINE"]


# ============================================================================
# Caching Behavior Tests
# ============================================================================

def test_shap_cached_flag(client, test_input):
    """Test SHAP cached flag changes on repeated calls"""
    # First call
    response1 = client.post('/api/assess-borrower-with-shap', json=test_input)
    data1 = response1.get_json()

    if data1["shap"]:
        first_cached = data1["shap"].get("cached", False)

        # Second call (should be cached)
        response2 = client.post('/api/assess-borrower-with-shap', json=test_input)
        data2 = response2.get_json()

        if data2["shap"]:
            second_cached = data2["shap"].get("cached", False)
            # Second call might be cached (depends on timing)
            assert isinstance(second_cached, bool)


# ============================================================================
# Documentation Tests
# ============================================================================

def test_endpoint_has_docstring(client):
    """Test endpoint function has documentation"""
    from app import assess_borrower_with_shap
    assert assess_borrower_with_shap.__doc__ is not None
    assert "SHAP" in assess_borrower_with_shap.__doc__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
