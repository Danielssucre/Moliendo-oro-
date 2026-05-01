import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

def analyze_rr_optimization(input_file="data/research/infinite_mfe_dataset_v2.csv", output_dir="data/research/plots"):
    """
    Analyzes the optimal Risk/Reward ratio based on Maximum Favorable Excursion (MFE).
    Expectancy = (WinRate * TargetRR) - ((1 - WinRate) * 1.0)
    """
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found.")
        return

    df = pd.read_csv(input_file)
    print(f"📊 Dataset loaded: {len(df)} trades.")

    # Target RR range
    rr_range = np.arange(0.5, 10.1, 0.1)
    
    results = []
    
    # Global Optimization
    for target_rr in rr_range:
        # P(MFE >= target_rr)
        win_rate = (df['max_mfe_r'] >= target_rr).mean()
        # Expectancy assuming 1.0R loss and 0.1R cost (spread/slippage)
        cost = 0.1 
        expectancy = (win_rate * (target_rr - cost)) - ((1 - win_rate) * (1.0 + cost))
        results.append({
            'target_rr': target_rr,
            'win_rate': win_rate,
            'expectancy': expectancy
        })

    results_df = pd.DataFrame(results)
    optimal_row = results_df.loc[results_df['expectancy'].idxmax()]
    
    print("\n🏆 GLOBAL OPTIMAL RR:")
    print(f"   RR: {optimal_row['target_rr']:.1f}")
    print(f"   Win Rate: {optimal_row['win_rate']*100:.1f}%")
    print(f"   Expectancy: {optimal_row['expectancy']:.4f} R per trade")

    # symbol-wise optimization
    symbol_results = []
    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol]
        if len(symbol_df) < 50: continue # Minimum sample size
        
        best_e = -999
        best_rr = 0
        best_wr = 0
        
        for target_rr in rr_range:
            wr = (symbol_df['max_mfe_r'] >= target_rr).mean()
            cost = 0.1
            exp = (wr * (target_rr - cost)) - ((1 - wr) * (1.0 + cost))
            if exp > best_e:
                best_e = exp
                best_rr = target_rr
                best_wr = wr
        
        symbol_results.append({
            'symbol': symbol,
            'optimal_rr': best_rr,
            'win_rate': best_wr,
            'expectancy': best_e,
            'sample_size': len(symbol_df)
        })

    symbol_results_df = pd.DataFrame(symbol_results).sort_values(by='expectancy', ascending=False)
    print("\n📊 OPTIMAL RR BY SYMBOL (Sample > 50):")
    print(symbol_results_df.to_string(index=False))
    
    # Plotting
    os.makedirs(output_dir, exist_ok=True)
    plt.figure(figsize=(12, 6))
    plt.plot(results_df['target_rr'], results_df['expectancy'], label='Global Expectancy', color='blue', linewidth=2)
    plt.axvline(optimal_row['target_rr'], color='red', linestyle='--', label=f"Optimal RR: {optimal_row['target_rr']:.1f}")
    plt.title("HIVE Ecosystem: RR Optimization Curve")
    plt.xlabel("Target RR")
    plt.ylabel("Expectancy (R)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plot_path = os.path.join(output_dir, "rr_optimization_curve.png")
    plt.savefig(plot_path)
    print(f"\n🖼️ Plot saved to {plot_path}")

    # direction optimization
    print("\n🔍 Optimizando por Dirección (THESIS vs ANTITESIS):")
    # direction in dataset is BUY/SELL, but we want to know if it's Thesis or Antithesis
    # In run_live.py, ALFA is side=1, NEME is side=-1. 
    # This dataset doesn't explicitly flag "Thesis/Antithesis" tags, 
    # but we can look at the average max_mfe_r.

    return results_df, symbol_results_df

if __name__ == "__main__":
    analyze_rr_optimization()
