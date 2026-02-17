#!/usr/bin/env python3
"""
AI Infinite Trailing Benchmark
Compares the AI-guided trailing stop vs the pure 0.5R Step Trailing Baseline.
"""
import pandas as pd
import numpy as np
import os
import joblib

# --- SETTINGS ---
DATA_PATH = "data/research/infinite_mfe_dataset_v2.csv"
MODEL_PATH = "models/infinite_nn_reg_v2.joblib"
SCALER_PATH = "models/infinite_scaler_reg_v2.joblib"

def simulate_step_trailing(mfe_r, step_size_r=0.5):
    """
    Standard step trailing logic.
    """
    if mfe_r < 1.3: return 0.0
    relative_gain = mfe_r - 1.3
    num_steps = int(relative_gain // step_size_r)
    return num_steps * step_size_r

def run_benchmark():
    if not os.path.exists(DATA_PATH) or not os.path.exists(MODEL_PATH):
        print("❌ Missing data or models")
        return

    df = pd.read_csv(DATA_PATH)
    
    # Features for AI
    features = ['adx_partial', 'rsi_partial', 'vol_partial', 
                'ema_9_slope', 'ema_15_slope', 'dist_ema200', 'hour']
    
    df = df.dropna(subset=features + ['max_mfe_r'])
    
    # Test on the same 20% window used for training evaluation
    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:].copy()
    
    # Load AI
    nn = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    
    X_test_scaled = scaler.transform(test_df[features])
    preds = nn.predict(X_test_scaled)
    test_df['ai_pred_mfe'] = np.maximum(preds, 0)
    
    # BASELINES
    test_df['r_fixed_3_1'] = test_df['max_mfe_r'].apply(lambda x: 1.8 if x >= 3.1 else 0.0)
    test_df['r_step_0_5'] = test_df['max_mfe_r'].apply(lambda x: simulate_step_trailing(x, 0.5))
    
    # AI DYNAMIC STRATEGY
    def simulate_ai_dynamic(row):
        pred_mfe = row['ai_pred_mfe']
        mfe_actual = row['max_mfe_r']
        
        # Logic:
        if pred_mfe > 5.0:
            # High potential -> Loose trailing (1.0R)
            return simulate_step_trailing(mfe_actual, 1.0)
        elif pred_mfe < 3.0:
            # Low potential -> Tight trailing (0.3R)
            return simulate_step_trailing(mfe_actual, 0.3)
        else:
            # Medium -> Default (0.5R)
            return simulate_step_trailing(mfe_actual, 0.5)

    test_df['r_ai_hybrid'] = test_df.apply(simulate_ai_dynamic, axis=1)
    
    print("\n" + "="*60)
    print("🧠 AI HYBRID INFINITE RUNNER BENCHMARK")
    print("="*60)
    print(f"Test Trades: {len(test_df)}")
    print("-" * 60)
    
    results = {
        "Fixed 3.1R (Baseline)": test_df['r_fixed_3_1'].sum(),
        "Step 0.5R (New Baseline)": test_df['r_step_0_5'].sum(),
        "AI Hybrid (Dynamic)": test_df['r_ai_hybrid'].sum()
    }
    
    for name, total_r in results.items():
        print(f"{name:<25} | Total R: {total_r:>10.2f} | Avg: {(total_r/len(test_df)):>5.2f}")

    print("-" * 60)
    alpha_gain = results["AI Hybrid (Dynamic)"] - results["Step 0.5R (New Baseline)"]
    print(f"🎯 AI Incremental Alpha: {alpha_gain:>+10.2f} R")
    print("="*60)

if __name__ == "__main__":
    run_benchmark()
