#!/usr/bin/env python3
"""
Trailing RF Trainer
Trains a Random Forest to predict if a trade will reach 3R or retrace to BE.
Uses the V3 expanded feature set.
"""
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, precision_score

# --- SETTINGS ---
DATA_PATH = "data/research/trailing_dataset_v3.csv"
MODEL_PATH = "models/trailing_rf_v1.joblib"

def train_model():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    df = df.sort_values('partial_time')
    
    # Features & Target
    features = ['hour', 'adx_partial', 'rsi_partial', 'vol_partial', 
                'ema_9_slope', 'ema_15_slope', 'ema_200_slope', 'dist_ema200', 'time_to_partial']
    
    # Drop any NaNs
    df = df.dropna(subset=features + ['outcome'])
    
    X = df[features]
    y = df['outcome']
    
    # Time-based Split
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Train Random Forest
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=5, # Keep it shallow to prevent overfitting
        random_state=42,
        class_weight='balanced'
    )
    
    print(f"🌲 Training Random Forest on {len(X_train)} samples...")
    rf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = rf.predict(X_test)
    y_prob = rf.predict_proba(X_test)[:, 1]
    
    print(f"\n✅ RF Performance (Test Set):")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.1%}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Feature Importance
    importances = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
    print("\nFeature Importance:")
    print(importances)
    
    # ALPHA ANALYSIS
    # Baseline: Always Run
    baseline_r = y_test.sum() * 1.5
    
    # NN Strategy: Run if Prob > Threshold
    best_threshold = 0.5
    best_nn_r = 0
    
    print("\n📊 Threshold Optimization (Incremental R):")
    for t in np.arange(0.3, 0.7, 0.05):
        nn_r = 0
        for i in range(len(y_test)):
            if y_prob[i] >= t:
                if y_test.iloc[i] == 1: nn_r += 1.5
            else:
                # Early exit at 1.3R (Secures approx 0.3R? No, BE is 0R relative to partial)
                # If we exit early at 1.3R, we get 0R incremental. 
                # If we let it run and it hits SL/BE, we get 0R incremental.
                # So the gain comes from AVOIDING the risk while keeping the winners.
                # BUT if we exit early and it WOULD have been a winner, we lose 1.5R.
                pass
        
        print(f"Threshold {t:.2f} -> {nn_r:.2f} R")
        if nn_r > best_nn_r:
            best_nn_r = nn_r
            best_threshold = t
            
    print(f"\n🏆 Best Result: {best_nn_r:.2f} R at Threshold {best_threshold:.2f}")
    print(f"Baseline Result: {baseline_r:.2f} R")
    
    # Save Model
    os.makedirs("models", exist_ok=True)
    joblib.dump(rf, MODEL_PATH)
    print(f"\n💾 Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
