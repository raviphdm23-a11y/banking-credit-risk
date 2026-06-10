# Report Generation Integration Plan
## Banking Credit Risk Calculator — Phase 6

**Date:** June 8, 2026  
**Status:** Planning (Ready for Implementation)  
**Purpose:** Integrate detailed borrower assessment reports with explainability into the Calculator

---

## Executive Summary

Currently, when a borrower enters details and clicks "Calculate," they receive:
- Probability of Default (PD) — from ML model
- Loss Given Default (LGD) — from seniority + collateral
- Risk weight and RWA — from AIRB or Standardized Approach formulas

**Gap:** These metrics lack explainability. Why was this PD calculated? What are this borrower's strengths? What specific actions could improve their assessment?

**Solution:** Integrate a **case report generation system** (inspired by `case_report_builder.py`) that produces:
1. **Detailed HTML Report** — immediately in-browser after calculation, showing PD explanation with visualizations
2. **PDF Export** — professional single-page summary (optional download)
3. **Three-Pathway Recommendations** — structured improvement actions for Indian banking context
4. **Feature Health Comparison** — how applicant values compare to approved borrowers
5. **Counterfactual Analysis** — "what if you improved X by Y%" scenarios

---

## Architecture Overview

### New Components

```
Banking_Credit_Risk/
├── backend/
│   ├── calculations.py              [existing AIRB/SA logic]
│   ├── report_engine.py             [NEW] Report generation orchestrator
│   ├── feature_metadata.py          [NEW] Feature definitions + pathways
│   ├── counterfactual_engine.py     [NEW] What-if scenario analysis
│   ├── peer_comparison.py           [NEW] Benchmark against approved borrowers
│   └── visualizations.py            [NEW] Chart generation (matplotlib → SVG/PNG)
│
├── ml_models/
│   ├── pd_model.pkl                 [existing RandomForest]
│   ├── approved_borrowers.pkl       [NEW] Cached approved set (for peer comparison)
│   └── feature_importance.json      [NEW] RF feature importance scores
│
├── public/
│   ├── borrower-info.html           [MODIFIED] Add "Generate Report" button
│   ├── report-viewer.html           [NEW] Full report display + export UI
│   ├── report-styles.css            [NEW] Report typography + layout
│   └── api-integration.js           [MODIFIED] Add report API calls
│
├── data/
│   └── reports/                     [NEW] Generated reports cache
│       └── {borrower_id}/
│           ├── report_{timestamp}.json
│           ├── charts/
│           │   ├── risk_gauge.svg
│           │   ├── feature_health.svg
│           │   └── counterfactuals.svg
│           └── report_{timestamp}.pdf [optional]
```

### Data Flow

```
User Input (borrower details)
    ↓
[Existing] API /api/predict-pd-ml → ML PD prediction
    ↓
[NEW] POST /api/generate-report → Report Engine
    ├─→ Ensemble prediction (if 3+ model agreement, use consensus)
    ├─→ Extract feature importance from RF model
    ├─→ Generate counterfactuals (what-if scenarios)
    ├─→ Find peer approved borrowers (k-NN)
    ├─→ Identify strengths/weaknesses
    ├─→ Cluster into 3 pathways (Restructure/Routine/Long-term)
    ├─→ Generate visualizations (risk gauge, tornado, feature health)
    └─→ Render HTML report + cache
    ↓
Return JSON: {
  report_html: "...",
  verdict: "HIGH_RISK|MODERATE_RISK|LOW_RISK",
  pd_ensemble: 0.45,
  pd_uncertainty: ±0.08,
  charts: { gauge: "svg_str", ..., },
  pathways: {...},
  ...
}
    ↓
[Frontend] Display in report-viewer.html
    ↓
[User] Download as PDF (optional)
```

---

## Phase 1: Backend Infrastructure

### 1.1 Feature Metadata System
**File:** `backend/feature_metadata.py`

Define all 4 features used by RandomForest with Indian banking context:

