#!/usr/bin/env python3
"""
NANOBOT HIVE V5: AXI SELECT ROADMAP PROJECTION 🚀
Objective: Simulate "Time to 5% Profit" to estimate stage progression.
"""
import sys
import os
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# Silicon MT5
try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("❌ siliconmetatrader5 not found")

# --- CONFIG ---
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.004 # 0.4%
RR_TARGET = 1.5
SL_ATR_MULT = 2.0
# AXI COMPLIANT ASSETS (No SOLUSD)
ASSETS = [
    "AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", 
    "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", 
    "USDCAD"
]
TIMEFRAME_H1 = 16385

def get_data():
    if not MT5_AVAILABLE or not mt5.initialize():
        print("❌ MT5 Failed")
        return {}
        
    print(f"📊 FETCHING H1 DATA FROM FTMO...")
    data = {}
    count = 1500 # Approx 60 days
    
    for symbol in ASSETS:
        if not mt5.symbol_select(symbol, True): continue
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME_H1, 0, count)
        if rates is None or len(rates) == 0: 
            time.sleep(1)
            rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME_H1, 0, count)
            if rates is None or len(rates) == 0: continue
            
        d_list = []
        for r in rates: d_list.append(list(r))
        df = pd.DataFrame(d_list, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'tick_volume':'Volume'}, inplace=True)
        
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        
        # ATR
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
        
        # ADX
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        atr1 = df['atr']
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr1)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr1)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        
        data[symbol] = df
        
    return data

def simulate_roadmap(data_map):
    print("\n🚀 AXI SELECT ROADMAP ESTIMATION (Based on 60-Day H1 Data) 🚀")
    print("Conditions: 0.4% Risk | 5% Profit Target | Min Days Rule")
    print("-" * 75)
    
    # Collect all signals
    all_signals = []
    for symbol, df in data_map.items():
        # Clean loop
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            if not (row['adx'] > 25 and row['volatility'] < 16): continue
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            all_signals.append({
                'time': row.name,
                'signal': sig,
                'entry': row['Close'],
                'atr': row['atr'],
                'df': df,
                'idx': i
            })
            
    all_signals.sort(key=lambda x: x['time'])
    
    # Simulate
    balance = INITIAL_CAPITAL
    start_date = all_signals[0]['time'].date()
    daily_trades = {}
    
    days_to_5 = None
    trades_taken = 0
    wins = 0
    
    for s in all_signals:
        if days_to_5: break
        
        t_date = s['time'].date()
        if daily_trades.get(t_date, 0) >= 1: continue # Strict 1 trade per pair/day logic
        
        # Outcome
        risk = INITIAL_CAPITAL * RISK_PER_TRADE
        outcome = 0
        df = s['df']; idx = s['idx']
        sl_dist = s['atr']*SL_ATR_MULT
        tp_dist = sl_dist*RR_TARGET
        entry = s['entry']
        sl = entry - sl_dist if s['signal']==1 else entry + sl_dist
        tp = entry + tp_dist if s['signal']==1 else entry - tp_dist
        
        future = df.iloc[idx+1:idx+48]
        for j in range(len(future)):
            bar = future.iloc[j]
            if s['signal']==1:
                if bar['Low'] <= sl: outcome=-1; break
                if bar['High'] >= tp: outcome=1; break
            else:
                if bar['High'] >= sl: outcome=-1; break
                if bar['Low'] <= tp: outcome=1; break
        
        if outcome != 0:
            pnl = risk * RR_TARGET if outcome==1 else -risk
            balance += pnl
            
            if t_date not in daily_trades: daily_trades[t_date]=0
            daily_trades[t_date]+=1
            trades_taken += 1
            if outcome==1: wins+=1
            
            profit = balance - INITIAL_CAPITAL
            if profit >= (INITIAL_CAPITAL * 0.05): # 5% Profit
                days_to_5 = (t_date - start_date).days
                
    if days_to_5:
        # Generate Roadmap
        print(f"📊 PERFORMANCE METRIC: The bot takes ~{days_to_5} days to make 5% profit.")
        print(f"   (Sample: {trades_taken} trades, Win Rate: {wins/trades_taken*100:.1f}%)")
        print("-" * 75)
        print(f"{'STAGE TO PASS':<15} | {'ALLOCATION':<10} | {'MIN DAYS':<10} | {'TIME TAKEN':<15} | {'STATUS':<15}")
        print("-" * 75)
        
        total_days = 0
        
        # 1. Seed
        stage_days = max(30, days_to_5)
        total_days += stage_days
        print(f"{'1. Seed':<15} | {'-':<10} | {'30':<10} | {f'{stage_days} days':<15} | {'Unlocks Incubation'}")
        
        # 2. Incubation
        stage_days = max(60, days_to_5)
        total_days += stage_days
        print(f"{'2. Incubation':<15} | {'$20k':<10} | {'60':<10} | {f'{stage_days} days':<15} | {'Unlocks Acceleration'}")
        
        # 3. Acceleration
        stage_days = max(60, days_to_5)
        total_days += stage_days
        print(f"{'3. Accel':<15} | {'$100k':<10} | {'60':<10} | {f'{stage_days} days':<15} | {'Unlocks Pro'}")
        
        # 4. Pro
        stage_days = max(60, days_to_5)
        total_days += stage_days
        print(f"{'4. Pro':<15} | {'$200k':<10} | {'60':<10} | {f'{stage_days} days':<15} | {'Unlocks Pro 500'}")
        
        # 5. Pro 500
        stage_days = max(60, days_to_5)
        total_days += stage_days
        print(f"{'5. Pro 500':<15} | {'$500k':<10} | {'60':<10} | {f'{stage_days} days':<15} | {'Unlocks Pro M'}")

        print("-" * 75)
        print(f"🏆 TARGET REACHED: PRO M ($1,000,000 Allocation)")
        print(f"⏱️  TOTAL ESTIMATED TIME: {total_days} days ({total_days/30:.1f} months)")
        print(f"📅 ESTIMATED DATE: {(datetime.now() + timedelta(days=total_days)).strftime('%B %Y')}")
    else:
        print("⚠️ Bot did not reach 5% in the simulation period.")

if __name__ == "__main__":
    d = get_data()
    if d:
        simulate_roadmap(d)
