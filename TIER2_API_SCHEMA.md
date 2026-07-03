# Tier 2 API Schema
## SHAP Values Response Format

**Endpoint:** `POST /api/assess-borrower-with-shap`  
**Status:** Design Phase (Production ready by July 17)  
**Response Format:** JSON  

---

## Request

**Same as Tier 1** (`/api/assess-borrower`)

```json
{
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
  "country_code": "IND"
}
```

---

## Response (Full Assessment with SHAP)

```json
{
  "report_id": "uuid",
  "timestamp": "2026-07-04T10:30:00Z",
  "model_version": "run_20260702_045113",
  "inputs": { /* same as request */ },

  "pd": {
    "point": 0.0416,
    "low": 0.0235,
    "high": 0.0596,
    "method": "XGBoostClassifier",
    "n_trees": 200,
    "band_note": "80% interval via binomial SE"
  },

  "rating": {
    "grade": "C",
    "description": "Moderate Credit Risk",
    "score_band": 0.04
  },

  "attribution": [
    /* Tier 1: Feature importance ranking */
    {
      "feature": "de_ratio",
      "display_name": "Debt-to-Equity Ratio",
      "value": 2.5,
      "baseline_value": 1.2,
      "contribution": 0.028649,
      "direction": "increases_pd",
      "reason_code": "HIGH_LEVERAGE",
      "reason_text": "D/E 2.50x is above risk threshold (benchmark <= 2.0x)",
      "five_c": "capacity",
      "xgb_importance": 0.0432,
      "weighted_rank": 0.001238,
      "rank_position": 1
    },
    {
      "feature": "interest_coverage",
      "display_name": "Interest Coverage Ratio",
      "value": 2.5,
      "baseline_value": 6.0,
      "contribution": -0.006746,
      "direction": "decreases_pd",
      "reason_code": null,
      "reason_text": "IC 2.50x is a positive factor — reduces default risk",
      "five_c": "capacity",
      "xgb_importance": 0.0397,
      "weighted_rank": 0.000268,
      "rank_position": 4
    }
    /* ... more features ... */
  ],

  "shap": {
    "base_value": 0.025,
    "expected_value": 0.025,
    "feature_contributions": [
      {
        "feature": "de_ratio",
        "shap_value": 0.028649,
        "feature_value": 2.5,
        "baseline_value": 1.2,
        "direction": "increases_pd"
      },
      {
        "feature": "interest_coverage",
        "shap_value": -0.006746,
        "feature_value": 2.5,
        "baseline_value": 6.0,
        "direction": "decreases_pd"
      },
      {
        "feature": "profitability",
        "shap_value": 0.004842,
        "feature_value": 8.0,
        "baseline_value": 12.0,
        "direction": "increases_pd"
      },
      /* ... remaining features ... */
    ],
    "interactions": [
      {
        "feature_pair": ["de_ratio", "interest_coverage"],
        "interaction_strength": 0.015234,
        "type": "amplifying",
        "explanation": "D/E (2.50) and Interest Coverage (2.50) together amplify risk"
      },
      {
        "feature_pair": ["de_ratio", "profitability"],
        "interaction_strength": 0.008567,
        "type": "amplifying",
        "explanation": "D/E (2.50) and Profitability (8.0) together amplify risk"
      },
      {
        "feature_pair": ["interest_coverage", "liquidity_ratio"],
        "interaction_strength": 0.005123,
        "type": "mitigating",
        "explanation": "Interest Coverage (2.50) and Liquidity Ratio (1.20) together mitigate risk"
      }
    ],
    "summary": "Top drivers: de_ratio, interest_coverage, profitability. Key interaction: de_ratio × interest_coverage (amplifying).",
    "model_version": "run_20260702_045113",
    "computed_at": "2026-07-04T10:30:00Z",
    "cached": false
  },

  "lgd": {
    "lgd": 0.35,
    "lgd_percentage": 35,
    "base_lgd": 0.45,
    "collateral_value": 3000000,
    "collateral_adjustment": 0.1,
    "seniority": "Senior Secured (Other)"
  },

  "ead": 5000000,

  "rwa": {
    "rwa": 1456789,
    "capital_required": 116543,
    "risk_weight_pct": 29.14,
    "correlation_r": 0.12,
    "maturity_adj": 1.041,
    "b_coefficient": 0.139,
    "exposure": 5000000
  },

  "el": {
    "amount": 2088,
    "percentage": 0.0416
  },

  "pricing": {
    "base_spread": 0.0275,
    "pd_adjustment": 0.0125,
    "lgd_adjustment": 0.005,
    "final_spread": 0.045,
    "indicative_rate": 0.085
  },

  "policy_knockouts": [],

  "recommendation": {
    "decision": "REFER",
    "confidence": "medium",
    "reason": "PD exceeds referral threshold",
    "key_risks": ["HIGH_LEVERAGE", "WEAK_PROFITABILITY"],
    "strengths": ["GOOD_LIQUIDITY"],
    "approval_probability": 0.45
  },

  "five_cs": {
    "capacity": {
      "score": "WEAK",
      "items": [
        {
          "label": "Interest Coverage",
          "value": "2.50x",
          "benchmark": ">= 6.00x (model-learned)",
          "assessment": "Below benchmark — risk factor"
        },
        {
          "label": "Debt-to-Equity",
          "value": "2.50x",
          "benchmark": "<= 1.86x (model-learned)",
          "assessment": "Above benchmark — risk factor"
        }
      ]
    },
    "capital": { /* ... */ },
    "collateral": { /* ... */ },
    "character": { /* ... */ },
    "condition": { /* ... */ }
  },

  "peer_health": {
    "de_ratio": {
      "value": 2.5,
      "peer_median": 1.2,
      "peer_p25": 0.8,
      "peer_p75": 1.62,
      "status": "WEAK",
      "gap": 1.3,
      "gap_pct": 108.3
    }
    /* ... more features ... */
  },

  "counterfactuals": [
    {
      "feature": "interest_coverage",
      "display_name": "Interest Coverage Ratio",
      "current_value": 2.5,
      "target_value": 4.0,
      "current_grade": "C",
      "target_grade": "B-",
      "pd_current": 0.0416,
      "pd_target": 0.0234,
      "pd_reduction_pp": 0.0182,
      "pct_change": 60.0
    }
  ],

  "macro_regime": {
    "score": 0.0,
    "label": "Normal",
    "delta_gdp_pct": 0.0,
    "delta_unemployment_pct": 0.0,
    "delta_policy_rate_pct": 0.0,
    "delta_cpi_pct": 0.0,
    "interpretation": "No significant regime shift — standard cycle conditions"
  },

  "content_hash": "sha256_hash_for_audit"
}
```

