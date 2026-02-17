#!/usr/bin/env python3
"""
NANOBOT PORTFOLIO SIMULATOR (Phase 27)
Simulates a Multi-Asset Prop Firm Challenge (5 Assets Combined).
"""
import yfinance as yf
import pandas as pd
import numpy as np
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- PROP FIRM CONFIGURATION ---
INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 0.002  # 0.2% conservative risk for Prop Firm
MAX_DAILY_DD = 0.05     # 5% Daily Limit
MAX_TOTAL_DD = 0.10     # 10% Total Limit
PROFIT_TARGET = 0.10    # 10% Target
PERIOD = "60d"
INTERVAL = "15m"

PORTFOLIO = {
    "SOL-USD": "SOL-USD",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "BTC-USD": "BTC-USD",
    "GBPUSD": "GBPUSD=X"
}

# --- LOGIC (Simplified Signal Generation) ---
def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def generate_signals(df):
    # Indicators
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['atr'] = calculate_atr(df)
    
    # ADX
    period = 14
    high = df['high']; low = df['low']; close = df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    signals = []
    for i in range(len(df)):
        if i < 200:
            signals.append(0); continue
        
        row = df.iloc[i]; prev = df.iloc[i-1]
        sig = 0
        
        # Branch A: Trend (ADX > 25)
        if row['adx'] > 25:
            if row['ema_9'] > row['ema_15'] and prev['ema_9'] <= prev['ema_15'] and row['close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and prev['ema_9'] >= prev['ema_15'] and row['close'] < row['ema_200']: sig = -1
        # Branch B: Range (ADX <= 25)
        else:
            if row['rsi'] < 35: sig = 1
            elif row['rsi'] > 65: sig = -1
            
        signals.append(sig)
    
    df['signal'] = signals
    return df

def simulate_portfolio():
    print(f"🔄 LOADING DATA for {len(PORTFOLIO)} assets...")
    
    # Check yfinance version/args
    # Assuming standard download works
    # We need to sync timestamps. 15m data might have gaps.
    # Strategy: Loop through time from Start to End, check each asset.
    # Better: generate trade list for each asset with timestamps, then merge and replay.
    
    all_trades = []
    
    for name, symbol in PORTFOLIO.items():
        print(f"   Downloading {name}...", end="\r")
        try:
            data = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False)
            if data.empty: continue
            
            # Clean
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0).str.lower()
            else: data.columns = data.columns.str.lower()
            
            # Signals
            df = generate_signals(data)
            
            # Iterate
            in_trade = False
            entry_price = 0; direction = 0; sl = 0; tp = 0
            
            for index, row in df.iterrows():
                timestamp = index
                if pd.isna(row['atr']) or row['atr'] == 0: continue
                
                # Check Exit
                if in_trade:
                    result = 0; exit_price = 0
                    if direction == 1:
                        if row['low'] <= sl: result = -1; exit_price = sl
                        elif row['high'] >= tp: result = 1; exit_price = tp
                    else:
                        if row['high'] >= sl: result = -1; exit_price = sl
                        elif row['low'] <= tp: result = 1; exit_price = tp
                    
                    if result != 0:
                        # Trade Closed
                        # Calculate R-Multiple (not dollar yet)
                        # R = (Exit - Entry) / (Entry - SL) * Direction
                        # Actually easier: PnL raw.
                        
                        # We store: timestamp, asset, result (R-units or similar)
                        # We will calculate $ based on dynamic balance later.
                        
                        r_value = 0
                        risk_distance = abs(entry_price - sl)
                        pnl_raw = (exit_price - entry_price) * direction
                        
                        r_multiple = pnl_raw / risk_distance
                        
                        all_trades.append({
                            'time': timestamp,
                            'asset': name,
                            'type': 'exit',
                            'r_multiple': r_multiple
                        })
                        in_trade = False
                
                # Check Entry
                if not in_trade and row['signal'] != 0:
                    direction = row['signal']
                    entry_price = row['close']
                    atr = row['atr']
                    
                    if row['adx'] > 25: # Trend
                        sl_mult = 1.0; rr = 2.0
                    else: # Range
                        sl_mult = 1.5; rr = 3.0
                    
                    sl_dist = atr * sl_mult
                    if direction == 1: sl = entry_price - sl_dist; tp = entry_price + (sl_dist * rr)
                    else: sl = entry_price + sl_dist; tp = entry_price - (sl_dist * rr)
                    
                    in_trade = True
                    
        except Exception as e:
            print(f"Error {name}: {e}")

    # --- REPLAY TRADES ---
    print("\n🎬 SIMULATING PORTFOLIO EQUITY CURVE...")
    
    # Sort trades by time
    all_trades.sort(key=lambda x: x['time'])
    
    balance = INITIAL_CAPITAL
    equity_curve = [INITIAL_CAPITAL]
    
    wins = 0; losses = 0
    gross_win = 0; gross_loss = 0
    
    # Daily Tracking
    current_day = None
    daily_start_balance = INITIAL_CAPITAL
    day_pnl = 0
    
    for trade in all_trades:
        # Check Day (simplified)
        trade_date = trade['time'].date()
        if trade_date != current_day:
            # New Day
            current_day = trade_date
            daily_start_balance = balance
            day_pnl = 0
            
        # Calculate Risk Amount ($)
        # 0.5% of CURRENT balance (Compounding) or INITIAL?
        # Prop firms usually based on Initial or Equity?
        # Let's use Current Balance for growth, but check DD against High Watermark.
        
        risk_amount = balance * RISK_PER_TRADE
        pnl_dollar = risk_amount * trade['r_multiple']
        
        # Update Balance
        balance += pnl_dollar
        equity_curve.append(balance)
        
        day_pnl += pnl_dollar
        
        # Stats
        if pnl_dollar > 0:
            wins += 1; gross_win += pnl_dollar
        else:
            losses += 1; gross_loss += abs(pnl_dollar)

    # --- METRICS ---
    final_balance = balance
    net_profit = final_balance - INITIAL_CAPITAL
    total_trades = wins + losses
    
    series = pd.Series(equity_curve)
    peak = series.cummax()
    drawdown = (series - peak) / peak * 100
    max_dd = abs(drawdown.min())
    
    print("\n" + "="*50)
    print("🏆 PROP FIRM CHALLENGE SIMULATION (5 ASSETS)")
    print("="*50)
    print(f"Risk Per Trade:      {RISK_PER_TRADE*100}%")
    print(f"Total Trades:        {total_trades}")
    print("-" * 30)
    print(f"Initial Balance:     ${INITIAL_CAPITAL:,.2f}")
    print(f"Final Balance:       ${final_balance:,.2f}")
    print(f"Net Profit:          ${net_profit:,.2f} ({net_profit/INITIAL_CAPITAL*100:.2f}%)")
    print("-" * 30)
    print(f"Profit Factor:       {gross_win/gross_loss:.2f}")
    print(f"Win Rate:            {wins/total_trades*100:.1f}%")
    print("-" * 30)
    print(f"Max Drawdown:        {max_dd:.2f}% (Limit: 10%)")
    
    if max_dd > 10:
        print("❌ FAILED: Drawdown Limit Breached")
    elif net_profit/INITIAL_CAPITAL < 0.10:
        print("⚠️ IN PROGRESS: Profit Target Not Reached Yet")
    else:
        print("✅ PASSED: Challenge Completed!")

if __name__ == "__main__":
    simulate_portfolio()
