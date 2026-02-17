#!/usr/bin/env python3
"""
NANOBOT ML TRAINER (60-Day Calibration)
Objective: Retrain Stop Hunt Model using last 60 days of data from FTMO (MT5).
Labeling Logic:
- If Signal -> SL -> Then TP == STOP HUNT (Class 1)
- Otherwise == NORMAL (Class 0)
"""
import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
import joblib

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.stop_hunt_model import StopHuntModel

# Silicon MT5 Integration
try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
except ImportError:
    print("❌ siliconmetatrader5 not found")
    sys.exit(1)

# --- CONFIG ---
# Native MT5 Symbols
PORTFOLIO = [
    "BTCUSD", "SOLUSD", "AUDUSD", "NZDUSD", "GBPUSD", 
    "GBPJPY", "USDCHF", "EURNZD", "GBPNZD", "USDJPY", "USDCAD"
]
DAYS_BACK = 60
TIMEFRAME = 15 # Will be mapped to mt5.TIMEFRAME_M15

def get_mt5_data(symbol, days=60):
    """Fetch M15 data from MT5 Bridge."""
    if not mt5.initialize():
        print(f"❌ MT5 Init Failed for {symbol}")
        return pd.DataFrame()

    # M15 in Minutes = 15. Autoscaling? 
    # mt5.TIMEFRAME_M15 usually is an int constant. 
    # Let's trust the library provides it or we use the int value 15 if supported?
    # Standard MT5 API uses constants. siliconmetatrader5 maps them.
    tf = mt5.TIMEFRAME_M15
    
    # Calculate number of bars approx
    # 4 bars per hour * 24 hours * 60 days = 5760 bars
    # Let's fetch 6000 to be safe
    count = 4 * 24 * days 
    
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
        
    # Convert list of tuples/structs to DF
    # RPyC might return tuples
    data = []
    for r in rates:
        data.append(list(r))
        
    df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    
    return df

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def prepare_data(df):
    # Indicators
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['atr'] = calculate_atr(df)
    
    # ADX
    period = 14
    high = df['high']; low = df['low']; close = df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def train_model():
    print(f"🧠 ML TRAINING STARTED (FTMO Data - Last {DAYS_BACK} Days)...")
    
    if not mt5.initialize():
        print("❌ CRITICAL: Cannot connect to MT5 for Training Data.")
        return

    full_X = []
    full_y = []
    
    model_wrapper = StopHuntModel() # To use extract_features helper
    
    for symbol in PORTFOLIO:
        print(f"   Gathering FTMO data for {symbol}...", end="\r")
        try:
            df = get_mt5_data(symbol, days=DAYS_BACK)
            
            if df.empty: 
                print(f"⚠️ No data for {symbol}")
                continue
                
            df = prepare_data(df)
            
            # Labeling Loop
            for i in range(200, len(df)-50): # Ensure future data exists
                row = df.iloc[i]
                prev = df.iloc[i-1]
                
                # Detect Signal Setup (Technical)
                sig = 0
                if row['adx'] > 25: # Trend
                    if row['ema_9'] > row['ema_15'] and prev['ema_9'] <= prev['ema_15'] and row['close'] > row['ema_200']: sig = 1
                    elif row['ema_9'] < row['ema_15'] and prev['ema_9'] >= prev['ema_15'] and row['close'] < row['ema_200']: sig = -1
                else: # Range
                    if row['rsi'] < 35: sig = 1
                    elif row['rsi'] > 65: sig = -1
                
                if sig != 0:
                    # Potential Trade
                    # Check outcome in next 48 bars (12 hours)
                    future = df.iloc[i+1:i+49]
                    
                    entry = row['close']
                    atr = row['atr']
                    sl_mult = 1.0 if row['adx'] > 25 else 1.5
                    rr = 2.0 if row['adx'] > 25 else 3.0
                    sl_dist = atr * sl_mult
                    
                    if sig == 1: sl = entry - sl_dist; tp = entry + (sl_dist * rr)
                    else: sl = entry + sl_dist; tp = entry - (sl_dist * rr)
                    
                    hit_sl = False
                    hit_tp = False
                    stop_hunt = 0
                    
                    for _, f_row in future.iterrows():
                        if sig == 1:
                            if f_row['low'] <= sl: hit_sl = True
                            if f_row['high'] >= tp: 
                                hit_tp = True
                                if hit_sl: stop_hunt = 1 
                                break
                        else:
                            if f_row['high'] >= sl: hit_sl = True
                            if f_row['low'] <= tp:
                                hit_tp = True
                                if hit_sl: stop_hunt = 1
                                break
                        
                    # Extract Features
                    slice_df = df.iloc[i-10:i+1] # Lookback
                    indicators = {
                        'rsi': row['rsi'],
                        'adx': row['adx'],
                        'atr': row['atr'],
                        'vwap': row['close']
                    }
                    features = model_wrapper.extract_features(slice_df, row['close'], indicators)
                    
                    feat_vector = [
                        features.get('wick_ratio', 0),
                        features.get('volatility_surge', 0),
                        features.get('successive_move', 0),
                        features.get('rsi', 50),
                        features.get('adx', 0)
                    ]
                    
                    full_X.append(feat_vector)
                    full_y.append(stop_hunt)
                    
        except Exception as e:
            print(f"Error {symbol}: {e}")
            
    # Train
    print(f"\n🧠 Training on {len(full_X)} signals from FTMO...")
    if len(full_X) < 50:
        print("❌ Not enough data points to train.")
        return
        
    X = np.array(full_X)
    y = np.array(full_y)
    
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42)
    clf.fit(X, y)
    
    # Save
    import joblib
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models/stop_hunt_rf.joblib")
    joblib.dump(clf, model_path)
    
    print("-" * 50)
    print(f"✅FTMO MODEL RETRAINED & SAVED to models/stop_hunt_rf.joblib")
    print(f"   Total Signals: {len(y)}")
    print(f"   Stop Hunts Found: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
    print("-" * 50)

if __name__ == "__main__":
    train_model()
