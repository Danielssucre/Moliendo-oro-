#!/usr/bin/env python3
"""
NANOBOT HIVE V5: INSTITUTIONAL BACKTEST 🏦
Objective: Compare performance with senior risk rules (One Pair One Trade, Cap 3, Correlation).
"""
import sys
import os
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# Silicon MT5
try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

# --- CONFIG ---
INITIAL_CAPITAL = 10000
BASE_RISK_PER_TRADE = 0.004 # 0.4%
RR_TARGET = 1.5
SL_ATR_MULT = 2.0
PORTFOLIO_CAP = 3

ASSETS = [
    "AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", 
    "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", 
    "USDCAD"
]
TIMEFRAME_H1 = 16385

def get_data():
    if not MT5_AVAILABLE or not mt5.initialize():
        print("❌ MT5 Failed")
        return {}
        
    print(f"📊 FETCHING DATA FOR INSTITUTIONAL BACKTEST...")
    data = {}
    count = 1500 # Approx 60 days
    
    for symbol in ASSETS:
        if not mt5.symbol_select(symbol, True): continue
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME_H1, 0, count)
        if rates is None or len(rates) == 0: continue
            
        d_list = []
        for r in rates: d_list.append(list(r))
        df = pd.DataFrame(d_list, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'tick_volume':'Volume'}, inplace=True)
        
        # Indicators
        df['ema_9'] = df['Close'].ewm(span=9).mean()
        df['ema_15'] = df['Close'].ewm(span=15).mean()
        df['ema_200'] = df['Close'].ewm(span=200).mean()
        
        # ATR / Vol
        high = df['High']; low = df['Low']; close = df['Close']
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
        
        # ADX
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
        plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
        minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
        atr1 = df['atr']
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr1)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr1)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        
        data[symbol] = df
        
    return data

