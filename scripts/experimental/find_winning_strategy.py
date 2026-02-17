#!/usr/bin/env python3
"""
NANOBOT EVOLUTIONARY SEARCH (The "Loop")
Target: Find a strategy configuration that passes the 15-day challenge in current conditions.
Data: yfinance (Last 60 days).
Search Space: Trend (EMA), Mean Reversion (RSI), Breakout (Bollinger).
Optimization: Random Search / Monte Carlo (1000 Iterations).
"""
import yfinance as yf
import pandas as pd
import numpy as np
import random
from datetime import datetime
import multiprocessing as mp

# --- CONFIGURATION SPACE ---
STRATEGIES = ['EMA_CROSS', 'RSI_REVERSION', 'BOLLINGER_BREAKOUT']
TIMEFRAMES = ['15m', '30m', '1h']
EMA_PAIRS = [(5, 12), (9, 15), (9, 21), (20, 50), (50, 200)]
RSI_PERIODS = [7, 14, 21]
RSI_BOUNDS = [(30, 70), (25, 75), (20, 80), (35, 65)]
TP_SL_RATIOS = [1.0, 1.5, 2.0, 3.0]
RISK_PER_TRADE = [0.005, 0.01] # 0.5% or 1%
TRADING_HOURS = [(8, 17), (0, 24), (7, 11), (8, 12)] # NY, 24/7, London Open, NY Morning

