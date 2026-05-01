import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- CONFIG ---
RESULTS_PATH = "data/research/backtest_sniper_v2_results.csv"
NEMESIS_PATH = "data/research/backtest_nemesis_results.csv"
OUTPUT_DIR = "data/research/plots"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_report():
    if not os.path.exists(RESULTS_PATH):
        print(f"❌ Results not found at {RESULTS_PATH}")
        return

    df = pd.read_csv(RESULTS_PATH)
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time')

    # 1. Equity Curve
    plt.figure(figsize=(12, 6))
    plt.plot(df['time'], df['balance'], label='Combined Equity', color='#2ecc71', linewidth=2)
    
    # Isolate Tésis for comparison
    df_tesis = df[df['type'].str.contains('TESIS')]
    if not df_tesis.empty:
        tesis_pnl = df_tesis['dollar_pnl'].cumsum() + 10000
        plt.plot(df_tesis['time'], tesis_pnl, label='Tésis Sniper (Trend)', color='#3498db', linestyle='--')

    # Load and plot Nemesis for comparison
    if os.path.exists(NEMESIS_PATH):
        df_neme = pd.read_csv(NEMESIS_PATH)
        df_neme['time'] = pd.to_datetime(df_neme['time'])
        plt.plot(df_neme['time'], df_neme['balance'], label='Old Nemesis (BB)', color='#9b59b6', alpha=0.6)


    plt.title('HIVE Sniper V2: Institutional Equity Curve', fontsize=14, fontweight='bold')
    plt.ylabel('Balance ($)')
    plt.xlabel('Date')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/equity_curve.png")
    print(f"✅ Equity Curve saved: {OUTPUT_DIR}/equity_curve.png")

    # 2. Drawdown Chart
    plt.figure(figsize=(12, 4))
    rolling_max = df['balance'].cummax()
    drawdown = (df['balance'] - rolling_max) / rolling_max * 100
    plt.fill_between(df['time'], drawdown, 0, color='#e74c3c', alpha=0.3)
    plt.plot(df['time'], drawdown, color='#c0392b', linewidth=1)
    plt.title('Drawdown Profile (%)', fontsize=12)
    plt.ylabel('Drawdown %')
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/drawdown.png")

    # 3. Profit by Symbol
    plt.figure(figsize=(12, 6))
    symbol_pnl = df.groupby('symbol')['pnl_r'].sum().sort_values()
    colors = ['#e74c3c' if x < 0 else '#2ecc71' for x in symbol_pnl]
    symbol_pnl.plot(kind='barh', color=colors)
    plt.title('PnL (R) by Trading Symbol', fontsize=14)
    plt.xlabel('Accumulated R')
    plt.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/symbol_performance.png")

    # 4. Strategy Comparison (Tésis vs Antítesis)
    plt.figure(figsize=(10, 6))
    strat_pnl = df.groupby('type')['pnl_r'].sum()
    colors_strat = ['#e74c3c' if x < 0 else '#2ecc71' for x in strat_pnl]
    strat_pnl.plot(kind='bar', color=colors_strat)
    plt.title('Total PnL (R) by Strategy Component', fontsize=14)
    plt.ylabel('Accumulated R')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/strategy_mix.png")


    print("\n📈 VISUAL REPORT GENERATION COMPLETE.")

if __name__ == "__main__":
    generate_report()
