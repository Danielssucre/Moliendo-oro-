#!/usr/bin/env python3
"""
Trailing Research Script - forensic Dataset Extraction (V4 - Infinite MFE + Advanced Features)
Extracts FULL potential (MFE) for trades that reached 1.3R.
Includes slopes and RSI for NN training.
"""
import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.utils import MT5DataSource

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("RESEARCH_INFINITE")

# --- SETTINGS ---
SYMBOLS = ["AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", "USDCAD"]
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365
PARTIAL_R = 1.3
INFINITE_MAX_R = 50.0

def calculate_indicators(df):
    df = df.copy()
    # EMAs
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Slopes (3-bar)
    df['ema_9_slope'] = df['ema_9'].diff(3) 
    df['ema_15_slope'] = df['ema_15'].diff(3)
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # RSI
    close = df['close']
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    period = 14
    high = df['high']; low = df['low']
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

    return df

def run_extraction_for_symbol(mt5, symbol):
    logger.info(f"♾️  Infinite Deep Extraction for {symbol}...")
    
    end_date_absolute = datetime.now()
    start_date_absolute = end_date_absolute - timedelta(days=LOOKBACK_DAYS + 15)
    
    all_bars = []
    current_end = end_date_absolute
    
    while current_end > start_date_absolute:
        batch_start = max(start_date_absolute, current_end - timedelta(days=30))
        batch_df = mt5.get_historical_data(symbol, TIMEFRAME, batch_start, current_end)
        if not batch_df.empty:
            all_bars.append(batch_df)
        else:
            break
        current_end = batch_start - timedelta(seconds=1)

    if not all_bars: return []
        
    df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    df = calculate_indicators(df)
    
    dataset = []
    last_trade_date = None
    
    for i in range(200, len(df) - 100):
        row = df.iloc[i]
        
        # HIVE V5 Signal
        sig = 0
        if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']: sig = 1
        elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']: sig = -1
        if sig == 0: continue
        
        # Constraints
        current_date = row['date'].date()
        if last_trade_date == current_date: continue
        if not (row['adx'] > 15 and row['vol'] < 18): continue
        
        # Entry Setup
        entry_price = df.iloc[i+1]['open']
        entry_time = df.iloc[i+1]['date']
        atr = row['atr']
        if pd.isna(atr) or atr == 0: continue
        
        sl_dist = atr * 2.0
        tp_partial = entry_price + (sl_dist * PARTIAL_R) if sig == 1 else entry_price - (sl_dist * PARTIAL_R)
        
        reached_partial = False
        max_mfe_r = 0.0
        
        # Evolution (Infinite)
        for j in range(i + 1, len(df)):
            m_row = df.iloc[j]
            high, low = m_row['high'], m_row['low']
            
            if not reached_partial:
                if (sig == 1 and high >= tp_partial) or (sig == -1 and low <= tp_partial):
                    reached_partial = True
                    last_trade_date = current_date
                    
                    # Capture Features at Moment of Partial
                    features = {
                        'symbol': symbol,
                        'entry_time': entry_time,
                        'partial_time': m_row['date'],
                        'direction': 'BUY' if sig == 1 else 'SELL',
                        'hour': m_row['date'].hour,
                        'adx_partial': m_row['adx'],
                        'rsi_partial': m_row['rsi'],
                        'vol_partial': m_row['vol'],
                        'ema_9_slope': m_row['ema_9_slope'] / atr,
                        'ema_15_slope': m_row['ema_15_slope'] / atr,
                        'dist_ema200': abs(m_row['close'] - m_row['ema_200']) / atr,
                    }
                
                # SL check before partial
                sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
                if (sig == 1 and low <= sl) or (sig == -1 and high >= sl): break
            else:
                m_high, m_low = m_row['high'], m_row['low']
                current_exc = (m_high - entry_price) / sl_dist if sig == 1 else (entry_price - m_low) / sl_dist
                max_mfe_r = max(max_mfe_r, current_exc)
                
                # Check BE Exit
                sl = entry_price
                if (sig == 1 and low <= sl) or (sig == -1 and high >= sl):
                    break
                    
                if max_mfe_r >= INFINITE_MAX_R: break
                    
        if reached_partial:
            features['max_mfe_r'] = max_mfe_r
            dataset.append(features)
            
    return dataset

def main():
    os.makedirs("data/research", exist_ok=True)
    all_data = []
    with MT5DataSource() as mt5:
        if not mt5.connected: return
        for symbol in SYMBOLS:
            all_data.extend(run_extraction_for_symbol(mt5, symbol))
            
    if all_data:
        res_df = pd.DataFrame(all_data)
        out_path = "data/research/infinite_mfe_dataset_v2.csv"
        res_df.to_csv(out_path, index=False)
        logger.info(f"✅ Infinite Deep Extraction Complete: {len(res_df)} samples saved.")
    else:
        logger.warning("No data extracted.")

if __name__ == "__main__":
    main()
