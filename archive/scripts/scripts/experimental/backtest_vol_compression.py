#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 13 (THE DEAD ZONE)
Objective: Test Extreme Volatility Compression (< 5).
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
RISK_GOLD = 0.006

def get_data():
    print(f"📊 FETCHING DATA FOR COMPRESSION ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING DEAD ZONE TEST (Vol < 5)...")
    
    trades_dead = []
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr1 = tr.rolling(14).mean()
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            vol = row['volatility']
            
            # CONDITION: DEAD ZONE (Extreme Compression)
            # Threshold: 5.0 (Very low)
            if vol < 5.0:
                # We need a breakout trigger.
                # Standard Signal?
                sig = 0
                if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
                elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
                
                if sig != 0:
                     # Calculate PnL (Use Golden Sizing/Target because it's Golden-like)
                     atr_val = atr1.iloc[i]
                     entry = row['Close']
                     sl_dist = atr_val * 1.5
                     tp_dist = atr_val * 3.0 # Expect explosion
                     
                     sl = entry - sl_dist if sig==1 else entry + sl_dist
                     tp = entry + tp_dist if sig==1 else entry - tp_dist
                     
                     outcome = 0 
                     future = df.iloc[i+1:i+48]
                     for j in range(len(future)):
                         fr = future.iloc[j]
                         if sig == 1:
                             if fr['Low'] <= sl: outcome = -1; break
                             if fr['High'] >= tp: outcome = 1; break
                         else:
                             if fr['High'] >= sl: outcome = -1; break
                             if fr['Low'] <= tp: outcome = 1; break
                    
                     if outcome != 0:
                         pnl = (RISK_GOLD * CAPITAL * 3.0) if outcome==1 else -(RISK_GOLD * CAPITAL)
                         trades_dead.append(pnl)

    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 13: THE DEAD ZONE (Extreme Compression)")
    print("="*60)
    
    net_pnl = sum(trades_dead)
    count = len(trades_dead)
    
    print(f"{'METRIC':<15} | {'VALUE':<15}")
    print("-" * 40)
    print(f"{'Trades Found':<15} | {count:<15}")
    print(f"{'Net Profit':<15} | ${net_pnl:<15.0f}")
    
    if count > 10 and net_pnl > 0:
        print("✅ SUCCESS: Dead Zone Breakouts are Real!")
    else:
        print("⚠️ FAILURE: Too rare or didn't work.")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
