#!/usr/bin/env python3
"""
12-Month Robustness Test (Monte Carlo)
Data: 1H (Due to yfinance M15 limit).
Strategy: Hybrid (ADX Trend + RSI Reversion).
Process: 12 Random 15-day samples (1 per month).
"""
import yfinance as yf
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def download_data(symbol, period="1y", interval="1h"):
    print(f"Downloading {symbol} ({period}, {interval})...")
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df

def calculate_hybrid_signal(df):
    # EMAs
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX
    period = 14
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up, down = high.diff(), -low.diff()
    plus_dm, minus_dm = pd.Series(0.0, index=df.index), pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI (7)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def simulate_sample(df, start_idx, length_candles=360): # 15 days * 24h = 360
    end_idx = start_idx + length_candles
    if end_idx >= len(df): return None
    
    sample = df.iloc[start_idx:end_idx].copy()
    capital = 10000.0
    balance = capital
    max_dd = 0
    trades = []
    open_trade = None
    peak_equity = capital
    
    for i in range(1, len(sample)):
        curr = sample.iloc[i]
        prev = sample.iloc[i-1]
        
        # Open Trade Management
        if open_trade:
            # Check SL/TP
             if open_trade['type'] == 'BUY':
                if curr['low'] <= open_trade['sl']:
                    pnl = (open_trade['sl'] - open_trade['entry']) * open_trade['size']
                    balance += pnl
                    trades.append(pnl)
                    open_trade = None
                elif curr['high'] >= open_trade['tp']:
                    pnl = (open_trade['tp'] - open_trade['entry']) * open_trade['size']
                    balance += pnl
                    trades.append(pnl)
                    open_trade = None
             else:
                if curr['high'] >= open_trade['sl']:
                    pnl = (open_trade['entry'] - open_trade['sl']) * open_trade['size']
                    balance += pnl
                    trades.append(pnl)
                    open_trade = None
                elif curr['low'] <= open_trade['tp']:
                    pnl = (open_trade['entry'] - open_trade['tp']) * open_trade['size']
                    balance += pnl
                    trades.append(pnl)
                    open_trade = None
            
             # DD Update
             if balance > peak_equity: peak_equity = balance
             dd = peak_equity - balance
             if dd > max_dd: max_dd = dd
             continue

        # Signal Logic (Hybrid)
        current_hour = curr.name.hour
        # Time Window (Relaxed for H1: 08-16)
        # Optimized window was 08-12 for M15. H1 needs broader? Or same?
        # Let's use 08-12 to be strict to strategy.
        if not (8 <= current_hour < 12): continue
        
        adx = curr['adx']
        signal = None
        sl_mult = 1.0; rr = 1.0
        
        # TREND
        if adx > 25:
             if curr['ema_9'] > curr['ema_15'] and prev['ema_9'] <= prev['ema_15'] and curr['close'] > curr['ema_200']:
                 signal = "BUY"; sl_mult = 1.0; rr = 2.0
             elif curr['ema_9'] < curr['ema_15'] and prev['ema_9'] >= prev['ema_15'] and curr['close'] < curr['ema_200']:
                 signal = "SELL"; sl_mult = 1.0; rr = 2.0
        # RANGE
        else:
             if curr['rsi'] < 35:
                 signal = "BUY"; sl_mult = 1.5; rr = 3.0
             elif curr['rsi'] > 65:
                 signal = "SELL"; sl_mult = 1.5; rr = 3.0
        
        if signal:
            atr = curr['atr']
            if np.isnan(atr) or atr == 0: continue
            
            entry = curr['close']
            sl_dist = atr * sl_mult
            
            if signal == "BUY":
                sl = entry - sl_dist
                tp = entry + (sl_dist * rr)
            else:
                sl = entry + sl_dist
                tp = entry - (sl_dist * rr)
            
            # Risk 1%
            risk_amt = capital * 0.01
            size = risk_amt / sl_dist
            
            open_trade = {'type': signal, 'entry': entry, 'sl': sl, 'tp': tp, 'size': size}

    return {
        'pnl_pct': (balance - capital) / capital * 100,
        'max_dd_pct': (max_dd / capital) * 100,
        'trades': len(trades),
        'start_date': sample.index[0]
    }

def run_robustness_test():
    pair = "GBPUSD=X" # Primary pair
    df = download_data(pair, period="1y", interval="1h")
    if df.empty: return
    
    df = calculate_hybrid_signal(df)
    
    # 12 Random Samples
    results = []
    
    print(f"\n--- ROBUSTNESS TEST (12 Months, H1 Data) ---")
    print(f"Strategy: Hybrid (Trend + Range) on {pair}")
    
    # Simple sampling: pick 12 random indices
    # Ensure they are somewhat spread?
    # Or just random uniform.
    
    # Valid indices (need 200 warmup)
    max_start = len(df) - 360 - 1
    if max_start < 200:
        print("Not enough data.")
        return
        
    for i in range(12):
        start_idx = random.randint(200, max_start)
        res = simulate_sample(df, start_idx)
        if res:
            results.append(res)
            print(f"Sample {i+1} ({res['start_date'].date()}): PnL={res['pnl_pct']:.2f}% | DD={res['max_dd_pct']:.2f}% | Trades={res['trades']}")

    # Summary
    pnls = [r['pnl_pct'] for r in results]
    dds = [r['max_dd_pct'] for r in results]
    wins = len([p for p in pnls if p > 0])
    pass_challenge = len([p for p in pnls if p >= 10 and r['max_dd_pct'] < 10 for r in [p]]) 
    # Logic error in comprehension above, fix:
    passes = 0
    failures = 0
    for r in results:
        if r['pnl_pct'] >= 10 and r['max_dd_pct'] < 10:
            passes += 1
        elif r['max_dd_pct'] >= 10:
            failures += 1
            
    avg_pnl = sum(pnls) / len(pnls)
    avg_dd = sum(dds) / len(dds)
    
    print(f"\n--- SUMMARY ---")
    print(f"Avg PnL: {avg_pnl:.2f}%")
    print(f"Avg DD:  {avg_dd:.2f}%")
    print(f"Win Rate (Positive Samples): {wins}/12 ({(wins/12)*100:.0f}%)")
    print(f"Challenge Pass Rate: {passes}/12 ({(passes/12)*100:.0f}%)")
    print(f"Blowout Rate (>10% DD): {failures}/12")

if __name__ == "__main__":
    run_robustness_test()
