#!/usr/bin/env python3
"""
NANOBOT ASSET DISCOVERY TOOL (Phase 27)
Scans 20+ assets to find profitable candidates for the Hybrid Strategy.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
CANDIDATE_ASSETS = {
    # Forex Majors
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    
    # Forex Crosses (Volatile)
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "AUDJPY": "AUDJPY=X",
    
    # Indices (CFD)
    "US30 (Dow)": "^DJI",
    "US500 (S&P)": "^GSPC",
    "NAS100": "^IXIC",
    "DAX": "^GDAXI",
    "FTSE100": "^FTSE",
    
    # Metals/Energy
    "GOLD (XAU)": "GC=F",
    "SILVER": "SI=F",
    "CRUDE OIL": "CL=F",
    
    # Crypto
    "BTC-USD": "BTC-USD",
    "ETH-USD": "ETH-USD",
    "SOL-USD": "SOL-USD"
}

PERIOD = "60d"
INTERVAL = "15m"
CAPITAL = 10000
RISK_PCT = 0.01

# --- STRATEGY LOGIC (COPIED FROM run_multi_pair_yfinance.py) ---

def calculate_atr(df: pd.DataFrame, period: int = 14):
    """Calculate Average True Range."""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean()
    return atr

def calculate_hybrid_signal_backtest(df: pd.DataFrame):
    """
    Calculate Signal based on Market Regime (ADX Decision Tree).
    Returns a Series of signals: 1 (Buy), -1 (Sell), 0 (None)
    And extra columns for analysis.
    """
    # 1. Indicators
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    df['atr'] = calculate_atr(df)
    
    # ADX
    period = 14
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 2. Logic Loop (Vectorized logic is hard for complex state, using loop for clarity in backtest)
    signals = []
    
    for i in range(len(df)):
        if i < 200:
            signals.append(0)
            continue
            
        row = df.iloc[i]
        prev = df.iloc[i-1]
        
        sig = 0
        
        # Branch A: Trend (ADX > 25)
        if row['adx'] > 25:
            # Buy
            if (row['ema_9'] > row['ema_15'] and 
                prev['ema_9'] <= prev['ema_15'] and
                row['close'] > row['ema_200']):
                sig = 1
            # Sell
            elif (row['ema_9'] < row['ema_15'] and 
                  prev['ema_9'] >= prev['ema_15'] and
                  row['close'] < row['ema_200']):
                sig = -1
                
        # Branch B: Range (ADX <= 25)
        else:
            # Time Filter (08-12 UTC) - Optional for Discovery, let's keep it open or restrict?
            # User wants a robust portfolio. Let's apply the Best Window logic (08-12) as a filter?
            # Or scan ALL windows?
            # Let's verify if the 08-12 window works for other pairs.
            # Actually, let's run WITHOUT time filter first to see raw potential.
            
            if row['rsi'] < 35:
                sig = 1
            elif row['rsi'] > 65:
                sig = -1
        
        signals.append(sig)
        
    df['signal'] = signals
    return df

def backtest_asset(symbol, name):
    try:
        data = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False) # Removed show_errors=False
        if data.empty or len(data) < 200:
            return None
            
        # Fix columns (lowercase)
        data.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in data.columns]
        # Handle yfinance multi-index if present
        if 'close' not in data.columns and 'Close' not in data.columns:
             # Try accessing level 0 if multiindex
             pass

        # Cleanup yfinance mess
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0).str.lower()
        else:
            data.columns = data.columns.str.lower()
            
        if 'adj close' in data.columns:
            data.rename(columns={'adj close': 'adj_close'}, inplace=True)
            
        df = calculate_hybrid_signal_backtest(data)
        
        # Simulate Trades
        trades = []
        in_trade = False
        entry_price = 0
        direction = 0
        sl = 0
        tp = 0
        
        balance = CAPITAL
        equity_curve = [CAPITAL]
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            if pd.isna(row['atr']) or row['atr'] == 0:
                continue
            
            # Check Exit
            if in_trade:
                result = 0
                exit_price = 0
                
                # Check SL/TP hits (using High/Low)
                if direction == 1: # Long
                    if row['low'] <= sl:
                        result = -1 # SL Hit
                        exit_price = sl
                    elif row['high'] >= tp:
                        result = 1 # TP Hit
                        exit_price = tp
                else: # Short
                    if row['high'] >= sl:
                        result = -1 # SL Hit
                        exit_price = sl
                    elif row['low'] <= tp:
                        result = 1 # TP Hit
                        exit_price = tp
                
                if result != 0:
                    pnl_raw = (exit_price - entry_price) * direction
                    trades.append(pnl_raw)
                    
                    # Risk calc (Simplified)
                    # We risk 1% of balance.
                    # PnL $ = (Risk Amount / SL dist) * PnL raw
                    risk_amount = balance * RISK_PCT
                    sl_dist = abs(entry_price - sl)
                    if sl_dist == 0: sl_dist = 0.0001
                    position_size = risk_amount / sl_dist
                    
                    pnl_dollar = pnl_raw * position_size
                    balance += pnl_dollar
                    in_trade = False
            
            equity_curve.append(balance)
            
            # Check Entry
            if not in_trade and row['signal'] != 0:
                direction = row['signal']
                entry_price = row['close']
                atr = row['atr']
                
                # Dynamic Risk based on strategy
                # Trend: SL 1.0 ATR, TP 2.0 ATR
                # Range: SL 1.5 ATR, TP 3.0 ATR
                
                if row['adx'] > 25: # Trend
                    sl_mult = 1.0
                    rr = 2.0
                else: # Range
                    sl_mult = 1.5
                    rr = 3.0
                    
                sl_dist = atr * sl_mult
                
                if direction == 1:
                    sl = entry_price - sl_dist
                    tp = entry_price + (sl_dist * rr)
                else:
                    sl = entry_price + sl_dist
                    tp = entry_price - (sl_dist * rr)
                    
                in_trade = True
                
        # Metrics
        final_balance = balance
        total_pnl = (final_balance - CAPITAL) / CAPITAL * 100
        total_trades = len(trades)
        wins = len([t for t in trades if t > 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Max Drawdown
        peaks = pd.Series(equity_curve).cummax()
        drawdown = (pd.Series(equity_curve) - peaks) / peaks * 100
        max_dd = abs(drawdown.min())
        
        return {
            "Asset": name,
            "PnL %": total_pnl,
            "Trades": total_trades,
            "Win Rate": win_rate,
            "Max DD": max_dd,
            "PF": 0 # TODO calculate PF
        }
        
    except Exception as e:
        logger.error(f"Error processing {name}: {e}")
        return None

def main():
    print("🌍 STARTING PORTFOLIO DISCOVERY VOYAGE...")
    print(f"   Scanning {len(CANDIDATE_ASSETS)} assets over {PERIOD} ({INTERVAL})...")
    print("-" * 65)
    print(f"{'ASSET':<15} {'PnL %':<10} {'MAX DD':<10} {'TRADES':<10} {'WIN RATE':<10}")
    print("-" * 65)
    
    results = []
    
    for name, symbol in CANDIDATE_ASSETS.items():
        res = backtest_asset(symbol, name)
        if res:
            results.append(res)
            print(f"{res['Asset']:<15} {res['PnL %']:<10.2f} {res['Max DD']:<10.2f} {res['Trades']:<10} {res['Win Rate']:<10.1f}")
        else:
             print(f"{name:<15} ERROR/NO DATA")
             
    # Sort by PnL
    results.sort(key=lambda x: x['PnL %'], reverse=True)
    
    print("\n🏆 LEADERBOARD:")
    for i, res in enumerate(results[:5]):
        print(f"{i+1}. {res['Asset']} (+{res['PnL %']:.2f}%)")

if __name__ == "__main__":
    main()
