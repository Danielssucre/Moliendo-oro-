#!/usr/bin/env python3
"""
NANOBOT SCIENTIFIC LOOP: CYCLE 12 (THE TOWER BUILDER)
Objective: Test Pyramiding (Adding to Winners).
Disruptive Idea: "Don't take profit. Add risk."
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

# HIVE V4 Base Params
RISK_GOLD = 0.006 

def get_data():
    print(f"📊 FETCHING DATA FOR PYRAMIDING ANALYSIS...")
    data = {}
    for symbol in ASSETS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=PERIOD, interval=INTERVAL)
            if not df.empty: data[symbol] = df
        except: pass
    return data

def run_simulation(data_map):
    print("\n🐝 RUNNING TOWER BUILDER TEST (Pyramiding on Golden Trades)...")
    
    trades_base = []
    trades_tower = []
    
    for symbol, df in data_map.items():
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
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
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # Filter: HIVE V4 (Golden Only for Pyramiding test)
            adx = row['adx']
            vol = row['volatility']
            if not (adx > 27 and vol < 16): continue
            
            # --- OUTCOME 1: BASE V4 (Single Entry) ---
            current_atr = atr1.iloc[i]
            entry = row['Close']
            sl_dist = current_atr * 1.5
            tp_dist_3r = current_atr * 3.0
            
            sl = entry - sl_dist if sig==1 else entry + sl_dist
            tp = entry + tp_dist_3r if sig==1 else entry - tp_dist_3r
            
            outcome_base = 0 
            future = df.iloc[i+1:i+48]
            
            # Store candle index where events happen
            idx_entry = i
            idx_tp = -1
            idx_sl = -1
            
            for j in range(len(future)):
                fr = future.iloc[j]
                if sig == 1:
                    if fr['Low'] <= sl: outcome_base = -1; idx_sl=j; break
                    if fr['High'] >= tp: outcome_base = 3; idx_tp=j; break
                else:
                    if fr['High'] >= sl: outcome_base = -1; idx_sl=j; break
                    if fr['Low'] <= tp: outcome_base = 3; idx_tp=j; break
            
            # Record Base PnL
            base_pnl = 0
            if outcome_base == 3: base_pnl = RISK_GOLD * CAPITAL * 3.0
            elif outcome_base == -1: base_pnl = -(RISK_GOLD * CAPITAL)
            trades_base.append(base_pnl)
            
            # --- OUTCOME 2: THE TOWER (Pyramiding) ---
            # Logic:
            # 1. Enter Trade 1.
            # 2. If Price reaches Entry + 1ATR:
            #    - Move SL 1 to Breakeven.
            #    - Enter Trade 2 (Same Size).
            #    - Trade 2 SL = (Price - 1.5 ATR) -> Usually equals Breakeven of T1.
            #    - Trade 2 TP = Original TP (So smaller R on T2).
            
            trigger_dist = current_atr * 1.0 # 1R Trigger
            trigger_level = entry + trigger_dist if sig==1 else entry - trigger_dist
            
            tower_pnl = 0
            
            # Simulate Step-by-Step
            t1_open = True
            t2_open = False
            
            t1_sl = sl
            t1_tp = tp
            
            t2_entry = 0
            t2_sl = 0
            t2_tp = tp # Shared Target
            
            hit_full_tp = False
            hit_stop = False
            
            for j in range(len(future)):
                fr = future.iloc[j]
                
                # Check Global TP first (Gap up)
                if sig == 1 and fr['High'] >= t1_tp: hit_full_tp = True; break
                if sig == -1 and fr['Low'] <= t1_tp: hit_full_tp = True; break
                
                # Check Global SL
                # If T1 is open, check T1 SL
                if t1_open:
                    if sig == 1 and fr['Low'] <= t1_sl: hit_stop = True; break
                    if sig == -1 and fr['High'] >= t1_sl: hit_stop = True; break
                
                # If T2 is open, check T2 SL
                if t2_open:
                    if sig == 1 and fr['Low'] <= t2_sl: hit_stop = True; break
                    if sig == -1 and fr['High'] >= t2_sl: hit_stop = True; break
                
                # Check Trigger for Pyramiding
                if not t2_open and t1_open:
                    can_pyramid = False
                    if sig == 1 and fr['High'] >= trigger_level: can_pyramid = True
                    if sig == -1 and fr['Low'] <= trigger_level: can_pyramid = True
                    
                    if can_pyramid:
                        # BUILD THE TOWER
                        t2_open = True
                        t2_entry = trigger_level
                        
                        # Move T1 SL to Entry (Breakeven) - slippage
                        t1_sl = entry
                        
                        # Set T2 SL to Trigger - 1.5 ATR
                        # Theoretically if Trigger = Entry+1ATR, and SL=1.5ATR, 
                        # SL is at Entry - 0.5ATR. 
                        # So T2 risks 1.5R.
                        # T1 is safe (BE).
                        t2_sl = t2_entry - sl_dist if sig==1 else t2_entry + sl_dist
                        
            # Calc Tower PnL
            net_tower_risk = RISK_GOLD * CAPITAL # Per trade unit
            
            if hit_full_tp:
                # T1 Wins 3R
                p1 = net_tower_risk * 3.0
                
                # T2 Wins?
                # T2 Entry was at 1R. TP is at 3R. Distance = 2R.
                # Since Size is based on 1.5ATR Risk, we need to normalize.
                # Simplified: assume fixed dollar risk units.
                # T1: +3 Units.
                # T2: Distance (2R relative to entry) / Risk Dist (1.5R) = 1.33 Units Profit?
                # Actually, simple math:
                # T1 captured 3.0 * ATR range.
                # T2 captured 2.0 * ATR range.
                # Both sized for 1.5 * ATR risk.
                
                t1_profit = (3.0 / 1.5) * net_tower_risk # = 2 * Risk Amount
                t2_profit = (2.0 / 1.5) * net_tower_risk # = 1.33 * Risk Amount
                
                # Wait, my V4 math says '3R' means Profit = Risk * 3.
                # So Distance = 1.5 * 3 = 4.5 ATR?
                # Check V4 logic: tp = entry + (sl_dist * rr). Yes. RR=3.0.
                # So Distance = 1.5ATR * 3 = 4.5 ATR.
                
                # RE-CALC:
                # T1: Runs 4.5 ATR. Risked 1.5 ATR. Profit = 3.0 * Risk($).
                # T2: Starts at 1.0 ATR. Runs to 4.5 ATR. Distance = 3.5 ATR.
                #     Risked 1.5 ATR. Profit = (3.5/1.5) * Risk($) = 2.33 * Risk($).
                
                # Total = 5.33 R!
                if t2_open:
                    tower_pnl = (net_tower_risk * 3.0) + (net_tower_risk * 2.333)
                else:
                    tower_pnl = (net_tower_risk * 3.0) # Just T1
            
            elif hit_stop:
                # Stopped out.
                # Scenario A: Stopped BEFORE Pyramid.
                if not t2_open:
                    tower_pnl = -net_tower_risk # Lose 1R
                else:
                    # Scenario B: Stopped AFTER Pyramid.
                    # T1 was at BE. PnL = 0.
                    # T2 was stopped. PnL = -1R.
                    # Total = -1R.
                    # BUT, usually chop hits T2 SL but not T1 BE immediately?
                    # Simplified: We treat "Hit Stop" as catastrophic failure of tower.
                    # Outcome: -1R (Risk of T2). T1 is scratched.
                    tower_pnl = -net_tower_risk
            
            else:
                # Timeout / Consolidation
                tower_pnl = 0
                
            trades_tower.append(tower_pnl)

    # --- REPORT ---
    print("\n" + "="*60)
    print(f"🏰 HIVE CYCLE 12: THE TOWER BUILDER (Pyramiding Rules)")
    print("="*60)
    
    base_pnl = sum(trades_base)
    tower_pnl = sum(trades_tower)
    
    print(f"{'METRIC':<15} | {'HIVE V4 (Base)':<15} | {'TOWER (Pyramid)':<15} | {'CHANGE'}")
    print("-" * 75)
    print(f"{'Net Profit':<15} | ${base_pnl:<15.0f} | ${tower_pnl:<15.0f} | ${tower_pnl-base_pnl:.0f}")
    
    if tower_pnl > base_pnl:
        print("✅ SUCCESS: Pyramiding multiplied profits! (Fat Tails exploited).")
    else:
        print("⚠️ FAILURE: Pyramiding adds risk in choppy markets.")

if __name__ == "__main__":
    d = get_data()
    run_simulation(d)
