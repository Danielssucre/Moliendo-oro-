#!/usr/bin/env python3
"""
15-Day Prop Firm Challenge Simulation (Aggressive Mode).
Target: +10% Profit in 15 Days.
Max DD: 10% (Hard Limit).
Strategies: EMA 9/15 + ATR + EMA 200 (Trend Following).
Risk: 1.0% per trade (Aggressive for Challenge).
"""
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def download_data(symbol, period="15d", interval="15m"):
    """Download data from yfinance (15 days)."""
    print(f"Downloading {symbol} data ({period}, {interval})...")
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            print(f"No data for {symbol}")
            return None
        
        # Handle MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Standardize columns
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"Error downloading {symbol}: {e}")
        return None

def calculate_indicators(df):
    """Calculate EMAs and ADX."""
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ADX Calculation
    period = 14
    high = df['high']
    low = df['low']
    close = df['close']
    
    # TR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    df['atr'] = atr # Need ATR for SL/TP too
    
    # DM
    up = high.diff()
    down = -low.diff()
    
    # +DM
    plus_dm = pd.Series(0.0, index=df.index)
    mask_plus = (up > down) & (up > 0)
    plus_dm[mask_plus] = up[mask_plus]
    
    # -DM
    minus_dm = pd.Series(0.0, index=df.index)
    mask_minus = (down > up) & (down > 0)
    minus_dm[mask_minus] = down[mask_minus]
    
    # Smooth
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    df['adx'] = adx
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    
    return df

