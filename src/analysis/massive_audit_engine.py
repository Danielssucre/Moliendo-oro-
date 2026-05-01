"""
QUANTUM FORENSIC RESEARCHER v2.2 — UNIFIED MASSIVE AUDIT
Unifies Axi, FTMO (Recent/Analyzed), Burned Account, and Shadow Grid data.
Analyzes ~1,942 trades to re-validate system hypotheses.
"""
import pandas as pd
import numpy as np
from scipy import stats
import os, re, warnings
warnings.filterwarnings('ignore')

# --- CONFIGURATION ---
DATA_DIR = "data/research"
AXI_FILE = os.path.join(DATA_DIR, "axi_history_extract.csv")
FTMO_ANALYZED = os.path.join(DATA_DIR, "analyzed_ftmo_history.csv")
FTMO_RECENT = os.path.join(DATA_DIR, "recent_ftmo_history.csv")
BURNED_ACCOUNT = os.path.join(DATA_DIR, "recovered_lhn_burned_account.csv")
SHADOW_GRID = os.path.join(DATA_DIR, "shadow_grid_results.csv")

def parse_strat(comment):
    if not isinstance(comment, str): return "OTHER"
    c = comment.upper()
    if "NEME" in c or "NEMESIS" in c: return "NEME"
    if "ALFA" in c: return "ALFA"
    if "EXPL" in c: return "EXPL"
    if "WINNER" in c or "WINN" in c: return "WINNER"
    if "KAIDO" in c: return "KAIDO"
    return "OTHER"

def load_axi():
    if not os.path.exists(AXI_FILE): return pd.DataFrame()
    df = pd.read_csv(AXI_FILE)
    df['time'] = pd.to_datetime(df['time'])
    # Join open/close to get strategy
    opens = df[df['entry'] == 0][['position_id','comment']].rename(columns={'comment':'strategy'})
    closes = df[(df['entry'] == 1) & (df['profit'] != 0)][['position_id','time','symbol','profit']]
    res = closes.merge(opens, on='position_id', how='left').reset_index(drop=True)
    res['source'] = 'AXI'
    return res

def load_ftmo_analyzed():
    if not os.path.exists(FTMO_ANALYZED): return pd.DataFrame()
    df = pd.read_csv(FTMO_ANALYZED)
    df = df.rename(columns={'comment_entry':'strategy'})
    df['source'] = 'FTMO_ANALYZED'
    return df[['symbol','profit','strategy','source']].reset_index(drop=True)

def load_ftmo_recent():
    if not os.path.exists(FTMO_RECENT): return pd.DataFrame()
    df = pd.read_csv(FTMO_RECENT)
    df = df[df['profit'] != 0]
    df = df.rename(columns={'comment':'strategy'})
    df['source'] = 'FTMO_RECENT'
    return df[['symbol','profit','strategy','source']].reset_index(drop=True)

def load_burned():
    if not os.path.exists(BURNED_ACCOUNT): return pd.DataFrame()
    df = pd.read_csv(BURNED_ACCOUNT)
    df = df.rename(columns={'config':'strategy'})
    df['source'] = 'BURNED_ACCOUNT'
    return df[['symbol','profit','strategy','source']].reset_index(drop=True)

def load_shadow():
    if not os.path.exists(SHADOW_GRID): return pd.DataFrame()
    df = pd.read_csv(SHADOW_GRID)
    df = df.rename(columns={'config':'strategy', 'outcome_r': 'profit'}) # outcome_r is P/L or R? 
    # Check if outcome_r is in R units or Dollars.
    df['source'] = 'SHADOW_GRID'
    return df[['symbol','profit','strategy','source']].reset_index(drop=True)

