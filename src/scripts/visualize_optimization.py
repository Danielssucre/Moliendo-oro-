import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- CONFIG ---
RESULTS_PATH = "data/research/antitesis_rr_optimization.csv"
OUTPUT_DIR = "data/research/plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def visualize_optimization():
    if not os.path.exists(RESULTS_PATH):
        print("❌ Optimization results not found.")
        return

    df = pd.read_csv(RESULTS_PATH)
    
    # 1. Total R vs RR (The Performance Curve)
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='rr_test', y='total_r', marker='o', color='#e74c3c')
    plt.axhline(0, color='black', linestyle='--')
    plt.title('Antítesis Performance Sensitivity: Total R vs RR', fontsize=14)
    plt.xlabel('Reward-to-Risk Ratio')
    plt.ylabel('Total Accumulated R (Losses)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/antitesis_sensitivity_curve.png")

    # 2. Win Rate vs RR (The Probability Decay)
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='rr_test', y='win_rate', marker='s', color='#3498db')
    plt.title('Win Rate Decay vs RR (Mirror Strategy)', fontsize=14)
    plt.xlabel('Reward-to-Risk Ratio')
    plt.ylabel('Win Rate %')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/antitesis_winrate_curve.png")

    # 3. Profit Factor vs RR (The Efficiency Frontier)
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='rr_test', y='profit_factor', marker='d', color='#2ecc71')
    plt.axhline(1.0, color='black', linestyle='--', label='Profitability Threshold')
    plt.title('Profit Factor Analysis: Is it even viable?', fontsize=14)
    plt.xlabel('Reward-to-Risk Ratio')
    plt.ylabel('Profit Factor')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/antitesis_profit_factor.png")

    print(f"\n✅ Optimization Visuals Saved in {OUTPUT_DIR}")

if __name__ == "__main__":
    visualize_optimization()