def run_challenge():
    capital = 10000.0
    pairs = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
    risk_per_trade = 0.01 
    profit_target = 1000.0
    max_drawdown_limit = 1000.0
    
    print(f"\n=======================================================")
    print(f"🏆 15-DAY PROP FIRM CHALLENGE SIMULATION (ADX MODE)")
    print(f"=======================================================")
    print(f"Strategy: EMA 9/15 + ADX (>20, Directional) + EMA 200")
    print(f"Risk/Trade: 1.0%")
    print(f"-------------------------------------------------------\n")
    
    portfolio_pnl = 0
    total_trades = 0
    equity_curve = [capital]
    peak_equity = capital
    max_dd_val = 0
    
    # We need to simulate time properly to track DAILY drawdown?
    # For now, we simulate sequentially per pair (simplified) but tracking global DD approx.
    # To be precise, we should merge dataframes on time index.
    # Let's do a sequential run per pair and sum up, checking DD on the aggregate if possible.
    # Merging is better.
    
    data_map = {}
    for pair in pairs:
        df = download_data(pair, period="15d")
        if df is not None:
            df = calculate_indicators(df)
            data_map[pair] = df
    
    if not data_map:
        print("No data available.")
        return

    # Create a global timeline
    # Get all timestamps
    all_dates = sorted(list(set().union(*[d.index for d in data_map.values()])))
    
    # Simulation state
    open_trades = {p: None for p in pairs}
    balance = capital
    
    print(f"Simulating {len(all_dates)} candles across {len(pairs)} pairs...")
    
    trades_log = []
    
    for current_time in all_dates:
        # Check Max DD
        current_equity = balance + sum([
            (t['Entry'] - t['Entry'])*0 if t else 0 for t in open_trades.values() 
            # Approximate equity of open trades (ignoring fluctuation for speed, assuming close only on signal)
            # Actually, let's just track CLOSED trade DD for simplicity unless we want strict equity DD
        ])
        
        # Proper DD tracking involves MTM (Mark to Market).
        # We'll check DD at balance level for simplicity.
        if balance > peak_equity:
            peak_equity = balance
        dd = peak_equity - balance
        if dd > max_dd_val:
            max_dd_val = dd
            
        if dd >= max_drawdown_limit:
            print(f"\n❌ FAILED: Max Drawdown Violated! (-${dd:.2f})")
            break
            
        # Process each pair
        for pair in pairs:
            if pair not in data_map: continue
            df = data_map[pair]
            if current_time not in df.index: continue
            
            # Get candle (row)
            # Efficient lookup?
            # Creating a unified dataframe is better but let's try direct index access if fast enough
            try:
                curr = df.loc[current_time]
                # Need previous candle for signal
                # integer location needed
                idx_int = df.index.get_loc(current_time)
                if idx_int < 200: continue # Warmup
                prev = df.iloc[idx_int-1]
            except KeyError:
                continue
                
            open_trade = open_trades[pair]
            
            # Manage Open Trade
            if open_trade:
                # Check SL/TP
                if open_trade['Type'] == 'BUY':
                    if curr['low'] <= open_trade['SL']:
                        # SL Hit
                        pnl = (open_trade['SL'] - open_trade['Entry']) * open_trade['Size']
                        balance += pnl
                        open_trades[pair] = None
                        trades_log.append(pnl)
                    elif curr['high'] >= open_trade['TP']:
                        # TP Hit
                        pnl = (open_trade['TP'] - open_trade['Entry']) * open_trade['Size']
                        balance += pnl
                        open_trades[pair] = None
                        trades_log.append(pnl)
                
                elif open_trade['Type'] == 'SELL':
                    if curr['high'] >= open_trade['SL']:
                        # SL Hit
                        pnl = (open_trade['Entry'] - open_trade['SL']) * open_trade['Size']
                        balance += pnl
                        open_trades[pair] = None
                        trades_log.append(pnl)
                    elif curr['low'] <= open_trade['TP']:
                        # TP Hit
                        pnl = (open_trade['Entry'] - open_trade['TP']) * open_trade['Size']
                        balance += pnl
                        open_trades[pair] = None
                        trades_log.append(pnl)
            
            # Entry Signal
            if open_trades[pair] is None:
                # Logic: EMA Cross + ADX + Trend
                # ADX Strength + Directional Match (+DI > -DI for Buy)
                # Also check ADX rising? df['adx'].iloc[i] > df['adx'].iloc[i-1]
                
                adx_ok = curr['adx'] > 20 and curr['adx'] > prev['adx']
                
                # BUY: Cross UP + ADX OK + +DI > -DI + Price > EMA 200
                if (curr['ema_9'] > curr['ema_15'] and 
                    adx_ok and
                    curr['plus_di'] > curr['minus_di'] and
                    curr['close'] > curr['ema_200']):
                    
                    sl = curr['close'] - curr['atr']
                    tp = curr['close'] + (curr['atr'] * 1.5)
                    dist = curr['close'] - sl
                    risk_amt = capital * risk_per_trade
                    size = risk_amt / dist
                    
                    open_trades[pair] = {
                        'Type': 'BUY', 'Entry': curr['close'], 'SL': sl, 'TP': tp, 'Size': size
                    }
                
                # SELL: Cross DOWN + ADX OK + -DI > +DI + Price < EMA 200
                elif (curr['ema_9'] < curr['ema_15'] and 
                      adx_ok and
                      curr['minus_di'] > curr['plus_di'] and
                      curr['close'] < curr['ema_200']):
                    
                    sl = curr['close'] + curr['atr']
                    tp = curr['close'] - (curr['atr'] * 1.5)
                    dist = sl - curr['close']
                    risk_amt = capital * risk_per_trade
                    size = risk_amt / dist
                    
                    open_trades[pair] = {
                        'Type': 'SELL', 'Entry': curr['close'], 'SL': sl, 'TP': tp, 'Size': size
                    }

    # Final Stats
    total_pnl = balance - capital
    pnl_percent = (total_pnl / capital) * 100
    
    print(f"\n=======================================================")
    print(f"📊 CHALLENGE RESULTS")
    print(f"=======================================================")
    print(f"Final Balance:   ${balance:,.2f}")
    print(f"Total PnL:       ${total_pnl:,.2f} ({pnl_percent:.2f}%)")
    print(f"Max Drawdown:    ${max_dd_val:,.2f} ({(max_dd_val/capital)*100:.2f}%)")
    print(f"Total Trades:    {len(trades_log)}")
    
    if len(trades_log) > 0:
        wins = len([t for t in trades_log if t > 0])
        wr = (wins / len(trades_log)) * 100
        print(f"Win Rate:        {wr:.1f}%")
    
    print(f"-------------------------------------------------------")
    
    if total_pnl >= profit_target:
        print(f"✅ PASSED! Target Reached (+10%)")
    elif max_dd_val >= max_drawdown_limit:
         print(f"❌ FAILED! Max Drawdown Exceeded")
    elif total_pnl > 0:
        print(f"⚠️  PROFITABLE BUT FAILED: Did not reach +10% target in 15 days.")
    else:
        print(f"❌ FAILED: Negative PnL")

if __name__ == "__main__":
    run_challenge()