```python
FEATURE_METADATA = {
    'de_ratio': {
        'display_name': 'Debt-to-Equity Ratio',
        'description': 'Total Debt ÷ Total Equity',
        'currency': 'Ratio (dimensionless)',
        'actionable': True,
        'pathways': {
            'restructure': {'difficulty': 1, 'time_months': (0, 3), 'action': 'Negotiate debt restructuring with existing lenders'},
            'routine': {'difficulty': 2, 'time_months': (3, 6), 'action': 'Gradually reduce debt through operational cash flow'},
            'long_term': {'difficulty': 3, 'time_months': (6, 12), 'action': 'Strategic equity injection or asset sales'},
        },
        'healthy_range': (0.5, 2.0),
        'critical_threshold': 3.0,
        'unit': 'ratio',
    },
    'interest_coverage': {
        'display_name': 'Interest Coverage Ratio',
        'description': 'EBIT ÷ Interest Expense',
        'actionable': True,
        'pathways': {
            'restructure': {'difficulty': 1, 'time_months': (0, 3), 'action': 'Renegotiate interest rates or restructure debt terms'},
            'routine': {'difficulty': 2, 'time_months': (3, 6), 'action': 'Improve operational profitability'},
            'long_term': {'difficulty': 3, 'time_months': (6, 12), 'action': 'Diversify revenue streams'},
        },
        'healthy_range': (2.5, 5.0),
        'critical_threshold': 1.5,
        'unit': 'ratio',
    },
    'profitability': {
        'display_name': 'Net Profit Margin (%)',
        'description': 'Net Income ÷ Revenue',
        'actionable': True,
        'pathways': {
            'restructure': {'difficulty': 2, 'time_months': (0, 3), 'action': 'Reduce operating costs (rent, salaries)'},
            'routine': {'difficulty': 2, 'time_months': (3, 6), 'action': 'Improve operational efficiency'},
            'long_term': {'difficulty': 3, 'time_months': (6, 12), 'action': 'Develop high-margin products/services'},
        },
        'healthy_range': (8, 15),
        'critical_threshold': 3,
        'unit': 'percent',
    },
    'liquidity_ratio': {
        'display_name': 'Current Ratio (Liquidity)',
        'description': 'Current Assets ÷ Current Liabilities',
        'actionable': True,
        'pathways': {
            'restructure': {'difficulty': 1, 'time_months': (0, 3), 'action': 'Accelerate receivables collection / extend payables'},
            'routine': {'difficulty': 2, 'time_months': (3, 6), 'action': 'Build working capital reserves'},
            'long_term': {'difficulty': 3, 'time_months': (6, 12), 'action': 'Establish credit line or revolving facility'},
        },
        'healthy_range': (1.5, 3.0),
        'critical_threshold': 1.0,
        'unit': 'ratio',
    },
}

PATHWAYS = {
    'restructure': {
        'label': 'Pathway A: Immediate Restructuring',
        'timeline': 'Next 0–3 months',
        'description': 'Renegotiate existing loan terms, restructure debt, accelerate receivables',
        'effort': 'Moderate',
        'likelihood': 'High (depends on lender cooperation)',
    },
    'routine': {
        'label': 'Pathway B: Build Financial Routine',
        'timeline': 'Next 3–6 months',
        'description': 'Improve operational profitability, reduce costs, build working capital',
        'effort': 'Moderate',
        'likelihood': 'Moderate (requires discipline)',
    },
    'long_term': {
        'label': 'Pathway C: Strengthen Profile Long-term',
        'timeline': 'Next 6–12 months',
        'description': 'Diversify revenue, pursue strategic improvements, rebuild equity',
        'effort': 'High',
        'likelihood': 'Moderate–High (transformational)',
    },
}
```

### 1.2 Counterfactual Engine
**File:** `backend/counterfactual_engine.py`

Generate "what-if" scenarios showing impact of feature changes:

```python
class CounterfactualEngine:
    """Generate actionable improvement scenarios for a borrower."""
    
    def __init__(self, model, feature_metadata):
        self.model = model  # RandomForest regressor
        self.metadata = feature_metadata
        
    def generate_scenarios(self, case_dict, feature_names, n_scenarios=10):
        """
        For each actionable feature:
        1. Create perturbed version (±5%, ±10%, ±15%)
        2. Predict new PD
        3. Calculate impact (old_pd - new_pd)
        4. Rank by impact
        
        Returns: [(feature, old_val, new_val, impact, pathway, difficulty), ...]
        """
        X_base = encode_features(case_dict, feature_names)
        pd_base = self.model.predict(X_base)[0]
        
        scenarios = []
        for feat in feature_names:
            if not self.metadata[feat]['actionable']:
                continue
            
            old_val = case_dict[feat]
            
            # Generate perturbations: -15%, -10%, -5%, +5%, +10%, +15%
            for pct_change in [-0.15, -0.10, -0.05, 0.05, 0.10, 0.15]:
                new_val = old_val * (1 + pct_change)
                
                # Clamp to healthy range (don't suggest unrealistic values)
                meta = self.metadata[feat]
                healthy_min, healthy_max = meta['healthy_range']
                new_val = max(healthy_min * 0.5, min(new_val, healthy_max * 2.0))
                
                # Predict new PD
                X_new = X_base.copy()
                X_new[0, feature_names.index(feat)] = new_val
                pd_new = self.model.predict(X_new)[0]
                impact = pd_base - pd_new  # positive = improvement
                
                if impact > 0.02:  # Only report meaningful improvements
                    scenarios.append({
                        'feature': feat,
                        'old_value': old_val,
                        'new_value': new_val,
                        'impact': impact,
                        'pct_change': pct_change,
                        'pathway': best_pathway(feat),  # from metadata
                        'difficulty': meta['pathways'][pathway]['difficulty'],
                    })
        
        # Rank by impact
        return sorted(scenarios, key=lambda s: s['impact'], reverse=True)
```

