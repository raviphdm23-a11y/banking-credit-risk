# Tier 2: SHAP Values Implementation Plan
## Feature Interactions & True Additive Attribution

**Priority:** First Tier 2 feature  
**Timeline:** 2 weeks  
**Expected Impact:** +50% attribution accuracy  
**Start Date:** July 3, 2026  
**Target Completion:** July 17, 2026

---

## Overview: Why SHAP Values?

### Problem Tier 1 Solves
- Shows which features matter (importance ranking)
- Uses lower bound for knockouts (uncertainty)
- Learns thresholds from data

### Problem Tier 2 Solves (SHAP)
- Tier 1 still shows features independently
- Can't explain feature interactions (D/E + low IC = synergistic risk)
- No model uncertainty on individual features
- Reports don't explain "why" features interact

### What SHAP Values Provide
- **True Additive Attribution:** Each feature's exact contribution to this borrower's PD
- **Interaction Handling:** Automatically accounts for how features work together
- **Model Transparency:** SHAP values sum to model's prediction (perfect decomposition)
- **Interpretability:** Each value is a probability mass shift from baseline

**Example:**
```
TIER 1: "D/E +0.0286, IC -0.0067, Profit +0.0048"
        (independent, can't see interactions)

TIER 2: "D/E +0.0286, IC -0.0067, Profit +0.0048
        INTERACTION: D/E × Low IC = +0.015 extra risk
        (shows how they work together)"
```

---

## Implementation Plan

### Phase 1: Design & Architecture (3 days)

#### 1.1 SHAP Library Integration
**Task:** Choose SHAP approach
```python
# Option A: TreeExplainer (for XGBoost)
from shap import TreeExplainer
# Fastest, most accurate for tree models
# Performance: ~50ms per assessment

# Option B: KernelExplainer
# Slower but model-agnostic
# Performance: ~500ms per assessment

# Recommendation: TreeExplainer (XGBoost-optimized)
```

**Deliverable:** SHAP setup in `backend/explainability.py`

#### 1.2 Caching Strategy
**Task:** Design SHAP value caching (avoid recomputation)

```python
# Cache structure:
_shap_cache = {
    "model_version": "run_20260702_045113",
    "borrower_hash": shap_values,  # Keyed by input hash
    "last_cleaned": datetime,
    "size_mb": 0,
}

# Cache invalidation:
# - On model retrain
# - After 7 days
# - If cache exceeds 500MB
```

**Deliverable:** Caching module in `backend/shap_cache.py`

#### 1.3 API Response Structure
**Task:** Define JSON schema for SHAP values

```json
{
  "shap_values": {
    "base_value": 0.025,
    "expected_value": 0.025,
    "feature_contributions": [
      {
        "feature": "de_ratio",
        "shap_value": 0.0286,
        "feature_value": 2.5,
        "baseline_value": 1.2
      },
      ...
    ],
    "interactions": [
      {
        "feature_pair": ["de_ratio", "interest_coverage"],
        "interaction_strength": 0.015,
        "type": "amplifying"  # or "mitigating"
      },
      ...
    ],
    "summary": "High D/E + Low IC creates synergistic risk (+0.015)"
  }
}
```

**Deliverable:** Schema document + example JSON

---

### Phase 2: Core Implementation (5 days)

#### 2.1 SHAP Computation Module
**File:** `backend/shap_explainer.py` (NEW)