def download_data(pairs):
    data = {}
    print("Downloading Data...")
    for pair in pairs:
        try:
            # Get 59 days (limit for some intraday intervals)
            df = yf.download(pair, period="59d", interval="15m", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            if not df.empty:
                data[pair] = df
        except Exception as e:
            print(f"Error {pair}: {e}")
    return data

def backtest_config(config, data_map):
    """Run a fast backtest for a specific configuration."""
    capital = 10000.0
    balance = capital
    equity_high = capital
    max_dd = 0
    trades = []
    
    # Unpack Config
    strat = config['strategy']
    pair_data = data_map[config['pair']] # Optimization per pair or portfolio? Let's do Portfolio.
    
    # Portfolio Loop is complex for simple fast search. 
    # Let's iterate linearly over time to check constraints.
    
    # Pre-calculate indicators based on strat
    df = data_map[config['pair']].copy()
    
    # Generic Indicators
    df['hour'] = df.index.hour
    
    if strat == 'EMA_CROSS':
        fast, slow = config['ema_pair']
        df['fast'] = df['close'].ewm(span=fast).mean()
        df['slow'] = df['close'].ewm(span=slow).mean()
        df['atr'] = calculate_atr(df)
        
    elif strat == 'RSI_REVERSION':
        period = config['rsi_period']
        df['rsi'] = calculate_rsi(df, period)
        df['atr'] = calculate_atr(df)
        
    elif strat == 'BOLLINGER_BREAKOUT':
        df['ma'] = df['close'].rolling(20).mean()
        df['std'] = df['close'].rolling(20).std()
        df['upper'] = df['ma'] + (2 * df['std'])
        df['lower'] = df['ma'] - (2 * df['std'])
        df['atr'] = calculate_atr(df)
    
    # Simulation
    # Vectorized signal generation? Hard with path dependent PnL.
    # Iterative approach.
    
    trade = None
    t_start, t_end = config['hours']
    rr = config['rr']
    risk = config['risk']
    
    # Restrict to last 15 days? Or full 60?
    # User wants to pass 15 day challenge. 
    # Let's test on LAST 30 DAYS (2 cycles).
    start_date = df.index[-1] - pd.Timedelta(days=30)
    df = df[df.index >= start_date]
    
    for i in range(50, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Check Trade
        if trade:
            if trade['type'] == 'buy':
                if curr['low'] <= trade['sl']:
                    pnl = (trade['sl'] - trade['entry']) * trade['size']
                    balance += pnl
                    trade = None
                elif curr['high'] >= trade['tp']:
                    pnl = (trade['tp'] - trade['entry']) * trade['size']
                    balance += pnl
                    trade = None
            else:
                if curr['high'] >= trade['sl']:
                    pnl = (trade['entry'] - trade['sl']) * trade['size']
                    balance += pnl
                    trade = None
                elif curr['low'] <= trade['tp']:
                    pnl = (trade['entry'] - trade['tp']) * trade['size']
                    balance += pnl
                    trade = None
                    
            # DD Check
            dd = equity_high - balance
            if dd > max_dd: max_dd = dd
            if balance > equity_high: equity_high = balance
            continue
            
        # Check Signal
        if not (t_start <= curr['hour'] < t_end):
            continue
            
        signal = None
        
        if strat == 'EMA_CROSS':
            # Trend Follow
            if curr['fast'] > curr['slow'] and prev['fast'] <= prev['slow']:
                signal = 'buy'
            elif curr['fast'] < curr['slow'] and prev['fast'] >= prev['slow']:
                signal = 'sell'
                
        elif strat == 'RSI_REVERSION':
            lower, upper = config['rsi_bounds']
            # Reversion: Buy Low, Sell High
            if curr['rsi'] < lower:
                signal = 'buy'
            elif curr['rsi'] > upper:
                signal = 'sell'
                
        elif strat == 'BOLLINGER_BREAKOUT':
            # Breakout: Buy > Upper, Sell < Lower
            if curr['close'] > curr['upper'] and prev['close'] <= prev['upper']:
                signal = 'buy'
            elif curr['close'] < curr['lower'] and prev['close'] >= prev['lower']:
                signal = 'sell'
                
        if signal:
            entry = curr['close']
            atr = curr['atr']
            if np.isnan(atr) or atr == 0: continue
            
            # SL/TP
            sl_dist = atr * 1.5 # Fixed structure for now
            if signal == 'buy':
                sl = entry - sl_dist
                tp = entry + (sl_dist * rr)
            else:
                sl = entry + sl_dist
                tp = entry - (sl_dist * rr)
                
            risk_amt = capital * risk
            size = risk_amt / sl_dist
            
            trade = {'type': signal, 'entry': entry, 'sl': sl, 'tp': tp, 'size': size}
            trades.append(trade)

    # Score
    pnl_pct = (balance - capital) / capital * 100
    dd_pct = (max_dd / capital) * 100
    trades_count = len(trades)
    
    # Fitness Function
    # We want: PnL > 10%, DD < 10%
    score = pnl_pct
    if dd_pct > 9: score -= 100 # Penalty for DD limit proximity
    if trades_count < 5: score -= 50 # Not statistically significant
    
    return {
        'config': config,
        'pnl': pnl_pct,
        'dd': dd_pct,
        'trades': trades_count,
        'score': score
    }

def calculate_atr(df, period=14):
    h, l, c = df['high'], df['low'], df['close']
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_search():
    pairs = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
    data = download_data(pairs)
    if not data: return
    
    iterations = 500
    results = []
    
    print(f"--- STARTING EVOLUTIONARY LOOP ({iterations} Iterations) ---")
    
    for i in range(iterations):
        # Generate Random Genome
        strat = random.choice(STRATEGIES)
        pair = random.choice(pairs)
        
        cfg = {
            'strategy': strat,
            'pair': pair,
            'ema_pair': random.choice(EMA_PAIRS),
            'rsi_period': random.choice(RSI_PERIODS),
            'rsi_bounds': random.choice(RSI_BOUNDS),
            'rr': random.choice(TP_SL_RATIOS),
            'risk': random.choice(RISK_PER_TRADE),
            'hours': random.choice(TRADING_HOURS)
        }
        
        res = backtest_config(cfg, data)
        results.append(res)
        
        if (i+1) % 50 == 0:
            print(f"Gen {i+1}: Best PnL so far: {max([r['pnl'] for r in results]):.2f}%")
            
    # Sort by Score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n\n🏆 --- TOP 3 SURVIVORS (Last 30 Days) ---")
    for r in results[:3]:
        c = r['config']
        print(f"\nStrategy: {c['strategy']} on {c['pair']}")
        print(f"  PnL: {r['pnl']:.2f}% | MaxDD: {r['dd']:.2f}% | Trades: {r['trades']}")
        print(f"  Params: RR={c['rr']}, Risk={c['risk']*100}%, Hours={c['hours']}")
        if c['strategy'] == 'EMA_CROSS': print(f"  EMA: {c['ema_pair']}")
        if c['strategy'] == 'RSI_REVERSION': print(f"  RSI: {c['rsi_period']} {c['rsi_bounds']}")

if __name__ == "__main__":
    run_search()