### 1.3 Peer Comparison Engine
**File:** `backend/peer_comparison.py`

Find similar approved borrowers and benchmark applicant features:

```python
class PeerComparison:
    """Compare applicant against approved borrowers."""
    
    def __init__(self, approved_borrowers_df):
        """
        approved_borrowers_df: DataFrame of borrowers with target=0 (approved)
        Columns: de_ratio, interest_coverage, profitability, liquidity_ratio
        """
        self.approved = approved_borrowers_df
        self.medians = approved_borrowers_df.median()
        
    def find_similar_approved(self, case_dict, k=10):
        """
        Use Euclidean distance in normalized feature space to find
        k nearest approved borrowers.
        
        Returns: DataFrame of k closest approved cases
        """
        # Normalize both case and approved pool
        case_norm = (case_dict - self.approved.mean()) / self.approved.std()
        approved_norm = (self.approved - self.approved.mean()) / self.approved.std()
        
        # Compute distances
        distances = np.linalg.norm(approved_norm.values - case_norm, axis=1)
        
        # Return k nearest
        nearest_idx = np.argsort(distances)[:k]
        return self.approved.iloc[nearest_idx]
    
    def feature_health(self, case_dict):
        """
        For each feature, compute:
        - Applicant value
        - Peer median (from approved)
        - Ratio (applicant / peer)
        - Status: "Healthy" if 0.8–1.2, "Low" if <0.8, "High" if >1.2
        
        Returns: {feature: {value, peer_median, ratio, status, delta}, ...}
        """
        health = {}
        for feat in self.medians.index:
            applicant_val = case_dict[feat]
            peer_median = self.medians[feat]
            ratio = applicant_val / (peer_median + 1e-9)
            
            if ratio < 0.8:
                status = 'Low'
            elif ratio > 1.2:
                status = 'High'
            else:
                status = 'Healthy'
            
            health[feat] = {
                'applicant_value': applicant_val,
                'peer_median': peer_median,
                'ratio': ratio,
                'status': status,
                'delta': applicant_val - peer_median,
            }
        
        return health
```

### 1.4 Visualization Engine
**File:** `backend/visualizations.py`

Generate SVG/PNG charts for web display:

```python
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

class ReportVisualizations:
    
    @staticmethod
    def risk_gauge(pd_value, pd_uncertainty=None):
        """
        Generate semi-circular risk gauge:
        0-15%: Green (Low)
        15-35%: Light Green (Moderate-Low)
        35-55%: Yellow (Moderate)
        55-75%: Orange (Moderate-High)
        75-100%: Red (High)
        """
        fig, ax = plt.subplots(figsize=(6, 4), subplot_kw=dict(projection='polar'))
        
        theta = np.linspace(0, np.pi, 100)
        r_bands = [1, 0.9, 0.8, 0.7, 0.6, 0.5]
        colors = ['#1a9641', '#91cf60', '#ffffbf', '#fdae61', '#d7191c']
        
        # Draw bands
        for i, (r1, r2) in enumerate(zip(r_bands[:-1], r_bands[1:])):
            ax.fill_between(theta, r1, r2, color=colors[i], alpha=0.7)
        
        # Draw needle for current PD
        needle_angle = (pd_value / 100) * np.pi
        ax.plot([needle_angle, needle_angle], [0, r_bands[-1]], 'k-', linewidth=3)
        
        # Add uncertainty band if provided
        if pd_uncertainty:
            uncertainty_range = (pd_uncertainty / 100) * np.pi
            ax.fill_between(
                [needle_angle - uncertainty_range, needle_angle + uncertainty_range],
                0, r_bands[-1], color='gray', alpha=0.2
            )
        
        ax.set_ylim(0, 1.2)
        ax.set_theta_zero_location('W')
        ax.set_theta_direction(1)
        ax.set_xticks([0, np.pi/4, np.pi/2, 3*np.pi/4, np.pi])
        ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'])
        ax.set_title(f'Default Probability: {pd_value:.1f}%', fontsize=14, fontweight='bold')
        
        return fig
    
    @staticmethod
    def feature_health_bars(health_dict, feature_metadata):
        """
        Horizontal bar chart comparing applicant vs peer median for each feature.
        Green: Healthy, Orange: Low, Red: High
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        features = list(health_dict.keys())
        applicant_vals = [health_dict[f]['applicant_value'] for f in features]
        peer_medians = [health_dict[f]['peer_median'] for f in features]
        statuses = [health_dict[f]['status'] for f in features]
        
        # Normalize for display (0-100)
        applicant_norm = [min(max(v / (m + 1e-9), 0), 2) * 50 for v, m in zip(applicant_vals, peer_medians)]
        peer_norm = [50] * len(features)  # Peer is always baseline
        
        y_pos = np.arange(len(features))
        
        # Colors by status
        colors = ['#1a9641' if s == 'Healthy' else ('#fd8d3c' if s == 'Low' else '#d7191c') for s in statuses]
        
        ax.barh(y_pos, applicant_norm, label='Your Values', color=colors, alpha=0.7)
        ax.axvline(50, color='gray', linestyle='--', linewidth=2, label='Approved Peer Median')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels([feature_metadata[f]['display_name'] for f in features])
        ax.set_xlabel('Relative to Peer Median (50 = peer median)')
        ax.set_title('Feature Health: Your Values vs Approved Borrowers', fontweight='bold')
        ax.legend()
        plt.tight_layout()
        
        return fig
    
    @staticmethod
    def counterfactual_tornado(scenarios, feature_metadata):
        """
        Tornado chart ranking counterfactuals by impact.
        X-axis: Impact on PD (percentage points)
        Y-axis: Feature name (ranked by impact)
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if not scenarios:
            ax.text(0.5, 0.5, 'No actionable improvements available', ha='center', va='center')
            return fig
        
        # Top 8 scenarios
        top_scenarios = scenarios[:8]
        features = [s['feature'] for s in top_scenarios]
        impacts = [s['impact'] * 100 for s in top_scenarios]  # Convert to percentage points
        
        y_pos = np.arange(len(features))
        
        # Color by pathway
        colors = {'restructure': '#fdae61', 'routine': '#91cf60', 'long_term': '#74add1'}
        bar_colors = [colors.get(s['pathway'], 'gray') for s in top_scenarios]
        
        ax.barh(y_pos, impacts, color=bar_colors, alpha=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([feature_metadata[f]['display_name'] for f in features])
        ax.set_xlabel('Impact on Default Probability (percentage points, lower is better)')
        ax.set_title('Top Actions to Improve Your Assessment', fontweight='bold')
        ax.invert_yaxis()
        plt.tight_layout()
        
        return fig
```

