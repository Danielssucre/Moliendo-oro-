#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 8 (TIMEFRAME)
Objective: Test HIVE V4 Logic across 15m, 30m, 1h, 4h.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np

# Config
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]
PERIOD = "59d" # 60d limit for 15m sometimes
TIMEFRAMES = ["15m", "30m", "1h"] # 4h not avail in 'period=60d' efficiently sometimes, let's try
CAPITAL = 10000

# HIVE V4 PARAMS
RISK_STD = 0.0025
RISK_GOLD = 0.006

def run_test_for_interval(interval):
    print(f"\n⏳ TESTING TIMEFRAME: {interval}...")
    
    total_pnl = 0
    trade_count = 0
    
    data_map = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            # yfinance limit: 15m/30m = 60d
            df = ticker.history(period=PERIOD, interval=interval)
            if not df.empty: data_map[symbol] = df
        except: pass
        
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
        
        # Simulation
        start_idx = 200
        if len(df) < start_idx: continue
        
        for i in range(start_idx, len(df)-48):
            row = df.iloc[i]
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # Check Golden
            adx = row['adx']
            vol = row['volatility']
            
            is_golden = False
            if adx > 27 and vol < 16: is_golden = True
            
            # Params
            if is_golden:
                risk = RISK_GOLD
                rr = 3.0
            else:
                risk = RISK_STD
                rr = 2.0
                
            # Outcome
            current_atr = row['atr']
            sl_dist = current_atr * 1.5
            entry = row['Close']
            
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
            
            if outcome != 0:
                pnl = 0
                if outcome == 1: pnl = risk * CAPITAL * rr
                else: pnl = -(risk * CAPITAL)
                total_pnl += pnl
                trade_count += 1
                
    return trade_count, total_pnl

def run_suite():
    print("\n🐝 RUNNING TIMEFRAME SUITE (HIVE V4)...")
    
    results = {}
    for tf in TIMEFRAMES:
        cnt, pnl = run_test_for_interval(tf)
        results[tf] = {'count': cnt, 'pnl': pnl}
        
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 8: TIMEFRAME COMPARISON (60 Days)")
    print("="*60)
    print(f"{'TF':<6} | {'TRADES':<10} | {'NET PnL':<15} | {'AVG / Trade'}")
    print("-" * 60)
    
    for tf in TIMEFRAMES:
        r = results[tf]
        c = r['count']
        p = r['pnl']
        avg = p/c if c else 0
        tag = "👑 WINNER" if p == max([x['pnl'] for x in results.values()]) else ""
        print(f"{tf:<6} | {c:<10} | ${p:<15.0f} | ${avg:<10.1f} {tag}")

if __name__ == "__main__":
    run_suite()
