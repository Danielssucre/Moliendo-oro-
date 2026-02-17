#!/usr/bin/env python3
"""
12-Month Sniper Mode Backtest (H1)
Data: yfinance (GBPUSD, 1y, 1h).
Strategy: Hybrid (ADX Trend + RSI Reversion).
Focus: Continuous equity curve analysis.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def download_data():
    symbol = "GBPUSD=X"
    print(f"Downloading {symbol} (1y, 1h)...")
    df = yf.download(symbol, period="1y", interval="1h", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df

def calculate_atr(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def run_simulation(df):
    if df is None or len(df) < 200: return None
    
    # 1. Indicators
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
    
    # 2. Simulation
    capital = 10000.0
    balance = capital
    equity = [capital]
    trades = []
    open_trade = None
    
    monthly_stats = {}
    
    start_idx = 200
    for i in range(start_idx, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        timestamp = curr.name
        month_key = timestamp.strftime("%Y-%m")
        
        if month_key not in monthly_stats:
            monthly_stats[month_key] = {'pnl': 0, 'trades': 0, 'wins': 0}
            
        # Manage Open Trade
        if open_trade:
            pnl = 0
            closed = False
            
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
                monthly_stats[month_key]['pnl'] += pnl
                monthly_stats[month_key]['trades'] += 1
                if pnl > 0: monthly_stats[month_key]['wins'] += 1
                open_trade = None
            
            equity.append(balance)
            continue
            
        # Signal Generation (08-16 H1 relaxed? Or strict 08-12?)
        # Keeping STRICT 08-12 to match strategy exactly as requested.
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
             entry = curr['close']
             
             if signal == "BUY":
                 sl = entry - sl_pips
                 tp = entry + (sl_pips * rr)
             else:
                 sl = entry + sl_pips
                 tp = entry - (sl_pips * rr)
                 
             # --- SMART BUFFER RISK CALCULATION ---
             # Logic: Risk 10% of the buffer (Equity - $9000)
             # Max Risk Cap: 2%
             
             hard_stop = 9000.0
             buffer_val = balance - hard_stop
             
             if buffer_val <= 0:
                 # Breach!
                 equity.append(balance)
                 continue
                 
             risk_amt = buffer_val * 0.10 # 10% of buffer
             
             # Caps
             if risk_amt > (balance * 0.02): risk_amt = balance * 0.02
             if risk_amt < (balance * 0.001): risk_amt = balance * 0.001 # Min size to trade
             
             size = risk_amt / sl_pips
             
             open_trade = {'type': signal, 'entry': entry, 'sl': sl, 'tp': tp, 'size': size}
        
        equity.append(balance)
        
    # Final Stats
    total_pnl = (balance - capital) / capital * 100
    peak = capital
    max_dd = 0
    for e in equity:
        if e > peak: peak = e
        dd = (peak - e) / capital * 100
        if dd > max_dd: max_dd = dd
        
    return {
        'total_pnl': total_pnl,
        'max_dd': max_dd,
        'total_trades': len(trades),
        'monthly': monthly_stats
    }

def main():
    print("--- 12-MONTH SNIPER MODE BACKTEST (GBPUSD H1) ---")
    df = download_data()
    res = run_simulation(df)
    
    if not res:
        print("Simulation failed (no data).")
        return
        
    print(f"\n📈 TOTAL PERFORMANCE:")
    print(f"  PnL: {res['total_pnl']:.2f}%")
    print(f"  Max DD: {res['max_dd']:.2f}%")
    print(f"  Trades: {res['total_trades']}")
    
    print(f"\n📅 MONTHLY BREAKDOWN:")
    sorted_months = sorted(res['monthly'].keys())
    for month in sorted_months:
        stats = res['monthly'][month]
        pnl_pct = (stats['pnl'] / 10000.0) * 100
        wr = 0 if stats['trades'] == 0 else (stats['wins'] / stats['trades']) * 100
        print(f"  {month}: {pnl_pct:6.2f}% | Trades: {stats['trades']:3} | WR: {wr:.0f}%")

if __name__ == "__main__":
    main()