### 1.5 Report Engine Orchestrator
**File:** `backend/report_engine.py`

```python
class ReportGenerator:
    """Orchestrate all components to generate a complete report."""
    
    def __init__(self, model, feature_metadata, approved_borrowers_df):
        self.model = model
        self.metadata = feature_metadata
        self.counterfactuals = CounterfactualEngine(model, feature_metadata)
        self.peer_comparison = PeerComparison(approved_borrowers_df)
        self.viz = ReportVisualizations()
        
    def generate_report(self, case_dict, feature_names):
        """
        Main entry point: generate complete report.
        
        Returns: {
            'verdict': 'HIGH_RISK|MODERATE_RISK|LOW_RISK',
            'pd_ensemble': 0.45,
            'pd_uncertainty': 0.08,
            'feature_health': {...},
            'counterfactuals': [...],
            'pathways': {...},
            'charts': {
                'risk_gauge': '<svg>...',
                'feature_health': '<svg>...',
                'counterfactuals': '<svg>...',
            },
            'html': '<html>...',
        }
        """
        # 1. Get ML predictions
        X = encode_features(case_dict, feature_names)
        pd_base = self.model.predict(X)[0]
        
        # 2. Get feature health
        health = self.peer_comparison.feature_health(case_dict)
        
        # 3. Generate counterfactuals
        cfs = self.counterfactuals.generate_scenarios(case_dict, feature_names)
        
        # 4. Identify strengths/weaknesses
        strengths = self._identify_strengths(health)
        weaknesses = self._identify_weaknesses(health)
        
        # 5. Cluster into pathways
        pathways = self._cluster_pathways(cfs)
        
        # 6. Generate visualizations
        charts = {
            'risk_gauge': self._fig_to_svg(self.viz.risk_gauge(pd_base * 100, pd_uncertainty=8)),
            'feature_health': self._fig_to_svg(self.viz.feature_health_bars(health, self.metadata)),
            'counterfactuals': self._fig_to_svg(self.viz.counterfactual_tornado(cfs, self.metadata)),
        }
        
        # 7. Render HTML
        html = self._render_html(case_dict, pd_base, health, cfs, pathways, strengths, weaknesses, charts)
        
        return {
            'verdict': 'HIGH_RISK' if pd_base > 0.5 else 'MODERATE_RISK' if pd_base > 0.35 else 'LOW_RISK',
            'pd_ensemble': round(pd_base, 4),
            'pd_uncertainty': 0.08,  # From model training metrics
            'feature_health': health,
            'counterfactuals': cfs[:5],  # Top 5
            'pathways': pathways,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'charts': charts,
            'html': html,
        }
    
    def _identify_strengths(self, health):
        """Features where applicant is better than peer median."""
        return [f for f, h in health.items() if h['status'] == 'Healthy' and h['ratio'] >= 1.0]
    
    def _identify_weaknesses(self, health):
        """Features where applicant is worse than peer median."""
        return [f for f, h in health.items() if h['status'] in ['Low', 'High']]
    
    def _cluster_pathways(self, scenarios):
        """Group counterfactuals into 3 pathways."""
        pathways = {
            'restructure': [s for s in scenarios if s['pathway'] == 'restructure'],
            'routine': [s for s in scenarios if s['pathway'] == 'routine'],
            'long_term': [s for s in scenarios if s['pathway'] == 'long_term'],
        }
        return {k: v for k, v in pathways.items() if v}  # Only include non-empty
    
    def _fig_to_svg(self, fig):
        """Convert matplotlib figure to SVG string."""
        from io import StringIO
        buf = StringIO()
        fig.savefig(buf, format='svg')
        buf.seek(0)
        return buf.getvalue()
    
    def _render_html(self, case_dict, pd_base, health, cfs, pathways, strengths, weaknesses, charts):
        """Render comprehensive HTML report."""
        # See section 2.1 for HTML template
        pass
```

