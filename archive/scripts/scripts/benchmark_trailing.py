#!/usr/bin/env python3
"""
Trailing Benchmark Script
Evaluates different trailing stop strategies on the forensic dataset.
"""
import pandas as pd
import numpy as np
import os

# --- SETTINGS ---
DATA_PATH = "data/research/trailing_dataset.csv"

def run_benchmark():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    total_trades = len(df)
    
    # 1. BASELINE: Current V1.0 (Fixed TP 3R or BE)
    # If outcome=1, we get 0.5 (initial) + 0.5 * 3.0 = 2.0 R (approx if we include initial 0.5*1.3)
    # Actually, let's just calculate "Incremental R" after the partial hit.
    # At Partial Hit: We already secured 0.5 * 1.3 = 0.65 R.
    # Current Rule: Let the other 0.5 run to 3.0 R (Goal) or return to BE.
    # Incremental R (Baseline): 
    # If outcome=1: (3.0 - 0.0) * 0.5 = 1.5 R
    # If outcome=0: 0.0 R
    
    df['incremental_r_baseline'] = df['outcome'].apply(lambda x: 1.5 if x == 1 else 0.0)
    baseline_r = df['incremental_r_baseline'].sum()
    
    print("\n" + "="*50)
    print("📋 TRAILING STRATEGY BENCHMARK")
    print("="*50)
    print(f"Total Samples: {total_trades}")
    print(f"Probability of 3.0R: {df['outcome'].mean():.1%}")
    print(f"Total Incremental R (Baseline V1.0): {baseline_r:.2f} R")
    print(f"Expectancy (Post-Partial): {df['incremental_r_baseline'].mean():.2f} R/trade")
    
    # 2. FIXED TRAILING (0.3R)
    # Assume we move SL to (Current Price - 0.3R) as price advances.
    # This is hard to simulate perfectly on a static dataset without MFE/MAE between Partial and Exit.
    # But we can approximate using the "Retracement" logic.
    # However, let's try to find a proxy.
    
    # Let's consider a "Protective Exit" rule:
    # If we implement a rule that closes the trade if it retraces X pips...
    # Since we don't have the path in the CSV, let's look at the features.
    
    print("\n💡 NOTE: Static benchmarking is limited. We need to verify in a full loop.")
    print("But lets analyze features correlation with success:")
    
    correlations = df[['adx_partial', 'vol_partial', 'time_to_partial_hours', 'ema_dist_ratio', 'outcome']].corr()['outcome']
    print("\nFeature Correlation with 3.0R Success:")
    print(correlations)

if __name__ == "__main__":
    run_benchmark()
