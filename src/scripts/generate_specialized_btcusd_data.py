
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.utils.mt5_data import MT5DataSource
from src.nanobot.ml.stop_hunt import StopHuntModel

# --- CONFIGURATION ---
SYMBOL = "BTCUSD"
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365
OUTPUT_PATH = "data/research/risk_specialized_btcusd_v1.csv"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("BTCUSD_DATA_GEN")

def calculate_technical_indicators(df):
    df = df.copy()
    # EMA for signal logic
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX (Robust)
    period = 14
    tr_adx = tr
    atr_smooth = tr_adx.ewm(alpha=1/period, adjust=False).mean()
    up = df['high'].diff(); down = -df['low'].diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Volatility
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    return df

def generate_signals():
    stop_hunt_model = StopHuntModel()
    
    with MT5DataSource() as mt5:
        if not mt5.connected:
            logger.error("MT5 Connection Failed")
            return

        logger.info(f"🚀 Fetching {LOOKBACK_DAYS} days of history for {SYMBOL}...")
        end_date_abs = datetime.now()
        start_date_abs = end_date_abs - timedelta(days=LOOKBACK_DAYS + 10)
        
        all_bars = []
        current_end = end_date_abs
        while current_end > start_date_abs:
            batch_start = max(start_date_abs, current_end - timedelta(days=30))
            logger.info(f"   Fetching batch: {batch_start.date()} to {current_end.date()}")
            batch_df = mt5.get_historical_data(SYMBOL, TIMEFRAME, batch_start, current_end)
            if not batch_df.empty:
                all_bars.append(batch_df)
            else:
                logger.warning(f"   No more history available before {batch_start.date()}")
                break
            current_end = batch_start - timedelta(seconds=1)

        if not all_bars:
            logger.error("No data fetched.")
            return

        df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)

        df = calculate_technical_indicators(df)
        df = df.dropna().reset_index(drop=True)
        
        records = []
        last_trade_date = None
        
        for i in range(50, len(df) - 48): # Need buffer for future outcome
            row = df.iloc[i]
            
            # HIVE V5 Signal Check
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']:
                sig = 1
            elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']:
                sig = -1
                
            if sig == 0: continue
            
            # Filter matches live bot (15/18)
            if not (row['adx'] > 15 and row['vol'] < 18):
                continue

            current_date = row['date'].date()
            if last_trade_date == current_date: continue

            # Extract features for StopHuntModel
            # Mocking indicators dict as in run_live
            inds = {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']}
            features = stop_hunt_model.extract_features(df.iloc[:i+1], row['close'], inds)
            ml_risk_score = stop_hunt_model.predict_risk(features)
            prob_success = 1.0 - ml_risk_score

            # Simulation for outcome_r (Target 1.5R)
            entry_price = df.iloc[i+1]['open']
            sl_dist = row['atr'] * 2.0
            tp_dist = sl_dist * 1.5
            
            if sig == 1:
                sl = entry_price - sl_dist
                tp = entry_price + tp_dist
            else:
                sl = entry_price + sl_dist
                tp = entry_price - tp_dist
                
            outcome_r = -1.0
            found = False
            
            # Future lookahead
            for j in range(i+1, i+48):
                f_row = df.iloc[j]
                if sig == 1:
                    if f_row['low'] <= sl: 
                        outcome_r = -1.0
                        found = True
                        break
                    if f_row['high'] >= tp:
                        outcome_r = 1.5
                        found = True
                        break
                else:
                    if f_row['high'] >= sl:
                        outcome_r = -1.0
                        found = True
                        break
                    if f_row['low'] <= tp:
                        outcome_r = 1.5
                        found = True
                        break
            
            if not found:
                # Terminal close at 48h
                final_price = df.iloc[i+47]['close']
                outcome_r = ((final_price - entry_price) / sl_dist) if sig == 1 else ((entry_price - final_price) / sl_dist)

            records.append({
                "symbol": SYMBOL,
                "prob": prob_success,
                "adx": row['adx'],
                "rsi": row['rsi'],
                "vol": row['vol'],
                "outcome_r": outcome_r
            })
            last_trade_date = current_date

        dataset_df = pd.DataFrame(records)
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        dataset_df.to_csv(OUTPUT_PATH, index=False)
        logger.info(f"✅ Specialized Dataset for {SYMBOL} created at {OUTPUT_PATH}")
        logger.info(f"📈 Total signals recorded: {len(dataset_df)}")

if __name__ == "__main__":
    generate_signals()