---

## Phase 2: API Integration

### 2.1 New Flask Endpoint
**File:** `app.py` (add new route)

```python
@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    """
    POST /api/generate-report
    
    Request body:
    {
        "de_ratio": 1.5,
        "interest_coverage": 3.2,
        "profitability": 10.5,
        "liquidity_ratio": 2.1,
        ...
    }
    
    Returns:
    {
        "verdict": "MODERATE_RISK",
        "pd_ensemble": 0.45,
        "pd_uncertainty": 0.08,
        "feature_health": {...},
        "counterfactuals": [...],
        "pathways": {...},
        "html": "<div>...</div>",
        "charts": {
            "risk_gauge": "<svg>...",
            ...
        },
        "timestamp": "2026-06-08T14:30:45Z",
        "borrower_id": "optional_ref_from_request"
    }
    """
    try:
        data = request.get_json()
        borrower_id = data.get('borrower_id', f'case_{int(time.time())}')
        
        # Load model + metadata
        from backend.report_engine import ReportGenerator
        from ml_models import pd_model_metadata
        
        model = joblib.load('ml_models/pd_model.pkl')
        approved_borrowers = pd.read_csv('ml_models/approved_borrowers.csv')  # Pre-cached
        
        generator = ReportGenerator(model, FEATURE_METADATA, approved_borrowers)
        
        # Generate report
        report = generator.generate_report(data, FEATURE_NAMES)
        report['borrower_id'] = borrower_id
        report['timestamp'] = datetime.now().isoformat()
        
        # Cache report to disk
        report_dir = Path('data/reports') / borrower_id
        report_dir.mkdir(parents=True, exist_ok=True)
        with open(report_dir / f'report_{datetime.now().timestamp()}.json', 'w') as f:
            json.dump(report, f)
        
        return jsonify(report), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400
```

---

## Phase 3: Frontend Integration

