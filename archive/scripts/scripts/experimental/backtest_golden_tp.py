#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 3 (TARGET OPTIMIZATION)
Objective: Test if Golden Trades earn more with 3R vs 2R.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np

# Config
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]
PERIOD = "60d"
INTERVAL = "1h"
CAPITAL = 10000
GOLDEN_RISK = 0.006

def get_data():
    print(f"📊 FETCHING DATA FOR TP ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING GOLDEN TP TEST (2R vs 3R)...")
    
    trades_2r = []
    trades_3r = []
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        df['atr'] = atr
        
        # Real ADX
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        
        # Volatility
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # Check Golden
            adx = row['adx']
            vol = row['volatility']
            if not (adx > 27 and vol < 16): continue # Only test Golden Trades
            
            # --- OUTCOME (2R) ---
            current_atr = row['atr']
            sl_dist = current_atr * 1.5
            tp_dist_2r = current_atr * 2.0
            tp_dist_3r = current_atr * 3.0
            
            entry = row['Close']
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            
            # 2R Check
            tp_2r = entry + tp_dist_2r if sig==1 else entry - tp_dist_2r
            outcome_2r = 0 
            future = df.iloc[i+1:i+48]
            for j in range(len(future)):
                fr = future.iloc[j]
                if sig == 1:
                    if fr['Low'] <= sl: outcome_2r = -1; break
                    if fr['High'] >= tp_2r: outcome_2r = 2; break
                else:
                    if fr['High'] >= sl: outcome_2r = -1; break
                    if fr['Low'] <= tp_2r: outcome_2r = 2; break
            
            if outcome_2r != 0:
                pnl = outcome_2r * GOLDEN_RISK * CAPITAL
                if outcome_2r == 2: pnl = (GOLDEN_RISK * CAPITAL * 2.0) # Explicit 2R
                else: pnl = -(GOLDEN_RISK * CAPITAL)
                trades_2r.append(pnl)
                
            # 3R Check (Re-simulate loop for 3R outcome)
            tp_3r = entry + tp_dist_3r if sig==1 else entry - tp_dist_3r
            outcome_3r = 0 
            for j in range(len(future)):
                fr = future.iloc[j]
                if sig == 1:
                    if fr['Low'] <= sl: outcome_3r = -1; break
                    if fr['High'] >= tp_3r: outcome_3r = 3; break # 3R
                else:
                    if fr['High'] >= sl: outcome_3r = -1; break
                    if fr['Low'] <= tp_3r: outcome_3r = 3; break # 3R
            
            if outcome_3r != 0:
                if outcome_3r == 3: pnl = (GOLDEN_RISK * CAPITAL * 3.0)
                else: pnl = -(GOLDEN_RISK * CAPITAL)
                trades_3r.append(pnl)
                    
    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 3: TARGET OPTIMIZATION (Golden Trades Only)")
    print("="*60)
    
    pnl_2r = sum(trades_2r)
    pnl_3r = sum(trades_3r)
    
    print(f"{'METRIC':<15} | {'2.0 R':<12} | {'3.0 R':<12} | {'CHANGE'}")
    print("-" * 60)
    print(f"{'Net Profit':<15} | ${pnl_2r:<11.0f} | ${pnl_3r:<11.0f} | ${pnl_3r-pnl_2r:.0f}")
    
    if pnl_3r > pnl_2r:
        print("✅ SUCCESS: 3R Targets generate MORE Profit!")
    else:
        print("⚠️ FAILURE: 3R Targets reduce Profit (Price doesn't reach).")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
