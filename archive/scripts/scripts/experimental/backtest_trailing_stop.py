#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 5 (TRAILING STOP)
Objective: Test if Trailing Stop beats Fixed 3R on Golden Trades.
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
    print(f"📊 FETCHING DATA FOR TRAILING STOP ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING TRAILING STOP TEST (Fixed 3R vs Trail 2ATR)...")
    
    trades_fixed_3r = []
    trades_trailing = []
    
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
            
            # Check Golden (Only test on Golden)
            adx = row['adx']
            vol = row['volatility']
            if not (adx > 27 and vol < 16): continue 
            
            current_atr = row['atr']
            sl_dist = current_atr * 1.5
            entry = row['Close']
            
            # --- OUTCOME 1: FIXED 3R ---
            tp_dist_3r = current_atr * 3.0
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            tp_3r = entry + tp_dist_3r if sig==1 else entry - tp_dist_3r
            
            outcome_3r = 0
            future = df.iloc[i+1:i+48]
            for j in range(len(future)):
                fr = future.iloc[j]
                if sig == 1:
                    if fr['Low'] <= sl: outcome_3r = -1; break
                    if fr['High'] >= tp_3r: outcome_3r = 3; break
                else:
                    if fr['High'] >= sl: outcome_3r = -1; break
                    if fr['Low'] <= tp_3r: outcome_3r = 3; break
                    
            if outcome_3r != 0:
                 pnl = (GOLDEN_RISK * CAPITAL * 3.0) if outcome_3r == 3 else -(GOLDEN_RISK * CAPITAL)
                 trades_fixed_3r.append(pnl)
                 
            # --- OUTCOME 2: TRAILING STOP (2 ATR) ---
            # Logic: 
            # 1. Initial SL = 1.5 ATR.
            # 2. As price moves in favor, SL moves.
            # 3. Simple Trailing: If Price hits New High, SL = High - 2.0 ATR.
            
            trail_dist = current_atr * 2.0
            current_sl = sl # Start with 1.5 ATR
            
            pnl_trail = 0
            reached_be = False
            
            best_price = entry
            
            for j in range(len(future)):
                fr = future.iloc[j]
                
                if sig == 1:
                    # Check SL
                    if fr['Low'] <= current_sl:
                        # OUT!
                        exit_price = current_sl # Slippage ignored
                        pnl_pct = (exit_price - entry) / entry
                        # Need to convert to R-muliples?
                        # Risk Amount = (entry - initial_sl_price) * units
                        # PnL = (exit - entry) * units
                        
                        risk_dist = abs(entry - sl) # initial sl distance
                        r_multiple = (exit_price - entry) / risk_dist
                        
                        pnl_trail = r_multiple * GOLDEN_RISK * CAPITAL
                        break
                        
                    # Update Trailing
                    if fr['High'] > best_price:
                        best_price = fr['High']
                        new_sl = best_price - trail_dist
                        if new_sl > current_sl: current_sl = new_sl
                        
                else:
                    # Check SL
                    if fr['High'] >= current_sl:
                        exit_price = current_sl
                        risk_dist = abs(entry - sl)
                        r_multiple = (entry - exit_price) / risk_dist
                        pnl_trail = r_multiple * GOLDEN_RISK * CAPITAL
                        break
                        
                    # Update Trailing
                    if fr['Low'] < best_price:
                        best_price = fr['Low']
                        new_sl = best_price + trail_dist
                        if new_sl < current_sl: current_sl = new_sl
            
            trades_trailing.append(pnl_trail)
                    
    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 5: TRAILING STOP (The Infinity Run)")
    print("="*60)
    
    pnl_fixed = sum(trades_fixed_3r)
    pnl_trail = sum(trades_trailing)
    
    print(f"{'METRIC':<15} | {'FIXED 3R':<12} | {'TRAILING':<12} | {'CHANGE'}")
    print("-" * 60)
    print(f"{'Net Profit':<15} | ${pnl_fixed:<11.0f} | ${pnl_trail:<11.0f} | ${pnl_trail-pnl_fixed:.0f}")
    
    if pnl_trail > pnl_fixed:
        print("✅ SUCCESS: Trailing Stop Captured HUGE Runs!")
    else:
        print("⚠️ FAILURE: Trailing Stop gave back too much profit.")
        print("   (Fixed 3R is superior).")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