def run_massive_audit():
    print("🚀 UNIFYING MASSIVE DATASET...")
    axi = load_axi()
    ft_a = load_ftmo_analyzed()
    ft_r = load_ftmo_recent()
    bn = load_burned()
    sh = load_shadow()
    
    all_dfs = [axi, ft_a, ft_r, bn, sh]
    valid_dfs = []
    for i, df_item in enumerate(all_dfs):
        name = ["AXI", "FT_A", "FT_R", "BN", "SH"][i]
        if not df_item.empty:
            print(f"  - {name}: {df_item.shape} columns: {list(df_item.columns)}")
            # Deduplicate columns if any
            if df_item.columns.duplicated().any():
                print(f"    ⚠️ Warning: {name} has duplicated columns! Deduplicating...")
                df_item = df_item.loc[:, ~df_item.columns.duplicated()]
            valid_dfs.append(df_item)
        else:
            print(f"  - {name}: EMPTY")
    
    if not valid_dfs:
        print("❌ No valid data found in any source.")
        return

    master = pd.concat(valid_dfs, ignore_index=True)
    master['strategy'] = master['strategy'].apply(parse_strat)
    master = master[master['strategy'] != 'OTHER']
    
    # Filter 2: Recent Axi (for contrast)
    recent_mask = (master['source'] == 'AXI')
    historical_mask = (master['source'] != 'AXI') # Simplified

    print(f"📊 Total Master Trades: {len(master)}")
    print(f"📊 Historical Trades: {len(master[historical_mask])}")
    print(f"📊 Recent Axi Trades: {len(master[recent_mask])}")
    
    results = []
    # Analyze by strategy
    for strat in ['ALFA','NEME','EXPL','WINNER','KAIDO']:
        s_data = master[master['strategy'] == strat]
        if s_data.empty: continue
        
        # Hist vs Recent
        hist = s_data[s_data['source'] != 'AXI']['profit']
        rece = s_data[s_data['source'] == 'AXI']['profit']
        
        hist_ev = hist.mean() if not hist.empty else np.nan
        rece_ev = rece.mean() if not rece.empty else np.nan
        
        # Whole population test
        avg = s_data['profit'].mean()
        t_stat, p_val = stats.ttest_1samp(s_data['profit'], 0)
        p_one_tail = p_val/2 if avg > 0 else 1 - (p_val/2)
        
        sh_ratio = (avg / s_data['profit'].std() * np.sqrt(252)) if s_data['profit'].std() > 0 else 0
        wr = len(s_data[s_data['profit'] > 0]) / len(s_data)

        results.append({
            'Strategy': strat,
            'Total_N': len(s_data),
            'Hist_EV': hist_ev,
            'Recent_EV': rece_ev,
            'Global_EV': avg,
            'WinRate': wr,
            'Sharpe': sh_ratio,
            'P-Val_Edge': p_one_tail
        })

    res_df = pd.DataFrame(results).sort_values('P-Val_Edge')
    print("\n" + "="*80)
    print(" STRATEGY RESILIENCE MATRIX (Contrast: Hist vs Recent)")
    print("="*80)
    print(res_df.to_string(index=False))
    
    # ── PER-PAIR DEEP DIVE (Survivor vs Zombies) ─────────────────────────────────
    pair_res = []
    for (strat, symbol), sub in master.groupby(['strategy', 'symbol']):
        if len(sub) < 10: continue
        avg = sub['profit'].mean()
        t_stat, p_val = stats.ttest_1samp(sub['profit'], 0)
        p_one_tail = p_val/2 if avg > 0 else 1 - (p_val/2)
        
        pair_res.append({
            'Strat': strat,
            'Symbol': symbol,
            'N': len(sub),
            'Avg': avg,
            'P-Val': p_one_tail
        })
    
    pair_df = pd.DataFrame(pair_res).sort_values('P-Val')
    print("\n" + "="*80)
    print(" TOP 15 SURVIVOR PAIRS (Global Population)")
    print("="*80)
    print(pair_df.head(15).to_string(index=False))
    
    print("\n" + "="*80)
    print(" WORST 15 ZOMBIE PAIRS (Global Population)")
    print("="*80)
    print(pair_df.tail(15).to_string(index=False))

if __name__ == "__main__":
    run_massive_audit()
