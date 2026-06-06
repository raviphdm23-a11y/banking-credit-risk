# Architecture Recommendations - Machine Learning Integration

**Date:** June 3, 2026  
**Status:** For Implementation (Starting Tomorrow)  
**Owner:** ravi_phdm23@iift.edu

---

## Executive Summary

**Decision:** Migrate from Pure HTML to **Flask + HTML (Phase 1)** → **React + Flask (Phase 2)**

**Why:** To support Python-based machine learning models (pickle files) and ensure scalability for future growth.

---

## Current State Analysis

### Limitations of Pure HTML Approach
- ❌ Cannot execute Python code in browser
- ❌ Cannot load pickle ML models directly
- ❌ No server-side processing capability
- ❌ Limited scalability for multiple users
- ❌ All logic must be JavaScript (complex for ML)

### Current Strengths to Preserve
- ✅ Simple, no server deployment needed
- ✅ Works offline (file:// protocol)
- ✅ Fast user experience
- ✅ Easy to understand and modify

---

## Recommended Architecture

### Phase 1: Flask + HTML Backend (Timeline: Next 3-6 months)

```
┌─────────────────────────────────────────┐
│         Frontend Layer                   │
│  HTML/CSS/JavaScript (borrower-info.html)│
│  - User forms and interface              │
│  - Data input validation                 │
│  - Results display                       │
└────────────┬──────────────────────────────┘
             │ API Calls (JSON)
             ↓
┌─────────────────────────────────────────┐
│         Backend Layer (Flask)             │
│  Python Flask Application                │
│  ├─ Rule-based PD calculation endpoint   │
│  ├─ ML Model PD prediction endpoint      │
│  ├─ LGD calculation endpoint             │
│  ├─ Risk weight lookup endpoint          │
│  ├─ Portfolio management                │
│  └─ Data persistence (SQLite/PostgreSQL)│
└─────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│    Machine Learning Layer                │
│  ├─ Pickle model files (.pkl)           │
│  ├─ Model predictions                   │
│  ├─ Model retraining pipeline           │
│  └─ Model versioning                    │
└─────────────────────────────────────────┘
```

**Benefits:**
- ✅ Python native environment for ML
- ✅ Direct pickle file loading
- ✅ Server-side processing
- ✅ Data persistence
- ✅ Multiple user support
- ✅ Easy model deployment
- ✅ Minimal frontend changes

---

### Phase 2: React + Flask Backend (Timeline: 6-12 months, as needed)

```
┌─────────────────────────────────────────┐
│         Frontend Layer                   │
│  React Application                       │
│  - Modern component architecture         │
│  - Better state management               │
│  - Enhanced UX/UX                        │
│  - Real-time updates                     │
└────────────┬──────────────────────────────┘
             │ REST API / GraphQL
             ↓
┌─────────────────────────────────────────┐
│      Backend Layer (Flask/FastAPI)       │
│  (Same as Phase 1, enhanced)             │
│  ├─ All Phase 1 endpoints                │
│  ├─ WebSocket support (optional)         │
│  ├─ Database integration                 │
│  └─ Authentication/Authorization         │
└─────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│    Machine Learning Layer                │
│  (Same as Phase 1)                       │
└─────────────────────────────────────────┘
```

**Benefits:**
- ✅ All Phase 1 benefits
- ✅ Professional, scalable frontend
- ✅ Better maintainability
- ✅ Team-friendly architecture
- ✅ Enterprise-ready

---

## Technology Comparison

| Aspect | Flask + HTML | FastAPI + HTML | React + Flask | Pure HTML |
|--------|---|---|---|---|
| **ML Integration** | ✅ Easy | ✅✅ Easy | ✅ Easy | ❌ Impossible |
| **Python Support** | ✅✅ Native | ✅✅ Native | ✅✅ Native | ❌ None |
| **Scalability** | ✅ Good | ✅✅ Better | ✅✅ Excellent | ❌ Limited |
| **Complexity** | ✅ Low | ⚠️ Medium | ⚠️ Medium | ✅ Lowest |
| **Setup Time** | ✅ 2-3 hrs | ⚠️ 4-5 hrs | ⚠️ 8-10 hrs | ✅ Already done |
| **ML Models** | ✅ Supported | ✅ Supported | ✅ Supported | ❌ Not supported |
| **Future-Proof** | ✅ Yes | ✅✅ Yes | ✅✅ Yes | ❌ No |
| **Team Ready** | ✅ Yes | ✅ Yes | ✅✅ Yes | ⚠️ Limited |
| **Deployment** | ✅ Simple | ✅ Simple | ⚠️ Moderate | ✅ Simplest |

**Recommendation:** **FLASK + HTML** (Phase 1 Now, React later if needed)

---

## Implementation Plan

### Phase 1: Flask Backend Setup (This Week)

**Step 1: Create Flask Project Structure**
```
banking-credit-risk/
├── app.py                          # Flask application
├── requirements.txt                # Python dependencies
├── config.py                       # Configuration
├── ml_models/
│   ├── pd_model.pkl               # (Future) ML model
│   └── __init__.py
├── backend/
│   ├── calculations.py            # Calculation logic
│   ├── database.py                # Database models
│   └── __init__.py
├── public/                         # Static HTML/CSS/JS (existing)
│   ├── borrower-info.html
│   └── ...
└── tests/                          # Unit tests
```

**Step 2: Migrate Calculation Logic**
- Move PD calculation from JavaScript → Python function
- Move LGD calculation from JavaScript → Python function
- Move RWA calculation from JavaScript → Python function
- Create Flask API endpoints for each

**Step 3: Create API Endpoints**
```python
POST /api/calculate-pd
POST /api/calculate-lgd
POST /api/calculate-rwa
GET /api/portfolio
POST /api/add-loan
```

**Step 4: Update HTML to Call Flask**
- Replace JavaScript calculations with API calls
- Keep UI/Form logic in HTML
- Display results from API responses

**Effort:** ~2-3 hours  
**Complexity:** Low  
**Risk:** Minimal (Flask is simple, non-breaking changes)

---

### Phase 2: Machine Learning Integration (Future)

**When Ready:**
1. Train ML model for PD prediction
2. Export as pickle file (`.pkl`)
3. Add to `ml_models/` folder
4. Create Flask endpoint: `POST /api/predict-pd-ml`
5. Update HTML to offer ML vs Rule-based option

**Example:**
```python
# Flask endpoint
@app.route('/api/predict-pd-ml', methods=['POST'])
def predict_pd_ml():
    data = request.json
    
    # Load trained model
    model = joblib.load('ml_models/pd_model.pkl')
    
    # Prepare features
    features = prepare_features(data)
    
    # Get prediction
    pd_prediction = model.predict([features])[0]
    
    return jsonify({'pd': pd_prediction})
```

---

### Phase 3: React Migration (12+ months, optional)

**When:**
- Frontend complexity outgrows HTML
- Need real-time updates
- Building team of developers
- Want modern architecture

**Approach:**
- Create React app (create-react-app or Vite)
- Keep Flask backend unchanged
- Migrate components one by one
- No disruption to backend

---

## Risk Assessment & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| Migration breaks existing HTML | High | Low | Keep original HTML, test thoroughly |
| Flask setup complexity | Medium | Low | Use templates, documentation |
| Database migration | Medium | Low | Use SQLite initially, upgrade later |
| ML model performance | Medium | Medium | Validate model accuracy before deployment |
| Backward compatibility | Medium | Low | API versioning, gradual rollout |

---

## Technology Stack (Recommended)

### Phase 1: Flask + HTML
- **Backend:** Flask 2.x (Python 3.9+)
- **Database:** SQLite (simple) or PostgreSQL (production)
- **Frontend:** HTML/CSS/JavaScript (existing)
- **Package Management:** pip + requirements.txt
- **ML Framework:** scikit-learn, pandas (for model training)
- **Serialization:** joblib or pickle

**Dependencies:**
```
Flask==2.3.x
Flask-CORS==4.0.x
SQLAlchemy==2.0.x
pandas==2.0.x
scikit-learn==1.3.x
joblib==1.3.x
```

### Phase 2: React + Flask (Future)
- **Frontend:** React 18.x
- **Build Tool:** Vite or Create React App
- **State Management:** Redux or Zustand
- **Backend:** Flask (same as Phase 1)
- **API:** REST or GraphQL

---

## Deployment Strategy

### Phase 1: Flask Development → Production
1. **Development:** `flask run` (localhost:5000)
2. **Testing:** Unit tests + integration tests
3. **Staging:** Deploy to staging server
4. **Production:** 
   - Option A: Heroku (simple, free tier available)
   - Option B: AWS EC2 (more control)
   - Option C: Docker container

### Phase 2: React + Flask
- Both frontend and backend in Docker containers
- Docker Compose for local development
- Kubernetes for production scaling (if needed)

---

## Next Steps (Starting Tomorrow)

### Day 1-2: Setup
- [ ] Install Flask and dependencies
- [ ] Create project structure
- [ ] Set up Git repository
- [ ] Create requirements.txt

### Day 3-4: Migration
- [ ] Move PD calculation to Python
- [ ] Move LGD calculation to Python
- [ ] Move RWA calculation to Python
- [ ] Create Flask API endpoints

### Day 5-7: Integration
- [ ] Update HTML to call Flask APIs
- [ ] Test all calculations
- [ ] Verify results match original
- [ ] Fix any issues

### Week 2+: Testing & Refinement
- [ ] Add unit tests
- [ ] Performance optimization
- [ ] Documentation
- [ ] Production deployment

---

## Resources & Documentation

**Flask Learning:**
- Official Flask documentation: https://flask.palletsprojects.com/
- Flask Tutorial: https://flask.palletsprojects.com/tutorial/
- Flask API Guide: https://flask.palletsprojects.com/api/

**ML Integration:**
- scikit-learn: https://scikit-learn.org/
- joblib for model persistence: https://joblib.readthedocs.io/
- Model deployment: https://www.datacamp.com/

**Architecture References:**
- Flask best practices: https://flask.palletsprojects.com/patterns/
- RESTful API design: https://www.restfulapi.net/

---

## FAQ

**Q: Will this break the current HTML application?**
A: No. Flask will serve the HTML while handling calculations in the backend.

**Q: Can I test locally?**
A: Yes. Run Flask locally (`flask run`), all features work the same.

**Q: How do I deploy Flask?**
A: Multiple options: Heroku (easiest), AWS, Docker, VPS. Heroku recommended for quick start.

**Q: What about the reference_data.xlsx?**
A: Flask will load it for dropdown validation. Can also migrate to database later.

**Q: Can I still use the current test suite?**
A: Yes, tests will call Flask API endpoints instead of JavaScript functions.

**Q: Timeline to ML integration?**
A: Framework ready in 1-2 weeks. ML model integration depends on model training timeline.

---

## Decision Log

**Decision:** Approve Flask + HTML architecture  
**Rationale:** 
- Supports future ML requirements
- Minimal disruption to current code
- Clear path to React migration
- Professional, scalable approach

**Alternative Considered:** Pure HTML with WebAssembly (REJECTED - too complex)

---

**Document Version:** 1.0  
**Last Updated:** June 3, 2026  
**Status:** Ready for Implementation  
**Owner:** Development Team

---

**Start tomorrow with Day 1-2 setup. Good luck! 🚀**
