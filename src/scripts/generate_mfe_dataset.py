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
OUTPUT_PATH = "data/research/equity_hunter_training_v1.csv"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("DATA_GEN")

def calculate_indicators(df):
    """Calculates granular features for AI training."""
    df = df.copy()
    df['ema_3'] = df['close'].ewm(span=3, adjust=False).mean()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['ema_800'] = df['close'].ewm(span=800, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    tr = pd.concat([high_low, abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    
    # ADX
    plus_dm = (df['high'].diff()).where(lambda x: (x > 0) & (x > -(df['low'].diff())), 0)
    minus_dm = (-df['low'].diff()).where(lambda x: (x > 0) & (x > df['high'].diff()), 0)
    df['adx'] = 100 * (plus_dm.rolling(14).mean() / (df['atr'] + 1e-9)) # Simplified DI+
    
    # Slopes and Gaps
    df['ema9_slope'] = df['ema_9'].diff() / df['close']
    df['dist_200'] = (df['close'] - df['ema_200']) / df['ema_200']
    df['ema3_9_gap'] = (df['ema_3'] - df['ema_9']) / df['close']
    
    return df

def generate_dataset():
    polimata = PolimataGeneral(model_path="models/polimata_hmm_v1.pkl")
    
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    master_records = []
    
    for filename in csv_files:
        symbol = filename.split("_")[2]
        path = os.path.join(DATA_DIR, filename)
        logger.info(f"💾 Harvesting data from {symbol}...")
        
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values("time").reset_index(drop=True)
        df = calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)
        
        # Precompute crossover signals
        df['prev_ema3'] = df['ema_3'].shift(1)
        df['prev_ema9'] = df['ema_9'].shift(1)
        crosses = df[((df['prev_ema3'] <= df['prev_ema9']) & (df['ema_3'] > df['ema_9'])) | 
                     ((df['prev_ema3'] >= df['prev_ema9']) & (df['ema_3'] < df['ema_9']))].index
        
        for idx in crosses:
            if idx < 100 or idx >= len(df) - 50: continue
            
            sig = 1 if df['ema_3'].iloc[idx] > df['ema_9'].iloc[idx] else -1
            row = df.iloc[idx]
            
            # Feature extraction
            feature_set = {
                'symbol': symbol,
                'hour': df['time'].iloc[idx].hour,
                'adx': row['adx'],
                'rsi': row['rsi'],
                'dist_200': row['dist_200'],
                'ema9_slope': row['ema9_slope'],
                'gap': row['ema3_9_gap'],
                'vol_ratio': row['atr'] / row['close'],
                'hmm_regime': polimata.predict_regime(df.iloc[idx-100:idx+1])
            }
            
            # Calculate MFE (Maximum Favorable Excursion)
            # Find how far price goes before hitting 1.5x ATR Stop Loss
            sl_dist = row['atr'] * 1.5
            entry_price = df['open'].iloc[idx+1]
            sl_price = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            
            max_favorable_dist = 0
            
            for future_idx in range(idx+1, min(idx + 500, len(df))): # Look up to 500 bars ahead
                f_row = df.iloc[future_idx]
                
                # Check for SL Hit
                sl_hit = (f_row['low'] <= sl_price) if sig == 1 else (f_row['high'] >= sl_price)
                if sl_hit:
                    break
                    
                # Track MFE
                if sig == 1:
                    move = f_row['high'] - entry_price
                else:
                    move = entry_price - f_row['low']
                
                max_favorable_dist = max(max_favorable_dist, move)
            
            # Normalize MFE to R-Units
            feature_set['max_mfe_r'] = max_favorable_dist / sl_dist
            master_records.append(feature_set)
            
    # Save to CSV
    if master_records:
        training_df = pd.DataFrame(master_records)
        training_df.to_csv(OUTPUT_PATH, index=False)
        logger.info(f"✅ Master Training Dataset Generated: {OUTPUT_PATH} ({len(training_df)} signals recorded)")
    else:
        logger.error("❌ No signals found to record.")

if __name__ == "__main__":
    generate_dataset()
