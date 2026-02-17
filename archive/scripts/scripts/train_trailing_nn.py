#!/usr/bin/env python3
"""
Trailing NN Trainer
Trains a small Neural Network to predict if a trade will reach 3R or retrace to BE.
"""
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# --- SETTINGS ---
DATA_PATH = "data/research/trailing_dataset.csv"
MODEL_PATH = "models/trailing_nn_v1.joblib"
SCALER_PATH = "models/trailing_scaler_v1.joblib"

def train_model():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    
    # Sort by time for Walk-Forward split
    df = df.sort_values('partial_time')
    
    # Features & Target
    features = ['adx_partial', 'vol_partial', 'time_to_partial_hours', 'ema_dist_ratio']
    X = df[features]
    y = df['outcome']
    
    # Time-based Split (Walk-Forward)
    # Train on 80%, Test on 20%
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Small Neural Network
    # 1 Hidden layer with 8 neurons (as requested by Daniel)
    nn = MLPClassifier(
        hidden_layer_sizes=(8,),
        activation='relu',
        solver='adam',
        max_iter=1000,
        random_state=42,
        early_stopping=True
    )
    
    print("🧠 Training Small Neural Network...")
    nn.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = nn.predict(X_test_scaled)
    y_prob = nn.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n✅ Testing Performance (Last 20% of data):")
    print(f"Accuracy: {accuracy:.1%}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Alpha Analysis
    # If we use the NN to close trades where prob < 0.4...
    threshold = 0.4
    nn_decision_close = y_prob < threshold
    
    # Baseline: If we didn't use NN, we'd have outcome sum * 1.5R (incremental)
    baseline_r = y_test.sum() * 1.5
    
    # NN Strategy:
    # If NN says CLOSE (prob < 0.4): We close immediately at Partial (approx 0.0 incremental R).
    # If NN says RUN: We get the actual outcome (1.5R if outcome=1, 0.0R if outcome=0).
    nn_r = 0.0
    for i in range(len(y_test)):
        is_hit = y_test.iloc[i] == 1
        if y_prob[i] >= threshold:
            # Let it run
            if is_hit: nn_r += 1.5
        else:
            # Close at partial (Early exit)
            # This avoids the risk of returning to BE, but we don't get the 3R if it would have hit.
            # In our baseline simulation, BE is 0R. Early exit is 0R.
            # BUT, if we close early and it WOULD HAVE BECOME a 3R, we lose Alpha.
            pass
            
    print(f"\n📊 Strategy Comparison (Post-Partial Incremental R):")
    print(f"Baseline (Always Run): {baseline_r:.2f} R")
    print(f"NN (Run if Prob > {threshold}): {nn_r:.2f} R")
    
    # Save Model
    os.makedirs("models", exist_ok=True)
    joblib.dump(nn, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\n💾 Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