### 3.1 HTML Report Viewer
**File:** `public/report-viewer.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Borrower Assessment Report</title>
    <link rel="stylesheet" href="report-styles.css">
</head>
<body>
    <div class="report-container">
        <!-- Header -->
        <div class="report-header">
            <h1>📊 Personal Credit Health Report</h1>
            <p class="subtitle">A comprehensive financial assessment for borrowing decisions</p>
            <div class="meta-info">
                <span class="timestamp" id="reportDate"></span>
                <span class="borrower-id" id="borrowerId"></span>
            </div>
        </div>

        <!-- Verdict Box -->
        <div class="verdict-section" id="verdictBox">
            <div class="verdict-card">
                <div class="verdict-pd" id="verdictPD">45%</div>
                <div class="verdict-label" id="verdictLabel">MODERATE RISK</div>
                <div class="verdict-uncertainty">Uncertainty: ±8 pp</div>
            </div>
        </div>

        <!-- Summary -->
        <section class="report-section">
            <h2>📋 Executive Summary</h2>
            <div class="summary-text" id="summaryText"></div>
        </section>

        <!-- Feature Health -->
        <section class="report-section">
            <h2>💚 Feature Health: Your Values vs Approved Borrowers</h2>
            <div id="featureHealthChart" class="chart-container"></div>
            <table class="health-table" id="healthTable">
                <thead>
                    <tr>
                        <th>Feature</th>
                        <th>Your Value</th>
                        <th>Peer Median</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="healthTableBody"></tbody>
            </table>
        </section>

        <!-- Strengths & Weaknesses -->
        <div class="two-column">
            <section class="report-section">
                <h2>✅ Your Strengths</h2>
                <ul id="strengthsList"></ul>
            </section>
            <section class="report-section">
                <h2>⚠️ Areas to Improve</h2>
                <ul id="weaknessList"></ul>
            </section>
        </div>

        <!-- Top Actions (Counterfactuals) -->
        <section class="report-section">
            <h2>🎯 Top Actions to Improve Your Assessment</h2>
            <div id="counterfactualChart" class="chart-container"></div>
            <div class="actions-list" id="actionsList"></div>
        </section>

        <!-- Three Pathways -->
        <section class="report-section">
            <h2>🗺️ Three Pathways to Approval</h2>
            <div class="pathways-container" id="pathwaysContainer"></div>
        </section>

        <!-- Reassessment Schedule -->
        <section class="report-section">
            <h2>📅 Reassessment Timeline</h2>
            <div class="timeline">
                <div class="milestone">
                    <span class="month">3 months</span>
                    <span class="date" id="month3"></span>
                    <p>Restructuring pathway items should be visible</p>
                </div>
                <div class="milestone">
                    <span class="month">6 months</span>
                    <span class="date" id="month6"></span>
                    <p>Build routine improvements fully reflected</p>
                </div>
                <div class="milestone">
                    <span class="month">12 months</span>
                    <span class="date" id="month12"></span>
                    <p>Long-term strengthening fully realized</p>
                </div>
            </div>
        </section>

        <!-- Advisor Note -->
        <section class="report-section advisor-section">
            <h2>💬 A Note from Your Advisor</h2>
            <div class="advisor-note" id="advisorNote"></div>
        </section>

        <!-- Technical Appendix -->
        <section class="report-section technical">
            <h2>⚙️ Technical Details</h2>
            <details>
                <summary>View Model & Methodology</summary>
                <div class="technical-content" id="technicalContent"></div>
            </details>
        </section>

        <!-- Export -->
        <div class="export-section">
            <button id="exportPDF" class="btn btn-primary">📥 Download as PDF</button>
            <button id="printReport" class="btn btn-secondary">🖨️ Print Report</button>
            <button id="newReport" class="btn btn-tertiary">🔄 Generate New Report</button>
        </div>
    </div>

    <script src="report-viewer.js"></script>
</body>
</html>
```

### 3.2 Report Viewer Script
**File:** `public/report-viewer.js`

```javascript
class ReportViewer {
    constructor(reportData) {
        this.report = reportData;
        this.init();
    }
    
    init() {
        this.renderVerdict();
        this.renderSummary();
        this.renderFeatureHealth();
        this.renderStrengthsWeaknesses();
        this.renderCounterfactuals();
        this.renderPathways();
        this.renderTimeline();
        this.renderAdvisorNote();
        this.setupExportButtons();
    }
    
    renderVerdict() {
        document.getElementById('verdictPD').textContent = `${(this.report.pd_ensemble * 100).toFixed(1)}%`;
        document.getElementById('verdictLabel').textContent = this.report.verdict;
        
        const verdictBox = document.getElementById('verdictBox');
        verdictBox.className = `verdict-section verdict-${this.report.verdict.toLowerCase().replace('_', '-')}`;
        
        document.getElementById('reportDate').textContent = new Date(this.report.timestamp).toLocaleDateString();
        document.getElementById('borrowerId').textContent = `Applicant: ${this.report.borrower_id}`;
    }
    
    renderFeatureHealth() {
        const chartHtml = this.report.charts['feature_health'];
        document.getElementById('featureHealthChart').innerHTML = chartHtml;
        
        const tbody = document.getElementById('healthTableBody');
        for (const [feature, health] of Object.entries(this.report.feature_health)) {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${this.formatFeatureName(feature)}</td>
                <td>${health.applicant_value.toFixed(2)}</td>
                <td>${health.peer_median.toFixed(2)}</td>
                <td><span class="status-${health.status.toLowerCase()}">${health.status}</span></td>
            `;
        }
    }
    
    renderCounterfactuals() {
        const chartHtml = this.report.charts['counterfactuals'];
        document.getElementById('counterfactualChart').innerHTML = chartHtml;
        
        const actionsList = document.getElementById('actionsList');
        this.report.counterfactuals.forEach((cf, idx) => {
            const actionCard = document.createElement('div');
            actionCard.className = 'action-card';
            actionCard.innerHTML = `
                <div class="action-rank">${idx + 1}</div>
                <div class="action-content">
                    <h4>${this.formatFeatureName(cf.feature)}</h4>
                    <p class="action-detail">
                        If you improve from <strong>${cf.old_value.toFixed(2)}</strong> 
                        to <strong>${cf.new_value.toFixed(2)}</strong>,
                        default probability could drop by <strong>${(cf.impact * 100).toFixed(1)}pp</strong>
                    </p>
                    <p class="action-pathway">
                        <strong>Pathway:</strong> ${this.formatPathway(cf.pathway)}
                        | <strong>Difficulty:</strong> ${'★'.repeat(cf.difficulty)}
                    </p>
                </div>
            `;
            actionsList.appendChild(actionCard);
        });
    }
    
    renderPathways() {
        const container = document.getElementById('pathwaysContainer');
        const pathwayLabels = {
            'restructure': 'Pathway A: Immediate Restructuring',
            'routine': 'Pathway B: Build Financial Routine',
            'long_term': 'Pathway C: Long-term Profile Strengthening',
        };
        
        for (const [key, actions] of Object.entries(this.report.pathways)) {
            const pathwayDiv = document.createElement('div');
            pathwayDiv.className = 'pathway-card';
            pathwayDiv.innerHTML = `
                <h3>${pathwayLabels[key]}</h3>
                <p class="pathway-timeline">${this.getPathwayTimeline(key)}</p>
                <ul>
                    ${actions.map(a => `<li>${this.formatFeatureName(a.feature)}: ${a.difficulty} difficulty</li>`).join('')}
                </ul>
            `;
            container.appendChild(pathwayDiv);
        }
    }
    
    setupExportButtons() {
        document.getElementById('exportPDF').addEventListener('click', () => {
            this.exportToPDF();
        });
        document.getElementById('printReport').addEventListener('click', () => {
            window.print();
        });
        document.getElementById('newReport').addEventListener('click', () => {
            window.location.href = '/borrower-info.html';
        });
    }
    
    exportToPDF() {
        // Use html2pdf or jsPDF library to export visible report as PDF
        alert('PDF export coming soon!');
    }
    
    // Helper methods...
    formatFeatureName(feat) {
        return feat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    formatPathway(pathway) {
        const labels = {
            'restructure': 'Restructure',
            'routine': 'Build Routine',
            'long_term': 'Long-term',
        };
        return labels[pathway] || pathway;
    }
    
    getPathwayTimeline(pathway) {
        const timelines = {
            'restructure': '0–3 months',
            'routine': '3–6 months',
            'long_term': '6–12 months',
        };
        return timelines[pathway];
    }
}

