#!/usr/bin/env python3
"""
Infinite Trailing Benchmark
Simulates and compares different trailing stop strategies against the fixed 3.1R baseline.
"""
import pandas as pd
import numpy as np
import os

# --- SETTINGS ---
DATA_PATH = "data/research/infinite_mfe_dataset.csv"

def simulate_step_trailing(mfe_r, step_size_r=1.0):
    """
    Simulates a step trailing stop after the 1.3R partial.
    If price moves up by step_size_r, we move SL up by step_size_r.
    """
    if mfe_r < 1.3: return 0.0 # Didn't even reach partial in our dataset extraction logic (but we already filtered)
    
    # Starting state: Price at 1.3R, SL at 0.0R (Entry/BE)
    current_sl_r = 0.0
    relative_gain_after_partial = mfe_r - 1.3
    
    # Every time we gain 'step_size_r' we move SL up
    num_steps = int(relative_gain_after_partial // step_size_r)
    current_sl_r = num_steps * step_size_r
    
    return current_sl_r

def simulate_fixed_target(mfe_r, target_r=3.1):
    """
    Baseline V1.0 result (Incremental R after the 1.3R partial).
    """
    if mfe_r >= target_r:
        return target_r - 1.3 # 1.8R gain
    else:
        return 0.0 # Hits BE

def run_benchmark():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset not found at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)
    
    # 1. FIXED 3.1R BASELINE
    df['r_fixed_3_1'] = df['max_mfe_r'].apply(lambda x: simulate_fixed_target(x, 3.1))
    
    # 2. STEP TRAILING (1.0R Step)
    df['r_step_1_0'] = df['max_mfe_r'].apply(lambda x: simulate_step_trailing(x, 1.0))
    
    # 3. STEP TRAILING (0.5R Step)
    df['r_step_0_5'] = df['max_mfe_r'].apply(lambda x: simulate_step_trailing(x, 0.5))
    
    # 4. "TIGHT" STEP TRAILING (0.3R Step)
    df['r_step_0_3'] = df['max_mfe_r'].apply(lambda x: simulate_step_trailing(x, 0.3))

    results = {
        "Baseline (Fixed 3.1R)": df['r_fixed_3_1'].sum(),
        "Step Trailing (1.0R)": df['r_step_1_0'].sum(),
        "Step Trailing (0.5R)": df['r_step_0_5'].sum(),
        "Step Trailing (0.3R)": df['r_step_0_3'].sum()
    }
    
    print("\n" + "="*60)
    print("♾️  INFINITE RUNNER STRATEGY BENCHMARK")
    print("="*60)
    print(f"Total Trades Analizados: {len(df)}")
    print("-" * 60)
    
    for name, total_r in results.items():
        avg_r = total_r / len(df)
        pct_change = (total_r / results["Baseline (Fixed 3.1R)"] - 1) * 100
        print(f"{name:<25} | Total R: {total_r:>10.2f} | Avg: {avg_r:>5.2f} | Diff: {pct_change:>+6.1f}%")

    print("="*60)
    
    # Deep dive into the winners
    print("\n💎 ANALYSIS OF 'MOON' TRADES (> 10R):")
    moons = df[df['max_mfe_r'] >= 10.0]
    print(f"Count: {len(moons)}")
    print(f"Fixed 3.1R Profit from these: {moons['r_fixed_3_1'].sum():.2f} R")
    print(f"Step 1.0R Profit from these:  {moons['r_step_1_0'].sum():.2f} R")
    print("-" * 60)
    
    # Why trailing might be worse?
    print("\n⚠️  ANALYSIS OF 'TRAPPED' TRADES (Reached 3R but fell to BE):")
    trapped = df[(df['max_mfe_r'] >= 3.0) & (df['max_mfe_r'] < 3.1)] # Very small window for now in this sim
    # Better: trades that reach 2.5R but not 3.1R
    trapped = df[(df['max_mfe_r'] >= 2.5) & (df['max_mfe_r'] < 3.1)]
    print(f"Count: {len(trapped)}")
    print(f"Fixed 3.1R Profit (Baseline): {trapped['r_fixed_3_1'].sum():.2f} R (All hit BE)")
    print(f"Step 0.5R Profit (Trailing): {trapped['r_step_0_5'].sum():.2f} R (Captured some!)")

if __name__ == "__main__":
    run_benchmark()