```python
class SHAPExplainer:
    def __init__(self, model, training_data=None):
        """Initialize SHAP explainer for XGBoost model"""
        self.model = model
        self.explainer = shap.TreeExplainer(model)
        # Training data for background reference

    def explain_assessment(self, inputs, use_cache=True):
        """
        Compute SHAP values for a single assessment
        
        Returns:
            {
                "base_value": float,
                "shap_values": array,
                "feature_names": list,
                "interactions": list,
            }
        """
        # Check cache
        if use_cache:
            cached = self._get_cached(inputs_hash)
            if cached: return cached
        
        # Compute SHAP values
        X = model_feature_frame(inputs, self.model)
        shap_values = self.explainer.shap_values(X)[0, 1]  # For class=1 (default)
        
        # Detect interactions
        interactions = self._find_interactions(shap_values, inputs)
        
        # Cache result
        self._cache_result(inputs_hash, result)
        
        return result

    def _find_interactions(self, shap_values, inputs):
        """
        Find significant feature interactions
        
        Logic:
        1. For each feature pair
        2. Compute joint SHAP value
        3. If |joint| > |independent sum|, interaction exists
        4. Return sorted by strength
        """
        interactions = []
        for feat1, feat2 in combinations(FEATURE_ORDER, 2):
            joint_val = self._compute_joint_shap(feat1, feat2, inputs)
            individual_sum = shap_values[feat1] + shap_values[feat2]
            
            interaction_strength = abs(joint_val - individual_sum)
            if interaction_strength > 0.003:  # Threshold
                interactions.append({
                    "pair": (feat1, feat2),
                    "strength": interaction_strength,
                    "type": "amplifying" if joint_val > individual_sum else "mitigating"
                })
        
        return sorted(interactions, key=lambda x: x["strength"], reverse=True)
```

**Deliverable:** Fully functional SHAP computation module

#### 2.2 Integration with Assessment Engine
**File:** `backend/assessment_engine.py` (MODIFIED)

```python
def assess(self, inputs: dict) -> dict:
    # ... existing Tier 1 code ...
    
    # NEW: Compute SHAP values
    shap_data = self._compute_shap(inputs, pd_point)
    
    findings = {
        # ... existing fields ...
        "shap": shap_data,  # NEW FIELD
    }
    
    return findings

def _compute_shap(self, inputs: dict, pd_point: float) -> dict:
    """Compute SHAP values for this assessment"""
    explainer = SHAPExplainer(self._model)
    return explainer.explain_assessment(inputs)
```

**Deliverable:** SHAP integrated into assessment pipeline

#### 2.3 Interaction Detection & Ranking
**File:** `backend/explainability.py` (ENHANCED)

```python
def rank_interactions(self, shap_data, attribution_tier1):
    """
    Rank feature interactions by impact
    
    Returns top 3 interactions with explanations
    """
    interactions = shap_data["interactions"]
    
    for inter in interactions[:3]:
        feat1, feat2 = inter["pair"]
        strength = inter["strength"]
        type_ = inter["type"]
        
        # Generate explanation
        if type_ == "amplifying":
            explanation = f"{feat1} and {feat2} together create synergistic risk"
        else:
            explanation = f"{feat1} and {feat2} together offset each other"
        
        inter["explanation"] = explanation
    
    return interactions[:3]
```

**Deliverable:** Interaction ranking logic

---

### Phase 3: API Exposure (2 days)

#### 3.1 New API Endpoint
**File:** `app.py` (NEW ENDPOINT)

```python
@app.route('/api/assess-borrower-with-shap', methods=['POST'])
def assess_borrower_with_shap():
    """
    Full assessment with SHAP values and interactions
    
    Same as /api/assess-borrower but includes:
    - SHAP values for each feature
    - Feature interactions
    - Interaction explanations
    """
    data = request.get_json()
    
    findings = _assessment_engine.assess(data)
    
    # findings already includes "shap" field from Tier 2
    return jsonify(findings)
```

**Deliverable:** SHAP values exposed via API

#### 3.2 Backward Compatibility
**Ensure:** `/api/assess-borrower` still works (Tier 1 mode)

```python
# Old endpoint still returns:
# - PD (point, low, high)
# - Attribution (xgb_importance, weighted_rank)
# - Five C's (learned thresholds)
# - Policy knockouts (with uncertainty band)

# New endpoint additionally returns:
# - SHAP values
# - Feature interactions
# - Interaction explanations
```

**Deliverable:** No breaking changes to existing API

---

### Phase 4: Testing (3 days)

#### 4.1 Unit Tests
**File:** `testing/test_shap.py` (NEW)

