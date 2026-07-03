# Comprehensive Credit Risk Assessment Synthesis Framework

**Purpose:** Integrate SHAP feature attribution with regulatory AIRB parameters for production-grade credit committee documentation.

---

## Executive Framework: Synthesizing Three Document Layers

### Layer 1: Primary Credit Decision (Main Report)
- Borrower demographics and financial profile
- PD estimate and confidence bands
- Rating grade and recommendation
- Five C's assessment

### Layer 2: Regulatory Parameters (Dashboard/AIRB)
- Asset correlation coefficient (ρ)
- Maturity adjustment factor (b)
- Risk weight percentage (RW%)
- Risk-weighted assets (RWA)
- Basel III capital requirement (CAR)

### Layer 3: Explainability Overlay (SHAP - NEW)
- Feature contribution decomposition
- Interaction effects and synergies
- Sensitivity to key drivers
- Counterfactual scenarios

---

## Enhanced Synthesis Prompt Template

```
Act as a senior credit risk validator synthesizing quantitative, 
regulatory, and explainability dimensions into a comprehensive 
credit assessment for rigorous committee review.

DOCUMENTS PROVIDED:
1. Main Report: Credit decision narrative and borrower profile
2. Dashboard: AIRB mechanics and regulatory parameters
3. SHAP Attribution: Feature-level contribution analysis

YOUR SYNTHESIS TASK:

=== SECTION 1: EXECUTIVE SUMMARY ===
Synthesize the final recommendation with confidence intervals.
Include: PD point estimate | Rating grade | Recommendation | 
Key risk drivers | Regulatory constraints.

=== SECTION 2: REGULATORY CAPITAL MECHANICS ===
Detail the Basel III AIRB parameters:

2.1 Asset Correlation Coefficient (ρ)
    - Specify value (e.g., 0.15 for corporate)
    - Source: Regulatory formula or bank estimate
    - Sensitivity to borrower size/sector

2.2 Maturity Adjustment Factor (b)
    - Formula: b = (0.11852 - 0.05478 × ln(PD))²
    - Calculated maturity adjustment
    - Impact on capital requirement

2.3 Risk Weight Calculation
    - LGD estimate (e.g., 0.45)
    - EAD (exposure at default)
    - Final RW% = [N(√(ρ/(1-ρ)) × G(PD) + √((1-ρ)/(ρ)) × G(0.999)) 
                    - PD] × (1 + (M - 2.5) × b) / (1.06)
    - Implied RWA

2.4 Capital Requirement (CAR)
    - CET1 requirement: 4.5% of RWA
    - Tier 1 requirement: 6% of RWA
    - Total CAR requirement: 8% of RWA
    - Regulatory cushion/(gap)

=== SECTION 3: FEATURE ATTRIBUTION ANALYSIS (SHAP) ===
Interpret the machine learning drivers with technical precision.

3.1 Marginal Contribution to Default Probability
    From SHAP analysis, report:
    - Base case PD (model average)
    - Top 5 features by |SHAP value|
    - For each: Feature name | Current value | SHAP contribution 
               | Direction (increase/decrease PD) | Percentage point 
               effect on PD

    Example format:
    "Debt-to-Equity Ratio (2.5x): +0.286% PD contribution
     [+61% uplift from base case]"

3.2 Feature Interactions (Tier 2)
    Identify and explain synergistic effects:
    - Top 3 feature pairs by interaction strength
    - Type: Amplifying (increases combined effect) or 
             Mitigating (reduces combined effect)
    - Quantified synergy impact
    - Economic interpretation

    Example:
    "High Leverage × Low Coverage (AMPLIFYING, 45% strength):
     D/E of 2.5x combined with Interest Coverage of 2.5x creates
     elevated debt service capacity risk. The synergistic effect 
     amplifies default probability by an additional 0.15%, beyond 
     the individual feature contributions."

3.3 Model Sensitivity & Uncertainty
    - 80% confidence band around PD point estimate
    - Key driver sensitivity: If D/E improves to 1.5x, PD falls to X%
    - Uncertainty sources: Missing data? Macro regime transitions?

3.4 Counterfactual Scenarios (Improvement Pathways)
    From SHAP, quantify rating upgrade paths:
    - Current PD: X% (Grade: BB)
    - Scenario A: D/E → 2.0x | Coverage → 3.5x
      Implied PD: Y% (Grade: BBB) | Timeline: 18 months
    - Scenario B: Collateral increase to 60% LTV
      Implied PD: Z% (Grade: A) | Difficulty: Medium

=== SECTION 4: POLICY KNOCKOUTS & CONSTRAINTS ===
Confirm automated policy rule application:
- Does model output violate any hard stops?
- Geographic/sector/product policy constraints?
- Management override flags?

=== SECTION 5: MACRO REGIME ASSESSMENT ===
Incorporate Macro Regime Score (if available):
- Current regime: Expansion/Stagnation/Contraction
- Probability shift if economy moves to next state
- Data availability: Lagged/forward-looking/nowcast

=== SECTION 6: SYNTHESIZED RECOMMENDATION ===
Present unified decision:
- Rating grade with confidence
- PD estimate with band
- Recommended action: APPROVE/REFER/DECLINE
- Key conditions/covenants if approval
- Improvement milestones for upgrade potential
- Risks requiring monitoring

=== APPENDIX: TECHNICAL VALIDATION ===
Validate model robustness:
- Feature importance ranking (Tier 1)
- SHAP value sum = PD point estimate (Tier 2)
- Interaction patterns economically sensible?
- Outlier detection: Any suspicious borrower comparables?
```

