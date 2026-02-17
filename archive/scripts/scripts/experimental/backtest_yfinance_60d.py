#!/usr/bin/env python3
"""
60-Day Backtest (M15) - Hybrid Strategy
Data: yfinance (Last 59 days, M15).
Strategy: Hybrid (ADX Decision Tree).
   - Trend: EMA 9/15 (ADX > 25)
   - Range: RSI Reversion (ADX <= 25)
"""
import yfinance as yf
import pandas as pd
import numpy as np
import sys

# --- CONFIGURATION ---
PAIRS = ["GBPUSD=X"]
CAPITAL = 10000.0  # Per Pair or Total? Let's do Portfolio Start $10k total? 
# Better: $10k per pair to see individual performance cleanliness.
# Or $10k Total, allocated.
# Let's simple sum results.

def download_data(symbol):
    print(f"Downloading {symbol} (59d, 15m)...")
    try:
        df = yf.download(symbol, period="59d", interval="15m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"Error: {e}")
        return None

def calculate_atr(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def run_backtest(df):
    if df is None or len(df) < 200: return None
    
    # Indicators
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ADX
    atr = calculate_atr(df)
    df['atr'] = atr  # Fix: Assign to DataFrame
    
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
    capital = 10000.0
    balance = capital
    equity = [capital]
    trades = []
    open_trade = None
    
    # Start loop
    start_idx = 200
    
    for i in range(start_idx, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # 1. Manage Trade
        if open_trade:
            # Approx M15 OHLC check
            # Assume we get stopped out if Low < SL, etc.
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
                open_trade = None
            
            equity.append(balance)
            continue
            
        # 2. Check Signal (08-12 Window)
        if not (8 <= curr.name.hour < 12):
            equity.append(balance)
            continue
            
        adx = curr['adx']
        signal = None
        sl_dist = 0; tp_dist = 0
        
        # TREND (ADX > 25)
        if adx > 25:
             if curr['ema_9'] > curr['ema_15'] and prev['ema_9'] <= prev['ema_15'] and curr['close'] > curr['ema_200']:
                 signal = "BUY"; rr = 2.0; sl_mult = 1.0
             elif curr['ema_9'] < curr['ema_15'] and prev['ema_9'] >= prev['ema_15'] and curr['close'] < curr['ema_200']:
                 signal = "SELL"; rr = 2.0; sl_mult = 1.0
        # RANGE (ADX <= 25)
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
                 
             # Risk 1%
             risk_amt = capital * 0.01
             size = risk_amt / sl_pips
             
             open_trade = {'type': signal, 'entry': entry, 'sl': sl, 'tp': tp, 'size': size}
        
        equity.append(balance)

    # Stats
    peak = capital
    max_dd = 0
    for e in equity:
        if e > peak: peak = e
        dd = (peak - e) / capital * 100
        if dd > max_dd: max_dd = dd
        
    pnl_pct = (balance - capital) / capital * 100
    win_rate = 0
    if trades:
        wins = len([t for t in trades if t > 0])
        win_rate = (wins / len(trades)) * 100
        
    return {
        'pnl': pnl_pct,
        'dd': max_dd,
        'trades': len(trades),
        'win_rate': win_rate
    }

def main():
    print("--- 60-DAY M15 BACKTEST (Hybrid Strategy) ---")
    
    grand_total_pnl = 0
    
    for pair in PAIRS:
        df = download_data(pair)
        res = run_backtest(df)
        if res:
            print(f"\n{pair}:")
            print(f"  PnL: {res['pnl']:.2f}%")
            print(f"  Max DD: {res['dd']:.2f}%")
            print(f"  Trades: {res['trades']}")
            print(f"  Win Rate: {res['win_rate']:.1f}%")
            grand_total_pnl += res['pnl']
            
    print(f"\n{'='*30}")
    print(f"PORTFOLIO TOTAL PnL: {grand_total_pnl:.2f}% (Sum of 3 pairs)")
    print(f"{'='*30}")

if __name__ == "__main__":
    main()
