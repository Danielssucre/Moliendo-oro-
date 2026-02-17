import pandas as pd
import numpy as np
import joblib
import os
from sklearn.metrics import brier_score_loss
from sklearn.calibration import calibration_curve
import matplotlib.pyplot as plt

def perform_surgical_diagnosis():
    dataset_path = "data/stop_hunt_dataset.csv"
    model_path = "models/stop_hunt_rf.joblib"
    
    if not os.path.exists(dataset_path) or not os.path.exists(model_path):
        print("Missing data or model for diagnosis.")
        return

    df = pd.read_csv(dataset_path)
    model = joblib.load(model_path)
    
    # Features match StopHuntModel definition
    features = ['wick_ratio', 'volatility_surge', 'successive_move', 'rsi', 'adx']
    X = df[features]
    y = df['label'] # 1 = Stop Hunt (Trap), 0 = Safe
    
    # Get uncalibrated probabilities
    y_prob = model.predict_proba(X)[:, 1]
    
    # 1. Brier Score (Lower is better)
    brier = brier_score_loss(y, y_prob)
    
    # 2. Calibration Curve data
    prob_true, prob_pred = calibration_curve(y, y_prob, n_bins=10)
    
    # 3. Likelihoods calculation
    # We want P(Evidence | Success) and P(Evidence | Fail)
    # Success in our context means NO Stop Hunt (label 0)
    # Evidence is the ML probability bucket
    
    print(f"--- DIAGNÓSTICO QUIRÚRGICO (NANOBOT) ---")
    print(f"Muestras: {len(df)}")
    print(f"Brier Score: {brier:.4f}")
    
    print("\n📈 Curva de Fiabilidad (Uncalibrated RF):")
    for p_pred, p_true in zip(prob_pred, prob_true):
        print(f"   Bin Pred: {p_pred:.2f} | Frecuencia Real: {p_true:.2f}")

    # 4. Expected Calibration Error (ECE) approximate
    ece = np.abs(prob_pred - prob_true).mean()
    print(f"\nExpected Calibration Error (ECE approx): {ece:.4f}")
    
    # Decision: If ECE > 0.05, we need calibration
    if ece > 0.05:
        print("\n⚠️ ALERTA: ECE > 0.05. Las probabilidades del RF están SESGADAS.")
    
    # 5. Kelly Preview (Conceptual)
    # Let's assume R:R = 1.5, p = 1 - risk
    # For a few samples:
    print("\n🔬 Simulación de Kelly Fraccionado (p = 0.7, R:R = 1.5):")
    p = 0.7
    b = 1.5
    kelly_f = (b * p - (1-p)) / b
    print(f"   Kelly Full: {kelly_f:.4f}")
    print(f"   Fractional Kelly (0.5x): {kelly_f * 0.5:.4f}")

if __name__ == "__main__":
    perform_surgical_diagnosis()