---

## Yes: Explicitly Include Feature Attribution

### Why SHAP Attribution is Critical for Credit Committees:

#### 1. **Regulatory Compliance**
- **Basel III Pillar 2 (Supervisory Review):** Regulators expect banks to explain rating drivers
- **CCAR/DFAST Stress Testing:** Explainability required for scenario stress tests
- **Model Governance (SR 11-7):** Fed requires documented rationale for material decisions
- **Fair Lending (FCRA):** Adverse Action Notice must explain decision factors

#### 2. **Model Transparency**
- **Committee Member Confidence:** Non-data scientists need understandable explanations
- **Audit Trail:** SHAP values provide immutable record of decision logic
- **Reproducibility:** Exactly which features drove the PD estimate?

#### 3. **Risk Management**
- **Concentration Risk:** Identify borrowers with idiosyncratic driver patterns
- **Macro Sensitivity:** Which borrowers most sensitive to key macro drivers?
- **Reverse Stress Testing:** What feature levels would trigger downgrade?

#### 4. **Business Decisions**
- **Covenant Setting:** Tie covenants to SHAP drivers (e.g., covenant on D/E if that's top driver)
- **Pricing:** If model flagged high leverage, why not charge for it?
- **Relationship Strategy:** What improvements would most help rating upgrade?

---

## Structured SHAP Integration into Credit Reports

### Section 3.1: Marginal Contribution Format

**Template:**

```
FEATURE ATTRIBUTION ANALYSIS
Tier 1: Feature Importance (XGBoost) | Tier 2: SHAP Values (Interactions)

Feature                    | Current Value | SHAP Value | % Effect | Direction
─────────────────────────────────────────────────────────────────────
Debt-to-Equity Ratio       | 2.50x         | +0.286%    | +61%     | Increases PD ↑
Interest Coverage Ratio    | 2.50x         | -0.257%    | -55%     | Decreases PD ↓
Net Profit Margin          | 8.0%          | +0.048%    | +10%     | Increases PD ↑
Current Ratio (Liquidity)  | 1.20x         | -0.204%    | -44%     | Decreases PD ↓
CIBIL Score                | 650           | -0.156%    | -33%     | Decreases PD ↓

Base Case Model PD (all features at training mean):        0.468%
Actual Borrower PD (this specific profile):                4.09%
Difference (explained by features above):                  3.62% ✓

Economic Interpretation:
This borrower's elevated PD is primarily driven by HIGH LEVERAGE (D/E 2.5x),
partially offset by ADEQUATE INTEREST COVERAGE (2.5x). If leverage improved
to 1.5x while maintaining current coverage, PD would fall to ~2.8% (BBB grade).
```

---

### Section 3.2: Interaction Effects Format

**Template:**

```
FEATURE INTERACTIONS: HOW FEATURES COMBINE

Interaction #1: LEVERAGE × COVERAGE (MITIGATING, 61% strength)
─────────────────────────────────────────────────────────────
D/E Ratio: 2.5x | Interest Coverage: 2.5x
Combined Effect: -0.152% (mitigating force reducing PD)

Economic Narrative:
While D/E of 2.5x alone would elevate default risk, the borrower's
interest coverage of 2.5x (though modest) demonstrates capacity to
service that debt. The synergistic effect of adequate coverage 
partially shields against leverage. This borrower is "levered but 
not stretched."

Risk Assessment: MODERATE
- If coverage falls below 2.0x, this mitigation disappears
- Covenant Recommendation: Minimum Interest Coverage ≥ 2.2x

─────────────────────────────────────────────────────────────

Interaction #2: PROFITABILITY × LEVERAGE (AMPLIFYING, 35% strength)
─────────────────────────────────────────────────────────────
Net Margin: 8.0% | D/E Ratio: 2.5x
Combined Effect: +0.087% (amplifying risk)

Economic Narrative:
Thin profit margins (8%) combined with high leverage create a
vulnerability. If revenues decline by 15%, margins compress to 6.8%,
and debt service capacity deteriorates rapidly. Limited earnings
cushion relative to debt burden.

Risk Assessment: ELEVATED
- Monitor: Revenue trends (top-line stability)
- Covenant Recommendation: Minimum EBITDA Margin ≥ 9%

─────────────────────────────────────────────────────────────
```

---

### Section 3.3: Counterfactual Sensitivity Format

**Template:**

```
SENSITIVITY TO KEY DRIVERS: WHAT-IF ANALYSIS

Current State → Scenario A: Deleveraging
────────────────────────────────────────
Current: D/E 2.5x, Coverage 2.5x, Margin 8% → PD 4.09%, Grade BB
Scenario: D/E 2.0x, Coverage 3.0x, Margin 8% → PD 3.24%, Grade BB+
Timeline: 18 months (feasible with disciplined capex/dividend policy)
Difficulty: MEDIUM

Current State → Scenario B: Improved Coverage
────────────────────────────────────────
Current: D/E 2.5x, Coverage 2.5x, Margin 8% → PD 4.09%, Grade BB
Scenario: D/E 2.5x, Coverage 4.0x, Margin 8% → PD 2.89%, Grade BBB-
Timeline: 12 months (achievable via EBITDA growth or debt paydown)
Difficulty: MEDIUM-LOW

Current State → Scenario C: Profitability Improvement
────────────────────────────────────────
Current: D/E 2.5x, Coverage 2.5x, Margin 8% → PD 4.09%, Grade BB
Scenario: D/E 2.5x, Coverage 2.5x, Margin 11% → PD 3.65%, Grade BB
Timeline: 24 months (operational improvement, pricing power)
Difficulty: MEDIUM-HIGH

IMPLICATION FOR CREDIT COMMITTEE:
Scenario A (deleveraging) offers fastest path to upgrade to BBB.
Recommend covenant on Minimum EBITDA/Interest Expense ≥ 2.5x
(Scenario B requirement) to accelerate upgrade timeline.
```

---

## Regulatory Alignment Checklist

### ✓ Basel III AIRB Documentation
- [ ] Asset correlation coefficient documented
- [ ] Maturity adjustment factor calculated
- [ ] Risk weight formula detailed with inputs
- [ ] RWA explicitly derived
- [ ] CAR requirement vs. actual capital compared

### ✓ Model Explainability (SR 11-7 Compliance)
- [ ] Feature rankings documented (Tier 1)
- [ ] SHAP values sum to point estimate (Tier 2)
- [ ] Top 5 drivers identified with magnitudes
- [ ] Interactions explained economically
- [ ] Uncertainties/confidence intervals stated

### ✓ Governance Trail
- [ ] Model version noted
- [ ] Training data period documented
- [ ] Out-of-sample performance metrics (AUC, etc.)
- [ ] Known limitations flagged
- [ ] Sensitivity analysis completed

### ✓ Fair Lending / Adverse Action
- [ ] Adverse action notice explains key decision drivers
- [ ] No protected characteristics appear in feature set
- [ ] Disparate impact analysis completed
- [ ] Borrower can understand why declined/downgraded

---

## Integration with Your Tier 2 SHAP System

Your implementation includes:
1. **Tier 1:** XGBoost feature importance
2. **Tier 2:** SHAP values + interactions

**Recommendation:** Build report generation that:

```python
# Pseudocode for report synthesis
def generate_credit_committee_report(assessment_findings):
    """
    Synthesize assessment into regulatory-grade report
    
    Inputs:
    - assessment_findings (from /api/assess-borrower-with-shap)
      Contains: pd, rating, attribution (Tier 1), 
                shap data (Tier 2 with interactions)
    
    Outputs:
    - executive summary (recommendation + confidence)
    - regulatory capital mechanics (AIRB parameters)
    - feature attribution section (Tier 1)
    - interaction analysis (Tier 2)
    - sensitivity scenarios (counterfactuals)
    - policy knockout status
    - covenant recommendations tied to drivers
    """
    
    # Extract from assessment_findings
    pd_point = findings['pd']['point']
    shap_values = findings['shap']['feature_contributions']
    interactions = findings['shap']['interactions']
    
    # 1. REGULATORY MECHANICS
    rw_percent = calculate_risk_weight(pd, lgd, correlation)
    rwa = exposure * rw_percent
    car_required = rwa * 0.08
    
    # 2. TIER 1: FEATURE ATTRIBUTION
    top_features = sort(shap_values)[:5]
    for feature in top_features:
        write(f"{feature['name']}: {feature['shap_value']*100:.2f}% PD effect")
    
    # 3. TIER 2: INTERACTIONS
    for interaction in interactions:
        pair_names = interaction['feature_pair']
        strength = interaction['interaction_strength']
        write(f"{pair_names[0]} × {pair_names[1]}: {strength*100:.1f}% "
              f"({interaction['type']})")
    
    # 4. SENSITIVITY SCENARIOS
    for scenario in ['deleveraging', 'coverage_improvement']:
        scenario_pd = calculate_pd_if(scenario_conditions)
        scenario_grade = pd_to_grade(scenario_pd)
        write(f"If {scenario}: PD {scenario_pd*100:.2f}%, Grade {scenario_grade}")
    
    # 5. COVENANTS TIED TO DRIVERS
    for feature in top_drivers:
        if feature is leverage:
            write("Covenant: Maximum Debt-to-Equity ≤ 2.0x")
        elif feature is coverage:
            write("Covenant: Minimum Interest Coverage ≥ 3.0x")
    
    return report
```

---

## Example: Final Report Section

```
═══════════════════════════════════════════════════════════════
COMPREHENSIVE CREDIT ASSESSMENT
Borrower: ABC Manufacturing Corp
Date: July 3, 2026
═══════════════════════════════════════════════════════════════

SECTION 1: EXECUTIVE RECOMMENDATION
───────────────────────────────────
Decision: REFER to Credit Committee
Probability of Default: 4.09% (Band: 2.47% - 5.71% at 80% confidence)
Internal Rating: BB (Speculative)
Rationale: Moderate leverage offset by adequate coverage; elevated 
           sensitivity to revenue volatility.

═══════════════════════════════════════════════════════════════

SECTION 2: REGULATORY CAPITAL MECHANICS (BASEL III AIRB)
───────────────────────────────────
Asset Correlation (ρ): 0.15 (per regulatory formula for corporates)
Maturity Adjustment (b): 0.0475 (calculated from PD and formula)
Loss Given Default (LGD): 0.45 (senior unsecured debt)
Exposure at Default (EAD): $5.0M

Risk Weight Calculation:
RW% = [N(√(ρ/(1-ρ)) × G(PD) + √((1-ρ)/ρ) × G(0.999)) - PD] 
       × (1 + (M - 2.5) × b) / 1.06
RW% = 42.8%

Risk-Weighted Assets (RWA): $2,140,000
Capital Required (8% CAR): $171,200

═══════════════════════════════════════════════════════════════

SECTION 3: FEATURE ATTRIBUTION ANALYSIS (SHAP TIER 2)
───────────────────────────────────
Base Case PD (training average): 0.468%
Actual PD (this borrower): 4.09%
Feature-driven increase: 3.62% ✓ (sum of SHAP values validates)

Top Drivers (Tier 1: Importance Ranking):
1. Debt-to-Equity Ratio (importance: 0.0432) → +0.286% PD
2. Current Ratio (importance: 0.0418) → -0.204% PD
3. Net Profit Margin (importance: 0.0397) → +0.048% PD

Key Interaction (Tier 2: SHAP Interaction Analysis):
"D/E × Interest Coverage" (61% strength, MITIGATING)
→ While leverage of 2.5x would alone elevate risk by 0.286%,
  the borrower's interest coverage of 2.5x provides mitigation.
  Combined effect: 0.128% net PD contribution (vs 0.286% alone).

═══════════════════════════════════════════════════════════════

SECTION 4: COVENANT RECOMMENDATIONS
───────────────────────────────────
Based on SHAP driver analysis, recommend:
1. Maximum D/E Ratio ≤ 2.0x (current: 2.5x) [top driver]
2. Minimum Interest Coverage ≥ 3.0x (current: 2.5x) [interaction mitigation]
3. Minimum EBITDA Margin ≥ 9% (current: 8%) [profitability buffer]

Monitoring: Quarterly P&L; annual facility review

═══════════════════════════════════════════════════════════════

SECTION 5: IMPROVEMENT PATHWAY TO UPGRADE
───────────────────────────────────
Current: PD 4.09%, Grade BB
Target: Grade BBB (PD < 2.89%)

Scenario A (RECOMMENDED): Deleveraging
  Target: D/E → 2.0x | Coverage → 3.0x
  Timeline: 18 months
  Implied PD: 2.89% (Grade BBB)
  Feasibility: MEDIUM (requires disciplined capex)
  Effort: Deploy $1.2M debt reduction

═══════════════════════════════════════════════════════════════

SECTION 6: FINAL COMMITTEE DECISION
───────────────────────────────────
APPROVE with conditions:
- Covenant package per Section 4
- Quarterly compliance monitoring
- Annual rating review with deleveraging progress tracking
- Exposure cap: $5.0M (current request)
- Pricing: [110 bps over prime] reflecting BB rating

═══════════════════════════════════════════════════════════════
```

---

## Summary: The Answer to Your Question

**YES—explicitly include SHAP feature attribution because:**

1. **Regulatory Mandate:** Basel III Pillar 2 + SR 11-7 require explainability
2. **Committee Governance:** Non-quants need to understand driver ratios
3. **Risk Management:** Identify concentration risks and monitoring triggers
4. **Covenant Design:** Tie covenants to actual model drivers (not arbitrary)
5. **Fair Lending:** Audit trail proves nondiscriminatory decision logic
6. **Competitive Advantage:** Most banks still don't explain ML-driven decisions well

Your Tier 2 SHAP implementation is exactly what regulators want to see.

---

**Next Step:** Implement the report generation template above into your API output layer to produce regulatory-grade credit committee documents automatically.

