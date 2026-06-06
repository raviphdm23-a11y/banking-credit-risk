"""Machine Learning models directory

This directory stores trained ML models in pickle format (.pkl):
- pd_model.pkl: Trained model for PD prediction
- lgd_model.pkl: Trained model for LGD prediction (future)
- rw_model.pkl: Trained model for Risk Weight prediction (future)

To load a model in Flask:
```python
import joblib
model = joblib.load('ml_models/pd_model.pkl')
prediction = model.predict([features])
```
"""
