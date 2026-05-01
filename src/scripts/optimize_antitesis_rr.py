import pandas as pd
import numpy as np
import os
import logging
from src.nanobot.ml.polimata_v6 import PolimataGeneral

# --- CONFIG ---
DATA_DIR = "data/historical"
RR_RANGE = np.arange(1.0, 5.1, 0.1) # 1.0 to 5.0 in 0.1 steps
SPREAD_PIPS = 1.5
SESSION_START = 6
SESSION_END = 18

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("OPTIMIZER")

def calculate_indicators(df):
    df = df.copy()
    df['ema_3'] = df['close'].ewm(span=3, adjust=False).mean()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # RSI (Simple)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def run_rr_optimization():
    polimata = PolimataGeneral()
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    
    optimization_ledger = []
    
    for file in csv_files:
        symbol = file.split("_")[2]
        logger.info(f"📊 Optimizing {symbol}...")
        
        path = os.path.join(DATA_DIR, file)
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'])
        df = calculate_indicators(df)
        df = df.dropna()
        
        # 1. Identify all POTENTIAL Antítesis signals
        # A signal is an EMA 3/9 cross approved by Polimata as ANTITESIS
        for i in range(1, len(df)-100): # Small buffer for trade duration
            row = df.iloc[i]
            
            # EMA Cross detection
            prev_e3, e3 = df['ema_3'].iloc[i-1], df['ema_3'].iloc[i]
            prev_e9, e9 = df['ema_9'].iloc[i-1], df['ema_9'].iloc[i]
            
            sig = 0
            if prev_e3 <= prev_e9 and e3 > e9: sig = 1
            if prev_e3 >= prev_e9 and e3 < e9: sig = -1
            
            if sig == 0: continue
            
            # Session Filter
            if not (SESSION_START <= row['time'].hour < SESSION_END): continue
            
            # [BYPASS AUDIT FOR RR DISCOVERY]
            # We want to see the performance of ALL Antítesis signals at different RRs
            # decision = polimata.evaluate_signal(symbol, -sig, "ANTITESIS", df.iloc[:i+1])
            pass

            
            # --- We found an Antítesis Trade! Now test all RRs ---
            entry_price = row['close']
            sl_dist = row['atr'] * 1.5
            pips_in_point = 10 if ("USD" in symbol and "JPY" not in symbol) else 1
            spread = SPREAD_PIPS * (df['close'].iloc[i] * 0.0001) / pips_in_point
            
            sl = entry_price - sl_dist if -sig == 1 else entry_price + sl_dist
            
            # Forward scan for SL/TP hits
            for rr in RR_RANGE:
                tp_dist = sl_dist * rr
                tp = entry_price + tp_dist if -sig == 1 else entry_price - tp_dist
                
                # Check results for this specific RR
                trade_pnl_r = 0
                for j in range(i+1, len(df)):
                    high, low = df['high'].iloc[j], df['low'].iloc[j]
                    
                    if -sig == 1: # Buy
                        if low <= sl: trade_pnl_r = -1.1; break # -1 + spread
                        if high >= tp: trade_pnl_r = rr - 0.1; break # rr - spread
                    else: # Sell
                        if high >= sl: trade_pnl_r = -1.1; break
                        if low <= tp: trade_pnl_r = rr - 0.1; break
                
                optimization_ledger.append({
                    'rr_test': round(rr, 1),
                    'pnl_r': trade_pnl_r
                })

    # --- AGGREGATE RESULTS ---
    if not optimization_ledger:
        print("❌ No Antítesis signals found in the specified session times.")
        return

    res_df = pd.DataFrame(optimization_ledger)
    final_stats = res_df.groupby('rr_test')['pnl_r'].agg([

        ('trades', 'count'),
        ('win_rate', lambda x: (x > 0).mean() * 100),
        ('total_r', 'sum'),
        ('avg_r', 'mean'),
        ('profit_factor', lambda x: abs(x[x > 0].sum() / (x[x < 0].sum() + 1e-9)))
    ]).reset_index()
    
    os.makedirs("data/research", exist_ok=True)
    final_stats.to_csv("data/research/antitesis_rr_optimization.csv", index=False)
    
    print("\n" + "="*80)
    print("🎯 ANTITESIS RR OPTIMIZATION RESULTS")
    print("="*80)
    print(final_stats.sort_values('total_r', ascending=False).head(10))
    print("\n✅ Optimization Report Saved: data/research/antitesis_rr_optimization.csv")

if __name__ == "__main__":
    run_rr_optimization()