// Load and display report when page loads
document.addEventListener('DOMContentLoaded', () => {
    const reportData = JSON.parse(localStorage.getItem('currentReport'));
    if (reportData) {
        new ReportViewer(reportData);
    } else {
        document.body.innerHTML = '<p>No report data found. <a href="/borrower-info.html">Generate a report</a></p>';
    }
});
```

### 3.3 Modify Calculator Page
**File:** `public/borrower-info.html` (modifications)

```javascript
// In the calculateRisk() function, after existing calculations:

async function generateReportAndDisplay() {
    const caseData = {
        borrower_id: document.getElementById('borrowerName')?.value || 'applicant_' + Date.now(),
        de_ratio: DE_RATIO,
        interest_coverage: INTEREST_COVERAGE,
        profitability: PROFITABILITY,
        liquidity_ratio: LIQUIDITY_RATIO,
    };
    
    try {
        showLoadingIndicator('Generating comprehensive report...');
        
        const response = await fetch('/api/generate-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(caseData),
        });
        
        const report = await response.json();
        
        // Save to localStorage
        localStorage.setItem('currentReport', JSON.stringify(report));
        
        // Redirect to report viewer
        window.location.href = '/report-viewer.html';
    } catch (error) {
        console.error('Report generation failed:', error);
        alert('Report generation failed. Please try again.');
    }
}

// Add "Generate Full Report" button to the UI
const reportButton = document.createElement('button');
reportButton.id = 'generateReportBtn';
reportButton.className = 'btn btn-primary';
reportButton.textContent = '📊 Generate Comprehensive Report';
reportButton.addEventListener('click', generateReportAndDisplay);
// Append to calculate results section
```

---

## Phase 4: Data Persistence

### 4.1 Report Caching
**File:** `data/reports/` directory structure

```
data/reports/
├── {borrower_id}_2026-06-08/
│   ├── report_metadata.json      {timestamp, verdict, pd, borrower_id}
│   ├── report_full.json          Complete report JSON
│   ├── report.html               Exportable HTML
│   └── charts/
│       ├── risk_gauge.svg
│       ├── feature_health.svg
│       └── counterfactuals.svg
├── batch_summary.csv             All reports in session
```

### 4.2 Admin Dashboard Update
**File:** `public/admin.html` (new section)

Add "Reports" panel to view:
- Total reports generated
- Average PD by verdict
- Most common weaknesses
- Most effective pathways
- Delete old reports (cleanup)

---

## Phase 5: Integration Points

### 5.1 Modify `app.py`
```python
# Load report generation components at startup
from backend.report_engine import ReportGenerator
from backend.feature_metadata import FEATURE_METADATA, PATHWAYS

