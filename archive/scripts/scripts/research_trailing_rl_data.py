#!/usr/bin/env python3
"""
RL Trajectory Extraction Script
Extracts the evolutionary path of trades after hitting the 1.3R partial.
This creates a dataset of (State, Action, Reward) candidates for the RL Agent.
"""
import sys
import os
import pandas as pd
import numpy as np
import logging
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.utils import MT5DataSource

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("RESEARCH_RL")

# --- SETTINGS ---
SYMBOLS = ["AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", "USDCAD"]
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365
PARTIAL_R = 1.3

def calculate_indicators(df):
    df = df.copy()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['ema_9_slope'] = df['ema_9'].diff(3)
    
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    return df

def run_rl_extraction(mt5, symbol):
    logger.info(f"🤖 Sequential RL Extraction for {symbol}...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS + 15)
    
    all_bars = []
    current_end = end_date
    while current_end > start_date:
        batch_start = max(start_date, current_end - timedelta(days=30))
        batch_df = mt5.get_historical_data(symbol, TIMEFRAME, batch_start, current_end)
        if not batch_df.empty:
            all_bars.append(batch_df)
        else:
            break
        current_end = batch_start - timedelta(seconds=1)

    if not all_bars: return []
    df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    df = calculate_indicators(df)
    
    trajectories = []
    last_trade_date = None
    
    for i in range(200, len(df) - 100):
        row = df.iloc[i]
        
        # HIVE Signal
        sig = 0
        if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']: sig = 1
        elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']: sig = -1
        if sig == 0: continue
        
        # Basic Filters
        current_date = row['date'].date()
        if last_trade_date == current_date: continue
        if not (row['vol'] < 18): continue
        
        entry_price = df.iloc[i+1]['open']
        atr = row['atr']
        if pd.isna(atr) or atr == 0: continue
        
        sl_dist = atr * 2.0
        tp_partial = entry_price + (sl_dist * PARTIAL_R) if sig == 1 else entry_price - (sl_dist * PARTIAL_R)
        
        reached_partial = False
        trajectory = []
        
        # Simulate trade lifecycle
        for j in range(i + 1, len(df)):
            m_row = df.iloc[j]
            high, low, close = m_row['high'], m_row['low'], m_row['close']
            
            if not reached_partial:
                # Check hits partial
                if (sig == 1 and high >= tp_partial) or (sig == -1 and low <= tp_partial):
                    reached_partial = True
                    last_trade_date = current_date
                
                # SL before partial
                sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
                if (sig == 1 and low <= sl) or (sig == -1 and high >= sl): break
            else:
                # WE ARE IN THE "RUNNER" PHASE. Record state at each H1 bar.
                current_r = (close - entry_price) / sl_dist if sig == 1 else (entry_price - close) / sl_dist
                max_r_so_far = (high - entry_price) / sl_dist if sig == 1 else (entry_price - low) / sl_dist
                
                state = {
                    'current_r': current_r,
                    'max_r': max_r_so_far,
                    'ema_9_slope': m_row['ema_9_slope'] / atr,
                    'vol': m_row['vol'],
                    'time_hours': (m_row['date'] - entry_time if 'entry_time' in locals() else timedelta(0)).total_seconds() / 3600.0,
                    'atr_norm': atr / close # Volatility measure
                }
                trajectory.append(state)
                
                # Default Exit check (BE)
                sl = entry_price
                if (sig == 1 and low <= sl) or (sig == -1 and high >= sl):
                    break
                
                # Max time cap for safety
                if len(trajectory) > 200: break
                    
        if reached_partial and len(trajectory) > 0:
            trajectories.append({
                'symbol': symbol,
                'entry_time': str(df.iloc[i+1]['date']),
                'history': trajectory,
                'final_outcome_r': trajectory[-1]['current_r']
            })
            
    return trajectories

def main():
    os.makedirs("data/research", exist_ok=True)
    all_trajectories = []
    with MT5DataSource() as mt5:
        if not mt5.connected: return
        for symbol in SYMBOLS:
            all_trajectories.extend(run_rl_extraction(mt5, symbol))
            
    if all_trajectories:
        out_path = "data/research/rl_trajectories_v1.json"
        with open(out_path, 'w') as f:
            json.dump(all_trajectories, f)
        logger.info(f"✅ RL Trajectories Complete: {len(all_trajectories)} sequences saved.")
    else:
        logger.warning("No sequences extracted.")

if __name__ == "__main__":
    main()