```python
def test_shap_values_sum_to_pd():
    """SHAP values must sum to model's prediction"""
    findings = engine.assess(test_input)
    
    shap_sum = findings["shap"]["base_value"] + sum(
        f["shap_value"] for f in findings["shap"]["feature_contributions"]
    )
    
    assert abs(shap_sum - findings["pd"]["point"]) < 0.0001
    # SHAP decomposition must be perfect

def test_interaction_detection():
    """Test that known interactions are detected"""
    # High D/E + Low IC should have interaction
    risky_combo = {
        "de_ratio": 3.0,
        "interest_coverage": 1.5,
        "profitability": 5,
        "liquidity_ratio": 1.0,
        ...
    }
    
    findings = engine.assess(risky_combo)
    interactions = findings["shap"]["interactions"]
    
    de_ic_pair = [i for i in interactions if set(i["pair"]) == {"de_ratio", "interest_coverage"}]
    assert len(de_ic_pair) > 0
    assert de_ic_pair[0]["type"] == "amplifying"

def test_caching():
    """Test SHAP value caching works"""
    findings1 = engine.assess(test_input)
    findings2 = engine.assess(test_input)  # Should be cached
    
    assert findings1["shap"] == findings2["shap"]
    # Same input → same SHAP values (from cache)
```

**Deliverable:** Comprehensive test coverage

#### 4.2 Integration Tests
**File:** `testing/test_shap_integration.py` (NEW)

```python
def test_shap_api_endpoint():
    """Test /api/assess-borrower-with-shap endpoint"""
    response = client.post('/api/assess-borrower-with-shap', json=test_input)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "shap" in data
    assert "feature_contributions" in data["shap"]
    assert "interactions" in data["shap"]
    assert "base_value" in data["shap"]

def test_backward_compat():
    """Test old endpoint still works"""
    response = client.post('/api/assess-borrower', json=test_input)
    
    assert response.status_code == 200
    assert "shap" not in response.json()  # Old endpoint doesn't include SHAP
```

**Deliverable:** Integration tests passing

#### 4.3 Performance Tests
**File:** `testing/test_shap_performance.py` (NEW)

```python
def test_shap_latency():
    """SHAP computation should not exceed latency budget"""
    start = time.time()
    findings = engine.assess(test_input)
    elapsed = time.time() - start
    
    assert elapsed < 0.15  # 150ms budget (with caching)
    # First call: ~100-150ms (compute)
    # Cached call: ~2-5ms (lookup)

def test_shap_cache_efficiency():
    """Cache should reduce latency significantly"""
    # First assessment (no cache)
    start1 = time.time()
    engine.assess(test_input)
    time1 = time.time() - start1
    
    # Second assessment (from cache)
    start2 = time.time()
    engine.assess(test_input)
    time2 = time.time() - start2
    
    assert time2 < time1 / 10  # Cached should be 10x faster
```

**Deliverable:** Performance verified <150ms with cache

---

### Phase 5: Frontend Visualization (2 days)

#### 5.1 Report Template Updates
**File:** `public/report-underwriter.html` (ENHANCED)

Add SHAP visualization section:

```html
<!-- NEW SECTION: Feature Interactions (SHAP) -->
<div class="report-section">
  <div class="section-title">2b — Feature Interactions (How Features Work Together)</div>
  
  <div id="shap-container">
    <!-- SHAP force plot visualization -->
    <div id="shap-force-plot"></div>
    
    <!-- Top interactions -->
    <div class="interactions-list">
      <div class="interaction-item">
        <h4>Interaction 1: D/E × Interest Coverage</h4>
        <p>Synergistic Risk: +0.015 to PD</p>
        <p>Your profile: High D/E (2.5x) + Low IC (2.5x) = combined risk</p>
        <p>If you improve IC to 4.0x: Interaction risk drops to +0.005</p>
      </div>
    </div>
  </div>
</div>
```

**Deliverable:** SHAP visualization in HTML report

