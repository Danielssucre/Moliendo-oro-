#!/usr/bin/env python3
"""
NANOBOT PORTFOLIO COMPARISON (A/B TEST)
Objective: Compare 'Big 5' vs 'Big 4' (No NZD) performance over the last 15 days.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np

# Add src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.ml.stop_hunt_model import StopHuntModel

# Config
PERIOD = "15d"
INTERVAL = "15m"
RISK_PER_TRADE = 0.002 # 0.2%
CAPITAL = 10000

# Scenarios
SCENARIOS = {
    "A: The Big 5 (Current)": ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"],
    "B: The Big 4 (Proposed)": ["GBPUSD=X", "AUDUSD=X", "BTC-USD", "SOL-USD"]
}

def backtest_scenario(name, assets):
    print(f"\n🧪 TESTING SCENARIO: {name}")
    print(f"   Assets: {len(assets)}")
    
    total_pnl = 0
    trades = []
    equity_curve = [CAPITAL]
    
    # Init ML (Mocked for speed if needed, or real)
    # Actually, we should use the same logic as live trading
    # But simplified for speed here: logic inside loop
    
    for symbol in assets:
        print(f"   Processing {symbol}...", end="\r")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=PERIOD, interval=INTERVAL)
        if df.empty: continue
        
        # Calculate Indicators (Simple version matching live bot)
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        df['rsi'] = 100 - (100 / (1 + df['Close'].diff().apply(lambda x: x if x>0 else 0).rolling(14).mean() / df['Close'].diff().apply(lambda x: -x if x<0 else 0).rolling(14).mean()))
        df['adx'] = 25 # Mocked ADX for speed (assume Trend/Range dynamic) - Actually let's calculate properly
        
        # Proper ADX
        high = df['High']; low = df['Low']; close = df['Close']
        plus_dm = high.diff(); minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm > 0] = 0
        tr1 = pd.DataFrame(high - low)
        tr2 = pd.DataFrame(abs(high - close.shift(1)))
        tr3 = pd.DataFrame(abs(low - close.shift(1)))
        frames = [tr1, tr2, tr3]
        tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr)
        minus_di = abs(100 * (minus_dm.ewm(alpha=1/14).mean() / atr))
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
        df['adx'] = dx.rolling(14).mean()
        df['atr'] = atr

        # Simulate Trades
        in_trade = False
        entry_price = 0
        tp = 0; sl = 0; direction = 0
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            if in_trade:
                # Check TP/SL
                if direction == 1: # Buy
                    if row['Low'] <= sl: total_pnl -= RISK_PER_TRADE * CAPITAL; in_trade = False; trades.append(-1)
                    elif row['High'] >= tp: total_pnl += (RISK_PER_TRADE * 2) * CAPITAL; in_trade = False; trades.append(2)
                else: # Sell
                    if row['High'] >= sl: total_pnl -= RISK_PER_TRADE * CAPITAL; in_trade = False; trades.append(-1)
                    elif row['Low'] <= tp: total_pnl += (RISK_PER_TRADE * 2) * CAPITAL; in_trade = False; trades.append(2)
            else:
                # Signal Logic
                sig = 0
                if row['adx'] > 25: # Trend
                    if row['ema_9'] > row['ema_15'] and prev['ema_9'] <= prev['ema_15'] and row['Close'] > row['ema_200']: sig = 1
                    elif row['ema_9'] < row['ema_15'] and prev['ema_9'] >= prev['ema_15'] and row['Close'] < row['ema_200']: sig = -1
                else: # Range
                    if row['rsi'] < 30: sig = 1
                    elif row['rsi'] > 70: sig = -1
                    
                if sig != 0:
                    # Execute
                    entry_price = row['Close']
                    atr_val = row['atr']
                    if sig == 1:
                        sl = entry_price - (atr_val * 1.5) # Wider SL for safety
                        tp = entry_price + (atr_val * 3.0) # 1:2
                        direction = 1
                    else:
                        sl = entry_price + (atr_val * 1.5)
                        tp = entry_price - (atr_val * 3.0)
                        direction = -1
                    in_trade = True
                    
            equity_curve.append(CAPITAL + total_pnl)
            
    # Metrics
    net_profit = total_pnl
    win_rate = (trades.count(2) / len(trades) * 100) if trades else 0
    drawdown = 0
    peak = CAPITAL
    for eq in equity_curve:
        if eq > peak: peak = eq
        dd = (peak - eq) / peak
        if dd > drawdown: drawdown = dd
        
    return {
        "Net Profit": net_profit,
        "Win Rate": win_rate,
        "Max Drawdown": drawdown * 100,
        "Total Trades": len(trades)
    }

def run_comparison():
    results = {}
    for name, assets in SCENARIOS.items():
        results[name] = backtest_scenario(name, assets)
        
    print("\n" + "="*60)
    print(f"🏆 A/B TEST RESULTS (Last 15 Days)")
    print("="*60)
    
    df = pd.DataFrame(results).T
    print(df[['Net Profit', 'Win Rate', 'Max Drawdown', 'Total Trades']].round(2))
    
    # Analysis
    res_a = results["A: The Big 5 (Current)"]
    res_b = results["B: The Big 4 (Proposed)"]
    
    diff = res_b['Net Profit'] - res_a['Net Profit']
    
    print("-" * 60)
    if diff > 0:
        print(f"✅ The 'Big 4' OUTPERFORMED by ${diff:.2f}.")
        print("   Removing NZD reduced drag/losses.")
    elif diff < 0:
        print(f"⚠️ The 'Big 5' was BETTER by ${abs(diff):.2f}.")
        print("   Removing NZD hurt profitability. Maybe keep it?")
    else:
        print("😐 Exact same performance (NZD didn't trade?).")
        
    print("-" * 60)

if __name__ == "__main__":
    run_comparison()
