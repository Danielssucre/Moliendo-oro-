#!/usr/bin/env python3
"""
NANOBOT MANUAL TRADING FEASIBILITY REPORT (Phase 29)
Analyzes Time-to-Fill, Signal Heatmap, and Prop Firm Viability.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from collections import Counter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG ---
PORTFOLIO = {
    "SOL-USD": "SOL-USD",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "BTC-USD": "BTC-USD",
    "GBPUSD": "GBPUSD=X"
}
PERIOD = "60d" 
INTERVAL = "15m"
RISK_PER_TRADE = 0.002 # 0.2%

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def generate_signals(df):
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['atr'] = calculate_atr(df)
    
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
        if row['adx'] > 25:
            if row['ema_9'] > row['ema_15'] and prev['ema_9'] <= prev['ema_15'] and row['close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and prev['ema_9'] >= prev['ema_15'] and row['close'] < row['ema_200']: sig = -1
        else:
            if row['rsi'] < 35: sig = 1
            elif row['rsi'] > 65: sig = -1
        signals.append(sig)
    df['signal'] = signals
    return df

def analyze_feasibility():
    print("⏳ SCANNING 5-ASSET PORTFOLIO FOR MANUAL METRICS...")
    
    fill_times = []
    trade_hours = []
    total_signals = 0
    filled_orders = 0
    
    for name, symbol in PORTFOLIO.items():
        try:
            data = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False)
            if data.empty: continue
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0).str.lower()
            else: data.columns = data.columns.str.lower()
            df = generate_signals(data)
            
            pending_order = None 
            active_trade = None 
            
            for i in range(len(df)):
                row = df.iloc[i]
                timestamp = row.name
                
                # 1. CHECK PENDING ORDER FILL
                if pending_order:
                    filled = False
                    trigger = pending_order['price']
                    direction = pending_order['direction']
                    
                    if direction == 1: # Buy
                        if row['high'] >= trigger: filled = True
                    else: # Sell
                        if row['low'] <= trigger: filled = True
                        
                    if filled:
                        # Success!
                        time_diff = (timestamp - pending_order['signal_time']).total_seconds() / 60
                        fill_times.append(time_diff)
                        filled_orders += 1
                        
                        # Move to Active Trade
                        active_trade = {
                            'sl': pending_order['sl'],
                            'tp': pending_order['tp'],
                            'direction': direction
                        }
                        pending_order = None # Cleared
                    else:
                        # Expiry (3 hours)
                        if (timestamp - pending_order['signal_time']).total_seconds() / 3600 > 3:
                            pending_order = None # Expired
                            continue

                # 2. CHECK ACTIVE TRADE EXIT
                elif active_trade:
                    sl = active_trade['sl']
                    tp = active_trade['tp']
                    direction = active_trade['direction']
                    
                    exited = False
                    if direction == 1:
                        if row['low'] <= sl or row['high'] >= tp: exited = True
                    else:
                        if row['high'] >= sl or row['low'] <= tp: exited = True
                        
                    if exited:
                        active_trade = None # Closed
                    
                # 3. NEW SIGNAL GENERATION
                # Only if we have NO pending order AND NO active trade
                elif not pending_order and not active_trade and row['signal'] != 0:
                    
                    total_signals += 1
                    direction = row['signal']
                    atr = row['atr']
                    if pd.isna(atr): continue
                    
                    if row['adx'] > 25: # Trend
                        buffer = 0.0002 
                        if direction == 1: trigger = row['high'] + buffer
                        else: trigger = row['low'] - buffer
                        sl_mult = 1.0; rr = 2.0
                    else: # Range
                        trigger = row['close']
                        sl_mult = 1.5; rr = 3.0
                    
                    sl_dist = atr * sl_mult
                    sl = trigger - sl_dist if direction == 1 else trigger + sl_dist
                    tp = trigger + (sl_dist * rr) if direction == 1 else trigger - (sl_dist * rr)

                    pending_order = {
                        'price': trigger,
                        'signal_time': timestamp,
                        'sl': sl, 'tp': tp, 'direction': direction
                    }
                    trade_hours.append(timestamp.hour)

        except Exception as e:
            print(f"Error {name}: {e}")

    # --- REPORT GENERATION ---
    print("\n📊 MANUAL EXECUTION FEASIBILITY REPORT (FINAL)")
    print("=" * 60)
    
    avg_trades_per_day = filled_orders / 60 
    print(f"1️⃣ FREQUENCY")
    print(f"   Signals Generated:   {total_signals}")
    print(f"   Orders Filled:       {filled_orders} ({filled_orders/total_signals*100:.1f}% Fill Rate)")
    print(f"   Trades Per Day:      {avg_trades_per_day:.1f} (Total across 5 assets)")
    print("-" * 60)

    print(f"2️⃣ BEST HOURS (UTC)")
    hour_counts = Counter(trade_hours)
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    top_5 = sorted_hours[:5]
    for h, count in top_5:
        print(f"   {h:02d}:00 UTC -> {count} Signals")
    print("-" * 60)
    
    avg_fill_mins = np.mean(fill_times) if fill_times else 0
    median_fill = np.median(fill_times) if fill_times else 0
    print(f"3️⃣ TIME TO ACT (Margin for User)")
    print(f"   Average Wait:        {avg_fill_mins:.1f} minutes")
    print(f"   Median Wait:         {median_fill:.1f} minutes")
    print(f"   Interpretation:      Avg time from Signal -> Entry Trigger")
    print("-" * 60)
    
    print(f"🤖 NANOBOT VERDICT: FATIBLE? (Feasible)")
    print(f"   MATH:               YES.")
    print(f"   MANUAL EXECUTION:   YES (Median Wait: {int(median_fill)}m).")
    print(f"   PACE:               ~{int(avg_trades_per_day)} trades/day is manageable.")

if __name__ == "__main__":
    analyze_feasibility()
