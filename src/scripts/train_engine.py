"""
Trainer Script for ENGINE (XGBoost Predictive Model)
=====================================================
Extracts OHLCV data, computes indicators (Feature Engineering), 
labels target logic, and trains the XGBoost model.
"""

import sys
import os
import pandas as pd
import numpy as np
import xgboost as xgb
import argparse
import joblib

# Ensure path is recognizable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Optionally use MT5
try:
    import siliconmetatrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../models'))
os.makedirs(MODELS_DIR, exist_ok=True)

def featurize(df):
    """
    EXACT replica of run_live.py's math calculations to prevent data mismatch.
    """
    df = df.copy()
    
    # EMAs
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = abs(minus_dm)
    tr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / (tr_smooth + 1e-9))
    minus_di = 100 * (minus_dm.rolling(14).mean() / (tr_smooth + 1e-9))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.rolling(14).mean()
    
    # Bollinger Bands
    df['bb_mid'] = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + (std * 2)
    df['bb_lower'] = df['bb_mid'] - (std * 2)

    return df

def generate_labels(df, forward_bars=5, profit_target=0.002, stop_loss=0.001):
    """
    Generates ternary target labels:
    1: Buy (Hit Profit Target without hitting Stop Loss first)
    -1: Sell (Hit Profit Target downwards without hitting Stop Loss upwards)
    0: Neutral (Neither hit, or chopped out)
    """
    labels = pd.Series(0, index=df.index)
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    
    for i in range(len(df) - forward_bars - 1):
        entry_price = close[i]
        
        # Look ahead
        success_buy = False
        success_sell = False
        
        for j in range(1, forward_bars + 1):
            future_high = high[i + j]
            future_low = low[i + j]
            
            # Did it hit buy target?
            if future_high >= entry_price * (1 + profit_target):
                success_buy = True
            # Did it hit stop loss for buy?
            if future_low <= entry_price * (1 - stop_loss):
                success_buy = False # Dead
                break
                
        for j in range(1, forward_bars + 1):
            future_low = low[i + j]
            future_high = high[i + j]
            
            # Did it hit sell target?
            if future_low <= entry_price * (1 - profit_target):
                success_sell = True
            # Did it hit stop loss for sell?
            if future_high >= entry_price * (1 + stop_loss):
                success_sell = False # Dead
                break
        
        if success_buy and not success_sell:
            labels.iloc[i] = 1
        elif success_sell and not success_buy:
            labels.iloc[i] = -1
        else:
            labels.iloc[i] = 0
            
    return labels

def build_features(df):
    """
    Convert raw priced indicators into normalized ML features.
    """
    features = pd.DataFrame(index=df.index)
    
    # Normalized EMAs
    features['dist_ema5'] = (df['close'] - df['ema_5']) / df['close']
    features['dist_ema15'] = (df['close'] - df['ema_15']) / df['close']
    features['dist_ema200'] = (df['close'] - df['ema_200']) / df['close']
    
    # Slopes
    features['slope_ema15'] = (df['ema_15'] - df['ema_15'].shift(3)) / df['ema_15'].shift(3)
    
    # Pure indicators
    features['rsi'] = df['rsi']
    features['adx'] = df['adx']
    
    # Relative ATR
    features['atr_rel'] = df['atr'] / df['close']
    
    # BB Bandwidth
    features['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
    features['bb_pos'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-9)
    
    return features.dropna()

def train_engine_for_symbol(symbol: str, bars=10000):
    print(f"🚀 Training ENGINE for {symbol} on {bars} bars...")
    
    df = None
    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../../data/historical/MT5_5M_{symbol}_Exchange_Rate_Dataset.csv"))

    if os.path.exists(csv_path):
        print(f"📂 Loading data from static CSV: {csv_path}")
        df = pd.read_csv(csv_path)
        
        # Determine column for time
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        # Ensure column names are lower case
        df.columns = df.columns.str.lower()
    else:
        print(f"❌ Could not find CSV at {csv_path} and MT5 is offline/unsupported here. Fallback failed.")
        return
        
    if df is None or len(df) == 0:
        print("❌ No data received.")
        return

    # Process
    print("⚙️ Engineering Features...")
    df = featurize(df)
    
    print("🏷️ Labeling Targets (Aggressive Scalping Profile)...")
    # Aggressive Scalping target: +0.15% Profit, -0.10% Stop
    df['target'] = generate_labels(df, forward_bars=5, profit_target=0.0015, stop_loss=0.0010)
    
    # Extract features
    features = build_features(df)
    
    # Align target
    aligned_target = df['target'].loc[features.index]
    
    # Convert labels from (-1, 0, 1) to (0, 1, 2) since XGBoost expects [0, num_class)
    y_mapped = aligned_target.map({-1: 0, 0: 1, 1: 2})
        
    # Drop ultimate N bars that haven't matured
    X = features.iloc[:-10]
    y = y_mapped.iloc[:-10]
    
    print(f"📊 Training shape: {X.shape}. Class distribution:")
    print(y.value_counts())
    
    # Train XGBoost
    print("🧠 Training XGBoost MultiClass Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=100, 
        max_depth=4, 
        learning_rate=0.05, 
        objective='multi:softprob',
        num_class=3,
        random_state=42
    )
    
    model.fit(X, y)
    
    # Save Model
    model_path = os.path.join(MODELS_DIR, f"engine_v1_{symbol}.xgb")
    model.save_model(model_path)
    print(f"✅ ENGINE Model Exported to: {model_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ENGINE XGBoost Model")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Symbol to train (e.g. BTCUSD)")
    parser.add_argument("--bars", type=int, default=100000, help="Number of bars to use")
    
    args = parser.parse_args()
    train_engine_for_symbol(args.symbol, bars=args.bars)
