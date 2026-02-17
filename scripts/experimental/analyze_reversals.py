#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 6 (CONTRARIAN)
Objective: Test Mean Reversion profitability in Ranges (Low ADX).
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
RISK_PER_TRADE = 0.004
CAPITAL = 10000

def get_data():
    print(f"📊 FETCHING DATA FOR REVERSAL ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING MEAN REVERSION TEST...")
    
    trades_reversal = []
    
    for symbol, df in data_map.items():
        # RSI
        delta = df['Close'].diff()
        u = delta.clip(lower=0); d = -1 * delta.clip(upper=0)
        rs = u.ewm(com=13, adjust=False).mean() / d.ewm(com=13, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ADX/ATR
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
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            adx = row['adx']
            rsi = row['rsi']
            
            # CONDITION: Range (Low ADX) + Extreme RSI
            if adx < 25:
                sig = 0
                if rsi < 30: sig = 1 # Buy the Dip
                elif rsi > 70: sig = -1 # Sell the Rip
                
                if sig != 0:
                     # Calculate PnL
                     atr_val = atr.iloc[i]
                     entry = row['Close']
                     sl_dist = atr_val * 1.5
                     tp_dist = atr_val * 1.5 # 1:1 for Reversion (quick scalp)
                     
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
                         pnl = outcome * RISK_PER_TRADE * CAPITAL
                         trades_reversal.append(pnl)

    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 6: REVERSAL STRATEGY (RSI Extemes in Range)")
    print("="*60)
    
    net_pnl = sum(trades_reversal)
    count = len(trades_reversal)
    wins = trades_reversal.count(RISK_PER_TRADE * CAPITAL)
    wr = (wins/count*100) if count else 0
    
    print(f"{'METRIC':<15} | {'VALUE':<15}")
    print("-" * 40)
    print(f"{'Trades Found':<15} | {count:<15}")
    print(f"{'Win Rate':<15} | {wr:<15.1f}%")
    print(f"{'Net Profit':<15} | ${net_pnl:<15.0f}")
    
    if net_pnl > 0 and wr > 50:
        print("✅ SUCCESS: Reversion is Profitable!")
    else:
        print("⚠️ FAILURE: Don't fight the trend (even in ranges).")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
