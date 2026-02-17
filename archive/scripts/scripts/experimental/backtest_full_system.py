#!/usr/bin/env python3
"""
NANOBOT FINAL SYSTEM BACKTEST (Technical + ML)
- Capital: $10,000
- Risk: 0.2%
- ML Filter: Stop Hunt Model (Risk < 0.65)
- Mode: Hybrid (Trend + Range)
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np
import logging

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.ml.stop_hunt_model import StopHuntModel
    ML_ENABLED = True
except ImportError:
    ML_ENABLED = False
    print("⚠️ ML Module not found. Simulating Technical Only.")

# --- CONFIG ---
INITIAL_CAPITAL = 10000.0
RISK_PER_TRADE = 0.002 
PORTFOLIO = ["SOL-USD", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "GBPUSD=X"]
PERIOD = "60d"
INTERVAL = "15m"

# Init ML
if ML_ENABLED:
    stop_hunt_model = StopHuntModel()

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def generate_signals_with_features(df):
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
    
    return df

def run_backtest():
    print(f"📉 STARTING FINAL SYSTEM BACKTEST (60 Days)")
    print(f"   Capital: ${INITIAL_CAPITAL:,.2f}")
    if ML_ENABLED: print("   🧠 ML Filter: ACTIVE (Stop Hunt Detection)")
    print("-" * 60)
    
    all_trades = []
    
    for symbol in PORTFOLIO:
        print(f"   Processing {symbol}...", end="\r")
        try:
            # Use Ticker for consistency with Live Bot
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=PERIOD, interval=INTERVAL)
            
            if data.empty: continue
            data.columns = data.columns.str.lower()
            
            df = generate_signals_with_features(data)
            
            in_trade = False
            trade = None
            
            # Iterate
            for i in range(200, len(df)):
                row = df.iloc[i]
                prev = df.iloc[i-1]
                ts = row.name
                
                # Check Exit
                if in_trade:
                    exit_price = None
                    pnl_r = 0
                    
                    if trade['direction'] == 1:
                        if row['low'] <= trade['sl']: exit_price = trade['sl']; pnl_r = -1.0 # Hit SL
                        elif row['high'] >= trade['tp']: exit_price = trade['tp']; pnl_r = trade['rr'] # Hit TP
                    else:
                        if row['high'] >= trade['sl']: exit_price = trade['sl']; pnl_r = -1.0
                        elif row['low'] <= trade['tp']: exit_price = trade['tp']; pnl_r = trade['rr']
                        
                    if exit_price:
                        trade['exit_time'] = ts
                        trade['pnl_r'] = pnl_r
                        all_trades.append(trade)
                        in_trade = False
                    continue
                
                # Check Entry
                sig = 0
                strategy = "None"
                
                # TECHNICAL LOGIC
                if row['adx'] > 25: # Trend
                    if row['ema_9'] > row['ema_15'] and prev['ema_9'] <= prev['ema_15'] and row['close'] > row['ema_200']:
                        sig = 1; strategy = "Trend Buy"
                    elif row['ema_9'] < row['ema_15'] and prev['ema_9'] >= prev['ema_15'] and row['close'] < row['ema_200']:
                        sig = -1; strategy = "Trend Sell"
                else: # Range
                    if row['rsi'] < 35: sig = 1; strategy = "Range Buy"
                    elif row['rsi'] > 65: sig = -1; strategy = "Range Sell"
                
                if sig != 0:
                    # ML FILTER LOGIC
                    ml_risk = 0.2 # Default low risk
                    if ML_ENABLED and stop_hunt_model:
                        # Extract features for THIS moment (lookback needed)
                        # We need valid dataframe slice up to i
                        # The extract_features uses df.tail(5)
                        slice_df = df.iloc[i-10:i+1] # Small buffer
                        indicators = {
                            'rsi': row['rsi'],
                            'adx': row['adx'],
                            'atr': row['atr'],
                            'vwap': row['close'] 
                        }
                        features = stop_hunt_model.extract_features(slice_df, row['close'], indicators)
                        ml_risk = stop_hunt_model.predict_risk(features)
                        
                        if ml_risk > 0.65:
                            # BLOCKED BY ML
                            # print(f"🛑 Blocked {strategy} on {symbol} at {ts} (Risk: {ml_risk:.2f})")
                            continue 
                            
                    # ACCEPTED
                    entry_price = row['close']
                    atr = row['atr']
                    if strategy.startswith("Trend"):
                        sl_mult = 1.0; rr = 2.0
                    else:
                        sl_mult = 1.5; rr = 3.0
                        
                    sl_dist = atr * sl_mult
                    if sig == 1: sl = entry_price - sl_dist; tp = entry_price + (sl_dist * rr)
                    else: sl = entry_price + sl_dist; tp = entry_price - (sl_dist * rr)
                    
                    trade = {
                        'symbol': symbol,
                        'entry_time': ts,
                        'direction': sig,
                        'entry': entry_price,
                        'sl': sl, 'tp': tp,
                        'rr': rr,
                        'ml_risk': ml_risk
                    }
                    in_trade = True
                    
        except Exception as e:
            print(f"Error {symbol}: {e}")

    # --- SIMULATE CURVE ---
    print("\n🎬 SIMULATING EQUITY CURVE...")
    if not all_trades:
        print("❌ No trades generated.")
        return

    all_trades.sort(key=lambda x: x['entry_time'])
    
    balance = INITIAL_CAPITAL
    equity_curve = [balance]
    wins = 0; losses = 0
    gross_win = 0; gross_loss = 0
    
    for t in all_trades:
        risk_amt = balance * RISK_PER_TRADE
        pnl_usd = risk_amt * t['pnl_r']
        
        balance += pnl_usd
        equity_curve.append(balance)
        
        if pnl_usd > 0: wins += 1; gross_win += pnl_usd
        else: losses += 1; gross_loss += abs(pnl_usd)
        
    net_profit = balance - INITIAL_CAPITAL
    win_rate = (wins / len(all_trades)) * 100 if all_trades else 0
    pf = (gross_win / gross_loss) if gross_loss > 0 else 0
    
    # Drawdown
    series = pd.Series(equity_curve)
    peak = series.cummax()
    dd = (series - peak) / peak * 100
    max_dd = abs(dd.min())

    print("\n" + "="*50)
    print("🏆 FINAL SYSTEM REPORT (60 Days)")
    print("="*50)
    print(f"Risk Per Trade:      {RISK_PER_TRADE*100:.1f}%")
    print(f"ML Filter:           {'ON (Stop Hunt)' if ML_ENABLED else 'OFF'}")
    print("-" * 30)
    print(f"Initial Balance:     ${INITIAL_CAPITAL:,.2f}")
    print(f"Final Balance:       ${balance:,.2f}")
    print(f"Net Profit:          ${net_profit:,.2f} ({net_profit/INITIAL_CAPITAL*100:.2f}%)")
    print("-" * 30)
    print(f"Total Trades:        {len(all_trades)}")
    print(f"Win Rate:            {win_rate:.2f}%")
    print(f"Profit Factor:       {pf:.2f}")
    print(f"Max Drawdown:        {max_dd:.2f}%")
    print("-" * 30)
    
    if max_dd > 10:
        print("❌ FAILED: Drawdown > 10%")
    elif net_profit > 1000: # 10%
        print("✅ PASSED: Target Reached!")
    else:
        print("⚠️ PROFITABLE but Target Pending.")

if __name__ == "__main__":
    run_backtest()