---

## Key Differences from Tier 1

### NEW FIELD: `shap`

```json
"shap": {
  "base_value": 0.025,
  "expected_value": 0.025,
  "feature_contributions": [
    {
      "feature": "de_ratio",
      "shap_value": 0.028649,
      "feature_value": 2.5,
      "baseline_value": 1.2,
      "direction": "increases_pd"
    }
  ],
  "interactions": [
    {
      "feature_pair": ["de_ratio", "interest_coverage"],
      "interaction_strength": 0.015234,
      "type": "amplifying",
      "explanation": "..."
    }
  ],
  "summary": "...",
  "model_version": "...",
  "computed_at": "...",
  "cached": false
}
```

### Unchanged from Tier 1

- `pd`, `rating`, `attribution`, `lgd`, `ead`, `rwa`, `el`, `pricing`
- `policy_knockouts`, `recommendation`, `five_cs`, `peer_health`, `counterfactuals`
- `macro_regime`, `content_hash`

---

## SHAP Field Details

### `base_value` / `expected_value`
- **Type:** float
- **Range:** 0.0 to 1.0
- **Meaning:** Model's average prediction (baseline before any features applied)
- **Note:** `base_value` + sum(`shap_value`) = PD point estimate

### `feature_contributions`

Array of features sorted by absolute `shap_value` (strongest first).

| Field | Type | Meaning |
|-------|------|---------|
| `feature` | string | Feature name (e.g., "de_ratio") |
| `shap_value` | float | SHAP value (contribution to PD) |
| `feature_value` | float | Borrower's actual value for this feature |
| `baseline_value` | float | Training distribution baseline |
| `direction` | string | "increases_pd" or "decreases_pd" |

### `interactions`

Top 3 feature interactions, sorted by `interaction_strength` (largest first).

| Field | Type | Meaning |
|-------|------|---------|
| `feature_pair` | [str, str] | Two features that interact |
| `interaction_strength` | float | Magnitude of interaction (0.0 to 1.0) |
| `type` | string | "amplifying" (joint risk > sum) or "mitigating" (joint risk < sum) |
| `explanation` | string | Plain English explanation |

**Threshold for inclusion:** interaction_strength > 0.003

### `summary`
- **Type:** string
- **Format:** "Top drivers: feat1, feat2, feat3. Key interaction: feat1 × feat2 (amplifying/mitigating)."
- **Purpose:** Executive one-liner for quick assessment

### `cached`
- **Type:** boolean
- **Meaning:** `true` if result came from cache, `false` if computed fresh
- **Performance:** Cached results return in ~2-5ms, fresh in ~100-150ms

