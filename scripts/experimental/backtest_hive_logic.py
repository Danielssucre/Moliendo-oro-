#!/usr/bin/env python3
"""
NANOBOT HIVE BACKTEST (A/B Comparison)
Objective: Prove HIVE Logic superiority over Standard Logic (60 Days).
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
    print(f"📊 FETCHING DATA (60 Days)...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING HIVE A/B TEST...")
    
    # Results containers
    trades_std = []
    trades_hive = []
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        
        # RSI
        delta = df['Close'].diff()
        u = delta.clip(lower=0); d = -1 * delta.clip(upper=0)
        rs = u.ewm(com=13, adjust=False).mean() / d.ewm(com=13, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ADX/ATR
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        df['atr'] = atr
        
        # Simple ADX proxy (ATR/Close ratio relative to history matches concept)
        # But let's use the explicit logic from before if possible
        # Actually, let's just use the features we have available.
        # Volatility Filter needs rolling mean of ATR
        df['avg_atr'] = df['atr'].rolling(24).mean()
        # Mock ADX for simulation speed (using Volatility as proxy for ADX? No, they are opposite often)
        # Let's compute Real ADX quickly
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm > 0] = 0
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr)
        minus_di = 100 * abs(minus_dm.ewm(alpha=1/14).mean() / atr)
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
        df['adx'] = dx.ewm(alpha=1/14).mean()
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            
            # --- SIGNAL GENERATION (Standard) ---
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # --- FILTERS (HIVE RELAXED) ---
            is_hive_valid = True
            
            # 1. RSI Cap (Relaxed to 75/25)
            # The previous 65/35 killed momentum trades.
            if (sig == 1 and row['rsi'] > 75) or (sig == -1 and row['rsi'] < 25):
                is_hive_valid = False
                
            # 2. ADX Fatigue (REMOVED)
            # "Trend is your friend". Cutting at 50 was a mistake.
            # if row['adx'] > 50: is_hive_valid = False
            
            # 3. Whipsaw (High Vol / Low ADX) -> KEEP
            current_atr = row['atr']
            avg_atr = row['avg_atr']
            if current_atr > (avg_atr * 2.0) and row['adx'] < 20:
                is_hive_valid = False
                
            # --- OUTCOME ---
            sl_dist = current_atr * 1.5
            tp_dist = current_atr * 2.0
            entry = row['Close']
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            tp = entry + tp_dist if sig==1 else entry - tp_dist
            
            outcome = 0 
            # Check future
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
                # Add to Standard
                trades_std.append(pnl)
                # Add to HIVE (if valid)
                if is_hive_valid:
                    trades_hive.append(pnl)
                    
    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE vs STANDARD COMPARISON (60 Days)")
    print("="*60)
    
    # Calc Metrics
    std_pnl = sum(trades_std)
    std_count = len(trades_std)
    std_win = trades_std.count(RISK_PER_TRADE * CAPITAL * 2)
    std_wr = (std_win / std_count * 100) if std_count else 0
    std_dd = 0 # (Simplified, max streak)
    
    hive_pnl = sum(trades_hive)
    hive_count = len(trades_hive)
    hive_win = trades_hive.count(RISK_PER_TRADE * CAPITAL * 2)
    hive_wr = (hive_win / hive_count * 100) if hive_count else 0
    
    print(f"{'METRIC':<15} | {'STANDARD':<12} | {'HIVE 🐝':<12} | {'CHANGE'}")
    print("-" * 60)
    print(f"{'Total Trades':<15} | {std_count:<12} | {hive_count:<12} | -{100 - (hive_count/std_count*100):.1f}%")
    print(f"{'Win Rate':<15} | {std_wr:<11.1f}% | {hive_wr:<11.1f}% | +{hive_wr-std_wr:.1f}%")
    print(f"{'Net Profit':<15} | ${std_pnl:<11.0f} | ${hive_pnl:<11.0f} | ${hive_pnl-std_pnl:.0f}")
    print("-" * 60)
    
    if hive_pnl > std_pnl:
        print("✅ CONCLUSION: HIVE Filters INCREASE Profit (Quality > Quantity).")
    else:
        print("⚠️ CONCLUSION: HIVE Filters reduced profit (Too strict?).")
        if hive_wr > std_wr:
            print("   (But Win Rate improved significantly).")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
