#!/usr/bin/env python3
"""
NANOBOT AUTO-RETRAIN ML
Objective: Weekly automatic retraining of the Stop Hunt model using 90 days of MT5 data.
Includes model versioning and simple walk-forward validation.
"""
import sys
import os
import pandas as pd
import numpy as np
import logging
import joblib
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

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
PORTFOLIO = [
    "BTCUSD", "AUDUSD", "NZDUSD", "GBPUSD", 
    "GBPJPY", "USDCHF", "EURNZD", "GBPNZD", "USDJPY", "USDCAD"
]
DAYS_BACK = 90
TIMEFRAME_M15 = 15 # Minutes

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
MODEL_FILE = os.path.join(MODEL_DIR, "stop_hunt_rf.joblib")

def get_mt5_data(symbol, days=90):
    """Fetch M15 data from MT5 Bridge."""
    if not mt5.initialize():
        return pd.DataFrame()

    tf = mt5.TIMEFRAME_M15
    count = 4 * 24 * days 
    
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
        
    data = [list(r) for r in rates]
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

def prepare_indicators(df):
    df = df.copy()
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
    
    return df.dropna()

def run_auto_retrain():
    print(f"🔄 STARTING AUTO-RETRAIN (Lookback: {DAYS_BACK} days)")
    print("-" * 50)
    
    if not mt5.initialize():
        print("❌ MT5 Connection Failed.")
        return

    full_X = []
    full_y = []
    model_wrapper = StopHuntModel()
    
    for symbol in PORTFOLIO:
        print(f"📥 Fetching {symbol}...")
        df = get_mt5_data(symbol, days=DAYS_BACK)
        if df.empty: continue
        
        df = prepare_indicators(df)
        
        # Signal Generation + Outcome Labeling
        for i in range(200, len(df)-50):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            sig = 0
            if row['adx'] > 15: # Relaxed HIVE Filter
                if row['ema_9'] > row['ema_15'] and prev['ema_9'] <= prev['ema_15'] and row['close'] > row['ema_200']: sig = 1
                elif row['ema_9'] < row['ema_15'] and prev['ema_9'] >= prev['ema_15'] and row['close'] < row['ema_200']: sig = -1
            
            if sig != 0:
                future = df.iloc[i+1:i+49]
                entry = row['close']
                sl_dist = row['atr'] * 2.0
                tp_dist = sl_dist * 1.5 # RR 1.5
                
                if sig == 1: sl = entry - sl_dist; tp = entry + tp_dist
                else: sl = entry + sl_dist; tp = entry - tp_dist
                
                hit_sl = False; stop_hunt = 0
                for _, f_row in future.iterrows():
                    if sig == 1:
                        if f_row['low'] <= sl: hit_sl = True
                        if f_row['high'] >= tp: 
                            if hit_sl: stop_hunt = 1
                            break
                    else:
                        if f_row['high'] >= sl: hit_sl = True
                        if f_row['low'] <= tp:
                            if hit_sl: stop_hunt = 1
                            break
                
                # Feature Extraction
                slice_df = df.iloc[i-10:i+1]
                indicators = {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']}
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

    if len(full_X) < 100:
        print("❌ Insufficient data points for robust training.")
        return

    X = np.array(full_X)
    y = np.array(full_y)
    
    # Walk-forward-ish: Split last 20% for testing
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    print(f"📊 Training on {len(X_train)} samples, Testing on {len(X_test)} samples...")
    
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42)
    clf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"📈 Test Accuracy: {acc:.2%}")
    print(classification_report(y_test, y_pred))
    
    # Model Versioning (Backup)
    if os.path.exists(MODEL_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{MODEL_FILE}.{timestamp}.bak"
        os.rename(MODEL_FILE, backup_path)
        print(f"📦 Backup created: {os.path.basename(backup_path)}")

    # Save New Model
    joblib.dump(clf, MODEL_FILE)
    print(f"✅ New Model Saved: {os.path.basename(MODEL_FILE)}")
    print(f"   Signals: {len(y)} | Stop Hunts: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")

if __name__ == "__main__":
    run_auto_retrain()