#### 5.2 SHAP Force Plot
**Generate:** Interactive force plot showing SHAP decomposition

```python
# Using shap.force_plot() library
# Shows: base_value → feature contributions → final PD
# Visual: force diagram (features pushing PD up/down)
```

**Deliverable:** Force plot renders in HTML

---

## Implementation Schedule

| Week | Days | Task | Deliverable |
|------|------|------|-------------|
| Week 1 (7/3-7/9) | 1-3 | Design architecture, choose SHAP approach | Architecture doc + schema |
| | 4-5 | Implement SHAP module, integrate with engine | Working SHAP computation |
| Week 2 (7/10-7/17) | 1-3 | Unit + integration testing | Tests passing |
| | 4 | Performance optimization + caching | <150ms latency verified |
| | 5 | Frontend visualization + report updates | HTML report with SHAP |

---

## Code Structure

```
backend/
├── explainability.py (EXISTING - ENHANCED)
│   ├── PeerComparison (existing)
│   ├── CounterfactualEngine (existing)
│   └── InteractionRanker (NEW)
│
├── shap_explainer.py (NEW)
│   ├── SHAPExplainer class
│   ├── Interaction detection
│   └── Caching logic
│
├── shap_cache.py (NEW)
│   └── Cache management
│
├── assessment_engine.py (MODIFIED)
│   ├── _compute_shap() method (NEW)
│   └── assess() integration (updated)
│
└── ...

app.py (MODIFIED)
├── /api/assess-borrower-with-shap (NEW endpoint)
└── /api/assess-borrower (unchanged - backward compat)

public/
├── report-underwriter.html (MODIFIED)
│   └── SHAP visualization section (NEW)
└── ...

testing/ (NEW)
├── test_shap.py
├── test_shap_integration.py
└── test_shap_performance.py
```

---

## Success Criteria

### Must Have (MVP)
- [ ] SHAP values computed correctly
- [ ] Feature interactions detected
- [ ] API returns SHAP data
- [ ] Backward compatibility maintained
- [ ] Latency <150ms (with cache)
- [ ] Tests passing (80%+ coverage)

### Should Have
- [ ] Force plot visualization in report
- [ ] Interaction explanations clear
- [ ] Performance optimized
- [ ] Caching working

### Nice to Have
- [ ] Interactive what-if using SHAP
- [ ] Benchmark against Tier 1 attribution
- [ ] Documentation for underwriters

---

## Risk & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| SHAP computation too slow | Medium | High | Implement caching; profile early |
| Interaction detection overfits | Low | Medium | Validate on holdout set |
| Complex to explain to underwriters | Medium | Medium | Create clear visual + training |
| Breaking changes to API | Low | High | Maintain backward compat endpoint |

---

## Rollback Plan

If SHAP values cause issues:
1. Keep old endpoint working (`/api/assess-borrower`)
2. Disable SHAP in assessment by default
3. Add feature flag: `enable_shap=false`
4. Investigate and fix
5. Re-enable gradually

**Rollback command:**
```bash
git revert HEAD  # Revert Tier 2
# System returns to Tier 1 only
```

---

## Next Steps (Starting Tomorrow)

1. **Day 1:** Design review + architecture approval
2. **Day 2:** Set up SHAP library + basic explainer
3. **Day 3:** Integration with assessment engine
4. **Day 4-5:** Testing + performance tuning
5. **Day 6-7:** Frontend visualization + final testing
6. **Day 8:** Deploy to production
7. **Week 2:** Monitor + gather underwriter feedback

---

## Completion Checklist

- [ ] SHAP explainer module written + tested
- [ ] Integration tests passing
- [ ] Performance <150ms verified
- [ ] API endpoint returning SHAP values
- [ ] HTML report updated with visualization
- [ ] Backward compatibility confirmed
- [ ] Deployed to production
- [ ] Monitoring active
- [ ] Underwriter feedback collected

---

**Ready to start?** Yes! Let's begin Phase 1 tomorrow.

Timeline: 2 weeks to full Tier 2 SHAP implementation.
