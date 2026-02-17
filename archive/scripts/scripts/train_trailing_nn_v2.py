#!/usr/bin/env python3
"""
Trailing NN Trainer V2 (Optimized)
Trains a small Neural Network with selected features from RF analysis.
Objective: Find a threshold where NN adds value vs Always Run.
"""
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, accuracy_score

# --- SETTINGS ---
DATA_PATH = "data/research/trailing_dataset_v3.csv"
MODEL_PATH = "models/trailing_nn_v2.joblib"
SCALER_PATH = "models/trailing_scaler_v2.joblib"

def train_model():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    df = df.sort_values('partial_time')
    
    # Top Features from RF Performance + Correlation
    features = ['dist_ema200', 'ema_9_slope', 'ema_15_slope', 'adx_partial', 'rsi_partial']
    
    df = df.dropna(subset=features + ['outcome'])
    X = df[features]
    y = df['outcome']
    
    # Time-based Split
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Small NN (1 hidden layer, 8 neurons - Daniel's spec)
    nn = MLPClassifier(
        hidden_layer_sizes=(8,),
        activation='relu',
        solver='adam',
        max_iter=2000,
        random_state=42,
        alpha=0.01 # L2 regularization to prevent overfit
    )
    
    print(f"🧠 Training Optimized MLP (8 Units) on {len(X_train)} samples...")
    nn.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = nn.predict(X_test_scaled)
    y_prob = nn.predict_proba(X_test_scaled)[:, 1]
    
    print(f"\n✅ NN Performance (Test Set):")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.1%}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # ALPHA STRATEGY EVALUATION
    # Strategy: 
    # - If Prob > T: Run normally (Goal 3.0R)
    # - If Prob < T: Tighten Trail or Exit Early
    
    baseline_r_inc = y_test.sum() * 1.5 
    
    print("\n📊 Threshold Optimization (Incremental R-Gain):")
    for t in np.arange(0.35, 0.65, 0.05):
        # Calculation for NN strategy:
        # We only let it run if it has high probability.
        # Otherwise, we exit at partial (0.0 incremental R).
        nn_r_inc = 0.0
        for i in range(len(y_test)):
            if y_prob[i] >= t:
                if y_test.iloc[i] == 1: nn_r_inc += 1.5
            else:
                # Early Exit secures the current profit and avoids potential loss.
                # In our simulation, BE is 0R gain. 
                # Early exit is also 0R gain *BUT* it reduces time in market.
                # To see a gain in R-units, we need to compare to a 'Loss' scenario.
                pass
        
        print(f"Prob Threshold {t:.2f} -> {nn_r_inc:.2f} R")

    # Save
    os.makedirs("models", exist_ok=True)
    joblib.dump(nn, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\n💾 Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