def run_institutional_backtest(data_map):
    print("\n🏦 INSTITUTIONAL RISK BACKTEST (Risk Manager 2.0) 🛡️")
    print(f"Rules: Cap {PORTFOLIO_CAP} | One Trade Per Pair | DD Shield | USD Correlation")
    print("-" * 75)
    
    # Pre-calculate all signals across timeline
    signals = []
    for symbol, df in data_map.items():
        for i in range(200, len(df)-48):
            row = df.iloc[i]
            if not (row['adx'] > 25 and row['volatility'] < 16): continue
            
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
            
            if sig != 0:
                signals.append({
                    'time': row.name,
                    'symbol': symbol,
                    'signal': sig,
                    'entry': row['Close'],
                    'atr': row['atr'],
                    'df': df,
                    'idx': i
                })
    
    signals.sort(key=lambda x: x['time'])
    
    # Simulation State
    balance = INITIAL_CAPITAL
    equity = INITIAL_CAPITAL
    daily_start_balance = INITIAL_CAPITAL
    current_day = None
    
    active_trades = [] # List of dicts
    history = []
    
    for s in signals:
        # 1. Update Current Time and Daily Balance
        sim_time = s['time']
        if current_day != sim_time.date():
            current_day = sim_time.date()
            daily_start_balance = balance
            
        # 2. Check and Close Active Trades (Simplified: Check up to current signal time)
        # In a real tick backtest this is more granular, but for H1 signals we check expiration
        still_active = []
        for t in active_trades:
            # Check price movement for t's symbol between t['time'] and sim_time
            # For simplicity in H1 backtest, trades are closed inside the loop before processing new signal
            # BUT we should check if they closed BEFORE this signal arrived.
            # However, since signals are sorted, we can assume we check if existing trades hit TP/SL 
            # by looking at the period between trade entry and current signal time.
            
            # Simplified logic: If signal time > trade exit time, trade is closed.
            # We need to find the exit time first.
            pass
        
        # Actually, let's do a more robust loop: Iterate by Hour.
        pass

    # RE-THINK: Chronological Simulation
    balance = INITIAL_CAPITAL
    active_trades = []
    history = []
    
    # Get all unique times
    all_times = sorted(list(set([t for df in data_map.values() for t in df.index])))
    
    # Group signals by time
    sig_by_time = {}
    for s in signals:
        t = s['time']
        if t not in sig_by_time: sig_by_time[t] = []
        sig_by_time[t].append(s)

    current_day = None
    daily_start_balance = INITIAL_CAPITAL
    
    for t_now in all_times:
        if current_day != t_now.date():
            current_day = t_now.date()
            daily_start_balance = balance

        # A. Update Active Trades
        active_remaining = []
        for trade in active_trades:
            df = data_map[trade['symbol']]
            if t_now not in df.index: 
                active_remaining.append(trade)
                continue
                
            row = df.loc[t_now]
            closed = False
            pnl = 0
            
            # --- PHASE 15: BREAK EVEN LOGIC ---
            # If price moves 1.5 ATR in favor, set SL to Entry (Break Even)
            if not trade.get('is_be', False):
                if trade['signal'] == 1: # Buy
                    if row['High'] >= (trade['entry'] + 1.5 * trade['atr']):
                        trade['sl'] = trade['entry']
                        trade['is_be'] = True
                else: # Sell
                    if row['Low'] <= (trade['entry'] - 1.5 * trade['atr']):
                        trade['sl'] = trade['entry']
                        trade['is_be'] = True

            # --- PHASE 15: AI GUARDIAN SIMULATION ---
            # If trade is in profit but stalls for > 6 hours, close it (Precaution)
            if not closed:
                duration_hrs = (t_now - trade['time']).total_seconds() / 3600
                current_pnl_pips = (row['Close'] - trade['entry']) if trade['signal'] == 1 else (trade['entry'] - row['Close'])
                if duration_hrs > 6 and current_pnl_pips > (0.5 * trade['atr']):
                    # Stall check: price hasn't made new high/low in 3 bars?
                    # Simplified: Random 10% chance AI predicts exhaustion, or just duration cap on profit.
                    # We'll use a simple rule: if at 10 hours and not at TP, AI closes if profit > 0.
                    if duration_hrs >= 10:
                        closed = True
                        pnl = (current_pnl_pips / abs(trade['entry'] - trade['original_sl'])) * trade['risk_usd']
            
            if not closed:
                if trade['signal'] == 1: # Buy
                    if row['Low'] <= trade['sl']:
                        closed = True; pnl = -trade['risk_usd'] if not trade.get('is_be') else 0
                    elif row['High'] >= trade['tp']:
                        closed = True; pnl = trade['risk_usd'] * RR_TARGET
                else: # Sell
                    if row['High'] >= trade['sl']:
                        closed = True; pnl = -trade['risk_usd'] if not trade.get('is_be') else 0
                    elif row['Low'] <= trade['tp']:
                        closed = True; pnl = trade['risk_usd'] * RR_TARGET
                    
            # Expiry (48h)
            if not closed and (t_now - trade['time']).total_seconds() >= 48 * 3600:
                closed = True
                pnl = (row['Close'] - trade['entry']) / (trade['entry'] - trade['original_sl']) * trade['risk_usd'] if trade['signal']==1 \
                      else (trade['entry'] - row['Close']) / (trade['original_sl'] - trade['entry']) * trade['risk_usd']

            if closed:
                balance += pnl
                history.append({'time': t_now, 'symbol': trade['symbol'], 'pnl': pnl, 'balance': balance})
            else:
                active_remaining.append(trade)
        
        active_trades = active_remaining

        # B. Check for New Signals
        if t_now in sig_by_time:
            for s in sig_by_time[t_now]:
                # 1. Cap Check
                if len(active_trades) >= PORTFOLIO_CAP: continue
                
                # 2. Duplicate Check
                if any(t['symbol'] == s['symbol'] for t in active_trades): continue
                
                # 3. Correlation Filter (USD)
                if "USD" in s['symbol']:
                    usd_exposure = 0
                    for t in active_trades:
                        if "USD" in t['symbol']:
                            # Simplified: count any USD exposure
                            usd_exposure += 1
                    if usd_exposure >= 2: continue # Institutional Limit

                # 4. Calculate Dynamic Risk
                daily_dd_pct = ((daily_start_balance - balance) / daily_start_balance) * 100
                risk_pct = BASE_RISK_PER_TRADE
                if daily_dd_pct > 2.0: 
                    risk_pct *= 0.5 # Shield
                
                # 5. Open Trade
                sl_dist = s['atr'] * SL_ATR_MULT
                tp_dist = sl_dist * RR_TARGET
                sl = s['entry'] - sl_dist if s['signal'] == 1 else s['entry'] + sl_dist
                tp = s['entry'] + tp_dist if s['signal'] == 1 else s['entry'] - tp_dist
                
                active_trades.append({
                    'time': t_now,
                    'symbol': s['symbol'],
                    'signal': s['signal'],
                    'entry': s['entry'],
                    'sl': sl,
                    'original_sl': sl,
                    'tp': tp,
                    'atr': s['atr'],
                    'risk_usd': balance * risk_pct,
                    'is_be': False
                })

    # Results
    if not history:
        print("⚠️ No trades taken in the simulation period.")
        return

    final_profit = (balance - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    win_rate = len([h for h in history if h['pnl'] > 0]) / len(history) * 100
    be_trades = len([h for h in history if h['pnl'] == 0])
    
    total_wins = sum([h['pnl'] for h in history if h['pnl'] > 0])
    total_losses = abs(sum([h['pnl'] for h in history if h['pnl'] < 0]))
    pf = total_wins / total_losses if total_losses > 0 else 0

    print(f"✅ Backtest Complete.")
    print(f"📈 Final Balance: ${balance:,.2f} ({final_profit:+.2f}%)")
    print(f"📊 Win Rate: {win_rate:.1f}% | Total Trades: {len(history)}")
    print(f"🛡️ Break Even Trades: {be_trades} | Profit Factor: {pf:.2f}")
    
    # Estimate days to 5%
    days_to_5 = None
    start_date = history[0]['time']
    for h in history:
        if (h['balance'] - INITIAL_CAPITAL) >= (INITIAL_CAPITAL * 0.05):
            days_to_5 = (h['time'] - start_date).days
            break
            
    if days_to_5:
        print(f"⏰ Time to 5% Profit: ~{days_to_5} days")
    else:
        print(f"ℹ️ Profit target of 5% not reached in this window.")

if __name__ == "__main__":
    d = get_data()
    if d:
        run_institutional_backtest(d)
