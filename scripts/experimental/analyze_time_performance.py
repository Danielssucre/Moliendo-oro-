#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 2 (TIME ANALYSIS)
Objective: Identify "Toxic Hours" where expectancy is negative.
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
RISK_PER_TRADE = 0.004 # 0.4%
CAPITAL = 10000

def get_data():
    print(f"📊 FETCHING DATA FOR TIME ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def analyze_time(data_map):
    print("\n⏳ ANALYZING PERFORMANCE BY HOUR...")
    
    hourly_pnl = {h: [] for h in range(24)}
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            hour = row.name.hour
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig != 0:
                atr_val = atr.iloc[i]
                entry = row['Close']
                sl = entry - (atr_val*1.5) if sig==1 else entry + (atr_val*1.5)
                tp = entry + (atr_val*2.0) if sig==1 else entry - (atr_val*2.0)
                
                outcome = 0
                future = df.iloc[i+1:i+48]
                for j in range(len(future)):
                    fr = future.iloc[j]
                    if sig == 1:
                        if fr['Low'] <= sl: outcome = -1; break
                        if fr['High'] >= tp: outcome = 2; break
                    else:
                        if fr['High'] >= sl: outcome = -1; break
                        if fr['Low'] <= tp: outcome = 2; break
                
                if outcome != 0:
                    pnl = outcome * RISK_PER_TRADE * CAPITAL
                    hourly_pnl[hour].append(pnl)
                    
    # Report
    print("\n" + "="*40)
    print(f"⏰ PnL BY HOUR OF DAY (UTC)")
    print("="*40)
    print(f"{'HOUR':<6} | {'TRADES':<8} | {'NET PnL':<10} | {'AVG per Trade'}")
    print("-" * 40)
    
    toxic_hours = []
    
    for h in sorted(hourly_pnl.keys()):
        trades = hourly_pnl[h]
        if not trades: continue
        net = sum(trades)
        count = len(trades)
        avg = net / count
        
        tag = ""
        if avg < -5: tag = "⚠️ TOXIC"
        elif avg > 20: tag = "🌟 PRIME"
        
        if avg < -10: toxic_hours.append(h)
        
        print(f"{h:02d}:00  | {count:<8} | ${net:<9.0f} | ${avg:<5.1f} {tag}")
        
    print("\n💀 TOXIC HOURS (Avoid):", toxic_hours)
    
    return toxic_hours

if __name__ == "__main__":
    d = get_data()
    analyze_time(d)
