import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.nanobot.utils.mt5_data import MT5DataSource
from src.nanobot.ml.gatekeeper import GatekeeperAgent
from src.nanobot.ml.mfe_sniper import MFESniperManager
from src.nanobot.ml.rl_trailing import RLTrailingManager

# --- CONFIG ---
SYMBOLS = ["AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", "USDCAD"]
LOOKBACK_DAYS = 90
TIMEFRAME = "H1"

def calculate_indicators(df):
    df = df.copy()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX
    period = 14
    high = df['high']; low = df['low']; close = df['close']
    tr_adx = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr_smooth = tr_adx.ewm(alpha=1/period, adjust=False).mean()
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Volatility
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    return df

def run_simulation(symbol, df, use_ai=True):
    # Agents
    gk = GatekeeperAgent() if use_ai else None
    sniper = MFESniperManager() if use_ai else None
    runner = RLTrailingManager() if use_ai else None

    trades = []
    last_trade_date = None
    
    for i in range(len(df) - 50): # Ensure space for trade management
        row = df.iloc[i]
        
        # 1. HIVE Signal
        sig = 0
        if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']: sig = 1
        elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']: sig = -1
        
        if sig == 0: continue
        
        # filters
        if not (row['adx'] > 15 and row['vol'] < 18): continue
        if last_trade_date == row['date'].date(): continue

        # 2. AI Gatekeeper (The Chooser)
        if use_ai and gk and gk.loaded:
            ema_slope = (row['ema_9'] - df.iloc[i-3]['ema_9']) / row['atr'] if row['atr'] > 0 else 0
            action, conf = gk.predict(ema_slope, row['vol'], row['atr']/row['close'], row['date'])
            if action == 0: continue # Rejected by AI
        
        # Entry
        entry_price = df.iloc[i+1]['open']
        entry_time = df.iloc[i+1]['date']
        sl_dist = row['atr'] * 2.0
        sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
        
        # Trade Loop
        pos_open = True
        reached_partial = False
        trade_result = 0.0
        max_r = 0
        min_r = 0
        
        for j in range(i+1, len(df)):
            m_row = df.iloc[j]
            high, low, close = m_row['high'], m_row['low'], m_row['close']
            
            # Calculate current R
            curr_r = (close - entry_price) / sl_dist if sig == 1 else (entry_price - close) / sl_dist
            max_r = max(max_r, (high - entry_price) / sl_dist if sig == 1 else (entry_price - low) / sl_dist)
            min_r = min(min_r, (low - entry_price) / sl_dist if sig == 1 else (entry_price - high) / sl_dist)

            # --- EXIT LOGIC ---
            # 1. SL Check
            if (sig == 1 and low <= sl) or (sig == -1 and high >= sl):
                trade_result += (1.0 - (0.5 if reached_partial else 0.0)) * (-1.0 if not reached_partial else 0.0)
                if reached_partial: trade_result += 0.5 * 1.3 # Add the partial we took
                pos_open = False
            
            # 2. Partial / Management (Before 1.3R)
            if not reached_partial and pos_open:
                if use_ai and sniper and sniper.enabled:
                    ema_9_slope = (m_row['ema_9'] - df.iloc[j-3]['ema_9']) / m_row['atr'] if m_row['atr'] > 0 else 0
                    atr_norm = m_row['atr'] / close if close > 0 else 0.001
                    action = sniper.get_action(curr_r, max_r, ema_9_slope, m_row['vol'], atr_norm)
                    if action == 1: # Partial
                        reached_partial = True
                        trade_result += 0.5 * curr_r
                        sl = entry_price # Move to BE
                    elif action == 2: # Full close
                        trade_result = curr_r
                        pos_open = False
                else: # Baseline: 1.3R Fixed
                    if max_r >= 1.3:
                        reached_partial = True
                        trade_result += 0.5 * 1.3
                        sl = entry_price
            
            # 3. Runner Management (After Partial)
            if reached_partial and pos_open:
                if use_ai and runner and runner.enabled:
                    # RL Trailing Manager
                    ema_9_slope = (m_row['ema_9'] - df.iloc[j-3]['ema_9']) / m_row['atr'] if m_row['atr'] > 0 else 0
                    current_sl_r = 0 # It's at BE
                    action = runner.get_action(curr_r, max_r, ema_9_slope, m_row['vol'], m_row['atr']/close, 0)
                    if action == 2: # Close
                        trade_result += 0.5 * curr_r
                        pos_open = False
                    elif action == 1: # Move Stop
                        sl = entry_price + (sl_dist * (curr_r - 0.5)) if sig == 1 else entry_price - (sl_dist * (curr_r - 0.5))
                else: # Baseline: Fixed 3.1R
                    if max_r >= 3.1:
                        trade_result += 0.5 * 3.1
                        pos_open = False
            
            if not pos_open:
                trades.append(trade_result)
                last_trade_date = row['date'].date()
                break
                
    return trades

def calculate_mdd(results):
    if not results: return 0.0
    equity = np.cumsum(results)
    running_max = np.maximum.accumulate(equity)
    drawdown = running_max - equity
    return np.max(drawdown)

def main():
    print(f"🚀 Starting Comparative Backtest ({LOOKBACK_DAYS} days)")
    all_results_baseline = []
    all_results_ai = []
    
    with MT5DataSource() as mt5:
        for symbol in SYMBOLS:
            print(f"⌛ Fetching {symbol}...")
            df = mt5.get_historical_data(symbol, TIMEFRAME, datetime.now() - timedelta(days=LOOKBACK_DAYS+10), datetime.now())
            if df.empty: continue
            df = calculate_indicators(df)
            
            res_base = run_simulation(symbol, df, use_ai=False)
            res_ai = run_simulation(symbol, df, use_ai=True)
            
            all_results_baseline.extend(res_base)
            all_results_ai.extend(res_ai)
            print(f"   [{symbol}] Baseline: {sum(res_base):.2f}R | AI: {sum(res_ai):.2f}R")

    print("\n" + "="*50)
    print("🏆 FINAL COMPARISON RESULTS (90 DAYS)")
    print("="*50)
    print(f"{'Metric':<20} | {'Baseline (Fixed)':<15} | {'AI (Full Stack)':<15}")
    print("-" * 50)
    print(f"{'Total Trades':<20} | {len(all_results_baseline):<15} | {len(all_results_ai):<15}")
    print(f"{'Total R Profit':<20} | {sum(all_results_baseline):<15.2f} | {sum(all_results_ai):<15.2f}")
    if len(all_results_baseline) > 0 and len(all_results_ai) > 0:
        print(f"{'Avg R per Trade':<20} | {np.mean(all_results_baseline):<15.2f} | {np.mean(all_results_ai):<15.2f}")
        print(f"{'Win Rate (R>0)':<20} | {len([r for r in all_results_baseline if r > 0])/len(all_results_baseline):<15.1%} | {len([r for r in all_results_ai if r > 0])/len(all_results_ai):<15.1%}")
        
        mdd_base = calculate_mdd(all_results_baseline)
        mdd_ai = calculate_mdd(all_results_ai)
        print(f"{'Max Drawdown (R)':<20} | {mdd_base:<15.2f} | {mdd_ai:<15.2f}")
        print(f"{'Profit/DD Ratio':<20} | {sum(all_results_baseline)/mdd_base if mdd_base > 0 else 0:<15.2f} | {sum(all_results_ai)/mdd_ai if mdd_ai > 0 else 0:<15.2f}")
    print("="*50)

if __name__ == "__main__":
    main()
