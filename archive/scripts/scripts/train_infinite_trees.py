#!/usr/bin/env python3
"""
Infinite Tree Trainer
Trains a Decision Tree and Random Forest to predict MFE potential.
Extracts interpretable rules and saves models for benchmarking.
"""
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor, export_text
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

# --- SETTINGS ---
DATA_PATH = "data/research/infinite_mfe_dataset_v2.csv"
MODEL_DT_PATH = "models/infinite_dt_reg_v1.joblib"
MODEL_RF_PATH = "models/infinite_rf_reg_v1.joblib"
SCALER_PATH = "models/infinite_scaler_tree_v1.joblib"

def train_models():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    
    # Features (Same as Phase 9)
    features = ['adx_partial', 'rsi_partial', 'vol_partial', 
                'ema_9_slope', 'ema_15_slope', 'dist_ema200', 'hour']
    
    df = df.dropna(subset=features + ['max_mfe_r'])
    X = df[features]
    y = df['max_mfe_r']
    
    # Time-based Split
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Scaling (Optional for trees, but good for consistency)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 1. TRAIN DECISION TREE (Interpretability)
    # Limiting depth for simplicity and extraction of clear rules
    dt = DecisionTreeRegressor(max_depth=4, random_state=42)
    print(f"🌳 Training Decision Tree (Depth 4)...")
    dt.fit(X_train_scaled, y_train)
    
    # 2. TRAIN RANDOM FOREST (Robustness)
    rf = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    print(f"🌲 Training Random Forest (100 Trees)...")
    rf.fit(X_train_scaled, y_train)
    
    # --- EVALUATION ---
    def evaluate(model, name, X_val, y_val):
        y_pred = model.predict(X_val)
        y_pred = np.maximum(y_pred, 0)
        print(f"\n✅ {name} Performance:")
        print(f"MAE: {mean_absolute_error(y_val, y_pred):.2f} R")
        print(f"R2 Score: {r2_score(y_val, y_pred):.4f}")
        return y_pred

    evaluate(dt, "Decision Tree", X_test_scaled, y_test)
    evaluate(rf, "Random Forest", X_test_scaled, y_test)
    
    # --- RULE EXTRACTION ---
    print("\n📜 EXTRACTED RULES (Decision Tree):")
    rules = export_text(dt, feature_names=features)
    print(rules)
    
    # --- IMPORTANCE ---
    print("\n📊 FEATURE IMPORTANCE (Random Forest):")
    importance = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
    print(importance)

    # Save
    os.makedirs("models", exist_ok=True)
    joblib.dump(dt, MODEL_DT_PATH)
    joblib.dump(rf, MODEL_RF_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\n💾 Models saved.")

if __name__ == "__main__":
    train_models()
