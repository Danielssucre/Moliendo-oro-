#!/usr/bin/env python3
"""
BTC-USD Hybrid Strategy Backtest
1. 60-Day M15 (Precision Test)
2. 12-Month H1 (Robustness Test)
Strategy: Hybrid ADX (Trend 9/15 + Range RSI).
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

PAIR = "BTC-USD"
CAPITAL = 10000.0

def download_data(symbol, period, interval):
    print(f"Downloading {symbol} ({period}, {interval})...")
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df

def calculate_atr(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def run_simulation(df, timeframe_label):
    if df is None or len(df) < 200: 
        print(f"Not enough data for {timeframe_label}")
        return
        
    # Indicators
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    atr = calculate_atr(df)
    df['atr'] = atr
    
    # ADX
    up, down = df['high'].diff(), -df['low'].diff()
    plus_dm, minus_dm = pd.Series(0.0, index=df.index), pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    atr_smooth = atr.ewm(alpha=1/14, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Simulation
    balance = CAPITAL
    equity = [CAPITAL]
    trades = []
    open_trade = None
    
    start_idx = 200
    
    for i in range(start_idx, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Open Trade
        if open_trade:
            closed = False
            pnl = 0
            if open_trade['type'] == 'BUY':
                if curr['low'] <= open_trade['sl']:
                    pnl = (open_trade['sl'] - open_trade['entry']) * open_trade['size']
                    closed = True
                elif curr['high'] >= open_trade['tp']:
                    pnl = (open_trade['tp'] - open_trade['entry']) * open_trade['size']
                    closed = True
            else:
                 if curr['high'] >= open_trade['sl']:
                    pnl = (open_trade['entry'] - open_trade['sl']) * open_trade['size']
                    closed = True
                 elif curr['low'] <= open_trade['tp']:
                    pnl = (open_trade['entry'] - open_trade['tp']) * open_trade['size']
                    closed = True
            
            if closed:
                balance += pnl
                trades.append(pnl)
                open_trade = None
            
            equity.append(balance)
            continue
            
        # Signal
        # Strategy requires 08-12 window. Does this apply to BTC?
        # Let's KEEP IT SAME as User said "don't change code/logic".
        
        if not (8 <= curr.name.hour < 12):
            equity.append(balance)
            continue
            
        adx = curr['adx']
        signal = None
        sl_mult = 1.0; rr = 1.0
        
        # TREND
        if adx > 25:
             if curr['ema_9'] > curr['ema_15'] and prev['ema_9'] <= prev['ema_15'] and curr['close'] > curr['ema_200']:
                 signal = "BUY"; rr = 2.0; sl_mult = 1.0
             elif curr['ema_9'] < curr['ema_15'] and prev['ema_9'] >= prev['ema_15'] and curr['close'] < curr['ema_200']:
                 signal = "SELL"; rr = 2.0; sl_mult = 1.0
        # RANGE
        else:
             if curr['rsi'] < 35:
                 signal = "BUY"; rr = 3.0; sl_mult = 1.5
             elif curr['rsi'] > 65:
                 signal = "SELL"; rr = 3.0; sl_mult = 1.5
        
        if signal:
             atr_val = curr['atr']
             if np.isnan(atr_val) or atr_val == 0: 
                 equity.append(balance)
                 continue
                 
             sl_pips = atr_val * sl_mult 
             # Note: For BTC, "pips" is just price diff.
             entry = curr['close']
             
             if signal == "BUY":
                 sl = entry - sl_pips
                 tp = entry + (sl_pips * rr)
             else:
                 sl = entry + sl_pips
                 tp = entry - (sl_pips * rr)
                 
             # Risk 1%
             risk_amt = CAPITAL * 0.01
             size = risk_amt / sl_pips
             
             open_trade = {'type': signal, 'entry': entry, 'sl': sl, 'tp': tp, 'size': size}

    # Results
    pnl_pct = (balance - CAPITAL) / CAPITAL * 100
    peak = CAPITAL
    max_dd = 0
    for e in equity:
        if e > peak: peak = e
        dd = (peak - e) / CAPITAL * 100
        if dd > max_dd: max_dd = dd
        
    print(f"\nRESULTS: {timeframe_label}")
    print(f"  PnL: {pnl_pct:.2f}%")
    print(f"  Max DD: {max_dd:.2f}%")
    print(f"  Trades: {len(trades)}")

def main():
    print(f"--- BTC-USD STRATEGY TEST (Hybrid 08-12 Window) ---")
    
    # 1. M15 Test (Last 60 Days)
    df_m15 = download_data(PAIR, "59d", "15m")
    run_simulation(df_m15, "M15 (Last 60 Days)")
    
    # 2. H1 Test (Last 12 Months)
    df_h1 = download_data(PAIR, "1y", "1h")
    run_simulation(df_h1, "H1 (Last 12 Months)")
    
if __name__ == "__main__":
    main()
