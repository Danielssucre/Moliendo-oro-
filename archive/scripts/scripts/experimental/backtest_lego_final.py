#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: THE LEGO DISRUPTIVE STRATEGY 🧱
Objective: Final Backtest of HIVE V4 + Pyramiding (The Tower).
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

# Params
RISK_STD = 0.0025
RISK_GOLD = 0.006

def get_data():
    print(f"📊 FETCHING DATA FOR LEGO STRATEGY...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING THE LEGO STRATEGY (V4 + Pyramiding)...")
    
    # Track Equity Curve (Monthly)
    monthly_pnl_base = {}
    monthly_pnl_lego = {}
    
    total_base = 0
    total_lego = 0
    
    trades_count = 0
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr1 = tr.rolling(14).mean()
        df['atr'] = atr1
        
        # Real ADX
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr1)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr1)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
        
        # Simulation
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            month_key = row.name.strftime("%Y-%m")
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # HIVE V4 Logic
            adx = row['adx']
            vol = row['volatility']
            is_golden = (adx > 27 and vol < 16)
            
            risk = RISK_GOLD if is_golden else RISK_STD
            rr = 3.0 if is_golden else 2.0
            
            current_atr = row['atr']
            entry = row['Close']
            sl_dist = current_atr * 1.5
            tp_dist = sl_dist * rr
            
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            tp = entry + tp_dist if sig==1 else entry - tp_dist
            
            # --- SIMULATION ---
            # BASE V4
            pnl_b = 0
            outcome_b = 0
            
            # LEGO (Pyramiding)
            # Only Pyramid on Golden Trades (The Disruptive Idea)
            pnl_l = 0
            
            # Future Scan
            future = df.iloc[i+1:i+48]
            
            # Lego State
            t1_open = True
            t2_open = False
            t1_sl = sl # Dynamic
            t1_tp = tp
            t2_entry = 0
            t2_sl = 0
            
            trigger_dist = current_atr * 1.0
            trigger_price = entry + trigger_dist if sig==1 else entry - trigger_dist
            
            base_done = False
            lego_done = False
            
            for j in range(len(future)):
                fr = future.iloc[j]
                
                # --- BASE LOGIC ---
                if not base_done:
                    if sig == 1:
                        if fr['Low'] <= sl: pnl_b = -(risk * CAPITAL); base_done=True
                        elif fr['High'] >= tp: pnl_b = (risk * CAPITAL * rr); base_done=True
                    else:
                        if fr['High'] >= sl: pnl_b = -(risk * CAPITAL); base_done=True
                        elif fr['Low'] <= tp: pnl_b = (risk * CAPITAL * rr); base_done=True
                
                # --- LEGO LOGIC ---
                if not lego_done:
                    # 1. Check TP (Win)
                    if sig == 1 and fr['High'] >= t1_tp: 
                        # Win!
                        # T1 wins 3R
                        win1 = risk * CAPITAL * 3.0
                        win2 = 0
                        if t2_open:
                            # T2 wins distance from Trigger to TP (2R distance)
                            # Size is same as T1 (risk based). 
                            # Profit = (2.0 / 1.5) * Risk($) = 1.33 * Risk($).
                            # Wait, T2 runs from Entry+1R to Entry+3R. The run is 2R (relative to initial entry ATR).
                            # If we risked 1R ($) on T1, T2 is also 1R ($).
                            # T2 'R' achieved = 2.0 / 1.5 = 1.33.
                            win2 = (risk * CAPITAL) * (2.0/1.5)
                        pnl_l = win1 + win2
                        lego_done = True
                        
                    elif sig == -1 and fr['Low'] <= t1_tp:
                        win1 = risk * CAPITAL * 3.0
                        win2 = 0
                        if t2_open:
                            win2 = (risk * CAPITAL) * (2.0/1.5)
                        pnl_l = win1 + win2
                        lego_done = True
                        
                    # 2. Check Stops
                    # T1 Stop
                    if t1_open: 
                         if sig==1 and fr['Low'] <= t1_sl:
                             # Stopped T1
                             pnl_l = -(risk * CAPITAL) if t1_sl == sl else 0 # Loss or BE
                             # If T2 was open, it is also stopped (since T2 SL usually near T1 BE)
                             if t2_open:
                                 pnl_l += -(risk * CAPITAL) # T2 Loss
                             lego_done = True
                         elif sig==-1 and fr['High'] >= t1_sl:
                             pnl_l = -(risk * CAPITAL) if t1_sl == sl else 0
                             if t2_open: pnl_l += -(risk * CAPITAL)
                             lego_done = True
                    
                    # T2 Stop (if strictly T2 hit but T1 didn't? T1 is at BE, T2 SL is below it usually? No.)
                    # Typically T2 SL is at T1 BE. So they hit together.
                    
                    # 3. Check Pyramid Trigger
                    if is_golden and not t2_open and not lego_done:
                        if sig == 1 and fr['High'] >= trigger_price:
                            t2_open = True
                            t2_entry = trigger_price
                            t1_sl = entry # Move T1 to BE
                            # T2 SL = T2 Entry - 1.5 ATR = (Entry+1ATR) - 1.5ATR = Entry - 0.5ATR.
                            # So T2 SL is actually below T1 BE.
                            # T2 Risk is standard.
                        elif sig == -1 and fr['Low'] <= trigger_price:
                            t2_open = True
                            t2_entry = trigger_price
                            t1_sl = entry # Move T1 to BE
            
            if base_done: 
                total_base += pnl_b
                monthly_pnl_base[month_key] = monthly_pnl_base.get(month_key, 0) + pnl_b
            
            if lego_done:
                total_lego += pnl_l
                monthly_pnl_lego[month_key] = monthly_pnl_lego.get(month_key, 0) + pnl_l
            else:
                # If simulation ended without lego completion, use base result?
                # No, assume closed at close? Or just exclude.
                # Matching base for fairness.
                if base_done: 
                     # If base finished but lego logic didn't trigger stop/tp?
                     # Means we are still in trade.
                     pass 
                else: 
                     pass

    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🧱 THE LEGO STRATEGY: HIVE V4 + PYRAMIDING")
    print("="*60)
    
    print(f"{'METRIC':<15} | {'HIVE V4 (Base)':<15} | {'LEGO (Disruptive)':<20}")
    print("-" * 60)
    print(f"{'Total Profit':<15} | ${total_base:<15.0f} | ${total_lego:<20.0f}")
    print(f"{'Outperformance':<15} | {'-':<15} | +${total_lego-total_base:.0f}")
    
    print("\n📅 MONTHLY BREAKDOWN (LEGO):")
    for m in sorted(monthly_pnl_lego.keys()):
        pnl = monthly_pnl_lego[m]
        print(f"   {m}: ${pnl:.0f}")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
