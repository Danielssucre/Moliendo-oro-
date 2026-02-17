#!/usr/bin/env python3
"""
NANOBOT HIVE V2: ALPHA HUNTER
Objective: Identify conditions that lead to BIG WINS (>2R) to implement Dynamic Sizing.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split

# Add src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Config
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]
PERIOD = "60d"
INTERVAL = "1h"

def get_data_and_features():
    print(f"📊 FETCHING DATA FOR HIVE V2...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
        
    print("\n🧠 EXTRACTING 'HOME RUN' FEATURES...")
    dataset = []
    
    for symbol, df in data.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        
        # RSI
        delta = df['Close'].diff()
        u = delta.clip(lower=0); d = -1 * delta.clip(upper=0)
        rs = u.ewm(com=13, adjust=False).mean() / d.ewm(com=13, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ADX (Standard)
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        
        # Volatility
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000 # Scaled
        
        # Simulate Trades
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig != 0:
                # Outcome
                atr_val = atr.iloc[i]
                entry = row['Close']
                sl = entry - (atr_val*1.5) if sig==1 else entry + (atr_val*1.5)
                tp = entry + (atr_val*2.0) if sig==1 else entry - (atr_val*2.0)
                
                # Check outcome
                outcome = 0 # 0=Neutral/Loss
                future = df.iloc[i+1:i+48]
                for j in range(len(future)):
                    fr = future.iloc[j]
                    if sig == 1:
                        if fr['Low'] <= sl: outcome = 0; break
                        if fr['High'] >= tp: outcome = 1; break # WIN
                    else:
                        if fr['High'] >= sl: outcome = 0; break
                        if fr['Low'] <= tp: outcome = 1; break # WIN
                
                dataset.append({
                    "rsi": row['rsi'],
                    "adx": row['adx'],
                    "volatility": row['volatility'],
                    "outcome": outcome
                })
                
    return pd.DataFrame(dataset)

def train_alpha_hunter(df):
    print(f"\n🐝 HIVE V2: HUNTING FOR ALPHA PARAMETERS ({len(df)} Trades)...")
    
    X = df.drop(columns=['outcome'])
    y = df['outcome']
    
    # Train Decision Tree
    clf = DecisionTreeClassifier(max_depth=3, random_state=42, class_weight='balanced')
    clf.fit(X, y)
    
    # Analyze Rules
    print("\n📜 WINNING CONDITIONS (Where is the 💰?):")
    print(export_text(clf, feature_names=list(X.columns)))
    
    # Feature Importance
    print("\n🔍 DRIVER IMPORTANCE:")
    for f, i in zip(X.columns, clf.feature_importances_):
        print(f"   - {f}: {i*100:.1f}%")

if __name__ == "__main__":
    df = get_data_and_features()
    if not df.empty:
        train_alpha_hunter(df)
