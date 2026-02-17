#!/usr/bin/env python3
"""
NANOBOT HIVE V5: NATIVE OPTIMIZER 🧠⚡
Objective: Find the best parameters for FTMO Native Data using Brute Force Grid Search.
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
    sys.exit(1)

# --- CONFIG ---
INITIAL_CAPITAL = 10000
ASSETS = [
    "AUDUSD", "GBPJPY", "BTCUSD", "SOLUSD", "NZDUSD", 
    "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", 
    "USDCAD"
]
PERIOD_DAYS = 60
# H1 TIMEFRAME TEST
TIMEFRAME_M15 = 16385 # PERIOD_H1 constant in MT5? No, int value.
# wait, mt5.TIMEFRAME_H1 is 16385? Or just 60?
# siliconmetatrader5 uses standard MT5 timeframe enums if imported, or minutes if using copy_rates_from_pos?
# documentation says: copy_rates_from_pos(symbol, timeframe, ...)
# timeframe can be mt5.TIMEFRAME_M15 (integer enum) or simply minutes if the wrapper handles it?
# In `run_ftmo_manual.py` I used `tf = 15`. It seemingly worked (optimizer ran).
# So for H1, I should use 60? Or is it 16385?
# checking siliconmetatrader5 usage...
# It seems correct to use standard MT5 constants. 
# TIMEFRAME_M15 = 15
# TIMEFRAME_H1 = 16385
# TIMEFRAME_M1 = 1
# Let's try 16385 (standard MT5 constant for H1). 
# If I used 15 before and it worked, maybe 15 maps to M15?
# Let's check `test_mt5_data.py`. I used `15`.
# Let's assume input is minutes or specific integer.
# Standard MT5 Python:
# TIMEFRAME_M1 = 1
# TIMEFRAME_M15 = 15
# TIMEFRAME_H1 = 16385 (WARNING: It's not 60)
# But wait, `mt5.copy_rates_from_pos` usually takes the enum.
# If I passed 15 (M15 enum value is 15? No, M15 is 15? No. M1 is 1. M2 is 2... M15 is 15. H1 is 16385.
# Let's verify standard mt5 constants.
# M1=1, M2=2, M3=3, M4=4, M5=5, M6=6, M10=10, M12=12, M15=15, M20=20, M30=30
# H1=16385, H2=16386...
# So 15 WAS correct for M15.
# For H1, I must use 16385.

TIMEFRAME_H1 = 16385 

# --- PARAMETER GRID ---
# Standard Grid on H1
PARAM_GRID = {
    "SL_MULTIPLIER": [1.5, 2.0, 2.5], 
    "RR_TARGET": [1.5, 2.0, 2.5], 
    "ADX_THRESHOLD": [20, 25, 30] 
}

def get_data():
    print(f"📊 FETCHING DATA FOR OPTIMIZATION...")
    if not MT5_AVAILABLE or not mt5.initialize():
        print("❌ MT5 Connection Failed.")
        sys.exit(1)
        
    data = {}
    count = 2000 # Enough for 60 days M15? 
    # 4 * 24 * 60 = 5760. Let's try 3000 to be fast but cover enough recent PA.
    # User had issues with 6000. 1000 worked. Let's try 2500.
    count = 2500
    
    selected_count = 0
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
        
        # Pre-calc Indicators just ONCE
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
        selected_count += 1
        
    print(f"✅ Data fetched for {selected_count} assets.")
    return data

def run_backtest(data_map, sl_mult, rr_target, adx_thresh):
    balance = INITIAL_CAPITAL
    wins = 0
    losses = 0
    total_trades = 0
    
    # We iterate chronologically to be precise? 
    # For speed in optimization, iterating per asset then combining PnL is faster but less accurate for drawdown.
    # But needed for quick stats.
    
    equity_curve = []
    
    for symbol, df in data_map.items():
        last_trade_date = None
        
        # Vectorized or fast loop
        # Loop is safer for logic
        # We start at 200 to have indicators ready
        
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            current_date = row.name.date()
            
            if current_date == last_trade_date: continue
            
            # FILTERS
            if not (row['adx'] > adx_thresh and row['volatility'] < 16): continue
            
            # SIGNAL
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig == 0: continue
            
            # TRADE
            last_trade_date = current_date
            
            risk_usd = 30 # 0.3% fixed
            atr = row['atr']
            entry = row['Close']
            
            sl_dist = atr * sl_mult
            tp_dist = sl_dist * rr_target
            
            if sig == 1: sl = entry - sl_dist; tp = entry + tp_dist
            else: sl = entry + sl_dist; tp = entry - tp_dist
            
            outcome = 0
            future = df.iloc[i+1:i+48] # 12 hours max hold
            
            for j in range(len(future)):
                fr = future.iloc[j]
                if sig == 1:
                    if fr['Low'] <= sl: outcome = -1; break
                    if fr['High'] >= tp: outcome = 1; break
                else:
                    if fr['High'] >= sl: outcome = -1; break
                    if fr['Low'] <= tp: outcome = 1; break
            
            if outcome != 0:
                pnl = (risk_usd * rr_target) if outcome == 1 else -risk_usd
                balance += pnl
                total_trades += 1
                if outcome == 1: wins += 1
                else: losses += 1
                
    return {
        "final_balance": balance,
        "trades": total_trades,
        "wins": wins,
        "win_rate": (wins/total_trades*100) if total_trades > 0 else 0,
        "profit_factor": ((wins * (30*rr_target)) / (losses * 30)) if losses > 0 else 99
    }

def main():
    data = get_data()
    if not data: return
    
    print("\n🚀 STARTING GRID SEARCH OPTIMIZATION...")
    print(f"{'SL_MULT':<8} | {'RR':<4} | {'ADX':<4} | {'BALANCE':<10} | {'PF':<6} | {'WR%':<5} | {'TRADES'}")
    print("-" * 60)
    
    results = []
    
    for slm in PARAM_GRID['SL_MULTIPLIER']:
        for rr in PARAM_GRID['RR_TARGET']:
            for adx in PARAM_GRID['ADX_THRESHOLD']:
                res = run_backtest(data, slm, rr, adx)
                
                print(f"{slm:<8.1f} | {rr:<4.1f} | {adx:<4} | ${res['final_balance']:<9.0f} | {res['profit_factor']:<6.2f} | {res['win_rate']:<5.1f} | {res['trades']}")
                
                res['params'] = f"SL={slm}, RR={rr}, ADX={adx}"
                results.append(res)
                
    # Best
    results.sort(key=lambda x: x['final_balance'], reverse=True)
    best = results[0]
    
    print("-" * 60)
    print(f"🏆 BEST CONFIG: {best['params']}")
    print(f"💰 Balance: ${best['final_balance']:.2f}")
    print(f"📈 Profit Factor: {best['profit_factor']:.2f}")
    
if __name__ == "__main__":
    main()
