import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import brier_score_loss, accuracy_score

def retrain_calibrated_model():
    dataset_path = "data/stop_hunt_dataset.csv"
    model_output_path = "models/stop_hunt_rf_calibrated.joblib"
    
    if not os.path.exists(dataset_path):
        print("Dataset not found.")
        return

    df = pd.read_csv(dataset_path)
    features = ['wick_ratio', 'volatility_surge', 'successive_move', 'rsi', 'adx']
    X = df[features]
    y = df['label']
    
    # Split for validation
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 1. Base Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    
    # 2. Calibration (Isotonic is preferred for larger datasets, Platt otherwise)
    # Since we have ~900 rows, Isotonic is suitable.
    calibrated_rf = CalibratedClassifierCV(rf, method='isotonic', cv=5)
    calibrated_rf.fit(X_train, y_train)
    
    # 3. Evaluate
    y_prob_uncal = calibrated_rf.predict_proba(X_test)[:, 1]
    brier = brier_score_loss(y_test, y_prob_uncal)
    acc = accuracy_score(y_test, calibrated_rf.predict(X_test))
    
    print(f"🚀 MODELO CALIBRADO ENTRENADO 🚀")
    print(f"Accuracy: {acc:.4f}")
    print(f"Brier Score (Test): {brier:.4f}")
    
    # Save
    os.makedirs("models", exist_ok=True)
    joblib.dump(calibrated_rf, model_output_path)
    print(f"Saved to {model_output_path}")

if __name__ == "__main__":
    retrain_calibrated_model()
