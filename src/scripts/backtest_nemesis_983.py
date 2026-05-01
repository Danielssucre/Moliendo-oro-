import pandas as pd
import numpy as np
import os
import logging

# --- CONFIG ---
DATA_DIR = "data/historical"
INITIAL_BALANCE = 10000.0
RISK_PER_TRADE = 0.005 # 0.5%
SPREAD_PIPS = 1.2 # Institutional spread
SESSION_START = 6
SESSION_END = 18

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("NEMESIS_983")

def calculate_indicators(df):
    df = df.copy()
    
    # 1. Bollinger Bands 2.5 SD
    sma_20 = df['close'].rolling(window=20).mean()
    std_20 = df['close'].rolling(window=20).std()
    df['upper_bb'] = sma_20 + (2.5 * std_20)
    df['lower_bb'] = sma_20 - (2.5 * std_20)
    
    # 2. RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. ATR 14 (Core of 983 strategy)
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    return df

def run_nemesis_983_backtest():
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    all_trades = []
    
    for file in csv_files:
        symbol = file.split("_")[2]
        logger.info(f"🔎 Simulating Némesis 983 on {symbol}...")
        
        path = os.path.join(DATA_DIR, file)
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'])
        df = calculate_indicators(df)
        df = df.dropna()
        
        for i in range(1, len(df)-100):
            row = df.iloc[i]
            
            # --- NEMESIS 983 TRIGGER (BB 2.5 + RSI) ---
            sig = 0
            if row['close'] > row['upper_bb'] and row['rsi'] > 70:
                sig = -1 # Sell Reversion
            elif row['close'] < row['lower_bb'] and row['rsi'] < 30:
                sig = 1 # Buy Reversion
                
            if sig == 0: continue
            
            # Session Filter (Preserving the 983 Window)
            if not (SESSION_START <= row['time'].hour < SESSION_END): continue
            
            # --- 983 PARAMETERS (A15R25) ---
            entry_price = row['close']
            sl_dist = row['atr'] * 1.5 # SL 1.5x ATR
            tp_dist = sl_dist * 2.5   # RR 2.5 (as per strategy DNA)
            
            sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            tp = entry_price + tp_dist if sig == 1 else entry_price - tp_dist
            
            # Simulation
            pnl_r = 0
            for j in range(i+1, len(df)):
                high, low = df['high'].iloc[j], df['low'].iloc[j]
                if sig == 1: # Buy
                    if low <= sl: pnl_r = -1.1; break
                    if high >= tp: pnl_r = 2.4; break
                else: # Sell
                    if high >= sl: pnl_r = -1.1; break
                    if low <= tp: pnl_r = 2.4; break
            
            if pnl_r != 0:
                all_trades.append({
                    'symbol': symbol,
                    'time': row['time'],
                    'pnl_r': pnl_r
                })

    if not all_trades:
        print("❌ No signals found for Némesis 983.")
        return

    res_df = pd.DataFrame(all_trades)
    dollar_risk = INITIAL_BALANCE * RISK_PER_TRADE
    res_df['dollar_pnl'] = res_df['pnl_r'] * dollar_risk
    res_df = res_df.sort_values('time')
    res_df['balance'] = INITIAL_BALANCE + res_df['dollar_pnl'].cumsum()
    
    print("\n" + "="*80)
    print("💎 RESULTS: NEMESIS 983 (A15R25)")
    print("="*80)
    print(f"Total Trades: {len(res_df)}")
    print(f"Win Rate: {(res_df['pnl_r'] > 0).mean()*100:.2f}%")
    print(f"Profit Factor: {abs(res_df[res_df['pnl_r'] > 0]['pnl_r'].sum() / res_df[res_df['pnl_r'] < 0]['pnl_r'].sum()):.2f}")
    print(f"Final Balance: ${res_df['balance'].iloc[-1]:,.2f}")
    
    os.makedirs("data/research", exist_ok=True)
    res_df.to_csv("data/research/backtest_nemesis_983_results.csv", index=False)
    print("\n✅ Results saved: data/research/backtest_nemesis_983_results.csv")

if __name__ == "__main__":
    run_nemesis_983_backtest()