---

## Backward Compatibility

### Old Endpoint (Tier 1 Only)
```
GET /api/assess-borrower
Response: Does NOT include "shap" field
```

### New Endpoint (Tier 1 + Tier 2)
```
GET /api/assess-borrower-with-shap
Response: Includes all Tier 1 fields PLUS new "shap" field
```

**Advantage:** Existing clients keep working; new clients opt-in to SHAP

---

## Performance Characteristics

| Scenario | Latency | Notes |
|----------|---------|-------|
| Cold (no cache) | 100-150ms | SHAP computation + interaction detection |
| Warm (cached) | 2-5ms | Hash lookup + return |
| Interaction detection | +30-50ms | Computed as part of SHAP |
| Force plot generation | +20-30ms | Frontend, not API |

**Latency budget:** <150ms for API response

---

## Frontend Integration

### HTML Report Enhancement

The `shap` field powers a new section in `report-underwriter.html`:

```html
<div class="report-section" id="shap-section">
  <h3>Feature Interactions (SHAP Analysis)</h3>
  
  <!-- Force plot visualization -->
  <div id="shap-force-plot"></div>
  
  <!-- Top interactions with explanations -->
  <div class="interactions-list">
    <div class="interaction-item">
      <h4>Interaction 1: de_ratio × interest_coverage</h4>
      <p>Type: Amplifying | Strength: 0.0152</p>
      <p>Explanation: D/E (2.50) and IC (2.50) together amplify risk</p>
    </div>
  </div>
</div>
```

### SHAP Force Plot
- **Library:** SHAP JavaScript library
- **Visualization:** Horizontal force plot showing each feature pushing PD up/down
- **Base value:** Starting point (0.025)
- **Features:** Color-coded (red = increases PD, blue = decreases PD)
- **Interactive:** Hover for details

---

## Example: Detailed Response

```json
{
  "shap": {
    "base_value": 0.025,
    "expected_value": 0.025,
    "feature_contributions": [
      {
        "feature": "de_ratio",
        "shap_value": 0.0286,
        "feature_value": 2.5,
        "baseline_value": 1.2,
        "direction": "increases_pd"
      },
      {
        "feature": "interest_coverage",
        "shap_value": -0.0067,
        "feature_value": 2.5,
        "baseline_value": 6.0,
        "direction": "decreases_pd"
      },
      {
        "feature": "profitability",
        "shap_value": 0.0048,
        "feature_value": 8.0,
        "baseline_value": 12.0,
        "direction": "increases_pd"
      }
    ],
    "interactions": [
      {
        "feature_pair": ["de_ratio", "interest_coverage"],
        "interaction_strength": 0.0152,
        "type": "amplifying",
        "explanation": "D/E (2.50) and Interest Coverage (2.50) together amplify risk"
      },
      {
        "feature_pair": ["de_ratio", "profitability"],
        "interaction_strength": 0.0086,
        "type": "amplifying",
        "explanation": "D/E (2.50) and Profitability (8.0) together amplify risk"
      },
      {
        "feature_pair": ["interest_coverage", "liquidity_ratio"],
        "interaction_strength": 0.0051,
        "type": "mitigating",
        "explanation": "IC (2.50) and Liquidity Ratio (1.20) together mitigate risk"
      }
    ],
    "summary": "Top drivers: de_ratio, interest_coverage, profitability. Key interaction: de_ratio × interest_coverage (amplifying).",
    "model_version": "run_20260702_045113",
    "computed_at": "2026-07-04T10:30:00Z",
    "cached": false
  }
}
```

**Reading this:**
- Base PD is 0.025 (2.5%)
- D/E pushes it up by +0.0286
- IC pulls it down by -0.0067 (protective)
- D/E × IC interaction adds +0.0152 extra risk (they amplify each other)
- Sum: 0.025 + 0.0286 - 0.0067 + 0.0152 ≈ 0.0421 ≈ actual PD 0.0416

---

## Implementation Checklist

- [ ] SHAP explainer module created (`backend/shap_explainer.py`)
- [ ] Caching strategy implemented
- [ ] Integration with assessment engine
- [ ] API endpoint `/api/assess-borrower-with-shap` added
- [ ] HTML report updated with SHAP visualization
- [ ] Force plot JavaScript integrated
- [ ] Tests written + passing
- [ ] Performance validated <150ms
- [ ] Documentation complete

---

## Next Steps (Phase 1 Complete)

1. ✅ Design API schema (this document)
2. ✅ Create SHAP explainer module
3. Next: Implement integration with assessment_engine.py
