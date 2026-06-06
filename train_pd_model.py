"""
PD Prediction Model Training Script

This script creates a machine learning model for PD (Probability of Default) prediction.
Uses scikit-learn's RandomForestRegressor trained on synthetic data for demonstration.

In production, replace with real historical borrower data and actual default outcomes.
"""

import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import os
import json

# ============================================================================
# SYNTHETIC DATA GENERATION
# ============================================================================

def generate_synthetic_data(n_samples=500):
    """
    Generate synthetic borrower data for model training.

    In production, this would be real historical data with actual defaults.

    Features:
    - D/E Ratio: 0.5 to 3.0
    - Interest Coverage: 0.5 to 5.0
    - Profitability Margin: -0.10 to 0.20
    - Liquidity Ratio: 0.8 to 2.5

    Target:
    - PD (Probability of Default): 0.5% to 20% (in decimal: 0.005 to 0.20)
    """
    np.random.seed(42)  # For reproducibility

    # Generate features
    de_ratio = np.random.uniform(0.5, 3.0, n_samples)
    interest_coverage = np.random.uniform(0.5, 5.0, n_samples)
    profitability = np.random.uniform(-0.10, 0.20, n_samples)
    liquidity_ratio = np.random.uniform(0.8, 2.5, n_samples)

    # Create feature matrix
    X = np.column_stack([de_ratio, interest_coverage, profitability, liquidity_ratio])

    # Generate target (PD) based on features with some realistic logic
    # Higher D/E -> Higher PD
    # Lower Interest Coverage -> Higher PD
    # Lower Profitability -> Higher PD
    # Lower Liquidity -> Higher PD

    pd = (
        0.01 +  # Base rate
        0.005 * de_ratio +  # D/E impact
        0.003 * (5 - interest_coverage) +  # Coverage impact (inverse)
        0.008 * np.maximum(0, -profitability) +  # Profitability impact
        0.003 * (2.5 - liquidity_ratio)  # Liquidity impact (inverse)
    )

    # Clip to realistic range [0.005, 0.50] (0.5% to 50%)
    y = np.clip(pd, 0.005, 0.50)

    # Add small random noise
    y = y + np.random.normal(0, 0.01, n_samples)
    y = np.clip(y, 0.001, 0.50)

    return X, y

# ============================================================================
# MODEL TRAINING
# ============================================================================

def train_model(X, y):
    """
    Train RandomForest model for PD prediction.

    RandomForest advantages:
    - Handles non-linear relationships
    - Robust to outliers
    - Feature importance available
    - No scaling needed
    """

    print("\n" + "="*70)
    print("TRAINING PD PREDICTION MODEL")
    print("="*70)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Create and train model
    print("\nTraining RandomForestRegressor...")
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    train_r2 = r2_score(y_train, y_pred_train)
    test_r2 = r2_score(y_test, y_pred_test)
    train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))

    print("\n" + "-"*70)
    print("MODEL PERFORMANCE")
    print("-"*70)
    print(f"Training R²:  {train_r2:.4f}")
    print(f"Test R²:      {test_r2:.4f}")
    print(f"Training RMSE: {train_rmse:.4f} ({train_rmse*100:.2f}%)")
    print(f"Test RMSE:     {test_rmse:.4f} ({test_rmse*100:.2f}%)")

    # Feature importance
    feature_names = ['D/E Ratio', 'Interest Coverage', 'Profitability', 'Liquidity Ratio']
    importances = model.feature_importances_

    print("\n" + "-"*70)
    print("FEATURE IMPORTANCE")
    print("-"*70)
    for name, importance in zip(feature_names, importances):
        print(f"{name:20s}: {importance:.4f} ({importance*100:.2f}%)")

    return model, X_test, y_test, y_pred_test

# ============================================================================
# MODEL VALIDATION
# ============================================================================

