import pandas as pd
import os

mt5_file = "data/research/analyzed_ftmo_history.csv"
if os.path.exists(mt5_file):
    df = pd.read_csv(mt5_file)
    print("\n--- Top Profitable Symbols (MT5 Only) ---")
    grp = df.groupby('symbol')['profit'].sum().sort_values(ascending=False)
    print(grp.head(10))
    
    print("\n--- Health Simulation for EURNZD ---")
    sym_df = df[df['symbol'] == 'EURNZD'].tail(40)
    total = len(sym_df)
    wins = len(sym_df[sym_df['profit'] > 0])
    p_fact = sym_df[sym_df['profit'] > 0]['profit'].sum() / abs(sym_df[sym_df['profit'] < 0]['profit'].sum())
    print(f"EURNZD: Total {total}, Wins {wins}, PF {p_fact}")
