#!/usr/bin/env python3
"""
Infinite NN Trainer V2 (Regression)
Trains a small Neural Network to predict the Max MFE potential of a trade.
Uses advanced features (slopes, RSI, etc.)
"""
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error, r2_score

# --- SETTINGS ---
DATA_PATH = "data/research/infinite_mfe_dataset_v2.csv"
MODEL_PATH = "models/infinite_nn_reg_v2.joblib"
SCALER_PATH = "models/infinite_scaler_reg_v2.joblib"

def train_model():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    
    # Features from Deep Extraction
    features = ['adx_partial', 'rsi_partial', 'vol_partial', 
                'ema_9_slope', 'ema_15_slope', 'dist_ema200', 'hour']
    
    df = df.dropna(subset=features + ['max_mfe_r'])
    X = df[features]
    y = df['max_mfe_r']
    
    # Time-based Split (Walk-Forward)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Small NN Regressor (8 Units as requested)
    nn = MLPRegressor(
        hidden_layer_sizes=(8,),
        activation='relu',
        solver='adam',
        max_iter=3000,
        random_state=42,
        alpha=0.01 # L2 Regularization
    )
    
    print(f"🧠 Training Infinite NN Regressor (Advanced Features)...")
    nn.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = nn.predict(X_test_scaled)
    # Floor negative predictions to 0
    y_pred = np.maximum(y_pred, 0)
    
    print(f"\n✅ Performance (Test Set):")
    print(f"MAE: {mean_absolute_error(y_test, y_pred):.2f} R")
    print(f"R2 Score: {r2_score(y_test, y_pred):.4f}")
    
    # Simple Logic Insight
    print("\n💡 AI Insights (Actual vs Predicted):")
    results = pd.DataFrame({'Actual': y_test, 'Pred': y_pred})
    print(results.describe())

    # Save
    os.makedirs("models", exist_ok=True)
    joblib.dump(nn, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\n💾 Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
