#!/usr/bin/env python3
"""
Backtest 30 Days using yfinance data (Standalone Logic).
Strategy: lit_ema_9_15_atr (EMA 9/15 Cross + ATR > ATR_Avg * 1.1)
Capital: $10,000
"""
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def download_data(symbol, period="30d", interval="15m"):
    """Download data from yfinance."""
    print(f"Downloading {symbol} data ({period}, {interval})...")
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            print(f"No data for {symbol}")
            return None
        # Handle MultiIndex columns (common in recent yfinance)
        if isinstance(df.columns, pd.MultiIndex):
            # Keep only the top level (Price Type)
            df.columns = df.columns.get_level_values(0)
            
        # Standardize columns
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"Error downloading {symbol}: {e}")
        return None

def calculate_indicators(df):
    """Calculate EMAs and ATR."""
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean() # Trend Filter
    
    # ATR 14
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ATR MA 20
    df['atr_avg'] = df['atr'].rolling(20).mean()
    
    return df

def run_backtest():
    capital = 10000.0
    pairs = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
    risk_per_trade = 0.01 # 1%
    
    print(f"--- STARTING BACKTEST (30 Days, $10k) ---")
    print(f"Strategy: EMA 9/15 Cross + ATR Volatility + EMA 200 Trend Filter")
    
    portfolio_pnl = 0
    total_trades = 0
    total_wins = 0
    
    for pair in pairs:
        df = download_data(pair)
        if df is None: continue
        
        df = calculate_indicators(df)
        
        trades = []
        open_trade = None
        
        # Iterate through candles
        start_idx = 200 # Need 200 data points for EMA 200
        
        for i in range(start_idx, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i-1]
            
            # Update Open Trade PnL/Exit
            if open_trade:
                if open_trade['Type'] == 'BUY':
                    if curr['low'] <= open_trade['SL']:
                        exit_price = open_trade['SL']
                        pnl = (exit_price - open_trade['Entry']) * open_trade['Size']
                        open_trade['Exit'] = exit_price
                        open_trade['PnL'] = pnl
                        trades.append(open_trade)
                        open_trade = None
                    elif curr['high'] >= open_trade['TP']:
                        exit_price = open_trade['TP']
                        pnl = (exit_price - open_trade['Entry']) * open_trade['Size']
                        open_trade['Exit'] = exit_price
                        open_trade['PnL'] = pnl
                        trades.append(open_trade)
                        open_trade = None
                
                elif open_trade['Type'] == 'SELL':
                    if curr['high'] >= open_trade['SL']:
                        exit_price = open_trade['SL']
                        pnl = (open_trade['Entry'] - exit_price) * open_trade['Size']
                        open_trade['Exit'] = exit_price
                        open_trade['PnL'] = pnl
                        trades.append(open_trade)
                        open_trade = None
                    elif curr['low'] <= open_trade['TP']:
                        exit_price = open_trade['TP']
                        pnl = (open_trade['Entry'] - exit_price) * open_trade['Size']
                        open_trade['Exit'] = exit_price
                        open_trade['PnL'] = pnl
                        trades.append(open_trade)
                        open_trade = None
                        
            # Check Entry Signal
            if open_trade is None:
                is_volatile = curr['atr'] > (curr['atr_avg'] * 1.1)
                
                # BUY: Cross UP + Volatility + Price > EMA 200
                if (curr['ema_9'] > curr['ema_15'] and 
                    prev['ema_9'] <= prev['ema_15'] and 
                    is_volatile and
                    curr['close'] > curr['ema_200']):
                    
                    sl = curr['close'] - curr['atr'] 
                    tp = curr['close'] + (curr['atr'] * 1.5)
                    dist = curr['close'] - sl
                    risk_amt = capital * risk_per_trade
                    size = risk_amt / dist
                    
                    open_trade = {
                        'Pair': pair, 'Type': 'BUY', 'Entry': curr['close'],
                        'SL': sl, 'TP': tp, 'Size': size, 'Time': curr.name, 'PnL': 0
                    }
                    
                # SELL: Cross DOWN + Volatility + Price < EMA 200
                elif (curr['ema_9'] < curr['ema_15'] and 
                      prev['ema_9'] >= prev['ema_15'] and 
                      is_volatile and
                      curr['close'] < curr['ema_200']):
                    
                    sl = curr['close'] + curr['atr']
                    tp = curr['close'] - (curr['atr'] * 1.5)
                    dist = sl - curr['close']
                    risk_amt = capital * risk_per_trade
                    size = risk_amt / dist
                    
                    open_trade = {
                        'Pair': pair, 'Type': 'SELL', 'Entry': curr['close'],
                        'SL': sl, 'TP': tp, 'Size': size, 'Time': curr.name, 'PnL': 0
                    }

        # Summary for Pair
        pair_pnl_val = sum(t['PnL'] for t in trades)
        pair_wins = len([t for t in trades if t['PnL'] > 0])
        pair_trades = len(trades)
        pair_wr = (pair_wins / pair_trades * 100) if pair_trades > 0 else 0
        
        print(f"{pair}: PnL=${pair_pnl_val:,.2f} | Trades={pair_trades} | WR={pair_wr:.1f}%")
        
        portfolio_pnl += pair_pnl_val
        total_trades += pair_trades
        total_wins += pair_wins

    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
    final_balance = capital + portfolio_pnl
    
    print(f"\n--- PORTFOLIO SUMMARY ---")
    print(f"Initial Capital: ${capital:,.2f}")
    print(f"Final Balance:   ${final_balance:,.2f}")
    print(f"Total PnL:       ${portfolio_pnl:,.2f} ({portfolio_pnl/capital*100:.2f}%)")
    print(f"Total Trades:    {total_trades}")
    print(f"Win Rate:        {total_wr:.1f}%")

if __name__ == "__main__":
    run_backtest()
