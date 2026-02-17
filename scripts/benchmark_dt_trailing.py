#!/usr/bin/env python3
"""
Dynamic Trailing Benchmark (Fase 4)
Quantifies the Alpha gain of an AI-guided trailing stop vs. Always Run.
"""
import pandas as pd
import numpy as np
import os
import joblib

# --- SETTINGS ---
DATA_PATH = "data/research/trailing_dataset_v3.csv" # V4 data is saved to the same name in my script
MODEL_PATH = "models/trailing_nn_v2.joblib"
SCALER_PATH = "models/trailing_scaler_v2.joblib"

def run_benchmark():
    if not os.path.exists(DATA_PATH) or not os.path.exists(MODEL_PATH):
        print("❌ Missing data or models")
        return

    df = pd.read_csv(DATA_PATH)
    df = df.sort_values('partial_time')
    
    # Features from NN v2
    features = ['dist_ema200', 'ema_9_slope', 'ema_15_slope', 'adx_partial', 'rsi_partial']
    df = df.dropna(subset=features + ['outcome', 'max_excursion_r'])
    
    # Test on the same 20% window
    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:].copy()
    
    # Load AI
    nn = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    
    X_test_scaled = scaler.transform(test_df[features])
    probs = nn.predict_proba(X_test_scaled)[:, 1]
    
    test_df['win_prob'] = probs
    
    # STRATEGY SIMULATION
    # Baseline V1.0: Always Run (Hits 1.5R incremental if outcome=1, else 0R)
    test_df['r_baseline'] = test_df['outcome'].apply(lambda x: 1.5 if x == 1 else 0.0)
    
    # AI Dynamic Trailing (Logic):
    # - At 1.3R (Partial), query the AI.
    # - If WinProb < 0.35: Implement a TIGHT Trailing. 
    #   Logic: If price reached 1.8R (+0.5 from Partial), we capture 0.5R even if it hits BE later.
    #   Approx: If max_excursion_gain_after_partial >= 0.5, we get 0.5R.
    
    def simulate_ai_trailing(row):
        prob = row['win_prob']
        outcome = row['outcome']
        max_exc = row['max_excursion_r'] # Absolute R from entry
        
        # Incremental R gained AFTER the 1.3R partial
        if prob < 0.35:
            # PROTECTIVE MODE
            # We move SL to +0.5R from Entry (approx half-way to a 1R runner)
            # If price reaches +0.8R from Entry (Wait, 1.3R is partial. Hits 0.5 is 1.8R)
            if max_exc >= 1.8:
                return 0.5 # We secured 0.5R more than the partial
            else:
                return 0.0 # Hits BE at Entry
        else:
            # AGGRESSIVE MODE (Run to 3.0R)
            if outcome == 1:
                return 1.5
            else:
                return 0.0

    test_df['r_ai_dynamic'] = test_df.apply(simulate_ai_trailing, axis=1)
    
    print("\n" + "="*50)
    print("🏆 FINAL ALPHA VALIDATION: AI DYNAMIC TRAILING")
    print("="*50)
    print(f"Total Test Trades: {len(test_df)}")
    print(f"Baseline Incremental R: {test_df['r_baseline'].sum():.2f} R")
    print(f"AI Dynamic Incremental R: {test_df['r_ai_dynamic'].sum():.2f} R")
    
    alpha = test_df['r_ai_dynamic'].sum() - test_df['r_baseline'].sum()
    print(f"🎯 NET ALPHA GAIN: {alpha:+.2f} R")
    print(f"📈 Performance Boost: {(alpha / test_df['r_baseline'].sum() * 100):.1f}%")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_benchmark()