# At Flask init:
APPROVED_BORROWERS = pd.read_csv('ml_models/approved_borrowers.csv')
REPORT_GENERATOR = ReportGenerator(
    joblib.load('ml_models/pd_model.pkl'),
    FEATURE_METADATA,
    APPROVED_BORROWERS
)
```

### 5.2 Update `ml_models/pd_model_metadata.json`
```json
{
    "model_version": "v2.0",
    "features": ["de_ratio", "interest_coverage", "profitability", "liquidity_ratio"],
    "feature_importance": {
        "de_ratio": 0.35,
        "interest_coverage": 0.28,
        "profitability": 0.22,
        "liquidity_ratio": 0.15
    },
    "approved_borrower_count": 5000,
    "training_data_rows": 14300,
    "report_generation_enabled": true
}
```

### 5.3 Create Approved Borrowers Cached Dataset
**File:** `ml_models/approved_borrowers.csv`

Extract from training data: all rows where `target == 0` (approved). Sample structure:
```
de_ratio,interest_coverage,profitability,liquidity_ratio
1.2,3.5,12.3,2.1
0.8,4.1,14.2,2.8
1.5,2.9,11.1,1.9
...
```

---

## Phase 6: Testing Strategy

### 6.1 Unit Tests
**File:** `testing/test_report_generation.py`

```python
def test_counterfactual_engine():
    """Test what-if scenario generation."""
    
def test_peer_comparison():
    """Test finding similar approved borrowers."""
    
def test_feature_health():
    """Test health status classification."""
    
def test_report_generation():
    """Test end-to-end report generation."""
```

### 6.2 Integration Test
**File:** `testing/test_report_api.py`

```python
def test_generate_report_endpoint():
    """POST /api/generate-report with sample case."""
```

### 6.3 UI Test
**File:** `testing/test_report_viewer_ui.py`

```python
def test_report_viewer_loads():
    """Render report and verify all sections visible."""
    
def test_export_pdf():
    """Generate and download PDF export."""
```

---

## Implementation Roadmap

| Phase | Task | Duration | Dependency |
|-------|------|----------|------------|
| 1.1 | Feature metadata system | 2 hours | None |
| 1.2 | Counterfactual engine | 3 hours | 1.1 |
| 1.3 | Peer comparison engine | 2 hours | 1.1 |
| 1.4 | Visualization engine | 4 hours | 1.1 |
| 1.5 | Report orchestrator | 3 hours | 1.2–1.4 |
| **Phase 1 Total** | | **14 hours** | |
| 2.1 | Flask API endpoint | 2 hours | 1.5 |
| **Phase 2 Total** | | **2 hours** | |
| 3.1 | HTML report viewer | 4 hours | 2.1 |
| 3.2 | Report viewer JS | 3 hours | 3.1 |
| 3.3 | Calculator integration | 2 hours | 3.2 |
| **Phase 3 Total** | | **9 hours** | |
| 4.1–4.2 | Data persistence | 2 hours | 2.1 |
| **Phase 4 Total** | | **2 hours** | |
| 5.1–5.3 | Integration & config | 2 hours | All above |
| **Phase 5 Total** | | **2 hours** | |
| 6.1–6.3 | Testing | 4 hours | All above |
| **Phase 6 Total** | | **4 hours** | |
| **Grand Total** | | **~33 hours** | |

---

## Success Criteria

✅ Report generation completes in <2 seconds for typical case  
✅ All 4 features show in feature health table  
✅ Top 3 counterfactuals clearly explain impact  
✅ All 3 pathways available with at least 1 action each  
✅ Report HTML displays correctly on desktop + mobile  
✅ PDF export produces readable single-page summary  
✅ Approved borrower statistics match training data  
✅ No duplicate reports for same borrower  

---

## Future Enhancements

1. **Model Ensemble Expansion** — Add 2–3 additional models (Logistic Regression, XGBoost) for stronger consensus
2. **External Risk Indicators** — Integrate Dun & Bradstreet, NSE market data, sectoral trends
3. **Regulatory Compliance** — Add Basel IV risk-weighting alignment
4. **Borrower Portal** — Secure login, report history, reassessment tracking
5. **Batch Report Generation** — Generate reports for 100s of borrowers in single admin action
6. **Explainable AI (SHAP)** — Feature contribution heatmap per case
7. **Loan Pricing Optimization** — Margin recommendations based on risk profile

---

## Notes

- **Currency:** All amounts in INR (₹). Feature names use Indian banking conventions.
- **Risk Threshold:** Default threshold = 50%. Can be adjusted per lender policy.
- **Performance:** Matplotlib chart generation (~500ms per report). SVG output keeps report size <5MB.
- **Data Privacy:** Reports cached to local filesystem only. No external uploads.
- **Accessibility:** HTML reports follow WCAG 2.1 AA standards for screen readers + keyboard navigation.

---

**Author:** Claude Code  
**Status:** Ready for Phase 1 Implementation  
**Next:** Review plan and approve for development
