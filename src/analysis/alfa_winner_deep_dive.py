import pandas as pd
import numpy as np
from scipy import stats
import os
import re

# --- CONFIGURE PATHS ---
DATA_DIR = "data/research"
CSV_FILES = [
    "recent_ftmo_history.csv",
    "recovered_lhn_burned_account.csv", 
    "axi_history_extract.csv",
    "analyzed_ftmo_history.csv"
]

def parse_strat(comment):
    if not isinstance(comment, str): return "OTHER"
    c = comment.upper()
    if "ALFA" in c: return "ALFA"
    if "WINNER" in u"WINN" in c: return "WINNER"
    return "OTHER"

def load_data():
    dfs = []
    col_map = {
        'time': 'timestamp', 'timestamp': 'timestamp',
        'comment': 'comment', 'config': 'comment', 'strategy': 'strategy',
        'profit': 'profit', 'outcome_r': 'profit',
        'symbol': 'symbol'
    }
    
    for f in CSV_FILES:
        path = os.path.join(DATA_DIR, f)
        if not os.path.exists(path): continue
        try:
            df = pd.read_csv(path)
            df = df.rename(columns=col_map)
            df = df[[c for c in df.columns if c in col_map.values()]]
            if 'profit' in df.columns:
                df['profit'] = pd.to_numeric(df['profit'], errors='coerce')
                df = df.dropna(subset=['profit'])
                df['strat'] = df['comment'].fillna(df.get('strategy', '')).apply(parse_strat)
                data_subset = df[df['strat'].isin(['ALFA', 'WINNER'])]
                dfs.append(data_subset)
        except: continue

    if not dfs: return None
    return pd.concat(dfs, ignore_index=True)

def deep_dive():
    print("🔬 ANALYZING ALFA & WINNER GRANULARITY...")
    df = load_data()
    if df is None:
        print("❌ No data found.")
        return

    results = []
    # Hypothesis testing per (strat, symbol)
    for (s, sym), sub in df.groupby(['strat', 'symbol']):
        if len(sub) < 5: continue # Minimum 5 trades
        
        avg = sub['profit'].mean()
        std = sub['profit'].std()
        t_stat, p_val = stats.ttest_1samp(sub['profit'], 0) # Testing for mean != 0
        # For one-tailed (mean > 0), use p_val/2 if avg > 0
        p_val_one_tailed = p_val / 2 if avg > 0 else 1 - (p_val / 2)
        ci = stats.t.interval(0.95, len(sub)-1, loc=avg, scale=stats.sem(sub['profit']))
        wr = len(sub[sub['profit'] > 0]) / len(sub)
        
        results.append({
            'Strategy': s,
            'Symbol': sym,
            'N': len(sub),
            'WR': wr,
            'Avg': avg,
            'P-Val (One-Tail > 0)': p_val_one_tailed,
            'CI_Low': ci[0],
            'CI_High': ci[1]
        })

    res_df = pd.DataFrame(results).sort_values('Avg', ascending=False)
    
    print("\n--- ✅ TOP POSITIVE PAIRS (POTENTIAL SURVIVORS) ---")
    survivors = res_df[res_df['P-Val (One-Tail > 0)'] < 0.05]
    print(survivors.to_string(index=False))
    
    print("\n--- ❌ BOTTOM NEGATIVE PAIRS (ZOMBIES) ---")
    zombies = res_df[res_df['P-Val (One-Tail > 0)'] > 0.95]
    print(zombies.to_string(index=False))

if __name__ == "__main__":
    deep_dive()