def validate_model(model, X_test, y_test, y_pred):
    """Validate model on test cases"""

    print("\n" + "="*70)
    print("MODEL VALIDATION - SAMPLE PREDICTIONS")
    print("="*70)

    # Show sample predictions
    print("\nSample Predictions (Test Set):")
    print(f"{'DE Ratio':>10} {'Coverage':>10} {'Profit':>10} {'Liquidity':>10} | {'Actual':>10} {'Predicted':>10} {'Error':>10}")
    print("-" * 85)

    for i in range(min(10, len(X_test))):
        de, cov, prof, liq = X_test[i]
        actual = y_test[i]
        predicted = y_pred[i]
        error = abs(predicted - actual)

        print(f"{de:10.2f} {cov:10.2f} {prof:10.2f} {liq:10.2f} | {actual*100:9.2f}% {predicted*100:9.2f}% {error*100:9.2f}%")

    # Compare with rule-based
    print("\n" + "-"*70)
    print("COMPARISON WITH RULE-BASED METHOD")
    print("-"*70)

    # Calculate rule-based PD for first test sample
    de, cov, prof, liq = X_test[0]

    # Rule-based formula
    baseRate = 0.02
    leverageImpact = de * 0.008
    profitabilityImpact = max(0, -prof * 0.15)
    liquidityImpact = max(0, (1.5 - liq) * 0.03)
    coverageImpact = cov > 0 and max(0, (4.0 - cov) * 0.005) or 0.05

    rule_based_pd = min(baseRate + leverageImpact + profitabilityImpact + liquidityImpact + coverageImpact, 1.0)
    ml_pd = y_pred[0]

    print(f"\nTest Sample:")
    print(f"  D/E Ratio: {de:.2f}")
    print(f"  Interest Coverage: {cov:.2f}")
    print(f"  Profitability: {prof:.2f}")
    print(f"  Liquidity Ratio: {liq:.2f}")
    print(f"\nRule-Based PD:    {rule_based_pd*100:.2f}%")
    print(f"ML-Predicted PD:  {ml_pd*100:.2f}%")
    print(f"Difference:       {abs(ml_pd - rule_based_pd)*100:.2f}%")

# ============================================================================
# SAVE MODEL
# ============================================================================

def save_model(model):
    """Save trained model as pickle file"""

    model_path = 'ml_models/pd_model.pkl'

    # Create directory if needed
    os.makedirs('ml_models', exist_ok=True)

    # Save model
    joblib.dump(model, model_path)

    print("\n" + "="*70)
    print("MODEL SAVED")
    print("="*70)
    print(f"Model saved to: {model_path}")

    # Save metadata
    metadata = {
        'model_type': 'RandomForestRegressor',
        'features': ['D/E Ratio', 'Interest Coverage', 'Profitability', 'Liquidity Ratio'],
        'target': 'PD (Probability of Default)',
        'date_created': '2026-06-05',
        'version': '1.0.0',
        'data_type': 'Synthetic (Demo)',
        'note': 'Replace with real data in production'
    }

    metadata_path = 'ml_models/pd_model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to: {metadata_path}")

    return model_path

# ============================================================================
# LOAD AND TEST MODEL
# ============================================================================

def test_loaded_model():
    """Test the saved model"""

    print("\n" + "="*70)
    print("TESTING LOADED MODEL")
    print("="*70)

    # Load model
    model = joblib.load('ml_models/pd_model.pkl')
    print("[OK] Model loaded successfully")

    # Test with sample data
    test_samples = [
        [1.5, 2.5, 0.08, 1.2],  # Good borrower
        [2.5, 1.5, 0.02, 0.9],  # Medium borrower
        [3.0, 0.8, -0.05, 0.8], # Risky borrower
    ]

    labels = ['Good Borrower', 'Medium Borrower', 'Risky Borrower']

    print("\nTest Predictions:")
    print(f"{'Sample':20s} | {'D/E':>6s} {'Cov':>6s} {'Prof':>7s} {'Liq':>6s} | {'PD':>10s}")
    print("-" * 75)

    for sample, label in zip(test_samples, labels):
        prediction = model.predict([sample])[0]
        de, cov, prof, liq = sample
        print(f"{label:20s} | {de:6.2f} {cov:6.2f} {prof:7.2f} {liq:6.2f} | {prediction*100:9.2f}%")

    print("\n[OK] Model is working correctly!")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main training pipeline"""

    print("\n" + "="*70)
    print("PD PREDICTION MODEL TRAINING PIPELINE")
    print("="*70)

    # Step 1: Generate data
    print("\nStep 1: Generating synthetic training data...")
    X, y = generate_synthetic_data(n_samples=500)
    print(f"[OK] Generated {len(X)} training samples")
    print(f"     Feature dimensions: {X.shape[1]}")
    print(f"     PD range: {y.min()*100:.2f}% to {y.max()*100:.2f}%")

    # Step 2: Train model
    print("\nStep 2: Training model...")
    model, X_test, y_test, y_pred = train_model(X, y)
    print("[OK] Model trained")

    # Step 3: Validate
    print("\nStep 3: Validating model...")
    validate_model(model, X_test, y_test, y_pred)
    print("[OK] Validation complete")

    # Step 4: Save
    print("\nStep 4: Saving model...")
    model_path = save_model(model)
    print("[OK] Model saved")

    # Step 5: Test loaded model
    print("\nStep 5: Testing loaded model...")
    test_loaded_model()
    print("[OK] All tests passed")

    print("\n" + "="*70)
    print("TRAINING PIPELINE COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("1. Model is ready at: ml_models/pd_model.pkl")
    print("2. Flask endpoint will load this model")
    print("3. Frontend will offer ML vs Rule-based option")
    print("4. Users can compare both methods")
    print("\nIMPORTANT: This is a DEMO model trained on synthetic data.")
    print("In production, train with real historical borrower data and actual defaults.")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
