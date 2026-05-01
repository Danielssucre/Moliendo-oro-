"""
QUANTUM FORENSIC RESEARCHER v2.3 — HYPER-GRANULAR AUDIT
Calculates hypothesis tests for EVERY Strategy-Symbol pair in the unified dataset.
"""
import pandas as pd
import numpy as np
from scipy import stats
import os, warnings
warnings.filterwarnings('ignore')

# --- CONFIGURATION (Re-using loading logic from massive_audit_engine.py) ---
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

def load_all():
    # Helper to load and tag
    def l_axi():
        if not os.path.exists(AXI_FILE): return pd.DataFrame()
        df = pd.read_csv(AXI_FILE)
        opens = df[df['entry'] == 0][['position_id','comment']].rename(columns={'comment':'strategy'})
        closes = df[(df['entry'] == 1) & (df['profit'] != 0)][['position_id','time','symbol','profit']]
        res = closes.merge(opens, on='position_id', how='left').reset_index(drop=True)
        return res
    
    def l_ft_a():
        if not os.path.exists(FTMO_ANALYZED): return pd.DataFrame()
        df = pd.read_csv(FTMO_ANALYZED)
        return df.rename(columns={'comment_entry':'strategy'})[['symbol','profit','strategy']].reset_index(drop=True)
    
    def l_ft_r():
        if not os.path.exists(FTMO_RECENT): return pd.DataFrame()
        df = pd.read_csv(FTMO_RECENT)
        return df[df['profit']!=0].rename(columns={'comment':'strategy'})[['symbol','profit','strategy']].reset_index(drop=True)

    def l_bn():
        if not os.path.exists(BURNED_ACCOUNT): return pd.DataFrame()
        df = pd.read_csv(BURNED_ACCOUNT).rename(columns={'config':'strategy'})[['symbol','profit','strategy']].reset_index(drop=True)
        return df

    def l_sh():
        if not os.path.exists(SHADOW_GRID): return pd.DataFrame()
        sh_df = pd.read_csv(SHADOW_GRID).rename(columns={'config':'strategy', 'outcome_r': 'profit'})[['symbol','profit','strategy']].reset_index(drop=True)
        return sh_df

    # Load and clean each
    dfs = []
    names = ["AXI", "FTA", "FTR", "BN", "SH"]
    loaders = [l_axi, l_ft_a, l_ft_r, l_bn, l_sh]
    
    for i, loader in enumerate(loaders):
        df_tmp = loader()
        if not df_tmp.empty:
            df_tmp = df_tmp.loc[:, ~df_tmp.columns.duplicated()] # Deduplicate columns
            df_tmp['source'] = names[i]
            dfs.append(df_tmp[['symbol', 'profit', 'strategy', 'source']].reset_index(drop=True))
            
    if not dfs: return pd.DataFrame()
    
    master = pd.concat(dfs, ignore_index=True)
    master['strategy'] = master['strategy'].apply(parse_strat)
    return master[master['strategy'] != 'OTHER']

