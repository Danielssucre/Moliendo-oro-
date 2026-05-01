import pandas as pd
import numpy as np
from scipy import stats
import os

# --- CONFIGURE PATHS ---
DATA_DIR = "data/research"
CSV_FILES = [
    "recent_ftmo_history.csv",
    "recovered_lhn_burned_account.csv", 
    "axi_history_extract.csv",
    "analyzed_ftmo_history.csv"
]

def analyze():
    print("🔬 INITIALIZING QUANTUM FORENSIC RESEARCHER...")
    data = []
    
    for f in CSV_FILES:
        path = os.path.join(DATA_DIR, f)
        if not os.path.exists(path): continue
        
        try:
            df = pd.read_csv(path)
            # Standardize columns: We need 'profit' and 'comment/strategy'
            col_map = {
                'time': 'timestamp', 'timestamp': 'timestamp',
                'comment': 'strategy', 'config': 'strategy', 'strategy': 'strategy',
                'profit': 'profit', 'outcome_r': 'profit'
            }
            df = df.rename(columns=col_map)
            df = df[[c for c in df.columns if c in col_map.values()]]
            if 'profit' in df.columns:
                df['profit'] = pd.to_numeric(df['profit'], errors='coerce')
                df = df.dropna(subset=['profit'])
                if 'timestamp' in df.columns:
                    df['dt'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                    if df['dt'].isna().all(): df['dt'] = pd.to_datetime(df['timestamp'], errors='coerce')
                data.append(df)
        except: continue

    if not data: return print("❌ No valid data found for analysis.")
    
    master = pd.concat(data, ignore_index=True).sort_values('dt')
    master['cum_profit'] = master['profit'].cumsum()
    
    print(f"📊 Processed {len(master)} trades. Final PnL: ${master['profit'].sum():.2f}")

    # ⚔️ THESIS VS ANTITHESIS
    print("\n--- STATISTICAL HYPOTHESIS TESTING ---")
    results = []
    for strat in ["ALFA", "NEME", "WINN", "EXPL"]:
        subset = master[master['strategy'].str.contains(strat, na=False, case=False)]
        if len(subset) < 10: continue
        
        avg = subset['profit'].mean()
        t_stat, p_val = stats.ttest_1samp(subset['profit'], 0)
        ci = stats.t.interval(0.95, len(subset)-1, loc=avg, scale=stats.sem(subset['profit']))
        
        print(f"[{strat}] N={len(subset)} | Avg=${avg:.2f} | P-Value={p_val:.4f}")
        print(f"       95% CI: [{ci[0]:.2f}, {ci[1]:.2f}]")
        results.append({'strat': strat, 'p': p_val, 'avg': avg})

    # 📈 REGIME ANALYSIS
    peak_idx = master['cum_profit'].idxmax()
    peak_dt = master.iloc[peak_idx]['dt']
    print(f"\n🚀 Performance Peak: {peak_dt}")
    
    pre = master[master['dt'] <= peak_dt]
    post = master[master['dt'] > peak_dt]
    print(f"✨ Ascent Phase: Avg Prof ${pre['profit'].mean():.2f}")
    print(f"📉 Drawdown Phase: Avg Prof ${post['profit'].mean():.2f}")

if __name__ == "__main__": analyze()
