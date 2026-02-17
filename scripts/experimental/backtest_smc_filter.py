#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 10 (SMC / SUPPLY & DEMAND)
Objective: Test if "Buying into Resistance" is the cause of losses.
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

# HIVE V4
def get_data():
    print(f"📊 FETCHING DATA FOR SMC ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING SMC FILTER TEST (Avoid Walls)...")
    
    trades_v4 = []
    trades_smc = []
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        df['atr'] = (df['High']-df['Low']).rolling(14).mean()
        
        # HIVE V4 Logic
        # ADX
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr1 = tr.rolling(14).mean()
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr1)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr1)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
        
        # SMC / ZONES
        # Rolling Max/Min of last 50 candles (approx 2 days)
        df['resistance'] = df['High'].rolling(50, closed='left').max()
        df['support'] = df['Low'].rolling(50, closed='left').min()
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # Outcome V4 (Baseline)
            current_atr = atr1.iloc[i]
            entry = row['Close']
            
            adx = row['adx']
            vol = row['volatility']
            is_golden = (adx > 27 and vol < 16)
            
            risk = 0.006 if is_golden else 0.0025
            rr = 3.0 if is_golden else 2.0
            
            sl_dist = current_atr * 1.5
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            tp = entry + (sl_dist * rr) if sig==1 else entry - (sl_dist * rr)
            
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
            
            pnl = 0
            if outcome != 0:
                pnl = (risk * CAPITAL * rr) if outcome==1 else -(risk * CAPITAL)
                trades_v4.append(pnl)
                
            # --- SMC FILTER ---
            # Logic: Avoid buying if Supply is very close (< 0.5R away)
            # Logic: Avoid selling if Demand is very close (< 0.5R away)
            
            is_blocked = False
            res_level = row['resistance']
            sup_level = row['support']
            
            dist_to_res = res_level - entry
            dist_to_sup = entry - sup_level
            
            min_room = sl_dist * 1.0 # Need at least 1R room to structure
            
            if sig == 1:
                # Buying
                if dist_to_res < min_room: is_blocked = True
            else:
                # Selling
                if dist_to_sup < min_room: is_blocked = True
                
            if not is_blocked:
                # Add to SMC portfolio (Only add if trade happened)
                if outcome != 0: trades_smc.append(pnl)
                
    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 10: SMC / ZONES FILTER")
    print("="*60)
    
    v4_pnl = sum(trades_v4)
    smc_pnl = sum(trades_smc)
    
    print(f"{'METRIC':<15} | {'HIVE V4':<15} | {'HIVE + SMC':<15} | {'CHANGE'}")
    print("-" * 60)
    print(f"{'Trades':<15} | {len(trades_v4):<15} | {len(trades_smc):<15} | -{len(trades_v4)-len(trades_smc)}")
    print(f"{'Net Profit':<15} | ${v4_pnl:<15.0f} | ${smc_pnl:<15.0f} | ${smc_pnl-v4_pnl:.0f}")
    
    if smc_pnl > v4_pnl:
        print("✅ SUCCESS: Identifying Liquidity Zones improved results!")
    else:
        print("⚠️ FAILURE: 'Walls' are meant to be broken. Filter reduced profit.")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
