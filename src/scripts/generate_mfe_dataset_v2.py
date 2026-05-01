import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.nanobot.ml.polimata_v6 import PolimataGeneral

# --- CONFIGURATION ---
DATA_DIR = "data/historical"
OUTPUT_PATH = "data/research/equity_hunter_training_v2.csv"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("DATA_GEN_V2")

def calculate_indicators(df, prefix=""):
    """Calculates granular features for AI training."""
    df = df.copy()
    df[f'{prefix}ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    tr = pd.concat([high_low, abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
    df[f'{prefix}atr'] = tr.rolling(14).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df[f'{prefix}rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    
    # ADX (Simplified)
    diff_h = df['high'].diff()
    diff_l = -df['low'].diff()
    plus_dm = diff_h.where((diff_h > diff_l) & (diff_h > 0), 0)
    minus_dm = diff_l.where((diff_l > diff_h) & (diff_l > 0), 0)
    plus_di = 100 * (plus_dm.rolling(14).mean() / (df[f'{prefix}atr'] + 1e-9))
    minus_di = 100 * (minus_dm.rolling(14).mean() / (df[f'{prefix}atr'] + 1e-9))
    df[f'{prefix}adx'] = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    
    return df

def generate_dataset_v2():
    polimata = PolimataGeneral(model_path="models/polimata_hmm_v1.pkl")
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    master_records = []
    
    for filename in csv_files:
        symbol = filename.split("_")[2]
        path = os.path.join(DATA_DIR, filename)
        logger.info(f"📊 Processing Multi-Timeframe Data for {symbol}...")
        
        # 1. Load M5 Data
        df_m5 = pd.read_csv(path)
        df_m5['time'] = pd.to_datetime(df_m5['time'])
        df_m5 = df_m5.sort_values("time").reset_index(drop=True)
        
        # 2. Resample to H1
        h1_resample = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum'
        }
        df_h1 = df_m5.set_index('time').resample('1h').agg(h1_resample).dropna()
        df_h1 = calculate_indicators(df_h1, prefix="h1_")
        df_h1 = df_h1.reset_index()
        
        # 3. Calculate M5 Indicators
        df_m5 = calculate_indicators(df_m5, prefix="m5_")
        df_m5['m5_ema_3'] = df_m5['close'].ewm(span=3, adjust=False).mean()
        df_m5['m5_ema_9'] = df_m5['close'].ewm(span=9, adjust=False).mean()
        
        # 4. Merge H1 Context into M5
        # We only want the indicator columns from H1, not the raw OHLC to avoid collisions
        h1_cols = ['time'] + [c for c in df_h1.columns if c.startswith('h1_')]
        
        df_master = pd.merge_asof(
            df_m5.sort_values('time'),
            df_h1[h1_cols].sort_values('time'),
            on='time',
            direction='backward'
        )
        
        df_master = df_master.dropna().reset_index(drop=True)
        
        # 5. Identify Signal Crosses
        df_master['prev_ema3'] = df_master['m5_ema_3'].shift(1)
        df_master['prev_ema9'] = df_master['m5_ema_9'].shift(1)
        crosses = df_master[((df_master['prev_ema3'] <= df_master['prev_ema9']) & (df_master['m5_ema_3'] > df_master['m5_ema_9'])) | 
                            ((df_master['prev_ema3'] >= df_master['prev_ema9']) & (df_master['m5_ema_3'] < df_master['m5_ema_9']))].index
        
        for idx in crosses:
            if idx < 100 or idx >= len(df_master) - 50: continue
            
            sig = 1 if df_master['m5_ema_3'].iloc[idx] > df_master['m5_ema_9'].iloc[idx] else -1
            row = df_master.iloc[idx]
            
            # Feature extraction (M5 + H1)
            feature_set = {
                'symbol': symbol,
                'hour': row['time'].hour,
                'm5_adx': row['m5_adx'],
                'm5_rsi': row['m5_rsi'],
                'm5_dist_200': (row['close'] - row['m5_ema_200']) / row['m5_ema_200'],
                'h1_adx': row['h1_adx'],
                'h1_rsi': row['h1_rsi'],
                'h1_dist_200': (row['close'] - row['h1_ema_200']) / row['h1_ema_200'],
                'h1_trend': 1 if (row['close'] > row['h1_ema_200']) else -1,
                'vol_ratio': row['m5_atr'] / row['close'],
                'hmm_regime': polimata.predict_regime(df_m5.iloc[idx-100:idx+1]) # Still use M5 for regime
            }
            
            # Calculate MFE (1.5x ATR Stop Loss)
            sl_dist = row['m5_atr'] * 1.5
            entry_price = df_master['open'].iloc[idx+1]
            sl_price = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            
            max_favorable_dist = 0
            for future_idx in range(idx+1, min(idx + 500, len(df_master))):
                f_row = df_master.iloc[future_idx]
                sl_hit = (f_row['low'] <= sl_price) if sig == 1 else (f_row['high'] >= sl_price)
                if sl_hit: break
                move = (f_row['high'] - entry_price) if sig == 1 else (entry_price - f_row['low'])
                max_favorable_dist = max(max_favorable_dist, move)
            
            feature_set['max_mfe_r'] = max_favorable_dist / (sl_dist + 1e-9)
            master_records.append(feature_set)
            
    # Save V2
    if master_records:
        training_df = pd.DataFrame(master_records)
        training_df.to_csv(OUTPUT_PATH, index=False)
        logger.info(f"✅ Master V2 (H1 Context) Generated: {OUTPUT_PATH} ({len(training_df)} signals)")
    else:
        logger.error("❌ No signals found to record.")

if __name__ == "__main__":
    generate_dataset_v2()
