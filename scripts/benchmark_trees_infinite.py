#!/usr/bin/env python3
"""
Tree-Based Infinite Trailing Benchmark
Compares Decision Tree and Random Forest vs the Step 0.5R Baseline.
"""
import pandas as pd
import numpy as np
import os
import joblib

# --- SETTINGS ---
DATA_PATH = "data/research/infinite_mfe_dataset_v2.csv"
MODEL_DT_PATH = "models/infinite_dt_reg_v1.joblib"
MODEL_RF_PATH = "models/infinite_rf_reg_v1.joblib"
SCALER_PATH = "models/infinite_scaler_tree_v1.joblib"

def simulate_step_trailing(mfe_r, step_size_r=0.5):
    if mfe_r < 1.3: return 0.0
    relative_gain = mfe_r - 1.3
    num_steps = int(relative_gain // step_size_r)
    return num_steps * step_size_r

def run_benchmark():
    if not all(os.path.exists(p) for p in [DATA_PATH, MODEL_DT_PATH, MODEL_RF_PATH]):
        print("❌ Missing data or models")
        return

    df = pd.read_csv(DATA_PATH)
    features = ['adx_partial', 'rsi_partial', 'vol_partial', 
                'ema_9_slope', 'ema_15_slope', 'dist_ema200', 'hour']
    df = df.dropna(subset=features + ['max_mfe_r'])
    
    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:].copy()
    
    # Load
    dt = joblib.load(MODEL_DT_PATH)
    rf = joblib.load(MODEL_RF_PATH)
    scaler = joblib.load(SCALER_PATH)
    
    X_test_scaled = scaler.transform(test_df[features])
    test_df['pred_dt'] = np.maximum(dt.predict(X_test_scaled), 0)
    test_df['pred_rf'] = np.maximum(rf.predict(X_test_scaled), 0)
    
    # STRATEGIES
    test_df['r_fixed_3_1'] = test_df['max_mfe_r'].apply(lambda x: 1.8 if x >= 3.1 else 0.0)
    test_df['r_step_0_5'] = test_df['max_mfe_r'].apply(lambda x: simulate_step_trailing(x, 0.5))
    
    def simulate_ai_dynamic(row, pred_col):
        pred_mfe = row[pred_col]
        mfe_actual = row['max_mfe_r']
        
        if pred_mfe > 7.0: # High Moon potential
            return simulate_step_trailing(mfe_actual, 1.0) # Loose for big moves
        elif pred_mfe < 3.0: # High chance of return to BE
            return simulate_step_trailing(mfe_actual, 0.3) # Tight protection
        else:
            return simulate_step_trailing(mfe_actual, 0.5)

    test_df['r_ai_dt'] = test_df.apply(lambda r: simulate_ai_dynamic(r, 'pred_dt'), axis=1)
    test_df['r_ai_rf'] = test_df.apply(lambda r: simulate_ai_dynamic(r, 'pred_rf'), axis=1)
    
    print("\n" + "="*60)
    print("🌳 TREE-BASED INFINITE RUNNER FINAL BENCHMARK")
    print("="*60)
    print(f"Test Trades: {len(test_df)}")
    print("-" * 60)
    
    results = {
        "Fixed 3.1R (Original)": test_df['r_fixed_3_1'].sum(),
        "Step 0.5R (New Baseline)": test_df['r_step_0_5'].sum(),
        "AI CART (Decision Tree)": test_df['r_ai_dt'].sum(),
        "AI Forest (Random Forest)": test_df['r_ai_rf'].sum()
    }
    
    for name, total_r in results.items():
        print(f"{name:<25} | Total R: {total_r:>10.2f} | Avg: {(total_r/len(test_df)):>5.2f}")

    print("-" * 60)
    best_ai = max(results["AI CART (Decision Tree)"], results["AI Forest (Random Forest)"])
    alpha_gain = best_ai - results["Step 0.5R (New Baseline)"]
    print(f"🎯 Best AI Alpha Gain: {alpha_gain:>+10.2f} R")
    print("="*60)

if __name__ == "__main__":
    run_benchmark()
