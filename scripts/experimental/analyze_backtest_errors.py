#!/usr/bin/env python3
"""
NANOBOT HIVE ANALYSIS: ERROR PATTERN RECOGNITION
Objective: Identify specific conditions that lead to LOSSES to create a 'Failure Filter'.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Add src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Config
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]
PERIOD = "60d"
INTERVAL = "1h"

def get_data_and_features():
    print(f"📊 FETCHING DATA FOR HIVE ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
        
    print("\n🧠 EXTRACTING FEATURES & LABELS...")
    dataset = []
    
    for symbol, df in data.items():
        # Features
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        
        # RSI
        delta = df['Close'].diff()
        u = delta.clip(lower=0); d = -1 * delta.clip(upper=0)
        rs = u.ewm(com=13, adjust=False).mean() / d.ewm(com=13, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ADX (Simple)
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        df['atr'] = atr
        
        # Rolling Volatility (std dev of returns)
        df['volatility'] = df['Close'].pct_change().rolling(24).std()
        
        # Time Features
        df['hour'] = df.index.hour
        
        # Simulate Trades
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            
            # Simplified Strategy Trigger
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1 # Trend Buy
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1 # Trend Sell
            
            if sig != 0:
                # Outcome (Did it hit TP or SL?)
                atr_val = atr.iloc[i]
                entry = row['Close']
                sl = entry - (atr_val*1.5) if sig==1 else entry + (atr_val*1.5)
                tp = entry + (atr_val*2.0) if sig==1 else entry - (atr_val*2.0)
                
                outcome = 0 # 0=Loss, 1=Win
                future = df.iloc[i+1:i+48]
                for j in range(len(future)):
                    fr = future.iloc[j]
                    if sig == 1:
                        if fr['Low'] <= sl: outcome = 0; break
                        if fr['High'] >= tp: outcome = 1; break
                    else:
                        if fr['High'] >= sl: outcome = 0; break
                        if fr['Low'] <= tp: outcome = 1; break
                
                # Append to Dataset
                dataset.append({
                    "rsi": row['rsi'],
                    "adx": row['atr'] / row['Close'] * 10000, # Normalized ATR as pseudo-ADX
                    "volatility": row['volatility'] * 1000,
                    "hour": row['hour'],
                    "asset_id": ASSETS.index(symbol), # 0=GBP, 1=AUD...
                    "outcome": outcome
                })
                
    return pd.DataFrame(dataset)

def train_failure_detector(df):
    print(f"\n🐝 HIVE INTELLIGENCE: ANALYZING {len(df)} TRADES...")
    
    X = df.drop(columns=['outcome'])
    y = df['outcome']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train Decision Tree (Max Depth 3 for interpretability)
    clf = DecisionTreeClassifier(max_depth=3, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    acc = accuracy_score(y_test, clf.predict(X_test))
    print(f"   Model Accuracy (Predicting W/L): {acc*100:.1f}%")
    
    # Feature Importance
    print("\n🔍 FEATURE IMPORTANCE (What causes failure?):")
    imps = clf.feature_importances_
    features = X.columns
    for f, i in zip(features, imps):
        print(f"   - {f}: {i*100:.1f}%")
        
    # Analyze The Tree Rules
    print("\n📜 DECISION RULES (The 'Why'):")
    tree_rules = export_text(clf, feature_names=list(X.columns))
    print(tree_rules)
    
    return clf

if __name__ == "__main__":
    df = get_data_and_features()
    if not df.empty:
        train_failure_detector(df)
    else:
        print("❌ Not enough data.")