def hyper_granular_audit():
    df = load_all()
    results = []
    
    # ── HYPOTHESIS TESTING PER (STRAT, SYMBOL) ─────────────────────────────────
    for (strat, symbol), sub in df.groupby(['strategy', 'symbol']):
        n = len(sub)
        avg = sub['profit'].mean()
        std = sub['profit'].std()
        
        # Win Rate
        wr = len(sub[sub['profit'] > 0]) / n
        
        # P-Value (H0: Mean <= 0)
        if n >= 2:
            t_stat, p_val = stats.ttest_1samp(sub['profit'], 0)
            p_one_tail = p_val/2 if avg > 0 else 1 - (p_val/2)
        else:
            p_one_tail = np.nan
            
        # CVaR (95%)
        # Simple implementation: Average of the worst 5% of trades
        if n >= 5:
            worst_5pct = int(np.ceil(n * 0.05))
            cvar_95 = sub['profit'].nsmallest(worst_5pct).mean()
        else:
            cvar_95 = np.nan
            
        # Expectancy: (WR * AvgW) - (LR * AvgL) -- Or simply the mean
        expectancy = avg
        
        # Veredicto (Fino-Granular)
        if n < 5:
            verdict = "⚠️ Tiny Sample"
        elif n < 12:
            verdict = "🔍 Low Sample (Test)"
        elif p_one_tail < 0.01 and avg > 0:
            verdict = "💎 SURVIVOR (Holy Grail)"
        elif p_one_tail < 0.05 and avg > 0:
            verdict = "🟢 SURVIVOR (Base Edge)"
        elif p_one_tail < 0.15 and avg > 0:
            verdict = "🟡 Promising (Watch)"
        elif avg < 0 and p_one_tail > 0.90:
            verdict = "💀 ZOMBIE (Surgical Stop)"
        elif avg < 0 and p_one_tail > 0.70:
            verdict = "🔴 Toxic (Avoid)"
        else:
            verdict = "⚪ No Edge (Noise)"
            
        results.append({
            'Strategy': strat,
            'Symbol': symbol,
            'N': n,
            'EV': expectancy,
            'WR': f"{wr*100:.0f}%",
            'CVaR 95%': cvar_95,
            'P-Val': f"{p_one_tail:.4f}",
            'Verdict': verdict
        })
        
    res_df = pd.DataFrame(results).sort_values(['Strategy', 'N'], ascending=[True, False])
    
    # --- MARKDOWN OUTPUT ---
    print("# 🔬 Auditoría Forense Hiper-Granular (788 trades)")
    print("\nAnálisis estadístico masivo de cada combinación Sistema-Par. Basado en Axi + FTMO + Burned History.")
    
    for strat in ['NEME', 'ALFA', 'EXPL', 'WINNER', 'KAIDO']:
        print(f"\n## 🤖 Bot: {strat}")
        subset = res_df[res_df['Strategy'] == strat].copy()
        if subset.empty: 
            print("No se encontraron trades para este bot.")
            continue
            
        # Sort by verdict quality
        subset['_sort'] = subset['Verdict'].map({
            "💎 SURVIVOR (Holy Grail)": 0,
            "🟢 SURVIVOR (Base Edge)": 1,
            "🟡 Promising (Watch)": 2,
            "⚪ No Edge (Noise)": 3,
            "🔍 Low Sample (Test)": 4,
            "⚠️ Tiny Sample": 5,
            "🔴 Toxic (Avoid)": 6,
            "💀 ZOMBIE (Surgical Stop)": 7
        })
        subset = subset.sort_values('_sort')
        
        table = subset[['Symbol', 'N', 'EV', 'WR', 'CVaR 95%', 'P-Val', 'Verdict']]
        from tabulate import tabulate
        print(tabulate(table, headers='keys', tablefmt='github', showindex=False))

    # --- CROSS-SYSTEM TOXICITY ---
    print("\n## ☢️ Toxicidad Cruzada: Pares Inoperables")
    print("Pares que son 'Zombies' o 'Toxic' en múltiples sistemas (Prohibición Institucional).")
    toxic_pairs = res_df[res_df['Verdict'].isin(['💀 ZOMBIE (Surgical Stop)', '🔴 Toxic (Avoid)'])]
    toxic_summary = toxic_pairs.groupby('Symbol')['Strategy'].count().sort_values(ascending=False)
    
    blacklist = []
    for sym, count in toxic_summary.items():
        if count >= 2:
            avg_ev = res_df[res_df['Symbol'] == sym]['EV'].mean()
            blacklist.append({'Symbol': sym, 'Bot Failures': count, 'Avg EV Global': avg_ev})
    
    if blacklist:
        from tabulate import tabulate
        print(tabulate(pd.DataFrame(blacklist), headers='keys', tablefmt='github', showindex=False))

if __name__ == "__main__":
    hyper_granular_audit()
