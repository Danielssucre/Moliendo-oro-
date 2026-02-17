#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 9 (FRACTAL ENTRY)
Objective: Test if M5 Alignment improves H1 Signals.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np

# Config
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]
PERIOD = "59d" # Limit for 5m
CAPITAL = 10000
RISK_STD = 0.0025
RISK_GOLD = 0.006

def get_data():
    print(f"📊 FETCHING DATA (H1 + M5)...")
    data_h1 = {}
    data_m5 = {}
    
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            # H1
            df_h1 = ticker.history(period=PERIOD, interval="1h")
            if not df_h1.empty: data_h1[symbol] = df_h1
            
            # M5
            df_m5 = ticker.history(period=PERIOD, interval="5m")
            if not df_m5.empty: data_m5[symbol] = df_m5
        except: pass
    return data_h1, data_m5

def run_simulation(data_h1, data_m5):
    print("\n🐝 RUNNING FRACTAL ENTRY TEST (Standard vs M5 Alignment)...")
    
    trades_std = []
    trades_fractal = [] # Only taken if M5 aligns
    
    for symbol in data_h1.keys():
        if symbol not in data_m5: continue
        
        df1 = data_h1[symbol].copy()
        df5 = data_m5[symbol].copy()
        
        # --- H1 INDICATORS ---
        df1['ema_9'] = df1['Close'].ewm(span=9).mean()
        df1['ema_15'] = df1['Close'].ewm(span=15).mean()
        df1['ema_200'] = df1['Close'].ewm(span=200).mean()
        df1['atr'] = (df1['High']-df1['Low']).rolling(14).mean()
        # ADX H1 (Simplify for speed)
        df1['adx'] = 30 # Mock ADX to assume active participation for now, 
                        # or re-calc full ADX. Let's re-calc to be fair to V4 logic.
        
        high = df1['High']; low = df1['Low']; close = df1['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr1 = tr.rolling(14).mean()
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df1.index); minus_dm = pd.Series(0.0, index=df1.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr1)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr1)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df1['adx'] = dx.ewm(alpha=1/14).mean()
        df1['volatility'] = df1['Close'].pct_change().rolling(24).std() * 1000
        
        # --- M5 INDICATORS ---
        df5['ema_9'] = df5['Close'].ewm(span=9).mean()
        df5['ema_15'] = df5['Close'].ewm(span=15).mean()
        
        # Align Timezones
        if df1.index.tz is None: df1.index = df1.index.tz_localize('UTC')
        else: df1.index = df1.index.tz_convert('UTC')
        
        if df5.index.tz is None: df5.index = df5.index.tz_localize('UTC')
        else: df5.index = df5.index.tz_convert('UTC')

        # Simulation Loop
        for i in range(200, len(df1)-48):
            row = df1.iloc[i]
            ts_h1 = row.name
            
            # 1. H1 Signal
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # --- OUTCOME CALCULATION ---
            # V4 Logic Params
            adx = row['adx']
            vol = row['volatility']
            is_golden = (adx > 27 and vol < 16)
            
            risk = RISK_GOLD if is_golden else RISK_STD
            rr = 3.0 if is_golden else 2.0
            
            current_atr = atr1.iloc[i]
            entry = row['Close']
            sl_dist = current_atr * 1.5
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            tp = entry + (sl_dist * rr) if sig==1 else entry - (sl_dist * rr)
            
            outcome = 0
            future = df1.iloc[i+1:i+48]
            for j in range(len(future)):
                fr = future.iloc[j]
                if sig == 1:
                    if fr['Low'] <= sl: outcome = -1; break
                    if fr['High'] >= tp: outcome = 1; break
                else:
                    if fr['High'] >= sl: outcome = -1; break
                    if fr['Low'] <= tp: outcome = 1; break
            
            if outcome != 0:
                pnl = (risk * CAPITAL * rr) if outcome == 1 else -(risk * CAPITAL)
                trades_std.append(pnl)
                
                # --- FRACTAL CHECK (M5) ---
                # Check M5 state AT THE EXACT TIME of H1 Close
                # Find closest M5 candle <= ts_h1
                try:
                    # Get M5 slice ending at ts_h1
                    # Actually H1 close time is the end of the hour.
                    # M5 candle for XX:55 should be available.
                    # Use searchsorted or asof
                    
                    loc_idx = df5.index.get_indexer([ts_h1], method='nearest')[0]
                    row_m5 = df5.iloc[loc_idx]
                    
                    # Logic: Is M5 Aligned?
                    m5_aligned = False
                    if sig == 1:
                        if row_m5['ema_9'] > row_m5['ema_15']: m5_aligned = True
                    else:
                        if row_m5['ema_9'] < row_m5['ema_15']: m5_aligned = True
                        
                    if m5_aligned:
                        trades_fractal.append(pnl)
                except:
                    pass # Data mismatch, skip fractal
                    
    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 9: FRACTAL ENTRY (M5 Alignment)")
    print("="*60)
    
    std_pnl = sum(trades_std)
    frac_pnl = sum(trades_fractal)
    
    print(f"{'METRIC':<15} | {'STANDARD (H1)':<15} | {'FRACTAL (H1+M5)':<15} | {'CHANGE'}")
    print("-" * 75)
    print(f"{'Net Profit':<15} | ${std_pnl:<15.0f} | ${frac_pnl:<15.0f} | ${frac_pnl-std_pnl:.0f}")
    
    if frac_pnl > std_pnl:
        print("✅ SUCCESS: Fractal Alignment Improved Profit!")
    else:
        print("⚠️ FAILURE: Fractal Filter blocked too many winners.")

if __name__ == "__main__":
    d1, d5 = get_data()
    run_simulation(d1, d5)
