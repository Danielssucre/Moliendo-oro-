import pandas as pd
import numpy as np
import os
import logging

# --- CONFIG ---
DATA_DIR = "data/historical"
INITIAL_BALANCE = 200000.0 # Match the FTMO account
RISK_PER_TRADE = 0.0125    # 1.25% (0.5% base * 2.5x Bayesian Mult)
TIMEFRAME = "H1"           # Institutional context

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("NEMESIS_CHAMPION")

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
    
    # 3. ATR 14
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    return df

def run_champion_backtest():
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    all_trades = []
    
    for file in csv_files:
        symbol = file.split("_")[2]
        logger.info(f"🏆 Simulating Némesis CAMPEÓN on {symbol}...")
        
        path = os.path.join(DATA_DIR, file)
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'])
        df = calculate_indicators(df)
        df = df.dropna()
        
        for i in range(1, len(df)-100):
            row = df.iloc[i]
            
            # --- CHAMPION TRIGGER (BB 2.5 + RSI EXTREME) ---
            # Using higher RSI thresholds for 'Champion' conviction
            sig = 0
            if row['close'] > row['upper_bb'] and row['rsi'] > 75:
                sig = -1 # Sell Top
            elif row['close'] < row['lower_bb'] and row['rsi'] < 25:
                sig = 1 # Buy Bottom
                
            if sig == 0: continue
            
            # --- CHAMPION PARAMETERS (ATR BASED) ---
            entry_price = row['close']
            sl_dist = row['atr'] * 1.5
            tp_dist = sl_dist * 2.5 # RR 2.5 aiming for PF > 2.0
            
            sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            tp = entry_price + tp_dist if sig == 1 else entry_price - tp_dist
            
            # Simulated Execution with 1.25% Risk
            pnl_r = 0
            for j in range(i+1, len(df)):
                high, low = df['high'].iloc[j], df['low'].iloc[j]
                if sig == 1: # Buy
                    if low <= sl: pnl_r = -1.0; break
                    if high >= tp: pnl_r = 2.5; break
                else: # Sell
                    if high >= sl: pnl_r = -1.0; break
                    if low <= tp: pnl_r = 2.5; break
            
            if pnl_r != 0:
                # Lot Calculation for record
                # Lot = (Balance * 0.0125) / (SL_Dist * Multiplier)
                # Since we are working with R-units, we store pnl_r.
                all_trades.append({
                    'symbol': symbol,
                    'time': row['time'],
                    'pnl_r': pnl_r,
                    'is_winner': pnl_r > 0
                })

    if not all_trades:
        print("❌ No signals found for Némesis Campeón.")
        return

    res_df = pd.DataFrame(all_trades)
    dollar_risk = INITIAL_BALANCE * RISK_PER_TRADE
    res_df['dollar_pnl'] = res_df['pnl_r'] * dollar_risk
    res_df = res_df.sort_values('time')
    res_df['balance'] = INITIAL_BALANCE + res_df['dollar_pnl'].cumsum()
    
    # Filtering for March 2026 if available to see the "Friday 13" effect
    march_stats = res_df[res_df['time'].dt.month == 3]
    
    print("\n" + "="*80)
    print("💎 FINAL PERFORMANCE: NÉMESIS CAMPEÓN (1.25% Risk)")
    print("="*80)
    print(f"Total Trades: {len(res_df)}")
    print(f"Win Rate: {res_df['is_winner'].mean()*100:.2f}%")
    print(f"Profit Factor: {abs(res_df[res_df['pnl_r'] > 0]['pnl_r'].sum() / res_df[res_df['pnl_r'] < 0]['pnl_r'].sum()):.2f}")
    print(f"Final Balance: ${res_df['balance'].iloc[-1]:,.2f}")
    print(f"Total Profit: ${res_df['balance'].iloc[-1] - INITIAL_BALANCE:,.2f}")
    
    if not march_stats.empty:
        print("\n🔎 March 2026 Snapshot:")
        print(f"  PnL March: ${march_stats['dollar_pnl'].sum():,.2f}")
    
    os.makedirs("data/research", exist_ok=True)
    res_df.to_csv("data/research/backtest_nemesis_champion_results.csv", index=False)
    print("\n✅ Champion Ledger saved: data/research/backtest_nemesis_champion_results.csv")

if __name__ == "__main__":
    run_champion_backtest()
